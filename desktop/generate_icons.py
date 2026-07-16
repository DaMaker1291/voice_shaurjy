"""
Generate JARVIS icons for Electron (Windows .ico, macOS .icns, tray .png)
Run: python generate_icons.py
Requires: pip install Pillow
"""
from PIL import Image, ImageDraw, ImageFont
import os

SIZE = 256
OUT_DIR = os.path.join(os.path.dirname(__file__), "assets")
os.makedirs(OUT_DIR, exist_ok=True)


def create_icon(size=256, bg="#030303", fg="#00FF66", ring="#00FF66"):
    """Create a JARVIS icon — green dot with rings."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx, cy = size // 2, size // 2
    r = size // 2 - 4

    # Background circle
    draw.ellipse(
        [cx - r, cy - r, cx + r, cy + r],
        fill=bg,
    )

    # Outer ring
    ring_r = int(r * 0.85)
    draw.ellipse(
        [cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r],
        outline=ring + "40",
        width=max(1, size // 128),
    )

    # Middle ring
    ring_r2 = int(r * 0.65)
    draw.ellipse(
        [cx - ring_r2, cy - ring_r2, cx + ring_r2, cy + ring_r2],
        outline=ring + "60",
        width=max(1, size // 128),
    )

    # Inner ring
    ring_r3 = int(r * 0.45)
    draw.ellipse(
        [cx - ring_r3, cy - ring_r3, cx + ring_r3, cy + ring_r3],
        outline=ring + "30",
        width=max(1, size // 128),
    )

    # Center dot
    dot_r = int(r * 0.15)
    draw.ellipse(
        [cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r],
        fill=fg,
    )

    return img


def main():
    # Main icon (256x256)
    icon = create_icon(256)
    icon.save(os.path.join(OUT_DIR, "icon.png"))
    print("Created icon.png")

    # ICO file (multiple sizes for Windows)
    ico_sizes = [16, 32, 48, 64, 128, 256]
    ico_images = [create_icon(s) for s in ico_sizes]
    ico_images[0].save(
        os.path.join(OUT_DIR, "icon.ico"),
        format="ICO",
        sizes=[(s, s) for s in ico_sizes],
        append_images=ico_images[1:],
    )
    print("Created icon.ico")

    # Tray icon (16x16)
    tray = create_icon(32)
    tray.resize((16, 16), Image.LANCZOS).save(os.path.join(OUT_DIR, "tray-icon.png"))
    print("Created tray-icon.png")

    # NSIS sidebar (164x314)
    sidebar = Image.new("RGBA", (164, 314), (3, 3, 3, 255))
    sdraw = ImageDraw.Draw(sidebar)
    # Add gradient lines
    for y in range(0, 314, 4):
        alpha = int(40 * (1 - y / 314))
        sdraw.line([(0, y), (164, y)], fill=(0, 255, 102, alpha))
    sidebar.save(os.path.join(OUT_DIR, "sidebar.bmp"), format="BMP")
    print("Created sidebar.bmp")

    print("\nAll icons generated in", OUT_DIR)


if __name__ == "__main__":
    main()
