"""Time-dependent multi-objective ship routing.

The core difficulty: edge cost depends on WHEN you traverse the edge, because the
weather forecast evolves during the voyage. That breaks ordinary shortest-path, so the
search state carries time as well as position.

Implemented here: time-dependent A* with an admissible heuristic, plus a weight sweep
that recovers the Pareto front across (time, fuel, risk).
"""
from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field

from forcing import haversine_km, initial_bearing
from ship import transit

try:
    from global_land_mask import globe
    _HAS_LAND = True
except ImportError:                                              # pragma: no cover
    _HAS_LAND = False


@dataclass
class Grid:
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float
    step: float = 0.5

    def __post_init__(self):
        self.nlat = int(round((self.lat_max - self.lat_min) / self.step)) + 1
        self.nlon = int(round((self.lon_max - self.lon_min) / self.step)) + 1
        self._land = [[False] * self.nlon for _ in range(self.nlat)]
        if _HAS_LAND:
            for i in range(self.nlat):
                for j in range(self.nlon):
                    la, lo = self.latlon(i, j)
                    self._land[i][j] = bool(globe.is_land(la, lo))

        # Edge geometry depends only on the latitude ROW and the neighbour offset -
        # never on longitude, time, or search state. Precomputing it removes millions
        # of redundant haversine/bearing calls from the inner loop.
        self._geom = {}
        for i in range(self.nlat):
            la, lo = self.latlon(i, 0)
            row = []
            for di, dj in NEIGHBOURS:
                ni = i + di
                if not (0 <= ni < self.nlat):
                    row.append(None)
                    continue
                nla, nlo = self.latlon(ni, dj)
                row.append((haversine_km(la, lo, nla, nlo),
                            initial_bearing(la, lo, nla, nlo)))
            self._geom[i] = row

    def edge(self, i, k):
        """(distance_km, bearing_deg) for neighbour k from any node in row i."""
        return self._geom[i][k]

    def latlon(self, i, j):
        return self.lat_min + i * self.step, self.lon_min + j * self.step

    def nearest(self, lat, lon):
        i = min(self.nlat - 1, max(0, int(round((lat - self.lat_min) / self.step))))
        j = min(self.nlon - 1, max(0, int(round((lon - self.lon_min) / self.step))))
        return i, j

    def is_water(self, i, j):
        return 0 <= i < self.nlat and 0 <= j < self.nlon and not self._land[i][j]

    def water_near(self, lat, lon, radius=6):
        """Snap a port to the closest navigable grid node."""
        i0, j0 = self.nearest(lat, lon)
        if self.is_water(i0, j0):
            return i0, j0
        best, bestd = None, 1e18
        for di in range(-radius, radius + 1):
            for dj in range(-radius, radius + 1):
                i, j = i0 + di, j0 + dj
                if self.is_water(i, j):
                    la, lo = self.latlon(i, j)
                    d = haversine_km(lat, lon, la, lo)
                    if d < bestd:
                        best, bestd = (i, j), d
        if best is None:
            raise ValueError(f"no water within {radius} cells of ({lat}, {lon})")
        return best


# 16-way connectivity: reduces the zig-zag artefacts of an 8-way grid
NEIGHBOURS = [(-1, 0), (1, 0), (0, -1), (0, 1),
              (-1, -1), (-1, 1), (1, -1), (1, 1),
              (-2, -1), (-2, 1), (2, -1), (2, 1),
              (-1, -2), (-1, 2), (1, -2), (1, 2)]


@dataclass(order=True)
class _Node:
    f: float
    counter: int
    state: tuple = field(compare=False)
    g: float = field(default=0.0, compare=False)
    t: float = field(default=0.0, compare=False)
    fuel: float = field(default=0.0, compare=False)
    risk: float = field(default=0.0, compare=False)
    parent: object = field(default=None, compare=False)


@dataclass
class RouteResult:
    waypoints: list          # [(lat, lon, t_hours)]
    hours: float
    fuel_t: float
    max_risk: float
    mean_risk: float
    expanded: int
    weights: tuple

    def summary(self):
        return (f"{self.hours:6.1f} h | {self.fuel_t:7.1f} t | "
                f"peak risk {self.max_risk:.2f} | {len(self.waypoints)} wpts "
                f"| {self.expanded} nodes expanded")


