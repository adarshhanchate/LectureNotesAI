"""Pre-rendered Math to SVG Renderer using matplotlib.mathtext.

Converts LaTeX expressions ($...$ and $$...$$) into crisp vector SVG elements
using pure Python (no external node or KaTeX installs required).

Features:
1. Multi-line math: splits equations containing \\ into separate lines, rendering
   each line independently.
2. Unescapes \\%, \\$, and \\_ to %, $, and _. Never emits literal \\ or \\% in output.
3. Fallback text: uses <sub> and <sup> tags exclusively (no Unicode subscript letters).
4. Plain labels & numbers: cleans symbols (P_1 -> P<sub>1</sub>, m_dot -> ṁ, Q_dot_ic -> Q̇<sub>ic</sub>, gamma -> γ)
   and ensures numbers with commas (14,000) render without extra spacing.
5. Simple symbols & quantities with units (P, T_1, 35.0 kJ, 15 °C) render as styled text
   in the body font with zero stray space before punctuation.
6. Display formulas maintain a consistent font scale across the entire book.
"""

from __future__ import annotations
import html
import io
import logging
import re
from typing import Dict, Tuple, List, Optional

logger = logging.getLogger("lecturenotes.math_renderer")

_math_svg_cache: Dict[Tuple[str, bool, int], str] = {}

# Common Greek and Math symbol mappings for clean Unicode fallback
_UNICODE_MAP = {
    r"\oiint": "∯",
    r"\oint": "∮",
    r"\int": "∫",
    r"\sum": "∑",
    r"\prod": "∏",
    r"\partial": "∂",
    r"\nabla": "∇",
    r"\Delta": "Δ",
    r"\Omega": "Ω",
    r"\alpha": "α",
    r"\beta": "β",
    r"\gamma": "γ",
    r"\delta": "δ",
    r"\epsilon": "ε",
    r"\eta": "η",
    r"\theta": "θ",
    r"\lambda": "λ",
    r"\mu": "μ",
    r"\pi": "π",
    r"\rho": "ρ",
    r"\sigma": "σ",
    r"\tau": "τ",
    r"\phi": "φ",
    r"\omega": "ω",
    r"\cdot": "·",
    r"\times": "×",
    r"\approx": "≈",
    r"\neq": "≠",
    r"\leq": "≤",
    r"\le": "≤",
    r"\geq": "≥",
    r"\ge": "≥",
    r"\pm": "±",
    r"\mp": "∓",
    r"\infty": "∞",
    r"\to": "→",
    r"\rightarrow": "→",
    r"\Leftarrow": "⇐",
    r"\Rightarrow": "⇒",
    r"\implies": "⇒",
    r"\iff": "⇔",
    r"\Leftrightarrow": "⇔",
    r"\quad": "  ",
    r"\qquad": "    ",
    r"\circ": "°",
}

# Greek word replacements for plain labels
_GREEK_WORDS = {
    "gamma": "γ",
    "alpha": "α",
    "beta": "β",
    "Delta": "Δ",
    "delta": "δ",
    "epsilon": "ε",
    "eta": "η",
    "theta": "θ",
    "lambda": "λ",
    "mu": "μ",
    "rho": "ρ",
    "sigma": "σ",
    "tau": "τ",
    "phi": "φ",
    "omega": "ω",
    "Omega": "Ω",
}


