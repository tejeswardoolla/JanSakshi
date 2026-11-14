"""
JanSakshi - Department Selection Experience & Multi-Division Security Tests
Verifies:
1. Department selection endpoint returns all 6 departments with live ticket counts.
2. dept_demo account has explicit access to all 6 departments.
3. roads_officer account is strictly restricted to RPW (1) only.
4. Unauthorized cross-department queries by roads_officer are rejected with 403 Forbidden.
5. dept_demo can seamlessly switch and query all 6 department dashboards.
6. Admin and Authority Officer workflows remain unchanged.
7. Roads dashboard functionality is fully preserved.
"""

import sys
import requests

BASE_URL = "http://127.0.0.1:8000"

def log_test(name, passed, detail=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} | {name}")
    if detail:
        print(f"      {detail}")
    if not passed:
        sys.exit(1)

def run_tests():
    print("=" * 80)
    print("JANSAKSHI - DEPARTMENT SELECTION & MULTI-DIVISION SECURITY TESTS")
    print("=" * 80)

    # 1. Authenticate Admin and Authority Officer (Unchanged flows)
    r_admin = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "admin", "password": "JanSakshi@2026"})
    log_test(
        "Criterion 1a: Admin login flow remains unchanged",
        r_admin.status_code == 200 and r_admin.json().get("user", {}).get("role") == "admin",
        f"Admin role: {r_admin.json().get('user', {}).get('role')}"
    )

    r_officer = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "officer", "password": "JanSakshi@2026"})
    log_test(
        "Criterion 1b: Authority Officer login flow remains unchanged",
        r_officer.status_code == 200 and r_officer.json().get("user", {}).get("role") == "authority_officer",
        f"Officer role: {r_officer.json().get('user', {}).get('role')}"
    )

    # 2. Authenticate Roads Officer (Restricted to RPW)
    r_roads = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "roads_officer", "password": "JanSakshi@2026"})
    roads_user = r_roads.json().get("user", {})
    roads_token = r_roads.json().get("access_token")
    headers_roads = {"Authorization": f"Bearer {roads_token}"}
    log_test(
        "Criterion 2: roads_officer is restricted to RPW only",
        r_roads.status_code == 200 and roads_user.get("authorized_departments") == [1],
        f"Authorized departments: {roads_user.get('authorized_departments')}, Code: {roads_user.get('department_code')}"
    )

    # 3. Authenticate Department Operations Demo (Full Access to 6 Departments)
    r_demo = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "dept_demo", "password": "JanSakshi@2026"})
    demo_user = r_demo.json().get("user", {})
    demo_token = r_demo.json().get("access_token")
    headers_demo = {"Authorization": f"Bearer {demo_token}"}
    log_test(
        "Criterion 3: dept_demo account has explicit authorized access to all 6 departments",
        r_demo.status_code == 200 and set(demo_user.get("authorized_departments", [])) == {1, 2, 3, 4, 5, 6},
        f"User: {demo_user.get('full_name')}, Authorized Dept IDs: {demo_user.get('authorized_departments')}"
    )

    # 4. Department Selection Directory Endpoint
    r_sel_demo = requests.get(f"{BASE_URL}/api/authority/departments/selection", headers=headers_demo)
    sel_data = r_sel_demo.json()
    depts = sel_data.get("departments", [])
    dept_codes = [d.get("code") for d in depts]
    all_6_present = set(["RPW", "SWM", "WSD", "DRN", "ESM", "PID"]).issubset(set(dept_codes))
    all_authorized_for_demo = all(d.get("is_authorized") is True for d in depts)
    all_have_tickets = all(d.get("complaint_count") > 0 for d in depts)

    log_test(
        "Criterion 4a: Selection endpoint displays all 6 municipal departments with live complaint counts",
        r_sel_demo.status_code == 200 and len(depts) == 6 and all_6_present and all_have_tickets,
        f"Departments: {[(d.get('code'), d.get('name'), str(d.get('complaint_count')) + ' tickets') for d in depts]}"
    )
    log_test(
        "Criterion 4b: For dept_demo, all 6 department cards are authorized (is_authorized=True)",
        all_authorized_for_demo,
        f"All 6 authorized: {all_authorized_for_demo}"
    )

    # Selection for roads_officer
    r_sel_roads = requests.get(f"{BASE_URL}/api/authority/departments/selection", headers=headers_roads)
    roads_depts = r_sel_roads.json().get("departments", [])
    rpw_card = next((d for d in roads_depts if d.get("code") == "RPW"), None)
    other_cards = [d for d in roads_depts if d.get("code") != "RPW"]
    rpw_authorized = rpw_card and rpw_card.get("is_authorized") is True
    others_locked = all(d.get("is_authorized") is False for d in other_cards)

    log_test(
        "Criterion 4c: For roads_officer, ONLY RPW is authorized; other 5 departments are locked",
        rpw_authorized and others_locked,
        f"RPW authorized: {rpw_authorized}, Other 5 locked: {others_locked}"
    )

    # 5. Backend Security Validation (Attempted Cross-Department Access by roads_officer)
    # Attempting to query SWM overview (dept 2)
    r_sec_overview = requests.get(f"{BASE_URL}/api/authority/overview?department_id=2", headers=headers_roads)
    log_test(
        "Criterion 5a: roads_officer querying SWM overview rejected with 403 Forbidden",
        r_sec_overview.status_code == 403,
        f"Status: {r_sec_overview.status_code} (Expected 403 Forbidden)"
    )

    # Attempting to query SWM complaints (dept 2)
    r_sec_comp = requests.get(f"{BASE_URL}/api/authority/complaints?department_id=2", headers=headers_roads)
    log_test(
        "Criterion 5b: roads_officer querying SWM complaints rejected with 403 Forbidden",
        r_sec_comp.status_code == 403,
        f"Status: {r_sec_comp.status_code} (Expected 403 Forbidden)"
    )

    # Attempting to query SWM inspection queue (dept 2)
    r_sec_queue = requests.get(f"{BASE_URL}/api/authority/inspection-queue?department_id=2", headers=headers_roads)
    log_test(
        "Criterion 5c: roads_officer querying SWM inspection queue rejected with 403 Forbidden",
        r_sec_queue.status_code == 403,
        f"Status: {r_sec_queue.status_code} (Expected 403 Forbidden)"
    )

    # Attempting to query SWM audit trail (dept 2)
    r_sec_audit = requests.get(f"{BASE_URL}/api/authority/audit?department_id=2", headers=headers_roads)
    log_test(
        "Criterion 5d: roads_officer querying SWM audit trail rejected with 403 Forbidden",
        r_sec_audit.status_code == 403,
        f"Status: {r_sec_audit.status_code} (Expected 403 Forbidden)"
    )

    # Attempting to access complaint JS-2026-00002 (assigned to SWM)
    r_sec_c2 = requests.get(f"{BASE_URL}/api/authority/complaints/JS-2026-00002", headers=headers_roads)
    log_test(
        "Criterion 5e: roads_officer viewing SWM complaint JS-2026-00002 rejected with 403 Forbidden",
        r_sec_c2.status_code == 403,
        f"Status: {r_sec_c2.status_code} (Expected 403 Forbidden)"
    )

    # 6. Multi-Division Access by dept_demo across all 6 departments
    dept_checks = []
    for dept_id in [1, 2, 3, 4, 5, 6]:
        r_dept_ov = requests.get(f"{BASE_URL}/api/authority/overview?department_id={dept_id}", headers=headers_demo)
        r_dept_cp = requests.get(f"{BASE_URL}/api/authority/complaints?department_id={dept_id}", headers=headers_demo)
        dept_checks.append(r_dept_ov.status_code == 200 and r_dept_cp.status_code == 200)

    log_test(
        "Criterion 6: dept_demo can seamlessly query dedicated dashboards for all 6 departments",
        all(dept_checks),
        f"Success across Depts 1 (RPW), 2 (SWM), 3 (WSD), 4 (DRN), 5 (ESM), 6 (PID): {dept_checks}"
    )

    # Invalid department ID test
    r_invalid_dept = requests.get(f"{BASE_URL}/api/authority/overview?department_id=99", headers=headers_demo)
    log_test(
        "Criterion 7: Non-existent department query rejected with 403 Forbidden",
        r_invalid_dept.status_code == 403,
        f"Status: {r_invalid_dept.status_code} (Expected 403 Forbidden)"
    )

    # 7. Preserve Roads Dashboard Functionality for RPW
    r_rpw_comp = requests.get(f"{BASE_URL}/api/authority/complaints?department_id=1", headers=headers_demo)
    rpw_items = r_rpw_comp.json().get("items", [])
    rpw_ids = [c.get("complaint_id") for c in rpw_items]
    has_key_rpw = "JS-2026-00019" in rpw_ids and "JS-2026-00004" in rpw_ids and "JS-2026-00010" in rpw_ids

    log_test(
        "Criterion 8: Existing Roads complaints (JS-2026-00019, JS-2026-00004, JS-2026-00010) fully preserved in RPW",
        has_key_rpw,
        f"Preserved RPW Complaint IDs: {rpw_ids}"
    )

    print("=" * 80)
    print("ALL DEPARTMENT SELECTION & MULTI-DIVISION SECURITY TESTS PASSED (100%)!")
    print("=" * 80)

if __name__ == "__main__":
    run_tests()
