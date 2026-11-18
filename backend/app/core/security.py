"""
JanSakshi Security & Authentication Module
Provides password hashing via bcrypt, JWT token issuing and validation with
cryptographic token rotation, revocation tracking, and configurable session policies.
Supports separate production and local hackathon demonstration policies.
"""

import os
import uuid
import logging
import datetime
import bcrypt
import jwt
from typing import Optional, List, Dict, Any, Tuple
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.authority import User, RevokedToken
from app.core.config import utc_now

logger = logging.getLogger("jansakshi.security")

# Secret key and algorithm for JWT
DEFAULT_INSECURE_SECRET = "jansakshi-authority-super-secure-key-2026-phase7"
_env_secret = os.getenv("JWT_SECRET_KEY", "").strip()
_app_env = os.getenv("APP_ENV", "development").strip().lower()

if _app_env == "production":
    if not _env_secret or _env_secret == DEFAULT_INSECURE_SECRET:
        raise RuntimeError(
            "CRITICAL SECURITY CONFIGURATION ERROR: A strong, unique JWT_SECRET_KEY "
            "must be configured in environment variables for production deployments. "
            "Refusing to boot with empty or insecure default secret."
        )
    SECRET_KEY = _env_secret
else:
    SECRET_KEY = _env_secret or DEFAULT_INSECURE_SECRET

ALGORITHM = "HS256"

# -----------------------------------------------------------------------------
# Configurable Session Policies
# -----------------------------------------------------------------------------
# By default, JanSakshi runs with strict short-lived production access tokens (30 minutes).
# Local hackathon demo mode must be EXPLICITLY enabled via JANSAKSHI_SESSION_POLICY=demo
# or JANSAKSHI_DEMO_MODE=true. It is NEVER silently enabled for production.
SESSION_POLICY = os.getenv("JANSAKSHI_SESSION_POLICY", "standard").strip().lower()
DEMO_MODE_FLAG = os.getenv("JANSAKSHI_DEMO_MODE", "false").strip().lower() in ("true", "1", "yes")

IS_DEMO_POLICY = (SESSION_POLICY == "demo") or DEMO_MODE_FLAG

if IS_DEMO_POLICY:
    # Hackathon Demo Mode: Extended access token window strictly for evaluations
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "720"))  # 12 hours
    REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
    logger.warning(
        "[SECURITY POLICY] Local Hackathon Demonstration Mode ACTIVE. "
        "Access token lifetime: %d minutes. DO NOT ENABLE IN PRODUCTION.",
        ACCESS_TOKEN_EXPIRE_MINUTES
    )
else:
    # Standard Production Policy: Short-lived access tokens with secure refresh rotation
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))  # 30 minutes
    REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))  # 7 days
    logger.info(
        "[SECURITY POLICY] Standard Secure Session Policy ACTIVE. "
        "Access token: %d minutes, Refresh token: %d days.",
        ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS
    )

ACCESS_TOKEN_EXPIRE_HOURS = ACCESS_TOKEN_EXPIRE_MINUTES / 60.0

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

def hash_password(plain_password: str) -> str:
    """Hash password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False

def create_access_token(data: dict, expires_delta: Optional[datetime.timedelta] = None) -> str:
    """
    Generate short-lived signed JWT access token with unique JTI.
    Data must include sub (username), role, and user identity fields.
    """
    to_encode = data.copy()
    now = utc_now()
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    jti = str(uuid.uuid4())
    to_encode.update({
        "exp": expire,
        "iat": now,
        "type": "access",
        "jti": jti,
        "policy": "demo" if IS_DEMO_POLICY else "standard"
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(data: dict, expires_delta: Optional[datetime.timedelta] = None) -> str:
    """
    Generate long-lived refresh token with unique JTI for rotation and revocation.
    """
    to_encode = data.copy()
    now = utc_now()
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + datetime.timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    jti = str(uuid.uuid4())
    to_encode.update({
        "exp": expire,
        "iat": now,
        "type": "refresh",
        "jti": jti
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str, expected_type: Optional[str] = "access") -> Optional[dict]:
    """Decode and validate JWT access or refresh token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if expected_type and payload.get("type") != expected_type:
            logger.warning(
                "Token type mismatch: expected '%s', got '%s'",
                expected_type, payload.get("type")
            )
            return None
        return payload
    except jwt.PyJWTError:
        return None

def decode_access_token(token: str) -> Optional[dict]:
    """Backward-compatible helper: decode access token."""
    return decode_token(token, expected_type="access")

def decode_refresh_token(token: str) -> Optional[dict]:
    """Decode and validate refresh token."""
    return decode_token(token, expected_type="refresh")

# -----------------------------------------------------------------------------
# Token Revocation Management
# -----------------------------------------------------------------------------
def is_token_revoked(db: Session, jti: str) -> bool:
    """Check if token JTI is recorded as revoked in the database."""
    if not jti:
        return False
    return db.query(RevokedToken).filter(RevokedToken.jti == jti).first() is not None

def revoke_token(
    db: Session,
    jti: str,
    token_type: str = "access",
    expires_at: Optional[datetime.datetime] = None,
    username: Optional[str] = None
) -> None:
    """Record token JTI in revoked_tokens table to prevent reuse."""
    if not jti:
        return
    existing = db.query(RevokedToken).filter(RevokedToken.jti == jti).first()
    if not existing:
        if expires_at is None:
            expires_at = utc_now() + datetime.timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        revoked = RevokedToken(
            jti=jti,
            token_type=token_type,
            username=username,
            expires_at=expires_at,
            revoked_at=utc_now()
        )
        try:
            db.add(revoked)
            db.commit()
        except Exception:
            db.rollback()
            raise

def cleanup_expired_revoked_tokens(db: Session) -> int:
    """
    Safely purges expired revocation records from revoked_tokens table.
    Records whose original expires_at has passed are already rejected by
    cryptographic JWT timestamp validation (now > exp), so their revocation records can
    be safely deleted without compromising security.
    """
    now = utc_now()
    deleted_count = db.query(RevokedToken).filter(RevokedToken.expires_at < now).delete()
    db.commit()
    return deleted_count

async def get_current_user(token: Optional[str] = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """Dependency: Extract current authenticated user from Bearer access token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate authority credentials or session expired.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception
    
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    
    jti = payload.get("jti")
    if jti and is_token_revoked(db, jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has been revoked or logged out. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception
    
    user = db.query(User).filter(User.username == username, User.is_active == True).first()
    if user is None:
        raise credentials_exception
    
    return user

def require_roles(allowed_roles: List[str]):
    """Role-based authorization dependency factory. Strictly enforces the specified allowed roles."""
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role in {allowed_roles}, your role is '{current_user.role}'."
            )
        return current_user
    return role_checker


