import logging
import datetime
import urllib.parse
import hmac
import os
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, Header, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.complaint import Complaint, ComplaintEvent
from app.models.email_message import EmailMessage
from app.schemas import EmailStatusResponse, EmailMessageResponse
from app.services.email import (
    GmailAuthService,
    InboxMonitor,
    EmailComplaintProcessor,
    GeminiEmailExtractor,
)
from app.core.config import FRONTEND_URL, utc_now
from app.core.security import require_roles
from app.models.authority import User

logger = logging.getLogger("jansakshi.email.routes")

router = APIRouter(prefix="/api/email", tags=["Email Complaint System"])

def _format_email_response(msg: EmailMessage) -> EmailMessageResponse:
    return EmailMessageResponse(
        id=msg.id,
        gmail_message_id=msg.gmail_message_id,
        gmail_thread_id=msg.gmail_thread_id,
        sender_email=msg.sender_email,
        sender_name=msg.sender_name,
        subject=msg.subject,
        snippet=msg.snippet,
        body_plain=msg.body_plain,
        received_at=msg.received_at,
        processing_status=msg.processing_status,
        complaint_id=msg.complaint_id,
        is_civic_complaint=msg.is_civic_complaint,
        extracted_category=msg.extracted_category,
        extracted_location_text=msg.extracted_location_text,
        extracted_metadata=msg.extracted_metadata,
        error_details=msg.error_details,
        has_attachments=bool(msg.has_attachments) if msg.has_attachments is not None else False,
        attachments_count=msg.attachments_count or 0,
        attachments_info=msg.attachments_info,
        acknowledgement_sent=bool(msg.acknowledgement_sent) if msg.acknowledgement_sent is not None else False,
        acknowledgement_sent_at=msg.acknowledgement_sent_at,
        acknowledgement_retry_count=getattr(msg, "acknowledgement_retry_count", 0) or 0,
        acknowledgement_last_retry_at=getattr(msg, "acknowledgement_last_retry_at", None),
        is_follow_up=bool(msg.is_follow_up) if msg.is_follow_up is not None else False,
        created_at=msg.created_at,
    )

@router.get("/status", response_model=EmailStatusResponse)
async def get_email_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"]))
):
    """
    Returns the real-time configuration, OAuth connection status,
    and processing statistics for the Gmail AI complaint subsystem.
    """
    auth_status = GmailAuthService.get_status()
    sync_info = InboxMonitor.get_last_sync_info()

    total_msgs = db.query(EmailMessage).count()
    total_processed = db.query(EmailMessage).filter(EmailMessage.processing_status == "processed").count()
    total_awaiting = db.query(EmailMessage).filter(EmailMessage.processing_status == "awaiting_information").count()
    total_needs_review = db.query(EmailMessage).filter(EmailMessage.processing_status == "needs_review").count()
    total_ignored = db.query(EmailMessage).filter(EmailMessage.processing_status == "ignored").count()
    total_failed = db.query(EmailMessage).filter(EmailMessage.processing_status == "failed").count()

    return EmailStatusResponse(
        enabled=auth_status["enabled"],
        configured=auth_status["configured"],
        authenticated=auth_status["authenticated"],
        official_inbox_address=auth_status["official_inbox_address"],
        connected_email=auth_status["connected_email"],
        email_address=auth_status["email_address"],
        mailbox_match=auth_status["mailbox_match"],
        account_mismatch_warning=auth_status["account_mismatch_warning"],
        status=auth_status["status"],
        message=auth_status["message"],
        total_messages_received=total_msgs,
        total_processed=total_processed,
        total_awaiting_info=total_awaiting,
        total_needs_review=total_needs_review,
        total_ignored=total_ignored,
        total_failed=total_failed,
        last_sync_at=sync_info.get("last_sync_at"),
    )

@router.get("/messages", response_model=List[EmailMessageResponse])
async def list_email_messages(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status: received, processing, processed, awaiting_information, needs_review, failed, ignored"),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"]))
):
    """
    Returns paginated email processing records for municipal monitoring.
    """
    query = db.query(EmailMessage)
    if status_filter:
        query = query.filter(EmailMessage.processing_status == status_filter.lower())

    messages = query.order_by(EmailMessage.received_at.desc()).offset(offset).limit(limit).all()
    return [_format_email_response(m) for m in messages]

