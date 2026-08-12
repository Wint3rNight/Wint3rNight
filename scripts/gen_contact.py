"""Generate the contact cards that replace the shields.io badge row.

The badges were the last third-party image dependency on the profile and
the last piece of stock styling — everything else is hand-rolled SVG in
the palette. gen_cards.py exists because a third-party image host going
down turns a profile into a wall of broken-image icons; the same argument
applies here, so these are local files too.

One SVG per destination, because GitHub strips <a> elements inside an SVG
embedded as an image: the link has to live in the README markdown around
each card, the way the featured cards work.

Styling follows the tool cards in the stack diagram — a small uppercase
label over the handle, no icons, so it reads as part of the same system.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PALETTE_PATH = ROOT / "palette.json"
ASSETS = ROOT / "assets"

# (slug, label, handle) — slug becomes assets/contact-<slug>.svg
CONTACTS = [
    ("email", "email", "pratap2003singh@gmail.com"),
    ("linkedin", "linkedin", "prataporwinters"),
    ("instagram", "instagram", "amidreaminnnn"),
    ("leetcode", "leetcode", "winter007"),
]

MONO = "JetBrains Mono, Fira Code, ui-monospace, monospace"
HEIGHT = 54
PAD_X = 16
LABEL_SIZE = 10
LABEL_TRACKING = 1.4
HANDLE_SIZE = 13
HANDLE_CHAR_PX = HANDLE_SIZE * 0.6


def load_palette() -> dict[str, str]:
    if PALETTE_PATH.exists():
        return json.loads(PALETTE_PATH.read_text())
    return {"primary": "#8658E3", "dark": "#1A1A1A", "light": "#DADADA"}


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> str:
    return "#{:02X}{:02X}{:02X}".format(
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


def esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_card(label: str, handle: str, palette: dict[str, str]) -> tuple[str, int]:
    primary = palette["primary"]
    light = palette["light"]
    d_rgb = hex_to_rgb(palette["dark"])
    p_rgb = hex_to_rgb(primary)
    l_rgb = hex_to_rgb(light)
    fill = mix(d_rgb, p_rgb, 0.07)
    stroke = mix(d_rgb, p_rgb, 0.42)
    muted = mix(d_rgb, l_rgb, 0.5)

    # Width follows the wider of the two lines so no handle is ever clipped.
    label_w = len(label) * (LABEL_SIZE * 0.6 + LABEL_TRACKING)
    handle_w = len(handle) * HANDLE_CHAR_PX
    width = int(max(label_w, handle_w) + 2 * PAD_X)

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {HEIGHT}" width="{width}" height="{HEIGHT}" role="img" aria-label="{esc(label)}: {esc(handle)}">
  <rect x="0.5" y="0.5" width="{width - 1}" height="{HEIGHT - 1}" rx="8" fill="{fill}" stroke="{stroke}" stroke-width="1"/>
  <g font-family="{MONO}">
    <text x="{PAD_X}" y="21" font-size="{LABEL_SIZE}" fill="{muted}" letter-spacing="{LABEL_TRACKING}">{esc(label.upper())}</text>
    <text x="{PAD_X}" y="40" font-size="{HANDLE_SIZE}" font-weight="700" fill="{light}">{esc(handle)}</text>
  </g>
  <rect x="{PAD_X}" y="46" width="18" height="1.6" rx="0.8" fill="{primary}"/>
</svg>
'''
    return svg, width


def main() -> int:
    palette = load_palette()
    ASSETS.mkdir(parents=True, exist_ok=True)
    for slug, label, handle in CONTACTS:
        svg, width = build_card(label, handle, palette)
        path = ASSETS / f"contact-{slug}.svg"
        path.write_text(svg)
        print(f"[contact] wrote {path} ({width}x{HEIGHT})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
