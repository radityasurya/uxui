#!/usr/bin/env python3
"""uxui:tokens Generator — write a Design system as three-layer DTCG Tokens.

Reads one Design system (the `--design-system --json` output of the search
skill) and writes three files into --out (default ./tokens):

  tokens.json         W3C DTCG JSON, primitive/semantic/component layers
  tokens.css          CSS custom properties, `var()` aliases per layer
  tailwind.theme.json Tailwind theme mapping onto the custom properties

Semantic names are shadcn-style (background, foreground, primary,
primary-foreground, ...) and identical across the DTCG tree, the CSS custom
properties, and the Tailwind keys. Every *-foreground token keeps at least
4.5:1 contrast against its fill and, when the fill has a hover ramp, against
the hover fill.

Python standard library only.

Usage:
    python3 scripts/generate.py --design-system design-system.json [--out tokens/]
    python3 ../search/scripts/search.py "SaaS analytics" --design-system --json \
        | python3 scripts/generate.py --design-system -
"""
from __future__ import annotations

import argparse
import csv
import functools
import json
import re
import sys
from pathlib import Path

# Spacing scale (px per step) when the Design system carries no density-dial
# override. Mirrors the mid tier of search's VISUAL_DENSITY dial.
DEFAULT_SPACING = {
    "0": "0", "xs": "4", "sm": "8", "md": "16", "lg": "24",
    "xl": "32", "2xl": "48", "3xl": "64",
}
FONT_SIZES = {
    "xs": "0.75rem", "sm": "0.875rem", "base": "1rem", "lg": "1.125rem",
    "xl": "1.25rem", "2xl": "1.5rem", "3xl": "1.875rem", "4xl": "2.25rem",
    "5xl": "3rem", "6xl": "3.75rem",
}
FONT_WEIGHTS = {"regular": 400, "medium": 500, "semibold": 600, "bold": 700}
LINE_HEIGHTS = {"tight": 1.25, "normal": 1.5, "relaxed": 1.625}
RADII = {
    "none": "0", "sm": "0.125rem", "default": "0.25rem", "md": "0.375rem",
    "lg": "0.5rem", "xl": "0.75rem", "full": "9999px",
}


def _shadow(color, x, y, blur, spread="0px"):
    """One DTCG shadow layer as a composite object."""
    return {"color": color, "offsetX": x, "offsetY": y, "blur": blur, "spread": spread}


SHADOWS = {
    # "none" is an empty layer list; a DTCG shadow has no "none" literal.
    "none": [],
    "sm": [_shadow("rgb(0 0 0 / 0.05)", "0px", "1px", "2px")],
    "default": [
        _shadow("rgb(0 0 0 / 0.1)", "0px", "1px", "3px"),
        _shadow("rgb(0 0 0 / 0.1)", "0px", "1px", "2px", "-1px"),
    ],
    "md": [
        _shadow("rgb(0 0 0 / 0.1)", "0px", "4px", "6px", "-1px"),
        _shadow("rgb(0 0 0 / 0.1)", "0px", "2px", "4px", "-2px"),
    ],
    "lg": [
        _shadow("rgb(0 0 0 / 0.1)", "0px", "10px", "15px", "-3px"),
        _shadow("rgb(0 0 0 / 0.1)", "0px", "4px", "6px", "-4px"),
    ],
}
DURATIONS = {"fast": "150ms", "normal": "200ms", "slow": "300ms"}

# Fallback stack per font category, appended after the chosen font.
FONT_FALLBACKS = {
    "serif": ["Georgia", "'Times New Roman'", "serif"],
    "mono": ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
    "script": ["cursive"],
    "sans": ["system-ui", "sans-serif"],
}

_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


# ---------- color helpers ----------
def _parse_hex(value):
    if not isinstance(value, str) or not _HEX_RE.match(value.strip()):
        return None
    value = value.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _hex(rgb):
    return "#%02X%02X%02X" % rgb


def mix_hex(base, other, amount):
    """Blend `other` into `base` by `amount` (0..1). Unparseable input returns base."""
    b, o = _parse_hex(base), _parse_hex(other)
    if b is None or o is None:
        return base
    return _hex(tuple(round(x + (y - x) * amount) for x, y in zip(b, o)))


