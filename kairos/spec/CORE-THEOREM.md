# The Co-Moving Reduction — the core of KAIROS

**Status: NORMATIVE. This is the algorithm's defining result.** Everything in `docs/` and
`spec/00-overview.md` describes the *previous* design, in which KAIROS was an assembly of
known components (ordered upwind + ε-Pareto labels + a causality condition). The referee
pass correctly identified that most of that assembly already exists in the literature
(see [ERRATA.md](ERRATA.md) §E10–E11). This document replaces the core with a single new
theorem, and the rest of the machinery becomes supporting apparatus rather than the claim.

**KAIROS** is redefined accordingly:
**K**inematic **A**dvection-**I**solating **R**eduction for **O**ptimal **S**hip-routing.

---

## 1. The observation

Every method in the ship-routing literature treats the time-dependence of the weather as an
*obstacle*: it breaks Dijkstra (no FIFO), it forces time into the state (dimension blow-up),
or it forces a full space-time HJB march (expense). An enormous amount of machinery exists
to cope with it.

But look at how ocean weather actually evolves on routing timescales. A synoptic low, a
tropical cyclone, a swell field, a monsoon surge — over 2–5 days these are, to leading
order, **rigid patterns that translate**. A cyclone moves at 5–8 m/s along a track that is
steady for days. The pattern deforms and intensifies, but slowly compared to how fast it
*moves*.

So the dominant part of the time-dependence is not evolution at all. **It is motion.** And
motion is frame-dependent.

> **The claim: the principal obstruction in time-dependent ship routing is an artefact of
> working in the ground frame. Change frames and it disappears.**

---

## 2. Setup

Ground frame. Ship kinematics (in the local orthonormal frame, per ERRATA E8):

```
ẋ = V·n(θ) + c(x,t) ,        (V,θ) ∈ 𝒜(x,t) ,        v := ẋ ∈ 𝒱(x,t)     (C.1)
```

> **Assumption A1 (frozen advection).** There is a constant `w ∈ ℝ²` such that every
> environmental field is a rigid translation of a fixed pattern over the planning horizon:
> ```
> E(x, t) = E₀(x − w t)      ⟹      𝒱(x,t) = 𝒱₀(x − w t)                (C.2)
> ```

> **Assumption A2 (outrun condition).** `|w| < σ_min^w`, where
> `σ_min^w := inf_{y, |u|=1} σ_w(y,u)` is the worst-direction speed made good in the
> co-moving frame (defined below). Physically: **the ship can make ground faster than the
> weather system translates.**

---

## 3. The theorem

> ### Theorem C.1 (Co-Moving Reduction)
> Under A1, define the co-moving coordinate and the **shifted indicatrix**
> ```
> y := x − w t ,        𝒱_w(y) := 𝒱₀(y) ⊖ w = { v − w : v ∈ 𝒱₀(y) }      (C.3)
> ```
> Then:
>
> **(a) Bijection.** `x(·)` is admissible for (C.1) **iff** `y(t) := x(t) − w t` is
> admissible for `ẏ ∈ 𝒱_w(y)`, with the *same* time parameterisation.
>
> **(b) Stationarity.** The co-moving problem is **autonomous**: `𝒱_w` depends on `y` only.
> Its arrival-time field `T_w` is the viscosity solution of a *stationary* Finsler eikonal,
> solvable in a single monotone pass with **no causality condition whatsoever**.
>
> **(c) Interception.** Under A2, the ground-frame minimum arrival time at `x_B` is
> ```
> t*  =  min { t ≥ 0 : T_w( x_B − w t ) ≤ t }                            (C.4)
> ```
> and the constraint is **active** at `t*`, i.e. `T_w(x_B − w t*) = t*`. Consequently no
> loitering is required at the optimum.
>
> **(d) Route recovery.** If `y(·)` is the co-moving geodesic reaching `x_B − w t*` with
> arrival-time parameterisation `τ(·)`, the ground-optimal route is
> ```
> x(s) = y(s) + w · τ(s)                                                 (C.5)
> ```

### Proof

