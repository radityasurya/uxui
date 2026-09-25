"""Tests for the uxui:slides Generator.

Follows the tokens Generator test pattern: load generate.py by path with
importlib, drive it end to end against tokens produced by the real uxui:tokens
Generator, and assert the deck contract. The render-check test mirrors the
shared checker's contract: it skips when no Chrome/Chromium binary is available
(exit code 2) or when the sandbox blocks the Chart.js CDN.
"""
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "generate.py"
SPEC = importlib.util.spec_from_file_location("slides_generate", MODULE_PATH)
slides_generate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(slides_generate)

TOKENS_MODULE_PATH = (
    MODULE_PATH.resolve().parents[2] / "tokens" / "scripts" / "generate.py"
)
TOKENS_SPEC = importlib.util.spec_from_file_location("tokens_generate", TOKENS_MODULE_PATH)
tokens_generate = importlib.util.module_from_spec(TOKENS_SPEC)
TOKENS_SPEC.loader.exec_module(tokens_generate)

REPO_ROOT = next(
    parent for parent in MODULE_PATH.resolve().parents
    if (parent / "scripts" / "render-check.py").is_file()
)
RENDER_CHECK = REPO_ROOT / "scripts" / "render-check.py"

# One full Design system, in the shape search.py --design-system --json emits
# (trimmed to the keys the tokens Generator consumes).
DESIGN_SYSTEM = {
    "project_name": "Acme",
    "category": "SaaS (General)",
    "style": {"id": "glassmorphism", "name": "Glassmorphism"},
    "colors": {
        "primary": "#2563EB", "on_primary": "#FFFFFF",
        "secondary": "#3B82F6", "on_secondary": "#000000",
        "accent": "#EA580C", "on_accent": "#000000",
        "background": "#F8FAFC", "foreground": "#1E293B",
    },
    "typography": {"heading": "Space Grotesk", "body": "Inter"},
    "spacing_scale": None,
}

SLIDES = {
    "title": "Acme — Series A",
    "company": "Acme",
    "slides": [
        {"type": "title", "badge": "Seed deck", "title": "Acme",
         "subtitle": "Product analytics that answers itself.", "date": "September 2026"},
        {"type": "chart", "badge": "Traction", "headline": "Revenue compounds",
         "chart": {"type": "bar", "title": "MRR ($K)", "labels": ["Mar", "Jun", "Sep"],
                   "series": [{"label": "MRR", "data": [12, 28, 76]}]}},
        {"type": "content", "badge": "Detail", "headline": "What the numbers say",
         "bullets": [{"title": "Activation", "text": "Up 3x year over year."}]},
        {"type": "chart", "badge": "Mix", "headline": "Balanced plan mix",
         "chart": {"type": "Donut Chart", "title": "Revenue by plan",
                   "labels": ["Starter", "Growth", "Scale"],
                   "series": [{"label": "Share", "data": [18, 42, 26]}]}},
        {"type": "closing", "headline": "Own the question loop",
         "subheadline": "Acme analytics for every team.", "cta": "Book a call",
         "contact": "team@acme.dev", "website": "acme.dev"},
    ],
}


def write_tokens(tmpdir):
    """Run the real tokens Generator over DESIGN_SYSTEM inside tmpdir."""
    source = Path(tmpdir) / "design-system.json"
    source.write_text(json.dumps(DESIGN_SYSTEM), encoding="utf-8")
    out = Path(tmpdir) / "tokens"
    assert tokens_generate.main(["--design-system", str(source), "--out", str(out)]) == 0
    return out


def build_deck(tmpdir, slides=None, chartjs=None):
    """Deck HTML string from the real tokens output of DESIGN_SYSTEM."""
    tokens_dir = write_tokens(tmpdir)
    slides_path = Path(tmpdir) / "deck.json"
    slides_path.write_text(json.dumps(slides or SLIDES), encoding="utf-8")
    argv = ["--slides", str(slides_path), "--tokens", str(tokens_dir / "tokens.css"),
            "--out", str(Path(tmpdir) / "deck.html")]
    if chartjs:
        argv += ["--chartjs", chartjs]
    assert slides_generate.main(argv) == 0
    return (Path(tmpdir) / "deck.html").read_text(encoding="utf-8")


