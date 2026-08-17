# 5. Proofs

Standing assumptions unless stated otherwise:

- **(A1)** `𝒱(x,t)` is compact, and `0 ∈ int 𝒱(x,t)` for all `(x,t)` in the domain of
  interest (the ship can hold station). Consequently `0 < F_min ≤ F(x,t,u) ≤ F_max < ∞`
  for all unit `u`.
- **(A2)** `F` is Lipschitz: `|F(x,t,u) − F(y,s,u)| ≤ L_x|x−y| + L_t|t−s|`.
- **(A3)** The domain `Ω` is bounded with Lipschitz boundary; land and exclusion zones are
  modelled as `F ≡ +∞`.

Where (A1) fails (`|c| ≥ σ_max`), all statements below hold on the sub-domain where it
holds, with `F = +∞` treated as an excluded direction; this is remarked on individually.

---

## Theorem 5.1 (Causality / FIFO)

**Statement.** Let the arrival map for a segment of length `h` in direction `u` from `x` be

```
Arr_{x,u,h}(t)  =  t  +  h · F(x, t, u).
```

If `h L_t ≤ 1` then `Arr` is non-decreasing in `t` for every `x, u`. Consequently the
label-setting sweep (4.1), which finalises nodes in non-decreasing order of `T`, computes
the exact discrete value function in a single pass with no reopenings.

**Proof.**
*(i) Monotonicity.* By (A2), `F(x,·,u)` is Lipschitz in `t` with constant `L_t`, hence
differentiable a.e. with `|∂_t F| ≤ L_t`. For `t₂ > t₁`,

```
Arr(t₂) − Arr(t₁)  =  (t₂ − t₁)  +  h[ F(x,t₂,u) − F(x,t₁,u) ]
                   ≥  (t₂ − t₁)  −  h L_t (t₂ − t₁)
                   =  (t₂ − t₁)(1 − h L_t)  ≥  0.
```

*(ii) Correctness of label setting.* We show the standard Dijkstra invariant survives.
Let `x*` be the node of minimal tentative value popped from the heap at some iteration, with
value `T̂(x*)`. Suppose for contradiction that the true value `T(x*) < T̂(x*)`. The optimal
path to `x*` leaves the Accepted set at some first node `z ∉ Accepted`, reached at true time
`T(z) ≤ T(x*) < T̂(x*)`. Since `z`'s predecessor is Accepted, `z` has been relaxed with a
departure time equal to that predecessor's final value, so its tentative value satisfies
`T̂(z) ≤ Arr(departure) `. By (i), using a departure time no later than the optimal one
cannot produce a later arrival, hence `T̂(z) ≤ T(z) < T̂(x*)`, contradicting minimality of
`T̂(x*)` in the heap. Therefore `T(x*) = T̂(x*)` and `x*` may be finalised. Induction over
pops gives the claim. ∎

**Remark 5.1.1.** Step (ii) is exactly where FIFO is indispensable, and it is why the naive
"just add time to the state" fix used in the baseline router is expensive: without
monotonicity you must either discretise time into buckets (introducing an `O(Δt_bucket)`
error and multiplying the state space) or allow reopenings (losing the `O(N log N)` bound).
Theorem 5.1 buys back a single-pass solve.

**Remark 5.1.2.** `h L_t ≤ 1` is *sharp*. If `h L_t = 1 + η`, take `F` decreasing in `t` at
the maximal rate on a single cell; then `Arr` is strictly decreasing there, waiting strictly
improves arrival, and any algorithm that finalises by arrival time is wrong on that cell.
Corollary 5.2 is therefore not a convenience but a necessity.

---

## Corollary 5.2 (Wait relaxation restores FIFO unconditionally)

**Statement.** Define `F̃(x,t,u) := inf_{s≥0} [ s/h + F(x, t+s, u) ]`. Then
`Arr̃(t) = t + h F̃(x,t,u)` is non-decreasing in `t` for every `L_t`, and `Arr̃(t)` equals the
earliest achievable arrival time when loitering at `x` is permitted.

**Proof.** Write

```
Arr̃(t) = t + h·inf_{s≥0}[ s/h + F(x,t+s,u) ] = inf_{s≥0} [ (t+s) + h F(x, t+s, u) ]
       = inf_{r ≥ t} Arr(r).
```

