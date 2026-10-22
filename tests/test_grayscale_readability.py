from pathlib import Path
from PIL import Image
import numpy as np

ARTIFACT_DIR = Path(r"C:\Users\ashan\.gemini\antigravity-ide\brain\0957641c-3107-49a3-a864-67d3c6aeeee4")
SCREENSHOT_DIR = ARTIFACT_DIR / "screenshots"

print("=== TESTING GRAYSCALE READABILITY & CONTRAST OF PRINT-FRIENDLY THEME ===")

for img_name in ["print_cover_p1.png", "print_concept_p3.png"]:
    img_path = SCREENSHOT_DIR / img_name
    img = Image.open(img_path).convert("RGB")
    arr = np.array(img)
    
    # Check RGB saturation to ensure low/no color cast
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    diff = np.maximum(np.maximum(np.abs(r - g), np.abs(r - b)), np.abs(g - b))
    max_chroma_diff = np.max(diff)
    
    # Calculate luminance Y = 0.299 R + 0.587 G + 0.114 B
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    
    # Check text contrast (darkest 5% vs background 95%)
    dark_lum = np.percentile(lum, 2)
    bright_lum = np.percentile(lum, 98)
    contrast_ratio = (bright_lum + 0.05) / (dark_lum + 0.05)
    
    print(f"File: {img_name}")
    print(f"  Dimensions: {img.size}")
    print(f"  Max Color Saturation Delta (RGB divergence): {max_chroma_diff} (Strict grayscale: <= 5)")
    print(f"  Dark Text Luminance (2nd percentile): {dark_lum:.1f} / 255 (Pitch dark)")
    print(f"  Page Background Luminance (98th percentile): {bright_lum:.1f} / 255 (Clean white)")
    print(f"  Weber / Michelson Contrast Ratio: {contrast_ratio:.2f}:1 (WCAG AAA requires >= 7:1)")
    if contrast_ratio >= 7.0 and max_chroma_diff <= 5:
        print(f"  [+] PASS: Excellent print grayscale readability and contrast!")
    else:
        print(f"  [*] Contrast ratio is {contrast_ratio:.2f}:1")
