"""Solar Run — single-spline routes, the clock, the ghost, traffic, tours.

One smooth closed loop per track. Route variety = the stage-select
library, a generated layout, or a CAMPAIGN: tracks driven in sequence,
where the final gate of each leg is a portal into the next — the track
reloads in realtime and your momentum carries straight through.

Race (default): Outrun rules — time on the clock, checkpoints add more,
completing the final lap (of the final leg) ends the run. On single
tracks your best finished run is saved as a ghost; campaigns save the
best total instead.

Zen (Z in the menu, or --zen): no clock, no fail state. On a campaign,
the tour loops forever.

Controls:
    W / Up        thrust
    S / Down      brake
    A,D / L,R     steer
    Space         jump
    Shift (tap)   boost — lateral kick in your steer direction,
                  forward slam if steering neutral; works airborne
    R             restart run
    Esc           back to menu / quit

CLI:  --track NAME | --random [SEED] | --campaign NAME | --zen
      --smoke N [shot.png]
      --synth (or type "synthmoon" in the menu — you didn't hear it here)
"""

import sys

import pygame

import menu
from craft import Craft, TUNING
from objects import spawn_traffic, update_traffic, collide_player, TRAFFIC
from planet import Planet
from render import Renderer
from terrain import Terrain
from timer import (RaceState, GhostRecorder, load_ghost, save_ghost_if_best,
                   load_best_total, save_best_total_if_best,
                   RUNNING, FINISHED)
from track import Track, random_track, load_campaign, SURFACE_FLAGS

WIDTH, HEIGHT = 1280, 720
BANNER_TIME = 2.2


def read_input(keys):
    throttle = 1.0 if keys[pygame.K_w] or keys[pygame.K_UP] else 0.0
    brake = 1.0 if keys[pygame.K_s] or keys[pygame.K_DOWN] else 0.0
    steer = 0.0
    if keys[pygame.K_a] or keys[pygame.K_LEFT]:
        steer -= 1.0
    if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
        steer += 1.0
    jump = bool(keys[pygame.K_SPACE])
    return throttle, brake, steer, jump