def clean_symbol_label(text: str) -> str:
    """Clean plain labels (Given / Find / table cells / simple variables).
    
    Turns names like P_1, T_2, m_dot, Q_dot_ic, gamma into proper styled symbols
    with HTML subscripts, superscripts, dot accents, and Greek letters.
    """
    if not text:
        return ""

    s = text.strip()
    
    # 1. Unescape escaped characters
    s = s.replace(r"\%", "%").replace(r"\$", "$").replace(r"\_", "_")

    # 2. Dot-accented variables (m_dot, Q_dot_ic, W_dot, V_dot)
    s = re.sub(r"\b([A-Za-z])_dot_([a-zA-Z0-9,\-]+)\b", r"\1̇<sub>\2</sub>", s)
    s = re.sub(r"\b([A-Za-z])_dot\b", r"\1̇", s)
    s = re.sub(r"\\dot\{([A-Za-z])\}_([a-zA-Z0-9,\-]+)", r"\1̇<sub>\2</sub>", s)
    s = re.sub(r"\\dot\{([A-Za-z])\}", r"\1̇", s)

    # Specific common dot variables
    s = s.replace("ṁ", "ṁ")  # standard precomposed lower m with dot
    s = s.replace("ẇ", "ẇ")
    s = s.replace("Ẇ", "Ẇ")

    # 2.5 Delta prefixes: Delta_U -> ΔU, Delta_S -> ΔS, Delta_H -> ΔH, Delta_T -> ΔT
    s = re.sub(r"\b(?:\\?Delta|Δ)_([A-Z])(?=[_ \t\n\r\(\)\[\]{{}},;:]|$)", r"Δ\1", s)

    # 3. Greek words and LaTeX commands (match even when followed by underscore or boundary)
    for word, greek in _GREEK_WORDS.items():
        s = re.sub(rf"\\?{word}(?=[_ \t\n\r\(\)\[\]{{}},;:]|$)", greek, s)

    # 4. Subscripts: P_1 -> P<sub>1</sub>, T_H -> T<sub>H</sub>, S_{universe} -> S<sub>universe</sub>
    s = re.sub(r"([A-Za-z0-9α-ωΑ-Ω̇̄]+)_\{([^}]+)\}", r"\1<sub>\2</sub>", s)
    s = re.sub(r"([A-Za-z0-9α-ωΑ-Ω̇̄]+)_([a-zA-Z0-9,\-]+)", r"\1<sub>\2</sub>", s)

    # 5. Superscripts: T^2 -> T<sup>2</sup>, P^{n} -> P<sup>n</sup>
    s = re.sub(r"([A-Za-z0-9α-ωΑ-Ω̇̄]+)\^\{([^}]+)\}", r"\1<sup>\2</sup>", s)
    s = re.sub(r"([A-Za-z0-9α-ωΑ-Ω̇̄]+)\^([a-zA-Z0-9,\-]+)", r"\1<sup>\2</sup>", s)

    # 6. Degrees circle: ^\circ C -> °C
    s = re.sub(r"\^\{?\\circ\}?\s*C", "°C", s)

    # 7. Strip leftover text wrappers
    s = re.sub(r"\\(?:text|mathrm|mathbf)\{([^}]+)\}", r"\1", s)
    s = s.replace("{", "").replace("}", "")
    
    return s


def normalize_latex_for_mathtext(latex_str: str) -> str:
    """Normalize typical LLM LaTeX formulas to matplotlib.mathtext-compatible syntax."""
    s = latex_str.strip().strip("$").strip()

    # 1. Unescape escaped characters
    s = s.replace(r"\%", "%").replace(r"\$", "$").replace(r"\_", "_")

    # 2. Number thousands separator: 14,000 -> 14{,}000 (prevents trailing punctuation space)
    s = re.sub(r"(\d),(\d)", r"\1{,}\2", s)

    # 3. Replace \dfrac and \tfrac with \frac
    s = re.sub(r"\\(?:dfrac|tfrac)\b", r"\\frac", s)

    # 4. Replace \text{...} and \textbf{...} with \mathrm{...}
    s = re.sub(r"\\(?:text|textbf)\s*\{([^}]+)\}", r"\\mathrm{\1}", s)

    # 5. Strip \left and \right delimiters (mathtext handles parentheses naturally)
    s = re.sub(r"\\left\b", "", s)
    s = re.sub(r"\\right\b", "", s)

    # 6. Drop spacing commands: \, \; \! \quad \qquad and literal escaped spaces '\ '
    s = re.sub(r"\\[,;! ]", " ", s)
    s = re.sub(r"\\(?:quad|qquad)\b", " ", s)

    # 7. Map shorthands and logical arrows
    s = re.sub(r"\\implies\b", r"\\Rightarrow", s)
    s = re.sub(r"\\iff\b", r"\\Leftrightarrow", s)
    s = re.sub(r"\\le\b", r"\\leq", s)
    s = re.sub(r"\\ge\b", r"\\geq", s)

    # 8. Normalize whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


