#!/usr/bin/env python3
"""Banner Generator: write an HTML/CSS banner at exact platform pixel size.

Consumes a Style from ``../data/styles.csv``, a Palette (by name, resolved
against the sibling search skill's color catalog, or as a CSS custom-property
file such as a tokens.css), a platform size slug from
``../references/banner-sizes-and-styles.md`` (or a literal ``WxH``), and the
banner copy. Standard library only; no network, no image API.

Run from this skill's directory:

    python3 scripts/generate.py --style gradient-wash --palette "SaaS (General)" \
        --size twitter-header --headline "Ship design faster" \
        --subhead "One search for styles, palettes, and guidelines" \
        --cta "Start free" -o banner.html

Then render-check the output from the repository root:
``scripts/render-check.py banner.html --window-size WxH`` screenshots it at
the exact pixel size.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from html import escape
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
STYLES_CSV = SKILL_DIR / "data" / "styles.csv"
COLORS_CSV = SKILL_DIR.parent / "search" / "data" / "colors.csv"

# Digital sizes from references/banner-sizes-and-styles.md: slug -> (width, height).
SIZES = {
    "facebook-cover": (820, 312),
    "facebook-cover-mobile": (640, 360),
    "facebook-event": (1920, 1080),
    "twitter-header": (1500, 500),
    "twitter-ad": (800, 418),
    "linkedin-company": (1128, 191),
    "linkedin-personal": (1584, 396),
    "youtube-channel": (2560, 1440),
    "youtube-safe": (1546, 423),
    "instagram-story": (1080, 1920),
    "instagram-post": (1080, 1080),
    "pinterest-pin": (1000, 1500),
    "medium-rectangle": (300, 250),
    "leaderboard": (728, 90),
    "wide-skyscraper": (160, 600),
    "half-page": (300, 600),
    "large-rectangle": (336, 280),
    "mobile-banner": (320, 50),
    "large-mobile": (320, 100),
    "billboard": (970, 250),
    "section-banner": (1200, 400),
    "blog-header": (1200, 628),
    "email-header": (600, 200),
    "website-hero": (1920, 600),
}

PALETTE_SLOTS = (
    "primary", "on_primary", "secondary", "on_secondary",
    "accent", "on_accent", "background", "foreground",
)

# CSS custom-property names accepted in a tokens file, normalized to slots.
CSS_KEY_ALIASES = {
    "fg": "foreground", "text": "foreground", "bg": "background",
    "foreground_on_primary": "on_primary", "foreground_on_accent": "on_accent",
    "on_fg": "foreground", "on_bg": "background",
}

CSS_VAR_RE = re.compile(r"--([A-Za-z0-9-]+)\s*:\s*([^;}]+)[;}]")
HEX_RE = re.compile(r"^#(?:[0-9A-Fa-f]{3,4}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$")

SANS = "system-ui,-apple-system,'Segoe UI',Roboto,Arial,sans-serif"
SERIF = "Georgia,'Times New Roman',serif"


# ---------------------------------------------------------------- data loading

def load_styles() -> dict[str, dict]:
    """Index styles.csv rows by Style ID and every alias, lowercase."""
    styles: dict[str, dict] = {}
    with STYLES_CSV.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            styles[row["Style ID"].strip().lower()] = row
            for alias in row.get("Aliases", "").split("|"):
                if alias.strip():
                    styles[alias.strip().lower()] = row
    return styles


def _normalize_key(key: str) -> str:
    key = key.lower().removeprefix("color-").replace("-", "_")
    return CSS_KEY_ALIASES.get(key, key)


def _palette_from_css(text: str) -> dict[str, str]:
    palette: dict[str, str] = {}
    for name, value in CSS_VAR_RE.findall(text):
        slot = _normalize_key(name)
        value = value.strip()
        if slot in PALETTE_SLOTS and HEX_RE.match(value):
            palette[slot] = value
    return palette


def _fill_palette_defaults(palette: dict[str, str]) -> dict[str, str]:
    palette.setdefault("primary", palette.get("accent", "#2563EB"))
    palette.setdefault("on_primary", "#FFFFFF")
    palette.setdefault("secondary", palette["primary"])
    palette.setdefault("on_secondary", palette["on_primary"])
    palette.setdefault("accent", palette["primary"])
    palette.setdefault("on_accent", palette["on_primary"])
    palette.setdefault("background", "#FFFFFF")
    palette.setdefault("foreground", "#111827")
    return palette


def load_palette(spec: str) -> dict[str, str]:
    """Resolve --palette: an existing CSS file by path, else a catalog name."""
    path = Path(spec)
    if path.is_file():
        return _fill_palette_defaults(_palette_from_css(path.read_text(encoding="utf-8")))
    if COLORS_CSV.is_file():
        with COLORS_CSV.open("r", encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                if spec.lower() in row["Product Type"].lower():
                    return {
                        "primary": row["Primary"], "on_primary": row["On Primary"],
                        "secondary": row["Secondary"], "on_secondary": row["On Secondary"],
                        "accent": row["Accent"], "on_accent": row["On Accent"],
                        "background": row["Background"], "foreground": row["Foreground"],
                    }
    raise SystemExit(
        f"error: palette {spec!r} is neither an existing file nor a name in "
        f"{COLORS_CSV} (search the 'color' domain for names)"
    )


# ------------------------------------------------------------------ color math

def _channels(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _mix(a: str, b: str, t: float) -> str:
    """Blend hex colors; t=0 is a, t=1 is b."""
    ca, cb = _channels(a), _channels(b)
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))


def _shade(hex_color: str, t: float) -> str:
    """Blend toward black; _shade(c, 0.1) keeps 10% of the color."""
    return _mix(hex_color, "#000000", 1.0 - t)


def _tint(hex_color: str, t: float) -> str:
    """Blend toward white; _tint(c, 0.9) is 90% white."""
    return _mix(hex_color, "#FFFFFF", t)


def _rgba(hex_color: str, alpha: float) -> str:
    r, g, b = _channels(hex_color)
    return f"rgba({r},{g},{b},{alpha})"


def _lum(hex_color: str) -> float:
    """WCAG relative luminance of a hex color."""
    total = 0.0
    for coeff, ch in zip((0.2126, 0.7152, 0.0722), _channels(hex_color)):
        c = ch / 255
        total += coeff * (c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return total


def _contrast(a: str, b: str) -> float:
    """WCAG 2.x contrast ratio between two hex colors."""
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# ---------------------------------------------------------------- style recipes
# Each recipe takes the palette dict and returns CSS fragments. The palette is
# authoritative for color; the recipe only shapes it (CONTEXT.md: a Generator
# consumes a Design system).

def _recipe(style_id: str, p: dict, w: int, h: int, pad: int) -> dict:
    """Return the per-Style treatment: fonts, colors, decor CSS, layout."""
    ring = max(4, min(w, h) // 60)
    top_rule = min(10, max(8, min(w, h) // 40))
    r: dict = {
        "fg": "var(--foreground)", "cta_bg": "var(--primary)",
        "cta_fg": "var(--on-primary)", "cta_css": "", "h1_css": "",
        "inner_css": "", "banner_css": "", "decor_css": "", "align": "left",
        "show_rule": False, "serif": False, "inset_y": 0,
        # Copy-column width as a fraction of the canvas width.
        "h1_max": 0.86, "sub_max": 0.70,
    }

    if style_id == "minimalist":
        r["decor_css"] = ""
        r["show_rule"] = True
    elif style_id == "bold-typography":
        r["h1_css"] = "text-transform:uppercase;letter-spacing:-0.03em"
        r["cta_css"] = (
            "background:transparent;color:var(--accent);padding:0;"
            "border:0;border-bottom:4px solid var(--accent);border-radius:0"
        )
    elif style_id == "gradient-wash":
        # A scrim under the copy holds on-primary text at 4.5:1 on the
        # lightest stop, radial highlight included. Its strength is the
        # weakest blend that passes against the worst stop.
        scrim = "#FFFFFF" if _lum(p["on_primary"]) < 0.5 else "#000000"
        stops = (p["primary"], p["secondary"], p["accent"])
        if scrim == "#000000":
            worst = max((_mix(s, "#FFFFFF", 0.28) for s in stops), key=_lum)
        else:  # dark text: the white highlight helps, so the raw stop is worst
            worst = min(stops, key=_lum)
        alpha = 1.0
        for step in range(21):
            if _contrast(p["on_primary"], _mix(worst, scrim, step / 20)) >= 4.5:
                alpha = step / 20
                break
        r["banner_css"] = (
            "background:linear-gradient(115deg,var(--primary) 0%,"
            "var(--secondary) 55%,var(--accent) 100%)"
        )
        r["fg"] = "var(--on-primary)"
        r["cta_bg"], r["cta_fg"] = "var(--on-primary)", "var(--primary)"
        r["h1_max"], r["sub_max"] = 0.55, 0.50  # copy stays on the scrim
        r["decor_css"] = (
            ".decor::before{content:'';position:absolute;inset:0;"
            "background:radial-gradient(circle at 78% 22%,"
            "rgba(255,255,255,0.28),transparent 42%)}"
            ".decor::after{content:'';position:absolute;inset:0;"
            f"background:linear-gradient(90deg,{_rgba(scrim, alpha)} 0%,"
            f"{_rgba(scrim, alpha)} 72%,{_rgba(scrim, 0)} 95%)}}"
        )
    elif style_id == "geometric-abstract":
        r["decor_css"] = (
            ".decor::before{content:'';position:absolute;right:-12%;top:-28%;"
            f"width:56%;aspect-ratio:1;border-radius:50%;"
            "background:var(--secondary);opacity:.45}"
            f".decor::after{{content:'';position:absolute;left:-10%;bottom:-35%;"
            f"width:44%;aspect-ratio:1;border-radius:50%;"
            f"border:{ring}px solid var(--accent);opacity:.55}}"
        )
    elif style_id == "glassmorphism":
        # Stops shaded to 0.6 keep white text at 4.5:1 under the 16% glass
        # fill; the panel is inset by pad so it never fills the canvas.
        inset = 0 if h <= 100 else pad  # strips keep the full-bleed panel
        r["banner_css"] = (
            f"background:linear-gradient(135deg,{_shade(p['secondary'], 0.6)},"
            f"{_shade(p['primary'], 0.6)})"
        )
        r["fg"] = "var(--on-primary)"
        r["cta_bg"], r["cta_fg"] = "var(--accent)", "var(--on-accent)"
        # Solid panel by default; the frosted glass applies only where the
        # engine supports blur (the row's no-blur fallback).
        r["inner_css"] = (
            f"background:{_rgba(p['primary'], 0.85)};"
            "border:1px solid rgba(255,255,255,0.4);border-radius:18px;"
            f"margin:{inset}px;max-width:{w - 2 * inset}px;"
            f"max-height:{h - 2 * inset}px"
        )
        r["decor_css"] = (
            "@supports (backdrop-filter:blur(1px))"
            "or (-webkit-backdrop-filter:blur(1px))"
            "{.inner{background:rgba(255,255,255,0.16);"
            "backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px)}}"
        )
        # Copy column = the panel's content box (border-box: inset, padding,
        # 1px border), so text never crosses the glass edge.
        col = (w - 2 * inset - 2 * pad - 2) / w
        r["h1_max"] = min(r["h1_max"], col)
        r["sub_max"] = min(r["sub_max"], col)
        r["inset_y"] = inset
    elif style_id == "neon-glow":
        dark = _shade(p["primary"], 0.10)
        r["banner_css"] = (
            f"background:radial-gradient(circle at 50% 45%,"
            f"{_shade(p['primary'], 0.22)}, {dark} 78%)"
        )
        r["fg"] = _tint(p["accent"], 0.35)
        r["h1_css"] = (
            f"text-shadow:0 0 8px {_rgba(p['accent'], 0.9)},"
            f"0 0 26px {_rgba(p['accent'], 0.55)}"
        )
        r["cta_css"] = (
            f"background:transparent;border:2px solid var(--accent);"
            f"color:{_tint(p['accent'], 0.55)};"
            f"box-shadow:0 0 18px {_rgba(p['accent'], 0.6)}"
        )
    elif style_id == "duotone-split":
        r["banner_css"] = "background:var(--primary)"
        r["fg"] = "var(--on-primary)"
        r["cta_bg"], r["cta_fg"] = "var(--on-primary)", "var(--primary)"
        r["h1_max"] = r["sub_max"] = 0.60  # headline sits on one field only
        r["decor_css"] = (
            ".decor::before{content:'';position:absolute;top:-10%;bottom:-10%;"
            "right:-6%;width:34%;background:var(--accent);transform:skewX(-12deg)}"
        )
    elif style_id == "editorial-grid":
        r["serif"] = True
        r["banner_css"] = (
            f"border-top:{top_rule}px solid var(--foreground);"
            "border-bottom:1px solid var(--secondary)"
        )
        r["show_rule"] = True
        # An underlined link in foreground, not a rounded pill.
        r["cta_css"] = (
            "background:transparent;color:var(--foreground);padding:0;"
            "border:0;border-bottom:2px solid var(--foreground);border-radius:0"
        )
    elif style_id == "flat-solid":
        r["banner_css"] = "background:var(--primary)"
        r["fg"] = "var(--on-primary)"
        r["cta_bg"], r["cta_fg"] = "var(--background)", "var(--foreground)"
        r["align"] = "center"
    elif style_id == "dark-luxe":
        r["serif"] = True
        r["banner_css"] = f"background:{_shade(p['foreground'], 0.14)}"
        r["fg"] = _tint(p["foreground"], 0.92)
        r["show_rule"] = True
        frame = max(8, min(w, h) // 18)
        r["decor_css"] = (
            ".decor::before{content:'';position:absolute;"
            f"inset:{frame}px;border:1px solid {_rgba(p['accent'], 0.5)}"
            "}"
        )
        r["cta_css"] = (
            "background:transparent;border:1px solid var(--accent);"
            f"color:{_tint(p['accent'], 0.4)}"
        )
    return r


# ------------------------------------------------------------------- rendering

def build_html(style: dict, palette: dict, w: int, h: int, headline: str,
               subhead: str, cta: str) -> str:
    style_id = style["Style ID"].strip()
    compact = h <= 100  # strip-shaped units: headline + CTA on one row
    pad = max(12 if compact else 16, min(96, int(min(w, h) * 0.10)))
    r = _recipe(style_id, palette, w, h, pad)

    h1_factor = 0.26 if style_id == "bold-typography" else 0.16
    w_factor = 0.20 if style_id == "bold-typography" else 0.11
    h1 = max(16 if compact else 24, min(int(h * h1_factor), int(w * w_factor)))
    # Cap so the longest word fits the copy column (narrow-canvas fix).
    longest = max((len(word) for word in headline.split()), default=1)
    h1 = min(h1, int(min(w - 2 * pad, int(w * r["h1_max"])) / (longest * 0.6)))
    sub = max(15, min(int(h * 0.05), int(w * 0.035)))
    cta_fs = max(11 if compact else 13,
                 min(int(h * 0.042), int(w * 0.05), int(h1 * 0.45)))
    gap = max(8, h // 28)

    # Vertical fit: the copy stack must fit the panel's content box, the
    # same budget the horizontal cap uses (0.6em per character estimate).
    budget = h - 2 * pad - 2 * r["inset_y"]
    col_px = min(w - 2 * pad, int(w * r["h1_max"]))
    sub_px = int(w * r["sub_max"])
    cta_h = cta_fs + 2 * max(6, cta_fs // 2)

    def _stack(v: int) -> float:
        lines = 1
        if headline:
            cpl = max(1, col_px // max(1, int(0.6 * v)))
            lines = max(1, -(-len(headline) // cpl))
        h1_h = 1.05 * v * lines
        sub_h = 0.0
        if subhead and not compact:
            s_cpl = max(1, sub_px // max(1, int(0.6 * sub)))
            sub_h = 1.4 * sub * max(1, -(-len(subhead) // s_cpl))
        # compact is a row: the gap runs between items, not under them
        return max(h1_h, cta_h) if compact else h1_h + sub_h + cta_h + 2 * gap

    while h1 > 12 and _stack(h1) > budget:
        h1 -= 1
        cta_fs = min(cta_fs, max(11 if compact else 13, int(h1 * 0.45)))
        cta_h = cta_fs + 2 * max(6, cta_fs // 2)
    if compact and _stack(h1) > budget:
        print(f"warning: at {w}x{h} the headline will likely wrap past two "
              "lines; use a shorter headline or a larger size", file=sys.stderr)
    align = "center" if compact or r["align"] == "center" else "flex-start"
    stack = SERIF if r["serif"] else SANS
    sub_style = "font-style:italic" if r["serif"] else ""

    vars_css = ";".join(
        f"--{slot.replace('_', '-')}:{palette[slot]}" for slot in PALETTE_SLOTS
    )
    label = escape(". ".join(x for x in (headline, subhead, cta) if x), quote=True)

    rule = (
        f'<div class="rule" aria-hidden="true"></div>' if r["show_rule"] and not compact else ""
    )
    sub_html = (
        f'<p class="sub">{escape(subhead)}</p>' if subhead and not compact else ""
    )
    cta_html = f'<span class="cta">{escape(cta)}</span>' if cta else ""
    inner_extra = r["inner_css"]
    cta_override = f".inner .cta{{{r['cta_css']}}}" if r["cta_css"] else ""
    if style_id == "bold-typography" and cta_fs < 24:
        cta_override += ".inner .cta{color:var(--foreground)}"  # accent 3.4:1
    h1_override = f".inner h1{{{r['h1_css']}}}" if r["h1_css"] else ""

    direction = "row" if compact else "column"

    css = f"""
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{background:var(--background)}}
.banner{{position:relative;width:{w}px;height:{h}px;overflow:hidden;
display:flex;align-items:center;{vars_css};background:var(--background);
color:{r['fg']};font-family:{stack};{r['banner_css']}}}
.decor{{position:absolute;inset:0;z-index:1}}
{r['decor_css']}
.inner{{position:relative;z-index:2;display:flex;flex-direction:{direction};
align-items:{align};gap:{gap}px;padding:{pad}px;max-width:100%;{inner_extra}}}
.rule{{width:64px;height:4px;background:var(--accent)}}
h1{{font-size:{h1}px;line-height:1.05;font-weight:800;max-width:{int(w * r['h1_max'])}px;overflow-wrap:break-word}}
.sub{{font-size:{sub}px;line-height:1.4;max-width:{int(w * r['sub_max'])}px;{sub_style}}}
.cta{{display:inline-block;background:{r['cta_bg']};color:{r['cta_fg']};
font-size:{cta_fs}px;font-weight:600;padding:{max(6, cta_fs // 2)}px {max(14, cta_fs)}px;
border-radius:{gap}px;text-decoration:none;white-space:nowrap}}
{cta_override}
{h1_override}
""".strip()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{escape(headline)}</title>
<style>
{css}
</style>
</head>
<body>
<div class="banner" role="img" aria-label="{label}">
<div class="decor" aria-hidden="true"></div>
<div class="inner">
{rule}<h1>{escape(headline)}</h1>
{sub_html}{cta_html}
</div>
</div>
</body>
</html>
"""


# ------------------------------------------------------------------------ main

def parse_size(spec: str) -> tuple[int, int]:
    if spec in SIZES:
        return SIZES[spec]
    match = re.fullmatch(r"(\d{2,5})x(\d{2,5})", spec)
    if match:
        w, h = int(match[1]), int(match[2])
        if w > 0 and h > 0:
            return w, h
    raise SystemExit(
        f"error: unknown size {spec!r}. Use a platform slug "
        f"({', '.join(SIZES)}) or a literal WxH such as 1500x500."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="generate.py",
        description="Write an HTML/CSS banner at exact platform pixel size.",
        epilog="Sizes and Styles come from ../references/banner-sizes-and-styles.md "
               "and ../data/styles.csv; Palettes from the sibling search skill's "
               "color catalog or any CSS custom-property file. "
               "--subhead is dropped at strip sizes (height 100px and below).",
    )
    parser.add_argument("--style", help="Style ID or alias from data/styles.csv")
    parser.add_argument("--palette",
                        help="Palette name from the search skill's color catalog, "
                             "or a path to a CSS custom-property file (tokens.css)")
    parser.add_argument("--size", help="platform slug (e.g. twitter-header) or WxH")
    parser.add_argument("--headline", default="")
    parser.add_argument("--subhead", default="")
    parser.add_argument("--cta", default="")
    parser.add_argument("-o", "--output",
                        help="output .html path (default: <style>-<W>x<H>.html)")
    parser.add_argument("--list", action="store_true",
                        help="list every Style ID and size slug, then exit")
    args = parser.parse_args(argv)

    if args.list:
        print("Styles:", ", ".join(sorted(set(
            row["Style ID"] for row in load_styles().values()))))
        print("Sizes:", ", ".join(
            f"{slug} ({w}x{h})" for slug, (w, h) in SIZES.items()))
        return 0

    styles = load_styles()
    if not args.headline:
        parser.error("--headline is required (unless --list)")
    style = styles.get((args.style or "").strip().lower())
    if style is None:
        parser.error(
            f"unknown style {args.style!r}; known: "
            + ", ".join(sorted(set(r["Style ID"] for r in styles.values())))
        )
    w, h = parse_size(args.size) if args.size else (0, 0)
    if w == 0:
        parser.error("--size is required (unless --list)")
    palette = load_palette(args.palette or "SaaS (General)")

    html = build_html(style, palette, w, h, args.headline, args.subhead, args.cta)

    out = Path(args.output) if args.output else Path(
        f"{style['Style ID']}-{w}x{h}.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} ({w}x{h}, style {style['Style ID']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
