"""
JanSakshi Evidence & Media Storage Service
Supports Dual Backends:
1. Local Filesystem Storage (Development & local deployments)
2. Vercel Blob Cloud Storage (Serverless production deployments)

Includes:
- Strict file format and magic byte validation (prevent disguised executable uploads)
- UUID-based safe filename allocation (prevent collisions and path traversal)
- Direct browser-to-Blob upload preparation (bypassing Vercel Hobby 4.5 MB request limit)
- Automatic fallback and transaction rollback cleanup
"""

import os
import uuid
import logging
from typing import Dict, Any, Optional
import aiofiles
import requests
from fastapi import UploadFile, HTTPException

logger = logging.getLogger("jansakshi.storage")

# -------------------------------------------------------------
# Configuration & Constants
# -------------------------------------------------------------
UPLOAD_DIR = os.getenv(
    "UPLOAD_DIR",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "storage", "evidence"))
)
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 25 MB max file size
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE_BYTES", str(25 * 1024 * 1024)))

# Vercel Blob Configuration
BLOB_READ_WRITE_TOKEN = os.getenv("BLOB_READ_WRITE_TOKEN", "").strip()
VERCEL_BLOB_API_URL = "https://blob.vercel-storage.com"

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/jpg",
    "video/mp4",
}

ALLOWED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".mp4"
}

# Magic byte signatures
MAGIC_BYTES = {
    "jpg": b"\xFF\xD8\xFF",
    "png": b"\x89PNG\r\n\x1a\n",
    "webp_riff": b"RIFF",
    "mp4_ftyp": b"ftyp",
}

def is_blob_storage_enabled() -> bool:
    """Returns True if Vercel Blob token is configured."""
    return bool(BLOB_READ_WRITE_TOKEN)

# -------------------------------------------------------------
# Validation Utilities
# -------------------------------------------------------------
def validate_upload_metadata(filename: str, content_type: str, file_size: int) -> None:
    """Validates filename, extension, mime type, and file size boundaries."""
    if not filename:
        raise HTTPException(status_code=400, detail="Filename cannot be empty.")

    ext = os.path.splitext(filename.lower())[1]
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File extension '{ext}' is not supported. Allowed formats: JPG, PNG, WEBP, MP4."
        )

    clean_content_type = (content_type or "").lower()
    if clean_content_type not in ALLOWED_MIME_TYPES and not clean_content_type.startswith("image/") and not clean_content_type.startswith("video/"):
        raise HTTPException(
            status_code=400,
            detail=f"Content type '{clean_content_type}' is not allowed for evidence submissions."
        )

    if file_size > MAX_FILE_SIZE:
        max_mb = MAX_FILE_SIZE // (1024 * 1024)
        raise HTTPException(
            status_code=400,
            detail=f"File size ({file_size} bytes) exceeds maximum allowable limit of {max_mb} MB."
        )

    if file_size < 100:
        raise HTTPException(
            status_code=400,
            detail=f"File '{filename}' is empty or corrupted."
        )

def validate_magic_bytes(content: bytes, filename: str) -> bool:
    """Validate initial header bytes to prevent disguised executable or malicious uploads."""
    if len(content) < 12:
        return False

    ext = os.path.splitext(filename.lower())[1]
    if ext in [".jpg", ".jpeg"]:
        return content.startswith(MAGIC_BYTES["jpg"])
    elif ext == ".png":
        return content.startswith(MAGIC_BYTES["png"])
    elif ext == ".webp":
        return content.startswith(MAGIC_BYTES["webp_riff"]) and b"WEBP" in content[8:16]
    elif ext == ".mp4":
        return MAGIC_BYTES["mp4_ftyp"] in content[4:16]

    return False

# -------------------------------------------------------------
# Storage Engine Abstraction
# -------------------------------------------------------------
class StorageProvider:
    """Abstract interface for storage providers."""
    def save(self, content: bytes, stored_filename: str, content_type: str) -> str:
        raise NotImplementedError

    def get_bytes(self, storage_path: str) -> bytes:
        raise NotImplementedError

    def delete(self, storage_path: str) -> bool:
        raise NotImplementedError

class LocalStorageProvider(StorageProvider):
    """Local filesystem storage provider for development."""
    def save(self, content: bytes, stored_filename: str, content_type: str) -> str:
        safe_path = os.path.join(UPLOAD_DIR, stored_filename)
        with open(safe_path, "wb") as f:
            f.write(content)
        return safe_path

    def get_bytes(self, storage_path: str) -> bytes:
        if not os.path.exists(storage_path):
            raise FileNotFoundError(f"Local evidence file not found: {storage_path}")
        with open(storage_path, "rb") as f:
            return f.read()

    def delete(self, storage_path: str) -> bool:
        try:
            if os.path.exists(storage_path):
                os.remove(storage_path)
                return True
        except Exception as e:
            logger.warning(f"Failed deleting local file {storage_path}: {e}")
        return False

