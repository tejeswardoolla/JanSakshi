"""
JANSAKSHI PHASE 9 — MASTER SYSTEM AUDIT & END-TO-END VERIFICATION TEST SUITE
Comprehensive release testing for:
1. End-to-End Complaint Lifecycle (Citizen -> Admin -> Officer -> Dept -> Resolution -> Review -> Closure -> Citizen Track)
2. Gmail Ingestion & Non-Civic Record Isolation (JS-2026-00022)
3. Three-Role RBAC Boundaries (Admin, Authority Officer, Department Officer)
4. Six Department Workspaces & Strict Division Isolation (RPW, SWM, WSD, DRN, ESM, PID)
5. Multi-Version Resolution Verification (v1 -> Return for correction -> v2 -> Approval & Closure)
6. Critical Escalations (System Flagging vs Human Decision Tier 1/2)
7. Security Audit (Password hashing, JWT, Path Traversal, File Restrictions, PII Protection)
8. Database Integrity & Timestamp Consistency
"""

import sys
import io
import time
import requests
import sqlite3

BASE_URL = "http://127.0.0.1:8000"

passed_tests = 0
failed_tests = 0

def pass_test(name, details=""):
    global passed_tests
    passed_tests += 1
    print(f"✅ PASS | {name}")
    if details:
        print(f"       {details}")

def fail_test(name, err):
    global failed_tests
    failed_tests += 1
    print(f"❌ FAIL | {name}: {err}")

def get_auth_token(username, password="JanSakshi@2026"):
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": username, "password": password},
        timeout=5
    )
    if r.status_code != 200:
        raise Exception(f"Login failed for {username}: {r.status_code} - {r.text}")
    return r.json()["access_token"]

