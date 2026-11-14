import docx

doc = docx.Document(r"C:\Users\TEJESWAR\Downloads\CodeForge_BuildX_2026_Sample_Project_Report.docx")

print(f"Total paragraphs: {len(doc.paragraphs)}")
for idx, p in enumerate(doc.paragraphs):
    runs_info = []
    for r in p.runs:
        font_name = r.font.name or "inherited"
        font_size = f"{r.font.size.pt}pt" if r.font.size else "inherited"
        bold = "B" if r.font.bold else ""
        italic = "I" if r.font.italic else ""
        runs_info.append(f"'{r.text}'({font_name},{font_size},{bold}{italic})")
    
    text_preview = p.text[:60].replace("\n", "\\n")
    if p.text.strip():
        print(f"P{idx:03d} [{p.style.name}] (align={p.alignment}): {text_preview}")
        # print(f"      runs: {runs_info}")

