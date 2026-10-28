"""Live preview for the ComfyUI canvas: POST /titlerig/preview renders a Render / Render Animation node's upstream
TitleRig graph with the real renderer and returns a PNG.

The web widget (web/titlerig_preview.js) sends the node's upstream tree:
  {"node": {"type": "TitleRigRender", "widgets": {...}, "inputs": {"glyphs": {"node": {...}, "slot": 0}, ...}},
   "pass": "beauty" | "depth" | "edges" | "alpha" | "letter_ids", "guides": bool, "frame": int, "max_width": int}
Every TitleRig builder node is rebuilt from its own class, so new nodes preview without changes here. Inputs that
only exist at run time (e.g. AUDIO) can't be previewed: a track driven by them is left out (rest pose).
"""
from __future__ import annotations

import io
import json

import numpy as np
from PIL import Image

from ..render import Layout, render_title
from ..render.animate import Anim, render_frame

PASSES = ("beauty", "depth", "edges", "alpha", "letter_ids")
RENDER_NODES = ("TitleRigRender", "TitleRigRenderAnimation")
UNRESOLVED = object()


def _evaluate(tree, mappings: dict, cache: dict):
    """Rebuild one upstream node from its widgets and inputs. Returns its output tuple, or UNRESOLVED."""
    if not tree:
        return UNRESOLVED
    key = json.dumps(tree, sort_keys=True, default=str)
    if key in cache:
        return cache[key]
    cls = mappings.get(tree.get("type"))
    if cls is None or tree.get("type") in RENDER_NODES:
        cache[key] = UNRESOLVED
        return UNRESOLVED
    spec = cls.INPUT_TYPES()
    names = set(spec.get("required", {})) | set(spec.get("optional", {}))
    kwargs = {k: v for k, v in (tree.get("widgets") or {}).items() if k in names}
    linked_unresolved = []
    for name, link in (tree.get("inputs") or {}).items():
        if name not in names or not link:
            continue
        out = _evaluate(link.get("node"), mappings, cache)
        if out is UNRESOLVED:
            linked_unresolved.append(name)
            kwargs.pop(name, None)
            continue
        kwargs[name] = out[int(link.get("slot", 0))]
    if linked_unresolved and tree["type"] in ("TitleRigAnimate", "TitleRigMagnet") and "drive" in linked_unresolved:
        # driven by run-time data (audio): preview without this track, keep the rest of the chain
        res = (kwargs["anim"],) if "anim" in kwargs else (Anim([], fps=float(kwargs.get("fps", 24.0))),)
        cache[key] = res
        return res
    missing = [n for n in spec.get("required", {}) if n not in kwargs]
    if missing:
        cache[key] = UNRESOLVED
        return UNRESOLVED
    try:
        res = getattr(cls(), cls.FUNCTION)(**kwargs)
    except Exception:  # a half-typed widget value (e.g. bad JSON) must not break the canvas
        res = UNRESOLVED
    cache[key] = res
    return res


def _to_rgb(p: dict, which: str, guides: bool) -> np.ndarray:
    if which == "beauty":
        b = p["beauty"]
        H, W = b.shape[:2]
        yy, xx = np.mgrid[0:H, 0:W]
        checker = np.where(((yy // 16) + (xx // 16)) % 2 == 0, 0.16, 0.20).astype(np.float32)[..., None]
        rgb = b[..., :3] * b[..., 3:] + checker * (1 - b[..., 3:])
    elif which in ("alpha",):
        rgb = np.repeat(p[which][..., None], 3, 2)
    else:
        rgb = p[which]
    if guides and "guides" in p:
        gd = p["guides"]
        rgb = rgb * (1 - gd[..., 3:] * 0.8) + gd[..., :3] * gd[..., 3:] * 0.8
    return np.clip(rgb, 0, 1)


def preview(payload: dict, mappings: dict) -> tuple[bytes, dict]:
    """Render the preview PNG for a payload. Returns (png bytes, info) — info has frame_count / fps / error."""
    node = payload.get("node") or {}
    which = payload.get("pass", "beauty")
    which = which if which in PASSES else "beauty"
    guides = bool(payload.get("guides", False))
    max_w = int(payload.get("max_width", 512))
    w = node.get("widgets") or {}
    width, height = int(w.get("width", 1280)), int(w.get("height", 720))
    cache: dict = {}

    def inp(name):
        link = (node.get("inputs") or {}).get(name)
        if not link:
            return None
        out = _evaluate(link.get("node"), mappings, cache)
        return None if out is UNRESOLVED else out[int(link.get("slot", 0))]

    glyphs, look, shadow, lay = inp("glyphs"), inp("look"), inp("shadow"), inp("layout")
    info = {"frame_count": 1, "fps": 24.0, "error": ""}
    if glyphs is None:
        info["error"] = "connect a TitleRig Text node to glyphs"
        img = np.full((max(1, round(max_w * height / width)), max_w, 3), 0.18, np.float32)
    else:
        want = ("beauty", which, "guides") if guides else ("beauty", which)
        if node.get("type") == "TitleRigRenderAnimation":
            anim = inp("anim") or Anim([])
            n = anim.n_frames(sum(1 for c in glyphs.text if c.strip()))
            f = min(max(int(payload.get("frame", 0)), 0), n - 1)
            p = render_frame(anim, glyphs, look, shadow, width, height, lay or Layout(), f,
                             passes=tuple(dict.fromkeys(want)))
            info.update(frame_count=n, fps=float(anim.fps))
        else:
            p = render_title(glyphs, look, shadow, width, height, lay, guides=w.get("guide_lines", "all") if guides else "none")
        img = _to_rgb(p, which, guides)
    im = Image.fromarray((img * 255).astype(np.uint8))
    if im.width > max_w:
        im = im.resize((max_w, max(1, round(im.height * max_w / im.width))), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue(), info


def register(mappings: dict) -> bool:
    """Add the /titlerig/preview route to ComfyUI's server (no-op outside ComfyUI)."""
    try:
        import asyncio

        from aiohttp import web
        from server import PromptServer
    except Exception:
        return False
    if getattr(PromptServer, "instance", None) is None:
        return False

    @PromptServer.instance.routes.post("/titlerig/preview")
    async def _preview(request):
        payload = await request.json()
        try:
            png, info = await asyncio.to_thread(preview, payload, mappings)
        except Exception as e:  # report instead of a 500 so the widget can show it
            return web.json_response({"error": str(e)}, status=400)
        return web.Response(body=png, content_type="image/png",
                            headers={"X-TitleRig-Frames": str(info["frame_count"]), "X-TitleRig-Fps": str(info["fps"]),
                                     "X-TitleRig-Error": info["error"], "Cache-Control": "no-store"})

    return True
