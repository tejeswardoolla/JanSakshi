from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.complaint import Complaint, PhysicalIssue, DuplicateMatch
from app.core.security import require_roles
from app.models.authority import User
from app.services.duplicate_detection import DuplicateDetector
from app.schemas import (
    DuplicateMatchResponse,
    DuplicateReviewQueueItem,
    DuplicateReviewActionRequest,
    DuplicateReviewActionResponse,
    PhysicalIssueResponse,
)

router = APIRouter(prefix="/api/duplicates", tags=["Duplicate Detection"])

def _format_match_response(match: DuplicateMatch) -> DuplicateMatchResponse:
    cand_issue = None
    if match.physical_issue:
        associated_ids = [c.complaint_id for c in match.physical_issue.complaints]
        associated_comps = [
            {
                "complaint_id": c.complaint_id,
                "citizen_name": c.citizen_name,
                "citizen_email": c.citizen_email,
                "submission_channel": c.submission_channel,
                "category": c.category,
                "description": c.description,
            }
            for c in match.physical_issue.complaints
        ]
        cand_issue = PhysicalIssueResponse(
            id=match.physical_issue.id,
            issue_reference_id=match.physical_issue.issue_reference_id,
            category=match.physical_issue.category,
            representative_latitude=match.physical_issue.representative_latitude,
            representative_longitude=match.physical_issue.representative_longitude,
            representative_location=match.physical_issue.representative_location,
            description=match.physical_issue.description,
            current_status=match.physical_issue.current_status,
            created_at=match.physical_issue.created_at,
            updated_at=match.physical_issue.updated_at,
            complaint_count=len(match.physical_issue.complaints),
            associated_complaint_ids=associated_ids,
            associated_complaints=associated_comps,
        )
    return DuplicateMatchResponse(
        id=match.id,
        complaint_id=match.complaint_id,
        candidate_physical_issue_id=match.candidate_physical_issue_id,
        similarity_score=match.similarity_score,
        gps_similarity=match.gps_similarity,
        gps_distance_meters=match.gps_distance_meters,
        text_similarity=match.text_similarity,
        image_similarity=match.image_similarity,
        category_similarity=match.category_similarity,
        confidence_level=match.confidence_level,
        recommendation=match.recommendation,
        matching_explanation=match.matching_explanation,
        warning_signals=match.warning_signals,
        review_status=match.review_status,
        reviewer_id=match.reviewer_id,
        review_reason=match.review_reason,
        reviewed_at=match.reviewed_at,
        created_at=match.created_at,
        updated_at=match.updated_at,
        candidate_issue=cand_issue,
    )

@router.get("/complaints/{complaint_id}", response_model=List[DuplicateMatchResponse])
async def get_complaint_duplicate_candidates(
    complaint_id: str,
    db: Session = Depends(get_db)
):
    """
    Retrieve candidate physical issue duplicate matches for a given citizen complaint.
    """
    complaint = db.query(Complaint).filter(Complaint.complaint_id == complaint_id.strip()).first()
    if not complaint:
        raise HTTPException(status_code=404, detail=f"Complaint '{complaint_id}' not found.")

    matches = (
        db.query(DuplicateMatch)
        .filter(DuplicateMatch.complaint_id == complaint.complaint_id)
        .order_by(DuplicateMatch.similarity_score.desc())
        .all()
    )
    return [_format_match_response(m) for m in matches]

@router.get("/review-queue", response_model=List[DuplicateReviewQueueItem])
async def get_duplicate_review_queue(
    status_filter: str = Query("pending", alias="status", description="Filter by review status: pending, approved, rejected, all"),
    confidence: Optional[str] = Query(None, description="Filter by confidence level: high, medium, low"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"]))
):
    """
    Returns candidate duplicate matches for the authority review dashboard.
    Enables civic administrators to review side-by-side evidence and verify physical issue linkages.
    """
    query = db.query(DuplicateMatch).join(Complaint, DuplicateMatch.complaint_id == Complaint.complaint_id)

    if status_filter != "all":
        query = query.filter(DuplicateMatch.review_status == status_filter)

    if confidence:
        query = query.filter(DuplicateMatch.confidence_level == confidence.lower())

    matches = query.order_by(DuplicateMatch.similarity_score.desc(), DuplicateMatch.created_at.desc()).all()

    queue_items = []
    for m in matches:
        comp = m.complaint
        queue_items.append(
            DuplicateReviewQueueItem(
                match=_format_match_response(m),
                complaint_category=comp.category,
                complaint_description=comp.description,
                complaint_latitude=comp.latitude,
                complaint_longitude=comp.longitude,
                complaint_created_at=comp.created_at,
                evidence_count=len(comp.evidence_files),
                citizen_name=comp.citizen_name,
                citizen_email=comp.citizen_email,
                submission_channel=comp.submission_channel,
            )
        )
    return queue_items

@router.post("/matches/{match_id}/approve", response_model=DuplicateReviewActionResponse)
async def approve_duplicate_candidate(
    match_id: int,
    payload: DuplicateReviewActionRequest = DuplicateReviewActionRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"]))
):
    """
    Authority action: Approve candidate duplicate match and associate the complaint with the PhysicalIssue.
    Citizen complaint record and evidence remain strictly preserved.
    """
    try:
        result = DuplicateDetector.approve_match(
            db=db,
            match_id=match_id,
            reviewer_id=current_user.full_name or "admin",
            review_reason=payload.review_reason or "Approved after inspecting spatial and evidence alignment."
        )
        return DuplicateReviewActionResponse(
            status=result["status"],
            message=result["message"],
            match_id=result["match_id"],
            complaint_id=result["complaint_id"],
            issue_reference_id=result["issue_reference_id"],
            review_status=result["review_status"],
            dismissed_sibling_count=result.get("dismissed_sibling_count", 0),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to approve match: {str(e)}")

@router.post("/matches/{match_id}/reject", response_model=DuplicateReviewActionResponse)
async def reject_duplicate_candidate(
    match_id: int,
    payload: DuplicateReviewActionRequest = DuplicateReviewActionRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"]))
):
    """
    Authority action: Reject candidate duplicate match.
    Complaint remains an independent record with independent resolution tracking.
    """
    try:
        result = DuplicateDetector.reject_match(
            db=db,
            match_id=match_id,
            reviewer_id=current_user.full_name or "admin",
            review_reason=payload.review_reason or "Rejected: distinct infrastructure problem."
        )
        return DuplicateReviewActionResponse(
            status=result["status"],
            message=result["message"],
            match_id=result["match_id"],
            complaint_id=result["complaint_id"],
            review_status=result["review_status"],
            issue_reference_id=None,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reject match: {str(e)}")

@router.post("/complaints/{complaint_id}/retry", response_model=List[DuplicateMatchResponse])
async def retry_duplicate_detection(
    complaint_id: str,
    search_radius_meters: float = Query(150.0, description="Search radius in meters"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"]))
):
    """
    Trigger or re-run duplicate detection for a complaint against existing Physical Issues.
    """
    complaint = db.query(Complaint).filter(Complaint.complaint_id == complaint_id.strip()).first()
    if not complaint:
        raise HTTPException(status_code=404, detail=f"Complaint '{complaint_id}' not found.")

    matches = DuplicateDetector.evaluate_complaint(
        complaint_id=complaint.complaint_id,
        db=db,
        search_radius_meters=search_radius_meters
    )
    return [_format_match_response(m) for m in matches]

