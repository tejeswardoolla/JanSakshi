import os
import sys
import time
import json
import requests
from playwright.sync_api import sync_playwright

BASE_API = "http://127.0.0.1:8000"
BASE_WEB = "http://localhost:5173"
SCREENSHOTS_DIR = os.path.abspath("screenshots")
SAMPLE_PHOTO = os.path.abspath(r"backend\storage\evidence\0042164933dd42899cab6e12b6549b13.jpg")
EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

def get_auth_data(username, password="JanSakshi@2026"):
    r = requests.post(f"{BASE_API}/api/auth/login", json={"username": username, "password": password})
    if r.status_code != 200:
        raise Exception(f"Login failed for {username}: {r.text}")
    data = r.json()
    return data["access_token"], data["user"]

def apply_privacy_mask(page):
    """Mask citizen email and phone numbers for privacy."""
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

def set_auth_session(page, token, user):
    page.evaluate(f"""() => {{
        localStorage.setItem('jansakshi_authority_token', {json.dumps(token)});
        localStorage.setItem('jansakshi_authority_user', JSON.stringify({json.dumps(user)}));
    }}""")

def clear_auth_session(page):
    page.evaluate("""() => {
        localStorage.removeItem('jansakshi_authority_token');
        localStorage.removeItem('jansakshi_authority_user');
    }""")

