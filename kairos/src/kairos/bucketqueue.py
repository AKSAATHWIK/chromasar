"""The monotone priority queue that carries the ordered-upwind front.

Spec reference: CONTRACT.md decision D3, Prop 4.9 (correctness of the Dial discipline).

The front propagation is a Dijkstra-shaped sweep, so its cost is `O(E + N log N)` with a
binary heap and `O(E + N)` with a Dial 1969 bucket queue. The `log N` factor is worth
removing because `N` is the number of grid nodes times the number of retained Pareto labels,
which for an ocean-basin solve at 0.125 degrees with Lambda = 8 is order 10^7 -- a `log N`
of about 23 on every single queue operation.

The bucket discipline is licensed by exactly one hypothesis: every edge costs at least
`Delta_min = h * F_min` and `F_min > 0` (assumption A1). That makes the live keys sit inside
a bounded window above the current minimum, so a key never has to be inserted behind the
scan cursor. `F_min` is NOT bounded away from zero when the drift exceeds the ship's own
speed -- a cell where some direction is simply unattainable -- and in that regime
`make_queue` hands back a heap. That is the D3 fallback rule, decided once at solver setup
rather than per cell.

Three things this implementation does that a textbook Dial does not, each because the solver
needs it:

  * **Exactly sorted output.** Textbook Dial pops a bucket in arbitrary order, which is
    enough for Dijkstra correctness but leaves the popped key sequence non-decreasing only
    to within `width`. KAIROS reads the queue minimum as the running lower bound for the
    a posteriori certificate (Cor 4.12), and an out-of-order key there would make the
    certificate wrong. So the bucket the cursor is parked on is sorted once on entry and
    drained from its tail: amortised `O(log b)` per element in `b` = bucket occupancy,
    against `O(log N)` for the heap, and `b << N` is exactly the regime where buckets pay.
  * **An overflow heap** for keys landing beyond the window, re-bucketed when the window
    advances past them. Without it a single long edge would corrupt the array by wrapping.
  * **Downward re-anchoring**, for keys below the cursor but above the current minimum.
    That can only happen before the first pop (afterwards the cursor sits exactly on the
    minimum's bucket), i.e. during bulk seeding of the front, but it happens there routinely.

A key pushed *below* the current minimum breaks the invariant outright. It is counted,
logged, and -- when `safe` is set, the default -- the queue transparently degrades to a
binary heap for the remainder of the run, because a voyage plan must not die on one bad cell.

Both classes expose the same surface, so the solver holds one name and never branches.
"""
from __future__ import annotations

import heapq
import logging
import math
from typing import Any, Iterator, List, Optional, Tuple

_LOG = logging.getLogger(__name__)
_floor = math.floor
_INF = math.inf

#: Window size in buckets. 1024 * (h * F_min) covers a front spread of ~1024 minimum edges,
#: far wider than the ordered-upwind stencil produces (Prop 4.7 bounds the stencil radius by
#: the local anisotropy, typically under 10 cells). An unused bucket is one empty list, so
#: the default is deliberately generous.
DEFAULT_N_BUCKETS = 1024

#: Entries are (key, seq, payload) triples. The sequence number exists so that every sort
#: and every heap comparison resolves on floats and ints in C and NEVER reaches the payload,
#: which is a solver label and is not required to be orderable. It also makes ties FIFO.
_Entry = Tuple[float, int, Any]


def _insort_desc(bucket: List[_Entry], entry: _Entry) -> None:
    """Insert into a key-descending list, comparing keys only.

    Open-coded rather than `bisect.insort` because insort compares whole tuples, and on a
    key tie that is one `seq` comparison we do not need. Used only on the active bucket,
    which under the D3 hypothesis is never pushed into at all (an edge costs at least one
    bucket width, so a child key always lands strictly ahead of its parent's bucket).
    """
    k = entry[0]
    lo, hi = 0, len(bucket)
    while lo < hi:
        mid = (lo + hi) >> 1
        if bucket[mid][0] > k:
            lo = mid + 1
        else:
            hi = mid
    bucket.insert(lo, entry)


