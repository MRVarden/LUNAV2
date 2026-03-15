#!/usr/bin/env python3
"""Luna v7.0 — UML Diagram Renderer.

Converts PlantUML .puml files to SVG and high-quality PNG with thumbnails.
Large diagrams are split into readable parts.

Dependencies:
  - Java (for PlantUML)
  - plantuml.jar (auto-downloaded if missing)
  - pip: cairosvg, pillow

Usage: python3 render.py [--skip-download] [--svg-only]
Output: uml_diagrams/output/*.svg, *.png, *_thumb.png
"""

from __future__ import annotations

import argparse
import logging
import math
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

log = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
PLANTUML_JAR = Path(__file__).resolve().parent / "plantuml.jar"
PLANTUML_URL = "https://github.com/plantuml/plantuml/releases/download/v1.2024.8/plantuml-1.2024.8.jar"

# Rendering settings
PNG_DPI = 200  # High DPI for crisp text
THUMB_WIDTH = 800  # Thumbnail width in pixels
MAX_PART_HEIGHT = 3000  # Max height per PNG part (pixels at PNG_DPI)


def ensure_plantuml() -> Path:
    """Download plantuml.jar if not present."""
    if PLANTUML_JAR.is_file():
        log.info("PlantUML jar found: %s", PLANTUML_JAR)
        return PLANTUML_JAR

    log.info("Downloading PlantUML from %s ...", PLANTUML_URL)
    try:
        urllib.request.urlretrieve(PLANTUML_URL, PLANTUML_JAR)
        log.info("Downloaded: %s", PLANTUML_JAR)
    except Exception as exc:
        log.error("Failed to download PlantUML: %s", exc)
        log.error("Please download manually: %s", PLANTUML_URL)
        sys.exit(1)
    return PLANTUML_JAR


