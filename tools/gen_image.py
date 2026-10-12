"""One PixelLab pixflux generation (1 credit). usage: gen_image.py out.png W H direction seed "description" """
import sys, json, base64, io, urllib.request
from PIL import Image
out, W, H, direction, seed, desc = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], int(sys.argv[5]), sys.argv[6]
body = {"description": desc, "image_size": {"width": W, "height": H}, "outline": "single color outline",
        "shading": "basic shading", "detail": "medium detail", "view": "side", "direction": direction,
        "no_background": True, "text_guidance_scale": 8, "seed": seed}
req = urllib.request.Request("https://api.pixellab.ai/v2/create-image-pixflux", data=json.dumps(body).encode(),
                             headers={"Content-Type": "application/json"}, method="POST")
try:
    r = json.load(urllib.request.urlopen(req, timeout=300))
except urllib.error.HTTPError as e:
    print('HTTP', e.code, e.read()[:300]); sys.exit(1)
print(out, r.get('usage'))
Image.open(io.BytesIO(base64.b64decode(r['image']['base64'].split(',')[-1]))).convert('RGBA').save(out)
