"""
JanSakshi Judge Demo Service
Provides idempotent provisioning of dedicated judge demo accounts and realistic demo seed data.
Ensures zero hardcoded passwords and strictly adheres to existing RBAC and department authorization models.
"""

import logging
import os
import secrets
import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.authority import User, Department
from app.models.complaint import Complaint, Evidence, ComplaintEvent
from app.core.security import hash_password
from app.core.config import utc_now, APP_ENV, DATABASE_URL

logger = logging.getLogger("jansakshi.judge_demo")

# Explicit production database hostnames denylist
PROD_DATABASE_HOSTS = {
    "ep-cool-snowflake-12345.us-east-2.aws.neon.tech",
    "ep-cool-123.us-east-1.aws.neon.tech",
    "ep-cool-123-pooler.us-east-1.aws.neon.tech",
    "ep-sample-pooler.us-east-1.aws.neon.tech",
}

# Approved dedicated demo database names
APPROVED_DEMO_DB_NAMES = {
    "jansakshi_demo",
    "jansakshi_judge_demo",
    "jansakshi_hackathon_demo",
}

# Approved dedicated demo database hostnames
APPROVED_DEMO_HOSTS = {
    "ep-demo-snowflake-12345.us-east-2.aws.neon.tech",
    "demo-db.neon.tech",
    "localhost",
    "127.0.0.1",
}

def _get_production_hosts() -> set:
    """
    Returns the comprehensive set of denylisted production database hostnames.
    Uses an explicit production hostname configuration and known production database identity.
    Does not automatically classify current DATABASE_URL as production merely because APP_ENV=production,
    as the dedicated demo deployment also runs with APP_ENV=production.
    """
    hosts = set(PROD_DATABASE_HOSTS)
    custom_prod_host = os.getenv("PRODUCTION_DATABASE_HOST", "").strip().lower()
    if custom_prod_host:
        hosts.add(custom_prod_host)
    custom_prod_url = os.getenv("PRODUCTION_DATABASE_URL", "").strip()
    if custom_prod_url:
        import urllib.parse
        try:
            p = urllib.parse.urlparse(custom_prod_url)
            if p.hostname:
                hosts.add(p.hostname.lower())
        except Exception:
            pass
    return hosts

def _get_approved_demo_hosts() -> set:
    """Returns the set of approved dedicated demo database hostnames."""
    hosts = set(APPROVED_DEMO_HOSTS)
    custom_demo_host = os.getenv("JANSAKSHI_DEMO_DATABASE_HOST", "").strip().lower()
    if custom_demo_host:
        hosts.add(custom_demo_host)
    return hosts

def _get_approved_demo_db_names() -> set:
    """Returns the set of approved dedicated demo database names."""
    names = set(APPROVED_DEMO_DB_NAMES)
    custom_demo_db = os.getenv("JANSAKSHI_DEMO_DATABASE_NAME", "").strip().lower()
    if custom_demo_db:
        names.add(custom_demo_db)
    return names

def _sanitize_db_descriptor(driver: str, host: Optional[str], database: Optional[str]) -> str:
    """
    Renders a sanitized, safe database descriptor without leaking usernames, passwords, or tokens.
    Never prints credentials or full connection strings.
    """
    d_driver = driver or "unknown"
    d_host = host or "local"
    d_db = database or "default"
    return f"{d_driver}://{d_host}/{d_db}"

