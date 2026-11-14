import unittest
import json
from unittest.mock import MagicMock, patch, AsyncMock
from app.services.ai.response_parser import parse_and_validate_ai_response, StructuredAnalysisResult
from app.services.ai.prompt_templates import build_complaint_analysis_prompt
from app.services.ai.gemini_client import GeminiClient
from app.services.ai.complaint_analyzer import ComplaintAnalyzer
from app.database import SessionLocal
from app.models.complaint import Complaint, AIAnalysis

class TestPhase4AIAgent(unittest.TestCase):

    def test_prompt_template_generation(self):
        prompt = build_complaint_analysis_prompt(
            category="Road Damage / Potholes",
            description="Deep pothole causing vehicle damage near market square.",
            has_image=True
        )
        self.assertIn("Road Damage / Potholes", prompt)
        self.assertIn("Evidence Image Provided: Yes", prompt)
        self.assertIn("predicted_category", prompt)

    def test_structured_json_parsing_clean(self):
        sample_json = json.dumps({
            "predicted_category": "Road Damage / Potholes",
            "category_confidence": 0.94,
            "complaint_summary": "Pothole on roadway near market.",
            "visible_problem": "Deep depression in asphalt tarmac.",
            "evidence_relevance": "relevant",
            "relevance_score": 92,
            "image_quality": "good",
            "clarity_score": 85,
            "visibility_score": 90,
            "additional_evidence_required": False,
            "recommended_severity": "high",
            "severity_confidence": 0.88,
            "reasoning": "Substantial hazard to two-wheelers.",
            "human_review_required": True,
            "review_reasons": ["High traffic corridor requires verification."]
        })
        result = parse_and_validate_ai_response(sample_json)
        self.assertIsInstance(result, StructuredAnalysisResult)
        self.assertEqual(result.predicted_category, "Road Damage / Potholes")
        self.assertEqual(result.evidence_relevance, "relevant")
        self.assertEqual(result.recommended_severity, "high")
        self.assertTrue(result.human_review_required)

    def test_structured_json_with_markdown_fence(self):
        sample_raw = """
        ```json
        {
          "predicted_category": "Broken Streetlights",
          "category_confidence": 0.82,
          "complaint_summary": "Streetlight unlit for days.",
          "visible_problem": "Broken lamp cover and exposed wiring.",
          "evidence_relevance": "relevant",
          "relevance_score": 85,
          "image_quality": "acceptable",
          "clarity_score": 75,
          "visibility_score": 70,
          "additional_evidence_required": false,
          "recommended_severity": "medium",
          "severity_confidence": 0.80,
          "reasoning": "Pedestrian safety concern at night.",
          "human_review_required": true,
          "review_reasons": ["Dark area verification."]
        }
        ```
        """
        result = parse_and_validate_ai_response(sample_raw)
        self.assertEqual(result.predicted_category, "Broken Streetlights")
        self.assertEqual(result.clarity_score, 75)

    def test_malformed_json_rejection(self):
        invalid_raw = "This is not valid json content from model"
        with self.assertRaises(ValueError):
            parse_and_validate_ai_response(invalid_raw)

    def test_missing_api_key_unconfigured_behavior(self):
        # Client initialized with empty key must report unconfigured
        client = GeminiClient(api_key="")
        self.assertFalse(client.is_configured)

    def test_complaint_analyzer_unconfigured_mode(self):
        db = SessionLocal()
        try:
            # Query an existing complaint
            complaint = db.query(Complaint).first()
            self.assertIsNotNone(complaint)

            # Analyze with unconfigured client
            unconfigured_client = GeminiClient(api_key="")
            analyzer = ComplaintAnalyzer(db=db, client=unconfigured_client)
            
            import asyncio
            analysis = asyncio.run(analyzer.run_analysis(complaint.complaint_id, force_retry=True))
            
            self.assertEqual(analysis.analysis_status, "not_configured")
            self.assertTrue(analysis.human_review_required)
            self.assertIn("not yet configured", analysis.review_reasons)
        finally:
            db.close()

    def test_mocked_gemini_multimodal_analysis_persistence(self):
        db = SessionLocal()
        try:
            complaint = db.query(Complaint).first()
            self.assertIsNotNone(complaint)

            mock_client = MagicMock()
            mock_client.is_configured = True
            mock_client.model = "gemini-2.5-flash-mock"

            mock_result = StructuredAnalysisResult(
                predicted_category="Water Leakage",
                category_confidence=0.96,
                complaint_summary="Pipeline bursting in roadway.",
                visible_problem="High pressure water jet from broken pipeline.",
                evidence_relevance="relevant",
                relevance_score=95,
                image_quality="good",
                clarity_score=90,
                visibility_score=92,
                additional_evidence_required=False,
                recommended_severity="critical",
                severity_confidence=0.91,
                reasoning="Active water loss and structural road wash risk.",
                human_review_required=True,
                review_reasons=["Immediate municipal pipeline shutdown needed."]
            )
            mock_client.analyze_complaint = AsyncMock(return_value=mock_result)

            analyzer = ComplaintAnalyzer(db=db, client=mock_client)
            
            import asyncio
            analysis = asyncio.run(analyzer.run_analysis(complaint.complaint_id, force_retry=True))

            self.assertEqual(analysis.analysis_status, "completed")
            self.assertEqual(analysis.predicted_category, "Water Leakage")
            self.assertEqual(analysis.recommended_severity, "critical")
            self.assertEqual(analysis.relevance_score, 95)
            self.assertEqual(analysis.model_name, "gemini-2.5-flash-mock")

            # Check audit event logged
            from app.models.complaint import ComplaintEvent
            ev = db.query(ComplaintEvent).filter(
                ComplaintEvent.complaint_id == complaint.complaint_id,
                ComplaintEvent.event_type == "ai_analysis_completed"
            ).first()
            self.assertIsNotNone(ev)
        finally:
            db.close()

if __name__ == "__main__":
    unittest.main()

