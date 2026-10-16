"""Gedaechtnis pro Kunde: Struktur-Fingerabdruck + gelernte Feld-Positionen.

Speichert bewusst NUR Struktur (Rasterlinien-Muster, relative Lage
bestaetigter Felder) - nie Inhalte. Gehoert dem Kunden, liegt lokal in
derselben SQLite-Datei, ist im Tool einsehbar und loeschbar.

Koordinaten-Konvention: alle rel_x/rel_y/rel_w/rel_h hier sind relativ zum
erkannten TITELBLOCK-AUSSCHNITT (nicht zur gesamten Seite) - also 0..1
bezogen auf das Bild, das Stufe B auch fuer die OCR-Lesung verwendet hat.
"""

import hashlib

import cv2
import numpy as np
from PIL import Image
from sqlalchemy.orm import Session

from .field_extraction import FieldCandidate
from .models import TitleblockFieldMemory, TitleblockPattern
from .region_detection import GRID_CELLS, _line_density_grid

FINGERPRINT_GRID = 8  # grob genug, um kleine OCR-Jitter zu tolerieren
POSITION_BUCKET = 0.05  # 5%-Raster fuer Feld-Positionen im Fingerabdruck

MIN_USABLE_MEMORY_CONFIDENCE = 0.3
CONFIDENCE_STEP_UP = 0.15
CONFIDENCE_STEP_DOWN = 0.25
POSITION_SMOOTHING = 0.3  # Anteil, mit dem eine neue Bestaetigung die Position nachzieht


def compute_fingerprint(region_image: Image.Image, label_positions: dict[str, tuple[float, float]]) -> str:
    """Baut einen reinen Struktur-Fingerabdruck: grobes Rasterlinien-Muster
    plus die Anordnung der WAEHREND DER ERKENNUNG gefundenen Beschriftungen
    (nur Feldname + grobe Position, kein Text/Inhalt)."""
    gray = cv2.cvtColor(np.array(region_image.convert("RGB")), cv2.COLOR_RGB2GRAY)
    density = _line_density_grid(gray)

    # Auf FINGERPRINT_GRID herunterbrechen und binarisieren
    factor = GRID_CELLS // FINGERPRINT_GRID
    coarse = density.reshape(FINGERPRINT_GRID, factor, FINGERPRINT_GRID, factor).sum(axis=(1, 3))
    grid_bits = "".join("1" if v > coarse.mean() else "0" for v in coarse.flatten())

    label_sig = ",".join(
        f"{key}:{round(pos[0] / POSITION_BUCKET) * POSITION_BUCKET:.2f}:"
        f"{round(pos[1] / POSITION_BUCKET) * POSITION_BUCKET:.2f}"
        for key, pos in sorted(label_positions.items())
    )

    source = f"{grid_bits}|{label_sig}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def find_or_create_pattern(db: Session, customer_id: int, fingerprint_hash: str) -> tuple[TitleblockPattern, bool]:
    """Liefert (Muster, ist_neu_angelegt). Legt bei neuem Fingerabdruck ein
    frisches, noch unbestaetigtes Muster an."""
    pattern = (
        db.query(TitleblockPattern)
        .filter_by(customer_id=customer_id, fingerprint_hash=fingerprint_hash)
        .first()
    )
    if pattern:
        return pattern, False

    pattern = TitleblockPattern(customer_id=customer_id, fingerprint_hash=fingerprint_hash)
    db.add(pattern)
    db.commit()
    db.refresh(pattern)
    return pattern, True


