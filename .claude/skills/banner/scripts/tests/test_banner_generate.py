"""Tests for the banner Generator: catalog shape, exact-size output, safety."""

import csv
import re
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

import generate  # noqa: E402

SEARCH_STYLES = SCRIPTS.parent.parent / "search" / "data" / "styles.csv"


def _styles() -> list[dict]:
    with generate.STYLES_CSV.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def test_catalog_matches_search_header_shape():
    """The banner catalog must reuse the search catalog's column contract."""
    with SEARCH_STYLES.open("r", encoding="utf-8", newline="") as fh:
        expected = next(csv.reader(fh))
    with generate.STYLES_CSV.open("r", encoding="utf-8", newline="") as fh:
        actual = next(csv.reader(fh))
    assert actual == expected


def test_catalog_has_ten_active_banner_styles():
    rows = _styles()
    assert len(rows) == 10
    assert all(r["Type"] == "Banner" for r in rows)
    assert all(r["Status"] == "active" for r in rows)
    assert len({r["Style ID"] for r in rows}) == 10


@pytest.mark.parametrize("style_id,size", [
    ("minimalist", "twitter-header"),      # 1500x500
    ("neon-glow", "email-header"),         # 600x200
    ("bold-typography", "instagram-post"), # 1080x1080
    ("dark-luxe", "300x250"),              # literal WxH
])
def test_output_carries_exact_pixel_dimensions(style_id, size):
    styles = generate.load_styles()
    w, h = generate.parse_size(size)
    palette = generate._fill_palette_defaults({})  # no colors.csv dependency
    html = generate.build_html(styles[style_id], palette, w, h, "H", "S", "C")
    assert f"width:{w}px;height:{h}px" in html


def test_strip_sizes_drop_the_subhead():
    styles = generate.load_styles()
    palette = generate._fill_palette_defaults({})
    html = generate.build_html(styles["minimalist"], palette, 728, 90, "H", "S", "C")
    assert '<p class="sub">' not in html


def test_mobile_banner_copy_fits_the_strip():
    """Regression: 320x50 clipped the headline (taste review blocker).

    Vertical budget: top+bottom padding plus one headline line at its
    computed font-size and line-height must fit the 50px canvas.
    """
    import re

    styles = generate.load_styles()
    palette = generate._fill_palette_defaults({})
    html = generate.build_html(styles["minimalist"], palette, 320, 50, "H", "S", "C")
    pad = int(re.search(r"\.inner\{[^}]*padding:(\d+)px", html).group(1))
    h1 = int(re.search(r"h1\{font-size:(\d+)px", html).group(1))
    assert 2 * pad + 1.05 * h1 <= 50
    flat = re.sub(r"\s+", "", html)  # CSS template wraps mid-rule
    assert "flex-direction:row;align-items:center" in flat  # strips center vertically


def test_copy_is_html_escaped():
    styles = generate.load_styles()
    palette = generate._fill_palette_defaults({})
    html = generate.build_html(
        styles["flat-solid"], palette, 300, 250,
        "<script>x</script>", "", "A & B")
    assert "<script>" not in html
    assert "A &amp; B" in html


def test_palette_from_css_file(tmp_path):
    tokens = tmp_path / "tokens.css"
    tokens.write_text(
        ":root{--primary:#123456;--accent:#abcdef;--fg:#111111}",
        encoding="utf-8")
    palette = generate.load_palette(str(tokens))
    assert palette["primary"] == "#123456"
    assert palette["accent"] == "#abcdef"
    assert palette["foreground"] == "#111111"


def test_unknown_style_exits_with_error(capsys):
    with pytest.raises(SystemExit):
        generate.main(["--style", "nope", "--size", "300x250", "--headline", "H"])
    assert "unknown style" in capsys.readouterr().err


# ------------------------------------------------------- sizing caps (review)

def test_h1_capped_to_fit_the_longest_word():
    """Regression: at 160x600 'Infrastructure' clipped the right edge."""
    styles = generate.load_styles()
    palette = generate._fill_palette_defaults({})
    headline = "Infrastructure observability"
    html = generate.build_html(styles["minimalist"], palette, 160, 600,
                               headline, "", "Start trial")
    h1 = int(re.search(r"h1\{font-size:(\d+)px", html).group(1))
    pad = int(re.search(r"\.inner\{[^}]*padding:(\d+)px", html).group(1))
    longest = max(len(word) for word in headline.split())
    assert h1 * longest * 0.6 <= 160 - 2 * pad  # longest word fits the column
    assert "overflow-wrap:break-word" in html


def test_cta_font_size_capped_by_canvas_and_headline():
    """Regression: the CTA grew to 80px at 1080x1920 (height-driven only)."""
    styles = generate.load_styles()
    palette = generate._fill_palette_defaults({})
    html = generate.build_html(styles["minimalist"], palette, 1080, 1920,
                               "H", "S", "C")
    h1 = int(re.search(r"h1\{font-size:(\d+)px", html).group(1))
    cta = int(re.search(r"\.cta\{[^}]*font-size:(\d+)px", html).group(1))
    assert cta <= min(int(1920 * 0.042), int(1080 * 0.05), int(h1 * 0.45))
    assert cta < 80  # the pre-fix value at this size


