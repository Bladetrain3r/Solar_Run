"""Track = ONE closed-loop spline + checkpoints + painted surface flags.

No forks, no segment joins — a single smooth Catmull-Rom loop, so there is
nothing to kink and nothing to jarringly switch (forks are deferred; route
variety = pick a track from the library before a run, or generate one).

Race = `laps` times around, Outrun clock rules; the lap line is the finish
gate. Zen = the same loop, forever.

Tracks are data: data/tracks/*.json. Checkpoints and flag ranges are
authored as fracs (0..1 of the loop) so humans don't need arc lengths.
random_track() builds the same data shape procedurally — a generated
track IS a track.
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


class Checkpoint:
    def __init__(self, dist, bonus, finish=False):
        self.dist = dist
        self.bonus = bonus
        self.finish = finish


class Track:
    @classmethod
    def load(cls, name):
        return cls(json.loads((TRACK_DIR / f"{name}.json").read_text()), name)

    @classmethod
    def list_available(cls):
        return sorted(p.stem for p in TRACK_DIR.glob("*.json"))

    def __init__(self, raw, name="unnamed"):
        self.file_name = name
        self.name = raw["name"]
        self.planet = raw["planet"]
        self.start_time = raw.get("start_time", 45.0)
        self.laps = raw.get("laps", 1)
        self.spline = Spline(raw["points"], closed=True)
        self.length = self.spline.length
        self.checkpoints = [Checkpoint(c["frac"] * self.length,
                                       c.get("bonus", 0.0))
                            for c in raw.get("checkpoints", [])]
        self.finish_gate = Checkpoint(0.0, 0.0, finish=True)  # the lap line
        # painted flag ranges, in metres: (from, to, flag) — may wrap
        self.flag_ranges = [(r["from"] * self.length, r["to"] * self.length,
                             r["flag"]) for r in raw.get("flags", [])]

    # --- queries -----------------------------------------------------------

    def flag_at(self, dist):
        m = dist % self.length
        for a, b, flag in self.flag_ranges:
            if (a <= m < b) if a <= b else (m >= a or m < b):
                return flag
        return "normal"

    def advance(self, old_dist, new_dist):
        """Everything crossed in (old_dist, new_dist] on the unwrapped
        line: ("checkpoint", ckpt) and ("lap", n) events, in order."""
        events = []
        L = self.length
        for c in self.checkpoints:
            k = int(old_dist // L)
            while c.dist + k * L <= new_dist:
                if c.dist + k * L > old_dist:
                    events.append((c.dist + k * L, "checkpoint", c))
                k += 1
        k = int(old_dist // L) + 1
        while k * L <= new_dist:
            events.append((k * L, "lap", k))
            k += 1
        return [(kind, data) for _pos, kind, data in sorted(events,
                                                            key=lambda e: e[0])]

    def dist_to_next_checkpoint(self, dist):
        m = dist % self.length
        gaps = [(c.dist - m) % self.length for c in self.checkpoints]
        return min(gaps) if gaps else None

    # --- render feed --------------------------------------------------------

    def sample_ahead(self, dist, span):
        """Walk the ribbon from dist-12 to dist+span.

        Returns (samples, gates):
          samples: [(d_off, pos, right, flag), ...]
          gates:   [(d_off, pos, right, up, checkpoint), ...] — checkpoints
                   plus the lap line (finish gate).
        """
        samples = []
        d_off = -12.0
        while d_off < span:
            d = dist + d_off
            pos, _f, right, _u = self.spline.frame_at(d)
            samples.append((d_off, pos, right, self.flag_at(d)))
            d_off += 3.0 if d_off < 80 else (8.0 if d_off < 200 else 16.0)

        gates = []
        for c in self.checkpoints + [self.finish_gate]:
            g = (c.dist - dist) % self.length
            if g < span:
                pos, _f, right, up = self.spline.frame_at(c.dist)
                gates.append((g, pos, right, up, c))
        return samples, gates


def random_track(seed=None, planet="moon"):
    """Generate a smooth closed loop: control points laid out radially
    around a centre (star-shaped, so it can never self-intersect), with
    jittered radius, rolling height, and a couple of painted flag arcs."""
    rng = np.random.default_rng(seed)
    n = int(rng.integers(10, 15))
    base_r = float(rng.uniform(260, 380))
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False)
    angles += rng.uniform(-0.12, 0.12, n) * (2 * np.pi / n)
    radii = base_r * (1.0 + rng.uniform(-0.22, 0.35, n))
    heights = rng.uniform(-1, 1, n)
    for _ in range(2):  # smooth the height walk so slopes stay gentle
        heights = (heights + np.roll(heights, 1) + np.roll(heights, -1)) / 3.0
    heights *= float(rng.uniform(10, 22))

    points = [[float(r * np.cos(a)), float(r * np.sin(a)), float(h)]
              for a, r, h in zip(angles, radii, heights)]

    f1 = float(rng.uniform(0.15, 0.55))
    f2 = float(rng.uniform(0.6, 0.9))
    raw = {
        "name": f"Random {seed if seed is not None else '??'}",
        "planet": planet,
        "laps": 1,
        "points": points,
        "checkpoints": [{"frac": 0.33, "bonus": 15.0},
                        {"frac": 0.66, "bonus": 12.0}],
        "flags": [{"from": f1, "to": f1 + 0.08, "flag": "low_grip"},
                  {"from": f2, "to": f2 + 0.06, "flag": "boost"}],
    }
    t = Track(raw, name=f"random-{seed}")
    t.start_time = round(t.length / 75.0 + 10.0)  # generous; tune later
    return t
