window.__balance = (opts={}) => {
  const N = opts.n || 60, out = [];
  if (opts.pw){ for (const k in CLASS_PW) delete CLASS_PW[k]; Object.assign(CLASS_PW, opts.pw); }
  const _r = render, _s = save, _rf = runFoes, _fx = fxPlay, _t = toast;
  render = ()=>{}; save = ()=>{}; runFoes = ()=>{}; fxPlay = ()=>{}; toast = ()=>{};
  const ROUTES = Object.entries(ROUTE).map(([r,o])=>[o.job, r]);
  const VAL = s => { const e = s.e; if (e.k==='dmg') return 3 + (e.all?.5:0); if (e.k==='pas') return ['atk','matk','skill','crit','double','spirit'].includes(e.st) ? 2.5 : ['hp','block','dodge','regen'].includes(e.st) ? 1.8 : e.st==='spd' ? 1.2 : 2; if (e.k==='buff') return 1.6; if (e.k==='heal') return 1.5; if (e.k==='debuff') return 1.2; return .4; };
  function build(j, r, lv, third){
    S.job = j; S.route = lv>=ROUTE_LV || third ? r : null; S.third = !!third; S.lv = lv; S.gender = r==='dancer' ? 'f' : 'm';
    const pts = 98 + 5 + (lv-1)*2 + 40*6 + (third ? 5 + 98*2 : 0), k = JOBS[j].key, w = [.6,.25,.15];
    for (const [s] of STATS) S.stats[s] = 40;
    let left = pts - 240; k.forEach((s,i)=>{ S.stats[s] += Math.round(left*w[i]); });
    S.sk = {}; let sp = lv + (third ? 99 : 0);
    while (sp > 0){ let best = null, bv = -1;
      for (const t of myTrees()) for (const s of TREES[t].list){ if (skLv(s.id) >= s.max || !skReqOk(s)) continue; let v = Math.max(VAL(s), ...TREES[t].list.filter(u=>(u.req||[]).some(([id,l])=>id===s.id && skLv(s.id) < l)).map(u=>VAL(u)*.95)) + (t===S.route?.3:0) + (t.startsWith('t3_')?.5:0) - skLv(s.id)*.02; if (v > bv){ bv = v; best = s; } }
      if (!best) break; S.sk[best.id] = skLv(best.id) + 1; sp--; }
    const band = third ? 9 : clamp(Math.floor((lv-1)/10), 0, 9);
    for (const sl of [...SLOT_ORDER, ...RING_SLOTS]) S.equip[sl] = null;
    for (const sl of ['weapon','sub','helm','top','bottom','shoes','cape','necklace','earring']){ const it = makeItem(sl, band, 1, true); if (third) it.t3 = true; if (canWear(itemInfo(it), it)) S.equip[sl] = it; }
    for (const sl of RING_SLOTS.slice(0,2)){ const it = makeItem('ring', band, 1, true); it.st = k[0]; if (third) it.t3 = true; S.equip[sl] = it; }
  }
  function pickAction(){
    const alive = B.foes.map((f,i)=>i).filter(i=>B.foes[i].hp>0), acts = learnedActive();
    const tgt = alive.slice().sort((a,b)=>B.foes[a].hp-B.foes[b].hp)[0]; B.target = tgt;
    const heal = acts.filter(s=>s.kind==='heal' && s.mp<=S.mp).sort((a,b)=>b.pct-a.pct)[0];
    if (heal && S.hp < hpMax()*.4) return ['skill', heal];
    if (B.round===1 && B.icons.length===2){ const bu = acts.filter(s=>s.kind==='buff' && ['atk','crit','double','spd','matk','skill'].includes(s.st) && !B.buffs[s.st] && s.mp<=S.mp)[0]; if (bu && alive.length>=2) return ['skill', bu]; }
    const score = s => { const ts = s.all ? alive : [tgt]; let v = 0; for (const t of ts){ const f = B.foes[t]; v += s.mult * (s.hits||1) * (f.weak.includes(s.attr)?1.5:f.resist.includes(s.attr)?.5:1) * Math.min(1, f.hp / Math.max(1, (s.magic?matk():atk())*s.mult*(s.hits||1))) ; } return v * (s.magic ? matk()/atk() : 1) * (1+pas('skill')); };
    const attack = {kind:'dmg', mult:1, hits:1 + (S.route==='dagger' && S.equip.sub && S.equip.sub.kind==='dagger' ? 1 : 0), attr:B.enchant ? B.enchant.attr : job().attr, all:false, magic:false};
    let best = null, bv = score(attack) * (1 + pas('double'));
    for (const s of acts) if (s.kind==='dmg' && (s.mp <= S.mp || (s.magic && B.stk.free))){ const v = score(s); if (v > bv*1.05){ bv = v; best = s; } }
    return best ? ['skill', best] : ['attack'];
  }
  function fight(g){
    S.hp = hpMax(); S.mp = mpMax(); startBattle(g, true); clearTimeout(foeTimer);
    for (const f of B.foes){ f.hp = f.max = Math.round(f.hp*(opts.hpMul||1)); f.atk = Math.round(f.atk*(opts.atkMul||1)); }
    let steps = 0, acts = 0;
    while (!B.over && steps++ < 400){
      if (B.turnFoe != null){ foeAct(B.turnFoe); continue; }
      if (B.queue[0]==='me'){ acts++; const [k,a] = pickAction(); const before = JSON.stringify([B.icons, B.queue.length, S.mp]); playerAction(k, a); if (JSON.stringify([B.icons, B.queue.length, S.mp])===before) playerAction('attack'); continue; }
      advance();
    }
    const o = {win: !!(B.over && B.over.win), rounds: acts, hpLeft: S.hp/hpMax(), mpUsed: 1 - S.mp/mpMax()}; B = null; return o;
  }
  const levels = opts.levels || [[20,0],[40,0],[70,0],[99,0],[50,1]];
  for (const [j,r] of ROUTES) for (const [lv,third] of levels){
    if (lv < ROUTE_LV && !third && ROUTES.findIndex(x=>x[0]===j) !== ROUTES.findIndex(x=>x[1]===r)) continue;  // pre-route rows: one per job
    build(j, r, lv, third);
    const g = clamp(Math.floor((lv-1)/10), 0, 9); let w=0, rd=0, hp=0, mp=0;
    for (let i=0;i<N;i++){ const o = fight(g); if (o.win){ w++; rd += o.rounds; hp += o.hpLeft; } mp += o.mpUsed; }
    out.push({job:j, route: lv>=ROUTE_LV||third ? r : '-', name: jobName(), lv: (third?'3차 ':'')+lv, win: Math.round(w/N*100), rounds: w? +(rd/w).toFixed(2):0, hpLeft: w? Math.round(hp/w*100):0, mp: Math.round(mp/N*100), atk: atk(), matk: matk(), hpMax: hpMax()});
  }
  render = _r; save = _s; runFoes = _rf; fxPlay = _fx; toast = _t;
  return out;
};