def memory_candidates_for_field(
    db: Session, pattern: TitleblockPattern, field_key: str, region_image: Image.Image
) -> FieldCandidate | None:
    """Falls fuer dieses Muster bereits eine brauchbare Erinnerung an die
    Position dieses Feldes existiert: an der gemerkten Stelle NEU lesen
    (nie den alten Wert wiederverwenden) und als Kandidat zurueckgeben."""
    import pytesseract

    memory = (
        db.query(TitleblockFieldMemory)
        .filter_by(pattern_id=pattern.id, field_key=field_key)
        .first()
    )
    if memory is None or memory.confidence < MIN_USABLE_MEMORY_CONFIDENCE:
        return None

    w, h = region_image.size
    box = (
        max(0, int((memory.rel_x - 0.01) * w)),
        max(0, int((memory.rel_y - 0.01) * h)),
        min(w, int((memory.rel_x + memory.rel_w + 0.01) * w)),
        min(h, int((memory.rel_y + memory.rel_h + 0.01) * h)),
    )
    if box[2] <= box[0] or box[3] <= box[1]:
        return None

    crop = region_image.crop(box)
    text = pytesseract.image_to_string(crop, lang="deu+eng").strip()
    if not text:
        return None

    data = pytesseract.image_to_data(crop, lang="deu+eng", output_type=pytesseract.Output.DICT)
    confs = [float(c) for c in data["conf"] if float(c) >= 0]
    ocr_conf = sum(confs) / len(confs) if confs else 0.0
    min_conf = min(confs) if confs else 0.0

    return FieldCandidate(
        value=text,
        assignment_confidence=memory.confidence,
        ocr_confidence=ocr_conf,
        match_type="memory",
        label_score=100.0,
        rel_bbox=(memory.rel_x, memory.rel_y, memory.rel_w, memory.rel_h),
        min_word_confidence=min_conf,
    )


def confirm_field_memory(
    db: Session, pattern: TitleblockPattern, field_key: str, rel_bbox: tuple[float, float, float, float]
) -> None:
    """Ein Mensch hat die Zuordnung bestaetigt (oder korrigiert und dabei
    eine neue Position gezeigt) - Erinnerung staerken bzw. neu anlegen."""
    memory = (
        db.query(TitleblockFieldMemory)
        .filter_by(pattern_id=pattern.id, field_key=field_key)
        .first()
    )
    if memory is None:
        memory = TitleblockFieldMemory(
            pattern_id=pattern.id,
            field_key=field_key,
            rel_x=rel_bbox[0], rel_y=rel_bbox[1], rel_w=rel_bbox[2], rel_h=rel_bbox[3],
            confidence=0.5,
            confirmation_count=0,
            contradiction_count=0,
        )
        db.add(memory)
    else:
        memory.rel_x = memory.rel_x * (1 - POSITION_SMOOTHING) + rel_bbox[0] * POSITION_SMOOTHING
        memory.rel_y = memory.rel_y * (1 - POSITION_SMOOTHING) + rel_bbox[1] * POSITION_SMOOTHING
        memory.rel_w = memory.rel_w * (1 - POSITION_SMOOTHING) + rel_bbox[2] * POSITION_SMOOTHING
        memory.rel_h = memory.rel_h * (1 - POSITION_SMOOTHING) + rel_bbox[3] * POSITION_SMOOTHING
        memory.confidence = min(1.0, memory.confidence + CONFIDENCE_STEP_UP)

    memory.confirmation_count += 1
    from datetime import datetime
    memory.last_confirmed_at = datetime.utcnow()

    pattern.confirmation_count += 1
    pattern.last_used_at = datetime.utcnow()
    db.commit()


def contradict_field_memory(db: Session, pattern: TitleblockPattern, field_key: str) -> None:
    """Ein Mensch hat eine aus dem Gedaechtnis stammende Zuordnung
    korrigiert - Erinnerung schwaechen, Position aber nicht blind aendern,
    da wir ohne neuen Fundort nicht wissen, wohin sie verschieben sollte."""
    memory = (
        db.query(TitleblockFieldMemory)
        .filter_by(pattern_id=pattern.id, field_key=field_key)
        .first()
    )
    if memory is not None:
        memory.contradiction_count += 1
        memory.confidence = max(0.0, memory.confidence - CONFIDENCE_STEP_DOWN)

    pattern.contradiction_count += 1
    db.commit()
