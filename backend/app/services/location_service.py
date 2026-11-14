import re
import urllib.parse
from typing import Optional, Tuple
from openlocationcode import openlocationcode as olc

def parse_coordinates(text: str) -> Optional[Tuple[float, float]]:
    """Parse lat,lng from plain text coordinates."""
    match = re.search(r"(-?\d{1,2}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)", text.strip())
    if match:
        try:
            lat = float(match.group(1))
            lng = float(match.group(2))
            if -90 <= lat <= 90 and -180 <= lng <= 180:
                return lat, lng
        except ValueError:
            return None
    return None

def parse_google_maps_url(url: str) -> Optional[Tuple[float, float]]:
    """
    Extract coordinates from Google Maps URLs (shortened or expanded).
    Supports query URLs, encoded commas (%2C), @lat,lng, /place/ paths, and protobuf embeds.
    Validates latitude (-90 to 90) and longitude (-180 to 180).
    """
    if not url or not isinstance(url, str):
        return None

    raw = url.strip()
    unquoted = urllib.parse.unquote(raw)

    patterns = [
        # 1. ?q=lat,lng or &query=lat,lng or &ll=lat,lng (supports %2C or comma or space or +)
        r"[?&](?:q|query|ll)=(-?\d{1,2}\.\d+)(?:[,\s\+]|%2C|%2c)+(-?\d{1,3}\.\d+)",
        # 2. @lat,lng
        r"@(-?\d{1,2}\.\d+)(?:,|%2C|%2c)(-?\d{1,3}\.\d+)",
        # 3. !3dlat!4dlng (Google Maps embedded coordinate format)
        r"!3d(-?\d{1,2}\.\d+)!4d(-?\d{1,3}\.\d+)",
        # 4. /place/lat,lng or /place/lat+lng
        r"/place/(-?\d{1,2}\.\d+)(?:[,\s\+]|%2C|%2c)+(-?\d{1,3}\.\d+)",
        # 5. /search/lat,lng or /search/lat+lng
        r"/search/(?:[^/?#]+/)?(-?\d{1,2}\.\d+)(?:[,\s\+]|%2C|%2c)+(-?\d{1,3}\.\d+)",
    ]

    for candidate in (unquoted, raw):
        for pat in patterns:
            m = re.search(pat, candidate, re.IGNORECASE)
            if m:
                try:
                    lat = float(m.group(1))
                    lng = float(m.group(2))
                    if -90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0:
                        return lat, lng
                except ValueError:
                    continue

    return None

def resolve_plus_code(code: str) -> Optional[Tuple[float, float]]:
    """Convert a Google Plus Code (Open Location Code) to latitude and longitude."""
    cleaned = code.strip()
    # Check if full plus code (e.g., 7J4V9F72+8M)
    if olc.isValid(cleaned):
        if olc.isFull(cleaned):
            area = olc.decode(cleaned)
            return area.latitudeCenter, area.longitudeCenter
        else:
            # Short code requires reference location; cannot decode safely without one
            return None
    # Sometimes user inputs text with plus code like "9F72+8M, Bangalore" or "7J4V9F72+8M"
    words = cleaned.split()
    for w in words:
        clean_w = w.strip(",.;")
        if olc.isValid(clean_w) and olc.isFull(clean_w):
            area = olc.decode(clean_w)
            return area.latitudeCenter, area.longitudeCenter
    return None

def resolve_location_input(raw: str) -> Tuple[bool, Optional[float], Optional[float], str, Optional[str], Optional[str]]:
    """
    Returns (success, lat, lng, source, google_maps_url, message)
    """
    cleaned = raw.strip()
    if not cleaned:
        return False, None, None, "unknown", None, "Location input cannot be empty."

    # 1. Direct coordinates
    coords = parse_coordinates(cleaned)
    if coords:
        lat, lng = coords
        return True, lat, lng, "manual", f"https://www.google.com/maps?q={lat:.6f},{lng:.6f}", None

    # 2. Google Maps URL
    if "maps" in cleaned.lower() or "goo.gl" in cleaned.lower():
        coords = parse_google_maps_url(cleaned)
        if coords:
            lat, lng = coords
            return True, lat, lng, "maps_url", f"https://www.google.com/maps?q={lat:.6f},{lng:.6f}", None
        else:
            return False, None, None, "maps_url", None, "Could not extract coordinates from Google Maps link. Please paste full link containing coordinates or enter latitude/longitude directly."

    # 3. Plus Code
    coords = resolve_plus_code(cleaned)
    if coords:
        lat, lng = coords
        return True, lat, lng, "plus_code", f"https://www.google.com/maps?q={lat:.6f},{lng:.6f}", None

    if "+" in cleaned:
        return False, None, None, "plus_code", None, "Short Plus Code detected. Plus Codes without area prefix (full 10-11 char code like 7J4V9F72+8M) cannot be uniquely resolved. Please use full Plus Code, GPS, or coordinates."

    return False, None, None, "unknown", None, "Unrecognized location format. Please provide coordinates (e.g. 17.3850, 78.4867), full Plus Code, or Google Maps URL."

