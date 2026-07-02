# Antigrav Solar-System Racer — Design & Architecture Doc

**Author:** Ziggy
**Status:** MVP spec. Repo-ready. Intended for staged build (solo + Code handoff).
**One-line pitch:** A *branching-route time-attack* antigrav racer — the Outrun
route-and-fork structure (not position racing), where each solar-system body is a
distinct physics-and-hazard regime. 2D-bound steering on a 3D-capable ribbon.

---

## Design thesis (what makes this the thing, not another racer)

- **Structure = Outrun, not F-Zero.** The opponent is the *clock and the route*,
  not other racers. Branching forks at checkpoints; you navigate a tree of track
  against time. This is the underexploited lineage — Redout/Wipeout/F-Zero are
  *position* racers; this is *route time-attack*. The novelty is structural.
- **Setting = free content-variety generator.** Each body is a **physics regime**,
  not a skin: gravity (jump-arc/fall-speed), atmospheric drag (speed bleed),
  grip (turn authority), surface hazards. The real solar system hands you ~10
  distinct handling+hazard packages you didn't have to invent. *Constrain the
  world, not the actor* — the craft stays constant; the planet imposes the rules.
- **2D-bound, 3D-capable.** Steering is lateral + jump (Skyroads-legible), NOT
  full 6-DOF. Keeps it readable AND keeps track authoring tractable. The ribbon
  itself can have elevation (dips, rises, banks, leaps) — 2D control, 3D surface.
- **Time-attack spine = cheap to build.** No competitive AI needed (a ghost/timer
  is the opponent). This is what makes it solo-buildable. Position-race mode is an
  optional later layer, not the spine.

---

## Code style & architecture constraints (firm)

- **Self-contained.** Minimise dependencies. Stdlib where possible; numpy for
  vector/spline math; one rendering lib (see stack below). No engine, no framework
  sprawl.
- **~500 lines/file ceiling.** If a file wants to grow past it, that's a signal to
  split by responsibility. Unavoidable exceptions get a comment saying why.
- **Prefer shallow duplication over entanglement.** Two modules each with their own
  small copy of a helper beats a shared "utils" god-module everyone imports and
  nobody can change safely. Couple through *data* (plain dicts/dataclasses/JSON),
  not through deep inheritance or shared mutable state.
- **Data-oriented.** Tracks, planets, craft-tuning are *data* (JSON / dataclasses),
  not code. The engine reads data; the editor writes data. This is the seam that
  keeps "add a planet" a content task, not an engineering task.
- **Debuggable by reading top-to-bottom.** Magic Launcher discipline. A new reader
  (or a future tired you) should follow any single file without a call-graph.
- **Modify-and-expand friendly.** Every stage below leaves a *playable* artifact;
  no stage requires a later stage to be usable.

---

## Tech stack (grounded)

- **Python 3 + pygame** for the MVP. Rationale: pygame is available/pip-installable,
  stdlib-adjacent in spirit, gives you a window + input + 2D/simple-3D drawing +
  audio with almost no ceremony, and is debuggable. It's the Magic-Launcher-shaped
  choice — enough to make the game, not so much it becomes the project.
- **numpy** for spline math, arc-length tables, vector ops (available).
- Rendering approach for MVP: **software/simple 3D** — project the 3D ribbon +
  heightmap to 2D yourself (this is the "throwback" look, and it's a *style* not a
  placeholder). No shader pipeline needed to prove fun. If you later want real GPU
  shaders (moderngl/pyglet), that's a *rendering-layer swap* the architecture
  should tolerate — keep rendering behind a thin interface so it's replaceable.
- **If Python's perf becomes the wall** (it may, for lots of ribbon geometry at
  framerate): the handling/track *logic* is portable, and only the *render/inner
  loop* would need a faster substrate. Design so logic ≠ rendering, so a later
  port doesn't touch the fun.

---

## The core representation: the branching spline

Everything hangs off this, so it's defined once, up front.

- A **track** is a **Catmull-Rom spline** (control points the curve passes
  *through* — authoring is "the track goes here, then here"; more intuitive than
  Bézier handles).
- Control points are **3D** (x, y on the plane + height), but **authored mostly in
  2D top-down** (route shape) with a **side view for height**. Decide this now:
  points are 3D from day one, you just usually edit them top-down.
- A **fork** = a node with **two child splines sharing a start point.** Forks are
  a property of the data structure, not a special piece. The craft picks a branch
  by lateral position at the split → *forks and steering are the same mechanic.*
- The **ribbon** (drivable surface) is *generated* from the spline: extrude the
  centerline to a width, derive banking/normal from the curve. You edit a line;
  the engine makes the surface.
- **Arc-length parameterization** (do this early — retrofitting is misery): build a
  distance→t lookup table by sampling the curve. This makes "point N metres along
  track", player progress, checkpoints, ghosts, and speed all trivial
  distance-queries instead of fighting raw `t`. (Note: this is literally your
  dynamics-ladder integral — walk the spline in small steps, sum segment lengths =
  accumulated path length. `state += rate·dt` shows up here.)

**Track data = a list of control points (3D) + fork topology + per-segment surface
flags (normal / boost / low-grip / hazard) + checkpoints (distance markers).**
That's the *entire* functional track vocabulary. No props in the data model —
props are decoration, added post-MVP.

---

## Stages (each ends in a playable/usable artifact)

### Stage 0 — Handling on a hardcoded spline (THE make-or-break)
**Goal:** a grey capsule feels *good* to fling around a grey ribbon on one planet.
No editor, no terrain, no forks, no art. Ribbon can float in void.

