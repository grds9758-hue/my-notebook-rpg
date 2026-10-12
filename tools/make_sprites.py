"""Builds the in-game sprite set from the PixelLab outputs in assets/.

Outputs assets/game/*.png and assets/game/sprites.json (data URIs) for embedding:
  body0..3   bald novice body per skin tone
  fist0..3   fist overlay per skin tone (drawn above the weapon)
  hair0..6   hair layer per color (brown, black, blonde, red, silver, blue, pink)
  wpn0..6    held weapon layer per weapon band (64x64, rotated into the hand)
  wico0..6   upright weapon icon per band (32x32)
"""
import base64, io, json, math, os
from PIL import Image

A = 'assets/'
OUT = A + 'game/'
os.makedirs(OUT, exist_ok=True)

SKIN_BASE = (246, 195, 159)
SKIN_SET = {(246, 195, 159), (225, 154, 126), (178, 119, 89), (201, 135, 107), (231, 167, 136),
            (214, 142, 115), (188, 128, 98), (164, 106, 75), (110, 60, 45), (255, 214, 184)}
SKINS = [(246, 195, 159), (231, 167, 127), (190, 126, 88), (128, 82, 56)]


def skin_swap(im, target):
    im = im.copy()
    k = [t / b for t, b in zip(target, SKIN_BASE)]
    for y in range(im.height):
        for x in range(im.width):
            p = im.getpixel((x, y))
            if p[3] and p[:3] in SKIN_SET:
                im.putpixel((x, y), tuple(min(255, round(c * f)) for c, f in zip(p[:3], k)) + (255,))
    return im


body = Image.open(A + 'novice_bald.png').convert('RGBA')
fist = Image.open(A + 'hand_fist.png').convert('RGBA')
sprites = {}
for i, s in enumerate(SKINS):
    sprites[f'body{i}'] = skin_swap(body, s)
    sprites[f'fist{i}'] = skin_swap(fist, s)

for i, c in enumerate(['brown', 'black', 'blonde', 'red', 'silver', 'blue', 'pink']):
    h = Image.open(A + f'hair/hair1_{c}.png').convert('RGBA')
    for y in range(64):
        for x in range(64):
            if h.getpixel((x, y))[:3] in SKIN_SET:
                h.putpixel((x, y), (0, 0, 0, 0))
    sprites[f'hair{i}'] = h

# weapons: recolor the PixelLab bat per material
bat = Image.open(A + 'raw/weapon_1_obj2.png').convert('RGBA')
WOOD = {(184, 131, 94): 0, (139, 93, 61): 1, (116, 74, 57): 2, (101, 64, 45): 2, (89, 56, 54): 3, (82, 50, 50): 3}
RAMPS = {
    'oak': [(150, 98, 62), (112, 70, 44), (90, 56, 36), (60, 36, 30)],
    'steel': [(206, 212, 224), (156, 164, 180), (118, 124, 140), (58, 60, 74)],
    'mithril': [(200, 236, 248), (132, 194, 228), (96, 150, 198), (46, 66, 108)],
    'bone': [(246, 238, 216), (216, 202, 172), (176, 158, 126), (96, 62, 60)],
}


def recolor(im, ramp, head_only=False):
    im = im.copy()
    for y in range(im.height):
        for x in range(im.width):
            p = im.getpixel((x, y))
            if p[3] and p[:3] in WOOD and (not head_only or y <= 20):
                im.putpixel((x, y), ramp[WOOD[p[:3]]] + (255,))
    return im


def put(im, pts, c):
    for x, y in pts:
        im.putpixel((x, y), c + (255,))


w0 = bat
w1 = recolor(bat, RAMPS['oak'])
w2 = bat.copy()  # nails poking out of both sides of the head
for y in (3, 7, 11, 15, 19):
    put(w2, [(12, y), (19, y + 2 if y < 19 else y)], (196, 202, 214))
    put(w2, [(11, y), (20, y + 2 if y < 19 else y)], (88, 92, 108))
    put(w2, [(15, y + 1)], (120, 124, 140))
w3 = bat.copy()  # iron bands across the head
for y in (4, 5, 14, 15):
    put(w3, [(x, y) for x in range(14, 18)], (150, 156, 172) if y in (4, 14) else (108, 114, 130))
    put(w3, [(13, y), (18, y)], (58, 60, 74))
