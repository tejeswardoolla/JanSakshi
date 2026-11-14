import sqlite3
import json

conn = sqlite3.connect('backend/jansakshi.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

print("=== COMPLAINT JS-2026-00022 ===")
row = c.execute("SELECT * FROM complaints WHERE complaint_id = 'JS-2026-00022'").fetchone()
if row:
    for k in row.keys():
        print(f"  {k}: {row[k]}")
else:
    print("Complaint JS-2026-00022 not found!")

print("\n=== EMAIL MESSAGE for JS-2026-00022 ===")
em = c.execute("SELECT * FROM email_messages WHERE complaint_id = 'JS-2026-00022'").fetchone()
if em:
    for k in em.keys():
        if k in ('body_plain', 'body_html'):
            print(f"  {k}: {repr(str(em[k])[:150])}...")
        else:
            print(f"  {k}: {em[k]}")
else:
    print("No email_message row found for JS-2026-00022")

print("\n=== COMPLAINT EVENTS for JS-2026-00022 ===")
for ev in c.execute("SELECT * FROM complaint_events WHERE complaint_id = 'JS-2026-00022'").fetchall():
    print(f"  [{ev['created_at']}] {ev['event_type']} | {ev['previous_value']} -> {ev['new_value']} | {ev['description']}")

print("\n=== AI ANALYSES for JS-2026-00022 ===")
for ai in c.execute("SELECT * FROM ai_analyses WHERE complaint_id = 'JS-2026-00022'").fetchall():
    print(f"  Status: {ai['analysis_status']}, Category: {ai['predicted_category']}, Summary: {ai['complaint_summary']}")

print("\n=== DUPLICATE MATCHES for JS-2026-00022 ===")
for dm in c.execute("SELECT * FROM duplicate_matches WHERE complaint_id = 'JS-2026-00022'").fetchall():
    print(f"  Score: {dm['similarity_score']}, Status: {dm['review_status']}")

