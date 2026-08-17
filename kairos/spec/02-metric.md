# §2 — The indicatrix and the Finsler metric

**Block owner:** `Def 2.x`, `Prop 2.x`, `Thm 2.x`, `Eq (2.x)`.
**Normative inputs, in precedence order:** `spec/CORE-THEOREM.md` (Thm C.1 and Eqs C.1–C.10),
`spec/ERRATA.md` (E1, E2, E6, E8, E9 bind this file), `spec/CONTRACT.md` (symbols, numbering,
design decisions D1–D7). Where this file and `docs/` disagree, `docs/` is wrong.
**Consumers:** §3 (causality), §4 (stencil, bucket queue), §5 (labels), §6 (root finds), §7
(complexity), §8 (validation).

---

## 2.0 What this section is, and what it is not

KAIROS is defined by the **Co-Moving Reduction** (Thm C.1): in coordinates `y = x − w t` the
routing problem is *exactly stationary*, the FIFO/causality obstruction dissolves, and the
solve is one monotone pass plus a scalar interception. Section 2 is **supporting apparatus**
for that theorem, not a competing claim. Its job is to supply four things the reduction needs:

1. a precise object to shift — the indicatrix `𝒱` (Def 2.1) and its gauge `F` (Def 2.2);
2. the statement that a *stationary* minimum-time problem **is** a length-minimisation problem
   (Prop 2.4), which is what makes "one monotone pass" meaningful;
3. the closed form and the numerically safe evaluation procedure that must survive the
   substitution `c ← c₀ − w` (Prop 2.8, Prop 2.10);
4. the constants `Υ_loc`, `F_min`, `F_max` that §4 sizes its stencil and its bucket ring with
   (Def 2.9).

**Novelty ledger for this section.** Only **Prop 2.10** (shift invariance of the indicatrix,
preservation of Randers structure, the corrected admissibility condition (C.7), and the
`w`-independence of the support tabulation) is claimed as new, and it is a corollary of
Thm C.1 rather than an independent result. Everything else is classical and is credited where
it is used:

| Object | Source |
|---|---|
| Minimum-time navigation in a drift field | Zermelo (1931) |
| Randers metric `F = α + β` | Randers (1941) |
| Zermelo ↔ Randers correspondence, the `|b|_α < 1` condition | Bao, Robles & Shen (2004) |
| Gauge / support-function duality, bipolar theorem | Minkowski; Rockafellar (1970); Schneider (1993) |
| Convex hull of a set in `ℝ²` = combinations of ≤ 3 points | Carathéodory (1911) |
| Relaxed controls, chattering realises `conv` | Filippov (1967); Warga (1972) |
| Anisotropy-driven stencils | Sethian & Vladimirsky (2003); Vladimirsky (2006) |
| Frozen-field (rigid-translation) hypothesis | Taylor (1938) |
| Level-set reachability formulation of ship routing | Lolla & Lermusiaux (2014) |
| Bucket queue whose width needs `F_min > 0` | Dial (1969) |
| Seakeeping criteria that carve `𝒱` (slamming, wind resistance, operational limits) | Ochi (1964); Fujiwara (2006); IMO MSC.1/Circ.1228 |

Nothing in §2 is claimed as a first.

**Frame convention (ERRATA E8, binding).** Throughout §2, all velocity vectors are components
in the *local orthonormal frame* `(𝐞_E, 𝐞_N)` in **m/s**. The chart conversion (E8.1) is
applied at the geodesy boundary and nowhere else. `ẋ` therefore means "ground velocity in the
local frame", never `(λ̇, ϕ̇)`. Every set in this section lives in `ℝ²` with the Euclidean inner
product `⟨·,·⟩` and norm `|·|` of that frame.

---

## 2.1 The indicatrix

> **Definition 2.1 (Indicatrix).** For `(x,t) ∈ Ω × [t₀, t₀+H_fc]` the **indicatrix** is the
> set of over-ground velocities the vessel can hold instantaneously:
> ```
> 𝒱(x,t) := { V_pwr(q,θ; x,t)·n(θ) + c(x,t) : (q,θ) ∈ 𝒜(x,t) } ∪ { c(x,t) } ⊂ ℝ²    (2.1)
> ```
> with `n(θ) = (sin θ, cos θ)`, `𝒜(x,t)` the seakeeping-admissible control set of Def 1.21,
> `V_pwr` the attainable through-water speed of §1.3.6, and `c(x,t)` the effective drift of
> Def 1.3 (current + leeway, folded once and never unfolded). The isolated point `c` is the
> engine-stopped control (drifting / hove-to).

> **Lemma 2.1.1 (Def 2.1 agrees with the radial form (1.39)).** `𝒱(x,t)` as defined by (2.1)
> equals `{ σ(x,t,u,q)·u : u ∈ S¹, q ∈ Q_feas(x,t,u) } ∪ {c}` of Eq (1.39).
>
> **Proof.** *(⊆)* Let `v = V n(θ) + c` with `(q,θ) ∈ 𝒜`, `v ≠ 0`. Put `u := v/|v|`. Then `v`
> is a ground velocity directed along `u`, so decomposing `c = c_∥u + c_⊥u^⊥` gives
> `|v| = c_∥ + √(V² − c_⊥²)`, which is exactly `σ(x,t,u,q)` of (1.37) with `θ = θ*(q,u)` the
> crab-angle solution of §1.4.2 (the heading that cancels the cross-track drift). Hence
> `v = σ(x,t,u,q)·u`. If `v = 0` then `V n(θ) = −c`, so `|c| = V` and `σ(u,q) = 0` for the
> corresponding `u`; the point `0` is then a limit of the radial family and both sides contain
> it or neither does, per the convention `σ = 0 ⟹ direction excluded`.
> *(⊇)* Given `u` and `q ∈ Q_feas(x,t,u)`, the crab-angle fixed point `θ*(q,u)` exists by
> definition of `Q_feas`, `(q,θ*) ∈ 𝒜`, and `V n(θ*) + c = σ(u,q)·u` by the same decomposition
> read backwards. ∎
>
> **Why it matters.** (2.1) is the *generative* form — it is how the physics layer produces the
> set. (1.39) is the *radial* form — it is how the solver consumes it, via the single primitive
> `sigma(x,t,u,q)` of `CONTRACT §4`. Every statement below can be read in either.

> **Lemma 2.1.2 (Translation structure).** Define the **water-frame body**
> ```
> 𝒲(x,t) := { V_pwr(q,θ; x,t)·n(θ) : (q,θ) ∈ 𝒜(x,t) } ∪ { 0 } .                     (2.2)
> ```
> Then
> ```
> 𝒱(x,t) = 𝒲(x,t) ⊕ c(x,t) := { ν + c(x,t) : ν ∈ 𝒲(x,t) } ,                         (2.3)
> ```
> and consequently `conv 𝒱 = (conv 𝒲) ⊕ c`.
>
> **Proof.** (2.3) is (2.1) rewritten; the isolated point `c` of (2.1) is `0 ∈ 𝒲` translated.
> For the hull: `conv(A ⊕ {p}) = (conv A) ⊕ {p}` because `x ↦ x + p` is an affine bijection and
> affine maps commute with convex hulls. ∎
>
> **This lemma is the load-bearing one for the whole of KAIROS.** It says the environment
> enters the achievable set **only as a translation**, and the vessel/sea-state physics enter
> only through `𝒲`. Prop 2.10 — the co-moving shift — is nothing more than Lemma 2.1.2 applied
> with `c ← c − w`. It is also why Def 1.3 folds leeway into `c` rather than leaving it as a
> separate heading-dependent force: if leeway lived inside `𝒲`, the frame change of Thm C.1
> would not be a pure translation of `𝒱` and the reduction would need new metric code.

**Structural facts inherited from §1, used without reproof.**

| Fact | Source | Consequence in §2 |
|---|---|---|
| `𝒜(x,t)` compact | Prop 1.22(c) | `𝒱` compact; `max`/`sup` attained in Def 2.6, Def 2.3 |
| `𝒜`, hence `𝒱`, generally non-convex and disconnected | Prop 1.22(d) | Prop 2.2.2 can fail on raw `𝒱`; D4 exists for this reason |
| `𝒱` is a 2-D annular region with a hole around `c` | Cor 1.11.0 | `0 ∉ 𝒱` under E9(3); Thm 2.11 bounds the cost of filling it |
| `q ↦ σ(x,t,u,q)` strictly increasing; `q^† = 1` in the ban-free case | Prop 1.11 | for the **time** objective `𝒱` may be replaced by its outer boundary |

**Notation fixed here and used everywhere below.**

```
V_max(x,t)   := max_{(q,θ) ∈ 𝒜(x,t)} V_pwr(q,θ; x,t)          [m/s, THROUGH WATER]   (2.4)
V_max(θ;x,t) := max_{q : (q,θ) ∈ 𝒜} V_pwr(q,θ; x,t)           per-heading version
V_min(x,t)   := min over the same set                          [m/s, THROUGH WATER]
```

`V_max` is **through-water speed**, never speed made good. ERRATA E1 exists because the draft
used `σ_max` where `V_max` was meant; the two differ by `|c|` and the substitution turns a
live test into dead code. Wherever `σ_max` appears below it means speed made good over ground
and is *never* compared against `|c|`.

**Derived constant (engine minimum).** With the Admiralty powering law `P ∝ V^{n_adm}`,
`n_adm = 3` (Vessel default), and `P = q·P_MCR`,
```
V_min / V_max = q_min^{1/n_adm} = 0.15^{1/3} = 0.531 329 …                          (2.5)
```
so the default vessel **cannot steam below 53.1 % of its maximum through-water speed**. This
number is used in Prop 2.5(F3) and in Thm 2.11. It is derived, not measured; it changes if the
speed–power curve is replaced by a measured spline (`Vessel.calm_power` override), and the
implementation must recompute it rather than hard-code 0.531.

---

## 2.2 The gauge

> **Definition 2.2 (Minkowski gauge; the Finsler metric).** With `K(x,t) := conv 𝒱(x,t)`
> (design decision **D4**; see Rmk 2.2.4 for the unconvexified reading),
> ```
> F(x,t,v) := inf { τ > 0 : v/τ ∈ K(x,t) } ,   inf ∅ := +∞ ,   F(x,t,0) := 0 .      (2.6)
> ```
> **Units:** s/m. **Meaning:** `F(x,t,v)` is the shortest time in which the displacement `v`
> can be achieved at `(x,t)`, holding the environment frozen.

`F` is *not* a norm: it is not symmetric (`F(−v) ≠ F(v)` whenever `c ≠ 0`), and it may be
`+∞`. It is a Finsler *fundamental function* in the sense of Def 2.2 only; smoothness and
strong convexity of `F²`, which classical Finsler geometry assumes, hold in the Randers case
(§2.8) and fail wherever a seakeeping ban puts a corner on `∂K`.

> **Lemma 2.2.1 (Positive 1-homogeneity).** For every `s > 0` and every `v ∈ ℝ²`,
> ```
> F(x,t,s v) = s · F(x,t,v) .                                                        (2.7)
> ```
>
> **Proof.** Fix `(x,t)`, write `K` for `K(x,t)`. If `v = 0` both sides are `0`. Otherwise
> ```
> F(sv) = inf{ τ > 0 : (sv)/τ ∈ K } .
> ```
> The substitution `τ = s τ'` is a bijection of `(0,∞)` onto itself (because `s > 0`), and
> `(sv)/(sτ') = v/τ'`, so the constraint set is `{ τ' > 0 : v/τ' ∈ K }` and
> `F(sv) = inf { s τ' : v/τ' ∈ K } = s · inf { τ' : v/τ' ∈ K } = s F(v)`, the last step
> because `s > 0` commutes with `inf`. If the constraint set is empty both sides are `+∞`. ∎
>
> **Sharpness.** Homogeneity holds only for `s > 0`. `F(−v) = F(v)` requires `K = −K`, i.e.
> `c = 0` and a heading-symmetric `𝒲`. The failure of *negative* homogeneity is precisely the
> physical content of the problem: sailing downstream and upstream are different.
>
> **What breaks without it.** Prop 2.4 (parameterisation invariance) and Prop 2.7 (the
> `𝔥(p)/⟨u,p⟩` recovery) both use (2.7) directly. A metric that is not 1-homogeneous makes the
> arrival time depend on how finely a straight leg is subdivided, which shows up in §8 as a
> convergence test that plateaus at a resolution-dependent value.

> **Definition 2.2a (unit ball).** `B_F(x,t) := { v ∈ ℝ² : F(x,t,v) ≤ 1 }`.

> **Lemma 2.2.1b (Identification of the unit ball).** For compact `K` (Def 2.2),
> ```
> B_F = star(K) := { μ k : k ∈ K , μ ∈ [0,1] } .                                     (2.8)
> ```
> If in addition `K` is convex, `star(K) = conv({0} ∪ K)`, which is convex.
>
> **Proof.** *(⊇)* Let `v = μk`, `k ∈ K`, `μ ∈ (0,1]`. Then `v/μ = k ∈ K`, so `F(v) ≤ μ ≤ 1`.
> For `μ = 0`, `v = 0` and `F(0) = 0`.
> *(⊆)* Let `F(v) ≤ 1`, `v ≠ 0`. Take `τ_n ↓ F(v)` with `v/τ_n ∈ K`. `K` is compact hence
> closed, and `v/τ_n → v/F(v)` (note `F(v) > 0` because `K` is bounded: if `|k| ≤ R` for all
> `k ∈ K` then `v/τ ∈ K` forces `τ ≥ |v|/R > 0`). Hence `v/F(v) ∈ K` and
> `v = F(v)·(v/F(v)) ∈ star(K)` with `μ = F(v) ≤ 1`.
> *Convex case.* For convex `K`, `conv({0} ∪ K) = { μk : k ∈ K, μ ∈ [0,1] }`: the right-hand
> side is contained in the left by definition; conversely any point of `conv({0}∪K)` is
> `λ·0 + (1−λ)·k'` with `k' ∈ conv K = K`, which has the stated form with `μ = 1−λ`. Convexity
> of a hull is automatic. ∎

