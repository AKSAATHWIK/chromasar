# 2. The routing metric

The claim of this section: **voyage time is a Finsler arc length**, and the whole physics
stack of §1 compresses into one scalar function `F(x, t, v)` that the solver can treat as a
black box. Getting to that statement cleanly is what makes the rest of KAIROS possible.

---

## 2.1 The gauge

> **Definition 2.1.** For `v ∈ ℝ² \ {0}`, the **local time cost** is the Minkowski gauge
> (Minkowski functional) of the indicatrix:
> ```
> F(x, t, v)  :=  inf { τ > 0  :  v/τ ∈ 𝒱(x, t) }        (with inf ∅ = +∞)
> ```

Read it directly: `F` is the number of seconds needed to make good one metre in direction
`v/|v|`, scaled by `|v|`. Three properties, all immediate from the definition:

**(P1) Positive 1-homogeneity.** `F(x,t,αv) = α F(x,t,v)` for `α > 0`.
*Not* absolutely homogeneous: `F(x,t,−v) ≠ F(x,t,v)` in general. Sailing east against the
Somali Current costs more than sailing west with it. That asymmetry is precisely why this
is Finsler and not Riemannian, and why symmetric-metric machinery (plain Fast Marching,
Riemannian eikonal solvers) is the wrong tool.

**(P2) Subadditivity iff convex.** `F(x,t,v+w) ≤ F(x,t,v) + F(x,t,w)` holds **iff** `𝒱` is
convex. §2.5 deals with what happens when the seakeeping bans break convexity.

**(P3) Finiteness.** `F(x,t,v) < ∞` for all `v ≠ 0` **iff** `0 ∈ int 𝒱(x,t)`, i.e. iff the
ship can hold station against the drift. Where `|c| ≥ V_pwr`, `F = +∞` in a cone of
directions and the metric is one-sided.

> **Proposition 2.2 (Voyage time is Finsler length).** For an absolutely continuous
> trajectory `x: [0,S] → Ω` parameterised by any monotone parameter `s`, with arrival-time
> profile `t(s)` satisfying `t(0)=t₀`, the elapsed voyage time is
> ```
> J_T  =  ∫₀^S  F( x(s), t(s), x'(s) )  ds
> ```
> and this value is independent of the parameterisation.

*Proof.* By (P1) the integrand is 1-homogeneous in `x'`, so the integral is
reparameterisation-invariant. Pointwise, `dt/ds = F(x, t, x')` is exactly the statement that
`x'(s)/(dt/ds) = ẋ ∈ 𝒱`, i.e. that the instantaneous ground velocity is achievable, and it is
the *smallest* such `dt/ds` by definition of the infimum. ∎

So the optimal route is a **Finsler geodesic of a time-dependent metric**. That is the whole
problem, stated in five words.

---

## 2.2 Closed form: the Randers case

Take the classical case — fixed through-water speed `V_s`, current `c`, no wave dents, no
bans. Then `𝒱 = D(c, V_s)`, the disc of radius `V_s` centred at `c`. Solve the gauge
directly. We need `τ` with `|v/τ − c| = V_s`:

```
|v|² − 2τ⟨v,c⟩ + τ²|c|²  =  τ² V_s²
⇒   (V_s² − |c|²) τ²  +  2⟨v,c⟩ τ  −  |v|²  =  0
```

Take the positive root. Writing `λ := V_s² − |c|² > 0`:

```
        sqrt( ⟨v,c⟩²  +  λ |v|² )        ⟨v,c⟩
F(v) =  ─────────────────────────   −   ───────                    (2.1)
                    λ                       λ
```

Sanity checks: `c = 0` gives `F = |v|/V_s` ✓. `v ∥ c`, `|v|=1` gives `F = 1/(V_s + |c|)` ✓
(riding the current). `v ∥ −c` gives `F = 1/(V_s − |c|)` ✓ (bucking it).

Equation (2.1) is exactly a **Randers metric** `F(v) = sqrt(a_{ij} v^i v^j) + b_i v^i` with