def test_compact_pad_floor_is_12px():
    styles = generate.load_styles()
    palette = generate._fill_palette_defaults({})
    html = generate.build_html(styles["minimalist"], palette, 320, 50,
                               "H", "S", "C")
    pad = int(re.search(r"\.inner\{[^}]*padding:(\d+)px", html).group(1))
    assert pad >= 12


def test_strip_headline_wrap_warning(capsys):
    styles = generate.load_styles()
    palette = generate._fill_palette_defaults({})
    # 93 characters: past two lines even at the 12px floor
    long_headline = ("Infrastructure observability pipelines for platform "
                     "engineering teams across every cloud region")
    generate.build_html(styles["minimalist"], palette, 320, 50,
                        long_headline, "", "Go")
    assert "wrap" in capsys.readouterr().err
    generate.build_html(styles["minimalist"], palette, 320, 50,
                        "Ship faster", "", "Go")
    assert capsys.readouterr().err == ""


def test_gradient_wash_cta_chip_inverts():
    """Regression: primary chip on a primary gradient was 1.41:1."""
    styles = generate.load_styles()
    palette = generate._fill_palette_defaults({})
    html = generate.build_html(styles["gradient-wash"], palette, 300, 250,
                               "H", "S", "C")
    m = re.search(r"\.cta\{[^}]*background:([^;]+);color:([^;]+);", html)
    assert m.group(1) == "var(--on-primary)"
    assert m.group(2) == "var(--primary)"


# --------------------------------------------- WCAG contrast per Style

VAR = re.compile(r"var\(--([a-z-]+)\)")


def _rule(html: str, selector: str) -> str:
    m = re.search(re.escape(selector) + r"\{([^}]*)\}", html)
    return m.group(1) if m else ""


def _prop(rule: str, name: str, default: str | None = None) -> str | None:
    found = re.findall(rf"(?:^|[;\n]){name}:([^;]+)", rule)  # last wins
    return found[-1].strip() if found else default


def _resolve(value: str, palette: dict) -> str:
    m = VAR.fullmatch(value.strip())
    return palette[m.group(1).replace("-", "_")] if m else value.strip()


def _copy_backgrounds(style_id: str, palette: dict, html: str,
                      fg: str) -> list[str]:
    """Backgrounds the copy can sit on, composited as the CSS layers them."""
    bg = _prop(_rule(html, ".banner"), "background", "var(--background)")
    if not bg.startswith(("linear-gradient", "radial-gradient")):
        return [_resolve(bg, palette)]
    stops = [palette[m.group(1).replace("-", "_")] for m in VAR.finditer(bg)]
    stops += re.findall(r"#[0-9A-Fa-f]{6}", bg)
    if style_id == "gradient-wash":
        # radial white highlight (0.28) then the scrim ::after over it
        scrim = re.search(
            r"linear-gradient\(90deg,rgba\((\d+),(\d+),(\d+),([0-9.]+)\)", html)
        hex_scrim = "#{:02x}{:02x}{:02x}".format(*map(int, scrim.groups()[:3]))
        alpha = float(scrim.group(4))
        stops = [generate._mix(generate._mix(s, "#FFFFFF", 0.28),
                               hex_scrim, alpha) for s in stops]
    elif style_id == "glassmorphism":
        fill = re.search(r"\.inner\{background:rgba\(255,255,255,([0-9.]+)\)",
                         html)
        stops = [generate._mix(s, "#FFFFFF", float(fill.group(1)))
                 for s in stops]
    return stops  # worst stop is whichever minimizes contrast with fg


@pytest.mark.parametrize("style_id", [
    "minimalist", "bold-typography", "gradient-wash", "geometric-abstract",
    "glassmorphism", "neon-glow", "duotone-split", "editorial-grid",
    "flat-solid", "dark-luxe",
])
def test_headline_and_cta_contrast_per_style(style_id):
    """Headline and CTA meet WCAG AA against the default palette."""
    styles = generate.load_styles()
    palette = generate.load_palette("SaaS (General)")
    html = generate.build_html(styles[style_id], palette, 1500, 500,
                               "H", "S", "C")

    fg = _resolve(_prop(_rule(html, ".banner"), "color", ""), palette)
    field = min(_copy_backgrounds(style_id, palette, html, fg),
                key=lambda c: generate._contrast(fg, c))
    assert generate._contrast(fg, field) >= 4.5

    cta_bg = _prop(_rule(html, ".cta"), "background", "")
    cta_fg = _prop(_rule(html, ".cta"), "color", "")
    for override in re.findall(r"\.inner \.cta\{([^}]*)\}", html):
        cta_bg = _prop(override, "background", cta_bg)
        cta_fg = _prop(override, "color", cta_fg)
    if cta_bg == "transparent":
        cta_bg = field
    fs = int(re.search(r"\.cta\{[^}]*font-size:(\d+)px", html).group(1))
    need = 3.0 if fs >= 24 else 4.5  # WCAG large-text threshold
    assert generate._contrast(_resolve(cta_fg, palette),
                              _resolve(cta_bg, palette)) >= need