def main():
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    print("Obtaining authority auth tokens...")
    admin_token, admin_user = get_auth_data("admin")
    officer_token, officer_user = get_auth_data("officer")
    roads_token, roads_user = get_auth_data("roads_officer")
    print("Tokens retrieved successfully.")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=EDGE_PATH,
            headless=True
        )

        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            geolocation={"latitude": 17.0005, "longitude": 81.8040},
            permissions=["geolocation"]
        )

        page = context.new_page()

        # ---------------------------------------------------------------------
        # 01_citizen_homepage.png
        # ---------------------------------------------------------------------
        print("\n[1/10] Capturing 01_citizen_homepage.png...")
        page.goto(f"{BASE_WEB}/", wait_until="networkidle")
        clear_auth_session(page)
        page.reload(wait_until="networkidle")
        time.sleep(2)
        apply_privacy_mask(page)
        path_01 = os.path.join(SCREENSHOTS_DIR, "01_citizen_homepage.png")
        page.screenshot(path=path_01, full_page=False)
        print(f"Saved: {path_01} ({os.path.getsize(path_01)} bytes)")

        # ---------------------------------------------------------------------
        # 02_report_form.png
        # ---------------------------------------------------------------------
        print("\n[2/10] Capturing 02_report_form.png...")
        page.goto(f"{BASE_WEB}/report", wait_until="networkidle")
        time.sleep(1)

        # Select category: Road Damage / Potholes
        try:
            page.locator("button:has-text('Road Damage')").click()
        except:
            pass

        # Enter description
        try:
            desc_area = page.locator("textarea#description, textarea[placeholder*='describe' i], textarea").first
            desc_area.fill("Deep asphalt trench pothole at Morampudi Junction creating hazardous traffic conditions.")
        except Exception as e:
            print("Notice on description:", e)

        # Upload photo
        try:
            file_input = page.locator("input[type=file]").first
            if os.path.exists(SAMPLE_PHOTO):
                file_input.set_input_files(SAMPLE_PHOTO)
                time.sleep(1.5)
        except Exception as e:
            print("Notice on file upload:", e)

        # Trigger GPS / Location capture
        try:
            gps_btn = page.locator("button:has-text('Use GPS'), button:has-text('Current Location'), button:has-text('GPS')").first
            if gps_btn.is_visible():
                gps_btn.click()
                time.sleep(2)
        except Exception as e:
            print("Notice on GPS click:", e)

        # Citizen contact info
        try:
            page.locator("input[placeholder*='name' i], input#citizen_name").first.fill("Suresh Varma")
            page.locator("input[placeholder*='phone' i], input#citizen_phone").first.fill("+91 98765 43210")
            page.locator("input[placeholder*='email' i], input#citizen_email").first.fill("citizen.demo@example.com")
        except:
            pass

        time.sleep(2)
        apply_privacy_mask(page)
        path_02 = os.path.join(SCREENSHOTS_DIR, "02_report_form.png")
        page.screenshot(path=path_02, full_page=False)
        print(f"Saved: {path_02} ({os.path.getsize(path_02)} bytes)")

        # ---------------------------------------------------------------------
        # 03_public_tracking.png
        # ---------------------------------------------------------------------
        print("\n[3/10] Capturing 03_public_tracking.png...")
        page.goto(f"{BASE_WEB}/track?id=JS-2026-00028", wait_until="networkidle")
        time.sleep(2.5)
        apply_privacy_mask(page)
        path_03 = os.path.join(SCREENSHOTS_DIR, "03_public_tracking.png")
        page.screenshot(path=path_03, full_page=False)
        print(f"Saved: {path_03} ({os.path.getsize(path_03)} bytes)")

        # ---------------------------------------------------------------------
        # 04_staff_login.png
        # ---------------------------------------------------------------------
        print("\n[4/10] Capturing 04_staff_login.png...")
        page.goto(f"{BASE_WEB}/authority/login", wait_until="networkidle")
        clear_auth_session(page)
        page.reload(wait_until="networkidle")
        time.sleep(2)
        path_04 = os.path.join(SCREENSHOTS_DIR, "04_staff_login.png")
        page.screenshot(path=path_04, full_page=False)
        print(f"Saved: {path_04} ({os.path.getsize(path_04)} bytes)")

        # ---------------------------------------------------------------------
        # 05_admin_management_centre.png
        # ---------------------------------------------------------------------
        print("\n[5/10] Capturing 05_admin_management_centre.png...")
        page.goto(f"{BASE_WEB}/authority", wait_until="networkidle")
        set_auth_session(page, admin_token, admin_user)
        page.goto(f"{BASE_WEB}/authority", wait_until="networkidle")
        time.sleep(3)
        apply_privacy_mask(page)
        path_05 = os.path.join(SCREENSHOTS_DIR, "05_admin_management_centre.png")
        page.screenshot(path=path_05, full_page=False)
        print(f"Saved: {path_05} ({os.path.getsize(path_05)} bytes)")

        # ---------------------------------------------------------------------
        # 06_gmail_intake_desk.png
        # ---------------------------------------------------------------------
        print("\n[6/10] Capturing 06_gmail_intake_desk.png...")
        page.goto(f"{BASE_WEB}/authority/email-management", wait_until="networkidle")
        time.sleep(2.5)
        apply_privacy_mask(page)
        path_06 = os.path.join(SCREENSHOTS_DIR, "06_gmail_intake_desk.png")
        page.screenshot(path=path_06, full_page=False)
        print(f"Saved: {path_06} ({os.path.getsize(path_06)} bytes)")

        # ---------------------------------------------------------------------
        # 07_duplicate_review_desk.png
        # ---------------------------------------------------------------------
        print("\n[7/10] Capturing 07_duplicate_review_desk.png...")
        page.goto(f"{BASE_WEB}/authority/duplicates", wait_until="networkidle")
        time.sleep(2.5)
        apply_privacy_mask(page)
        path_07 = os.path.join(SCREENSHOTS_DIR, "07_duplicate_review_desk.png")
        page.screenshot(path=path_07, full_page=False)
        print(f"Saved: {path_07} ({os.path.getsize(path_07)} bytes)")

        # ---------------------------------------------------------------------
        # 08_authority_dispatch_dialog.png
        # ---------------------------------------------------------------------
        print("\n[8/10] Capturing 08_authority_dispatch_dialog.png...")
        # Log in as officer
        page.goto(f"{BASE_WEB}/authority", wait_until="networkidle")
        set_auth_session(page, officer_token, officer_user)
        page.goto(f"{BASE_WEB}/authority", wait_until="networkidle")
        time.sleep(2.5)

        # Click Department Dispatch tab
        dispatch_tab = page.locator("button:has-text('Department Dispatch')").first
        if dispatch_tab.is_visible():
            dispatch_tab.click()
            time.sleep(1.5)

        # Click Dispatch button to open 7-field modal
        dispatch_btn = page.locator("button:has-text('Dispatch')").first
        if dispatch_btn.is_visible():
            dispatch_btn.click()
            time.sleep(1.5)

        apply_privacy_mask(page)
        path_08 = os.path.join(SCREENSHOTS_DIR, "08_authority_dispatch_dialog.png")
        page.screenshot(path=path_08, full_page=False)
        print(f"Saved: {path_08} ({os.path.getsize(path_08)} bytes)")

        # ---------------------------------------------------------------------
        # 09_department_workspace.png
        # ---------------------------------------------------------------------
        print("\n[9/10] Capturing 09_department_workspace.png...")
        page.goto(f"{BASE_WEB}/authority?dept=1", wait_until="networkidle")
        set_auth_session(page, roads_token, roads_user)
        page.goto(f"{BASE_WEB}/authority?dept=1", wait_until="networkidle")
        time.sleep(3)
        apply_privacy_mask(page)
        path_09 = os.path.join(SCREENSHOTS_DIR, "09_department_workspace.png")
        page.screenshot(path=path_09, full_page=False)
        print(f"Saved: {path_09} ({os.path.getsize(path_09)} bytes)")

        # ---------------------------------------------------------------------
        # 10_resolution_review_desk.png
        # ---------------------------------------------------------------------
        print("\n[10/10] Capturing 10_resolution_review_desk.png...")
        # Log in as officer and view resolution review detail for complaint JS-2026-00028 (submission ID 18)
        set_auth_session(page, officer_token, officer_user)
        page.goto(f"{BASE_WEB}/authority/resolution-review/18", wait_until="networkidle")
        time.sleep(3)
        apply_privacy_mask(page)
        path_10 = os.path.join(SCREENSHOTS_DIR, "10_resolution_review_desk.png")
        page.screenshot(path=path_10, full_page=False)
        print(f"Saved: {path_10} ({os.path.getsize(path_10)} bytes)")

        browser.close()
        print("\nAll 10 requested screenshots captured successfully!")

if __name__ == "__main__":
    main()
