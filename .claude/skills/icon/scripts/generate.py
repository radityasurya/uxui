#!/usr/bin/env python3
"""Compose an SVG icon locally from a Style, a semantic role, and a name or prompt.

Clean-room Generator (uxui issue #7): standard library only, no external
model-provider call. It reads the Style catalog at ``../data/styles.csv``
(MIT seed), picks a glyph from a small hand-authored 24x24 library, and
adapts the glyph's geometry to the Style's stroke weight, fill mode, caps,
and joins. The semantic role (the Icon definition in CONTEXT.md) decides the
accessibility attributes:

  decorative  aria-hidden="true" focusable="false", no title
  meaningful  role="img" + <title> (accessible name) + aria-labelledby
  interactive icon stays aria-hidden; the printed guidance wraps it in a
              <button>/<a> that carries the accessible name

Output is deterministic; run scripts/render-check.py on the file it writes.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import re
import sys
from pathlib import Path

DATA_CSV = Path(__file__).resolve().parents[1] / "data" / "styles.csv"
VIEWBOX = "0 0 24 24"
ROLES = ("decorative", "meaningful", "interactive")

# Hand-authored glyphs. Each element: (tag, attrs, draw, layer).
#   draw  "shape" = closed form: filled in fill modes, stroked in stroke modes
#         "line"  = open form: always stroked (a thick stroke in fill modes)
#   layer "ink"   = primary geometry
#         "detail"= secondary layer (duotone's 30% opacity, animation target)
GLYPHS: dict[str, list[tuple]] = {
    "home": [
        ("path", {"d": "M4 11.5 L12 4.5 L20 11.5"}, "line", "ink"),
        ("path", {"d": "M6 10.6 V20 H18 V10.6 Z"}, "shape", "ink"),
        ("path", {"d": "M10 20 V15.2 H14 V20"}, "line", "detail"),
    ],
    "search": [
        ("circle", {"cx": "10.5", "cy": "10.5", "r": "6.5"}, "shape", "ink"),
        ("line", {"x1": "15.3", "y1": "15.3", "x2": "20.6", "y2": "20.6"}, "line", "ink"),
    ],
    "heart": [
        ("path", {
            "d": "M12 20.2 C5.4 15.2 3.2 11.2 5.3 8 C7 5.5 10.6 5.6 12 8.4 "
                 "C13.4 5.6 17 5.5 18.7 8 C20.8 11.2 18.6 15.2 12 20.2 Z"
        }, "shape", "ink"),
    ],
    "star": [
        ("polygon", {
            "points": "12,3 14.2,8.9 20.6,9.2 15.6,13.2 17.3,19.3 12,15.8 "
                      "6.7,19.3 8.4,13.2 3.4,9.2 9.8,8.9"
        }, "shape", "ink"),
    ],
    "check": [
        ("path", {"d": "M4.5 12.5 L9.5 17.5 L19.5 6.5"}, "line", "ink"),
    ],
    "close": [
        ("path", {"d": "M5.5 5.5 L18.5 18.5 M18.5 5.5 L5.5 18.5"}, "line", "ink"),
    ],
    "plus": [
        ("path", {"d": "M12 5 V19 M5 12 H19"}, "line", "ink"),
    ],
    "chevron-right": [
        ("path", {"d": "M9 5 L16 12 L9 19"}, "line", "ink"),
    ],
    "arrow-right": [
        ("path", {"d": "M4 12 H20"}, "line", "ink"),
        ("path", {"d": "M13.5 5.5 L20 12 L13.5 18.5"}, "line", "ink"),
    ],
    # Primary geometry (body parts that identify the glyph) sits on "ink";
    # only optional embellishment (home's door, gear's hub) sits on "detail",
    # because solid styles drop the detail layer.
    "user": [
        ("circle", {"cx": "12", "cy": "8", "r": "4.2"}, "shape", "ink"),
        ("path", {
            "d": "M4.5 20 C4.5 15.2 7.8 13.2 12 13.2 C16.2 13.2 19.5 15.2 19.5 20 Z"
        }, "shape", "ink"),
    ],
    "bell": [
        ("path", {
            "d": "M12 3.5 C8.6 3.5 6.2 6.2 6.2 9.8 V14 L4.2 16.8 H19.8 L17.8 14 V9.8 "
                 "C17.8 6.2 15.4 3.5 12 3.5 Z"
        }, "shape", "ink"),
        ("path", {"d": "M9.6 16.8 C9.6 19.4 10.6 20.4 12 20.4 C13.4 20.4 14.4 19.4 14.4 16.8"},
         "line", "ink"),
    ],
    "cart": [
        ("path", {"d": "M3.5 4.5 H6 L8.2 15.5 H18.8 L20.8 7.2 H7.6"}, "line", "ink"),
        ("circle", {"cx": "9.4", "cy": "19", "r": "1.7"}, "shape", "ink"),
        ("circle", {"cx": "16.4", "cy": "19", "r": "1.7"}, "shape", "ink"),
    ],
    "download": [
        ("path", {"d": "M12 4 V15.5"}, "line", "ink"),
        ("path", {"d": "M7 10.5 L12 15.5 L17 10.5"}, "line", "ink"),
        ("path", {"d": "M4.5 19.5 H19.5"}, "line", "ink"),
    ],
    "gear": [
        ("circle", {"cx": "12", "cy": "12", "r": "6.6"}, "shape", "ink"),
        ("circle", {"cx": "12", "cy": "12", "r": "3.2"}, "shape", "detail"),
        *[("line", {"x1": f"{x1:.2f}", "y1": f"{y1:.2f}",
                    "x2": f"{x2:.2f}", "y2": f"{y2:.2f}"}, "line", "ink")
          for x1, y1, x2, y2 in [
              (18.6, 12, 21.6, 12), (16.67, 16.67, 18.79, 18.79),
              (12, 18.6, 12, 21.6), (7.33, 16.67, 5.21, 18.79),
              (5.4, 12, 2.4, 12), (7.33, 7.33, 5.21, 5.21),
              (12, 5.4, 12, 2.4), (16.67, 7.33, 18.79, 5.21),
          ]],
    ],
}

# Prompt/name words that resolve to a glyph.
KEYWORDS: dict[str, list[str]] = {
    # Keep keywords specific: short generic words (go, get, new, more, right,
    # main, start) hijack unrelated prompts, so they stay out.
    "home": ["home", "house"],
    "search": ["search", "find", "magnify", "zoom", "lookup", "glass"],
    "heart": ["heart", "like", "love", "favorite", "favourite"],
    "star": ["star", "rating", "review", "rate"],
    "check": ["check", "done", "success", "complete", "confirm", "tick"],
    "close": ["close", "cancel", "cross", "dismiss", "clear"],
    "plus": ["plus", "add", "create"],
    "chevron-right": ["chevron", "next", "caret", "expand"],
    "arrow-right": ["arrow", "forward"],
    "user": ["user", "person", "profile", "account", "member", "avatar"],
    "bell": ["bell", "notification", "notify", "alert", "reminder"],
    "cart": ["cart", "basket", "shop", "shopping", "checkout", "bag"],
    "download": ["download", "save", "export"],
    "gear": ["gear", "settings", "setting", "cog", "preferences", "options", "config"],
}

# How each Style id draws. Values missing here fall back to the fill column
# of styles.csv (none→stroke, solid→fill, dual→duotone, gradient→gradient,
# semi-transparent→glass, partial→iso, varies→anim).
STYLE_MODES: dict[str, dict] = {
    "outlined":   {"mode": "stroke", "caps": "round"},
    "thin":       {"mode": "stroke", "caps": "round"},
    "bold":       {"mode": "stroke", "caps": "round"},
    "rounded":    {"mode": "stroke", "caps": "round"},
    "sharp":      {"mode": "stroke", "caps": "butt"},
    "filled":     {"mode": "fill"},
    "flat":       {"mode": "flat"},
    "glyph":      {"mode": "glyph"},
    "duotone":    {"mode": "duotone", "caps": "round"},
    "gradient":   {"mode": "gradient"},
    "glassmorphism": {"mode": "glass", "caps": "round"},
    "pixel":      {"mode": "pixel"},
    "hand-drawn": {"mode": "hand", "caps": "round"},
    "isometric":  {"mode": "iso", "caps": "round"},
    "animated-ready": {"mode": "anim", "caps": "round"},
}
FILL_COLUMN_MODES = {
    "none": "stroke", "solid": "fill", "dual": "duotone", "gradient": "gradient",
    "semi-transparent": "glass", "partial": "iso", "varies": "anim",
}
CAPS = {"round": ("round", "round"), "butt": ("butt", "miter")}


def load_styles() -> dict[str, dict]:
    with DATA_CSV.open("r", encoding="utf-8", newline="") as fh:
        return {row["id"]: row for row in csv.DictReader(fh)}


def style_width(row: dict) -> float | None:
    match = re.search(r"\d+(?:\.\d+)?", row["stroke_width"])
    return float(match.group()) if match else None


def resolve_mode(style_id: str, row: dict) -> tuple[str, str]:
    """Return (mode, caps) for a Style row, tuning table first."""
    tuning = STYLE_MODES.get(style_id, {})
    mode = tuning.get("mode") or FILL_COLUMN_MODES.get(row["fill"], "stroke")
    return mode, tuning.get("caps", "round")


def pick_glyph(text: str) -> str:
    """Match a name or prompt against the keyword table; longest keyword wins."""
    words = set(re.findall(r"[a-z]+", text.lower()))
    best, best_len = None, 0
    for glyph, keywords in KEYWORDS.items():
        for keyword in keywords:
            if keyword in words and len(keyword) > best_len:
                best, best_len = glyph, len(keyword)
    if best is None:
        available = ", ".join(sorted(GLYPHS))
        raise SystemExit(
            f"error: no glyph matches {text!r}; available names: {available}"
        )
    return best


def quantize(value: str) -> str:
    """Snap every number in an attribute to a 3-unit grid (pixel Style)."""
    return re.sub(r"-?\d+(?:\.\d+)?",
                  lambda m: str(round(float(m.group()) / 3) * 3 or 3), value)


# Geometry attributes only: quantizing paint attributes (fill="#6366F1") or
# url(#…) references would silently corrupt colors and ids.
QUANTIZED_ATTRS = {"cx", "cy", "r", "x", "y", "x1", "y1", "x2", "y2",
                   "rx", "ry", "d", "points", "stroke-width"}


def paint_attrs(draw: str, layer: str, mode: str, color: str, width: float,
                caps: str, uid: str) -> dict[str, str]:
    """Attributes for one glyph element under one drawing mode."""
    stroke = {"stroke": color, "stroke-width": f"{width:g}",
              "stroke-linecap": caps, "stroke-linejoin": CAPS[caps][1]}
    fill = {"fill": color}
    if draw == "line":
        # Open paths must never inherit the default black fill.
        attrs = {"fill": "none", **stroke}
        if mode in ("fill", "gradient", "pixel"):
            attrs["stroke-width"] = "2"
        if mode == "glyph":
            attrs["stroke-width"] = "2.5"  # heavier geometry reads at small sizes
        if mode == "gradient":
            attrs["stroke"] = f"url(#uxui-grad-{uid})"
        elif layer == "detail" and mode == "duotone":
            attrs["stroke-opacity"] = "0.3"
        return attrs
    # Closed shapes.
    if mode in ("fill", "pixel", "flat", "glyph"):
        return dict(fill)
    if mode == "gradient":
        return {"fill": f"url(#uxui-grad-{uid})"}
    if mode == "glass":
        return {**fill, "fill-opacity": "0.35", "stroke": color, "stroke-width": "1",
                "stroke-linecap": caps, "stroke-linejoin": CAPS[caps][1]}
    if layer == "detail" and mode == "duotone":
        return {"fill": color, "fill-opacity": "0.3"}
    return {"fill": "none", **stroke}


def render_element(tag: str, attrs: dict, mode: str) -> str:
    if mode == "pixel":
        attrs = {key: quantize(value) if key in QUANTIZED_ATTRS else value
                 for key, value in attrs.items()}
    inner = " ".join(f'{key}="{html.escape(value, quote=True)}"'
                     for key, value in attrs.items())
    return f"<{tag} {inner}/>"


def svg_defs(mode: str, color: str, uid: str) -> list[str]:
    if mode == "gradient":
        safe = html.escape(color, quote=True)
        return [
            "<defs>",
            f'<linearGradient id="uxui-grad-{uid}" x1="0" y1="0" x2="24" y2="24" '
            f'gradientUnits="userSpaceOnUse">',
            f'  <stop offset="0" stop-color="{safe}"/>',
            f'  <stop offset="1" stop-color="{safe}" stop-opacity="0.45"/>',
            "</linearGradient>",
            "</defs>",
        ]
    if mode == "hand":
        return [
            "<defs>",
            # userSpaceOnUse: percentage regions collapse on the zero-height
            # bbox of a straight H/V line and the line disappears.
            f'<filter id="uxui-rough-{uid}" filterUnits="userSpaceOnUse" '
            f'x="0" y="0" width="24" height="24">',
            '  <feTurbulence type="fractalNoise" baseFrequency="0.05" numOctaves="2" '
            'result="noise"/>',
            '  <feDisplacementMap in="SourceGraphic" in2="noise" scale="1.6"/>',
            "</filter>",
            "</defs>",
        ]
    return []


def render_body(elements: list[tuple], mode: str, color: str, width: float,
                caps: str, name: str, uid: str) -> list[str]:
    lines: list[str] = []
    if mode == "anim":
        target = "detail" if any(e[3] == "detail" for e in elements) else "ink"
        lines.append("<style>")
        lines.append(" @media (prefers-reduced-motion: no-preference) {")
        lines.append(f"  #{name}-{target}-{uid} {{ animation: uxui-pulse 2.4s "
                     "ease-in-out infinite; }")
        lines.append("  @keyframes uxui-pulse { 50% { opacity: 0.35; } }")
        lines.append(" }")
        lines.append("</style>")
    layers = {"ink": [], "detail": []}
    for tag, attrs, draw, layer in elements:
        if layer == "detail" and mode in ("fill", "pixel", "glyph", "flat"):
            continue  # single-color solid styles render the ink silhouette
            # only; flat consumes its detail as knockout holes instead
        painted = {**attrs, **paint_attrs(draw, layer, mode, color, width, caps, uid)}
        if mode == "hand":
            painted["filter"] = f"url(#uxui-rough-{uid})"
        layers[layer].append(render_element(tag, painted, mode))
    # flat two-tone: cut the detail layer out of the solid ink as holes (a
    # lighter overlay would vanish under the same-color fill).
    has_detail = any(e[3] == "detail" for e in elements)
    if mode == "flat" and has_detail:
        cut = []
        for tag, attrs, draw, layer in elements:
            if layer != "detail":
                continue
            if draw == "line":
                hole = {**attrs, "fill": "none", "stroke": "black",
                        "stroke-width": "2"}
            else:
                hole = {**attrs, "fill": "black"}
            cut.append(render_element(tag, hole, "fill"))
        lines += ["<defs>",
                  f'<mask id="{name}-cut-{uid}" maskUnits="userSpaceOnUse" '
                  f'x="0" y="0" width="24" height="24">',
                  '  <rect x="0" y="0" width="24" height="24" fill="white"/>',
                  *[f"  {c}" for c in cut],
                  "</mask>",
                  "</defs>"]
    if mode == "iso":
        back = []
        for tag, attrs, draw, _layer in elements:
            back_attrs = dict(attrs)
            if draw == "shape":
                back_attrs.update({"fill": color, "fill-opacity": "0.3"})
            else:
                back_attrs.update({"fill": "none", "stroke": color,
                                   "stroke-width": f"{width:g}",
                                   "stroke-opacity": "0.3"})
            back.append(render_element(tag, back_attrs, "fill"))
        lines.append('<g transform="translate(2.2 -2.2)">')
        lines += [f"  {element}" for element in back]
        lines.append("</g>")
    for layer in ("ink", "detail"):
        if not layers[layer]:
            continue
        mask = (f' mask="url(#{name}-cut-{uid})"'
                if mode == "flat" and has_detail and layer == "ink" else "")
        open_tag = (f'<g id="{name}-{layer}-{uid}">' if mode == "anim"
                    else f"<g{mask}>")
        lines.append(open_tag)
        lines += [f"  {element}" for element in layers[layer]]
        lines.append("</g>")
    return lines


def compose_svg(glyph: str, style_id: str, row: dict, role: str, label: str,
                color: str, size: int) -> str:
    mode, caps = resolve_mode(style_id, row)
    width = style_width(row)
    if width is None or width <= 0:
        width = 2  # 0 or unparsable means "default", never an invisible stroke
    # Every id the output carries is suffixed with a digest of the inputs that
    # shape it, so two inlined icons never share defs or <title> ids unless
    # they are semantically identical (same digest -> same content anyway).
    uid = hashlib.sha256(
        "|".join((glyph, style_id, role, label, color)).encode()
    ).hexdigest()[:8]
    elements = GLYPHS[glyph]
    svg_attrs = {
        "xmlns": "http://www.w3.org/2000/svg", "viewBox": VIEWBOX,
        "width": str(size), "height": str(size),
    }
    if mode == "pixel":
        svg_attrs["shape-rendering"] = "crispEdges"

    header: list[str] = []
    title_id = f"{glyph}-{style_id}-title-{uid}"
    if role == "decorative":
        svg_attrs.update({"aria-hidden": "true", "focusable": "false"})
    elif role == "meaningful":
        svg_attrs.update({"role": "img", "aria-labelledby": title_id})
    else:  # interactive: the wrapper carries the accessible name, not the icon
        svg_attrs.update({"aria-hidden": "true", "focusable": "false"})
        # Any --title must yield valid XML: escape quotes, neutralize "--"
        # (illegal inside XML comments).
        safe_label = html.escape(label, quote=True).replace("--", "–")
        snippet = (f'<button type="button" aria-label="{safe_label}">…</button> or '
                   f'<a href="…" aria-label="{safe_label}">…</a>')
        header.append(f"<!-- uxui:icon interactive role — wrap this icon in a "
                      f"focusable control that carries the accessible name, e.g. "
                      f"{snippet} -->")

    attr_text = " ".join(f'{key}="{value}"' for key, value in svg_attrs.items())
    lines = header + [f"<svg {attr_text}>"]
    if role == "meaningful":
        lines.append(f'<title id="{title_id}">{html.escape(label)}</title>')
    lines += [f"  {line}" for line in svg_defs(mode, color, uid)]
    lines += render_body(elements, mode, color, width, caps, glyph, uid)
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="generate.py",
        description="Compose an SVG icon from a Style, a semantic role, and a "
                    "name or prompt (local, standard library only).",
    )
    parser.add_argument("--name", "-n", help="glyph name (see --list-icons)")
    parser.add_argument("--prompt", "-p", help="icon description; the closest "
                        "glyph keyword wins")
    parser.add_argument("--style", "-s", default="outlined",
                        help="Style id from data/styles.csv (see --list-styles)")
    parser.add_argument("--role", choices=ROLES, default="meaningful",
                        help="semantic role; decides the accessibility "
                        "attributes (default: meaningful)")
    parser.add_argument("--title", help="accessible name for role=meaningful "
                        "(default: the name or prompt)")
    parser.add_argument("--color", default="currentColor",
                        help='"currentColor" or a hex color such as "#6366F1"')
    parser.add_argument("--size", type=int, default=24, help="width/height in px")
    parser.add_argument("--output", "-o", help="output .svg path "
                        "(default: <name>-<style>.svg)")
    parser.add_argument("--list-styles", action="store_true",
                        help="print the Style catalog and exit")
    parser.add_argument("--list-icons", action="store_true",
                        help="print the glyph library and exit")
    args = parser.parse_args(argv)

    styles = load_styles()
    if args.list_styles:
        for row in styles.values():
            print(f"{row['id']:<15} {row['stroke_width']:<8} {row['fill']:<17} "
                  f"{row['best_for']}")
        return 0
    if args.list_icons:
        for glyph, keywords in sorted(KEYWORDS.items()):
            print(f"{glyph:<15} {', '.join(keywords)}")
        return 0

    if not args.name and not args.prompt:
        parser.error("give --name or --prompt (or --list-styles / --list-icons)")
    if args.style not in styles:
        parser.error(f"unknown style {args.style!r}; run --list-styles")
    if not re.fullmatch(r"currentColor|#[0-9a-fA-F]{3,8}", args.color):
        parser.error('color must be "currentColor" or a hex value such as "#6366F1"')

    text = args.name or args.prompt or ""
    glyph = pick_glyph(args.name) if args.name else pick_glyph(args.prompt)
    if args.title:
        label = args.title
    else:
        label = glyph.capitalize() if args.name else text.strip().capitalize()
        if args.role in ("meaningful", "interactive"):
            print(f"warning: no --title given; using {label!r} as the accessible "
                  f"name; pass --title to override", file=sys.stderr)
    svg = compose_svg(glyph, args.style, styles[args.style], args.role,
                      label, args.color, args.size)

    out = Path(args.output) if args.output else Path(f"{glyph}-{args.style}.svg")
    out.write_text(svg, encoding="utf-8")
    print(f"wrote {out} ({glyph} glyph, {args.style} style, {args.role} role)")
    if args.role == "interactive":
        safe_label = html.escape(label, quote=True)
        print(f'interactive guidance: wrap it in a focusable control that carries '
              f'the name, e.g. <button type="button" aria-label="{safe_label}">…</button>; '
              f'the icon itself stays aria-hidden')
    return 0


if __name__ == "__main__":
    sys.exit(main())
