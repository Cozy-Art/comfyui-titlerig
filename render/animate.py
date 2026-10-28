"""TitleRig animation: per-letter / whole-word effects with stagger, order and easing -> list of frames.

Each Track maps a time (or an external drive curve, e.g. from audio) to an offset fraction v per letter:
v = 0 is the rest pose, v = 1 is the full effect amount. "in" eases v 1 -> 0, "out" 0 -> 1, "loop" repeats 0 -> 1.
"""
from __future__ import annotations

import copy
import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace

import numpy as np

from .core import Glyphs, Look3D, Shadow, letter_anchors, render_title
from .geometry import Layout
from .magnet import Magnet, simulate, stretch_of

LETTER_EFFECTS = ("flip_x", "spin_y", "roll_z", "pop", "drop", "slide", "squash", "shake",
                  "skew_x", "skew_y", "taper_x", "taper_y", "corner_pin")
SHADOW_EFFECTS = ("shadow_length", "shadow_angle", "shadow_opacity", "shadow_softness")
LOOK_EFFECTS = ("extrude", "light")
LAYOUT_EFFECTS = ("wave", "tilt_x", "tilt_y", "bend", "wrap_spin")
EFFECTS = LETTER_EFFECTS + LAYOUT_EFFECTS + SHADOW_EFFECTS + LOOK_EFFECTS
EASINGS = ("linear", "in", "out", "in_out", "sine", "expo", "back", "elastic", "bounce", "spring", "steps")
RESPONSES = ("follow", "trigger")
DEFAULT_CORNERS = [[-24, -18], [24, -18], [0, 0], [0, 0]]  # corner_pin without a target: the top flares out
RETRIGGERS = ("restart", "finish", "layer")
ORDERS = ("forward", "reverse", "center_out", "edges_in", "random")
DIRECTIONS = ("in", "out", "loop")
TARGETS = ("letters", "word")
# amount at v = 1: degrees for flip/spin/roll/wave/shadow_angle, % shrink for pop and % fade for
# shadow_opacity (negative grows / darkens), px for drop/slide/shadow_length/shadow_softness
DEFAULT_AMOUNT = {"flip_x": 90.0, "spin_y": 360.0, "roll_z": 180.0, "pop": 100.0, "drop": 420.0, "slide": 700.0,
                  "wave": 360.0, "shadow_length": 60.0, "shadow_angle": 45.0, "shadow_opacity": 100.0,
                  "shadow_softness": 12.0, "squash": 35.0, "shake": 12.0, "extrude": 30.0, "light": 90.0,
                  "tilt_x": 30.0, "tilt_y": 30.0, "bend": 50.0, "skew_x": 20.0, "skew_y": 12.0,
                  "taper_x": 50.0, "taper_y": 40.0, "corner_pin": 100.0, "wrap_spin": 360.0}
# squash: % squash (negative = stretch tall), shake: px jitter, extrude: px depth, light: deg of key-light sweep,
# tilt_x/tilt_y: deg, bend: % of full arc bend, skew_x/skew_y: deg, taper_x/taper_y: % (negative flares),
# corner_pin: % of the track's `corners` offsets ([[dx,dy] x4], TL TR BR BL, px)


# ------------------------------------------------------------------------------------------------ easing
def _bounce(p):
    n, d = 7.5625, 2.75
    if p < 1 / d:
        return n * p * p
    if p < 2 / d:
        p -= 1.5 / d
        return n * p * p + 0.75
    if p < 2.5 / d:
        p -= 2.25 / d
        return n * p * p + 0.9375
    p -= 2.625 / d
    return n * p * p + 0.984375


def ease(name: str, p: float) -> float:
    """Easing for p in [0,1] -> progress (back / elastic overshoot past 1 on purpose)."""
    if p <= 0.0 or p >= 1.0:
        if name not in EASINGS:
            raise ValueError(f"unknown easing: {name}")
        return 0.0 if p <= 0.0 else 1.0
    if name == "linear":
        return p
    if name == "in":
        return p ** 3
    if name == "sine":
        return -(math.cos(math.pi * p) - 1) / 2
    if name == "expo":
        return 1 - 2 ** (-10 * p)
    if name == "spring":  # damped spring: overshoots, rings twice, settles exactly at 1
        return 1 - math.exp(-6 * p) * math.cos(4.5 * math.pi * p) * (1 - p)
    if name == "steps":  # stop-motion: 4 held poses
        return math.floor(p * 4) / 4
    if name == "in_out":
        return 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2
    if name == "out":
        return 1 - (1 - p) ** 3
    if name == "back":
        c1 = 1.70158
        return 1 + (c1 + 1) * (p - 1) ** 3 + c1 * (p - 1) ** 2
    if name == "elastic":
        if p in (0.0, 1.0):
            return p
        return 2 ** (-10 * p) * math.sin((p * 10 - 0.75) * (2 * math.pi / 3)) + 1
    if name == "bounce":
        return _bounce(p)
    raise ValueError(f"unknown easing: {name}")


