import os
import base64
import email
import logging
import asyncio
import datetime
import threading
from contextlib import contextmanager
from email.utils import parseaddr, parsedate_to_datetime
from typing import Dict, Any, List, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import (
    GMAIL_ENABLED,
    GMAIL_INBOX_LABEL,
    GMAIL_POLL_INTERVAL_SECONDS,
    utc_now,
)
from app.database import SessionLocal, engine, get_lock_engine
from app.models.complaint import Complaint
from app.models.email_message import EmailMessage
from app.services.email.gmail_auth import GmailAuthService
from app.services.email.acknowledgement_service import AcknowledgementService
from app.services.email.email_complaint_processor import EmailComplaintProcessor

logger = logging.getLogger("jansakshi.gmail.monitor")

class GmailSyncLock:
    """
    Session-level concurrency lock preventing parallel inbox sync invocations.
    Uses PostgreSQL advisory locks exclusively on a dedicated, direct connection from get_lock_engine().
    Guarantees that db.commit() in application sessions cannot alter or release the physical lock connection.
    Invalidates connection on acquisition exception, unlock exception, or unlock failure.
    Falls back to a thread lock for SQLite/testing environments.
    """
    _thread_lock = threading.Lock()
    ADVISORY_LOCK_ID = 987654321

    @classmethod
    @contextmanager
    def acquire(cls, db_or_engine=None):
        target_engine = None
        is_session = False

        if db_or_engine:
            if hasattr(db_or_engine, "get_bind") and not hasattr(db_or_engine, "dialect"):
                is_session = True
                try:
                    target_engine = db_or_engine.get_bind()
                except Exception:
                    target_engine = getattr(db_or_engine, "bind", None)
            elif hasattr(db_or_engine, "dialect"):
                target_engine = db_or_engine
            elif hasattr(db_or_engine, "connect"):
                target_engine = db_or_engine

        # Determine whether running on PostgreSQL
        is_postgres = False
        try:
            if target_engine and getattr(target_engine, "dialect", None):
                if target_engine.dialect.name == "postgresql":
                    is_postgres = True
            else:
                default_lock_eng = get_lock_engine()
                if default_lock_eng and getattr(default_lock_eng, "dialect", None) and default_lock_eng.dialect.name == "postgresql":
                    is_postgres = True
        except Exception:
            pass

        if is_postgres:
            # On PostgreSQL, ALWAYS use get_lock_engine() to obtain a dedicated unpooled connection,
            # even when sync_inbox receives a SQLAlchemy Session, to prevent locks running
            # through the application's pooled (-pooler) connection.
            # (If an explicit mock/test Engine was passed directly, not a Session, respect that engine).
            if is_session or db_or_engine is None:
                lock_engine = get_lock_engine()
            elif hasattr(db_or_engine, "connect") and getattr(db_or_engine, "dialect", None) and db_or_engine.dialect.name == "postgresql":
                lock_engine = db_or_engine
            else:
                lock_engine = target_engine or get_lock_engine()

            conn = None
            try:
                conn = lock_engine.connect()
            except Exception as e:
                logger.error(f"Failed to check out dedicated connection for advisory lock: {e}")
                yield False
                return

            acquired = False
            try:
                res = conn.execute(text(f"SELECT pg_try_advisory_lock({cls.ADVISORY_LOCK_ID})")).scalar()
                acquired = bool(res)
                if acquired:
                    conn.commit()
            except Exception as e:
                logger.error(f"Failed to execute pg_try_advisory_lock on dedicated connection: {e}")
                acquired = False
                try:
                    conn.invalidate()
                except Exception:
                    pass
                try:
                    conn.close()
                except Exception:
                    pass
                yield False
                return

            if not acquired:
                try:
                    conn.close()
                except Exception:
                    pass
                yield False
                return

            logger.info(f"Acquired PostgreSQL advisory lock {cls.ADVISORY_LOCK_ID} on dedicated connection.")
            try:
                yield True
            finally:
                try:
                    unlocked = conn.execute(text(f"SELECT pg_advisory_unlock({cls.ADVISORY_LOCK_ID})")).scalar()
                    if not unlocked:
                        logger.warning(f"pg_advisory_unlock({cls.ADVISORY_LOCK_ID}) returned False on dedicated connection.")
                        try:
                            conn.invalidate()
                        except Exception:
                            pass
                    else:
                        conn.commit()
                        logger.info(f"Successfully released PostgreSQL advisory lock {cls.ADVISORY_LOCK_ID}.")
                except Exception as e:
                    logger.error(f"Exception during pg_advisory_unlock on dedicated connection: {e}")
                    try:
                        conn.invalidate()
                    except Exception:
                        pass
                finally:
                    try:
                        conn.close()
                    except Exception as e:
                        logger.warning(f"Error closing dedicated lock connection: {e}")
        else:
            acquired = cls._thread_lock.acquire(blocking=False)
            if not acquired:
                yield False
                return
            try:
                yield True
            finally:
                cls._thread_lock.release()

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

        with GmailSyncLock.acquire(db) as lock_acquired:
            if not lock_acquired:
                logger.info("Gmail inbox sync skipped: another sync task is actively holding the lock.")
                return {
                    "status": "skipped",
                    "message": "Another synchronization job is currently in progress.",
                    "synced_count": 0,
                }

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

                # ------------------------------------------------------------------
                # Safe, Genuinely Bounded Automatic Retry for Pending Acknowledgements
                # Persistent tracking, exponential backoff, maximum 5 attempts, fair queueing
                # ------------------------------------------------------------------
                MAX_AUTOMATIC_ACK_RETRIES = 5
                BACKOFF_DELAYS_SECONDS = [300, 900, 3600, 10800, 43200]  # 5m, 15m, 1h, 3h, 12h

                ack_retried_count = 0
                ack_success_count = 0
                now = utc_now()

                # Query pending acknowledgements that have not exceeded MAX_AUTOMATIC_ACK_RETRIES
                # Order by acknowledgement_last_retry_at.asc().nullsfirst(), id.asc() to guarantee fairness.
                # Scan up to 100 pending candidates so ineligible records in long backoff windows do not starve eligible ones.
                candidate_acks = db.query(EmailMessage).filter(
                    EmailMessage.complaint_id != None,
                    EmailMessage.acknowledgement_sent == False,
                    EmailMessage.processing_status.in_(["processed", "awaiting_information"]),
                    EmailMessage.acknowledgement_retry_count < MAX_AUTOMATIC_ACK_RETRIES
                ).order_by(
                    EmailMessage.acknowledgement_last_retry_at.asc().nullsfirst(),
                    EmailMessage.id.asc()
                ).limit(100).all()

                # Filter by exponential backoff window (bounded to 5 dispatches per sync run)
                eligible_acks = []
                for cand in candidate_acks:
                    retry_cnt = cand.acknowledgement_retry_count or 0
                    if not cand.acknowledgement_last_retry_at:
                        eligible_acks.append(cand)
                    else:
                        # 0-indexed backoff lookup: retry_cnt=1 -> 300s (5m), retry_cnt=2 -> 900s (15m), etc.
                        delay_idx = max(0, min(retry_cnt - 1, len(BACKOFF_DELAYS_SECONDS) - 1)) if retry_cnt > 0 else 0
                        delay_sec = BACKOFF_DELAYS_SECONDS[delay_idx]
                        last_try = cand.acknowledgement_last_retry_at
                        if last_try.tzinfo is None:
                            last_try = last_try.replace(tzinfo=datetime.timezone.utc)
                        if (now - last_try).total_seconds() >= delay_sec:
                            eligible_acks.append(cand)
                    if len(eligible_acks) >= 5:
                        break

                for pending_msg in eligible_acks:
                    complaint = db.query(Complaint).filter(Complaint.complaint_id == pending_msg.complaint_id).first()
                    if complaint:
                        ack_retried_count += 1
                        try:
                            ack_ok = AcknowledgementService.send_acknowledgement(
                                db=db,
                                complaint=complaint,
                                email_record=pending_msg,
                                location_missing=(complaint.latitude is None)
                            )
                            if ack_ok:
                                ack_success_count += 1
                        except Exception as ack_err:
                            logger.error(f"Error during automatic retry of acknowledgement for {pending_msg.gmail_message_id}: {ack_err}")

                return {
                    "status": "success",
                    "total_found": len(messages),
                    "processed": processed_count,
                    "ignored": ignored_count,
                    "failed": failed_count,
                    "skipped_previously_processed": skipped_count,
                    "acknowledgements_retried": ack_retried_count,
                    "acknowledgements_retry_success": ack_success_count,
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

