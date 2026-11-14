from app.database import SessionLocal
from app.models.complaint import Complaint

def compute_preparation_status(c, latest_ai):
    # 1. Non-civic / Rejected
    if c.status == "Rejected" or c.verification_status == "rejected" or c.admin_status == "Rejected":
        return "Rejected / Non-Civic"
    
    # 2. Awaiting Information (Missing location coordinates or citizen clarification requested)
    if c.verification_status == "info_requested":
        return "Awaiting Information"
    if (c.latitude is None or c.longitude is None or c.location_source in ("missing", "email_pending_clarification")) and c.verification_status == "pending" and c.status not in ("Closed", "Resolved"):
        return "Awaiting Information"

    # 3. Ready for Authority Officer / Already Prepared
    # If explicitly marked ready, or already verified/assigned/closed post-intake
    if c.admin_status == "Ready for Authority Officer":
        return "Ready for Authority Officer"
    if c.verification_status == "verified" or c.status in ("Verified", "Assigned", "In Progress", "Resolution Submitted", "Returned for Correction", "Closed", "Resolved") or c.assigned_department_id is not None:
        return "Ready for Authority Officer"

    # 4. Under Preparation
    ai_status = latest_ai.analysis_status if latest_ai else "pending"
    if ai_status == "completed" or (c.latitude is not None and c.longitude is not None):
        return "Under Preparation"

    # 5. Default / Initial intake
    return "Pending Review"

db = SessionLocal()
complaints = db.query(Complaint).order_by(Complaint.id.asc()).all()
for c in complaints:
    latest_ai = c.ai_analyses[0] if c.ai_analyses else None
    ai_st = latest_ai.analysis_status if latest_ai else "pending"
    prep_st = compute_preparation_status(c, latest_ai)
    print(f"{c.complaint_id} | AI: {ai_st:10} | Prep: {prep_st:27} | Lifecycle: {c.status:20} | Admin_status: {c.admin_status}")
db.close()