# ============================================================================ heap
class HeapQueue:
    """Binary heap with the BucketQueue surface. The unconditionally-correct fallback.

    Accepts and ignores `width` / `n_buckets` so it is a drop-in substitute at every call
    site. It still counts monotonicity violations: a nonzero count means some cell produced
    a negative-cost edge, which is a physics bug worth surfacing in `Route.notes` even
    though the heap absorbs it without misordering anything.
    """

    __slots__ = ("_h", "_seq", "_min_key", "_violations")

    def __init__(self, width: Optional[float] = None, n_buckets: int = 0) -> None:
        self._h: List[_Entry] = []
        self._seq: int = 0
        self._min_key: float = -_INF     # key of the most recent pop
        self._violations: int = 0

    def push(self, key: float, item: Any) -> None:
        if not -_INF < key < _INF:       # also catches NaN, which fails every comparison
            raise ValueError(f"non-finite queue key {key!r}; the metric returned inf/NaN")
        if key < self._min_key:
            self._violations += 1
        seq = self._seq
        self._seq = seq + 1
        heapq.heappush(self._h, (key, seq, item))

    def pop_min(self) -> Tuple[float, Any]:
        if not self._h:
            raise IndexError("pop_min from an empty queue")
        key, _, item = heapq.heappop(self._h)
        self._min_key = key
        return key, item

    def min_key(self) -> float:
        """Key of the next pop, without removing it. The solver uses this as the running
        lower bound on every unsettled arrival time (Cor 4.12, the certificate)."""
        if not self._h:
            raise IndexError("min_key of an empty queue")
        return self._h[0][0]

    def empty(self) -> bool:
        return not self._h

    def __len__(self) -> int:
        return len(self._h)

    @property
    def monotone_violations(self) -> int:
        return self._violations

    @property
    def fell_back(self) -> bool:
        """True: this IS the fallback structure. Lets the caller report one flag either way."""
        return True

    @property
    def overflow_events(self) -> int:
        return 0


