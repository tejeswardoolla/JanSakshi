import urllib.request
import urllib.parse
import json

BASE = "http://127.0.0.1:8000"

def post_multipart(fields, files):
    boundary = "----JanSakshiFormBoundary7MA4YWxkTrZu0gW"
    data = []
    for name, value in fields.items():
        data.append(f"--{boundary}".encode())
        data.append(f'Content-Disposition: form-data; name="{name}"'.encode())
        data.append(b"")
        data.append(str(value).encode())

    for name, (filename, content, content_type) in files.items():
        data.append(f"--{boundary}".encode())
        data.append(f'Content-Disposition: form-data; name="{name}"; filename="{filename}"'.encode())
        data.append(f'Content-Type: {content_type}'.encode())
        data.append(b"")
        data.append(content)

    data.append(f"--{boundary}--".encode())
    data.append(b"")
    body = b"\r\n".join(data)

    req = urllib.request.Request(
        f"{BASE}/api/complaints/",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    with urllib.request.urlopen(req) as res:
        return res.status, json.loads(res.read().decode())

print("Testing Pipeline via Multipart Submission...")
jpg_header = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00" + b"X" * 300
status_code, resp = post_multipart(
    fields={
        "category": "Broken Streetlights",
        "description": "Entire lane dark because fixture glass broke and bulb fell out.",
        "latitude": 17.4400,
        "longitude": 78.4500,
        "location_accuracy": 5.0,
        "location_source": "gps",
        "citizen_name": "Deepa Sundaram"
    },
    files={
        "evidence": ("streetlight.jpg", jpg_header, "image/jpeg")
    }
)
print("Pipeline Submission result:", status_code, resp)
new_cid = resp.get("complaint_id")
assert status_code == 201
assert new_cid.startswith("JS-2026-")

# Check Audit Events
req = urllib.request.Request(f"{BASE}/api/complaints/{new_cid}/events")
with urllib.request.urlopen(req) as res:
    events = json.loads(res.read().decode())
print(f"Events recorded by pipeline for {new_cid}:")
for ev in events:
    print(f"  - [{ev['event_type']}] {ev['description']} (Source: {ev['source']})")

event_types = [ev["event_type"] for ev in events]
assert "complaint_received" in event_types
assert "evidence_uploaded" in event_types
assert "background_processing_queued" in event_types
print("\nPIPELINE & BACKGROUND TASK INTEGRATION VERIFIED!")

