"""Software 3D renderer — the thin, swappable seam.

Projects the spline ribbon + craft to the screen with a chase camera and
plain perspective math. This is the throwback LOOK, not a placeholder.
Nothing in here touches game logic; a future GPU renderer replaces this
file and nothing else.

Owns: camera, projection, sky/stars, ribbon strip, craft sprite, HUD.
"""

import math

import numpy as np
import pygame

from spline import WORLD_UP

# Camera + projection dials
CAM_BACK = 16.0        # m behind the craft along the spline
CAM_HEIGHT = 7.0       # m above the ribbon
CAM_AHEAD = 40.0       # m ahead of the craft to aim at
FOCAL_HFOV = 80.0      # degrees, horizontal field of view
NEAR_CLIP = 2.0        # m
DRAW_AHEAD = 420.0     # m of ribbon drawn ahead of the craft
FOG_DIST = 420.0       # m, full-fade distance into the sky colour

ROAD_LIGHT = (58, 62, 70)
ROAD_DARK = (46, 50, 57)
RAIL_COLOR = (232, 102, 77)
DASH_COLOR = (255, 176, 58)
HULL_COLOR = (214, 220, 228)
HULL_SHADE = (122, 130, 142)
CANOPY_COLOR = (27, 44, 58)
TEXT_DIM = (150, 158, 170)


def _lerp3(a, b, t):
    return (int(a[0] + (b[0] - a[0]) * t),
            int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t))


