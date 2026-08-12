"""Generate the hand-rolled SVG header.

A terminal-style prompt followed by every tagline on one line, separated
by dots in the primary colour. An earlier version cycled the taglines
with a typewriter reveal, showing one at a time; they now sit side by
side so the whole line reads at a glance.

The output is deliberately free of <animate> elements. GitHub overlays a
play/pause control on any image containing animation and honours reduced-
motion by rendering it paused — which froze the old cycling header on its
first tagline and hid the rest. A fully static image has no control to
overlay and looks identical for every visitor.

Run after palette.json exists; output lives at assets/header.svg.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PALETTE_PATH = ROOT / "palette.json"
OUT_PATH = ROOT / "assets" / "header.svg"

TAGLINES = [
    "Renderer engineer",
    "Graphics programmer",
    "GPU programmer",
    "Engine programmer",
]

# Separator padding is applied with dx, not space characters: SVG collapses
# whitespace runs, which renders the line as "Renderer engineer·Graphics
# programmer" with the dots jammed against the words.
SEP_DX = 7

FONT_SIZE = 20
CHAR_PX = FONT_SIZE * 0.6  # mono advance is 0.6em in JetBrains Mono / Fira Code
PROMPT_X = 30
TEXT_X = 60
BASELINE_Y = 38
CURSOR_W = 10
CURSOR_H = 22
CURSOR_Y = BASELINE_Y - CURSOR_H + 5
HEIGHT = 62
RIGHT_PAD = 30


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


def build() -> str:
    palette = load_palette()
    primary = palette["primary"]
    light = palette["light"]
    # The taglines are drawn in the palette's light colour. Without a card
    # behind them they sat directly on the page background, which made them
    # near-invisible on GitHub's light theme. Every other asset on the
    # profile carries its own card; this one now does too.
    card_fill = mix(hex_to_rgb(palette["dark"]), hex_to_rgb(primary), 0.07)
    card_stroke = mix(hex_to_rgb(palette["dark"]), hex_to_rgb(primary), 0.42)

    line = " · ".join(TAGLINES)

    # Separators get the accent colour, taglines stay in the text colour.
    spans: list[str] = []
    for i, tag in enumerate(TAGLINES):
        if i:
            spans.append(f'<tspan fill="{primary}" dx="{SEP_DX}">·</tspan>')
            spans.append(f'<tspan fill="{light}" dx="{SEP_DX}">{tag}</tspan>')
        else:
            spans.append(f'<tspan fill="{light}">{tag}</tspan>')

    # Width follows the content so the line never runs off the viewBox when
    # taglines are edited: every glyph advances CHAR_PX, and each separator
    # adds a dot plus its two dx gaps.
    seps = len(TAGLINES) - 1
    text_w = sum(len(t) for t in TAGLINES) * CHAR_PX + seps * (CHAR_PX + 2 * SEP_DX)
    cursor_x = TEXT_X + text_w + 14
    width = int(cursor_x + CURSOR_W + RIGHT_PAD)

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {HEIGHT}" width="100%" preserveAspectRatio="xMidYMid meet" role="img" aria-label="{line}">
  <defs>
    <linearGradient id="under" x1="0" x2="1" y1="0" y2="0">
      <stop offset="0%" stop-color="{primary}" stop-opacity="0"/>
      <stop offset="50%" stop-color="{primary}" stop-opacity="0.55"/>
      <stop offset="100%" stop-color="{primary}" stop-opacity="0"/>
    </linearGradient>
  </defs>

  <rect x="0.5" y="0.5" width="{width - 1}" height="{HEIGHT - 1}" rx="10" fill="{card_fill}" stroke="{card_stroke}" stroke-width="1"/>
  <rect x="{PROMPT_X - 12}" y="{HEIGHT - 9}" width="{width - 2 * (PROMPT_X - 12)}" height="1.2" fill="url(#under)"/>

  <g font-family="JetBrains Mono, Fira Code, ui-monospace, monospace" font-size="{FONT_SIZE}">
    <text x="{PROMPT_X}" y="{BASELINE_Y}" fill="{primary}" font-weight="700">&gt;</text>
    <text x="{TEXT_X}" y="{BASELINE_Y}">{''.join(spans)}</text>
  </g>

  <rect x="{cursor_x:.1f}" y="{CURSOR_Y}" width="{CURSOR_W}" height="{CURSOR_H}" fill="{primary}" rx="1.5"/>
</svg>
'''


def main() -> int:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(build())
    print(f"[header] wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
