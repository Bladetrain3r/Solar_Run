"""Solar Run — Stage 1: routes, forks, the clock, the ghost.

Race mode (default): Outrun rules — start with time on the clock,
checkpoints add more, the finish gate ends the run. Steer into a fork's
side to choose it. Your best finished run is saved as a ghost and races
alongside you next time.

Zen mode (--zen): no clock, no ghost, no fail state — the track graph is
cyclic, so just drive. Forever.

Controls:
    W / Up        thrust
    S / Down      brake
    A,D / L,R     steer (also picks the branch at a fork)
    Space         jump
    Shift (tap)   boost — lateral kick in your steer direction,
                  forward slam if steering neutral; works airborne
    R             restart run / reset
    Esc           quit

Smoke test (headless):  python3 main.py --smoke 300 [screenshot.png] [--zen]
"""

import sys

import pygame

from craft import Craft, TUNING
from planet import Planet
from render import Renderer
from timer import (RaceState, GhostRecorder, load_ghost, save_ghost_if_best,
                   RUNNING)
from track import Track, SURFACE_FLAGS

WIDTH, HEIGHT = 1280, 720
TRACK_NAME = "moon_a1"


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


def main():
    args = sys.argv[1:]
    zen = "--zen" in args
    args = [a for a in args if a != "--zen"]
    smoke_frames = 0
    shot_path = None
    if args and args[0] == "--smoke":
        smoke_frames = int(args[1]) if len(args) > 1 else 300
        shot_path = args[2] if len(args) > 2 else None
        import os
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Solar Run — Stage 1 (Moon)")
    clock = pygame.time.Clock()

    track = Track.load(TRACK_NAME)
    planet = Planet.load(track.planet)
    renderer = Renderer(screen, planet, TUNING["ribbon_half_width"])

    seg_id = track.start_segment
    prev_seg = None
    craft = Craft(track.segments[seg_id].spline, planet)
    race = None if zen else RaceState(track.start_time)
    ghost = None if zen else load_ghost(TRACK_NAME)
    recorder = None if zen else GhostRecorder()
    ghost_saved = False

    def restart():
        nonlocal seg_id, prev_seg, race, recorder, ghost, ghost_saved
        seg_id, prev_seg = track.start_segment, None
        craft.spline = track.segments[seg_id].spline
        craft.reset()
        if not zen:
            race = RaceState(track.start_time)
            recorder = GhostRecorder()
            ghost = load_ghost(TRACK_NAME)
            ghost_saved = False

    frame = 0
    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        dt = min(dt, 1 / 20.0)  # clamp hitches so physics never explodes

        boost = False
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    running = False
                elif ev.key == pygame.K_r:
                    restart()
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

        # surface flag of the segment under the craft
        grip_mult, accel_add, _tint = SURFACE_FLAGS[track.segments[seg_id].flag]
        craft.surface_grip, craft.surface_accel = grip_mult, accel_add

        old_dist = craft.dist
        craft.update(dt, throttle, brake, steer, jump, boost)
        new_seg, events = track.advance(seg_id, old_dist, craft)
        if new_seg != seg_id:
            prev_seg, seg_id = seg_id, new_seg

        ghost_pos = None
        if race is not None:
            race.update(dt)
            for kind, data in events:
                if kind == "checkpoint":
                    race.checkpoint(data)
            if race.state == RUNNING:
                recorder.record(race.total, seg_id, craft.dist,
                                craft.lat, craft.alt)
            elif race.state == "finished" and not ghost_saved:
                best = ghost.total if ghost else None
                if save_ghost_if_best(TRACK_NAME, recorder, race.total, ghost):
                    print(f"ghost saved: {race.total:.1f}s"
                          + (f" (was {best:.1f}s)" if best else ""))
                ghost_saved = True
            if ghost is not None:
                pose = ghost.sample(race.total)
                if pose is not None:
                    g_seg, g_dist, g_lat, g_alt = pose
                    gp, _f, gr, gu = track.segments[g_seg].spline.frame_at(g_dist)
                    ghost_pos = gp + gr * g_lat + gu * g_alt

        renderer.draw(track, seg_id, prev_seg, craft, race, ghost_pos,
                      ghost.total if ghost else None, zen)
        pygame.display.flip()

        frame += 1
        if smoke_frames and frame >= smoke_frames:
            if shot_path:
                pygame.image.save(screen, shot_path)
            state = race.state if race else "zen"
            print(f"smoke ok: {frame} frames | seg {seg_id} | "
                  f"dist {craft.dist:.1f}m | odo {craft.odometer:.0f}m | "
                  f"speed {craft.speed * 3.6:.0f} km/h | {state}")
            running = False

    pygame.quit()


if __name__ == "__main__":
    main()
