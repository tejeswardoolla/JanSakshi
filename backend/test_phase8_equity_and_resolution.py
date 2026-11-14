"""
JanSakshi Phase 8 Comprehensive Test Suite
Equity-Aware Civic Intelligence & Evidence-Based Resolution Verification
Tests:
1. Admin full equity management & overview
2. Grounded ward breakdown, data quality, and distinct metrics
3. Statistical sample size audit (n < 5 flagged, no premature disparity conclusions)
4. Authority Officer read-only decision support access
5. Authority Officer blocked from admin equity management (403 Forbidden)
6. Department Officer division isolation (403 Forbidden on cross-department)
7. Department Officer field resolution submission (v1)
8. Department Officer blocked from approving resolution (403 Forbidden)
9. Authority Officer review queue and side-by-side inspection
10. Authority Officer return for correction with mandatory instructions
11. Department Officer versioned resubmission (v2 incremented)
12. Authority Officer final approval and official ticket closure
"""

import sys
import time
import requests

BASE_URL = "http://127.0.0.1:8000"

passed = 0
failed = 0

def record_pass(test_name, details=""):
    global passed
    passed += 1
    print(f"✅ PASS | {test_name}")
    if details:
        print(f"      {details}")

def record_fail(test_name, err):
    global failed
    failed += 1
    print(f"❌ FAIL | {test_name}: {err}")


