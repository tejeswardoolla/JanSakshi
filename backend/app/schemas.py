import re
import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_serializer

def serialize_to_utc_iso(dt: Optional[datetime.datetime]) -> Optional[str]:
    """
    Ensure any datetime returned by the API is explicitly timezone-aware in UTC
    with an ISO 8601 'Z' suffix, eliminating timezone ambiguity.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    else:
        dt = dt.astimezone(datetime.timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")

class LocationResolveRequest(BaseModel):
    query: str = Field(..., description="Google Maps URL, coordinates 'lat,lng', or Plus Code")

class LocationResolveResponse(BaseModel):
    success: bool
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    source: str
    google_maps_url: Optional[str] = None
    message: Optional[str] = None

class EvidenceResponse(BaseModel):
    id: int
    original_filename: str
    file_type: str
    file_size: int
    created_at: datetime.datetime

    @field_serializer("created_at")
    def serialize_created_at(self, dt: datetime.datetime, _info):
        return serialize_to_utc_iso(dt)

    class Config:
        from_attributes = True

class ComplaintEventResponse(BaseModel):
    id: int
    complaint_id: str
    event_type: str
    previous_value: Optional[str] = None
    new_value: Optional[str] = None
    description: str
    source: str
    created_at: datetime.datetime

    @field_serializer("created_at")
    def serialize_created_at(self, dt: datetime.datetime, _info):
        return serialize_to_utc_iso(dt)

    class Config:
        from_attributes = True

class ComplaintCreateResponse(BaseModel):
    complaint_id: str
    tracking_token: str
    status: str
    category: str
    created_at: datetime.datetime
    google_maps_url: str
    message: str

    @field_serializer("created_at")
    def serialize_created_at(self, dt: datetime.datetime, _info):
        return serialize_to_utc_iso(dt)

# --- AI Analysis Schemas (Phase 4) ---

class AIStatusResponse(BaseModel):
    configured: bool
    enabled: bool
    model: str
    confidence_threshold: float
    status: str # operational, unconfigured, disabled
    message: str

class AIAnalysisResponse(BaseModel):
    id: int
    complaint_id: str
    evidence_id: Optional[int] = None
    analysis_status: str
    predicted_category: Optional[str] = None
    category_confidence: Optional[float] = None
    complaint_summary: Optional[str] = None
    visible_problem: Optional[str] = None
    evidence_relevance: Optional[str] = None
    relevance_score: Optional[int] = None
    image_quality: Optional[str] = None
    clarity_score: Optional[int] = None
    visibility_score: Optional[int] = None
    additional_evidence_required: bool = False
    recommended_severity: Optional[str] = None
    severity_confidence: Optional[float] = None
    reasoning: Optional[str] = None
    human_review_required: bool = True
    review_reasons: Optional[str] = None
    model_name: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    @field_serializer("created_at", "updated_at")
    def serialize_dates(self, dt: datetime.datetime, _info):
        return serialize_to_utc_iso(dt)

    class Config:
        from_attributes = True

# --- Physical Issue Schemas ---

class PhysicalIssueCreateRequest(BaseModel):
    category: str = Field(..., min_length=3, max_length=64)
    representative_latitude: float
    representative_longitude: float
    description: str = Field(..., min_length=10, max_length=2000)
    representative_location: Optional[str] = None

class PhysicalIssueResponse(BaseModel):
    id: int
    issue_reference_id: str
    category: str
    representative_latitude: float
    representative_longitude: float
    representative_location: Optional[str] = None
    description: str
    current_status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    complaint_count: int = 0

    @field_serializer("created_at", "updated_at")
    def serialize_dates(self, dt: datetime.datetime, _info):
        return serialize_to_utc_iso(dt)

    class Config:
        from_attributes = True

# --- Phase 5 Duplicate Detection Schemas ---

class DuplicateMatchResponse(BaseModel):
    id: int
    complaint_id: str
    candidate_physical_issue_id: str
    similarity_score: float
    gps_similarity: Optional[float] = None
    gps_distance_meters: Optional[float] = None
    text_similarity: Optional[float] = None
    image_similarity: Optional[float] = None
    category_similarity: Optional[float] = None
    confidence_level: str
    recommendation: str
    matching_explanation: str
    warning_signals: Optional[str] = None
    review_status: str
    reviewer_id: Optional[str] = None
    review_reason: Optional[str] = None
    reviewed_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    candidate_issue: Optional[PhysicalIssueResponse] = None

    @field_serializer("created_at", "updated_at", "reviewed_at")
    def serialize_dates(self, dt: Optional[datetime.datetime], _info):
        return serialize_to_utc_iso(dt)

    class Config:
        from_attributes = True

class ComplaintTrackResponse(BaseModel):
    complaint_id: str
    issue_id: Optional[str] = None
    category: str
    description: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_accuracy: Optional[float] = None
    location_source: str
    google_maps_url: Optional[str] = None
    status: str
    submission_channel: str
    created_at: datetime.datetime
    evidence_count: int
    evidence: List[EvidenceResponse]
    latest_ai_analysis: Optional[AIAnalysisResponse] = None
    associated_issue: Optional[PhysicalIssueResponse] = None
    duplicate_matches: List[DuplicateMatchResponse] = []

    @field_serializer("created_at")
    def serialize_created_at(self, dt: datetime.datetime, _info):
        return serialize_to_utc_iso(dt)

    class Config:
        from_attributes = True

# --- Phase 6 Gmail AI Integration Schemas ---

class EmailMessageResponse(BaseModel):
    id: int
    gmail_message_id: str
    gmail_thread_id: Optional[str] = None
    sender_email: str
    sender_name: Optional[str] = None
    subject: Optional[str] = None
    snippet: Optional[str] = None
    body_plain: Optional[str] = None
    received_at: datetime.datetime
    processing_status: str
    complaint_id: Optional[str] = None
    is_civic_complaint: Optional[bool] = None
    extracted_category: Optional[str] = None
    extracted_location_text: Optional[str] = None
    extracted_metadata: Optional[str] = None
    error_details: Optional[str] = None
    has_attachments: Optional[bool] = False
    attachments_count: Optional[int] = 0
    attachments_info: Optional[str] = None
    acknowledgement_sent: Optional[bool] = False
    acknowledgement_sent_at: Optional[datetime.datetime] = None
    is_follow_up: Optional[bool] = False
    created_at: datetime.datetime

    @field_serializer("received_at", "created_at", "acknowledgement_sent_at")
    def serialize_dates(self, dt: Optional[datetime.datetime], _info):
        return serialize_to_utc_iso(dt)

    class Config:
        from_attributes = True

class EmailStatusResponse(BaseModel):
    enabled: bool
    configured: bool
    authenticated: bool
    official_inbox_address: str
    connected_email: Optional[str] = None
    email_address: Optional[str] = None
    mailbox_match: bool = True
    account_mismatch_warning: Optional[str] = None
    status: str
    message: str
    total_messages_received: int = 0
    total_processed: int = 0
    total_awaiting_info: int = 0
    total_needs_review: int = 0
    total_ignored: int = 0
    total_failed: int = 0
    last_sync_at: Optional[str] = None

class DuplicateReviewQueueItem(BaseModel):
    match: DuplicateMatchResponse
    complaint_category: str
    complaint_description: str
    complaint_latitude: float
    complaint_longitude: float
    complaint_created_at: datetime.datetime
    evidence_count: int

    @field_serializer("complaint_created_at")
    def serialize_created_at(self, dt: datetime.datetime, _info):
        return serialize_to_utc_iso(dt)

class DuplicateReviewActionRequest(BaseModel):
    reviewer_id: Optional[str] = Field("authority_reviewer", description="Identifier of the reviewer or authority")
    review_reason: Optional[str] = Field(None, description="Reason for approving or rejecting association")

class DuplicateReviewActionResponse(BaseModel):
    status: str
    message: str
    match_id: int
    complaint_id: str
    review_status: str
    issue_reference_id: Optional[str] = None

class AssociateIssueRequest(BaseModel):
    issue_reference_id: Optional[str] = Field(None, description="Issue reference ID to associate with, or null to disassociate")
    source: str = Field("admin", description="Source or authority making the association")

class AssociateIssueResponse(BaseModel):
    complaint_id: str
    issue_id: Optional[str] = None
    message: str
    updated_at: datetime.datetime

    @field_serializer("updated_at")
    def serialize_updated_at(self, dt: datetime.datetime, _info):
        return serialize_to_utc_iso(dt)
