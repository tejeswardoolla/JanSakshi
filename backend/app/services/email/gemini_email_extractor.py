import os
import re
import json
import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from app.core.config import GEMINI_API_KEY, GEMINI_MODEL, is_gemini_configured
from app.services.location_service import resolve_location_input

logger = logging.getLogger("jansakshi.gemini.email_extractor")

VALID_CATEGORIES = [
    "Road Damage / Potholes",
    "Broken Streetlights",
    "Garbage Accumulation",
    "Drainage Overflow",
    "Water Leakage",
    "Damaged Public Infrastructure",
    "Other",
]

class GeminiEmailExtractionResult(BaseModel):
    """Structured extraction output validated by Pydantic."""
    is_civic_complaint: bool = Field(True, description="Whether the email is a genuine public infrastructure complaint")
    non_civic_reason: Optional[str] = Field(None, description="Reason if classified as non-civic (spam, marketing, general)")
    category: str = Field("Other", description="Standardized civic category")
    description: str = Field(..., description="Cleaned problem description preserving citizen context")
    urgency: str = Field("medium", description="Urgency: low, medium, high, emergency")
    location_text: Optional[str] = Field(None, description="Extracted landmark, address, street, or intersection")
    latitude: Optional[float] = Field(None, description="Latitude ONLY if explicitly stated")
    longitude: Optional[float] = Field(None, description="Longitude ONLY if explicitly stated")
    google_maps_url: Optional[str] = Field(None, description="Google Maps URL if found in email")
    plus_code: Optional[str] = Field(None, description="Plus Code if found in email")
    missing_information: List[str] = Field(default_factory=list, description="Missing details like coordinates or exact address")
    is_follow_up: bool = Field(False, description="Whether this email is a follow-up/reply to a previous report")
    referenced_complaint_id: Optional[str] = Field(None, description="Referenced complaint ID (e.g. JS-2026-00001) if present")

EMAIL_EXTRACTION_SYSTEM_PROMPT = f"""
You are the JanSakshi Civic Email Extraction Agent.
Your job is to analyze incoming citizen emails sent to a civic grievance authority, determine if they represent a genuine public infrastructure or municipal complaint, and extract structured information.

Permitted Categories:
{json.dumps(VALID_CATEGORIES, indent=2)}

STRICT LOCATION & LANDMARK EXTRACTION PRIORITY:
1. Extract landmarks, specific addresses, street names, intersections, cities, and states from the EMAIL BODY FIRST.
2. NEVER use the email subject (or subject title) as `location_text` or `landmark` when a more specific landmark or address is present in the email body.
3. The subject may provide supplementary context only (e.g. city name if missing from body).
4. If the body contains explicit location labels (such as "*Location:*", "Location:", "Address:", "Landmark:", "near <landmark>"), extract that exact phrase into `location_text`.
5. If a Google Maps link (e.g. "maps.google.com", "goo.gl/maps", "maps.app.goo.gl") is present anywhere in the text, extract it into `google_maps_url`.
6. If a Plus Code is present (e.g. "7M8Q+9X Hyderabad"), extract it into `plus_code`.

STRICT ANTI-HALLUCINATION RULES:
1. NEVER invent an address, landmark, or GPS coordinates.
2. If the citizen did NOT explicitly mention numerical coordinates in text (e.g. "17.4375, 78.4482"), leave `latitude` and `longitude` as null (the system will parse Google Maps URLs separately).
3. If location is mentioned as a general description without coordinates, place it in `location_text` and list "location_coordinates" in `missing_information`.
4. If the email is clearly non-civic (e.g. newsletter, advertising, password reset, personal chat, receipt), set `is_civic_complaint: false` and provide `non_civic_reason`.
5. If the subject or body references a previous complaint ID (e.g. "Re: JS-2026-00001", "regarding complaint JS-2026-00004"), set `is_follow_up: true` and set `referenced_complaint_id`.

Your response MUST be a single valid JSON object adhering strictly to the JSON structure without Markdown or commentary.
"""

