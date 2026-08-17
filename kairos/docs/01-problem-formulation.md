# 1. From naval architecture to an optimal control problem

Everything downstream depends on getting this layer right, so it is written out in full.
Notation used throughout is collected at the end of this file.

---

## 1.1 Configuration space

The ship moves on the sphere of radius `R = 6371 km`. Position `x = (λ, φ)` (longitude,
latitude). The round metric is

```
ds² = R²( dφ² + cos²φ · dλ² )
```

Work in the **local orthonormal frame** at each point,

```
e_E = (1/(R cos φ)) ∂_λ ,      e_N = (1/R) ∂_φ
```

so that all velocities are ordinary 2-vectors in m/s and the sphere only enters through the
metric coefficients when we convert grid steps to arc lengths. This keeps every formula
below planar; the spherical correction is a scaling applied once per grid row (the existing
prototype already exploits exactly this — see the `_geom` cache in `router.py`).

**State**: `(x, t) ∈ Ω × [t₀, ∞)`, where `Ω ⊂ S²_R` is the navigable ocean (open water minus
land minus TSS/ECA exclusion polygons minus depth < ship draft + UKC margin).

**Control**: `u = (V, θ) ∈ [0, V_MCR] × S¹` — through-water speed `V` and true heading `θ`.
Note the control is *through the water*, not over the ground. This distinction is the whole
game.

---

## 1.2 Kinematics

Let `c(x,t) ∈ ℝ²` be the surface current (Ekman + geostrophic + tidal). Then

```
ẋ  =  V · n(θ)  +  c(x, t) ,        n(θ) = (sin θ, cos θ)
```

`ẋ` is speed over ground (SOG); `V` is speed through water (STW). Leeway (wind-driven
drift of the hull, ≈ 1–3 % of true wind for a loaded bulker, much more for a car carrier)
is folded into an effective drift vector

```
c_eff(x,t) = c(x,t) + κ_L · W_10(x,t)
```

with `κ_L` a per-vessel leeway coefficient (a *drift characteristic* — the PS explicitly
asks for these to be configurable). From here on `c` means `c_eff`.

---

## 1.3 Powering: what speed is actually attainable

Total resistance at through-water speed `V` and heading `θ`:

```
R_tot(V, θ; x, t)  =  R_calm(V)  +  R_aw(V, θ; H_s, T_p, μ)  +  R_wind(V, θ; W_10, ψ)
```

**Calm water.** `R_calm(V) = ½ ρ S V² C_T(V)`. For the versatility the PS demands we do not
require a full Holtrop–Mennen regression per vessel; the vessel model exposes

```
P_calm(V) = P_ref · (V / V_ref)^n ,        n ∈ [2.8, 3.2]  (Admiralty form, n = 3 default)
```

and any operator with a real speed–power curve can drop it in as a spline instead. Both
paths satisfy the only property the algorithm needs: **`P_calm` strictly increasing in `V`**.

**Added resistance in waves.** Default is STAwave-1 (ISO 15016 Annex), valid for head-ish
seas and moderate heave/pitch:

```
R_aw =  (1/16) · ρ g H_s² · B · sqrt( B / L_BWL )   ·  f_dir(μ_rel)
```

with a directionality factor `f_dir(μ_rel)` peaking at head seas (`μ_rel = 180°`) and
falling to ≈ 0.2–0.3 in following seas. Where a vessel's RAOs are available, replace the
closed form by the spectral integral

```
R_aw(V, μ_rel) = 2 ∫₀^∞ ∫_{-π}^{π}  (R_aw(ω, β; V) / ζ_a²) · S(ω, β)  dβ dω
```

against the directional spectrum `S(ω, β)` (JONSWAP × cos²ˢ spreading, from the wave model).
Both forms plug into the same interface.

**Wind.** `R_wind = ½ ρ_a C_X(ψ_rel) A_T V_rel²`, `C_X` from Fujiwara's regression on
superstructure geometry.

