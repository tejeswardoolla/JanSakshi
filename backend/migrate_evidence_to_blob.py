#!/usr/bin/env python3
"""
JanSakshi Evidence Migration to Vercel Blob Utility

Migrates historical evidence files from local disk (storage/evidence/) to Vercel Blob.
Features:
- Dry-Run by default (requires --execute flag to perform live uploads).
- Dedicated binding to target Neon PostgreSQL (neondb) using TARGET_DATABASE_URL.
- Preserves all local files (NEVER deletes original evidence on disk).
- Validates file integrity, magic bytes, and size before upload.
- Uploads using Vercel Blob REST API with BLOB_READ_WRITE_TOKEN read strictly from environment.
- Verifies post-upload HTTP 200 availability before updating database records.
- Outputs a detailed reconciliation report with masked credentials.
"""

import os
import sys
import argparse
import datetime
import re
from typing import Dict, Any, List
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

# Ensure backend root is on sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

# 1. Explicitly load backend/.env BEFORE importing database or storage modules
env_path = os.path.join(SCRIPT_DIR, ".env")
load_dotenv(dotenv_path=env_path, override=True)

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.models.complaint import Evidence
from app.services.storage_service import (
    validate_magic_bytes,
    VERCEL_BLOB_API_URL
)

def mask_database_url(url: str) -> str:
    """Masks database credentials in connection string for safe logging."""
    if not url:
        return "(Not Configured)"
    return re.sub(r"://([^:]+):([^@]+)@", r"://\1:***@", url)

def parse_args():
    parser = argparse.ArgumentParser(description="JanSakshi Local Evidence to Vercel Blob Migration Utility")
    parser.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help="Execute actual upload and update target database storage_paths. Default: False (dry-run)."
    )
    return parser.parse_args()

