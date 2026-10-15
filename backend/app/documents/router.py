import io
import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..config import PLAN_UPLOADS_DIR
from ..database import get_db
from . import memory as memory_mod
from . import metrics as metrics_mod
from . import schemas
from .models import (
    BenchmarkRun,
    Customer,
    CustomerPrivacySettings,
    DocumentFieldResult,
    DocumentRegion,
    ExtractionField,
    ExtractionMetricEvent,
    FieldStatus,
    GreenSampleCheck,
    HumanAction,
    MetricOutcome,
    TitleblockDocument,
    TitleblockPattern,
)
from .pipeline import get_document_region_image, get_field_crop_image, process_document

router = APIRouter(prefix="/api/documents", tags=["documents"])


# ---------- Kunden ----------


@router.get("/customers", response_model=list[schemas.CustomerOut])
def list_customers(db: Session = Depends(get_db)):
    return db.query(Customer).order_by(Customer.name).all()


@router.post("/customers", response_model=schemas.CustomerOut)
def create_customer(payload: schemas.CustomerCreate, db: Session = Depends(get_db)):
    customer = Customer(name=payload.name)
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


# ---------- Extraktionsfelder (Synonym-Liste) ----------


@router.get("/fields", response_model=list[schemas.ExtractionFieldOut])
def list_fields(db: Session = Depends(get_db)):
    rows = db.query(ExtractionField).order_by(ExtractionField.sort_order).all()
    return [
        schemas.ExtractionFieldOut(
            id=r.id, field_key=r.field_key, label=r.label,
            synonyms=json.loads(r.synonyms), format_regex=r.format_regex,
            is_user_edited=r.is_user_edited,
        )
        for r in rows
    ]


@router.patch("/fields/{field_id}", response_model=schemas.ExtractionFieldOut)
def update_field(field_id: int, payload: schemas.ExtractionFieldUpdate, db: Session = Depends(get_db)):
    row = db.get(ExtractionField, field_id)
    if not row:
        raise HTTPException(404, "Feld nicht gefunden")
    if payload.label is not None:
        row.label = payload.label
    if payload.synonyms is not None:
        row.synonyms = json.dumps(payload.synonyms, ensure_ascii=False)
    if payload.format_regex is not None:
        row.format_regex = payload.format_regex
    row.is_user_edited = True
    db.commit()
    db.refresh(row)
    return schemas.ExtractionFieldOut(
        id=row.id, field_key=row.field_key, label=row.label,
        synonyms=json.loads(row.synonyms), format_regex=row.format_regex,
        is_user_edited=row.is_user_edited,
    )


# ---------- Datenschutz-Schalter pro Kunde ----------


def _get_or_create_privacy(db: Session, customer_id: int) -> CustomerPrivacySettings:
    row = db.get(CustomerPrivacySettings, customer_id)
    if row is None:
        row = CustomerPrivacySettings(customer_id=customer_id)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


@router.get("/privacy/{customer_id}", response_model=schemas.PrivacySettingsOut)
def get_privacy(customer_id: int, db: Session = Depends(get_db)):
    if not db.get(Customer, customer_id):
        raise HTTPException(404, "Kunde nicht gefunden")
    return _get_or_create_privacy(db, customer_id)


@router.patch("/privacy/{customer_id}", response_model=schemas.PrivacySettingsOut)
def update_privacy(customer_id: int, payload: schemas.PrivacySettingsUpdate, db: Session = Depends(get_db)):
    if not db.get(Customer, customer_id):
        raise HTTPException(404, "Kunde nicht gefunden")
    row = _get_or_create_privacy(db, customer_id)
    now = datetime.utcnow()

    if payload.contribute_anonymized_structure_data is not None:
        if payload.contribute_anonymized_structure_data and not row.contribute_anonymized_structure_data:
            row.consent_given_at = now
        if not payload.contribute_anonymized_structure_data and row.contribute_anonymized_structure_data:
            row.consent_withdrawn_at = now
        row.contribute_anonymized_structure_data = payload.contribute_anonymized_structure_data

    if payload.allow_cloud_escalation is not None:
        if payload.allow_cloud_escalation and not row.allow_cloud_escalation:
            row.escalation_consent_at = now
        row.allow_cloud_escalation = payload.allow_cloud_escalation

    db.commit()
    db.refresh(row)
    return row


# ---------- Upload & Verarbeitung ----------


