# CIP Design Reference

Corporate Identity Program design with 50+ deliverables, 20 styles, 20 industries. Generate mockup bundles through cost-gated Image jobs (`uxui:image`, OpenRouter).

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/cip/search.py` | Search deliverables, styles, industries; generate CIP briefs |
| `../brand/scripts/cip_bundle.py` | CIP generator bundle: one Image job per deliverable behind one combined cost gate |
| `scripts/cip/render-html.py` | Render HTML presentation from CIP mockups |
| `scripts/cip/core.py` | BM25 search engine for CIP data |

## Commands

### CIP Brief (Start Here)

```bash
python3 scripts/cip/search.py "tech startup" --cip-brief -b "BrandName"
```

### Search Domains

```bash
# Deliverables
python3 scripts/cip/search.py "business card letterhead" --domain deliverable

# Design styles
python3 scripts/cip/search.py "luxury premium elegant" --domain style

# Industry guidelines
python3 scripts/cip/search.py "hospitality hotel" --domain industry

# Mockup contexts
python3 scripts/cip/search.py "office reception" --domain mockup
```

### Generate Mockup Bundle

One combined cost gate covers all N deliverables: the bundle prints every
name, prompt, the model, and the total estimated cost, then asks once. A
decline sends zero requests; `--dry-run` prints the plan with no key and no
network. See the `brand` skill's SKILL.md for the full cost-gate contract.

```bash
# Three deliverables, logo described in every prompt
python3 ../brand/scripts/cip_bundle.py --brand "TopGroup" --industry consulting --deliverables "business card,letterhead,reception signage" --logo logo.svg

# Plan only: all prompts and the total, nothing sent
python3 ../brand/scripts/cip_bundle.py --brand "GreenLeaf" --industry "food & beverage" --deliverables "product label,folding carton" --dry-run

# Without a logo (each image invents its own mark; consistency not guaranteed)
python3 ../brand/scripts/cip_bundle.py --brand "TechFlow" --industry technology --deliverables "business card"
```

### Render HTML Presentation

```bash
python3 scripts/cip/render-html.py --brand "TopGroup" --industry "consulting" --images /path/to/cip-output
python3 scripts/cip/render-html.py --brand "TopGroup" --industry "consulting" --images ./topgroup-cip --output presentation.html
```

## Models

- `openai/gpt-image-2` (default): OpenRouter images endpoint via `uxui:image`
- Override with `UXUI_IMAGE_MODEL`; models without a price row print
  "unknown model: cost unknown" and still require confirmation

## Deliverable Categories

| Category | Items |
|----------|-------|
| Core Identity | Logo, Logo Variations |
| Stationery | Business Card, Letterhead, Envelope, Folder, Notebook, Pen |
| Security/Access | ID Badge, Lanyard, Access Card |
| Office Environment | Reception Signage, Wayfinding, Meeting Room Signs, Wall Graphics |
| Apparel | Polo Shirt, T-Shirt, Cap, Jacket, Apron |
| Promotional | Tote Bag, Gift Box, USB Drive, Water Bottle, Mug, Umbrella |
| Vehicle | Car Sedan, Van, Truck |
| Digital | Social Media, Email Signature, PowerPoint, Document Templates |
| Product | Packaging Box, Labels, Tags, Retail Display |
| Events | Trade Show Booth, Banner Stand, Table Cover, Backdrop |

## Design Styles

| Style | Colors | Best For |
|-------|--------|----------|
| Corporate Minimal | Navy, White, Blue | Finance, Legal, Consulting |
| Modern Tech | Purple, Cyan, Green | Tech, Startups, SaaS |
| Luxury Premium | Black, Gold, White | Fashion, Jewelry, Hotels |
| Warm Organic | Brown, Green, Cream | Food, Organic, Artisan |
| Bold Dynamic | Red, Orange, Black | Sports, Entertainment |

## HTML Presentation Features

- Hero section with brand name, industry, style, mood
- Deliverable cards with mockup images
- Descriptions: concept, purpose, specifications
- Responsive desktop/mobile, dark theme
- Images embedded as base64 (single-file portable)

## Workflow

1. Generate CIP brief → `scripts/cip/search.py --cip-brief`
2. Generate mockup bundle → `../brand/scripts/cip_bundle.py --brand --industry --deliverables [--logo]`
3. Render HTML presentation → `scripts/cip/render-html.py --brand --industry --images`

**Tip:** If no logo exists, generate one first with the `brand` skill's
`scripts/generate.py` (a local SVG; the bundle reads its `<title>` as the
logo description for every prompt).

## Detailed References

- `references/cip-deliverable-guide.md` - Deliverable specifications
- `references/cip-style-guide.md` - Design style descriptions
- `references/cip-prompt-engineering.md` - AI generation prompts

## Setup

```bash
export OPENROUTER_API_KEY="your-key"   # required before the first Image job
```
