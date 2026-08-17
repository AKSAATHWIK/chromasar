"""The Co-Moving Reduction -- Theorem C.1.

Spec: spec/CORE-THEOREM.md. This module is the core of KAIROS; everything else in the
package is supporting apparatus.

The whole reduction collapses to one observation about data structures, not just about
mathematics: the shifted indicatrix

    V_w(y) = V_0(y) - w                                            (C.3)

is obtained by *subtracting w from the drift vector*, because every achievable ground
velocity is (V n(theta) + c) and shifting c by -w shifts the whole set by -w. So the
reduction needs no new metric code at all -- it wraps the environment field and lets the
existing RandersMetric / FinslerMetric run against it unchanged, on a field that is now
stationary.

Consequences implemented here:
  * the sweep is stationary   -> no causality condition, no wait relaxation  (Thm C.1b)
  * arrival is an interception root find                                     (Thm C.1c)
  * the ground route is the co-moving route plus w*tau                       (Thm C.1d)
"""
from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, replace
from typing import Callable, List, Optional, Sequence, Tuple

import numpy as np

from .geodesy import (haversine, heading_to_vec, initial_bearing,
                      metres_to_dlatlon, wrap_pi)
from .types import Env  # noqa: F401  (re-exported for callers)


# ============================================================ the co-moving field
class CoMovingField:
    """Presents a field's t_ref snapshot with the advection velocity removed.

    `at(lat, lon, t)` ignores `t` entirely -- that is the point. Under assumption A1 the
    pattern is the t_ref snapshot for all time, so the co-moving problem is autonomous and
    `L_t == 0` identically (spec Thm C.1b). Any metric built on this field is stationary.

    The advection `w` is given in m/s in the local east/north frame. It is subtracted from
    the current, which is exactly the indicatrix shift of Eq (C.3).
    """

    __slots__ = ("base", "w_e", "w_n", "t_ref")

    def __init__(self, base, w_east: float, w_north: float, t_ref: float = 0.0):
        self.base = base
        self.w_e = float(w_east)
        self.w_n = float(w_north)
        self.t_ref = float(t_ref)

    def at(self, lat: float, lon: float, t: float = 0.0) -> Env:
        e = self.base.at(lat, lon, self.t_ref)
        return replace(e, cu=e.cu - self.w_e, cv=e.cv - self.w_n)

    @property
    def t0(self) -> float:
        return self.t_ref

    @property
    def horizon(self) -> float:
        return float("inf")          # stationary: valid for all time

    def ground_position(self, lat: float, lon: float, t: float) -> Tuple[float, float]:
        """Map a co-moving point to its ground position at time t:  x = y + w t  (C.5)."""
        dlat, dlon = metres_to_dlatlon(lat, self.w_e * t, self.w_n * t)
        return lat + dlat, wrap_pi(lon + dlon)

    def comoving_position(self, lat: float, lon: float, t: float) -> Tuple[float, float]:
        """Inverse of `ground_position`:  y = x - w t."""
        dlat, dlon = metres_to_dlatlon(lat, -self.w_e * t, -self.w_n * t)
        return lat + dlat, wrap_pi(lon + dlon)


# ============================================================ choosing w  (Eq C.10)
def residual_causality_constant(field, sigma_fn: Callable, w: Tuple[float, float],
                                lats: Sequence[float], lons: Sequence[float],
                                times: Sequence[float], dirs: Sequence[Tuple[float, float]],
                                dt: float = 1800.0, pct: float = 99.0) -> float:
    """P_pct over the domain of  max_u |dF/dt|,  sampled at points fixed in the w-frame.

    This is the quantity Eq (C.10) minimises. The percentile rather than the max keeps one
    pathological cell from steering the choice of w -- measured in Test 8.10, where the max
    and the 99th percentile differ by enough to matter.
    """
    vals = []
    for la in lats:
        for lo in lons:
            worst = 0.0
            for t in times:
                F = []
                for sgn in (-1.0, +1.0):
                    tt = t + sgn * dt
                    dlat, dlon = metres_to_dlatlon(la, w[0] * tt, w[1] * tt)
                    e = field.at(la + dlat, wrap_pi(lo + dlon), tt)
                    best = 0.0
                    for u in dirs:
                        s = sigma_fn(e, u)
                        if s > 1e-6:
                            best = max(best, 1.0 / s)
                    F.append(best)
                worst = max(worst, abs(F[1] - F[0]) / (2.0 * dt))
            vals.append(worst)
    return float(np.percentile(np.array(vals), pct)) if vals else 0.0