class ChartKindTests(unittest.TestCase):
    def test_alias_id_name_and_keyword_all_resolve(self):
        self.assertEqual(slides_generate.resolve_chart("bar"), 1)
        self.assertEqual(slides_generate.resolve_chart("Bar Chart Vertical"), 1)
        self.assertEqual(slides_generate.resolve_chart("1"), 1)
        self.assertEqual(slides_generate.resolve_chart("comparison"), 1)  # CSV keyword
        self.assertEqual(slides_generate.resolve_chart("donut"), 6)
        self.assertEqual(slides_generate.resolve_chart("Donut Chart"), 6)
        self.assertEqual(slides_generate.resolve_chart("hbar"), 2)
        self.assertEqual(slides_generate.resolve_chart("area"), 4)
        self.assertEqual(slides_generate.resolve_chart("7"), 7)

    def test_supported_kinds_map_to_chartjs_types(self):
        self.assertEqual(slides_generate.CHART_KINDS[6][0], "doughnut")
        self.assertEqual(slides_generate.CHART_KINDS[4], ("line", {"fill": True}, ("area",)))
        self.assertEqual(slides_generate.CHART_KINDS[2][1], {"indexAxis": "y"})
        self.assertEqual(slides_generate.CHART_KINDS[7][1], {"stacked": True})

    def test_hbar_payload_carries_index_axis_y(self):
        with tempfile.TemporaryDirectory() as tmp:
            slides = dict(SLIDES, slides=[
                {"type": "chart", "headline": "Latency by region",
                 "chart": {"type": "hbar", "labels": ["eu", "us"],
                           "series": [{"label": "p95", "data": [120, 98]}]}}])
            html = build_deck(tmp, slides=slides)
        charts = json.loads(re.search(
            r'<script id="deck-charts" type="application/json">(.*?)</script>',
            html, re.S).group(1).replace("<\\/", "</"))
        self.assertEqual(charts[0]["type"], "bar")
        self.assertEqual(charts[0]["indexAxis"], "y")

    def test_cataloged_but_unsupported_chart_names_the_alternatives(self):
        with self.assertRaises(ValueError) as ctx:
            slides_generate.resolve_chart("Sankey Diagram")
        self.assertIn("cannot draw", str(ctx.exception))
        self.assertIn("donut", str(ctx.exception))

    def test_unknown_chart_type_is_rejected(self):
        with self.assertRaises(ValueError):
            slides_generate.resolve_chart("hologram")


