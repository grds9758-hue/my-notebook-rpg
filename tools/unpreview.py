"""Turns a PixelLab workbench preview (dark bg + label strip) back into a transparent sprite.
usage: unpreview.py in.png out.png W H"""
import sys
from PIL import Image
a = Image.open(sys.argv[1]).convert('RGBA'); W, H = int(sys.argv[3]), int(sys.argv[4])
bg = a.getpixel((0, a.height - 1))
a = a.crop((0, a.height - H, W, a.height))
px = a.load()
for y in range(H):
    for x in range(W):
        if px[x, y] == bg: px[x, y] = (0, 0, 0, 0)
a.save(sys.argv[2])
