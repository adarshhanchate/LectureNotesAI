import fitz

doc = fitz.open("sample_book_indigo.pdf")

print("=== CHECKING PAGE 7 (Problem 3.1) ===")
p7 = doc[6]
for b in p7.get_text("blocks"):
    txt = b[4].strip().replace("\n", " ")[:80]
    print(f"  y: [{b[1]:.1f} - {b[3]:.1f}] | {txt}")

print("\n=== CHECKING PAGE 8 (Problem 3.2 Part 1) ===")
p8 = doc[7]
for b in p8.get_text("blocks"):
    txt = b[4].strip().replace("\n", " ")[:80]
    print(f"  y: [{b[1]:.1f} - {b[3]:.1f}] | {txt}")

print("\n=== CHECKING PAGE 9 (Problem 3.2 Part 2 Continued) ===")
p9 = doc[8]
for b in p9.get_text("blocks"):
    txt = b[4].strip().replace("\n", " ")[:80]
    print(f"  y: [{b[1]:.1f} - {b[3]:.1f}] | {txt}")
