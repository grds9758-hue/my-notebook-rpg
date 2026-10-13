window.__audit = () => {
  const out = [], bad = [];
  const combos = [['novice',null],['warrior','greatsword'],['warrior','shield'],['warrior','rider'],['archer','trapper'],['archer','bowman'],['thief','dagger'],['thief','shuriken'],['thief','dancer'],['healer','priest'],['healer','monk'],['mage','wizard'],['mage','elementalist']];
  for (const [j,r] of combos){
    S.job = j; S.route = r; S.lv = j==='novice'?50:99; S.sk = {};
    for (const t of myTrees()) for (const sk of TREES[t].list) S.sk[sk.id] = sk.max;
    startBattle(0,false); clearTimeout(foeTimer);
    for (const t of myTrees()) for (const sk of TREES[t].list) if (sk.e.k==='buff'){ const o = skillAt(sk, sk.max); const ob = B.buffs[o.st]; B.buffs[o.st] = {v:Math.max(o.v, ob?ob.v:0), t:3}; }
    B.stk = {fury:5, aim:5, aimT:0, sphere:sphereMax(), over:5, free:true};
    const v = {crit:crit(), critDmg:critDmg(), miss:missRate(), dodge:dodgeRate(), block:Math.min(.5,pas('block')), dbl:pas('double'), spirit:pas('spirit'), regen:regenRate(), skill:pas('skill'), atk:atk(), matk:matk(), def:def(), hp:hpMax(), mp:mpMax(), spd:spd()};
    out.push(`${j}/${r}: crit ${v.crit}% critDmg ${v.critDmg.toFixed(2)} miss ${(v.miss*100).toFixed(1)}% dodge ${(v.dodge*100).toFixed(0)}% block ${(v.block*100).toFixed(0)}% double ${(v.dbl*100).toFixed(0)}% spirit ${(v.spirit*100).toFixed(0)}% regen ${(v.regen*100).toFixed(1)}% atk ${v.atk} matk ${v.matk} def ${v.def} hp ${v.hp}`);
    for (const [k,x] of Object.entries(v)) if (!Number.isFinite(x) || x < 0) bad.push(`${j}/${r} ${k}=${x}`);
    if (v.crit > 100) bad.push(`${j}/${r} crit>100`); if (v.dodge > .4) bad.push('dodge'); if (v.regen > .1) bad.push('regen');
    for (const t of myTrees()) for (const sk of TREES[t].list){
      let prev = null;
      for (let lv=1; lv<=sk.max; lv++){ const o = skillAt(sk, lv), d = skDesc(sk, lv);
        if (/NaN|undefined|Infinity/.test(d)) bad.push(`${sk.id} lv${lv} desc: ${d}`);
        if (o.mp < 0 || !Number.isFinite(o.mp)) bad.push(`${sk.id} mp ${o.mp}`);
        const val = o.mult ?? o.pct ?? o.v; if (prev!=null && val!=null && val < prev - 1e-9) bad.push(`${sk.id} goes down at lv${lv}`); prev = val; }
      for (const [id,l] of (sk.req||[])){ if (!SKILL[id]) bad.push(`${sk.id} req missing ${id}`); else { if (l > SKILL[id].max) bad.push(`${sk.id} req ${id} Lv${l} > max ${SKILL[id].max}`); if (SKILL[id].tree !== sk.tree) bad.push(`${sk.id} req other tree`); } }
    }
    const f = B.foes[0]; f.hp = f.max = 1e9; const r1 = hitFoe(f, job().attr, 1, false); if (!Number.isFinite(r1.dmg) || r1.dmg < 0) bad.push(`${j} dmg ${r1.dmg}`);
    B = null;
  }
  S.job='healer'; S.route='priest'; S.lv=50; S.sk={ac_heal:3, ac_bless:10, pr_sanc:3, pr_impos:1}; S.mp=1e6;
  startBattle(0,false); clearTimeout(foeTimer);
  const use = id => { B.queue=['me',0]; B.icons=['f','f']; B.over=null; playerAction('skill', learnedActive().find(x=>x.id===id)); clearTimeout(foeTimer); };
  use('ac_bless'); const strong = B.buffs.atk.v; use('pr_impos');
  out.push(`buff merge: bless ${strong.toFixed(2)} then weaker impositio -> ${B.buffs.atk.v.toFixed(2)} (${B.buffs.atk.v===strong?'kept stronger':'REPLACED'})`);
  if (B.buffs.atk.v !== strong) bad.push('buff merge');
  B = null;
  return {out, bad};
};
window.__trees = () => { const ids = {}, out = []; for (const [k,T] of Object.entries(TREES)){ for (const s of T.list){ if (ids[s.id]) out.push('DUP '+s.id); ids[s.id]=1; } const L = treeLayout(T); out.push(`${k}: ${T.list.length}개 · ${L.cols}열 ${L.rows}줄 · 총 ${T.list.reduce((a,s)=>a+s.max,0)}포인트`); } return out; };
