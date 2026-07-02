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

- **D-010 · Track = directed graph of open-spline segments**, may be
  CYCLIC (branches rejoin; last segment points back at the first). Race
  mode runs start → finish gate; zen mode exploits the cycle to run
  forever. One data model, two modes.
- **D-011 · Fork choice = lateral position at the split.** Left half of
  the ribbon (lat < 0) takes `next[0]`. Authoring convention: list the
  LEFT branch first. Forks and steering are the same mechanic — no
  special input.
- **D-012 · Segment joins use reflected phantom endpoints** (local,
  per-segment) rather than cross-segment tangent stitching. Curvature
  flattens slightly at joints; the editor's job is to author smooth
  joins. Craft lat is re-projected into the new segment's frame at the
  hop, so world position stays continuous.
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
  needs "ghost progress at my progress" mapping across the graph; do it
  when it earns its keep.
- **O-005 · moon_a1 pacing**: start_time 40 + bonuses is deliberately
  generous. Tighten in JSON once real lap times exist.

## Next

**Stage 2 — the editor**: place/drag control points top-down, side-view
height, branch a node, paint surface flags, place checkpoints, ONE save
slot. Scope guard per Design.md: NO undo, multi-track, copy-paste, or
grid-snap in v1.
