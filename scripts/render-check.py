#!/usr/bin/env python3
"""Render-check a Generator output file: prove it actually renders.

Shared by every Generator skill (tokens, slides, banner, icon, logo) to
check the file it just wrote. Two checks per file, standard library only:

1. Markup validity. ``xml.etree.ElementTree`` parses ``.svg`` files; a
   ``html.parser.HTMLParser`` subclass checks ``.html`` files for stray or
   unclosed tags. Relative ``src``/``href``/``poster``/``srcset`` references
   must resolve next to the input file: headless Chrome logs no error for a
   missing ``file://`` subresource, so the script checks them itself.
2. Headless render. ``subprocess`` runs a Chrome or Chromium binary with
   ``--screenshot`` and ``--enable-logging=stderr``, then fails on a
   non-zero Chrome exit status, on error-like console output, or on a
   missing screenshot.

Binary discovery, first match wins: ``$RENDER_CHECK_CHROME``, then
google-chrome / google-chrome-stable / chromium / chromium-browser on PATH,
then a Playwright-downloaded Chromium in the user's browser cache (it uses
the binary already on disk; it installs nothing).

Exit codes:
  0  rendered; screenshot path printed
  1  bad input or invalid markup
  2  no Chrome/Chromium binary found (a Generator test can skip on this)
  3  render failed: Chrome error, console error, or missing screenshot
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

# Console messages arrive as
# [pid:pid:date:INFO:CONSOLE:line] "message", source: url (line)
CONSOLE_LINE = re.compile(r":CONSOLE(?::\d+|\(\d+\))?\]\s*(.*)")
CONSOLE_ERROR_MARKERS = ("Uncaught", "net::ERR_", "Failed to load resource")

CHROME_PATH_CANDIDATES = (
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
)
PLAYWRIGHT_CACHE_GLOBS = (
    "chromium-*/chrome-linux*/chrome",
    "chromium_headless_shell-*/chrome-linux*/headless_shell",
)
CHROME_FLAGS = (
    # --no-sandbox: Ubuntu 23.10+ AppArmor blocks the user-namespace sandbox
    # and Chrome aborts at startup; CI containers need it as well.
    "--headless", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
    "--window-size=1280,800",
    # Deterministic settle time, so scripts that draw after load (Chart.js)
    # run before the screenshot is taken.
    "--virtual-time-budget=3000",
    "--enable-logging=stderr",
)

VOID_ELEMENTS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
})
REF_ATTRS = ("src", "href", "poster", "srcset")


class _HtmlTagChecker(HTMLParser):
    """Collect the tag errors html.parser itself never raises.

    An end tag that matches an outer open tag closes the elements above it
    implicitly, the way a browser repairs ``<li>1<li>2</ul>``. Only what a
    browser could not place — stray close tags and tags still open at EOF —
    counts as an error.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.open_tags: list[tuple[str, int]] = []
        self.errors: list[str] = []
        self.refs: list[tuple[str, str]] = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name in REF_ATTRS and value:
                self.refs.append((name, value))
        if tag not in VOID_ELEMENTS:
            self.open_tags.append((tag, self.getpos()[0]))

    def handle_endtag(self, tag):
        if tag in VOID_ELEMENTS:
            return
        if tag not in (open for open, _ in self.open_tags):
            line = self.getpos()[0]
            self.errors.append(f"line {line}: </{tag}> matches no open <{tag}>")
            return
        while self.open_tags:
            open_tag, _ = self.open_tags.pop()
            if open_tag == tag:
                break

    def close(self):
        super().close()
        for tag, line in self.open_tags:
            self.errors.append(f"line {line}: <{tag}> never closed")


def _local_target(value: str) -> str | None:
    """Return the file part of a reference that must exist on disk."""
    target = value.strip()
    if not target:
        return None
    parsed = urlparse(target)
    if parsed.scheme or target.startswith(("#", "/", "//")):
        return None
    return unquote(parsed.path)


def _srcset_targets(value: str):
    for candidate in value.split(","):
        parts = candidate.split()
        if parts:
            yield parts[0]


def _ref_errors(path: Path, refs: list[tuple[str, str]]) -> list[str]:
    errors = []
    for attr, value in refs:
        for raw in _srcset_targets(value) if attr == "srcset" else [value]:
            target = _local_target(raw)
            if target and not (path.parent / target).exists():
                errors.append(f'{attr}="{raw.strip()}": {path.parent / target} not found')
    return errors


