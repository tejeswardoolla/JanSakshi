import urllib.request
import urllib.parse
import json
import sys
import requests

BASE_URL = "http://127.0.0.1:8000"

def login(username, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, f"Login failed for {username}: {r.text}"
    return r.json()

def api_call(path, method="GET", token=None, body=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except:
            return e.code, str(e)

def test_rbac_rules():
    print("=== Testing Staff & Authority Portal RBAC Boundaries ===")
    
    # 1. Login as Admin
    print("\n1. Testing ADMIN role...")
    admin_auth = login("admin", "JanSakshi@2026")
    admin_token = admin_auth["access_token"]
    print(f"   Admin Logged In: {admin_auth['user']['full_name']} (Role: {admin_auth['user']['role']})")
    
    # Admin CAN mark-ready
    status, res = api_call("/api/authority/complaints/JS-2026-00001/mark-ready", "POST", admin_token, {"notes": "Intake verified."})
    print(f"   Admin mark-ready test: Status {status}")
    assert status == 200, f"Admin should be able to mark-ready, got {status}: {res}"
    
    # Admin CANNOT verify civic complaints
    status, res = api_call("/api/authority/complaints/JS-2026-00001/verify", "POST", admin_token, {"notes": "Unauthorized verify"})
    print(f"   Admin verify rejection test: Status {status} (Expected 403)")
    assert status == 403, f"Admin should be blocked with 403 on verify, got {status}: {res}"
    
    # Admin CANNOT assign department
    status, res = api_call("/api/authority/complaints/JS-2026-00001/assign", "POST", admin_token, {"department_id": 1})
    print(f"   Admin assign department rejection test: Status {status} (Expected 403)")
    assert status == 403, f"Admin should be blocked with 403 on assign, got {status}: {res}"

    # 2. Login as Authority Officer
    print("\n2. Testing AUTHORITY OFFICER role...")
    officer_auth = login("officer", "JanSakshi@2026")
    officer_token = officer_auth["access_token"]
    print(f"   Authority Officer Logged In: {officer_auth['user']['full_name']} (Role: {officer_auth['user']['role']})")
    
    # Authority Officer CAN verify
    status, res = api_call("/api/authority/complaints/JS-2026-00001/verify", "POST", officer_token, {"notes": "Approved by Officer."})
    print(f"   Officer verify test: Status {status}")
    assert status == 200, f"Officer should be able to verify, got {status}: {res}"
    
    # Authority Officer CAN assign department & priority
    status, res = api_call("/api/authority/complaints/JS-2026-00001/assign", "POST", officer_token, {
        "department_id": 1,
        "priority": "High",
        "expected_completion_days": 3,
        "notes": "Urgent pothole repair."
    })
    print(f"   Officer assign department test: Status {status}")
    assert status == 200, f"Officer should be able to assign department, got {status}: {res}"
    
    # Authority Officer CANNOT call admin mark-ready
    status, res = api_call("/api/authority/complaints/JS-2026-00001/mark-ready", "POST", officer_token, {"notes": "Try mark-ready"})
    print(f"   Officer mark-ready rejection test: Status {status} (Expected 403)")
    assert status == 403, f"Officer should be blocked with 403 on mark-ready, got {status}: {res}"

    # 3. Login as Roads Officer (Restricted Dept Officer)
    print("\n3. Testing ROADS OFFICER (RPW Only)...")
    roads_auth = login("roads_officer", "JanSakshi@2026")
    roads_token = roads_auth["access_token"]
    print(f"   Roads Officer Logged In: {roads_auth['user']['full_name']} (Allowed Depts: {roads_auth['user'].get('authorized_departments')})")
    
    # Roads Officer CANNOT verify citizen complaints
    status, res = api_call("/api/authority/complaints/JS-2026-00001/verify", "POST", roads_token, {"notes": "Try verify"})
    print(f"   Roads officer verify rejection test: Status {status} (Expected 403)")
    assert status == 403, f"Roads officer must not verify complaints, got {status}: {res}"
    
    # Roads Officer CANNOT mark complaint Resolved directly (must be submitted for review)
    status, res = api_call("/api/authority/complaints/JS-2026-00001/status", "POST", roads_token, {"status": "Resolved"})
    print(f"   Roads officer direct 'Resolved' rejection test: Status {status} (Expected 403)")
    assert status == 403, f"Dept officer cannot directly set status to Resolved, got {status}: {res}"
    
    # Roads Officer CAN update status to 'In Progress' or 'Resolution Submitted'
    status, res = api_call("/api/authority/complaints/JS-2026-00001/status", "POST", roads_token, {"status": "In Progress", "notes": "Work started"})
    print(f"   Roads officer set 'In Progress': Status {status}")
    assert status == 200, f"Dept officer should be able to set In Progress, got {status}: {res}"
    
    # 4. Login as Multi-Dept Demo Officer
    print("\n4. Testing DEPT_DEMO Multi-Department Officer...")
    demo_auth = login("dept_demo", "JanSakshi@2026")
    demo_token = demo_auth["access_token"]
    print(f"   Dept Demo Officer Logged In: {demo_auth['user']['full_name']} (Allowed Depts: {demo_auth['user'].get('authorized_departments')})")
    assert len(demo_auth['user'].get('authorized_departments', [])) == 6, "dept_demo must have all 6 departments authorized"

    print("\n=== ALL RBAC BOUNDARY TESTS PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    test_rbac_rules()
