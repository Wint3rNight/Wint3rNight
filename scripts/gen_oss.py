"""Generate the upstream open-source contributions card.

Everything on this card comes from one GitHub search query — PRs authored
by USERNAME, anywhere. Rows are grouped by upstream project, sorted so
merged work leads, and each row carries the project's star count so the
reach of a contribution is visible without summing stars into a single
inflated headline number.

PRs against the user's own repos are filtered out; only genuine upstream
work counts. Run with USERNAME and (in CI) GITHUB_TOKEN in the
environment. Without a token the search API still answers, just at a
lower rate limit — and if the network is unavailable the card degrades
to an empty state rather than failing the build.
"""

import json
import os
import sys
from pathlib import Path
from urllib import error, parse, request

ROOT = Path(__file__).resolve().parents[1]
PALETTE_PATH = ROOT / "palette.json"
OUT_PATH = ROOT / "assets" / "oss.svg"

# Deliberately NOT reading $USERNAME: on Linux and macOS that's the login
# name, so a local run silently queries a stranger's GitHub account and
# renders their contributions onto this card. GITHUB_REPOSITORY_OWNER is
# set automatically in every Actions run; GH_USER is the local override.
USERNAME = os.environ.get("GH_USER") or os.environ.get("GITHUB_REPOSITORY_OWNER") or "Wint3rNight"
TOKEN = os.environ.get("GITHUB_TOKEN")

# Hand-written one-liners. API PR titles are inconsistent in how much they
# explain — "layers: NV per-viewport array count VUs" says little to a
# reader who isn't already in that codebase. Any project without an entry
# here falls back to its first PR title, so new contributions render
# without needing a code change.
PROJECT_NOTES = {
    "KhronosGroup/glslang": "constant folding for hyperbolic + bit-cast builtins, bit-identical to the SPIR-V back end",
    "KhronosGroup/Vulkan-ValidationLayers": "draw-time validation checks — +104 VUIDs covered across 678 tests, 0 regressions",
    "google/highway": "IndexOfMin / IndexOfMax for hwy/contrib/algo, plus a 2x unroll",
    "ggml-org/llama.cpp": "CUDA backend — f16 support for OUT_PROD",
    "NVIDIA/raft": "RAFT_LOG_TRACE_VEC fix after the rapids-logger migration",
    "shadps4-emu/shadPS4": "shader recompiler — 10_11_11 unorm/snorm/uint/sint number formats",
}

WIDTH = 1100
ROW_H = 40
ROWS_TOP = 140
PAD_X = 40
CHIP_X = 460          # fixed column so state chips line up under each other
MAX_ROWS = 8          # beyond this the card gets taller than it earns


# --- HTTP -------------------------------------------------------------------

def gh_get(url: str, default):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{USERNAME}-profile-generator",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    try:
        req = request.Request(url, headers=headers)
        with request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"[oss] GET {url} failed: {exc}", file=sys.stderr)
        return default


def fetch_upstream_prs(username: str) -> list[dict] | None:
    """Every PR the user has authored outside their own repos.

    `pull_request.merged_at` comes back inside the search payload, so
    merged-vs-open needs no follow-up request per PR.
    """
    query = parse.urlencode({"q": f"author:{username} type:pr", "per_page": 100, "advanced_search": "true"})
    payload = gh_get(f"https://api.github.com/search/issues?{query}", None)
    if not payload or "items" not in payload:
        return None

    prs: list[dict] = []
    for item in payload["items"]:
        full_name = item.get("repository_url", "").split("/repos/")[-1]
        owner = full_name.split("/")[0]
        if owner.lower() == username.lower():
            continue  # own repo — not an upstream contribution
        prs.append(
            {
                "repo": full_name,
                "number": item.get("number"),
                "title": item.get("title", ""),
                "merged": bool((item.get("pull_request") or {}).get("merged_at")),
            }
        )
    return prs


