"""Magnet: a moving point (optionally a second word) that attracts or repels the title's letters.

Each letter rides a damped spring toward the displacement the magnet's field asks for, so letters lag, overshoot and
settle; squash & stretch follows each letter's velocity. Pure numpy; simulated once per clip, then read per frame.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

POLARITIES = ("repel", "attract")
PATHS = ("sweep", "orbit", "fixed")


@dataclass
class Magnet:
    polarity: str = "repel"
    strength: float = 90.0           # px of push at the magnet's centre
    range: float = 220.0             # px, Gaussian falloff radius
    lag: float = 0.15                # s: letters at `range` respond this much later than letters on the magnet
    spring: float = 0.5              # 0 = settles smoothly, 1 = very bouncy overshoot
    squash: float = 0.4              # 0..1 squash & stretch along each letter's velocity
    path: str = "sweep"              # sweep (x,y -> x_end,y_end) | orbit (around x,y) | fixed (x,y)
    x: float = -0.15                 # canvas 0..1 (may start off-frame)
    y: float = 0.5
    x_end: float = 1.15
    y_end: float = 0.5
    radius: float = 0.3              # orbit radius, fraction of canvas height
    duration: float = 2.5            # s for the sweep / one orbit
    start: float = 0.0               # s
    drive: np.ndarray | None = None  # per-frame 0..1 curve (e.g. Audio React) that scales strength
    text: str = ""                   # optional: render this word as the magnet
    font: str = "Anton"
    size: int = 120

    def __post_init__(self):
        if self.polarity not in POLARITIES:
            raise ValueError(f"unknown polarity: {self.polarity}; choose from {POLARITIES}")
        if self.path not in PATHS:
            raise ValueError(f"unknown path: {self.path}; choose from {PATHS}")

    def end_time(self) -> float:
        return self.start + self.duration

    def position(self, t: float, W: int, H: int) -> tuple[float, float]:
        """Magnet centre in px at time t (s). Sweeps ease in-out; orbits run at constant speed."""
        p = min(max((t - self.start) / max(self.duration, 1e-6), 0.0), 1.0)
        if self.path == "fixed":
            return self.x * W, self.y * H
        if self.path == "orbit":
            a = 2 * math.pi * p - math.pi / 2
            r = self.radius * H
            return self.x * W + r * math.cos(a) * 1.6, self.y * H + r * math.sin(a)
        e = 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2
        return (self.x + (self.x_end - self.x) * e) * W, (self.y + (self.y_end - self.y) * e) * H

    def gain(self, frame: int) -> float:
        if self.drive is None:
            return 1.0
        d = np.asarray(self.drive)
        if d.ndim == 2:
            d = d.mean(axis=0)
        return float(d[min(max(frame, 0), len(d) - 1)])


def field(mg: Magnet, letter: np.ndarray, magnet: np.ndarray, gain: float = 1.0) -> np.ndarray:
    """Displacement the magnet asks of a letter at rest position `letter`."""
    d = magnet - letter
    r = float(np.hypot(*d))
    if r < 1e-6:
        return np.zeros(2)
    f = mg.strength * gain * math.exp(-(r / max(mg.range, 1.0)) ** 2)
    u = d / r
    if mg.polarity == "attract":
        return u * min(f, 0.85 * r)  # never pulled past the magnet
    return -u * f


def simulate(mg: Magnet, anchors: dict[int, tuple[float, float]], n: int, fps: float, W: int, H: int,
             substeps: int = 4) -> dict[int, np.ndarray]:
    """Spring-follow the field for every letter. Returns {letter: (n, 4) [dx, dy, vx, vy]} in px, px/s."""
    omega = 2 * math.pi * 2.5
    zeta = 1.0 - 0.85 * float(np.clip(mg.spring, 0, 1))
    dt = 1.0 / fps / substeps
    out = {}
    for i, (ax, ay) in anchors.items():
        rest = np.array([ax, ay], np.float64)
        x, v = np.zeros(2), np.zeros(2)
        rows = np.zeros((n, 4), np.float32)
        for f in range(n):
            for s in range(substeps):
                t = (f + (s + 1) / substeps) / fps
                m_now = np.array(mg.position(t, W, H))
                dist = float(np.hypot(*(m_now - rest)))
                delay = mg.lag * min(1.0, dist / max(mg.range, 1.0))
                target = field(mg, rest, np.array(mg.position(t - delay, W, H)), mg.gain(f))
                a = omega ** 2 * (target - x) - 2 * zeta * omega * v
                v = v + a * dt
                x = x + v * dt
            rows[f] = (x[0], x[1], v[0], v[1])
        out[i] = rows
    return out


def stretch_of(mg: Magnet, vx: float, vy: float) -> tuple[float, float]:
    """(stretch factor, angle deg) for squash & stretch along the velocity."""
    speed = math.hypot(vx, vy)
    if mg.squash <= 0 or speed < 1e-3:
        return 1.0, 0.0
    ref = 6.0 * max(mg.strength, 1.0)  # px/s that counts as "fast"
    return 1.0 + 0.8 * mg.squash * min(1.0, speed / ref), math.degrees(math.atan2(vy, vx))
