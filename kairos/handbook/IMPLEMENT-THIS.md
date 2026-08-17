# KAIROS — Implementation Brief

**Self-contained.** You do not need any other file to implement this. Everything required —
the mathematics, the algorithm, the exact test numbers, and the traps — is below. A working
300-line reference implementation ships alongside as `reference_min.py`; it is the thing to
port, and it passes every test in §7.

**Who this is for.** An engineer or coding agent implementing the algorithm from scratch in
any language. Python 3.9+, C++, Rust, Julia and Go have all been considered; nothing here
depends on language features beyond arrays, a priority queue, and `sqrt`/`atan2`.

**Time required.** About 2 days for the core (§6, gates M0–M4). The optional extras in §11
are a further week and are not needed for a working router.

---

## 1. What you are building

A ship routing algorithm: given a start port, a destination port, a ship, and a weather
forecast (ocean currents, wind, waves) that **changes during the voyage**, find the route
that arrives soonest.

The hard part is not the search. It is that the cost of every leg depends on *when* you
sail it. That single fact breaks Dijkstra's correctness, and the standard responses are all
expensive: add time to the state (dimension blow-up), march the whole domain forward in a
space-time grid, or accept an approximation.

KAIROS avoids the problem instead of paying for it.

### 1.1 You do not need any data to build this

**A\* does not ship with a map. Dijkstra does not ship with a road network. KAIROS does not
ship with an ocean.** Build the algorithm first; connect data later, or never.

The solver consumes exactly one interface:

```
field.at(lat, lon, t) -> { c_east, c_north, wind_east, wind_north, hs, tp, wave_dir, depth }
```

Anything satisfying that signature is a valid field — an analytic function, a synthetic test
case, a NetCDF file from ERA5 or INCOIS, a live OPeNDAP server, a CSV, or a mock in a unit
test. **The algorithm cannot tell the difference and must not be able to.** Every gate in §6
and every golden vector in §7 is checkable with a two-line analytic field and no network.

Keep this boundary strict and enforce it: no module in your solver should import a NetCDF,
HTTP or cloud library. In the reference project this is checked automatically — an AST scan
asserts that no core module imports the data layer, and the solver is then re-run with the
data layer disabled to prove it still works.

When you *do* want real data, write an adapter that implements `at()` and nothing else
changes. Verified working sources:

| Source | Gives you | Access |
|---|---|---|
| **HYCOM** GLBy0.08 (OPeNDAP) | ocean currents, 1/12° global | **open, no account** — easiest start |
| **ERA5** (Copernicus CDS) | wind + waves, hourly | free account + API key, `pip install cdsapi` |
| **INCOIS** | Indian Ocean waves/currents | registration for some products |
| **CMEMS / WaveWatch III** | waves, currents | account |

Ocean products carry `NaN` over land, which is a free land mask — and one guaranteed
consistent with the currents the solver actually sees, which a separate coastline database is
not.

---

## 2. The idea

Look at how ocean weather actually behaves over 2–5 days. A cyclone, a swell field, a
monsoon surge — these are, to leading order, **rigid patterns that move**. A cyclone travels
at 5–8 m/s along a track that stays steady for days. The pattern deforms slowly compared to
how fast it *translates*.

So most of the time-dependence is not evolution. **It is motion.** And motion depends on
which frame you measure it in.

> **Move with the weather, and the weather stops changing.**

In coordinates that translate with the weather system, the routing problem becomes
**stationary**: an ordinary shortest-path problem with no time dimension at all. Solve it
once, then work out when the ship meets its destination — which is now a *moving* target,
because a fixed point on Earth drifts backwards through the co-moving frame.

---

## 3. The theorem

Let `w` be the weather system's translation velocity. Assume:

- **A1 (frozen advection):** every field is a rigid translation of a fixed pattern,
  `E(x,t) = E₀(x − w·t)`.
