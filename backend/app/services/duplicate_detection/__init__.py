from app.services.duplicate_detection.location_similarity import (
    calculate_haversine_distance,
    calculate_location_similarity,
    get_bounding_box,
)
from app.services.duplicate_detection.category_similarity import calculate_category_similarity
from app.services.duplicate_detection.text_similarity import calculate_text_similarity
from app.services.duplicate_detection.image_similarity import (
    calculate_single_image_similarity,
    compare_evidence_lists,
)
from app.services.duplicate_detection.scoring import compute_composite_score
from app.services.duplicate_detection.candidate_retrieval import retrieve_candidate_issues
from app.services.duplicate_detection.duplicate_detector import DuplicateDetector

__all__ = [
    "calculate_haversine_distance",
    "calculate_location_similarity",
    "get_bounding_box",
    "calculate_category_similarity",
    "calculate_text_similarity",
    "calculate_single_image_similarity",
    "compare_evidence_lists",
    "compute_composite_score",
    "retrieve_candidate_issues",
    "DuplicateDetector",
]

