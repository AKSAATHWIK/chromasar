# ERRATA — corrections to the KAIROS theory

**Status: NORMATIVE. This file supersedes `CONTRACT.md` and everything in `docs/` wherever
they disagree.**

An adversarial referee pass over the draft found **11 blocking errors and 18 major ones**.
Several were fatal to claims made in the first draft. They are recorded here in full,
because (a) the corrected statements are what must be implemented, and (b) a paper that
shows its own failed claims and the repairs is far more credible than one that quietly
drops them.

Two of the eleven are *citation kills* — prior work that already does what was claimed as
new. Those are dealt with in §E10–E11 and the contribution list is re-scoped accordingly.

---

## E1 — The strong-drift condition was unsatisfiable

**Was:** "Where `|c| ≥ σ_max`, the metric is one-sided (Kropina-type)."

**Wrong because:** `σ_max = max_u σ(x,t,u)` is speed made good **over ground**, and in the
direction of the drift `σ ≥ V_max + |c|`. So `σ_max > |c|` always, for any `V_max > 0`.
The condition is identically false. Any implementer coding `if (norm_c >= sigma_max)` gets a
branch that never fires — silently running the fast path in exactly the cells where the
theory says it must not.

**Corrected statement.** Let `V_max(x,t) := max_{θ,q} attainable(vessel, env, θ, q)` — the
best **through-water** speed. Then:

- `0 ∈ int conv 𝒱(x,t)` **iff** `|c| < V_max(x,t)`.
- When `|c| > V_max`, all achievable ground velocities lie in `D(c, V_max)`, which excludes
  the origin. The reachable set of *directions* is a cone about `c` of half-angle

  ```
  α_reach = arcsin( V_max / |c| )                                        (E1.1)
  ```

  and `F(x,t,u) = +∞` for every `u` outside that cone. This is the excluded-direction test
  §4 must implement; it is a two-line check, not a special case.
- `|c| = V_max` exactly: the cone degenerates to a half-plane boundary; treat as excluded
  (`F = +∞`) for strict safety.

Everywhere `σ_max` was used as a proxy for through-water speed, substitute `V_max`.

---

## E2 — `F_min → 0` is false; the bucket queue fails for a different reason

**Was:** "Fall back to a heap when `F_min` is not bounded away from 0" (CONTRACT D3).

**Wrong because:** `F_min = 1/σ_max = 1/(V_max + |c|)`, which is **bounded below** by
`1/(V_max + |c|_max) > 0`. It does not approach zero. Numerically, with `V_max = 7 m/s`:

| `\|c\|` [m/s] | 0.5 | 2 | 3 | 8 |
|---|---|---|---|---|
| `F_min` [s/m] | 0.133 | 0.111 | 0.100 | 0.067 |

It shrinks by a third across the entire realistic drift range. The stated failure mechanism
was the wrong one, so the stated remedy fired on the wrong test.

**Corrected statement.** What actually diverges in a strong-drift cell is

```
F_max = 1/σ_min → ∞      as σ_min = V_max − |c| → 0⁺
Υ_loc = F_max/F_min = (V_max + |c|)/(V_max − |c|) → ∞                     (E2.1)
```

The Dial ring's **bucket count**, not its width, becomes unbounded:

```
n_buckets  =  ⌈ r_max · F_max / Δ_min ⌉                                   (E2.2)
```

**Corrected D3 fallback rule:** use the heap when `Υ_loc(x,t) > Υ_heap` (normative default
`Υ_heap = 12`), and treat `F = +∞` directions as excluded per E1. The trigger is anisotropy,
not `F_min`.

---

## E3 — The Dial bucket width had no valid lower bound

**Was:** "every update advances the value by at least `Δ_min = h·F_min`."

**Wrong because:** in the semi-Lagrangian update the segment runs from an arbitrary point
`ξ(ζ)` on an accepted-front edge, of length anywhere in `(0, r(x)]`. An open interval has no
positive infimum, so `ℓ·F ≥ h·F_min` is simply false. Dial's correctness requires the bucket
width to be **≤** the minimum increment; with an arbitrarily small increment the queue can
finalise a node whose value is later lowered, destroying the label-setting invariant.

