"""Solar Run — Stage 0: handling on a hardcoded spline.

A grey capsule on a grey ribbon over the Moon. No editor, no forks, no
terrain yet — this stage exists to make the fling feel GOOD. Iterate
craft.TUNING (and the planet JSON) longest.

Controls:
    W / Up        thrust
    S / Down      brake
    A,D / L,R     steer
    Space         jump
    R             reset to start
    Esc           quit

Smoke test (headless):  python3 main.py --smoke 300 [screenshot.png]
"""

import sys

import pygame

from craft import Craft, TUNING
from planet import Planet
from render import Renderer
from spline import Spline

# The hardcoded Stage-0 circuit: a ~1.5 km closed loop with a climbing
# sweeper, a crest you can launch off, and a dip. (x, y, height) in metres.
TRACK_POINTS = [
    (0, 0, 0),
    (140, -20, 0),
    (280, 0, 4),
    (380, 80, 10),
    (400, 200, 16),     # crest — carry speed here for airtime
    (340, 310, 6),
    (200, 360, 0),
    (60, 340, -6),      # the dip
    (-60, 260, -2),
    (-140, 140, 6),
    (-160, 20, 2),
    (-90, -40, 0),
]

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


def main():
    smoke_frames = 0
    shot_path = None
    if len(sys.argv) > 1 and sys.argv[1] == "--smoke":
        smoke_frames = int(sys.argv[2]) if len(sys.argv) > 2 else 300
        shot_path = sys.argv[3] if len(sys.argv) > 3 else None
        import os
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Solar Run — Stage 0 (Moon)")
    clock = pygame.time.Clock()

    planet = Planet.load("moon")
    spline = Spline(TRACK_POINTS, closed=True)
    craft = Craft(spline, planet)
    renderer = Renderer(screen, planet, TUNING["ribbon_half_width"])

    frame = 0
    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        dt = min(dt, 1 / 20.0)  # clamp hitches so physics never explodes

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    running = False
                elif ev.key == pygame.K_r:
                    craft.reset()

        if smoke_frames:
            dt = 1 / 60.0  # deterministic physics for the scripted run
            throttle, brake = 1.0, 0.0
            steer = -0.6 if frame % 240 > 170 else 0.2
            jump = frame % 200 == 150
        else:
            throttle, brake, steer, jump = read_input(pygame.key.get_pressed())

        craft.update(dt, throttle, brake, steer, jump)
        renderer.draw(spline, craft)
        pygame.display.flip()

        frame += 1
        if smoke_frames and frame >= smoke_frames:
            if shot_path:
                pygame.image.save(screen, shot_path)
            print(f"smoke ok: {frame} frames | dist {craft.dist:.1f}m | "
                  f"speed {craft.speed * 3.6:.0f} km/h | lat {craft.lat:+.1f}m | "
                  f"track {spline.length:.0f}m")
            running = False

    pygame.quit()


if __name__ == "__main__":
    main()
