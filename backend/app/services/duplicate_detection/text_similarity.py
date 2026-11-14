import re
import math
from typing import Optional, Set, List, Dict
from collections import Counter

STOPWORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "aren't",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but", "by", "can",
    "cannot", "could", "did", "do", "does", "doing", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself", "him", "himself",
    "his", "how", "i", "if", "in", "into", "is", "isn't", "it", "its", "itself", "let's", "me", "more",
    "most", "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought",
    "our", "ours", "ourselves", "out", "over", "own", "same", "she", "should", "so", "some", "such",
    "than", "that", "the", "their", "theirs", "them", "themselves", "then", "there", "these", "they",
    "this", "those", "through", "to", "too", "under", "until", "up", "very", "was", "wasn't", "we", "were",
    "weren't", "what", "when", "where", "which", "while", "who", "whom", "why", "with", "won't", "would",
    "you", "your", "yours", "yourself", "yourselves", "please", "kindly", "urgent", "complaint", "issue",
    "problem", "there", "is", "are"
}

def normalize_text(text: str) -> str:
    """Standardizes civic compound words and common variants."""
    t = text.lower()
    t = re.sub(r'pot[\s\-_]+hole[s]?', 'pothole', t)
    t = re.sub(r'street[\s\-_]+light[s]?', 'streetlight', t)
    t = re.sub(r'garbage[\s\-_]+dump[s]?', 'garbage', t)
    t = re.sub(r'drain[\s\-_]+age', 'drainage', t)
    t = re.sub(r'water[\s\-_]+leak(age)?', 'waterleak', t)
    return t

def stem_word(w: str) -> str:
    """Lightweight civic word stemmer."""
    if len(w) > 4:
        w = re.sub(r'(ing|ed|es|s)$', '', w)
    return w

def tokenize(text: str) -> List[str]:
    """Tokenize and stem words, filtering stopwords."""
    norm = normalize_text(text)
    words = re.findall(r'[a-zA-Z0-9]+', norm)
    tokens = []
    for w in words:
        if len(w) > 1 and w not in STOPWORDS:
            tokens.append(stem_word(w))
    return tokens

def cosine_similarity(vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
    """Compute cosine similarity between two term frequency vectors."""
    intersection = set(vec1.keys()) & set(vec2.keys())
    if not intersection:
        return 0.0

    dot_product = sum(vec1[k] * vec2[k] for k in intersection)
    norm1 = math.sqrt(sum(v ** 2 for v in vec1.values()))
    norm2 = math.sqrt(sum(v ** 2 for v in vec2.values()))

    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot_product / (norm1 * norm2)

def calculate_text_similarity(text1: Optional[str], text2: Optional[str]) -> Optional[float]:
    """
    Computes semantic/lexical similarity between two text descriptions in range [0.0, 1.0].
    Combines:
    1. Unigram TF cosine similarity (45%)
    2. Token Overlap coefficient (containment) (35%)
    3. Token Jaccard coefficient (20%)
    """
    if not text1 or not text2:
        return None

    t1_clean = text1.strip()
    t2_clean = text2.strip()
    if not t1_clean or not t2_clean:
        return None

    if t1_clean.lower() == t2_clean.lower():
        return 1.0

    tokens1 = tokenize(t1_clean)
    tokens2 = tokenize(t2_clean)

    if not tokens1 or not tokens2:
        return 0.0

    # 1. Unigram Term Frequency Cosine Similarity
    v1 = Counter(tokens1)
    v2 = Counter(tokens2)
    cosine_sim = cosine_similarity(dict(v1), dict(v2))

    # 2. Set-based metrics
    s1 = set(tokens1)
    s2 = set(tokens2)
    intersection = s1 & s2

    if not intersection:
        return round(float(cosine_sim), 4)

    min_len = min(len(s1), len(s2))
    overlap_sim = len(intersection) / min_len if min_len > 0 else 0.0
    jaccard_sim = len(intersection) / len(s1 | s2)

    composite = 0.45 * cosine_sim + 0.35 * overlap_sim + 0.20 * jaccard_sim
    return round(float(min(1.0, max(0.0, composite))), 4)