def group_by_repo(prs: list[dict]) -> list[dict]:
    """Collapse PRs into one entry per upstream project, merged work first."""
    grouped: dict[str, dict] = {}
    for pr in prs:
        entry = grouped.setdefault(
            pr["repo"], {"repo": pr["repo"], "merged": 0, "open": 0, "numbers": [], "first_title": pr["title"]}
        )
        entry["merged" if pr["merged"] else "open"] += 1
        entry["numbers"].append(pr["number"])

    for entry in grouped.values():
        meta = gh_get(f"https://api.github.com/repos/{entry['repo']}", {}) or {}
        entry["stars"] = meta.get("stargazers_count", 0)
        entry["numbers"].sort()

    # Depth of contribution leads, then reach: two merged PRs into glslang
    # outranks one into a repo with more stars.
    return sorted(grouped.values(), key=lambda e: (-e["merged"], -e["stars"]))


def upstream_by_repo() -> dict[str, dict[str, int]]:
    """Per-project merged/open counts, keyed by "owner/repo".

    Skips the star lookups that group_by_repo does — callers that only
    need counts pay for one search request, not one per project.
    """
    prs = fetch_upstream_prs(USERNAME)
    if prs is None:
        return {}
    out: dict[str, dict[str, int]] = {}
    for pr in prs:
        entry = out.setdefault(pr["repo"], {"merged": 0, "open": 0})
        entry["merged" if pr["merged"] else "open"] += 1
    return out


def upstream_summary() -> dict:
    """Counts for other generators to reuse (the stats card wants `merged`)."""
    prs = fetch_upstream_prs(USERNAME)
    if prs is None:
        return {"merged": None, "open": None, "repos": []}
    return {
        "merged": sum(1 for p in prs if p["merged"]),
        "open": sum(1 for p in prs if not p["merged"]),
        "repos": sorted({p["repo"] for p in prs}),
    }


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


def fmt_stars(n: int) -> str:
    if n >= 10_000:
        return f"{n / 1000:.0f}k"
    if n >= 1000:
        return f"{n / 1000:.1f}k"
    return str(n)


# --- rendering --------------------------------------------------------------

MONO = "JetBrains Mono, Fira Code, ui-monospace, monospace"


