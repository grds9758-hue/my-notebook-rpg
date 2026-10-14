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
    if (sub === 'logs'){ const r = await db.prepare('SELECT by, act, target, at FROM gmlog ORDER BY n DESC LIMIT 50').all(); return json({list: r.results || []}); }
  }
  return json({error: '없는 주소예요.'}, 404);
}
