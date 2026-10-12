"""Repaints mismatched weapons on the PixelLab job sprites without spending credits.

Each recipe erases the wrong weapon (rects), draws the right one with pixel primitives,
then redraws the hand pixels on top so the weapon reads as held.
in:  assets/raw/jobs/cut/front{i}.png   out: assets/jobs/front{i}.png
"""
import math, os
from PIL import Image

OUT = (38, 30, 48, 255)
WOOD = [(196, 142, 92), (150, 100, 62), (112, 72, 46)]
STEEL = [(232, 236, 244), (176, 184, 200), (120, 128, 148)]
GOLD = [(255, 226, 120), (232, 178, 56), (176, 124, 34)]
STRING = (236, 232, 220, 255)


def px(im, x, y, c):
    if 0 <= x < im.width and 0 <= y < im.height:
        im.putpixel((x, y), c if len(c) == 4 else c + (255,))


def outline(im, cells):
    """Dark outline around a set of filled cells."""
    for x, y in list(cells):
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            q = (x + dx, y + dy)
            if q not in cells:
                px(im, *q, OUT)


def rod(im, p0, p1, r0, r1, ramp, cells=None):
    """Capsule from p0 to p1 with radius r0->r1, shaded light on the upper side."""
    (x0, y0), (x1, y1) = p0, p1
    L = math.hypot(x1 - x0, y1 - y0) or 1
    ux, uy = (x1 - x0) / L, (y1 - y0) / L
    nx, ny = uy, -ux
    if ny > 0 or (ny == 0 and nx > 0): nx, ny = -nx, -ny
    cells = {} if cells is None else cells
    for y in range(64):
        for x in range(64):
            qx, qy = x + .5 - x0, y + .5 - y0
            t = qx * ux + qy * uy; d = qx * nx + qy * ny
            if t < -.5 or t > L + .5: continue
            r = r0 + (r1 - r0) * max(0, min(1, t / L))
            if abs(d) <= r:
                lv = 0 if d > r - 1 else (2 if d < -r + 1 else 1)
                cells[(x, y)] = ramp[lv]
    return cells


def paint(im, cells):
    outline(im, cells)
    for (x, y), c in cells.items(): px(im, x, y, c)


def erase(im, rects, keep=None):
    for x0, y0, x1, y1 in rects:
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if keep and im.getpixel((x, y))[:3] in keep: continue
                im.putpixel((x, y), (0, 0, 0, 0))


def is_skin(p):
    r, g, b = p[:3]
    return r > 170 and g > 110 and r > g > b and r - b > 40


def restore(im, src, rects, skin_only=False):
    for x0, y0, x1, y1 in rects:
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                p = src.getpixel((x, y))
                if p[3] > 128 and (not skin_only or is_skin(p)): im.putpixel((x, y), p)