- **A2 (outrun condition):** `|w| <` the ship's worst-direction speed made good. Physically:
  the ship can make ground faster than the system moves. If this fails, the honest answer is
  that you cannot escape the storm, and the algorithm says so.

Ship kinematics in the ground frame, where `V` is speed **through water** and `c` the current:

```
ẋ = V·n(θ) + c(x, t)
```

Substitute `y = x − w·t`, so `ẏ = ẋ − w`:

```
ẏ = V·n(θ) + c₀(y) − w
```

**The right-hand side no longer contains `t`.** That is the whole theorem. Shifting the drift
by `−w` shifts every achievable velocity by `−w`, and the time-dependence was nothing but the
motion of the pattern.

**Three consequences, all of which you get for free:**

1. No causality/FIFO condition to check — there is no time-dependence left to violate it.
2. No time-expanded state, no space-time march, no wait relaxation.
3. **No temporal discretisation error**, because there is nothing to sample in time. Measured:
   the co-moving solve's feasibility error was `2.8e-14` m/s where the ground-frame solve's
   was `6.7e-3`. It is not merely faster — it is *more accurate on the same grid*.

**This has been verified.** Taking the co-moving route, mapping it back to the ground frame,
and checking leg by leg that the required through-water velocity is achievable against the
*advected* field gives a residual of **9.77e-14 m/s** where the theorem says exactly zero.

**In code, the reduction is one line: subtract `w` from the drift vector.** No new metric
code, no new solver. That is genuinely all it is.

---

## 4. The mathematics you need

### 4.1 Geodesy

Radians internally, degrees only at input/output. Earth radius **exactly 6 371 000.0 m** (the
golden tests depend on it).

Great-circle distance — use **haversine**, not the spherical law of cosines (`acos` loses ~6
significant figures at the ~28 km spacing of adjacent grid nodes):

```
a = sin²(Δφ/2) + cos φ₁ · cos φ₂ · sin²(Δλ/2)
d = 2 R asin(√a)
```

Wrap `Δλ` into `(−π, π]` **before** using it, or every route crossing the antimeridian breaks.

Heading to vector: `n(θ) = (sin θ, cos θ)` — **east first**, `0 = north`, clockwise. Fix this
now and never revisit it; a transposed east/north bends routes the wrong way around currents
while looking entirely plausible on a map.

### 4.2 Speed made good — the one function that matters

Given a requested direction of travel `u` (unit, east/north), through-water speed `V`, and
drift `c`, split the drift along and across the track:

```
c∥ = ⟨c, u⟩                    (along)
c⊥ = −c_e·u_n + c_n·u_e        (across)
σ  = √(V² − c⊥²) + c∥          speed made good over ground
```

The ship must crab into the cross-track current to hold the track, which costs speed;
whatever is left adds to the along-track component. Cost per metre is `1/σ`.

**Two guards, both mandatory, both routine in real oceans:**

- `|c⊥| ≥ V` → the current sets the ship sideways faster than it can crab back. No heading
  holds the track. `√` of a negative. **Return 0 (infinite cost). Do not raise** — this
  happens routinely in the Agulhas and Somali Currents and must not abort a voyage plan.
- `σ ≤ 0` → the ship is pushed backwards along the track. Also return 0.

### 4.3 The closed form, and its two traps

For constant through-water speed the metric has an exact form (this is the classical Randers
metric; Zermelo 1931, Bao–Robles–Shen 2004):

```
λ = V² − |c|²
F(v) = [ √(⟨v,c⟩² + λ|v|²) − ⟨v,c⟩ ] / λ
```

**Trap 1 — `λ ≤ 0` returns a NEGATIVE cost.** When drift exceeds ship speed the formula
silently returns e.g. `F = −1.25`. Not NaN, not an exception: a plausible finite number with
the wrong sign. In a shortest-path solver that is a negative cycle — non-termination, or
arrival times in the past. **Guard `λ > 0` before dividing. Every time.**

