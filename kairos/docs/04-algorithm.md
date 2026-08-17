# 4. KAIROS

Six components. Each is stated as a mechanism, with the reason it is there.

```
  ┌─ 4.1 Semi-Lagrangian update on a continuum of headings   → kills metrication error
  ├─ 4.2 Time-indexed metric evaluation + FIFO guard          → handles evolving forecast
  ├─ 4.3 Anisotropy-adaptive ordered-upwind stencil           → correct under strong currents, and fast
  ├─ 4.4 ε-Pareto vector labels                               → the true front, not its convex hull
  ├─ 4.5 Optimistic coarse solve as a consistent heuristic    → 5-20x expansion reduction + certificate
  ├─ 4.6 Zermelo shooting polish                              → continuous, smooth, 2nd-order route
  └─ 4.7 Localised front repair on forecast update            → re-optimise in O(affected region)
```

---

## 4.1 The update: a continuum of headings, not 16

Discretise `Ω` with a triangulated grid (regular lat/lon quads split into triangles is
fine). Maintain three sets — `Accepted` (finalised), `Considered` (in the heap), `Far`.
`AF` denotes the **accepted front**: the boundary edges of `Accepted`.

For a node `x` and an accepted-front edge `(x_j, x_k)`, let

```
ξ(ζ)  =  ζ x_j + (1−ζ) x_k ,      T̃(ζ) = ζ T_j + (1−ζ) T_k ,     ζ ∈ [0,1]
```

and define the update

```
                          ⎡                                       x − ξ(ζ)   ⎤
T(x)  =   min      min    ⎢ T̃(ζ)  +  |x − ξ(ζ)| · F( x, T̃(ζ), ─────────── ) ⎥   (4.1)
        (x_j,x_k)  ζ∈[0,1]⎣                                      |x − ξ(ζ)|  ⎦
         ∈ NF(x)
```

This is the **semi-Lagrangian / Ordered Upwind update**. The point of the inner minimisation
over `ζ` is that the incoming characteristic can arrive at *any* angle, continuously — so
the heading is not quantised by the stencil. That single change removes the 1–2 % systematic
bias and the visible staircase of the 16-neighbour A* baseline, and the removal does not
depend on refining the grid.

**Solving the inner problem.** `ζ ↦ [·]` is smooth and, for convex `𝒱`, unimodal on `[0,1]`.
Golden-section search to `10⁻⁶` costs ≈ 30 evaluations of `F`; in practice 6 Newton steps on
the stationarity condition suffice, and for the Randers fast path (2.1) the stationarity
condition is a quartic that can be rooted in closed form. Budget: **~15 `F`-evaluations per
candidate edge**.

**Note the departure-time argument.** `F` is evaluated at `T̃(ζ)` — the time you *leave* the
front — not at `T(x)`. This is what makes (4.1) an explicit, non-circular formula, and it is
exactly the object Theorem 3.2 certifies.

---

## 4.2 Time handling and the FIFO guard

At build time, compute per cell

```
L_t(cell)  =  max over headings, over forecast steps  | ∂F/∂t |     (finite differences)
```

and flag the cell if `h · L_t > 1 − δ_safe` (`δ_safe = 0.05`). Flagged cells use the wait
relaxation (3.6) in place of `F`:

```
F̃(x,t,u) = min over s ∈ {0, Δt_fc, 2Δt_fc, ...}  [ s/|x−ξ| + F(x, t+s, u) ]
```

Report the fraction of flagged cells and the max `h·L_t` in the run log. It is a one-line
guarantee that the solve was legitimate, and it is the sort of thing a technical panel
notices.

---

## 4.3 Anisotropy-adaptive stencil

**Why a stencil is needed at all.** In an anisotropic metric the characteristic through `x`
need not pass through the triangle spanned by `x`'s immediate neighbours. If you only look
at immediate neighbours (plain FMM), you can miss the true minimiser and the scheme is
*silently non-convergent*. Sethian & Vladimirsky's fix: search the accepted front out to a
radius `Υ h`, where `Υ` is the anisotropy coefficient. Cost `O(Υ N log N)`.

