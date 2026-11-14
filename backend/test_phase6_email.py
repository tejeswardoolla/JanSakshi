"""
JanSakshi Phase 6 Automated Verification Suite
Tests the Gmail AI Integration, Unified Email Complaint Processing Pipeline,
Gemini Extraction, Attachment Handling, Duplicate Protection, and Follow-Up Workflows.
"""

import sys
import os
import asyncio
import requests
from datetime import datetime, timezone

BACKEND_URL = "http://127.0.0.1:8000"

def log(msg: str):
    print(f"[TEST] {msg}", flush=True)

def assert_true(cond: bool, msg: str):
    if not cond:
        print(f"❌ ASSERTION FAILED: {msg}", flush=True)
        sys.exit(1)
    print(f"✅ {msg}", flush=True)

async def run_async_tests():
    log("Starting Phase 6 Gmail AI Integration Verification...")

    # 1. Health check
    res = requests.get(f"{BACKEND_URL}/api/health")
    assert_true(res.status_code == 200, "Backend health endpoint returns 200")
    data = res.json()
    assert_true(data.get("phase") == 6, f"Backend version is Phase 6 (got {data.get('phase')})")

    # 2. Email status endpoint check
    res_status = requests.get(f"{BACKEND_URL}/api/email/status")
    assert_true(res_status.status_code == 200, "Email status endpoint returns 200")
    status_data = res_status.json()
    assert_true("configured" in status_data and "authenticated" in status_data, "Status payload contains configured/authenticated flags")
    log(f"Initial mailbox status: {status_data['status']} ({status_data['message']})")

    # 3. Unit Test: Attachment Processor Validation & Sanitization
    from app.services.email.attachment_processor import AttachmentProcessor, sanitize_filename

    assert_true(sanitize_filename("../../etc/passwd.jpg") == "passwd.jpg", "Path traversal sanitized from filename")
    
    # Reject dangerous executable
    exe_result = AttachmentProcessor.process_attachment("virus.exe", b"MZfakebinarycontent", "application/x-dosexec")
    assert_true(exe_result is None, "Dangerous executable attachment (.exe) strictly rejected")

    # Accept valid image
    # Minimal 1x1 valid PNG bytes
    valid_png_bytes = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
    img_result = AttachmentProcessor.process_attachment("citizen_pothole_photo.png", valid_png_bytes, "image/png")
    assert_true(img_result is not None, "Valid PNG evidence attachment accepted and persisted")
    assert_true(os.path.exists(img_result["storage_path"]), "Evidence file written to storage directory")

    # 4. Unit Test: Gemini Email Extractor (Civic Complaint vs Non-Civic)
    from app.services.email.gemini_email_extractor import GeminiEmailExtractor

    # Civic Complaint with Coordinates
    civic_email = await GeminiEmailExtractor.extract(
        subject="Dangerous pothole near Morampudi Junction",
        body="There is a very deep pothole causing vehicle accidents at coordinates 17.3850, 78.4867. Please repair urgently."
    )
    assert_true(civic_email.is_civic_complaint is True, "Civic complaint classified as genuine civic issue")
    assert_true(civic_email.category == "Road Damage / Potholes", f"Category extracted: {civic_email.category}")
    assert_true(civic_email.latitude is not None and abs(civic_email.latitude - 17.3850) < 0.01, f"Explicit latitude extracted: {civic_email.latitude}")
    assert_true(civic_email.longitude is not None and abs(civic_email.longitude - 78.4867) < 0.01, f"Explicit longitude extracted: {civic_email.longitude}")

    # Civic Complaint with Missing Location (No coordinates)
    missing_loc_email = await GeminiEmailExtractor.extract(
        subject="Broken streetlight fixture",
        body="The streetlight fixture on our street has shattered and is not turning on at night. It is completely dark."
    )
    assert_true(missing_loc_email.is_civic_complaint is True, "Streetlight email classified as civic issue")
    assert_true(missing_loc_email.category == "Broken Streetlights", f"Category extracted: {missing_loc_email.category}")
    assert_true(missing_loc_email.latitude is None and missing_loc_email.longitude is None, "Missing coordinates left as None without hallucination")
    assert_true("location_coordinates" in missing_loc_email.missing_information, "Missing location flagged in missing_information")

    # Non-Civic Email (Promotional / Spam)
    spam_email = await GeminiEmailExtractor.extract(
        subject="Exclusive 50% discount on shoes this weekend!",
        body="Unsubscribe at any time. Get the best discount on your order with promo code SALE50."
    )
    assert_true(spam_email.is_civic_complaint is False, "Promotional email classified as non-civic")

    # 5. Pipeline Test: Ingest Email via EmailComplaintProcessor
    from app.database import SessionLocal
    from app.models.complaint import Complaint, ComplaintEvent
    from app.models.email_message import EmailMessage
    from app.services.email.email_complaint_processor import EmailComplaintProcessor

    db = SessionLocal()
    try:
        # Scenario A: New Email Complaint Ingestion with Coordinates and Attachment
        msg_id_1 = f"mock_gmail_msg_{datetime.now(timezone.utc).timestamp()}_1"
        raw_msg_1 = {
            "gmail_message_id": msg_id_1,
            "gmail_thread_id": f"thread_{msg_id_1}",
            "sender_email": "citizen.tester@example.com",
            "sender_name": "Ravi Kumar",
            "subject": "Deep road crater at Main Street",
            "snippet": "Severe pothole at 17.4375, 78.4482",
            "body_plain": "There is a severe pothole at 17.4375, 78.4482 right in the middle of the road. Vehicles are damaged daily.",
            "received_at": datetime.now(timezone.utc),
            "attachments": [{
                "filename": "pothole_evidence.png",
                "data": valid_png_bytes,
                "mime_type": "image/png"
            }]
        }

        result1 = await EmailComplaintProcessor.process_raw_email(db, raw_msg_1)
        assert_true(result1["status"] == "success", f"Email processed successfully into complaint: {result1}")
        complaint_id_1 = result1["complaint_id"]
        assert_true(complaint_id_1.startswith("JS-"), f"Unique JS reference ID generated: {complaint_id_1}")

        # Verify Complaint in Database
        db.expire_all()
        comp1 = db.query(Complaint).filter(Complaint.complaint_id == complaint_id_1).first()
        assert_true(comp1 is not None, "Complaint record found in database")
        assert_true(comp1.submission_channel == "email", f"Submission channel recorded as email: {comp1.submission_channel}")
        assert_true(comp1.citizen_email == "citizen.tester@example.com", "Citizen email saved securely")
        assert_true(len(comp1.evidence_files) == 1, f"Attached evidence linked ({len(comp1.evidence_files)} files)")

        # Verify EmailMessage record
        email_row_1 = db.query(EmailMessage).filter(EmailMessage.gmail_message_id == msg_id_1).first()
        assert_true(email_row_1 is not None, "EmailMessage record saved")
        assert_true(email_row_1.processing_status == "processed", f"Status is processed: {email_row_1.processing_status}")
        assert_true(email_row_1.acknowledgement_sent is True, "Acknowledgement email logged as sent")

        # Scenario B: Strict Duplicate Prevention Check
        log("Testing duplicate prevention with identical gmail_message_id...")
        result_dup = await EmailComplaintProcessor.process_raw_email(db, raw_msg_1)
        assert_true(result_dup["status"] == "already_processed", f"Duplicate email prevented: {result_dup['status']}")
        assert_true(result_dup["complaint_id"] == complaint_id_1, "Duplicate returns existing complaint ID without creating a new one")

        # Scenario C: Ingestion of Email with Missing Location
        msg_id_2 = f"mock_gmail_msg_{datetime.now(timezone.utc).timestamp()}_2"
        raw_msg_2 = {
            "gmail_message_id": msg_id_2,
            "gmail_thread_id": f"thread_{msg_id_2}",
            "sender_email": "citizen2@example.com",
            "sender_name": "Priya Sharma",
            "subject": "Overflowing garbage dump in colony",
            "snippet": "Garbage has not been collected for a week",
            "body_plain": "Huge garbage accumulation near the local colony entrance. Rotten smell and stray animals.",
            "received_at": datetime.now(timezone.utc),
            "attachments": []
        }

        result2 = await EmailComplaintProcessor.process_raw_email(db, raw_msg_2)
        assert_true(result2["status"] == "success", "Complaint with missing location registered successfully")
        complaint_id_2 = result2["complaint_id"]
        assert_true(result2["location_status"] == "awaiting_clarification", "Location status is awaiting_clarification")

        db.expire_all()
        comp2 = db.query(Complaint).filter(Complaint.complaint_id == complaint_id_2).first()
        assert_true(comp2.status == "Awaiting Location", f"Complaint status is Awaiting Location (got {comp2.status})")
        assert_true(comp2.latitude is None and comp2.longitude is None, "Coordinates are None without inventing false GPS data")

        # Scenario D: Follow-Up Location Clarification Email
        log("Testing follow-up email providing location clarification...")
        msg_id_followup = f"mock_gmail_msg_{datetime.now(timezone.utc).timestamp()}_followup"
        raw_msg_followup = {
            "gmail_message_id": msg_id_followup,
            "gmail_thread_id": f"thread_{msg_id_2}", # Same thread as complaint 2
            "sender_email": "citizen2@example.com",
            "sender_name": "Priya Sharma",
            "subject": f"Re: JanSakshi Complaint Registered – {complaint_id_2}",
            "snippet": "The garbage dump location is at 17.0005, 81.8040",
            "body_plain": f"In response to your query regarding {complaint_id_2}, the garbage dump is located at 17.0005, 81.8040 near the vegetable market.",
            "received_at": datetime.now(timezone.utc),
            "attachments": []
        }

        result_followup = await EmailComplaintProcessor.process_raw_email(db, raw_msg_followup)
        assert_true(result_followup["status"] == "follow_up_processed", f"Follow-up recognized and processed: {result_followup['status']}")
        assert_true(result_followup["complaint_id"] == complaint_id_2, "Follow-up linked to existing complaint without creating a new record")

        # Verify Complaint 2 is now updated with location
        db.expire_all()
        comp2_updated = db.query(Complaint).filter(Complaint.complaint_id == complaint_id_2).first()
        assert_true(comp2_updated.latitude is not None and abs(comp2_updated.latitude - 17.0005) < 0.01, f"Latitude updated to {comp2_updated.latitude}")
        assert_true(comp2_updated.status == "Received", f"Status updated to Received: {comp2_updated.status}")
        assert_true(comp2_updated.location_source == "email_follow_up", "Location source marked as email_follow_up")

        # Verify ComplaintEvent for clarification
        clarification_event = db.query(ComplaintEvent).filter(
            ComplaintEvent.complaint_id == complaint_id_2,
            ComplaintEvent.event_type == "location_clarification_provided"
        ).first()
        assert_true(clarification_event is not None, "Location clarification audit event recorded in complaint history")

        # Scenario E: Non-Civic Email Ignored
        msg_id_spam = f"mock_gmail_msg_{datetime.now(timezone.utc).timestamp()}_spam"
        raw_msg_spam = {
            "gmail_message_id": msg_id_spam,
            "gmail_thread_id": f"thread_{msg_id_spam}",
            "sender_email": "marketing@shop.com",
            "sender_name": "SuperStore",
            "subject": "Your monthly order receipt #9842",
            "snippet": "Thank you for shopping with us",
            "body_plain": "Thank you for shopping with us. Your invoice is attached. Unsubscribe here.",
            "received_at": datetime.now(timezone.utc),
            "attachments": []
        }

        result_spam = await EmailComplaintProcessor.process_raw_email(db, raw_msg_spam)
        assert_true(result_spam["status"] == "ignored", "Non-civic email ignored")
        email_spam_row = db.query(EmailMessage).filter(EmailMessage.gmail_message_id == msg_id_spam).first()
        assert_true(email_spam_row.complaint_id is None, "No complaint created for ignored spam message")

        # 6. Test Email API Endpoints
        # List messages
        res_list = requests.get(f"{BACKEND_URL}/api/email/messages")
        assert_true(res_list.status_code == 200, "GET /api/email/messages returns 200")
        msgs = res_list.json()
        assert_true(len(msgs) >= 3, f"Messages list returns records (got {len(msgs)})")

        # Get single message
        res_single = requests.get(f"{BACKEND_URL}/api/email/messages/{email_row_1.id}")
        assert_true(res_single.status_code == 200, "GET /api/email/messages/{id} returns 200")
        assert_true(res_single.json()["complaint_id"] == complaint_id_1, "Single message endpoint returns correct complaint reference")

        # Track complaint endpoint includes submission channel
        res_track = requests.get(f"{BACKEND_URL}/api/complaints/{complaint_id_1}")
        assert_true(res_track.status_code == 200, "GET /api/complaints/{id} returns 200")
        track_payload = res_track.json()
        assert_true(track_payload["submission_channel"] == "email", f"Track payload indicates channel=email (got {track_payload['submission_channel']})")

    finally:
        db.close()

    print("\n🎉 ALL PHASE 6 GMAIL AI INTEGRATION & UNIFIED PIPELINE TESTS PASSED! 🎉\n")

if __name__ == "__main__":
    asyncio.run(run_async_tests())