**Trap 2 — catastrophic cancellation on the following-current branch.** When `⟨v,c⟩ > 0` the
numerator subtracts two nearly-equal positive numbers and loses up to 8 significant digits —
worst exactly where currents are strongest. Use the algebraically identical conjugate form:

```
⟨v,c⟩ ≤ 0 :   F = [ √(⟨v,c⟩² + λ|v|²) − ⟨v,c⟩ ] / λ     (safe: adding)
⟨v,c⟩ > 0 :   F = |v|² / [ √(⟨v,c⟩² + λ|v|²) + ⟨v,c⟩ ]   (conjugate: adding)
```

### 4.4 The co-moving shift

```
c_effective(y) = c₀(y) − w
```

That is the entire implementation of §3. Because the shifted set is still a disc centred on a
drift vector, the closed form of §4.3 **still applies** with `c ← c₀ − w`. Everything carries
over.

The admissibility condition becomes `|c₀(y) − w| < V`, which is the precise statement of "the
ship can work against this system."

### 4.5 Interception — the destination moves

In the co-moving frame a fixed ground point `x_B` traces the line `y(t) = x_B − w·t`. So you
need the node whose *own* arrival time makes its ground landfall coincide with the target:

```
find the node y minimising  ‖ (y + w·T[y]) − x_B ‖
```

Every node carries its own arrival time `T[y]`, hence its own ground landfall `y + w·T[y]`.
Scan them all: `O(N)`, one haversine per node, milliseconds.

### 4.6 Route recovery

```
x(s) = y(s) + w · τ(s)
```

Backtrack the parent chain in the co-moving frame; map each waypoint to the ground using
*that waypoint's* arrival time.

---

## 5. The algorithm

```
INPUT   ship speed V, current field c(x,t), start x_A, destination x_B, horizon t_max
OUTPUT  route as (lat, lon, time) waypoints, and arrival time

1. CHOOSE w
     Pick the weather translation velocity (see §5.1).

2. BUILD THE CO-MOVING FIELD
     c_eff(y) = c₀(y) − w,  where c₀ is the forecast snapshot at t₀.
     This field is STATIONARY: it takes no time argument.

3. SIZE THE GRID                                            ← easy to get wrong, see Trap 3
     Dilate the domain by |w|·t_max OPPOSITE to w, beyond the ground bounding box.

4. STATIONARY SWEEP
     Ordinary Dijkstra from x_A on the co-moving grid, edge cost = distance / σ.
     No causality check. No time in the state. This is a plain shortest-path solve.

5. INTERCEPTION
     goal = argmin over nodes of ‖(y + w·T[y]) − x_B‖          (§4.5)
     arrival = T[goal]

6. ROUTE RECOVERY
     Backtrack from goal; map each waypoint x = y + w·τ.        (§4.6)
```

That is the whole algorithm. Steps 4–6 are under 100 lines.

### 5.1 Choosing `w`

Two options, in increasing order of effort:

**(a) Use the forecast's storm track.** If your data gives cyclone centre positions over time,
`w` is the finite difference of successive centres. Simplest and usually good enough.

**(b) Optimise it.** Choose `w` to minimise how fast the field still changes in the co-moving
frame — i.e. minimise `max_u |∂F/∂t|` (99th percentile over the domain, not the max, so one
pathological cell cannot steer the choice) by a coarse-to-fine grid search over `w`. Three
rounds of 9×9 is ample.

**Do not use phase correlation / image registration.** It was tried and it **failed badly** —
returned `w = (−0.74, 0.00)` against a true `(2.0, 0.5)`, because it locks onto whichever
feature carries the most gradient energy rather than the one governing the routing cost.

**Important honesty note:** option (b) is *not* an estimate of the meteorological advection
velocity, and must not be reported as one. Once the frozen-advection assumption is violated,
minimising the residual and estimating the storm track are different problems, and the solver
wants the former.

