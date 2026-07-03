"""Moon terrain — a low-poly heightfield under the ribbon.

Pure data generation (render.py draws it): value-noise hills + crater
displacement on a coarse grid around the track, shaded by slope. The
corridor under the track is pressed down so terrain never pokes through
the road; the allowance grows with distance, so hills live away from
the racing line. Deterministic per track (seeded from its name) — the
same track always sits in the same landscape.

Low-poly + clean shading is the STYLE, not a placeholder.
"""

import zlib

import numpy as np

CELL = 50.0        # m per grid cell — the low-poly look
MARGIN = 550.0     # m of landscape beyond the track bounds
CLEARANCE = 3.0    # m the corridor sits below the ribbon
CORRIDOR = 28.0    # m half-width of the fully-flattened corridor
MAX_VERTS = 96     # grid cap per axis, keeps generation + draw bounded
LIGHT = np.array([-0.45, -0.35, 0.82])  # fixed sun


def _value_noise(rng, ny, nx, octaves=4):
    """Classic bilinear value noise, octaves summed, in [-1, 1]-ish."""
    out = np.zeros((ny, nx))
    ys = np.linspace(0.0, 1.0, ny)
    xs = np.linspace(0.0, 1.0, nx)
    amp = 1.0
    for o in range(octaves):
        g = 3 * 2 ** o
        grid = rng.uniform(-1.0, 1.0, (g + 1, g + 1))
        gy, gx = ys * g, xs * g
        y0 = np.clip(gy.astype(int), 0, g - 1)[:, None]
        x0 = np.clip(gx.astype(int), 0, g - 1)[None, :]
        ty = (gy[:, None] - y0)
        tx = (gx[None, :] - x0)
        a = grid[y0, x0] * (1 - tx) + grid[y0, x0 + 1] * tx
        b = grid[y0 + 1, x0] * (1 - tx) + grid[y0 + 1, x0 + 1] * tx
        out += amp * (a * (1 - ty) + b * ty)
        amp *= 0.5
    return out / 1.875


class Terrain:
    def __init__(self, track, planet, seed=None):
        if seed is None:
            seed = zlib.crc32(track.file_name.encode())
        rng = np.random.default_rng(seed)

        pts = np.asarray(track.spline.points)
        lo = pts[:, :2].min(0) - MARGIN
        hi = pts[:, :2].max(0) + MARGIN
        nx = min(MAX_VERTS, int((hi[0] - lo[0]) / CELL) + 2)
        ny = min(MAX_VERTS, int((hi[1] - lo[1]) / CELL) + 2)
        xs = np.linspace(lo[0], hi[0], nx)
        ys = np.linspace(lo[1], hi[1], ny)
        X, Y = np.meshgrid(xs, ys)

        # rolling hills + craters
        Z = _value_noise(rng, ny, nx) * float(rng.uniform(14, 22))
        span = float(max(hi[0] - lo[0], hi[1] - lo[1]))
        for _ in range(int(rng.integers(18, 30))):
            cx = float(rng.uniform(lo[0], hi[0]))
            cy = float(rng.uniform(lo[1], hi[1]))
            r = float(rng.uniform(0.02, 0.08) * span)
            depth = r * 0.25
            d = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)
            bowl = -depth * np.clip(1 - (d / r) ** 2, 0, None)
            rim = (depth * 0.35
                   * np.exp(-((d - r) / (0.25 * r)) ** 2) * (d > r * 0.8))
            Z += bowl + rim

        # press the corridor down under the ribbon
        samples = np.array([track.spline.pos_at(t) for t in
                            np.arange(0.0, track.length, 12.0)])
        V = np.stack([X.ravel(), Y.ravel()], axis=1)
        d2 = ((V[:, None, :] - samples[None, :, :2]) ** 2).sum(-1)
        near = d2.argmin(1)
        dist = np.sqrt(d2[np.arange(len(V)), near]).reshape(ny, nx)
        road_z = samples[near, 2].reshape(ny, nx)
        t = np.clip((dist - CORRIDOR) / 200.0, 0.0, 1.0)
        allowance = road_z - CLEARANCE + t * t * 80.0
        Z = np.minimum(Z, allowance)

        self.verts = np.stack([X, Y, Z], axis=-1)

        # per-cell flat shading: lambert on the cell normal + height tint
        dzx = (Z[:-1, 1:] - Z[:-1, :-1]) / CELL
        dzy = (Z[1:, :-1] - Z[:-1, :-1]) / CELL
        n = np.stack([-dzx, -dzy, np.ones_like(dzx)], axis=-1)
        n /= np.linalg.norm(n, axis=-1, keepdims=True)
        lit = np.clip((n * LIGHT).sum(-1), 0.0, 1.0)
        zc = (Z[:-1, :-1] - Z.min()) / max(float(np.ptp(Z)), 1e-6)
        base = np.asarray(planet.ground_color, float)
        shade = (base[None, None, :] * 0.9
                 + (lit * 52 + zc * 14)[:, :, None]
                 + np.array([2.0, 3.0, 6.0]))
        self.cell_colors = np.clip(shade, 0, 255).astype(int)
        self.cell_centers = 0.25 * (self.verts[:-1, :-1] + self.verts[1:, :-1]
                                    + self.verts[:-1, 1:] + self.verts[1:, 1:])
