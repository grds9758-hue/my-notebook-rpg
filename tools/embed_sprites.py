"""Embeds assets/game/sprites.json into index.html on the line marked /*SPR*/."""
import json, re
data = json.load(open('assets/game/sprites.json'))
p = 'index.html'; s = open(p, encoding='utf-8').read()
line = 'const SPR = ' + json.dumps(data, separators=(',', ':')) + '; /*SPR*/'
s, n = re.subn(r'^const SPR = .*?; /\*SPR\*/$', lambda m: line, s, flags=re.M)
assert n == 1, n
open(p, 'w', encoding='utf-8').write(s)
print('embedded', len(line), 'chars')