### 5.2 When A1 does not hold exactly

Real weather is not one rigid pattern: systems intensify, deform, and move at different
speeds. The reduction then becomes a **preconditioner** rather than an exact solution — apply
it anyway and handle the leftover with a conventional time-dependent method.

Measured, on a deliberately adversarial field (translating jet + 35 %/day intensification + a
second system moving in a different direction):

| | ground frame | co-moving |
|---|---|---|
| causality diagnostic `r·L_t` | **1.31 — violated** | **0.26 — fine** |
| reduction at 99th percentile | — | 4.6–5.0× |
| **reduction at the median** | — | **0.22× — it gets WORSE** |

So it takes a field where a single-pass solve is *not licensed* and makes it licensed. But the
median cell degrades ~4.5×: de-advection trades a large improvement in the worst cells for a
modest loss in already-benign ones. Because the licence is a worst-case condition that is the
right trade — but it is a trade, and reporting only the max would oversell it.

---

## 6. Build order, with gates that can fail

**Do not skip a gate.** Routing bugs produce plausible wrong maps; you cannot eyeball
correctness. Each gate below fails loudly when the thing above it is broken.

### M0 — Geodesy (1 hour)
Implement `wrap_pi`, `haversine`, `initial_bearing`, `heading_to_vec`, `metres_to_dlatlon`.

> **Gate:** `haversine(0°N 0°E, 0°N 90°E) = 10 007.543 398 010 3 km` — this must equal
> `2πR/4` exactly. If it does not, your radius constant or `asin` guard is wrong. This single
> check catches most geodesy errors.

### M1 — Speed made good (1 hour)
Implement §4.2 including both guards.

> **Gate:** the eight vectors T1–T8 in §7, to 12 significant figures. T7 and T8 must return
> **zero**, not an exception and not a NaN.

### M2 — The closed form (30 minutes)
Implement §4.3 with both branches and the `λ` guard.

> **Gate:** `F(following, |c|/V = 0.9) = 1/13.68 = 0.073 099 415 204 678` exactly, and
> `λ ≤ 0` returns `+∞`. Verify the naive form loses digits where the conjugate form does not —
> print both and look at them.

### M3 — Grid and stationary sweep (4 hours)
Regular lat/lon grid, 16-neighbour connectivity, per-row leg cache, Dijkstra.

> **Gate:** with **zero** current, arrival time must equal `great-circle distance / V` to
> within the stencil's discretisation error (a few percent). If it is wildly off, your leg
> cache is broken — see Trap 1.

### M4 — Co-moving reduction (2 hours)
`CoMoving` class: `drift`, `to_ground`, `to_comoving`, `required_dilation_m`. Then
interception and route recovery.

> **Gate — the decisive one.** Take the route your solver produces, map it to the ground
> frame, and check leg by leg that the required through-water speed `|v − c_ground(x, t)|` is
> `≤ V`, sampling the **advected** field at each waypoint's actual position and actual time.
> The excess must be `~1e-13`, i.e. floating-point zero. **If it is not, the reduction is
> wrong somewhere.** This test needs no reference solution and is insensitive to grid
> resolution.

### M5 — Sanity against a conventional solver (2 hours)
Write a plain time-dependent Dijkstra in the ground frame and compare on the same grid.

> **Gate:** agreement within ~1 %. Measured on a 3698 km voyage: ground-frame 141.2107 h vs
> co-moving 139.9963 h, **0.860 % apart**. Do not expect exact agreement — both carry a
> fixed-stencil metrication floor (see §10).

---

## 7. Golden test vectors

Computed at 50-digit precision from the closed forms. **Exact reference values** — if your
implementation disagrees, it is wrong. Match to 12 significant figures.

### Geodesy

