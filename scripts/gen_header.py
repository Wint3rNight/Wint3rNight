"""Generate the hand-rolled animated SVG header.

A terminal-style typewriter that cycles through the taglines: each one
reveals via an animated clip-path, the cursor follows the typed portion
and then blinks, the prompt sits left in the primary color. No third-
party widgets, no JS — pure SMIL so it renders on GitHub.

Run after palette.json exists; output lives at assets/header.svg.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PALETTE_PATH = ROOT / "palette.json"
OUT_PATH = ROOT / "assets" / "header.svg"

TAGLINES = [
    "I code sometimes",
    "Graphics programmer",
    "GPU programmer",
    "Engine programmer",
]

FONT_SIZE = 26
CHAR_PX = 15.6  # approx mono advance at FONT_SIZE for Fira Code / JetBrains Mono
PROMPT_X = 36
TEXT_X = 78
BASELINE_Y = 48
CURSOR_W = 13
CURSOR_H = 28
CURSOR_Y = BASELINE_Y - CURSOR_H + 6
WIDTH = 780
HEIGHT = 72

CYCLE = 14.0          # total loop length in seconds
SLOT = CYCLE / len(TAGLINES)   # 3.5s per tagline
REVEAL = 1.2          # seconds to type a tagline
HOLD = SLOT - REVEAL - 0.05    # remainder, minus a tiny tail to fade


def load_palette() -> dict[str, str]:
    if PALETTE_PATH.exists():
        return json.loads(PALETTE_PATH.read_text())
    return {"primary": "#8658E3", "dark": "#1A1A1A", "light": "#DADADA"}


def kt(t: float) -> str:
    """Format a keyTime fraction without trailing zeros."""
    s = f"{t:.6f}".rstrip("0").rstrip(".")
    return s or "0"


def build() -> str:
    palette = load_palette()
    primary = palette["primary"]
    light = palette["light"]
    dim = palette["dark"]

    clip_defs: list[str] = []
    texts: list[str] = []
    cursor_x_values: list[str] = []
    cursor_x_keytimes: list[str] = []

    cursor_x_values.append(str(TEXT_X))
    cursor_x_keytimes.append("0")

    for i, line in enumerate(TAGLINES):
        slot_start = i * SLOT
        reveal_end = slot_start + REVEAL
        slot_end = slot_start + SLOT
        width_px = max(1.0, len(line) * CHAR_PX)

        # clip rect width across the whole CYCLE: 0 -> full during reveal,
        # hold full during HOLD, snap back to 0 at slot end.
        ks: list[float] = []
        vs: list[float] = []
        if i == 0:
            ks.append(0.0)
            vs.append(0.0)
        else:
            ks += [0.0, slot_start / CYCLE]
            vs += [0.0, 0.0]
        ks += [reveal_end / CYCLE, (slot_end - 0.001) / CYCLE]
        vs += [width_px, width_px]
        if i < len(TAGLINES) - 1:
            ks += [slot_end / CYCLE, 1.0]
            vs += [0.0, 0.0]
        else:
            ks += [1.0]
            vs += [width_px]

        clip_defs.append(
            f'    <clipPath id="c{i}"><rect x="{TEXT_X}" y="{BASELINE_Y - 30}" width="0" height="42">'
            f'<animate attributeName="width" '
            f'values="{";".join(f"{v:.2f}" for v in vs)}" '
            f'keyTimes="{";".join(kt(k) for k in ks)}" '
            f'dur="{CYCLE}s" repeatCount="indefinite"/></rect></clipPath>'
        )

        texts.append(
            f'  <text x="{TEXT_X}" y="{BASELINE_Y}" font-size="{FONT_SIZE}" fill="{light}" '
            f'clip-path="url(#c{i})">{line}</text>'
        )

        # cursor: travel right during reveal, hold at end during HOLD, snap to TEXT_X at slot end
        cursor_x_keytimes += [
            kt(slot_start / CYCLE),
            kt(reveal_end / CYCLE),
            kt((slot_end - 0.001) / CYCLE),
        ]
        cursor_x_values += [
            str(TEXT_X),
            f"{TEXT_X + width_px:.2f}",
            f"{TEXT_X + width_px:.2f}",
        ]
        if i < len(TAGLINES) - 1:
            cursor_x_keytimes.append(kt(slot_end / CYCLE))
            cursor_x_values.append(str(TEXT_X))

    cursor_x_keytimes.append("1")
    cursor_x_values.append(f"{TEXT_X + max(len(t) for t in TAGLINES) * CHAR_PX:.2f}")

    # The first prepended (0, TEXT_X) duplicates with the next entry for slot 0;
    # strip if so to keep keyTimes strictly nondecreasing.
    if len(cursor_x_keytimes) > 1 and cursor_x_keytimes[1] == "0":
        cursor_x_keytimes.pop(0)
        cursor_x_values.pop(0)

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" width="100%" preserveAspectRatio="xMidYMid meet" role="img" aria-label="terminal tagline">
  <defs>
    <linearGradient id="under" x1="0" x2="1" y1="0" y2="0">
      <stop offset="0%" stop-color="{primary}" stop-opacity="0"/>
      <stop offset="50%" stop-color="{primary}" stop-opacity="0.55"/>
      <stop offset="100%" stop-color="{primary}" stop-opacity="0"/>
    </linearGradient>
{chr(10).join(clip_defs)}
  </defs>

  <rect x="{PROMPT_X - 12}" y="{HEIGHT - 6}" width="{WIDTH - 2*(PROMPT_X - 12)}" height="1.2" fill="url(#under)"/>

  <text x="{PROMPT_X}" y="{BASELINE_Y}" font-size="{FONT_SIZE}" font-family="JetBrains Mono, Fira Code, ui-monospace, monospace" fill="{primary}" font-weight="700">&gt;</text>

  <g font-family="JetBrains Mono, Fira Code, ui-monospace, monospace">
{chr(10).join(texts)}
  </g>

  <rect width="{CURSOR_W}" height="{CURSOR_H}" y="{CURSOR_Y}" fill="{primary}" rx="1.5">
    <animate attributeName="x"
      values="{";".join(cursor_x_values)}"
      keyTimes="{";".join(cursor_x_keytimes)}"
      dur="{CYCLE}s" repeatCount="indefinite"/>
    <animate attributeName="opacity"
      values="1;1;0;0;1"
      keyTimes="0;0.45;0.5;0.95;1"
      dur="0.9s" repeatCount="indefinite"/>
  </rect>
</svg>
'''
    return svg


def main() -> int:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(build())
    print(f"[header] wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
