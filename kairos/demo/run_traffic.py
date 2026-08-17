"""KAIROS applied to CITY TRAFFIC -- no ocean, no weather, no ships.

Why traffic is a legitimate instance of the same problem:

Lighthill-Whitham-Richards kinematic wave theory says congestion on a road propagates as a
SHOCKWAVE travelling at a characteristic speed -- typically 15-20 km/h, and usually UPSTREAM,
against the flow. The jam is not where it was an hour ago. So the cost field a driver faces
is an advected pattern, exactly like a weather system, and the same reduction applies:

    move with the jam, and the jam stops moving.

One structural difference worth noticing. In the ocean case the ground problem is already
anisotropic (currents push you). Here the ground problem is ISOTROPIC -- a car's speed limit
does not depend on which way it points. But after the co-moving substitution,

    y_dot = s(y)*n - w

the achievable set is a disc of radius s(y) centred at -w. So the reduction INTRODUCES an
apparent drift of -w, and the co-moving problem is anisotropic even though the original was
not. That is not a defect; it is the price of the frame change, and it is exactly the Randers
structure the ocean case has.

It also makes assumption A2 concrete and checkable here: we need s(y) > |w| everywhere, i.e.
traffic must move faster than the jam propagates. When it does not, the jam OVERTAKES you and
no route escapes it -- which is both physically true and the honest output.
"""
from __future__ import annotations

import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from kairos.core import (PlanarLattice, comoving_plan, required_bounds,
                         time_dependent_dijkstra)

# ---------------------------------------------------------------- the city
KMH = 1000.0 / 3600.0
FREE = 60.0 * KMH               # free-flow speed, m/s
JAM = 20.0 * KMH                # speed inside the jam, m/s
BLOCK = 200.0                   # block size, m

# The congestion shockwave: a diagonal band drifting south-west at ~11 km/h.
W = (-3.0, -1.0)                # m/s  -> |w| = 3.16 m/s = 11.4 km/h
BAND_POS = 9000.0               # where the band sits at t = 0 (along x+y)
BAND_W = 1400.0                 # band half-width, m

TRIP_FROM = (500.0, 500.0)
TRIP_TO = (11500.0, 11500.0)


def congestion(x, y):
    """Congestion intensity 0..1 at a point, IN THE CO-MOVING FRAME (stationary here)."""
    d = (x + y - BAND_POS) / math.sqrt(2.0)
    return math.exp(-(d * d) / (2.0 * BAND_W * BAND_W))


def local_speed(x, y):
    """Isotropic road speed. This is the ground-frame physics: no direction dependence."""
    return FREE - (FREE - JAM) * congestion(x, y)


# ---------------------------------------------------------------- the three planners
def speed_comoving(x, y, u):
    """Speed made good in the co-moving frame.

    The frame change turns the isotropic speed s into a disc centred at -w, so we must solve
    the same drift correction the ocean case uses. Returns 0 if the jam outruns us (A2 fails).
    """
    s = local_speed(x, y)
    dx, dy = -W[0], -W[1]                       # apparent drift
    c_par = dx * u[0] + dy * u[1]
    c_perp = -dx * u[1] + dy * u[0]
    r = s * s - c_perp * c_perp
    if r <= 0.0:
        return 0.0                              # A2 violated here: the wave overtakes us
    v = math.sqrt(r) + c_par
    return v if v > 1e-9 else 0.0


def speed_ground(x, y, u, t):
    """Ground frame: sample the advected congestion at absolute time t. Isotropic."""
    return local_speed(x - W[0] * t, y - W[1] * t)


def speed_frozen(x, y, u, t):
    """The naive thing everyone does: assume the jam stays where it is now."""
    return local_speed(x, y)


def summarise(name, plan, ref=None):
    if plan is None:
        print(f"  {name:38s} NO ROUTE")
        return
    extra = ""
    if ref is not None and ref > 0:
        extra = f"   {100*(plan.arrival-ref)/ref:+6.2f} % vs truth"
    print(f"  {name:38s} {plan.arrival/60:7.2f} min   {len(plan.route):4d} wpts   "
          f"expanded {plan.expanded:6d}   miss {plan.miss:6.0f} m{extra}")


