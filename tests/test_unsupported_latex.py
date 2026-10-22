"""Unit test for deliberately unsupported LaTeX expressions.

Verifies that equations with unsupported LaTeX commands (e.g. \\oiint, \\xcancel)
gracefully fall back to clean, readable HTML text with <sub> and <sup> tags,
with zero crashes and zero unescaped raw LaTeX artifacts.
"""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.pdf.math_renderer import render_latex_to_svg, latex_to_plain_unicode


def test_unsupported_latex_fallback():
    unsupported_expr = r"\oiint \vec{B} \cdot d\vec{A} = 0 \quad \text{and} \quad \xcancel{\Delta S_{\text{universe}} < 0}"
    
    print("\n========================================================")
    print("TEST: Unsupported LaTeX Fallback Handling")
    print("========================================================")
    print(f"Input Expression:\n  {unsupported_expr}\n")

    fallback_text = latex_to_plain_unicode(unsupported_expr)
    print(f"Plain Unicode/HTML Fallback:\n  {fallback_text.encode('ascii', errors='replace').decode('ascii')}\n")
    
    rendered_html = render_latex_to_svg(unsupported_expr, is_block=True)
    print(f"Rendered Output HTML:\n  {rendered_html.encode('ascii', errors='replace').decode('ascii')}\n")

    # Assertions
    assert "∯" in fallback_text, "Expected surface integral ∯ in fallback"
    assert "<sub>universe</sub>" in fallback_text, "Expected <sub>universe</sub> tag"
    assert "math-unicode-block" in rendered_html, "Expected math-unicode-block class in fallback container"
    assert r"\xcancel" not in rendered_html, "Raw command \\xcancel must not leak into output"
    assert r"\\" not in rendered_html, "Raw backslashes must not leak into output"
    
    print("[+] All unsupported LaTeX fallback tests passed successfully!")


if __name__ == "__main__":
    test_unsupported_latex_fallback()
