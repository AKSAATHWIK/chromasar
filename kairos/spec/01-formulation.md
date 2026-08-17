# §1 — Formulation: the control problem

**Block ownership (CONTRACT §2):** this file owns `§1`, `Def 1.x`, `Lemma 1.x`, `Prop 1.x`,
`Eq (1.x)`. Symbols are those of CONTRACT §1 and are not redefined here.

**Normative precedence.** Where this file and CONTRACT disagree, ERRATA and CORE-THEOREM
win, then this file, then CONTRACT. Three specific overrides are exercised below and each is
flagged at the point of use: **E8** (kinematics resolved in the local frame, §1.1.2),
**E9** (finiteness of the metric, §1.4.7), **E1** (the reachable cone, §1.4.7).

---

## 1.0 What this file is for, and where it sits

KAIROS is defined by the **Co-Moving Reduction** (CORE-THEOREM, Thm C.1): under assumption
A1 the routing problem in the frame `y = x − w t` is *exactly stationary*, so the causality
obstruction that dominates the time-dependent-routing literature dissolves, and the solve is
one monotone pass plus a scalar interception. That theorem is the claim. Everything in this
file is the **model it is applied to** — the control problem whose indicatrix field `𝒱(x,t)`
Thm C.1 shifts.

This file therefore does four things and claims novelty for none of them:

1. It fixes the configuration space, the frame, and the kinematics, dimensionally
   consistently (§1.1–§1.2). Zermelo (1931) is the ancestor.
2. It builds the achievable-velocity model out of published naval-architecture components —
   Admiralty powering, STAwave-1 (ITTC/ISO), Fujiwara (2006) windage, Ochi (1964) slamming,
   IMO MSC.1/Circ.1228 seakeeping — and states exactly which of them are load-bearing for
   the algorithm and which are swappable (§1.3, §1.5).
3. It makes **throttle an explicit control** (decision D1) and proves the asymmetry that
   makes the multi-objective machinery necessary rather than decorative: the time objective
   collapses the throttle family to a single point per direction, fuel does not (§1.4, §1.6).
4. It states **A1** and **A2** as the standing assumptions of the whole specification, with
   an exact account of what each buys and what breaks without it (§1.8).

One result in this file is genuinely new and is a direct consequence of the reduction:
**Prop 1.16 (Galilean invariance of the vessel model)** — the co-moving shift is invisible to
every function in §1.3, §1.5 and §1.6, touching only the kinematic drift. That is why the
reduction needs no new physics code, and it comes with an implementation trap (§1.8.3) that
costs about 1 % in speed if got wrong.

**Assumptions A1 and A2 are not in force in §1.1–§1.7.** Those sections state the ground-frame
problem in full generality, with `𝒱` depending on both `x` and `t`. A1 and A2 enter in §1.8
and are in force from there on, for every later file.

---

## 1.1 Configuration space and the local orthonormal frame

### 1.1.1 The manifold

The vessel's position is a point on a sphere of radius

```
R_E = 6 371 000 m   exactly (definitional, not measured)                     (1.1)
```

The navigable domain `Ω ⊂ S²` is an open set with a piecewise-smooth boundary, obtained by
removing land, water shallower than the vessel's draft-plus-margin, and any policy exclusion
(ice charts, ECA boundaries, traffic-separation schemes, war-risk zones). `Ω` is a **static**
set: it does not depend on `t`. This is a stronger statement than it looks and it is the
subject of §1.8.2, where it collides with A1.

Charted coordinates are `x = (λ, ϕ)` — longitude, latitude — **in radians**. The chart is
singular at the poles and degenerate near them; §1.1.4 gives the quantitative cap.

The sphere is a model, not the Earth. WGS84 has flattening `f = 1/298.257 223 563`, so the
polar radius is smaller than the equatorial by `f·a = 21.385 km`, i.e. **0.335 %**. Distances
computed on a sphere of radius `R_E` therefore carry a systematic error of that order,
latitude-dependent, which is far larger than every numerical tolerance in this specification.
The error is *common to all candidate routes at a given latitude*, so it largely cancels out
of route *comparisons* and shows up mainly in absolute arrival times. Implementations that
need absolute times to better than 0.3 % must replace `haversine`/`initial_bearing` with
their geodesic (Vincenty or Karney) equivalents; nothing else in the specification changes,
because §1.1.2 confines all geodesy to one conversion layer.

**Self-check (handbook G1).** The quarter-circumference must be

```
2π R_E / 4 = 10 007 543.398 010 286 m                                        (1.2)
```

to the last printed digit. A distance routine that fails (1.2) has the wrong radius or a
missing `asin` domain guard, and every number downstream of it is wrong by the same factor.

### 1.1.2 The local orthonormal frame, and the E8 convention

At each `x ∈ Ω` the tangent plane `T_x S²` carries the orthonormal frame

```
𝐞_E(x) = east-pointing unit tangent,   𝐞_N(x) = north-pointing unit tangent   (1.3)
```

which is positively oriented and defined everywhere except at the poles.

> **Convention 1.0 (ERRATA E8 — the only dimensionally consistent reading).**
> Throughout KAIROS, `ẋ` denotes the pair of **components of the ground velocity resolved in
> the frame `(𝐞_E, 𝐞_N)`, in metres per second** — *not* the derivative of the chart
> coordinates. Every velocity, drift, wind and wave vector in this specification is a pair of
> m/s components in that frame.

The draft that this file replaces wrote `ẋ = V n(θ) + c` with `x = (λ, ϕ)` in radians. The
left-hand side is then rad/s and the right-hand side m/s: the equation is dimensionally false,
and an implementer who takes it literally gets a router whose errors scale with `1/cos ϕ` and
therefore look like a "high-latitude problem" rather than the units bug they are.

The chart derivative is recovered from the frame components exactly once, at the chart
boundary:

```
λ̇ = ⟨v, 𝐞_E⟩ / (R_E cos ϕ) ,        ϕ̇ = ⟨v, 𝐞_N⟩ / R_E                       (1.4)
```

and the inverse, used to step a position by a metric displacement `(Δ_E, Δ_N)` in metres:

```
Δλ = Δ_E / (R_E cos ϕ) ,             Δϕ = Δ_N / R_E                           (1.5)
```

**Implementation obligation.** (1.4)–(1.5) are implemented in exactly one module (the
reference implementation calls it `geodesy`) and nothing else in the system performs a
degree/metre conversion. The solver, the metric, the powering model and the seakeeping model
run entirely in frame components and never see `λ` or `ϕ` except as arguments to environment
sampling. This is not tidiness: two independent copies of (1.5) is how a `cos ϕ` gets applied
twice, and the resulting route is plausible everywhere and wrong everywhere.

`cos ϕ` in (1.4)–(1.5) must be guarded. Adopt `cos ϕ ← max(cos ϕ, cos ϕ_max)` with the
domain cap of §1.1.4; do not let it reach zero.

### 1.1.3 Directions, headings and bearings

A unit direction over ground is written `u ∈ S¹` with frame components `u = (u_E, u_N)`,
`|u| = 1`. A heading `θ` is measured clockwise from true north, so

```
n(θ) = (sin θ, cos θ)          [components in (𝐞_E, 𝐞_N)]                     (1.6)
```

and the bearing of a direction `u` is `χ(u) = atan2(u_E, u_N)` — east-first in the
`atan2` arguments, which is the transposition of the usual mathematical convention and the
single most common source of routes that bend the wrong way (playbook S2).

### 1.1.4 Why one grid cell may be treated as planar, and where that stops

The frame is not parallel-transported: it rotates along a path. Moving a distance `ℓ` on a
bearing `χ` from latitude `ϕ`, the meridian convergence rotates the frame by

```
Δχ_frame = (ℓ / R_E) · tan ϕ · sin χ + O((ℓ/R_E)²)                            (1.7)
```

(the `sin χ` factor because only the east-going component of the displacement crosses
meridians). Within one grid cell of side `h` the worst case is `χ = 90°`:

| `ϕ` | `tan ϕ` | `Δχ_frame` at `h = 28 km` | at `h = 4 km` |
|---|---|---|---|
| 0° | 0.000 | 0.000° | 0.000° |
| 30° | 0.577 | 0.145° | 0.021° |
| 45° | 1.000 | 0.252° | 0.036° |
| 60° | 1.732 | 0.436° | 0.062° |
| 75° | 3.732 | 0.940° | 0.134° |
| 85° | 11.430 | 2.879° | 0.411° |

*(computed from (1.7) with `R_E` from (1.1); e.g. `28 000 · 1.732 / 6 371 000 = 7.612×10⁻³
rad = 0.436°`.)*

The semi-Lagrangian update of §4 treats a stencil neighbourhood as a Euclidean plane. The
error that introduces is a heading error of order `Δχ_frame`, which enters the speed made good
as `σ(u) → σ(u + O(Δχ_frame))`, i.e. a relative speed error of order `Δχ_frame · Υ_loc` in the
worst case, `Υ_loc` being the local anisotropy (CONTRACT Def 2.9). At `ϕ = 60°`, `h = 28 km`,
`Υ_loc = 2`: `0.436° = 7.6×10⁻³ rad`, giving under 1.6 % — comparable to the fixed-stencil
metrication floor already measured at ~1 % (CORE-THEOREM §4) and therefore not the dominant
error. At `ϕ = 85°` it dominates.

> **Domain cap (normative).** `|ϕ| ≤ 80°`. Beyond that, either refine `h` so that
> `h · tan ϕ / R_E ≤ 5×10⁻³` (0.29°), or change chart. The Indian Ocean operating envelope
> that motivates KAIROS never approaches this cap; polar routing does, and this
> specification does not cover it.

**What breaks without the cap:** at `ϕ → 90°`, `cos ϕ → 0` makes (1.4) singular, `Δχ_frame`
diverges, and a fixed-`Δλ` grid degenerates (cells become slivers), so the stencil radius in
metres becomes wildly anisotropic in a way that has nothing to do with the physics. The
failure is not graceful; it is a silent loss of accuracy that looks like a weather effect.

---

## 1.2 Kinematics, with leeway folded into the effective drift

### 1.2.1 The equation of motion

> **Def 1.1 (Effective drift).** The **effective drift** is the ground velocity the vessel
> acquires from the medium at zero through-water speed:
> ```
> c(x,t) := c_cur(x,t) + κ_L · W₁₀(x,t)          [m/s, frame components]      (1.8)
> ```
> with `c_cur` the surface current and `κ_L` the vessel's leeway coefficient
> (`κ_L = 0.025` default). Both terms are frame components per Convention 1.0.

The kinematics are then, per Convention 1.0 and ERRATA E8,

```
ẋ = v = V · n(θ) + c(x,t)                                                     (1.9)
```

with `V ≥ 0` the speed **through the water** and `θ` the true heading. Chart coordinates are
recovered from (1.9) by (1.4) and only there.

Three things (1.9) asserts and one it does not:

- The ship's motion relative to the water is `V n(θ)`, aligned with the heading. Real hulls
  make a small drift angle under rudder and in a beam wind; that is inside the leeway term
  and inside `η_D`, not modelled separately.
- The drift is added, not composed: the current advects the whole water column the ship sits
  in. This is exact for a depth-uniform current and is the standard Zermelo (1931) model.
- Wind enters (1.9) **kinematically** through `κ_L W₁₀` and enters §1.3 **dynamically**
  through the added aerodynamic resistance `R_AA`. These are different physical channels —
  being pushed sideways versus being slowed down — and counting one of them twice is not
  double-counting the other. An implementation must apply both.
- (1.9) does **not** model manoeuvring dynamics: no turning circle, no acceleration lag, no
  rudder drag. The vessel is a kinematic point that can change heading instantaneously. That
  idealisation is repaired, partially, by the minimum steering dwell `τ_d` and the
  realisability gap of Thm 2.11 in its corrected local form (ERRATA E6.3), and it is the
  reason that theorem exists.

### 1.2.2 Leeway: what the collinear model costs

`κ_L W₁₀` puts the leeway *along the true wind*. A hull actually makes leeway largely abeam,
with the fraction depending on the relative wind angle, the draft and the lateral area. The
collinear model therefore overstates the along-track component in head and following winds
and understates the cross-track component in beam winds.

The magnitude is not negligible and should not be described as if it were. At `κ_L = 0.025`:

| `\|W₁₀\|` | leeway `κ_L\|W₁₀\|` | worst-case direction error |
|---|---|---|
| 10 m/s (fresh breeze) | 0.250 m/s | up to 0.250 m/s |
| 15 m/s (near gale) | 0.375 m/s | up to 0.375 m/s |
| 20 m/s (gale) | 0.500 m/s | up to 0.500 m/s |

The "worst-case direction error" column is the leeway magnitude itself, because a vector of
that length can be misplaced by up to 90°. Against a through-water speed of ~7.9 m/s this is
up to 6 % of the velocity, cross-track, in a gale.

Two honest qualifications. First, the error is bounded by the leeway magnitude and is much
smaller at the beam angles where the collinear model is worst in *direction*, because there
the along-wind and abeam directions are close. Second, operational surface-current forecasts
carry their own error; open-ocean values of 0.1–0.3 m/s are commonly quoted but we have not
measured them here, so **that comparison is an unverified estimate and must not be used to
dismiss the leeway error**. A vessel operating routinely in gale conditions should replace
Def 1.1 with an angle-dependent leeway model; the interface (`drift_vector`) does not change.

### 1.2.3 Where the co-moving shift acts

Under Thm C.1 the co-moving indicatrix is `𝒱_w(y) = 𝒱₀(y) ⊖ w`, i.e. the whole achievable
set is translated by `−w`. By (1.9) this is achieved by translating the **effective drift**:

```
c(x,t)  ⟼  c_w(y) := c₀(y) − w                                               (1.10)
```

and nothing else. Because the shift is by a constant vector and Def 1.1 is a sum, it is
immaterial which additive component of `c` absorbs it: subtracting `w` from `c_cur` before
adding leeway gives `(c_cur − w) + κ_L W₁₀ = c − w`, identically. The reference
implementation does exactly that, which is why it needs no new metric code.

> **Do not subtract `w` twice.** The one failure mode here is an implementation that shifts
> the current *and* shifts the wind (or the wave field). The wind must not be shifted: it
> enters the drift with a coefficient `κ_L`, so shifting it would apply `−κ_L w` on top of
> `−w`. The correct rule is: **`w` is subtracted from the total effective drift, once.**

The deeper reason the reduction touches only (1.10) — and nothing in §1.3, §1.5 or §1.6 — is
Prop 1.16, proved in §1.8.3.

---

## 1.3 Powering: from throttle to through-water speed

The chain is: throttle `q` fixes available shaft power; resistance at a candidate speed fixes
required shaft power; the attainable speed is where they balance. All three pieces are
swappable; the algorithm requires only the monotonicity of Lemma 1.4.

### 1.3.1 Resistance decomposition and delivered power

> **Def 1.2 (Delivered power).** For a heading `θ` and through-water speed `V`, in
> environment `Env`,
> ```
> R_tot(V,θ) := R_calm(V) + R_AW(θ) + R_AA(V,θ)              [N]              (1.11)
> P_D(V,θ)   := R_tot(V,θ) · V / η_D                          [W]              (1.12)
> ```
> with `η_D` the quasi-propulsive coefficient. `R_AA` is **signed**: a following wind returns
> a negative value, and clamping it would insert a spurious resistance floor.

`R_calm` is not modelled independently. It is *defined* by inverting the vessel's own
calm-water speed–power curve:

```
R_calm(V) := η_D · P_calm(V) / V                                              (1.13)
```

so that (1.12) may be evaluated in the algebraically identical but numerically preferable form

```
P_D(V,θ) = P_calm(V) + ( R_AW(θ) + R_AA(V,θ) ) · V / η_D                      (1.14)
```

Two reasons, both structural rather than cosmetic. (i) A vessel record published by a
charterer or a class society contains a speed–power curve, not a resistance breakdown, so
(1.13) consumes what actually exists. (ii) In flat calm, (1.14) returns `P_calm(V)` *exactly*,
bit for bit, rather than to a few parts in 10¹⁵ — so replacing `P_calm` with a measured spline
propagates through every function downstream with no further edit and no drift.

### 1.3.2 Calm-water power: the Admiralty default and the measured-curve hook

**Default (Admiralty).**

```
P_calm(V) = P_ref · (V / V_ref)^n ,     n = 3 default                         (1.15)
```

Reference vessel (a generic Handymax bulker, and every number below is derived from it):
`V_ref = 14 kt = 7.202 222 m/s`, `P_ref = 8.2 MW`, `P_MCR = 11.0 MW`, `η_D = 0.68`,
`V_hull = 16.5 kt = 8.488 333 m/s`, `q_min = 0.15`, `L = 190 m`, `B = 32 m`, `T_d = 11 m`,
`L_bwl = 185 m`, freeboard `f_b = 6.5 m`, `A_T = 620 m²`, `GM = 2.4 m`, `k_xx = 0.38 B`.

From (1.15): `P_ref / V_ref³ = 8.2×10⁶ / 373.594 = 21 948.6 W·s³/m³`, so

```
P_calm(V) = 21 948.6 · V³        [W]                                          (1.16)
dP_calm/dV = 65 845.8 · V²       [W per m/s]                                  (1.17)
```

and `R_calm(V_ref) = 0.68 × 8.2×10⁶ / 7.202 222 = 774.2 kN`. This last number is the yardstick
for §1.3.3–§1.3.4: every added resistance below is quoted against it.

`n = 3` is the classical Admiralty exponent. Real full-form hulls run `n ≈ 3.0–3.5` over the
service range and steeper above it. The value is a vessel parameter, not a constant of the
method.

