"""Laufende Kennzahl bei echten Kundenplanen + Stichprobenkontrolle.

Getrennt vom Pruefstand (der arbeitet mit synthetischen Testplaenen).
Hier zaehlen wir nur Ereignisse (ExtractionMetricEvent) - nie Werte oder
Dokumentinhalte, wie im Datenschutz-Teil gefordert.
"""

import random
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import (
    DocumentFieldResult,
    ExtractionMetricEvent,
    FieldStatus,
    GreenSampleCheck,
    MetricOutcome,
    TitleblockDocument,
)

CORRECT_OUTCOMES = {
    MetricOutcome.GREEN_UNREVIEWED,  # Annahme: korrekt, bis Stichprobe/Korrektur das Gegenteil zeigt
    MetricOutcome.GREEN_CONFIRMED_CORRECT,
    MetricOutcome.YELLOW_CONFIRMED,
}
INCORRECT_OUTCOMES = {
    MetricOutcome.GREEN_CORRECTED,
    MetricOutcome.YELLOW_CORRECTED,
    MetricOutcome.RED_CORRECTED,
    MetricOutcome.RED_UNRESOLVED,
}


def _rate(correct: int, total: int) -> float:
    return round(correct / total, 4) if total else 0.0


def compute_live_metrics(
    db: Session, customer_id: int | None = None, since_days: int | None = None
) -> dict:
    """Prozentsatz der Felder, die ohne menschliche Korrektur richtig erkannt
    wurden - gesamt, je Feld, je Titelblock-Vorlage."""
    query = db.query(ExtractionMetricEvent)
    if customer_id is not None:
        query = query.filter(ExtractionMetricEvent.customer_id == customer_id)
    if since_days is not None:
        cutoff = datetime.utcnow() - timedelta(days=since_days)
        query = query.filter(ExtractionMetricEvent.recorded_at >= cutoff)

    events = query.all()

    def _bucket():
        return {"correct": 0, "total": 0}

    overall = _bucket()
    per_field: dict[str, dict] = {}
    per_pattern: dict[int, dict] = {}

    for e in events:
        is_correct = e.outcome in CORRECT_OUTCOMES
        for store, key in ((per_field, e.field_key), (per_pattern, e.pattern_id)):
            if key is None:
                continue
            bucket = store.setdefault(key, _bucket())
            bucket["total"] += 1
            bucket["correct"] += int(is_correct)
        overall["total"] += 1
        overall["correct"] += int(is_correct)

    return {
        "overall_correct_rate": _rate(overall["correct"], overall["total"]),
        "overall_n": overall["total"],
        "per_field": {k: {"correct_rate": _rate(v["correct"], v["total"]), "n": v["total"]} for k, v in per_field.items()},
        "per_pattern": {k: {"correct_rate": _rate(v["correct"], v["total"]), "n": v["total"]} for k, v in per_pattern.items()},
    }


def compute_weekly_history(db: Session, customer_id: int | None = None, weeks: int = 12) -> list[dict]:
    """Verlauf je Woche, damit sichtbar wird, ob das Gedaechtnis mit jedem
    bestaetigten Plan besser wird."""
    query = db.query(ExtractionMetricEvent)
    if customer_id is not None:
        query = query.filter(ExtractionMetricEvent.customer_id == customer_id)
    events = query.all()

    buckets: dict[str, dict] = {}
    for e in events:
        year, week, _ = e.recorded_at.isocalendar()
        key = f"{year}-W{week:02d}"
        bucket = buckets.setdefault(key, {"correct": 0, "total": 0})
        bucket["total"] += 1
        bucket["correct"] += int(e.outcome in CORRECT_OUTCOMES)

    weeks_sorted = sorted(buckets.keys())[-weeks:]
    return [
        {"week": k, "correct_rate": _rate(buckets[k]["correct"], buckets[k]["total"]), "n": buckets[k]["total"]}
        for k in weeks_sorted
    ]


SAMPLE_RATE_DEFAULT = 0.05


def maybe_sample_green_field(db: Session, document_id: int, field_key: str, sample_rate: float = SAMPLE_RATE_DEFAULT) -> bool:
    """Zieht mit der eingestellten Wahrscheinlichkeit ein gruenes Feld fuer
    eine kurze menschliche Gegenpruefung. Gibt zurueck, ob es gezogen wurde."""
    if random.random() > sample_rate:
        return False
    db.add(GreenSampleCheck(document_id=document_id, field_key=field_key))
    db.commit()
    return True


def pending_sample_checks(db: Session, customer_id: int | None = None) -> list[GreenSampleCheck]:
    query = (
        db.query(GreenSampleCheck)
        .join(TitleblockDocument, GreenSampleCheck.document_id == TitleblockDocument.id)
        .filter(GreenSampleCheck.reviewed_at.is_(None))
    )
    if customer_id is not None:
        query = query.filter(TitleblockDocument.customer_id == customer_id)
    return query.all()


def resolve_sample_check(db: Session, check_id: int, verdict: str) -> GreenSampleCheck | None:
    """verdict: 'correct' | 'incorrect'. Fliesst in die geschaetzte
    unbemerkte Fehlerquote ein, die zusaetzlich zur Kennzahl angezeigt wird."""
    check = db.get(GreenSampleCheck, check_id)
    if check is None:
        return None
    check.human_verdict = verdict
    check.reviewed_at = datetime.utcnow()
    db.commit()
    return check


def estimated_undetected_error_rate(db: Session, customer_id: int | None = None) -> dict:
    query = (
        db.query(GreenSampleCheck)
        .join(TitleblockDocument, GreenSampleCheck.document_id == TitleblockDocument.id)
        .filter(GreenSampleCheck.human_verdict.isnot(None))
    )
    if customer_id is not None:
        query = query.filter(TitleblockDocument.customer_id == customer_id)
    checks = query.all()
    if not checks:
        return {"rate": None, "n": 0}
    incorrect = sum(1 for c in checks if c.human_verdict == "incorrect")
    return {"rate": _rate(incorrect, len(checks)), "n": len(checks)}
