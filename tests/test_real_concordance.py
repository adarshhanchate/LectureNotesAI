"""Rigorous Concordance Audit for All Themes.

Parses every TOC row on Page 2 (title + printed page number via target-counter),
locates the actual physical page where each section heading appears in the PDF body,
prints a comparison table, and exits with code 1 on any mismatch.
"""

import sys
from pathlib import Path
import fitz

THEMES = ["indigo", "emerald", "sunset", "print"]

# Mapping of section prefixes to distinctive heading search terms
SECTION_KEYWORDS = {
    "1.1": ["1.1", "thermodynamic systems"],
    "1.2": ["1.2", "path independence"],
    "1.3": ["1.3", "first law"],
    "1.4": ["1.4", "quasi-static"],
    "1.5": ["1.5", "second law"],
    "1.6": ["1.6", "clausius"],
    "2.1": ["2.1", "reversible isothermal"],
    "2.2": ["2.2", "adiabatic free"],
    "3.1": ["3.1", "carnot heat engine"],
    "3.2": ["3.2", "two-stage gas compression"],
    "3.3": ["3.3", "polytropic expansion"],
    "4.1": ["4.1", "chapter overview"],
    "4.2": ["4.2", "formula"],
    "5.1": ["5.1", "easy level"],
    "5.2": ["5.2", "moderate level"],
    "5.3": ["5.3", "hard level"],
    "5.4": ["5.4", "comprehensive solutions"],
}


def audit_theme(pdf_path: Path) -> int:
    if not pdf_path.exists():
        print(f"[-] ERROR: PDF file not found: {pdf_path}")
        return 1

    doc = fitz.open(str(pdf_path))
    theme_name = pdf_path.stem.replace("sample_book_", "")
    print(f"\n{'='*75}")
    print(f"CONCORDANCE AUDIT: {theme_name.upper()} THEME ({len(doc)} pages)")
    print(f"{'='*75}")

    p2 = doc[1]  # Page 2 is Table of Contents
    blocks = p2.get_text("blocks")

    # Extract printed page numbers (right aligned, x > 500) and entry titles (left aligned, 50 < x < 60)
    num_blocks = sorted(
        [b for b in blocks if b[0] > 500 and 110 < b[1] < 450],
        key=lambda b: b[1]
    )
    title_blocks = sorted(
        [b for b in blocks if 50 < b[0] < 60 and 110 < b[1] < 450],
        key=lambda b: b[1]
    )

    if len(num_blocks) != len(title_blocks):
        print(f"[-] ERROR: Number of title rows ({len(title_blocks)}) does not match page numbers ({len(num_blocks)})")
        return 1

    print(f"{'Item':<5} | {'Section Title':<40} | {'Printed':<7} | {'Actual':<7} | {'Status'}")
    print(f"{'-'*5}-+-{'-'*40}-+-{'-'*7}-+-{'-'*7}-+-{'-'*8}")

    mismatches = 0

    for tb, nb in zip(title_blocks, num_blocks):
        title = tb[4].strip().replace("\n", " ")
        sec_num = title[:3]
        printed_page = int(nb[4].strip())

        # Locate physical page where heading appears in the document body (p3 to end)
        actual_page = None
        keywords = [kw.lower() for kw in SECTION_KEYWORDS.get(sec_num, [title[:15].lower()])]

        for p_idx in range(2, len(doc)):
            page_text = doc[p_idx].get_text().lower()
            if all(kw in page_text for kw in keywords):
                actual_page = p_idx + 1
                break

        status = "MATCH" if printed_page == actual_page else "MISMATCH"
        if status == "MISMATCH":
            mismatches += 1

        flag = "[OK]  " if status == "MATCH" else "[FAIL]"
        print(f"{sec_num:<5} | {title[:40]:<40} | {printed_page:^7} | {str(actual_page):^7} | {flag} {status}")

    print(f"{'-'*75}")
    print(f"Result for {theme_name.upper()}: {len(title_blocks) - mismatches}/{len(title_blocks)} matches ({mismatches} mismatches)")
    return mismatches


def main():
    root = Path(__file__).resolve().parent.parent
    total_mismatches = 0

    for theme in THEMES:
        pdf_path = root / f"sample_book_{theme}.pdf"
        total_mismatches += audit_theme(pdf_path)

    print(f"\n{'='*75}")
    if total_mismatches == 0:
        print("[+] ALL THEMES PASSED 100% REAL CONCORDANCE AUDIT (Exit Code 0)")
        print(f"{'='*75}\n")
        sys.exit(0)
    else:
        print(f"[-] FAILED: Detected {total_mismatches} page number mismatch(es) across themes! (Exit Code 1)")
        print(f"{'='*75}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