def build_card(repos: list[dict], summary: dict, palette: dict[str, str]) -> str:
    rows = repos[:MAX_ROWS]
    overflow = len(repos) - len(rows)
    # An overflow note gets its own half-height row so dropped projects are
    # visible rather than silently missing.
    height = ROWS_TOP + max(len(rows), 1) * ROW_H + (20 if overflow else 0) + 12

    primary = palette["primary"]
    light = palette["light"]
    p_rgb = hex_to_rgb(primary)
    d_rgb = hex_to_rgb(palette["dark"])
    l_rgb = hex_to_rgb(light)
    fill = mix(d_rgb, p_rgb, 0.07)
    stroke = mix(d_rgb, p_rgb, 0.42)
    muted = mix(d_rgb, l_rgb, 0.5)

    # ── metric strip: same treatment as the stats card ────────────────
    def dash(v):
        return "—" if v is None else str(v)

    metrics = [
        ("merged upstream", dash(summary["merged"])),
        ("in review", dash(summary["open"])),
        ("projects", dash(len(repos)) if summary["merged"] is not None else "—"),
    ]
    metric_y = 78
    metric_w = (WIDTH - 2 * PAD_X) // len(metrics)
    parts: list[str] = []
    for i, (label, value) in enumerate(metrics):
        cx = PAD_X + metric_w * i + metric_w / 2
        parts.append(
            f'<g text-anchor="middle" font-family="{MONO}">'
            f'<text x="{cx:.0f}" y="{metric_y}" font-size="36" font-weight="700" fill="{light}">{value}</text>'
            f'<text x="{cx:.0f}" y="{metric_y + 24}" font-size="12" fill="{muted}">{label}</text>'
            f'</g>'
        )
        if i < len(metrics) - 1:
            sep_x = PAD_X + metric_w * (i + 1)
            parts.append(
                f'<line x1="{sep_x}" y1="{metric_y - 30}" x2="{sep_x}" y2="{metric_y + 28}" stroke="{stroke}" stroke-width="1"/>'
            )

    parts.append(
        f'<line x1="{PAD_X}" y1="124" x2="{WIDTH - PAD_X}" y2="124" stroke="{stroke}" stroke-width="1" opacity="0.7"/>'
    )

    # ── one row per upstream project ──────────────────────────────────
    if not rows:
        parts.append(
            f'<text x="{PAD_X + 6}" y="{ROWS_TOP + 22}" font-size="13" fill="{muted}" font-family="{MONO}">'
            f'// upstream data unavailable — regenerate with network access</text>'
        )

    for i, entry in enumerate(rows):
        top = ROWS_TOP + i * ROW_H
        has_merged = entry["merged"] > 0

        pip = (
            f'<circle cx="{PAD_X + 6}" cy="{top + 12}" r="4.5" fill="{primary}"/>'
            if has_merged
            else f'<circle cx="{PAD_X + 6}" cy="{top + 12}" r="4.5" fill="none" stroke="{muted}" stroke-width="1.4"/>'
        )

        # Spacing via dx, not space characters: SVG collapses whitespace runs,
        # and U+00A0 renders zero-width in parts of this font stack — both
        # give "2 merged·1 in review" with the separator jammed in.
        chips: list[str] = []
        if entry["merged"]:
            chips.append(f'<tspan fill="{primary}">{entry["merged"]} merged</tspan>')
        if entry["open"]:
            sep = f'<tspan fill="{muted}" dx="7">·</tspan>' if chips else ""
            chips.append(f'{sep}<tspan fill="{muted}" dx="7">{entry["open"]} in review</tspan>')

        note = PROJECT_NOTES.get(entry["repo"]) or truncate(entry["first_title"], 90)
        refs = " ".join(f"#{n}" for n in entry["numbers"])

        parts.append(
            f'<g font-family="{MONO}">'
            f'{pip}'
            f'<text x="{PAD_X + 24}" y="{top + 17}" font-size="14" font-weight="700" fill="{light}">{esc(entry["repo"])}</text>'
            f'<text x="{CHIP_X}" y="{top + 17}" font-size="12">{"".join(chips)}</text>'
            f'<text x="{WIDTH - PAD_X}" y="{top + 17}" font-size="12" text-anchor="end" fill="{light}" opacity="0.85">'
            f'<tspan fill="{primary}">★</tspan> {fmt_stars(entry["stars"])}</text>'
            f'<text x="{PAD_X + 24}" y="{top + 34}" font-size="11.5" fill="{muted}">'
            f'<tspan fill="{primary}" opacity="0.8">{refs}</tspan><tspan dx="10">{esc(note)}</tspan></text>'
            f'</g>'
        )

    if overflow:
        plural = "s" if overflow != 1 else ""
        parts.append(
            f'<text x="{PAD_X + 24}" y="{ROWS_TOP + len(rows) * ROW_H + 12}" font-size="11.5" '
            f'fill="{muted}" font-family="{MONO}">+ {overflow} more project{plural}</text>'
        )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {height}" width="100%" preserveAspectRatio="xMidYMid meet" role="img" aria-label="upstream open source contributions by {USERNAME}">
  <rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{height - 1}" rx="10" fill="{fill}" stroke="{stroke}" stroke-width="1"/>
  {''.join(parts)}
</svg>
'''


def main() -> int:
    palette = load_palette()
    prs = fetch_upstream_prs(USERNAME)

    if prs is None:
        # A transient search-API failure must not replace a good card with an
        # empty one — the weekly workflow auto-commits whatever is on disk.
        if OUT_PATH.exists():
            print("[oss] search unavailable — keeping the existing card", file=sys.stderr)
            return 0
        print("[oss] search unavailable and no card on disk — writing empty state", file=sys.stderr)
        repos: list[dict] = []
        summary = {"merged": None, "open": None}
    else:
        repos = group_by_repo(prs)
        summary = {
            "merged": sum(1 for p in prs if p["merged"]),
            "open": sum(1 for p in prs if not p["merged"]),
        }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(build_card(repos, summary, palette))
    print(f"[oss] wrote {OUT_PATH}  ({summary['merged']} merged, {summary['open']} in review, {len(repos)} projects)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
