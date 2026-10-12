"""Collects every sprite the game uses into assets/game/all.json (data URIs) and embeds it into index.html (/*SPR*/ line).
Novice layers come from tools/make_sprites.py (assets/game/sprites.json); jobs, female and monsters from assets/."""
import base64, io, json, re
from PIL import Image
def uri(path):
    b = io.BytesIO(); Image.open(path).convert('RGBA').save(b, 'PNG', optimize=True)
    return 'data:image/png;base64,' + base64.b64encode(b.getvalue()).decode()
data = json.load(open('assets/game/sprites.json'))
for i in range(17):
    data[f'jf{i}'] = uri(f'assets/jobs/front{i}.png')
    data[f'jb{i}'] = uri(f'assets/raw/jobs/cut/back{i}.png')
for k in ('fnovice_front', 'fnovice_back', 'fthief_front', 'fthief_back'):
    data[k] = uri(f'assets/raw/jobs/cut/{k}.png')
for i in range(20):
    data[f'm{i}'] = uri(f'assets/raw/monsters/m{i}.png')
json.dump(data, open('assets/game/all.json', 'w'))
p = 'index.html'; s = open(p, encoding='utf-8').read()
line = 'const SPR = ' + json.dumps(data, separators=(',', ':')) + '; /*SPR*/'
s, n = re.subn(r'^const SPR = .*?; /\*SPR\*/$', lambda m: line, s, flags=re.M)
assert n == 1, n
D = json.load(open('design/monsters.json', encoding='utf-8'))
gd = [{'ground': g['ground'], 'mons': [{k: m[k] for k in ('name', 'weak', 'resist', 'act', 'drop')} for m in g['mons']]} for g in D]
s, n = re.subn(r'^const GD = .*?; /\*GD\*/$', lambda m: 'const GD = ' + json.dumps(gd, ensure_ascii=False, separators=(',', ':')) + '; /*GD*/', s, flags=re.M)
assert n == 1, n
open(p, 'w', encoding='utf-8').write(s)
print('embedded', len(line) // 1024, 'KB')
