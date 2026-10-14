#!/usr/bin/env python3
"""받은 그림(zip 또는 폴더)을 검사해서 index.html의 `const ART = {...}; /*ART*/` 줄에 넣는다.

파일 이름은 의뢰서(design/art_parts/*.txt) 그대로. 폴더 이름은 보지 않고 파일 이름으로 분류한다(한글 폴더 OK):
  icons/{equipment,set,material,consumable}/<이름>.png  -> icon/<이름>   (64px로 줄여 넣음, NEAREST)
  icons/ui/<이름>.png                                   -> ui/<이름>
  icons/skill/skill_<스킬코드>.png                       -> skill/<스킬코드>
  npc/npc_<시설>_sheet.png (6열×3행)                     -> npc/<시설>_<줄>_<칸> 18장으로 잘라 넣음
  backgrounds/bg_<이름>.png                             -> bg/<이름>  (보스 등장 컷 bosses/boss_bN_intro.png -> bg/boss_intro_bN)
  characters/char_<코드>_illust.png -> char/<코드>_illust (직업 일러스트, 홈·캐릭터 화면)
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
ILLUST_H = 560        # 직업 일러스트 세로 최대(px)
BG_W = 585            # 배경 가로 (780의 3/4, 용량 절약)
NPC_CELL = (512, 640)  # 더 크면 줄이고, 작으면 그대로 (흐려지지 않게)
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


HAIR_COLS = ['#5a302a', '#3a3646', '#deb460', '#be4634', '#c6c8d8', '#4c6ebe', '#dc7ca4']  # 게임 HAIRS 순서


def recolor(im, hexcol):
    """밝기는 그대로 두고 색만 바꾼다 (머리카락 색 만들기)."""
    im = im.convert('RGBA')
    t = [int(hexcol[k:k + 2], 16) for k in (1, 3, 5)]
    px = [p for p in im.getdata() if p[3] > 100]
    m = sum(0.299 * r + 0.587 * g + 0.114 * b for r, g, b, a in px) / max(1, len(px)) / 255 or 1
    out = Image.new('RGBA', im.size)
    out.putdata([(0, 0, 0, 0) if a == 0 else tuple(max(0, min(255, int(c * (0.299 * r + 0.587 * g + 0.114 * b) / 255 / m))) for c in t) + (a,)
                 for r, g, b, a in im.getdata()])
    return out


def to_data_url(im, lossless=True, q=80, aq=100):
    b = io.BytesIO()
    if lossless:
        im.save(b, 'WEBP', lossless=True, quality=100, method=6)
    else:
        im.save(b, 'WEBP', quality=q, alpha_quality=aq, method=6)
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
    return {'src': to_data_url(im, lossless=False, q=88, aq=80), 'cols': SHEET_COLS, 'rows': max(1, rows), 'n': FRAMES[kind][:max(1, rows)]}, issues


UI_PREFIX = ('attr_', 'ui_', 'home_', 'talk_', 'todo_', 'mission_', 'kind_', 'tab_', 'fx_')


def drop_neighbor_bits(cell):
    """칸끼리 겹친 시트를 자르면 옆 칸 그림 조각(머리카락 끝 등)이 가장자리에 남는다.
    몸(가장 큰 덩어리)과 이어지지 않고 왼쪽·오른쪽 가장자리에 닿은 조각은 지운다."""
    try:
        import numpy as np
        from scipy import ndimage
    except Exception:
        return cell
    a = np.array(cell)
    mask = a[:, :, 3] > 10
    lab, n = ndimage.label(mask, structure=np.ones((3, 3)))
    if n < 2:
        return cell
    sizes = ndimage.sum(mask, lab, range(1, n + 1))
    main = int(np.argmax(sizes)) + 1
    w = a.shape[1]
    edge = set(np.unique(lab[:, :2])) | set(np.unique(lab[:, w - 2:]))
    for k in edge:
        if k and k != main:
            a[lab == k, 3] = 0
    return Image.fromarray(a)


def fix_sheet_im(im, kind, rep, base):
    """tools/fix_sheet.py로 시트를 다시 정렬. 고친 내용은 보고서에."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import fix_sheet
    sheet, s, log, cell = fix_sheet.repack(im.convert('RGBA'), kind)
    for l in log:
        rep.setdefault('fixed', []).append(f'{base}: {l}')
    return sheet