def classify_database_target(db: Session) -> str:
    """
    Inspects the actual connection and bind details directly from the database Session.
    Does not rely only on imported environment variables.
    Classifies the database target into one of three strict categories:
    - 'PRODUCTION': The real JanSakshi production database (neondb or production host).
    - 'DEMO': An explicitly approved dedicated demo database and approved host.
    - 'UNKNOWN': Any unrecognized, external, or staging database.
    """
    bind = getattr(db, "get_bind", lambda: None)()
    if bind is None:
        return "UNKNOWN"

    url = getattr(bind, "url", None)
    if not url:
        return "UNKNOWN"

    driver = (url.drivername or "").lower()
    raw_database = (url.database or "").lower()
    host = (url.host or "").lower()

    # Clean database name (extract basename for SQLite)
    clean_db_name = os.path.basename(raw_database) if "sqlite" in driver else raw_database
    base_host = host.replace("-pooler", "")

    # 1. STRICT PRODUCTION CHECK (Never allowed under any circumstance)
    # The canonical production database for JanSakshi on Neon is 'neondb'
    # Any production host is permanently denylisted, even if DB name contains 'demo'
    prod_hosts = _get_production_hosts()
    is_prod_host = host in prod_hosts or base_host in prod_hosts
    is_prod_name = (clean_db_name == "neondb")

    if is_prod_host or is_prod_name:
        return "PRODUCTION"

    # Block if APP_ENV == "production" and target is not in approved demo allowlist
    if APP_ENV == "production" and clean_db_name != ":memory:" and clean_db_name not in _get_approved_demo_db_names():
        return "PRODUCTION"

    # 2. STRICT DEDICATED DEMO ALLOWLIST
    # In PostgreSQL:
    #   - Require BOTH explicitly approved dedicated demo database name AND exact approved database hostname.
    #   - Do NOT classify as DEMO merely because its name ends in _demo or -demo.
    if "postgresql" in driver:
        approved_hosts = _get_approved_demo_hosts()
        approved_db_names = _get_approved_demo_db_names()

        is_approved_host = (host in approved_hosts or base_host in approved_hosts)
        is_approved_db = (clean_db_name in approved_db_names)

        if is_approved_host and is_approved_db:
            return "DEMO"
        return "UNKNOWN"

    # In SQLite:
    #   - Approved local development/test targets
    if "sqlite" in driver:
        if (
            clean_db_name in {":memory:", "jansakshi.db", "jansakshi_demo.db"}
            or "demo" in clean_db_name
            or "test" in clean_db_name
            or clean_db_name.endswith("_demo.db")
        ):
            return "DEMO"
        return "UNKNOWN"

    # 3. UNKNOWN: All other database systems fail closed
    return "UNKNOWN"

def verify_safe_demo_seed_environment(db: Session, force_allow: bool = False) -> None:
    """
    Fail-closed safeguard preventing demo seeding against production and unauthorized databases.
    Rules:
    1. LIVE IDENTITY VERIFICATION: For PostgreSQL, queries SELECT current_database().
       Does not silently ignore exceptions. Fails closed if query fails, returns 'neondb',
       or differs from expected connection database.
    2. PRODUCTION: Always BLOCKED. No flag (--force-demo-seed) can EVER bypass this.
    3. UNKNOWN: Always BLOCKED. Unknown database endpoints fail closed.
    4. DEMO: Requires explicit authorization. If force_allow is False, BLOCKED.
       If force_allow is True, ALLOWED.
    """
    bind = getattr(db, "get_bind", lambda: None)()
    if bind is None:
        raise PermissionError("FAIL-CLOSED REJECTION: Database session has no active bind. Seeding rejected.")

    url = getattr(bind, "url", None)
    driver = (getattr(url, "drivername", "") or "").lower()
    raw_database = (getattr(url, "database", "") or "").lower()
    host = (getattr(url, "host", "") or "").lower()
    safe_desc = _sanitize_db_descriptor(driver, host, raw_database)

    # 1. LIVE DATABASE IDENTITY VERIFICATION (Mandatory for PostgreSQL)
    dialect = getattr(bind, "dialect", None)
    dialect_name = getattr(dialect, "name", "").lower() if dialect else ""
    if dialect_name == "postgresql" or "postgresql" in driver:
        from sqlalchemy import text
        try:
            live_db = db.execute(text("SELECT current_database()")).scalar()
        except Exception as err:
            logger.critical("LIVE DATABASE VERIFICATION FAILED on %s: %s", safe_desc, err)
            raise PermissionError(
                f"LIVE DATABASE VERIFICATION FAILED: Unable to verify live database identity via "
                f"SELECT current_database() on '{safe_desc}'. Error: {err}. Seeding rejected."
            ) from err

        if not live_db or not isinstance(live_db, str):
            logger.critical("LIVE DATABASE VERIFICATION FAILED on %s: Non-string database identifier", safe_desc)
            raise PermissionError(
                f"LIVE DATABASE VERIFICATION FAILED: Invalid database identifier returned from "
                f"SELECT current_database() on '{safe_desc}'. Seeding rejected."
            )

        live_db_name = live_db.strip().lower()

        # Reject immediately if live database is production neondb
        if live_db_name == "neondb":
            logger.critical(
                "CRITICAL SECURITY REJECTION: Live database is 'neondb' (production) on %s. Seeding blocked.",
                safe_desc
            )
            raise PermissionError(
                f"FAIL-CLOSED PRODUCTION PROTECTION: Live connected database returned '{live_db_name}', "
                f"which is the real JanSakshi production database. Demo seeding is PERMANENTLY BLOCKED. "
                f"The --force-demo-seed flag cannot bypass production protection."
            )

        # Reject if live database name differs from expected connection database
        if live_db_name != raw_database:
            logger.critical(
                "DATABASE IDENTITY MISMATCH: Live db '%s' differs from configured db '%s' on %s.",
                live_db_name, raw_database, safe_desc
            )
            raise PermissionError(
                f"DATABASE IDENTITY MISMATCH: Live connected database ('{live_db_name}') differs from "
                f"configured connection database ('{raw_database}'). Seeding rejected."
            )

    # 2. CLASSIFICATION AND STRICT ALLOWLIST
    target_class = classify_database_target(db)

    if target_class == "PRODUCTION":
        logger.critical(
            "CRITICAL SECURITY REJECTION: Seeding permanently blocked against production database (%s). "
            "--force-demo-seed cannot bypass production protection.", safe_desc
        )
        raise PermissionError(
            f"FAIL-CLOSED PRODUCTION PROTECTION: Target database '{safe_desc}' is identified as the "
            f"real JanSakshi production database. Demo seeding is PERMANENTLY BLOCKED. "
            f"The --force-demo-seed flag may only authorize seeding against dedicated demo databases."
        )

    if target_class == "UNKNOWN":
        logger.error(
            "FAIL-CLOSED REJECTION: Database '%s' is not in the approved dedicated demo allowlist.", safe_desc
        )
        raise PermissionError(
            f"FAIL-CLOSED REJECTION: Target database '{safe_desc}' is not an authorized judge demo database. "
            f"Unknown database endpoints fail closed. Seeding is strictly forbidden."
        )

    if target_class == "DEMO":
        if not force_allow:
            logger.warning(
                "Demo seeding blocked: dedicated demo database '%s' requires explicit --force-demo-seed authorization.",
                safe_desc
            )
            raise PermissionError(
                f"AUTHORIZATION REQUIRED: Target database '{safe_desc}' is an authorized demo database, "
                f"but requires explicit one-time authorization. Run seeder with: "
                f"python seed_judge_demo.py --force-demo-seed"
            )
        logger.info("Demo seeding authorized with --force-demo-seed on dedicated demo database: %s", safe_desc)

