#!/usr/bin/env python3
"""uxui Image job: one paid image-generation call, gated on a cost estimate.

An Image job is a paid, per-call request to OpenRouter's image endpoint,
unlike every v1 Generator, which runs locally. This module is the only caller:
a Generator that needs a raster asset imports run_image_job() or shells out
to this CLI, and never touches the provider itself (uxui issue #11).

The cost gate prints the model, the prompt, and an estimated cost, then
requires an interactive "y" (or --yes for scripted use) before any HTTP call.
A declined job returns None without sending a request. A missing
OPENROUTER_API_KEY exits before the gate (issue #10).

Schema per https://openrouter.ai/docs/api/api-reference/images/generate-an-image:
request {"model", "prompt", optional "size"}; response data[].b64_json holds
the base64 image bytes — the endpoint returns no url field.
"""

import argparse
import base64
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:  # let Generators load this file by path
    sys.path.insert(0, str(_SCRIPTS_DIR))

from openrouter_key import image_model, require_key  # noqa: E402

API_URL = "https://openrouter.ai/api/v1/images"

# Per-image USD estimates. Source: OpenRouter endpoints API,
# https://openrouter.ai/api/v1/models/openai/gpt-image-2/endpoints
# ($0.000008 per text token, $0.00003 per image-output token), applied to the
# docs' example of a 4,175-token high-quality image
# (https://openrouter.ai/docs/api/api-reference/images/generate-an-image).
# ponytail: estimate, not a quote — the token count varies with size and
# quality; the response's usage.cost is printed after the call, which trues
# the estimate up. Add a row here when a new UXUI_IMAGE_MODEL becomes common.
PRICE_ESTIMATES = {
    "openai/gpt-image-2": (0.03, 0.14),
}
UNKNOWN_COST = "unknown model: cost unknown"


def cost_line(model: str) -> str:
    """Return the printed cost estimate for one image on this model."""
    estimate = PRICE_ESTIMATES.get(model)
    if estimate is None:
        return UNKNOWN_COST
    return f"~${estimate[0]:.2f}-${estimate[1]:.2f} per image (estimate)"


def post_image_request(url, payload, key):
    """POST the JSON payload and return the parsed response."""
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _payload(prompt, size):
    payload = {"model": image_model(), "prompt": prompt}
    if size:
        payload["size"] = size
    return payload


def run_image_job(prompt, out_path, *, yes=False, size=None,
                  input=input, http=post_image_request):
    """Run one Image job; return the saved Path, or None if declined.

    Prints the model, prompt, and estimated cost, then requires an
    interactive "y" (or yes=True) before the single HTTP call.
    """
    key = require_key()  # exits 2 before anything paid if the key is unset
    model = image_model()
    print(f"Model: {model}")
    print(f"Prompt: {prompt}")
    if size:
        print(f"Size: {size}")
    print(f"Estimated cost: {cost_line(model)}")
    if not yes:
        answer = input("Run this paid Image job? [y/N] ")
        if answer.strip().lower() != "y":
            print("Declined; no request was sent.")
            return None

    response = http(API_URL, _payload(prompt, size), key)
    data = response.get("data") or []
    if not data or "b64_json" not in data[0]:
        raise SystemExit(
            "Unexpected response (expected data[0].b64_json): "
            + json.dumps(response)[:300]
        )
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(base64.b64decode(data[0]["b64_json"]))
    actual = response.get("usage", {}).get("cost")
    if actual is not None:
        print(f"Actual cost: ${actual}")
    print(f"Saved: {out_path}")
    return out_path


def main(argv=None, *, input=input, http=post_image_request):
    parser = argparse.ArgumentParser(
        description="Run one cost-gated Image job against OpenRouter (uxui #11)."
    )
    parser.add_argument("--prompt", required=True, help="image prompt")
    parser.add_argument("--out", required=True, help="output image path")
    parser.add_argument("--size", help="image size, for example 1024x1024 or 2K")
    parser.add_argument("--yes", action="store_true",
                        help="skip the interactive confirmation")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the request without sending it (no network)")
    args = parser.parse_args(argv)

    if args.dry_run:
        key = require_key()
        print(f"POST {API_URL}")
        print(f"Authorization: Bearer {key[:7]}... (redacted)")
        print(f"Estimated cost: {cost_line(image_model())}")
        print(json.dumps(_payload(args.prompt, args.size), indent=2))
        return 0

    try:
        saved = run_image_job(args.prompt, args.out, yes=args.yes, size=args.size,
                              input=input, http=http)
    except urllib.error.HTTPError as err:  # the paid call failed; show the body
        print(f"HTTP {err.code}: {err.read().decode('utf-8', 'replace')}",
              file=sys.stderr)
        return 3
    return 0 if saved else 1


if __name__ == "__main__":
    sys.exit(main())
