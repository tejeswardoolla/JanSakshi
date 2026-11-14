import docx
import os

doc_path = r"C:\Users\TEJESWAR\Desktop\JanSakshi\JanSakshi_CodeForge_BuildX_2026_Project_Report.docx"
print("Validating:", doc_path)
print("File exists:", os.path.exists(doc_path))
print("File size:", os.path.getsize(doc_path), "bytes")

doc = docx.Document(doc_path)
print(f"Total sections: {len(doc.sections)}")
sec = doc.sections[0]
print(f"Page width: {sec.page_width.inches} in, height: {sec.page_height.inches} in")
print(f"Margins: Left={sec.left_margin.inches} in, Right={sec.right_margin.inches} in, Top={sec.top_margin.inches} in, Bottom={sec.bottom_margin.inches} in")

print(f"Total paragraphs: {len(doc.paragraphs)}")
print(f"Total tables: {len(doc.tables)}")

# Check for forbidden sample keywords
forbidden = ["Campus Helpdesk", "Sample Student", "ROLL001", "ROLL002", "[Mentor Name]", "Flask REST API", "Student A", "Student B"]
found_forbidden = []
for i, p in enumerate(doc.paragraphs):
    for f in forbidden:
        if f.lower() in p.text.lower():
            found_forbidden.append((i, f, p.text[:50]))

for t_idx, table in enumerate(doc.tables):
    for r_idx, row in enumerate(table.rows):
        for c_idx, cell in enumerate(row.cells):
            for f in forbidden:
                if f.lower() in cell.text.lower():
                    found_forbidden.append((f"T{t_idx}R{r_idx}C{c_idx}", f, cell.text[:50]))

print("Leftover sample text occurrences:", len(found_forbidden))
if found_forbidden:
    for occ in found_forbidden:
        print("  Found:", occ)

# Verify Cover Page
print("\n=== COVER PAGE VERIFICATION ===")
for i in [0, 1, 2, 4, 5, 8, 11, 12, 13]:
    print(f"P{i:02d}: {doc.paragraphs[i].text.strip()[:80]}")

# Verify Team Members
print("\n=== TEAM MEMBERS CHECK ===")
team_names = [
    "DOOLLA TEJESWARA DURGA LAXMI NARASIMHA", "25B11AIB79",
    "Kuruthalla Joel Jason", "25B11CS504",
    "Korumilli Harsha Vardhan", "25B11AI578",
    "Syed Saif Hussain", "25B11AIB59",
    "KAPPARATI LOKESH SATYA SAI BABU", "25B11AI495",
    "Ashok"
]
all_text = " ".join([p.text for p in doc.paragraphs])
for t in doc.tables:
    for r in t.rows:
        for c in r.cells:
            all_text += " " + c.text

for name in team_names:
    print(f"  {name} present: {name in all_text}")

# Check Section Headings
print("\n=== SECTION HEADINGS CHECK ===")
headings = [p.text for p in doc.paragraphs if p.style.name.startswith("Heading")]
print(f"Total headings: {len(headings)}")
for h in headings[:15]:
    print(f"  {h}")

# Check Media
import zipfile
z = zipfile.ZipFile(doc_path)
media = [f for f in z.namelist() if f.startswith('word/media/')]
print(f"\n=== MEDIA IN FINAL DOCX ({len(media)} files) ===")
for m in sorted(media):
    print(f"  {m}: {z.getinfo(m).file_size} bytes")

print("\nValidation complete!")