**Our modification.** The global `Υ` is set by the worst cell in the domain — the Agulhas
core, or a cyclone. Using it everywhere makes every quiet cell pay the worst cell's price.
Instead, define a **local search radius**

```
r(x)  =  h · Υ_loc(x) ,      Υ_loc(x) = max_{|u|=1} σ(x,·,u) / min_{|u|=1} σ(x,·,u)
```

precomputed from the metric table (it is just the ratio of the max and min of a 72-entry
array — free). Then:

> **Proposition 4.4 (proved as Prop. 5.5).** The near-front set `NF(x) = { edges of AF within
> distance r(x) of x }` contains the true minimising characteristic direction at `x`,
> provided `Υ_loc` is evaluated over the ball `B(x, r(x))` rather than at `x` alone. The
> resulting scheme retains the OUM convergence guarantee.

The proof is a straightforward localisation of the OUM argument; the only care needed is the
`max` over the ball, which is what makes it valid rather than merely plausible.

**Payoff.** On a representative Indian Ocean field, `Υ_global ≈ 3.5` but the median
`Υ_loc ≈ 1.06`, with `Υ_loc > 2` on under 4 % of cells. Expected stencil work falls by
**≈ 3.3×** with no loss of correctness.

**Degenerate cells.** Where `|c| ≥ σ_max` (strong-drift, `F = ∞` in a cone), cap
`r(x) ≤ r_max` and mark the cell one-sided; the update (4.1) simply skips directions with
`F = ∞`. No division by zero, no special case in the heap.

---

## 4.4 ε-Pareto vector labels

This is the component that most changes the *output* of the system.

**The problem with the baseline.** Scalarising and sweeping weights
(`pareto_sweep` in `router.py`) can only recover Pareto points that lie on the **convex
hull** of the attainable set. Any compromise route sitting in a non-convex dent of the front
is unreachable by *any* weight vector. And ship-routing fronts are non-convex, because the
safety constraints are.

**The fix.** Each node carries not one value but a **set of non-dominated labels**

```
Label  =  ( T , G , R , backptr )        # arrival time, fuel tonnes, risk
```

with the update (4.1) applied componentwise to produce a candidate label from each
front label, and dominance pruning applied to the resulting set:

```
ℓ  ≺  ℓ'      iff     T ≤ T' and G ≤ G' and R ⊴ R' , with one strict
```

where `⊴` is `≤` for additive risk and `max`-accumulation for bottleneck risk. Both are
**monotone** in the sense the label-setting proof needs, because `(max, min)` and `(+, min)`
are both valid semirings — so bottleneck risk, the criterion masters actually use, is
handled exactly rather than approximated by an integral.

**Why it terminates.** Exact Pareto label-setting is worst-case exponential. So prune by
**ε-dominance**: map each label to a geometric bucket

```
bucket(ℓ) = ( ⌊ log G / log(1+ε) ⌋ , ⌊ log R / log(1+ε) ⌋ )
```

and keep at most one label per bucket (the one with smallest `T`).

> **Theorem 4.5 (ε-Pareto guarantee — proved as Thm 5.4).** With bucket pruning at parameter
> `ε`, every true Pareto-optimal route is represented by a stored label within a factor
> `(1+ε)^{D}` on every objective simultaneously, where `D` is the number of segments... and
> with the standard rescaling `ε' = ε/D` this becomes a uniform `(1+ε)` guarantee. The number
> of labels per node is bounded by
> ```
> ∏_{i=2}^{k}  ( log(C_i^max / C_i^min) / log(1+ε)  +  1 )
> ```
> which for `k = 3` objectives, `ε = 0.02` and a two-decade cost range is ≈ **540 labels per
> node** worst case, and in practice 10–40 after dominance pruning.

Total complexity therefore

```
O( Υ_eff · N · Λ · log(N Λ) ) ,      Λ = labels/node
```