def extract_landmark_from_text(body: str, subject: str = "") -> Optional[str]:
    """
    Extracts landmark, street address, intersection, city, or state from email text.
    Prioritizes email body. Never returns generic complaint titles or subjects as landmarks.
    """
    body = body or ""

    # 1. Check for labeled location field in body (e.g. *Location:*, Location:, Address:, Landmark:)
    labeled_match = re.search(
        r"(?:^|\n)\s*(?:\*|_)?(?:Location|Address|Landmark|Incident Location|Place|Site|Area)(?:\*|_)?\s*:\s*([^\r\n]+)",
        body,
        re.IGNORECASE
    )
    if labeled_match:
        val = labeled_match.group(1).strip()
        val = re.sub(r"^[\*_\'\"]+|[\*_\'\"]+$", "", val).strip(" .;,")
        if not val.startswith("http") and len(val) >= 3:
            return val

    # 2. Check for prepositional location phrases in body (e.g. near Morampudi Junction, at Main Road)
    prep_match = re.search(
        r"\b(?:located\s+(?:at|near|in)|issue\s+(?:at|near|in)|problem\s+(?:at|near|in)|near|opposite|behind|in\s+front\s+of|beside|across\s+from)\s+([A-Z0-9][^\.\n\r;]{3,100})",
        body,
        re.IGNORECASE
    )
    if prep_match:
        val = prep_match.group(1).strip()
        # Strip trailing citizen requests or signatures (e.g. Please look into..., Thanks...)
        val = re.sub(r"[\s,\.]+(?:Please|Kindly|Urgent|Thanks|Thank\s+you|And\s+arrange).*$", "", val, flags=re.IGNORECASE).strip(" .;,")
        if not val.startswith("http") and len(val) >= 4:
            return val

    # 3. Check for general landmark keywords in body lines
    for line in body.splitlines():
        line_clean = line.strip()
        if not line_clean or line_clean.startswith("http") or len(line_clean) > 120:
            continue
        if re.search(r"\b(?:Junction|Circle|Cross|Road|Street|Marg|Nagar|Colony|Layout|Sector|Phase|Ward|Bazaar|Market|Chowk|Flyover|Bridge)\b", line_clean, re.IGNORECASE):
            cleaned_line = re.sub(r"^(?:Please\s+look\s+into|Report\s+at|There\s+is\s+a\s+[^,]+at|issue\s+near|issue\s+at)\s+", "", line_clean, flags=re.IGNORECASE).strip(" .;,*")
            if len(cleaned_line) >= 4 and not cleaned_line.startswith("http"):
                return cleaned_line

    # 4. If body has no specific landmark, check if subject explicitly contains location preposition
    if subject:
        subj_match = re.search(r"\b(?:at|near|opposite|in)\s+([A-Z][a-zA-Z0-9\s,\'-]{3,60})$", subject.strip())
        if subj_match:
            cand = subj_match.group(1).strip(" .;,")
            if cand.lower() not in ("jansakshi", "complaint", "portal", "system"):
                return cand

    return None

