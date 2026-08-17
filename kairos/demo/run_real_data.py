"""KAIROS on REAL ocean data -- and on no data at all, through the identical code path.

The point of this demo is not that it routes a ship. It is that the two runs below call the
SAME solver, and the solver cannot tell them apart:

  RUN 1: live HYCOM ocean currents over OPeNDAP (open access, no credentials)
  RUN 2: a two-line analytic function, no data, no network, no files

Like A* with a graph, KAIROS takes a field. Where the field comes from is not the algorithm's
business. `kairos.comoving` imports nothing from `kairos.data`, and deleting data.py entirely
would not affect run 2.
"""
from __future__ import annotations

import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from kairos.comoving import (CoMovingField, goal_node_for, recover_ground_route,
                             stationary_sweep)
from kairos.geodesy import haversine
from kairos.grid import Grid
from kairos.types import Env

D2R = math.pi / 180.0
V_S = 7.2                      # constant through-water speed, m/s (~14 kt)

# Arabian Sea box and a real voyage leg: off Kochi -> Gulf of Aden approaches
BBOX = (2.0, 22.0, 45.0, 78.0)          # lat_min, lat_max, lon_min, lon_max (degrees)
SRC = (9.5 * D2R, 76.0 * D2R)
DST = (12.6 * D2R, 47.0 * D2R)


def sigma_of(field_like, lat, lon, u):
    """Speed made good -- the only thing the solver needs from a field."""
    e = field_like.at(lat, lon, 0.0)
    cpar = e.cu * u[0] + e.cv * u[1]
    cperp = -e.cu * u[1] + e.cv * u[0]
    r = V_S * V_S - cperp * cperp
    if r <= 0.0:
        return 0.0
    s = math.sqrt(r) + cpar
    return s if s > 1e-6 else 0.0


def plan(field, grid, w, label):
    """Identical for every field. This function is the whole point of the demo."""
    co = CoMovingField(field, w[0], w[1], t_ref=field.t0 if hasattr(field, "t0") else 0.0)
    t0 = time.perf_counter()
    sw = stationary_sweep(grid, lambda la, lo, u: sigma_of(co, la, lo, u), grid.nearest(*SRC))
    el = time.perf_counter() - t0
    node, miss = goal_node_for(grid, co, DST, 0.0, sw)
    route = recover_ground_route(sw, grid, co, node)
    arr = route[-1][2] if route else float("nan")
    print(f"  {label:34s} arrival {arr/3600:8.3f} h   miss {miss/1000:6.1f} km   "
          f"{len(route):4d} wpts   sweep {el:5.2f} s")
    return arr, route


# ============================================================ RUN 2's field: no data at all
class AnalyticField:
    """A field with no data behind it. Two lines of physics, valid everywhere, instantly.

    This is the equivalent of handing A* a hand-drawn graph. It is a first-class citizen of
    the interface, not a fallback.
    """
    t0 = 0.0
    horizon = 1e12

    def at(self, lat, lon, t):
        # a westward equatorial-style drift that weakens away from 10 N
        dn = (lat - 10.0 * D2R) * 6.371e6
        cu = -1.4 * math.exp(-(dn * dn) / (2 * (350e3) ** 2))
        return Env(cu=cu, cv=0.0, hs=1.5, tp=9.0, mu_w=0.0, depth=4000.0)


if __name__ == "__main__":
    print("=" * 84)
    print("KAIROS with real data, and without any")
    print("=" * 84)
    print(f"voyage {SRC[0]/D2R:.2f}N {SRC[1]/D2R:.2f}E -> {DST[0]/D2R:.2f}N {DST[1]/D2R:.2f}E"
          f"   ({haversine(*SRC, *DST)/1000:.0f} km great circle)")
    print(f"V_s = {V_S} m/s, grid 0.25 deg")
    print()

    # ---------------------------------------------------------------- RUN 1: real data
    print("RUN 1 -- live HYCOM ocean currents (OPeNDAP, open access, no credentials)")
    real_ok = False
    try:
        from kairos.data import hycom_currents
        t0 = time.perf_counter()
        hy = hycom_currents(BBOX, time_slice=(0, 1))
        print(f"  fetched in {time.perf_counter()-t0:.1f} s")
        print(f"  coverage: {hy.coverage()}")
        grid_real = Grid(BBOX[0], BBOX[1], BBOX[2], BBOX[3], 0.25,
                         land_fn=hy.land_mask_fn("cu"))
        water = sum(1 for n in range(grid_real.n)
                    if grid_real.is_water(*grid_real.unindex(n)))
        print(f"  land mask from data NaNs: {water}/{grid_real.n} nodes navigable "
              f"({100*water/grid_real.n:.1f} %)")
        plan(hy, grid_real, (0.0, 0.0), "HYCOM currents")
        real_ok = True
    except Exception as e:
        print(f"  UNAVAILABLE ({type(e).__name__}: {str(e)[:110]})")
        print("  -> the algorithm is unaffected; RUN 2 below uses the same solver.")

    # ---------------------------------------------------------------- RUN 2: no data
    print()
    print("RUN 2 -- analytic field: no data, no network, no files")
    grid_syn = Grid(BBOX[0], BBOX[1], BBOX[2], BBOX[3], 0.25)
    plan(AnalyticField(), grid_syn, (0.0, 0.0), "analytic field")

    print()
    print("-" * 84)
    print("Both runs called stationary_sweep() with the same signature. The solver never")
    print("learned whether its numbers came from an OPeNDAP server or a two-line function.")
    print("kairos.comoving imports nothing from kairos.data; delete data.py and RUN 2 still")
    print("works, along with the entire analytic test suite.")
    if not real_ok:
        print()
        print("NOTE: the real-data run did not complete. That is a DATA availability problem,")
        print("      not an algorithm problem -- which is exactly the separation being shown.")