class DeckContractTests(unittest.TestCase):
    def test_deck_has_real_chartjs_canvases_and_pinned_cdn(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = build_deck(tmp)
        self.assertIn('src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"', html)
        self.assertEqual(html.count("<canvas"), 2)
        self.assertIn('role="img"', html)
        charts = json.loads(re.search(
            r'<script id="deck-charts" type="application/json">(.*?)</script>',
            html, re.S).group(1).replace("<\\/", "</"))
        self.assertEqual([c["type"] for c in charts], ["bar", "doughnut"])
        self.assertEqual(charts[0]["canvas"], "chart-2")
        self.assertEqual(charts[1]["series"][0]["data"], [18, 42, 26])

    def test_colors_and_type_come_from_tokens_not_literals(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = build_deck(tmp)
        # Slice off the deck CSS (before the inlined tokens block) and the chart
        # script: those must carry no hex color literals, only token reads.
        deck_css = html.split("/* uxui:tokens output")[0]
        chart_js = html.split("<script>\n        (function ()")[1].split("</script>")[0]
        for label, chunk in (("deck CSS", deck_css), ("chart script", chart_js)):
            self.assertEqual(re.findall(r"#[0-9a-fA-F]{3}\b|#[0-9a-fA-F]{6}\b", chunk), [],
                             f"{label} hardcodes a color")
        for var in ("--color-primary", "--color-accent", "--color-border",
                    "--color-card", "--color-muted-foreground", "--font-body"):
            # Deck CSS reads var(--…); the chart script reads tok('--…') at runtime.
            self.assertIn(var, deck_css + chart_js)
        self.assertIn("getComputedStyle", chart_js)
        self.assertIn("Chart.defaults.font.family = tok('--font-body');", chart_js)

    def test_tokens_css_is_inlined_and_fonts_link_from_tokens_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = build_deck(tmp)
        self.assertIn("/* uxui:tokens output, inlined from tokens.css", html)
        self.assertIn("--color-primary:", html)  # the inlined tokens themselves
        self.assertIn("https://fonts.googleapis.com/css2?family=Space+Grotesk&family=Inter",
                      html)

    def test_unknown_slide_type_and_missing_slides_are_errors(self):
        with self.assertRaises(ValueError):
            slides_generate.render_deck({"slides": [{"type": "hologram"}]}, ":root{}", "", "x")
        with self.assertRaises(ValueError):
            slides_generate.render_deck({"slides": []}, ":root{}", "", "x")

    def test_chart_series_without_data_is_rejected(self):
        with self.assertRaises(ValueError):
            slides_generate.render_deck(
                {"slides": [{"type": "chart",
                             "chart": {"type": "bar", "labels": ["a"],
                                       "series": [{"label": "x"}]}}]},
                ":root{}", "", "x")

    def test_offline_chartjs_override_is_used_verbatim(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = build_deck(tmp, chartjs="chart.umd.min.js")
        self.assertIn('src="chart.umd.min.js"', html)
        self.assertNotIn("cdn.jsdelivr.net", html)

    def test_over_five_bullets_split_into_continuation_slides(self):
        bullets = [{"title": f"Point {i}", "text": "text"} for i in range(1, 8)]
        with tempfile.TemporaryDirectory() as tmp:
            html = build_deck(tmp, slides=dict(SLIDES, slides=[
                {"type": "title", "title": "Deck"},
                {"type": "content", "headline": "Roadmap", "bullets": bullets},
            ]))
        self.assertEqual(html.count('<section class="slide'), 3)  # title + 5 + 2
        self.assertEqual(html.count('class="bullet"'), 7)
        self.assertIn("Roadmap (cont.)", html)
        self.assertIn("02 / 03", html)
        self.assertIn("03 / 03", html)
        # the "(cont.)" slide keeps the tail, not a copy of the head
        self.assertIn("Point 7", html)

    def test_five_or_fewer_bullets_are_not_split(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = build_deck(tmp, slides=dict(SLIDES, slides=[
                {"type": "content", "headline": "Roadmap",
                 "bullets": [{"title": f"P{i}", "text": ""} for i in range(5)]},
            ]))
        self.assertEqual(html.count('<section class="slide'), 1)
        self.assertNotIn("(cont.)", html)

    def test_deck_is_a_viewport_snapped_presentation_not_a_card_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = build_deck(tmp)
        for fragment in (
            "scroll-snap-type: y mandatory",
            "scroll-snap-align: center",
            "max-width: calc(100vh * 16 / 9)",
            "aspect-ratio: 16 / 9",
            "container-type: inline-size",
            "clamp(var(--font-size-3xl), 4.5cqw, var(--font-size-6xl))",
        ):
            self.assertIn(fragment, html)
        # keyboard navigation: arrows, paging, space, and jump-to-end keys
        chart_js = html.split("<script>\n        (function ()")[1].split("</script>")[0]
        for key in ("ArrowDown", "ArrowUp", "ArrowLeft", "ArrowRight",
                    "PageDown", "PageUp", "' '", "Home", "End"):
            self.assertIn(key, chart_js)

    def test_badge_bullet_and_centering_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = build_deck(tmp)
        self.assertIn(".badge {\n            align-self: flex-start;", html)
        self.assertIn(".slide--center .badge { align-self: center; }", html)
        self.assertIn("min-width: 2ch; font-variant-numeric: tabular-nums;", html)
        # title/closing content sits in a centered flex core, footer at the edge
        self.assertEqual(html.count('<div class="slide-core">'), 2)

    def test_chart_title_dropped_when_it_repeats_the_headline(self):
        slides = dict(SLIDES, slides=[
            {"type": "chart", "headline": "Revenue compounds",
             "chart": {"type": "bar", "title": "Revenue compounds",
                       "labels": ["a"], "series": [{"label": "s", "data": [1]}]}},
            {"type": "chart", "headline": "Mix",
             "chart": {"type": "bar", "title": "Revenue by plan",
                       "labels": ["a"], "series": [{"label": "s", "data": [1]}]}},
        ])
        with tempfile.TemporaryDirectory() as tmp:
            html = build_deck(tmp, slides=slides)
        self.assertEqual(html.count('class="chart-title"'), 1)
        self.assertIn("Revenue by plan", html)

    def test_series_colors_are_distinct_token_expressions(self):
        series = slides_generate.SERIES_COLORS
        self.assertEqual(len(set(series[:3])), 3)  # first three all different
        for a, b in zip(series, series[1:]):  # adjacent clearly distinct
            self.assertNotEqual(a, b)
        joined = " ".join(series)
        self.assertNotIn("secondary", joined)  # too close to primary on charts
        self.assertNotIn("hover", joined)
        self.assertTrue(all(expr.startswith(("var(", "color-mix(")) for expr in series))
        # the ramp mixes by large steps (>= 22%) so lightness gaps stay visible
        ramp = [e for e in series if e.startswith("color-mix")]
        self.assertGreaterEqual(len(ramp), 4)
        for expr in ramp:
            pct = int(re.search(r" (\d+)%", expr).group(1))
            self.assertGreaterEqual(pct, 22)

    def test_alpha_uses_color_mix_not_hex_parsing(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = build_deck(tmp)
        chart_js = html.split("<script>\n        (function ()")[1].split("</script>")[0]
        self.assertIn(
            "'color-mix(in srgb, ' + color + ' ' + Math.round(pct * 100) + '%, transparent)'",
            chart_js)
        # fractions passed at the call sites must become whole percentages, or
        # bars mix at 0.85% opacity instead of 85% and vanish
        self.assertNotIn("parseInt(h, 16)", chart_js)
        # series colors resolve through a probe element, not raw token text
        self.assertIn("getComputedStyle(probe).color", chart_js)

    def test_chart_font_size_scales_with_the_chart_area(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = build_deck(tmp)
        chart_js = html.split("<script>\n        (function ()")[1].split("</script>")[0]
        self.assertIn("Chart.defaults.font.size = Math.max(12, Math.min(40, Math.round(width / 75)))",
                      chart_js)
        self.assertIn("x: { stacked: !!c.stacked, grid: { display: false } }", chart_js)

    def test_headline_larger_than_chart_tick_font(self):
        """The slide headline must outsize the chart ticks and legend.

        Parse the ratios out of the generated CSS and chart script and compare
        them at a 1920px slide. The chart box is narrower than the slide, so
        the tick size is computed against the full slide width — an upper
        bound; if the headline wins that, it wins in the browser too.
        """
        with tempfile.TemporaryDirectory() as tmp:
            html = build_deck(tmp)
        heading = re.search(
            r"\.slide-heading \{\s*font-size: clamp\([^,]+, ([\d.]+)cqw, var\((--[\w-]+)\)\)",
            html)
        divisor = re.search(r"Chart\.defaults\.font\.size = [^)]*width / (\d+)\)", html)
        self.assertTrue(heading and divisor, "headline clamp or tick formula not found")
        # clamp max token, resolved against the inlined tokens (rem -> px at 16)
        cap = re.search(re.escape(heading.group(2)) + r": ([\d.]+)rem", html)
        self.assertTrue(cap, f"{heading.group(2)} not in inlined tokens")
        headline_px = min(float(heading.group(1)) / 100 * 1920, float(cap.group(1)) * 16)
        tick_px = min(40, 1920 / int(divisor.group(1)))  # JS clamps at 40
        self.assertGreater(
            headline_px, tick_px,
            f"headline {headline_px}px does not clearly outsize ticks {tick_px}px")

    def test_generated_markup_passes_the_shared_markup_checks(self):
        render_check = importlib.util.spec_from_file_location(
            "render_check", RENDER_CHECK)
        module = importlib.util.module_from_spec(render_check)
        render_check.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "deck.html"
            path.write_text(build_deck(tmp), encoding="utf-8")
            self.assertEqual(module.validate_markup(path), [])


class RenderCheckTests(unittest.TestCase):
    def test_generated_deck_renders_with_chartjs_without_console_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "deck.html"
            path.write_text(build_deck(tmp), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(RENDER_CHECK), str(path)],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 2:
                self.skipTest("no Chrome/Chromium binary available")
            if result.returncode != 0 and "net::ERR_" in result.stdout:
                self.skipTest("sandbox blocks the Chart.js CDN")
            self.assertEqual(result.returncode, 0,
                             f"render-check failed:\n{result.stdout}\n{result.stderr}")


if __name__ == "__main__":
    unittest.main()
