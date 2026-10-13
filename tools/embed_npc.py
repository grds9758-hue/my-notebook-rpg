"""Embeds the guide NPC expressions (assets/npc/guide0..17.webp, cut from assets/raw/npc/guide_sheet.png) into index.html.

Re-cut: 6x3 grid of the sheet, background removed with rembg (isnet-anime, `pip install rembg onnxruntime`),
trimmed to the figure and saved as 260px-wide WebP with alpha so she stands in the town scene.
"""
import base64, re
from PIL import Image
from rembg import remove, new_session
import numpy as np
from scipy import ndimage
SES = None
COLS, ROWS = 6, 3

def cut():
    im = Image.open('assets/raw/npc/guide_sheet.png').convert('RGB'); W, H = im.size
    # rows are split at the blank white bands between them (pure-white full-width lines)
    g = np.array(im.convert('L')); white = (g > 240).mean(axis=1) > .98
    bands, y = [], 0
    while y < H:
        if white[y]:
            y0 = y
            while y < H and white[y]: y += 1
            if y - y0 >= 6: bands.append((y0, y))
        y += 1
    edges = [0] + [b for a, b2 in bands for b in (a, b2)] + [H]
    rows = [(edges[i], edges[i+1]) for i in range(0, len(edges), 2) if edges[i+1] - edges[i] > 100]
    assert len(rows) == ROWS, rows
    for r, (ry0, ry1) in enumerate(rows):
        for c in range(COLS):
            t = im.crop((round(c*W/COLS)+4, ry0, round((c+1)*W/COLS)-4, ry1))
            g = np.array(t.convert('L')); blank = (g > 238).mean(axis=1) > .96  # white gap rows under the figure
            y1 = len(blank)
            while y1 > 1 and blank[y1-1]: y1 -= 1
            t = t.crop((0, 0, t.width, y1))
            t = remove(t, session=SES)
            a = np.array(t.getchannel('A')); a[a < 24] = 0
            lab, n = ndimage.label(a > 0)  # keep the figure only: drop bits of neighbouring cells
            if n > 1: a[lab != 1 + np.argmax(ndimage.sum(a > 0, lab, range(1, n+1)))] = 0
            a = Image.fromarray(a); t.putalpha(a)
            t = t.crop(a.getbbox())
            t.resize((260, round(260*t.height/t.width)), Image.LANCZOS).save(f'assets/npc/guide{r*COLS+c}.webp', quality=86, method=6)

if __name__ == '__main__':
    SES = new_session('isnet-anime')
    cut()
    faces = ['"data:image/webp;base64,' + base64.b64encode(open(f'assets/npc/guide{i}.webp','rb').read()).decode() + '"' for i in range(COLS*ROWS)]
    bg = Image.open('assets/raw/npc/town_bg.png').convert('RGB'); bg = bg.resize((960, round(960*bg.height/bg.width)), Image.LANCZOS)
    bg.save('assets/npc/town_bg.webp', quality=80, method=6)
    faces.append('"data:image/webp;base64,' + base64.b64encode(open('assets/npc/town_bg.webp','rb').read()).decode() + '"')
    line = 'const NPC_FACE = [' + ','.join(faces) + ']; /*NPC*/'  # faces first, town background last
    s = open('index.html').read()
    if '/*NPC*/' in s: s = re.sub(r'const NPC_FACE = \[.*?\]; /\*NPC\*/', lambda m: line, s, flags=re.S)
    else: s = s.replace('const NPC_SVG = `', line + '\nconst NPC_SVG = `', 1)
    open('index.html','w').write(s)
