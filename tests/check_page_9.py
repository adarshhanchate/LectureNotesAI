import fitz

doc = fitz.open("sample_book_indigo.pdf")

print("=== CHECKING PAGE 9 (Problem 3.2 Part 2 Continued) ===")
p9 = doc[8]
for b in p9.get_text("blocks"):
    # encode to ascii or safe string
    txt = b[4].strip().replace("\n", " ").encode("ascii", errors="replace").decode("ascii")[:100]
    print(f"  y: [{b[1]:.1f} - {b[3]:.1f}] | {txt}")
