import os
import sys

# Ensure backend directory is in sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import unittest
import asyncio
from unittest.mock import patch, MagicMock
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup test environment variables before importing app
os.environ["CRON_SECRET"] = "test_cron_secret_token_12345"

from app.database import Base
from app.models.complaint import Complaint
from app.models.email_message import EmailMessage
from app.routes.email_routes import verify_cron_secret, cron_sync_inbox, trigger_inbox_sync, router as email_router
from app.services.email.inbox_monitor import GmailSyncLock, InboxMonitor
from app.services.email.attachment_processor import AttachmentProcessor

# In-memory DB setup
test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
Base.metadata.create_all(bind=test_engine)

class TestGmailAutomationCron(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.valid_token = "test_cron_secret_token_12345"

    def setUp(self):
        from app.models.complaint import ComplaintEvent
        db = TestingSessionLocal()
        db.query(EmailMessage).delete()
        db.query(ComplaintEvent).delete()
        db.query(Complaint).delete()
        db.commit()
        db.close()

    def tearDown(self):
        from app.models.complaint import ComplaintEvent
        db = TestingSessionLocal()
        db.query(EmailMessage).delete()
        db.query(ComplaintEvent).delete()
        db.query(Complaint).delete()
        db.commit()
        db.close()

    def test_verify_cron_secret_missing_header(self):
        """Missing Authorization header must raise 401."""
        with self.assertRaises(HTTPException) as ctx:
            verify_cron_secret(authorization=None)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("Missing Authorization header", ctx.exception.detail)

    def test_verify_cron_secret_invalid_scheme(self):
        """Non-Bearer scheme must raise 401."""
        with self.assertRaises(HTTPException) as ctx:
            verify_cron_secret(authorization="Basic 12345")
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("Invalid authorization scheme", ctx.exception.detail)

    def test_verify_cron_secret_invalid_token(self):
        """Incorrect Bearer token must raise 403 Forbidden."""
        with self.assertRaises(HTTPException) as ctx:
            verify_cron_secret(authorization="Bearer wrong_secret_token")
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("Invalid cron secret token", ctx.exception.detail)

    def test_verify_cron_secret_valid(self):
        """Matching Bearer token must succeed and return True."""
        res = verify_cron_secret(authorization=f"Bearer {self.valid_token}")
        self.assertTrue(res)

    def test_verify_cron_secret_unconfigured(self):
        """When CRON_SECRET is not configured, raises 401."""
        with patch.dict(os.environ, {"CRON_SECRET": ""}):
            with patch("app.core.config.CRON_SECRET", ""):
                with self.assertRaises(HTTPException) as ctx:
                    verify_cron_secret(authorization="Bearer anything")
                self.assertEqual(ctx.exception.status_code, 401)
                self.assertIn("not configured", ctx.exception.detail)

    def test_cron_sync_inbox_disabled_when_gmail_enabled_false(self):
        """When GMAIL_ENABLED is false, returns disabled status without processing."""
        db = TestingSessionLocal()
        mock_bg = MagicMock()
        with patch.dict(os.environ, {"GMAIL_ENABLED": "false"}):
            with patch("app.core.config.GMAIL_ENABLED", False):
                res = asyncio.run(cron_sync_inbox(
                    background_tasks=mock_bg,
                    response=Response(),
                    max_messages=10,
                    db=db,
                    _authorized=True
                ))
                self.assertEqual(res.get("status"), "disabled")
                self.assertIn("GMAIL_ENABLED is false", res.get("message", ""))
                self.assertEqual(res.get("processed"), 0)
        db.close()

    def test_cron_sync_inbox_authorized_success(self):
        """Valid Bearer token and GMAIL_ENABLED triggers sync_inbox successfully."""
        db = TestingSessionLocal()
        mock_bg = MagicMock()
        mock_sync_result = {
            "status": "success",
            "total_found": 3,
            "processed": 1,
            "ignored": 2,
            "failed": 0,
            "skipped_previously_processed": 0
        }
        with patch.dict(os.environ, {"GMAIL_ENABLED": "true"}):
            with patch("app.core.config.GMAIL_ENABLED", True):
                with patch.object(InboxMonitor, "sync_inbox", return_value=mock_sync_result) as mock_sync:
                    res = asyncio.run(cron_sync_inbox(
                        background_tasks=mock_bg,
                        response=Response(),
                        max_messages=10,
                        db=db,
                        _authorized=True
                    ))
                    self.assertEqual(res, mock_sync_result)
                    mock_sync.assert_called_once_with(
                        db=db,
                        max_messages=10,
                        background_tasks=mock_bg
                    )
        db.close()

    def test_concurrency_lock_skips_overlapping_sync(self):
        """When sync is already running, concurrency lock must return status: skipped."""
        db = TestingSessionLocal()
        with GmailSyncLock.acquire(db) as acquired:
            self.assertTrue(acquired)
            # While lock is actively held, a concurrent acquisition must fail
            with GmailSyncLock.acquire(db) as acquired_second:
                self.assertFalse(acquired_second)
        db.close()

    def test_attachment_processor_routes_to_blob_when_configured(self):
        """When Vercel Blob is enabled, attachment processor persists to blob storage."""
        fake_blob_meta = {
            "original_filename": "pothole.jpg",
            "stored_filename": "abc123def456.jpg",
            "file_type": "image/jpeg",
            "file_size": 1024,
            "storage_path": "https://blob.vercel-storage.com/evidence/abc123def456.jpg"
        }
        with patch("app.services.email.attachment_processor.is_blob_storage_enabled", return_value=True):
            with patch("app.services.email.attachment_processor.save_evidence_bytes", return_value=fake_blob_meta) as mock_save:
                res = AttachmentProcessor.process_attachment(
                    filename="pothole.jpg",
                    content_bytes=b"\xFF\xD8\xFF" + b"0" * 500,
                    mime_type="image/jpeg"
                )
                self.assertIsNotNone(res)
                self.assertEqual(res["storage_path"], fake_blob_meta["storage_path"])
                mock_save.assert_called_once()

    def test_attachment_processor_local_fallback(self):
        """When Vercel Blob is not enabled in development mode, attachment processor writes to local directory."""
        temp_dir = "storage/test_evidence_tmp"
        try:
            with patch("app.services.email.attachment_processor.APP_ENV", "development"):
                with patch.dict(os.environ, {"VERCEL": ""}):
                    with patch("app.services.email.attachment_processor.is_blob_storage_enabled", return_value=False):
                        res = AttachmentProcessor.process_attachment(
                            filename="sample_road.jpg",
                            content_bytes=b"\xFF\xD8\xFF" + b"0" * 300,
                            mime_type="image/jpeg",
                            target_dir=temp_dir
                        )
                        self.assertIsNotNone(res)
                        self.assertTrue(os.path.exists(res["storage_path"]))
                        self.assertEqual(res["original_filename"], "sample_road.jpg")
        finally:
            if os.path.exists(temp_dir):
                for f in os.listdir(temp_dir):
                    os.remove(os.path.join(temp_dir, f))
                os.rmdir(temp_dir)

    def test_attachment_processor_fails_closed_in_production_on_blob_upload_error(self):
        """In production, Blob upload failure must fail closed (return None) and NEVER write to ephemeral local disk."""
        temp_dir = "storage/test_evidence_prod_fail_closed"
        try:
            with patch("app.services.email.attachment_processor.APP_ENV", "production"):
                with patch("app.services.email.attachment_processor.is_blob_storage_enabled", return_value=True):
                    with patch("app.services.email.attachment_processor.save_evidence_bytes", side_effect=Exception("Blob API 500 error")):
                        res = AttachmentProcessor.process_attachment(
                            filename="damaged_road.jpg",
                            content_bytes=b"\xFF\xD8\xFF" + b"0" * 400,
                            mime_type="image/jpeg",
                            target_dir=temp_dir
                        )
                        self.assertIsNone(res)
                        self.assertFalse(os.path.exists(temp_dir), "Local directory must NOT be created in production fail-closed state")
        finally:
            if os.path.exists(temp_dir):
                for f in os.listdir(temp_dir):
                    os.remove(os.path.join(temp_dir, f))
                os.rmdir(temp_dir)

    def test_attachment_processor_fails_closed_in_production_when_blob_unconfigured(self):
        """In production, unconfigured BLOB_READ_WRITE_TOKEN must fail closed to prevent silent evidence loss on ephemeral disk."""
        temp_dir = "storage/test_evidence_prod_unconfigured"
        try:
            with patch("app.services.email.attachment_processor.APP_ENV", "production"):
                with patch("app.services.email.attachment_processor.is_blob_storage_enabled", return_value=False):
                    res = AttachmentProcessor.process_attachment(
                        filename="leakage.jpg",
                        content_bytes=b"\xFF\xD8\xFF" + b"0" * 400,
                        mime_type="image/jpeg",
                        target_dir=temp_dir
                    )
                    self.assertIsNone(res)
                    self.assertFalse(os.path.exists(temp_dir), "Local directory must NOT be created when Blob unconfigured in production")
        finally:
            if os.path.exists(temp_dir):
                for f in os.listdir(temp_dir):
                    os.remove(os.path.join(temp_dir, f))
                os.rmdir(temp_dir)

    def test_manual_sync_endpoint_intact(self):
        """Manual admin trigger_inbox_sync remains operational."""
        db = TestingSessionLocal()
        mock_bg = MagicMock()
        mock_admin = MagicMock()
        mock_result = {
            "status": "success",
            "total_found": 2,
            "processed": 1,
            "ignored": 1
        }
        with patch.object(InboxMonitor, "sync_inbox", return_value=mock_result) as mock_sync:
            res = asyncio.run(trigger_inbox_sync(
                background_tasks=mock_bg,
                max_messages=15,
                db=db,
                current_user=mock_admin
            ))
            self.assertEqual(res, mock_result)
            mock_sync.assert_called_once_with(
                db=db,
                max_messages=15,
                background_tasks=mock_bg
            )
        db.close()

    def test_cron_sync_route_method_is_post(self):
        """Verifies that /cron-sync is registered strictly as a POST endpoint."""
        cron_routes = [r for r in email_router.routes if hasattr(r, "path") and r.path.endswith("/cron-sync")]
        self.assertTrue(len(cron_routes) > 0, "Route ending with /cron-sync not found on email router")
        for route in cron_routes:
            self.assertIn("POST", route.methods, "Expected POST method for /cron-sync")
            self.assertNotIn("GET", route.methods, "/cron-sync should not allow GET")

    def test_sync_inbox_automatic_retry_acknowledgement(self):
        """sync_inbox automatically identifies and retries pending acknowledgements without duplicating complaints."""
        db = TestingSessionLocal()
        import datetime
        # Seed complaint
        comp = Complaint(
            complaint_id="JS-2026-RETRY01",
            tracking_token="tok_retry_123456",
            category="Roads & Footpaths",
            description="Pothole retry test",
            status="Received"
        )
        db.add(comp)
        db.commit()

        # Seed email message with pending acknowledgement
        msg = EmailMessage(
            gmail_message_id="msg_retry_auto_001",
            gmail_thread_id="thread_retry_001",
            sender_email="citizen.retry@example.com",
            received_at=datetime.datetime.now(datetime.timezone.utc),
            processing_status="processed",
            complaint_id=comp.complaint_id,
            acknowledgement_sent=False
        )
        db.add(msg)
        db.commit()

        mock_service = MagicMock()
        mock_service.users().messages().list().execute.return_value = {"messages": []}

        with patch("app.services.email.gmail_auth.GmailAuthService.get_gmail_service", return_value=mock_service):
            with patch("app.services.email.acknowledgement_service.AcknowledgementService.send_acknowledgement", return_value=True) as mock_ack:
                res = asyncio.run(InboxMonitor.sync_inbox(db=db, max_messages=10))
                self.assertEqual(res["status"], "success")
                self.assertEqual(res["acknowledgements_retried"], 1)
                self.assertEqual(res["acknowledgements_retry_success"], 1)
                mock_ack.assert_called_once()
        db.close()

    def test_cron_sync_inbox_error_returns_500(self):
        """When InboxMonitor.sync_inbox returns status 'error', cron_sync_inbox sets response.status_code to 500."""
        db = TestingSessionLocal()
        mock_bg = MagicMock()
        mock_resp = Response()
        mock_error_result = {
            "status": "error",
            "error": "Neon PostgreSQL connection timed out during advisory lock check",
            "synced_count": 0
        }
        with patch.dict(os.environ, {"GMAIL_ENABLED": "true"}):
            with patch("app.core.config.GMAIL_ENABLED", True):
                with patch.object(InboxMonitor, "sync_inbox", return_value=mock_error_result):
                    res = asyncio.run(cron_sync_inbox(
                        background_tasks=mock_bg,
                        response=mock_resp,
                        max_messages=10,
                        db=db,
                        _authorized=True
                    ))
                    self.assertEqual(res["status"], "error")
                    self.assertEqual(mock_resp.status_code, 500)
        db.close()

    def test_failed_attachment_admin_visibility(self):
        """Failed attachment uploads in production are visible to administrators via get_authority_complaint_detail."""
        import json
        import datetime
        from app.models.authority import User
        from app.models.complaint import ComplaintEvent
        from app.routes.authority_routes import get_authority_complaint_detail

        db = TestingSessionLocal()
        cid = "JS-2026-FAILATT01"
        try:
            # Create complaint
            comp = Complaint(
                complaint_id=cid,
                tracking_token="tok_failatt_123456",
                category="Sanitation",
                description="Garbage dump with failed photo upload",
                status="Received",
                submission_channel="email"
            )
            db.add(comp)
            db.commit()

            # Create email record with failed attachment info
            failed_info = [
                {
                    "filename": "overflowing_bins.jpg",
                    "file_size": 1048576,
                    "file_type": "image/jpeg",
                    "status": "upload_failed",
                    "error": "Blob upload failed in production mode: network timeout"
                }
            ]
            msg = EmailMessage(
                gmail_message_id="msg_fail_att_001",
                gmail_thread_id="thread_fail_att_001",
                sender_email="citizen.fail@example.com",
                received_at=datetime.datetime.now(datetime.timezone.utc),
                processing_status="processed",
                complaint_id=cid,
                acknowledgement_sent=True,
                attachments_info=json.dumps(failed_info),
                error_details="Attachment processing failed for overflowing_bins.jpg"
            )
            db.add(msg)

            # Record event
            event = ComplaintEvent(
                complaint_id=cid,
                event_type="attachment_upload_failed",
                source="email_pipeline",
                description="Failed to upload attachment overflowing_bins.jpg: Blob upload failed in production mode: network timeout"
            )
            db.add(event)
            db.commit()
            db.close()

            # Query detail as admin with fresh session
            db_query = TestingSessionLocal()
            try:
                mock_admin = MagicMock(spec=User)
                mock_admin.role = "super_admin"
                mock_admin.department_id = None

                detail = asyncio.run(get_authority_complaint_detail(
                    complaint_id=cid,
                    db=db_query,
                    current_user=mock_admin
                ))

                self.assertIn("failed_evidence", detail)
                self.assertEqual(len(detail["failed_evidence"]), 1)
                failed_item = detail["failed_evidence"][0]
                self.assertEqual(failed_item["original_filename"], "overflowing_bins.jpg")
                self.assertEqual(failed_item["status"], "upload_failed")
                self.assertIn("Blob upload failed in production mode", failed_item["error"])

                # Verify evidence list is empty (failed evidence is not mixed with verified evidence)
                self.assertEqual(len(detail["evidence"]), 0)

                # Verify audit event is present
                event_types = [e["event_type"] for e in detail.get("audit_events", [])]
                self.assertIn("attachment_upload_failed", event_types)
            finally:
                db_query.close()
        finally:
            pass

if __name__ == "__main__":
    unittest.main()