# Canonical 6 municipal departments
DEFAULT_DEPARTMENTS = [
    {"id": 1, "code": "RPW", "name": "Roads & Public Works", "sla_days": 7, "description": "Road maintenance, pothole patching, asphalt restoration, and bridge infrastructure."},
    {"id": 2, "code": "SWM", "name": "Sanitation & Waste Management", "sla_days": 3, "description": "Municipal solid waste collection, dump clearance, and sanitation hygiene."},
    {"id": 3, "code": "WSD", "name": "Water Supply & Sewerage", "sla_days": 5, "description": "Potable water distribution, pipeline leak repairs, and sewage network maintenance."},
    {"id": 4, "code": "DRN", "name": "Storm Water Drainage", "sla_days": 7, "description": "Monsoon drain clearance, culvert repairs, and flood mitigation canals."},
    {"id": 5, "code": "ESM", "name": "Electrical & Street Lighting", "sla_days": 3, "description": "Streetlight repairs, public lighting infrastructure, and electrical safety."},
    {"id": 6, "code": "PID", "name": "Public Infrastructure & Parks", "sla_days": 10, "description": "Public park maintenance, recreational equipment, and civic amenities."}
]

# Dedicated demo accounts mapped to existing canonical roles
DEMO_ACCOUNTS_SPEC = {
    "admin": {
        "username": "judge_admin",
        "email": "judge_admin@demo.jansakshi.internal",
        "full_name": "Municipal Admin (Judge Demo)",
        "role": "admin",
        "department_id": None,
        "allowed_department_ids": "1,2,3,4,5,6",
    },
    "authority_officer": {
        "username": "judge_officer",
        "email": "judge_officer@demo.jansakshi.internal",
        "full_name": "Authority Officer (Judge Demo)",
        "role": "authority_officer",
        "department_id": None,
        "allowed_department_ids": "1,2,3,4,5,6",
    },
    "department_officer": {
        "username": "judge_dept",
        "email": "judge_dept@demo.jansakshi.internal",
        "full_name": "Department Operations Lead (Judge Demo)",
        "role": "department_officer",
        "department_id": 1,
        "allowed_department_ids": "1,2,3,4,5,6",
    }
}

