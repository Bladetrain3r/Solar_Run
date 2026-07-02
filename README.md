# Solar Run

A branching-route time-attack antigrav racer — Outrun's route-and-fork
structure, where each solar-system body is a distinct physics regime.
Full design & staging: [Design.md](Design.md) · decision log: [Decisions.md](Decisions.md).

## Current stage: 0 — handling on a hardcoded spline

A grey capsule on a grey ribbon over the Moon. One ~1.5 km closed loop with
a climbing sweeper, a crest you can launch off, and a dip. This stage exists
to make the fling feel good — everything else waits on that.

## Run

```
pip install -r requirements.txt
python3 main.py
```

| Key | Action |
|---|---|
| W / ↑ | thrust |
| S / ↓ | brake |
| A,D / ←,→ | steer |
| Space | jump |
| Shift (tap) | boost — ~30 g lateral kick in your steer direction; forward slam to top speed if steering neutral; full power airborne |
| R | reset |
| Esc | quit |

Headless smoke test: `python3 main.py --smoke 300 [screenshot.png]`

## Tuning the feel

- `craft.py` → `TUNING` dict: thrust, brake, steering thrust + lateral grip,
  jump impulse, air control, rail bounce. Iterate here longest.
- The craft has its own trajectory: track curvature shoves you toward the
  outside at `curvature × speed²`; steering is the force you supply against
  it. Max corner speed = `sqrt(steer_accel × grip / curvature)` — brake for
  the final hairpin.
- `data/planets/moon.json`: gravity / drag / grip — gameplay-scaled numbers,
  relative feel between bodies is what matters.
- `main.py` → `TRACK_POINTS`: the hardcoded circuit (3D control points the
  spline threads through).

## Module map

```
main.py    game loop; owns window/input; hardcoded Stage-0 track
spline.py  Catmull-Rom + arc-length table; distance-based queries
craft.py   handling model; ribbon-space state; reads planet profile
planet.py  physics-profile data loader (data/planets/*.json)
render.py  software 3D chase-cam renderer — thin, swappable seam
```
