import docx

doc = docx.Document(r"C:\Users\TEJESWAR\Downloads\CodeForge_BuildX_2026_Sample_Project_Report.docx")
p14 = doc.paragraphs[14]
for r in p14.runs:
    print("Run text:", repr(r.text), "has drawing:", "<w:drawing>" in r._r.xml)

