"""
JanSakshi Phase 8: Evidence-Based Resolution Verification API Routes
Provides endpoints for department resolution submissions, AI evidence evaluation,
and Authority Officer resolution review queue & closure workflows.
"""

from typing import Optional, List, Dict, Any
import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models.complaint import Complaint, ResolutionSubmission, ResolutionEvidenceAnalysis, Evidence
from app.models.authority import User
from app.core.security import get_current_user, require_roles
from app.services.resolution_service import ResolutionVerificationService

router = APIRouter(prefix="/api/authority", tags=["Resolution Verification"])

class ResolutionSubmitRequest(BaseModel):
    work_completed_description: Optional[str] = None
    work_description: Optional[str] = None
    repair_action_taken: str = Field(..., min_length=5, description="Specific repair action taken by department team")
    completion_datetime: Optional[datetime.datetime] = None
    field_notes: Optional[str] = None
    materials_used: Optional[str] = None
    after_photo_urls: Optional[List[str]] = None
    before_evidence_id: Optional[int] = None
    after_evidence_id: Optional[int] = None
    additional_evidence_ids: Optional[str] = None

class ResolutionActionRequest(BaseModel):
    notes: Optional[str] = None
    verification_notes: Optional[str] = None

class ResolutionReturnRequest(BaseModel):
    correction_notes: Optional[str] = None
    rejection_reason: Optional[str] = None

class ResolutionEvidenceRequest(BaseModel):
    requested_details: Optional[str] = None
    evidence_request_notes: Optional[str] = None


@router.post("/complaints/{complaint_id}/resolution/submit", status_code=201)
async def submit_work_resolution(
    complaint_id: str,
    payload: ResolutionSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["department_officer", "admin"]))
):
    """
    Department Officer submits completed work order for verification.
    Creates a versioned ResolutionSubmission record.
    """
    desc = (payload.work_completed_description or payload.work_description or "").strip()
    if len(desc) < 5:
        raise HTTPException(status_code=422, detail="Work completion description must be at least 5 characters.")

    sub = ResolutionVerificationService.submit_resolution(
        db=db,
        complaint_id=complaint_id,
        current_user=current_user,
        work_completed_description=desc,
        repair_action_taken=payload.repair_action_taken,
        completion_datetime=payload.completion_datetime,
        field_notes=payload.field_notes,
        before_evidence_id=payload.before_evidence_id,
        after_evidence_id=payload.after_evidence_id,
        additional_evidence_ids=payload.additional_evidence_ids
    )
    officer_name = current_user.full_name or "Department Officer"
    return {
        "status": sub.status,
        "workflow_status": sub.status,
        "id": sub.id,
        "submission_id": sub.id,
        "complaint_id": sub.complaint_id,
        "version_number": sub.version_number,
        "submitted_by_officer_name": officer_name,
        "message": f"Resolution submission Version #{sub.version_number} recorded successfully."
    }

