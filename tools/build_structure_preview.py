"""Builds mockup/structure-preview.html: the age-free progression (home, hunting grounds, job change, quests, EXP curve)."""
import base64, io, json
from PIL import Image
def uri(p):
    b = io.BytesIO(); Image.open(p).convert('RGBA').save(b, 'PNG'); return 'data:image/png;base64,' + base64.b64encode(b.getvalue()).decode()
D = json.load(open('design/monsters.json', encoding='utf-8'))
mexp = [round(10 * 1.5 ** g) for g in range(10)]
kills = lambda lv: round(5 + lv * 1.5)
spr = json.load(open('assets/game/sprites.json'))
from PIL import Image as I
c = I.open('assets/game/body0.png').convert('RGBA')
for k in ['hair0', 'wpn2', 'fist0']: c.alpha_composite(I.open(f'assets/game/{k}.png').convert('RGBA'))
b = io.BytesIO(); c.save(b, 'PNG'); me = 'data:image/png;base64,' + base64.b64encode(b.getvalue()).decode()

grounds = ''
for g, G in enumerate(D):
    lo = int(G['lv'].split('–')[0])
    st = 'rec' if g == 4 else ('lock' if g > 5 else '')
    mons = ''.join(f'<img class="px" src="{uri(f"assets/raw/monsters/m{g*2+j}.png")}" alt="">' for j in range(2))
    tag = '추천' if st == 'rec' else ('잠김' if st == 'lock' else '')
    grounds += f'''<div class="gr {st}"><div class="mons">{mons}</div><div class="grow"><b>{G["ground"]}</b> <span class="chip {'blue' if st=='rec' else ''}">{tag+' · ' if tag else ''}Lv.{G["lv"]}</span>
      <div class="d">{' · '.join(m['name'] for m in G['mons'])} · 1마리 EXP {mexp[g]}</div></div></div>'''

JOBS = [(0, '전사', '맨 앞에서 버티는 근접 전투', '힘 · 체력', '양손검 기사 / 방패 기사 / 라이딩 기사'),
        (1, '궁수', '멀리서 약점을 꿰뚫는다', '민첩 · 행운', '트랩 궁수 / 활 궁수'),
        (2, '도적', '빠른 연속 공격과 회피', '민첩 · 힘', '단검(이도류) / 표창 / 무희(여캐)'),
        (3, '힐러', '회복과 빛 속성', '정신 · 체력', '사제 / 몽크'),
        (4, '마법사', '속성 마법으로 약점 공략', '지능 · 정신', '위자드 / 정령사')]
jobs = ''.join(f'''<div class="job {'sel' if i==0 else ''}"><img class="px" src="{uri(f"assets/jobs/front{i}.png")}" alt=""><div class="grow"><b>{n}</b><div class="d">{d}</div>
  <div class="d">핵심 {k}</div><div class="route">루트 · {r}</div></div></div>''' for i, n, d, k, r in JOBS)

lvls = [1, 5, 10, 15, 20, 25, 30, 35, 40, 45, 49]
mx = kills(49)
bars = ''.join(f'<div class="bc"><i style="height:{kills(l)/mx*104:.0f}px"></i><span>{kills(l)}</span><small>{l}</small></div>' for l in lvls)
cum = lambda L: round(sum(kills(l) for l in range(1, L)) / 2.5 * .75)

html = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>진행 구조 미리보기</title>
<style>
:root{{--bg:#f2f4f6;--s:#fff;--s2:#f4f5f7;--ink:#191f28;--sub:#4e5968;--mu:#8b95a1;--line:#e5e8eb;--blue:#3182f6;--bs:#e8f3ff;--red:#f04452;--gold:#e5a50a;--exp:#ffb400}}
@media (prefers-color-scheme: dark){{:root:not([data-theme="light"]){{--bg:#101318;--s:#1b1f26;--s2:#242a33;--ink:#eef1f4;--sub:#b0b8c1;--mu:#7d8692;--line:#2c333d;--bs:#1d2a3d}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font-family:'Noto Sans KR',system-ui,sans-serif;font-size:14.5px;line-height:1.5}}
.app{{max-width:480px;margin:0 auto;padding:12px 16px 24px}}.px{{image-rendering:pixelated;image-rendering:crisp-edges}}
.t{{font-weight:700;font-size:13px;color:var(--sub);margin:18px 2px 6px}}.card{{background:var(--s);border-radius:20px;padding:18px;margin-bottom:10px}}
h2{{font-size:16px;margin:0 0 10px}}.row{{display:flex;gap:12px;align-items:center}}.grow{{flex:1;min-width:0}}
.av{{width:72px;height:72px;border-radius:16px;background:var(--s2);display:grid;place-items:center}}.av img{{width:64px;height:64px}}
.lv{{font-size:12px;font-weight:700;color:var(--blue);background:var(--bs);padding:2px 8px;border-radius:6px}}
.bar{{height:8px;border-radius:99px;background:var(--s2);overflow:hidden;margin-top:4px}}.bar i{{display:block;height:100%;border-radius:99px}}
.bl{{display:flex;justify-content:space-between;font-size:12.5px;color:var(--sub);margin-top:10px}}.bl b{{color:var(--ink)}}
.d{{font-size:12.5px;color:var(--mu)}}.chip{{font-size:11.5px;font-weight:700;padding:1px 7px;border-radius:6px;background:var(--s2);color:var(--sub)}}.chip.blue{{background:var(--bs);color:var(--blue)}}
.li{{display:flex;gap:12px;align-items:center;padding:10px 0;border-top:1px solid var(--line)}}.li:first-of-type{{border-top:0}}
.ic{{width:38px;height:38px;border-radius:50%;background:var(--bs);color:var(--blue);display:grid;place-items:center;font-size:17px;flex:none}}
.dot{{display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--red);vertical-align:2px}}
.cta{{display:block;width:100%;border:0;border-radius:16px;background:var(--blue);color:#fff;font:inherit;font-weight:700;font-size:16px;padding:15px;margin:2px 0 10px}}
.gr{{display:flex;gap:10px;align-items:center;padding:9px 0;border-top:1px solid var(--line)}}.gr:first-of-type{{border-top:0}}.gr.lock{{opacity:.45}}
.gr.rec{{background:var(--bs);margin:0 -10px;padding:9px 10px;border-radius:14px;border-top:0}}
.mons{{display:flex;flex:none}}.mons img{{width:46px;height:46px;margin-right:-8px}}
.job{{display:flex;gap:10px;align-items:center;padding:8px;border-radius:14px;background:var(--s2);margin-top:8px;border:2px solid transparent}}.job.sel{{border-color:var(--blue);background:var(--bs)}}
.job img{{width:72px;height:72px;flex:none}}.route{{font-size:12px;color:var(--blue);font-weight:500;margin-top:2px}}
.chart{{display:flex;gap:4px;align-items:flex-end;height:150px;padding-top:16px}}.bc{{flex:1;height:100%;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;position:relative}}
.bc i{{display:block;width:100%;background:var(--exp);border-radius:5px 5px 2px 2px}}.bc span{{font-size:10.5px;font-weight:700}}.bc small{{font-size:10.5px;color:var(--mu)}}
.kv{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;margin-top:12px;text-align:center}}.kv div{{background:var(--s2);border-radius:12px;padding:8px 2px}}.kv b{{display:block;font-size:17px}}
.note{{font-size:12.5px;color:var(--sub);margin-top:10px;line-height:1.6}}
</style></head><body><div class="app">

<div class="t">① 홈 · 나이 없이 레벨 중심</div>
<div class="card"><div class="row"><div class="av"><img class="px" src="{me}" alt=""></div><div class="grow">
  <div class="d">리안 · 변방 용병단</div><div style="font-size:20px;font-weight:700"><span class="lv">노비스 Lv.23</span> 전투력 61</div>
  <div class="d">전직까지 27레벨</div></div></div>
  <div class="bl"><span>경험치</span><span><b>41.2%</b> · 1,630 / 3,960</span></div><div class="bar"><i style="width:41%;background:var(--exp)"></i></div>
  <div class="bl"><span>HP</span><span><b>412</b> / 450</span></div><div class="bar"><i style="width:91%;background:var(--red)"></i></div>
  <div class="bl"><span>MP</span><span><b>96</b> / 140</span></div><div class="bar"><i style="width:68%;background:var(--blue)"></i></div></div>
<div class="card"><h2>확인할 일</h2>
  <div class="li"><div class="ic">📜</div><div class="grow"><b>오늘의 의뢰 2 / 3</b> <span class="dot"></span><div class="d">늪 트롤 15마리 · 매일 새로 받음</div></div></div>
  <div class="li"><div class="ic">🛡️</div><div class="grow"><b>승급 시험을 볼 수 있어요</b> <span class="dot"></span><div class="d">변방 용병단 → 모험가 길드 · Lv.20 이상</div></div></div>
  <div class="li"><div class="ic">⭐</div><div class="grow"><b>능력치 포인트 3</b><div class="d">레벨 업마다 지급</div></div></div></div>
<button class="cta">트롤 늪지로 사냥 가기</button>

<div class="t">② 사냥터 · 노비스 Lv.1~50 (10곳)</div>
<div class="card"><h2>사냥터</h2>{grounds}
  <p class="note">내 레벨보다 5 이상 낮은 사냥터는 경험치 −50%, 10 이상 낮으면 −90%. 위로 올라가야 빨리 큰다.</p></div>

<div class="t">③ 전직 · 노비스 Lv.50 달성 시</div>
<div class="card"><h2>전직할 직업을 골라요</h2><div class="d">전직하면 Lv.1부터 다시 시작하고, 최대 Lv.99까지 오른다. 루트는 직업 Lv.30에 고른다.</div>{jobs}
  <button class="cta" style="margin-top:12px">전사로 전직하기</button></div>

<div class="t">④ 퀘스트 · 소속 · 성장</div>
<div class="card"><h2>메인 퀘스트</h2>
  <div class="li"><div class="ic">📖</div><div class="grow"><b>3장 · 늪에 잠긴 마을</b><div class="d">트롤 늪지 조사 · 보상 EXP 2,000 · 희귀 장비</div></div></div>
  <h2 style="margin-top:14px">소속 승급 시험</h2>
  <div class="li"><div class="ic">🛡️</div><div class="grow"><b>모험가 길드 입단 시험</b><div class="d">조건 Lv.20 · 시련 전투(정예 몬스터 3연전) · 통과하면 소속 보너스와 상점 개방</div></div></div>
  <div class="d" style="margin-top:6px">자경단 → 수련원 → 용병단 → 길드 → 기사단 → 근위대 → 원정대 (Lv.5·10·20·35·50·직업 Lv.30)</div>
  <h2 style="margin-top:14px">훈련소</h2>
  <div class="li"><div class="ic">🏋️</div><div class="grow"><b>골드로 능력치 +1</b><div class="d">한 번 할수록 비용 증가 · 잠재력의 벽은 그대로</div></div></div>
  <h2 style="margin-top:14px">기록</h2>
  <div class="li"><div class="ic">🏅</div><div class="grow"><b>업적 · 칭호</b><div class="d">은퇴와 명예의 전당 대신 업적과 칭호로 남긴다</div></div></div></div>

<div class="t">⑤ 경험치 곡선 · 레벨당 필요한 몬스터 수</div>
<div class="card"><h2>노비스 레벨업 난이도</h2><div class="chart">{bars}</div>
  <div class="kv"><div><b>~{cum(10)}</b><span class="d">Lv.10까지 전투</span></div><div><b>~{cum(30)}</b><span class="d">Lv.30까지</span></div><div><b>~{cum(50)}</b><span class="d">Lv.50까지</span></div></div>
  <p class="note">전투 1번에 몬스터 2~3마리. 의뢰·퀘스트 보상이 경험치의 약 25%. 메이플처럼 갈수록 가파르지만, Lv.50까지 전투 약 {cum(50)}번(빠른 전투 기준 3~4시간)으로 너무 극단적이지 않게.</p></div>
</div></body></html>'''
open('mockup/structure-preview.html', 'w', encoding='utf-8').write(html)
