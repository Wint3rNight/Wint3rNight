"""Generate the linear contribution flow graph.

Smooth area chart of daily contributions over the last 365 days. The
curve is drawn with cubic-bezier Catmull-Rom smoothing for an organic
flow, filled with a vertical gradient that fades from primary to
transparent. The line strokes in over ~2.5s on first paint via
stroke-dashoffset.

Requires a GITHUB_TOKEN in CI to hit GraphQL; falls back to
deterministic mock data when run locally without one so the SVG always
exists.
"""

import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path
from urllib import error, request

ROOT = Path(__file__).resolve().parents[1]
PALETTE_PATH = ROOT / "palette.json"
OUT_PATH = ROOT / "assets" / "activity.svg"

USERNAME = os.environ.get("USERNAME") or os.environ.get("GITHUB_REPOSITORY_OWNER") or "Wint3rNight"
TOKEN = os.environ.get("GITHUB_TOKEN")

DAYS = 365
WIDTH = 1100
HEIGHT = 150
PAD_X = 18
PAD_TOP = 18
PAD_BOTTOM = 14


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


def fetch_contributions(username: str) -> list[int] | None:
    if not TOKEN:
        return None
    end = date.today()
    start = end - timedelta(days=DAYS - 1)
    query = """
    query($login:String!,$from:DateTime!,$to:DateTime!){
      user(login:$login){
        contributionsCollection(from:$from,to:$to){
          contributionCalendar{weeks{contributionDays{date contributionCount}}}
        }
      }
    }"""
    body = json.dumps(
        {
            "query": query,
            "variables": {
                "login": username,
                "from": f"{start}T00:00:00Z",
                "to": f"{end}T23:59:59Z",
            },
        }
    ).encode()
    req = request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    try:
        with request.urlopen(req, timeout=20) as r:
            payload = json.loads(r.read())
    except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"[activity] graphql failed: {exc}", file=sys.stderr)
        return None
    try:
        weeks = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    except (KeyError, TypeError):
        print(f"[activity] unexpected payload: {payload}", file=sys.stderr)
        return None
    counts: list[int] = []
    for w in weeks:
        for d in w["contributionDays"]:
            counts.append(int(d["contributionCount"]))
    return counts[-DAYS:]


def zero_contributions() -> list[int]:
    """Return a flat zero array used when no token is available locally.

    This produces a clean empty baseline chart rather than seeded fake data
    that would show misleading numbers like '2181 contributions'.
    """
    return [0] * DAYS