**Measured-curve hook.** `P_calm` is an injection point. A production deployment replaces
(1.15) with an interpolant through sea-trial or noon-report points. The **only** requirement
the rest of KAIROS places on it is:

> **(H1)** `P_calm` is continuous on `[0, V_hull]`, `P_calm(0⁺) = 0`, and **strictly
> increasing** on `(0, V_hull]`.

The Admiralty form satisfies (H1) for any `n > 0`. §1.3.5 says exactly what to do when a
supplied spline does not.

### 1.3.3 Added resistance in waves: STAwave-1 and its envelope

**STAwave-1** (ITTC 7.5-04-01-01.2; ISO 15016:2015 Annex), extended by a directionality
factor:

```
R_AW(θ) = f_dir(β) · (1/16) · ρ_sw · g · H_s² · B · sqrt(B / L_bwl)     [N]   (1.18)
f_dir(β) = 0.55 − 0.45 cos β                                                  (1.19)
β := angle between n(θ) and the direction the waves TRAVEL TOWARDS
```

so `β = π` is a head sea (`f_dir = 1.00`), `β = π/2` beam (`0.55`), `β = 0` following
(`0.10`); bow-quartering `β = 3π/4` gives `0.868`, stern-quartering `β = π/4` gives `0.232`.
The wave-direction convention is **towards**, not the meteorological **from**; the rotation by
`π` happens once, at data ingest, and never again. Getting it backwards is a 180° error that
looks entirely plausible on a chart (playbook S2 gives the discriminating test).

With the reference vessel the height-independent coefficient is

```
K_AW := (1/16) ρ_sw g B sqrt(B/L_bwl)
      = 0.0625 × 1025 × 9.806 65 × 32 × 0.415 900 = 8 361.1 N/m²             (1.20)
```

so `R_AW = f_dir · 8 361.1 · H_s²`, e.g. **133.8 kN** in a 4 m head sea — **17.3 %** of
`R_calm(V_ref)`, and 5.9 % in a 2 m head sea.

**Validity envelope, stated because the formula is used far outside it.**

1. *Head waves only*, nominally within ±45° of the bow. `f_dir` in (1.19) is **our**
   extension, not part of the standard. Its shape tracks published RAO-integrated
   added-resistance polars for full-form hulls; it does not go to zero in a following sea
   because the real one does not either. It is unvalidated against tank data here — treat
   the off-bow values as a modelled interpolation, not a measurement.
2. *Small heave and pitch*, operationalised by the standard as
   `H_s ≤ 2.25 sqrt(L_pp/100)` — **3.101 m** for `L = 190 m`. Above that the true added
   resistance saturates relative to the `H_s²` law, so (1.18) **overstates** resistance in
   the heaviest seas. That bias is conservative for routing (storms look worse than they are)
   and is accepted deliberately. It also means fuel figures in high seas are upper bounds.
3. *No period dependence.* STAwave-1 is blind to `T_p` and therefore blind to the resonance
   peak near `λ ≈ L_pp`, where added resistance genuinely roughly doubles. This is the
   formula's chief weakness and it is a weakness in exactly the sea states that decide
   routing. `T_p` is available in `Env` and a STAwave-2 or RAO-based replacement drops in
   behind the same signature.
4. *Deep water.* No shallow-water correction, even though `Env.depth` exists; shallow effects
   are carried by the squat term in S7 instead.

**The spectral RAO alternative.** Where motion transfer functions are available (strip theory
or panel code), replace (1.18) by the exact quadratic-transfer integral

```
R_AW = 2 ∫₀^∞ ∫_{-π}^{π} R_wave(ω, β; V) · S(ω, β) dβ dω                      (1.21)
```

with `R_wave` the added-resistance operator per unit wave amplitude squared [N/m²] and
`S(ω,β)` the directional spectrum [m²·s/rad]. (1.21) restores the period dependence and the
resonance peak, is speed-dependent, and is the correct object; it costs a 2-D quadrature per
`(V,θ)` evaluation, which is prohibitive in the inner loop and must be **pre-tabulated on a
`(V, β, H_s, T_p)` grid** and interpolated. If a directional spectrum is unavailable, the
standard reconstruction from `(H_s, T_p, μ_w)` is a JONSWAP or Bretschneider frequency
spectrum times a `cos^{2s}` spreading function; that reconstruction is itself a model and its
error is not quantified here.

**Consequence for the algorithm, and it is the one that matters:** STAwave-1 is
**independent of `V`**. A `V`-independent `R_AW ≥ 0` contributes a term `R_AW·V/η_D` to (1.14)
that is *linear and increasing* in `V`, so it cannot break Lemma 1.4. The RAO path (1.21) is
`V`-dependent and **can** break it; an implementation using (1.21) must re-verify (H1)-style
monotonicity numerically on its tabulated grid and fall back to the smallest-root rule of
§1.3.5 where it fails.

### 1.3.4 Wind resistance: Fujiwara

Following Fujiwara, Ueno and Ikeda (2006), the longitudinal aerodynamic force is a windage
area times a dynamic pressure times a direction-dependent coefficient, with the still-air
term subtracted per ISO 15016:

```
R_AA(V,θ) = ½ ρ_air A_T [ C_X(ψ) · |V_rel|²  −  C_X(0) · |v_g|² ]       [N]   (1.22)

v_g   = V n(θ) + c        (ground velocity)
V_rel = W₁₀ − v_g         (wind as seen from the deck)
cos ψ = −⟨V_rel, n(θ)⟩ / |V_rel|     (ψ = apparent wind angle off the bow)
```

**Why the second term is not decoration.** `P_calm` is a fit to trial or service data taken in
some ambient air, so the still-air windage at the ship's own speed is *already inside*
`R_calm` through (1.13). Subtracting it makes the still-air case cancel exactly: with
`W₁₀ = 0`, `V_rel = −v_g`, `ψ = 0`, and (1.22) is identically zero. Omitting the subtraction
adds `½ ρ_air A_T C_X(0) |v_g|² = 379.75 × 51.87 = 19.7 kN` at service speed to **every leg of
every route, uniformly** — 2.5 % of `R_calm(V_ref)`. That is the worst kind of error: it never
looks wrong, and it biases every comparison in the same direction so it never shows up as an
inconsistency.

Note `V_rel` uses the **ground** velocity, not the through-water velocity: air does not know
about the current. The distinction is worth up to a metre per second in the Agulhas.

**The coefficient.** A four-term Fourier series in the apparent wind angle,

```
C_X(ψ) = a₀ + a₁ cos ψ + a₂ cos 2ψ + a₃ cos 3ψ ,   (a₀,a₁,a₂,a₃) = (0.05, 0.80, 0.10, 0.05)
                                                                              (1.23)
```

giving `C_X(0) = 1.00` head-on and `C_X(π) = −0.70` dead astern, both by construction. Via
`cos 2ψ = 2c² − 1` and `cos 3ψ = 4c³ − 3c` with `c := cos ψ`, (1.23) is exactly the cubic

```
C_X = (a₀−a₂) + (a₁−3a₃) c + 2a₂ c² + 4a₃ c³
    = −0.05 + 0.65 c + 0.20 c² + 0.20 c³                                      (1.24)
```

Use (1.24), not (1.23): the hot path holds a wind vector and a heading vector, whose
normalised dot product **is** `c`, so (1.23) costs four transcendentals and an angle wrap to
arrive back where it started. Two derived properties of (1.24) are used later:

> **Lemma 1.3 (Shape of `C_X`).** With the coefficients of (1.23), the cubic (1.24) is
> **strictly increasing** on `c ∈ [−1,1]`, hence `−0.70 ≤ C_X ≤ 1.00` and `|C_X| ≤ 1`.
> Moreover `C_X` vanishes at `c* = 0.075 3`, i.e. `ψ* = 85.68°`.
>
> *Proof.* `dC_X/dc = 0.65 + 0.40c + 0.60c²`, a quadratic with discriminant
> `0.40² − 4(0.60)(0.65) = 0.16 − 1.56 = −1.40 < 0` and positive leading coefficient, so it is
> strictly positive for all real `c`; hence `C_X` is strictly increasing and attains its
> extremes at `c = ±1`, namely `C_X(1) = −0.05+0.65+0.20+0.20 = 1.00` and
> `C_X(−1) = −0.05−0.65+0.20−0.20 = −0.70`. Strict monotonicity gives a unique root; solving
> `−0.05 + 0.65c + 0.20c² + 0.20c³ = 0` gives `c* = 0.075 3`, `ψ* = arccos(0.075 3) = 85.68°`.
> ∎

(The sign change is often quoted "near 80°"; the value implied by (1.23) is 85.7°, and 85.7°
is what an implementation will reproduce.)

**Limitations.** No lateral force, hence no wind-induced yaw and no rudder-drag penalty for
holding a heading in a beam wind. That penalty is real — of order a few percent of resistance
in a strong beam wind, though we have not measured it — and is **not modelled anywhere in
KAIROS**. `C_X` is even in `ψ`, correctly: the longitudinal force does not care which bow the
wind is on. A vessel with an unusual profile (car carrier, boxship with a high deck stow)
must override (1.23); the *shape*, more than the magnitude, is what matters.

### 1.3.5 The monotonicity lemma and the attainable-speed map

> **Def 1.3 (Attainable speed).** For throttle `q ∈ [q_min, 1]` and heading `θ`,
> ```
> 𝒮(q,θ) := connected component containing 0⁺ of { V ∈ (0, V_hull] : P_D(V,θ) ≤ q·P_MCR }
> V_pwr(q,θ) := sup 𝒮(q,θ)      (0 if 𝒮 is empty)                              (1.25)
> ```

Def 1.3 is deliberately *not* "the largest `V` with `P_D ≤ qP_MCR`". A ship accelerates
continuously from rest; a speed lying beyond a power hump the engine cannot climb is not
attainable however comfortable the power balance looks once you are past it. Under Lemma 1.4
the two definitions coincide and the distinction is invisible; when they differ, (1.25) is the
physical one.

> ### Lemma 1.4 (Strict monotonicity of delivered power; uniqueness of the attainable speed)
>
> Fix `x, t, θ`. Write `U := |W₁₀| + |c|` for the environmental speed scale,
> `a := ½ ρ_air A_T`, and suppose:
>
> **(i)** `P_calm` satisfies (H1) and is differentiable on `(0,V_hull]` with
> `dP_calm/dV ≥ p₀(V) > 0`;
> **(ii)** `R_AW ≥ 0` and is independent of `V`;
> **(iii)** for all `V ∈ (0, V_hull]`,
> ```
> p₀(V)  >  (a/η_D) · [ 1.7 (V+U)² + 2V(V+U) ]                                (1.26)
> ```
>
> Then `P_D(·,θ)` is **strictly increasing** on `(0,V_hull]`. Consequently, for every
> `q ∈ (0,1]` the equation `P_D(V,θ) = q P_MCR` has **at most one** root, `𝒮(q,θ)` is the
> interval `(0, V_pwr]`, and `V_pwr(·,θ)` of Def 1.3 is single-valued, continuous, and
> non-decreasing in `q`.
>
> **Proof.** Differentiate (1.14):
> ```
> dP_D/dV = dP_calm/dV + R_AW/η_D + (a/η_D) · d/dV[ (A(V) − B(V)) · V ]       (1.27)
> ```
> where, writing `r := V_rel = W₁₀ − v_g`, `ρ := |r|`, `m := −⟨r, n⟩/ρ = cos ψ`, and `f` for
> the cubic (1.24),
> ```
> A(V) := C_X(ψ)|V_rel|² = ρ² f(m) ,        B(V) := C_X(0)|v_g|² = |v_g|²
> ```
> (`C_X(0)=1` by Lemma 1.3). The second term of (1.27) is `≥ 0` by (ii).
>
> *Step 1 — the derivative of the gross aerodynamic term is exactly `ρΦ(m)`.* Since
> `v_g = Vn + c` we have `dr/dV = −n`, hence
> ```
> dρ/dV = ⟨r/ρ, −n⟩ = m ,
> dm/dV = −[ ⟨−n,n⟩ρ − ⟨r,n⟩ (dρ/dV) ] / ρ² = −[ −ρ + (−mρ)(m) ]/ρ² = (1−m²)/ρ
> ```
> using `⟨r,n⟩ = −mρ` and `|n| = 1`. Therefore
> ```
> dA/dV = 2ρ (dρ/dV) f(m) + ρ² f'(m) (dm/dV) = ρ [ 2m f(m) + (1−m²) f'(m) ] =: ρ Φ(m)
>                                                                              (1.28)
> ```
> *Step 2 — `Φ > 0`.* With `f(m) = −0.05 + 0.65m + 0.20m² + 0.20m³` and
> `f'(m) = 0.65 + 0.40m + 0.60m²`, expanding (1.28):
> ```
> 2m f(m)      = −0.10m + 1.30m² + 0.40m³ + 0.40m⁴
> (1−m²) f'(m) =  0.65 + 0.40m − 0.05m² − 0.40m³ − 0.60m⁴
> Φ(m)         =  0.65 + 0.30m + 1.25m² − 0.20m⁴                               (1.29)
> ```
> `Φ'(m) = 0.30 + 2.50m − 0.80m³` has its only root in `[−1,1]` at `m = −0.120 6` (bracketed
> by `Φ'(−0.12) = +1.38×10⁻³` and `Φ'(−0.121) = −1.1×10⁻³`; `Φ'' = 2.50 − 2.40m² > 0` on
> `[−1,1]`, so `Φ'` is strictly increasing there and the root is unique), giving
> ```
> Φ_min = Φ(−0.120 6) = 0.631 96 ,   Φ(0) = 0.65 ,   Φ(−1) = 1.40 ,   Φ_max = Φ(1) = 2.00
> ```
> So `0.632 ≤ Φ ≤ 2.00`: **the gross aerodynamic term is strictly increasing in `V`, always.**
> The non-monotone risk comes entirely from the still-air subtraction `B` and from `A` being
> negative in a following wind.
>
> *Step 3 — a lower bound on the bracket in (1.27).* From `f ≥ −0.70` (Lemma 1.3),
> `A ≥ −0.70 ρ²`; `B = |v_g|² ≥ 0` and `dB/dV = 2⟨v_g, n⟩ ≤ 2|v_g|`; and `dA/dV = ρΦ ≥ 0` by
> Step 2, which may be discarded from a lower bound. With `|v_g| ≤ V + |c| ≤ V + U` and
> `ρ ≤ |W₁₀| + |v_g| ≤ V + U`:
> ```
> d/dV[(A−B)V] = (A−B) + V(dA/dV − dB/dV)
>              ≥ −0.70ρ² − |v_g|² + 0 − 2V|v_g|
>              ≥ −0.70(V+U)² − (V+U)² − 2V(V+U)
>              = −[ 1.7(V+U)² + 2V(V+U) ]                                      (1.30)
> ```
> *Step 4.* Substituting (1.30) into (1.27) and using (i) and (ii),
> `dP_D/dV ≥ p₀(V) − (a/η_D)[1.7(V+U)² + 2V(V+U)] > 0` by (iii). Strict monotonicity gives
> injectivity, hence at most one root; the sublevel set of a strictly increasing continuous
> function is an interval containing `0⁺`, so `𝒮 = (0, V_pwr]`. Monotonicity of `V_pwr` in `q`
> is monotonicity of that sublevel set in `q`, and continuity follows from strict monotonicity
> of `P_D` plus the intermediate value theorem. ∎

**Is hypothesis (iii) satisfied?** For the reference vessel, `a = ½(1.225)(620) = 379.75`,
`a/η_D = 558.46`, and `p₀(V) = 65 845.8 V²` from (1.17). Condition (1.26) reads

```
65 845.8 V²  >  558.46 · [ 1.7 (V+U)² + 2V(V+U) ]                             (1.31)
```

| `U` [m/s] | condition (1.31) holds for | at `V = V_ref = 7.202`: LHS / RHS |
|---|---|---|
| 5 (light) | `V > 0.75 m/s` | 3.42 MW / 0.13 MW = **26×** |
| 10 (fresh) | `V > 1.49 m/s` | 3.42 MW / 0.32 MW = **10.7×** |
| 20 (gale) | `V > 2.95 m/s` | 3.42 MW / 0.92 MW = **3.71×** |
| 30 (storm) | `V > 4.42 m/s` | 3.42 MW / 1.83 MW = **1.87×** |

*(e.g. at `U = 20`, `V = 7.202`: `1.7(27.202)² + 2(7.202)(27.202) = 1 258.0 + 391.8 = 1 649.8`,
times `558.46` = `921.3 kW/(m/s)`, against `65 845.8 × 51.872 = 3 415.6 kW/(m/s)`.)*

The relevant comparison is against the **lowest attainable speed**, not against zero. From
(1.15)–(1.16), the calm-water speed at throttle `q` is

```
V_pwr(q) = V_ref · ( q P_MCR / P_ref )^{1/n}                                  (1.32)
V_pwr(1)     = 7.202 222 × (1.341 463)^{1/3} = 7.943 4 m/s  (15.44 kt)
V_pwr(q_min) = V_pwr(1) × 0.15^{1/3} = 7.943 4 × 0.531 33 = 4.220 2 m/s  (8.20 kt)
                                                                              (1.33)
```

So the entire admissible throttle range lives at `V ≥ 4.22 m/s` in calm water, comfortably
above the thresholds in the table up to storm-force `U`. **Lemma 1.4 therefore holds
throughout the operational envelope of the reference vessel**, with a margin of at least 1.9×
at `U = 30 m/s`. Below `V ≈ 3 m/s` in a gale the bound is inconclusive — note *inconclusive*,
not violated: (1.30) uses simultaneous worst-case alignment of three vectors that cannot in
fact be simultaneously worst. The regime is unreachable anyway, since it corresponds to
`q ≈ 0.05 < q_min`.

