import os
import json
import time
import requests
from playwright.sync_api import sync_playwright

BASE_API = "http://127.0.0.1:8000"
BASE_WEB = "http://localhost:5173"
EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

r = requests.post(f"{BASE_API}/api/auth/login", json={"username": "officer", "password": "JanSakshi@2026"})
token = r.json()["access_token"]
user = r.json()["user"]

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=EDGE_PATH, headless=True)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.goto(f"{BASE_WEB}/")
    page.evaluate(f"""() => {{
        localStorage.setItem('jansakshi_authority_token', {json.dumps(token)});
        localStorage.setItem('jansakshi_authority_user', JSON.stringify({json.dumps(user)}));
    }}""")
    
    print("Navigating to resolution review detail (submission 18)...")
    page.goto(f"{BASE_WEB}/authority/resolution-review/18", wait_until="networkidle")
    time.sleep(3)
    
    # Check title / content
    text = page.locator("body").inner_text()
    print("Page preview text:", repr(text[:300]))
    
    path = os.path.join("screenshots", "10_resolution_review_desk.png")
    page.screenshot(path=path, full_page=False)
    print(f"Captured: {path} ({os.path.getsize(path)} bytes)")
    browser.close()