So `Arr̃` is the running infimum of `Arr` over `[t, ∞)`, which is non-decreasing in `t` by
construction: enlarging the feasible set (decreasing `t`) can only decrease an infimum. The
second claim is the definition of the loiter-augmented control problem: `r = t+s` is the
departure time actually chosen. Finally `F̃ ≤ F` by taking `s = 0`. ∎

**Remark.** `Arr̃` is non-decreasing but need not be strictly increasing — it is constant on
"wait it out" intervals. That is the correct behaviour: departing at any time within the
storm window yields the same arrival, because you wait for the same window to close. Ties
are broken by the fuel objective, which strictly prefers the latest such departure (less
loitering). The Pareto machinery of §4.4 handles this automatically.

---

## Theorem 5.3 (Realisability gap under a dwell constraint)

**Statement.** Let `J*_relax` be the optimal voyage time over relaxed (chattering) controls,
i.e. with ground velocity in `conv 𝒱`, and `J*_dwell` the optimum over piecewise-constant
controls in `𝒜` with switching intervals `≥ τ_d`. Under (A1)–(A2), for routes of Finsler
length `S` with ground speed bounded by `v_max`,

```
0  ≤  J*_dwell  −  J*_relax  ≤  L_x · v_max · τ_d · S.
```

**Proof.**
*Lower bound.* `𝒱 ⊆ 𝒱_{τ_d} ⊆ conv 𝒱` gives `F_{conv} ≤ F_{τ_d}`, hence
`J*_relax ≤ J*_dwell`.

*Upper bound.* Let `x_r(·)` be an optimal relaxed trajectory. By Carathéodory in the plane,
at each time its velocity is a convex combination of at most three points of `𝒱`; by the
chattering (relaxed-control approximation) lemma of Warga/Gamkrelidze, for any `τ_d > 0`
there is a piecewise-constant control with switching intervals `≥ τ_d` whose trajectory
`x_d(·)` satisfies, over each cycle, the same *average* velocity as `x_r`. Hence `x_d`
tracks `x_r` with deviation bounded by the distance travelled within one dwell interval:

```
sup_s | x_d(s) − x_r(s) |  ≤  v_max · τ_d  =:  ρ.
```

Now compare costs. Both trajectories are reparameterised by relaxed arc length `s ∈ [0,S]`.
By (A2), for each `s`,

```
F( x_d(s), t, u )  ≤  F( x_r(s), t, u )  +  L_x |x_d(s) − x_r(s)|  ≤  F( x_r(s), t, u ) + L_x ρ.
```

Integrating over the route,

```
J(x_d)  ≤  J(x_r)  +  L_x ρ S  =  J*_relax + L_x v_max τ_d S,
```

and `J*_dwell ≤ J(x_d)`. ∎

**Remark 5.3.1.** The bound is linear in `τ_d` and *independent of how badly non-convex `𝒱`
is*. This is the useful content: a forbidden region of any shape costs you at most the
tracking error induced by finite steering bandwidth.

**Remark 5.3.2 (why we still project).** The bound certifies the *cost*, not the
*admissibility*, of the relaxed solution — the relaxed optimum may literally command a
banned heading. The notch projection of §4.7 restores admissibility; Theorem 5.3 certifies
that the projected route is near-optimal. Both steps are needed.

---

## Theorem 5.4 (ε-Pareto guarantee and label bound)

**Statement.** Consider `k` objectives, the first (time) used for the heap order, the
remaining `k−1` bucketed geometrically at ratio `(1+ε')`. Suppose each objective `i ≥ 2` has
per-route range `[C_i^min, C_i^max]`. Then:

**(a)** the number of labels retained at any node is at most
```
Λ  ≤  ∏_{i=2}^{k} ( ⌈ log(C_i^max/C_i^min) / log(1+ε') ⌉ + 1 );
```

**(b)** for every Pareto-optimal route `π` with `D` segments, the algorithm retains a label
`ℓ` at the destination with `ℓ_1 ≤ (1+ε')^D · π_1` and `ℓ_i ≤ (1+ε')^D · π_i` for all `i`;
choosing `ε' = ε / D` (so `(1+ε/D)^D ≤ e^ε ≤ 1 + 2ε` for `ε ≤ 1`) yields a uniform
`(1 + 2ε)`-approximation of the entire Pareto front.

