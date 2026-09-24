# uxui

Domain glossary for the uxui design-data and recommendation layer.

## Language

**Style**: A named visual language (for example Minimalism, Glassmorphism) with its own
colors, effects, and best-use cases, drawn from the style catalog.
_Avoid_: "UI style", "aesthetic", "theme" — always say Style.

**Palette**: A fixed set of named colors (primary, secondary, accent, background, and their
paired foreground colors) tied to one Product type or brand.
_Avoid_: "color scheme", or "colors" as a stand-in for the whole set.

**Font pairing**: A heading font and a body font chosen together for one mood, drawn from the
font catalog.
_Avoid_: "typography" or "fonts" alone when one specific pairing is meant.

**Product type**: A category of product being designed (for example SaaS, e-commerce, micro
SaaS) that anchors every other recommendation.
_Avoid_: "app type", "vertical".

**Layout pattern**: A recommended page structure and section order (for example Hero +
Features + CTA) for one Product type and one page kind, such as a landing page or a
dashboard.
_Avoid_: "template", or "pattern" alone.

**Reasoning rule**: A conditional decision that maps a Product type or context to a
recommended Style, Layout pattern, color mood, or constraint.
_Avoid_: "logic", "recommendation engine".

**Guideline**: A platform- or Stack-scoped do/don't check with a severity, covering
accessibility, performance, motion, and interaction correctness.
_Avoid_: "best practice"; reserve "rule" for Reasoning rule.

**Stack**: The specific framework or library a product is built with (for example React,
SwiftUI, Flutter), used to select the matching set of Guidelines.
_Avoid_: "framework" alone. Distinct from platform, the broader OS or runtime surface
(Web, iOS, Android, All) a Guideline also carries.

**Icon**: A single symbol chosen from a maintained icon library (for example Phosphor) for
one interface use, with a defined semantic role (decorative, meaningful, or interactive).
_Avoid_: confusing this with a generated icon set — see Flagged ambiguities.

**Design system**: One recommended set of Style, Palette, and Font pairing for one Product
type, filtered by Reasoning rules and Guidelines.
_Avoid_: "theme", "UI kit".

**Token**: A named design decision (a color, a spacing value, a font size) written in the
W3C Design Tokens Community Group (DTCG) format, organized in primitive, semantic, and
component layers.
_Avoid_: "variable", or "design value" alone.

**Generator**: A skill that turns a Design system into an output file, such as slides, a
banner, an icon set, or a logo.
_Avoid_: "tool", or "skill" alone — a Generator is a specific kind of skill that always
produces a file.

**Image job**: One paid image-generation call to an external model provider, used only
inside a Generator that needs a raster or illustrated asset.
_Avoid_: "generation" or "render" alone.

## Relationships

- A Design system selects one Style, one Palette, and one Font pairing for one Product
  type, filtered by Reasoning rules and Guidelines.
- A Product type recommends a primary Style, a Palette, and a Layout pattern, plus
  secondary Style alternates.
- A Reasoning rule reads a Product type, and sometimes a Style, and outputs a Layout
  pattern, a color mood, or a constraint.
- A Guideline is scoped to one platform and, where relevant, one Stack. Reasoning rules
  decide what to build; Guidelines check how it is built.
- A Style can supersede another Style when retired, through a parent-style and
  replacement link.
- A Font pairing draws its heading font and body font from the font catalog.
- An Icon is chosen from the icon library independent of Style; a Generator can also
  produce a new icon set as output.
- A Generator consumes a Design system, or sometimes a single Style or Palette, and
  writes Tokens or a rendered file. Some Generators call one or more Image jobs to fill
  in raster art.
- A Token is organized in three layers: primitive (raw value), semantic (purpose alias),
  and component (per-component override).

## Flagged ambiguities

- **Style**: the data names the same concept "Style", "UI style", and "Primary Style
  Recommendation" across different tables. Resolution: always say Style.
- **Palette**: the data mixes "Palette", "Colors", and "Color Palette Focus" for the same
  set. Resolution: Palette is the noun; never use "color" alone for the whole set.
- **Platform vs. Stack**: general guideline tables use "Platform" for a broad runtime
  surface (Web, iOS, Android, All); the per-framework guideline tables name a specific
  Stack (React, Vue, SwiftUI) and add a version constraint. Resolution: Platform is the
  broad surface, Stack is the specific framework or library; a Stack's version constraint
  is not a separate term.
- **Reasoning rule vs. Guideline**: both get called "rule" in places. Reasoning rule
  chooses a recommendation before anything is built; Guideline checks an implementation
  after a choice is made. Resolution: keep the two terms and the distinction above.
- **Icon**: the icon catalog and the icon Generator both get called "icon" upstream.
  Resolution: Icon is a catalog entry used to compose an interface; the Generator's
  output is always called a generated icon set when the two could be confused.
- **Pattern**: some tables call a Layout pattern just "Pattern" or "Pattern Name".
  Resolution: always say Layout pattern.
- **Generator output cardinality**: a Generator is defined as producing one file, but the
  corporate identity program generator produces a bundle of many deliverables (business
  cards, signage, digital templates) from one Design system. Resolution: a Generator can
  emit one file or a bundle that shares one Design system; call a multi-file output a
  generator bundle only where the distinction matters.
