"""The CIP generator bundle cost gate: one confirmation for N Image jobs (uxui #12).

All HTTP is mocked through the uxui:image ``http=`` seam; no test touches
the network. The OpenRouter key is faked via the environment.
"""

import base64
import contextlib
import importlib.util
import io
import os
import re
import tempfile
from pathlib import Path
from unittest import mock

import pytest

HELPER = Path(__file__).resolve().parents[1] / "cip_bundle.py"
# 1x1 transparent PNG — same fixture as the uxui:image tests
TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)

_spec = importlib.util.spec_from_file_location("cip_bundle", HELPER)
bundle = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bundle)

DELIVERABLES = "business card,letterhead,reception signage"
NAMES = ["Business Card", "Letterhead", "Reception Signage"]


def make_prompt(deliverable, industry, brand="Northbeam"):
    """build_prompt on real catalog rows, with the default (no-logo) line."""
    d = bundle.find_row(bundle.load_catalog(bundle.DATA_DIR / "deliverables.csv"), "Deliverable", deliverable)
    i = bundle.find_row(bundle.load_catalog(bundle.DATA_DIR / "industries.csv"), "Industry", industry)
    c = bundle.find_row(bundle.load_catalog(bundle.DATA_DIR / "mockup-contexts.csv"),
                        "Context Name", d["Mockup Context"])
    logo_line = (f"Logo: a simple mark plus the wordmark '{brand}', spelled exactly, "
                 "set in the heading font.")
    return bundle.build_prompt(brand, i, d, c, logo_line, None, None)


class FakeHTTP:
    """Records calls and returns a canned one-image response."""

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


def run_main(tmp_path, *extra, input=lambda _: "n", http=forbidden_http):
    """main() under a fake key, with stdout captured; returns (code, printed)."""
    argv = ["--brand", "Northbeam", "--industry", "Consulting",
            "--deliverables", DELIVERABLES,
            "--out-dir", str(tmp_path / "cip"), *extra]
    stdout = io.StringIO()
    with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-test-123"}, clear=True):
        with contextlib.redirect_stdout(stdout):
            code = bundle.main(argv, input=input, http=http)
    return code, stdout.getvalue()


def test_declined_combined_confirmation_names_all_and_sends_nothing(tmp_path):
    code, printed = run_main(tmp_path, input=lambda _: "n")
    assert code == 1
    for name in NAMES:  # the one confirmation names all N deliverables
        assert name in printed
    assert "openai/gpt-image-2" in printed
    assert "Estimated cost: ~$0.03-$0.14 per image (estimate) x 3" in printed
    assert "Total estimated cost: ~$0.09-$0.42 for 3 images (estimate)" in printed
    assert "Declined; no request was sent." in printed
    out = tmp_path / "cip"
    assert not out.exists() or not list(out.glob("*.png"))


def test_accept_sends_exactly_n_requests_and_saves_each(tmp_path):
    http = FakeHTTP()
    code, printed = run_main(tmp_path, input=lambda _: "y", http=http)
    assert code == 0
    assert len(http.calls) == 3  # exactly N — one Image job per deliverable
    url, first, key = http.calls[0]
    assert url == bundle.image_job.API_URL
    assert key == "sk-test-123"
    assert first["model"] == "openai/gpt-image-2"
    assert "Northbeam" in first["prompt"]
    assert first["size"] == "1536x1024"  # Business Card row's Size column
    saved = sorted((tmp_path / "cip").glob("*.png"))
    assert len(saved) == 3
    assert all(p.read_bytes() == TINY_PNG for p in saved)
    assert "3 of 3 deliverables generated" in printed


def test_missing_key_exits_before_any_prompt(tmp_path):
    argv = ["--brand", "Northbeam", "--industry", "Consulting",
            "--deliverables", DELIVERABLES, "--out-dir", str(tmp_path / "cip")]
    stdout, stderr = io.StringIO(), io.StringIO()
    with mock.patch.dict(os.environ, {}, clear=True):
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with pytest.raises(SystemExit) as ctx:
                bundle.main(argv, input=lambda _: "y", http=forbidden_http)
    assert ctx.value.code == 2
    assert "OPENROUTER_API_KEY" in stderr.getvalue()
    assert "Prompt:" not in stdout.getvalue()  # nothing paid, nothing printed


def test_dry_run_prints_all_prompts_and_total_without_key_or_network(tmp_path):
    argv = ["--brand", "Northbeam", "--industry", "Consulting",
            "--deliverables", DELIVERABLES,
            "--out-dir", str(tmp_path / "cip"), "--dry-run"]
    stdout = io.StringIO()
    with mock.patch.dict(os.environ, {}, clear=True):  # no key needed
        with contextlib.redirect_stdout(stdout):
            code = bundle.main(argv, http=forbidden_http)
    assert code == 0
    printed = stdout.getvalue()
    assert printed.count("Prompt:") == 3
    for name in NAMES:
        assert name in printed
    assert "Total estimated cost: ~$0.09-$0.42 for 3 images (estimate)" in printed
    assert "no request was sent" in printed
    assert not (tmp_path / "cip").exists()


