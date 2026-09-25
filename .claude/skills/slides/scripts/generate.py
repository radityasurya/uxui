#!/usr/bin/env python3
"""uxui:slides Generator — write one deck HTML with real Chart.js charts.

Consumes one Design system's Tokens (the uxui:tokens Generator output) plus a
slide-content JSON file and writes a self-contained deck: every color and font
comes from the inlined ``tokens.css``, every chart is a Chart.js canvas fed by
chart types cataloged in ``../design-system/data/slide-charts.csv``, loaded
from a CDN <script> tag pinned to Chart.js 4.

``../design-system/scripts/generate-slide.py`` is a deprecated stub that
points here: it targeted the design-system skill's Node .cjs token contract
(``--typography-font-*``, ``--primitive-*``, ``--card-*``), which the
uxui:tokens Generator does not emit, and drew its charts as CSS bars.

Python standard library only.

Usage:
    python3 scripts/generate.py --slides deck.json --tokens tokens/tokens.css \
        [--out deck.html] [--chartjs URL]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from html import escape
from pathlib import Path
from urllib.parse import quote_plus

SCRIPT_DIR = Path(__file__).resolve().parent
CHARTS_CSV = SCRIPT_DIR.parent.parent / "design-system" / "data" / "slide-charts.csv"

# CDN build pinned to one major version (v4) so minor updates cannot change
# the chart API under a shipped deck.
CHARTJS_CDN = "https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"

# Chart.js-expressible subset of slide-charts.csv: CSV row id →
# (Chart.js type, options flags, aliases). Rows the table catalogs but a
# plain Chart.js build cannot draw (funnel, sankey, treemap, ...) are left
# out on purpose; resolve_chart names them when asked for.
CHART_KINDS = {
    1: ("bar", {}, ("bar", "bar-vertical")),
    2: ("bar", {"indexAxis": "y"}, ("hbar", "bar-horizontal")),
    3: ("line", {}, ("line",)),
    4: ("line", {"fill": True}, ("area",)),
    5: ("pie", {}, ("pie",)),
    6: ("doughnut", {}, ("donut", "doughnut")),
    7: ("bar", {"stacked": True}, ("stacked-bar", "stacked")),
    8: ("bar", {}, ("grouped-bar", "grouped")),
    18: ("radar", {}, ("radar",)),
}

# Series color cycle: primary, accent, then large shade steps of each against
# the background and foreground tokens (≥45% mixed away, so adjacent series
# stay clearly distinct in light and dark palettes alike). No secondary or
# *-hover roles — those sit too close to primary/accent to tell apart on a
# chart. Resolved against the inlined tokens at runtime; the deck script
# computes each expression through a probe element, so any token color
# format works.
SERIES_COLORS = [
    "var(--color-primary)",
    "var(--color-accent)",
    "color-mix(in srgb, var(--color-primary) 45%, var(--color-background))",
    "color-mix(in srgb, var(--color-primary) 55%, var(--color-foreground))",
    "color-mix(in srgb, var(--color-accent) 45%, var(--color-background))",
    "color-mix(in srgb, var(--color-accent) 55%, var(--color-foreground))",
    "color-mix(in srgb, var(--color-primary) 22%, var(--color-background))",
    "color-mix(in srgb, var(--color-accent) 22%, var(--color-background))",
]

# A slide taller than its 16:9 frame cannot scroll, so more bullets than this
# split into "(cont.)" continuation slides instead of silently clipping.
MAX_BULLETS = 5


def _e(value, default=""):
    """HTML-escape a user-supplied value for safe embedding in HTML."""
    return escape(str(value if value is not None and value != "" else default), quote=True)


# ---------- chart types (slide-charts.csv) ----------
def load_chart_rows():
    """[{id, name, keywords}] from the design-system slide chart catalog."""
    if not CHARTS_CSV.is_file():
        raise SystemExit(f"error: chart catalog not found: {CHARTS_CSV}")
    with CHARTS_CSV.open(encoding="utf-8", newline="") as fh:
        rows = [
            {
                "id": int(row["id"]),
                "name": row["chart_type"].strip(),
                "keywords": [k.strip().lower() for k in row["keywords"].split(",")],
            }
            for row in csv.DictReader(fh)
        ]
    missing = set(CHART_KINDS) - {row["id"] for row in rows}
    if missing:
        raise SystemExit(
            f"error: slide-charts.csv no longer carries rows {sorted(missing)}; "
            "update CHART_KINDS in this script"
        )
    return rows


def resolve_chart(name):
    """CSV row id for a chart request: alias, row id, chart_type, or keyword."""
    key = str(name).strip().lower()
    supported = ", ".join(
        f"{aliases[0]} (csv id {cid})" for cid, (_, _, aliases) in sorted(CHART_KINDS.items())
    )
    if key.isdigit() and int(key) in CHART_KINDS:
        return int(key)
    for cid, (_, _, aliases) in CHART_KINDS.items():
        if key in aliases:
            return cid
    for row in load_chart_rows():
        if key == row["name"].lower() or key in row["keywords"]:
            if row["id"] in CHART_KINDS:
                return row["id"]
            raise ValueError(
                f"chart {name!r} is {row['name']!r} in slide-charts.csv, which a "
                "plain Chart.js build cannot draw; pick one of: " + supported
            )
    raise ValueError(f"unknown chart type {name!r}; supported: {supported}")


def build_chart_payload(slide, canvas_id):
    """One chart as the deck's JSON payload: Chart.js type, flags, series."""
    chart = slide.get("chart") or {}
    chartjs_type, flags, _ = CHART_KINDS[resolve_chart(chart.get("type", "bar"))]
    labels = chart.get("labels") or []
    series = chart.get("series") or [{"label": "Series 1", "data": [0] * len(labels)}]
    for entry in series:
        if not isinstance(entry.get("data"), list):
            raise ValueError(f"chart series {entry.get('label')!r} has no data list")
    payload = {
        "canvas": canvas_id,
        "type": chartjs_type,
        "title": str(chart.get("title") or slide.get("headline") or "Chart"),
        "labels": [str(x) for x in labels],
        "series": [{"label": str(s.get("label") or ""), "data": s["data"]} for s in series],
    }
    payload.update(flags)
    return payload


