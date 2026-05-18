"""Extract dominant colors from the source skyline and write palette.json.

Uses Image.quantize for a zero-dependency-beyond-Pillow approach. From the
three dominant colors we pick:
  primary -> highest HSL saturation (the accent)
  dark    -> lowest lightness     (the backdrop)
  light   -> highest lightness that isn't near-white (text/highlights)

If the picture is grayscale (as the source skyline is here), saturation is
zero across the board and "primary" would otherwise collapse to a flat grey.
In that case we synthesize a tasteful accent by lifting the mid-tone into a
cool violet that fits the engine/graphics theme.
"""

import colorsys
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "assets" / "source-skyline.jpg"
OUT = ROOT / "palette.json"

FALLBACK = {"primary": "#8B5CF6", "dark": "#0B1026", "light": "#E0E7FF"}


def rgb_to_hsl(r: int, g: int, b: int) -> tuple[float, float, float]:
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    return h, s, l


def hex_of(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def synth_accent_from_dark(dark_rgb: tuple[int, int, int]) -> str:
    """Build a saturated violet/cyan accent whose lightness is mid-range."""
    # Cool violet (260deg) at high saturation, mid lightness.
    r, g, b = colorsys.hls_to_rgb(260 / 360, 0.62, 0.72)
    return hex_of((int(r * 255), int(g * 255), int(b * 255)))


def main() -> int:
    if not SRC.exists():
        print(f"[palette] source missing: {SRC}", file=sys.stderr)
        OUT.write_text(json.dumps({**FALLBACK, "source": str(SRC.relative_to(ROOT))}, indent=2))
        return 1

    try:
        img = Image.open(SRC).convert("RGB").resize((100, 100))
        q = img.quantize(colors=3, method=Image.Quantize.MEDIANCUT).convert("RGB")
        pixels = list(q.getdata())
        # Get the 3 unique palette colors.
        colors = list({p for p in pixels})
        if len(colors) < 3:
            # Pad with shifted variants if quantizer collapsed.
            base = colors[0] if colors else (16, 16, 30)
            while len(colors) < 3:
                colors.append(tuple(min(255, c + 40 * (len(colors))) for c in base))

        ranked_by_sat = sorted(colors, key=lambda c: rgb_to_hsl(*c)[1], reverse=True)
        ranked_by_light = sorted(colors, key=lambda c: rgb_to_hsl(*c)[2])

        dark_rgb = ranked_by_light[0]
        light_rgb = next(
            (c for c in reversed(ranked_by_light) if rgb_to_hsl(*c)[2] < 0.95),
            ranked_by_light[-1],
        )
        primary_rgb = ranked_by_sat[0]

        primary_sat = rgb_to_hsl(*primary_rgb)[1]
        if primary_sat < 0.08:
            # Grayscale source -> synthesize a real accent so the theme has life.
            primary_hex = synth_accent_from_dark(dark_rgb)
        else:
            primary_hex = hex_of(primary_rgb)

        out = {
            "primary": primary_hex,
            "dark": hex_of(dark_rgb),
            "light": hex_of(light_rgb),
            "source": str(SRC.relative_to(ROOT)),
        }
        OUT.write_text(json.dumps(out, indent=2) + "\n")
        print(json.dumps(out, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[palette] extraction failed: {exc}", file=sys.stderr)
        OUT.write_text(json.dumps({**FALLBACK, "source": "fallback"}, indent=2) + "\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
