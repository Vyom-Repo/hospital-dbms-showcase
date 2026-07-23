"""
Generate production Favicons and GitHub Banner for Hospital DBMS Showcase
"""

from PIL import Image, ImageDraw, ImageFont
import os

# Ensure directories exist
os.makedirs("static", exist_ok=True)
os.makedirs("docs", exist_ok=True)

# ─── 1. SVG Favicon ─────────────────────────────────────────────────────────
svg_content = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64">
  <rect x="2" y="2" width="60" height="60" rx="14" fill="#064e3b" stroke="#10b981" stroke-width="2"/>
  <!-- Database Cylinders -->
  <ellipse cx="32" cy="18" rx="18" ry="6" fill="#10b981"/>
  <path d="M14,18 v12 c0,3.3 8,6 18,6 s18,-2.7 18,-6 v-12" fill="none" stroke="#34d399" stroke-width="2.5"/>
  <path d="M14,30 v12 c0,3.3 8,6 18,6 s18,-2.7 18,-6 v-12" fill="none" stroke="#34d399" stroke-width="2.5"/>
  <!-- Medical Cross Badge -->
  <circle cx="48" cy="46" r="11" fill="#f59e0b" stroke="#060a12" stroke-width="2"/>
  <path d="M48,40 v12 M42,46 h12" stroke="#060a12" stroke-width="3.5" stroke-linecap="round"/>
