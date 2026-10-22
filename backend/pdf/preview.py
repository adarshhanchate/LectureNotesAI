"""Standalone PDF Preview Tool.

Renders sample_book.pdf directly from templates/sample_lecture.json
without running the audio or LLM pipeline.

Usage:
    python -m backend.pdf.preview [--theme indigo|emerald|sunset|print-friendly] [--out sample_book.pdf]
"""

import argparse
import json
import logging
import subprocess
import sys
import time
from pathlib import Path

# Ensure project root is in sys.path regardless of working directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from jinja2 import Environment, FileSystemLoader

from backend.config import get_settings
from backend.pdf.math_renderer import render_all_math_in_html, render_latex_to_svg, clean_symbol_label

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("lecturenotes.pdf.preview")


def render_sample_pdf(
    sample_json_path: Path,
    output_pdf_path: Path,
    theme: str = "indigo",
) -> Path:
    """Render a sample lecture JSON file into a high-quality study book PDF."""
    settings = get_settings()
    project_root = settings.PROJECT_ROOT
    templates_dir = settings.TEMPLATES_DIR
    css_file = templates_dir / "styles" / "book.css"

    if not sample_json_path.exists():
        raise FileNotFoundError(f"Sample lecture data not found at: {sample_json_path}")
    if not css_file.exists():
        raise FileNotFoundError(f"Book CSS stylesheet not found at: {css_file}")

    with open(sample_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if theme:
        data["theme"] = theme

    data["css_path"] = css_file.as_uri()

    # Setup Jinja environment with custom math filters
    env = Environment(loader=FileSystemLoader(str(templates_dir)))
    env.filters["render_math"] = render_all_math_in_html
    env.filters["clean_label"] = clean_symbol_label
    env.filters["render_latex_svg"] = lambda s, block=False: render_latex_to_svg(s, is_block=block)

    logger.info("Compiling Jinja2 template (templates/book.html.j2)...")
    template = env.get_template("book.html.j2")
    html_content = template.render(**data)

    # Save rendered HTML
    html_debug = output_pdf_path.with_suffix(".html")
    with open(html_debug, "w", encoding="utf-8") as f:
        f.write(html_content)

    logger.info(f"Rendering PDF with WeasyPrint (Theme: {data.get('theme', 'indigo')})...")
    t0 = time.monotonic()

    standalone_exe = project_root / "bin" / "weasyprint" / "onedir" / "weasyprint" / "weasyprint.exe"
    if standalone_exe.exists():
        res = subprocess.run(
            [str(standalone_exe), str(html_debug), str(output_pdf_path)],
            capture_output=True,
            text=True,
        )
        if res.returncode != 0:
            logger.warning(f"Standalone WeasyPrint stderr: {res.stderr}")
            raise RuntimeError(f"WeasyPrint failed: {res.stderr}")
    else:
        from weasyprint import HTML
        HTML(filename=str(html_debug)).write_pdf(target=str(output_pdf_path))

    duration = time.monotonic() - t0
    pdf_size_kb = output_pdf_path.stat().st_size / 1024
    logger.info(f"Successfully generated PDF: {output_pdf_path.name} ({pdf_size_kb:.1f} KB in {duration:.2f}s)")
    return output_pdf_path


def main():
    parser = argparse.ArgumentParser(description="Render sample lecture study book PDF directly.")
    parser.add_argument(
        "--theme",
        choices=["indigo", "emerald", "sunset", "print-friendly"],
        default="indigo",
        help="Color theme palette (default: indigo)",
    )
    parser.add_argument(
        "--input",
        type=str,
        default="templates/sample_lecture.json",
        help="Path to sample JSON file",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="sample_book.pdf",
        help="Output PDF file path",
    )

    args = parser.parse_args()
    project_root = get_settings().PROJECT_ROOT
    input_path = project_root / args.input
    output_path = project_root / args.out

    print("=" * 60)
    print("   LectureNotes AI -- PDF Design System Preview")
    print("=" * 60)
    print(f"Input:   {input_path}")
    print(f"Output:  {output_path}")
    print(f"Theme:   {args.theme}")
    print("-" * 60)

    try:
        render_sample_pdf(input_path, output_path, theme=args.theme)
        print("\n[+] SUCCESS: Sample study book PDF rendered!")
        print(f"    File: {output_path.resolve()}")
        print("=" * 60)
        return 0
    except Exception as e:
        print(f"\n[-] ERROR: Failed to render PDF: {e}")
        logger.exception("PDF generation error")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
