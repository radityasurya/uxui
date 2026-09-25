# Logo Design Reference

Logo design with 55+ searchable styles, 30 color palettes, 25 industry guides, and a local SVG Generator. The Generator needs no API keys and no network: it composes the logo from the Style and Palette catalogs on disk.

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/logo/search.py` | Search styles, colors, industries; generate design briefs |
| `../brand/scripts/generate.py` | Compose an SVG logo locally from a Style, a Palette, and a brand name |
| `scripts/logo/core.py` | BM25 search engine for logo data |

## Commands

### Design Brief (Start Here)

```bash
python3 scripts/logo/search.py "tech startup modern" --design-brief -p "BrandName"
```

### Search Domains

```bash
# Styles
python3 scripts/logo/search.py "minimalist clean" --domain style

# Color palettes
python3 scripts/logo/search.py "tech professional" --domain color

# Industry guidelines
python3 scripts/logo/search.py "healthcare medical" --domain industry
```

### Generate Logo

The brand skill's Generator composes an SVG logo from a Style, a Palette, and a brand name. The Palette is a name from the color catalog or a `tokens.css` path. The brand name stays live `<text>` on a system font stack, so the SVG renders with no external fonts.

```bash
python3 ../brand/scripts/generate.py --name "TechFlow" --style Minimalist --palette "Classic Blue Trust"
python3 ../brand/scripts/generate.py --name "Ironwood Coffee" --style "Vintage Badge" --palette "Coffee Brew" --tagline "Est. 2026"
python3 ../brand/scripts/generate.py --name "TechFlow" --style Gradient --palette assets/design-tokens.css
```

Options: `--name`, `--style`, `--palette` (Palette name or `tokens.css` path), `--tagline`, `--out`, `--list`

## Available Styles

| Category | Styles |
|----------|--------|
| General | Minimalist, Wordmark, Lettermark, Pictorial Mark, Abstract Mark, Mascot, Emblem, Combination Mark |
| Aesthetic | Vintage/Retro, Art Deco, Luxury, Playful, Corporate, Organic, Neon, Grunge, Watercolor |
| Modern | Gradient, Flat Design, 3D/Isometric, Geometric, Line Art, Duotone, Motion-Ready |
| Clever | Negative Space, Monoline, Split/Fragmented, Responsive/Adaptive |

## Color Psychology

| Color | Psychology | Best For |
|-------|------------|----------|
| Blue | Trust, stability | Finance, tech, healthcare |
| Green | Growth, natural | Eco, wellness, organic |
| Red | Energy, passion | Food, sports, entertainment |
| Gold | Luxury, premium | Fashion, jewelry, hotels |
| Purple | Creative, innovative | Beauty, creative, tech |

## Industry Defaults

| Industry | Style | Colors | Typography |
|----------|-------|--------|------------|
| Tech | Minimalist, Abstract | Blues, purples, gradients | Geometric sans |
| Healthcare | Professional, Line Art | Blues, greens, teals | Clean sans |
| Finance | Corporate, Emblem | Navy, gold | Serif or clean sans |
| Food | Vintage Badge, Mascot | Warm reds, oranges | Friendly, script |
| Fashion | Wordmark, Luxury | Black, gold, white | Elegant serif |

## Workflow

1. Generate design brief → `scripts/logo/search.py --design-brief`
2. Generate logo variations → `../brand/scripts/generate.py --name --style --palette`
3. Ask user about HTML preview → `AskUserQuestion` tool
4. If yes, use the bundled `search` skill for the HTML gallery

## Detailed References

- `references/logo-style-guide.md` - Detailed style descriptions
- `references/logo-color-psychology.md` - Color meanings and combinations
- `references/logo-prompt-engineering.md` - AI generation prompts
