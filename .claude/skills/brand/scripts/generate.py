#!/usr/bin/env python3
"""Local SVG logo Generator for the uxui brand skill.

Composes one SVG logo from a Style row, a Palette row, and a brand name:

    python3 scripts/generate.py --name "Northwind" --style Minimalist \
        --palette "Classic Blue Trust" --tagline "Logistics that move" --out northwind.svg

The Palette is either a Palette name from data/logo/colors.csv or the path to a
tokens.css file with ``--color-primary``-style custom properties. The brand
name and tagline stay live ``<text>`` elements on a system font stack, so the
SVG renders with no external fonts or network access. Python standard library
only.
"""
from __future__ import annotations

import argparse
import csv
import html
import math
import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = SKILL_DIR / "data" / "logo"

FONT_STACKS = {
    "sans": "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif",
    "serif": "ui-serif, Georgia, 'Times New Roman', serif",
    "mono": "ui-monospace, 'Cascadia Mono', Menlo, Consolas, monospace",
}
# Uppercase lockups read as institutional; tracked ones as luxury or Swiss.
UPPERCASE_STYLES = {"Emblem", "Vintage Badge", "Brutalist", "Luxury/Premium",
                    "Swiss/International", "Lettermark"}
TRACKED_STYLES = {"Luxury/Premium", "Vintage Badge", "Swiss/International"}
DEFAULT_PALETTE = "Monochrome Gray"
HEX_RE = re.compile(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")
TOKEN_RE = re.compile(r"--([\w-]+)\s*:\s*(#[0-9a-fA-F]{3,8})")

ROLES = ("primary", "secondary", "accent", "background", "text")


def normalize_hex(value: str) -> str:
    value = value.strip()
    if not value.startswith("#"):
        value = "#" + value
    if re.fullmatch(r"#[0-9a-fA-F]{3}", value):
        value = "#" + "".join(ch * 2 for ch in value[1:])
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise ValueError(f"not a hex color: {value!r}")
    return value.lower()


def load_catalog(path: Path, name_field: str) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def find_row(rows: list[dict], name_field: str, name: str) -> dict:
    wanted = name.strip().lower()
    for row in rows:
        if row[name_field].strip().lower() == wanted:
            return row
    for row in rows:  # then a prefix/substring match, so "minimal" finds Minimalist
        if wanted in row[name_field].strip().lower():
            return row
    names = ", ".join(row[name_field] for row in rows)
    raise SystemExit(f"error: no {name_field.lower()} matching {name!r}. Known: {names}")


def palette_from_row(row: dict) -> dict:
    return {role: normalize_hex(row[f"{role.title()} Hex"]) for role in ROLES}


def palette_from_tokens_css(path: Path) -> dict:
    """Read custom properties like --color-primary / --bg / --text from tokens.css."""
    tokens: dict[str, str] = {}
    for prop, value in TOKEN_RE.findall(path.read_text(encoding="utf-8")):
        tokens[prop.lower()] = normalize_hex(value)
    palette: dict[str, str] = {}
    for role in ROLES:
        aliases = ("background", "bg") if role == "background" else (role,)
        matches = [v for k, v in tokens.items() if any(a in k for a in aliases)]
        palette[role] = matches[0] if matches else ""
    if not palette["primary"]:  # fall back to whatever hexes the file does carry
        any_hex = HEX_RE.findall(path.read_text(encoding="utf-8"))
        if not any_hex:
            raise SystemExit(f"error: no usable color custom properties in {path}")
        palette["primary"] = normalize_hex(any_hex[0])
    palette["background"] = palette["background"] or "#ffffff"
    palette["text"] = palette["text"] or "#111111"
    palette["secondary"] = palette["secondary"] or palette["primary"]
    palette["accent"] = palette["accent"] or palette["secondary"]
    return palette


def font_class(typography: str) -> str:
    t = typography.lower()
    if "mono" in t:
        return "mono"
    if re.search(r"(?<!sans[- ])serif", t) or "script" in t:
        return "serif"
    return "sans"


def font_weight(typography: str, default: str) -> str:
    """Read the intended weight off the Typography column of the Style row."""
    t = typography.lower()
    if "black" in t:
        return "900"
    if "bold" in t or "heavy" in t:
        return "800"
    if "thin" in t or "light" in t:
        return "300"
    if "medium" in t:
        return "500"
    return default


def initials(name: str, single: bool) -> str:
    words = [w for w in name.split() if w]
    if single or len(words) == 1:
        return words[0][0].upper()
    return (words[0][0] + words[1][0]).upper()


def relative_luminance(color: str) -> float:
    def channel(value: int) -> float:
        value /= 255
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast_ratio(a: str, b: str) -> float:
    light, dark = sorted((relative_luminance(a), relative_luminance(b)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def legible_on(fg: str, fill: str) -> bool:
    """WCAG contrast ratio >= 3:1 — the large-graphics threshold."""
    return contrast_ratio(fg, fill) >= 3


def pick_legible(candidates: tuple[str, ...], fills: tuple[str, ...]) -> str:
    """First candidate legible on every fill; else the best total contrast.

    Keeps marks visible on hostile palettes: a dark primary on a dark
    background (Midnight Dark) or a pale one on white (Pastel Rainbow)
    falls back to the text color instead of vanishing.
    """
    for cand in candidates:
        if cand and all(legible_on(cand, fill) for fill in fills):
            return cand
    return max(candidates, key=lambda c: sum(contrast_ratio(c, f) for f in fills))


def char_width(ch: str) -> float:
    """Rough advance width of one character as a fraction of font size.

    Tuned for the system stacks: full-width CJK near 1.0, wide Latin caps
    (M/W) near 0.95, hairline glyphs (i, l, period) near 0.3. A flat
    0.66em/char let "MMMMWWWWMMMMWWWW" and long Japanese names run off
    the canvas.
    """
    o = ord(ch)
    if (0x1100 <= o <= 0x115F            # Hangul Jamo
            or 0x2E80 <= o <= 0xA4CF     # CJK radicals, kana, ideographs
            or 0xAC00 <= o <= 0xD7A3     # Hangul syllables
            or 0xF900 <= o <= 0xFAFF     # CJK compatibility ideographs
            or 0xFE30 <= o <= 0xFE4F     # CJK compatibility forms
            or 0xFF00 <= o <= 0xFF60):   # fullwidth forms
        return 1.0
    if ch in "MW\"@":
        return 0.95
    if ch in "mw":
        return 0.80
    if ch in "iljtI.,;:'!|":
        return 0.30
    if ch in "fr-()[]{}/\\":
        return 0.40
    if ch == " ":
        return 0.30
    if ch in "%&":
        return 0.85
    if ch.isupper() or ch.isdigit():
        return 0.74
    return 0.55


def estimate_width(text: str, fs: float, tracking: float) -> float:
    """Estimated rendered width of `text` at font-size `fs` with tracking."""
    if not text:
        return 0.0
    return sum(char_width(ch) for ch in text) * fs + (len(text) - 1) * tracking


def fit_size(text: str, base: float, max_width: float, tracking: float) -> float:
    units = sum(char_width(ch) for ch in text)
    if units <= 0:
        return base
    return min(base, (max_width - (len(text) - 1) * tracking) / units)


def text_el(x: float, y: float, text: str, fs: float, avail: float,
            tracking: float, anchor: str = "", extra: str = "") -> str:
    """One <text> element, hard-capped with textLength when the estimate
    says the string runs past the available width."""
    fs = round(fs)  # judge the cap on the size that is actually emitted
    cap = ""
    if text and estimate_width(text, fs, tracking) > avail:
        cap = f' textLength="{avail:.0f}" lengthAdjust="spacingAndGlyphs"'
    a = f' text-anchor="{anchor}"' if anchor else ""
    return (f'<text x="{x:.0f}" y="{y:.0f}"{a} font-size="{fs:.0f}"{cap}{extra}>'
            f'{html.escape(text)}</text>')


def hexagon_points(cx: float, cy: float, r: float) -> str:
    return " ".join(
        f"{cx + r * math.sin(math.radians(a)):.1f},{cy - r * math.cos(math.radians(a)):.1f}"
        for a in range(0, 360, 60)
    )


def mark_svg(style: dict, palette: dict, name: str, size: float) -> tuple[str, str]:
    """Return (defs, mark group) drawn in a size x size box, origin top-left."""
    mark = style["Mark"]
    container = style["Container"]
    outline = style["Outline"] == "1"
    variant = style["Variant"]
    c = size / 2
    primary, secondary, accent = palette["primary"], palette["secondary"], palette["accent"]
    text_color, bg = palette["text"], palette["background"]
    defs: list[str] = []
    parts: list[str] = []
    sw = size * 0.045  # one stroke weight everywhere: monoline discipline
    # Everything in the mark draws in `ink`: primary when it clears the
    # background, else the strongest surviving palette color.
    ink = pick_legible((primary, text_color, secondary, accent), (bg,))
    stroke_attrs = f'fill="none" stroke="{ink}" stroke-width="{sw:.1f}"'

    def shape(element: str) -> None:
        """Add a container shape authored as fill=none: filled or outlined."""
        if outline:
            parts.append(element.replace("/>", f' stroke="{ink}" stroke-width="{sw:.1f}"/>'))
        else:
            parts.append(element.replace('fill="none"', f'fill="{ink}"', 1))

    # 1. Container
    if container == "circle":
        shape(f'<circle cx="{c}" cy="{c}" r="{size * 0.475:.1f}" fill="none"/>')
    elif container == "square":
        shape(f'<rect x="{size * 0.04:.1f}" y="{size * 0.04:.1f}" width="{size * 0.92:.1f}"'
              f' height="{size * 0.92:.1f}" rx="{size * 0.16:.1f}" fill="none"/>')
    elif container == "hexagon":
        shape(f'<polygon points="{hexagon_points(c, c, size * 0.49)}" fill="none"/>')
    elif container == "shield":
        s = size / 160  # shield path is authored on a 160 box
        path = ("M80,8 L146,34 V88 C146,120 118,146 80,156 "
                "C42,146 14,120 14,88 V34 Z")
        shape(f'<path d="{path}" fill="none" transform="scale({s:.3f})"/>')
    elif container == "ring":
        parts.append(f'<circle cx="{c}" cy="{c}" r="{size * 0.475:.1f}" fill="none" '
                     f'stroke="{ink}" stroke-width="{sw * 1.1:.1f}"/>')
        parts.append(f'<circle cx="{c}" cy="{c}" r="{size * 0.38:.1f}" fill="none" '
                     f'stroke="{ink}" stroke-width="{sw * 0.35:.1f}"/>')

    filled = not outline and container in {"circle", "square", "hexagon", "shield"}
    grad_end = duo_right = block = ""

    # 2. Variant decorations that repaint the container
    if variant == "gradient" and filled:
        grad_end = pick_legible((accent, text_color, secondary), (bg,))
        defs.append(f'<linearGradient id="grad" x1="0" y1="0" x2="1" y2="1">'
                    f'<stop offset="0" stop-color="{ink}"/>'
                    f'<stop offset="1" stop-color="{grad_end}"/></linearGradient>')
        for i, part in enumerate(parts):
            parts[i] = part.replace(f'fill="{ink}"', 'fill="url(#grad)"')
    elif variant == "duotone" and filled:
        duo_right = pick_legible((accent, text_color, secondary), (bg, ink))
        defs.append(f'<clipPath id="duo"><rect x="{size / 2}" y="0" width="{size}" '
                    f'height="{size}"/></clipPath>')
        right = parts[0].replace(f'fill="{ink}"', f'fill="{duo_right}"')
        for tag in ("<circle ", "<rect ", "<polygon ", "<path "):
            if tag in right:  # clip the accent copy to the right half of the container
                right = right.replace(tag, f'{tag}clip-path="url(#duo)" ', 1)
                break
        parts.append(right)
    elif variant == "brutalist" and filled:
        block = text_color if legible_on(text_color, bg) else ink
        for i, part in enumerate(parts):
            parts[i] = part.replace(f'fill="{ink}"', f'fill="{block}"')
    elif variant == "bauhaus":
        # Circle, square, triangle — the Bauhaus triad, each fully inside the
        # mark box and not overlapping the others.
        parts = [
            f'<circle cx="{size * 0.30:.1f}" cy="{size * 0.30:.1f}" '
            f'r="{size * 0.22:.1f}" fill="{ink}"/>',
            f'<rect x="{size * 0.58:.1f}" y="{size * 0.08:.1f}" width="{size * 0.32:.1f}" '
            f'height="{size * 0.32:.1f}" fill="{pick_legible((accent, text_color, secondary), (bg,))}"/>',
            f'<polygon points="{size * 0.14:.1f},{size * 0.88:.1f} {size * 0.86:.1f},'
            f'{size * 0.88:.1f} {size * 0.50:.1f},{size * 0.42:.1f}" '
            f'fill="{pick_legible((secondary, text_color), (bg,))}"/>',
        ]
    elif variant == "badge" and container == "ring":
        # Coin-edge dots between the rings: the heritage badge tell that
        # separates this mark from the plain Luxury ring.
        parts.append(f'<circle cx="{c}" cy="{c}" r="{size * 0.42:.1f}" fill="none" '
                     f'stroke="{ink}" stroke-width="{sw * 0.5:.1f}" stroke-dasharray="1.5 7"/>')

    # Colors the mark content actually sits on: the filled container (ink, or
    # its variant repaint) or the bare canvas.
    if not filled or variant == "knockout":
        behind: tuple[str, ...] = (bg,)
    elif variant == "gradient":
        behind = (ink, grad_end)
    elif variant == "duotone":
        behind = (ink, duo_right)
    elif variant == "brutalist":
        behind = (block,)
    else:
        behind = (ink,)

    # 3. Mark content inside the container (the Bauhaus triad replaces it all)
    if mark == "monogram":
        single = style["Style Name"] == "Letterform"
        letters = initials(name, single)
        fs = size * (0.95 if single and container == "none" else
                     (0.60 if single else (0.42 if len(letters) == 2 else 0.55)))
        fonts = FONT_STACKS[font_class(style["Typography"])]
        weight = font_weight(style["Typography"], "700")
        if variant == "knockout" and parts and not outline:
            # Negative space, honestly: the initials are cut out of the filled
            # container with a mask, so the canvas shows through the letters.
            defs.append(f'<mask id="cut"><rect width="{size:.0f}" height="{size:.0f}" '
                        f'fill="white"/><text x="{c:.1f}" y="{c + fs * 0.36:.1f}" '
                        f'text-anchor="middle" font-family="{fonts}" '
                        f'font-size="{fs:.0f}" font-weight="700" '
                        f'fill="black">{html.escape(letters)}</text></mask>')
            head, _, rest = parts[0].partition(" ")
            parts[0] = f'{head} mask="url(#cut)" {rest}'
        elif outline:
            parts.append(f'<text x="{c}" y="{c + fs * 0.36:.1f}" text-anchor="middle" '
                         f'font-family="{fonts}" font-size="{fs:.0f}" font-weight="{weight}" '
                         f'fill="none" stroke="{ink}" '
                         f'stroke-width="{sw * 0.45:.1f}">{html.escape(letters)}</text>')
        else:
            fill = ink if container in ("none", "ring") else pick_legible((bg, text_color), behind)
            parts.append(f'<text x="{c}" y="{c + fs * 0.36:.1f}" text-anchor="middle" '
                         f'font-family="{fonts}" font-size="{fs:.0f}" font-weight="{weight}" '
                         f'fill="{fill}">{html.escape(letters)}</text>')
    elif mark == "geometric" and variant != "bauhaus":
        core = pick_legible((accent, bg, text_color), behind)
        if container == "circle":
            parts.append(f'<circle cx="{c}" cy="{c}" r="{size * 0.27:.1f}" fill="none" '
                         f'stroke="{core}" stroke-width="{sw:.1f}"/>')
            parts.append(f'<circle cx="{c}" cy="{c}" r="{size * 0.075:.1f}" fill="{core}"/>')
        elif container == "square":
            parts.append(f'<rect x="{size * 0.31:.1f}" y="{size * 0.31:.1f}" '
                         f'width="{size * 0.38:.1f}" height="{size * 0.38:.1f}" fill="{core}" '
                         f'transform="rotate(45 {c:.1f} {c:.1f})"/>')
        elif container == "hexagon":
            hole = pick_legible((behind[0], bg), (core,))
            parts.append(f'<circle cx="{c}" cy="{c}" r="{size * 0.25:.1f}" fill="{core}"/>')
            parts.append(f'<circle cx="{c}" cy="{c}" r="{size * 0.09:.1f}" fill="{hole}"/>')
        elif container == "shield":
            parts.append(f'<path d="M{c * 0.62:.0f},{c * 1.08:.0f} L{c:.0f},{c * 0.7:.0f} '
                         f'L{c * 1.38:.0f},{c * 1.08:.0f} L{c * 1.38:.0f},{c * 1.4:.0f} '
                         f'L{c:.0f},{c * 1.12:.0f} L{c * 0.62:.0f},{c * 1.4:.0f} Z" fill="{core}"/>')
        else:  # no container: an abstract triad of primary shapes
            triangle = " ".join(hexagon_points(size * 0.74, c * 1.14, size * 0.22).split()[0::2])
            c2 = pick_legible((accent, text_color, secondary), (bg,))
            c3 = pick_legible((secondary, text_color), (bg,))
            parts.append(f'<circle cx="{size * 0.30:.1f}" cy="{c * 1.06:.1f}" r="{size * 0.21:.1f}" fill="{ink}"/>')
            parts.append(f'<rect x="{size * 0.52:.1f}" y="{size * 0.10:.1f}" width="{size * 0.30:.1f}" '
                         f'height="{size * 0.30:.1f}" fill="{c2}" transform="rotate(45 {size * 0.67:.1f} {size * 0.25:.1f})"/>')
            parts.append(f'<polygon points="{triangle}" fill="{c3}"/>')
    elif mark == "line":
        if container != "none":  # outlined initials inside an outlined container
            letters = initials(name, False)
            fs = size * 0.42
            parts.append(f'<text x="{c}" y="{c + fs * 0.36:.1f}" text-anchor="middle" '
                         f'font-family="{FONT_STACKS["sans"]}" font-size="{fs:.0f}" '
                         f'font-weight="{font_weight(style["Typography"], "600")}" fill="none" '
                         f'stroke="{ink}" stroke-width="{sw * 0.35:.1f}">'
                         f'{html.escape(letters)}</text>')
        elif style["Style Name"] == "Monoline":
            parts.append(f'<circle cx="{c}" cy="{c}" r="{size * 0.34:.1f}" {stroke_attrs}/>')
            parts.append(f'<line x1="{size * 0.06:.1f}" y1="{c:.1f}" x2="{size * 0.94:.1f}" '
                         f'y2="{c:.1f}" {stroke_attrs}/>')
        else:  # Line Art: one deliberate continuous stroke (a closed infinity
               # loop — a single subpath, the pen never lifts)
            s = size / 160
            path = ("M80,80 C58,38 18,58 18,80 C18,102 58,122 80,80 "
                    "C102,38 142,58 142,80 C142,102 102,122 80,80 Z")
            parts.append(f'<path d="{path}" {stroke_attrs} stroke-linecap="round" '
                         f'stroke-linejoin="round" transform="scale({s:.3f})"/>')

    body = "\n    ".join(parts)
    transform = ' transform="skewX(-10)"' if variant == "slant" else ""
    return ("\n    ".join(defs), f'<g{transform}>\n    {body}\n  </g>')


def compose_svg(style: dict, palette: dict, name: str, tagline: str) -> str:
    layout = style["Layout"]
    variant = style["Variant"]
    typography = style["Typography"]
    fonts = FONT_STACKS[font_class(typography)]
    upper = style["Style Name"] in UPPERCASE_STYLES
    tracked = style["Style Name"] in TRACKED_STYLES
    display = name.upper() if upper else name
    tracking = 8 if tracked else 1.5
    default_weight = "500" if fonts == FONT_STACKS["serif"] else "700"
    weight = "900" if variant == "brutalist" else font_weight(typography, default_weight)
    italic = ' font-style="italic"' if variant == "slant" else ""
    bg, text = palette["background"], palette["text"]
    # Tagline: lighter, smaller (<= 0.4x the name), and less tracked than the name
    tag_extra = ' font-weight="500" letter-spacing="2"'
    tag_fs = 0.0

    if layout == "left":
        w, h = 960, 320
        mark_size = 160
        defs, mark = mark_svg(style, palette, name, mark_size)
        tx = 272
        avail = w - tx - 48
        fs = fit_size(display, 72, avail, tracking)
        name_el = text_el(tx, 164 if tagline else 190, display, fs, avail, tracking)
        if tagline:
            tag_fs = min(24, fs * 0.4)
            tag_el = text_el(tx, 211, tagline, tag_fs, avail, 2, extra=tag_extra)
        else:
            tag_el = ""
    elif layout == "stacked":
        w = 640
        mark_size, mark_y = 280, 64
        defs, mark = mark_svg(style, palette, name, mark_size)
        avail = w - 96
        fs = fit_size(display, 64, avail, tracking)
        # the name starts at the mark's actual bottom, not a fixed y
        name_y = mark_y + mark_size + fs * 0.78 + (26 if tagline else 12)
        name_el = text_el(w / 2, name_y, display, fs, avail, tracking, anchor="middle")
        if tagline:
            tag_fs = min(22, fs * 0.4)
            tag_y = name_y + tag_fs * 1.9
            if variant == "badge":  # heritage rules flanking the tagline
                half = estimate_width(tagline, tag_fs, 2) / 2 + 36
                ly = tag_y - 8
                tag_el = (f'<line x1="{w / 2 - half:.0f}" y1="{ly:.0f}" '
                          f'x2="{w / 2 - half + 22:.0f}" y2="{ly:.0f}" '
                          f'stroke="{text}" stroke-width="2"/>'
                          + text_el(w / 2, tag_y, tagline, tag_fs, avail, 2,
                                    anchor="middle", extra=tag_extra)
                          + f'<line x1="{w / 2 + half - 22:.0f}" y1="{ly:.0f}" '
                            f'x2="{w / 2 + half:.0f}" y2="{ly:.0f}" '
                            f'stroke="{text}" stroke-width="2"/>')
            else:
                tag_el = text_el(w / 2, tag_y, tagline, tag_fs, avail, 2,
                                 anchor="middle", extra=tag_extra)
            h = round(tag_y + tag_fs * 0.9 + 52)
        else:
            tag_el = ""
            h = round(name_y + fs * 0.32 + 52)
    else:  # inline wordmark
        w, h = 960, 260
        avail = w - 160
        fs = fit_size(display, 104, avail, tracking)
        name_y = 158 if tagline else 160
        name_el = text_el(w / 2, name_y, display, fs, avail, tracking, anchor="middle")
        if tagline:
            tag_fs = min(24, fs * 0.4)
            tag_y = name_y + fs * 0.48 + 14
            tag_el = text_el(w / 2, tag_y, tagline, tag_fs, avail, 2,
                             anchor="middle", extra=tag_extra)
        else:
            tag_el = ""
        if variant == "accent":  # Swiss poster square leading the name
            # placed off the same width estimate that sizes the name (or the
            # textLength cap), so it can never ride onto the first letter
            half = min(estimate_width(display, fs, tracking), avail) / 2
            sq, gap = fs * 0.26, fs * 0.30
            sq_fill = pick_legible((palette["accent"], text, palette["secondary"]), (bg,))
            mark = (f'<rect x="{w / 2 - half - gap - sq:.0f}" y="{name_y - fs * 0.49:.0f}" '
                    f'width="{sq:.0f}" height="{sq:.0f}" fill="{sq_fill}"/>')
        else:
            mark = ""
        defs = ""

    defs_block = f"<defs>{defs}</defs>" if defs else ""
    if not mark:
        mark_group = ""
    elif layout == "inline":  # the accent square is already in canvas coordinates
        mark_group = mark
    elif layout == "stacked":
        mark_group = f'<g transform="translate({(w - mark_size) / 2:.0f}, {mark_y})">\n    {mark}\n  </g>'
    else:
        mark_group = f'<g transform="translate(48, 80)">\n    {mark}\n  </g>'
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" \
width="{w}" height="{h}" role="img" aria-label="{html.escape(name)} logo">
  <title>{html.escape(name)} — {style["Style Name"]} logo</title>
  {defs_block}
  <rect width="{w}" height="{h}" fill="{bg}"/>
  {mark_group}
  <g font-family="{fonts}" font-weight="{weight}" fill="{text}"{italic} \
letter-spacing="{tracking}">
    {name_el}
    {tag_el}
  </g>
</svg>
'''


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "brand"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="generate.py",
        description="Compose a local SVG logo from a Style, a Palette, and a brand name.",
        epilog='The Palette is a name from data/logo/colors.csv or a tokens.css path. '
               'Run with --list to print every Style and Palette name.',
    )
    parser.add_argument("--name", help="brand name (required unless --list)")
    parser.add_argument("--style", help="Style name from data/logo/styles.csv")
    parser.add_argument("--palette", default=DEFAULT_PALETTE,
                        help=f"Palette name or tokens.css path (default: {DEFAULT_PALETTE})")
    parser.add_argument("--tagline", default="", help="optional tagline under the name")
    parser.add_argument("--out", help="output .svg path (default: <name>-logo.svg)")
    parser.add_argument("--list", action="store_true", help="list Styles and Palettes, then exit")
    args = parser.parse_args(argv)

    styles = load_catalog(DATA_DIR / "styles.csv", "Style Name")
    palettes = load_catalog(DATA_DIR / "colors.csv", "Palette Name")

    if args.list:
        print("Styles:")
        for row in styles:
            print(f"  {row['Style Name']:22} {row['Mark']}/{row['Container']}/{row['Layout']}")
        print("Palettes:")
        for row in palettes:
            print(f"  {row['Palette Name']}")
        return 0

    if not args.style:
        parser.error("--style is required unless --list")
    if not args.name or not args.name.strip():
        parser.error("--name is required and must not be blank")

    style = find_row(styles, "Style Name", args.style)
    palette_path = Path(args.palette)
    if palette_path.suffix.lower() == ".css" and palette_path.is_file():
        palette = palette_from_tokens_css(palette_path)
    else:
        palette = palette_from_row(find_row(palettes, "Palette Name", args.palette))

    svg = compose_svg(style, palette, args.name.strip(), args.tagline.strip())
    out = Path(args.out) if args.out else Path(f"{slugify(args.name)}-logo.svg")
    out.write_text(svg, encoding="utf-8")
    print(out.resolve())
    return 0


if __name__ == "__main__":
    sys.exit(main())
