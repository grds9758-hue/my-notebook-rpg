// 계정 서버: Cloudflare Pages Functions + D1 (바인딩 이름 DB).
// /api/ping · /api/signup · /api/login · /api/logout · /api/save?slot=0~3 (GET 불러오기, PUT 저장, DELETE 지우기) · /api/saves (캐릭터 칸 목록)
// /api/me · /api/notice · /api/inquiry(POST)·/api/inquiries · /api/grants(GET)·/api/grants/ack — 문의, 운영자 우편(지급·조정), 공지
// /api/admin/* (운영자 전용): stats · users · chars · user(정지·해제·비번 초기화·강제 로그아웃·삭제) · grant · inquiries · answer · notice · logs
// 비밀번호는 PBKDF2 해시로만 저장한다. 로그인하면 30일짜리 토큰을 준다.
// 운영자: Cloudflare Pages 환경 변수 ADMIN_IDS(쉼표로, 기본 'gm')에 있는 아이디. 이 아이디는 아무나 가입 못 하고,
//        가입할 때 환경 변수 ADMIN_CODE와 같은 '운영자 코드'를 넣어야 만들어진다(ADMIN_CODE가 없으면 못 만듦).

const SCHEMA = [
  'CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, salt TEXT NOT NULL, hash TEXT NOT NULL, created INTEGER NOT NULL)',
  'CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, id TEXT NOT NULL, exp INTEGER NOT NULL)',
  'CREATE TABLE IF NOT EXISTS saves (id TEXT PRIMARY KEY, data TEXT NOT NULL, at INTEGER NOT NULL, name TEXT, lv INTEGER)',
  'CREATE TABLE IF NOT EXISTS tries (key TEXT PRIMARY KEY, n INTEGER NOT NULL, until INTEGER NOT NULL)',
  'CREATE TABLE IF NOT EXISTS bans (id TEXT PRIMARY KEY, reason TEXT, at INTEGER NOT NULL, until INTEGER NOT NULL, by TEXT)',
  'CREATE TABLE IF NOT EXISTS inquiries (n INTEGER PRIMARY KEY AUTOINCREMENT, uid TEXT NOT NULL, cat TEXT, title TEXT, body TEXT, at INTEGER NOT NULL, answer TEXT, ans_at INTEGER, ans_by TEXT)',
  'CREATE TABLE IF NOT EXISTS grants (n INTEGER PRIMARY KEY AUTOINCREMENT, uid TEXT NOT NULL, slot INTEGER NOT NULL, payload TEXT NOT NULL, at INTEGER NOT NULL, by TEXT, done INTEGER NOT NULL DEFAULT 0)',
  'CREATE TABLE IF NOT EXISTS notice (k TEXT PRIMARY KEY, text TEXT, at INTEGER)',
  'CREATE TABLE IF NOT EXISTS gmlog (n INTEGER PRIMARY KEY AUTOINCREMENT, by TEXT, act TEXT, target TEXT, at INTEGER NOT NULL)',
  // ----- 멀티: 캐릭터 키 pk = '아이디:칸'
  'CREATE TABLE IF NOT EXISTS presence (pk TEXT PRIMARY KEY, uid TEXT NOT NULL, name TEXT, card TEXT, lv INTEGER, elv INTEGER, cp INTEGER, dex INTEGER, job TEXT, place TEXT, at INTEGER NOT NULL)',
  'CREATE TABLE IF NOT EXISTS chat (n INTEGER PRIMARY KEY AUTOINCREMENT, ch TEXT NOT NULL, pk TEXT, name TEXT, text TEXT NOT NULL, at INTEGER NOT NULL, gm INTEGER DEFAULT 0)',
  'CREATE INDEX IF NOT EXISTS chat_ch ON chat (ch, n)',
  'CREATE TABLE IF NOT EXISTS friends (a TEXT NOT NULL, b TEXT NOT NULL, st TEXT NOT NULL, at INTEGER NOT NULL, PRIMARY KEY (a, b))',
  'CREATE TABLE IF NOT EXISTS cheers (a TEXT NOT NULL, b TEXT NOT NULL, day TEXT NOT NULL, PRIMARY KEY (a, b, day))',
  'CREATE TABLE IF NOT EXISTS mutes (id TEXT PRIMARY KEY, until INTEGER NOT NULL, reason TEXT)',
  'CREATE TABLE IF NOT EXISTS guilds (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, master TEXT NOT NULL, notice TEXT, join_mode TEXT DEFAULT \'open\', lv INTEGER DEFAULT 1, exp INTEGER DEFAULT 0, mark TEXT, created INTEGER NOT NULL)',
  'CREATE TABLE IF NOT EXISTS gmembers (pk TEXT PRIMARY KEY, gid INTEGER NOT NULL, rank TEXT NOT NULL, joined INTEGER NOT NULL, contrib INTEGER DEFAULT 0, att TEXT)',
  'CREATE TABLE IF NOT EXISTS gapps (pk TEXT NOT NULL, gid INTEGER NOT NULL, at INTEGER NOT NULL, PRIMARY KEY (pk, gid))',
  'CREATE TABLE IF NOT EXISTS market (n INTEGER PRIMARY KEY AUTOINCREMENT, seller TEXT NOT NULL, sname TEXT, item TEXT NOT NULL, kind TEXT, name TEXT, slot TEXT, rar INTEGER, band INTEGER, qty INTEGER DEFAULT 1, price INTEGER NOT NULL, at INTEGER NOT NULL, st TEXT NOT NULL DEFAULT \'on\', buyer TEXT, done_at INTEGER)',
  'CREATE INDEX IF NOT EXISTS market_st ON market (st, at)',
];
const ITER = 20000;               // 무료 요금제 CPU 한도 안에서 돌도록
const SESSION_MS = 30 * 864e5;    // 30일
const MAX_SAVE = 900 * 1024;      // 저장 데이터 최대 900KB
const SLOTS = 4;                   // 계정마다 캐릭터 칸 수
const ID_RE = /^[a-z0-9_-]{5,20}$/;          // 가입: 5~20자 영문 소문자·숫자·_·- (네이버식)
const ID_LOGIN_RE = /^[a-z0-9_-]{4,20}$/;    // 로그인: 예전 4자 아이디도 받음
const pwOk = pw => pw.length >= 8 && pw.length <= 16 && [/[A-Za-z]/, /[0-9]/, /[^A-Za-z0-9]/].filter(r => r.test(pw)).length >= 2;  // 8~16자, 영문·숫자·특수문자 중 2가지 이상

const json = (o, status = 200) => new Response(JSON.stringify(o), {status, headers: {'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store'}});
const hex = b => [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, '0')).join('');
const rand = n => hex(crypto.getRandomValues(new Uint8Array(n)));

