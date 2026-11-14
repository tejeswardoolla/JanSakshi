from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.issue_service import PhysicalIssueService
from app.schemas import (
    PhysicalIssueCreateRequest,
    PhysicalIssueResponse,
    ComplaintTrackResponse,
)

router = APIRouter(prefix="/api/issues", tags=["Physical Issues"])

@router.post("/", response_model=PhysicalIssueResponse, status_code=status.HTTP_201_CREATED)
async def create_physical_issue(
    payload: PhysicalIssueCreateRequest,
    db: Session = Depends(get_db)
):
    """
    Create a new Physical Issue entity representing a distinct real-world infrastructure problem.
    """
    service = PhysicalIssueService(db)
    issue = service.create_issue(
        category=payload.category,
        representative_latitude=payload.representative_latitude,
        representative_longitude=payload.representative_longitude,
        description=payload.description,
        representative_location=payload.representative_location
    )
    return PhysicalIssueResponse(
        id=issue.id,
        issue_reference_id=issue.issue_reference_id,
        category=issue.category,
        representative_latitude=issue.representative_latitude,
        representative_longitude=issue.representative_longitude,
        representative_location=issue.representative_location,
        description=issue.description,
        current_status=issue.current_status,
        created_at=issue.created_at,
        updated_at=issue.updated_at,
        complaint_count=len(issue.complaints)
    )

@router.get("/{issue_id}", response_model=PhysicalIssueResponse)
async def get_physical_issue(
    issue_id: str,
    db: Session = Depends(get_db)
):
    """
    Retrieve details of a Physical Issue by its reference ID (e.g. ISSUE-2026-00001).
    """
    service = PhysicalIssueService(db)
    issue = service.get_issue(issue_id)
    return PhysicalIssueResponse(
        id=issue.id,
        issue_reference_id=issue.issue_reference_id,
        category=issue.category,
        representative_latitude=issue.representative_latitude,
        representative_longitude=issue.representative_longitude,
        representative_location=issue.representative_location,
        description=issue.description,
        current_status=issue.current_status,
        created_at=issue.created_at,
        updated_at=issue.updated_at,
        complaint_count=len(issue.complaints)
    )

@router.get("/{issue_id}/complaints", response_model=List[ComplaintTrackResponse])
async def get_complaints_for_issue(
    issue_id: str,
    db: Session = Depends(get_db)
):
    """
    Retrieve all individual citizen complaints associated with a specific Physical Issue.
    All complaints remain independent entities.
    """
    service = PhysicalIssueService(db)
    complaints = service.get_complaints_for_issue(issue_id)
    return [
        ComplaintTrackResponse(
            complaint_id=c.complaint_id,
            issue_id=c.issue_id,
            category=c.category,
            description=c.description,
            latitude=c.latitude,
            longitude=c.longitude,
            location_accuracy=c.location_accuracy,
            location_source=c.location_source,
            google_maps_url=c.google_maps_url,
            status=c.status,
            submission_channel=c.submission_channel,
            created_at=c.created_at,
            evidence_count=len(c.evidence_files),
            evidence=c.evidence_files
        )
        for c in complaints
    ]