| From | To | Distance | Bearing |
|---|---|---|---|
| 0.00 N, 0.00 E | 0.00 N, 90.00 E | **10 007.543 398 010 3 km** | 90.000000° |
| 18.95 N, 72.95 E | 29.92 N, 32.55 E | **4 243.611 km** | 294.619° |
| 13.09 N, 80.29 E | 1.26 N, 103.85 E | 2 908.549 km | 114.975° |

### Speed made good — `V = 7.2 m/s`

| # | Case | `c∥` | `\|c⊥\|` | expected `σ` [m/s] |
|---|---|---|---|---|
| T1 | no current | 0 | 0 | **7.2** exact |
| T2 | pure following | +1.5 | 0 | **8.7** exact |
| T3 | pure head | −1.5 | 0 | **5.7** exact |
| T4 | pure cross | 0 | 1.5 | **7.042 016 756 583 30** |
| T5 | 30° off a 1.5 m/s current | +1.299 038 105 676 66 | 0.75 | **8.459 869 063 044 66** |
| T6 | near-degenerate, `\|c\|/V = 0.95` | −6.84 | 0 | **0.36** exact |
| T7 | drift exceeds speed | −8.0 | 0 | **0** (blocked) |
| T8 | cross-dominated | 0 | 7.5 | **0** (infeasible) |

Check by hand: T4 is `√(7.2² − 1.5²) = √49.59`. T5 is `√(51.84 − 0.5625) + 1.5 cos30°`.

### End-to-end, uniform current

`V = 7.2 m/s`, uniform 1.5 m/s eastward current, along the equator from 0°E to 5°E
(exactly 555 974.633 2 m):

| | `σ` | arrival |
|---|---|---|
| with the current | 8.7 | **17.751 425 h** |
| against | 5.7 | **27.094 280 h** |

The ratio `27.094280 / 17.751425 = 1.526 315 789 5` must equal `8.7/5.7` **to all printed
digits**. These come from completely different code paths, so agreement to 10 figures is
strong evidence both are right. Run this on every commit.

---

## 8. The traps — all of which fail *silently*

Every one of these was hit during development. None produces an error message; all produce a
converged, plausible-looking, wrong route.

**Trap 1 — negative array indices in the leg cache.** Leg geometry depends only on the grid
*row* and the neighbour offset, so it is cached per row. If you reference from column 0, then
offset `dj = −2` asks for column `−2` — which in Python (and any language that wraps) returns
a column at the *other edge of the map*. Measured: a **4020 km leg instead of 57.9 km**,
bearing 142° wrong, arrival **10 419 h instead of 141 h**.
*Fix:* reference from column `≥ max|dj|`. *Signature:* absurd arrival times, or routes that
jump across the domain.

**Trap 2 — `λ ≤ 0` unguarded.** Negative edge costs. *Signature:* non-termination, or arrival
times in the past.

**Trap 3 — co-moving grid not dilated.** The solve lives in `y = x − w·t`, so the target node
sits `|w|·t*` away from `x_B` — on a 140 h voyage with `|w| = 1.4 m/s` that is ~500 km. If
your grid does not cover it, **no node maps anywhere near the target**. Measured: a **104.5 km
landfall miss that a full-grid scan could not reduce.**
*Fix:* extend the domain by `|w|·t_max` opposite to `w`. *Signature:* the best achievable miss
over the *whole grid* is large.

**Trap 4 — selecting the goal node by root-finding on `t`.** `g(t) = T(x_B − w·t) − t` is a
**step function** when `T` is sampled at the nearest node, so a bisection converges to a
discontinuity rather than a root, and `T` at the returned node can be far from `t*`. The error
is then amplified by `|w|`. *Fix:* scan the grid directly as in §4.5.

**Trap 5 — transposed east/north.** *Signature:* routes bend the wrong way around currents.
*Discriminating test:* with a 1.5 m/s **eastward** current, `σ` due east must be 8.7, due west
5.7, due north 7.042. If east and west swap, your along-track sign is flipped; if north gives
8.7 or 5.7, your components are transposed.

