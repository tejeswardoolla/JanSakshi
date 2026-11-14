import os
import sqlite3
from playwright.sync_api import sync_playwright

DB_PATH = r"backend\jansakshi.db"
OUTPUT_PNG = os.path.abspath(r"screenshots\11_er_diagram.png")
EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

tables = [t[0] for t in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]

schema_info = {}
mermaid_lines = ["erDiagram"]

for t in sorted(tables):
    cols = c.execute(f"PRAGMA table_info({t})").fetchall()
    fks = c.execute(f"PRAGMA foreign_key_list({t})").fetchall()
    # cols format: (cid, name, type, notnull, dflt_value, pk)
    # fks format: (id, seq, table, from, to, on_update, on_delete, match)
    
    schema_info[t] = {
        "columns": [(col[1], col[2] or "TEXT", bool(col[5])) for col in cols],
        "fks": [(fk[3], fk[2], fk[4]) for fk in fks]
    }

print("=== DATABASE TABLES & COLUMNS ===")
for t, data in schema_info.items():
    print(f"\nTABLE: {t}")
    for col, ctype, is_pk in data["columns"]:
        pk_str = " [PRIMARY KEY]" if is_pk else ""
        print(f"  - {col}: {ctype}{pk_str}")
    for from_col, to_table, to_col in data["fks"]:
        print(f"  * FK: {from_col} -> {to_table}({to_col})")

# Build relationships
relationships = set()
for t, data in schema_info.items():
    for from_col, to_table, to_col in data["fks"]:
        if to_table in schema_info:
            rel = f'    {to_table.upper()} ||--o{{ {t.upper()} : "references"'
            relationships.add(rel)

# Add hardcoded business domain FKs if implicit in schema
# e.g., complaints.assigned_department_id -> departments.id
relationships.add('    DEPARTMENTS ||--o{ USERS : "belongs_to"')
relationships.add('    DEPARTMENTS ||--o{ COMPLAINTS : "assigned_to"')
relationships.add('    COMPLAINTS ||--o{ EVIDENCE : "has_evidence"')
relationships.add('    COMPLAINTS ||--o{ COMPLAINT_EVENTS : "tracks_events"')
relationships.add('    COMPLAINTS ||--o{ RESOLUTION_SUBMISSIONS : "resolves"')
relationships.add('    RESOLUTION_SUBMISSIONS ||--o{ RESOLUTION_EVIDENCE_ANALYSES : "evaluated_by"')
relationships.add('    COMPLAINTS ||--o{ AI_ANALYSES : "analyzed_by"')
relationships.add('    PHYSICAL_ISSUES ||--o{ DUPLICATE_MATCHES : "clustered_in"')
relationships.add('    COMPLAINTS ||--o{ DUPLICATE_MATCHES : "matched_as"')

mermaid_lines.extend(sorted(list(relationships)))

# Add table definitions
for t, data in schema_info.items():
    mermaid_lines.append(f"    {t.upper()} {{")
    for col, ctype, is_pk in data["columns"]:
        clean_type = ctype.replace(" ", "_").replace("(", "_").replace(")", "")
        pk_tag = " PK" if is_pk else ""
        mermaid_lines.append(f"        {clean_type} {col}{pk_tag}")
    mermaid_lines.append("    }")

mermaid_text = "\n".join(mermaid_lines)
with open("screenshots/er_diagram.mermaid", "w") as f:
    f.write(mermaid_text)

print("\nMermaid diagram saved to screenshots/er_diagram.mermaid")

# Create standalone HTML to render Mermaid with dark modern styling
html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
    <style>
        body {{
            background-color: #0E1017;
            color: #FFFFFF;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 40px;
            margin: 0;
        }}
        h1 {{
            color: #F36B21;
            font-size: 24px;
            margin-bottom: 20px;
            font-weight: 800;
            letter-spacing: -0.5px;
        }}
        .mermaid {{
            background: #141722;
            padding: 30px;
            border-radius: 20px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0 20px 40px rgba(0,0,0,0.5);
            max-width: 1360px;
            overflow: auto;
        }}
    </style>
</head>
<body>
    <h1>JanSakshi — Relational Database Entity-Relationship (ER) Topology</h1>
    <div class="mermaid">
{mermaid_text}
    </div>
    <script>
        mermaid.initialize({{
            startOnLoad: true,
            theme: 'dark',
            themeVariables: {{
                primaryColor: '#1A1F2C',
                primaryTextColor: '#FFFFFF',
                primaryBorderColor: '#F36B21',
                lineColor: '#F36B21',
                secondaryColor: '#10131C',
                tertiaryColor: '#0E1017'
            }}
        }});
    </script>
</body>
</html>
"""

html_path = os.path.abspath(r"screenshots\er_diagram.html")
with open(html_path, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"HTML diagram saved to {html_path}")

# Render to PNG using Playwright
print("Rendering screenshots/11_er_diagram.png...")
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=EDGE_PATH, headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 950})
    page.goto(f"file:///{html_path.replace(os.sep, '/')}", wait_until="networkidle")
    page.wait_for_selector(".mermaid svg", timeout=10000)
    page.screenshot(path=OUTPUT_PNG, full_page=True)
    browser.close()

print(f"SUCCESS: Rendered {OUTPUT_PNG} ({os.path.getsize(OUTPUT_PNG)} bytes)")