</svg>"""

with open("static/favicon.svg", "w") as f:
    f.write(svg_content)

print("✓ static/favicon.svg created")

# ─── 2. PNG Favicons & ICO ──────────────────────────────────────────────────
# Render raster favicons
sizes = [16, 32, 48, 64, 128]
images = []

for size in sizes:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Background rounded rect
    margin = max(1, size // 16)
    r = size // 4
    draw.rounded_rectangle([margin, margin, size - margin, size - margin], radius=r, fill=(6, 78, 59, 255), outline=(16, 185, 129, 255), width=max(1, size // 32))
    
    # DB cylinder top
    cx, cy = size // 2, int(size * 0.3)
    rx, ry = int(size * 0.28), int(size * 0.1)
    draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=(16, 185, 129, 255))
    
    # DB lines
    w = max(1, size // 24)
    y1 = int(size * 0.45)
    draw.arc([cx - rx, y1 - ry, cx + rx, y1 + ry], start=0, end=180, fill=(52, 211, 153, 255), width=w)
    draw.line([cx - rx, cy, cx - rx, y1], fill=(52, 211, 153, 255), width=w)
    draw.line([cx + rx, cy, cx + rx, y1], fill=(52, 211, 153, 255), width=w)
    
    y2 = int(size * 0.6)
    draw.arc([cx - rx, y2 - ry, cx + rx, y2 + ry], start=0, end=180, fill=(52, 211, 153, 255), width=w)
    draw.line([cx - rx, y1, cx - rx, y2], fill=(52, 211, 153, 255), width=w)
    draw.line([cx + rx, y1, cx + rx, y2], fill=(52, 211, 153, 255), width=w)
    
    # Medical Cross badge
    bcx, bcy = int(size * 0.72), int(size * 0.72)
    br = int(size * 0.18)
    draw.ellipse([bcx - br, bcy - br, bcx + br, bcy + br], fill=(245, 158, 11, 255), outline=(6, 10, 18, 255), width=max(1, size // 32))
    
    cw = max(1, int(br * 0.35))
    ch = int(br * 0.65)
    draw.rectangle([bcx - cw, bcy - ch, bcx + cw, bcy + ch], fill=(6, 10, 18, 255))
    draw.rectangle([bcx - ch, bcy - cw, bcx + ch, bcy + cw], fill=(6, 10, 18, 255))
    
    img.save(f"static/favicon-{size}x{size}.png")
    images.append(img)

# Save favicon.ico containing multiple sizes
images[1].save("static/favicon.ico", format="ICO", sizes=[(16,16), (32,32), (48,48), (64,64)])
print("✓ static/favicon.ico & PNGs created")

# ─── 3. GitHub Banner (docs/banner.png) ──────────────────────────────────────
banner_w, banner_h = 1200, 630
banner = Image.new("RGBA", (banner_w, banner_h), (6, 10, 18, 255))
bdraw = ImageDraw.Draw(banner)

# Background gradient & subtle emerald glow
for y in range(banner_h):
    r = int(6 + (y / banner_h) * 6)
    g = int(10 + (y / banner_h) * 20)
    b = int(18 + (y / banner_h) * 15)
    bdraw.line([(0, y), (banner_w, y)], fill=(r, g, b, 255))

# Top decorative bar (Emerald & Saffron accent line)
bdraw.rectangle([0, 0, banner_w, 6], fill=(16, 185, 129, 255))
bdraw.rectangle([banner_w // 2 - 100, 0, banner_w // 2 + 100, 6], fill=(245, 158, 11, 255))

# Large Icon Box
icon_box = Image.new("RGBA", (140, 140), (0, 0, 0, 0))
ibdraw = ImageDraw.Draw(icon_box)
ibdraw.rounded_rectangle([0, 0, 140, 140], radius=28, fill=(6, 78, 59, 255), outline=(16, 185, 129, 255), width=3)
# DB Icon inside banner
ibdraw.ellipse([30, 30, 110, 60], fill=(16, 185, 129, 255))
ibdraw.arc([30, 50, 110, 80], 0, 180, fill=(52, 211, 153, 255), width=4)
ibdraw.line([(30, 45), (30, 65)], fill=(52, 211, 153, 255), width=4)
ibdraw.line([(110, 45), (110, 65)], fill=(52, 211, 153, 255), width=4)
ibdraw.arc([30, 75, 110, 105], 0, 180, fill=(52, 211, 153, 255), width=4)
ibdraw.line([(30, 65), (30, 90)], fill=(52, 211, 153, 255), width=4)
ibdraw.line([(110, 65), (110, 90)], fill=(52, 211, 153, 255), width=4)
# Medical Cross
ibdraw.ellipse([90, 90, 135, 135], fill=(245, 158, 11, 255), outline=(6, 10, 18, 255), width=3)
ibdraw.rectangle([108, 98, 117, 127], fill=(6, 10, 18, 255))
ibdraw.rectangle([98, 108, 127, 117], fill=(6, 10, 18, 255))

banner.paste(icon_box, (100, 140), icon_box)

# Try loading font or default
try:
    font_title = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 54)
    font_sub = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 26)
    font_badge = ImageFont.truetype("/System/Library/Fonts/Supplemental/Courier New Bold.ttf", 18)
except:
    font_title = ImageFont.load_default()
    font_sub = ImageFont.load_default()
    font_badge = ImageFont.load_default()

# Text
bdraw.text((270, 150), "Hospital DBMS Showcase", fill=(248, 250, 252, 255), font=font_title)
bdraw.text((270, 220), "High-Performance PostgreSQL Enterprise Management System", fill=(148, 163, 184, 255), font=font_sub)

# Badges
badges = ["PostgreSQL 16", "Raw SQL (No ORM)", "FastAPI", "asyncpg", "100K+ Patients", "500K+ Appts", "FOR UPDATE Locking"]
bx = 100
by = 330
for btext in badges:
    tw = len(btext) * 11 + 24
    if bx + tw > banner_w - 100:
        bx = 100
        by += 44
    bdraw.rounded_rectangle([bx, by, bx + tw, by + 34], radius=6, fill=(18, 26, 42, 255), outline=(30, 44, 69, 255), width=1)
    bdraw.text((bx + 12, by + 7), btext, fill=(16, 185, 129, 255), font=font_badge)
    bx += tw + 14

# Bottom Stats Bar
bdraw.rectangle([0, banner_h - 100, banner_w, banner_h], fill=(12, 18, 30, 255), outline=(30, 44, 69, 255), width=1)
stats_list = [
    ("100,000", "PATIENTS"),
    ("500,000", "APPOINTMENTS"),
    ("2,133x", "INDEX SPEEDUP"),
    ("₹91.63 Cr", "BILLED REVENUE"),
    ("100%", "ATOMIC TRANSACTIONS"),
]

sx = 80
for val, lbl in stats_list:
    bdraw.text((sx, banner_h - 80), val, fill=(245, 158, 11, 255), font=font_sub)
    bdraw.text((sx, banner_h - 45), lbl, fill=(100, 116, 139, 255), font=font_badge)
    sx += 220

banner.save("docs/banner.png")
print("✓ docs/banner.png created")
