"""
JanSakshi – AI-Powered Public Complaint Verification and Accountability System
FastAPI Backend – Phase 6 Gmail AI Integration & Unified Email Complaint Processing
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
import app.models  # Ensures all models (PhysicalIssue, Complaint, Evidence, ComplaintEvent, AIAnalysis, DuplicateMatch, EmailMessage, Department, User) register
from app.routes import (
    complaints, ai_routes, issues, duplicates, email_routes,
    auth_routes, authority_routes, resolution_routes
)
from app.core.config import ALLOWED_ORIGINS

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure database schema is up-to-date on startup
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(
    title="JanSakshi API",
    description="AI-Powered Public Complaint Verification & Departmental Accountability Platform – Phase 9 Release",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan
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
