"""
JanSakshi - JWT Session Policy, Token Rotation, Revocation & Gmail Desk Verification
Tests:
1. Configurable session policies (Standard vs Demo).
2. Short-lived access token creation and expired-token rejection (HTTP 401).
3. Fresh Admin login issuing both access and refresh tokens.
4. Refresh token endpoint with cryptographic rotation and replay prevention.
5. Server-enforced logout and active token revocation.
6. Public endpoint and invalid credential handling (no false positive redirects).
7. Full Gmail Intake Desk suite (status, messages, filters, live sync, review actions).
"""

import sys
import os
import requests
import datetime
import jwt

BASE_URL = "http://127.0.0.1:8000"

def log_test(name, passed, detail=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} | {name}")
    if detail:
        print(f"      {detail}")
    if not passed:
        sys.exit(1)

def run_tests():
    print("=" * 80)
    print("JANSAKSHI — JWT SESSION POLICIES, TOKEN ROTATION & GMAIL DESK TESTS")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # TEST 1: Session Policy Verification
    # -------------------------------------------------------------------------
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from app.core.security import (
        SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES,
        REFRESH_TOKEN_EXPIRE_DAYS, IS_DEMO_POLICY
    )
    
    log_test(
        "Policy Check: Standard production policy active by default (not demo)",
        not IS_DEMO_POLICY and ACCESS_TOKEN_EXPIRE_MINUTES == 30,
        f"Policy: {'DEMO' if IS_DEMO_POLICY else 'STANDARD'} | Access Token: {ACCESS_TOKEN_EXPIRE_MINUTES} min | Refresh Token: {REFRESH_TOKEN_EXPIRE_DAYS} days"
    )

    # -------------------------------------------------------------------------
    # TEST 2: Expired Token Rejection
    # -------------------------------------------------------------------------
    # Generate an explicitly expired token using the server's key
    expired_payload = {
        "sub": "admin",
        "uid": 1,
        "role": "admin",
        "type": "access",
        "jti": "test-expired-jti-12345",
        "iat": datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2),
        "exp": datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)
    }
    expired_token = jwt.encode(expired_payload, SECRET_KEY, algorithm=ALGORITHM)

    res_expired = requests.get(
        f"{BASE_URL}/api/email/status",
        headers={"Authorization": f"Bearer {expired_token}"}
    )
    log_test(
        "Security Gate: Expired access token rejected with HTTP 401",
        res_expired.status_code == 401 and "Could not validate authority credentials or session expired" in res_expired.text,
        f"HTTP {res_expired.status_code} | Body: {res_expired.json()}"
    )

    # -------------------------------------------------------------------------
    # TEST 3: Fresh Admin Login & Dual Token Issuance
    # -------------------------------------------------------------------------
    res_login = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "JanSakshi@2026"
    })
    login_data = res_login.json()
    has_dual_tokens = (
        res_login.status_code == 200 and
        "access_token" in login_data and
        "refresh_token" in login_data and
        login_data.get("expires_in") == 1800 and # 30 min in seconds
        login_data.get("policy") == "standard"
    )
    log_test(
        "Authentication: Fresh Admin login issues short-lived access & refresh tokens",
        has_dual_tokens,
        f"Access token len: {len(login_data.get('access_token', ''))} | Refresh token len: {len(login_data.get('refresh_token', ''))} | Expires in: {login_data.get('expires_in')}s ({login_data.get('policy')} policy)"
    )

    admin_token = login_data["access_token"]
    refresh_token_v1 = login_data["refresh_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # -------------------------------------------------------------------------
    # TEST 4: Secure Refresh Token & Cryptographic Rotation
    # -------------------------------------------------------------------------
    res_refresh = requests.post(f"{BASE_URL}/api/auth/refresh", json={
        "refresh_token": refresh_token_v1
    })
    refresh_data = res_refresh.json()
    rotation_success = (
        res_refresh.status_code == 200 and
        "access_token" in refresh_data and
        "refresh_token" in refresh_data and
        refresh_data["refresh_token"] != refresh_token_v1
    )
    log_test(
        "Token Rotation: Refresh token generates new access token and rotated refresh token",
        rotation_success,
        f"New access token issued | Rotated refresh token len: {len(refresh_data.get('refresh_token', ''))}"
    )

    new_access_token = refresh_data["access_token"]
    refresh_token_v2 = refresh_data["refresh_token"]

    # Verify that the NEW access token works on protected endpoints
    res_verify_new = requests.get(
        f"{BASE_URL}/api/email/status",
        headers={"Authorization": f"Bearer {new_access_token}"}
    )
    log_test(
        "Token Usability: Newly refreshed access token authenticates successfully",
        res_verify_new.status_code == 200,
        f"Status endpoint HTTP {res_verify_new.status_code}"
    )

    # REPLAY ATTACK CHECK: Try to use the OLD (v1) refresh token again
    res_replay = requests.post(f"{BASE_URL}/api/auth/refresh", json={
        "refresh_token": refresh_token_v1
    })
    log_test(
        "Replay Prevention: Re-using rotated refresh token rejected with HTTP 401",
        res_replay.status_code == 401,
        f"HTTP {res_replay.status_code} | Body: {res_replay.json()}"
    )

    # -------------------------------------------------------------------------
    # TEST 5: Server-Enforced Logout & Active Token Revocation
    # -------------------------------------------------------------------------
    res_logout = requests.post(
        f"{BASE_URL}/api/auth/logout",
        headers={"Authorization": f"Bearer {new_access_token}"},
        json={"refresh_token": refresh_token_v2}
    )
    log_test(
        "Server Logout: Logout endpoint registers token revocation",
        res_logout.status_code == 200 and res_logout.json().get("status") == "ok",
        f"Body: {res_logout.json()}"
    )

    # Access token must now be rejected IMMEDIATELY (even though exp is still valid)
    res_revoked_access = requests.get(
        f"{BASE_URL}/api/email/status",
        headers={"Authorization": f"Bearer {new_access_token}"}
    )
    log_test(
        "Revocation Enforcement: Logged-out access token immediately rejected with HTTP 401",
        res_revoked_access.status_code == 401 and "revoked" in res_revoked_access.json().get("detail", "").lower(),
        f"HTTP {res_revoked_access.status_code} | Detail: {res_revoked_access.json().get('detail')}"
    )

    # Refresh token must also be rejected
    res_revoked_refresh = requests.post(f"{BASE_URL}/api/auth/refresh", json={
        "refresh_token": refresh_token_v2
    })
    log_test(
        "Revocation Enforcement: Logged-out refresh token rejected with HTTP 401",
        res_revoked_refresh.status_code == 401,
        f"HTTP {res_revoked_refresh.status_code} | Detail: {res_revoked_refresh.json().get('detail')}"
    )

    # -------------------------------------------------------------------------
    # TEST 6: Public Endpoints & Login Error Safety
    # -------------------------------------------------------------------------
    # Bad credentials on login must return 401 without affecting session
    res_bad_login = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "WrongPassword123"
    })
    log_test(
        "Login Isolation: Invalid login returns clean 401 without session redirect conflict",
        res_bad_login.status_code == 401 and "Invalid username or password" in res_bad_login.text,
        f"HTTP {res_bad_login.status_code} | Body: {res_bad_login.json()}"
    )

    # Public endpoint (/api/complaints/{id}) must work with NO auth
    res_public = requests.get(f"{BASE_URL}/api/complaints/JS-2026-00030")
    log_test(
        "Public Endpoint: Public tracking requires no auth and receives no 401",
        res_public.status_code == 200,
        f"Complaint: {res_public.json().get('complaint_id')} | Category: {res_public.json().get('category')}"
    )

    # -------------------------------------------------------------------------
    # TEST 7: Complete Gmail Intake Desk Verification
    # -------------------------------------------------------------------------
    # Acquire a fresh admin session for the Gmail Desk tests
    res_admin2 = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "JanSakshi@2026"
    })
    fresh_admin_token = res_admin2.json()["access_token"]
    fresh_headers = {"Authorization": f"Bearer {fresh_admin_token}"}

    # 7.1 Gmail Status Endpoint
    res_status = requests.get(f"{BASE_URL}/api/email/status", headers=fresh_headers)
    status_data = res_status.json()
    log_test(
        "Gmail Desk: Status endpoint returns operational mailbox metrics",
        res_status.status_code == 200 and status_data.get("authenticated") is True,
        f"Connected: {status_data.get('connected_email')} | Status: {status_data.get('status')} | Total Messages: {status_data.get('total_messages_received')}"
    )

    # 7.2 Historical Messages Endpoint
    res_msgs = requests.get(f"{BASE_URL}/api/email/messages", headers=fresh_headers)
    msgs = res_msgs.json()
    log_test(
        "Gmail Desk: Messages endpoint returns historical ingested records",
        res_msgs.status_code == 200 and len(msgs) > 0,
        f"Historical records returned: {len(msgs)} | Sample ID: #{msgs[0].get('id')} ({msgs[0].get('subject')[:40]}...)"
    )

    # 7.3 Filter Tabs Check
    res_filter_proc = requests.get(f"{BASE_URL}/api/email/messages?status=processed", headers=fresh_headers)
    res_filter_ign = requests.get(f"{BASE_URL}/api/email/messages?status=ignored", headers=fresh_headers)
    res_filter_rev = requests.get(f"{BASE_URL}/api/email/messages?status=needs_review", headers=fresh_headers)
    log_test(
        "Gmail Desk: Status filters operational (processed, ignored, needs_review)",
        res_filter_proc.status_code == 200 and res_filter_ign.status_code == 200 and res_filter_rev.status_code == 200,
        f"Processed: {len(res_filter_proc.json())} | Ignored: {len(res_filter_ign.json())} | Needs Review: {len(res_filter_rev.json())}"
    )

    # 7.4 Live Inbox Synchronization
    res_sync = requests.post(f"{BASE_URL}/api/email/sync?max_messages=5", headers=fresh_headers)
    sync_data = res_sync.json()
    log_test(
        "Gmail Desk: Live Google Gmail API inbox sync executes successfully",
        res_sync.status_code == 200 and sync_data.get("status") == "success",
        f"Status: {sync_data.get('status')} | Messages checked: {sync_data.get('total_found')} | Skipped existing: {sync_data.get('skipped_previously_processed')} | Synced at: {sync_data.get('synced_at')}"
    )

    # 7.5 Review Actions Validation (Confirm Civic & Mark Non-Civic)
    # Check that endpoints exist and enforce proper validation
    res_rev_invalid = requests.post(
        f"{BASE_URL}/api/email/messages/99999/confirm-civic",
        headers=fresh_headers,
        json={}
    )
    log_test(
        "Gmail Desk: Confirm Civic action endpoint validated (404 on invalid ID)",
        res_rev_invalid.status_code == 404,
        f"HTTP {res_rev_invalid.status_code} | Detail: {res_rev_invalid.json().get('detail')}"
    )

    res_nonciv_invalid = requests.post(
        f"{BASE_URL}/api/email/messages/99999/mark-non-civic",
        headers=fresh_headers,
        json={"reason": "Test audit"}
    )
    log_test(
        "Gmail Desk: Mark Non-Civic action endpoint validated (404 on invalid ID)",
        res_nonciv_invalid.status_code == 404,
        f"HTTP {res_nonciv_invalid.status_code} | Detail: {res_nonciv_invalid.json().get('detail')}"
    )

    print("=" * 80)
    print("ALL 12 JWT SESSION & GMAIL DESK VERIFICATION TESTS PASSED (100%)!")
    print("=" * 80)

if __name__ == "__main__":
    run_tests()

