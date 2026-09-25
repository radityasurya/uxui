"""Tests for the uxui:icon Generator (.claude/skills/icon/scripts/generate.py).

Run with pytest or `python3 -m unittest discover -s scripts/tests`. Checks the
three semantic roles' accessibility attributes and a few Style behaviors the
catalog drives; everything the Generator writes must parse as SVG.
"""

import contextlib
import importlib.util
import io
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

SCRIPT = (Path(__file__).resolve().parents[2]
          / ".claude" / "skills" / "icon" / "scripts" / "generate.py")
_spec = importlib.util.spec_from_file_location("icon_generate", SCRIPT)
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)

SVG_NS = "{http://www.w3.org/2000/svg}"


class IconGenerateTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def generate(self, **cli) -> tuple[ET.Element, str]:
        out = self.dir / "icon.svg"
        code = gen.main([
            "--prompt", cli.pop("prompt", "settings gear"),
            "--title", "Settings",
            "--output", str(out), *sum(([f"--{k}", str(v)] for k, v in cli.items()), []),
        ])
        self.assertEqual(code, 0)
        return ET.parse(out).getroot(), out.read_text(encoding="utf-8")

    def test_every_style_and_role_parses(self):
        for style in gen.load_styles():
            for role in gen.ROLES:
                root, _ = self.generate(style=style, role=role)
                self.assertEqual(root.tag, f"{SVG_NS}svg", f"{style}/{role}")

    def test_decorative_role_is_hidden_with_no_title(self):
        root, text = self.generate(role="decorative")
        self.assertEqual(root.get("aria-hidden"), "true")
        self.assertEqual(root.get("focusable"), "false")
        self.assertNotIn("<title", text)

    def test_meaningful_role_has_img_role_and_labelled_title(self):
        root, text = self.generate(role="meaningful")
        self.assertEqual(root.get("role"), "img")
        title_id = root.get("aria-labelledby")
        title = root.find(f"{SVG_NS}title")
        self.assertEqual(title.get("id"), title_id)
        self.assertEqual(title.text, "Settings")
        self.assertIn('id="%s"' % title_id, text)

    def test_interactive_role_stays_hidden_and_emits_wrapper_guidance(self):
        root, text = self.generate(role="interactive")
        self.assertEqual(root.get("aria-hidden"), "true")
        self.assertIn("<button", text)          # wrapper guidance comment
        self.assertNotIn("<title", text)        # the wrapper carries the name

    def test_catalog_drives_stroke_weight(self):
        bold, _ = self.generate(style="bold")
        thin, _ = self.generate(style="thin")
        widths = lambda root: {e.get("stroke-width") for e in root.iter()
                               if e.get("stroke-width")}
        self.assertIn("3", widths(bold))
        self.assertIn("1.5", widths(thin))

    def test_duotone_secondary_layer_is_30_percent(self):
        root, _ = self.generate(style="duotone")
        self.assertTrue(any(e.get("fill-opacity") == "0.3" for e in root.iter()))

    def test_pixel_style_snaps_to_grid(self):
        root, _ = self.generate(style="pixel")
        for circle in root.iter(f"{SVG_NS}circle"):
            for key in ("cx", "cy", "r"):
                self.assertEqual(float(circle.get(key)) % 3, 0, key)

    def test_unknown_prompt_is_an_error_not_a_guess(self):
        with self.assertRaises(SystemExit):
            gen.pick_glyph("a very abstract concept with no match")

    def test_ids_differ_when_inlined_icons_differ(self):
        """Two inlined icons must not share gradient/title ids (review #1)."""
        _, a = self.generate(style="gradient", color="#6366F1")
        _, b = self.generate(style="gradient", color="#ec4899")
        id_of = lambda text: re.search(r'linearGradient id="([^"]+)"', text).group(1)
        self.assertNotEqual(id_of(a), id_of(b))

    def test_pixel_mode_keeps_hex_colors(self):
        """Quantization must not touch paint attributes (review #2)."""
        root, _ = self.generate(style="pixel", color="#6366F1")
        for element in root.iter():
            for key in ("fill", "stroke"):
                self.assertNotEqual(element.get(key), "#6366F3")

    def test_fill_mode_renders_ink_silhouette_only(self):
        """Solid styles drop the detail layer instead of hiding it (review #3)."""
        root, _ = self.generate(style="filled")
        radii = sorted(circle.get("r") for circle in root.iter(f"{SVG_NS}circle"))
        self.assertEqual(radii, ["6.6"])  # hub detail circle absent

    def test_open_paths_carry_fill_none_in_every_style(self):
        """Open paths must never inherit the default black fill (review item 1)."""
        for style in gen.load_styles():
            root, _ = self.generate(prompt="check done", style=style)
            stroked = [e for e in root.iter() if e.get("stroke")]
            self.assertTrue(stroked, style)
            for element in stroked:
                self.assertEqual(element.get("fill"), "none",
                                 f"{style}: {element.tag}")

    def test_zero_csv_width_falls_back_to_default(self):
        """A stroke-based Style with width 0 must not erase strokes (item 2)."""
        svg = gen.compose_svg("check", "probe",
                              {"stroke_width": "0", "fill": "dual"},
                              "decorative", "Probe", "currentColor", 24)
        self.assertIn('stroke-width="2"', svg)
        root, _ = self.generate(prompt="check done", style="duotone")
        self.assertTrue(any(e.get("stroke-width") == "2" for e in root.iter()))

    def test_solid_styles_keep_primary_geometry(self):
        """Glyph parts that identify the glyph must sit on ink, not detail
        (review item 3: user was a dot, bell lost its clapper, cart its
        wheels, download its tray)."""
        for glyph in ("user", "bell", "cart", "download"):
            root, _ = self.generate(name=glyph, style="filled")
            drawn = [e for e in root.iter()
                     if e.tag.rsplit("}", 1)[-1] not in ("svg", "g", "title")]
            self.assertEqual(len(drawn), len(gen.GLYPHS[glyph]), glyph)

    def test_hand_filter_region_covers_straight_lines(self):
        """Percent filter regions collapse on a straight line's zero-size
        bbox and the line disappears; the region must be userSpaceOnUse
        (review item 4)."""
        root, _ = self.generate(prompt="plus add", style="hand-drawn")
        filt = root.find(f"{SVG_NS}defs/{SVG_NS}filter")
        self.assertEqual(filt.get("filterUnits"), "userSpaceOnUse")
        self.assertEqual((filt.get("x"), filt.get("y"),
                          filt.get("width"), filt.get("height")),
                         ("0", "0", "24", "24"))

    def test_hostile_title_yields_valid_xml_and_escaped_guidance(self):
        """A --title with quotes, angle brackets, or -- must not break the
        file or the printed wrapper guidance (review item 5)."""
        out = self.dir / "icon.svg"
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = gen.main(["--name", "download", "--style", "outlined",
                             "--role", "interactive",
                             "--title", 'Save -- "draft" <v2>',
                             "--output", str(out)])
        self.assertEqual(code, 0)
        ET.parse(out)  # raises on the illegal "--" inside the comment
        text = out.read_text(encoding="utf-8")
        self.assertIn("Save – ", text)          # "--" neutralized in the comment
        self.assertNotIn("Save --", text)
        guidance = stdout.getvalue()
        self.assertIn("&quot;draft&quot;", guidance)  # quotes escaped in print
        self.assertNotIn('"draft"', guidance)

    def test_solid_styles_are_differentiated(self):
        """filled, flat, glyph must not render identically (review item 7)."""
        _, filled = self.generate(prompt="home house", style="filled")
        _, flat = self.generate(prompt="home house", style="flat")
        _, glyph = self.generate(prompt="home house", style="glyph")
        self.assertIn("<mask", flat)                  # detail cut as holes
        self.assertIn('stroke-width="2.5"', glyph)    # heavier open paths
        self.assertNotIn("<mask", filled)
        self.assertNotIn('stroke-width="2.5"', filled)

    def test_overbroad_keywords_are_gone(self):
        """Short generic words must not hijack prompts (review item 10)."""
        all_keywords = {kw for kws in gen.KEYWORDS.values() for kw in kws}
        for broad in ("go", "get", "new", "more", "right", "main", "start"):
            self.assertNotIn(broad, all_keywords)
        for glyph in gen.GLYPHS:  # every glyph name still resolves to itself
            self.assertEqual(gen.pick_glyph(glyph), glyph)
        self.assertEqual(gen.pick_glyph("shopping cart"), "cart")

    def test_missing_title_defaults_to_capitalized_glyph_name(self):
        """Without --title the accessible name is the capitalized glyph name,
        and meaningful/interactive roles warn on stderr (review item 11)."""
        out = self.dir / "icon.svg"
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = gen.main(["--name", "gear", "--style", "outlined",
                             "--output", str(out)])
        self.assertEqual(code, 0)
        root = ET.parse(out).getroot()
        self.assertEqual(root.find(f"{SVG_NS}title").text, "Gear")
        self.assertIn("warning", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