Note also the ratio `V_pwr(q_min)/V_pwr(1) = q_min^{1/3} = 0.5313`, which is ERRATA E9's
observation: **the reference vessel cannot stop.** `0 ∉ 𝒱` whenever `|c| < V_min`, and E9
records that the draft's own default configuration is a counterexample to the draft's own
"finite iff `0 ∈ 𝒱`" lemma. §1.4.7 states the corrected version.

### 1.3.6 What to do when the supplied speed–power spline is non-monotone

A badly conditioned fit through sea-trial points will produce a hump; so, for some hulls, will
the physics, near the hump speed. Then (H1) fails and Lemma 1.4 does not apply. The response
is a rule, a detector, and an honest statement of what is lost.

**Rule (normative).** Keep Def 1.3 exactly as written: `V_pwr(q,θ)` is the supremum of the
connected component of the sublevel set containing `0⁺`, which for a non-monotone `P_D` is the
**smallest** root of `P_D(V,θ) − q P_MCR`. Never the largest.

> **Prop 1.5 (The smallest root is the attainable one).** Suppose `P_D(·,θ)` is continuous on
> `[0,V_hull]` with `P_D(0)=0`, and let `V₁ < V₂` be two roots of `P_D = qP_MCR` with
> `P_D > qP_MCR` somewhere on `(V₁,V₂)`. Then no trajectory of the vessel starting from rest
> and respecting the power bound `P_D(V(s)) ≤ qP_MCR` at all times reaches a speed in
> `(V₁, V₂]`.
>
> *Proof.* `V(·)` is continuous along a trajectory (the vessel has finite mass, hence finite
> acceleration, hence absolutely continuous speed). Suppose `V(s₁) = 0` and `V(s₂) ∈ (V₁,V₂]`
> for some `s₂ > s₁`. Let `V̄ ∈ (V₁,V₂)` be a point with `P_D(V̄) > qP_MCR`, which exists by
> hypothesis; if `V(s₂) ∈ (V₁, V̄]` pick instead any `V̄' ∈ (V₁, V(s₂))` with
> `P_D(V̄') > qP_MCR` — such a point exists because `P_D(V₁) = qP_MCR` and `P_D` exceeds
> `qP_MCR` immediately to the right of `V₁` (otherwise `V₁` would not separate the component).
> By the intermediate value theorem there is `s̄ ∈ (s₁,s₂)` with `V(s̄) = V̄'`, at which
> `P_D(V(s̄)) > qP_MCR`, violating the power bound. ∎

The proof also identifies the hypothesis that makes it work: **the power constraint is
enforced continuously along the trajectory**, not just at the endpoints. That is the physical
content of "the ship cannot jump across a hump it has not the power to climb".

**Detector.** Evaluate `P_calm` (and, if the RAO path (1.21) is used, `P_D`) at `N_scan`
uniform samples of `(0, V_hull]` and report every adjacent pair with `P(V_{i+1}) ≤ P(V_i)`.
Log the interval. `N_scan = 32` is the reference value; it resolves an excursion no narrower
than `V_hull/N_scan = 8.488/32 = 0.265 m/s`. **A power excursion narrower than that falls
between samples and is missed**, and the returned speed then lies on the far side of it. No
fixed sampling can do better without an a-priori bound on the spline's curvature; raise
`N_scan` if the vessel's measured curve is known to be spiky. This is a real, unremovable
limitation of the procedure, not a tuning parameter.

**What is lost.** With a hump present, `V_pwr(·,θ)` remains non-decreasing in `q` (the
sublevel set grows with `q`), but it is **discontinuous**: at the throttle `q_h` whose power
equals the hump peak, the component suddenly connects to the far side and `V_pwr` jumps up.
Since the sublevel set is defined by `≤`, the jump is attained at `q_h` itself, so
`V_pwr(·,θ)` is right-continuous, hence **upper semicontinuous**, with at most countably many
jumps. Three consequences:

1. Prop 1.7 (time collapses the throttle family) survives untouched: it needs only
   monotonicity of `V_pwr` in `q`, which survives.
2. The achievable `(σ, fuel)` trace of §1.4.5 acquires gaps. A *minimum* over `q` of a
   quantity that is not lower-semicontinuous may fail to be attained. The practical
   resolution is the one the algorithm uses anyway: minimise over a **finite throttle sample
   set** `q ∈ {q_min = q^{(1)} < … < q^{(n_q)} = 1}` (`n_q = 5` default). The minimum over a
   finite set is always attained, and the returned family is a *subset* of the true one, so
   the reported fuel is an **achievable upper bound** — the conservative direction.
3. The admissible control set of Def 1.6 may fail to be closed, so Prop 1.7's `max` may fail
   to be attained in the continuum. The finite sample restores attainment for the same reason.

**What not to do.** Do not silently monotonise the curve. If the hump is a fitting artefact,
refit with a shape-preserving monotone interpolant (monotone cubic Hermite / PCHIP through
the trial points) and say so in the vessel record. If the hump is real, keep it and accept the
discontinuity — smoothing it would hand the solver a speed the ship cannot reach.

---

## 1.4 Throttle as an explicit control (decision D1)

> This is the section the rest of the multi-objective apparatus rests on. The claim is narrow
> and provable: **the time objective collapses the throttle family to one point per direction;
> the fuel objective does not.** That asymmetry is what makes `𝒱(x,t)` a two-dimensional
> filled region rather than a curve, and it is what makes vector-valued labels necessary
> rather than ornamental. Prior art for carrying vector labels through front propagation is
> Kumar & Vladimirsky (2010) and, for the ε-bucketing, Tsaggouris & Zaroliagis (2009)
> (ERRATA E11); the throttle family itself is the part we claim, and only as a modelling
> decision, not a theorem.

### 1.4.1 The control and the control-to-velocity map

The control is the pair `(q, θ) ∈ [q_min, 1] × S¹`. It maps to a ground velocity in two steps:

```
(q, θ)  ──Def 1.3──►  V = V_pwr(q, θ; x, t)  ──(1.9)──►  v = V n(θ) + c(x,t)  (1.34)
```

`q` is the fraction of MCR *delivered*, so available power is `q P_MCR` and, at the root of
Def 1.3, delivered power equals available power exactly:

```
P_D( V_pwr(q,θ), θ ) = q P_MCR      whenever  V_pwr(q,θ) < V_hull             (1.35)
```

with `<` replaced by the hull cap when the cap binds (then `P_D < qP_MCR` and the surplus
power is unusable). (1.35) is what lets the fuel model in §1.6 be written as a function of `q`
alone rather than requiring a second power evaluation.

`q_min = 0.15` is the engine's minimum stable load, below which a two-stroke main engine
cannot run continuously. It is a **hard** lower bound: the ship cannot throttle below it and
cannot stop without shutting down and losing steerage way. This is why `0 ∉ 𝒱` for the
reference vessel in weak drift (E9), and why "hold station" is a property of `conv 𝒱`, not of
`𝒱` (§1.4.7).

### 1.4.2 The crab-angle fixed point

The solver asks for progress in a **ground** direction `u`; the vessel is steered on a
**heading** `θ`. These differ whenever the drift has a cross-track component. Decompose the
drift relative to `u`:

```
c_∥ := ⟨c, u⟩ ,    c_⊥ := ⟨c, u^⊥⟩ ,    u^⊥ := (u_N, −u_E)                    (1.36)
```

For `v = V n(θ) + c` to be parallel to `u` with positive sense, the cross-track component must
cancel exactly:

```
V sin(θ − χ(u)) + c_⊥ = 0     ⟹     θ = χ(u) − arcsin( c_⊥ / V )              (1.37)
```

which requires `|c_⊥| ≤ V`. The resulting speed made good is then

```
σ = V cos(θ − χ(u)) + c_∥ = sqrt(V² − c_⊥²) + c_∥                             (1.38)
```

(1.38) is the Randers/Zermelo closed form and it is the object validated by the handbook's
golden vectors G2: at `V_s = 7.2`, `(c_∥, |c_⊥|) = (0,0) → σ = 7.2`; `(+1.5, 0) → 8.7`;
`(−1.5, 0) → 5.7`; `(0, 1.5) → 7.042 016 756 583 30`; `(+1.299 038 105 676 66, 0.75) →
8.459 869 063 044 66`. Any implementation must reproduce those to 12 significant figures.

But `V` in (1.37) is itself a function of `θ` — resistance depends on heading through both
`R_AW(β(θ))` and `R_AA(ψ(θ))`. So (1.37) is a **fixed-point equation**:

```
θ = Ψ(θ) := χ(u) − arcsin( c_⊥ / V_pwr(q, θ) )                                (1.39)
```

> **Lemma 1.6 (Existence, uniqueness and convergence of the crab-angle fixed point).**
> Fix `x, t, q, u`. Let `L_θ := sup_θ |∂V_pwr/∂θ|` and suppose `V_pwr(q,·) ≥ V_ > |c_⊥|` on
> `S¹` (so the arcsin is defined) and `V_pwr(q,·)` is `C¹`. If
> ```
> L_θ · |c_⊥|  <  V_ · sqrt( V_² − c_⊥² )                                     (1.40)
> ```
> then `Ψ` is a contraction on `S¹`, the fixed point exists and is unique, and the Banach
> iteration `θ_{k+1} = Ψ(θ_k)` converges linearly with rate
> `κ_Ψ = L_θ|c_⊥| / (V_ sqrt(V_²−c_⊥²))`.
>
> *Proof.* Write `γ(θ) := c_⊥/V_pwr(q,θ)`, so `Ψ = χ(u) − arcsin γ`. Then
> ```
> Ψ'(θ) = − γ'(θ) / sqrt(1 − γ²) ,   γ'(θ) = − c_⊥ V_pwr'(θ) / V_pwr²
> ```
> hence `|Ψ'| = |c_⊥| |V_pwr'| / ( V_pwr² sqrt(1 − c_⊥²/V_pwr²) ) =
> |c_⊥||V_pwr'| / ( V_pwr sqrt(V_pwr² − c_⊥²) )`. The right side is decreasing in `V_pwr`
> for `V_pwr > |c_⊥|` (both factors in the denominator increase), so it is bounded by its
> value at `V_pwr = V_`, giving `|Ψ'| ≤ L_θ|c_⊥| / (V_ sqrt(V_²−c_⊥²)) = κ_Ψ`. Under (1.40),
> `κ_Ψ < 1`; `S¹` is complete; Banach's fixed-point theorem applies. ∎

**Is (1.40) satisfied?** `L_θ` is the heading sensitivity of the attainable speed. Its
dominant contribution is the wave term: from (1.18)–(1.19), `|dR_AW/dβ| ≤ 0.45 K_AW H_s²`,
which at `H_s = 4 m` is `0.45 × 133 778 = 60 200 N/rad`. Converting to a speed sensitivity by
implicit differentiation of `P_D = qP_MCR`,

```
|∂V_pwr/∂θ| = (V/η_D)·|∂R_tot/∂θ| / (∂P_D/∂V)
            ≈ (7.2/0.68) × 60 200 / 3.42×10⁶ = 0.186 m/s per rad              (1.41)
```

with a comparable contribution from `R_AA` in a strong wind; take `L_θ ≈ 0.5 m/s/rad` as a
generous bound in a rough sea. Then with `V_ = 7 m/s` and `|c_⊥| = 2 m/s`, (1.40) reads
`0.5 × 2 = 1.0 < 7 × sqrt(49−4) = 46.96` — satisfied by a factor of **47**. Two or three
iterations of (1.39) from `θ₀ = χ(u) − arcsin(c_⊥/V_pwr(q, χ(u)))` reach machine precision.

**Where it fails, and what that means.** `κ_Ψ → ∞` as `|c_⊥| → V_`, i.e. exactly as the
cross-track drift approaches the through-water speed. That is golden-vector **T8**: the ship
is set sideways faster than it can crab back, no heading holds the track, and the correct
answer is `σ = 0`, `F = +∞`, **direction excluded** — not an exception, because it is a
routine physical condition in the Agulhas and the Somali Current and it must not abort a
voyage plan. So the fixed point degenerates precisely where the direction it is solving for
becomes infeasible; the two failures coincide and the implementation needs one test, not two.

### 1.4.3 The per-direction achievable family

> **Def 1.7 (Achievable family in a direction).** For `x, t` and a unit ground direction `u`,
> ```
> 𝔉(x,t,u) := { ( σ(u,q), ṁ(q), ρ_R(q), ρ_C(q) ) : q ∈ 𝒬_adm(x,t,u) }         (1.42)
> ```
> where for each `q`, `θ_q` solves (1.39), `V_q = V_pwr(q,θ_q)`,
> `σ(u,q) = sqrt(V_q² − c_⊥²) + c_∥` by (1.38), the rates are those of §1.6, and
> ```
> 𝒬_adm(x,t,u) := { q ∈ [q_min,1] : (1.39) is solvable and (V_q, θ_q) violates no ban S1–S7 }
>                                                                              (1.43)
> ```

This is decision **D1** made concrete: *a direction does not have a speed, it has a curve of
`(speed, fuel, risk)` triples.* The interface obligation (CONTRACT §4) is that
`legs(x, t, u)` returns the Pareto-non-dominated subset of (1.42), ordered by decreasing `σ`,
with an empty sequence meaning `F = +∞` in that direction.

Two structural facts about `𝒬_adm` that implementations get wrong:

- **It is not an interval.** S3 (surf-riding) bans *high* speed, S1/S2/S6 ban *bands* of
  encounter frequency, which by §1.5 are bands in `V cos μ_rel`. A direction can therefore be
  admissible at `q = 0.3` and at `q = 1.0` but banned at `q = 0.6`. Code that finds the
  largest admissible `q` by bisection from the top is wrong.
- **It is closed** whenever `V_pwr(·,θ)` is continuous (Lemma 1.4 holds). The bans are
  `sev_i(V,θ) > 1` with `sev_i` continuous (§1.5), so `𝒬_adm` is the preimage of a closed set
  under a continuous map intersected with a compact interval: compact. Hence maxima over
  `𝒬_adm` are attained. Under a non-monotone spline this fails and the finite throttle sample
  of §1.3.6 is what restores it.

### 1.4.4 Time collapses the family — statement and proof

> ### Prop 1.7 (The time objective collapses the throttle family)
>
> **(a)** `σ(u, ·)` is non-decreasing on `𝒬_adm(x,t,u)`, and strictly increasing wherever
> `V_pwr(·,θ_q)` is strictly increasing.
>
> **(b)** Define the **time-optimal throttle** and the minimum-time metric
> ```
> q*(x,t,u) := arg max { σ(x,t,u,q) : q ∈ 𝒬_adm(x,t,u) } ,
> σ(x,t,u)  := σ(x,t,u,q*) ,      F(x,t,u) := 1/σ(x,t,u)                       (1.44)
> ```
> The max is attained whenever `𝒬_adm` is compact (§1.4.3). Then **for the single-objective
> earliest-arrival problem the throttle is not a free control at all**: an optimal control may
> be taken with `q(s) = q*(x(s), t(s), u(s))` at almost every `s`, where `u(s)` is the
> instantaneous ground direction of the optimal trajectory. The arrival-time field depends on
> the vessel model *only* through `σ` of (1.44).
>
> **(c)** `q* = 1` if and only if `1 ∈ 𝒬_adm(x,t,u)`. It is **not** true in general that the
> time-optimal throttle is full ahead.
>
> **Proof.**
>
> *(a)* Under Lemma 1.4, `V_pwr(·,θ)` is non-decreasing in `q` for each fixed `θ`. Let
> `q₁ < q₂` in `𝒬_adm` with fixed-point headings `θ₁, θ₂` and speeds `V₁, V₂`. By (1.38)
> along the same direction `u`, `σ(u,q) = sqrt(V_q² − c_⊥²) + c_∥` where `c_∥, c_⊥` depend
> only on `u` and `c`, **not on `q` or `θ`**. Hence `σ` is a strictly increasing function of
> `V_q` alone on `V_q > |c_⊥|`:
> ```
> ∂σ/∂V = V / sqrt(V² − c_⊥²) > 0                                             (1.45)
> ```
> So it suffices that `V₂ ≥ V₁`. Both are values of `V_pwr` at the *same* `q`-monotone family
> but at different headings, so this needs one more step: `θ_q` is determined by (1.37) as
> `θ_q = χ(u) − arcsin(c_⊥/V_q)`, and substituting into `P_D(V_q, θ_q) = q P_MCR` gives a
> scalar equation `G(V, q) := P_D(V, χ(u) − arcsin(c_⊥/V)) − qP_MCR = 0`. For fixed `q`,
> `∂G/∂V = ∂P_D/∂V + (∂P_D/∂θ)(c_⊥/(V² sqrt(1−c_⊥²/V²)))`, and by exactly the bound used in
> Lemma 1.6 the second term is smaller in magnitude than the first whenever (1.40) holds
> (there it was written as `|Ψ'| < 1`; here it is the same quantity multiplied by
> `∂P_D/∂θ / ∂P_D/∂V`, and (1.41) shows the ratio is `≈ 0.19/1 ≪ 1`). Hence `∂G/∂V > 0`,
> while `∂G/∂q = −P_MCR < 0`, so by the implicit function theorem `dV/dq = −G_q/G_V > 0`:
> `V_q` is strictly increasing in `q`. With (1.45), so is `σ`. Non-strict monotonicity in the
> statement covers the hull-cap plateau, where `V_q = V_hull` for all sufficiently large `q`.
>
> *(b)* Let `𝒜(x,t)` be the admissible control set (Def 1.8) and `𝒱(x,t)` the set of ground
> velocities it generates (Def 2.1). The minimum-time value function of the control system
> `ẋ ∈ 𝒱(x,t)` depends on `𝒱` only through its **gauge**, i.e. through `F(x,t,u) = 1/σ(x,t,u)`
> where `σ(x,t,u) = sup{ s > 0 : s·u ∈ 𝒱(x,t) }` — this is the definition of the Minkowski
> gauge (Def 2.2) and it is the standard dynamic-programming statement for a minimum-time
> problem with a compact velocity set. Now `𝒱(x,t)` is by (1.34) the union over `q` of the
> per-throttle velocity sets, so
> ```
> sup{ s : s u ∈ 𝒱(x,t) } = sup_{q ∈ 𝒬_adm(u)} σ(x,t,u,q)
> ```
> which is (1.44). Therefore two vessel models with the same `σ(·,·,·)` have the same arrival
> field, whatever their throttle families; and any measurable control achieving the value must
> use, at almost every time, a throttle attaining (or approaching) the supremum in the
> direction actually being travelled. Attainment makes "approaching" into "attaining". ∎
>
> *(c)* Immediate from (a) and the definition of `𝒬_adm`: `σ(u,·)` is non-decreasing, so its
> maximum over a compact `𝒬_adm ⊆ [q_min,1]` is at `max 𝒬_adm`, which equals 1 exactly when
> `1 ∈ 𝒬_adm`. ∎

