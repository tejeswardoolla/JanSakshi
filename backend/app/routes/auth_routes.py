"""
JanSakshi Authentication Routes
Provides login and profile inspection endpoints for authority users.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from sqlalchemy.orm import Session
import datetime
import time
import threading
import logging
from collections import defaultdict

from app.database import get_db
from app.models.authority import User, Department
from app.core.security import (
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    decode_access_token,
    decode_refresh_token,
    revoke_token,
    is_token_revoked,
    get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    IS_DEMO_POLICY
)
from app.core.config import utc_now, get_judge_demo_expiry, is_judge_demo_active
from app.services.judge_demo_service import get_judge_demo_account, classify_database_target

logger = logging.getLogger("jansakshi.auth")

# In-memory sliding-window rate limiter for judge demo endpoints
_demo_rate_lock = threading.Lock()
_demo_rate_attempts: dict[str, list[float]] = defaultdict(list)
_DEMO_RATE_LIMIT_PER_MINUTE = 15

def _check_demo_rate_limit(client_ip: str) -> bool:
    now = time.time()
    with _demo_rate_lock:
        timestamps = _demo_rate_attempts[client_ip]
        valid_ts = [t for t in timestamps if now - t < 60]
        if len(valid_ts) >= _DEMO_RATE_LIMIT_PER_MINUTE:
            _demo_rate_attempts[client_ip] = valid_ts
            return False
        valid_ts.append(now)
        _demo_rate_attempts[client_ip] = valid_ts
        return True

router = APIRouter(prefix="/api/auth", tags=["Authority Authentication"])

class LoginRequest(BaseModel):
    username: str
    password: str

class RefreshRequest(BaseModel):
    refresh_token: str

class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    role: str
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    department_code: Optional[str] = None
    authorized_departments: list[int] = []
    has_all_departments: bool = False
    is_active: bool

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int = 1800  # seconds
    policy: str = "standard"
    user: UserResponse

class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 1800
    policy: str = "standard"

class JudgeDemoRoleInfo(BaseModel):
    role: str
    label: str
    description: str

class JudgeDemoStatusResponse(BaseModel):
    enabled: bool
    expires_at: Optional[str] = None
    roles: list[JudgeDemoRoleInfo] = []

@router.post("/login", response_model=TokenResponse)
async def login(credentials: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate an authority user and return JWT access and refresh tokens."""
    username = credentials.username.strip()
    user = db.query(User).filter(User.username == username).first()
    
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password."
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated. Please contact the administrator."
        )
    
    user.last_login_at = utc_now()
    db.commit()

    dept_name = user.department.name if user.department else None
    dept_code = user.department.code if user.department else None

    token_data = {
        "sub": user.username,
        "uid": user.id,
        "role": user.role,
        "name": user.full_name,
        "dept": dept_code
    }
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    auth_depts = user.get_authorized_department_ids()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        policy="demo" if IS_DEMO_POLICY else "standard",
        user=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            department_id=user.department_id,
            department_name=dept_name,
            department_code=dept_code,
            authorized_departments=auth_depts,
            has_all_departments=len(auth_depts) > 1,
            is_active=user.is_active
        )
    )

