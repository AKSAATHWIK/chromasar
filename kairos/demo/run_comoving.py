"""End-to-end run of the KAIROS co-moving reduction (Theorem C.1).

Solves the same voyage two ways on the SAME grid:
  A) ground frame, time-dependent Dijkstra   (the conventional approach)
  B) co-moving reduction: stationary sweep + interception root find

and reports arrival times, work done, and the causality diagnostic in both frames.
"""
from __future__ import annotations

import heapq
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np

from kairos.comoving import (NEIGHBOURS, CoMovingField, choose_advection,
                             goal_node_for, interception_time,
                             recover_ground_route, stationary_sweep)
from kairos.geodesy import haversine, heading_to_vec, initial_bearing
from kairos.grid import Grid
from kairos.types import Vessel

D2R = math.pi / 180.0


# ------------------------------------------------------------------ a field with a
# ------------------------------------------------------------------ translating cyclone
class TranslatingCyclone:
    """Western-boundary-style jet plus a cyclone whose centre translates at a fixed w.

    Deliberately simple and self-contained so the demo does not depend on the exact
    constructor signature of environment.SyntheticIndianOcean.
    """

    def __init__(self, w_east=3.0, w_north=1.0, t0=0.0):
        self.w = (w_east, w_north)
        self._t0 = t0
        self.c_lat0 = 5.0 * D2R
        self.c_lon0 = 68.0 * D2R
        self.jet_lon = 52.0 * D2R

    @property
    def t0(self):
        return self._t0

    @property
    def horizon(self):
        return self._t0 + 10 * 86400.0

    def at(self, lat, lon, t):
        from kairos.types import Env
        # jet: northward flow along a meridian (steady)
        dlon = (lon - self.jet_lon) * 6371000.0 * math.cos(lat)
        jet = 1.8 * math.exp(-(dlon ** 2) / (2.0 * (250e3) ** 2))
        cu, cv = 0.0, jet
        # cyclone: rotating current + waves, centre translating at w
        dn = (lat - self.c_lat0) * 6371000.0 - self.w[1] * t
        de = (lon - self.c_lon0) * 6371000.0 * math.cos(lat) - self.w[0] * t
        r = math.hypot(de, dn)
        R0 = 300e3
        amp = 2.2 * math.exp(-(r ** 2) / (2.0 * R0 ** 2))
        if r > 1.0:
            cu += -amp * dn / max(r, 1.0) * 1.0
            cv += amp * de / max(r, 1.0) * 1.0
        hs = 1.2 + 7.0 * math.exp(-(r ** 2) / (2.0 * (R0 * 1.1) ** 2))
        return Env(cu=cu, cv=cv, wu=0.0, wv=0.0, hs=hs, tp=10.0, mu_w=0.0, depth=4000.0)


V_S = 7.2   # constant through-water speed for this demo (pure Zermelo case)


def sigma_from_env(e, u):
    """Drift-corrected speed made good in unit direction u = (east, north)."""
    cpar = e.cu * u[0] + e.cv * u[1]
    cperp = -e.cu * u[1] + e.cv * u[0]
    r = V_S * V_S - cperp * cperp
    if r <= 0.0:
        return 0.0
    s = math.sqrt(r) + cpar
    return s if s > 1e-6 else 0.0


# ------------------------------------------------------------------ ground-frame solver
def ground_sweep(grid, field, src_ij, t0):
    """Time-dependent Dijkstra: the conventional approach, for comparison."""
    T = np.full(grid.n, np.inf)
    par = np.full(grid.n, -1, dtype=np.int64)
    geom = {}

    JREF = 2   # not 0: Grid.latlon wraps negative column indices -- see comoving.py

    def leg(i, k):
        row = geom.get(i)
        if row is None:
            row = []
            la, lo = grid.latlon(i, JREF)
            for di, dj in NEIGHBOURS:
                ni = i + di
                if not (0 <= ni < grid.nlat):
                    row.append(None); continue
                nla, nlo = grid.latlon(ni, JREF + dj)
                row.append((haversine(la, lo, nla, nlo),
                            heading_to_vec(initial_bearing(la, lo, nla, nlo))))
            geom[i] = row
        return row[k]

    s = grid.index(*src_ij)
    T[s] = t0
    pq = [(t0, s)]
    exp = 0
    while pq:
        t, n = heapq.heappop(pq)
        if t > T[n] + 1e-9:
            continue
        exp += 1
        i, j = grid.unindex(n)
        la, lo = grid.latlon(i, j)
        for k, (di, dj) in enumerate(NEIGHBOURS):
            i2, j2 = i + di, j + dj
            if not grid.is_water(i2, j2):
                continue
            g = leg(i, k)
            if g is None:
                continue
            dist, u = g
            nla, nlo = grid.latlon(i2, j2)
            e = field.at(0.5 * (la + nla), 0.5 * (lo + nlo), t)   # DEPARTURE time
            sig = sigma_from_env(e, u)
            if sig <= 1e-6:
                continue
            t2 = t + dist / sig
            m = grid.index(i2, j2)
            if t2 < T[m] - 1e-9:
                T[m] = t2; par[m] = n
                heapq.heappush(pq, (t2, m))
    return T, par, exp


