"""Generate the hero skyline SVG from real GitHub contribution data.

Each building's height encodes one day's commits over the last 84 days
(12 weeks). Windows light up proportionally to the day's activity, so a
busy week becomes a glowing strip and a quiet week a dark silhouette.
Palette is read from palette.json so the entire profile stays cohesive.

Data source: GitHub GraphQL `contributionsCollection`, queried with the
GITHUB_TOKEN injected by the workflow. When run locally without a token
(or when the API call fails) we deterministically seed mock data from
the username so the rendered image is still meaningful and stable.
"""

import hashlib
import json
import os
import random
import sys
from datetime import date, timedelta
from pathlib import Path
from urllib import error, request

ROOT = Path(__file__).resolve().parents[1]
PALETTE_PATH = ROOT / "palette.json"
OUT_PATH = ROOT / "assets" / "skyline.svg"

USERNAME = os.environ.get("USERNAME") or os.environ.get("GITHUB_REPOSITORY_OWNER") or "Wint3rNight"
TOKEN = os.environ.get("GITHUB_TOKEN")

DAYS = 84  # 12 weeks
WIDTH = 1200
HEIGHT = 340
PAD_X = 24
PAD_BOTTOM = 28
SKY_TOP = 0


def load_palette() -> dict[str, str]:
    if PALETTE_PATH.exists():
        return json.loads(PALETTE_PATH.read_text())
    return {"primary": "#8658E3", "dark": "#1A1A1A", "light": "#DADADA"}


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> str:
    r = int(a[0] + (b[0] - a[0]) * t)
    g = int(a[1] + (b[1] - a[1]) * t)
    bl = int(a[2] + (b[2] - a[2]) * t)
    return f"#{r:02X}{g:02X}{bl:02X}"