**(a)** Differentiate `y(t) = x(t) − w t`: `ẏ = ẋ − w`. By A1, `ẋ ∈ 𝒱(x,t) = 𝒱₀(x − wt) =
𝒱₀(y)`. Hence `ẏ = ẋ − w ∈ 𝒱₀(y) − w = 𝒱_w(y)`. Every step is reversible (`w` is constant,
so the map `x(·) ↦ x(·) − w·` is a bijection on absolutely continuous curves preserving the
time parameter). ∎

**(b)** `𝒱_w(y)` in (C.3) has no `t` argument: the translation was absorbed entirely into the
shift. Autonomy is immediate, and the stationary Finsler eikonal `F_w*(y, ∇T_w) = 1` follows
by the standard dynamic-programming argument for autonomous minimum-time problems. Since the
Hamiltonian is now `t`-independent, `L_t ≡ 0` and the causality condition of ERRATA (E4.1),
`r(x)·L_t ≤ 1`, holds **vacuously**. ∎

**(c)** Reaching the *ground* point `x_B` at time `t` means, by (a), reaching the *co-moving*
point `x_B − w t` at time `t`. That is possible iff `T_w(x_B − w t) ≤ t`, since `T_w` is the
minimum co-moving time and any larger time is achievable by a non-minimal path.

Let `g(t) := T_w(x_B − w t) − t`, continuous since `T_w` is continuous (finite and locally
Lipschitz under A2). Then `g(0) = T_w(x_B) > 0` for `x_B ≠ x_A`. Writing
`F_max^w = 1/σ_min^w`,

```
T_w(x_B − wt) ≤ F_max^w · |x_B − wt − x_A| ≤ F_max^w ( |x_B − x_A| + |w| t )
⟹  g(t) ≤ F_max^w |x_B − x_A| + ( F_max^w |w| − 1 ) t
```

Under A2, `F_max^w |w| = |w|/σ_min^w < 1`, so the bracket is negative and `g(t) → −∞`. By the
intermediate value theorem a zero exists; let `t*` be the smallest. For `t < t*` we have
`g(t) > 0`, i.e. infeasible; at `t*`, continuity gives `g(t*) ≤ 0`. If `g(t*) < 0` strictly,
continuity would give `g < 0` on a neighbourhood, contradicting minimality of `t*`. Hence
`g(t*) = 0`. ∎

**(d)** Immediate from (a) applied to the optimal co-moving trajectory. ∎

---

## 4. Numerical verification

The substantive content of Theorem C.1 is the bijection (a); (c) and (d) follow from it.
The bijection was tested directly, without a second optimal solve, so that stencil error
cannot contaminate the result.

**Setup:** `V_s = 7.0 m/s`; eastward Gaussian jet, 3.0 m/s peak, 60 km half-width, advected
at `w = (2.0, 0.5) m/s`; 600 km voyage; 4 km grid.

**Procedure:** solve in the co-moving frame, map the resulting route to the ground frame via
(C.5), and check leg by leg that the required *through-water* velocity is achievable against
the ground-frame field sampled at the actual position and the actual time.

| Check | Theorem predicts | Measured |
|---|---|---|
| Co-moving route, checked in co-moving frame: excess over `V_s` | 0 | `+2.84e-14` m/s |
| Same route mapped to ground frame, checked against advected field | 0 | `+9.15e-14` m/s |
| Per-leg bijection residual `‖(v_x − c_gnd) − (v_y − (c₀−w))‖` | **exactly 0** | **`9.77e-14` m/s** |
| Converse (ground route mapped to co-moving): difference in max `V_req` | 0 | `3.55e-15` m/s |
| Ground arrival vs `x_B` | ≤ grid diagonal | 1.46 km (diagonal 5.66 km) |

**Verified to machine precision.**

### A second, unplanned finding

The ground-frame solve required `V_req = 7.006721 m/s` — an excess of `6.7e-3 m/s` over the
ship's actual capability — because sampling the advected field at the leg midpoint is only
first-order accurate in *time* as well as space. The co-moving solve's excess was `2.8e-14`.

