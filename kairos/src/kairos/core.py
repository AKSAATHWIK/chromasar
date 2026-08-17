"""KAIROS core -- the domain-independent reduction.

This module knows nothing about ships, oceans, latitude or weather. It solves a general
problem:

    MINIMUM-TIME TRAVEL THROUGH A COST FIELD THAT TRANSLATES.

Given a space, a speed field that moves rigidly at velocity w, a start and a destination,
find the fastest route. The reduction converts it into an ORDINARY STATIONARY shortest-path
problem -- the kind Dijkstra, A* or fast marching already solve -- plus an interception.

    Ground frame:  x_dot = v,        v in V(x - w*t)      [cost field translates]
    Substitute     y = x - w*t   =>  y_dot = v - w,   v in V(y)

The right-hand side has no t in it. That is the whole theorem.

WHEN IT APPLIES
---------------
Two requirements, and the second is the one people miss:

  (1) The cost field is ADVECTED: it translates rigidly at some velocity w, at least to
      leading order. Weather systems, traffic shockwaves, wildfire fronts, tidal bores,
      contaminant plumes, moving interference sources.

  (2) The SPACE IS TRANSLATION-INVARIANT. In co-moving coordinates the space shifts, so
      unless shifting the space maps it onto itself, you have merely traded a moving cost
      field for a moving space and gained nothing.

      Works:        continuous space; regular lattices; a line (1-D corridor); any
                    statistically homogeneous medium.
      Does NOT work: an arbitrary irregular graph -- a real road network, a rail map, an
                    abstract graph with no embedding. There, use ordinary time-dependent
                    shortest path.

Requirement (2) is a genuine limit, not a caveat to be waved away. Check it before using this.

EXAMPLES THAT FIT
-----------------
  ships in weather          the original case
  aircraft in jet streams   jet cores translate for days
  UAVs / gliders in wind
  traffic on a grid city    LWR kinematic waves propagate at a characteristic speed
  wildfire evacuation       the fire front translates downwind
  AUVs in tidal flow
  search and rescue         the drifting target IS the moving frame
"""
from __future__ import annotations

import heapq
import math
from dataclasses import dataclass
from typing import Callable, List, Optional, Protocol, Sequence, Tuple

Vec2 = Tuple[float, float]


# ============================================================ the space
class Space(Protocol):
    """A translation-invariant discretisation of a planar region.

    Units are yours. Use metres and m/s, or kilometres and km/h, or city blocks and
    blocks/minute -- the algorithm only ever divides a distance by a speed, so any
    self-consistent pair works.
    """

    @property
    def n(self) -> int:
        """Number of nodes."""

    def position(self, node: int) -> Vec2:
        """(x, y) of a node. The embedding the translation acts on."""

    def nearest(self, x: float, y: float) -> int:
        """Node closest to a point."""

    def neighbours(self, node: int) -> Sequence[Tuple[int, float, Vec2]]:
        """(neighbour, distance, unit direction) triples."""

    def passable(self, node: int) -> bool:
        """False for obstacles."""


class PlanarLattice:
    """Regular rectangular lattice with configurable connectivity. The common case.

    A lattice is translation-invariant under shifts by whole cells; the reduction tolerates
    the sub-cell remainder as ordinary discretisation error.
    """

    # 16-way: reduces the direction quantisation of an 8-way lattice. Note this quantisation
    # does NOT vanish under refinement -- see the note in comoving_plan.
    OFFSETS16 = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1),
                 (-2, -1), (-2, 1), (2, -1), (2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2)]
    OFFSETS8 = OFFSETS16[:8]

    def __init__(self, x0: float, y0: float, nx: int, ny: int, h: float,
                 offsets=None, passable_fn: Optional[Callable[[float, float], bool]] = None):
        self.x0, self.y0, self.nx, self.ny, self.h = x0, y0, nx, ny, h
        self.offsets = list(offsets if offsets is not None else self.OFFSETS16)
        self._blocked = [False] * (nx * ny)
        if passable_fn is not None:
            for k in range(nx * ny):
                self._blocked[k] = not passable_fn(*self.position(k))
        # Precompute geometry once: on a lattice it is identical at every node, so this is a
        # single table rather than a per-node computation.
        self._geom = []
        for dx, dy in self.offsets:
            d = math.hypot(dx * h, dy * h)
            self._geom.append((d, (dx * h / d, dy * h / d)))

    @property
    def n(self) -> int:
        return self.nx * self.ny

    def ij(self, node: int) -> Tuple[int, int]:
        return divmod(node, self.ny)

    def index(self, i: int, j: int) -> int:
        return i * self.ny + j

    def position(self, node: int) -> Vec2:
        i, j = self.ij(node)
        return self.x0 + i * self.h, self.y0 + j * self.h

    def nearest(self, x: float, y: float) -> int:
        i = min(self.nx - 1, max(0, int(round((x - self.x0) / self.h))))
        j = min(self.ny - 1, max(0, int(round((y - self.y0) / self.h))))
        return self.index(i, j)

    def passable(self, node: int) -> bool:
        return not self._blocked[node]

    def neighbours(self, node: int):
        i, j = self.ij(node)
        out = []
        for k, (di, dj) in enumerate(self.offsets):
            i2, j2 = i + di, j + dj
            if 0 <= i2 < self.nx and 0 <= j2 < self.ny:
                m = self.index(i2, j2)
                if not self._blocked[m]:
                    d, u = self._geom[k]
                    out.append((m, d, u))
        return out


