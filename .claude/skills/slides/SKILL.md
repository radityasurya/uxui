---
name: slides
description: Create strategic HTML presentations with Chart.js, design tokens, responsive layouts, copywriting formulas, and contextual slide strategies. Includes a Generator that writes a deck HTML file from a Design system's Tokens and a slide-content JSON.
argument-hint: "[topic] [slide-count]"
metadata:
  author: claudekit
  version: "1.1.0"
---

# Slides

Strategic HTML presentation design with data visualization.

## When to Use

- Marketing presentations and pitch decks
- Data-driven slides with Chart.js
- Strategic slide design with layout patterns
- Copywriting-optimized presentation content

## Generator

`scripts/generate.py` writes one deck HTML file from a Design system's Tokens
plus a slide-content JSON. Every color and font reads the inlined `tokens.css`
written by the uxui:tokens Generator, and every chart slide draws a real
Chart.js canvas (v4 from a CDN; pass `--chartjs <file>` for a vendored,
offline build). Chart types resolve against
`../design-system/data/slide-charts.csv`.

Chain the three Generators, run from this skill's directory:

```bash
# 1. Search: one Design system as JSON
python3 ../search/scripts/search.py "SaaS analytics" --design-system --json -p "Acme" > design-system.json

# 2. Tokens: write tokens/tokens.css (sibling tokens.json supplies the fonts link)
python3 ../tokens/scripts/generate.py --design-system design-system.json --out tokens/

# 3. Slides: write the deck
python3 scripts/generate.py --slides deck.json --tokens tokens/tokens.css --out deck.html
```

Author `deck.json` with the slide types documented in `references/create.md`
(`title`, `content`, `chart`, `closing`). Then run the repository-level checker
`scripts/render-check.py <file>` from the repository root: it screenshots the
deck headlessly, fails on console errors, and is how you confirm the Chart.js
canvases drew.

## Subcommands

| Subcommand | Description | Reference |
|------------|-------------|-----------|
| `create` | Create strategic presentation slides | `references/create.md` |

## Script Paths

Script paths in this skill and its `references/` are relative to the directory that contains this SKILL.md, not to the project: `scripts/<file>` is this skill's own `scripts/` folder, and `../<skill>/scripts/<file>` is a sibling sub-skill installed alongside it. Build the full path from that directory (Claude Code reports it as the skill's base directory when the skill loads) and keep the working directory at the project root — the scripts read and write project files such as `docs/brand-guidelines.md`, `assets/design-tokens.json` or `src/` relative to it.

## References (Knowledge Base)

| Topic | File |
|-------|------|
| Layout Patterns | `references/layout-patterns.md` |
| HTML Template | `references/html-template.md` |
| Copywriting Formulas | `references/copywriting-formulas.md` |
| Slide Strategies | `references/slide-strategies.md` |

## Routing

1. Parse subcommand from `$ARGUMENTS` (first word)
2. Load corresponding `references/{subcommand}.md`
3. Execute with remaining arguments
