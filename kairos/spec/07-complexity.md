# 7. Convergence, rate, complexity, memory, parallelism

This file owns block **§7**: `Thm 7.x`, `Prop 7.x`, `Lemma 7.x`, `Cor 7.x`, `Conjecture 7.x`,
and equations `(7.x)`. The numbers `Thm 7.1` (convergence) and `Thm 7.3` (total complexity) are
fixed by `CONTRACT.md` §2; `Prop 7.2` and `7.4`–`7.15` are allocated here. Symbols are those of
`CONTRACT.md` §1 and are never redefined. Objects owned by other blocks (`Alg 4.1`, `Prop 4.7`,
`Prop 4.9`, `Prop 4.11`, `Cor 4.12`, `Prop 2.7`, `Thm 2.11`, `Thm 5.2`, `Thm 5.3`) are cited,
never renumbered.

**Normative hierarchy.** `CORE-THEOREM.md` and `ERRATA.md` supersede `CONTRACT.md` wherever they
disagree; §7.10 lists every disagreement this file found. In particular this file is written
against **Theorem C.1, the Co-Moving Reduction**, which is the algorithm's defining result. The
ordered-upwind sweep, the ε-Pareto label machinery, the bucket queue and the a posteriori
certificate are **supporting apparatus** whose prior art is credited by name and year
(`ERRATA` §E10–E11); nothing in this file claims novelty for them. What §7 does claim is the
*consequences* of Theorem C.1 for cost: a metric table that is one forecast frame deep instead
of `n_fc`, a scheme whose monotonicity is unconditional rather than causality-licensed, an error
budget with an identically zero temporal term, and a domain decomposition whose interface data
is a scalar rather than a function of time. Each of those is derived below, and each is charged
its price — chiefly the grid dilation of `R1` and an increase in anisotropy in quiet cells.

**Language-agnostic, per `D7`.** Data structures appear as abstract types with an operation set
and a per-operation complexity. Memory appears as byte counts over explicitly described layouts.
Nothing is assumed beyond IEEE-754 arithmetic, a flat addressable byte array, and (only in §7.8)
an atomic 64-bit compare-and-swap.

---

## 7.0 What §7 must account for: the phases of the solve

`CORE-THEOREM.md` §8 gives the algorithm. §7 costs it phase by phase. The phase labels `P0`–`P8`
are local to this file and are used in every table below.

| | Phase | Owner | Novel? |
|---|---|---|---|
| **P0** | Choose `w` by minimising the residual causality constant, Eq (C.10) | `CORE-THEOREM` §7 | **yes** (contribution 3b) |
| **P1** | Build the co-moving metric / support table `𝔥_w(y, p_j)`, `j = 1..n_θ` | `D2`, `Prop 2.7` | tabulation is standard; **one frame instead of `n_fc` is a consequence of Thm C.1(b)** |
| **P2** | Optimistic **dilated-cell** coarse solve → heuristic + certificate bound | `Prop 4.11`, `Cor 4.12`, `D5` | supporting apparatus |
| **P3** | Stationary label-setting sweep with the continuum semi-Lagrangian update | `Alg 4.1`; Sethian–Vladimirsky (2003), Dial (1969), Martins (1984) | supporting apparatus; **the licence to run it single-pass is new** (Thm C.1(b)) |
| **P4** | Interception: pick the goal node, Eq (C.4) as corrected by `R2` | `CORE-THEOREM` §8.1 | **yes**, as a consequence of Thm C.1(c) |
| **P5** | Route recovery `x(s) = y(s) + w·τ(s)`, Eq (C.5) | Thm C.1(d) | **yes** |
| **P6** | Residual corrector in the ground frame, causality guard on `L_t^R` | Eq (C.8) | **yes** (splitting as a preconditioner, contribution 3) |
| **P7** | Forecast repair (incremental re-solve on a dependency closure) | §4 | supporting apparatus |
| **P8** | ε-Pareto labels over the throttle family; certificate report | `Thm 5.2/5.3`; Tsaggouris–Zaroliagis (2009), Kumar–Vladimirsky (2010) | supporting apparatus |

`P0`, `P4`, `P5`, `P6` exist only because of Theorem C.1. `P1`'s depth and `P3`'s licence change
because of it. `P2`, `P7`, `P8` are unaffected by the reduction and are costed for completeness.

### 7.0.1 Cost model

Operation counts are in **model operations (mops)**. One mop = one IEEE-754 scalar add, multiply,
compare or fused multiply-add, or one aligned table probe hitting L1/L2. Division counts as 4
mops, `sqrt` as 6, and each of `sin`, `cos`, `atan2`, `asin`, `exp`, `log`, `pow` as 8. These are
typical reciprocal-throughput ratios on a scalar out-of-order core; changing them changes the
totals by under 20 % and never changes which term dominates. Wall-clock estimates assume
**2×10⁹ mops/s/core**, deliberately conservative (roughly one quarter of scalar peak on the
Ryzen 7730U class of part). No SIMD, no GPU. Every wall-clock figure below can be recomputed for
other hardware by substituting a different rate.

Two per-evaluation constants recur and are named once:

```
c_σ^R    = 22 mops    Randers closed form σ(u) = √(V² − |c_⊥|²) + c_∥ with the λ>0 guard
                      (3 for c_∥, 3 for |c|², 2 for |c_⊥|², 2 for the radicand, 6 sqrt,
                       1 add, 1 compare, 4 for the reciprocal)                        [derived]
c_σ^phys = 400 mops   one call to attainable(·) + rates(·): Admiralty powering, added
                      resistance in wind (Fujiwara 2006) and waves, and the seven
                      seakeeping bans (Ochi 1964 slamming/deck-wetness probabilities;
                      IMO MSC.1/Circ.1228 parametric-roll, synchronous-roll and
                      surf-riding guidance)                        [UNVERIFIED ESTIMATE]
c_probe  = 15 mops    one support-table probe: binary search over n_θ = 72 (⌈log₂72⌉ = 7
                      compares), two loads, one linear interpolation                  [derived]
c_hav    = 60 mops    one haversine plus one metres→(Δlat,Δlon) conversion            [derived]
```

`c_σ^phys = 400` is the only figure here that is not derived from an operation count of a written
formula; it is an order-of-magnitude estimate of the naval-architecture stack and is **flagged as
unverified** everywhere it is used. Every conclusion that depends on it is stated as a ratio in
which it cancels, or is marked.

---

## 7.1 Standing assumptions, and what breaks without each

`(A1)`–`(A2)` are Theorem C.1's own hypotheses, restated for reference. `(S1)`–`(S7)` are the
additional hypotheses §7 needs. Every one carries an explicit failure mode, because an
implementer must know which of them to assert at run time.

| | Assumption | Used for | What breaks without it |
|---|---|---|---|
| **(A1)** | **Frozen advection.** There is a constant `w ∈ ℝ²` with `E(x,t) = E₀(x − wt)`, hence `𝒱(x,t) = 𝒱₀(x − wt)`. | Theorem C.1 in its exact form; `L_t ≡ 0` in the co-moving frame; the one-frame metric table of `P1` | the reduction becomes a *preconditioner*, not a solution: the residual `R = E − E₀(·−wt)` of Eq (C.8) must be carried by `P6`, and the causality condition returns — applied to `L_t^R`, not `L_t`. **Measured** (`CORE-THEOREM` Test 8.10): `r·L_t` falls from 1.31 (unlicensed) to 0.26 (licensed) in regimes B and C, at a 4.5× *regression* in the median cell. |
| **(A2)** | **Outrun condition.** `\|w\| < σ_min^w := inf_{y,\|u\|=1} σ_w(y,u)`. | existence of the interception time `t*` (Thm C.1(c)); via `Lemma 7.4`, coercivity and stability of the sweep | `g(t) = T_w(x_B − wt) − t` need not reach zero: the weather system cannot be outrun and there is **no finite arrival time**. The correct output is a refusal, not a route. The reference implementation returns `NONE` from `interception_time`; the honest report is "this system cannot be outrun on this hull". |
| **(S1)** | **Co-moving station-keeping.** `0 ∈ int conv 𝒱_w(y)` for every `y`, equivalently `\|c₀(y) − w\| < V_max(y)` — Eq (C.7). | `F_w ≤ F_max^w < ∞` in every direction; stability (7.11); coercivity (C3); the nesting `Lemma 7.7` | on the sub-domain where it fails, `F_w = +∞` outside a cone of half-angle `arcsin(V_max/\|c₀−w\|)` (`ERRATA` E1.1), `F_max^w = ∞`, `Υ_loc^w = ∞`, the nesting lemma fails, and the returned values are *feasible* but not certifiably *optimal*. See `Remark 7.2.4`. **Note that (A2) ⟹ (S1)** — `Lemma 7.4` — so (S1) never has to be checked separately when (A2) has been checked, but it is the weaker and more often satisfiable condition and is what the per-cell runtime flag should test. |
| **(S2)** | `\|F_w(y,u) − F_w(z,u)\| ≤ L_y\|y − z\|` uniformly in unit `u`. **There is no `L_t` term: the co-moving metric has no time argument** (Thm C.1(b)). | consistency (7.20); the structure condition (C2) of the comparison principle | the truncation error is no longer `O(h)` and uniqueness of the viscosity solution can fail. |
| **(S3)** | `Ω_w` bounded with Lipschitz boundary, **and dilated per `R1`**: `Ω_w ⊇ Ω ⊖ {wt : t ∈ [0, t_max]}`. Land, TSS/ECA exclusions and `d_b(x) < T_d + UKC` are modelled by `F_w ≡ +∞`. | stability (7.11); the state-constraint boundary condition (Soner 1986); **correctness of `P4`** | **silent wrong answers.** The sweep converges, the route looks plausible, the landfall is simply wrong. Measured on a 140 h voyage with `w = (1,1) m/s`: a **104.5 km miss that a full-grid scan could not reduce**, because no node in the domain mapped anywhere near the target; extending by `\|w\|·t_max ≈ 500 km` brought it to **11.2 km**. This is the most expensive assumption in the file and §7.6 prices it. |
| **(S4)** | `𝒱_w(y)` is **convex**. Guaranteed by construction: `D4` solves with `conv 𝒱`, and convexity is preserved by the shift `⊖ w` (translation of a convex set). | sublinearity of `F_w` (`Lemma 7.5`); duality `𝔥_𝒱 = 𝔥_{conv𝒱}` (`Prop 2.7`); unimodality of the inner `ζ`-problem; convexity of the Hamiltonian | `F_w` is not sublinear, `Lemma 7.5` fails, and every Lipschitz-in-direction constant in §7.2 and §7.5 is lost; the inner minimisation may have several local minima and golden-section search is no longer valid. The realisability gap convexification costs is bounded by `Thm 2.11` **in its corrected local form only** (`ERRATA` E6.3) — the global a-priori bound is vacuous and the operative guarantee is the a posteriori certificate `Cor 4.12`. |
| **(S5)** | **Front regularity.** There is `C_AF < ∞` with `H¹(AF ∩ B(y,ρ)) ≤ C_AF·ρ` for all `y` and all `ρ ∈ [h, r_max]`, `H¹` = 1-dimensional Hausdorff measure, `AF` = accepted front. | the edge counts in `Thm 7.3` | the accepted-front edge count inside a stencil ball is no longer `Θ(r/h)` and the sweep gains a factor equal to the number of front sheets. `C_AF ≈ 2` on open water, `≈ 3–4` at a cut locus where two sheets meet, and grows with the number of island coastlines inside a stencil ball (Maldives, Andamans, Indonesian straits). **Observable**: instrument `max_y \|NF(y)\|` and compare against `C_AF·r_max/h`. |
| **(S6)** | **Stencil geometry.** Every accepted-front edge used by `Alg 4.1` satisfies `\|y_j − y_k\| ≤ c₁h`, and every update distance satisfies `ℓ_min ≤ ℓ = \|y − ξ(ζ)\| ≤ r_max`, with `ℓ_min := h/√2` enforced **by construction** through the `ERRATA` E3 exclusion rule and `c_geo := 1/√2 = 0.707106781…`. On a lat/lon grid `c₁ = √2·(1 + O(h/R_E))`. | the `ι/ℓ` term of (7.19); the bucket width `Δ_min` of `Prop 4.9`; termination | if edge length is not `O(h)` while `ℓ` stays `Θ(h)`, the linear-interpolation error `ι = O(\|y_j−y_k\|²)` divided by `ℓ` no longer vanishes and **the scheme is inconsistent, silently**. This is why the accepted front must be re-triangulated near coastlines rather than allowed to carry long chords. Without the `ℓ_min` exclusion there is no positive lower bound on the value increment, and Dial's discipline loses its premise entirely — `ERRATA` E3 is not a refinement, it is the difference between a theorem and an assumption. |
| **(S7)** | **Residual regularity** (only for `P6`): `R` of Eq (C.8) is Lipschitz in `t` on each inter-slice interval, `L_t^R < ∞`, and the slice-boundary jumps are `O(Δt_fc)`. | monotonicity of the ground-frame corrector; consistency of the wait relaxation (`Remark 7.2.5`) | if the forecast is genuinely discontinuous in `t`, the wait-relaxed corrector converges to the *loiter-augmented* value function — a different, and in that case physically correct, limit. We do not claim `Thm 7.1` for it. |

Throughout: `k` = active objectives (`k = 3` default), `Λ` = labels retained per node, `ε` = Pareto
parameter, `n_θ = 72` (`D2`), `ρ_c = 8` and `H = ρ_c h` (`§4`), `N` = ground-domain node count,
`N_w` = **dilated** co-moving node count, `n_fc` = forecast frames in the horizon.

### 7.1.1 Three anisotropy averages, and the anisotropy the reduction *costs*

`Υ_loc(x,t) = σ_max/σ_min` is the local anisotropy (`CONTRACT` §1); `Υ = sup Υ_loc` the global one.
`Thm 7.3` needs two averages:

```
Υ₁  :=  (1/N_w) · Σ_y  Υ_loc^w(y)                                                 (7.1)
Υ₂  :=  ( (1/N_w) · Σ_y  Υ_loc^w(y)² )^{1/2}                                      (7.2)
```

`Υ₁ ≤ Υ₂ ≤ Υ`, with equality throughout iff `Υ_loc` is constant. `Υ₁` is the one that appears in
the cost of an implementation that maintains an explicit **accepted-front edge list** (the number
of front edges inside a ball of radius `r = hΥ_loc` is `Θ(C_AF Υ_loc)` by (S5), because the front
is a curve). `Υ₂` appears only in the cost of a naive implementation that **scans the disc** of
radius `r` for accepted nodes, which is `Θ(Υ_loc²)` per node. The ratio `Υ₂²/Υ₁` is therefore the
price of not maintaining the front list; **§7.5 mandates the list**. Any earlier draft text
claiming the adaptive stencil's payoff is `(Υ/Υ₂)²` is describing the disc-scan variant.

**The reduction raises anisotropy in quiet cells. This is a real cost and it is derivable.**
By Eq (C.6) the co-moving drift is `c_eff = c₀ − w`, so in the Randers case

```
Υ_loc^w(y)  =  ( V_max(y) + |c₀(y) − w| ) / ( V_max(y) − |c₀(y) − w| )            (7.3)
```

In a cell with no current, `Υ_loc = 1` in the ground frame but `Υ_loc^w = (V_max+|w|)/(V_max−|w|)`
in the co-moving frame. For the end-to-end configuration of `CORE-THEOREM` §8.2
(`V_s = 7.2 m/s`, `w = (3.0, 1.0) m/s`, `|w| = 3.1623 m/s`):

```
Υ_loc^w  =  (7.2 + 3.1623)/(7.2 − 3.1623)  =  10.3623/4.0377  =  2.566          (quiet cell)
```

so the stencil radius goes from `1·h` to `2.57·h`, the front-edge count per node from `≈2` to
`≈5.1`, and the bucket-ring depth from 2 to 10 (`Prop 7.10`). Conversely, in a storm cell where
`c₀` is aligned with `w`, `|c₀ − w| < |c₀|` and `Υ_loc^w < Υ_loc` — the reduction *reduces*
anisotropy exactly where it was worst. This is the same trade `CORE-THEOREM` §7 records for the
causality constant ("the median gets worse by ~4.5×, the worst cells get much better"), appearing
here in the cost model rather than in the licence. **Anyone reporting only the storm-cell
improvement is overselling it in this respect too.** The honest summary: the reduction converts a
*licence* problem into a *constant-factor* problem, and the constant is `≈ 2.6×` on the
front-edge count for the measured configuration.

---

## 7.2 `Thm 7.1` — convergence to the viscosity solution

### 7.2.1 The scheme, written out

`Alg 4.1` updates a node `y` from the accepted front `AF` using, for each front edge
`e = (y_j, y_k) ∈ NF(y)` and each `ζ ∈ [0,1]`,

```
ξ_e(ζ) = ζ y_j + (1−ζ) y_k ,     W̃_e(ζ) = ζ W_j + (1−ζ) W_k ,
ℓ_e(ζ) = |y − ξ_e(ζ)| ,          u_e(ζ) = (y − ξ_e(ζ)) / ℓ_e(ζ) ,
```

restricted, per `ERRATA` E3, to the **admissible parameter set**

```
Z_e(y)  :=  { ζ ∈ [0,1] : ℓ_e(ζ) ≥ ℓ_min = h/√2 } .                              (7.4)
```

The update operator on grid functions is then

```
(𝒮_h W)(y)  =    min         min      [ W̃_e(ζ)  +  ℓ_e(ζ) · F_w( y, u_e(ζ) ) ]    (7.5)
              e ∈ NF(y)   ζ ∈ Z_e(y)
```

with `min ∅ = +∞`, and `T_h` is the fixed point `T_h = 𝒮_h T_h` subject to `T_h(y_A) = 0`. (We
normalise `t₀ = 0`; the co-moving problem is autonomous so nothing depends on the epoch.)

**Four features of (7.5) are load-bearing and none is generic.**

