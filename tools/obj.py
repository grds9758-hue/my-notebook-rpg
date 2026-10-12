import sys, json, base64, io, urllib.request
from PIL import Image
# obj.py out.png W H "description" [seed]
out, W, H, desc = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
seed = int(sys.argv[5]) if len(sys.argv) > 5 else 1234
body = {"description": desc, "image_size": {"width": W, "height": H},
        "outline": "single color outline", "shading": "basic shading", "detail": "medium detail",
        "view": "side", "no_background": True, "text_guidance_scale": 8, "seed": seed}
req = urllib.request.Request("https://api.pixellab.ai/v2/create-image-pixflux", data=json.dumps(body).encode(),
                             headers={"Content-Type": "application/json"}, method="POST")
r = json.load(urllib.request.urlopen(req, timeout=300))
print(out, r.get('usage'))
Image.open(io.BytesIO(base64.b64decode(r['image']['base64'].split(',')[-1]))).convert('RGBA').save(out)