class Renderer:
    def __init__(self, screen, planet, ribbon_half_width):
        self.screen = screen
        self.planet = planet
        self.half_width = ribbon_half_width
        self.w, self.h = screen.get_size()
        self.cx, self.cy = self.w // 2, self.h // 2
        self.focal = (self.w / 2) / math.tan(math.radians(FOCAL_HFOV / 2))
        self.cam_lat = 0.0  # smoothed lateral camera follow

        rng = np.random.default_rng(7)
        self.stars = [(float(x), float(y), float(b)) for x, y, b in zip(
            rng.uniform(0, self.w * 2, 90),
            rng.uniform(0, self.h * 0.55, 90),
            rng.uniform(80, 220, 90))]

        self.font_big = pygame.font.Font(None, 110)
        self.font_med = pygame.font.Font(None, 34)
        self.font_small = pygame.font.Font(None, 24)

        # one-time scanline overlay for the retro look
        self.scanlines = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        for y in range(0, self.h, 3):
            pygame.draw.line(self.scanlines, (0, 0, 0, 28), (0, y), (self.w, y))

    # --- camera ------------------------------------------------------------

    def _camera(self, spline, craft):
        pos, _fwd, right, _up = spline.frame_at(craft.dist - CAM_BACK)
        self.cam_lat += (craft.lat * 0.45 - self.cam_lat) * 0.12
        cam_pos = pos + right * self.cam_lat + WORLD_UP * CAM_HEIGHT
        target = spline.pos_at(craft.dist + CAM_AHEAD) + WORLD_UP * 2.0
        f = target - cam_pos
        f = f / np.linalg.norm(f)
        r = np.cross(f, WORLD_UP)
        r = r / np.linalg.norm(r)
        u = np.cross(r, f)
        return cam_pos, r, u, f

    def _project(self, p, cam):
        cam_pos, r, u, f = cam
        d = p - cam_pos
        z = float(np.dot(d, f))
        if z < NEAR_CLIP:
            return None
        sx = self.cx + float(np.dot(d, r)) * self.focal / z
        sy = self.cy - float(np.dot(d, u)) * self.focal / z
        return sx, sy, z

    # --- scene -------------------------------------------------------------

    def draw(self, spline, craft):
        cam = self._camera(spline, craft)
        self._draw_sky(cam)
        self._draw_ribbon(spline, craft, cam)
        self._draw_craft(spline, craft, cam)
        self.screen.blit(self.scanlines, (0, 0))
        self._draw_hud(craft)

    def _draw_sky(self, cam):
        _cam_pos, _r, _u, f = cam
        # horizon = projection of the camera's forward direction flattened
        flat = np.array([f[0], f[1], 0.0])
        n = np.linalg.norm(flat)
        if n > 1e-6:
            flat /= n
            horizon = self.cy - float(np.dot(flat, _u)) * self.focal
        else:
            horizon = self.cy
        horizon = int(min(max(horizon, 0), self.h))
        self.screen.fill(self.planet.sky_color, (0, 0, self.w, horizon))
        self.screen.fill(self.planet.ground_color,
                         (0, horizon, self.w, self.h - horizon))
        pygame.draw.line(self.screen, (70, 75, 84),
                         (0, horizon), (self.w, horizon), 2)

        yaw = math.atan2(f[1], f[0])
        shift = yaw / (2 * math.pi) * self.w * 2
        for x, y, b in self.stars:
            sx = (x - shift) % (self.w * 2)
            if sx < self.w and y < horizon:
                self.screen.fill((int(b), int(b), int(b + 20)),
                                 (int(sx), int(y), 2, 2))
        # Earth on the horizon, drifting with heading
        ex = int((self.w * 1.4 - shift) % (self.w * 2))
        ey = horizon - 70
        if 0 <= ex < self.w and ey > 20:
            pygame.draw.circle(self.screen, (29, 51, 72), (ex, ey), 26)
            pygame.draw.circle(self.screen, (127, 168, 201), (ex - 7, ey - 7), 17)

    def _draw_ribbon(self, spline, craft, cam):
        hw = self.half_width
        # sample distances: fine near, coarse far
        ds, d = [], craft.dist - 12.0
        while d < craft.dist + DRAW_AHEAD:
            ds.append(d)
            ahead = d - craft.dist
            d += 3.0 if ahead < 80 else (8.0 if ahead < 200 else 16.0)
        ds.append(craft.dist + DRAW_AHEAD)

        edges = []  # (d, left_screen, right_screen, z) or None
        for d in ds:
            pos, _fwd, right, _up = spline.frame_at(d)
            pl = self._project(pos - right * hw, cam)
            pr = self._project(pos + right * hw, cam)
            edges.append((d, pl, pr) if pl and pr else None)

        # far -> near so near quads paint over far ones on dips/crests
        for i in range(len(edges) - 2, -1, -1):
            a, b = edges[i], edges[i + 1]
            if a is None or b is None:
                continue
            d0, al, ar = a
            _d1, bl, br = b
            z = min(al[2], ar[2])
            fog = min(1.0, max(0.0, z / FOG_DIST)) * 0.88
            base = ROAD_DARK if int(d0 // 10) % 2 else ROAD_LIGHT
            quad = [(al[0], al[1]), (ar[0], ar[1]), (br[0], br[1]), (bl[0], bl[1])]
            pygame.draw.polygon(self.screen, _lerp3(base, self.planet.sky_color, fog), quad)

            def strip(f0, f1, color):
                p = [(al[0] + (ar[0] - al[0]) * f0, al[1] + (ar[1] - al[1]) * f0),
                     (al[0] + (ar[0] - al[0]) * f1, al[1] + (ar[1] - al[1]) * f1),
                     (bl[0] + (br[0] - bl[0]) * f1, bl[1] + (br[1] - bl[1]) * f1),
                     (bl[0] + (br[0] - bl[0]) * f0, bl[1] + (br[1] - bl[1]) * f0)]
                pygame.draw.polygon(self.screen, _lerp3(color, self.planet.sky_color, fog), p)

            rail = (255, 150, 120) if craft.scraping else RAIL_COLOR
            strip(0.0, 0.03, rail)
            strip(0.97, 1.0, rail)
            if int(d0 // 12) % 2 == 0:  # scrolling centre dashes
                strip(0.492, 0.508, DASH_COLOR)

    def _draw_craft(self, spline, craft, cam):
        pos, _fwd, right, _up = spline.frame_at(craft.dist)
        ground = pos + right * craft.lat
        # shadow stays on the ribbon — the altitude cue
        sp = self._project(ground, cam)
        if sp:
            size = 3.4 * self.focal / sp[2]
            fade = max(40, 110 - int(craft.alt * 18))
            shadow = pygame.Surface((int(size), int(size * 0.4)), pygame.SRCALPHA)
            pygame.draw.ellipse(shadow, (0, 0, 0, fade), shadow.get_rect())
            self.screen.blit(shadow, (sp[0] - size / 2, sp[1] - size * 0.2))

        wp = self._project(craft.world_pos() + WORLD_UP * 0.8, cam)
        if not wp:
            return
        w_px = max(8, 3.2 * self.focal / wp[2])
        surf = pygame.Surface((120, 64), pygame.SRCALPHA)
        pygame.draw.ellipse(surf, HULL_SHADE, (4, 18, 112, 40))
        pygame.draw.ellipse(surf, HULL_COLOR, (4, 12, 112, 38))
        pygame.draw.ellipse(surf, CANOPY_COLOR, (38, 16, 44, 16))
        glow = DASH_COLOR if craft.grounded else (255, 210, 140)
        pygame.draw.rect(surf, glow, (18, 50, 22, 9), border_radius=4)
        pygame.draw.rect(surf, glow, (80, 50, 22, 9), border_radius=4)
        roll = -craft.lat_vel * 0.9
        sprite = pygame.transform.rotozoom(surf, roll, w_px / 120.0)
        self.screen.blit(sprite, sprite.get_rect(center=(wp[0], wp[1])))

    def _draw_hud(self, craft):
        kmh = int(craft.speed * 3.6)
        num = self.font_big.render(f"{kmh}", True, (235, 240, 246))
        self.screen.blit(num, (34, self.h - 150))
        lab = self.font_med.render("KM/H", True, TEXT_DIM)
        self.screen.blit(lab, (40 + num.get_width(), self.h - 78))

        tag = self.font_med.render(self.planet.name.upper(), True,
                                   self.planet.accent_color)
        self.screen.blit(tag, (34, 26))
        if not craft.grounded:
            air = self.font_small.render(f"AIR  +{craft.alt:.1f}m", True,
                                         self.planet.accent_color)
            self.screen.blit(air, (34, 60))
        if craft.scraping:
            warn = self.font_med.render("EDGE", True, RAIL_COLOR)
            self.screen.blit(warn, (self.cx - warn.get_width() // 2, self.h - 60))
