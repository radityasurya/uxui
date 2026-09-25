"""Tests for the uxui:tokens Generator.

Follows the logo Generator test pattern: load generate.py by path with
importlib, drive it end to end, assert the three output files are
well-formed. The render-check test mirrors the shared checker's contract:
it skips when no Chrome/Chromium binary is available (exit code 2).
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
SPEC = importlib.util.spec_from_file_location("tokens_generate", MODULE_PATH)
tokens_generate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tokens_generate)

REPO_ROOT = next(
    parent for parent in MODULE_PATH.resolve().parents
    if (parent / "scripts" / "render-check.py").is_file()
)

# One full Design system, in the exact shape search.py --design-system --json
# emits (unwrapped). Captured from a real run, trimmed to the keys consumed.
DESIGN_SYSTEM = {
    "project_name": "Acme",
    "category": "SaaS (General)",
    "style": {"id": "glassmorphism", "name": "Glassmorphism"},
    "colors": {
        "primary": "#2563EB", "on_primary": "#FFFFFF",
        "secondary": "#3B82F6", "on_secondary": "#000000",
        "accent": "#EA580C", "on_accent": "#000000",
        "background": "#F8FAFC", "foreground": "#1E293B",
        "card": "#FFFFFF", "card_foreground": "#1E293B",
        "muted": "#E9EFF8", "muted_foreground": "#475569",
        "border": "#E2E8F0", "destructive": "#DC2626",
        "on_destructive": "#FFFFFF", "ring": "#2563EB",
    },
    "typography": {
        "heading": "Calistoga", "body": "Inter",
        "css_import": "@import url('https://fonts.googleapis.com/css2?family=Calistoga&family=Inter&display=swap');",
    },
    "spacing_scale": None,
}

# Palettes the contrast guarantees must hold across: the demo palette (an
# #EA580C accent), a Tailwind blue-500 #3B82F6 primary, a dark palette, and
# provided on-colors that fail 4.5:1 and must be replaced.
CONTRAST_PALETTES = [
    ("demo", DESIGN_SYSTEM["colors"]),
    ("blue-500-primary", {"primary": "#3B82F6", "accent": "#EA580C",
                          "background": "#FFFFFF", "foreground": "#0F172A"}),
    ("dark", {"background": "#0F172A", "foreground": "#F8FAFC",
              "primary": "#3B82F6", "accent": "#F97316"}),
    ("failing-on-colors", {"primary": "#EA580C", "on_primary": "#FFFFFF",
                           "accent": "#F97316", "on_accent": "#FFFFFF",
                           "background": "#FFFFFF", "foreground": "#0F172A"}),
]

# Every semantic fill / foreground pair; the hover rows pair a *-foreground
# with the hover fill it must also hold 4.5:1 against.
FILL_FOREGROUND_PAIRS = (
    ("primary", "primary-foreground"),
    ("primary-hover", "primary-hover-foreground"),
    ("secondary", "secondary-foreground"),
    ("accent", "accent-foreground"),
    ("accent-hover", "accent-hover-foreground"),
    ("card", "card-foreground"),
    ("muted", "muted-foreground"),
    ("destructive", "destructive-foreground"),
    ("success", "success-foreground"),
    ("warning", "warning-foreground"),
)

SAMPLE_PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Acme tokens sample</title>
  <link rel="stylesheet" href="tokens.css">
</head>
<body>
  <main class="wrap">
    <h1>Acme</h1>
    <p class="lead">Tokens applied from tokens.css.</p>
    <button>Get started</button>
    <div class="card">
      <h2>Card</h2>
      <p>Card body text.</p>
    </div>
  </main>
</body>
</html>
"""

