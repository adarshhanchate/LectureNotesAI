from pathlib import Path
import sys
import time

root = Path(r"c:\Users\ashan\Documents\NLP mini project")
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from backend.pdf.preview import render_sample_pdf
sample_json = root / "templates" / "sample_lecture.json"

themes = ["indigo", "emerald", "sunset", "print-friendly"]

for theme in themes:
    suffix = "print" if theme == "print-friendly" else theme
    out_pdf = root / f"sample_book_{suffix}.pdf"
    print(f"\n>>> Rendering theme: {theme} -> {out_pdf.name}")
    t0 = time.time()
    render_sample_pdf(sample_json, out_pdf, theme=theme)
    print(f"    Completed in {time.time() - t0:.2f}s (Size: {out_pdf.stat().st_size / 1024:.1f} KB)")

print("\n[+] ALL 4 THEMES RENDERED SUCCESSFULLY!")