# ------------------------------------------------------------------------------------------------ tracks
@dataclass
class Track:
    effect: str = "pop"
    target: str = "letters"            # letters | word
    direction: str = "in"              # in | out | loop
    easing: str = "back"
    duration: float = 0.6              # s per letter (per cycle for loop)
    stagger: float = 0.06              # s between letters (also the per-letter lag of a drive curve)
    order: str = "forward"
    amount: float | None = None        # None = DEFAULT_AMOUNT[effect]
    start: float = 0.0                 # s
    seed: int = 0
    drive: np.ndarray | None = None    # per-frame curve (n,) or spectrum (bands, n), 0..1; replaces time + easing
    letters: str = "all"               # which letters: "all", "0,2,5-7" (char indices), "word:2" (1-based words)
    influence: float = 1.0             # dial: scales how far the track pushes (0 = off, 2 = double)
    corners: list | None = None        # corner_pin target: [[dx, dy] x4] px, TL TR BR BL
    response: str = "follow"           # drive only: follow the curve, or "trigger": every hit replays the easing
    retrigger: str = "restart"         # trigger: restart on every hit | finish the current one first | layer (max)

    def amt(self) -> float:
        return DEFAULT_AMOUNT[self.effect] if self.amount is None else self.amount


@dataclass
class Anim:
    tracks: list[Track] = field(default_factory=list)
    fps: float = 24.0
    hold: float = 0.6                  # s of rest after the last track settles
    magnets: list[Magnet] = field(default_factory=list)

    def n_frames(self, n_letters: int = 1) -> int:
        ends = [0.0]
        for mg in self.magnets:
            ends.append(len(mg.drive) / self.fps if mg.drive is not None else mg.end_time() + self.hold)
        for t in self.tracks:
            if t.drive is not None:
                ends.append(np.shape(t.drive)[-1] / self.fps)
            elif t.direction == "loop":
                ends.append(t.start + t.duration + t.stagger * max(n_letters - 1, 0))
            else:
                ends.append(t.start + t.duration + t.stagger * max(n_letters - 1, 0) + self.hold)
        return max(1, int(round(max(ends) * self.fps)))


def select_letters(text: str, spec: str = "all") -> list[int]:
    """Visible letter indices picked by spec: "all", "0,2,5-7" (character indices), "word:2" or "word:1,3"."""
    vis = [i for i, c in enumerate(text) if c.strip()]
    spec = (spec or "all").strip().lower()
    if spec in ("all", "*"):
        return vis
    if spec.startswith("word:"):
        words, cur, k = {}, [], 1
        for i, c in enumerate(text + " "):
            if c.strip():
                cur.append(i)
            elif cur:
                words[k], cur, k = cur, [], k + 1
        want = {int(w) for w in spec[5:].split(",") if w.strip()}
        return [i for w in sorted(want) for i in words.get(w, [])]
    picked = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = (int(x) for x in part.split("-", 1))
            picked.update(range(min(a, b), max(a, b) + 1))
        else:
            picked.add(int(part))
    return [i for i in vis if i in picked]


def letter_ranks(text: str, order: str, seed: int = 0, select: str = "all") -> dict[int, int]:
    """Stagger rank per selected visible letter index (spaces are skipped)."""
    idx = select_letters(text, select)
    n = len(idx)
    if order == "forward":
        keys = list(range(n))
    elif order == "reverse":
        keys = list(range(n - 1, -1, -1))
    elif order in ("center_out", "edges_in"):
        c = (n - 1) / 2
        d = [abs(k - c) for k in range(n)]
        if order == "edges_in":
            d = [max(d) - x for x in d]
        keys = [int(math.floor(x + 1e-6)) for x in d]  # mirrored pairs move together
    elif order == "random":
        keys = list(np.random.default_rng(seed).permutation(n))
    else:
        raise ValueError(f"unknown order: {order}")
    return {i: int(k) for i, k in zip(idx, keys)}


