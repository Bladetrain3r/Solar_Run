"""Craft handling — the make-or-break module.

The craft lives in RIBBON SPACE: distance along the spline, lateral offset
across it, altitude above it. Steering is lateral + jump (Skyroads-legible),
never 6-DOF. The craft's numbers stay constant; the PLANET imposes gravity,
drag and grip — constrain the world, not the actor.

All feel-tuning numbers live in TUNING at the top. Iterate there, longest.
"""

import numpy as np

# ---------------------------------------------------------------------------
# Handling tuning — THE dials. Everything here is craft-constant; planet
# profiles multiply in on top (gravity/drag/grip).
# ---------------------------------------------------------------------------
TUNING = {
    "thrust_accel": 48.0,     # m/s^2 at full throttle
    "brake_decel": 90.0,      # m/s^2 at full brake
    "base_damp": 0.30,        # /s, linear speed bleed (engine/field losses)
    "max_lat_speed": 30.0,    # m/s, lateral slew at full steer, grip=1
    "lat_response": 9.0,      # /s, how fast lateral vel chases the stick
    "air_control": 0.35,      # steering authority multiplier while airborne
    "jump_impulse": 8.5,      # m/s vertical kick
    "ribbon_half_width": 10.0,# m, drivable half-width of the ribbon
    "hull_half_width": 1.3,   # m, craft half-width (edge clamp margin)
    "scrape_decel": 1.2,      # /s, speed bleed while grinding an edge rail
    "grounded_eps": 0.08,     # m, altitude below which we count as grounded
}


class Craft:
    """Reads a Planet profile, queries a Spline for the surface under it."""

    def __init__(self, spline, planet):
        self.spline = spline
        self.planet = planet
        self.reset()

    def reset(self, dist=0.0):
        self.dist = dist                 # metres along the spline
        self.lat = 0.0                   # metres right of centerline
        self.speed = 0.0                 # m/s along the track
        self.lat_vel = 0.0               # m/s across the track
        self.world_z = float(self.spline.pos_at(dist)[2])
        self.vz = 0.0                    # vertical velocity, world space
        self.alt = 0.0                   # metres above ribbon surface
        self.grounded = True
        self.scraping = False

    def update(self, dt, throttle, brake, steer, jump):
        """Advance one frame. throttle/brake in [0,1], steer in [-1,1],
        jump is a bool (edge-triggered by the caller or held, both fine —
        it only fires when grounded)."""
        t = TUNING

        # --- longitudinal: thrust vs brake vs bleed ---
        accel = t["thrust_accel"] * throttle - t["brake_decel"] * brake
        accel -= t["base_damp"] * self.speed                  # engine losses
        accel -= self.planet.drag * self.speed * self.speed   # atmosphere
        self.speed = max(0.0, self.speed + accel * dt)

        # --- lateral: grip-limited slew toward the stick ---
        authority = self.planet.grip
        if not self.grounded:
            authority *= t["air_control"]
        target = steer * t["max_lat_speed"] * authority
        blend = min(1.0, t["lat_response"] * authority * dt)
        self.lat_vel += (target - self.lat_vel) * blend
        self.lat += self.lat_vel * dt

        # edge rails: clamp and grind (falling off arrives with forks)
        limit = t["ribbon_half_width"] - t["hull_half_width"]
        self.scraping = False
        if abs(self.lat) > limit:
            self.lat = limit if self.lat > 0 else -limit
            self.lat_vel = 0.0
            self.speed *= max(0.0, 1.0 - t["scrape_decel"] * dt)
            self.scraping = True

        # --- advance along the track ---
        ribbon_z_old = float(self.spline.pos_at(self.dist)[2])
        self.dist += self.speed * dt
        ribbon_z_new = float(self.spline.pos_at(self.dist)[2])

        # --- vertical: one unified model. vz always integrates gravity;
        # the ribbon catches us when we meet it. Cresting a hill faster
        # than gravity can pull you down = airtime, for free. ---
        if self.grounded and jump:
            self.vz = t["jump_impulse"]
            # inherit the ground's vertical motion so hill-jumps carry it
            if dt > 0:
                self.vz += max(0.0, (ribbon_z_new - ribbon_z_old) / dt)
            self.grounded = False

        self.vz -= self.planet.gravity * dt
        self.world_z += self.vz * dt

        if self.world_z <= ribbon_z_new:
            self.world_z = ribbon_z_new
            self.vz = (ribbon_z_new - ribbon_z_old) / dt if dt > 0 else 0.0
            self.grounded = True
        else:
            self.grounded = False
        self.alt = self.world_z - ribbon_z_new

    def world_pos(self):
        """3D world position (centerline frame + lateral + altitude)."""
        pos, _fwd, right, up = self.spline.frame_at(self.dist)
        return pos + right * self.lat + up * self.alt