def astar(grid, ship, forcing, start, goal, w_time=1.0, w_fuel=0.0, w_risk=0.0,
          depart_h=0.0, time_bucket_h=3.0, max_expand=400_000):
    """Time-dependent A*.

    Cost = w_time * hours + w_fuel * fuel_tonnes + w_risk * (risk * hours).
    The heuristic lower-bounds remaining cost using the best physically possible speed
    and the cheapest possible fuel rate, so it never overestimates and A* stays optimal
    on the discretised graph.
    """
    si, sj = grid.water_near(*start)
    gi, gj = grid.water_near(*goal)
    glat, glon = grid.latlon(gi, gj)

    # --- admissible heuristic constants -------------------------------
    max_sog_kmh = (ship.max_speed_kts + 3.0) * 1.852       # + generous current help
    min_fuel_per_h = ship.calm_power(ship.service_speed_kts * 0.6) * ship.sfoc_t_per_kwh
    cost_per_h_lb = w_time + w_fuel * min_fuel_per_h       # risk >= 0, so omitted

    _hcache = {}

    def h(i, j):
        v = _hcache.get((i, j))
        if v is None:
            la, lo = grid.latlon(i, j)
            v = (haversine_km(la, lo, glat, glon) / max_sog_kmh) * cost_per_h_lb
            _hcache[(i, j)] = v
        return v

    counter = 0
    start_node = _Node(h(si, sj), counter, (si, sj, 0), 0.0, depart_h, 0.0, 0.0, None)
    open_heap = [start_node]
    best = {}
    expanded = 0

    while open_heap:
        cur = heapq.heappop(open_heap)
        i, j, _ = cur.state
        if (i, j) == (gi, gj):
            return _build(cur, grid, w_time, w_fuel, w_risk, expanded)
        if best.get(cur.state, math.inf) < cur.g - 1e-12:
            continue
        expanded += 1
        if expanded > max_expand:
            break

        la, lo = grid.latlon(i, j)
        for k, (di, dj) in enumerate(NEIGHBOURS):
            ni, nj = i + di, j + dj
            if not grid.is_water(ni, nj):
                continue
            geom = grid.edge(i, k)
            if geom is None:
                continue
            dist, brg = geom
            nla, nlo = grid.latlon(ni, nj)
            # sample forcing at the segment midpoint, at the time we are there
            cond = forcing.at((la + nla) / 2, (lo + nlo) / 2, cur.t)
            out = transit(ship, brg, dist, cond)
            if out is None:
                continue                                   # unsafe or unreachable
            hours, fuel, risk = out
            g2 = cur.g + w_time * hours + w_fuel * fuel + w_risk * risk * hours
            t2 = cur.t + hours
            state2 = (ni, nj, int(t2 / time_bucket_h))
            if g2 >= best.get(state2, math.inf) - 1e-12:
                continue
            best[state2] = g2
            counter += 1
            heapq.heappush(open_heap, _Node(
                g2 + h(ni, nj), counter, state2, g2, t2,
                cur.fuel + fuel, max(cur.risk, risk), cur))

    return None


def _build(node, grid, w_time, w_fuel, w_risk, expanded):
    pts, risks = [], []
    n = node
    while n is not None:
        i, j, _ = n.state
        la, lo = grid.latlon(i, j)
        pts.append((la, lo, n.t))
        risks.append(n.risk)
        n = n.parent
    pts.reverse()
    return RouteResult(pts, node.t - pts[0][2], node.fuel, node.risk,
                       sum(risks) / len(risks), expanded, (w_time, w_fuel, w_risk))


