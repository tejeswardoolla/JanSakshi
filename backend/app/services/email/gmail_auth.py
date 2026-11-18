import os
import time
import json
import secrets
import hashlib
import base64
import logging
import threading
from typing import Optional, Dict, Any, Tuple
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from app.core.config import (
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
    Thread-safe and persistent store for OAuth 2.0 PKCE code verifiers and state tokens.
    Prevents CSRF, enforces TTL expiration (15 min), and guarantees single-use consumption.
    """
    _lock = threading.Lock()

    @classmethod
    def _load_states(cls) -> Dict[str, Dict[str, Any]]:
        if not os.path.exists(GMAIL_OAUTH_STATE_PATH):
            return {}
        try:
            with open(GMAIL_OAUTH_STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not read OAuth state store: {e}")
            return {}

    @classmethod
    def _save_states(cls, states: Dict[str, Dict[str, Any]]) -> None:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(GMAIL_OAUTH_STATE_PATH)), exist_ok=True)
            with open(GMAIL_OAUTH_STATE_PATH, "w", encoding="utf-8") as f:
                json.dump(states, f)
        except Exception as e:
            logger.error(f"Could not save OAuth states: {e}")

    @classmethod
    def store(cls, state: str, code_verifier: str, ttl_seconds: int = 900) -> None:
        """Saves a state -> code_verifier mapping with expiration."""
        with cls._lock:
            now = time.time()
            states = cls._load_states()
            # Prune expired states
            valid_states = {s: v for s, v in states.items() if v.get("expires_at", 0) > now}
            valid_states[state] = {
                "code_verifier": code_verifier,
                "expires_at": now + ttl_seconds,
            }
            cls._save_states(valid_states)

    @classmethod
    def consume(cls, state: Optional[str]) -> Optional[str]:
        """
        Atomically validates, retrieves, and deletes the code_verifier for the given state.
        Returns code_verifier if valid and unexpired; None otherwise.
        """
        if not state:
            return None
        with cls._lock:
            now = time.time()
            states = cls._load_states()
            entry = states.pop(state, None)
            valid_states = {s: v for s, v in states.items() if v.get("expires_at", 0) > now}
            cls._save_states(valid_states)

            if not entry:
                logger.warning("OAuth state verification failed: state token not found.")
                return None
            if entry.get("expires_at", 0) < now:
                logger.warning("OAuth state verification failed: session expired.")
                return None
            return entry.get("code_verifier")


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
    def consume_oauth_state(cls, state: Optional[str]) -> Optional[str]:
        """Validates and retrieves the PKCE code_verifier for an OAuth state, deleting it immediately."""
        return OAuthStateManager.consume(state)

    @classmethod
    def generate_auth_url(cls, state: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
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
            OAuthStateManager.store(oauth_state, code_verifier, ttl_seconds=900)

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

