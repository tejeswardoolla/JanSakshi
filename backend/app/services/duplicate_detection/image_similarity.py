import os
import logging
from typing import Optional, List
from PIL import Image

logger = logging.getLogger("jansakshi.duplicate_detection.image")

def compute_dhash(image_path: str, hash_size: int = 8) -> Optional[int]:
    """
    Computes a Difference Hash (dHash) for an image.
    Robust to slight rotations, scaling, and compression artifacts.
    """
    if not os.path.exists(image_path):
        return None

    try:
        with Image.open(image_path) as img:
            # Convert to grayscale and resize to (hash_size + 1, hash_size)
            resized = img.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.BILINEAR)
            pixels = list(resized.getdata())

            difference = []
            for row in range(hash_size):
                row_start = row * (hash_size + 1)
                for col in range(hash_size):
                    pixel_left = pixels[row_start + col]
                    pixel_right = pixels[row_start + col + 1]
                    difference.append(pixel_left > pixel_right)

            # Convert boolean array to integer hash
            hash_val = 0
            for bit in difference:
                hash_val = (hash_val << 1) | (1 if bit else 0)
            return hash_val
    except Exception as e:
        logger.warning(f"Failed to compute dHash for {image_path}: {e}")
        return None

def compute_ahash(image_path: str, hash_size: int = 8) -> Optional[int]:
    """
    Computes an Average Hash (aHash) for an image.
    """
    if not os.path.exists(image_path):
        return None

    try:
        with Image.open(image_path) as img:
            resized = img.convert("L").resize((hash_size, hash_size), Image.Resampling.BILINEAR)
            pixels = list(resized.getdata())
            avg = sum(pixels) / len(pixels)

            hash_val = 0
            for pixel in pixels:
                hash_val = (hash_val << 1) | (1 if pixel > avg else 0)
            return hash_val
    except Exception as e:
        logger.warning(f"Failed to compute aHash for {image_path}: {e}")
        return None

def hamming_distance(hash1: int, hash2: int, bit_length: int = 64) -> int:
    """Computes number of differing bits between two integer hashes."""
    xor = hash1 ^ hash2
    return bin(xor).count('1')

def calculate_single_image_similarity(path1: str, path2: str) -> Optional[float]:
    """
    Calculates perceptual similarity between two images on disk in range [0.0, 1.0].
    Returns None if either image is missing or invalid.
    """
    dhash1 = compute_dhash(path1)
    dhash2 = compute_dhash(path2)
    ahash1 = compute_ahash(path1)
    ahash2 = compute_ahash(path2)

    if dhash1 is None or dhash2 is None or ahash1 is None or ahash2 is None:
        return None

    dist_d = hamming_distance(dhash1, dhash2, 64)
    dist_a = hamming_distance(ahash1, ahash2, 64)

    # Convert Hamming distance into [0.0, 1.0] similarity
    # 0 distance -> 1.0; 32 distance (random noise) -> 0.0; > 32 distance -> 0.0
    sim_d = max(0.0, 1.0 - (dist_d / 32.0))
    sim_a = max(0.0, 1.0 - (dist_a / 32.0))

    composite = 0.60 * sim_d + 0.40 * sim_a
    return round(float(composite), 4)

def compare_evidence_lists(paths1: List[str], paths2: List[str]) -> Optional[float]:
    """
    Compares two lists of image paths and returns the maximum similarity among any pair.
    Returns None if either list has no valid images.
    """
    valid_paths1 = [p for p in paths1 if p and os.path.exists(p)]
    valid_paths2 = [p for p in paths2 if p and os.path.exists(p)]

    if not valid_paths1 or not valid_paths2:
        return None

    max_sim: Optional[float] = None
    for p1 in valid_paths1:
        for p2 in valid_paths2:
            sim = calculate_single_image_similarity(p1, p2)
            if sim is not None:
                if max_sim is None or sim > max_sim:
                    max_sim = sim

    return max_sim

