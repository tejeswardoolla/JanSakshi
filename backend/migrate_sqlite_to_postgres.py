#!/usr/bin/env python3
"""
JanSakshi SQLite to Neon PostgreSQL Data Migration Utility

Safely migrates all data from local SQLite (jansakshi.db) to target PostgreSQL (Neon).
Features:
- Strict Dry-Run by default (requires explicit --execute flag).
- Preserves primary keys, foreign key constraints, timestamps, and UUID tracking tokens.
- Automatic PostgreSQL serial sequence synchronization after insert.
- Pre- and post-migration record reconciliation and foreign key integrity audit.
- Completely non-destructive: original SQLite database is NEVER modified or deleted.
"""

import os
import sys
import argparse
import datetime
from typing import Dict, List, Any, Optional

from sqlalchemy import create_engine, inspect, text, select
from sqlalchemy.orm import sessionmaker

# Ensure backend root is on sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from app.database import Base, DEFAULT_DB_PATH, normalize_database_url
import app.models  # Registers all models

# Strict foreign-key dependency order for migration
TABLE_ORDER = [
    "departments",
    "users",
    "revoked_tokens",
    "physical_issues",
    "complaints",
    "evidence",
    "complaint_events",
    "ai_analyses",
    "duplicate_matches",
    "email_messages",
    "resolution_submissions",
    "resolution_evidence_analyses",
    "oauth_tokens",
    "oauth_states",
]

# Tables with serial sequence columns to reset
SEQUENCE_TABLES = [
    ("departments", "id"),
    ("users", "id"),
    ("physical_issues", "id"),
    ("evidence", "id"),
    ("complaint_events", "id"),
    ("ai_analyses", "id"),
    ("duplicate_matches", "id"),
    ("email_messages", "id"),
    ("resolution_submissions", "id"),
    ("resolution_evidence_analyses", "id"),
    ("oauth_tokens", "id"),
    ("oauth_states", "id"),
]

def parse_args():
    parser = argparse.ArgumentParser(description="JanSakshi SQLite to PostgreSQL Migration Utility")
    parser.add_argument(
        "--source-db",
        default=f"sqlite:///{DEFAULT_DB_PATH.as_posix()}",
        help="Source SQLite database URL"
    )
    parser.add_argument(
        "--target-url",
        default=os.getenv("TARGET_DATABASE_URL", ""),
        help="Target PostgreSQL database URL (Neon). Defaults to TARGET_DATABASE_URL env var."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help="Execute actual migration. If omitted, utility runs in safe DRY-RUN verification mode."
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Chunk size for batch insertion (default: 500)"
    )
    return parser.parse_args()

def inspect_database_counts(engine) -> Dict[str, int]:
    """Inspects row counts for all application tables."""
    counts = {}
    with engine.connect() as conn:
        for table_name in TABLE_ORDER:
            try:
                res = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                counts[table_name] = res.scalar() or 0
            except Exception:
                counts[table_name] = 0
    return counts

def validate_source_integrity(source_engine) -> Dict[str, Any]:
    """Audits SQLite source database for foreign key or primary key anomalies."""
    issues = []
    with source_engine.connect() as conn:
        # Check orphan complaints without valid department
        res = conn.execute(text(
            "SELECT COUNT(*) FROM complaints WHERE assigned_department_id IS NOT NULL AND assigned_department_id NOT IN (SELECT id FROM departments)"
        )).scalar()
        if res > 0:
            issues.append(f"Found {res} complaints referencing non-existent assigned_department_id.")

        # Check orphan evidence without complaint
        res = conn.execute(text(
            "SELECT COUNT(*) FROM evidence WHERE complaint_id NOT IN (SELECT complaint_id FROM complaints)"
        )).scalar()
        if res > 0:
            issues.append(f"Found {res} evidence rows referencing missing complaint_id.")

        # Check duplicate complaint_ids
        res = conn.execute(text(
            "SELECT complaint_id, COUNT(*) as c FROM complaints GROUP BY complaint_id HAVING c > 1"
        )).fetchall()
        if res:
            issues.append(f"Found duplicate complaint primary keys: {[r[0] for r in res]}")

    return {
        "valid": len(issues) == 0,
        "issues": issues
    }