@router.post("/upload", response_model=schemas.DocumentDetailOut)
def upload_document(
    customer_id: int | None = None,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}:
        raise HTTPException(400, "Nicht unterstuetztes Dateiformat - bitte PDF oder Bild hochladen.")

    safe_name = f"{uuid.uuid4().hex}{suffix}"
    dest_path = PLAN_UPLOADS_DIR / safe_name
    with dest_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    document = TitleblockDocument(
        customer_id=customer_id, filename=file.filename, stored_path=str(dest_path)
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    try:
        process_document(db, document)
    except Exception as exc:
        # Dokument bleibt mit Fehlerstatus erhalten, statt verloren zu gehen
        raise HTTPException(500, f"Verarbeitung fehlgeschlagen: {exc}")

    return _document_detail(db, document.id)


# ---------- Abfragen ----------


def _document_detail(db: Session, document_id: int) -> schemas.DocumentDetailOut:
    document = db.get(TitleblockDocument, document_id)
    if not document:
        raise HTTPException(404, "Dokument nicht gefunden")

    field_labels = {f.field_key: f.label for f in db.query(ExtractionField).all()}

    regions = db.query(DocumentRegion).filter_by(document_id=document_id).all()
    field_results = db.query(DocumentFieldResult).filter_by(document_id=document_id).all()

    fields_out = []
    for r in field_results:
        candidates = json.loads(r.candidates_json) if r.candidates_json else []
        fields_out.append(
            schemas.FieldResultOut(
                id=r.id, field_key=r.field_key, label=field_labels.get(r.field_key, r.field_key),
                status=r.status, chosen_value=r.chosen_value, chosen_source=r.chosen_source,
                assignment_confidence=r.assignment_confidence, ocr_confidence=r.ocr_confidence,
                candidates=[schemas.FieldCandidateOut(**c) for c in candidates],
                reviewed=r.reviewed, human_action=r.human_action,
                corrected_value=r.corrected_value, reviewed_at=r.reviewed_at,
            )
        )

    return schemas.DocumentDetailOut(
        document=schemas.DocumentOut.model_validate(document),
        regions=[schemas.RegionOut.model_validate(r) for r in regions],
        fields=fields_out,
    )


@router.get("", response_model=list[schemas.DocumentOut])
def list_documents(customer_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(TitleblockDocument)
    if customer_id is not None:
        query = query.filter_by(customer_id=customer_id)
    return query.order_by(TitleblockDocument.uploaded_at.desc()).all()

# ---------- Laufende Kennzahl (echte Kundenplaene) ----------


@router.get("/metrics", response_model=schemas.LiveMetricsOut)
def get_live_metrics(customer_id: int | None = None, since_days: int | None = None, db: Session = Depends(get_db)):
    result = metrics_mod.compute_live_metrics(db, customer_id, since_days)
    undetected = metrics_mod.estimated_undetected_error_rate(db, customer_id)
    return schemas.LiveMetricsOut(
        overall_correct_rate=result["overall_correct_rate"],
        overall_n=result["overall_n"],
        per_field=result["per_field"],
        per_pattern=result["per_pattern"],
        estimated_undetected_error_rate=undetected["rate"],
        estimated_undetected_n=undetected["n"],
    )


@router.get("/metrics/history", response_model=list[schemas.WeeklyHistoryPoint])
def get_metrics_history(customer_id: int | None = None, weeks: int = 12, db: Session = Depends(get_db)):
    return metrics_mod.compute_weekly_history(db, customer_id, weeks)


@router.get("/sample-checks", response_model=list[schemas.SampleCheckOut])
def list_sample_checks(customer_id: int | None = None, db: Session = Depends(get_db)):
    return metrics_mod.pending_sample_checks(db, customer_id)


@router.post("/sample-checks/{check_id}/resolve", response_model=schemas.SampleCheckOut)
def resolve_sample_check(check_id: int, payload: schemas.SampleCheckResolve, db: Session = Depends(get_db)):
    if payload.verdict not in {"correct", "incorrect"}:
        raise HTTPException(400, "verdict muss 'correct' oder 'incorrect' sein")
    check = metrics_mod.resolve_sample_check(db, check_id, payload.verdict)
    if check is None:
        raise HTTPException(404, "Stichprobe nicht gefunden")
    return check


# ---------- Pruefstand (Entwickleransicht) ----------


@router.get("/benchmark/history", response_model=list[schemas.BenchmarkRunOut])
def benchmark_history(db: Session = Depends(get_db)):
    runs = db.query(BenchmarkRun).order_by(BenchmarkRun.run_at.desc()).limit(50).all()
    return [
        schemas.BenchmarkRunOut(
            id=r.id, run_at=r.run_at, overall_hit_rate=r.overall_hit_rate,
            false_green_rate=r.false_green_rate, no_result_rate=r.no_result_rate,
            plan_count=r.plan_count,
            per_field=json.loads(r.per_field_json), per_template=json.loads(r.per_template_json),
        )
        for r in runs
    ]


@router.post("/benchmark/run", response_model=schemas.BenchmarkRunOut)
def trigger_benchmark_run(db: Session = Depends(get_db)):
    from .testbench.run_benchmark import run_benchmark

    try:
        result = run_benchmark()
    except FileNotFoundError as exc:
        raise HTTPException(409, str(exc))

    run = BenchmarkRun(
        overall_hit_rate=result["overall"]["hit_rate"],
        false_green_rate=result["overall"]["false_green_rate"],
        no_result_rate=result["overall"]["no_result_rate"],
        per_field_json=json.dumps(result["per_field"], ensure_ascii=False),
        per_template_json=json.dumps(result["per_template"], ensure_ascii=False),
        plan_count=result["plan_count"],
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    return schemas.BenchmarkRunOut(
        id=run.id, run_at=run.run_at, overall_hit_rate=run.overall_hit_rate,
        false_green_rate=run.false_green_rate, no_result_rate=run.no_result_rate,
        plan_count=run.plan_count,
        per_field=result["per_field"], per_template=result["per_template"],
    )


@router.get("/{document_id}", response_model=schemas.DocumentDetailOut)
def get_document(document_id: int, db: Session = Depends(get_db)):
    return _document_detail(db, document_id)


@router.get("/{document_id}/region-image")
def get_region_image(document_id: int, db: Session = Depends(get_db)):
    document = db.get(TitleblockDocument, document_id)
    if not document:
        raise HTTPException(404, "Dokument nicht gefunden")
    try:
        image = get_document_region_image(db, document)
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="image/png")


@router.get("/{document_id}/fields/{field_key}/crop")
def get_field_crop(document_id: int, field_key: str, db: Session = Depends(get_db)):
    document = db.get(TitleblockDocument, document_id)
    if not document:
        raise HTTPException(404, "Dokument nicht gefunden")
    result = (
        db.query(DocumentFieldResult)
        .filter_by(document_id=document_id, field_key=field_key)
        .first()
    )
    if not result or not result.candidates_json:
        raise HTTPException(404, "Kein Ausschnitt fuer dieses Feld verfuegbar")
    candidates = json.loads(result.candidates_json)
    if not candidates:
        raise HTTPException(404, "Kein Ausschnitt fuer dieses Feld verfuegbar")

    image = get_field_crop_image(db, document, tuple(candidates[0]["rel_bbox"]))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="image/png")


# ---------- Pruefen: bestaetigen / korrigieren ----------


_STATUS_ACTION_TO_OUTCOME = {
    (FieldStatus.GREEN, "confirm"): MetricOutcome.GREEN_CONFIRMED_CORRECT,
    (FieldStatus.GREEN, "correct"): MetricOutcome.GREEN_CORRECTED,
    (FieldStatus.YELLOW, "confirm"): MetricOutcome.YELLOW_CONFIRMED,
    (FieldStatus.YELLOW, "correct"): MetricOutcome.YELLOW_CORRECTED,
    (FieldStatus.RED, "correct"): MetricOutcome.RED_CORRECTED,
}


@router.post("/{document_id}/fields/{field_key}/review", response_model=schemas.FieldResultOut)
def review_field(
    document_id: int, field_key: str, payload: schemas.FieldReviewRequest, db: Session = Depends(get_db)
):
    document = db.get(TitleblockDocument, document_id)
    if not document:
        raise HTTPException(404, "Dokument nicht gefunden")

    result = (
        db.query(DocumentFieldResult)
        .filter_by(document_id=document_id, field_key=field_key)
        .first()
    )
    if not result:
        raise HTTPException(404, "Feld nicht gefunden")

    candidates = json.loads(result.candidates_json) if result.candidates_json else []

    if payload.action == "confirm":
        idx = payload.candidate_index or 0
        if idx >= len(candidates):
            raise HTTPException(400, "Kein Kandidat mit diesem Index vorhanden")
        chosen = candidates[idx]
        result.human_action = HumanAction.CONFIRMED
        result.corrected_value = None
        rel_bbox = tuple(chosen["rel_bbox"])

        if document.matched_pattern_id:
            pattern = db.get(TitleblockPattern, document.matched_pattern_id)
            memory_mod.confirm_field_memory(db, pattern, field_key, rel_bbox)

    elif payload.action == "correct":
        if not payload.corrected_value:
            raise HTTPException(400, "corrected_value fehlt")
        result.human_action = HumanAction.CORRECTED
        result.corrected_value = payload.corrected_value

        if document.matched_pattern_id and result.chosen_source and result.chosen_source.value == "memory":
            pattern = db.get(TitleblockPattern, document.matched_pattern_id)
            memory_mod.contradict_field_memory(db, pattern, field_key)
    else:
        raise HTTPException(400, "action muss 'confirm' oder 'correct' sein")

    result.reviewed = True
    result.reviewed_at = datetime.utcnow()

    outcome = _STATUS_ACTION_TO_OUTCOME.get((result.status, payload.action))
    if outcome:
        db.add(
            ExtractionMetricEvent(
                document_id=document_id, customer_id=document.customer_id, field_key=field_key,
                pattern_id=document.matched_pattern_id, outcome=outcome,
            )
        )

    db.commit()
    db.refresh(result)

    field_labels = {f.field_key: f.label for f in db.query(ExtractionField).all()}
    return schemas.FieldResultOut(
        id=result.id, field_key=result.field_key, label=field_labels.get(result.field_key, result.field_key),
        status=result.status, chosen_value=result.chosen_value, chosen_source=result.chosen_source,
        assignment_confidence=result.assignment_confidence, ocr_confidence=result.ocr_confidence,
        candidates=[schemas.FieldCandidateOut(**c) for c in candidates],
        reviewed=result.reviewed, human_action=result.human_action,
        corrected_value=result.corrected_value, reviewed_at=result.reviewed_at,
    )