> **The reduction eliminates the temporal discretisation error entirely**, because in the
> co-moving frame there is no temporal sampling to do. This was not designed for; it falls
> out. It means the co-moving solve is not merely faster and better-licensed, it is
> **more accurate on the same grid**.

### What the two-grid comparison could *not* show

Solving the same problem independently in both frames on the same 16-neighbour grid gave a
0.15–0.98 % discrepancy that **did not converge under refinement** (h = 24, 16, 12, 8, 6, 4,
3 km: 0.36, 0.15, 0.79, 0.92, 0.17, 0.98, 0.58 %). That is the fixed-stencil metrication
error floor — a stencil with finitely many neighbours quantises heading, and the quantisation
bias does not vanish as `h → 0`. The two frames quantise *differently* (their optimal headings
differ by the drift shift), so their errors do not cancel.

This is an independent, accidental confirmation of the motivation for the continuum-heading
semi-Lagrangian update: **on a fixed-neighbour grid, refinement buys you nothing beyond ~1 %.**
It also means the two-grid test is the wrong instrument for this theorem, which is why the
bijection test above is the one that settles it.

---

## 5. Why this changes the algorithm

| Obstacle in the ground frame | Status in the co-moving frame |
|---|---|
| Time-dependence breaks FIFO; needs the causality condition `r(x)·L_t ≤ 1` (ERRATA E4) | **Gone.** `L_t ≡ 0`; the condition is vacuous |
| Wait relaxation needed where causality fails (ERRATA E5) | **Not needed** in the pure case; the interception constraint is active at the optimum (Thm C.1c), so the optimum never loiters |
| Time in the state, or a full space-time HJB march | **One stationary solve** plus a scalar root find |
| Temporal sampling error in the update | **Zero** — nothing to sample in time |
| Randers closed form applies only without time-dependence | **Still applies**, with effective drift `c₀ − w` (see §6) |

The hardest theoretical obstacle in time-dependent routing turns out to be **frame-dependent**.

---

## 6. Randers structure is preserved

For the classical constant-through-water-speed case, `𝒱₀(y) = D(c₀(y), V_s)`, so

```
𝒱_w(y) = D( c₀(y) − w , V_s )                                            (C.6)
```

— still a disc, still centred on a drift vector, so the co-moving metric is **still Randers**
with effective drift `c_eff := c₀ − w`. Every closed form, every golden vector, and the
numerically stable conjugate branch of `handbook/01-golden-vectors.md` carry over verbatim
with `c ← c₀ − w`. The admissibility condition `|c| < V_s` becomes

```
| c₀(y) − w |  <  V_max(y)                                               (C.7)
```

which is the precise, checkable statement of "the ship can work against this system." Where
it fails, ERRATA E1 applies: the reachable directions form a cone of half-angle
`arcsin(V_max/|c₀−w|)`, and the correct answer really is *you cannot escape this storm.*

---

## 7. Real weather is not a rigid translation

Honest treatment of the assumption, because A1 is where a referee will push.

Decompose

```
E(x,t) = E₀(x − w t)  +  R(x,t)                                          (C.8)
```

with `R` the **residual**: intensification, deformation, and any second weather system moving
at a different velocity. Then:

1. **The reduction is exact when `R ≡ 0`** (Theorem C.1, verified §4).
2. **When `R ≠ 0`**, apply the reduction anyway and treat `R` with the existing
   time-dependent machinery. The causality condition then constrains not `L_t` but
   `L_t^R := Lip_t(R)`. The reduction acts as a **preconditioner** on the causality
   constant.

### Test 8.10 — measured

Three regimes, from A1-exact to A1-badly-violated. `L_t = max_u |∂F/∂t|` over 24 headings,
3-day horizon, 10 km grid, reported as max / 99th percentile / median over the domain.

