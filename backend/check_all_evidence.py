import sqlite3
conn = sqlite3.connect('backend/jansakshi.db')
c = conn.cursor()
c.execute("SELECT id, complaint_id, stored_filename FROM evidence")
for r in c.fetchall():
    print(r)
conn.close()
