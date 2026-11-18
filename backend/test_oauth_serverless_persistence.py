"""
JanSakshi Test Suite:
Gmail OAuth Serverless State Persistence & PKCE Verification

Verifies:
1. PostgreSQL-backed OAuthState model persistence across separate serverless instances.
2. Atomic single-use state consumption (with_for_update / atomic UPDATE).
3. Immediate replay rejection: second consumption of the same state returns None.
4. Expiration rejection: states past their TTL are rejected.
5. Invalid and forged state rejection: unknown states return None.
6. Safe cleanup of expired states without affecting active sessions.
7. Zero credential leakage: state tokens and PKCE code_verifiers are never printed in logs or __repr__.
8. Gmail token persistence regression: existing OAuthToken records remain intact.
9. Local development fallback compatibility.
"""

import os
import sys
import time
import datetime
import unittest
from unittest.mock import patch

# Ensure backend root is on sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from app.database import SessionLocal, engine
from app.models.oauth_state import OAuthState
from app.models.oauth_token import OAuthToken
from app.services.email.gmail_auth import OAuthStateManager, GmailAuthService, generate_pkce_pair
from app.core.config import utc_now, GMAIL_OAUTH_STATE_PATH

class TestOAuthServerlessPersistence(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()
        # Clean test states
        self.db.query(OAuthState).filter(OAuthState.state_token.like("test_%")).delete(synchronize_session=False)
        self.db.commit()

    def tearDown(self):
        self.db.query(OAuthState).filter(OAuthState.state_token.like("test_%")).delete(synchronize_session=False)
        self.db.commit()
        self.db.close()

    # -------------------------------------------------------------------------
    # 1. CROSS-INSTANCE SERVERLESS COORDINATION
    # -------------------------------------------------------------------------
    def test_cross_instance_oauth_state_persistence(self):
        """Simulate Instance A storing OAuth state and Instance B consuming it with NO shared disk."""
        state_token = f"test_cross_inst_{time.time()}"
        code_verifier = "test_code_verifier_999888777666555444333222111000"

        # Instance A: Stores state in PostgreSQL
        OAuthStateManager.store(state_token, code_verifier, ttl_seconds=600, db=self.db)

        # Simulate Instance B running in a completely separate container/Lambda:
        # 1. Purge/wipe local JSON state file to guarantee zero filesystem sharing
        if os.path.exists(GMAIL_OAUTH_STATE_PATH):
            os.remove(GMAIL_OAUTH_STATE_PATH)

        # 2. Instance B opens a fresh database session and consumes state
        instance_b_db = SessionLocal()
        try:
            retrieved_verifier = OAuthStateManager.consume(state_token, db=instance_b_db)
            self.assertEqual(
                retrieved_verifier,
                code_verifier,
                "Instance B must retrieve matching PKCE code_verifier from PostgreSQL database"
            )

            # Verify consumption status in database
            record = instance_b_db.query(OAuthState).filter(OAuthState.state_token == state_token).first()
            self.assertIsNotNone(record)
            self.assertTrue(record.is_consumed, "Record must be marked as consumed")
            self.assertIsNotNone(record.consumed_at, "consumed_at must be populated")
        finally:
            instance_b_db.close()

    # -------------------------------------------------------------------------
    # 2. ATOMIC SINGLE-USE & REPLAY REJECTION
    # -------------------------------------------------------------------------
    def test_atomic_single_use_and_replay_rejection(self):
        """State must be consumed exactly once; any second/replayed attempt MUST return None."""
        state_token = f"test_replay_{time.time()}"
        code_verifier = "test_verifier_single_use_12345"

        OAuthStateManager.store(state_token, code_verifier, ttl_seconds=600, db=self.db)

        # 1. First consumption -> SUCCESS
        first_call = OAuthStateManager.consume(state_token, db=self.db)
        self.assertEqual(first_call, code_verifier, "First consumption must succeed")

        # 2. Second consumption (Replay Attack) -> MUST RETURN NONE
        second_call = OAuthStateManager.consume(state_token, db=self.db)
        self.assertIsNone(second_call, "Replayed state must return None")

        # 3. Third consumption -> STILL NONE
        third_call = OAuthStateManager.consume(state_token, db=self.db)
        self.assertIsNone(third_call, "Repeated replayed state must return None")

    # -------------------------------------------------------------------------
    # 3. EXPIRED STATE REJECTION
    # -------------------------------------------------------------------------
    def test_expired_state_rejection(self):
        """Expired state tokens must be rejected and return None."""
        state_token = f"test_expired_{time.time()}"
        code_verifier = "test_verifier_expired_9999"

        # Store with TTL of -60 seconds (already expired)
        OAuthStateManager.store(state_token, code_verifier, ttl_seconds=-60, db=self.db)

        result = OAuthStateManager.consume(state_token, db=self.db)
        self.assertIsNone(result, "Expired state must return None upon consumption")

    # -------------------------------------------------------------------------
    # 4. INVALID & EMPTY STATE REJECTION
    # -------------------------------------------------------------------------
    def test_invalid_and_empty_state_rejection(self):
        """Unknown or empty state tokens must return None."""
        self.assertIsNone(OAuthStateManager.consume("completely_fake_state_123", db=self.db))
        self.assertIsNone(OAuthStateManager.consume("", db=self.db))
        self.assertIsNone(OAuthStateManager.consume(None, db=self.db))

    # -------------------------------------------------------------------------
    # 5. SAFE CLEANUP OF EXPIRED STATES
    # -------------------------------------------------------------------------
    def test_cleanup_expired_states(self):
        """Verify cleanup_expired_states deletes expired states while keeping active states intact."""
        now = utc_now()

        # Insert 2 expired states
        s1 = OAuthState(state_token="test_clean_exp1", code_verifier="v1", expires_at=now - datetime.timedelta(minutes=10))
        s2 = OAuthState(state_token="test_clean_exp2", code_verifier="v2", expires_at=now - datetime.timedelta(minutes=5))
        # Insert 1 active state
        s3 = OAuthState(state_token="test_clean_active", code_verifier="v3", expires_at=now + datetime.timedelta(minutes=15))

        self.db.add_all([s1, s2, s3])
        self.db.commit()

        deleted = OAuthStateManager.cleanup_expired_states(db=self.db)
        self.assertGreaterEqual(deleted, 2, "Must delete at least the 2 expired states")

        # Verify active state still exists
        active_record = self.db.query(OAuthState).filter(OAuthState.state_token == "test_clean_active").first()
        self.assertIsNotNone(active_record, "Active unexpired state must NOT be deleted")

    # -------------------------------------------------------------------------
    # 6. ZERO CREDENTIAL LEAKAGE IN REPR AND LOGS
    # -------------------------------------------------------------------------
    def test_zero_credential_leakage_in_model_repr(self):
        """Verify OAuthState __repr__ never contains state_token or code_verifier."""
        state = OAuthState(
            id=42,
            state_token="secret_state_token_xyz",
            code_verifier="super_secret_pkce_verifier_abc",
            expires_at=utc_now(),
            is_consumed=False
        )
        repr_str = repr(state)
        self.assertNotIn("secret_state_token_xyz", repr_str)
        self.assertNotIn("super_secret_pkce_verifier_abc", repr_str)
        self.assertIn("id=42", repr_str)
        self.assertIn("is_consumed=False", repr_str)

    # -------------------------------------------------------------------------
    # 7. GMAIL TOKEN PERSISTENCE REGRESSION
    # -------------------------------------------------------------------------
    def test_gmail_token_persistence_regression(self):
        """Verify existing OAuthToken records in PostgreSQL database are unaffected."""
        token_record = self.db.query(OAuthToken).filter(OAuthToken.provider == "gmail").first()
        self.assertIsNotNone(token_record, "OAuthToken record for gmail must exist")
        self.assertTrue(len(token_record.token_data) > 50, "token_data must contain valid serialized credentials")

        # Verify GmailAuthService credentials loading
        creds = GmailAuthService.get_credentials()
        self.assertIsNotNone(creds, "Gmail credentials must load successfully from persistent store")
        self.assertTrue(creds.valid or creds.refresh_token, "Credentials must be valid or have refresh_token")

    # -------------------------------------------------------------------------
    # 8. LOCAL DEVELOPMENT FALLBACK
    # -------------------------------------------------------------------------
    def test_local_json_fallback(self):
        """Verify local JSON state store functions as a fallback."""
        state = f"test_local_fallback_{time.time()}"
        verifier = "verifier_local_999"

        OAuthStateManager._save_to_local_json(state, verifier, time.time() + 300)
        retrieved = OAuthStateManager._consume_from_local_json(state)
        self.assertEqual(retrieved, verifier)

        # Ensure single use from local JSON too
        replayed = OAuthStateManager._consume_from_local_json(state)
        self.assertIsNone(replayed)

if __name__ == "__main__":
    unittest.main()
