import os
import datetime
from typing import Optional
from dotenv import load_dotenv

# Explicitly load .env file from backend directory if present
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
env_path = os.path.join(BASE_DIR, ".env")
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path, override=False)

APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
PORT = int(os.getenv("PORT", "8000"))
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").strip()

# Production-safe CORS origin resolution
_raw_origins = os.getenv("ALLOWED_ORIGINS", "").strip()
if _raw_origins:
    ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]
else:
    if APP_ENV == "production":
        # In production, require explicit origins or default to FRONTEND_URL
        ALLOWED_ORIGINS = [FRONTEND_URL] if FRONTEND_URL else []
    else:
        ALLOWED_ORIGINS = [
            "http://localhost:5173",
            "http://localhost:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:3000"
        ]

# Ensure configured FRONTEND_URL is always included in allowed origins
if FRONTEND_URL and FRONTEND_URL not in ALLOWED_ORIGINS:
    ALLOWED_ORIGINS.append(FRONTEND_URL)

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./jansakshi.db")

# Timezone standard
DEFAULT_TIMEZONE = "Asia/Kolkata"

# -------------------------------------------------------------
# Google Gemini Multimodal AI Settings (Phase 4)
# -------------------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip() or "gemini-3.8-flash"
AI_ANALYSIS_ENABLED = os.getenv("AI_ANALYSIS_ENABLED", "true").lower() in ("true", "1", "yes")
AI_CONFIDENCE_THRESHOLD = float(os.getenv("AI_CONFIDENCE_THRESHOLD", "0.75"))

def is_gemini_configured() -> bool:
    """Returns True only if a non-empty Gemini API key is provided and AI analysis is enabled."""
    return bool(GEMINI_API_KEY) and AI_ANALYSIS_ENABLED

# -------------------------------------------------------------
# Gmail AI Integration Settings (Phase 6)
# -------------------------------------------------------------
GMAIL_ENABLED = os.getenv("GMAIL_ENABLED", "false").lower() in ("true", "1", "yes")
GMAIL_INBOX_ADDRESS = os.getenv("GMAIL_INBOX_ADDRESS", "jansakshiofficial@gmail.com").strip().lower() or "jansakshiofficial@gmail.com"
GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID", "").strip()
GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET", "").strip()
GMAIL_REDIRECT_URI = os.getenv("GMAIL_REDIRECT_URI", "http://localhost:8000/api/email/oauth/callback").strip()
GMAIL_CREDENTIALS_FILE = os.getenv("GMAIL_CREDENTIALS_FILE", os.path.join(BASE_DIR, "storage", "gmail_credentials.json"))
GMAIL_TOKEN_PATH = os.getenv("GMAIL_TOKEN_PATH", os.path.join(BASE_DIR, "storage", "gmail_tokens.json"))
GMAIL_OAUTH_STATE_PATH = os.getenv("GMAIL_OAUTH_STATE_PATH", os.path.join(BASE_DIR, "storage", "gmail_oauth_states.json"))
GMAIL_INBOX_LABEL = os.getenv("GMAIL_INBOX_LABEL", "INBOX").strip()
GMAIL_POLL_INTERVAL_SECONDS = int(os.getenv("GMAIL_POLL_INTERVAL_SECONDS", "60"))
CRON_SECRET = os.getenv("CRON_SECRET", "").strip()
GMAIL_LOCK_DATABASE_URL = os.getenv("GMAIL_LOCK_DATABASE_URL", "").strip()
DEFAULT_LOGO_URL = "https://raw.githubusercontent.com/tejeswardoolla/JanSakshi/main/frontend/public/assets/jansakshi-logo.jpg"
EMAIL_LOGO_URL = os.getenv("EMAIL_LOGO_URL", DEFAULT_LOGO_URL).strip() or DEFAULT_LOGO_URL
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]

def is_gmail_configured() -> bool:
    """Returns True if client credentials or valid token file exists."""
    has_oauth_keys = bool(GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET)
    has_cred_file = os.path.exists(GMAIL_CREDENTIALS_FILE)
    has_token_file = os.path.exists(GMAIL_TOKEN_PATH)
    return has_oauth_keys or has_cred_file or has_token_file

def utc_now() -> datetime.datetime:
    """Single source of truth for timezone-aware UTC datetime."""
    return datetime.datetime.now(datetime.timezone.utc)

# -------------------------------------------------------------
# Hackathon Judge Demo Access Configuration
# -------------------------------------------------------------
def get_judge_demo_expiry() -> Optional[datetime.datetime]:
    """
    Parses and returns the configured absolute UTC expiry timestamp for judge demo access.
    Fails closed (returns None) if missing, empty, or unparseable.
    """
    raw = os.getenv("JANSAKSHI_JUDGE_DEMO_EXPIRES_AT", "").strip()
    if not raw:
        return None
    try:
        clean = raw.replace("Z", "+00:00")
        dt = datetime.datetime.fromisoformat(clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        else:
            dt = dt.astimezone(datetime.timezone.utc)
        return dt
    except Exception as err:
        import logging
        logging.getLogger("jansakshi.config").warning(
            "Invalid JANSAKSHI_JUDGE_DEMO_EXPIRES_AT timestamp '%s': %s", raw, err
        )
        return None

def is_judge_demo_active() -> bool:
    """
    Returns True ONLY if judge demo mode is explicitly enabled via environment variable
    AND a valid absolute UTC expiry timestamp is configured AND current time < expiry.
    Fails closed otherwise.
    """
    enabled = os.getenv("JANSAKSHI_JUDGE_DEMO_ENABLED", "false").strip().lower() in ("true", "1", "yes")
    if not enabled:
        return False
    expiry = get_judge_demo_expiry()
    if expiry is None:
        return False
    return utc_now() < expiry
