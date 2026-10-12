import sys
from PIL import Image
# outline.py in.png out.png : recolor outer contour pixels to dark navy-brown, darken dark interior lines
im = Image.open(sys.argv[1]).convert('RGBA'); W, H = im.size
src = im.copy(); OUT = (38, 30, 48, 255)
def a(x, y): return 0 <= x < W and 0 <= y < H and src.getpixel((x, y))[3] > 128
for y in range(H):
    for x in range(W):
        r, g, b, al = src.getpixel((x, y))
        if al <= 128: continue
        edge = any(not a(x+dx, y+dy) for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)))
        lum = 0.3*r + 0.59*g + 0.11*b
        if edge or lum < 40:
            im.putpixel((x, y), OUT)
im.save(sys.argv[2])