**Remarks.**

- **What this buys.** The time-only solve never needs the family. That is why the interface
  carries a separate `sigma_max(x,t,u)` primitive alongside `legs(x,t,u)`: it is equivalent to
  `legs(...)[0].sog` but is allowed to be — and is — much cheaper, and most calls go to it.
- **The error Prop 1.7(c) prevents.** The routing literature routinely assumes "minimum time
  ⟹ full ahead" and drops throttle from the state. In flat calm that is right. In a seaway it
  is wrong, because the *high-speed* bans (S3 surf-riding, S7 under-keel clearance via squat,
  and the upper edge of the S2/S6 bands) can make `q = 1` inadmissible while `q = 0.7` is
  fine. A router that hard-codes `q = 1` then reports "no feasible direction" where a real
  master would simply ease the throttle. This is not hypothetical: §1.5.9 exhibits the
  under-keel case, where in 15 m of water the reference vessel is capped at 6.00 m/s.
- **What fails without compactness of `𝒬_adm`.** The `arg max` in (1.44) may not exist and
  `σ` becomes a supremum that is approached but not attained. The value function is unchanged
  (a supremum is enough for the dynamic programming argument), but no *optimal* control
  exists — only ε-optimal ones. The finite throttle sample restores attainment at the cost of
  a conservative `σ`, which is the safe direction (the router promises a speed it can hold).
- **What fails without Lemma 1.4.** `V_pwr` may jump; (a) survives (monotone, possibly
  discontinuous), (b) survives (it never used continuity), (c) survives. Prop 1.7 is robust to
  the non-monotone spline case. This is worth knowing: the collapse is the *stable* half of
  D1.

### 1.4.5 Fuel does not collapse

The corresponding statement for fuel is false, and it is false for a reason worth writing
down precisely, because the reason is *not* the one usually given.

Write the fuel rate (Def 1.11 below) as `ṁ(q) = SFOC(qP_MCR) · qP_MCR` and the **fuel per unit
distance made good**

```
φ(u,q) := ṁ(q) / σ(u,q)          [kg/m]                                       (1.46)
```

> ### Prop 1.8 (Every throttle is non-dominated; the family cannot be collapsed)
>
> Under Lemma 1.4 and (1.45), on any `u` with `𝒬_adm(u)` an interval and `ṁ` strictly
> increasing in `q`:
>
> **(a)** `σ(u,·)` is strictly increasing and `ṁ(·)` is strictly increasing, so **every**
> `q ∈ 𝒬_adm(u)` is Pareto-non-dominated for the pair (time, fuel) on that edge. The family
> (1.42) reduces to a single point only when `𝒬_adm(u)` is a singleton.
>
> **(b)** With the Admiralty cube law and the parabolic SFOC bowl of §1.6, `φ(u,·)` is
> **strictly increasing** in `q` in calm water, so the fuel-optimal steady throttle is
> `q_min` and the time-optimal is `q*`. The two ends of the family are the two objectives'
> optima and the interior is the trade-off.
>
> **(c)** `φ` has an interior minimum in `q` if and only if the SFOC curvature satisfies
> `κ ≥ 16/9 = 1.777…`. For the reference value `κ = 0.28` there is **no** interior minimum.
>
> **Proof.**
>
> *(a)* Strict monotonicity of `σ` is Prop 1.7(a). For `ṁ`: with
> `SFOC(q) = s_ref(1 + κ d(q)²)`, `d(q) = (q − q_opt)/q_opt`, the fuel rate is
> `ṁ(q) = s_ref P_MCR ψ(q)` with
> ```
> ψ(q) := q ( 1 + κ ((q−q_opt)/q_opt)² )                                      (1.47)
> ψ'(q) = 1 + κ d(q)² + 2κ q d(q)/q_opt
> ```
> At `q = q_min = 0.15`, `q_opt = 0.75`, `κ = 0.28`: `d = −0.8`, `ψ' = 1 + 0.28(0.64) +
> 2(0.28)(0.15)(−0.8)/0.75 = 1.1792 − 0.0896 = 1.0896 > 0`; `ψ'` is a quadratic in `q` with
> positive leading coefficient `3κ/q_opt²` and its minimum over `[q_min,1]` is at
> `q = 2q_opt/3 = 0.5`, where `ψ'(0.5) = 1 + 0.28(1/9) + 2(0.28)(0.5)(−1/3)/0.75 = 1.03111 −
> 0.12444 = 0.90667 > 0`. So `ψ' > 0` on `[q_min,1]` and `ṁ` is strictly increasing. Now if
> `q₁ < q₂` then `σ(q₁) < σ(q₂)` (less time) and `ṁ(q₁) < ṁ(q₂)`; neither dominates the other
> in the pair (time, fuel), because the shorter-time option is the dearer one. ∎
>
> *(b)–(c)* In calm water `σ = V_pwr(q) = V_pwr(1) q^{1/n}` with `n = 3` by (1.32), so from
> (1.46)–(1.47), up to a positive constant,
> ```
> φ(q) ∝ ψ(q) / q^{1/3} = q^{2/3} ( 1 + κ ((q−q_opt)/q_opt)² )                (1.48)
> ```
> Substituting `x := q/q_opt` and dropping positive constants, stationarity of (1.48) requires
> ```
> g(x) := (2/3)(1 + κ(x−1)²) + 2κ x(x−1) = 0
> ```
> Put `s := x − 1 ∈ [q_min/q_opt − 1, 1/q_opt − 1]`:
> `g = 2/3 + (2/3)κs² + 2κ(1+s)s = 2/3 + 2κ s + (8/3)κ s²`, a convex parabola in `s`
> minimised at `s* = −3/8`, with minimum value
> ```
> g_min = 2/3 + 2κ(−3/8) + (8/3)κ(9/64) = 2/3 − (3/4)κ + (3/8)κ = 2/3 − (3/8)κ  (1.49)
> ```
> `g_min ≥ 0 ⟺ κ ≤ (2/3)/(3/8) = 16/9`. So for `κ < 16/9`, `g > 0` everywhere and (1.48) is
> strictly increasing — no interior stationary point, minimum at the left endpoint `q_min`,
> proving (b). For `κ > 16/9`, `g < 0` on a neighbourhood of `s* = −3/8`, i.e.
> `q = 0.625 q_opt`, and (1.48) has an interior minimum there, proving (c). ∎

**Numerically, for the reference vessel** (calm water, from (1.32) and (1.47)):

| `q` | `V_pwr` [m/s] | `SFOC` [10⁻⁹ kg/(W·s)] | `ṁ` [kg/s] | `φ = ṁ/V` [kg/m] |
|---|---|---|---|---|
| 0.15 | 4.220 | 188.63 | 0.3112 | 0.0737 |
| 0.35 | 5.597 | 188.94 | 0.7274 | 0.1300 |
| 0.55 | 6.503 | 178.48 | 1.0798 | 0.1660 |
| 0.75 | 7.217 | 175.00 | 1.4438 | 0.2001 |
| 1.00 | 7.943 | 180.44 | 1.9849 | 0.2499 |

Strictly increasing, as Prop 1.8(b) says. Between `q_min` and `q = 1` the ship gains a factor
**1.88 in speed** and pays a factor **3.39 in fuel per metre**. That spread is the Pareto
front; it does not require an interior optimum and it does not require a bowl in the SFOC
curve at all.