```
a_{ij}  =  δ_{ij}/λ  +  c_i c_j / λ²  ,        b_i  =  − c_i / λ
```

and the Randers admissibility condition `‖b‖_a < 1` is precisely `|c| < V_s`.

> **Theorem 2.3 (Zermelo ↔ Randers; Bao–Robles–Shen 2004).** The solution of Zermelo's
> navigation problem on a Riemannian manifold `(M, a)` under a vector field `c` with
> `|c|_a < 1` is a Randers metric, and every Randers metric arises this way.

We do not claim this; we *use* it, and it earns its place twice over:

1. **A closed-form ground truth.** Every numerical claim KAIROS makes can be validated
   against (2.1) on synthetic current fields where the geodesics are known analytically
   (uniform flow, linear shear, a Rankine vortex). Most routing papers validate against
   another code. We can validate against a formula.
2. **A fast path.** When the sea state at a node is below the wave threshold and no ban is
   active, evaluate (2.1) directly instead of running the bisection of §1.3. In the Indian
   Ocean outside monsoon this is the majority of nodes, and it is roughly 40× cheaper.

---

## 2.3 The general case: no closed form, but a cheap one

With wave dents and bans, `𝒱` is described implicitly and the gauge must be evaluated
numerically. But note what is actually required: for a *fixed direction* `u = v/|v|`, we need

```
F(x,t,v) = |v| / σ(x,t,u) ,     σ(x,t,u) := max { s > 0 : s·u ∈ 𝒱(x,t) }
```

`σ` is the **speed made good** in direction `u` — a scalar, positive, and computable by a
1-D root find. Concretely: parameterise candidate headings `θ`, require the cross-track
component of `V n(θ) + c` to vanish (drift-correction, exactly the `c_cross` cancellation
already implemented in `ship.py:transit`), giving

```
V sin(θ − α_u)  =  −c_⊥(u)        ⇒       θ(V) = α_u + arcsin( −c_⊥(u)/V )
σ(u) = max over V ∈ [0,V_pwr(θ(V))] with (V,θ(V)) ∈ 𝒜  of  [ sqrt(V² − c_⊥²) + c_∥ ]
```

Since `V ↦ sqrt(V² − c_⊥²) + c_∥` is increasing, the unconstrained maximiser is the largest
feasible `V`, and the only work is (a) the `V_pwr` bisection and (b) checking `𝒜`. **Cost per
evaluation: ~10 flops plus one bisection**, and the whole thing tabulates on a
`(cell, forecast-hour, 72 heading bins)` grid that fits in cache.

*Precomputation is the reason KAIROS is fast.* The metric table for a 0.25° Indian Ocean
grid × 8 forecast hours × 72 headings is ≈ 40 M floats ≈ 160 MB in float32 — fits in RAM on
a laptop, and it is embarrassingly parallel to build.

---

## 2.4 Anisotropy coefficient

> **Definition 2.4.** The local anisotropy coefficient is
> ```
> Υ(x,t)  :=  max_{|u|=1} F(x,t,u)  /  min_{|u|=1} F(x,t,u)  =  σ_max / σ_min
> ```
> and `Υ := sup_{x,t} Υ(x,t)` globally.

For pure current, `Υ = (V_s + |c|)/(V_s − |c|)`. Numbers for the Indian Ocean:

| Situation | `V_s` | `|c|` | `Υ` |
|---|---|---|---|
| Open Arabian Sea, quiet | 14 kt | 0.3 kt | 1.04 |
| Equatorial counter-current | 14 kt | 1.2 kt | 1.19 |
| Somali Current, SW monsoon peak | 14 kt | 3.5 kt | **1.67** |
| Agulhas core, slow bulker | 11 kt | 4.5 kt | **2.4** |
| + head-sea speed loss `H_s = 6 m` | — | — | **3.5–4** |

`Υ` is the parameter that governs everything numerical:

