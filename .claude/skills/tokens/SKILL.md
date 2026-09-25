---
name: tokens
description: "Generator that writes one Design system as W3C DTCG Tokens: a three-layer (primitive/semantic/component) tokens.json, a tokens.css of CSS custom properties, and a tailwind.theme.json. Use it when a Design system exists and slides, banners, icons, logos, or app code need its colors and type through Tokens instead of hardcoded values."
---

# uxui:tokens — Design system to DTCG Tokens

Reads one Design system (one Style, one Palette, one Font pairing for one
Product type, from the search skill's `--design-system` output) and writes it
as three-layer Tokens in W3C Design Tokens Community Group (DTCG) JSON, then
exports CSS custom properties and a Tailwind theme file from that JSON.

Python standard library only. No Node.js, no dependencies.

## When to use

- A Design system was generated and a page, component, or another Generator
  (slides, banner, icon, logo) needs its colors and type through Tokens.
- A project needs CSS custom properties or a Tailwind theme derived from one
  Palette instead of hardcoded hex values.

## Supersedes the design-system skill's Node.js token scripts

This skill supersedes `.claude/skills/design-system/scripts/generate-tokens.cjs`,
`validate-tokens.cjs`, and `embed-tokens.cjs` for new work. Those are Node.js
scripts, and the runtime decision for uxui Generators is local Python,
standard library only (ADR 0001). The `.cjs` files stay in place for existing
consumers; they are not deleted. Use this skill for every new token export.

## Command chain

Generate a Design system, then write its Tokens. Run from the skill directory
context; script paths are relative to this skill's folder:

```bash
# 1. Search: one Design system as JSON
python3 ../search/scripts/search.py "SaaS analytics" --design-system --json -p "Acme" > design-system.json

# 2. Tokens: write tokens.json, tokens.css, tailwind.theme.json
python3 scripts/generate.py --design-system design-system.json --out tokens/
```

Or pipe the search output straight in:

```bash
python3 ../search/scripts/search.py "SaaS analytics" --design-system --json | python3 scripts/generate.py --design-system - --out tokens/
```

## Outputs

| File | Contents |
|---|---|
| `tokens/tokens.json` | DTCG JSON, `$value` + `$type` per token, `{layer.group.name}` aliases between layers |
| `tokens/tokens.css` | CSS custom properties in three commented `:root` blocks, aliases as `var()` |
| `tokens/tailwind.theme.json` | Tailwind theme mapping every utility onto the `var(--…)` names |

`tailwind.theme.json` targets Tailwind v3: merge it into `theme.extend` in
`tailwind.config.js`, with `tokens.css` imported first so the `var()` values
resolve. Tailwind v4's `@theme` reads CSS, not JSON — in v4, import
`tokens.css` and use its custom properties (or alias them in `@theme`)
directly instead of this file.

Regenerate after changing the Design system. Do not hand-edit the outputs.

## Layering

The three layers follow `.claude/skills/design-system/references/token-architecture.md`:

- **primitive** — raw values: the resolved Palette under `color.palette.*`,
  derived hover ramps `color.primary.500/600/700` and `color.accent.500/600/700`
  (600 is the exact Palette value), the Font pairing stacks, the spacing scale,
  font sizes and weights, line heights, radii, shadows, durations.
- **semantic** — purpose aliases the app and later Generators consume.
- **component** — per-component overrides (`button.*`, `input.*`, `card.*`)
  referencing the semantic layer.

CSS naming rule: the custom-property name is the token path after the layer,
dash-joined — `semantic.color.background` → `--color-background`,
`component.button.background` → `--button-background`.

## Semantic token set

The base every later Generator consumes. Names are shadcn-style and identical
in the DTCG tree, the CSS custom properties, and the Tailwind keys. These
names are the contract; keep them stable:

| Token | CSS | Points at |
|---|---|---|
| `color.background` / `color.foreground` | `--color-background` / `--color-foreground` | Palette background / foreground |
| `color.primary`, `primary-hover`, `primary-foreground`, `primary-hover-foreground` | `--color-primary` … | Brand ramp and its text |
| `color.secondary` / `secondary-foreground` | `--color-secondary` … | Palette secondary and its text |
| `color.accent`, `accent-hover`, `accent-foreground`, `accent-hover-foreground` | `--color-accent` … | CTA ramp and its text |
| `color.accent-text` | `--color-accent-text` | Accent tuned for text on background (≥ 4.5:1) |
| `color.card` / `card-foreground`, `color.muted` / `muted-foreground` | `--color-card` … | Surfaces and their text |
| `color.border` / `color.input` | `--color-border` / `--color-input` | Decorative dividers / input outlines (≥ 3:1) |
| `color.destructive` / `destructive-foreground` | `--color-destructive` … | Danger fill and its text |
| `color.success` / `success-foreground`, `color.warning` / `warning-foreground` | `--color-success` … | Status fills and their text (slides, banners) |
| `color.ring` | `--color-ring` | Focus ring |
| `font.heading` / `font.body` | `--font-heading` / `--font-body` | Font pairing stacks |
| `spacing.component` / `spacing.section` | `--spacing-component` … | Semantic spacing |

Contrast guarantees: every `*-foreground` token holds at least 4.5:1 against
its fill, and — where the fill has a hover ramp (`primary`, `accent`) — the
`*-hover-foreground` token holds 4.5:1 against the hover fill. A Palette
on-color that fails 4.5:1 is replaced by the stronger of black or white.

Scales live in the primitive layer: `spacing.0…3xl` (from the Design system's
density dial, else the standard 4–64 px scale), `font.size.xs…6xl`,
`font.weight.regular…bold`, `line-height.tight/normal/relaxed`,
`radius.none…full`, `shadow.none…lg`, `duration.fast/normal/slow`. In
`tailwind.theme.json` the bare `rounded` / `shadow` utilities come from the
`DEFAULT` key.

Optional Palette roles missing from the Design system (card, muted, border,
ring, on-colors, success, warning) are derived: mixes of background and
foreground for surfaces, and a black/white pick by contrast ratio for
on-colors. Font stacks fall back by category — a serif heading gets a serif
fallback stack, a mono body gets monospace — using the Design system's pairing
category when it gives one, else the font's entry in the search skill's
typography dataset.

## Verify an output

To render-check an HTML page that links `tokens.css`, run the repository-level
checker `scripts/render-check.py <file>` from the repository root.

## Known limits

- No dark-mode derivation: the generator emits the Design system's resolved
  mode only. A `.dark` override layer is future work.
- The Google Fonts import (`typography.css_import` in the Design system) is
  not written into `tokens.css`; add it to the project's own CSS (or a
  `<link>` in the page) so token files stay values-only.
