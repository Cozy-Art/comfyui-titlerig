"""Queue an API-format workflow on a running ComfyUI, wait for it and list the files it wrote.

Run: python workflows/run_headless.py workflows/api/titlerig_rig_only.json [server_url]
(For the audio workflow, copy examples/assets/titlerig_beat.wav into ComfyUI/input first.)"""
import json
import sys
import time
import urllib.request
import uuid

path = sys.argv[1]
URL = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8188"
prompt = json.load(open(path))
for n in prompt.values():
    n.pop("_meta", None)

req = urllib.request.Request(f"{URL}/prompt", data=json.dumps({"prompt": prompt, "client_id": str(uuid.uuid4())}).encode(),
                             headers={"Content-Type": "application/json"})
try:
    pid = json.load(urllib.request.urlopen(req))["prompt_id"]
except urllib.error.HTTPError as e:
    sys.exit(f"rejected: {e.read().decode()}")
t0 = time.time()
while True:
    h = json.load(urllib.request.urlopen(f"{URL}/history/{pid}"))
    if pid in h:
        break
    if time.time() - t0 > 1800:
        sys.exit("timed out")
    time.sleep(1)
st = h[pid]["status"]
print(f"{path}: {st['status_str']} in {time.time() - t0:.1f}s")
for m in st.get("messages", []):
    if m[0] == "execution_error":
        print(json.dumps(m[1], indent=2)[:3000])
for nid, out in h[pid]["outputs"].items():
    for kind, items in out.items():
        if isinstance(items, list):
            for it in items:
                if isinstance(it, dict) and "filename" in it:
                    print(f"  node {nid} {kind}: {it.get('subfolder', '')}/{it['filename']} ({it.get('type')})")
sys.exit(0 if st["status_str"] == "success" else 1)