def test_logo_svg_is_described_in_every_prompt(tmp_path):
    logo = tmp_path / "northbeam-logo.svg"
    logo.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><title>Northbeam — Minimalist logo'
        "</title></svg>", encoding="utf-8")
    http = FakeHTTP()
    run_main(tmp_path, "--logo", str(logo), input=lambda _: "y", http=http)
    assert len(http.calls) == 3
    for _, payload, _ in http.calls:
        assert "Northbeam — Minimalist logo" in payload["prompt"]


def test_total_cost_line_scales_per_image_estimate():
    line = bundle.total_cost_line("openai/gpt-image-2", 3)
    assert line == "~$0.09-$0.42 for 3 images (estimate)"
    assert "unknown" in bundle.total_cost_line("vendor/other", 3)


def test_paper_stock_reaches_only_stationery_and_print():
    for deliverable in ("business card", "invoice"):  # Stationery, Print
        assert "navy cotton paper" in make_prompt(deliverable, "Finance")
    mug = make_prompt("coffee mug", "Finance")  # Merch: paper must not leak
    van = make_prompt("van branding", "Food & Beverage")  # Vehicle
    assert "navy cotton paper" not in mug
    assert "kraft paper" not in mug
    assert "kraft paper" not in van
    assert "gold foil accents" in mug  # neutral art direction still applies
    assert "Paper stock" not in mug


def test_no_logo_line_is_a_fixed_description_not_a_style_interpolation():
    # Food & Beverage would have produced "a Honest Craft logomark" before
    prompt = make_prompt("business card", "Food & Beverage")
    assert ("a simple mark plus the wordmark 'Northbeam', spelled exactly, "
            "set in the heading font") in prompt
    assert "fits the deliverable" not in prompt
    assert "a Honest" not in prompt


def test_negative_guidance_and_exact_brand_in_every_prompt():
    for deliverable in ("business card", "van branding"):
        prompt = make_prompt(deliverable, "Finance")
        assert "No other brand names" in prompt
        assert "no placeholder or garbled text" in prompt
        assert "no watermark" in prompt
        assert "no extra logos" in prompt
        assert "render 'Northbeam' exactly" in prompt


def test_palette_pairs_each_hex_with_a_name_and_a_role():
    prompt = make_prompt("business card", "Finance")
    assert re.search(r"[a-z][a-z ]* #123B5A as the dominant color", prompt)
    assert re.search(r"[a-z][a-z ]* #C9A227 as the accent only", prompt)
    assert re.search(r"[a-z][a-z ]* #F5F1E8 and [a-z][a-z ]* #26323F "
                     r"as supporting colors", prompt)
    assert bundle.color_name("#123B5A") == "deep navy"
    assert bundle.color_name("#C9A227") == "gold"


def test_photography_phrasing_comes_from_the_context_row():
    prompt = make_prompt("coffee mug", "Finance")  # Cafe Table context
    assert "professional product photography" not in prompt
    assert "lifestyle photography" in prompt


class FailSecondHTTP:
    """Returns a good payload once, then a payload run_image_job rejects."""

    def __init__(self):
        self.calls = 0

    def __call__(self, url, payload, key):
        self.calls += 1
        if self.calls > 1:
            return {"data": []}  # missing b64_json -> SystemExit mid-bundle
        return {"data": [{"b64_json": base64.b64encode(TINY_PNG).decode()}],
                "usage": {"cost": 0.04}}


def test_mid_bundle_failure_lists_saved_and_paid_before_exiting(tmp_path):
    argv = ["--brand", "Northbeam", "--industry", "Consulting",
            "--deliverables", DELIVERABLES, "--out-dir", str(tmp_path / "cip")]
    stdout, stderr = io.StringIO(), io.StringIO()
    with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-test-123"}, clear=True):
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with pytest.raises(SystemExit):
                bundle.main(argv, input=lambda _: "y", http=FailSecondHTTP())
    printed = stdout.getvalue()
    assert "Bundle stopped after 1 of 3 deliverables." in printed
    assert "Saved and paid for: Business Card (" in printed
    assert "Business Card, Letterhead" not in printed.split("Saved and paid for:")[1]
    out = tmp_path / "cip"
    assert (out / "northbeam-business-card.png").exists()
    assert not (out / "northbeam-letterhead.png").exists()
