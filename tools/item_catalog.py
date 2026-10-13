import json, html
SP='./'  # folder holding items.json (dump of index.html constants)
d=json.load(open(SP+'items.json')); eq=json.load(open('design/equipment.json'))
N=d['ITEM_NAMES']; B=d['BANDS']; SET=d['SET']; SUB=d['SUB_KINDS']; G=d['GD']
e=html.escape
slots=[('weapon','무기','힘(직업 주능력)·공격력'),('helm','투구','방어·체력'),('top','상의','방어·체력'),('bottom','하의','방어·민첩'),('suit','한벌옷','상의+하의 칸을 함께 차지'),('shoes','신발','방어·민첩'),('cape','망토','행운·정신'),('necklace','목걸이','체력·행운'),('earring','귀걸이','지능·정신')]
STATS=['힘','민첩','지능','체력','정신','행운']
rar=[('일반','r0'),('고급','r1'),('희귀','r2'),('영웅','r3'),('전설','r4')]
setslots={'helm','top','bottom','suit','shoes','cape'}
def lvlist(names, setmark=False):
    return '<ol class="tier">'+''.join(f'<li><span class="lv">Lv.{B[i]}</span><span class="nm">{e(n)}</span>{f"<span class=set>{e(SET[i])}</span>" if setmark else ""}</li>' for i,n in enumerate(names))+'</ol>'
cards=''.join(f'<article class="slot"><header><h3>{n}</h3><span class="hint">{h}</span></header>{lvlist(N[k], k in setslots)}</article>' for k,n,h in slots)
subwho={'shield':'노비스 · 소드맨 · 크루세이더 · 드래곤 나이트','dagger':'어쌔신 (이도류 수련을 배운 뒤)','quiver':'아처 · 헌터 · 스나이퍼','tome':'어콜라이트 · 프리스트 · 매지션 · 위자드 · 소서러'}
subcards=''.join(f'<article class="slot"><header><h3>{e(v["n"])}</h3><span class="hint">{subwho[k]}</span></header>{lvlist(v["names"])}</article>' for k,v in SUB.items())
ringrows=''.join(f'<li><span class="lv">Lv.{B[i]}</span><span class="nm">{e(m)} ○○의 반지</span></li>' for i,m in enumerate(N['ring']))
mats=''.join(f'<tr><td class="g">{e(g["ground"])}</td><td>{e(m["name"])}</td><td><b>{e(m["drop"])}</b></td><td class="num">{4*(gi+1)}G</td></tr>' for gi,g in enumerate(G) for m in g['mons'])
jobs=''
for jn,j in eq['jobs'].items():
    routes=''.join(f'<div class="route"><b>{e(rn)}</b><span>{" · ".join(e(x) for x in rw)}</span></div>' for rn,rw in j['routes'].items())
    jobs+=f'<article class="slot plan"><header><h3>{e(jn)}</h3><span class="hint">{e(j["stat"])}</span></header><p class="row"><b>방어구 세트</b> {" · ".join(e(x) for x in j["armor"])}</p><p class="row"><b>공용 무기</b> {" · ".join(e(x) for x in j["weapon"])}</p>{routes}</article>'