def bow(im, cx, top, bottom, bulge, facing=-1):
    """Vertical longbow: limbs curve towards `facing` (-1 = left), string on the other side."""
    cells = {}
    h = bottom - top
    for i in range(h * 3 + 1):
        t = i / (h * 3) * 2 - 1
        x = cx + facing * bulge * (1 - t * t); y = top + (t + 1) / 2 * h
        for w in (0, -facing):
            cells[(round(x) + w, round(y))] = WOOD[0 if w == 0 else 2] if abs(t) < .85 else WOOD[1]
    for y in range(top + h // 2 - 2, top + h // 2 + 3):  # leather grip
        cells[(round(cx + facing * bulge), y)] = (110, 64, 40)
        cells[(round(cx + facing * bulge) - facing, y)] = (82, 46, 30)
    paint(im, cells)
    for y in range(top + 1, bottom):
        if (cx - facing, y) not in cells: px(im, cx - facing, y, STRING)


STAR9 = ["....X....",
         "...XLX...",
         "...XLX...",
         ".XXLMLXX.",
         "XLLMOMMDX",
         ".XXLMDXX.",
         "...XDX...",
         "...XDX...",
         "....X...."]
STAR7 = ["...X...",
         "..XLX..",
         ".XLMDX.",
         "XLMOMDX",
         ".XLMDX.",
         "..XDX..",
         "...X..."]


def shuriken(im, cx, cy, big=True):
    """Four-pointed throwing star stamped from a hand-drawn bitmap."""
    bm = STAR9 if big else STAR7
    h = len(bm) // 2
    col = {'X': OUT, 'L': STEEL[0] + (255,), 'M': STEEL[1] + (255,), 'D': STEEL[2] + (255,), 'O': OUT}
    for j, row in enumerate(bm):
        for i, ch in enumerate(row):
            if ch != '.': px(im, cx - h + i, cy - h + j, col[ch])


def holy_staff(im, x, top, bottom):
    paint(im, rod(im, (x, top + 6), (x, bottom), 1.0, 1.0, WOOD))
    cells = {}
    for y in range(top, top + 9): cells[(x, y)] = GOLD[1]; cells[(x + 1, y)] = GOLD[2]
    for xx in range(x - 3, x + 5): cells[(xx, top + 3)] = GOLD[0]; cells[(xx, top + 4)] = GOLD[1]
    paint(im, cells)
    px(im, x, top + 3, (255, 248, 210))


def blade(im, base, tip, r=1.3, guard=3, ramp=STEEL):
    """Straight blade from base (hilt) to tip with a small gold crossguard at the base."""
    paint(im, rod(im, base, tip, r, .4, ramp))
    (x0, y0), (x1, y1) = base, tip
    L = math.hypot(x1 - x0, y1 - y0) or 1
    nx, ny = (y1 - y0) / L, -(x1 - x0) / L
    cells = {}
    for k in range(-guard, guard + 1):
        cells[(round(x0 + nx * k), round(y0 + ny * k))] = GOLD[1]
    paint(im, cells)


def crossbow(im, hx, hy, length=13, span=6):
    """Small crossbow pointing left from the hand: stock, bow limbs at the front, string."""
    cells = rod(im, (hx, hy), (hx - length, hy), 1.0, 1.0, WOOD)
    fx = hx - length + 2
    for k in range(-span, span + 1):
        cells[(fx + abs(k) // 3, hy + k)] = STEEL[1] if abs(k) < span else STEEL[2]
    paint(im, cells)
    for k in range(-span + 1, span):
        if (fx + 2, hy + k) not in cells: px(im, fx + 2 + abs(k) // 3, hy + k, STRING)


RECIPES = {
    # 궁수: knife + mace -> short bow in the left hand
    1: lambda im, src: (erase(im, [(9, 28, 18, 41), (42, 30, 52, 38)]),
                        bow(im, 20, 30, 58, 3, -1),
                        restore(im, src, [(14, 41, 20, 47), (39, 37, 45, 42)], skin_only=True)),
    # 도적: golden wand -> dagger held up
    2: lambda im, src: (erase(im, [(47, 22, 55, 37)]),
                        blade(im, (47, 38), (53, 26), 1.3, 2),
                        restore(im, src, [(43, 37, 49, 44)], skin_only=True)),
    # 양손검 기사: sideways cleaver -> greatsword held upright beside the body
    5: lambda im, src: (erase(im, [(0, 37, 21, 49)]),
                        blade(im, (20, 40), (20, 6), 2.0, 4),
                        paint(im, rod(im, (20, 41), (20, 48), .8, .8, WOOD)),
                        restore(im, src, [(19, 40, 26, 48)], skin_only=True)),
    # 트랩 궁수: wrench -> small crossbow
    8: lambda im, src: (erase(im, [(10, 30, 20, 40)]),
                        crossbow(im, 24, 43, 14, 6),
                        restore(im, src, [(21, 40, 28, 47)], skin_only=True)),
    # 단검 도적: empty hands -> a dagger in each hand
    10: lambda im, src: (blade(im, (25, 38), (19, 28), 1.2, 2), blade(im, (45, 38), (51, 28), 1.2, 2),
                         restore(im, src, [(22, 37, 29, 45), (41, 37, 48, 46)], skin_only=True)),
    # 활 궁수: the curved stick on the left and the rod on the right were not a bow
    9: lambda im, src: (erase(im, [(5, 15, 16, 41), (36, 44, 50, 53)]),
                        bow(im, 20, 20, 60, 4, -1),
                        restore(im, src, [(15, 40, 20, 46)])),
    # 표창 도적: dagger -> shuriken in hand and one in flight
    11: lambda im, src: (erase(im, [(39, 21, 54, 39)]),
                         restore(im, src, [(39, 33, 47, 43)], skin_only=True),
                         shuriken(im, 45, 35), shuriken(im, 55, 22, big=False),
                         restore(im, src, [(40, 37, 47, 43)], skin_only=True)),
    # 사제: thin curved blade -> golden cross staff
    13: lambda im, src: (erase(im, [(6, 18, 15, 49)]),
                         holy_staff(im, 12, 12, 56),
                         restore(im, src, [(11, 35, 17, 43)])),
}

if __name__ == '__main__':
    os.makedirs('assets/jobs', exist_ok=True)
    for i in range(20):
        src = Image.open(f'assets/raw/jobs/cut/front{i}.png').convert('RGBA')
        im = src.copy()
        if i in RECIPES: RECIPES[i](im, src)
        im.save(f'assets/jobs/front{i}.png')