def choose_advection(field, sigma_fn: Callable, lats, lons, times, dirs,
                     span: float = 4.0, n: int = 7, rounds: int = 3,
                     dt: float = 1800.0) -> Tuple[Tuple[float, float], float, float]:
    """Pick w by minimising the residual causality constant -- Eq (C.10).

    Returns (w, L_t_ground, L_t_comoving).

    NOT an estimate of the meteorological advection velocity, and must not be reported as
    one. Phase correlation was tried for that and failed badly (Test 8.10: it returned
    (-0.74, 0.00) against a true (2.0, 0.5)), because it locks onto whichever feature carries
    the most gradient energy rather than the one governing causality. Once assumption A1 is
    violated the two are different problems, and this is the one the solver needs.
    """
    base = residual_causality_constant(field, sigma_fn, (0.0, 0.0), lats, lons, times, dirs, dt)
    c = np.zeros(2)
    s = float(span)
    best = base
    for _ in range(rounds):
        bw = c.copy()
        for wx in np.linspace(c[0] - s, c[0] + s, n):
            for wy in np.linspace(c[1] - s, c[1] + s, n):
                v = residual_causality_constant(field, sigma_fn, (wx, wy),
                                                lats, lons, times, dirs, dt)
                if v < best:
                    best, bw = v, np.array([wx, wy])
        c = bw
        s = s * 2.0 / (n - 1)
    return (float(c[0]), float(c[1])), base, best


# ============================================================ the stationary sweep
NEIGHBOURS = [(-1, 0), (1, 0), (0, -1), (0, 1),
              (-1, -1), (-1, 1), (1, -1), (1, 1),
              (-2, -1), (-2, 1), (2, -1), (2, 1),
              (-1, -2), (-1, 2), (1, -2), (1, 2)]


@dataclass(slots=True)
class SweepResult:
    T: np.ndarray                 # arrival time per node, +inf where unreached
    parent: np.ndarray            # backpointer per node, -1 at the source
    expanded: int
    source: int


def stationary_sweep(grid, sigma_of, src_ij: Tuple[int, int],
                     max_expand: int = 5_000_000) -> SweepResult:
    """Single-pass label-setting sweep on a STATIONARY metric.

    `sigma_of(lat, lon, u) -> float` is speed made good over ground in unit direction
    `u = (east, north)`; return 0.0 for an infeasible direction.

    No causality condition is checked, and none is needed: Theorem C.1(b) makes the
    co-moving problem autonomous, so `L_t == 0` and the FIFO requirement of ERRATA (E4.1)
    holds vacuously. That is the whole point of the reduction.

    This is the Stage-1 solver of handbook M6: node-to-node Dijkstra on a 16-neighbour
    stencil. It is correct but carries the fixed-stencil metrication floor (~1 %, and it does
    NOT vanish under refinement -- measured in spec/CORE-THEOREM.md section 4). Upgrading the
    update to the continuum semi-Lagrangian form is an accuracy improvement orthogonal to the
    reduction, and is the next increment.
    """
    n_nodes = grid.n
    T = np.full(n_nodes, np.inf)
    parent = np.full(n_nodes, -1, dtype=np.int64)

    # Per-row geometry cache: leg length and bearing depend only on the row and the offset,
    # never on the column, so this is computed once per row.
    #
    # JREF is not 0. `Grid.latlon(i, j)` wraps a negative j like a Python list index, so
    # referencing from column 0 turns the westward offsets (dj < 0) into wrap-around legs --
    # measured at 4020 km instead of 57.9 km, with a bearing 142 degrees wrong. Referencing
    # from a column at least max|dj| from the edge keeps every offset in range.
    JREF = 2
    geom = {}

    def leg(i: int, k: int):
        row = geom.get(i)
        if row is None:
            row = []
            la, lo = grid.latlon(i, JREF)
            for di, dj in NEIGHBOURS:
                ni = i + di
                if not (0 <= ni < grid.nlat):
                    row.append(None)
                    continue
                nla, nlo = grid.latlon(ni, JREF + dj)
                d = haversine(la, lo, nla, nlo)
                b = initial_bearing(la, lo, nla, nlo)
                row.append((d, heading_to_vec(b)))
            geom[i] = row
        return row[k]

    s = grid.index(*src_ij)
    T[s] = 0.0
    pq = [(0.0, s)]
    expanded = 0

    while pq:
        t, node = heapq.heappop(pq)
        if t > T[node] + 1e-9:
            continue
        expanded += 1
        if expanded > max_expand:
            break
        i, j = grid.unindex(node)
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
            # sample at the segment midpoint; the field is stationary so there is no
            # temporal sampling error here at all (spec CORE-THEOREM section 4)
            sig = sigma_of(0.5 * (la + nla), 0.5 * (lo + nlo), u)
            if sig <= 1e-6:
                continue
            t2 = t + dist / sig
            m = grid.index(i2, j2)
            if t2 < T[m] - 1e-9:
                T[m] = t2
                parent[m] = node
                heapq.heappush(pq, (t2, m))

    return SweepResult(T=T, parent=parent, expanded=expanded, source=s)


