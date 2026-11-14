import os
import sys
import time
import json
import urllib.parse
import subprocess
import requests

EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
BASE_API = "http://127.0.0.1:8000"
BASE_WEB = "http://127.0.0.1:5173"

def get_credentials(username, password="JanSakshi@2026"):
    r = requests.post(f"{BASE_API}/api/auth/login", json={"username": username, "password": password})
    if r.status_code != 200:
        raise Exception(f"Login failed for {username}: {r.text}")
    data = r.json()
    return data["access_token"], json.dumps(data["user"])

def capture_url(url, output_path, width=1280, height=800, wait_budget=4000):
    cmd = [
        EDGE_PATH,
        "--headless=new",
        "--disable-gpu",
        f"--window-size={width},{height}",
        f"--virtual-time-budget={wait_budget}",
        f"--screenshot={output_path}",
        url
    ]
    print(f"Capturing: {url} -> {output_path}")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if os.path.exists(output_path):
        size = os.path.getsize(output_path)
        print(f"Success! {output_path} ({size} bytes)")
    else:
        print(f"Error capturing {output_path}: {res.stderr}")

def main():
    print("Obtaining role tokens...")
    admin_token, admin_user = get_credentials("admin")
    officer_token, officer_user = get_credentials("officer")
    roads_token, roads_user = get_credentials("roads_officer")
    print("Tokens retrieved.")

    # 1. Citizen Portal
    capture_url(
        f"{BASE_WEB}/",
        r"C:\Users\TEJESWAR\Desktop\JanSakshi\figure_1_citizen_portal.png",
        width=1280, height=800, wait_budget=3500
    )

    # 2. Admin Dashboard
    q_admin = urllib.parse.urlencode({"demo_token": admin_token, "demo_user": admin_user})
    capture_url(
        f"{BASE_WEB}/authority?{q_admin}",
        r"C:\Users\TEJESWAR\Desktop\JanSakshi\figure_2_admin_dashboard.png",
        width=1280, height=800, wait_budget=4500
    )

    # 3. Authority Officer Dashboard
    q_officer = urllib.parse.urlencode({"demo_token": officer_token, "demo_user": officer_user})
    capture_url(
        f"{BASE_WEB}/authority?{q_officer}",
        r"C:\Users\TEJESWAR\Desktop\JanSakshi\figure_3_authority_dashboard.png",
        width=1280, height=800, wait_budget=4500
    )

    # 4. Department Officer Workflow
    q_roads = urllib.parse.urlencode({"dept": "1", "demo_token": roads_token, "demo_user": roads_user})
    capture_url(
        f"{BASE_WEB}/authority?{q_roads}",
        r"C:\Users\TEJESWAR\Desktop\JanSakshi\figure_4_department_workflow.png",
        width=1280, height=800, wait_budget=4500
    )

if __name__ == "__main__":
    main()

