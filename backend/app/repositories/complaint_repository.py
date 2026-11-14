import datetime
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models.complaint import Complaint, Evidence, ComplaintEvent, PhysicalIssue
from app.core.config import utc_now

class ComplaintRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_complaint_id(self, complaint_id: str) -> Optional[Complaint]:
        return self.db.query(Complaint).filter(Complaint.complaint_id == complaint_id.strip()).first()

    def get_latest_complaint_for_year(self, year: int) -> Optional[Complaint]:
        prefix = f"JS-{year}-"
        return (
            self.db.query(Complaint)
            .filter(Complaint.complaint_id.like(f"{prefix}%"))
            .order_by(Complaint.id.desc())
            .first()
        )

    def create(self, complaint_data: dict) -> Complaint:
        complaint = Complaint(**complaint_data)
        self.db.add(complaint)
        self.db.flush()
        return complaint

    def add_evidence(self, evidence_data: dict) -> Evidence:
        evidence = Evidence(**evidence_data)
        self.db.add(evidence)
        self.db.flush()
        return evidence

    def add_event(
        self,
        complaint_id: str,
        event_type: str,
        description: str,
        previous_value: Optional[str] = None,
        new_value: Optional[str] = None,
        source: str = "system"
    ) -> ComplaintEvent:
        event = ComplaintEvent(
            complaint_id=complaint_id,
            event_type=event_type,
            previous_value=previous_value,
            new_value=new_value,
            description=description,
            source=source,
            created_at=utc_now()
        )
        self.db.add(event)
        self.db.flush()
        return event

    def get_events_for_complaint(self, complaint_id: str) -> List[ComplaintEvent]:
        return (
            self.db.query(ComplaintEvent)
            .filter(ComplaintEvent.complaint_id == complaint_id.strip())
            .order_by(ComplaintEvent.created_at.asc())
            .all()
        )

    def associate_with_issue(self, complaint: Complaint, issue_id: Optional[str], source: str = "admin") -> Complaint:
        old_issue_id = complaint.issue_id
        complaint.issue_id = issue_id
        complaint.updated_at = utc_now()
        self.db.flush()

        self.add_event(
            complaint_id=complaint.complaint_id,
            event_type="complaint_associated_with_issue" if issue_id else "complaint_disassociated_from_issue",
            previous_value=old_issue_id,
            new_value=issue_id,
            description=f"Complaint associated with Physical Issue {issue_id}" if issue_id else f"Complaint disassociated from Physical Issue {old_issue_id}",
            source=source
        )
        return complaint

class PhysicalIssueRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_reference_id(self, issue_reference_id: str) -> Optional[PhysicalIssue]:
        return self.db.query(PhysicalIssue).filter(PhysicalIssue.issue_reference_id == issue_reference_id.strip()).first()

    def get_latest_issue_for_year(self, year: int) -> Optional[PhysicalIssue]:
        prefix = f"ISSUE-{year}-"
        return (
            self.db.query(PhysicalIssue)
            .filter(PhysicalIssue.issue_reference_id.like(f"{prefix}%"))
            .order_by(PhysicalIssue.id.desc())
            .first()
        )

    def create(self, issue_data: dict) -> PhysicalIssue:
        issue = PhysicalIssue(**issue_data)
        self.db.add(issue)
        self.db.flush()
        return issue

    def get_complaints_for_issue(self, issue_reference_id: str) -> List[Complaint]:
        return (
            self.db.query(Complaint)
            .filter(Complaint.issue_id == issue_reference_id.strip())
            .order_by(Complaint.created_at.asc())
            .all()
        )

