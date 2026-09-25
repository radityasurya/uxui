#!/usr/bin/env python3
"""The Image-job key gate fails fast, with an actionable message (uxui #10)."""

import contextlib
import importlib.util
import io
import os
import unittest
from pathlib import Path
from unittest import mock

HELPER = Path(__file__).resolve().parents[1] / "openrouter_key.py"


def load_helper():
    spec = importlib.util.spec_from_file_location("openrouter_key", HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RequireKeyTest(unittest.TestCase):
    def test_unset_key_exits_2_with_error(self):
        mod = load_helper()
        stderr = io.StringIO()
        with mock.patch.dict(os.environ, {}, clear=True):
            with contextlib.redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as ctx:
                    mod.require_key()
        self.assertEqual(ctx.exception.code, 2)
        message = stderr.getvalue()
        self.assertIn(mod.KEY_ENV, message)
        self.assertEqual(message.count("\n"), 1)  # one line plus the newline

    def test_blank_key_exits_2(self):
        mod = load_helper()
        with mock.patch.dict(os.environ, {mod.KEY_ENV: "   "}):
            with self.assertRaises(SystemExit) as ctx:
                mod.require_key()
        self.assertEqual(ctx.exception.code, 2)

    def test_set_key_is_returned(self):
        mod = load_helper()
        with mock.patch.dict(os.environ, {mod.KEY_ENV: "sk-test-123"}):
            self.assertEqual(mod.require_key(), "sk-test-123")

    def test_model_override(self):
        mod = load_helper()
        self.assertEqual(mod.image_model(), mod.DEFAULT_IMAGE_MODEL)
        with mock.patch.dict(os.environ, {mod.MODEL_ENV: "vendor/other"}):
            self.assertEqual(mod.image_model(), "vendor/other")


if __name__ == "__main__":
    unittest.main()
