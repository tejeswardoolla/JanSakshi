import sqlite3

conn = sqlite3.connect('backend/jansakshi.db')
c = conn.cursor()

print("--- Resolution Submissions for JS-2026-00028 ---")
for r in c.execute("SELECT id, complaint_id, version_number, status, authority_notes FROM resolution_submissions WHERE complaint_id = 'JS-2026-00028'"):
    print(r)

print("\n--- Duplicate Matches ---")
for r in c.execute("SELECT id, complaint_id, candidate_physical_issue_id, similarity_score, gps_distance_meters, review_status FROM duplicate_matches"):
    print(r)

print("\n--- Email Messages ---")
for r in c.execute("SELECT id, sender_name, sender_email, subject, processing_status FROM email_messages LIMIT 5"):
    print(r)

