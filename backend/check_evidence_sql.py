import sqlite3
conn = sqlite3.connect('backend/jansakshi.db')
c = conn.cursor()
c.execute("SELECT sql FROM sqlite_master WHERE name = 'evidence'")
print(c.fetchone()[0])
conn.close()
