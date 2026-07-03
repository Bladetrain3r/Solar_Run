"""Track editor — Stage 2. Author a loop visually, drive it from the menu.

One save slot (data/tracks/custom.json), per the scope guard: place /
drag / height / flag / checkpoint, and nothing else. No undo, no
multi-track, no copy-paste, no grid-snap. (No branch tool either — forks
are deferred, tracks are one closed loop.)

Modes (number keys or click the toolbar):
    1 PLACE   click near the curve inserts a point there; click empty
              canvas adds one between the last and first points. Hold and
              drag to position it.
    2 DRAG    drag control points around the plane.
    3 HEIGHT  drag a point up/down to change its height (see the profile
              strip along the bottom).
    4 FLAG    click a span (between two points) to cycle its surface:
              normal -> boost -> low_grip.
    5 CKPT    click the curve to drop a checkpoint; right-click one to
              remove it.
Right-click a point in PLACE/DRAG deletes it (minimum 4 stay).
S saves. F refits the view. +/- or mouse wheel zooms, arrows pan.

Run it:  python3 editor.py     — then race it: python3 main.py (pick CUSTOM)
"""

import json
from pathlib import Path

import numpy as np
import pygame

from spline import Spline
from track import TRACK_DIR

SAVE_PATH = TRACK_DIR / "custom.json"
W, H = 1280, 720
TOOLBAR_H, PROFILE_H = 44, 100

BG = (22, 24, 28)
GRID = (38, 41, 48)
CURVE = (196, 202, 212)
POINT = (196, 202, 212)
ACCENT = (255, 176, 58)
DIMTXT = (130, 138, 150)
FLAG_COLORS = {"normal": CURVE, "boost": (255, 150, 60),
               "low_grip": (110, 160, 230)}
MODES = ["PLACE", "DRAG", "HEIGHT", "FLAG", "CKPT"]
FLAG_CYCLE = {"normal": "boost", "boost": "low_grip", "low_grip": "normal"}


def default_data():
    ang = np.linspace(0, 2 * np.pi, 10, endpoint=False)
    return {
        "name": "Custom",
        "planet": "moon",
        "laps": 1,
        "points": [[float(250 * np.cos(a)), float(250 * np.sin(a)), 0.0]
                   for a in ang],
        "checkpoints": [{"frac": 0.5, "bonus": 15.0}],
        "flags": [],
    }


