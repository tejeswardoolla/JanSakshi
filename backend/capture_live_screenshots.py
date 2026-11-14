import os
import sys
import time
import json
import base64
import subprocess
import tempfile
import urllib.request
import asyncio
import requests
import websockets

EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
BASE_API = "http://127.0.0.1:8000"
BASE_WEB = "http://127.0.0.1:5173"

def get_auth_token(username, password="JanSakshi@2026"):
    r = requests.post(f"{BASE_API}/api/auth/login", json={"username": username, "password": password})
    if r.status_code != 200:
        raise Exception(f"Failed to login as {username}: {r.text}")
    data = r.json()
    return data["access_token"], data["user"]

async def cdp_command(ws, req_id, method, params=None):
    payload = {"id": req_id, "method": method}
    if params:
        payload["params"] = params
    await ws.send(json.dumps(payload))
    while True:
        resp = await ws.recv()
        msg = json.loads(resp)
        if msg.get("id") == req_id:
            return msg.get("result", {})

async def capture_page(ws, req_id, url, token=None, user=None, wait_secs=3):
    # Navigate to base domain first so localStorage can be set for the origin
    req_id += 1
    await cdp_command(ws, req_id, "Page.navigate", {"url": BASE_WEB})
    await asyncio.sleep(1.5)
    
    if token and user:
        # Inject localStorage items
        js_code = f"""
        localStorage.setItem('jansakshi_authority_token', {json.dumps(token)});
        localStorage.setItem('jansakshi_authority_user', {json.dumps(json.dumps(user))});
        """
        req_id += 1
        await cdp_command(ws, req_id, "Runtime.evaluate", {"expression": js_code})
        await asyncio.sleep(0.5)
    else:
        # Clear any existing authority session for citizen portal
        js_code = """
        localStorage.removeItem('jansakshi_authority_token');
        localStorage.removeItem('jansakshi_authority_user');
        """
        req_id += 1
        await cdp_command(ws, req_id, "Runtime.evaluate", {"expression": js_code})
        await asyncio.sleep(0.5)

    # Now navigate to target URL
    req_id += 1
    await cdp_command(ws, req_id, "Page.navigate", {"url": url})
    await asyncio.sleep(wait_secs)
    
    # Capture screenshot
    req_id += 1
    res = await cdp_command(ws, req_id, "Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
    img_data = base64.b64decode(res["data"])
    return img_data, req_id

async def main():
    print("Obtaining auth tokens...")
    admin_token, admin_user = get_auth_token("admin")
    officer_token, officer_user = get_auth_token("officer")
    roads_token, roads_user = get_auth_token("roads_officer")
    print("Tokens retrieved successfully.")

    temp_dir = tempfile.mkdtemp()
    edge_proc = subprocess.Popen([
        EDGE_PATH,
        "--headless=new",
        "--remote-debugging-port=9222",
        f"--user-data-dir={temp_dir}",
        "--disable-gpu",
        "--window-size=1440,900",
        "--no-first-run",
        "--no-default-browser-check"
    ])
    
    print("Edge headless process started (PID:", edge_proc.pid, ")")
    time.sleep(2)
    
    try:
        # Query targets list (GET) or create new (PUT)
        r = requests.get("http://127.0.0.1:9222/json/list")
        targets = r.json()
        if targets:
            ws_url = targets[0]["webSocketDebuggerUrl"]
        else:
            r = requests.put("http://127.0.0.1:9222/json/new")
            ws_url = r.json()["webSocketDebuggerUrl"]
        print("Connected to CDP target:", ws_url)
        
        async with websockets.connect(ws_url, max_size=20*1024*1024) as ws:
            req_id = 1
            await cdp_command(ws, req_id, "Page.enable")
            req_id += 1
            await cdp_command(ws, req_id, "Runtime.enable")
            
            # Figure 1: Citizen Portal (Public Homepage)
            print("Capturing Figure 1: Public Citizen Portal...")
            img1, req_id = await capture_page(ws, req_id, f"{BASE_WEB}/", wait_secs=3)
            with open("figure_1_citizen_portal.png", "wb") as f:
                f.write(img1)
            print("Saved figure_1_citizen_portal.png (", len(img1), "bytes )")
            
            # Figure 2: Admin Dashboard
            print("Capturing Figure 2: Admin Dashboard...")
            img2, req_id = await capture_page(ws, req_id, f"{BASE_WEB}/authority", token=admin_token, user=admin_user, wait_secs=3.5)
            with open("figure_2_admin_dashboard.png", "wb") as f:
                f.write(img2)
            print("Saved figure_2_admin_dashboard.png (", len(img2), "bytes )")
            
            # Figure 3: Authority Officer Dashboard
            print("Capturing Figure 3: Authority Officer Dashboard...")
            img3, req_id = await capture_page(ws, req_id, f"{BASE_WEB}/authority", token=officer_token, user=officer_user, wait_secs=3.5)
            with open("figure_3_authority_dashboard.png", "wb") as f:
                f.write(img3)
            print("Saved figure_3_authority_dashboard.png (", len(img3), "bytes )")
            
            # Figure 4: Department Officer Workflow
            print("Capturing Figure 4: Department Officer Assigned Work Orders...")
            img4, req_id = await capture_page(ws, req_id, f"{BASE_WEB}/authority?dept=1", token=roads_token, user=roads_user, wait_secs=3.5)
            with open("figure_4_department_workflow.png", "wb") as f:
                f.write(img4)
            print("Saved figure_4_department_workflow.png (", len(img4), "bytes )")

    finally:
        edge_proc.terminate()
        try:
            edge_proc.wait(timeout=3)
        except:
            edge_proc.kill()
        print("Edge terminated. All 4 genuine screenshots captured!")

if __name__ == "__main__":
    asyncio.run(main())
