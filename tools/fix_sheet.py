#!/usr/bin/env python3
"""칸에 안 맞게 그려진 스프라이트 시트를 다시 정렬한다.

쓰는 법:  python3 tools/fix_sheet.py 입력.png 출력.png mon|boss [--sheet 확인용.png]

하는 일
1) 그림 덩어리(투명이 아닌 부분)를 찾아 원래 칸(왼→오, 위→아래)에 배정한다. 칸 경계를 넘어 그려진 부분도 그 프레임에 붙인다.
2) 줄마다 발바닥(바닥선)과 가운데를 맞춘다 → 동작을 바꿔도 몸이 튀지 않음. 줄 안의 움직임(점프 등)은 그대로.
3) 칸을 넉넉히 키워 다시 배열한다 → 잘림 없음. 게임에는 원래 칸 크기 비율(s)을 함께 넘겨 화면 크기는 그대로.
4) 원본에서 이미 잘려 나간 프레임(칸 경계에서 일자로 끊김)은 같은 줄의 멀쩡한 프레임으로 바꾸고 기록한다.
"""
import sys, json
import numpy as np
from PIL import Image
from scipy import ndimage

SPEC = {'mon': (96, [4, 4, 2, 3]), 'boss': (160, [4, 4, 4, 2, 2, 4])}
COLS = 4


