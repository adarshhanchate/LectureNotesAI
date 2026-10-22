"""PDF Generation module — compiles study books using Jinja2 and WeasyPrint."""

from __future__ import annotations
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Any

from jinja2 import Environment, FileSystemLoader

from backend.config import get_settings
from backend.pdf.math_renderer import render_all_math_in_html, render_latex_to_svg, clean_symbol_label

logger = logging.getLogger("lecturenotes.pdf_builder")


def build_pdf(
    book_data: Dict[str, Any],
    output_pdf_path: Path,
    theme: str = "indigo",
) -> Path:
    """Compile structured lecture notes and questions into a PDF study book.

    Uses templates/book.html.j2, templates/styles/book.css, and pre-rendered KaTeX math.
    """
    settings = get_settings()
    project_root = settings.PROJECT_ROOT
    templates_dir = settings.TEMPLATES_DIR
    css_file = templates_dir / "styles" / "book.css"

    if not css_file.exists():
        raise FileNotFoundError(f"Book CSS stylesheet not found at: {css_file}")

    data = dict(book_data)
    data["theme"] = theme or data.get("theme", "indigo")
    data["css_path"] = css_file.as_uri()

    # Setup Jinja2 environment with custom math filters
    env = Environment(loader=FileSystemLoader(str(templates_dir)))
    env.filters["render_math"] = render_all_math_in_html
    env.filters["clean_label"] = clean_symbol_label
    env.filters["render_latex_svg"] = lambda s, block=False: render_latex_to_svg(s, is_block=block)

    logger.info("Rendering Jinja2 study book template...")
    template = env.get_template("book.html.j2")
    html_content = template.render(**data)

    # Save HTML artifact alongside PDF
    html_debug_path = output_pdf_path.with_suffix(".html")
    with open(html_debug_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    logger.info(f"Generating PDF with WeasyPrint: {output_pdf_path.name}...")
    t0 = time.monotonic()

    standalone_exe = project_root / "bin" / "weasyprint" / "onedir" / "weasyprint" / "weasyprint.exe"
    if standalone_exe.exists():
        res = subprocess.run(
            [str(standalone_exe), str(html_debug_path), str(output_pdf_path)],
            capture_output=True,
            text=True,
        )
        if res.returncode != 0:
            logger.warning(f"Standalone WeasyPrint warning/error: {res.stderr[:300]}")
    else:
        from weasyprint import HTML
        HTML(filename=str(html_debug_path)).write_pdf(target=str(output_pdf_path))

    elapsed = time.monotonic() - t0
    pdf_size_kb = output_pdf_path.stat().st_size / 1024
    logger.info(f"PDF successfully built: {pdf_size_kb:.1f} KB in {elapsed:.2f}s")
    return output_pdf_path