# ============================================================ results
@dataclass(slots=True)
class Plan:
    route: List[Tuple[float, float, float]]   # (x, y, time)
    arrival: float
    miss: float                                # distance from the requested destination
    expanded: int
    reached: int


# ============================================================ the reduction
def intercept_lower_bound(ax: float, ay: float, w: Vec2, sigma_max: float) -> float:
    """Exact minimum time to intercept a target drifting at -w, from relative offset a,
    when the pursuer's speed is bounded by sigma_max. Returns +inf if it cannot be caught.

    THE ADMISSIBLE HEURISTIC. This is what makes A* possible on the co-moving problem, and it
    is available ONLY because the problem is stationary -- a time-dependent solver has no
    comparable closed form.

    Derivation. From node y at time t we must reach x_B - w*t' at some t' = t + D. Writing
    a = x_B - y - w*t for the target's current relative position, the reachability condition is

        |a - w*D|  <=  sigma_max * D

    Squaring and collecting gives (|w|^2 - s^2) D^2 - 2<a,w> D + |a|^2 <= 0. Under assumption
    A2 (|w| < sigma_max) the leading coefficient is negative, so the feasible set is D >= D_min
    with D_min the positive root:

        D_min = [ sqrt(<a,w>^2 + (s^2 - |w|^2)|a|^2) - <a,w> ] / (s^2 - |w|^2)

    which is exactly the Randers metric with drift w and speed s -- the same closed form the
    ocean metric uses, arrived at independently. It is a lower bound because the true speed
    never exceeds sigma_max, hence admissible; and it is a metric-derived bound, hence
    consistent, so A* finalises nodes correctly with no reopening.

    Numerically stable: the subtraction cancels when <a,w> > 0, so use the conjugate form
    there, exactly as in the metric itself.
    """
    lam = sigma_max * sigma_max - (w[0] * w[0] + w[1] * w[1])
    if lam <= 0.0:
        return math.inf                       # A2 violated: the target cannot be caught
    aw = ax * w[0] + ay * w[1]
    a2 = ax * ax + ay * ay
    if a2 <= 0.0:
        return 0.0
    disc = math.sqrt(aw * aw + lam * a2)
    if aw > 0.0:
        return a2 / (disc + aw)               # conjugate branch, avoids cancellation
    return (disc - aw) / lam