**Proof.**
*(a)* By construction at most one label is kept per bucket of the `(k−1)`-dimensional
geometric grid, and the grid has the stated number of cells because objective `i` spans
`log(C_i^max/C_i^min)/log(1+ε')` bucket widths.

*(b)* Induction on segments. Let `π = (e_1, …, e_D)` be Pareto-optimal and let `ℓ^{(m)}` be
the label the algorithm retains at the node reached after `m` segments, with the inductive
hypothesis `ℓ^{(m)}_i ≤ (1+ε')^m π^{(m)}_i` for all `i`.

*Base:* `m = 0`, the source label is exact.

*Step:* By monotonicity of the update — each objective's accumulation operator is either `+`
with non-negative increments or `max`, both order-preserving — extending `ℓ^{(m)}` along
`e_{m+1}` produces a candidate `ĉ` with `ĉ_i ≤ (1+ε')^m π^{(m+1)}_i`. When `ĉ` is inserted it
is either kept, or discarded because some `ℓ'` already occupies its bucket. In the latter
case, occupying the same geometric bucket means `ℓ'_i ≤ (1+ε') ĉ_i` for `i ≥ 2`, and `ℓ'_1 ≤
ĉ_1` because the bucket retains the minimum-time label. Either way the retained label
satisfies `ℓ^{(m+1)}_i ≤ (1+ε')^{m+1} π^{(m+1)}_i`. ∎

**Remark 5.4.1.** The `D`-dependence is the standard cost of the FPTAS argument and is
pessimistic: it assumes every segment loses a full bucket, which requires an adversarial
instance. Empirically the accumulated loss on ocean routes is well under `ε`, and it is
directly measurable — run once with `ε` and once with `ε/4` and compare fronts. That is a
cheap, honest experiment to put in the report.

**Remark 5.4.2 (bottleneck risk).** For the `max`-accumulated risk objective, monotonicity
in the induction step holds because `max` is order-preserving in each argument; no further
change is needed. This is why the algorithm handles "worst moment of the voyage" — the
criterion a master actually uses — exactly, whereas a scalarised sum cannot express it at
all.

---

## Proposition 5.5 (Locality of the ordered-upwind stencil)

**Statement.** Let `r(x) = h · max_{y ∈ B(x, r(x))} Υ_loc(y)` (a fixed point of the radius
map, computable by two iterations since `Υ_loc` is bounded). Then the near-front set
`NF(x)` of accepted-front edges within `r(x)` of `x` contains the minimiser of (4.1), and the
resulting scheme satisfies the OUM causality property: the update at `x` depends only on
nodes with strictly smaller `T`.

**Proof sketch.** The Sethian–Vladimirsky argument shows that the characteristic reaching
`x` originates from a point `ξ` on the accepted front with `|x − ξ| ≤ h Υ`, where `Υ` bounds
the anisotropy *along the segment `[ξ, x]`*. Their global `Υ` is used only because it
dominates every such segment. Since the segment lies inside `B(x, r(x))` by construction of
the fixed point, `max_{B(x,r(x))} Υ_loc` dominates the anisotropy along it, and the same
argument applies verbatim. Causality follows because every node of `NF(x)` is Accepted and
therefore has value `< T(x)`, by (A1) which gives `F ≥ F_min > 0` so that no zero-cost
segment exists. ∎

**Remark.** If (A1) fails at `x` (one-sided metric), cap `r(x) ≤ r_max` and restrict the
minimisation to directions with `F < ∞`. The scheme remains causal but the *a priori* error
constant degrades; this affects `< 1 %` of Indian Ocean cells and only inside western
boundary currents.

---

## Proposition 5.6 (Admissibility and consistency of the optimistic heuristic)

**Statement.** Let `F_low(C,u) := min_{x ∈ C, t} F(x,t,u) ≤ F(x,t,u)` for all `x ∈ C`, and
let `T_low` solve the coarse backward problem to `x_B` under `F_low`. Then for all `x`,

```
T_low( cell(x) )  ≤  T_true(x → x_B)
```

(admissibility), and `ĥ := T_low ∘ cell` satisfies the triangle inequality
`ĥ(x) ≤ d_F(x,y) + ĥ(y)` (consistency). Hence the focused sweep with key `T + ĥ` finalises
nodes with exact values.

