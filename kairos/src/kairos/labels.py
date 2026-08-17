"""The eps-Pareto label algebra.

Spec reference: CONTRACT.md section 3 decision D1, and section 5 (Thm 5.2, Thm 5.3,
Prop 5.4).

The solver carries vector-valued labels because throttle is a free control (D1): a
direction does not have *a* cost, it has a one-parameter family of (time, fuel, risk)
triples. This module is the order structure on those triples -- what dominates what, how a
cost accumulates across a leg, and which labels a node is allowed to remember. It knows
nothing about geometry, the metric, or the queue; it is pure algebra over cost tuples, and
it is the only place where the approximation in "eps-Pareto" is introduced.

Two discretisation decisions are load-bearing and are argued in place:

  * additive objectives are bucketed on the accumulated VALUE, geometrically
    (`_geometric_index`), which is what makes the guarantee a clean (1+eps) instead of
    (1+eps)^D in the number of legs -- see `LabelSet.bucket_key`;

  * MAX-accumulated objectives are bucketed uniformly, not geometrically, because a
    running maximum is drawn from the finite set of edge levels and its meaningful
    differences are absolute -- see `LabelSet.bucket_key`.

Everything is deterministic. Determinism is not tidiness: Thm 3.1's causality argument and
the reproducibility of a reported route both assume that re-running the sweep on the same
input retains the same labels, so every tie is broken by a stated total order and never by
insertion order or object identity.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterator, Optional, Sequence, Tuple

from .types import Accum, Leg, ObjectiveSpec

# Characteristic scale of a MAX-accumulated objective. `Leg.risk_level` is a dimensionless
# index of order 1 (types.py), so an absolute bucket width of eps*1.0 is the natural grid.
# An unnormalised bottleneck objective must be rescaled before it reaches this module; that
# limitation is real and is restated in LabelSet.bucket_key.
MAX_OBJECTIVE_SCALE = 1.0

# How far up the parent chain the final tie-break looks. Reached only when two labels agree
# on cost, time, node, heading and throttle, i.e. essentially never; the bound exists so a
# corrupted parent cycle cannot hang the comparison.
_CHAIN_SIG_DEPTH = 8


# ============================================================================ label
@dataclass(eq=False, slots=True)
class Label:
    """One nondominated way of being at `node` at time `t`.

    `cost` is the accumulated objective vector in the normative order of CONTRACT.md
    section 1 (index 0 is time). `parent` is the predecessor label, so a route is recovered
    by walking the chain backwards; `theta` and `q` are the control that produced this
    label, kept because the route must report the commanded heading and throttle, not just
    the geometry.

    `eq=False` on purpose: the generated __eq__ would compare `parent` recursively and so
    cost O(path length) and risk recursion limits on long routes. Labels compare by
    identity; cost-order comparison goes through `LabelSet`, which uses an explicit total
    order (`_order_key`).
    """
    cost: Tuple[float, ...]
    node: int
    parent: Optional["Label"]
    theta: float
    q: float
    t: float


def _chain_sig(label: object, limit: int = _CHAIN_SIG_DEPTH) -> Tuple[int, ...]:
    """Node ids of up to `limit` ancestors, as a last-resort tie-break component."""
    sig: list = []
    p = getattr(label, "parent", None)
    while p is not None and len(sig) < limit:
        sig.append(getattr(p, "node", -1))
        p = getattr(p, "parent", None)
    return tuple(sig)


def _order_key(cost: Tuple[float, ...], label: object):
    """A deterministic total order on labels, used for every tie.

    Primary key is the cost tuple itself (lexicographic, so time first -- the queue order).
    The remaining components exist only to make ties decidable without consulting insertion
    order: two labels that compare equal here agree on cost, arrival time, node, heading,
    throttle and the last few ancestors, so they are interchangeable for every future
    extension and which one survives cannot change any reported cost.

    `getattr` rather than attribute access: the solver's priority queue also parks
    lightweight stand-ins in a LabelSet during the coarse pass, and they carry no controls.
    """
    return (cost,
            float(getattr(label, "t", 0.0)),
            int(getattr(label, "node", -1)),
            float(getattr(label, "theta", 0.0)),
            float(getattr(label, "q", 0.0)),
            _chain_sig(label))


# ============================================================================ dominance
def dominates(a: Tuple[float, ...], b: Tuple[float, ...],
              objs: Sequence[ObjectiveSpec]) -> bool:
    """True if `a` Pareto-dominates `b`: no worse everywhere, strictly better somewhere.

    Accumulation-agnostic by construction. Prop 5.4 makes the point precisely: ADD and MAX
    differ in how a value is produced, never in how two produced values are ordered, so the
    dominance test is componentwise on the accumulated vector for both. `objs` is taken to
    fix the arity and to keep every call site honest about which objective set it is
    working in.

    No tolerance. A relative-slack version of this test is not transitive (a beats b beats
    c beats a is reachable with slack), and a nontransitive dominance relation makes the
    retained set depend on scan order, which is exactly the determinism the causality proof
    needs. Near-equal labels are collapsed by the bucket in `LabelSet`, where the merge is
    an explicit quantisation with a stated bound, not silent fuzz in the order.
    """
    k = len(objs)
    if len(a) != k or len(b) != k:
        raise ValueError(f"cost arity mismatch: |a|={len(a)}, |b|={len(b)}, |objs|={k}")
    strict = False
    for x, y in zip(a, b):
        if x > y:
            return False
        if x < y:
            strict = True
    return strict


# ============================================================================ extension
# Which Leg field feeds which objective. ADD objectives integrate a rate over the leg; MAX
# objectives take the instantaneous level, which for risk is a separate field because the
# bottleneck is "how bad did it get", not "how bad per second on average" (types.py, Leg).
_ADD_RATE = {"time": None, "fuel": "fuel_rate", "risk": "risk_rate", "comfort": "comfort_rate"}
_MAX_LEVEL = {"fuel": "fuel_rate", "risk": "risk_level", "comfort": "comfort_rate"}


def extend(label: Label, leg: Leg, dt: float, objs: Sequence[ObjectiveSpec]) -> Tuple[float, ...]:
    """Accumulate `label.cost` across one leg of duration `dt` seconds.

    ADD objectives take rate*dt, MAX objectives take max(running, instantaneous level).
    `dt` is supplied by the caller rather than derived from `leg.sog` because the caller
    already solved for it (leg length / sog) and because of the wait move: Thm 3.3's wait
    relaxation is a leg with sog = 0 and dt > 0, burning fuel at idle and going nowhere.
    A zero speed made good is therefore legal here and is not treated as infeasible.

    dt == 0 is legal (a degenerate leg contributes nothing) and MAX objectives deliberately
    ignore it: a bottleneck attained on a set of measure zero is not a bottleneck, and
    letting one through would let a route be condemned by a level it never actually
    experienced.

    Raises rather than returning a poisoned tuple: a negative increment, a non-finite rate
    or a MAX-accumulated time all break the isotonicity that Prop 5.4 requires of the
    semiring, and a label-setting sweep that admits one produces a wrong answer silently
    instead of failing.
    """
    if not math.isfinite(dt) or dt < 0.0:
        raise ValueError(f"leg duration must be finite and non-negative, got {dt!r}")
    base = label.cost
    if len(base) != len(objs):
        raise ValueError(f"label cost arity {len(base)} != objective count {len(objs)}")

    out: list = []
    for i, spec in enumerate(objs):
        v0 = base[i]
        if spec.accum == Accum.ADD:
            if spec.name == "time":
                inc = dt
            else:
                field = _ADD_RATE.get(spec.name)
                if field is None:
                    raise ValueError(f"no Leg rate defined for additive objective {spec.name!r}")
                inc = float(getattr(leg, field)) * dt
            if not math.isfinite(inc):
                raise ValueError(f"non-finite increment for {spec.name!r}: {inc!r}")
            if inc < 0.0:
                raise ValueError(f"negative increment for {spec.name!r}: {inc!r}; "
                                 "additive objectives must be isotone (Prop 5.4)")
            v = v0 + inc
        elif spec.accum == Accum.MAX:
            if spec.name == "time":
                raise ValueError("time is additive by definition (CONTRACT.md section 1)")
            field = _MAX_LEVEL.get(spec.name)
            if field is None:
                raise ValueError(f"no Leg level defined for bottleneck objective {spec.name!r}")
            if dt <= 0.0:
                v = v0
            else:
                level = float(getattr(leg, field))
                if not math.isfinite(level):
                    raise ValueError(f"non-finite level for {spec.name!r}: {level!r}")
                v = v0 if v0 >= level else level
        else:
            raise ValueError(f"unknown accumulation {spec.accum!r} for {spec.name!r}")
        out.append(v)
    return tuple(out)


# ============================================================================ bucketing
def _geometric_index(v: float, log1p_eps: float, floor: float) -> int:
    """Index of `v` on the grid floor*(1+eps)^k. Values at or below `floor` share index 0."""
    if v <= floor:
        return 0
    return 1 + int(math.floor(math.log(v / floor) / log1p_eps))


def _uniform_index(v: float, width: float, floor: float) -> int:
    """Index of `v` on the grid k*width. Values at or below `floor` share index 0."""
    if v <= floor:
        return 0
    return 1 + int(math.floor(v / width))


# ============================================================================ label set
@dataclass(slots=True)
class _Entry:
    cost: Tuple[float, ...]
    label: object
    key: tuple
    ordk: tuple


class LabelSet:
    """The labels one node is allowed to remember, under eps-dominance.

    Maintains two invariants simultaneously:

      (P) no stored cost dominates another stored cost (exact Pareto filter), and
      (B) within one bucket cell, only the labels that are Pareto-minimal on the
          *non-bucketed* objectives survive.

    With the default objective set (time exact, fuel and risk bucketed) invariant (B) reads
    "one label per bucket cell, the earliest-arriving one", which is the whole point: time
    is never approximated, and the price of the approximation is paid entirely on fuel and
    risk.

    Cost of the guarantee. Let p be any cost offered to this set and rejected. Either some
    stored s dominated it (s <= p everywhere) or some stored s shared its bucket cell and
    was no worse on every non-bucketed axis. In the second case s and p lie in the same
    cell, so they differ by at most one bucket width on the bucketed axes. Both cases are
    preserved when s is itself later evicted -- by a dominator (which is <= s <= p) or by a
    same-cell replacement (same cell as s, hence the same cell as p). The distance from a
    rejected cost to the surviving witness is therefore ONE bucket width in total, not one
    per eviction and not one per leg.

    Determinism, stated exactly because the loose version would be false. The same sequence
    of offers always produces the same retained set, byte for byte: every tie goes through
    `_order_key`, nothing consults object identity, insertion order or hash iteration. That
    is what the sweep needs, since the bucket queue pops in a deterministic order and so
    offers labels in a deterministic order. It is NOT permutation invariance. With eps > 0
    the retained set does depend on the order of offers -- if a label is evicted from its
    cell by a same-cell rival, a third label the evicted one would have dominated can
    survive -- and no online eps-filter avoids this without storing everything it discards.
    Measured on the self-test input: 101 labels retained in the natural order, 98-104 under
    random permutations, agreeing on roughly 80% of entries. At eps = 0 the filter is exact
    and permutation invariance is restored (verified: 338 labels under every permutation
    tried, matching an offline Pareto filter of the same input exactly).

    Complexity: insert is O(m*k) for m stored labels and k objectives, one scan. m is
    bounded by the number of occupied cells, which is the Thm 5.3 count.
    """

    def __init__(self, objs: Sequence[ObjectiveSpec], eps: float) -> None:
        if len(objs) == 0:
            raise ValueError("at least one objective is required")
        if not math.isfinite(eps) or eps < 0.0:
            raise ValueError(f"eps must be finite and non-negative, got {eps!r}")
        lead = objs[0]
        # CONTRACT.md section 1: index 0 is arrival time, additive, and drives the queue
        # order. Bucketing it would let the sweep pop a label whose time has been rounded
        # up past a label still in the queue, which is precisely the monotonicity Prop 4.9
        # relies on. Refuse the configuration rather than approximate it.
        if lead.eps_bucket:
            raise ValueError("objective 0 (time) drives the queue and must not be bucketed")
        if lead.accum != Accum.ADD:
            raise ValueError("objective 0 (time) must accumulate additively")

        self._objs: Tuple[ObjectiveSpec, ...] = tuple(objs)
        self._eps = float(eps)
        self._exact = eps <= 0.0
        self._log1p_eps = math.log1p(eps) if eps > 0.0 else 1.0
        self._free = tuple(i for i, s in enumerate(self._objs) if not s.eps_bucket)
        self._entries: list = []
        self.peak = 0            # high-water mark, for Route.label_peak
        self.n_offered = 0
        self.n_accepted = 0

    # ------------------------------------------------------------------ properties
    @property
    def objectives(self) -> Tuple[ObjectiveSpec, ...]:
        return self._objs

    @property
    def eps(self) -> float:
        return self._eps

    # ------------------------------------------------------------------ bucketing
    def bucket_key(self, cost: Sequence[float]) -> tuple:
        """The bucket cell of a cost vector. Spec Thm 5.3.

        Bucketing is on the accumulated objective VALUE, never on the per-edge increment.
        This is the difference between a clean guarantee and a useless one. Quantise the
        increments and each of the D legs of a route contributes its own rounding, so the
        retained label is only within (1+eps)^D of the true one and the bound degrades with
        route length -- for an ocean crossing with D in the thousands that is not a bound at
        all. Quantise the value and the label competes against its rivals in absolute terms
        at every node it reaches; the cell it lands in depends on where it is, not on how it
        got there, and the surviving witness is within one bucket width of any rejected
        cost regardless of D (argued in the class docstring). Hence (1+eps), not (1+eps)^D.

        Per-axis discretisation:

        * not bucketed (`eps_bucket=False`, i.e. time): contributes the constant 0. The
          axis does not partition anything; exactness on it is enforced instead by
          invariant (B), which keeps the minimiser over the non-bucketed axes inside every
          cell. Time is therefore never rounded, only rivals are.

        * ADD + bucketed (fuel): geometric grid floor*(1+eps)^k. Correct because an
          additive objective ranges over several decades along a route -- the first hour of
          fuel burn and the thousandth differ in scale, and only a relative grid gives them
          comparable resolution. This is also what bounds the cell count by
          log(max/floor)/log(1+eps) per axis, the Thm 5.3 factor.

        * MAX + bucketed (bottleneck risk): uniform grid of width eps*MAX_OBJECTIVE_SCALE.
          Deliberately NOT geometric, for two independent reasons. First, a running maximum
          does not compound: its value on any path is one of the instantaneous levels of
          the edges traversed, so it takes at most as many distinct values as there are
          distinct edge levels, no matter how long the route -- the unbounded growth that
          geometric bucketing exists to control simply does not occur on this axis, and the
          cell count is already bounded by 1/eps here. Second, a geometric grid resolves
          exactly where the resolution is worthless: it spends unboundedly many cells
          separating risk 1e-9 from 1e-8, differences with no operational meaning, while
          giving the same single (1+eps) factor to the interval around 0.9 where a master
          actually makes decisions. A bottleneck index is compared by difference, not by
          ratio, so the grid is uniform and the guarantee on this axis is additive-eps
          rather than multiplicative.

          Limitation, stated because it is a real one: the uniform width assumes the MAX
          objective is normalised to order 1, which `Leg.risk_level` is (types.py). A
          bottleneck objective on some other scale -- metres of freeboard, degrees of roll
          -- must be normalised before it reaches this module, or MAX_OBJECTIVE_SCALE
          adjusted to its characteristic magnitude.

        eps = 0 disables the approximation: bucketed axes contribute their exact value, so
        cells collide only for exactly equal costs and the set degenerates to an exact
        Pareto filter with deterministic tie-breaking.
        """
        if len(cost) != len(self._objs):
            raise ValueError(f"cost arity {len(cost)} != objective count {len(self._objs)}")
        key: list = []
        for i, spec in enumerate(self._objs):
            if not spec.eps_bucket:
                key.append(0)
                continue
            v = cost[i]
            if self._exact:
                key.append(v)
            elif spec.accum == Accum.MAX:
                key.append(_uniform_index(v, self._eps * MAX_OBJECTIVE_SCALE, spec.floor))
            else:
                key.append(_geometric_index(v, self._log1p_eps, spec.floor))
        return tuple(key)

    # ------------------------------------------------------------------ insertion
    def _validate(self, cost: Sequence[float]) -> Tuple[float, ...]:
        if len(cost) != len(self._objs):
            raise ValueError(f"cost arity {len(cost)} != objective count {len(self._objs)}")
        out = tuple(float(c) for c in cost)
        for i, c in enumerate(out):
            # A NaN compares False against everything, so a single one would make the
            # dominance test silently non-transitive and corrupt the whole front.
            if not math.isfinite(c):
                raise ValueError(f"objective {self._objs[i].name!r} is not finite: {c!r}")
        return out

    def insert(self, cost: Sequence[float], label: object) -> bool:
        """Offer a label. Returns False if it is dominated or eps-dominated, and stores
        nothing in that case; returns True and evicts everything the newcomer supersedes
        otherwise.

        `cost` is authoritative -- it is not read back off `label`, because the solver
        computes the extension before it decides whether a Label object is worth building.
        """
        cost = self._validate(cost)
        self.n_offered += 1
        key = self.bucket_key(cost)
        ordk = _order_key(cost, label)
        free = self._free

        for e in self._entries:
            if dominates(e.cost, cost, self._objs):
                return False
            if e.key == key:
                # Same cell: the newcomer only earns its place by being better on an axis
                # the cell does not resolve. Exact ties fall through to the total order,
                # where the incumbent wins -- stable and independent of arrival order.
                better = False
                worse = False
                for i in free:
                    if e.cost[i] < cost[i]:
                        better = True
                    elif e.cost[i] > cost[i]:
                        worse = True
                if not worse and (better or e.ordk <= ordk):
                    return False

        keep: list = []
        for e in self._entries:
            if dominates(cost, e.cost, self._objs):
                continue
            if e.key == key:
                better = False
                worse = False
                for i in free:
                    if cost[i] < e.cost[i]:
                        better = True
                    elif cost[i] > e.cost[i]:
                        worse = True
                if not worse and (better or ordk < e.ordk):
                    continue
            keep.append(e)

        keep.append(_Entry(cost, label, key, ordk))
        self._entries = keep
        self.n_accepted += 1
        if len(keep) > self.peak:
            self.peak = len(keep)
        return True

    # ------------------------------------------------------------------ access
    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self) -> Iterator:
        """Labels in the total order of `_order_key`, i.e. lexicographic by cost with time
        first. Sorted on every call rather than kept sorted: iteration happens once per
        node at reconstruction time, insertion happens millions of times."""
        for e in sorted(self._entries, key=lambda e: e.ordk):
            yield e.label

    def costs(self) -> list:
        """The stored cost vectors, in the same order as __iter__."""
        return [e.cost for e in sorted(self._entries, key=lambda e: e.ordk)]

    def best(self, index: int):
        """The stored label minimising objective `index`; None if the set is empty.

        index 0 is what the bucket queue pops. Ties are broken by the same total order as
        everywhere else, so the queue's choice is reproducible.
        """
        if index < 0 or index >= len(self._objs):
            raise IndexError(f"objective index {index} out of range")
        if not self._entries:
            return None
        best = min(self._entries, key=lambda e: (e.cost[index], e.ordk))
        return best.label


# ============================================================================ self-test
def _selftest() -> None:
    """Exercise the algebra on 10000 seeded cost triples and print the measured loss."""
    import numpy as np

    from kairos.types import DEFAULT_OBJECTIVES

    objs = DEFAULT_OBJECTIVES
    eps = 0.10
    rng = np.random.default_rng(12345)
    n = 10000

    # Costs shaped like the real thing: a slow route burns less fuel, so time and fuel are
    # anti-correlated and the front is genuinely two-dimensional rather than a single point.
    hours = rng.uniform(60.0, 240.0, n)
    time_s = hours * 3600.0
    fuel_kg = 4.0e5 / hours * rng.uniform(0.75, 1.35, n)
    risk = np.clip(rng.beta(2.0, 5.0, n), 0.0, 1.0)
    triples = [(float(time_s[i]), float(fuel_kg[i]), float(risk[i])) for i in range(n)]

    ls = LabelSet(objs, eps)
    for i, c in enumerate(triples):
        ls.insert(c, Label(cost=c, node=i, parent=None, theta=0.0, q=1.0, t=c[0]))

    stored = ls.costs()
    print(f"objectives      : {[ (s.name, s.accum, s.eps_bucket) for s in objs ]}")
    print(f"eps             : {eps}")
    print(f"offered         : {ls.n_offered}")
    print(f"accepted        : {ls.n_accepted}")
    print(f"final set size  : {len(ls)}   (peak {ls.peak})")

    # (1) internal consistency: invariant (P).
    viol = [(i, j) for i in range(len(stored)) for j in range(len(stored))
            if i != j and dominates(stored[i], stored[j], objs)]
    print(f"internal dominations: {len(viol)}  (must be 0)")

    # (2) exact Pareto filter of the same input, by lexicographic sweep: sorted by cost,
    # any dominator of a point precedes it, so testing against the running front suffices.
    order = sorted(range(n), key=lambda i: triples[i])
    exact: list = []
    for i in order:
        c = triples[i]
        if not any(dominates(f, c, objs) for f in exact):
            exact = [f for f in exact if not dominates(c, f, objs)]
            exact.append(c)
    print(f"exact Pareto set: {len(exact)}")

    # (3) measured loss. The claim is that every exact-Pareto point has a retained witness
    # that is no worse in time and within one bucket width on fuel and risk, so time is a
    # hard constraint on the witness search rather than one axis of the score -- scoring it
    # alongside the others would report the loss of some other label, not of the witness.
    tol = 1e-12
    w_time = w_fuel = w_risk = -math.inf
    violations = 0
    for p in exact:
        best = None
        for s in stored:
            lt = s[0] / p[0] - 1.0
            if lt > tol:
                continue
            lf = s[1] / p[1] - 1.0
            lr = s[2] - p[2]
            score = max(lf, lr)
            if best is None or score < best[0]:
                best = (score, lt, lf, lr)
        if best is None:
            violations += 1
            continue
        _, lt, lf, lr = best
        w_time = max(w_time, lt)
        w_fuel = max(w_fuel, lf)
        w_risk = max(w_risk, lr)
        if lf > eps + tol or lr > eps * MAX_OBJECTIVE_SCALE + tol:
            violations += 1
    print(f"max relative loss, time (ADD, unbucketed): {w_time:+.6f}  (bound 0)")
    print(f"max relative loss, fuel (ADD, geometric) : {w_fuel:+.6f}  (bound {eps})")
    print(f"max absolute loss, risk (MAX, uniform)   : {w_risk:+.6f}  (bound {eps})")
    print(f"guarantee violations over exact front    : {violations}  (must be 0)")

    # (4) accumulation, on a leg a Handymax would actually sail.
    leg = Leg(sog=7.0, fuel_rate=0.55, risk_rate=1.0e-5, risk_level=0.42,
              comfort_rate=0.0, q=0.85, theta=1.2)
    root = Label(cost=(0.0, 0.0, 0.0), node=0, parent=None, theta=0.0, q=1.0, t=0.0)
    c1 = extend(root, leg, 3600.0, objs)
    hot = Leg(sog=6.0, fuel_rate=0.60, risk_rate=2.0e-5, risk_level=0.31,
              comfort_rate=0.0, q=0.90, theta=1.3)
    c2 = extend(Label(cost=c1, node=1, parent=root, theta=leg.theta, q=leg.q, t=c1[0]),
                hot, 3600.0, objs)
    print(f"extend 1 h  : {c1}")
    print(f"extend +1 h : {c2}   (risk is the running max, 0.42 not 0.31)")
    wait = extend(Label(cost=c2, node=2, parent=None, theta=0.0, q=0.15, t=c2[0]),
                  Leg(sog=0.0, fuel_rate=0.08, risk_rate=0.0, risk_level=0.05),
                  1800.0, objs)
    print(f"wait 0.5 h  : {wait}   (sog=0 is legal, Thm 3.3)")


if __name__ == "__main__":
    _selftest()
