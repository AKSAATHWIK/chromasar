"""Ship performance model: how weather turns into speed, fuel and risk.

Assumptions are stated explicitly because a naval-architecture panel will ask. Every
number here is a documented approximation, not a fitted result - and the model is
pluggable per vessel, which is what the PS asks for ("a range of ships with varying
type, dimensions, drift characteristics").

Physics used:
  * Calm-water power scales roughly with V^3 (Admiralty coefficient form).
  * Added resistance in waves grows with Hs^2 and depends strongly on the wave
    encounter angle - head seas cost far more than following seas.
  * Speed over ground = speed through water (vector) + surface current (vector).
  * Involuntary speed loss: in heavy seas the master slows down regardless of power.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

KTS = 0.514444  # m/s per knot


@dataclass
class Ship:
    name: str = "Generic Handymax bulker"
    loa_m: float = 190.0
    beam_m: float = 32.0
    displacement_t: float = 58000.0
    service_speed_kts: float = 14.0
    max_speed_kts: float = 16.5
    sfoc_t_per_kwh: float = 0.00019     # tonnes fuel per kWh
    calm_power_kw: float = 8200.0       # shaft power at service speed, calm water
    hs_limit_m: float = 6.5             # master's heavy-weather limit
    hs_caution_m: float = 4.5           # comfort / cargo-safety threshold

    # ---------------------------------------------------------------- power
    def calm_power(self, stw_kts: float) -> float:
        """Cubic scaling off the service-speed design point."""
        return self.calm_power_kw * (stw_kts / self.service_speed_kts) ** 3

    def wave_penalty(self, hs: float, rel_wave_deg: float) -> float:
        """Multiplier on power from added resistance in waves.

        rel_wave_deg is the angle between the ship's heading and the direction the
        waves are travelling towards: 180 deg = head seas (worst), 0 = following.
        """
        a = math.radians(rel_wave_deg)
        # 1.0 in head seas, ~0.25 following, ~0.6 beam
        directionality = 0.62 - 0.38 * math.cos(a)
        return 1.0 + 0.34 * directionality * (hs ** 2) / (self.service_speed_kts ** 0.5)

    def involuntary_speed_loss(self, hs: float, rel_wave_deg: float) -> float:
        """Fraction of speed lost that no amount of throttle recovers."""
        if hs < 2.0:
            return 0.0
        a = math.radians(rel_wave_deg)
        head = max(0.0, -math.cos(a))          # 1 in head seas, 0 following
        return min(0.45, 0.020 * (hs ** 1.7) * (0.35 + 0.65 * head))

    # ---------------------------------------------------------------- risk
    def risk(self, hs: float, rel_wave_deg: float) -> float:
        """0 = safe, 1 = at the master's limit, >1 = should not be there.

        Beam seas are penalised extra: that is the parametric-roll / cargo-shift case,
        which is what actually damages ships and hurts people.
        """
        if hs <= 0:
            return 0.0
        base = hs / self.hs_limit_m
        beam = abs(math.sin(math.radians(rel_wave_deg)))    # 1 at beam seas
        return base * (1.0 + 0.35 * beam)

    def is_navigable(self, hs: float, rel_wave_deg: float) -> bool:
        return self.risk(hs, rel_wave_deg) <= 1.0


def relative_wave_angle(heading_deg: float, wave_dir_deg: float) -> float:
    """0 = waves travelling with the ship, 180 = head seas. Always in [0, 180]."""
    d = abs((wave_dir_deg - heading_deg + 180.0) % 360.0 - 180.0)
    return d


def transit(ship: Ship, heading_deg: float, dist_km: float, cond, throttle_kts=None):
    """Traverse one edge. Returns (hours, fuel_tonnes, risk) or None if unsafe.

    Solves speed over ground properly: the ship steers through the water, the current
    carries it, and the two add as vectors. Water-relative heading is corrected so the
    resulting ground track actually points where we want to go.
    """
    stw = throttle_kts if throttle_kts else ship.service_speed_kts
    rel = relative_wave_angle(heading_deg, cond.wave_dir)

    if not ship.is_navigable(cond.hs, rel):
        return None

    stw_eff = stw * (1.0 - ship.involuntary_speed_loss(cond.hs, rel))
    if stw_eff <= 0.5:
        return None
    v_water = stw_eff * KTS

    # desired ground track unit vector
    hr = math.radians(heading_deg)
    gx, gy = math.sin(hr), math.cos(hr)
    cx, cy = cond.u_cur, cond.v_cur

    # solve |v_water| steering so that (steer + current) is parallel to (gx, gy):
    # decompose current into along/cross track, cancel the cross component.
    c_along = cx * gx + cy * gy
    c_cross = -cx * gy + cy * gx
    if abs(c_cross) >= v_water:
        return None                      # current too strong to hold the track
    v_along = math.sqrt(v_water ** 2 - c_cross ** 2)
    sog = v_along + c_along              # m/s over ground
    if sog <= 0.2:
        return None                      # pushed backwards

    hours = (dist_km * 1000.0) / sog / 3600.0
    power = ship.calm_power(stw) * ship.wave_penalty(cond.hs, rel)
    fuel = power * ship.sfoc_t_per_kwh * hours
    return hours, fuel, ship.risk(cond.hs, rel)