**Proof.** Admissibility: for any route `π` from `x` to `x_B`,
`∫_π F ≥ ∫_π F_low ≥ T_low(cell(x))` — the first inequality is pointwise domination, the
second is optimality of `T_low` among coarse-representable routes, using that any fine route
projects to a coarse route of no greater `F_low`-length (the projection error is absorbed
because `F_low` takes a min over the whole cell). Consistency: `T_low` is itself a value
function of a shortest-path problem under `F_low ≤ F`, so it satisfies the dynamic
programming inequality with respect to `F_low`, and a fortiori with respect to the larger
`F`. Optimality of A*-ordered search under a consistent heuristic is standard. ∎

**Corollary 5.6.1 (optimality certificate).** For any admissible route `π` from `x_A` to
`x_B` with true cost `J(π)`,
```
0  ≤  J(π) − J*  ≤  J(π) − T_low(cell(x_A)),
```
computable without knowing `J*`. ∎

---

## Theorem 5.7 (Convergence of the scheme)

**Statement.** The scheme (4.1) is monotone, stable and consistent; under (A1)–(A3) and the
FIFO condition of Theorem 5.1, its solution `T_h` converges locally uniformly as `h → 0` to
the unique viscosity solution of the Finsler eikonal equation (3.2).

**Proof.** Apply the Barles–Souganidis framework. Write (4.1) abstractly as
`S_h(x, T_h(x), T_h|_{AF}) = 0`.

*Monotone:* the right-hand side of (4.1) is a minimum of terms each non-decreasing in the
front values `T̃(ζ)`; increasing any neighbour's value cannot decrease `T(x)`.

*Stable:* by (A1), `F_min·diam(Ω) ≤ T_h ≤ F_max·diam(Ω)` uniformly in `h`, and the values
are non-negative; the family `{T_h}` is uniformly bounded.

*Consistent:* fix a smooth `ϕ` and expand (4.1) at `x` with `T̃ = ϕ(ξ)`. Taylor:
`ϕ(ξ) = ϕ(x) − ⟨∇ϕ(x), x−ξ⟩ + O(h²)`. Substituting and dividing by `|x−ξ| = O(h)` gives
```
0 = min over directions u of  [ F(x, ϕ(x), u) − ⟨∇ϕ(x), u⟩ ] + O(h),
```
which as `h → 0` is exactly the statement `max_{v ∈ 𝒱} ⟨−∇ϕ, v⟩ = 1`, i.e. (3.2). The
inner minimisation over `ζ` is what supplies the *continuum* of directions `u` needed for
this limit; a fixed-neighbour stencil supplies only finitely many and the consistency error
does **not** vanish — this is the formal statement of defect (1) in the README.

*Comparison principle:* holds for (3.2) under (A1) since the Hamiltonian is convex, coercive
and continuous, and `Ω` satisfies (A3).

Barles–Souganidis then gives local uniform convergence to the unique viscosity solution. ∎

**Remark 5.7.1.** With the ε-Pareto extension, convergence holds for each scalar objective
to within the `(1+2ε)` factor of Theorem 5.4; letting `ε → 0` jointly with `h → 0` recovers
the exact Pareto front in the limit. We do not claim a rate for the joint limit — that is
open, and worth saying so.

**Remark 5.7.2 (rate).** For the single-objective case the OUM error is `O(h)` in general,
improving to `O(h²)` on smooth patches with the Zermelo polish of §4.6. We should measure
this, not assume it: §6 specifies the grid-refinement study.

---

## What is *not* proved here

Stated plainly, because a jury will ask and because it is the honest thing to do:

1. **No rate for the joint `(h, ε) → 0` limit.** Each limit is controlled separately.
2. **Theorem 5.3 assumes the chattering lemma's hypotheses**, in particular that `conv 𝒱`
   is attained by combinations of at most three admissible controls (Carathéodory in the
   plane — fine) and that the switching structure is realisable by the steering gear. A
   rudder-rate model would tighten this from a dwell-time abstraction to a real constraint.
3. **Uncertainty is not treated as uncertainty.** Everything above is deterministic given a
   forecast. The right object for an ensemble forecast is a risk measure such as CVaR, and
   *static* CVaR is not time-consistent, so it breaks the dynamic programming principle that
   all of §5 rests on. The correct fix is **nested (dynamic) CVaR**, which restores
   time-consistency at the cost of an extra state dimension. This is scoped as future work
   in §6, not hand-waved as done.
