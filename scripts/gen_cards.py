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
from pathlib import Path
from urllib import error, request

ROOT = Path(__file__).resolve().parents[1]
PALETTE_PATH = ROOT / "palette.json"
ASSETS = ROOT / "assets"

USERNAME = os.environ.get("USERNAME") or os.environ.get("GITHUB_REPOSITORY_OWNER") or "Wint3rNight"
TOKEN = os.environ.get("GITHUB_TOKEN")
FEATURED_REPOS = ["Heliora", "Zenith", "Tinyforge", "BehaveYourself"]

# GitHub's language colors for a few we care about; falls back to primary palette.
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
    "Cuda": "#3A4E3A",
    "Java": "#b07219",
    "Rust": "#dea584",
    "Go": "#00ADD8",
}


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
    owned = [r for r in repos if not r.get("fork")]
    total_stars = sum(r.get("stargazers_count", 0) or 0 for r in owned)
    total_forks = sum(r.get("forks_count", 0) or 0 for r in owned)

    lang_count: dict[str, int] = {}
    for r in owned:
        lng = r.get("language")
        if not lng:
            continue
        lang_count[lng] = lang_count.get(lng, 0) + 1
    top_langs = sorted(lang_count.items(), key=lambda kv: kv[1], reverse=True)[:5]
    total_lang = sum(v for _, v in top_langs) or 1
    top_langs_pct = [(name, v, v * 100.0 / total_lang) for name, v in top_langs]

    return {
        "public_repos": user.get("public_repos", 0),
        "followers": user.get("followers", 0),
        "following": user.get("following", 0),
        "total_stars": total_stars,
        "total_forks": total_forks,
        "top_langs": top_langs_pct,
        "owned_count": len(owned),
    }


def build_stats_card(stats: dict, palette: dict[str, str]) -> str:
    w, h = 1040, 200
    primary = palette["primary"]
    light = palette["light"]
    p_rgb = hex_to_rgb(primary)
    d_rgb = hex_to_rgb(palette["dark"])
    l_rgb = hex_to_rgb(light)
    fill = mix(d_rgb, p_rgb, 0.07)
    stroke = mix(d_rgb, p_rgb, 0.42)
    muted = mix(d_rgb, l_rgb, 0.5)

    metrics = [
        ("public repos", str(stats["public_repos"])),
        ("total stars", str(stats["total_stars"])),
        ("followers", str(stats["followers"])),
        ("forks earned", str(stats["total_forks"])),
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

    # language bar
    bar_y = 150
    bar_x = 40
    bar_w = w - 80
    bar_h = 14
    bar_segments: list[str] = []
    legend_parts: list[str] = []
    cursor = 0.0
    for i, (name, _count, pct) in enumerate(stats["top_langs"]):
        seg_w = bar_w * pct / 100.0
        color = LANG_COLORS.get(name, mix(d_rgb, p_rgb, 0.5 + i * 0.08))
        bar_segments.append(
            f'<rect x="{bar_x + cursor:.2f}" y="{bar_y}" width="{seg_w:.2f}" height="{bar_h}" fill="{color}"/>'
        )
        legend_x = bar_x + i * (bar_w / max(len(stats["top_langs"]), 1))
        legend_parts.append(
            f'<g transform="translate({legend_x:.0f} {bar_y + 32})" font-family="JetBrains Mono, Fira Code, ui-monospace, monospace">'
            f'<circle cx="6" cy="-4" r="5" fill="{color}"/>'
            f'<text x="18" y="0" font-size="11" fill="{light}" opacity="0.9">{esc(name)} <tspan fill="{muted}">{pct:.0f}%</tspan></text>'
            f'</g>'
        )
        cursor += seg_w

    if not stats["top_langs"]:
        bar_segments.append(
            f'<rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" fill="{stroke}"/>'
        )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="100%" preserveAspectRatio="xMidYMid meet" role="img" aria-label="stats summary for {USERNAME}">
  <rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="10" fill="{fill}" stroke="{stroke}" stroke-width="1"/>
  <text x="24" y="32" font-size="13" font-family="JetBrains Mono, Fira Code, ui-monospace, monospace" fill="{primary}" font-weight="700">// {esc(USERNAME)}</text>
  <text x="{w - 24}" y="32" font-size="11" font-family="JetBrains Mono, Fira Code, ui-monospace, monospace" fill="{muted}" text-anchor="end">// regenerated weekly</text>
  {''.join(metric_parts)}
  <text x="{bar_x}" y="{bar_y - 8}" font-size="12" font-family="JetBrains Mono, Fira Code, ui-monospace, monospace" fill="{muted}">most-used languages</text>
  <g>
    <clipPath id="barClip"><rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" rx="4"/></clipPath>
    <g clip-path="url(#barClip)">{''.join(bar_segments)}</g>
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
    print(f"[cards] wrote {path}  ({stats['public_repos']} repos, {stats['total_stars']}★)")
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
