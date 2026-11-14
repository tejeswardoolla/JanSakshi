import uuid
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey, Index, Boolean
from sqlalchemy.orm import relationship
from app.database import Base
from app.core.config import utc_now

class PhysicalIssue(Base):
    """
    Physical Issue Entity: Represents the real-world infrastructure problem
    (e.g. a specific pothole, broken streetlight segment, or overflowing drain).
    Multiple citizen complaints can be associated with one Physical Issue.
    """
    __tablename__ = "physical_issues"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    issue_reference_id = Column(String(32), unique=True, index=True, nullable=False)
    category = Column(String(64), nullable=False, index=True)
    representative_latitude = Column(Float, nullable=False)
    representative_longitude = Column(Float, nullable=False)
    representative_location = Column(String(255), nullable=True)
    description = Column(Text, nullable=False)
    current_status = Column(String(32), nullable=False, default="Open")  # Open, In_Progress, Resolved, Verified
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    complaints = relationship("Complaint", back_populates="physical_issue")
    duplicate_matches = relationship("DuplicateMatch", back_populates="physical_issue", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_physical_issues_created_at", "created_at"),
        Index("ix_physical_issues_coords", "representative_latitude", "representative_longitude"),
    )

class Complaint(Base):
    """
    Complaint Entity: An individual citizen's report.
    Never deleted, merged, or overwritten when associated with an Issue.
    """
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    complaint_id = Column(String(32), unique=True, index=True, nullable=False)
    tracking_token = Column(String(64), unique=True, index=True, nullable=False, default=lambda: uuid.uuid4().hex)
    issue_id = Column(String(32), ForeignKey("physical_issues.issue_reference_id"), nullable=True, index=True)
    category = Column(String(64), nullable=False, index=True)
    description = Column(Text, nullable=False)
    
    # Location
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    location_accuracy = Column(Float, nullable=True) # in metres
    location_source = Column(String(32), nullable=False, default="gps") # gps, manual, maps_url, plus_code, marker_drag, email_parsed, missing
    google_maps_url = Column(String(512), nullable=True)
    
    # Citizen Info (Optional, Protected)
    citizen_name = Column(String(128), nullable=True)
    citizen_email = Column(String(128), nullable=True)
    citizen_phone = Column(String(32), nullable=True)
    
    # Meta
    submission_channel = Column(String(32), nullable=False, default="website") # website, email
    status = Column(String(32), nullable=False, default="Received")
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Phase 7 Authority Decision & Verification
    verification_status = Column(String(32), nullable=False, default="pending")  # pending, verified, rejected, info_requested
    verified_at = Column(DateTime(timezone=True), nullable=True)
    verified_by_user_id = Column(Integer, nullable=True)
    verified_by_name = Column(String(128), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    info_request_notes = Column(Text, nullable=True)

    # Phase 7 Department Assignment & Workload
    assigned_department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_to_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_at = Column(DateTime(timezone=True), nullable=True)
    assignment_notes = Column(Text, nullable=True)

    # Phase 7 Administrative Progress & Escalation
    admin_status = Column(String(64), nullable=False, default="Received")  # Received, Pending Verification, Verified, Awaiting Department Assignment, Assigned, In Progress, Resolved, Rejected, Escalated
    status_notes = Column(Text, nullable=True)
    escalation_level = Column(Integer, default=0, nullable=False)  # 0 = Normal, 1 = Escalated Tier 1, 2 = Commissioner
    escalation_reason = Column(Text, nullable=True)
    escalated_at = Column(DateTime(timezone=True), nullable=True)
    escalated_to = Column(String(128), nullable=True)
    internal_notes = Column(Text, nullable=True)

    # Relationships
    physical_issue = relationship("PhysicalIssue", back_populates="complaints")
    evidence_files = relationship("Evidence", back_populates="complaint", cascade="all, delete-orphan")
    audit_events = relationship("ComplaintEvent", back_populates="complaint", cascade="all, delete-orphan", order_by="ComplaintEvent.created_at.asc()")
    ai_analyses = relationship("AIAnalysis", back_populates="complaint", cascade="all, delete-orphan", order_by="AIAnalysis.created_at.desc()")
    duplicate_matches = relationship("DuplicateMatch", back_populates="complaint", cascade="all, delete-orphan", order_by="DuplicateMatch.similarity_score.desc()")
    email_messages = relationship("EmailMessage", back_populates="complaint")
    department = relationship("Department", back_populates="complaints", foreign_keys=[assigned_department_id])
    assigned_user = relationship("User", foreign_keys=[assigned_to_user_id])
    resolution_submissions = relationship("ResolutionSubmission", back_populates="complaint", cascade="all, delete-orphan", order_by="ResolutionSubmission.version_number.desc()")

    __table_args__ = (
        Index("ix_complaints_created_at", "created_at"),
        Index("ix_complaints_lat_lng", "latitude", "longitude"),
    )

class Evidence(Base):
    """
    Evidence Entity: Photo/video files submitted by a citizen for a complaint.
    Strictly attached to the original complaint.
    """
    __tablename__ = "evidence"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    complaint_id = Column(String(32), ForeignKey("complaints.complaint_id", ondelete="CASCADE"), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False, unique=True)
    file_type = Column(String(64), nullable=False) # image/jpeg, video/mp4 etc.
    file_size = Column(Integer, nullable=False) # bytes
    storage_path = Column(String(512), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    complaint = relationship("Complaint", back_populates="evidence_files")
    ai_analyses = relationship("AIAnalysis", back_populates="evidence", cascade="all, delete-orphan")

class ComplaintEvent(Base):
    """
    Structured chronological audit and processing history for each complaint.
    """
    __tablename__ = "complaint_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    complaint_id = Column(String(32), ForeignKey("complaints.complaint_id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    previous_value = Column(String(255), nullable=True)
    new_value = Column(String(255), nullable=True)
    description = Column(Text, nullable=False)
    source = Column(String(64), nullable=False, default="system")
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    complaint = relationship("Complaint", back_populates="audit_events")

    __table_args__ = (
        Index("ix_complaint_events_created_at", "created_at"),
    )

class AIAnalysis(Base):
    """
    Phase 4 AI Analysis Record:
    Stores structured multimodal analysis results generated by Gemini for a complaint
    and its uploaded evidence. Preserves historical analyses across multiple runs/retries.
    """
    __tablename__ = "ai_analyses"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    complaint_id = Column(String(32), ForeignKey("complaints.complaint_id", ondelete="CASCADE"), nullable=False, index=True)
    evidence_id = Column(Integer, ForeignKey("evidence.id", ondelete="SET NULL"), nullable=True, index=True)

    # Status: pending, completed, failed, not_configured
    analysis_status = Column(String(32), nullable=False, default="pending", index=True)

    # Classification
    predicted_category = Column(String(64), nullable=True)
    category_confidence = Column(Float, nullable=True)
    complaint_summary = Column(Text, nullable=True)

    # Evidence & Image Analysis
    visible_problem = Column(Text, nullable=True)
    evidence_relevance = Column(String(32), nullable=True)
    relevance_score = Column(Integer, nullable=True)
    image_quality = Column(String(32), nullable=True)
    clarity_score = Column(Integer, nullable=True)
    visibility_score = Column(Integer, nullable=True)
    additional_evidence_required = Column(Boolean, default=False)

    # Severity Assessment
    recommended_severity = Column(String(32), nullable=True)
    severity_confidence = Column(Float, nullable=True)
    reasoning = Column(Text, nullable=True)

    # Human-in-the-loop safeguards
    human_review_required = Column(Boolean, default=True)
    review_reasons = Column(Text, nullable=True)

    # Technical metadata
    model_name = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)
    raw_response = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    complaint = relationship("Complaint", back_populates="ai_analyses")
    evidence = relationship("Evidence", back_populates="ai_analyses")

    __table_args__ = (
        Index("ix_ai_analyses_created_at", "created_at"),
        Index("ix_ai_analyses_status", "analysis_status"),
    )

class DuplicateMatch(Base):
    """
    Phase 5 Duplicate Match Entity:
    Represents a candidate link between a citizen Complaint and an existing PhysicalIssue.
    Stores multi-signal similarity scores, explanations, and human review decision workflow.
    """
    __tablename__ = "duplicate_matches"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    complaint_id = Column(String(32), ForeignKey("complaints.complaint_id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_physical_issue_id = Column(String(32), ForeignKey("physical_issues.issue_reference_id", ondelete="CASCADE"), nullable=False, index=True)

    # Scores (0.0 to 1.0)
    similarity_score = Column(Float, nullable=False, index=True)
    gps_similarity = Column(Float, nullable=True)
    gps_distance_meters = Column(Float, nullable=True)
    text_similarity = Column(Float, nullable=True)
    image_similarity = Column(Float, nullable=True)
    category_similarity = Column(Float, nullable=True)

    # Confidence and recommendation: 'high', 'medium', 'low', 'insufficient_evidence'
    confidence_level = Column(String(32), nullable=False)
    recommendation = Column(String(64), nullable=False)
    matching_explanation = Column(Text, nullable=False)
    warning_signals = Column(Text, nullable=True) # JSON list or notes on potential discrepancies

    # Human review workflow: 'pending', 'approved', 'rejected'
    review_status = Column(String(32), nullable=False, default="pending")
    reviewer_id = Column(String(128), nullable=True)
    review_reason = Column(Text, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    complaint = relationship("Complaint", back_populates="duplicate_matches")
    physical_issue = relationship("PhysicalIssue", back_populates="duplicate_matches")

    __table_args__ = (
        Index("ix_duplicate_matches_created_at", "created_at"),
        Index("ix_duplicate_matches_review_status", "review_status"),
        Index("ix_duplicate_matches_pair", "complaint_id", "candidate_physical_issue_id", unique=True),
    )

class ResolutionSubmission(Base):
    """
    Phase 8: Evidence-Based Resolution Submission Entity
    Represents a formal work order resolution submission by a department officer.
    Maintains version history when work is returned for correction.
    """
    __tablename__ = "resolution_submissions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    complaint_id = Column(String(32), ForeignKey("complaints.complaint_id", ondelete="CASCADE"), nullable=False, index=True)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    submitted_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # Content
    work_completed_description = Column(Text, nullable=False)
    repair_action_taken = Column(Text, nullable=False)
    completion_datetime = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    field_notes = Column(Text, nullable=True)

    # Evidence linkages
    before_evidence_id = Column(Integer, ForeignKey("evidence.id", ondelete="SET NULL"), nullable=True, index=True)
    after_evidence_id = Column(Integer, ForeignKey("evidence.id", ondelete="SET NULL"), nullable=True, index=True)
    additional_evidence_ids = Column(String(255), nullable=True)  # Comma-separated evidence IDs

    # Versioning and workflow status: 'submitted', 'approved', 'returned_for_correction', 'additional_evidence_requested'
    version_number = Column(Integer, default=1, nullable=False)
    status = Column(String(32), nullable=False, default="submitted", index=True)

    # Authority Officer Review Notes
    authority_notes = Column(Text, nullable=True)
    reviewed_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    complaint = relationship("Complaint", back_populates="resolution_submissions")
    department = relationship("Department")
    submitted_by = relationship("User", foreign_keys=[submitted_by_user_id])
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_user_id])
    before_evidence = relationship("Evidence", foreign_keys=[before_evidence_id])
    after_evidence = relationship("Evidence", foreign_keys=[after_evidence_id])
    ai_analysis = relationship("ResolutionEvidenceAnalysis", back_populates="resolution_submission", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_resolution_submissions_created_at", "created_at"),
        Index("ix_resolution_submissions_complaint_ver", "complaint_id", "version_number"),
    )

class ResolutionEvidenceAnalysis(Base):
    """
    Phase 8: AI-Assisted Resolution Evidence Advisory Analysis
    Stores structured multimodal advisory analysis from Gemini comparing
    submitted repair photographs against original complaint claims.
    """
    __tablename__ = "resolution_evidence_analyses"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    resolution_submission_id = Column(Integer, ForeignKey("resolution_submissions.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    model_name = Column(String(64), nullable=True)
    evidence_relevance = Column(String(32), nullable=True)
    description_consistency = Column(String(32), nullable=True)
    before_after_comparison = Column(Text, nullable=True)
    visual_observations = Column(Text, nullable=True)
    missing_evidence = Column(Text, nullable=True)

    # Assessment: 'Evidence Appears Relevant', 'Additional Evidence Recommended', 'Human Inspection Recommended', 'Insufficient Evidence'
    assessment = Column(String(64), nullable=False, default="Human Inspection Recommended")
    analysis_status = Column(String(32), nullable=False, default="completed")  # completed, failed, skipped
    error_message = Column(Text, nullable=True)
    raw_response = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    resolution_submission = relationship("ResolutionSubmission", back_populates="ai_analysis")

    __table_args__ = (
        Index("ix_resolution_ai_created_at", "created_at"),
    )
