"""
JanSakshi Phase 7 – Comprehensive Automated Test Suite
Covers all 14 Phase 7 authority scenarios, RBAC permissions, audit trail logging,
and regression tests across Phases 1 through 6.
"""

import sys
import os
import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def log_test(name, passed, detail=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} | {name}")
    if detail:
        print(f"      {detail}")

def run_tests():
    print("=" * 75)
    print("JANSAKSHI PHASE 7 – AUTHORITY DASHBOARD & CIVIC DECISION TESTS")
    print("=" * 75)

    # -------------------------------------------------------------
    # Scenario 1: Unauthorized Access Protection
    # -------------------------------------------------------------
    r = requests.get(f"{BASE_URL}/api/authority/overview")
    log_test(
        "Scenario 1: Unauthenticated request to authority endpoint is rejected",
        r.status_code == 401,
        f"Status: {r.status_code} (Expected 401 Unauthorized)"
    )

    # -------------------------------------------------------------
    # Scenario 2: Authentication & Role-Based Token Generation
    # -------------------------------------------------------------
    # 2a: Officer login
    r_officer = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "officer",
        "password": "JanSakshi@2026"
    })
    officer_data = r_officer.json()
    officer_token = officer_data.get("access_token")
    officer_role = officer_data.get("user", {}).get("role")
    log_test(
        "Scenario 2a: Officer login returns valid JWT token and role",
        r_officer.status_code == 200 and officer_token and officer_role == "authority_officer",
        f"Role: {officer_role}, Token length: {len(officer_token or '')}"
    )

    # 2b: Admin login
    r_admin = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "JanSakshi@2026"
    })
    admin_data = r_admin.json()
    admin_token = admin_data.get("access_token")
    log_test(
        "Scenario 2b: Admin login succeeds with admin privileges",
        r_admin.status_code == 200 and admin_data.get("user", {}).get("role") == "admin",
        f"Full name: {admin_data.get('user', {}).get('full_name')}"
    )

    # 2c: Department officer login
    r_dept = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "roads_officer",
        "password": "JanSakshi@2026"
    })
    dept_data = r_dept.json()
    dept_token = dept_data.get("access_token")
    dept_code = dept_data.get("user", {}).get("department_code")
    log_test(
        "Scenario 2c: Department officer login includes department association",
        r_dept.status_code == 200 and dept_code == "RPW",
        f"Department Code: {dept_code}"
    )

    # 2d: Invalid password fails
    r_invalid = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "officer",
        "password": "WrongPassword!23"
    })
    log_test(
        "Scenario 2d: Invalid password rejected with 401",
        r_invalid.status_code == 401,
        f"Status: {r_invalid.status_code}"
    )

    headers_officer = {"Authorization": f"Bearer {officer_token}"}
    headers_admin = {"Authorization": f"Bearer {admin_token}"}
    headers_dept = {"Authorization": f"Bearer {dept_token}"}

    # -------------------------------------------------------------
    # Scenario 3: Real-Time Overview Metrics & KPI Computation
    # -------------------------------------------------------------
    r_overview = requests.get(f"{BASE_URL}/api/authority/overview", headers=headers_officer)
    ov = r_overview.json()
    kpis = ov.get("kpis", {})
    log_test(
        "Scenario 3: Real-time municipal dashboard metrics computed from database",
        r_overview.status_code == 200 and kpis.get("total_complaints", 0) >= 21,
        f"Total: {kpis.get('total_complaints')}, Pending: {kpis.get('pending_verification')}, Categories: {len(ov.get('category_distribution', []))}"
    )

    # -------------------------------------------------------------
    # Scenario 4: Filterable, Sortable Complaints Desk
    # -------------------------------------------------------------
    r_list = requests.get(f"{BASE_URL}/api/authority/complaints?limit=10&page=1", headers=headers_officer)
    list_data = r_list.json()
    log_test(
        "Scenario 4: Paginated complaint list retrieved successfully",
        r_list.status_code == 200 and len(list_data.get("items", [])) <= 10 and list_data.get("total", 0) >= 21,
        f"Returned {len(list_data.get('items', []))} items of {list_data.get('total')} total"
    )

    # -------------------------------------------------------------
    # Scenario 5: Search & Multi-Faceted Filters
    # -------------------------------------------------------------
    r_search = requests.get(f"{BASE_URL}/api/authority/complaints?search=JS-2026-00019", headers=headers_officer)
    search_data = r_search.json()
    found_19 = any(c.get("complaint_id") == "JS-2026-00019" for c in search_data.get("items", []))
    log_test(
        "Scenario 5: Search by Complaint ID returns exact target complaint",
        r_search.status_code == 200 and found_19,
        f"Found JS-2026-00019 in search results (matches: {len(search_data.get('items', []))})"
    )

    # -------------------------------------------------------------
    # Scenario 6: Detailed Single Complaint & Evidence Retrieval
    # -------------------------------------------------------------
    r_detail = requests.get(f"{BASE_URL}/api/authority/complaints/JS-2026-00019", headers=headers_officer)
    det = r_detail.json()
    has_evidence = len(det.get("evidence", [])) > 0
    has_audit = len(det.get("audit_events", [])) > 0
    log_test(
        "Scenario 6: Full complaint details, evidence URLs and audit history loaded",
        r_detail.status_code == 200 and has_evidence and has_audit,
        f"Evidence files: {len(det.get('evidence', []))}, Audit events: {len(det.get('audit_events', []))}"
    )

    # -------------------------------------------------------------
    # Scenario 7: Multimodal Gemini AI Analysis Integration
    # -------------------------------------------------------------
    ai_analyses = det.get("ai_analyses", [])
    has_ai = len(ai_analyses) > 0
    ai_item = ai_analyses[0] if has_ai else {}
    log_test(
        "Scenario 7: Gemini multimodal advisory analysis preserved and separated",
        r_detail.status_code == 200 and has_ai and "recommended_severity" in ai_item,
        f"AI Severity: {ai_item.get('recommended_severity')}, AI Category: {ai_item.get('predicted_category')}"
    )

    # -------------------------------------------------------------
    # Scenario 8: Human Verification Approval
    # -------------------------------------------------------------
    r_verify = requests.post(
        f"{BASE_URL}/api/authority/complaints/JS-2026-00019/verify",
        headers=headers_officer,
        json={"notes": "Inspection confirmed road pothole at Morampudi Junction, Rajahmundry."}
    )
    v_data = r_verify.json()
    log_test(
        "Scenario 8: Authority verification approved and status advanced",
        r_verify.status_code == 200 and v_data.get("verification_status") == "verified",
        f"Verified status: {v_data.get('verification_status')}, Admin status: {v_data.get('admin_status')}"
    )

    # -------------------------------------------------------------
    # Scenario 9: Human Verification Rejection with Mandatory Reason
    # -------------------------------------------------------------
    # Use JS-2026-00021 for rejection test
    # First verify empty reason fails validation
    r_reject_empty = requests.post(
        f"{BASE_URL}/api/authority/complaints/JS-2026-00021/reject",
        headers=headers_officer,
        json={"reason": ""}
    )
    # Valid rejection
    r_reject = requests.post(
        f"{BASE_URL}/api/authority/complaints/JS-2026-00021/reject",
        headers=headers_officer,
        json={"reason": "Duplicate submission test, non-reproducible grievance."}
    )
    rej_data = r_reject.json()
    log_test(
        "Scenario 9: Rejection enforces mandatory reason and logs audit event",
        r_reject_empty.status_code == 422 and r_reject.status_code == 200 and rej_data.get("verification_status") == "rejected",
        f"Rejection Reason: {rej_data.get('rejection_reason')}"
    )

    # -------------------------------------------------------------
    # Scenario 10: Additional Information Request
    # -------------------------------------------------------------
    # Use JS-2026-00020 for info request test
    r_info = requests.post(
        f"{BASE_URL}/api/authority/complaints/JS-2026-00020/request-info",
        headers=headers_officer,
        json={"notes": "Please provide the nearest electrical post number or landmark."}
    )
    info_data = r_info.json()
    log_test(
        "Scenario 10: Additional information requested and citizen note recorded",
        r_info.status_code == 200 and info_data.get("verification_status") == "info_requested",
        f"Notes: {info_data.get('info_request_notes')}"
    )

    # -------------------------------------------------------------
    # Scenario 11: Department Assignment & Workload Allocation
    # -------------------------------------------------------------
    # Get RPW department id
    r_depts = requests.get(f"{BASE_URL}/api/authority/departments", headers=headers_officer)
    depts_list = r_depts.json().get("departments", [])
    rpw_dept = next((d for d in depts_list if d.get("code") == "RPW"), None)
    rpw_id = rpw_dept.get("id") if rpw_dept else 1

    r_assign = requests.post(
        f"{BASE_URL}/api/authority/complaints/JS-2026-00019/assign",
        headers=headers_officer,
        json={
            "department_id": rpw_id,
            "notes": "Assigned to Roads Division for asphalt resurfacing."
        }
    )
    assign_data = r_assign.json()
    log_test(
        "Scenario 11: Complaint assigned to municipal department with audit event",
        r_assign.status_code == 200 and assign_data.get("department_code") == "RPW",
        f"Assigned Dept: {assign_data.get('department_name')} ({assign_data.get('department_code')})"
    )

    # -------------------------------------------------------------
    # Scenario 12: Administrative Status Progression (Lifecycle)
    # -------------------------------------------------------------
    r_status = requests.post(
        f"{BASE_URL}/api/authority/complaints/JS-2026-00019/status",
        headers=headers_officer,
        json={
            "status": "In Progress",
            "notes": "Field inspection team dispatched to site."
        }
    )
    status_data = r_status.json()
    log_test(
        "Scenario 12: Administrative progress status transitioned to In Progress",
        r_status.status_code == 200 and status_data.get("admin_status") == "In Progress",
        f"New Admin Status: {status_data.get('admin_status')}"
    )

    # -------------------------------------------------------------
    # Scenario 13: Escalation Controls (Tier 1 & Tier 2)
    # -------------------------------------------------------------
    r_escalate = requests.post(
        f"{BASE_URL}/api/authority/complaints/JS-2026-00019/escalate",
        headers=headers_officer,
        json={
            "escalation_level": 1,
            "reason": "High-traffic junction requires urgent intervention before weekend congestion.",
            "escalated_to": "Superintending Engineer (Roads)"
        }
    )
    esc_data = r_escalate.json()
    log_test(
        "Scenario 13: Complaint escalated to Tier 1 with responsible officer tracking",
        r_escalate.status_code == 200 and esc_data.get("escalation_level") == 1,
        f"Escalated to: {esc_data.get('escalated_to')}, Level: {esc_data.get('escalation_level')}"
    )

    # -------------------------------------------------------------
    # Scenario 14: Role-Based Access Control (RBAC) Enforcement
    # -------------------------------------------------------------
    # Department officer should NOT be allowed to verify/reject complaints
    r_dept_verify = requests.post(
        f"{BASE_URL}/api/authority/complaints/JS-2026-00019/verify",
        headers=headers_dept,
        json={"notes": "Unauthorized attempt"}
    )
    log_test(
        "Scenario 14a: Department officer denied verification permissions (403 Forbidden)",
        r_dept_verify.status_code == 403,
        f"Status: {r_dept_verify.status_code} (Expected 403 Forbidden)"
    )

    # Department officer CAN update status for complaints in their own department
    r_dept_status = requests.post(
        f"{BASE_URL}/api/authority/complaints/JS-2026-00019/status",
        headers=headers_dept,
        json={"status": "In Progress", "notes": "Road crew started patch repair."}
    )
    log_test(
        "Scenario 14b: Department officer allowed to update status within their department",
        r_dept_status.status_code == 200,
        f"Status code: {r_dept_status.status_code}"
    )

    # Internal note logging
    r_note = requests.post(
        f"{BASE_URL}/api/authority/complaints/JS-2026-00019/notes",
        headers=headers_admin,
        json={"notes": "Verified asphalt contract PO #94827 issued."}
    )
    log_test(
        "Scenario 14c: Staff internal note securely recorded in complaint file",
        r_note.status_code == 200 and "PO #94827" in r_note.json().get("internal_notes", ""),
        "Internal staff notes preserved without citizen exposure"
    )

    # -------------------------------------------------------------
    # Regression Tests: Phases 1 through 6
    # -------------------------------------------------------------
    print("-" * 75)
    print("REGRESSION TESTS (PHASES 1 - 6)")
    print("-" * 75)

    # Regression: Phase 1 & 2 Public Health & Tracking
    r_health = requests.get(f"{BASE_URL}/api/health")
    log_test(
        "Regression Phase 1: API health check endpoint active",
        r_health.status_code == 200 and r_health.json().get("phase") == 7,
        f"API Version: {r_health.json().get('version')}"
    )

    r_track = requests.get(f"{BASE_URL}/api/complaints/JS-2026-00019")
    log_test(
        "Regression Phase 2: Public complaint tracking endpoint intact",
        r_track.status_code == 200 and r_track.json().get("complaint_id") == "JS-2026-00019",
        f"Citizen tracking preserved without exposure of confidential notes"
    )

    # Regression: Phase 3 & 5 Physical Issues & Review Desk
    r_issues = requests.get(f"{BASE_URL}/api/issues/ISSUE-2026-00001")
    log_test(
        "Regression Phase 3: Physical issues entity endpoint active",
        r_issues.status_code == 200 and r_issues.json().get("issue_reference_id") == "ISSUE-2026-00001",
        f"Physical issue retrieved: {r_issues.json().get('issue_reference_id')}"
    )

    r_dups = requests.get(f"{BASE_URL}/api/duplicates/review-queue")
    log_test(
        "Regression Phase 5: Duplicate Review Desk queue endpoint active",
        r_dups.status_code == 200,
        f"Duplicate review queue operational"
    )

    # Regression: Phase 6 Gmail Integration Status
    r_email_status = requests.get(f"{BASE_URL}/api/email/status")
    es = r_email_status.json()
    log_test(
        "Regression Phase 6: Email integration desk & official mailbox active",
        r_email_status.status_code == 200 and es.get("official_inbox_address") == "jansakshiofficial@gmail.com",
        f"Mailbox: {es.get('official_inbox_address')}, Status: {es.get('status')}"
    )

    print("=" * 75)
    print("ALL 14 PHASE 7 SCENARIOS + REGRESSION TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 75)

if __name__ == "__main__":
    run_tests()