# Realistic dummy complaints across all 6 departments for judge evaluations
DEMO_COMPLAINTS_DATA = [
    {
        "complaint_id": "JS-DEMO-001",
        "category": "Road Damage / Potholes",
        "description": "Severe pothole cluster and crumbling asphalt on Main Market Road, causing hazardous traffic congestion.",
        "latitude": 16.5062,
        "longitude": 80.6480,
        "location_accuracy": 5.0,
        "citizen_name": "Citizen Evaluator 1",
        "citizen_email": "evaluator1@demo.jansakshi.internal",
        "status": "In Progress",
        "admin_status": "In Progress",
        "assigned_department_id": 1,
        "verification_status": "verified",
        "evidence_file": "demo_evidence_pothole_01.jpg"
    },
    {
        "complaint_id": "JS-DEMO-002",
        "category": "Road Damage / Potholes",
        "description": "Sunken road trenching section near Collectorate intersection following utility excavation.",
        "latitude": 16.5105,
        "longitude": 80.6412,
        "location_accuracy": 8.0,
        "citizen_name": "Citizen Evaluator 2",
        "citizen_email": "evaluator2@demo.jansakshi.internal",
        "status": "Received",
        "admin_status": "Pending Verification",
        "assigned_department_id": 1,
        "verification_status": "pending",
        "evidence_file": "demo_evidence_trench_02.jpg"
    },
    {
        "complaint_id": "JS-DEMO-003",
        "category": "Garbage Dump / Waste Management",
        "description": "Overflowing secondary waste bin blocking pedestrian walkway near Central Bus Terminus.",
        "latitude": 16.5140,
        "longitude": 80.6350,
        "location_accuracy": 6.0,
        "citizen_name": "Citizen Evaluator 3",
        "citizen_email": "evaluator3@demo.jansakshi.internal",
        "status": "Assigned",
        "admin_status": "Assigned",
        "assigned_department_id": 2,
        "verification_status": "verified",
        "evidence_file": "demo_evidence_garbage_03.jpg"
    },
    {
        "complaint_id": "JS-DEMO-004",
        "category": "Garbage Dump / Waste Management",
        "description": "Cleared construction debris and restored roadside cleanliness at Ward 8 bypass.",
        "latitude": 16.5180,
        "longitude": 80.6300,
        "location_accuracy": 10.0,
        "citizen_name": "Citizen Evaluator 4",
        "citizen_email": "evaluator4@demo.jansakshi.internal",
        "status": "Resolved",
        "admin_status": "Resolved",
        "assigned_department_id": 2,
        "verification_status": "verified",
        "evidence_file": "demo_evidence_debris_04.jpg"
    },
    {
        "complaint_id": "JS-DEMO-005",
        "category": "Water Supply Leakage",
        "description": "High-pressure municipal potable water pipeline rupture flooding service lane in Ward 14.",
        "latitude": 16.5020,
        "longitude": 80.6550,
        "location_accuracy": 4.0,
        "citizen_name": "Citizen Evaluator 5",
        "citizen_email": "evaluator5@demo.jansakshi.internal",
        "status": "In Progress",
        "admin_status": "In Progress",
        "assigned_department_id": 3,
        "verification_status": "verified",
        "evidence_file": "demo_evidence_pipe_burst_05.jpg"
    },
    {
        "complaint_id": "JS-DEMO-006",
        "category": "Water Supply Contamination",
        "description": "Discolored drinking water supply reported across residential colony tap connections.",
        "latitude": 16.5045,
        "longitude": 80.6520,
        "location_accuracy": 7.0,
        "citizen_name": "Citizen Evaluator 6",
        "citizen_email": "evaluator6@demo.jansakshi.internal",
        "status": "Received",
        "admin_status": "Received",
        "assigned_department_id": 3,
        "verification_status": "pending",
        "evidence_file": "demo_evidence_water_quality_06.jpg"
    },
    {
        "complaint_id": "JS-DEMO-007",
        "category": "Drainage Overflow",
        "description": "Heavy silt stagnation in open storm water drain creating health hazard near Government High School.",
        "latitude": 16.4980,
        "longitude": 80.6600,
        "location_accuracy": 5.0,
        "citizen_name": "Citizen Evaluator 7",
        "citizen_email": "evaluator7@demo.jansakshi.internal",
        "status": "In Progress",
        "admin_status": "In Progress",
        "assigned_department_id": 4,
        "verification_status": "verified",
        "evidence_file": "demo_evidence_drain_clog_07.jpg"
    },
    {
        "complaint_id": "JS-DEMO-008",
        "category": "Drainage Overflow",
        "description": "Broken culvert slab preventing storm water runoff into main drainage channel.",
        "latitude": 16.4950,
        "longitude": 80.6650,
        "location_accuracy": 9.0,
        "citizen_name": "Citizen Evaluator 8",
        "citizen_email": "evaluator8@demo.jansakshi.internal",
        "status": "Received",
        "admin_status": "Pending Verification",
        "assigned_department_id": 4,
        "verification_status": "pending",
        "evidence_file": "demo_evidence_culvert_08.jpg"
    },
    {
        "complaint_id": "JS-DEMO-009",
        "category": "Streetlight Outage",
        "description": "Series of 8 LED streetlamps non-operational along Ring Road corridor causing poor night visibility.",
        "latitude": 16.5200,
        "longitude": 80.6250,
        "location_accuracy": 12.0,
        "citizen_name": "Citizen Evaluator 9",
        "citizen_email": "evaluator9@demo.jansakshi.internal",
        "status": "In Progress",
        "admin_status": "In Progress",
        "assigned_department_id": 5,
        "verification_status": "verified",
        "evidence_file": "demo_evidence_streetlight_09.jpg"
    },
    {
        "complaint_id": "JS-DEMO-010",
        "category": "Electrical Hazard",
        "description": "Exposed low-tension live wiring at roadside electrical distribution pillar box near market crossing.",
        "latitude": 16.5230,
        "longitude": 80.6210,
        "location_accuracy": 3.0,
        "citizen_name": "Citizen Evaluator 10",
        "citizen_email": "evaluator10@demo.jansakshi.internal",
        "status": "Escalated",
        "admin_status": "Escalated",
        "assigned_department_id": 5,
        "verification_status": "verified",
        "evidence_file": "demo_evidence_electrical_hazard_10.jpg"
    },
    {
        "complaint_id": "JS-DEMO-011",
        "category": "Public Infrastructure & Parks",
        "description": "Damaged playground equipment and broken safety railing in Community Park.",
        "latitude": 16.5120,
        "longitude": 80.6450,
        "location_accuracy": 5.0,
        "citizen_name": "Citizen Evaluator 11",
        "citizen_email": "evaluator11@demo.jansakshi.internal",
        "status": "In Progress",
        "admin_status": "In Progress",
        "assigned_department_id": 6,
        "verification_status": "verified",
        "evidence_file": "demo_evidence_park_equipment_11.jpg"
    },
    {
        "complaint_id": "JS-DEMO-012",
        "category": "Public Infrastructure & Parks",
        "description": "Renovated public seating benches and landscaped pathway in Municipal Botanical Garden.",
        "latitude": 16.5150,
        "longitude": 80.6480,
        "location_accuracy": 6.0,
        "citizen_name": "Citizen Evaluator 12",
        "citizen_email": "evaluator12@demo.jansakshi.internal",
        "status": "Resolved",
        "admin_status": "Resolved",
        "assigned_department_id": 6,
        "verification_status": "verified",
        "evidence_file": "demo_evidence_park_bench_12.jpg"
    }
]