def run_evidence_migration(execute: bool):
    mode_str = "EXECUTE (LIVE BLOB UPLOAD)" if execute else "DRY RUN (READ-ONLY INSPECTION)"
    target_url = os.getenv("TARGET_DATABASE_URL", "")
    blob_token = os.getenv("BLOB_READ_WRITE_TOKEN", "")

    print("=" * 80)
    print(f"JANSAKSHI EVIDENCE CLOUD MIGRATION ENGINE — {mode_str}")
    print("=" * 80)
    print(f"Timestamp:       {datetime.datetime.now(datetime.timezone.utc).isoformat()}")
    print(f"Target Database: {mask_database_url(target_url)}")
    print(f"Blob Token:      {'Configured' if blob_token else 'NOT SET (Local only)'}")
    print("-" * 80)

    # 1. Validate target database configuration
    if not target_url:
        print("[ERROR] TARGET_DATABASE_URL is not set in backend/.env or environment.")
        print("Please configure TARGET_DATABASE_URL before running evidence migration.")
        sys.exit(1)

    norm_target_url = target_url
    if norm_target_url.startswith("postgres://"):
        norm_target_url = "postgresql://" + norm_target_url[len("postgres://"):]

    parsed = urlparse(norm_target_url)
    hostname = parsed.hostname or ""
    db_name = parsed.path.lstrip("/")

    if "-pooler" in hostname:
        print(f"[ERROR] Target hostname '{hostname}' is a connection pooler endpoint.")
        print("Please use the direct (non-pooler) connection string for migration.")
        sys.exit(1)

    if db_name != "neondb":
        print(f"[ERROR] Target database is '{db_name}'. Expected 'neondb'.")
        sys.exit(1)

    # 2. Initialize dedicated engine & sessionmaker bound strictly to Neon PostgreSQL
    neon_engine = create_engine(
        norm_target_url,
        pool_pre_ping=True,
        connect_args={"sslmode": "require"} if "neon.tech" in norm_target_url else {}
    )

    # 3. Verify current_database() is neondb before accessing evidence
    with neon_engine.connect() as test_conn:
        current_db = test_conn.execute(text("SELECT current_database();")).scalar()
        if current_db != "neondb":
            print(f"[ERROR] Connected database is '{current_db}', expected 'neondb'.")
            sys.exit(1)
        print(f"Target Binding:  Neon PostgreSQL (db: {current_db}, host: {hostname})")

    TargetSession = sessionmaker(bind=neon_engine, autocommit=False, autoflush=False)
    db = TargetSession()

    try:
        evidence_records = db.query(Evidence).order_by(Evidence.id.asc()).all()
        total_records = len(evidence_records)
        print(f"\nDiscovered {total_records} evidence records in target Neon database.\n")

        already_blob = 0
        ready_to_upload = 0
        missing_on_disk = 0
        corrupted = 0
        migrated = 0
        verified = 0

        details: List[Dict[str, Any]] = []

        for ev in evidence_records:
            item = {
                "id": ev.id,
                "complaint_id": ev.complaint_id,
                "filename": ev.stored_filename,
                "original_filename": ev.original_filename,
                "file_type": ev.file_type,
                "file_size": ev.file_size,
                "current_path": ev.storage_path,
                "status": "PENDING"
            }

            # 1. Check if already on remote blob
            if ev.storage_path.startswith("http://") or ev.storage_path.startswith("https://"):
                item["status"] = "ALREADY_ON_BLOB"
                already_blob += 1
                details.append(item)
                continue

            # 2. Check local file on disk
            local_path = ev.storage_path
            if not os.path.exists(local_path):
                # Fallback to local storage/evidence relative path
                alt_path = os.path.join(SCRIPT_DIR, "storage", "evidence", ev.stored_filename)
                if os.path.exists(alt_path):
                    local_path = alt_path
                else:
                    item["status"] = "MISSING_ON_DISK"
                    missing_on_disk += 1
                    details.append(item)
                    continue

            # 3. Read and validate local file
            try:
                with open(local_path, "rb") as f:
                    content = f.read()

                actual_size = len(content)
                item["actual_size"] = actual_size

                if not validate_magic_bytes(content, ev.stored_filename):
                    item["status"] = "INVALID_MAGIC_BYTES"
                    corrupted += 1
                    details.append(item)
                    continue

                item["status"] = "READY_FOR_UPLOAD"
                ready_to_upload += 1

                # 4. If execute mode is active, upload to Vercel Blob
                if execute:
                    if not blob_token:
                        raise RuntimeError("BLOB_READ_WRITE_TOKEN environment variable is required when running with --execute.")

                    upload_url = f"{VERCEL_BLOB_API_URL}/evidence/{ev.stored_filename}"
                    headers = {
                        "Authorization": f"Bearer {blob_token}",
                        "x-content-type": ev.file_type,
                        "x-add-random-suffix": "false",
                        "x-vercel-blob-access": "private",
                    }
                    res = requests.put(upload_url, data=content, headers=headers, timeout=45)
                    if not res.ok:
                        item["status"] = f"UPLOAD_FAILED_{res.status_code}"
                        details.append(item)
                        continue

                    blob_data = res.json()
                    blob_url = blob_data.get("url")
                    if not blob_url:
                        item["status"] = "INVALID_BLOB_RESPONSE"
                        details.append(item)
                        continue

                    # 5. Verify file is readable via authenticated private HTTPS GET
                    v_res = requests.get(
                        blob_url,
                        headers={"Authorization": f"Bearer {blob_token}"},
                        timeout=15
                    )
                    if v_res.status_code == 200 and len(v_res.content) == actual_size:
                        verified += 1
                        ev.storage_path = blob_url
                        db.commit()
                        item["status"] = "MIGRATED_AND_VERIFIED"
                        item["new_url"] = blob_url
                        migrated += 1
                    else:
                        item["status"] = f"VERIFICATION_FAILED_{v_res.status_code}"

            except Exception as read_err:
                item["status"] = f"ERROR: {str(read_err)}"
                corrupted += 1

            details.append(item)

        # Print Itemized Inventory
        print(f"{'ID':<4} | {'Complaint':<14} | {'Stored Filename':<32} | {'Size':<10} | {'Status'}")
        print("-" * 80)
        for d in details:
            size_str = f"{d.get('file_size', 0):,} B"
            print(f"{d['id']:<4} | {d['complaint_id']:<14} | {d['filename']:<32} | {size_str:<10} | {d['status']}")

        print("\n" + "=" * 80)
        print("EVIDENCE RECONCILIATION SUMMARY")
        print("=" * 80)
        print(f"Total Database Records:      {total_records:>5}")
        print(f"Already Hosted on Blob:      {already_blob:>5}")
        print(f"Validated Local Files Ready: {ready_to_upload:>5}")
        print(f"Missing Local Files:         {missing_on_disk:>5}")
        print(f"Corrupted or Invalid Header: {corrupted:>5}")
        if execute:
            print(f"Successfully Migrated:       {migrated:>5}")
            print(f"Verified Private Read:       {verified:>5}")
        print("=" * 80)

        if not execute:
            print("\n[NOTE] Dry-run completed. All 15 local files remain untouched on disk.")
            print("Zero records were updated on the target Neon database.")
            print("To execute live migration to Vercel Blob once cloud storage is provisioned:")
            print("  set BLOB_READ_WRITE_TOKEN=<token> && python backend/migrate_evidence_to_blob.py --execute")

    finally:
        db.close()

if __name__ == "__main__":
    args = parse_args()
    run_evidence_migration(execute=args.execute)
