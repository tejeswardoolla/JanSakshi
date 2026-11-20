import os
import logging
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool

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

# Dedicated Lock Database URL for Neon Session-Level Advisory Locking
RAW_LOCK_URL = os.getenv("GMAIL_LOCK_DATABASE_URL", "").strip()
GMAIL_LOCK_DATABASE_URL = normalize_database_url(RAW_LOCK_URL) if RAW_LOCK_URL else ""

def validate_lock_url_matches_database(lock_url: str, app_url: str):
    """
    Validates that GMAIL_LOCK_DATABASE_URL points to the same Neon database and cluster as DATABASE_URL,
    without exposing or logging credentials.
    """
    if not lock_url or not app_url:
        return
    import urllib.parse
    try:
        p_lock = urllib.parse.urlparse(lock_url)
        p_app = urllib.parse.urlparse(app_url)
    except Exception:
        return

    # Check database name (e.g. /neondb)
    db_lock = p_lock.path.strip('/')
    db_app = p_app.path.strip('/')
    if db_lock and db_app and db_lock != db_app:
        raise ValueError(
            f"GMAIL_LOCK_DATABASE_URL targets database '{db_lock}', but DATABASE_URL targets '{db_app}'. "
            f"The dedicated lock engine must point to the same database."
        )

    # Check host / cluster (stripping -pooler from both)
    host_lock = (p_lock.hostname or "").lower()
    host_app = (p_app.hostname or "").lower()
    if host_lock and host_app:
        base_lock = host_lock.replace("-pooler", "")
        base_app = host_app.replace("-pooler", "")
        if base_lock != base_app:
            raise ValueError(
                f"GMAIL_LOCK_DATABASE_URL host ('{p_lock.hostname}') does not match DATABASE_URL cluster ('{base_app}'). "
                f"The dedicated lock engine must target the direct endpoint of the same Neon database cluster."
            )

def get_lock_engine():
    """
    Returns a dedicated, unpooled Engine exclusively for session-level PostgreSQL advisory locks.
    Uses GMAIL_LOCK_DATABASE_URL (Neon direct non-pooled endpoint) when on PostgreSQL.
    Enforces NullPool so that connections are never recycled or reused across application sessions.
    Fails safely with a clear configuration error if the direct lock connection is missing or incorrectly configured.
    Never prints or exposes database credentials.
    """
    # 1. If explicit GMAIL_LOCK_DATABASE_URL is provided:
    if GMAIL_LOCK_DATABASE_URL:
        if GMAIL_LOCK_DATABASE_URL.startswith("postgresql"):
            if "-pooler" in GMAIL_LOCK_DATABASE_URL:
                raise ValueError("GMAIL_LOCK_DATABASE_URL is misconfigured: points to a pooled (-pooler) endpoint. Direct endpoint required.")
            if is_postgres and DATABASE_URL:
                validate_lock_url_matches_database(GMAIL_LOCK_DATABASE_URL, DATABASE_URL)
            return create_engine(GMAIL_LOCK_DATABASE_URL, poolclass=NullPool, connect_args={"connect_timeout": 15})
        return create_engine(GMAIL_LOCK_DATABASE_URL, poolclass=NullPool)

    # 2. Check if TARGET_DATABASE_URL is configured (e.g. during local tests against Neon direct)
    target_raw = os.getenv("TARGET_DATABASE_URL", "").strip()
    if target_raw:
        target_norm = normalize_database_url(target_raw)
        if target_norm.startswith("postgresql"):
            if "-pooler" not in target_norm:
                return create_engine(target_norm, poolclass=NullPool, connect_args={"connect_timeout": 15})

    # 3. If primary DATABASE_URL is PostgreSQL:
    if is_postgres:
        if "-pooler" in DATABASE_URL:
            raise RuntimeError(
                "GMAIL_LOCK_DATABASE_URL is required on Neon PostgreSQL when DATABASE_URL uses a pooled (-pooler) endpoint. "
                "Configure GMAIL_LOCK_DATABASE_URL with Neon's direct non-pooled endpoint."
            )
        # Direct non-pooled PostgreSQL fallback
        return create_engine(DATABASE_URL, poolclass=NullPool, connect_args={"connect_timeout": 15})

    # 4. In SQLite / local dev environments:
    return engine

import threading

# Process-level concurrency lock for local SQLite migrations
_schema_migration_lock = threading.Lock()
MIGRATION_ADVISORY_LOCK_ID = 999888777

