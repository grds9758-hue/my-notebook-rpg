#!/usr/bin/env python3
"""받은 그림(zip 또는 폴더)을 검사해서 index.html의 `const ART = {...}; /*ART*/` 줄에 넣는다.

폴더·파일 이름은 의뢰서(design/ALL_ART_REQUEST.txt PART 11) 그대로:
  icons/{equipment,set,material,consumable}/<이름>.png  -> icon/<이름>   (64px로 줄여 넣음, NEAREST)
  icons/ui/<이름>.png                                   -> ui/<이름>
  icons/skill/skill_<스킬코드>.png                       -> skill/<스킬코드>
  npc/npc_<시설>_sheet.png (6열×3행)                     -> npc/<시설>_<줄>_<칸> 18장으로 잘라 넣음
  backgrounds/bg_<이름>.png                             -> bg/<이름>  (보스 등장 컷 bosses/boss_bN_intro.png -> bg/boss_intro_bN)
  characters/char_<코드>_<front|back>.png, characters/novice/char_novice_*.png -> char/<코드>_<면> (시트, 4열)
  monsters/mon_mN.png (4열×4행)                          -> mon/mN (시트)
  bosses/boss_bN.png (4열×6행)                           -> boss/bN (시트)
  cards/card_*.png                                       -> card/*

쓰는 법:  python3 tools/import_art.py 받은파일.zip [더.zip ...] [--dry]
  --dry : 검사만 하고 게임에는 안 넣음
결과 보고: design/art_import_report.txt (넣은 것·이름이 틀린 것·문제 있는 것)
같은 이름을 다시 넣으면 덮어쓴다. 여러 번 나눠 넣어도 앞에 넣은 그림은 남는다.
"""
import sys, os, io, re, json, csv, base64, zipfile, tempfile
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, 'index.html')
REPORT = os.path.join(ROOT, 'design', 'art_import_report.txt')

ICON_PX = 64          # 아이콘은 64px로 (화면에서 40~56px)
BG_W = 585            # 배경 가로 (780의 3/4, 용량 절약)
NPC_CELL = (256, 320) # NPC 한 컷
SHEET_COLS = 4
ROWS = {'front': 5, 'back': 8, 'mon': 4, 'boss': 6}
FRAMES = {'front': [4, 4, 3, 1, 2], 'back': [4, 4, 4, 2, 2, 2, 3, 3], 'mon': [4, 4, 2, 3], 'boss': [4, 4, 4, 2, 2, 4]}


def known_names():
    """의뢰서 목록에 있는 아이콘 파일 이름 (이름이 틀린 파일을 골라내려고)."""
    names = set()
    for f in ('item_list_699.csv', 'icons_new.csv'):
        p = os.path.join(ROOT, 'design', f)
        if os.path.exists(p):
            for row in list(csv.reader(open(p, encoding='utf-8-sig')))[1:]:
                names.add(row[1][:-4])
    p = os.path.join(ROOT, 'design', 'emoji_icons.txt')
    if os.path.exists(p):
        t = open(p, encoding='utf-8').read()
        names.update(m[:-4] for m in re.findall(r'^  (\w+\.png)', t, re.M))
        names.update(re.findall(r'^    (skill_\w+)', t, re.M))
    return names


def to_data_url(im, lossless=True, q=80):
    b = io.BytesIO()
    if lossless:
        im.save(b, 'WEBP', lossless=True, quality=100, method=6)
    else:
        im.save(b, 'WEBP', quality=q, method=6)
    return 'data:image/webp;base64,' + base64.b64encode(b.getvalue()).decode()


def corners_transparent(im):
    if im.mode != 'RGBA':
        return False
    w, h = im.size
    return all(im.getpixel(p)[3] < 16 for p in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)])


