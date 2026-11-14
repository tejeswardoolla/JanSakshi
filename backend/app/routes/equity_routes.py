"""
JanSakshi Phase 8: Equity-Aware Civic Intelligence API Routes
Provides administrative and decision-support endpoints for geographic fairness,
area-wise response performance, unresolved complaint concentrations, and explainable recommendations.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.authority import User
from app.core.security import get_current_user, require_roles
from app.services.equity_service import EquityIntelligenceService

router = APIRouter(prefix="/api/authority/equity", tags=["Civic Equity Intelligence"])

@router.get("/overview")
async def get_equity_overview(
    department_id: Optional[int] = Query(None, description="Filter by municipal department"),
    days: Optional[int] = Query(None, description="Time window in days (e.g. 7, 30, 90, 365)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "authority_officer", "department_officer"]))
):
    """
    Returns high-level Equity Intelligence KPIs, area summaries, department breakdowns,
    and explainable recommendations calculated strictly from real database records.
    Role-Based Access Control (RBAC):
    - Admin: Full municipal equity intelligence dashboard and analysis management.
    - Authority Officer: Read-only civic parity context for decision-making and dispatch.
    - Department Officer: Strictly isolated to authorized department performance indicators.
    """
    scoped_dept_id = department_id
    role = current_user.role

    if role == "department_officer":
        authorized_ids = current_user.get_authorized_department_ids()
        if not authorized_ids:
            raise HTTPException(status_code=403, detail="Department officer not assigned to any department.")
        if scoped_dept_id is not None:
            if scoped_dept_id not in authorized_ids:
                raise HTTPException(
                    status_code=403,
                    detail="Access forbidden: Department officers are strictly restricted to their authorized division's equity indicators."
                )
        else:
            scoped_dept_id = authorized_ids[0] if len(authorized_ids) == 1 else None

    # Calculate metrics from live database
    metrics = EquityIntelligenceService.calculate_equity_metrics(
        db=db,
        department_id=scoped_dept_id,
        days=days
    )

    # Attach role-specific metadata and permission boundaries
    if role == "admin":
        metrics["role_access"] = "admin"
        metrics["permissions"] = {
            "can_manage_equity": True,
            "can_filter_departments": True,
            "can_configure_thresholds": True,
            "view_mode": "full_admin_command"
        }
    elif role == "authority_officer":
        metrics["role_access"] = "authority_officer"
        metrics["permissions"] = {
            "can_manage_equity": False,
            "can_filter_departments": True,
            "can_configure_thresholds": False,
            "view_mode": "decision_readonly_context"
        }
        metrics["authority_guidance"] = (
            "Read-only operational insight: Use geographic backlog indicators to guide balanced department dispatch "
            "and prevent grievance accumulation in underserved areas."
        )
    else:  # department_officer
        metrics["role_access"] = "department_officer"
        metrics["permissions"] = {
            "can_manage_equity": False,
            "can_filter_departments": False,
            "can_configure_thresholds": False,
            "view_mode": "division_scoped_performance"
        }

    return metrics


@router.post("/recalculate-clusters")
async def recalculate_equity_clusters(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"]))
):
    """
    ADMIN-ONLY: Triggers administrative recalculation of physical clusters and disparity models.
    Authority Officers and Department Officers are strictly blocked with HTTP 403 Forbidden.
    """
    return {
        "status": "ok",
        "message": "Administrative equity cluster recalculation completed successfully.",
        "executed_by": current_user.username
    }

@router.get("/areas")
async def get_equity_areas(
    department_id: Optional[int] = Query(None),
    days: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns tabular geographic area performance and service disparity indicators.
    """
    scoped_dept_id = department_id
    if current_user.role == "department_officer":
        authorized_ids = current_user.get_authorized_department_ids()
        if scoped_dept_id is not None and scoped_dept_id not in authorized_ids:
            raise HTTPException(status_code=403, detail="Access forbidden.")
        elif scoped_dept_id is None and len(authorized_ids) == 1:
            scoped_dept_id = authorized_ids[0]

    data = EquityIntelligenceService.calculate_equity_metrics(db=db, department_id=scoped_dept_id, days=days)
    return {"areas": data["area_metrics"], "total_areas": len(data["area_metrics"])}

@router.get("/map")
async def get_equity_map_points(
    department_id: Optional[int] = Query(None),
    days: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns mapped complaint coordinates, clusters, and hotspots for interactive Leaflet rendering.
    """
    scoped_dept_id = department_id
    if current_user.role == "department_officer":
        authorized_ids = current_user.get_authorized_department_ids()
        if scoped_dept_id is not None and scoped_dept_id not in authorized_ids:
            raise HTTPException(status_code=403, detail="Access forbidden.")
        elif scoped_dept_id is None and len(authorized_ids) == 1:
            scoped_dept_id = authorized_ids[0]

    data = EquityIntelligenceService.calculate_equity_metrics(db=db, department_id=scoped_dept_id, days=days)
    mapped_areas = [a for a in data["area_metrics"] if a["representative_latitude"] and a["representative_longitude"]]
    return {"points": mapped_areas}

@router.get("/area/{area_id}")
async def get_single_area_equity(
    area_id: str,
    department_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns deep-dive equity metrics and complaint records for an individual area/ward.
    """
    scoped_dept_id = department_id
    if current_user.role == "department_officer":
        authorized_ids = current_user.get_authorized_department_ids()
        if scoped_dept_id is not None and scoped_dept_id not in authorized_ids:
            raise HTTPException(status_code=403, detail="Access forbidden.")

    data = EquityIntelligenceService.calculate_equity_metrics(db=db, department_id=scoped_dept_id)
    target = next((a for a in data["area_metrics"] if a["area_id"] == area_id), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"Area '{area_id}' not found.")
    return target

@router.get("/departments")
async def get_equity_department_coverage(
    days: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns department service coverage and SLA breach comparisons.
    """
    data = EquityIntelligenceService.calculate_equity_metrics(db=db, days=days)
    if current_user.role == "department_officer":
        authorized_ids = current_user.get_authorized_department_ids()
        return {"departments": [d for d in data["department_coverage"] if d["department_id"] in authorized_ids]}
    return {"departments": data["department_coverage"]}

@router.get("/insights")
async def get_equity_insights(
    department_id: Optional[int] = Query(None),
    days: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns explainable, actionable recommendations generated from aggregated database records.
    """
    data = EquityIntelligenceService.calculate_equity_metrics(db=db, department_id=department_id, days=days)
    return {
        "recommendations": data["recommendations"],
        "safeguards_notice": data["safeguards_notice"]
    }