def extract_via_heuristics(subject: str, body: str) -> GeminiEmailExtractionResult:
    """
    Deterministic rule-based fallback when Gemini API key is missing, network is down, or rate-limited.
    Never invents coordinates or addresses.
    """
    combined = f"{subject}\n{body}".strip()
    lower_text = combined.lower()

    # Check for follow-up reference (JS-YYYY-NNNNN)
    ref_match = re.search(r'\b(JS-\d{4}-\d{5})\b', combined, re.IGNORECASE)
    referenced_id = ref_match.group(1).upper() if ref_match else None
    is_follow_up = bool(referenced_id or "re:" in subject.lower() or "fwd:" in subject.lower())

    # Check for obvious non-civic / spam signals
    spam_keywords = ["unsubscribe", "newsletter", "promotional", "discount", "order confirmation", "invoice", "receipt", "verification code"]
    if any(k in lower_text for k in spam_keywords) and not any(c in lower_text for c in ["pothole", "streetlight", "drainage", "garbage", "leakage"]):
        return GeminiEmailExtractionResult(
            is_civic_complaint=False,
            non_civic_reason="Automated promotional/transactional email without civic complaint keywords.",
            category="Other",
            description=subject or "Non-civic automated message",
            urgency="low",
            missing_information=[],
            is_follow_up=False,
            referenced_complaint_id=None
        )

    # Category matching
    category = "Other"
    has_civic_keyword = False
    if any(w in lower_text for w in ["pothole", "potholes", "road damage", "crater", "asphalt", "broken road"]):
        category = "Road Damage / Potholes"
        has_civic_keyword = True
    elif any(w in lower_text for w in ["streetlight", "street light", "lamp post", "dark lane", "street light broken"]):
        category = "Broken Streetlights"
        has_civic_keyword = True
    elif any(w in lower_text for w in ["garbage", "trash", "dump", "waste", "rubbish", "uncollected"]):
        category = "Garbage Accumulation"
        has_civic_keyword = True
    elif any(w in lower_text for w in ["drain", "drainage", "sewage", "sewer", "overflow", "gutter", "manhole"]):
        category = "Drainage Overflow"
        has_civic_keyword = True
    elif any(w in lower_text for w in ["water leak", "pipeline", "pipe burst", "water pipe", "drinking water"]):
        category = "Water Leakage"
        has_civic_keyword = True
    elif any(w in lower_text for w in ["bridge", "footpath", "bench", "park", "railing", "public toilet"]):
        category = "Damaged Public Infrastructure"
        has_civic_keyword = True

    if not has_civic_keyword and not is_follow_up:
        return GeminiEmailExtractionResult(
            is_civic_complaint=False,
            non_civic_reason="No recognizable municipal complaint keywords identified in heuristic analysis.",
            category="Other",
            description=subject or "Unrecognized message content",
            urgency="low",
            missing_information=[],
            is_follow_up=False,
            referenced_complaint_id=None
        )

    # Search for coordinates: e.g. 17.4375, 78.4482
    coord_match = re.search(r'(-?\d{1,2}\.\d{3,8})[\s,]+(-?\d{1,3}\.\d{3,8})', combined)
    latitude = None
    longitude = None
    if coord_match:
        try:
            lat = float(coord_match.group(1))
            lng = float(coord_match.group(2))
            if -90 <= lat <= 90 and -180 <= lng <= 180:
                latitude = lat
                longitude = lng
        except ValueError:
            pass

    # Search for Google Maps URL
    gmaps_match = re.search(r'(https?://(?:maps\.app\.goo\.gl|goo\.gl/maps|www\.google\.com/maps|maps\.google\.com)[^\s<>"\']+)', combined)
    google_maps_url = gmaps_match.group(1) if gmaps_match else None

    # Search for Plus Code
    plus_code_match = re.search(r'\b([23456789CFGHJMPQRVWX]{4,8}\+[23456789CFGHJMPQRVWX]{2,4}(?:\s+[A-Za-z\s,]+)?)\b', combined)
    plus_code = plus_code_match.group(1).strip() if plus_code_match else None

    # If maps link or plus code found, try resolving coordinates
    if (latitude is None or longitude is None) and (google_maps_url or plus_code):
        query = google_maps_url or plus_code
        success, rlat, rlng, _, _, _ = resolve_location_input(query)
        if success and rlat is not None and rlng is not None:
            latitude = rlat
            longitude = rlng

    missing_info = []
    if latitude is None or longitude is None:
        missing_info.append("location_coordinates")

    # Extract landmark from body first; never use subject when body has location
    landmark = extract_landmark_from_text(body, subject)

    # Clean description
    desc = body.strip() if len(body.strip()) >= 10 else f"{subject}. {body}".strip()
    if len(desc) < 10:
        desc = f"Civic report: {subject}"

    return GeminiEmailExtractionResult(
        is_civic_complaint=True,
        non_civic_reason=None,
        category=category,
        description=desc[:1900],
        urgency="medium",
        location_text=landmark,
        latitude=latitude,
        longitude=longitude,
        google_maps_url=google_maps_url,
        plus_code=plus_code,
        missing_information=missing_info,
        is_follow_up=is_follow_up,
        referenced_complaint_id=referenced_id
    )