# ============================================================================ buckets
class BucketQueue:
    """Dial 1969 monotone bucket queue. O(1) amortised push/pop when all keys lie within
    a bounded window above the current minimum -- which holds here because every edge
    costs at least h*F_min > 0.

    Layout: a circular array of `n_buckets` lists, bucket `b` holding every live key in
    `[b*width, (b+1)*width)`, plus a cursor that walks forward and never rewinds once
    popping has begun. The bucket under the cursor is detached into `_active`, sorted
    descending, and drained from its tail, which makes the common pop a single `list.pop()`.
    """

    __slots__ = ("_width", "_inv_width", "_n_buckets", "_buckets", "_active", "_active_b",
                 "_overflow", "_seq", "_cursor", "_primed", "_n", "_min_key",
                 "_violations", "_overflowed", "_safe", "_fallback")

    def __init__(self, width: float, n_buckets: int = DEFAULT_N_BUCKETS,
                 safe: bool = True) -> None:
        if not (-_INF < width < _INF) or width <= 0.0:
            raise ValueError(
                f"bucket width must be finite and positive, got {width!r}; use make_queue(), "
                "which routes the unbounded-F_min case to a heap instead of erroring")
        if n_buckets < 2:
            raise ValueError(f"n_buckets must be at least 2, got {n_buckets}")

        self._width: float = width
        # One multiply beats one divide in the hottest line in the module. Every bucket
        # index in this file is computed with this same expression so that a key can never
        # be assigned two different bucket indices by two different roundings.
        self._inv_width: float = 1.0 / width
        self._n_buckets: int = n_buckets
        self._buckets: List[List[_Entry]] = [[] for _ in range(n_buckets)]

        self._active: List[_Entry] = []   # the cursor's bucket, sorted descending
        self._active_b: int = 0           # its absolute bucket index (stale when _active empty)

        # Keys more than `n_buckets * width` above the cursor cannot be addressed by the
        # circular array. They wait here and are reclaimed by `_refill` once the sliding
        # window has caught up with them.
        self._overflow: List[_Entry] = []
        self._overflowed: int = 0

        self._seq: int = 0
        self._cursor: int = 0            # absolute bucket index
        self._primed: bool = False       # cursor not yet anchored to any real key
        self._n: int = 0
        self._min_key: float = -_INF     # key of the most recent pop
        self._violations: int = 0
        self._safe: bool = safe
        self._fallback: Optional[HeapQueue] = None

    # ------------------------------------------------------------------ public
    def push(self, key: float, item: Any) -> None:
        fb = self._fallback
        if fb is not None:
            fb.push(key, item)
            return
        if not -_INF < key < _INF:       # also catches NaN
            raise ValueError(f"non-finite queue key {key!r}; the metric returned inf/NaN")
        if key < self._min_key:
            # Dial's invariant is broken: this key belongs behind the cursor, in array cells
            # already consumed. Bucketing it anyway would emit an out-of-order pop and, in
            # the solver, settle a node at a time it cannot actually be reached at.
            self._violations += 1
            self._degrade(key, item)
            return

        seq = self._seq
        self._seq = seq + 1
        entry = (key, seq, item)
        self._n += 1

        b = _floor(key * self._inv_width)
        if not self._primed:
            self._cursor = b
            self._primed = True
        d = b - self._cursor

        if 0 < d < self._n_buckets:
            self._buckets[b % self._n_buckets].append(entry)
        elif d == 0:
            # The cursor's own bucket. Only reachable when an edge costs less than one
            # bucket width, which the D3 hypothesis forbids -- but a metric that is merely
            # nearly-degenerate can produce it, and the active list must stay sorted.
            if self._active:
                _insort_desc(self._active, entry)
            else:
                self._buckets[b % self._n_buckets].append(entry)
        elif d < 0:
            # Below the cursor but not below the minimum: only possible before the first pop
            # (afterwards the cursor sits on the minimum's own bucket), i.e. while the front
            # is being seeded. Move the window down instead of wrapping into a live cell.
            self._reanchor_down(b)
            self._buckets[b % self._n_buckets].append(entry)
        else:
            heapq.heappush(self._overflow, entry)
            self._overflowed += 1

    def pop_min(self) -> Tuple[float, Any]:
        fb = self._fallback
        if fb is not None:
            return fb.pop_min()
        active = self._active
        if not active:
            if self._n == 0:
                raise IndexError("pop_min from an empty queue")
            self._refill()
            active = self._active
        key, _, item = active.pop()
        self._n -= 1
        self._min_key = key
        if self._n == 0:
            # Nothing live: let the next push re-anchor the window wherever it likes. The
            # check against `_min_key` still guards that re-anchor.
            self._primed = False
        return key, item

    def min_key(self) -> float:
        """Key of the next pop, without removing it (the Cor 4.12 lower bound)."""
        if self._fallback is not None:
            return self._fallback.min_key()
        if not self._active:
            if self._n == 0:
                raise IndexError("min_key of an empty queue")
            self._refill()
        return self._active[-1][0]

    def empty(self) -> bool:
        return len(self) == 0

    def __len__(self) -> int:
        if self._fallback is not None:
            return len(self._fallback)
        return self._n

    @property
    def monotone_violations(self) -> int:
        """Pushes whose key was below the current minimum. Nonzero means the metric emitted
        an edge of negative cost somewhere; the route is still produced, but the count
        belongs in `Route.notes`."""
        if self._fallback is not None:
            return self._violations + self._fallback.monotone_violations
        return self._violations

    @property
    def fell_back(self) -> bool:
        """True once the structure has degraded to a heap; stays true for the rest of the run."""
        return self._fallback is not None

    @property
    def overflow_events(self) -> int:
        """Entries that had to be parked outside the window. Large relative to `n_buckets`
        means the window is mis-sized and the queue is doing heap work in disguise."""
        return self._overflowed

    # ------------------------------------------------------------------ internals
    def _refill(self) -> None:
        """Reclaim any overflow that the window has caught up with, then detach the next
        non-empty bucket into `_active`, sorted descending.

        The reclaim step is not optional. The addressable window `[cursor, cursor+n_buckets)`
        SLIDES with the cursor, so a key parked in overflow at push time can come inside the
        window later simply because the cursor moved; if it were only reclaimed when the
        array went completely empty, the scan below would walk straight past its bucket and
        emit a larger key first. Doing the reclaim here, before every scan, restores the
        invariant the scan relies on: after it, every overflow key has bucket index at least
        `cursor + n_buckets`, hence exceeds every key the window can hold, hence cannot be
        the minimum. The cursor advances at most `n_buckets - 1` during one scan, so it can
        never step over an overflow entry either.

        That same window invariant is what makes slot reuse safe: live bucketed entries all
        have indices in a half-open range of length `n_buckets`, so `b % n_buckets` is
        injective over them and two different absolute buckets never share a list.

        Sorting whole triples means the comparison runs entirely in C and stops at `seq` on
        a key tie, so the payload is never compared. Descending order lets `pop_min` take
        the minimum with `list.pop()`, which is O(1) and does not move the other elements.
        """
        buckets = self._buckets
        nb = self._n_buckets
        inv = self._inv_width
        ovf = self._overflow
        cursor = self._cursor
        while True:
            limit = cursor + nb
            while ovf and _floor(ovf[0][0] * inv) < limit:
                entry = heapq.heappop(ovf)
                buckets[_floor(entry[0] * inv) % nb].append(entry)
            for _ in range(nb):
                idx = cursor % nb
                bucket = buckets[idx]
                if bucket:
                    bucket.sort(reverse=True)
                    self._active = bucket
                    self._active_b = cursor
                    buckets[idx] = []
                    self._cursor = cursor
                    return
                cursor += 1
            # The whole window is empty, so everything left is parked above it. Jump the
            # cursor to the smallest parked key rather than walking there a bucket at a time.
            if not ovf:
                self._cursor = cursor
                raise RuntimeError(
                    f"bucket queue reports {self._n} live entries but every bucket, the "
                    "active list and the overflow heap are empty; its counters are "
                    "inconsistent")
            cursor = _floor(ovf[0][0] * inv)

    def _reanchor_down(self, b_new: int) -> None:
        """Move the window down to start at `b_new`, evicting whatever no longer fits.

        The eviction preserves the window invariant stated in `_refill`: the entries pushed
        out are the ones with the LARGEST bucket indices (>= b_new + n_buckets), which is
        exactly what the overflow heap is for, and what remains again spans a range of length
        `n_buckets` starting at the new cursor. Entries that stay keep their array slot,
        because `b % n_buckets` does not depend on the cursor.

        Cost is O(n_buckets) per call, and a call happens only when the running minimum of
        the pushed keys drops below the current window -- O(log m) times for m random
        seeds, and once for the usual case of a single source node.
        """
        nb = self._n_buckets
        limit = b_new + nb
        inv = self._inv_width
        buckets = self._buckets

        if self._active:
            # Deactivating is mandatory, not tidy-up: the cursor is about to move below
            # `_active_b`, and buckets below it would then hold smaller keys than the
            # active list, which `pop_min` would not look at.
            if self._active_b >= limit:
                for entry in self._active:
                    heapq.heappush(self._overflow, entry)
                    self._overflowed += 1
            else:
                buckets[self._active_b % nb] = self._active
            self._active = []

        for idx in range(nb):
            bucket = buckets[idx]
            if bucket and _floor(bucket[0][0] * inv) >= limit:
                # One bucket holds one absolute index, so testing the first entry decides
                # the whole list.
                for entry in bucket:
                    heapq.heappush(self._overflow, entry)
                    self._overflowed += 1
                buckets[idx] = []
        self._cursor = b_new

    def _drain(self) -> Iterator[Tuple[float, Any]]:
        """Every live (key, payload) pair, in no particular order. Empties the structure."""
        for entry in self._active:
            yield entry[0], entry[2]
        self._active = []
        for bucket in self._buckets:
            for entry in bucket:
                yield entry[0], entry[2]
            bucket.clear()
        for entry in self._overflow:
            yield entry[0], entry[2]
        self._overflow.clear()
        self._n = 0

    def _degrade(self, key: float, item: Any) -> None:
        """Handle a below-minimum push: migrate to a heap (safe) or refuse (strict).

        Option (a) of the brief is the default. One anomalous cell -- a forecast artefact, a
        current field that briefly exceeds hull speed, a metric that returned a marginally
        negative edge through rounding -- must not destroy an otherwise valid voyage plan.
        The event is counted and logged so it appears in the run report instead of vanishing.
        """
        deficit = self._min_key - key
        if not self._safe:
            raise ValueError(
                f"monotonicity violation: key {key!r} is {deficit:.6g} below the current "
                f"queue minimum {self._min_key!r}, so the bucket discipline (Prop 4.9) is "
                "invalid here. Construct with safe=True to degrade to a heap instead.")

        _LOG.warning(
            "bucket queue monotonicity violated: key %.6g is %.6g below the current minimum "
            "%.6g (%.2f bucket widths). Degrading to a binary heap for the remainder of the "
            "run; %d live entries migrated.",
            key, deficit, self._min_key, deficit * self._inv_width, self._n)

        fq = HeapQueue()
        for k, it in self._drain():
            fq.push(k, it)
        self._fallback = fq
        # Push the offender while the heap's own watermark is still -inf, then hand the real
        # watermark over. That keeps this violation counted exactly once, here.
        fq.push(key, item)
        fq._min_key = self._min_key


