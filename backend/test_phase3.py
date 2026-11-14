import urllib.request
import urllib.parse
import json

BASE = "http://127.0.0.1:8000"

def get(path):
    req = urllib.request.Request(f"{BASE}{path}")
    with urllib.request.urlopen(req) as res:
        return res.status, json.loads(res.read().decode())

def post(path, data):
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(f"{BASE}{path}", data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as res:
            return res.status, json.loads(res.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())

print("=== JANSAKSHI PHASE 3 TEST SUITE ===")

# Test 1: Health
s, d = get("/api/health")
print(f"1. Health Check: status={s}, phase={d.get('phase')}")
assert s == 200 and d.get("phase") in (3, 4, 5, 6)

# Test 2: Existing Complaint Verification & UTC/IST Timestamp Check
s, c1 = get("/api/complaints/JS-2026-00001")
print(f"2. Existing Complaint JS-2026-00001: status={s}, created_at={c1.get('created_at')}, issue_id={c1.get('issue_id')}")
assert s == 200 and c1.get("created_at").endswith("Z")

# Test 3: Create Physical Issue
issue_payload = {
    "category": "Road Damage / Potholes",
    "representative_latitude": 17.4375,
    "representative_longitude": 78.4482,
    "representative_location": "Inner Ring Road Junction, Ward 12",
    "description": "Cluster of recurrent potholes along the eastbound fast lane."
}
s, issue1 = post("/api/issues/", issue_payload)
print(f"3. Create Physical Issue: status={s}, issue_id={issue1.get('issue_reference_id')}")
assert s == 201
issue_ref = issue1.get("issue_reference_id")
assert issue_ref.startswith("ISSUE-2026-")

# Test 4: Retrieve Physical Issue
s, issue_retrieved = get(f"/api/issues/{issue_ref}")
print(f"4. Retrieve Physical Issue: status={s}, status={issue_retrieved.get('current_status')}, desc={issue_retrieved.get('description')[:30]}...")
assert s == 200 and issue_retrieved.get("issue_reference_id") == issue_ref

# Test 5: Associate Complaints with Physical Issue (Multiple Complaints -> 1 Physical Issue)
# Associate JS-2026-00001
s, a1 = post(f"/api/complaints/JS-2026-00001/associate-issue", {"issue_reference_id": issue_ref, "source": "admin"})
print(f"5a. Associate JS-2026-00001 to {issue_ref}: status={s}, issue_id={a1.get('issue_id')}")
assert s == 200 and a1.get("issue_id") == issue_ref

# Associate JS-2026-00004
s, a2 = post(f"/api/complaints/JS-2026-00004/associate-issue", {"issue_reference_id": issue_ref, "source": "admin"})
print(f"5b. Associate JS-2026-00004 to {issue_ref}: status={s}, issue_id={a2.get('issue_id')}")
assert s == 200 and a2.get("issue_id") == issue_ref

# Test 6: Verify Complaints Under Physical Issue (Complaints preserved independently)
s, issue_complaints = get(f"/api/issues/{issue_ref}/complaints")
print(f"6. Issue Complaints List: status={s}, count={len(issue_complaints)}")
assert s == 200 and len(issue_complaints) == 2
c_ids = [c["complaint_id"] for c in issue_complaints]
print(f"   Associated complaint IDs: {c_ids}")
assert "JS-2026-00001" in c_ids and "JS-2026-00004" in c_ids

# Test 7: Verify Original Complaints Remain Independently Retrievable
s, c1_check = get("/api/complaints/JS-2026-00001")
s, c4_check = get("/api/complaints/JS-2026-00004")
assert c1_check.get("complaint_id") == "JS-2026-00001" and c1_check.get("issue_id") == issue_ref
assert c4_check.get("complaint_id") == "JS-2026-00004" and c4_check.get("issue_id") == issue_ref
print(f"7. Individual retrieval check passed: JS-2026-00001 and JS-2026-00004 maintain unique identity")

# Test 8: Audit Events Retrieval for Complaint
s, events = get("/api/complaints/JS-2026-00001/events")
print(f"8. Audit Events for JS-2026-00001: status={s}, events_count={len(events)}")
assert s == 200 and len(events) >= 1
print(f"   Latest event: type={events[-1].get('event_type')}, desc={events[-1].get('description')}")
assert events[-1].get("event_type") == "complaint_associated_with_issue"

# Test 9: Reject Association with Non-Existent Issue
s, err_assoc = post("/api/complaints/JS-2026-00001/associate-issue", {"issue_reference_id": "ISSUE-2026-99999", "source": "admin"})
print(f"9. Invalid Issue Association Rejection: status={s}, error={err_assoc.get('detail')}")
assert s == 404

# Test 10: Disassociate Complaint (Reversibility check)
s, disassoc = post("/api/complaints/JS-2026-00004/associate-issue", {"issue_reference_id": None, "source": "admin"})
print(f"10. Disassociate JS-2026-00004: status={s}, issue_id={disassoc.get('issue_id')}")
assert s == 200 and disassoc.get("issue_id") is None
s, issue_complaints_after = get(f"/api/issues/{issue_ref}/complaints")
assert len(issue_complaints_after) == 1
print(f"    Issue now has {len(issue_complaints_after)} complaint associated")

# Re-associate to keep clean test state
post(f"/api/complaints/JS-2026-00004/associate-issue", {"issue_reference_id": issue_ref, "source": "admin"})

print("\nALL BACKEND ARCHITECTURE & PIPELINE TESTS PASSED!")

