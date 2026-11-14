"""
JanSakshi Phase 7 Database Migration and Seeding Script
Safely applies schema extensions to 'complaints' table, creates 'departments' and 'users' tables,
and seeds initial departments and authority accounts without touching existing complaints.
"""

import sqlite3
import os
import sys

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.security import hash_password
from app.core.config import utc_now

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jansakshi.db")

def migrate():
    print(f"Connecting to database at: {DB_PATH}")
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    # 1. Inspect existing columns in complaints table
    existing_cols = [c[1] for c in cur.execute("PRAGMA table_info(complaints)").fetchall()]
    print(f"Existing complaints columns count: {len(existing_cols)}")

    # Columns to add to complaints
    new_cols = [
        ("verification_status", "VARCHAR(32) DEFAULT 'pending' NOT NULL"),
        ("verified_at", "DATETIME"),
        ("verified_by_user_id", "INTEGER"),
        ("verified_by_name", "VARCHAR(128)"),
        ("rejection_reason", "TEXT"),
        ("info_request_notes", "TEXT"),
        ("assigned_department_id", "INTEGER"),
        ("assigned_to_user_id", "INTEGER"),
        ("assigned_at", "DATETIME"),
        ("assignment_notes", "TEXT"),
        ("admin_status", "VARCHAR(64) DEFAULT 'Received' NOT NULL"),
        ("status_notes", "TEXT"),
        ("escalation_level", "INTEGER DEFAULT 0 NOT NULL"),
        ("escalation_reason", "TEXT"),
        ("escalated_at", "DATETIME"),
        ("escalated_to", "VARCHAR(128)"),
        ("internal_notes", "TEXT"),
    ]

    for col_name, col_type in new_cols:
        if col_name not in existing_cols:
            print(f"Adding column '{col_name}' to complaints...")
            cur.execute(f"ALTER TABLE complaints ADD COLUMN {col_name} {col_type};")

    # 2. Create departments table if not exists
    cur.execute("""
    CREATE TABLE IF NOT EXISTS departments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(128) NOT NULL UNIQUE,
        code VARCHAR(32) NOT NULL UNIQUE,
        description TEXT,
        head_name VARCHAR(128),
        contact_email VARCHAR(128),
        sla_days INTEGER DEFAULT 7 NOT NULL,
        is_active BOOLEAN DEFAULT 1 NOT NULL,
        created_at DATETIME NOT NULL
    );
    """)
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_departments_code ON departments (code);")

    # 3. Create users table if not exists
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username VARCHAR(64) NOT NULL UNIQUE,
        email VARCHAR(128) NOT NULL UNIQUE,
        hashed_password VARCHAR(255) NOT NULL,
        full_name VARCHAR(128) NOT NULL,
        role VARCHAR(32) DEFAULT 'authority_officer' NOT NULL,
        department_id INTEGER REFERENCES departments(id) ON DELETE SET NULL,
        is_active BOOLEAN DEFAULT 1 NOT NULL,
        created_at DATETIME NOT NULL,
        last_login_at DATETIME
    );
    """)
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username);")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email);")

    con.commit()

    # 4. Seed Standard Municipal Departments
    standard_depts = [
        ("Roads & Public Works", "RPW", "Potholes, asphalt road damages, damaged footpaths, flyovers, and road safety barriers", "Er. Rajesh Kumar", "roads@jansakshi.gov.in", 7),
        ("Sanitation & Waste Management", "SWM", "Garbage accumulation, community bin overflow, waste clearing, and street sweeping", "Dr. Sunita Sharma", "sanitation@jansakshi.gov.in", 3),
        ("Water Supply & Sewerage", "WSD", "Pipeline leakage, contamination, low pressure, and drinking water shortages", "Er. Manoj Varma", "water@jansakshi.gov.in", 5),
        ("Storm Water Drainage", "DRN", "Clogged drains, open drainage canals, storm water overflow, and monsoon waterlogging", "Er. P. Venkatesh", "drainage@jansakshi.gov.in", 4),
        ("Electrical & Street Lighting", "ESM", "Broken streetlights, dangling overhead cables, unlit roads, and transformer safety", "Er. K. Ramesh", "electrical@jansakshi.gov.in", 2),
        ("Public Infrastructure & Parks", "PID", "Damaged public parks, broken benches, open manholes, bus stops, and civic amenities", "Ms. Anita Desai", "infra@jansakshi.gov.in", 10),
    ]

    now_iso = utc_now().isoformat()

    for name, code, desc, head, email, sla in standard_depts:
        cur.execute("SELECT id FROM departments WHERE code = ?", (code,))
        row = cur.fetchone()
        if not row:
            print(f"Seeding department: {name} ({code})")
            cur.execute("""
                INSERT INTO departments (name, code, description, head_name, contact_email, sla_days, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?)
            """, (name, code, desc, head, email, sla, now_iso))

    con.commit()

    # Get department IDs
    dept_map = {}
    for row in cur.execute("SELECT code, id FROM departments").fetchall():
        dept_map[row[0]] = row[1]

    # 5. Seed Authority Users
    default_pw_hash = hash_password("JanSakshi@2026")

    standard_users = [
        ("admin", "admin@jansakshi.gov.in", "Municipal Administrator", "admin", None),
        ("officer", "officer@jansakshi.gov.in", "Civic Verification Officer", "authority_officer", None),
        ("roads_officer", "roads@jansakshi.gov.in", "Executive Engineer (Roads)", "department_officer", dept_map.get("RPW")),
        ("sanitation_officer", "sanitation@jansakshi.gov.in", "Sanitation Inspector", "department_officer", dept_map.get("SWM")),
        ("water_officer", "water@jansakshi.gov.in", "Water Works Engineer", "department_officer", dept_map.get("WSD")),
    ]

    for uname, email, fname, role, dept_id in standard_users:
        cur.execute("SELECT id FROM users WHERE username = ?", (uname,))
        row = cur.fetchone()
        if not row:
            print(f"Seeding user: {uname} ({role})")
            cur.execute("""
                INSERT INTO users (username, email, hashed_password, full_name, role, department_id, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?)
            """, (uname, email, default_pw_hash, fname, role, dept_id, now_iso))

    con.commit()

    # 6. Verify existing complaints
    cur.execute("SELECT count(*) FROM complaints")
    c_count = cur.fetchone()[0]
    print(f"Migration completed successfully. Total complaints in database: {c_count}")
    con.close()

if __name__ == "__main__":
    migrate()

