import fitz

doc = fitz.open('sample_book_indigo.pdf')
p2 = doc[1]
links = p2.get_links()
print('Total links on Page 2:', len(links))
for i, l in enumerate(links[:15]):
    tgt = l.get('page')
    tgt_p = tgt + 1 if tgt is not None else 'None'
    k = l.get('kind')
    r = l.get('from')
    print(f'Link {i+1}: kind={k}, target_page={tgt_p}, rect={r}')
