# uxui

A design data and recommendation layer for AI coding assistants. uxui ships a
searchable local catalog — styles, palettes, font pairings, product types,
reasoning rules, and guidelines — plus generator skills that turn a
recommendation into an output file.

The data covers 79 styles (50 active), 192 product palettes with reasoning
profiles, 74 font pairings, 119 UX guidelines, 105 curated icons, 17 GSAP
presets, 25 chart types, and 22 technology stacks. The search engine runs on
BM25 ranking with regex matching, in pure Python with no dependencies.

## Install

uxui is a plugin for Claude Code and Codex:

```
/plugin marketplace add radityasurya/uxui
/plugin install uxui@uxui
```

Requires Python 3.x on the machine running the assistant.

## Skills

| Skill | Purpose |
|---|---|
| `search` | Design intelligence: search styles, palettes, typography, charts, UX guidelines, and stack-specific rules |
| `styling` | Build styled interfaces with shadcn/ui, Tailwind CSS, and accessible components |
| `banner` | Design banners for social media, ads, website heroes, and print |
| `brand` | Brand voice, visual identity, messaging frameworks, and brand consistency |
| `design` | Logo generation, corporate identity programs, social photos, and icon design |
| `design-system` | Design token architecture, component specs, and slide generation |
| `slides` | Strategic HTML presentations with Chart.js and design tokens |

## Run the search script

```bash
# Search a domain: product, style, typography, color, landing, chart, ux, icons, gsap, react, web, google-fonts
python3 .claude/skills/search/scripts/search.py "fintech dashboard" --domain product

# Generate a complete design system recommendation
python3 .claude/skills/search/scripts/search.py "fintech dashboard" --design-system

# Stack-specific guidelines: react, nextjs, vue, swiftui, flutter, and 17 more
python3 .claude/skills/search/scripts/search.py "virtualized list" --stack react
```

Add `--json` for machine-readable output, `-n <count>` to limit results, and
`--variance/--motion/--density` (with `--design-system`) to bias the
recommendation.

## v2: Image jobs

Some Generators run Image jobs: paid image-generation calls to OpenRouter's
`POST /api/v1/images`. Every Image job reads two environment variables:

- `OPENROUTER_API_KEY` — required. Set it in the environment before the first
  run. Generators check it at the start of a run and exit with a one-line,
  actionable error instead of failing later with a bare HTTP 401. To check
  your environment, run:

  ```bash
  python3 .claude/skills/image/scripts/openrouter_key.py
  ```

- `UXUI_IMAGE_MODEL` — optional. The default model is GPT Image 2
  (`openai/gpt-image-2` on OpenRouter); set this variable to override it.

Provisioning the key value is outside this repository's scope. uxui has no
runtime server and stores no secrets; it only reads the environment variable.
Create the key at openrouter.ai, keep it in your own secret store (for example
a chezmoi-rendered dotfile), and export it before the assistant runs.

## Development

To check catalog freshness against upstream sources, run
`python3 scripts/generate-catalog-summary.py --check`. Current snapshot:
**1,934 approved Google Fonts**, **8 review exclusions**, **105 curated rows**,
**1,512-icon upstream Phosphor manifest**.

To validate a checkout after changes, run:

```bash
python3 scripts/validate-csv.py
python3 scripts/validate-agent-guide.py
bash scripts/smoke-domains.sh
```

To render-check a Generator's output (`.svg` or `.html`), run
`python3 scripts/render-check.py <file> [--out <screenshot>]`. It validates
markup with the Python standard library, renders the file in headless
Chrome or Chromium, and saves a screenshot. Exit code `2` means no Chrome
binary was found; install one or set `RENDER_CHECK_CHROME`.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow.

## Credits

Based on [ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) by Next Level Builder (MIT).

`.claude/skills/styling/` is Apache-2.0; see its LICENSE.txt.
