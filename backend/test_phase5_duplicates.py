"""
JanSakshi Phase 5 Automated Verification Suite
Tests the Multi-Signal Duplicate Detection Engine, Dynamic Normalization,
Candidate Retrieval, and Human Review Workflow.
"""

import sys
import os
import requests

BACKEND_URL = "http://127.0.0.1:8000"

def log(msg: str):
    print(f"[TEST] {msg}")

def assert_true(cond: bool, msg: str):
    if not cond:
        print(f"❌ ASSERTION FAILED: {msg}")
        sys.exit(1)
    print(f"✅ {msg}")

def run_tests():
    log("Starting Phase 5 Duplicate Detection Verification...")

    # 1. Health check
    res = requests.get(f"{BACKEND_URL}/api/health")
    assert_true(res.status_code == 200, "Backend health endpoint returns 200")
    data = res.json()
    assert_true(data.get("phase") in (5, 6), "Backend version is Phase 5 or 6")

    # 2. Test Unit Logic (Location, Text, Category, Scoring)
    from app.services.duplicate_detection.location_similarity import (
        calculate_haversine_distance,
        calculate_location_similarity,
    )
    from app.services.duplicate_detection.category_similarity import calculate_category_similarity
    from app.services.duplicate_detection.text_similarity import calculate_text_similarity
    from app.services.duplicate_detection.scoring import compute_composite_score

    # Geodesic distance test: two points in Hyderabad approx 25m apart
    d = calculate_haversine_distance(17.385044, 78.486671, 17.385200, 78.486800)
    assert_true(10.0 <= d <= 35.0, f"Haversine calculation accurate ({d:.2f}m)")

    # Location similarity decay
    sim_0m = calculate_location_similarity(0.0)
    assert_true(sim_0m == 1.0, "0m distance produces 1.0 similarity")
    sim_20m = calculate_location_similarity(20.0)
    assert_true(0.70 <= sim_20m <= 0.99, f"20m distance produces high similarity ({sim_20m})")
    sim_200m = calculate_location_similarity(200.0)
    assert_true(sim_200m == 0.0, "200m distance decays to 0.0")

    # Category similarity
    assert_true(calculate_category_similarity("Road Damage / Potholes", "Road Damage / Potholes") == 1.0, "Exact category match = 1.0")
    cat_compat = calculate_category_similarity("Drainage Overflow", "Water Leakage")
    assert_true(cat_compat == 0.50, f"Compatible civic category pair = 0.50 ({cat_compat})")
    cat_incompat = calculate_category_similarity("Broken Streetlights", "Garbage Accumulation")
    assert_true(cat_incompat == 0.0, "Incompatible categories = 0.0")

    # Text similarity
    text_exact = calculate_text_similarity("Massive pothole near main gate", "Massive pothole near main gate")
    assert_true(text_exact == 1.0, "Identical text = 1.0")
    text_close = calculate_text_similarity("Deep pothole on main road near school gate", "Dangerous pot hole on main road near school")
    assert_true(text_close is not None and text_close >= 0.50, f"Semantic overlap gives high similarity ({text_close})")
    text_diff = calculate_text_similarity("Deep pothole on road", "Streetlight not turning on at night")
    assert_true(text_diff is not None and text_diff < 0.20, f"Different civic issue text gives low similarity ({text_diff})")

    # Dynamic Weight Normalization (Missing image signal)
    score_all = compute_composite_score(gps_score=0.95, distance_meters=8.0, text_score=0.85, image_score=0.90, category_score=1.0)
    assert_true(score_all["confidence_level"] == "high", f"Full signals high confidence: {score_all['similarity_score']}")

    score_no_img = compute_composite_score(gps_score=0.95, distance_meters=8.0, text_score=0.85, image_score=None, category_score=1.0)
    assert_true(score_no_img["similarity_score"] >= 0.85, f"Missing image gracefully normalized without zero penalty: {score_no_img['similarity_score']}")
    assert_true("Visual comparison skipped" in score_no_img["matching_explanation"] or "Visual: N/A" in score_no_img["matching_explanation"], "Explanation documents missing visual signal")

    # Discrepancy warning test
    score_discrepancy = compute_composite_score(gps_score=0.98, distance_meters=5.0, text_score=0.10, image_score=None, category_score=0.0)
    assert_true("Geographically close" in score_discrepancy["warning_signals"], "Warning generated for close GPS but incompatible categories")

    # 3. Test API Duplicate Flow with Database
    from app.database import SessionLocal
    from app.models.complaint import Complaint, PhysicalIssue, DuplicateMatch
    from app.services.duplicate_detection import DuplicateDetector

    db = SessionLocal()
    try:
        # Check an existing complaint
        first_comp = db.query(Complaint).order_by(Complaint.id.asc()).first()
        assert_true(first_comp is not None, f"Found existing complaint: {first_comp.complaint_id}")

        # Check existing PhysicalIssues
        issues = db.query(PhysicalIssue).all()
        log(f"Existing physical issues count: {len(issues)}")

        # Run duplicate detection retry endpoint on first_comp
        res_dup = requests.post(f"{BACKEND_URL}/api/duplicates/complaints/{first_comp.complaint_id}/retry?search_radius_meters=500000.0")
        assert_true(res_dup.status_code == 200, f"Duplicate detection retry succeeded: status {res_dup.status_code}")
        candidates = res_dup.json()
        log(f"Detected {len(candidates)} candidate matches for {first_comp.complaint_id}")

        # Query Review Queue
        res_queue = requests.get(f"{BACKEND_URL}/api/duplicates/review-queue?status=all")
        assert_true(res_queue.status_code == 200, "Review queue endpoint returned 200")
        queue_items = res_queue.json()
        log(f"Review queue total items: {len(queue_items)}")

        # Test Track Complaint includes duplicate matches and issue info
        res_track = requests.get(f"{BACKEND_URL}/api/complaints/{first_comp.complaint_id}")
        assert_true(res_track.status_code == 200, "Track complaint endpoint returned 200")
        track_data = res_track.json()
        assert_true("duplicate_matches" in track_data, "Track response contains duplicate_matches field")
        log(f"Track complaint duplicate_matches count: {len(track_data['duplicate_matches'])}")

        # If we have at least one match, test approve and reject workflow
        if candidates:
            test_match = candidates[0]
            match_id = test_match["id"]

            # Test Reject
            res_reject = requests.post(
                f"{BACKEND_URL}/api/duplicates/matches/{match_id}/reject",
                json={"reviewer_id": "test_officer", "review_reason": "Automated verification test rejection"}
            )
            assert_true(res_reject.status_code == 200, "Reject match endpoint returned 200")
            assert_true(res_reject.json()["review_status"] == "rejected", "Match status updated to rejected")

            # Test Approve
            res_approve = requests.post(
                f"{BACKEND_URL}/api/duplicates/matches/{match_id}/approve",
                json={"reviewer_id": "test_officer", "review_reason": "Automated verification test approval"}
            )
            assert_true(res_approve.status_code == 200, "Approve match endpoint returned 200")
            assert_true(res_approve.json()["review_status"] == "approved", "Match status updated to approved")

            # Verify complaint is linked without destroying citizen metadata
            db.expire_all()
            comp_after = db.query(Complaint).filter(Complaint.complaint_id == test_match["complaint_id"]).first()
            assert_true(comp_after.issue_id == test_match["candidate_physical_issue_id"], "Complaint issue_id correctly linked to physical issue")
            assert_true(comp_after.description == first_comp.description, "Complaint original description preserved")
            assert_true(comp_after.latitude == first_comp.latitude, "Complaint original latitude preserved")
            assert_true(comp_after.longitude == first_comp.longitude, "Complaint original longitude preserved")

    finally:
        db.close()

    print("\n🎉 ALL PHASE 5 DUPLICATE DETECTION TESTS PASSED SUCCESSFULLY! 🎉\n")

if __name__ == "__main__":
    run_tests()
