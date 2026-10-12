import sys, math
from PIL import Image
# hold.py base.png weapon.png angle grip_from_end out_layer.png out_hand.png
base, wp, ang, gfe, out_l, out_h = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4]), sys.argv[5], sys.argv[6]
b = Image.open(base).convert('RGBA'); w = Image.open(wp).convert('RGBA')
r = w.resize((w.width*4, w.height*4), Image.NEAREST).rotate(ang, Image.NEAREST, expand=True)
r = r.resize((r.width//4, r.height//4), Image.NEAREST)
px = [(x, y) for y in range(r.height) for x in range(r.width) if r.getpixel((x, y))[3] > 128]
ex, ey = max(px, key=lambda p: p[1])
t = math.radians(ang)
HX, HY = 21, 45
ox = round(HX - (ex - gfe*math.sin(t))); oy = round(HY - (ey - gfe*math.cos(t)))
layer = Image.new('RGBA', (64, 64)); layer.paste(r, (ox, oy), r)
layer.save(out_l)
# fist overlay drawn above weapon
O, F, D = (178,119,89,255), (246,195,159,255), (225,154,126,255)
fist = Image.new('RGBA', (64, 64))
rows = ["OFFO", "OFFO", "OFDO", "OOOO"]
for j, row in enumerate(rows):
    for i, ch in enumerate(row):
        fist.putpixel((20+i, 43+j), {'O': O, 'F': F, 'D': D}[ch])
fist.save(out_h)
