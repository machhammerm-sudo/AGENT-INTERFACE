"""Orchestriert Stufe A, Stufe B, Gedaechtnis und (gated) Eskalation fuer ein
hochgeladenes Dokument. Alles rein lokal, ausser der ausdruecklich erlaubten
Eskalation an Claude (P16)."""

import json
from datetime import datetime

from sqlalchemy.orm import Session

from . import memory as memory_mod
from .escalation import escalate_field
from .field_extraction import FieldCandidate, FieldSpec, extract_fields, status_from_candidates
from .models import (
    CustomerPrivacySettings,
    DocumentFieldResult,
    DocumentRegion,
    DocumentStatus,
    ExtractionField,
    ExtractionMetricEvent,
    FieldResultSource,
    FieldStatus,
    MetricOutcome,
    TitleblockDocument,
)
from .region_detection import detect_rotation, find_titleblock_candidates, has_grid_frame, _rotate
from .rendering import render_page

LOW_DPI = 150
HIGH_DPI = 300


def get_document_region_image(db: Session, document: TitleblockDocument):
    """Rendert das Dokument neu und schneidet auf den gewaehlten
    Titelblock-Bereich zu - fuer die Anzeige in der Pruefen-Ansicht."""
    from .models import DocumentRegion

    chosen = (
        db.query(DocumentRegion)
        .filter_by(document_id=document.id, is_chosen=True)
        .first()
    )
    if chosen is None:
        raise ValueError("Kein Bereich fuer dieses Dokument gefunden")

    high_res = render_page(document.stored_path, dpi=HIGH_DPI)
    upright = _rotate(high_res.image, chosen.rotation)
    w, h = upright.size
    box = (
        int(chosen.rel_x * w), int(chosen.rel_y * h),
        int((chosen.rel_x + chosen.rel_w) * w), int((chosen.rel_y + chosen.rel_h) * h),
    )
    return upright.crop(box)


def get_field_crop_image(db: Session, document: TitleblockDocument, rel_bbox: tuple[float, float, float, float]):
    """Schneidet innerhalb des Titelblock-Bereichs auf die Lage eines
    einzelnen Feldes zu (mit etwas Rand), damit ein Mensch den Ausschnitt im
    Original sehen kann."""
    region_image = get_document_region_image(db, document)
    w, h = region_image.size
    pad_x, pad_y = int(w * 0.03), int(h * 0.03)
    box = (
        max(0, int(rel_bbox[0] * w) - pad_x),
        max(0, int(rel_bbox[1] * h) - pad_y),
        min(w, int((rel_bbox[0] + rel_bbox[2]) * w) + pad_x),
        min(h, int((rel_bbox[1] + rel_bbox[3]) * h) + pad_y),
    )
    if box[2] <= box[0] or box[3] <= box[1]:
        return region_image
    return region_image.crop(box)


def _candidate_to_dict(c: FieldCandidate) -> dict:
    return {
        "value": c.value,
        "assignment_confidence": round(c.assignment_confidence, 3),
        "ocr_confidence": round(c.ocr_confidence, 1),
        "match_type": c.match_type,
        "label_score": round(c.label_score, 1),
        "rel_bbox": list(c.rel_bbox),
    }


def _load_field_specs(db: Session) -> list[FieldSpec]:
    rows = db.query(ExtractionField).order_by(ExtractionField.sort_order).all()
    return [
        FieldSpec(
            field_key=r.field_key,
            label=r.label,
            synonyms=json.loads(r.synonyms),
            format_regex=r.format_regex,
        )
        for r in rows
    ]


def process_document(db: Session, document: TitleblockDocument) -> None:
    document.status = DocumentStatus.PROCESSING
    db.commit()

    try:
        _run_pipeline(db, document)
        document.status = DocumentStatus.PROCESSED
        document.processed_at = datetime.utcnow()
        db.commit()
    except Exception as exc:  # Fehler sichtbar machen statt Dokument zu verlieren
        document.status = DocumentStatus.ERROR
        document.error_message = str(exc)
        db.commit()
        raise