if __name__ == "__main__":
    span = 12000.0
    nx = ny = int(span / BLOCK) + 1

    print("=" * 92)
    print("KAIROS on CITY TRAFFIC -- a congestion shockwave, not an ocean")
    print("=" * 92)
    print(f"city {span/1000:.0f} x {span/1000:.0f} km, {BLOCK:.0f} m blocks, {nx}x{ny} lattice")
    print(f"free flow {FREE/KMH:.0f} km/h, jam {JAM/KMH:.0f} km/h")
    print(f"shockwave velocity w = ({W[0]}, {W[1]}) m/s = {math.hypot(*W)/KMH:.1f} km/h "
          f"south-west")
    print(f"trip {TRIP_FROM} -> {TRIP_TO}  "
          f"({math.dist(TRIP_FROM, TRIP_TO)/1000:.1f} km straight line)")
    print(f"A2 check: jam speed {JAM:.2f} m/s  >  |w| {math.hypot(*W):.2f} m/s  -> "
          f"{'OK, traffic outruns the wave' if JAM > math.hypot(*W) else 'VIOLATED'}")
    print()

    # ---- ground truth: conventional time-dependent Dijkstra on the real moving field
    lat_ground = PlanarLattice(0.0, 0.0, nx, ny, BLOCK)
    t0 = time.perf_counter()
    truth = time_dependent_dijkstra(lat_ground, speed_ground, TRIP_FROM, TRIP_TO)
    el_t = time.perf_counter() - t0
    print("reference and baselines")
    summarise("time-dependent Dijkstra (truth)", truth)
    ref = truth.arrival if truth else None

    naive = time_dependent_dijkstra(lat_ground, speed_frozen, TRIP_FROM, TRIP_TO)
    summarise("frozen-field Dijkstra (naive)", naive, ref)

    # ---- KAIROS: the space must cover the co-moving sweep of the ground region.
    # Use required_bounds, NOT a magnitude-only dilation -- the direction depends on sign(w).
    t_max = 1.0 * 3600.0
    bx0, by0, bx1, by1 = required_bounds(0.0, 0.0, span, span, W, t_max)
    print()
    print(f"KAIROS co-moving reduction   (co-moving box "
          f"x {bx0/1000:.1f}..{bx1/1000:.1f} km, y {by0/1000:.1f}..{by1/1000:.1f} km "
          f"for a {t_max/3600:.0f} h horizon)")
    lat_co = PlanarLattice(bx0, by0,
                           int((bx1 - bx0) / BLOCK) + 1, int((by1 - by0) / BLOCK) + 1, BLOCK)
    t0 = time.perf_counter()
    co = comoving_plan(lat_co, speed_comoving, W, TRIP_FROM, TRIP_TO)
    el_c = time.perf_counter() - t0
    summarise("co-moving (stationary Dijkstra)", co, ref)

    # A*: available only because the problem is stationary. The heuristic is the exact
    # interception time at max speed -- admissible and consistent (core.intercept_lower_bound).
    t0 = time.perf_counter()
    co_a = comoving_plan(lat_co, speed_comoving, W, TRIP_FROM, TRIP_TO,
                         sigma_max=FREE, goal_tol=BLOCK)
    el_a = time.perf_counter() - t0
    summarise("co-moving + A* (heuristic)", co_a, ref)

    print()
    print(f"timing: truth {el_t:.3f} s ({truth.expanded} expanded) | "
          f"co-moving {el_c:.3f} s ({co.expanded}) | "
          f"co-moving+A* {el_a:.3f} s ({co_a.expanded})")
    if co and co_a:
        print(f"A* speedup vs plain co-moving: {el_c/max(el_a,1e-9):.1f}x wall clock, "
              f"{co.expanded/max(co_a.expanded,1):.1f}x fewer expansions")
        print(f"A* vs conventional time-dependent Dijkstra: "
              f"{el_t/max(el_a,1e-9):.2f}x  "
              f"({'FASTER' if el_a < el_t else 'slower'})")
    if truth and naive:
        print(f"cost of ignoring that the jam moves: "
              f"{100*(naive.arrival-truth.arrival)/truth.arrival:+.2f} %")
    print()
    print("-" * 92)
    print("Same core, same call signature as the ocean case. kairos.core knows nothing about")
    print("ships, weather, latitude or currents -- only a space, a speed field, and w.")
