import os
import uuid
import re
import logging
from typing import List, Dict, Any, Optional

from app.core.config import APP_ENV
from app.services.storage_service import is_blob_storage_enabled, save_evidence_bytes

logger = logging.getLogger("jansakshi.email.attachments")

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_VIDEO_EXTENSIONS = {".mp4"}
ALLOWED_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_VIDEO_EXTENSIONS

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "video/mp4",
}

MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_VIDEO_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB

DANGEROUS_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".sh", ".bin", ".vbs", ".js", ".jar", ".py", ".php",
    ".pif", ".scr", ".com", ".msi", ".dll", ".apk"
}

def sanitize_filename(filename: str) -> str:
    """Removes path traversals and illegal characters."""
    base = os.path.basename(filename)
    clean = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', base)
    return clean[:128]

class AttachmentProcessor:
    """
    Validates, sanitizes, and persists email attachments into the evidence store.
    """

    @classmethod
    def process_attachment(
        cls,
        filename: str,
        content_bytes: bytes,
        mime_type: Optional[str] = None,
        target_dir: str = "storage/evidence"
    ) -> Optional[Dict[str, Any]]:
        """
        Validates and saves a single email attachment.
        Returns evidence metadata dict if valid, or None if invalid/rejected.
        """
        if not filename or not content_bytes:
            return None

        clean_name = sanitize_filename(filename)
        _, ext = os.path.splitext(clean_name.lower())

        # Check dangerous extensions
        if ext in DANGEROUS_EXTENSIONS:
            logger.warning(f"Rejected dangerous email attachment: {clean_name}")
            return None

        # Check allowed extensions
        if ext not in ALLOWED_EXTENSIONS:
            logger.info(f"Skipping unsupported attachment extension: {ext} for {clean_name}")
            return None

        # Determine normalized MIME type
        file_size = len(content_bytes)
        is_video = ext in ALLOWED_VIDEO_EXTENSIONS or (mime_type and "video" in mime_type)

        # Check size limits
        max_size = MAX_VIDEO_SIZE_BYTES if is_video else MAX_IMAGE_SIZE_BYTES
        if file_size > max_size:
            logger.warning(f"Attachment {clean_name} exceeds size limit ({file_size} > {max_size})")
            return None

        detected_mime = mime_type or ("video/mp4" if is_video else "image/jpeg")

        # -------------------------------------------------------------
        # Storage Backend Selection with Production Fail-Closed Safety
        # -------------------------------------------------------------
        is_prod = (APP_ENV == "production") or bool(os.getenv("VERCEL"))

        if is_prod:
            if not is_blob_storage_enabled():
                logger.error(
                    f"Production attachment processing failed for '{clean_name}': "
                    "BLOB_READ_WRITE_TOKEN is not configured. Ephemeral local disk fallback is blocked in production."
                )
                return None

            try:
                blob_meta = save_evidence_bytes(
                    content=content_bytes,
                    filename=clean_name,
                    content_type=detected_mime
                )
                logger.info(f"Saved email attachment to Vercel Blob: {clean_name} -> {blob_meta.get('storage_path')}")
                return blob_meta
            except Exception as e:
                logger.error(f"Production Vercel Blob upload failed for '{clean_name}': {e}. Fail-closed: refusing local fallback.")
                return None

        # Development / Testing Mode
        if is_blob_storage_enabled():
            try:
                blob_meta = save_evidence_bytes(
                    content=content_bytes,
                    filename=clean_name,
                    content_type=detected_mime
                )
                logger.info(f"Saved email attachment to Vercel Blob (dev): {clean_name} -> {blob_meta.get('storage_path')}")
                return blob_meta
            except Exception as e:
                logger.warning(f"Vercel Blob upload failed in development for '{clean_name}': {e}. Falling back to local storage.")

        # Fallback to local filesystem storage (development & testing only)
        os.makedirs(target_dir, exist_ok=True)
        stored_filename = f"{uuid.uuid4().hex}{ext}"
        storage_path = os.path.abspath(os.path.join(target_dir, stored_filename))

        try:
            with open(storage_path, "wb") as f:
                f.write(content_bytes)

            logger.info(f"Saved email attachment {clean_name} -> {storage_path} ({file_size} bytes)")
            return {
                "original_filename": clean_name,
                "stored_filename": stored_filename,
                "file_type": detected_mime,
                "file_size": file_size,
                "storage_path": storage_path,
            }
        except Exception as e:
            logger.error(f"Failed to write attachment to {storage_path}: {e}")
            return None

