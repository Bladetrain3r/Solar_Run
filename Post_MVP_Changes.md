# Post-MVP Changelist
## More like a wishlist really

Now that the stage 3 MVP is done (see: Design.md), this file serves as a source of truth for post-MVP changes

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

## Wishlist (Features)
- Audio Handling (OGG loading for music and FX)
  - May need some filtering and doppler for engine state sound changes
- Slow Movers (wheeled and floater), moving about 60% of max player speed
  - These just stick to their lane
  - Spawned on track load, distributed according to a density parameter in the track JSON (i.e. a value of 10 creates 10 slow movers equally distributed)
- For movers: Collision
  - Slow (relative) collisions just slow down both parties and transfer some momentum
  - Hard collisions (high decel force) force the player to respawn, knock out the NPC
- Static objects placeable in the editor
  - Defined list
  - Added class of placeable in the editor
  - Low walls and ditches to start
  - Random maps spawn one or two per checkpoint on track load

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
