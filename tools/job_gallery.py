"""Cuts assets/raw/jobs/{front,back}N.png into 64px job sprites and renders a labeled front/back preview."""
import glob, os
from PIL import Image, ImageDraw, ImageFont
NAMES = ['전사', '궁수', '도적', '힐러', '마법사', '양손검 기사', '방패 기사', '라이딩 기사', '트랩 궁수', '활 궁수',
         '단검 도적', '표창 도적', '무희', '사제', '몽크', '위자드', '정령사', '여캐 노비스', '여캐 사제', '여캐 궁수']
os.makedirs('assets/raw/jobs/cut', exist_ok=True)
font = ImageFont.truetype([p for p in glob.glob('/usr/share/fonts/**/*.tt[cf]', recursive=True) if 'wqy' in p.lower()][0], 20)
S = 3; cell = 64 * S; cols = 4
for side in ('front', 'back'):
    out = Image.new('RGB', (cols * (cell + 10) + 10, 5 * (cell + 34) + 10), (244, 245, 246)); d = ImageDraw.Draw(out)
    for si in range(5):
        sh = Image.open(f'assets/raw/jobs/{side}{si + 1}.png').convert('RGBA')
        for q in range(4):
            i = si * 4 + q
            m = sh.crop(((q % 2) * 64, (q // 2) * 64, (q % 2) * 64 + 64, (q // 2) * 64 + 64)); m.save(f'assets/raw/jobs/cut/{side}{i}.png')
            X = 10 + q * (cell + 10); Y = 10 + si * (cell + 34)
            big = m.resize((cell, cell), Image.NEAREST); out.paste(big, (X, Y), big)
            d.text((X + cell // 2, Y + cell + 2), NAMES[i], fill=(25, 31, 40), font=font, anchor='mt')
    out.save(f'mockup/shots/jobs_{side}.png')
