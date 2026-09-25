# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

uxui is a design-data and recommendation plugin: searchable databases of UI styles, color palettes, font pairings, chart types, and UX guidelines, plus generator skills. It ships as a plugin for AI coding assistants (Claude Code, Codex).

## Search Command

```bash
python3 .claude/skills/search/scripts/search.py "<query>" --domain <domain> [-n <max_results>]
```

**Domain search:**
- `product` - Product type recommendations (SaaS, e-commerce, portfolio)
- `style` - UI styles (glassmorphism, minimalism, brutalism) + AI prompts and CSS keywords
- `typography` - Font pairings with Google Fonts imports
- `color` - Color palettes by product type
- `landing` - Page structure and CTA strategies
- `chart` - Chart types and library recommendations
- `ux` - Best practices and anti-patterns
- `icons` - Icon recommendations with import code (Phosphor, Heroicons, Lucide)
- `react` - React/Next.js performance patterns
- `web` - App interface guidelines (iOS/Android/React Native)
- `google-fonts` - Individual Google Fonts lookup
- `gsap` - GSAP animation skeletons by intensity tier (hover, scroll reveal, stagger, page transition, parallax, loading)

**Design dials (optional, only with `--design-system`):**
```bash
python3 .claude/skills/search/scripts/search.py "<query>" --design-system --variance <1-10> --motion <1-10> --density <1-10>
```
`--variance` biases style selection (centered/minimal → bold/asymmetric), `--motion` attaches a matching GSAP snippet from `motion.csv`, `--density` overrides the spacing-scale tokens (spacious → dense/dashboard). Any dial left unset behaves exactly as before.

**Stack search:**
```bash
python3 .claude/skills/search/scripts/search.py "<query>" --stack <stack>
```
Available stacks: `html-tailwind` (default), `react`, `nextjs`, `astro`, `vue`, `nuxtjs`, `nuxt-ui`, `svelte`, `swiftui`, `react-native`, `flutter`, `shadcn`, `jetpack-compose`, `threejs`, `angular`, `laravel`, `javafx`, `wpf`, `winui`, `avalonia`, `uno`, `uwp`

## Architecture

```
.claude/skills/                    # The plugin skills — single source of truth
├── search/                        # Design data + search engine
│   ├── data/                      # Canonical CSV databases
│   │   ├── products.csv, styles.csv, colors.csv, typography.csv, ...
│   │   └── stacks/                # Stack-specific guidelines
│   ├── scripts/
│   │   ├── search.py              # CLI entry point
│   │   ├── core.py                # BM25 + regex hybrid search engine
│   │   └── design_system.py       # Design system generation
│   └── references/                # Quick reference docs
├── styling/                       # UI styling skill (Apache-2.0 — see its LICENSE.txt)
├── banner/                        # Banner design skill
├── brand/                         # Brand identity skill
├── icon/                          # SVG icon Generator skill
├── design/                        # Logo/CIP/social-photos generator skill
├── design-system/                 # Token architecture + slides skill
└── slides/                        # HTML presentation skill

.claude-plugin/                    # Plugin manifest and marketplace metadata
scripts/                           # Repo-level validation and catalog refresh scripts
docs/                              # ADRs and journals
```

The search engine uses BM25 ranking combined with regex matching. Domain auto-detection is available when `--domain` is omitted.

## Validation

After changing data or scripts, run:

```bash
python3 scripts/validate-csv.py
python3 scripts/validate-agent-guide.py
python3 scripts/generate-catalog-summary.py --check
python3 -m unittest discover -s .claude/skills/search/scripts/tests -p 'test_*.py'
bash scripts/smoke-domains.sh
bash scripts/smoke-stacks.sh
```

`.claude/skills/styling/` is Apache-2.0: add a "Modified by radityasurya, 2026." mark
near the top of every file you change inside that folder.

## Prerequisites

Python 3.x (no external dependencies required)

**Note:** On Windows, use `python` instead of `python3` to run the scripts.

## Git Workflow

Never push directly to `main`. Always:

1. Create a new branch: `git checkout -b feat/...` or `fix/...`
2. Commit changes
3. Push branch: `git push -u origin <branch>`
4. Create PR: `gh pr create`
