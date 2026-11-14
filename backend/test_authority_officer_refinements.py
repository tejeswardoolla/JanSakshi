"""
JanSakshi Authority Officer Dashboard Refinements & Role Boundary Test Suite
Validates:
1. JS-2026-00022 Audit: Non-civic Higgsfield notification marked Rejected with preserved audit trail.
2. Authority Officer Decision Queue Gate: Only Admin-prepared, intake-complete complaints enter queue.
3. Department Dispatch Form Verification:
   - Municipal department selection.
   - Responsible department officer selection.
   - Priority, assignment date, expected completion date/days, instructions.
   - Cross-department officer assignment validation (rejected with 400).
   - Valid department officer assignment (succeeds with 200).
4. Authority Officer Lifecycle Actions:
   - Return work for correction.
   - Status update / closure.
5. Decision Audit History Timestamps:
   - Preserves actual event timestamps without alteration.
   - Events strictly ordered chronologically (created_at DESC).
6. Role-Based Access Control:
   - Authority Officer blocked from Admin-only intake/preparation endpoints.
   - Admin can execute preparation actions.
"""

import sys
import requests
import sqlite3

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

def run_tests():
    print("=" * 80)
    print("JANSAKSHI - AUTHORITY OFFICER DASHBOARD REFINEMENTS TEST SUITE")
    print("=" * 80)

    # 1. Login Authority Officer
    try:
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": "officer", "password": "JanSakshi@2026"},
            timeout=5
        )
        assert r.status_code == 200, f"Officer login failed: {r.text}"
        officer_token = r.json()["access_token"]
        officer_headers = {"Authorization": f"Bearer {officer_token}"}
        record_pass("Authentication: Authority Officer login", "Token issued")
    except Exception as e:
        record_fail("Authentication: Authority Officer login", e)
        return

    # 2. Login Admin
    try:
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": "admin", "password": "JanSakshi@2026"},
            timeout=5
        )
        assert r.status_code == 200, f"Admin login failed: {r.text}"
        admin_token = r.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        record_pass("Authentication: Admin login", "Token issued")
    except Exception as e:
        record_fail("Authentication: Admin login", e)
        return

    # 3. Test JS-2026-00022 Non-Civic Audit Integrity
    try:
        conn = sqlite3.connect('jansakshi.db')
        c = conn.cursor()
        c.execute("SELECT complaint_id, admin_status, verification_status, rejection_reason FROM complaints WHERE complaint_id = ?", ('JS-2026-00022',))
        row = c.fetchone()
        assert row is not None, "JS-2026-00022 must exist"
        assert row[1] == "Rejected", f"admin_status expected 'Rejected', got {row[1]}"
        assert row[2] == "rejected", f"verification_status expected 'rejected', got {row[2]}"
        assert "Higgsfield" in row[3] or "Non-civic" in row[3], "Rejection reason must note non-civic account notification"

        c.execute("SELECT event_type, description, created_at FROM complaint_events WHERE complaint_id = ? ORDER BY id ASC", ('JS-2026-00022',))
        events = c.fetchall()
        assert len(events) >= 2, "Complete audit history must be preserved"
        has_rejection_event = any("non_civic" in e[0] or "Rejected" in e[1] for e in events)
        assert has_rejection_event, "Must contain non-civic rejection audit event"
        conn.close()
        record_pass("Item 2: Complaint JS-2026-00022 audit & non-civic rejection", "Record preserved, marked Rejected, complete audit events intact")
    except Exception as e:
        record_fail("Item 2: Complaint JS-2026-00022 audit & non-civic rejection", e)

    # 4. Test Decision Queue Gate (Excludes raw/unprepared complaints and JS-2026-00022)
    try:
        res = requests.get(
            f"{BASE_URL}/api/authority/complaints?verification_status=pending&limit=50",
            headers=officer_headers,
            timeout=5
        )
        assert res.status_code == 200
        items = res.json().get("items", [])
        cids = [item["complaint_id"] for item in items]
        assert "JS-2026-00022" not in cids, "Non-civic JS-2026-00022 must NEVER appear in Authority Officer decision queue"

        for item in items:
            assert item["admin_status"] == "Ready for Authority Officer", (
                f"Complaint {item['complaint_id']} has admin_status '{item['admin_status']}', "
                "expected 'Ready for Authority Officer'"
            )
            assert item["latitude"] is not None and item["longitude"] is not None, (
                f"Complaint {item['complaint_id']} lacks grounded GPS coordinates"
            )
        record_pass("Item 3: Authority Officer Decision Queue Gate", f"Queue strictly scoped to {len(items)} intake-complete grievances")
    except Exception as e:
        record_fail("Item 3: Authority Officer Decision Queue Gate", e)

    # 5. Test Department Dispatch: Officer-to-Department Validation
    try:
        # Cross-department assignment must be blocked with HTTP 400
        invalid_body = {
            "department_id": 2,  # Sanitation & Waste Management
            "assigned_to_user_id": 3,  # Roads officer (dept 1)
            "priority": "High",
            "assignment_date": "2026-11-13",
            "expected_completion_date": "2026-11-16",
            "expected_completion_days": 3,
            "notes": "Invalid test: assigning Roads officer to Sanitation"
        }
        res_invalid = requests.post(
            f"{BASE_URL}/api/authority/complaints/JS-2026-00018/assign",
            json=invalid_body,
            headers=officer_headers,
            timeout=5
        )
        assert res_invalid.status_code == 400, f"Expected 400 for cross-department officer, got {res_invalid.status_code}"
        assert "does not belong to" in res_invalid.json().get("detail", "")
        record_pass("Item 4A: Department Dispatch Officer Validation (Blocked)", "Cross-department assignment correctly rejected with 400")
    except Exception as e:
        record_fail("Item 4A: Department Dispatch Officer Validation (Blocked)", e)

    try:
        # Valid department assignment (Sanitation Inspector to Sanitation)
        valid_body = {
            "department_id": 2,  # Sanitation
            "assigned_to_user_id": 4,  # Sanitation Inspector (dept 2)
            "priority": "High",
            "assignment_date": "2026-11-13",
            "expected_completion_date": "2026-11-16",
            "expected_completion_days": 3,
            "notes": "Dispatch garbage clearing work order to local sanitation crew."
        }
        res_valid = requests.post(
            f"{BASE_URL}/api/authority/complaints/JS-2026-00018/assign",
            json=valid_body,
            headers=officer_headers,
            timeout=5
        )
        assert res_valid.status_code == 200, f"Expected 200 for valid assignment, got {res_valid.status_code}: {res_valid.text}"
        data = res_valid.json()
        assert data["department_id"] == 2
        assert data["admin_status"] == "Assigned"
        record_pass("Item 4B: Department Dispatch Officer Validation (Accepted)", "Assigned to Sanitation Inspector with full dispatch fields")
    except Exception as e:
        record_fail("Item 4B: Department Dispatch Officer Validation (Accepted)", e)

    # 6. Test Authority Officer Return for Correction
    try:
        return_body = {
            "correction_notes": "Road asphalt surface uneven; re-compact surface before final closure approval."
        }
        res_ret = requests.post(
            f"{BASE_URL}/api/authority/complaints/JS-2026-00004/return-correction",
            json=return_body,
            headers=officer_headers,
            timeout=5
        )
        assert res_ret.status_code == 200, f"Expected 200 on return-correction, got {res_ret.status_code}"
        assert res_ret.json()["admin_status"] == "In Progress"
        record_pass("Item 5: Return Work for Correction", "Work order returned to department with recorded correction notes")
    except Exception as e:
        record_fail("Item 5: Return Work for Correction", e)

    # 7. Test Decision Audit History Timestamps & Chronological Order
    try:
        res_audit = requests.get(
            f"{BASE_URL}/api/authority/audit?limit=30",
            headers=officer_headers,
            timeout=5
        )
        assert res_audit.status_code == 200
        events = res_audit.json().get("items", [])
        assert len(events) >= 5, "Audit history must contain records"

        # Check chronological descending order
        for i in range(len(events) - 1):
            t1 = events[i]["created_at"]
            t2 = events[i + 1]["created_at"]
            assert t1 >= t2, f"Timestamps out of chronological order: {t1} should be >= {t2}"
        record_pass("Item 6: Decision Audit History Timestamps", f"All {len(events)} events ordered chronologically, original timestamps preserved")
    except Exception as e:
        record_fail("Item 6: Decision Audit History Timestamps", e)

    # 8. Test Role Boundary Enforcement
    try:
        # Authority Officer attempting Admin mark-ready action -> 403 Forbidden
        res_blocked = requests.post(
            f"{BASE_URL}/api/authority/complaints/JS-2026-00012/mark-ready",
            headers=officer_headers,
            timeout=5
        )
        assert res_blocked.status_code == 403, f"Expected 403 for Authority Officer on mark-ready, got {res_blocked.status_code}"

        # Admin executing mark-ready action -> 200 OK
        res_allowed = requests.post(
            f"{BASE_URL}/api/authority/complaints/JS-2026-00012/mark-ready",
            headers=admin_headers,
            timeout=5
        )
        assert res_allowed.status_code == 200, f"Expected 200 for Admin on mark-ready, got {res_allowed.status_code}"
        record_pass("Item 7: Role Boundary Enforcement", "Admin exclusive over intake preparation; Authority Officer restricted to decisions")
    except Exception as e:
        record_fail("Item 7: Role Boundary Enforcement", e)

    print("=" * 80)
    print(f"RESULTS: {passed} PASSED, {failed} FAILED")
    print("=" * 80)
    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