def frames_of(im, cell, counts):
    a = np.array(im.convert('RGBA'))
    alpha = a[:, :, 3] > 20
    H, W = alpha.shape
    lab, n = ndimage.label(alpha, structure=np.ones((3, 3)))
    objs = ndimage.find_objects(lab)
    areas = ndimage.sum(alpha, lab, range(1, n + 1))
    body_min = 0.05 * cell * cell
    pieces = []  # (mask_sl, ys, xs) 몸통 조각들
    parts = []
    for k in range(1, n + 1):
        sl = objs[k - 1]
        ys, xs = np.nonzero(lab[sl] == k)
        ys = ys + sl[0].start; xs = xs + sl[1].start
        if areas[k - 1] >= body_min:
            # 이웃 프레임과 붙어 버린 몸통은 칸 경계에서 나눔
            w = xs.max() - xs.min(); h = ys.max() - ys.min()
            if w > 1.2 * cell or h > 1.25 * cell:
                # 붙어 버린 이웃 프레임: 칸 경계 근처에서 그림이 가장 얇은 줄을 찾아 나눔(행이 어긋나 있어도 맞게)
                def cuts(v, lo, hi, do):
                    if not do:
                        return []
                    res = []
                    for b0 in range(int(np.ceil(lo / cell)) * cell, int(hi) + 1, cell):
                        if b0 <= lo or b0 >= hi:
                            continue
                        win = np.arange(max(lo + 1, b0 - int(.4 * cell)), min(hi, b0 + int(.4 * cell)))
                        cnt = np.bincount(v - lo, minlength=hi - lo + 1)[win - lo]
                        res.append(int(win[np.argmin(cnt)]))
                    return res
                ycut = cuts(ys, ys.min(), ys.max(), h > 1.25 * cell)
                xcut = cuts(xs, xs.min(), xs.max(), w > 1.2 * cell)
                key = np.searchsorted(ycut, ys, side='right') * 100 + np.searchsorted(xcut, xs, side='right')
                for v in np.unique(key):
                    m = key == v
                    if m.sum() >= body_min * .3:
                        pieces.append((ys[m], xs[m]))
                    else:
                        parts.append((ys[m], xs[m]))
            else:
                pieces.append((ys, xs))
        else:
            parts.append((ys, xs))
    slot_pts = {}
    boxes = {}
    for ys, xs in pieces:
        r = min(int(ys.mean() // cell), len(counts) - 1)
        c = min(int(xs.mean() // cell), COLS - 1, counts[r] - 1)
        slot_pts.setdefault((r, c), []).append((ys, xs))
    for key, L in slot_pts.items():
        ys = np.concatenate([p[0] for p in L]); xs = np.concatenate([p[1] for p in L])
        boxes[key] = (ys.min(), ys.max(), xs.min(), xs.max())
    # 작은 조각(물방울·불꽃)은 가장 가까운 몸통에, 멀면 버림
    for ys, xs in parts:
        cy, cx = ys.mean(), xs.mean(); best = None
        for key, (y0, y1, x0, x1) in boxes.items():
            d = max(y0 - cy, 0, cy - y1) + max(x0 - cx, 0, cx - x1)
            if best is None or d < best[0]:
                best = (d, key)
        if best and best[0] < .3 * cell:
            slot_pts[best[1]].append((ys, xs))
    out = {}
    for (r, c), L in slot_pts.items():
        ys = np.concatenate([p[0] for p in L]); xs = np.concatenate([p[1] for p in L])
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        px = np.zeros((y1 - y0, x1 - x0, 4), np.uint8)
        px[ys - y0, xs - x0] = a[ys, xs]
        # 원본에서 잘린 흔적: 몸통이 칸 경계·그림 끝에서 일자로 끊김
        # 원본에서 잘린 흔적: 칸 경계선 바로 안쪽에 그림이 꽉 차 있는데 경계 바깥은 텅 빔(일자로 썰린 모양)
        cut = []
        strong = a[:, :, 3] > 180
        own = np.zeros_like(alpha); own[ys, xs] = True; own &= strong
        for b0 in range((y0 // cell + 1) * cell, y1 + 1, cell):
            if 0 < b0 < H:
                n_in = (own[b0 - 1] & ~alpha[b0]).sum(); n_out = (own[b0] & ~alpha[b0 - 1]).sum()
                if n_in > .08 * cell: cut.append(('B', n_in))
                if n_out > .08 * cell: cut.append(('T', n_out))
            elif b0 == H and own[H - 1].sum() > .08 * cell:
                cut.append(('B', own[H - 1].sum()))
        for b0 in range((x0 // cell + 1) * cell, x1 + 1, cell):
            if 0 < b0 < W:
                n1 = (own[:, b0 - 1] & ~alpha[:, b0]).sum(); n2 = (own[:, b0] & ~alpha[:, b0 - 1]).sum()
                if n1 > .08 * cell: cut.append(('R', n1))
                if n2 > .08 * cell: cut.append(('L', n2))
        if y0 == 0 and own[0].sum() > .08 * cell: cut.append(('T', own[0].sum()))
        if x0 == 0 and own[:, 0].sum() > .08 * cell: cut.append(('L', own[:, 0].sum()))
        out[(r, c)] = {'px': px, 'x0': x0 - c * cell, 'y0': y0 - r * cell, 'w': x1 - x0, 'h': y1 - y0, 'cut': cut}
    return out


def repack(im, kind):
    cell, counts = SPEC[kind]
    sc = im.size[0] / (cell * COLS)  # 받은 시트가 다른 배율이면 맞춤
    if abs(sc - 1) > .01:
        cell = int(round(cell * sc))
    F = frames_of(im, cell, counts)
    log = []
    # 위아래로 많이 잘린 프레임(경계에 닿은 길이가 칸의 35% 넘음)은 같은 줄의 멀쩡한 프레임으로 바꾸고,
    # 조금 잘린 것(꼬리·빛 끝)은 잘린 가장자리를 부드럽게 흐려 일자로 썰린 티가 안 나게 한다.
    last = len(counts) - 1
    for r, n in enumerate(counts):
        for c in range(n):
            f = F.get((r, c))
            if f is None and r == last:
                continue  # 쓰러짐 마지막 칸이 비어 있으면(사라짐) 그대로
            severe = f is None or any(v > .35 * cell and e in 'BT' for e, v in f['cut'])  # 위아래로 몸이 썰린 것만 교체, 옆(꼬리·빛 끝)은 흐리게
            if severe:
                good = [F[(r, k)] for k in list(range(c - 1, -1, -1)) + list(range(c + 1, n)) if (r, k) in F and not any(v > .35 * cell and e in 'BT' for e, v in F[(r, k)]['cut'])]
                if not good:
                    good = [F[(0, k)] for k in range(counts[0]) if (0, k) in F and not F[(0, k)]['cut']]
                if good:
                    log.append(f'{r + 1}줄 {c + 1}번 ' + ('비어 있음' if f is None else f"많이 잘림({''.join(e for e, _ in f['cut'])})") + ' → 같은 줄 다른 프레임으로 대체')
                    F[(r, c)] = dict(good[0], cut=[])
            elif f['cut']:
                px = f['px'].astype(np.float32)
                k = 6
                ramp = np.linspace(.15, 1, k)
                for e, _ in f['cut']:
                    if e == 'B': px[-k:, :, 3] *= ramp[::-1][:, None]
                    if e == 'T': px[:k, :, 3] *= ramp[:, None]
                    if e == 'R': px[:, -k:, 3] *= ramp[::-1][None, :]
                    if e == 'L': px[:, :k, 3] *= ramp[None, :]
                f['px'] = px.clip(0, 255).astype(np.uint8)
                log.append(f"{r + 1}줄 {c + 1}번 조금 잘림({''.join(e for e, _ in f['cut'])}) → 가장자리 부드럽게")
                f['cut'] = []
    # 줄마다 바닥선·가운데를 기준 줄(첫 줄)에 맞춤
    base_b, base_cx = None, None
    shift = {}
    for r, n in enumerate(counts):
        fr = [F[(r, c)] for c in range(n) if (r, c) in F]
        if not fr:
            continue
        b = float(np.median([f['y0'] + f['h'] for f in fr]))
        cx = float(np.median([f['x0'] + f['w'] / 2 for f in fr]))
        if base_b is None:
            base_b, base_cx = b, cx
        shift[r] = (base_cx - cx, base_b - b)
    # 원래 칸(가운데·바닥선)이 새 칸 가운데에 오도록, 모두 들어가는 크기 계산
    ctr_x, ctr_y = cell / 2, cell / 2  # 원래 칸 가운데
    need = 0
    for (r, c), f in F.items():
        dx, dy = shift.get(r, (0, 0))
        L = f['x0'] + dx; R = L + f['w']; T = f['y0'] + dy; Bm = T + f['h']
        need = max(need, ctr_x - L, R - ctr_x, ctr_y - T, Bm - ctr_y)
    M = int(np.ceil(max(need * 2 + 6, cell)))
    M += M % 2
    rows = len(counts)
    sheet = Image.new('RGBA', (M * COLS, M * rows), (0, 0, 0, 0))
    off = M / 2 - cell / 2
    for (r, c), f in F.items():
        dx, dy = shift.get(r, (0, 0))
        x = int(round(c * M + off + f['x0'] + dx))
        y = int(round(r * M + off + f['y0'] + dy))
        sheet.alpha_composite(Image.fromarray(f['px']), (x, y))
    return sheet, M / cell, log, cell


def main():
    src, dst, kind = sys.argv[1], sys.argv[2], sys.argv[3]
    im = Image.open(src).convert('RGBA')
    sheet, s, log, cell = repack(im, kind)
    sheet.save(dst)
    print(json.dumps({'file': src.split('/')[-1], 'scale': round(s, 3), 'cell': cell, 'new_cell': sheet.size[0] // COLS, 'fixed': log}, ensure_ascii=False))


if __name__ == '__main__':
    main()
