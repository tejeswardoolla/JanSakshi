"""
JanSakshi - Roads Department Officer Role Corrections Automated Test Suite
Verifies:
1. Roads dashboard & scoped overview.
2. Assigned complaints list shows only authorized RPW records (no system-wide count leakage).
3. Road Inspection Queue shows field inspections, not human verification controls.
4. Department SLA shows ONLY Roads & Public Works (RPW) with 7 core SLA metrics.
5. Division Activity is strictly scoped to RPW complaints at SQL query level.
6. Road progress updates still work for RPW complaints.
7. Map displays actual road complaint coordinates (including JS-2026-00019).
8. Unauthorized cross-department access is strictly blocked (403 Forbidden).
"""

import sys
import requests
import json

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
    print("JANSAKSHI - ROADS DEPARTMENT OFFICER ROLE CORRECTIONS & SECURITY TESTS")
    print("=" * 80)

    # -------------------------------------------------------------
    # 1. Authenticate Roads Officer
    # -------------------------------------------------------------
    r_login = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "roads_officer",
        "password": "JanSakshi@2026"
    })
    log_test(
        "Authentication: roads_officer login succeeds with department association",
        r_login.status_code == 200 and r_login.json().get("user", {}).get("department_code") == "RPW",
        f"User: {r_login.json().get('user', {}).get('full_name')} ({r_login.json().get('user', {}).get('role')}), Dept: {r_login.json().get('user', {}).get('department_code')}"
    )
    token_roads = r_login.json().get("access_token")
    headers_roads = {"Authorization": f"Bearer {token_roads}"}

    # Authenticate Admin for comparison
    r_admin_login = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "JanSakshi@2026"
    })
    headers_admin = {"Authorization": f"Bearer {r_admin_login.json().get('access_token')}"}

    # -------------------------------------------------------------
    # 2. Roads Dashboard & Scoped Overview
    # -------------------------------------------------------------
    r_overview = requests.get(f"{BASE_URL}/api/authority/overview", headers=headers_roads)
    ov = r_overview.json()
    dept_metrics = ov.get("department_metrics", [])
    log_test(
        "Criterion 1: Roads dashboard overview computes metrics scoped to RPW",
        r_overview.status_code == 200 and len(dept_metrics) == 1 and dept_metrics[0].get("code") == "RPW",
        f"Departments in overview: {[d.get('code') for d in dept_metrics]} (Only RPW exposed)"
    )

    # -------------------------------------------------------------
    # 3. Assigned Complaints - Strict Scoping (No System-Wide Leakage)
    # -------------------------------------------------------------
    r_comp = requests.get(f"{BASE_URL}/api/authority/complaints", headers=headers_roads)
    comp_data = r_comp.json()
    items = comp_data.get("items", [])
    total_count = comp_data.get("total", 0)
    all_rpw = all(i.get("department", {}).get("code") == "RPW" for i in items if i.get("department"))
    log_test(
        "Criterion 2a: Assigned complaints endpoint returns only authorized RPW records",
        r_comp.status_code == 200 and len(items) > 0 and all_rpw,
        f"Returned {len(items)} RPW complaints: {[i.get('complaint_id') for i in items]}"
    )
    log_test(
        "Criterion 2b: Total count reflects ONLY department complaints (no system-wide 21 leakage)",
        total_count == len(items) and total_count < 21,
        f"Total count exposed to roads_officer: {total_count} (System-wide count of 21 safely hidden)"
    )

    # Attempt to bypass and query another department ID (e.g. 2: Water Supply)
    r_bypass_dept = requests.get(f"{BASE_URL}/api/authority/complaints?department_id=2", headers=headers_roads)
    log_test(
        "Criterion 2c: Querying another department ID is blocked with 403 Forbidden",
        r_bypass_dept.status_code == 403,
        f"Status: {r_bypass_dept.status_code} (Expected 403 Forbidden)"
    )

    # -------------------------------------------------------------
    # 4. Road Inspection Queue - Field Work Orders
    # -------------------------------------------------------------
    r_queue = requests.get(f"{BASE_URL}/api/authority/inspection-queue", headers=headers_roads)
    queue_data = r_queue.json()
    q_items = queue_data.get("items", [])
    all_verified_and_active = all(
        i.get("verification_status") == "verified" and i.get("admin_status") in ("Assigned", "In Progress", "Pending Inspection")
        for i in q_items
    )
    log_test(
        "Criterion 3: Road Inspection Queue returns verified RPW field work orders",
        r_queue.status_code == 200 and len(q_items) > 0 and all_verified_and_active,
        f"Work orders awaiting inspection/repair: {[(i.get('complaint_id'), i.get('admin_status')) for i in q_items]}"
    )

    # -------------------------------------------------------------
    # 5. Department SLA - Restricted Strictly to RPW with 7 Metrics
    # -------------------------------------------------------------
    r_depts = requests.get(f"{BASE_URL}/api/authority/departments", headers=headers_roads)
    depts_data = r_depts.json()
    depts_list = depts_data.get("departments", [])
    log_test(
        "Criterion 4a: Department SLA returns ONLY Roads & Public Works (RPW)",
        r_depts.status_code == 200 and len(depts_list) == 1 and depts_list[0].get("code") == "RPW",
        f"Exposed departments count: {len(depts_list)}, Code: {depts_list[0].get('code')}"
    )

    rpw = depts_list[0]
    required_metrics = [
        "sla_days", "total_assigned", "pending_inspections",
        "in_progress_repairs", "resolved_complaints", "overdue_work_orders",
        "sla_compliance_rate", "resolution_rate", "performance_rate"
    ]
    has_all_metrics = all(k in rpw for k in required_metrics)
    expected_resolution_rate = round((rpw.get("resolved_complaints", 0) / max(rpw.get("total_assigned", 1), 1)) * 100, 1)
    resolution_matches = abs(rpw.get("resolution_rate", 0) - expected_resolution_rate) < 0.2
    log_test(
        "Criterion 4b: RPW SLA includes all statutory performance metrics (SLA Compliance Rate vs Resolution Rate)",
        has_all_metrics and rpw.get("sla_compliance_rate") == 100.0 and resolution_matches,
        f"SLA: {rpw.get('sla_days')}d | Assigned: {rpw.get('total_assigned')} | Pending: {rpw.get('pending_inspections')} | In Progress: {rpw.get('in_progress_repairs')} | Resolved: {rpw.get('resolved_complaints')} | Overdue: {rpw.get('overdue_work_orders')} | SLA Compliance: {rpw.get('sla_compliance_rate')}% | Resolution Rate: {rpw.get('resolution_rate')}%"
    )

    # -------------------------------------------------------------
    # 6. Division Activity - Strict Query-Level Scoping
    # -------------------------------------------------------------
    r_audit = requests.get(f"{BASE_URL}/api/authority/audit", headers=headers_roads)
    audit_data = r_audit.json()
    audit_items = audit_data.get("items", [])
    audit_cids = set(i.get("complaint_id") for i in audit_items)
    # Get all RPW complaint IDs currently assigned
    rpw_cids = set(c.get("complaint_id") for c in items)
    log_test(
        "Criterion 5a: Division Activity returns only audit events for RPW complaints",
        r_audit.status_code == 200 and len(audit_items) > 0 and audit_cids.issubset(rpw_cids),
        f"Total events: {len(audit_items)}, Associated Complaint IDs: {audit_cids}"
    )

    # Attempt to query audit for an unrelated complaint (e.g. JS-2026-00002)
    r_unauth_audit = requests.get(f"{BASE_URL}/api/authority/audit?complaint_id=JS-2026-00002", headers=headers_roads)
    log_test(
        "Criterion 5b: Querying audit for an unrelated complaint returns 403 Forbidden",
        r_unauth_audit.status_code == 403,
        f"Status: {r_unauth_audit.status_code} (Expected 403 Forbidden)"
    )

    # -------------------------------------------------------------
    # 7. Road Progress Updates for RPW Complaints
    # -------------------------------------------------------------
    r_update_status = requests.post(
        f"{BASE_URL}/api/authority/complaints/JS-2026-00019/status",
        headers=headers_roads,
        json={
            "status": "In Progress",
            "notes": "Asphalt patchwork roller compaction verified by roads engineer."
        }
    )
    log_test(
        "Criterion 6: Road progress update succeeds for assigned RPW complaint",
        r_update_status.status_code == 200 and r_update_status.json().get("admin_status") == "In Progress",
        f"Updated admin_status: {r_update_status.json().get('admin_status')}"
    )

    # -------------------------------------------------------------
    # 8. Road Complaint Geolocation Coordinates & Confidential Notes
    # -------------------------------------------------------------
    r_detail_19 = requests.get(f"{BASE_URL}/api/authority/complaints/JS-2026-00019", headers=headers_roads)
    c19 = r_detail_19.json()
    coords_valid = c19.get("latitude") == 17.0005 and c19.get("longitude") == 81.804
    log_test(
        "Criterion 7a: JS-2026-00019 preserves exact coordinates for map visualization",
        r_detail_19.status_code == 200 and coords_valid,
        f"Coordinates: {c19.get('latitude')}, {c19.get('longitude')} (Morampudi Junction, Rajahmundry)"
    )

    r_admin_c19 = requests.get(f"{BASE_URL}/api/authority/complaints/JS-2026-00019", headers=headers_admin)
    admin_notes = r_admin_c19.json().get("internal_notes", "")
    roads_notes = c19.get("internal_notes", "")
    notes_masked_for_officer = "Confidential to Municipal Leadership" in roads_notes and "PO #94827" not in roads_notes
    notes_intact_for_admin = "PO #94827" in admin_notes

    log_test(
        "Criterion 7b: Activity & Notes visibility masks confidential admin notes for department officer while retaining audit headers",
        notes_masked_for_officer and notes_intact_for_admin,
        f"Roads Officer view: '{roads_notes.splitlines()[0]}' | Admin view has raw PO: {notes_intact_for_admin}"
    )

    # -------------------------------------------------------------
    # 9. Security & Cross-Department Enforcement (403 Tests)
    # -------------------------------------------------------------
    # 9a: Cannot verify complaints
    r_verify = requests.post(f"{BASE_URL}/api/authority/complaints/JS-2026-00019/verify", headers=headers_roads, json={})
    log_test("Criterion 8a: Verification by department officer rejected with 403", r_verify.status_code == 403)

    # 9b: Cannot reject complaints
    r_reject = requests.post(f"{BASE_URL}/api/authority/complaints/JS-2026-00019/reject", headers=headers_roads, json={"reason": "Test"})
    log_test("Criterion 8b: Rejection by department officer rejected with 403", r_reject.status_code == 403)

    # 9c: Cannot request info from citizen
    r_info = requests.post(f"{BASE_URL}/api/authority/complaints/JS-2026-00019/request-info", headers=headers_roads, json={"notes": "Test"})
    log_test("Criterion 8c: Request info by department officer rejected with 403", r_info.status_code == 403)

    # 9d: Cannot assign complaints to departments
    r_assign = requests.post(f"{BASE_URL}/api/authority/complaints/JS-2026-00019/assign", headers=headers_roads, json={"department_id": 1})
    log_test("Criterion 8d: Department assignment by department officer rejected with 403", r_assign.status_code == 403)

    # 9e: Cannot escalate complaints
    r_esc = requests.post(f"{BASE_URL}/api/authority/complaints/JS-2026-00019/escalate", headers=headers_roads, json={"escalation_level": 1, "reason": "Test escalation"})
    log_test("Criterion 8e: Escalation by department officer rejected with 403", r_esc.status_code == 403)

    # 9f: Cannot access details of complaint outside RPW (e.g. JS-2026-00002)
    r_cross_detail = requests.get(f"{BASE_URL}/api/authority/complaints/JS-2026-00002", headers=headers_roads)
    log_test("Criterion 8f: Viewing complaint outside division rejected with 403", r_cross_detail.status_code == 403)

    # 9g: Cannot add notes to complaint outside RPW
    r_cross_note = requests.post(f"{BASE_URL}/api/authority/complaints/JS-2026-00002/notes", headers=headers_roads, json={"notes": "Unauthorized note"})
    log_test("Criterion 8g: Adding notes to complaint outside division rejected with 403", r_cross_note.status_code == 403)

    # 9h: Cannot update status of complaint outside RPW
    r_cross_status = requests.post(f"{BASE_URL}/api/authority/complaints/JS-2026-00002/status", headers=headers_roads, json={"status": "In Progress"})
    log_test("Criterion 8h: Updating status of complaint outside division rejected with 403", r_cross_status.status_code == 403)

    # -------------------------------------------------------------
    # 10. Field Inspection Evidence Upload
    # -------------------------------------------------------------
    fake_jpg = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00' + b'\x00' * 500
    r_evidence = requests.post(
        f"{BASE_URL}/api/authority/complaints/JS-2026-00019/evidence",
        headers=headers_roads,
        files={"file": ("asphalt_compaction_verified.jpg", fake_jpg, "image/jpeg")},
        data={"caption": "Post-patch roller compaction density test passed"}
    )
    log_test(
        "Criterion 9: Upload field inspection evidence succeeds for RPW complaint",
        r_evidence.status_code == 200 and r_evidence.json().get("evidence_id") is not None,
        f"Evidence ID: {r_evidence.json().get('evidence_id')}, Stored: {r_evidence.json().get('stored_filename')}"
    )

    print("=" * 80)
    print("ALL ROADS DEPARTMENT OFFICER CORRECTIONS & SECURITY TESTS PASSED (100%)!")
    print("=" * 80)

if __name__ == "__main__":
    run_tests()