| Regime | frame | max | p99 | median | `r·L_t` at `r = 56 km` |
|---|---|---|---|---|---|
| **A** pure translation (A1 exact) | ground | 6.33e-07 | 6.33e-07 | 5.64e-07 | 0.035 OK |
| | co-moving | **0.0** | **0.0** | **0.0** | **0.000** |
| **B** + intensification 35 %/day | ground | 2.34e-05 | 2.34e-05 | 3.75e-07 | **1.309 VIOLATED** |
| | co-moving | 4.86e-06 | 4.86e-06 | 1.69e-06 | **0.272 OK** |
| **C** + second system at a different `w` | ground | 2.34e-05 | 2.33e-05 | 3.52e-07 | **1.307 VIOLATED** |
| | co-moving | 5.07e-06 | 4.67e-06 | 1.63e-06 | **0.261 OK** |

**What this establishes.**

- **Regime A confirms the mechanism exactly**: `L_t` in the co-moving frame is *identically
  zero*, to the last bit. Theorem C.1(b) is not approximately true, it is true.
- **Regimes B and C are the result that matters practically**: the reduction takes a field on
  which the causality condition is **violated** (`r·L_t = 1.31 > 1`, so a single-pass solve is
  *not licensed*) and makes it **comfortably satisfied** (`0.26`). A 4.6–5.0× reduction at the
  99th percentile. This is contribution 3, and it now has evidence.

**Three honest caveats, all of which cost the claim something.**

1. **The median gets *worse*, by ~4.5×** (0.22× "reduction"). In the ground frame most cells
   are far from any system and see almost no change; in the co-moving frame the sampling point
   slides through space, so quiet cells now see the field vary. De-advection **trades a large
   improvement in the worst cells for a modest degradation in already-benign ones.** Because
   the causality condition is a worst-case condition, this is the right trade — but it is a
   trade, not a free win, and anyone reporting only the max is overselling it.
2. **Regime A's test field was degenerate in `x`** (an `x`-invariant jet), so only the
   `y`-component of `w` was identifiable; the optimiser recovered `w_y = +0.500` exactly
   against a true `+0.5` and left `w_x` unconstrained. The exactness of the reduction is
   established; the *identifiability* of `w` is not, by this test.
3. **In B and C the optimised `w` is nowhere near the true advection velocity**
   (`(−0.56, −1.38)` vs a true `(+2.0, +0.5)`). Once A1 is violated, minimising the residual
   causality constant and estimating the meteorological advection are **different problems**,
   and it is the former that the algorithm wants. Say so; do not dress the optimised `w` up
   as a physical storm-track estimate.

### Choosing `w`: what failed and what replaced it

The natural choice — **phase correlation** between consecutive forecast frames — was tried
first and **failed badly**: against a true dominant `w = (2.0, 0.5)` it returned
`(−0.74, 0.00)`. It locks onto whichever feature carries the most gradient energy, which need
not be the one governing the causality constant.

It is replaced by **choosing `w` to directly minimise the co-moving causality constant**:

```
w* = argmin_w  P₉₉ over the domain of  max_u |∂F_w/∂t|                    (C.10)
```

by coarse-to-fine search over a 2-D grid (three rounds of 9×9 is ample; the field evaluation
is vectorised). This optimises the quantity the algorithm actually needs, rather than a proxy
for it, and it is robust to multiple competing systems in a way phase correlation is not. The
99th percentile rather than the max keeps a single pathological cell from steering the choice.

For multiple systems a spatially varying `w(x)` gives a **warped** reduction — a flow map
`y = Φ_t^{-1}(x)` rather than a rigid shift, with the Jacobian entering the metric. Exact for
constant `w`, approximate otherwise. Not implemented; noted as the obvious extension.

**The honest scope:** Theorem C.1 is exact under A1 and A2, and A1 holds well for isolated,
coherently-translating systems over 2–5 day horizons — which is precisely the tropical-cyclone
and monsoon-surge case that matters most for Indian Ocean safety routing. It degrades for
rapidly deepening or merging systems, and there the reduction becomes a preconditioner rather
than a solution.

---

## 8. The algorithm