def comoving_plan(space: Space,
                  speed: Callable[[float, float, Vec2], float],
                  w: Vec2,
                  src: Vec2,
                  dst: Vec2,
                  t0: float = 0.0,
                  sigma_max: Optional[float] = None,
                  goal_tol: Optional[float] = None,
                  precompute: bool = False) -> Optional[Plan]:
    """Minimum-time route through a cost field translating at velocity `w`.

    Args:
      space : any Space. Must be translation-invariant -- see the module docstring.
      speed : speed(x, y, u) -> speed made good in unit direction u, evaluated in the
              CO-MOVING frame (i.e. the field as seen by an observer drifting with it).
              Return 0.0 for impassable. This is the only physics the core knows.
      w     : the cost field's translation velocity, same units as `speed`.
      src   : (x, y) start, in ground coordinates at time t0.
      dst   : (x, y) destination, in ground coordinates. FIXED IN THE GROUND FRAME, which
              is why it appears to move in the co-moving frame -- hence the interception.

    Returns a Plan, or None if the destination is unreachable.

    THREE THINGS THAT SILENTLY GO WRONG (all measured during development):

      1. The space must be DILATED by |w| * t_max opposite to w. The solve lives in
         y = x - w*t, so the target node y = dst - w*t* must exist. Undersized, this fails
         silently with a plausible route and a wrong landfall. Use `required_dilation`.
      2. Do NOT find the arrival time by bisecting g(t) = T(dst - w*t) - t. Sampling T at a
         node makes g a STEP function, so bisection lands on a discontinuity. Solve the
         interception directly over nodes, as below.
      3. Guard the speed function: return 0, never a negative or a NaN. A negative edge cost
         creates negative cycles and the search will not terminate.
    """
    # ---- stationary solve. No time in the state, no causality condition, because after the
    # ---- substitution there is no time dependence left.
    # ----
    # ---- With sigma_max supplied this is A*: the heuristic of intercept_lower_bound() is
    # ---- admissible and consistent, and it lets the search stop as soon as a node's ground
    # ---- landfall is within goal_tol. Without it, plain Dijkstra over the whole domain.
    src_node = space.nearest(*src)
    INF = math.inf
    T = [INF] * space.n
    parent = [-1] * space.n
    T[src_node] = 0.0
    expanded = 0
    use_astar = sigma_max is not None and sigma_max > 0.0

    # ---- optional: tabulate the speed field once.
    #
    # This is available ONLY because the co-moving field is stationary. A time-dependent
    # solver must re-evaluate at a different time on every edge relaxation, and with real
    # forecast data that is a trilinear interpolation into a 4-D array each time. Here the
    # field is evaluated once per (node, neighbour) and thereafter read from a list.
    #
    # Worth it when field evaluation is expensive relative to the heap operations, which is
    # the realistic case; pure overhead when the field is a cheap analytic function.
    table = None
    if precompute:
        table = [None] * space.n
        for nd in range(space.n):
            x, y = space.position(nd)
            row = []
            for m, dist, u in space.neighbours(nd):
                mx, my = space.position(m)
                row.append((m, dist, speed(0.5 * (x + mx), 0.5 * (y + my), u)))
            table[nd] = row

    def h_of(node: int, tau: float) -> float:
        if not use_astar:
            return 0.0
        x, y = space.position(node)
        # target's position relative to this node, at this node's arrival time
        return intercept_lower_bound(dst[0] - w[0] * tau - x,
                                     dst[1] - w[1] * tau - y, w, sigma_max)

    def landfall_miss(node: int, tau: float) -> float:
        x, y = space.position(node)
        return math.hypot(x + w[0] * tau - dst[0], y + w[1] * tau - dst[1])

    pq = [(h_of(src_node, 0.0), 0.0, src_node)]
    best, best_miss = -1, INF

    while pq:
        _, t, node = heapq.heappop(pq)
        if t > T[node] + 1e-12:
            continue
        expanded += 1

        # goal test on POP, not on push: with a consistent heuristic the first pop that
        # satisfies it is optimal.
        if use_astar:
            miss = landfall_miss(node, t)
            if miss < best_miss:
                best_miss, best = miss, node
            if goal_tol is not None and miss <= goal_tol:
                break

        if table is not None:
            for m, dist, s in table[node]:
                if s <= 0.0:
                    continue
                nt = t + dist / s
                if nt < T[m] - 1e-12:
                    T[m] = nt
                    parent[m] = node
                    f = nt + h_of(m, nt)
                    if f < INF:
                        heapq.heappush(pq, (f, nt, m))
        else:
            x, y = space.position(node)
            for m, dist, u in space.neighbours(node):
                mx, my = space.position(m)
                s = speed(0.5 * (x + mx), 0.5 * (y + my), u)
                if s <= 0.0:
                    continue
                nt = t + dist / s
                if nt < T[m] - 1e-12:
                    T[m] = nt
                    parent[m] = node
                    f = nt + h_of(m, nt)
                    if f < INF:
                        heapq.heappush(pq, (f, nt, m))

    # ---- interception: in the co-moving frame the destination MOVES, tracing
    # ---- y(t) = dst - w*t. Every node carries its own arrival time, hence its own ground
    # ---- landfall y + w*T[y]. Take the node whose landfall is closest to dst.
    # ---- Under Dijkstra this is an O(n) scan; under A* the incumbent is already tracked.
    if not use_astar:
        for node in range(space.n):
            tau = T[node]
            if tau == INF:
                continue
            x, y = space.position(node)
            miss = math.hypot(x + w[0] * tau - dst[0], y + w[1] * tau - dst[1])
            if miss < best_miss:
                best_miss, best = miss, node
    if best < 0:
        return None

    # ---- recover: backtrack in the co-moving frame, map each waypoint to the ground
    chain, node = [], best
    while node != -1:
        chain.append(node)
        node = parent[node]
    chain.reverse()
    route = []
    for node in chain:
        x, y = space.position(node)
        tau = T[node]
        route.append((x + w[0] * tau, y + w[1] * tau, t0 + tau))

    return Plan(route=route, arrival=t0 + T[best], miss=best_miss,
                expanded=expanded, reached=sum(1 for v in T if v < INF))