1. **`F_w` has no time argument.** This is Theorem C.1(b). In the ground-frame scheme the metric
   is evaluated at the **departure** time `W̃_e(ζ)` — never at `W(y)`, which would make the update
   implicit and circular (`handbook` S4, cause 1) — and that dependence is the sole reason
   monotonicity is conditional there. Here there is nothing to evaluate it at. **The entire
   causality apparatus of `ERRATA` E4–E5 is vacuous in (7.5)**, and §7.2.2 Part 1 proves
   monotonicity with no hypothesis at all.
2. **`ℓ_e(ζ)` ranges over `[ℓ_min, r_max]`** with `ℓ_min = h/√2` (E3) and `r_max = h·Υ` from the
   adaptive stencil (`Prop 4.7`) — not over `{h, √2h}`.
3. **`ζ` ranges over a continuum**, so `U_h(y) := { u_e(ζ) : e ∈ NF(y), ζ ∈ Z_e(y) }` is a finite
   union of closed arcs of `S¹`, not a finite set. §7.2.3 and `Prop 7.2` are about exactly this,
   and it is the single point at which the whole convergence argument turns.
4. **The exclusion (7.4) is not cosmetic.** It is what makes `Δ_min := ℓ_min·F_min = c_geo h F_min`
   a *theorem* (`ERRATA` Lemma E3.1) rather than an assumption, and `Δ_min > 0` is simultaneously
   the acyclicity argument for existence of the fixed point (§7.2.2 Part 2), the bucket width of
   `Prop 4.9`, and the correctness condition for bucket-parallel relaxation (`Prop 7.11`).

For Barles–Souganidis (1991) we need the **residual** form. Since (7.5) says
`T_h(y) − W̃_e(ζ) − ℓ_e(ζ)F_w(·) ≤ 0` for every admissible `(e,ζ)` with equality at the minimiser,

```
                                     ⎡  r − W̃_e(ζ)                        ⎤
S_h( y, r, W )  =    max      max    ⎢ ───────────── −  F_w( y, u_e(ζ) )   ⎥        (7.6)
                  e∈NF(y)  ζ∈Z_e(y)  ⎣    ℓ_e(ζ)                           ⎦
```

so `S_h(y, T_h(y), T_h) = 0` is exactly the update, with Barles–Souganidis' sign convention
(non-decreasing in `r`, non-increasing in the neighbour values `W`).

**The limit equation.** In support-function form,

```
𝔥_w( y, ∇T_w(y) )  =  1     on Ω_w \ {y_A} ,        T_w(y_A) = 0 ,                  (7.7)
```

where `𝔥_w(y,p) = max_{v ∈ 𝒱_w(y)} ⟨v,p⟩`. *(Sign convention: `T_w` increases along travel, so for
`v ∈ 𝒱_w`, `T_w(y + vδ) ≤ T_w(y) + δ`, hence `⟨∇T_w, v⟩ ≤ 1` with equality at the optimal `v` —
i.e. `𝔥_w = 1`. Under the Randers specialisation (C.6) this reads
`√(V_s² − |c_eff⊥|²)·|∇T_w| + ⟨c_eff, ∇T_w⟩ = 1` with `c_eff = c₀ − w`, which is the form an
implementer should check against.)*

The evolutionary form used for uniqueness is

```
∂φ/∂t  +  𝔥_w( y, ∇_y φ )  =  0 ,     R(t) = { y : φ(y,t) < 0 } ,                   (7.8)
```

**and note that (7.8) is autonomous**: `𝔥_w` carries no `t`. That is what makes the comparison
argument of §7.2.4 a citation with checkable hypotheses rather than an open problem. (7.7) is
recovered from (7.8) by `T_w(y) = min{ t : φ(y,t) ≤ 0 }`; the derivation is one line and is used
later, so: on the graph `φ(y,T_w(y)) = 0`, differentiation gives `∇_yφ + (∂_tφ)∇T_w = 0`; writing
`a := −∂_tφ > 0` gives `∇_yφ = a∇T_w`, substituting into (7.8) gives `−a + 𝔥_w(y, a∇T_w) = 0`,
i.e. `a(𝔥_w(y,∇T_w) − 1) = 0` by 1-homogeneity, i.e. (7.7).

### 7.2.2 Four lemmas, then monotonicity and stability

> **Lemma 7.4 (the outrun condition implies co-moving station-keeping).** Under (A2),
> `0 ∈ int conv 𝒱_w(y)` for every `y`; equivalently (S1) / Eq (C.7) holds, with the quantitative
> bound
> ```
> B(0, σ_min^w − |w|·0)  ⊆  conv 𝒱_w(y) ,     and in the Randers case
> | c₀(y) − w |  <  V_max(y) − |w|  <  V_max(y) .                                    (7.9)
> ```
> Consequently `F_w(y,u) ≤ F_max^w := 1/σ_min^w < ∞` in **every** direction, and `Υ_loc^w < ∞`.

**Proof.** `σ_min^w = inf_{y,|u|=1} σ_w(y,u)` is by definition the worst-direction speed made good
in the co-moving frame, so `σ_w(y,u) ≥ σ_min^w > 0` for every unit `u` and every `y`; a set whose
radial function is bounded below by `σ_min^w` in every direction contains `B(0, σ_min^w)`, hence
contains `0` in its interior. (A2) asserts `|w| < σ_min^w`, which in particular asserts
`σ_min^w > 0`, which is exactly the required statement; the inequality `|w| < σ_min^w` is not
needed for the conclusion but is what makes it *checkable*, since `σ_min^w > 0` alone is the
content. For the Randers form: `𝒱_w(y) = D(c₀(y) − w, V_max(y))` by Eq (C.6), whose radial
function in the worst direction is `V_max − |c₀ − w|`, so `σ_min^w = min_y (V_max − |c₀ − w|)`,
and `|w| < σ_min^w` gives `|c₀ − w| < V_max − |w|`, which is (7.9). Finiteness of `F_w = 1/σ_w`
in every direction is immediate. ∎

**Remark (this is `ERRATA` E1 and E9, transported).** E1 killed the old condition `|c| ≥ σ_max`
(identically false, since `σ_max ≥ V_max + |c| > |c|` always). The correct condition is on
`V_max`, the **through-water** speed, and it becomes Eq (C.7) after the shift. E9 further warns
that `0 ∈ 𝒱` itself is *false* for our own default vessel whenever `|c_eff| < V_min` — with
`q_min = 0.15` and the cube law, `V_min/V_max = 0.15^{1/3} = 0.53`, so the ship cannot stop. What
`Lemma 7.4` establishes is `0 ∈ int conv 𝒱_w`, which is what `D4` solves with and what every use
below requires. The physical reading — the ship holds co-moving station by alternating headings
rather than by stopping — is `D4` earning its keep, and its cost is `Thm 2.11` **in the corrected
local form E6.3 only**: for `τ_d = 300 s`, `Δt = 6 h`, `S_leg = 150 km` the gap is under 2 s per
leg. The global a-priori bound is vacuous (`ERRATA` E6: `exp(L_v T) ≈ 1.6×10⁵` at 14 days), and
the operative global guarantee is the a posteriori certificate `Cor 4.12`.

> **Lemma 7.5 (the gauge is Lipschitz in direction, with constant `F_max^w`).** Under (S1) and
> (S4), for all `v, z ∈ ℝ²`,
> ```
> | F_w(y,v) − F_w(y,z) |  ≤  |v − z| / σ_min^w  =  F_max^w · |v − z| .              (7.10)
> ```
> In particular `u ↦ F_w(y,u)` is `F_max^w`-Lipschitz on `S¹`, and `σ_w = 1/F_w` restricted to
> `S¹` is `Υ σ_max^w`-Lipschitz.

**Proof.** By (S4) `𝒱_w` is convex and by (S1) it contains `0` in its interior, so its Minkowski
gauge `F_w(y,·)` is sublinear: positively 1-homogeneous and subadditive. Subadditivity gives
`F_w(v) = F_w(z + (v−z)) ≤ F_w(z) + F_w(v−z)`, hence `F_w(v) − F_w(z) ≤ F_w(v−z)`. Since
`B(0,σ_min^w) ⊆ 𝒱_w` (Lemma 7.4), for any `ρ ≠ 0` the vector `σ_min^w ρ/|ρ| ∈ 𝒱_w`, so
`F_w(ρ) ≤ |ρ|/σ_min^w`. Therefore `F_w(v) − F_w(z) ≤ |v−z|/σ_min^w`; exchanging `v` and `z` gives
(7.10). For the second claim,
`|σ_w(u) − σ_w(z)| = |F_w(u)−F_w(z)|/(F_w(u)F_w(z)) ≤ F_max^w|u−z|/(F_min^w)² = (σ_max^w)²F_max^w|u−z|`,
and `(σ_max^w)²F_max^w = Υ σ_max^w`. ∎

**Remark.** (7.10) is where (S4) is indispensable. For non-convex `𝒱_w` the gauge is not
subadditive and no Lipschitz-in-direction bound follows from `B(0,σ_min^w) ⊆ 𝒱_w` alone: a thin
banned wedge of angular width `ϑ` makes `σ_w` drop by `σ_max^w − σ_min^w` across `ϑ`, so the
Lipschitz constant is `Θ(1/ϑ)` and blows up as the wedge narrows. Seakeeping bans produce exactly
such wedges (a synchronous-roll ban is an interval of encounter frequencies, hence of headings),
so this is not hypothetical. `D4` removes it by convexifying before the solve.

> **Lemma 7.6 (Hausdorff perturbation of the indicatrix).** Let `𝒱_w, 𝒱_w'` both satisfy
> (S1)/(S4) with the same `σ_min^w, σ_max^w`, and let `d = d_H(𝒱_w, 𝒱_w')`. Then for all `p` and
> all unit `u`,
> ```
> | 𝔥_w(p) − 𝔥_w'(p) | ≤ d·|p| ,     | F_w(u) − F_w'(u) | ≤ d·σ_max^w/(σ_min^w)³ .   (7.11)
> ```

**Proof.** *Support function.* `𝒱_w' ⊆ 𝒱_w + dB` gives `𝔥_w'(p) ≤ 𝔥_w(p) + d|p|`; symmetrically.
*Gauge.* `𝒱_w' ⊆ 𝒱_w + dB`, and since `σ_min^w B ⊆ 𝒱_w` with `𝒱_w` convex,
`dB ⊆ (d/σ_min^w)𝒱_w`, so `𝒱_w' ⊆ (1 + d/σ_min^w)𝒱_w`, whence
`σ_w'(u) ≤ (1 + d/σ_min^w)σ_w(u)` and `|σ_w(u) − σ_w'(u)| ≤ σ_max^w d/σ_min^w`. Then
`|F_w − F_w'| = |σ_w − σ_w'|/(σ_wσ_w') ≤ (σ_max^w d/σ_min^w)/(σ_min^w)²`. ∎

`Lemma 7.6` is the tool used three times below: to price the `n_θ` support tabulation
(`Remark 7.2.6`), to price the residual `R` of Eq (C.8) as a metric perturbation (§7.5, `P6`), and
to bound the coarse-solve dilation of `D5`.

> **Lemma 7.7 (transfer from (7.8) to (7.7)).** Under (S1), the co-moving reachable sets are
> nested, `R(t₁) ⊆ R(t₂)` for `0 ≤ t₁ ≤ t₂`; hence `φ(y,·)` is non-increasing,
> `{t : φ(y,t) ≤ 0}` is a closed half-line `[T_w(y), ∞)`, and `T_w(y) = min{t : φ(y,t) ≤ 0}` is
> single-valued. Uniqueness of `φ` therefore implies uniqueness of `T_w`.

**Proof.** By (S1), `0 ∈ int conv 𝒱_w(y)` for every `y`, so under `D4` (we solve with the convex
hull) the constant control `ẏ = 0` is admissible everywhere: a point reachable by time `t₁` is
reachable by time `t₂ ≥ t₁` (reach it, then hold co-moving station), giving `R(t₁) ⊆ R(t₂)`. Since
`R(t) = {φ(·,t) < 0}` and `φ` is continuous, `φ(y,·)` is non-increasing across its sign change, so
its zero-sublevel set in `t` is a closed half-line; single-valuedness follows, and the
identification of `T_w` with the viscosity solution of (7.7) is the computation after (7.8). ∎

**What "hold co-moving station" means physically, and why it is not free.** `ẏ = 0` means
`ẋ = w`: the ship *travels with the weather system* at `w`. It is not loitering. Under (A2) the
ship can do better than that in every direction, which is precisely why the interception
constraint is **active** at the optimum (Thm C.1(c)) and why **no wait relaxation appears anywhere
in `P3`**. `ERRATA` E5's `ℓ`-scaled, horizon-truncated relaxation `F̃_ℓ` is needed only in `P6`,
the ground-frame residual corrector, and it must be evaluated at the *same* `ℓ` the update uses
and truncated at `S_max(t) = (t₀⁻ + H_fc) − t`; the run log must report how many evaluations were
horizon-truncated.

---

> ### **Thm 7.1 (convergence to the viscosity solution).**
> Assume (A1)–(A2) and (S1)–(S6). Let `T_h` be the fixed point of (7.5) produced by `Alg 4.1`
> with the adaptive stencil of `Prop 4.7`, the `ℓ_min` exclusion (7.4), the bucket discipline of
> `Prop 4.9`, and (for `k = 1`) exact rather than `ε`-pruned labels. Then the scheme (7.6) is
> **monotone**, **stable** and **consistent** with (7.7), the comparison principle of §7.2.4 holds
> for (7.8), and consequently
> ```
> T_h  →  T_w    locally uniformly on Ω_w \ {y_A}    as  h → 0 ,
> ```
> where `T_w` is the unique viscosity solution of (7.7). The ground-frame arrival time is then
> recovered exactly, without further discretisation in time, by Thm C.1(c)–(d). For `k ≥ 2` with
> `ε`-pruning the same conclusion holds for each objective up to the multiplicative factor of
> `Thm 5.2`; the joint limit is `Conjecture 7.9`.
>
> **Monotonicity is unconditional.** No causality hypothesis appears in the statement. This is
> the only place in the KAIROS literature where that is true, and it is a consequence of
> Theorem C.1(b), not of anything in §7.

**Proof — Part 1, monotonicity.** Barles–Souganidis require `S_h(y,r,W)` non-decreasing in `r` and
non-increasing in `W` under the pointwise order. Fix an admissible `(e,ζ)` and write
`ℓ = ℓ_e(ζ) ∈ [ℓ_min, r_max]`, `u = u_e(ζ)`, `a = W̃_e(ζ)`; the bracket of (7.6) is

```
g(r,a)  =  (r − a)/ℓ  −  F_w(y, u) .
```

*In `r`:* `∂g/∂r = 1/ℓ > 0`, and a maximum of functions non-decreasing in `r` is non-decreasing in
`r`. ✓

*In `W`:* the dependence is only through `a`, and `a = ζW_j + (1−ζ)W_k` is a convex combination
with non-negative weights, so it suffices that `g` be non-increasing in `a`. Since `F_w` does not
depend on `a` at all (Theorem C.1(b)),

```
g(r,a₂) − g(r,a₁)  =  −(a₂ − a₁)/ℓ   <  0     for  a₂ > a₁ ,                       (7.12)
```

with **no condition whatsoever**. A maximum of non-increasing functions is non-increasing. ✓ ∎(1)

> **Contrast, stated precisely because it is the contribution.** In the ground frame the same
> computation gives, by (S7)/`ERRATA` E4,
> ```
> g(r,a₂) − g(r,a₁)  ≤  −(a₂ − a₁)(1/ℓ − L_t) ,                                     (7.13)
> ```
> so monotonicity holds **iff `ℓ·L_t ≤ 1`**, and since `ℓ` ranges up to the ordered-upwind radius
> `r(y) ≤ Υ_loc·h` the licence needed is `r(y)·L_t ≤ 1` — `ERRATA` (E4.1) — which is a factor `Υ`
> stronger than the `h·L_t ≤ 1` of the pre-errata drafts, and `Υ` is precisely the quantity the
> ordered-upwind machinery exists to handle. An implementation built to the old condition reports
> a green causality certificate on forecasts where the sweep is not licensed. In the co-moving
> frame (7.13) degenerates to (7.12) because `L_t ≡ 0`, **to the last bit**: `CORE-THEOREM` Test
> 8.10 regime A measures the co-moving `L_t` as `0.0` max, `0.0` p99, `0.0` median. In regimes B
> and C, where (A1) is violated and the residual must be carried, the reduction moves
> `r·L_t` from **1.309 (violated)** to **0.272 (satisfied)** and from **1.307** to **0.261** —
> i.e. it converts a solve that is *not licensed* into one that is, which is the practical content
> of contribution 3. The median degrades 4.5× in the same experiment and that is reported here as
> it is there.

**Proof — Part 2, stability.** Two claims: the fixed point exists and is unique, and `{T_h}` is
uniformly bounded independently of `h`.

*Existence and uniqueness of the fixed point.* By (7.4) every admissible bracket satisfies
`ℓ ≥ ℓ_min = h/√2`, and by (S1) `F_w ≥ F_min^w = 1/σ_max^w > 0`, so

```
W̃_e(ζ) + ℓ F_w(y,u)  ≥  W̃_e(ζ) + Δ_min ,      Δ_min := c_geo·h·F_min^w > 0 .       (7.14)
```

Since `W̃_e(ζ) ≥ min(W_j, W_k)`, the value assigned to `y` exceeds the value of **every** node it
depends on by at least `Δ_min`. Hence the dependency relation is acyclic: order nodes by assigned
value; every dependency strictly decreases it by at least `Δ_min`. An acyclic explicit recursion
has exactly one solution, computed in one pass in non-decreasing order of value — which is
`Prop 4.9`'s premise, and `Δ_min` here is exactly the Dial bucket width of `ERRATA` (E3.1).
**Without the `ℓ_min` exclusion this argument collapses**: `ξ_e(ζ)` may lie arbitrarily close to
`y`, `ℓ` has infimum 0 over the open interval, and there is no positive lower bound on the
increment — which is precisely `ERRATA` E3, and it is fatal, not cosmetic.

