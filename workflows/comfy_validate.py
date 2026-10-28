"""Ask a running ComfyUI to validate the AI workflows exactly as it would before a real run, on a machine without
the models: empty placeholder files with the exact model names are created in the right models/ folders, each
workflow is submitted, and the run is cancelled straight after ComfyUI accepts it. Placeholders are removed after.

Never used for workflows/api/bonus (API, paid). Run: python workflows/comfy_validate.py <ComfyUI dir> [server_url]
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_workflows import MODELS, WORKFLOWS, RUNNABLE_ON_CPU  # noqa: E402

comfy = sys.argv[1]
url = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8188"
made = []
for name, folder, _, _ in MODELS.values():
    path = os.path.join(comfy, "models", folder, name)
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "wb").close()
        made.append(path)


def post(path, body=None):
    req = urllib.request.Request(url + path, data=json.dumps(body or {}).encode(),
                                 headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(req)


bad = 0
try:
    for name, fn in WORKFLOWS.items():
        if name in RUNNABLE_ON_CPU:
            continue
        prompt = fn()
        for n in prompt.values():
            n.pop("_meta", None)
            # keep the accepted run cheap until it's cancelled: values only, the structure is unchanged
            if n["class_type"] in ("TitleRigRenderAnimation", "TitleRigRender"):
                n["inputs"]["width"], n["inputs"]["height"] = 64, 64
            if n["class_type"] == "TitleRigAudioReact":
                n["inputs"]["max_seconds"] = 0.5
        try:
            pid = json.load(post("/prompt", {"prompt": prompt}))["prompt_id"]
            print(f"{name}: ACCEPTED by ComfyUI's validator ({len(prompt)} nodes)")
            time.sleep(0.5)
            post("/interrupt")
            post("/queue", {"delete": [pid]})
        except urllib.error.HTTPError as e:
            bad += 1
            err = json.loads(e.read().decode())
            print(f"{name}: REJECTED {err.get('error', {}).get('message')}")
            for nid, ne in (err.get("node_errors") or {}).items():
                for x in ne.get("errors", []):
                    print(f"   node {nid} {ne.get('class_type')}: {x.get('message')} {x.get('details')}")
finally:
    time.sleep(2)
    post("/interrupt")
    for p in made:
        os.remove(p)
    print(f"removed {len(made)} placeholder files")
sys.exit(1 if bad else 0)
