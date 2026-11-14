import datetime
from sqlalchemy.orm import Session
from app.models.complaint import PhysicalIssue

def generate_issue_reference_id(db: Session) -> str:
    """
    Generate unique human-readable issue ID: ISSUE-YYYY-XXXXX
    e.g. ISSUE-2026-00001
    """
    year = datetime.datetime.utcnow().year
    prefix = f"ISSUE-{year}-"

    latest = (
        db.query(PhysicalIssue.issue_reference_id)
        .filter(PhysicalIssue.issue_reference_id.like(f"{prefix}%"))
        .order_by(PhysicalIssue.id.desc())
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

