---
name: brand
description: Brand voice, visual identity, messaging frameworks, asset management, brand consistency, corporate identity program mockup bundles. Activate for branded content, tone of voice, marketing assets, brand compliance, style guides, CIP deliverables.
argument-hint: "[update|review|create] [args]"
metadata:
  author: claudekit
  version: "1.0.0"
---

# Brand

Brand identity, voice, messaging, asset management, and consistency frameworks.

## When to Use

- Brand voice definition and content tone guidance
- Visual identity standards and style guide development
- Messaging framework creation
- Brand consistency review and audit
- Asset organization, naming, and approval
- Color palette management and typography specs
- Logo generation: a local SVG logo from a Style and a Palette
- CIP mockup bundles: business cards, signage, apparel, and other deliverables as cost-gated Image jobs

## Script Paths

Script paths in this skill and its `references/` are relative to the directory that contains this SKILL.md, not to the project: `scripts/<file>` is this skill's own `scripts/` folder, and `../<skill>/scripts/<file>` is a sibling sub-skill installed alongside it. Build the full path from that directory (Claude Code reports it as the skill's base directory when the skill loads) and keep the working directory at the project root — the scripts read and write project files such as `docs/brand-guidelines.md`, `assets/design-tokens.json` or `src/` relative to it.

## Quick Start

**Inject brand context into prompts:**
```bash
node scripts/inject-brand-context.cjs
node scripts/inject-brand-context.cjs --json
```

**Validate an asset:**
```bash
node scripts/validate-asset.cjs <asset-path>
```

**Extract/compare colors:**
```bash
node scripts/extract-colors.cjs --palette
node scripts/extract-colors.cjs <image-path>
```

**Generate an SVG logo:**
```bash
python3 scripts/generate.py --name "Northwind" --style Minimalist --palette "Classic Blue Trust" --tagline "Freight that arrives early"
```

The Style comes from `data/logo/styles.csv`; the Palette is a name from
`data/logo/colors.csv` or a `tokens.css` path. The brand name stays live
`<text>` on a system font stack, so the SVG needs no external fonts. Run with
`--list` to print every Style and Palette name.

## CIP mockup bundle

One brand plus its Design system fans out into N corporate identity program
(CIP) deliverables — each one Image job through the bundled `uxui:image`
skill (`../image/scripts/image_job.py`), so the cost gate covers every
deliverable.

```bash
python3 scripts/cip_bundle.py --brand "Northbeam" --industry Consulting \
  --deliverables "business card,letterhead,reception signage" \
  [--logo northbeam-logo.svg] [--palette "#123B5A #C9A227"] [--typography "..."] \
  [--mockup "Marble Desk"] [--out-dir northbeam-cip] [--dry-run]
```

Run with `--list` to print every Deliverable, Industry, and mockup-context
name. The industry row supplies the default Design system (Style, Palette,
Font pairing); `--palette` and `--typography` override it.

**Cost gate — one combined confirmation.** The bundle prints every
deliverable name, its prompt, the model, the per-image estimate, and the
total estimated cost for all N, then asks **once**; a `y` runs all N Image
jobs, a decline sends zero requests. `--yes` skips the single prompt.
Per-call confirmation was rejected: N interactive stops for a full bundle
buys no additional protection, since the totals are printed up front.
`--dry-run` prints the same plan with no key and no network. A failed job
stops the bundle and lists which deliverables were already saved and paid
for — spend never continues silently.

**Logo.** `--logo` takes the SVG this skill's `scripts/generate.py` writes;
its `<title>` (or `--logo-notes`) becomes a text description in every
prompt. OpenRouter's images endpoint does accept reference images for
image-to-image (`input_references`, per
<https://openrouter.ai/docs/api/api-reference/images/generate-an-image>),
but `uxui:image`'s `run_image_job()` sends `{model, prompt, size}` only, so
the logo travels as a description — never as bytes. Without `--logo`, each
prompt asks for a simple mark plus the wordmark, so logo consistency across
the N images is not guaranteed — generate an SVG with `scripts/generate.py`
and pass `--logo`.

**Contact sheet.** The design skill's renderer turns a finished output
directory into an HTML presentation:

```bash
python3 ../design/scripts/cip/render-html.py --brand "Northbeam" --industry "consulting" --images northbeam-cip
```

## Brand Sync Workflow

```bash
# 1. Edit docs/brand-guidelines.md (or use /brand update)
# 2. Sync to design tokens
node scripts/sync-brand-to-tokens.cjs
# 3. Verify
node scripts/inject-brand-context.cjs --json | head -20
```

The sync stops when it detects existing token files, `:root` custom properties
or Tailwind v4 `@theme` variables in common CSS entry points and their local
CSS imports, or Tailwind theme colors and presets. Review the reported source
before proceeding. If the detected files are the managed
`assets/design-tokens.*` outputs from an earlier sync and replacing them is
intentional, re-run with `--force`.

**Files synced:**
- `docs/brand-guidelines.md` → Source of truth
- `assets/design-tokens.json` → Token definitions
- `assets/design-tokens.css` → CSS variables

## Subcommands

| Subcommand | Description | Reference |
|------------|-------------|-----------|
| `update` | Update brand identity and sync to all design systems | `references/update.md` |

## References

| Topic | File |
|-------|------|
| Voice Framework | `references/voice-framework.md` |
| Visual Identity | `references/visual-identity.md` |
| Messaging | `references/messaging-framework.md` |
| Consistency | `references/consistency-checklist.md` |
| Guidelines Template | `references/brand-guideline-template.md` |
| Asset Organization | `references/asset-organization.md` |
| Color Management | `references/color-palette-management.md` |
| Typography | `references/typography-specifications.md` |
| Logo Usage | `references/logo-usage-rules.md` |
| Approval Checklist | `references/approval-checklist.md` |

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/inject-brand-context.cjs` | Extract brand context for prompt injection |
| `scripts/sync-brand-to-tokens.cjs` | Sync brand-guidelines.md → design-tokens.json/css |
| `scripts/validate-asset.cjs` | Validate asset naming, size, format |
| `scripts/extract-colors.cjs` | Extract and compare colors against palette |
| `scripts/generate.py` | Compose an SVG logo from a Style, a Palette, and a brand name |
| `scripts/cip_bundle.py` | Fan one brand and its Design system out into N cost-gated CIP mockup Image jobs |

## Templates

| Template | Purpose |
|----------|---------|
| `templates/brand-guidelines-starter.md` | Complete starter template for new brands |

## Routing

1. Parse subcommand from `$ARGUMENTS` (first word)
2. Load corresponding `references/{subcommand}.md`
3. Execute with remaining arguments