def latex_to_plain_unicode(latex_str: str) -> str:
    """Convert LaTeX math syntax to clean plain Unicode/HTML text when SVG rendering fails.
    
    Renders subscripts and superscripts as <sub> and <sup> tags exclusively
    (e.g. S_{universe} -> S<sub>universe</sub>, W_{total,2-stage} -> W<sub>total,2-stage</sub>).
    Never produces Unicode subscript letters or literal \\ or \\%.
    """
    text = latex_str.strip()

    # 1. Unescape escaped characters
    text = text.replace(r"\%", "%").replace(r"\$", "$").replace(r"\_", "_")

    # 2. Split multi-line commands if any
    text = re.sub(r"\\\\|\\newline", " ; ", text)

    # 3. Strip text wrappers: \text{...} -> ...
    text = re.sub(r"\\(?:text|mathrm|mathbf|textbf)\s*\{([^}]+)\}", r"\1", text)

    # 4. Convert inner subscripts and superscripts first so outer braces don't get truncated
    text = re.sub(r"_\{([^}]+)\}", r"<sub>\1</sub>", text)
    text = re.sub(r"\^\{([^}]+)\}", r"<sup>\1</sup>", text)
    text = re.sub(r"_([0-9a-zA-Z\+\-]+)", r"<sub>\1</sub>", text)
    text = re.sub(r"\^([0-9a-zA-Z\+\-]+)", r"<sup>\1</sup>", text)

    # 5. Handle special cancel commands: \xcancel{x} -> [canceled: x]
    text = re.sub(r"\\xcancel\s*\{([^}]+)\}", r"[canceled: \1]", text)

    # 6. Replace fractions: \frac{num}{den} -> (num / den)
    text = re.sub(r"\\(?:frac|dfrac|tfrac)\s*\{([^}]+)\}\s*\{([^}]+)\}", r"(\1 / \2)", text)

    # 7. Replace square roots: \sqrt{arg} -> √(arg)
    text = re.sub(r"\\sqrt\s*\{([^}]+)\}", r"√(\1)", text)

    # 8. Replace vectors: \vec{v} -> v̄
    text = re.sub(r"\\vec\s*\{([^}]+)\}", r"\1̄", text)

    # 9. Map math symbols and Greek letters
    for cmd, sym in _UNICODE_MAP.items():
        text = text.replace(cmd, sym)

    # 11. Clean residual backslashes and leftover structural braces
    text = re.sub(r"\\[a-zA-Z]+", "", text)
    text = text.replace("{", "").replace("}", "")
    text = re.sub(r"\s+", " ", text).strip()

    return text


def is_complex_formula(expr: str) -> bool:
    """Determine if a formula requires full mathtext SVG rendering.
    
    Returns True for real formulas (fractions, roots, integrals, sums, multi-level scripts).
    Returns False for simple symbols, variables, or quantities with units (P, T_1, 35.0 kJ, 15 °C).
    """
    s = expr.strip().strip("$").strip()
    
    # Must use SVG for real structural formula elements
    svg_triggers = [
        r"\\(?:frac|dfrac|tfrac)\b",
        r"\\sqrt\b",
        r"\\(?:int|oint|oiint|sum|prod|partial|nabla)\b",
        r"\\(?:matrix|pmatrix|bmatrix|begin|end)\b",
        r"\\[a-zA-Z]+.*\\(?:frac|sqrt)",
    ]
    for pattern in svg_triggers:
        if re.search(pattern, s):
            return True

    # Multi-level scripts or complex nested exponents/fractions
    if re.search(r"\^\{[^}]*[_^]", s) or re.search(r"_\{[^}]*[_^]", s):
        return True

    # Long equations with multiple mathematical operators (+, -, =, \times, \cdot)
    ops_count = len(re.findall(r"[=+\-·×*/]", s)) + len(re.findall(r"\\(?:cdot|times|pm|mp)\b", s))
    if ops_count >= 2 and any(k in s for k in ("=", r"\leq", r"\geq", "<", ">")):
        return True

    return False


