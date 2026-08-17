# Complexity: KAIROS versus everything else

**Short answer: KAIROS is the same asymptotic order as FIFO time-dependent Dijkstra, and in
wall-clock terms it is currently *slower* because of a spatial dilation penalty. Its wins are
correctness, licensing and accuracy — not speed.**

That is worth stating bluntly up front, because it is easy to assume a new method must be
faster, and claiming so here would be false.

Notation: `V` nodes, `E` edges, `m` neighbours per node (so `E = mV`), `K` time layers,
`Υ` anisotropy coefficient, `d` spatial dimensions (2 here), `Λ` Pareto labels per node.

---

## 1. The table

| Method | Time complexity | Space | Optimal? | Needs FIFO? | Notes |
|---|---|---|---|---|---|
| **Dijkstra** (stationary) | `O(E + V log V)` Fib. heap; `O(E log V)` binary heap | `O(V)` | exact on the graph | n/a — no time | the baseline everything is measured against |
| **A\*** (stationary) | same worst case; far fewer expansions with a good heuristic | `O(V)` | exact if heuristic admissible | n/a | heuristic quality is everything |
| **Fast Marching** (isotropic) | `O(V log V)` | `O(V)` | converges to viscosity solution | n/a | **continuous** headings; wrong under anisotropy |
| **Ordered Upwind** (anisotropic) | `O(Υ V log V)` | `O(V)` | converges | n/a | Sethian–Vladimirsky 2003 |
| **Time-dependent Dijkstra, FIFO holds** | `O(E log V)` | `O(V)` | exact | **yes** | Kaufman–Smith 1993. Time rides in the label; no extra dimension |
| **Time-expanded graph** (FIFO fails) | `O(K·E log(KV))` | `O(KV)` | exact to `Δt` | no | pay a full factor `K` in time *and* memory |
| **Level-set / HJB space-time march** | `O(V·K)`, with `K = T·v_max/h` by CFL | `O(V)` | converges | no | marches the whole domain even where the front never goes |
| **Isochrone** | `O(K · n_θ · n_front)` | `O(n_front)` | **no guarantee** | no | fast, classical, no optimality claim |
| **NSGA-II / evolutionary** | `O(G·P²·k)` | `O(P)` | **no guarantee** | no | `G` generations, `P` population |
| **KAIROS (co-moving)** | `O(E' log V') + O(V')` where `V' = D·V` | `O(V')` | exact on the graph | **no** | `D` = dilation factor, below. The `O(V')` term is the interception scan |

---

## 2. The dilation penalty — the price of the reduction

The solve lives in `y = x − w·t`, so the domain must cover every co-moving position a ground
point visits over the horizon. For a box of side `L_i` per axis:

```
D  =  ∏_i  ( L_i + |w_i|·T ) / L_i                                        (K.1)
```

This is the *entire* cost of the reduction, and it is a **constant factor, not an asymptotic
change**. It is small when `|w|·T ≪ L` (long voyages, slow systems) and punishing when the
horizon is long relative to the domain.

**Verified.** On the traffic demo — `L = 12 km` square, `w = (−3, −1) m/s`, `T = 1 h`:

```
D_predicted = (12 + 10.8)/12 × (12 + 3.6)/12 = 1.90 × 1.30 = 2.47
D_measured  = 9085 / 3721 = 2.44
```

Agreement to 1 %. Formula (K.1) is the right model.

**Regime guide:**

| Case | `L` | `\|w\|·T` | `D` |
|---|---|---|---|
| Ocean, 3700 km voyage, cyclone at 1.4 m/s over 140 h | ~5000 km | 706 km | **1.23** |
| Traffic, 12 km city, jam wave over 1 h | 12 km | 11 km | **2.47** |
| Traffic, 12 km city, jam wave over 3 h | 12 km | 34 km | **8.4** — use a shorter horizon |

Practical rule: **set `T` to the actual expected arrival time, not a generous upper bound.**
The 3 h horizon in an early version of the traffic demo cost 8.4× for nothing. Solve once with
a rough estimate, then re-solve with `T = 1.2 × arrival`.

---

## 3. Measured wall-clock — KAIROS is currently slower

| Problem | Conventional time-dependent Dijkstra | KAIROS co-moving | Ratio |
|---|---|---|---|
| Traffic, 12 km city, 200 m blocks | **0.08 s** (3 721 nodes) | 0.27 s (9 085 nodes) | **3.4× slower** |
| Ocean, Kochi → Aden, 0.25° | **2.14 s** (29 529 nodes) | 3.38 s | **1.6× slower** |

Both are pure-Python, single-threaded, unoptimised, and the comparison is fair (same lattice,
same connectivity, same heap). The gap is the dilation factor plus the `O(V')` interception
scan.

**So do not sell this as a speed improvement.** It is not one.

