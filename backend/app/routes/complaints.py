from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories import ComplaintRepository
from app.models.complaint import AIAnalysis, PhysicalIssue
from app.pipeline import ComplaintProcessingPipeline, NormalizedComplaintInput
from app.services.location_service import resolve_location_input
from app.services.issue_service import PhysicalIssueService
from app.schemas import (
    ComplaintCreateResponse,
    ComplaintTrackResponse,
    LocationResolveRequest,
    LocationResolveResponse,
    ComplaintEventResponse,
    AssociateIssueRequest,
    AssociateIssueResponse,
    AIAnalysisResponse,
    PhysicalIssueResponse,
    DuplicateMatchResponse,
)
from pydantic import BaseModel

class DirectUploadTokenRequest(BaseModel):
    filename: str
    content_type: str
    file_size: int

router = APIRouter(prefix="/api/complaints", tags=["Complaints"])

@router.post("/evidence/upload-token")
async def get_direct_upload_token(payload: DirectUploadTokenRequest):
    """
    Direct Browser-to-Blob Upload Token Endpoint.
    Enables secure direct media uploads to Vercel Blob up to 25 MB,
    bypassing the Vercel Hobby 4.5 MB request body limit.
    """
    from app.services.storage_service import prepare_direct_upload
    return prepare_direct_upload(
        filename=payload.filename,
        content_type=payload.content_type,
        file_size=payload.file_size
    )

@router.post("/resolve-location", response_model=LocationResolveResponse)
async def resolve_location(payload: LocationResolveRequest):
    """
    Resolve coordinates from manual inputs, Google Maps links, or Plus Codes.
    """
    success, lat, lng, source, gmaps_url, msg = resolve_location_input(payload.query)
    return LocationResolveResponse(
        success=success,
        latitude=lat,
        longitude=lng,
        source=source,
        google_maps_url=gmaps_url,
        message=msg
    )