@router.post("/refresh", response_model=RefreshResponse)
async def refresh_token_endpoint(body: RefreshRequest, db: Session = Depends(get_db)):
    """
    Secure Refresh Token Endpoint with Cryptographic Rotation.
    Validates the refresh token, revokes the used token to prevent replay attacks,
    and returns a brand-new access token and rotated refresh token.
    """
    raw_token = body.refresh_token.strip()
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token required."
        )

    payload = decode_refresh_token(raw_token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token. Please sign in again."
        )

    jti = payload.get("jti")
    if jti and is_token_revoked(db, jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked or invalidated. Please sign in again."
        )

    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token payload."
        )

    user = db.query(User).filter(User.username == username, User.is_active == True).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account no longer active."
        )

    # Phase 6: Enforce judge demo lifecycle on refresh
    if payload.get("is_judge_demo"):
        if not is_judge_demo_active():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Judge demo access has expired or is disabled. Please contact the administrator."
            )
        token_demo_exp = payload.get("demo_expires_at")
        if token_demo_exp:
            try:
                exp_dt = datetime.datetime.fromisoformat(token_demo_exp.replace("Z", "+00:00"))
                if utc_now() >= exp_dt:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Judge demo access has expired."
                    )
            except HTTPException:
                raise
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid judge demo session expiration."
                )

    # Cryptographic Rotation: Revoke the old refresh token immediately
    if jti:
        exp_ts = payload.get("exp")
        exp_dt = datetime.datetime.fromtimestamp(exp_ts, tz=datetime.timezone.utc) if exp_ts else None
        try:
            revoke_token(db, jti=jti, token_type="refresh", expires_at=exp_dt, username=username)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been revoked or invalidated by concurrent request. Please sign in again."
            )

    dept_code = user.department.code if user.department else None
    token_data = {
        "sub": user.username,
        "uid": user.id,
        "role": user.role,
        "name": user.full_name,
        "dept": dept_code
    }
    if payload.get("is_judge_demo"):
        token_data["is_judge_demo"] = True
        token_data["demo_role"] = payload.get("demo_role", user.role)
        token_data["demo_expires_at"] = payload.get("demo_expires_at")

    new_access_token = create_access_token(token_data)
    new_refresh_token = create_refresh_token(token_data)

    return RefreshResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        policy="demo" if IS_DEMO_POLICY else "standard"
    )

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Retrieve currently authenticated authority user profile."""
    dept_name = current_user.department.name if current_user.department else None
    dept_code = current_user.department.code if current_user.department else None
    auth_depts = current_user.get_authorized_department_ids()

    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        department_id=current_user.department_id,
        department_name=dept_name,
        department_code=dept_code,
        authorized_departments=auth_depts,
        has_all_departments=len(auth_depts) > 1,
        is_active=current_user.is_active
    )

@router.post("/logout")
async def logout(
    request: Request,
    body: Optional[LogoutRequest] = None,
    db: Session = Depends(get_db)
):
    """
    Server-enforced session logout and token revocation.
    Revokes the current access token and refresh token in the database.
    """
    # 1. Revoke access token if present in Authorization header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        payload = decode_access_token(token)
        if payload:
            jti = payload.get("jti")
            sub = payload.get("sub")
            exp_ts = payload.get("exp")
            exp_dt = datetime.datetime.fromtimestamp(exp_ts, tz=datetime.timezone.utc) if exp_ts else None
            revoke_token(db, jti=jti, token_type="access", expires_at=exp_dt, username=sub)

    # 2. Revoke refresh token if provided
    if body and body.refresh_token:
        r_payload = decode_refresh_token(body.refresh_token)
        if r_payload:
            r_jti = r_payload.get("jti")
            r_sub = r_payload.get("sub")
            r_exp_ts = r_payload.get("exp")
            r_exp_dt = datetime.datetime.fromtimestamp(r_exp_ts, tz=datetime.timezone.utc) if r_exp_ts else None
            revoke_token(db, jti=r_jti, token_type="refresh", expires_at=r_exp_dt, username=r_sub)

    return {"status": "ok", "message": "Successfully logged out and session credentials revoked."}

# -----------------------------------------------------------------------------
# Hackathon 10-Day Judge Demo Authentication Endpoints
# -----------------------------------------------------------------------------
ALLOWED_JUDGE_ROLES = {"admin", "authority_officer", "department_officer"}

@router.get("/judge-demo/status", response_model=JudgeDemoStatusResponse)
async def get_judge_demo_status():
    """
    Public status endpoint reporting whether temporary judge demo access is enabled and unexpired.
    Never exposes passwords, signing secrets, or private keys.
    """
    active = is_judge_demo_active()
    expiry = get_judge_demo_expiry()
    if not active or not expiry:
        return JudgeDemoStatusResponse(enabled=False, expires_at=None, roles=[])

    return JudgeDemoStatusResponse(
        enabled=True,
        expires_at=expiry.isoformat(),
        roles=[
            JudgeDemoRoleInfo(
                role="admin",
                label="Municipal Admin",
                description="AI & Complaint Management"
            ),
            JudgeDemoRoleInfo(
                role="authority_officer",
                label="Authority Officer",
                description="Decisions & Department Assignment"
            ),
            JudgeDemoRoleInfo(
                role="department_officer",
                label="Department Operations",
                description="All Six Department Workspaces"
            )
        ]
    )

@router.post("/judge-demo/{role}", response_model=TokenResponse)
async def judge_demo_login(
    role: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Secure, password-free, one-click judge authentication for hackathon evaluation.
    Requires server-side judge demo mode to be enabled and unexpired.
    Applies rate limiting and audit logging.
    Authenticates dedicated demo user using existing JWT architecture.
    """
    normalized_role = role.strip().lower()
    client_ip = request.client.host if request.client else "unknown"

    # 1. Reject invalid roles immediately
    if normalized_role not in ALLOWED_JUDGE_ROLES:
        logger.warning(
            "Judge demo login rejected: invalid role '%s', client_ip=%s",
            normalized_role, client_ip
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid demo role '{role}'. Allowed demo roles: {sorted(list(ALLOWED_JUDGE_ROLES))}"
        )

    # 2. Reject if demo is disabled or expired (fail closed)
    if not is_judge_demo_active():
        logger.warning(
            "Judge demo login rejected: demo disabled or expired, role=%s, client_ip=%s",
            normalized_role, client_ip
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Judge demo access is disabled or has expired. Please contact the administrator."
        )

    expiry_dt = get_judge_demo_expiry()
    if not expiry_dt:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Judge demo expiry is not configured or invalid."
        )

    # 3. Verify connected database is strictly an authorized dedicated demo database
    db_target = classify_database_target(db)
    if db_target != "DEMO":
        logger.critical(
            "Judge demo login rejected: connected database is not an approved demo database (%s), client_ip=%s",
            db_target, client_ip
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Judge demo access is restricted to the dedicated demo environment."
        )

    # 4. Rate limiting (max 15 requests per minute per IP)
    if not _check_demo_rate_limit(client_ip):
        logger.warning("Judge demo login rate limit exceeded for IP %s", client_ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded for judge demo access. Please try again shortly."
        )

    # 5. Retrieve already-provisioned judge demo user account (STRICTLY READ-ONLY)
    user = get_judge_demo_account(db, normalized_role)
    if not user or not user.is_active:
        logger.warning(
            "Judge demo login rejected: account for role '%s' has not been pre-seeded or is inactive",
            normalized_role
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Judge demo account has not been provisioned. Please contact the administrator."
        )

    dept_name = user.department.name if user.department else None
    dept_code = user.department.code if user.department else None

    # 5. Issue JWT tokens carrying dedicated judge demo claims
    token_data = {
        "sub": user.username,
        "uid": user.id,
        "role": user.role,
        "name": user.full_name,
        "dept": dept_code,
        "is_judge_demo": True,
        "demo_role": user.role,
        "demo_expires_at": expiry_dt.isoformat()
    }

    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    auth_depts = user.get_authorized_department_ids()

    logger.info(
        "Judge demo login granted: role=%s, user=%s, client_ip=%s, timestamp=%s",
        user.role, user.username, client_ip, utc_now().isoformat()
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        policy="demo" if IS_DEMO_POLICY else "standard",
        user=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            department_id=user.department_id,
            department_name=dept_name,
            department_code=dept_code,
            authorized_departments=auth_depts,
            has_all_departments=len(auth_depts) > 1,
            is_active=user.is_active
        )
    )

