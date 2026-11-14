import json
import re
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator

from app.services.ai.prompt_templates import VALID_CATEGORIES

class StructuredAnalysisResult(BaseModel):
    predicted_category: str
    category_confidence: float = Field(..., ge=0.0, le=1.0)
    complaint_summary: str
    visible_problem: str
    evidence_relevance: str = "unclear" # relevant, insufficient, unclear, unrelated, not_applicable
    relevance_score: int = Field(50, ge=0, le=100)
    image_quality: str = "inconclusive" # good, acceptable, blurred, dark, obstructed, inconclusive
    clarity_score: int = Field(50, ge=0, le=100)
    visibility_score: int = Field(50, ge=0, le=100)
    additional_evidence_required: bool = False
    recommended_severity: str = "medium" # low, medium, high, critical
    severity_confidence: float = Field(0.5, ge=0.0, le=1.0)
    reasoning: str
    human_review_required: bool = True
    review_reasons: List[str] = Field(default_factory=list)

    @field_validator("predicted_category")
    def validate_category(cls, v):
        clean = v.strip()
        for cat in VALID_CATEGORIES:
            if cat.lower() == clean.lower():
                return cat
        return "Other"

    @field_validator("evidence_relevance")
    def validate_relevance(cls, v):
        allowed = {"relevant", "insufficient", "unclear", "unrelated", "not_applicable"}
        return v.lower() if v.lower() in allowed else "unclear"

    @field_validator("image_quality")
    def validate_quality(cls, v):
        allowed = {"good", "acceptable", "blurred", "dark", "obstructed", "inconclusive"}
        return v.lower() if v.lower() in allowed else "inconclusive"

    @field_validator("recommended_severity")
    def validate_severity(cls, v):
        allowed = {"low", "medium", "high", "critical"}
        return v.lower() if v.lower() in allowed else "medium"

def clean_json_text(text: str) -> str:
    """Strip markdown code blocks or wrapping quotes if model wraps in ```json ... ```"""
    stripped = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", stripped)
    if match:
        return match.group(1).strip()
    return stripped

def parse_and_validate_ai_response(raw_text: str) -> StructuredAnalysisResult:
    """
    Safely parse raw response text into a validated StructuredAnalysisResult object.
    Raises ValueError with descriptive context if malformed.
    """
    cleaned = clean_json_text(raw_text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as err:
        raise ValueError(f"Failed decoding JSON from Gemini output: {str(err)}. Content: {cleaned[:120]}")

    return StructuredAnalysisResult(**data)

