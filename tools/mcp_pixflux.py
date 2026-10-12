"""PixelLab pixflux via the async MCP endpoint (1 credit). Avoids the REST 502 timeout on big canvases.
usage: mcp_pixflux.py out.png W H direction "description" [seed]"""
import sys, json, re, time, base64, urllib.request
URL = 'https://api.pixellab.ai/mcp'
def call(name, args):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}}).encode()
    req = urllib.request.Request(URL, data=body, method='POST', headers={'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream'})
    raw = urllib.request.urlopen(req, timeout=180).read().decode()
    data = [l[6:] for l in raw.splitlines() if l.startswith('data: ')]
    return json.loads(data[-1] if data else raw)['result']['content']
out, W, H, direction, desc = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], sys.argv[5]
args = {"description": desc, "width": W, "height": H, "no_background": True, "view": "side", "direction": direction,
        "outline": "single color outline", "shading": "basic shading", "detail": "medium detail"}
if len(sys.argv) > 6: args["seed"] = int(sys.argv[6])
txt = ' '.join(c.get('text', '') for c in call('create_image_pixflux', args))
m = re.search(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', txt)
if not m: print('no job id:', txt[:500]); sys.exit(1)
job = m.group(0); print('job', job)
for _ in range(60):
    res = call('get_image', {"job_id": job})
    imgs = [c for c in res if c['type'] == 'image']
    text = ' '.join(c.get('text', '') for c in res)
    if imgs:
        open(out, 'wb').write(base64.b64decode(imgs[0]['data'])); print('saved', out); break
    if 'fail' in text.lower() or 'error' in text.lower(): print(text[:500]); sys.exit(1)
    time.sleep(8)