---

## 4. Where KAIROS actually wins

**(a) It removes the FIFO requirement entirely.** This is the real result. FIFO Dijkstra is
only *correct* when leaving later can never mean arriving earlier. Where that fails — a storm
closing a strait, a jam forming ahead of you — the alternatives are a time-expanded graph
(`×K` in time *and* memory) or a wait-augmented relaxation. KAIROS stays `O(E log V)` because
after the substitution there is no time dependence left to violate anything. Measured on a
deliberately adversarial field: the causality diagnostic went from `1.31` (violated, so a
single-pass solve is *not licensed*) to `0.26`.

**(b) It removes temporal discretisation error.** Not temporal *complexity* — the error.
There is nothing to sample in time, so the sampling error is zero. Measured: co-moving
feasibility excess `2.8e-14` m/s versus `6.7e-3` for the ground-frame solve on the same grid.
It is **more accurate on the same grid**.

**(c) It unlocks the stationary toolbox.** This is the part with the most headroom, and it is
where the speed argument would eventually be won. A stationary problem admits:

- **Fast marching / ordered upwind** — `O(Υ V log V)` with *continuous* headings, which
  removes the ~1 % fixed-stencil metrication floor that neither method currently escapes.
- **Precomputed heuristics, landmarks, contraction hierarchies** — all of which assume a
  static cost field and are simply unavailable on a time-dependent graph.
- ~~**Reusable solves**: one co-moving solve answers every departure time.~~
  **RETRACTED — this claim was wrong.** Departing at `t_d` puts the co-moving source at
  `y = x_A − w·t_d`, so the *source moves with the departure time* and the forward field must
  be recomputed. A backward solve does not rescue it either: removing the moving target with
  `z = y + wΔ` gives `ż ∈ 𝒱₀(y)` with `y = z − wΔ`, which is time-dependent again — that
  substitution just returns you to the ground frame. There is no free lunch here, and a
  departure-time sweep costs `P` solves for KAIROS exactly as it does for anyone else.

- **Precomputable field** — the co-moving field being stationary means it *can* be tabulated
  once per (node, direction), which a time-dependent solver cannot do. **Measured: this does
  not pay off, and makes things worse.** See §4.1.

**(d) It generalises.** `kairos/core.py` knows nothing about oceans. Ships, aircraft, UAVs,
traffic shockwaves, wildfire fronts — anything where the cost field is advected.

---

## 4.1 Attempts to make it faster, and what they measured

Two optimisations were implemented and benchmarked on the traffic case (12 km city, 200 m
blocks, field = trilinear interpolation into a 24×160×160 forecast array, so evaluation cost
is realistic rather than a two-flop formula).

**A\* with an exact admissible heuristic — worked, 1.9×.**

The stationary form admits a heuristic a time-dependent solver has no analogue for: the exact
minimum interception time at maximum speed, `intercept_lower_bound()`. Deriving it gives

```
D_min = [ √(⟨a,w⟩² + (s² − |w|²)|a|²) − ⟨a,w⟩ ] / (s² − |w|²)
```

— **the Randers formula again**, arrived at independently, with drift `w` and speed `s`. It is
admissible (true speed never exceeds `s`) and consistent (metric-derived), so A* finalises with
no reopening. Measured: **1.9× wall clock, 2.3× fewer expansions** (9085 → 4033).

**Field precomputation — backfired, 2.6× worse.**

| field cost | conventional | co-moving + A* | + precompute |
|---|---|---|---|
| cheap | 0.321 s | 0.401 s | 1.050 s |
| ~40 flops | 0.661 s | 0.773 s | 1.618 s |
| ~200 flops | 1.383 s | 1.691 s | 3.527 s |
| ~1000 flops | 5.380 s | 6.081 s | 14.325 s |

The crossover never arrives, and precompute is worse at *every* field cost. The reason is
structural: **precomputation and A\* are in direct tension.** Tabulating costs
`O(V'·m)` evaluations over the whole dilated lattice — 145 000 here — while A* expands only
~4 000 nodes. Precompute does more work than the search saves, and raising the field cost
makes it worse in proportion, not better.

It would pay only if the search visited most of the domain (i.e. no usable heuristic), which
is exactly the case where you would not want the dilation either.

**Where the remaining gap comes from.** After A*, co-moving expands 4033 nodes against
conventional Dijkstra's 3721 — essentially the same. The residual ~1.4× is per-node overhead:
computing the heuristic (a `sqrt` plus a handful of flops on every push) and 3-tuple rather
than 2-tuple heap entries. And note the comparison flatters KAIROS in one respect and not
another: conventional Dijkstra here has **no heuristic at all**; give it one and it would pull
further ahead.

**~~Verdict: the speed avenue is closed.~~ RETRACTED — this was premature.**