@router.post("/", response_model=ComplaintCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_complaint(
    background_tasks: BackgroundTasks,
    category: str = Form(...),
    description: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    location_accuracy: Optional[float] = Form(None),
    location_source: str = Form("gps"),
    citizen_name: Optional[str] = Form(None),
    citizen_email: Optional[str] = Form(None),
    citizen_phone: Optional[str] = Form(None),
    evidence: List[UploadFile] = File([]),
    db: Session = Depends(get_db)
):
    """
    Submit a citizen complaint through the Unified Complaint Processing Pipeline.
    Supports transactional persistence, evidence storage, and background processing tasks.
    """
    normalized_input = NormalizedComplaintInput(
        category=category,
        description=description,
        latitude=latitude,
        longitude=longitude,
        location_accuracy=location_accuracy,
        location_source=location_source,
        citizen_name=citizen_name,
        citizen_email=citizen_email,
        citizen_phone=citizen_phone,
        submission_channel="website",
        evidence_files=evidence
    )

    pipeline = ComplaintProcessingPipeline(db=db, background_tasks=background_tasks)
    complaint_record = await pipeline.execute(normalized_input)

    return ComplaintCreateResponse(
        complaint_id=complaint_record.complaint_id,
        tracking_token=complaint_record.tracking_token,
        status=complaint_record.status,
        category=complaint_record.category,
        created_at=complaint_record.created_at,
        google_maps_url=complaint_record.google_maps_url,
        message="Your report has been received successfully."
    )

@router.get("/{complaint_id}", response_model=ComplaintTrackResponse)
async def track_complaint(complaint_id: str, db: Session = Depends(get_db)):
    """
    Retrieve complaint status, physical issue link (if mapped), latest AI analysis (if any),
    and evidence references securely. Citizen personal details remain protected.
    """
    repo = ComplaintRepository(db)
    complaint = repo.get_by_complaint_id(complaint_id)
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found. Please verify your Complaint ID.")

    latest_ai = (
        db.query(AIAnalysis)
        .filter(AIAnalysis.complaint_id == complaint_id.strip())
        .order_by(AIAnalysis.id.desc())
        .first()
    )

    associated_issue = None
    if complaint.issue_id:
        issue = db.query(PhysicalIssue).filter(PhysicalIssue.issue_reference_id == complaint.issue_id).first()
        if issue:
            associated_issue = PhysicalIssueResponse(
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

    # Attach candidate issue information to duplicate matches
    duplicate_matches_response = []
    for m in complaint.duplicate_matches:
        cand_issue = None
        if m.physical_issue:
            cand_issue = PhysicalIssueResponse(
                id=m.physical_issue.id,
                issue_reference_id=m.physical_issue.issue_reference_id,
                category=m.physical_issue.category,
                representative_latitude=m.physical_issue.representative_latitude,
                representative_longitude=m.physical_issue.representative_longitude,
                representative_location=m.physical_issue.representative_location,
                description=m.physical_issue.description,
                current_status=m.physical_issue.current_status,
                created_at=m.physical_issue.created_at,
                updated_at=m.physical_issue.updated_at,
                complaint_count=len(m.physical_issue.complaints)
            )
        duplicate_matches_response.append(
            DuplicateMatchResponse(
                id=m.id,
                complaint_id=m.complaint_id,
                candidate_physical_issue_id=m.candidate_physical_issue_id,
                similarity_score=m.similarity_score,
                gps_similarity=m.gps_similarity,
                gps_distance_meters=m.gps_distance_meters,
                text_similarity=m.text_similarity,
                image_similarity=m.image_similarity,
                category_similarity=m.category_similarity,
                confidence_level=m.confidence_level,
                recommendation=m.recommendation,
                matching_explanation=m.matching_explanation,
                warning_signals=m.warning_signals,
                review_status=m.review_status,
                reviewer_id=m.reviewer_id,
                review_reason=m.review_reason,
                reviewed_at=m.reviewed_at,
                created_at=m.created_at,
                updated_at=m.updated_at,
                candidate_issue=cand_issue
            )
        )

    sanitized_description = complaint.description
    if complaint.status == "Rejected" or complaint.verification_status == "rejected":
        # Check if description contains auth tickets, tokens, or security links
        import re
        sanitized_description = re.sub(
            r'https?://[^\s]+(?:ticket|token|clerk|session|key)=[^\s]+',
            '[REDACTED_SECURITY_LINK]',
            sanitized_description
        )
        if complaint.rejection_reason and "Non-civic" in complaint.rejection_reason:
            sanitized_description = f"[Non-civic submission rejected during intake review: {complaint.rejection_reason}]"

    return ComplaintTrackResponse(
        complaint_id=complaint.complaint_id,
        issue_id=complaint.issue_id,
        category=complaint.category,
        description=sanitized_description,
        latitude=complaint.latitude,
        longitude=complaint.longitude,
        location_accuracy=complaint.location_accuracy,
        location_source=complaint.location_source,
        google_maps_url=complaint.google_maps_url,
        status=complaint.status,
        submission_channel=complaint.submission_channel,
        created_at=complaint.created_at,
        evidence_count=len(complaint.evidence_files),
        evidence=complaint.evidence_files,
        latest_ai_analysis=latest_ai,
        associated_issue=associated_issue,
        duplicate_matches=duplicate_matches_response
    )

@router.get("/{complaint_id}/events", response_model=List[ComplaintEventResponse])
async def get_complaint_events(complaint_id: str, db: Session = Depends(get_db)):
    """
    Retrieve chronological audit and processing history for a complaint.
    """
    repo = ComplaintRepository(db)
    complaint = repo.get_by_complaint_id(complaint_id)
    if not complaint:
        raise HTTPException(status_code=404, detail=f"Complaint '{complaint_id}' not found.")

    events = repo.get_events_for_complaint(complaint_id)
    return events

@router.post("/{complaint_id}/associate-issue", response_model=AssociateIssueResponse)
async def associate_complaint_to_issue(
    complaint_id: str,
    payload: AssociateIssueRequest,
    db: Session = Depends(get_db)
):
    """
    Associate or disassociate a Complaint with a Physical Issue.
    Controlled, reversible, and auditable operation.
    """
    service = PhysicalIssueService(db)
    updated = service.associate_complaint(
        complaint_id=complaint_id,
        issue_reference_id=payload.issue_reference_id,
        source=payload.source
    )
    return AssociateIssueResponse(
        complaint_id=updated.complaint_id,
        issue_id=updated.issue_id,
        message=f"Complaint '{complaint_id}' successfully updated.",
        updated_at=updated.updated_at
    )