# ---------- slides ----------
def _footer(left, right):
    return (
        f'<footer class="slide-footer"><span>{_e(left)}</span>'
        f"<span>{_e(right)}</span></footer>"
    )


def render_title(slide, ctx):
    date = slide.get("date") or datetime.now().strftime("%B %Y")
    return f'''
    <section class="slide slide--center" id="slide-{ctx["index"]}">
        <div class="slide-core">
            <p class="badge">{_e(slide.get("badge"), "Deck")}</p>
            <h1 class="slide-title">{_e(slide.get("title"), ctx["title"])}</h1>
            <p class="slide-subtitle">{_e(slide.get("subtitle"), "")}</p>
        </div>
        {_footer(ctx["company"], date)}
    </section>'''


def render_content(slide, ctx):
    bullets = "".join(
        f'''
        <div class="bullet">
            <span class="bullet-no">{i:02d}</span>
            <div>
                <h3 class="bullet-title">{_e(b.get("title"), "Point")}</h3>
                <p class="bullet-text">{_e(b.get("text"), "")}</p>
            </div>
        </div>'''
        for i, b in enumerate(slide.get("bullets") or [], start=1)
    )
    return f'''
    <section class="slide" id="slide-{ctx["index"]}">
        <p class="badge">{_e(slide.get("badge"), "Detail")}</p>
        <h2 class="slide-heading">{_e(slide.get("headline"), ctx["title"])}</h2>
        <div class="bullets">{bullets}</div>
        {_footer(ctx["company"], ctx["page"])}
    </section>'''


def render_chart(slide, ctx):
    payload = build_chart_payload(slide, ctx["canvas_id"])
    ctx["charts"].append(payload)
    # A chart title that just repeats the slide headline adds a smaller,
    # redundant copy of the same line; keep it only when it says more.
    headline = str(slide.get("headline") or "").strip().casefold()
    title_line = ""
    if headline != payload["title"].strip().casefold():
        title_line = f'<p class="chart-title">{_e(payload["title"])}</p>'
    return f'''
    <section class="slide" id="slide-{ctx["index"]}">
        <p class="badge">{_e(slide.get("badge"), "Data")}</p>
        <h2 class="slide-heading">{_e(slide.get("headline"), payload["title"])}</h2>
        <div class="chart-card">
            {title_line}
            <div class="chart-box">
                <canvas id="{payload["canvas"]}" role="img"
                    aria-label="{_e(payload["title"])} chart drawn with Chart.js"></canvas>
            </div>
        </div>
        {_footer(ctx["company"], ctx["page"])}
    </section>'''


