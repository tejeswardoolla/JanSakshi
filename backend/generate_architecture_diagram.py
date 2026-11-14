import os
from PIL import Image, ImageDraw, ImageFont

def draw_architecture():
    # Width 1200, Height 600
    width = 1200
    height = 550
    im = Image.new("RGB", (width, height), color="#FFFFFF")
    draw = ImageDraw.Draw(im)

    # We can use default or basic font
    try:
        font_title = ImageFont.truetype("arial.ttf", 20)
        font_box = ImageFont.truetype("arial.ttf", 15)
        font_sub = ImageFont.truetype("arial.ttf", 12)
    except:
        font_title = ImageFont.load_default()
        font_box = ImageFont.load_default()
        font_sub = ImageFont.load_default()

    # Draw rounded boxes for layers
    boxes = [
        # (x0, y0, x1, y1, title, subtitle, color, border)
        (40, 100, 240, 450, "CITIZEN INTAKE", "• Public Web Portal (React)\n• Interactive Leaflet Map\n• Official Gmail Gateway\n• Public Tracking Desk", "#EBF5FB", "#2980B9"),
        (280, 80, 580, 470, "BACKEND CORE (FastAPI)", "• REST API & Auth Router (JWT)\n• RBAC Middleware Engine\n• Google Gemini AI Analysis\n• Haversine & Duplicate Engine\n• 7-Field Department Dispatch\n• Versioned Resolution Audit", "#E8F8F5", "#16A085"),
        (620, 100, 860, 450, "MUNICIPAL WORKSPACES", "• Admin Management Desk\n• Authority Officer Portal\n• 6 Dept Field Workspaces:\n   - RPW (Roads & Works)\n   - SWM (Sanitation)\n   - WSD (Water Supply)\n   - DRN (Drainage)\n   - ESM (Electrical)\n   - PID (Parks & Infra)", "#FEF9E7", "#F39C12"),
        (900, 100, 1160, 450, "DATA & EXTERNAL TIERS", "• SQLAlchemy ORM (SQLite)\n• 10 Relational Data Tables\n• Physical Issue Clustering\n• Evidence Media Vault\n• Google Gemini API\n• Gmail OAuth 2.0 Client", "#F4ECF7", "#8E44AD"),
    ]

    for b in boxes:
        x0, y0, x1, y1, title, sub, bg, border = b
        draw.rounded_rectangle([x0, y0, x1, y1], radius=12, fill=bg, outline=border, width=3)
        # Header box
        draw.rounded_rectangle([x0, y0, x1, y0 + 40], radius=10, fill=border)
        draw.text((x0 + 15, y0 + 10), title, fill="#FFFFFF", font=font_title)
        draw.text((x0 + 15, y0 + 60), sub, fill="#2C3E50", font=font_box, spacing=10)

    # Draw arrows between boxes
    arrow_color = "#E67E22"
    arrows = [
        (240, 260, 280, 260),
        (580, 260, 620, 260),
        (860, 260, 900, 260),
    ]

    for ax0, ay0, ax1, ay1 in arrows:
        draw.line([ax0, ay0, ax1, ay1], fill=arrow_color, width=4)
        # Arrowhead
        draw.polygon([(ax1, ay1), (ax1 - 12, ay1 - 7), (ax1 - 12, ay1 + 7)], fill=arrow_color)

    # Title
    draw.text((380, 25), "JanSakshi Multi-Tier High-Level System Architecture", fill="#1A252F", font=font_title)

    out_path = r"C:\Users\TEJESWAR\Desktop\JanSakshi\figure_1_architecture.png"
    im.save(out_path)
    print("Saved architecture diagram to:", out_path)

if __name__ == "__main__":
    draw_architecture()

