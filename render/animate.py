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

from .core import Glyphs, Look3D, Shadow, render_title
from .geometry import Layout

EFFECTS = ("flip_x", "spin_y", "roll_z", "pop", "drop", "slide", "wave")
EASINGS = ("linear", "in_out", "out", "back", "elastic", "bounce")
ORDERS = ("forward", "reverse", "center_out", "edges_in", "random")
DIRECTIONS = ("in", "out", "loop")
TARGETS = ("letters", "word")
# amount at v = 1: degrees for flip/spin/roll/wave, % shrink for pop (negative grows), px for drop/slide
DEFAULT_AMOUNT = {"flip_x": 90.0, "spin_y": 360.0, "roll_z": 180.0, "pop": 100.0, "drop": 420.0, "slide": 700.0,
                  "wave": 360.0}


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
    drive: np.ndarray | None = None    # optional per-frame curve (0..1); replaces time + easing when set

    def amt(self) -> float:
        return DEFAULT_AMOUNT[self.effect] if self.amount is None else self.amount


@dataclass
class Anim:
    tracks: list[Track] = field(default_factory=list)
    fps: float = 24.0
    hold: float = 0.6                  # s of rest after the last track settles

    def n_frames(self, n_letters: int = 1) -> int:
        ends = [0.0]
        for t in self.tracks:
            if t.drive is not None:
                ends.append(len(t.drive) / self.fps)
            elif t.direction == "loop":
                ends.append(t.start + t.duration + t.stagger * max(n_letters - 1, 0))
            else:
                ends.append(t.start + t.duration + t.stagger * max(n_letters - 1, 0) + self.hold)
        return max(1, int(round(max(ends) * self.fps)))


def letter_ranks(text: str, order: str, seed: int = 0) -> dict[int, int]:
    """Stagger rank per visible letter index (spaces are skipped)."""
    idx = [i for i, c in enumerate(text) if c.strip()]
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


def track_value(tr: Track, rank: int, frame: int, fps: float) -> float:
    """Offset fraction v for one letter (rank) at one frame."""
    if tr.drive is not None:
        f = frame - int(round(tr.stagger * rank * fps))
        return float(tr.drive[min(max(f, 0), len(tr.drive) - 1)]) if f >= 0 else 0.0
    t = frame / fps - tr.start - tr.stagger * rank
    if tr.direction == "loop":
        if t < 0:
            return 0.0
        return ease(tr.easing, (t / max(tr.duration, 1e-6)) % 1.0)
    e = ease(tr.easing, t / max(tr.duration, 1e-6))
    return 1.0 - e if tr.direction == "in" else e


def _apply(d: dict, effect: str, amount: float, v: float) -> None:
    if effect == "flip_x":
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
    else:
        raise ValueError(f"unknown effect: {effect}")


def pose(anim: Anim, g: Glyphs, lay: Layout, frame: int) -> tuple[Glyphs, Layout]:
    """Glyphs + Layout for one frame: per-letter / word transforms layered on top of the user's own."""
    g = copy.deepcopy(g)
    lay = replace(lay)
    for tr in anim.tracks:
        amount = tr.amt()
        if tr.effect == "wave":  # ripples the flag: animates the layout's flag phase
            lay.flag_phase += amount * track_value(tr, 0, frame, anim.fps)
            continue
        if tr.target == "word":
            _apply(g.word, tr.effect, amount, track_value(tr, 0, frame, anim.fps))
            continue
        for i, r in letter_ranks(g.text, tr.order, tr.seed).items():
            g.letters.setdefault(i, {})
            _apply(g.letters[i], tr.effect, amount, track_value(tr, r, frame, anim.fps))
    return g, lay


ANIM_PASSES = ("beauty", "alpha", "depth", "edges")


def render_frames(anim: Anim, g: Glyphs, look: Look3D | None = None, shadow: Shadow | None = None,
                  width: int = 1280, height: int = 720, lay: Layout | None = None,
                  passes=ANIM_PASSES, workers: int = 4) -> dict[str, np.ndarray]:
    """Render every frame; returns {pass: (N, H, W[, C]) float32}. Frames render in parallel threads."""
    lay = lay or Layout()
    n = anim.n_frames(sum(1 for c in g.text if c.strip()))

    def one(f):
        gf, lf = pose(anim, g, lay, f)
        p = render_title(gf, look, shadow, width, height, lf, guides="all" if "guides" in passes else "none")
        return {k: p[k] for k in passes}

    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        frames = list(ex.map(one, range(n)))
    return {k: np.stack([fr[k] for fr in frames]) for k in passes}
