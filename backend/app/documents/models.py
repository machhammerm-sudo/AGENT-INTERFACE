"""P13 - Dokument-Auslese: Datenbank-Modelle.

Alles hier liegt lokal in derselben SQLite-Datei wie der Rest von Nauteron.
Wichtige Trennung fuer den Datenschutz:
- TitleblockPattern / TitleblockFieldMemory speichern NUR Struktur
  (Linienraster-Lage, relative Feld-Positionen) - keine Dokumentinhalte.
- DocumentFieldResult speichert die tatsaechlichen erkannten Werte, aber rein
  lokal pro Dokument - das ist normale Verarbeitung, keine Weitergabe.
- ExtractionMetricEvent speichert NUR Zaehlwerte/Zeitpunkte fuer die laufende
  Kennzahl, nie Werte oder Inhalte.
"""

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from ..database import Base


class Customer(Base):
    """Ein Kunde des Nutzers (z.B. ein Planungsbuero-Mandant). Das
    Titelblock-Gedaechtnis gehoert jeweils einem Kunden."""

    __tablename__ = "doc_customers"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class FieldStatus(str, enum.Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class FieldResultSource(str, enum.Enum):
    MEMORY = "memory"
    OCR = "ocr"
    MANUAL = "manual"
    ESCALATION = "escalation"


class HumanAction(str, enum.Enum):
    CONFIRMED = "confirmed"
    CORRECTED = "corrected"


class ExtractionField(Base):
    """Ein Feld im Extraktionsschema (z.B. 'Bauherr') mit editierbaren
    Beschriftungs-Synonymen fuer den unscharfen Vergleich."""

    __tablename__ = "doc_extraction_fields"

    id = Column(Integer, primary_key=True)
    field_key = Column(String, unique=True, nullable=False)
    label = Column(String, nullable=False)
    synonyms = Column(Text, nullable=False)  # JSON-Liste von Strings
    format_regex = Column(String, nullable=True)  # optional, fuer formatbasierte Kandidaten
    sort_order = Column(Integer, default=0, nullable=False)
    is_user_edited = Column(Boolean, default=False, nullable=False)


class DocumentStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"  # automatische Auslese fertig, wartet auf Pruefung
    REVIEWED = "reviewed"  # alle Felder von einem Menschen bestaetigt/korrigiert
    ERROR = "error"


class TitleblockDocument(Base):
    """Ein hochgeladener Plan (PDF oder Bild)."""

    __tablename__ = "doc_titleblock_documents"

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("doc_customers.id"), nullable=True)
    filename = Column(String, nullable=False)
    stored_path = Column(String, nullable=False)
    status = Column(Enum(DocumentStatus), default=DocumentStatus.UPLOADED, nullable=False)
    matched_pattern_id = Column(Integer, ForeignKey("doc_titleblock_patterns.id"), nullable=True)
    error_message = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)

    customer = relationship("Customer")
    regions = relationship(
        "DocumentRegion", back_populates="document", cascade="all, delete-orphan"
    )
    field_results = relationship(
        "DocumentFieldResult", back_populates="document", cascade="all, delete-orphan"
    )


class DocumentRegion(Base):
    """Stufe A: ein Kandidatenbereich fuer den Titelblock auf der Seite."""

    __tablename__ = "doc_document_regions"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("doc_titleblock_documents.id"), nullable=False)
    page_index = Column(Integer, default=0, nullable=False)
    rel_x = Column(Float, nullable=False)
    rel_y = Column(Float, nullable=False)
    rel_w = Column(Float, nullable=False)
    rel_h = Column(Float, nullable=False)
    rotation = Column(Integer, default=0, nullable=False)  # 0/90/180/270
    score = Column(Float, nullable=False)
    method = Column(String, nullable=False)  # "grid" | "label_density" | "fallback_full_page"
    is_chosen = Column(Boolean, default=False, nullable=False)

    document = relationship("TitleblockDocument", back_populates="regions")


class DocumentFieldResult(Base):
    """Stufe B: das Ergebnis fuer ein Feld eines Dokuments, inkl. Kandidaten
    und Pruefprotokoll-Angaben. Lokal pro Dokument - enthaelt die
    tatsaechlichen erkannten Werte (normale, lokale Verarbeitung)."""

    __tablename__ = "doc_field_results"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("doc_titleblock_documents.id"), nullable=False)
    field_key = Column(String, nullable=False)
    status = Column(Enum(FieldStatus), nullable=False)
    chosen_value = Column(Text, nullable=True)
    chosen_source = Column(Enum(FieldResultSource), nullable=True)
    assignment_confidence = Column(Float, nullable=True)  # Zuordnungs-Sicherheit
    ocr_confidence = Column(Float, nullable=True)  # OCR-Lesesicherheit (getrennt!)
    candidates_json = Column(Text, nullable=True)  # bis zu 3 Kandidaten mit Scores
    reviewed = Column(Boolean, default=False, nullable=False)
    human_action = Column(Enum(HumanAction), nullable=True)
    corrected_value = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    document = relationship("TitleblockDocument", back_populates="field_results")


