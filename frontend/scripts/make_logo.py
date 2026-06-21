"""Render the Tradeoff brand mark (src/components/shared/Logo.tsx) to a PNG.

The logo is an SVG of two paths (teal A, amber B) converging on a single decision
node. Pillow can't rasterise SVG, but the mark is simple geometric primitives, so
we redraw it here from the exact viewBox (0 0 32 32) coordinates and the brand
palette (tailwind.config.ts). Rendered at 4x then downsampled for clean
anti-aliasing (Pillow's ImageDraw doesn't AA lines itself).

Run:  python frontend/scripts/make_logo.py
Out:  frontend/public/logo.png            (branded dark background, 1024px)
      frontend/public/logo-transparent.png (transparent background, 1024px)
"""

from pathlib import Path

from PIL import Image, ImageDraw

# ── Brand palette (tailwind.config.ts) ───────────────────────────────────────
PAPER = (0x0E, 0x15, 0x1E)   # deep blue-slate background
PATH_A = (0x3C, 0xAE, 0xBD)  # teal — country A
PATH_B = (0xE0, 0xA2, 0x4A)  # amber — country B
INK = (0xE9, 0xEE, 0xF2)     # near-white foreground

# ── Geometry (SVG viewBox is 32x32) ──────────────────────────────────────────
VIEWBOX = 32
FINAL = 1024          # output edge in px
SS = 4                # supersample factor
BIG = FINAL * SS
U = BIG / VIEWBOX     # viewBox-unit -> pixel scale
STROKE = 2.5          # stroke-width in viewBox units


def p(x: float, y: float) -> tuple[float, float]:
    return (x * U, y * U)


def round_line(base: Image.Image, a, b, color, width_units, opacity=1.0):
    """Draw a round-capped stroke with per-element opacity via a composited layer."""
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    w = width_units * U
    d.line([p(*a), p(*b)], fill=color + (255,), width=round(w))
    # Emulate SVG round caps with filled circles at each endpoint.
    r = w / 2
    for (cx, cy) in (p(*a), p(*b)):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color + (255,))
    if opacity < 1.0:
        alpha = layer.getchannel("A").point(lambda v: round(v * opacity))
        layer.putalpha(alpha)
    base.alpha_composite(layer)


def filled_circle(base, center, radius_units, color, opacity=1.0):
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = p(*center)
    r = radius_units * U
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color + (255,))
    if opacity < 1.0:
        layer.putalpha(layer.getchannel("A").point(lambda v: round(v * opacity)))
    base.alpha_composite(layer)


def stroked_circle(base, center, radius_units, color, width_units, opacity=1.0):
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = p(*center)
    r = radius_units * U
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color + (255,), width=round(width_units * U))
    if opacity < 1.0:
        layer.putalpha(layer.getchannel("A").point(lambda v: round(v * opacity)))
    base.alpha_composite(layer)


def draw_glyph(background):
    img = Image.new("RGBA", (BIG, BIG), background)
    # outer faint ring (r=6, opacity 0.25) sits behind the node
    stroked_circle(img, (16, 19), 6, INK, 1.0, opacity=0.25)
    # the two converging paths
    round_line(img, (5, 7), (16, 19), PATH_A, STROKE)
    round_line(img, (27, 7), (16, 19), PATH_B, STROKE)
    # the decision stem (opacity 0.55)
    round_line(img, (16, 19), (16, 27), INK, STROKE, opacity=0.55)
    # the decision node
    filled_circle(img, (16, 19), 3.2, INK)
    return img.resize((FINAL, FINAL), Image.LANCZOS)


def main():
    out_dir = Path(__file__).resolve().parents[1] / "public"
    out_dir.mkdir(parents=True, exist_ok=True)

    draw_glyph(PAPER + (255,)).save(out_dir / "logo.png")
    draw_glyph((0, 0, 0, 0)).save(out_dir / "logo-transparent.png")
    print(f"Wrote {out_dir / 'logo.png'} and {out_dir / 'logo-transparent.png'}")


if __name__ == "__main__":
    main()
