import docx

doc = docx.Document(r"C:\Users\TEJESWAR\Downloads\CodeForge_BuildX_2026_Sample_Project_Report.docx")

for idx, p in enumerate(doc.paragraphs[:25]):
    print(f"P{idx}: {repr(p.text)}")

