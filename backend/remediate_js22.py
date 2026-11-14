import re
from app.database import SessionLocal
from app.models.complaint import Complaint
from app.models.email_message import EmailMessage

db = SessionLocal()
c = db.query(Complaint).filter(Complaint.complaint_id == "JS-2026-00022").first()
if c:
    # Sanitize ticket url
    c.description = re.sub(
        r'https?://[^\s]+(?:ticket|token|clerk|session|key)=[^\s]+',
        '[REDACTED_SECURITY_LINK]',
        c.description
    )
    c.status = "Rejected"
    c.verification_status = "rejected"
    c.rejection_reason = "Non-civic submission: Account security notification from Higgsfield AI (not a municipal grievance)"
    print("Sanitized JS-2026-00022 complaint description and confirmed status=Rejected")

e = db.query(EmailMessage).filter(EmailMessage.complaint_id == "JS-2026-00022").first()
if e:
    e.is_civic_complaint = False
    e.processing_status = "ignored"
    e.error_details = "Non-civic email filtered [Account Security Notification]: Account security sign-in notification."
    print("Updated EmailMessage 26 to is_civic_complaint=False, status=ignored")

db.commit()
db.close()
print("Done database remediation for JS-2026-00022.")

