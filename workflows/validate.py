"""Structural check of API-format workflows against a running ComfyUI's /object_info — nothing is executed.

For every node: the class exists, every input name is real (dynamic forms like `images.image_1` and `model.size`
included), required inputs are present, links point at real output slots of a compatible type, and combo values are
valid. Model filenames that aren't installed are listed as "needs file" (expected on a machine without the models)
rather than errors. Safe for the API (paid) bonus workflows: it never queues a prompt.

Run: python workflows/validate.py [server_url] [workflow.json ...]   (default: every workflows/api/**/*.json)
"""
import glob
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_INPUTS = ("ckpt_name", "lora_name", "unet_name", "vae_name", "clip_name", "clip_name1", "clip_name2",
                "text_encoder", "model_name", "audio")


def _spec_type(spec):
    """(type, options or None) of an input spec."""
    t = spec[0]
    opts = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
    if isinstance(t, list):
        return "COMBO", t
    if t == "COMBO":
        return "COMBO", opts.get("options")
    return t, None


def _inputs(info):
    out = {}
    for group in ("required", "optional"):
        for name, spec in (info["input"].get(group) or {}).items():
            out[name] = (group, spec)
    return out


def _dynamic(name, inputs):
    """Resolve 'images.image_1' / 'model.size' against autogrow / dynamic-combo specs. Returns (type, options)."""
    base, _, sub = name.partition(".")
    if base not in inputs:
        return None
    t, opts = _spec_type(inputs[base][1])
    meta = inputs[base][1][1] if len(inputs[base][1]) > 1 else {}
    if t == "COMFY_AUTOGROW_V3":
        tmpl = meta.get("template", {}).get("input", {})
        for group in ("required", "optional"):
            for _, spec in (tmpl.get(group) or {}).items():
                return _spec_type(spec)
    if t == "COMFY_DYNAMICCOMBO_V3":
        for o in meta.get("options", []):
            for group in ("required", "optional"):
                spec = (o.get("inputs", {}).get(group) or {}).get(sub)
                if spec:
                    return _spec_type(spec)
        return "ANY", None
    return None


def _compatible(out_t, in_t):
    if "*" in (out_t, in_t) or in_t in ("ANY", "COMBO"):
        return True
    return bool(set(str(out_t).split(",")) & set(str(in_t).split(",")))


def validate(prompt: dict, info: dict) -> tuple[list[str], set[str]]:
    errors, needs = [], set()
    for nid, n in prompt.items():
        cls = n.get("class_type")
        if cls not in info:
            errors.append(f"{nid}: unknown node type {cls}")
            continue
        spec = _inputs(info[cls])
        given = n.get("inputs", {})
        for name, (group, s) in spec.items():
            t, _ = _spec_type(s)
            if group == "required" and name not in given and t not in ("COMFY_AUTOGROW_V3",):
                if not any(k.startswith(name + ".") for k in given):
                    errors.append(f"{nid} {cls}: missing required input '{name}'")
        for name, val in given.items():
            if name in spec:
                t, opts = _spec_type(spec[name][1])
            else:
                dyn = _dynamic(name, spec)
                if dyn is None:
                    errors.append(f"{nid} {cls}: unknown input '{name}'")
                    continue
                t, opts = dyn
            if isinstance(val, list) and len(val) == 2 and isinstance(val[0], str):
                src = prompt.get(val[0])
                if src is None:
                    errors.append(f"{nid} {cls}.{name}: link to missing node {val[0]}")
                    continue
                outs = info.get(src["class_type"], {}).get("output", [])
                if val[1] >= len(outs):
                    errors.append(f"{nid} {cls}.{name}: {src['class_type']} has no output slot {val[1]}")
                elif not _compatible(outs[val[1]], t):
                    errors.append(f"{nid} {cls}.{name}: expects {t}, linked to {outs[val[1]]} ({src['class_type']})")
            elif t == "COMBO" and opts is not None and val not in opts:
                if name.split(".")[0] in MODEL_INPUTS:
                    needs.add(str(val))
                else:
                    errors.append(f"{nid} {cls}.{name}: {val!r} not in {opts[:8]}")
    if not any(info.get(n["class_type"], {}).get("output_node") for n in prompt.values()):
        errors.append("no output node (nothing would be saved)")
    return errors, needs


def main():
    args = sys.argv[1:]
    url = args.pop(0) if args and args[0].startswith("http") else "http://127.0.0.1:8188"
    files = args or sorted(glob.glob(os.path.join(HERE, "api", "**", "*.json"), recursive=True))
    info = json.load(urllib.request.urlopen(f"{url}/object_info"))
    bad = 0
    for f in files:
        prompt = json.load(open(f))
        errors, needs = validate(prompt, info)
        rel = os.path.relpath(f, HERE)
        status = "OK" if not errors else f"{len(errors)} ERROR(S)"
        print(f"{rel}: {status} · {len(prompt)} nodes" + (f" · needs files: {', '.join(sorted(needs))}" if needs else ""))
        for e in errors:
            print("   ", e)
        bad += bool(errors)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