- `Υ = 1` → isotropic → plain Fast Marching is correct and `O(N log N)`.
- `Υ > 1` → the characteristic direction can leave the simplex used for the update, and
  **plain FMM is silently wrong**. The Ordered Upwind Method fixes this at cost
  `O(Υ N log N)` by widening the stencil to radius `Υ h`.
- `Υ = ∞` (when `|c| ≥ V_pwr`) → one-sided metric, and the algorithm must handle `F = ∞`
  gracefully rather than dividing by zero.

The key operational observation, and the source of KAIROS's speed: **`Υ` is large only on a
small fraction of the domain.** A globally-sized stencil pays the Agulhas price everywhere.
§4.3 makes the stencil local, which is worth a 4–8× constant factor on realistic fields.

---

## 2.5 Non-convexity and what it costs

The seakeeping bans S1–S7 make `𝒱` non-convex. Two facts, in tension.

**Fact A — the Hamiltonian cannot see the dents.** The HJB Hamiltonian (§3.1) is the
*support function* of `𝒱`,

```
H(x,t,p)  =  max_{v ∈ 𝒱(x,t)} ⟨v, p⟩ ,
```

and the support function of any set equals that of its closed convex hull:
`h_𝒱 = h_{conv 𝒱}`. So the viscosity solution of the HJB is the value function of the
**relaxed** problem, in which the ship is allowed to *chatter* between two admissible
control values at infinite frequency, achieving their convex combination on average.

**Fact B — chattering is not steerable.** A real rudder has a rate limit and a real master
does not oscillate heading at 1 Hz to synthesise a banned course.

So the relaxed optimum is a genuine **lower bound** that may be unattainable. Most of the
literature quietly ignores this. We bound it instead.

> **Definition 2.5 (Dwell-constrained indicatrix).** For minimum dwell time `τ_d > 0` let
> `𝒱_{τ_d}(x,t)` be the set of average ground velocities realisable by piecewise-constant
> controls in `𝒜(x,t)` with all switching intervals `≥ τ_d`. Then
> ```
> 𝒱  ⊆  𝒱_{τ_d}  ⊆  conv 𝒱 ,     and  𝒱_{τ_d} ↑ conv 𝒱  as τ_d ↓ 0.
> ```

> **Proposition 2.6 (Realisability gap — proved as Thm 5.3).** Let `J*_relax` be the optimal
> voyage time for `conv 𝒱` and `J*_dwell` that for `𝒱_{τ_d}`. If `F` is `L_x`-Lipschitz in
> `x` and the ship's ground speed is bounded by `v_max`, then along a route of length `S`
> ```
> 0  ≤  J*_dwell  −  J*_relax  ≤  L_x · v_max · τ_d · S
> ```

The gap is **linear in the dwell time**, not in the size of the banned region, and it
vanishes when the metric is spatially uniform. For a bulker with `τ_d = 300 s`,
`v_max = 8 m/s`, `L_x ≈ 10⁻⁸ s/m² ` (a 10 % metric change over 1000 km), `S = 5×10⁶ m`:
gap ≈ 120 s on a two-week voyage. **Negligible, and now certified rather than assumed.**

Practical consequence for the implementation: solve with `conv 𝒱` (cheap, convex, gives a
valid support function and a valid lower bound), then run the **notch projection** of §4.7 —
walk the recovered route, and wherever the commanded `(V,θ)` lands inside a banned region,
snap it to the nearest feasible boundary point and re-integrate. Proposition 2.6 certifies
the result is within `L_x v_max τ_d S` of optimal. This is the honest version of what every
other router does implicitly.

---

## 2.6 What the solver needs from all of this

The entire physics of §1 and §2 reduces to **one function** with this signature:

```
sigma(x, t, u)  ->  float          # speed made good, m/s, in unit direction u; 0 if forbidden
```

plus its per-objective siblings `fuel_rate(x,t,u)` and `risk_rate(x,t,u)`. Everything in
§3 and §4 is written against that interface alone. Swapping bulker → container ship → ferry
means swapping the vessel model, not the algorithm — which is the "versatile … for a range
of ships" requirement of the problem statement, discharged structurally rather than by
promise.
