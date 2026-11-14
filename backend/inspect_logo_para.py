import docx

doc = docx.Document(r"C:\Users\TEJESWAR\Downloads\CodeForge_BuildX_2026_Sample_Project_Report.docx")

for i in range(14, 18):
    p = doc.paragraphs[i]
    print(f"P{i}: len runs={len(p.runs)}, xml snippet={p._p.xml[:300]}")