@router.get("/complaints/{complaint_id}/resolutions")
async def get_complaint_resolution_history(
    complaint_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns full versioned history of resolution submissions and review decisions for a complaint.
    """
    clean_id = complaint_id.strip()
    c = db.query(Complaint).filter(Complaint.complaint_id == clean_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Complaint not found.")

    if current_user.role == "department_officer":
        if c.assigned_department_id not in current_user.get_authorized_department_ids():
            raise HTTPException(status_code=403, detail="Access forbidden.")

    subs = db.query(ResolutionSubmission).filter(
        ResolutionSubmission.complaint_id == clean_id
    ).order_by(desc(ResolutionSubmission.version_number)).all()

    items = []
    for s in subs:
        ai_data = None
        if s.ai_analysis:
            ai_data = {
                "assessment": s.ai_analysis.assessment,
                "evidence_relevance": s.ai_analysis.evidence_relevance,
                "description_consistency": s.ai_analysis.description_consistency,
                "visual_observations": s.ai_analysis.visual_observations,
                "before_after_comparison": s.ai_analysis.before_after_comparison,
                "missing_evidence": s.ai_analysis.missing_evidence,
                "analysis_status": s.ai_analysis.analysis_status
            }

        items.append({
            "id": s.id,
            "complaint_id": s.complaint_id,
            "version_number": s.version_number,
            "status": s.status,
            "work_completed_description": s.work_completed_description,
            "repair_action_taken": s.repair_action_taken,
            "field_notes": s.field_notes,
            "completion_datetime": s.completion_datetime.isoformat() if s.completion_datetime else None,
            "authority_notes": s.authority_notes,
            "submitted_by_name": s.submitted_by.full_name if s.submitted_by else "Field Engineer",
            "reviewed_by_name": s.reviewed_by.full_name if s.reviewed_by else None,
            "reviewed_at": s.reviewed_at.isoformat() if s.reviewed_at else None,
            "before_evidence": {
                "id": s.before_evidence.id,
                "original_filename": s.before_evidence.original_filename,
                "view_url": f"/api/authority/evidence/{s.before_evidence.stored_filename}"
            } if s.before_evidence else None,
            "after_evidence": {
                "id": s.after_evidence.id,
                "original_filename": s.after_evidence.original_filename,
                "view_url": f"/api/authority/evidence/{s.after_evidence.stored_filename}"
            } if s.after_evidence else None,
            "ai_analysis": ai_data,
            "created_at": s.created_at.isoformat() if s.created_at else None
        })

    return {"complaint_id": clean_id, "submissions": items, "count": len(items)}

@router.get("/resolutions/queue")
async def get_resolution_review_queue(
    department_id: Optional[int] = Query(None),
    status_filter: str = Query("submitted", description="Filter by resolution status: submitted, approved, returned_for_correction, all"),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["authority_officer", "admin"]))
):
    """
    Authority Officer Resolution Review Queue:
    Lists work orders awaiting final review and verification.
    """
    query = db.query(ResolutionSubmission).join(Complaint, ResolutionSubmission.complaint_id == Complaint.complaint_id)

    if status_filter != "all":
        query = query.filter(ResolutionSubmission.status == status_filter)

    if department_id is not None:
        query = query.filter(ResolutionSubmission.department_id == department_id)

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            (Complaint.complaint_id.ilike(term)) |
            (Complaint.category.ilike(term)) |
            (ResolutionSubmission.work_completed_description.ilike(term)) |
            (ResolutionSubmission.repair_action_taken.ilike(term))
        )

    total = query.count()
    subs = query.order_by(desc(ResolutionSubmission.created_at)).offset((page - 1) * limit).limit(limit).all()

    items = []
    for s in subs:
        c = s.complaint
        dept = s.department
        ai = s.ai_analysis
        items.append({
            "id": s.id,
            "submission_id": s.id,
            "complaint_id": s.complaint_id,
            "version_number": s.version_number,
            "status": s.status,
            "department": {
                "id": dept.id,
                "code": dept.code,
                "name": dept.name
            } if dept else None,
            "category": c.category,
            "citizen_description": c.description,
            "latitude": c.latitude,
            "longitude": c.longitude,
            "assigned_officer_name": s.submitted_by.full_name if s.submitted_by else "Field Engineer",
            "submission_date": s.created_at.isoformat() if s.created_at else None,
            "work_completed_description": s.work_completed_description,
            "repair_action_taken": s.repair_action_taken,
            "has_before_photo": s.before_evidence_id is not None,
            "has_after_photo": s.after_evidence_id is not None,
            "ai_assessment": ai.assessment if ai else "Human Inspection Recommended",
            "evidence_relevance": ai.evidence_relevance if ai else "Pending Review"
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit
    }

@router.get("/resolutions/{submission_id}")
async def get_single_resolution_detail(
    submission_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns full side-by-side comparison detail for a resolution submission.
    Accepts either an integer submission ID or a complaint ID string (e.g., JS-2026-00028).
    """
    clean_val = str(submission_id).strip()
    if clean_val.isdigit():
        sub = db.query(ResolutionSubmission).filter(ResolutionSubmission.id == int(clean_val)).first()
    else:
        sub = db.query(ResolutionSubmission).filter(
            ResolutionSubmission.complaint_id == clean_val
        ).order_by(desc(ResolutionSubmission.version_number)).first()

    if not sub:
        raise HTTPException(status_code=404, detail="Resolution submission not found.")

    c = sub.complaint
    if current_user.role == "department_officer":
        if c.assigned_department_id not in current_user.get_authorized_department_ids():
            raise HTTPException(status_code=403, detail="Access forbidden.")

    # All complaint evidence files
    evidence_list = [{
        "id": ev.id,
        "original_filename": ev.original_filename,
        "view_url": f"/api/authority/evidence/{ev.stored_filename}",
        "file_type": ev.file_type,
        "file_size": ev.file_size
    } for ev in c.evidence_files]

    ai_data = None
    if sub.ai_analysis:
        ai_data = {
            "assessment": sub.ai_analysis.assessment,
            "evidence_relevance": sub.ai_analysis.evidence_relevance,
            "description_consistency": sub.ai_analysis.description_consistency,
            "visual_observations": sub.ai_analysis.visual_observations,
            "before_after_comparison": sub.ai_analysis.before_after_comparison,
            "missing_evidence": sub.ai_analysis.missing_evidence,
            "analysis_status": sub.ai_analysis.analysis_status,
            "model_name": sub.ai_analysis.model_name
        }

    return {
        "id": sub.id,
        "submission_id": sub.id,
        "complaint_id": c.complaint_id,
        "version_number": sub.version_number,
        "status": sub.status,
        "after_photo_urls": [f"/api/authority/evidence/{sub.after_evidence.stored_filename}"] if sub.after_evidence else ["/assets/dept_rpw.jpg"],
        "department": {
            "id": c.department.id,
            "code": c.department.code,
            "name": c.department.name,
            "sla_days": c.department.sla_days
        } if c.department else None,
        "complaint": {
            "complaint_id": c.complaint_id,
            "category": c.category,
            "description": c.description,
            "latitude": c.latitude,
            "longitude": c.longitude,
            "location_source": c.location_source,
            "submission_channel": c.submission_channel,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "admin_status": c.admin_status
        },
        "resolution": {
            "work_completed_description": sub.work_completed_description,
            "repair_action_taken": sub.repair_action_taken,
            "field_notes": sub.field_notes,
            "completion_datetime": sub.completion_datetime.isoformat() if sub.completion_datetime else None,
            "submitted_by_name": sub.submitted_by.full_name if sub.submitted_by else "Field Engineer",
            "authority_notes": sub.authority_notes,
            "reviewed_by_name": sub.reviewed_by.full_name if sub.reviewed_by else None,
            "reviewed_at": sub.reviewed_at.isoformat() if sub.reviewed_at else None,
            "created_at": sub.created_at.isoformat() if sub.created_at else None
        },
        "before_evidence": {
            "id": sub.before_evidence.id,
            "original_filename": sub.before_evidence.original_filename,
            "view_url": f"/api/authority/evidence/{sub.before_evidence.stored_filename}"
        } if sub.before_evidence else None,
        "after_evidence": {
            "id": sub.after_evidence.id,
            "original_filename": sub.after_evidence.original_filename,
            "view_url": f"/api/authority/evidence/{sub.after_evidence.stored_filename}"
        } if sub.after_evidence else None,
        "all_evidence": evidence_list,
        "ai_analysis": ai_data
    }

@router.post("/resolutions/{submission_id}/verify-ai")
async def trigger_ai_resolution_advisory(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["authority_officer", "admin"]))
):
    """
    Triggers or retries Gemini AI advisory analysis of resolution evidence proof.
    """
    analysis = ResolutionVerificationService.run_ai_advisory_analysis(db, submission_id)
    return {
        "status": "ok",
        "submission_id": submission_id,
        "assessment": analysis.assessment,
        "evidence_relevance": analysis.evidence_relevance,
        "description_consistency": analysis.description_consistency,
        "visual_observations": analysis.visual_observations,
        "before_after_comparison": analysis.before_after_comparison,
        "missing_evidence": analysis.missing_evidence
    }

