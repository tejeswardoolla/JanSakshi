import os
import sys
import unittest
import datetime
import asyncio
from unittest.mock import patch, MagicMock
from fastapi import HTTPException

# Ensure backend root is in path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.complaint import Complaint, ComplaintEvent
from app.models.email_message import EmailMessage
from app.models.authority import User
from app.services.email.acknowledgement_service import AcknowledgementService
from app.services.email.gmail_auth import GmailAuthService
from app.services.email.inbox_monitor import InboxMonitor
from app.routes.email_routes import resend_acknowledgement

# In-memory test DB
test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
Base.metadata.create_all(bind=test_engine)

class TestAcknowledgementDelivery(unittest.TestCase):
    def setUp(self):
        self.db = TestingSessionLocal()
        # Clean up any leftover records
        self.db.query(ComplaintEvent).delete()
        self.db.query(EmailMessage).delete()
        self.db.query(Complaint).delete()
        self.db.commit()

        # Create a sample complaint
        self.complaint = Complaint(
            complaint_id="JS-2026-TEST01",
            tracking_token="tok_test_1234567890abcdef",
            category="Roads & Footpaths",
            description="Massive pothole on Main Street near market",
            latitude=17.001,
            longitude=81.789,
            location_source="email_parsed",
            status="Received",
            admin_status="Received",
            citizen_name="John Doe",
        )
        self.db.add(self.complaint)
        self.db.commit()

        # Create a sample email message with required received_at
        self.email_record = EmailMessage(
            gmail_message_id="msg_gmail_incoming_001",
            gmail_thread_id="thread_001",
            sender_email="citizen.tester@example.com",
            sender_name="John Doe",
            subject="Urgent: Pothole on Main Street",
            body_plain="Please fix the pothole near market. Morampudi Junction.",
            received_at=datetime.datetime.now(datetime.timezone.utc),
            processing_status="processing",
            complaint_id=self.complaint.complaint_id,
            acknowledgement_sent=False,
            acknowledgement_sent_at=None,
            acknowledgement_message_id=None,
        )
        self.db.add(self.email_record)
        self.db.commit()

    def tearDown(self):
        self.db.rollback()
        self.db.query(ComplaintEvent).delete()
        self.db.query(EmailMessage).delete()
        self.db.query(Complaint).delete()
        self.db.commit()
        self.db.close()

    def test_send_acknowledgement_success(self):
        """When Gmail API succeeds with valid ID, marks acknowledgement as sent and records audit event."""
        mock_service = MagicMock()
        mock_send_execute = MagicMock(return_value={"id": "gmail_msg_ack_999001", "threadId": "thread_001"})
        mock_service.users().messages().send().execute = mock_send_execute

        with patch.object(GmailAuthService, "get_gmail_service", return_value=mock_service):
            with patch.object(GmailAuthService, "get_mailbox_profile", return_value={"email_address": "jansakshiofficial@gmail.com"}):
                result = AcknowledgementService.send_acknowledgement(
                    db=self.db,
                    complaint=self.complaint,
                    email_record=self.email_record
                )

                self.assertTrue(result)
                self.assertTrue(self.email_record.acknowledgement_sent)
                self.assertIsNotNone(self.email_record.acknowledgement_sent_at)
                self.assertEqual(self.email_record.acknowledgement_message_id, "gmail_msg_ack_999001")
                self.assertIsNone(self.email_record.error_details)

                # Verify audit event strictly created
                event = self.db.query(ComplaintEvent).filter(
                    ComplaintEvent.complaint_id == self.complaint.complaint_id,
                    ComplaintEvent.event_type == "acknowledgement_email_dispatched"
                ).first()
                self.assertIsNotNone(event)
                self.assertEqual(event.new_value, "citizen.tester@example.com")

    def test_send_acknowledgement_service_unavailable(self):
        """When Gmail service is disconnected, returns False, keeps acknowledgement_sent=False, no simulated ID, no audit event."""
        with patch.object(GmailAuthService, "get_gmail_service", return_value=None):
            result = AcknowledgementService.send_acknowledgement(
                db=self.db,
                complaint=self.complaint,
                email_record=self.email_record
            )

            self.assertFalse(result)
            self.assertFalse(self.email_record.acknowledgement_sent)
            self.assertIsNone(self.email_record.acknowledgement_sent_at)
            self.assertIsNone(self.email_record.acknowledgement_message_id)
            self.assertIn("Gmail service unavailable", self.email_record.error_details)

            # Verify NO audit event created
            events = self.db.query(ComplaintEvent).filter(
                ComplaintEvent.complaint_id == self.complaint.complaint_id,
                ComplaintEvent.event_type == "acknowledgement_email_dispatched"
            ).all()
            self.assertEqual(len(events), 0)

    def test_send_acknowledgement_api_failure(self):
        """When Gmail API call raises an exception, returns False, keeps acknowledgement_sent=False, records error details."""
        mock_service = MagicMock()
        mock_service.users().messages().send().execute.side_effect = Exception("503 Service Unavailable: Backend Error")

        with patch.object(GmailAuthService, "get_gmail_service", return_value=mock_service):
            with patch.object(GmailAuthService, "get_mailbox_profile", return_value={"email_address": "jansakshiofficial@gmail.com"}):
                result = AcknowledgementService.send_acknowledgement(
                    db=self.db,
                    complaint=self.complaint,
                    email_record=self.email_record
                )

                self.assertFalse(result)
                self.assertFalse(self.email_record.acknowledgement_sent)
                self.assertIsNone(self.email_record.acknowledgement_sent_at)
                self.assertIsNone(self.email_record.acknowledgement_message_id)
                self.assertIn("503 Service Unavailable", self.email_record.error_details)

                # Verify NO audit event created
                events = self.db.query(ComplaintEvent).filter(
                    ComplaintEvent.complaint_id == self.complaint.complaint_id,
                    ComplaintEvent.event_type == "acknowledgement_email_dispatched"
                ).all()
                self.assertEqual(len(events), 0)

    def test_send_acknowledgement_api_returns_no_id(self):
        """When Gmail API returns response without message ID, treated as failure."""
        mock_service = MagicMock()
        mock_service.users().messages().send().execute.return_value = {"threadId": "123"}  # missing 'id'

        with patch.object(GmailAuthService, "get_gmail_service", return_value=mock_service):
            with patch.object(GmailAuthService, "get_mailbox_profile", return_value={"email_address": "jansakshiofficial@gmail.com"}):
                result = AcknowledgementService.send_acknowledgement(
                    db=self.db,
                    complaint=self.complaint,
                    email_record=self.email_record
                )

                self.assertFalse(result)
                self.assertFalse(self.email_record.acknowledgement_sent)
                self.assertIsNone(self.email_record.acknowledgement_sent_at)
                self.assertIsNone(self.email_record.acknowledgement_message_id)
                self.assertIn("no message ID", self.email_record.error_details)

    def test_send_acknowledgement_retry_after_failure(self):
        """When a previously failed acknowledgement is retried after Gmail is available, it succeeds and clears send error."""
        # Step 1: Initial failure
        with patch.object(GmailAuthService, "get_gmail_service", return_value=None):
            failed_res = AcknowledgementService.send_acknowledgement(
                db=self.db,
                complaint=self.complaint,
                email_record=self.email_record
            )
            self.assertFalse(failed_res)
            self.assertFalse(self.email_record.acknowledgement_sent)
            self.assertIn("Gmail service unavailable", self.email_record.error_details)

        # Step 2: Retry with working service
        mock_service = MagicMock()
        mock_service.users().messages().send().execute.return_value = {"id": "gmail_msg_ack_retry_success_456"}

        with patch.object(GmailAuthService, "get_gmail_service", return_value=mock_service):
            with patch.object(GmailAuthService, "get_mailbox_profile", return_value={"email_address": "jansakshiofficial@gmail.com"}):
                retry_res = AcknowledgementService.send_acknowledgement(
                    db=self.db,
                    complaint=self.complaint,
                    email_record=self.email_record
                )

                self.assertTrue(retry_res)
                self.assertTrue(self.email_record.acknowledgement_sent)
                self.assertIsNotNone(self.email_record.acknowledgement_sent_at)
                self.assertEqual(self.email_record.acknowledgement_message_id, "gmail_msg_ack_retry_success_456")
                self.assertIsNone(self.email_record.error_details)

                # Verify audit event strictly created upon retry success
                event = self.db.query(ComplaintEvent).filter(
                    ComplaintEvent.complaint_id == self.complaint.complaint_id,
                    ComplaintEvent.event_type == "acknowledgement_email_dispatched"
                ).first()
                self.assertIsNotNone(event)

    def test_send_acknowledgement_idempotency_when_already_sent(self):
        """When acknowledgement_sent is already True, send_acknowledgement returns True immediately without calling Gmail."""
        self.email_record.acknowledgement_sent = True
        self.email_record.acknowledgement_message_id = "existing_id_777"
        self.db.commit()

        with patch.object(GmailAuthService, "get_gmail_service") as mock_get_svc:
            res = AcknowledgementService.send_acknowledgement(
                db=self.db,
                complaint=self.complaint,
                email_record=self.email_record
            )
            self.assertTrue(res)
            mock_get_svc.assert_not_called()

    def test_resend_acknowledgement_endpoint_success(self):
        """Admin resend-acknowledgement endpoint triggers send_acknowledgement and returns 200 on success."""
        mock_admin = User(id=1, username="admin", email="admin@test.gov.in", role="admin")
        mock_service = MagicMock()
        mock_service.users().messages().send().execute.return_value = {"id": "gmail_msg_resend_101"}

        with patch.object(GmailAuthService, "get_gmail_service", return_value=mock_service):
            with patch.object(GmailAuthService, "get_mailbox_profile", return_value={"email_address": "jansakshiofficial@gmail.com"}):
                res = asyncio.run(resend_acknowledgement(
                    message_id=self.email_record.id,
                    db=self.db,
                    current_user=mock_admin
                ))
                self.assertEqual(res["status"], "success")
                self.assertEqual(res["acknowledgement_message_id"], "gmail_msg_resend_101")
                self.assertTrue(self.email_record.acknowledgement_sent)

    def test_resend_acknowledgement_endpoint_service_unavailable(self):
        """Admin resend-acknowledgement endpoint raises 502 Bad Gateway if Gmail service is disconnected."""
        mock_admin = User(id=1, username="admin", email="admin@test.gov.in", role="admin")

        with patch.object(GmailAuthService, "get_gmail_service", return_value=None):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(resend_acknowledgement(
                    message_id=self.email_record.id,
                    db=self.db,
                    current_user=mock_admin
                ))
            self.assertEqual(ctx.exception.status_code, 502)
            self.assertIn("Failed to dispatch acknowledgement", ctx.exception.detail)
            self.assertFalse(self.email_record.acknowledgement_sent)

    def test_backoff_delay_enforcement(self):
        """sync_inbox skips retrying a message if the required exponential backoff delay has not elapsed."""
        now = datetime.datetime.now(datetime.timezone.utc)
        # Attempt 1 retry (retry_count=1) requires 300s (5m), attempt 2 retry (retry_count=2) requires 900s (15m).
        # Set retry_count = 1, last_retry_at = 60s ago (< 300s)
        self.email_record.acknowledgement_retry_count = 1
        self.email_record.acknowledgement_last_retry_at = now - datetime.timedelta(seconds=60)
        self.email_record.processing_status = "processed"
        self.db.commit()

        mock_service = MagicMock()
        mock_service.users().messages().list().execute.return_value = {"messages": []}

        with patch.object(GmailAuthService, "get_gmail_service", return_value=mock_service):
            with patch.object(AcknowledgementService, "send_acknowledgement") as mock_ack:
                res = asyncio.run(InboxMonitor.sync_inbox(db=self.db, max_messages=10))
                self.assertEqual(res["status"], "success")
                self.assertEqual(res["acknowledgements_retried"], 0)
                mock_ack.assert_not_called()

        # Now simulate 350s elapsed (> 300s): should be retried
        self.email_record.acknowledgement_last_retry_at = now - datetime.timedelta(seconds=350)
        self.db.commit()

        with patch.object(GmailAuthService, "get_gmail_service", return_value=mock_service):
            with patch.object(AcknowledgementService, "send_acknowledgement", return_value=True) as mock_ack:
                res = asyncio.run(InboxMonitor.sync_inbox(db=self.db, max_messages=10))
                self.assertEqual(res["status"], "success")
                self.assertEqual(res["acknowledgements_retried"], 1)
                self.assertEqual(res["acknowledgements_retry_success"], 1)
                mock_ack.assert_called_once()

    def test_max_retry_bound(self):
        """sync_inbox permanently skips messages that have reached or exceeded MAX_AUTOMATIC_ACK_RETRIES (5)."""
        now = datetime.datetime.now(datetime.timezone.utc)
        self.email_record.acknowledgement_retry_count = 5
        self.email_record.acknowledgement_last_retry_at = now - datetime.timedelta(days=2)
        self.email_record.processing_status = "processed"
        self.db.commit()

        mock_service = MagicMock()
        mock_service.users().messages().list().execute.return_value = {"messages": []}

        with patch.object(GmailAuthService, "get_gmail_service", return_value=mock_service):
            with patch.object(AcknowledgementService, "send_acknowledgement") as mock_ack:
                res = asyncio.run(InboxMonitor.sync_inbox(db=self.db, max_messages=10))
                self.assertEqual(res["status"], "success")
                self.assertEqual(res["acknowledgements_retried"], 0)
                mock_ack.assert_not_called()

    def test_fair_queue_ordering(self):
        """Pending acknowledgements are ordered by acknowledgement_last_retry_at ASC NULLS FIRST, id ASC to prevent starvation."""
        now = datetime.datetime.now(datetime.timezone.utc)
        # Msg A: retry_count=1, last_retry = 2 hours ago
        msg_a = self.email_record
        msg_a.acknowledgement_retry_count = 1
        msg_a.acknowledgement_last_retry_at = now - datetime.timedelta(hours=2)

        # Msg B: retry_count=0, last_retry = None (never attempted)
        msg_b = EmailMessage(
            gmail_message_id="msg_b_null_last_try",
            gmail_thread_id="thread_b",
            sender_email="b@example.com",
            received_at=now,
            processing_status="processed",
            complaint_id=self.complaint.complaint_id,
            acknowledgement_sent=False,
            acknowledgement_retry_count=0,
            acknowledgement_last_retry_at=None
        )
        # Msg C: retry_count=2, last_retry = 10 hours ago (oldest attempted)
        msg_c = EmailMessage(
            gmail_message_id="msg_c_oldest_try",
            gmail_thread_id="thread_c",
            sender_email="c@example.com",
            received_at=now,
            processing_status="processed",
            complaint_id=self.complaint.complaint_id,
            acknowledgement_sent=False,
            acknowledgement_retry_count=2,
            acknowledgement_last_retry_at=now - datetime.timedelta(hours=10)
        )
        self.db.add_all([msg_b, msg_c])
        self.db.commit()

        # Query candidate order using the exact ordering specified in inbox_monitor
        candidates = self.db.query(EmailMessage).filter(
            EmailMessage.complaint_id != None,
            EmailMessage.acknowledgement_sent == False,
            EmailMessage.acknowledgement_retry_count < 5
        ).order_by(
            EmailMessage.acknowledgement_last_retry_at.asc().nullsfirst(),
            EmailMessage.id.asc()
        ).all()

        # Expected order: msg_b (nullsfirst), msg_c (10h ago), msg_a (2h ago)
        candidate_ids = [m.gmail_message_id for m in candidates]
        self.assertEqual(candidate_ids, ["msg_b_null_last_try", "msg_c_oldest_try", "msg_gmail_incoming_001"])

    def test_queue_fairness_eligible_beyond_ten_ineligible_candidates(self):
        """Proves that a block of 10 ineligible candidates with active backoff delays does NOT starve the 11th eligible candidate."""
        now = datetime.datetime.now(datetime.timezone.utc)
        # Clear existing email records
        self.db.query(EmailMessage).delete()
        self.db.commit()

        # Seed 10 ineligible candidates (retry_count=4, requiring 10800s delay = 3 hours; last attempted 1 hour ago)
        ineligible_records = []
        for i in range(10):
            msg = EmailMessage(
                gmail_message_id=f"msg_ineligible_{i:03d}",
                gmail_thread_id=f"thread_ineligible_{i:03d}",
                sender_email=f"citizen_{i}@example.com",
                received_at=now - datetime.timedelta(days=1),
                processing_status="processed",
                complaint_id=self.complaint.complaint_id,
                acknowledgement_sent=False,
                acknowledgement_retry_count=4,
                acknowledgement_last_retry_at=now - datetime.timedelta(hours=1)  # only 1 hr elapsed < 3 hrs
            )
            ineligible_records.append(msg)
        self.db.add_all(ineligible_records)
        self.db.commit()

        # Seed the 11th record: ELIGIBLE (retry_count=1, requiring 300s = 5m delay; last attempted 15m ago)
        eligible_msg = EmailMessage(
            gmail_message_id="msg_eligible_eleventh",
            gmail_thread_id="thread_eligible_eleventh",
            sender_email="citizen.eleventh@example.com",
            received_at=now - datetime.timedelta(hours=2),
            processing_status="processed",
            complaint_id=self.complaint.complaint_id,
            acknowledgement_sent=False,
            acknowledgement_retry_count=1,
            acknowledgement_last_retry_at=now - datetime.timedelta(minutes=15)  # 15m elapsed > 5m
        )
        self.db.add(eligible_msg)
        self.db.commit()

        mock_service = MagicMock()
        mock_service.users().messages().list().execute.return_value = {"messages": []}

        with patch.object(GmailAuthService, "get_gmail_service", return_value=mock_service):
            with patch.object(AcknowledgementService, "send_acknowledgement", return_value=True) as mock_ack:
                res = asyncio.run(InboxMonitor.sync_inbox(db=self.db, max_messages=10))
                self.assertEqual(res["status"], "success")
                # Confirms the 11th record was evaluated and retried successfully despite the 10 preceding ineligible records
                self.assertEqual(res["acknowledgements_retried"], 1)
                self.assertEqual(res["acknowledgements_retry_success"], 1)
                self.assertEqual(mock_ack.call_args[1]["email_record"].gmail_message_id, "msg_eligible_eleventh")

    def test_ambiguous_timeout_recovery(self):
        """When acknowledgement was already delivered in thread (e.g. timeout on previous attempt), recovers sent ID without resending."""
        mock_service = MagicMock()
        mock_thread_data = {
            "id": "thread_001",
            "messages": [
                {
                    "id": "msg_gmail_incoming_001",
                    "labelIds": ["INBOX"],
                    "payload": {
                        "headers": [
                            {"name": "Subject", "value": "Urgent: Pothole on Main Street"},
                            {"name": "To", "value": "jansakshiofficial@gmail.com"},
                            {"name": "From", "value": "citizen.tester@example.com"}
                        ]
                    }
                },
                {
                    "id": "msg_ack_previously_delivered_999",
                    "labelIds": ["SENT"],
                    "payload": {
                        "headers": [
                            {"name": "Subject", "value": f"JanSakshi Grievance Acknowledged — [{self.complaint.complaint_id}]"},
                            {"name": "To", "value": "citizen.tester@example.com"},
                            {"name": "From", "value": "jansakshiofficial@gmail.com"}
                        ]
                    }
                }
            ]
        }
        mock_service.users().threads().get().execute.return_value = mock_thread_data

        with patch.object(GmailAuthService, "get_gmail_service", return_value=mock_service):
            with patch.object(GmailAuthService, "get_mailbox_profile", return_value={"email_address": "jansakshiofficial@gmail.com"}):
                result = AcknowledgementService.send_acknowledgement(
                    db=self.db,
                    complaint=self.complaint,
                    email_record=self.email_record
                )

                self.assertTrue(result)
                self.assertTrue(self.email_record.acknowledgement_sent)
                self.assertEqual(self.email_record.acknowledgement_message_id, "msg_ack_previously_delivered_999")
                # Ensure messages().send() was NOT called because thread already had the sent message
                mock_service.users().messages().send.assert_not_called()

                # Verify audit event recorded
                event = self.db.query(ComplaintEvent).filter(
                    ComplaintEvent.complaint_id == self.complaint.complaint_id,
                    ComplaintEvent.event_type == "acknowledgement_email_dispatched"
                ).first()
                self.assertIsNotNone(event)

    def test_thread_recovery_ignores_citizen_incoming_reply(self):
        """Incoming citizen reply mentioning complaint ID without SENT label is NOT treated as an acknowledgement."""
        mock_service = MagicMock()
        mock_thread_data = {
            "id": "thread_001",
            "messages": [
                {
                    "id": "msg_gmail_incoming_001",
                    "labelIds": ["INBOX"],
                    "payload": {
                        "headers": [
                            {"name": "Subject", "value": "Urgent: Pothole on Main Street"},
                            {"name": "To", "value": "jansakshiofficial@gmail.com"},
                            {"name": "From", "value": "citizen.tester@example.com"}
                        ]
                    }
                },
                {
                    "id": "msg_citizen_reply_002",
                    "labelIds": ["INBOX"],  # NOT SENT!
                    "payload": {
                        "headers": [
                            {"name": "Subject", "value": f"Re: [{self.complaint.complaint_id}] Still no action taken"},
                            {"name": "To", "value": "jansakshiofficial@gmail.com"},
                            {"name": "From", "value": "citizen.tester@example.com"}
                        ]
                    }
                }
            ]
        }
        mock_service.users().threads().get().execute.return_value = mock_thread_data
        mock_send = MagicMock()
        mock_send.return_value.execute.return_value = {"id": "gmail_msg_actual_send_111"}
        mock_service.users().messages().send = mock_send

        with patch.object(GmailAuthService, "get_gmail_service", return_value=mock_service):
            with patch.object(GmailAuthService, "get_mailbox_profile", return_value={"email_address": "jansakshiofficial@gmail.com"}):
                result = AcknowledgementService.send_acknowledgement(
                    db=self.db,
                    complaint=self.complaint,
                    email_record=self.email_record
                )

                self.assertTrue(result)
                self.assertTrue(self.email_record.acknowledgement_sent)
                # Ensure it called messages().send() and DID NOT adopt the citizen's incoming message ID
                mock_send.assert_called_once()
                self.assertEqual(self.email_record.acknowledgement_message_id, "gmail_msg_actual_send_111")

    def test_thread_recovery_ignores_message_to_different_recipient(self):
        """Outbound message in thread sent to a different recipient is NOT treated as an acknowledgement for this citizen."""
        mock_service = MagicMock()
        mock_thread_data = {
            "id": "thread_001",
            "messages": [
                {
                    "id": "msg_unrelated_recipient_003",
                    "labelIds": ["SENT"],
                    "payload": {
                        "headers": [
                            {"name": "Subject", "value": f"Notification [{self.complaint.complaint_id}]"},
                            {"name": "To", "value": "officer.roads@rajahmundry.gov.in"},  # Unrelated recipient!
                            {"name": "From", "value": "jansakshiofficial@gmail.com"}
                        ]
                    }
                }
            ]
        }
        mock_service.users().threads().get().execute.return_value = mock_thread_data
        mock_send = MagicMock()
        mock_send.return_value.execute.return_value = {"id": "gmail_msg_actual_send_222"}
        mock_service.users().messages().send = mock_send

        with patch.object(GmailAuthService, "get_gmail_service", return_value=mock_service):
            with patch.object(GmailAuthService, "get_mailbox_profile", return_value={"email_address": "jansakshiofficial@gmail.com"}):
                result = AcknowledgementService.send_acknowledgement(
                    db=self.db,
                    complaint=self.complaint,
                    email_record=self.email_record
                )

                self.assertTrue(result)
                self.assertTrue(self.email_record.acknowledgement_sent)
                # Ensure actual send executed because recipient did not match citizen
                mock_send.assert_called_once()
                self.assertEqual(self.email_record.acknowledgement_message_id, "gmail_msg_actual_send_222")

    def test_manual_admin_retry_bypasses_max_retry_limit(self):
        """Admin manual resend with force_retry=True succeeds even when message reached max automatic retry limit (5)."""
        mock_admin = User(id=1, username="admin", email="admin@test.gov.in", role="admin")
        self.email_record.acknowledgement_retry_count = 5
        self.email_record.acknowledgement_sent = False
        self.db.commit()

        mock_service = MagicMock()
        mock_service.users().threads().get().execute.return_value = {"messages": []}
        mock_service.users().messages().send().execute.return_value = {"id": "gmail_msg_force_retry_success_888"}

        with patch.object(GmailAuthService, "get_gmail_service", return_value=mock_service):
            with patch.object(GmailAuthService, "get_mailbox_profile", return_value={"email_address": "jansakshiofficial@gmail.com"}):
                res = asyncio.run(resend_acknowledgement(
                    message_id=self.email_record.id,
                    force_retry=True,
                    db=self.db,
                    current_user=mock_admin
                ))
                self.assertEqual(res["status"], "success")
                self.assertEqual(res["acknowledgement_message_id"], "gmail_msg_force_retry_success_888")
                self.assertTrue(self.email_record.acknowledgement_sent)
                self.assertEqual(self.email_record.acknowledgement_message_id, "gmail_msg_force_retry_success_888")

    def test_retry_counters_incremented_and_persisted_on_api_failure(self):
        """Proves acknowledgement_retry_count and acknowledgement_last_retry_at are incremented and persisted on API error."""
        self.email_record.acknowledgement_retry_count = 0
        self.email_record.acknowledgement_last_retry_at = None
        self.db.commit()

        mock_service = MagicMock()
        mock_service.users().threads().get().execute.return_value = {"messages": []}
        mock_service.users().messages().send().execute.side_effect = Exception("500 Internal Server Error")

        with patch.object(GmailAuthService, "get_gmail_service", return_value=mock_service):
            with patch.object(GmailAuthService, "get_mailbox_profile", return_value={"email_address": "jansakshiofficial@gmail.com"}):
                # Attempt 1
                res1 = AcknowledgementService.send_acknowledgement(
                    db=self.db,
                    complaint=self.complaint,
                    email_record=self.email_record
                )
                self.assertFalse(res1)
                self.db.refresh(self.email_record)
                self.assertEqual(self.email_record.acknowledgement_retry_count, 1)
                self.assertIsNotNone(self.email_record.acknowledgement_last_retry_at)
                first_attempt_time = self.email_record.acknowledgement_last_retry_at
                self.assertFalse(self.email_record.acknowledgement_sent)

                # Attempt 2
                res2 = AcknowledgementService.send_acknowledgement(
                    db=self.db,
                    complaint=self.complaint,
                    email_record=self.email_record
                )
                self.assertFalse(res2)
                self.db.refresh(self.email_record)
                self.assertEqual(self.email_record.acknowledgement_retry_count, 2)
                self.assertGreaterEqual(self.email_record.acknowledgement_last_retry_at, first_attempt_time)
                self.assertFalse(self.email_record.acknowledgement_sent)

    def test_retry_counters_incremented_and_persisted_on_disconnected_gmail(self):
        """Proves retry count and timestamp are incremented and persisted even when Gmail is disconnected."""
        self.email_record.acknowledgement_retry_count = 1
        self.email_record.acknowledgement_last_retry_at = None
        self.db.commit()

        with patch.object(GmailAuthService, "get_gmail_service", return_value=None):
            res = AcknowledgementService.send_acknowledgement(
                db=self.db,
                complaint=self.complaint,
                email_record=self.email_record
            )
            self.assertFalse(res)
            self.db.refresh(self.email_record)
            self.assertEqual(self.email_record.acknowledgement_retry_count, 2)
            self.assertIsNotNone(self.email_record.acknowledgement_last_retry_at)
            self.assertFalse(self.email_record.acknowledgement_sent)

    def test_successful_send_does_not_increment_retry_count(self):
        """Proves successful sends do not count as failures: retry_count is not incremented and acknowledgement_sent is True."""
        self.email_record.acknowledgement_retry_count = 2
        self.email_record.acknowledgement_sent = False
        self.db.commit()

        mock_service = MagicMock()
        mock_service.users().threads().get().execute.return_value = {"messages": []}
        mock_service.users().messages().send().execute.return_value = {"id": "gmail_msg_success_999"}

        with patch.object(GmailAuthService, "get_gmail_service", return_value=mock_service):
            with patch.object(GmailAuthService, "get_mailbox_profile", return_value={"email_address": "jansakshiofficial@gmail.com"}):
                res = AcknowledgementService.send_acknowledgement(
                    db=self.db,
                    complaint=self.complaint,
                    email_record=self.email_record
                )
                self.assertTrue(res)
                self.db.refresh(self.email_record)
                # Successful automatic retry preserves retry_count (does not increment to 3)
                self.assertEqual(self.email_record.acknowledgement_retry_count, 2)
                self.assertTrue(self.email_record.acknowledgement_sent)
                self.assertEqual(self.email_record.acknowledgement_message_id, "gmail_msg_success_999")
                self.assertIsNotNone(self.email_record.acknowledgement_last_retry_at)

    def test_automatic_retry_loop_persists_retry_state_in_sync_inbox(self):
        """Integration test: InboxMonitor.sync_inbox automatic retry persists incremented retry count on failure."""
        now = datetime.datetime.now(datetime.timezone.utc)
        self.email_record.acknowledgement_retry_count = 0
        self.email_record.acknowledgement_last_retry_at = None
        self.email_record.processing_status = "processed"
        self.email_record.acknowledgement_sent = False
        self.db.commit()

        mock_service = MagicMock()
        mock_service.users().messages().list().execute.return_value = {"messages": []}
        mock_service.users().threads().get().execute.return_value = {"messages": []}
        mock_service.users().messages().send().execute.side_effect = Exception("503 Service Unavailable")

        with patch.object(GmailAuthService, "get_gmail_service", return_value=mock_service):
            with patch.object(GmailAuthService, "get_mailbox_profile", return_value={"email_address": "jansakshiofficial@gmail.com"}):
                res = asyncio.run(InboxMonitor.sync_inbox(db=self.db, max_messages=10))
                self.assertEqual(res["status"], "success")
                self.assertEqual(res["acknowledgements_retried"], 1)
                self.assertEqual(res["acknowledgements_retry_success"], 0)

                # Verify persistence in database
                self.db.refresh(self.email_record)
                self.assertEqual(self.email_record.acknowledgement_retry_count, 1)
                self.assertIsNotNone(self.email_record.acknowledgement_last_retry_at)
                self.assertFalse(self.email_record.acknowledgement_sent)

if __name__ == "__main__":
    unittest.main()
