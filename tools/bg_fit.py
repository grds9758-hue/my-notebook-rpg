#!/usr/bin/env python3
"""사냥터 배경 넣기: python3 tools/bg_fit.py <그림> <키> [--top N] [--w 720] [--q 78]
- 그림 위쪽 이름표(파일 이름 띠)를 --top 픽셀만큼 잘라 냄
- 가로 --w로 줄여 WebP로 ART[<키>]에 넣음 (예: bg/ground_0)
- 전투 위치는 index.html의 BGFIT(땅 높이 fy·my, 가운데 x, 아래 색 c)에서 맞춤
"""
import sys, io, json, base64, argparse
from PIL import Image
ap = argparse.ArgumentParser(); ap.add_argument('src'); ap.add_argument('key')
ap.add_argument('--top', type=int, default=0); ap.add_argument('--w', type=int, default=720); ap.add_argument('--q', type=int, default=78)
a = ap.parse_args()
im = Image.open(a.src).convert('RGB')
if a.top: im = im.crop((0, a.top, im.width, im.height))
if im.width > a.w: im = im.resize((a.w, round(im.height * a.w / im.width)), Image.LANCZOS)
b = io.BytesIO(); im.save(b, 'WEBP', quality=a.q, method=6)
uri = 'data:image/webp;base64,' + base64.b64encode(b.getvalue()).decode()
bot = im.crop((0, im.height - 20, im.width, im.height)).resize((1, 1), Image.BOX).getpixel((0, 0))
P = 'index.html'; s = open(P, encoding='utf-8').read()
i = s.index('const ART = '); j = s.index('/*ART*/', i)
art = json.loads(s[i + len('const ART = '):j].rstrip().rstrip(';'))
art[a.key] = uri
s = s[:i] + 'const ART = ' + json.dumps(art, ensure_ascii=False, separators=(',', ':')) + '; ' + s[j:]
open(P, 'w', encoding='utf-8').write(s)
print(f'{a.key}: {im.size} {len(b.getvalue())//1024}KB  ar={im.width/im.height:.3f}  아래색=#{bot[0]:02x}{bot[1]:02x}{bot[2]:02x}')
