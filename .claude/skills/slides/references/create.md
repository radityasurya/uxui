# Create

Invoke the `slides` skill to produce a deck HTML file: write the slide content
as JSON, generate one Design system's Tokens, then run this skill's Generator
(`scripts/generate.py`; the command chain is in this skill's SKILL.md).

## Task

<task>$ARGUMENTS</task>

## Workflow

1. Plan the narrative with `references/slide-strategies.md` and
   `references/copywriting-formulas.md`; pick layouts from
   `references/layout-patterns.md`.
2. Generate one Design system and its Tokens:
   `python3 ../search/scripts/search.py "<product>" --design-system --json`,
   then `python3 ../tokens/scripts/generate.py`.
3. Write `deck.json` (schema below).
4. Run the Generator from this skill's directory:
   `python3 scripts/generate.py --slides deck.json --tokens tokens/tokens.css --out deck.html`
5. Run the repository-level checker `scripts/render-check.py <file>` from the
   repository root. It screenshots the deck and fails on console errors or a
   missing render — use it to confirm each Chart.js canvas drew.

## deck.json schema

The top level is `{title, company, slides: [...]}`. Each slide object carries
`type` plus its own fields:

| Type | Fields | Renders |
|---|---|---|
| `title` | badge, title, subtitle, date | Centered opener; footer shows company and date |
| `content` | badge, headline, bullets: [{title, text}] | Numbered points (01, 02, ...); more than 5 bullets split into `<headline> (cont.)` slides |
| `chart` | badge, headline, chart: {type, title, labels, series} | Real Chart.js canvas in a card; a chart title equal to the headline is dropped |
| `closing` | headline, subheadline, cta, cta_url, contact, website | Centered closer with a CTA button |

Every slide also renders a footer: company and page number (`NN / NN`). The
deck is a presentation, not a page: each slide fills the viewport's 16:9 area,
scroll-snaps one slide per screen, and takes Arrow/Page/Space/Home/End keys.
Type and chart fonts scale with the slide size.

`chart.type` resolves against `../design-system/data/slide-charts.csv` by row
id, alias, `chart_type` name, or keyword: bar, bar-horizontal (hbar), line,
area, pie, donut, stacked-bar, grouped-bar, radar. A type the CSV catalogs but
a plain Chart.js build cannot draw (sankey, funnel, ...) is rejected with the
supported list. Each `series` entry needs a `data` list; series colors cycle
primary, accent, then large shade steps of each against background and
foreground.

Colors and type are never hardcoded. The deck inlines `tokens.css` and the
chart script reads Tokens at runtime with `getComputedStyle`, so regenerating
the Tokens recolors the whole deck. Pass `--chartjs <file>` to build a fully
offline deck from a vendored Chart.js file.
