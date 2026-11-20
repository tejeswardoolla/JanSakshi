from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index, Boolean
from sqlalchemy.orm import relationship
from app.database import Base
from app.core.config import utc_now

class EmailMessage(Base):
    """
    Phase 6 Email Tracking Entity:
    Tracks incoming emails from Gmail to guarantee strict idempotency (no duplicate complaints).
    Stores parsing results, Gemini extraction metadata, processing status, and acknowledgement logs.
    """
    __tablename__ = "email_messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    gmail_message_id = Column(String(128), unique=True, index=True, nullable=False)
    gmail_thread_id = Column(String(128), index=True, nullable=True)

    sender_email = Column(String(255), nullable=False, index=True)
    sender_name = Column(String(255), nullable=True)
    subject = Column(String(512), nullable=True)
    snippet = Column(Text, nullable=True)
    body_plain = Column(Text, nullable=True)
    body_html = Column(Text, nullable=True)
    received_at = Column(DateTime(timezone=True), nullable=False)

    # Processing state: received, processing, awaiting_information, processed, failed, ignored
    processing_status = Column(String(32), nullable=False, default="received", index=True)
    complaint_id = Column(String(32), ForeignKey("complaints.complaint_id", ondelete="SET NULL"), nullable=True, index=True)

    # Gemini extraction metadata
    is_civic_complaint = Column(Boolean, default=True)
    extracted_category = Column(String(64), nullable=True)
    extracted_location_text = Column(Text, nullable=True)
    extracted_metadata = Column(Text, nullable=True)  # JSON-serialized Gemini extraction result
    error_details = Column(Text, nullable=True)

    # Attachments
    has_attachments = Column(Boolean, default=False)
    attachments_count = Column(Integer, default=0)
    attachments_info = Column(Text, nullable=True)  # JSON list of filename & size

    # Acknowledgement Email
    acknowledgement_sent = Column(Boolean, default=False)
    acknowledgement_sent_at = Column(DateTime(timezone=True), nullable=True)
    acknowledgement_message_id = Column(String(128), nullable=True)
    acknowledgement_retry_count = Column(Integer, default=0, nullable=False)
    acknowledgement_last_retry_at = Column(DateTime(timezone=True), nullable=True)

    # Follow-up email flag
    is_follow_up = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    complaint = relationship("Complaint", back_populates="email_messages")

    __table_args__ = (
        Index("ix_email_messages_received_at", "received_at"),
        Index("ix_email_messages_created_at", "created_at"),
    )

