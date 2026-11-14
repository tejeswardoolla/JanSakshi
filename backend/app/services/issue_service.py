from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.complaint import PhysicalIssue, Complaint
from app.repositories import PhysicalIssueRepository, ComplaintRepository
from app.services.issue_id_service import generate_issue_reference_id

class PhysicalIssueService:
    def __init__(self, db: Session):
        self.db = db
        self.issue_repo = PhysicalIssueRepository(db)
        self.complaint_repo = ComplaintRepository(db)

    def create_issue(
        self,
        category: str,
        representative_latitude: float,
        representative_longitude: float,
        description: str,
        representative_location: Optional[str] = None
    ) -> PhysicalIssue:
        issue_ref = generate_issue_reference_id(self.db)
        issue = self.issue_repo.create({
            "issue_reference_id": issue_ref,
            "category": category.strip(),
            "representative_latitude": representative_latitude,
            "representative_longitude": representative_longitude,
            "representative_location": representative_location.strip() if representative_location else None,
            "description": description.strip(),
            "current_status": "Open"
        })
        self.db.commit()
        self.db.refresh(issue)
        return issue

    def get_issue(self, issue_reference_id: str) -> PhysicalIssue:
        issue = self.issue_repo.get_by_reference_id(issue_reference_id)
        if not issue:
            raise HTTPException(status_code=404, detail=f"Physical Issue '{issue_reference_id}' not found.")
        return issue

    def get_complaints_for_issue(self, issue_reference_id: str) -> List[Complaint]:
        self.get_issue(issue_reference_id) # validates existence
        return self.issue_repo.get_complaints_for_issue(issue_reference_id)

    def associate_complaint(
        self,
        complaint_id: str,
        issue_reference_id: Optional[str],
        source: str = "admin"
    ) -> Complaint:
        complaint = self.complaint_repo.get_by_complaint_id(complaint_id)
        if not complaint:
            raise HTTPException(status_code=404, detail=f"Complaint '{complaint_id}' not found.")

        if issue_reference_id:
            # Verify issue exists
            issue = self.issue_repo.get_by_reference_id(issue_reference_id)
            if not issue:
                raise HTTPException(status_code=404, detail=f"Target Physical Issue '{issue_reference_id}' not found.")

        updated_complaint = self.complaint_repo.associate_with_issue(
            complaint=complaint,
            issue_id=issue_reference_id,
            source=source
        )
        self.db.commit()
        self.db.refresh(updated_complaint)
        return updated_complaint

