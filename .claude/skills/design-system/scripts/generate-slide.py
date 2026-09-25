#!/usr/bin/env python3
"""Deprecated stub — the slide Generator moved to the uxui:slides skill.

This script used to generate slides against the design-system skill's Node
.cjs token contract (--typography-font-*, --primitive-*, --card-* from
assets/design-tokens.css). That contract is gone; deck generation now runs
on uxui:tokens output. Nothing references this path anymore; the stub only
exists to redirect old invocations.
"""
import sys

REPLACEMENT = "../../slides/scripts/generate.py"


def main():
    print(
        "error: generate-slide.py is deprecated; run the uxui:slides Generator instead:\n"
        f"    python3 {REPLACEMENT} --slides deck.json --tokens tokens/tokens.css --out deck.html",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
