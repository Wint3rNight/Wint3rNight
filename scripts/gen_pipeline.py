"""Generate the stack diagram: two lanes, plus upstream contribution markers.

Raster and compute are drawn as separate lanes because they are separate
paths. An earlier version chained them into one flow — shaders → IR →
compute → framebuffer — which claimed CUDA consumes SPIR-V and feeds the
framebuffer. Neither is true: CUDA and Vulkan are different APIs, and the
CUDA work (Tinyforge) shares no pipeline with the Vulkan work (Heliora).

The raster lane is ordered as an honest build-and-submit chain: GLSL is
compiled to SPIR-V, which is handed to the graphics API at pipeline
creation, which rasterises to the framebuffer.

Contribution markers hang off the stages where upstream work actually
landed — glslang is the GLSL→SPIR-V compiler, so it sits on that edge;
Vulkan-ValidationLayers sits on the graphics API. Their counts come from
the live search API via gen_oss, not a hardcoded list, so the diagram
can't drift out of sync with reality the way a hand-maintained one does.

Pulls colors from palette.json; output goes to assets/pipeline.svg.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PALETTE_PATH = ROOT / "palette.json"
OUT_PATH = ROOT / "assets" / "pipeline.svg"

WIDTH = 1100
LEFT_PAD = 40
MONO = "JetBrains Mono, Fira Code, ui-monospace, monospace"

# (label, tech, detail) — build-and-submit order, left to right.
RASTER = [
    ("application", "C++", "engine · ECS · allocators"),
    ("shaders", "GLSL", "PBR · SSAO · CSM"),
    ("IR", "SPIR-V", "compiler target"),
    ("graphics api", "Vulkan · OpenGL", "deferred · bindless"),
    ("framebuffer", "HDR · TAA", "→ display"),
]

COMPUTE = [
    ("kernels", "CUDA · cuBLAS", "GEMM · SIMT"),
    ("optimization", "tiling · float4", "occupancy analysis"),
    ("profiling", "Nsight Compute", "4400 GFLOPS"),
]

TOOLS = [
    ("CMake", "build"),
    ("RenderDoc", "frame debug"),
    ("gdb · ASan", "systems"),
]

# Which raster stage each upstream project belongs to, by index into RASTER.
# glslang IS the GLSL→SPIR-V front end, so it marks the IR stage.
CONTRIB_ANCHORS = {
    "KhronosGroup/glslang": 2,
    "KhronosGroup/Vulkan-ValidationLayers": 3,
}

CARD_W = 172
CARD_H = 78
GAP = (WIDTH - 2 * LEFT_PAD - len(RASTER) * CARD_W) / (len(RASTER) - 1)

RASTER_Y = 32
BADGE_Y = 130
BADGE_H = 28
COMPUTE_Y = 196
HEIGHT = COMPUTE_Y + CARD_H + 18

TOOL_W = 108
TOOL_H = 46
TOOLS_X = LEFT_PAD + len(COMPUTE) * CARD_W + (len(COMPUTE) - 1) * GAP + 56


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


def card_x(i: int) -> float:
    return LEFT_PAD + i * (CARD_W + GAP)


def fetch_contributions() -> dict[str, dict[str, int]]:
    """Live per-project counts; an empty dict just means no badges."""
    try:
        from gen_oss import upstream_by_repo

        return upstream_by_repo()
    except (ImportError, OSError, ValueError) as exc:
        print(f"[pipeline] contribution data unavailable: {exc}", file=sys.stderr)
        return {}


def build(contribs: dict[str, dict[str, int]]) -> str:
    palette = load_palette()
    primary = palette["primary"]
    light = palette["light"]
    p_rgb = hex_to_rgb(primary)
    d_rgb = hex_to_rgb(palette["dark"])
    l_rgb = hex_to_rgb(light)

    card_fill = mix(d_rgb, p_rgb, 0.08)
    card_stroke = mix(d_rgb, p_rgb, 0.45)
    muted = mix(d_rgb, l_rgb, 0.5)

    out: list[str] = []
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" width="100%" '
        f'preserveAspectRatio="xMidYMid meet" role="img" aria-label="stack: raster and compute pipelines">'
    )
    out.append('  <defs>')
    out.append(
        f'    <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="9" markerHeight="9" '
        f'orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="{primary}"/></marker>'
    )
    out.append('  </defs>')

    def lane_label(text: str, y: float) -> None:
        out.append(
            f'  <text x="{LEFT_PAD}" y="{y}" font-size="11" font-family="{MONO}" fill="{muted}" '
            f'letter-spacing="1.5">{text.upper()}</text>'
        )

    def draw_row(items, y: float, x0: float, width: float) -> None:
        for i, (label, tech, detail) in enumerate(items):
            x = x0 + i * (width + GAP)
            if i:
                out.append(
                    f'  <line x1="{x - GAP + 6:.1f}" y1="{y + CARD_H / 2:.1f}" x2="{x - 4:.1f}" '
                    f'y2="{y + CARD_H / 2:.1f}" stroke="{primary}" stroke-width="1.6" marker-end="url(#arr)"/>'
                )
            cx = x + width / 2
            out.append(
                f'  <g><rect x="{x:.1f}" y="{y}" width="{width}" height="{CARD_H}" rx="6" '
                f'fill="{card_fill}" stroke="{card_stroke}" stroke-width="1"/>'
                f'<circle cx="{x + 12:.1f}" cy="{y + 12:.1f}" r="3.2" fill="{primary}"/>'
                f'<text x="{cx:.1f}" y="{y + 27}" font-size="13" font-family="{MONO}" font-weight="700" '
                f'fill="{light}" text-anchor="middle">{esc(label)}</text>'
                f'<text x="{cx:.1f}" y="{y + 47}" font-size="12" font-family="{MONO}" fill="{primary}" '
                f'text-anchor="middle">{esc(tech)}</text>'
                f'<text x="{cx:.1f}" y="{y + 65}" font-size="10.5" font-family="{MONO}" fill="{muted}" '
                f'text-anchor="middle">{esc(detail)}</text></g>'
            )

    # ── raster lane ───────────────────────────────────────────────────
    lane_label("raster", RASTER_Y - 12)
    draw_row(RASTER, RASTER_Y, LEFT_PAD, CARD_W)

    # ── upstream contribution badges ──────────────────────────────────
    for repo, anchor in CONTRIB_ANCHORS.items():
        counts = contribs.get(repo)
        if not counts:
            continue  # nothing landed there yet, or the API was unreachable
        merged, open_ = counts["merged"], counts["open"]
        state = f"{merged} merged" if merged else f"{open_} in review"
        accent = primary if merged else muted

        ax = card_x(anchor) + CARD_W / 2
        short = repo.split("/")[-1]
        badge_w = max(len(short), len(state)) * 7.0 + 26
        bx = ax - badge_w / 2

        out.append(
            f'  <line x1="{ax:.1f}" y1="{RASTER_Y + CARD_H}" x2="{ax:.1f}" y2="{BADGE_Y}" '
            f'stroke="{accent}" stroke-width="1" stroke-dasharray="3 4" opacity="0.8"/>'
        )
        out.append(
            f'  <g><rect x="{bx:.1f}" y="{BADGE_Y}" width="{badge_w:.1f}" height="{BADGE_H}" rx="14" '
            f'fill="{card_fill}" stroke="{accent}" stroke-width="1"/>'
            f'<text x="{ax:.1f}" y="{BADGE_Y + 12}" font-size="10.5" font-family="{MONO}" font-weight="700" '
            f'fill="{light}" text-anchor="middle">{esc(short)}</text>'
            f'<text x="{ax:.1f}" y="{BADGE_Y + 23}" font-size="9.5" font-family="{MONO}" '
            f'fill="{accent}" text-anchor="middle">{esc(state)}</text></g>'
        )

    if any(contribs.get(r) for r in CONTRIB_ANCHORS):
        out.append(
            f'  <text x="{WIDTH - LEFT_PAD}" y="{BADGE_Y + 18}" font-size="10.5" font-family="{MONO}" '
            f'fill="{muted}" text-anchor="end">upstream contributions</text>'
        )

    # ── compute lane ──────────────────────────────────────────────────
    lane_label("compute", COMPUTE_Y - 12)
    draw_row(COMPUTE, COMPUTE_Y, LEFT_PAD, CARD_W)

    # ── tools, parked to the right of the compute lane ────────────────
    for i, (label, role) in enumerate(TOOLS):
        x = TOOLS_X + i * (TOOL_W + 20)
        cx = x + TOOL_W / 2
        out.append(
            f'  <g><rect x="{x:.1f}" y="{COMPUTE_Y + 16}" width="{TOOL_W}" height="{TOOL_H}" rx="6" '
            f'fill="{card_fill}" stroke="{card_stroke}" stroke-width="1" stroke-dasharray="4 3"/>'
            f'<text x="{cx:.1f}" y="{COMPUTE_Y + 38}" font-size="11.5" font-family="{MONO}" font-weight="700" '
            f'fill="{light}" text-anchor="middle">{esc(label)}</text>'
            f'<text x="{cx:.1f}" y="{COMPUTE_Y + 53}" font-size="9.5" font-family="{MONO}" fill="{muted}" '
            f'text-anchor="middle">{esc(role)}</text></g>'
        )

    out.append('</svg>')
    return '\n'.join(out) + '\n'


def main() -> int:
    contribs = fetch_contributions()

    # Same reasoning as gen_oss: the workflow auto-commits whatever lands on
    # disk, so a transient API failure must not strip the badges off a good
    # diagram. Only the badges are live data — the lanes themselves are
    # static, so an existing file is always at least as good as a fresh one.
    if not contribs and OUT_PATH.exists():
        print("[pipeline] contribution data unavailable — keeping the existing diagram", file=sys.stderr)
        return 0

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(build(contribs))
    marked = sum(1 for r in CONTRIB_ANCHORS if contribs.get(r))
    print(f"[pipeline] wrote {OUT_PATH}  ({marked}/{len(CONTRIB_ANCHORS)} stages marked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
