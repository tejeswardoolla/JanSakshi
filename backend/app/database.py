import os
import logging
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

logger = logging.getLogger("jansakshi.database")

# Anchor SQLite database to backend/jansakshi.db to prevent working-directory divergence
BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BACKEND_DIR / "jansakshi.db"

def normalize_database_url(url: str) -> str:
    """
    Normalizes database URLs for SQLAlchemy 2.x and Neon PostgreSQL:
    - Replaces legacy postgres:// with postgresql://
    - Ensures sslmode=require for remote Neon/PostgreSQL endpoints if omitted
    """
    if not url:
        return f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"

    normalized = url.strip()
    if normalized.startswith("postgres://"):
        normalized = "postgresql://" + normalized[len("postgres://"):]

    # If remote PostgreSQL without sslmode, append sslmode=require
    if normalized.startswith("postgresql://") and "@" in normalized and "localhost" not in normalized and "127.0.0.1" not in normalized:
        if "sslmode=" not in normalized:
            sep = "&" if "?" in normalized else "?"
            normalized = f"{normalized}{sep}sslmode=require"

    return normalized

RAW_DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH.as_posix()}")
DATABASE_URL = normalize_database_url(RAW_DATABASE_URL)

is_sqlite = DATABASE_URL.startswith("sqlite")
is_postgres = DATABASE_URL.startswith("postgresql")

engine_kwargs = {
    "echo": False,
}

if is_sqlite:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
elif is_postgres:
    # Production resilience for Neon PostgreSQL:
    # pool_pre_ping checks connection liveness before every checkout (crucial for Neon serverless scale-to-zero)
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_recycle"] = int(os.getenv("DB_POOL_RECYCLE", "300"))
    engine_kwargs["pool_size"] = int(os.getenv("DB_POOL_SIZE", "10"))
    engine_kwargs["max_overflow"] = int(os.getenv("DB_MAX_OVERFLOW", "20"))
    engine_kwargs["pool_timeout"] = int(os.getenv("DB_POOL_TIMEOUT", "30"))

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """FastAPI dependency for thread-safe database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
