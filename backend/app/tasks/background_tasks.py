import logging
import asyncio
from app.database import SessionLocal
from app.repositories import ComplaintRepository
from app.services.ai.complaint_analyzer import ComplaintAnalyzer
from app.services.duplicate_detection import DuplicateDetector

logger = logging.getLogger(__name__)

def post_complaint_submission_task(complaint_id: str):
    """
    Background Task: Executes post-submission actions asynchronously without blocking the user.
    Flow:
    1. Log initial background event.
    2. Invoke ComplaintAnalyzer to run multimodal Gemini analysis in background.
    3. Invoke DuplicateDetector to evaluate physical issue candidates and link recommendations.
    4. Handles failure gracefully; persistence is already confirmed.
    """
    db = SessionLocal()
    try:
        repo = ComplaintRepository(db)
        repo.add_event(
            complaint_id=complaint_id,
            event_type="background_processing_queued",
            description="Complaint queued for asynchronous background pipeline checks.",
            source="background_task"
        )
        db.commit()

        # Step 1: Trigger AI analysis asynchronously
        try:
            analyzer = ComplaintAnalyzer(db)
            asyncio.run(analyzer.run_analysis(complaint_id))
        except Exception as ai_err:
            logger.error(f"AI analysis failed in background for complaint {complaint_id}: {str(ai_err)}")

        # Step 2: Phase 5 Smart Physical Issue Duplicate Detection
        try:
            DuplicateDetector.evaluate_complaint(complaint_id, db)
        except Exception as dup_err:
            logger.error(f"Duplicate detection failed for complaint {complaint_id}: {str(dup_err)}")
            repo.add_event(
                complaint_id=complaint_id,
                event_type="duplicate_detection_failed",
                description=f"Duplicate detection encountered an error: {str(dup_err)}",
                source="ai_duplicate_detector"
            )
            db.commit()

    except Exception as e:
        logger.error(f"Background task failed for complaint {complaint_id}: {str(e)}")
        db.rollback()
    finally:
        db.close()
