"""Layout geometry for TitleRig: bezier arcs, bulge envelope, perspective homography, flag warp. Pure numpy/OpenCV."""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

LAYOUT_MODES = ("flat", "arc", "ticker", "sphere", "cube")
WRAP_MODES = ("ticker", "sphere", "cube")


@dataclass
class Layout:
    mode: str = "flat"                 # flat | arc
    bend: float = 0.0                  # arc: -1..1, + arches up (rainbow), - sags (smile)
    curve: tuple | None = None         # arc: custom cubic bezier ((x0,y0),(x1,y1),(x2,y2),(x3,y3)), canvas 0..1 coords
    align: float = 0.5                 # arc: where the text centre sits along the curve (0..1)
    bulge: float = 0.0                 # -1..1, + letters swell toward the middle, - pinch
    tilt_x: float = 0.0                # degrees, + leans the top away (crawl)
    tilt_y: float = 0.0                # degrees, + swings the right side away
    fov: float = 50.0                  # degrees, perspective strength for tilt
    vanish: bool = False               # extrusion converges on a vanishing point instead of a parallel offset
    vp_x: float = 0.5                  # vanishing point, canvas 0..1 (may sit outside the frame)
    vp_y: float = 1.4
    flag_amp: float = 0.0              # px, wave height (0 = off)
    flag_wavelength: float = 420.0     # px
    flag_phase: float = 0.0            # degrees, animate this to make the flag ripple
    flag_shade: float = 0.5            # 0..1, fabric light/dark along the wave
    wrap_radius: float = 0.32          # ticker / cube: fraction of canvas width; sphere: fraction of canvas height
    wrap_phase: float = 0.0            # degrees the wrap is turned (animate with the wrap_spin effect)
    wrap_tilt: float = 15.0            # sphere: degrees the globe leans toward the viewer
    wrap_repeat: bool = True           # ticker / cube: repeat the text around the band
    wrap_shade: float = 0.6            # 0..1, darken toward the silhouette so the form reads


# ---------------------------------------------------------------------------------------------- bezier
def bezier(p: np.ndarray, t: np.ndarray) -> np.ndarray:
    """Cubic bezier points for control points p (4,2) at parameters t (N,) -> (N,2)."""
    t = np.asarray(t, np.float64)[:, None]
    u = 1 - t
    return u ** 3 * p[0] + 3 * u ** 2 * t * p[1] + 3 * u * t ** 2 * p[2] + t ** 3 * p[3]


def bezier_tangent(p: np.ndarray, t: np.ndarray) -> np.ndarray:
    t = np.asarray(t, np.float64)[:, None]
    u = 1 - t
    return 3 * u ** 2 * (p[1] - p[0]) + 6 * u * t * (p[2] - p[1]) + 3 * t ** 2 * (p[3] - p[2])


class ArcPath:
    """Arc-length parameterised cubic bezier, extended along its end tangents so long text never runs off."""

    def __init__(self, p: np.ndarray, samples: int = 1024):
        self.p = np.asarray(p, np.float64)
        self.t = np.linspace(0, 1, samples)
        pts = bezier(self.p, self.t)
        seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        self.s = np.concatenate([[0], np.cumsum(seg)])
        self.length = float(self.s[-1])

    def at(self, s: float):
        """Point and tangent angle (radians, image coords) at arc length s."""
        if s < 0 or s > self.length:
            end = 0.0 if s < 0 else 1.0
            pt = bezier(self.p, [end])[0]
            tg = bezier_tangent(self.p, [end])[0]
            tg = tg / (np.linalg.norm(tg) + 1e-9)
            over = s if s < 0 else s - self.length
            return pt + tg * over, math.atan2(tg[1], tg[0])
        t = float(np.interp(s, self.s, self.t))
        pt = bezier(self.p, [t])[0]
        tg = bezier_tangent(self.p, [t])[0]
        return pt, math.atan2(tg[1], tg[0])

    def polyline(self, offset: float = 0.0, s0: float = 0.0, s1: float | None = None, n: int = 200) -> np.ndarray:
        """Points along the path between arc lengths s0..s1, pushed `offset` px along the (upward) normal."""
        s1 = self.length if s1 is None else s1
        out = []
        for s in np.linspace(s0, s1, n):
            pt, a = self.at(s)
            nrm = np.array([math.sin(a), -math.cos(a)])  # left of travel = up for left-to-right text
            out.append(pt + nrm * offset)
        return np.array(out)


