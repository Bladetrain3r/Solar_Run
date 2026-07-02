# Decisions — Solar Run

Running tracker of what's been decided, what's checkpointed, and what's
still open. Append entries; don't rewrite history — supersede it.
[Design.md](Design.md) is the *why*; this is the *what happened*.

---

## Decided (Stage 0)

- **D-001 · Stack**: Python 3 + pygame + numpy, software-projected 3D.
  Renderer isolated in `render.py` behind a thin seam — a future GPU/perf
  swap replaces that file only. Holding at ~110 fps uncapped @1280×720.
- **D-002 · Ribbon-space craft state**: distance / lateral / altitude, not
  free 3D. Keeps steering 2D-legible and forks-by-lateral-position viable.
- **D-003 · Craft has its own trajectory**: track curvature under you is a
  centrifugal push `curvature × speed² × centrifugal_scale`; steering is
  lateral thrust fighting it. Corner speed is emergent:
  `vmax = sqrt(steer_accel × grip / (curvature × centrifugal_scale))`.
  Applies airborne too (geometry, not grip).
- **D-004 · Unified vertical model**: `vz` always integrates gravity, the
  ribbon catches you when you meet it. Hill crests give airtime for free;
  jumping inherits the hill's upward velocity. No special cases.
- **D-005 · Boost on Shift tap**: direction locked at ignition — lateral
  kick when steering, forward slam when neutral; thruster-powered (full
  strength airborne, ignores grip); cooldown makes it a rhythm resource.
  This is the drift-replacement and the air-control move.
- **D-006 · Planet values are gameplay-scaled**, not astronomical. Relative
  feel between bodies is what matters (Moon gravity = 13, not 1.62).
- **D-007 · Rails bounce** (35% lateral reflection + speed grind), craft
  cannot leave the ribbon sideways. Falling off arrives with forks, not
  before.
- **D-008 · Track hairpin stays**: the r≈26 m final corner is the lap's
  brake-and-boost rhythm feature, not a defect. Proper track authoring is
  Stage 2's (editor) problem — no more hand-tuning `TRACK_POINTS`.
- **D-009 · Headless smoke test** (`main.py --smoke N [shot.png]`) is the
  regression check: scripted input, deterministic dt, screenshot out.

## Checkpoint — 2026-07-02 (merged to main)

**Verdict: fun enough to tune, not refactor.** Relaxing ride with
"needs boost" moments. Feel dials as merged:

| dial | value | note |
|---|---|---|
| thrust_accel / brake | 32 / 48 | top speed ≈ 384 km/h (thrust/base_damp) |
| steer_accel | 100 | hairpin cap ≈ 212 km/h, r=68 bends ≈ 343 |
| centrifugal_scale | 0.75 | 1.0 = full physics, punishing |
| jump_impulse | 4.5 | see O-001 — jump is currently weak vs hills |
| boost lat / fwd | 100 (~10 g) / 260 | lateral was 300 (~30 g), felt like teleport |
| boost_cooldown | 1.0 s | |

## Open

- **O-001 · Jump feel**: hills produce the flying; the jump button barely
  does (0.7 s air, <1 m height at current numbers). Candidates: raise
  impulse back up, hold-to-charge, or lean into "hills are the jumps" and
  make the button a hop for hazard-dodging only. Decide when hazards exist
  (they're what jumping is *for*).
- **O-002 · All tuning provisional** until routes + clock exist — corner
  caps only mean something against a checkpoint timer.

## Decided (Stage 1)

- **D-010 · ~~Track = directed graph of open-spline segments~~**
  SUPERSEDED by D-019.
- **D-011 · ~~Fork choice = lateral position at the split~~**
  SUPERSEDED by D-019 — even with C1-stitched joins and diverging
  branches, the rendered route SNAPS between branches as your lateral
  position crosses the centreline near a fork. Jarring, inherent to
  lat-as-choice rendering, not worth polishing pre-MVP.
- **D-012 · ~~Segment joins use reflected phantom endpoints~~**
  SUPERSEDED by D-017 — reflection kinked the joins (ragged render,
  curvature spike shoved you into the rail = felt like losing accel).
- **D-017 · ~~Joins are graph-stitched~~** (C1 phantom stitching) —
  worked for linear joins, but moot once D-019 removed joins entirely.
  Spline still accepts lead/tail phantoms; the multi-segment graph
  implementation lives in git history (commits a342c1c..8c38468) if
  forks return post-MVP.
- **D-018 · ~~Fork branches must diverge decisively~~** — moot per D-019.
- **D-019 · MVP tracks are ONE closed-loop spline. Forks are deferred.**
  Nothing to join = nothing to kink or snap. Route variety comes from
  (a) a LIBRARY of tracks picked in the stage-select menu before a run,
  (b) RANDOM — a procedural generator (radial star-shaped layout: never
  self-intersects, always smooth) that emits the same track-data shape.
  Race = laps around the loop (lap line = finish gate); checkpoints and
  surface flags are painted as fracs of the loop. Forks may return
  post-MVP as pre-run route selection rather than mid-ribbon switches.
- **D-013 · Outrun clock rules**: start with time, checkpoints add time,
  zero = run over, "finish"-flagged checkpoint ends the run. All numbers
  live in the track JSON (start_time, per-checkpoint bonus).
- **D-014 · Ghost = best finished run**, recorded as (segment, dist, lat,
  alt) per frame, persisted to data/ghosts/ (gitignored — player data).
  Precise live delta readout deferred; the ghost pod itself is the delta.
- **D-015 · Surface flags are physics + tint**: low_grip halves grip
  (icy blue), boost adds accel (amber). Defined once in
  `track.SURFACE_FLAGS`; craft gets them as plain multipliers.
- **D-016 · Zen mode** (`--zen`): no clock, no ghost, no fail state.
  Same track data. Later: procgen = synthesizing segments on the fly
  instead of loading them — the graph model already supports it.

## Open (Stage 1)

- **O-003 · Race countdown/start gate** — currently the clock just runs
  from frame one. Fine until times get competitive.
- **O-004 · Ghost delta readout** (the wireframe's `GHOST +0.82`) —
  trivial now on a single loop (compare dist at same t); do it when it
  earns its keep.
- **O-005 · Track pacing**: start_times + bonuses deliberately generous
  (random tracks estimate theirs from length). Tighten once real lap
  times exist.
- **O-006 · ~~Fork presence~~** — moot per D-019.
- **O-007 · Zen procgen-on-the-go**: random_track proves generated
  layouts work; endless zen = synthesizing the loop ahead while
  retiring it behind. Post-MVP.
- **O-008 · Random-track ghosts**: not persisted (each seed is
  one-off). Could persist per-seed with a seed picker later.

## Next

**Stage 2 — the editor**: place/drag control points top-down, side-view
height, branch a node, paint surface flags, place checkpoints, ONE save
slot. Scope guard per Design.md: NO undo, multi-track, copy-paste, or
grid-snap in v1.
