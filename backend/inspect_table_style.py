import docx

doc = docx.Document(r"C:\Users\TEJESWAR\Downloads\CodeForge_BuildX_2026_Sample_Project_Report.docx")

for i, t in enumerate(doc.tables):
    print(f"Table {i} style:", t.style.name if t.style else "None")