Modules:
- `spline.py` — Catmull-Rom eval, arc-length table, distance↔position queries.
- `craft.py` — the handling model: lateral position on ribbon, thrust/brake, jump
  (leave surface, arc under gravity, land), speed. Reads a **planet profile**
  (gravity, drag, grip) as data.
- `planet.py` — dataclass/JSON of physics params. Ship with ONE (the Moon:
  low-grav, no atmosphere-drag — simplest profile to tune first).
- `main.py` — window, input, game loop, calls craft+spline, draws the grey ribbon
  + capsule (simple projected 3D).

**Done when:** flinging the capsule around a hardcoded curve is *fun*. If it's not
fun here, no later stage rescues it. Iterate handling longest.

### Stage 1 — Route structure: checkpoints, forks, the clock
**Goal:** the capsule now has somewhere to go, a branch to choose, a time to beat.
Route time-attack becomes real. Still grey, still void-floating is fine.

Modules:
- extend `spline.py` for fork topology (node → multiple child splines).
- `track.py` — a track = splines + forks + checkpoints + surface flags; progress
  tracking (which segment, distance along, next checkpoint).
- `timer.py` / race state — checkpoint timing, the clock, pass/fail, simple ghost
  (record player positions vs distance, replay as the "opponent").

**Done when:** you can drive a branching route, pick a fork, beat (or miss) the
checkpoint clock, and race your own ghost.

### Stage 2 — The editor (spline authoring)
**Goal:** author routes visually instead of hardcoding them. This is the
middle-layer externalisation — the route lives on screen, not in your head.

Module:
- `editor.py` — top-down plane: click to place control points (curve threads
  them), drag to adjust, side-view to set height per point, branch a node (fork),
  paint surface flags per segment, place checkpoints. Save/load track data (JSON).

**Scope guard (editors balloon — hold the line):** v1 editor = place / drag /
branch / height / surface-flag / checkpoint / ONE save slot. NO undo-redo,
multi-track management, copy-paste, or grid-snap in v1. Add those only once
*routes are proving fun*. Magic-Launcher the editor.

**Done when:** you can author a fun branching route in the editor and drive it.

### Stage 3 — Terrain (first real art, cheap)
**Goal:** it looks like *somewhere*. Moon heightmap under the ribbon.

Modules:
- `terrain.py` — heightmap generation (noise + crater displacement) + a simple
  surface shader/colouring. Greyscale Moon. This is a *style*, not a placeholder —
  low-poly heightmap + clean shading is a legit look, likely the keeper.
- render integration — draw terrain under the projected ribbon.

**Done when:** one planet (Moon), one good authored route, looks like the Moon,
drives well. **This is the MVP "done" line.** Stop here to evaluate.

### Stage 4+ (POST-MVP — the multiplying content, and the tedious tail)
- **More planets = content, not engineering.** Each new body = new heightmap +
  new planet-profile numbers + new hazard flags, authored through the editor you
  already built. This is the "author once (engine/editor/handling), run cheap
  forever (planets)" payoff. Mercury lava, Venus drag+acid canyons, Earth
  underwater (drag+buoyancy oddball), Mars thin-air twitch, gas-giant cloud-layer
  tracks (no solid surface — most antigrav-native), Pluto.
- **Props/doodads/polish** — decoration. This is the finishing-pattern tail; it's
  *optional flavour*, deliberately deferred so the MVP proves fun without it.
- Position-race mode, more hazard types, sound/music (Suno?), etc.

---

## Module map (flat, for the middle-layer)

What-touches-what, so the wiring isn't held in-head:

```
main.py        → game loop; owns window/input; calls craft + track + render
spline.py      → Catmull-Rom, arc-length; used by craft, track, editor, render
craft.py       → handling; reads planet profile; queries spline for position
planet.py      → physics-profile data (gravity/drag/grip); read by craft
track.py       → splines + forks + checkpoints + flags; reads spline; JSON I/O
timer.py       → race/checkpoint state + ghost; reads track progress
editor.py      → writes track JSON; uses spline for preview; standalone-ish
terrain.py     → heightmap + shading; read by render; keyed to planet
render (in main or render.py) → thin interface; projects 3D→2D; swappable later
```

Couple through **data** (JSON track files, planet dataclasses), not shared
mutable state. `spline.py` is the one genuinely-shared module (math); everything
else prefers its own small helpers over a common utils dumping-ground.

---

## First move (low-wall on-ramp)

Stage 0, and within it: get a window open with a capsule you can move on a
*hardcoded straight-then-curved spline* with basic thrust/steer. Before forks,
before the handling model is tuned — just "capsule moves along a curve in a
window." That's the first hit, and everything else is iteration on a thing that
already runs. Handling-fun is the whole ballgame; prove you can even draw and move
first, then spend the real time on making the fling *feel good*.

## Notes for the Code instance
- Ziggy is strong on big-picture and individual functions, weaker on the *middle
  wiring* between files — use the flat module map above, propose changes as
  small sequential steps, and give an explicit what-touches-what for any new
  wiring rather than assuming it's held in-head.
- Respect the constraints: ~500 lines/file, stdlib+numpy+pygame only, shallow
  duplication over entanglement, data-oriented (tracks/planets are data).
- Keep rendering behind a thin seam so a future GPU/perf swap doesn't touch game
  logic. Logic ≠ rendering.
- Do NOT build ahead of the current stage. Each stage must leave a playable/usable
  artifact before the next begins. The MVP done-line is Stage 3 (one planet, one
  route, looks like the Moon, drives well) — props and extra planets are post-MVP.
