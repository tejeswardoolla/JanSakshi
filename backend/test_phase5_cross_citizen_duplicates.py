"""
JanSakshi Phase 5 Cross-Citizen Duplicate Detection & Security Regression Suite
Covers:
1. First complaint creates a provisional physical issue anchor.
2. Second complaint at same coordinates from different citizen creates duplicate candidate.
3. Same photograph increases visual similarity score.
4. Similar descriptions and categories contribute to matching.
5. Different physical locations are not incorrectly associated.
6. Different issues at nearby locations are not automatically merged.
7. Reprocessing same complaint does not create duplicate anchors or matches (idempotency).
8. Missing coordinates do not crash background processing.
9. Admin can approve or reject candidate.
10. Original complaints and evidence remain independently accessible.
11. Simulation of real-world scenario JS-2026-00058 and JS-2026-00059.
12. Security & SSRF Defense (localhost, metadata, private IPs, non-HTTPS, untrusted domains, URL userinfo, ports).
13. Download Size Cap (streaming enforcement of 10 MB limit).
14. Pillow Decompression Bomb & Oversized Dimension Safeguards.
15. Redundant Image Download & Hash Computation Elimination (Caching).
16. Category-Aware Earlier Unlinked Complaint Retrieval.
17. Review Lifecycle: Sibling Match Dismissal upon Approval.
18. True Concurrency: Concurrent Anchor Creation under Multi-Threaded Contention.
"""

import os
import sys
import unittest
import datetime
import io
import socket
from unittest.mock import patch, MagicMock
from concurrent.futures import ThreadPoolExecutor

# Ensure backend root is in python path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from PIL import Image

import asyncio
from app.core.config import utc_now
from app.database import Base
from app.models.complaint import Complaint, PhysicalIssue, Evidence, ComplaintEvent, DuplicateMatch
from app.models.authority import User
from app.services.duplicate_detection import DuplicateDetector
from app.services.duplicate_detection.image_similarity import (
    validate_safe_evidence_url,
    calculate_single_image_similarity,
    compare_evidence_lists,
    compute_hashes_for_image,
    _fetch_safe_remote_bytes,
)
from app.services.duplicate_detection.location_similarity import calculate_haversine_distance
from app.schemas import DuplicateReviewQueueItem, DuplicateMatchResponse, PhysicalIssueResponse
from app.routes.duplicates import (
    _format_match_response,
    get_complaint_duplicate_candidates,
    get_duplicate_review_queue,
)
from app.services.issue_id_service import (
    generate_issue_reference_id,
    acquire_postgres_issue_seq_lock,
    get_verified_database_dialect,
    is_issue_reference_id_collision,
)

# Shared in-memory database with StaticPool for cross-thread testing
from sqlalchemy.pool import StaticPool
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=test_engine))
Base.metadata.create_all(bind=test_engine)