**Corrected statement.** Enforce the lower bound by construction, and derive the constant.

> **Lemma E3.1.** On a grid of spacing `h` whose accepted front is 8-connected, the
> perpendicular distance from a node `x` to any accepted-front edge is at least `h/√2`.
>
> *Proof.* Grid nodes nearest `x` lie at distance `h` at `(±h,0)` and `(0,±h)`. A front edge
> is a segment between two *adjacent* accepted nodes. Among the nearest four, the adjacent
> pairs are the diagonal ones, e.g. `(h,0)–(0,h)`, lying on the line `x+y=h` whose distance
> from the origin is `h/√2`. Pairs sharing an axis, e.g. `(h,0)–(h,h)`, lie at distance `h`.
> Any edge involving a node at distance `> h` is farther still. Hence the infimum over
> admissible front geometries is `h/√2`, attained. ∎

So set, normatively,

```
ℓ_min := h/√2 ,        c_geo := 1/√2 = 0.707106781…
Δ_min := ℓ_min · F_min = c_geo · h · F_min                                (E3.1)
```

and **the update must skip any front point `ξ` with `|x − ξ| < ℓ_min`.** That exclusion is
what makes (E3.1) a theorem rather than an assumption. It costs nothing: such points are
interior to the stencil and their characteristics are represented by other front edges.

---

## E4 — The causality condition used the wrong length scale

**Was:** `h · L_t ≤ 1`.

**Wrong because:** the ordered-upwind update traverses a segment of length up to
`r(x) ≤ Υ_loc·h`, not `h`. The arrival map actually iterated is `Arr(t) = t + ℓ·F(x,t,u)`
with derivative `1 − ℓ·L_t`. The correct licence is therefore **a factor `Υ` stronger** than
what was stated — and `Υ` is precisely the quantity the ordered-upwind machinery exists to
handle, so this is not a small margin. An implementation built to the old condition would
report a green causality certificate on forecasts where the sweep is not licensed.

**Corrected statement.**

```
Causality holds at (x,t)   ⟸   r(x) · L_t(x,t)  ≤  1                      (E4.1)
```

with `r(x)` the actual stencil radius used at `x`. The runtime diagnostic must report
`max_x r(x)·L_t(x,t)`, not `max_x h·L_t`. In the isotropic limit `r = h` and the old
condition is recovered, which is why the error was invisible in testing on weak fields.

---

## E5 — The wait relaxation was scaled by the wrong length

**Was:** `F̃(x,t,u) := inf_{s≥0} [ s/h + F(x, t+s, u) ]`.

**Wrong because:** the running-infimum identity

```
t + ℓ·F̃ = inf_{s≥0} [ (t+s) + ℓ·F(x, t+s, u) ] = inf_{t'≥t} Arr(t')
```

works **only** when the penalty denominator equals the multiplier on `F`. With `s/h` against
a multiplier `ℓ ≤ Υ·h`, the waiting penalty is over-charged by a factor up to `Υ`, and the
result is *not* the running infimum — so unconditional causality does not follow.

Two further defects: (i) `F̃` defined with `h` in it is a *scheme-level* object, not a
continuum metric, so it cannot be identified with "the loiter-augmented value function of
the continuum problem" as claimed — indeed `s/h → ∞` as `h → 0`, so `F̃ → F` and the
relaxation degenerates in the continuum limit; (ii) `inf_{s≥0}` requires `F` beyond the
forecast horizon, which does not exist.

**Corrected statement.**

```
F̃_ℓ(x,t,u) := inf over s ∈ [0, S_max(t)] of [ s/ℓ + F(x, t+s, u) ]        (E5.1)
S_max(t)    := (t₀⁻ + H_fc) − t          (truncated at the forecast horizon)
```

evaluated at the **same `ℓ`** the update uses. Beyond the horizon, persistence of the final
frame is the normative convention, and the run log must report how many evaluations were
horizon-truncated.