def required_bounds(x0: float, y0: float, x1: float, y1: float,
                    w: Vec2, t_max: float) -> Tuple[float, float, float, float]:
    """The co-moving bounding box that MUST be covered, given a ground region and a horizon.

    Returns (x_min, y_min, x_max, y_max).

    The solve lives in y = x - w*t, so as t runs over [0, t_max] every ground point sweeps a
    segment in co-moving space. The domain must contain all of them.

    THE DIRECTION DEPENDS ON THE SIGN OF w, and getting this wrong fails silently. An earlier
    version of this function returned only the magnitude |w|*t_max and left the caller to
    extend "opposite to w"; that is correct for w > 0 and WRONG for w < 0. Measured cost of
    the mistake on a traffic case with w = (-3, -1) m/s: the required node lay outside the
    lattice, the search still converged, and the route landed 2649 m from the destination
    while reporting an arrival 11 % faster than truth -- because it had quietly solved for a
    different destination.

    Computing the box directly from the corner sweeps, as below, is sign-safe by construction.
    """
    xs = (x0, x1, x0 - w[0] * t_max, x1 - w[0] * t_max)
    ys = (y0, y1, y0 - w[1] * t_max, y1 - w[1] * t_max)
    return min(xs), min(ys), max(xs), max(ys)


def required_dilation(w: Vec2, t_max: float) -> Vec2:
    """DEPRECATED -- magnitude only, and therefore sign-unsafe. Use `required_bounds`."""
    return abs(w[0]) * t_max, abs(w[1]) * t_max


# ============================================================ the baseline, for comparison
def time_dependent_dijkstra(space: Space,
                            speed_at_time: Callable[[float, float, Vec2, float], float],
                            src: Vec2, dst: Vec2, t0: float = 0.0) -> Optional[Plan]:
    """Conventional time-dependent Dijkstra, for comparison.

    `speed_at_time(x, y, u, t)` samples the field at absolute time t. Correct only when the
    FIFO condition holds (leaving later never lets you arrive earlier); the co-moving solve
    needs no such condition because it has no time dependence to violate it.
    """
    src_node = space.nearest(*src)
    dst_node = space.nearest(*dst)
    INF = math.inf
    T = [INF] * space.n
    parent = [-1] * space.n
    T[src_node] = t0
    pq = [(t0, src_node)]
    expanded = 0
    while pq:
        t, node = heapq.heappop(pq)
        if t > T[node] + 1e-12:
            continue
        expanded += 1
        x, y = space.position(node)
        for m, dist, u in space.neighbours(node):
            mx, my = space.position(m)
            s = speed_at_time(0.5 * (x + mx), 0.5 * (y + my), u, t)   # DEPARTURE time
            if s <= 0.0:
                continue
            nt = t + dist / s
            if nt < T[m] - 1e-12:
                T[m] = nt
                parent[m] = node
                heapq.heappush(pq, (nt, m))
    if T[dst_node] == INF:
        return None
    chain, node = [], dst_node
    while node != -1:
        chain.append(node)
        node = parent[node]
    chain.reverse()
    route = [(*space.position(nd), T[nd]) for nd in chain]
    return Plan(route=route, arrival=T[dst_node], miss=0.0, expanded=expanded,
                reached=sum(1 for v in T if v < INF))
