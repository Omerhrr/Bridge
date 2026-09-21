"""Generate Bridge PWA icons: navy rounded square, suspension-bridge mark.

Outputs (in frontend/public/):
  icons/icon-192.png, icons/icon-512.png, icons/maskable-512.png,
  icons/apple-touch-icon.png (180), favicon.ico
"""
from PIL import Image, ImageDraw
import os

OUT = "/home/z/my-project/frontend/public"
os.makedirs(f"{OUT}/icons", exist_ok=True)

NAVY = (11, 18, 32, 255)        # #0B1220
BLUE = (37, 99, 235, 255)       # #2563EB signal blue
CYAN = (6, 182, 212, 255)       # #06B6D4 communication cyan
LIGHT = (248, 250, 252, 255)    # #F8FAFC
SLATE = (226, 232, 240, 255)    # #E2E8F0


def rounded_bg(size: int) -> Image.Image:
    """Transparent canvas with a rounded-square navy tile."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * 0.19), fill=NAVY)
    return img


def draw_mark(img: Image.Image, scale: float = 1.0) -> None:
    """Draw the bridge mark (suspension bridge + deck) centered on img.

    Coordinates are authored in a 512 space, then scaled by `scale` about
    the canvas center — used by the maskable icon (0.72) and touch icon.
    """
    size = img.width
    d = ImageDraw.Draw(img)
    s = size / 512.0 * scale
    cx, cy = size / 2, size / 2

    def pt(x: float, y: float) -> tuple[float, float]:
        """Author-space (512 box, origin at its top-left) -> canvas space."""
        ax = 256 + (x - 256) * scale
        ay = 256 + (y - 256) * scale
        return ax * s / (size / 512.0), ay * s / (size / 512.0)

    def rect(x0, y0, x1, y1, fill, radius=0):
        a = pt(x0, y0)
        b = pt(x1, y1)
        if radius:
            d.rounded_rectangle([a[0], a[1], b[0], b[1]], radius=radius * s, fill=fill)
        else:
            d.rectangle([a[0], a[1], b[0], b[1]], fill=fill)

    def arc(x0, y0, x1, y1, width, fill):
        a = pt(x0, y0)
        b = pt(x1, y1)
        d.arc([a[0], a[1], b[0], b[1]], start=180, end=360, fill=fill, width=int(width * s))

    # Towers (drawn first, arcs overlap them)
    rect(118, 262, 136, 372, SLATE, radius=6)
    rect(376, 262, 394, 372, SLATE, radius=6)
    # Main span (signal blue) and inner span (cyan) — both spring at the deck
    arc(88, 206, 424, 534, 30, BLUE)
    arc(152, 240, 360, 500, 20, CYAN)
    # Deck line across the springline (y=370..388)
    rect(88, 370, 424, 388, LIGHT, radius=9)


def icon(size: int, maskable: bool = False) -> Image.Image:
    if maskable:
        # Full-bleed square (no transparency) with the mark inside the
        # 80% safe zone so Android's circular mask never clips it.
        img = Image.new("RGBA", (size, size), NAVY)
        draw_mark(img, scale=0.72)
    else:
        img = rounded_bg(size)
        draw_mark(img, scale=0.94)
    return img


# App icons (rounded square, transparent corners)
icon(192).save(f"{OUT}/icons/icon-192.png")
icon(512).save(f"{OUT}/icons/icon-512.png")
icon(512, maskable=True).save(f"{OUT}/icons/maskable-512.png")

# Apple touch icon: 180px, full-bleed (iOS applies its own mask)
apple = Image.new("RGBA", (180, 180), NAVY)
draw_mark(apple, scale=0.86)
apple.convert("RGB").save(f"{OUT}/icons/apple-touch-icon.png")

# favicon.ico from the 256 render
icon(256).save(f"{OUT}/favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])

print("icons written to", OUT)