def looks_checker(im):
    """회색·흰색 체크무늬를 그림으로 그린 가짜 투명 배경인지 (모서리 16px 안에서 두 색이 번갈아 나옴)."""
    rgb = im.convert('RGB')
    w, h = rgb.size
    for cx, cy in [(0, 0), (w - 16, 0), (0, h - 16), (w - 16, h - 16)]:
        cols = set()
        for y in range(cy, min(h, cy + 16), 2):
            for x in range(cx, min(w, cx + 16), 2):
                r, g, b = rgb.getpixel((x, y))
                if abs(r - g) < 8 and abs(g - b) < 8 and r > 150:
                    cols.add(r // 24)
        if len(cols) == 2:
            return True
    return False


def fit_icon(im, px):
    im = im.convert('RGBA')
    bb = im.getbbox() or (0, 0, im.width, im.height)
    im = im.crop(bb)
    s = (px - 4) / max(im.size)
    nw, nh = max(1, round(im.width * s)), max(1, round(im.height * s))
    im = im.resize((nw, nh), Image.NEAREST if s < 1 else Image.NEAREST)
    out = Image.new('RGBA', (px, px), (0, 0, 0, 0))
    out.paste(im, ((px - nw) // 2, (px - nh) // 2), im)
    return out


def remove_flat_bg(im):
    """배경이 단색이면 지운다 (rembg가 있으면 그걸 우선 사용)."""
    if corners_transparent(im):
        return im
    try:
        from rembg import remove, new_session
        out = remove(im, session=new_session('isnet-anime')).convert('RGBA')
        alpha = out.getchannel('A')
        if sum(1 for a in alpha.getdata() if a > 128) > alpha.width * alpha.height * 0.08:
            return out  # 사람이 남았을 때만 사용 (거의 다 지웠으면 단색 지우기로)
    except Exception:
        pass
    im = im.convert('RGBA')
    px = im.load()
    bg = px[0, 0][:3]
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2]) < 30:
                px[x, y] = (r, g, b, 0)
    return im


def sheet_entry(im, kind):
    im = im.convert('RGBA')
    w, h = im.size
    issues = []
    if w % SHEET_COLS:
        issues.append(f'가로 {w}px가 4칸으로 나누어떨어지지 않음')
    cw = w // SHEET_COLS
    rows = round(h / cw) if cw else 0
    want = ROWS[kind]
    if rows != want:
        issues.append(f'줄 수 {rows} (기대 {want})')
    if not corners_transparent(im):
        issues.append('배경이 투명하지 않음')
    return {'src': to_data_url(im), 'cols': SHEET_COLS, 'rows': max(1, rows), 'n': FRAMES[kind][:max(1, rows)]}, issues


def handle(rel, im, names, out, rep):
    rel = rel.replace('\\', '/')
    parts = rel.split('/')
    # zip 안 맨 위 폴더(mnbrpg_art/ 등)는 무시
    while parts and parts[0] not in ('icons', 'npc', 'backgrounds', 'characters', 'monsters', 'bosses', 'cards', 'preview'):
        parts = parts[1:]
    if not parts or parts[0] == 'preview':
        return
    base = os.path.splitext(parts[-1])[0]
    top = parts[0]
    def bad(msg):
        rep['bad'].append(f'{rel} — {msg}')
    if top == 'icons':
        sub = parts[1] if len(parts) > 2 else ''
        if sub == 'skill':
            if not base.startswith('skill_'):
                return bad('스킬 아이콘 이름은 skill_<스킬코드>')
            key = 'skill/' + base[6:]
        elif sub == 'ui':
            key = 'ui/' + base
        else:
            key = 'icon/' + base
        if names and base not in names and not (sub == 'skill' and base in names):
            rep['unknown'].append(rel)
            return
        if looks_checker(im):
            return bad('체크무늬 배경을 그림으로 그림 (진짜 투명이어야 함)')
        if not corners_transparent(im):
            bad('모서리가 투명하지 않음 (넣긴 했지만 확인 필요)')
        out[key] = to_data_url(fit_icon(im, ICON_PX))
    elif top == 'npc':
        m = re.match(r'npc_(shop|smith|onsen|inn|training)_sheet$', base)
        if not m:
            return bad('NPC 파일 이름은 npc_<shop|smith|onsen|inn|training>_sheet.png')
        code = m.group(1)
        w, h = im.size
        cw, ch = w // 6, h // 3
        if w % 6 or h % 3:
            bad('6열×3행으로 나누어떨어지지 않음 (넣긴 했지만 확인 필요)')
        for r in range(3):
            for c in range(6):
                cell = im.crop((c * cw, r * ch, (c + 1) * cw, (r + 1) * ch)).convert('RGBA')
                cell = remove_flat_bg(cell)
                cell.thumbnail(NPC_CELL, Image.LANCZOS)
                out[f'npc/{code}_{r}_{c}'] = to_data_url(cell, lossless=False, q=82)
    elif top == 'backgrounds' or (top == 'bosses' and base.endswith('_intro')):
        name = base[3:] if base.startswith('bg_') else ('boss_intro_' + base[5:-6] if base.startswith('boss_') else None)
        if not name:
            return bad('배경 이름은 bg_<이름>.png')
        w, h = im.size
        if abs(w / h - 780 / 1120) > .03:
            bad(f'비율이 780×1120과 다름 ({w}×{h}) — 넣긴 했지만 확인 필요')
        im = im.convert('RGB')
        im = im.resize((BG_W, round(BG_W * h / w)), Image.LANCZOS)
        out['bg/' + name] = to_data_url(im, lossless=False, q=74)
    elif top == 'characters':
        m = re.match(r'char_(.+)_(front|back)$', base)
        if not m:
            return bad('캐릭터 시트 이름은 char_<코드>_front.png / _back.png')
        e, issues = sheet_entry(im, m.group(2))
        for x in issues:
            bad(x)
        out[f'char/{m.group(1)}_{m.group(2)}'] = e
    elif top == 'monsters':
        m = re.match(r'mon_m(\d+)$', base)
        if not m:
            return bad('몬스터 시트 이름은 mon_m0.png ~ mon_m19.png')
        e, issues = sheet_entry(im, 'mon')
        for x in issues:
            bad(x)
        out['mon/m' + m.group(1)] = e
    elif top == 'bosses':
        m = re.match(r'boss_b(\d+)$', base)
        if not m:
            return bad('보스 시트 이름은 boss_b0.png ~ boss_b9.png')
        e, issues = sheet_entry(im, 'boss')
        for x in issues:
            bad(x)
        out['boss/b' + m.group(1)] = e
    elif top == 'cards':
        if not base.startswith('card_'):
            return bad('카드 이름은 card_m0.png 등')
        im = im.convert('RGBA')
        im.thumbnail((200, 300), Image.LANCZOS)
        out['card/' + base[5:]] = to_data_url(im, lossless=False, q=85)
    else:
        return
    rep['ok'].append(rel)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    dry = '--dry' in sys.argv
    if not args:
        print(__doc__)
        return
    names = known_names()
    out, rep = {}, {'ok': [], 'bad': [], 'unknown': []}
    for a in args:
        if zipfile.is_zipfile(a):
            z = zipfile.ZipFile(a)
            for info in z.infolist():
                if info.is_dir() or not info.filename.lower().endswith('.png') or '__MACOSX' in info.filename:
                    continue
                try:
                    im = Image.open(io.BytesIO(z.read(info)))
                    im.load()
                except Exception as ex:
                    rep['bad'].append(f'{info.filename} — 열 수 없음 ({ex})')
                    continue
                handle(info.filename, im, names, out, rep)
        elif os.path.isdir(a):
            for dp, _, fs in os.walk(a):
                for f in fs:
                    if f.lower().endswith('.png'):
                        p = os.path.join(dp, f)
                        handle(os.path.relpath(p, a), Image.open(p), names, out, rep)
    if not dry and out:
        s = open(INDEX, encoding='utf-8').read()
        m = re.search(r'const ART = (\{.*?\}); /\*ART\*/', s, re.S)
        cur = json.loads(m.group(1)) if m else {}
        cur.update(out)
        line = 'const ART = ' + json.dumps(cur, ensure_ascii=False, separators=(',', ':')) + '; /*ART*/'
        s = s[:m.start()] + line + s[m.end():]
        open(INDEX, 'w', encoding='utf-8').write(s)
    lines = [f'그림 넣기 결과 ({"검사만" if dry else "게임에 넣음"})', f'넣은 것 {len(rep["ok"])}개 · 문제 {len(rep["bad"])}건 · 목록에 없는 이름 {len(rep["unknown"])}개', '']
    if rep['bad']:
        lines += ['[문제 — 고쳐서 다시 받기]'] + ['  ' + x for x in rep['bad']] + ['']
    if rep['unknown']:
        lines += ['[목록에 없는 파일 이름 — 넣지 않음]'] + ['  ' + x for x in rep['unknown']] + ['']
    lines += ['[넣은 것]'] + ['  ' + x for x in rep['ok']]
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    open(REPORT, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    print('\n'.join(lines[:3]))
    if not dry:
        print('index.html 크기:', round(os.path.getsize(INDEX) / 1e6, 2), 'MB')


if __name__ == '__main__':
    main()
