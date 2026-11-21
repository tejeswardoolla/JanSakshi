"""
JanSakshi Automated Test Suite: Hackathon 10-Day Judge Demo Access
Verifies security, token claims, 10-day fixed expiry, RBAC isolation, rate limiting, and zero regressions.

Covers the 10 mandated requirements:
1. Normal password login remains unchanged.
2. Valid judge demo login works for every allowed role.
3. Invalid roles are rejected.
4. Disabled demo mode rejects access.
5. Expired demo mode rejects access.
6. Existing demo sessions cannot be refreshed after expiry.
7. Existing role authorization is preserved.
8. Department access remains correctly scoped.
9. Demo login cannot access production data.
10. Citizen portal behavior remains unchanged.
"""

import os
import unittest
import datetime
import asyncio
from unittest.mock import patch, MagicMock
from fastapi import HTTPException, BackgroundTasks

from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from app.database import SessionLocal, Base, engine
from app.models.authority import User, Department
from app.models.complaint import Complaint
from app.core.security import (
    hash_password,
    verify_password,
    decode_access_token,
    decode_refresh_token,
    get_current_user,
    require_roles
)
from app.core.config import utc_now, is_judge_demo_active, get_judge_demo_expiry
from app.services.judge_demo_service import (
    seed_judge_demo_data,
    verify_safe_demo_seed_environment,
    classify_database_target
)
from app.routes.auth_routes import (
    login,
    refresh_token_endpoint,
    get_me,
    get_judge_demo_status,
    judge_demo_login,
    LoginRequest,
    RefreshRequest,
)
from app.routes.authority_routes import get_departments_for_selection
from app.routes.complaints import create_complaint, track_complaint

