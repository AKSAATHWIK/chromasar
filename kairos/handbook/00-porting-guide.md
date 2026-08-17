# KAIROS Implementation Handbook — Porting Guide

**Audience:** an engineer implementing KAIROS from scratch in C++, Rust, Julia, Go or
Python, who has read `spec/` and wants to know the order to build things and how to know
each piece is right before moving on.

**The governing principle:** every milestone below ends with an *acceptance test that can
fail*. Do not proceed past a milestone whose test you have not seen pass with your own eyes.
Routing bugs are insidious — a wrong sign in the drift correction produces routes that look
completely plausible on a map and are 15 % worse than optimal. The map will not tell you.
The tests will.

---

## The dependency graph

```
      geodesy ──┬─► grid ──────────────┐
                │                      ├─► sweep ─► api
      types ────┼─► seakeeping ─┐      │      ▲
                │               ├─► metric ───┘
                └─► powering ───┤      │
                                │      ├─► heuristic
      environment ──────────────┘      │
                                       ├─► labels ─► bucketqueue
                                       └─► polish
```

Nothing above `metric` knows about the algorithm. Nothing below `metric` knows about ships.
That separation is the whole reason the thing is portable — hold the line on it.

---

## M0 — Geodesy (half a day)

Implement: `haversine`, `initial_bearing`, `destination`, `wrap_pi`, local-frame conversion.

**Non-obvious requirements:**
- Use haversine, not the spherical law of cosines. At 0.125° spacing adjacent nodes are
  ~14 km apart and `acos` loses ~6 significant figures there.
- Wrap the longitude difference *before* using it, or every route crossing 180° is wrong.
- `heading_to_vec(θ) = (sin θ, cos θ)` — **east first**. Fix this convention now and never
  revisit it. Half of all porting bugs are a transposed east/north.

**Acceptance test M0:**
```
haversine(JNPT 18.95N 72.95E, Suez 29.92N 32.55E) = 4243.611 km   (great circle, not the
                                                                  sailing route round Yemen)
haversine(0N 0E, 0N 90E)           = 10 007.543 km      (= quarter circumference, exact check)
destination(x, bearing(x,y), d(x,y)) == y               to 1e-9 rad
wrap_pi(3π)                        == π
bearing due east at the equator    == π/2 exactly
```

---

## M1 — Vessel and powering (1 day)

Implement: `calm_power`, `added_resistance_waves`, `wind_resistance`, `delivered_power`,
`attainable_speed`, `fuel_rate`.

**The one lemma that matters:** `delivered_power(V)` must be *strictly increasing* on
`(0, V_max_hull]`, because the whole attainable-speed root find depends on the root being
unique. The Admiralty form `P = P_ref (V/V_ref)^n` satisfies it for any `n > 0`. If you
plug in a measured speed–power spline, **check monotonicity at load time** and, if it fails,
take the *smallest* root — that is the physically attainable speed, and the larger roots are
on an unreachable branch.

**Root find:** bracket on `[0, V_max_hull]`, then Brent or bisection-with-Newton. Never
plain Newton — the added-resistance term makes the curve stiff in heavy seas and Newton
walks off. Tolerance `1e-4 m/s` (0.0002 kt) is far below any physical meaning and costs
~8 iterations.

**Acceptance test M1:**
```
calm water,  q = 1.0   →  V ≈ V_max_hull  (power-limited or hull-limited, whichever binds)
6 m head sea, q = 1.0  →  V is 10-30 % below the calm-water value
6 m following sea      →  speed loss strictly smaller than in head sea
q = 0.5                →  V ≈ V_calm · 0.5^(1/3)   (Admiralty cube law, ±2 %)
fuel_rate at q = 0.75  →  strictly less per unit distance than at q = 1.0
```
That last one is the SFOC bowl doing its job. If fuel per mile is monotone in speed, your
SFOC model is flat and the entire Pareto front will collapse to a line later. Fix it here.

---

## M2 — Seakeeping ban set (1 day)

Implement S1–S7 as a bitmask, plus a *continuous* `risk_level`.

**Why two functions.** `violations()` is discrete (banned or not) and drives feasibility.
`risk_level()` must be continuous in `(V, θ)` because it is an *objective*, and a
discontinuous objective makes the Pareto front ragged and the label pruning unstable. Build
`risk_level` as a smooth blend of the margin to each criterion, not as `1.0 if banned`.

**The one with real geometry:** parametric roll (S2) bans a *ring* in `(V, θ)` space — the
locus where `ω_e ≈ 2ω_φ`. Encounter frequency

```
ω_e = ω_p − (ω_p² V / g)·cos μ_rel
```

is monotone in `V` for fixed `μ_rel`, so for each heading the ban is an interval in `V`;
sweeping heading traces the ring. **Plot it.** If your parametric-roll region is not a
closed band in following/quartering seas, the sign of `cos μ_rel` is flipped.

