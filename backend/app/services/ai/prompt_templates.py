VALID_CATEGORIES = [
    "Road Damage / Potholes",
    "Garbage Accumulation",
    "Drainage Overflow",
    "Water Leakage",
    "Broken Streetlights",
    "Damaged Public Infrastructure",
    "Other"
]

COMPLAINT_ANALYSIS_SYSTEM_INSTRUCTION = """
You are JanSakshi's civic infrastructure analysis agent.
Your mission is to objectively analyze public infrastructure complaints submitted by citizens, together with any photographic evidence.

Core Guidelines:
1. Objectivity: Identify only what is factually visible and stated. Do not fabricate details.
2. Evidence Relevance: Evaluate if the image directly corroborates the reported problem.
3. Quality vs Authenticity: An unclear or blurry photo does not mean the complaint is fraudulent; it merely means photographic evidence is insufficient or requires human verification.
4. Human Review: You do NOT make final government determinations. Always flag issues for human review if there is ambiguity, category disagreement, or serious public safety hazards.
5. Strict JSON: You must always respond with valid JSON matching the requested schema. Do not include markdown formatting or extra text outside the JSON object.
"""

def build_complaint_analysis_prompt(
    category: str,
    description: str,
    has_image: bool = False
) -> str:
    categories_str = ", ".join([f'"{c}"' for c in VALID_CATEGORIES])

    return f"""
Analyze the following civic complaint:

Citizen-Reported Category: "{category}"
Citizen Description: "{description}"
Evidence Image Provided: {"Yes" if has_image else "No"}

Permitted Issue Categories:
[{categories_str}]

Output Requirements:
Return a single JSON object with these exact keys:
{{
  "predicted_category": "<One of the permitted categories listed above>",
  "category_confidence": <float between 0.0 and 1.0>,
  "complaint_summary": "<A concise, neutral 1-2 sentence summary of the reported problem>",
  "visible_problem": "<What problem is visibly identifiable in the image or described, or 'No image provided'>",
  "evidence_relevance": "<'relevant', 'insufficient', 'unclear', 'unrelated', or 'not_applicable'>",
  "relevance_score": <integer from 0 to 100>,
  "image_quality": "<'good', 'acceptable', 'blurred', 'dark', 'obstructed', or 'inconclusive'>",
  "clarity_score": <integer from 0 to 100>,
  "visibility_score": <integer from 0 to 100>,
  "additional_evidence_required": <boolean>,
  "recommended_severity": "<'low', 'medium', 'high', or 'critical'>",
  "severity_confidence": <float between 0.0 and 1.0>,
  "reasoning": "<1-3 sentences explaining your severity and category assessment>",
  "human_review_required": <boolean>,
  "review_reasons": ["<List of specific reasons why a human inspector should review this>"]
}}
"""