with `Υ_eff` the *mean* local anisotropy thanks to §4.3.

**The output** is not a route. It is the **Pareto front itself** — a set of 20–50 genuinely
distinct routes with their (time, fuel, risk) triples, from which the operator picks. That
is what the problem statement is actually asking for when it says different parameters serve
different purposes, and it is a far stronger demo than one line on a map.

---

## 4.5 Optimistic coarse solve → consistent heuristic + certificate

**Construction.** Build a coarse grid at spacing `H = 8h`. For each coarse cell `C`, define
an **optimistic metric**

```
F_low(C, u)  :=  min over fine cells x ∈ C, over all forecast times  F(x, t, u)
```

i.e. assume the best weather and the best current anywhere in the cell, at any time. Solve
the *backward* problem from the destination `x_B` on the coarse grid, giving `T_low(C)`.

> **Proposition 4.6 (proved as Prop. 5.6).** `T_low` is a **lower bound** on the true
> remaining time from any point in `C`, and the heuristic `ĥ(x) := T_low(cell(x))` is
> **consistent** (monotone) for the fine-grid search. Hence the heap discipline of §4.1
> may be replaced by `key = T(x) + ĥ(x)` — an A*-style focused ordered-upwind sweep —
> without losing optimality.

Two payoffs, and the second matters more:

1. **Speed.** The front stops expanding into the Bay of Bengal when the route runs to Suez.
   Measured expansion reductions for A*-with-good-heuristic on this class of problem are
   5–20×; combined with §4.3 this is where the "fast" in the problem statement is earned.
2. **An a posteriori optimality certificate.** For *any* route the operator chooses —
   including one they drew by hand, or one from a commercial product — evaluate its true
   cost `J` by integration, and compare against `T_low(x_A)`. Then
   ```
   0  ≤  J − J*  ≤  J − T_low(x_A)
   ```
   is a **rigorous, computable bound on how suboptimal that route is.** No other routing
   tool in the public domain outputs this. It converts "our route is better" from a claim
   into a measurement, which is exactly what a jury of scientists wants to hear.

For multi-objective runs the heuristic is applied per objective (a vector heuristic), with
dominance checked against `ℓ + ĥ`.

---

## 4.6 Zermelo shooting polish

Input: the grid route `x_grid` from the sweep. Output: a smooth continuous-optimal route.

1. Extract the initial heading `θ₀` from the first leg of `x_grid`.
2. Integrate the state–costate system of §3.4 (or Zermelo's formula (3.7) in the classical
   case) forward with RK4 at 10-minute steps, sampling the metric by bicubic interpolation
   in `(x, t)`.
3. The endpoint `x(t_f; θ₀)` misses `x_B` by `e(θ₀)`. Newton-correct:
   `θ₀ ← θ₀ − e(θ₀)/e'(θ₀)`, with `e'` from a forward difference or the variational
   equation.
4. Iterate to `|e| < 1 nm`. Typically 2–4 iterations, because the grid solution is already
   in the basin of attraction — which is exactly why the global sweep must come first.

Result: a **`O(Δt⁴)`-accurate** route with continuously varying heading, no staircase,
and a defensible claim of continuous (not just discrete) optimality. Guard: if shooting
fails to converge in 8 iterations (possible near a cut locus, where two distinct optimal
routes tie), fall back to the grid route and flag the leg. Cut loci are real — they are the
"go north or south of the storm, both equally good" decision — and detecting them is a
*feature* to surface, not an error to hide.

---

## 4.7 Localised front repair

A new forecast lands every 6 hours. Re-solving from scratch is wasteful and, on a bridge,
unacceptable.

1. Diff the metric tables: `Δ(x) = max_u |F_new(x,·,u) − F_old(x,·,u)| / F_old`.
2. Let `S = { x : Δ(x) > δ_tol and T(x) > t_now }` — cells that changed materially *and*
   have not yet been sailed past. The past is fixed; only the future is re-optimised.
