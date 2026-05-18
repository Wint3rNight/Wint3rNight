"""Generate the custom GPU-pipeline SVG that replaces the badge wall.

Six stages of a render pipeline laid out left-to-right with arrows, plus
three tool sidecars (build / compute / debug) hanging off the main bar
with dashed connectors. Each card labels its stage and the tech that
lives there, so the "stack" reads as how the languages actually fit
together instead of a flat list of badges.

Pulls colors from palette.json; output goes to assets/pipeline.svg.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PALETTE_PATH = ROOT / "palette.json"
OUT_PATH = ROOT / "assets" / "pipeline.svg"

WIDTH = 1100
HEIGHT = 360

# pipeline stages: top row, left -> right
STAGES = [
    ("application", "C++  ·  C#"),
    ("graphics api", "OpenGL  ·  Vulkan"),
    ("vertex stage", "GLSL  ·  HLSL"),
    ("IR", "SPIR-V"),
    ("fragment stage", "GLSL  ·  HLSL"),
    ("framebuffer", "→  display"),
]

# sidecar tools: (label, role, anchor_stage_index)
SIDECARS = [
    ("CMake", "build", 0),
    ("CUDA", "compute", 2),
    ("RenderDoc", "debug", 4),
]

STAGE_W = 134
STAGE_H = 78
ROW_Y = 70
LEFT_PAD = 56
GAP = (WIDTH - 2 * LEFT_PAD - len(STAGES) * STAGE_W) / (len(STAGES) - 1)

SIDECAR_W = 120
SIDECAR_H = 58
SIDECAR_Y = 240


def load_palette() -> dict[str, str]:
    if PALETTE_PATH.exists():
        return json.loads(PALETTE_PATH.read_text())
    return {"primary": "#8658E3", "dark": "#1A1A1A", "light": "#DADADA"}


def stage_x(i: int) -> float:
    return LEFT_PAD + i * (STAGE_W + GAP)


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
    dark = palette["dark"]
    light = palette["light"]

    p_rgb = hex_to_rgb(primary)
    d_rgb = hex_to_rgb(dark)
    card_fill = mix(d_rgb, p_rgb, 0.08)
    card_stroke = mix(d_rgb, p_rgb, 0.45)
    muted = mix(d_rgb, hex_to_rgb(light), 0.55)

    out: list[str] = []

    out.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" width="100%" preserveAspectRatio="xMidYMid meet" role="img" aria-label="render pipeline / stack">')
    out.append('  <defs>')
    out.append(f'    <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="9" markerHeight="9" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="{primary}"/></marker>')
    out.append(f'    <linearGradient id="rail" x1="0" x2="1" y1="0" y2="0"><stop offset="0%" stop-color="{primary}" stop-opacity="0"/><stop offset="15%" stop-color="{primary}" stop-opacity="0.7"/><stop offset="85%" stop-color="{primary}" stop-opacity="0.7"/><stop offset="100%" stop-color="{primary}" stop-opacity="0"/></linearGradient>')
    out.append('  </defs>')

    # ambient rail under the pipeline
    rail_y = ROW_Y + STAGE_H / 2
    out.append(f'  <rect x="20" y="{rail_y - 0.6:.1f}" width="{WIDTH - 40}" height="1.2" fill="url(#rail)"/>')

    # arrows BETWEEN stages
    for i in range(len(STAGES) - 1):
        x1 = stage_x(i) + STAGE_W + 6
        x2 = stage_x(i + 1) - 4
        out.append(f'  <line x1="{x1:.1f}" y1="{rail_y:.1f}" x2="{x2:.1f}" y2="{rail_y:.1f}" stroke="{primary}" stroke-width="1.6" marker-end="url(#arr)"/>')

    # pipeline cards
    for i, (label, sub) in enumerate(STAGES):
        x = stage_x(i)
        out.append(f'  <g>')
        out.append(f'    <rect x="{x:.1f}" y="{ROW_Y}" width="{STAGE_W}" height="{STAGE_H}" rx="6" fill="{card_fill}" stroke="{card_stroke}" stroke-width="1"/>')
        # stage index pip
        out.append(f'    <circle cx="{x + 12:.1f}" cy="{ROW_Y + 12:.1f}" r="3.2" fill="{primary}"/>')
        out.append(f'    <text x="{x + STAGE_W/2:.1f}" y="{ROW_Y + 32}" font-size="13" font-family="JetBrains Mono, Fira Code, ui-monospace, monospace" font-weight="700" fill="{light}" text-anchor="middle">{label}</text>')
        out.append(f'    <text x="{x + STAGE_W/2:.1f}" y="{ROW_Y + 56}" font-size="12" font-family="JetBrains Mono, Fira Code, ui-monospace, monospace" fill="{primary}" text-anchor="middle">{sub}</text>')
        out.append(f'  </g>')

    # sidecar tools below
    for label, role, anchor in SIDECARS:
        ax = stage_x(anchor) + STAGE_W / 2
        sx = ax - SIDECAR_W / 2
        # dashed connector
        out.append(f'  <line x1="{ax:.1f}" y1="{ROW_Y + STAGE_H}" x2="{ax:.1f}" y2="{SIDECAR_Y}" stroke="{card_stroke}" stroke-width="1" stroke-dasharray="3 4"/>')
        # card
        out.append(f'  <g>')
        out.append(f'    <rect x="{sx:.1f}" y="{SIDECAR_Y}" width="{SIDECAR_W}" height="{SIDECAR_H}" rx="6" fill="{card_fill}" stroke="{card_stroke}" stroke-width="1"/>')
        out.append(f'    <text x="{ax:.1f}" y="{SIDECAR_Y + 24}" font-size="14" font-family="JetBrains Mono, Fira Code, ui-monospace, monospace" font-weight="700" fill="{light}" text-anchor="middle">{label}</text>')
        out.append(f'    <text x="{ax:.1f}" y="{SIDECAR_Y + 44}" font-size="11" font-family="JetBrains Mono, Fira Code, ui-monospace, monospace" fill="{muted}" text-anchor="middle">// {role}</text>')
        out.append(f'  </g>')

    # caption strip at top
    out.append(f'  <text x="{LEFT_PAD}" y="36" font-size="12" font-family="JetBrains Mono, Fira Code, ui-monospace, monospace" fill="{muted}">// the stack, in the order pixels move through it</text>')

    # legend (bottom)
    legend_y = HEIGHT - 24
    out.append(f'  <g font-family="JetBrains Mono, Fira Code, ui-monospace, monospace" font-size="11" fill="{muted}">')
    out.append(f'    <text x="{LEFT_PAD}" y="{legend_y}">— pipeline flow</text>')
    out.append(f'    <text x="{LEFT_PAD + 160}" y="{legend_y}" fill="{muted}">- - sidecar tooling</text>')
    out.append(f'    <text x="{WIDTH - LEFT_PAD}" y="{legend_y}" text-anchor="end">10 stack items</text>')
    out.append(f'  </g>')

    out.append('</svg>')
    return '\n'.join(out) + '\n'


def main() -> int:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(build())
    print(f"[pipeline] wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