**Trap 6 — wave direction "from" vs "towards".** Meteorological convention is "from"; the
solver wants "towards". Convert once at the data boundary. *Signature:* head and following
seas swapped — speed loss appears where it should not.

---

## 9. The reference implementation

`reference_min.py`, alongside this file. Standard library only, no dependencies, ~300 lines,
ordered so each piece only uses the pieces above it. Run `python reference_min.py`; all 15
checks should print `PASS`.

It contains, in order: geodesy → speed made good → Randers closed form → grid with per-row leg
cache → `CoMoving` → stationary sweep → interception → route recovery → the self-test.

Port it section by section, running the gates of §6 as you go.

---

## 10. What "done" looks like

Publish this table. Nobody else in this space shows their error bars, and it is the difference
between "it works" and "we know it works":

| Quantity | Target |
|---|---|
| Max error vs the golden vectors of §7 | `< 1e-12` |
| Bijection residual (M4 gate) | `< 1e-13` m/s |
| Landfall miss | `<` half a grid diagonal |
| Agreement with a ground-frame solver | `~1 %` |
| Zero-current arrival vs `distance / V` | within stencil error |

**One thing to expect and not be alarmed by.** Refining the grid will *not* drive the
co-moving-vs-ground-frame difference to zero. Measured across `h = 24, 16, 12, 8, 6, 4, 3 km`
the discrepancy oscillated `0.36, 0.15, 0.79, 0.92, 0.17, 0.98, 0.58 %` with **no convergence
trend**. That is not a bug in the reduction — it is the fixed-neighbour stencil quantising
heading, an error that does not vanish as `h → 0`. Removing it needs a continuum-heading
(semi-Lagrangian) update, which is §11.

---

## 10.1 Making it fast and accurate — do this AFTER the gates pass

Do not optimise before M5. But when you do, these are measured, not guessed.

### The one optimisation that matters: cache the edge midpoint

Profiling showed **61 % of runtime in field evaluation** (63 943 calls for 4 027 expansions —
one per edge relaxation), not in the search. So attack that.

Every undirected edge is relaxed **twice**, once from each endpoint, and both relaxations
sample the field at the **same midpoint**. In the co-moving frame the field is stationary, so
those two samples are *identical* and the second is free.

> **A time-dependent solver cannot do this.** Its two visits to that midpoint happen at
> different arrival times, so it must re-interpolate. This is the single structural speed
> advantage of the reduction — take it.

To make it possible, split the field interface in two:

```
sample(x, y)              -> field value    EXPENSIVE (a forecast interpolation). Cache this.
speed_from(field, u)      -> speed          CHEAP (~10 flops). Call it twice per edge.
```

The cached quantity must be **direction-independent**, which is why the split is necessary
rather than cosmetic. Key the cache on the *canonical* edge (use `min(a,b)` plus the
opposite-offset index) so both directions hit the same slot.

**Do NOT eagerly tabulate the whole lattice.** Measured: **2.6× worse**, at every field cost.
Eager precomputation fights A* — it costs `O(V·m)` evaluations over the whole domain while A*
expands only a fraction of it. Lazy caching wins; eager loses.

### A\*: you have an exact admissible heuristic

The stationary form admits a heuristic a time-dependent solver has no analogue for — the exact
minimum time to intercept the moving destination at maximum speed. From node `y` at time `τ`,
with `a = dst − w·τ − y`:

```
h = [ √(⟨a,w⟩² + (s²−|w|²)|a|²) − ⟨a,w⟩ ] / (s²−|w|²)          s = max speed
```

That is **the Randers formula again**, reached independently. Admissible (true speed never
exceeds `s`) and consistent (metric-derived), so no reopening. Use the conjugate branch when
`⟨a,w⟩ > 0`, same as §4.3. Measured: **1.9× faster, 2.3× fewer expansions.**

Stop as soon as a popped node's ground landfall is within half a cell of the target.

### Measured speed, against conventional time-dependent Dijkstra

