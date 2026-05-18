# GitHub Profile README — Build Spec for Claude Code

## Context

Build a minimal, dynamic GitHub profile README. Aesthetic is graphics/engine-programming themed: hero skyline image at the top, one consistent color palette throughout, a few animated accents, no clutter. Output is everything needed to push to `github.com/<username>/<username>`.

I'll handle: creating the GitHub repo, pushing, enabling workflow permissions, and triggering the first workflow runs. You handle: every file in this repo, themed consistently, ready to commit.

---

## Operating principles

1. **Ask for all missing inputs in a single consolidated message at the start.** Don't drip questions out one at a time. After I respond once, proceed end-to-end without further prompts unless something genuinely blocks you.
2. **Defaults over questions.** Where I've specified a default below, use it silently. Only ask about things with no sensible default.
3. **Don't commit or push.** Stage with `git add` and stop. I review before committing.
4. **No extras.** Build exactly the sections listed. No trophy walls, no visitor maps, no quote widgets, no "Hi 👋 I'm…" — none of the standard GitHub profile bloat.

---

## Required inputs

At the start of the run, ask me for these in **one** message. Skip anything you can infer from the working directory or files already present.

**Essential:**
- GitHub username (for image URLs, badges, repo paths — must be exact)
- Display name for the header overlay (e.g. "Winter")
- Path to the skyline image (default to look for it at `./assets/skyline.{png,jpg,jpeg,webp}` — only ask if you can't find one)

**Content:**
- 2–4 tagline lines for the typing animation. Default if I say "you pick": `Graphics programmer;Engine developer;Low-level enjoyer;Currently rendering pixels`
- Short bio (3–4 lines). Default if I skip: write something neutral about real-time rendering and engine architecture.
- 2–4 pinned/featured repo names (just names, owned by me)
- Tech stack, 6–10 items. Default: `C++, Rust, OpenGL, Vulkan, GLSL, CMake, Linux, Python`
- Contact links (email, website, social). Optional — skip the section if none.

**Aesthetic:**
- Color palette: either a primary hex code, or `extract` (default — pull from the skyline image).
- Theme name for stats cards. Default: `tokyonight`. Other options I might pick: `radical`, `dracula`, `nord`, `gruvbox`, `transparent`, `synthwave`.

**Features (yes/no, defaults in parens):**
- Snake contribution animation (yes)
- 3D contribution skyline (yes)
- Profile view counter (no)
- Spotify now-playing (no — needs OAuth)
- Wakatime stats (no — needs separate account)

---

## Target directory structure

```
.
├── README.md
├── palette.json                 ← generated, dominant colors from skyline
├── assets/
│   └── skyline.{png|jpg|...}    ← I provide
├── .github/
│   └── workflows/
│       ├── snake.yml
│       └── profile-3d.yml       ← only if 3D contrib enabled
└── .gitignore
```

If the working dir doesn't have a `.git` folder, run `git init` as the first step.

---

## Phase 1 — Palette extraction

Only if I picked `extract` (or didn't specify).

1. Locate the skyline image under `./assets/`.
2. Using Python + Pillow, downscale to 100×100, convert to RGB.
3. Cluster pixels to find 3 dominant colors. Simple k-means (`k=3`) or median-cut is fine. If you want zero-dependency, do a basic quantization via `Image.quantize(colors=3)`.
4. From the 3 colors, pick:
   - **primary** → most saturated (use HSL `S` to rank)
   - **dark** → lowest lightness
   - **light** → highest lightness that's not pure white
5. Write `palette.json`:
   ```json
   {
     "primary": "#8B5CF6",
     "dark": "#0B1026",
     "light": "#E0E7FF",
     "source": "assets/skyline.png"
   }
   ```
6. Use `primary` (without the `#`) wherever a single hex is referenced in the README. Use `dark` for any custom badge background that isn't a brand color.

If extraction fails (image unreadable, etc.), fall back to a default palette of `primary=#8B5CF6, dark=#0B1026, light=#E0E7FF` and note this in the final summary.

---

## Phase 2 — README.md

Generate `README.md` with the sections below in this order. Substitute every `<PLACEHOLDER>` before writing. After writing, grep for stray `<` followed by an uppercase letter — there should be no matches.

```markdown
<!-- =========== HEADER =========== -->
<p align="center">
  <img src="./assets/skyline.<EXT>" alt="<DISPLAY_NAME>" width="100%" />
</p>

<!-- =========== TAGLINE =========== -->
<p align="center">
  <img src="https://readme-typing-svg.demolab.com?font=Fira+Code&size=22&pause=1000&color=<PRIMARY_HEX_NO_HASH>&center=true&vCenter=true&width=600&lines=<TAGLINE_1>;<TAGLINE_2>;<TAGLINE_3>" alt="taglines" />
</p>

<br/>

### whoami

<BIO_PARAGRAPH>

<br/>

### featured

<a href="https://github.com/<USERNAME>/<REPO_1>">
  <img src="https://github-readme-stats.vercel.app/api/pin/?username=<USERNAME>&repo=<REPO_1>&theme=<THEME>&hide_border=true&bg_color=00000000" />
</a>
<a href="https://github.com/<USERNAME>/<REPO_2>">
  <img src="https://github-readme-stats.vercel.app/api/pin/?username=<USERNAME>&repo=<REPO_2>&theme=<THEME>&hide_border=true&bg_color=00000000" />
</a>

<br/>

<!-- =========== ACTIVITY =========== -->
<!-- Include only if snake enabled -->
### activity

<picture>
  <source media="(prefers-color-scheme: dark)"
          srcset="https://raw.githubusercontent.com/<USERNAME>/<USERNAME>/output/snake-dark.svg" />
  <source media="(prefers-color-scheme: light)"
          srcset="https://raw.githubusercontent.com/<USERNAME>/<USERNAME>/output/snake.svg" />
  <img alt="snake eating contributions"
       src="https://raw.githubusercontent.com/<USERNAME>/<USERNAME>/output/snake.svg" />
</picture>

<!-- Include only if 3D contrib enabled -->
<p align="center">
  <img src="./profile-3d-contrib/profile-night-view.svg" alt="3d contributions skyline" />
</p>

<br/>

### stats

<p align="center">
  <img height="160" src="https://github-readme-stats.vercel.app/api?username=<USERNAME>&show_icons=true&theme=<THEME>&hide_border=true&bg_color=00000000&icon_color=<PRIMARY_HEX_NO_HASH>&title_color=ffffff&count_private=true" />
  <img height="160" src="https://github-readme-stats.vercel.app/api/top-langs/?username=<USERNAME>&layout=compact&theme=<THEME>&hide_border=true&bg_color=00000000&langs_count=8" />
</p>

<br/>

### stack

<p align="center">
  <!-- one shields.io badge per stack item, see mapping table -->
</p>

<br/>

<!-- Only if contact links provided -->
### elsewhere

<INLINE_CONTACT_LINKS>
```

### Tech stack badge mapping

Use these brand-color + logo mappings for stack badges. Logo names are simpleicons.org slugs.

| tech         | bg hex   | logo slug      | notes                       |
|--------------|----------|----------------|-----------------------------|
| C++          | `00599C` | `cplusplus`    |                             |
| C            | `A8B9CC` | `c`            | logoColor=black             |
| Rust         | `000000` | `rust`         |                             |
| OpenGL       | `5586A4` | `opengl`       |                             |
| Vulkan       | `AC1E2D` | `vulkan`       |                             |
| GLSL         | `5586A4` | `opengl`       | no dedicated slug; reuse    |
| HLSL         | `107C10` | `microsoft`    |                             |
| CMake        | `064F8C` | `cmake`        |                             |
| Linux        | `FCC624` | `linux`        | logoColor=black             |
| Python       | `3776AB` | `python`       |                             |
| WebGPU       | `005A9C` | `webgpu`       |                             |
| Metal        | `000000` | `apple`        |                             |
| DirectX      | `107C10` | `microsoft`    |                             |
| Vim/Neovim   | `019733` | `neovim`       |                             |
| Git          | `F05032` | `git`          |                             |

Badge URL pattern: `https://img.shields.io/badge/<URL_ENCODED_TEXT>-<BG>?style=for-the-badge&logo=<LOGO>&logoColor=white`

For anything not in the table, fall back to: `style=for-the-badge&logo=<LOWERCASE_NAME>&logoColor=white&color=<PRIMARY_HEX_NO_HASH>`.

URL-encode the badge text properly: `C++` → `C%2B%2B`, spaces → `%20`.

---

## Phase 3 — GitHub Actions

### `.github/workflows/snake.yml` (only if snake enabled)

```yaml
name: Generate Snake

on:
  schedule:
    - cron: "0 */12 * * *"
  workflow_dispatch:
  push:
    branches: [main]

jobs:
  generate:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: Platane/snk/svg-only@v3
        with:
          github_user_name: ${{ github.repository_owner }}
          outputs: |
            dist/snake.svg
            dist/snake-dark.svg?palette=github-dark

      - uses: crazy-max/ghaction-github-pages@v4
        with:
          target_branch: output
          build_dir: dist
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### `.github/workflows/profile-3d.yml` (only if 3D contrib enabled)

```yaml
name: GitHub-Profile-3D-Contrib

on:
  schedule:
    - cron: "0 18 * * *"
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
      - uses: yoshi389111/github-profile-3d-contrib@0.7.1
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          USERNAME: ${{ github.repository_owner }}
      - uses: stefanzweifel/git-auto-commit-action@v5
        with:
          commit_message: "build: 3d skyline"
          branch: main
```

No substitutions needed in these — they read `github.repository_owner` at runtime.

---

## Phase 4 — `.gitignore`

```
__pycache__/
*.pyc
.DS_Store
.venv/
node_modules/
```

---

## Phase 5 — Sanity checks

Before declaring done, run these checks and report results inline:

1. `README.md` has no remaining `<UPPERCASE>` placeholders (grep `<[A-Z_]\+>`).
2. Skyline image referenced in README actually exists at that path.
3. `palette.json` exists and `primary` is a valid 7-char hex string.
4. Workflow YAML parses cleanly — try `python -c "import yaml; yaml.safe_load(open('.github/workflows/snake.yml'))"` and same for the 3D one.
5. Primary hex appears in the README in at least 2 places (typing animation + stats `icon_color`).
6. Print the final tree (`find . -not -path './.git/*' -not -path './.venv/*'`).
7. Print the rendered README to stdout — full content, no truncation — so I can review.

If any check fails, fix it before reporting done.

---

## Phase 6 — Git staging

1. If no `.git` directory, `git init` (default branch `main`).
2. `git add .`
3. Print `git status --short`.
4. Suggest a commit message in the final summary: e.g. `"chore: initial profile README"`.
5. **Do not run `git commit` or `git push`.**

---

## Final summary to print

Output a short summary block at the end with:
- Files created (paths)
- Palette used (3 hex codes)
- Sections included / skipped
- Suggested commit message
- The manual handoff list (below) verbatim

---

## Manual handoff — for me

Things you cannot do; print this list at the end so I have it:

1. **Create the GitHub repo** named exactly `<username>/<username>`. Public. No init options (no README, no .gitignore — we have those).
2. **Add the remote and push:**
   ```bash
   git remote add origin git@github.com:<username>/<username>.git
   git commit -m "chore: initial profile README"
   git push -u origin main
   ```
3. **Enable workflow write permissions:** repo Settings → Actions → General → Workflow permissions → "Read and write permissions" → Save. Without this the snake and 3D workflows can't push their outputs back.
4. **Trigger the first runs manually** from the Actions tab (both workflows have `workflow_dispatch`). The snake one creates the `output` branch the README points at; the 3D one populates `profile-3d-contrib/`. Until they run, those images will 404.
5. **Wait ~30 seconds**, refresh `github.com/<username>`. Everything should load. Check mobile too.

---

## Constraints summary (do not violate)

- One color palette throughout. The primary hex should visibly tie the typing animation, stats card, and any custom-colored badges together.
- Every stats/typing/snake image uses `bg_color=00000000` (transparent) for dark/light mode compatibility.
- `<picture>` block for the snake — light and dark variants.
- Headers in the README are lowercase (`whoami`, `featured`, `stats`, etc.) — that's the minimal aesthetic, don't title-case them.
- No emoji in the README unless I explicitly ask.
- No "thanks for visiting" footer, no gradient horizontal rules, no animated GIF mascots.
