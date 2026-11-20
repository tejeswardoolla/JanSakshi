"""
JanSakshi Phase 7 – Authority Dashboard & Civic Decision-Making Routes
Provides administrative overview KPIs, complaint management, human verification workflows,
department assignment, administrative status transitions, escalation controls, and audit trails.
"""

import os
import json
from typing import Optional, List
import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Header, UploadFile, File, Form, status
from fastapi.responses import FileResponse, StreamingResponse
import requests
import logging
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_, desc, asc

from app.database import get_db
from app.models.complaint import Complaint, PhysicalIssue, Evidence, ComplaintEvent, AIAnalysis, DuplicateMatch
from app.models.authority import Department, User
from app.core.security import get_current_user, require_roles, get_user_from_token_str
from app.core.config import utc_now, BASE_DIR
from app.services.storage_service import BLOB_READ_WRITE_TOKEN

logger = logging.getLogger("jansakshi.authority")

router = APIRouter(prefix="/api/authority", tags=["Authority Dashboard"])

# -------------------------------------------------------------
# Request / Response Schemas
# -------------------------------------------------------------

class VerificationActionRequest(BaseModel):
    notes: Optional[str] = None

class RejectionActionRequest(BaseModel):
    reason: str = Field(..., min_length=3, description="Mandatory justification for rejecting a complaint")

class InfoRequestActionRequest(BaseModel):
    notes: str = Field(..., min_length=3, description="Specific details or evidence requested from citizen")

class AssignmentActionRequest(BaseModel):
    department_id: int
    assigned_to_user_id: Optional[int] = None
    priority: Optional[str] = "High"
    expected_completion_days: Optional[int] = 7
    assignment_date: Optional[str] = None
    expected_completion_date: Optional[str] = None
    notes: Optional[str] = None

class StatusActionRequest(BaseModel):
    status: str
    notes: Optional[str] = None

class LocationUpdateRequest(BaseModel):
    latitude: float
    longitude: float
    location_source: Optional[str] = "manual"
    google_maps_url: Optional[str] = None
    notes: Optional[str] = None

class MarkReadyActionRequest(BaseModel):
    notes: Optional[str] = None

class ReturnCorrectionActionRequest(BaseModel):
    correction_notes: str = Field(..., min_length=4, description="Mandatory explanation of corrections required before resolution can be approved")

class EscalationActionRequest(BaseModel):
    escalation_level: int = Field(1, ge=1, le=2)
    reason: str = Field(..., min_length=5)
    escalated_to: Optional[str] = "Municipal Commissioner"

class InternalNoteRequest(BaseModel):
    notes: str = Field(..., min_length=1)

# -------------------------------------------------------------
# 1. Overview & Analytics
# -------------------------------------------------------------

