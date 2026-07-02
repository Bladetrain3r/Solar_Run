"""Track = a directed graph of spline segments + forks + checkpoints + flags.

A segment is an open Catmull-Rom spline with a `next` list: one entry means
the track continues, two means a FORK. The craft picks a branch with its
lateral position at the split — steer left half (lat < 0) for next[0],
right half for next[1]. Authoring convention: list the LEFT branch first.

A track graph may be CYCLIC (branches rejoin, the last segment points back
at the first) — that's what makes zen mode endless. Race mode just runs
until a checkpoint flagged "finish" fires.

Tracks are data: data/tracks/*.json. The engine reads them; the (future)
editor writes them. Checkpoint positions are authored as `frac` (0..1 of
segment length) so humans don't need to know arc lengths.
"""

import json
from pathlib import Path

import numpy as np

from spline import Spline

TRACK_DIR = Path(__file__).parent / "data" / "tracks"

# flag -> (grip multiplier, bonus accel m/s^2, road tint RGB or None)
SURFACE_FLAGS = {
    "normal":   (1.0, 0.0, None),
    "low_grip": (0.5, 0.0, (72, 96, 130)),
    "boost":    (1.0, 30.0, (120, 84, 40)),
}


class Segment:
    def __init__(self, seg_id, points, next_ids, flag):
        self.id = seg_id
        self.spline = Spline(points, closed=False)
        self.length = self.spline.length
        self.next = next_ids
        self.flag = flag


class Checkpoint:
    def __init__(self, seg_id, dist, bonus, finish):
        self.seg = seg_id
        self.dist = dist
        self.bonus = bonus
        self.finish = finish