def render_closing(slide, ctx):
    return f'''
    <section class="slide slide--center" id="slide-{ctx["index"]}">
        <div class="slide-core">
            <h2 class="slide-heading">{_e(slide.get("headline"), "Thank you")}</h2>
            <p class="slide-subtitle">{_e(slide.get("subheadline"), "")}</p>
            <a class="btn" href="{_e(slide.get("cta_url"), "#contact")}">
                {_e(slide.get("cta"), "Get in touch")}</a>
        </div>
        {_footer(slide.get("contact", ctx["company"]), slide.get("website", ""))}
    </section>'''


SLIDE_RENDERERS = {
    "title": render_title,
    "content": render_content,
    "chart": render_chart,
    "closing": render_closing,
}


# ---------- deck document ----------
# Each slide fills the viewport's 16:9 area (letterboxed on other shapes),
# snapped one-per-screen; type scales with the slide through cqw preferred
# sizes clamped between token steps, so a deck holds up on a laptop and on a
# 1920px projector alike.
DECK_CSS = '''
        /* Deck styles: every color, font, and size bound is a uxui:tokens variable. */
        * { margin: 0; padding: 0; box-sizing: border-box; }
        html { scroll-snap-type: y mandatory; }
        body {
            background: var(--color-muted);
            font-family: var(--font-body);
            line-height: var(--line-height-normal);
        }
        .deck { display: flex; flex-direction: column; align-items: center; }
        .slide {
            /* 100% (not 100vw) so a scrollbar cannot cause horizontal overflow;
               aspect-ratio keeps 16:9 when the maxes do not bind. */
            width: 100%;
            max-width: calc(100vh * 16 / 9);
            aspect-ratio: 16 / 9;
            max-height: 100vh;
            flex: none;
            scroll-snap-align: center;
            scroll-snap-stop: always;
            container-type: inline-size;
            background: var(--color-background);
            padding: clamp(var(--spacing-xl), 4cqw, var(--spacing-3xl));
            display: flex; flex-direction: column;
            overflow: hidden;
        }
        h1, h2, h3 {
            font-family: var(--font-heading);
            font-weight: var(--font-weight-bold);
            line-height: var(--line-height-tight);
            color: var(--color-foreground);
        }
        .badge {
            align-self: flex-start;
            font-size: clamp(var(--font-size-xs), 1.1cqw, var(--font-size-2xl));
            font-weight: var(--font-weight-medium);
            color: var(--color-accent-text);
            background: color-mix(in srgb, var(--color-accent) 14%, transparent);
            border-radius: var(--radius-full);
            padding: var(--spacing-xs) var(--spacing-md);
        }
        .slide--center .badge { align-self: center; }
        /* flex:1 core keeps title/closing content centered in the frame while
           the footer stays pinned to the slide's bottom edge. */
        .slide-core {
            flex: 1; min-height: 0;
            display: flex; flex-direction: column;
            justify-content: center; align-items: center; text-align: center;
            gap: clamp(var(--spacing-sm), 1.2cqw, var(--spacing-lg));
        }
        .slide-title {
            font-size: clamp(var(--font-size-3xl), 4.5cqw, var(--font-size-6xl));
            max-width: 24ch;
        }
        .slide-subtitle {
            font-size: clamp(var(--font-size-lg), 1.05cqw, var(--font-size-2xl));
            color: var(--color-muted-foreground); max-width: 48ch;
        }
        /* The headline is the largest text on any slide — bigger than the
           Chart.js ticks and legend below, or the hierarchy inverts. */
        .slide-heading {
            font-size: clamp(var(--font-size-3xl), 3.5cqw, var(--font-size-6xl));
            margin-bottom: clamp(var(--spacing-sm), 1.2cqw, var(--spacing-lg));
        }
        .bullets {
            display: flex; flex-direction: column;
            gap: clamp(var(--spacing-sm), 1.2cqw, var(--spacing-xl));
        }
        .bullet { display: flex; gap: clamp(var(--spacing-sm), 1cqw, var(--spacing-lg)); align-items: baseline; }
        .bullet-no {
            font-family: var(--font-heading); font-weight: var(--font-weight-bold);
            font-size: clamp(var(--font-size-lg), 1.25cqw, var(--font-size-3xl));
            color: var(--color-accent-text);
            min-width: 2ch; font-variant-numeric: tabular-nums;
        }
        .bullet-title { font-size: clamp(var(--font-size-sm), 0.95cqw, var(--font-size-xl)); margin-bottom: var(--spacing-xs); }
        .bullet-text {
            font-size: clamp(var(--font-size-xs), 0.85cqw, var(--font-size-lg));
            color: var(--color-muted-foreground);
        }
        .chart-card {
            background: var(--color-card); color: var(--color-card-foreground);
            border: 1px solid var(--color-border); border-radius: var(--radius-lg);
            padding: clamp(var(--spacing-md), 1.5cqw, var(--spacing-xl));
            flex: 1; min-height: 0;
            display: flex; flex-direction: column;
        }
        /* Between the tick size and the headline: a subtitle to the slide's
           headline, not a rival to it. */
        .chart-title {
            font-family: var(--font-heading); font-weight: var(--font-weight-semibold);
            font-size: clamp(var(--font-size-2xl), 1.8cqw, var(--font-size-4xl));
            margin-bottom: var(--spacing-sm);
        }
        .chart-box { position: relative; flex: 1; min-height: 0; }
        .chart-box canvas { position: absolute; inset: 0; }
        .btn {
            display: inline-block; text-decoration: none;
            background: var(--button-background); color: var(--button-foreground);
            padding: var(--button-padding-y) var(--button-padding-x);
            border-radius: var(--button-radius);
            font-size: var(--button-font-size); font-weight: var(--button-font-weight);
        }
        .slide-footer {
            margin-top: auto; display: flex; justify-content: space-between;
            align-self: stretch;
            padding-top: var(--spacing-md); border-top: 1px solid var(--color-border);
            font-size: clamp(var(--font-size-xs), 1cqw, var(--font-size-xl));
            color: var(--color-muted-foreground);
        }
        @media print {
            html { scroll-snap-type: none; }
            body { background: var(--color-background); }
            .slide { page-break-after: always; break-inside: avoid; }
        }
'''

