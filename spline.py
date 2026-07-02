"""Catmull-Rom spline with arc-length parameterization.

The one genuinely-shared module. A Spline is built from 3D control points
(x, y on the plane, z = height) that the curve passes THROUGH. Everything
downstream (craft, track, editor, render) asks it distance-based questions:
"where is the track D metres along?", "which way is forward there?".

Coordinate convention: x/y horizontal plane, z up. World up = (0, 0, 1).
"""

import numpy as np

WORLD_UP = np.array([0.0, 0.0, 1.0])


class Spline:
    """Uniform Catmull-Rom through control points, with a distance->t table.

    closed=True wraps the curve into a loop (racing circuit).
    closed=False spans ALL the given points (P0..Pn) by adding reflected
    phantom endpoints — used for track segments that join other segments.
    samples_per_seg controls arc-length table resolution; 32 is plenty
    for metre-accurate queries on track-scale geometry.
    """

    def __init__(self, points, closed=True, samples_per_seg=32):
        self.points = np.asarray(points, dtype=float)
        if self.points.ndim != 2 or self.points.shape[1] != 3:
            raise ValueError("points must be an (N, 3) array")
        if len(self.points) < (4 if closed else 2):
            raise ValueError("not enough control points")
        self.closed = closed
        if closed:
            self._ext = self.points
            self.n_segs = len(self.points)
        else:
            lead = 2.0 * self.points[0] - self.points[1]
            tail = 2.0 * self.points[-1] - self.points[-2]
            self._ext = np.vstack([lead, self.points, tail])
            self.n_segs = len(self.points) - 1
        self._build_arc_table(samples_per_seg)

    # --- raw parameter-space evaluation -----------------------------------

    def _seg_points(self, seg):
        """The 4 control points governing segment `seg` (curve runs p1->p2)."""
        n = len(self._ext)
        if self.closed:
            idx = [(seg - 1) % n, seg % n, (seg + 1) % n, (seg + 2) % n]
        else:
            idx = [seg, seg + 1, seg + 2, seg + 3]
        return (self._ext[idx[0]], self._ext[idx[1]],
                self._ext[idx[2]], self._ext[idx[3]])

    def _seg_t(self, u):
        """Split global parameter into (segment index, local t), clamping
        the open-spline end so u == n_segs evaluates the final point."""
        if not self.closed and u >= self.n_segs:
            return self.n_segs - 1, 1.0
        seg = int(u) % self.n_segs
        return seg, u - int(u)

    def point_at(self, u):
        """Evaluate at global parameter u in [0, n_segs]. Returns 3D point."""
        seg, t = self._seg_t(u)
        p0, p1, p2, p3 = self._seg_points(seg)
        t2, t3 = t * t, t * t * t
        return 0.5 * ((2.0 * p1)
                      + (-p0 + p2) * t
                      + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t2
                      + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t3)

    def tangent_at(self, u):
        """Unnormalized curve derivative at global parameter u."""
        seg, t = self._seg_t(u)
        p0, p1, p2, p3 = self._seg_points(seg)
        t2 = t * t
        return 0.5 * ((-p0 + p2)
                      + 2.0 * (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t
                      + 3.0 * (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t2)

    # --- arc-length table: the distance <-> parameter seam ----------------

    def _build_arc_table(self, samples_per_seg):
        n = self.n_segs * samples_per_seg + 1
        self._us = np.linspace(0.0, self.n_segs, n)
        pts = np.array([self.point_at(u) for u in self._us])
        seg_lens = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        self._dists = np.concatenate([[0.0], np.cumsum(seg_lens)])
        self.length = float(self._dists[-1])

    def _u_at_dist(self, d):
        """Distance along curve -> global parameter, via table + lerp."""
        if self.closed:
            d = d % self.length
        else:
            d = min(max(d, 0.0), self.length)
        i = int(np.searchsorted(self._dists, d, side="right")) - 1
        i = min(max(i, 0), len(self._dists) - 2)
        span = self._dists[i + 1] - self._dists[i]
        frac = (d - self._dists[i]) / span if span > 0 else 0.0
        return self._us[i] + frac * (self._us[i + 1] - self._us[i])

    # --- distance-based queries (the public vocabulary) -------------------

    def pos_at(self, d):
        """3D point D metres along the track."""
        return self.point_at(self._u_at_dist(d))

    def forward_at(self, d):
        """Unit tangent D metres along the track."""
        t = self.tangent_at(self._u_at_dist(d))
        n = np.linalg.norm(t)
        return t / n if n > 0 else np.array([1.0, 0.0, 0.0])

    def curvature_at(self, d, h=1.0):
        """Signed horizontal curvature D metres along, in rad/m.

        Positive = track bending left (CCW seen from above). This is the
        rate the centerline's heading changes per metre — the craft's
        centrifugal drift is curvature * speed^2.
        """
        f1 = self.forward_at(d - h)
        f2 = self.forward_at(d + h)
        cross = f1[0] * f2[1] - f1[1] * f2[0]
        dot = f1[0] * f2[0] + f1[1] * f2[1]
        return float(np.arctan2(cross, dot)) / (2.0 * h)

    def frame_at(self, d):
        """(pos, forward, right, up) frame D metres along the track.

        Right/up derived from the tangent and world up, so the ribbon
        follows pitch but stays unbanked (banking is a later flourish).
        """
        pos = self.pos_at(d)
        fwd = self.forward_at(d)
        right = np.cross(fwd, WORLD_UP)
        n = np.linalg.norm(right)
        right = right / n if n > 1e-6 else np.array([0.0, -1.0, 0.0])
        up = np.cross(right, fwd)
        return pos, fwd, right, up
