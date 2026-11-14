import os
import base64
import email
import logging
import asyncio
import datetime
from email.utils import parseaddr, parsedate_to_datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.core.config import (
    GMAIL_ENABLED,
    GMAIL_INBOX_LABEL,
    GMAIL_POLL_INTERVAL_SECONDS,
    utc_now,
)
from app.database import SessionLocal
from app.models.email_message import EmailMessage
from app.services.email.gmail_auth import GmailAuthService
from app.services.email.email_complaint_processor import EmailComplaintProcessor

logger = logging.getLogger("jansakshi.gmail.monitor")

class InboxMonitor:
    """
    Monitors Gmail inbox, retrieves new unread/eligible messages,
    parses MIME structures and attachments, and passes them to EmailComplaintProcessor.
    """

    _polling_task = None
    _last_sync_at: Optional[datetime.datetime] = None
    _last_error: Optional[str] = None

    @classmethod
    def get_last_sync_info(cls) -> Dict[str, Any]:
        return {
            "last_sync_at": cls._last_sync_at.isoformat() if cls._last_sync_at else None,
            "last_error": cls._last_error,
        }

    @classmethod
    def parse_gmail_message_payload(cls, service, msg_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves full message payload from Gmail API and parses headers, body, and attachments.
        """
        try:
            msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
            payload = msg.get("payload", {})
            headers = payload.get("headers", [])

            headers_dict = {h["name"].lower(): h["value"] for h in headers}

            subject = headers_dict.get("subject", "No Subject")
            from_header = headers_dict.get("from", "")
            sender_name, sender_email = parseaddr(from_header)

            # Determine received_at consistently in timezone-aware UTC
            # 1. Authoritative: Gmail internalDate (epoch milliseconds in UTC)
            received_at: Optional[datetime.datetime] = None
            internal_ms = msg.get("internalDate")
            if internal_ms:
                try:
                    received_at = datetime.datetime.fromtimestamp(
                        int(internal_ms) / 1000.0,
                        tz=datetime.timezone.utc
                    )
                except Exception as e:
                    logger.warning(f"Could not parse internalDate {internal_ms}: {e}")
                    received_at = None

            # 2. Fallback: Parse MIME Date header and convert strictly to UTC
            if not received_at:
                date_str = headers_dict.get("date")
                if date_str:
                    try:
                        dt = parsedate_to_datetime(date_str)
                        if dt.tzinfo is None:
                            received_at = dt.replace(tzinfo=datetime.timezone.utc)
                        else:
                            received_at = dt.astimezone(datetime.timezone.utc)
                    except Exception as e:
                        logger.warning(f"Could not parse Date header {date_str}: {e}")
                        received_at = None

            # 3. Final fallback: utc_now()
            if not received_at:
                received_at = utc_now()
            elif received_at.tzinfo is not None:
                received_at = received_at.astimezone(datetime.timezone.utc)

            snippet = msg.get("snippet", "")
            body_plain = ""
            body_html = ""
            attachments = []

            # Recursive part parsing
            def walk_parts(part):
                nonlocal body_plain, body_html, attachments
                mime_type = part.get("mimeType", "")
                filename = part.get("filename", "")
                body_data = part.get("body", {})

                # Check for attachments
                if filename and body_data.get("attachmentId"):
                    att_id = body_data.get("attachmentId")
                    try:
                        att_res = service.users().messages().attachments().get(
                            userId="me",
                            messageId=msg_id,
                            id=att_id
                        ).execute()
                        data_b64 = att_res.get("data", "")
                        raw_bytes = base64.urlsafe_b64decode(data_b64.encode("UTF-8"))
                        attachments.append({
                            "filename": filename,
                            "data": raw_bytes,
                            "mime_type": mime_type,
                        })
                    except Exception as att_err:
                        logger.warning(f"Failed to fetch attachment {filename} for msg {msg_id}: {att_err}")

                elif mime_type == "text/plain" and not body_plain:
                    raw_b64 = body_data.get("data")
                    if raw_b64:
                        body_plain = base64.urlsafe_b64decode(raw_b64.encode("UTF-8")).decode("utf-8", errors="ignore")

                elif mime_type == "text/html" and not body_html:
                    raw_b64 = body_data.get("data")
                    if raw_b64:
                        body_html = base64.urlsafe_b64decode(raw_b64.encode("UTF-8")).decode("utf-8", errors="ignore")

                for subpart in part.get("parts", []):
                    walk_parts(subpart)

            walk_parts(payload)

            # Fallback if body_plain is empty but snippet exists
            if not body_plain:
                body_plain = snippet

            return {
                "gmail_message_id": msg_id,
                "gmail_thread_id": msg.get("threadId"),
                "sender_email": sender_email,
                "sender_name": sender_name,
                "subject": subject,
                "snippet": snippet,
                "body_plain": body_plain,
                "body_html": body_html,
                "received_at": received_at,
                "attachments": attachments,
            }
        except Exception as e:
            logger.error(f"Error parsing Gmail message {msg_id}: {e}")
            return None

    @classmethod
    async def sync_inbox(
        cls,
        db: Session,
        max_messages: int = 15,
        background_tasks = None
    ) -> Dict[str, Any]:
        """
        Polls the Gmail inbox, finds new unprocessed emails, and processes each.
        """
        service = GmailAuthService.get_gmail_service()
        if not service:
            return {
                "status": "unauthenticated",
                "message": "Gmail API service not connected or authorized.",
                "synced_count": 0,
            }

        cls._last_sync_at = utc_now()
        cls._last_error = None

        try:
            # Query messages with INBOX label
            res = service.users().messages().list(
                userId="me",
                labelIds=[GMAIL_INBOX_LABEL],
                maxResults=max_messages
            ).execute()

            messages = res.get("messages", [])
            logger.info(f"Gmail sync discovered {len(messages)} messages in {GMAIL_INBOX_LABEL}")

            processed_count = 0
            ignored_count = 0
            failed_count = 0
            skipped_count = 0

            for m in messages:
                msg_id = m["id"]
                # Quick check if already processed
                existing = db.query(EmailMessage).filter(EmailMessage.gmail_message_id == msg_id).first()
                if existing and existing.processing_status in ("processed", "ignored"):
                    skipped_count += 1
                    continue

                parsed = cls.parse_gmail_message_payload(service, msg_id)
                if not parsed:
                    continue

                result = await EmailComplaintProcessor.process_raw_email(
                    db=db,
                    message_data=parsed,
                    background_tasks=background_tasks
                )

                if result.get("status") in ("success", "follow_up_processed"):
                    processed_count += 1
                elif result.get("status") == "ignored":
                    ignored_count += 1
                elif result.get("status") == "failed":
                    failed_count += 1

            return {
                "status": "success",
                "total_found": len(messages),
                "processed": processed_count,
                "ignored": ignored_count,
                "failed": failed_count,
                "skipped_previously_processed": skipped_count,
                "synced_at": cls._last_sync_at.isoformat()
            }

        except Exception as e:
            cls._last_error = str(e)
            logger.error(f"Error during Gmail inbox synchronization: {e}")
            return {
                "status": "error",
                "error": str(e),
                "synced_count": 0,
            }