def ensure_departments(db: Session) -> None:
    """Ensures all 6 municipal departments exist in the database."""
    for dept_spec in DEFAULT_DEPARTMENTS:
        existing = db.query(Department).filter(
            (Department.id == dept_spec["id"]) | (Department.code == dept_spec["code"])
        ).first()
        if not existing:
            dept = Department(
                id=dept_spec["id"],
                code=dept_spec["code"],
                name=dept_spec["name"],
                description=dept_spec["description"],
                sla_days=dept_spec["sla_days"],
                is_active=True,
                created_at=utc_now()
            )
            db.add(dept)
        else:
            existing.code = dept_spec["code"]
            existing.name = dept_spec["name"]
            existing.description = dept_spec["description"]
            existing.sla_days = dept_spec["sla_days"]
            existing.is_active = True
    db.commit()

def get_judge_demo_account(db: Session, role: str) -> Optional[User]:
    """
    Read-only retrieval of an already-provisioned dedicated judge demo account.
    Never creates, updates, seeds, or mutates database records.
    Returns None if the account has not been provisioned.
    """
    normalized_role = role.strip().lower()
    spec = DEMO_ACCOUNTS_SPEC.get(normalized_role)
    if not spec:
        return None
    return db.query(User).filter(
        User.username == spec["username"],
        User.role == spec["role"]
    ).first()

