import os
import io
import logging
import ipaddress
import socket
import ssl
import http.client
from typing import Optional, List, Tuple, Dict
from urllib.parse import urlparse
from PIL import Image

logger = logging.getLogger("jansakshi.duplicate_detection.image")

# Pillow safety limits: prevent decompression bombs and enormous bitmaps
Image.MAX_IMAGE_PIXELS = 25_000_000
MAX_IMAGE_DOWNLOAD_BYTES = 10 * 1024 * 1024  # 10 MB maximum
FETCH_CONNECT_TIMEOUT = 3.0                   # 3 seconds connection timeout
FETCH_READ_TIMEOUT = 5.0                      # 5 seconds read timeout

# Verified production Vercel Blob domains used by JanSakshi
VERIFIED_BLOB_DOMAINS = (
    "public.blob.vercel-storage.com",
    "blob.vercel-storage.com",
)

class PinnedHTTPSConnection(http.client.HTTPSConnection):
    """
    HTTP client connection that pins the TCP connection to a pre-validated public IP address
    while preserving TLS SNI (Server Name Indication) and full certificate verification
    against the target hostname. Eliminates TOCTOU DNS rebinding SSRF vulnerabilities.
    """
    def __init__(self, host: str, port: int = 443, pinned_ip: Optional[str] = None, **kwargs):
        super().__init__(host, port, **kwargs)
        self.pinned_ip = pinned_ip

    def connect(self):
        sock = socket.create_connection(
            (self.pinned_ip or self.host, self.port),
            self.timeout
        )
        if self._tunnel_host:
            self.sock = sock
            self._tunnel()
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)