> **Correction to handbook §S5.** The debugging playbook states that `fuel_per_mile(q)` "must
> have an interior minimum near `q ≈ 0.75`" and that a monotone-decreasing result indicates a
> constant `sfoc()`. Prop 1.8(c) shows that with the cube law an interior minimum requires
> `κ ≥ 16/9 ≈ 1.78`, i.e. an SFOC 178 % above optimum at zero load — far outside any real
> engine, and 6.3× the reference `κ = 0.28`. **The correct expectation is that
> `fuel_per_mile(q)` is strictly increasing**, and its being so is not a bug. The
> discriminating test for the symptom the playbook is chasing ("the Pareto front is a thin
> line") is the second one it gives: check that `legs()` returns 2–4 entries for a mid-ocean
> cell, and check that `φ(q_min)/φ(1)` is well below 1 — for the reference vessel it is
> `0.0737/0.2499 = 0.295`.

### 1.4.6 The per-edge Pareto set over throttle

Prop 1.8(a) says every `q` is non-dominated on the (time, fuel) pair. With a third objective
the picture is *not* monotone: the measured risk levels across the throttle family at one
mid-ocean point of the synthetic field (25 positions × 2 forecast times × 24 directions,
`n_θ = 24`, `n_q = 5`) are

```
q      = q_min … 1
risk   = 0.618  0.571  0.514  0.441  0.650        (non-monotone in q)
```

The non-monotonicity at both ends is real: it is the surf-riding and roll criteria of §1.5
exchanging which one is worst as the encounter frequency sweeps through `V cos μ_rel`. So the
per-edge problem is a genuine small Pareto problem in `k` objectives over `q`, not a sort.

**Abstract data type (D7).** The per-edge family is a `LegList`:

| Operation | Semantics | Complexity |
|---|---|---|
| `build(x,t,u)` | evaluate (1.42) at `n_q` throttle samples | `n_q · C_σ` |
| `prune()` | remove dominated entries, `k` objectives | `O(n_q² k)`, `n_q ≤ 8` |
| `best_time()` | first entry after sorting by `σ` desc | `O(1)` |
| `iterate()` | in decreasing `σ` | `O(1)` per entry |

`C_σ` is the cost of one `(σ, rates)` evaluation: `N_fp` crab-angle iterations (Lemma 1.6:
2–3), each requiring one attainable-speed solve, which is `N_scan + N_root ≈ 32 + 12 ≈ 44`
power evaluations. **Measured** on the reference implementation over 1 200 `sigma_max` calls:
**524.5 µs** with the full physics (STAwave-1 + Fujiwara + all seven criteria) against
**541.2 µs** with a reduced four-criterion model — i.e. the full model is marginally *cheaper*,
because both are dominated by the same power-evaluation count and the extra criteria are noise
beside it. Of 1 200 direction evaluations, 24 were infeasible under both. `n_q = 5` gives 2–4
surviving legs after pruning in a mid-ocean cell.

The `O(n_q²k)` pruning is quadratic but `n_q ≤ 8` makes it 64 comparisons; do not replace it
with a sweep-line, which is asymptotically better and empirically slower at this size.

### 1.4.7 Finiteness of the metric: the corrected statements (E9, E1)

> **Prop 1.9 (Finiteness — ERRATA E9, corrected form).** Let `𝒱 = 𝒱(x,t)` be the achievable
> ground-velocity set and `V_max(x,t) := max_{θ,q} V_pwr(q,θ)` the best through-water speed.
> Then, as three **separate** claims:
>
> **(i)** `F(x,t,u) < ∞` **iff** the ray `ℝ₊u` meets `𝒱`.
> **(ii)** `F(x,t,·)` is finite in **every** direction **iff** `0 ∈ int(star-hull 𝒱)`; under
> D4 (the solver works with `conv 𝒱`) this is equivalent to `0 ∈ int conv 𝒱`, i.e. to
> `|c| < V_max`.
> **(iii)** `0 ∈ 𝒱` is **false** whenever `|c| < V_min := min_{θ} V_pwr(q_min,θ)`, and is
> required by nothing.
>
> *Proof.* (i) is the definition of the gauge: `F(u) = inf{ 1/s : s u ∈ 𝒱, s>0 }`, finite iff
> some `s > 0` has `su ∈ 𝒱`. (ii) If `0 ∈ int(star-hull 𝒱)` then a ball `B(0,ε)` lies in the
> star-hull, so every ray meets it and `F ≤ 1/ε < ∞`. Conversely if every ray meets `𝒱` then
> every ray meets the star-hull in a segment from the origin, so the star-hull contains a
> star-shaped neighbourhood of 0; if in addition `σ(u) ≥ ε > 0` uniformly (which holds by
> compactness of `S¹` and lower semicontinuity of `σ`) that neighbourhood contains `B(0,ε)`.
> Under D4, `𝒱` is replaced by `conv 𝒱 ⊇ D(c, V_max) ∩ …`; in the throttle-max, ban-free case
> `conv 𝒱 = D(c, V_max)`, and `0 ∈ int D(c,V_max) ⟺ |c| < V_max`. (iii) `0 ∈ 𝒱` requires a
> control with `V n(θ) = −c`, i.e. `V = |c|`; but `V ≥ V_min > |c|` by hypothesis. ∎

The practical content of (iii): a ship with a minimum engine load **genuinely cannot hold
station**. The relaxation D4 is what lets it be treated as if it could — by alternating
headings, whose *average* velocity is zero — and that is D4 earning its keep, at the price of
the realisability gap (ERRATA E6.3, Thm 2.11 local form).

> **Prop 1.10 (The reachable cone — ERRATA E1, corrected form).** The draft's condition
> `|c| ≥ σ_max` is identically false, because in the drift direction
> `σ ≥ V_max + |c| > |c|` for any `V_max > 0`. The correct statement uses the **through-water**
> speed:
>
> - `0 ∈ int conv 𝒱(x,t)` **iff** `|c| < V_max(x,t)`.
> - When `|c| > V_max`, every achievable ground velocity lies in `D(c, V_max)`, which excludes
>   the origin. The reachable set of *directions* is the cone about `c` of half-angle
>   ```
>   α_reach = arcsin( V_max / |c| )                                           (1.50)
>   ```
>   and `F(x,t,u) = +∞` for every `u` outside it.
> - `|c| = V_max` exactly: the cone degenerates to a half-plane boundary; treat as excluded
>   (`F = +∞`) for strict safety.
>
> *Proof.* `𝒱 ⊆ D(c, V_max)` because `|v − c| = V ≤ V_max` by (1.9). The set of directions of
> points of `D(c,V_max)` is, for `|c| > V_max`, the set of `u` for which the ray `ℝ₊u` meets
> the disc; the extreme rays are the two tangents from the origin, which touch at distance
> `sqrt(|c|² − V_max²)` and subtend half-angle `arcsin(V_max/|c|)` about `c`. For `|c| = V_max`
> the origin is on the boundary and only the single tangent ray survives with `σ = 0`. ∎

Any implementer coding `if (norm_c >= sigma_max)` gets a branch that **never fires**, silently
running the fast path in exactly the cells where the theory says it must not. Everywhere
`σ_max` was used as a proxy for through-water speed, substitute `V_max`. The test is two
lines, not a special case.

Under the co-moving reduction this becomes the checkable outrun test of §1.8.

---

## 1.5 The seakeeping ban set S1–S7

**Source.** IMO **MSC.1/Circ.1228** (2007), *Revised guidance to the master for avoiding
dangerous situations in adverse weather and sea conditions*, which supersedes MSC/Circ.707.
Its Annex identifies the dangerous phenomena (surf-riding and broaching-to; reduction of
intact stability on a wave crest; synchronous rolling; parametric rolling; successive high
wave attack) and gives operational avoidance guidance in terms of encounter period, wave
length and ship speed. The circular is written **for a master looking at the sea**, not for a
solver: it gives period ratios and qualitative sectors, not inequalities with tolerances.
S1–S7 below are our **operationalisation** of it. Every threshold is flagged as either *from
the circular*, *from a cited standard*, or *ours*.

**Design invariant (load-bearing).** `violations` (discrete) and `risk_level` (continuous) are
the **same function**. Each criterion is scored by a severity normalised so that
`sev = 1` lies exactly on the regulatory boundary, and the ban is that severity thresholded at
1. A conjunctive criterion ("banned when A **and** B **and** C") takes the **min** of its
factor severities; a disjunctive one takes the **max**. Thresholding at 1 then reproduces the
boolean exactly, so

```
risk_level(V,θ) > 1   ⟺   violations(V,θ) ≠ 0                                 (1.51)
```

always, with no second tuned model to drift out of sync. And the severities are **continuous**
in `(V,θ)` even where the bans are not — required, because a risk field with jumps makes the
ε-dominance pruning of §5 flicker between adjacent stencil directions (playbook S6).

The four severity primitives, each continuous, each equal to 1 on its threshold and `> 1` on
the banned side, clamped to `[0, SEV_CAP = 10]`:

```
sev_above(x; x_th)     = x / x_th                        banned when x > x_th
sev_below(x; x_th)     = 2 − x / x_th                    banned when x < x_th
sev_within(x; μ, w)    = 2 − |x − μ| / w                 banned when |x−μ| < w
sev_between(x; lo, hi) = 2 − |log(x/√(lo·hi))| / (½log(hi/lo))
                                                          banned when lo < x < hi  (1.52)
```

`sev_between` works in **log** space because the wavelength band `[0.8L, 2.0L]` is a *ratio*
band: a wave 10 % longer than `2.0L` is as far outside as one 10 % shorter than `0.8L`, which
a linear midpoint would deny.

### 1.5.1 Kinematic preliminaries

```
μ_rel(θ) := | wrap_π( μ_w − θ ) | ∈ [0, π]      0 = following, π/2 = beam, π = head
ω_p      := 2π / T_p                            peak angular frequency        (1.53)
k        := solution of ω_p² = g k tanh(k d)    wave number (linear dispersion)
λ        := 2π / k                              wavelength
ω_e      := ω_p − k V cos μ_rel                 encounter frequency, SIGNED    (1.54)
ω_φ      := sqrt(g·GM) / k_xx                   natural roll frequency         (1.55)
```

`k_xx` in (1.55) is the roll gyradius **in metres**. CONTRACT §1 lists it that way; the
reference implementation stores it as a *fraction of beam* (`k_xx = 0.38`, so
`k_xx,metres = 0.38 × 32 = 12.16 m`). The two must not be confused — the resulting `ω_φ`
differs by a factor of `B`, which moves every resonance band by an order of magnitude.

Reference vessel: `ω_φ = sqrt(9.806 65 × 2.4)/12.16 = 4.851 39/12.16 = 0.398 963 rad/s`,
so the natural roll period is `T_φ = 15.749 s`. Cross-check against the empirical
`T_φ ≈ 2 C B / sqrt(GM)` with `C = 0.38`: `2(0.38)(32)/1.549 = 15.70 s`. ✓

The sign of (1.54) is kept. A negative `ω_e` means the ship is **overtaking** the wave system,
which is a physically distinct state from meeting it at the same `|ω_e|`. Criteria that only
care about resonance use `|ω_e|`; S3 uses the sign implicitly through its heading sector.

**The one geometric fact that organises the whole ban set.** By (1.54), `ω_e` depends on the
control only through the scalar

```
p := V cos μ_rel = ⟨ V n(θ) , ê_wave ⟩                                        (1.56)
```

the **signed along-wave component of the through-water velocity**, with `ê_wave` the unit
vector in the direction the waves travel towards. `ω_e` is *affine* in `p`. Therefore every
criterion phrased as a band in `|ω_e|` removes, in the through-water velocity plane
`{V n(θ) : V ∈ [V_min,V_max], θ ∈ S¹}`, a set bounded by **lines perpendicular to `ê_wave`** —
one or two parallel strips. This is the source of every non-convexity in §1.5 and it is what
`conv 𝒱` in D4 fills in.

The deep-water limit `k = ω_p²/g` is used wherever `k d > 10` (then `tanh(kd) = 1 − 4×10⁻⁹`);
below that the full dispersion relation is solved by Newton from an Eckart start. Using the
deep-water `k` in shallow water makes `λ` too long and `ω_e` wrong in the same cells where the
under-keel criterion S7 is about to bind, which is the worst place to be wrong.

### 1.5.2 S1 — Synchronous rolling

**Source:** MSC.1/Circ.1228, Annex, dangerous phenomenon "synchronous rolling motion":
resonance when the encounter period approaches the natural roll period. **Band width and
height gate are ours.**

```
S1 banned ⟺   | |ω_e| − ω_φ | < 0.10 ω_φ      AND      H_s > 2.5 m           (1.57)
sev_1 = min( sev_within(|ω_e|; ω_φ, 0.10 ω_φ) ,  sev_above(H_s; 2.5) )
```

The `±10 %` band is our numerical rendering of the circular's "≈"; the `H_s > 2.5 m` gate is
ours entirely and is operator-configurable — the circular gives no height floor, because it is
addressed to a master who can see whether the resonance matters. Without a floor, S1 removes
control space in a 1 m swell where resonant roll is a nuisance, not a hazard.

**Geometry.** `|ω_e| ∈ ((1−0.10)ω_φ, (1+0.10)ω_φ)` is two intervals in the signed `ω_e`, hence
by (1.56) two intervals in `p`:

```
p ∈ ( (ω_p − 1.1ω_φ)/k , (ω_p − 0.9ω_φ)/k )   ∪   ( (ω_p + 0.9ω_φ)/k , (ω_p + 1.1ω_φ)/k )
                                                                              (1.58)
```

i.e. **two parallel strips perpendicular to `ê_wave`**, intersected with the attainable
annulus `V ∈ [V_min, V_max]`. Each strip ∩ annulus is a lune bounded by two chords and two
arcs.

*Worked, reference vessel, `T_p = 10 s`, deep water:* `ω_p = 0.628 32`, `k = ω_p²/g =
0.040 257 rad/m`, `λ = 156.1 m`; `ω_φ = 0.398 963`, band `|ω_e| ∈ (0.359 07, 0.438 86)`.
First strip: `p ∈ (4.706, 6.688) m/s`. Second strip: `p ∈ (24.53, 26.51) m/s` — unreachable,
since `|p| ≤ V_max = 7.94`. So **one** strip is live: following and quartering seas with
`V cos μ_rel` between 4.71 and 6.69 m/s. At dead-following (`cos μ_rel = 1`) that is
`V ∈ [4.71, 6.69]`, which straddles most of the throttle range: the vessel must run either
slow (`V < 4.71`, i.e. below `V_min = 4.22`? no — infeasible) or fast (`V > 6.69`, i.e.
`q > 0.60`). **In this sea state S1 alone forces the throttle above `q ≈ 0.60` on a following
heading** — a concrete instance of Prop 1.7(c)'s warning, in the opposite direction.

### 1.5.3 S2 — Parametric rolling, and the geometry of the ring

**Source:** MSC.1/Circ.1228, Annex, "parametric roll motions", which identifies the head-sea
mechanism at `T_e ≈ T_φ/2` (i.e. `ω_e ≈ 2ω_φ`) with wave length comparable to ship length.
**Band width, wavelength band and height gate are ours.**

```
S2 banned ⟺   | |ω_e| − 2ω_φ | < 0.15 · 2ω_φ
          AND  0.8 L < λ < 2.0 L
          AND  H_s > 2.0 m                                                    (1.59)
sev_2 = min( sev_within(|ω_e|; 2ω_φ, 0.30 ω_φ),
             sev_between(λ; 0.8L, 2.0L),
             sev_above(H_s; 2.0) )
```

**This is the main source of non-convexity in the whole formulation**, so its geometry is
worth getting exactly right.

The second and third factors are **control-independent**: `λ` and `H_s` are properties of the
cell, not of `(V,θ)`. They act as an on/off switch for the entire criterion. Only the first
factor removes control space, and by (1.56) it removes the preimage of a band in `|ω_e|`,
i.e. the union of at most two strips

```
Σ± := { p : (ω_p ∓ 1.15·2ω_φ)/k  <  p  <  (ω_p ∓ 0.85·2ω_φ)/k }               (1.60)
```

Intersecting `Σ+ ∪ Σ−` with the attainable annulus `A := {V_min ≤ V ≤ V_max}` gives exactly
three possible geometries:

> **Prop 1.11 (Taxonomy of the S2 removed set).** Let `Σ` be an open strip
> `{p_lo < p < p_hi}` perpendicular to `ê_wave` and `A` the annulus `V_min ≤ |Vn| ≤ V_max`.
> Then:
>
> **(a) Empty.** If `[p_lo,p_hi] ∩ [−V_max, V_max] = ∅`, nothing is removed.
>
> **(b) Annular sector ("ring segment").** If `0 ∉ (p_lo, p_hi)`, the removed set
> `Σ ∩ A` is bounded by two chords and two arcs and does **not** surround the origin. The
> admissible set `A \ Σ` remains connected iff the strip does not cut all the way across `A`.
> At each speed `V`, the banned headings form the sector
> `cos μ_rel ∈ (p_lo/V, p_hi/V) ∩ [−1,1]`, which is empty for `V < min(|p_lo|,|p_hi|)` and
> shrinks again for `V > max(|p_lo|,|p_hi|)`.
>
> **(c) Ring.** If `p_lo < 0 < p_hi` and `V_min < min(|p_lo|, p_hi)`, then every point of `A`
> with `|Vn| < min(|p_lo|, p_hi)` satisfies `|p| ≤ V < min(|p_lo|,p_hi)`, hence lies in `Σ`.
> The removed set therefore contains the **entire annulus**
> `V_min ≤ V ≤ min(|p_lo|, p_hi)`, all headings, and `A \ Σ` is the outer ring
> `{ V > V_esc(θ) }` with `V_esc(θ) = p_hi/cos μ_rel` for `cos μ_rel > 0` and
> `|p_lo|/|cos μ_rel|` for `cos μ_rel < 0`, diverging as `μ_rel → π/2`. The admissible set is
> then **disconnected from the origin side**, and the only escape is to *go fast enough, in
> either direction, to Doppler-shift out of the band*.
>
> *Proof.* (a) is immediate. (b): `p = ⟨Vn, ê_wave⟩` so `|p| ≤ V`; the banned heading set at
> fixed `V` is `{μ_rel : V cos μ_rel ∈ (p_lo,p_hi)}`, which requires `V ≥ min(|p_lo|,|p_hi|)`
> since `|p| ≤ V`; the boundary curves `p = p_lo` and `p = p_hi` are straight lines, giving
> chords. Since `0 ∉ (p_lo,p_hi)`, the origin is not in `Σ`, so `Σ` does not surround it.
> (c): if `p_lo < 0 < p_hi` and `V < min(|p_lo|,p_hi)` then `p ∈ [−V,V] ⊂ (p_lo,p_hi)`, so
> **every** heading at that speed is banned; the union over `V ∈ [V_min, min(|p_lo|,p_hi)]` is
> the stated annulus. ∎

**Which case is the reference vessel in?** Case (b), and only just.

The wavelength gate `0.8L < λ < 2.0L` with `L = 190 m` and deep-water `λ = 2πg/ω_p²` is

```
152 m < 2πg/ω_p² < 380 m   ⟺   ω_p ∈ (0.402 68, 0.636 69) rad/s
                           ⟺   T_p ∈ (9.87, 15.61) s                          (1.61)
```

Case (c) requires `p = 0` to be inside the frequency band, i.e. `ω_p` itself in
`(0.85·2ω_φ, 1.15·2ω_φ) = (0.678 24, 0.917 62)`, i.e. `T_p ∈ (6.85, 9.27) s`. **The two
intervals (1.61) and (6.85, 9.27) are disjoint**, by a margin of 6.5 % in `ω_p`. So for the
reference vessel the ring never closes: at zero speed the vessel is never simultaneously in
the parametric band and in the admissible wavelength window.

**When does the ring close?** Case (c) needs `(0.85·2ω_φ, 1.15·2ω_φ)` to intersect
`(0.402 68, 0.636 69)`, i.e. `2ω_φ ∈ (0.402 68/1.15, 0.636 69/0.85) = (0.350 2, 0.749 0)`,
i.e.

```
ω_φ ∈ (0.175 1, 0.374 5) rad/s   ⟺   T_φ ∈ (16.8, 35.9) s
                                 ⟺   GM ∈ (0.462, 2.120) m                    (1.62)
```

*(from `ω_φ = sqrt(g·GM)/12.16`: `GM = (12.16 ω_φ)²/g`; `ω_φ = 0.3745` gives `GM = 2.120 m`,
`ω_φ = 0.1751` gives `GM = 0.462 m`.)*

The reference `GM = 2.4 m` sits **just above** the window. Load the same hull tender —
`GM = 1.6 m`, `T_φ = 19.3 s` — and the ring closes. That is not an artefact of our thresholds:
low-`GM` (tender) loading conditions are precisely the recognised parametric-roll risk case,
and the geometry reproduces it. It means the indicatrix topology is **load-condition
dependent**, and a router that caches the ban geometry across a voyage in which the vessel
deballasts is caching the wrong topology.

**Worked case (b), `T_p = 10 s`.** `ω_p = 0.628 32`, `k = 0.040 257`, `λ = 156.1 m ∈ (152,380)`
so the gate is open. Band `|ω_e| ∈ (0.678 24, 0.917 62)`; since `ω_p < 0.678`, only head-sea
components raise `ω_e` into the band, giving

```
p ∈ ( −7.186 , −1.240 ) m/s                                                   (1.63)
```

(the mirror strip `p ∈ (32.4, 38.4)` is unreachable). So at dead head (`cos μ_rel = −1`) the
banned speeds are `V ∈ (1.240, 7.186)`, which given `V_min = 4.220` and `V_max = 7.943` means
**the admissible head-sea speeds are only `V ∈ (7.186, 7.943]`, i.e. `q > 0.74`.** The vessel
must run near full ahead into the sea, or turn. At `T_p = 12 s` (`ω_p = 0.5236`,
`k = 0.027 957`, `λ = 224.8 m`) the strip is `p ∈ (−14.09, −5.531)` and the banned head-sea
speeds are `V ∈ (5.531, 7.943]` — the *whole* upper range, so the vessel must slow to
`V < 5.53 m/s` (`q < 0.36`) or turn. **The escape direction reverses between `T_p = 10 s` and
`T_p = 12 s`.** No monotone heuristic in speed can capture that, which is the concrete reason
the ban set must be evaluated rather than approximated.

### 1.5.4 S3 — Surf-riding and broaching-to

**Source:** MSC.1/Circ.1228, Annex, "surf-riding and broaching-to". The circular gives the
danger zone as an encounter angle within ±45° of following seas together with a ship speed
above a threshold stated dimensionally, `V > 1.8 sqrt(λ)` in knots with `λ` the wave length in
metres (divided by the cosine of the off-following angle). KAIROS uses the standard
Froude-number restatement:

```
S3 banned ⟺   Fn := V / sqrt(g L) > 0.30
          AND  μ_rel < π/4
          AND  λ > 0.8 L                                                      (1.64)
sev_3 = min( sev_above(Fn; 0.30), sev_below(μ_rel; π/4), sev_above(λ; 0.8L) )
```

> **The constant 0.30 is exactly the circular's threshold at `λ = L`.** Converting
> `1.8 sqrt(λ)` kn to SI: `1.8 × 0.514 444 = 0.926 0` m/s per `sqrt(m)`, so
> `Fn_th = 0.926 0 sqrt(λ) / sqrt(gL) = 0.295 66 sqrt(λ/L)`. At `λ = L` this is **0.2957**,
> i.e. 0.30 to two figures. The fixed 0.30 therefore *over-warns* for `λ > L` and
> *under-warns* for `λ < L`; the sharper form is
> ```
> Fn > 0.295 66 · sqrt( λ / L )                                              (1.65)
> ```
> and an implementation that wants to track the circular exactly should use (1.65). We keep
> 0.30 because it is the form in universal use and because the wavelength gate `λ > 0.8L`
> already excludes the region where the two differ most.

**Geometry.** `{Fn > 0.30}` is the exterior of a disc of radius `V_surf = 0.30 sqrt(gL)`;
`{μ_rel < π/4}` is a 90°-wide sector centred on `ê_wave`. The removed set is an **annular
sector** — a 90° wedge outside radius `V_surf` — switched on and off by the wavelength gate.

**For the reference vessel, S3 can never fire.** `V_surf = 0.30 sqrt(9.806 65 × 190) =
0.30 × 43.166 = 12.950 m/s = 25.2 kt`, against `V_hull = 8.488 m/s = 16.5 kt`. The criterion
binds only for vessels with

```
L < V_hull² / (0.09 g) = 72.052 / 0.882 60 = 81.6 m                           (1.66)
```

i.e. fishing vessels, small ro-ros and fast craft — which is exactly the population
MSC.1/Circ.1228 has in mind for surf-riding. **Say this out loud rather than letting the
criterion sit inert:** for a 190 m bulker S3 contributes only to the *continuous* risk level
(a severity below 1), never to the ban mask, and an implementation that reports "S3 never
fires" on this vessel is correct, not broken. It is also the reason the `bans_enabled` bitmask
exists.

### 1.5.5 S4 — Slamming

**Source:** Ochi (1964), *Prediction of the occurrence and severity of ship slamming at sea*,
5th Symposium on Naval Hydrodynamics — the two-condition model. Threshold probability from
NORDFORSK (1987), *Assessment of Ship Performance in a Seaway*: `0.03` for merchant vessels of
this size (`0.01` is used for container ships; NORDFORSK grades it with length).
MSC.1/Circ.1228's "successive high wave attack" is the qualitative counterpart.

Ochi's model: a slam requires the bow to **emerge** (relative vertical motion at the forward
perpendicular exceeding the local draft) **and** to re-enter faster than a threshold velocity.
Under a narrow-band Gaussian assumption the two events are jointly Rayleigh and independent in
the required sense, so the probability is the product of two exceedance probabilities:

```
P_slam = exp[ − T_d² / (2 m₀ʳ)  −  v_th² / (2 m₂ʳ) ] ,   v_th = 0.093 sqrt(g L)
S4 banned ⟺ P_slam > 0.03                                                     (1.67)
sev_4 = ( P_slam / 0.03 )^{1/3}
```

`m₀ʳ`, `m₂ʳ` are the zeroth and second spectral moments of the relative vertical motion at the
forward perpendicular. The cube root in `sev_4` only compresses six decades of probability into
an `O(1)` severity; it is monotone and fixes 1 at the threshold, so the ban boundary is
untouched. `v_th = 0.093 sqrt(9.806 65 × 190) = 4.014 m/s` for the reference vessel.