# Chart colors are read from the inlined tokens.css at runtime (getComputedStyle),
# never hardcoded: series colors cycle SERIES_COLORS (resolved through an
# attached probe element, so var()/color-mix() expressions become concrete
# canvas colors), grids and text use the border and muted-foreground tokens,
# tooltips use the card surface.
DECK_JS = '''
        (function () {
            var charts = JSON.parse(document.getElementById('deck-charts').textContent);
            var root = getComputedStyle(document.documentElement);
            function tok(name) { return root.getPropertyValue(name).trim(); }
            var probe = document.createElement('span');
            probe.style.display = 'none';
            document.documentElement.appendChild(probe);
            function resolve(expr) {
                probe.style.color = '';
                probe.style.color = expr;
                return getComputedStyle(probe).color;
            }
            // pct is a 0–1 fraction; color-mix() takes a percentage.
            function alpha(color, pct) {
                return 'color-mix(in srgb, ' + color + ' ' + Math.round(pct * 100) + '%, transparent)';
            }
            var SERIES = __SERIES__;
            var grid = tok('--color-border');
            Chart.defaults.font.family = tok('--font-body');
            Chart.defaults.color = tok('--color-muted-foreground');
            charts.forEach(function (c) {
                var box = document.getElementById(c.canvas).parentElement;
                var width = box.clientWidth;
                // ~1.2cqw of slide width (box ≈ 0.9× slide): ticks and legend
                // stay well under the headline clamp above.
                Chart.defaults.font.size = Math.max(12, Math.min(40, Math.round(width / 75)));
                var colors = c.series.map(function (_, i) { return resolve(SERIES[i % SERIES.length]); });
                var sliceColors = c.labels.map(function (_, i) { return resolve(SERIES[i % SERIES.length]); });
                var datasets;
                if (c.type === 'pie' || c.type === 'doughnut') {
                    datasets = [{ data: c.series[0].data, backgroundColor: sliceColors,
                                  borderColor: tok('--color-card'), borderWidth: 2 }];
                } else if (c.type === 'line') {
                    datasets = c.series.map(function (s, i) {
                        return { label: s.label, data: s.data, borderColor: colors[i],
                                 hoverBorderColor: colors[i], pointHoverBackgroundColor: colors[i],
                                 backgroundColor: alpha(colors[i], c.fill ? 0.25 : 0.08),
                                 hoverBackgroundColor: alpha(colors[i], c.fill ? 0.25 : 0.08),
                                 fill: !!c.fill, tension: 0.35,
                                 pointBackgroundColor: colors[i], pointRadius: 3 };
                    });
                } else if (c.type === 'radar') {
                    datasets = c.series.map(function (s, i) {
                        return { label: s.label, data: s.data, borderColor: colors[i],
                                 hoverBorderColor: colors[i], pointHoverBackgroundColor: colors[i],
                                 backgroundColor: alpha(colors[i], 0.2),
                                 hoverBackgroundColor: alpha(colors[i], 0.2),
                                 pointBackgroundColor: colors[i] };
                    });
                } else {
                    datasets = c.series.map(function (s, i) {
                        return { label: s.label, data: s.data,
                                 backgroundColor: alpha(colors[i], 0.85),
                                 hoverBackgroundColor: colors[i], borderRadius: 4 };
                    });
                }
                var round = c.type === 'pie' || c.type === 'doughnut' || c.type === 'radar';
                var options = {
                    responsive: true, maintainAspectRatio: false,
                    animation: false,
                    plugins: {
                        legend: {
                            position: 'bottom',
                            display: round || c.series.length > 1,
                            labels: { color: tok('--color-foreground'),
                                      boxWidth: Math.max(10, Math.round(width / 80)),
                                      boxHeight: Math.max(10, Math.round(width / 80)) }
                        },
                        tooltip: {
                            backgroundColor: tok('--color-card'),
                            titleColor: tok('--color-card-foreground'),
                            bodyColor: tok('--color-card-foreground'),
                            borderColor: tok('--color-border'), borderWidth: 1
                        }
                    },
                    scales: round ? {} : {
                        x: { stacked: !!c.stacked, grid: { display: false } },
                        y: { stacked: !!c.stacked, beginAtZero: true, grid: { color: grid } }
                    }
                };
                if (c.indexAxis) { options.indexAxis = c.indexAxis; }
                new Chart(document.getElementById(c.canvas), { type: c.type, data: { labels: c.labels, datasets: datasets }, options: options });
            });

            // Keyboard deck navigation: one slide per key press, snapped.
            var slides = Array.prototype.slice.call(document.querySelectorAll('.slide'));
            function go(i) {
                i = Math.max(0, Math.min(slides.length - 1, i));
                slides[i].scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
            document.addEventListener('keydown', function (ev) {
                if (ev.metaKey || ev.ctrlKey || ev.altKey) { return; }
                var current = 0, best = Infinity;
                slides.forEach(function (s, i) {
                    var d = Math.abs(s.getBoundingClientRect().top);
                    if (d < best) { best = d; current = i; }
                });
                var k = ev.key;
                var next = { ArrowDown: 1, ArrowRight: 1, PageDown: 1, ' ': 1,
                             ArrowUp: -1, ArrowLeft: -1, PageUp: -1 }[k];
                if (next) { ev.preventDefault(); go(current + next); }
                else if (k === 'Home') { ev.preventDefault(); go(0); }
                else if (k === 'End') { ev.preventDefault(); go(slides.length - 1); }
            });
        })();
'''


