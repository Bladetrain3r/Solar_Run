"""Stage select — pick a track from the library (or RANDOM), pick a mode.

Deliberately tiny: arrows to choose, Z to toggle RACE/ZEN, Enter to run,
Esc to quit. Route variety lives HERE now (forks are deferred): you choose
your layout before the run, not mid-ribbon.
"""

import numpy as np
import pygame

from track import Track, random_track, list_campaigns, load_campaign

BG = (11, 13, 18)
FG = (203, 210, 220)
DIM = (110, 118, 130)
ACCENT = (255, 176, 58)


SYNTH = (230, 64, 220)


def pick(screen):
    """Returns (selection, zen, synth) where selection is
    ("track", Track) | ("campaign", campaign dict) — or (None, None,
    False) on quit. synth flips when someone types the cheat code."""
    w, h = screen.get_size()
    font_title = pygame.font.Font(None, 96)
    font_item = pygame.font.Font(None, 44)
    font_hint = pygame.font.Font(None, 26)
    names = Track.list_available()
    tours = list_campaigns()
    entries = ([("track", n) for n in names]
               + [("campaign", n) for n in tours]
               + [("random", None)])
    sel, zen, synth = 0, False, False
    typed = ""
    clock = pygame.time.Clock()

    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return None, None, False
            if ev.type == pygame.KEYDOWN:
                ch = getattr(ev, "unicode", "").lower()
                if ch.isalpha():
                    typed = (typed + ch)[-12:]
                    if typed.endswith("synthmoon"):
                        synth = not synth
                        typed = ""
                if ev.key == pygame.K_ESCAPE:
                    return None, None, False
                elif ev.key in (pygame.K_UP, pygame.K_w):
                    sel = (sel - 1) % len(entries)
                elif ev.key in (pygame.K_DOWN, pygame.K_s):
                    sel = (sel + 1) % len(entries)
                elif ev.key == pygame.K_z:
                    zen = not zen
                elif ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                    kind, name = entries[sel]
                    if kind == "random":
                        seed = int(np.random.default_rng().integers(0, 99999))
                        return ("track", random_track(seed)), zen, synth
                    if kind == "campaign":
                        return ("campaign", load_campaign(name)), zen, synth
                    return ("track", Track.load(name)), zen, synth

        screen.fill((20, 8, 30) if synth else BG)
        title = font_title.render("SOLAR RUN", True, SYNTH if synth else FG)
        screen.blit(title, (w // 2 - title.get_width() // 2, h // 5))
        mode = font_item.render(f"MODE  {'ZEN' if zen else 'RACE'}"
                                + ("  ·  SYNTHMOON" if synth else ""),
                                True, SYNTH if synth else ACCENT)
        screen.blit(mode, (w // 2 - mode.get_width() // 2, h // 5 + 110))

        y = h // 2
        for i, (kind, name) in enumerate(entries):
            active = i == sel
            label = {"random": "RANDOM",
                     "campaign": f"TOUR · {name}"}.get(kind, name)
            if active:
                label = "· " + label + " ·"
            t = font_item.render(label.upper(), True, ACCENT if active else DIM)
            screen.blit(t, (w // 2 - t.get_width() // 2, y))
            y += 54

        hint = font_hint.render(
            "W/S select · Z mode · Enter run · Esc quit", True, DIM)
        screen.blit(hint, (w // 2 - hint.get_width() // 2, h - 70))
        pygame.display.flip()
        clock.tick(30)