def _run_pipeline(db: Session, document: TitleblockDocument) -> None:
    field_specs = _load_field_specs(db)
    all_synonyms = [s for f in field_specs for s in f.synonyms]

    low_res = render_page(document.stored_path, dpi=LOW_DPI)
    rotation = detect_rotation(low_res.image, all_synonyms)
    upright_low = _rotate(low_res.image, rotation)

    candidates = find_titleblock_candidates(upright_low, all_synonyms)

    for cand in candidates:
        db.add(
            DocumentRegion(
                document_id=document.id,
                page_index=0,
                rel_x=cand.rel_x, rel_y=cand.rel_y, rel_w=cand.rel_w, rel_h=cand.rel_h,
                rotation=rotation,
                score=cand.score,
                method=cand.method,
                is_chosen=(cand is candidates[0]),
            )
        )
    db.commit()

    chosen = candidates[0]

    high_res = render_page(document.stored_path, dpi=HIGH_DPI)
    upright_high = _rotate(high_res.image, rotation)
    w, h = upright_high.size
    box = (
        int(chosen.rel_x * w), int(chosen.rel_y * h),
        int((chosen.rel_x + chosen.rel_w) * w), int((chosen.rel_y + chosen.rel_h) * h),
    )
    region_crop = upright_high.crop(box)

    has_frame = has_grid_frame(region_crop)
    results = extract_fields(region_crop, field_specs, has_frame)
    results_by_key = {r.field_key: r for r in results}

    # --- Gedaechtnis pro Kunde ---
    pattern = None
    if document.customer_id is not None:
        label_positions = {
            r.field_key: (r.candidates[0].rel_bbox[0], r.candidates[0].rel_bbox[1])
            for r in results if r.candidates and r.candidates[0].label_score > 0
        }
        fingerprint = memory_mod.compute_fingerprint(region_crop, label_positions)
        pattern, _is_new = memory_mod.find_or_create_pattern(db, document.customer_id, fingerprint)
        document.matched_pattern_id = pattern.id

        for spec in field_specs:
            mem_candidate = memory_mod.memory_candidates_for_field(db, pattern, spec.field_key, region_crop)
            if mem_candidate is None:
                continue
            result = results_by_key[spec.field_key]
            existing_same_value = next(
                (c for c in result.candidates if c.value.strip().lower() == mem_candidate.value.strip().lower()),
                None,
            )
            if existing_same_value:
                existing_same_value.assignment_confidence = max(
                    existing_same_value.assignment_confidence, mem_candidate.assignment_confidence
                )
                existing_same_value.match_type = "memory+ocr"
            else:
                result.candidates.insert(0, mem_candidate)
            result.candidates.sort(key=lambda c: c.assignment_confidence, reverse=True)
            result.candidates = result.candidates[:3]
            result.status = status_from_candidates(result.candidates, has_frame, spec.field_key, field_specs)

    # --- Eskalation (P16) nur lokal-unsicher UND Schalter aktiv ---
    privacy = None
    if document.customer_id is not None:
        privacy = db.get(CustomerPrivacySettings, document.customer_id)

    if privacy and privacy.allow_cloud_escalation:
        for spec in field_specs:
            result = results_by_key[spec.field_key]
            if result.status == "green":
                continue
            if result.candidates:
                bbox = result.candidates[0].rel_bbox
            else:
                bbox = (0.0, 0.0, 1.0, 1.0)
            cw, ch = region_crop.size
            pad_x, pad_y = int(cw * 0.05), int(ch * 0.05)
            crop_box = (
                max(0, int(bbox[0] * cw) - pad_x), max(0, int(bbox[1] * ch) - pad_y),
                min(cw, int((bbox[0] + bbox[2]) * cw) + pad_x), min(ch, int((bbox[1] + bbox[3]) * ch) + pad_y),
            )
            if crop_box[2] <= crop_box[0] or crop_box[3] <= crop_box[1]:
                crop_box = (0, 0, cw, ch)
            field_crop = region_crop.crop(crop_box)

            escalated = escalate_field(spec, field_crop)
            if escalated:
                result.candidates.insert(0, escalated)
                result.candidates = result.candidates[:3]
                result.status = "yellow"  # Cloud-Ergebnis braucht immer menschliche Bestaetigung

    # --- Ergebnisse speichern ---
    for result in results:
        top = result.candidates[0] if result.candidates else None
        source_map = {
            "memory": FieldResultSource.MEMORY,
            "memory+ocr": FieldResultSource.MEMORY,
            "escalation": FieldResultSource.ESCALATION,
        }
        db.add(
            DocumentFieldResult(
                document_id=document.id,
                field_key=result.field_key,
                status=FieldStatus(result.status),
                chosen_value=top.value if top else None,
                chosen_source=source_map.get(top.match_type, FieldResultSource.OCR) if top else None,
                assignment_confidence=top.assignment_confidence if top else None,
                ocr_confidence=top.ocr_confidence if top else None,
                candidates_json=json.dumps([_candidate_to_dict(c) for c in result.candidates], ensure_ascii=False),
            )
        )

        if result.status == "green":
            db.add(
                ExtractionMetricEvent(
                    document_id=document.id,
                    customer_id=document.customer_id,
                    field_key=result.field_key,
                    pattern_id=pattern.id if pattern else None,
                    outcome=MetricOutcome.GREEN_UNREVIEWED,
                )
            )
            db.commit()
            from . import metrics as metrics_mod
            metrics_mod.maybe_sample_green_field(db, document.id, result.field_key)
        elif result.status == "red":
            db.add(
                ExtractionMetricEvent(
                    document_id=document.id,
                    customer_id=document.customer_id,
                    field_key=result.field_key,
                    pattern_id=pattern.id if pattern else None,
                    outcome=MetricOutcome.RED_UNRESOLVED,
                )
            )

    db.commit()