def bend_curve(bend: float, text_width: float, cx: float, cy: float) -> np.ndarray:
    """Symmetric cubic bezier whose arc length equals text_width, centred on (cx, cy) with sag split evenly."""
    bend = float(np.clip(bend, -1, 1))

    def ctrl(chord):
        h = -bend * chord * 0.75  # control point lift (negative = up in image coords)
        return np.array([[-chord / 2, 0], [-chord / 6, h], [chord / 6, h], [chord / 2, 0]], np.float64)

    chord = text_width
    for _ in range(30):  # shrink the chord until the arc is exactly as long as the text
        L = ArcPath(ctrl(chord), 256).length
        if abs(L - text_width) < 0.25:
            break
        chord *= text_width / max(L, 1e-6)
    p = ctrl(chord)
    mid_y = bezier(p, [0.5])[0, 1]
    p[:, 1] -= mid_y / 2  # centre the sag on cy
    p += np.array([cx, cy])
    return p


def bulge_scale(u: float, bulge: float) -> float:
    """Envelope scale for a letter at normalised position u in [0,1] along the text."""
    return max(0.05, 1.0 + bulge * (1.0 - (2.0 * u - 1.0) ** 2))


# ------------------------------------------------------------------------------------------ perspective
def tilt_homography(W: int, H: int, tilt_x: float, tilt_y: float, fov: float = 50.0) -> np.ndarray:
    """3x3 homography that rotates the title plane about the canvas centre and re-projects it."""
    f = (W / 2) / math.tan(math.radians(max(1.0, min(fov, 170.0))) / 2)
    ax, ay = math.radians(-tilt_x), math.radians(-tilt_y)
    Rx = np.array([[1, 0, 0], [0, math.cos(ax), -math.sin(ax)], [0, math.sin(ax), math.cos(ax)]])
    Ry = np.array([[math.cos(ay), 0, math.sin(ay)], [0, 1, 0], [-math.sin(ay), 0, math.cos(ay)]])
    R = Ry @ Rx
    K = np.array([[f, 0, W / 2], [0, f, H / 2], [0, 0, 1]])
    plane = np.column_stack([R[:, 0], R[:, 1], [0, 0, f]])  # plane z=0 placed at distance f
    T = np.array([[1, 0, -W / 2], [0, 1, -H / 2], [0, 0, 1]])
    Hm = K @ plane @ T
    return Hm / Hm[2, 2]


def apply_homography_point(Hm: np.ndarray, x: float, y: float):
    v = Hm @ np.array([x, y, 1.0])
    return v[0] / v[2], v[1] / v[2]


# ---------------------------------------------------------------------------------------------- flag
def flag_offset(W: int, lay: Layout) -> np.ndarray:
    """Per-column vertical displacement (px) of the flag wave."""
    x = np.arange(W, dtype=np.float32)
    return lay.flag_amp * np.sin(2 * math.pi * x / max(lay.flag_wavelength, 1.0) + math.radians(lay.flag_phase))


def flag_maps(W: int, H: int, lay: Layout):
    """cv2.remap maps that push every column down by flag_offset."""
    off = flag_offset(W, lay)
    mx = np.tile(np.arange(W, dtype=np.float32), (H, 1))
    my = np.arange(H, dtype=np.float32)[:, None] - off[None, :]
    return mx, my.astype(np.float32)


def flag_shading(W: int, lay: Layout) -> np.ndarray:
    """Per-column brightness multiplier: fabric facing the light is brighter on the rising slope."""
    x = np.arange(W, dtype=np.float32)
    slope = np.cos(2 * math.pi * x / max(lay.flag_wavelength, 1.0) + math.radians(lay.flag_phase))
    return (1.0 + 0.35 * lay.flag_shade * slope).astype(np.float32)


