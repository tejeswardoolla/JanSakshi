import math
from typing import Optional, Tuple

EARTH_RADIUS_METERS = 6371000.0
DEFAULT_MAX_RADIUS_METERS = 100.0
ZERO_TOLERANCE_METERS = 5.0

def calculate_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes geodesic distance between two GPS coordinates in meters using the Haversine formula.
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2)
    
    # Numerical clamp
    a = min(1.0, max(0.0, a))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_METERS * c

def calculate_location_similarity(
    distance_meters: Optional[float],
    max_radius_meters: float = DEFAULT_MAX_RADIUS_METERS,
    zero_tolerance_meters: float = ZERO_TOLERANCE_METERS
) -> Optional[float]:
    """
    Normalizes distance in meters into a 0.0 to 1.0 similarity score using a smooth cosine decay curve.
    - distance <= zero_tolerance_meters: 1.0
    - distance >= max_radius_meters: 0.0
    - in-between: smooth transition between 1.0 and 0.0
    """
    if distance_meters is None or distance_meters < 0:
        return None

    if distance_meters <= zero_tolerance_meters:
        return 1.0
    if distance_meters >= max_radius_meters:
        return 0.0

    # Smooth S-curve (cosine decay)
    fraction = (distance_meters - zero_tolerance_meters) / (max_radius_meters - zero_tolerance_meters)
    similarity = 0.5 * (1.0 + math.cos(math.pi * fraction))
    return round(float(similarity), 4)

def get_bounding_box(lat: float, lon: float, radius_meters: float) -> Tuple[float, float, float, float]:
    """
    Calculates min_lat, max_lat, min_lon, max_lon for an approximate bounding box around (lat, lon).
    Useful for indexed candidate filtering before precise Haversine calculation.
    """
    delta_lat = radius_meters / 111320.0
    cos_lat = math.cos(math.radians(lat))
    if abs(cos_lat) < 1e-6:
        delta_lon = 180.0
    else:
        delta_lon = radius_meters / (111320.0 * cos_lat)

    return (
        lat - delta_lat,
        lat + delta_lat,
        lon - delta_lon,
        lon + delta_lon
    )