def run_phase8_tests():
    print("=" * 80)
    print("JANSAKSHI - PHASE 8: EQUITY INTELLIGENCE & RESOLUTION VERIFICATION TESTS")
    print("=" * 80)

    # Ensure backend is up
    for attempt in range(5):
        try:
            r = requests.get(f"{BASE_URL}/", timeout=3)
            if r.status_code == 200:
                break
        except Exception:
            time.sleep(1)

    # ----------------------------------------------------
    # TEST 1: Admin Authentication & Full Equity Overview
    # ----------------------------------------------------
    try:
        login_res = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": "admin", "password": "JanSakshi@2026"},
            timeout=5
        )
        assert login_res.status_code == 200, f"Admin login failed: {login_res.text}"
        admin_token = login_res.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        record_pass("Authentication: Admin login succeeds", "Bearer token issued for admin")
    except Exception as e:
        record_fail("Authentication: Admin login succeeds", e)
        return

    try:
        res = requests.get(f"{BASE_URL}/api/authority/equity/overview?days=30", headers=admin_headers, timeout=5)
        assert res.status_code == 200, f"Status: {res.status_code} - {res.text}"
        data = res.json()
        assert "summary" in data and "areas" in data and "department_coverage" in data and "recommendations" in data
        assert data.get("role_access") == "admin"
        assert data.get("permissions", {}).get("can_manage_equity") is True
        summary = data["summary"]
        assert summary["total_areas"] >= 1
        assert summary["total_complaints"] >= 1
        record_pass(
            "Phase 8.2: Admin Full Equity Intelligence Overview",
            f"Role: {data.get('role_access')} | Total Areas: {summary['total_areas']} | Total Grievances: {summary['total_complaints']} | Attention: {summary['areas_requiring_attention']}"
        )
    except Exception as e:
        record_fail("Phase 8.2: Admin Full Equity Intelligence Overview", e)

    # ----------------------------------------------------
    # TEST 2: Metric Reliability & Statistical Sample Audit
    # ----------------------------------------------------
    try:
        areas = data["areas"]
        assert len(areas) >= 1
        insufficient_count = 0
        for a in areas:
            assert "unresolved_rate" in a
            assert "resolution_rate" in a
            assert "sla_breach_rate" in a
            assert "denominators" in a
            assert "is_insufficient_sample" in a
            # Verify distinct rates: unresolved + resolution rate add up properly
            assert a["unresolved_count"] + a["resolved_count"] <= a["total_complaints"]
            if a["total_complaints"] < 5:
                assert a["is_insufficient_sample"] is True, f"Ward {a['area_name']} with n={a['total_complaints']} must be marked insufficient sample"
                assert "Insufficient Sample" in a["indicators"][0]
                insufficient_count += 1
            else:
                assert a["is_insufficient_sample"] is False

        record_pass(
            "Phase 8.2: Metric Reliability & Statistical Sample Size Validation",
            f"Audited {len(areas)} wards | Distinct rates verified | {insufficient_count} low-sample wards (n < 5) safely flagged against premature disparity claims"
        )
    except Exception as e:
        record_fail("Phase 8.2: Metric Reliability & Statistical Sample Size Validation", e)

    # ----------------------------------------------------
    # TEST 3: Department Coverage & Explainable Recommendations
    # ----------------------------------------------------
    try:
        dept_cov = data["department_coverage"]
        assert len(dept_cov) >= 1
        recs = data["recommendations"]
        assert isinstance(recs, list)
        for r in recs:
            assert "neutral_label" in r
            assert "evidence_basis" in r
        record_pass(
            "Phase 8.2: Department Coverage & Explainable Recommendations",
            f"Departments audited: {len(dept_cov)} | Recommendations generated: {len(recs)}"
        )
    except Exception as e:
        record_fail("Phase 8.2: Department Coverage & Explainable Recommendations", e)

    # ----------------------------------------------------
    # TEST 4: Authority Officer Read-Only Parity Access
    # ----------------------------------------------------
    try:
        auth_res = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "officer", "password": "JanSakshi@2026"}, timeout=5)
        assert auth_res.status_code == 200
        auth_token = auth_res.json()["access_token"]
        auth_headers = {"Authorization": f"Bearer {auth_token}"}

        auth_equity = requests.get(f"{BASE_URL}/api/authority/equity/overview?days=30", headers=auth_headers, timeout=5)
        assert auth_equity.status_code == 200
        auth_data = auth_equity.json()
        assert auth_data.get("role_access") == "authority_officer"
        assert auth_data.get("permissions", {}).get("can_manage_equity") is False
        assert "authority_guidance" in auth_data
        record_pass(
            "Phase 8.2: RBAC - Authority Officer granted Read-Only Decision Context",
            f"Role: {auth_data.get('role_access')} | Manage Equity: {auth_data.get('permissions', {}).get('can_manage_equity')} | Guidance attached"
        )
    except Exception as e:
        record_fail("Phase 8.2: RBAC - Authority Officer granted Read-Only Decision Context", e)

    # ----------------------------------------------------
    # TEST 5: RBAC - Authority Officer Blocked from Admin Recalculation
    # ----------------------------------------------------
    try:
        recalc_attempt = requests.post(f"{BASE_URL}/api/authority/equity/recalculate-clusters", headers=auth_headers, timeout=5)
        assert recalc_attempt.status_code == 403, f"Expected 403, got {recalc_attempt.status_code}"
        record_pass(
            "Phase 8.2: RBAC - Authority Officer strictly blocked from Admin cluster recalculation",
            f"Blocked with HTTP {recalc_attempt.status_code} Forbidden as designed"
        )
    except Exception as e:
        record_fail("Phase 8.2: RBAC - Authority Officer strictly blocked from Admin cluster recalculation", e)

    # ----------------------------------------------------
    # TEST 6: Department Officer Division Scoping & Cross-Dept Protection
    # ----------------------------------------------------
    try:
        dept_res = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "roads_officer", "password": "JanSakshi@2026"}, timeout=5)
        assert dept_res.status_code == 200
        dept_token = dept_res.json()["access_token"]
        dept_headers = {"Authorization": f"Bearer {dept_token}"}

        # Query own department (1) -> succeeds
        own_res = requests.get(f"{BASE_URL}/api/authority/equity/overview?department_id=1", headers=dept_headers, timeout=5)
        assert own_res.status_code == 200
        assert own_res.json().get("role_access") == "department_officer"

        # Query other department (2) -> 403 Forbidden
        other_res = requests.get(f"{BASE_URL}/api/authority/equity/overview?department_id=2", headers=dept_headers, timeout=5)
        assert other_res.status_code == 403, f"Expected 403, got {other_res.status_code}"

        record_pass(
            "Phase 8.2: RBAC - Department Officer strictly scoped to authorized division",
            f"Department 1 query: 200 OK | Department 2 cross-query: HTTP {other_res.status_code} Forbidden"
        )
    except Exception as e:
        record_fail("Phase 8.2: RBAC - Department Officer strictly scoped to authorized division", e)

    # ----------------------------------------------------
    # TEST 7: Department Officer Submits Field Resolution Dossier
    # ----------------------------------------------------
    try:
        cid = "JS-2026-00001"
        sub_payload = {
            "work_description": "Resurfaced damaged asphalt section on Inner Ring Road.",
            "repair_action_taken": "Excavated loose road debris, applied bituminous tack coat, compacted hot mix asphalt.",
            "materials_used": "Bitumen emulsion, 40mm aggregate, roller",
            "field_notes": "Road restored to smooth grade. Traffic moving normally.",
            "after_photo_urls": ["/assets/dept_rpw.jpg"]
        }
        sub_res = requests.post(f"{BASE_URL}/api/authority/complaints/{cid}/resolution/submit", json=sub_payload, headers=dept_headers, timeout=5)
        assert sub_res.status_code == 201, f"Failed: {sub_res.text}"
        sub_data = sub_res.json()
        sub_id = sub_data["id"]
        assert sub_data["status"] == "submitted"
        assert sub_data["version_number"] >= 1
        record_pass(
            "Phase 8.4: Department Officer submits field resolution dossier",
            f"Submission ID: {sub_id} | Version: {sub_data['version_number']} | Status: {sub_data['status']}"
        )
    except Exception as e:
        record_fail("Phase 8.4: Department Officer submits field resolution dossier", e)

    # ----------------------------------------------------
    # TEST 8: RBAC - Department Officer CANNOT close complaint
    # ----------------------------------------------------
    try:
        forbidden = requests.post(
            f"{BASE_URL}/api/authority/resolutions/{sub_id}/approve",
            json={"verification_notes": "Self approval attempt"},
            headers=dept_headers,
            timeout=5
        )
        assert forbidden.status_code in [401, 403], f"Expected 403, got {forbidden.status_code}"
        record_pass(
            "Phase 8.4: RBAC Enforcement - Department Officer blocked from approving resolution",
            f"Blocked with HTTP {forbidden.status_code} Forbidden as designed"
        )
    except Exception as e:
        record_fail("Phase 8.4: RBAC Enforcement - Department Officer blocked from approving resolution", e)

    # ----------------------------------------------------
    # TEST 9: Authority Officer Verification Queue & Detail
    # ----------------------------------------------------
    try:
        q_res = requests.get(f"{BASE_URL}/api/authority/resolutions/queue?status=submitted", headers=auth_headers, timeout=5)
        assert q_res.status_code == 200
        items = q_res.json().get("items", [])
        matched = [item for item in items if item["id"] == sub_id]
        assert len(matched) == 1, "Submission not found in review queue"

        det_res = requests.get(f"{BASE_URL}/api/authority/resolutions/{sub_id}", headers=auth_headers, timeout=5)
        assert det_res.status_code == 200
        det_data = det_res.json()
        assert det_data["complaint"]["complaint_id"] == cid
        record_pass(
            "Phase 8.4: Authority Officer views verification queue and detailed comparison dossier",
            f"Queue items: {len(items)} | Detail matched complaint: {cid}"
        )
    except Exception as e:
        record_fail("Phase 8.4: Authority Officer views verification queue and detailed comparison dossier", e)

    # ----------------------------------------------------
    # TEST 10: Return for Correction (Mandatory Reason)
    # ----------------------------------------------------
    try:
        # Empty reason fails
        empty_res = requests.post(
            f"{BASE_URL}/api/authority/resolutions/{sub_id}/return",
            json={"rejection_reason": "   "},
            headers=auth_headers,
            timeout=5
        )
        assert empty_res.status_code in [400, 422]

        # Valid reason succeeds
        ret_res = requests.post(
            f"{BASE_URL}/api/authority/resolutions/{sub_id}/return",
            json={"rejection_reason": "Perimeter joint not sealed properly. Please tamp asphalt edge and re-submit."},
            headers=auth_headers,
            timeout=5
        )
        assert ret_res.status_code == 200
        ret_data = ret_res.json()
        assert ret_data["admin_status"] == "Returned for Correction"

        # Check complaint status
        c_check = requests.get(f"{BASE_URL}/api/authority/complaints/{cid}", headers=auth_headers, timeout=5)
        assert c_check.json()["admin_status"] == "Returned for Correction"

        record_pass(
            "Phase 8.4: Authority Officer returns dossier with mandatory correction reason",
            f"Complaint admin_status: Returned for Correction"
        )
    except Exception as e:
        record_fail("Phase 8.4: Authority Officer returns dossier with mandatory correction reason", e)

    # ----------------------------------------------------
    # TEST 11: Versioned Resubmission by Department Officer
    # ----------------------------------------------------
    try:
        v2_payload = {
            "work_description": "Perimeter joint sealed and leveled with asphalt.",
            "repair_action_taken": "Tamped perimeter, applied secondary bitumen coat.",
            "materials_used": "Bitumen joint sealant, compactor",
            "field_notes": "Edges fully sealed.",
            "after_photo_urls": ["/assets/dept_rpw.jpg"]
        }
        v2_res = requests.post(f"{BASE_URL}/api/authority/complaints/{cid}/resolution/submit", json=v2_payload, headers=dept_headers, timeout=5)
        assert v2_res.status_code == 201
        v2_data = v2_res.json()
        v2_id = v2_data["id"]
        assert v2_data["version_number"] == sub_data["version_number"] + 1
        record_pass(
            "Phase 8.4: Department Officer submits Version 2 correction",
            f"New Submission ID: {v2_id} | Version: {v2_data['version_number']} (Incremented)"
        )
    except Exception as e:
        record_fail("Phase 8.4: Department Officer submits Version 2 correction", e)

    # ----------------------------------------------------
    # TEST 12: Authority Officer Final Approval & Closure
    # ----------------------------------------------------
    try:
        app_res = requests.post(
            f"{BASE_URL}/api/authority/resolutions/{v2_id}/approve",
            json={"verification_notes": "Photographic evidence re-inspected. Compaction and sealing verified."},
            headers=auth_headers,
            timeout=5
        )
        assert app_res.status_code == 200
        app_data = app_res.json()
        assert app_data["admin_status"] == "Closed"

        # Verify Complaint is officially Closed
        final_check = requests.get(f"{BASE_URL}/api/authority/complaints/{cid}", headers=auth_headers, timeout=5)
        assert final_check.status_code == 200
        final_json = final_check.json()
        assert final_json["admin_status"] == "Closed"
        assert final_json["status"] in ["Closed", "Resolved"]
        record_pass(
            "Phase 8.4: Authority Officer approves evidence and officially marks complaint Closed",
            f"Final Admin Status: {final_json['admin_status']} | Public Status: {final_json['status']}"
        )
    except Exception as e:
        record_fail("Phase 8.4: Authority Officer approves evidence and officially marks complaint Closed", e)

    print("=" * 80)
    print(f"RESULTS: {passed} PASSED | {failed} FAILED")
    print("=" * 80)
    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    run_phase8_tests()
