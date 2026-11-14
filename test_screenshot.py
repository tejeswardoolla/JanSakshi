import subprocess
import os
import tempfile

edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
out_img = r"C:\Users\TEJESWAR\Desktop\JanSakshi\test_edge.png"

with tempfile.TemporaryDirectory() as tmp_dir:
    cmd = [
        edge_path,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        f"--user-data-dir={tmp_dir}",
        "--virtual-time-budget=2000",
        f"--screenshot={out_img}",
        "--window-size=1280,800",
        "http://localhost:5173/"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    print("Return code:", res.returncode)

print("File created:", os.path.exists(out_img))
if os.path.exists(out_img):
    print("File size:", os.path.getsize(out_img))
