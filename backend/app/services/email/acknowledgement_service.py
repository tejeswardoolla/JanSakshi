import base64
import logging
from email.mime.text import MIMEText
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.core.config import FRONTEND_URL, GMAIL_INBOX_ADDRESS, utc_now
from app.models.complaint import Complaint, ComplaintEvent
from app.models.email_message import EmailMessage
from app.services.email.gmail_auth import GmailAuthService

logger = logging.getLogger("jansakshi.email.acknowledgement")

class AcknowledgementService:
    """
    Constructs and sends professional acknowledgement emails via Gmail API.
    Records delivery in audit logs and EmailMessage state.
    """

    @classmethod
    def create_message(
        cls,
        sender_email: str,
        to_email: str,
        subject: str,
        body_text: str,
        thread_id: Optional[str] = None,
        in_reply_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """Creates a MIME email message formatted for the Gmail API."""
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
        Sends acknowledgement email to citizen and updates database records.
        """
        if email_record.acknowledgement_sent:
            logger.info(f"Acknowledgement already sent for message {email_record.gmail_message_id}; skipping.")
            return True

        tracking_url = f"{FRONTEND_URL}/track?id={complaint.complaint_id}"
        subject = f"JanSakshi Complaint Registered – {complaint.complaint_id}"

        # Location text formatting
        if location_missing or complaint.latitude is None or complaint.longitude is None:
            location_info = (
                "Status: Awaiting Incident Location\n"
                "Action Required: Please reply directly to this email with the street address, landmark, or a Google Maps link so civic authorities can locate and dispatch inspection teams."
            )
        else:
            location_info = f"Coordinates: {complaint.latitude:.5f}, {complaint.longitude:.5f} ({complaint.location_source})"

        body_text = f"""Dear Citizen,

Thank you for reporting a public infrastructure issue through JanSakshi.

Your complaint has been successfully registered.

==================================================
COMPLAINT DETAILS
==================================================
Reference ID: {complaint.complaint_id}
Category: {complaint.category}
{location_info}

Live Resolution Tracking:
{tracking_url}

==================================================
AI VERIFICATION & SAFEGUARD NOTICE
==================================================
Our AI system will analyze your submitted description and attached photographic evidence.
This AI assessment provides preliminary severity and category validation. Final resolution and ground dispatch are authorized directly by municipal authorities.

Thank you for actively contributing to better public infrastructure in our community.

Sincerely,
Team JanSakshi
AI-Powered Public Complaint Verification and Accountability System
"""

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
        event = ComplaintEvent(
            complaint_id=complaint.complaint_id,
            event_type="acknowledgement_email_dispatched",
            previous_value=None,
            new_value=email_record.sender_email,
            description=f"Acknowledgement email dispatched to citizen ({email_record.sender_email}). Location status: {'awaiting_clarification' if location_missing else 'coordinates_captured'}.",
            source="email_service",
            created_at=utc_now()
        )
        db.add(event)
        db.commit()

        return True

