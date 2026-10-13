"""Embeds the guide NPC expressions (assets/npc/guide0..14.jpg, cut from assets/raw/npc/guide_sheet.png) into index.html.

Re-cut: 5x3 grid of the sheet, each cell resized to 240px wide JPEG.
"""
import base64, re
from PIL import Image

def cut():
    im = Image.open('assets/raw/npc/guide_sheet.png').convert('RGB'); W, H = im.size
    for r in range(3):
        for c in range(5):
            t = im.crop((round(c*W/5)+4, round(r*H/3)+4, round((c+1)*W/5)-4, round((r+1)*H/3)-4))
            t.resize((240, round(240*t.height/t.width)), Image.LANCZOS).save(f'assets/npc/guide{r*5+c}.jpg', quality=82)

if __name__ == '__main__':
    cut()
    faces = ['"data:image/jpeg;base64,' + base64.b64encode(open(f'assets/npc/guide{i}.jpg','rb').read()).decode() + '"' for i in range(15)]
    line = 'const NPC_FACE = [' + ','.join(faces) + ']; /*NPC*/'
    s = open('index.html').read()
    if '/*NPC*/' in s: s = re.sub(r'const NPC_FACE = \[.*?\]; /\*NPC\*/', lambda m: line, s, flags=re.S)
    else: s = s.replace('const NPC_SVG = `', line + '\nconst NPC_SVG = `', 1)
    open('index.html','w').write(s)