def _render_single_latex_to_svg(normalized: str, is_block: bool, fontsize: int = 12) -> str:
    """Worker to render a single normalized line of LaTeX to SVG via mathtext."""
    from matplotlib import mathtext
    from matplotlib.font_manager import FontProperties
    
    math_expr = f"${normalized}$"
    buf = io.BytesIO()
    prop = FontProperties(size=14 if is_block else 12)
    
    mathtext.math_to_image(
        math_expr,
        buf,
        prop=prop,
        dpi=120 if is_block else 100,
        format="svg",
    )
    svg_content = buf.getvalue().decode("utf-8")
    
    svg_start = svg_content.find("<svg")
    if svg_start != -1:
        svg_cleaned = svg_content[svg_start:]
        cls = "math-svg-block" if is_block else "math-svg-inline"
        svg_cleaned = svg_cleaned.replace("<svg ", f'<svg class="{cls}" role="img" ')
        return svg_cleaned
    raise ValueError("No <svg> tag generated")


def render_latex_to_svg(latex_str: str, is_block: bool = False, fontsize: int = 12) -> str:
    """Convert a LaTeX expression to SVG string (or styled text if simple).
    
    Handles:
    - Multi-line formulas with \\: splits and renders each line independently.
    - Simple symbols & quantities: renders directly as styled body text.
    - Full formulas: renders as crisp vector SVG.
    - Unsupported math: falls back to clean <sub>/<sup> HTML text.
    """
    clean_latex = latex_str.strip().strip("$").strip()
    if not clean_latex:
        return ""

    # Unescape escaped characters first
    clean_latex = clean_latex.replace(r"\%", "%").replace(r"\$", "$").replace(r"\_", "_")

    cache_key = (clean_latex, is_block, fontsize)
    if cache_key in _math_svg_cache:
        return _math_svg_cache[cache_key]

    # 1. Multi-line math check: split equations containing \\ into separate lines
    if r"\\" in clean_latex or "\\\\" in clean_latex or r"\newline" in clean_latex:
        raw_lines = [l.strip() for l in re.split(r"\\\\|\\newline", clean_latex) if l.strip()]
        if len(raw_lines) > 1:
            rendered_rows: List[str] = []
            for line in raw_lines:
                row_svg = render_latex_to_svg(line, is_block=True, fontsize=fontsize)
                rendered_rows.append(f'<div class="math-multiline-row">{row_svg}</div>')
            multiline_html = f'<div class="math-multiline-container">{"".join(rendered_rows)}</div>'
            _math_svg_cache[cache_key] = multiline_html
            return multiline_html

    # 2. Simple symbol / quantity check for inline math
    if not is_block and not is_complex_formula(clean_latex):
        styled = clean_symbol_label(clean_latex)
        out = f'<span class="math-styled-text">{styled}</span>'
        _math_svg_cache[cache_key] = out
        return out

    # 3. Full SVG rendering via mathtext
    normalized = normalize_latex_for_mathtext(clean_latex)

    try:
        svg_out = _render_single_latex_to_svg(normalized, is_block=is_block, fontsize=fontsize)
        _math_svg_cache[cache_key] = svg_out
        return svg_out

    except Exception as e:
        logger.info(f"Mathtext unsupported LaTeX '{clean_latex}' (normalized: '{normalized}'): {e}. Falling back to clean HTML.")
        # Graceful fallback to clean Unicode/HTML with sub/sup tags
        unicode_html = latex_to_plain_unicode(clean_latex)
        cls = "math-unicode-block" if is_block else "math-unicode-inline"
        fallback = f'<span class="{cls}" title="Fallback Unicode math">{unicode_html}</span>'
        _math_svg_cache[cache_key] = fallback
        return fallback


def render_all_math_in_html(text: str) -> str:
    """Replace all block ($$...$$) and inline ($...$) LaTeX math in text with pre-rendered SVGs or styled text."""
    if not text:
        return ""

    # Replace block math: $$...$$
    def _replace_block(match):
        latex = match.group(1)
        return f'<div class="math-block-container">{render_latex_to_svg(latex, is_block=True)}</div>'

    processed = re.sub(r"\$\$(.+?)\$\$", _replace_block, text, flags=re.DOTALL)

    # Replace inline math: $...$
    def _replace_inline(match):
        latex = match.group(1)
        # Ignore currency amounts like $50 or $1,000
        if re.match(r"^\d+(?:,\d+)*(?:\.\d+)?$", latex):
            return match.group(0)
        return render_latex_to_svg(latex, is_block=False)

    processed = re.sub(r"\$([^\$\n]+?)\$", _replace_inline, processed)
    return processed
