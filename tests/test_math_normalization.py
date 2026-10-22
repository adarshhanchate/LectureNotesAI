from matplotlib import mathtext
import io
import re

def normalize_latex_for_mathtext(latex_str: str) -> str:
    s = latex_str.strip().strip("$").strip()
    # 1. Replace \dfrac and \tfrac with \frac
    s = re.sub(r"\\(?:dfrac|tfrac)\b", r"\\frac", s)
    # 2. Replace \text{...} with \mathrm{...}
    s = re.sub(r"\\text\s*\{([^}]+)\}", r"\\mathrm{\1}", s)
    # 3. Strip \left and \right
    s = re.sub(r"\\left\b", "", s)
    s = re.sub(r"\\right\b", "", s)
    # 4. Drop spacing commands: \, \; \! \quad \qquad \ 
    s = re.sub(r"\\[,;! ]", " ", s)
    s = re.sub(r"\\(?:quad|qquad)\b", " ", s)
    # 5. Common conversions: \implies -> \Rightarrow, \le -> \leq, \ge -> \geq
    s = re.sub(r"\\implies\b", r"\\Rightarrow", s)
    s = re.sub(r"\\le\b", r"\\leq", s)
    s = re.sub(r"\\ge\b", r"\\geq", s)
    # 6. Normalize whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s

formulas = [
    r"\eta_{\text{th}} = 1 - \frac{T_C}{T_H}",
    r"W = \int_{V_1}^{V_2} P \, dV = \frac{P_2 V_2 - P_1 V_1}{1 - n}",
    r"\Delta U = Q - W",
    r"P V = n R T",
    r"v_{\mathrm{rms}} = \sqrt{\dfrac{3 k_B T}{m}}",
    r"T_2 = T_1 \left( \frac{P_2}{P_1} \right)^{\frac{\gamma - 1}{\gamma}}",
    r"\dot{W}_{\text{comp}} = \dot{m} C_p (T_{\text{exit}} - T_{\text{in}})",
    r"s_2 - s_1 = C_p \ln \left( \frac{T_2}{T_1} \right) - R \ln \left( \frac{P_2}{P_1} \right)",
    r"h = u + P v",
    r"\oint \frac{\delta Q}{T} \le 0",
    r"\Delta S_{\text{univ}} = \Delta S_{\text{sys}} + \Delta S_{\text{surr}} \ge 0",
    r"\dot{Q}_H = \dfrac{\dot{W}_{\text{net}}}{\eta_{\text{th}}}",
    r"P_i = \sqrt{P_1 \cdot P_2}",
    r"\oiint \vec{B} \cdot d\vec{A} = 0",
    r"\xcancel{\Delta S < 0}",
]

svg_count = 0
fallback_count = 0

print("=== TESTING 15 TYPICAL LLM FORMULAS WITH NORMALIZATION ===")
for idx, f in enumerate(formulas, 1):
    norm = normalize_latex_for_mathtext(f)
    buf = io.BytesIO()
    try:
        mathtext.math_to_image(f"${norm}$", buf, format="svg")
        print(f"{idx:2d}. [SVG SUCCESS] {f}")
        svg_count += 1
    except Exception as e:
        print(f"{idx:2d}. [FALLBACK]    {f} -> {e}")
        fallback_count += 1

print(f"\nRESULT: {svg_count}/15 Rendered as crisp SVG ({svg_count/15*100:.1f}%)")
print(f"        {fallback_count}/15 Rendered via Unicode Fallback ({fallback_count/15*100:.1f}%)")
