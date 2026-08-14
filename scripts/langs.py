"""Measure the languages actually written, rather than repo bulk.

GitHub's /languages endpoint reports the byte size of everything on a
repo's default branch, which turned out to be a poor proxy for authored
work. Two distortions dominated:

  - Vendored single-header libraries counted in full. vk_mem_alloc.h,
    stb_image.h and stb_image_write.h together are ~1.12 MB, roughly 60%
    of Heliora and ~29% of the whole chart, none of it authored here.
  - Forks are skipped entirely, so every upstream contribution — the
    merged glslang work, the highway SIMD patch, the llama.cpp CUDA
    change — counted as nothing.

This module walks each owned repo's tree, skipping vendored and
generated paths, and adds the additions from pull requests authored
against upstream repositories. The result is a picture of what was
written, including work that lives in someone else's repository.
"""

import json
import os
import sys
from urllib import error, parse, request

USERNAME = os.environ.get("GH_USER") or os.environ.get("GITHUB_REPOSITORY_OWNER") or "Wint3rNight"
TOKEN = os.environ.get("GITHUB_TOKEN")

# Languages this profile is about. An allowlist rather than a denylist so
# that a future side project in some unrelated web stack can't quietly
# take over the chart the way monastery360's 671 KB of HTML did.
KEEP = {
    "C", "C++", "Cuda", "GLSL", "HLSL", "ShaderLab", "SPIR-V",
    "Python", "C#", "CMake", "Shell", "Make", "Rust", "Zig", "Assembly",
}

EXT_LANG = {
    ".c": "C", ".h": "C",  # .h is remapped to C++ below when the repo has C++ sources
    ".cpp": "C++", ".cc": "C++", ".cxx": "C++", ".hpp": "C++", ".hh": "C++",
    ".hxx": "C++", ".inl": "C++", ".ipp": "C++",
    ".cu": "Cuda", ".cuh": "Cuda",
    ".glsl": "GLSL", ".vert": "GLSL", ".frag": "GLSL", ".comp": "GLSL",
    ".geom": "GLSL", ".tesc": "GLSL", ".tese": "GLSL", ".mesh": "GLSL",
    ".task": "GLSL", ".rgen": "GLSL", ".rchit": "GLSL", ".rmiss": "GLSL",
    ".hlsl": "HLSL", ".fx": "HLSL", ".hlsli": "HLSL",
    ".shader": "ShaderLab", ".cginc": "ShaderLab",
    ".cs": "C#", ".py": "Python", ".rs": "Rust", ".zig": "Zig",
    ".sh": "Shell", ".bash": "Shell", ".zsh": "Shell",
    ".cmake": "CMake", ".s": "Assembly", ".asm": "Assembly",
}

# Vendored or generated. Matched against the lowercased path.
VENDOR_DIRS = (
    "vendor/", "third_party/", "thirdparty/", "external/", "extern/",
    "deps/", "dependencies/", "subprojects/", "node_modules/", "build/",
    ".venv/", "venv/", "dist/", "generated/",
)
VENDOR_FILES = (
    "vk_mem_alloc.h", "stb_image.h", "stb_image_write.h", "stb_truetype.h",
    "stb_rect_pack.h", "tiny_obj_loader.h", "tiny_gltf.h", "json.hpp",
    "glad.c", "glad.h", "khrplatform.h", "volk.c", "volk.h", "imgui.cpp",
    "imgui.h", "imgui_draw.cpp", "imgui_widgets.cpp", "imgui_tables.cpp",
    "imgui_demo.cpp", "catch.hpp", "doctest.h", "miniaudio.h",
)
# Compiled shader output is not authored source.
SKIP_EXT = (".spv",)

# A repository is counted only when its own dominant language is one of
# these. That keeps the chart about systems and graphics work without a
# hand-maintained list of repositories to exclude — a future side project
# in some other stack drops out on its own, which is how 671 KB of HTML
# came to outweigh every CUDA kernel here.
CORE_LANGS = {"C", "C++", "Cuda", "GLSL", "HLSL", "ShaderLab", "Python", "C#"}

# Only used to recognise what a repository mostly is. These never appear
# in the output, but without them a web project looks like whatever small
# amount of Python it happens to contain.
WEB_EXT = {
    ".html": "HTML", ".htm": "HTML", ".css": "CSS", ".scss": "CSS",
    ".sass": "CSS", ".less": "CSS", ".js": "JavaScript", ".jsx": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript", ".vue": "Vue", ".svelte": "Svelte",
    ".php": "PHP", ".rb": "Ruby",
}


def gh(path: str, default):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": f"{USERNAME}-profile"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    try:
        req = request.Request(f"https://api.github.com{path}", headers=headers)
        with request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"[langs] GET {path} failed: {exc}", file=sys.stderr)
        return default