@router.get("/overview")
async def get_authority_overview(
    department_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Computes real-time municipal dashboard metrics from real database records:
    - Core KPI counts (total, pending verification, verified, rejected, awaiting assignment, in progress, resolved, escalated)
    - Category distribution with percentage share
    - Status breakdown
    - Top geographical areas / landmarks
    - Department workload performance
    - High-priority complaints queue
    - Aging breakdown of unresolved complaints
    """
    now = utc_now()

    # Base query: scoped to department for department officers
    if current_user.role == "department_officer":
        authorized_ids = current_user.get_authorized_department_ids()
        if not authorized_ids:
            raise HTTPException(status_code=403, detail="Department officer not assigned to any municipal department.")

        if department_id is not None:
            if department_id not in authorized_ids:
                raise HTTPException(
                    status_code=403,
                    detail=f"Access forbidden: You do not have authorization for department {department_id}."
                )
            target_dept_id = department_id
        else:
            target_dept_id = current_user.department_id or authorized_ids[0]

        all_complaints = db.query(Complaint).filter(Complaint.assigned_department_id == target_dept_id).all()
        departments = db.query(Department).filter(Department.id == target_dept_id, Department.is_active == True).all()
    else:
        if department_id is not None:
            all_complaints = db.query(Complaint).filter(Complaint.assigned_department_id == department_id).all()
            departments = db.query(Department).filter(Department.id == department_id, Department.is_active == True).all()
        else:
            all_complaints = db.query(Complaint).all()
            departments = db.query(Department).filter(Department.is_active == True).all()

    total_complaints = len(all_complaints)

    pending_verification = sum(1 for c in all_complaints if c.verification_status == "pending")
    verified_complaints = sum(1 for c in all_complaints if c.verification_status == "verified")
    rejected_complaints = sum(1 for c in all_complaints if c.verification_status == "rejected")
    info_requested_complaints = sum(1 for c in all_complaints if c.verification_status == "info_requested")

    awaiting_assignment = sum(
        1 for c in all_complaints
        if c.verification_status == "verified" and c.assigned_department_id is None and c.admin_status not in ("Resolved", "Rejected")
    )
    in_progress = sum(1 for c in all_complaints if c.admin_status in ("In Progress", "Assigned"))
    resolved_complaints = sum(1 for c in all_complaints if c.admin_status == "Resolved" or c.status == "Resolved")
    escalated_complaints = sum(1 for c in all_complaints if (c.escalation_level or 0) > 0 or c.admin_status == "Escalated")

    # Role 1 (Admin) Specific Operational KPIs
    active_complaints = [c for c in all_complaints if c.status != "Rejected" and c.admin_status != "Rejected" and c.verification_status != "rejected"]
    pending_intake = [c for c in active_complaints if c.verification_status == "pending" and c.status not in ("Closed", "Resolved")]
    awaiting_ai_processing = sum(1 for c in pending_intake if not c.ai_analyses or any(a.analysis_status == "pending" for a in c.ai_analyses))
    awaiting_location_review = sum(1 for c in pending_intake if c.latitude is None or c.longitude is None or c.location_source in ("missing", "email_parsed", "email_pending_clarification"))
    duplicate_candidates_pending = db.query(DuplicateMatch).filter(DuplicateMatch.review_status == "pending").count()
    ready_for_officer = sum(1 for c in pending_intake if c.admin_status == "Ready for Authority Officer")

    # Role 2 (Authority Officer) Specific Operational KPIs
    # Strictly Admin-prepared, intake-complete grievances awaiting authoritative civic decision
    awaiting_decision = sum(
        1 for c in all_complaints
        if c.admin_status == "Ready for Authority Officer" and c.verification_status == "pending" and c.latitude is not None and c.longitude is not None
    )
    active_work_orders = sum(1 for c in all_complaints if c.admin_status in ("Assigned", "In Progress", "Under Inspection", "Resolution Submitted"))
    resolution_submitted = sum(1 for c in all_complaints if c.admin_status == "Resolution Submitted")

    # Role 3 (Department Officer) Field KPIs
    pending_inspections = sum(1 for c in all_complaints if c.admin_status in ("Assigned", "Pending Inspection") and c.verification_status == "verified")
    in_progress_repairs = sum(1 for c in all_complaints if c.admin_status == "In Progress")

    # Category distribution
    cat_counts = {}
    for c in all_complaints:
        cat = c.category or "Uncategorized"
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    category_distribution = [
        {
            "category": cat,
            "count": count,
            "percentage": round((count / total_complaints * 100), 1) if total_complaints > 0 else 0
        }
        for cat, count in sorted(cat_counts.items(), key=lambda x: x[1], reverse=True)
    ]

    # Status distribution
    status_counts = {}
    for c in all_complaints:
        st = c.admin_status or c.status or "Received"
        status_counts[st] = status_counts.get(st, 0) + 1

    status_distribution = [
        {"status": st, "count": count}
        for st, count in sorted(status_counts.items(), key=lambda x: x[1], reverse=True)
    ]

    # Geographical area distribution
    area_counts = {}
    for c in all_complaints:
        # Check description or email message or coordinates
        loc = "Coordinates Available" if (c.latitude and c.longitude) else "Awaiting Geolocation"
        if c.google_maps_url:
            loc = "Mapped Location"
        area_counts[loc] = area_counts.get(loc, 0) + 1

    area_distribution = [
        {"area": loc, "count": count}
        for loc, count in sorted(area_counts.items(), key=lambda x: x[1], reverse=True)
    ]

    # Department performance & workload
    if 'departments' not in locals() or not departments:
        departments = db.query(Department).filter(Department.is_active == True).all()
    department_metrics = []
    for d in departments:
        dept_complaints = [c for c in all_complaints if c.assigned_department_id == d.id]
        assigned_c = len(dept_complaints)
        in_prog_c = sum(1 for c in dept_complaints if c.admin_status in ("In Progress", "Assigned"))
        res_c = sum(1 for c in dept_complaints if c.admin_status == "Resolved" or c.status == "Resolved")
        pending_c = sum(1 for c in dept_complaints if c.admin_status not in ("Resolved", "Rejected"))

        department_metrics.append({
            "id": d.id,
            "name": d.name,
            "code": d.code,
            "sla_days": d.sla_days,
            "head_name": d.head_name,
            "total_assigned": assigned_c,
            "in_progress": in_prog_c,
            "resolved": res_c,
            "pending": pending_c
        })

    # High priority queue (Critical/High severity, escalated > 0, or unresolved > 48h)
    high_priority_list = []
    for c in all_complaints:
        if c.admin_status in ("Resolved", "Rejected"):
            continue

        is_escalated = (c.escalation_level or 0) > 0
        latest_ai = c.ai_analyses[0] if c.ai_analyses else None
        severity = latest_ai.recommended_severity if latest_ai else "Medium"

        # Calculate age in hours
        created_time = c.created_at
        if created_time.tzinfo is None:
            created_time = created_time.replace(tzinfo=datetime.timezone.utc)
        age_hours = (now - created_time).total_seconds() / 3600.0

        is_high_sev = severity in ("High", "Critical", "high", "critical")
        is_overdue = age_hours > 48

        if is_escalated or is_high_sev or is_overdue:
            high_priority_list.append({
                "complaint_id": c.complaint_id,
                "category": c.category,
                "description": c.description[:120] + "..." if len(c.description) > 120 else c.description,
                "severity": severity,
                "escalation_level": c.escalation_level or 0,
                "age_hours": round(age_hours, 1),
                "admin_status": c.admin_status or c.status,
                "verification_status": c.verification_status,
                "department_code": c.department.code if c.department else None,
                "created_at": c.created_at.isoformat() if c.created_at else None
            })

    high_priority_list.sort(key=lambda x: (x["escalation_level"], x["severity"] in ("Critical", "critical"), x["age_hours"]), reverse=True)

    # Aging breakdown of unresolved complaints
    aging_breakdown = {
        "under_24h": 0,
        "24h_to_48h": 0,
        "3d_to_7d": 0,
        "over_7d": 0
    }
    for c in all_complaints:
        if c.admin_status in ("Resolved", "Rejected") or c.status in ("Resolved", "Rejected"):
            continue
        c_time = c.created_at
        if c_time.tzinfo is None:
            c_time = c_time.replace(tzinfo=datetime.timezone.utc)
        age_h = (now - c_time).total_seconds() / 3600.0

        if age_h < 24:
            aging_breakdown["under_24h"] += 1
        elif age_h < 48:
            aging_breakdown["24h_to_48h"] += 1
        elif age_h < 168: # 7 days
            aging_breakdown["3d_to_7d"] += 1
        else:
            aging_breakdown["over_7d"] += 1

    # Recent activity events (last 12 events)
    if current_user.role == "department_officer":
        recent_events = (
            db.query(ComplaintEvent)
            .join(Complaint, ComplaintEvent.complaint_id == Complaint.complaint_id)
            .filter(Complaint.assigned_department_id == target_dept_id)
            .order_by(ComplaintEvent.created_at.desc())
            .limit(12)
            .all()
        )
    elif department_id is not None:
        recent_events = (
            db.query(ComplaintEvent)
            .join(Complaint, ComplaintEvent.complaint_id == Complaint.complaint_id)
            .filter(Complaint.assigned_department_id == department_id)
            .order_by(ComplaintEvent.created_at.desc())
            .limit(12)
            .all()
        )
    else:
        recent_events = (
            db.query(ComplaintEvent)
            .order_by(ComplaintEvent.created_at.desc())
            .limit(12)
            .all()
        )
    activity_log = [
        {
            "id": ev.id,
            "complaint_id": ev.complaint_id,
            "event_type": ev.event_type,
            "description": ev.description,
            "source": ev.source,
            "created_at": ev.created_at.isoformat() if ev.created_at else None
        }
        for ev in recent_events
    ]

    return {
        "kpis": {
            "total_complaints": total_complaints,
            "pending_verification": pending_verification,
            "verified_complaints": verified_complaints,
            "rejected_complaints": rejected_complaints,
            "info_requested": info_requested_complaints,
            "awaiting_assignment": awaiting_assignment,
            "in_progress": in_progress,
            "resolved_complaints": resolved_complaints,
            "escalated_complaints": escalated_complaints,
            # Admin KPIs
            "awaiting_ai_processing": awaiting_ai_processing,
            "awaiting_location_review": awaiting_location_review,
            "duplicate_candidates_pending": duplicate_candidates_pending,
            "ready_for_officer": ready_for_officer,
            # Authority Officer KPIs
            "awaiting_decision": awaiting_decision,
            "accepted_complaints": verified_complaints,
            "awaiting_department_assignment": awaiting_assignment,
            "active_work_orders": active_work_orders,
            "resolution_submitted": resolution_submitted,
            # Department Officer KPIs
            "assigned_work_orders": total_complaints,
            "pending_inspections": pending_inspections,
            "in_progress_repairs": in_progress_repairs,
        },
        "category_distribution": category_distribution,
        "status_distribution": status_distribution,
        "area_distribution": area_distribution,
        "department_metrics": department_metrics,
        "high_priority_queue": high_priority_list[:10],
        "aging_breakdown": aging_breakdown,
        "recent_activity": activity_log
    }

# -------------------------------------------------------------
# 2. Complaints Table / List with Rich Filtering
# -------------------------------------------------------------

def compute_ai_status(latest_ai) -> str:
    """Returns canonical AI processing status: Pending, Processing, Completed, Failed."""
    if not latest_ai:
        return "Pending"
    st = (latest_ai.analysis_status or "").lower()
    if st == "completed":
        return "Completed"
    elif st == "failed":
        return "Failed"
    elif st in ("processing", "running"):
        return "Processing"
    return "Pending"

def compute_preparation_status(c, latest_ai) -> str:
    """
    Computes distinct Admin Preparation Status:
    - Rejected / Non-Civic
    - Awaiting Information
    - Ready for Authority Officer
    - Under Preparation
    - Pending Review
    """
    if c.status == "Rejected" or c.verification_status == "rejected" or c.admin_status == "Rejected":
        return "Rejected / Non-Civic"
    if c.rejection_reason and "Non-civic" in c.rejection_reason:
        return "Rejected / Non-Civic"

    if c.verification_status == "info_requested":
        return "Awaiting Information"
    if (c.latitude is None or c.longitude is None or c.location_source in ("missing", "email_pending_clarification")) and c.verification_status == "pending" and c.status not in ("Closed", "Resolved"):
        return "Awaiting Information"

    if c.admin_status == "Ready for Authority Officer":
        return "Ready for Authority Officer"
    if c.verification_status == "verified" or c.status in ("Verified", "Assigned", "In Progress", "Resolution Submitted", "Returned for Correction", "Closed", "Resolved") or c.assigned_department_id is not None:
        return "Ready for Authority Officer"

    ai_status = compute_ai_status(latest_ai)
    if ai_status == "Completed" or (c.latitude is not None and c.longitude is not None):
        return "Under Preparation"

    return "Pending Review"

def can_mark_complaint_ready(c, prep_status: str) -> bool:
    """
    Validation gate for whether Admin can click 'Mark Ready':
    - Genuine civic complaint (not rejected)
    - Not already marked ready
    - Still in intake (verification_status == pending, status == Received)
    - Grounded location coordinates available
    - prep_status in Pending Review or Under Preparation
    """
    if c.status == "Rejected" or c.verification_status == "rejected":
        return False
    if c.verification_status != "pending" or c.status in ("Closed", "Resolved", "In Progress", "Assigned", "Resolution Submitted"):
        return False
    if c.admin_status == "Ready for Authority Officer":
        return False
    if c.latitude is None or c.longitude is None or c.location_source in ("missing", "email_pending_clarification"):
        return False
    return prep_status in ("Pending Review", "Under Preparation")

def compute_lifecycle_status(c) -> str:
    """Returns canonical complaint lifecycle status."""
    st = c.status or "Received"
    if st == "Assigned" or (st == "Received" and c.assigned_department_id is not None and c.verification_status == "verified"):
        return "Department Assigned"
    return st

@router.get("/complaints")
async def list_authority_complaints(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    verification_status: Optional[str] = None,
    admin_status: Optional[str] = None,
    channel: Optional[str] = None,
    department_id: Optional[int] = None,
    severity: Optional[str] = None,
    escalation_level: Optional[int] = None,
    sort_by: str = Query("created_at", regex="^(created_at|complaint_id|category|status|admin_status|verification_status)$"),
    sort_dir: str = Query("desc", regex="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Search, filter, sort, and paginate complaints for authority officers.
    Role-based scoping: department officers can optionally filter by their assigned department.
    """
    query = db.query(Complaint)

    # Department officer strict scoping
    if current_user.role == "department_officer":
        authorized_ids = current_user.get_authorized_department_ids()
        if not authorized_ids:
            raise HTTPException(
                status_code=403,
                detail="Department officer account is not assigned to any municipal department."
            )
        if department_id is not None:
            if department_id not in authorized_ids:
                raise HTTPException(
                    status_code=403,
                    detail="Access forbidden: Department officers can only view complaints assigned to their department."
                )
            target_dept_id = department_id
        else:
            target_dept_id = current_user.department_id or authorized_ids[0]
        query = query.filter(Complaint.assigned_department_id == target_dept_id)
    elif department_id is not None:
        query = query.filter(Complaint.assigned_department_id == department_id)

    if search:
        search_term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Complaint.complaint_id.ilike(search_term),
                Complaint.description.ilike(search_term),
                Complaint.citizen_name.ilike(search_term),
                Complaint.citizen_email.ilike(search_term)
            )
        )

    if category:
        query = query.filter(Complaint.category.ilike(category.strip()))

    if status:
        query = query.filter(or_(Complaint.admin_status == status, Complaint.status == status))

    if admin_status:
        query = query.filter(Complaint.admin_status == admin_status)

    if channel:
        query = query.filter(Complaint.submission_channel == channel)

    if verification_status:
        query = query.filter(Complaint.verification_status == verification_status)
        # Authority Officer Decision Queue Gate:
        # Only Admin-prepared, intake-complete complaints ('Ready for Authority Officer') with grounded GPS coordinates
        # enter the Authority Officer's pending decision queue. Records awaiting location clarification,
        # missing essential information, or non-civic review must remain in the Admin workflow.
        if current_user.role == "authority_officer" and verification_status == "pending" and not admin_status:
            query = query.filter(
                Complaint.admin_status == "Ready for Authority Officer",
                Complaint.latitude.isnot(None),
                Complaint.longitude.isnot(None)
            )

    if escalation_level is not None:
        query = query.filter(Complaint.escalation_level >= escalation_level)

    total_count = query.count()

    # Sorting
    sort_col = getattr(Complaint, sort_by, Complaint.created_at)
    if sort_dir == "asc":
        query = query.order_by(asc(sort_col))
    else:
        query = query.order_by(desc(sort_col))

    complaints_page = query.offset((page - 1) * limit).limit(limit).all()

    items = []
    for c in complaints_page:
        latest_ai = c.ai_analyses[0] if c.ai_analyses else None

        # Check severity filter in python if specified
        ai_sev = latest_ai.recommended_severity if latest_ai else "Medium"
        if severity and ai_sev.lower() != severity.lower():
            continue

        prep_status = compute_preparation_status(c, latest_ai)
        can_mark = can_mark_complaint_ready(c, prep_status)
        ai_st = compute_ai_status(latest_ai)
        lifecycle_st = compute_lifecycle_status(c)

        items.append({
            "id": c.id,
            "complaint_id": c.complaint_id,
            "tracking_token": c.tracking_token,
            "category": c.category,
            "description": c.description,
            "latitude": c.latitude,
            "longitude": c.longitude,
            "location_source": c.location_source,
            "google_maps_url": c.google_maps_url,
            "citizen_name": c.citizen_name,
            "citizen_email": c.citizen_email,
            "citizen_phone": c.citizen_phone,
            "submission_channel": c.submission_channel,
            "status": c.status,
            "lifecycle_status": lifecycle_st,
            "admin_status": c.admin_status or c.status,
            "preparation_status": prep_status,
            "ai_status": ai_st,
            "can_mark_ready": can_mark,
            "verification_status": c.verification_status,
            "verified_at": c.verified_at.isoformat() if c.verified_at else None,
            "verified_by_name": c.verified_by_name,
            "rejection_reason": c.rejection_reason,
            "info_request_notes": c.info_request_notes,
            "department": {
                "id": c.department.id,
                "name": c.department.name,
                "code": c.department.code
            } if c.department else None,
            "assigned_user": {
                "id": c.assigned_user.id,
                "full_name": c.assigned_user.full_name,
                "email": c.assigned_user.email
            } if c.assigned_user else None,
            "assigned_at": c.assigned_at.isoformat() if c.assigned_at else None,
            "assignment_notes": c.assignment_notes,
            "escalation_level": c.escalation_level or 0,
            "escalation_reason": c.escalation_reason,
            "escalated_at": c.escalated_at.isoformat() if c.escalated_at else None,
            "escalated_to": c.escalated_to,
            "internal_notes": c.internal_notes,
            "evidence_count": len(c.evidence_files),
            "ai_severity": ai_sev,
            "ai_confidence": latest_ai.category_confidence if latest_ai else None,
            "ai_problem": latest_ai.visible_problem if latest_ai else None,
            "duplicate_matches_count": len(c.duplicate_matches),
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        })

    return {
        "page": page,
        "limit": limit,
        "total": total_count,
        "items": items
    }

