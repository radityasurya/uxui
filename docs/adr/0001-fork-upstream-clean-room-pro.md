# 0001. Start from the upstream MIT repo, clean-room the pro features

Status: accepted
Date: 2026-09-25

## Context

uxui needs a working design-data catalog and a search engine (BM25 over style, palette,
font, and reasoning-rule tables) on day one. The upstream `ui-ux-pro-max-skill` project
(MIT license, Copyright (c) 2024 Next Level Builder) already has both, plus an
Apache-2.0-licensed `ui-styling` skill folder with its own `LICENSE.txt`.

Upstream also sells a paid "pro" tier: logo, banner, icon, slide, and design-token
generation. That tier is a paused, hosted API and MCP service. Upstream ships no
downloadable source for it, so there is no code to reuse, adapt, or attribute.

## Decision

Start the uxui repository from the upstream MIT free tier, keeping its git history and
an `upstream` remote for future data pulls. This is not a GitHub fork: it is a new,
independent repository.

Build every pro-tier feature (logo, banner, icon, slides, design tokens in v1; OpenRouter
image features in v2) clean-room. We write the recommendation data, the prompts, and the
generator code ourselves. We never copy or rephrase paid upstream content, and we never
use the name "UI UX Pro Max" for our product.

## Consequences

- The MIT root `LICENSE` stays. It must list both the original 2024 copyright and the
  uxui project's own copyright once that entity is set; that addition is a follow-up
  task, not part of this ADR.
- The `.claude/skills/ui-styling/` folder keeps its Apache-2.0 license and its own
  `LICENSE.txt` and copyright notices. Apache-2.0 section 4 requires a change mark on
  every file we modify inside that folder, stating what changed.
- Pro-tier generators carry no upstream license obligation, because we wrote them from
  scratch. They fall under the uxui project's own license terms once those are set.
- Clean-room work costs more up front than adapting existing code, since we design and
  populate every pro-tier data table (logo styles, banner sizes, icon styles, slide
  strategies, design tokens) from our own research.

## Alternatives rejected

- **Rewrite everything from zero.** Throws away a working, tested MIT data set and BM25
  engine for no license benefit; the free tier carries no restriction that a rewrite
  would remove.
- **Fork on GitHub.** A fork ties the repository to upstream's repository graph and
  issue tracker, and signals ongoing parity with upstream. uxui diverges by design once
  the pro-tier generators land.
- **Buy the pro tier and rephrase its output.** Rephrasing paid content is a license and
  copyright risk, not a clean-room boundary, and it stops working the moment upstream
  changes its data or prompts.