```
KAIROS(vessel, forecast stack, x_A, x_B, t₀):

  1. ADVECTION ESTIMATION
       w  ←  phase-correlate consecutive forecast frames                    (§7.3)
       R  ←  E(x,t) − E₀(x − w t)                                           (C.8)
       report  L_t(E)  and  L_t(R)  and their ratio                     [Test 8.10]

  2. CO-MOVING METRIC
       𝒱_w(y) = 𝒱₀(y) ⊖ w        — stationary, and Randers when applicable  (C.3, C.6)
       check the outrun condition A2 and (C.7) cell by cell; flag failures

  3. STATIONARY SOLVE                                    ← no causality condition needed
       T_w  ←  anisotropy-adaptive ordered-upwind sweep with the continuum
               semi-Lagrangian update, monotone bucket queue, ℓ_min exclusion
               (spec §4 as corrected by ERRATA E2, E3)

  4. INTERCEPTION
       t*  ←  bisect g(t) = T_w(x_B − w t) − t  on [0, T_max]               (C.4)

  5. ROUTE RECOVERY
       y(·) ← backtrack from x_B − w t* ;   x(s) = y(s) + w·τ(s)            (C.5)

  6. RESIDUAL CORRECTOR                                        [only if R is significant]
       one corrector sweep in the ground frame, seeded by step 5, with the
       causality guard now applied to L_t^R rather than L_t

  7. MULTI-OBJECTIVE / CERTIFICATE                                  [supporting apparatus]
       ε-Pareto labels over the throttle family (ERRATA E7, value bucketing)
       optimistic dilated-cell coarse solve → a posteriori certificate (spec Cor 4.12)
```

Steps 1, 2, 4, 5 and the licence for step 3 are new. Steps 3, 6 and 7 are the supporting
apparatus, and their prior art is credited in ERRATA §E10–E11.

### 8.1 Two implementation requirements that fail silently

Both were found by building it, not by thinking about it, and neither is visible in the
mathematics. They are recorded here because an implementer will otherwise hit them.

> **R1 — The co-moving grid must be dilated by `|w|·t_max` opposite to `w`.**
>
> The solve lives in `y = x − w t`, so reaching ground point `x_B` at time `t` requires the
> node `y = x_B − w t` to be *inside the grid*. Over a voyage of duration `t_max` the
> co-moving domain is displaced from the ground domain by `w·t_max`.
>
> Undersized, this fails **silently**: the sweep converges, the route looks plausible, and
> the landfall is simply wrong. Measured on a 140 h voyage with `w = (1,1) m/s`: the required
> node lay 4.5° west of the grid edge, giving a **104.5 km miss that a full-grid scan could
> not reduce**, because no node in the domain mapped anywhere near the target. Extending the
> domain by `|w|·t_max ≈ 500 km` brought the miss to **11.2 km**, under half a grid diagonal.
>
> Implemented as `comoving.required_dilation_m`.

> **R2 — Do not select the goal node by the interception root find.**
>
> Sampling `T` at the nearest node makes `g(t) = T_w(x_B − w t) − t` a *step function*, so a
> bisection converges to a discontinuity rather than a root, and `T` at the returned node can
> be far from `t*`. Because the ground position is `y + w·T[y]`, that timing error is
> amplified by `|w|`.
>
> Instead, solve the interception condition **directly on the discretisation**: every node
> carries its own arrival time, hence its own ground landfall `y + w·T[y]`; take the node
> minimising `‖(y + w·T[y]) − x_B‖`. This is Eq (C.4) evaluated exactly on the grid, with no
> interpolation and no root find, at `O(N)` with one haversine per node. The root find remains
> useful for reporting `t*` and would be the right method in a continuum implementation.

### 8.2 End-to-end result

Voyage 8.0 N 77.0 E → 12.6 N 43.5 E (3698 km great circle), `V_s = 7.2 m/s`, cyclone
translating at `(3.0, 1.0) m/s`, 0.25° grid, 29 529 nodes.

| | arrival | wall clock | notes |
|---|---|---|---|
| Ground-frame time-dependent Dijkstra | 141.2107 h | 2.14 s | conventional approach |
| Co-moving reduction | **139.9963 h** | 3.38 s (+0.05 s to choose `w`) | landfall miss 11.2 km |