def deck_js():
    """DECK_JS with the SERIES_COLORS cycle embedded as JSON."""
    return DECK_JS.replace("__SERIES__", json.dumps(SERIES_COLORS))


def google_fonts_link(tokens_css):
    """Google Fonts css2 link for the Font pairing, from the sibling tokens.json.

    The tokens Generator keeps tokens.css values-only and leaves the fonts
    import to the page (see uxui:tokens SKILL.md), so the deck builds it from
    the DTCG font.family tokens. Missing tokens.json means no link; the font
    stacks in tokens.css still carry their fallbacks.
    """
    tokens_json = tokens_css.with_name("tokens.json")
    if not tokens_json.is_file():
        return ""
    try:
        families = json.loads(tokens_json.read_text(encoding="utf-8"))["primitive"]["font"]["family"]
        names = []
        for slot in ("heading", "body"):
            value = families.get(slot, {}).get("$value")
            if isinstance(value, list) and value and isinstance(value[0], str):
                name = value[0].strip()
                if name and name not in names:
                    names.append(name)
    except (KeyError, ValueError, OSError):
        return ""
    if not names:
        return ""
    families_q = "&".join("family=" + quote_plus(n) for n in names)
    return (
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?{families_q}&display=swap">'
    )


def expand_slides(slides, deck_title):
    """Copy of the slide list with over-long bullet slides split.

    A slide holds at most MAX_BULLETS bullets; a longer list splits into
    MAX_BULLETS-sized chunks, each continuation headed "<headline> (cont.)".
    Anything else passes through untouched.
    """
    expanded = []
    for slide in slides:
        bullets = slide.get("bullets") if slide.get("type") == "content" else None
        if bullets is None or len(bullets) <= MAX_BULLETS:
            expanded.append(slide)
            continue
        headline = str(slide.get("headline") or deck_title)
        for chunk_no, start in enumerate(range(0, len(bullets), MAX_BULLETS)):
            part = dict(slide, bullets=bullets[start:start + MAX_BULLETS])
            if chunk_no:
                part["headline"] = f"{headline} (cont.)"
            expanded.append(part)
    return expanded