*Uniform bounds.* Lower: `T_h ≥ 0`, since every bracket exceeds its front value and the source is
`0`. Upper: fix a node `y`. By (S3) and connectivity of the navigable set there is a stencil path
`y_A = z_0, z_1, …, z_M = y` with `|z_{i+1} − z_i| ≤ c₁h` and total length `≤ ℓ_Ω`, where `ℓ_Ω` is
the supremum over `y` of the shortest admissible polyline length from `y_A` to `y` inside `Ω_w`,
finite and `h`-independent by (S3). Applying (7.5) along that path with `F_w ≤ F_max^w`,

```
0  ≤  T_h(y)  ≤  F_max^w · ℓ_Ω        for every  h ≤ h₀ .                          (7.15)
```

The lower bound uses (S1) only through `F_min^w > 0`; the upper bound uses it through
`F_max^w < ∞`, i.e. `0 ∈ int conv 𝒱_w`, i.e. Eq (C.7), which `Lemma 7.4` derives from (A2). ∎(2)

### 7.2.3 Consistency, and exactly where the continuum of directions is needed

**Proof — Part 3, consistency.** Barles–Souganidis require: for every `ψ ∈ C^∞(Ω_w)` and every
`y* ∈ Ω_w \ {y_A}`,

```
lim sup / lim inf     S_h( y, ψ(y) + κ, ψ + κ )   →   𝔥_w( y*, ∇ψ(y*) ) − 1        (7.16)
  h→0, y→y*, κ→0
```

up to a fixed positive normalisation. We prove the stronger statement that the residual is `O(h)`
with an explicit constant, and we isolate the one step at which the direction set must be a
continuum.

*Step 3a — expansion of one bracket.* Fix `e ∈ NF(y)`, `ζ ∈ Z_e(y)`; write `ξ = ξ_e(ζ)`,
`ℓ = ℓ_e(ζ)`, `u = u_e(ζ)`, so `ξ = y − ℓu`. The scheme uses the **linear interpolant**
`W̃_e(ζ) = ζψ(y_j) + (1−ζ)ψ(y_k) + κ`, not `ψ(ξ) + κ`. The interpolation defect is

```
ι_e(ζ) := W̃_e(ζ) − κ − ψ(ξ_e(ζ)) ,     |ι_e(ζ)| ≤ (1/8)·|y_j − y_k|²·‖D²ψ‖_∞
                                                 ≤ (c₁²/8)·h²·‖D²ψ‖_∞ ,           (7.17)
```

the exact error of linear interpolation of a `C²` function on a segment (maximum
`½|ζ(1−ζ)|·|y_j−y_k|²·‖D²ψ‖` at `ζ = ½`, giving the `1/8`). (S6) supplies `|y_j−y_k| ≤ c₁h`.
Taylor expansion of `ψ` at `y` along `−ℓu`:

```
ψ(ξ) = ψ(y) − ℓ⟨∇ψ(y),u⟩ + (ℓ²/2)·uᵀD²ψ(y)u + R₃ ,     |R₃| ≤ (ℓ³/6)‖D³ψ‖_∞ .      (7.18)
```

Therefore, with `r = ψ(y) + κ` and noting that the `κ` cancels between `r` and `W̃_e(ζ)`,

```
r − W̃_e(ζ)                            ℓ                  R₃ + ι_e(ζ)
───────────  =  ⟨∇ψ(y), u⟩  −  ─── uᵀD²ψ(y) u  −  ─────────────── .                (7.19)
   ℓ                                   2                        ℓ
```

**This is the whole expansion.** In the ground-frame scheme there is a second error source here,
because `F` must additionally be evaluated at the perturbed departure time `W̃_e(ζ)` rather than at
`ψ(y)`, contributing `L_t·( |κ| + ℓ‖∇ψ‖_∞ + |ι| + |R₃| )` to every bracket. **In the co-moving
frame that term is identically absent**, since `F_w` has no time argument. Collecting, each bracket
of (7.6) equals `⟨∇ψ(y),u⟩ − F_w(y,u)` plus an error `E_e(ζ)` bounded by

```
             ℓ                |R₃| + |ι_e(ζ)|
|E_e(ζ)| ≤  ─── ‖D²ψ‖_∞  +  ──────────────────
             2                       ℓ

          ≤  (Υh/2)‖D²ψ‖  +  (c₁²h²/8)‖D²ψ‖/(c_geo h)  +  (Υ³h³/6)‖D³ψ‖/(c_geo h)   (7.20)

          =  h·[ (Υ/2)‖D²ψ‖ + (c₁²/(8c_geo))‖D²ψ‖ ]  +  h²·(Υ³/(6c_geo))‖D³ψ‖  =  O(h),
```

uniformly in `(e,ζ)`, using `ℓ ≤ r_max = Υh` in the numerators and `ℓ ≥ ℓ_min = c_geo h` in the
denominators. With `c₁ = √2` and `c_geo = 1/√2`: `c₁²/(8c_geo) = 2/(8·0.7071) = 0.354`.

> **All error terms are `O(h)` because `ℓ = Θ(h)` in both numerator and denominator. The term that
> would destroy this is `ι/ℓ`, which is `O(h)` only because (S6) forces `|y_j−y_k| = O(h)` while
> the E3 exclusion forces `ℓ ≥ c_geo h`.** That is the sole role of (S6), and an implementation
> that lets accepted-front chords grow long near coastlines loses consistency silently — the
> routes still look fine. `handbook` S3 is the symptom entry for this failure.

*Step 3b — the maximisation, and the continuum.* Taking the max over `(e,ζ)` in (7.6),

```
| S_h(y, ψ(y)+κ, ψ+κ)  −   max      [ ⟨∇ψ(y),u⟩ − F_w(y,u) ] |   ≤   sup |E_e(ζ)|   (7.21)
                        u ∈ U_h(y)
```

where `U_h(y) = { u_e(ζ) : e ∈ NF(y), ζ ∈ Z_e(y) } ⊆ S¹`. Define
`g_y(u) := ⟨∇ψ(y),u⟩ − F_w(y,u)` on `S¹`. By **Lemma 7.5**, `g_y` is Lipschitz on `S¹` with

```
Lip(g_y)  ≤  |∇ψ(y)|  +  F_max^w .                                                  (7.22)
```

Let `δ_h(y) := max_{u ∈ S¹} dist(u, U_h(y))` be the **covering radius** (fill distance) of the
scheme's direction set. Then

```
0  ≤   max_{u ∈ S¹} g_y(u)  −  max_{u ∈ U_h(y)} g_y(u)   ≤   (|∇ψ(y)| + F_max^w)·δ_h(y).  (7.23)
```

> **This is the step that needs the continuum.** Combining (7.21) and (7.23), the scheme is
> consistent **iff `δ_h(y) → 0` on the arc containing the maximiser**, and the residual left over
> is exactly `(|∇ψ| + F_max^w)·δ_h(y)` — **a quantity with no `h` in it.** Refining the grid does
> not reduce it. Only enlarging the direction set does. That is the entire argument for the
> `ζ`-continuum, and it is why `Prop 7.2` below is a theorem about a *different limit equation*
> rather than about a slower rate.

The `ζ`-continuum supplies `δ_h = 0` on the relevant arc, as follows. For a single front edge
`e = (y_j,y_k)`, the map `ζ ↦ u_e(ζ)` is continuous on the compact set `Z_e(y)` (the denominator
`ℓ_e(ζ) ≥ ℓ_min > 0` never vanishes, by (7.4)), so its image is a finite union of closed arcs
`A_e ⊆ S¹` subtended at `y` by the admissible part of the segment `[y_k, y_j]`. By `Prop 4.7`,
`NF(y)` contains a connected portion of `AF` separating `y` from the accepted region, so the true
optimal characteristic reaching `y` crosses `AF` inside `NF(y)` at some point `ξ*` on some edge
`e*`. Two cases. If `|y − ξ*| ≥ ℓ_min`, then `u* = (y−ξ*)/|y−ξ*| ∈ A_{e*} ⊆ U_h(y)` and the
maximiser is attained **exactly**, giving equality in (7.23). If `|y − ξ*| < ℓ_min` then by
`Lemma E3.1` the crossing point is not the perpendicular foot on any front edge, and the same
characteristic, extended backwards past `ξ*`, crosses a *different* accepted-front edge at
distance `≥ ℓ_min` whose direction differs from `u*` by `O(h/ℓ_min) = O(1)`… **and this is exactly
where the E3 exclusion costs something.** The honest statement:

```
δ_h(y)  =  0        whenever the optimal characteristic crosses NF(y) at distance ≥ ℓ_min ;
δ_h(y)  ≤  arcsin(ℓ_min / ℓ_next)   otherwise,                                      (7.24)
```

where `ℓ_next ≥ ℓ_min` is the distance to the next front edge crossed. Since the front is
8-connected and `Lemma E3.1` gives perpendicular distance `≥ h/√2 = ℓ_min` to **every** front
edge, the second case is empty: no admissible characteristic can cross a front edge at distance
below `ℓ_min`, so the exclusion (7.4) removes only parameter values that correspond to no
characteristic at all. `δ_h ≡ 0` on the relevant arc. This is the sense in which `ERRATA` E3's
claim that the exclusion "costs nothing" is a theorem: it costs nothing *because* `ℓ_min` is the
geometric infimum rather than an arbitrary safety margin. Consequently

```
| S_h(y,ψ(y)+κ,ψ+κ)  −  max_{u∈S¹} g_y(u) |   ≤   sup_{e,ζ} |E_e(ζ)|   =   O(h).    (7.25)
```

*Step 3c — the polar identity.* It remains to identify `max_{u∈S¹} g_y(u) = 0` with (7.7).

> **Claim.** Under (S1) and (S4), for any `p ∈ ℝ²`,
> `max_{|u|=1} [ ⟨p,u⟩ − F_w(y,u) ] = 0` **iff** `𝔥_w(y,p) = 1`; and the map
> `θ ↦ max_{|u|=1}[⟨p,u⟩ − θF_w(y,u)]` is strictly decreasing on `θ > 0`, so the two conditions cut
> out the same level set.

*Proof of claim.* For unit `u`, `F_w(y,u) = 1/σ_w(y,u)` by `Def 2.3`. Since `𝒱_w` is convex,
compact and contains `0` in its interior, every boundary point is `σ_w(u)u` for a unique unit `u`,
and the maximum of a linear functional over a compact convex set is attained on the boundary, so
`𝔥_w(y,p) = max_{v∈𝒱_w}⟨v,p⟩ = max_{|u|=1} σ_w(y,u)⟨u,p⟩`.

(⇐) Suppose `𝔥_w(y,p) = 1`. Then `σ_w(u)⟨u,p⟩ ≤ 1` for every unit `u`, i.e. `⟨p,u⟩ ≤ 1/σ_w(u) =
F_w(u)`, so `g_y ≤ 0` everywhere. `S¹` is compact and `g_y` continuous (Lemma 7.5), so a maximiser
exists; at the `u*` attaining `𝔥_w` we have `σ_w(u*)⟨u*,p⟩ = 1`, hence `g_y(u*) = 0`. So
`max g_y = 0`.

(⇒) Suppose `max_{|u|=1} g_y(u) = 0`. Then `⟨p,u⟩ ≤ F_w(u) = 1/σ_w(u)` for all `u`, so
`σ_w(u)⟨u,p⟩ ≤ 1` for all `u`, giving `𝔥_w ≤ 1`; and at the maximiser `u*`, `σ_w(u*)⟨u*,p⟩ = 1`,
giving `𝔥_w ≥ 1`. Hence `𝔥_w = 1`.

Strict monotonicity in `θ`: for `θ₂ > θ₁ > 0` and any `u`,
`⟨p,u⟩ − θ₂F_w(u) ≤ ⟨p,u⟩ − θ₁F_w(u) − (θ₂−θ₁)F_min^w`, and `F_min^w > 0` by (S1); taking maxima
gives a strict decrease of at least `(θ₂−θ₁)F_min^w`. ∎(claim)

Applying the claim with `p = ∇ψ(y)`, (7.25) becomes: `S_h(y,ψ(y)+κ,ψ+κ) → 0` exactly when
`𝔥_w(y*,∇ψ(y*)) = 1`, with residual `O(h)`. Since `S_h` is continuous in `(y,r)` and the bound
(7.20) is uniform on compact subsets of `Ω_w \ {y_A}`, the `lim sup` and `lim inf` in (7.16)
coincide, and the normalisation is the positive factor supplied by (7.23). ∎(3)

### 7.2.4 The comparison principle, with hypotheses checked

Barles–Souganidis needs **strong uniqueness** for the limit equation: any bounded
upper-semicontinuous viscosity subsolution is `≤` any bounded lower-semicontinuous supersolution.

**Why (7.7) is not covered directly by the textbook statement.** Comparison for
`H(y, W, DW) = 0` in the standard form (Crandall–Ishii–Lions 1992, condition (0.3)) requires
**properness**, `H(y,r,p) − H(y,s,p) ≥ γ(r−s)` for `r ≥ s` with `γ > 0`. Here
`H(y,r,p) = 𝔥_w(y,p) − 1` is *independent of `r`*, so `γ = 0` and the textbook theorem does not
apply as written. In the ground frame the situation is worse: `∂_r𝔥` may be **negative** (weather
improving), which is the continuum shadow of the FIFO problem. The reduction has removed the sign
problem but not the degeneracy, so we route uniqueness through the evolutionary form (7.8), where
comparison is classical.

> **Comparison principle (CP), used as a citation with hypotheses verified.**
> Consider the Cauchy problem (7.8) on `Ω_w × (0, H]` with `φ(·,0) = φ₀` bounded and uniformly
> continuous, under the state-constraint boundary condition on `∂Ω_w` induced by `F_w ≡ +∞`
> outside `Ω_w` (S3). Suppose
> * **(C1)** `𝔥_w : Ω̄_w × ℝ² → ℝ` is continuous, convex and positively 1-homogeneous in `p`;
> * **(C2)** `|𝔥_w(y,p) − 𝔥_w(z,p)| ≤ L_𝒱·|y−z|·|p| ≤ L_𝒱·|y−z|·(1+|p|)` (structure condition);
> * **(C3)** `σ_min^w|p| ≤ 𝔥_w(y,p) ≤ σ_max^w|p|` (coercivity and linear growth);
> * **(C4)** `Ω_w` bounded with Lipschitz boundary.
>
> Then (7.8) satisfies a comparison principle, hence has a unique bounded uniformly continuous
> viscosity solution. This is Crandall & Lions (1983) as extended to state constraints by Soner
> (1986); the convex, 1-homogeneous, coercive case is the setting of Ishii (1987) and of Bardi &
> Capuzzo-Dolcetta (1997, Ch. II–IV).

**Verification for KAIROS.** (C1): `𝔥_w(y,·)` is a support function, hence convex and positively
1-homogeneous for every `y`; continuity in `y` follows from `Lemma 7.6` and (S2). Convexity of
`𝒱_w` is not needed for (C1) — `𝔥_𝒱 = 𝔥_{conv𝒱}` — but is needed by (S4) elsewhere. (C2): from
`Lemma 7.6`, `L_𝒱` is the Hausdorff-Lipschitz constant of `y ↦ 𝒱_w(y)`, finite by (S2); note the
absence of any `t`-component, which is what makes the Cauchy problem autonomous. (C3): `Lemma 7.4`
and (S1). (C4): (S3).

**A second, independent route for the stationary form.** Because `𝔥_w` is positively
1-homogeneous, `θ·T_w` is a *strict* subsolution of (7.7) for every `θ ∈ (0,1)`:
`𝔥_w(y, ∇(θT_w)) = θ·𝔥_w(y,∇T_w) = θ < 1`. Together with `T_w(y_A) = 0` (so `θT_w = T_w = 0` at
the source) this supplies the strict subsolution that the standard doubling-of-variables argument
for coercive convex stationary Hamiltonians requires (Ishii 1987; Bardi & Capuzzo-Dolcetta 1997,
Thm IV.4.5). **This route is available only because the co-moving problem is autonomous and the
source value is 0**; it is not available in the ground frame, where `T(x_A) = t₀ ≠ 0` and scaling
by `θ` does not preserve the boundary datum. We record it because it is simpler than the level-set
route and an implementer verifying the theory may prefer it.

**Where (S1) does its second job.** Without `0 ∈ int conv 𝒱_w` — i.e. where Eq (C.7) fails and the
ship cannot hold co-moving station — the reachable set is **not** monotone in `t`, `φ(y,·)` can
change sign twice, and `T_w` as defined is not the value function of a well-posed stationary
problem. Any label-setting method is then structurally wrong on that sub-domain, independently of
any discretisation issue.

**Proof — Part 4, conclusion.** Monotone (Part 1, unconditionally), stable (Part 2), consistent
(Part 3), with the comparison principle above. Barles & Souganidis (1991), Theorem 2.1, yields
locally uniform convergence of `T_h` to the unique viscosity solution of (7.7) on `Ω_w \ {y_A}`. ∎

### 7.2.5 Remarks on `Thm 7.1`

**Remark 7.2.1 (what each hypothesis buys, minimal form).** (S1) ⟹ stability, coercivity (C3),
*and* `Lemma 7.7`. (S2) ⟹ (C2) and the continuity of `𝔥_w` in `y`. (S3) ⟹ (7.15), (C4), and the
correctness of `P4`. (S4) ⟹ `Lemma 7.5` ⟹ the Lipschitz constant (7.22), without which (7.23)
gives no bound and consistency cannot be quantified. (S6) ⟹ the `ι/ℓ` term is `O(h)` and
`Δ_min > 0`. (S5) and (S7) are **not used** in `Thm 7.1`; they are used in `Thm 7.3` and in
`Remark 7.2.5` respectively. **No causality hypothesis is used anywhere.**

