import os
import zipfile
import shutil

template_path = r"C:\Users\TEJESWAR\Downloads\CodeForge_BuildX_2026_Sample_Project_Report.docx"
print("Checking file exists:", os.path.exists(template_path))
print("File size:", os.path.getsize(template_path), "bytes")

# Inspect media inside docx (unzip)
extract_dir = r"C:\Users\TEJESWAR\Desktop\JanSakshi\report_template_extracted"
if os.path.exists(extract_dir):
    shutil.rmtree(extract_dir)

with zipfile.ZipFile(template_path, 'r') as z:
    z.extractall(extract_dir)

media_dir = os.path.join(extract_dir, "word", "media")
if os.path.exists(media_dir):
    print("Media files in template:")
    for f in os.listdir(media_dir):
        fp = os.path.join(media_dir, f)
        print(f"  {f} ({os.path.getsize(fp)} bytes)")
else:
    print("No word/media dir found.")

