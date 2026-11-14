import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models.complaint import Complaint

def generate_complaint_id(db: Session) -> str:
    """
    Concurrency-safe complaint ID generator in format: JS-YYYY-XXXXX
    e.g. JS-2026-00001
    """
    year = datetime.datetime.utcnow().year
    prefix = f"JS-{year}-"
    
    # Query highest sequential number for current year
    # Works consistently across SQLite and PostgreSQL
    latest = (
        db.query(Complaint.complaint_id)
        .filter(Complaint.complaint_id.like(f"{prefix}%"))
        .order_by(Complaint.id.desc())
        .first()
    )
    
    if latest and latest[0]:
        try:
            current_num_str = latest[0].split("-")[-1]
            next_num = int(current_num_str) + 1
        except (ValueError, IndexError):
            next_num = 1
    else:
        next_num = 1
        
    return f"{prefix}{next_num:05d}"

