#!/usr/bin/env python3
"""Shared gate for v2 Image jobs: require an OpenRouter API key upfront.

Every Generator that runs an Image job imports this module instead of reading
the environment itself, so a missing key fails here, with one clear line,
before any paid HTTP call is attempted (uxui issue #10; the uxui:image
Generator in issue #11 is the first consumer).

Run directly to check your environment:

    python3 .claude/skills/image/scripts/openrouter_key.py
"""

import os
import sys

KEY_ENV = "OPENROUTER_API_KEY"
MODEL_ENV = "UXUI_IMAGE_MODEL"
# OpenRouter model id for GPT Image 2 (https://openrouter.ai/openai/gpt-image-2).
DEFAULT_IMAGE_MODEL = "openai/gpt-image-2"

_MISSING = (
    f"{KEY_ENV} is not set; Image jobs need it before the first run. "
    "Provision it outside this repo (for example a chezmoi-rendered dotfile), "
    "export it in the environment, and re-run."
)


def require_key() -> str:
    """Return the OpenRouter API key, or exit 2 with a one-line error."""
    key = os.environ.get(KEY_ENV, "").strip()
    if not key:
        print(_MISSING, file=sys.stderr)
        sys.exit(2)
    return key


def image_model() -> str:
    """Return the Image-job model id; UXUI_IMAGE_MODEL overrides the default."""
    return os.environ.get(MODEL_ENV, "").strip() or DEFAULT_IMAGE_MODEL


if __name__ == "__main__":
    require_key()
    print(f"{KEY_ENV} is set")