Agreement **0.860 %** — inside the ~1 % fixed-stencil metrication floor of §4, which is the
expected outcome: the reduction is exact, so any residual difference is discretisation. The
co-moving answer is the *slightly faster* of the two, consistent with it carrying no temporal
sampling error.

Causality constant on this field: `L_t` **3.22e-07 → 1.24e-07 (2.60×)**;
`r·L_t` at `r = 2h = 55 km`: **0.0177 → 0.0068**.

Reproduce with `python demo/run_comoving.py`.

---

## 9. Re-scoped contribution list

Replacing the list in ERRATA §"re-scoped contribution list".

| # | Contribution | Evidence |
|---|---|---|
| **1** | **Theorem C.1, the Co-Moving Reduction.** Time-optimal routing in a rigidly advected field is *exactly* a stationary Finsler problem plus a scalar root find. The FIFO/causality obstruction is frame-dependent and vanishes. | Proved §3; verified to `9.8e-14` §4 |
| **2** | **The reduction eliminates temporal discretisation error**, not merely temporal *complexity* — the co-moving solve is more accurate on the same grid. | Measured: `2.8e-14` vs `6.7e-3` §4 |
| **3** | **Advection/evolution splitting as a preconditioner** (C.8): where A1 fails, the reduction still shrinks the causality constant enough to move a solve from *unlicensed* to *licensed*. | **Measured** (Test 8.10 §7): `r·L_t` 1.31 → 0.26; 4.6–5.0× at p99. Median regresses 4.5× — reported |
| **3b** | **Choosing `w` by minimising the residual causality constant** (C.10) rather than by image registration. Phase correlation was tried and failed (returned `(−0.74, 0)` against a true `(2.0, 0.5)`). | Test 8.10 §7 |
| **4** | Preservation of Randers structure under the shift (C.6), so closed forms and stable branches carry over with `c ← c₀ − w`. | §6 |
| **5** | Supporting apparatus, correctly credited: anisotropy-adaptive stencil; dilated-cell optimistic heuristic and a posteriori certificate; ε-bucketed Pareto labels with bottleneck objectives and throttle families. | ERRATA E10–E11 |
| **6** | A validated open reference implementation with analytic golden vectors and published error bars. | `handbook/`, `src/` |

Contribution 1 is the paper. It is a single, sharp, verifiable theorem that changes what the
algorithm *is*, rather than how fast it runs — and unlike the previous draft's claims, we
have searched for and failed to find prior art for it, and we have verified it numerically to
machine precision rather than asserting it.

**Still to do before submission:** run Test 8.10 (the `L_t/L_t^R` ratio on a real forecast
stack) — contribution 3 is currently a claim, not a result.

---

## 10. Prior art searched

Searched and **not** found: any application of a co-moving/Galilean reduction to weather
routing or to time-dependent Zermelo navigation.

Adjacent work that exists and is credited:
- **Zermelo (1931)**; **Bao–Robles–Shen (2004)** — Zermelo ↔ Randers correspondence.
- **Markvorsen (2025)**, *Time-dependent Zermelo navigation with tacking* (arXiv:2508.07274) —
  treats indicatrix fields that are **time-dependent only** (no spatial structure), a
  different and complementary special case.
- **Vladimirsky (2006)** — causality conditions for single-pass solution of time-dependent
  control problems. Our step 3 removes the need for his condition rather than checking it.
- **Kumar & Vladimirsky (2010)** — multi-objective control via fast marching.
- **Tsaggouris & Zaroliagis (2009)** — value-bucketed FPTAS for multi-objective shortest paths.
- **Sethian & Vladimirsky (2003)** — ordered upwind methods.
- **Lolla & Lermusiaux (2014)** — level-set ship routing.
- **Taylor (1938)** — the frozen-field hypothesis in turbulence, which is the meteorological
  ancestor of assumption A1, though it has not to our knowledge been used this way in routing.
- Moving-target interception (e.g. **Journal of Optimization Theory and Applications**, 2024)
  — step 4 is an instance, though the reduction that produces it is not.
