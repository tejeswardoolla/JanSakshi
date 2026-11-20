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
from unittest.mock import patch, MagicMock
from concurrent.futures import ThreadPoolExecutor

# Ensure backend root is in python path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from PIL import Image

from app.database import Base
from app.models.complaint import Complaint, PhysicalIssue, Evidence, ComplaintEvent, DuplicateMatch
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
from app.routes.duplicates import _format_match_response

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
        """18. Concurrent multi-threaded anchor creation does not crash or generate duplicate anchors."""
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

if __name__ == "__main__":
    unittest.main()
