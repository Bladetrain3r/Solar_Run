# Post-MVP Changelist
## More like a wishlist really

Now that the stage 3 MVP is done (see: Design.md), this file serves as a source of truth for post-MVP changes

## Build order (agreed; each stage leaves a playable artifact)

| Stage | Contents | Notes |
|---|---|---|
| 4 · Traffic ✅ | `objects.py` entities layer, slow movers (lane-stick, ~60% pace, `traffic` in track JSON), soft/hard collision, respawn-at-last-checkpoint | Respawn + entities are the shared foundations; jump got a job |
| 5 · Portals & campaigns ✅ | Final gate of a leg = portal into the next track (realtime reload, momentum carried); campaign = JSON list of tracks; menu TOUR entries; zen tours loop forever | Moved up ahead of planets so track-to-track flow lands first |
| 6 · Placeables | Low walls + ditches, editor `6 OBJ` mode (defined list), random maps sprinkle 1–2 per checkpoint | Thin layer over stage 4's collision/respawn |
| 7 · Planet framework | Terrain params → planet JSON; Mercury (lava lakes), Venus (fog), Mars (mountains), Pluto (trenches) + library tracks + campaigns across them | Pure content multiplication |
| 8 · Audio | OGG music dir + SFX + speed-banded engine hum (numpy resample; no live pitch in pygame — doppler parked) | Independent; can float earlier on request |
| 9 · Weather | Per-planet event table, roll on checkpoint crossing (~10%), 3–10 s, HUD warning strip; cheap effects first (flare/fog), hazards reuse stages 4/6 | "Per segment" defined as per checkpoint crossing |
| 10 · Exotic terrains | Jupiter cloud-tunnel render mode, Neptune ring asteroid-scatter mode, cryovolcanoes → Titania, Oberon, ring courses | The renderer-heavy tail, deliberately last |

Planned split when render.py nears the 500-line ceiling (~stage 8): render.py
keeps camera/projection/HUD, world drawing moves to render_world.py.

## Wishlist (Planets)
- Mercury
- Venus
- Mars
- Jupiter
- Mooning Uranus (Titania + Oberon)
- Rings of Neptune
- Pluto

## Completed (Planets)
- Luna/Moon
- Synthmoon

## Completed (Features)
- Slow Movers (wheeled and floater), moving about 60% of max player speed — stage 4
  - Lane-stick, spawned on load per `traffic` density key in track JSON, deterministic per track
- Mover collision — stage 4
  - Soft: momentum trade + lateral shove; Hard (closing > ~100 km/h): NPC knocked out, player respawns at last gate crossed
  - Jump clears wheelers; a high-bobbing floater can be slipped under
- Portal transitions + campaigns — stage 5 (P-001)
  - data/campaigns/*.json = a named list of tracks; final gate of each leg reloads the next track in realtime with momentum carried (speed/lat/alt/vz + stripe phase)
  - Arrival grants the leg's start_time × bonus_scale; STAGE x/y HUD; flash + banner
  - Campaigns save best TOTAL (ghosts sit out campaigns v1); zen tours loop forever

## Wishlist (Features)
- Audio Handling (OGG loading for music and FX)
  - May need some filtering and doppler for engine state sound changes
- Resolution scaling / fullscreen (post-everything-else; 720p windowed fine for dev)
  - Game renderer + menu already derive from screen size, so likely just
    a `--res WxH` flag + F11 fullscreen toggle; editor is the only
    hardcoded-720p holdout
- Static objects placeable in the editor
  - Defined list
  - Added class of placeable in the editor
  - Low walls and ditches to start
  - Random maps spawn one or two per checkpoint on track load
- Screensaver mode: Load a track in zen mode, spawn a player object that acts like a slow mover, no HUD or active control.
- Menu Options. Break it up into screens.
  - Play -> Single Track or Tour -> Select (Random = Single Track).
  - Options (Stub - resolution and fullscreen options)
  - Exit

## Planet Base Visuals
- Base planets each have different heightmap tuning
- Mercury gets simple lava lakes
- Venus gets fog
- Mars gets erm... big mountains?
- Jupiter you're racing through low poly clouds (i.e. more of a low-poly plasma noise than a height map, the road is a tunnel through)
- Uranus moons get cryo-volcanos
- Neptune rings are basically flying through a low-poly asteroid field
- Pluto gets ice canyons, players are racing through deep trenches.

## Weather/Transient Track Events
- Some visual, some gameplay altering
- Last between 3-10 seconds
- ~10% chance per track segment
- Mercury: Solar Flare, disable boost
- Venus: Acid storm, very low visibility
- Luna/Moon: N/A
- Mars: Sandstorms, similar to acid storms
- Jupiter: Telegraphed lightning strikes from cloud interactions. Dodge or respawn.
- Uranus moons: Ice waves - spawn temporary wall obstacles that move retrograde to the track.
- Uranus Rings: Asteroid impacts, similar to Jupiter lightning
- Pluto: N/A