@router.get("/messages/{message_id}", response_model=EmailMessageResponse)
async def get_email_message(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"]))
):
    """
    Returns the full details of a specific incoming email record including extraction metadata.
    """
    msg = db.query(EmailMessage).filter(EmailMessage.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Email record not found.")
    return _format_email_response(msg)

@router.post("/messages/{message_id}/retry")
async def retry_email_processing(
    message_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"]))
):
    """
    Retries failed processing for an existing email message safely without creating duplicates.
    """
    msg = db.query(EmailMessage).filter(EmailMessage.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Email record not found.")

    raw_data = {
        "gmail_message_id": msg.gmail_message_id,
        "gmail_thread_id": msg.gmail_thread_id,
        "sender_email": msg.sender_email,
        "sender_name": msg.sender_name,
        "subject": msg.subject or "",
        "snippet": msg.snippet or "",
        "body_plain": msg.body_plain or "",
        "body_html": msg.body_html or "",
        "received_at": msg.received_at,
        "attachments": [],
    }

    result = await EmailComplaintProcessor.process_raw_email(
        db=db,
        message_data=raw_data,
        background_tasks=background_tasks
    )
    return result

@router.post("/messages/{message_id}/resend-acknowledgement")
async def resend_acknowledgement(
    message_id: int,
    force_retry: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"]))
):
    """
    Retries sending an acknowledgement email for a registered complaint if previously failed.
    """
    msg = db.query(EmailMessage).filter(EmailMessage.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Email record not found.")
    if not msg.complaint_id:
        raise HTTPException(status_code=400, detail="No complaint linked to this email message.")

    complaint = db.query(Complaint).filter(Complaint.complaint_id == msg.complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail=f"Linked complaint {msg.complaint_id} not found.")

    from app.services.email.acknowledgement_service import AcknowledgementService
    success = AcknowledgementService.send_acknowledgement(
        db=db,
        complaint=complaint,
        email_record=msg,
        location_missing=(complaint.latitude is None),
        force_retry=force_retry
    )
    if not success:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to dispatch acknowledgement: {msg.error_details or 'Gmail sending failed'}"
        )
    return {
        "status": "success",
        "message": f"Acknowledgement email successfully sent to {msg.sender_email}",
        "acknowledgement_message_id": msg.acknowledgement_message_id
    }

@router.post("/messages/{message_id}/re-extract", response_model=EmailMessageResponse)
async def re_extract_email_message(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"]))
):
    """
    Safely re-runs the updated extraction logic on an existing email message
    and updates the email message and linked complaint in-place without creating
    duplicate complaints or re-sending acknowledgement emails.
    """
    msg = db.query(EmailMessage).filter(EmailMessage.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Email record not found.")

    extraction = await GeminiEmailExtractor.extract(
        subject=msg.subject or "",
        body=msg.body_plain or msg.snippet or "",
        sender_email=msg.sender_email
    )

    # Normalize received_at against authoritative Gmail API internalDate (epoch ms in UTC)
    service = GmailAuthService.get_gmail_service()
    if service and msg.gmail_message_id:
        try:
            gmsg = service.users().messages().get(
                userId="me",
                id=msg.gmail_message_id,
                format="metadata",
                metadataHeaders=["Date"]
            ).execute()
            internal_ms = gmsg.get("internalDate")
            if internal_ms:
                msg.received_at = datetime.datetime.fromtimestamp(
                    int(internal_ms) / 1000.0,
                    tz=datetime.timezone.utc
                )
        except Exception as e:
            logger.warning(f"Could not refresh internalDate for {msg.gmail_message_id}: {e}")

    # Update only extraction metadata fields on the email record
    msg.is_civic_complaint = extraction.is_civic_complaint
    msg.extracted_category = extraction.category
    msg.extracted_location_text = extraction.location_text
    msg.extracted_metadata = extraction.model_dump_json()
    if extraction.latitude is not None and extraction.longitude is not None:
        msg.processing_status = "processed"

    # Update linked complaint location in-place if present
    if msg.complaint_id:
        complaint = db.query(Complaint).filter(Complaint.complaint_id == msg.complaint_id).first()
        if complaint:
            if extraction.latitude is not None and extraction.longitude is not None:
                complaint.latitude = extraction.latitude
                complaint.longitude = extraction.longitude
                complaint.location_source = "maps_url" if extraction.google_maps_url else "email_parsed"
                complaint.google_maps_url = extraction.google_maps_url or f"https://www.google.com/maps?q={extraction.latitude:.6f},{extraction.longitude:.6f}"
                if complaint.status == "Awaiting Location":
                    complaint.status = "Received"

            # Add audit event for traceability
            event = ComplaintEvent(
                complaint_id=complaint.complaint_id,
                event_type="location_re_extracted",
                previous_value=None,
                new_value=f"{extraction.latitude}, {extraction.longitude}" if extraction.latitude else extraction.location_text,
                description=f"Email location re-extracted in-place. Landmark: '{extraction.location_text}'. Coordinates: {extraction.latitude}, {extraction.longitude}.",
                source="email_service",
                created_at=utc_now()
            )
            db.add(event)

    db.commit()
    db.refresh(msg)
    return _format_email_response(msg)

class ConfirmCivicRequest(BaseModel):
    category_override: Optional[str] = None
    landmark_override: Optional[str] = None
    notes: Optional[str] = None

class MarkNonCivicRequest(BaseModel):
    reason: Optional[str] = None

@router.post("/messages/{message_id}/confirm-civic")
async def confirm_civic_complaint(
    message_id: int,
    background_tasks: BackgroundTasks,
    payload: Optional[ConfirmCivicRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"]))
):
    """
    Admin action: Confirms that an email currently in needs_review or ignored
    is a genuine civic complaint, executes the complaint pipeline, creates a Complaint,
    and sends official citizen acknowledgement.
    """
    msg = db.query(EmailMessage).filter(EmailMessage.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Email record not found.")

    if msg.complaint_id:
        return {
            "status": "already_has_complaint",
            "message": f"Message already linked to complaint {msg.complaint_id}",
            "complaint_id": msg.complaint_id
        }

    extraction = await GeminiEmailExtractor.extract(
        subject=msg.subject or "",
        body=msg.body_plain or msg.snippet or "",
        sender_email=msg.sender_email
    )

    category = payload.category_override if (payload and payload.category_override) else (
        extraction.category if extraction.category != "Other" else "Other"
    )
    landmark = payload.landmark_override if (payload and payload.landmark_override) else extraction.location_text

    has_coords = extraction.latitude is not None and extraction.longitude is not None
    location_src = "maps_url" if extraction.google_maps_url else ("email_parsed" if has_coords else "email_pending_clarification")

    from app.pipeline.complaint_pipeline import ComplaintProcessingPipeline, NormalizedComplaintInput
    normalized_input = NormalizedComplaintInput(
        category=category,
        description=extraction.description or msg.subject or "Citizen reported grievance via email.",
        latitude=extraction.latitude,
        longitude=extraction.longitude,
        location_source=location_src,
        google_maps_url=extraction.google_maps_url,
        citizen_name=msg.sender_name,
        citizen_email=msg.sender_email,
        submission_channel="email",
        pre_saved_evidence=[]
    )

    pipeline = ComplaintProcessingPipeline(db=db, background_tasks=background_tasks)
    complaint_record = await pipeline.execute(normalized_input)

    msg.complaint_id = complaint_record.complaint_id
    msg.is_civic_complaint = True
    msg.extracted_category = category
    msg.extracted_location_text = landmark
    msg.processing_status = "awaiting_information" if (extraction.latitude is None) else "processed"
    msg.error_details = f"Manually confirmed as Civic Complaint by Admin ({current_user.full_name or current_user.username})."
    db.commit()

    event = ComplaintEvent(
        complaint_id=complaint_record.complaint_id,
        event_type="admin_intake_confirmed",
        previous_value=None,
        new_value="Confirmed Civic",
        description=f"Promoted to official complaint by Admin {current_user.username}. Notes: {payload.notes if payload else 'None'}",
        source="admin_desk",
        created_at=utc_now()
    )
    db.add(event)
    db.commit()

    from app.services.email.acknowledgement_service import AcknowledgementService
    AcknowledgementService.send_acknowledgement(
        db=db,
        complaint=complaint_record,
        email_record=msg,
        location_missing=(extraction.latitude is None)
    )

    return {
        "status": "success",
        "message": f"Successfully created complaint {complaint_record.complaint_id}",
        "complaint_id": complaint_record.complaint_id,
        "tracking_token": complaint_record.tracking_token
    }

@router.post("/messages/{message_id}/mark-non-civic")
async def mark_email_non_civic(
    message_id: int,
    payload: Optional[MarkNonCivicRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"]))
):
    """
    Admin action: Reclassifies an email as non-civic (status = ignored),
    ensuring it does not trigger complaints or alerts.
    """
    msg = db.query(EmailMessage).filter(EmailMessage.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Email record not found.")

    reason = (payload.reason if payload and payload.reason else "Marked non-civic by Administrator.")
    msg.is_civic_complaint = False
    msg.processing_status = "ignored"
    msg.error_details = f"Non-civic confirmed by Admin ({current_user.full_name or current_user.username}): {reason}"
    db.commit()

    return {
        "status": "success",
        "message": "Message successfully marked as non-civic and ignored.",
        "message_id": msg.id
    }

def verify_cron_secret(authorization: Optional[str] = Header(None)) -> bool:
    """
    Validates that the incoming request carries a valid Bearer token matching CRON_SECRET.
    Uses constant-time comparison via hmac.compare_digest to prevent timing attacks.
    """
    from app.core.config import CRON_SECRET
    secret = (CRON_SECRET or os.getenv("CRON_SECRET", "")).strip()
    if not secret:
        logger.error("Cron sync rejected: CRON_SECRET is not configured on this instance.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cron synchronization is not configured or disabled."
        )
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header."
        )
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization scheme. Expected 'Bearer <token>'."
        )
    if not hmac.compare_digest(token.strip(), secret):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid cron secret token."
        )
    return True

@router.post("/cron-sync")
async def cron_sync_inbox(
    background_tasks: BackgroundTasks,
    response: Response,
    max_messages: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    _authorized: bool = Depends(verify_cron_secret),
):
    """
    Scheduled Gmail inbox synchronization endpoint triggered by external runners (e.g. GitHub Actions).
    Secured with Bearer token authentication matching CRON_SECRET.
    Respects GMAIL_ENABLED setting and prevents concurrent runs using PostgreSQL advisory locking.
    Returns HTTP 500 when synchronization encounters an unhandled error so runners detect failure.
    """
    from app.core.config import GMAIL_ENABLED
    is_enabled = GMAIL_ENABLED or os.getenv("GMAIL_ENABLED", "false").lower() in ("true", "1", "yes")
    if not is_enabled:
        logger.info("Cron sync skipped: GMAIL_ENABLED is false.")
        return {
            "status": "disabled",
            "message": "Gmail integration is disabled (GMAIL_ENABLED is false).",
            "messages_checked": 0,
            "civic_complaints_found": 0,
            "processed": 0
        }

    result = await InboxMonitor.sync_inbox(
        db=db,
        max_messages=max_messages,
        background_tasks=background_tasks
    )

    if result.get("status") == "error":
        if response is not None:
            response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        logger.error(f"Cron synchronization failed: {result.get('error')}")

    return result

@router.post("/sync")
async def trigger_inbox_sync(
    background_tasks: BackgroundTasks,
    max_messages: int = Query(15, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"]))
):
    """
    Manually triggers Gmail inbox synchronization and processes new incoming citizen complaints.
    """
    result = await InboxMonitor.sync_inbox(
        db=db,
        max_messages=max_messages,
        background_tasks=background_tasks
    )
    return result

@router.post("/oauth/start")
async def start_oauth_flow(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"]))
):
    """
    Generates a Google OAuth authorization URL to connect JanSakshi to a municipal Gmail inbox.
    """
    auth_url, error = GmailAuthService.generate_auth_url(db=db)
    if error:
        raise HTTPException(status_code=400, detail=error)
    return {
        "status": "success",
        "authorization_url": auth_url
    }

@router.get("/oauth/callback")
async def oauth_callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Handles Google OAuth redirect with authorization code and state,
    validates CSRF state and retrieves preserved PKCE code_verifier,
    and exchanges code for OAuth tokens.
    """
    if error:
        logger.warning(f"Google OAuth authorization returned error: {error}")
        return RedirectResponse(f"{FRONTEND_URL}/email-management?error={urllib.parse.quote(error)}")

    if not state:
        logger.warning("OAuth callback received without state parameter.")
        return RedirectResponse(
            f"{FRONTEND_URL}/email-management?error={urllib.parse.quote('Missing OAuth state parameter. Possible CSRF.')}"
        )

    # Retrieve and consume the matching PKCE code_verifier bound to this state
    code_verifier = GmailAuthService.consume_oauth_state(state, db=db)
    if not code_verifier:
        logger.warning(f"OAuth callback state verification failed or session expired.")
        return RedirectResponse(
            f"{FRONTEND_URL}/email-management?error={urllib.parse.quote('Invalid or expired OAuth session. Please try connecting again.')}"
        )

    if not code:
        logger.warning("OAuth callback received without authorization code.")
        return RedirectResponse(
            f"{FRONTEND_URL}/email-management?error={urllib.parse.quote('Authorization code missing from Google callback.')}"
        )

    success, msg = GmailAuthService.exchange_code_for_tokens(
        code=code,
        code_verifier=code_verifier,
        state=state
    )
    if success:
        return RedirectResponse(f"{FRONTEND_URL}/email-management?connected=true")
    else:
        return RedirectResponse(f"{FRONTEND_URL}/email-management?error={urllib.parse.quote(msg)}")

@router.post("/disconnect")
async def disconnect_gmail(
    current_user: User = Depends(require_roles(["admin"]))
):
    """
    Clears local Gmail OAuth tokens securely.
    """
    success = GmailAuthService.disconnect()
    return {
        "status": "success" if success else "failed",
        "message": "Gmail disconnected. Tokens cleared."
    }

