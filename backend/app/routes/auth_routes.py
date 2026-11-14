"""
JanSakshi Authentication Routes
Provides login and profile inspection endpoints for authority users.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, EmailStr
from typing import Optional
from sqlalchemy.orm import Session
import datetime

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
from app.core.config import utc_now

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