**Remark 7.2.2 (rate is not claimed here).** Barles–Souganidis is a *qualitative* theorem. It
gives no rate. §7.3 addresses rates separately and honestly.

**Remark 7.2.3 (the point source).** `T_w(y_A) = 0` is a point Dirichlet condition at which `T_w`
is not differentiable; the standard device is to solve on `Ω_w \ B(y_A,δ)` with the exact boundary
datum on `∂B(y_A,δ)` and let `δ → 0`, using that `T_w` is the maximal subsolution vanishing at
`y_A` (Bardi & Capuzzo-Dolcetta 1997, Ch. IV). Numerically the same issue appears as an `O(h)`
initialisation error concentrated near `y_A` which then propagates globally; the remedy is to seed
`Alg 4.1` with exact values on a disc of radius `2h` around `y_A` from the closed-form Randers
metric with `c ← c₀ − w` (`CORE-THEOREM` §6: every closed form and every golden vector of
`handbook/01-golden-vectors.md` carries over verbatim under that substitution), and from a local
`n_θ`-direction integration where a ban is active. **Without this seeding the observed global
error saturates at the seeding error and a refinement study looks first-order-with-a-floor** —
a classic and easily misdiagnosed artefact, and one that is easy to confuse with the genuine
metrication floor of `Prop 7.2`. The discriminating test is `handbook` S3: disable the wide
stencil but keep the `ζ` search.

**Remark 7.2.4 (failure of (S1): the one-sided sub-domain).** Let
`Ω_w⁻ := { y : |c₀(y) − w| ≥ V_max(y) }` — the corrected condition, per `ERRATA` E1; **not**
`|c| ≥ σ_max`, which is identically false. On `Ω_w⁻` the reachable directions form a cone about
`c₀ − w` of half-angle `α_reach = arcsin(V_max/|c₀−w|)` (E1.1) and `F_w = +∞` outside it;
`F_max^w = ∞`, (7.15) is vacuous, `Lemma 7.7` fails, `Υ_loc^w = ∞`. `Alg 4.1` handles this by
capping `r(y) ≤ r_max` and restricting the `ζ`-minimisation to directions with `F_w < ∞`. What
survives: `Thm 7.1` holds verbatim on any relatively open sub-domain `Ω' ⊆ Ω_w \ Ω_w⁻` reachable
from `y_A` by a path staying in `Ω'`, with `σ_min^w, σ_max^w` taken over `Ω'`. On `Ω_w⁻` the scheme
still terminates and still produces a valid **upper** bound on arrival time (every value it assigns
corresponds to a realisable path), but neither consistency nor comparison is available, and those
values must be reported as *feasible*, not *optimal*. An implementation must carry a per-node
one-sided flag and propagate it into the output. `|c₀ − w| = V_max` exactly: treat as excluded,
`F_w = +∞`, per E1. This is a genuine limitation, not a discretisation artefact, and it has a
correct physical reading: *you cannot escape this storm.*

**Remark 7.2.5 (the wait relaxation is a `P6`-only device).** In `P3` it does not appear at all:
by Theorem C.1(c) the interception constraint is active at `t*`, so the optimum never loiters. In
`P6`, where the ground-frame residual is carried, the corrected relaxation is `ERRATA` (E5.1),

```
F̃_ℓ(x,t,u) := inf over s ∈ [0, S_max(t)] of [ s/ℓ + F(x,t+s,u) ] ,
S_max(t)    := (t₀⁻ + H_fc) − t ,                                                   (7.26)
```

evaluated at the **same `ℓ` the update uses** — not `s/h`, which over-charges the wait by up to
`Υ` and therefore does *not* produce the running infimum, so unconditional causality does not
follow from it. With (7.26), `a + ℓF̃_ℓ = inf_{b ∈ [a, a+S_max]}[ b + ℓF(x,b,u) ]`, which is
non-decreasing in `a` as the infimum of a fixed function over a shrinking set, so
`g̃(r,a) = (r − [a + ℓF̃_ℓ])/ℓ` is non-increasing in `a` unconditionally: the relaxation restores
monotonicity **at the level of the scheme operator**, which is the precise sense in which it
works. Two further points, both from `ERRATA` E5: `F̃_ℓ` contains the scheme parameter `ℓ`, so it
is a scheme-level object and cannot be identified with a continuum metric; and the infimum must
be truncated at the forecast horizon, with the count of truncated evaluations reported in the run
log. Under (S7), `L_t^R < ∞`, and the wait branch is selected only when `ℓ L_t^R > 1`, so for
`h < 1/(Υ L_t^R)` we have `F̃_ℓ ≡ F` and the relaxation **switches itself off under refinement**;
`Thm 7.1`'s limit is unaffected. If (S7) fails, the corrector converges instead to the
loiter-augmented value function, which is a different (obstacle-type) PDE. We do not claim
`Thm 7.1` for it.

**Remark 7.2.6 (the `n_θ = 72` tabulation is not a metrication error).** `Prop 2.7` tabulates
`𝔥_w` on `n_θ` directions and recovers `F_w` at arbitrary directions by interpolation in the dual.
This perturbs `𝒱_w` by a Hausdorff distance controlled by the second angular derivative of the
support function: for `p(ϑ) = (cos ϑ, sin ϑ)`, linear interpolation of `ϑ ↦ 𝔥_w(p(ϑ))` on a mesh
of width `Δϑ = 2π/n_θ` has error `≤ (Δϑ²/8)·sup|∂²_ϑ𝔥_w|`, and for the Randers case
`𝔥_w = V_s + |c_eff|cos(ϑ − ϑ_c)` this is exactly `|∂²_ϑ𝔥_w| = |c_eff|`. Hence the relative metric
error is `≤ (Δϑ²/8)·|c_eff|/(V_s − |c_eff|)`. At `n_θ = 72`, `Δϑ²/8 = 9.518×10⁻⁴`; for the
end-to-end configuration (`V_s = 7.2`, `|c_eff| = |w| = 3.162` in a quiet cell) this is

```
9.518e-4 × 3.162/(7.2 − 3.162)  =  9.518e-4 × 0.7831  =  7.45e-4  =  0.075 % .      (7.27)
```

By `Lemma 7.6` this is an `O(n_θ^{-2})` perturbation of the *same* PDE: it changes the limit by
`O(n_θ^{-2})` and can be driven to zero **independently of `h`**, at a cost linear in `n_θ`.
`Prop 7.2` shows an `m`-neighbour stencil is a categorically different animal: it changes the
limit by `Θ(m^{-2})` **and** couples `m` to the stencil geometry, so it cannot be driven to zero
without changing the algorithm's cost per node in a way that also lengthens the stencil arms.

**Remark 7.2.7 (exactness check for implementers).** Set `c₀ ≡ 0`, `w = 0`, `σ ≡ σ_s`, no bans.
Then `𝒱_w = B(0,σ_s)`, `𝔥_w(p) = σ_s|p|`, (7.7) reads `|∇T_w| = 1/σ_s`, and the exact solution is
`T_w(y) = |y − y_A|/σ_s`. Substituting a linear `ψ` into (7.17)–(7.25) makes every error term
vanish identically (`D²ψ = D³ψ = 0`, `ι ≡ 0`), so the scheme is **exact** on this instance for
every `h` and every stencil radius. Any implementation not reproducing `T_w` to machine precision
here has a bug in the `ζ`-minimisation or the interpolant, not a discretisation error. The
quantitative version with drift is golden vector **G4**: `V_s = 7.2`, uniform `c = (1.5,0)`,
0°N 0°E → 0°N 5°E, exact arrival `63 905.1303 s = 17.751425 h` eastbound and `97 539.4093 s =
27.094280 h` westbound, with the ratio `1.5263157895` required to equal
`Υ = (V_s+|c|)/(V_s−|c|) = 8.7/5.7` to all printed digits. Under the reduction the same test runs
with `c ← c₀ − w`, unchanged.

---

## 7.3 `Prop 7.2` — a fixed `m`-neighbour stencil is not consistent

This is the formal version of the claim that motivates the `ζ`-continuum, stated with the exact
residual so a reader can decide whether it matters at their resolution. **It also applies to the
shipped reference implementation** (`comoving.stationary_sweep` uses a fixed 16-neighbour
stencil), which is why every measured number in `CORE-THEOREM` carries a ~1 % floor.

**Setting.** Let `{u_1,…,u_m} ⊂ S¹` be a **fixed** direction set (independent of `h`), `ℓ_i > 0`
the corresponding lattice step lengths, and

```
(𝒮_h^{(m)} W)(y)  =   min_{1≤i≤m}  [ W(y − ℓ_iu_i)  +  ℓ_i F_w( y, u_i ) ] ,        (7.28)
```

residual form `S_h^{(m)}(y,r,W) = max_i [ (r − W(y−ℓ_iu_i))/ℓ_i − F_w(y,u_i) ]`. This is exactly
Dijkstra/A\* on an `m`-neighbour grid graph — the baseline, with `m = 16`. Define the **inscribed
indicatrix**

```
𝒫_m(y)  :=  conv{ σ_w(y,u_i)·u_i : i = 1..m }   ⊆   𝒱_w(y) .                        (7.29)
```

> **Prop 7.2.** Under (A2), (S1)–(S4), with `ℓ_i = Θ(h)`:
>
> **(a)** `𝒮_h^{(m)}` is monotone and stable, by the proofs of `Thm 7.1` Parts 1–2 verbatim.
> (In the co-moving frame monotonicity is again unconditional; in the ground frame it needs
> `max_i ℓ_i·L_t ≤ 1`.)
>
> **(b)** `𝒮_h^{(m)}` is **consistent with the wrong equation**: for every `ψ ∈ C^∞`,
> `S_h^{(m)}(y, ψ(y)+κ, ψ+κ) → 0` as `h→0, y→y*, κ→0` **iff** `𝔥_{𝒫_m}(y*, ∇ψ(y*)) = 1`. It is
> therefore *not* consistent with (7.7) unless `𝒱_w = 𝒫_m`, and the residual
> ```
> E_m(y,p)  :=  𝔥_w(y,p) − 𝔥_{𝒫_m}(y,p)  ≥  0        contains no h.                  (7.30)
> ```
>
> **(c)** The induced error is a *relative* error on the metric, given exactly by the radial
> function of the inscribed polygon. For unit `u` between adjacent rays `u_i, u_{i+1}` at angles
> `α, β ≥ 0` with `α + β = Δ := 2π/m`, writing `σ_i = σ_w(y,u_i)`,
> ```
>                       σ_i σ_{i+1} sin Δ
> σ_{𝒫_m}(u)  =  ─────────────────────────────── ,       F_{𝒫_m}(u) = 1/σ_{𝒫_m}(u) . (7.31)
>                  σ_i sin α  +  σ_{i+1} sin β
> ```
> Hence `F_{𝒫_m}/F_w = σ_w/σ_{𝒫_m} ≥ 1`, with
> ```
> max_u σ_w(u)/σ_{𝒫_m}(u)  ≤  (1 + 2Υ_loc^w Δ) / [ (1 − Υ_loc^w Δ)²(1 − Δ²/6) ]
>                           =  1 + 4Υ_loc^w Δ + O(Δ²)        (general convex 𝒱_w),   (7.32)
> ```
> and in the **isotropic** case `σ_w ≡ σ₀` the value is *exact*:
> ```
> max_u σ_w(u)/σ_{𝒫_m}(u)  =  sec(π/m)  =  1 + π²/(2m²) + O(m⁻⁴) .                   (7.33)
> ```
>
> **(d)** Consequently `‖T_h^{(m)} − T_w‖_∞ ↛ 0`: on the isotropic instance `c_eff ≡ 0`,
> `σ_w ≡ σ₀`, obstacle-free, with `y_A` at the origin and `y` in a mid-ray direction,
> ```
> T^{(m)}(y) − T_w(y)  =  ( sec(π/m) − 1 )·|y|/σ₀  =  ( sec(π/m) − 1 )·T_w(y) ,      (7.34)
> ```
> **a floor proportional to voyage time that no grid refinement removes.**

**Proof.**

*(a)* The bracket of (7.28) has the structure of (7.5) with `ζ` frozen; (7.12) applies with
`ℓ = ℓ_i`, and stability is (7.15) with the same connectivity argument (the `m`-ray graph is
connected because it contains the four axis directions). ∎(a)

*(b)* Repeat Step 3a of `Thm 7.1` with `ι ≡ 0` (there is no interpolation: the scheme reads grid
values directly) and `ℓ = ℓ_i = Θ(h)`. Each bracket equals `⟨∇ψ(y),u_i⟩ − F_w(y,u_i) + O(h)`.
Taking the max over the finite set,

```
S_h^{(m)}(y,ψ(y)+κ,ψ+κ)  =  max_{1≤i≤m} [ ⟨∇ψ(y),u_i⟩ − F_w(y,u_i) ]  +  O(h) .
```

Now apply the polar identity of `Thm 7.1` Step 3c over the *finite* set. For any `p`,

```
max_i [ ⟨p,u_i⟩ − F_w(u_i) ] = 0
  ⟺  ⟨p,u_i⟩ ≤ 1/σ_w(u_i)  ∀i,  with equality for some i
  ⟺  σ_w(u_i)⟨u_i,p⟩ ≤ 1    ∀i,  with equality for some i
  ⟺  max_i ⟨ σ_w(u_i)u_i , p ⟩ = 1
  ⟺  𝔥_{𝒫_m}(p) = 1 ,
```

the last step because the support function of the convex hull of finitely many points is the
maximum of `⟨·,p⟩` over those points. So the limit is (7.7) with `𝒱_w` replaced by `𝒫_m`. Since
each `σ_w(u_i)u_i ∈ 𝒱_w` and `𝒱_w` is convex by (S4), `𝒫_m ⊆ 𝒱_w`, hence `𝔥_{𝒫_m} ≤ 𝔥_w` and
`E_m ≥ 0`. `E_m` contains no `h`. Consistency with (7.7) would require `E_m ≡ 0`, i.e.
`𝔥_{𝒫_m} = 𝔥_w`, i.e. `𝒱_w = 𝒫_m` (two compact convex sets with equal support functions
coincide), which fails whenever `∂𝒱_w` is not a polygon with vertices exactly on the `m` rays. In
the Randers case `∂𝒱_w` is a circle, so it always fails. ∎(b)

*(c) — the chord formula.* Let `a_i = σ_iu_i`, `a_{i+1} = σ_{i+1}u_{i+1}`, and let the ray along
`u` meet the segment `[a_i, a_{i+1}]` at radius `s`. Equating the area of triangle
`O a_i a_{i+1}` computed whole and split by the ray,

```
½ σ_i σ_{i+1} sin Δ  =  ½ σ_i s sin α  +  ½ s σ_{i+1} sin β ,
```

which rearranges to (7.31). Because `𝒫_m` is the convex hull and `u` lies in the cone spanned by
`u_i, u_{i+1}`, the segment `[a_i,a_{i+1}]` is the boundary of `𝒫_m` in that cone, so
`σ_{𝒫_m}(u) = s`. Isotropic check: `σ_i = σ_{i+1} = σ₀`, `α = β = Δ/2` gives
`s = σ₀ sinΔ/(2sin(Δ/2)) = σ₀cos(Δ/2) = σ₀cos(π/m)`, and the worst `u` is the bisector, giving
(7.33) exactly. For the general bound (7.32): by `Lemma 7.5` applied to `F_w = 1/σ_w` and using
`|u − u_i| ≤ α` (chord ≤ arc),

```
1/σ_i   ≤  1/σ_w(u) + α/σ_min^w   ⟹   σ_i ≥ σ_w(u)(1 − Υ_loc^w α) ,
1/σ_w(u) ≤ 1/σ_i + α/σ_min^w      ⟹   σ_i ≤ σ_w(u)/(1 − Υ_loc^w α) ≤ σ_w(u)(1 + 2Υ_loc^w α) ,
```

the last step valid for `Υ_loc^w α ≤ ½` using `1/(1−z) ≤ 1+2z` on `z ∈ [0,½]`, and identically for
`σ_{i+1}` with `β`. Substituting into (7.31) with `sin α ≤ α`, `sin β ≤ β`, `α+β = Δ` and
`sin Δ ≥ Δ(1 − Δ²/6)`:

```
   σ_w(u)        σ_w(u)(σ_i sinα + σ_{i+1} sinβ)       σ_w(u)²(1+2Υ_loc^wΔ)Δ
──────────  =  ────────────────────────────────  ≤  ─────────────────────────────────
σ_{𝒫_m}(u)            σ_i σ_{i+1} sin Δ              σ_w(u)²(1−Υ_loc^wΔ)²Δ(1−Δ²/6)
```

which is (7.32); expanding to first order gives `1 + 4Υ_loc^wΔ + O(Δ²)`. ∎(c)

*(d)* On the stated instance `𝒱_w = B(0,σ₀)` everywhere; `T_w(y) = |y|/σ₀`; by (b) the `m`-ray
scheme converges to the viscosity solution for `𝒫_m` = the regular `m`-gon inscribed in
`B(0,σ₀)`, whose gauge is `F_{𝒫_m}(v) = |v|/σ_{𝒫_m}(v/|v|)`. Since that metric is spatially
constant the geodesic is a straight segment and `T^{(m)}(y) = |y|/σ_{𝒫_m}(y/|y|)` exactly; in a
bisector direction `σ_{𝒫_m} = σ₀cos(π/m)`, giving (7.34). ∎

### 7.3.1 The numbers, and the coupling to stencil geometry

On a square lattice the `m` available directions are the **primitive** integer offsets (`gcd = 1`;
non-primitive offsets reduce to shorter ones and add nothing). Their count inside radius `R` is
asymptotically `(6/π²)πR² = 1.9099 R²`. Enumerating by increasing norm:

