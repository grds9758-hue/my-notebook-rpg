import sys, json, base64, io, urllib.request
from PIL import Image, ImageDraw
# usage: gen.py base.png outdir name "x0,y0,x1,y1[;...]" "description" [seed]
base_p, outdir, name, rects, desc = sys.argv[1:6]
seed = int(sys.argv[6]) if len(sys.argv) > 6 else 1234
base = Image.open(base_p).convert('RGBA')
mask = Image.new('RGB', base.size, (0, 0, 0))
d = ImageDraw.Draw(mask)
for r in rects.split(';'):
    d.rectangle([int(v) for v in r.split(',')], fill=(255, 255, 255))
def b64(im):
    buf = io.BytesIO(); im.save(buf, 'PNG'); return base64.b64encode(buf.getvalue()).decode()
body = {"description": desc + ", cute chibi pixel art, dark brown outline",
        "image_size": {"width": 64, "height": 64},
        "inpainting_image": {"type": "base64", "base64": b64(base)},
        "mask_image": {"type": "base64", "base64": b64(mask)},
        "outline": "single color outline", "shading": "basic shading", "detail": "medium detail",
        "view": "side", "direction": "south", "no_background": True,
        "text_guidance_scale": 6, "seed": seed}
req = urllib.request.Request("https://api.pixellab.ai/v2/inpaint", data=json.dumps(body).encode(),
                             headers={"Content-Type": "application/json"}, method="POST")
r = json.load(urllib.request.urlopen(req, timeout=300))
print(name, r.get('usage'))
img = Image.open(io.BytesIO(base64.b64decode(r['image']['base64'].split(',')[-1]))).convert('RGBA')
img.save(f"{outdir}/{name}_full.png")
mask.save(f"{outdir}/{name}_mask.png")
