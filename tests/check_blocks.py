import fitz

doc = fitz.open("sample_book_indigo.pdf")

for pno in [6, 7, 8, 9]:
    p = doc[pno]
    print(f"\n================ PAGE {pno+1} (height: {p.rect.height}) ================")
    blocks = p.get_text("blocks")
    for b in blocks:
        # b is (x0, y0, x1, y1, text, block_no, block_type)
        txt = b[4].strip().replace("\n", " ")
        if len(txt) > 80:
            txt = txt[:80] + "..."
        print(f"y: [{b[1]:.1f} - {b[3]:.1f}] | {txt}")
