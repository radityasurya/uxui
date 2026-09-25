#!/usr/bin/env python3
"""The Image-job cost gate: no paid call without consent or a key (uxui #11)."""

import base64
import contextlib
import importlib.util
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HELPER = Path(__file__).resolve().parents[1] / "image_job.py"
# 1x1 transparent PNG
TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


def load_module():
    spec = importlib.util.spec_from_file_location("image_job", HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeHTTP:
    """Test seam for the http= parameter: records calls, returns a canned response."""

    def __init__(self):
        self.calls = []

    def __call__(self, url, payload, key):
        self.calls.append((url, payload, key))
        return {
            "data": [{"b64_json": base64.b64encode(TINY_PNG).decode()}],
            "usage": {"cost": 0.04},
        }


def forbidden_http(url, payload, key):
    raise AssertionError("an HTTP call was made without consent or a key")


class CostGateTest(unittest.TestCase):
    def test_declined_job_prints_cost_and_sends_nothing(self):
        mod = load_module()
        stdout = io.StringIO()
        with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-test-123"}, clear=True):
            with contextlib.redirect_stdout(stdout):
                saved = mod.run_image_job(
                    "a flat vector hero illustration",
                    "/tmp/never-written.png",
                    input=lambda _: "n",
                    http=forbidden_http,
                )
        self.assertIsNone(saved)
        self.assertFalse(Path("/tmp/never-written.png").exists())
        printed = stdout.getvalue()
        self.assertIn("openai/gpt-image-2", printed)  # model
        self.assertIn("flat vector hero illustration", printed)  # prompt
        self.assertIn("Estimated cost:", printed)
        self.assertIn("Declined; no request was sent.", printed)

    def test_yes_saves_the_image(self):
        mod = load_module()
        http = FakeHTTP()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "sub" / "hero.png"
            stdout = io.StringIO()
            with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-test-123"}, clear=True):
                with contextlib.redirect_stdout(stdout):
                    saved = mod.run_image_job("hero", out, yes=True, size="1024x1024",
                                              http=http)
            self.assertEqual(saved, out)
            self.assertEqual(out.read_bytes(), TINY_PNG)
        self.assertEqual(len(http.calls), 1)
        url, payload, key = http.calls[0]
        self.assertEqual(url, mod.API_URL)
        self.assertEqual(key, "sk-test-123")
        self.assertEqual(payload, {"model": "openai/gpt-image-2", "prompt": "hero",
                                   "size": "1024x1024"})
        printed = stdout.getvalue()
        self.assertIn("Estimated cost:", printed)
        self.assertIn("Actual cost: $0.04", printed)

    def test_missing_key_exits_before_any_call(self):
        mod = load_module()
        stderr = io.StringIO()
        with mock.patch.dict(os.environ, {}, clear=True):
            with contextlib.redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as ctx:
                    mod.run_image_job("hero", "/tmp/never.png", yes=True,
                                      http=forbidden_http)
        self.assertEqual(ctx.exception.code, 2)
        self.assertIn("OPENROUTER_API_KEY", stderr.getvalue())

    def test_model_override_reaches_request_and_cost_line(self):
        mod = load_module()
        http = FakeHTTP()
        stdout = io.StringIO()
        with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-test-123",
                                          "UXUI_IMAGE_MODEL": "vendor/other"}, clear=True):
            with contextlib.redirect_stdout(stdout):
                mod.run_image_job("hero", "/tmp/uxui-image-override.png", yes=True,
                                  http=http)
        self.assertEqual(http.calls[0][1]["model"], "vendor/other")
        self.assertIn(mod.UNKNOWN_COST, stdout.getvalue())  # unknown model: cost unknown
        Path("/tmp/uxui-image-override.png").unlink(missing_ok=True)


class MainTest(unittest.TestCase):
    def test_declined_cli_returns_1_without_a_call(self):
        mod = load_module()
        with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-test-123"}, clear=True):
            code = mod.main(["--prompt", "hero", "--out", "/tmp/never.png"],
                            input=lambda _: "", http=forbidden_http)
        self.assertEqual(code, 1)

    def test_dry_run_prints_request_without_key_or_network(self):
        mod = load_module()
        stdout = io.StringIO()
        fake_key = "sk-demo-0123456789abcdef"
        with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": fake_key}, clear=True):
            with contextlib.redirect_stdout(stdout):
                code = mod.main(["--prompt", "hero", "--out", "/tmp/hero.png",
                                 "--dry-run"])
        self.assertEqual(code, 0)
        printed = stdout.getvalue()
        self.assertIn(f"POST {mod.API_URL}", printed)
        self.assertIn('"model": "openai/gpt-image-2"', printed)
        self.assertIn("Authorization: Bearer sk-demo", printed)  # prefix only
        self.assertNotIn(fake_key, printed)  # the full key is redacted


if __name__ == "__main__":
    unittest.main()