The continuum claim is replaced by the honest one: *the scheme's value function converges to
the loiter-augmented value function as `h → 0`*, which is a statement about §7 convergence,
not about the per-edge object `F̃_ℓ`.

---

## E6 — The realisability gap was dimensionally inconsistent and pointed the wrong way

**Was (CONTRACT D6 and docs/05 Thm 5.3):** `J_dwell − J_relax ≤ L_x · v_max · τ_d · S`, with
an instruction to "add a Grönwall factor".

**Wrong because:** the draft's Grönwall forcing term was dimensionally inconsistent
(`v_max/τ_d` is m/s², not m/s), and worse, it made the gap **decrease** as the dwell time
increased — backwards, since a longer minimum steering interval means coarser chattering and
a *larger* gap.

**Corrected statement.** Introduce `L_v` := Lipschitz constant of the ground-velocity field
in position, **units 1/s** (this symbol was missing from CONTRACT §1 and is now added).

The dwell-constrained trajectory oscillates about the relaxed one with amplitude `v_max·τ_d`
(it does not accumulate within an interval — the average velocity matches by construction),
but that oscillation feeds back through the position-dependence of the velocity field:

```
e(T)  ≤  v_max · τ_d · exp( L_v · T )                                     (E6.1)
J_dwell − J_relax  ≤  L_x · v_max · τ_d · S · exp( L_v · T )              (E6.2)
```

Units check: `L_x` [s/m²] · `v_max` [m/s] · `τ_d` [s] · `S` [m] = [s] ✓, and the exponential
is dimensionless ✓. The bound now increases with `τ_d`, as it must.

**And here is the honest part.** Substitute realistic Indian Ocean numbers —
`L_v ≈ 10⁻⁵ s⁻¹` (1 m/s of current variation over 100 km), `T ≈ 1.2×10⁶ s` (14 days) —
and `L_v·T ≈ 12`, so `exp(L_v T) ≈ 1.6×10⁵`. **The global bound is vacuous.**

So Thm 2.11 is demoted to what it can actually support:

> **Corrected Thm 2.11 (local form).** Over a leg of duration `Δt` with `L_v·Δt ≪ 1`,
> ```
> J_dwell − J_relax  ≤  L_x · v_max · τ_d · S_leg · (1 + L_v·Δt)          (E6.3)
> ```
> which for `τ_d = 300 s`, `Δt = 6 h`, `S_leg = 150 km` gives a gap under 2 seconds.

The **global** guarantee is not the a-priori bound. It is the *a posteriori* certificate of
Cor 4.12, which is computable, tight, and does not degrade with voyage length. This is a
better paper than the one that claimed an a-priori bound it could not support.

---

## E7 — The ε-Pareto label bound was vacuous as constructed

**Was:** bucket the per-edge *increment* at ratio `(1+ε')` with `ε' = ε/D`, giving a uniform
`(1+ε)` guarantee.

**Wrong because:** `Λ ≈ (log range / log(1+ε'))^{k−1}`, and `ε' = ε/D` makes
`log(1+ε') ≈ ε/D`, so `Λ ≈ (D·log range / ε)^{k−1}` — **polynomial of degree `k−1` in the
path length**. With `range = 10³`, `ε = 0.02`, and `D ≈ S/h ≈ 5000 km / 28 km ≈ 180`, the
bound exceeds `10¹⁰` labels per node. Vacuous.

**Corrected statement.** Bucket on the **objective value**, not the increment:

```
bucket_i(ℓ)  =  ⌊ log(ℓ_i / C_i^min) / log(1+ε) ⌋ ,      i = 2 … k        (E7.1)
```

This is the Tsaggouris & Zaroliagis (2009) construction. It gives a uniform `(1+ε)`
guarantee with **no path-length dependence**, and

```
Λ  ≤  ∏_{i=2}^{k} ( ⌈ log(C_i^max/C_i^min) / log(1+ε) ⌉ + 1 )             (E7.2)
```

For `k = 3`, `ε = 0.02`, two decades of range: `Λ ≤ (log 100 / log 1.02 + 1)² ≈ 234² ≈
5.5×10⁴` worst case, and 10–40 observed after dominance pruning. Usable.