def great_circle_route(grid, ship, forcing, start, goal, depart_h=0.0, n_steps=140):
    """Baseline: sail the great circle regardless of weather, and pay for it.

    This is what we compare against, so the saving we quote is measured, not asserted.
    Returns None if the naive route is actually unnavigable - itself a useful result.
    """
    si, sj = grid.water_near(*start)
    gi, gj = grid.water_near(*goal)
    lat1, lon1 = grid.latlon(si, sj)
    lat2, lon2 = grid.latlon(gi, gj)

    pts = []
    for k in range(n_steps + 1):
        f = k / n_steps
        pts.append((lat1 + (lat2 - lat1) * f, lon1 + (lon2 - lon1) * f))

    t = depart_h
    fuel = 0.0
    peak = 0.0
    risks = []
    out_pts = [(pts[0][0], pts[0][1], t)]
    for a, b in zip(pts, pts[1:]):
        dist = haversine_km(a[0], a[1], b[0], b[1])
        if dist < 1e-6:
            continue
        brg = initial_bearing(a[0], a[1], b[0], b[1])
        cond = forcing.at((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, t)
        res = transit(ship, brg, dist, cond)
        if res is None:
            # naive route sails into conditions beyond the ship's limit
            return None
        hours, f_used, risk = res
        t += hours
        fuel += f_used
        peak = max(peak, risk)
        risks.append(risk)
        out_pts.append((b[0], b[1], t))
    return RouteResult(out_pts, t - depart_h, fuel, peak,
                       sum(risks) / len(risks), 0, ("great-circle",))


def grid_line_route(grid, ship, forcing, start, goal, depart_h=0.0):
    """Baseline constrained to the SAME graph the optimiser uses.

    Walks grid nodes along the straight line in index space. This is the fair
    comparison: any saving we quote is then attributable to routing decisions, not to
    one method being allowed finer geometry than the other.
    """
    si, sj = grid.water_near(*start)
    gi, gj = grid.water_near(*goal)
    n = max(abs(gi - si), abs(gj - sj))
    if n == 0:
        return None
    nodes = []
    for k in range(n + 1):
        f = k / n
        i = int(round(si + (gi - si) * f))
        j = int(round(sj + (gj - sj) * f))
        if not nodes or nodes[-1] != (i, j):
            nodes.append((i, j))
    if any(not grid.is_water(i, j) for i, j in nodes):
        return None                      # straight line crosses land

    t, fuel, peak, risks = depart_h, 0.0, 0.0, []
    pts = [(*grid.latlon(*nodes[0]), t)]
    for a, b in zip(nodes, nodes[1:]):
        la, lo = grid.latlon(*a)
        nla, nlo = grid.latlon(*b)
        dist = haversine_km(la, lo, nla, nlo)
        brg = initial_bearing(la, lo, nla, nlo)
        cond = forcing.at((la + nla) / 2, (lo + nlo) / 2, t)
        res = transit(ship, brg, dist, cond)
        if res is None:
            return None
        hours, f_used, risk = res
        t += hours
        fuel += f_used
        peak = max(peak, risk)
        risks.append(risk)
        pts.append((nla, nlo, t))
    return RouteResult(pts, t - depart_h, fuel, peak,
                       sum(risks) / len(risks), 0, ("grid-straight",))


def pareto_sweep(grid, ship, forcing, start, goal, depart_h=0.0, weights=None):
    """Run the router across several objective weightings and keep non-dominated routes.

    The PS is explicit that fuel, time and safety trade off against each other, so the
    honest output is a set of choices, not a single 'optimal' route.
    """
    if weights is None:
        weights = [(1.0, 0.0, 0.0),      # pure speed
                   (1.0, 0.4, 0.0),
                   (1.0, 1.2, 0.0),      # fuel-leaning
                   (1.0, 0.4, 8.0),      # safety-conscious
                   (1.0, 1.2, 20.0)]     # safety-first
    routes = []
    for w in weights:
        r = astar(grid, ship, forcing, start, goal, *w, depart_h=depart_h)
        if r:
            routes.append(r)

    keep = []
    for r in routes:
        dominated = any(
            (o.hours <= r.hours and o.fuel_t <= r.fuel_t and o.max_risk <= r.max_risk)
            and (o.hours < r.hours or o.fuel_t < r.fuel_t or o.max_risk < r.max_risk)
            for o in routes if o is not r)
        if not dominated:
            keep.append(r)
    return routes, keep
