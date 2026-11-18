import os
import time
import datetime
import json
import secrets
import hashlib
import base64
import logging
import threading
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from app.database import SessionLocal
from app.models.oauth_state import OAuthState
from app.core.config import (
    utc_now,
    GMAIL_ENABLED,
    GMAIL_INBOX_ADDRESS,
    GMAIL_CLIENT_ID,
    GMAIL_CLIENT_SECRET,
    GMAIL_REDIRECT_URI,
    GMAIL_TOKEN_PATH,
    GMAIL_OAUTH_STATE_PATH,
    GMAIL_CREDENTIALS_FILE,
    GMAIL_SCOPES,
)

logger = logging.getLogger("jansakshi.gmail.auth")


class OAuthStateManager:
    """
    Thread-safe, serverless-ready persistent store for OAuth 2.0 PKCE code verifiers and state tokens.
    Persists to PostgreSQL (OAuthState table) for cross-instance serverless coordination on Vercel.
    Retains local JSON state storage as a secondary fallback for local development.
    Guarantees atomic single-use consumption, TTL expiration, and replay protection.
    Never logs or exposes sensitive state tokens or code verifier secrets.
    """
    _lock = threading.Lock()

    @classmethod
    def _save_to_local_json(cls, state: str, code_verifier: str, expires_at_timestamp: float) -> None:
        """Fallback: stores state in local JSON file for development environments."""
        try:
            with cls._lock:
                now = time.time()
                states = cls._load_local_json()
                valid_states = {s: v for s, v in states.items() if v.get("expires_at", 0) > now}
                valid_states[state] = {
                    "code_verifier": code_verifier,
                    "expires_at": expires_at_timestamp
                }
                os.makedirs(os.path.dirname(os.path.abspath(GMAIL_OAUTH_STATE_PATH)), exist_ok=True)
                with open(GMAIL_OAUTH_STATE_PATH, "w", encoding="utf-8") as f:
                    json.dump(valid_states, f)
        except Exception as e:
            logger.debug(f"Could not write local OAuth state JSON (expected in read-only serverless): {e}")

    @classmethod
    def _load_local_json(cls) -> Dict[str, Dict[str, Any]]:
        """Reads local JSON store if present."""
        if not os.path.exists(GMAIL_OAUTH_STATE_PATH):
            return {}
        try:
            with open(GMAIL_OAUTH_STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.debug(f"Could not read local OAuth state JSON: {e}")
            return {}

    @classmethod
    def _consume_from_local_json(cls, state: str) -> Optional[str]:
        """Consumes code_verifier from local JSON fallback."""
        try:
            with cls._lock:
                now = time.time()
                states = cls._load_local_json()
                entry = states.pop(state, None)
                valid_states = {s: v for s, v in states.items() if v.get("expires_at", 0) > now}
                try:
                    with open(GMAIL_OAUTH_STATE_PATH, "w", encoding="utf-8") as f:
                        json.dump(valid_states, f)
                except Exception:
                    pass

                if entry and entry.get("expires_at", 0) >= now:
                    return entry.get("code_verifier")
        except Exception:
            pass
        return None

    @classmethod
    def cleanup_expired_states(cls, db: Optional[Session] = None) -> int:
        """Safely cleans expired OAuth states from the database without touching valid states."""
        own_session = False
        if db is None:
            db = SessionLocal()
            own_session = True
        try:
            now = utc_now()
            deleted_count = db.query(OAuthState).filter(OAuthState.expires_at < now).delete(synchronize_session=False)
            db.commit()
            return deleted_count
        except Exception as e:
            db.rollback()
            logger.warning(f"Could not clean expired OAuth states: {e}")
            return 0
        finally:
            if own_session:
                db.close()

    @classmethod
    def store(cls, state: str, code_verifier: str, ttl_seconds: int = 900, db: Optional[Session] = None) -> None:
        """
        Securely stores OAuth state and PKCE verifier in PostgreSQL database.
        Also writes to local JSON store for local development environments.
        Never logs or exposes the state token or code verifier value.
        """
        if not state or not code_verifier:
            raise ValueError("State and code_verifier are required.")

        now = utc_now()
        expires_at = now + datetime.timedelta(seconds=ttl_seconds)

        # 1. Primary Store: Database (PostgreSQL / SQLite)
        own_session = False
        if db is None:
            db = SessionLocal()
            own_session = True
        try:
            # Clean expired states periodically on insert
            cls.cleanup_expired_states(db)

            # Ensure any duplicate state entry is removed (prevent conflicts)
            db.query(OAuthState).filter(OAuthState.state_token == state).delete(synchronize_session=False)

            oauth_state_record = OAuthState(
                state_token=state,
                code_verifier=code_verifier,
                expires_at=expires_at,
                created_at=now,
                is_consumed=False,
                consumed_at=None
            )
            db.add(oauth_state_record)
            db.commit()
            logger.info("OAuth state successfully persisted to database with %ds TTL.", ttl_seconds)
        except Exception as db_err:
            db.rollback()
            logger.error(f"Failed to persist OAuth state to database: {db_err}")
            raise
        finally:
            if own_session:
                db.close()

        # 2. Secondary Local JSON Store (Development fallback)
        cls._save_to_local_json(state, code_verifier, time.time() + ttl_seconds)

    @classmethod
    def consume(cls, state: Optional[str], db: Optional[Session] = None) -> Optional[str]:
        """
        Atomically validates, retrieves, and marks the code_verifier for the given state as consumed.
        Enforces single-use consumption and expiration.
        Rejects already-consumed (replayed), expired, or invalid states.
        Never logs the actual state or verifier strings.
        """
        if not state:
            logger.warning("OAuth state verification failed: Empty state parameter.")
            return None

        now = utc_now()

        # 1. Primary Verification: Database (Atomic single-use consumption)
        own_session = False
        if db is None:
            db = SessionLocal()
            own_session = True
        try:
            # Atomic update: only updates if state exists, is NOT consumed, and NOT expired
            rows_updated = db.query(OAuthState).filter(
                OAuthState.state_token == state,
                OAuthState.is_consumed == False,
                OAuthState.expires_at > now
            ).update(
                {
                    OAuthState.is_consumed: True,
                    OAuthState.consumed_at: now
                },
                synchronize_session=False
            )
            db.commit()

            if rows_updated > 0:
                # Successfully consumed atomically! Fetch code_verifier
                record = db.query(OAuthState).filter(OAuthState.state_token == state).first()
                if record and record.code_verifier:
                    logger.info("OAuth state successfully validated and consumed atomically from database.")
                    return record.code_verifier

            # If atomic update did not update any row, check why to provide accurate security audit logging
            existing = db.query(OAuthState).filter(OAuthState.state_token == state).first()
            if existing:
                if existing.is_consumed:
                    logger.warning("OAuth state verification rejected: State has already been consumed (Replay attack blocked).")
                    return None
                exp = existing.expires_at
                if exp and exp.tzinfo is None:
                    exp = exp.replace(tzinfo=datetime.timezone.utc)
                if exp and exp <= now:
                    logger.warning("OAuth state verification rejected: State token has expired.")
                    return None
        except Exception as db_err:
            db.rollback()
            logger.warning(f"Database OAuth state lookup encountered error: {db_err}")
        finally:
            if own_session:
                db.close()

        # 2. Secondary Fallback: Local JSON store (only if not found in DB, e.g. mock local dev without DB)
        local_verifier = cls._consume_from_local_json(state)
        if local_verifier:
            logger.info("OAuth state consumed from local development store.")
            return local_verifier

        logger.warning("OAuth state verification rejected: State token not found in any store.")
        return None


def generate_pkce_pair() -> Tuple[str, str]:
    """
    Generates a cryptographically secure PKCE code_verifier and S256 code_challenge per RFC 7636.
    64 URL-safe bytes yields ~86 safe unreserved chars [A-Za-z0-9_-], well within 43-128 range.
    """
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return code_verifier, code_challenge

class GmailAuthService:
    """
    Handles Google OAuth 2.0 authentication, token persistence,
    automatic token refresh, and Gmail API service resource creation.
    """

    @classmethod
    def get_client_config(cls) -> Optional[Dict[str, Any]]:
        """Constructs or reads OAuth client configuration without exposing secrets."""
        if GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET:
            return {
                "web": {
                    "client_id": GMAIL_CLIENT_ID,
                    "client_secret": GMAIL_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [GMAIL_REDIRECT_URI],
                }
            }

        if os.path.exists(GMAIL_CREDENTIALS_FILE):
            try:
                with open(GMAIL_CREDENTIALS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "installed" in data or "web" in data:
                        return data
            except Exception as e:
                logger.error(f"Failed to read credentials file {GMAIL_CREDENTIALS_FILE}: {e}")

        return None

    @classmethod
    def is_configured(cls) -> bool:
        """Checks if OAuth credentials exist in environment or file."""
        return cls.get_client_config() is not None

    @classmethod
    def is_authenticated(cls) -> bool:
        """Checks if a valid, refreshed token file exists."""
        creds = cls.get_credentials()
        return creds is not None and creds.valid

    @classmethod
    def _load_token_from_db(cls) -> Optional[dict]:
        """Loads OAuth token data dictionary from PostgreSQL database."""
        try:
            from app.database import SessionLocal
            from app.models.oauth_token import OAuthToken
            db = SessionLocal()
            try:
                row = db.query(OAuthToken).filter(
                    OAuthToken.provider == "gmail",
                    OAuthToken.account_email == GMAIL_INBOX_ADDRESS
                ).first()
                if row and row.token_data:
                    return json.loads(row.token_data)
            finally:
                db.close()
        except Exception as e:
            logger.debug(f"Could not load OAuth token from database: {e}")
        return None

    @classmethod
    def _save_token_to_db(cls, token_json_str: str) -> bool:
        """Persists OAuth token securely to database for serverless resilience."""
        try:
            from app.database import SessionLocal
            from app.models.oauth_token import OAuthToken
            from app.core.config import utc_now
            db = SessionLocal()
            try:
                row = db.query(OAuthToken).filter(
                    OAuthToken.provider == "gmail",
                    OAuthToken.account_email == GMAIL_INBOX_ADDRESS
                ).first()
                if not row:
                    row = OAuthToken(
                        provider="gmail",
                        account_email=GMAIL_INBOX_ADDRESS,
                        token_data=token_json_str
                    )
                    db.add(row)
                else:
                    row.token_data = token_json_str
                    row.updated_at = utc_now()
                db.commit()
                return True
            except Exception as e:
                db.rollback()
                logger.error(f"Failed to persist OAuth token to database: {e}")
                return False
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Database error while saving OAuth token: {e}")
            return False

    @classmethod
    def _delete_token_from_db(cls) -> bool:
        """Removes OAuth token from database."""
        try:
            from app.database import SessionLocal
            from app.models.oauth_token import OAuthToken
            db = SessionLocal()
            try:
                db.query(OAuthToken).filter(
                    OAuthToken.provider == "gmail",
                    OAuthToken.account_email == GMAIL_INBOX_ADDRESS
                ).delete()
                db.commit()
                return True
            except Exception as e:
                db.rollback()
                logger.error(f"Failed to remove OAuth token from database: {e}")
                return False
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Database error while removing OAuth token: {e}")
            return False

    @classmethod
    def get_credentials(cls) -> Optional[Credentials]:
        """
        Loads and auto-refreshes Google OAuth credentials from database or local token file.
        Database is preferred for serverless durability across instances.
        """
        token_data = None
        source = None

        # 1. Try PostgreSQL database first
        db_data = cls._load_token_from_db()
        if db_data:
            token_data = db_data
            source = "database"
        elif os.path.exists(GMAIL_TOKEN_PATH):
            # 2. Fall back to local filesystem file
            try:
                with open(GMAIL_TOKEN_PATH, "r", encoding="utf-8") as f:
                    token_data = json.load(f)
                source = "file"
            except Exception as e:
                logger.warning(f"Failed reading token file {GMAIL_TOKEN_PATH}: {e}")

        if not token_data:
            return None

        try:
            stored_scopes = set(token_data.get("scopes", []))
            required_scopes = set(GMAIL_SCOPES)
            
            # If token lacks any required scope or contains obsolete modify scope, invalidate for re-authorization
            if not required_scopes.issubset(stored_scopes) or "https://www.googleapis.com/auth/gmail.modify" in stored_scopes:
                logger.warning(
                    f"Stored Gmail credentials scopes {stored_scopes} do not match configured minimal scopes {required_scopes} "
                    "or contain deprecated modify permission. Re-authorization is required."
                )
                return None

            creds = Credentials.from_authorized_user_info(token_data, GMAIL_SCOPES)
            if creds and creds.expired and creds.refresh_token:
                logger.info(f"Gmail OAuth token expired; auto-refreshing via refresh_token ({source})...")
                creds.refresh(Request())
                cls.save_credentials(creds)
            elif creds and source == "file":
                # Auto-sync token from file into database for serverless persistence
                cls._save_token_to_db(creds.to_json())

            return creds if creds and creds.valid else None
        except Exception as e:
            logger.warning(f"Failed to load or refresh Gmail credentials from {source}: {e}")
            return None

    @classmethod
    def save_credentials(cls, creds: Credentials) -> None:
        """Securely writes credentials to both PostgreSQL database and local token file."""
        json_str = creds.to_json()

        # 1. Save to PostgreSQL database for serverless durability
        cls._save_token_to_db(json_str)

        # 2. Save to local filesystem if writable
        try:
            os.makedirs(os.path.dirname(os.path.abspath(GMAIL_TOKEN_PATH)), exist_ok=True)
            with open(GMAIL_TOKEN_PATH, "w", encoding="utf-8") as token_file:
                token_file.write(json_str)
        except Exception as e:
            logger.debug(f"Could not write local token file (expected in read-only serverless): {e}")

        logger.info("Gmail credentials securely saved to persistent store.")

    @classmethod
    def consume_oauth_state(cls, state: Optional[str], db: Optional[Session] = None) -> Optional[str]:
        """Validates and retrieves the PKCE code_verifier for an OAuth state, consuming it atomically."""
        return OAuthStateManager.consume(state, db=db)

    @classmethod
    def generate_auth_url(cls, state: Optional[str] = None, db: Optional[Session] = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Creates an OAuth authorization URL with PKCE (S256) and binds code_verifier to state.
        Returns (authorization_url, error).
        """
        config = cls.get_client_config()
        if not config:
            return None, "Gmail OAuth client credentials not configured. Please set GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET in backend/.env"

        try:
            # 1. Generate CSRF state token
            oauth_state = state or secrets.token_urlsafe(32)

            # 2. Generate PKCE code verifier & S256 code challenge
            code_verifier, code_challenge = generate_pkce_pair()

            # 3. Securely store state -> code_verifier mapping with 15-minute TTL
            OAuthStateManager.store(oauth_state, code_verifier, ttl_seconds=900, db=db)

            # 4. Initialize Flow with minimal scopes and redirect URI
            flow = Flow.from_client_config(
                config,
                scopes=GMAIL_SCOPES,
                redirect_uri=GMAIL_REDIRECT_URI,
                state=oauth_state
            )
            flow.code_verifier = code_verifier

            # 5. Generate authorization URL embedding code_challenge, code_challenge_method=S256, and state
            auth_url, _ = flow.authorization_url(
                access_type="offline",
                prompt="consent",
                login_hint=GMAIL_INBOX_ADDRESS,
                state=oauth_state,
                code_challenge=code_challenge,
                code_challenge_method="S256"
            )
            return auth_url, None
        except Exception as e:
            logger.error(f"Failed to generate OAuth URL: {e}")
            return None, str(e)

    @classmethod
    def exchange_code_for_tokens(
        cls,
        code: str,
        code_verifier: Optional[str] = None,
        state: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Exchanges authorization code from Google OAuth callback for access and refresh tokens
        using the preserved PKCE code_verifier.
        """
        config = cls.get_client_config()
        if not config:
            return False, "OAuth client credentials missing."

        if not code_verifier:
            return False, "Missing PKCE code verifier. Please initiate authorization again."

        try:
            flow = Flow.from_client_config(
                config,
                scopes=GMAIL_SCOPES,
                redirect_uri=GMAIL_REDIRECT_URI,
                state=state
            )
            # Supply the matching PKCE code_verifier
            flow.code_verifier = code_verifier
            flow.fetch_token(code=code, code_verifier=code_verifier)
            creds = flow.credentials
            cls.save_credentials(creds)
            logger.info("Successfully exchanged authorization code for Gmail OAuth tokens with PKCE S256.")
            return True, "Successfully authenticated with Google Gmail API."
        except Exception as e:
            err_msg = str(e)
            logger.error(f"Failed exchanging OAuth code for tokens: {err_msg}")
            return False, f"Token exchange failed: {err_msg}"

    @classmethod
    def get_gmail_service(cls):
        """
        Returns authenticated Google Gmail API service resource, or None if not authenticated.
        """
        creds = cls.get_credentials()
        if not creds:
            return None
        try:
            return build("gmail", "v1", credentials=creds, cache_discovery=False)
        except Exception as e:
            logger.error(f"Failed to build Gmail service: {e}")
            return None

    @classmethod
    def get_mailbox_profile(cls) -> Optional[Dict[str, Any]]:
        """Retrieves profile (e.g. emailAddress, messagesTotal) of the authenticated user."""
        service = cls.get_gmail_service()
        if not service:
            return None
        try:
            profile = service.users().getProfile(userId="me").execute()
            return {
                "email_address": profile.get("emailAddress"),
                "messages_total": profile.get("messagesTotal"),
                "threads_total": profile.get("threadsTotal"),
                "history_id": profile.get("historyId"),
            }
        except Exception as e:
            logger.warning(f"Could not retrieve Gmail profile: {e}")
            return None

    @classmethod
    def disconnect(cls) -> bool:
        """Removes token safely from both database and local store to disconnect mailbox."""
        db_removed = cls._delete_token_from_db()
        file_removed = True
        if os.path.exists(GMAIL_TOKEN_PATH):
            try:
                os.remove(GMAIL_TOKEN_PATH)
            except Exception as e:
                logger.error(f"Failed removing local token file: {e}")
                file_removed = False
        logger.info("Gmail credentials disconnected.")
        return db_removed or file_removed

    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        """Returns consolidated connection status dictionary."""
        configured = cls.is_configured()
        authenticated = cls.is_authenticated()
        profile = cls.get_mailbox_profile() if authenticated else None
        connected_email = profile.get("email_address") if profile else None

        mailbox_match = True
        account_mismatch_warning = None
        if authenticated and connected_email:
            if connected_email.strip().lower() != GMAIL_INBOX_ADDRESS.strip().lower():
                mailbox_match = False
                account_mismatch_warning = (
                    f"Account Mismatch Warning: The authenticated Gmail account ({connected_email}) "
                    f"does not match the configured official inbox ({GMAIL_INBOX_ADDRESS}). "
                    f"Please disconnect and authorize {GMAIL_INBOX_ADDRESS}."
                )

        status_str = "connected" if (authenticated and mailbox_match) else (
            "account_mismatch" if (authenticated and not mailbox_match) else (
                "configured" if configured else "unconfigured"
            )
        )

        message_str = account_mismatch_warning if account_mismatch_warning else (
            f"Official mailbox {GMAIL_INBOX_ADDRESS} connected and operational" if authenticated else (
                f"OAuth configured. Please authorize official account {GMAIL_INBOX_ADDRESS}" if configured else
                f"Gmail OAuth credentials missing. Set GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET in backend/.env for {GMAIL_INBOX_ADDRESS}"
            )
        )

        return {
            "enabled": GMAIL_ENABLED,
            "configured": configured,
            "authenticated": authenticated,
            "official_inbox_address": GMAIL_INBOX_ADDRESS,
            "connected_email": connected_email,
            "email_address": connected_email,
            "mailbox_match": mailbox_match,
            "account_mismatch_warning": account_mismatch_warning,
            "redirect_uri": GMAIL_REDIRECT_URI,
            "status": status_str,
            "message": message_str
        }

