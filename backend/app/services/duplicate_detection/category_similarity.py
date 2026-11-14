from typing import Optional

# Related category clusters with partial compatibility weights
COMPATIBLE_PAIRS = {
    frozenset(["road damage / potholes", "damaged public infrastructure"]): 0.55,
    frozenset(["drainage overflow", "water leakage"]): 0.50,
    frozenset(["drainage overflow", "damaged public infrastructure"]): 0.40,
    frozenset(["water leakage", "damaged public infrastructure"]): 0.40,
    frozenset(["broken streetlights", "damaged public infrastructure"]): 0.45,
}

def calculate_category_similarity(cat1: Optional[str], cat2: Optional[str]) -> float:
    """
    Evaluates category similarity between two complaints/issues:
    - 1.0 for exact matches
    - 0.40 - 0.55 for semantically compatible categories
    - 0.30 if either category is 'Other'
    - 0.0 for distinct, incompatible categories
    """
    if not cat1 or not cat2:
        return 0.3  # Neutral score if category is unknown

    c1 = cat1.strip().lower()
    c2 = cat2.strip().lower()

    if c1 == c2:
        return 1.0

    pair = frozenset([c1, c2])
    if pair in COMPATIBLE_PAIRS:
        return COMPATIBLE_PAIRS[pair]

    if "other" in c1 or "other" in c2:
        return 0.3

    return 0.0

