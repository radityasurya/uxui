"""Smoke test for the brand skill's local SVG logo Generator.

Runs scripts/generate.py as a subprocess for one recipe per layout branch
(left, stacked, inline) plus the tokens.css palette path, and asserts each
output is well-formed SVG whose live ``<text>`` carries the brand name.
Also unit-tests the sizing estimator, the contrast guard, blank-name
rejection, and mark uniqueness across styles.csv directly on the module.
"""

import importlib.util
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
SCRIPT = SCRIPTS / "generate.py"

_spec = importlib.util.spec_from_file_location("generate", SCRIPT)
generate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(generate)

STYLES_CSV = generate.DATA_DIR / "styles.csv"
PALETTES_CSV = generate.DATA_DIR / "colors.csv"

# (style, args) pairs chosen to cover every layout and the fiddly variants:
# stacked+badge draws the flanking rules, inline+accent draws the Swiss square.
CASES = [
    (["--style", "Minimalist", "--palette", "Monochrome Gray"], "left"),
    (["--style", "Vintage Badge", "--palette", "Coffee Brew", "--tagline", "Roasters"], "stacked"),
    (["--style", "Swiss/International", "--palette", "Bold Red", "--tagline", "systems"], "inline"),
]

TOKENS_CSS = """\
:root {
  --color-primary: #123456;
  --color-secondary: #654321;
  --color-accent: #f97316;
  --color-bg: #abcdef;
  --color-text: #111111;
}
"""


def _generate(tmp_path: Path, name: str, *args: str) -> Path:
    out = tmp_path / f"{name}.svg"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--name", name, "--out", str(out), *args],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    return out


@pytest.mark.parametrize("extra_args", [c[0] for c in CASES], ids=[c[1] for c in CASES])
def test_generated_svg_is_wellformed_and_carries_the_name(tmp_path, extra_args):
    out = _generate(tmp_path, "TestCo", *extra_args)
    root = ET.parse(out).getroot()
    assert root.tag.endswith("svg")
    texts = [el.text or "" for el in root.iter() if el.tag.endswith("text")]
    assert any("testco" in t.lower() for t in texts), texts


def test_tokens_css_palette(tmp_path):
    tokens = tmp_path / "tokens.css"
    tokens.write_text(TOKENS_CSS, encoding="utf-8")
    out = _generate(tmp_path, "TestCo", "--style", "Minimalist", "--palette", str(tokens))
    root = ET.parse(out).getroot()
    bg = next(el for el in root.iter() if el.tag.endswith("rect"))
    assert bg.get("fill") == "#abcdef"  # --color-bg landed on the canvas


def test_list_prints_catalog():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--list"], capture_output=True, text=True,
    )
    assert proc.returncode == 0
    assert "Minimalist" in proc.stdout and "Palettes:" in proc.stdout


def test_unknown_style_fails_with_known_names():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--name", "X", "--style", "Nope"],
        capture_output=True, text=True,
    )
    assert proc.returncode != 0
    assert "Minimalist" in proc.stderr  # the error lists what is known


def _style_row(name: str) -> dict:
    return generate.find_row(generate.load_catalog(STYLES_CSV, "Style Name"),
                             "Style Name", name)


def _palette(name: str) -> dict:
    return generate.palette_from_row(
        generate.find_row(generate.load_catalog(PALETTES_CSV, "Palette Name"),
                          "Palette Name", name))


# The three stress lockups: wide Latin caps (left), a long Japanese name
# (stacked), and a W-heavy name in the inline layout that draws the Swiss
# accent square. (name, style, base font size, available width)
STRESS = [
    ("MMMMWWWWMMMMWWWW", "Minimalist", 72, 960 - 272 - 48),
    ("株式会社テクノロジーソリューションズ", "Luxury/Premium", 64, 640 - 96),
    ("WWW Maximum", "Swiss/International", 104, 960 - 160),
]


@pytest.mark.parametrize("name,style,base,avail", STRESS, ids=[s[1] for s in STRESS])
def test_stress_names_fit_the_available_width(tmp_path, name, style, base, avail):
    row = _style_row(style)
    display = name.upper() if row["Style Name"] in generate.UPPERCASE_STYLES else name
    tracking = 8 if row["Style Name"] in generate.TRACKED_STYLES else 1.5
    fs = generate.fit_size(display, base, avail, tracking)
    assert generate.estimate_width(display, fs, tracking) <= avail

    out = _generate(tmp_path, name, "--style", style)
    root = ET.parse(out).getroot()
    group = next(g for g in root.iter()
                 if g.tag.endswith("g") and g.get("letter-spacing"))
    el = next(t for t in group if (t.text or "") == display)
    est = generate.estimate_width(display, float(el.get("font-size")),
                                  float(group.get("letter-spacing")))
    # capped with textLength, or comfortably inside the usable width
    assert est <= avail or el.get("textLength") is not None
    assert float(el.get("textLength", avail)) <= avail


@pytest.mark.parametrize("palette_name", ["Midnight Dark", "Obsidian Dark",
                                          "Pastel Rainbow"])
def test_illegible_primary_is_replaced_inside_the_mark(palette_name):
    palette = _palette(palette_name)
    assert not generate.legible_on(palette["primary"], palette["background"])
    for style_name in ("Minimalist", "Geometric", "Lettermark", "Monoline",
                       "Luxury/Premium"):
        defs, mark = generate.mark_svg(_style_row(style_name), palette, "Aurora", 160)
        assert palette["primary"] not in f"{defs}{mark}", style_name


def test_blank_name_fails_with_a_clear_error():
    for blank in ("   ", ""):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--name", blank, "--style", "Minimalist"],
            capture_output=True, text=True,
        )
        assert proc.returncode != 0, blank
        assert "blank" in (proc.stderr + proc.stdout).lower()


def test_no_two_styles_render_the_same_mark():
    styles = generate.load_catalog(STYLES_CSV, "Style Name")
    palette = _palette("Classic Blue Trust")
    marks: dict[str, str] = {}
    svgs: dict[str, str] = {}
    for row in styles:
        if row["Mark"] != "wordmark":  # wordmark rows carry no symbol by design
            defs, mark = generate.mark_svg(row, palette, "Aurora", 160)
            assert mark not in marks, (row["Style Name"], marks[mark])
            marks[mark] = row["Style Name"]
        svg = generate.compose_svg(row, palette, "Aurora", "Studio")
        assert svg not in svgs, (row["Style Name"], svgs[svg])
        svgs[svg] = row["Style Name"]
