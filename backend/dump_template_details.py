import docx
from docx.shared import Inches, Pt

doc = docx.Document(r"C:\Users\TEJESWAR\Downloads\CodeForge_BuildX_2026_Sample_Project_Report.docx")

print("=== SECTIONS ===")
for i, section in enumerate(doc.sections):
    print(f"Section {i}:")
    print(f"  Page width: {section.page_width.inches} in, height: {section.page_height.inches} in")
    print(f"  Margins: left={section.left_margin.inches} in, right={section.right_margin.inches} in, top={section.top_margin.inches} in, bottom={section.bottom_margin.inches} in")
    print(f"  Header text: {[p.text for p in section.header.paragraphs if p.text]}")
    print(f"  Footer text: {[p.text for p in section.footer.paragraphs if p.text]}")

print("\n=== PARAGRAPHS (First 35) ===")
for i, p in enumerate(doc.paragraphs[:35]):
    fonts = set()
    sizes = set()
    for r in p.runs:
        if r.font.name: fonts.add(r.font.name)
        if r.font.size: sizes.add(r.font.size.pt)
    print(f"P{i:02d} [{p.style.name}] (align={p.alignment}, fonts={fonts}, sizes={sizes}): {p.text[:80]}")

print(f"\nTotal paragraphs: {len(doc.paragraphs)}")
print(f"Total tables: {len(doc.tables)}")
for i, table in enumerate(doc.tables):
    print(f"Table {i}: {len(table.rows)} rows x {len(table.columns)} cols")
    for r_idx, row in enumerate(table.rows[:2]):
        print(f"  Row {r_idx}: {[c.text.strip() for c in row.cells]}")