def track_value(tr: Track, rank: int, frame: int, fps: float, pos: float | None = None) -> float:
    """Offset fraction v (times the influence dial) for one letter at one frame.

    pos (0..1, left to right) picks a row of a spectrum drive; None averages the rows (word / shadow targets)."""
    return tr.influence * _raw_value(tr, rank, frame, fps, pos)


def hits(curve: np.ndarray, threshold: float = 0.5) -> list[tuple[int, float]]:
    """(frame, strength) wherever the curve rises through `threshold` (its peak value within the rise)."""
    out, f, n = [], 1, len(curve)
    if n and curve[0] >= threshold:
        out.append((0, float(curve[0])))
    while f < n:
        if curve[f] >= threshold > curve[f - 1]:
            g = f
            while g + 1 < n and curve[g + 1] >= curve[g]:
                g += 1
            out.append((f, float(curve[g])))
        f += 1
    return out


def _triggered(tr: Track, d: np.ndarray, f: int, fps: float, row: int) -> float:
    """Each hit replays the track's easing over `duration`, scaled by the hit's strength.

    in: jump on the hit, ease back to rest (bounce / elastic / back / spring settle with character)
    out: ease up to the hit's strength and hold until the next hit. loop: one full 0 -> 1 cycle per hit."""
    key = row  # the drive never changes for a track, so its hit list is cached per spectrum row (-1 = mean)
    cache = tr.__dict__.setdefault("_hits", {})
    if key not in cache:
        hs = hits(d)
        if tr.retrigger == "finish":  # drop hits that land while the previous one is still playing
            kept, busy_until = [], -1.0
            for h in hs:
                if h[0] >= busy_until:
                    kept.append(h)
                    busy_until = h[0] + tr.duration * fps
            hs = kept
        cache[key] = hs
    live = [h for h in cache[key] if h[0] <= f]
    if not live:
        return 0.0
    if tr.retrigger != "layer":
        live = live[-1:]
    else:  # every hit still playing contributes; the strongest wins, so motion never snaps back
        live = [h for h in live if (f - h[0]) <= tr.duration * fps] or live[-1:]
    best = 0.0
    for h0, strength in live:
        e = ease(tr.easing, (f - h0) / max(tr.duration * fps, 1e-6))
        val = strength * (1.0 - e) if tr.direction == "in" else strength * e
        best = val if abs(val) > abs(best) else best
    return best


def _raw_value(tr: Track, rank: int, frame: int, fps: float, pos: float | None) -> float:
    if tr.drive is not None:
        d = np.asarray(tr.drive)
        row = -1
        if d.ndim == 2:
            if pos is None:
                d = d.mean(axis=0)
            else:
                row = int(round(min(max(pos, 0.0), 1.0) * (len(d) - 1)))
                d = d[row]
        f = frame - int(round(tr.stagger * rank * fps))
        if f < 0:
            return 0.0
        if tr.response == "trigger":
            return _triggered(tr, d, min(f, len(d) - 1), fps, row)
        return float(d[min(f, len(d) - 1)])
    t = frame / fps - tr.start - tr.stagger * rank
    if tr.direction == "loop":
        if t < 0:
            return 0.0
        return ease(tr.easing, (t / max(tr.duration, 1e-6)) % 1.0)
    e = ease(tr.easing, t / max(tr.duration, 1e-6))
    return 1.0 - e if tr.direction == "in" else e