**What `m₀ʳ, m₂ʳ` should be, and what we use.** The correct object is

```
m_nʳ = 2 ∫∫ ω_e^n | H_r(ω, β; V) |² S(ω,β) dβ dω                              (1.68)
```

with `H_r` the relative-motion transfer function. That requires strip-theory or panel-code
output which a charterer does not publish. **We use a narrow-band surrogate**, and it is the
weakest link in S4 and S5:

```
σ_w  := H_s / 4                                (RMS surface elevation)
r    := λ / ( L · max(|cos μ_rel|, 10⁻³) )     (effective wave length along the hull)
gain := [ 1/(1 + 0.25 r²) ] · [ 1 + 1.2 exp( −((r − 1.2)/0.7)² ) ]
m₀ʳ  = (σ_w · gain)² ,      m₂ʳ = ω_e² m₀ʳ                                     (1.69)
```

built from three statements any relative-motion RAO satisfies: long waves (`λ ≫ L`) → the ship
contours the wave, relative motion → 0; short waves (`λ ≪ L`) → the ship ignores the wave,
relative motion → the wave amplitude; near `λ ≈ 1.2 L` → pitch resonance puts bow motion in
antiphase with the surface and the relative motion is amplified to roughly twice the wave
amplitude, which is where published RAOs for full-form hulls peak. The maximum of `gain` is
**1.685 at `r ≈ 1.0`**.

The geometric variable is the wavelength measured **along the hull**, `λ/|cos μ_rel|`, so beam
seas give a very long effective wave, no pitch, and therefore no slamming — the correct heading
dependence, and the reason S4 and S5 do not simply track `H_s`. Speed enters only through
`m₂ʳ = ω_e² m₀ʳ`, which reproduces the operational fact that **slamming is relieved by slowing
down in head seas** (slowing reduces `|ω_e| = ω_p + kV|cos μ_rel|`).

**Bias, stated:** the surrogate is calibrated to be right in the middle of the range and
conservative at the edges. It is a decision boundary. **Do not quote absolute slamming
probabilities from it.**

**Geometry.** `m₀ʳ` is independent of `V`; `m₂ʳ` depends on `V` only through `ω_e²`, hence
through `p` by (1.56). So the S4 region is `{ (V,θ) : ω_e(p)² > g₄(μ_rel) }` for an explicit
threshold `g₄` — the union of two half-planes in `p` whose boundaries depend on `μ_rel`. Its
intersection with the annulus is a **cap on the head-sea side that widens with speed**, plus a
mirror cap on the far following side when the vessel can overtake the waves (unreachable for
this vessel: `|ω_e| = 0` requires `p = ω_p/k = 15.6 m/s` at `T_p = 10 s`).

### 1.5.6 S5 — Green water on deck

**Source:** the same relative-motion statistic measured against freeboard; threshold
probability `0.05` from NORDFORSK (1987).

```
P_gw = exp[ − f_b² / (2 m₀ʳ) ] ,        S5 banned ⟺ P_gw > 0.05               (1.70)
sev_5 = ( P_gw / 0.05 )^{1/3}
```

**Geometry — and this one is structurally different.** `m₀ʳ` in (1.69) is **independent of
`V`**. Therefore *under this surrogate* S5 removes a set that depends on **heading only**: a
pair of sectors about the wave axis, at **all** speeds. In the through-water velocity plane it
is a double wedge from the origin, not a strip.

That is a modelling artefact, and it must be named as one: a real relative-motion RAO is
speed-dependent (forward speed changes the encounter spectrum and the pitch response), so the
true S5 region is a speed-dependent wedge. The RAO path (1.68) restores that. **What breaks
because of it:** the operational manoeuvre "slow down to stop taking green water" is invisible
to S5 as modelled; only S4 responds to speed. An operator relying on S5 alone would be told to
turn when easing the throttle would do.

**When does S5 fire at all?** From (1.70), `P_gw > 0.05` requires
`m₀ʳ > f_b²/(2 ln 20) = 42.25/5.991 5 = 7.051 7 m²`, i.e. RMS relative motion above `2.6555 m`,
i.e. `σ_w · gain > 2.6555`, i.e. with `gain ≤ 1.685`,

```
H_s > 4 × 2.6555 / 1.685 = 6.303 m                                            (1.71)
```

Since the operator envelope S7 bans everything above `H_s = 6.5 m` for this vessel,
**S5 governs only the window `6.30 m < H_s < 6.50 m`, and only at wave lengths near `L`.**
For the reference vessel it is very nearly shadowed by S7. That is worth knowing before
anyone spends effort tuning it; it also means (1.71) is the diagnostic to run when adding a
new vessel — a ship with low freeboard relative to its length will have S5 firing far below
its heavy-weather limit, and then S5 is the criterion that matters.

### 1.5.7 S6 — Lateral acceleration at the bridge

**Source:** NORDFORSK (1987) crew-habitability limits on RMS lateral acceleration; the value
used is `0.10 g` (NORDFORSK tabulates 0.10–0.12 g for merchant crews performing light manual
work, and 0.05 g for passengers). MSC.1/Circ.1228 does not give an acceleration limit; this
criterion is the habitability/cargo-securing counterpart to the stability criteria.

Roll is modelled as a linear single-degree-of-freedom response to wave slope:

```
slope_rms = k σ_w · s_eff · |sin μ_rel| ,      s_eff = 0.75
ρ_ω       = |ω_e| / ω_φ
φ_rms     = min( slope_rms / sqrt( (1−ρ_ω²)² + (2 ζ ρ_ω)² ) , 0.45 rad ) ,  ζ = 0.08
a_y       = φ_rms · ( g + h_br ω_e² ) ,        h_br = f_b + 0.40 B            (1.72)
S6 banned ⟺ a_y > 0.10 g ,      sev_6 = a_y / (0.10 g)
```

`s_eff = 0.75` is the effective wave-slope coefficient for a full-form hull (the IS Code
weather criterion uses 0.7–0.8 for this hull class); `ζ = 0.08` of critical is a bilge-keeled
full hull. `h_br = 6.5 + 0.40 × 32 = 19.3 m` is the bridge height above the roll axis taken at
the waterline, since the vessel record carries no bridge height. The `(g + h_br ω_e²)` factor
adds algebraically rather than in quadrature because for narrow-band roll about a waterline
axis the gravity component `g sin φ` and the tangential component `h φ̈` are both proportional
to `φ` and in phase. The cap `φ_rms ≤ 0.45 rad ≈ 26°` marks where the linear model is void;
it is reached only deep inside an already-banned region.

**Sway and yaw coupling are omitted.** For beam-sea roll they are second order at the bridge;
for a stern-quartering broach they are not — but a broach is already banned by S3 wherever the
vessel is fast enough to reach one, and for this vessel S3 never fires (§1.5.4), so **for a
large slow ship the omission is not covered by S3 and is a real gap.** Say so.

**Geometry.** `φ_rms` peaks on the S1 resonance strip (`ρ_ω = 1`) and is weighted by
`|sin μ_rel|`, so S6 removes approximately the **same strip as S1, widened**, with the removal
strongest where the strip crosses beam-ish headings and with an extra lever arm from the
`h_br ω_e²` term at high `|ω_e|`.

**Worked, reference vessel, `H_s = 4 m`, `T_p = 10 s`.** Roll resonance `ω_e = ω_φ` needs
`p = (ω_p − ω_φ)/k = (0.628 32 − 0.398 96)/0.040 257 = 5.697 m/s`. At `V = V_max = 7.943` that
is `cos μ_rel = 0.7173`, `μ_rel = 44.2°` (stern-quartering), `|sin μ_rel| = 0.6968`. Then
`slope_rms = 0.040 257 × 1.0 × 0.75 × 0.6968 = 0.021 04 rad`; at resonance the magnification is
`1/(2ζ) = 6.25`, so `φ_rms = 0.131 5 rad = 7.53°`; `a_y = 0.131 5 (9.806 65 + 19.3 × 0.159 17)
= 0.131 5 × 12.878 65 = 1.693 m/s²`, i.e. `sev_6 = 1.73` — **banned**. Solving for the height
at which it exactly fires gives `H_s = 2.32 m`. Compare S1 on the same geometry: `p = 5.697`
lies inside the S1 strip `(4.706, 6.688)` ✓, so S1 also fires, but only above its `H_s = 2.5 m`
gate. **S6 is therefore the binding roll criterion for this hull, firing about 8 % earlier in
`H_s` than S1**, and the two are co-located in the control plane.

### 1.5.8 S7 — Operator envelope

**Source:** not IMO. The wave-height limit is charter-party / operator policy; the under-keel
clearance requirement follows standard voyage-planning practice (IMO Res. A.893(21) on voyage
planning; PIANC guidance on UKC). The squat estimate is **ICORELS (1980)**.

This criterion is **disjunctive** (either condition bans), so the severity is a `max`:

```
squat(V) = 2.4 (∇/L²) Fn_h² / sqrt(1 − Fn_h²) ,     Fn_h = V/sqrt(g·d_b)
clearance = d_b − T_d − squat(V)
S7 banned ⟺ H_s > H_s^lim   OR   clearance < ukc_margin                       (1.73)
sev_7 = max( sev_above(H_s; H_s^lim) , ukc_margin/clearance )
```

with `H_s^lim = 6.5 m` and `ukc_margin = 2.0 m` for the reference vessel, and displacement
estimated as `∇ = C_B L B T_d = 0.80 × 190 × 32 × 11 = 53 504 m³` (the vessel record carries no
block coefficient; `C_B = 0.80` is a full-form default used **only** here). The ICORELS form is
self-limiting — it vanishes as depth grows, unlike the Barrass regressions — so it may be
evaluated in every cell rather than only in pilotage waters. `Fn_h²` is clamped at 0.95:
above `Fn_h = 1` the ship is supercritical and the formula is meaningless.

**Geometry — two completely different objects sharing one criterion.**

- The `H_s > H_s^lim` term is **control-independent**. It removes the *entire* control set or
  none of it. Structurally it is a **cell mask**, not a direction ban: it makes cells
  impassable. This matters for the algorithm — a cell mask can be applied once per cell, at
  `O(1)`, before any direction is evaluated.
- The UKC term is a pure **speed cap**: `squat` is strictly increasing in `V`, so the removed
  set is `{V > V_ukc(d_b)}` for **all** headings — the outer annulus. It is the only criterion
  in S1–S7 that is a clean speed cap, and it is the one that most often makes `q = 1`
  inadmissible while lower throttles are fine (Prop 1.7(c)).

**Worked, reference vessel.** `∇/L² = 53 504/36 100 = 1.482 1 m`, so
`squat(V) = 3.557 1 Fn_h²/sqrt(1−Fn_h²)`.

| depth `d_b` | `squat` at `V = 7.94` | clearance | verdict at full ahead |
|---|---|---|---|
| 40 m | 0.583 m | 28.42 m | clear |
| 20 m | 1.388 m | 7.61 m | clear |
| 15 m | 2.017 m | 1.983 m | **banned** |

At `d_b = 15 m` the speed cap is found by solving `squat = 1.0 m`:
`Fn_h²/sqrt(1−Fn_h²) = 0.281 13`, giving `Fn_h² = 0.244 38`, `Fn_h = 0.494 3`, and

```
V_ukc(15 m) = 0.494 3 × sqrt(9.806 65 × 15) = 0.494 3 × 12.128 = 6.00 m/s     (1.74)
```

So **in 15 m of water the reference vessel is throttle-capped at 6.00 m/s (`q ≈ 0.43`)** by
squat alone. A router that assumes `q = 1` reports this cell as banned; the correct answer is
"proceed at half power".

### 1.5.9 The admissible control set, and the summary of geometries

> **Def 1.8 (Admissible control set).**
> ```
> 𝒜(x,t) := { (q,θ) ∈ [q_min,1] × S¹ :
>              V := V_pwr(q,θ;x,t) ∈ (0, V_hull]  and  sev_i(V,θ) ≤ 1
>              for every i with bit i set in the vessel's bans_enabled mask }  (1.75)
> ```
> Its image under (1.9), `𝒱(x,t) := { V n(θ) + c(x,t) : (q,θ) ∈ 𝒜(x,t) }`, is the
> **indicatrix**, formally introduced as **Def 2.1** in `02-metric.md`.

*(Note on numbering: some source comments refer to the indicatrix as "Def 1.1". CONTRACT §1
assigns it **Def 2.1**, and CONTRACT is normative on numbering; §1 owns `𝒜`, §2 owns `𝒱`.)*

> **Prop 1.12 (Compactness).** If `V_pwr(·,·)` is continuous (Lemma 1.4 holds) then `𝒜(x,t)`
> is compact, hence `𝒱(x,t)` is compact and the suprema of (1.44) and Def 1.7 are attained.
>
> *Proof.* `[q_min,1] × S¹` is compact. Each `sev_i` is continuous in `(V,θ)` by construction
> (1.52) — each primitive is a composition of continuous functions and a clamp, and `min`/`max`
> of finitely many continuous functions is continuous — and `V_pwr` is continuous, so
> `(q,θ) ↦ sev_i(V_pwr(q,θ), θ)` is continuous. `𝒜` is the intersection of finitely many
> preimages of the closed set `(−∞,1]` with the compact domain, minus the open set
> `{V_pwr = 0}`; the latter is excluded because `V_pwr > 0` on `𝒜` is implied by
> `V_pwr ≥ V_pwr(q_min, ·) > 0` whenever the vessel is powered at all. Closed subset of a
> compact set is compact. `𝒱` is the image of a compact set under the continuous map (1.34).
> ∎

**Summary — what each criterion removes.**

| # | Name | Source of threshold | Control-plane geometry |
|---|---|---|---|
| S1 | Synchronous roll | Circ.1228 phenomenon; ±10 %, `H_s>2.5 m` ours | up to 2 **parallel strips** ⟂ `ê_wave` |
| S2 | Parametric roll | Circ.1228 phenomenon; ±15 %, `[0.8L,2L]`, `H_s>2 m` ours | strips ⟂ `ê_wave`; **annular sector** (case b) or **full ring** (case c, `GM ∈ (0.46,2.12) m`) |
| S3 | Surf-riding / broaching | Circ.1228 (`Fn>0.3` ≡ circular at `λ=L`); sector ±45° from circular | **annular sector**, 90° wide, outside `V_surf`; inert for `L > 81.6 m` |
| S4 | Slamming | Ochi (1964) model; `P<0.03` NORDFORSK (1987) | **cap on the head-sea side**, widening with speed |
| S5 | Green water | NORDFORSK (1987), `P<0.05` | **double wedge**, speed-independent *under our surrogate* (a modelling artefact) |
| S6 | Lateral acceleration | NORDFORSK (1987), `0.10 g` | S1's strip **widened**, weighted by `\|sin μ_rel\|` |
| S7 | Operator envelope | operator policy; ICORELS (1980) squat; A.893(21)/PIANC UKC | **cell mask** (`H_s`) ∪ **outer-annulus speed cap** (UKC) |

Only S2 case (c) produces a topological hole. Everything else produces sectors, strips and
caps whose union is non-convex but simply connected. **D4** convexifies (`conv 𝒱`), solves,
then projects back and certifies the gap — and Prop 1.11(c) is the case where that projection
has the most to do.

---

## 1.6 Objectives

> **Def 1.9 (Objective vector).** With the CONTRACT ordering (index 1 is always time):
> ```
> J = ( J_T , J_G , J_R , J_C )                                               (1.76)
> J_T = t_arr − t_dep                                    [s]     accumulate +
> J_G = ∫ ṁ(s) ds                                        [kg]    accumulate +
> J_R = ∫ ρ_R(s) ds   or   max_s ρ_R^lvl(s)              [–]     accumulate + or max
> J_C = ∫ ρ_C(s) ds                                      [–]     accumulate +
> ```
> `k` is the number of active objectives; `k = 3` is the default.

### 1.6.1 Fuel and the SFOC bowl

> **Def 1.10 (SFOC).** Specific fuel oil consumption as a function of delivered power, through
> engine load `q = P/P_MCR`:
> ```
> SFOC(P) = s_ref ( 1 + κ ( (q − q_opt)/q_opt )² ) ,  q_opt = 0.75, κ = 0.28   (1.77)
> ```

> **Def 1.11 (Fuel rate).** `ṁ = SFOC(P_D) · P_D`, clamped to zero when `P_D ≤ 0`.

The clamp is one-sided and deliberate: a following wind or sea can make `R_tot < 0` and hence
`P_D < 0`, but **the environment cannot put bunkers back in the tank**. The other end is an
honest omission: at `P_D = 0` this returns zero, whereas a real vessel still burns auxiliary
and boiler fuel — of order 0.02–0.05 kg/s for a Handymax, *an operational figure we have not
measured and which is flagged as an estimate*. That offset is identical on every route of
equal duration and therefore cancels out of every comparison the solver makes; add it at the
reporting boundary if a charterer wants absolute figures.

> **Units warning, and it is large.** The reference vessel's `s_ref = 175×10⁻⁹ kg/(W·s)` is
> commented in the source as "175 g/kWh". It is not: `175 g/kWh = 0.175/3.6×10⁶ =
> 48.61×10⁻⁹ kg/(W·s)`. As written, `s_ref` corresponds to **630 g/kWh**, about **3.6×** a
> modern two-stroke. The field is used as given because it is the vessel record's to define,
> **but every absolute fuel mass in this specification scales with it.** Divide by 3.6 for a
> realistic figure. All *ratios* — the Pareto front's shape, the throttle trade-off, the
> counterexample of Prop 1.14 — are unaffected.

### 1.6.2 Risk and comfort