Objective 0 (time) is **never** bucketed. Bottleneck (`max`-accumulated) objectives take
finitely many distinct values along a route and are bucketed on the value directly.

---

## E8 — The kinematic equation was dimensionally inconsistent

**Was:** `ẋ = V·n(θ) + c` with `x = (λ, ϕ)` in radians.

**Wrong because:** the left side is rad/s and the right is m/s. The missing factors are
exactly the chart-to-frame conversion.

**Corrected statement.** Either write the chart form explicitly,

```
λ̇ = ⟨v, 𝐞_E⟩ / (R_E cos ϕ) ,      ϕ̇ = ⟨v, 𝐞_N⟩ / R_E ,   v = V n(θ) + c   (E8.1)
```

or — the convention KAIROS uses — state once and for all that **`ẋ` denotes the components
of the ground velocity resolved in the local orthonormal frame `(𝐞_E, 𝐞_N)`, in m/s**, with
(E8.1) applied at the chart boundary only. The solver runs entirely in the frame; `geodesy.py`
owns the conversion and nothing else touches it.

---

## E9 — "Finite iff `0 ∈ int 𝒱`" is false, including for our own default vessel

**Was:** "`F(x,t,·)` is finite in every direction iff `0 ∈ int 𝒱`."

**Wrong because:** sufficiency holds, necessity does not. Counterexample: `𝒱 = {1 ≤ |v| ≤ 2}`
— every ray from the origin meets `𝒱`, so `F` is finite in every direction, yet `0 ∉ 𝒱`.
And this is not academic: **our own model has `q_min = 0.15`**, so by the cube law
`V_min/V_max = 0.15^{1/3} = 0.53 > 0`, the ship cannot stop, and `0 ∉ 𝒱` whenever `|c| <
V_min`. The draft's own default configuration is a counterexample to its own lemma.

**Corrected statement (three separate claims).**

1. `F(x,t,u) < ∞` **iff** the ray `ℝ₊u` meets `𝒱(x,t)`.
2. `F(x,t,·)` is finite in **every** direction **iff** `0 ∈ int(star-hull 𝒱)`; under D4
   (we solve with `conv 𝒱`) this is equivalent to `0 ∈ int conv 𝒱`, i.e. `|c| < V_max`.
3. `0 ∈ 𝒱` itself is **false** whenever `|c| < V_min`, and is not required by anything.

The practical consequence: the "can the ship hold station" intuition is about `conv 𝒱`, not
`𝒱`. A ship with a minimum engine load genuinely cannot hold station, and the relaxation is
what lets it be treated as if it could (by alternating headings) — which is D4 earning its
keep, and worth saying out loud.

---

## E10 — Thm 3.1 is not new: Vladimirsky (2006)

**Prior art the draft missed.** A. Vladimirsky, *Static PDEs for time-dependent control
problems*, **Interfaces and Free Boundaries 8** (2006), 281–300. That paper asks precisely
when a time-dependent optimal-control problem can be solved by a single-pass static
(Dijkstra / fast-marching-type) method, and derives the causality condition. The draft's
framing — "the graph literature has FIFO, the level-set literature has HJB, nobody joined
them" — is simply wrong; this is the paper that joined them, twenty years ago.

**Re-scoped claim.** What survives, and it is narrower but defensible:

1. The identification of the causality constant with the **temporal Lipschitz constant of an
   operational forecast field**, estimated cell-by-cell from a real forecast stack.
2. The resulting **runtime diagnostic** (E4.1) reporting the margin per cell, so a solve
   comes with a machine-checkable licence rather than an assumption.
3. The **wait relaxation** (E5.1) as the physically-meaningful repair where the condition
   fails, with the observation that loitering and slow-steaming are what mariners do anyway,
   and that the wait branch is often Pareto-*dominant* on fuel and risk rather than merely
   feasible.

Cite Vladimirsky (2006) in §0.2 C1 and in the related-work section. Claim (3) is the one
worth defending as genuinely new.

---