# ============================================================================ factory
def make_queue(width: Optional[float], n_buckets: int = DEFAULT_N_BUCKETS,
               safe: bool = True) -> "BucketQueue | HeapQueue":
    """Pick the queue the solver should run with.

    `width` is `Delta_min = h * F_min`, the smallest possible edge cost, or None when the
    solver could not bound `F_min` away from zero. The latter is the strong-drift case: some
    direction in some cell is unattainable because the set exceeds the hull's speed through
    water, `F -> inf` there, and the reciprocal bound collapses. Dial's discipline means
    nothing without a positive width, so we take the heap and the `log N` with it.

    Non-finite or non-positive `width` is treated as "not bounded" rather than as an error:
    that is exactly what a degenerate `F_min` estimate looks like coming out of the metric,
    and refusing to build a queue would turn a hard routing problem into a crash.
    """
    if width is None or not -_INF < width < _INF or width <= 0.0:
        _LOG.info("F_min not bounded away from zero (width=%r); using a binary heap rather "
                  "than the Dial bucket queue, per the D3 fallback rule.", width)
        return HeapQueue()
    if n_buckets < 2:
        raise ValueError(f"n_buckets must be at least 2, got {n_buckets}")
    return BucketQueue(width, n_buckets, safe=safe)


# ============================================================================ self-test
def _selftest() -> None:
    """Exercise both structures and print the measured numbers.

    Run with `python -m kairos.bucketqueue`. Worth re-running on any machine the solver is
    benchmarked on: whether buckets beat a heap is a constant-factor question, and CPython's
    heapq is written in C while this is not.
    """
    import random
    import time

    WIDTH = 1.0
    N = 200_000
    SEED = 20260814

    # ---------------------------------------------------------------- [1] bulk
    # 200k keys inside one window, pushed before any pop, so monotonicity holds trivially.
    rng = random.Random(SEED)
    keys = [rng.uniform(0.0, DEFAULT_N_BUCKETS * WIDTH) for _ in range(N)]
    want = sorted(keys)

    def bulk(q):
        t0 = time.perf_counter()
        for i, k in enumerate(keys):
            q.push(k, i)
        out = [q.pop_min()[0] for _ in range(N)]
        return time.perf_counter() - t0, out

    bq = BucketQueue(WIDTH, DEFAULT_N_BUCKETS)
    t_b, got_b = bulk(bq)
    t_h, got_h = bulk(HeapQueue())
    assert all(got_b[i] <= got_b[i + 1] for i in range(N - 1)), "bucket queue emitted a decrease"
    assert got_b == want, "bucket output is not the sorted input"
    assert got_h == want
    print(f"[1] bulk: {N} random keys over {DEFAULT_N_BUCKETS} buckets, push all then pop all")
    print(f"    bucket {t_b * 1000:8.1f} ms   heap {t_h * 1000:8.1f} ms   "
          f"speedup {t_h / t_b:5.2f}x   non-decreasing: yes   == sorted(input): yes")
    print(f"    reanchor-downs exercised, overflow events {bq.overflow_events}, "
          f"violations {bq.monotone_violations}, len now {len(bq)}")

    # ---------------------------------------------------------------- [2] front-shaped
    # The realistic regime: keys are parent + width*(1 + 8U), i.e. every edge at least one
    # bucket wide, with the live set held near a target so both queues see a steady state.
    def frontlike(q, live_target: int):
        rng = random.Random(SEED + 1)
        q.push(0.0, 0)
        out: List[float] = []
        t0 = time.perf_counter()
        for i in range(N):
            k, _ = q.pop_min()
            out.append(k)
            live = len(q)
            fan = 2 if live < live_target else (1 if live < 2 * live_target else 0)
            if live == 0 and fan == 0:
                fan = 1
            for _ in range(fan):
                q.push(k + WIDTH * (1.0 + 8.0 * rng.random()), i)
        return time.perf_counter() - t0, out

    print(f"[2] front-shaped: {N} pops, edges in [1, 9) bucket widths")
    for live_target in (2_000, 50_000, 400_000):
        fq = BucketQueue(WIDTH, DEFAULT_N_BUCKETS)
        t_b, out_b = frontlike(fq, live_target)
        t_h, out_h = frontlike(HeapQueue(), live_target)
        assert all(out_b[i] <= out_b[i + 1] for i in range(N - 1)), "decrease in front workload"
        assert out_b == out_h, "bucket and heap disagree on the pop sequence"
        print(f"    live ~{live_target:7d}: bucket {t_b * 1000:8.1f} ms   "
              f"heap {t_h * 1000:8.1f} ms   speedup {t_h / t_b:5.2f}x   "
              f"identical to heap: yes")

    # ---------------------------------------------------------------- [3] overflow
    rng = random.Random(SEED + 2)
    span = 50.0 * DEFAULT_N_BUCKETS * WIDTH
    okeys = [rng.uniform(0.0, span) for _ in range(N)]
    oq = BucketQueue(WIDTH, DEFAULT_N_BUCKETS)
    for i, k in enumerate(okeys):
        oq.push(k, i)
    got = [oq.pop_min()[0] for _ in range(N)]
    assert got == sorted(okeys), "overflow re-bucketing lost or reordered entries"
    print(f"[3] overflow: key span = 50x the window -> {oq.overflow_events} entries parked, "
          f"output exactly sorted, drained to len {len(oq)}")

    # ---------------------------------------------------------------- [3b] min_key
    # The certificate reads this on every outer iteration, so it must agree with the pop
    # that follows it, including across a bucket boundary and a reclaim from overflow.
    rng = random.Random(SEED + 4)
    mq = BucketQueue(WIDTH, 8)                       # tiny window: forces both transitions
    for i in range(20_000):
        mq.push(rng.uniform(0.0, 400.0 * WIDTH), i)
    peeked = []
    while not mq.empty():
        p = mq.min_key()
        k, _ = mq.pop_min()
        assert p == k, "min_key disagreed with the pop that followed it"
        peeked.append(k)
    assert peeked == sorted(peeked)
    print(f"[3b] min_key agreed with the following pop on all {len(peeked)} pops "
          f"(8-bucket window, {mq.overflow_events} reclaims from overflow)")

    # ---------------------------------------------------------------- [4] violation
    rng = random.Random(SEED + 3)
    ops: List[Tuple[str, float]] = [("push", rng.uniform(0.0, 50.0)) for _ in range(1000)]
    ops += [("pop", 0.0)] * 300
    ops += [("push", 0.001)]              # far below the current minimum
    ops += [("pop", 0.0)] * 701

    def replay(q) -> List[float]:
        out = []
        for op, val in ops:
            if op == "push":
                q.push(val, None)
            else:
                out.append(q.pop_min()[0])
        return out

    vq = BucketQueue(WIDTH, DEFAULT_N_BUCKETS, safe=True)
    got = replay(vq)
    ref = replay(HeapQueue())
    assert got == ref, "post-fallback pop sequence differs from the reference heap"
    tail = got[300:]
    assert all(tail[i] <= tail[i + 1] for i in range(len(tail) - 1))
    print(f"[4] deliberate violation: fell_back={vq.fell_back}, "
          f"violations={vq.monotone_violations}, pop sequence identical to a pure heap "
          f"driven with the same ops: yes")
    print(f"    minimum before the bad push {ref[299]:.4f}, next key popped {tail[0]:.4f}, "
          f"remaining tail non-decreasing: yes")

    # ---------------------------------------------------------------- [5] strict / factory
    sq = BucketQueue(WIDTH, 16, safe=False)
    sq.push(10.0, None)
    sq.pop_min()
    try:
        sq.push(1.0, None)
    except ValueError as exc:
        print(f"[5] safe=False refuses instead of degrading: {type(exc).__name__}")
    else:
        raise AssertionError("strict mode accepted a below-minimum push")

    print(f"[6] make_queue: None -> {type(make_queue(None)).__name__}, "
          f"0.0 -> {type(make_queue(0.0)).__name__}, "
          f"-1.0 -> {type(make_queue(-1.0)).__name__}, "
          f"inf -> {type(make_queue(_INF)).__name__}, "
          f"2.5 -> {type(make_queue(2.5)).__name__}")

    for bad in (float("nan"), _INF, -_INF):
        for q in (BucketQueue(WIDTH, 16), HeapQueue()):
            try:
                q.push(bad, None)
            except ValueError:
                pass
            else:
                raise AssertionError(f"{type(q).__name__} accepted key {bad}")
    print("[7] nan/+inf/-inf keys rejected by both structures: yes")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    _selftest()