def smooth(counts: list[float], window: int = 3) -> list[float]:
    """Symmetric moving average so spikes don't dominate the curve."""
    out: list[float] = []
    for i in range(len(counts)):
        lo = max(0, i - window // 2)
        hi = min(len(counts), i + window // 2 + 1)
        seg = counts[lo:hi]
        out.append(sum(seg) / len(seg))
    return out


def catmull_path(points: list[tuple[float, float]]) -> str:
    if not points:
        return ""
    parts = [f"M {points[0][0]:.2f},{points[0][1]:.2f}"]
    for i in range(1, len(points)):
        p0 = points[i - 1]
        p1 = points[i]
        p_prev = points[i - 2] if i >= 2 else p0
        p_next = points[i + 1] if i + 1 < len(points) else p1
        c1x = p0[0] + (p1[0] - p_prev[0]) / 6
        c1y = p0[1] + (p1[1] - p_prev[1]) / 6
        c2x = p1[0] - (p_next[0] - p0[0]) / 6
        c2y = p1[1] - (p_next[1] - p0[1]) / 6
        parts.append(f"C {c1x:.2f},{c1y:.2f} {c2x:.2f},{c2y:.2f} {p1[0]:.2f},{p1[1]:.2f}")
    return " ".join(parts)


def build_svg(counts: list[int], palette: dict[str, str]) -> str:
    primary = palette["primary"]
    dark = palette["dark"]
    light = palette["light"]
    p_rgb = hex_to_rgb(primary)
    d_rgb = hex_to_rgb(dark)
    l_rgb = hex_to_rgb(light)

    bg_fill = mix(d_rgb, p_rgb, 0.06)
    stroke = mix(d_rgb, p_rgb, 0.4)

    smoothed = smooth([float(c) for c in counts], window=5)
    max_c = max(max(smoothed), 1.0)

    plot_w = WIDTH - 2 * PAD_X
    plot_h = HEIGHT - PAD_TOP - PAD_BOTTOM

    n = len(smoothed)
    points: list[tuple[float, float]] = []
    for i, c in enumerate(smoothed):
        x = PAD_X + (i / max(n - 1, 1)) * plot_w
        y = PAD_TOP + plot_h - (c / max_c) * plot_h
        points.append((x, y))

    line_path = catmull_path(points)
    first_x = points[0][0]
    last_x = points[-1][0]
    base_y = PAD_TOP + plot_h
    area_path = f"{line_path} L {last_x:.2f},{base_y:.2f} L {first_x:.2f},{base_y:.2f} Z"

    # peak marker
    peak_i = max(range(n), key=lambda i: smoothed[i])
    px, py = points[peak_i]

    # Approximate path length so stroke-dashoffset reveal fully covers it.
    # Manhattan-ish overshoot of the chord length is enough for a draw-in.
    approx_len = sum(
        ((points[i][0] - points[i - 1][0]) ** 2 + (points[i][1] - points[i - 1][1]) ** 2) ** 0.5
        for i in range(1, n)
    )
    dash_len = int(approx_len * 1.1) + 32

    total = sum(counts)
    has_data = total > 0
    label_text = f"{total} contributions · last {DAYS} days" if has_data else "no data · run in CI with GITHUB_TOKEN"

    start_date = date.today() - timedelta(days=DAYS - 1)

    # ── per-day hit rects with <title> tooltips ───────────────────────────────
    # Each rect covers the chart column for that day. Hovering shows
    # "YYYY-MM-DD · N contributions" as a native browser tooltip.
    # GitHub sanitises JS but leaves <title> intact inside SVG <img> tags
    # when the SVG is opened directly; in README <img> embeds the title is
    # shown by most browsers on hover.
    seg_w = (WIDTH - 2 * PAD_X) / max(n - 1, 1)
    hit_rects: list[str] = []
    for i, raw in enumerate(counts):
        d = start_date + timedelta(days=i)
        tip = f"{d.isoformat()} · {raw} contribution{'s' if raw != 1 else ''}"
        hx = PAD_X + i * seg_w - seg_w / 2
        hit_rects.append(
            f'<rect x="{hx:.1f}" y="{PAD_TOP}" width="{seg_w:.1f}" '
            f'height="{HEIGHT - PAD_TOP - PAD_BOTTOM}" fill="transparent" cursor="crosshair">'
            f'<title>{tip}</title></rect>'
        )
    hit_layer = "\n  ".join(hit_rects)

    # ── animated cursor sweep ─────────────────────────────────────────────────
    # A vertical line that sweeps from left to right over 3 s after the draw-in
    # animation finishes. Gives the graph a sense of motion / "reading" the data.
    cursor_line = (
        f'<line x1="{PAD_X:.1f}" y1="{PAD_TOP}" x2="{PAD_X:.1f}" y2="{HEIGHT - PAD_BOTTOM}" '
        f'stroke="{primary}" stroke-width="1.2" stroke-dasharray="3 3" opacity="0.6">'
        f'<animate attributeName="x1" from="{PAD_X:.1f}" to="{WIDTH - PAD_X:.1f}" '
        f'dur="3s" begin="2.6s" fill="freeze"/>'
        f'<animate attributeName="x2" from="{PAD_X:.1f}" to="{WIDTH - PAD_X:.1f}" '
        f'dur="3s" begin="2.6s" fill="freeze"/>'
        f'<animate attributeName="opacity" from="0.6" to="0" dur="0.6s" begin="5.5s" fill="freeze"/>'
        f'</line>'
    )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" width="100%" preserveAspectRatio="xMidYMid meet" role="img" aria-label="contribution flow for {USERNAME}">
  <defs>
    <linearGradient id="areaGrad" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0%" stop-color="{primary}" stop-opacity="0.55"/>
      <stop offset="60%" stop-color="{primary}" stop-opacity="0.18"/>
      <stop offset="100%" stop-color="{primary}" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="lineGrad" x1="0" x2="1" y1="0" y2="0">
      <stop offset="0%" stop-color="{primary}" stop-opacity="0.55"/>
      <stop offset="50%" stop-color="{primary}" stop-opacity="1"/>
      <stop offset="100%" stop-color="{mix(p_rgb, l_rgb, 0.25)}" stop-opacity="1"/>
    </linearGradient>
  </defs>

  <rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{HEIGHT - 1}" rx="8" fill="{bg_fill}" stroke="{stroke}" stroke-width="0.8"/>

  <path d="{area_path}" fill="url(#areaGrad)">
    <animate attributeName="opacity" from="0" to="1" dur="2.5s" fill="freeze" begin="0.3s"/>
  </path>

  <path d="{line_path}" fill="none" stroke="url(#lineGrad)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
        stroke-dasharray="{dash_len}" stroke-dashoffset="{dash_len}">
    <animate attributeName="stroke-dashoffset" from="{dash_len}" to="0" dur="2.5s" fill="freeze" begin="0s"/>
  </path>

  <circle cx="{px:.2f}" cy="{py:.2f}" r="0" fill="{primary}" stroke="{light}" stroke-width="1.2">
    <animate attributeName="r" values="0;4;3" keyTimes="0;0.6;1" dur="0.6s" begin="2.4s" fill="freeze"/>
  </circle>

  {cursor_line}

  <!-- per-day hover tooltips (browser-native <title>) -->
  {hit_layer}

  <text x="{WIDTH - PAD_X}" y="{HEIGHT - 6}" text-anchor="end" font-size="11"
        font-family="JetBrains Mono, Fira Code, ui-monospace, monospace" fill="{light}" opacity="0">
    {label_text}
    <animate attributeName="opacity" from="0" to="0.55" dur="0.8s" begin="2.6s" fill="freeze"/>
  </text>
</svg>
'''



def main() -> int:
    palette = load_palette()
    counts = fetch_contributions(USERNAME)
    if counts is None:
        print("[activity] no GITHUB_TOKEN — using zero baseline (run in CI for real data)", file=sys.stderr)
        counts = zero_contributions()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(build_svg(counts, palette))
    total = sum(counts)
    print(f"[activity] wrote {OUT_PATH} (days={len(counts)}, total={total}, max={max(counts)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