def stitch_halves(items, rep):
    """나노바나나 방식: char_<코드>_back_a.png(1~4줄) + _back_b.png(5~8줄) → char_<코드>_back.png 한 장."""
    halves, rest = {}, []
    for rel, im in items:
        m = re.match(r'(char_.+_back)_([ab])$', os.path.splitext(rel.replace('\\', '/').split('/')[-1])[0])
        if m:
            halves.setdefault(m.group(1), {})[m.group(2)] = (rel, im)
        else:
            rest.append((rel, im))
    for base, d in halves.items():
        if set(d) != {'a', 'b'}:
            rep['bad'].append(f'{base} — 뒷모습 위(_a)·아래(_b) 두 장이 다 있어야 함 (지금: {", ".join(sorted(d))})')
            continue
        a = key_bg(d['a'][1]); b = key_bg(d['b'][1])
        w = 512
        a = a.resize((w, round(a.size[1] * w / a.size[0])), Image.LANCZOS)
        b = b.resize((w, round(b.size[1] * w / b.size[0])), Image.LANCZOS)
        both = Image.new('RGBA', (w, a.size[1] + b.size[1]), (0, 0, 0, 0))
        both.paste(a, (0, 0)); both.paste(b, (0, a.size[1]))
        rest.append((base + '.png', both))
        rep.setdefault('fixed', []).append(f'{base}: 위·아래 두 장을 이어 붙임')
    return rest