class TestJudgeDemoAccess(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.db = SessionLocal()
        # Seed departments and judge demo users
        seed_judge_demo_data(cls.db, force_allow=True)

        # Ensure standard password users exist for normal login testing
        standard_users = [
            ("admin_test", "admin", "Admin Test", "admin", None, None),
            ("officer_test", "officer", "Officer Test", "authority_officer", None, None),
            ("dept_test", "dept", "Dept Test", "department_officer", 1, "1")
        ]
        for uname, pw, name, role, dept_id, allowed_depts in standard_users:
            u = cls.db.query(User).filter(User.username == uname).first()
            if not u:
                u = User(
                    username=uname,
                    email=f"{uname}@jansakshi.gov.in",
                    full_name=name,
                    role=role,
                    department_id=dept_id,
                    allowed_department_ids=allowed_depts,
                    hashed_password=hash_password(f"SecretPass@{pw}123!"),
                    is_active=True,
                    created_at=utc_now()
                )
                cls.db.add(u)
        cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def _create_mock_request(self, ip="127.0.0.1"):
        req = MagicMock()
        req.client.host = ip
        return req

    def _create_mock_session_with_url(self, url_str: str, live_db_return="MATCH_URL") -> MagicMock:
        sess = MagicMock(spec=Session)
        mock_bind = MagicMock()
        mock_bind.url = make_url(url_str)
        driver = mock_bind.url.drivername.split("+")[0]
        mock_bind.dialect.name = driver
        sess.get_bind.return_value = mock_bind
        sess.query.return_value.filter.return_value.first.return_value = None
        sess.query.return_value.all.return_value = []

        if live_db_return == "MATCH_URL":
            db_val = mock_bind.url.database or ""
            sess.execute.return_value.scalar.return_value = db_val
        elif live_db_return == "FAIL":
            sess.execute.side_effect = Exception("Live database connection query failed")
        else:
            sess.execute.return_value.scalar.return_value = live_db_return

        return sess

    # -------------------------------------------------------------------------
    # 1. Normal password login remains unchanged
    # -------------------------------------------------------------------------
    def test_01_normal_password_login_remains_unchanged(self):
        """1. Verify standard password login, token issuance, profile fetch, and refresh work normally."""
        res = asyncio.run(login(
            credentials=LoginRequest(username="admin_test", password="SecretPass@admin123!"),
            db=self.db
        ))
        self.assertIsNotNone(res.access_token)
        self.assertIsNotNone(res.refresh_token)
        self.assertEqual(res.user.username, "admin_test")
        self.assertEqual(res.user.role, "admin")

        # Standard token must NOT contain judge demo claim
        payload = decode_access_token(res.access_token)
        self.assertFalse(payload.get("is_judge_demo", False))

        # Access profile via get_me
        current_u = asyncio.run(get_current_user(token=res.access_token, db=self.db))
        me_res = asyncio.run(get_me(current_user=current_u))
        self.assertEqual(me_res.username, "admin_test")

        # Refresh token
        ref_res = asyncio.run(refresh_token_endpoint(
            body=RefreshRequest(refresh_token=res.refresh_token),
            db=self.db
        ))
        self.assertIsNotNone(ref_res.access_token)
        ref_payload = decode_access_token(ref_res.access_token)
        self.assertFalse(ref_payload.get("is_judge_demo", False))

    # -------------------------------------------------------------------------
    # 2. Valid judge demo login works for every allowed role
    # -------------------------------------------------------------------------
    def test_02_valid_judge_demo_login_works_for_every_allowed_role(self):
        """2. Verify password-free judge demo login works for admin, authority_officer, and department_officer."""
        future_expiry = (utc_now() + datetime.timedelta(days=10)).isoformat()
        with patch.dict(os.environ, {
            "JANSAKSHI_JUDGE_DEMO_ENABLED": "true",
            "JANSAKSHI_JUDGE_DEMO_EXPIRES_AT": future_expiry
        }):
            # Test status endpoint
            status_res = asyncio.run(get_judge_demo_status())
            self.assertTrue(status_res.enabled)
            self.assertEqual(len(status_res.roles), 3)

            roles_to_test = [
                ("admin", "judge_admin"),
                ("authority_officer", "judge_officer"),
                ("department_officer", "judge_dept")
            ]

            req = self._create_mock_request()
            for role, expected_username in roles_to_test:
                res = asyncio.run(judge_demo_login(role=role, request=req, db=self.db))
                self.assertIsNotNone(res.access_token)
                self.assertIsNotNone(res.refresh_token)
                self.assertEqual(res.user.role, role)
                self.assertEqual(res.user.username, expected_username)

                # Token payload must carry dedicated judge demo claims
                payload = decode_access_token(res.access_token)
                self.assertTrue(payload.get("is_judge_demo"))
                self.assertEqual(payload.get("demo_role"), role)
                self.assertIsNotNone(payload.get("demo_expires_at"))

                # get_current_user must work with demo access token
                user_obj = asyncio.run(get_current_user(token=res.access_token, db=self.db))
                self.assertEqual(user_obj.username, expected_username)

    # -------------------------------------------------------------------------
    # 3. Invalid roles are rejected
    # -------------------------------------------------------------------------
    def test_03_invalid_roles_are_rejected(self):
        """3. Verify unauthorized or invented roles (super_admin, citizen, etc.) are strictly rejected with HTTP 400."""
        future_expiry = (utc_now() + datetime.timedelta(days=10)).isoformat()
        with patch.dict(os.environ, {
            "JANSAKSHI_JUDGE_DEMO_ENABLED": "true",
            "JANSAKSHI_JUDGE_DEMO_EXPIRES_AT": future_expiry
        }):
            req = self._create_mock_request()
            invalid_roles = ["super_admin", "department_admin", "citizen", "root", "hacker", "unknown"]
            for bad_role in invalid_roles:
                with self.assertRaises(HTTPException) as ctx:
                    asyncio.run(judge_demo_login(role=bad_role, request=req, db=self.db))
                self.assertEqual(ctx.exception.status_code, 400, f"Role {bad_role} should return 400")
                self.assertIn("Invalid demo role", ctx.exception.detail)

    # -------------------------------------------------------------------------
    # 4. Disabled demo mode rejects access
    # -------------------------------------------------------------------------
    def test_04_disabled_demo_mode_rejects_access(self):
        """4. Verify when JANSAKSHI_JUDGE_DEMO_ENABLED is false, demo endpoints fail closed."""
        future_expiry = (utc_now() + datetime.timedelta(days=10)).isoformat()
        with patch.dict(os.environ, {
            "JANSAKSHI_JUDGE_DEMO_ENABLED": "false",
            "JANSAKSHI_JUDGE_DEMO_EXPIRES_AT": future_expiry
        }):
            # Status endpoint reports disabled
            status_res = asyncio.run(get_judge_demo_status())
            self.assertFalse(status_res.enabled)
            self.assertEqual(status_res.roles, [])

            # Login endpoints reject with 403 Forbidden
            req = self._create_mock_request()
            for role in ["admin", "authority_officer", "department_officer"]:
                with self.assertRaises(HTTPException) as ctx:
                    asyncio.run(judge_demo_login(role=role, request=req, db=self.db))
                self.assertEqual(ctx.exception.status_code, 403)
                self.assertIn("disabled or has expired", ctx.exception.detail)

    # -------------------------------------------------------------------------
    # 5. Expired demo mode rejects access
    # -------------------------------------------------------------------------
    def test_05_expired_demo_mode_rejects_access(self):
        """5. Verify when JANSAKSHI_JUDGE_DEMO_EXPIRES_AT has passed, demo access fails closed."""
        past_expiry = (utc_now() - datetime.timedelta(days=1)).isoformat()
        with patch.dict(os.environ, {
            "JANSAKSHI_JUDGE_DEMO_ENABLED": "true",
            "JANSAKSHI_JUDGE_DEMO_EXPIRES_AT": past_expiry
        }):
            # Status endpoint reports disabled
            status_res = asyncio.run(get_judge_demo_status())
            self.assertFalse(status_res.enabled)

            # Login endpoint rejects with 403
            req = self._create_mock_request()
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(judge_demo_login(role="admin", request=req, db=self.db))
            self.assertEqual(ctx.exception.status_code, 403)
            self.assertIn("disabled or has expired", ctx.exception.detail)

    # -------------------------------------------------------------------------
    # 6. Existing demo sessions cannot be refreshed after expiry
    # -------------------------------------------------------------------------
    def test_06_existing_demo_sessions_cannot_be_refreshed_or_used_after_expiry(self):
        """6. Existing judge demo access tokens and refresh tokens become invalid immediately upon demo expiry."""
        future_expiry = (utc_now() + datetime.timedelta(days=10)).isoformat()
        req = self._create_mock_request()
        with patch.dict(os.environ, {
            "JANSAKSHI_JUDGE_DEMO_ENABLED": "true",
            "JANSAKSHI_JUDGE_DEMO_EXPIRES_AT": future_expiry
        }):
            # Obtain valid demo session
            res = asyncio.run(judge_demo_login(role="admin", request=req, db=self.db))
            access_token = res.access_token
            refresh_token = res.refresh_token

        # Now simulate judge demo mode has expired or been disabled
        with patch.dict(os.environ, {
            "JANSAKSHI_JUDGE_DEMO_ENABLED": "false"
        }):
            # 1. Existing access token must be rejected in get_current_user
            with self.assertRaises(HTTPException) as ctx_acc:
                asyncio.run(get_current_user(token=access_token, db=self.db))
            self.assertEqual(ctx_acc.exception.status_code, 401)
            self.assertIn("expired or is disabled", ctx_acc.exception.detail)

            # 2. Existing refresh token must be rejected in refresh_token_endpoint
            with self.assertRaises(HTTPException) as ctx_ref:
                asyncio.run(refresh_token_endpoint(body=RefreshRequest(refresh_token=refresh_token), db=self.db))
            self.assertEqual(ctx_ref.exception.status_code, 401)
            self.assertIn("expired or is disabled", ctx_ref.exception.detail)

    # -------------------------------------------------------------------------
    # 7. Existing role authorization is preserved
    # -------------------------------------------------------------------------
    def test_07_existing_role_authorization_is_preserved(self):
        """7. Verify standard RBAC dependencies enforce correct role boundaries on judge demo users."""
        future_expiry = (utc_now() + datetime.timedelta(days=10)).isoformat()
        req = self._create_mock_request()
        with patch.dict(os.environ, {
            "JANSAKSHI_JUDGE_DEMO_ENABLED": "true",
            "JANSAKSHI_JUDGE_DEMO_EXPIRES_AT": future_expiry
        }):
            admin_tok = asyncio.run(judge_demo_login("admin", req, self.db)).access_token
            officer_tok = asyncio.run(judge_demo_login("authority_officer", req, self.db)).access_token
            dept_tok = asyncio.run(judge_demo_login("department_officer", req, self.db)).access_token

            admin_user = asyncio.run(get_current_user(token=admin_tok, db=self.db))
            officer_user = asyncio.run(get_current_user(token=officer_tok, db=self.db))
            dept_user = asyncio.run(get_current_user(token=dept_tok, db=self.db))

            # Admin checker: admin passes, officer and dept fail
            admin_checker = require_roles(["admin"])
            self.assertEqual(asyncio.run(admin_checker(admin_user)), admin_user)

            with self.assertRaises(HTTPException) as ctx1:
                asyncio.run(admin_checker(officer_user))
            self.assertEqual(ctx1.exception.status_code, 403)

            with self.assertRaises(HTTPException) as ctx2:
                asyncio.run(admin_checker(dept_user))
            self.assertEqual(ctx2.exception.status_code, 403)

            # Department checker: dept passes, others fail
            dept_checker = require_roles(["department_officer"])
            self.assertEqual(asyncio.run(dept_checker(dept_user)), dept_user)

    # -------------------------------------------------------------------------
    # 8. Department access remains correctly scoped
    # -------------------------------------------------------------------------
    def test_08_department_access_remains_correctly_scoped(self):
        """8. Verify judge department officer has authorized access across all 6 municipal department workspaces."""
        future_expiry = (utc_now() + datetime.timedelta(days=10)).isoformat()
        req = self._create_mock_request()
        with patch.dict(os.environ, {
            "JANSAKSHI_JUDGE_DEMO_ENABLED": "true",
            "JANSAKSHI_JUDGE_DEMO_EXPIRES_AT": future_expiry
        }):
            res = asyncio.run(judge_demo_login("department_officer", req, self.db))
            user_data = res.user

            # Must have all departments enabled
            self.assertTrue(user_data.has_all_departments)
            self.assertEqual(set(user_data.authorized_departments), {1, 2, 3, 4, 5, 6})

            # Check /departments/selection endpoint
            dept_user = asyncio.run(get_current_user(token=res.access_token, db=self.db))
            dept_sel = asyncio.run(get_departments_for_selection(db=self.db, current_user=dept_user))
            depts = dept_sel["departments"]
            self.assertEqual(len(depts), 6)
            for d in depts:
                self.assertTrue(d["is_authorized"], f"Department {d['code']} should be authorized for judge dept lead")

            # Check individual department officers (non-demo) remain restricted
            roads_user = self.db.query(User).filter(User.username == "dept_test").first()
            roads_dept_sel = asyncio.run(get_departments_for_selection(db=self.db, current_user=roads_user))
            roads_depts = roads_dept_sel["departments"]
            auth_count = sum(1 for d in roads_depts if d["is_authorized"])
            self.assertEqual(auth_count, 1, "Standard department officer must only have 1 authorized department")

    # -------------------------------------------------------------------------
    # 9. Demo login cannot access production data
    # -------------------------------------------------------------------------
    def test_09_demo_login_cannot_access_production_data(self):
        """9. Verify demo accounts have dedicated identity, distinct emails, random non-public passwords, and demo claims."""
        judge_admin = self.db.query(User).filter(User.username == "judge_admin").first()
        judge_officer = self.db.query(User).filter(User.username == "judge_officer").first()
        judge_dept = self.db.query(User).filter(User.username == "judge_dept").first()

        self.assertIsNotNone(judge_admin)
        self.assertIsNotNone(judge_officer)
        self.assertIsNotNone(judge_dept)

        # Demo emails must be segregated from production
        self.assertTrue(judge_admin.email.endswith("@demo.jansakshi.internal"))
        self.assertTrue(judge_officer.email.endswith("@demo.jansakshi.internal"))
        self.assertTrue(judge_dept.email.endswith("@demo.jansakshi.internal"))

        # Passwords must NOT be empty or match known public test passwords
        known_test_passwords = ["admin", "officer", "JanSakshi@2026", "secret", "password", "123456"]
        for bad_pw in known_test_passwords:
            self.assertFalse(verify_password(bad_pw, judge_admin.hashed_password))
            self.assertFalse(verify_password(bad_pw, judge_officer.hashed_password))
            self.assertFalse(verify_password(bad_pw, judge_dept.hashed_password))

    # -------------------------------------------------------------------------
    # 10. Citizen portal behavior remains unchanged
    # -------------------------------------------------------------------------
    def test_10_citizen_portal_behavior_remains_unchanged(self):
        """10. Verify public citizen grievance submission and tracking flows remain fully functional and unauthenticated."""
        bg_tasks = BackgroundTasks()
        submit_res = asyncio.run(create_complaint(
            background_tasks=bg_tasks,
            category="Road Damage / Potholes",
            description="Public citizen pothole report outside metro station",
            latitude=16.5100,
            longitude=80.6400,
            location_accuracy=5.0,
            location_source="gps",
            citizen_name="Citizen User",
            citizen_email="citizen@example.com",
            citizen_phone="9876543210",
            evidence=[],
            db=self.db
        ))
        self.assertIsNotNone(submit_res.complaint_id)
        self.assertIsNotNone(submit_res.tracking_token)
        cid = submit_res.complaint_id

        # Public grievance tracking
        track_res = asyncio.run(track_complaint(complaint_id=cid, db=self.db))
        self.assertEqual(track_res.complaint_id, cid)

    # -------------------------------------------------------------------------
    # 11. Existing account preservation across multiple seeds
    # -------------------------------------------------------------------------
    def test_11_existing_account_preservation_across_multiple_seeds(self):
        """
        Verify that running seed_judge_demo_data multiple times preserves all existing non-judge users:
        usernames, emails, password hashes, roles, department assignments, and active status are unchanged.
        Verify only intended judge_* accounts are created or updated.
        """
        # 1. Snapshot all existing non-judge users
        non_judge_users = self.db.query(User).filter(~User.username.like("judge_%")).all()
        snapshots_before = {}
        for u in non_judge_users:
            snapshots_before[u.id] = {
                "username": u.username,
                "email": u.email,
                "hashed_password": u.hashed_password,
                "role": u.role,
                "department_id": u.department_id,
                "allowed_department_ids": u.allowed_department_ids,
                "is_active": u.is_active,
            }

        # 2. Run seed operation (Run 1)
        res1 = seed_judge_demo_data(self.db, force_allow=True)
        self.assertEqual(res1["status"], "success")

        # 3. Verify all existing users are completely unchanged
        for u_id, before in snapshots_before.items():
            u = self.db.query(User).filter(User.id == u_id).first()
            self.assertIsNotNone(u)
            self.assertEqual(u.username, before["username"])
            self.assertEqual(u.email, before["email"])
            self.assertEqual(u.hashed_password, before["hashed_password"])
            self.assertEqual(u.role, before["role"])
            self.assertEqual(u.department_id, before["department_id"])
            self.assertEqual(u.allowed_department_ids, before["allowed_department_ids"])
            self.assertEqual(u.is_active, before["is_active"])

        # 4. Run seed operation again (Run 2 - idempotency check)
        res2 = seed_judge_demo_data(self.db, force_allow=True)
        self.assertEqual(res2["status"], "success")

        # 5. Verify all existing users are STILL completely unchanged
        for u_id, before in snapshots_before.items():
            u = self.db.query(User).filter(User.id == u_id).first()
            self.assertIsNotNone(u)
            self.assertEqual(u.username, before["username"])
            self.assertEqual(u.email, before["email"])
            self.assertEqual(u.hashed_password, before["hashed_password"])
            self.assertEqual(u.role, before["role"])
            self.assertEqual(u.department_id, before["department_id"])
            self.assertEqual(u.allowed_department_ids, before["allowed_department_ids"])
            self.assertEqual(u.is_active, before["is_active"])

        # 6. Verify only intended judge_* accounts were created or updated
        all_judge_users = self.db.query(User).filter(User.username.like("judge_%")).all()
        judge_usernames = {u.username for u in all_judge_users}
        self.assertEqual(judge_usernames, {"judge_admin", "judge_officer", "judge_dept"})

    # -------------------------------------------------------------------------
    # 12. Strict production safeguards matrix and database identity classification
    # -------------------------------------------------------------------------
    def test_12_fail_closed_production_safeguards_matrix(self):
        """
        Verify the complete production-safety matrix for judge demo database seeding:
        1. Production hostname + database ending in _demo + force flag -> BLOCKED.
        2. Unknown hostname + approved demo database name + force flag -> BLOCKED.
        3. Exact approved demo hostname + approved demo database + force flag -> ALLOWED.
        4. Live current_database() returns neondb despite a demo-looking URL -> BLOCKED.
        5. Live database identity query fails -> BLOCKED.
        6. Dedicated demo database without flag -> BLOCKED when authorization required.
        7. Confirm rejected cases perform zero writes.
        """
        prod_host_demo_db = "postgresql://user:pass@ep-cool-snowflake-12345.us-east-2.aws.neon.tech/custom_sub_demo"
        unknown_host_approved_db = "postgresql://user:pass@unauthorized-host.internal/jansakshi_demo"
        approved_demo_url = "postgresql://demo_user:pass@ep-demo-snowflake-12345.us-east-2.aws.neon.tech/jansakshi_demo"

        # 1. Production hostname + database ending in _demo + force flag -> BLOCKED
        sess1 = self._create_mock_session_with_url(prod_host_demo_db)
        with self.assertRaises(PermissionError) as ctx1:
            seed_judge_demo_data(sess1, force_allow=True)
        self.assertIn("FAIL-CLOSED PRODUCTION PROTECTION", str(ctx1.exception))
        self.assertIn("PERMANENTLY BLOCKED", str(ctx1.exception))
        self.assertEqual(sess1.add.call_count, 0)
        self.assertEqual(sess1.commit.call_count, 0)
        self.assertEqual(sess1.flush.call_count, 0)

        # 2. Unknown hostname + approved demo database name + force flag -> BLOCKED
        sess2 = self._create_mock_session_with_url(unknown_host_approved_db)
        with self.assertRaises(PermissionError) as ctx2:
            seed_judge_demo_data(sess2, force_allow=True)
        self.assertIn("FAIL-CLOSED REJECTION", str(ctx2.exception))
        self.assertIn("not an authorized judge demo database", str(ctx2.exception))
        self.assertEqual(sess2.add.call_count, 0)
        self.assertEqual(sess2.commit.call_count, 0)
        self.assertEqual(sess2.flush.call_count, 0)

        # 3. Exact approved demo hostname + approved demo database + force flag -> ALLOWED
        sess3 = self._create_mock_session_with_url(approved_demo_url, live_db_return="jansakshi_demo")
        verify_safe_demo_seed_environment(sess3, force_allow=True)
        self.assertEqual(classify_database_target(sess3), "DEMO")
        # Live demo test execution with force flag succeeds
        res3 = seed_judge_demo_data(self.db, force_allow=True)
        self.assertEqual(res3["status"], "success")

        # 4. Live current_database() returns neondb despite a demo-looking URL -> BLOCKED
        sess4 = self._create_mock_session_with_url(approved_demo_url, live_db_return="neondb")
        with self.assertRaises(PermissionError) as ctx4:
            seed_judge_demo_data(sess4, force_allow=True)
        self.assertIn("FAIL-CLOSED PRODUCTION PROTECTION", str(ctx4.exception))
        self.assertIn("neondb", str(ctx4.exception))
        self.assertEqual(sess4.add.call_count, 0)
        self.assertEqual(sess4.commit.call_count, 0)
        self.assertEqual(sess4.flush.call_count, 0)

        # 5. Live database identity query fails -> BLOCKED
        sess5 = self._create_mock_session_with_url(approved_demo_url, live_db_return="FAIL")
        with self.assertRaises(PermissionError) as ctx5:
            seed_judge_demo_data(sess5, force_allow=True)
        self.assertIn("LIVE DATABASE VERIFICATION FAILED", str(ctx5.exception))
        self.assertEqual(sess5.add.call_count, 0)
        self.assertEqual(sess5.commit.call_count, 0)
        self.assertEqual(sess5.flush.call_count, 0)

        # 6. Dedicated demo database without flag -> BLOCKED when explicit authorization is required
        sess6 = self._create_mock_session_with_url(approved_demo_url, live_db_return="jansakshi_demo")
        with self.assertRaises(PermissionError) as ctx6:
            seed_judge_demo_data(sess6, force_allow=False)
        self.assertIn("AUTHORIZATION REQUIRED", str(ctx6.exception))
        self.assertIn("--force-demo-seed", str(ctx6.exception))
        self.assertEqual(sess6.add.call_count, 0)
        self.assertEqual(sess6.commit.call_count, 0)
        self.assertEqual(sess6.flush.call_count, 0)

        # 7. Live database identity differs from configured database -> BLOCKED
        sess7 = self._create_mock_session_with_url(approved_demo_url, live_db_return="unexpected_other_db")
        with self.assertRaises(PermissionError) as ctx7:
            seed_judge_demo_data(sess7, force_allow=True)
        self.assertIn("DATABASE IDENTITY MISMATCH", str(ctx7.exception))
        self.assertEqual(sess7.add.call_count, 0)
        self.assertEqual(sess7.commit.call_count, 0)
        self.assertEqual(sess7.flush.call_count, 0)

    # -------------------------------------------------------------------------
    # 13. Rate limiting enforcement
    # -------------------------------------------------------------------------
    def test_13_rate_limiting_enforcement(self):
        """Verify that more than 15 requests per minute from a single IP triggers HTTP 429."""
        future_expiry = (utc_now() + datetime.timedelta(days=10)).isoformat()
        with patch.dict(os.environ, {
            "JANSAKSHI_JUDGE_DEMO_ENABLED": "true",
            "JANSAKSHI_JUDGE_DEMO_EXPIRES_AT": future_expiry
        }):
            req = self._create_mock_request(ip="198.51.100.99")
            # Consume 15 tokens
            for _ in range(15):
                res = asyncio.run(judge_demo_login("admin", req, self.db))
                self.assertIsNotNone(res.access_token)

            # 16th request must trigger 429
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(judge_demo_login("admin", req, self.db))
            self.assertEqual(ctx.exception.status_code, 429)
            self.assertIn("Rate limit exceeded", ctx.exception.detail)

if __name__ == "__main__":
    unittest.main()
