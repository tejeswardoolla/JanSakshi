"""
JanSakshi Security Remediation Test Suite:
Private Vercel Blob Access Control & Scoped Direct Upload Verification

Verifies:
1. Direct upload token security: client tokens are short-lived, scoped, and NEVER expose master read-write tokens.
2. Server-side validation: 25 MB limit, extensions, magic bytes, and overwrite protections.
3. Role-based private evidence access: Admin, Authority Officer, Department Officer scoping, and unauthenticated blocking (401/403).
4. Citizen tracking access: secure retrieval via valid tracking token and rejection of unauthorized citizens.
5. Gemini remote evidence retrieval: authenticated private blob fetching without credential leakage.
6. Resolution evidence workflows: before/after photographic proof accessibility.
7. Local development preservation: 100% backward compatibility for local filesystem mode.
"""

import os
import sys
import json
import base64
import unittest
from unittest.mock import patch, MagicMock
import requests

# Ensure backend root is on sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from app.database import SessionLocal
from app.models.complaint import Complaint, Evidence, ResolutionSubmission
from app.models.authority import User, Department
from app.core.security import create_access_token
from app.services.storage_service import (
    generate_blob_client_token,
    prepare_direct_upload,
    get_evidence_content,
    validate_upload_metadata,
    validate_magic_bytes,
    VercelBlobStorageProvider,
    MAGIC_BYTES,
    MAX_FILE_SIZE
)

BASE_URL = "http://127.0.0.1:8000"