SAMPLE_PAGE_CSS = """
  body { background: var(--color-background); color: var(--color-foreground);
         font-family: var(--font-body); margin: 0; }
  .wrap { max-width: 40rem; margin: var(--spacing-section) auto;
          padding: 0 var(--spacing-component); }
  h1 { font-family: var(--font-heading); font-size: var(--font-size-3xl); }
  .lead { color: var(--color-muted-foreground); font-size: var(--font-size-lg); }
  button { background: var(--button-background); color: var(--button-foreground);
           padding: var(--button-padding-y) var(--button-padding-x);
           border: 0; border-radius: var(--button-radius);
           font-size: var(--button-font-size); font-weight: var(--button-font-weight);
           cursor: pointer; }
  button:hover { background: var(--button-hover-background);
                 color: var(--button-hover-foreground); }
  .card { background: var(--card-background); color: var(--card-foreground);
          border: 1px solid var(--card-border); border-radius: var(--card-radius);
          box-shadow: var(--card-shadow); padding: var(--card-padding);
          margin-top: var(--spacing-component); }
"""


def generate_into(tmpdir, design_system=None):
    source = Path(tmpdir) / "design-system.json"
    source.write_text(json.dumps(design_system or DESIGN_SYSTEM), encoding="utf-8")
    out = Path(tmpdir) / "tokens"
    code = tokens_generate.main(["--design-system", str(source), "--out", str(out)])
    assert code == 0
    return out


def dtcg_leaves(group, path=()):
    """Yield (path, token-dict) for every $value leaf in a DTCG group."""
    for key, node in group.items():
        if isinstance(node, dict) and "$value" in node:
            yield path + (key,), node
        elif isinstance(node, dict):
            yield from dtcg_leaves(node, path + (key,))


def resolve_values(tokens):
    """{token path: resolved value} with every {...} alias followed."""
    values = {}

    def resolve(value):
        while isinstance(value, str) and value.startswith("{") and value.endswith("}"):
            value = values[tuple(value[1:-1].split("."))]
        return value

    for path, token in dtcg_leaves(tokens):
        values[path] = resolve(token["$value"])
    return values


