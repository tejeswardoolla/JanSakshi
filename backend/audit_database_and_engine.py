import os
import sqlite3
import json

def audit_db():
    db_path = "jansakshi.db"
    if not os.path.exists(db_path):
        print("Database not found!")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Foreign Key Check
    cursor.execute("PRAGMA foreign_key_check")
    fk_violations = cursor.fetchall()
    print("=== DATABASE INTEGRITY ===")
    print(f"Foreign Key Violations: {len(fk_violations)}")
    if fk_violations:
        for v in fk_violations:
            print("  Violation:", v)

    # 2. SQLite Integrity Check
    cursor.execute("PRAGMA integrity_check")
    integrity = cursor.fetchall()
    print("SQLite Integrity:", integrity)

    # 3. Table counts
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    print("\n=== TABLE COUNTS ===")
    for t in sorted(tables):
        if t != "sqlite_sequence":
            cursor.execute(f"SELECT count(*) FROM {t}")
            cnt = cursor.fetchone()[0]
            print(f"  {t}: {cnt}")

    # 4. Check Table Schemas
    print("\n=== COMPLAINTS COLUMNS ===")
    cursor.execute("PRAGMA table_info(complaints)")
    cols = [r[1] for r in cursor.fetchall()]
    print("Columns in complaints:", cols)

    # 4b. Query actual complaints
    cursor.execute(f"SELECT complaint_id, category, status, admin_status, verification_status, latitude, longitude, tracking_token FROM complaints")
    rows = cursor.fetchall()
    print(f"Total Complaints: {len(rows)}")
    null_coords = [r[0] for r in rows if r[5] is None or r[6] is None]
    print(f"Complaints without GPS: {len(null_coords)} -> {null_coords}")
    
    status_dist = {}
    admin_status_dist = {}
    for r in rows:
        cid, cat, st, ast, vst, lat, lng, tok = r
        status_dist[st] = status_dist.get(st, 0) + 1
        admin_status_dist[ast] = admin_status_dist.get(ast, 0) + 1
    
    print("Public Status distribution:", status_dist)
    print("Admin Status distribution:", admin_status_dist)

    # 5. Check Non-Civic Record JS-2026-00022
    print("\n=== NON-CIVIC RECORD JS-2026-00022 ===")
    cursor.execute("SELECT complaint_id, category, status, admin_status, verification_status, rejection_reason, description FROM complaints WHERE complaint_id='JS-2026-00022'")
    rec = cursor.fetchone()
    if rec:
        print(f"ID: {rec[0]}")
        print(f"Category: {rec[1]}")
        print(f"Public Status: {rec[2]}")
        print(f"Admin Status: {rec[3]}")
        print(f"Verification Status: {rec[4]}")
        print(f"Rejection Reason: {rec[5]}")
        print(f"Description snippet: {rec[6][:100]}...")
    else:
        print("JS-2026-00022 NOT FOUND!")

    # Check audit events for JS-2026-00022
    cursor.execute("SELECT event_type, previous_value, new_value, source, description, created_at FROM complaint_events WHERE complaint_id='JS-2026-00022' ORDER BY created_at ASC")
    events = cursor.fetchall()
    print(f"Audit events for JS-2026-00022: {len(events)}")
    for e in events:
        print(f"  {e[5]} | {e[0]} | {e[3]} | {e[4]}")

    # 6. Evidence Table Check
    print("\n=== EVIDENCE AUDIT ===")
    cursor.execute("SELECT id, complaint_id, file_type, storage_path, original_filename, file_size FROM evidence")
    ev_rows = cursor.fetchall()
    print(f"Total Evidence Records: {len(ev_rows)}")
    orphaned_evidence = []
    missing_files = []
    for ev in ev_rows:
        eid, cid, ftype, fpath, fname, fsize = ev
        cursor.execute("SELECT id FROM complaints WHERE complaint_id=?", (cid,))
        if not cursor.fetchone():
            orphaned_evidence.append((eid, cid))
        if fpath and not os.path.exists(fpath):
            missing_files.append((eid, fpath))
    print(f"Orphaned Evidence Records (invalid complaint_id): {len(orphaned_evidence)}")
    print(f"Missing Files on Disk: {len(missing_files)}")

    # 7. Resolution Submissions Check
    print("\n=== RESOLUTION SUBMISSIONS AUDIT ===")
    cursor.execute("SELECT id, complaint_id, version_number, status, submitted_by_user_id, reviewed_by_user_id, authority_notes FROM resolution_submissions")
    res_rows = cursor.fetchall()
    print(f"Total Resolution Submissions: {len(res_rows)}")
    for rs in res_rows:
        print(f"  Sub ID {rs[0]} | CID: {rs[1]} | v{rs[2]} | Status: {rs[3]} | SubUser: {rs[4]} | RevUser: {rs[5]} | Notes: {rs[6]}")

    # 8. Physical Issues Check
    print("\n=== PHYSICAL ISSUES AUDIT ===")
    cursor.execute("SELECT issue_reference_id, category, representative_location, current_status FROM physical_issues")
    issues = cursor.fetchall()
    print(f"Total Physical Issues: {len(issues)}")
    for iss in issues:
        cursor.execute("SELECT count(*) FROM complaints WHERE issue_id=?", (iss[0],))
        c_count = cursor.fetchone()[0]
        print(f"  {iss[0]} | {iss[1]} | {iss[2]} | Status: {iss[3]} | Linked Complaints: {c_count}")

    # 9. Departments Check
    print("\n=== DEPARTMENTS AUDIT ===")
    cursor.execute("SELECT id, code, name, sla_days FROM departments")
    depts = cursor.fetchall()
    for d in depts:
        cursor.execute("SELECT count(*) FROM users WHERE department_id=?", (d[0],))
        ucnt = cursor.fetchone()[0]
        cursor.execute("SELECT count(*) FROM complaints WHERE assigned_department_id=?", (d[0],))
        ccnt = cursor.fetchone()[0]
        print(f"  Dept {d[0]} | Code: {d[1]} | Name: {d[2]} | SLA: {d[3]}d | Users: {ucnt} | Complaints: {ccnt}")

    # 10. Users Check
    print("\n=== USERS AUDIT ===")
    cursor.execute("SELECT id, username, email, full_name, role, department_id, is_active FROM users")
    users = cursor.fetchall()
    for u in users:
        print(f"  User {u[0]} | {u[1]} ({u[3]}) | Role: {u[4]} | Dept: {u[5]} | Active: {u[6]}")

    conn.close()

    # 11. Integrations Status Check
    print("\n=== EXTERNAL INTEGRATIONS STATUS ===")
    import app.core.config as cfg
    has_gemini = bool(cfg.GEMINI_API_KEY)
    gemini_model = cfg.GEMINI_MODEL
    has_gmail_id = bool(cfg.GMAIL_CLIENT_ID)
    cred_file = cfg.GMAIL_CREDENTIALS_FILE
    cred_exists = os.path.exists(cred_file) if cred_file else False
    token_file = cfg.GMAIL_TOKEN_PATH
    token_exists = os.path.exists(token_file) if token_file else False
    print(f"Gemini API Key configured: {has_gemini}")
    print(f"Gemini Model: {gemini_model}")
    print(f"Gemini AI Analysis Enabled: {cfg.AI_ANALYSIS_ENABLED}")
    print(f"Gmail Enabled: {cfg.GMAIL_ENABLED}")
    print(f"Gmail Inbox Address: {cfg.GMAIL_INBOX_ADDRESS}")
    print(f"Gmail Client ID configured: {has_gmail_id}")
    print(f"Gmail Credentials file: {cred_file} (exists: {cred_exists})")
    print(f"Gmail Token file: {token_file} (exists: {token_exists})")

if __name__ == "__main__":
    audit_db()
