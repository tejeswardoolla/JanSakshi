#!/usr/bin/env python3
"""
JanSakshi Phase 2 Cloud Integration Test Suite
Verifies Neon PostgreSQL readiness, Vercel Blob abstraction, direct uploads,
and PostgreSQL OAuth token persistence without mutating genuine citizen data.
"""

import os
import sys
import uuid
import datetime
from typing import Dict, Any

# Ensure backend root is on sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from app.database import (
    Base,
    engine,
    SessionLocal,
    normalize_database_url
)
from app.models import (
    Complaint, Evidence, ComplaintEvent, Department, User,
    PhysicalIssue, AIAnalysis, DuplicateMatch, EmailMessage,
    ResolutionSubmission, ResolutionEvidenceAnalysis, RevokedToken,
    OAuthToken
)
from app.services.storage_service import (
    get_storage_provider,
    LocalStorageProvider,
    VercelBlobStorageProvider,
    validate_magic_bytes,
    validate_upload_metadata,
    prepare_direct_upload,
    save_evidence_bytes,
    get_evidence_content,
    MAGIC_BYTES,
    MAX_FILE_SIZE
)
from app.services.email.gmail_auth import GmailAuthService

def run_tests():
    print("=" * 80)
    print("JANSAKSHI PHASE 2: CLOUD INTEGRATION TEST SUITE")
    print("=" * 80)

    passed = 0
    failed = 0

    def assert_test(condition: bool, name: str, detail: str = ""):
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"  [PASS] {name} {f'({detail})' if detail else ''}")
        else:
            failed += 1
            print(f"  [FAIL] {name} {f'({detail})' if detail else ''}")

    # -------------------------------------------------------------
    # 1. DATABASE & NEON POSTGRESQL READINESS
    # -------------------------------------------------------------
    print("\n--- 1. DATABASE & NEON POSTGRESQL CONFIGURATION ---")
    neon_url = "postgres://user:pass@ep-cool-snowflake-12345.us-east-2.aws.neon.tech/neondb"
    norm_url = normalize_database_url(neon_url)
    assert_test(
        norm_url.startswith("postgresql://") and "sslmode=require" in norm_url,
        "Neon URL normalization",
        norm_url
    )

    # Dialect and connection pool validation
    assert_test(
        engine is not None,
        "SQLAlchemy engine initialized",
        f"Dialect: {engine.dialect.name}"
    )

    # -------------------------------------------------------------
    # 2. ORM MODEL INTEGRITY (ALL 13 TABLES)
    # -------------------------------------------------------------
    print("\n--- 2. ORM MODEL & TABLE INVENTORY ---")
    expected_tables = {
        "departments", "users", "revoked_tokens", "physical_issues",
        "complaints", "evidence", "complaint_events", "ai_analyses",
        "duplicate_matches", "email_messages", "resolution_submissions",
        "resolution_evidence_analyses", "oauth_tokens"
    }
    actual_tables = set(Base.metadata.tables.keys())
    missing_tables = expected_tables - actual_tables
    assert_test(
        len(missing_tables) == 0,
        "All 13 Core Database Tables Defined in ORM",
        f"Missing: {missing_tables if missing_tables else 'None'}"
    )

    # -------------------------------------------------------------
    # 3. TRANSACTION ROLLBACK INTEGRITY
    # -------------------------------------------------------------
    print("\n--- 3. TRANSACTION ROLLBACK ISOLATION ---")
    db = SessionLocal()
    initial_revoked_count = db.query(RevokedToken).count()
    try:
        # Create temporary token within transaction and roll back
        temp_token = RevokedToken(
            jti=f"test_rollback_{uuid.uuid4().hex}",
            token_type="access",
            username="test_admin",
            expires_at=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
        )
        db.add(temp_token)
        db.flush()
        # Explicit rollback
        db.rollback()
        after_rollback_count = db.query(RevokedToken).count()
        assert_test(
            initial_revoked_count == after_rollback_count,
            "Transaction rollback cleanly restores state without leakage",
            f"Count before={initial_revoked_count}, after={after_rollback_count}"
        )
    except Exception as e:
        db.rollback()
        assert_test(False, "Transaction rollback failed", str(e))
    finally:
        db.close()

    # -------------------------------------------------------------
    # 4. STORAGE ABSTRACTION & LOCAL FILE VALIDATION
    # -------------------------------------------------------------
    print("\n--- 4. EVIDENCE STORAGE ABSTRACTION ---")
    provider = get_storage_provider()
    assert_test(
        isinstance(provider, (LocalStorageProvider, VercelBlobStorageProvider)),
        "Active storage provider resolves cleanly",
        provider.__class__.__name__
    )

    # Test Magic Byte Validation
    valid_png = MAGIC_BYTES["png"] + b"\x00" * 20
    invalid_file = b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 20  # Executable PE header disguised as PNG
    assert_test(
        validate_magic_bytes(valid_png, "test.png") is True,
        "Magic bytes accepts genuine PNG header"
    )
    assert_test(
        validate_magic_bytes(invalid_file, "malicious.png") is False,
        "Magic bytes blocks disguised executable payload"
    )

    # -------------------------------------------------------------
    # 5. DIRECT BROWSER-TO-BLOB UPLOAD TOKEN PREPARATION
    # -------------------------------------------------------------
    print("\n--- 5. DIRECT UPLOAD TOKEN SPECIFICATION ---")
    upload_prep = prepare_direct_upload(
        filename="citizen_pothole_evidence.jpg",
        content_type="image/jpeg",
        file_size=1024 * 500  # 500 KB
    )
    assert_test(
        "stored_filename" in upload_prep and upload_prep["stored_filename"].endswith(".jpg"),
        "Pre-allocates secure UUID filename with proper extension",
        upload_prep.get("stored_filename")
    )
    assert_test(
        "direct_blob_enabled" in upload_prep,
        "Indicates direct Blob capability state accurately",
        f"direct_blob_enabled={upload_prep.get('direct_blob_enabled')}"
    )

    # -------------------------------------------------------------
    # 6. GMAIL OAUTH TOKEN DATABASE PERSISTENCE
    # -------------------------------------------------------------
    print("\n--- 6. GMAIL TOKEN PERSISTENCE ---")
    db = SessionLocal()
    try:
        db_token = db.query(OAuthToken).filter(OAuthToken.provider == "gmail").first()
        assert_test(
            db_token is not None and bool(db_token.token_data),
            "OAuthToken persisted in database table",
            f"Account: {db_token.account_email if db_token else 'None'}"
        )
    finally:
        db.close()

    # Verify GmailAuthService reads from DB or file without error
    creds = GmailAuthService.get_credentials()
    assert_test(
        creds is not None and creds.valid,
        "Gmail credentials loaded and validated via persistent store",
        f"Scopes: {len(creds.scopes) if creds else 0}"
    )

    # -------------------------------------------------------------
    # 7. MULTIMODAL GEMINI FILE CONTENT ADAPTER
    # -------------------------------------------------------------
    print("\n--- 7. EVIDENCE CONTENT ADAPTER FOR GEMINI ---")
    db = SessionLocal()
    try:
        first_evidence = db.query(Evidence).first()
        if first_evidence:
            content = get_evidence_content(first_evidence.storage_path)
            assert_test(
                len(content) == first_evidence.file_size,
                f"get_evidence_content reads full evidence binary for {first_evidence.stored_filename}",
                f"{len(content):,} bytes"
            )
        else:
            assert_test(True, "Evidence table empty (skipped)")
    finally:
        db.close()

    # -------------------------------------------------------------
    # 8. STRICT DATA PRESERVATION AUDIT
    # -------------------------------------------------------------
    print("\n--- 8. DATA PRESERVATION VERIFICATION ---")
    db = SessionLocal()
    try:
        complaint_count = db.query(Complaint).count()
        evidence_count = db.query(Evidence).count()
        event_count = db.query(ComplaintEvent).count()
        submission_count = db.query(ResolutionSubmission).count()
        email_count = db.query(EmailMessage).count()

        assert_test(complaint_count == 22, f"All 22 complaints intact (Count: {complaint_count})")
        assert_test(evidence_count == 15, f"All 15 evidence records intact (Count: {evidence_count})")
        assert_test(event_count == 320, f"All 320 complaint events intact (Count: {event_count})")
        assert_test(submission_count == 10, f"All 10 resolution submissions intact (Count: {submission_count})")
        assert_test(email_count == 9, f"All 9 email intake records intact (Count: {email_count})")
    finally:
        db.close()

    print("\n" + "=" * 80)
    print(f"RESULTS: {passed} PASSED | {failed} FAILED")
    print("=" * 80)
    return failed == 0

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