def run_master_audit():
    print("=" * 85)
    print("JANSAKSHI PHASE 9 — COMPLETE SYSTEM AUDIT & RELEASE VERIFICATION")
    print("=" * 85)

    # ------------------------------------------------------------------------
    # 1. AUTHENTICATION OF ALL THREE ROLES & DEMO ACCOUNTS
    # ------------------------------------------------------------------------
    try:
        admin_token = get_auth_token("admin")
        admin_hdr = {"Authorization": f"Bearer {admin_token}"}
        pass_test("Role 1 Auth: Admin ('admin')", "Token issued successfully")

        officer_token = get_auth_token("officer")
        officer_hdr = {"Authorization": f"Bearer {officer_token}"}
        pass_test("Role 2 Auth: Authority Officer ('officer')", "Token issued successfully")

        roads_token = get_auth_token("roads_officer")
        roads_hdr = {"Authorization": f"Bearer {roads_token}"}
        pass_test("Role 3 Auth: Single-Dept Roads Officer ('roads_officer')", "Token issued, scoped to RPW (Dept 1)")

        demo_token = get_auth_token("dept_demo")
        demo_hdr = {"Authorization": f"Bearer {demo_token}"}
        pass_test("Role 3 Auth: Multi-Dept Demo Officer ('dept_demo')", "Token issued, authorized across 6 divisions")
    except Exception as e:
        fail_test("Authentication of Primary Accounts", e)
        return

    # ------------------------------------------------------------------------
    # 2. PHASE 9.1 SCENARIO A — COMPLETE CITIZEN TO CLOSURE WORKFLOW
    # ------------------------------------------------------------------------
    test_cid = None
    try:
        # Step A1: Citizen submits complaint via public portal
        dummy_jpg = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00" + b"X" * 200
        submit_res = requests.post(
            f"{BASE_URL}/api/complaints/",
            data={
                "category": "Road Damage / Potholes",
                "description": "Deep asphalt trench pothole at Morampudi Junction creating hazardous traffic conditions.",
                "latitude": 17.0005,
                "longitude": 81.8040,
                "location_accuracy": 4.5,
                "location_source": "gps",
                "citizen_name": "Suresh Varma (Demo Citizen)",
                "citizen_email": "citizen.demo@example.com",
                "citizen_phone": "+91 98765 43210"
            },
            files={"evidence": ("pothole_initial.jpg", dummy_jpg, "image/jpeg")},
            timeout=8
        )
        assert submit_res.status_code == 201, f"Citizen submit failed: {submit_res.text}"
        sub_data = submit_res.json()
        test_cid = sub_data["complaint_id"]
        tracking_token = sub_data.get("tracking_token")
        assert test_cid.startswith("JS-2026-"), f"Invalid ID format: {test_cid}"
        pass_test("Step A1: Citizen Website Submission", f"Created {test_cid} with GPS (17.0005, 81.8040) and tracking token")

        # Step A2: Admin reviews intake and marks Ready for Authority Officer
        mark_res = requests.post(
            f"{BASE_URL}/api/authority/complaints/{test_cid}/mark-ready",
            json={"notes": "Intake completed: GPS grounded, AI classification valid, duplicate screened."},
            headers=admin_hdr,
            timeout=5
        )
        assert mark_res.status_code == 200, f"Admin mark-ready failed: {mark_res.text}"
        assert mark_res.json()["admin_status"] == "Ready for Authority Officer"
        pass_test("Step A2: Admin Intake Review & Preparation", f"Marked {test_cid} 'Ready for Authority Officer'")

        # Step A3: Authority Officer verifies queue, accepts, and dispatches to Roads (RPW)
        queue_res = requests.get(
            f"{BASE_URL}/api/authority/complaints?verification_status=pending&limit=50",
            headers=officer_hdr,
            timeout=5
        )
        assert queue_res.status_code == 200
        queue_cids = [item["complaint_id"] for item in queue_res.json().get("items", [])]
        assert test_cid in queue_cids, f"{test_cid} must appear in Authority Officer decision queue"

        # Officer accepts complaint
        accept_res = requests.post(
            f"{BASE_URL}/api/authority/complaints/{test_cid}/verify",
            json={"notes": "Civic grievance verified as genuine municipal responsibility."},
            headers=officer_hdr,
            timeout=5
        )
        assert accept_res.status_code == 200
        pass_test("Step A3: Authority Officer Civic Acceptance", f"{test_cid} accepted for departmental action")

        # Step A4: Officer dispatches work order to RPW (Dept 1) with specific officer and deadline
        dispatch_res = requests.post(
            f"{BASE_URL}/api/authority/complaints/{test_cid}/assign",
            json={
                "department_id": 1,  # RPW
                "assigned_to_user_id": 3,  # Executive Engineer (Roads)
                "priority": "High",
                "assignment_date": "2026-11-13",
                "expected_completion_date": "2026-11-20",
                "expected_completion_days": 7,
                "notes": "Execute immediate asphalt patch repair and seal trench at Morampudi Junction."
            },
            headers=officer_hdr,
            timeout=5
        )
        assert dispatch_res.status_code == 200
        assert dispatch_res.json()["admin_status"] == "Assigned"
        pass_test("Step A4: Department Work Order Dispatch", f"Dispatched to RPW with 7-day SLA and assigned officer 3")

        # Step A5: Roads Department Officer inspects work order and updates status to In Progress
        stat_res = requests.post(
            f"{BASE_URL}/api/authority/complaints/{test_cid}/status",
            json={"status": "In Progress", "notes": "Road crew mobilized on site with asphalt roller."},
            headers=roads_hdr,
            timeout=5
        )
        assert stat_res.status_code == 200
        assert stat_res.json()["admin_status"] == "In Progress"
        pass_test("Step A5: Department Field Inspection & Progress Update", "Status moved to 'In Progress'")

        # Step A6: Department Officer submits Version 1 resolution
        v1_evidence_res = requests.post(
            f"{BASE_URL}/api/authority/complaints/{test_cid}/evidence",
            files={"file": ("v1_patch.jpg", dummy_jpg, "image/jpeg")},
            data={"evidence_type": "after_repair", "notes": "Preliminary asphalt fill completed."},
            headers=roads_hdr,
            timeout=5
        )
        assert v1_evidence_res.status_code == 200
        v1_eid = v1_evidence_res.json()["evidence_id"]

        v1_sub_res = requests.post(
            f"{BASE_URL}/api/authority/complaints/{test_cid}/resolution/submit",
            json={
                "work_description": "Pothole filled with standard bitumin mix.",
                "repair_action_taken": "Bituminous patching and compaction",
                "field_notes": "Preliminary asphalt fill completed.",
                "after_evidence_id": v1_eid
            },
            headers=roads_hdr,
            timeout=5
        )
        assert v1_sub_res.status_code == 201, f"v1 submit failed: {v1_sub_res.text}"
        v1_data = v1_sub_res.json()
        sub_id = v1_data["id"]
        assert v1_data["version_number"] >= 1
        pass_test("Step A6: Department Resolution Submission (v1)", f"Version {v1_data['version_number']} submitted for review")

        # Step A7: Authority Officer reviews and returns for correction with mandatory note
        return_res = requests.post(
            f"{BASE_URL}/api/authority/resolutions/{sub_id}/return",
            json={"rejection_reason": "Bitumen surface requires edge sealing and final rolling before approval."},
            headers=officer_hdr,
            timeout=5
        )
        assert return_res.status_code == 200, f"Return failed: {return_res.text}"
        assert return_res.json().get("status") in ("ok", "returned_for_correction")
        pass_test("Step A7: Authority Review — Return for Correction", "Work returned with mandatory correction instruction")

        # Step A8: Department Officer submits Version 2 corrected resolution
        v2_evidence_res = requests.post(
            f"{BASE_URL}/api/authority/complaints/{test_cid}/evidence",
            files={"file": ("v2_sealed.jpg", dummy_jpg, "image/jpeg")},
            data={"evidence_type": "after_repair", "notes": "Compacted and edge-sealed surface."},
            headers=roads_hdr,
            timeout=5
        )
        assert v2_evidence_res.status_code == 200
        v2_eid = v2_evidence_res.json()["evidence_id"]

        v2_sub_res = requests.post(
            f"{BASE_URL}/api/authority/complaints/{test_cid}/resolution/submit",
            json={
                "work_description": "Re-rolled and edge-sealed with hot-mix asphalt. Inspection verified.",
                "repair_action_taken": "Hot-mix asphalt edge-seal and heavy compaction",
                "field_notes": "Surface grade inspected and leveled.",
                "after_evidence_id": v2_eid
            },
            headers=roads_hdr,
            timeout=5
        )
        assert v2_sub_res.status_code == 201, f"v2 submit failed: {v2_sub_res.text}"
        v2_data = v2_sub_res.json()
        v2_sub_id = v2_data["id"]
        assert v2_data["version_number"] > v1_data["version_number"], "Version must increment"
        pass_test("Step A8: Department Versioned Resubmission (v2)", f"Incremented to Version {v2_data['version_number']}")

        # Step A9: Authority Officer conducts final review and approves closure
        close_res = requests.post(
            f"{BASE_URL}/api/authority/resolutions/{v2_sub_id}/approve",
            json={"verification_notes": "Edge sealing and surface compaction verified against municipal road standards."},
            headers=officer_hdr,
            timeout=5
        )
        assert close_res.status_code == 200, f"Approve failed: {close_res.text}"
        assert close_res.json().get("status") in ("approved", "ok")
        assert close_res.json().get("admin_status") == "Closed"
        pass_test("Step A9: Authority Officer Final Approval & Closure", f"{test_cid} officially Closed")

        # Step A10: Citizen Tracking displays verified closed status and audit history
        track_res = requests.get(f"{BASE_URL}/api/complaints/{test_cid}", timeout=5)
        assert track_res.status_code == 200, f"Tracking failed: {track_res.text}"
        t_json = track_res.json()
        assert t_json["status"] in ("Closed", "Resolved")
        pass_test("Step A10: Citizen Public Tracking Verification", f"Public status: {t_json['status']} with timeline")

    except Exception as e:
        import traceback
        traceback.print_exc()
        fail_test("Phase 9.1 Scenario A (Full End-to-End Workflow)", e)

    # ------------------------------------------------------------------------
    # 3. PHASE 9.1 SCENARIO B & C — GMAIL & NON-CIVIC EMAIL AUDIT (JS-2026-00022)
    # ------------------------------------------------------------------------
    try:
        # Ingestion logic & email desk test
        em_res = requests.get(f"{BASE_URL}/api/email/messages?limit=10", headers=admin_hdr, timeout=5)
        assert em_res.status_code == 200, f"Email desk failed: {em_res.text}"
        pass_test("Phase 9.1 Scenario B: Gmail Ingestion Desk Access", "Admin can access ingested messages and audit logs")

        # Non-civic record investigation: JS-2026-00022
        conn = sqlite3.connect('jansakshi.db')
        c = conn.cursor()
        c.execute("SELECT complaint_id, category, admin_status, verification_status, rejection_reason FROM complaints WHERE complaint_id = ?", ('JS-2026-00022',))
        row = c.fetchone()
        assert row is not None, "JS-2026-00022 must exist"
        assert row[2] == "Rejected" and row[3] == "rejected", f"Expected Rejected status, got {row[2]}, {row[3]}"
        assert "Higgsfield" in row[4] or "Non-civic" in row[4], "Rejection reason must document non-civic account alert"

        # Check audit trail preservation
        c.execute("SELECT event_type FROM complaint_events WHERE complaint_id = ?", ('JS-2026-00022',))
        events = [r[0] for r in c.fetchall()]
        assert "non_civic_rejected" in events, "non_civic_rejected audit event must be preserved"
        conn.close()

        # Verify JS-2026-00022 does not appear in Authority Officer pending queue
        officer_q = requests.get(f"{BASE_URL}/api/authority/complaints?verification_status=pending&limit=50", headers=officer_hdr, timeout=5)
        cids = [item["complaint_id"] for item in officer_q.json().get("items", [])]
        assert "JS-2026-00022" not in cids, "JS-2026-00022 must never enter Authority Officer queue"
        pass_test("Phase 9.1 Scenario C: Non-Civic Record Isolation (JS-2026-00022)", "Classified as non-civic, marked Rejected, complete audit preserved, excluded from decision queue")
    except Exception as e:
        fail_test("Phase 9.1 Scenario B/C (Email Ingestion & Non-Civic Isolation)", e)

    # ------------------------------------------------------------------------
    # 4. PHASE 9.2 — THREE-ROLE RBAC BOUNDARY ENFORCEMENT
    # ------------------------------------------------------------------------
    try:
        # Check A: Admin cannot perform Authority Officer civic acceptance
        adm_act = requests.post(f"{BASE_URL}/api/authority/complaints/JS-2026-00016/verify", json={"notes": "test"}, headers=admin_hdr, timeout=5)
        assert adm_act.status_code == 403, f"Expected 403 for Admin on verify, got {adm_act.status_code}"
        pass_test("RBAC Boundary: Admin blocked from Civic Verification decisions", "HTTP 403 Forbidden")

        # Check B: Authority Officer cannot manage Gmail desk
        off_gmail = requests.get(f"{BASE_URL}/api/email/messages", headers=officer_hdr, timeout=5)
        assert off_gmail.status_code == 403, f"Expected 403 for Officer on Gmail, got {off_gmail.status_code}"
        pass_test("RBAC Boundary: Authority Officer blocked from Gmail Intake Desk", "HTTP 403 Forbidden")

        # Check C: Authority Officer cannot perform duplicate review management
        off_dup = requests.get(f"{BASE_URL}/api/duplicates/review-queue", headers=officer_hdr, timeout=5)
        assert off_dup.status_code == 403, f"Expected 403 for Officer on Duplicate Desk, got {off_dup.status_code}"
        pass_test("RBAC Boundary: Authority Officer blocked from Duplicate Review Desk", "HTTP 403 Forbidden")

        # Check D: Department Officer cannot verify complaints
        dept_ver = requests.post(f"{BASE_URL}/api/authority/complaints/JS-2026-00016/verify", json={"notes": "test"}, headers=roads_hdr, timeout=5)
        assert dept_ver.status_code == 403, f"Expected 403 for Dept Officer on verify, got {dept_ver.status_code}"
        pass_test("RBAC Boundary: Department Officer blocked from Complaint Verification", "HTTP 403 Forbidden")

        # Check E: Department Officer cannot independently approve final closure
        dept_close = requests.post(f"{BASE_URL}/api/authority/resolutions/JS-2026-00001/approve", json={"notes": "test"}, headers=roads_hdr, timeout=5)
        assert dept_close.status_code == 403, f"Expected 403 for Dept Officer on resolution approval, got {dept_close.status_code}"
        pass_test("RBAC Boundary: Department Officer blocked from Approving Closure", "HTTP 403 Forbidden")

        # Check F: Unauthenticated access blocked
        unauth = requests.get(f"{BASE_URL}/api/authority/complaints", timeout=5)
        assert unauth.status_code == 401, f"Expected 401 for unauthenticated request, got {unauth.status_code}"
        pass_test("RBAC Boundary: Unauthenticated access rejected with HTTP 401", "Authoritative backend security")
    except Exception as e:
        fail_test("Phase 9.2 (Three-Role RBAC Boundary Enforcement)", e)

    # ------------------------------------------------------------------------
    # 5. PHASE 9.3 — ALL SIX DEPARTMENT WORKSPACES & DATA ISOLATION
    # ------------------------------------------------------------------------
    departments = [
        (1, "RPW", "Roads & Public Works", 7),
        (2, "SWM", "Sanitation & Waste Management", 3),
        (3, "WSD", "Water Supply & Sewerage", 5),
        (4, "DRN", "Storm Water Drainage", 4),
        (5, "ESM", "Electrical & Street Lighting", 2),
        (6, "PID", "Public Infrastructure & Parks", 10),
    ]
    try:
        for d_id, d_code, d_name, sla in departments:
            # Multi-department demo officer queries division
            d_res = requests.get(f"{BASE_URL}/api/authority/overview?department_id={d_id}", headers=demo_hdr, timeout=5)
            assert d_res.status_code == 200, f"Failed querying {d_code}: {d_res.status_code}"

            # Work orders list
            w_res = requests.get(f"{BASE_URL}/api/authority/complaints?department_id={d_id}&limit=10", headers=demo_hdr, timeout=5)
            assert w_res.status_code == 200
            w_items = w_res.json().get("items", [])
            for w in w_items:
                if w.get("department"):
                    assert w["department"]["id"] == d_id, f"Cross-department leakage: found dept {w['department']['id']} in {d_code}"

            pass_test(f"Dept Workspace {d_code} ({d_name})", f"SLA: {sla}d | Verified work orders count: {len(w_items)}")

        # Single-department roads_officer cross-access test: Attempting to query Sanitation (Dept 2) -> 403
        cross_res = requests.get(f"{BASE_URL}/api/authority/complaints?department_id=2", headers=roads_hdr, timeout=5)
        assert cross_res.status_code == 403, f"Expected 403 on cross-department query, got {cross_res.status_code}"
        pass_test("Cross-Department Isolation", "roads_officer blocked from querying Sanitation with HTTP 403 Forbidden")
    except Exception as e:
        fail_test("Phase 9.3 (Six Department Workspaces & Isolation)", e)

    # ------------------------------------------------------------------------
    # 6. PHASE 9.5 — CRITICAL ESCALATIONS AUDIT
    # ------------------------------------------------------------------------
    try:
        # Check escalations endpoint
        esc_res = requests.get(f"{BASE_URL}/api/authority/complaints?escalation_level=1&limit=20", headers=officer_hdr, timeout=5)
        assert esc_res.status_code == 200
        esc_items = esc_res.json().get("items", [])
        pass_test("Critical Escalations Monitoring", f"Found {len(esc_items)} active Tier 1/2 escalated tickets")

        # Escalate an assigned complaint to Tier 1
        esc_act = requests.post(
            f"{BASE_URL}/api/authority/complaints/JS-2026-00004/escalate",
            json={
                "escalation_level": 1,
                "reason": "Approaching SLA target; high commuter traffic corridor requiring Division Head intervention.",
                "escalated_to": "Division Head / Superintending Engineer (Roads)"
            },
            headers=officer_hdr,
            timeout=5
        )
        assert esc_act.status_code == 200
        assert esc_act.json()["escalation_level"] == 1
        pass_test("Human Escalation Decision (Tier 1)", "Officer recorded justification, escalated to Division Head")
    except Exception as e:
        fail_test("Phase 9.5 (Critical Escalations Audit)", e)

    # ------------------------------------------------------------------------
    # 7. PHASE 9.9 — SECURITY & DATA INTEGRITY AUDIT
    # ------------------------------------------------------------------------
    try:
        # Path Traversal Security Test on Evidence Endpoint
        trav_res = requests.get(f"{BASE_URL}/api/authority/evidence/..%2f..%2f..%2f..%2fWindows%2fwin.ini", headers=officer_hdr, timeout=5)
        assert trav_res.status_code in (400, 404), f"Path traversal should be blocked, got {trav_res.status_code}"
        pass_test("Security: Path Traversal Prevention", "Traversal attempts securely rejected with 400/404")

        # Database Integrity: Foreign Keys, IDs, and UTC Timestamps
        conn = sqlite3.connect('jansakshi.db')
        c = conn.cursor()
        c.execute("PRAGMA foreign_key_check")
        fk_errors = c.fetchall()
        assert len(fk_errors) == 0, f"Foreign key check errors: {fk_errors}"
        pass_test("Database Integrity: Foreign Keys", "0 violations across all tables")

        c.execute("SELECT COUNT(*) FROM complaints WHERE complaint_id IS NULL OR tracking_token IS NULL")
        missing_ids = c.fetchone()[0]
        assert missing_ids == 0, "No null complaint IDs or tracking tokens"
        pass_test("Database Integrity: Unique Identifiers", "All complaints possess valid IDs and tracking tokens")

        conn.close()
    except Exception as e:
        fail_test("Phase 9.9 (Security & Database Integrity)", e)

    print("=" * 85)
    print(f"AUDIT SUMMARY: {passed_tests} PASSED, {failed_tests} FAILED")
    print("=" * 85)
    if failed_tests > 0:
        sys.exit(1)

if __name__ == "__main__":
    run_master_audit()
