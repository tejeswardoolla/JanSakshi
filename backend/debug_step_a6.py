import requests

roads_token = requests.post("http://127.0.0.1:8000/api/auth/login", json={"username": "roads_officer", "password": "JanSakshi@2026"}).json()["access_token"]
roads_hdr = {"Authorization": f"Bearer {roads_token}"}

cid = "JS-2026-00023"
dummy_jpg = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00" + b"X" * 200

res = requests.post(
    f"http://127.0.0.1:8000/api/authority/complaints/{cid}/evidence",
    files={"file": ("v1_patch.jpg", dummy_jpg, "image/jpeg")},
    data={"evidence_type": "after_repair", "notes": "Preliminary asphalt fill completed."},
    headers=roads_hdr
)
print("Evidence upload status:", res.status_code, res.text)
if res.status_code == 200:
    eid = res.json().get("id") or res.json().get("evidence_id")
    print("EID:", eid, res.json())
    sub_res = requests.post(
        f"http://127.0.0.1:8000/api/authority/resolutions/{cid}/submit",
        json={
            "completion_summary": "Pothole filled with standard bitumin mix.",
            "work_order_cost": 4500.0,
            "contractor_name": "Municipal Road Maintenance Wing",
            "repair_duration_hours": 4.0,
            "evidence_ids": [eid]
        },
        headers=roads_hdr
    )
    print("Submit resolution status:", sub_res.status_code, sub_res.text)
