import json
from typing import Optional, Dict, Any, List, Tuple

BASE_WEIGHTS = {
    "gps": 0.35,
    "text": 0.30,
    "image": 0.25,
    "category": 0.10,
}

THRESHOLD_HIGH = 0.85
THRESHOLD_MEDIUM = 0.65
MIN_REQUIRED_WEIGHT = 0.35

def compute_composite_score(
    gps_score: Optional[float],
    distance_meters: Optional[float],
    text_score: Optional[float],
    image_score: Optional[float],
    category_score: Optional[float]
) -> Dict[str, Any]:
    """
    Computes a dynamically normalized duplicate similarity score across available signals.
    Never penalizes missing signals with zero.
    Produces confidence level, recommendation, human-readable explanation, and discrepancy warnings.
    """
    signals = {
        "gps": gps_score,
        "text": text_score,
        "image": image_score,
        "category": category_score,
    }

    available_signals = {k: v for k, v in signals.items() if v is not None}
    total_available_weight = sum(BASE_WEIGHTS[k] for k in available_signals.keys())

    warnings: List[str] = []

    # Check minimum signal presence
    if total_available_weight < MIN_REQUIRED_WEIGHT:
        return {
            "similarity_score": 0.0,
            "confidence_level": "insufficient_evidence",
            "recommendation": "Insufficient Evidence - Independent Verification Required",
            "matching_explanation": "Insufficient multi-signal data available to evaluate duplicate relationship.",
            "warning_signals": json.dumps(["Available signals below minimum threshold for confidence scoring."]),
            "effective_weights": {},
        }

    # Dynamic renormalization
    weighted_sum = sum(BASE_WEIGHTS[k] * available_signals[k] for k in available_signals.keys())
    composite_score = round(weighted_sum / total_available_weight, 4)

    # Discrepancy checks & warning signals
    if distance_meters is not None:
        if distance_meters <= 25.0 and (category_score is not None and category_score == 0.0):
            warnings.append("Geographically close (<25m) but reported under distinct, conflicting categories.")
        if distance_meters <= 15.0 and (text_score is not None and text_score < 0.20):
            warnings.append("Coordinates overlap (<15m) but descriptions depict different civic problems.")
        if distance_meters > 100.0 and (text_score is not None and text_score >= 0.80):
            warnings.append("Descriptions share similar language but physical locations are over 100m apart.")

    if image_score is None:
        warnings.append("Visual comparison skipped: photographic evidence missing from one or both records.")

    # Threshold classification
    if composite_score >= THRESHOLD_HIGH:
        confidence = "high"
        recommendation = "Candidate Duplicate - High Confidence"
    elif composite_score >= THRESHOLD_MEDIUM:
        confidence = "medium"
        recommendation = "Potential Match - Manual Review Recommended"
    else:
        confidence = "low"
        recommendation = "Unlikely Duplicate - Distinct Physical Issue"

    # Human-readable breakdown explanation
    parts = []
    if distance_meters is not None and gps_score is not None:
        parts.append(f"GPS Distance: {distance_meters:.1f}m (score: {gps_score:.2f})")
    elif gps_score is not None:
        parts.append(f"GPS Score: {gps_score:.2f}")

    if text_score is not None:
        parts.append(f"Text Similarity: {text_score:.2f}")

    if category_score is not None:
        parts.append(f"Category Match: {category_score:.2f}")

    if image_score is not None:
        parts.append(f"Visual Similarity: {image_score:.2f}")
    else:
        parts.append("Visual: N/A")

    explanation = " | ".join(parts)

    effective_weights = {
        k: round(BASE_WEIGHTS[k] / total_available_weight, 3)
        for k in available_signals.keys()
    }

    return {
        "similarity_score": composite_score,
        "confidence_level": confidence,
        "recommendation": recommendation,
        "matching_explanation": explanation,
        "warning_signals": json.dumps(warnings) if warnings else None,
        "effective_weights": effective_weights,
    }