class BuildTokensTests(unittest.TestCase):
    def test_three_layers_with_dtcg_nodes(self):
        tokens = tokens_generate.build_tokens(DESIGN_SYSTEM)
        for layer in ("primitive", "semantic", "component"):
            self.assertIn(layer, tokens, f"missing {layer} layer")
        leaves = list(dtcg_leaves({k: v for k, v in tokens.items()
                                   if k in ("primitive", "semantic", "component")}))
        self.assertGreater(len(leaves), 60)
        for path, token in leaves:
            self.assertIn("$value", token, f"{path} has no $value")
            self.assertIn("$type", token, f"{path} has no $type")

    def test_aliases_resolve_to_real_tokens(self):
        tokens = tokens_generate.build_tokens(DESIGN_SYSTEM)
        paths = {path for path, _ in dtcg_leaves(tokens)}
        for path, token in dtcg_leaves(tokens):
            value = token["$value"]
            if isinstance(value, str) and value.startswith("{"):
                self.assertTrue(
                    value.endswith("}"), f"{path}: malformed alias {value}"
                )
                target = tuple(value[1:-1].split("."))
                self.assertIn(target, paths, f"{path}: alias {value} dangles")

    def test_semantic_contract_names_exist(self):
        tokens = tokens_generate.build_tokens(DESIGN_SYSTEM)
        semantic_color = tokens["semantic"]["color"]
        for name in (
            "background", "foreground",
            "primary", "primary-hover", "primary-foreground", "primary-hover-foreground",
            "secondary", "secondary-foreground",
            "accent", "accent-hover", "accent-foreground", "accent-hover-foreground",
            "accent-text",
            "card", "card-foreground", "muted", "muted-foreground",
            "border", "input", "ring",
            "destructive", "destructive-foreground",
            "success", "success-foreground", "warning", "warning-foreground",
        ):
            self.assertIn(name, semantic_color, f"missing semantic color.{name}")
        for name in ("heading", "body"):
            self.assertIn(name, tokens["semantic"]["font"])
        self.assertIn("0", tokens["primitive"]["spacing"])
        self.assertIn("3xl", tokens["primitive"]["spacing"])
        self.assertIn("md", tokens["primitive"]["radius"])

    def test_missing_palette_roles_are_derived(self):
        sparse = {
            "project_name": "Sparse",
            "colors": {"primary": "#7C3AED", "background": "#FFFFFF",
                       "foreground": "#111827"},
            "typography": {},
        }
        tokens = tokens_generate.build_tokens(sparse)
        palette = tokens["primitive"]["color"]["palette"]
        self.assertEqual(palette["card"]["$value"], "#FFFFFF")
        self.assertEqual(palette["ring"]["$value"], "#7C3AED")
        self.assertEqual(palette["primary-foreground"]["$value"], "#FFFFFF")
        self.assertEqual(palette["muted-foreground"]["$type"], "color")
        for role in ("success", "success-foreground", "warning", "warning-foreground",
                     "input", "accent-text"):
            self.assertIn(role, palette)

    def test_spacing_scale_from_density_dial(self):
        dense = dict(DESIGN_SYSTEM, spacing_scale={
            "xs": "2px", "sm": "4px", "md": "8px", "lg": "12px",
            "xl": "16px", "2xl": "24px", "3xl": "32px"})
        tokens = tokens_generate.build_tokens(dense)
        self.assertEqual(tokens["primitive"]["spacing"]["xs"]["$value"], "0.125rem")
        self.assertEqual(tokens["primitive"]["spacing"]["md"]["$value"], "0.5rem")

    def test_dtcg_value_shapes_are_valid(self):
        tokens = tokens_generate.build_tokens(DESIGN_SYSTEM)
        primitive = tokens["primitive"]
        # Shadows: composite objects (or lists of them); "none" is an empty list.
        for layer in (primitive["shadow"]["sm"]["$value"]
                      + primitive["shadow"]["default"]["$value"]):
            self.assertEqual(set(layer), {"color", "offsetX", "offsetY", "blur", "spread"},
                             f"shadow layer {layer} is not a DTCG composite")
        self.assertEqual(primitive["shadow"]["none"]["$value"], [])
        # fontWeight is a number, fontFamily is an array.
        self.assertEqual(primitive["font"]["weight"]["semibold"]["$value"], 600)
        self.assertIsInstance(primitive["font"]["weight"]["semibold"]["$value"], int)
        heading = primitive["font"]["family"]["heading"]["$value"]
        self.assertIsInstance(heading, list)
        self.assertTrue(heading and all(isinstance(f, str) for f in heading))
        # Slide coverage: 5xl/6xl sizes, line-height primitives.
        self.assertEqual(primitive["font"]["size"]["5xl"]["$value"], "3rem")
        self.assertEqual(primitive["font"]["size"]["6xl"]["$value"], "3.75rem")
        for step in ("tight", "normal", "relaxed"):
            self.assertIn(step, primitive["line-height"])
        self.assertEqual(primitive["line-height"]["normal"]["$value"], 1.5)

    def test_font_stack_falls_back_by_category(self):
        tokens = tokens_generate.build_tokens({
            "colors": DESIGN_SYSTEM["colors"],
            "typography": {"heading": "Playfair Display", "body": "Inter"},
        })
        families = tokens["primitive"]["font"]["family"]
        self.assertEqual(families["heading"]["$value"][-1], "serif")
        self.assertEqual(families["body"]["$value"][-1], "sans-serif")

        mono = tokens_generate.build_tokens({
            "colors": DESIGN_SYSTEM["colors"],
            "typography": {"heading": "Space Grotesk", "body": "JetBrains Mono"},
        })["primitive"]["font"]["family"]
        self.assertEqual(mono["body"]["$value"][-1], "monospace")

        # A Design system that carries the pairing category wins over the name.
        categorized = tokens_generate.build_tokens({
            "colors": DESIGN_SYSTEM["colors"],
            "typography": {"heading": "Inter", "body": "Inter",
                           "category": "Serif + Sans"},
        })["primitive"]["font"]["family"]
        self.assertEqual(categorized["heading"]["$value"][-1], "serif")
        self.assertEqual(categorized["body"]["$value"][-1], "sans-serif")


