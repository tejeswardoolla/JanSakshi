import datetime
import logging
import threading
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.complaint import PhysicalIssue

logger = logging.getLogger("jansakshi.issue_id")

# Process-level re-entrant mutex to serialize sequence generation and insertion across threads (SQLite & worker threads)
_issue_id_seq_mutex = threading.RLock()

def get_verified_database_dialect(db: Session) -> str:
    """
    Explicitly identifies the database dialect ('postgresql' or 'sqlite').
    If dialect identification fails entirely, raises RuntimeError to prevent silently skipping distributed locking.
    """
    bind = None
    try:
        bind = db.get_bind() if hasattr(db, "get_bind") else getattr(db, "bind", None)
    except Exception:
        pass

    dialect_name = (getattr(bind, "dialect", None).name or "").lower() if bind else ""
    if dialect_name in ("postgresql", "sqlite"):
        return dialect_name

    # Fallback to database configuration
    try:
        from app.database import is_postgres, is_sqlite
        if is_postgres:
            return "postgresql"
        if is_sqlite:
            return "sqlite"
    except Exception:
        pass

    raise RuntimeError(
        "CRITICAL DATABASE ERROR: Unable to verify database dialect for concurrency locking. "
        "Failing closed to prevent uncoordinated database operations."
    )

def is_issue_reference_id_collision(err: IntegrityError) -> bool:
    """
    Positively identifies whether an IntegrityError was caused specifically by a
    unique constraint collision on physical_issues.issue_reference_id.

    Inspects:
    1. PostgreSQL driver diagnostics (table_name, column_name, constraint_name, message_detail).
       Requires table_name == 'physical_issues' when checking column diagnostics.
    2. SQLite exact column failure ('physical_issues.issue_reference_id').
    3. Strict SQL error diagnostic substrings that uniquely identify physical_issues.issue_reference_id.

    Returns False for any unrelated, ambiguous, or other unique constraint failures.
    """
    if not isinstance(err, IntegrityError):
        return False

    orig = getattr(err, "orig", None)

    # 1. PostgreSQL driver diagnostic inspection (psycopg / psycopg2)
    diag = getattr(orig, "diag", None)
    if diag is not None:
        table = (getattr(diag, "table_name", None) or "").lower()
        constraint = (getattr(diag, "constraint_name", None) or "").lower()
        column = (getattr(diag, "column_name", None) or "").lower()
        message_detail = (getattr(diag, "message_detail", None) or "").lower()

        # If table_name is populated and points to another table, reject immediately
        if table and table != "physical_issues":
            return False

        # Positive condition A: Exact constraint belonging to physical_issues.issue_reference_id
        is_known_constraint = (
            constraint in (
                "physical_issues_issue_reference_id_key",
                "ix_physical_issues_issue_reference_id",
                "uq_physical_issues_issue_reference_id",
            )
            or (constraint.startswith("physical_issues_") and "issue_reference_id" in constraint)
        )
        if is_known_constraint and (not table or table == "physical_issues"):
            return True

        # Positive condition B: BOTH table_name == "physical_issues" AND column_name == "issue_reference_id"
        if table == "physical_issues" and column == "issue_reference_id":
            return True

        # Positive condition C: table_name == "physical_issues" and detail specifies key (issue_reference_id)
        if table == "physical_issues" and "key (issue_reference_id)=" in message_detail:
            return True

        # If diag exists and did not positively match physical_issues.issue_reference_id, reject
        return False

    # 2. SQLite and strict error message text matching
    err_str = str(err).lower()

    # SQLite exact failed column: must explicitly identify physical_issues.issue_reference_id
    if "unique constraint failed: physical_issues.issue_reference_id" in err_str:
        return True

    # PostgreSQL error text fallback: must strictly reference physical_issues AND issue_reference_id
    if "physical_issues_issue_reference_id_key" in err_str:
        return True
    if "ix_physical_issues_issue_reference_id" in err_str and "physical_issues" in err_str:
        return True
    if "physical_issues" in err_str and "key (issue_reference_id)=" in err_str:
        return True

    return False

def acquire_postgres_issue_seq_lock(db: Session, year: int) -> None:
    """
    Acquires a transaction-scoped PostgreSQL advisory lock for the yearly PhysicalIssue ID sequence.
    Held until transaction commit or rollback. Fails closed if acquisition fails.
    """
    dialect = get_verified_database_dialect(db)
    if dialect == "postgresql":
        lock_key = f"jansakshi_seq_physical_issue_{year}"
        try:
            db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": lock_key})
        except Exception as err:
            logger.error(f"PostgreSQL advisory lock acquisition failed for PhysicalIssue sequence ({year}): {err}")
            db.rollback()
            raise RuntimeError(
                f"PostgreSQL advisory lock acquisition failed for PhysicalIssue sequence ({year}): {err}"
            ) from err
    elif dialect == "sqlite":
        # SQLite uses application-level process re-entrant mutex (_issue_id_seq_mutex)
        # and file-level locking for concurrency protection.
        return

def generate_issue_reference_id(db: Session) -> str:
    """
    Generate unique human-readable issue ID: ISSUE-YYYY-XXXXX
    e.g. ISSUE-2026-00001

    Guarantees atomic allocation across independent PostgreSQL workers and locations
    via transaction-scoped advisory locking (pg_advisory_xact_lock) and re-entrant thread mutex.
    """
    year = datetime.datetime.now(datetime.timezone.utc).year
    prefix = f"ISSUE-{year}-"

    # Acquire PostgreSQL transaction-scoped advisory lock for the yearly sequence (fails closed)
    acquire_postgres_issue_seq_lock(db, year)

    with _issue_id_seq_mutex:
        latest = (
            db.query(PhysicalIssue.issue_reference_id)
            .filter(PhysicalIssue.issue_reference_id.like(f"{prefix}%"))
            .order_by(PhysicalIssue.id.desc())
            .first()
        )

        if latest and latest[0]:
            try:
                current_num_str = latest[0].split("-")[-1]
                next_num = int(current_num_str) + 1
            except (ValueError, IndexError):
                next_num = 1
        else:
            next_num = 1

        return f"{prefix}{next_num:05d}"
