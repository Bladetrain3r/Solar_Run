"""Menus — main screen, play flow, options stub.

MAIN: Play / Options / Exit
PLAY: Solo Track / Tour
SOLO: track library + RANDOM       TOUR: campaigns

W/S or arrows navigate, Enter selects, Esc backs up a level (quits from
MAIN), Z toggles RACE/ZEN anywhere. Options is a stub until the
resolution/audio/keys work lands. The synthmoon cheat can be typed on
any screen.
"""

import numpy as np
import pygame

from track import Track, random_track, list_campaigns, load_campaign

BG = (11, 13, 18)
FG = (203, 210, 220)
DIM = (110, 118, 130)
ACCENT = (255, 176, 58)
SYNTH = (230, 64, 220)

PARENT = {"play": "main", "solo": "play", "tours": "play", "options": "main"}
CAPTION = {"main": "", "play": "PLAY", "solo": "SOLO TRACK",
           "tours": "TOUR", "options": "OPTIONS"}


def _entries(state):
    """Each entry: (kind, value, label)."""
    if state == "main":
        return [("nav", "play", "PLAY"), ("nav", "options", "OPTIONS"),
                ("quit", None, "EXIT")]
    if state == "play":
        return [("nav", "solo", "SOLO TRACK"), ("nav", "tours", "TOUR"),
                ("back", None, "BACK")]
    if state == "solo":
        return ([("track", n, n) for n in Track.list_available()]
                + [("random", None, "RANDOM"), ("back", None, "BACK")])
    if state == "tours":
        return ([("campaign", n, n) for n in list_campaigns()]
                + [("back", None, "BACK")])
    return [("back", None, "BACK")]  # options stub


def pick(screen):
    """Returns (selection, zen, synth) where selection is
    ("track", Track) | ("campaign", campaign dict) — or (None, None,
    False) on quit."""
    w, h = screen.get_size()
    font_title = pygame.font.Font(None, 96)
    font_item = pygame.font.Font(None, 44)
    font_hint = pygame.font.Font(None, 26)
    state, sel = "main", 0
    zen, synth = False, False
    typed = ""
    clock = pygame.time.Clock()

    while True:
        for ev in pygame.event.get():
            # recompute per event: a state change earlier in this same
            # batch must not leave us indexing a stale entries list
            ents = _entries(state)
            sel = min(sel, len(ents) - 1)
            if ev.type == pygame.QUIT:
                return None, None, False
            if ev.type != pygame.KEYDOWN:
                continue
            ch = getattr(ev, "unicode", "").lower()
            if ch.isalpha():
                typed = (typed + ch)[-12:]
                if typed.endswith("synthmoon"):
                    synth = not synth
                    typed = ""
            if ev.key == pygame.K_ESCAPE:
                if state == "main":
                    return None, None, False
                state, sel = PARENT[state], 0
            elif ev.key in (pygame.K_UP, pygame.K_w):
                sel = (sel - 1) % len(ents)
            elif ev.key in (pygame.K_DOWN, pygame.K_s):
                sel = (sel + 1) % len(ents)
            elif ev.key == pygame.K_z:
                zen = not zen
            elif ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                kind, val, _ = ents[sel]
                if kind == "nav":
                    state, sel = val, 0
                elif kind == "back":
                    state, sel = PARENT[state], 0
                elif kind == "quit":
                    return None, None, False
                elif kind == "track":
                    return ("track", Track.load(val)), zen, synth
                elif kind == "random":
                    seed = int(np.random.default_rng().integers(0, 99999))
                    return ("track", random_track(seed)), zen, synth
                elif kind == "campaign":
                    return ("campaign", load_campaign(val)), zen, synth

        ents = _entries(state)
        screen.fill((20, 8, 30) if synth else BG)
        title = font_title.render("SOLAR RUN", True, SYNTH if synth else FG)
        screen.blit(title, (w // 2 - title.get_width() // 2, h // 6))
        mode = font_item.render(f"MODE  {'ZEN' if zen else 'RACE'}"
                                + ("  ·  SYNTHMOON" if synth else ""),
                                True, SYNTH if synth else ACCENT)
        screen.blit(mode, (w // 2 - mode.get_width() // 2, h // 6 + 100))
        if CAPTION[state]:
            cap = font_hint.render("· " + CAPTION[state] + " ·", True, DIM)
            screen.blit(cap, (w // 2 - cap.get_width() // 2, h // 6 + 160))

        y = h // 2 - 20
        for i, (kind, _val, label) in enumerate(ents):
            active = i == sel
            text = ("· " + label.upper() + " ·") if active else label.upper()
            t = font_item.render(text, True, ACCENT if active else DIM)
            screen.blit(t, (w // 2 - t.get_width() // 2, y))
            y += 50

        if state == "options":
            stub = font_hint.render(
                "coming later: resolution · fullscreen · audio · key bindings",
                True, DIM)
            screen.blit(stub, (w // 2 - stub.get_width() // 2, y + 16))

        hint = font_hint.render(
            "W/S select · Enter go · Z mode · Esc back", True, DIM)
        screen.blit(hint, (w // 2 - hint.get_width() // 2, h - 60))
        pygame.display.flip()
        clock.tick(30)