class ContrastTests(unittest.TestCase):
    def test_readable_on_returns_the_stronger_side(self):
        self.assertEqual(tokens_generate.readable_on("#2563EB"), "#FFFFFF")
        self.assertEqual(tokens_generate.readable_on("#EA580C"), "#000000")
        self.assertEqual(tokens_generate.readable_on("#3B82F6"), "#000000")

    def test_every_foreground_holds_45_on_fill_and_hover(self):
        for label, colors in CONTRAST_PALETTES:
            with self.subTest(palette=label):
                tokens = tokens_generate.build_tokens(
                    {"project_name": label, "colors": dict(colors), "typography": {}})
                values = resolve_values(tokens)
                for fill, foreground in FILL_FOREGROUND_PAIRS:
                    ratio = tokens_generate.contrast_ratio(
                        values[("semantic", "color", foreground)],
                        values[("semantic", "color", fill)])
                    self.assertIsNotNone(ratio, f"{foreground}: unparseable value")
                    self.assertGreaterEqual(
                        ratio, 4.5, f"{label}: {foreground} on {fill} is {ratio:.2f}:1")

    def test_failing_provided_on_colors_are_replaced(self):
        tokens = tokens_generate.build_tokens({
            "project_name": "failing",
            "colors": dict(CONTRAST_PALETTES[3][1]),
            "typography": {},
        })
        palette = tokens["primitive"]["color"]["palette"]
        # #FFFFFF on #EA580C is 3.55:1, so the generator must not keep it.
        self.assertNotEqual(palette["primary-foreground"]["$value"], "#FFFFFF")

    def test_accent_text_holds_45_on_background(self):
        for label, colors in CONTRAST_PALETTES:
            with self.subTest(palette=label):
                tokens = tokens_generate.build_tokens(
                    {"project_name": label, "colors": dict(colors), "typography": {}})
                values = resolve_values(tokens)
                ratio = tokens_generate.contrast_ratio(
                    values[("semantic", "color", "accent-text")],
                    values[("semantic", "color", "background")])
                self.assertGreaterEqual(ratio, 4.5, f"{label}: accent-text is {ratio:.2f}:1")

    def test_input_holds_3_on_background_and_feeds_component_border(self):
        tokens = tokens_generate.build_tokens(DESIGN_SYSTEM)
        values = resolve_values(tokens)
        for label, colors in CONTRAST_PALETTES:
            with self.subTest(palette=label):
                palette = tokens_generate._palette(
                    {"colors": dict(colors), "typography": {}})
                ratio = tokens_generate.contrast_ratio(
                    palette["input"], palette["background"])
                self.assertGreaterEqual(ratio, 3.0, f"{label}: input border {ratio:.2f}:1")
        self.assertEqual(values[("component", "input", "border")],
                         values[("semantic", "color", "input")])
        # Decorative border stays a separate, lighter token.
        self.assertNotEqual(values[("semantic", "color", "input")],
                            values[("semantic", "color", "border")])


