# Solar Run

A branching-route time-attack antigrav racer — Outrun's route-and-fork
structure, where each solar-system body is a distinct physics regime.
Full design & staging: [Design.md](Design.md) · decision log: [Decisions.md](Decisions.md).

## Current stage: 3 — terrain (the MVP done-line)

Low-poly Moon under the ribbon: noise hills + craters, slope-shaded,
seeded per track (custom and random layouts get their own landscape).
The corridor is pressed flat under the racing line so hills frame the
road instead of eating it.

## Stage 2 — the editor

`python3 editor.py` — place/drag points top-down, drag heights (profile
strip along the bottom), paint boost/low-grip spans, drop checkpoints.
S saves to `data/tracks/custom.json`; it appears in the game menu as
CUSTOM. Modes: 1 PLACE · 2 DRAG · 3 HEIGHT · 4 FLAG · 5 CKPT; right-click
deletes; the toolbar warns in red if you author an unfair hairpin.

## Stage 1 — single-spline routes, the clock, the ghost

Tracks are one smooth closed loop each (forks deferred — no joins, nothing
to kink). Pick a stage from the menu, or RANDOM for a generated layout.

**Race** (default): Outrun rules — time on the clock, checkpoints add more,
completing the lap ends the run. Your best run is saved as a ghost and
races alongside you next time.

**Zen** (Z in the menu): no clock, no fail state — just drive laps forever.

## Run

```
pip install -r requirements.txt
python3 main.py                    # menu: Play (Solo Track / Tour) · Options · Exit
python3 main.py --track moon_b1    # straight into a track
python3 main.py --random 42        # generated layout (seeded)
python3 main.py --zen --random     # zen on a fresh random loop
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
- `data/tracks/*.json`: the library — loop points, checkpoint fracs +
  bonuses, painted flag ranges, laps, start_time. Add a JSON, it's in
  the menu.

## Module map

```
main.py    game loop; owns window/input/mode; wires craft+track+timer+render
menu.py    stage select: library + RANDOM, race/zen toggle
editor.py  standalone track editor -> data/tracks/custom.json (one slot)
terrain.py heightfield data: noise + craters, corridor-clamped, per-track
spline.py  Catmull-Rom + arc-length table; distance-based queries
craft.py   handling model; ribbon-space state; reads planet profile
planet.py  physics-profile data loader (data/planets/*.json)
track.py   one closed loop + checkpoints + flags; JSON I/O; random generator
timer.py   race clock (Outrun rules) + ghost record/replay/persist
render.py  software 3D chase-cam renderer — thin, swappable seam
```
