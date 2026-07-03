"""Solar Run — Stage 1: single-spline routes, the clock, the ghost.

One smooth closed loop per track — no forks, no joins, nothing to kink
(route variety = the stage-select library, or a generated layout).

Race (default): Outrun rules — time on the clock, checkpoints add more,
completing the final lap ends the run. Your best finished run is saved
as a ghost and races alongside you next time.

Zen (Z in the menu, or --zen): no clock, no fail state — just drive.

Controls:
    W / Up        thrust
    S / Down      brake
    A,D / L,R     steer
    Space         jump
    Shift (tap)   boost — lateral kick in your steer direction,
                  forward slam if steering neutral; works airborne
    R             restart run
    Esc           back to menu / quit

CLI:  --track NAME | --random [SEED] | --zen | --smoke N [shot.png]
"""

import sys

import pygame

import menu
from craft import Craft, TUNING
from planet import Planet
from render import Renderer
from terrain import Terrain
from timer import (RaceState, GhostRecorder, load_ghost, save_ghost_if_best,
                   RUNNING, FINISHED)
from track import Track, random_track, SURFACE_FLAGS

WIDTH, HEIGHT = 1280, 720


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


def run(screen, track, zen, smoke_frames=0, shot_path=None):
    """One session on one track. Returns False if the window was closed."""
    clock = pygame.time.Clock()
    planet = Planet.load(track.planet)
    renderer = Renderer(screen, planet, TUNING["ribbon_half_width"])
    terrain = Terrain(track, planet)
    craft = Craft(track.spline, planet)
    is_random = track.file_name.startswith("random-")

    race = None if zen else RaceState(track.start_time)
    ghost = None if (zen or is_random) else load_ghost(track.file_name)
    recorder = None if zen else GhostRecorder()
    ghost_saved = False

    frame = 0
    while True:
        dt = clock.tick(60) / 1000.0
        dt = min(dt, 1 / 20.0)  # clamp hitches so physics never explodes

        boost = False
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return False
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    return True  # back to menu
                elif ev.key == pygame.K_r:
                    craft.reset()
                    if not zen:
                        race = RaceState(track.start_time)
                        recorder = GhostRecorder()
                        ghost_saved = False
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

        ghost_pos = None
        if race is not None:
            race.update(dt)
            for kind, data in events:
                if kind == "checkpoint":
                    race.checkpoint(data.bonus)
                elif kind == "lap":
                    race.lap = data + 1
                    if data >= track.laps:
                        race.finish()
            if race.state == RUNNING:
                recorder.record(race.total, craft.dist, craft.lat, craft.alt)
            elif race.state == FINISHED and not ghost_saved and not is_random:
                if save_ghost_if_best(track.file_name, recorder,
                                      race.total, ghost):
                    print(f"ghost saved: {race.total:.1f}s")
                ghost_saved = True
            if ghost is not None:
                pose = ghost.sample(race.total)
                if pose is not None:
                    g_dist, g_lat, g_alt = pose
                    gp, _f, gr, gu = track.spline.frame_at(g_dist)
                    ghost_pos = gp + gr * g_lat + gu * g_alt

        renderer.draw(track, craft, race, ghost_pos,
                      ghost.total if ghost else None, zen, terrain)
        pygame.display.flip()

        frame += 1
        if smoke_frames and frame >= smoke_frames:
            if shot_path:
                pygame.image.save(screen, shot_path)
            state = race.state if race else "zen"
            print(f"smoke ok: {frame} frames | dist {craft.dist:.1f}m | "
                  f"speed {craft.speed * 3.6:.0f} km/h | "
                  f"track {track.length:.0f}m | {state}")
            return False


def main():
    args = sys.argv[1:]
    zen = "--zen" in args
    args = [a for a in args if a != "--zen"]

    track = None
    smoke_frames, shot_path = 0, None
    if "--track" in args:
        track = Track.load(args[args.index("--track") + 1])
    if "--random" in args:
        i = args.index("--random")
        seed = int(args[i + 1]) if len(args) > i + 1 and args[i + 1].isdigit() \
            else None
        track = random_track(seed)
    if "--smoke" in args:
        i = args.index("--smoke")
        smoke_frames = int(args[i + 1]) if len(args) > i + 1 else 300
        if len(args) > i + 2 and not args[i + 2].startswith("--"):
            shot_path = args[i + 2]
        if track is None:
            track = Track.load("moon_a1")
        import os
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Solar Run (Moon)")

    if track is not None:  # CLI-selected: single session, no menu loop
        run(screen, track, zen, smoke_frames, shot_path)
    else:
        while True:
            track, zen = menu.pick(screen)
            if track is None or not run(screen, track, zen):
                break

    pygame.quit()


if __name__ == "__main__":
    main()