def render_puml_to_svg(puml_path: Path, jar: Path) -> Path | None:
    """Render a .puml file to SVG using PlantUML."""
    svg_path = puml_path.with_suffix(".svg")
    cmd = [
        "java", "-jar", str(jar),
        "-tsvg",
        "-charset", "UTF-8",
        "-o", str(puml_path.parent),
        str(puml_path),
    ]
    log.info("Rendering SVG: %s", puml_path.name)
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            log.error("PlantUML error for %s:\n%s", puml_path.name, result.stderr)
            return None
    except subprocess.TimeoutExpired:
        log.error("PlantUML timed out for %s", puml_path.name)
        return None

    if svg_path.is_file():
        log.info("  -> %s (%d KB)", svg_path.name, svg_path.stat().st_size // 1024)
        return svg_path
    else:
        log.error("SVG not created: %s", svg_path)
        return None


def svg_to_png(svg_path: Path, dpi: int = PNG_DPI) -> Path | None:
    """Convert SVG to high-resolution PNG using CairoSVG."""
    try:
        import cairosvg
    except ImportError:
        log.error("cairosvg not installed: pip install cairosvg")
        return None

    png_path = svg_path.with_suffix(".png")
    try:
        cairosvg.svg2png(
            url=str(svg_path),
            write_to=str(png_path),
            dpi=dpi,
            background_color="#1A1A2E",
        )
        log.info("  -> %s (%d KB)", png_path.name, png_path.stat().st_size // 1024)
        return png_path
    except Exception as exc:
        log.error("CairoSVG error for %s: %s", svg_path.name, exc)
        return None


def split_png_parts(png_path: Path, max_height: int = MAX_PART_HEIGHT) -> list[Path]:
    """Split a tall PNG into multiple parts for readability."""
    try:
        from PIL import Image
    except ImportError:
        log.warning("Pillow not installed — skipping PNG split")
        return [png_path]

    img = Image.open(png_path)
    width, height = img.size

    if height <= max_height:
        return [png_path]

    num_parts = math.ceil(height / max_height)
    parts: list[Path] = []
    stem = png_path.stem

    for i in range(num_parts):
        y_start = i * max_height
        y_end = min((i + 1) * max_height, height)
        part_img = img.crop((0, y_start, width, y_end))

        part_path = png_path.parent / f"{stem}_part{i + 1}.png"
        part_img.save(part_path, "PNG", optimize=True)
        parts.append(part_path)
        log.info("  -> %s (%dx%d)", part_path.name, width, y_end - y_start)

    img.close()
    return parts


def create_thumbnail(png_path: Path, thumb_width: int = THUMB_WIDTH) -> Path | None:
    """Create a thumbnail version of a PNG."""
    try:
        from PIL import Image
    except ImportError:
        return None

    img = Image.open(png_path)
    width, height = img.size

    if width <= thumb_width:
        img.close()
        return None  # Already small enough

    ratio = thumb_width / width
    new_height = int(height * ratio)
    resized = img.resize((thumb_width, new_height), Image.LANCZOS)

    thumb_path = png_path.parent / f"{png_path.stem}_thumb.png"
    resized.save(thumb_path, "PNG", optimize=True)
    resized.close()
    img.close()

    log.info("  -> %s (%dx%d)", thumb_path.name, thumb_width, new_height)
    return thumb_path


def generate_index_html(output_dir: Path) -> None:
    """Generate an index.html to browse all diagrams."""
    svgs = sorted(output_dir.glob("*.svg"))
    if not svgs:
        return

    html_parts = [
        '<!DOCTYPE html>',
        '<html lang="en">',
        '<head>',
        '  <meta charset="UTF-8">',
        '  <meta name="viewport" content="width=device-width, initial-scale=1.0">',
        '  <title>Luna v7.0 — Architecture Diagrams</title>',
        '  <style>',
        '    * { box-sizing: border-box; margin: 0; padding: 0; }',
        '    body {',
        '      background: #0a0a0f;',
        '      color: #e0e0e0;',
        '      font-family: "Segoe UI", system-ui, sans-serif;',
        '      padding: 2rem;',
        '    }',
        '    h1 {',
        '      color: #E94560;',
        '      font-size: 2rem;',
        '      margin-bottom: 0.5rem;',
        '    }',
        '    .subtitle {',
        '      color: #53A8B6;',
        '      font-size: 1rem;',
        '      margin-bottom: 2rem;',
        '    }',
        '    .grid {',
        '      display: grid;',
        '      grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));',
        '      gap: 1.5rem;',
        '    }',
        '    .card {',
        '      background: #16213E;',
        '      border: 1px solid #0F3460;',
        '      border-radius: 8px;',
        '      overflow: hidden;',
        '      transition: transform 0.2s, border-color 0.2s;',
        '    }',
        '    .card:hover {',
        '      transform: translateY(-2px);',
        '      border-color: #533483;',
        '    }',
        '    .card a {',
        '      text-decoration: none;',
        '      color: inherit;',
        '    }',
        '    .card img {',
        '      width: 100%;',
        '      height: 250px;',
        '      object-fit: cover;',
        '      object-position: top left;',
        '      background: #1A1A2E;',
        '    }',
        '    .card .info {',
        '      padding: 1rem;',
        '    }',
        '    .card h2 {',
        '      color: #E94560;',
        '      font-size: 1.1rem;',
        '      margin-bottom: 0.3rem;',
        '    }',
        '    .card .meta {',
        '      color: #888;',
        '      font-size: 0.85rem;',
        '    }',
        '    .formats {',
        '      margin-top: 0.5rem;',
        '    }',
        '    .formats a {',
        '      display: inline-block;',
        '      padding: 0.2rem 0.6rem;',
        '      background: #0F3460;',
        '      color: #53A8B6;',
        '      border-radius: 4px;',
        '      font-size: 0.8rem;',
        '      margin-right: 0.3rem;',
        '      text-decoration: none;',
        '    }',
        '    .formats a:hover { background: #533483; color: #fff; }',
        '  </style>',
        '</head>',
        '<body>',
        '  <h1>Luna v7.0 — Architecture Diagrams</h1>',
        '  <p class="subtitle">Auto-generated from source code introspection</p>',
        '  <div class="grid">',
    ]

    diagram_titles = {
        "01": "Architecture Overview",
        "02": "luna_common Classes",
        "03": "Core Architecture",
        "04": "Consciousness Pipeline",
        "05": "Sensorimotor Cycle",
        "06": "State Machines",
    }

    for svg in svgs:
        stem = svg.stem
        num = stem[:2]
        title = diagram_titles.get(num, stem)
        thumb = output_dir / f"{stem}_thumb.png"
        png = output_dir / f"{stem}.png"
        img_src = thumb.name if thumb.is_file() else (png.name if png.is_file() else svg.name)

        # Count parts
        parts = sorted(output_dir.glob(f"{stem}_part*.png"))
        parts_info = f" ({len(parts)} parts)" if parts else ""

        # File size
        size_kb = svg.stat().st_size // 1024

        html_parts.append(f'    <div class="card">')
        html_parts.append(f'      <a href="{svg.name}">')
        html_parts.append(f'        <img src="{img_src}" alt="{title}" loading="lazy">')
        html_parts.append(f'      </a>')
        html_parts.append(f'      <div class="info">')
        html_parts.append(f'        <h2>{title}</h2>')
        html_parts.append(f'        <div class="meta">SVG: {size_kb} KB{parts_info}</div>')
        html_parts.append(f'        <div class="formats">')
        html_parts.append(f'          <a href="{svg.name}">SVG</a>')
        if png.is_file():
            html_parts.append(f'          <a href="{png.name}">PNG</a>')
        for part in parts:
            html_parts.append(f'          <a href="{part.name}">{part.stem.split("_")[-1]}</a>')
        html_parts.append(f'        </div>')
        html_parts.append(f'      </div>')
        html_parts.append(f'    </div>')

    html_parts.extend([
        '  </div>',
        '</body>',
        '</html>',
    ])

    index_path = output_dir / "index.html"
    index_path.write_text("\n".join(html_parts), encoding="utf-8")
    log.info("Generated index: %s", index_path)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )

    parser = argparse.ArgumentParser(description="Render Luna UML diagrams")
    parser.add_argument("--skip-download", action="store_true",
                        help="Skip PlantUML jar download")
    parser.add_argument("--svg-only", action="store_true",
                        help="Only generate SVG (skip PNG)")
    args = parser.parse_args()

    # Ensure output dir
    if not OUTPUT_DIR.is_dir():
        log.error("No output directory: %s\nRun generate.py first.", OUTPUT_DIR)
        sys.exit(1)

    pumls = sorted(OUTPUT_DIR.glob("*.puml"))
    if not pumls:
        log.error("No .puml files in %s\nRun generate.py first.", OUTPUT_DIR)
        sys.exit(1)

    # Get PlantUML
    if not args.skip_download:
        jar = ensure_plantuml()
    else:
        jar = PLANTUML_JAR
        if not jar.is_file():
            log.error("PlantUML jar not found: %s", jar)
            sys.exit(1)

    log.info("Rendering %d diagrams...\n", len(pumls))

    all_svgs: list[Path] = []
    for puml in pumls:
        svg = render_puml_to_svg(puml, jar)
        if svg:
            all_svgs.append(svg)

            if not args.svg_only:
                png = svg_to_png(svg)
                if png:
                    parts = split_png_parts(png)
                    # Create thumbnail from the full PNG (before splitting)
                    create_thumbnail(png)
        print()

    # Generate browsable index
    generate_index_html(OUTPUT_DIR)

    log.info("=" * 50)
    log.info("Done: %d SVG + PNG rendered", len(all_svgs))
    log.info("Open: %s", OUTPUT_DIR / "index.html")


if __name__ == "__main__":
    main()
