import sqlite3
import bcrypt

def migrate():
    conn = sqlite3.connect('backend/jansakshi.db')
    c = conn.cursor()

    # Check if allowed_department_ids column exists
    c.execute("PRAGMA table_info(users)")
    cols = [r[1] for r in c.fetchall()]
    if 'allowed_department_ids' not in cols:
        c.execute("ALTER TABLE users ADD COLUMN allowed_department_ids VARCHAR(128)")
        print("Added allowed_department_ids column")
    else:
        print("allowed_department_ids column already exists")

    # Check or insert dept_demo user
    c.execute("SELECT id FROM users WHERE username = 'dept_demo'")
    row = c.fetchone()
    hashed = bcrypt.hashpw('JanSakshi@2026'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    if not row:
        c.execute("""
            INSERT INTO users (username, email, hashed_password, full_name, role, department_id, allowed_department_ids, is_active, created_at)
            VALUES ('dept_demo', 'dept_demo@jansakshi.gov.in', ?, 'Department Operations Lead (Demo)', 'department_officer', 1, '1,2,3,4,5,6', 1, datetime('now'))
        """, (hashed,))
        print("Created dept_demo user with access to 1,2,3,4,5,6")
    else:
        c.execute("UPDATE users SET allowed_department_ids = '1,2,3,4,5,6', role = 'department_officer' WHERE username = 'dept_demo'")
        print("Updated dept_demo user with access to 1,2,3,4,5,6")

    # Ensure roads_officer is restricted to 1
    c.execute("UPDATE users SET allowed_department_ids = '1' WHERE username = 'roads_officer'")

    # Assign sample grievances to other departments for demo completeness
    # SWM (2): JS-2026-00002, JS-2026-00006
    c.execute("UPDATE complaints SET assigned_department_id = 2, verification_status = 'verified', admin_status = 'In Progress' WHERE complaint_id = 'JS-2026-00002'")
    c.execute("UPDATE complaints SET assigned_department_id = 2, verification_status = 'verified', admin_status = 'Assigned' WHERE complaint_id = 'JS-2026-00006'")

    # WSD (3): JS-2026-00003
    c.execute("UPDATE complaints SET assigned_department_id = 3, verification_status = 'verified', admin_status = 'In Progress' WHERE complaint_id = 'JS-2026-00003'")

    # DRN (4): JS-2026-00005
    c.execute("UPDATE complaints SET assigned_department_id = 4, verification_status = 'verified', admin_status = 'In Progress' WHERE complaint_id = 'JS-2026-00005'")

    # ESM (5): JS-2026-00007, JS-2026-00008
    c.execute("UPDATE complaints SET assigned_department_id = 5, verification_status = 'verified', admin_status = 'In Progress' WHERE complaint_id = 'JS-2026-00007'")
    c.execute("UPDATE complaints SET assigned_department_id = 5, verification_status = 'verified', admin_status = 'Resolved' WHERE complaint_id = 'JS-2026-00008'")

    # PID (6): JS-2026-00011
    c.execute("UPDATE complaints SET assigned_department_id = 6, category = 'Public Infrastructure & Parks', verification_status = 'verified', admin_status = 'In Progress' WHERE complaint_id = 'JS-2026-00011'")

    conn.commit()
    print("Migration complete. Current users and department allocations:")
    c.execute('SELECT id, username, role, department_id, allowed_department_ids FROM users')
    print(c.fetchall())
    c.execute('SELECT assigned_department_id, count(*) FROM complaints GROUP BY assigned_department_id')
    print(c.fetchall())
    conn.close()

if __name__ == '__main__':
    migrate()