# ------------------------------------------------------------------ main
if __name__ == "__main__":
    SRC = (8.0 * D2R, 77.0 * D2R)      # off Kanyakumari
    DST = (12.6 * D2R, 43.5 * D2R)     # Gulf of Aden approaches

    field = TranslatingCyclone(w_east=3.0, w_north=1.0)
    # The co-moving grid must be DILATED opposite to w by |w|*t_max, because the solve lives
    # in y = x - w t and the target node y = x_B - w t* must be inside it. See
    # comoving.required_dilation_m. Undersizing this fails silently with a plausible-looking
    # but wrong landfall.
    grid = Grid(-10.0, 28.0, 32.0, 80.0, 0.25)
    src_ij = grid.nearest(*SRC)
    dst_ij = grid.nearest(*DST)

    print("=" * 78)
    print("KAIROS -- co-moving reduction, end to end")
    print("=" * 78)
    print(f"grid {grid.nlat} x {grid.nlon} = {grid.n} nodes @ 0.25 deg")
    print(f"voyage: {SRC[0]/D2R:.2f}N {SRC[1]/D2R:.2f}E  ->  {DST[0]/D2R:.2f}N {DST[1]/D2R:.2f}E"
          f"   ({haversine(*SRC, *DST)/1000:.0f} km great circle)")
    print(f"cyclone translating at w_true = (3.0, 1.0) m/s, V_s = {V_S} m/s")
    print()

    # ---- A) ground frame ------------------------------------------------
    t0 = time.perf_counter()
    Tg, parg, expg = ground_sweep(grid, field, src_ij, 0.0)
    el_g = time.perf_counter() - t0
    t_ground = Tg[grid.index(*dst_ij)]
    print(f"A) ground-frame time-dependent Dijkstra")
    print(f"   arrival {t_ground/3600:9.4f} h   expanded {expg:7d}   {el_g:6.2f} s")

    # ---- B) co-moving reduction ----------------------------------------
    lats = [x * D2R for x in (0.0, 8.0, 16.0)]
    lons = [x * D2R for x in (48.0, 60.0, 72.0)]
    times = [0.0, 86400.0, 2 * 86400.0]
    dirs = [heading_to_vec(a) for a in np.linspace(0, 2 * math.pi, 12, endpoint=False)]

    t0 = time.perf_counter()
    w, Lt_ground, Lt_co = choose_advection(field, sigma_from_env, lats, lons, times, dirs,
                                           span=4.0, n=5, rounds=2)
    el_w = time.perf_counter() - t0
    print()
    print(f"B) co-moving reduction")
    print(f"   chosen w = ({w[0]:+.3f}, {w[1]:+.3f}) m/s        [{el_w:.2f} s]")
    print(f"   causality constant  L_t: ground {Lt_ground:.4e} -> co-moving {Lt_co:.4e}"
          f"   ({Lt_ground/max(Lt_co,1e-30):.2f}x)")
    r = 2 * haversine(*grid.latlon(grid.nlat // 2, 0), *grid.latlon(grid.nlat // 2, 1))
    print(f"   r*L_t at r=2h={r/1000:.0f} km : ground {r*Lt_ground:7.4f}"
          f"  ->  co-moving {r*Lt_co:7.4f}")

    co = CoMovingField(field, w[0], w[1], t_ref=0.0)

    def sigma_co(lat, lon, u):
        return sigma_from_env(co.at(lat, lon, 0.0), u)

    t0 = time.perf_counter()
    sw = stationary_sweep(grid, sigma_co, src_ij)
    el_s = time.perf_counter() - t0
    tstar = interception_time(sw, grid, co, DST)
    print(f"   stationary sweep: expanded {sw.expanded:7d}   {el_s:6.2f} s")
    if tstar is None:
        print("   NO INTERCEPTION -- assumption A2 fails (cannot outrun the system)")
    else:
        print(f"   interception t* = {tstar/3600:9.4f} h  (root find)")
        gn, miss = goal_node_for(grid, co, DST, tstar, sw)
        route = recover_ground_route(sw, grid, co, gn)
        t_arr = route[-1][2]
        print(f"   route: {len(route)} waypoints, "
              f"lands at {route[-1][0]/D2R:.3f}N {route[-1][1]/D2R:.3f}E "
              f"(target {DST[0]/D2R:.3f}N {DST[1]/D2R:.3f}E, miss {miss/1000:.1f} km)")
        print(f"   recovered arrival = {t_arr/3600:9.4f} h")
        print()
        print(f"   comparison: ground {t_ground/3600:.4f} h vs co-moving {t_arr/3600:.4f} h"
              f"   -> {abs(t_ground-t_arr)/t_ground*100:.3f} % apart")
        print(f"   (both carry the ~1 % fixed-stencil metrication floor; "
              f"see spec/CORE-THEOREM.md section 4)")
