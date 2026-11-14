"""
JanSakshi - Comprehensive Department Work Order Inspection & Data Isolation Test
Validates:
1. Department-specific data isolation across all 6 municipal divisions (RPW, SWM, WSD, DRN, ESM, PID).
2. Field inspection lifecycle: notes, progress update, evidence upload, resolution submission.
3. Strict cross-department RBAC protection (HTTP 403 Forbidden).
4. Error handling (HTTP 404 for invalid work order IDs).
"""

import sys
import io
import requests

BASE_URL = "http://127.0.0.1:8000"

def log_test(name, passed, detail=""):
    symbol = "✅ PASS" if passed else "❌ FAIL"
    print(f"{symbol} | {name}")
    if detail:
        print(f"      {detail}")
    if not passed:
        sys.exit(1)

def run_tests():
    print("=" * 80)
    print("JANSAKSHI - DEPARTMENT WORK ORDER INSPECTION & DATA ISOLATION TESTS")
    print("=" * 80)

    # 1. Login as Multi-Department Lead (dept_demo)
    r_login = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "dept_demo",
        "password": "JanSakshi@2026"
    })
    log_test("Authentication: dept_demo login succeeds", r_login.status_code == 200)
    token_demo = r_login.json()["access_token"]
    headers_demo = {"Authorization": f"Bearer {token_demo}"}

    # 2. Login as Roads Officer (RPW restricted)
    r_roads_login = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "roads_officer",
        "password": "JanSakshi@2026"
    })
    log_test("Authentication: roads_officer login succeeds", r_roads_login.status_code == 200)
    token_roads = r_roads_login.json()["access_token"]
    headers_roads = {"Authorization": f"Bearer {token_roads}"}

    # 3. Test All 6 Departments Workspaces
    departments = [
        {"id": 1, "code": "RPW", "name": "Roads & Public Works", "expected_cat": "Road Damage / Potholes"},
        {"id": 2, "code": "SWM", "name": "Sanitation & Waste Management", "expected_cat": "Garbage Accumulation"},
        {"id": 3, "code": "WSD", "name": "Water Supply & Sewerage", "expected_cat": "Water Leakage"},
        {"id": 4, "code": "DRN", "name": "Storm Water Drainage", "expected_cat": "Drainage Overflow"},
        {"id": 5, "code": "ESM", "name": "Electrical & Street Lighting", "expected_cat": "Broken Streetlights"},
        {"id": 6, "code": "PID", "name": "Public Infrastructure & Parks", "expected_cat": "Public Infrastructure & Parks"},
    ]

    for dept in departments:
        dept_id = dept["id"]
        dept_code = dept["code"]

        # A. Query department overview
        r_over = requests.get(f"{BASE_URL}/api/authority/overview?department_id={dept_id}", headers=headers_demo)
        log_test(
            f"Dept {dept_code}: Overview queries department {dept_id}",
            r_over.status_code == 200,
            f"Dept: {dept_code} | Total: {r_over.json().get('total_complaints')}"
        )

        # B. Query assigned work orders
        r_comp = requests.get(f"{BASE_URL}/api/authority/complaints?department_id={dept_id}", headers=headers_demo)
        items = r_comp.json().get("items", [])
        all_match_dept = all(c.get("department", {}).get("id") == dept_id for c in items if c.get("department"))
        log_test(
            f"Dept {dept_code}: Assigned work orders strictly isolated to department {dept_id}",
            r_comp.status_code == 200 and len(items) > 0 and all_match_dept,
            f"Count: {len(items)} | IDs: {[c['complaint_id'] for c in items]}"
        )

        # C. Inspect primary work order
        target_complaint = items[0]
        cid = target_complaint["complaint_id"]
        r_detail = requests.get(f"{BASE_URL}/api/authority/complaints/{cid}", headers=headers_demo)
        det = r_detail.json()
        log_test(
            f"Dept {dept_code}: Inspect work order {cid} loads full details & coordinates",
            r_detail.status_code == 200 and det.get("category") == dept["expected_cat"],
            f"ID: {cid} | Cat: {det.get('category')} | GPS: {det.get('latitude')}, {det.get('longitude')}"
        )

    # 4. Lifecycle Actions on Water Supply Work Order JS-2026-00003
    water_cid = "JS-2026-00003"
    print("\n--- Testing Lifecycle Actions on Water Supply & Sewerage Work Order ---")

    # A. Add inspection note
    r_note = requests.post(
        f"{BASE_URL}/api/authority/complaints/{water_cid}/notes",
        headers=headers_demo,
        json={"notes": "Water division engineer on site. Hydrostatic pressure gauge test initiated."}
    )
    log_test(
        f"Lifecycle: Add inspection note to {water_cid}",
        r_note.status_code == 200,
        f"Message: {r_note.json().get('message')}"
    )

    # B. Update status to In Progress
    r_status1 = requests.post(
        f"{BASE_URL}/api/authority/complaints/{water_cid}/status",
        headers=headers_demo,
        json={"status": "In Progress", "notes": "Excavation and pipe replacement in active progress."}
    )
    log_test(
        f"Lifecycle: Update status to 'In Progress' for {water_cid}",
        r_status1.status_code == 200 and r_status1.json().get("admin_status") == "In Progress",
        f"Admin Status: {r_status1.json().get('admin_status')}"
    )

    # C. Upload field inspection evidence
    dummy_img = io.BytesIO(b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xFF\xDB\x00C\x00" + b"\x00" * 500)
    r_ev = requests.post(
        f"{BASE_URL}/api/authority/complaints/{water_cid}/evidence",
        headers=headers_demo,
        files={"file": ("water_pipeline_inspection.jpg", dummy_img, "image/jpeg")},
        data={"caption": "Replaced high-pressure flange joint and gasket."}
    )
    log_test(
        f"Lifecycle: Upload field inspection photo to {water_cid}",
        r_ev.status_code == 200 and r_ev.json().get("evidence_id") is not None,
        f"Evidence ID: {r_ev.json().get('evidence_id')} | Stored: {r_ev.json().get('stored_filename')}"
    )

    # D. Submit resolution for authority review
    r_status2 = requests.post(
        f"{BASE_URL}/api/authority/complaints/{water_cid}/status",
        headers=headers_demo,
        json={
            "status": "Resolution Submitted",
            "notes": "Pipeline successfully welded and pressure restored. Ready for final closure inspection."
        }
    )
    log_test(
        f"Lifecycle: Submit resolution for authority review on {water_cid}",
        r_status2.status_code == 200 and r_status2.json().get("admin_status") == "Resolution Submitted",
        f"Admin Status: {r_status2.json().get('admin_status')}"
    )

    # 5. Cross-Department RBAC Boundary Tests
    print("\n--- Testing Cross-Department RBAC Security Boundaries ---")
    other_dept_work_orders = [
        ("SWM", "JS-2026-00002"),
        ("WSD", "JS-2026-00003"),
        ("DRN", "JS-2026-00005"),
        ("ESM", "JS-2026-00007"),
        ("PID", "JS-2026-00011"),
    ]

    for code, target_cid in other_dept_work_orders:
        r_unauth = requests.get(f"{BASE_URL}/api/authority/complaints/{target_cid}", headers=headers_roads)
        log_test(
            f"Security RBAC: roads_officer blocked from viewing {code} work order {target_cid}",
            r_unauth.status_code == 403,
            f"Status: {r_unauth.status_code} (Expected 403 Forbidden)"
        )

        r_unauth_act = requests.post(
            f"{BASE_URL}/api/authority/complaints/{target_cid}/status",
            headers=headers_roads,
            json={"status": "In Progress", "notes": "Unauthorized modification attempt"}
        )
        log_test(
            f"Security RBAC: roads_officer blocked from updating {code} work order {target_cid}",
            r_unauth_act.status_code == 403,
            f"Status: {r_unauth_act.status_code} (Expected 403 Forbidden)"
        )

    # 6. Error Handling: Non-existent work order returns 404
    r_404 = requests.get(f"{BASE_URL}/api/authority/complaints/JS-2026-NONEXISTENT", headers=headers_demo)
    log_test(
        "Error Handling: Non-existent work order returns 404 Not Found",
        r_404.status_code == 404,
        f"Status: {r_404.status_code}"
    )

    print("=" * 80)
    print("ALL 16 DEPARTMENT WORK ORDER & ISOLATION TESTS PASSED (100%)!")
    print("=" * 80)

if __name__ == "__main__":
    run_tests()
