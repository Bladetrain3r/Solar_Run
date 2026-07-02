"""Software 3D renderer — the thin, swappable seam.

Projects the track ribbon + craft to the screen with a chase camera and
plain perspective math. This is the throwback LOOK, not a placeholder.
Nothing in here touches game logic; a future GPU renderer replaces this
file and nothing else.

Owns: camera, projection, sky/stars, ribbon strip (with fork branches and
checkpoint gates), craft + ghost sprites, HUD (race clock or zen tag).
Feeds on track.sample_ahead — it never walks the segment graph itself.
"""

import math

import numpy as np
import pygame

from spline import WORLD_UP
from track import SURFACE_FLAGS

# Camera + projection dials
CAM_BACK = 16.0        # m behind the craft along the track
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
GATE_DIM = (110, 118, 130)


def _lerp3(a, b, t):
    return (int(a[0] + (b[0] - a[0]) * t),
            int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t))


def fmt_time(t):
    m, s = divmod(max(0.0, t), 60.0)
    return f"{int(m)}:{s:04.1f}"


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

    def _camera(self, track, seg_id, prev_seg, craft):
        pos, _f, right, _u = track.frame_at_offset(
            seg_id, craft.dist, -CAM_BACK, craft.lat, prev_seg)
        self.cam_lat += (craft.lat * 0.45 - self.cam_lat) * 0.12
        cam_pos = pos + right * self.cam_lat + WORLD_UP * CAM_HEIGHT
        tpos, _f2, _r2, _u2 = track.frame_at_offset(
            seg_id, craft.dist, CAM_AHEAD, craft.lat, prev_seg)
        f = (tpos + WORLD_UP * 2.0) - cam_pos
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

    # --- scene ---------------------------------------------------------------

    def draw(self, track, seg_id, prev_seg, craft, race=None, ghost_pos=None,
             best_total=None, zen=False):
        cam = self._camera(track, seg_id, prev_seg, craft)
        primary, alt, gates = track.sample_ahead(
            seg_id, craft.dist, DRAW_AHEAD, craft.lat, prev_seg)
        self._draw_sky(cam)
        self._draw_strip(alt, cam, craft.odometer, dim=0.45)
        self._draw_strip(primary, cam, craft.odometer, dim=0.0,
                         scraping=craft.scraping)
        self._draw_gates(gates, cam)
        if ghost_pos is not None:
            self._draw_pod(ghost_pos, cam, alpha=110)
        self._draw_craft(craft, cam)
        self.screen.blit(self.scanlines, (0, 0))
        self._draw_hud(track, seg_id, craft, race, best_total, zen)

    def _draw_sky(self, cam):
        _cam_pos, _r, _u, f = cam
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
        ex = int((self.w * 1.4 - shift) % (self.w * 2))
        ey = horizon - 70
        if 0 <= ex < self.w and ey > 20:
            pygame.draw.circle(self.screen, (29, 51, 72), (ex, ey), 26)
            pygame.draw.circle(self.screen, (127, 168, 201), (ex - 7, ey - 7), 17)

    def _draw_strip(self, samples, cam, odometer, dim=0.0, scraping=False):
        """One ribbon strip from track samples. dim > 0 = the unchosen
        fork branch, faded toward the sky so the choice reads at a glance."""
        hw = self.half_width
        edges = []
        for d_off, pos, right, flag in samples:
            pl = self._project(pos - right * hw, cam)
            pr = self._project(pos + right * hw, cam)
            edges.append((d_off, pl, pr, flag) if pl and pr else None)

        for i in range(len(edges) - 2, -1, -1):
            a, b = edges[i], edges[i + 1]
            if a is None or b is None:
                continue
            d0, al, ar, flag = a
            _d1, bl, br, _fl = b
            z = min(al[2], ar[2])
            fog = min(1.0, max(0.0, z / FOG_DIST)) * 0.88 + dim
            fog = min(fog, 0.97)
            phase = odometer + d0
            base = ROAD_DARK if int(phase // 10) % 2 else ROAD_LIGHT
            tint = SURFACE_FLAGS[flag][2]
            if tint:
                base = _lerp3(base, tint, 0.45)
            quad = [(al[0], al[1]), (ar[0], ar[1]), (br[0], br[1]), (bl[0], bl[1])]
            pygame.draw.polygon(self.screen,
                                _lerp3(base, self.planet.sky_color, fog), quad)

            def strip(f0, f1, color):
                p = [(al[0] + (ar[0] - al[0]) * f0, al[1] + (ar[1] - al[1]) * f0),
                     (al[0] + (ar[0] - al[0]) * f1, al[1] + (ar[1] - al[1]) * f1),
                     (bl[0] + (br[0] - bl[0]) * f1, bl[1] + (br[1] - bl[1]) * f1),
                     (bl[0] + (br[0] - bl[0]) * f0, bl[1] + (br[1] - bl[1]) * f0)]
                pygame.draw.polygon(self.screen,
                                    _lerp3(color, self.planet.sky_color, fog), p)

            rail = (255, 150, 120) if (scraping and dim == 0) else RAIL_COLOR
            strip(0.0, 0.03, rail)
            strip(0.97, 1.0, rail)
            if int(phase // 12) % 2 == 0:
                strip(0.492, 0.508, DASH_COLOR)

    def _draw_gates(self, gates, cam):
        """Checkpoint gates: posts + beam + diamond. The nearest gate ahead
        is lit in the planet accent; finish gets a double beam."""
        lit_done = False
        for d_off, pos, right, up, ckpt in sorted(gates, key=lambda g: g[0]):
            if d_off < 0:
                continue
            lit = not lit_done
            lit_done = True
            color = self.planet.accent_color if lit else GATE_DIM
            hw, gh = self.half_width, 7.0
            pts = {}
            for name, p in (("lb", pos - right * hw), ("rb", pos + right * hw),
                            ("lt", pos - right * hw + up * gh),
                            ("rt", pos + right * hw + up * gh)):
                pr = self._project(p, cam)
                if pr is None:
                    break
                pts[name] = (int(pr[0]), int(pr[1]))
            if len(pts) < 4:
                continue
            w = max(1, int(3.0 * self.focal / max(1.0, d_off + CAM_BACK)))
            pygame.draw.line(self.screen, color, pts["lb"], pts["lt"], w)
            pygame.draw.line(self.screen, color, pts["rb"], pts["rt"], w)
            pygame.draw.line(self.screen, color, pts["lt"], pts["rt"], w)
            if ckpt.finish:
                mid_l = (pts["lt"][0], pts["lt"][1] + 3 * w)
                mid_r = (pts["rt"][0], pts["rt"][1] + 3 * w)
                pygame.draw.line(self.screen, color, mid_l, mid_r, w)
            tx = (pts["lt"][0] + pts["rt"][0]) // 2
            ty = min(pts["lt"][1], pts["rt"][1]) - 4 * w
            pygame.draw.polygon(self.screen, color,
                                [(tx, ty - 3 * w), (tx + 2 * w, ty),
                                 (tx, ty + 3 * w), (tx - 2 * w, ty)])

    def _draw_pod(self, world_pos, cam, alpha=255, roll=0.0, boosting=False,
                  grounded=True):
        wp = self._project(world_pos + WORLD_UP * 0.8, cam)
        if not wp:
            return
        w_px = max(8, 3.2 * self.focal / wp[2])
        surf = pygame.Surface((120, 64), pygame.SRCALPHA)
        glow = DASH_COLOR if grounded else (255, 210, 140)
        if boosting:
            glow = (255, 250, 235)
            pygame.draw.ellipse(surf, (255, 200, 110, 110), (0, 6, 120, 56))
        pygame.draw.ellipse(surf, HULL_SHADE, (4, 18, 112, 40))
        pygame.draw.ellipse(surf, HULL_COLOR, (4, 12, 112, 38))
        pygame.draw.ellipse(surf, CANOPY_COLOR, (38, 16, 44, 16))
        pygame.draw.rect(surf, glow, (18, 50, 22, 9), border_radius=4)
        pygame.draw.rect(surf, glow, (80, 50, 22, 9), border_radius=4)
        sprite = pygame.transform.rotozoom(surf, roll, w_px / 120.0)
        if alpha < 255:
            sprite.set_alpha(alpha)
        self.screen.blit(sprite, sprite.get_rect(center=(wp[0], wp[1])))

    def _draw_craft(self, craft, cam):
        pos, _fwd, right, _up = craft.spline.frame_at(craft.dist)
        ground = pos + right * craft.lat
        sp = self._project(ground, cam)
        if sp:
            size = 3.4 * self.focal / sp[2]
            fade = max(40, 110 - int(craft.alt * 18))
            shadow = pygame.Surface((int(size), int(size * 0.4)), pygame.SRCALPHA)
            pygame.draw.ellipse(shadow, (0, 0, 0, fade), shadow.get_rect())
            self.screen.blit(shadow, (sp[0] - size / 2, sp[1] - size * 0.2))
        self._draw_pod(craft.world_pos(), cam, roll=-craft.lat_vel * 0.9,
                       boosting=craft.boosting, grounded=craft.grounded)

    # --- HUD -------------------------------------------------------------

    def _draw_hud(self, track, seg_id, craft, race, best_total, zen):
        kmh = int(craft.speed * 3.6)
        num = self.font_big.render(f"{kmh}", True, (235, 240, 246))
        self.screen.blit(num, (34, self.h - 150))
        lab = self.font_med.render("KM/H", True, TEXT_DIM)
        self.screen.blit(lab, (40 + num.get_width(), self.h - 78))

        tag = "ZEN · " + self.planet.name.upper() if zen \
            else self.planet.name.upper() + " · " + track.name.upper()
        self.screen.blit(self.font_med.render(tag, True,
                                              self.planet.accent_color), (34, 26))
        if craft.scraping:
            warn = self.font_med.render("EDGE", True, RAIL_COLOR)
            self.screen.blit(warn, (self.cx - warn.get_width() // 2, self.h - 60))

        # boost readiness, bottom-right
        charge = craft.boost_charge()
        color = self.planet.accent_color if charge >= 1.0 else TEXT_DIM
        txt = self.font_med.render("BOOST", True, color)
        x = self.w - txt.get_width() - 40
        self.screen.blit(txt, (x, self.h - 78))
        pygame.draw.rect(self.screen, (60, 65, 74),
                         (x, self.h - 46, txt.get_width(), 6))
        pygame.draw.rect(self.screen, color,
                         (x, self.h - 46, int(txt.get_width() * charge), 6))

        if zen or race is None:
            return

        # race clock cluster, top-right
        ck = track.dist_to_next_checkpoint(seg_id, craft.dist, craft.lat)
        if ck is not None:
            t = self.font_small.render(f"CKPT IN {int(ck)}m", True, TEXT_DIM)
            self.screen.blit(t, (self.w - t.get_width() - 40, 30))
        clock = self.font_big.render(fmt_time(race.remaining), True,
                                     self.planet.accent_color)
        self.screen.blit(clock, (self.w - clock.get_width() - 36, 48))
        sub = f"TOTAL {fmt_time(race.total)}"
        if best_total is not None:
            sub += f" · BEST {fmt_time(best_total)}"
        s = self.font_small.render(sub, True, TEXT_DIM)
        self.screen.blit(s, (self.w - s.get_width() - 40, 136))

        if race.state != "running":
            if race.state == "finished":
                msg, col = f"FINISH  {fmt_time(race.total)}", self.planet.accent_color
                if best_total is None or race.total <= best_total:
                    msg += "  · BEST"
            else:
                msg, col = "TIME OUT", RAIL_COLOR
            b = self.font_big.render(msg, True, col)
            self.screen.blit(b, (self.cx - b.get_width() // 2, self.cy - 120))
            r = self.font_med.render("R — restart", True, TEXT_DIM)
            self.screen.blit(r, (self.cx - r.get_width() // 2, self.cy - 30))