def _apply(d: dict, effect: str, amount: float, v: float, corners=None) -> None:
    if effect in ("skew_x", "skew_y"):
        d[effect] = d.get(effect, 0.0) + amount * v
    elif effect in ("taper_x", "taper_y"):
        d[effect] = d.get(effect, 0.0) + amount / 100.0 * v
    elif effect == "corner_pin":
        c = np.asarray(corners if corners is not None else DEFAULT_CORNERS, np.float64).reshape(4, 2)
        d["corners"] = np.asarray(d.get("corners", np.zeros((4, 2))), np.float64) + c * amount / 100.0 * v
    elif effect == "flip_x":
        d["sy"] = d.get("sy", 1.0) * math.cos(math.radians(amount * v))
    elif effect == "spin_y":
        d["sx"] = d.get("sx", 1.0) * math.cos(math.radians(amount * v))
    elif effect == "roll_z":
        d["rot"] = d.get("rot", 0.0) + amount * v
    elif effect == "pop":
        d["scale"] = d.get("scale", 1.0) * max(0.0, 1.0 - amount / 100.0 * v)
    elif effect == "drop":
        d["dy"] = d.get("dy", 0.0) - amount * v
    elif effect == "slide":
        d["dx"] = d.get("dx", 0.0) - amount * v
    elif effect == "squash":  # squash & stretch, volume-preserving-ish
        k = amount / 100.0 * v
        d["sy"] = d.get("sy", 1.0) * max(0.05, 1.0 - k)
        d["sx"] = d.get("sx", 1.0) * max(0.05, 1.0 + 0.6 * k)
    elif effect == "shadow_length":
        d.length = max(0.0, d.length + amount * v)
        d.on = d.on or d.length > 0
    elif effect == "shadow_angle":
        d.angle += amount * v
    elif effect == "shadow_opacity":
        d.opacity = float(np.clip(d.opacity - amount / 100.0 * v, 0, 1))
    elif effect == "shadow_softness":
        d.softness = max(0.0, d.softness + amount * v)
    elif effect == "extrude":
        d.extrude = max(0, int(round(d.extrude + amount * v)))
    elif effect == "light":
        d.light_angle = d.light_angle + amount * v
    elif effect == "wave":
        d.flag_phase += amount * v
    elif effect == "tilt_x":
        d.tilt_x += amount * v
    elif effect == "tilt_y":
        d.tilt_y += amount * v
    elif effect == "wrap_spin":
        d.wrap_phase += amount * v
    elif effect == "bend":
        d.bend = float(np.clip(d.bend + amount / 100.0 * v, -1, 1))
    else:
        raise ValueError(f"unknown effect: {effect}")


def _shake(d: dict, amount: float, v: float, seed: int, frame: int, i: int) -> None:
    rng = np.random.default_rng((seed * 1_000_003 + frame * 7919 + i) & 0x7FFFFFFF)
    jx, jy = rng.uniform(-1, 1, 2)
    d["dx"] = d.get("dx", 0.0) + amount * v * jx
    d["dy"] = d.get("dy", 0.0) + amount * v * jy


def _magnet_motion(anim: Anim, mg: Magnet, g: Glyphs, lay: Layout, size: tuple[int, int]) -> dict:
    """Simulated per-letter motion for one magnet, cached on the magnet per canvas + text + layout."""
    W, H = size
    key = (W, H, g.text, g.font, g.size, g.tracking, lay.mode, lay.bend, lay.align, anim.fps)
    cache = mg.__dict__.setdefault("_sim", {})
    if key not in cache:
        n = anim.n_frames(sum(1 for c in g.text if c.strip()))
        cache[key] = simulate(mg, letter_anchors(g, W, H, lay), n, anim.fps, W, H)
    return cache[key]