def ensure_judge_demo_accounts(db: Session) -> Dict[str, User]:
    """
    Idempotently creates or updates the dedicated judge demo accounts for the 3 allowed roles.
    Uses cryptographically random, non-public passwords with standard bcrypt hashing.
    Used ONLY during explicit database seeding, NEVER during auth login requests.
    """
    if classify_database_target(db) == "PRODUCTION":
        raise PermissionError(
            "FAIL-CLOSED PRODUCTION PROTECTION: Provisioning judge demo accounts against "
            "the production database is strictly prohibited."
        )
    ensure_departments(db)
    demo_users: Dict[str, User] = {}

    for role_key, spec in DEMO_ACCOUNTS_SPEC.items():
        user = db.query(User).filter(User.username == spec["username"]).first()
        if not user:
            # Generate a secure cryptographically random non-public password
            random_pw = secrets.token_urlsafe(32)
            user = User(
                username=spec["username"],
                email=spec["email"],
                full_name=spec["full_name"],
                role=spec["role"],
                department_id=spec["department_id"],
                allowed_department_ids=spec["allowed_department_ids"],
                hashed_password=hash_password(random_pw),
                is_active=True,
                created_at=utc_now()
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info("Created judge demo account '%s' (role: %s)", user.username, user.role)
        else:
            # Update permissions and ensure active
            user.role = spec["role"]
            user.department_id = spec["department_id"]
            user.allowed_department_ids = spec["allowed_department_ids"]
            user.is_active = True
            db.commit()
            db.refresh(user)
        demo_users[role_key] = user

    return demo_users

def seed_judge_demo_data(db: Session, force_allow: bool = False) -> Dict[str, Any]:
    """
    Idempotent demo seed routine:
    1. Fail-closed safeguard: verifies database environment is safe for demo seeding.
    2. Ensures 6 municipal departments.
    3. Provisions dedicated judge demo accounts with random hashed passwords.
    4. Seeds realistic dummy demo complaints across departments without touching production data.
    """
    verify_safe_demo_seed_environment(db, force_allow=force_allow)
    ensure_departments(db)
    users = ensure_judge_demo_accounts(db)

    seeded_complaints = 0
    now = utc_now()

    for item in DEMO_COMPLAINTS_DATA:
        cid = item["complaint_id"]
        existing = db.query(Complaint).filter(Complaint.complaint_id == cid).first()
        if not existing:
            c = Complaint(
                complaint_id=cid,
                category=item["category"],
                description=item["description"],
                latitude=item["latitude"],
                longitude=item["longitude"],
                location_accuracy=item["location_accuracy"],
                location_source="gps",
                citizen_name=item["citizen_name"],
                citizen_email=item["citizen_email"],
                status=item["status"],
                admin_status=item["admin_status"],
                assigned_department_id=item["assigned_department_id"],
                verification_status=item["verification_status"],
                submission_channel="website",
                created_at=now,
                updated_at=now
            )
            db.add(c)
            db.flush()

            # Attach realistic dummy evidence record
            ev = Evidence(
                complaint_id=cid,
                original_filename=item["evidence_file"],
                stored_filename=f"demo_blob_{cid.lower()}.jpg",
                file_type="image/jpeg",
                file_size=1024 * 350,
                storage_path=f"/demo/evidence/{cid.lower()}.jpg",
                created_at=now
            )
            db.add(ev)

            # Audit event
            event = ComplaintEvent(
                complaint_id=cid,
                event_type="demo_seeded",
                previous_value=None,
                new_value=item["status"],
                description=f"Judge demo grievance initialized: {item['category']}",
                source="judge_demo_seeder",
                created_at=now
            )
            db.add(event)
            seeded_complaints += 1

    db.commit()
    logger.info("Judge demo seed completed: %d complaints seeded.", seeded_complaints)

    return {
        "status": "success",
        "demo_accounts": {k: u.username for k, u in users.items()},
        "seeded_complaints_count": seeded_complaints
    }
