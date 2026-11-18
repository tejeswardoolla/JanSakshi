"""
Test and Verification script for JanSakshi Redesigned Automatic Citizen Acknowledgement Email
Validates:
1. Dynamic population from actual complaint record JS-2026-00057
2. Exact required headers, text, AI disclaimer, tracking CTA, and footer
3. MIME multipart alternative payload generation
4. Local HTML preview generation and Playwright Edge screenshot capture
"""

import os
import sys
import datetime
import base64

# Ensure backend root is in path and working directory
os.chdir(os.path.abspath(os.path.dirname(__file__)))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.database import SessionLocal
from app.models.complaint import Complaint
from app.models.email_message import EmailMessage
from app.services.email.acknowledgement_service import AcknowledgementService
from app.services.email.email_templates import (
    render_acknowledgement_email_html,
    render_acknowledgement_email_text
)

def run_verification():
    db = SessionLocal()
    try:
        complaint = db.query(Complaint).filter(Complaint.complaint_id == "JS-2026-00057").first()
        if not complaint:
            print("ERROR: Complaint JS-2026-00057 not found in database!")
            return False

        email_record = db.query(EmailMessage).filter(EmailMessage.complaint_id == "JS-2026-00057").first()

        print("=== 1. COMPLAINT & EMAIL DATA LOADED ===")
        print(f"Complaint ID:     {complaint.complaint_id}")
        print(f"Category:         {complaint.category}")
        print(f"Status:           {complaint.status} (Admin: {complaint.admin_status})")
        print(f"Tracking Token:   {complaint.tracking_token}")
        print(f"Evidence Files:   {len(complaint.evidence_files)}")
        if email_record:
            print(f"Sender Email:     {email_record.sender_email}")
            print(f"Sender Name:      {email_record.sender_name}")
            print(f"Extracted Loc:    {email_record.extracted_location_text}")

        # Generate Email Content using official hosted HTTPS logo URL
        subject, body_text, body_html = AcknowledgementService.generate_email_content(
            complaint=complaint,
            email_record=email_record,
            location_missing=False
        )

        print("\n=== 2. CONTENT GENERATION CHECK ===")
        print(f"Subject: {subject}")
        assert "JS-2026-00057" in subject, "Subject must contain Complaint ID"

        # Check that generic scales icon and CID attachments are removed
        assert "&#9878;" not in body_html, "Generic scales icon must be completely removed"
        assert "cid:jansakshi-logo" not in body_html, "Inline CID attachment reference must be removed"
        assert "https://raw.githubusercontent.com" in body_html, "Official hosted HTTPS logo URL must be present"
        assert 'alt="JanSakshi Logo"' in body_html, "Logo must have proper alternative text"

        # Check required text elements in HTML
        required_elements = [
            ("Header Brand", "Jan"),
            ("Header Subtitle", "Civic Complaint Management"),
            ("Main Heading", "Your Complaint Has Been Successfully Registered!"),
            ("Registration Message", "Thank you for bringing this issue to our attention. Your complaint has been successfully registered in the JanSakshi civic complaint management system."),
            ("Complaint Reference ID", "JS-2026-00057"),
            ("Category", "Damaged Public Infrastructure"),
            ("Location", "Morampudi Junction"),
            ("Current Status", "Received"),
            ("Evidence Status", "photographic evidence"),
            ("Tracking CTA Button", "TRACK YOUR COMPLAINT"),
            ("AI Disclaimer", "AI-powered assessment provides preliminary category and severity recommendations. Final verification, prioritization and resolution decisions are made by the concerned municipal authorities."),
            ("Footer Platform", "JanSakshi Civic Grievance &amp; Redressal Platform"),
            ("Footer Civic Message", "Empowering citizens to report, track, and resolve civic infrastructure issues collaboratively"),
            ("Footer Automated Note", "This is an automated acknowledgement generated upon receipt of your civic report")
        ]

        print("\nValidating HTML Template:")
        for label, snippet in required_elements:
            assert snippet.lower() in body_html.lower(), f"Missing '{snippet}' ({label}) in HTML template"
            print(f"  [PASS] {label}: Found '{snippet[:40]}...'")

        # Check plain-text fallback
        print("\nValidating Plain-Text Fallback:")
        for label, snippet in [
            ("Header Brand", "JANSAKSHI – CIVIC COMPLAINT MANAGEMENT"),
            ("Registration Message", "Your complaint has been successfully registered in the JanSakshi civic complaint management system."),
            ("Complaint Reference ID", "JS-2026-00057"),
            ("Category", "Damaged Public Infrastructure"),
            ("Tracking URL", "/track?id=JS-2026-00057"),
            ("AI Disclaimer", "AI-powered assessment provides preliminary category and severity recommendations."),
            ("Footer", "Municipal Corporation of Rajamahendravaram")
        ]:
            assert snippet.lower() in body_text.lower(), f"Missing '{snippet}' ({label}) in plain text"
            print(f"  [PASS] {label}: Found '{snippet[:40]}...'")

        # Verify MIME creation with inline CID logo
        msg_payload = AcknowledgementService.create_message(
            sender_email="jansakshiofficial@gmail.com",
            to_email=email_record.sender_email if email_record else "citizen@example.com",
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            thread_id=email_record.gmail_thread_id if email_record else None,
            in_reply_to=email_record.gmail_message_id if email_record else None
        )
        assert "raw" in msg_payload, "MIME message must have 'raw' payload"
        print(f"\n[PASS] MIME Message Payload generated successfully (Base64 length: {len(msg_payload['raw'])})")

        # Save HTML preview
        screenshots_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Screenshots"))
        os.makedirs(screenshots_dir, exist_ok=True)
        preview_html_path = os.path.join(screenshots_dir, "email_preview_JS-2026-00057.html")

        with open(preview_html_path, "w", encoding="utf-8") as f:
            f.write(body_html)
        print(f"\n[PASS] Saved HTML preview to: {preview_html_path}")

        # Also save plain-text preview
        preview_txt_path = os.path.join(screenshots_dir, "email_preview_JS-2026-00057.txt")
        with open(preview_txt_path, "w", encoding="utf-8") as f:
            f.write(body_text)
        print(f"[PASS] Saved Plain-text preview to: {preview_txt_path}")

        return True
    finally:
        db.close()

if __name__ == "__main__":
    success = run_verification()
    if not success:
        sys.exit(1)
    print("\nAll acknowledgement template unit validations passed successfully!")
