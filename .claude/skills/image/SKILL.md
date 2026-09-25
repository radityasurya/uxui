---
name: image
description: "Cost-gated Image jobs for Generators: one paid image-generation call to OpenRouter (GPT Image 2 by default, UXUI_IMAGE_MODEL to override) with the model, prompt, and estimated cost printed and an explicit confirmation required before every request. Actions: generate image, create raster asset, run an Image job."
argument-hint: "[prompt]"
license: MIT
metadata:
  author: uxui
  version: "2.0.0"
---

# Image job

One paid image-generation call to OpenRouter's `POST /api/v1/images`, used only
inside a Generator that needs a raster or illustrated asset. Every call passes
the cost gate first: the model, the prompt, and an estimated cost are printed,
and the job runs only after an interactive `y` — or `--yes` for scripted use.
A declined job sends no request.

## When to activate

- A Generator needs a raster or illustrated asset that CSS or SVG cannot express.
- The user asks for a generated image, photo-style art, or an illustration.

Do not activate for icon sets, logos, banners, or slides that stay vector or
HTML — those Generators build their output locally.

## Environment

- `OPENROUTER_API_KEY` — required. Check it with:

  ```bash
  python3 scripts/openrouter_key.py
  ```

- `UXUI_IMAGE_MODEL` — optional. Overrides the default GPT Image 2
  (`openai/gpt-image-2`). Models without a price row print
  "unknown model: cost unknown" and still require confirmation.

## Run an Image job

From this skill's directory:

```bash
python3 scripts/image_job.py --prompt "flat vector illustration of a calm dashboard, teal palette" --out hero.png [--size 1024x1024] [--yes]
```

Add `--dry-run` to print the request (with the key redacted) instead of
sending it.

From a sibling Generator, shell out with
`python3 ../image/scripts/image_job.py …`, or import and call:

```python
spec = importlib.util.spec_from_file_location(
    "image_job", SKILL_DIR / "../image/scripts/image_job.py")
image_job = importlib.util.module_from_spec(spec)
spec.loader.exec_module(image_job)
saved = image_job.run_image_job(prompt, out_path, yes=True)
```

The response arrives as `data[0].b64_json` (the endpoint returns base64 only,
no URL); the script decodes it, writes the image to the out path, prints the
actual `usage.cost`, and returns the saved `Path` — or `None` when declined.
