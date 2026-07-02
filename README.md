# Solar Run

A branching-route time-attack antigrav racer — Outrun's route-and-fork
structure, where each solar-system body is a distinct physics regime.
Full design & staging: [Design.md](Design.md) · decision log: [Decisions.md](Decisions.md).

## Current stage: 1 — routes, forks, the clock, the ghost

**Race** (default): Outrun rules — time on the clock, checkpoints add more,
the finish gate ends the run. Steer into a fork's side to pick the branch
(left = the low-grip shortcut, right = the safe dip route). Your best run
is saved as a ghost and races alongside you next time.

**Zen** (`--zen`): no clock, no fail state — the track graph is cyclic,
just drive forever.

## Run

```
pip install -r requirements.txt
python3 main.py          # race
python3 main.py --zen    # zen roaming
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
- `data/tracks/moon_a1.json`: the track — segment graph, fork topology,
  surface flags, checkpoint fracs/bonuses, start_time.

## Module map

```
main.py    game loop; owns window/input/mode; wires craft+track+timer+render
spline.py  Catmull-Rom + arc-length table; distance-based queries
craft.py   handling model; ribbon-space state; reads planet profile
planet.py  physics-profile data loader (data/planets/*.json)
track.py   segment graph + forks + checkpoints + flags; JSON I/O; render feed
timer.py   race clock (Outrun rules) + ghost record/replay/persist
render.py  software 3D chase-cam renderer — thin, swappable seam
```