| `m` | largest offset | `R_m = ℓ_max/h` | `sec(π/m) − 1` (isotropic floor) | bound (7.32) at `Υ_loc^w = 2.566` |
|---|---|---|---|---|
| 4 | (1,0) | 1.000 | 41.4 % | void |
| 8 | (1,1) | 1.414 | 8.24 % | void |
| **16** | (2,1) | 2.236 | **1.96 %** | void — use (7.31) pointwise |
| 24 | (3,1) | 3.162 | 0.863 % | 175 % |
| 32 | (3,2) | 3.606 | 0.484 % | 105 % |
| 48 | (4,3) | 5.000 | 0.215 % | 60 % |
| 72 | (5,3) | 5.831 | 0.0953 % | 38 % |

("Void" means `Υ_loc^wΔ > ½` so the hypothesis of (7.32) fails; the exact formula (7.31) still
applies and should be evaluated pointwise from the `n_θ` table.)

Two readings, both necessary:

1. **The isotropic column is the optimistic case and it already convicts `m = 16`.** A 1.96 %
   systematic *over*-estimate of voyage time, present at every grid resolution, is 2.75 h on the
   139.9963 h passage of `CORE-THEOREM` §8.2 — larger than the total saving most weather-routing
   systems claim. It is a **bias**, not noise: always in the same direction (`T^{(m)} ≥ T_w`), so
   it does not average out over a fleet, and it is invisible in a grid-refinement study because it
   does not shrink with `h`.
2. **The general bound (7.32) is first-order in `Δ`, not second.** In a strongly anisotropic cell
   the inscribed polygon is much worse than `sec(π/m)`, because the `σ_i` themselves vary between
   rays. (7.32) is provable but pessimistic; the truth for a given field is (7.31), which is exact
   and cheap to evaluate from the `n_θ` table — **an implementation should compute
   `max_u σ_w/σ_{𝒫_m}` cell by cell and report it**, which converts this from an argument into a
   measurement.

> **Cor 7.8 (a lattice stencil can regain consistency, but only by letting `m` grow with `h`, and
> at a cost per node that grows too).** Let `m = m(h) → ∞` with the lattice construction above,
> so `ℓ_max = R_m h` with `R_m = (m/1.9099)^{1/2}`. Sample the metric at the edge midpoint. Then
> the truncation error per unit length is
> ```
> E(m,h)  =  A/m²  +  C₂·‖D²F_w‖·(R_m h)²  =  A/m²  +  C₂'·‖D²F_w‖·m h² ,
> A = π²/2 (isotropic),   C₂' = 1/(1.9099·24) = 0.0218 ,                             (7.35)
> ```
> the first term from (7.33), the second the midpoint-quadrature error `(L³/24)max|d²F_w/ds²|` on
> a segment of length `L = R_mh`, divided by `L` to express it per unit length. Balancing,
> ```
> m*(h)  =  ( 2A/(C₂'‖D²F_w‖h²) )^{1/4}  =  Θ(h^{-1/2}) ,      E(m*,h) = Θ(h) .      (7.36)
> ```
> So an `m`-neighbour lattice scheme attains first-order accuracy **only** with `m ∝ h^{-1/2}`
> neighbours per node — `Θ(h^{-1/2})` work and memory per node, and stencil arms of physical
> length `Θ(h^{1/2})`, i.e. arms that get *longer relative to the mesh* as the mesh refines. The
> `ζ`-continuum update (7.5) attains the same `O(h)` with `Θ(C_AF Υ_loc)` work per node,
> **independent of `h`**.

**Proof.** Both terms of (7.35) are established: the first is `Prop 7.2`(c)–(d) (an error in the
*limit equation*, hence present at every `h`); the second is the midpoint rule. Differentiating,
`−2A/m³ + C₂'‖D²F_w‖h² = 0` gives (7.36). Substituting `m* = c·h^{-1/2}` back:
`A/m*² = (A/c²)h` and `C₂'‖D²F_w‖h²m* = C₂'‖D²F_w‖c·h^{3/2}`, so the first term dominates and
`E = Θ(h)`. ∎

**Remark (honest prior art).** That a fixed lattice stencil cannot represent anisotropic
characteristics is **Sethian & Vladimirsky's (2003)** motivation for ordered upwind methods, and
the `sec(π/m)` metrication constant is folklore in digital geometry. What `Prop 7.2` adds is
(i) the identification of the limit equation as the eikonal for the **inscribed polygon** `𝒫_m`,
which makes the defect an exactly computable quantity (7.31) rather than a qualitative warning,
and (ii) `Cor 7.8`'s `m ∝ h^{-1/2}` scaling. **Mirebeau (2014)** closes part of this gap from the
lattice side: anisotropy-adapted stencils built by lattice reduction achieve `O(Υ)` offsets per
node with a provable consistency guarantee, at the price of a stencil that must be rebuilt
whenever the metric changes. **In the ground frame that is once per forecast slice per cell; in
the co-moving frame it is once, ever** — which is a further, unclaimed benefit of the reduction
and makes Mirebeau's construction a legitimate alternative to (7.5) here. It should be cited as
such.

### 7.3.2 Empirical confirmation: the fixed-stencil floor was measured, and it does not converge

`Prop 7.2` predicts a metrication error that is bounded away from zero uniformly in `h`. That
prediction was **tested, accidentally, and confirmed**.

`CORE-THEOREM` §4 reports solving the same problem independently in the ground frame and in the
co-moving frame on the same **16-neighbour** grid, at seven resolutions, and comparing the two
arrival times:

| `h` [km] | 24 | 16 | 12 | 8 | 6 | 4 | 3 |
|---|---|---|---|---|---|---|---|
| discrepancy [%] | 0.36 | 0.15 | 0.79 | 0.92 | 0.17 | 0.98 | 0.58 |

**What this proves, rigorously.** Both frames solve problems with the *same* exact answer, by
Theorem C.1(a) (verified to `9.77×10⁻¹⁴ m/s` per-leg residual in the same section). Write `e_g(h)`
and `e_c(h)` for the two schemes' errors against that common exact answer. The measured quantity
is `|e_g(h) − e_c(h)|`. If both schemes were convergent, `e_g, e_c → 0` and hence the measured
difference would tend to 0. It does not. **Therefore at least one of the two 16-neighbour schemes
is not convergent.** `Prop 7.2` says both are not, and predicts the size: the isotropic floor
`sec(π/16) − 1 = 1.96 %`, with the observed 0.15–0.98 % being the *difference* of two same-signed
biases that partially cancel (the two frames quantise heading differently, because their optimal
headings differ by the drift shift, but the two biases are not independent).

**Quantifying "no convergence trend."** Ordinary least squares of `ln(discrepancy)` on `ln h` over
the seven points gives

```
slope  =  −0.382 ,     r = −0.365 ,     R² = 0.133 ,
t = r√(5/(1−r²)) = −0.875  on 5 d.f.  ⟹  two-sided p = 0.42 .                       (7.37)
```

The null hypothesis of **no dependence on `h` cannot be rejected** at any conventional level; `h`
explains 13 % of the variance in an 8× refinement range. For contrast, a first-order scheme
anchored at the `h = 24 km` value would predict `0.36 % × 3/24 = 0.045 %` at `h = 3 km`; the
observed value is `0.58 %`, **13× larger**. The observed spread (max/min = 6.5×) is comparable to
the refinement ratio (8×) but uncorrelated with it — the signature of a resolution-independent
bias plus sampling noise from which node happens to land nearest the target, exactly what (7.34)
and `R2` together predict.

> **This is empirical confirmation of the inconsistency of fixed stencils, from inside our own
> build, obtained while trying to measure something else.** It also means the two-grid comparison
> is the *wrong instrument* for Theorem C.1 — which is why the bijection test (residual
> `9.77×10⁻¹⁴ m/s`, `CORE-THEOREM` §4) is the one that settles it, and why the end-to-end
> agreement of **0.860 %** in §8.2 is reported as *inside the metrication floor* rather than as a
> validation of either solver's absolute accuracy.
>
> **And it means the shipped reference implementation does not satisfy `Thm 7.1`.**
> `comoving.stationary_sweep` uses a fixed 16-neighbour stencil, so it satisfies `Prop 7.2`, not
> `Thm 7.1`. Upgrading the update to the continuum semi-Lagrangian form (7.5) is an accuracy
> improvement **orthogonal to the reduction** and is the next increment. Every measured number in
> `CORE-THEOREM` should be read with a ~1 % floor attached.

---

## 7.4 Convergence rate: provable, observed, conjectural

Three columns, kept strictly separate.

### 7.4.1 What is provable

**(P-a) Truncation error `O(h)`, proved here.** Estimate (7.20) is a complete proof that the
consistency residual of scheme (7.5) is `O(h)` with the explicit constant

```
C_trunc  =  [ Υ/2  +  c₁²/(8c_geo) ]·‖D²ψ‖_∞   +   h·(Υ³/(6c_geo))·‖D³ψ‖_∞ ,        (7.38)
```

i.e. `[Υ/2 + 0.354]‖D²ψ‖ + h·0.236Υ³‖D³ψ‖`. Note the `Υ³` in the third-derivative term: **the
constant degrades cubically in anisotropy**, so by (7.3) the reduction's quiet-cell anisotropy
penalty (`Υ_loc^w = 2.57` where `Υ_loc = 1`) costs a factor `≈17` in that term. It is the
subdominant term, but for a coarse grid in a strongly-sheared field it need not be.

**(P-b) Solution error `O(√h)` in general, by citation with hypotheses verified.** The standard
route from an `O(h)` consistency residual to a sup-norm error bound for a monotone scheme is the
doubling-of-variables technique of **Crandall & Lions (1984)**, adapted to stationary problems by
**Capuzzo-Dolcetta & Ishii (1984)** and to semi-Lagrangian schemes by **Falcone (1987)**. It
yields `‖T_h − T_w‖_∞ = O(h^{1/2})` under exactly (C1)–(C4) of §7.2.4 plus monotonicity and
stability, all of which are established above. We do not reproduce that proof; we assert only that
its hypotheses hold here and that it is what is available.

**(P-c) `O(h)` for the minimum-time problem under small-time controllability.** **Bardi & Falcone
(1990)** prove a first-order rate for semi-Lagrangian approximation of the minimum-time function
under small-time local controllability. `Lemma 7.4` establishes exactly that hypothesis with an
explicit constant: `B(0,σ_min^w) ⊆ conv 𝒱_w(y)` uniformly, so the reachable set from any `y` in
time `τ` contains `B(y, σ_min^w τ)` for small `τ`, which is small-time local controllability at
rate `σ_min^w`. **Under (A2) this hypothesis is verified, not assumed.** What we do not verify is
their regularity hypothesis at the cut locus, which is where `T_w` fails to be semiconcave.

**(P-d) The temporal error is exactly zero, not merely small.** This is the only rate statement in
this file that is `O(1)`-free, and it is a consequence of Theorem C.1(b), not of a discretisation
choice. There is no time step, no temporal interpolation, and no `O(Δt)` or `O(Δt²)` term in the
budget of §7.4.4, because the co-moving metric is not sampled in time at all. **Measured**
(`CORE-THEOREM` §4): the ground-frame solve required `V_req = 7.006721 m/s` against a ship
capability of `7.0` — an excess of `6.7×10⁻³ m/s` arising purely from sampling the advected field
at the leg midpoint, which is first-order accurate in *time* as well as space. The co-moving
solve's excess was `2.8×10⁻¹⁴ m/s`. That is a factor of `2.4×10¹¹`, i.e. the difference between a
first-order term and machine epsilon. **The co-moving solve is not merely faster and better
licensed; it is more accurate on the same grid.**

**(P-e) The interception error is `O(h)` with an amplification factor.** `P4` selects a grid node,
so the recovered ground landfall carries the node-snapping error amplified by `|w|` (`R2`):

```
miss  ≤  h·( 1 + |w|/σ_min^w )        [snapping in y, plus |w|·(timing error h/σ_min^w)]  (7.39)
```

For `CORE-THEOREM` §8.2 (`h = 0.25° ≈ 27.8 km`, `|w| = 3.162`, `σ_min^w = 7.2 − 3.162 = 4.038`):
`27.8 × (1 + 0.783) = 49.6 km`. **Measured: 11.2 km** — consistent with, and comfortably inside,
the bound, because `P4` minimises the ground miss over all `N` nodes rather than snapping to the
nearest. Converted to time at the achieved mean speed `3698 km / 139.9963 h = 7.34 m/s`, 11.2 km
is `1526 s = 0.42 h = 0.30 %` of the voyage — i.e. **the landfall miss accounts for roughly a
third of the 0.860 % ground/co-moving disagreement, and the 1.96 % metrication floor covers the
rest.** The two independent error sources add up to the observed discrepancy without any residual
that needs explaining. That is the strongest internal-consistency check available on these
numbers.

### 7.4.2 What is observed

| Quantity | Value | Source |
|---|---|---|
| Observed convergence order of the **shipped 16-neighbour** solver | **0** (a floor) | (7.37), `p = 0.42` for any trend |
| Fixed-stencil error floor, predicted | 1.96 % | (7.33), `m = 16` |
| Fixed-stencil error floor, observed (as a two-frame difference) | 0.15–0.98 % | `CORE-THEOREM` §4 |
| End-to-end ground vs co-moving agreement | 0.860 % | `CORE-THEOREM` §8.2 |
| Temporal sampling error, ground frame | `6.7×10⁻³ m/s` excess `V_req` | `CORE-THEOREM` §4 |
| Temporal sampling error, co-moving frame | `2.8×10⁻¹⁴ m/s` | `CORE-THEOREM` §4 |
| Bijection residual (Thm C.1(a), the substantive claim) | `9.77×10⁻¹⁴ m/s` | `CORE-THEOREM` §4 |
| Landfall miss | 11.2 km on 3698 km | `CORE-THEOREM` §8.1 `R1` |

**Observed convergence order of the continuum-update solver: NOT MEASURED.** The refinement study
that would produce it is `handbook` G5 row 3 (arrival-time error vs the G4 exact solution at
1.0°/0.5°/0.25°/0.125°) run against the continuum update, and it has not been run. Until it is,
this file makes **no** claim about the practical convergence order of KAIROS's specified scheme.
Anyone reporting one from the numbers above is reporting the 16-neighbour prototype's order, which
is zero.

### 7.4.3 What is conjectural

> **Conjecture 7.9 (first-order convergence away from the cut locus).** Under (A1)–(A2),
> (S1)–(S6), and if `T_w` is semiconcave with a linear modulus on every compact subset of
> `Ω_w \ (Cut(y_A) ∪ {y_A})`, then `‖T_h − T_w‖_{L^∞(K)} = O(h)` on each such compact `K`, and
> `‖T_h − T_w‖_{L^∞(Ω_w)} = O(h·log(1/h))` globally.
>
> **Exactly what is missing.** (i) A semiconcavity estimate for `T_w` **uniform in `h`** and
> valid up to the boundary of the seeding disc of `Remark 7.2.3`. Semiconcavity of the minimum-time
> function is classical under small-time controllability *away from the cut locus* (Cannarsa &
> Sinestrari 2004), and `Lemma 7.4` supplies the controllability — but the seakeeping ban set makes
> `𝒱_w` only Lipschitz, not `C^{1,1}`, in `y`, and we have not checked whether the semiconcavity
> constant survives that. (ii) A bound on the measure of the `h`-neighbourhood of the cut locus,
> which is what would turn the local `O(h)` into the global `O(h log(1/h))`. For a generic Finsler
> metric the cut locus is a 1-rectifiable set and the neighbourhood has measure `O(h)`, but
> "generic" is not a hypothesis we can assert about an operational forecast. Neither gap is
> believed hard; both are real.

> **Conjecture 7.10 (the joint `ε`-Pareto limit).** For `k ≥ 2` with the value-bucketed labels of
> `ERRATA` (E7.1), the discrete Pareto front converges in Hausdorff distance to the continuum
> Pareto front as `(h, ε) → 0`, at rate `O(h) + O(ε)`.
>
> **Exactly what is missing.** `Thm 5.2` gives the `(1+ε)` guarantee **at fixed `h`**, and
> `Thm 7.1` gives convergence **at fixed `k = 1`**. Interchanging the two limits requires knowing
> that the `ε`-pruning does not discard a label that would have become non-dominated after
> refinement — i.e. an equicontinuity statement for the label sets in `h`, which we do not have.
> The practical consequence is bounded and reportable: `Cor 4.12`'s a posteriori certificate is
> computed on the returned route and does not depend on this conjecture, which is precisely why
> `ERRATA` E6 makes the certificate the *primary* guarantee.

### 7.4.4 The error budget, assembled

For the configuration of `CORE-THEOREM` §8.2 (`h = 0.25°`, `V_s = 7.2`, `w = (3,1)`, 139.9963 h):

| Source | Scaling | Value here | Removable by |
|---|---|---|---|
| Metrication, fixed `m = 16` stencil | `Θ(m⁻²)`, **`h`-independent** | 1.96 % | the `ζ`-continuum (7.5) — sets it to 0 |
| Metrication, continuum stencil | 0 | 0 | — |
| Truncation, continuum stencil | `O(h)` with (7.38) | not measured | refinement |
| Support tabulation, `n_θ = 72` | `O(n_θ⁻²)` | 0.075 % (7.27) | raising `n_θ`, cost linear |
| **Temporal sampling** | ground: `O(Δt)`; **co-moving: exactly 0** | `6.7e-3 m/s` → `2.8e-14 m/s` | **the reduction** |
| Interception / landfall | `O(h(1+\|w\|/σ_min^w))` | ≤ 49.6 km bound; 11.2 km measured = 0.30 % | refinement; sub-cell interpolation of `T_w` |
| Convexification `D4` | `Thm 2.11` **local form E6.3** | < 2 s per 6 h leg | notch projection + certificate |
| Model error in `R` when (A1) fails | `Lemma 7.6` applied to `d_H` | regime-dependent | the `P6` corrector |