`ρ_R^lvl(V,θ) := risk_level(V,θ) = max_i sev_i(V,θ)` over enabled criteria, continuous by
Prop 1.12's argument, equal to 1 exactly on the regulatory boundary, and satisfying (1.51).
Values above 1 are ordered and meaningful (2 is dead on resonance in a sea well past the height
gate) but they are **severities, not probabilities**. The additive risk rate is
`ρ_R = ρ_R^lvl/3600`, so the additive objective is measured in **risk-hours**.

`ρ_R^lvl` is continuous everywhere and differentiable except on the measure-zero set where the
arg-max criterion changes. **Any gradient-based polish must treat it as non-smooth there.**

The comfort objective `ρ_C` is a beam-sea proxy, `ρ_C = H_s |sin μ_rel| / (H_s^caution · 3600)`.
The proper object is the MSI/MII of ISO 2631 built from the vertical-acceleration response
spectrum, which the severity computation already forms internally but does not export.
**This is a documented gap, not a model.** Do not report `J_C` as a motion-sickness incidence.

### 1.6.3 Why SFOC load-dependence matters — precisely

The usual claim is that a load-dependent SFOC makes fuel non-monotone in speed. Prop 1.8(c)
shows that is **false** for realistic curvature. Here is what load-dependence actually does,
and it is a stronger reason for carrying fuel as a separate label.

> ### Prop 1.13 (Fuel is not a function of energy)
> With `SFOC` constant, `J_G = s_ref ∫ P_D dt = s_ref · E`, so fuel is a strictly increasing
> function of the accumulated energy `E` and a **single scalar label `E` determines fuel**.
> With `SFOC` load-dependent, no such function exists: there are throttle profiles with equal
> energy and unequal fuel.
>
> *Proof (explicit counterexample).* Over a duration `τ`, compare
> (A) constant `q = 0.75` and (B) `q = 0.5` for `τ/2` then `q = 1.0` for `τ/2`. Both deliver
> mean load 0.75, hence the same energy `0.75 P_MCR τ`. With (1.77), `κ = 0.28`, `q_opt = 0.75`:
> ```
> SFOC(0.75) = s_ref                                → ṁ_A = s_ref (0.75 P_MCR)
> SFOC(0.50) = s_ref(1 + 0.28(1/3)²) = 1.031 11 s_ref
> SFOC(1.00) = s_ref(1 + 0.28(1/3)²) = 1.031 11 s_ref
> J_G^B / J_G^A = [ ½(1.031 11)(0.5) + ½(1.031 11)(1.0) ] / (0.75) = 0.773 33/0.75 = 1.031 1
> ```
> so profile (B) burns **3.11 % more fuel for exactly the same energy**. ∎

That is the operative statement: **the label must carry fuel, not power-time.** A scalarised
"energy" objective is not merely a different weighting, it is a different and wrong quantity.

> ### Prop 1.14 (Fuel is not a function of arrival time)
> There exist two routes with **identical** arrival time and materially different fuel. Hence
> no scalarisation of time determines fuel, and vector-valued labels are necessary.
>
> *Proof (explicit, reference vessel, stationary field).* Route A: 1 000 km through a 4 m head
> sea (`R_AW = 133.78 kN` from (1.20)). Route B: 1 150 km in flat calm. Fix the arrival at
> `144 763 s = 40.212 h`.
>
> *Route A.* Required `V = 10⁶/144 763 = 6.907 8 m/s`. From (1.14) and (1.16),
> `P_D = 21 948.6 V³ + (133 778/0.68) V = 7 233 kW + 1 359 kW = 8 592 kW`, so `q = 0.781 1`.
> From (1.77), `d = 0.041 49`, `SFOC = 175.08×10⁻⁹`, `ṁ = 1.504 4 kg/s`, and
> `J_G^A = 1.504 4 × 144 763 = 217.8 t`.
>
> *Route B.* Required `V = 1.15×10⁶/144 763 = 7.944 0 m/s`. `P_D = 21 948.6 V³ = 11 003 kW`,
> `q = 1.000 3`, `d = 0.333 7`, `SFOC = 180.46×10⁻⁹`, `ṁ = 1.985 7 kg/s`, and
> `J_G^B = 287.4 t`.
>
> Same arrival time; **217.8 t versus 287.4 t, a 32 % difference**. ∎
> *(Both tonnages carry the `s_ref` factor of §1.6.1; divide by 3.6 for realistic absolute
> values — 60.5 t and 79.8 t. The ratio is unaffected.)*

Finally, the question of whether it ever pays to *vary* the throttle at fixed distance and
duration — which matters because D4 convexifies the indicatrix and thereby permits exactly
that kind of chattering.

> ### Prop 1.15 (Steady steaming is optimal iff `κ < 7/18`)
> In calm water with the Admiralty cube law, fuel per unit distance as a function of speed,
> `φ(V) ∝ s² + (κ/q_opt²)( s⁸ − 2q_opt s⁵ + q_opt² s² )` with `s := V/V_pwr(1)`, is **strictly
> convex** on `(0,1]` if and only if
> ```
> κ  <  7/18 = 0.388 9                                                        (1.78)
> ```
> Hence for `κ < 7/18` a constant-speed profile strictly beats any non-constant profile with
> the same distance and duration, by Jensen; for `κ > 7/18` a two-speed profile is cheaper.
>
> *Proof.* With `q = s³` (cube law) and `d = (s³ − q_opt)/q_opt`, fuel per distance is
> `φ ∝ SFOC·P/V ∝ (1 + κd²) s²`, and expanding `d²`:
> `φ ∝ s² + (κ/q_opt²)(s³−q_opt)² s² = s² + (κ/q_opt²)( s⁸ − 2q_opt s⁵ + q_opt² s² )`.
> Differentiate twice:
> ```
> φ'' ∝ 2 + (κ/q_opt²)( 56 s⁶ − 40 q_opt s³ + 2 q_opt² )                      (1.79)
> ```
> Minimise the bracket over `s`: `d/ds = 336 s⁵ − 120 q_opt s² = 0` gives
> `s³ = (120/336) q_opt = (5/14) q_opt`, at which
> `56 s⁶ − 40q_opt s³ + 2q_opt² = q_opt²( 56(5/14)² − 40(5/14) + 2 ) = q_opt²(56·25/196 −
> 100/7 + 2) = q_opt²(50/7 − 100/7 + 14/7) = −(36/7) q_opt²`. Substituting,
> `min φ'' ∝ 2 − (36/7)κ`, which is positive iff `κ < 14/36 = 7/18`. Convexity plus Jensen
> gives the optimality of the constant profile at fixed mean; concavity somewhere gives a
> cheaper two-point mixture. (The stationary point is interior: `s³ = (5/14)(0.75) = 0.2679`,
> `s = 0.644`.) ∎

For the reference `κ = 0.28` the margin is 28 %: **steady steaming is optimal, and the
chattering permitted by D4 costs nothing in fuel** (it costs in the realisability gap of
Thm 2.11 instead). If a vessel record carries `κ ≥ 7/18` — an engine with a very steep
part-load penalty — then the fuel-optimal control genuinely chatters, the dwell constraint
`τ_d` binds on fuel as well as on geometry, and Thm 2.11's gap must be re-derived for the fuel
objective. That is a real behavioural change triggered by a single vessel parameter, and an
implementation should test `κ < 7/18` at vessel load and log the result.

### 1.6.4 Admissible accumulation

`+` and `max` accumulation are both supported (CONTRACT: `J_R` may be either). The label
algebra requires only that the accumulation be monotone and isotone over an ordered semiring;
that is **Prop 5.4** in `05-multiobjective.md`. Bottleneck (`max`) objectives are the ones a
master actually uses — *what is the worst moment of this voyage* — and no weighted sum can
express them. Prior art for multi-objective front propagation is Kumar & Vladimirsky (2010)
(ERRATA E11); the bottleneck accumulation in that setting is the part we have not found
treated.

---

## 1.7 Problem P

> ### Problem P (the routing problem, ground frame)
>
> **Given:** a vessel model (§1.3, §1.5, §1.6); an environment field `sample_env(x,t)` valid on
> `[t₀⁻, t₀⁻ + H_fc]`; a navigable domain `Ω ⊂ S²`; endpoints `x_A, x_B ∈ Ω`; a departure
> window `[t₀⁻, t₀⁺]`; optionally a minimum steering dwell `τ_d`.
>
> **Find:** the Pareto front of
> ```
> minimise   J = ( J_T, J_G, J_R, J_C )     of Def 1.9                        (1.80)
> ```
> over the departure time `t_dep` and the measurable control `s ↦ (q(s), θ(s))`, subject to
> ```
> ẋ(t) = V_pwr(q(t),θ(t); x(t),t) · n(θ(t)) + c(x(t),t)   a.e.  [frame components, Conv. 1.0]
> (q(t), θ(t)) ∈ 𝒜(x(t), t)                               a.e.  [Def 1.8]     (1.81)
> x(t) ∈ Ω                                                for all t
> x(t_dep) = x_A ,   x(t_arr) = x_B ,   t_dep ∈ [t₀⁻, t₀⁺]
> t_arr ≤ t₀⁻ + H_fc                                      [else see below]
> θ piecewise constant with minimum dwell τ_d              [optional; relaxed per D4]
> ```

**Forecast horizon.** Beyond `t₀⁻ + H_fc` the normative convention (ERRATA E5.1) is
**persistence of the final frame**, and the run log must report how many evaluations were
horizon-truncated. A solve in which a material fraction of evaluations are truncated is
reporting a forecast-free extrapolation and must be labelled as such.

**Existence.** Under Prop 1.12, `𝒱(x,t)` is compact; it is **not** convex (§1.5). For a
minimum-time problem with a compact but non-convex velocity set, an optimal *measurable*
control need not exist — minimising sequences chatter between the two sides of a notch. Under
**D4** the solver works with `conv 𝒱(x,t)`, which is compact and convex, and then Filippov's
theorem gives existence of an optimal relaxed control; the relaxed optimum is approached by
ordinary controls that alternate rapidly. **This is why D4 exists** and it is the honest
statement of what it buys: not accuracy, but existence. The price is the realisability gap,
bounded a-priori only locally (ERRATA E6.3) and globally only by the a-posteriori certificate
Cor 4.12.

**Two distinct problems hide in the departure window**, and they have different answers:

```
(P-dur)  minimise  t_arr − t_dep     over t_dep ∈ [t₀⁻,t₀⁺]     "shortest passage"
(P-arr)  minimise  t_arr             over t_dep ∈ [t₀⁻,t₀⁺]     "earliest arrival"
(P-dead) maximise  t_dep  subject to t_arr ≤ T_deadline          "latest safe departure"
                                                                              (1.82)
```

They differ whenever waiting pays: sailing after a front passes shortens the *passage* without
advancing the *arrival*. (P-dur) is the charterer's question, (P-arr) the shipper's, (P-dead)
the port-slot question. All three are stated because implementations routinely solve one and
report it as another.

**Cost of the window under the reduction (§1.8).** In the co-moving frame the field is
stationary, so shifting `t_dep` by `δ` translates *both* the source `y_A = x_A − w t_dep` and
the interception target `x_B − w t_arr` by `−wδ`: the whole configuration slides rigidly
through **one fixed metric field**. Two consequences, both real savings:

- (P-dur) and (P-arr) require `n_dep` stationary sweeps — but they share **one** metric build,
  and the metric build (the support tabulation of D2, `n_θ = 72` evaluations per cell per
  forecast hour) is the expensive part. Only the sweeps repeat.
- (P-dead) requires **one** sweep. The target `y_B = x_B − w T_deadline` is *fixed*, so a
  single **reverse** stationary sweep from `y_B` yields `T_w^rev(y)` for every `y` at once,
  and the answer is `max{ t_dep : T_w^rev(x_A − w t_dep) ≤ T_deadline − t_dep }`, a scalar
  scan over the window on an array already computed.

---

## 1.8 Standing assumptions A1 and A2

From here to the end of the specification, the following two assumptions are **in force**.
They are the hypotheses of **Theorem C.1 (the Co-Moving Reduction)**, `spec/CORE-THEOREM.md`,
which is the defining result of KAIROS. §1.1–§1.7 above do not use them.

### 1.8.1 A1 — frozen advection

> **Assumption A1 (frozen advection).** There is a constant `w ∈ ℝ²` (frame components, m/s)
> such that every **dynamic** environmental field is a rigid translation of a fixed pattern
> over the planning horizon:
> ```
> E(x,t) = E₀(x − w t)        ⟹        𝒱(x,t) = 𝒱₀(x − w t)                  (1.83)
> ```
> where `E = (c_cur, W₁₀, H_s, T_p, μ_w)`.

A1 is the meteorological ancestor of **Taylor's (1938) frozen-field hypothesis** in turbulence,
applied at synoptic scale rather than at eddy scale. Its justification is empirical: over
2–5 days a synoptic low, a tropical cyclone, a swell field or a monsoon surge is, to leading
order, a rigid pattern that translates at 5–8 m/s along a track steady for days. The pattern
deforms and intensifies, but slowly compared to how fast it *moves*.

**What A1 buys:** everything. By Thm C.1(a)(b) the co-moving problem `ẏ ∈ 𝒱_w(y)` with
`𝒱_w(y) = 𝒱₀(y) ⊖ w` is **autonomous**, so `L_t ≡ 0` and the causality condition of ERRATA
(E4.1), `r(x)·L_t ≤ 1`, holds **vacuously** — a single monotone pass is licensed with no
condition to check. Verified: in the pure-translation regime the measured co-moving `L_t` is
`0.0` at max, p99 and median, **to the last bit**.

**What breaks without A1.** Decompose (CORE-THEOREM C.8)

```
E(x,t) = E₀(x − w t) + R(x,t)                                                 (1.84)
```

with `R` the residual — intensification, deformation, a second system moving at a different
velocity. Then the reduction is no longer exact, and it becomes a **preconditioner**: apply it
anyway, and treat `R` with the ground-frame time-dependent machinery, whose causality constant
is now `L_t^R = Lip_t(R)` rather than `L_t`. **Measured** (Test 8.10, 3-day horizon, 10 km
grid, 24 headings, reported as max / p99 / median):

| Regime | frame | max | p99 | median | `r·L_t` at `r = 56 km` |
|---|---|---|---|---|---|
| A: pure translation | ground | 6.33e-07 | 6.33e-07 | 5.64e-07 | 0.035 OK |
| | co-moving | **0.0** | **0.0** | **0.0** | **0.000** |
| B: + intensification 35 %/day | ground | 2.34e-05 | 2.34e-05 | 3.75e-07 | **1.309 VIOLATED** |
| | co-moving | 4.86e-06 | 4.86e-06 | 1.69e-06 | **0.272 OK** |
| C: + second system, different `w` | ground | 2.34e-05 | 2.33e-05 | 3.52e-07 | **1.307 VIOLATED** |
| | co-moving | 5.07e-06 | 4.67e-06 | 1.63e-06 | **0.261 OK** |

So where A1 fails badly the reduction still moves a solve from **unlicensed** (`r·L_t = 1.31`)
to **comfortably licensed** (`0.26`), a 4.6–5.0× improvement at p99. **And it costs something:
the median gets ~4.5× worse** — in the ground frame most cells are far from any system and see
almost no change, whereas in the co-moving frame the sampling point slides through space, so
quiet cells now see the field vary. Because causality is a worst-case condition this is the
right trade, but it *is* a trade, and reporting only the max oversells it.

**Choosing `w`.** Not by image registration. Phase correlation between consecutive forecast
frames was tried first and **failed badly** — against a true dominant `w = (2.0, 0.5)` it
returned `(−0.74, 0.00)`, because it locks onto whichever feature carries the most gradient
energy, which need not be the one governing causality. It is replaced by choosing `w` to
minimise the residual causality constant directly (CORE-THEOREM C.10), by coarse-to-fine
search. **The resulting `w` is not a storm-track estimate and must never be reported as one**:
in regimes B and C the optimised `w` was `(−0.56, −1.38)` against a true `(+2.0, +0.5)`. Once
A1 is violated, minimising the residual causality constant and estimating the meteorological
advection are *different problems*, and the algorithm wants the former.

### 1.8.2 A1 does not apply to the static domain — and the consequence

> **A1 covers the dynamic fields only.** Bathymetry, coastlines and policy exclusions are
> **static in the ground frame**, hence *moving* in the co-moving frame. `Ω` is time-invariant
> in `x`; in `y` it is `Ω_w(t) = Ω ⊖ w t`.

This is not covered by Theorem C.1 as stated, and it is a real gap that an implementer will
hit. Over a 140 h voyage with `|w| = 1.4 m/s` the displacement is ~700 km: a co-moving node `y`
that is water in the co-moving grid may correspond to a ground point `y + w·T_w(y)` that is
land, and vice versa.

**The correct test, and why it is available.** The label-setting sweep finalises nodes in
increasing `T_w`. At the moment node `y` is finalised, its label `T_w(y)` is **final**, so its
ground position `y + w·T_w(y)` is known exactly. The land mask must be evaluated **there**:

```
node y is admissible  ⟺  y + w·T_w(y) ∈ Ω                                     (1.85)
```

at a cost of one coordinate map plus one mask lookup per finalisation, `O(1)`, preserving the
single-pass property. This is the same device as CORE-THEOREM's requirement R2 (select the
goal node by the ground miss, not by the interception root find) applied to the domain
constraint instead of the target.

