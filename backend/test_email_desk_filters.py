import requests

BASE_URL = "http://127.0.0.1:8000"

def run_tests():
    r_login = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "admin", "password": "JanSakshi@2026"})
    assert r_login.status_code == 200, f"Login failed: {r_login.text}"
    headers = {"Authorization": f"Bearer {r_login.json()['access_token']}"}

    r_status = requests.get(f"{BASE_URL}/api/email/status", headers=headers)
    assert r_status.status_code == 200, f"Status failed: {r_status.text}"
    status_data = r_status.json()

    print("=" * 80)
    print("JANSAKSHI GMAIL INTAKE DESK — STATS & FILTER VERIFICATION")
    print("=" * 80)
    print(f"Total Received:          {status_data['total_messages_received']}")
    print(f"Complaints Registered:   {status_data['total_processed']}")
    print(f"Needs Review:            {status_data['total_needs_review']}")
    print(f"Awaiting Location:       {status_data['total_awaiting_info']}")
    print(f"Non-Civic Ignored:       {status_data['total_ignored']}")
    print(f"Failures:                {status_data['total_failed']}")
    print("-" * 80)

    filters = [
        ("", status_data["total_messages_received"], "All Ingested"),
        ("needs_review", status_data["total_needs_review"], "Needs Review"),
        ("processed", status_data["total_processed"], "Processed (Complaints)"),
        ("awaiting_information", status_data["total_awaiting_info"], "Awaiting Location"),
        ("ignored", status_data["total_ignored"], "Non-Civic Ignored"),
        ("failed", status_data["total_failed"], "Failures"),
    ]

    all_passed = True
    for filter_val, expected, label in filters:
        url = f"{BASE_URL}/api/email/messages"
        if filter_val:
            url += f"?status={filter_val}"
        r = requests.get(url, headers=headers)
        assert r.status_code == 200, f"Failed for {label}: {r.status_code} {r.text}"
        data = r.json()
        count = len(data)
        passed = (count == expected)
        if not passed:
            all_passed = False
        mark = "✅ PASS" if passed else "❌ FAIL"
        print(f"{mark} | Filter: {label:<24} | Fetched: {count:<3} | Expected Counter: {expected:<3} | Endpoint: {url}")

    print("=" * 80)
    if all_passed:
        print("ALL 6 GMAIL DESK FILTERS EXACTLY MATCH DASHBOARD COUNTERS (100% PASS)!")
    else:
        print("FILTER VERIFICATION MISMATCH OCCURRED!")
    print("=" * 80)
    assert all_passed

if __name__ == "__main__":
    run_tests()

