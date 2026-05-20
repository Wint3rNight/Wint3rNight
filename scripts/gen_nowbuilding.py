"""Generate the 'now building' card.

Fetches the most recent push event from the public events API (no token
required) and renders a card showing repo name, commit message, and time
elapsed. Falls back to a placeholder when no events are found.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, request

ROOT = Path(__file__).resolve().parents[1]
PALETTE_PATH = ROOT / "palette.json"
OUT_PATH = ROOT / "assets" / "nowbuilding.svg"

USERNAME = os.environ.get("USERNAME") or os.environ.get("GITHUB_REPOSITORY_OWNER") or "Wint3rNight"
TOKEN = os.environ.get("GITHUB_TOKEN")


def load_palette() -> dict[str, str]:
    if PALETTE_PATH.exists():
        return json.loads(PALETTE_PATH.read_text())
    return {"primary": "#8658E3", "dark": "#1A1A1A", "light": "#DADADA"}


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def mix(a: tuple, b: tuple, t: float) -> str:
    return "#{:02X}{:02X}{:02X}".format(
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


def esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def gh_get(path: str):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": f"{USERNAME}-profile"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = request.Request(f"https://api.github.com{path}", headers=headers)
    try:
        with request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"[nowbuilding] GET {path} failed: {exc}", file=sys.stderr)
        return None


def time_ago(iso: str) -> str:
    try:
        created = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - created
        s = int(delta.total_seconds())
        if s < 60:
            return "just now"
        if s < 3600:
            return f"{s // 60}m ago"
        if s < 86400:
            return f"{s // 3600}h ago"
        return f"{delta.days}d ago"
    except (ValueError, TypeError):
        return "recently"


def fetch_latest_push() -> dict | None:
    events = gh_get(f"/users/{USERNAME}/events/public?per_page=50")
    if not isinstance(events, list):
        return None
    for ev in events:
        if ev.get("type") == "PushEvent":
            commits = (ev.get("payload") or {}).get("commits") or []
            if not commits:
                continue
            msg = commits[-1].get("message", "").split("\n")[0][:72]
            repo = ev["repo"]["name"].split("/", 1)[-1]
            ago = time_ago(ev.get("created_at", ""))
            return {"repo": repo, "message": msg, "ago": ago}
    return None


def build_card(data: dict | None, palette: dict[str, str]) -> str:
    w, h = 1040, 100
    primary = palette["primary"]
    light = palette["light"]
    p_rgb = hex_to_rgb(primary)
    d_rgb = hex_to_rgb(palette["dark"])
    l_rgb = hex_to_rgb(light)
    fill = mix(d_rgb, p_rgb, 0.07)
    stroke = mix(d_rgb, p_rgb, 0.42)
    muted = mix(d_rgb, l_rgb, 0.5)

    if data:
        repo = esc(data["repo"])
        message = esc(data["message"])
        ago = esc(data["ago"])
    else:
        repo = USERNAME
        message = "no recent push events found"
        ago = "—"

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="100%" preserveAspectRatio="xMidYMid meet" role="img" aria-label="now building">
  <rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="10" fill="{fill}" stroke="{stroke}" stroke-width="1"/>

  <!-- pulsing live dot -->
  <circle cx="28" cy="50" r="6" fill="{primary}">
    <animate attributeName="r" values="5;7;5" dur="2s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="1;0.5;1" dur="2s" repeatCount="indefinite"/>
  </circle>

  <!-- label -->
  <text x="44" y="42" font-size="11" fill="{muted}" font-family="JetBrains Mono, Fira Code, ui-monospace, monospace">now building</text>

  <!-- repo name -->
  <text x="44" y="62" font-size="18" font-weight="700" fill="{light}" font-family="JetBrains Mono, Fira Code, ui-monospace, monospace">{repo}</text>

  <!-- commit message -->
  <text x="44" y="82" font-size="12" fill="{muted}" font-family="JetBrains Mono, Fira Code, ui-monospace, monospace">{message}</text>

  <!-- time ago (right-aligned) -->
  <text x="{w - 28}" y="55" font-size="24" font-weight="700" fill="{primary}" text-anchor="end" font-family="JetBrains Mono, Fira Code, ui-monospace, monospace">{ago}</text>
</svg>
'''


def main() -> int:
    palette = load_palette()
    data = fetch_latest_push()
    if data:
        print(f"[nowbuilding] {data['repo']} · {data['message'][:40]} · {data['ago']}")
    else:
        print("[nowbuilding] no push events found, writing placeholder", file=sys.stderr)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(build_card(data, palette))
    print(f"[nowbuilding] wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
