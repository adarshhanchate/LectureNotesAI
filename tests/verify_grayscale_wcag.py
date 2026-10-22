from pathlib import Path
import fitz
from PIL import Image
import numpy as np

ARTIFACT_DIR = Path(r"C:\Users\ashan\.gemini\antigravity-ide\brain\0957641c-3107-49a3-a864-67d3c6aeeee4")
SCREENSHOT_DIR = ARTIFACT_DIR / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

# 1. Render grayscale screenshots for Numerical card (Page 8) and Questions (Page 12) from sample_book_print.pdf
print_pdf_path = Path("sample_book_print.pdf")
doc = fitz.open(str(print_pdf_path))
matrix = fitz.Matrix(2.0, 2.0)

# Render Page 8 (Numerical Problem 3.2)
pix_num = doc[7].get_pixmap(matrix=matrix)
num_path = SCREENSHOT_DIR / "print_numerical_card_p8.png"
pix_num.save(str(num_path))
print(f"Saved: {num_path.name}")

# Render Page 12 (Questions)
pix_q = doc[11].get_pixmap(matrix=matrix)
q_path = SCREENSHOT_DIR / "print_questions_p12.png"
pix_q.save(str(q_path))
print(f"Saved: {q_path.name}")

# 2. Precise WCAG 2.1 Relative Luminance & Contrast Ratio calculation
def srgb_to_rel_lum(r: int, g: int, b: int) -> float:
    def channel_lum(val):
        s = val / 255.0
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4
    return 0.2126 * channel_lum(r) + 0.7152 * channel_lum(g) + 0.0722 * channel_lum(b)

def calc_wcag_contrast(l1: float, l2: float) -> float:
    light = max(l1, l2)
    dark = min(l1, l2)
    return (light + 0.05) / (dark + 0.05)

bg_lum = srgb_to_rel_lum(255, 255, 255) # #ffffff background
black_lum = srgb_to_rel_lum(0, 0, 0)     # #000000 pure black text
body_lum = srgb_to_rel_lum(34, 34, 34)   # #222222 body text
muted_lum = srgb_to_rel_lum(102, 102, 102) # #666666 border/muted

cr_pure_black = calc_wcag_contrast(bg_lum, black_lum)
cr_body = calc_wcag_contrast(bg_lum, body_lum)
cr_muted = calc_wcag_contrast(bg_lum, muted_lum)

print("\n=== WCAG 2.1 RELATIVE LUMINANCE & CONTRAST RATIOS ===")
print(f"White Page Background (#ffffff) Relative Luminance: {bg_lum:.4f}")
print(f"Pure Black Text (#000000) Relative Luminance:        {black_lum:.4f} -> Contrast Ratio: {cr_pure_black:.2f}:1 (Theoretical Max: 21.00:1)")
print(f"Body Text (#222222) Relative Luminance:              {body_lum:.4f} -> Contrast Ratio: {cr_body:.2f}:1 (WCAG AAA requires >= 7.0:1)")
print(f"Muted / Border (#666666) Relative Luminance:         {muted_lum:.4f} -> Contrast Ratio: {cr_muted:.2f}:1 (WCAG AA requires >= 4.5:1)")

# Empirical verification on print_concept_p3.png
img = Image.open(SCREENSHOT_DIR / "print_concept_p3.png").convert("RGB")
arr = np.array(img)
# Sample dark text pixels (lowest 5% luminance) and white background (top 95%)
ch_lum = np.vectorize(lambda v: v / 255.0 / 12.92 if v / 255.0 <= 0.04045 else ((v / 255.0 + 0.055) / 1.055) ** 2.4)
pix_lum = 0.2126 * ch_lum(arr[:, :, 0]) + 0.7152 * ch_lum(arr[:, :, 1]) + 0.0722 * ch_lum(arr[:, :, 2])

dark_emp = np.percentile(pix_lum, 2)
light_emp = np.percentile(pix_lum, 98)
cr_emp = calc_wcag_contrast(light_emp, dark_emp)
print(f"\nEmpirical Rendered Pixel Contrast Ratio (print_concept_p3.png): {cr_emp:.2f}:1")