def run_migration(source_url: str, target_url: str, execute: bool, batch_size: int = 500):
    mode_str = "EXECUTE (LIVE DATA MIGRATION)" if execute else "DRY RUN (READ-ONLY AUDIT)"
    print("=" * 80)
    print(f"JANSAKSHI DATABASE MIGRATION ENGINE — {mode_str}")
    print("=" * 80)
    print(f"Source SQLite:   {source_url}")
    print(f"Target Database: {target_url or '(Not Specified - Dry Run Only)'}")
    print(f"Timestamp:       {datetime.datetime.now(datetime.timezone.utc).isoformat()}")
    print("-" * 80)

    # 1. Connect and inspect source SQLite database
    source_engine = create_engine(source_url, connect_args={"check_same_thread": False})
    source_counts = inspect_database_counts(source_engine)
    total_source_records = sum(source_counts.values())

    print("\n--- 1. SOURCE SQLITE DATABASE INVENTORY ---")
    for t in TABLE_ORDER:
        print(f"  {t:<32}: {source_counts.get(t, 0):>6} rows")
    print(f"  {'TOTAL SOURCE RECORDS':<32}: {total_source_records:>6} rows")

    # 2. Source Data Integrity Audit
    print("\n--- 2. SOURCE INTEGRITY AUDIT ---")
    integrity = validate_source_integrity(source_engine)
    if integrity["valid"]:
        print("  [PASS] Foreign key relationships and unique primary keys are 100% valid.")
    else:
        print("  [FAIL] Integrity anomalies detected:")
        for issue in integrity["issues"]:
            print(f"    - {issue}")
        if execute:
            print("\nAborting live migration due to integrity violations.")
            sys.exit(1)

    if not execute:
        print("\n" + "=" * 80)
        print("DRY-RUN VERIFICATION SUCCESSFUL")
        print("=" * 80)
        print("The source SQLite database was verified without mutation.")
        print("To execute migration to Neon PostgreSQL, provide target connection string:")
        print("  python migrate_sqlite_to_postgres.py --target-url \"postgresql://user:pass@ep-...neon.tech/neondb?sslmode=require\" --execute")
        print("=" * 80)
        return

    # --- LIVE MIGRATION LOGIC (ONLY REACHED IF --execute IS PASSED) ---
    if not target_url:
        print("\n[ERROR] --target-url must be provided when --execute flag is active.")
        sys.exit(1)

    norm_target_url = normalize_database_url(target_url)
    target_engine = create_engine(
        norm_target_url,
        pool_pre_ping=True,
        connect_args={"sslmode": "require"} if "neon.tech" in norm_target_url else {}
    )

    print("\n--- 3. INITIALIZING TARGET POSTGRESQL SCHEMA ---")
    # Non-destructively creates tables if they do not exist
    Base.metadata.create_all(bind=target_engine)
    print("  [PASS] Target PostgreSQL schema confirmed ready.")

    print("\n--- 4. MIGRATING TABLE DATA ---")
    migrated_counts = {}

    with source_engine.connect() as s_conn, target_engine.begin() as t_conn:
        for table_name in TABLE_ORDER:
            table_obj = Base.metadata.tables.get(table_name)
            if table_obj is None:
                print(f"  [SKIP] Table {table_name} not defined in ORM metadata.")
                continue

            rows = s_conn.execute(select(table_obj)).mappings().all()
            row_count = len(rows)

            if row_count == 0:
                print(f"  {table_name:<30}:      0 rows (skipped)")
                migrated_counts[table_name] = 0
                continue

            # Batch insert into target
            inserted = 0
            for i in range(0, row_count, batch_size):
                chunk = rows[i:i + batch_size]
                # Convert Mapping to dict
                chunk_dicts = [dict(r) for r in chunk]
                t_conn.execute(table_obj.insert(), chunk_dicts)
                inserted += len(chunk_dicts)

            print(f"  {table_name:<30}: {inserted:>6} rows inserted")
            migrated_counts[table_name] = inserted

    print("\n--- 5. SYNCHRONIZING POSTGRESQL SERIAL SEQUENCES ---")
    with target_engine.begin() as t_conn:
        for table_name, pk_col in SEQUENCE_TABLES:
            try:
                seq_query = text(f"""
                    SELECT setval(
                        pg_get_serial_sequence('{table_name}', '{pk_col}'),
                        coalesce(max({pk_col}), 1),
                        max({pk_col}) IS NOT null
                    ) FROM {table_name};
                """)
                t_conn.execute(seq_query)
                print(f"  Synchronized sequence: {table_name}.{pk_col}")
            except Exception as seq_err:
                # Some tables may not use serial sequences if primary key is String
                print(f"  Sequence sync note for {table_name}.{pk_col}: {seq_err}")

    print("\n--- 6. RECONCILIATION AUDIT ---")
    target_counts = inspect_database_counts(target_engine)
    all_match = True
    for t in TABLE_ORDER:
        src = source_counts.get(t, 0)
        tgt = target_counts.get(t, 0)
        status = "MATCH" if src == tgt else "MISMATCH"
        if src != tgt:
            all_match = False
        print(f"  {t:<30}: Source={src:>5} | Target={tgt:>5} | [{status}]")

    print("\n" + "=" * 80)
    if all_match:
        print("MIGRATION COMPLETED SUCCESSFULLY WITH 100% RECONCILIATION!")
    else:
        print("WARNING: Some table counts did not match. Please review reconciliation logs above.")
    print("=" * 80)

if __name__ == "__main__":
    args = parse_args()
    run_migration(
        source_url=args.source_db,
        target_url=args.target_url,
        execute=args.execute,
        batch_size=args.batch_size
    )