class TestCrossCitizenDuplicateDetection(unittest.TestCase):
    def setUp(self):
        self.db = TestingSessionLocal()
        # Clean all tables before each test
        self.db.query(DuplicateMatch).delete()
        self.db.query(ComplaintEvent).delete()
        self.db.query(Evidence).delete()
        self.db.query(Complaint).delete()
        self.db.query(PhysicalIssue).delete()
        self.db.commit()

    def tearDown(self):
        self.db.close()
        TestingSessionLocal.remove()

    def _create_test_complaint(self, citizen_id, category, lat, lon, desc):
        import uuid
        c = Complaint(
            complaint_id=f"JS-2026-{uuid.uuid4().hex[:6].upper()}",
            citizen_name=f"Citizen {citizen_id}",
            citizen_email=f"{citizen_id}@example.com",
            category=category,
            description=desc,
            latitude=lat,
            longitude=lon,
            status="Received",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self.db.add(c)
        self.db.commit()
        return c

    def test_01_first_complaint_creates_provisional_anchor(self):
        """1. When a geolocated complaint is evaluated and no anchor exists, a provisional anchor is created."""
        c1 = Complaint(
            complaint_id="JS-2026-00101",
            category="Road Damage / Potholes",
            description="Deep pothole in middle of Main Road causing traffic slowdown",
            latitude=16.9936192,
            longitude=81.776287,
            citizen_name="Citizen One",
            citizen_email="citizen1@example.com",
            submission_channel="website",
            status="Received",
        )
        self.db.add(c1)
        self.db.commit()

        matches = DuplicateDetector.evaluate_complaint(c1.complaint_id, self.db)
        self.assertEqual(len(matches), 0, "First complaint should have 0 duplicate candidate matches")

        self.db.refresh(c1)
        self.assertIsNotNone(c1.issue_id, "Complaint 1 should now be linked to a provisional issue anchor")

        anchor = self.db.query(PhysicalIssue).filter(PhysicalIssue.issue_reference_id == c1.issue_id).first()
        self.assertIsNotNone(anchor, "Provisional PhysicalIssue record must exist in DB")
        self.assertEqual(anchor.category, "Road Damage / Potholes")
        self.assertIn("[Provisional Issue Anchor]", anchor.description)
        self.assertAlmostEqual(anchor.representative_latitude, 16.9936192, places=4)
        self.assertAlmostEqual(anchor.representative_longitude, 81.776287, places=4)

        event = self.db.query(ComplaintEvent).filter(
            ComplaintEvent.complaint_id == c1.complaint_id,
            ComplaintEvent.event_type == "provisional_issue_anchor_created"
        ).first()
        self.assertIsNotNone(event, "Provisional anchor audit event must be logged")

    def test_02_second_complaint_creates_duplicate_candidate(self):
        """2. Second complaint at same coords from different citizen creates a duplicate candidate with pending review."""
        c1 = Complaint(
            complaint_id="JS-2026-00102",
            category="Road Damage / Potholes",
            description="Huge pothole near church on Main Road",
            latitude=16.9936192,
            longitude=81.776287,
            citizen_name="Citizen One",
            citizen_email="citizen1@example.com",
            submission_channel="website",
            status="Received",
        )
        self.db.add(c1)
        self.db.commit()
        DuplicateDetector.evaluate_complaint(c1.complaint_id, self.db)
        self.db.refresh(c1)

        c2 = Complaint(
            complaint_id="JS-2026-00103",
            category="Road Damage / Potholes",
            description="Dangerous road crater on Main Road right by church",
            latitude=16.9936192,
            longitude=81.776287,
            citizen_name="Citizen Two",
            citizen_email="citizen2@example.com",
            submission_channel="email",
            status="Received",
        )
        self.db.add(c2)
        self.db.commit()

        matches = DuplicateDetector.evaluate_complaint(c2.complaint_id, self.db)
        self.assertEqual(len(matches), 1, "Second complaint must generate 1 candidate duplicate match")
        self.assertEqual(matches[0].candidate_physical_issue_id, c1.issue_id)
        self.assertEqual(matches[0].review_status, "pending")
        self.assertGreaterEqual(matches[0].similarity_score, 0.40)

        self.db.refresh(c2)
        self.assertIsNone(c2.issue_id, "Subsequent complaint must not be auto-associated before review")

    def test_03_photograph_increases_visual_similarity(self):
        """3. Photographic attachments are compared and identical photos result in 1.0 image similarity."""
        sim_same = calculate_single_image_similarity("https://blob.vercel-storage.com/pothole.jpg", "https://blob.vercel-storage.com/pothole.jpg")
        self.assertEqual(sim_same, 1.0, "Identical image path/URL must have 1.0 similarity")

        ev_list1 = ["https://blob.vercel-storage.com/pothole.jpg"]
        ev_list2 = ["https://blob.vercel-storage.com/pothole.jpg"]
        list_sim = compare_evidence_lists(ev_list1, ev_list2)
        self.assertEqual(list_sim, 1.0, "Evidence list with matching photo must yield 1.0 visual similarity")

    def test_04_similar_descriptions_and_categories_contribute(self):
        """4. Text and category similarities contribute positively to composite score."""
        from app.services.duplicate_detection.category_similarity import calculate_category_similarity
        from app.services.duplicate_detection.text_similarity import calculate_text_similarity
        from app.services.duplicate_detection.scoring import compute_composite_score

        cat_sim = calculate_category_similarity("Road Damage / Potholes", "Road Damage / Potholes")
        self.assertEqual(cat_sim, 1.0)

        text_sim = calculate_text_similarity(
            "Large dangerous crater in asphalt road",
            "Dangerous pothole and crater on asphalt road surface"
        )
        self.assertGreater(text_sim, 0.3)

        score_data = compute_composite_score(
            gps_score=1.0,
            distance_meters=0.0,
            text_score=text_sim,
            image_score=1.0,
            category_score=cat_sim,
        )
        self.assertGreaterEqual(score_data["similarity_score"], 0.80)
        self.assertEqual(score_data["confidence_level"], "high")

    def test_05_different_locations_not_associated(self):
        """5. Complaints far apart (>150m) are not associated as duplicate candidates."""
        c1 = Complaint(
            complaint_id="JS-2026-00104",
            category="Road Damage / Potholes",
            description="Pothole in Ward 1",
            latitude=16.9936192,
            longitude=81.776287,
            status="Received",
        )
        self.db.add(c1)
        self.db.commit()
        DuplicateDetector.evaluate_complaint(c1.complaint_id, self.db)

        c2 = Complaint(
            complaint_id="JS-2026-00105",
            category="Road Damage / Potholes",
            description="Pothole in Ward 12",
            latitude=17.0150000,
            longitude=81.7950000,
            status="Received",
        )
        self.db.add(c2)
        self.db.commit()

        dist = calculate_haversine_distance(c1.latitude, c1.longitude, c2.latitude, c2.longitude)
        self.assertGreater(dist, 1000.0)

        matches = DuplicateDetector.evaluate_complaint(c2.complaint_id, self.db)
        self.assertEqual(len(matches), 0, "Distant complaints must not match")
        self.db.refresh(c2)
        self.assertIsNotNone(c2.issue_id)
        self.assertNotEqual(c1.issue_id, c2.issue_id, "Distant complaints must have different anchors")

    def test_06_different_categories_at_same_location_not_merged(self):
        """6. Different issues at same location (e.g. streetlight vs pothole) are not falsely merged."""
        c1 = Complaint(
            complaint_id="JS-2026-00106",
            category="Road Damage / Potholes",
            description="Pothole on the road",
            latitude=16.9936192,
            longitude=81.776287,
            status="Received",
        )
        self.db.add(c1)
        self.db.commit()
        DuplicateDetector.evaluate_complaint(c1.complaint_id, self.db)

        c2 = Complaint(
            complaint_id="JS-2026-00107",
            category="Broken Streetlights",
            description="Light pole bulb is dead and dark at night",
            latitude=16.9936192,
            longitude=81.776287,
            status="Received",
        )
        self.db.add(c2)
        self.db.commit()

        matches = DuplicateDetector.evaluate_complaint(c2.complaint_id, self.db)
        self.assertEqual(len(matches), 0, "Incompatible categories must not create duplicate candidates")
        self.db.refresh(c2)
        self.assertIsNotNone(c2.issue_id)
        self.assertNotEqual(c1.issue_id, c2.issue_id, "Incompatible issues must have separate anchors")

    def test_07_idempotency_no_duplicate_anchors_or_matches_on_reprocess(self):
        """7. Reprocessing the same complaint does not create duplicate anchors or duplicate match records."""
        c1 = Complaint(
            complaint_id="JS-2026-00108",
            category="Road Damage / Potholes",
            description="Idempotency test pothole",
            latitude=16.9936192,
            longitude=81.776287,
            status="Received",
        )
        self.db.add(c1)
        self.db.commit()

        DuplicateDetector.evaluate_complaint(c1.complaint_id, self.db)
        self.db.refresh(c1)
        initial_anchor = c1.issue_id

        DuplicateDetector.evaluate_complaint(c1.complaint_id, self.db)
        self.db.refresh(c1)
        self.assertEqual(c1.issue_id, initial_anchor, "Anchor must remain identical")

        total_issues = self.db.query(PhysicalIssue).count()
        self.assertEqual(total_issues, 1, "Only 1 PhysicalIssue anchor should exist")

    def test_08_missing_coordinates_do_not_crash(self):
        """8. Complaint with missing coordinates does not crash duplicate detection."""
        c_unlocated = Complaint(
            complaint_id="JS-2026-00109",
            category="Road Damage / Potholes",
            description="Pothole somewhere on highway without GPS",
            latitude=None,
            longitude=None,
            status="Awaiting Location",
        )
        self.db.add(c_unlocated)
        self.db.commit()

        matches = DuplicateDetector.evaluate_complaint(c_unlocated.complaint_id, self.db)
        self.assertEqual(matches, [], "Unlocated complaint should return empty list gracefully")

        event = self.db.query(ComplaintEvent).filter(
            ComplaintEvent.complaint_id == c_unlocated.complaint_id,
            ComplaintEvent.event_type == "duplicate_evaluation_unlocated"
        ).first()
        self.assertIsNotNone(event, "Unlocated audit event should be recorded")

    def test_09_admin_can_approve_or_reject_candidate(self):
        """9. Admin can approve or reject candidate matches."""
        c1 = Complaint(
            complaint_id="JS-2026-00110",
            category="Drainage Overflow",
            description="Drain overflow on Cross Road",
            latitude=16.9936192,
            longitude=81.776287,
            status="Received",
        )
        c2 = Complaint(
            complaint_id="JS-2026-00111",
            category="Drainage Overflow",
            description="Sewage overflowing on Cross Road",
            latitude=16.9936192,
            longitude=81.776287,
            status="Received",
        )
        self.db.add_all([c1, c2])
        self.db.commit()

        DuplicateDetector.evaluate_complaint(c1.complaint_id, self.db)
        matches = DuplicateDetector.evaluate_complaint(c2.complaint_id, self.db)
        self.assertEqual(len(matches), 1)
        match_id = matches[0].id

        res = DuplicateDetector.approve_match(self.db, match_id=match_id, reviewer_id="Admin Officer")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["review_status"], "approved")

        self.db.refresh(c2)
        self.assertEqual(c2.issue_id, c1.issue_id, "Approved complaint must be associated with anchor")

        c3 = Complaint(
            complaint_id="JS-2026-00112",
            category="Drainage Overflow",
            description="Minor leak near curb",
            latitude=16.9936192,
            longitude=81.776287,
            status="Received",
        )
        self.db.add(c3)
        self.db.commit()
        matches_c3 = DuplicateDetector.evaluate_complaint(c3.complaint_id, self.db)
        self.assertEqual(len(matches_c3), 1)

        rej_res = DuplicateDetector.reject_match(self.db, match_id=matches_c3[0].id, reviewer_id="Admin Officer")
        self.assertEqual(rej_res["status"], "success")
        self.assertEqual(rej_res["review_status"], "rejected")

    def test_10_original_complaints_and_evidence_remain_independent(self):
        """10. Association does not overwrite original complaints' descriptions, metadata, or evidence."""
        c1 = Complaint(
            complaint_id="JS-2026-00113",
            category="Road Damage / Potholes",
            description="Original citizen description A",
            latitude=16.9936192,
            longitude=81.776287,
            citizen_name="Citizen Alpha",
            citizen_email="alpha@example.com",
            status="Received",
        )
        ev1 = Evidence(
            complaint_id="JS-2026-00113",
            original_filename="photo_a.jpg",
            stored_filename="stored_a.jpg",
            file_type="image/jpeg",
            file_size=1024,
            storage_path="/path/to/stored_a.jpg"
        )
        c2 = Complaint(
            complaint_id="JS-2026-00114",
            category="Road Damage / Potholes",
            description="Original citizen description B",
            latitude=16.9936192,
            longitude=81.776287,
            citizen_name="Citizen Beta",
            citizen_email="beta@example.com",
            status="Received",
        )
        ev2 = Evidence(
            complaint_id="JS-2026-00114",
            original_filename="photo_b.jpg",
            stored_filename="stored_b.jpg",
            file_type="image/jpeg",
            file_size=2048,
            storage_path="/path/to/stored_b.jpg"
        )
        self.db.add_all([c1, ev1, c2, ev2])
        self.db.commit()

        DuplicateDetector.evaluate_complaint(c1.complaint_id, self.db)
        matches = DuplicateDetector.evaluate_complaint(c2.complaint_id, self.db)
        DuplicateDetector.approve_match(self.db, match_id=matches[0].id)

        self.db.refresh(c1)
        self.db.refresh(c2)
        self.assertEqual(c1.citizen_email, "alpha@example.com")
        self.assertEqual(c2.citizen_email, "beta@example.com")
        self.assertEqual(c1.description, "Original citizen description A")
        self.assertEqual(c2.description, "Original citizen description B")
        self.assertEqual(len(c1.evidence_files), 1)
        self.assertEqual(len(c2.evidence_files), 1)

    def test_11_simulation_js_2026_00058_and_js_2026_00059(self):
        """
        11. Simulation of real-world scenario JS-2026-00058 and JS-2026-00059:
        Both submitted at (16.9936192, 81.776287) with Road Damage, different citizens,
        same photograph URL. Guarantees 00059 generates a duplicate candidate against 00058.
        """
        c58 = Complaint(
            complaint_id="JS-2026-00058",
            category="Road Damage / Potholes",
            description="Severe road crater causing vehicle damage on Main Bazaar Road",
            latitude=16.9936192,
            longitude=81.776287,
            location_source="exif",
            citizen_name="Rajesh Kumar",
            citizen_email="rajesh.kumar@example.com",
            submission_channel="email",
            status="Received",
            created_at=datetime.datetime(2026, 11, 20, 10, 0, 0),
        )
        ev58 = Evidence(
            complaint_id="JS-2026-00058",
            original_filename="pothole_evidence.jpg",
            stored_filename="pothole_evidence_hash1.jpg",
            file_type="image/jpeg",
            file_size=245000,
            storage_path="https://blob.vercel-storage.com/evidence/pothole_shared.jpg"
        )
        self.db.add_all([c58, ev58])
        self.db.commit()

        matches_58 = DuplicateDetector.evaluate_complaint(c58.complaint_id, self.db)
        self.assertEqual(len(matches_58), 0, "58 is the first report, creates provisional anchor")
        self.db.refresh(c58)
        self.assertIsNotNone(c58.issue_id)
        anchor_id = c58.issue_id

        c59 = Complaint(
            complaint_id="JS-2026-00059",
            category="Road Damage / Potholes",
            description="Deep pothole in middle of road near market, dangerous for two-wheelers",
            latitude=16.9936192,
            longitude=81.776287,
            location_source="exif",
            citizen_name="Sita Lakshmi",
            citizen_email="sita.lakshmi@example.com",
            submission_channel="email",
            status="Received",
            created_at=datetime.datetime(2026, 11, 20, 10, 15, 0),
        )
        ev59 = Evidence(
            complaint_id="JS-2026-00059",
            original_filename="pothole_evidence.jpg",
            stored_filename="pothole_evidence_hash2.jpg",
            file_type="image/jpeg",
            file_size=245000,
            storage_path="https://blob.vercel-storage.com/evidence/pothole_shared.jpg"
        )
        self.db.add_all([c59, ev59])
        self.db.commit()

        matches_59 = DuplicateDetector.evaluate_complaint(c59.complaint_id, self.db)
        self.assertEqual(len(matches_59), 1, "59 MUST find 58's anchor as a duplicate candidate!")
        match = matches_59[0]
        self.assertEqual(match.complaint_id, "JS-2026-00059")
        self.assertEqual(match.candidate_physical_issue_id, anchor_id)
        self.assertEqual(match.review_status, "pending")
        self.assertEqual(match.gps_distance_meters, 0.0)
        self.assertEqual(match.image_similarity, 1.0, "Same photograph must yield 1.0 image similarity")
        self.assertGreaterEqual(match.similarity_score, 0.70)

        formatted = _format_match_response(match)
        self.assertIsNotNone(formatted.candidate_issue)
        self.assertIn("JS-2026-00058", formatted.candidate_issue.associated_complaint_ids)

    # -------------------------------------------------------------
    # New Security, Reliability, & Concurrency Tests (Items 12 - 18)
    # -------------------------------------------------------------

    def test_12_security_ssrf_and_url_validation(self):
        """12. Strict SSRF protection rejects all unsafe, internal, or non-allowlisted URLs."""
        # A. Localhost & Loopback
        self.assertFalse(validate_safe_evidence_url("http://localhost/image.png"))
        self.assertFalse(validate_safe_evidence_url("http://127.0.0.1:8000/image.png"))
        self.assertFalse(validate_safe_evidence_url("https://127.0.0.1/image.png"))
        self.assertFalse(validate_safe_evidence_url("http://[::1]/image.png"))

        # B. Cloud Metadata Endpoints
        self.assertFalse(validate_safe_evidence_url("http://169.254.169.254/latest/meta-data/"))
        self.assertFalse(validate_safe_evidence_url("https://169.254.169.254/secret"))
        self.assertFalse(validate_safe_evidence_url("http://metadata.google.internal/computeMetadata/v1/"))

        # C. RFC 1918 Private Ranges
        self.assertFalse(validate_safe_evidence_url("http://10.0.0.1/evidence.jpg"))
        self.assertFalse(validate_safe_evidence_url("https://192.168.1.1/evidence.jpg"))
        self.assertFalse(validate_safe_evidence_url("https://172.16.0.5/evidence.jpg"))

        # D. Non-HTTPS / Plain HTTP
        self.assertFalse(validate_safe_evidence_url("http://blob.vercel-storage.com/evidence.jpg"))

        # E. Untrusted External Domains & Spoofed Substrings
        self.assertFalse(validate_safe_evidence_url("https://evil-site.com/image.jpg"))
        self.assertFalse(validate_safe_evidence_url("https://evil-blob.vercel-storage.com.attacker.com/pothole.jpg"))
        self.assertFalse(validate_safe_evidence_url("https://attacker.com/blob.vercel-storage.com"))

        # F. URL Userinfo & Nonstandard Ports
        self.assertFalse(validate_safe_evidence_url("https://admin:secret@blob.vercel-storage.com/image.jpg"))
        self.assertFalse(validate_safe_evidence_url("https://blob.vercel-storage.com:8443/image.jpg"))

        # G. Valid Verified Hosts (Must Pass)
        with patch("socket.getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("76.76.21.35", 443))]):
            self.assertTrue(validate_safe_evidence_url("https://blob.vercel-storage.com/evidence/uuid.jpg"))
            self.assertTrue(validate_safe_evidence_url("https://store123.public.blob.vercel-storage.com/pothole.png"))

    def test_13_download_size_cap_and_timeout(self):
        """13. Remote download enforces strict 10MB ceiling and rejects oversized responses."""
        # Mock requests.get returning oversized stream
        with patch("requests.get") as mock_get:
            mock_res = MagicMock()
            mock_res.ok = True
            mock_res.headers = {"Content-Length": str(15 * 1024 * 1024)} # 15 MB
            mock_get.return_value.__enter__.return_value = mock_res

            res = _fetch_safe_remote_bytes("https://blob.vercel-storage.com/large.jpg")
            self.assertIsNone(res, "Oversized remote image must be rejected via Content-Length header")

        # Mock streaming response exceeding 10MB during download
        with patch("requests.get") as mock_get:
            mock_res = MagicMock()
            mock_res.ok = True
            mock_res.headers = {}
            # Yield 11 MB in chunks
            mock_res.iter_content.return_value = [b"X" * (1024 * 1024) for _ in range(11)]
            mock_get.return_value.__enter__.return_value = mock_res

            res = _fetch_safe_remote_bytes("https://blob.vercel-storage.com/stream_large.jpg")
            self.assertIsNone(res, "Stream exceeding 10MB must be aborted and return None")

    def test_14_decompression_bomb_and_dimension_safety(self):
        """14. Pillow safeguards prevent decompression bombs and enormous images from crashing process."""
        # Create a mock corrupt or enormous image path
        huge_img_bytes = io.BytesIO()
        # Normal image for baseline
        img = Image.new("RGB", (100, 100), color="red")
        img.save(huge_img_bytes, format="JPEG")
        raw_valid = huge_img_bytes.getvalue()

        with patch("app.services.duplicate_detection.image_similarity._fetch_safe_remote_bytes") as mock_fetch:
            mock_fetch.return_value = raw_valid
            dhash, ahash = compute_hashes_for_image("https://blob.vercel-storage.com/safe.jpg")
            self.assertIsNotNone(dhash)
            self.assertIsNotNone(ahash)

        # Mock corrupt bytes
        with patch("app.services.duplicate_detection.image_similarity._fetch_safe_remote_bytes") as mock_fetch:
            mock_fetch.return_value = b"NOT_AN_IMAGE_DATA_CORRUPT"
            dhash, ahash = compute_hashes_for_image("https://blob.vercel-storage.com/corrupt.jpg")
            self.assertIsNone(dhash)
            self.assertIsNone(ahash)

    def test_15_redundant_download_elimination_cache(self):
        """15. Image content and hashes are loaded only once per evaluation using ephemeral cache."""
        cache = {}
        with patch("app.services.duplicate_detection.image_similarity._fetch_safe_remote_bytes") as mock_fetch:
            img_bytes = io.BytesIO()
            Image.new("RGB", (64, 64), color="blue").save(img_bytes, format="PNG")
            mock_fetch.return_value = img_bytes.getvalue()

            url1 = "https://blob.vercel-storage.com/photo1.png"
            url2 = "https://blob.vercel-storage.com/photo2.png"

            # Compare list with repeated entries
            compare_evidence_lists([url1, url1], [url2, url1], cache=cache)

            # Each unique URL must only be fetched once!
            self.assertEqual(mock_fetch.call_count, 2, "Each unique URL must be fetched exactly once")
            self.assertIn(url1, cache)
            self.assertIn(url2, cache)

    def test_16_category_aware_earlier_unlinked_retrieval(self):
        """16. Earlier unlinked complaints are filtered by category compatibility so unrelated issues do not block."""
        # Unlinked Complaint 1: Garbage (older)
        c_garbage = Complaint(
            complaint_id="JS-2026-EARLY-GARBAGE",
            category="Garbage Accumulation",
            description="Garbage pile next to bus stop",
            latitude=16.9936192,
            longitude=81.776287,
            status="Received",
            created_at=datetime.datetime(2026, 11, 20, 8, 0, 0),
        )
        # Unlinked Complaint 2: Road Damage (newer than garbage, older than c_new)
        c_road_old = Complaint(
            complaint_id="JS-2026-EARLY-ROAD",
            category="Road Damage / Potholes",
            description="Large pothole near bus stop",
            latitude=16.9936192,
            longitude=81.776287,
            status="Received",
            created_at=datetime.datetime(2026, 11, 20, 8, 30, 0),
        )
        # New Complaint: Road Damage
        c_road_new = Complaint(
            complaint_id="JS-2026-NEW-ROAD",
            category="Road Damage / Potholes",
            description="Dangerous pothole right in front of bus stop",
            latitude=16.9936192,
            longitude=81.776287,
            status="Received",
            created_at=datetime.datetime(2026, 11, 20, 9, 0, 0),
        )
        self.db.add_all([c_garbage, c_road_old, c_road_new])
        self.db.commit()

        # Evaluate the new road complaint: It must match against c_road_old, NOT garbage!
        matches = DuplicateDetector.evaluate_complaint(c_road_new.complaint_id, self.db)
        self.assertEqual(len(matches), 1, "Must find exactly 1 matching candidate for road damage")

        self.db.refresh(c_road_old)
        self.assertIsNotNone(c_road_old.issue_id, "Old road complaint should be anchored")
        self.assertEqual(matches[0].candidate_physical_issue_id, c_road_old.issue_id)

        # Verify garbage complaint was NOT anchored as the road issue
        self.db.refresh(c_garbage)
        self.assertIsNone(c_garbage.issue_id, "Unrelated garbage complaint must remain untouched")

    def test_17_review_lifecycle_sibling_matches_dismissed(self):
        """17. When an admin approves one duplicate candidate, sibling pending candidates are marked dismissed."""
        # Create an anchor issue 1
        p1 = PhysicalIssue(
            issue_reference_id="ISSUE-2026-00991",
            category="Road Damage / Potholes",
            representative_latitude=16.9936192,
            representative_longitude=81.776287,
            description="Pothole Issue 1",
            current_status="Open",
        )
        # Create an anchor issue 2 nearby
        p2 = PhysicalIssue(
            issue_reference_id="ISSUE-2026-00992",
            category="Road Damage / Potholes",
            representative_latitude=16.9936200,
            representative_longitude=81.776280,
            description="Pothole Issue 2",
            current_status="Open",
        )
        # Complaint with 2 candidate matches
        comp = Complaint(
            complaint_id="JS-2026-MULTI-CAND",
            category="Road Damage / Potholes",
            description="Road crater candidate",
            latitude=16.9936192,
            longitude=81.776287,
            status="Received",
        )
        self.db.add_all([p1, p2, comp])
        self.db.commit()

        m1 = DuplicateMatch(
            complaint_id=comp.complaint_id,
            candidate_physical_issue_id=p1.issue_reference_id,
            similarity_score=0.92,
            confidence_level="high",
            recommendation="Candidate Duplicate",
            matching_explanation="Overlap 1",
            review_status="pending",
        )
        m2 = DuplicateMatch(
            complaint_id=comp.complaint_id,
            candidate_physical_issue_id=p2.issue_reference_id,
            similarity_score=0.88,
            confidence_level="high",
            recommendation="Candidate Duplicate",
            matching_explanation="Overlap 2",
            review_status="pending",
        )
        self.db.add_all([m1, m2])
        self.db.commit()

        # Approve match 1
        res = DuplicateDetector.approve_match(self.db, match_id=m1.id, reviewer_id="Admin Jane")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["review_status"], "approved")
        self.assertEqual(res["dismissed_sibling_count"], 1)

        self.db.refresh(m1)
        self.db.refresh(m2)
        self.assertEqual(m1.review_status, "approved")
        self.assertEqual(m2.review_status, "dismissed", "Sibling candidate must be marked dismissed")
        self.assertIn("Automatically dismissed", m2.review_reason)

    def test_18_true_concurrency_anchor_creation(self):
        """18. SQLite thread concurrency: Concurrent anchor creation under multi-threaded contention creates 1 canonical anchor."""
        # Note: Validates SQLite file-locking and process-level threading mutex (_anchor_creation_lock).
        # Multi-process distributed concurrency across separate server instances is enforced on PostgreSQL via pg_advisory_xact_lock.
        import tempfile
        # Create a temporary file-backed SQLite database to test true multi-connection concurrency
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            temp_db_path = tf.name

        try:
            conc_engine = create_engine(
                f"sqlite:///{temp_db_path}",
                connect_args={"timeout": 30.0}
            )
            Base.metadata.create_all(bind=conc_engine)
            ConcSessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=conc_engine)

            thread_count = 6
            complaints_data = [
                (f"JS-2026-CONC-{i:03d}", f"Concurrent road defect {i}")
                for i in range(thread_count)
            ]

            def process_worker(complaint_info):
                cid, desc = complaint_info
                worker_db = ConcSessionFactory()
                try:
                    c = Complaint(
                        complaint_id=cid,
                        category="Water Leakage",
                        description=desc,
                        latitude=17.445566,
                        longitude=78.384455,
                        status="Received",
                    )
                    worker_db.add(c)
                    worker_db.commit()

                    DuplicateDetector.evaluate_complaint(cid, worker_db)
                    worker_db.refresh(c)
                    return cid, c.issue_id
                finally:
                    worker_db.close()

            with ThreadPoolExecutor(max_workers=thread_count) as executor:
                results = list(executor.map(process_worker, complaints_data))

            verify_db = ConcSessionFactory()
            anchors = verify_db.query(PhysicalIssue).filter(
                PhysicalIssue.category == "Water Leakage"
            ).all()

            # Exactly 1 PhysicalIssue anchor must exist for this location and category
            self.assertEqual(len(anchors), 1, "Concurrent submissions at same coordinate/category must produce exactly 1 anchor")
            canonical_anchor_id = anchors[0].issue_reference_id

            # Check candidate duplicate matches created
            matches = verify_db.query(DuplicateMatch).filter(
                DuplicateMatch.candidate_physical_issue_id == canonical_anchor_id
            ).all()
            self.assertGreaterEqual(len(matches), thread_count - 2, "Subsequent concurrent complaints should match against the anchor")
            verify_db.close()

        finally:
            try:
                os.remove(temp_db_path)
            except Exception:
                pass

    def test_19_dns_rebinding_simulation_neutralized(self):
        """19. Simulating DNS rebinding to 127.0.0.1 or private IP is fully neutralized via IP pinning and pre-validation."""
        import socket
        from unittest.mock import patch, MagicMock
        from app.services.duplicate_detection.image_similarity import _fetch_safe_remote_bytes, get_validated_safe_storage_ip

        # Scenario A: Hostname resolves to 127.0.0.1 on initial check -> Immediately blocked
        with patch("socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', 443))]
            res = get_validated_safe_storage_ip("https://blob.vercel-storage.com/malicious.png")
            self.assertIsNone(res, "DNS resolving to 127.0.0.1 must be rejected by validator")

        # Scenario B: DNS rebinding TOCTOU simulation:
        # First query returns public IP 66.33.60.34 (validation phase).
        # Subsequent query returns 127.0.0.1 (rebinding attempt during connect phase).
        dns_call_count = [0]
        def dynamic_dns(host, port, *args, **kwargs):
            dns_call_count[0] += 1
            if dns_call_count[0] == 1:
                # 1st call: legitimate public IP
                return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('66.33.60.34', 443))]
            else:
                # Rebound to loopback!
                return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', 443))]

        # Mock socket.create_connection to record destination IP and prevent real network call
        connected_destinations = []
        mock_sock = MagicMock()
        def mock_create_connection(address, timeout=None):
            connected_destinations.append(address)
            return mock_sock

        with patch("socket.getaddrinfo", side_effect=dynamic_dns):
            with patch("socket.create_connection", side_effect=mock_create_connection):
                with patch("ssl.create_default_context") as mock_ssl_ctx:
                    mock_ssl_sock = MagicMock()
                    mock_ssl_ctx.return_value.wrap_socket.return_value = mock_ssl_sock
                    # Mock HTTP response
                    mock_ssl_sock.makefile.return_value = io.BytesIO(b"HTTP/1.1 200 OK\r\nContent-Length: 4\r\n\r\nTEST")

                    _fetch_safe_remote_bytes("https://blob.vercel-storage.com/rebind_test.png")

        # Verify:
        # 1. socket.create_connection was called with the PINNED public IP '66.33.60.34'
        self.assertGreater(len(connected_destinations), 0)
        dest_ip, dest_port = connected_destinations[0]
        self.assertEqual(dest_ip, "66.33.60.34", "Connection must be pinned to the validated public IP")
        self.assertEqual(dest_port, 443)

        # 2. Connection was NEVER opened to 127.0.0.1
        self.assertNotIn(("127.0.0.1", 443), connected_destinations, "Connection must never connect to 127.0.0.1")

    def test_20_postgres_advisory_lock_failure_fails_closed(self):
        """20. When PostgreSQL advisory lock acquisition fails, anchor creation aborts safely (fails closed) with no anchor created."""
        from sqlalchemy.exc import OperationalError

        # Part A: Test _create_provisional_anchor directly with a PostgreSQL session where lock acquisition fails
        mock_pg_db = MagicMock()
        mock_pg_db.get_bind.return_value.dialect.name = "postgresql"
        mock_pg_db.execute.side_effect = OperationalError("statement timeout", params={}, orig=Exception("Lock Timeout"))

        c_pg = Complaint(
            complaint_id="JS-2026-PG-LOCK-FAIL",
            category="Road Damage / Potholes",
            description="Pothole requiring lock",
            latitude=16.9936192,
            longitude=81.776287,
            status="Received",
        )

        with self.assertRaises(RuntimeError) as ctx:
            DuplicateDetector._create_provisional_anchor(c_pg, mock_pg_db)

        self.assertIn("PostgreSQL advisory lock acquisition failed", str(ctx.exception))
        self.assertIsNone(c_pg.issue_id, "Complaint must not be anchored when advisory lock fails")
        # Verify rollback was called on the database session
        mock_pg_db.rollback.assert_called_once()
        # Verify anchor was not added
        mock_pg_db.add.assert_not_called()

        # Part B: Integration test with evaluate_complaint ensuring exception propagates to background task
        c_real = Complaint(
            complaint_id="JS-2026-PG-INTEG-FAIL",
            category="Road Damage / Potholes",
            description="Pothole integration test",
            latitude=16.9936192,
            longitude=81.776287,
            status="Received",
        )
        self.db.add(c_real)
        self.db.commit()

        with patch.object(DuplicateDetector, "_create_provisional_anchor", side_effect=RuntimeError("Simulated lock failure")):
            with self.assertRaises(RuntimeError) as ctx2:
                DuplicateDetector.evaluate_complaint(c_real.complaint_id, self.db)
            self.assertIn("Simulated lock failure", str(ctx2.exception))

        self.db.refresh(c_real)
        self.assertIsNone(c_real.issue_id, "Complaint issue_id must remain None when lock fails")
        anchor_count = self.db.query(PhysicalIssue).filter(
            PhysicalIssue.category == "Road Damage / Potholes"
        ).count()
        self.assertEqual(anchor_count, 0, "No PhysicalIssue anchor should exist when lock fails")

    def test_21_integration_remote_loader_uses_pinned_connection(self):
        """21. Integration test: Actual remote image loader uses PinnedHTTPSConnection with pinned IP and hostname TLS SNI."""
        from app.services.duplicate_detection.image_similarity import PinnedHTTPSConnection, compute_hashes_for_image

        test_url = "https://blob.vercel-storage.com/pothole_integration.jpg"
        pinned_instances = []
        orig_init = PinnedHTTPSConnection.__init__
        orig_connect = PinnedHTTPSConnection.connect

        def spy_init(self, host, port=443, pinned_ip=None, **kwargs):
            pinned_instances.append({
                "instance": self,
                "host": host,
                "port": port,
                "pinned_ip": pinned_ip,
                "kwargs": kwargs
            })
            orig_init(self, host, port, pinned_ip=pinned_ip, **kwargs)

        connected_calls = []
        def spy_connect(self):
            connected_calls.append({
                "host": self.host,
                "port": self.port,
                "pinned_ip": self.pinned_ip,
            })
            # Prevent real network connection by creating mock socket
            mock_s = MagicMock()
            mock_s.getpeername.return_value = (self.pinned_ip, self.port)
            self.sock = mock_s
            # Mock getresponse on the connection
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.getheader.return_value = "100"
            # Small valid JPEG bytes
            img_buf = io.BytesIO()
            Image.new("RGB", (32, 32), color="green").save(img_buf, format="JPEG")
            mock_resp.read.side_effect = [img_buf.getvalue(), b""]
            self.getresponse = MagicMock(return_value=mock_resp)

        with patch("socket.getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("76.76.21.35", 443))]):
            with patch.object(PinnedHTTPSConnection, "__init__", spy_init):
                with patch.object(PinnedHTTPSConnection, "connect", spy_connect):
                    # Run the actual high-level image hashing function
                    dhash, ahash = compute_hashes_for_image(test_url)

        # Verify integration:
        # 1. PinnedHTTPSConnection was instantiated
        self.assertEqual(len(pinned_instances), 1, "PinnedHTTPSConnection must be instantiated by image loader")
        init_data = pinned_instances[0]
        self.assertEqual(init_data["host"], "blob.vercel-storage.com")
        self.assertIsNotNone(init_data["pinned_ip"], "Pre-validated pinned IP must be provided")

        # 2. connect() was executed using the pinned IP
        self.assertEqual(len(connected_calls), 1)
        self.assertEqual(connected_calls[0]["host"], "blob.vercel-storage.com")
        self.assertEqual(connected_calls[0]["pinned_ip"], init_data["pinned_ip"])

        # 3. Hashes were successfully computed from the loaded response
        self.assertIsNotNone(dhash)
        self.assertIsNotNone(ahash)

    def test_22_public_duplicate_endpoint_strips_citizen_pii(self):
        """22. Public/unauthenticated duplicate candidate endpoint strips citizen name and email."""
        c1 = Complaint(
            complaint_id="JS-2026-PII-01",
            category="Road Damage / Potholes",
            description="Deep pothole in public avenue",
            latitude=16.9936192,
            longitude=81.776287,
            status="Received",
            citizen_name="Confidential Citizen",
            citizen_email="citizen1@example.com",
            submission_channel="website",
        )
        c2 = Complaint(
            complaint_id="JS-2026-PII-02",
            category="Road Damage / Potholes",
            description="Crater in public avenue",
            latitude=16.9936192,
            longitude=81.776287,
            status="Received",
            citizen_name="Private Reporter",
            citizen_email="citizen2@example.com",
            submission_channel="gmail",
        )
        self.db.add_all([c1, c2])
        self.db.commit()

        DuplicateDetector.evaluate_complaint(c1.complaint_id, self.db)
        matches = DuplicateDetector.evaluate_complaint(c2.complaint_id, self.db)
        self.assertGreaterEqual(len(matches), 1)

        # Approve candidate match so c2 is associated with the PhysicalIssue anchor
        DuplicateDetector.approve_match(self.db, match_id=matches[0].id, reviewer_id="Admin Officer")

        # Call public unauthenticated endpoint without token
        public_resp = asyncio.run(
            get_complaint_duplicate_candidates(complaint_id=c2.complaint_id, db=self.db, token=None)
        )
        self.assertGreaterEqual(len(public_resp), 1)
        for match in public_resp:
            if match.candidate_issue and match.candidate_issue.associated_complaints:
                for comp_info in match.candidate_issue.associated_complaints:
                    self.assertNotIn("citizen_name", comp_info, "Public response must not contain citizen_name")
                    self.assertNotIn("citizen_email", comp_info, "Public response must not contain citizen_email")
                    self.assertIn("complaint_id", comp_info)

        # Call with invalid token
        invalid_resp = asyncio.run(
            get_complaint_duplicate_candidates(complaint_id=c2.complaint_id, db=self.db, token="invalid-token")
        )
        self.assertGreaterEqual(len(invalid_resp), 1)
        for match in invalid_resp:
            if match.candidate_issue and match.candidate_issue.associated_complaints:
                for comp_info in match.candidate_issue.associated_complaints:
                    self.assertNotIn("citizen_name", comp_info)
                    self.assertNotIn("citizen_email", comp_info)

    def test_23_admin_duplicate_review_queue_preserves_citizen_metadata(self):
        """23. Admin duplicate review queue preserves citizen identity details for authorized administrators."""
        c1 = Complaint(
            complaint_id="JS-2026-ADMIN-01",
            category="Streetlight Defect",
            description="Dark pole near library",
            latitude=17.385044,
            longitude=78.486671,
            status="Received",
            citizen_name="Suresh Kumar",
            citizen_email="suresh.k@example.com",
            submission_channel="website",
        )
        c2 = Complaint(
            complaint_id="JS-2026-ADMIN-02",
            category="Streetlight Defect",
            description="Pole light not glowing at night near library",
            latitude=17.385044,
            longitude=78.486671,
            status="Received",
            citizen_name="Ramesh Sharma",
            citizen_email="ramesh.s@example.com",
            submission_channel="gmail",
        )
        self.db.add_all([c1, c2])
        self.db.commit()

        DuplicateDetector.evaluate_complaint(c1.complaint_id, self.db)
        matches = DuplicateDetector.evaluate_complaint(c2.complaint_id, self.db)
        self.assertGreaterEqual(len(matches), 1)

        admin_user = User(
            id=999,
            username="admin_reviewer",
            full_name="Municipal Admin Officer",
            email="admin@jansakshi.gov.in",
            role="admin",
            is_active=True,
        )

        queue_items = asyncio.run(
            get_duplicate_review_queue(status_filter="all", confidence=None, db=self.db, current_user=admin_user)
        )
        self.assertGreater(len(queue_items), 0)

        # Find the queue item for c2
        c2_item = next((item for item in queue_items if item.match.complaint_id == c2.complaint_id), None)
        self.assertIsNotNone(c2_item, "Queue item for c2 should be found")
        self.assertEqual(c2_item.citizen_name, "Ramesh Sharma")
        self.assertEqual(c2_item.citizen_email, "ramesh.s@example.com")

        # Candidate issue must retain associated complaints with citizen metadata for admin
        cand_issue = c2_item.match.candidate_issue
        self.assertIsNotNone(cand_issue)
        if cand_issue.associated_complaints:
            c1_linked = next((c for c in cand_issue.associated_complaints if c["complaint_id"] == c1.complaint_id), None)
            if c1_linked:
                self.assertEqual(c1_linked.get("citizen_name"), "Suresh Kumar")
                self.assertEqual(c1_linked.get("citizen_email"), "suresh.k@example.com")

    def test_24_concurrent_anchor_creation_different_coordinates_unique_ids(self):
        """24. SQLite thread concurrency: Concurrent anchor creation at different coordinates allocates distinct, unique PhysicalIssue IDs."""
        # Note: Validates SQLite file-locking and process-level sequence mutex (_issue_id_seq_mutex).
        # Multi-process distributed sequence isolation across separate server instances is enforced on PostgreSQL via pg_advisory_xact_lock.
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            temp_db_path = tf.name

        try:
            conc_engine = create_engine(
                f"sqlite:///{temp_db_path}",
                connect_args={"timeout": 30.0}
            )
            Base.metadata.create_all(bind=conc_engine)
            ConcSessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=conc_engine)

            # 6 completely distinct coordinates
            complaint_coords = [
                ("JS-2026-DIFF-01", 16.10, 80.10, "Defect at Loc 1"),
                ("JS-2026-DIFF-02", 16.60, 80.60, "Defect at Loc 2"),
                ("JS-2026-DIFF-03", 17.10, 81.10, "Defect at Loc 3"),
                ("JS-2026-DIFF-04", 17.60, 81.60, "Defect at Loc 4"),
                ("JS-2026-DIFF-05", 18.10, 82.10, "Defect at Loc 5"),
                ("JS-2026-DIFF-06", 18.60, 82.60, "Defect at Loc 6"),
            ]

            def worker_fn(item):
                cid, lat, lon, desc = item
                worker_db = ConcSessionFactory()
                try:
                    c = Complaint(
                        complaint_id=cid,
                        category="Sanitation",
                        description=desc,
                        latitude=lat,
                        longitude=lon,
                        status="Received",
                    )
                    worker_db.add(c)
                    worker_db.commit()

                    DuplicateDetector.evaluate_complaint(cid, worker_db)
                    worker_db.refresh(c)
                    return cid, c.issue_id
                finally:
                    worker_db.close()

            with ThreadPoolExecutor(max_workers=len(complaint_coords)) as executor:
                results = list(executor.map(worker_fn, complaint_coords))

            verify_db = ConcSessionFactory()
            anchors = verify_db.query(PhysicalIssue).filter(
                PhysicalIssue.category == "Sanitation"
            ).all()

            # Every distinct coordinate must produce its own anchor
            self.assertEqual(len(anchors), len(complaint_coords))
            issue_ids = [a.issue_reference_id for a in anchors]

            # All allocated issue reference IDs must be strictly unique
            self.assertEqual(len(set(issue_ids)), len(complaint_coords), "Allocated PhysicalIssue IDs must be completely unique")
            current_year = datetime.datetime.now(datetime.timezone.utc).year
            for iid in issue_ids:
                self.assertTrue(iid.startswith(f"ISSUE-{current_year}-"), f"Invalid ID format: {iid}")

            verify_db.close()

        finally:
            try:
                os.remove(temp_db_path)
            except Exception:
                pass

    def test_25_postgres_issue_seq_lock_failure_fails_closed(self):
        """25. When PostgreSQL sequence advisory lock acquisition fails, ID allocation and anchor creation fail closed."""
        from sqlalchemy.exc import OperationalError

        mock_pg_db = MagicMock()
        mock_pg_db.get_bind.return_value.dialect.name = "postgresql"
        mock_pg_db.execute.side_effect = OperationalError("statement timeout", params={}, orig=Exception("Seq Lock Timeout"))

        with self.assertRaises(RuntimeError) as ctx:
            generate_issue_reference_id(mock_pg_db)

        self.assertIn("PostgreSQL advisory lock acquisition failed for PhysicalIssue sequence", str(ctx.exception))
        # Session rollback must be invoked
        mock_pg_db.rollback.assert_called_once()

    def test_26_live_neon_postgres_advisory_lock_multiconnection_sequence_isolation(self):
        """26. Live Neon PostgreSQL integration: Multi-connection sequence advisory lock guarantees cross-process mutual exclusion."""
        target_url = os.getenv("TARGET_DATABASE_URL", "").strip()
        if not target_url:
            env_file = os.path.join(backend_dir, ".env")
            if os.path.exists(env_file):
                with open(env_file, "r") as f:
                    for line in f:
                        if line.startswith("TARGET_DATABASE_URL="):
                            target_url = line.split("=", 1)[1].strip().strip('"').strip("'")
                            break

        if not target_url or not target_url.startswith("postgres"):
            self.skipTest("TARGET_DATABASE_URL not configured with PostgreSQL; skipping live Neon multi-connection test.")

        pg_engine = create_engine(target_url, pool_pre_ping=True, connect_args={"connect_timeout": 5})
        try:
            with pg_engine.connect() as test_conn:
                test_conn.execute(text("SELECT 1"))
        except Exception as conn_err:
            self.skipTest(f"Remote Neon PostgreSQL is unreachable ({conn_err}); skipping live test.")

        year = datetime.datetime.now(datetime.timezone.utc).year
        lock_key = f"jansakshi_seq_physical_issue_{year}"

        # Connection 1 begins a transaction and acquires the sequence advisory transaction lock
        with pg_engine.connect() as conn1:
            trans1 = conn1.begin()
            conn1.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": lock_key})

            # Connection 2 attempts non-blocking acquisition of the same lock while conn1 holds it
            with pg_engine.connect() as conn2:
                with conn2.begin():
                    acquired_conn2 = bool(
                        conn2.execute(text("SELECT pg_try_advisory_xact_lock(hashtext(:k))"), {"k": lock_key}).scalar()
                    )
                    self.assertFalse(
                        acquired_conn2,
                        "Independent connection 2 MUST NOT acquire the advisory lock while connection 1 holds it!"
                    )

            # Connection 1 completes its transaction
            trans1.commit()

        # After Connection 1 commits, Connection 2 can acquire the lock
        with pg_engine.connect() as conn2_after:
            with conn2_after.begin():
                acquired_after = bool(
                    conn2_after.execute(text("SELECT pg_try_advisory_xact_lock(hashtext(:k))"), {"k": lock_key}).scalar()
                )
                self.assertTrue(acquired_after, "Connection 2 must successfully acquire lock after Connection 1 commits.")

    def test_27_concurrent_physical_issue_service_create_issue_sqlite(self):
        """27. Concurrent PhysicalIssueService.create_issue() calls across multiple threads on SQLite allocate unique IDs without collision."""
        import tempfile
        from app.services.issue_service import PhysicalIssueService

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            temp_db_path = tf.name

        try:
            conc_engine = create_engine(
                f"sqlite:///{temp_db_path}",
                connect_args={"timeout": 30.0}
            )
            Base.metadata.create_all(bind=conc_engine)
            ConcSessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=conc_engine)

            thread_count = 8
            issues_to_create = [
                (f"Road Hazard {i}", 16.5 + (i * 0.05), 80.5 + (i * 0.05), f"Road issue description {i}")
                for i in range(thread_count)
            ]

            def worker_fn(issue_args):
                category, lat, lon, desc = issue_args
                worker_db = ConcSessionFactory()
                try:
                    service = PhysicalIssueService(worker_db)
                    created = service.create_issue(
                        category=category,
                        representative_latitude=lat,
                        representative_longitude=lon,
                        description=desc,
                        representative_location=f"Location {lat:.2f}, {lon:.2f}"
                    )
                    return created.id, created.issue_reference_id
                finally:
                    worker_db.close()

            with ThreadPoolExecutor(max_workers=thread_count) as executor:
                results = list(executor.map(worker_fn, issues_to_create))

            # Verify all thread results
            self.assertEqual(len(results), thread_count)
            allocated_ids = [r[1] for r in results]
            self.assertEqual(len(set(allocated_ids)), thread_count, "All created PhysicalIssue reference IDs must be unique!")

            # Verify in database
            verify_db = ConcSessionFactory()
            all_issues = verify_db.query(PhysicalIssue).all()
            self.assertEqual(len(all_issues), thread_count)
            db_ref_ids = [i.issue_reference_id for i in all_issues]
            self.assertEqual(len(set(db_ref_ids)), thread_count)

            year = datetime.datetime.now(datetime.timezone.utc).year
            for ref in db_ref_ids:
                self.assertTrue(ref.startswith(f"ISSUE-{year}-"), f"Invalid ID format: {ref}")

            verify_db.close()
        finally:
            try:
                os.remove(temp_db_path)
            except Exception:
                pass

    def test_28_dialect_detection_failure_fails_closed(self):
        """28. When database dialect identification fails completely, system fails closed by raising RuntimeError."""
        mock_unknown_db = MagicMock()
        mock_unknown_db.get_bind.return_value.dialect.name = "oracle_unknown"

        with patch("app.database.is_postgres", False):
            with patch("app.database.is_sqlite", False):
                with self.assertRaises(RuntimeError) as ctx:
                    get_verified_database_dialect(mock_unknown_db)

                self.assertIn("Unable to verify database dialect for concurrency locking", str(ctx.exception))

    def test_29_unique_id_collision_retry(self):
        """29. When an issue_reference_id collision occurs, create_issue() retries with a new ID."""
        from app.services.issue_service import PhysicalIssueService

        # Pre-seed an existing issue
        existing = PhysicalIssue(
            issue_reference_id="ISSUE-2026-99991",
            category="Roads",
            representative_latitude=16.5,
            representative_longitude=80.5,
            description="Existing road issue",
            current_status="Open",
            created_at=datetime.datetime.now(datetime.timezone.utc),
            updated_at=datetime.datetime.now(datetime.timezone.utc),
        )
        self.db.add(existing)
        self.db.commit()

        service = PhysicalIssueService(self.db)

        # Mock generate_issue_reference_id to collide on first attempt, succeed on second
        with patch(
            "app.services.issue_service.generate_issue_reference_id",
            side_effect=["ISSUE-2026-99991", "ISSUE-2026-99992"]
        ) as mock_gen:
            created = service.create_issue(
                category="Roads",
                representative_latitude=16.6,
                representative_longitude=80.6,
                description="New road issue"
            )

            self.assertEqual(mock_gen.call_count, 2, "generate_issue_reference_id must be called twice due to retry")
            self.assertEqual(created.issue_reference_id, "ISSUE-2026-99992")

            # Verify both issues exist in database
            issues = self.db.query(PhysicalIssue).filter(PhysicalIssue.category == "Roads").all()
            self.assertEqual(len(issues), 2)
            self.assertEqual({i.issue_reference_id for i in issues}, {"ISSUE-2026-99991", "ISSUE-2026-99992"})

    def test_30_non_integrity_error_does_not_retry_or_cause_second_insert(self):
        """30. Non-IntegrityError during create/commit does not trigger a retry or second insert."""
        from sqlalchemy.exc import OperationalError
        from app.services.issue_service import PhysicalIssueService

        service = PhysicalIssueService(self.db)

        with patch("app.services.issue_service.generate_issue_reference_id", return_value="ISSUE-2026-FAIL01") as mock_gen:
            with patch.object(self.db, "commit", side_effect=OperationalError("disk I/O error", params={}, orig=Exception("disk error"))) as mock_commit:
                with self.assertRaises(OperationalError):
                    service.create_issue(
                        category="Roads",
                        representative_latitude=16.5,
                        representative_longitude=80.5,
                        description="Should fail without retry"
                    )

                # Must not retry: exactly 1 attempt
                self.assertEqual(mock_gen.call_count, 1)
                self.assertEqual(mock_commit.call_count, 1)

    def test_31_post_commit_refresh_failure_does_not_retry_create(self):
        """31. An exception during db.refresh() after successful commit propagates without retrying create."""
        from sqlalchemy.exc import OperationalError
        from app.services.issue_service import PhysicalIssueService

        service = PhysicalIssueService(self.db)

        # Track commit calls and count created issues
        orig_commit = self.db.commit
        commit_calls = []
        def tracking_commit():
            commit_calls.append(True)
            orig_commit()

        with patch("app.services.issue_service.generate_issue_reference_id", return_value="ISSUE-2026-REFRESH-FAIL") as mock_gen:
            with patch.object(self.db, "commit", side_effect=tracking_commit):
                with patch.object(self.db, "refresh", side_effect=OperationalError("connection dropped during refresh", params={}, orig=Exception("dropped"))):
                    with self.assertRaises(OperationalError):
                        service.create_issue(
                            category="Streetlights",
                            representative_latitude=17.0,
                            representative_longitude=78.0,
                            description="Issue with post-commit refresh failure"
                        )

                    # ID generation and commit must be executed exactly ONCE
                    self.assertEqual(mock_gen.call_count, 1, "Must NOT re-execute generate_issue_reference_id after commit")
                    self.assertEqual(len(commit_calls), 1, "Must NOT re-execute commit after successful commit")

        # The issue record was committed once and persisted
        persisted = self.db.query(PhysicalIssue).filter(PhysicalIssue.issue_reference_id == "ISSUE-2026-REFRESH-FAIL").all()
        self.assertEqual(len(persisted), 1, "Exactly one issue record must be persisted; no duplicate creation")

    def test_32_unrelated_unique_constraint_violation_does_not_retry(self):
        """32. Unrelated unique constraint violations (e.g. complaints.complaint_id) do NOT trigger a retry."""
        from sqlalchemy.exc import IntegrityError
        from app.services.issue_service import PhysicalIssueService

        service = PhysicalIssueService(self.db)

        # Part A: SQLite unrelated unique constraint (complaints.tracking_token)
        sqlite_unrelated_err = IntegrityError(
            "INSERT INTO complaints ...",
            params={},
            orig=Exception("UNIQUE constraint failed: complaints.tracking_token")
        )
        with patch("app.services.issue_service.generate_issue_reference_id", return_value="ISSUE-2026-UNRELATED-01") as mock_gen_a:
            with patch.object(self.db, "commit", side_effect=sqlite_unrelated_err):
                with self.assertRaises(IntegrityError):
                    service.create_issue(category="Roads", representative_latitude=16.5, representative_longitude=80.5, description="Test")

                self.assertEqual(mock_gen_a.call_count, 1, "Must fail immediately without retrying unrelated SQLite constraint")

        # Part B: PostgreSQL driver diagnostic unrelated unique constraint (complaints_complaint_id_key)
        mock_pg_diag = MagicMock(
            constraint_name="complaints_complaint_id_key",
            column_name="complaint_id",
            message_detail="Key (complaint_id)=(JS-2026-00001) already exists."
        )
        mock_pg_orig = MagicMock(diag=mock_pg_diag)
        pg_unrelated_err = IntegrityError(
            "INSERT INTO complaints ...",
            params={},
            orig=mock_pg_orig
        )
        with patch("app.services.issue_service.generate_issue_reference_id", return_value="ISSUE-2026-UNRELATED-02") as mock_gen_b:
            with patch.object(self.db, "commit", side_effect=pg_unrelated_err):
                with self.assertRaises(IntegrityError):
                    service.create_issue(category="Roads", representative_latitude=16.5, representative_longitude=80.5, description="Test")

                self.assertEqual(mock_gen_b.call_count, 1, "Must fail immediately without retrying unrelated PostgreSQL constraint")

    def test_33_is_issue_reference_id_collision_classification(self):
        """33. Unit verification of is_issue_reference_id_collision classifier across engines."""
        from sqlalchemy.exc import IntegrityError

        # 1. Matching cases:
        # SQLite matching
        err_sqlite = IntegrityError("st", {}, orig=Exception("UNIQUE constraint failed: physical_issues.issue_reference_id"))
        self.assertTrue(is_issue_reference_id_collision(err_sqlite))

        # PostgreSQL matching via diag constraint_name on physical_issues
        diag_match = MagicMock(table_name="physical_issues", constraint_name="physical_issues_issue_reference_id_key", column_name="issue_reference_id", message_detail="")
        err_pg_diag = IntegrityError("st", {}, orig=MagicMock(diag=diag_match))
        self.assertTrue(is_issue_reference_id_collision(err_pg_diag))

        # PostgreSQL matching via BOTH table_name == 'physical_issues' AND column_name == 'issue_reference_id'
        diag_col = MagicMock(table_name="physical_issues", constraint_name=None, column_name="issue_reference_id", message_detail="")
        err_pg_col = IntegrityError("st", {}, orig=MagicMock(diag=diag_col))
        self.assertTrue(is_issue_reference_id_collision(err_pg_col))

        # PostgreSQL matching via table_name == 'physical_issues' and message_detail
        diag_detail = MagicMock(table_name="physical_issues", constraint_name=None, column_name=None, message_detail="Key (issue_reference_id)=(ISSUE-2026-00001) already exists.")
        err_pg_detail = IntegrityError("st", {}, orig=MagicMock(diag=diag_detail))
        self.assertTrue(is_issue_reference_id_collision(err_pg_detail))

        # 2. Non-matching (unrelated / ambiguous) cases:
        # PostgreSQL unrelated table with unique column named 'issue_reference_id'
        diag_unrelated_table = MagicMock(table_name="archived_issues", column_name="issue_reference_id", message_detail="Key (issue_reference_id)=(123) already exists.")
        err_pg_unrelated_table = IntegrityError("st", {}, orig=MagicMock(diag=diag_unrelated_table))
        self.assertFalse(is_issue_reference_id_collision(err_pg_unrelated_table), "Must reject unrelated table with column named issue_reference_id")

        # PostgreSQL unrelated constraint name on different table
        diag_other_table_constraint = MagicMock(table_name="audit_issues", constraint_name="audit_issues_issue_reference_id_key")
        self.assertFalse(is_issue_reference_id_collision(IntegrityError("st", {}, orig=MagicMock(diag=diag_other_table_constraint))))

        # PostgreSQL missing table_name and ambiguous column_name without known constraint
        diag_ambiguous_col = MagicMock(table_name="", constraint_name="other_table_idx", column_name="issue_reference_id")
        self.assertFalse(is_issue_reference_id_collision(IntegrityError("st", {}, orig=MagicMock(diag=diag_ambiguous_col))))

        # Text fallback referencing another table
        err_text_unrelated = IntegrityError('duplicate key value violates unique constraint "archived_issues_issue_reference_id_key" Key (issue_reference_id)=(123) already exists.', {}, None)
        self.assertFalse(is_issue_reference_id_collision(err_text_unrelated))

        # SQLite unrelated table
        err_sqlite_other = IntegrityError("st", {}, orig=Exception("UNIQUE constraint failed: complaints.complaint_id"))
        self.assertFalse(is_issue_reference_id_collision(err_sqlite_other))

        # General non-IntegrityError
        self.assertFalse(is_issue_reference_id_collision(ValueError("other error")))

    def test_34_unrelated_table_unique_issue_reference_id_column_does_not_retry(self):
        """34. An unrelated table with a unique issue_reference_id column returns False and does NOT trigger retry."""
        from sqlalchemy.exc import IntegrityError
        from app.services.issue_service import PhysicalIssueService

        service = PhysicalIssueService(self.db)

        # Unrelated table 'archived_issues' has a unique column 'issue_reference_id'
        mock_pg_diag = MagicMock(
            table_name="archived_issues",
            column_name="issue_reference_id",
            constraint_name="archived_issues_issue_reference_id_key",
            message_detail="Key (issue_reference_id)=(ARCH-01) already exists."
        )
        mock_pg_orig = MagicMock(diag=mock_pg_diag)
        unrelated_table_err = IntegrityError(
            "INSERT INTO archived_issues (issue_reference_id) VALUES ('ARCH-01')",
            params={},
            orig=mock_pg_orig
        )

        with patch("app.services.issue_service.generate_issue_reference_id", return_value="ISSUE-2026-UNRELATED-TABLE") as mock_gen:
            with patch.object(self.db, "commit", side_effect=unrelated_table_err):
                with self.assertRaises(IntegrityError):
                    service.create_issue(
                        category="Roads",
                        representative_latitude=16.5,
                        representative_longitude=80.5,
                        description="Should fail without retry on unrelated table"
                    )

                # Must fail immediately: exactly 1 attempt, zero retries
                self.assertEqual(mock_gen.call_count, 1, "Must NOT retry when unique collision occurs on an unrelated table")

    def test_35_provisional_anchor_and_audit_event_atomicity(self):
        """35. Provisional anchor, complaint association, and audit event persist atomically in a single transaction."""
        from app.services.duplicate_detection.duplicate_detector import DuplicateDetector
        from app.models.complaint import PhysicalIssue, ComplaintEvent

        complaint = self._create_test_complaint(
            citizen_id="citizen-atomic-1",
            category="Roads",
            lat=16.7100,
            lon=80.7100,
            desc="Pothole needing atomic anchor creation"
        )
        self.assertIsNone(complaint.issue_id)

        # Successful atomic creation
        anchor = DuplicateDetector._create_provisional_anchor(complaint, self.db)
        self.assertIsNotNone(anchor)
        self.assertEqual(complaint.issue_id, anchor.issue_reference_id)

        # Verify physical issue and audit event exist
        persisted_anchor = self.db.query(PhysicalIssue).filter_by(issue_reference_id=anchor.issue_reference_id).first()
        self.assertIsNotNone(persisted_anchor)

        event = self.db.query(ComplaintEvent).filter_by(
            complaint_id=complaint.complaint_id,
            event_type="provisional_issue_anchor_created"
        ).first()
        self.assertIsNotNone(event)
        self.assertEqual(event.new_value, anchor.issue_reference_id)

        # Now test atomicity rollback when commit fails
        complaint_fail = self._create_test_complaint(
            citizen_id="citizen-atomic-2",
            category="Sanitation",
            lat=16.7200,
            lon=80.7200,
            desc="Garbage dump with simulated commit failure"
        )
        with patch.object(self.db, "commit", side_effect=RuntimeError("Simulated DB connection drop on commit")):
            with self.assertRaises(RuntimeError):
                DuplicateDetector._create_provisional_anchor(complaint_fail, self.db)

        # After rollback, verify no orphan anchor or audit event was persisted
        failed_event = self.db.query(ComplaintEvent).filter_by(
            complaint_id=complaint_fail.complaint_id,
            event_type="provisional_issue_anchor_created"
        ).first()
        self.assertIsNone(failed_event, "No audit event should persist after failed transaction commit")

    def test_36_unrelated_integrity_error_not_swallowed_when_anchor_exists(self):
        """36. An unrelated IntegrityError is never swallowed or suppressed even if an anchor exists."""
        from app.services.duplicate_detection.duplicate_detector import DuplicateDetector
        from sqlalchemy.exc import IntegrityError

        complaint = self._create_test_complaint(
            citizen_id="citizen-err-1",
            category="Water Supply",
            lat=16.8000,
            lon=80.8000,
            desc="Water pipeline issue"
        )

        unrelated_err = IntegrityError(
            "FOREIGN KEY constraint failed: complaints.user_id",
            params={},
            orig=Exception("FOREIGN KEY constraint failed: complaints.user_id")
        )

        with patch("app.services.issue_id_service.generate_issue_reference_id", return_value="ISSUE-2026-UNRELATED-ERR") as mock_gen:
            with patch.object(self.db, "commit", side_effect=unrelated_err):
                with self.assertRaises(IntegrityError):
                    DuplicateDetector._create_provisional_anchor(complaint, self.db)

                # Must not loop / retry on unrelated integrity errors
                self.assertEqual(mock_gen.call_count, 1)

    def test_37_anchor_post_commit_refresh_failure_does_not_retry_or_duplicate(self):
        """37. Post-commit db.refresh failure outside retry handler does not retry or create duplicate anchors."""
        from app.services.duplicate_detection.duplicate_detector import DuplicateDetector
        from app.models.complaint import PhysicalIssue

        complaint = self._create_test_complaint(
            citizen_id="citizen-refresh-1",
            category="Electricity",
            lat=16.8500,
            lon=80.8500,
            desc="Flickering street light"
        )

        with patch("app.services.issue_id_service.generate_issue_reference_id", return_value="ISSUE-2026-REFRESH-TEST") as mock_gen:
            with patch.object(self.db, "refresh", side_effect=RuntimeError("Post-commit refresh failed")):
                with self.assertRaises(RuntimeError):
                    DuplicateDetector._create_provisional_anchor(complaint, self.db)

                # Exactly 1 ID generation and anchor insertion attempt occurred (no retries)
                self.assertEqual(mock_gen.call_count, 1)

        # The anchor was committed in the DB before refresh failed
        persisted = self.db.query(PhysicalIssue).filter_by(issue_reference_id="ISSUE-2026-REFRESH-TEST").first()
        self.assertIsNotNone(persisted, "The anchor should remain committed even if post-commit refresh failed")

    def test_38_concurrent_same_location_anchor_creation_resolves_to_single_anchor(self):
        """38. Same-location concurrent anchor collision links to winning anchor with linked audit event."""
        from app.services.duplicate_detection.duplicate_detector import DuplicateDetector
        from app.models.complaint import PhysicalIssue, ComplaintEvent
        from sqlalchemy.exc import IntegrityError

        complaint = self._create_test_complaint(
            citizen_id="citizen-race-1",
            category="Roads",
            lat=16.9000,
            lon=80.9000,
            desc="Concurrent road pothole"
        )

        collision_err = IntegrityError(
            "UNIQUE constraint failed: physical_issues.issue_reference_id",
            params={},
            orig=Exception("UNIQUE constraint failed: physical_issues.issue_reference_id")
        )

        attempt_count = 0
        real_commit = self.db.commit
        def side_effect_commit():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count == 1:
                # Another concurrent thread commits winning anchor at same location before our transaction finishes
                from sqlalchemy.orm import sessionmaker
                concurrent_session_factory = sessionmaker(bind=test_engine)
                concurrent_db = concurrent_session_factory()
                try:
                    winning_anchor = PhysicalIssue(
                        issue_reference_id="ISSUE-2026-WINNING",
                        category="Roads",
                        representative_latitude=16.9000,
                        representative_longitude=80.9000,
                        representative_location="Winning Anchor Location",
                        description="[Provisional Issue Anchor] Winning anchor",
                        current_status="Open",
                        created_at=utc_now(),
                        updated_at=utc_now(),
                    )
                    concurrent_db.add(winning_anchor)
                    concurrent_db.commit()
                finally:
                    concurrent_db.close()
                raise collision_err
            else:
                return real_commit()

        # Simulate collision on first commit attempt, then recovery returning winning anchor without silent auto-association
        with patch.object(self.db, "commit", side_effect=side_effect_commit):
            anchor = DuplicateDetector._create_provisional_anchor(complaint, self.db)
            self.assertEqual(anchor.issue_reference_id, "ISSUE-2026-WINNING")
            self.db.refresh(complaint)
            self.assertIsNone(complaint.issue_id, "Subsequent complaint must not be auto-linked without authority approval")

            # Verify no auto-linking audit event was created
            link_event = self.db.query(ComplaintEvent).filter_by(
                complaint_id=complaint.complaint_id,
                event_type="provisional_issue_anchor_linked"
            ).first()
            self.assertIsNone(link_event, "No auto-link audit event should be created before review")

    def test_39_id_generation_failure_triggers_rollback_and_propagates_exception(self):
        """39. Database failure during ID generation rolls back the session and propagates original exception."""
        from app.services.duplicate_detection.duplicate_detector import DuplicateDetector
        from app.models.complaint import PhysicalIssue, ComplaintEvent

        complaint = self._create_test_complaint(
            citizen_id="citizen-id-fail-1",
            category="Sanitation",
            lat=16.9500,
            lon=80.9500,
            desc="Garbage piling up near school"
        )

        with patch("app.services.issue_id_service.generate_issue_reference_id", side_effect=RuntimeError("Simulated DB sequence lock timeout")):
            with patch.object(self.db, "rollback", wraps=self.db.rollback) as mock_rollback:
                with self.assertRaises(RuntimeError) as cm:
                    DuplicateDetector._create_provisional_anchor(complaint, self.db)

                self.assertIn("Simulated DB sequence lock timeout", str(cm.exception))
                # Verify rollback was called to ensure active transaction and spatial lock do not leak
                self.assertGreaterEqual(mock_rollback.call_count, 1)

        # Confirm no physical issue or audit event was persisted
        persisted_anchor = self.db.query(PhysicalIssue).filter_by(category="Sanitation").first()
        self.assertIsNone(persisted_anchor)

        event = self.db.query(ComplaintEvent).filter_by(
            complaint_id=complaint.complaint_id,
            event_type="provisional_issue_anchor_created"
        ).first()
        self.assertIsNone(event)

    def test_40_initial_existing_anchor_lookup_failure_triggers_rollback_and_propagates_exception(self):
        """40. Database failure during initial existing-anchor lookup triggers rollback and propagates exception."""
        from app.services.duplicate_detection.duplicate_detector import DuplicateDetector
        from app.models.complaint import PhysicalIssue

        complaint = self._create_test_complaint(
            citizen_id="citizen-lookup-fail-1",
            category="Roads",
            lat=16.6500,
            lon=80.6500,
            desc="Pothole lookup failure test"
        )

        real_query = self.db.query

        def side_effect_query(entity, *args, **kwargs):
            if entity is PhysicalIssue:
                raise RuntimeError("Simulated DB query timeout during initial existing-anchor lookup")
            return real_query(entity, *args, **kwargs)

        with patch.object(self.db, "query", side_effect=side_effect_query):
            with patch.object(self.db, "rollback", wraps=self.db.rollback) as mock_rollback:
                with self.assertRaises(RuntimeError) as cm:
                    DuplicateDetector._create_provisional_anchor(complaint, self.db)

                self.assertIn("Simulated DB query timeout during initial existing-anchor lookup", str(cm.exception))
                self.assertGreaterEqual(mock_rollback.call_count, 1, "Must call db.rollback() on initial lookup failure")

    def test_41_existing_exact_anchor_does_not_silently_associate_complaint(self):
        """41. An existing exact anchor at same coordinates returns the anchor without silently associating the complaint."""
        from app.services.duplicate_detection.duplicate_detector import DuplicateDetector
        from app.models.complaint import PhysicalIssue

        # Pre-existing anchor in DB
        anchor = PhysicalIssue(
            issue_reference_id="ISSUE-2026-PREEXIST",
            category="Road Damage / Potholes",
            representative_latitude=16.9936,
            representative_longitude=81.7762,
            representative_location="Main Bazaar",
            description="[Provisional Issue Anchor] Pre-existing crater",
            current_status="Open",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self.db.add(anchor)
        self.db.commit()

        # New unassociated complaint at exact same coordinates
        c_new = self._create_test_complaint(
            citizen_id="citizen-independent-1",
            category="Road Damage / Potholes",
            lat=16.9936,
            lon=81.7762,
            desc="Different citizen reporting the same crater"
        )
        self.assertIsNone(c_new.issue_id)

        returned_anchor = DuplicateDetector._create_provisional_anchor(c_new, self.db)
        self.assertEqual(returned_anchor.issue_reference_id, "ISSUE-2026-PREEXIST")

        # Crucial check: c_new.issue_id MUST NOT be automatically assigned!
        self.db.refresh(c_new)
        self.assertIsNone(c_new.issue_id, "Complaint must preserve independence and not be silently auto-associated")

    def test_42_complaint_at_existing_anchor_receives_pending_review_candidate(self):
        """42. Evaluating a complaint at an existing anchor creates a pending DuplicateMatch for authority review."""
        from app.services.duplicate_detection.duplicate_detector import DuplicateDetector
        from app.models.complaint import PhysicalIssue, DuplicateMatch

        anchor = PhysicalIssue(
            issue_reference_id="ISSUE-2026-REVIEW-ME",
            category="Road Damage / Potholes",
            representative_latitude=16.9936,
            representative_longitude=81.7762,
            representative_location="Main Bazaar",
            description="[Provisional Issue Anchor] Pre-existing crater for review test",
            current_status="Open",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self.db.add(anchor)
        self.db.commit()

        c = self._create_test_complaint(
            citizen_id="citizen-cand-1",
            category="Road Damage / Potholes",
            lat=16.9936,
            lon=81.7762,
            desc="Pothole at the same spot"
        )

        matches = DuplicateDetector.evaluate_complaint(c.complaint_id, self.db)
        self.assertEqual(len(matches), 1, "Must generate exactly 1 candidate duplicate match")
        self.assertEqual(matches[0].candidate_physical_issue_id, "ISSUE-2026-REVIEW-ME")
        self.assertEqual(matches[0].review_status, "pending")

        # Confirm unlinked before approval
        self.db.refresh(c)
        self.assertIsNone(c.issue_id, "Complaint must not be linked prior to manual approval")

        # Approve the match and verify association occurs ONLY on approval
        DuplicateDetector.approve_match(self.db, match_id=matches[0].id, reviewer_id="Officer Smith")
        self.db.refresh(c)
        self.assertEqual(c.issue_id, "ISSUE-2026-REVIEW-ME", "Complaint must be linked after authority approval")

    def test_43_rejected_candidate_remains_independently_recorded(self):
        """43. A rejected candidate match leaves complaint independent and records audit event."""
        from app.services.duplicate_detection.duplicate_detector import DuplicateDetector
        from app.models.complaint import PhysicalIssue, DuplicateMatch, ComplaintEvent

        anchor = PhysicalIssue(
            issue_reference_id="ISSUE-2026-REJECT-TEST",
            category="Sanitation",
            representative_latitude=16.5000,
            representative_longitude=80.5000,
            representative_location="Dump Yard",
            description="[Provisional Issue Anchor] Garbage cluster",
            current_status="Open",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self.db.add(anchor)
        self.db.commit()

        c = self._create_test_complaint(
            citizen_id="citizen-rej-1",
            category="Sanitation",
            lat=16.5000,
            lon=80.5000,
            desc="Separate distinct pile of commercial debris"
        )

        matches = DuplicateDetector.evaluate_complaint(c.complaint_id, self.db)
        self.assertEqual(len(matches), 1)
        match_id = matches[0].id

        # Authority officer inspects and rejects because it is a distinct problem
        res = DuplicateDetector.reject_match(
            self.db,
            match_id=match_id,
            reviewer_id="Officer Johnson",
            review_reason="Distinct commercial debris needing independent tractor"
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["review_status"], "rejected")

        # Confirm the rejected match is recorded in DB
        match_record = self.db.query(DuplicateMatch).filter_by(id=match_id).first()
        self.assertEqual(match_record.review_status, "rejected")
        self.assertEqual(match_record.reviewer_id, "Officer Johnson")

        # Confirm rejection event
        event = self.db.query(ComplaintEvent).filter_by(
            complaint_id=c.complaint_id,
            event_type="issue_association_rejected"
        ).first()
        self.assertIsNotNone(event)
        self.assertEqual(event.previous_value, "ISSUE-2026-REJECT-TEST")

    def test_44_spatial_lock_is_reacquired_after_failed_transaction_before_retry(self):
        """44. Spatial advisory lock is reacquired after a failed transaction collision rollback before retry."""
        from app.services.duplicate_detection.duplicate_detector import DuplicateDetector
        from sqlalchemy.exc import IntegrityError
        from sqlalchemy import text

        complaint = self._create_test_complaint(
            citizen_id="citizen-reacquire-1",
            category="Roads",
            lat=16.8800,
            lon=80.8800,
            desc="Testing lock reacquisition"
        )

        collision_err = IntegrityError(
            "UNIQUE constraint failed: physical_issues.issue_reference_id",
            params={},
            orig=Exception("UNIQUE constraint failed: physical_issues.issue_reference_id")
        )

        lock_calls = []
        real_execute = self.db.execute

        def spy_execute(statement, *args, **kwargs):
            stmt_str = str(statement)
            if "pg_advisory_xact_lock" in stmt_str:
                lock_calls.append(kwargs.get("params") or args)
                return MagicMock()
            return real_execute(statement, *args, **kwargs)

        attempt = 0
        real_commit = self.db.commit
        def side_effect_commit():
            nonlocal attempt
            attempt += 1
            if attempt == 1:
                raise collision_err
            return real_commit()

        with patch("app.services.issue_id_service.get_verified_database_dialect", return_value="postgresql"):
            with patch.object(self.db, "execute", side_effect=spy_execute):
                with patch.object(self.db, "commit", side_effect=side_effect_commit):
                    anchor = DuplicateDetector._create_provisional_anchor(complaint, self.db)
                    self.assertIsNotNone(anchor)

        # In PostgreSQL, pg_advisory_xact_lock must be acquired on attempt 1 AND reacquired on attempt 2 after rollback!
        self.assertGreaterEqual(
            len(lock_calls),
            2,
            f"Expected spatial advisory lock to be acquired initially and reacquired after collision rollback, got {len(lock_calls)} calls"
        )

    def test_45_concurrent_same_location_requests_cannot_create_duplicate_anchors_after_collision_rollback(self):
        """45. Concurrent same-location requests resolve to exactly one canonical anchor; no duplicates created."""
        from app.services.duplicate_detection.duplicate_detector import DuplicateDetector
        from app.models.complaint import PhysicalIssue, Complaint

        c1 = self._create_test_complaint("cit-conc-1", "Water Supply", 16.5500, 80.5500, "Burst pipe report 1")
        c2 = self._create_test_complaint("cit-conc-2", "Water Supply", 16.5500, 80.5500, "Burst pipe report 2")

        # Use independent SQLAlchemy sessions for concurrent workers rather than sharing a single session
        session_factory = sessionmaker(bind=self.db.get_bind())
        db1 = session_factory()
        db2 = session_factory()

        try:
            comp1 = db1.query(Complaint).filter_by(complaint_id=c1.complaint_id).first()
            comp2 = db2.query(Complaint).filter_by(complaint_id=c2.complaint_id).first()

            # Run concurrent anchor creation via thread pool with independent sessions
            with ThreadPoolExecutor(max_workers=2) as executor:
                fut1 = executor.submit(DuplicateDetector._create_provisional_anchor, comp1, db1)
                fut2 = executor.submit(DuplicateDetector._create_provisional_anchor, comp2, db2)
                anchor1 = fut1.result()
                anchor2 = fut2.result()
        finally:
            db1.close()
            db2.close()

        # Both complaints must receive the EXACT same canonical anchor
        self.assertEqual(anchor1.issue_reference_id, anchor2.issue_reference_id)

        # In DB, exactly 1 PhysicalIssue should exist for this location and category
        anchors_in_db = self.db.query(PhysicalIssue).filter(
            PhysicalIssue.category == "Water Supply",
            PhysicalIssue.representative_latitude >= 16.5499,
            PhysicalIssue.representative_latitude <= 16.5501,
            PhysicalIssue.representative_longitude >= 80.5499,
            PhysicalIssue.representative_longitude <= 80.5501,
        ).all()
        self.assertEqual(len(anchors_in_db), 1, "Exactly one canonical anchor must exist for the location")

    def test_46_coordinate_boundary_race_prevention(self):
        """46. Boundary coordinates (e.g. 16.10004 vs 16.10006) share unified advisory lock and resolve to 1 anchor."""
        from app.services.duplicate_detection.duplicate_detector import DuplicateDetector
        from app.models.complaint import PhysicalIssue

        # 16.10004 and 16.10006 are ~2.2 metres apart, well within tolerance 0.0001 deg (~11 metres)
        # Old 4-decimal formatting: 16.10004 -> "16.1000", 16.10006 -> "16.1001" (split lock keys)
        # Unified locking: both use "jansakshi_provisional_anchor_mutex"
        c1 = self._create_test_complaint("cit-bound-1", "Sanitation", 16.10004, 80.10004, "Garbage at boundary 1")
        c2 = self._create_test_complaint("cit-bound-2", "Sanitation", 16.10006, 80.10006, "Garbage at boundary 2")

        lock_keys_used = []
        real_execute = self.db.execute

        def spy_execute(statement, *args, **kwargs):
            stmt_str = str(statement)
            if "pg_advisory_xact_lock" in stmt_str:
                params = kwargs.get("params") or (args[0] if args else {})
                if isinstance(params, dict) and "k" in params:
                    lock_keys_used.append(params["k"])
                return MagicMock()
            return real_execute(statement, *args, **kwargs)

        with patch("app.services.issue_id_service.get_verified_database_dialect", return_value="postgresql"):
            with patch.object(self.db, "execute", side_effect=spy_execute):
                anchor1 = DuplicateDetector._create_provisional_anchor(c1, self.db)
                anchor2 = DuplicateDetector._create_provisional_anchor(c2, self.db)

        # Both calls must acquire the unified lock key, NOT coordinate-rounded split keys
        self.assertIn("jansakshi_provisional_anchor_mutex", lock_keys_used)
        provisional_locks = [k for k in lock_keys_used if "provisional_anchor" in k or "jansakshi_anchor" in k]
        self.assertEqual(len(provisional_locks), 2, "Both calls must acquire provisional anchor mutex")
        for key in provisional_locks:
            self.assertEqual(key, "jansakshi_provisional_anchor_mutex", "All provisional lock calls must use the unified mutex key")

        # Both complaints must resolve to the identical canonical anchor
        self.assertEqual(anchor1.issue_reference_id, anchor2.issue_reference_id)

        # Only 1 PhysicalIssue anchor must exist in the database for this boundary cluster
        anchors = self.db.query(PhysicalIssue).filter(
            PhysicalIssue.category == "Sanitation",
            PhysicalIssue.representative_latitude >= 16.10004 - 0.0001,
            PhysicalIssue.representative_latitude <= 16.10006 + 0.0001,
        ).all()
        self.assertEqual(len(anchors), 1, "Exactly one canonical anchor must be created despite split decimal rounding")

    def test_47_real_postgresql_concurrent_boundary_anchor_creation(self):
        """47. Genuine PostgreSQL integration test for boundary coordinates concurrency using isolated test database."""
        test_url = os.getenv("TEST_DATABASE_URL", "").strip() or os.getenv("POSTGRES_TEST_DATABASE_URL", "").strip()
        if not test_url or not test_url.startswith("postgres"):
            self.skipTest("Isolated PostgreSQL test database (TEST_DATABASE_URL) is not configured; skipping live PostgreSQL concurrency integration test.")

        # Never connect to production database
        if "production" in test_url.lower() or "prod" in test_url.lower():
            self.skipTest("TEST_DATABASE_URL appears to reference a production database; skipping live test for safety.")

        from app.database import Base
        from app.models.complaint import Complaint, PhysicalIssue, DuplicateMatch
        from app.services.duplicate_detection.duplicate_detector import DuplicateDetector
        from app.routes.duplicates import approve_match

        test_pg_engine = create_engine(test_url, pool_pre_ping=True, connect_args={"connect_timeout": 5})
        try:
            with test_pg_engine.connect() as probe:
                probe.execute(text("SELECT 1"))
        except Exception as conn_err:
            self.skipTest(f"Configured PostgreSQL test database unreachable: {conn_err}; skipping live integration test.")

        # Ensure schema on test database
        Base.metadata.create_all(bind=test_pg_engine)
        PgSessionFactory = sessionmaker(bind=test_pg_engine)

        session_cleanup = PgSessionFactory()
        try:
            # Clean test records for boundary coords
            session_cleanup.query(DuplicateMatch).delete()
            session_cleanup.query(Complaint).filter(Complaint.category == "Roads Boundary Test").delete()
            session_cleanup.query(PhysicalIssue).filter(PhysicalIssue.category == "Roads Boundary Test").delete()
            session_cleanup.commit()
        finally:
            session_cleanup.close()

        # Seed initial complaints across two independent sessions
        sess_init1 = PgSessionFactory()
        sess_init2 = PgSessionFactory()
        try:
            now_val = utc_now()
            c1 = Complaint(
                complaint_id="JS-2026-PG-TEST-01",
                citizen_id="cit-pg-01",
                category="Roads Boundary Test",
                latitude=16.10004,
                longitude=80.10004,
                description="Pothole at boundary 16.10004",
                address="Road Boundary A",
                current_status="Submitted",
                created_at=now_val,
                updated_at=now_val,
            )
            c2 = Complaint(
                complaint_id="JS-2026-PG-TEST-02",
                citizen_id="cit-pg-02",
                category="Roads Boundary Test",
                latitude=16.10006,
                longitude=80.10006,
                description="Pothole at boundary 16.10006",
                address="Road Boundary B",
                current_status="Submitted",
                created_at=now_val + datetime.timedelta(seconds=1),
                updated_at=now_val + datetime.timedelta(seconds=1),
            )
            sess_init1.add(c1)
            sess_init1.commit()
            sess_init2.add(c2)
            sess_init2.commit()
        finally:
            sess_init1.close()
            sess_init2.close()

        # Run concurrent anchor creation / evaluation using 2 separate sessions on genuine PostgreSQL
        def worker_evaluate(comp_id: str):
            w_session = PgSessionFactory()
            try:
                matches = DuplicateDetector.evaluate_complaint(comp_id, w_session, search_radius_meters=150.0)
                return [m.id for m in matches]
            finally:
                w_session.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            fut1 = executor.submit(worker_evaluate, "JS-2026-PG-TEST-01")
            fut2 = executor.submit(worker_evaluate, "JS-2026-PG-TEST-02")
            m_ids1 = fut1.result()
            m_ids2 = fut2.result()

        # Verify results on independent verification session
        verify_sess = PgSessionFactory()
        try:
            anchors = verify_sess.query(PhysicalIssue).filter(PhysicalIssue.category == "Roads Boundary Test").all()
            self.assertEqual(len(anchors), 1, "Exactly one canonical PhysicalIssue anchor must exist on PostgreSQL")
            canonical_ref = anchors[0].issue_reference_id

            comp_db1 = verify_sess.query(Complaint).filter_by(complaint_id="JS-2026-PG-TEST-01").first()
            comp_db2 = verify_sess.query(Complaint).filter_by(complaint_id="JS-2026-PG-TEST-02").first()

            # Confirm complaint independence: first is anchored, second remains unlinked pending human review
            self.assertEqual(comp_db1.issue_id, canonical_ref)
            self.assertIsNone(comp_db2.issue_id, "Subsequent complaint must NOT be silently auto-linked")

            # Subsequent complaint must have a pending DuplicateMatch
            pending_match = verify_sess.query(DuplicateMatch).filter_by(
                complaint_id="JS-2026-PG-TEST-02",
                physical_issue_id=canonical_ref
            ).first()
            self.assertIsNotNone(pending_match, "Pending DuplicateMatch must be recorded for human review")
            self.assertEqual(pending_match.review_status, "pending")

            # Verify that ONLY authority approval associates the complaint
            app_result = approve_match(
                match_id=pending_match.id,
                reviewer_id="Officer Postgres",
                review_reason="Verified duplicate on live PG",
                db=verify_sess
            )
            self.assertEqual(app_result["status"], "success")

            verify_sess.refresh(comp_db2)
            self.assertEqual(comp_db2.issue_id, canonical_ref, "Complaint must only be associated after authority approval")
        finally:
            verify_sess.close()

    def test_48_advisory_lock_released_immediately_on_existing_anchor_return(self):
        """48. When an existing anchor is found, read transaction is committed to release pg_advisory_xact_lock immediately."""
        from app.services.duplicate_detection.duplicate_detector import DuplicateDetector
        from app.models.complaint import PhysicalIssue

        # Pre-seed an existing PhysicalIssue anchor
        anchor_id = "ISSUE-2026-LOCK-REL-01"
        existing = PhysicalIssue(
            issue_reference_id=anchor_id,
            category="Streetlights",
            representative_latitude=16.3000,
            representative_longitude=80.3000,
            representative_location="16.3000, 80.3000",
            description="Existing streetlight cluster",
            current_status="Open",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self.db.add(existing)
        self.db.commit()

        # Create new complaint at the exact same location
        c_new = self._create_test_complaint(
            citizen_id="cit-lock-rel",
            category="Streetlights",
            lat=16.3000,
            lon=80.3000,
            desc="Another dark lamp near the cluster"
        )

        commit_count = 0
        real_commit = self.db.commit
        real_execute = self.db.execute

        def spy_commit():
            nonlocal commit_count
            commit_count += 1
            real_commit()

        def spy_execute(statement, *args, **kwargs):
            stmt_str = str(statement)
            if "pg_advisory_xact_lock" in stmt_str:
                return MagicMock()
            return real_execute(statement, *args, **kwargs)

        with patch("app.services.issue_id_service.get_verified_database_dialect", return_value="postgresql"):
            with patch.object(self.db, "execute", side_effect=spy_execute):
                with patch.object(self.db, "commit", side_effect=spy_commit):
                    # Call _create_provisional_anchor
                    returned_anchor = DuplicateDetector._create_provisional_anchor(c_new, self.db)

        # Confirm returned anchor is the pre-existing anchor
        self.assertEqual(returned_anchor.issue_reference_id, anchor_id)
        # Confirm complaint was NOT auto-linked
        self.assertIsNone(c_new.issue_id)

        # Crucial check: db.commit() MUST have been called by _release_read_lock_if_clean()
        # to terminate the read transaction and release pg_advisory_xact_lock in PostgreSQL!
        self.assertGreaterEqual(
            commit_count,
            1,
            "Expected db.commit() to be called on clean read transaction to release pg_advisory_xact_lock before returning"
        )


if __name__ == "__main__":
    unittest.main()