def _luminance(hex_color):
    rgb = _parse_hex(hex_color)
    if rgb is None:
        return None
    linear = [c / 255 / 12.92 if c / 255 <= 0.04045
              else ((c / 255 + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(a, b):
    """WCAG contrast ratio between two hex colors, or None if unparseable."""
    la, lb = _luminance(a), _luminance(b)
    if la is None or lb is None:
        return None
    lo, hi = min(la, lb), max(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def readable_on(hex_color):
    """Whichever of black or white has the higher WCAG ratio against the fill."""
    return "#000000" if (contrast_ratio(hex_color, "#000000") or 0) >= (
        contrast_ratio(hex_color, "#FFFFFF") or 0) else "#FFFFFF"


def _on_color(fill, provided=None):
    """The Palette's on-color when it holds 4.5:1 on the fill, else black/white.

    For any fill, the better of black and white always reaches 4.5:1 (the two
    curves cross at 4.58:1), so this never fails.
    """
    if provided and (contrast_ratio(provided, fill) or 0) >= 4.5:
        return provided
    return readable_on(fill)


def text_safe(base, toward, bg, target=4.5):
    """Blend `base` toward `toward` until it reads at `target` ratio on `bg`."""
    amount = 0.0
    while amount < 1.0 and (contrast_ratio(mix_hex(base, toward, amount), bg) or 0) < target:
        amount += 0.05
    return mix_hex(base, toward, round(amount, 2))


def input_border(background, foreground):
    """Input outline: ~45% foreground into background, deepened to 3:1 on background."""
    amount = 0.45
    while amount < 1.0 and (contrast_ratio(mix_hex(background, foreground, amount),
                                           background) or 0) < 3.0:
        amount += 0.05
    return mix_hex(background, foreground, round(amount, 2))


# ---------- font stacks ----------
def _category_word(text):
    """Category word for one half of a pairing category or a font name."""
    text = (text or "").lower()
    if "mono" in text:
        return "mono"
    if "serif" in text:
        return "serif"
    if "script" in text or "handwrit" in text:
        return "script"
    return "sans"


@functools.lru_cache(maxsize=1)
def _known_font_categories():
    """{font name: pairing-category half} from the search skill's typography data."""
    mapping = {}
    path = Path(__file__).resolve().parents[2] / "search" / "data" / "typography.csv"
    try:
        with path.open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                halves = [h for h in re.split(r"\+|,", row.get("Category") or "") if h.strip()]
                for column, half in zip(("Heading Font", "Body Font"), halves):
                    if row.get(column):
                        mapping[row[column].strip().lower()] = half
    except OSError:
        pass  # dataset missing: fall back to the name heuristic
    return mapping


def _font_category(name, typography, position):
    """serif / mono / script / sans for one slot of the Font pairing."""
    halves = [h for h in re.split(r"\+|,", typography.get("category") or "") if h.strip()]
    if len(halves) > position:
        return _category_word(halves[position])
    # The name itself wins before the dataset: e.g. "Roboto Mono" is listed
    # under a "Sans + Sans" pairing row but is a monospace font.
    if _category_word(name) != "sans":
        return _category_word(name)
    known = _known_font_categories().get((name or "").strip().lower())
    if known:
        return _category_word(known)
    return "sans"


def font_stack(name, category=None):
    """Font stack as a DTCG fontFamily array: the font plus a category fallback."""
    name = (name or "").strip() or "Inter"
    return [name] + FONT_FALLBACKS.get(category or "sans", FONT_FALLBACKS["sans"])


def _stack(typography, slot):
    """DTCG fontFamily array for one slot ("heading"/"body") of the pairing."""
    name = (typography.get(slot) or "").strip()
    return font_stack(name, _font_category(name, typography, 0 if slot == "heading" else 1))


# ---------- DTCG assembly ----------
def _token(value, token_type):
    return {"$value": value, "$type": token_type}


def _palette(ds):
    """Resolved palette under final role names: given roles verbatim, optional
    roles derived, every *-foreground held to 4.5:1 on its fill and hover fill."""
    colors = ds.get("colors", {})
    get = lambda k: (colors.get(k) or "").strip()
    given = {k: get(k) for k in (
        "primary", "on_primary", "secondary", "on_secondary",
        "accent", "on_accent", "background", "foreground",
        "card", "card_foreground", "muted", "muted_foreground",
        "border", "destructive", "on_destructive", "ring",
    ) if _parse_hex(get(k))}

    def fill(key, value):
        given.setdefault(key, value)

    fill("primary", "#2563EB")
    fill("secondary", mix_hex(given["primary"], "#FFFFFF", 0.15)
         if "primary" in given else "#3B82F6")
    fill("accent", "#F97316")
    fill("background", "#F8FAFC")
    fill("foreground", "#1E293B")
    fill("card", given["background"])
    fill("card_foreground", given["foreground"])
    fill("muted", mix_hex(given["background"], given["foreground"], 0.10))
    fill("muted_foreground", mix_hex(given["foreground"], given["background"], 0.30))
    fill("border", mix_hex(given["background"], given["foreground"], 0.15))
    fill("destructive", "#DC2626")
    fill("success", "#16A34A")
    fill("warning", "#D97706")
    fill("ring", given["primary"])

    hover = {
        "primary": mix_hex(given["primary"], "#000000", 0.20),
        "accent": mix_hex(given["accent"], "#000000", 0.20),
    }
    return {
        "primary": given["primary"],
        "primary-hover": hover["primary"],
        "primary-foreground": _on_color(given["primary"], given.get("on_primary")),
        "primary-hover-foreground": _on_color(hover["primary"], given.get("on_primary")),
        "secondary": given["secondary"],
        "secondary-foreground": _on_color(given["secondary"], given.get("on_secondary")),
        "accent": given["accent"],
        "accent-hover": hover["accent"],
        "accent-foreground": _on_color(given["accent"], given.get("on_accent")),
        "accent-hover-foreground": _on_color(hover["accent"], given.get("on_accent")),
        "accent-text": text_safe(given["accent"], given["foreground"], given["background"]),
        "background": given["background"],
        "foreground": given["foreground"],
        "card": given["card"],
        "card-foreground": _on_color(given["card"], given["card_foreground"]),
        "muted": given["muted"],
        "muted-foreground": _on_color(given["muted"], given["muted_foreground"]),
        "border": given["border"],
        "input": input_border(given["background"], given["foreground"]),
        "destructive": given["destructive"],
        "destructive-foreground": _on_color(given["destructive"], given.get("on_destructive")),
        "success": given["success"],
        "success-foreground": _on_color(given["success"]),
        "warning": given["warning"],
        "warning-foreground": _on_color(given["warning"]),
        "ring": given["ring"],
    }


def _spacing_scale(ds):
    """Spacing scale in rem, from the Design system's density override or the default."""
    scale = ds.get("spacing_scale") or DEFAULT_SPACING
    out = {}
    for step, px in scale.items():
        out[step] = "0" if px in ("0", 0) else f"{int(str(px).rstrip('px')) / 16:g}rem"
    return out


def build_tokens(ds):
    """Build the three-layer DTCG token tree from one Design system dict."""
    palette = _palette(ds)
    typography = ds.get("typography", {})
    spacing = _spacing_scale(ds)

    primitive = {
        "color": {
            # The resolved Palette under one group, so the semantic layer can
            # name purposes without name collisions. Given roles are verbatim;
            # optional roles (card, muted, border, ring, on-colors) are derived.
            "palette": {
                key: _token(value, "color") for key, value in palette.items()
            },
            # Derived brand ramps: 600 is the exact Palette value, 500/700 are
            # mixes used for hover/active states.
            "primary": {
                "500": _token(mix_hex(palette["primary"], "#FFFFFF", 0.18), "color"),
                "600": _token(palette["primary"], "color"),
                "700": _token(palette["primary-hover"], "color"),
            },
            "accent": {
                "500": _token(mix_hex(palette["accent"], "#FFFFFF", 0.18), "color"),
                "600": _token(palette["accent"], "color"),
                "700": _token(palette["accent-hover"], "color"),
            },
        },
        "font": {
            "family": {
                "heading": _token(_stack(typography, "heading"), "fontFamily"),
                "body": _token(_stack(typography, "body"), "fontFamily"),
            },
            "weight": {step: _token(value, "fontWeight")
                       for step, value in FONT_WEIGHTS.items()},
        },
        "spacing": {step: _token(value, "dimension") for step, value in spacing.items()},
    }
    primitive["font"]["size"] = {step: _token(value, "dimension")
                                 for step, value in FONT_SIZES.items()}
    primitive["line-height"] = {step: _token(value, "number")
                                for step, value in LINE_HEIGHTS.items()}
    primitive["radius"] = {step: _token(value, "dimension")
                           for step, value in RADII.items()}
    primitive["shadow"] = {step: _token(value, "shadow")
                           for step, value in SHADOWS.items()}
    primitive["duration"] = {step: _token(value, "duration")
                             for step, value in DURATIONS.items()}

    semantic = {
        "color": {
            "background": _token("{primitive.color.palette.background}", "color"),
            "foreground": _token("{primitive.color.palette.foreground}", "color"),
            "primary": _token("{primitive.color.primary.600}", "color"),
            "primary-hover": _token("{primitive.color.primary.700}", "color"),
            "primary-foreground": _token("{primitive.color.palette.primary-foreground}", "color"),
            "primary-hover-foreground": _token(
                "{primitive.color.palette.primary-hover-foreground}", "color"),
            "secondary": _token("{primitive.color.palette.secondary}", "color"),
            "secondary-foreground": _token(
                "{primitive.color.palette.secondary-foreground}", "color"),
            "accent": _token("{primitive.color.accent.600}", "color"),
            "accent-hover": _token("{primitive.color.accent.700}", "color"),
            "accent-foreground": _token("{primitive.color.palette.accent-foreground}", "color"),
            "accent-hover-foreground": _token(
                "{primitive.color.palette.accent-hover-foreground}", "color"),
            "accent-text": _token("{primitive.color.palette.accent-text}", "color"),
            "card": _token("{primitive.color.palette.card}", "color"),
            "card-foreground": _token("{primitive.color.palette.card-foreground}", "color"),
            "muted": _token("{primitive.color.palette.muted}", "color"),
            "muted-foreground": _token("{primitive.color.palette.muted-foreground}", "color"),
            "border": _token("{primitive.color.palette.border}", "color"),
            "input": _token("{primitive.color.palette.input}", "color"),
            "destructive": _token("{primitive.color.palette.destructive}", "color"),
            "destructive-foreground": _token(
                "{primitive.color.palette.destructive-foreground}", "color"),
            "success": _token("{primitive.color.palette.success}", "color"),
            "success-foreground": _token(
                "{primitive.color.palette.success-foreground}", "color"),
            "warning": _token("{primitive.color.palette.warning}", "color"),
            "warning-foreground": _token(
                "{primitive.color.palette.warning-foreground}", "color"),
            "ring": _token("{primitive.color.palette.ring}", "color"),
        },
        "font": {
            "heading": _token("{primitive.font.family.heading}", "fontFamily"),
            "body": _token("{primitive.font.family.body}", "fontFamily"),
        },
        "spacing": {
            "component": _token("{primitive.spacing.md}", "dimension"),
            "section": _token("{primitive.spacing.xl}", "dimension"),
        },
    }

    component = {
        "button": {
            "background": _token("{semantic.color.primary}", "color"),
            "foreground": _token("{semantic.color.primary-foreground}", "color"),
            "hover-background": _token("{semantic.color.primary-hover}", "color"),
            "hover-foreground": _token("{semantic.color.primary-hover-foreground}", "color"),
            "padding-x": _token("{primitive.spacing.md}", "dimension"),
            "padding-y": _token("{primitive.spacing.sm}", "dimension"),
            "radius": _token("{primitive.radius.md}", "dimension"),
            "font-size": _token("{primitive.font.size.sm}", "dimension"),
            "font-weight": _token("{primitive.font.weight.semibold}", "fontWeight"),
        },
        "input": {
            "background": _token("{semantic.color.background}", "color"),
            "foreground": _token("{semantic.color.foreground}", "color"),
            "border": _token("{semantic.color.input}", "color"),
            "ring": _token("{semantic.color.ring}", "color"),
            "padding-x": _token("{primitive.spacing.sm}", "dimension"),
            "padding-y": _token("{primitive.spacing.xs}", "dimension"),
            "radius": _token("{primitive.radius.md}", "dimension"),
        },
        "card": {
            "background": _token("{semantic.color.card}", "color"),
            "foreground": _token("{semantic.color.card-foreground}", "color"),
            "border": _token("{semantic.color.border}", "color"),
            "shadow": _token("{primitive.shadow.default}", "shadow"),
            "padding": _token("{primitive.spacing.lg}", "dimension"),
            "radius": _token("{primitive.radius.lg}", "dimension"),
        },
    }

    return {
        "$schema": "https://design-tokens.org/schema.json",
        "$description": (
            f"Tokens for the {ds.get('project_name', 'design system')} Design system, "
            "generated by the uxui:tokens Generator."
        ),
        "primitive": primitive,
        "semantic": semantic,
        "component": component,
    }


# ---------- CSS + Tailwind export ----------
def iter_tokens(group, path=()):
    """Yield (full_path, token) for every $value leaf in a DTCG group."""
    for key, node in group.items():
        if isinstance(node, dict) and "$value" in node:
            yield path + (key,), node
        elif isinstance(node, dict):
            yield from iter_tokens(node, path + (key,))


def css_name(path):
    """CSS custom-property name for a token path (layer segment dropped)."""
    return "--" + "-".join(path[1:])


def _css_font_family(names):
    return ", ".join(
        name if name.startswith(("'", '"')) or " " not in name else f"'{name}'"
        for name in names
    )


def _css_shadow(layers):
    return ", ".join(
        f"{s['offsetX']} {s['offsetY']} {s['blur']} {s['spread']} {s['color']}"
        for s in layers
    ) or "none"


def css_value(token, all_paths):
    """CSS text for a token value: var() for aliases, literals otherwise."""
    value = token["$value"]
    if isinstance(value, str) and value.startswith("{") and value.endswith("}"):
        target = tuple(value[1:-1].split("."))
        if target not in all_paths:
            raise ValueError(f"alias {value} points at no token")
        return f"var({css_name(target)})"
    if isinstance(value, dict):
        return _css_shadow([value])
    if isinstance(value, list):
        # A shadow layer list (empty means "none"); anything else is a fontFamily.
        if not value or isinstance(value[0], dict):
            return _css_shadow(value)
        return _css_font_family(value)
    return str(value)


def render_css(tokens):
    """Render the three layers as CSS custom properties with layer comments."""
    all_paths = {path for path, _ in iter_tokens(tokens)}
    lines = [
        "/* Generated by the uxui:tokens Generator from one Design system. */",
        "/* Regenerate instead of hand-editing. */",
        "",
    ]
    for layer, title in (("primitive", "PRIMITIVE TOKENS (raw values)"),
                         ("semantic", "SEMANTIC TOKENS (purpose aliases)"),
                         ("component", "COMPONENT TOKENS (per-component)")):
        lines.append(f"/* === {title} === */")
        lines.append(":root {")
        for path, token in iter_tokens({layer: tokens[layer]}):
            lines.append(f"  {css_name(path)}: {css_value(token, all_paths)};")
        lines.append("}")
        lines.append("")
    return "\n".join(lines)


def build_tailwind_theme(tokens):
    """Tailwind theme file mapping utility keys onto tokens.css variables."""
    names = {css_name(path) for path, _ in iter_tokens(tokens)}

    def v(name):
        return f"var({name})" if name in names else None

    def group(mapping):
        return {k: val for k, val in mapping.items() if val is not None} or None

    colors = group({
        "background": v("--color-background"), "foreground": v("--color-foreground"),
        "card": group({"DEFAULT": v("--color-card"),
                       "foreground": v("--color-card-foreground")}),
        "muted": group({"DEFAULT": v("--color-muted"),
                        "foreground": v("--color-muted-foreground")}),
        "border": v("--color-border"), "input": v("--color-input"),
        "ring": v("--color-ring"),
        "destructive": group({"DEFAULT": v("--color-destructive"),
                              "foreground": v("--color-destructive-foreground")}),
        "success": group({"DEFAULT": v("--color-success"),
                          "foreground": v("--color-success-foreground")}),
        "warning": group({"DEFAULT": v("--color-warning"),
                          "foreground": v("--color-warning-foreground")}),
        "primary": group({"DEFAULT": v("--color-primary"),
                          "foreground": v("--color-primary-foreground"),
                          "hover": group({"DEFAULT": v("--color-primary-hover"),
                                          "foreground": v("--color-primary-hover-foreground")})}),
        "secondary": group({"DEFAULT": v("--color-secondary"),
                            "foreground": v("--color-secondary-foreground")}),
        "accent": group({"DEFAULT": v("--color-accent"),
                         "foreground": v("--color-accent-foreground"),
                         "text": v("--color-accent-text"),
                         "hover": group({"DEFAULT": v("--color-accent-hover"),
                                         "foreground": v("--color-accent-hover-foreground")})}),
    })
    theme = {
        "$comment": (
            "Tailwind theme for the uxui:tokens Generator. Merge into "
            "theme.extend (Tailwind v3); import tokens.css first so the var() "
            "values resolve. Tailwind v4 reads CSS, not JSON: use the "
            "tokens.css custom properties directly."
        ),
        "colors": colors,
        "fontFamily": group({"heading": v("--font-heading"),
                             "body": v("--font-body")}),
        "fontSize": group({step: v(f"--font-size-{step}") for step in FONT_SIZES}),
        "fontWeight": group({step: v(f"--font-weight-{step}") for step in FONT_WEIGHTS}),
        "lineHeight": group({step: v(f"--line-height-{step}") for step in LINE_HEIGHTS}),
        "spacing": group({**{step: v(f"--spacing-{step}") for step in
                          ("0", "xs", "sm", "md", "lg", "xl", "2xl", "3xl")},
                          "component": v("--spacing-component"),
                          "section": v("--spacing-section")}),
        # Tailwind's DEFAULT key makes the bare utility (`rounded`, `shadow`);
        # the token underneath keeps its "default" name.
        "borderRadius": group({key: v(f"--radius-{step}") for key, step in (
            ("DEFAULT", "default"), ("sm", "sm"), ("md", "md"),
            ("lg", "lg"), ("xl", "xl"), ("full", "full"))}),
        "boxShadow": group({key: v(f"--shadow-{step}") for key, step in (
            ("DEFAULT", "default"), ("sm", "sm"), ("md", "md"), ("lg", "lg"))}),
        "transitionDuration": group({step: v(f"--duration-{step}")
                                     for step in DURATIONS}),
    }
    return {key: value for key, value in theme.items() if value}


# ---------- CLI ----------
def load_design_system(source):
    """Read a Design system JSON from a file path or '-' (stdin)."""
    if source == "-":
        data = json.load(sys.stdin)
    else:
        data = json.loads(Path(source).read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("design_system"), dict):
        data = data["design_system"]
    if not isinstance(data, dict) or "colors" not in data:
        raise ValueError(
            "input is not a Design system: expected the --design-system --json "
            "output of the search skill"
        )
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="generate.py",
        description="Write one Design system as DTCG JSON, tokens.css, and a Tailwind theme.",
    )
    parser.add_argument(
        "--design-system", required=True, metavar="JSON",
        help="Design system JSON file (search skill --design-system --json output), or '-' for stdin",
    )
    parser.add_argument("--out", default="tokens", metavar="DIR",
                        help="output directory (default: ./tokens)")
    args = parser.parse_args(argv)

    ds = load_design_system(args.design_system)
    tokens = build_tokens(ds)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    outputs = {
        "tokens.json": json.dumps(tokens, indent=2) + "\n",
        "tokens.css": render_css(tokens),
        "tailwind.theme.json": json.dumps(build_tailwind_theme(tokens), indent=2) + "\n",
    }
    for filename, content in outputs.items():
        path = out_dir / filename
        path.write_text(content, encoding="utf-8")
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
