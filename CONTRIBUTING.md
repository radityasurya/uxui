# Contributing to uxui

Thank you for taking the time to contribute! 🎉
This guide will help you get started quickly.

---

## Getting Started

### Prerequisites

- **Python 3.x**
- **Git**

### Fork & Clone

```bash
# 1. Fork the repo on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/uxui.git
cd uxui
```

---

## Project Structure

```
uxui/
├── .claude/skills/          # The plugin skills — the single source of truth
│   ├── search/              # Design data (CSV) + Python search engine
│   ├── styling/             # UI styling skill (Apache-2.0, see its LICENSE.txt)
│   └── ...                  # banner, brand, design, design-system, slides
├── scripts/                 # Repo-level validation and catalog refresh scripts
├── docs/                    # Documentation
└── .github/                 # Workflows and issue templates
```

> **Important:** Edit data and scripts directly in `.claude/skills/search/`. There is no separate copy to sync.

---

## Ways to Contribute

### 🐛 Bug Fixes
Check the [Issues tab](https://github.com/radityasurya/uxui/issues) for bugs labeled `bug`. Comment on the issue before starting so we don't duplicate work.

### ✨ New UI Styles
Add a new entry to `.claude/skills/search/data/styles.csv`. Each row needs:
- Style name
- Description
- Best for (use cases)
- Key CSS properties/effects

### 🎨 New Color Palettes
Add entries to `.claude/skills/search/data/colors.csv`. Match the existing format (primary, secondary, CTA, background, text, notes).

### 🏭 New Industry Reasoning Rules
Add rules to `.claude/skills/search/data/rules.csv`. Each rule needs a product type, recommended pattern, style priority, color mood, typography mood, key effects, and anti-patterns.

### 📝 Documentation Improvements
Fix typos, clarify confusing sections, or add missing examples in `README.md` or `docs/`.

---

## Development Workflow

```bash
# 1. Create a feature branch from main
git checkout -b feat/your-feature-name

# 2. Make your changes in .claude/skills/

# 3. Test the Python search script
python3 .claude/skills/search/scripts/search.py "your query" --design-system

# 4. Run the validation scripts
python3 scripts/validate-csv.py
python3 scripts/validate-agent-guide.py
bash scripts/smoke-domains.sh

# 5. Push your branch
git push -u origin feat/your-feature-name
```

---

## Commit Message Format

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>: <short description>

Types:
  feat     → New feature or content (new style, rule, palette)
  fix      → Bug fix
  docs     → Documentation only
  refactor → Code change without new feature or fix
  chore    → Build process, dependency updates
  test     → Adding or fixing tests
```

**Examples:**
```
feat: add Skeuomorphism 2.0 style to general styles
fix: correct color palette for fintech industry rule
```

---

## Pull Request Guidelines

1. **One PR per change** — keep PRs focused and small
2. **Reference related issues** — use `Closes #123` in the PR description
3. **Fill out the PR template** — describe what you changed and why
4. **Never push directly to `main`** — always use a feature branch
5. **Wait for review** — a maintainer will review within a few days

---

## Reporting Bugs

Please [open an issue](https://github.com/radityasurya/uxui/issues/new) and include:

- Your OS and terminal
- The AI assistant you're using (Claude Code, Codex, etc.)
- The exact command or prompt that triggered the bug
- Expected vs. actual behavior
- Any error messages or screenshots

---

## Code of Conduct

Be kind, constructive, and respectful. We're all here to build something useful together.
Harassment, spam, or low-effort contributions will be closed without review.

---

## Questions?

Open an [issue](https://github.com/radityasurya/uxui/issues) or check the [README](README.md) first.

Happy contributing! 🚀