class TitleblockPattern(Base):
    """Gedaechtnis pro Kunde: ein Struktur-Fingerabdruck (Linienraster,
    Rahmenaufteilung, Anordnung der Beschriftungen) - KEINE Inhalte."""

    __tablename__ = "doc_titleblock_patterns"

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("doc_customers.id"), nullable=False)
    fingerprint_hash = Column(String, nullable=False)
    confirmation_count = Column(Integer, default=0, nullable=False)
    contradiction_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    customer = relationship("Customer")
    field_memories = relationship(
        "TitleblockFieldMemory", back_populates="pattern", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("customer_id", "fingerprint_hash", name="uq_customer_fingerprint"),
    )


class TitleblockFieldMemory(Base):
    """Wo ein Feld innerhalb eines bekannten Musters typischerweise sitzt -
    relative Lage, damit es aufloesungsunabhaengig bleibt. Keine Inhalte."""

    __tablename__ = "doc_titleblock_field_memory"

    id = Column(Integer, primary_key=True)
    pattern_id = Column(Integer, ForeignKey("doc_titleblock_patterns.id"), nullable=False)
    field_key = Column(String, nullable=False)
    rel_x = Column(Float, nullable=False)
    rel_y = Column(Float, nullable=False)
    rel_w = Column(Float, nullable=False)
    rel_h = Column(Float, nullable=False)
    confidence = Column(Float, default=0.5, nullable=False)
    confirmation_count = Column(Integer, default=0, nullable=False)
    contradiction_count = Column(Integer, default=0, nullable=False)
    last_confirmed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    pattern = relationship("TitleblockPattern", back_populates="field_memories")

    __table_args__ = (
        UniqueConstraint("pattern_id", "field_key", name="uq_pattern_field"),
    )


class CustomerPrivacySettings(Base):
    """Zwei getrennte Zustimmungen pro Kunde/Objekt:
    - contribute_anonymized_structure_data: Strukturdaten (Fingerabdruck,
      Feldpositionen, Bereichsgeometrie - keine Texte/Namen/Bilder) zur
      Systemverbesserung beitragen. Standard AUS. Wird aktuell nirgends
      ausgelesen oder exportiert - nur vorbereitet.
    - allow_cloud_escalation: darf ein einzelner unklarer Bildausschnitt
      bei Bedarf an die Claude-Bildauswertung (P16) geschickt werden.
      Ebenfalls Standard AUS."""

    __tablename__ = "doc_customer_privacy_settings"

    customer_id = Column(Integer, ForeignKey("doc_customers.id"), primary_key=True)
    contribute_anonymized_structure_data = Column(Boolean, default=False, nullable=False)
    consent_given_at = Column(DateTime, nullable=True)
    consent_withdrawn_at = Column(DateTime, nullable=True)
    allow_cloud_escalation = Column(Boolean, default=False, nullable=False)
    escalation_consent_at = Column(DateTime, nullable=True)

    customer = relationship("Customer")


class MetricOutcome(str, enum.Enum):
    GREEN_UNREVIEWED = "green_unreviewed"
    GREEN_CONFIRMED_CORRECT = "green_confirmed_correct"
    GREEN_CORRECTED = "green_corrected"  # gruen markiert, aber von Mensch als falsch erkannt
    YELLOW_CONFIRMED = "yellow_confirmed"
    YELLOW_CORRECTED = "yellow_corrected"
    RED_CORRECTED = "red_corrected"
    RED_UNRESOLVED = "red_unresolved"


class ExtractionMetricEvent(Base):
    """Laufende Kennzahl bei echten Kundenplanen. Speichert bewusst NUR
    Zaehlwerte/Zeitpunkte - keine Werte, keine Dokumentinhalte."""

    __tablename__ = "doc_extraction_metric_events"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("doc_titleblock_documents.id"), nullable=False)
    customer_id = Column(Integer, ForeignKey("doc_customers.id"), nullable=True)
    field_key = Column(String, nullable=False)
    pattern_id = Column(Integer, ForeignKey("doc_titleblock_patterns.id"), nullable=True)
    outcome = Column(Enum(MetricOutcome), nullable=False)
    recorded_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class GreenSampleCheck(Base):
    """Stichprobenkontrolle: ein zufaellig gezogenes gruenes Feld, das einem
    Menschen zur kurzen Gegenpruefung vorgelegt wird, um die unbemerkte
    Fehlerquote zu schaetzen."""

    __tablename__ = "doc_green_sample_checks"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("doc_titleblock_documents.id"), nullable=False)
    field_key = Column(String, nullable=False)
    sampled_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    human_verdict = Column(String, nullable=True)  # "correct" | "incorrect"
    reviewed_at = Column(DateTime, nullable=True)


class BenchmarkRun(Base):
    """Ein Lauf des Pruefstands (synthetische Testplaene)."""

    __tablename__ = "doc_benchmark_runs"

    id = Column(Integer, primary_key=True)
    run_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    overall_hit_rate = Column(Float, nullable=False)
    false_green_rate = Column(Float, nullable=False)
    no_result_rate = Column(Float, nullable=False)
    per_field_json = Column(Text, nullable=False)
    per_template_json = Column(Text, nullable=False)
    plan_count = Column(Integer, nullable=False)
