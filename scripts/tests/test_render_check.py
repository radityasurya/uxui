"""Tests for scripts/render-check.py.

Run with `python3 -m unittest discover -s scripts/tests` or pytest. The
end-to-end cases need a Chrome/Chromium binary and skip without one.
"""

import importlib.util
import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

# The script name is hyphenated, so it needs an explicit file-location load.
SCRIPT = Path(__file__).resolve().parents[1] / "render-check.py"
_spec = importlib.util.spec_from_file_location("render_check", SCRIPT)
rc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rc)

VALID_HTML = """<!DOCTYPE html>
<html><head><title>Deck</title></head>
<body><main><h1>Q3 report</h1><img src="dot.png" alt="dot"></main></body></html>
"""
VALID_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20">'
    '<use href="icons.svg#arrow"/></svg>'
)


class RenderCheckTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def write(self, text: str, suffix: str = ".html") -> Path:
        path = self.dir / f"input{suffix}"
        path.write_text(text, encoding="utf-8")
        return path

    def run_main(self, *argv: str) -> tuple[int, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = rc.main(list(argv))
        return code, stdout.getvalue() + stderr.getvalue()

    # Markup validity

    def test_valid_html_passes(self):
        (self.dir / "dot.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        self.assertEqual(rc.validate_markup(self.write(VALID_HTML)), [])

    def test_unclosed_tag_fails(self):
        errors = rc.validate_markup(self.write("<main><p>hi\n"))
        self.assertTrue(any("never closed" in e for e in errors), errors)

    def test_stray_end_tag_fails(self):
        errors = rc.validate_markup(self.write("<p>hi</span></p>\n"))
        self.assertTrue(any("matches no open" in e for e in errors), errors)

    def test_missing_local_ref_fails(self):
        errors = rc.validate_markup(self.write('<img src="nope.png" alt="x">\n'))
        self.assertTrue(any("nope.png" in e for e in errors), errors)

    def test_external_and_fragment_refs_ignored(self):
        html = (
            '<img src="https://cdn.example.com/dot.png" alt="x">'
            '<img src="dot.png" srcset="dot.png 1x, dot.png 2x" alt="y">'
            '<a href="#section">skip</a>\n'
        )
        (self.dir / "dot.png").write_bytes(b"")
        self.assertEqual(rc.validate_markup(self.write(html)), [])

    def test_valid_svg_passes(self):
        (self.dir / "icons.svg").write_text("<svg/>", encoding="utf-8")
        self.assertEqual(rc.validate_markup(self.write(VALID_SVG, ".svg")), [])

    def test_broken_svg_fails(self):
        errors = rc.validate_markup(self.write("<svg><rect></svg>", ".svg"))
        self.assertTrue(any("invalid XML" in e for e in errors), errors)

    def test_svg_unresolved_href_fails(self):
        errors = rc.validate_markup(self.write(VALID_SVG, ".svg"))
        self.assertTrue(any("icons.svg" in e for e in errors), errors)

    # Console classification and binary discovery

    def test_console_failures(self):
        messages = [
            '"Chart.js v4.4.1"',  # benign version banner
            '"Uncaught Error: boom", source: file:///x.html (3)',
            '"Failed to load resource: net::ERR_FILE_NOT_FOUND", source: ...',
        ]
        self.assertEqual(len(rc.console_failures(messages)), 2)

    def test_find_chrome_env_override(self):
        fake = self.dir / "fake-chrome"
        fake.write_bytes(b"")
        with mock.patch.dict(os.environ, {"RENDER_CHECK_CHROME": str(fake)}):
            self.assertEqual(rc.find_chrome(), str(fake))
        with mock.patch.dict(os.environ, {"RENDER_CHECK_CHROME": "/nonexistent"}):
            self.assertIsNone(rc.find_chrome())

    # Exit codes

    def test_missing_chrome_binary_exits_2(self):
        path = self.write("<!DOCTYPE html><html><body><p>hi</p></body></html>")
        with mock.patch.dict(os.environ, {"RENDER_CHECK_CHROME": "/nonexistent"}):
            code, output = self.run_main(str(path), "--out", str(self.dir / "s.png"))
        self.assertEqual(code, 2)
        self.assertIn("no Chrome/Chromium binary found", output)

    def test_broken_markup_exits_1(self):
        code, output = self.run_main(str(self.write("<div><h1>x</h2></div>")))
        self.assertEqual(code, 1)
        self.assertIn("markup error", output)

    def test_missing_file_exits_1(self):
        code, _ = self.run_main(str(self.dir / "absent.html"))
        self.assertEqual(code, 1)

    def test_unsupported_extension_exits_1(self):
        code, output = self.run_main(str(self.write("x", ".css")))
        self.assertEqual(code, 1)
        self.assertIn("unsupported extension", output)


@unittest.skipUnless(rc.find_chrome(), "no Chrome/Chromium binary found")
class RenderCheckEndToEndTest(unittest.TestCase):
    """Drive main() against real renders; needs a Chrome/Chromium binary."""

    setUp = RenderCheckTest.setUp
    write = RenderCheckTest.write
    run_main = RenderCheckTest.run_main

    def test_renders_and_screenshots(self):
        path = self.write(
            "<!DOCTYPE html><html><body><h1>ok</h1>"
            "<script>setTimeout(function(){}, 400)</script></body></html>"
        )
        shot = self.dir / "shot.png"
        code, output = self.run_main(str(path), "--out", str(shot))
        self.assertEqual(code, 0, output)
        self.assertTrue(shot.is_file() and shot.stat().st_size > 0)
        self.assertIn(str(shot), output)

    def test_console_error_fails(self):
        path = self.write(
            "<!DOCTYPE html><html><body><h1>bad</h1>"
            '<script>throw new Error("boom")</script></body></html>'
        )
        shot = self.dir / "shot.png"
        code, output = self.run_main(str(path), "--out", str(shot))
        self.assertEqual(code, 3, output)
        self.assertIn("Uncaught Error: boom", output)


if __name__ == "__main__":
    unittest.main()
