"""
Generate JARVIS icons for Electron (Windows .ico, macOS .icns, tray .png)
Run: python generate_icons.py
Requires: pip install Pillow
On macOS, also creates .icns via iconutil
"""
from PIL import Image, ImageDraw
import os
import subprocess
import struct

SIZE = 256
OUT_DIR = os.path.join(os.path.dirname(__file__), "assets")
os.makedirs(OUT_DIR, exist_ok=True)


def create_icon(size=256, bg="#030303", fg="#00FF66", ring="#00FF66"):
    """Create a JARVIS icon — green dot with rings."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx, cy = size // 2, size // 2
    r = size // 2 - 4

    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=bg)

    for frac, alpha in [(0.85, "40"), (0.65, "60"), (0.45, "30")]:
        rr = int(r * frac)
        draw.ellipse(
            [cx - rr, cy - rr, cx + rr, cy + rr],
            outline=ring + alpha,
            width=max(1, size // 128),
        )

    dot_r = int(r * 0.15)
    draw.ellipse([cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r], fill=fg)

    return img


def create_ico(images, path):
    """Write a proper multi-size ICO file."""
    sizes = [(img.size[0], img.size[1]) for img in images]
    count = len(images)

    # ICO header
    ico = struct.pack("<HHH", 0, 1, count)

    # Calculate offsets
    dir_size = 6 + count * 16
    data_offset = dir_size
    image_data_list = []

    for img in images:
        w, h = img.size
        # Convert to BGRA with XOR mask
        rgba = img.convert("RGBA")
        pixels = list(rgba.getdata())

        # Build BMP data (BI_RGB, 32-bit, bottom-up)
        bmp_header = struct.pack("<IiiHHIIiiII", 40, w, h * 2, 1, 32, 0, 0, 0, 0, 0, 0)

        # Pixel data (BGRA, bottom-up)
        pixel_data = b""
        for y in range(h - 1, -1, -1):
            for x in range(w):
                r, g, b, a = pixels[y * w + x]
                pixel_data += struct.pack("BBBB", b, g, r, a)

        # AND mask (all zeros = fully opaque)
        and_mask = b"\x00" * (((w + 31) // 32) * 4 * h)

        data = bmp_header + pixel_data + and_mask
        image_data_list.append(data)

        size = len(data)
        ico += struct.pack("<BBBBHHII", w if w < 256 else 0, h if h < 256 else 0, 0, 0, 1, 32, size, data_offset)
        data_offset += size

    with open(path, "wb") as f:
        f.write(ico)
        for data in image_data_list:
            f.write(data)


def create_icns(img, out_dir):
    """Create .icns via iconutil (macOS only)."""
    iconset_dir = os.path.join(out_dir, "JARVIS.iconset")
    os.makedirs(iconset_dir, exist_ok=True)

    sizes = {
        "icon_16x16.png": 16,
        "icon_16x16@2x.png": 32,
        "icon_32x32.png": 32,
        "icon_32x32@2x.png": 64,
        "icon_128x128.png": 128,
        "icon_128x128@2x.png": 256,
        "icon_256x256.png": 256,
        "icon_256x256@2x.png": 512,
        "icon_512x512.png": 512,
        "icon_512x512@2x.png": 1024,
    }

    for name, sz in sizes.items():
        resized = img.resize((sz, sz), Image.LANCZOS)
        resized.save(os.path.join(iconset_dir, name))

    subprocess.run(["iconutil", "-c", "icns", iconset_dir, "-o", os.path.join(out_dir, "icon.icns")], check=True)
    import shutil
    shutil.rmtree(iconset_dir)
    print("Created icon.icns")


def main():
    icon = create_icon(256)
    icon.save(os.path.join(OUT_DIR, "icon.png"))
    print("Created icon.png")

    ico_sizes = [16, 32, 48, 64, 128, 256]
    ico_images = [create_icon(s) for s in ico_sizes]
    create_ico(ico_images, os.path.join(OUT_DIR, "icon.ico"))
    print("Created icon.ico")

    tray = create_icon(32)
    tray.resize((16, 16), Image.LANCZOS).save(os.path.join(OUT_DIR, "tray-icon.png"))
    print("Created tray-icon.png")

    sidebar = Image.new("RGBA", (164, 314), (3, 3, 3, 255))
    sdraw = ImageDraw.Draw(sidebar)
    for y in range(0, 314, 4):
        alpha = int(40 * (1 - y / 314))
        sdraw.line([(0, y), (164, y)], fill=(0, 255, 102, alpha))
    sidebar.save(os.path.join(OUT_DIR, "sidebar.bmp"), format="BMP")
    print("Created sidebar.bmp")

    if os.name == "posix" and os.path.exists("/usr/bin/iconutil"):
        create_icns(icon, OUT_DIR)
    else:
        print("Skipping .icns (not macOS) — will create on CI")

    print("\nAll icons generated in", OUT_DIR)


if __name__ == "__main__":
    main()
