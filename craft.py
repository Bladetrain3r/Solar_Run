"""Craft handling — the make-or-break module.

The craft lives in RIBBON SPACE: distance along the spline, lateral offset
across it, altitude above it. Steering is lateral + jump (Skyroads-legible),
never 6-DOF. The craft's numbers stay constant; the PLANET imposes gravity,
drag and grip — constrain the world, not the actor.

The craft has its OWN trajectory: when the track curves under it, it keeps
going straight, which in ribbon space is a centrifugal push toward the
outside (curvature * speed^2). Steering is lateral THRUST you supply to
fight that — so corner-holding speed emerges from physics: max corner
speed = sqrt(steer_accel * grip / curvature).

All feel-tuning numbers live in TUNING at the top. Iterate there, longest.
"""

import numpy as np

# ---------------------------------------------------------------------------
# Handling tuning — THE dials. Everything here is craft-constant; planet
# profiles multiply in on top (gravity/drag/grip).
# ---------------------------------------------------------------------------
TUNING = {
    "thrust_accel": 32.0,     # m/s^2 at full throttle
    "brake_decel": 48.0,      # m/s^2 at full brake
    "base_damp": 0.30,        # /s, linear speed bleed (engine/field losses)
    "steer_accel": 100.0,     # m/s^2 lateral thrust at full steer, grip=1
    "lat_damp": 2.6,          # /s, lateral-velocity bleed (field "grip")
    "centrifugal_scale": 0.75,# how much of the frame's push the AG field
                              # fails to counter (1.0 = full physics)
    "air_steer": 0.35,        # steering authority multiplier while airborne
    "air_damp": 0.25,         # lateral damping multiplier while airborne
    "jump_impulse": 4.5,      # m/s vertical kick
    "boost_lat_accel": 100.0, # m/s^2 (~10g) lateral kick, full power in air
    "boost_lat_time": 0.2,    # s, lateral boost burn
    "boost_fwd_accel": 260.0, # m/s^2 forward slam when boosting straight
    "boost_fwd_time": 0.35,   # s, forward boost burn
    "boost_cooldown": 1.0,    # s between boosts — a rhythm, not a spam
    "ribbon_half_width": 10.0,# m, drivable half-width of the ribbon
    "hull_half_width": 1.3,   # m, craft half-width (edge clamp margin)
    "rail_bounce": 0.35,      # fraction of lateral vel reflected off a rail
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
        self.boost_timer = 0.0   # remaining burn, seconds
        self.boost_dir = 0       # -1/+1 lateral, 0 = forward
        self.boost_cd = 0.0      # cooldown remaining
        self.boosting = False

    def update(self, dt, throttle, brake, steer, jump, boost=False):
        """Advance one frame. throttle/brake in [0,1], steer in [-1,1],
        jump held (only fires when grounded), boost edge-triggered
        (a Shift TAP, not hold)."""
        t = TUNING

        # --- boost: a thruster slam, direction locked at ignition ---
        self.boost_cd = max(0.0, self.boost_cd - dt)
        if boost and self.boost_cd <= 0.0:
            self.boost_dir = (steer > 0) - (steer < 0)
            self.boost_timer = (t["boost_lat_time"] if self.boost_dir
                                else t["boost_fwd_time"])
            self.boost_cd = t["boost_cooldown"]
        boosting = self.boost_timer > 0.0
        self.boosting = boosting  # renderer reads this for the flare
        self.boost_timer = max(0.0, self.boost_timer - dt)

        # --- longitudinal: thrust vs brake vs bleed ---
        accel = t["thrust_accel"] * throttle - t["brake_decel"] * brake
        if boosting and self.boost_dir == 0:
            accel += t["boost_fwd_accel"]
        accel -= t["base_damp"] * self.speed                  # engine losses
        accel -= self.planet.drag * self.speed * self.speed   # atmosphere
        self.speed = max(0.0, self.speed + accel * dt)

        # --- lateral: the craft's own trajectory ---
        # The track curving under you IS a lateral push toward the outside
        # (in the ribbon's rotating frame). Left bend = drift right. This
        # applies grounded or airborne — it's geometry, not grip — but the
        # AG field counters part of it (centrifugal_scale).
        centrifugal = (self.spline.curvature_at(self.dist)
                       * self.speed ** 2 * t["centrifugal_scale"])

        # Steering is lateral thrust; grip is how hard the field can shove.
        grip = self.planet.grip
        steer_authority = grip * (1.0 if self.grounded else t["air_steer"])
        damp = t["lat_damp"] * grip * (1.0 if self.grounded else t["air_damp"])

        lat_accel = (steer * t["steer_accel"] * steer_authority
                     + centrifugal
                     - damp * self.lat_vel)
        if boosting and self.boost_dir != 0:
            # thruster, not tyres: full power airborne, ignores grip
            lat_accel += self.boost_dir * t["boost_lat_accel"]
        self.lat_vel += lat_accel * dt
        self.lat += self.lat_vel * dt

        # edge rails: bounce and grind (falling off arrives with forks)
        limit = t["ribbon_half_width"] - t["hull_half_width"]
        self.scraping = False
        if abs(self.lat) > limit:
            self.lat = limit if self.lat > 0 else -limit
            self.lat_vel = -self.lat_vel * t["rail_bounce"]
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

    def boost_charge(self):
        """0..1 cooldown recovery — 1.0 means boost is ready (HUD reads this)."""
        return 1.0 - self.boost_cd / TUNING["boost_cooldown"]

    def world_pos(self):
        """3D world position (centerline frame + lateral + altitude)."""
        pos, _fwd, right, up = self.spline.frame_at(self.dist)
        return pos + right * self.lat + up * self.alt