## E11 — The multi-objective front-propagation idea is not new: Kumar & Vladimirsky (2010)

**Prior art the draft missed.** A. Kumar and A. Vladimirsky, *An efficient method for
multiobjective optimal control and optimal exit-time problems*, **Journal of Scientific
Computing 43** (2010), 274–298 — multi-objective optimal control solved with
fast-marching-type semi-Lagrangian methods, i.e. vector-valued information carried through a
minimisation-based update. Also relevant: Mitchell & Sastry (2003) on multi-objective
level-set reachability. The claim that "the multi-objective and the front-propagation
literatures are disjoint" was false and had been for over a decade.

**Re-scoped claim.** What survives:

1. The **ε-bucketed (FPTAS-style) label set** on a continuum ordered-upwind front, with the
   value-bucketing of E7 giving a path-length-independent `(1+ε)` guarantee and the label
   bound (E7.2) — with credit to Tsaggouris & Zaroliagis (2009) for the value-bucketing
   construction itself.
2. **Bottleneck (`max`-accumulated) objectives** carried through the front propagation. This
   is the one a master actually uses ("what is the worst moment of this voyage") and no
   weighted sum can express it. We have not found it treated in the front-propagation
   setting.
3. The **throttle family** (D1): each direction carries a one-parameter family of
   (time, fuel, risk) triples rather than a scalar, which is what makes fuel a genuine
   objective rather than a monotone function of time.

---

## The re-scoped contribution list

After E10 and E11, the honest list. This is what the paper claims.

| # | Contribution | Strength |
|---|---|---|
| 1 | **Formulation**: ship routing as a non-stationary Finsler geodesic problem with a throttle-parameterised, seakeeping-constrained indicatrix. Reduces the whole naval-architecture stack to five primitives. | Framework. Modest but real, and it is what makes the vessel model swappable. |
| 2 | **Forecast-checkable causality**: (E4.1) as a per-cell runtime diagnostic, plus the **wait relaxation** (E5.1) as the physically-meaningful repair. | Narrow but defensible after E10. The wait relaxation is the strongest part. |
| 3 | **Bottleneck objectives + throttle families** in ε-bucketed front propagation. | Defensible after E11. |
| 4 | **Anisotropy-adaptive stencil** with the ball-max radius fixed point. | Constant-factor, but provable and measured. |
| 5 | **A posteriori optimality certificate** via a *dilated-cell* optimistic coarse solve — where the dilation is required for admissibility and the naive construction is wrong. | Genuinely useful, and after E6 it is the *primary* guarantee rather than a bonus. |
| 6 | **A complete, validated, open reference implementation** for the Indian Ocean with published error bars, analytic ground-truth tests, and golden vectors. | For an applied venue this is a legitimate contribution in its own right. |

What was dropped: "first single-pass solve of the time-dependent anisotropic problem" (E10),
"first multi-objective front propagation" (E11), and the a-priori realisability bound as a
global guarantee (E6).

**This is a weaker paper than the first draft claimed, and a much stronger one than the first
draft actually was.** Every remaining claim is one we can defend under review.

---

## Open items still to fix in the remaining spec files

The 8 spec-file authors were interrupted by a session limit before writing; only
`00-overview.md` exists and it carries all of the above errors. When those files are written
they must be written against **this errata**, not against the original CONTRACT. Specifically:

- `01-formulation.md` — must use (E8.1) for the kinematics and E9 for the finiteness claims.
- `02-metric.md` — E1 (cone), E9 (finiteness), E6 (Thm 2.11 local form only).
- `03-causality.md` — E4 (`r(x)·L_t`), E5 (`ℓ`-scaled wait relaxation, horizon truncation),
  E10 (cite Vladimirsky 2006 and re-scope).
- `04-algorithm.md` — E2 (`Υ_heap` fallback), E3 (`ℓ_min` exclusion and `c_geo = 1/√2`).
- `05-multiobjective.md` — E7 (value bucketing), E11 (cite Kumar & Vladimirsky 2010).
- `07-complexity.md` — bucket count (E2.2), label bound (E7.2).
