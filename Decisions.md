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

## Next

**Stage 1 — route structure**: fork topology in `spline.py`, `track.py`
(splines + forks + checkpoints + flags + progress), `timer.py` (clock,
checkpoint pass/fail, ghost). Done when: drive a branching route, pick a
fork by steering into it, beat the clock, race your ghost.
