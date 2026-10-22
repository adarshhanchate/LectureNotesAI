import json
from pathlib import Path
import fitz  # PyMuPDF

PROJECT_ROOT = Path(r"c:\Users\ashan\Documents\NLP mini project")
ARTIFACT_DIR = Path(r"C:\Users\ashan\.gemini\antigravity-ide\brain\0957641c-3107-49a3-a864-67d3c6aeeee4")
SCREENSHOT_DIR = ARTIFACT_DIR / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

def inspect_pdf(pdf_path: Path):
    doc = fitz.open(str(pdf_path))
    print(f"\n==========================================")
    print(f"Inspecting PDF: {pdf_path.name}")
    print(f"Total Pages: {len(doc)}")
    
    # Check Bookmarks (TOC)
    bookmarks = doc.get_toc()
    print(f"\n--- PDF Bookmarks ({len(bookmarks)} items) ---")
    for level, title, page in bookmarks[:15]:
        print(f"  Level {level}: '{title}' -> Page {page}")
    if len(bookmarks) > 15:
        print(f"  ... and {len(bookmarks) - 15} more bookmarks")
        
    # Check Links on Page 2 (TOC page, index 1)
    toc_page = doc[1]
    links = toc_page.get_links()
    print(f"\n--- Page 2 Links ({len(links)} links found) ---")
    for link in links[:10]:
        target_page = link.get("page", None)
        print(f"  Link kind: {link.get('kind')}, target page: {target_page}")

    # Extract text from Page 2 (TOC)
    print(f"\n--- Page 2 (TOC) Raw Text ---")
    text_p2 = toc_page.get_text()
    for line in text_p2.splitlines():
        if line.strip():
            print(f"  {line.strip()}")
            
    return doc, bookmarks

def render_screenshots(pdf_path: Path, pages_to_render: dict, prefix: str):
    doc = fitz.open(str(pdf_path))
    matrix = fitz.Matrix(2.0, 2.0) # 144 dpi crisp rendering
    saved_paths = {}
    for name, pno in pages_to_render.items():
        if pno < len(doc):
            page = doc[pno]
            pix = page.get_pixmap(matrix=matrix)
            filename = f"{prefix}_{name}_p{pno+1}.png"
            dest = SCREENSHOT_DIR / filename
            pix.save(str(dest))
            saved_paths[name] = dest
            print(f"Saved screenshot: {dest.name} ({pix.width}x{pix.height})")
    return saved_paths

if __name__ == "__main__":
    indigo_pdf = PROJECT_ROOT / "sample_book_indigo.pdf"
    doc, bookmarks = inspect_pdf(indigo_pdf)
    
    # Screenshots mapping (0-indexed page numbers):
    # Indigo: cover (0), index (1), concept (2), numerical (6 or 7), formula cheat-sheet (10), questions (11), answer key (13)
    indigo_pages = {
        "cover": 0,
        "index": 1,
        "concept": 2,
        "numerical_card": 7,  # Page 8: long numerical problem continuation
        "formula_cheatsheet": 10, # Page 11: Summary & Formulas
        "questions": 11, # Page 12: Question bank
        "answer_key": 13 # Page 14: Answer key
    }
    render_screenshots(indigo_pdf, indigo_pages, "indigo")
    
    # Emerald
    emerald_pdf = PROJECT_ROOT / "sample_book_emerald.pdf"
    render_screenshots(emerald_pdf, {"cover": 0, "concept": 2}, "emerald")
    
    # Sunset
    sunset_pdf = PROJECT_ROOT / "sample_book_sunset.pdf"
    render_screenshots(sunset_pdf, {"cover": 0, "concept": 2}, "sunset")
    
    # Print-friendly
    print_pdf = PROJECT_ROOT / "sample_book_print.pdf"
    render_screenshots(print_pdf, {"cover": 0, "concept": 2}, "print")