Profiling showed the real bottleneck was not solver overhead but **field evaluation: 61 % of
runtime, 63 943 calls for 4 027 expansions** — one per edge relaxation. Attacking that changed
the answer completely.

## 4.2 The optimised solver (`kairos/fast.py`)

Four changes, in descending order of measured benefit:

1. **Edge-midpoint cache — the structural one.** Every undirected edge is relaxed twice, once
   from each endpoint, and both sample the *same* midpoint. In the co-moving frame the field
   is stationary, so the second sample is free. **A time-dependent solver cannot do this**: its
   two visits happen at different arrival times and it must re-interpolate. This is the
   precomputation advantage done *lazily* — only for edges the search touches — which is why
   it works where eager tabulation of the whole lattice (2.6× worse) did not.
2. **Split `sample(x,y)` from `speed_from(field,u)`** — the expensive part is
   direction-independent, which is what makes the cache possible at all.
3. **Flat neighbour tables** — the reference lattice allocated a fresh list of tuples per call.
4. **Two-tuple heap with lazy deletion.**

| field cost | conventional | co-moving + A* | **optimised** | verdict |
|---|---|---|---|---|
| cheap | 0.357 s | 0.416 s | **0.140 s** | **2.55× faster** |
| ~40 flops | 0.532 s | 0.800 s | **0.350 s** | **1.52× faster** |
| ~200 flops | 2.048 s | 2.499 s | **0.421 s** | **4.87× faster** |
| ~1000 flops | 8.027 s | 8.074 s | **1.254 s** | **6.40× faster** |

**The advantage grows with field cost**, which is the direction reality moves in — a real
forecast lookup is a quadrilinear interpolation over several variables, not a two-flop formula.

## 4.3 Precision

Measured against the exact Randers answer in a uniform field, averaged over 13 headings
spanning all directions, `h = 2.5 km`:

| stencil | neighbours | mean error | max error | time |
|---|---|---|---|---|
| `r ≤ 1` | 8 | 5.49 % | 9.66 % | 7.7 s |
| `r ≤ 2` | 16 | 1.27 % | 3.13 % | 20.0 s |
| **`r ≤ 3`** | **32** | **0.57 %** | **1.68 %** | 35.3 s |
| `r ≤ 4` | 48 | 0.43 % | 1.14 % | 54.9 s |

**Recommendation: 32 neighbours.** It cuts mean error 9.6× against the 8-neighbour default for
4.6× the cost; going on to 48 buys only a further 1.3× for 1.55×. And the speed work above
more than pays for the richer stencil.

**What did *not* work: the semi-Lagrangian update.** `comoving_plan_sl` implements the 2-point
interpolated update that should give continuum headings and remove the metrication floor
outright. Measured gain: **1.02–1.05×, i.e. nothing.** The implementation qualifies too few
(a, c) segment pairs to fire usefully. It is left in the tree, clearly marked as not working
as intended; the principled fix remains the right idea and the wrong implementation.

---

## 5. The constraint that bounds all of this

The reduction needs the **space** to be translation-invariant, because in co-moving
coordinates the space is what shifts. Continuous space, regular lattices and 1-D corridors
qualify. An **arbitrary irregular graph does not** — a real road network in co-moving
coordinates becomes a *moving graph*, which is strictly worse than moving costs.

So for a real road map with moving congestion, use ordinary FIFO time-dependent Dijkstra. For
a vehicle moving through a continuous medium — which is every fluid-borne routing problem —
use this.

---

## 6. Honest summary

> **KAIROS is 2.5–6.4× faster than conventional time-dependent Dijkstra**, with the margin
> growing as field evaluation gets more expensive — which is the direction real forecast data
> pushes. The win comes from the edge-midpoint cache, which is available *only* because the
> co-moving field is stationary: a time-dependent solver visits the same midpoint at two
> different times and must re-interpolate both.
>
> Precision: **0.57 % mean error with a 32-neighbour stencil** (vs 5.49 % at 8 neighbours), and
> the speed headroom pays for the richer stencil several times over.
>
> Also measured: **correct with no FIFO assumption** (causality diagnostic 1.31 *violated* →
> 0.26 *fine*; where FIFO fails, the alternatives cost a factor `K` in time *and* memory), and
> **zero temporal sampling error** (`2.8e-14` vs `6.7e-3`).
>
> **Three claims were retracted along the way**, all after being checked rather than assumed:
> the single-solve departure-time sweep (no free lunch — the co-moving source moves with the
> departure time), the eager-precomputation crossover (never arrives; it fights A*), and
> "the speed avenue is closed" (premature — profiling found the real bottleneck).
>
> The reduction still only applies where the space is translation-invariant and the field is
> advected. Inside that domain it is now both faster and more accurate; outside it, it does
> not apply at all.
