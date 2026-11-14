import sqlite3

conn = sqlite3.connect('backend/jansakshi.db')
c = conn.cursor()

# Map integer complaint IDs to actual complaint_id string (e.g. 19 -> JS-2026-00019, 3 -> JS-2026-00003)
c.execute("SELECT id, complaint_id FROM complaints")
mapping = {str(row[0]): row[1] for row in c.fetchall()}
print("Mapping count:", len(mapping))

c.execute("SELECT id, complaint_id FROM evidence")
evidence_rows = c.fetchall()
fixed_count = 0
for eid, cid in evidence_rows:
    if cid in mapping:
        real_cid = mapping[cid]
        c.execute("UPDATE evidence SET complaint_id = ? WHERE id = ?", (real_cid, eid))
        print(f"Fixed evidence {eid}: {cid} -> {real_cid}")
        fixed_count += 1

conn.commit()

c.execute("PRAGMA foreign_key_check")
fk_errors = c.fetchall()
print("Foreign key check violations remaining:", len(fk_errors), fk_errors)
conn.close()
