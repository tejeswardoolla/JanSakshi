from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.config import (
    is_gemini_configured,
    AI_ANALYSIS_ENABLED,
    GEMINI_MODEL,
    AI_CONFIDENCE_THRESHOLD,
    GEMINI_API_KEY
)
from app.repositories import ComplaintRepository
from app.models.complaint import AIAnalysis
from app.schemas import AIStatusResponse, AIAnalysisResponse
from app.services.ai.complaint_analyzer import ComplaintAnalyzer

router = APIRouter(prefix="/api/ai", tags=["AI Processing Agent"])

@router.get("/status", response_model=AIStatusResponse)
async def get_ai_status():
    """
    Returns the current operational status of the Gemini AI integration.
    Never exposes API keys or sensitive credentials.
    """
    configured = is_gemini_configured()
    
    if not AI_ANALYSIS_ENABLED:
        stat = "disabled"
        msg = "AI analysis is currently disabled in backend configuration."
    elif not configured:
        stat = "unconfigured"
        msg = "Gemini API key is not configured. Add GEMINI_API_KEY to backend/.env to activate live multimodal AI."
    else:
        stat = "operational"
        msg = f"Gemini Multimodal AI is operational using model '{GEMINI_MODEL}'."

    return AIStatusResponse(
        configured=configured,
        enabled=AI_ANALYSIS_ENABLED,
        model=GEMINI_MODEL,
        confidence_threshold=AI_CONFIDENCE_THRESHOLD,
        status=stat,
        message=msg
    )

@router.get("/complaints/{complaint_id}/analysis", response_model=AIAnalysisResponse)
async def get_complaint_ai_analysis(complaint_id: str, db: Session = Depends(get_db)):
    """
    Retrieve the latest AI analysis for a specific complaint.
    """
    repo = ComplaintRepository(db)
    complaint = repo.get_by_complaint_id(complaint_id)
    if not complaint:
        raise HTTPException(status_code=404, detail=f"Complaint '{complaint_id}' not found.")

    latest_analysis = (
        db.query(AIAnalysis)
        .filter(AIAnalysis.complaint_id == complaint_id.strip())
        .order_by(AIAnalysis.id.desc())
        .first()
    )

    if not latest_analysis:
        raise HTTPException(
            status_code=404,
            detail=f"No AI analysis found for complaint '{complaint_id}'. Analysis may be pending or AI is unconfigured."
        )

    return latest_analysis

@router.get("/complaints/{complaint_id}/analysis/history", response_model=List[AIAnalysisResponse])
async def get_complaint_ai_history(complaint_id: str, db: Session = Depends(get_db)):
    """
    Retrieve all historical AI analyses for a complaint across retries.
    """
    repo = ComplaintRepository(db)
    complaint = repo.get_by_complaint_id(complaint_id)
    if not complaint:
        raise HTTPException(status_code=404, detail=f"Complaint '{complaint_id}' not found.")

    history = (
        db.query(AIAnalysis)
        .filter(AIAnalysis.complaint_id == complaint_id.strip())
        .order_by(AIAnalysis.created_at.asc())
        .all()
    )
    return history

@router.post("/complaints/{complaint_id}/analysis/retry", response_model=AIAnalysisResponse)
async def retry_ai_analysis(
    complaint_id: str,
    evidence_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Force a re-run of AI analysis on an existing complaint.
    Controlled, idempotent, and non-destructive.
    """
    analyzer = ComplaintAnalyzer(db)
    try:
        analysis = await analyzer.run_analysis(complaint_id, evidence_id=evidence_id, force_retry=True)
        return analysis
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed re-running AI analysis: {str(e)}")