class Track:
    @classmethod
    def load(cls, name):
        return cls(json.loads((TRACK_DIR / f"{name}.json").read_text()), name)

    def __init__(self, raw, name="unnamed"):
        self.file_name = name
        self.name = raw["name"]
        self.planet = raw["planet"]
        self.start_segment = raw["start_segment"]
        self.start_time = raw.get("start_time", 45.0)
        self.segments = {
            sid: Segment(sid, s["points"], s["next"], s.get("flag", "normal"))
            for sid, s in raw["segments"].items()
        }
        self.checkpoints = []
        for c in raw.get("checkpoints", []):
            seg = self.segments[c["segment"]]
            self.checkpoints.append(Checkpoint(
                seg.id, c["frac"] * seg.length,
                c.get("bonus", 0.0), c.get("finish", False)))
        self._ckpts_by_seg = {}
        for c in self.checkpoints:
            self._ckpts_by_seg.setdefault(c.seg, []).append(c)
        for lst in self._ckpts_by_seg.values():
            lst.sort(key=lambda c: c.dist)

    # --- graph walking -----------------------------------------------------

    def choose(self, seg_id, lat):
        """Which segment follows seg_id, given the craft's lateral position.
        Fork rule: left half of the ribbon (lat < 0) -> next[0]."""
        nxt = self.segments[seg_id].next
        if not nxt:
            return None
        if len(nxt) == 1:
            return nxt[0]
        return nxt[0] if lat < 0 else nxt[1]

    def advance(self, seg_id, old_dist, craft):
        """Handle everything that happened between old_dist and craft.dist:
        checkpoint crossings and segment transitions (incl. fork choice).
        Mutates craft (set_segment) on transition. Returns
        (new_seg_id, events) where events is a list of
        ("checkpoint", Checkpoint) / ("fork", chosen_seg_id)."""
        events = []
        lo = old_dist
        while True:
            seg = self.segments[seg_id]
            hi = min(craft.dist, seg.length)
            for c in self._ckpts_by_seg.get(seg_id, []):
                if lo < c.dist <= hi:
                    events.append(("checkpoint", c))
            if craft.dist <= seg.length:
                return seg_id, events
            # transition: hop to the chosen next segment
            new_id = self.choose(seg_id, craft.lat)
            if new_id is None:  # dead end: stop at the end of the ribbon
                craft.dist = seg.length
                return seg_id, events
            if len(seg.next) > 1:
                events.append(("fork", new_id))
            new_seg = self.segments[new_id]
            # keep the craft's world position continuous: re-express lat
            # in the new segment's frame (joints share a point, tangents
            # may differ slightly)
            _, _, right_old, _ = seg.spline.frame_at(seg.length)
            _, _, right_new, _ = new_seg.spline.frame_at(0.0)
            leftover = craft.dist - seg.length
            craft.set_segment(new_seg.spline,
                              leftover,
                              craft.lat * float(np.dot(right_old, right_new)))
            seg_id, lo = new_id, 0.0

    def frame_at_offset(self, seg_id, dist, offset, lat=0.0, prev_seg=None):
        """Frame `offset` metres ahead (or behind) of (seg_id, dist),
        hopping segments forward via the fork rule. Behind the segment
        start, falls back into prev_seg if given, else clamps."""
        d = dist + offset
        if d < 0 and prev_seg:
            seg_id, d = prev_seg, d + self.segments[prev_seg].length
        while d > self.segments[seg_id].length:
            nxt = self.choose(seg_id, lat)
            if nxt is None:
                break
            d -= self.segments[seg_id].length
            seg_id = nxt
        return self.segments[seg_id].spline.frame_at(max(0.0, d))

    def dist_to_next_checkpoint(self, seg_id, dist, lat, cap=3000.0):
        """Metres to the next checkpoint along the branch the craft is
        currently lined up for, or None if none within cap."""
        acc, d = 0.0, dist
        while acc < cap:
            seg = self.segments[seg_id]
            for c in self._ckpts_by_seg.get(seg_id, []):
                if c.dist > d:
                    return acc + c.dist - d
            acc += seg.length - d
            nxt = self.choose(seg_id, lat)
            if nxt is None:
                return None
            seg_id, d = nxt, 0.0
        return None

    # --- render feed ---------------------------------------------------------

    def sample_ahead(self, seg_id, dist, span, lat, prev_seg=None):
        """Walk the ribbon from `dist - 12` to `dist + span`, hopping joins.

        Returns (primary, alt, gates):
          primary: [(d_off, pos, right, flag), ...] along the branch the
                   craft is lined up for
          alt:     same, down the OTHER branch of the first fork in the
                   window (capped ~180 m) — so the player sees the choice
          gates:   [(d_off, pos, right, up, checkpoint), ...] for both
        """
        primary, alt, gates = [], [], []
        fork_state = None  # (other_seg_id, d_off at the fork)

        def walk(seg_id, d, d_off, out, limit, follow_forks):
            nonlocal fork_state
            while d_off < limit:
                seg = self.segments[seg_id]
                d_clamped = min(d, seg.length)
                pos, _f, right, up = seg.spline.frame_at(d_clamped)
                out.append((d_off, pos, right, seg.flag))
                for c in self._ckpts_by_seg.get(seg_id, []):
                    step = self._step(d_off)
                    if d_clamped <= c.dist < d_clamped + step:
                        cpos, _cf, cright, cup = seg.spline.frame_at(c.dist)
                        gates.append((d_off + (c.dist - d_clamped),
                                      cpos, cright, cup, c))
                step = self._step(d_off)
                d += step
                d_off += step
                if d > seg.length:
                    nxt = self.choose(seg_id, lat)
                    if nxt is None:
                        break
                    if follow_forks and len(seg.next) > 1 and fork_state is None:
                        other = seg.next[1] if nxt == seg.next[0] else seg.next[0]
                        fork_state = (other, d_off)
                    d -= seg.length
                    seg_id = nxt

        start_seg, start_d = seg_id, dist - 12.0
        if start_d < 0 and prev_seg:
            start_seg, start_d = prev_seg, start_d + self.segments[prev_seg].length
        start_d = max(0.0, start_d)
        walk(start_seg, start_d, -12.0, primary, span, True)
        if fork_state:
            other, fork_off = fork_state
            walk(other, 0.0, fork_off, alt, min(span, fork_off + 180.0), False)
        return primary, alt, gates

    @staticmethod
    def _step(d_off):
        """Ribbon sampling stride: fine near the camera, coarse far away."""
        return 3.0 if d_off < 80 else (8.0 if d_off < 200 else 16.0)