**Which dominates:** for the shipped prototype, metrication, by an order of magnitude over
everything else. For the specified scheme, the interception/landfall term at `h = 0.25°`, then
truncation. The temporal term, which dominates *every* published time-dependent router's budget,
is identically absent.

---

## 7.5 `Thm 7.3` — total complexity, derived term by term

### 7.5.1 Abstract data types

`D7` requires abstract types with operations and complexities. Five are used.

| Type | Operations | Complexity | Realisation |
|---|---|---|---|
| **SupportTable** | `probe(node, p) → 𝔥_w` | `O(log n_θ)` = `c_probe` | flat `N_w × n_θ` array of `f32`, angle-sorted; binary search + linear interpolation (`D2`, `Prop 2.7`) |
| **MonotoneQueue** | `insert(key,id)`, `extract_min()`, `decrease_key` | `O(1)` amortised | Dial (1969) bucket ring, width `Δ_min` (7.14), depth `Prop 7.10`; heap fallback when `Υ_loc > Υ_heap = 12` (`ERRATA` E2) |
| **AcceptedFront** | `edges_within(node, r) → list` | `O(C_AF·r/h)` output-sensitive | doubly-linked list of front edges per grid stripe; **must be maintained explicitly** — see §7.1.1 |
| **LabelSet** | `insert(label)`, `prune_ε`, `iterate` | `O(Λ)` insert with bucket-key dedup | per-node array of `Λ` records; value-bucketed keys (`ERRATA` E7.1); Martins (1984) label-setting discipline, Tsaggouris–Zaroliagis (2009) bucketing |
| **CoarseGrid** | `lower_bound(node) → f64` | `O(1)` | `N_w/ρ_c²` array from `P2`; dilated-cell minima by running-min filter (below) |

> **Prop 7.10 (bucket-ring depth).** With `Δ_min = c_geo h F_min^w` (7.14) and maximum key
> increment `r_max·F_max^w`, the Dial ring depth of `ERRATA` (E2.2) is
> ```
> n_buckets  =  ⌈ r_max F_max^w / Δ_min ⌉  =  ⌈ (Υh/σ_min^w)/(c_geo h/σ_max^w) ⌉
>            =  ⌈ Υ² / c_geo ⌉  =  ⌈ √2 · Υ² ⌉ .                                     (7.40)
> ```
> **Proof.** `r_max = Υh` (`Prop 4.7`), `F_max^w = 1/σ_min^w`, `F_min^w = 1/σ_max^w`, and
> `Υ = σ_max^w/σ_min^w`; substitute and use `1/c_geo = √2`. ∎
>
> **Numbers.** At the measured `Υ_loc^w = 2.566`: `n_buckets = ⌈9.31⌉ = 10`. At the normative
> fallback threshold `Υ_heap = 12`: `n_buckets = ⌈203.6⌉ = 204`. The ring is therefore a few
> hundred pointers — **1.6 kB** — and its memory is never a consideration. `ERRATA` E2 is right
> that the failure mode is unbounded *bucket count*, not vanishing `F_min`: `F_min = 1/(V_max+|c|)`
> is bounded below by construction and shrinks only by a third across the entire realistic drift
> range, whereas (7.40) is quadratic in `Υ` and does diverge as `|c_eff| → V_max`.

**A deflationary note on `D3`, in the interest of honesty.** The bucket queue removes a `log N`
factor from the queue term only. That term is `Θ(N_w Λ)` operations at `≈ 20` mops each with
buckets versus `≈ log₂(N_w)·10 ≈ 170` mops each with a heap: a difference of `150·N_w Λ` mops. At
`N_w = 136 456`, `Λ = 1`, that is `2.0×10⁷` mops against a total of `≈ 4×10⁹` (§7.5.4) — **0.5 %**.
`Prop 4.9` is correct and worth stating, but the reason to prefer the bucket queue is determinism
and memory locality, not asymptotics. Anyone claiming the bucket queue as a headline speed-up is
overselling it by two orders of magnitude.

**Dilated-cell minima in `O(1)` per output (`D5`).** `Prop 4.11` requires
`F_low(C,u) = min over the closed cell C dilated by the coarse spacing H` — the dilation is what
makes the heuristic admissible across cell boundaries, and the naive "min over the bare cell" is
inadmissible (`handbook` S4, cause 2: A\* with an inadmissible heuristic returns suboptimal
answers quietly). Computed naively this costs `(ρ_c + 2)²` fine probes per coarse cell per
direction, i.e. `N_w n_θ (1 + 2/ρ_c)² = 1.56 N_w n_θ` probes at `ρ_c = 8` — **more** than building
the fine table. Computed as a separable 1-D running minimum over a sliding window (van Herk 1992;
Gil & Werman 1993) it costs 3 comparisons per element per axis, i.e. `6 N_w n_θ` mops **totally
independent of `ρ_c`**. Use the running-min filter.

### 7.5.2 The theorem

> ### **Thm 7.3 (total complexity).**
> Under (A1)–(A2), (S1)–(S6), the total work of `P0`–`P8` is
> ```
> W_total  =  W_w + W_tab + W_coarse + W_sweep + W_int + W_rec + W_corr + W_rep       (7.41)
> ```
> with, writing `N_w` for the **dilated** node count (`Cor 7.13`), `n_ζ` for the inner
> minimisation's evaluation count, and using the ADTs above:
> ```
> W_w      =  Θ( R·n_w² · N_s · n_t · n_u · c_σ )                        — O(1) in N_w   (7.42)
> W_tab    =  Θ( N_w · n_θ · c_σ )                       ← ONE frame, by Thm C.1(b)      (7.43)
> W_coarse =  Θ( N_w n_θ )  +  Θ( (N_w/ρ_c²)·Λ_c·C_AF·Υ₁·n_ζ·c_probe )                   (7.44)
> W_sweep  =  Θ( N_w · Λ · C_AF · Υ₁ · n_ζ · c_probe )  +  Θ( N_w Λ )                    (7.45)
> W_int    =  Θ( N_w · c_hav )                           ← one haversine per node        (7.46)
> W_rec    =  Θ( P ) ,     P = O(S/h)  the route's node count                            (7.47)
> W_corr   =  Θ( |K| · Λ · C_AF · Υ₁ · n_ζ · c_probe · n_pass )    [only if R ≠ 0]       (7.48)
> W_rep    =  Θ( |K_R| · Λ · C_AF · Υ₁ · n_ζ · c_probe )                                 (7.49)
> ```
> **Worst case:** `Υ₁ → Υ_heap = 12` (beyond which the heap fallback fires and (7.45)'s second
> term becomes `Θ(N_w Λ log N_w)`), `C_AF → 4` at a cut locus or in an archipelago, and
> `Λ ≤ ∏_{i=2}^{k}(⌈log(C_i^max/C_i^min)/log(1+ε)⌉ + 1)` by `ERRATA` (E7.2) — for `k = 3`,
> `ε = 0.02` and two decades of range, `Λ ≤ 234² ≈ 5.5×10⁴`.
> **Realistic case:** `Υ₁ ≈ 2.6` (7.3), `C_AF ≈ 2`, `Λ ≈ 10–40` after dominance pruning,
> `n_ζ = 15`, giving `W_sweep = Θ(N_w Λ)` with a constant of `≈ 3.0×10³` mops per node per label.
> **The dominant term is `W_tab`, not `W_sweep`** — see (7.51).

**Proof, term by term.**

**(7.42), `P0` — choosing `w`.** Eq (C.10) minimises `P₉₉` over the domain of `max_u |∂F_w/∂t|`
by coarse-to-fine search over a 2-D grid: `R` rounds of `n_w × n_w` candidates. Each candidate
evaluation samples `N_s` cells × `n_t` times × `n_u` headings, with a central difference in `t`
costing 2 metric evaluations each. So the count is `R·n_w²·N_s·n_t·n_u·2·c_σ` plus one `O(N_s)`
percentile (linear-time selection). **`N_s` is a coarse sample set, not the fine grid: `W_w` is
`O(1)` in `N_w`.** Normative parameters: `R = 3`, `n_w = 9` (`CORE-THEOREM` §7: "three rounds of
9×9 is ample") → 243 candidate evaluations. *(The reference implementation defaults to `n = 7`,
`rounds = 3` → 147; the spec value is normative, the code value is a default, and neither is a
conflict.)* **Measured: 0.05 s**, 1.5 % of the 3.38 s solve. Reconciling: 0.05 s at `2×10⁹` mops/s
is `10⁸` mops; divided by 147 candidates, `2 × 24` headings and `c_σ^R = 22` mops, that is
`≈ 6.4×10²` (cell, time) samples per candidate — e.g. a `12×12` cell grid at 4 times, vectorised.
*(This decomposition is a reconstruction consistent with the reported figure, not a reading from
the run log.)* **What matters for `Thm 7.3` is only that `W_w` is a fixed constant number of field
evaluations, independent of `N_w`, and empirically 1.5 % of the solve.**

Two honest notes on `P0`. First, phase correlation — the obvious choice — was tried and **failed**:
against a true dominant `w = (2.0, 0.5)` it returned `(−0.74, 0.00)`, because it locks onto
whichever feature carries the most gradient energy, which need not be the one governing the
causality constant. Second, the `w` that (C.10) returns is **not** a meteorological advection
estimate and must not be reported as one: in regimes B and C of Test 8.10 the optimised `w` was
`(−0.56, −1.38)` against a true `(+2.0, +0.5)`. Once (A1) is violated, minimising the residual
causality constant and estimating the storm track are different problems, and it is the former the
algorithm needs.

**(7.43), `P1` — the metric table, and where the reduction actually pays.** `D2` tabulates
`𝔥_w(y, p_j)` for `n_θ` directions at every node. In the co-moving frame the field is stationary
(Theorem C.1(b)), so the table is **one frame deep**. In the ground frame the same table must
carry `n_fc` forecast frames, or be evaluated lazily at the departure time of every edge. Hence

```
W_tab^{co-moving}  =  N_w · n_θ · c_σ ,        W_tab^{ground}  =  N · n_fc · n_θ · c_σ .  (7.50)
```

At `N = 112 681` (basin grid, §7.6), `N_w = 136 456`, `n_θ = 72`, `n_fc = 41` (5 days, 3-hourly),
`c_σ^phys = 400` mops:

```
W_tab^{co-moving}  =  136 456 × 72 × 400  =  3.93×10⁹ mops  =  1.96 s
W_tab^{ground}     =  112 681 × 72 × 400 × 41  =  1.33×10¹¹ mops  =  66.5 s              (7.51)
```

a **34×** reduction after paying the 21 % dilation penalty. Compare `W_sweep` at the same size
(below): `4.1×10⁸` mops. **The metric table build dominates the sweep by roughly 10×**, which is
the single most useful fact in this section for an implementer: optimise the table, not the queue.
(`c_σ^phys` is the unverified estimate; the *ratio* `W_tab^{ground}/W_tab^{co-moving} = n_fc·N/N_w`
does not depend on it and is exact.)

**(7.44), `P2` — the coarse solve and the certificate.** The dilated-cell minima cost `6 N_w n_θ`
mops by the running-min filter (above). The coarse sweep itself is (7.45) on `N_w/ρ_c² = N_w/64`
nodes with `Λ_c = 1` (the heuristic is time-only), i.e. **1.6 %** of the fine sweep. `Cor 4.12`'s
certificate is then one comparison per returned route: `O(P)`. `P2` is never a dominant term, and
after `ERRATA` E6 it carries the *primary* optimality guarantee, so it is never optional either.
**`P2` also has a second job specific to the reduction**: it supplies the upper bound on `t_max`
that sizes the dilation (`Cor 7.13`). It must therefore run on a pessimistic metric (max over the
dilated cell) to give an *upper* bound, in addition to the optimistic pass that gives the lower
bound, and the two passes must precede fine-grid allocation. This is an ordering constraint on the
pipeline that does not exist in the ground frame.

**(7.45), `P3` — the stationary sweep.** Each of the `N_w` nodes is finalised once (label-setting,
justified by the acyclicity argument of §7.2.2 Part 2 with `Δ_min > 0`). At finalisation the node
relaxes its outward neighbourhood; equivalently each node is *updated* from the accepted front
`|NF(y)| = Θ(C_AF·r(y)/h) = Θ(C_AF·Υ_loc^w(y))` times by (S5). Each front edge requires one
minimisation over `ζ ∈ Z_e(y)`, which by (S4) is unimodal (the composition of a convex gauge with
an affine map, plus an affine interpolant) and is therefore solved by golden-section search in

```
n_ζ  =  ⌈ ln(1/tol_ζ) / ln(1/0.618) ⌉  =  ⌈ ln(10³)/0.4812 ⌉  =  15   evaluations
```

for a relative tolerance `tol_ζ = 10⁻³` on `ζ`. Each evaluation costs: `ξ_e(ζ)` and `W̃_e(ζ)` by
lerp (6 mops), `ℓ` by `sqrt` (6+3), `u` by two divisions (8), one `SupportTable.probe`
(`c_probe = 15`), and the combine (3) — **38 mops**. So per front edge `15 × 38 + 20 = 590` mops,
and per node

```
c_node  =  C_AF · Υ₁ · 590  +  20   =   2 × 2.566 × 590 + 20  =  3 049 mops .         (7.52)
```

Summing over nodes gives the first term of (7.45), `Λ` copies for `k ≥ 2`. The second term is the
queue: `Θ(1)` amortised per insert/extract by `Prop 4.9` with the width `Δ_min` and depth (7.40),
degrading to `Θ(log N_w)` under the `Υ_heap` fallback of `ERRATA` E2. At `N_w = 136 456`, `Λ = 1`:
`W_sweep = 136 456 × 3 049 = 4.16×10⁸` mops `= 0.21 s`.

**(7.46), `P4` — interception.** By `R2`, the goal node is **not** selected by a root find on
`g(t) = T_w(x_B − wt) − t`. Sampling `T_w` at the nearest node makes `g` a **step function**, so a
bisection converges to a discontinuity rather than a root, and `T_w` at the returned node can be
far from `t*`; because the ground position is `y + w·T_w[y]`, that timing error is amplified by
`|w|`. **Measured: a 104.5 km miss, unchanged by widening the neighbourhood search, because the
offset is systematic rather than local.** Instead, solve the interception condition **directly on
the discretisation**: every node carries its own arrival time, hence its own ground landfall
`y + w·T_w[y]`; take the node minimising `‖(y + w·T_w[y]) − x_B‖`. This is Eq (C.4) evaluated
exactly on the grid, with no interpolation and no root find:

```
for each of the N_w nodes:  one metres→(Δlat,Δlon) conversion + one haversine  =  c_hav = 60 mops
```

so `W_int = 60 N_w` mops — at `N_w = 136 456`, `8.2×10⁶` mops `= 4.1 ms`, **0.2 % of `W_sweep`**.
It is a parallel min-reduction (§7.8). The bisection remains useful for *reporting* `t*` and would
be the right method in a continuum implementation; it costs `O(log(t_max/tol))` probes and is
negligible either way.

**(7.47), `P5` — route recovery.** Backtrack the parent chain and apply `x(s) = y(s) + w·τ(s)`,
Eq (C.5): `O(1)` per waypoint over `P = O(S/h)` waypoints, `S` the route length. At `S = 3698 km`
and `h = 27.8 km`, `P ≈ 133`. Negligible. Verified to `9.77×10⁻¹⁴ m/s` per-leg residual.

**(7.48), `P6` — the residual corrector.** Run only if `R` of Eq (C.8) is significant. One
corrector sweep in the ground frame, seeded by `P5`, over the dependency closure `K` of the cells
where `R` materially changes the metric, with the causality guard applied to `L_t^R` rather than
`L_t` and the wait relaxation (7.26) where it fails. Cost is (7.45) restricted to `K`, times
`n_pass` outer passes. **The measured licence improvement is what makes this affordable**: Test
8.10 gives `r·L_t` falling from 1.309 to 0.272 (regime B) and 1.307 to 0.261 (regime C), so the
corrector runs *licensed* where the ground-frame solve would not have been — which is the
difference between one pass and an unbounded label-correcting iteration. `|K|/N_w` must be
instrumented; `handbook` S9 gives the diagnostic (a closure near 1.0 means the closure computation
is degenerate).

**(7.49), `P7` — forecast repair.** Same structure with `K_R` the closure of the cells whose
forecast changed. Target `|K_R|/N_w < 0.2` for a 5 % perturbation (`handbook` S9). Note that in
the co-moving frame a forecast update generally changes `w` as well, and **a changed `w` changes
the grid dilation**, hence potentially the domain: an implementation must either re-check `R1` or
allocate the dilation for the worst `|w|` it will accept. This is a repair-path hazard that does
not exist in the ground frame and is worth an assertion.

Summing (7.42)–(7.49) gives (7.41). ∎

### 7.5.3 Which constants dominate

| Rank | Term | Constant | Why it dominates / when it stops |
|---|---|---|---|
| 1 | `W_tab` | `n_θ · c_σ^phys = 72 × 400 = 2.9×10⁴` mops/node | the naval-architecture stack is evaluated `n_θ` times per node. Reduce by lowering `n_θ` (pays `O(n_θ⁻²)` accuracy, (7.27)), by exploiting the Randers fast path where no ban is active (`c_σ^R = 22`, a **18×** saving), or by lazy evaluation with a cache. **The reduction already divided this by `n_fc = 41`.** |
| 2 | `W_sweep` | `C_AF·Υ₁·n_ζ·38 ≈ 3.0×10³` mops/node/label | `n_ζ = 15` and `C_AF·Υ₁ = 5.1` multiply. Reduce `n_ζ` by warm-starting `ζ` from the previous front edge (the minimiser moves continuously along the front); reduce `Υ₁` only by choosing a different `w`, which trades against the causality constant. |
| 3 | `Λ` | 10–40 realistic, `5.5×10⁴` worst case | multiplies `W_sweep` and dominates **memory** for `k ≥ 2` (§7.6). Must be hard-capped. |
| 4 | `W_int`, `W_coarse`, `W_w`, `W_rec` | — | together under 3 % |

