"""Environmental forcing fields (currents, waves, wind).

Everything the router needs sits behind one interface, so the analytic test field and a
real INCOIS/HYCOM feed are interchangeable. The router never knows which it is using.

Convention throughout: u = eastward component, v = northward component, both m/s.
Wave direction is the direction waves travel TOWARDS, in degrees clockwise from north.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass
class Conditions:
    u_cur: float      # m/s eastward current
    v_cur: float      # m/s northward current
    hs: float         # m significant wave height
    wave_dir: float   # deg, direction waves travel towards
    u_wind: float     # m/s eastward wind
    v_wind: float     # m/s northward wind


class ForcingField:
    """Base interface. Subclass and implement `at`."""

    def at(self, lat: float, lon: float, t_hours: float) -> Conditions:
        raise NotImplementedError

    def grid(self, lats, lons, t_hours):
        """Sample onto a mesh - used for plotting."""
        U = np.zeros((len(lats), len(lons)))
        V = np.zeros_like(U)
        H = np.zeros_like(U)
        for i, la in enumerate(lats):
            for j, lo in enumerate(lons):
                c = self.at(la, lo, t_hours)
                U[i, j], V[i, j], H[i, j] = c.u_cur, c.v_cur, c.hs
        return U, V, H


class SyntheticIndianOcean(ForcingField):
    """Analytic Indian Ocean forcing with known-correct structure.

    Three features the router should visibly react to:

    1. A zonal jet near 5 deg S flowing WEST at up to 1.5 m/s. Westbound ships should
       be pulled onto it; eastbound ships should avoid it.
    2. A monsoon gyre centred in the Arabian Sea - circular flow, so the cheapest path
       around it depends on which way you are going.
    3. A storm cell with high waves, drifting EAST at 20 km/h. Because it moves, the
       correct answer depends on WHEN you arrive - which is the whole point of
       time-dependent routing. A static router cannot get this right.

    If the optimiser does not bend towards the jet and around the storm, it is broken.
    """

    def __init__(self, storm_lat=-6.0, storm_lon0=57.0, storm_speed_kmh=9.0,
                 storm_radius_km=620.0, storm_hs=4.6, seed=1658):
        self.storm_lat = storm_lat
        self.storm_lon0 = storm_lon0
        self.storm_speed_kmh = storm_speed_kmh
        self.storm_radius_km = storm_radius_km
        self.storm_hs = storm_hs
        self.rng = np.random.default_rng(seed)

    def storm_centre(self, t_hours):
        # ~111 km per degree of longitude at low latitude
        lon = self.storm_lon0 + (self.storm_speed_kmh * t_hours) / 111.0
        return self.storm_lat, lon

    def at(self, lat, lon, t_hours):
        # --- 1. westward equatorial jet, gaussian about 5S -------------
        jet = -1.5 * math.exp(-((lat + 5.0) ** 2) / (2 * 2.5 ** 2))
        u = jet
        v = 0.0

        # --- 2. Arabian Sea monsoon gyre, anticlockwise ----------------
        gy_lat, gy_lon, gy_r = 14.0, 62.0, 8.0
        dlat, dlon = lat - gy_lat, lon - gy_lon
        r = math.hypot(dlat, dlon)
        if r < gy_r and r > 1e-6:
            strength = 1.1 * (1 - r / gy_r)
            u += -strength * (dlat / r)
            v += strength * (dlon / r)

        # --- 3. moving storm -------------------------------------------
        slat, slon = self.storm_centre(t_hours)
        d_km = haversine_km(lat, lon, slat, slon)
        if d_km < self.storm_radius_km:
            f = 1.0 - (d_km / self.storm_radius_km)
            hs = 1.2 + self.storm_hs * (f ** 1.5)
            wdir = (math.degrees(math.atan2(lon - slon, lat - slat)) + 360) % 360
            wind = 25.0 * f
            uw = wind * math.sin(math.radians(wdir))
            vw = wind * math.cos(math.radians(wdir))
        else:
            hs = 1.2 + 0.8 * math.exp(-((lat + 12.0) ** 2) / 200.0)  # swell band
            wdir = 45.0
            uw, vw = 4.0, 2.0

        return Conditions(u, v, hs, wdir, uw, vw)


class CachedForcing(ForcingField):
    """Memoise field lookups on a quantised (lat, lon, time) key.

    The router samples the field once per edge evaluation, which makes `at` the hot
    path by a wide margin. Neighbouring edges sample nearly the same point at nearly
    the same time, so quantising to the grid resolution and the time bucket collapses
    most of those calls into cache hits without changing the routing decisions.
    """

    def __init__(self, inner, dxy=0.25, dt=3.0):
        self.inner = inner
        self.dxy = dxy
        self.dt = dt
        self._cache = {}
        self.hits = 0
        self.misses = 0

    def at(self, lat, lon, t_hours):
        key = (round(lat / self.dxy), round(lon / self.dxy), round(t_hours / self.dt))
        c = self._cache.get(key)
        if c is None:
            self.misses += 1
            c = self.inner.at(key[0] * self.dxy, key[1] * self.dxy, key[2] * self.dt)
            self._cache[key] = c
        else:
            self.hits += 1
        return c

    def storm_centre(self, t_hours):
        return self.inner.storm_centre(t_hours)

    @property
    def hit_rate(self):
        n = self.hits + self.misses
        return self.hits / n if n else 0.0


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def initial_bearing(lat1, lon1, lat2, lon2):
    """Bearing in degrees clockwise from north, at the start of the great circle."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0