def pose(anim: Anim, g: Glyphs, lay: Layout, frame: int, shadow: Shadow | None = None, look: Look3D | None = None,
         size: tuple[int, int] | None = None):
    """(Glyphs, Layout, Shadow, Look3D) for one frame: animated transforms on top of the user's own settings.

    target "word" moves the selected letters as one rigid group (the whole word when letters="all")."""
    base = g
    g = copy.deepcopy(g)
    lay = replace(lay)
    shadow = replace(shadow or Shadow())
    look = replace(look or Look3D())
    if anim.magnets and size is not None:  # magnets push letters first; tracks layer on top
        for mg in anim.magnets:
            motion = _magnet_motion(anim, mg, base, lay, size)
            for i, rows in motion.items():
                dx, dy, vx, vy = rows[min(frame, len(rows) - 1)]
                d = g.letters.setdefault(i, {})
                d["dx"] = d.get("dx", 0.0) + float(dx)
                d["dy"] = d.get("dy", 0.0) + float(dy)
                k, ang = stretch_of(mg, float(vx), float(vy))
                if k != 1.0:
                    d["stretch"], d["stretch_angle"] = d.get("stretch", 1.0) * k, ang
    for tr in anim.tracks:
        amount = tr.amt()
        if tr.effect in LAYOUT_EFFECTS:  # wave ripples the flag phase; tilt / bend move the whole layout
            if tr.effect == "bend" and lay.mode != "arc":
                lay.mode = "arc"
            _apply(lay, tr.effect, amount, track_value(tr, 0, frame, anim.fps))
            continue
        if tr.effect in SHADOW_EFFECTS:
            _apply(shadow, tr.effect, amount, track_value(tr, 0, frame, anim.fps))
            continue
        if tr.effect in LOOK_EFFECTS:
            _apply(look, tr.effect, amount, track_value(tr, 0, frame, anim.fps))
            continue
        if tr.target == "word":
            v = track_value(tr, 0, frame, anim.fps)
            sel = select_letters(g.text, tr.letters)
            if sel == select_letters(g.text, "all"):
                tgt = [g.word]
            else:  # rigid group: one transform about the group's centre, stored apart from per-letter ones
                gid = ",".join(map(str, sel))
                tgt = [g.letters.setdefault(i, {}).setdefault("group", {"id": gid}) for i in sel]
            if tr.effect == "shake":
                rng_v = {}
                _shake(rng_v, amount, v, tr.seed, frame, -1)
                for d in tgt:
                    d["dx"] = d.get("dx", 0.0) + rng_v["dx"]
                    d["dy"] = d.get("dy", 0.0) + rng_v["dy"]
            else:
                _apply(tgt[0], tr.effect, amount, v, tr.corners)
                for d in tgt[1:]:  # group members share the first member's group transform
                    d.update({k: val for k, val in tgt[0].items() if k != "id"})
            continue
        ranks = letter_ranks(g.text, tr.order, tr.seed, tr.letters)
        order = sorted(ranks)
        for j, i in enumerate(order):
            pos = j / max(len(order) - 1, 1)
            g.letters.setdefault(i, {})
            v = track_value(tr, ranks[i], frame, anim.fps, pos)
            if tr.effect == "shake":
                _shake(g.letters[i], amount, v, tr.seed, frame, i)
            else:
                _apply(g.letters[i], tr.effect, amount, v, tr.corners)
    return g, lay, shadow, look


ANIM_PASSES = ("beauty", "alpha", "depth", "edges")
MAGNET_LOOK = Look3D(face="#e2e8f0", face2="#94a3b8", side="#334155", extrude=12, bevel=0, bevel_profile="flat")


def composite(under: dict, over: dict) -> dict:
    """Layer one render's passes over another's: beauty alpha-over, masks / depth / edges by max."""
    out = dict(under)
    a = over["alpha"][..., None]
    ub, ob = under["beauty"], over["beauty"]
    rgb = ob[..., :3] * a + ub[..., :3] * (1 - a)
    out["beauty"] = np.dstack([rgb, np.maximum(ub[..., 3], ob[..., 3])]).astype(np.float32)
    for k in under:
        if k == "beauty":
            continue
        if k in ("letter_ids", "normals"):
            out[k] = np.where(over["alpha"][..., None] > 0, over[k], under[k]).astype(np.float32)
        else:
            out[k] = np.maximum(under[k], over[k]).astype(np.float32)
    return out


def render_frame(anim: Anim, g: Glyphs, look: Look3D | None, shadow: Shadow | None, width: int, height: int,
                 lay: Layout, f: int, passes=ANIM_PASSES) -> dict[str, np.ndarray]:
    """One animation frame: posed rig + any magnet words composited on top."""
    gf, lf, sf, kf = pose(anim, g, lay, f, shadow, look, size=(width, height))
    p = render_title(gf, kf, sf, width, height, lf, guides="all" if "guides" in passes else "none")
    for mg in anim.magnets:  # a magnet word is drawn on top, where the magnet is
        if mg.text.strip():
            mx, my = mg.position(f / anim.fps, width, height)
            mw = Glyphs(text=mg.text, font=mg.font, size=mg.size, word={"dx": mx - width / 2, "dy": my - height / 2})
            p = composite(p, render_title(mw, MAGNET_LOOK, Shadow(on=False), width, height, Layout(), guides="none"))
    return {k: p[k] for k in passes}


def render_frames(anim: Anim, g: Glyphs, look: Look3D | None = None, shadow: Shadow | None = None,
                  width: int = 1280, height: int = 720, lay: Layout | None = None,
                  passes=ANIM_PASSES, workers: int = 4) -> dict[str, np.ndarray]:
    """Render every frame; returns {pass: (N, H, W[, C]) float32}. Frames render in parallel threads."""
    lay = lay or Layout()
    n = anim.n_frames(sum(1 for c in g.text if c.strip()))
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        frames = list(ex.map(lambda f: render_frame(anim, g, look, shadow, width, height, lay, f, passes), range(n)))
    return {k: np.stack([fr[k] for fr in frames]) for k in passes}
