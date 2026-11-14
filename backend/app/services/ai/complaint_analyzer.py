import json
import logging
from typing import Optional, List
from sqlalchemy.orm import Session

from app.core.config import is_gemini_configured, GEMINI_MODEL, utc_now
from app.models.complaint import Complaint, Evidence, AIAnalysis
from app.repositories import ComplaintRepository
from app.services.ai.gemini_client import GeminiClient
from app.services.ai.response_parser import StructuredAnalysisResult

logger = logging.getLogger(__name__)

class ComplaintAnalyzer:
    """
    Orchestrates the AI complaint analysis process:
    - Verifies configuration status
    - Prepares multimodal evidence files
    - Invokes GeminiClient
    - Creates and persists AIAnalysis database records
    - Emits structured ComplaintEvents to the audit log
    - Handles failures gracefully without breaking complaint records
    """

    def __init__(self, db: Session, client: Optional[GeminiClient] = None):
        self.db = db
        self.repo = ComplaintRepository(db)
        self.client = client or GeminiClient()

    async def run_analysis(
        self,
        complaint_id: str,
        evidence_id: Optional[int] = None,
        force_retry: bool = False
    ) -> AIAnalysis:
        complaint = self.repo.get_by_complaint_id(complaint_id)
        if not complaint:
            raise ValueError(f"Complaint '{complaint_id}' not found.")

        # Check if already completed and not force_retry
        if not force_retry:
            existing = (
                self.db.query(AIAnalysis)
                .filter(AIAnalysis.complaint_id == complaint_id)
                .order_by(AIAnalysis.id.desc())
                .first()
            )
            if existing and existing.analysis_status == "completed":
                return existing

        # Locate image evidence if available
        target_evidence = None
        image_path = None
        if evidence_id:
            target_evidence = self.db.query(Evidence).filter(Evidence.id == evidence_id).first()
        elif complaint.evidence_files:
            # Pick first image evidence
            for ev in complaint.evidence_files:
                if "image" in ev.file_type or ev.original_filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                    target_evidence = ev
                    break

        if target_evidence:
            image_path = target_evidence.storage_path

        # Case 1: Gemini API key is not configured
        if not self.client.is_configured:
            analysis = AIAnalysis(
                complaint_id=complaint_id,
                evidence_id=target_evidence.id if target_evidence else None,
                analysis_status="not_configured",
                predicted_category=None,
                complaint_summary=None,
                visible_problem="AI analysis is currently unconfigured. Awaiting Gemini API key.",
                evidence_relevance="unclear",
                image_quality="inconclusive",
                recommended_severity="medium",
                human_review_required=True,
                review_reasons=json.dumps(["Gemini API key is not yet configured on server."]),
                model_name=GEMINI_MODEL,
                error_message="GEMINI_API_KEY is not set or AI is disabled in environment.",
                created_at=utc_now(),
                updated_at=utc_now()
            )
            self.db.add(analysis)
            self.repo.add_event(
                complaint_id=complaint_id,
                event_type="ai_analysis_unconfigured",
                description="AI analysis skipped: Gemini API key not yet configured on server.",
                source="ai_agent"
            )
            self.db.commit()
            self.db.refresh(analysis)
            return analysis

        # Case 2: Configured -> Call Gemini
        try:
            result: StructuredAnalysisResult = await self.client.analyze_complaint(
                category=complaint.category,
                description=complaint.description,
                image_path=image_path
            )

            # Check if category differs from citizen choice
            category_disagreement = result.predicted_category.lower() != complaint.category.lower()
            review_reasons = list(result.review_reasons)
            if category_disagreement:
                review_reasons.append(
                    f"AI predicted category '{result.predicted_category}' differs from citizen-selected '{complaint.category}'."
                )

            analysis = AIAnalysis(
                complaint_id=complaint_id,
                evidence_id=target_evidence.id if target_evidence else None,
                analysis_status="completed",
                predicted_category=result.predicted_category,
                category_confidence=result.category_confidence,
                complaint_summary=result.complaint_summary,
                visible_problem=result.visible_problem,
                evidence_relevance=result.evidence_relevance,
                relevance_score=result.relevance_score,
                image_quality=result.image_quality,
                clarity_score=result.clarity_score,
                visibility_score=result.visibility_score,
                additional_evidence_required=result.additional_evidence_required,
                recommended_severity=result.recommended_severity,
                severity_confidence=result.severity_confidence,
                reasoning=result.reasoning,
                human_review_required=result.human_review_required or category_disagreement,
                review_reasons=json.dumps(review_reasons),
                model_name=self.client.model,
                error_message=None,
                raw_response=result.model_dump_json(),
                created_at=utc_now(),
                updated_at=utc_now()
            )
            self.db.add(analysis)

            # Audit event
            self.repo.add_event(
                complaint_id=complaint_id,
                event_type="ai_analysis_completed",
                new_value=result.predicted_category,
                description=f"AI analysis completed. Recommended severity: {result.recommended_severity.upper()} (relevance: {result.evidence_relevance}).",
                source="ai_agent"
            )
            self.db.commit()
            self.db.refresh(analysis)
            return analysis

        except Exception as e:
            logger.error(f"AI analysis failed for complaint '{complaint_id}': {str(e)}")
            self.db.rollback()

            error_analysis = AIAnalysis(
                complaint_id=complaint_id,
                evidence_id=target_evidence.id if target_evidence else None,
                analysis_status="failed",
                human_review_required=True,
                review_reasons=json.dumps(["AI analysis failed; manual human review mandatory."]),
                model_name=self.client.model,
                error_message=str(e)[:500],
                created_at=utc_now(),
                updated_at=utc_now()
            )
            self.db.add(error_analysis)
            self.repo.add_event(
                complaint_id=complaint_id,
                event_type="ai_analysis_failed",
                description=f"AI analysis failed: {str(e)[:150]}",
                source="ai_agent"
            )
            self.db.commit()
            self.db.refresh(error_analysis)
            return error_analysis

