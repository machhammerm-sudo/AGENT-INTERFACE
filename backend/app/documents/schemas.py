from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from .models import DocumentStatus, FieldResultSource, FieldStatus, HumanAction


class CustomerCreate(BaseModel):
    name: str


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    created_at: datetime


class ExtractionFieldOut(BaseModel):
    id: int
    field_key: str
    label: str
    synonyms: list[str]
    format_regex: Optional[str] = None
    is_user_edited: bool


class ExtractionFieldUpdate(BaseModel):
    label: Optional[str] = None
    synonyms: Optional[list[str]] = None
    format_regex: Optional[str] = None


class PrivacySettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    customer_id: int
    contribute_anonymized_structure_data: bool
    consent_given_at: Optional[datetime] = None
    consent_withdrawn_at: Optional[datetime] = None
    allow_cloud_escalation: bool
    escalation_consent_at: Optional[datetime] = None


class PrivacySettingsUpdate(BaseModel):
    contribute_anonymized_structure_data: Optional[bool] = None
    allow_cloud_escalation: Optional[bool] = None


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    customer_id: Optional[int] = None
    filename: str
    status: DocumentStatus
    matched_pattern_id: Optional[int] = None
    error_message: Optional[str] = None
    uploaded_at: datetime
    processed_at: Optional[datetime] = None


class RegionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    rel_x: float
    rel_y: float
    rel_w: float
    rel_h: float
    rotation: int
    score: float
    method: str
    is_chosen: bool


class FieldCandidateOut(BaseModel):
    value: str
    assignment_confidence: float
    ocr_confidence: float
    match_type: str
    label_score: float
    rel_bbox: list[float]


class FieldResultOut(BaseModel):
    id: int
    field_key: str
    label: str
    status: FieldStatus
    chosen_value: Optional[str] = None
    chosen_source: Optional[FieldResultSource] = None
    assignment_confidence: Optional[float] = None
    ocr_confidence: Optional[float] = None
    candidates: list[FieldCandidateOut]
    reviewed: bool
    human_action: Optional[HumanAction] = None
    corrected_value: Optional[str] = None
    reviewed_at: Optional[datetime] = None


class DocumentDetailOut(BaseModel):
    document: DocumentOut
    regions: list[RegionOut]
    fields: list[FieldResultOut]


class LiveMetricsOut(BaseModel):
    overall_correct_rate: float
    overall_n: int
    per_field: dict
    per_pattern: dict
    estimated_undetected_error_rate: Optional[float] = None
    estimated_undetected_n: int = 0


class WeeklyHistoryPoint(BaseModel):
    week: str
    correct_rate: float
    n: int


class SampleCheckOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    document_id: int
    field_key: str
    sampled_at: datetime
    human_verdict: Optional[str] = None
    reviewed_at: Optional[datetime] = None


class SampleCheckResolve(BaseModel):
    verdict: str  # "correct" | "incorrect"


class BenchmarkRunOut(BaseModel):
    id: int
    run_at: datetime
    overall_hit_rate: float
    false_green_rate: float
    no_result_rate: float
    plan_count: int
    per_field: dict
    per_template: dict


class FieldReviewRequest(BaseModel):
    action: str  # "confirm" | "correct"
    candidate_index: Optional[int] = None  # bei "confirm": welcher Kandidat war richtig (Default 0)
    corrected_value: Optional[str] = None  # bei "correct": der tatsaechliche Wert