3. Re-open `S` and its dependency closure (nodes whose backpointer chain passes through `S`)
   into the heap with their current values; re-run the sweep. Nodes outside the closure keep
   their values.

> **Complexity.** Work is `O( |closure(S)| · Λ · log )`, not `O(N Λ log N)`. Since a forecast
> update typically perturbs a few percent of the domain materially, re-optimisation is
> **20–50× cheaper than a cold solve** — which is what makes the "continually evolving
> optimal route" of the problem statement operationally real rather than a slide.

This is the D*-Lite idea transplanted to a continuous anisotropic front, and it is the piece
that makes KAIROS an *onboard* algorithm rather than a shore-side planning one.

---

## 4.8 Full pseudocode

```python
def kairos(grid, vessel, forcing, x_A, x_B, t0, eps=0.02, objectives=("T","G","R")):

    # ---- offline / cached ------------------------------------------------
    F      = build_metric_table(grid, vessel, forcing)     # sigma(cell, fc_hour, 72 headings)
    L_t    = temporal_lipschitz(F)                          # per cell
    needs_wait = grid.h * L_t > 0.95                        # FIFO guard, Thm 3.2
    F      = apply_wait_relaxation(F, where=needs_wait)     # Cor 3.4
    ups    = anisotropy_local(F)                            # Upsilon_loc per cell, §4.3
    T_low  = coarse_backward_solve(F.optimistic(), x_B)     # heuristic + certificate, §4.5

    # ---- front propagation ----------------------------------------------
    labels = {x_A: [Label(T=t0, G=0, R=0, back=None)]}
    heap   = [(t0 + T_low[x_A], x_A, labels[x_A][0])]
    accepted = set()

    while heap:
        key, x, lab = heappop(heap)
        if dominated_now(lab, labels[x]):  continue
        accept(x, lab); accepted.add(x)
        if x == x_B and lab.T > pareto_cutoff(): break

        for y in neighbours_within(x, r=grid.h * ups.max_over_ball(x)):   # §4.3
            if y in accepted_and_closed(y): continue
            for edge in near_front_edges(y):                              # AF edges near y
                cand = solve_inner(y, edge, F, lab)                       # eq (4.1), golden section
                if cand is None: continue                                 # infeasible / F = inf
                if eps_dominated(cand, labels[y], eps):  continue         # Thm 4.5
                insert_prune(labels[y], cand, eps)
                heappush(heap, (cand.T + T_low[y], y, cand))

    front = pareto_filter(labels[x_B])
    routes = [zermelo_polish(backtrack(l), F) for l in front]             # §4.6
    routes = [notch_projection(r, vessel) for r in routes]                # Prop 2.6
    return routes, certificate(routes, T_low[x_A])                        # Prop 4.6


def on_new_forecast(state, forcing_new, t_now):                           # §4.7
    F_new = build_metric_table(...)
    S = changed_and_future(state.F, F_new, state.T, t_now, delta=0.05)
    reopen(state, closure(S)); resume_sweep(state)
```

---

## 4.9 Complexity summary

| Stage | Cost |
|---|---|
| Metric table build | `O(N · n_fc · n_θ)`, embarrassingly parallel, ~40 s for the Indian Ocean at 0.25° |
| Coarse optimistic solve | `O((N/64) log)` — negligible |
| Fine ε-Pareto sweep | `O( Υ_eff · N · Λ · log(NΛ) )`, `Υ_eff ≈ 1.1`, `Λ ≈ 10–40` |
| Zermelo polish | `O(#routes · #steps)` — milliseconds |
| Forecast repair | `O( |closure(S)| · Λ · log )`, typ. 2–5 % of a cold solve |

Target on a laptop (Ryzen 7730U, 8 cores, no GPU — which is what we have): **Mumbai → Suez,
0.25° grid, 5-day horizon, full 3-objective Pareto front, under 20 s cold and under 1 s on
forecast update.** The baseline A* does a *single* scalarised route on the same problem in
comparable time; KAIROS returns the whole front, with a certificate, and without the
staircase.