class Editor:
    def __init__(self):
        raw = default_data()
        if SAVE_PATH.exists():
            raw = json.loads(SAVE_PATH.read_text())
        self.meta = {k: raw[k] for k in raw
                     if k not in ("points", "checkpoints", "flags")}
        self.points = [list(map(float, p)) for p in raw["points"]]
        self.ckpts = [dict(c) for c in raw.get("checkpoints", [])]
        self.mode = "PLACE"
        self.sel = 0
        self.dragging = False
        self.unsaved = False
        self.rebuild()
        self.span_flags = self._flags_from_ranges(raw.get("flags", []))
        self.fit_view()

    # --- geometry ----------------------------------------------------------

    def rebuild(self):
        self.spline = Spline(self.points, closed=True)
        self.length = self.spline.length
        n = len(self.points)
        # subsampled polyline per span, for drawing and hit-testing
        self.span_lines = []
        for i in range(n):
            us = np.linspace(i, i + 1, 9)
            self.span_lines.append([self.spline.point_at(u) for u in us])
        ks = [abs(self.spline.curvature_at(d))
              for d in np.linspace(0, self.length, 300)]
        self.min_radius = 1.0 / max(max(ks), 1e-9)

    def point_frac(self, i):
        return self.spline.param_dist(i) / self.length

    def _flags_from_ranges(self, ranges):
        flags = []
        for i in range(len(self.points)):
            mid = (self.point_frac(i)
                   + (self.point_frac(i + 1) if i + 1 < len(self.points)
                      else 1.0)) / 2.0
            flag = "normal"
            for r in ranges:
                a, b = r["from"], r["to"]
                if (a <= mid < b) if a <= b else (mid >= a or mid < b):
                    flag = r["flag"]
            flags.append(flag)
        return flags

    def _ranges_from_flags(self):
        ranges, i, n = [], 0, len(self.points)
        while i < n:
            if self.span_flags[i] == "normal":
                i += 1
                continue
            j = i
            while j + 1 < n and self.span_flags[j + 1] == self.span_flags[i]:
                j += 1
            end = 1.0 if j + 1 >= n else self.point_frac(j + 1)
            ranges.append({"from": round(self.point_frac(i), 4),
                           "to": round(end, 4),
                           "flag": self.span_flags[i]})
            i = j + 1
        return ranges

    def save(self):
        data = dict(self.meta)
        data.setdefault("name", "Custom")
        data.setdefault("planet", "moon")
        data.setdefault("laps", 1)
        data["start_time"] = data.get("start_time") or round(
            self.length / 75.0 + 10.0)
        data["points"] = [[round(v, 1) for v in p] for p in self.points]
        data["checkpoints"] = sorted(
            [{"frac": round(c["frac"], 4), "bonus": c.get("bonus", 15.0)}
             for c in self.ckpts], key=lambda c: c["frac"])
        data["flags"] = self._ranges_from_flags()
        TRACK_DIR.mkdir(parents=True, exist_ok=True)
        tmp = SAVE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1))
        tmp.replace(SAVE_PATH)
        self.unsaved = False

    # --- view --------------------------------------------------------------

    def fit_view(self):
        pts = np.array(self.points)
        lo, hi = pts[:, :2].min(0), pts[:, :2].max(0)
        span = max(hi[0] - lo[0], hi[1] - lo[1], 100.0)
        self.scale = min(W - 160, H - TOOLBAR_H - PROFILE_H - 80) / span
        self.center = (lo + hi) / 2.0

    def w2s(self, p):
        cy = TOOLBAR_H + (H - TOOLBAR_H - PROFILE_H) / 2
        return (int(W / 2 + (p[0] - self.center[0]) * self.scale),
                int(cy - (p[1] - self.center[1]) * self.scale))

    def s2w(self, s):
        cy = TOOLBAR_H + (H - TOOLBAR_H - PROFILE_H) / 2
        return ((s[0] - W / 2) / self.scale + self.center[0],
                (cy - s[1]) / self.scale + self.center[1])

    # --- hit tests -----------------------------------------------------------

    def nearest_point(self, mouse, r=12):
        best, best_d = None, r * r
        for i, p in enumerate(self.points):
            s = self.w2s(p)
            d = (s[0] - mouse[0]) ** 2 + (s[1] - mouse[1]) ** 2
            if d < best_d:
                best, best_d = i, d
        return best

    def nearest_on_curve(self, mouse, r=14):
        best = None
        best_d = r * r
        for i, line in enumerate(self.span_lines):
            for k, p in enumerate(line):
                s = self.w2s(p)
                d = (s[0] - mouse[0]) ** 2 + (s[1] - mouse[1]) ** 2
                if d < best_d:
                    best_d = d
                    best = (i, i + k / (len(line) - 1.0))
        if best is None:
            return None
        span, u = best
        return span, self.spline.param_dist(u) / self.length

    # --- edits ---------------------------------------------------------------

    def touch(self):
        self.rebuild()
        self.unsaved = True

    def place(self, mouse):
        wx, wy = self.s2w(mouse)
        hit = self.nearest_on_curve(mouse, r=18)
        if hit:
            span, _ = hit
            z = (self.points[span][2]
                 + self.points[(span + 1) % len(self.points)][2]) / 2
            self.points.insert(span + 1, [wx, wy, z])
            self.span_flags.insert(span + 1, self.span_flags[span])
            self.sel = span + 1
        else:
            self.points.append([wx, wy, self.points[-1][2]])
            self.span_flags.append("normal")
            self.sel = len(self.points) - 1
        self.touch()

    def delete_point(self, i):
        if len(self.points) <= 4:
            return
        self.points.pop(i)
        self.span_flags.pop(i % len(self.span_flags))
        self.sel = min(self.sel, len(self.points) - 1)
        self.touch()

    # --- event handling --------------------------------------------------------

    def on_mouse_down(self, ev):
        m = ev.pos
        if m[1] < TOOLBAR_H:
            self.click_toolbar(m)
            return
        if ev.button == 4 or ev.button == 5:
            self.scale *= 1.1 if ev.button == 4 else 1 / 1.1
            return
        right = ev.button == 3
        if self.mode in ("PLACE", "DRAG", "HEIGHT"):
            i = self.nearest_point(m)
            if right and i is not None and self.mode != "HEIGHT":
                self.delete_point(i)
            elif i is not None:
                self.sel, self.dragging = i, True
            elif self.mode == "PLACE" and not right:
                self.place(m)
                self.dragging = True
        elif self.mode == "FLAG" and not right:
            hit = self.nearest_on_curve(m, r=20)
            if hit:
                span, _ = hit
                self.span_flags[span] = FLAG_CYCLE[self.span_flags[span]]
                self.unsaved = True
        elif self.mode == "CKPT":
            hit = self.nearest_on_curve(m, r=20)
            if hit is None:
                return
            _, frac = hit
            if right:
                if self.ckpts:
                    near = min(self.ckpts,
                               key=lambda c: abs(c["frac"] - frac))
                    if abs(near["frac"] - frac) < 0.05:
                        self.ckpts.remove(near)
                        self.unsaved = True
            else:
                self.ckpts.append({"frac": frac, "bonus": 15.0})
                self.unsaved = True

    def on_mouse_motion(self, ev):
        if not self.dragging:
            return
        if self.mode == "HEIGHT":
            self.points[self.sel][2] -= ev.rel[1] * 0.25
            self.touch()
        else:
            wx, wy = self.s2w(ev.pos)
            self.points[self.sel][0] = wx
            self.points[self.sel][1] = wy
            self.touch()

    def click_toolbar(self, m):
        for i, name in enumerate(MODES):
            if 14 + i * 110 <= m[0] <= 14 + i * 110 + 100:
                self.mode = name
        if m[0] >= W - 110:
            self.save()

    def on_key(self, key):
        if key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5):
            self.mode = MODES[key - pygame.K_1]
        elif key == pygame.K_s:
            self.save()
        elif key == pygame.K_f:
            self.fit_view()
        elif key in (pygame.K_PLUS, pygame.K_EQUALS):
            self.scale *= 1.15
        elif key == pygame.K_MINUS:
            self.scale /= 1.15
        elif key == pygame.K_DELETE:
            self.delete_point(self.sel)

    def pan(self, keys):
        step = 12 / self.scale
        if keys[pygame.K_LEFT]:
            self.center[0] -= step
        if keys[pygame.K_RIGHT]:
            self.center[0] += step
        if keys[pygame.K_UP]:
            self.center[1] += step
        if keys[pygame.K_DOWN]:
            self.center[1] -= step

    # --- drawing -----------------------------------------------------------------

    def draw(self, screen, fonts):
        screen.fill(BG)
        font, small = fonts
        # world grid, 100 m
        step = 100 * self.scale
        if step > 14:
            ox = (W / 2 - self.center[0] * self.scale) % step
            oy = ((TOOLBAR_H + (H - TOOLBAR_H - PROFILE_H) / 2)
                  + self.center[1] * self.scale) % step
            for x in np.arange(ox, W, step):
                pygame.draw.line(screen, GRID, (int(x), TOOLBAR_H),
                                 (int(x), H - PROFILE_H), 1)
            for y in np.arange(oy, H, step):
                if TOOLBAR_H < y < H - PROFILE_H:
                    pygame.draw.line(screen, GRID, (0, int(y)), (W, int(y)), 1)

        # curve, coloured per span flag
        for i, line in enumerate(self.span_lines):
            pts = [self.w2s(p) for p in line]
            color = FLAG_COLORS[self.span_flags[i]]
            pygame.draw.lines(screen, color, False, pts,
                              4 if self.span_flags[i] != "normal" else 3)

        # lap line marker at point 0
        p0, _f, r0, _u = self.spline.frame_at(0.0)
        a, b = self.w2s(p0 - r0 * 12), self.w2s(p0 + r0 * 12)
        pygame.draw.line(screen, ACCENT, a, b, 3)

        # checkpoints
        for c in self.ckpts:
            pos = self.spline.pos_at(c["frac"] * self.length)
            s = self.w2s(pos)
            pygame.draw.polygon(screen, ACCENT,
                                [(s[0], s[1] - 9), (s[0] + 6, s[1]),
                                 (s[0], s[1] + 9), (s[0] - 6, s[1])], 2)

        # control points
        for i, p in enumerate(self.points):
            s = self.w2s(p)
            if i == self.sel:
                pygame.draw.rect(screen, ACCENT, (s[0] - 8, s[1] - 8, 16, 16), 2)
            pygame.draw.circle(screen, ACCENT if i == self.sel else POINT,
                               s, 5)
        if self.mode == "HEIGHT":
            s = self.w2s(self.points[self.sel])
            z = self.points[self.sel][2]
            screen.blit(small.render(f"z = {z:+.1f}m", True, ACCENT),
                        (s[0] + 12, s[1] - 22))

        self.draw_profile(screen, small)
        self.draw_toolbar(screen, font, small)

    def draw_profile(self, screen, small):
        top = H - PROFILE_H
        pygame.draw.rect(screen, (16, 17, 21), (0, top, W, PROFILE_H))
        zs = np.array([self.spline.pos_at(d)[2] for d in
                       np.linspace(0, self.length, 160)])
        zmax = max(abs(zs).max(), 5.0)
        mid = top + PROFILE_H / 2
        sy = (PROFILE_H / 2 - 12) / zmax
        pygame.draw.line(screen, (60, 65, 74), (0, int(mid)), (W, int(mid)))
        pts = [(int(i / 159 * W), int(mid - z * sy)) for i, z in enumerate(zs)]
        pygame.draw.lines(screen, CURVE, False, pts, 2)
        for i in range(len(self.points)):
            x = int(self.point_frac(i) * W)
            y = int(mid - self.points[i][2] * sy)
            c = ACCENT if i == self.sel else DIMTXT
            pygame.draw.rect(screen, c, (x - 3, y - 3, 6, 6))
        screen.blit(small.render("height profile", True, DIMTXT),
                    (10, top + 6))

    def draw_toolbar(self, screen, font, small):
        pygame.draw.rect(screen, (14, 15, 19), (0, 0, W, TOOLBAR_H))
        for i, name in enumerate(MODES):
            x = 14 + i * 110
            active = self.mode == name
            if active:
                pygame.draw.rect(screen, ACCENT, (x, 8, 100, 28))
            else:
                pygame.draw.rect(screen, DIMTXT, (x, 8, 100, 28), 2)
            t = font.render(f"{i+1} {name}", True,
                            (14, 15, 19) if active else DIMTXT)
            screen.blit(t, (x + 8, 13))
        status = (f"{SAVE_PATH.name}{'*' if self.unsaved else ''} · "
                  f"{self.length:.0f}m · min r {self.min_radius:.0f}m")
        warn = self.min_radius < 25  # tighter than the hairpin = unfair
        t = small.render(status, True, (232, 102, 77) if warn else DIMTXT)
        screen.blit(t, (W - 380, 14))
        pygame.draw.rect(screen, ACCENT, (W - 110, 8, 96, 28), 2)
        screen.blit(font.render("S SAVE", True, ACCENT), (W - 100, 13))


def main():
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Solar Run — track editor (custom.json)")
    fonts = (pygame.font.Font(None, 26), pygame.font.Font(None, 22))
    ed = Editor()
    clock = pygame.time.Clock()
    running = True
    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    running = False
                else:
                    ed.on_key(ev.key)
            elif ev.type == pygame.MOUSEBUTTONDOWN:
                ed.on_mouse_down(ev)
            elif ev.type == pygame.MOUSEBUTTONUP:
                ed.dragging = False
            elif ev.type == pygame.MOUSEMOTION:
                ed.on_mouse_motion(ev)
        ed.pan(pygame.key.get_pressed())
        ed.draw(screen, fonts)
        pygame.display.flip()
        clock.tick(60)
    if ed.unsaved:
        print("note: unsaved changes were discarded (press S to save)")
    pygame.quit()


if __name__ == "__main__":
    main()
