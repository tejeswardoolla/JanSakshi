from app.database import SessionLocal
from app.models.complaint import Complaint

db = SessionLocal()
rows = db.query(Complaint.complaint_id, Complaint.status, Complaint.admin_status, Complaint.verification_status, Complaint.submission_channel).all()
for r in rows:
    print(f"{r[0]} | status={r[1]} | admin_status={r[2]} | verif={r[3]} | channel={r[4]}")
db.close()