def _is_ip_address(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False

def get_validated_safe_storage_ip(url: str) -> Optional[Tuple[str, str, str]]:
    """
    Validates evidence URL to prevent SSRF, DNS rebinding, and credential leakage:
    - HTTPS scheme only
    - No userinfo (user:pass@host)
    - Standard HTTPS port only (None or 443)
    - Hostname must be in VERIFIED_BLOB_DOMAINS
    - Hostname cannot be a numeric IP, localhost, or link-local address
    - Resolves DNS and verifies target IP is not private, loopback, link-local, or multicast
    Returns (hostname, path_and_query, validated_ip) or None if invalid.
    """
    if not url or not isinstance(url, str):
        return None

    try:
        parsed = urlparse(url)
        if parsed.scheme.lower() != "https":
            return None

        # Reject userinfo
        if parsed.username or parsed.password:
            return None

        # Reject non-standard ports
        if parsed.port not in (None, 443):
            return None

        hostname = (parsed.hostname or "").lower()
        if not hostname:
            return None

        # Reject localhost explicitly
        if hostname == "localhost" or hostname.endswith(".localhost"):
            return None

        # Reject numeric IPs
        if _is_ip_address(hostname):
            return None

        # Must strictly match or be subdomain of verified Vercel Blob domains
        domain_match = any(
            hostname == d or hostname.endswith("." + d)
            for d in VERIFIED_BLOB_DOMAINS
        )
        if not domain_match:
            return None

        # Validate resolved IP to block DNS rebinding to private / link-local / metadata networks
        try:
            addr_info = socket.getaddrinfo(hostname, 443, socket.AF_UNSPEC, socket.SOCK_STREAM)
            safe_ip = None
            for family, socktype, proto, canonname, sockaddr in addr_info:
                ip_str = sockaddr[0]
                ip_obj = ipaddress.ip_address(ip_str)
                if (
                    ip_obj.is_private
                    or ip_obj.is_loopback
                    or ip_obj.is_link_local
                    or ip_obj.is_multicast
                    or ip_obj.is_reserved
                ):
                    logger.warning(f"SSRF block: Hostname {hostname} resolved to unsafe IP {ip_str}")
                    return None
                if safe_ip is None:
                    safe_ip = ip_str

            if not safe_ip:
                return None

            path = parsed.path or "/"
            if parsed.query:
                path = f"{path}?{parsed.query}"

            return hostname, path, safe_ip

        except Exception as dns_err:
            logger.warning(f"DNS resolution check failure for {hostname}: {dns_err}")
            return None

    except Exception as e:
        logger.warning(f"Evidence URL validation error: {e}")
        return None

def validate_safe_evidence_url(url: str) -> bool:
    """Public helper to check if an evidence URL is safe and valid."""
    return get_validated_safe_storage_ip(url) is not None

def _fetch_safe_remote_bytes(url: str) -> Optional[bytes]:
    """
    Fetches remote image bytes safely:
    - Pre-validates URL and pins connection to resolved safe IP
    - Disables second DNS resolution (eliminating TOCTOU DNS rebinding)
    - Verifies TLS certificate and SNI against target hostname
    - Streams response with strict 10 MB ceiling
    - Sets tight connection and read timeouts
    - Attaches authorization token ONLY for verified Vercel Blob domains
    """
    validated_info = get_validated_safe_storage_ip(url)
    if not validated_info:
        logger.warning(f"Rejected unsafe or unauthorized evidence URL: {url}")
        return None

    hostname, path, pinned_ip = validated_info

    try:
        ctx = ssl.create_default_context()
        headers = {
            "User-Agent": "JanSakshi-EvidenceVerification/1.0",
            "Host": hostname,
        }

        # BLOB_READ_WRITE_TOKEN is strictly attached ONLY to verified Vercel Blob storage domains
        token = os.getenv("BLOB_READ_WRITE_TOKEN", "").strip()
        if token and (hostname == "blob.vercel-storage.com" or hostname.endswith(".blob.vercel-storage.com")):
            headers["Authorization"] = f"Bearer {token}"

        conn = PinnedHTTPSConnection(
            host=hostname,
            port=443,
            pinned_ip=pinned_ip,
            context=ctx,
            timeout=FETCH_READ_TIMEOUT
        )

        conn.request("GET", path, headers=headers)
        res = conn.getresponse()

        if res.status != 200:
            logger.warning(f"Remote evidence request returned HTTP {res.status}")
            conn.close()
            return None

        content_length = res.getheader("Content-Length")
        if content_length:
            try:
                if int(content_length) > MAX_IMAGE_DOWNLOAD_BYTES:
                    logger.warning(f"Remote evidence Content-Length ({content_length}) exceeds 10 MB limit")
                    conn.close()
                    return None
            except ValueError:
                pass

        downloaded = bytearray()
        while True:
            chunk = res.read(65536)
            if not chunk:
                break
            downloaded.extend(chunk)
            if len(downloaded) > MAX_IMAGE_DOWNLOAD_BYTES:
                logger.warning(f"Remote evidence download exceeded {MAX_IMAGE_DOWNLOAD_BYTES} bytes; aborted.")
                conn.close()
                return None

        conn.close()
        return bytes(downloaded)

    except Exception as e:
        logger.warning(f"Failed fetching remote evidence: {e}")
        return None

def compute_hashes_for_image(
    image_path: str,
    hash_size: int = 8,
    cache: Optional[Dict[str, Tuple[Optional[int], Optional[int]]]] = None
) -> Tuple[Optional[int], Optional[int]]:
    """
    Computes both dHash and aHash in a single image load/decode operation.
    Eliminates redundant downloads and decodes.
    Optionally stores and reads from a per-evaluation cache dictionary.
    Returns (dhash, ahash).
    """
    if not image_path:
        return None, None

    if cache is not None and image_path in cache:
        return cache[image_path]

    try:
        raw_bytes: Optional[bytes] = None
        if image_path.startswith("https://"):
            raw_bytes = _fetch_safe_remote_bytes(image_path)
            if not raw_bytes:
                if cache is not None:
                    cache[image_path] = (None, None)
                return None, None
            img = Image.open(io.BytesIO(raw_bytes))
        elif os.path.exists(image_path):
            img = Image.open(image_path)
        else:
            if cache is not None:
                cache[image_path] = (None, None)
            return None, None

        with img:
            # Dimension safety checks
            if img.width > 10000 or img.height > 10000 or (img.width * img.height) > Image.MAX_IMAGE_PIXELS:
                logger.warning(f"Image dimensions ({img.width}x{img.height}) exceed safety limits")
                if cache is not None:
                    cache[image_path] = (None, None)
                return None, None

            # 1. dHash (Difference Hash): Grayscale resized to (hash_size + 1, hash_size)
            resized_d = img.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.BILINEAR)
            pixels_d = list(resized_d.get_flattened_data() if hasattr(resized_d, "get_flattened_data") else resized_d.getdata())
            difference = []
            for row in range(hash_size):
                row_start = row * (hash_size + 1)
                for col in range(hash_size):
                    difference.append(pixels_d[row_start + col] > pixels_d[row_start + col + 1])

            dhash_val = 0
            for bit in difference:
                dhash_val = (dhash_val << 1) | (1 if bit else 0)

            # 2. aHash (Average Hash): Grayscale resized to (hash_size, hash_size)
            resized_a = img.convert("L").resize((hash_size, hash_size), Image.Resampling.BILINEAR)
            pixels_a = list(resized_a.get_flattened_data() if hasattr(resized_a, "get_flattened_data") else resized_a.getdata())
            avg = sum(pixels_a) / len(pixels_a) if pixels_a else 0

            ahash_val = 0
            for pixel in pixels_a:
                ahash_val = (ahash_val << 1) | (1 if pixel > avg else 0)

            result = (dhash_val, ahash_val)
            if cache is not None:
                cache[image_path] = result
            return result

    except Exception as e:
        logger.warning(f"Failed computing hashes for image: {e}")
        if cache is not None:
            cache[image_path] = (None, None)
        return None, None