| field-evaluation cost | conventional | optimised | |
|---|---|---|---|
| cheap analytic | 0.357 s | **0.140 s** | 2.55× faster |
| ~200 flops | 2.048 s | **0.421 s** | 4.87× faster |
| ~1000 flops | 8.027 s | **1.254 s** | **6.40× faster** |

**The advantage grows with field cost**, which is the direction real data pushes — a forecast
lookup is a quadrilinear interpolation over several variables, not a formula.

Also worth doing: flat neighbour arrays (the naive version allocates a fresh list of tuples per
call), and a 2-tuple heap with lazy deletion instead of carrying a 3-tuple.

### Precision: use a 32-neighbour stencil

Measured against the exact answer in a uniform field, averaged over 13 headings spanning all
directions, `h = 2.5 km`:

| stencil | neighbours | mean error | max error | relative cost |
|---|---|---|---|---|
| `r ≤ 1` | 8 | 5.49 % | 9.66 % | 1.0× |
| `r ≤ 2` | 16 | 1.27 % | 3.13 % | 2.6× |
| **`r ≤ 3`** | **32** | **0.57 %** | **1.68 %** | 4.6× |
| `r ≤ 4` | 48 | 0.43 % | 1.14 % | 7.1× |

Generate the offsets as all `(i,j)` with `max(|i|,|j|) ≤ r` and `gcd(|i|,|j|) = 1`.
**32 is the sweet spot** — 9.6× less error than the 8-neighbour default, and the speed work
above more than pays for it.

**What did not work:** a 2-point semi-Lagrangian (interpolated) update, which in principle
removes the direction-quantisation floor entirely. Measured gain: **1.02×, i.e. nothing** —
too few qualifying segment pairs fired. Right idea, wrong implementation. If you get it
working properly, that is the next real accuracy step and worth telling us about.

---

## 11. Deliberately out of scope

Build the core first. These are all real improvements and none is needed for a working router:

- **Continuum-heading semi-Lagrangian update** — removes the ~1 % metrication floor of §10.
  The highest-value next step for accuracy.
- **Anisotropy-adaptive wide stencil** (ordered upwind) — required for *correctness*, not just
  accuracy, once currents get strong relative to ship speed.
- **Multi-objective** (time / fuel / risk) with ε-Pareto labels — returns a whole front of
  routes rather than one. Note that a weighted-sum sweep can only ever find the *convex hull*
  of the Pareto set, and ship-routing fronts are non-convex, so scalarisation provably misses
  the interesting compromise routes.
- **Throttle as an explicit control** — needed before fuel is a meaningful objective at all.
- **Seakeeping constraints** (IMO MSC.1/Circ.1228: parametric roll, slamming, broaching) —
  needed before "safety" means anything.
- **Optimality certificate** — solve a coarse *optimistic* problem for a provable lower bound,
  then report `(J − bound)/bound` as a rigorous suboptimality gap on any route.
- **Residual corrector** for when assumption A1 is violated (§5.2).

---

## 12. Honest limitations

State these; a reviewer will find them otherwise.

- **A1 is a strong assumption.** Exact only for an isolated, coherently translating system. It
  holds well for tropical cyclones and monsoon surges over 2–5 days — the cases that matter
  most for Indian Ocean safety routing — and degrades for merging or rapidly deepening
  systems, where it becomes a preconditioner rather than a solution.
- **A2 is required** for an interception to exist. Where it fails, the correct answer really is
  *you cannot outrun this storm*, and the algorithm should report that rather than a route.
- **The underlying transformation is classical.** A Galilean change of variables to make an
  advected field stationary is old — Taylor's frozen-field hypothesis (1938) is the same idea
  in meteorology. What appears to be new is applying it to routing and quantifying what it
  buys. Do not claim new mathematics.
- **All numbers here come from synthetic fields.** No validation against real forecast data or
  AIS tracks yet.
