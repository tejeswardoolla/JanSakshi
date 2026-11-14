from typing import List, Tuple
from sqlalchemy.orm import Session
from app.models.complaint import PhysicalIssue, Complaint, Evidence
from app.services.duplicate_detection.location_similarity import get_bounding_box, calculate_haversine_distance

DEFAULT_CANDIDATE_RADIUS_METERS = 150.0

def retrieve_candidate_issues(
    db: Session,
    complaint: Complaint,
    search_radius_meters: float = DEFAULT_CANDIDATE_RADIUS_METERS
) -> List[Tuple[PhysicalIssue, float]]:
    """
    Retrieves candidate PhysicalIssue records within the search radius of the complaint.
    Returns a list of tuples: (PhysicalIssue, distance_in_meters), sorted by distance ascending.
    """
    if complaint.latitude is None or complaint.longitude is None:
        return []

    min_lat, max_lat, min_lon, max_lon = get_bounding_box(
        complaint.latitude,
        complaint.longitude,
        search_radius_meters
    )

    # Coarse spatial query using bounding box on indexed coordinates
    query = db.query(PhysicalIssue).filter(
        PhysicalIssue.representative_latitude >= min_lat,
        PhysicalIssue.representative_latitude <= max_lat,
        PhysicalIssue.representative_longitude >= min_lon,
        PhysicalIssue.representative_longitude <= max_lon
    )

    # If the complaint is already attached to an issue, don't re-match the exact same issue
    if complaint.issue_id:
        query = query.filter(PhysicalIssue.issue_reference_id != complaint.issue_id)

    candidates = query.all()

    # Precise Haversine distance filtering
    results = []
    for issue in candidates:
        dist = calculate_haversine_distance(
            complaint.latitude,
            complaint.longitude,
            issue.representative_latitude,
            issue.representative_longitude
        )
        if dist <= search_radius_meters:
            results.append((issue, round(dist, 2)))

    # Sort nearest first
    results.sort(key=lambda x: x[1])
    return results

