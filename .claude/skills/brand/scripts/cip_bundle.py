#!/usr/bin/env python3
"""uxui CIP generator bundle: one Design system, N deliverables, N Image jobs.

A corporate identity program (CIP) mockup set: one brand plus the Design
system its industry row carries (Style, Palette, Font pairing — each
overridable on the CLI) fans out into N deliverables. Each deliverable is
exactly one Image job run through the uxui:image Generator
(../image/scripts/image_job.py), so the per-call cost gate applies to every
deliverable; this bundle never touches the provider itself.

Cost gate — ONE combined confirmation. The plan prints every deliverable
name, its prompt and size, the model, the per-image estimate, and the
TOTAL estimated cost for all N; a single "y" (or --yes) then runs all N
jobs with yes=True. A decline sends zero requests. --dry-run prints the
same plan with no key and no network.

Logo: --logo takes the SVG path the brand logo Generator writes
(scripts/generate.py). OpenRouter's images endpoint does accept reference
images for image-to-image (`input_references`, per
https://openrouter.ai/docs/api/api-reference/images/generate-an-image),
but uxui:image's run_image_job() sends {model, prompt, size} only, so the
logo travels as a text description: the SVG's <title> (which generate.py
writes as "<name> — <style> logo") or --logo-notes, repeated in every
prompt. Without --logo, every prompt asks for a simple mark plus the
wordmark spelled exactly; mark consistency across images is not
guaranteed, so --logo is recommended.

A failed job stops the bundle and lists which deliverables were already
saved and paid for: spend must not continue silently after an error.

Data: data/cip/{deliverables,industries,mockup-contexts}.csv, re-authored
for uxui. The seed catalogs in ../design/data/cip/ stay with the design
skill's search tools.
"""
from __future__ import annotations

import argparse
import colorsys
import csv
import importlib.util
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = SKILL_DIR / "data" / "cip"
# Sibling Generator (issue #11): the only caller of the images endpoint.
IMAGE_JOB_PATH = SKILL_DIR.parent / "image" / "scripts" / "image_job.py"


