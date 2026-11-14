import os
import json
import time
import requests
from playwright.sync_api import sync_playwright

BASE_API = "http://127.0.0.1:8000"
BASE_WEB = "http://localhost:5173"
EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

r = requests.post(f"{BASE_API}/api/auth/login", json={"username": "admin", "password": "JanSakshi@2026"})
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
    
    print("Loading /authority/email-management...")
    page.goto(f"{BASE_WEB}/authority/email-management", wait_until="networkidle")
    time.sleep(3)
    
    text = page.locator("body").inner_text()
    has_error = "Could not validate authority credentials or session expired" in text
    has_emails = "Deep road crater" in text or "Ravi Kumar" in text or "citizen" in text
    print("Has auth error banner?:", has_error)
    print("Loaded ingested emails?:", has_emails)
    
    # Apply privacy mask and save
    page.evaluate("""() => {
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
        let node;
        const emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}/g;
        const phoneRegex = /(\\+91[\\-\\s]?)?[6-9]\\d{9}|\\+?[0-9]{2,3}[\\-\\s]?[0-9]{4,5}[\\-\\s]?[0-9]{4,5}/g;
        const nodesToReplace = [];
        while (node = walker.nextNode()) {
            if (emailRegex.test(node.nodeValue) || phoneRegex.test(node.nodeValue)) {
                nodesToReplace.push(node);
            }
        }
        for (const n of nodesToReplace) {
            n.nodeValue = n.nodeValue
                .replace(emailRegex, 'citizen***@***.***')
                .replace(phoneRegex, '+91 *****-*****');
        }
    }""")
    
    path = os.path.join("screenshots", "06_gmail_intake_desk.png")
    page.screenshot(path=path, full_page=False)
    print(f"Captured: {path} ({os.path.getsize(path)} bytes)")

    # Also re-check 07_duplicate_review_desk.png
    print("\nLoading /authority/duplicates...")
    page.goto(f"{BASE_WEB}/authority/duplicates", wait_until="networkidle")
    time.sleep(3)
    text_dup = page.locator("body").inner_text()
    print("Has duplicate error?:", "Failed to load review queue" in text_dup or "Could not validate" in text_dup)
    
    path_dup = os.path.join("screenshots", "07_duplicate_review_desk.png")
    page.screenshot(path=path_dup, full_page=False)
    print(f"Captured: {path_dup} ({os.path.getsize(path_dup)} bytes)")
    
    browser.close()

