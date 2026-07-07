"""Planet physics profiles — data, not code.

A planet is a small bundle of numbers the craft, terrain and renderer
read. Values are GAMEPLAY-scaled, not astronomically real: what matters
is the relative feel (Moon = floaty vacuum, Mercury = lava-scarred rock).
Profiles live in data/planets/*.json so adding a body is a content task.

Optional keys (all default to Moon-like behaviour when absent):
  "terrain":  {hill_amp: [lo,hi], craters: [lo,hi], crater_r: [lo,hi]}
              — heightmap tuning ranges, read by terrain.py
  "features": ["lava_lakes", ...] — switches for terrain effects
  "liquid":   {color, glow, opacity, fill, pulse_speed} — how flooded
              indents look; generic enough for other liquids later
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

PLANET_DIR = Path(__file__).parent / "data" / "planets"


@dataclass
class Planet:
    name: str
    gravity: float      # downward accel, m/s^2 (gameplay-scaled)
    drag: float         # atmospheric quadratic drag coeff (0 = vacuum)
    grip: float         # steering authority multiplier (1.0 = baseline)
    sky_color: tuple    # background, top of sky
    ground_color: tuple # background, below horizon; terrain shading base
    accent_color: tuple # HUD / gate accent
    features: tuple = ()          # terrain effect switches
    liquid: dict = None           # flooded-indent look (lava, ...)
    terrain: dict = field(default_factory=dict)  # heightmap tuning

    @classmethod
    def list_available(cls):
        return sorted(p.stem for p in PLANET_DIR.glob("*.json"))

    @classmethod
    def load(cls, name):
        raw = json.loads((PLANET_DIR / f"{name}.json").read_text())
        return cls(
            name=raw["name"],
            gravity=raw["gravity"],
            drag=raw["drag"],
            grip=raw["grip"],
            sky_color=tuple(raw["sky_color"]),
            ground_color=tuple(raw["ground_color"]),
            accent_color=tuple(raw["accent_color"]),
            features=tuple(raw.get("features", [])),
            liquid=raw.get("liquid"),
            terrain=raw.get("terrain", {}),
        )