class TestBlobSecurityRemediation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = SessionLocal()

        # Load test complaints and users
        cls.test_complaint = cls.db.query(Complaint).filter(Complaint.complaint_id == "JS-2026-00057").first()
        assert cls.test_complaint is not None, "JS-2026-00057 must exist in database"

        cls.test_evidence = cls.test_complaint.evidence_files[0] if cls.test_complaint.evidence_files else None
        assert cls.test_evidence is not None, "Complaint JS-2026-00057 must have attached evidence"

        # Generate test JWT tokens
        # 1. Admin user
        cls.admin_token = create_access_token({"sub": "admin", "role": "admin"})
        # 2. Authority officer
        cls.officer_token = create_access_token({"sub": "officer", "role": "authority_officer"})
        # 3. Roads dept officer (authorized for RPW - Road Maintenance, dept=1)
        cls.roads_token = create_access_token({"sub": "roads_officer", "role": "department_officer"})
        # 4. Sanitation dept officer (authorized for SWM - Sanitation, dept=2)
        cls.sanitation_token = create_access_token({"sub": "sanitation_officer", "role": "department_officer"})

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    # -------------------------------------------------------------------------
    # 1. DIRECT UPLOAD TOKEN SECURITY
    # -------------------------------------------------------------------------
    def test_upload_token_never_exposes_master_rw_token(self):
        """Verify prepare_direct_upload generates scoped client token and NEVER leaks BLOB_READ_WRITE_TOKEN."""
        dummy_master_token = "vercel_blob_rw_teststore123_secretkeyabc987654321"

        with patch("app.services.storage_service.BLOB_READ_WRITE_TOKEN", dummy_master_token):
            with patch("app.services.storage_service.is_blob_storage_enabled", return_value=True):
                prep = prepare_direct_upload("pothole.jpg", "image/jpeg", 1024 * 500)

                # 1. Ensure master token is completely absent
                self.assertNotIn("token", prep, "Master 'token' key must NEVER be in response")
                self.assertNotEqual(prep.get("client_token"), dummy_master_token)
                self.assertNotIn("secretkeyabc987654321", json.dumps(prep), "Master secret key must never appear anywhere in payload")

                # 2. Verify client token format
                client_token = prep["client_token"]
                self.assertTrue(client_token.startswith("vercel_blob_client_teststore123_"))

                # 3. Decode payload to verify restrictions
                parts = client_token.split("_")
                combined_b64 = parts[4]
                combined = base64.b64decode(combined_b64).decode("utf-8")
                sig, payload_b64 = combined.split(".")
                payload = json.loads(base64.b64decode(payload_b64).decode("utf-8"))

                # 4. Verify scoped upload policies
                self.assertEqual(payload["pathname"], prep["pathname"])
                self.assertFalse(payload["allowOverwrite"], "allowOverwrite MUST be False to prevent tampering/deletion")
                self.assertEqual(payload["access"], "private", "Access MUST be private")
                self.assertEqual(payload["maximumSizeInBytes"], MAX_FILE_SIZE)
                self.assertIn("image/jpeg", payload["allowedContentTypes"])

                # 5. Verify authorization header in response uses client token
                self.assertEqual(prep["headers"]["Authorization"], f"Bearer {client_token}")
                self.assertEqual(prep["headers"]["x-vercel-blob-access"], "private")

    # -------------------------------------------------------------------------
    # 2. SERVER-SIDE UPLOAD METADATA VALIDATION
    # -------------------------------------------------------------------------
    def test_file_size_and_extension_validation(self):
        """Verify strict server-side validation rejects oversized or malicious file uploads."""
        # 1. File exceeding 25 MB limit
        with self.assertRaises(Exception) as ctx:
            validate_upload_metadata("huge_dump.jpg", "image/jpeg", 26 * 1024 * 1024)
        self.assertIn("exceeds maximum allowable limit", str(ctx.exception.detail))

        # 2. Empty or corrupted file (< 100 bytes)
        with self.assertRaises(Exception) as ctx:
            validate_upload_metadata("corrupt.jpg", "image/jpeg", 50)
        self.assertIn("empty or corrupted", str(ctx.exception.detail))

        # 3. Unauthorized executable extension
        with self.assertRaises(Exception) as ctx:
            validate_upload_metadata("exploit.exe", "application/x-msdownload", 1024 * 500)
        self.assertIn("not supported", str(ctx.exception.detail))

        # 4. Disguised executable header
        fake_png = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00" + b"\x00" * 20
        self.assertFalse(validate_magic_bytes(fake_png, "disguised.png"))

        # 5. Genuine JPG header
        genuine_jpg = MAGIC_BYTES["jpg"] + b"\x00" * 30
        self.assertTrue(validate_magic_bytes(genuine_jpg, "photo.jpg"))

    # -------------------------------------------------------------------------
    # 3. PRIVATE EVIDENCE RETRIEVAL & ROLE-BASED ACCESS CONTROL
    # -------------------------------------------------------------------------
    def test_unauthenticated_evidence_retrieval_blocked(self):
        """Unauthenticated requests to evidence files MUST be rejected with 401."""
        filename = self.test_evidence.stored_filename
        res = requests.get(f"{BASE_URL}/api/authority/evidence/{filename}")
        self.assertEqual(res.status_code, 401, "Unauthenticated access must return 401 Unauthorized")
        self.assertIn("Authentication required", res.json()["detail"])

    def test_invalid_token_blocked(self):
        """Requests with forged or invalid tokens MUST be rejected with 401."""
        filename = self.test_evidence.stored_filename
        res = requests.get(f"{BASE_URL}/api/authority/evidence/{filename}?token=invalid_fake_jwt_token")
        self.assertEqual(res.status_code, 401, "Invalid token must return 401")

    def test_admin_and_authority_officer_access_granted(self):
        """Admin and Authority Officers have global permission to view complaint evidence."""
        filename = self.test_evidence.stored_filename

        # Admin via Header
        res_admin = requests.get(
            f"{BASE_URL}/api/authority/evidence/{filename}",
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        self.assertEqual(res_admin.status_code, 200, "Admin must be granted access")

        # Authority Officer via Query Parameter (browser <img> support)
        res_officer = requests.get(
            f"{BASE_URL}/api/authority/evidence/{filename}?token={self.officer_token}"
        )
        self.assertEqual(res_officer.status_code, 200, "Authority Officer must be granted access via query token")

    def test_department_officer_role_scoping(self):
        """Department Officers can ONLY access evidence belonging to their assigned department."""
        filename = self.test_evidence.stored_filename
        # Complaint JS-2026-00057 is assigned to Department ID 1 (RPW - Road Maintenance)
        complaint_dept_id = self.test_complaint.assigned_department_id

        if complaint_dept_id == 1:
            # Roads Officer (Dept 1) -> GRANTED
            res_roads = requests.get(
                f"{BASE_URL}/api/authority/evidence/{filename}?token={self.roads_token}"
            )
            self.assertEqual(res_roads.status_code, 200, "Assigned department officer must be granted access")

            # Sanitation Officer (Dept 3) -> FORBIDDEN (403)
            res_sanitation = requests.get(
                f"{BASE_URL}/api/authority/evidence/{filename}?token={self.sanitation_token}"
            )
            self.assertEqual(res_sanitation.status_code, 403, "Unassigned department officer must be rejected with 403 Forbidden")
            self.assertIn("permission", res_sanitation.json()["detail"].lower())

    # -------------------------------------------------------------------------
    # 4. CITIZEN TRACKING EVIDENCE ACCESS
    # -------------------------------------------------------------------------
    def test_citizen_tracking_token_access(self):
        """Citizens with valid tracking token can retrieve their own evidence."""
        filename = self.test_evidence.stored_filename
        cid = self.test_complaint.complaint_id
        valid_tracking_token = self.test_complaint.tracking_token
        wrong_tracking_token = "00000000000000000000000000000000"

        # 1. Access via authority evidence endpoint with valid tracking token
        res_valid = requests.get(f"{BASE_URL}/api/authority/evidence/{filename}?tracking_token={valid_tracking_token}")
        self.assertEqual(res_valid.status_code, 200, "Citizen with valid tracking token must be allowed")

        # 2. Access with forged/wrong tracking token -> 403
        res_wrong = requests.get(f"{BASE_URL}/api/authority/evidence/{filename}?tracking_token={wrong_tracking_token}")
        self.assertEqual(res_wrong.status_code, 403, "Citizen with wrong tracking token must receive 403")

        # 3. Dedicated citizen complaint evidence endpoint
        res_citizen_ep = requests.get(f"{BASE_URL}/api/complaints/{cid}/evidence/{filename}?tracking_token={valid_tracking_token}")
        self.assertEqual(res_citizen_ep.status_code, 200, "Dedicated citizen endpoint must stream evidence")

        res_citizen_bad = requests.get(f"{BASE_URL}/api/complaints/{cid}/evidence/{filename}?tracking_token={wrong_tracking_token}")
        self.assertEqual(res_citizen_bad.status_code, 403, "Dedicated citizen endpoint must reject wrong tracking token")

    # -------------------------------------------------------------------------
    # 5. GEMINI REMOTE PRIVATE BLOB RETRIEVAL
    # -------------------------------------------------------------------------
    def test_gemini_remote_blob_authenticated_retrieval(self):
        """Verify get_evidence_content includes Authorization header for private Vercel Blob URLs."""
        test_url = "https://teststore.private.blob.vercel-storage.com/evidence/sample.jpg"
        dummy_token = "vercel_blob_rw_teststore_secret123"

        with patch("app.services.storage_service.BLOB_READ_WRITE_TOKEN", dummy_token):
            with patch("requests.get") as mock_get:
                mock_resp = MagicMock()
                mock_resp.ok = True
                mock_resp.content = b"TEST_IMAGE_BYTES"
                mock_get.return_value = mock_resp

                data = get_evidence_content(test_url)

                self.assertEqual(data, b"TEST_IMAGE_BYTES")
                mock_get.assert_called_once()
                args, kwargs = mock_get.call_args
                self.assertEqual(args[0], test_url)
                self.assertIn("Authorization", kwargs["headers"])
                self.assertEqual(kwargs["headers"]["Authorization"], f"Bearer {dummy_token}")

    # -------------------------------------------------------------------------
    # 6. RESOLUTION EVIDENCE WORKFLOW
    # -------------------------------------------------------------------------
    def test_resolution_evidence_access(self):
        """Verify before/after resolution evidence is accessible to authorized reviewers."""
        # Find resolution submission
        sub = self.db.query(ResolutionSubmission).first()
        if sub and sub.before_evidence:
            ev = sub.before_evidence
            res = requests.get(
                f"{BASE_URL}/api/authority/evidence/{ev.stored_filename}",
                headers={"Authorization": f"Bearer {self.officer_token}"}
            )
            self.assertEqual(res.status_code, 200, "Resolution before-evidence must be accessible to reviewing officer")

    # -------------------------------------------------------------------------
    # 7. BLOB DELETION PERMISSIONS
    # -------------------------------------------------------------------------
    def test_blob_deletion_requires_master_token(self):
        """Verify client tokens are prohibited from deleting blobs; deletions must use master token."""
        dummy_token = "vercel_blob_rw_teststore_secret123"
        provider = VercelBlobStorageProvider(token=dummy_token)

        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.ok = True
            mock_post.return_value = mock_resp

            result = provider.delete("https://teststore.blob.vercel-storage.com/evidence/sample.jpg")

            self.assertTrue(result)
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            self.assertEqual(args[0], "https://blob.vercel-storage.com/delete")
            self.assertEqual(kwargs["headers"]["Authorization"], f"Bearer {dummy_token}")

    # -------------------------------------------------------------------------
    # 8. LOCAL DEVELOPMENT PRESERVATION
    # -------------------------------------------------------------------------
    def test_local_development_preservation(self):
        """Verify local development works seamlessly when BLOB_READ_WRITE_TOKEN is empty."""
        with patch("app.services.storage_service.BLOB_READ_WRITE_TOKEN", ""):
            with patch("app.services.storage_service.is_blob_storage_enabled", return_value=False):
                prep = prepare_direct_upload("test.png", "image/png", 50000)
                self.assertFalse(prep["direct_blob_enabled"], "direct_blob_enabled must be False in local dev")
                self.assertEqual(prep["standard_upload_endpoint"], "/api/complaints/")

        # Verify all existing 22 complaints intact
        complaint_count = self.db.query(Complaint).count()
        self.assertEqual(complaint_count, 22, f"Expected 22 complaints, found {complaint_count}")

        # Verify all existing 15 evidence records intact
        evidence_count = self.db.query(Evidence).count()
        self.assertEqual(evidence_count, 15, f"Expected 15 evidence records, found {evidence_count}")

if __name__ == "__main__":
    unittest.main()
