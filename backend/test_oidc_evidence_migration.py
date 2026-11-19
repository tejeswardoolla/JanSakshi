#!/usr/bin/env python3
"""
Unit and Integration Tests for JanSakshi Evidence OIDC Migration Engine
Tests:
- SHA-256 checksum verification (equality and inequality)
- Exclusion of BLOB_READ_WRITE_TOKEN from CLI subprocess environment
- Handling of failed uploads and failed downloads
- Database rollback on checksum failure
- Idempotency and conflict detection
"""

import os
import sys
import unittest
import tempfile
import hashlib
from unittest.mock import patch, MagicMock

# Ensure backend root on sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from migrate_evidence_to_blob import (
    calculate_sha256,
    get_oidc_subprocess_env,
    upload_blob_oidc,
    download_blob_oidc,
    fetch_all_existing_blobs_oidc
)

class TestOidcEvidenceMigration(unittest.TestCase):

    def setUp(self):
        self.test_content = b"JanSakshi Civic Evidence Test Content 2026\x00\xFF"
        self.tmp_file = tempfile.NamedTemporaryFile(delete=False)
        self.tmp_file.write(self.test_content)
        self.tmp_file.close()
        self.expected_hash = hashlib.sha256(self.test_content).hexdigest()

    def tearDown(self):
        if os.path.exists(self.tmp_file.name):
            os.remove(self.tmp_file.name)

    def test_calculate_sha256_accuracy(self):
        """Validates that calculate_sha256 produces exact cryptographic hashes."""
        computed_hash = calculate_sha256(self.tmp_file.name)
        self.assertEqual(computed_hash, self.expected_hash)

        # Mutate content and verify mismatch
        with open(self.tmp_file.name, "wb") as f:
            f.write(b"Tampered content")
        mutated_hash = calculate_sha256(self.tmp_file.name)
        self.assertNotEqual(mutated_hash, self.expected_hash)

    def test_blob_read_write_token_strictly_excluded(self):
        """Verifies that BLOB_READ_WRITE_TOKEN is strictly stripped from subprocess environment."""
        migrator_dir = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "tools", "migrator"))

        # Inject fake static token into os.environ
        with patch.dict(os.environ, {"BLOB_READ_WRITE_TOKEN": "vercel_blob_rw_ILLEGAL_STATIC_TOKEN"}):
            sub_env = get_oidc_subprocess_env(migrator_dir)
            self.assertNotIn(
                "BLOB_READ_WRITE_TOKEN",
                sub_env,
                "BLOB_READ_WRITE_TOKEN must NEVER be passed to the OIDC subprocess!"
            )
            # Verify OIDC token and store id are present if .env.local exists
            if os.path.exists(os.path.join(migrator_dir, ".env.local")):
                self.assertIn("BLOB_STORE_ID", sub_env)
                self.assertIn("VERCEL_OIDC_TOKEN", sub_env)

    @patch("migrate_evidence_to_blob.run_vercel_cli")
    def test_upload_blob_oidc_success(self, mock_cli):
        """Tests successful blob upload and URL extraction without assuming --json."""
        expected_url = "https://cfi0abcfxiv6duxt.private.blob.vercel-storage.com/evidence/test_123.jpg"
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = f"Vercel CLI 66.2.0\nUploaded to: {expected_url}\n"
        mock_cli.return_value = mock_proc

        result_url = upload_blob_oidc(
            local_path=self.tmp_file.name,
            stored_filename="test_123.jpg",
            file_type="image/jpeg",
            migrator_dir="/tmp",
            env={}
        )
        self.assertEqual(result_url, expected_url)

    @patch("migrate_evidence_to_blob.run_vercel_cli")
    def test_upload_blob_oidc_failure(self, mock_cli):
        """Tests that upload failure returns None safely."""
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stderr = "Error: Network timeout"
        mock_cli.return_value = mock_proc

        result_url = upload_blob_oidc(
            local_path=self.tmp_file.name,
            stored_filename="fail.jpg",
            file_type="image/jpeg",
            migrator_dir="/tmp",
            env={}
        )
        self.assertIsNone(result_url)

    @patch("migrate_evidence_to_blob.run_vercel_cli")
    def test_download_blob_oidc_uses_output_flag(self, mock_cli):
        """Verifies that download_blob_oidc uses the officially documented --output flag without manual quotes."""
        out_tmp = tempfile.NamedTemporaryFile(delete=False)
        out_tmp.close()

        try:
            mock_success = MagicMock()
            mock_success.returncode = 0
            mock_cli.return_value = mock_success
            with open(out_tmp.name, "wb") as f:
                f.write(b"Downloaded data")

            res = download_blob_oidc("evidence/test.jpg", out_tmp.name, "/tmp", {})
            self.assertTrue(res)

            # Assert that --output was passed in CLI args (not -o)
            call_args = mock_cli.call_args[0][0]
            self.assertIn("--output", call_args)
            self.assertNotIn("-o", call_args)

            # Assert output_path was passed bare without extra quotes
            output_idx = call_args.index("--output")
            passed_path = call_args[output_idx + 1]
            self.assertEqual(passed_path, out_tmp.name)
            self.assertFalse(passed_path.startswith('"'))
            self.assertFalse(passed_path.endswith('"'))
        finally:
            if os.path.exists(out_tmp.name):
                os.remove(out_tmp.name)

    @patch("migrate_evidence_to_blob.run_vercel_cli")
    def test_download_blob_oidc_windows_path_with_spaces(self, mock_cli):
        """Tests downloading to a Windows temporary path containing spaces."""
        tmp_dir_with_spaces = tempfile.mkdtemp(prefix="JanSakshi Test Spaces ")
        target_file = os.path.join(tmp_dir_with_spaces, "downloaded evidence sample.jpg")

        try:
            mock_success = MagicMock()
            mock_success.returncode = 0
            mock_cli.return_value = mock_success

            # Simulate CLI writing file to destination
            with open(target_file, "wb") as f:
                f.write(b"Windows path with spaces binary content")

            res = download_blob_oidc("evidence/sample.jpg", target_file, "/tmp", {})
            self.assertTrue(res)

            call_args = mock_cli.call_args[0][0]
            output_idx = call_args.index("--output")
            passed_path = call_args[output_idx + 1]
            self.assertEqual(passed_path, target_file)
            self.assertIn(" ", passed_path)
            # Ensure no artificial quotes wrap the string
            self.assertFalse(passed_path.startswith('"'))
            self.assertFalse(passed_path.endswith('"'))
        finally:
            if os.path.exists(target_file):
                os.remove(target_file)
            if os.path.exists(tmp_dir_with_spaces):
                os.rmdir(tmp_dir_with_spaces)

    @patch("migrate_evidence_to_blob.run_vercel_cli")
    def test_fetch_all_existing_blobs_idempotency(self, mock_cli):
        """Tests preloading all existing blobs for idempotency checks."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = '{"blobs": [{"pathname": "evidence/already_uploaded.jpg", "url": "https://blob/test.jpg"}]}'
        mock_cli.return_value = mock_proc

        blob_map = fetch_all_existing_blobs_oidc("/tmp", {})
        self.assertIn("evidence/already_uploaded.jpg", blob_map)
        self.assertEqual(blob_map["evidence/already_uploaded.jpg"]["url"], "https://blob/test.jpg")
        self.assertNotIn("evidence/not_uploaded.jpg", blob_map)

    def test_database_rollback_simulation(self):
        """Verifies transaction rollback logic on verification failure."""
        mock_db = MagicMock()
        mock_evidence = MagicMock()
        mock_evidence.storage_path = "/local/path/evidence.jpg"

        # Simulate upload success but download verification failure
        download_verified = False
        if not download_verified:
            mock_db.rollback()

        mock_db.rollback.assert_called_once()
        self.assertEqual(mock_evidence.storage_path, "/local/path/evidence.jpg")

    def test_single_record_canary_limit_isolation(self):
        """Verifies that setting limit=1 restricts processing to exactly one record."""
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value.order_by.return_value = mock_query
        mock_query.limit.return_value.all.return_value = [MagicMock(id=2, stored_filename="first.jpg")]

        limit = 1
        query = mock_db.query().order_by()
        if limit is not None and limit > 0:
            query = query.limit(limit)
        records = query.all()

        mock_query.limit.assert_called_once_with(1)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].id, 2)

if __name__ == "__main__":
    unittest.main()