@router.post("/resolutions/{submission_id}/approve")
async def approve_and_close_resolution(
    submission_id: int,
    payload: ResolutionActionRequest = ResolutionActionRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["authority_officer"]))
):
    """
    Authority Officer approves work order resolution and marks complaint 'Closed'.
    """
    res = ResolutionVerificationService.approve_and_close(
        db=db,
        submission_id=submission_id,
        current_user=current_user,
        authority_notes=payload.notes or payload.verification_notes
    )
    res["reviewed_by_officer_name"] = current_user.full_name or "Authority Officer"
    return res

@router.post("/resolutions/{submission_id}/return")
async def return_resolution_for_correction(
    submission_id: int,
    payload: ResolutionReturnRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["authority_officer"]))
):
    """
    Authority Officer rejects incomplete work and returns it to the department with mandatory instructions.
    """
    corr_notes = (payload.correction_notes or payload.rejection_reason or "").strip()
    if not corr_notes:
        raise HTTPException(status_code=422, detail="Mandatory correction reason required.")
    return ResolutionVerificationService.return_for_correction(
        db=db,
        submission_id=submission_id,
        current_user=current_user,
        correction_notes=corr_notes
    )

@router.post("/resolutions/{submission_id}/request-evidence")
async def request_additional_resolution_evidence(
    submission_id: int,
    payload: ResolutionEvidenceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["authority_officer"]))
):
    """
    Authority Officer requests additional photographic or engineering proof while keeping ticket open.
    """
    req_details = (payload.requested_details or payload.evidence_request_notes or "").strip()
    if not req_details:
        raise HTTPException(status_code=422, detail="Evidence request details required.")
    return ResolutionVerificationService.request_additional_evidence(
        db=db,
        submission_id=submission_id,
        current_user=current_user,
        requested_details=req_details
    )
