"""Renders design/monsters.json to mockup/monsters.html (design sheet, no sprites yet)."""
import json, html
D = json.load(open('design/monsters.json', encoding='utf-8'))
E = html.escape
def tags(xs, cls):
    return ''.join(f'<span class="tg {cls}">{E(x)}</span>' for x in xs) or '<span class="tg">없음</span>'
def card(m, boss=False):
    return f'''<div class="m{' boss' if boss else ''}"><div class="hd"><b>{E(m["name"])}</b>{'<span class="bb">보스</span>' if boss else ''}</div>
<p class="look">{E(m["look"])}</p>
<div class="row"><span class="k">약점</span>{tags(m["weak"],"w")}</div>
<div class="row"><span class="k">내성</span>{tags(m["resist"],"r")}</div>
<p class="act">{E(m["act"])}</p><p class="drop">드롭 · {E(m["drop"])}</p></div>'''
body = ''.join(f'''<section><h2>{E(g["ground"])} <small>Lv.{E(g["lv"])}</small></h2><div class="grid">{''.join(card(m) for m in g["mons"])}{card(g["boss"], True)}</div></section>''' for g in D)
page = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>몬스터 도감</title>
<style>
:root{{--bg:#f2f4f6;--s:#fff;--s2:#f4f5f7;--ink:#191f28;--sub:#4e5968;--mu:#8b95a1;--red:#f04452;--blue:#3182f6;--gold:#e5a50a}}
@media (prefers-color-scheme: dark){{:root:not([data-theme="light"]){{--bg:#101318;--s:#1b1f26;--s2:#242a33;--ink:#eef1f4;--sub:#b0b8c1;--mu:#7d8692}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font-family:'Noto Sans KR',system-ui,sans-serif;font-size:14px;line-height:1.5}}
.app{{max-width:480px;margin:0 auto;padding:16px}}h1{{font-size:20px;margin:4px 2px 12px}}
section{{background:var(--s);border-radius:20px;padding:16px;margin-bottom:12px}}h2{{font-size:16px;margin:0 0 10px}}h2 small{{font-size:12px;color:var(--mu);font-weight:500}}
.grid{{display:grid;gap:8px}}.m{{background:var(--s2);border-radius:14px;padding:11px 12px}}.m.boss{{background:#fff7e6;outline:1.5px solid #f5d38a}}
.hd{{display:flex;align-items:center;gap:6px;font-size:15px}}.bb{{font-size:11px;font-weight:700;color:#fff;background:var(--gold);border-radius:6px;padding:0 6px}}
.look{{margin:3px 0 6px;color:var(--sub);font-size:13px}}.row{{display:flex;align-items:center;gap:4px;margin:2px 0;flex-wrap:wrap}}.k{{font-size:12px;color:var(--mu);width:30px}}
.tg{{font-size:11.5px;font-weight:700;padding:0 6px;border-radius:5px;background:var(--s);color:var(--mu)}}.tg.w{{background:#ffe1e4;color:var(--red)}}.tg.r{{background:#e6eefc;color:#5871a8}}
.act{{margin:6px 0 0;font-size:12.5px}}.drop{{margin:2px 0 0;font-size:12px;color:var(--mu)}}
</style></head><body><div class="app"><h1>몬스터 도감 · 설정안</h1>{body}</div></body></html>'''
open('mockup/monsters.html', 'w', encoding='utf-8').write(page)