def fetch_contributions(username: str, token: str) -> list[int] | None:
    end = date.today()
    start = end - timedelta(days=DAYS - 1)
    query = """
    query($login:String!,$from:DateTime!,$to:DateTime!){
      user(login:$login){
        contributionsCollection(from:$from,to:$to){
          contributionCalendar{ weeks{ contributionDays{ date contributionCount } } }
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
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read())
    except (error.URLError, TimeoutError) as exc:
        print(f"[skyline] GraphQL request failed: {exc}", file=sys.stderr)
        return None
    try:
        weeks = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    except (KeyError, TypeError):
        print(f"[skyline] unexpected GraphQL payload: {payload}", file=sys.stderr)
        return None
    counts: list[int] = []
    for w in weeks:
        for d in w["contributionDays"]:
            counts.append(int(d["contributionCount"]))
    return counts[-DAYS:]


def mock_contributions(username: str) -> list[int]:
    """Deterministic plausible data: weekday burst, weekend lull, occasional spikes."""
    seed = int(hashlib.sha256(username.encode()).hexdigest()[:12], 16)
    rng = random.Random(seed)
    counts: list[int] = []
    start = date.today() - timedelta(days=DAYS - 1)
    for i in range(DAYS):
        d = start + timedelta(days=i)
        weekend = d.weekday() >= 5
        base = rng.gauss(2.5, 1.8) if weekend else rng.gauss(7.0, 3.5)
        if rng.random() < 0.07:  # spike days
            base += rng.uniform(8, 16)
        counts.append(max(0, int(base)))
    return counts


def build_svg(counts: list[int], palette: dict[str, str]) -> str:
    primary = palette["primary"]
    dark = palette["dark"]
    light = palette["light"]

    p_rgb = hex_to_rgb(primary)
    d_rgb = hex_to_rgb(dark)

    max_c = max(counts) if counts else 1
    max_c = max(max_c, 1)

    plot_w = WIDTH - 2 * PAD_X
    n = len(counts)
    slot = plot_w / n
    bar_w = max(6.0, slot * 0.78)
    base_y = HEIGHT - PAD_BOTTOM
    min_h = 14
    max_h = 230

    seed = int(hashlib.sha256(USERNAME.encode()).hexdigest()[:12], 16)
    rng = random.Random(seed ^ 0xDEADBEEF)

    # Sky gradient: dark up top, slight primary tint near the horizon.
    horizon_tint = mix(d_rgb, p_rgb, 0.18)

    # Stars in the sky.
    stars = []
    star_rng = random.Random(seed ^ 0xC0FFEE)
    for _ in range(80):
        sx = star_rng.uniform(0, WIDTH)
        sy = star_rng.uniform(0, HEIGHT - PAD_BOTTOM - max_h - 6)
        r = star_rng.choice([0.6, 0.8, 1.0, 1.2])
        op = star_rng.uniform(0.35, 0.9)
        # twinkle period varies for a subtle living sky
        dur = star_rng.uniform(2.2, 5.8)
        stars.append(
            f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="{r:.2f}" fill="{light}" opacity="{op:.2f}">'
            f'<animate attributeName="opacity" values="{op:.2f};{op*0.25:.2f};{op:.2f}" '
            f'dur="{dur:.1f}s" repeatCount="indefinite"/></circle>'
        )

    # Distant building haze (parallax layer behind).
    haze = []
    haze_rng = random.Random(seed ^ 0xBADC0DE)
    cursor = 0.0
    while cursor < WIDTH:
        bw = haze_rng.uniform(28, 70)
        bh = haze_rng.uniform(40, 110)
        x = cursor
        y = base_y - bh
        fill = mix(d_rgb, p_rgb, 0.08)
        haze.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" fill="{fill}" opacity="0.55"/>')
        cursor += bw + haze_rng.uniform(2, 14)

    # Foreground buildings (one per day).
    buildings = []
    windows = []
    for i, c in enumerate(counts):
        norm = c / max_c
        h = min_h + (max_h - min_h) * (norm ** 0.85)
        x = PAD_X + i * slot + (slot - bar_w) / 2
        y = base_y - h
        buildings.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_w:.2f}" height="{h:.2f}" '
            f'fill="{dark}" stroke="{mix(d_rgb, p_rgb, 0.35)}" stroke-width="0.6"/>'
        )

        # windows: small grid inside the rectangle, lit proportional to commits
        cols = max(1, int(bar_w / 4))
        rows = max(1, int(h / 6))
        # never more than this many windows lit
        lit_target = int(min(cols * rows, max(1, c * 1.3)))
        positions = [(cc, rr) for cc in range(cols) for rr in range(rows)]
        rng.shuffle(positions)
        chosen = positions[:lit_target]
        for cc, rr in chosen:
            wx = x + 1.2 + cc * (bar_w - 2.4) / max(cols, 1)
            wy = y + 2 + rr * (h - 4) / max(rows, 1)
            ww = max(0.9, (bar_w - 2.4) / cols * 0.55)
            wh = max(1.2, (h - 4) / rows * 0.55)
            # subtle flicker on a few windows so it feels alive
            flicker = rng.random() < 0.06
            if flicker:
                dur = rng.uniform(3.0, 7.5)
                windows.append(
                    f'<rect x="{wx:.2f}" y="{wy:.2f}" width="{ww:.2f}" height="{wh:.2f}" fill="{primary}" opacity="0.95">'
                    f'<animate attributeName="opacity" values="0.95;0.2;0.95" dur="{dur:.1f}s" repeatCount="indefinite"/></rect>'
                )
            else:
                op = 0.55 + 0.4 * rng.random()
                windows.append(
                    f'<rect x="{wx:.2f}" y="{wy:.2f}" width="{ww:.2f}" height="{wh:.2f}" fill="{primary}" opacity="{op:.2f}"/>'
                )

    # Horizon line + glow.
    horizon = (
        f'<line x1="0" y1="{base_y:.1f}" x2="{WIDTH}" y2="{base_y:.1f}" '
        f'stroke="{primary}" stroke-width="1" opacity="0.55"/>'
        f'<rect x="0" y="{base_y:.1f}" width="{WIDTH}" height="{PAD_BOTTOM}" fill="url(#groundFade)"/>'
    )

    # Corner label.
    total = sum(counts)
    label = (
        f'<g font-family="JetBrains Mono, Fira Code, ui-monospace, monospace" '
        f'fill="{light}" opacity="0.55">'
        f'<text x="{PAD_X}" y="{HEIGHT - 8}" font-size="11">// wint3rnight · last {DAYS} days · {total} contributions</text>'
        f'<text x="{WIDTH - PAD_X}" y="{HEIGHT - 8}" font-size="11" text-anchor="end">v={max_c} max/day</text>'
        f'</g>'
    )

    defs = f'''
    <defs>
      <linearGradient id="sky" x1="0" x2="0" y1="0" y2="1">
        <stop offset="0%" stop-color="{dark}"/>
        <stop offset="55%" stop-color="{mix(d_rgb, p_rgb, 0.06)}"/>
        <stop offset="100%" stop-color="{horizon_tint}"/>
      </linearGradient>
      <radialGradient id="moonGlow" cx="0.82" cy="0.18" r="0.22">
        <stop offset="0%" stop-color="{light}" stop-opacity="0.55"/>
        <stop offset="60%" stop-color="{primary}" stop-opacity="0.10"/>
        <stop offset="100%" stop-color="{dark}" stop-opacity="0"/>
      </radialGradient>
      <linearGradient id="groundFade" x1="0" x2="0" y1="0" y2="1">
        <stop offset="0%" stop-color="{primary}" stop-opacity="0.18"/>
        <stop offset="100%" stop-color="{dark}" stop-opacity="0"/>
      </linearGradient>
    </defs>
    '''

    moon_cx = WIDTH * 0.82
    moon_cy = HEIGHT * 0.18
    moon = (
        f'<rect x="0" y="0" width="{WIDTH}" height="{HEIGHT}" fill="url(#moonGlow)"/>'
        f'<circle cx="{moon_cx:.1f}" cy="{moon_cy:.1f}" r="22" fill="{light}" opacity="0.92"/>'
        f'<circle cx="{moon_cx:.1f}" cy="{moon_cy:.1f}" r="22" fill="none" stroke="{primary}" stroke-opacity="0.4" stroke-width="0.8"/>'
    )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" width="100%" preserveAspectRatio="xMidYMid slice" role="img" aria-label="contribution skyline for {USERNAME}">
    {defs}
    <rect width="{WIDTH}" height="{HEIGHT}" fill="url(#sky)"/>
    {moon}
    {''.join(stars)}
    {''.join(haze)}
    {''.join(buildings)}
    {''.join(windows)}
    {horizon}
    {label}
    </svg>
    '''
    return svg


def main() -> int:
    palette = load_palette()
    counts = None
    if TOKEN:
        counts = fetch_contributions(USERNAME, TOKEN)
    if counts is None:
        counts = mock_contributions(USERNAME)
    svg = build_svg(counts, palette)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(svg)
    print(f"[skyline] wrote {OUT_PATH} ({len(counts)} days, max={max(counts)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