async function pbkdf2(pw, salt){
  const key = await crypto.subtle.importKey('raw', new TextEncoder().encode(pw), 'PBKDF2', false, ['deriveBits']);
  const bits = await crypto.subtle.deriveBits({name: 'PBKDF2', hash: 'SHA-256', salt: new TextEncoder().encode(salt), iterations: ITER}, key, 256);
  return hex(bits);
}
function same(a, b){ if (a.length !== b.length) return false; let d = 0; for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i); return d === 0; }

let ready = false;
async function init(db){ if (ready) return; await db.batch(SCHEMA.map(q => db.prepare(q))); ready = true; }

// 같은 IP·아이디로 비밀번호를 너무 많이 틀리면 10분 쉬게 한다
async function tooMany(db, key){ const r = await db.prepare('SELECT n, until FROM tries WHERE key = ?').bind(key).first(); return r && r.n >= 8 && r.until > Date.now(); }
async function failed(db, key){ const now = Date.now(); await db.prepare('INSERT INTO tries (key, n, until) VALUES (?, 1, ?) ON CONFLICT(key) DO UPDATE SET n = CASE WHEN until < ? THEN 1 ELSE n + 1 END, until = ?').bind(key, now + 6e5, now, now + 6e5).run(); }

async function banOf(db, id){
  const b = await db.prepare('SELECT reason, until FROM bans WHERE id = ?').bind(id).first();
  return b && (!b.until || b.until > Date.now()) ? b : null;
}
const banMsg = b => `이용이 정지된 계정이에요${b.reason ? ` (사유: ${b.reason})` : ''}${b.until ? ` · ${new Date(b.until).toLocaleDateString('ko-KR')}까지` : ''}`;
async function session(db, req){
  const t = (req.headers.get('Authorization') || '').replace(/^Bearer\s+/, '');
  if (!t) return null;
  const r = await db.prepare('SELECT id, exp FROM sessions WHERE token = ?').bind(t).first();
  if (!r || r.exp < Date.now()) return null;
  return {id: r.id, token: t};
}
async function newSession(db, id){
  const token = rand(32);
  await db.prepare('INSERT INTO sessions (token, id, exp) VALUES (?, ?, ?)').bind(token, id, Date.now() + SESSION_MS).run();
  return token;
}