sh=eq['shared_job_tier']
base=sum(len(N[k]) for k,_,_ in slots)+len(N['ring'])*6+sum(len(v['names']) for v in SUB.values())
page=f'''<title>공책 RPG 아이템 도감</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Do+Hyeon&family=Noto+Sans+KR:wght@400;500;700&display=swap">
<style>
/* Layout: 도감 — summary strip, then one card per equipment slot (10 tiers each), then materials table, then the planned-but-unbuilt job gear */
:root{{
  --bg:#f2f4f8; --card:#ffffff; --ink:#1c2230; --muted:#6a7486; --line:#e1e6ee; --accent:#2f6fe0; --soft:#e8f0ff; --gold:#c4860f;
  --r0:#86909f; --r1:#22915a; --r2:#2c66d8; --r3:#8a4cd4; --r4:#cc8c0c;
  --display:'Do Hyeon','Noto Sans KR',sans-serif; --body:'Noto Sans KR','Apple SD Gothic Neo','Malgun Gothic',sans-serif;
}}
@media (prefers-color-scheme: dark){{:root:not([data-theme="light"]){{--bg:#10141b;--card:#181e28;--ink:#e6ebf3;--muted:#8f9aac;--line:#283244;--accent:#7aa6ff;--soft:#1d2a44;--gold:#f0bd48;--r0:#9aa4b3;--r1:#5fd394;--r2:#6d9bff;--r3:#b98cff;--r4:#f0bd48;color-scheme:dark}}}}
:root[data-theme="dark"]{{--bg:#10141b;--card:#181e28;--ink:#e6ebf3;--muted:#8f9aac;--line:#283244;--accent:#7aa6ff;--soft:#1d2a44;--gold:#f0bd48;--r0:#9aa4b3;--r1:#5fd394;--r2:#6d9bff;--r3:#b98cff;--r4:#f0bd48;color-scheme:dark}}
*{{box-sizing:border-box}}
body{{background:var(--bg);color:var(--ink);font-family:var(--body);font-size:14px;line-height:1.55}}
.wrap{{max-width:1080px;margin:0 auto;padding-inline:16px;padding-block:20px 56px;display:grid;gap:28px}}
h1,h2,h3{{font-family:var(--display);font-weight:400;margin:0;line-height:1.2;text-wrap:balance}}
h1{{font-size:32px}} h2{{font-size:24px}} h3{{font-size:19px}}
p{{margin:0}}
.lead{{color:var(--muted);max-width:62ch}}
.stats{{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}}
.stats span{{background:var(--card);border:1px solid var(--line);border-radius:999px;padding:4px 12px;font-size:13px}}
.stats b{{font-variant-numeric:tabular-nums}}
section{{display:grid;gap:12px}}
.sec-h{{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 12px}}
.sec-h p{{color:var(--muted);font-size:13px}}
.rar{{display:flex;flex-wrap:wrap;gap:8px}}
.rar span{{border:2px solid currentColor;border-radius:8px;padding:2px 10px;font-weight:700;font-size:13px;background:var(--card)}}
.r0{{color:var(--r0)}}.r1{{color:var(--r1)}}.r2{{color:var(--r2)}}.r3{{color:var(--r3)}}.r4{{color:var(--r4)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px}}
.slot{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px;min-width:0}}
.slot header{{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 10px;margin-bottom:8px}}
.hint{{color:var(--muted);font-size:12px}}
.tier{{list-style:none;margin:0;padding:0;display:grid;gap:2px}}
.tier li{{display:flex;gap:10px;align-items:baseline;padding:3px 0;border-bottom:1px dashed var(--line)}}
.tier li:last-child{{border-bottom:0}}
.lv{{flex:none;width:44px;color:var(--muted);font-size:12px;font-variant-numeric:tabular-nums}}
.nm{{flex:1;min-width:0}}
.set{{flex:none;font-size:11px;color:var(--accent);background:var(--soft);border-radius:6px;padding:0 6px}}
.note{{background:var(--soft);border-radius:12px;padding:12px 14px;font-size:13px}}
.stat-chips{{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}}
.stat-chips span{{border:1px solid var(--line);border-radius:6px;padding:0 8px;font-size:12px}}
.tablewrap{{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:14px}}
table{{border-collapse:collapse;width:100%;font-size:13.5px}}
th,td{{text-align:left;padding:8px 12px;border-bottom:1px solid var(--line);white-space:nowrap}}
th{{color:var(--muted);font-weight:500;font-size:12px}}
tr:last-child td{{border-bottom:0}}
td.g{{color:var(--muted)}} td.num{{font-variant-numeric:tabular-nums;text-align:right}}
.plan{{border-style:dashed}}
.plan .row{{font-size:13px;margin-bottom:6px}} .plan .row b{{display:block;font-size:12px;color:var(--muted);font-weight:500}}
.route{{font-size:13px;margin-top:6px}} .route b{{display:block;font-size:12px;color:var(--accent);font-weight:700}}
.badge{{display:inline-block;font-size:11px;font-weight:700;border-radius:6px;padding:1px 8px;background:var(--gold);color:var(--card)}}
</style>
<main class="wrap">
<header>
  <h1>공책 RPG 아이템 도감</h1>
  <p class="lead">지금 게임(index.html)에 들어 있는 장비·보조무기·반지·재료·소모품 전부. 장비는 같은 이름에 희귀도 5단계가 붙고, 전직 후에는 같은 이름 앞에 「심연의」가 붙은 강화판이 나온다.</p>
  <div class="stats"><span>장비 칸 <b>11</b>종</span><span>등급대 <b>10</b>단계 (Lv.1~45)</span><span>희귀도 <b>5</b></span><span>기본 이름 <b>{base}</b>개</span><span>재료 <b>{len(G)*2}</b>종</span><span>소모품 <b>2</b>종</span></div>
</header>

<section>
  <div class="sec-h"><h2>희귀도</h2><p>이름 앞에 붙고, 능력치가 단계마다 15%씩 오른다</p></div>
  <div class="rar">{''.join(f'<span class="{c}">{n}</span>' for n,c in rar)}</div>
</section>

<section>
  <div class="sec-h"><h2>장비</h2><p>Lv는 착용 레벨(노비스 기준, 전직하면 모두 착용). 파란 꼬리표는 세트 이름(효과는 아직 없음)</p></div>
  <div class="grid">{cards}
    <article class="slot"><header><h3>반지 · 5칸</h3><span class="hint">재질 10 × 능력치 6 = 60종</span></header>
      <ol class="tier">{ringrows}</ol>
      <div class="stat-chips">{''.join(f'<span>○○ = {s}</span>' for s in STATS)}</div></article>
  </div>
</section>

<section>
  <div class="sec-h"><h2>보조무기</h2><p>칸 이름은 늘 '보조무기'. 직업·루트에 따라 들어가는 종류가 다르다. 나이트·몽크·시프·닌자·댄서는 ✕</p></div>
  <div class="grid">{subcards}</div>
</section>

<section>
  <div class="sec-h"><h2>심연 장비</h2><p>전직 후에만 드롭</p></div>
  <p class="note">위 장비·보조무기·반지와 같은 이름 앞에 <b>「심연의」</b>가 붙는다 (예: 심연의 강철 몽둥이). 능력치는 약 1.6~1.7배, 착용 조건은 전직 후 직업 Lv. 그림은 기본 장비와 같이 써도 되고, 보라빛 오라 같은 변형으로 구분해도 된다.</p>
</section>

<section>
  <div class="sec-h"><h2>재료</h2><p>몬스터마다 1종, 승리 시 50% 확률로 드롭. 가방 → 재료에서 한 번에 판매</p></div>
  <div class="tablewrap"><table><thead><tr><th>사냥터</th><th>몬스터</th><th>재료</th><th style="text-align:right">1개 판매가</th></tr></thead><tbody>{mats}</tbody></table></div>
</section>

<section>
  <div class="sec-h"><h2>소모품</h2><p>가방 → 소모품에서 구매, 전투 중 아이템으로 사용</p></div>
  <div class="tablewrap"><table><thead><tr><th>이름</th><th>효과</th><th style="text-align:right">가격</th></tr></thead><tbody>
    <tr><td><b>체력 물약</b></td><td>HP 50% 회복</td><td class="num">25G</td></tr>
    <tr><td><b>마나 물약</b></td><td>MP 50% 회복</td><td class="num">25G</td></tr></tbody></table></div>
</section>

<section>
  <div class="sec-h"><h2>직업 장비 <span class="badge">설계만 · 아직 게임에 없음</span></h2><p>design/equipment.json. 전직 후 직업 Lv 1·10·20…90 기준</p></div>
  <div class="grid">{jobs}
    <article class="slot plan"><header><h3>직업 공용 악세서리</h3><span class="hint">전직 후 10단계</span></header>
      <p class="row"><b>망토</b> {" · ".join(e(x) for x in sh['망토'])}</p><p class="row"><b>귀걸이</b> {" · ".join(e(x) for x in sh['귀걸이'])}</p><p class="row"><b>반지</b> {e(sh['반지'])}</p></article>
  </div>
</section>
</main>
'''
open(SP+'items.html','w').write(page)
print(base, len(page))