def _load_image_job():
    spec = importlib.util.spec_from_file_location("uxui_image_job", IMAGE_JOB_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


image_job = _load_image_job()  # import fails loudly if the sibling skill is gone


def load_catalog(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def find_row(rows: list[dict], name_field: str, name: str) -> dict:
    wanted = name.strip().lower()
    for row in rows:
        if row[name_field].strip().lower() == wanted:
            return row
    for row in rows:  # then a prefix/substring match, so "business" finds Business Card
        if wanted in row[name_field].strip().lower():
            return row
    raise SystemExit(f"error: no {name_field.lower()} matching {name!r}. "
                     f"Run with --list to print every name.")


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "item"


def describe_logo(svg_path: str, notes: str) -> str:
    """One sentence describing the logo, read from the SVG's <title>."""
    if notes:
        return notes
    title = ""
    try:
        title = (ET.parse(svg_path).getroot().findtext(".//{*}title") or "").strip()
    except ET.ParseError:
        pass
    # ponytail: <title> text only — a full visual reading of the mark would
    # need a raster step; use --logo-notes when the title is too thin.
    return title or f"the logomark contained in {Path(svg_path).name}"


def color_name(hex_code: str) -> str:
    """Name one hex from hue, lightness, and chroma; coarse is fine.

    The name steers the image model, it does not have to match a swatch
    book. Buckets were checked against every hex in industries.csv.
    """
    r, g, b = (int(hex_code.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))
    hue, light = colorsys.rgb_to_hls(r, g, b)[:2]
    hue *= 360
    chroma = max(r, g, b) - min(r, g, b)
    if light > 0.9:
        return "off-white"
    if light < 0.12:
        return "near-black"
    if chroma < 0.1:
        return "charcoal" if light < 0.3 else "light grey" if light > 0.6 else "grey"
    if hue < 12 or hue >= 348: base = "red"
    elif hue < 35: base = "brown" if chroma < 0.3 and light < 0.55 else "orange"
    elif hue < 55: base = "sand" if light >= 0.7 else "gold" if light >= 0.35 else "bronze"
    elif hue < 165: base = "sage green" if chroma < 0.25 and light > 0.45 else "green"
    elif hue < 200: base = "sky blue" if light > 0.45 else "teal"
    elif hue < 235: base = "navy" if light < 0.32 else "blue"
    elif hue < 285: base = "violet"
    elif hue < 320: base = "purple"
    else: base = "pink"
    depth = "deep " if light < 0.25 else "dark " if light < 0.42 else "light " if light > 0.75 else ""
    return depth + base


def describe_colors(hex_text: str) -> str:
    """Pair every palette hex with a name and a role for the prompt."""
    named = [f"{color_name(h)} {h}" for h in hex_text.split()]
    if not named:
        return "the industry palette"
    parts = [f"{named[0]} as the dominant color"]
    if len(named) > 1:
        parts.append(f"{named[1]} as the accent only")
    if named[2:]:
        parts.append(" and ".join(named[2:]) + " as supporting colors")
    return ", ".join(parts)


def build_prompt(brand: str, industry: dict, deliverable: dict, context: dict,
                 logo_line: str, palette: str | None, typography: str | None) -> str:
    colors = describe_colors(palette or f"{industry['Primary Colors']} {industry['Secondary Colors']}")
    fonts = typography or industry["Typography"]
    # Paper stock is print-specific: it must not leak onto mugs, vans, or screens.
    paper = (f" Paper stock: {industry['Paper Stock']}."
             if deliverable["Category"] in ("Stationery", "Print")
             and industry["Paper Stock"].strip() else "")
    return (f"Photorealistic corporate identity mockup of {deliverable['Description']} "
            f"for '{brand}', a {industry['Industry'].lower()} brand. "
            f"Scene: {context['Scene']}; lighting: {context['Lighting']}; "
            f"camera: {context['Camera']}; props: {context['Props']}. "
            f"Art direction: {industry['Art Direction']}; {deliverable['Prompt Notes']}.{paper} "
            f"Style: {industry['CIP Style']}, {industry['Mood']} mood. "
            f"Palette: {colors}. Typography: {fonts}. {logo_line} "
            f"{context['Prompt Modifiers']}. "
            f"No other brand names, no placeholder or garbled text, no watermark, "
            f"no extra logos; render '{brand}' exactly.")


def total_cost_line(model: str, n: int) -> str:
    estimate = image_job.PRICE_ESTIMATES.get(model)
    if estimate is None:
        return f"{image_job.UNKNOWN_COST}; the total for {n} images is unknown too"
    lo, hi = n * estimate[0], n * estimate[1]
    return f"~${lo:.2f}-${hi:.2f} for {n} images (estimate)"


class Job:
    def __init__(self, name: str, prompt: str, size: str, out_path: Path):
        self.name, self.prompt, self.size, self.out_path = name, prompt, size, out_path


def build_jobs(args, industries, deliverables, contexts) -> list[Job]:
    industry = find_row(industries, "Industry", args.industry)
    logo_line = (f"Logo: {describe_logo(args.logo, args.logo_notes)} — place it as the primary mark."
                 if args.logo else
                 f"Logo: a simple mark plus the wordmark '{args.brand}', spelled exactly, "
                 f"set in the heading font.")
    jobs: list[Job] = []
    for wanted in [d.strip() for d in args.deliverables.split(",") if d.strip()]:
        deliverable = find_row(deliverables, "Deliverable", wanted)
        context = (find_row(contexts, "Context Name", args.mockup) if args.mockup
                   else find_row(contexts, "Context Name", deliverable["Mockup Context"]))
        prompt = build_prompt(args.brand, industry, deliverable, context, logo_line,
                              args.palette, args.typography)
        size = deliverable["Size"].strip() or None
        out_path = Path(args.out_dir) / f"{slugify(args.brand)}-{slugify(deliverable['Deliverable'])}.png"
        jobs.append(Job(deliverable["Deliverable"], prompt, size, out_path))
    if not jobs:
        raise SystemExit("error: --deliverables is empty; run with --list to print every name.")
    return jobs


def print_plan(jobs: list[Job], model: str) -> None:
    for i, job in enumerate(jobs, 1):
        print(f"[{i}/{len(jobs)}] {job.name} -> {job.out_path}"
              + (f" ({job.size})" if job.size else ""))
        print(f"    Prompt: {job.prompt}")
    print(f"Model: {model}")
    print(f"Estimated cost: {image_job.cost_line(model)} x {len(jobs)}")
    print(f"Total estimated cost: {total_cost_line(model, len(jobs))}")


def run_bundle(jobs: list[Job], *, yes: bool = False,
               input=input, http=image_job.post_image_request) -> list[Path]:
    """Print the plan, confirm once for all N, then run N Image jobs."""
    model = image_job.image_model()
    image_job.require_key()  # exits 2 before any prompt is printed or sent
    print_plan(jobs, model)
    names = ", ".join(job.name for job in jobs)
    if not yes:
        answer = input(f"\nRun {len(jobs)} paid Image jobs for {names} on {model} — "
                       f"{total_cost_line(model, len(jobs))}? [y/N] ")
        if answer.strip().lower() != "y":
            print("Declined; no request was sent.")
            return []
    done: list[Job] = []
    try:
        for job in jobs:  # consent covered all N; a failure stops the bundle
            out = image_job.run_image_job(job.prompt, job.out_path, yes=True,
                                          size=job.size, http=http)
            if out:
                done.append(job)
    except BaseException:  # report the spend so far, then let the failure propagate
        print(f"Bundle stopped after {len(done)} of {len(jobs)} deliverables. "
              "Saved and paid for: "
              + (", ".join(f"{j.name} ({j.out_path})" for j in done) or "none") + ".")
        raise
    print(f"{len(done)} of {len(jobs)} deliverables generated in {jobs[0].out_path.parent}.")
    return [job.out_path for job in done]


def main(argv: list[str] | None = None, *,
         input=input, http=image_job.post_image_request) -> int:
    parser = argparse.ArgumentParser(
        prog="cip_bundle.py",
        description="Fan one brand and its Design system out into N CIP mockup "
                    "Image jobs through uxui:image, behind one combined cost gate.")
    parser.add_argument("--brand", help="brand name (required unless --list)")
    parser.add_argument("--industry", help="Industry name from data/cip/industries.csv; "
                        "supplies the default Style, Palette, and Font pairing")
    parser.add_argument("--deliverables", help="comma-separated Deliverable names "
                        "from data/cip/deliverables.csv")
    parser.add_argument("--out-dir", help="output directory (default: <brand>-cip)")
    parser.add_argument("--palette", help="override the industry Palette, for example "
                        "'#123B5A #C9A227'")
    parser.add_argument("--typography", help="override the industry Font pairing")
    parser.add_argument("--mockup", help="override the mockup context for every "
                        "deliverable (name from data/cip/mockup-contexts.csv)")
    parser.add_argument("--logo", help="SVG path from scripts/generate.py; described "
                        "as text in every prompt")
    parser.add_argument("--logo-notes", help="logo description override for --logo")
    parser.add_argument("--yes", action="store_true",
                        help="skip the single combined confirmation")
    parser.add_argument("--dry-run", action="store_true",
                        help="print every prompt and the total cost; no key, no network")
    parser.add_argument("--list", action="store_true",
                        help="list Deliverables, Industries, and mockup contexts, then exit")
    args = parser.parse_args(argv)

    industries = load_catalog(DATA_DIR / "industries.csv")
    deliverables = load_catalog(DATA_DIR / "deliverables.csv")
    contexts = load_catalog(DATA_DIR / "mockup-contexts.csv")

    if args.list:
        for label, rows, field in (("Deliverables", deliverables, "Deliverable"),
                                   ("Industries", industries, "Industry"),
                                   ("Mockup contexts", contexts, "Context Name")):
            print(f"{label}: " + ", ".join(row[field] for row in rows))
        return 0

    missing = [flag for flag, value in (("--brand", args.brand),
                                        ("--industry", args.industry),
                                        ("--deliverables", args.deliverables)) if not value]
    if missing:
        parser.error(" and ".join(missing) + " are required unless --list")
    args.out_dir = args.out_dir or f"{slugify(args.brand)}-cip"

    jobs = build_jobs(args, industries, deliverables, contexts)
    model = image_job.image_model()

    if args.dry_run:
        print_plan(jobs, model)
        print(f"Dry run: {len(jobs)} Image jobs would run, "
              f"{total_cost_line(model, len(jobs))}; no request was sent.")
        return 0

    return 0 if run_bundle(jobs, yes=args.yes, input=input, http=http) else 1


if __name__ == "__main__":
    sys.exit(main())