export async function onRequest({request, env, params}){
  const db = env.DB;
  const path = [].concat(params.path || []).join('/');
  if (path === 'ping') return json({ok: !!db});
  if (!db) return json({error: '서버 DB가 아직 연결되지 않았어요.'}, 503);
  await init(db);
  const m = request.method, url = new URL(request.url);
  let body = {};
  if (m === 'POST' || m === 'PUT'){ try { body = await request.json(); } catch(e){ return json({error: '잘못된 요청이에요.'}, 400); } }

  const ADMINS = String(env.ADMIN_IDS || 'gm').split(',').map(x => x.trim().toLowerCase()).filter(Boolean);
  const isAdmin = id => ADMINS.includes(id);
  if (path === 'signup' && m === 'POST'){
    const id = String(body.id || '').toLowerCase(), pw = String(body.pw || '');
    if (isAdmin(id) || /^(admin|gm|operator|master|root|운영자)[0-9_-]*$/.test(id)){
      if (!isAdmin(id) || !env.ADMIN_CODE || String(body.code || '') !== String(env.ADMIN_CODE)) return json({error: '쓸 수 없는 아이디예요.'}, 400);
    } else if (!ID_RE.test(id)) return json({error: '아이디는 5~20자의 영문 소문자, 숫자, 특수기호(_, -)만 쓸 수 있어요.'}, 400);
    if (!pwOk(pw)) return json({error: '비밀번호는 8~16자로, 영문·숫자·특수문자 중 2가지 이상을 섞어 주세요.'}, 400);
    const key = id.toLowerCase();
    if (await db.prepare('SELECT 1 FROM users WHERE id = ?').bind(key).first()) return json({error: '이미 쓰는 아이디예요.'}, 409);
    const salt = rand(16), hash = await pbkdf2(pw, salt);
    await db.prepare('INSERT INTO users (id, salt, hash, created) VALUES (?, ?, ?, ?)').bind(key, salt, hash, Date.now()).run();
    return json({id: key, token: await newSession(db, key), admin: isAdmin(key)});
  }
  if (path === 'login' && m === 'POST'){
    const id = String(body.id || '').toLowerCase(), pw = String(body.pw || '');
    const ip = request.headers.get('CF-Connecting-IP') || '?', tk = `${ip}|${id}`;
    if (await tooMany(db, tk)) return json({error: '비밀번호를 너무 많이 틀렸어요. 10분 뒤에 다시 해 주세요.'}, 429);
    const u = (ID_LOGIN_RE.test(id) || isAdmin(id)) && pw.length <= 64 ? await db.prepare('SELECT salt, hash FROM users WHERE id = ?').bind(id).first() : null;
    if (!u || !same(await pbkdf2(pw, u.salt), u.hash)){ await failed(db, tk); return json({error: '아이디 또는 비밀번호가 틀려요.'}, 401); }
    const ban = await banOf(db, id); if (ban) return json({error: banMsg(ban)}, 403);
    await db.prepare('DELETE FROM tries WHERE key = ?').bind(tk).run();
    await db.prepare('DELETE FROM sessions WHERE id = ? AND exp < ?').bind(id, Date.now()).run();
    return json({id, token: await newSession(db, id), admin: isAdmin(id)});
  }
  if (path === 'notice' && m === 'GET'){ const r = await db.prepare("SELECT text, at FROM notice WHERE k = 'main'").first(); return json(r || {text: ''}); }

  const s = await session(db, request);
  if (!s) return json({error: '다시 로그인해 주세요.'}, 401);
  { const ban = await banOf(db, s.id); if (ban){ await db.prepare('DELETE FROM sessions WHERE id = ?').bind(s.id).run(); return json({error: banMsg(ban)}, 401); } }
  if (path === 'me' && m === 'GET') return json({id: s.id, admin: isAdmin(s.id)});
  if (path === 'logout' && m === 'POST'){ await db.prepare('DELETE FROM sessions WHERE token = ?').bind(s.token).run(); return json({ok: true}); }
  // 캐릭터 칸 0~3: 0번은 예전처럼 id 그대로, 1~3번은 'id#칸'
  const slotOf = v => { const n = parseInt(v, 10); return n >= 1 && n < SLOTS ? n : 0; };
  const rowId = n => n ? `${s.id}#${n}` : s.id;
  const slot = slotOf(m === 'PUT' ? body.slot : url.searchParams.get('slot'));
  if (path === 'saves' && m === 'GET'){
    const ids = Array.from({length: SLOTS}, (_, i) => rowId(i));
    const r = await db.prepare(`SELECT id, data, at FROM saves WHERE id IN (${ids.map(() => '?').join(',')})`).bind(...ids).all();
    const list = (r.results || []).map(x => ({slot: ids.indexOf(x.id), data: x.data, at: x.at}));
    return json({list});
  }
  if (path === 'save' && m === 'GET'){
    const r = await db.prepare('SELECT data, at FROM saves WHERE id = ?').bind(rowId(slot)).first();
    return json(r ? {data: r.data, at: r.at} : {data: null});
  }
  if (path === 'save' && m === 'DELETE'){
    await db.prepare('DELETE FROM saves WHERE id = ?').bind(rowId(slot)).run();
    return json({ok: true});
  }
  if (path === 'save' && m === 'PUT'){
    const data = String(body.data || '');
    if (!data || data.length > MAX_SAVE) return json({error: '저장 데이터가 너무 커요.'}, 413);
    try { JSON.parse(data); } catch(e){ return json({error: '잘못된 저장 데이터예요.'}, 400); }
    await db.prepare('INSERT INTO saves (id, data, at, name, lv) VALUES (?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET data = excluded.data, at = excluded.at, name = excluded.name, lv = excluded.lv')
      .bind(rowId(slot), data, +body.at || Date.now(), String(body.name || '').slice(0, 24), +body.lv || 1).run();
    return json({ok: true});
  }
  // ----- 문의
  if (path === 'inquiry' && m === 'POST'){
    const title = String(body.title || '').trim().slice(0, 40), text = String(body.body || '').trim().slice(0, 1000), cat = String(body.cat || '기타').slice(0, 10);
    if (!title || !text) return json({error: '제목과 내용을 적어 주세요.'}, 400);
    const today = await db.prepare('SELECT COUNT(*) AS c FROM inquiries WHERE uid = ? AND at > ?').bind(s.id, Date.now() - 864e5).first();
    if (today && today.c >= 10) return json({error: '문의는 하루 10번까지 보낼 수 있어요.'}, 429);
    await db.prepare('INSERT INTO inquiries (uid, cat, title, body, at) VALUES (?, ?, ?, ?, ?)').bind(s.id, cat, title, text, Date.now()).run();
    return json({ok: true});
  }
  if (path === 'inquiries' && m === 'GET'){
    const r = await db.prepare('SELECT n, cat, title, body, at, answer, ans_at FROM inquiries WHERE uid = ? ORDER BY n DESC LIMIT 30').bind(s.id).all();
    return json({list: r.results || []});
  }
  // ----- 운영자 우편(지급·조정): 캐릭터가 접속하면 받아서 적용하고 ack
  if (path === 'grants' && m === 'GET'){
    const r = await db.prepare('SELECT n, slot, payload, at FROM grants WHERE uid = ? AND slot = ? AND done = 0 ORDER BY n').bind(s.id, slot).all();
    return json({list: r.results || []});
  }
  if (path === 'grants/ack' && m === 'POST'){
    const ns = [].concat(body.ids || []).map(x => +x).filter(Boolean).slice(0, 50);
    for (const n of ns) await db.prepare('UPDATE grants SET done = 1 WHERE n = ? AND uid = ?').bind(n, s.id).run();
    return json({ok: true});
  }


  // ======================= 멀티 (접속자·채팅·친구·랭킹·길드·거래소) =======================
  const now = Date.now(), day = new Date(now + 9 * 36e5).toISOString().slice(0, 10);  // 한국 날짜
  const mySlot = slotOf(m === 'GET' ? url.searchParams.get('slot') : body.slot), me = `${s.id}:${mySlot}`;
  const pkOk = v => /^[a-z0-9_-]{2,20}:[0-3]$/.test(String(v || ''));
  const uidOf = pk => String(pk).split(':')[0], slotOfPk = pk => +String(pk).split(':')[1];
  const ONLINE_MS = 3 * 60e3;
  const one = (q, ...a) => db.prepare(q).bind(...a).first();
  const all = async (q, ...a) => ((await db.prepare(q).bind(...a).all()).results || []);
  const run = (q, ...a) => db.prepare(q).bind(...a).run();
  const mail = (pk, payload) => run('INSERT INTO grants (uid, slot, payload, at, by) VALUES (?, ?, ?, ?, ?)', uidOf(pk), slotOfPk(pk), JSON.stringify(payload), now, 'system');
  const nameOf = async pk => ((await one('SELECT name FROM presence WHERE pk = ?', pk)) || {}).name || uidOf(pk);
  const myGuild = async (pk = me) => one('SELECT g.*, m.rank, m.contrib, m.att FROM gmembers m JOIN guilds g ON g.id = m.gid WHERE m.pk = ?', pk);
  const G_NEED = lv => 200 * lv * lv, G_MAX = 10, gCap = lv => 10 + lv * 2;
  async function gAddExp(gid, n){
    const g = await one('SELECT lv, exp FROM guilds WHERE id = ?', gid); if (!g) return;
    let lv = g.lv, exp = g.exp + n; while (lv < G_MAX && exp >= G_NEED(lv)){ exp -= G_NEED(lv); lv++; }
    if (lv >= G_MAX) exp = Math.min(exp, G_NEED(G_MAX));
    await run('UPDATE guilds SET lv = ?, exp = ? WHERE id = ?', lv, exp, gid);
    if (lv > g.lv) await run('INSERT INTO chat (ch, pk, name, text, at) VALUES (?, ?, ?, ?, ?)', 'g:' + gid, '', '길드', `길드 레벨이 ${lv}이 되었어요! (경험치·골드 +${lv}%)`, now);
  }
  const gInfo = g => g && {id: g.id, name: g.name, lv: g.lv, exp: g.exp, need: G_NEED(g.lv), max: g.lv >= G_MAX, notice: g.notice || '', join: g.join_mode, mark: g.mark || '', rank: g.rank, contrib: g.contrib || 0, attended: g.att === day, cap: gCap(g.lv), bonus: g.lv};

  // 접속 신호 (1분마다): 내 캐릭터 카드 갱신 + 길드·안 읽은 귓속말 알림
  if (path === 'beat' && m === 'POST'){
    const c = body.card || {}, card = JSON.stringify(c).slice(0, 4000);
    await run('INSERT INTO presence (pk, uid, name, card, lv, elv, cp, dex, job, place, at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(pk) DO UPDATE SET name = excluded.name, card = excluded.card, lv = excluded.lv, elv = excluded.elv, cp = excluded.cp, dex = excluded.dex, job = excluded.job, place = excluded.place, at = excluded.at',
      me, s.id, String(c.name || '').slice(0, 16), card, +c.lv || 1, +c.elv || 1, +c.cp || 0, +c.dex || 0, String(c.job || '').slice(0, 20), String(body.place || '').slice(0, 20), now);
    const online = await one('SELECT COUNT(*) AS c FROM presence WHERE at > ?', now - ONLINE_MS);
    const g = await myGuild(); const freq = await one("SELECT COUNT(*) AS c FROM friends WHERE b = ? AND st = 'req'", me);
    return json({online: online.c, guild: gInfo(g), freq: freq.c});
  }
  if (path === 'online' && m === 'GET'){
    const r = await all('SELECT p.pk, p.name, p.lv, p.job, p.place, p.card, g.name AS guild FROM presence p LEFT JOIN gmembers gm ON gm.pk = p.pk LEFT JOIN guilds g ON g.id = gm.gid WHERE p.at > ? ORDER BY p.elv DESC LIMIT 100', now - ONLINE_MS);
    return json({list: r.map(x => { let c = {}; try { c = JSON.parse(x.card); } catch(e){} return {pk: x.pk, name: x.name, lv: x.lv, job: x.job, place: x.place, guild: x.guild, code: c.code, gm: isAdmin(uidOf(x.pk))}; })});
  }
  if (path === 'player' && m === 'GET'){
    const pk = url.searchParams.get('pk'); if (!pkOk(pk)) return json({error: '없는 캐릭터예요.'}, 404);
    const p = await one('SELECT * FROM presence WHERE pk = ?', pk); if (!p) return json({error: '아직 접속한 적이 없는 캐릭터예요.'}, 404);
    const g = await myGuild(pk), f = await one('SELECT a, st FROM friends WHERE (a = ? AND b = ?) OR (a = ? AND b = ?)', me, pk, pk, me);
    let card = {}; try { card = JSON.parse(p.card); } catch(e){}
    return json({pk, name: p.name, card, online: p.at > now - ONLINE_MS, at: p.at, place: p.place, guild: g ? {id: g.id, name: g.name, lv: g.lv, rank: g.rank} : null,
      friend: f ? (f.st === 'ok' ? 'ok' : f.a === me ? 'sent' : 'got') : null, me: pk === me, sameUser: uidOf(pk) === s.id, gm: isAdmin(uidOf(pk))});
  }
  // ----- 채팅: all(전체) · g:길드 · w:귓속말 · sys(알림)
  if (path === 'chat' && m === 'GET'){
    const since = Math.max(0, +url.searchParams.get('since') || 0), g = await myGuild();
    const chs = ['all', 'sys']; if (g) chs.push('g:' + g.id);
    const r = await all(`SELECT n, ch, pk, name, text, at, gm FROM chat WHERE n > ? AND (ch IN (${chs.map(() => '?').join(',')}) OR (ch LIKE 'w:%' AND (pk = ? OR ch LIKE ?))) ORDER BY n DESC LIMIT 60`, since, ...chs, me, `w:${me}|%`);
    return json({list: r.reverse().map(x => ({...x, ch: x.ch.startsWith('g:') ? 'guild' : x.ch.startsWith('w:') ? 'w' : x.ch, to: x.ch.startsWith('w:') ? x.ch.slice(2).split('|')[0] : undefined}))});
  }
  if (path === 'chat' && m === 'POST'){
    const mu = await one('SELECT until, reason FROM mutes WHERE id = ?', s.id);
    if (mu && mu.until > now) return json({error: `채팅이 금지됐어요${mu.reason ? ` (사유: ${mu.reason})` : ''}`}, 403);
    const last = await one('SELECT at FROM chat WHERE pk = ? ORDER BY n DESC LIMIT 1', me);
    if (last && now - last.at < 1500) return json({error: '조금 천천히 말해 주세요.'}, 429);
    const name = await nameOf(me); let ch = String(body.ch || 'all'), text = String(body.text || '').replace(/\s+/g, ' ').trim().slice(0, 120);
    if (ch === 'sys'){  // 서버가 정한 틀로만 (아무 말이나 알림으로 못 보내게)
      const T = {legend: `✨ ${name}님이 [${String(body.item || '').slice(0, 30)}]을(를) 얻었어요!`, job: `🎉 ${name}님이 ${String(body.job || '').slice(0, 20)}(으)로 전직했어요!`, lvmax: `👑 ${name}님이 Lv.${+body.lv || 99}에 도달했어요!`, rare: `🌟 ${name}님이 희귀 몬스터 ${String(body.mon || '').slice(0, 20)}을(를) 쓰러뜨렸어요!`};
      if (!T[body.kind]) return json({error: '모르는 알림이에요.'}, 400); text = T[body.kind];
    } else if (!text) return json({error: '할 말을 적어 주세요.'}, 400);
    if (ch === 'guild'){ const g = await myGuild(); if (!g) return json({error: '길드에 들어가 있지 않아요.'}, 400); ch = 'g:' + g.id; }
    else if (ch === 'w'){ const to = String(body.to || ''); if (!pkOk(to) || !(await one('SELECT 1 FROM presence WHERE pk = ?', to))) return json({error: '없는 캐릭터예요.'}, 404); ch = `w:${to}|${me}`; }
    else if (ch !== 'sys') ch = 'all';
    await run('INSERT INTO chat (ch, pk, name, text, at, gm) VALUES (?, ?, ?, ?, ?, ?)', ch, me, name, text, now, isAdmin(s.id) ? 1 : 0);
    if (Math.random() < .03) await run('DELETE FROM chat WHERE at < ?', now - 3 * 864e5);  // 3일 지난 채팅 정리
    return json({ok: true});
  }
  // ----- 랭킹
  if (path === 'rank' && m === 'GET'){
    const by = {lv: 'elv', cp: 'cp', dex: 'dex'}[url.searchParams.get('by')] || 'elv', job = String(url.searchParams.get('job') || '');
    const w = job ? 'WHERE job = ?' : '', a = job ? [job] : [];
    const r = await all(`SELECT p.pk, p.name, p.lv, p.job, p.cp, p.dex, p.elv, p.at, g.name AS guild FROM presence p LEFT JOIN gmembers gm ON gm.pk = p.pk LEFT JOIN guilds g ON g.id = gm.gid ${w} ORDER BY p.${by} DESC, p.lv DESC LIMIT 50`, ...a);
    const mine = await one(`SELECT ${by} AS v FROM presence WHERE pk = ?`, me);
    const myRank = mine ? ((await one(`SELECT COUNT(*) AS c FROM presence ${w ? w + ' AND' : 'WHERE'} ${by} > ?`, ...a, mine.v)).c + 1) : null;
    const gr = await all('SELECT g.id, g.name, g.lv, g.exp, (SELECT COUNT(*) FROM gmembers WHERE gid = g.id) AS n FROM guilds g ORDER BY g.lv DESC, g.exp DESC LIMIT 20');
    return json({list: r.map(x => ({...x, online: x.at > now - ONLINE_MS})), myRank, guilds: gr});
  }
  // ----- 친구 (캐릭터끼리)
  if (path === 'friends' && m === 'GET'){
    const r = await all("SELECT f.a, f.b, f.st, p.name, p.lv, p.job, p.at, p.place FROM friends f JOIN presence p ON p.pk = CASE WHEN f.a = ? THEN f.b ELSE f.a END WHERE f.a = ? OR f.b = ? ORDER BY p.at DESC", me, me, me);
    const ch = await all('SELECT b FROM cheers WHERE a = ? AND day = ?', me, day);
    return json({list: r.map(x => { const pk = x.a === me ? x.b : x.a; return {pk, name: x.name, lv: x.lv, job: x.job, place: x.place, online: x.at > now - ONLINE_MS, at: x.at, st: x.st === 'ok' ? 'ok' : x.a === me ? 'sent' : 'got', cheered: ch.some(c => c.b === pk)}; })});
  }
  if (path === 'friend' && m === 'POST'){
    const to = String(body.to || ''), act = String(body.act || '');
    if (!pkOk(to) || to === me) return json({error: '친구로 할 수 없어요.'}, 400);
    if (uidOf(to) === s.id) return json({error: '내 다른 캐릭터예요.'}, 400);
    const f = await one('SELECT a, b, st FROM friends WHERE (a = ? AND b = ?) OR (a = ? AND b = ?)', me, to, to, me);
    if (act === 'req'){
      if (f) return json({error: f.st === 'ok' ? '이미 친구예요.' : '이미 신청했거나 받은 신청이 있어요.'}, 400);
      const n = await one("SELECT COUNT(*) AS c FROM friends WHERE (a = ? OR b = ?) AND st = 'ok'", me, me); if (n.c >= 50) return json({error: '친구는 50명까지예요.'}, 400);
      await run("INSERT INTO friends (a, b, st, at) VALUES (?, ?, 'req', ?)", me, to, now);
      await run('INSERT INTO chat (ch, pk, name, text, at) VALUES (?, ?, ?, ?, ?)', `w:${to}|${me}`, me, await nameOf(me), '(친구 신청을 보냈어요. 친구 탭에서 받아 주세요!)', now);
    } else if (act === 'accept'){ if (!f || f.st !== 'req' || f.b !== me) return json({error: '받은 신청이 없어요.'}, 400); await run("UPDATE friends SET st = 'ok', at = ? WHERE a = ? AND b = ?", now, to, me); }
    else if (act === 'del'){ await run('DELETE FROM friends WHERE (a = ? AND b = ?) OR (a = ? AND b = ?)', me, to, to, me); }
    else if (act === 'cheer'){  // 하루 한 번 응원: 둘 다 작은 선물
      if (!f || f.st !== 'ok') return json({error: '친구에게만 응원할 수 있어요.'}, 400);
      try { await run('INSERT INTO cheers (a, b, day) VALUES (?, ?, ?)', me, to, day); } catch(e){ return json({error: '오늘은 이미 응원했어요.'}, 400); }
      const nm = await nameOf(me); await mail(to, {msg: `${nm}님의 응원!`, gold: 100}); await mail(me, {msg: '응원 보답', gold: 50});
    } else return json({error: '모르는 작업이에요.'}, 400);
    return json({ok: true});
  }
  // ----- 길드
  if (path === 'guild' && m === 'GET'){
    const g = await myGuild();
    if (!g){ const apps = await all('SELECT a.gid, g.name FROM gapps a JOIN guilds g ON g.id = a.gid WHERE a.pk = ?', me); return json({guild: null, apps}); }
    const mem = await all('SELECT m.pk, m.rank, m.contrib, m.att, m.joined, p.name, p.lv, p.job, p.at FROM gmembers m LEFT JOIN presence p ON p.pk = m.pk WHERE m.gid = ? ORDER BY CASE m.rank WHEN \'master\' THEN 0 WHEN \'officer\' THEN 1 ELSE 2 END, m.contrib DESC', g.id);
    const apps = g.rank !== 'member' ? await all('SELECT a.pk, a.at, p.name, p.lv, p.job FROM gapps a LEFT JOIN presence p ON p.pk = a.pk WHERE a.gid = ?', g.id) : [];
    return json({guild: gInfo(g), members: mem.map(x => ({...x, online: x.at > now - ONLINE_MS, attended: x.att === day})), apps});
  }
  if (path === 'guilds' && m === 'GET'){
    const q = '%' + String(url.searchParams.get('q') || '').replace(/[%_]/g, '') + '%';
    const r = await all('SELECT g.id, g.name, g.lv, g.notice, g.join_mode, g.mark, (SELECT COUNT(*) FROM gmembers WHERE gid = g.id) AS n FROM guilds g WHERE g.name LIKE ? ORDER BY g.lv DESC, n DESC LIMIT 30', q);
    return json({list: r.map(x => ({...x, cap: gCap(x.lv)}))});
  }
  if (path === 'guild' && m === 'POST'){
    const act = String(body.act || ''), g = await myGuild(), tgt = String(body.pk || '');
    const officer = g && g.rank !== 'member', master = g && g.rank === 'master';
    const gsys = (gid, text) => run('INSERT INTO chat (ch, pk, name, text, at) VALUES (?, ?, ?, ?, ?)', 'g:' + gid, '', '길드', text, now);
    const myName = await nameOf(me);
    if (act === 'create'){
      if (g) return json({error: '이미 길드에 있어요.'}, 400);
      const name = String(body.name || '').trim(); if (!/^[가-힣A-Za-z0-9 ]{2,12}$/.test(name)) return json({error: '길드 이름은 2~12자 한글·영문·숫자예요.'}, 400);
      if (await one('SELECT 1 FROM guilds WHERE name = ?', name)) return json({error: '이미 있는 길드 이름이에요.'}, 409);
      await run('INSERT INTO guilds (name, master, notice, join_mode, mark, created) VALUES (?, ?, ?, ?, ?, ?)', name, me, '', body.join === 'apply' ? 'apply' : 'open', String(body.mark || '🛡️').slice(0, 4), now);
      const ng = await one('SELECT id FROM guilds WHERE name = ?', name);
      await run("INSERT INTO gmembers (pk, gid, rank, joined) VALUES (?, ?, 'master', ?)", me, ng.id, now); await run('DELETE FROM gapps WHERE pk = ?', me);
      await gsys(ng.id, `${myName}님이 길드 [${name}]을(를) 만들었어요!`); return json({ok: true});
    }
    if (act === 'apply'){
      if (g) return json({error: '이미 길드에 있어요.'}, 400);
      const tg = await one('SELECT id, name, lv, join_mode FROM guilds WHERE id = ?', +body.gid); if (!tg) return json({error: '없는 길드예요.'}, 404);
      const n = (await one('SELECT COUNT(*) AS c FROM gmembers WHERE gid = ?', tg.id)).c; if (n >= gCap(tg.lv)) return json({error: '길드 인원이 가득 찼어요.'}, 400);
      if (tg.join_mode === 'open'){ await run("INSERT INTO gmembers (pk, gid, rank, joined) VALUES (?, ?, 'member', ?)", me, tg.id, now); await run('DELETE FROM gapps WHERE pk = ?', me); await gsys(tg.id, `${myName}님이 길드에 들어왔어요. 환영해요!`); return json({ok: true, joined: true}); }
      await run('INSERT OR REPLACE INTO gapps (pk, gid, at) VALUES (?, ?, ?)', me, tg.id, now); await gsys(tg.id, `${myName}님이 가입을 신청했어요.`); return json({ok: true, joined: false});
    }
    if (act === 'cancelapp'){ await run('DELETE FROM gapps WHERE pk = ? AND gid = ?', me, +body.gid); return json({ok: true}); }
    if (!g) return json({error: '길드에 들어가 있지 않아요.'}, 400);
    if (act === 'accept' || act === 'reject'){
      if (!officer) return json({error: '길드장·부길드장만 할 수 있어요.'}, 403);
      const ap = await one('SELECT 1 FROM gapps WHERE pk = ? AND gid = ?', tgt, g.id); if (!ap) return json({error: '신청이 없어요.'}, 404);
      await run('DELETE FROM gapps WHERE pk = ?', act === 'accept' ? tgt : '\u0000'); await run('DELETE FROM gapps WHERE pk = ? AND gid = ?', tgt, g.id);
      if (act === 'accept'){
        if (await myGuild(tgt)) return json({error: '이미 다른 길드에 들어갔어요.'}, 400);
        const n = (await one('SELECT COUNT(*) AS c FROM gmembers WHERE gid = ?', g.id)).c; if (n >= gCap(g.lv)) return json({error: '길드 인원이 가득 찼어요.'}, 400);
        await run("INSERT INTO gmembers (pk, gid, rank, joined) VALUES (?, ?, 'member', ?)", tgt, g.id, now); await gsys(g.id, `${await nameOf(tgt)}님이 길드에 들어왔어요. 환영해요!`);
      }
      return json({ok: true});
    }
    if (act === 'leave'){
      if (master){ const n = (await one('SELECT COUNT(*) AS c FROM gmembers WHERE gid = ?', g.id)).c; if (n > 1) return json({error: '길드장은 다른 사람에게 넘긴 뒤 나갈 수 있어요.'}, 400);
        await db.batch([db.prepare('DELETE FROM gmembers WHERE gid = ?').bind(g.id), db.prepare('DELETE FROM gapps WHERE gid = ?').bind(g.id), db.prepare('DELETE FROM guilds WHERE id = ?').bind(g.id)]); return json({ok: true, disbanded: true}); }
      await run('DELETE FROM gmembers WHERE pk = ?', me); await gsys(g.id, `${myName}님이 길드를 떠났어요.`); return json({ok: true});
    }
    if (act === 'attend'){
      if (g.att === day) return json({error: '오늘은 이미 출석했어요.'}, 400);
      await run('UPDATE gmembers SET att = ?, contrib = contrib + 10 WHERE pk = ?', day, me); await gAddExp(g.id, 10);
      await mail(me, {msg: `길드 출석 보상 (길드 Lv.${g.lv})`, gold: 50 * g.lv, pots: {hp: 1}}); return json({ok: true});
    }
    if (act === 'donate'){  // 골드는 클라이언트에서 먼저 뺌
      const gold = Math.floor(+body.gold || 0); if (gold < 100 || gold > 1e7) return json({error: '100~1천만 골드까지 낼 수 있어요.'}, 400);
      const e = Math.floor(gold / 100); await run('UPDATE gmembers SET contrib = contrib + ? WHERE pk = ?', e, me); await gAddExp(g.id, e);
      await gsys(g.id, `${myName}님이 ${gold.toLocaleString()}골드를 기부했어요! (길드 경험치 +${e})`); return json({ok: true});
    }
    if (act === 'notice'){ if (!officer) return json({error: '길드장·부길드장만 할 수 있어요.'}, 403); await run('UPDATE guilds SET notice = ? WHERE id = ?', String(body.text || '').slice(0, 120), g.id); return json({ok: true}); }
    if (act === 'joinmode'){ if (!master) return json({error: '길드장만 할 수 있어요.'}, 403); await run('UPDATE guilds SET join_mode = ? WHERE id = ?', body.join === 'apply' ? 'apply' : 'open', g.id); return json({ok: true}); }
    if (act === 'mark'){ if (!master) return json({error: '길드장만 할 수 있어요.'}, 403); await run('UPDATE guilds SET mark = ? WHERE id = ?', String(body.mark || '🛡️').slice(0, 4), g.id); return json({ok: true}); }
    const tm = await one('SELECT rank FROM gmembers WHERE pk = ? AND gid = ?', tgt, g.id);
    if (!tm || tgt === me) return json({error: '길드원이 아니에요.'}, 404);
    if (act === 'kick'){ if (!officer || tm.rank === 'master' || (tm.rank === 'officer' && !master)) return json({error: '권한이 없어요.'}, 403); await run('DELETE FROM gmembers WHERE pk = ?', tgt); await gsys(g.id, `${await nameOf(tgt)}님이 길드에서 나갔어요.`); return json({ok: true}); }
    if (act === 'promote' || act === 'demote'){ if (!master) return json({error: '길드장만 할 수 있어요.'}, 403); await run('UPDATE gmembers SET rank = ? WHERE pk = ?', act === 'promote' ? 'officer' : 'member', tgt); return json({ok: true}); }
    if (act === 'master'){ if (!master) return json({error: '길드장만 할 수 있어요.'}, 403);
      await db.batch([db.prepare("UPDATE gmembers SET rank = 'master' WHERE pk = ?").bind(tgt), db.prepare("UPDATE gmembers SET rank = 'officer' WHERE pk = ?").bind(me), db.prepare('UPDATE guilds SET master = ? WHERE id = ?').bind(tgt, g.id)]);
      await gsys(g.id, `${await nameOf(tgt)}님이 새 길드장이 되었어요!`); return json({ok: true}); }
    return json({error: '모르는 작업이에요.'}, 400);
  }
  // ----- 거래소: 물건은 서버가 맡아 두고, 팔리면 판 사람에게 골드(수수료 5%)를 우편으로
  const FEE = .05, LIST_MAX = 10, LIST_MS = 3 * 864e5;
  async function expireListings(){
    const old = await all("SELECT n, seller, item, name FROM market WHERE st = 'on' AND at < ? LIMIT 20", now - LIST_MS);
    for (const x of old){ const r = await run("UPDATE market SET st = 'expired', done_at = ? WHERE n = ? AND st = 'on'", now, x.n); if (r.meta && r.meta.changes === 0) continue; await mail(x.seller, {msg: `거래소 기간이 끝나 [${x.name}]을(를) 돌려드려요.`, raw: [JSON.parse(x.item)]}); }
  }
  if (path === 'market' && m === 'GET'){
    if (Math.random() < .2) await expireListings();
    const q = String(url.searchParams.get('q') || '').replace(/[%_]/g, ''), kind = String(url.searchParams.get('kind') || ''), slot = String(url.searchParams.get('slotf') || ''), rar = url.searchParams.get('rar');
    const sort = {low: 'price ASC', high: 'price DESC', new: 'n DESC'}[url.searchParams.get('sort')] || 'n DESC', page = Math.max(0, +url.searchParams.get('page') || 0);
    const w = ["st = 'on'"], a = [];
    if (q){ w.push('name LIKE ?'); a.push('%' + q + '%'); } if (kind){ w.push('kind = ?'); a.push(kind); } if (slot){ w.push('slot = ?'); a.push(slot); } if (rar !== null && rar !== ''){ w.push('rar = ?'); a.push(+rar); }
    const r = await all(`SELECT n, seller, sname, item, kind, name, slot, rar, band, qty, price, at FROM market WHERE ${w.join(' AND ')} ORDER BY ${sort} LIMIT 30 OFFSET ?`, ...a, page * 30);
    return json({list: r.map(x => ({...x, item: JSON.parse(x.item), mine: uidOf(x.seller) === s.id, left: Math.max(0, x.at + LIST_MS - now)}))});
  }
  if (path === 'market/mine' && m === 'GET'){
    const r = await all('SELECT n, item, kind, name, rar, qty, price, at, st, buyer, done_at FROM market WHERE seller = ? ORDER BY n DESC LIMIT 40', me);
    const b = await all("SELECT n, name, rar, qty, price, done_at FROM market WHERE buyer = ? ORDER BY done_at DESC LIMIT 20", me);
    return json({list: r.map(x => ({...x, item: JSON.parse(x.item), left: Math.max(0, x.at + LIST_MS - now)})), bought: b});
  }
  if (path === 'market/price' && m === 'GET'){
    const name = String(url.searchParams.get('name') || '');
    const r = await one("SELECT COUNT(*) AS c, AVG(price * 1.0 / qty) AS avg, MIN(price * 1.0 / qty) AS lo, MAX(price * 1.0 / qty) AS hi FROM market WHERE name = ? AND st = 'sold' AND done_at > ?", name, now - 7 * 864e5);
    const on = await one("SELECT MIN(price * 1.0 / qty) AS lo, COUNT(*) AS c FROM market WHERE name = ? AND st = 'on'", name);
    return json({sold: r.c, avg: r.avg ? Math.round(r.avg) : null, lo: r.lo ? Math.round(r.lo) : null, hi: r.hi ? Math.round(r.hi) : null, onLow: on.lo ? Math.round(on.lo) : null, onCount: on.c});
  }
  if (path === 'market' && m === 'POST'){
    const act = String(body.act || '');
    if (act === 'sell'){
      const it = body.item, price = Math.floor(+body.price || 0), qty = Math.max(1, Math.min(999, Math.floor(+body.qty || 1)));
      if (!it || typeof it !== 'object' || JSON.stringify(it).length > 2000) return json({error: '잘못된 물건이에요.'}, 400);
      if (price < 1 || price > 1e9) return json({error: '가격은 1~10억 골드예요.'}, 400);
      const n = (await one("SELECT COUNT(*) AS c FROM market WHERE seller = ? AND st = 'on'", me)).c; if (n >= LIST_MAX) return json({error: `한 번에 ${LIST_MAX}개까지 올릴 수 있어요.`}, 400);
      await run('INSERT INTO market (seller, sname, item, kind, name, slot, rar, band, qty, price, at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        me, await nameOf(me), JSON.stringify(it), String(body.kind || 'equip').slice(0, 10), String(body.name || '').slice(0, 40), String(it.slot || body.slotf || '').slice(0, 12), +it.rar || 0, +it.band || 0, qty, price, now);
      return json({ok: true});
    }
    const x = await one('SELECT * FROM market WHERE n = ?', +body.n); if (!x) return json({error: '없는 물건이에요.'}, 404);
    if (act === 'cancel'){
      if (x.seller !== me) return json({error: '내가 올린 물건이 아니에요.'}, 403);
      const r = await run("UPDATE market SET st = 'cancel', done_at = ? WHERE n = ? AND st = 'on'", now, x.n); if (r.meta && r.meta.changes === 0) return json({error: '이미 팔렸거나 내려간 물건이에요.'}, 400);
      return json({ok: true, item: JSON.parse(x.item), qty: x.qty});
    }
    if (act === 'buy'){
      if (uidOf(x.seller) === s.id) return json({error: '내가 올린 물건은 살 수 없어요.'}, 400);
      if (x.at < now - LIST_MS) return json({error: '기간이 끝난 물건이에요.'}, 400);
      const r = await run("UPDATE market SET st = 'sold', buyer = ?, done_at = ? WHERE n = ? AND st = 'on'", me, now, x.n); if (r.meta && r.meta.changes === 0) return json({error: '방금 다른 사람이 샀어요.'}, 409);
      const got = Math.max(1, Math.floor(x.price * (1 - FEE)));
      await mail(x.seller, {msg: `거래소에서 [${x.name}${x.qty > 1 ? ' ×' + x.qty : ''}]이(가) ${x.price.toLocaleString()}골드에 팔렸어요! (수수료 5%)`, gold: got});
      return json({ok: true, item: JSON.parse(x.item), price: x.price, qty: x.qty});
    }
    return json({error: '모르는 작업이에요.'}, 400);
  }

  // ----- 운영자 전용
  if (path.startsWith('admin/')){
    if (!isAdmin(s.id)) return json({error: '운영자만 쓸 수 있어요.'}, 403);
    const sub = path.slice(6), log = (act, target) => db.prepare('INSERT INTO gmlog (by, act, target, at) VALUES (?, ?, ?, ?)').bind(s.id, act, target, Date.now()).run();
    const lastOf = "(SELECT MAX(at) FROM saves WHERE id = u.id OR substr(id, 1, length(u.id) + 1) = u.id || '#')";
    if (sub === 'stats'){
      const c = async q => ((await db.prepare(q).first()) || {}).c || 0;
      return json({users: await c('SELECT COUNT(*) AS c FROM users'), today: await c(`SELECT COUNT(*) AS c FROM users WHERE created > ${Date.now() - 864e5}`),
        active: await c(`SELECT COUNT(*) AS c FROM saves WHERE at > ${Date.now() - 864e5}`), open: await c('SELECT COUNT(*) AS c FROM inquiries WHERE answer IS NULL'), bans: await c('SELECT COUNT(*) AS c FROM bans')});
    }
    if (sub === 'users'){
      const q = '%' + String(url.searchParams.get('q') || '').toLowerCase().replace(/[%_]/g, '') + '%';
      const r = await db.prepare(`SELECT u.id, u.created, b.reason AS ban, b.until AS ban_until, ${lastOf} AS last FROM users u LEFT JOIN bans b ON b.id = u.id WHERE u.id LIKE ? ORDER BY last DESC LIMIT 50`).bind(q).all();
      return json({list: (r.results || []).map(x => ({...x, admin: isAdmin(x.id)}))});
    }
    const target = String(body.id || url.searchParams.get('id') || '').toLowerCase();
    const tRow = n => n ? `${target}#${n}` : target;
    if (sub === 'chars'){
      const ids = Array.from({length: SLOTS}, (_, i) => tRow(i));
      const r = await db.prepare(`SELECT id, data, at FROM saves WHERE id IN (${ids.map(() => '?').join(',')})`).bind(...ids).all();
      return json({list: (r.results || []).map(x => ({slot: ids.indexOf(x.id), data: x.data, at: x.at}))});
    }
    if (sub === 'user' && m === 'POST'){
      if (!target || !(await db.prepare('SELECT 1 FROM users WHERE id = ?').bind(target).first())) return json({error: '없는 아이디예요.'}, 404);
      const act = String(body.act || '');
      if (isAdmin(target) && act !== 'kick') return json({error: '운영자 계정에는 할 수 없어요.'}, 400);
      if (act === 'ban'){
        const days = Math.max(0, Math.min(3650, +body.days || 0)), reason = String(body.reason || '').slice(0, 60);
        await db.prepare('INSERT INTO bans (id, reason, at, until, by) VALUES (?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET reason = excluded.reason, at = excluded.at, until = excluded.until, by = excluded.by')
          .bind(target, reason, Date.now(), days ? Date.now() + days * 864e5 : 0, s.id).run();
        await db.prepare('DELETE FROM sessions WHERE id = ?').bind(target).run();
      } else if (act === 'unban') await db.prepare('DELETE FROM bans WHERE id = ?').bind(target).run();
      else if (act === 'mute'){ const days = Math.max(0, Math.min(3650, +body.days || 1)); await db.prepare('INSERT INTO mutes (id, until, reason) VALUES (?, ?, ?) ON CONFLICT(id) DO UPDATE SET until = excluded.until, reason = excluded.reason').bind(target, days ? Date.now() + days * 864e5 : 9e15, String(body.reason || '').slice(0, 60)).run(); }
      else if (act === 'unmute') await db.prepare('DELETE FROM mutes WHERE id = ?').bind(target).run();
      else if (act === 'kick') await db.prepare('DELETE FROM sessions WHERE id = ?').bind(target).run();
      else if (act === 'resetpw'){
        const pw = String(body.pw || ''); if (!pwOk(pw)) return json({error: '새 비밀번호는 8~16자, 영문·숫자·특수문자 중 2가지 이상이에요.'}, 400);
        const salt = rand(16); await db.prepare('UPDATE users SET salt = ?, hash = ? WHERE id = ?').bind(salt, await pbkdf2(pw, salt), target).run();
        await db.prepare('DELETE FROM sessions WHERE id = ?').bind(target).run();
      } else if (act === 'delete'){
        await db.batch([db.prepare('DELETE FROM users WHERE id = ?').bind(target), db.prepare('DELETE FROM sessions WHERE id = ?').bind(target),
          db.prepare("DELETE FROM saves WHERE id = ? OR substr(id, 1, length(?) + 1) = ? || '#'").bind(target, target, target), db.prepare('DELETE FROM grants WHERE uid = ?').bind(target), db.prepare('DELETE FROM bans WHERE id = ?').bind(target)]);
      } else return json({error: '모르는 작업이에요.'}, 400);
      await log(act, target); return json({ok: true});
    }
    if (sub === 'grant' && m === 'POST'){
      const pl = JSON.stringify(body.payload || {}); if (pl.length > 4000) return json({error: '너무 많아요.'}, 400);
      if (!(await db.prepare('SELECT 1 FROM users WHERE id = ?').bind(target).first())) return json({error: '없는 아이디예요.'}, 404);
      await db.prepare('INSERT INTO grants (uid, slot, payload, at, by) VALUES (?, ?, ?, ?, ?)').bind(target, slotOf(body.slot), pl, Date.now(), s.id).run();
      await log('grant', `${target}#${slotOf(body.slot)} ${pl.slice(0, 120)}`); return json({ok: true});
    }
    if (sub === 'inquiries'){
      const open = url.searchParams.get('open') === '1';
      const r = await db.prepare(`SELECT n, uid, cat, title, body, at, answer, ans_at, ans_by FROM inquiries ${open ? 'WHERE answer IS NULL' : ''} ORDER BY n DESC LIMIT 50`).all();
      return json({list: r.results || []});
    }
    if (sub === 'answer' && m === 'POST'){
      const ans = String(body.answer || '').trim().slice(0, 1000); if (!ans) return json({error: '답변을 적어 주세요.'}, 400);
      await db.prepare('UPDATE inquiries SET answer = ?, ans_at = ?, ans_by = ? WHERE n = ?').bind(ans, Date.now(), s.id, +body.n).run();
      await log('answer', '#' + body.n); return json({ok: true});
    }
    if (sub === 'notice' && m === 'POST'){
      const text = String(body.text || '').trim().slice(0, 200);
      await db.prepare("INSERT INTO notice (k, text, at) VALUES ('main', ?, ?) ON CONFLICT(k) DO UPDATE SET text = excluded.text, at = excluded.at").bind(text, Date.now()).run();
      await log('notice', text.slice(0, 60)); return json({ok: true});
    }
    if (sub === 'chatdel' && m === 'POST'){ await db.prepare('DELETE FROM chat WHERE n = ?').bind(+body.n).run(); await log('chatdel', '#' + body.n); return json({ok: true}); }
    if (sub === 'logs'){ const r = await db.prepare('SELECT by, act, target, at FROM gmlog ORDER BY n DESC LIMIT 50').all(); return json({list: r.results || []}); }
  }
  return json({error: '없는 주소예요.'}, 404);
}