# -------------------------------------------------------------
# 3. Single Complaint Details with Evidence & Full Audit History
# -------------------------------------------------------------

@router.get("/complaints/{complaint_id}")
async def get_authority_complaint_detail(
    complaint_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve full details of a complaint for evidence inspection and administrative review."""
    clean_id = complaint_id.strip()
    c = db.query(Complaint).filter(Complaint.complaint_id == clean_id).first()
    if not c:
        raise HTTPException(status_code=404, detail=f"Complaint '{clean_id}' not found.")

    # Department officer access restriction
    if current_user.role == "department_officer":
        if c.assigned_department_id not in current_user.get_authorized_department_ids():
            raise HTTPException(
                status_code=403,
                detail="Access forbidden: Department officers can only access complaints assigned to their division."
            )

    # Evidence files with URLs
    evidence_list = []
    for ev in c.evidence_files:
        evidence_list.append({
            "id": ev.id,
            "original_filename": ev.original_filename,
            "stored_filename": ev.stored_filename,
            "file_type": ev.file_type,
            "file_size": ev.file_size,
            "status": "stored",
            "view_url": f"/api/authority/evidence/{ev.stored_filename}",
            "created_at": ev.created_at.isoformat() if ev.created_at else None
        })

    # Failed email attachments if any (e.g. cloud upload failed in production)
    failed_evidence_list = []
    for em in c.email_messages:
        if em.attachments_info:
            try:
                raw_info = json.loads(em.attachments_info)
                for item in raw_info:
                    if isinstance(item, dict) and item.get("status") == "upload_failed":
                        failed_evidence_list.append({
                            "original_filename": item.get("filename"),
                            "file_size": item.get("file_size"),
                            "file_type": item.get("file_type"),
                            "status": "upload_failed",
                            "error": item.get("error", "Cloud storage upload failed"),
                            "view_url": None,
                            "email_message_id": em.gmail_message_id
                        })
            except Exception:
                pass

    # AI Analyses list
    ai_list = []
    for ai in c.ai_analyses:
        ai_list.append({
            "id": ai.id,
            "analysis_status": ai.analysis_status,
            "predicted_category": ai.predicted_category,
            "category_confidence": ai.category_confidence,
            "complaint_summary": ai.complaint_summary,
            "visible_problem": ai.visible_problem,
            "evidence_relevance": ai.evidence_relevance,
            "relevance_score": ai.relevance_score,
            "image_quality": ai.image_quality,
            "clarity_score": ai.clarity_score,
            "visibility_score": ai.visibility_score,
            "additional_evidence_required": ai.additional_evidence_required,
            "recommended_severity": ai.recommended_severity,
            "severity_confidence": ai.severity_confidence,
            "reasoning": ai.reasoning,
            "human_review_required": ai.human_review_required,
            "review_reasons": ai.review_reasons,
            "model_name": ai.model_name,
            "created_at": ai.created_at.isoformat() if ai.created_at else None
        })

    # Duplicate matches
    dup_list = []
    for m in c.duplicate_matches:
        cand_issue = None
        if m.physical_issue:
            cand_issue = {
                "issue_reference_id": m.physical_issue.issue_reference_id,
                "category": m.physical_issue.category,
                "current_status": m.physical_issue.current_status,
                "representative_latitude": m.physical_issue.representative_latitude,
                "representative_longitude": m.physical_issue.representative_longitude,
                "representative_location": m.physical_issue.representative_location,
                "complaint_count": len(m.physical_issue.complaints)
            }
        dup_list.append({
            "id": m.id,
            "candidate_physical_issue_id": m.candidate_physical_issue_id,
            "similarity_score": m.similarity_score,
            "confidence_level": m.confidence_level,
            "recommendation": m.recommendation,
            "matching_explanation": m.matching_explanation,
            "review_status": m.review_status,
            "candidate_issue": cand_issue,
            "created_at": m.created_at.isoformat() if m.created_at else None
        })

    # Audit Events timeline
    events_list = []
    for ev in c.audit_events:
        events_list.append({
            "id": ev.id,
            "event_type": ev.event_type,
            "previous_value": ev.previous_value,
            "new_value": ev.new_value,
            "description": ev.description,
            "source": ev.source,
            "created_at": ev.created_at.isoformat() if ev.created_at else None
        })

    # Sanitize internal notes for department officers (mask executive deliberations)
    sanitized_internal_notes = c.internal_notes
    if current_user.role == "department_officer" and sanitized_internal_notes:
        entries = sanitized_internal_notes.split("\n\n")
        masked_entries = []
        for e in entries:
            if "(admin)" in e or "(authority_officer)" in e:
                if "):" in e:
                    header, _ = e.split("):", 1)
                    masked_entries.append(f"{header}): [Executive Administrative Note — Confidential to Municipal Leadership]")
                else:
                    masked_entries.append("[Executive Administrative Note — Confidential to Municipal Leadership]")
            else:
                masked_entries.append(e)
        sanitized_internal_notes = "\n\n".join(masked_entries)

    return {
        "id": c.id,
        "complaint_id": c.complaint_id,
        "tracking_token": c.tracking_token,
        "category": c.category,
        "description": c.description,
        "latitude": c.latitude,
        "longitude": c.longitude,
        "location_accuracy": c.location_accuracy,
        "location_source": c.location_source,
        "google_maps_url": c.google_maps_url,
        "citizen_name": c.citizen_name,
        "citizen_email": c.citizen_email,
        "citizen_phone": c.citizen_phone,
        "submission_channel": c.submission_channel,
        "status": c.status,
        "lifecycle_status": compute_lifecycle_status(c),
        "admin_status": c.admin_status or c.status,
        "preparation_status": compute_preparation_status(c, c.ai_analyses[0] if c.ai_analyses else None),
        "ai_status": compute_ai_status(c.ai_analyses[0] if c.ai_analyses else None),
        "can_mark_ready": can_mark_complaint_ready(c, compute_preparation_status(c, c.ai_analyses[0] if c.ai_analyses else None)),
        "verification_status": c.verification_status,
        "verified_at": c.verified_at.isoformat() if c.verified_at else None,
        "verified_by_user_id": c.verified_by_user_id,
        "verified_by_name": c.verified_by_name,
        "rejection_reason": c.rejection_reason,
        "info_request_notes": c.info_request_notes,
        "department": {
            "id": c.department.id,
            "name": c.department.name,
            "code": c.department.code,
            "sla_days": c.department.sla_days,
            "contact_email": c.department.contact_email
        } if c.department else None,
        "assigned_user": {
            "id": c.assigned_user.id,
            "full_name": c.assigned_user.full_name,
            "email": c.assigned_user.email
        } if c.assigned_user else None,
        "assigned_at": c.assigned_at.isoformat() if c.assigned_at else None,
        "assignment_notes": c.assignment_notes,
        "escalation_level": c.escalation_level or 0,
        "escalation_reason": c.escalation_reason,
        "escalated_at": c.escalated_at.isoformat() if c.escalated_at else None,
        "escalated_to": c.escalated_to,
        "internal_notes": sanitized_internal_notes,
        "evidence": evidence_list,
        "failed_evidence": failed_evidence_list,
        "ai_analyses": ai_list,
        "duplicate_matches": dup_list,
        "audit_events": events_list,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }

# -------------------------------------------------------------
# -------------------------------------------------------------
# 4. Admin Complaint Preparation & Location Review
# -------------------------------------------------------------

@router.post("/complaints/{complaint_id}/mark-ready")
async def mark_complaint_ready_for_officer(
    complaint_id: str,
    payload: MarkReadyActionRequest = MarkReadyActionRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"]))
):
    """
    Admin Preparation Action:
    Marks complaint ready for Authority Officer review after AI extraction,
    location verification, and duplicate screening are completed.
    Does NOT mean the civic complaint has been verified as genuine.
    """
    clean_id = complaint_id.strip()
    c = db.query(Complaint).filter(Complaint.complaint_id == clean_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Complaint not found.")

    # 1. Submission must not be non-civic or rejected
    if c.status == "Rejected" or c.verification_status == "rejected" or "Non-civic" in (c.rejection_reason or ""):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot mark ready: Complaint '{c.complaint_id}' was rejected as non-civic ({c.rejection_reason or 'Non-civic'})."
        )

    # 2. Complaint must not already be in post-intake lifecycle stage
    if c.verification_status != "pending" or c.status in ("Closed", "Resolved", "In Progress", "Assigned", "Resolution Submitted"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot mark ready: Complaint '{c.complaint_id}' has already progressed to lifecycle status '{c.status}' (verification: {c.verification_status})."
        )

    # 3. Mandatory location requirements
    if c.latitude is None or c.longitude is None or c.location_source in ("missing", "email_pending_clarification"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot mark ready: Complaint '{c.complaint_id}' is missing mandatory GPS coordinates. Please update location first."
        )

    prev_status = c.admin_status
    c.admin_status = "Ready for Authority Officer"
    c.updated_at = utc_now()

    note_text = f" Notes: {payload.notes.strip()}" if payload.notes and payload.notes.strip() else ""
    event = ComplaintEvent(
        complaint_id=c.complaint_id,
        event_type="intake_prepared_for_officer",
        previous_value=prev_status,
        new_value="Ready for Authority Officer",
        description=f"Complaint intake reviewed and marked Ready for Authority Officer by Admin {current_user.full_name} ({current_user.username}).{note_text}",
        source="admin",
        created_at=utc_now()
    )
    db.add(event)
    db.commit()
    db.refresh(c)

    latest_ai = c.ai_analyses[0] if c.ai_analyses else None
    prep_status = compute_preparation_status(c, latest_ai)

    return {
        "status": "ok",
        "message": f"Complaint {c.complaint_id} marked Ready for Authority Officer.",
        "admin_status": c.admin_status,
        "preparation_status": prep_status,
        "complaint_id": c.complaint_id
    }

@router.put("/complaints/{complaint_id}/location")
async def update_complaint_location(
    complaint_id: str,
    payload: LocationUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"]))
):
    """
    Admin Location Management:
    Confirm or correct GPS coordinates, address, or Maps URL using evidence.
    """
    clean_id = complaint_id.strip()
    c = db.query(Complaint).filter(Complaint.complaint_id == clean_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Complaint not found.")

    prev_coords = f"({c.latitude}, {c.longitude})"
    c.latitude = payload.latitude
    c.longitude = payload.longitude
    if payload.location_source:
        c.location_source = payload.location_source
    if payload.google_maps_url:
        c.google_maps_url = payload.google_maps_url

    event = ComplaintEvent(
        complaint_id=c.complaint_id,
        event_type="location_reviewed_by_admin",
        previous_value=prev_coords,
        new_value=f"({payload.latitude}, {payload.longitude})",
        description=f"Incident coordinates reviewed and verified by Admin {current_user.full_name}. Source: {payload.location_source}.",
        source="admin"
    )
    db.add(event)
    db.commit()
    db.refresh(c)

    return {
        "status": "ok",
        "message": "Complaint location updated successfully.",
        "complaint_id": c.complaint_id,
        "latitude": c.latitude,
        "longitude": c.longitude,
        "location_source": c.location_source,
        "google_maps_url": c.google_maps_url
    }

# -------------------------------------------------------------
# 5. Authority Officer Decisions & Department Assignment
# -------------------------------------------------------------

@router.post("/complaints/{complaint_id}/verify")
async def verify_complaint(
    complaint_id: str,
    payload: VerificationActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["authority_officer"]))
):
    """
    Authority Officer Civic Decision:
    Accept complaint for departmental action. Transitions from pending to verified.
    Advances admin status to 'Awaiting Department Assignment' if unassigned.
    """
    c = db.query(Complaint).filter(Complaint.complaint_id == complaint_id.strip()).first()
    if not c:
        raise HTTPException(status_code=404, detail="Complaint not found.")

    prev_status = c.verification_status
    c.verification_status = "verified"
    c.verified_at = utc_now()
    c.verified_by_user_id = current_user.id
    c.verified_by_name = current_user.full_name

    # Advance administrative status
    if c.assigned_department_id is None:
        c.admin_status = "Awaiting Department Assignment"
    else:
        c.admin_status = "Assigned"

    note_text = f" Notes: {payload.notes}" if payload.notes else ""
    event = ComplaintEvent(
        complaint_id=c.complaint_id,
        event_type="human_verification_approved",
        previous_value=prev_status,
        new_value="verified",
        description=f"Human civic decision approved by Authority Officer {current_user.full_name}.{note_text}",
        source="authority_officer"
    )
    db.add(event)
    db.commit()
    db.refresh(c)

    return {
        "status": "ok",
        "message": f"Complaint {c.complaint_id} verified successfully.",
        "verification_status": c.verification_status,
        "admin_status": c.admin_status,
        "verified_by": c.verified_by_name,
        "verified_at": c.verified_at.isoformat()
    }

@router.post("/complaints/{complaint_id}/reject")
async def reject_complaint(
    complaint_id: str,
    payload: RejectionActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["authority_officer"]))
):
    """
    Authority Officer Civic Decision:
    Reject complaint with mandatory justification.
    Updates status to 'Rejected' and records reason in audit trail.
    """
    c = db.query(Complaint).filter(Complaint.complaint_id == complaint_id.strip()).first()
    if not c:
        raise HTTPException(status_code=404, detail="Complaint not found.")

    prev_status = c.verification_status
    c.verification_status = "rejected"
    c.rejection_reason = payload.reason.strip()
    c.admin_status = "Rejected"
    c.status = "Rejected"

    event = ComplaintEvent(
        complaint_id=c.complaint_id,
        event_type="human_verification_rejected",
        previous_value=prev_status,
        new_value="rejected",
        description=f"Complaint rejected by Authority Officer {current_user.full_name}. Reason: {c.rejection_reason}",
        source="authority_officer"
    )
    db.add(event)
    db.commit()
    db.refresh(c)

    return {
        "status": "ok",
        "message": f"Complaint {c.complaint_id} rejected.",
        "verification_status": c.verification_status,
        "rejection_reason": c.rejection_reason,
        "admin_status": c.admin_status
    }

@router.post("/complaints/{complaint_id}/request-info")
async def request_additional_info(
    complaint_id: str,
    payload: InfoRequestActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["authority_officer"]))
):
    """
    Authority Officer Civic Decision:
    Request additional information or clearer evidence from citizen.
    Logs requirement in audit trail.
    """
    c = db.query(Complaint).filter(Complaint.complaint_id == complaint_id.strip()).first()
    if not c:
        raise HTTPException(status_code=404, detail="Complaint not found.")

    prev_status = c.verification_status
    c.verification_status = "info_requested"
    c.info_request_notes = payload.notes.strip()

    event = ComplaintEvent(
        complaint_id=c.complaint_id,
        event_type="additional_info_requested",
        previous_value=prev_status,
        new_value="info_requested",
        description=f"Additional information requested by Authority Officer {current_user.full_name}: {c.info_request_notes}",
        source="authority_officer"
    )
    db.add(event)
    db.commit()
    db.refresh(c)

    return {
        "status": "ok",
        "message": "Additional information requested from citizen.",
        "verification_status": c.verification_status,
        "info_request_notes": c.info_request_notes
    }

@router.post("/complaints/{complaint_id}/assign")
async def assign_department(
    complaint_id: str,
    payload: AssignmentActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["authority_officer"]))
):
    """
    Authority Officer Department Dispatch:
    Assign complaint to a municipal department, select an authorized department officer,
    set priority, set deadline / expected completion days, and dispatch work order.
    """
    c = db.query(Complaint).filter(Complaint.complaint_id == complaint_id.strip()).first()
    if not c:
        raise HTTPException(status_code=404, detail="Complaint not found.")

    dept = db.query(Department).filter(Department.id == payload.department_id, Department.is_active == True).first()
    if not dept:
        raise HTTPException(status_code=400, detail="Invalid department ID or department is inactive.")

    assigned_user_name = None
    if payload.assigned_to_user_id:
        target_user = db.query(User).filter(User.id == payload.assigned_to_user_id).first()
        if not target_user:
            raise HTTPException(status_code=400, detail="Assigned officer user not found.")
        # Validate that officer belongs to or has access to this department
        if target_user.department_id and target_user.department_id != dept.id and dept.id not in target_user.get_authorized_department_ids():
            raise HTTPException(status_code=400, detail=f"User '{target_user.full_name}' does not belong to {dept.name}.")
        assigned_user_name = target_user.full_name

    priority = payload.priority or "High"
    deadline_days = payload.expected_completion_days or dept.sla_days or 7
    instructions = payload.notes.strip() if payload.notes else ""
    full_notes_parts = [f"Priority: {priority}"]
    if payload.assignment_date:
        full_notes_parts.append(f"Assignment Date: {payload.assignment_date}")
    if payload.expected_completion_date:
        full_notes_parts.append(f"Expected Completion: {payload.expected_completion_date}")
    else:
        full_notes_parts.append(f"Expected Completion: {deadline_days} days")
    if instructions:
        full_notes_parts.append(f"Instructions: {instructions}")
    full_assignment_notes = " | ".join(full_notes_parts)

    c.assigned_department_id = dept.id
    c.assigned_to_user_id = payload.assigned_to_user_id
    c.assigned_at = utc_now()
    c.assignment_notes = full_assignment_notes
    c.admin_status = "Assigned"
    c.status = "Assigned"

    user_text = f" and assigned to officer {assigned_user_name}" if assigned_user_name else ""
    event = ComplaintEvent(
        complaint_id=c.complaint_id,
        event_type="department_assigned",
        new_value=dept.code,
        description=f"Assigned to {dept.name} ({dept.code}){user_text} by Authority Officer {current_user.full_name}. ({full_assignment_notes})",
        source="authority_officer"
    )
    db.add(event)
    db.commit()
    db.refresh(c)

    return {
        "status": "ok",
        "message": f"Complaint {c.complaint_id} assigned to {dept.name}.",
        "department_id": dept.id,
        "department_name": dept.name,
        "department_code": dept.code,
        "priority": priority,
        "expected_completion_days": deadline_days,
        "admin_status": c.admin_status,
        "assigned_at": c.assigned_at.isoformat()
    }

@router.post("/complaints/{complaint_id}/return-correction")
async def return_work_for_correction(
    complaint_id: str,
    payload: ReturnCorrectionActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["authority_officer"]))
):
    """
    Authority Officer Resolution Review:
    Returns submitted work back to the department officer when evidence or repair is insufficient.
    Requires an explanatory note.
    """
    clean_id = complaint_id.strip()
    c = db.query(Complaint).filter(Complaint.complaint_id == clean_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Complaint not found.")

    prev_status = c.admin_status
    c.admin_status = "In Progress"
    c.status = "In Progress"

    event = ComplaintEvent(
        complaint_id=c.complaint_id,
        event_type="resolution_returned_for_correction",
        previous_value=prev_status,
        new_value="In Progress",
        description=f"Resolution work returned for correction by Authority Officer {current_user.full_name}. Requirement: {payload.correction_notes}",
        source="authority_officer"
    )
    db.add(event)
    db.commit()
    db.refresh(c)

    return {
        "status": "ok",
        "message": f"Work order for complaint {c.complaint_id} returned to department for correction.",
        "admin_status": c.admin_status,
        "correction_notes": payload.correction_notes
    }

# -------------------------------------------------------------
# 6. Administrative Status Progression (Lifecycle Workflow)
# -------------------------------------------------------------

@router.post("/complaints/{complaint_id}/status")
async def update_complaint_status(
    complaint_id: str,
    payload: StatusActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "authority_officer", "department_officer"]))
):
    """
    Update administrative progress status with strict role boundaries:
    - Department Officers can mark 'Under Inspection', 'In Progress', 'Resolution Submitted' (cannot directly close/verify/reject).
    - Authority Officers can advance to 'Resolved', 'In Progress', 'Assigned', etc.
    - Admins can mark 'Ready for Authority Officer', 'Under Review'.
    """
    allowed_statuses = [
        "Received",
        "Pending Verification",
        "Ready for Authority Officer",
        "Verified",
        "Awaiting Department Assignment",
        "Assigned",
        "Pending Inspection",
        "Under Inspection",
        "In Progress",
        "Resolution Submitted",
        "Resolved",
        "Rejected",
        "Escalated"
    ]
    target_status = payload.status.strip()
    if target_status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{target_status}'. Must be one of: {', '.join(allowed_statuses)}"
        )

    c = db.query(Complaint).filter(Complaint.complaint_id == complaint_id.strip()).first()
    if not c:
        raise HTTPException(status_code=404, detail="Complaint not found.")

    if current_user.role == "department_officer":
        if c.assigned_department_id not in current_user.get_authorized_department_ids():
            raise HTTPException(
                status_code=403,
                detail="Access forbidden: Department officers can only update status for complaints assigned to their division."
            )
        # Department Officers cannot directly verify, reject, or close complaints
        if target_status in ("Resolved", "Verified", "Rejected", "Awaiting Department Assignment"):
            raise HTTPException(
                status_code=403,
                detail="Department officers cannot directly close, verify, or reject complaints. Please submit resolution evidence for Authority Officer review."
            )

    if current_user.role == "admin":
        if target_status in ("Resolved", "Verified", "Rejected"):
            raise HTTPException(
                status_code=403,
                detail="Civic verification decisions and closure are restricted to Authority Officers. Admin prepares complaints."
            )

    prev_status = c.admin_status or c.status
    c.admin_status = target_status
    c.status = target_status
    if payload.notes:
        c.status_notes = payload.notes.strip()

    note_text = f" Notes: {payload.notes}" if payload.notes else ""
    event = ComplaintEvent(
        complaint_id=c.complaint_id,
        event_type="status_changed",
        previous_value=prev_status,
        new_value=target_status,
        description=f"Status transitioned to '{target_status}' by {current_user.full_name} ({current_user.role}).{note_text}",
        source="authority"
    )
    db.add(event)
    db.commit()
    db.refresh(c)

    return {
        "status": "ok",
        "message": f"Status updated to '{target_status}'.",
        "complaint_id": c.complaint_id,
        "admin_status": c.admin_status,
        "status": c.status
    }

# -------------------------------------------------------------
# 7. Escalation Controls
# -------------------------------------------------------------

@router.post("/complaints/{complaint_id}/escalate")
async def escalate_complaint(
    complaint_id: str,
    payload: EscalationActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "authority_officer"]))
):
    """
    Escalate an urgent, unresolved, or high-risk complaint to higher administrative tier.
    """
    c = db.query(Complaint).filter(Complaint.complaint_id == complaint_id.strip()).first()
    if not c:
        raise HTTPException(status_code=404, detail="Complaint not found.")

    if current_user.role == "department_officer":
        if c.assigned_department_id not in current_user.get_authorized_department_ids():
            raise HTTPException(
                status_code=403,
                detail="Access forbidden: Department officers can only add notes to complaints assigned to their division."
            )

    c.escalation_level = payload.escalation_level
    c.escalation_reason = payload.reason.strip()
    c.escalated_to = payload.escalated_to.strip() if payload.escalated_to else "Municipal Commissioner"
    c.escalated_at = utc_now()
    c.admin_status = "Escalated"

    event = ComplaintEvent(
        complaint_id=c.complaint_id,
        event_type="complaint_escalated",
        new_value=f"Tier {payload.escalation_level}",
        description=f"Escalated to {c.escalated_to} (Tier {payload.escalation_level}) by {current_user.full_name}. Reason: {c.escalation_reason}",
        source="authority"
    )
    db.add(event)
    db.commit()
    db.refresh(c)

    return {
        "status": "ok",
        "message": f"Complaint {c.complaint_id} escalated to {c.escalated_to}.",
        "escalation_level": c.escalation_level,
        "escalated_to": c.escalated_to,
        "escalation_reason": c.escalation_reason,
        "admin_status": c.admin_status,
        "escalated_at": c.escalated_at.isoformat()
    }

# -------------------------------------------------------------
# 8. Internal Administrative Notes
# -------------------------------------------------------------

@router.post("/complaints/{complaint_id}/notes")
async def add_internal_note(
    complaint_id: str,
    payload: InternalNoteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add or append an internal administrative note (not visible to citizen)."""
    c = db.query(Complaint).filter(Complaint.complaint_id == complaint_id.strip()).first()
    if not c:
        raise HTTPException(status_code=404, detail="Complaint not found.")

    if current_user.role == "department_officer":
        if c.assigned_department_id not in current_user.get_authorized_department_ids():
            raise HTTPException(
                status_code=403,
                detail="Access forbidden: Department officers can only add notes to complaints assigned to their division."
            )

    timestamp_str = utc_now().strftime("%Y-%m-%d %H:%M UTC")
    new_entry = f"[{timestamp_str}] {current_user.full_name} ({current_user.role}): {payload.notes.strip()}"

    if c.internal_notes:
        c.internal_notes = f"{c.internal_notes}\n\n{new_entry}"
    else:
        c.internal_notes = new_entry

    event = ComplaintEvent(
        complaint_id=c.complaint_id,
        event_type="internal_note_added",
        description=f"Internal note added by {current_user.full_name}.",
        source="authority"
    )
    db.add(event)
    db.commit()

    return {
        "status": "ok",
        "message": "Internal note recorded.",
        "internal_notes": c.internal_notes
    }

# -------------------------------------------------------------
# 9. Departments & Officers Directory
# -------------------------------------------------------------

@router.get("/departments/selection")
async def get_departments_for_selection(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns all 6 municipal departments formatted for the post-login Department Selection screen.
    Includes live complaint counts and authorization status for the authenticated officer.
    """
    depts = db.query(Department).filter(Department.is_active == True).order_by(Department.id.asc()).all()
    authorized_ids = current_user.get_authorized_department_ids()

    results = []
    for d in depts:
        count = db.query(Complaint).filter(Complaint.assigned_department_id == d.id).count()
        results.append({
            "id": d.id,
            "name": d.name,
            "code": d.code,
            "description": d.description,
            "sla_days": d.sla_days,
            "complaint_count": count,
            "is_authorized": d.id in authorized_ids
        })

    return {
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "full_name": current_user.full_name,
            "role": current_user.role,
            "has_all_departments": len(authorized_ids) > 1,
            "authorized_departments": authorized_ids
        },
        "departments": results
    }

@router.get("/departments")
async def list_departments(
    department_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve municipal departments and their workload metrics.
    Strictly scoped to officer's division for department officers.
    """
    if current_user.role == "department_officer":
        authorized_ids = current_user.get_authorized_department_ids()
        if not authorized_ids:
            raise HTTPException(status_code=403, detail="Department officer not assigned to any municipal department.")

        if department_id is not None:
            if department_id not in authorized_ids:
                raise HTTPException(
                    status_code=403,
                    detail=f"Access forbidden: You do not have authorization for department {department_id}."
                )
            depts = db.query(Department).filter(Department.id == department_id, Department.is_active == True).all()
        else:
            if len(authorized_ids) == 1:
                depts = db.query(Department).filter(Department.id == authorized_ids[0], Department.is_active == True).all()
            else:
                depts = db.query(Department).filter(Department.id.in_(authorized_ids), Department.is_active == True).all()
    else:
        if department_id is not None:
            depts = db.query(Department).filter(Department.id == department_id, Department.is_active == True).all()
        else:
            depts = db.query(Department).filter(Department.is_active == True).all()

    now = utc_now()
    results = []
    for d in depts:
        users = [{"id": u.id, "full_name": u.full_name, "email": u.email, "role": u.role} for u in d.users if u.is_active]
        dept_complaints = d.complaints
        total_assigned = len(dept_complaints)
        pending_inspections = sum(1 for c in dept_complaints if c.admin_status in ("Assigned", "Pending Inspection") and c.verification_status == "verified")
        in_progress_repairs = sum(1 for c in dept_complaints if c.admin_status == "In Progress")
        resolved_complaints = sum(1 for c in dept_complaints if c.admin_status == "Resolved" or c.status == "Resolved")

        # Calculate overdue work orders (> sla_days)
        overdue_work_orders = 0
        sla_hours = d.sla_days * 24
        for c in dept_complaints:
            if c.admin_status not in ("Resolved", "Rejected"):
                c_time = c.assigned_at or c.created_at
                if c_time:
                    if c_time.tzinfo is None:
                        c_time = c_time.replace(tzinfo=datetime.timezone.utc)
                    if (now - c_time).total_seconds() / 3600.0 > sla_hours:
                        overdue_work_orders += 1

        active_count = sum(1 for c in dept_complaints if c.admin_status not in ("Resolved", "Rejected"))
        # SLA Compliance Rate: Complaints still within target deadline = ((total_assigned - overdue_work_orders) / total_assigned) * 100
        sla_compliance_rate = round(((total_assigned - overdue_work_orders) / total_assigned * 100), 1) if total_assigned > 0 else 100.0
        # Resolution Rate: Percentage of assigned complaints fully resolved = (resolved_complaints / total_assigned) * 100
        resolution_rate = round((resolved_complaints / total_assigned * 100), 1) if total_assigned > 0 else 0.0

        results.append({
            "id": d.id,
            "name": d.name,
            "code": d.code,
            "description": d.description,
            "head_name": d.head_name,
            "contact_email": d.contact_email,
            "sla_days": d.sla_days,
            "users": users,
            "active_complaint_count": active_count,
            "total_assigned": total_assigned,
            "pending_inspections": pending_inspections,
            "in_progress_repairs": in_progress_repairs,
            "resolved_complaints": resolved_complaints,
            "overdue_work_orders": overdue_work_orders,
            "sla_compliance_rate": sla_compliance_rate,
            "resolution_rate": resolution_rate,
            "performance_rate": sla_compliance_rate  # Kept for backward compatibility
        })
    return {"departments": results}

# -------------------------------------------------------------
# 10. System-Wide Chronological Audit History
# -------------------------------------------------------------

@router.get("/audit")
async def get_audit_trail(
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    event_type: Optional[str] = None,
    complaint_id: Optional[str] = None,
    department_id: Optional[int] = None,
    source: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve chronological audit history across authorized complaints.
    Enforces strict department scoping for department officers at the database query layer.
    """
    query = db.query(ComplaintEvent)

    # Department officer strict query-level scoping
    if current_user.role == "department_officer":
        authorized_ids = current_user.get_authorized_department_ids()
        if not authorized_ids:
            raise HTTPException(status_code=403, detail="Department officer not assigned to any department.")

        # If a specific complaint_id is requested, verify it belongs to this department
        if complaint_id:
            clean_cid = complaint_id.strip()
            target_c = db.query(Complaint).filter(Complaint.complaint_id == clean_cid).first()
            if not target_c or target_c.assigned_department_id not in authorized_ids:
                raise HTTPException(
                    status_code=403,
                    detail="Access forbidden: You cannot view audit records for complaints outside your department."
                )

        if department_id is not None:
            if department_id not in authorized_ids:
                raise HTTPException(
                    status_code=403,
                    detail=f"Access forbidden: You do not have authorization for department {department_id}."
                )
            target_dept_id = department_id
        else:
            target_dept_id = current_user.department_id or authorized_ids[0]

        # Scoped query joining Complaint at the SQL layer
        query = query.join(Complaint, ComplaintEvent.complaint_id == Complaint.complaint_id)
        query = query.filter(Complaint.assigned_department_id == target_dept_id)
    elif department_id is not None:
        query = query.join(Complaint, ComplaintEvent.complaint_id == Complaint.complaint_id)
        query = query.filter(Complaint.assigned_department_id == department_id)

    if complaint_id:
        query = query.filter(ComplaintEvent.complaint_id.ilike(f"%{complaint_id.strip()}%"))
    if event_type:
        query = query.filter(ComplaintEvent.event_type.ilike(f"%{event_type.strip()}%"))
    if source:
        query = query.filter(ComplaintEvent.source.ilike(f"%{source.strip()}%"))

    total = query.count()
    events = (
        query.order_by(ComplaintEvent.created_at.desc(), ComplaintEvent.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    items = [
        {
            "id": ev.id,
            "complaint_id": ev.complaint_id,
            "event_type": ev.event_type,
            "previous_value": ev.previous_value,
            "new_value": ev.new_value,
            "description": ev.description,
            "source": ev.source,
            "created_at": ev.created_at.isoformat() if ev.created_at else None
        }
        for ev in events
    ]

    return {
        "page": page,
        "limit": limit,
        "total": total,
        "items": items
    }

# -------------------------------------------------------------
# 11. Evidence File Streaming / Display
# -------------------------------------------------------------

@router.get("/evidence/{stored_filename}")
async def get_evidence_file(
    stored_filename: str,
    token: Optional[str] = Query(None, description="Authority JWT access token or Citizen tracking token"),
    tracking_token: Optional[str] = Query(None, description="Citizen tracking token"),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Stream evidence photo or video securely from local storage or private Vercel Blob.
    Enforces role-based authority access and citizen tracking access.
    Never exposes raw private Blob URLs or master credentials to unauthenticated users.
    """
    clean_name = os.path.basename(stored_filename.strip())
    ev = db.query(Evidence).filter(Evidence.stored_filename == clean_name).first()
    if not ev:
        raise HTTPException(status_code=404, detail="Evidence record not found.")

    # ---------------------------------------------------------
    # Authentication & Authorization Verification
    # ---------------------------------------------------------
    authorized = False
    auth_token = None

    if authorization and authorization.lower().startswith("bearer "):
        auth_token = authorization[7:].strip()
    elif token:
        auth_token = token.strip()

    # 1. Authority User Check (JWT Token)
    if auth_token:
        user = get_user_from_token_str(auth_token, db)
        if user:
            if user.role in ["admin", "authority_officer"]:
                authorized = True
            elif user.role == "department_officer":
                assigned_dept = ev.complaint.assigned_department_id if ev.complaint else None
                authorized_depts = user.get_authorized_department_ids()
                # Department officers can view evidence for their department or unassigned intake
                if assigned_dept is None or assigned_dept in authorized_depts:
                    authorized = True
                else:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access forbidden: You do not have permission to view evidence for this department's complaint."
                    )
            else:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    # 2. Citizen Tracking Token Check
    if not authorized:
        candidate_tracking = tracking_token or (token if not auth_token else None)
        if candidate_tracking and ev.complaint and ev.complaint.tracking_token:
            if candidate_tracking.strip() == ev.complaint.tracking_token.strip():
                authorized = True
            else:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: Invalid tracking token for this complaint evidence."
                )

    if not authorized:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: Provide valid authority credentials or citizen tracking token.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # ---------------------------------------------------------
    # Secure Content Streaming
    # ---------------------------------------------------------
    # If evidence is hosted in Vercel Blob (Private cloud storage), stream via server-side authenticated GET
    if ev.storage_path.startswith("http://") or ev.storage_path.startswith("https://"):
        headers = {}
        if BLOB_READ_WRITE_TOKEN and ("vercel-storage.com" in ev.storage_path or "blob.vercel" in ev.storage_path):
            headers["Authorization"] = f"Bearer {BLOB_READ_WRITE_TOKEN}"

        try:
            res = requests.get(ev.storage_path, headers=headers, stream=True, timeout=30)
            if res.status_code != 200:
                logger.error(f"Failed to fetch evidence from private blob: {ev.storage_path} (Status {res.status_code})")
                raise HTTPException(status_code=404, detail="Evidence file could not be retrieved from private cloud storage.")

            return StreamingResponse(
                res.iter_content(chunk_size=65536),
                media_type=ev.file_type or "image/jpeg",
                headers={
                    "Content-Disposition": f'inline; filename="{ev.original_filename}"',
                    "Cache-Control": "private, max-age=300"
                }
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error streaming evidence from private blob: {e}")
            raise HTTPException(status_code=502, detail="Error retrieving evidence from cloud storage.")

    # Local filesystem storage
    if not os.path.exists(ev.storage_path):
        raise HTTPException(status_code=404, detail="Evidence file not found on disk.")

    return FileResponse(
        path=ev.storage_path,
        media_type=ev.file_type or "image/jpeg",
        filename=ev.original_filename
    )

# -------------------------------------------------------------
# 12. Road Inspection Queue (Department Field Queue)
# -------------------------------------------------------------

@router.get("/inspection-queue")
async def get_road_inspection_queue(
    department_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve complaints awaiting physical field inspection and repair work.
    For department officers: strictly filtered to their assigned department.
    Complaints must have passed human verification.
    """
    query = db.query(Complaint).filter(Complaint.verification_status == "verified")

    if current_user.role == "department_officer":
        authorized_ids = current_user.get_authorized_department_ids()
        if not authorized_ids:
            raise HTTPException(status_code=403, detail="Department officer is not associated with any department.")

        if department_id is not None:
            if department_id not in authorized_ids:
                raise HTTPException(
                    status_code=403,
                    detail=f"Access forbidden: You do not have authorization for department {department_id}."
                )
            target_dept_id = department_id
        else:
            target_dept_id = current_user.department_id or authorized_ids[0]

        query = query.filter(Complaint.assigned_department_id == target_dept_id)
    elif department_id is not None:
        query = query.filter(Complaint.assigned_department_id == department_id)

    # Needs field inspection / repair (not resolved or rejected)
    query = query.filter(Complaint.admin_status.in_(["Assigned", "In Progress", "Pending Inspection"]))

    complaints = query.order_by(Complaint.created_at.desc()).all()

    items = []
    for c in complaints:
        latest_ai = c.ai_analyses[0] if c.ai_analyses else None
        items.append({
            "id": c.id,
            "complaint_id": c.complaint_id,
            "tracking_token": c.tracking_token,
            "category": c.category,
            "description": c.description,
            "latitude": c.latitude,
            "longitude": c.longitude,
            "location_source": c.location_source,
            "google_maps_url": c.google_maps_url,
            "citizen_name": c.citizen_name,
            "admin_status": c.admin_status or c.status,
            "verification_status": c.verification_status,
            "department_code": c.department.code if c.department else None,
            "department_name": c.department.name if c.department else None,
            "assigned_at": c.assigned_at.isoformat() if c.assigned_at else None,
            "assignment_notes": c.assignment_notes,
            "evidence_count": len(c.evidence_files),
            "evidence": [
                {
                    "id": ev.id,
                    "original_filename": ev.original_filename,
                    "stored_filename": ev.stored_filename,
                    "view_url": f"/api/authority/evidence/{ev.stored_filename}"
                }
                for ev in c.evidence_files
            ],
            "ai_severity": latest_ai.recommended_severity if latest_ai else "Medium",
            "ai_problem": latest_ai.visible_problem if latest_ai else None,
            "internal_notes": c.internal_notes,
            "created_at": c.created_at.isoformat() if c.created_at else None
        })

    return {
        "total": len(items),
        "items": items
    }

# -------------------------------------------------------------
# 13. Upload Field Inspection Evidence
# -------------------------------------------------------------

@router.post("/complaints/{complaint_id}/evidence")
async def upload_inspection_evidence(
    complaint_id: str,
    file: UploadFile = File(...),
    caption: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "authority_officer", "department_officer"]))
):
    """
    Upload physical field inspection evidence or repair completion photos.
    Secured: department officers can only upload evidence to complaints in their division.
    """
    clean_id = complaint_id.strip()
    c = db.query(Complaint).filter(Complaint.complaint_id == clean_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Complaint not found.")

    if current_user.role == "department_officer":
        if c.assigned_department_id not in current_user.get_authorized_department_ids():
            raise HTTPException(
                status_code=403,
                detail="Access forbidden: You cannot upload evidence for a complaint outside your department."
            )

    from app.services.storage_service import save_evidence_file
    meta = await save_evidence_file(file)

    evidence_record = Evidence(
        complaint_id=c.complaint_id,
        original_filename=meta["original_filename"],
        stored_filename=meta["stored_filename"],
        file_type=meta["file_type"],
        file_size=meta["file_size"],
        storage_path=meta["storage_path"]
    )
    db.add(evidence_record)

    caption_text = f" Caption: {caption.strip()}" if caption and caption.strip() else ""
    event = ComplaintEvent(
        complaint_id=c.complaint_id,
        event_type="inspection_evidence_uploaded",
        description=f"Field inspection evidence '{meta['original_filename']}' uploaded by {current_user.full_name} ({current_user.role}).{caption_text}",
        source="authority"
    )
    db.add(event)
    db.commit()
    db.refresh(evidence_record)

    return {
        "status": "ok",
        "message": "Inspection evidence uploaded successfully.",
        "evidence_id": evidence_record.id,
        "original_filename": evidence_record.original_filename,
        "stored_filename": evidence_record.stored_filename,
        "view_url": f"/api/authority/evidence/{evidence_record.stored_filename}"
    }