> **Proposition 2.2.2 (Subadditivity holds exactly when the unit ball is convex).**
> ```
> F(x,t, v₁+v₂) ≤ F(x,t,v₁) + F(x,t,v₂)   for all v₁,v₂ ∈ ℝ²
>                       ⟺        B_F(x,t) is convex.                                 (2.9)
> ```
>
> **Proof.** Fix `(x,t)` and drop it.
>
> *(⇐) Convex ball ⟹ subadditive.* If either `F(v_i) = +∞` the inequality is vacuous, so
> assume both finite. Fix `τ_i > F(v_i)` arbitrary (if `F(v_i) = 0` then `v_i = 0`, since
> `F(v) = 0` with `v ≠ 0` would need `v/τ ∈ K` for arbitrarily small `τ`, contradicting
> boundedness of `K`; the inequality is then trivial, so assume `τ_i > 0`). By homogeneity
> `F(v_i/τ_i) = F(v_i)/τ_i < 1`, so `v_i/τ_i ∈ B_F`. Put `τ := τ_1 + τ_2 > 0` and write
> ```
> (v₁+v₂)/τ  =  (τ₁/τ)·(v₁/τ₁)  +  (τ₂/τ)·(v₂/τ₂) ,
> ```
> a convex combination (`τ_i/τ ≥ 0`, sum `1`) of two points of `B_F`. Convexity gives
> `(v₁+v₂)/τ ∈ B_F`, i.e. `F((v₁+v₂)/τ) ≤ 1`, i.e. `F(v₁+v₂) ≤ τ = τ₁+τ₂` by (2.7). Letting
> `τ_i ↓ F(v_i)` gives (2.9).
>
> *(⇒) Subadditive ⟹ convex ball.* Let `a, b ∈ B_F` and `s ∈ [0,1]`. For `s ∈ (0,1)`,
> subadditivity and then (2.7) give
> ```
> F(sa + (1−s)b) ≤ F(sa) + F((1−s)b) = s F(a) + (1−s) F(b) ≤ s + (1−s) = 1 ,
> ```
> so `sa+(1−s)b ∈ B_F`. For `s ∈ {0,1}` the point is `a` or `b`, already in `B_F`. ∎

> **Corollary 2.2.3 (D4 buys subadditivity unconditionally).** Under D4, `K = conv 𝒱` is convex
> and compact, so by Lemma 2.2.1b `B_F = conv({0} ∪ K)` is convex, and by Prop 2.2.2 `F` is
> subadditive. **Note carefully that this holds whether or not `0 ∈ K`** — the star hull of a
> convex set about *any* point is convex, so the strong-drift (Kropina) case of §2.8, where
> `0 ∉ K`, still has a subadditive `F` (taking values `+∞` outside the reachable cone, with the
> convention `a + ∞ = ∞`). ∎

> **Remark 2.2.4 (What breaks without D4 — a concrete failure).** On the raw `𝒱`, `F` need not
> be subadditive, and the triangle inequality is what makes "shortest path" well posed. Take a
> cell in which a resonance ban (S1/S2, §1.5) removes an upper speed interval in a heading
> wedge, so that in the calm-water, current-free case
> ```
> 𝒱 = { v : |v| ≤ r(v/|v|) } ,   r(u) = V_s except r(u) = V_s/2 for u in a wedge W
> ```
> where `W` is a wedge of half-angle `δ` about `(1,1)/√2`. With `e₁,e₂` the frame axes and
> `δ > 0` small enough that `e₁, e₂ ∉ W` while `(e₁+e₂)/√2 ∈ W`:
> ```
> F(e₁) = 1/V_s ,   F(e₂) = 1/V_s ,   F(e₁+e₂) = √2 / (V_s/2) = 2√2 / V_s ≈ 2.83/V_s
> ```
> against `F(e₁)+F(e₂) = 2/V_s`. **Subadditivity fails by 41 %.** Physically the relaxed
> control that restores it is *alternating between two admissible headings*, which is exactly
> what D4 licenses and exactly what Thm 2.11 charges for. Without D4 the Hamiltonian in §3 is
> non-convex, the viscosity-solution theory of Barles & Souganidis (1991) invoked in Thm 7.1
> does not apply as stated, and the ordered-upwind update of §4 may return a value that a
> refinement of the same stencil beats — the plateau symptom S3 of the debugging playbook.

> **Remark 2.2.5 (`F` cannot see non-convexity anyway).** By Lemma 2.6.1 the support function,
> and hence the Hamiltonian of §3, is identical for `𝒱` and `conv 𝒱`. D4 is therefore not an
> approximation at the level of the HJB equation; it is an approximation only at the level of
> *realising* the optimal control with a physical rudder, which is Thm 2.11's subject.

---

## 2.3 Speed made good

> **Definition 2.3 (Speed made good).** For a unit vector `u ∈ S¹`,
> ```
> σ(x,t,u) := max { s ≥ 0 : s·u ∈ K(x,t) }  ( = 0 if no s > 0 qualifies) ,          (2.10)
> ```
> the **radial function** of `K` in direction `u`. With the throttle dimension exposed (D1),
> `σ(x,t,u,q)` is (1.37) and `σ(x,t,u) = max_{q ∈ Q_feas} σ(x,t,u,q) = σ(x,t,u,q^†)` by
> Prop 1.11(b). Define
> ```
> σ_max(x,t) := max_{|u|=1} σ(x,t,u) ,     σ_min(x,t) := min_{|u|=1} σ(x,t,u) .      (2.11)
> ```

The `max` in (2.10) is attained because `K` is compact and `{s ≥ 0 : su ∈ K}` is closed and
bounded.

> **Lemma 2.3.1 (`F` and `σ` are reciprocal).** For `v ≠ 0` with `u := v/|v|`,
> ```
> F(x,t,v) = |v| / σ(x,t,u) ,     F(x,t,u) = 1/σ(x,t,u) ,                            (2.12)
> ```
> with `1/0 := +∞`. Consequently
> ```
> F_min(x,t) = 1/σ_max(x,t) ,     F_max(x,t) = 1/σ_min(x,t) .                        (2.13)
> ```
>
> **Proof.** `F(v) = inf{τ>0 : v/τ ∈ K} = inf{τ>0 : (|v|/τ)u ∈ K}`. Put `s := |v|/τ`, a
> decreasing bijection of `(0,∞)` onto itself; the constraint becomes `su ∈ K` and minimising
> `τ = |v|/s` means maximising `s`. Hence `F(v) = |v|/max{s>0 : su ∈ K} = |v|/σ(u)`, with the
> empty-set convention on both sides. (2.13) is (2.12) at `|v| = 1` together with (2.11). ∎

**Implementation note (D7).** `σ` is the *only* metric primitive the solver calls
(`CONTRACT §4`). Everything in §1 — powering, added resistance, seakeeping bans, throttle
Pareto sets — is behind it. An implementation that exposes `F` instead is equivalent; it must
then compute `1/σ` rather than re-deriving the gauge, because §2.8 shows the two have
different conditioning in the strong-drift regime.

---

## 2.4 Voyage time is a Finsler length

This is the proposition that turns "minimum-time routing" into "geodesic", and it is
**true only for a stationary indicatrix**. That restriction is the whole reason Thm C.1 is the
core of KAIROS: the reduction manufactures the stationarity that Prop 2.4 needs.

> **Proposition 2.4 (Voyage time = Finsler length; parameterisation invariance).**
> **Hypotheses.**
> (H1) `𝒱` is **stationary**: `K(y) := conv 𝒱₀(y)` depends on position only.
> (H2) `K(y)` is compact for every `y`, and there are constants with
> `0 < σ_min ≤ σ(y,u) ≤ σ_max < ∞` for all `y ∈ Ω`, `u ∈ S¹`.
> (H3) `y ↦ K(y)` is continuous in the Hausdorff metric (so `F` is continuous on `Ω × (ℝ²∖0)`).
>
> Let `Γ ⊂ Ω` be a rectifiable oriented curve from `y_A` to `y_B`, and let `y : [0,S] → Ω` be
> any absolutely continuous, orientation-preserving parameterisation of it. Define the
> **Finsler length**
> ```
> 𝓛[Γ] := ∫₀^S F( y(s), y'(s) ) ds .                                                 (2.14)
> ```
> Then:
> **(a) (Invariance.)** `𝓛[Γ]` is unchanged by any absolutely continuous, non-decreasing,
> surjective reparameterisation `φ : [0,S'] → [0,S]`.
> **(b) (Lower bound.)** Every admissible trajectory `x : [0,T] → Ω` with `ẋ(t) ∈ K(x(t))`
> a.e. that traverses `Γ` monotonically satisfies `T ≥ 𝓛[Γ]`.
> **(c) (Attainment.)** There is an admissible trajectory traversing `Γ` in time exactly
> `𝓛[Γ]`; it is the reparameterisation of `y` by Finsler arclength, and it satisfies
> `F(x(τ), ẋ(τ)) = 1` a.e.
> **(d)** Hence the minimum voyage time over all routes equals `min_Γ 𝓛[Γ]`, i.e. the
> minimum-time problem **is** the Finsler geodesic problem for `F`.
>
> **Proof.**
>
> **(a)** Let `φ` be as stated. `y ∘ φ` is absolutely continuous (composition of an AC function
> with a monotone AC function is AC) and `(y∘φ)'(r) = y'(φ(r))·φ'(r)` for a.e. `r`, with
> `φ'(r) ≥ 0`. By Lemma 2.2.1,
> ```
> F( y(φ(r)), y'(φ(r))·φ'(r) )  =  φ'(r) · F( y(φ(r)), y'(φ(r)) ) ,
> ```
> valid also where `φ'(r) = 0` since `F(·,0) = 0`. Integrating and applying the
> change-of-variables theorem for monotone absolutely continuous maps (which is legitimate
> because AC maps satisfy Luzin's property (N), so null sets are preserved and the integrand
> `g(s) := F(y(s),y'(s))` — measurable and non-negative — satisfies
> `∫₀^{S'} g(φ(r)) φ'(r) dr = ∫₀^{S} g(s) ds`):
> ```
> ∫₀^{S'} F( (y∘φ)(r), (y∘φ)'(r) ) dr = ∫₀^{S'} g(φ(r)) φ'(r) dr = ∫₀^{S} g(s) ds = 𝓛[Γ]. ∎(a)
> ```
>
> **(b)** Let `x : [0,T] → Ω` be admissible and traverse `Γ` monotonically. Admissibility means
> `ẋ(t) ∈ K(x(t))` a.e.; by Lemma 2.2.1b `K(x(t)) ⊆ B_F(x(t))`, hence
> ```
> F( x(t), ẋ(t) ) ≤ 1     for a.e. t ∈ [0,T].
> ```
> Monotone traversal means `x = y ∘ φ` for some non-decreasing surjective `φ : [0,T] → [0,S]`,
> which is AC because `x` and `y` are AC and `|y'| = 1` under the arclength normalisation used
> below. Part (a) then gives `∫₀^T F(x,ẋ) dt = 𝓛[Γ]`. Therefore
> ```
> 𝓛[Γ] = ∫₀^T F(x(t),ẋ(t)) dt  ≤  ∫₀^T 1 dt = T .                            ∎(b)
> ```
>
> **(c)** Normalise `y` by Euclidean arclength, so `|y'(s)| = 1` for a.e. `s ∈ [0,S]`. By (H2)
> and Lemma 2.3.1,
> ```
> 1/σ_max ≤ g(s) := F(y(s), y'(s)) ≤ 1/σ_min       for a.e. s,                       (2.15)
> ```
> so `g` is bounded above and *below by a positive constant*. Define
> `τ(s) := ∫₀^s g(s') ds'`. Then `τ` is absolutely continuous, `τ(0) = 0`, `τ(S) = 𝓛[Γ]`, and
> `τ' = g ≥ 1/σ_max > 0` a.e., so `τ` is strictly increasing and bi-Lipschitz from `[0,S]` onto
> `[0,𝓛]` with `1/σ_max ≤ τ' ≤ 1/σ_min`. Its inverse `s(·)` is Lipschitz with
> `s'(τ) = 1/g(s(τ)) ∈ [σ_min, σ_max]` a.e.
>
> Set `x(τ) := y(s(τ))`. Then `x` is Lipschitz, hence AC, and a.e.
> ```
> ẋ(τ) = y'(s(τ)) · s'(τ) = y'(s(τ)) / g(s(τ)) .
> ```
> By Lemma 2.2.1 with the positive scalar `1/g`,
> ```
> F( x(τ), ẋ(τ) ) = F( y(s), y'(s) ) / g(s) = 1 .
> ```
> `F(x,ẋ) = 1` means `ẋ ∈ ∂B_F(x)` in the radial sense: writing `u := ẋ/|ẋ|`, (2.12) gives
> `|ẋ| = σ(x,u)`, and by compactness of `K` the maximum in Def 2.3 is attained, so
> `σ(x,u)·u ∈ K(x)`, i.e. `ẋ(τ) ∈ K(x(τ))`. Hence `x` is admissible, traverses `Γ`, and has
> duration `𝓛[Γ]`. ∎(c)
>
> **(d)** By (b) no traversal of `Γ` is faster than `𝓛[Γ]`; by (c) that time is attained.
> Minimising over `Γ` on both sides gives the claim. ∎

