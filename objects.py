"""On-track entities — anything on the ribbon that isn't the player.

Stage 4: slow movers (wheelers hug the surface, floaters bob). Stage 5
adds static placeables; the weather stage adds temporary hazards. They
all share one shape: a thing at (dist, lat) with an extent, tested
against the player in ribbon space. Couple through data — main owns the
list, craft never sees it.

Collision rules (from Post_MVP_Changes.md):
  soft  (small closing speed): both parties trade momentum, player gets
        nudged off the entity; annoying, survivable.
  hard  (closing speed above TRAFFIC["hard_rv"]): the NPC is knocked
        out and the player respawns at the last checkpoint.
Jumping clears an entity if you're above it; a high-bobbing floater can
even be slipped under.
"""

from dataclasses import dataclass, field

import numpy as np

# ---------------------------------------------------------------------------
TRAFFIC = {
    "pace_frac": 0.6,      # mover cruise speed vs player top speed
    "hard_rv": 28.0,       # m/s closing speed that turns a hit deadly
    "soft_brake": 0.65,    # fraction of closing speed the player loses
    "soft_shove": 0.35,    # fraction the entity gains
    "lat_kick": 6.0,       # m/s sideways nudge off a soft hit
    "spawn_gap": 120.0,    # m kept clear around the start line
    "player_half_l": 4.0,  # m, player longitudinal half-extent
    "player_half_w": 1.6,  # m, player lateral half-extent
    "player_height": 1.3,  # m, player hull height (for slip-unders)
}


@dataclass
class Entity:
    kind: str            # "wheeler" | "floater"
    dist: float          # m along the loop, kept in [0, L)
    lat: float
    speed: float
    half_l: float
    half_w: float
    height: float
    alt: float = 0.0     # metres above the ribbon (floaters bob)
    phase: float = 0.0
    alive: bool = True


def spawn_traffic(track, count, pace, seed=None):
    """`count` movers, equally distributed around the loop, deterministic
    per track (same seed -> same traffic pattern, so time attack is fair)."""
    if count <= 0:
        return []
    import zlib
    if seed is None:
        seed = zlib.crc32(("traffic:" + track.file_name).encode())
    rng = np.random.default_rng(seed)
    L = track.length
    entities = []
    usable = L - 2 * TRAFFIC["spawn_gap"]
    for i in range(count):
        d = TRAFFIC["spawn_gap"] + usable * (i + 0.5) / count
        kind = "wheeler" if rng.random() < 0.5 else "floater"
        lat = float(rng.choice([-6.0, -2.5, 2.5, 6.0]))
        if kind == "wheeler":
            e = Entity(kind, d, lat, pace * float(rng.uniform(0.9, 1.05)),
                       half_l=3.2, half_w=1.5, height=1.6)
        else:
            e = Entity(kind, d, lat, pace * float(rng.uniform(0.95, 1.1)),
                       half_l=2.6, half_w=1.4, height=1.3,
                       phase=float(rng.uniform(0, 6.28)))
        entities.append(e)
    return entities


def update_traffic(entities, track, pace, dt):
    L = track.length
    for e in entities:
        if not e.alive:
            continue
        e.dist = (e.dist + e.speed * dt) % L
        e.speed += (pace - e.speed) * min(1.0, 1.5 * dt)  # settle to cruise
        if e.kind == "floater":
            e.phase += dt * 2.2
            e.alt = 0.7 + 0.6 * np.sin(e.phase)


def collide_player(entities, craft, L):
    """Resolve player-vs-entity overlaps. Returns "hard" if the player
    must respawn, "soft" if they traded paint, None otherwise."""
    t = TRAFFIC
    result = None
    m = craft.dist % L
    for e in entities:
        if not e.alive:
            continue
        dd = (e.dist - m + L / 2) % L - L / 2  # signed along-track gap
        if abs(dd) > e.half_l + t["player_half_l"]:
            continue
        if abs(e.lat - craft.lat) > e.half_w + t["player_half_w"]:
            continue
        if craft.alt > e.alt + e.height:      # jumped clean over
            continue
        if craft.alt + t["player_height"] < e.alt:  # slipped under a bob
            continue

        rv = craft.speed - e.speed
        if rv > t["hard_rv"]:
            e.alive = False
            return "hard"

        # soft: momentum trade + get pushed off the entity
        if rv > 0:
            craft.speed = max(0.0, craft.speed - rv * t["soft_brake"])
            e.speed += rv * t["soft_shove"]
        if dd > 0 and rv > 2.0:  # rear-ended it: sit the player behind
            overlap = (e.half_l + t["player_half_l"]) - dd
            craft.dist -= max(0.0, overlap)
        kick = -t["lat_kick"] if craft.lat < e.lat else t["lat_kick"]
        craft.lat_vel += kick
        result = "soft"
    return result