**The interpreter is not in this model, and it is the largest constant in the measured numbers.**
For `CORE-THEOREM` §8.2 (`N = 29 529`, fixed 16-neighbour stencil, no `ζ` search), the model gives
`16 × c_σ + queue ≈ 16 × 400 + 20 = 6.4×10³` mops/node → `1.9×10⁸` mops → **0.095 s** of
arithmetic. Measured: **3.38 s**. The ratio, `≈ 36×`, is interpreter and allocation overhead in a
pure-array reference implementation with a binary heap of tuples. A compiled C++/Rust/Go/Julia
port should expect **1.5–2 orders of magnitude** below the published wall clocks, and should not
read the published wall clocks as algorithmic. *(The 36× is derived from the model; the `c_σ^phys`
input to it is the unverified estimate, so read it as "one to two orders of magnitude", not as
"36".)*

### 7.5.4 The measured end-to-end numbers, and what they do and do not decompose into

`CORE-THEOREM` §8.2. Voyage 8.0 N 77.0 E → 12.6 N 43.5 E, 3698 km great circle, `V_s = 7.2 m/s`,
cyclone translating at `w = (3.0, 1.0) m/s`, 0.25° grid, **29 529 nodes**.

| | arrival | wall clock | notes |
|---|---|---|---|
| Ground-frame time-dependent Dijkstra | 141.2107 h | **2.14 s** | conventional approach |
| Co-moving reduction | **139.9963 h** | **3.38 s** (+ **0.05 s** to choose `w`) | landfall miss 11.2 km |

Agreement **0.860 %**, inside the 1.96 % fixed-stencil floor. Causality constant on this field:
`L_t` `3.22×10⁻⁷ → 1.24×10⁻⁷` (2.60×); `r·L_t` at `r = 2h = 55 km`: `0.0177 → 0.0068`.

**The 1.58× wall-clock ratio has two candidate explanations and the published log does not
disambiguate them.** Stated plainly, because a complexity section that papers this over is worth
nothing:

- **Reading A — dilation.** `29 529 = 153 × 193`. The east–west dilation required by `R1` is
  `|w_e|·t_max = 3.0 × 503 987 s = 1 512 km`, which at 10 °N is `13.8°`, i.e. **55 columns** of a
  0.25° grid. The remaining 138 columns span 34.5°, against a voyage longitude span of 33.5° — a
  close fit. On this reading the co-moving grid carries **193/138 = 1.40×** the nodes of the ground
  grid, which accounts for most of the 1.58×, leaving `3.38/1.40 = 2.41 s` against `2.14 s`, i.e.
  **13 % per-node overhead**.
- **Reading B — one grid for both.** If the reported node count is a single grid used by both
  solves, the 1.58× is entirely per-node overhead and is **not explained** by the model above,
  which predicts the co-moving update to be *cheaper* per node (no temporal interpolation of the
  forecast stack, no `L_t` diagnostic).

Reading A is arithmetically consistent to within 5 % and Reading B is not consistent with the cost
model, which is evidence for A but not proof. *(The factorisation `153 × 193` and the column
accounting are a reconstruction from the reported node count, not a reading from the run log.)*
**Required instrumentation:** report `N_ground` and `N_comoving` separately, and report
`required_dilation_m` alongside them. Until that is done, the honest statement is: *the co-moving
solve cost 1.58× the ground solve on this problem, of which a factor of about 1.4 is attributable
to the grid dilation the reduction imposes.*

**What is unambiguous in these numbers:** `P0` costs 0.05 s, i.e. **1.5 %**, and is `O(1)` in `N`;
the co-moving answer is the *faster* of the two arrival times, consistent with it carrying no
temporal sampling error; and the disagreement is fully accounted for by the 1.96 % metrication
floor plus the 0.30 % landfall term (§7.4.1(P-e)) with nothing left over.

---

## 7.6 Memory

### 7.6.1 The footprint formula

```
M_total  =  M_metric + M_solve + M_labels + M_coarse + M_queue + M_field                (7.53)

M_metric  =  N_w · n_fc^eff · n_θ · b_θ                b_θ = 4 (f32)
M_solve   =  N_w · ( 8 [T, f64] + 4 [parent, i32] + 1 [status, u8] + 4 [bucket link, i32] )
          =  17 N_w                                    (structure-of-arrays; no padding)
M_labels  =  N_w · Λ · ( 4k [objective values, f32] + 4 [parent node] + 4 [parent label] )
M_coarse  =  (N_w/ρ_c²) · ( n_θ b_θ + 8 )
M_queue   =  n_buckets · 8   +   0                     links live in M_solve
M_field   =  N · n_fc · n_env · 4                      n_env = 8 (cu,cv,wu,wv,hs,tp,μ_w,depth)
```

with, **and this is the whole point**,

```
n_fc^eff  =  1        in the co-moving frame     (Theorem C.1(b))
n_fc^eff  =  n_fc     in the ground frame .                                             (7.54)
```

`b_θ = 4` bytes is justified: `f32` relative precision is `6×10⁻⁸`, four orders below the
`7.5×10⁻⁴` tabulation error of (7.27), so the storage format is not the limiting accuracy. `T`
stays `f64`: at `5×10⁵ s` an `f32` resolves `0.03 s`, adequate per value but not across `10³`
accumulated legs.

### 7.6.2 `Cor 7.13` — the co-moving dilation, and exactly what it costs

> **Cor 7.13 (dilation cost).** Let the ground domain be a `W × H` box (metres). By `R1` the
> co-moving grid must contain `Ω ⊖ {wt : t ∈ [0,t_max]}`, i.e. must be extended by `|w_e|·t_max`
> in the direction opposite `w_e` and `|w_n|·t_max` opposite `w_n` (one side each, not both).
> Hence
> ```
> N_w / N   =   ( 1 + |w_e| t_max / W ) · ( 1 + |w_n| t_max / H )                        (7.55)
> ```
> and every term of (7.53) except `M_field` scales by this factor.
>
> **Proof.** `y = x − wt`, so as `t` runs over `[0,t_max]` the co-moving image of the fixed ground
> box sweeps the Minkowski sum of the box with the segment `{−wt}`, whose bounding box has sides
> `W + |w_e|t_max` and `H + |w_n|t_max`. On a lat/lon grid the longitudinal extension must be
> converted at the **highest-latitude** row of the domain, `Δλ = |w_e|t_max/(R_E cos ϕ_max)`, or
> the extension is insufficient at the poleward edge. ∎

**This is a real memory penalty the reduction imposes and it must not be hidden.** It also fails
*silently* if under-provisioned: `S3` above and `handbook` S8b record the measured 104.5 km miss
that a full-grid scan could not reduce. The mitigations are: (i) obtain `t_max` from the
pessimistic coarse pass of `P2` **before** allocating the fine grid; (ii) assert
`required_dilation_m` against the actual grid bounds at start-up and refuse rather than proceed;
(iii) note that (7.55) is benign for basin-scale domains and severe for tight boxes — the penalty
is `|w|t_max` divided by the box dimension, so it is a *fixed distance*, not a fixed fraction.

### 7.6.3 Real numbers: Indian Ocean, 0.25° and 0.125°

**Domain:** 20 °E–120 °E, 40 °S–30 °N — a 100° × 70° box. **Horizon:** `t_max = 5 d = 432 000 s`.
**Advection:** `w = (3.0, 1.0) m/s` (the measured cyclone translation of `CORE-THEOREM` §8.2), so
`|w_e|t_max = 1 296 km` and `|w_n|t_max = 432 km`. At the poleward edge (40 °S) the longitudinal
extension is `1296/(111.32·cos 40°) = 15.20°`; the latitudinal extension is `3.88°`. `n_fc = 41`
(5 days, 3-hourly), `n_θ = 72`, `k = 3`, MB = 10⁶ B.

| | 0.25° | 0.125° |
|---|---|---|
| ground grid `N` | 401 × 281 = **112 681** | 801 × 561 = **449 361** |
| dilated grid `N_w` | 461 × 296 = **136 456** | 922 × 592 = **545 824** |
| **dilation penalty (7.55)** | **+21.1 %** | **+21.5 %** |
| `M_metric`, co-moving (`n_fc^eff = 1`, on `N_w`) | **39.3 MB** | **157.2 MB** |
| `M_metric`, ground (`n_fc^eff = 41`, on `N` — no dilation needed) | **1 331 MB** | **5 306 MB** |
| **net metric-table saving** | **41 / 1.211 = 33.9×** | **33.8×** |
| `M_solve` | 2.3 MB | 9.3 MB |
| `M_coarse` (`ρ_c = 8`) | 0.6 MB | 2.5 MB |
| `M_queue` (`Υ = 12` worst case) | 1.6 kB | 1.6 kB |
| `M_labels`, `k = 3`, `Λ = 40` (20 B/label) | **109 MB** | **437 MB** |
| `M_labels`, `k = 3`, `Λ = 5.5×10⁴` (E7.2 worst case) | **150 GB** | **600 GB** |
| `M_field` (forecast stack, `n_env = 8`) | 148 MB | 590 MB |
| **total, `k = 1`, corrector off** (`M_field` = one frame) | **46 MB** | **183 MB** |
| **total, `k = 3`, `Λ = 40`, corrector on** | **299 MB** | **1 196 MB** |

**Four readings, all load-bearing.**

1. **The metric table is the dominating term for `k = 1`, and the reduction divides it by `n_fc`.**
   `39.3 MB` fits in L3 on a laptop-class part; `1 611 MB` does not fit anywhere useful and its
   working set slides through the whole array as `t` advances. This is a bigger practical
   difference than the byte count suggests, and it is the reason §7.8 can replicate the table per
   NUMA node.
2. **For `k ≥ 2` the label store dominates, not the metric table**, and the `ERRATA` (E7.2) worst
   case is **vacuous as a memory budget** (150 GB). A hard cap `Λ_max` is mandatory; at
   `Λ_max = 64` the 0.25° label store is 175 MB. The cap is safe to impose because `Cor 4.12`'s a
   posteriori certificate reports the resulting gap on the returned route — the guarantee degrades
   *measurably* rather than silently. Observed `Λ` after dominance pruning is 10–40 (`ERRATA` E7),
   so the cap rarely binds.
3. **`M_field` does not go away.** The raw forecast stack is still needed by `P0` (choosing `w`, on
   a coarse sample) and by `P6` (the residual corrector). If the corrector is not run and `P0`
   samples coarsely, only the `t_ref` frame is needed: `112 681 × 8 × 4 = 3.6 MB`. If the corrector
   is run, the full 148 MB stays resident. **State which mode you are in when you quote a
   footprint.**
4. **The dilation costs ~21 % on a basin-scale box and ~40 % on a voyage-scale box** (§7.5.4,
   Reading A). It is a fixed *distance*, `|w|t_max = 1 366 km` here, so its relative cost falls as
   the domain grows. The corollary for practice: **do not tightly crop the domain to the voyage
   when using the reduction** — a crop that would be safe in the ground frame becomes an `R1`
   violation.

---

## 7.7 A worked size comparison of the two frames

Assembling §7.5 and §7.6 at the 0.25° basin grid, `k = 1`, `c_σ^phys = 400` (unverified):

| Phase | co-moving | ground frame | ratio |
|---|---|---|---|
| `P0` choose `w` | `10⁸` mops (0.05 s) | — | new cost |
| `P1` metric table | `3.93×10⁹` (1.96 s) | `1.33×10¹¹` (66.5 s) | **34×** |
| `P2` coarse + certificate | `6.7×10⁷` (0.03 s) | `2.7×10⁹` (1.4 s) | 40× |
| `P3` sweep | `4.16×10⁸` (0.21 s) | `3.4×10⁸` (0.17 s) | 0.82× (dilation + anisotropy) |
| `P4` interception | `8.2×10⁶` (0.004 s) | — | new cost |
| `P5` recovery | `10⁴` | `10⁴` | — |
| **total** | **`4.5×10⁹` (2.2 s)** | **`1.36×10¹¹` (68 s)** | **30×** |
| **peak memory** | **46 MB** | **1 337 MB** | **29×** |

**Caveat, stated in full.** These are model figures, not measurements, and the dominant input
`c_σ^phys = 400` mops is an unverified estimate. The *ratio* is robust to it, because `c_σ` appears
in both columns of the dominant term and cancels: the metric-table ratio is exactly
`n_fc·N/N_w = 41/1.211 = 33.9`, independent of any cost model. The only measurement that exists is
`CORE-THEOREM` §8.2, and it shows the co-moving solve *slower* by 1.58× — for the reasons decomposed
in §7.5.4, chiefly that the prototype uses a fixed 16-neighbour stencil with no support table at
all, so `P1` (where the entire advantage lives) does not appear in it. **The reduction's cost
advantage is a prediction of this section, not a measured result, and it will only be realised by
an implementation that tabulates the metric.**

---

## 7.8 Parallelism

### 7.8.1 What is embarrassingly parallel

| Phase | Granularity | Speed-up | Notes |
|---|---|---|---|
| `P0` choose `w` | one task per candidate `w` (243 of them), each a read-only reduction over the sample set | linear to 243 cores | percentile is a small final reduction |
| `P1` metric table | one task per `(node, direction)` pair — `N_w n_θ = 9.8×10⁶` tasks | linear | write-disjoint; **the dominant term is the one that parallelises best** |
| `P2` dilated-cell minima | separable running-min, one task per row then per column | linear | van Herk / Gil–Werman is sequential *within* a line, parallel *across* lines |
| `P4` interception | one task per node, then a min-reduction on `(miss, node)` | linear | `O(N_w)` reads of `T_w`, no writes |
| `P8` per-node ε-pruning | one task per node | linear | after the sweep, on the final label sets |
| `Cor 4.12` certificate | one task per route | linear | |

Together these are `W_tab + W_coarse + W_int + W_w ≈ 90 %` of `W_total` in the model of §7.7. The
Amdahl-serial fraction is therefore the sweep, `≈ 10 %`, capping the whole-solve speed-up at
`≈ 10×` unless the sweep is also parallelised — which is what §7.8.2 is about.

### 7.8.2 What is inherently sequential, and the four relaxations

**`P3`, the label-setting sweep, is inherently sequential in its exact form.** The extraction order
is a total order determined by the values being computed, so no node's final value is known before
all smaller ones are. (Single-source shortest paths admits `NC` algorithms via matrix closure, but
at `Õ(N³)` work — irrelevant at `N ~ 10⁵`.) Four standard relaxations apply; each is stated with
the correctness condition it requires, and each condition is proved.

> **Prop 7.11 (bucket-level parallelism is correct at width `Δ_min`).** Let all nodes in the
> current Dial bucket be relaxed concurrently. If the bucket width `Δ ≤ Δ_min = c_geo h F_min^w`,
> no node in a bucket can lower the value of another node in the same bucket, so the concurrent
> relaxation computes exactly the sequential result.
>
> **Proof.** Suppose node `z` is updated from a front point `ξ` lying on an edge incident to node
> `y`, both `y` and `z` in the same bucket. By (7.14) the update satisfies
> `T(z) ≥ W̃(ξ) + Δ_min ≥ min(T(y), T(y')) + Δ_min` for the edge's endpoints. If `T(y) ≤ T(z)` and
> both lie in a bucket of width `Δ ≤ Δ_min`, then `T(z) − T(y) < Δ ≤ Δ_min`, contradicting the
> displayed inequality. Hence no intra-bucket dependency exists and the relaxations commute. ∎
>
> This is **Δ-stepping** (Meyer & Sanders 2003) with `Δ` pinned to the value `ERRATA` E3 derives.
> Available parallelism per bucket is the bucket occupancy, which for a propagating front of
> length `L` is `Θ(L/h)` nodes — at `N_w = 1.4×10⁵` and a front spanning a basin, `Θ(√N_w) ≈ 370`
> nodes per bucket, i.e. **a few hundred-way parallelism**, decaying at the start and end of the
> sweep. Requires an atomic 64-bit CAS on the `(value, parent)` pair, or a per-thread inbox merged
> at bucket boundaries.

> **Prop 7.12 (ghost-layer domain decomposition converges in a bounded number of rounds).**
> Partition `Ω_w` into `D` subdomains with one-cell ghost layers. Initialise all interior values to
> `+∞` except the source. Repeat: solve every subdomain independently to its own fixed point using
> its current ghost values as boundary data; then exchange ghost values, keeping the pointwise
> minimum. Then (i) the iteration is monotone decreasing and bounded below, hence converges;
> (ii) after round `κ`, every node whose optimal characteristic crosses at most `κ − 1` subdomain
> interfaces has attained its final value; (iii) the number of rounds needed is
> `1 + max_y #{interface crossings of the optimal characteristic to y}`.
>
> **Proof.** (i) Each subdomain solve is the fixed point of the monotone operator (7.5) restricted
> to that subdomain with the given boundary data; by `Thm 7.1` Part 1 the operator is monotone in
> the boundary data, and by Part 2 it has a unique fixed point. Ghost exchange takes pointwise
> minima, which cannot increase any value; every value is bounded below by the exact `T_w`, which
> is a lower bound because every value the scheme assigns corresponds to a realisable path. A
> monotone decreasing sequence bounded below converges, and since the state space is finite
> (values from a finite set of possible path sums) it converges in finitely many rounds.
> (ii) Induction on `κ`. Base `κ = 1`: nodes whose optimal characteristic never leaves their own
> subdomain are solved by the first subdomain solve, since the operator restricted to that
> subdomain sees the same front. Step: assume true for `κ`; a node whose characteristic crosses
> `κ` interfaces has, at its last interface crossing, a predecessor whose characteristic crosses
> `κ − 1`, which by hypothesis was final after round `κ`; the exchange at the end of round `κ`
> publishes it, and round `κ + 1`'s subdomain solve propagates it. (iii) Immediate from (ii). ∎
>
> **Correctness requires nothing beyond monotonicity** — the ghost exchange is a Jacobi iteration
> on a monotone operator. What it requires for *efficiency* is that characteristics cross few
> interfaces, which is a property of the partition: a partition aligned with the dominant
> characteristic direction (i.e. with `c_eff = c₀ − w`) minimises crossings, and one orthogonal to
> it maximises them.