> **Remark 2.4.1 (What breaks without stationarity — and why this is the core of KAIROS).**
> Drop (H1) and let `F = F(x,t,v)`. Then (2.14) is not defined without also specifying *when*
> each point of `Γ` is visited, and the functional
> ```
> J[x] := ∫₀^T F( x(t), t, ẋ(t) ) dt
> ```
> is **not** invariant under reparameterisation: reparameterising changes the time at which
> each point is reached, hence changes the integrand's second argument. A one-line witness:
> take `F(x,t,v) = f(t)|v|` with `f` non-constant and the constraint `F ≤ 1`, i.e. speed
> `≤ 1/f(t)`. Two traversals of the same `Γ` that differ in how they distribute distance across
> time have different arrival times, and the optimum may require *waiting* (which no
> length functional can express). So the ground-frame problem is an optimal-control problem,
> not a geodesic problem; the value function solves a Hamilton–Jacobi–Bellman equation with a
> genuine `∂_t` term (§3), FIFO can fail, and a single monotone pass is not licensed without
> the causality condition (E4.1).
>
> **Theorem C.1(b) removes exactly this.** In `y = x − w t` the indicatrix is `𝒱_w(y)`, which
> has no `t` argument (Eq C.3), so (H1) holds by construction, Prop 2.4 applies verbatim in
> `y`, and the co-moving arrival-time field is the distance function of a genuine Finsler
> metric. Measured confirmation: the co-moving temporal Lipschitz constant is `L_t ≡ 0.0` to
> the last bit in the A1-exact regime (CORE-THEOREM §7, Test 8.10, regime A).
>
> **Remark 2.4.2 (Relation to the level-set formulation).** Prop 2.4(c)–(d) is the statement
> that the reachable front at time `τ` is the `τ`-sublevel set of the Finsler distance from
> `y_A`. Lolla & Lermusiaux (2014) propagate that front directly with a level-set method; the
> difference is one of solution method, not of formulation, and their reachability front and
> our `T_w` are the same object under (H1)–(H3).

---

## 2.5 Finiteness — ERRATA E9

The draft claimed *"`F(x,t,·)` is finite in every direction iff `0 ∈ int 𝒱`."* **This is
false**, and it is false for the reference vessel: by (2.5), `q_min = 0.15` gives
`V_min = 0.531 V_max > 0`, so the ship cannot stop and `0 ∉ 𝒱` whenever `|c| < V_min`. The
draft's own default configuration was a counterexample to its own lemma. ERRATA E9 splits the
claim into three; they are proved separately below, because they are genuinely different
statements about genuinely different sets.

> **Proposition 2.5 (Finiteness trichotomy; ERRATA E9).** Fix `(x,t)`; write `𝒱 := 𝒱(x,t)`
> (compact), `K := conv 𝒱`, and `S := star(K)` as in (2.8).
>
> **(F1) Directional finiteness.**
> ```
> F(x,t,u) < ∞   ⟺   the open ray ℝ_{>0}·u meets K .                                 (2.16)
> ```
> Taking the gauge of `𝒱` instead of `K` gives the same statement with `K` replaced by `𝒱`,
> because a gauge depends on a set only through its radial function.
>
> **(F2) Uniform finiteness.**
> ```
> sup_{|u|=1} F(x,t,u) < ∞   ⟺   0 ∈ int S .                                         (2.17)
> ```
> If `K` is convex (i.e. under **D4**), the weaker hypothesis "`F(x,t,u) < ∞` for **every** `u`"
> already implies `0 ∈ int S = int conv({0}∪K)`, so for convex `K` the three statements
> *finite in every direction*, *uniformly finite*, and `0 ∈ int S` coincide. Without convexity
> they do not (Rmk 2.5.2).
>
> **(F3) The origin is not in the indicatrix.** If `|c(x,t)| < V_min(x,t)` and the drift point
> is excluded from (2.1) (engine running), then `0 ∉ 𝒱(x,t)`. With the drift point included,
> `0 ∈ 𝒱` iff `c(x,t) = 0`. Neither is required by anything in KAIROS.
>
> **Proof.**
>
> **(F1)** `F(u) < ∞` iff `{τ>0 : u/τ ∈ K} ≠ ∅` iff `∃τ>0 : (1/τ)u ∈ K` iff `∃s>0 : su ∈ K`,
> which is the statement that the open ray from the origin through `u` meets `K`. The last
> sentence follows from Lemma 2.3.1: `F` is determined by `σ`, which is the radial function,
> which is unchanged by any set operation that preserves rays. ∎
>
> **(F2)** *(⇐)* If `0 ∈ int S` there is `ε > 0` with `D(0,ε) ⊆ S`, so `εu ∈ S` for every unit
> `u`, so by (2.8) `σ_S(u) ≥ ε`, hence `F(u) = 1/σ(u) ≤ 1/ε` uniformly.
> *(⇒)* If `sup_u F(u) = M < ∞` then `σ(u) ≥ 1/M > 0` for every `u`, so `(1/M)u ∈ S` for every
> unit `u` (using (2.8) and `σ(u)u ∈ K`), hence `D(0, 1/M) ⊆ S` and `0 ∈ int S`.
>
> *Convex case.* Assume `K` convex and `F(u) < ∞` for every `u`, i.e. `σ(u) > 0` for every `u`.
> Pick three unit vectors at mutual angle `2π/3`, `u_1,u_2,u_3`, and put `s_i := σ(u_i) > 0`,
> so `p_i := s_i u_i ∈ K`. The triangle `T := conv{p_1,p_2,p_3}` is non-degenerate (three
> positive multiples of three directions at `120°` are never collinear). Because `u_1,u_2,u_3`
> positively span `ℝ²`, there are `α_i > 0` with `Σα_i u_i = 0`. Set `λ_i := (α_i/s_i) / Σ_j
> (α_j/s_j) > 0`; then `Σλ_i = 1` and `Σ λ_i p_i = (Σ_j α_j/s_j)^{-1} Σ_i α_i u_i = 0`. So `0`
> has all three barycentric coordinates strictly positive in a non-degenerate triangle, hence
> `0 ∈ int T ⊆ int conv K = int K ⊆ int S`. ∎
>
> **(F3)** Let `v ∈ 𝒱` come from a running engine, `v = V n(θ) + c` with `V ≥ V_min`. The
> reverse triangle inequality gives `|v| ≥ V − |c| ≥ V_min − |c| > 0`, so `v ≠ 0`. The only
> remaining element of (2.1) is the drift point `c`, which is `0` iff `c = 0`. ∎

