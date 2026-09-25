---
name: icon
description: "Compose SVG icons locally from a Style, a semantic role, and a name or prompt. 15 styles from the bundled catalog (outlined, filled, duotone, thin, bold, rounded, sharp, flat, gradient, glassmorphism, pixel, hand-drawn, isometric, glyph, animated-ready) over a 14-glyph library (home, search, heart, star, check, close, plus, chevron-right, arrow-right, user, bell, cart, download, gear) with accessibility attributes per role: decorative (aria-hidden), meaningful (role=img + title), interactive (button wrapper guidance). No external API, no image generation. Actions: generate icon, create SVG icon, build icon set, compose icon."
argument-hint: "[name-or-prompt] [style] [role]"
license: MIT
metadata:
  author: radityasurya
  version: "0.1.0"
---

# Icon

Compose SVG icons locally. This Generator turns a Style from the bundled
catalog, a semantic role, and a name or prompt into one `.svg` file, using a
hand-authored 24×24 glyph library and the Python standard library only.

## When to Use

- Generate an SVG icon or a small icon set for one interface
- Apply an icon Style (stroke weight, fill mode, caps, joins) to a symbol
- Emit correct accessibility attributes for an icon's semantic role

The glyph library covers 14 glyphs: `home`, `search`, `heart`, `star`, `check`,
`close`, `plus`, `chevron-right`, `arrow-right`, `user`, `bell`, `cart`,
`download`, and `gear` (`--list-icons` prints them with their keywords).

Not for this skill: picking an icon from a maintained library (Phosphor,
Heroicons, Lucide). That is an Icon per CONTEXT.md — use the bundled `search`
skill with `--domain icons`.

## Semantic Roles

The role is the Icon definition in CONTEXT.md and decides the accessibility
attributes the Generator writes:

| Role | SVG output | Use when |
|------|-----------|----------|
| `decorative` | `aria-hidden="true" focusable="false"`, no `<title>` | The icon repeats visible text or is pure ornament |
| `meaningful` | `role="img"` + `<title>` + `aria-labelledby` | The icon is the only carrier of its meaning |
| `interactive` | Icon stays `aria-hidden`; the Generator prints wrapper guidance | The icon sits alone in a control — the `<button>`/`<a>` wrapper carries the `aria-label` |

## Commands

Script paths are relative to this skill's directory.

```bash
# Generate from a glyph name
python3 scripts/generate.py --name gear --style outlined --role meaningful --title "Settings"

# Generate from a prompt (longest matching keyword wins)
python3 scripts/generate.py --prompt "shopping cart" --style duotone --role decorative

# Interactive icon: prints the button-wrapper guidance
python3 scripts/generate.py --name download --style filled --role interactive --title "Download"

# Catalog and glyph library
python3 scripts/generate.py --list-styles
python3 scripts/generate.py --list-icons
```

Then render-check the output: `scripts/render-check.py` (issue #2) at the
repository root validates and screenshots the file the Generator wrote. Run it
from the repository root, not from this skill's directory.

## Workflow

1. **Pick the Style** from `data/styles.csv` (`--list-styles` prints it). The
   catalog drives stroke weight and fill mode; the Generator adds what the CSV
   cannot express (caps and joins, duotone layering, gradients, the pixel grid,
   the hand-drawn displacement filter, isometric extrusion, animation IDs).
2. **Pick the role** with the table above. Default: `meaningful` — the
   accessible-by-default choice.
3. **Generate** with `--name` or `--prompt`. Both match the glyph's keyword
   table — `--name gear` works because `gear` is a keyword, not because the
   string equals a glyph id — and the longest matching keyword wins.
   `--color` accepts `currentColor` (default) or a hex value; `--size` sets
   width/height (viewBox stays `0 0 24 24`). Without `--title`, the
   accessible name defaults to the capitalized glyph name (or prompt), and
   the Generator warns on stderr for `meaningful` and `interactive` roles.
4. **Render-check** the file with `scripts/render-check.py` from the repository
   root before handing it over.

An unmatched name or prompt is an error, never a guess: the Generator lists
the available glyphs and exits. For an icon set, generate one file per icon
with the same Style and role; per CONTEXT.md, call the multi-file output a
generated icon set.

Style and glyph notes:

- The solid Styles differ: `filled` renders the ink silhouette only (a filled
  gear has no hub hole); `flat` cuts the detail layer out of the solid ink as
  knockout holes (a flat home shows the door as a hole; glyphs without a
  detail layer render like `filled`); `glyph` stays single-color but draws
  open paths at a heavier weight (2.5) for small sizes; `pixel` snaps to a
  3-unit grid and drops detail.
- `isometric` is not a true isometric projection: the Generator draws a 30%
  opacity copy of the glyph offset by (2.2, −2.2) behind it — a shadow
  extrusion effect, not measured 3D geometry.
- `glassmorphism` applies its translucent fill to closed shapes; a line-only
  glyph (such as `check` or `plus`) renders as an outline under it.
- Every id in the output (gradient, filter, `<title>`, animation groups)
  carries a digest of the icon's inputs, so inlined icons never collide.

## Data

`data/styles.csv` is the Style catalog, seeded from the MIT-licensed
`design/data/icon/styles.csv` and validated by `scripts/validate-csv.py` at
the repository root. `stroke_width` is a plain number in viewBox units (for
example `2`, `1.5`) — `0` marks fill-driven Styles that draw no stroke of
their own; the Generator substitutes its default width when a value is 0 or
missing.

## Prerequisites

Python 3.x, standard library only. On Windows, use `python` instead of
`python3`.
