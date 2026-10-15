#!/usr/bin/env python3
"""배포 전에: 게임 안 업데이트 알림용 BUILD·CHANGES 바꾸기.
쓰는 법: python3 tools/bump.py "바뀐 점 1" "바뀐 점 2" ...   (사용자에게 보이는 짧은 한국어)"""
import sys, re, json, datetime
p = 'index.html'; s = open(p, encoding='utf-8').read()
cur = re.search(r"const BUILD = '([^']+)'; /\*BUILD\*/", s).group(1)
today = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).strftime('%Y-%m-%d')
n = int(cur.split('.')[1]) + 1 if cur.startswith(today) else 1
new = f'{today}.{n}'
s = re.sub(r"const BUILD = '[^']+'; /\*BUILD\*/", f"const BUILD = '{new}'; /*BUILD*/", s)
s = re.sub(r"const CHANGES = \[[^\n]*?\]; /\*CHANGES\*/", 'const CHANGES = ' + json.dumps(sys.argv[1:], ensure_ascii=False) + '; /*CHANGES*/', s)
open(p, 'w', encoding='utf-8').write(s)
print(new)