# ---------------------------------------------------------------------------------------------- wraps
def wrap_maps(W: int, H: int, lay: Layout, text_width: float, cx: float, cy: float, gap: float):
    """cv2.remap maps that wrap the flat title (centred on cx, cy) onto a ticker cylinder, sphere or cube band.

    Returns (map_x, map_y, shade) where shade is a per-pixel brightness multiplier (0 outside the surface)."""
    xs = np.arange(W, dtype=np.float64)
    ys = np.arange(H, dtype=np.float64)
    phase = math.radians(lay.wrap_phase)
    period = text_width + gap
    k = float(np.clip(lay.wrap_shade, 0, 1))

    def tile(u):
        if lay.wrap_repeat:
            return ((u + period / 2) % period) - period / 2
        return u

    if lay.mode == "sphere":
        R = max(lay.wrap_radius * H, 2.0)
        if lay.wrap_repeat:  # whole copies around the equator, so a full spin has no seam
            period = 2 * math.pi * R / max(1, round(2 * math.pi * R / max(period, 1.0)))
        X = (xs[None, :] - W / 2) / R
        Y = (ys[:, None] - cy) / R
        r2 = X ** 2 + Y ** 2
        inside = r2 < 1.0
        Z = np.sqrt(np.clip(1.0 - r2, 0, 1))
        t = math.radians(lay.wrap_tilt)
        Y2 = Y * math.cos(t) - Z * math.sin(t)  # lean the globe's top toward the viewer
        Z2 = Y * math.sin(t) + Z * math.cos(t)
        lon = np.arctan2(X, Z2) + phase
        lat = np.arcsin(np.clip(Y2, -1, 1))
        u = (((lon + math.pi) % (2 * math.pi)) - math.pi) * R
        mx = cx + (u if not lay.wrap_repeat else tile(u))
        my = cy + lat * R
        shade = np.where(inside, (1 - k) + k * Z, 0.0)
        mx = np.where(inside, mx, -1.0)
        return mx.astype(np.float32), my.astype(np.float32), shade.astype(np.float32)

    R = max(lay.wrap_radius * W, 2.0)
    X = (xs - W / 2) / R
    band = 2 * math.pi * R if lay.mode == "ticker" else 8 * R / math.sqrt(2)
    if lay.wrap_repeat:  # whole copies around the closed band, so a full spin has no seam
        period = band / max(1, round(band / max(period, 1.0)))
    if lay.mode == "ticker":
        inside = np.abs(X) < 1.0
        theta = np.arcsin(np.clip(X, -1, 1))
        u = tile(theta * R - phase * R)
        col_shade = np.where(inside, (1 - k) + k * np.cos(theta), 0.0)
    else:  # cube band: four faces of side 2a, a = R / sqrt(2) so the band's corners touch the radius
        a = R / math.sqrt(2)
        u = np.full(W, np.nan)
        col_shade = np.zeros(W)
        best = np.full(W, -1.0)
        for face in range(4):
            al = phase + face * math.pi / 2
            beta = (al + math.pi) % (2 * math.pi) - math.pi  # this face's angle to the camera, -pi..pi
            c = math.cos(beta)
            if c <= 1e-3:
                continue
            sx = (xs - W / 2 - a * math.sin(beta)) / c  # local coordinate along this face
            on = np.abs(sx) <= a
            take = on & (c > best)
            u = np.where(take, beta / (math.pi / 2) * 2 * a + sx, u)  # continuous across neighbouring faces
            col_shade = np.where(take, (1 - k) + k * c, col_shade)
            best = np.where(take, c, best)
        inside = ~np.isnan(u)
        u = np.where(inside, u, 0.0) - phase / (math.pi / 2) * 2 * a  # material coordinate turns with the cube
        u = tile(u)
    mx = np.where(inside, cx + u, -1.0)
    map_x = np.tile(mx[None, :], (H, 1)).astype(np.float32)
    map_y = np.tile(ys[:, None], (1, W)).astype(np.float32)
    shade = np.tile(col_shade[None, :], (H, 1)).astype(np.float32)
    return map_x, map_y, shade
