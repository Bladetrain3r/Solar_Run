"""Race state and the ghost — the opponent is the clock and your last self.

Outrun rules: you start with time on the clock, checkpoints add more,
the checkpoint flagged "finish" ends the run. Clock hits zero first =
run over. The ghost is a recording of (segment, dist, lat, alt) per frame;
the best finished run is saved to data/ghosts/ and replayed next session.
"""

import json
from bisect import bisect_right
from pathlib import Path

GHOST_DIR = Path(__file__).parent / "data" / "ghosts"

RUNNING, FINISHED, TIMEOUT = "running", "finished", "timeout"


class RaceState:
    def __init__(self, start_time):
        self.remaining = start_time
        self.total = 0.0
        self.state = RUNNING

    def update(self, dt):
        if self.state != RUNNING:
            return
        self.total += dt
        self.remaining -= dt
        if self.remaining <= 0.0:
            self.remaining = 0.0
            self.state = TIMEOUT

    def checkpoint(self, ckpt):
        if self.state != RUNNING:
            return
        self.remaining += ckpt.bonus
        if ckpt.finish:
            self.state = FINISHED


class GhostRecorder:
    """Append one frame per tick; keeps memory bounded (10 min cap)."""

    MAX_FRAMES = 60 * 600

    def __init__(self):
        self.times = []
        self.frames = []  # (seg_id, dist, lat, alt)

    def record(self, t, seg_id, dist, lat, alt):
        if len(self.times) < self.MAX_FRAMES:
            self.times.append(t)
            self.frames.append((seg_id, dist, lat, alt))


class GhostPlayer:
    def __init__(self, times, frames, total):
        self.times = times
        self.frames = frames
        self.total = total

    def sample(self, t):
        """Ghost pose at time t, or None once the recording is over."""
        if not self.times or t > self.times[-1]:
            return None
        i = max(0, bisect_right(self.times, t) - 1)
        return self.frames[i]


def ghost_path(track_file_name):
    return GHOST_DIR / f"{track_file_name}.json"


def load_ghost(track_file_name):
    """Best saved run for this track, or None."""
    p = ghost_path(track_file_name)
    if not p.exists():
        return None
    raw = json.loads(p.read_text())
    return GhostPlayer(raw["times"], [tuple(f) for f in raw["frames"]],
                       raw["total"])


def save_ghost_if_best(track_file_name, recorder, total, current_best):
    """Persist this run if it beats the loaded best. Returns True if saved."""
    if current_best is not None and total >= current_best.total:
        return False
    GHOST_DIR.mkdir(parents=True, exist_ok=True)
    ghost_path(track_file_name).write_text(json.dumps({
        "total": total,
        "times": [round(t, 4) for t in recorder.times],
        "frames": [[s, round(d, 2), round(l, 2), round(a, 2)]
                   for s, d, l, a in recorder.frames],
    }))
    return True