class GeminiEmailExtractor:
    """
    Orchestrates extraction using Google Gemini AI, falling back to robust heuristics
    if Gemini is unconfigured, rate-limited, or times out.
    Features a circuit-breaker to instantly fall back when quota limits (429) are active.
    """

    _quota_exhausted_until: float = 0.0

    @classmethod
    async def extract(
        cls,
        subject: str,
        body: str,
        sender_email: Optional[str] = None
    ) -> GeminiEmailExtractionResult:
        """
        Extracts structured complaint metadata from subject and body.
        Guarantees non-null, validated output.
        """
        import time
        # Circuit-breaker check or unconfigured
        if time.time() < cls._quota_exhausted_until or not is_gemini_configured() or not GEMINI_API_KEY:
            logger.info("Using heuristic email extraction (Gemini standby/quota circuit breaker).")
            return extract_via_heuristics(subject, body)

        prompt = f"""
Incoming Citizen Email for Analysis:
Subject: {subject}
Body:
{body}

Extract structured complaint data according to the system instructions.
"""

        def _call_gemini_sync():
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=GEMINI_API_KEY)
            config = types.GenerateContentConfig(
                system_instruction=EMAIL_EXTRACTION_SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=0.1,
            )
            return client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=config
            )

        try:
            import asyncio
            response = await asyncio.wait_for(asyncio.to_thread(_call_gemini_sync), timeout=6.0)
            raw_text = response.text.strip()
            # Clean possible markdown wrap
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]

            data = json.loads(raw_text.strip())

            # Validate category against valid categories
            category = data.get("category", "Other")
            if category not in VALID_CATEGORIES:
                category = "Other"

            result = GeminiEmailExtractionResult(
                is_civic_complaint=data.get("is_civic_complaint", True),
                non_civic_reason=data.get("non_civic_reason"),
                category=category,
                description=data.get("description") or subject or "Citizen reported issue.",
                urgency=data.get("urgency", "medium"),
                location_text=data.get("location_text"),
                latitude=data.get("latitude"),
                longitude=data.get("longitude"),
                google_maps_url=data.get("google_maps_url"),
                plus_code=data.get("plus_code"),
                missing_information=data.get("missing_information", []),
                is_follow_up=data.get("is_follow_up", False),
                referenced_complaint_id=data.get("referenced_complaint_id"),
            )

            # Secondary coordinate resolution: check Maps URL from extraction or text
            maps_url = result.google_maps_url
            if not maps_url:
                gmaps_match = re.search(r'(https?://(?:maps\.app\.goo\.gl|goo\.gl/maps|www\.google\.com/maps|maps\.google\.com)[^\s<>"\']+)', f"{subject}\n{body}")
                if gmaps_match:
                    maps_url = gmaps_match.group(1)
                    result.google_maps_url = maps_url

            if (result.latitude is None or result.longitude is None):
                q = maps_url or result.plus_code
                if q:
                    success, lat, lng, _, _, _ = resolve_location_input(q)
                    if success and lat is not None and lng is not None:
                        result.latitude = lat
                        result.longitude = lng
                        result.missing_information = [m for m in result.missing_information if m != "location_coordinates"]

            # Location landmark priority: ensure body landmark is prioritized over subject
            body_landmark = extract_landmark_from_text(body, subject)
            if body_landmark:
                curr_loc = (result.location_text or "").strip()
                # If Gemini returned empty, or echoed the subject or generic title, override with body landmark
                if not curr_loc or curr_loc.lower() == subject.strip().lower() or subject.strip().lower() in curr_loc.lower():
                    result.location_text = body_landmark
            elif not result.location_text:
                result.location_text = body_landmark

            return result

        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                import time
                cls._quota_exhausted_until = time.time() + 300.0
            logger.warning(f"Gemini email extraction encountered error or timeout: {e}. Falling back to heuristic extraction.")
            return extract_via_heuristics(subject, body)
