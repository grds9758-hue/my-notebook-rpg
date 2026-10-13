// 계정 서버: Cloudflare Pages Functions + D1 (바인딩 이름 DB).
// /api/ping · /api/signup · /api/login · /api/logout · /api/save (GET 불러오기, PUT 저장)
// 비밀번호는 PBKDF2 해시로만 저장한다. 로그인하면 30일짜리 토큰을 준다.

const SCHEMA = [
  'CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, salt TEXT NOT NULL, hash TEXT NOT NULL, created INTEGER NOT NULL)',
  'CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, id TEXT NOT NULL, exp INTEGER NOT NULL)',
  'CREATE TABLE IF NOT EXISTS saves (id TEXT PRIMARY KEY, data TEXT NOT NULL, at INTEGER NOT NULL, name TEXT, lv INTEGER)',
  'CREATE TABLE IF NOT EXISTS tries (key TEXT PRIMARY KEY, n INTEGER NOT NULL, until INTEGER NOT NULL)',
];
const ITER = 20000;               // 무료 요금제 CPU 한도 안에서 돌도록
const SESSION_MS = 30 * 864e5;    // 30일
const MAX_SAVE = 900 * 1024;      // 저장 데이터 최대 900KB
const ID_RE = /^[A-Za-z0-9]{4,16}$/;

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
  const m = request.method;
  let body = {};
  if (m === 'POST' || m === 'PUT'){ try { body = await request.json(); } catch(e){ return json({error: '잘못된 요청이에요.'}, 400); } }

  if (path === 'signup' && m === 'POST'){
    const id = String(body.id || ''), pw = String(body.pw || '');
    if (!ID_RE.test(id)) return json({error: '아이디는 영문·숫자 4~16자예요.'}, 400);
    if (pw.length < 6 || pw.length > 64) return json({error: '비밀번호는 6~64자예요.'}, 400);
    const key = id.toLowerCase();
    if (await db.prepare('SELECT 1 FROM users WHERE id = ?').bind(key).first()) return json({error: '이미 쓰는 아이디예요.'}, 409);
    const salt = rand(16), hash = await pbkdf2(pw, salt);
    await db.prepare('INSERT INTO users (id, salt, hash, created) VALUES (?, ?, ?, ?)').bind(key, salt, hash, Date.now()).run();
    return json({id: key, token: await newSession(db, key)});
  }
  if (path === 'login' && m === 'POST'){
    const id = String(body.id || '').toLowerCase(), pw = String(body.pw || '');
    const ip = request.headers.get('CF-Connecting-IP') || '?', tk = `${ip}|${id}`;
    if (await tooMany(db, tk)) return json({error: '비밀번호를 너무 많이 틀렸어요. 10분 뒤에 다시 해 주세요.'}, 429);
    const u = ID_RE.test(id) ? await db.prepare('SELECT salt, hash FROM users WHERE id = ?').bind(id).first() : null;
    if (!u || !same(await pbkdf2(pw, u.salt), u.hash)){ await failed(db, tk); return json({error: '아이디 또는 비밀번호가 틀려요.'}, 401); }
    await db.prepare('DELETE FROM tries WHERE key = ?').bind(tk).run();
    await db.prepare('DELETE FROM sessions WHERE id = ? AND exp < ?').bind(id, Date.now()).run();
    return json({id, token: await newSession(db, id)});
  }

  const s = await session(db, request);
  if (!s) return json({error: '다시 로그인해 주세요.'}, 401);
  if (path === 'logout' && m === 'POST'){ await db.prepare('DELETE FROM sessions WHERE token = ?').bind(s.token).run(); return json({ok: true}); }
  if (path === 'save' && m === 'GET'){
    const r = await db.prepare('SELECT data, at FROM saves WHERE id = ?').bind(s.id).first();
    return json(r ? {data: r.data, at: r.at} : {data: null});
  }
  if (path === 'save' && m === 'PUT'){
    const data = String(body.data || '');
    if (!data || data.length > MAX_SAVE) return json({error: '저장 데이터가 너무 커요.'}, 413);
    try { JSON.parse(data); } catch(e){ return json({error: '잘못된 저장 데이터예요.'}, 400); }
    await db.prepare('INSERT INTO saves (id, data, at, name, lv) VALUES (?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET data = excluded.data, at = excluded.at, name = excluded.name, lv = excluded.lv')
      .bind(s.id, data, +body.at || Date.now(), String(body.name || '').slice(0, 24), +body.lv || 1).run();
    return json({ok: true});
  }
  return json({error: '없는 주소예요.'}, 404);
}