> **Prop 1.17 (Soundness and incompleteness of the co-moving land test).** With (1.85) in
> force, every route the solver returns satisfies `x(s) ∈ Ω` at every node, so no returned
> route passes through land. However, the test may **reject a node that is reachable**: if the
> earliest co-moving arrival at `y` maps to land but a later arrival maps to water, that later
> arrival is lost.
>
> *Proof.* Soundness: the recovered route is `x(s) = y(s) + w τ(s)` with `τ(s) = T_w(y(s))`
> (Thm C.1(d)), which is exactly the quantity tested in (1.85), so every node of the returned
> route is in `Ω`. Incompleteness: label-setting stores only the minimal `T_w(y)`; the test is
> applied to that value; a distinct, larger arrival time at the same `y` is never materialised
> and therefore never tested. ∎

**Scope of the incompleteness.** For the *time-optimal* problem the algorithm only ever uses
the earliest label at each node, so the lost alternatives are exactly the ones it would not use
anyway — unless the loss disconnects the graph. The exposure is confined to nodes whose ground
position lies within `|w|·t_max` of a coast. **The honest recommendation:** apply the reduction
on the open-ocean interior and run the ground-frame corrector (CORE-THEOREM step 6) inside a
coastal buffer of width `|w|·t_max`. A voyage that is coastal along its whole length is outside
the reduction's comfortable scope; a transoceanic voyage with coastal endpoints is not.

This also interacts with requirement **R1**: the co-moving grid must be dilated by `|w|·t_max`
opposite to `w`, or the target node `y = x_B − w t*` simply is not in the domain. Undersized,
this fails **silently** — measured at a **104.5 km landfall miss that a full-grid scan could
not reduce**, because no node in the domain mapped anywhere near the target; extending the
domain by `|w|·t_max ≈ 500 km` brought the miss to **11.2 km**, under half a grid diagonal.

### 1.8.3 The vessel model is invariant under the shift

> ### Prop 1.16 (Galilean invariance of the vessel model)
> Under the co-moving map `y = x − w t` with constant `w`, the through-water velocity is
> unchanged. Consequently `R_calm`, `R_AW`, `R_AA`, `P_D`, `V_pwr`, all seven severities
> `sev_1 … sev_7`, `ṁ`, `ρ_R`, `ρ_C` and the ban set `𝒜` are **identical** in the two frames.
> The *only* object that transforms is the effective drift, `c ↦ c − w`.
>
> *Proof.* By (1.9), `V n(θ) = ẋ − c`. Differentiating `y = x − wt` with `w` constant gives
> `ẏ = ẋ − w`, so
> ```
> V n(θ) = ẋ − c = (ẏ + w) − c = ẏ − ( c − w )                                (1.86)
> ```
> i.e. the same vector, expressed as the co-moving ground velocity minus the shifted drift.
> Hence `V` and `θ` are frame-invariant. Every function listed depends on the control only
> through `(V, θ)` and on the environment only through fields that A1 leaves pointwise
> unchanged under the map (they are evaluated at the same physical point and time). ∎

**This is why the reduction needs no new physics code.** The implementation wraps the
environment field, subtracts `w` from the current, and lets the existing metric run unchanged
on a field that is now stationary. It is also why the Randers structure survives (CORE-THEOREM
C.6): `𝒱₀(y) = D(c₀(y), V_s)` gives `𝒱_w(y) = D(c₀(y) − w, V_s)` — still a disc, still centred
on a drift vector, so every closed form and every golden vector of handbook G2–G3 carries over
verbatim with `c ← c₀ − w`.

> **Implementation trap (from (1.86), and it costs about 1 % in speed).** `R_AA` in (1.22) is
> computed from the **apparent wind**, `V_rel = W₁₀ − v_g`, where `v_g` is the **true ground
> velocity** `ẋ`. In the co-moving frame the available vector is `ẏ`, and `ẋ = ẏ + w`. An
> implementation that shifts the drift and then computes the apparent wind from
> `V n(θ) + (c − w)` is computing `W₁₀ − ẏ` instead of `W₁₀ − ẋ`, i.e. **an apparent wind
> wrong by exactly `w`**.
>
> Magnitude, for `|w| = 3 m/s` and an apparent wind of 15 m/s: the error in `|V_rel|²` is up to
> `2|V_rel||w| + |w|² = 99` against `225`, i.e. 40 % of the gross aerodynamic term. With
> `R_AA ≈ 65.7 kN` net against `R_calm(V_ref) = 774.2 kN`, that is ~3.4 % of total resistance,
> ~3.4 % in power, and by the cube law ~1.1 % in speed. *(These are derived from the reference
> vessel's numbers; the 15 m/s apparent wind is an assumed operating point, not a measurement.)*
>
> **Rule:** the apparent wind must be formed from `ẏ + w`. The leeway term `κ_L W₁₀` must
> **not** be shifted (§1.2.3). `w` is subtracted from the total effective drift, once, and
> nowhere else.

### 1.8.4 A2 — the outrun condition

> **Assumption A2 (outrun condition).** `|w| < σ_min^w`, where
> ```
> σ_min^w := inf_{y ∈ Ω, |u| = 1} σ_w(y, u)                                   (1.87)
> ```
> is the worst-direction speed made good in the co-moving frame. Physically: **the ship can
> make ground faster than the weather system translates.**

**What A2 buys.** It is exactly what makes the interception (Thm C.1(c)) well posed. With
`g(t) := T_w(x_B − wt) − t` and `F_max^w = 1/σ_min^w`,

```
T_w(x_B − wt) ≤ F_max^w |x_B − wt − x_A| ≤ F_max^w ( |x_B − x_A| + |w| t )
⟹  g(t) ≤ F_max^w |x_B − x_A| + ( F_max^w |w| − 1 ) t                         (1.88)
```

and A2 makes the bracket negative, so `g → −∞` and a zero exists. Without it, `g` may stay
positive forever: no interception, and the honest output is **"this system cannot be
outrun"** — not an error, and not a fallback to a longer horizon.

**A checkable cellwise form.** A2 as written is an infimum over the whole domain and every
direction. In the classical Randers case (throttle-max, no active bans, isotropic `V_max`) it
collapses to a two-line test:

> **Prop 1.18 (Cellwise outrun test).** If `𝒱_w(y) = D(c₀(y) − w, V_max(y))` then
> `σ_w(y,u) = sqrt(V_max² − c_⊥²) + c_∥` with `c := c₀(y) − w`, whose minimum over `u` is
> attained at `u = −c/|c|` and equals `V_max(y) − |c₀(y) − w|`. Hence
> ```
> A2  ⟺  sup_{y ∈ Ω} [ |c₀(y) − w| + |w| − V_max(y) ] < 0                     (1.89)
> ```
> an `O(N)` scan with two vector norms per cell.
>
> *Proof.* Write `c = c₀ − w`, decompose relative to `u` as in (1.36). Then
> `σ_w(u) = sqrt(V_max² − c_⊥²) + c_∥` by (1.38) at `V = V_max`. Parameterise
> `c_∥ = |c|cos α`, `c_⊥ = |c| sin α`; then
> `σ_w = sqrt(V_max² − |c|²sin²α) + |c| cos α`, whose derivative in `α` is
> `−|c|² sin α cos α / sqrt(V_max² − |c|² sin²α) − |c| sin α`, vanishing at `sin α = 0`. At
> `α = π` (i.e. `u` anti-parallel to `c`) the value is `V_max − |c|`, at `α = 0` it is
> `V_max + |c|`; the former is the minimum. ∎

Note the relation to Prop 1.10: `σ_min^w > 0` is exactly `|c₀ − w| < V_max`, which is
CORE-THEOREM's condition (C.7), *"the ship can work against this system."* **A2 is strictly
stronger**: it demands `σ_min^w > |w|`, i.e. a margin equal to the system's own translation
speed. So:

```
(C.7)  |c₀(y) − w| < V_max(y)                    necessary for A2, not sufficient
(A2)   |c₀(y) − w| + |w| < V_max(y)              the operative test              (1.90)
```

Where (C.7) fails, ERRATA E1 applies and Prop 1.10 gives the answer: the reachable directions
form a cone of half-angle `arcsin(V_max/|c₀−w|)`, and the correct output really is *you cannot
escape this storm*. Where (C.7) holds but A2 fails, the metric is fine and the *interception*
is not: the ship can work against the field locally but cannot catch the destination, which is
receding at `|w|`. Those are different failures with different operator messages and an
implementation should distinguish them.

With bans active, `𝒱_w` is not a disc and (1.89) must be replaced by an evaluation of the gauge
over the direction set, i.e. `σ_min^w = min_j σ_w(y, u_j)` over the `n_θ` tabulated directions,
which is exactly the support-function tabulation of D2 and costs nothing extra. Report
`min_y σ_min^w(y) − |w|` as a run diagnostic; a negative value is a hard refusal, a small
positive value is a warning that the interception root is ill-conditioned.

### 1.8.5 Summary: what each assumption buys, what breaks without it

| Assumption | Buys | Breaks without it |
|---|---|---|
| **A1** frozen advection | `L_t ≡ 0` co-moving; single pass licensed with no causality check; **zero temporal discretisation error** (measured `2.8e-14` vs `6.7e-3` m/s) | Reduction becomes a preconditioner via (1.84): `r·L_t` 1.31 → 0.26 measured, still licensed; median degrades 4.5×; residual corrector (step 6) required |
| **A1 restricted to dynamic fields** (§1.8.2) | Coastlines stay ground-fixed and must be tested at `y + w·T_w(y)` | Land mask misplaced by up to `\|w\|·t_max` (~500–700 km); routes through land, or spurious blockage |
| **A2** outrun | Interception (C.4) has a root, active at `t*`, so the optimum never loiters and no wait relaxation is needed | `g(t)` may never reach 0: no interception. Correct output is refusal, not a longer horizon |
| **Lemma 1.4** monotone power | `V_pwr` single-valued and continuous; `𝒜` compact; maxima attained | Smallest-root rule (Prop 1.5) still correct; `V_pwr` usc with jumps; finite throttle sample restores attainment; reported fuel becomes a conservative upper bound |
| **(1.40)** crab contraction | Fixed point unique, 2–3 iterations | Coincides with `\|c_⊥\| → V`: direction infeasible, `σ = 0`, `F = +∞`, excluded (golden vector T8) |
| **D4** convexify | Existence of an optimal relaxed control (Filippov) | Minimising sequences chatter; no optimal measurable control for a non-convex `𝒱` |
| **`κ < 7/18`** (Prop 1.15) | Steady steaming optimal; D4's chattering costs no fuel | Fuel-optimal control genuinely chatters; `τ_d` binds on fuel; Thm 2.11 must be re-derived for `J_G` |
| **Domain cap `\|ϕ\| ≤ 80°`** | Planar-cell treatment good to `< 1 %` | `cos ϕ` singularity in (1.4); frame rotation (1.7) dominates the error budget |
| deterministic forecast | Everything above | No probabilistic guarantee. Ensemble/uncertainty handling is **out of scope** and is not approximated anywhere |

---

## 1.9 Interface obligations of §1 (language-agnostic)

Everything above must be reachable through the five primitives of CONTRACT §4 and nothing
else. Restated as abstract types with the operations and complexities §1 requires:

| Primitive | §1 obligation | Complexity | Notes |
|---|---|---|---|
| `sample_env(x,t) → Env` | trilinear in `(λ,ϕ,t)`; **deterministic and side-effect free** | `O(1)`, 8 loads | Determinism is a hypothesis, not a style rule: the sweep evaluates the same `(x,t)` from several front edges and the correctness argument assumes the same answer each time. Hidden state breaks the algorithm silently. |
| `attainable(vessel, env, θ, q) → V or NONE` | Def 1.3 + Def 1.8: the smallest root of `P_D − qP_MCR` (Prop 1.5), or NONE if any enabled `sev_i > 1` | `N_scan + N_root ≈ 44` power evaluations | Never raises, never returns NaN. Degenerate returns of 0: `q ≤ 0`, `P_MCR ≤ 0`, `V_hull ≤ 0`, root below the steerage-way floor. |
| `rates(vessel, env, θ, q) → (ṁ, ρ_R, ρ_C)` | Def 1.11, §1.6.2 | `O(1)` after `attainable` | `ρ_R` must be **continuous** in `(V,θ)` (playbook S6) and satisfy (1.51). |
| `sigma(x,t,u,q) → f64` | (1.38) after the fixed point (1.39); `0` if infeasible | `N_fp ≈ 2–3` × `attainable` | **The only function the solver calls.** Everything above is behind it. |
| `support(x,t,p) → f64` | `𝔥(x,t,p) = max_{v ∈ conv 𝒱} ⟨v,p⟩`, tabulated on `n_θ = 72` directions per cell per forecast hour (D2) | build `n_θ · C_σ`; query `O(log n_θ)` | For convex `𝒱` the gauge is recovered exactly from `𝔥` by duality (Prop 2.7), turning the inner minimisation into a binary search. |

**Measured cost** (reference implementation, 1 200 `sigma_max` calls over 25 positions × 2
forecast times × 24 directions, `n_θ = 24`, `n_q = 5`): **524.5 µs per `sigma_max`** with the
full §1.3/§1.5 physics; **541.2 µs** with a reduced four-criterion model; 24/1 200 directions
infeasible under both. The full model is marginally *cheaper*, because both are dominated by
the ~50 power evaluations of the attainable-speed root find multiplied by the crab-angle
iterations, and the three extra criteria are noise beside it. There is therefore **no
wall-clock argument for the reduced model**, and one substantive argument against it: with the
reduced model `risk_level` is constant across the throttle family (measured: `0.266` at all
five throttles), so the risk axis of the Pareto front collapses and D1 becomes vacuous. With
the full model the same point gives `0.618, 0.571, 0.514, 0.441, 0.650` — non-monotone in `q`,
as §1.4.6 describes.

**Instrumentation §1 must expose** (playbook, "from day one"): metric evaluations and cache hit
rate; count of directions returning `F = +∞` (Prop 1.10 cone); count of throttles rejected by
each of S1–S7 separately; distribution of `𝒬_adm` cardinality; number of crab-angle iterations;
`min_y σ_min^w(y) − |w|` (the A2 margin, §1.8.4); number of non-monotone intervals detected in
`P_calm` (§1.3.6); number of horizon-truncated evaluations (§1.7); and `κ` against `7/18`
(Prop 1.15). These cost nothing and they are the difference between "it works" and "we know it
works".

---

## References cited in §1

- **Zermelo, E.** (1931). *Über das Navigationsproblem bei ruhender oder veränderlicher
  Windverteilung.* ZAMM 11, 114–124. — The kinematics (1.9) and the navigation formula.
- **Taylor, G. I.** (1938). *The spectrum of turbulence.* Proc. R. Soc. A 164, 476–490. — The
  frozen-field hypothesis, meteorological ancestor of A1.
- **Ochi, M. K.** (1964). *Prediction of the occurrence and severity of ship slamming at sea.*
  5th Symposium on Naval Hydrodynamics. — The two-condition slamming model (1.67).
- **ICORELS** (1980). International Commission for the Reception of Large Ships, squat
  formulation. — (1.73).
- **NORDFORSK** (1987). *Assessment of Ship Performance in a Seaway.* — Slamming and green-water
  probability thresholds, lateral-acceleration habitability limits.
- **Bao, D., Robles, C., Shen, Z.** (2004). *Zermelo navigation on Riemannian manifolds.*
  J. Differential Geom. 66, 377–435. — The Zermelo ↔ Randers correspondence used in §1.4.2 and
  §1.8.3.
- **Fujiwara, T., Ueno, M., Ikeda, Y.** (2006). *Cruising performance of a large passenger ship
  in heavy sea.* — Wind-force regression underlying (1.22)–(1.23).
- **IMO MSC.1/Circ.1228** (2007). *Revised guidance to the master for avoiding dangerous
  situations in adverse weather and sea conditions.* — S1, S2, S3.
- **IMO Res. A.893(21)** (1999). *Guidelines for voyage planning.* — S7 under-keel practice.
- **ISO 15016:2015**, Annex; **ITTC 7.5-04-01-01.2**. — STAwave-1 (1.18) and its validity
  envelope; the still-air wind correction in (1.22).
- **Filippov, A. F.** (1962). *On certain questions in the theory of optimal control.* SIAM J.
  Control 1, 76–84. — Existence under D4 (§1.7).
- **Kumar, A., Vladimirsky, A.** (2010). *An efficient method for multiobjective optimal
  control and optimal exit-time problems.* J. Sci. Comput. 43, 274–298. — Prior art for
  vector-valued front propagation (ERRATA E11); §1.4, §1.6.4.
- **Tsaggouris, G., Zaroliagis, C.** (2009). *Multiobjective optimization: improved FPTAS for
  shortest paths and non-linear objectives with applications.* Theory Comput. Syst. 45,
  162–186. — Value-bucketing (ERRATA E7); referenced from §1.6.4.
- **Vladimirsky, A.** (2006). *Static PDEs for time-dependent control problems.* Interfaces and
  Free Boundaries 8, 281–300. — The causality condition the reduction removes the need for
  (ERRATA E10); referenced from §1.8.1.
- **Sethian, J. A., Vladimirsky, A.** (2003). *Ordered upwind methods for static
  Hamilton–Jacobi equations.* SIAM J. Numer. Anal. 41, 325–363. — The supporting solver.
- **Lolla, T., Lermusiaux, P. F. J.** (2014). Level-set ship routing. — Adjacent approach.
- **Markvorsen, S.** (2025). *Time-dependent Zermelo navigation with tacking.* arXiv:2508.07274.
  — Time-dependent-only indicatrix fields; complementary special case to A1.
- **Barles, G., Souganidis, P. E.** (1991). *Convergence of approximation schemes for fully
  nonlinear second order equations.* Asymptotic Analysis 4, 271–283. — Referenced forward from
  §1.7 to Thm 7.1.
- **Dial, R. B.** (1969); **Martins, E. Q. V.** (1984). — Bucket queue and multi-objective
  labelling, referenced forward to §4 and §5.