**Delivered power and the attainable-speed map.** With `η_D` the quasi-propulsive
coefficient,

```
P(V, θ; x, t)  =  R_tot(V, θ; x, t) · V / η_D(V)
```

Because `P` is strictly increasing in `V` for fixed `(θ, x, t)`, the equation `P = P_MCR`
has a **unique** root. Define

```
V_pwr(θ; x, t)  :=  max { V ≥ 0 : P(V, θ; x, t) ≤ P_MCR }
```

computable by 6–8 Newton or bisection steps, and cacheable per (grid cell, forecast hour,
heading bin). This is the *involuntary speed loss*: no throttle setting recovers it.

---

## 1.4 Safety: the seakeeping ban set

Voluntary speed reduction — the master slowing or altering course — is not a soft penalty.
It is a hard constraint set, and IMO MSC.1/Circ.1228 tells us its shape. Each criterion
below is a function of `(V, θ)` given the sea state; each defines a forbidden region.

Let the **encounter frequency** for a wave component of frequency `ω` be

```
ω_e(ω, V, μ_rel)  =  ω  −  (ω² V / g) · cos μ_rel
```

(`μ_rel = 0` following seas, `π` head seas), and let `ω_φ` be the ship's natural roll
frequency, `T_φ = 2π/ω_φ ≈ 2π k_xx / sqrt(g·GM)`.

**S1 — Synchronous roll.** `|ω_e(ω_p, V, μ_rel) − ω_φ| < 0.10 ω_φ` **and** `H_s > H_s^{roll}`
→ banned.

**S2 — Parametric roll.** `|ω_e(ω_p, V, μ_rel) − 2ω_φ| < 0.15 · 2ω_φ` **and**
`λ_wave ∈ [0.8 L, 2.0 L]` **and** `H_s > H_s^{par}` → banned. This is the criterion that
punches a *ring-shaped* hole into the control set and is the main source of non-convexity.

**S3 — Surf-riding / broaching.** `Fn = V / sqrt(gL) > 0.30` **and** `|μ_rel| < 45°`
**and** `λ_wave > 0.8 L` → banned.

**S4 — Slamming.** Ochi's criterion on the relative vertical motion at station 0.15 L:

```
P_slam = exp( − ( d_FP² / (2 m₀ʳ)  +  v_th² / (2 m₂ʳ) ) ) ,     v_th = 0.093 sqrt(gL)
```

banned when `P_slam > 0.03` (0.01 for container ships).

**S5 — Green water on deck.** `P_gw = exp( − f_b² / (2 m₀ʳ) ) > 0.05`, `f_b` the freeboard.

**S6 — Lateral acceleration / cargo & passenger comfort.** RMS lateral acceleration at the
bridge above `0.10 g` (crew), `0.05 g` (passengers), or MSI/MII limits for a ferry.

**S7 — Operator envelope.** `H_s ≤ H_s^{max}` for the vessel/charter, plus ice, piracy
(IRTC / High Risk Area), and ECA polygons.

Collect them:

```
𝒜(x, t)  :=  { (V, θ) ∈ [0, V_pwr(θ;x,t)] × S¹  :  g_i(V, θ; x, t) ≤ 0 , i = 1..7 }
```

`𝒜` is **compact but in general not connected and not convex**. Prototype `ship.py`
currently collapses S1–S7 into one scalar `risk()`; that is a reasonable v0, and §5 explains
exactly what it costs you.

---

## 1.5 The indicatrix

> **Definition 1.1 (Indicatrix).** The set of achievable over-ground velocities is
> ```
> 𝒱(x, t)  :=  { V·n(θ) + c(x,t)  :  (V, θ) ∈ 𝒜(x, t) }  ⊂  ℝ²
> ```

Geometry to keep in your head:

- No weather, constant speed → `𝒱` is the **circle** of radius `V_s` about the origin.
  Isotropic. Ordinary Euclidean shortest path (great circle).
