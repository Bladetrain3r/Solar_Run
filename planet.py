"""Planet physics profiles — data, not code.

A planet is a small bundle of numbers the craft reads each frame. Values are
GAMEPLAY-scaled, not astronomically real: what matters is the relative feel
(Moon = floaty and grippy-in-vacuum, Venus = soup, ...). Profiles live in
data/planets/*.json so adding a body is a content task.
"""

import json
from dataclasses import dataclass
from pathlib import Path

PLANET_DIR = Path(__file__).parent / "data" / "planets"


@dataclass
class Planet:
    name: str
    gravity: float      # downward accel, m/s^2 (gameplay-scaled)
    drag: float         # atmospheric quadratic drag coeff (0 = vacuum)
    grip: float         # steering authority multiplier (1.0 = baseline)
    sky_color: tuple    # background, top of sky
    ground_color: tuple # background, below horizon
    accent_color: tuple # HUD / edge-rail accent

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
        )