**Acceptance test M2:** print the admissible set over a 72 × 40 grid of (heading, speed) for
`H_s = 5 m, T_p = 11 s`, and check:
```
head seas at full speed        → slamming fires
beam seas                      → lateral acceleration fires first
following seas at high Fn      → surf-riding fires
the parametric-roll region is a closed band, not a half-plane
H_s = 0                        → nothing fires
```

---

## M3 — The metric (2 days) — **the core**

Implement `RandersMetric` first, then `FinslerMetric`, then `SupportTable`.

### M3a — Randers closed form

```
λ = V_s² − |c|²
F(v) = [ sqrt(⟨v,c⟩² + λ|v|²) − ⟨v,c⟩ ] / λ
```

**The stability trap.** When `⟨v,c⟩ > 0` (following current) the numerator is a difference
of two nearly-equal positive numbers and you lose up to 8 digits. Use the conjugate form:

```
⟨v,c⟩ ≤ 0 :   F = [ sqrt(⟨v,c⟩² + λ|v|²) − ⟨v,c⟩ ] / λ        (safe: adding)
⟨v,c⟩ > 0 :   F = |v|² / [ sqrt(⟨v,c⟩² + λ|v|²) + ⟨v,c⟩ ]     (conjugate: adding)
```
Both are algebraically identical; only the second is numerically safe on the following-
current branch. This is not a micro-optimisation — at `|c|/V_s = 0.9` the naive form is
wrong in the 8th digit, which is enough to break the `1e-12` acceptance test and to make the
convergence study report a garbage order.

**The `λ ≤ 0` trap.** When `|c| ≥ V_s` the formula returns a **negative** `F`, silently.
A negative cost in a shortest-path algorithm is catastrophic — it produces negative cycles
and the sweep never terminates. **Guard `λ` before you divide, always.** Verified behaviour:
see golden vector T7 in [01-golden-vectors.md](01-golden-vectors.md).

### M3b — Speed made good, and the drift-correction fixed point

For a requested unit direction `u`, decompose the drift into along- and cross-track
components `c_∥ = ⟨c,u⟩`, `c_⊥ = c − c_∥u`. Then

```
σ(u) = sqrt(V² − |c_⊥|²) + c_∥       provided |c_⊥| < V
```

with the ship's heading crabbed off `u` by `arcsin(−c_⊥/V)`.

**The subtlety nobody mentions:** `V` itself depends on the heading (waves are directional),
and the heading depends on `V` through the crab angle. It is a fixed point. Iterate:

```
V₀ ← attainable_speed(θ = direction of u)
repeat 3-4 times:
    θ ← heading(u) + arcsin( −c_⊥ / V )
    V ← attainable_speed(θ)
```
It converges geometrically because `∂θ/∂V` is small whenever `|c_⊥|/V` is not near 1. Cap
the iterations and, on non-convergence, mark the direction infeasible rather than returning
a half-converged number.

### M3c — Throttle family (design decision D1)

`legs(u)` returns the *Pareto-nondominated set* over throttle, not a single value. Five
throttle samples `q ∈ {0.15, 0.35, 0.55, 0.75, 1.0}` is enough; the SFOC bowl means the
non-dominated set is usually 2–4 entries after pruning. **The time-only solver should call
`sigma_max` instead and never build the family** — that is a 5× saving on the hot path.

**Acceptance test M3:** the golden vectors of
[01-golden-vectors.md](01-golden-vectors.md), all eight, to 12 significant figures. Plus:
`FinslerMetric` with waves off, bans off, constant speed must reproduce `RandersMetric` to
`1e-10`.

---

## M4 — Grid and stencil (1 day)

Regular lat/lon grid, node index `n = i·n_lon + j`.

**Cache geometry per row, not per node.** Edge length and bearing between `(i,j)` and
`(i+di, j+dj)` are independent of `j`. This is a ~40× saving in the inner loop and the
existing prototype already does it — copy that idea.

**The neighbour template.** `neighbours_within(i, j, r)` must not scan a bounding box every
call. Precompute, per row `i`, the list of `(di, dj)` offsets whose great-circle distance is
`≤ r`. Rows near the poles have far more longitudinal neighbours within a given metric
radius — that asymmetry is real and must not be clipped away.

**Acceptance test M4:** node count and memory for a 0.5° Indian Ocean grid
(lat −40…30, lon 20…120): 141 × 201 = 28 341 nodes. Neighbour template size at `r = 2h`
should be ~12 offsets at the equator and grow toward the poles. Time `neighbours_within`;
you want > 10⁶ calls/s or the sweep will be dominated by it.

---

## M5 — Bucket queue (half a day)

Dial's monotone bucket queue, width `Δ = h·F_min`.

**Correctness condition:** keys are never pushed below the current minimum. This holds
because every edge costs at least `h·F_min > 0`. **Do not assume it — count violations.**
If one occurs (it can, in a strong-drift cell where `F_min` is not what you assumed), fall
back to a binary heap for the remainder of the run and log it. A single anomalous cell must
not corrupt a voyage plan, and it must not silently corrupt one either.

**Acceptance test M5:** push 200 000 monotone keys, pop all, assert the popped sequence is
non-decreasing. Then deliberately violate monotonicity and confirm the fallback triggers
*and the output is still correctly ordered*.