def render_deck(doc, tokens_css_text, fonts_link, chartjs_src):
    """Assemble the full deck HTML document from a slides JSON dict."""
    ctx = {
        "title": doc.get("title") or "Presentation",
        "company": doc.get("company") or "",
        "charts": [],
    }
    if not doc.get("slides"):
        raise ValueError("deck has no slides")
    slides = expand_slides(doc["slides"], ctx["title"])
    total = len(slides)
    parts = []
    for index, slide in enumerate(slides, start=1):
        slide_type = slide.get("type")
        renderer = SLIDE_RENDERERS.get(slide_type)
        if renderer is None:
            raise ValueError(
                f"unknown slide type {slide_type!r} (slide {index}); "
                f"expected one of {', '.join(SLIDE_RENDERERS)}"
            )
        ctx["index"] = index
        ctx["page"] = f"{index:02d} / {total:02d}"
        ctx["canvas_id"] = f"chart-{index}"
        parts.append(renderer(slide, ctx))

    # JSON payload for the chart script; </ is escaped so a closing HTML tag
    # inside user data cannot end the <script> element early.
    charts_json = json.dumps(ctx["charts"], ensure_ascii=False).replace("</", "<\\/")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{_e(doc.get("title"), "Presentation")}</title>
    {fonts_link}
    <style>{DECK_CSS}
    </style>
    <style>
/* uxui:tokens output, inlined from tokens.css — regenerate, do not edit. */
{tokens_css_text}
    </style>
</head>
<body>
    <main class="deck">
{"".join(parts)}
    </main>
    <script id="deck-charts" type="application/json">{charts_json}</script>
    <script src="{_e(chartjs_src)}"></script>
    <script>{deck_js()}
    </script>
</body>
</html>
"""


# ---------- CLI ----------
def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="generate.py",
        description="Write one deck HTML with real Chart.js charts from uxui:tokens output.",
    )
    parser.add_argument(
        "--slides", required=True, metavar="JSON",
        help="slide-content JSON file: {title, company, slides: [{type, ...}]}",
    )
    parser.add_argument(
        "--tokens", required=True, metavar="CSS",
        help="tokens.css written by the uxui:tokens Generator (its sibling "
             "tokens.json supplies the Google Fonts link)",
    )
    parser.add_argument("--out", default="deck.html", metavar="HTML",
                        help="output deck file (default: ./deck.html)")
    parser.add_argument(
        "--chartjs", default=CHARTJS_CDN, metavar="SRC",
        help="Chart.js script src (default: jsdelivr CDN pinned to v4; pass a "
             "vendored file name to build fully offline decks)",
    )
    args = parser.parse_args(argv)

    doc = json.loads(Path(args.slides).read_text(encoding="utf-8"))
    tokens_css = Path(args.tokens)
    html = render_deck(
        doc,
        tokens_css.read_text(encoding="utf-8"),
        google_fonts_link(tokens_css),
        args.chartjs,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
