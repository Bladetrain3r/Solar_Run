"""Planet terrain — a low-poly heightfield under the ribbon.

Pure data generation (render.py draws it): value-noise hills + crater
displacement on a coarse grid around the track, shaded by slope, tuned
per planet via the planet JSON's "terrain" ranges. The corridor under
the track is pressed down so terrain never pokes through the road.
Deterministic per track (seeded from its name).

Feature "lava_lakes": indents below a fill-level flood — flooded
vertices are raised TO the level, so lakes are literally flat planes in
the same mesh (no separate liquid pass). Lava cells get pulsing colors
in the renderer; "opacity" blends the liquid over the rock it covers.
Generic for any liquid a planet JSON describes.

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

TERRAIN_DEFAULTS = {   # Moon-like; planet JSON "terrain" overrides
    "hill_amp": (14.0, 22.0),
    "craters": (18, 30),
    "crater_r": (0.02, 0.08),   # fraction of map span
    "corridor_blend": 200.0,    # m over which terrain may rise again
                                # beside the road (smaller = landscape
                                # and liquids crowd the racing line)
}


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
        tp = {**TERRAIN_DEFAULTS, **planet.terrain}

        pts = np.asarray(track.spline.points)
        lo = pts[:, :2].min(0) - MARGIN
        hi = pts[:, :2].max(0) + MARGIN
        nx = min(MAX_VERTS, int((hi[0] - lo[0]) / CELL) + 2)
        ny = min(MAX_VERTS, int((hi[1] - lo[1]) / CELL) + 2)
        xs = np.linspace(lo[0], hi[0], nx)
        ys = np.linspace(lo[1], hi[1], ny)
        X, Y = np.meshgrid(xs, ys)

        # rolling hills + craters, tuned by the planet
        Z = _value_noise(rng, ny, nx) * float(rng.uniform(*tp["hill_amp"]))
        span = float(max(hi[0] - lo[0], hi[1] - lo[1]))
        for _ in range(int(rng.integers(*tp["craters"]))):
            cx = float(rng.uniform(lo[0], hi[0]))
            cy = float(rng.uniform(lo[1], hi[1]))
            r = float(rng.uniform(*tp["crater_r"]) * span)
            depth = r * 0.25
            d = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)
            bowl = -depth * np.clip(1 - (d / r) ** 2, 0, None)
            rim = (depth * 0.35
                   * np.exp(-((d - r) / (0.25 * r)) ** 2) * (d > r * 0.8))
            Z += bowl + rim
        natural = Z.copy()   # pre-corridor stats, for liquid level

        # press the corridor down under the ribbon
        samples = np.array([track.spline.pos_at(t) for t in
                            np.arange(0.0, track.length, 12.0)])
        V = np.stack([X.ravel(), Y.ravel()], axis=1)
        d2 = ((V[:, None, :] - samples[None, :, :2]) ** 2).sum(-1)
        near = d2.argmin(1)
        dist = np.sqrt(d2[np.arange(len(V)), near]).reshape(ny, nx)
        road_z = samples[near, 2].reshape(ny, nx)
        t = np.clip((dist - CORRIDOR) / float(tp["corridor_blend"]), 0.0, 1.0)
        allowance = road_z - CLEARANCE + t * t * 80.0
        Z = np.minimum(Z, allowance)

        # flood deep indents with liquid (lava on Mercury): raise flooded
        # vertices TO the level — the lake IS the mesh, drawn flat
        self.liquid = None
        level = None
        if "lava_lakes" in planet.features and planet.liquid:
            liq = planet.liquid
            level = float(np.percentile(natural,
                                        liq.get("fill", 0.15) * 100.0))
            Z = np.where(Z < level, level, Z)
            # consolidate shorelines: a vertex sitting barely above the
            # level with 2+ flooded neighbours gets pulled down too —
            # otherwise terrain undulating around the level makes
            # checkerboard lakes (alternating lava/rock cells)
            for _ in range(2):
                at = np.abs(Z - level) < 0.01
                nb = np.zeros_like(Z)
                nb[1:, :] += at[:-1, :]
                nb[:-1, :] += at[1:, :]
                nb[:, 1:] += at[:, :-1]
                nb[:, :-1] += at[:, 1:]
                pull = (~at) & (nb >= 2) & (Z < level + 2.5)
                Z[pull] = level
            Z = np.minimum(Z, allowance)  # never above the road corridor
            self.liquid = liq

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
        rock = np.clip(shade, 0, 255)
        self.cell_colors = rock.astype(int)
        self.cell_centers = 0.25 * (self.verts[:-1, :-1] + self.verts[1:, :-1]
                                    + self.verts[:-1, 1:] + self.verts[1:, 1:])

        if self.liquid is not None:
            eps = 0.01
            at = np.abs(Z - level) < eps
            self.lava_mask = (at[:-1, :-1] & at[1:, :-1]
                              & at[:-1, 1:] & at[1:, 1:])
            op = float(self.liquid.get("opacity", 0.85))
            c = np.asarray(self.liquid.get("color", [255, 96, 24]), float)
            g = np.asarray(self.liquid.get("glow", c), float)
            # fake transparency: composite liquid over the rock it covers
            self.lava_c0 = np.clip(rock * (1 - op) + c * op, 0, 255).astype(int)
            self.lava_c1 = np.clip(rock * (1 - op) + g * op, 0, 255).astype(int)
            self.lava_phase = rng.uniform(0.0, 6.283, self.lava_mask.shape)
            self.lava_speed = float(self.liquid.get("pulse_speed", 1.6))