> **Corollary 2.5.1 (The checkable admissibility condition, and where E1's "iff" is exact).**
> By Lemma 2.1.2, `K = (conv 𝒲) ⊕ c`, so
> ```
> 0 ∈ int K   ⟺   −c(x,t) ∈ int conv 𝒲(x,t) .                                        (2.18)
> ```
> Consequently:
> **(i) (Necessity — holds always.)** `𝒲 ⊆ D(0, V_max)`, so `K ⊆ D(c, V_max)`; if `|c| ≥ V_max`
> then `0 ∉ int D(c,V_max) ⊇ int K`. Hence `0 ∈ int K ⟹ |c| < V_max`.
> **(ii) (Sufficiency under isotropy.)** If `V_max(θ;x,t) ≡ V_max` (calm water, no active bans,
> heading-independent attainable speed) then `conv 𝒲 = D(0,V_max)` and (2.18) reads exactly
> `|c| < V_max`. **This is the case in which ERRATA E1's "iff" is exact.**
> **(iii) (Sufficiency in general.)** If `V_max(θ) ≥ m > 0` for all `θ` then `conv 𝒲 ⊇ D(0,m)`,
> so `|c| < m := min_θ V_max(θ;x,t)` suffices.
> **(iv) (Sharp runtime test, no new machinery.)** `0 ∈ int K ⟺ 𝔥(x,t,p) > 0 for all |p| = 1`,
> where `𝔥` is the support function of Def 2.6. On the `n_θ`-direction table of D2 the
> **rigorous** discrete test is
> ```
> min_{k} 𝔥(x,t,p_k)  >  R · π / n_θ ,        R := max_{v ∈ 𝒱} |v| ≤ V_max + |c| ,   (2.19)
> ```
> because `𝔥` is Lipschitz with constant `R` and adjacent tabulated directions are at distance
> `2 sin(π/n_θ) ≤ π/n_θ`.
>
> **Proof.** (2.18) is (2.3) plus the fact that translation maps interiors to interiors. (i)
> and (ii) are immediate from `𝒲 ⊆ D(0,V_max)` and, under isotropy, `{V_max n(θ)} ⊆ 𝒲`, whose
> convex hull is `D(0,V_max)`. (iii): the curve `{V_max(θ) n(θ)}` winds around the origin at
> radius `≥ m`; by the barycentric argument of Prop 2.5(F2) applied to three of its points at
> `120°`, `0 ∈ int conv 𝒲`, and then `star(conv 𝒲) ⊆ conv 𝒲` gives `D(0,m) ⊆ conv 𝒲`.
> (iv): for a compact convex `K`, `0 ∈ int K` iff every supporting half-plane
> `⟨v,p⟩ ≤ 𝔥(p)` has `𝔥(p) > 0`; and `|𝔥(p) − 𝔥(p')| ≤ R|p−p'|` since
> `𝔥(p) − 𝔥(p') ≤ max_v ⟨v, p−p'⟩ ≤ R|p−p'|` and symmetrically. If `min_k 𝔥(p_k) > Rπ/n_θ` then
> for any unit `p` there is `k` with `|p−p_k| ≤ π/n_θ`, whence `𝔥(p) ≥ 𝔥(p_k) − Rπ/n_θ > 0`. ∎
>
> **This corrects ERRATA E1's `iff` in one direction only.** E1 states
> "`0 ∈ int conv 𝒱 iff |c| < V_max`". The *only if* is unconditionally true (i). The *if*
> requires isotropy (ii); with an active heading ban that removes an entire wedge, `V_max(θ)`
> can be `0` on that wedge, `conv 𝒲` can degenerate, and `|c| < V_max` no longer suffices. An
> implementation must use (2.19), not `norm_c < V_max`, whenever bans are enabled.

> **Remark 2.5.2 (Why (F2) needs a hypothesis: the spiral).** ERRATA E9 claim 2 is stated as
> "`F` finite in every direction iff `0 ∈ int(star-hull 𝒱)`". Without convexity the `⟹` is
> **false**, and the counterexample is compact. Let
> ```
> 𝒱 := { (ψ cos ψ, ψ sin ψ) : ψ ∈ (0, 2π] } ∪ { 0 } .
> ```
> This set is closed (the only accumulation point not of the listed form is `0`, which is
> included) and bounded, hence compact. Every unit direction of angle `ψ ∈ (0,2π]` is met by
> `𝒱` at radius `ψ > 0`, so `σ(u) > 0` and `F(u) < ∞` in **every** direction. But
> `inf_u σ(u) = 0` (as `ψ ↓ 0`), so `0 ∉ int star(𝒱)` and `sup_u F(u) = ∞`. The correct general
> statement is therefore (2.17): **uniform** finiteness, not pointwise. Under D4 the
> distinction evaporates (Prop 2.5(F2), convex case), which is why E9's phrasing is harmless in
> the KAIROS pipeline — but a port that skips D4 and takes gauges of the raw `𝒱` will hit it.

> **Remark 2.5.3 (Physical reading of (F3), and what it costs).** A ship with a minimum stable
> engine load genuinely **cannot hold station**: `0 ∉ 𝒱` is the truth, not a modelling defect.
> The "can the ship hold station" intuition is a statement about `conv 𝒱`, and D4 is what lets
> the solver treat the ship as if it could — by alternating headings so that the *average*
> ground velocity is zero. That relaxation is exactly the hole of Cor 1.11.0 being filled, the
> realising manoeuvre is intermittent engine operation, and its cost under a minimum steering
> dwell `τ_d` is what **Thm 2.11** bounds. This is D4 earning its keep, and it is worth saying
> out loud rather than hiding in a hull operator.
>
> **What breaks without each hypothesis of Prop 2.5.**
> - Drop compactness of `𝒱`: the `max` in Def 2.3 becomes a `sup` that may not be attained,
>   Lemma 2.2.1b fails (`B_F` is no longer `star(K)`), and Prop 2.4(c) loses its realising
>   control — the optimal trajectory exists only as a limit.
> - Drop D4: (F2) weakens to (2.17) only, and Prop 2.2.2 can fail (Rmk 2.2.4).
> - Drop `V_min > 0` (allow the engine to stop): (F3) becomes vacuous, `0 ∈ 𝒱`, and the hole of
>   Cor 1.11.0 disappears — Thm 2.11's bound is then *not* needed for station-keeping, only for
>   the seakeeping notches.

---

## 2.6 The support function

> **Definition 2.6 (Support function).** For `p ∈ ℝ²`,
> ```
> 𝔥(x,t,p) := max_{v ∈ 𝒱(x,t)} ⟨v, p⟩ .                                              (2.20)
> ```
> **Units:** `[m/s]·[units of p]`. The maximum is attained (`𝒱` compact). This realises the
> `support` primitive of `CONTRACT §4`.

> **Lemma 2.6.1 (Basic properties; the hull is invisible).**
> **(i)** `𝔥(x,t,·)` is positively 1-homogeneous, convex, and finite on all of `ℝ²`.
> **(ii)** `𝔥_𝒱 = 𝔥_{conv 𝒱}`.
> **(iii)** `𝔥_{A ⊕ B} = 𝔥_A + 𝔥_B` and `𝔥_{λA} = λ𝔥_A` for `λ ≥ 0`; in particular
> `𝔥_{𝒱 ⊕ {p₀}}(p) = 𝔥_𝒱(p) + ⟨p₀,p⟩`.
> **(iv)** For the Randers set `K = D(c, V_s)`,
> ```
> 𝔥(p) = ⟨c,p⟩ + V_s |p| .                                                           (2.21)
> ```
>
> **Proof.** (i) Homogeneity: `max_v ⟨v,sp⟩ = s max_v ⟨v,p⟩` for `s > 0`, and `𝔥(0) = 0`.
> Convexity: `𝔥` is a pointwise maximum of the linear functions `p ↦ ⟨v,p⟩`, and a pointwise
> supremum of convex functions is convex. Finiteness: `|𝔥(p)| ≤ R|p|` with `R = max_{v∈𝒱}|v|`.
> (ii) `𝒱 ⊆ conv 𝒱` gives `≤`. For `≥`: any `z ∈ conv 𝒱` is `Σλ_i v_i` with `v_i ∈ 𝒱`,
> `λ_i ≥ 0`, `Σλ_i = 1`, and `⟨z,p⟩ = Σλ_i⟨v_i,p⟩ ≤ max_i ⟨v_i,p⟩ ≤ 𝔥_𝒱(p)`; take the max over
> `z`. (iii) `max_{a∈A,b∈B} ⟨a+b,p⟩ = max_a⟨a,p⟩ + max_b⟨b,p⟩` since the objective separates;
> the singleton case is `B = {p₀}`. (iv) By (iii) with `A = D(0,V_s)`, `B = {c}`, and
> `max_{|d| ≤ V_s} ⟨d,p⟩ = V_s|p|` attained at `d = V_s p/|p|` (Cauchy–Schwarz, equality iff
> `d ∥ p`). ∎
>
> **(ii) is the formal content of Remark 2.2.5 and of D4:** the Hamiltonian of §3 is built from
> `𝔥`, so no PDE in KAIROS can distinguish `𝒱` from `conv 𝒱`. Note also (iii) with
> `p₀ = −w`: **the co-moving shift changes `𝔥` by a rank-one term** (Prop 2.10(vii)).

---

## 2.7 Support-function tabulation (design decision D2)

> **Proposition 2.7 (Support-function tabulation is exact for convex indicatrices).**
> Let `K` be compact convex with `0 ∈ int K`, `𝔥` its support function, and let
> `p_k := n(2πk/n_θ)`, `k = 0,…,n_θ−1`, be uniformly spaced unit directions.
>
> **(i) (Exact duality.)**
> ```
> F(v) = max_{|p|=1, ⟨v,p⟩>0} ⟨v,p⟩ / 𝔥(p) ,      σ(u) = min_{|p|=1, ⟨u,p⟩>0} 𝔥(p)/⟨u,p⟩ .  (2.22)
> ```
> **(ii) (One-sided polygonal recovery.)** Define the tabulated recovery
> ```
> σ̂(u) := min { 𝔥(p_k)/⟨u,p_k⟩ : k with ⟨u,p_k⟩ > 0 } .                              (2.23)
> ```
> Then `σ̂` is the radial function of the circumscribed polygon
> `P := { v : ⟨v,p_k⟩ ≤ 𝔥(p_k), ∀k }`, and `K ⊆ P`; hence
> ```
> σ̂(u) ≥ σ(u)   for every u ,   equivalently   F̂(u) ≤ F(u) .                        (2.24)
> ```
> **The tabulation error is signed and optimistic**, so a solve run on `σ̂` returns a **lower
> bound** on arrival time — which is exactly the direction Cor 4.12's certificate requires.
> **(iii) (`O(log n_θ)` evaluation.)** The sequence `k ↦ 𝔥(p_k)/⟨u,p_k⟩` restricted to the
> contiguous cyclic block `A(u) := {k : ⟨u,p_k⟩ > 0}` is **unimodal**, and the sign of its
> forward difference is non-decreasing across the block. Hence a binary search for the first
> index with a non-negative forward difference finds the minimiser in
> `⌈log₂ |A(u)|⌉ + O(1)` table reads, each `O(1)`.
> **(iv) (Interpolation in forecast time is legitimate.)** For `λ ∈ [0,1]`,
> `λ𝔥_{K₀} + (1−λ)𝔥_{K₁} = 𝔥_{λK₀ ⊕ (1−λ)K₁}`, so a linear interpolant of tabulated support
> values is itself the support function of a compact convex set. The recovered `σ̂` is therefore
> always the radial function of a legitimate indicatrix, never an artefact.
>
> **Proof.**
>
> **(i)** For compact convex `K`, the supporting-hyperplane (bipolar) theorem gives
> `K = { v : ⟨v,p⟩ ≤ 𝔥(p) for all p }`. Hence for `v ≠ 0`,
> ```
> F(v) = inf{ τ>0 : v/τ ∈ K } = inf{ τ>0 : ⟨v,p⟩ ≤ τ 𝔥(p) ∀p } .
> ```
> Because `0 ∈ int K`, `𝔥(p) > 0` for every `p ≠ 0` (there is `ε>0` with `εp/|p| ∈ K`, so
> `𝔥(p) ≥ ε|p|`). The constraint for a given `p` is therefore `τ ≥ ⟨v,p⟩/𝔥(p)`, vacuous when
> `⟨v,p⟩ ≤ 0`. Taking the tightest constraint,
> `F(v) = sup_{p≠0} ⟨v,p⟩/𝔥(p) = max_{|p|=1, ⟨v,p⟩>0} ⟨v,p⟩/𝔥(p)`, the restriction to `|p|=1`
> being legitimate because both numerator and denominator are 1-homogeneous in `p`, and the
> `sup` being attained by continuity on the compact arc `{|p|=1, ⟨v,p⟩ ≥ δ}` for small `δ>0`
> (the objective tends to `0` as `⟨v,p⟩ → 0⁺` since `𝔥` is bounded below on the unit circle).
> The `σ` form is the reciprocal, by Lemma 2.3.1.
>
> **(ii)** `ρ_P(u) = max{ s ≥ 0 : s⟨u,p_k⟩ ≤ 𝔥(p_k) ∀k }`. Constraints with `⟨u,p_k⟩ ≤ 0` are
> satisfied for all `s ≥ 0` because `𝔥(p_k) > 0`. The remaining constraints give
> `s ≤ 𝔥(p_k)/⟨u,p_k⟩`, so `ρ_P(u) = min_{k ∈ A(u)} 𝔥(p_k)/⟨u,p_k⟩ = σ̂(u)`. `K ⊆ P` because
> every `v ∈ K` satisfies `⟨v,p_k⟩ ≤ 𝔥(p_k)` by definition of `𝔥`. Radial functions are
> monotone under inclusion, so `σ̂ = ρ_P ≥ ρ_K = σ`. ∎
>
> **(iii)** Fix `u` and rotate coordinates so `u = (1,0)`. For `p = (cos φ, sin φ)` with
> `|φ| < π/2` we have `⟨u,p⟩ = cos φ > 0`, and by 1-homogeneity of `𝔥`,
> ```
> 𝔥(p)/cos φ  =  𝔥( p/cos φ )  =  𝔥( (1, tan φ) )  =:  G( tan φ ) ,                  (2.25)
> ```
> where `G(ζ) := 𝔥((1,ζ))`. By Lemma 2.6.1(i) `𝔥` is convex on `ℝ²`; the restriction of a
> convex function to the line `{(1,ζ)}` is convex, so **`G` is convex on `ℝ`**. The map
> `φ ↦ tan φ` is a strictly increasing bijection `(−π/2,π/2) → ℝ`, so the tabulated arguments
> `ζ_k := tan φ_k` are strictly increasing in `k` across the block `A(u)`. For a convex `G` the
> divided differences `(G(ζ_{k+1}) − G(ζ_k))/(ζ_{k+1} − ζ_k)` are non-decreasing in `k`; since
> `ζ_{k+1} − ζ_k > 0`, the **signs** of the plain forward differences
> `Δ_k := G(ζ_{k+1}) − G(ζ_k)` are non-decreasing, i.e. the sign pattern across the block is
> `(−,…,−, 0,…,0, +,…,+)`. Binary search for the least `k` with `Δ_k ≥ 0` therefore locates the
> minimum, using `⌈log₂|A(u)|⌉` difference evaluations, each two table reads and one compare.
> `|A(u)| ∈ {n_θ/2 − 1, n_θ/2, n_θ/2 + 1}` for uniform `p_k`. ∎
>
> **Remark.** Ternary search is the obvious alternative but is unsafe on the flat runs that
> arise when `∂K` has a facet (which it does, for any polygonal or banned-wedge indicatrix):
> a ternary step cannot decide which side of a plateau the minimum lies on. The convex-difference
> binary search above has no such failure mode. **Use the difference search, not ternary search.**
>
> **(iv)** By Lemma 2.6.1(iii), `λ𝔥_{K₀} = 𝔥_{λK₀}` and `𝔥_{λK₀} + 𝔥_{(1−λ)K₁} =
> 𝔥_{λK₀ ⊕ (1−λ)K₁}`; the Minkowski combination of compact convex sets is compact convex. ∎

> **Corollary 2.7.1 (Interpolation error bound for the Randers indicatrix).**
> Let `K = D(c, V_s)` be tabulated exactly on `n_θ` uniform directions. Then
> ```
> D(c, V_s)  ⊆  P  ⊆  D( c , V_s · sec(π/n_θ) )                                       (2.26)
> ```
> and, writing `β := |c_⊥|/V_s ∈ [0,1]` for the direction `u` under test,
> ```
> 0 ≤ σ̂(u) − σ(u) ≤ V_s · [ √(sec²(π/n_θ) − β²) − √(1 − β²) ]
>                 = V_s · tan²(π/n_θ) / [ √(sec²(π/n_θ) − β²) + √(1−β²) ] .           (2.27)
> ```
> **Two regimes, and they have different orders:**
> ```
> β = 0  (drift along track):     error ≤ V_s (sec(π/n_θ) − 1)  =  O(n_θ^{-2})
> β → 1  (grazing, near the T8 boundary):  error → V_s tan(π/n_θ) =  O(n_θ^{-1})      (2.28)
> ```
> On a restricted set `{ |c_⊥| ≤ κ V_s }` with `κ < 1` the uniform bound is
> `V_s tan²(π/n_θ) / (2√(1−κ²)) = O(n_θ^{-2})`.
>
> **Proof.** `P − c` is the intersection of the half-planes `⟨d, p_k⟩ ≤ V_s` by (2.21) and
> Lemma 2.6.1(iii), i.e. the regular `n_θ`-gon circumscribing `D(0,V_s)`: inradius `V_s`,
> circumradius `V_s sec(π/n_θ)`. That is (2.26). Radial functions from the *origin* then satisfy
> `σ(u) = c_∥ + √(V_s² − c_⊥²) ≤ σ̂(u) ≤ c_∥ + √(V_s² sec² − c_⊥²)` — the outer inequality
> because `P ⊆ D(c, V_s sec)` and the radial function of `D(c,r)` in direction `u` is
> `c_∥ + √(r² − c_⊥²)` (derived in §2.8, Eq (2.33)). Subtracting gives the first line of (2.27);
> the second is the algebraic identity `√A − √B = (A−B)/(√A+√B)` with
> `A − B = V_s²(sec² − 1) = V_s² tan²`. The first line of (2.28) is (2.27) at `β = 0`; the
> second is (2.27) at `β = 1`, where `√(1−β²) = 0` and the bound is `V_s√(sec²−1) = V_s tan`.
> The restricted bound uses `√(sec²−β²) ≥ √(1−β²) ≥ √(1−κ²)`. ∎
>
> **This refines the `O(n_θ^{-2})` claim in the reference implementation's `SupportTable`
> docstring.** `O(n_θ^{-2})` is correct for the radial error measured *from the centre of the
> disc*, and for directions bounded away from the cross-track feasibility boundary. It is not
> correct uniformly: as `|c_⊥| → V_s` the ray grazes the circle tangentially and the polygonal
> error is first order, `V_s tan(π/n_θ)`. An implementation that needs a uniform guarantee must
> either exclude the grazing cone or evaluate those directions from the metric directly.
>
> **Numbers (derived here; `n_θ = 72` per D2, `V_s = 7.2 m/s` per handbook G2).**
> ```
> π/72 = 0.043 633 231 3 rad
> sec(π/72) − 1 = 9.526 79 × 10⁻⁴        tan(π/72) = 4.366 09 × 10⁻²
> V_s(sec−1)    = 6.859 × 10⁻³ m/s       V_s tan   = 3.144 × 10⁻¹ m/s
> restricted bound at κ = 0.9: V_s tan²/(2√(1−0.81)) = 7.2·1.9063e-3/0.87178 = 1.574 × 10⁻² m/s
> ```
> **Justification of `n_θ = 72` (D2's magic number, now not magic).** The along-track relative
> error is `sec(π/72) − 1 = 9.53 × 10⁻⁴`, i.e. **0.095 %**. The fixed-stencil metrication error
> floor measured in CORE-THEOREM §4 is **0.15–0.98 %** and does not vanish under refinement.
> The tabulation is therefore an order of magnitude below the binding error and is not the
> limiting approximation; halving it by doubling `n_θ` to 144 would double the table's memory
> for no measurable gain. **This is the argument for 72, and it is the only one.**
>
> **Measured cross-check** (reference implementation self-test, `metric.py`, default bulker,
> `H_s = 3 m`, `n_θ = 72`): max relative excess of `σ̂` over `σ` is `1.1×10⁻³` with bans off
> (consistent with the derived `9.53×10⁻⁴` plus the grazing contribution of (2.28)), and
> `3.5×10⁻¹` inside a parametric-roll notch with bans on, median `2.9×10⁻⁴`. **The 35 % is not
> tabulation error**: it is the D4 chattering gap (Rmk 2.2.5), localised exactly where a heading
> is banned, and it is what Thm 2.11 bounds. A test asserting `table == metric` with bans on is
> testing the wrong thing.

**Abstract data type (D7).**

```
SUPPORT TABLE
  state    : dense array  h[n_time][n_lat][n_lon][n_theta] of f64,
             direction axis LAST (one cell's indicatrix is one contiguous run)
  build    : O(n_time · n_lat · n_lon · n_theta) evaluations of `support`; embarrassingly
             parallel over cells
  frame(i,j,t) : O(n_theta) copy or O(1) view; linear interpolation in t, CLAMPED at both
             ends (never extrapolated — past the horizon, persist the last frame, §6)
  sigma_hat(i,j,t,u) : O(log n_theta) by Prop 2.7(iii)
  memory   : 8 · n_time · n_lat · n_lon · n_theta bytes
```

Worked memory figure, derived: the end-to-end configuration of CORE-THEOREM §8.2 has 29 529
nodes at `0.25°`; with `n_θ = 72` that is `29 529 × 72 × 8 = 17 008 704 B = 16.2 MiB` **per
forecast frame**, so 24 frames cost `389 MiB`.

> **Consequence of the core (Prop 2.10 forward reference).** In the co-moving frame the field
> is stationary, so `n_time = 1` and the table collapses to a single frame — a **24×** memory
> reduction on that configuration. This is a second, unadvertised benefit of Thm C.1, of the
> same kind as the elimination of temporal discretisation error: it falls out of stationarity
> rather than being designed for.

---

## 2.8 The Randers closed form, and strong drift (ERRATA E1)

**Setting (R).** The classical Zermelo (1931) case: constant through-water speed `V_s`,
heading-independent, no active bans, throttle collapsed to `q = 1` (legitimate for the time
objective by Prop 1.11(c)). Then `𝒲 = { V_s n(θ) } ∪ {0}`, `conv 𝒲 = D(0,V_s)`, and by
Lemma 2.1.2
```
K(x,t) = conv 𝒱(x,t) = D( c(x,t), V_s ) .                                            (2.29)
```
This is the case in which everything is exact and against which every implementation is
validated (handbook G2, G3, G4).

> **Proposition 2.8 (The Randers gauge in closed form, with its stable branches).**
> Fix `c ∈ ℝ²`, `V_s > 0`, and `v ≠ 0`. Write
> ```
> D := ⟨v,v⟩ ,   a := ⟨v,c⟩ ,   λ := V_s² − |c|² ,   Δ := a² + λ D .                  (2.30)
> ```
> Then `F(v) = min { τ > 0 : φ(τ) ≥ 0 }` where `φ(τ) := λτ² + 2aτ − D`, and:
> **(i)** a positive root exists **iff** `a + √Δ > 0` with `Δ ≥ 0` (equivalently: `λ > 0`, or
> `λ ≤ 0 ∧ a > 0 ∧ Δ ≥ 0`);
> **(ii)** when it exists,
> ```
> F(v) = ( √Δ − a ) / λ                       (direct form)                           (2.31)
>      = D / ( a + √Δ )                       (conjugate form)                        (2.32)
> ```
> the two being algebraically identical;
> **(iii)** for `|v| = 1`, decomposing `c = c_∥ u + c_⊥ u^⊥` with `u = v`,
> ```
> Δ = V_s² − c_⊥²   and   σ(u) = 1/F(u) = c_∥ + √( V_s² − c_⊥² ) .                    (2.33)
> ```
>
> **Proof.** `v/τ ∈ D(c,V_s)` iff `|v/τ − c| ≤ V_s` iff (multiplying by `τ > 0`)
> `|v − τc| ≤ τV_s` iff `|v|² − 2τ⟨v,c⟩ + τ²|c|² ≤ τ²V_s²` iff `φ(τ) ≥ 0`. Since `φ(0) = −D < 0`,
> the smallest admissible `τ` is the smallest positive root of `φ`. The roots of `φ` are
> `(−a ± √Δ)/λ` when `λ ≠ 0`.
>
> *Case `λ > 0`.* `Δ = a² + λD > 0`, `φ` is an upward parabola with `φ(0) < 0`, so it has
> exactly one positive root, `τ_+ = (−a + √Δ)/λ`, giving (2.31).
>
> *Case `λ = 0`.* `φ(τ) = 2aτ − D`. If `a > 0` the root is `D/(2a)`, which is (2.32) with
> `√Δ = |a| = a`. If `a ≤ 0` there is no positive root; `F = +∞`. Note (2.31) is undefined here
> and (2.32) is not — a first reason to prefer (2.32) when `a > 0`.
>
> *Case `λ < 0`.* Write `λ = −|λ|`. Real roots require `Δ = a² − |λ|D ≥ 0`. The roots are
> `(a ∓ √Δ)/|λ|`. Their product is `D/|λ| > 0` and their sum is `2a/|λ|`, so both are positive
> iff `a > 0` and both are negative iff `a < 0`. Hence a positive root exists iff `a > 0` and
> `Δ ≥ 0`, and the **smallest** positive root is `(a − √Δ)/|λ| = (√Δ − a)/λ`, again (2.31).
>
> Collecting the three cases gives (i), and (2.31) holds whenever a positive root exists.
>
> *(2.31) ⟺ (2.32).* Multiply numerator and denominator of (2.31) by `(√Δ + a)`:
> ```
> (√Δ − a)(√Δ + a) / [λ(√Δ + a)] = (Δ − a²) / [λ(√Δ + a)] = λD / [λ(√Δ+a)] = D/(a+√Δ) ,
> ```
> legitimate whenever `λ ≠ 0` and `a + √Δ ≠ 0`; at `λ = 0, a > 0` the right side is the correct
> root as shown above, so (2.32) is the form valid on the whole existence region.
>
> *(iii)* With `|u| = 1`, `D = 1`, `a = ⟨u,c⟩ = c_∥`, and `|c|² = c_∥² + c_⊥²`, so
> `Δ = c_∥² + V_s² − c_∥² − c_⊥² = V_s² − c_⊥²`. Then `F(u) = 1/(c_∥ + √(V_s²−c_⊥²))` from
> (2.32) and (2.33) follows from Lemma 2.3.1. ∎

**The Randers presentation `F = α + β` (Randers 1941; Bao–Robles–Shen 2004).** Rearranging
(2.31),
```
F(v) = √( |v|²/λ + ⟨v,c⟩²/λ² ) − ⟨v,c⟩/λ  =  α(v) + β(v)                             (2.34)
α(v) = √( a_{ij} v^i v^j ) ,  a_{ij} = δ_{ij}/λ + c_i c_j/λ² ;   β(v) = b_i v^i , b_i = −c_i/λ.
```
The classical admissibility condition for a Randers metric is `|b|_α < 1`. Computing it: with
`a_{ij} = λ^{-1}(δ_{ij} + c_ic_j/λ)`, the Sherman–Morrison inverse is
`a^{ij} = λ(δ_{ij} − c_ic_j/(λ+|c|²)) = λ(δ_{ij} − c_ic_j/V_s²)` since `λ + |c|² = V_s²`. Hence
```
|b|²_α = a^{ij} b_i b_j = λ^{-2}·λ ( |c|² − |c|⁴/V_s² ) = |c|²(1 − |c|²/V_s²)/λ = |c|²/V_s² ,
```
so
```
|b|_α = |c| / V_s < 1   ⟺   |c| < V_s .                                              (2.35)
```
**The Finsler-geometric admissibility condition and the physical one are the same condition.**
That identity is Bao–Robles–Shen's; it is reproduced here in full because §2.10 transports it
to `c ← c₀ − w` and because it is the cleanest available statement of why `|c| = V_s` is a
genuine geometric degeneration and not a numerical inconvenience.

### 2.8.1 The normative evaluation procedure

Language-agnostic, `O(1)`, one square root, one division, four multiplications. **This is the
form an implementation must use.** The branch on `sign(a)` is not an optimisation.

```
GAUGE(v, c, V_max) -> f64 in (0, +inf]        # Randers case, Eq (2.30)-(2.32)
 1  D  <- v.x*v.x + v.y*v.y
 2  if D == 0 : return 0
 3  a  <- v.x*c.x + v.y*c.y
 4  lam <- V_max*V_max - (c.x*c.x + c.y*c.y)
 5  disc <- a*a + lam*D
 6  if a > 0 :
 7      if disc < 0 : return +INF            # outside the reachable cone (Cor 2.8.1)
 8      return D / (a + sqrt(disc))          # conjugate branch: stable, never forms 1/lam
 9  else :
10      if lam <= 0 : return +INF            # no positive root exists  (golden vector T7)
11      return (sqrt(disc) - a) / lam        # direct branch: numerator adds two positives
12  POSTCONDITION: result > 0 and (isfinite(result) or result == +INF).  ASSERT IT.
```

**Why line 6's branch (handbook G3).** For `a > 0`, `√Δ = √(a² + λD) → |a| = a` as `λ → 0⁺`,
so (2.31) subtracts two nearly equal positive numbers. Round-off analysis: `√Δ` carries
absolute error `≈ u·√Δ ≈ u·a` (`u` = unit round-off, `1.1×10⁻¹⁶` in IEEE double), while the
true difference is `√Δ − a = λD/(√Δ + a) ≈ λD/(2a)`. The relative error of the computed
difference is therefore
```
relerr ≈  u · a · 2a / (λ D)  =  2u · a²/(λD) ,     digits lost ≈ log₁₀( 2a²/(λD) ) .  (2.36)
```
For a unit direction along a following current, `a²/(λD) = μ²/(1−μ²)` with `μ := |c|/V_s`
(independent of `|v|`, as homogeneity requires). Evaluated:

| `μ = \|c\|/V_s` | `2μ²/(1−μ²)` | digits lost (upper estimate) |
|---|---|---|
| 0.9 | 8.53 | 0.93 |
| 0.99 | 98.5 | 1.99 |
| 0.999 | 999 | 3.00 |
| `1 − 10⁻⁸` | `1.0 × 10⁸` | 8.0 |

> **Correction of record.** The claim that the naive form "loses 8 digits at `|c|/V_s = 0.9`"
> is **wrong by roughly seven digits**, and the reference implementation's own self-test says
> so in as many words ("at the `|c|/V_s = 0.9` case specifically it is well under one digit,
> NOT eight — the cancellation only becomes severe as `lam -> 0`"). Handbook G3 itself does not
> state a digit count at 0.9; it states, correctly, that the loss grows like `⟨v,c⟩/λ`. The
> derived table above is the statement to use. **The branch is still mandatory** — the failure
> is unbounded as `μ → 1`, which is precisely the strong-current regime in which routing
> decisions matter — but it must be justified by (2.36), not by an inflated number.

**Why the `a > 0` branch is doubly safe.** Line 8 never forms `1/λ`, so it is immune to a
second, independent cancellation: the one *inside* `λ = V_s² − |c|²`. Line 11 is not immune to
that; but there, no branch can be, because the quantity is **intrinsically ill-conditioned**.
For a head-on current the relative condition number of `σ` with respect to `|c|` is
```
κ = | (|c|/σ) ∂σ/∂|c| | = |c| / (V_s − |c|) ,                                        (2.37)
```
which is `6.84/0.36 = 19` at golden vector T6 (`μ = 0.95`), i.e. `1.3` digits of unavoidable
loss from the *data*, not from the algorithm. State it; do not pretend a rearrangement removes
it. Note `κ ≈ Υ_loc/2` for `μ → 1` (Def 2.9), so the ill-conditioning of `σ` and the
anisotropy that drives the stencil radius are the same phenomenon.

### 2.8.2 Verification against golden vectors T1–T8

All eight cases of handbook `01-golden-vectors.md` §G2, `V_s = 7.2 m/s`, run through `GAUGE`
above. **The `σ` and `F` columns are the handbook's exact reference values, quoted verbatim;
the intermediate columns are computed here so the branch taken can be checked by hand.**

| # | `c_∥` | `\|c_⊥\|` | `a` | `λ` | `Δ` | branch | `σ` [m/s] | `F` [s/m] |
|---|---|---|---|---|---|---|---|---|
| T1 | 0 | 0 | 0 | 51.84 | 51.84 | 11 direct | **7.2** (exact) | **0.138 888 888 888 889** |
| T2 | +1.5 | 0 | 1.5 | 49.59 | 51.84 | 8 conjugate | **8.7** (exact) | **0.114 942 528 735 632** |
| T3 | −1.5 | 0 | −1.5 | 49.59 | 51.84 | 11 direct | **5.7** (exact) | **0.175 438 596 491 228** |
| T4 | 0 | 1.5 | 0 | 49.59 | 49.59 | 11 direct | **7.042 016 756 583 30** | **0.142 004 774 280 768** |
| T5 | +1.299 038 105 676 66 | 0.75 | 1.299 038… | 49.59 | 51.2775 | 8 conjugate | **8.459 869 063 044 66** | **0.118 205 139 175 062** |
| T6 | −6.84 | 0 | −6.84 | 5.0544 | 51.84 | 11 direct | **0.36** (exact) | **2.777 777 777 777 78** |
| T7 | −8.0 | 0 | −8.0 | −12.16 | 51.84 | **10 → +∞** | **blocked** (σ ≤ 0) | **+∞** |
| T8 | 0 | 7.5 | 0 | −4.41 | −4.41 | **10 → +∞** | **infeasible** | **+∞** |

**Arithmetic, checkable by hand.**
- T1: direct, `(√51.84 − 0)/51.84 = 7.2/51.84 = 0.138 888 …` ✓
- T2: conjugate, `1/(1.5 + 7.2) = 1/8.7` ✓ — note the conjugate branch never forms `λ`.
- T3: direct, `(7.2 + 1.5)/49.59 = 8.7/49.59`, and `49.59 = 5.7 × 8.7`, so `F = 1/5.7` ✓.
- T4: `Δ = V_s² − c_⊥² = 51.84 − 2.25 = 49.59`; `√49.59 = 7.042 016 756 583 301 4` ✓,
  `F = 7.042 016 …/49.59` ✓.
- T5: `a = 1.5 cos 30° = 1.299 038 105 676 658`, `a² = 1.6875` exactly,
  `Δ = 1.6875 + 49.59 = 51.2775 = 51.84 − 0.5625 = V_s² − c_⊥²` ✓ (the identity of (2.33)
  holding to the last digit is itself a check), `√Δ = 7.160 830 957 …`,
  `σ = 7.160 830 957 + 1.299 038 106 = 8.459 869 063 044 66` ✓.
- T6: direct, `(7.2 + 6.84)/5.0544 = 14.04/5.0544 = 2.7̄` ✓; `μ = 6.84/7.2 = 0.95`.
- T7: `λ = 51.84 − 64 = −12.16 < 0` and `a = −8 ≤ 0`, so line 10 fires: `+∞`.
- T8: `a = 0`, so the `else` branch; `λ = 51.84 − 56.25 = −4.41 ≤ 0`, line 10: `+∞`. The naive
  single-branch form would evaluate `√(−4.41)` and return **NaN**.

**Handbook G3 stability case, also verified through `GAUGE`.** `V_s = 7.2`, `c = 6.48`
(`μ = 0.9`), `v = (1,0)`: `a = 6.48 > 0`, `Δ = 41.9904 + 9.8496 = 51.84`, `√Δ = 7.2`, line 8
returns `1/(6.48 + 7.2) = 1/13.68 = 0.073 099 415 204 678 362…`, matching the handbook exactly,
with `σ = 13.68 = 7.2 + 6.48` ✓.

### 2.8.3 Strong drift: the reachable cone (ERRATA E1)

> **The condition is `|c| ≥ V_max` (THROUGH WATER), not `|c| ≥ σ_max`.** ERRATA E1: `σ_max` is
> speed made good over ground, and in the drift direction `σ ≥ V_max + |c| > |c|` always, so
> `|c| ≥ σ_max` is **identically false for every `V_max > 0`**. An implementation coding
> `if (norm_c >= sigma_max)` gets a branch that never fires — silently running the fast path in
> exactly the cells where the theory forbids it. Substitute `V_max` for `σ_max` everywhere the
> comparison is against a drift magnitude.

> **Corollary 2.8.1 (Reachable cone; Kropina degeneration).** In setting (R) with
> `|c| ≥ V_max`:
> **(i)** `0 ∉ D(c,V_max) = K`, so no direction is reachable in the half-plane opposite `c`;
> **(ii)** the set of reachable directions is the closed cone about `c` of half-angle
> ```
> α_reach = arcsin( V_max / |c| )  ∈ (0, π/2] ,                                       (2.38)
> ```
> and `F(x,t,u) = +∞` for every `u` outside it;
> **(iii)** the equivalent per-direction test is `|c_⊥| ≤ V_max` **and** `c_∥ > 0`, which is
> exactly `Δ ≥ 0 ∧ a > 0` — lines 6–7 of `GAUGE`;
> **(iv)** at `|c| = V_max` exactly, `α_reach = π/2` but the extreme rays touch `∂K` only at the
> origin, i.e. at `τ = 0`, which is not a positive root. Per E1, **treat `|c| = V_max` as
> excluded (`F = +∞`) for strict safety.**
>
> **Proof.** *(i)* `|0 − c| = |c| ≥ V_max`, so `0 ∉ int K`, and `0 ∈ ∂K` only in the boundary
> case (iv).
> *(ii)* Let `ψ := ∠(u,c) ∈ [0,π]`. The line `ℝu` meets `D(c,V_max)` iff the perpendicular
> distance `|c| sin ψ ≤ V_max`, i.e. `sin ψ ≤ V_max/|c| ≤ 1`. Because `|c| ≥ V_max`, this forces
> `ψ ≤ arcsin(V_max/|c|) ≤ π/2`, hence `cos ψ ≥ 0` and the intersection points are at
> non-negative parameter along the ray; they are strictly positive unless the tangency is at the
> origin, which is case (iv). Conversely if `sin ψ > V_max/|c|` the line misses the disc entirely
> and `F(u) = +∞` by (F1).
> *(iii)* `c_⊥ = |c| sin ψ` and `c_∥ = |c| cos ψ`, so `|c_⊥| ≤ V_max ⟺ sin ψ ≤ V_max/|c|`, and
> by (2.33) `Δ = V_max² − c_⊥² ≥ 0` is the same test; `c_∥ > 0 ⟺ a > 0` excludes the mirror cone
> about `−c`, which meets the *line* but not the *ray*.
> *(iv)* At `|c| = V_max` and `ψ = π/2`, `Δ = V_max² − c_⊥² = 0` and `a = 0`, so `GAUGE` takes
> the `else` branch with `λ = 0`, line 10, `+∞`. ∎
>
> **Worked values (derived).** `V_s = 3.0 m/s` (slow bulker) in a `4.0 m/s` Agulhas core:
> `α_reach = arcsin(0.75) = 0.848 062 rad = 48.590 4°`. `V_s = 7.2` against `|c| = 8.0` (golden
> vector T7's field): `α_reach = arcsin(0.9) = 1.119 770 rad = 64.158 1°`.
>
> **The correct answer really is "you cannot escape this storm."** `F = +∞` outside the cone is
> not a numerical failure to be smoothed away; it is the physically true statement that the
> vessel is being set down-drift faster than it can make way. §4 must implement (iii) as an
> excluded-direction test — two comparisons — and must not attempt to invert `σ = 0`.

> **Warning 2.8.2 (golden vector T7: the closed form returns a NEGATIVE cost).**
> The textbook single-branch form (2.31), evaluated without the existence test of
> Prop 2.8(i), at `V_s = 7.2`, `c` head-on with `|c| = 8.0`, `v = u` against the current:
> ```
> a = −8.0 ,  λ = 51.84 − 64 = −12.16 ,  Δ = 64 − 12.16 = 51.84 ,  √Δ = 7.2
> F = ( 7.2 − (−8.0) ) / (−12.16) = 15.2 / (−12.16) = −1.25            ← NEGATIVE
> ```
> **It does not raise. It does not return NaN. It returns a plausible finite number with the
> wrong sign.** Dropped into a label-setting shortest-path solver this creates negative edge
> costs, hence negative cycles: the sweep either fails to terminate, or terminates having
> "finalised" a node whose value is later lowered, or returns an arrival time in the past. This
> is failure mode S1 of the debugging playbook, cause 1, and it is the single most destructive
> bug available in this codebase.
>
> **Guard `λ` before dividing. Every time. No exceptions.** `GAUGE` line 10 is that guard, and
> line 12's postcondition assertion is the tripwire that catches a port which omits it. Both T7
> and T8 must be *reachable in the test suite*, not merely defended against in code (handbook
> G2).

---

## 2.9 Anisotropy

> **Definition 2.9 (Local and global anisotropy).**
> ```
> Υ_loc(x,t) := σ_max(x,t) / σ_min(x,t) = F_max(x,t) / F_min(x,t)  ∈ [1, +∞]         (2.39)
> Υ          := sup { Υ_loc(x,t) : x ∈ Ω , t ∈ [t₀, t₀+H_fc] } .                      (2.40)
> ```
> `Υ_loc = +∞` exactly when `σ_min = 0`, i.e. when some direction is excluded (Cor 2.8.1).

> **Proposition 2.9.1 (Closed form, pure-current case).** In setting (R) with `|c| < V_s`,
> ```
> σ_max = V_s + |c|   (attained dead down-drift) ,   σ_min = V_s − |c|   (dead up-drift),
> Υ_loc = ( V_s + |c| ) / ( V_s − |c| ) = (1+μ)/(1−μ) ,     μ := |c|/V_s .            (2.41)
> ```
> **Proof.** Parameterise `u` by the angle `ψ` from `c`: `c_∥ = |c|cos ψ`, `c_⊥ = |c| sin ψ`, so
> by (2.33) `σ(ψ) = |c|cos ψ + √(V_s² − |c|² sin²ψ)`. Differentiating,
> ```
> dσ/dψ = −|c| sin ψ · [ 1 + |c| cos ψ / √(V_s² − |c|² sin²ψ) ] .
> ```
> The bracket is strictly positive: when `cos ψ ≥ 0` this is obvious; when `cos ψ < 0` the
> bracket is positive iff `√(V_s² − |c|²sin²ψ) > −|c|cos ψ = |c||cos ψ|`, and squaring both
> (non-negative) sides gives `V_s² − |c|²sin²ψ > |c|²cos²ψ ⟺ V_s² > |c|²`, true. Hence
> `sign(dσ/dψ) = −sign(sin ψ)`: `σ` is strictly decreasing on `(0,π)` and strictly increasing on
> `(π,2π)`, so its maximum is at `ψ = 0` (`σ = |c| + V_s`) and its minimum at `ψ = π`
> (`σ = V_s − |c|`). ∎

**Derived table.** `Υ_loc` against `μ`, and the corresponding `F_min = 1/(V_s+|c|)` at
`V_s = 7 m/s` (the values in ERRATA E2's table, reproduced here from the formula, not copied):

| `μ = \|c\|/V_s` | 0.0 | 0.2 | 0.5 | 0.8 | 0.9 | 0.95 | `≥ 1` |
|---|---|---|---|---|---|---|---|
| `Υ_loc` | 1.0 | 1.5 | 3.0 | 9.0 | 19.0 | 39.0 | `+∞` |
| `F_min` at `V_s = 7` [s/m] | 0.143 | 0.119 | 0.095 | 0.079 | 0.075 | 0.073 | 0.067 at `\|c\| = 8` |

**Three consequences that other sections consume, stated here because this is where `Υ` is
defined.**

1. **`F_min` does not go to zero (ERRATA E2).** `F_min = 1/(V_max + |c|) ≥ 1/(V_max + |c|_max)`,
   bounded below. Over the entire realistic drift range it shrinks by about a third. The draft's
   D3 fallback rule — "fall back to a heap when `F_min` is not bounded away from 0" — therefore
   fires on a condition that never occurs. **What actually diverges is `F_max = 1/σ_min` and
   hence `Υ_loc`**, and the object that becomes unbounded is Dial's (1969) **bucket count**,
   `n_buckets = ⌈ r_max · F_max / Δ_min ⌉` (E2.2), not the bucket width.
2. **The corrected fallback trigger is `Υ_loc > Υ_heap`,** normative default `Υ_heap = 12`
   (E2). By (2.41) that threshold is reached at
   ```
   μ_heap = (Υ_heap − 1)/(Υ_heap + 1) = 11/13 = 0.846 154 ,                          (2.42)
   ```
   i.e. at `|c| = 0.846 V_max`, which for `V_max = 7.2 m/s` is `|c| = 6.09 m/s`. **That is the
   number an implementation should log**, because a drift magnitude is what a forecast gives
   you and an anisotropy is not.
3. **`Υ_loc` sizes the ordered-upwind stencil**, `r(x) ≤ Υ_loc(x)·h` (Sethian & Vladimirsky
   2003), which is what makes ERRATA E4's causality condition `r(x)·L_t ≤ 1` a factor `Υ`
   stronger than the draft's `h·L_t ≤ 1`. §3 and §4 own those statements; the constant is
   defined here.

**Global anisotropy is a worst case and behaves like one.** `Υ` is a supremum over the whole
domain and horizon; a single Agulhas or Somali-Current cell sets it for the entire solve. That
is why §4 uses the *local* `Υ_loc(x,t)` for the per-cell stencil radius and reserves `Υ` for
the complexity statement of Thm 7.3.

---

## 2.10 The shifted indicatrix (Eq C.3) — the connection to the core

This is the only part of §2 claimed as new, and it is a corollary of Thm C.1 rather than an
independent result. Thm C.1(a) says a ground trajectory `x(·)` is admissible iff
`y(t) := x(t) − wt` is admissible for `ẏ ∈ 𝒱_w(y)`, with
```
𝒱_w(y) := 𝒱₀(y) ⊖ w := { v − w : v ∈ 𝒱₀(y) } .                                       (C.3)
```
Prop 2.10 works out what that does to every object defined in §2. The answer is: almost
nothing, which is the point.

> **Proposition 2.10 (Shift invariance; preservation of Randers structure).**
> Let `w ∈ ℝ²` be constant, let A1 (frozen advection, Eq C.2) hold, and define `𝒱_w` by (C.3).
> Then:
>
> **(i) (The shift is a drift shift.)** With `𝒲` the water-frame body of (2.2) and
> `𝒱₀ = 𝒲 ⊕ c₀`,
> ```
> 𝒱_w(y) = 𝒲(y) ⊕ ( c₀(y) − w ) .                                                    (2.43)
> ```
> **The vessel/sea-state physics `𝒲` is untouched; only the drift vector moves.**
>
> **(ii) (Hulls and support functions commute with the shift.)**
> ```
> conv 𝒱_w = (conv 𝒱₀) ⊖ w ,        𝔥_{𝒱_w}(y,p) = 𝔥_{𝒱₀}(y,p) − ⟨w,p⟩ .              (2.44)
> ```
>
> **(iii) (Gauges do NOT commute with the shift.)** `F_w(y,·)` is the gauge of a *translated*
> set and is in general unrelated to `F₀(y,·)` by any translation or rescaling. The metric
> genuinely changes; only the *set* moves rigidly.
>
> **(iv) (Randers is preserved — Eq C.6.)** If `conv 𝒱₀(y) = D(c₀(y), V_max(y))` then
> ```
> conv 𝒱_w(y) = D( c₀(y) − w , V_max(y) ) ,      c_eff := c₀ − w ,                    (2.45)
> ```
> so Prop 2.8, `GAUGE`, Cor 2.8.1, Cor 2.7.1, Prop 2.9.1 and golden vectors T1–T8 all apply
> **verbatim with `c ← c_eff`**, and (2.35) becomes `|b|_α = |c₀−w|/V_max`.
>
> **(v) (Corrected admissibility — Eq C.7.)** `0 ∈ int conv 𝒱_w(y)` iff
> `−(c₀(y) − w) ∈ int conv 𝒲(y)`; in the isotropic case (Cor 2.5.1(ii)) that is exactly
> ```
> | c₀(y) − w |  <  V_max(y) .                                                       (C.7)
> ```
> Where it fails, `F_w = +∞` outside a cone of half-angle `arcsin(V_max/|c₀−w|)` by Cor 2.8.1.
>
> **(vi) (Anisotropy under the shift.)** In the Randers case,
> ```
> Υ_loc^w(y) = ( V_max(y) + |c₀(y) − w| ) / ( V_max(y) − |c₀(y) − w| ) .              (2.46)
> ```
>
> **(vii) (The D2 table is `w`-independent.)** By (2.44) the tabulated support values need no
> rebuild when `w` changes: subtract `⟨w,p_k⟩` at read time, `O(1)` per read, using the same
> `p_k` already stored. Choosing or re-choosing `w` costs **no table work at all**.
>
> **Proof.**
> **(i)** `𝒱_w = (𝒲 ⊕ c₀) ⊖ w = 𝒲 ⊕ (c₀ − w)` because Minkowski addition of singletons is
> associative and commutative: `{ν + c₀ − w : ν ∈ 𝒲} = {ν + (c₀−w) : ν ∈ 𝒲}`. ∎
> **(ii)** `v ↦ v − w` is an affine bijection, and affine maps commute with convex hulls. For
> the support function, `𝔥_{𝒱_w}(p) = max_{v ∈ 𝒱₀} ⟨v − w, p⟩ = 𝔥_{𝒱₀}(p) − ⟨w,p⟩`. ∎
> **(iii)** Immediate from (2.6): the gauge is defined by rays from the **origin**, which is not
> translated with the set. Explicitly, in the Randers case `F₀` has parameters `(c₀,V_max)` and
> `F_w` has `(c₀−w, V_max)`; by (2.33) their unit-direction values differ by
> `σ_w(u) − σ₀(u) = −⟨w,u⟩ + √(V²−(c₀−w)_⊥²) − √(V²−(c₀)_⊥²)`, which is not a constant, not a
> scalar multiple, and changes sign with `u`. ∎
> **(iv)** By (i), `conv 𝒱_w = conv 𝒲 ⊕ (c₀ − w) = D(0,V_max) ⊕ (c₀−w) = D(c₀−w, V_max)`. Every
> statement of §2.8 was proved for an arbitrary disc `D(c,V_s)`, so substituting `c := c₀ − w`
> is legitimate without reproof. ∎
> **(v)** Cor 2.5.1 applied to `𝒱_w` using (i). ∎
> **(vi)** Prop 2.9.1 applied to `D(c₀−w, V_max)`. ∎
> **(vii)** Restatement of (2.44). ∎

> **Corollary 2.10.1 (Assumption A2 is strictly stronger than (C.7), and implies ground
> admissibility).** In the Randers case, `σ_min^w(y) = V_max(y) − |c₀(y) − w|`, so the outrun
> condition A2 (`|w| < inf_y σ_min^w`) reads
> ```
> | c₀(y) − w |  +  |w|  <  V_max(y)      for all y ∈ Ω .                             (2.47)
> ```
> By the triangle inequality `|c₀(y)| ≤ |c₀(y)−w| + |w|`, so **A2 implies both (C.7) and the
> ground-frame admissibility `|c₀(y)| < V_max(y)`**. Hence:
> **under A2 the reduction never manufactures a Kropina cell that the ground problem did not
> already have.** When A2 fails it can — e.g. `c₀ ≡ 0`, `V_max = 7`, `|w| = 8` gives a fully
> degenerate co-moving metric over a perfectly benign ocean — and then Cor 2.8.1's cone test
> fires in the co-moving frame and reports, correctly, that the vessel cannot hold station
> relative to the weather system. ∎

> **Remark 2.10.2 (Physical reading of (C.7) — this is the sentence to put in the paper).**
> `|c₀ − w| < V_max` is **not** "the current is weak". It is *"the current, as seen from the
> weather system, is weak"* — the vessel must be able to make way against the vector sum of the
> ocean current and the reversed translation of the system. Two consequences a mariner will
> recognise:
> - A ship in **slack water under a fast-moving cyclone** can fail (C.7) while trivially
>   satisfying `|c₀| < V_max`. That is correct, not a defect: the co-moving problem asks
>   whether the ship can hold position *relative to the storm*, and a `8 m/s` storm outruns a
>   `7 m/s` ship.
> - A ship in a **strong but co-moving current** (`c₀ ≈ w`) satisfies (C.7) comfortably even
>   where `|c₀| < V_max` is marginal. Being swept along with the system is not the same problem
>   as being swept across it.
>
> Where (C.7) fails, the honest output is the cone: the reachable headings are restricted, the
> route must go with the system, and the answer to "route me upwind of this cyclone" is *no*.

> **Remark 2.10.3 (Two different `w`'s, and KAIROS chooses the causality one).** Prop 2.10(vi)
> shows that the `w` minimising the co-moving anisotropy is the one minimising
> `sup_y |c₀(y) − w|` — the Chebyshev centre of the current field. Eq (C.10) instead chooses
> `w` to minimise the 99th percentile of the residual causality constant
> `max_u |∂F_w/∂t|`. **These are different optimisation problems and they need not agree.**
> CORE-THEOREM §7 is normative: KAIROS uses (C.10), because the quantity that licenses a
> single-pass solve is the causality constant, not the anisotropy. An implementation should
> **report both** `Υ` and `r·L_t` before and after the shift, because the reduction can improve
> one while degrading the other, and a run log that reports only the improving one is
> overselling.
>
> The measured evidence for the (C.10) choice, from CORE-THEOREM §7 Test 8.10, is worth
> restating with its caveats intact: `r·L_t` goes from `1.309`/`1.307` (**violated**) to
> `0.272`/`0.261` (**satisfied**) in the two A1-violating regimes — but the **median cell gets
> ~4.5× worse**, because in the ground frame most cells are far from any system and see almost
> nothing change, while in the co-moving frame the sampling point slides through space. Because
> causality is a worst-case condition this is the right trade, but it is a trade. Phase
> correlation, the natural alternative for choosing `w`, was tried and returned `(−0.74, 0.00)`
> against a true `(2.0, 0.5)`.

> **Remark 2.10.4 (What breaks without A1).** If the field is not a rigid translation,
> `E(x,t) = E₀(x − wt) + R(x,t)` (Eq C.8), then `𝒱_w` acquires a `t`-dependence through `R`,
> Prop 2.4 no longer applies exactly, and the co-moving problem is again a control problem —
> but with causality constant `L_t^R = Lip_t(R)` instead of `L_t(E)`. The reduction degrades
> from a *solution* to a *preconditioner*. All of §2's algebra (Prop 2.10(i)–(vii)) survives
> unchanged because it is pointwise in `y`; only Prop 2.4 and Thm C.1(b) are lost.
>
> **Remark 2.10.5 (Prior art).** The Galilean covariance of Zermelo's problem is elementary and
> is not claimed. What is claimed — and what CORE-THEOREM §10 records as searched for and not
> found — is its use as a *solution method* for time-dependent weather routing. Markvorsen
> (2025) treats indicatrix fields that are time-dependent but spatially uniform; that is a
> complementary special case in which the shift does nothing, since there is no spatial pattern
> to co-move with. Taylor's (1938) frozen-field hypothesis is the meteorological ancestor of A1.

---

## 2.11 The realisability gap under a dwell constraint (ERRATA E6)

**What the draft got wrong.** CONTRACT D6 and the earlier `docs/05 Thm 5.3` stated
`J_dwell − J_relax ≤ L_x · v_max · τ_d · S` with an instruction to "add a Grönwall factor".
The draft's Grönwall forcing term was **dimensionally inconsistent** (`v_max/τ_d` is m/s², not
m/s) and, worse, made the gap **decrease** as the dwell time increased — backwards, since a
longer minimum steering interval means coarser chattering and a *larger* gap. The corrected
statement is below.

**The gap being bounded.** D4 solves with `conv 𝒱`. By Carathéodory (1911) in `ℝ²`, a point of
`conv 𝒱` is a convex combination of at most three points of `𝒱`; on the *boundary* of `conv 𝒱`
— which is where a time-optimal control lives — at most two suffice. Realising such a point
requires alternating between those controls (Filippov 1967; Warga 1972). A minimum steering
dwell `τ_d` caps how fast that alternation can run, so the realised trajectory tracks the
relaxed one only on average. The gap has two sources, and only one of them is real:

- **Cost of the chattering itself: zero, provided the relaxation is taken jointly.** The
  relaxation must be applied to the *extended* set `𝒱^ext(x,t) := {(v, φ, r, m)}` of Def 1.10(c)
  — velocity together with fuel, risk and comfort rates — not to `𝒱` alone. Then the relaxed
  cost is by construction the convex combination of the achievable rates, which is exactly what
  the alternation delivers. **If instead one convexifies `𝒱` and then takes the best rate over
  the pre-image, the relaxed cost is optimistic by an amount (2.48) does not bound**, and the
  theorem is false. This hypothesis is (H-ext) below and it is not optional.
- **Cost of the position error: real, and bounded below.** The chattering trajectory oscillates
  about the relaxed one; the oscillation feeds back through the position-dependence of the
  velocity field.

> **Theorem 2.11 (Realisability gap; corrected per ERRATA E6).**
> **Hypotheses.**
> **(H-ext)** The relaxed problem is solved on `conv 𝒱^ext`, jointly in velocity and rates.
> **(H-L)** `d_H( conv 𝒱^ext(x,t), conv 𝒱^ext(x',t) ) ≤ L_v |x − x'|` with `L_v` in **1/s**.
> **(H-F)** `F` is Lipschitz in position with constant `L_x` in **s/m²**.
> **(H-τ)** Minimum steering dwell `τ_d`; within each chattering cycle every sub-interval has
> length `≥ τ_d`, and the cycle length is chosen **minimal** subject to that.
> **(H-v)** `v_max := sup_{x,t} diam( conv 𝒱(x,t) )` in m/s. (Reading `v_max` as `sup|v|`
> instead inserts a factor 2 into (2.48)–(2.49); the diameter reading is the one that makes
> ERRATA (E6.1) hold with constant 1.)
>
> **Conclusions.** Along a route of duration `T` and Euclidean length `S`, with
> `e(t) := |x_dwell(t) − x_relax(t)|`:
> ```
> e(T)               ≤  v_max · τ_d · exp( L_v · T )                                  (2.48)
> J_dwell − J_relax  ≤  L_x · v_max · τ_d · S · exp( L_v · T )                        (2.49)
> ```
> and per leg, for `z := L_v·Δt ≤ 1`,
> ```
> J_dwell − J_relax  ≤  L_x · v_max · τ_d · S_leg · ( 1 + z + (e−2) z² )
>                    ≤  L_x · v_max · τ_d · S_leg · ( 1 + 1.719 z ) .                 (2.50)
> ```
>
> **Proof.**
>
> *Step 1 — within-cycle amplitude.* Consider a cycle `[t_m, t_m + Δ]` on which the relaxed
> control is `v̄ = λ v_1 + (1−λ) v_2` with `v_1,v_2 ∈ 𝒱`, `λ ∈ (0,1)` (the two-point case; the
> three-point case is identical with an extra term and a factor `≤ 3/2`). The dwell schedule
> applies `v_1` for `λΔ` then `v_2` for `(1−λ)Δ`. Over the full cycle both cover
> `λΔ v_1 + (1−λ)Δ v_2 = v̄Δ`, so **the cycle endpoints agree exactly**; the deviation is purely
> intra-cycle. Its maximum is at the switch:
> ```
> max_{s ∈ [0,Δ]} | ∫₀^s (v_dwell − v̄) | = λΔ·|v_1 − v̄| = λ(1−λ)Δ·|v_1 − v_2| .
> ```
> (H-τ) requires `λΔ ≥ τ_d` and `(1−λ)Δ ≥ τ_d`, so the minimal cycle length is
> `Δ = τ_d / min(λ, 1−λ)`, whence
> ```
> λ(1−λ)Δ = max(λ, 1−λ) · τ_d ≤ τ_d ,
> ```
> and the intra-cycle amplitude is bounded by `A := τ_d · |v_1 − v_2| ≤ τ_d · diam(conv 𝒱)
> = v_max τ_d`, uniformly over cycles. **Note where (H-τ) is used**: without the minimal-cycle
> rule, `Δ` is free and the amplitude grows linearly in `Δ`, unbounded.
>
> *Step 2 — an intermediate trajectory.* Let `x̃` follow the same chattering schedule but with
> the velocities evaluated along the **relaxed** trajectory `x_r`. Then `x̃ − x_r` is exactly the
> intra-cycle oscillation of Step 1: `|x̃(t) − x_r(t)| ≤ A` for all `t`, and `= 0` at cycle
> boundaries.
>
> *Step 3 — Grönwall.* The true dwell trajectory `x_d` uses the same schedule but samples the
> velocity field at its own position. By (H-L), for a.e. `t`
> ```
> | d/dt ( x_d − x̃ ) |  ≤  L_v · | x_d(t) − x_r(t) |  ≤  L_v ( |x_d − x̃| + A ) .
> ```
> Writing `ξ(t) := |x_d(t) − x̃(t)|` (absolutely continuous, `ξ(0) = 0`),
> `ξ'(t) ≤ L_v ξ(t) + L_v A` a.e. Grönwall's inequality in integral form gives
> ```
> ξ(T) ≤ A ( e^{L_v T} − 1 ) ,
> ```
> and therefore `e(T) ≤ ξ(T) + A = A e^{L_v T} = v_max τ_d e^{L_v T}`, which is (2.48). ∎
>
> *Step 4 — from position error to cost.* The relaxed and dwell trajectories traverse routes
> whose corresponding points differ by at most `sup_t e(t) ≤ v_max τ_d e^{L_vT}`. By (H-F), at
> matched arclength the integrands differ by at most `L_x · e`, and integrating over the route
> length `S`,
> ```
> | J_dwell − J_relax | ≤ ∫₀^S L_x · e ds ≤ L_x · v_max τ_d e^{L_v T} · S ,
> ```
> which is (2.49). **Units:** `[s/m²]·[m/s]·[s]·[m] = [s]` ✓, the exponential dimensionless ✓,
> and the bound **increases** with `τ_d`, as it must. Under (H-ext) there is no additional cost
> term from the chattering itself: the relaxed objective already equals the convex combination
> of the achievable rates, and the schedule realises that combination exactly over each cycle. ∎
>
> *Step 5 — the local form.* For `z ∈ [0,1]`,
> `e^z = 1 + z + z²(1/2 + z/6 + z²/24 + …) ≤ 1 + z + z²(e − 2)` since the bracketed series is
> maximised at `z = 1` where it equals `e − 2 = 0.718 281…`. Hence
> `e^z ≤ 1 + z + 0.7183 z² ≤ 1 + 1.7183 z` on `[0,1]`. Substituting into (2.49) with `T ← Δt`
> and `S ← S_leg` gives (2.50). ∎

> **Remark 2.11.1 (Correction to ERRATA (E6.3)).** E6.3 states the local form as
> `≤ L_x v_max τ_d S_leg (1 + L_vΔt)`. That is the **first-order truncation** of `exp(L_vΔt)`
> and is a *lower* estimate of it, so as written it is not implied by (2.49). (2.50) is the
> rigorous version. At E6's own numbers (`L_v = 10⁻⁵ s⁻¹`, `Δt = 6 h`, so `z = 0.216`) the
> factors are `1 + z = 1.216` against `e^z = 1.241`, a `2.1 %` difference on a quantity of
> minutes. **The correction changes nothing operationally and is recorded only so the
> inequality is true as stated.**

> **Remark 2.11.2 (The numbers, derived — and E6's "under 2 seconds" is not reproducible).**
> `L_x` and `L_v` describe the *same* field variation and must be chosen consistently. In the
> Randers case, `σ(u) = ⟨u,c⟩ + √(V² − ⟨u^⊥,c⟩²)`, so
> ```
> ‖ ∂σ/∂c ‖ = ‖ u − (c_⊥/√(V²−c_⊥²)) u^⊥ ‖ = V / √(V² − c_⊥²) ≤ 1/√(1−μ²) ,
> L_x = sup |∂_x F| = sup |∂_x σ| / σ²  ≤  L_v / ( σ_min² √(1−μ²) ) .                (2.51)
> ```
> With E6's own `L_v = 10⁻⁵ s⁻¹` (1 m/s of current variation over 100 km) and the handbook's
> `V_s = 7.2 m/s`, `|c| = 1.5 m/s` (`μ = 0.2083`, `σ_min = 5.7`, `√(1−μ²) = 0.97806`):
> ```
> L_x ≤ 10⁻⁵ / (32.49 × 0.97806) = 3.147 × 10⁻⁷ s/m² ,     v_max = diam = 2V_s = 14.4 m/s.
> ```
> **Per leg** (`τ_d = 300 s`, `Δt = 6 h = 21 600 s`, `S_leg = 150 km`, `z = 0.216`,
> `e^z = 1.2411`):
> ```
> 3.147e-7 × 14.4 × 300 × 1.5e5 × 1.2411 = 253 s  ≈  4.2 minutes ,
> ```
> i.e. **1.2 % of a 6-hour leg**. E6.3 quotes "a gap under 2 seconds" for the same
> configuration; reproducing 2 s requires `L_x ≈ 2.5 × 10⁻⁹ s/m²`, two orders of magnitude
> below the value that its own `L_v = 10⁻⁵ s⁻¹` implies through (2.51). **The 2-second figure is
> not reproducible and should not be quoted.** The conclusion E6 draws from it is nevertheless
> unaffected: `4` minutes per leg is small, usable, and the local form is the one to report.
>
> **Globally** (`T = 14 d = 1.2096×10⁶ s`, `S = 5000 km`): `L_v T = 12.096`,
> `exp(L_vT) = 1.79 × 10⁵`, and
> ```
> linear part      3.147e-7 × 14.4 × 300 × 5e6            =  6 797 s  =  1.89 h  (0.56 % of T)
> with Grönwall    6 797 × 1.79e5                          =  1.22e9 s ≈ 38 years .
> ```
> **The global bound is vacuous, and it is the Grönwall factor alone that makes it so** — the
> linear part would have been a perfectly usable 0.6 %. That is a sharper statement of E6's
> point than E6 makes.

> **Conjecture 2.11.3 (what the exponential should really be, and exactly what is missing).**
> The factor `exp(L_v T)` assumes the deviation compounds for the whole voyage without ever
> re-synchronising. It does not: by Step 1 each chattering cycle returns to the relaxed
> trajectory at its endpoint, and the accumulation is driven not by `L_v` (the *magnitude* of
> the velocity gradient) but by the *expansion rate along the route*. We conjecture that the
> correct factor is `exp(Λ₁ T)` where `Λ₁` is the largest finite-time Lyapunov exponent of the
> ground-velocity field along the returned route, and that `Λ₁ ≪ L_v` for ocean currents away
> from separatrices.
> **What is missing to make this a theorem:** a one-sided Lipschitz (monotonicity) hypothesis
> `⟨v(x,t) − v(x',t), x − x'⟩ ≤ ν |x−x'|²` with `ν` replacing `L_v` in Step 3's Grönwall
> argument. Ocean current fields are *not* globally one-sided Lipschitz with small `ν` — shear
> and mesoscale eddies violate it — so the hypothesis must be localised to a tube around the
> route, and we have neither proved that localisation nor measured `Λ₁` on any returned route.
> **This is a conjecture and an unverified estimate. It must not be cited as a bound.**

> **Remark 2.11.4 (The real guarantee is a posteriori, and this is a better paper for it).**
> ERRATA E6 is right that Thm 2.11 cannot carry the global guarantee. The global guarantee in
> KAIROS is the **a posteriori optimality certificate of Cor 4.12** — the dilated-cell
> optimistic coarse solve — which is computable, tight, reported per route, and **does not
> degrade with voyage length**. Thm 2.11's local form (2.50) is a *per-leg sanity bound*, not a
> guarantee. A paper that claims an a-priori bound it cannot support is weaker than one that
> reports a computable certificate and says plainly where the a-priori bound fails.
>
> **What breaks without each hypothesis of Thm 2.11.**
> - **Without (H-ext)**: the relaxed cost may be strictly unattainable at any `τ_d > 0`, and
>   the gap is not bounded by (2.49) at all. This is the most likely way an implementation gets
>   Thm 2.11 wrong, because convexifying `𝒱` alone looks like the natural reading of D4.
> - **Without (H-L)** (`L_v = ∞`; a current discontinuity — an ice edge, a front modelled as a
>   jump, a bathymetric cliff): Grönwall does not apply and there is **no** a-priori bound. The
>   certificate is then the only guarantee available, which is another reason it is primary.
> - **Without (H-τ)**'s minimal-cycle rule: amplitude grows linearly in the cycle length and
>   (2.48) fails.
> - **With `τ_d = 0`**: the bound gives `0`, consistent with the classical relaxation theorem
>   (Filippov 1967; Warga 1972) that chattering attains `conv` in the limit.
> - **Without compactness of `𝒱`**: `v_max` may be infinite and Carathéodory's finite
>   representation, while still valid in `ℝ²`, no longer bounds the switching amplitude.

---

## 2.12 What an implementer must provide (D7 summary)

Every statement in §2 is expressible through the five primitives of `CONTRACT §4`. The
abstract data types and their required complexities:

| ADT | Operations | Complexity | Where proved |
|---|---|---|---|
| `Indicatrix` (implicit) | `sigma(x,t,u,q) -> f64 ≥ 0` | `O(1)` amortised; one crab-angle fixed point (§1.4.2) | Def 2.3 |
| `Gauge` (Randers fast path) | `F(v; c, V_max) -> (0,+∞]` | `O(1)`: 1 sqrt, 1 divide, 4 mults, 2 branches | Prop 2.8, `GAUGE` |
| `SupportTable` | `build`, `frame(i,j,t)`, `sigma_hat(i,j,t,u)` | `O(n_t n_x n_y n_θ)` / `O(n_θ)` / `O(log n_θ)` | Prop 2.7 |
| `AdmissibilityTest` | `is_degenerate(x,t) -> bool` | `O(n_θ)` scan of (2.19), or `O(1)` via `\|c\| ≥ V_max` under isotropy | Cor 2.5.1 |
| `AnisotropyOracle` | `upsilon_loc(x,t) -> [1,+∞]` | `O(1)` closed form (2.41) in setting (R); `O(n_θ)` otherwise | Prop 2.9.1 |
| `CoMovingWrapper` | wrap an `EnvField`; subtract `w` from `c` | `O(1)` per sample; **no new metric code** | Prop 2.10(i) |

**Three invariants an implementation must assert, in this order of importance.**

1. `F > 0 ∧ (isfinite(F) ∨ F = +∞)` at **every** metric evaluation, recording the first
   violating `(x, t, u)`. This catches golden vectors T7 and T8 and playbook symptom S1.
2. `σ̂ ≥ σ` wherever both the table and the metric are available with bans off (Prop 2.7(ii));
   a violation means the table is stale or the direction indexing is transposed.
3. `min_k 𝔥(x,t,p_k) > R π/n_θ` (2.19) in every cell the sweep touches, or the cell is flagged
   Kropina and its excluded cone recorded.

---

## 2.13 Assumption ledger

| Assumption | Used in | What breaks without it |
|---|---|---|
| `𝒱` compact | 2.3, 2.5, 2.6, 2.11 | `max` in Def 2.3 not attained; Prop 2.4(c) loses its realising control; `v_max = ∞` |
| **D4** (`conv 𝒱`) | 2.2.3, 2.5(F2), 2.7, 2.11 | `F` not subadditive (Rmk 2.2.4, 41 % failure); §3's Hamiltonian non-convex; Barles–Souganidis (1991) inapplicable as stated |
| **(H1)** stationarity | Prop 2.4 | voyage time is not a length; the problem is control, not geometry; **this is what Thm C.1 manufactures** |
| Isotropic `V_max(θ)` | Cor 2.5.1(ii), E1's "iff" | `\|c\| < V_max` no longer sufficient for `0 ∈ int conv 𝒱`; must use the support test (2.19) |
| `\|c\| < V_max` | 2.8, 2.9.1, (2.35) | Kropina regime: reachable cone `arcsin(V_max/\|c\|)`, `Υ_loc = ∞`, `σ_min = 0` |
| **A1** frozen advection | Prop 2.10, Prop 2.4 in `y` | reduction becomes a preconditioner; causality constant `L_t^R` replaces `L_t` |
| **A2** outrun `\|w\| < σ_min^w` | Cor 2.10.1, Thm C.1(c) | interception root may not exist; reduction can create Kropina cells the ground problem lacks |
| `V_min > 0` (engine minimum) | 2.5(F3), 2.11 | the hole of Cor 1.11.0 vanishes; station-keeping needs no relaxation |
| **(H-ext)** joint relaxation | Thm 2.11 | relaxed cost unattainable at any `τ_d`; (2.49) false |
| `L_v, L_x < ∞` | Thm 2.11 | no a-priori gap bound at all; only Cor 4.12 remains |

---

## References cited in §2

- Bao, D., Robles, C. & Shen, Z. (2004). *Zermelo navigation on Riemannian manifolds.*
  J. Differential Geometry **66**, 377–435. — the Zermelo↔Randers correspondence and the
  `|b|_α < 1` condition, reproduced in (2.35).
- Barles, G. & Souganidis, P. E. (1991). *Convergence of approximation schemes for fully
  nonlinear second order equations.* Asymptotic Analysis **4**, 271–283. — convergence
  framework invoked in Rmk 2.2.4; owned by §7.
- Carathéodory, C. (1911). — convex hull in `ℝ²` as combinations of ≤ 3 points; Thm 2.11.
- Dial, R. B. (1969). *Algorithm 360: shortest-path forest with topological ordering.*
  Comm. ACM **12**, 632–633. — the bucket queue whose ring size (E2.2) is governed by `Υ`.
- Filippov, A. F. (1967); Warga, J. (1972). — relaxed controls; chattering attains `conv`.
- Fujiwara, T. et al. (2006). — wind resistance coefficients; one of the physical sources of
  the notches in `𝒱` (owned by §1).
- IMO MSC.1/Circ.1228 (2007). *Revised guidance to the master for avoiding dangerous
  situations in adverse weather and sea conditions.* — operator envelope S7 (owned by §1).
- Lolla, T. & Lermusiaux, P. F. J. (2014). — level-set ship routing; Rmk 2.4.2.
- Markvorsen, S. (2025). *Time-dependent Zermelo navigation with tacking.* arXiv:2508.07274. —
  time-dependent-only indicatrix fields; complementary special case, Rmk 2.10.5.
- Ochi, M. K. (1964). — slamming criteria; source of ban wedges in `𝒱` (owned by §1).
- Randers, G. (1941). *On an asymmetrical metric in the four-space of general relativity.*
  Phys. Rev. **59**, 195–199. — the metric of (2.34).
- Rockafellar, R. T. (1970). *Convex Analysis.* — gauge/support duality, bipolar theorem,
  used in Prop 2.7(i).
- Schneider, R. (1993). *Convex Bodies: the Brunn–Minkowski Theory.* — support functions of
  Minkowski combinations, Lemma 2.6.1(iii) and Prop 2.7(iv).
- Sethian, J. A. & Vladimirsky, A. (2003). *Ordered upwind methods for static
  Hamilton–Jacobi equations.* SIAM J. Numer. Anal. **41**, 325–363. — `Υ`-sized stencils.
- Taylor, G. I. (1938). *The spectrum of turbulence.* Proc. R. Soc. A **164**, 476–490. —
  the frozen-field hypothesis, meteorological ancestor of A1.
- Vladimirsky, A. (2006). *Static PDEs for time-dependent control problems.* Interfaces and
  Free Boundaries **8**, 281–300. — causality conditions; ERRATA E10.
- Zermelo, E. (1931). *Über das Navigationsproblem bei ruhender oder veränderlicher
  Windverteilung.* ZAMM **11**, 114–124. — the problem, and setting (R).