> **Relaxation 3 — fast sweeping** (Zhao 2005; Tsai, Cheng, Osher & Zhao 2003 for the anisotropic
> case). Replace the priority order by `2^d = 4` alternating-direction Gauss–Seidel sweeps, which
> parallelise along anti-diagonal levels (Detrixhe, Gibou & Min 2013). **Correctness is
> unconditional** given monotonicity and `Δ_min > 0`: Gauss–Seidel on a monotone operator with an
> acyclic dependency structure converges to the unique fixed point regardless of visit order (only
> the *number* of sweeps depends on order). **Efficiency is not unconditional**: the sweep count is
> the number of times the optimal characteristic field reverses relative to the sweep directions,
> which grows with `Υ` and with domain curvature. For a lat/lon domain with islands, budget 6–12
> sweeps rather than 4. The trade against `Prop 7.12` is that fast sweeping needs no priority
> structure at all and has perfect memory locality.

> **Relaxation 4 — speculative expansion with rollback.** Expand the `κ` smallest-keyed nodes
> concurrently and re-open any node whose value is later lowered. **Correctness is unconditional**
> (the method degenerates to label-*correcting*, i.e. Bellman–Ford-like, which converges for
> non-negative costs), but the work bound is no longer `O(N_w)`: it is `O(N_w + #decreases)`, and
> `#decreases` is unbounded a priori. Use only with `κ` small and a monitored re-open counter; the
> `handbook` instrumentation table's `monotone_violations` counter is exactly the diagnostic.

### 7.8.3 Why stationarity makes domain decomposition easier — precisely

This is a consequence of Theorem C.1(b) and it is worth stating exactly, because "stationary
problems parallelise better" is folklore and the specific mechanism here is sharper than the
folklore.

**In the time-dependent ground frame, a subdomain cannot be solved once.** The interface datum a
subdomain must export is not a number per boundary node but a **function**: "if you enter me at
boundary node `b` at time `t`, you exit at boundary node `b'` at time `Ψ_{b,b'}(t)`." Three
consequences follow, and all three are removed by the reduction:

1. **Interface data volume.** Ground frame: `Ψ` must be sampled at the forecast resolution, so each
   boundary node carries `n_fc` values (41 here) — or, worse, an entry-time-indexed table per
   *pair* of boundary nodes. Co-moving frame: **one `f64` per boundary node.** For a subdomain with
   `∂ = 4√(N_w/D)` boundary nodes, the exchange volume per round drops by exactly `n_fc = 41×`.
2. **Recomputation on re-entry.** Ground frame: if a later, cheaper path re-enters a subdomain at a
   different time, **every internal edge cost changes**, because the metric is evaluated at the
   departure time; the subdomain's entire interior must be recomputed against the new entry time,
   and the "solve" is not a function of the boundary values alone. This is what makes `Prop 7.12`'s
   induction fail in the ground frame: the operator is not merely monotone in the boundary data,
   it has a different *interior* for each entry time. Co-moving frame: `F_w` has no time argument,
   so the subdomain solve **is** a function of its boundary values alone, and `Prop 7.12` applies
   verbatim. **This, not the data volume, is the substantive point.**
3. **Metric-table residency.** Ground frame: the metric table's working set slides through the
   `n_fc` slices as the front advances, so each subdomain's private copy must either hold all 41
   slices (1.6 GB, §7.6.3) or stream them. Co-moving frame: the table is one slice, read-only, and
   **immutable for the whole solve** — it can be replicated per NUMA node or per socket at 39 MB
   and never invalidated. Read-only replication of the dominant data structure is the difference
   between a memory-bound and a compute-bound parallel solve.

**Summary of the parallel picture.** `P1` (the dominant term) is embarrassingly parallel; `P3` (the
sequential core) admits `Prop 7.11` for a few hundred-way intra-bucket parallelism and `Prop 7.12`
for coarse-grained decomposition whose correctness needs only monotonicity and whose *hypotheses
are satisfiable only because the co-moving problem is autonomous*. `P4` is a parallel reduction.
The model of §7.7 gives a serial fraction of `≈ 10 %` before `Prop 7.11`/`7.12`, so an
implementation that parallelises only `P1` is already within `10×` of the ideal, and one that adds
`Prop 7.12` should approach the interface-crossing bound.

---

## 7.9 Comparison with the alternatives

### 7.9.1 Complexity table

`N` = spatial nodes, `n_t` = time levels, `m` = stencil neighbours, `P` = population, `G` =
generations, `n_wp` = waypoints per candidate route, `n_iso` = points per isochrone, `n_stage` =
isochrone stages.

| Method | Time | Memory | Consistent? | Temporal error | Guarantee | Bottleneck objectives |
|---|---|---|---|---|---|---|
| **KAIROS co-moving** (this spec) | `Θ(N_w n_θ c_σ) + Θ(N_w Λ C_AF Υ₁ n_ζ)` | `Θ(N_w n_θ + N_w Λ k)` | **yes** (`Thm 7.1`) | **exactly 0** (`Thm C.1(b)`) | viscosity limit + a posteriori certificate (`Cor 4.12`) | **yes** (`max`-accumulation, `Prop 5.4`) |
| Time-dependent Dijkstra/A\*, `m`-neighbour (the baseline) | `Θ(N m c_σ + N Λ log N)` | `Θ(N)` (or `Θ(N n_t)` with time in the state) | **no** (`Prop 7.2`): floor `sec(π/m) − 1` | `O(Δt)` at leg midpoint — measured `6.7×10⁻³ m/s` | optimal *on the graph*, not on the continuum | yes, with Martins (1984) labels |
| Level-set HJB marching (Lolla & Lermusiaux 2014) | `Θ(n_t N ·(c_σ + c_upwind))`, `n_t ≥ t_max σ_max/h` (CFL) | `Θ(N n_t)` if the whole history is kept for backtracking | yes, for the level-set scheme | `O(Δt)` per step | viscosity limit | not naturally (needs a second field) |
| Isochrone (James 1957; Hagiwara 1989) | `Θ(n_stage n_iso n_head c_σ)` | `Θ(n_stage n_iso)` | no — heuristic pruning | `O(Δt_stage)` | **none** | no |
| NSGA-II (Deb et al. 2002) | `Θ(P G n_wp c_σ) + Θ(G k P²)` sorting | `Θ(P n_wp)` | n/a (not a PDE scheme) | `O(Δt)` in the route integrator | **none**; stochastic, non-reproducible | yes, trivially (any objective) |

### 7.9.2 Operation counts at a concrete size

Basin grid, 0.25°, `N = 112 681`, `N_w = 136 456`, `t_max = 5 d`, `h = 27.8 km`,
`σ_max = V_s + |c| ≈ 10.4 m/s`, `n_fc = 41`, `n_θ = 72`, `k = 1`, `c_σ^phys = 400` mops
(**unverified estimate — the column is a model, not a measurement**).

| Method | derivation | mops | @2×10⁹ mops/s |
|---|---|---|---|
| **KAIROS co-moving** | table `136 456×72×400 = 3.93e9`; sweep `136 456×3 049 = 4.2e8`; coarse `6.7e7`; interception `8.2e6`; `w` search `1e8` | **4.5×10⁹** | **2.2 s** |
| KAIROS ground frame (same scheme, no reduction) | table `112 681×72×400×41 = 1.33e11`; sweep `3.4e8` | 1.36×10¹¹ | 68 s |
| `m = 16` time-dependent Dijkstra | `112 681×16×(400+30) = 7.8e8`; heap `112 681×17×10 = 1.9e7` | **8.0×10⁸** | **0.40 s** |
| `m = 84` (equal *isotropic* accuracy, 0.070 %) | `m*` from `sec(π/84)−1 = 7.0×10⁻⁴`; arms `R_84 = 6.63h = 184 km`; `112 681×84×430 = 4.1e9` | 4.1×10⁹ | 2.0 s |
| Level-set HJB march | `n_t = ⌈432 000×10.4/27 800⌉ = 162` steps; `162×112 681×(400+60) = 8.4e9` | 8.4×10⁹ | 4.2 s |
| Isochrone | `n_stage = 40` (3-hourly), `n_iso = 200`, `n_head = 60`: `40×200×60×430 = 2.1e8` | 2.1×10⁸ | 0.10 s |
| NSGA-II | `P = 200`, `G = 500`, `n_wp = 40`: `10⁵×40×430 = 1.7e9`; sorting `500×3×4×10⁴ = 6×10⁷` | 1.8×10⁹ | 0.9 s |

### 7.9.3 Reading the table honestly

**KAIROS is not the fastest method here, and this section will not pretend otherwise.** The
isochrone method is 20× cheaper and NSGA-II is 2.4× cheaper. Four points make the comparison
meaningful rather than flattering:

1. **The `m = 16` baseline is cheaper (0.40 s vs 2.2 s) and wrong by 1.96 % at every resolution**
   (`Prop 7.2`, confirmed by (7.37)). The correct comparison is at equal accuracy, and the `m = 84`
   row supplies it: **4.1×10⁹ mops, essentially identical to KAIROS's 4.5×10⁹** — and the `m = 84`
   scheme is still *anisotropically* wrong by (7.32), still carries an `O(Δt)` temporal error, and
   needs stencil arms of 184 km, which exceed the correlation length of a mesoscale current field
   so that (7.35)'s quadrature term takes over. At equal accuracy the continuum update wins on
   robustness rather than on raw count, and the honest headline is **"comparable cost, strictly
   better error structure"**, not "faster".
2. **The reduction's own advantage is 30× and it is entirely in `P1`** (row 1 vs row 2). It exists
   only for implementations that tabulate the metric; a solver that re-evaluates the physics per
   edge does not see it. This is a prediction of §7.5, not a measurement.
3. **What the cheap methods do not provide.** Isochrone and NSGA-II return no bound of any kind.
   KAIROS returns `Cor 4.12`'s a posteriori certificate — computable, tight, and not degrading with
   voyage length — which after `ERRATA` E6 is the *primary* guarantee in the whole specification,
   because the a-priori realisability bound was shown to be vacuous (`exp(L_v T) ≈ 1.6×10⁵` at 14
   days). NSGA-II additionally returns a *different answer each run*, which is disqualifying for an
   operational routing product that must be auditable.
4. **The level-set method (Lolla & Lermusiaux 2014) is the closest honest competitor** and is
   within a factor of 2. It is CFL-limited (`n_t ≥ t_max σ_max/h`, so refining `h` costs `h⁻³` in
   2-D, versus `h⁻²` for a stationary solve), it stores `Θ(N n_t)` for backtracking (`112 681 × 162 × 4` = 73 MB here,
   growing with the horizon), and it carries an `O(Δt)` temporal error that the reduction removes
   exactly. It also returns the full reachable-set evolution, which is genuinely more information
   than KAIROS's `T_w` and is the right tool if that is what you want.

**Prior art credited by name, as required.** Zermelo (1931) for the navigation problem; Taylor
(1938) for the frozen-field hypothesis that is assumption (A1)'s meteorological ancestor;
Bao–Robles–Shen (2004) for the Zermelo↔Randers correspondence used in (C.6); Sethian & Vladimirsky
(2003) for ordered upwind methods and for the observation motivating `Prop 7.2`; Vladimirsky (2006)
for causality conditions for single-pass solution of time-dependent control problems — **our `P3`
removes the need for his condition rather than checking it, which is a different claim from
improving on it**; Kumar & Vladimirsky (2010) for multi-objective control by fast marching;
Tsaggouris & Zaroliagis (2009) for the value-bucketing construction of `ERRATA` (E7.1); Barles &
Souganidis (1991) for the convergence framework of `Thm 7.1`; Dial (1969) for the bucket queue;
Martins (1984) for multi-objective label setting; Lolla & Lermusiaux (2014) for level-set ship
routing; Markvorsen (2025) for time-dependent Zermelo navigation with tacking (time-dependent-only
indicatrix fields — a complementary special case); Ochi (1964) for slamming and deck-wetness
probabilities, Fujiwara (2006) for wind resistance, and IMO MSC.1/Circ.1228 for the parametric-roll,
synchronous-roll and surf-riding guidance that together constitute the `c_σ^phys` cost constant.

---

## 7.10 Conflicts and discrepancies found while writing this file

Recorded because the specification is normative and a reader must know which text wins.

1. **`CONTRACT` §0 vs `CORE-THEOREM`.** `CONTRACT`'s framing paragraph defines KAIROS as
   "ε-Pareto anisotropic ordered-upwind front propagation … licensed by a sharp causality
   condition". `CORE-THEOREM` demotes all of that to supporting apparatus and removes the causality
   condition entirely from the co-moving solve. **`CORE-THEOREM` wins** (its own status line, and
   `ERRATA` E10–E11). §7 is written to the new hierarchy.
2. **`CONTRACT` D3 vs `ERRATA` E2.** D3 says fall back to a heap when "`F_min` is not bounded away
   from 0". E2 proves `F_min = 1/(V_max+|c|)` is bounded below by construction and that the real
   failure is unbounded *bucket count* (E2.2). **E2 wins**; the fallback trigger is
   `Υ_loc > Υ_heap = 12`. `Prop 7.10` is stated to E2.
3. **`CONTRACT` D6 vs `ERRATA` E6.** D6 mandates a Grönwall factor `exp(L_x v_max S)`; E6 shows the
   correct factor is `exp(L_v T)` with a new symbol `L_v` [1/s], that the global bound is
   **vacuous** for Indian Ocean numbers, and that `Thm 2.11` survives only in the local form E6.3.
   **E6 wins.** §7 therefore treats `Cor 4.12` as the primary guarantee throughout.
4. **Internal inconsistency inside `CORE-THEOREM`.** §8 step 1 of the algorithm listing says
   "`w ← phase-correlate consecutive forecast frames (§7.3)`", but §7 of the *same document* reports
   that phase correlation **failed** (returned `(−0.74, 0.00)` against a true `(2.0, 0.5)`) and
   replaces it with Eq (C.10), minimisation of the residual causality constant. The §8 listing is
   stale. **§7 / Eq (C.10) wins**, and it is what `W_w` (7.42) costs and what
   `comoving.choose_advection` implements. This is the one genuine internal conflict found.
5. **`handbook/01-golden-vectors.md` G5 and `handbook/02-debugging-playbook.md` S7 use the
   pre-errata causality form.** G5's reporting table requires "Max `h·L_t` over the domain … `< 1`";
   S7's sanity check says "`h·L_t` should be `≈ 0.05–0.15`". `ERRATA` E4 supersedes both: the
   diagnostic is `max_x r(x)·L_t(x,t)`, which is up to `Υ` times larger. **The handbook rows should
   be updated**; an implementation reporting `h·L_t` will emit a green certificate on forecasts
   where the sweep is not licensed. (In the co-moving frame both forms read zero, which is why this
   never surfaced in the co-moving tests.)
6. **`CORE-THEOREM` §7 "three rounds of 9×9" vs `comoving.choose_advection` default `n = 7`.** The
   spec figure (243 evaluations) is normative; the code figure (147) is a default. Not a conflict
   between normative documents, but `W_w` (7.42) is quoted with the spec figure and the measured
   0.05 s was produced with the code figure.
7. **The shipped solver does not satisfy `Thm 7.1`.** `comoving.stationary_sweep` uses a fixed
   16-neighbour stencil, so it satisfies `Prop 7.2` — including the non-vanishing `1.96 %`
   metrication floor — not `Thm 7.1`. Its own docstring says so. Every measured accuracy figure in
   `CORE-THEOREM` must be read with that floor attached, and §7.3.2 shows it *was* measured.

---

## 7.11 Instrumentation this file requires

`Thm 7.3` and §7.6 are only as good as the quantities an implementation actually reports. Beyond
the `handbook` list, §7 needs these, and they cost nothing:

| Quantity | Why | Where it appears |
|---|---|---|
| `N_ground` and `N_comoving` **separately** | the only way to settle §7.5.4's Reading A vs B | (7.55), `Cor 7.13` |
| `required_dilation_m` vs actual grid bounds, asserted at start-up | `R1` fails **silently**; 104.5 km measured | (S3), `Cor 7.13` |
| histogram of `Υ_loc^w`, and `Υ₁`, `Υ₂` | the cost model's dominant sweep constant, and the anisotropy the reduction *costs* | (7.1)–(7.3), (7.52) |
| `max_y |NF(y)|` against `C_AF r_max/h` | validates (S5); grows in archipelagos | (S5), (7.45) |
| distribution of the inner minimiser's `ζ` | endpoint-pinned ⟹ the `ζ` search is broken ⟹ you are running `Prop 7.2`, not `Thm 7.1` | §7.2.3, `handbook` S3 |
| fraction of update evaluations rejected by the `ℓ_min` exclusion | validates `ERRATA` E3 is actually implemented | (7.4), (7.14) |
| `max_x r(x)·L_t` — **not** `max_x h·L_t` | `ERRATA` E4; must read 0 in the co-moving frame and is the licence for `P6` | (7.13), (7.26) |
| `max_u σ_w/σ_{𝒫_m}` per cell, if a fixed stencil is used | converts `Prop 7.2` from an argument into a measurement | (7.31) |
| peak and mean `Λ`, and the count of `Λ_max` truncations | memory dominates for `k ≥ 2`; E7.2's worst case is 150 GB | §7.6.3 |
| `|K|/N_w` for the corrector and `|K_R|/N_w` for repair | near 1.0 means the closure is degenerate | (7.48), (7.49), `handbook` S9 |
| bucket-queue monotonicity violations | must be 0 | `Prop 4.9`, `Prop 7.11` |
| landfall miss in metres, against the bound (7.39) | the interception term of the error budget | §7.4.1(P-e) |

Reporting these is what separates a validated implementation from a demo, and every claim in this
file is falsifiable against them.
