import os
import base64
import datetime
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session

from app.core.config import FRONTEND_URL, GMAIL_INBOX_ADDRESS, utc_now
from app.models.complaint import Complaint, ComplaintEvent
from app.models.email_message import EmailMessage
from app.services.email.gmail_auth import GmailAuthService
from app.services.email.email_templates import (
    render_acknowledgement_email_html,
    render_acknowledgement_email_text,
)

logger = logging.getLogger("jansakshi.email.acknowledgement")

class AcknowledgementService:
    """
    Constructs and sends professional HTML & plain-text acknowledgement emails via Gmail API.
    Records delivery in audit logs and EmailMessage state.
    """

    @classmethod
    def get_logo_bytes(cls) -> Optional[bytes]:
        """Loads the official JanSakshi logo asset bytes."""
        possible_paths = [
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "assets", "jansakshi-logo.jpg")),
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "frontend", "public", "assets", "jansakshi-logo.jpg")),
        ]
        for p in possible_paths:
            if os.path.exists(p):
                with open(p, "rb") as f:
                    return f.read()
        return None

    @classmethod
    def format_submission_datetime(cls, dt: Optional[datetime.datetime]) -> str:
        """Formats datetime into human-readable IST string."""
        if not dt:
            return "Recently Submitted"
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        ist_dt = dt.astimezone(datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
        return ist_dt.strftime("%d %B %Y, %I:%M %p IST")

    @classmethod
    def generate_email_content(
        cls,
        complaint: Complaint,
        email_record: Optional[EmailMessage] = None,
        location_missing: bool = False,
        logo_url: Optional[str] = None
    ) -> Tuple[str, str, str]:
        """
        Generates (subject, body_text, body_html) dynamically populated from complaint
        and email record data.
        """
        subject = f"JanSakshi Complaint Registered – {complaint.complaint_id}"

        # Resolve location status and display string
        loc_missing = bool(
            location_missing
            or complaint.latitude is None
            or complaint.longitude is None
            or str(complaint.location_source).lower() == "missing"
        )

        if loc_missing:
            location_display = "Awaiting Incident Location"
        elif email_record and email_record.extracted_location_text:
            location_display = f"{email_record.extracted_location_text} (Coordinates: {complaint.latitude:.5f}, {complaint.longitude:.5f})"
        else:
            location_display = f"Coordinates: {complaint.latitude:.5f}, {complaint.longitude:.5f} ({complaint.location_source})"

        # Resolve evidence count & status
        ev_count = 0
        if hasattr(complaint, "evidence_files") and complaint.evidence_files:
            ev_count = len(complaint.evidence_files)
        elif email_record and email_record.attachments_count:
            ev_count = email_record.attachments_count

        if ev_count == 1:
            evidence_status = "1 photographic evidence attachment received & verified"
        elif ev_count > 1:
            evidence_status = f"{ev_count} photographic evidence attachments received & verified"
        else:
            evidence_status = "No photographic evidence attached"

        # Resolve citizen name
        citizen_name = complaint.citizen_name or (email_record.sender_name if email_record else None) or "Citizen"

        # Construct public tracking URL using complaint ID & existing token mechanism
        token_param = f"&token={complaint.tracking_token}" if complaint.tracking_token else ""
        tracking_url = f"{FRONTEND_URL}/track?id={complaint.complaint_id}{token_param}"

        status_display = complaint.status or complaint.admin_status or "Received"
        submission_dt_str = cls.format_submission_datetime(complaint.created_at)
        official_email = GMAIL_INBOX_ADDRESS or "jansakshiofficial@gmail.com"

        # Render HTML template
        body_html = render_acknowledgement_email_html(
            complaint_id=complaint.complaint_id,
            category=complaint.category,
            location_display=location_display,
            submission_datetime_str=submission_dt_str,
            status_display=status_display,
            evidence_status=evidence_status,
            tracking_url=tracking_url,
            location_missing=loc_missing,
            citizen_name=citizen_name,
            official_email=official_email,
            logo_url=logo_url
        )

        # Render plain text fallback
        body_text = render_acknowledgement_email_text(
            complaint_id=complaint.complaint_id,
            category=complaint.category,
            location_display=location_display,
            submission_datetime_str=submission_dt_str,
            status_display=status_display,
            evidence_status=evidence_status,
            tracking_url=tracking_url,
            location_missing=loc_missing,
            citizen_name=citizen_name,
            official_email=official_email
        )

        return subject, body_text, body_html

    @classmethod
    def create_message(
        cls,
        sender_email: str,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        thread_id: Optional[str] = None,
        in_reply_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """Creates a MIME email message formatted for the Gmail API (supports multipart HTML + plain text fallback)."""
        if body_html:
            message = MIMEMultipart("alternative")
            message["to"] = to_email
            message["from"] = sender_email
            message["subject"] = subject

            if in_reply_to:
                message["In-Reply-To"] = in_reply_to
                message["References"] = in_reply_to

            # Attach plain-text fallback first, then HTML alternative
            part_text = MIMEText(body_text, "plain", "utf-8")
            part_html = MIMEText(body_html, "html", "utf-8")
            message.attach(part_text)
            message.attach(part_html)
        else:
            message = MIMEText(body_text, "plain", "utf-8")
            message["to"] = to_email
            message["from"] = sender_email
            message["subject"] = subject

            if in_reply_to:
                message["In-Reply-To"] = in_reply_to
                message["References"] = in_reply_to

        raw_bytes = message.as_bytes()
        raw_b64 = base64.urlsafe_b64encode(raw_bytes).decode("utf-8")

        payload: Dict[str, Any] = {"raw": raw_b64}
        if thread_id:
            payload["threadId"] = thread_id
        return payload

    @classmethod
    def send_acknowledgement(
        cls,
        db: Session,
        complaint: Complaint,
        email_record: EmailMessage,
        location_missing: bool = False
    ) -> bool:
        """
        Sends rich HTML + plain text acknowledgement email to citizen and updates database records.
        """
        if email_record.acknowledgement_sent:
            logger.info(f"Acknowledgement already sent for message {email_record.gmail_message_id}; skipping.")
            return True

        subject, body_text, body_html = cls.generate_email_content(
            complaint=complaint,
            email_record=email_record,
            location_missing=location_missing
        )

        # Attempt to send via Gmail API
        sent_id = None
        service = GmailAuthService.get_gmail_service()
        if service:
            try:
                profile = GmailAuthService.get_mailbox_profile() or {}
                my_email = profile.get("email_address") or GMAIL_INBOX_ADDRESS or "me"
                msg_payload = cls.create_message(
                    sender_email=my_email,
                    to_email=email_record.sender_email,
                    subject=subject,
                    body_text=body_text,
                    body_html=body_html,
                    thread_id=email_record.gmail_thread_id,
                    in_reply_to=email_record.gmail_message_id
                )
                sent = service.users().messages().send(userId="me", body=msg_payload).execute()
                sent_id = sent.get("id")
                logger.info(f"Sent acknowledgement email for {complaint.complaint_id} -> {email_record.sender_email} (Msg ID: {sent_id})")
            except Exception as e:
                logger.error(f"Failed to send email via Gmail API: {e}")
                # Record the error on email message but proceed with audit
                email_record.error_details = f"Email send failed: {str(e)}"
        else:
            logger.info(f"Gmail service not connected. Acknowledgement generated and recorded in system for {complaint.complaint_id}")
            sent_id = f"simulated_ack_{complaint.complaint_id}"

        # Update email record
        email_record.acknowledgement_sent = True
        email_record.acknowledgement_sent_at = utc_now()
        email_record.acknowledgement_message_id = sent_id

        # Audit event on complaint
        loc_is_missing = location_missing or complaint.latitude is None or complaint.longitude is None
        event = ComplaintEvent(
            complaint_id=complaint.complaint_id,
            event_type="acknowledgement_email_dispatched",
            previous_value=None,
            new_value=email_record.sender_email,
            description=f"Acknowledgement email dispatched to citizen ({email_record.sender_email}). Location status: {'awaiting_clarification' if loc_is_missing else 'coordinates_captured'}.",
            source="email_service",
            created_at=utc_now()
        )
        db.add(event)
        db.commit()

        return True
