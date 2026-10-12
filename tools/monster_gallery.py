"""Cuts assets/raw/monsters/sheetN.png (2x2 of 64px) into m0..m19 and renders a labeled preview."""
import json, glob
from PIL import Image, ImageDraw, ImageFont
D = json.load(open('design/monsters.json', encoding='utf-8'))
names = [m['name'] for g in D for m in g['mons']]
font = ImageFont.truetype([p for p in glob.glob('/usr/share/fonts/**/*.tt[cf]', recursive=True) if 'wqy' in p.lower()][0], 22)
S = 3; cell = 64 * S; cols = 4
sprites = []
for si in range(1, 6):
    sh = Image.open(f'assets/raw/monsters/sheet{si}.png').convert('RGBA')
    for q in range(4):
        m = sh.crop(((q % 2) * 64, (q // 2) * 64, (q % 2) * 64 + 64, (q // 2) * 64 + 64))
        m.save(f'assets/raw/monsters/m{len(sprites)}.png'); sprites.append(m)
rows = (len(sprites) + cols - 1) // cols
out = Image.new('RGB', (cols * (cell + 12) + 12, rows * (cell + 40) + 12), (244, 245, 246))
d = ImageDraw.Draw(out)
for i, m in enumerate(sprites):
    X = 12 + (i % cols) * (cell + 12); Y = 12 + (i // cols) * (cell + 40)
    big = m.resize((cell, cell), Image.NEAREST); out.paste(big, (X, Y), big)
    d.text((X + cell // 2, Y + cell + 2), names[i] if i < len(names) else '?', fill=(25, 31, 40), font=font, anchor='mt')
out.save('mockup/shots/monsters_art_all.png')
print(len(sprites), 'monsters')