def run(screen, playlist, zen, smoke_frames=0, shot_path=None, synth=False,
        campaign=None):
    """One session over a playlist of tracks (length 1 = a normal run).
    Returns "menu", "restart", or "quit"."""
    clock = pygame.time.Clock()

    def load_leg(i):
        t = playlist[i]
        name = "synthmoon" if synth and t.planet == "moon" else t.planet
        p = Planet.load(name)
        return t, p, Terrain(t, p)

    leg = 0
    track, planet, terrain = load_leg(0)
    renderer = Renderer(screen, planet, TUNING["ribbon_half_width"])
    craft = Craft(track.spline, planet)
    is_random = track.file_name.startswith("random-")

    pace = TRAFFIC["pace_frac"] * TUNING["thrust_accel"] / TUNING["base_damp"]
    entities = spawn_traffic(track, track.traffic, pace)
    respawn_dist = 0.0
    respawns = 0
    banner_text, banner_t = None, 0.0

    race = None if zen else RaceState(track.start_time)
    solo = campaign is None
    ghost = load_ghost(track.file_name) if (solo and not zen and not is_random) \
        else None
    recorder = GhostRecorder() if (solo and not zen) else None
    best_total = (ghost.total if ghost else None) if solo \
        else load_best_total(campaign["file_name"])
    result_saved = False

    frame = 0
    while True:
        dt = clock.tick(60) / 1000.0
        dt = min(dt, 1 / 20.0)  # clamp hitches so physics never explodes

        boost = False
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return "quit"
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    return "menu"
                elif ev.key == pygame.K_r:
                    return "restart"
                elif ev.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
                    boost = True

        if smoke_frames:
            dt = 1 / 60.0  # deterministic physics for the scripted run
            throttle, brake = 1.0, 0.0
            steer = -0.6 if frame % 240 > 170 else 0.2
            jump = frame % 200 == 150
            boost = frame % 130 == 60
        else:
            throttle, brake, steer, jump = read_input(pygame.key.get_pressed())

        if race is not None and race.state != RUNNING:
            throttle, jump, boost = 0.0, False, False  # coast out the run

        flag = track.flag_at(craft.dist)
        craft.surface_grip, craft.surface_accel, _ = SURFACE_FLAGS[flag]

        old_dist = craft.dist
        craft.update(dt, throttle, brake, steer, jump, boost)
        events = track.advance(old_dist, craft.dist)

        update_traffic(entities, track, pace, dt)
        if craft.invuln <= 0.0:
            hit = collide_player(entities, craft, track.length)
            if hit == "hard":
                craft.reset(respawn_dist)
                craft.invuln = 2.0
                respawns += 1

        # gates: respawn point, race bonuses, portals, the finish
        for kind, data in events:
            if kind == "checkpoint":
                delta = (craft.dist % track.length - data.dist) % track.length
                respawn_dist = craft.dist - delta
                if race is not None:
                    race.checkpoint(data.bonus)
                continue
            # lap line
            respawn_dist = data * track.length
            final_lap = data >= track.laps
            last_leg = leg == len(playlist) - 1
            if final_lap and len(playlist) > 1 and not (race and last_leg):
                # PORTAL: hop to the next leg, momentum intact
                leftover = max(0.0, craft.dist - data * track.length)
                leg = (leg + 1) % len(playlist)   # zen tours loop forever
                track, planet, terrain = load_leg(leg)
                renderer.planet = planet
                craft.spline = track.spline
                craft.planet = planet
                craft.dist = leftover
                craft.world_z = (float(track.spline.pos_at(leftover)[2])
                                 + craft.alt)
                entities = spawn_traffic(track, track.traffic, pace)
                respawn_dist = 0.0
                banner_text = track.name.upper()
                if race is not None:
                    race.remaining += track.start_time * campaign["bonus_scale"]
                    race.lap = 1
                    banner_text += f"  ·  STAGE {leg + 1}/{len(playlist)}"
                banner_t = BANNER_TIME
                break  # events from the old track no longer apply
            if race is not None:
                if final_lap:
                    race.finish()
                else:
                    race.lap = data + 1

        ghost_pos = None
        if race is not None:
            race.update(dt)
            if race.state == RUNNING and recorder is not None:
                recorder.record(race.total, craft.dist, craft.lat, craft.alt)
            elif race.state == FINISHED and not result_saved:
                if campaign is not None:
                    if save_best_total_if_best(campaign["file_name"],
                                               race.total, best_total):
                        print(f"tour best: {race.total:.1f}s")
                elif not is_random:
                    if save_ghost_if_best(track.file_name, recorder,
                                          race.total, ghost):
                        print(f"ghost saved: {race.total:.1f}s")
                result_saved = True
            if ghost is not None:
                pose = ghost.sample(race.total)
                if pose is not None:
                    g_dist, g_lat, g_alt = pose
                    gp, _f, gr, gu = track.spline.frame_at(g_dist)
                    ghost_pos = gp + gr * g_lat + gu * g_alt

        banner_t = max(0.0, banner_t - dt)
        renderer.draw(track, craft, race, ghost_pos, best_total, zen, terrain,
                      entities,
                      stage=(leg + 1, len(playlist)) if len(playlist) > 1
                      else None,
                      banner=(banner_text, banner_t / BANNER_TIME)
                      if banner_t > 0 else None)
        pygame.display.flip()

        frame += 1
        if smoke_frames and frame >= smoke_frames:
            if shot_path:
                pygame.image.save(screen, shot_path)
            state = race.state if race else "zen"
            alive = sum(e.alive for e in entities)
            print(f"smoke ok: {frame} frames | leg {leg + 1}/{len(playlist)} "
                  f"| dist {craft.dist:.1f}m | "
                  f"speed {craft.speed * 3.6:.0f} km/h | "
                  f"traffic {alive}/{len(entities)} | respawns {respawns} | "
                  f"{state}")
            return "quit"


def play(screen, playlist, zen, synth, campaign, smoke_frames=0,
         shot_path=None):
    """run() until something other than a restart comes back."""
    while True:
        r = run(screen, playlist, zen, smoke_frames, shot_path, synth,
                campaign)
        if r != "restart":
            return r


def main():
    args = sys.argv[1:]
    zen = "--zen" in args
    synth = "--synth" in args
    args = [a for a in args if a not in ("--zen", "--synth")]

    playlist, campaign = None, None
    smoke_frames, shot_path = 0, None
    if "--track" in args:
        playlist = [Track.load(args[args.index("--track") + 1])]
    if "--random" in args:
        i = args.index("--random")
        seed = int(args[i + 1]) if len(args) > i + 1 and args[i + 1].isdigit() \
            else None
        playlist = [random_track(seed)]
    if "--campaign" in args:
        campaign = load_campaign(args[args.index("--campaign") + 1])
        playlist = campaign["tracks"]
    if "--smoke" in args:
        i = args.index("--smoke")
        smoke_frames = int(args[i + 1]) if len(args) > i + 1 else 300
        if len(args) > i + 2 and not args[i + 2].startswith("--"):
            shot_path = args[i + 2]
        if playlist is None:
            playlist = [Track.load("moon_a1")]
        import os
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Solar Run (Moon)")

    if playlist is not None:  # CLI-selected: single session, no menu loop
        play(screen, playlist, zen, synth, campaign, smoke_frames, shot_path)
    else:
        while True:
            sel, zen, synth = menu.pick(screen)
            if sel is None:
                break
            kind, payload = sel
            if kind == "campaign":
                playlist, campaign = payload["tracks"], payload
            else:
                playlist, campaign = [payload], None
            if play(screen, playlist, zen, synth, campaign) == "quit":
                break

    pygame.quit()


if __name__ == "__main__":
    main()
