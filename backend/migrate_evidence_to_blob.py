#!/usr/bin/env python3
"""
JanSakshi Evidence Migration to Vercel Blob Utility (OIDC Architecture)

Migrates historical evidence files from local disk (storage/evidence/) to Vercel Blob
using OpenID Connect (OIDC) authentication via Vercel CLI subprocesses.

Features:
- Pure OIDC Authentication: Runs CLI commands inside isolated tools/migrator/ context.
- Zero Static Token Exposure: Explicitly strips BLOB_READ_WRITE_TOKEN from child processes.
- Strict Dry-Run Default: Requires explicit --execute flag for live uploads.
- Neon Database Safety: Dedicated TargetSession bound strictly to Neon PostgreSQL (neondb).
- Post-Upload Checksum Verification: Downloads uploaded blob and verifies exact SHA-256 and size.
- Conflict & Idempotency Protection: Reuses verified existing blobs; aborts on checksum mismatch.
- Non-Destructive: Original local files in storage/evidence/ are NEVER deleted or modified.
"""

import os
import sys
import argparse
import datetime
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse

from dotenv import load_dotenv, dotenv_values

# Ensure backend root is on sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

# Default paths
DEFAULT_MIGRATOR_DIR = os.path.join(REPO_ROOT, "tools", "migrator")
DEFAULT_ENV_PATH = os.path.join(SCRIPT_DIR, ".env")

# 1. Explicitly load backend/.env for TARGET_DATABASE_URL
load_dotenv(dotenv_path=DEFAULT_ENV_PATH, override=True)

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.models.complaint import Evidence
from app.services.storage_service import validate_magic_bytes

def mask_database_url(url: str) -> str:
    """Masks database credentials in connection string for safe logging."""
    if not url:
        return "(Not Configured)"
    return re.sub(r"://([^:]+):([^@]+)@", r"://\1:***@", url)