def validate_markup(path: Path) -> list[str]:
    """Check well-formed markup and resolvable local references."""
    if path.suffix.lower() == ".svg":
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError as exc:
            return [f"invalid XML: {exc}"]
        refs = [
            (local, value)
            for element in root.iter()
            for attr, value in element.attrib.items()
            if (local := attr.rsplit("}", 1)[-1]) in REF_ATTRS
        ]
        return _ref_errors(path, refs)

    checker = _HtmlTagChecker()
    try:
        checker.feed(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        return [f"cannot decode as UTF-8: {exc}"]
    checker.close()
    return checker.errors + _ref_errors(path, checker.refs)


def find_chrome() -> str | None:
    """Locate a Chrome or Chromium binary (see module docstring)."""
    override = os.environ.get("RENDER_CHECK_CHROME")
    if override:
        return override if Path(override).is_file() else None
    for name in CHROME_PATH_CANDIDATES:
        found = shutil.which(name)
        if found:
            return found
    for base in (
        Path.home() / ".cache" / "ms-playwright",
        Path.home() / "Library" / "Caches" / "ms-playwright",
    ):
        found = sorted(
            (p for glob in PLAYWRIGHT_CACHE_GLOBS for p in base.glob(glob) if p.is_file()),
            key=lambda p: p.stat().st_mtime,
        )
        if found:
            return str(found[-1])
    return None


def console_failures(messages: list[str]) -> list[str]:
    """Return the console messages that count as render errors."""
    return [m for m in messages if any(marker in m for marker in CONSOLE_ERROR_MARKERS)]


def run_render(chrome: str, url: str, out: Path) -> tuple[int, list[str], list[str]]:
    """Render `url` headlessly. Return (exit status, console messages, log tail)."""
    try:
        proc = subprocess.run(
            [chrome, *CHROME_FLAGS, f"--screenshot={out}", url],
            capture_output=True, text=True, errors="replace", timeout=90,
        )
    except subprocess.TimeoutExpired:
        return 124, [], ["Chrome timed out after 90 s"]
    except OSError as exc:
        return 127, [], [f"could not run {chrome}: {exc}"]
    messages: list[str] = []
    noise: list[str] = []
    for line in proc.stderr.splitlines():
        match = CONSOLE_LINE.search(line)
        (messages if match else noise).append(match.group(1) if match else line)
    return proc.returncode, messages, noise[-8:]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="render-check.py",
        description="Validate and render-check a Generator's .svg or .html output.",
        epilog=(
            "checks:\n"
            "  1. markup validity, stdlib only: xml.etree.ElementTree parses\n"
            "     SVG, html.parser.HTMLParser checks HTML; stray or unclosed\n"
            "     tags, and relative src/href/poster/srcset references that do\n"
            "     not resolve next to the file, are errors\n"
            "  2. headless render: a Chrome or Chromium binary (google-chrome,\n"
            "     chromium, ... on PATH, $RENDER_CHECK_CHROME, or a\n"
            "     Playwright-cached Chromium) screenshots the page; a Chrome\n"
            "     crash, error-like console output, or a missing screenshot\n"
            "     fails\n"
            "\n"
            "exit codes: 0 rendered, 1 bad input or markup, 2 no Chrome binary\n"
            "(a Generator test can skip on this), 3 render failure"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("file", help=".svg or .html file to check")
    parser.add_argument(
        "--out", metavar="PATH",
        help="screenshot path (default: <input>.render-check.png)",
    )
    args = parser.parse_args(argv)

    path = Path(args.file)
    if not path.is_file():
        print(f"error: no such file: {path}", file=sys.stderr)
        return 1
    if path.suffix.lower() not in (".svg", ".html"):
        print(
            f"error: unsupported extension {path.suffix!r}: expected .svg or .html",
            file=sys.stderr,
        )
        return 1
    path = path.resolve()
    out = Path(args.out) if args.out else path.with_name(path.stem + ".render-check.png")

    errors = validate_markup(path)
    if errors:
        for error in errors:
            print(f"markup error: {error}", file=sys.stderr)
        return 1

    chrome = find_chrome()
    if chrome is None:
        print(
            "error: no Chrome/Chromium binary found (checked: "
            + ", ".join(CHROME_PATH_CANDIDATES) + " on PATH, $RENDER_CHECK_CHROME,\n"
            "and the Playwright browser cache). Install one, or set\n"
            "RENDER_CHECK_CHROME to its path.",
            file=sys.stderr,
        )
        return 2

    code, messages, log_tail = run_render(chrome, path.as_uri(), out)
    failures = console_failures(messages)
    for message in messages:
        kind = "console error" if message in failures else "console"
        print(f"{kind}: {message}")
    if code != 0:
        print(f"error: Chrome exited with status {code}", file=sys.stderr)
        for line in log_tail:
            print(f"  {line}", file=sys.stderr)
        return 3
    if failures:
        return 3
    if not out.is_file() or out.stat().st_size == 0:
        print(f"error: Chrome wrote no screenshot to {out}", file=sys.stderr)
        return 3

    print(f"OK: {path.name} renders; screenshot: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