def ensure_email_message_schema(bind=None):
    """
    Concurrency-safe, non-destructive schema verification and migration for email_messages table.
    Ensures persistent retry tracking columns exist without altering or deleting existing records.
    Safe for simultaneous multi-instance cold starts (e.g. Vercel serverless containers):
    - Uses verified direct lock connection from get_lock_engine() on PostgreSQL.
    - Aborts migration if advisory lock acquisition fails, invalidating the connection.
    - Invalidates connection on unlock failure to prevent leaking locked sessions back to pool.
    - Uses process locking and idempotent duplicate-column handling on SQLite.
    - Fails loudly with RuntimeError if schema cannot be verified or migrated.
    """
    from sqlalchemy import inspect, text
    target_engine = bind or engine
    is_pg = target_engine.dialect.name == "postgresql"

    with _schema_migration_lock:
        # On PostgreSQL, use verified direct unpooled lock engine from get_lock_engine()
        # unless an explicit test bind was provided
        migration_engine = get_lock_engine() if (is_pg and bind is None) else target_engine
        try:
            conn = migration_engine.connect()
        except Exception as conn_err:
            logger.error(f"Failed to check out dedicated lock connection for schema migration: {conn_err}")
            raise RuntimeError(f"Database migration failure: unable to connect to database for migration: {conn_err}") from conn_err

        lock_acquired = False
        try:
            # On PostgreSQL, acquire dedicated session advisory lock during migration
            if is_pg:
                try:
                    conn.execute(text(f"SELECT pg_advisory_lock({MIGRATION_ADVISORY_LOCK_ID})"))
                    conn.commit()
                    lock_acquired = True
                except Exception as lock_err:
                    logger.error(f"Failed to acquire migration advisory lock on PostgreSQL: {lock_err}")
                    try:
                        conn.invalidate()
                    except Exception:
                        pass
                    raise RuntimeError(f"Database migration failure: unable to acquire migration advisory lock: {lock_err}") from lock_err

            inspector = inspect(migration_engine)
            if "email_messages" in inspector.get_table_names():
                columns = {c["name"] for c in inspector.get_columns("email_messages")}

                # 1. acknowledgement_retry_count
                if "acknowledgement_retry_count" not in columns:
                    logger.info("Migrating email_messages schema: adding column acknowledgement_retry_count")
                    ddl = (
                        "ALTER TABLE email_messages ADD COLUMN IF NOT EXISTS acknowledgement_retry_count INTEGER DEFAULT 0"
                        if is_pg else
                        "ALTER TABLE email_messages ADD COLUMN acknowledgement_retry_count INTEGER DEFAULT 0"
                    )
                    try:
                        conn.execute(text(ddl))
                        conn.commit()
                    except Exception as ddl_err:
                        err_str = str(ddl_err).lower()
                        if "already exists" in err_str or "duplicate column" in err_str:
                            logger.info("Column acknowledgement_retry_count already added by concurrent instance.")
                        else:
                            raise

                # 2. acknowledgement_last_retry_at
                if "acknowledgement_last_retry_at" not in columns:
                    logger.info("Migrating email_messages schema: adding column acknowledgement_last_retry_at")
                    col_type = "TIMESTAMP WITH TIME ZONE" if is_pg else "DATETIME"
                    ddl = (
                        f"ALTER TABLE email_messages ADD COLUMN IF NOT EXISTS acknowledgement_last_retry_at {col_type}"
                        if is_pg else
                        f"ALTER TABLE email_messages ADD COLUMN acknowledgement_last_retry_at {col_type}"
                    )
                    try:
                        conn.execute(text(ddl))
                        conn.commit()
                    except Exception as ddl_err:
                        err_str = str(ddl_err).lower()
                        if "already exists" in err_str or "duplicate column" in err_str:
                            logger.info("Column acknowledgement_last_retry_at already added by concurrent instance.")
                        else:
                            raise

                # Post-migration verification: confirm required columns are now active
                updated_inspector = inspect(migration_engine)
                columns_after = {c["name"] for c in updated_inspector.get_columns("email_messages")}
                missing = {"acknowledgement_retry_count", "acknowledgement_last_retry_at"} - columns_after
                if missing:
                    raise RuntimeError(f"Post-migration schema verification failed: missing columns {missing} in email_messages table")
        except Exception as e:
            logger.error(f"Critical database migration failure in ensure_email_message_schema: {e}")
            raise RuntimeError(f"Database migration failure: unable to verify or create email_messages schema: {e}") from e
        finally:
            if is_pg and lock_acquired:
                try:
                    res = conn.execute(text(f"SELECT pg_advisory_unlock({MIGRATION_ADVISORY_LOCK_ID})")).scalar()
                    if not res:
                        logger.error(f"pg_advisory_unlock({MIGRATION_ADVISORY_LOCK_ID}) returned False")
                        try:
                            conn.invalidate()
                        except Exception:
                            pass
                    else:
                        conn.commit()
                except Exception as unlock_err:
                    logger.error(f"Exception during pg_advisory_unlock in ensure_email_message_schema: {unlock_err}")
                    try:
                        conn.invalidate()
                    except Exception:
                        pass
            try:
                conn.close()
            except Exception:
                pass
