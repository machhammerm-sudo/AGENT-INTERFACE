"""Vorbefuellung des Extraktionsschemas fuer Titelbloecke von Einreichplaenen.
Wie bei den Kategorien: nur beim ersten Start, bestehende Eintraege werden
nie ueberschrieben, und alles ist im Tool editierbar."""

import json

from sqlalchemy.orm import Session

from .models import ExtractionField

DEFAULT_FIELDS = [
    dict(
        field_key="bauherr",
        label="Bauherr",
        synonyms=["Bauherr", "Bauherrschaft", "Auftraggeber", "Bauherrin"],
        format_regex=None,
    ),
    dict(
        field_key="planverfasser",
        label="Planverfasser",
        synonyms=["Planverfasser", "Architekt", "Verfasser", "Entwurfsverfasser"],
        format_regex=None,
    ),
    dict(
        field_key="bauvorhaben",
        label="Bauvorhaben",
        synonyms=["Bauvorhaben", "Projekt", "Vorhaben", "Bauobjekt"],
        format_regex=None,
    ),
    dict(
        field_key="grundstuecksadresse",
        label="Grundstücksadresse",
        synonyms=["Adresse", "Grundstücksadresse", "Baugrundstück", "Lage"],
        format_regex=None,
    ),
    dict(
        field_key="gemeinde",
        label="Gemeinde / Ort",
        synonyms=["Gemeinde", "Ort", "Standort", "Stadt"],
        format_regex=None,
    ),
    dict(
        field_key="flurstueck",
        label="Flurstück / Grundstücksnummer",
        synonyms=["Flurstück", "Flurstücksnummer", "Grundstücksnummer", "Flur", "Parzelle"],
        format_regex=r"\b\d{1,5}(/\d{1,4})?\b",
    ),
    dict(
        field_key="massstab",
        label="Maßstab",
        synonyms=["Maßstab", "Massstab", "M.", "Scale"],
        format_regex=r"\b1\s*:\s*\d{1,4}\b",
    ),
    dict(
        field_key="plannummer",
        label="Plannummer",
        synonyms=["Plan-Nr.", "Plannummer", "Zeichnungsnummer", "Plan Nr", "Nr."],
        format_regex=r"\b[A-Za-z0-9][A-Za-z0-9.\-/]{2,}\b",
    ),
    dict(
        field_key="planinhalt",
        label="Planinhalt",
        synonyms=["Planinhalt", "Zeichnungsinhalt", "Darstellung", "Inhalt"],
        format_regex=None,
    ),
    dict(
        field_key="datum",
        label="Datum",
        synonyms=["Datum", "Stand", "Ausfertigungsdatum", "Planungsstand"],
        format_regex=r"\b\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}\b",
    ),
    dict(
        field_key="index",
        label="Index / Revision",
        synonyms=["Index", "Revision", "Änderungsindex", "Rev."],
        format_regex=r"\b[A-Z]{1,2}\d{0,2}\b",
    ),
    dict(
        field_key="flaeche",
        label="Fläche",
        synonyms=["Fläche", "Grundstücksfläche", "Nutzfläche", "Wohnfläche"],
        format_regex=r"\b\d{1,6}([.,]\d{1,2})?\s*m[²2]\b",
    ),
]


def seed_defaults(db: Session) -> None:
    if db.query(ExtractionField).count() == 0:
        for i, data in enumerate(DEFAULT_FIELDS):
            db.add(
                ExtractionField(
                    field_key=data["field_key"],
                    label=data["label"],
                    synonyms=json.dumps(data["synonyms"], ensure_ascii=False),
                    format_regex=data["format_regex"],
                    sort_order=i,
                )
            )
        db.commit()
