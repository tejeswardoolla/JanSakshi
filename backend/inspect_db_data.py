import sqlite3

conn = sqlite3.connect('backend/jansakshi.db')
c = conn.cursor()

tables = [t[0] for t in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
print("TABLES IN DB:", tables)

for t in tables:
    cols = [col[1] for col in c.execute(f"PRAGMA table_info({t})")]
    count = c.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
    print(f"\nTable '{t}' ({count} rows):")
    print("  Columns:", cols)

print("\n--- Recent Complaints ---")
for r in c.execute("SELECT * FROM complaints ORDER BY id DESC LIMIT 5"):
    print(r)

print("\n--- Closed Complaints ---")
for r in c.execute("SELECT id, complaint_id, status, category, stage FROM complaints WHERE status = 'Closed'"):
    print(r)