def compute_dhash(image_path: str, hash_size: int = 8) -> Optional[int]:
    """Computes Difference Hash (dHash) for an image."""
    dhash, _ = compute_hashes_for_image(image_path, hash_size=hash_size)
    return dhash

def compute_ahash(image_path: str, hash_size: int = 8) -> Optional[int]:
    """Computes Average Hash (aHash) for an image."""
    _, ahash = compute_hashes_for_image(image_path, hash_size=hash_size)
    return ahash

def hamming_distance(hash1: int, hash2: int, bit_length: int = 64) -> int:
    """Computes number of differing bits between two integer hashes."""
    xor = hash1 ^ hash2
    return bin(xor).count('1')

def calculate_single_image_similarity(
    path1: str,
    path2: str,
    cache: Optional[Dict[str, Tuple[Optional[int], Optional[int]]]] = None
) -> Optional[float]:
    """
    Calculates perceptual similarity between two images on disk or remote storage in range [0.0, 1.0].
    Returns None if either image is missing or invalid.
    """
    if not path1 or not path2:
        return None

    # Exact same path / URL or identical reference
    if path1 == path2:
        return 1.0

    dhash1, ahash1 = compute_hashes_for_image(path1, cache=cache)
    dhash2, ahash2 = compute_hashes_for_image(path2, cache=cache)

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

def compare_evidence_lists(
    paths1: List[str],
    paths2: List[str],
    cache: Optional[Dict[str, Tuple[Optional[int], Optional[int]]]] = None
) -> Optional[float]:
    """
    Compares two lists of image paths and returns the maximum similarity among any pair.
    Shares a per-evaluation image hash cache to avoid redundant downloads or decodes.
    Returns None if either list has no valid images.
    """
    def _is_plausible(p: str) -> bool:
        if not p:
            return False
        if p.startswith("https://"):
            return True
        return os.path.exists(p)

    valid_paths1 = [p for p in paths1 if _is_plausible(p)]
    valid_paths2 = [p for p in paths2 if _is_plausible(p)]

    if not valid_paths1 or not valid_paths2:
        return None

    if cache is None:
        cache = {}

    max_sim: Optional[float] = None
    for p1 in valid_paths1:
        for p2 in valid_paths2:
            sim = calculate_single_image_similarity(p1, p2, cache=cache)
            if sim is not None:
                if max_sim is None or sim > max_sim:
                    max_sim = sim

    return max_sim