- Add current → the disc is **translated** to be centred at `c`. If `|c| < V_s` the origin
  is still inside: you can go anywhere, just not equally fast. If `|c| > V_s` the origin
  falls outside and there are directions you **cannot make good at all** — the metric
  degenerates from Randers to a genuinely one-sided (Kropina-type) metric. Real for the
  Agulhas retroflection and the Somali Current at 3.5–4 kt against a slow bulker.
- Add waves → `V_pwr` becomes heading-dependent, so the disc **dents inward** on the
  upwind/upwave side. Egg-shaped.
- Add S1–S7 → **wedges and rings are cut out**. The set stops being convex, and may stop
  being connected.

This single object carries all of the physics. Everything after this point is geometry and
numerics on `𝒱`.

---

## 1.6 The objectives

Along a trajectory `x(·)` with controls `u(·)` over `[t₀, t_f]`:

**Time** `J_T = t_f − t₀ = ∫ dt`.

**Fuel** `J_F = ∫ SFOC(P) · P(V,θ;x,t) dt`, in tonnes. (`SFOC` itself is load-dependent —
a shallow U in engine load with a minimum near 70–80 % MCR — which is why slow steaming is
not monotonically cheaper and why fuel is *not* a monotone function of time. This is what
makes the multi-objective problem non-trivial rather than cosmetic.)

**Risk** — two algebras, both supported:
- *additive*: `J_R = ∫ r(V,θ;x,t) dt`, an expected-damage integral;
- *bottleneck*: `J_R = max_t r(V,θ;x,t)`, the worst moment of the voyage.

Bottleneck is the one that matches how a master actually thinks, and it is the one a
scalarising weight sweep handles worst. KAIROS supports both because `(max, min)` is a
valid semiring for label-setting — see §4.4.

**Emissions / EEXI–CII** `J_C = Σ_f CF_f · (fuel_f)`, a fixed linear map of fuel, so it adds
no new machinery. Comfort (MSI) is an additive integral like risk.

---

## 1.7 The problem

> **Problem P.** Given ports `x_A, x_B`, a departure window `[t₀⁻, t₀⁺]`, a vessel model,
> and forecast fields on `Ω × [t₀, t₀+H]`, find the departure time and the measurable
> control `u(·) ∈ 𝒜(x(·), ·)` whose trajectory `ẋ = V n(θ) + c` steers `x_A → x_B` and is
> **Pareto-optimal** for `(J_T, J_F, J_R)`.

Two features distinguish this from a textbook shortest path and drive the entire design:

1. **The cost of an edge depends on when you traverse it** (non-stationary fields). Time is
   part of the state. §3 is about recovering a one-pass solve despite this.
2. **The cost depends on the direction of travel** (anisotropy), and unboundedly so when
   `|c| → V_s`. §2 quantifies this and §4 is about a stencil that survives it.

---

## Notation

| Symbol | Meaning |
|---|---|
| `x, t` | position on the sphere, absolute time |
| `V, θ` | through-water speed, true heading (the control) |
| `n(θ)` | `(sin θ, cos θ)`, unit heading vector |
| `c(x,t)` | effective drift = current + leeway |
| `H_s, T_p, μ` | significant wave height, peak period, mean wave direction |
| `μ_rel, ψ_rel` | wave / wind direction relative to heading (0 = following) |
| `ω_e, ω_φ` | encounter frequency, natural roll frequency |
| `P_MCR, η_D` | max continuous rating, quasi-propulsive coefficient |
| `𝒜(x,t)` | admissible control set after S1–S7 |
| `𝒱(x,t)` | indicatrix: achievable over-ground velocities |
| `F(x,t,v)` | Finsler metric = Minkowski gauge of `𝒱` (§2) |
| `T(x)` | earliest-arrival value function |
| `Υ` | anisotropy coefficient (§2.4) |
| `h` | grid spacing; `L_t, L_x` | Lipschitz constants of `F` in `t`, `x` |
