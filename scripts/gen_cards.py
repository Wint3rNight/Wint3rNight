"""Hand-roll the featured repo cards and the stats card.

The vercel github-readme-stats deployment goes down regularly — when it
does, every pin and stats card on a profile renders as a broken-image
icon. This script removes the dependency by talking to the GitHub REST
API directly and writing local SVGs that the README references. A weekly
workflow re-runs this against the live API so the numbers stay current.

Run with USERNAME and (in CI) GITHUB_TOKEN in the environment.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, request

ROOT = Path(__file__).resolve().parents[1]
PALETTE_PATH = ROOT / "palette.json"
ASSETS = ROOT / "assets"

USERNAME = os.environ.get("USERNAME") or os.environ.get("GITHUB_REPOSITORY_OWNER") or "Wint3rNight"
TOKEN = os.environ.get("GITHUB_TOKEN")
FEATURED_REPOS = ["Heliora", "Zenith", "Tinyforge", "BehaveYourself"]

# GitHub's language colors. Falls back to a palette-derived colour for unknowns.
LANG_COLORS = {
    "C": "#555555",
    "C++": "#f34b7d",
    "C#": "#178600",
    "Python": "#3572A5",
    "JavaScript": "#f1e05a",
    "TypeScript": "#3178c6",
    "HTML": "#e34c26",
    "CSS": "#563d7c",
    "Shell": "#89e051",
    "GLSL": "#5686a5",
    "HLSL": "#aace60",
    "CMake": "#DA3434",
    "Cuda": "#76b900",
    "CUDA": "#76b900",
    "ShaderLab": "#6f42c1",
    "Java": "#b07219",
    "Rust": "#dea584",
    "Go": "#00ADD8",
    "Wolfram Language": "#dd1100",
    "Makefile": "#427819",
    "Dockerfile": "#384d54",
    "Lua": "#000080",
    "Zig": "#ec915c",
}

TOP_LANGS_COUNT = 12  # how many languages to show in the bar + legend


# --- HTTP -------------------------------------------------------------------

def gh_get(path: str) -> dict | list:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{USERNAME}-profile-generator",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = request.Request(f"https://api.github.com{path}", headers=headers)
    with request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def safe_gh(path: str, default):
    try:
        return gh_get(path)
    except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"[cards] GET {path} failed: {exc}", file=sys.stderr)
        return default


def gh_graphql(query: str, variables: dict) -> dict | None:
    if not TOKEN:
        return None
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    try:
        with request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"[cards] graphql failed: {exc}", file=sys.stderr)
        return None


def fetch_contributions_total(username: str) -> int | None:
    """Total contributions in the trailing 12 months.

    Strategy:
    1. GraphQL (fast, exact) — only works in CI where GITHUB_TOKEN is set.
    2. REST contributions calendar scrape — public, no token needed.
       GitHub exposes a contributions calendar JSON-ish endpoint at
       /users/{user}/contributions which returns an SVG; we avoid that.
       Instead we hit the user's public events feed across the year.
       That's rate-limited to 300 public events, so it under-counts heavy
       contributors but gives a reasonable number without auth.
    """
    # --- try GraphQL first (CI path) ---
    payload = gh_graphql(
        """query($login:String!){user(login:$login){contributionsCollection{contributionCalendar{totalContributions}}}}""",
        {"login": username},
    )
    if payload:
        try:
            return int(payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"])
        except (KeyError, TypeError, ValueError):
            pass

    # --- REST fallback: public events (no auth needed) ---
    # Cap at 10 pages × 100 events = 1000 events max
    total = 0
    from datetime import datetime, timezone, timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=365)
    for page in range(1, 11):
        events = safe_gh(f"/users/{username}/events/public?per_page=100&page={page}", [])
        if not isinstance(events, list) or not events:
            break
        page_has_old = False
        for ev in events:
            created_raw = ev.get("created_at", "")
            try:
                created = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue
            if created < cutoff:
                page_has_old = True
                break
            # Count pushes by commits, everything else as 1
            if ev.get("type") == "PushEvent":
                total += len((ev.get("payload") or {}).get("commits") or [])
            else:
                total += 1
        if page_has_old:
            break
    return total if total else None


# --- helpers ----------------------------------------------------------------

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
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def truncate(s: str | None, n: int) -> str:
    if not s:
        return ""
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


# --- featured card ----------------------------------------------------------

def build_repo_card(repo: dict, palette: dict[str, str]) -> str:
    w, h = 340, 140
    primary = palette["primary"]
    light = palette["light"]
    p_rgb = hex_to_rgb(primary)
    d_rgb = hex_to_rgb(palette["dark"])
    l_rgb = hex_to_rgb(light)
    fill = mix(d_rgb, p_rgb, 0.07)
    stroke = mix(d_rgb, p_rgb, 0.42)
    muted = mix(d_rgb, l_rgb, 0.5)

    name = repo.get("name", "?")
    desc = truncate(repo.get("description"), 88) or "no description yet"
    lang = repo.get("language") or "—"
    stars = repo.get("stargazers_count", 0)
    forks = repo.get("forks_count", 0)
    lang_color = LANG_COLORS.get(lang, primary)
    error_state = repo.get("__error__")

    # repo icon (octicon "repo" simplified)
    icon = (
        f'<path d="M12 2.75A1.75 1.75 0 0 1 13.75 1h6.5c.97 0 1.75.78 1.75 1.75v17.5A1.75 1.75 0 0 1 20.25 22h-6.5A1.75 1.75 0 0 1 12 20.25V2.75zm-9 0A1.75 1.75 0 0 1 4.75 1h6.5v21h-6.5A1.75 1.75 0 0 1 3 20.25V2.75z" '
        f'transform="translate(16 16) scale(0.7)" fill="{primary}" opacity="0.95"/>'
    )

    if error_state:
        body = (
            f'<text x="16" y="64" font-size="13" fill="{muted}" font-family="JetBrains Mono, Fira Code, ui-monospace, monospace">'
            f'{esc(error_state)}</text>'
        )
    else:
        body = (
            f'<text x="16" y="64" font-size="12" fill="{muted}" font-family="JetBrains Mono, Fira Code, ui-monospace, monospace">{esc(desc)}</text>'
            f'<g transform="translate(16 {h - 22})">'
            f'<circle cx="6" cy="6" r="5.5" fill="{lang_color}"/>'
            f'<text x="20" y="10" font-size="12" fill="{light}" opacity="0.85" font-family="JetBrains Mono, Fira Code, ui-monospace, monospace">{esc(lang)}</text>'
            f'</g>'
            f'<g transform="translate({w - 16} {h - 22})">'
            f'<text x="0" y="10" font-size="12" fill="{light}" opacity="0.85" text-anchor="end" font-family="JetBrains Mono, Fira Code, ui-monospace, monospace">'
            f'<tspan fill="{primary}">★</tspan> {stars}  <tspan fill="{primary}">⑂</tspan> {forks}</text>'
            f'</g>'
        )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{esc(name)}">
  <rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="8" fill="{fill}" stroke="{stroke}" stroke-width="1"/>
  {icon}
  <text x="44" y="36" font-size="16" font-weight="700" fill="{light}" font-family="JetBrains Mono, Fira Code, ui-monospace, monospace">{esc(name)}</text>
  {body}
</svg>
'''


def write_featured(palette: dict[str, str]) -> list[str]:
    written: list[str] = []
    for name in FEATURED_REPOS:
        repo = safe_gh(f"/repos/{USERNAME}/{name}", None)
        if not repo or repo.get("message") == "Not Found":
            repo = {"name": name, "__error__": f"// repo not found: {name}"}
        path = ASSETS / f"featured-{name.lower()}.svg"
        path.write_text(build_repo_card(repo, palette))
        written.append(str(path.relative_to(ROOT)))
        print(f"[cards] wrote {path}")
    return written


# --- stats card -------------------------------------------------------------

def aggregate_stats(user: dict, repos: list[dict]) -> dict:
    """Aggregate language stats by summing raw bytes across all owned repos.

    GitHub exposes bytes-per-language via /repos/{owner}/{repo}/languages.
    Summing those gives a far more accurate picture than counting how many
    repos list a language as their primary language.
    """
    owned = [r for r in repos if not r.get("fork")]

    lang_bytes: dict[str, int] = {}
    for r in owned:
        langs = safe_gh(f"/repos/{USERNAME}/{r['name']}/languages", {})
        if not isinstance(langs, dict):
            continue
        for lang, byte_count in langs.items():
            lang_bytes[lang] = lang_bytes.get(lang, 0) + byte_count

    all_lang_count = len(lang_bytes)  # total distinct languages (for the counter)

    # Top N by bytes, percentages relative to the top-N subtotal
    sorted_langs = sorted(lang_bytes.items(), key=lambda kv: kv[1], reverse=True)
    top_langs = sorted_langs[:TOP_LANGS_COUNT]
    total_bytes = sum(v for _, v in top_langs) or 1
    top_langs_pct = [(name, b, b * 100.0 / total_bytes) for name, b in top_langs]

    created_raw = user.get("created_at")
    years_here: float | None = None
    if created_raw:
        try:
            created = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
            years_here = (datetime.now(timezone.utc) - created).days / 365.25
        except (ValueError, TypeError):
            years_here = None

    contributions = fetch_contributions_total(USERNAME)

    return {
        "public_repos": user.get("public_repos", 0),
        "languages_used": all_lang_count,
        "contributions_year": contributions,
        "years_here": years_here,
        "top_langs": top_langs_pct,
    }


def build_stats_card(stats: dict, palette: dict[str, str]) -> str:
    """Render the stats SVG.

    Card height grows by 24 px for every extra legend row beyond the first,
    so 12 languages sit cleanly in two rows of 6.
    """
    top_langs = stats["top_langs"]
    n = len(top_langs)
    per_row = 6
    legend_rows = max(1, -(-n // per_row))  # ceiling division
    w = 1040
    h = 200 + (legend_rows - 1) * 24

    primary = palette["primary"]
    light = palette["light"]
    p_rgb = hex_to_rgb(primary)
    d_rgb = hex_to_rgb(palette["dark"])
    l_rgb = hex_to_rgb(light)
    fill = mix(d_rgb, p_rgb, 0.07)
    stroke = mix(d_rgb, p_rgb, 0.42)
    muted = mix(d_rgb, l_rgb, 0.5)

    yrs = stats["years_here"]
    contrib = stats["contributions_year"]
    metrics = [
        ("public repos", str(stats["public_repos"])),
        ("contributions / year", str(contrib) if contrib is not None else "—"),
        ("languages used", str(stats["languages_used"])),
        ("years on github", f"{yrs:.1f}" if yrs is not None else "—"),
    ]
    metric_y = 78
    metric_w = (w - 80) // len(metrics)
    metric_parts: list[str] = []
    for i, (label, value) in enumerate(metrics):
        cx = 40 + metric_w * i + metric_w / 2
        metric_parts.append(
            f'<g text-anchor="middle" font-family="JetBrains Mono, Fira Code, ui-monospace, monospace">'
            f'<text x="{cx:.0f}" y="{metric_y}" font-size="36" font-weight="700" fill="{light}">{value}</text>'
            f'<text x="{cx:.0f}" y="{metric_y + 24}" font-size="12" fill="{muted}">{label}</text>'
            f'</g>'
        )
        if i < len(metrics) - 1:
            sep_x = 40 + metric_w * (i + 1)
            metric_parts.append(
                f'<line x1="{sep_x}" y1="{metric_y - 30}" x2="{sep_x}" y2="{metric_y + 28}" stroke="{stroke}" stroke-width="1"/>'
            )

    # ── language bar ──────────────────────────────────────────────
    bar_y = 150
    bar_x = 40
    bar_w = w - 80
    bar_h = 14
    bar_segments: list[str] = []
    legend_parts: list[str] = []
    cursor = 0.0
    col_w = bar_w / per_row  # width each legend column occupies

    for i, (name, _bytes, pct) in enumerate(top_langs):
        seg_w = bar_w * pct / 100.0
        color = LANG_COLORS.get(name, mix(d_rgb, p_rgb, 0.5 + i * 0.06))
        bar_segments.append(
            f'<rect x="{bar_x + cursor:.2f}" y="{bar_y}" width="{seg_w:.2f}" height="{bar_h}" fill="{color}"/>'
        )
        row = i // per_row
        col = i % per_row
        lx = bar_x + col * col_w
        ly = bar_y + 32 + row * 24
        legend_parts.append(
            f'<g transform="translate({lx:.0f} {ly:.0f})" font-family="JetBrains Mono, Fira Code, ui-monospace, monospace">'
            f'<circle cx="6" cy="-4" r="5" fill="{color}"/>'
            f'<text x="18" y="0" font-size="11" fill="{light}" opacity="0.9">{esc(name)} <tspan fill="{muted}">{pct:.0f}%</tspan></text>'
            f'</g>'
        )
        cursor += seg_w

    if not top_langs:
        bar_segments.append(
            f'<rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" fill="{stroke}"/>'
        )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="100%" preserveAspectRatio="xMidYMid meet" role="img" aria-label="stats summary for {USERNAME}">
  <rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="10" fill="{fill}" stroke="{stroke}" stroke-width="1"/>
  {''.join(metric_parts)}
  <g>
    <clipPath id="barClip"><rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" rx="4"/></clipPath>
    <g clip-path="url(#barClip)">{' '.join(bar_segments)}</g>
    <rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" rx="4" fill="none" stroke="{stroke}" stroke-width="0.6"/>
  </g>
  {''.join(legend_parts)}
</svg>
'''


def write_stats(palette: dict[str, str]) -> str:
    user = safe_gh(f"/users/{USERNAME}", {})
    repos = safe_gh(f"/users/{USERNAME}/repos?per_page=100&type=owner&sort=updated", []) or []
    if not isinstance(repos, list):
        repos = []
    stats = aggregate_stats(user, repos)
    path = ASSETS / "stats.svg"
    path.write_text(build_stats_card(stats, palette))
    print(f"[cards] wrote {path}  ({stats['public_repos']} repos, {stats['languages_used']} langs, contrib={stats['contributions_year']})")
    return str(path.relative_to(ROOT))


# --- main -------------------------------------------------------------------

def main() -> int:
    palette = load_palette()
    ASSETS.mkdir(parents=True, exist_ok=True)
    write_featured(palette)
    write_stats(palette)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