class OutputFileTests(unittest.TestCase):
    def test_full_design_system_writes_three_well_formed_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = generate_into(tmp)

            dtcg = json.loads((out / "tokens.json").read_text(encoding="utf-8"))
            for layer in ("primitive", "semantic", "component"):
                self.assertIn(layer, dtcg)

            css = (out / "tokens.css").read_text(encoding="utf-8")
            self.assertEqual(css.count("/* === PRIMITIVE TOKENS"),
                             1, "primitive layer section missing")
            self.assertEqual(css.count("/* === SEMANTIC TOKENS"), 1)
            self.assertEqual(css.count("/* === COMPONENT TOKENS"), 1)
            self.assertEqual(css.count("{"), css.count("}"), "unbalanced braces")
            self.assertIn("--color-background: var(--color-palette-background);", css)
            self.assertIn("--button-background: var(--color-primary);", css)
            self.assertIn("--button-hover-foreground: var(--color-primary-hover-foreground);", css)
            # DTCG composites still render as CSS shadows and font stacks.
            self.assertIn("--shadow-default: 0px 1px 3px 0px rgb(0 0 0 / 0.1),", css)
            # Calistoga sits under a "Display Serif + …" pairing, so the
            # fallback stack is serif.
            self.assertIn("--font-family-heading: Calistoga, Georgia, 'Times New Roman', serif;", css)
            self.assertIn("--font-weight-semibold: 600;", css)
            self.assertIn("--line-height-normal: 1.5;", css)

            theme = json.loads((out / "tailwind.theme.json").read_text(encoding="utf-8"))
            self.assertEqual(theme["colors"]["primary"]["DEFAULT"],
                             "var(--color-primary)")
            self.assertEqual(theme["colors"]["primary"]["foreground"],
                             "var(--color-primary-foreground)")
            self.assertEqual(theme["colors"]["primary"]["hover"]["foreground"],
                             "var(--color-primary-hover-foreground)")
            self.assertEqual(theme["fontFamily"]["heading"], "var(--font-heading)")

    def test_tailwind_theme_uses_config_conventions(self):
        with tempfile.TemporaryDirectory() as tmp:
            theme = json.loads(
                (generate_into(tmp) / "tailwind.theme.json").read_text(encoding="utf-8"))
            self.assertIn("DEFAULT", theme["borderRadius"])
            self.assertNotIn("default", theme["borderRadius"])
            self.assertIn("DEFAULT", theme["boxShadow"])
            comment = theme["$comment"]
            self.assertIn("theme.extend", comment)
            self.assertNotIn("@theme", comment)

    def test_every_css_var_reference_is_defined(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = generate_into(tmp)
            css = (out / "tokens.css").read_text(encoding="utf-8")
            defined = set(re.findall(r"^\s*(--[\w-]+)\s*:", css, re.M))
            referenced = set(re.findall(r"var\((--[\w-]+)\)", css))
            self.assertTrue(defined, "no custom properties emitted")
            self.assertEqual(referenced - defined, set(),
                             "tokens.css references undefined properties")

            theme = json.loads((out / "tailwind.theme.json").read_text(encoding="utf-8"))
            referenced = set(re.findall(r"var\((--[\w-]+)\)", json.dumps(theme)))
            self.assertEqual(referenced - defined, set(),
                             "tailwind theme references undefined properties")

    def test_stdin_input_unwraps_design_system_key(self):
        payload = {"design_system": DESIGN_SYSTEM, "text": "box drawing"}
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "wrapped.json"
            source.write_text(json.dumps(payload), encoding="utf-8")
            unwrapped = tokens_generate.load_design_system(str(source))
            self.assertEqual(unwrapped["project_name"], "Acme")

    def test_rejects_non_design_system_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "not-a-ds.json"
            source.write_text('{"results": []}', encoding="utf-8")
            with self.assertRaises(ValueError):
                tokens_generate.load_design_system(str(source))


class RenderCheckTests(unittest.TestCase):
    def test_sample_page_linking_tokens_css_renders(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = generate_into(tmp)
            page = out / "sample.html"
            page.write_text(
                SAMPLE_PAGE.replace("</head>",
                                    f"<style>{SAMPLE_PAGE_CSS}</style></head>"),
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(REPO_ROOT / "scripts" / "render-check.py"),
                 str(page)],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 2:
                self.skipTest("no Chrome/Chromium binary available")
            self.assertEqual(result.returncode, 0,
                             f"render-check failed:\n{result.stdout}\n{result.stderr}")


if __name__ == "__main__":
    unittest.main()