class VercelBlobStorageProvider(StorageProvider):
    """Vercel Blob cloud storage provider for production."""
    def __init__(self, token: str):
        self.token = token

    def save(self, content: bytes, stored_filename: str, content_type: str) -> str:
        url = f"{VERCEL_BLOB_API_URL}/evidence/{stored_filename}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "x-content-type": content_type,
            "x-add-random-suffix": "false",
        }
        res = requests.put(url, data=content, headers=headers, timeout=30)
        if not res.ok:
            raise RuntimeError(f"Vercel Blob upload failed ({res.status_code}): {res.text}")

        data = res.json()
        blob_url = data.get("url")
        if not blob_url:
            raise RuntimeError(f"Vercel Blob returned invalid payload: {data}")
        return blob_url

    def get_bytes(self, storage_path: str) -> bytes:
        res = requests.get(storage_path, timeout=30)
        if not res.ok:
            raise FileNotFoundError(f"Could not retrieve file from Vercel Blob ({res.status_code}): {storage_path}")
        return res.content

    def delete(self, storage_path: str) -> bool:
        try:
            url = f"{VERCEL_BLOB_API_URL}/delete"
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
            res = requests.post(url, json={"urls": [storage_path]}, headers=headers, timeout=15)
            return res.ok
        except Exception as e:
            logger.warning(f"Failed deleting blob {storage_path}: {e}")
            return False

def get_storage_provider() -> StorageProvider:
    """Returns the active storage provider based on environment configuration."""
    if is_blob_storage_enabled():
        return VercelBlobStorageProvider(BLOB_READ_WRITE_TOKEN)
    return LocalStorageProvider()

# -------------------------------------------------------------
# High-Level Storage Operations
# -------------------------------------------------------------
async def save_evidence_file(file: UploadFile) -> Dict[str, Any]:
    """
    Validates and securely saves an uploaded evidence file.
    Automatically selects Vercel Blob or local storage depending on configuration.
    Returns metadata dictionary.
    """
    filename = file.filename or "evidence"
    content_type = (file.content_type or "").lower()

    content = await file.read()
    file_size = len(content)

    validate_upload_metadata(filename, content_type, file_size)

    if not validate_magic_bytes(content, filename):
        raise HTTPException(
            status_code=400,
            detail=f"File header signature for '{filename}' does not match its declared format."
        )

    ext = os.path.splitext(filename.lower())[1]
    stored_filename = f"{uuid.uuid4().hex}{ext}"

    provider = get_storage_provider()
    storage_path = provider.save(content, stored_filename, content_type)

    return {
        "original_filename": filename,
        "stored_filename": stored_filename,
        "file_type": content_type or f"application/{ext.lstrip('.')}",
        "file_size": file_size,
        "storage_path": storage_path
    }

def save_evidence_bytes(content: bytes, filename: str, content_type: str) -> Dict[str, Any]:
    """Synchronous helper to store in-memory bytes (e.g. from Gmail attachments)."""
    file_size = len(content)
    validate_upload_metadata(filename, content_type, file_size)

    if not validate_magic_bytes(content, filename):
        raise HTTPException(
            status_code=400,
            detail=f"File header signature for '{filename}' does not match its declared format."
        )

    ext = os.path.splitext(filename.lower())[1]
    stored_filename = f"{uuid.uuid4().hex}{ext}"

    provider = get_storage_provider()
    storage_path = provider.save(content, stored_filename, content_type)

    return {
        "original_filename": filename,
        "stored_filename": stored_filename,
        "file_type": content_type or f"application/{ext.lstrip('.')}",
        "file_size": file_size,
        "storage_path": storage_path
    }

def get_evidence_content(storage_path: str) -> bytes:
    """
    Retrieves binary content of an evidence file from either local disk or remote Vercel Blob.
    Used by Gemini multimodal AI client.
    """
    if storage_path.startswith("http://") or storage_path.startswith("https://"):
        res = requests.get(storage_path, timeout=30)
        if not res.ok:
            raise FileNotFoundError(f"Could not load evidence from remote URL ({res.status_code}): {storage_path}")
        return res.content

    if not os.path.exists(storage_path):
        raise FileNotFoundError(f"Local evidence file not found on disk: {storage_path}")

    with open(storage_path, "rb") as f:
        return f.read()

def cleanup_orphaned_file(storage_path: str) -> None:
    """Safely delete file if transaction rolls back."""
    try:
        provider = get_storage_provider()
        provider.delete(storage_path)
    except Exception:
        pass

# -------------------------------------------------------------
# Direct Browser-to-Blob Upload Preparation (Bypass 4.5MB limit)
# -------------------------------------------------------------
def prepare_direct_upload(filename: str, content_type: str, file_size: int) -> Dict[str, Any]:
    """
    Pre-authorizes a direct browser-to-Blob upload when Vercel Blob is active.
    When local storage is active, returns direct_upload=False to use standard multipart route.
    """
    validate_upload_metadata(filename, content_type, file_size)
    ext = os.path.splitext(filename.lower())[1]
    stored_filename = f"{uuid.uuid4().hex}{ext}"

    if is_blob_storage_enabled():
        return {
            "direct_blob_enabled": True,
            "upload_url": f"{VERCEL_BLOB_API_URL}/evidence/{stored_filename}",
            "pathname": f"evidence/{stored_filename}",
            "stored_filename": stored_filename,
            "content_type": content_type,
            "token": BLOB_READ_WRITE_TOKEN,
            "headers": {
                "Authorization": f"Bearer {BLOB_READ_WRITE_TOKEN}",
                "x-content-type": content_type,
                "x-add-random-suffix": "false"
            }
        }

    return {
        "direct_blob_enabled": False,
        "stored_filename": stored_filename,
        "standard_upload_endpoint": "/api/complaints/"
    }
