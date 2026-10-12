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
print(sum(len(v) for v in data.values()), 'bytes of data URIs')
