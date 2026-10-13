"""Embeds the guide NPC expressions (assets/npc/guide0..14.jpg, cut from assets/raw/npc/guide_sheet.png) into index.html.

Re-cut: 5x3 grid of the sheet, background removed with rembg (isnet-anime, `pip install rembg onnxruntime`),
trimmed to the figure and saved as 260px-wide WebP with alpha so she stands in the town scene.
"""
import base64, re
from PIL import Image
from rembg import remove, new_session
import numpy as np
from scipy import ndimage
SES = None

def cut():
    im = Image.open('assets/raw/npc/guide_sheet.png').convert('RGB'); W, H = im.size
    for r in range(3):
        for c in range(5):
            t = im.crop((round(c*W/5)+4, round(r*H/3)+4, round((c+1)*W/5)-4, round((r+1)*H/3)-4))
            t = remove(t, session=SES)
            a = np.array(t.getchannel('A')); a[a < 24] = 0
            lab, n = ndimage.label(a > 0)  # keep the figure only: drop bits of neighbouring cells
            if n > 1: a[lab != 1 + np.argmax(ndimage.sum(a > 0, lab, range(1, n+1)))] = 0
            a = Image.fromarray(a); t.putalpha(a)
            t = t.crop(a.getbbox())
            t.resize((260, round(260*t.height/t.width)), Image.LANCZOS).save(f'assets/npc/guide{r*5+c}.webp', quality=86, method=6)

if __name__ == '__main__':
    SES = new_session('isnet-anime')
    cut()
    faces = ['"data:image/webp;base64,' + base64.b64encode(open(f'assets/npc/guide{i}.webp','rb').read()).decode() + '"' for i in range(15)]
    bg = Image.open('assets/raw/npc/town_bg.png').convert('RGB'); bg = bg.resize((960, round(960*bg.height/bg.width)), Image.LANCZOS)
    bg.save('assets/npc/town_bg.webp', quality=80, method=6)
    faces.append('"data:image/webp;base64,' + base64.b64encode(open('assets/npc/town_bg.webp','rb').read()).decode() + '"')
    line = 'const NPC_FACE = [' + ','.join(faces) + ']; /*NPC*/'  # 0..14 faces, 15 = town background
    s = open('index.html').read()
    if '/*NPC*/' in s: s = re.sub(r'const NPC_FACE = \[.*?\]; /\*NPC\*/', lambda m: line, s, flags=re.S)
    else: s = s.replace('const NPC_SVG = `', line + '\nconst NPC_SVG = `', 1)
    open('index.html','w').write(s)