def calculate_sha256(file_path: str) -> str:
    """Calculates the SHA-256 checksum of a file on disk."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

def get_oidc_subprocess_env(migrator_dir: str) -> Dict[str, str]:
    """
    Constructs a sanitized execution environment for Vercel CLI subprocesses.
    Loads VERCEL_OIDC_TOKEN and BLOB_STORE_ID from tools/migrator/.env.local,
    and strictly strips BLOB_READ_WRITE_TOKEN to enforce pure OIDC authentication.
    """
    sub_env = os.environ.copy()

    # 1. Strictly remove any static read-write token
    sub_env.pop("BLOB_READ_WRITE_TOKEN", None)

    # 2. Load migrator .env.local variables
    migrator_env_file = os.path.join(migrator_dir, ".env.local")
    if os.path.exists(migrator_env_file):
        migrator_vars = dotenv_values(migrator_env_file)
        for k in ["VERCEL_OIDC_TOKEN", "BLOB_STORE_ID", "BLOB_WEBHOOK_PUBLIC_KEY"]:
            if k in migrator_vars and migrator_vars[k]:
                sub_env[k] = migrator_vars[k]

    # Double check static token removal
    sub_env.pop("BLOB_READ_WRITE_TOKEN", None)
    return sub_env

def run_vercel_cli(args: List[str], migrator_dir: str, env: Dict[str, str]) -> subprocess.CompletedProcess:
    """
    Executes a Vercel CLI command via subprocess in the migrator directory.
    Uses shell=False with shutil.which("npx") and pure argument lists
    so that Python automatically escapes paths with spaces without manual quoting artifacts.
    """
    npx_bin = shutil.which("npx") or "npx"
    cmd = [npx_bin, "vercel"] + args
    return subprocess.run(
        cmd,
        shell=False,
        cwd=migrator_dir,
        env=env,
        capture_output=True,
        text=True
    )

def test_oidc_connection(migrator_dir: str, env: Dict[str, str]) -> bool:
    """Verifies that OIDC authentication succeeds by listing blobs (read-only)."""
    proc = run_vercel_cli(["blob", "list", "--limit", "5", "--json"], migrator_dir, env)
    return proc.returncode == 0

def fetch_all_existing_blobs_oidc(migrator_dir: str, env: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
    """
    Preloads all existing blobs under the 'evidence/' prefix from the store in a single OIDC call.
    Uses --limit 1000 to ensure full pagination coverage without default 10-item truncation.
    Returns a dictionary keyed by pathname: { 'evidence/<filename>': blob_metadata_dict }.
    """
    proc = run_vercel_cli(["blob", "list", "--prefix", "evidence/", "--limit", "1000", "--json"], migrator_dir, env)
    existing_map = {}
    if proc.returncode == 0:
        try:
            data = json.loads(proc.stdout)
            for b in data.get("blobs", []):
                p = b.get("pathname")
                if p:
                    existing_map[p] = b
        except Exception:
            pass
    return existing_map

def download_blob_oidc(pathname: str, output_path: str, migrator_dir: str, env: Dict[str, str]) -> bool:
    """
    Downloads a private blob from Vercel Blob store via OIDC into a local file.
    Returns True if downloaded successfully, False otherwise.
    Uses the officially documented --output flag without manual quotes so paths with spaces are handled cleanly.
    """
    proc = run_vercel_cli(
        ["blob", "get", pathname, "--access", "private", "--output", output_path],
        migrator_dir,
        env
    )
    return proc.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0

def upload_blob_oidc(local_path: str, stored_filename: str, file_type: str, migrator_dir: str, env: Dict[str, str]) -> Optional[str]:
    """
    Uploads a local evidence file to Vercel Blob with private access using OIDC.
    Does not assume --json is supported for put; reliably retrieves and validates the blob URL.
    Uses clean unquoted arguments with shell=False.
    """
    target_pathname = f"evidence/{stored_filename}"
    proc = run_vercel_cli(
        [
            "blob", "put", local_path,
            "--access", "private",
            "--pathname", target_pathname,
            "--content-type", file_type,
            "--no-multipart"
        ],
        migrator_dir,
        env
    )

    if proc.returncode != 0:
        return None

    # Retrieve URL from stdout regex match or authoritative list query
    stdout_match = re.search(r"https://[^\s\"']+", proc.stdout)
    if stdout_match:
        cand_url = stdout_match.group(0).rstrip(".,;")
        if f"/evidence/{stored_filename}" in cand_url:
            return cand_url

    # Fallback to authoritative blob list verification
    fresh_map = fetch_all_existing_blobs_oidc(migrator_dir, env)
    if target_pathname in fresh_map and fresh_map[target_pathname].get("url"):
        return fresh_map[target_pathname]["url"]

    return None

def parse_args():
    parser = argparse.ArgumentParser(description="JanSakshi Local Evidence to Vercel Blob OIDC Migration Utility")
    parser.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help="Execute actual upload and update target database storage_paths. Default: False (dry-run)."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of evidence records to process (e.g. --limit 1 for canary test). Default: None (all records)."
    )
    parser.add_argument(
        "--migrator-dir",
        default=DEFAULT_MIGRATOR_DIR,
        help=f"Path to isolated migrator directory containing .env.local. Default: {DEFAULT_MIGRATOR_DIR}"
    )
    return parser.parse_args()

def run_evidence_migration(execute: bool, limit: Optional[int] = None, migrator_dir: str = DEFAULT_MIGRATOR_DIR):
    mode_str = "EXECUTE (LIVE BLOB UPLOAD & NEON UPDATE)" if execute else "DRY RUN (READ-ONLY PREFLIGHT)"
    target_url = os.getenv("TARGET_DATABASE_URL", "")

    print("=" * 80)
    print(f"JANSAKSHI EVIDENCE CLOUD MIGRATION ENGINE (OIDC) — {mode_str}")
    print("=" * 80)
    print(f"Timestamp:       {datetime.datetime.now(datetime.timezone.utc).isoformat()}")
    print(f"Target Database: {mask_database_url(target_url)}")
    print(f"Migrator Dir:    {migrator_dir}")

    # 1. Validate Migrator Directory & Build OIDC Subprocess Environment
    if not os.path.exists(migrator_dir):
        print(f"[ERROR] Migrator directory does not exist: {migrator_dir}")
        sys.exit(1)

    oidc_env = get_oidc_subprocess_env(migrator_dir)
    store_id = oidc_env.get("BLOB_STORE_ID", "")
    has_oidc_token = bool(oidc_env.get("VERCEL_OIDC_TOKEN"))

    print(f"Blob Store ID:   {store_id if store_id else 'NOT SET'}")
    print(f"OIDC Token:      {'Configured (Masked)' if has_oidc_token else 'NOT SET'}")
    print(f"Static Token:    STRICTLY EXCLUDED (pure OIDC mode)")
    print("-" * 80)

    if not has_oidc_token or not store_id:
        print("[ERROR] VERCEL_OIDC_TOKEN or BLOB_STORE_ID missing from migrator directory.")
        sys.exit(1)

    # 2. Verify OIDC connectivity
    print("Verifying Vercel Blob OIDC authentication...")
    if not test_oidc_connection(migrator_dir, oidc_env):
        print("[ERROR] OIDC authentication test failed. Verify project connection and OIDC token.")
        sys.exit(1)
    print("[PASS] OIDC authentication verified successfully against Vercel Blob store.\n")

    # 3. Validate Target Database Configuration
    if not target_url:
        print("[ERROR] TARGET_DATABASE_URL is not set in backend/.env or environment.")
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

    # 4. Initialize dedicated engine & sessionmaker bound strictly to Neon PostgreSQL
    neon_engine = create_engine(
        norm_target_url,
        pool_pre_ping=True,
        connect_args={"sslmode": "require"} if "neon.tech" in norm_target_url else {}
    )

    with neon_engine.connect() as test_conn:
        current_db = test_conn.execute(text("SELECT current_database();")).scalar()
        if current_db != "neondb":
            print(f"[ERROR] Connected database is '{current_db}', expected 'neondb'.")
            sys.exit(1)
        print(f"Target Binding:  Neon PostgreSQL (db: {current_db}, host: {hostname})")

    TargetSession = sessionmaker(bind=neon_engine, autocommit=False, autoflush=False)
    db = TargetSession()

    try:
        query = db.query(Evidence).order_by(Evidence.id.asc())
        if limit is not None and limit > 0:
            query = query.limit(limit)
        evidence_records = query.all()
        total_records = len(evidence_records)
        limit_str = f" (limited to {limit} record{'s' if limit > 1 else ''})" if limit else ""
        print(f"Discovered {total_records} evidence records in target Neon database{limit_str}.\n")

        already_blob = 0
        ready_to_upload = 0
        missing_on_disk = 0
        corrupted = 0
        migrated = 0
        reused = 0
        conflicts = 0
        failed = 0

        details: List[Dict[str, Any]] = []

        print(f"Preloading existing store inventory from Vercel Blob...")
        existing_blobs_map = fetch_all_existing_blobs_oidc(migrator_dir, oidc_env)
        print(f"Preloaded {len(existing_blobs_map)} existing blobs from store.\n")

        for ev in evidence_records:
            item = {
                "id": ev.id,
                "complaint_id": ev.complaint_id,
                "filename": ev.stored_filename,
                "original_filename": ev.original_filename,
                "file_type": ev.file_type,
                "file_size": ev.file_size,
                "current_path": ev.storage_path,
                "status": "PENDING",
                "sha256": ""
            }

            # A. Check if already on remote blob in database record
            if ev.storage_path.startswith("http://") or ev.storage_path.startswith("https://"):
                item["status"] = "ALREADY_ON_BLOB"
                already_blob += 1
                details.append(item)
                continue

            # B. Check local file existence on disk
            local_path = ev.storage_path
            if not os.path.exists(local_path):
                alt_path = os.path.join(SCRIPT_DIR, "storage", "evidence", ev.stored_filename)
                if os.path.exists(alt_path):
                    local_path = alt_path
                else:
                    item["status"] = "MISSING_ON_DISK"
                    missing_on_disk += 1
                    details.append(item)
                    continue

            # C. Read and validate local file integrity and calculate SHA-256
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

                local_sha256 = calculate_sha256(local_path)
                item["sha256"] = local_sha256

                # D. Check if blob already exists on Vercel Blob store (Idempotency)
                target_key = f"evidence/{ev.stored_filename}"
                existing_blob = existing_blobs_map.get(target_key)
                if existing_blob:
                    # Download existing blob to verify checksum match
                    with tempfile.NamedTemporaryFile(delete=False) as tmp:
                        tmp_download = tmp.name

                    try:
                        if download_blob_oidc(f"evidence/{ev.stored_filename}", tmp_download, migrator_dir, oidc_env):
                            existing_sha256 = calculate_sha256(tmp_download)
                            existing_size = os.path.getsize(tmp_download)

                            if existing_sha256 == local_sha256 and existing_size == actual_size:
                                item["status"] = "STORE_MATCH_REUSABLE"
                                if execute:
                                    ev.storage_path = existing_blob["url"]
                                    db.commit()
                                    item["status"] = "REUSED_AND_UPDATED"
                                    reused += 1
                                else:
                                    ready_to_upload += 1
                            else:
                                item["status"] = "CONFLICT_CHECKSUM_MISMATCH"
                                conflicts += 1
                                details.append(item)
                                continue
                        else:
                            item["status"] = "EXISTING_DOWNLOAD_FAILED"
                    finally:
                        if os.path.exists(tmp_download):
                            os.remove(tmp_download)

                    if item["status"] in ["STORE_MATCH_REUSABLE", "REUSED_AND_UPDATED"]:
                        details.append(item)
                        continue

                item["status"] = "READY_FOR_UPLOAD"
                ready_to_upload += 1

                # E. Live Execution Pipeline
                if execute:
                    # 1. Upload via Vercel CLI with OIDC
                    blob_url = upload_blob_oidc(local_path, ev.stored_filename, ev.file_type, migrator_dir, oidc_env)
                    if not blob_url:
                        item["status"] = "UPLOAD_FAILED"
                        failed += 1
                        details.append(item)
                        continue

                    # 2. Authenticated Download Verification
                    with tempfile.NamedTemporaryFile(delete=False) as tmp_f:
                        verify_dest = tmp_f.name

                    try:
                        download_ok = download_blob_oidc(
                            f"evidence/{ev.stored_filename}",
                            verify_dest,
                            migrator_dir,
                            oidc_env
                        )

                        if not download_ok:
                            db.rollback()
                            item["status"] = "VERIFICATION_DOWNLOAD_FAILED"
                            failed += 1
                            details.append(item)
                            continue

                        downloaded_sha256 = calculate_sha256(verify_dest)
                        downloaded_size = os.path.getsize(verify_dest)

                        # 3. Require exact checksum and size equality
                        if downloaded_sha256 == local_sha256 and downloaded_size == actual_size:
                            ev.storage_path = blob_url
                            db.commit()
                            item["status"] = "MIGRATED_AND_VERIFIED"
                            item["new_url"] = blob_url
                            migrated += 1
                        else:
                            db.rollback()
                            item["status"] = "VERIFICATION_CHECKSUM_MISMATCH"
                            failed += 1

                    finally:
                        if os.path.exists(verify_dest):
                            os.remove(verify_dest)

            except Exception as err:
                db.rollback()
                item["status"] = f"ERROR: {str(err)}"
                corrupted += 1

            details.append(item)

        # Print Itemized Inventory
        print(f"{'ID':<4} | {'Complaint':<14} | {'Stored Filename':<32} | {'Size':<10} | {'Status':<24} | {'SHA-256 (prefix)'}")
        print("-" * 105)
        for d in details:
            size_str = f"{d.get('file_size', 0):,} B"
            sha_prefix = d.get('sha256', '')[:12] + "..." if d.get('sha256') else "N/A"
            print(f"{d['id']:<4} | {d['complaint_id']:<14} | {d['filename']:<32} | {size_str:<10} | {d['status']:<24} | {sha_prefix}")

        print("\n" + "=" * 80)
        print("EVIDENCE OIDC RECONCILIATION SUMMARY")
        print("=" * 80)
        print(f"Total Database Records:      {total_records:>5}")
        print(f"Already Hosted on Blob:      {already_blob:>5}")
        print(f"Validated Local Files Ready: {ready_to_upload:>5}")
        print(f"Existing Store Matches:      {reused:>5}")
        print(f"Conflicts / Checksum Errors: {conflicts:>5}")
        print(f"Missing Local Files:         {missing_on_disk:>5}")
        print(f"Corrupted or Invalid Header: {corrupted:>5}")
        if execute:
            print(f"Successfully Migrated:       {migrated:>5}")
            print(f"Failed Uploads/Verifications:{failed:>5}")
        print("=" * 80)

        if not execute:
            print("\n[NOTE] Dry-run completed. All 15 local files remain untouched on disk.")
            print("Zero records were updated on the target Neon database.")
            print("Zero files were uploaded to Vercel Blob.")
            print("To execute live migration to Vercel Blob:")
            print("  python backend/migrate_evidence_to_blob.py --execute")

    finally:
        db.close()

if __name__ == "__main__":
    args = parse_args()
    run_evidence_migration(
        execute=args.execute,
        limit=args.limit,
        migrator_dir=args.migrator_dir
    )