def is_vendored(path: str) -> bool:
    low = path.lower()
    if any(d in low for d in VENDOR_DIRS):
        return True
    return low.rsplit("/", 1)[-1] in VENDOR_FILES


def classify(path: str, cxx_repo: bool) -> str | None:
    low = path.lower()
    if low.endswith(SKIP_EXT):
        return None
    if low.rsplit("/", 1)[-1] == "cmakelists.txt":
        return "CMake"
    ext = low[low.rfind("."):] if "." in low.rsplit("/", 1)[-1] else ""
    lang = EXT_LANG.get(ext)
    # Linguist reports bare .h as C, which misfiled Heliora's C++17 headers
    # as ~839 KB of C. In a repo that has C++ sources, .h is a C++ header.
    if lang == "C" and ext == ".h" and cxx_repo:
        return "C++"
    return lang


def _repo_languages(name: str) -> tuple[dict[str, int], dict[str, int]]:
    """Return (everything classified, allowlisted only) for one repository."""
    tree = gh(f"/repos/{USERNAME}/{name}/git/trees/HEAD?recursive=1", {})
    blobs = (tree or {}).get("tree") or []
    if tree.get("truncated"):
        print(f"[langs] {name}: tree truncated, counts are partial", file=sys.stderr)

    paths = [b["path"] for b in blobs if b.get("type") == "blob"]
    cxx_repo = any(p.lower().endswith((".cpp", ".cc", ".cxx")) for p in paths)

    everything: dict[str, int] = {}
    allowed: dict[str, int] = {}
    for b in blobs:
        if b.get("type") != "blob" or is_vendored(b["path"]):
            continue
        path = b["path"].lower()
        ext = path[path.rfind("."):] if "." in path.rsplit("/", 1)[-1] else ""
        lang = classify(b["path"], cxx_repo) or WEB_EXT.get(ext)
        if not lang:
            continue
        size = b.get("size", 0)
        everything[lang] = everything.get(lang, 0) + size
        if lang in KEEP:
            allowed[lang] = allowed.get(lang, 0) + size
    return everything, allowed


def owned_repo_bytes() -> dict[str, int]:
    """Authored bytes across owned repositories that are systems/graphics work."""
    repos = gh(f"/users/{USERNAME}/repos?per_page=100&type=owner&sort=updated", []) or []
    if not isinstance(repos, list):
        return {}

    totals: dict[str, int] = {}
    for repo in repos:
        if repo.get("fork"):
            continue
        name = repo["name"]
        # The profile repo renders this chart; counting its own generator
        # scripts would let the tooling inflate the stats it produces.
        if name.lower() == USERNAME.lower():
            continue
        everything, allowed = _repo_languages(name)
        if not everything:
            continue
        dominant = max(everything, key=everything.get)
        if dominant not in CORE_LANGS:
            print(f"[langs] skipping {name} (mostly {dominant})", file=sys.stderr)
            continue
        for lang, size in allowed.items():
            totals[lang] = totals.get(lang, 0) + size
    return totals


def upstream_pr_bytes() -> dict[str, int]:
    """Additions from pull requests authored against other people's repos.

    Additions are line counts, not bytes, so they're scaled to a rough
    byte-equivalent before being merged with the tree totals. The point is
    that upstream work registers at all — it was previously invisible.
    """
    query = parse.urlencode(
        {"q": f"author:{USERNAME} type:pr", "per_page": 100, "advanced_search": "true"}
    )
    payload = gh(f"/search/issues?{query}", None)
    if not payload or "items" not in payload:
        return {}

    AVG_LINE_BYTES = 34
    totals: dict[str, int] = {}
    for item in payload["items"]:
        full = item.get("repository_url", "").split("/repos/")[-1]
        if full.split("/")[0].lower() == USERNAME.lower():
            continue  # own repo, already counted via its tree
        files = gh(f"/repos/{full}/pulls/{item['number']}/files?per_page=100", [])
        if not isinstance(files, list):
            continue
        for f in files:
            lang = classify(f.get("filename", ""), cxx_repo=True)
            if lang:
                totals[lang] = totals.get(lang, 0) + f.get("additions", 0) * AVG_LINE_BYTES
    return totals


def language_totals(apply_filter: bool = True) -> dict[str, int]:
    totals = owned_repo_bytes()
    for lang, n in upstream_pr_bytes().items():
        totals[lang] = totals.get(lang, 0) + n
    if apply_filter:
        totals = {k: v for k, v in totals.items() if k in KEEP}
    return dict(sorted(totals.items(), key=lambda kv: -kv[1]))