def key_bg(im):
    """단색 배경(나노바나나 분홍 #FF00FF 등)을 가장자리에서 이어진 부분만 투명하게. 이미 투명하면 그대로."""
    im = im.convert('RGBA')
    if corners_transparent(im):
        return im
    import numpy as np
    from scipy import ndimage
    a = np.array(im).astype(np.int16)
    # 배경색: 테두리 3px에서 많이 나오는 색(최대 2개). 투명인 척 칠한 회색 체크무늬면 두 색을 다 배경으로 본다.
    ring = np.concatenate([a[:3].reshape(-1, 4), a[-3:].reshape(-1, 4), a[:, :3].reshape(-1, 4), a[:, -3:].reshape(-1, 4)])[:, :3]
    q, cnt = np.unique(ring // 16, axis=0, return_counts=True)
    order = np.argsort(-cnt)
    bgs = []
    for k in order[:2]:
        if cnt[k] > .15 * len(ring):
            sel = np.all(ring // 16 == q[k], axis=1)
            bgs.append(np.median(ring[sel], axis=0))
    if not bgs:
        bgs = [np.median(np.array([a[0, 0, :3], a[0, -1, :3], a[-1, 0, :3], a[-1, -1, :3]]), axis=0)]
    gray = lambda c: c.max() - c.min() < 24 and c.min() > 120  # 밝은 무채색(흰·회색 체크무늬 칸)
    if len(bgs) == 2 and not (gray(bgs[0]) and gray(bgs[1])) and np.abs(bgs[0] - bgs[1]).sum() > 120:
        bgs = bgs[:1]  # 체크무늬가 아닌데 두 색이 많이 다르면 하나만(가장자리에 닿은 그림일 수 있음)
    d = np.min([np.abs(a[:, :, :3] - bg).sum(2) for bg in bgs], axis=0)
    near = d < 90
    lab, n = ndimage.label(near)
    edge = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    mask = np.isin(lab, list(edge)) | ((d < 45) if len(bgs) == 1 else False)  # 체크무늬(흰·회색)면 갇힌 색은 안 지움(흰 옷 보호)  # 가장자리와 이어진 배경 + 그림 틈에 갇힌 거의 같은 색(그림에는 그 색을 안 쓰게 요청함)
    # 경계 1~2px 번짐(분홍 테두리)도 지움
    fringe = ndimage.binary_dilation(mask, iterations=2) & (d < 200) & ~mask
    out = a.copy()
    out[mask, 3] = 0
    out[fringe, 3] = (out[fringe, 3] * .35).astype(np.int16)
    # 남은 분홍기 빼기 (가장자리 픽셀 색에서 배경색 섞임 줄이기)
    return Image.fromarray(out.clip(0, 255).astype(np.uint8))


def drop_text_bands(im, rows):
    """나노바나나가 위·아래에 써 넣은 제목 글자 줄을 잘라 낸다(빈 띠로 떨어진 얇은 줄만). 잘라 낸 높이를 돌려줌."""
    import numpy as np
    a = np.array(im.convert('RGBA'))[:, :, 3] > 20
    H = a.shape[0]
    ch = H / rows
    filled = a.any(1)
    cut_top = cut_bot = 0
    # 위: 맨 위 그림 덩어리가 얇고(칸의 30% 아래) 그 아래 빈 띠가 있으면 제목 글자로 봄
    ys = np.nonzero(filled)[0]
    if len(ys):
        y = ys[0]; end = y
        while end < H and filled[end]: end += 1
        gap = end
        while gap < H and not filled[gap]: gap += 1
        if y < .12 * H and end - y < .3 * ch and gap - end >= 4 and gap < .5 * H:
            cut_top = gap - 2
        y = ys[-1]; st = y
        while st > 0 and filled[st]: st -= 1
        gap = st
        while gap > 0 and not filled[gap]: gap -= 1
        if y > .88 * H and y - st < .3 * ch and st - gap >= 4 and gap > .5 * H:
            cut_bot = H - (gap + 2)
    if cut_top or cut_bot:
        im = im.crop((0, cut_top, im.size[0], H - cut_bot))
    return im, cut_top + cut_bot


def chroma_key(im, green=False):
    """일러스트용 색 차이 키잉: 분홍(#FF00FF) 또는 초록(#00FF00) 기운이 얼마나 강한지로 투명도를 정한다.
    그림 틈에 갇힌 배경·외곽선에 섞인 배경까지 지우고, 섞인 색은 배경 기운을 빼서 되살린다. 보라·분홍 옷(색이 한쪽으로 치우침)은 남김."""
    import numpy as np
    from scipy import ndimage
    a = np.array(im.convert('RGBA')).astype(np.float32)
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    if green:
        k = g - np.maximum(r, b)
        hue_ok = np.ones_like(k, bool)
    else:
        k = np.minimum(r, b) - g
        hue_ok = np.abs(r - b) < 45  # 분홍 배경은 R≈B. 보라(파랑 쪽)·핫핑크(빨강 쪽)는 남김
    t0, t1 = 70.0, 170.0
    alpha = np.where(hue_ok, 1 - np.clip((k - t0) / (t1 - t0), 0, 1), 1.0)
    alpha = ndimage.grey_opening(alpha, size=(2, 2))  # 한 점짜리 구멍·점 정리
    sp = np.where(hue_ok, np.clip(k - 20, 0, None), 0)
    if green:
        a[:, :, 1] = g - sp
    else:
        a[:, :, 0] = r - sp; a[:, :, 2] = b - sp
    a[:, :, 3] = a[:, :, 3] * alpha
    out = Image.fromarray(a.clip(0, 255).astype(np.uint8))
    al = np.array(out)[:, :, 3] > 24
    lab, n = ndimage.label(al)
    if n:
        sz = ndimage.sum(al, lab, range(1, n + 1))
        arr = np.array(out); arr[np.isin(lab, np.nonzero(sz < 40)[0] + 1), 3] = 0
        out = Image.fromarray(arr)
    return out


def despill_edge(im, bg=(255, 0, 255), band=4):
    """분홍(또는 초록) 배경을 지운 뒤 테두리에 남는 배경색 번짐을 뺀다. 테두리 band px 안에서만(캐릭터 안의 분홍은 그대로)."""
    import numpy as np
    from scipy import ndimage
    a = np.array(im.convert('RGBA')).astype(np.float32)
    al = a[:, :, 3] > 8
    edge = al & ndimage.binary_dilation(~al, iterations=band)
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    if bg[1] > 200:  # 초록 배경
        spill = np.clip(g - np.maximum(r, b), 0, None)
        a[:, :, 1] = np.where(edge, g - spill, g)
    else:
        spill = np.clip(np.minimum(r, b) - g, 0, None)
        a[:, :, 0] = np.where(edge, r - spill * .85, r)
        a[:, :, 2] = np.where(edge, b - spill * .85, b)
        # 거의 배경색인 테두리 픽셀은 지움
        d = np.abs(r - bg[0]) + np.abs(g - bg[1]) + np.abs(b - bg[2])
        a[:, :, 3] = np.where(edge & (d < 150), 0, a[:, :, 3])
    # 떨어진 작은 점(배경 찌꺼기) 지움
    al2 = a[:, :, 3] > 24
    lab, n = ndimage.label(al2)
    if n:
        sz = ndimage.sum(al2, lab, range(1, n + 1))
        small = np.isin(lab, np.nonzero(sz < 40)[0] + 1)
        a[small, 3] = 0
    return Image.fromarray(a.clip(0, 255).astype(np.uint8))


def keep_main(im):
    """가장 큰 덩어리(아이콘 본체)와 이어지지 않은 조각을 모두 지운다."""
    try:
        import numpy as np
        from scipy import ndimage
    except Exception:
        return im
    a = np.array(im.convert('RGBA'))
    mask = a[:, :, 3] > 10
    lab, n = ndimage.label(mask, structure=np.ones((3, 3)))
    if n < 2:
        return im
    sizes = ndimage.sum(mask, lab, range(1, n + 1))
    main = int(np.argmax(sizes)) + 1
    a[(lab != main) & (lab != 0), 3] = 0
    return Image.fromarray(a)


def edge_touch(im):
    """가장자리 2px 안에 그림이 있는 비율 (아이콘은 8px 여백이라 0이어야 함)."""
    a = im.convert('RGBA').getchannel('A')
    w, h = a.size
    px = a.load()
    pts = [(x, y) for x in range(w) for y in (0, 1, h - 2, h - 1)] + [(x, y) for y in range(h) for x in (0, 1, w - 2, w - 1)]
    return sum(1 for p in pts if px[p] > 40) / len(pts)


def classify(fname):
    """파일 이름 → [위 폴더, (아이콘이면) 하위 폴더, 파일] (옛 폴더 구조와 같은 모양)."""
    b = fname
    if b.startswith('skill_'):
        return ['icons', 'skill', b]
    if b.startswith(UI_PREFIX):
        return ['icons', 'ui', b]
    if b.startswith(('nov_', 'job_', 'set_', 'mat_', 'potion_', 'item_')):
        return ['icons', 'item', b]
    if b.startswith('npc_'):
        return ['npc', b]
    if b.startswith('bg_'):
        return ['backgrounds', b]
    if b.startswith('char_'):
        return ['characters', b]
    if b.startswith('mon_'):
        return ['monsters', b]
    if b.startswith('boss_'):
        return ['bosses', b]
    if b.startswith('card_'):
        return ['cards', b]
    return None


def handle(rel, im, names, out, rep):
    rel = rel.replace('\\', '/')
    fname = rel.split('/')[-1]
    if fname.startswith('preview') or '/preview' in rel.lower():
        return
    # 폴더 이름은 보지 않고 파일 이름으로 분류한다 (작가가 한글 폴더 등으로 나눠 보내도 됨)
    parts = classify(fname)
    if not parts:
        rep['unknown'].append(rel)
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
        want = 64 if sub in ('ui', 'skill') else 128
        if im.size != (want, want) and not (base == 'fx_victory_frame' and im.size == (256, 32)):
            return bad(f'크기 {im.size[0]}×{im.size[1]} (정해진 크기 {want}×{want}) — 반려')
        if not corners_transparent(im) and looks_checker(im):  # 그려 넣은 체크무늬는 모서리까지 불투명
            return bad('체크무늬 배경을 그림으로 그림 (진짜 투명이어야 함) — 반려')
        if sub != 'skill' and not corners_transparent(im):
            return bad('모서리가 투명하지 않음 (흰 배경·옆 그림 조각) — 반려')
        if sub != 'skill' and edge_touch(im) > 0.02:
            return bad('그림이 가장자리에 닿음 (잘린 그림·옆 그림 조각, 여백 8px 필요) — 반려')
        if sub == 'skill':  # 스킬 아이콘은 테두리 사각형 한 덩어리 — 바깥에 떨어진 글씨·선 조각은 지움
            im = keep_main(im)
        out[key] = to_data_url(fit_icon(im, ICON_PX), lossless=(sub != 'skill'), q=88)  # 스킬은 그림풍이라 손실 압축이 훨씬 작음
    elif top == 'npc':
        m = re.match(r'npc_(shop|smith|onsen|inn|training)_sheet$', base)
        if not m:
            return bad('NPC 파일 이름은 npc_<shop|smith|onsen|inn|training>_sheet.png')
        code = m.group(1)
        w, h = im.size
        A = im.convert('RGBA').getchannel('A')
        has_alpha = A.histogram()[0] > A.width * A.height * 0.01  # 완전 투명 픽셀이 1% 넘으면 이미 배경이 지워진 시트
        for r in range(3):
            for c in range(6):  # 칸 크기가 나누어떨어지지 않아도 고르게 자름
                cell = im.crop((round(c * w / 6), round(r * h / 3), round((c + 1) * w / 6), round((r + 1) * h / 3))).convert('RGBA')
                if not has_alpha:  # 이미 투명 배경으로 온 시트는 배경 지우기를 하지 않음 (그림 훼손 방지)
                    cell = remove_flat_bg(cell)
                cell = drop_neighbor_bits(cell)
                cell.thumbnail(NPC_CELL, Image.LANCZOS)
                out[f'npc/{code}_{r}_{c}'] = to_data_url(cell, lossless=False, q=75, aq=60)  # 한 컷 약 23KB
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
    elif top == 'characters' and base.endswith('_illust'):
        # 직업 일러스트(홈·캐릭터 화면용 전신 그림): 단색 배경 지우기 → 안 되면 rembg → 그림만 남게 자르고 줄임
        code = base[5:-7]
        c0 = im.convert('RGB').getpixel((0, 0))  # 배경색(위 모서리)
        if (c0[0] > 180 and c0[2] > 180 and c0[1] < 90) or (c0[1] > 180 and max(c0[0], c0[2]) < 90):
            im2 = chroma_key(im, green=c0[1] > 180)  # 분홍·초록 배경: 색 차이로 지움(틈·외곽선 섞임까지)
        else:
            im2 = key_bg(im)
        if not corners_transparent(im2) and im2.getchannel('A').getextrema()[0] > 0:
            im2 = remove_flat_bg(im.convert('RGB'))
        bb = im2.getchannel('A').point(lambda v: 255 if v > 24 else 0).getbbox()
        if not bb:
            return bad('일러스트에서 사람을 못 찾음(배경만 있음)')
        im2 = im2.crop(bb)
        w, h = im2.size
        if bb[1] <= 1 or bb[3] >= im.size[1] - 1:
            bad('일러스트가 위나 아래 끝에 닿음(머리·발 잘림 의심) — 넣긴 했지만 확인 필요')
        if h > ILLUST_H:
            im2 = im2.resize((round(w * ILLUST_H / h), ILLUST_H), Image.LANCZOS)
        out[f'char/{code}_illust'] = to_data_url(im2, lossless=False, q=80, aq=70)
    elif top == 'characters':
        m = re.match(r'char_(.+)_(front|back)$', base)
        if not m:
            return bad('캐릭터 시트 이름은 char_<코드>_front.png / _back.png')
        im = key_bg(im)
        im, cutp = drop_text_bands(im, 8 if m.group(2) == 'back' else 5)
        if cutp:
            rep.setdefault('fixed', []).append(f'{base}: 위·아래 글자 줄 {cutp}px 잘라 냄')
        cw = im.size[0] / 4
        if cw > 160:  # 나노바나나처럼 크게 온 그림은 칸 128px 기준으로 줄임
            im = im.resize((512, round(im.size[1] * 512 / im.size[0])), Image.LANCZOS)
        if not m.group(1).startswith('novice_') or m.group(1) == 'novice_f':
            # 통짜 캐릭터 시트는 칸 밖으로 넘친 프레임을 다시 정렬 (노비스 부품은 겹쳐야 해서 그대로)
            im = fix_sheet_im(im, m.group(2), rep, base)
        e, issues = sheet_entry(im, m.group(2))
        if im.size[0] > 4 * 128: e['s'] = round(im.size[0] / 4 / 128, 3)
        for x in issues:
            if '줄 수' not in x: bad(x)
        out[f'char/{m.group(1)}_{m.group(2)}'] = e
        if m.group(1) == 'novice_hair':  # 머리카락은 갈색 1장만 받고, 게임의 7가지 머리색은 여기서 칠해 만든다
            for i, col in enumerate(HAIR_COLS):
                e2, _ = sheet_entry(recolor(im, col), m.group(2))
                out[f'char/novice_hair_hair{i}_{m.group(2)}'] = e2
    elif top == 'monsters':
        m = re.match(r'mon_m(\d+)$', base)
        if not m:
            return bad('몬스터 시트 이름은 mon_m0.png ~ mon_m19.png')
        im = fix_sheet_im(im, 'mon', rep, base)  # 칸에 안 맞게 그려진 프레임 재정렬·잘림 처리 (tools/fix_sheet.py)
        e, issues = sheet_entry(im, 'mon')
        e['s'] = round(im.size[0] / 4 / 96, 3)  # 칸이 원래(96px)보다 크면 그 비율 — 게임이 그만큼 확대해 화면 크기를 맞춤
        for x in issues:
            if '줄 수' not in x: bad(x)
        out['mon/m' + m.group(1)] = e
    elif top == 'bosses':
        m = re.match(r'boss_b(\d+)$', base)
        if not m:
            return bad('보스 시트 이름은 boss_b0.png ~ boss_b9.png')
        im = fix_sheet_im(im, 'boss', rep, base)
        sc = round(im.size[0] / 4 / 160, 3)
        c8 = round(im.size[0] / 4 * .8)  # 칸 ×0.8 (용량), 칸 크기는 정수로
        im = im.convert('RGBA').resize((c8 * 4, c8 * round(im.size[1] / (im.size[0] / 4))), Image.LANCZOS)
        e, issues = sheet_entry(im, 'boss')
        e['s'] = sc
        e['src'] = to_data_url(im.convert('RGBA'), lossless=False, q=82, aq=70)
        for x in issues:
            if '줄 수' not in x: bad(x)
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
    items = []
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
                items.append((info.filename, im))
        elif os.path.isdir(a):
            for dp, _, fs in os.walk(a):
                for f in fs:
                    if f.lower().endswith('.png'):
                        p = os.path.join(dp, f)
                        items.append((os.path.relpath(p, a), Image.open(p)))
        elif a.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')) and os.path.isfile(a):  # 그림 파일 하나씩도 받음
            items.append((os.path.basename(a).rsplit('.', 1)[0] + '.png', Image.open(a)))
    for rel, im in stitch_halves(items, rep):
        handle(rel, im, names, out, rep)
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
    if rep.get('fixed'):
        lines += ['[자동으로 고친 것 — 원본은 잘림·어긋남, 다시 받으면 더 좋음]'] + ['  ' + x for x in rep['fixed']] + ['']
    lines += ['[넣은 것]'] + ['  ' + x for x in rep['ok']]
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    open(REPORT, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    print('\n'.join(lines[:3]))
    if not dry:
        print('index.html 크기:', round(os.path.getsize(INDEX) / 1e6, 2), 'MB')


if __name__ == '__main__':
    main()