# ============================================================ interception  (Eq C.4)
def interception_time(sweep: SweepResult, grid, comoving: CoMovingField,
                      dst_latlon: Tuple[float, float], t_max: float = 30 * 86400.0,
                      tol: float = 1.0) -> Optional[float]:
    """t* = min { t >= 0 : T_w(x_B - w t) <= t }   -- Theorem C.1(c), Eq (C.4).

    g(t) = T_w(x_B - w t) - t is continuous with g(0) > 0, and under assumption A2
    (|w| < sigma_min, the ship can outrun the system) g -> -inf, so a bisection is valid and
    the first zero is the optimum. The constraint is ACTIVE at t*, so the optimal route never
    loiters -- which is why no wait relaxation appears anywhere in this module.

    Returns None if no interception exists within t_max, which is the honest answer when
    A2 fails: the weather system cannot be outrun.
    """
    lat_b, lon_b = dst_latlon

    def T_at(t: float) -> float:
        y_lat, y_lon = comoving.comoving_position(lat_b, lon_b, t)
        try:
            i, j = grid.nearest(y_lat, y_lon)
        except Exception:
            return float("inf")
        if not (0 <= i < grid.nlat and 0 <= j < grid.nlon):
            return float("inf")
        return float(sweep.T[grid.index(i, j)])

    def g(t: float) -> float:
        v = T_at(t)
        return float("inf") if not math.isfinite(v) else v - t

    if g(0.0) <= 0.0:
        return 0.0
    hi = 3600.0
    while hi < t_max and g(hi) > 0.0:
        hi *= 1.7
    if g(hi) > 0.0:
        return None                      # A2 fails, or the target is unreachable
    lo = 0.0
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        if g(mid) > 0.0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# ============================================================ route recovery (Eq C.5)
def recover_ground_route(sweep: SweepResult, grid, comoving: CoMovingField,
                         y_goal_node: int) -> List[Tuple[float, float, float]]:
    """Backtrack the co-moving geodesic and map it to the ground frame.

    x(s) = y(s) + w * tau(s)  -- Eq (C.5). Verified to 9.77e-14 m/s in
    tests/comoving/test_c1_bijection.py.
    """
    chain = []
    n = int(y_goal_node)
    while n != -1:
        chain.append(n)
        n = int(sweep.parent[n])
    chain.reverse()

    out = []
    for n in chain:
        i, j = grid.unindex(n)
        y_lat, y_lon = grid.latlon(i, j)
        tau = float(sweep.T[n])
        x_lat, x_lon = comoving.ground_position(y_lat, y_lon, tau)
        out.append((x_lat, x_lon, tau))
    return out


def goal_node_for(grid, comoving: CoMovingField, dst_latlon: Tuple[float, float],
                  t_star: float, sweep: SweepResult, radius: int = 8) -> Tuple[int, float]:
    """The co-moving node whose MAPPED GROUND ARRIVAL is closest to x_B.

    Returns (node, miss_metres).

    Snapping y = x_B - w t* to the nearest grid node is not good enough. That node's own
    arrival time T[y] differs from t* by up to a cell's worth of transit, and the ground
    position is y + w*T[y], so the error is amplified by w: with |w| ~ 3 m/s and a half-cell
    timing error of ~2000 s the landfall moves by ~6 km per cell of snapping error. Measured
    at 104 km before this fix.

    So search a neighbourhood and minimise the quantity we actually care about -- the ground
    miss distance -- rather than the co-moving snapping error.
    """
    del t_star, radius          # kept in the signature for callers; see below

    # A neighbourhood search around y = x_B - w t* is NOT enough, and neither is the root
    # find that produces t*. Sampling T at the nearest node makes g(t) = T(x_B - w t) - t a
    # STEP function, so the bisection converges to a discontinuity rather than a root, and
    # T at the returned node can be far from t*. Measured: 104.5 km miss, unchanged by
    # widening the neighbourhood, because the offset is systematic rather than local.
    #
    # So solve the interception condition directly on the grid instead. Every node carries
    # its own arrival time, so every node has a well-defined ground landfall y + w*T[y];
    # pick the one closest to x_B. This IS Eq (C.4) evaluated exactly on the discretisation,
    # with no interpolation and no root find. O(N) with one haversine per node.
    best_node, best_miss = -1, float("inf")
    for n in range(grid.n):
        tau = float(sweep.T[n])
        if not math.isfinite(tau):
            continue
        i, j = grid.unindex(n)
        la, lo = grid.latlon(i, j)
        g_lat, g_lon = comoving.ground_position(la, lo, tau)
        miss = haversine(g_lat, g_lon, dst_latlon[0], dst_latlon[1])
        if miss < best_miss:
            best_miss, best_node = miss, n
    return best_node, best_miss


def required_dilation_m(comoving: CoMovingField, t_max: float) -> Tuple[float, float]:
    """How far the co-moving grid must extend BEYOND the ground domain, in metres.

    The solve happens in y = x - w t, so reaching a ground point x_B at time t requires the
    co-moving node y = x_B - w t to be IN THE GRID. Over a voyage of duration t_max the
    co-moving domain is displaced by w * t_max relative to the ground domain, opposite to w.

    This is not a subtlety, it is a hard requirement, and it fails silently: the sweep still
    converges, the route still looks plausible, and the landfall is simply wrong. Measured
    before this was understood: a 104.5 km miss that a full-grid scan could not reduce,
    because no node in the domain mapped anywhere near the target.

    Returns (east_m, north_m) -- extend the grid by this much in the direction OPPOSITE to
    each component of w (west/south for positive w).
    """
    return abs(comoving.w_e) * t_max, abs(comoving.w_n) * t_max