w4 = recolor(recolor(bat, RAMPS['steel'], head_only=True), RAMPS['oak'])
w5 = recolor(recolor(bat, RAMPS['mithril'], head_only=True), RAMPS['oak'])
w6 = recolor(bat, RAMPS['bone'])
put(w6, [(15, 6), (16, 6), (15, 7), (16, 12), (15, 13), (16, 13)], (204, 52, 64))
weapons = [w0, w1, w2, w3, w4, w5, w6]


def hold(w, ang=35.0, gfe=4.0, hx=21, hy=45):
    r = w.resize((w.width * 4, w.height * 4), Image.NEAREST).rotate(ang, Image.NEAREST, expand=True)
    r = r.resize((r.width // 4, r.height // 4), Image.NEAREST)
    px = [(x, y) for y in range(r.height) for x in range(r.width) if r.getpixel((x, y))[3] > 128]
    ex, ey = max(px, key=lambda p: p[1])
    t = math.radians(ang)
    ox = round(hx - (ex - gfe * math.sin(t))); oy = round(hy - (ey - gfe * math.cos(t)))
    layer = Image.new('RGBA', (64, 64)); layer.paste(r, (ox, oy), r)
    return layer


for i, w in enumerate(weapons):
    sprites[f'wpn{i}'] = hold(w)
    sprites[f'wico{i}'] = w

# back view (Pokemon-style battle): mirror the front sprite and cover the face with hair
HAIR_LV = {(99, 59, 54): 0, (90, 48, 42): 1, (80, 43, 36): 1, (75, 37, 32): 2, (70, 34, 29): 2, (64, 32, 24): 3}
HAIR_COLS = ['brown', 'black', 'blonde', 'red', 'silver', 'blue', 'pink']
HAIR_PAL = {'brown': [(99, 59, 54), (90, 48, 42), (75, 37, 32), (64, 32, 24)],
            'black': [(78, 74, 92), (58, 54, 70), (46, 42, 58), (36, 33, 46)],
            'blonde': [(246, 216, 132), (222, 180, 96), (186, 140, 70), (150, 104, 52)],
            'red': [(222, 100, 70), (190, 70, 52), (150, 50, 42), (118, 38, 36)],
            'silver': [(232, 234, 242), (198, 200, 216), (160, 162, 184), (124, 126, 150)],
            'blue': [(110, 150, 226), (76, 110, 190), (56, 80, 150), (42, 58, 116)],
            'pink': [(246, 168, 196), (220, 124, 164), (178, 88, 128), (140, 64, 100)]}
OUTL = (38, 30, 48, 255)
# back pose (PixelLab, 3/4 from behind, club on the shoulder) cut into body / hair / club layers
bp = Image.open(A + 'raw/back_pose1.png').convert('RGBA')
B_HAIR = {(94, 72, 81): 0, (66, 45, 55): 1, (55, 33, 43): 2}
B_LINE = {(43, 21, 31), (48, 26, 35)}
B_SKIN = {(237, 194, 168), (215, 140, 131), (205, 128, 120), (235, 168, 160), (244, 187, 186), (187, 112, 104),
          (169, 99, 88), (158, 92, 80), (145, 85, 71), (138, 80, 66)}
B_CLUB = {(182, 124, 74): 0, (125, 77, 45): 1, (113, 67, 50): 2, (95, 57, 38): 2, (78, 48, 31): 3, (72, 43, 28): 3, (68, 40, 25): 3}
WOOD_RAMP = [(184, 131, 94), (139, 93, 61), (116, 74, 57), (82, 50, 50)]
CLUB_RAMPS = [WOOD_RAMP, RAMPS['oak'], WOOD_RAMP, WOOD_RAMP, RAMPS['steel'], RAMPS['mithril'], RAMPS['bone']]
bbase, bhair, bclub = Image.new('RGBA', (64, 64)), Image.new('RGBA', (64, 64)), Image.new('RGBA', (64, 64))
for y in range(64):
    for x in range(64):
        p = bp.getpixel((x, y))
        if p[3] <= 128: continue
        c = p[:3]
        if c in B_HAIR or (c in B_LINE and y <= 18): bhair.putpixel((x, y), p)
        elif c in B_CLUB and y <= 35: bclub.putpixel((x, y), p)
        else: bbase.putpixel((x, y), p)
op = lambda x, y: 0 <= x < 64 and 0 <= y < 64 and bp.getpixel((x, y))[3] > 128
def outline(layer):
    for y in range(64):
        for x in range(64):
            px = layer.getpixel((x, y))
            if px[3] and (px[:3] in B_LINE or any(not op(x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))):
                layer.putpixel((x, y), OUTL)
for L in (bbase, bhair, bclub): outline(L)
for k, s in enumerate(SKINS):
    kk = [t / b for t, b in zip(s, SKIN_BASE)]
    im = bbase.copy()
    for y in range(64):
        for x in range(64):
            px = im.getpixel((x, y))
            if px[3] and px[:3] in B_SKIN:
                im.putpixel((x, y), tuple(min(255, round(c * f)) for c, f in zip(px[:3], kk)) + (255,))
    sprites[f'bbody{k}'] = im
for i, c in enumerate(HAIR_COLS):
    im = bhair.copy()
    for y in range(64):
        for x in range(64):
            px = im.getpixel((x, y))
            if px[3] and px[:3] in B_HAIR:
                im.putpixel((x, y), HAIR_PAL[c][B_HAIR[px[:3]]] + (255,))
    sprites[f'bhair{i}'] = im
for i, ramp in enumerate(CLUB_RAMPS):
    im = bclub.copy()
    for y in range(64):
        for x in range(64):
            px = im.getpixel((x, y))
            if px[3] and px[:3] in B_CLUB:
                head = x < 32
                r = ramp if (head or i in (1, 6)) else RAMPS['oak'] if i >= 4 else ramp
                im.putpixel((x, y), r[B_CLUB[px[:3]]] + (255,))
    if i == 2:  # nails on the club head
        for x, y in ((16, 29), (19, 27), (22, 26), (25, 27), (18, 31)):
            if im.getpixel((x, y))[3]: im.putpixel((x, y), (196, 202, 214, 255))
    if i == 3:  # iron bands
        for x in range(12, 32):
            for y in range(24, 34):
                if im.getpixel((x, y))[3] and x in (20, 21, 27, 28) and im.getpixel((x, y))[:3] != OUTL[:3]:
                    im.putpixel((x, y), (150, 156, 172, 255) if x in (20, 27) else (108, 114, 130, 255))
    if i == 6:
        for x, y in ((18, 29), (19, 29), (24, 28)):
            if im.getpixel((x, y))[3]: im.putpixel((x, y), (204, 52, 64, 255))
    sprites[f'bwpn{i}'] = im

data = {}
for k, im in sprites.items():
    im.save(OUT + k + '.png')
    b = io.BytesIO(); im.save(b, 'PNG', optimize=True)
    data[k] = 'data:image/png;base64,' + base64.b64encode(b.getvalue()).decode()
json.dump(data, open(OUT + 'sprites.json', 'w'))

# preview sheet: each weapon on a body, and each skin
row = Image.new('RGBA', (68 * 11, 64), (244, 245, 246, 255))
for i in range(7):
    c = sprites['body0'].copy(); c.alpha_composite(sprites['hair0']); c.alpha_composite(sprites[f'wpn{i}']); c.alpha_composite(sprites['fist0'])
    row.alpha_composite(c, (i * 68, 0))
for i in range(4):
    c = sprites[f'body{i}'].copy(); c.alpha_composite(sprites[f'hair{i}']); c.alpha_composite(sprites['wpn0']); c.alpha_composite(sprites[f'fist{i}'])
    row.alpha_composite(c, ((7 + i) * 68, 0))
row.resize((row.width * 3, 192), Image.NEAREST).save(A + 'preview_game_sprites.png')
back = Image.new('RGBA', (68 * 7, 64), (244, 245, 246, 255))
for i in range(7):
    c = sprites[f'bbody{i % 4}'].copy(); c.alpha_composite(sprites[f'bhair{i}']); c.alpha_composite(sprites[f'bwpn{i}'])
    back.alpha_composite(c, (i * 68, 0))
back.resize((back.width * 3, 192), Image.NEAREST).save(A + 'preview_back_sprites.png')
print(sum(len(v) for v in data.values()), 'bytes of data URIs')
