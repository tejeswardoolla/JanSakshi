import os
import uuid
import aiofiles
from fastapi import UploadFile, HTTPException

UPLOAD_DIR = os.getenv("UPLOAD_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "storage", "evidence")))
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 25 MB max file size
MAX_FILE_SIZE = 25 * 1024 * 1024

# Allowed MIME prefixes and explicit formats
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

async def save_evidence_file(file: UploadFile) -> dict:
    """
    Validates and securely saves an uploaded evidence file.
    Returns metadata dict.
    """
    filename = file.filename or "evidence"
    ext = os.path.splitext(filename.lower())[1]

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File extension '{ext}' is not supported. Allowed formats: JPG, PNG, WEBP, MP4."
        )

    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_MIME_TYPES and not content_type.startswith("image/") and not content_type.startswith("video/"):
        raise HTTPException(
            status_code=400,
            detail=f"File content type '{content_type}' is not allowed."
        )

    # Read content to check size and magic bytes
    content = await file.read()
    file_size = len(content)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File '{filename}' exceeds maximum allowable size of {MAX_FILE_SIZE // (1024 * 1024)} MB."
        )

    if file_size < 100:
        raise HTTPException(
            status_code=400,
            detail=f"File '{filename}' is empty or corrupted."
        )

    if not validate_magic_bytes(content, filename):
        raise HTTPException(
            status_code=400,
            detail=f"File header signature for '{filename}' does not match its declared format."
        )

    # Secure random filename to prevent collisions & path traversal
    stored_filename = f"{uuid.uuid4().hex}{ext}"
    safe_path = os.path.join(UPLOAD_DIR, stored_filename)

    async with aiofiles.open(safe_path, "wb") as out_file:
        await out_file.write(content)

    return {
        "original_filename": filename,
        "stored_filename": stored_filename,
        "file_type": content_type or f"application/{ext.lstrip('.')}",
        "file_size": file_size,
        "storage_path": safe_path
    }

def cleanup_orphaned_file(storage_path: str):
    """Safely delete file if transaction rolls back."""
    try:
        if os.path.exists(storage_path):
            os.remove(storage_path)
    except Exception:
        pass