---

## M6 — The sweep (3 days) — the second core

Anisotropy-adaptive ordered upwind. Build it in three strictly increasing stages, and test
each:

**Stage 1 — plain Dijkstra on the node graph.** No `ζ` minimisation, no wide stencil. This
is your fallback path forever after, and it must always remain in the code. Test: it
reproduces the old A* baseline's answer on the same graph.

**Stage 2 — add the semi-Lagrangian `ζ` minimisation** over accepted-front edges. This is
what removes the heading quantisation. Test: on a uniform current field the arrival-time
error versus the exact Randers distance must *drop* when you go from Stage 1 to Stage 2 at
the same grid resolution. If it does not, the `ζ` search or the interpolation is wrong.

**Stage 3 — add the wide anisotropic stencil,** radius `r = h·Υ_loc` over the ball. Test:
construct a strong-shear field where `Υ ≈ 3` and confirm Stage 3 beats Stage 2. In a weak
field the two agree — that agreement is itself a good regression test.

**The single most important implementation detail:** in the update

```
T(x) = min over front edges, min over ζ:  T̃(ζ) + |x − ξ(ζ)| · F( x, T̃(ζ), (x−ξ)/|x−ξ| )
```

the metric is evaluated at the **departure** time `T̃(ζ)`, not at the arrival time `T(x)`.
Evaluating at the arrival time makes the update implicit, circular, and wrong — and it will
still produce plausible-looking routes. This is the difference between an algorithm licensed
by Theorem 3.1 and a heuristic that happens to converge sometimes.

**FIFO guard.** Estimate `L_t` per cell by finite differences across forecast frames. Where
`h·L_t > 0.95`, use the wait relaxation. **Count the flagged cells and report the count** —
it is a one-line proof that your solve was legitimate.

**Acceptance test M6 — the convergence study.** Uniform current, constant speed, bans off.
Compute arrival time at 1.0°, 0.5°, 0.25°; compare against the exact Randers value. The
errors must decrease monotonically, and roughly halve per refinement. **If the error
plateaus, the scheme is inconsistent** — almost always because the `ζ` minimisation is being
skipped or the stencil is too narrow.

---

## M7 — Labels, heuristic, polish (2 days)

**Labels.** Bucket on the objective *value*, not the increment — that is what makes the
guarantee a clean `(1+ε)` instead of `(1+ε)^D`. Never bucket objective 0 (time).

**Heuristic.** The optimistic coarse solve must take its per-cell optimistic metric over the
**dilated** cell (the cell plus a one-cell margin), not the bare cell. A fine path can clip
a corner of a coarse cell without entering its interior; without the dilation the heuristic
is inadmissible, the search is no longer optimal, and you will not notice because the routes
still look fine.

**Polish.** Zermelo shooting with Newton on the terminal miss. Cap at 8 iterations; on
failure return the grid route and flag the leg as a suspected cut locus rather than shipping
a non-converged trajectory.

**Acceptance test M7 — the sharpest test in the project:**
> In a **uniform** current field, Zermelo's navigation formula gives `dθ/dt ≡ 0`. The optimal
> route is therefore a **single constant heading with zero intermediate turns.**

Measure `max |dθ/dt|` over the route. It must be ~1e-15, not ~1e-6. Any waypoint your router
emits in a uniform current field is a numerical artefact, and this test finds it instantly.

---

## M8 — Repair and API (1 day)

Localised front repair: diff the metric tables, take cells that changed materially **and**
have `T(x) > t_now`, take the dependency closure, re-open, resume. The past is immutable —
the ship has already sailed it.

**Acceptance test M8:** perturb the forecast in a 5 % patch, re-optimise, and confirm (a) the
answer matches a cold solve to within tolerance, and (b) the work done is a small fraction of
the cold solve. Report the measured ratio; anything above ~0.2 means your closure is too
conservative.

---

## Total effort

About **12 working days** for one competent engineer who reads the spec first. The two cores
(M3 metric, M6 sweep) are half of that and all of the risk. Everything else is mechanical.

## Order of failure — where ports actually break

In descending order of how often we would expect it, based on what the mathematics is
sensitive to:

1. **East/north transposed** somewhere in the drift correction. Symptom: routes bend the
   wrong way around currents.
2. **Metric evaluated at arrival time instead of departure time.** Symptom: works, converges,
   answers are ~2–5 % off and nothing looks wrong.
3. **`λ ≤ 0` unguarded.** Symptom: non-termination or absurd negative arrival times in
   strong-current cells.
4. **`ζ` minimisation skipped** or done on the wrong interval. Symptom: error plateaus under
   grid refinement.
5. **Wave direction "from" vs "towards"** mixed. Symptom: head and following seas swapped;
   speed loss appears where it should not.
6. **Bucketing on increments instead of values** in the label set. Symptom: Pareto front
   degrades as routes get longer.
7. **Heuristic without dilation.** Symptom: subtly suboptimal routes, no visible error.
