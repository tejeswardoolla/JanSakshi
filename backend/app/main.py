"""
JanSakshi – AI-Powered Public Complaint Verification and Accountability System
FastAPI Backend – Phase 6 Gmail AI Integration & Unified Email Complaint Processing
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html
from sqlalchemy import inspect

from app.database import Base, engine
import app.models  # Ensures all models (PhysicalIssue, Complaint, Evidence, ComplaintEvent, AIAnalysis, DuplicateMatch, EmailMessage, Department, User) register
from app.routes import (
    complaints, ai_routes, issues, duplicates, email_routes,
    auth_routes, authority_routes, resolution_routes
)
from app.core.config import ALLOWED_ORIGINS, APP_ENV

logger = logging.getLogger("jansakshi.lifecycle")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inspect database schema on startup to verify deployment readiness
    try:
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())
        dialect_name = engine.dialect.name

        if APP_ENV == "production":
            required_tables = {"complaints", "departments", "users", "evidence", "complaint_events"}
            missing_tables = required_tables - existing_tables
            if missing_tables:
                logger.warning(
                    f"[DATABASE WARNING] Production {dialect_name} database is missing core tables: {missing_tables}. "
                    f"Applying non-destructive Base.metadata.create_all(). Run migration script to import historical data."
                )
            else:
                logger.info(
                    f"[DATABASE] Verified production {dialect_name} database schema with {len(existing_tables)} tables."
                )
        Base.metadata.create_all(bind=engine)
        from app.database import ensure_email_message_schema
        ensure_email_message_schema()
    except Exception as db_err:
        logger.error(f"[DATABASE ERROR] Startup database verification failed: {db_err}")
        raise RuntimeError(f"Application startup aborted due to database initialization failure: {db_err}") from db_err
    yield

app = FastAPI(
    title="JanSakshi API",
    description="AI-Powered Public Complaint Verification & Departmental Accountability Platform – Phase 9 Release",
    version="1.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
    lifespan=lifespan
)

@app.get("/api/redoc", include_in_schema=False)
async def redoc_html():
    """
    Pinned stable ReDoc 2.4.0 documentation viewer.
    Replaces unpinned redoc@next which introduced syntax errors in ESM worker bundles.
    """
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - ReDoc",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@2.4.0/bundles/redoc.standalone.js",
        redoc_favicon_url="https://fastapi.tiangolo.com/img/favicon.png",
        with_google_fonts=True,
    )

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register modular routes
app.include_router(complaints.router)
app.include_router(issues.router)
app.include_router(ai_routes.router)
app.include_router(duplicates.router)
app.include_router(email_routes.router)
app.include_router(auth_routes.router)
app.include_router(authority_routes.router)
# Phase 9: Standalone Civic Equity Intelligence unmounted per scope directive
# app.include_router(equity_routes.router)
app.include_router(resolution_routes.router)

@app.get("/api/health", tags=["System"])
async def health():
    return {
        "status": "ok",
        "service": "JanSakshi API",
        "version": "8.0.0",
        "phase": 8
    }
