import os
import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def run_checks():
    results = {}

    # 1. Check Equity route is 404
    res = requests.get(f"{BASE_URL}/api/authority/equity/overview", timeout=3)
    results["equity_route_unmounted"] = (res.status_code == 404)

    # 2. Check Auth for 3 roles
    roles = {
        "admin": ("admin", "JanSakshi@2026"),
        "officer": ("officer", "JanSakshi@2026"),
        "roads_officer": ("roads_officer", "JanSakshi@2026"),
        "dept_demo": ("dept_demo", "JanSakshi@2026")
    }
    tokens = {}
    for rname, (user, pwd) in roles.items():
        t0 = time.time()
        l_res = requests.post(f"{BASE_URL}/api/auth/login", json={"username": user, "password": pwd}, timeout=3)
        tokens[rname] = (l_res.status_code, l_res.json().get("access_token") if l_res.status_code == 200 else None, time.time() - t0)

    results["auth"] = {r: {"status": tokens[r][0], "latency_ms": round(tokens[r][2] * 1000, 1)} for r in tokens}

    # 3. Public Tracking PII Check
    track_res = requests.get(f"{BASE_URL}/api/complaints/JS-2026-00001", timeout=3)
    t_json = track_res.json() if track_res.status_code == 200 else {}
    results["public_tracking"] = {
        "status_code": track_res.status_code,
        "complaint_id": t_json.get("complaint_id"),
        "citizen_phone_exposed": "citizen_phone" in t_json or "phone" in t_json,
        "citizen_email_exposed": "citizen_email" in t_json or "email" in t_json,
        "internal_notes_exposed": "internal_notes" in t_json,
    }

    # 4. Authority Officer Decision Queue Gate Check
    off_hdr = {"Authorization": f"Bearer {tokens['officer'][1]}"}
    queue_res = requests.get(f"{BASE_URL}/api/authority/complaints?verification_status=pending", headers=off_hdr, timeout=3)
    q_data = queue_res.json() if queue_res.status_code == 200 else {}
    q_items = q_data.get("items", [])
    results["decision_queue"] = {
        "status_code": queue_res.status_code,
        "count": len(q_items),
        "contains_js_00022": any(c.get("complaint_id") == "JS-2026-00022" for c in q_items),
        "all_have_gps": all(c.get("latitude") is not None and c.get("longitude") is not None for c in q_items)
    }

    # 5. Department Isolation Matrix
    roads_hdr = {"Authorization": f"Bearer {tokens['roads_officer'][1]}"}
    dept_results = {}
    for d_id, d_code in [(1, "RPW"), (2, "SWM"), (3, "WSD"), (4, "DRN"), (5, "ESM"), (6, "PID")]:
        r = requests.get(f"{BASE_URL}/api/authority/complaints?department_id={d_id}", headers=roads_hdr, timeout=3)
        res_data = r.json() if r.status_code == 200 else {}
        dept_results[d_code] = {
            "status_code": r.status_code,
            "access_allowed": r.status_code == 200,
            "work_orders_count": len(res_data.get("items", [])) if r.status_code == 200 else 0
        }
    results["department_isolation_roads_officer"] = dept_results

    # 6. Duplicate Match Math & Retrieval
    adm_hdr = {"Authorization": f"Bearer {tokens['admin'][1]}"}
    dup_res = requests.get(f"{BASE_URL}/api/duplicates/review-queue", headers=adm_hdr, timeout=3)
    dup_items = dup_res.json() if dup_res.status_code == 200 else []
    results["duplicate_queue"] = {
        "status_code": dup_res.status_code,
        "count": len(dup_items)
    }

    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    run_checks()
