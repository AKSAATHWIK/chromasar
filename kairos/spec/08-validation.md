# §8 — Validation

**Block owner:** this file owns §8, `Test 8.x`, `Eq (8.x)`, `Lemma 8.x`, `Conj 8.x`.
Normative parents: `CORE-THEOREM.md` (the algorithm's defining result), `ERRATA.md`
(corrected statements E1–E11), `CONTRACT.md` (symbols, numbering, D1–D7). Where this file
states a number it is either (i) an exact analytic reference value, (ii) derived in-place with
the arithmetic shown, (iii) a **measured** result quoted from `CORE-THEOREM.md`, or
(iv) explicitly flagged as an **unverified estimate**. Nothing else.

---

## 8.0 What this file is for, and what each test can and cannot decide

KAIROS is defined by **Theorem C.1, the Co-Moving Reduction**: in the frame `y = x − w t`
that translates with the weather, the routing problem is *exactly stationary*, so the
causality/FIFO obstruction of the ground frame does not arise, and the solve is one monotone
pass plus a scalar interception. Everything else in the specification — ordered upwind
(Sethian & Vladimirsky 2003), ε-Pareto labels (Tsaggouris & Zaroliagis 2009; Kumar &
Vladimirsky 2010), the causality condition (Vladimirsky 2006), the bucket queue (Dial 1969;
Martins 1984), the a posteriori certificate — is **supporting apparatus** whose prior art is
credited in ERRATA §E10–E11. The validation suite is arranged to match that hierarchy.

**Test tiers.** A third party reproducing KAIROS should run them in this order, because each
tier presupposes the ones above it.

| Tier | Tests | What it decides | Needs a reference solution? |
|---|---|---|---|
| **0 — pointwise metric** | 8.1 | The Randers closed form and its two failure branches | No — exact closed form |
| **1 — analytic geodesics** | 8.2, 8.3, 8.4 | The sweep, the inner minimisation, the frame conventions | No — closed-form geodesic or exact invariant |
| **2 — the theorem** | **8.5** | **Theorem C.1 itself.** The decisive test | **No** — an identity, not a comparison |
| **3 — approximation quality** | 8.6, 8.7 | ε-front quality; discretisation floor | Self-referential (refinement) |
| **4 — invariants** | 8.8, 8.9 | Certificate soundness; solver invariants | No |
| **5 — the reduction as preconditioner** | 8.10 | Contribution 3: `r·L_t` licensed vs unlicensed | No |
| **6 — end to end** | 8.11 | Whole-pipeline agreement; the two silent failures R1, R2 | Cross-frame |
| **7 — reality** | 8.12 | Whether any of this helps a real ship | Yes — AIS. **Not yet run** |

**Run status, stated once and honestly.**

| Test | Status |
|---|---|
| 8.1 | Reference values exact (handbook G2/G3). Suite must reach T7 and T8. |
| 8.2 | Reference values exact (handbook G4). |
| 8.3 | Analytic solution **derived in this file**; expected points computed here. Not yet run against the implementation. |
| 8.4 | Invariant **derived in this file**; bounds computed here. Not yet run. |
| 8.5 | **RUN. Measured**, `CORE-THEOREM.md` §4. |
| 8.6 | Protocol only. **Not yet run.** |
| 8.7 | **RUN. Measured**, `CORE-THEOREM.md` §4. Explanatory constant derived here. |
| 8.8, 8.9 | Protocol only. **Not yet run** as a formal suite. |
| 8.10 | **RUN. Measured**, `CORE-THEOREM.md` §7. Two caveats carried forward. |
| 8.11 | **RUN. Measured**, `CORE-THEOREM.md` §8.1–8.2. |
| 8.12 | **NOT RUN.** Protocol and failure modes only. |

### 8.0.1 Tolerance policy (normative)

Three distinct tolerance classes; conflating them is how validation suites become
decorative.

```
CLASS E (exact)        closed-form reference values.       tol = 1e-12 relative        (8.1)
CLASS I (identity)     quantities an exact theorem forces
                       to zero; residual is pure round-off. tol = 1e-11 absolute, SI   (8.2)
CLASS D (discretised)  quantities carrying stencil error.   tol = the MEASURED floor,
                       which for a 16-neighbour stencil is ~1.4 % and does NOT
                       shrink under refinement (§8.7).                                 (8.3)
```

Class E at `1e-12` follows handbook G2: 12 significant figures in IEEE double, loose enough
to survive last-bit `sqrt` behaviour and tight enough that no real bug hides under it.
Class I at `1e-11` is 100× the measured `9.77e-14` floor of §8.5, which leaves headroom for a
port using a different geodesy library without leaving room for a genuine violation.
Class D is **not a tolerance you choose**; it is a number you measure and publish (§8.7).

> **The single most common validation failure in this field** is applying a Class D tolerance
> to a Class I quantity — "agreement to 1 %" on a test whose exact answer is zero. A 1 %
> agreement on §8.5 would be a *catastrophic failure* of Theorem C.1 disguised as a pass.

### 8.0.2 Conventions that must be fixed before any test runs

1. **Frame.** Per ERRATA E8, `ẋ` denotes ground-velocity components in the local orthonormal
   frame `(𝐞_E, 𝐞_N)`, in m/s. Chart conversion (E8.1) happens at the chart boundary only.
   Every velocity, drift and advection `w` in this file is in that frame.
2. **Heading.** CONTRACT §1 fixes `n(θ) = (sin θ, cos θ)`: `θ` is **true heading, from north,
   clockwise**. Zermelo's navigation formula as printed in handbook G4 is stated in the
   *mathematical* convention (angle from east, counter-clockwise). The two are related by
   ```
   θ_math = π/2 − θ_compass                                                (8.4)
   ```
   and (8.4) must be applied before using the G4 formula or the §8.3 derivation below.
   **This is the one inconsistency between CONTRACT §1 and handbook G4**; it is a convention
   mismatch, not a numerical error, and it is resolved here by (8.4).
   *What breaks without it:* the shear test §8.3 returns a route mirrored about the
   north–east diagonal — a plausible-looking curve that is wrong.
3. **Wave direction.** `μ_w` is the direction waves travel **towards** (`types.Env`).
   Meteorological "from" is converted at the data boundary and never again. A leaked "from"
   convention is a 180° error that produces a plausible map (playbook S2).
4. **Departure-time sampling.** The ground-frame update evaluates `F` at the **departure**
   time of the leg, never the arrival time (playbook S4). In the co-moving frame this
   distinction is void — there is no time argument at all — which is itself part of what
   §8.5 measures.

---

## Test 8.1 — The Randers closed form, and its two silent failures

**What it decides.** Whether the pointwise metric is right, including the two branches that
return plausible garbage instead of raising. Nothing downstream can be trusted until this
passes. Class E, tolerance `1e-12` relative.

**Prior art.** The Zermelo ↔ Randers correspondence is Zermelo (1931) as made precise by
Bao, Robles & Shen (2004). Nothing in this test is claimed as new; it is the base case that
Theorem C.1 preserves under the shift (C.6).

### 8.1.1 Setup

Through-water speed `V_s = 7.2 m/s` (13.9973 kt), no waves, no seakeeping bans, uniform
drift `c`. For a requested unit ground direction `u`, decompose

```
c_∥ := ⟨c, u⟩ ,        c_⊥ := c − c_∥ u ,        |c_⊥| = |c − ⟨c,u⟩u|      (8.5)
σ(u) = sqrt( V_s² − |c_⊥|² ) + c_∥              [speed made good, m/s]     (8.6)
F(u) = 1 / σ(u)                                  [metric, s/m]             (8.7)
```

Equation (8.6) is the crab-angle solution: the cross-track component of the through-water
velocity must exactly cancel `c_⊥`, leaving `sqrt(V_s² − |c_⊥|²)` along track, to which the
along-track drift adds. It is defined only when `|c_⊥| ≤ V_s` and positive only when in
addition `c_∥ > −sqrt(V_s² − |c_⊥|²)`.

### 8.1.2 The golden vectors T1–T8 (handbook G2, verbatim)

These are **exact reference values computed at 50-digit precision from the closed forms and
cross-checked against independent brute-force evaluation** — they are not recorded outputs of
any implementation, so they validate *any* implementation, including the reference one.

| # | Case | `c_∥` | `\|c_⊥\|` | `σ` [m/s] | `F` [s/m] |
|---|---|---|---|---|---|
| T1 | no current | 0 | 0 | **7.2** (exact) | **0.138 888 888 888 889** |
| T2 | pure following | +1.5 | 0 | **8.7** (exact) | **0.114 942 528 735 632** |
| T3 | pure head | −1.5 | 0 | **5.7** (exact) | **0.175 438 596 491 228** |
| T4 | pure cross | 0 | 1.5 | **7.042 016 756 583 30** | **0.142 004 774 280 768** |
| T5 | 30° off a 1.5 m/s current | +1.299 038 105 676 66 | 0.75 | **8.459 869 063 044 66** | **0.118 205 139 175 062** |
| T6 | near-degenerate, `\|c\|/V_s = 0.95` | −6.84 | 0 | **0.36** (exact) | **2.777 777 777 777 78** |
| T7 | Kropina, `\|c\| > V_s`, head-on | −8.0 | 0 | **blocked** (σ ≤ 0) | **+∞** |
| T8 | cross-dominated | 0 | 7.5 | **infeasible** (√ of negative) | **+∞** |

**The arithmetic, so a reader can check every row by hand.**

- **T1.** `sqrt(51.84 − 0) + 0 = 7.2`. `F = 1/7.2 = 0.1388̄`, i.e. `0.138 888 888 888 889`.
- **T2.** `7.2 + 1.5 = 8.7`; `F = 1/8.7 = 0.114 942 528 735 632…` (`= 10/87`).
- **T3.** `7.2 − 1.5 = 5.7`; `F = 1/5.7 = 0.175 438 596 491 228…` (`= 10/57`).
- **T4.** `sqrt(7.2² − 1.5²) = sqrt(51.84 − 2.25) = sqrt(49.59)
  = 7.042 016 756 583 301 399 891…`; `F = 1/σ = 0.142 004 774 280 768…`.
- **T5.** `c_∥ = 1.5·cos 30° = 1.299 038 105 676 658…`, `|c_⊥| = 1.5·sin 30° = 0.75`;
  `σ = sqrt(51.84 − 0.5625) + 1.299 038… = sqrt(51.2775) + 1.299 038…
  = 7.160 830 957 368 00 + 1.299 038 105 676 66 = 8.459 869 063 044 66`.
- **T6.** `7.2 − 6.84 = 0.36`, so `F = 1/0.36 = 2.7̄ = 2.777 777 777 777 78`. Note
  `|c|/V_s = 6.84/7.2 = 0.95` exactly, and `Υ_loc = (7.2+6.84)/(7.2−6.84) = 14.04/0.36 = 39`
  — above the normative `Υ_heap = 12` of ERRATA E2, so this row must also trigger the heap
  fallback (§8.9).
- **T7, T8.** Below.

### 8.1.3 T7 — the negative-cost branch (blocking; ERRATA E1)

T7 is in the table because it does not raise, does not return NaN, and does not look wrong.
Write the closed form in its algebraic (non-decomposed) shape, with `λ := V_s² − |c|²`:

```
F(v) = [ sqrt( ⟨v,c⟩² + λ|v|² ) − ⟨v,c⟩ ] / λ                              (8.8)
```

Evaluate at `V_s = 7.2`, `c = (−8.0, 0)` (an 8 m/s set opposing travel), `v = (1, 0)`:

```
λ      = 51.84 − 64.00 = −12.16                       ← NEGATIVE
⟨v,c⟩  = −8.0
√term  = sqrt( 64.00 + (−12.16)(1) ) = sqrt(51.84) = 7.2
F      = ( 7.2 − (−8.0) ) / (−12.16) = 15.2 / (−12.16) = −1.25             (8.9)
```

**`F = −1.25 s/m`, a finite, plausible, negative cost.** Dropped into any label-setting or
label-correcting sweep this creates negative cycles: the sweep either fails to terminate or
terminates with an arrival time in the past (playbook S1).

> **Normative:** guard `λ > 0` before dividing, on every evaluation, with no exceptions. When
> `λ ≤ 0`, ERRATA E1 governs: the reachable directions form a cone about `c` of half-angle
> `α_reach = arcsin(V_max/|c|)` (E1.1) and `F = +∞` outside it. `|c| = V_max` exactly is
> treated as excluded, for strict safety.

*Worked E1.1 for this row:* `α_reach = arcsin(7.2/8.0) = arcsin(0.9) = 1.119 769 514 998 9 rad
= 64.158 067 2°`. So even in the strong-drift cell the ship is not immobile — it can make
ground in any direction within 64.158 067° of the set. The **correct** answer for T7's
direction (180° from the set) is `+∞`, because 180° > 64.158°.

*What breaks without the guard:* everything, silently. This is failure mode S1 cause 1.

### 8.1.4 T8 — the infeasible cross-drift branch (blocking)

`|c_⊥| = 7.5 > V_s = 7.2`: the ship is set sideways faster than it can crab back, so **no
heading holds the requested track**.

```
V_s² − |c_⊥|² = 51.84 − 56.25 = −4.41                  ← NEGATIVE RADICAND
sqrt(−4.41) → NaN                                                          (8.10)
```

Correct behaviour: `σ = 0`, `F = +∞`, the direction is **excluded from the update**.
Not an exception, not an abort. This is a routine, physically real condition in the Agulhas
retroflection and the summer Somali Current, and a solver that throws here cannot plan a
voyage that merely passes near one.

*Distinction from T7, which implementations conflate:* T7 is `|c| > V_s` with the drift
**opposing** — a whole cone of directions survives. T8 is `|c_⊥| > V_s` for **this** `u`,
which can happen even when `|c| < V_s` is false only marginally; the two guards are
different and both are required. A single `if (norm_c >= V_s)` catches T7 and misses T8's
per-direction case; a single radicand guard catches T8 and lets T7 through with the wrong
sign (because (8.8) has no radicand problem — its radicand is `51.84`, positive).

**Both T7 and T8 must be *reached* by the test suite, not merely defended against in code.**
Assert on branch coverage, not on the absence of a crash.

### 8.1.5 G3 — the conjugate branch (numerical stability)

At `⟨v,c⟩ > 0` the numerator of (8.8) subtracts two nearly equal numbers. Test at
`|c|/V_s = 0.9`, `V_s = 7.2`, `c = (6.48, 0)` following, `v = (1,0)`:

```
λ     = 51.84 − 41.9904 = 9.8496
⟨v,c⟩ = 6.48
naive:      F = ( sqrt(41.9904 + 9.8496) − 6.48 ) / 9.8496
              = ( sqrt(51.84) − 6.48 ) / 9.8496
              = ( 7.2 − 6.48 ) / 9.8496            ← catastrophic cancellation
conjugate:  F = 1 / ( sqrt(⟨v,c⟩² + λ|v|²) + ⟨v,c⟩ ) = 1/(7.2 + 6.48) = 1/13.68   (8.11)
```

Exact: `F = 1/13.68 = 0.073 099 415 204 678 362…`, i.e. `σ = 13.68 = 7.2 + 6.48` ✓.
The conjugate form (8.11) is exact to the last bit; the naive form loses digits in proportion
to `⟨v,c⟩/λ`, which diverges precisely as `|c| → V_s` — i.e. in exactly the cells where the
routing decision matters. **Branch on `sign⟨v,c⟩`.**

*What breaks without it:* nothing visible on a weak field, and 3–4 significant figures lost in
strong-current cells, which then propagates into the ε-dominance comparisons of §5 and makes
the Pareto front unstable (playbook S6 look-alike with a different cause).

### 8.1.6 The co-moving variant (Theorem C.1 §6, Eq C.6)

Under the reduction `𝒱_w(y) = D(c₀(y) − w, V_s)` (C.6): still a disc, still centred on a
drift vector, so **the co-moving metric is still Randers with `c_eff := c₀ − w`** and T1–T8
carry over verbatim under `c ← c₀ − w`. This is not a claim requiring new code — it is the
observation that the reduction is implemented by subtracting `w` from the drift and letting
the existing metric run unchanged.

**Required co-moving golden vectors** (derived here by substitution; each reduces to a row
above, so each is exact):

| # | `c₀` [m/s] | `w` [m/s] | `c_eff = c₀ − w` | direction | reduces to | `σ` [m/s] |
|---|---|---|---|---|---|---|
| T2w | `(3.0, 0)` | `(1.5, 0)` | `(1.5, 0)` | east | **T2** | **8.7** |
| T3w | `(3.0, 0)` | `(1.5, 0)` | `(1.5, 0)` | west | **T3** | **5.7** |
| T4w | `(1.5, 1.5)` | `(1.5, 0)` | `(0, 1.5)` | east | **T4** | **7.042 016 756 583 30** |
| T6w | `(0, 0)` | `(6.84, 0)` | `(−6.84, 0)` | west | **T6** | **0.36** |
| T7w | `(0, 0)` | `(8.0, 0)` | `(−8.0, 0)` | east | **T7** | **blocked**, `F = +∞` |

T7w is the one worth dwelling on: `c₀ = 0` — *no current at all* — yet the co-moving problem
is infeasible eastward, because the ship is being asked to outrun a system translating at
8 m/s with only 7.2 m/s of through-water speed. This is **assumption A2 failing**, and (C.7)
`|c₀(y) − w| < V_max(y)` is its checkable form. The correct output is not a route; it is
*you cannot escape this storm*, together with the reachable cone `arcsin(7.2/8.0) = 64.158 067°`
about west.

> **Normative:** (C.7) is checked **cell by cell before the sweep**, and failures are counted
> and reported. A run in which (C.7) fails anywhere on the eventual route is not a valid
> KAIROS solve, whatever number it returns.

*What breaks without A2:* Theorem C.1(c) loses its `g(t) → −∞` argument (`F_max^w|w| ≥ 1`
makes the bracket in the CORE-THEOREM §3 proof non-negative), the interception root need not
exist, and the honest return value is `None` — which `interception_time` does return.

### 8.1.7 Pass criteria for Test 8.1

```
P1  every row T1..T6, T2w..T6w:  |σ_impl − σ_ref| / σ_ref  ≤ 1e-12
P2  T7  : F_impl is +∞ (or the direction is reported excluded). It is a HARD FAIL
          if any finite value is returned, and a CATASTROPHIC FAIL if it is negative.
P3  T7  : the reported reachable cone half-angle matches arcsin(V_max/|c|) to 1e-12
P4  T8  : σ_impl == 0 exactly and F_impl == +∞; no exception propagates to the caller
P5  G3  : |F_impl − 1/13.68| ≤ 1e-15 absolute (the conjugate branch is exact; a naive
          branch typically lands near 1e-11 here, which is the discriminator)
P6  coverage: the T7 and T8 code paths are executed, asserted by instrumentation
```

---

## Test 8.2 — Uniform-flow Zermelo: the zero-intermediate-waypoint test

**What it decides.** Whether the *solver* — not the metric — is right. It is the sharpest
single test in the project because it requires no reference solution, is insensitive to grid
resolution, and fails loudly for five distinct bugs at once. Class E on the arrival times,
Class I on the turn rate.

**Prior art.** Zermelo (1931). The test itself is a degenerate case of his navigation
formula, not a contribution.

### 8.2.1 The structural claim

Zermelo's navigation formula, in the mathematical heading convention (apply (8.4) first),
with drift `c = (u_c, v_c)`:

```
dθ/dt = ∂v_c/∂x · sin²θ + (∂u_c/∂x − ∂v_c/∂y)·sin θ cos θ − ∂u_c/∂y · cos²θ   (8.12)
```

In a **uniform** field every partial derivative vanishes identically, so

```
dθ/dt ≡ 0    for every heading, every position, every drift magnitude.      (8.13)
```

**Therefore the time-optimal route is a single constant-heading leg with *zero* intermediate
turns.** This is a theorem about the continuum problem, so any waypoint a router emits in a
uniform field is a numerical artefact, and every quantity computed downstream of it is
suspect.

**Proof of (8.13).** (8.12) is the Euler–Lagrange equation of the Zermelo problem written in
the heading variable; its right-hand side is a homogeneous linear form in the four first
partials of `c`. A uniform field has all four equal to zero, hence `dθ/dt = 0` pointwise
along any extremal, hence `θ` is constant on every extremal. Since the drift is constant, the
ground velocity `v = V_s n(θ) + c` is then also constant, so the extremal is a straight line
traversed at constant speed. There is exactly one straight line joining `x_A` to `x_B`, and
the constant heading realising it is the unique solution of the crab-angle equation; hence the
extremal is unique and, being the unique extremal of a problem whose minimum exists (the
metric is Randers with `|c| < V_s`, hence a positive-definite Finsler metric with a compact
indicatrix, so minimisers exist and satisfy the Euler–Lagrange equation), it is the
minimiser. ∎

### 8.2.2 The qualitative assertion

```
Q1   max over the whole route of |dθ/dt|  <  1e-14 rad/s     (floating-point zero)
Q2   number of intermediate waypoints with a heading change > 1e-9 rad  ==  0
```

Q1/Q2 fail loudly and *distinguishably* for:

| Bug | Signature in this test |
|---|---|
| east/north transposed | heading off by exactly `90° − 2·(bearing)`; σ takes T4's value where T2's is expected |
| finite differences in degrees not metres | `dθ/dt` inflated by `(π/180 · R_E)` ≈ `1.1e5`; Q1 fails by ~5 decades |
| the `ζ` inner minimisation is skipped or pinned at an endpoint | waypoints appear at every stencil step; Q2 fails with a count ≈ path length / h |
| any stencil that quantises heading with no continuum update | waypoints appear on the two lattice directions bracketing the true heading, alternating — a zig-zag, and its period is the giveaway |
| the metric evaluated at arrival rather than departure time | Q1/Q2 **pass** (the field is time-independent). This test cannot see S4 cause 1; §8.5 and §8.10 can |

The last row is why this test is necessary and not sufficient.

### 8.2.3 The quantitative version (handbook G4, exact)

`V_s = 7.2 m/s`, uniform current `c = (1.5, 0) m/s` (due east). Voyage `(0°N, 0°E) → (0°N, 5°E)`,
due east along the equator. The exact great-circle distance is

```
S = 5° · (π/180) · R_E = 0.087 266 462 599 716 48 × 6 371 000 = 555 974.633 222 8 m   (8.14)
```

(Arithmetic: `0.087 266 462 599 716 48 × 6 000 000 = 523 598.775 598 3` and
`× 371 000 = 32 375.857 624 5`; sum `555 974.633 222 8` m. This matches handbook G4's
`555 974.633 2 m`.)

**With the current (eastbound).** The current is purely along-track, so `c_⊥ = 0` and the
crab angle is `arcsin(−c_⊥/V_s) = 0`:

```
heading   = exactly 090.000 000°
σ         = 7.2 + 1.5 = 8.7 m/s                                    (row T2)
arrival   = 555 974.633 222 8 / 8.7 = 63 905.130 255 s
          = 17.751 425 h                                                   (8.15)
```

**Against the current (0°E → 5°W).**

```
heading   = exactly 270.000 000°
σ         = 7.2 − 1.5 = 5.7 m/s                                    (row T3)
arrival   = 555 974.633 222 8 / 5.7 = 97 539.409 337 s
          = 27.094 280 h                                                   (8.16)
```

**The cross-check that makes this the cheapest end-to-end consistency test in the suite.**

```
27.094 280 / 17.751 425  =  1.526 315 789 5
Υ = (V_s+|c|)/(V_s−|c|)  =  8.7/5.7  =  29/19  =  1.526 315 789 473 684…   (8.17)
```

The two sides of (8.17) are computed by **completely different code paths** — a full sweep
with backtracking on the left, a one-line ratio on the right. Agreement to 10 figures is
strong evidence that both are right; and because `29/19` is exact, the right-hand side can be
extended to arbitrary precision to test the left as far as it will go. **Run this on every
commit.**

### 8.2.4 The crab-angle variant (derived here — not in handbook G4)

G4's uniform-flow case has `c_⊥ = 0`, so it never exercises the cross-track branch. Add a
third case with the current rotated 90°, which tests exactly the code that T4 tests
pointwise, now end-to-end:

`V_s = 7.2`, `c = (0, 1.5) m/s` (due **north**), same voyage `(0°N,0°E) → (0°N,5°E)`.

```
crab angle  = arcsin(|c_⊥|/V_s) = arcsin(1.5/7.2) = arcsin(0.208 333 333 3)
            = 0.209 870 56 rad = 12.024 64°           steered SOUTH of the track
heading     = 090° + 12.024 64° = 102.024 64°  (true, i.e. south of east)
σ           = sqrt(51.84 − 2.25) = 7.042 016 756 583 30 m/s            (row T4)
arrival     = 555 974.633 222 8 / 7.042 016 756 583 301
            = 78 951.052 3 s = 21.930 848 h                                (8.18)
```

*Derivation of the arrival figure, so it can be checked:*
`7.042 016 756 583 301 × 78 951 = 555 974.264 949 0`; the remainder
`555 974.633 222 8 − 555 974.264 949 0 = 0.368 273 8`, and `0.368 273 8 / 7.042 016 8
= 0.052 296 7`. Hence `78 951.052 297 s`, and `/3600 = 21.930 848 h`.

> **Flagged:** (8.18) and the crab angle are **derived in this file**, not quoted from the
> handbook, and are stated to the precision of the arithmetic shown (≈ 9 significant
> figures). Recompute at higher precision before using them as a 12-figure Class E reference.

The sign is the whole point: a **northward** current requires steering **south** of the
track. If an implementation steers north, its cross-track sign is flipped — the exact failure
of playbook S2, invisible in G4's along-track-only case.

### 8.2.5 Pass criteria for Test 8.2

```
P1  Q1: max |dθ/dt| over the route < 1e-14 rad/s
P2  Q2: zero intermediate waypoints (heading change > 1e-9 rad)
P3  eastbound arrival matches (8.15) to 1e-12 relative
P4  westbound arrival matches (8.16) to 1e-12 relative
P5  ratio matches 29/19 to 1e-10 relative
P6  crab case: heading south of east; magnitude matches (8.18) to 1e-8 relative
P7  the same four cases pass with (c₀, w) = (c + w₀, w₀) for any w₀ with
    |c₀ − w₀| < V_s — i.e. the co-moving solve reproduces them exactly (Eq C.6)
```

P7 deserves emphasis. Because the reduction is a shift of the drift, **Test 8.2 is
simultaneously a co-moving test**: pick any `w₀`, add it to the current, and the co-moving
solve must return bit-comparable answers. That is Theorem C.1(a) exercised on a case with a
closed-form answer, and it costs one extra parameter in the test harness.

---

## Test 8.3 — Linear shear: an analytic geodesic derived in full

**What it decides.** Whether the solver tracks a *curved* extremal — the first test in which
`dθ/dt ≠ 0`, so the inner minimisation and the backtracking must actually work. It is the
test that separates "reproduces straight lines" from "solves the Zermelo problem".

**Status:** the closed-form solution below is **derived here**; the sampled points are
**computed here** from that closed form. Not yet run against the implementation.

### 8.3.1 The field

Planar tangent frame (E8), Cartesian `(x, y)` in metres east and north, drift

```
c(x, y) = ( a·y , 0 ) ,     a = 1.0e-5 s⁻¹  (1 m/s of current per 100 km of northing)  (8.19)
```

Restricted to the strip `|y| ≤ 500 km`, where `|c| ≤ 5.0 m/s < V_s = 7.2 m/s`, so `λ > 0`
everywhere in the test domain and the metric is Randers, positive-definite, admissible (E9
claim 2: `0 ∈ int conv 𝒱`). The value `a = 1e-5 s⁻¹` is the same order as the `L_v ≈ 10⁻⁵ s⁻¹`
used for realistic Indian Ocean shear in ERRATA E6, so this is a physically calibrated test,
not an arbitrary one.

*What breaks outside the strip:* at `|y| > 720 km` we would have `|c| > V_s`, ERRATA E1 takes
over, and the reachable set becomes a cone. The test domain is chosen to stay clear of that
by a factor of 1.44 so that this test isolates curvature, not degeneracy.

### 8.3.2 Derivation of the extremal

Use the mathematical heading convention throughout (apply (8.4) at the interface):
`ẋ = V_s cos θ + a y`, `ẏ = V_s sin θ`. Substituting `u_c = a y`, `v_c = 0` into (8.12),
so that `∂v_c/∂x = ∂u_c/∂x = ∂v_c/∂y = 0` and `∂u_c/∂y = a`:

```
dθ/dt = − a cos²θ                                                          (8.20)
```

**Step 1 — integrate (8.20).** Multiply by `sec²θ`:

```
d(tan θ)/dt = sec²θ · dθ/dt = sec²θ · (−a cos²θ) = −a
⟹  tan θ(t) = tan θ₀ − a t                                                 (8.21)
```

`tan θ` is **exactly linear in time**. This alone is a strong test: it is a one-line
prediction with no free parameters. Write `τ := tan θ`, `τ₀ := tan θ₀`, and take
`θ ∈ (−π/2, π/2)` so that `sec θ = +sqrt(1 + τ²) > 0`. Then `t = (τ₀ − τ)/a`, i.e. `t` is an
affine reparameterisation of `τ`, and `dt = −dτ/a`.

**Step 2 — the northing.** `dy/dτ = ẏ · dt/dτ = V_s sin θ · (−1/a)`, and
`sin θ = τ/sqrt(1+τ²) = τ/sec θ`, so

```
dy/dτ = −(V_s/a) · τ / sqrt(1+τ²)
y(τ)  = y₀ − (V_s/a) [ sqrt(1+τ²) − sqrt(1+τ₀²) ]
      = y₀ − (V_s/a) ( sec θ − sec θ₀ )                                     (8.22)
```

using `∫ τ(1+τ²)^{-1/2} dτ = sqrt(1+τ²)`.

**Step 3 — the easting.** With `K := y₀ + (V_s/a) sec θ₀`, (8.22) reads `y = K − (V_s/a) sec θ`,
so `a y = aK − V_s sec θ`. Work entirely in the variable `τ`, where `sec θ = sqrt(1+τ²)` and
`cos θ = (1+τ²)^{-1/2}`:

```
dx/dτ = ẋ · (dt/dτ) = ( V_s cos θ + a y ) · (−1/a)
      = −(1/a)[ V_s (1+τ²)^{-1/2} + aK − V_s (1+τ²)^{1/2} ]
      = −K − (V_s/a)[ (1+τ²)^{-1/2} − (1+τ²)^{1/2} ]
      = −K + (V_s/a) · τ² (1+τ²)^{-1/2}                                     (8.23)
```

the last line because `(1+τ²)^{-1/2} − (1+τ²)^{1/2} = [1 − (1+τ²)](1+τ²)^{-1/2}
= −τ²(1+τ²)^{-1/2}`. Only one antiderivative is now needed,

```
∫ τ²(1+τ²)^{-1/2} dτ = ½( τ sqrt(1+τ²) − asinh τ )
```

which is checked by differentiating the right-hand side:
`½[ sqrt(1+τ²) + τ²(1+τ²)^{-1/2} − (1+τ²)^{-1/2} ] = ½·[(1+τ²) + τ² − 1](1+τ²)^{-1/2}
= τ²(1+τ²)^{-1/2}` ✓. Define

```
Φ(τ) := τ·sqrt(1+τ²) − asinh τ = sec θ tan θ − ln|sec θ + tan θ|            (8.24)
Φ'(τ) = 2τ² / sqrt(1+τ²)                                                    (8.25)
```

((8.25): `d/dτ[τ(1+τ²)^{1/2}] = (1+τ²)^{1/2} + τ²(1+τ²)^{-1/2} = (1+2τ²)(1+τ²)^{-1/2}`, and
`d/dτ[asinh τ] = (1+τ²)^{-1/2}`; the difference is `2τ²(1+τ²)^{-1/2}`. ✓)

With `Φ` in hand, integrating (8.23) gives

```
x(τ) = x₀ − K·(τ − τ₀) + (V_s/2a)·[ Φ(τ) − Φ(τ₀) ]                         (8.26)
```

**Independent verification of (8.26) by differentiation.**
Differentiate (8.26): `dx/dτ = −K + (V_s/2a)·Φ'(τ) = −K + (V_s/a)·τ²/sqrt(1+τ²)`.
Independently, `dx/dτ = ẋ·(dt/dτ) = (V_s cos θ + a y)(−1/a)`. Substituting
`cos θ = 1/sqrt(1+τ²)` and `a y = aK − V_s sqrt(1+τ²)`:

```
(V_s/sqrt(1+τ²) + aK − V_s sqrt(1+τ²))·(−1/a)
 = −K − (V_s/a)[ 1/sqrt(1+τ²) − sqrt(1+τ²) ]
 = −K − (V_s/a)·[ (1 − (1+τ²)) / sqrt(1+τ²) ]
 = −K + (V_s/a)·τ²/sqrt(1+τ²)   ✓  identical.
```
∎

**The solution, collected.**

> ### Lemma 8.1 (linear-shear Zermelo extremal)
> In the field (8.19) with constant through-water speed `V_s`, every extremal of the
> minimum-time problem is given in closed form by
> ```
> τ(t)  = τ₀ − a t                       (heading:  θ = arctan τ)          (8.21)
> y(t)  = y₀ − (V_s/a)( sqrt(1+τ²) − sqrt(1+τ₀²) )                         (8.22)
> x(t)  = x₀ − K(τ − τ₀) + (V_s/2a)( Φ(τ) − Φ(τ₀) ),  K = y₀ + (V_s/a)sqrt(1+τ₀²)  (8.26)
> ```
> with `Φ` from (8.24). Conversely every curve of this form is an extremal.
>
> **Proof.** Forward direction: Steps 1–3 above, each an exact integration, with (8.26)
> verified by differentiation. Converse: given (8.21), `dθ/dt = d(arctan τ)/dt =
> (dτ/dt)/(1+τ²) = −a/(1+τ²) = −a cos²θ`, which is (8.20); and (8.22), (8.26) were shown to
> reproduce `ẏ = V_s sin θ`, `ẋ = V_s cos θ + a y`. Hence the curve is admissible with
> `|through-water velocity| = V_s`, and satisfies the Zermelo necessary condition. ∎

This is Bryson & Ho's (1975) textbook linear-shear Zermelo problem; it is reproduced here in
full because the spec must be self-contained, not because the result is new.

### 8.3.3 The test instance and its sampled points

```
V_s = 7.2 m/s ,  a = 1.0e-5 s⁻¹ ,  x₀ = y₀ = 0 ,  θ₀ = 45° (τ₀ = 1)
V_s/a = 720 000 m ,   V_s/2a = 360 000 m ,   K = 720 000·√2 = 1 018 233.764 908 63 m
```

Constants used, to 16 figures:
`√2 = 1.414 213 562 373 095`, `√1.5625 = 1.25` (exact), `√1.25 = 1.118 033 988 749 895`,
`√1.0625 = 1.030 776 406 404 415`;
`asinh 1 = ln(1+√2) = 0.881 373 587 019 543`, `asinh 0.75 = ln 2 = 0.693 147 180 559 945`,
`asinh 0.5 = ln φ = 0.481 211 825 059 604`, `asinh 0.25 = 0.247 466 461 57`.
Hence
`Φ(1) = 1.414 213 562 373 095 − 0.881 373 587 019 543 = 0.532 839 975 353 552`,
`Φ(0.75) = 0.9375 − 0.693 147 180 559 945 = 0.244 352 819 440 055`,
`Φ(0.5) = 0.559 016 994 374 947 − 0.481 211 825 059 604 = 0.077 805 169 315 343`,
`Φ(0.25) = 0.257 694 101 601 104 − 0.247 466 461 57 = 0.010 227 640 03`,
`Φ(0) = 0`.

**Expected trajectory points** (each row is (8.21)/(8.22)/(8.26) evaluated; `t = (1−τ)/a`):

| `t` [s] | `tan θ` | `θ` [deg, math conv.] | `x` [m] | `y` [m] |
|---|---|---|---|---|
| 0 | 1 | 45.000 000 000 | 0 | 0 |
| 25 000 | 0.75 | 36.869 897 645 8 | **150 703.065 098** | **118 233.764 909** |
| 50 000 | 0.5 | 26.565 051 177 1 | **345 304.352 281** | **213 249.293 009** |
| 75 000 | 0.25 | 14.036 243 467 9 | **575 534.882 974** | **276 074.752 297** |
| 100 000 | 0 | 0.000 000 000 | **826 411.373 781** | **298 233.764 909** |

Worked arithmetic for the last row, so the table is checkable:
`y = −720 000·(1 − 1.414 213 562 373 095) = 720 000 × 0.414 213 562 373 095 = 298 233.764 908 6`;
`x = −1 018 233.764 908 63 × (0 − 1) + 360 000 × (0 − 0.532 839 975 353 552)
 = 1 018 233.764 908 6 − 191 822.391 127 3 = 826 411.373 781 3`.

And for `t = 50 000`:
`y = 720 000 × (1.414 213 562 373 095 − 1.118 033 988 749 895) = 720 000 × 0.296 179 573 623 200
 = 213 249.293 008 7`;
`x = 1 018 233.764 908 63 × 0.5 + 360 000 × (0.077 805 169 315 343 − 0.532 839 975 353 552)
 = 509 116.882 454 3 − 163 812.530 173 8 = 345 304.352 280 6`.

**Sanity:** the straight-line distance from `(0,0)` to the `t = 100 000` endpoint is
`sqrt(826 411.37² + 298 233.76²) ≈ 878 578 m`, i.e. a mean ground speed of `8.786 m/s` against
a through-water speed of `7.2 m/s`. The excess is supplied by the shear, whose value at the
final northing is `a·y = 1e-5 × 298 233.76 = 2.982 m/s` — consistent, and comfortably inside
`|c| < V_s`. ✓

### 8.3.4 Optimality: what is proved and what is not

The test as specified is a **boundary-value** test: solve from `A = (0,0)` to
`B = (826 411.373 781, 298 233.764 909)` and compare the returned route and arrival time to
the table. For that to be a valid test of a *minimum*-time solver, the tabulated extremal must
be the minimiser.

**What is proved.** Lemma 8.1 shows the tabulated curve is an extremal, and the *unique*
extremal with `θ(0) = 45°` — because (8.21) determines `θ(t)` from `θ₀` alone, and (8.22),
(8.26) then determine the curve. So any minimiser through these endpoints in this time is
either this curve or an extremal with a different `θ₀`.

**No conjugate point on the test interval.** Consider the exponential map
`E : (τ₀, t) ↦ (x, y)` from the source `(0,0)`, given by (8.22)/(8.26) with `y₀ = x₀ = 0`,
`τ = τ₀ − a t`. Differentiating (using `∂K/∂τ₀ = (V_s/a)·τ₀/sqrt(1+τ₀²) = (V_s/a) sin θ₀`, and
noting `τ − τ₀ = −a t` is independent of `τ₀` at fixed `t`):

```
∂y/∂t   = V_s sin θ
∂x/∂t   = V_s cos θ + a y
∂y/∂τ₀  = (V_s/a)( sin θ₀ − sin θ )
∂x/∂τ₀  = V_s t sin θ₀ + (V_s/a)( τ sin θ − τ₀ sin θ₀ )                     (8.27)
det J   = (∂x/∂τ₀)(∂y/∂t) − (∂x/∂t)(∂y/∂τ₀)                                 (8.28)
```

Evaluating (8.28) on the test extremal (`τ₀ = 1`, `sin θ₀ = 1/√2 = 0.707 106 781`):

| `t` [s] | `det J` [m²/s] |
|---|---|
| 0 | 0 (the source; every extremal leaves from here — not a conjugate point) |
| 50 000 | **−1.905 × 10⁶** |
| 100 000 | **−5.184 × 10⁶** |

(At `t = 100 000 = 1/a` the first product in (8.28) vanishes twice over — `sin θ = 0` and,
coincidentally, `V_s t = V_s/a` makes `∂x/∂τ₀ = 0` — so
`det J = −(V_s + a y)(V_s/a) sin θ₀ = −(7.2 + 2.982 337 65)(720 000)(0.707 106 781)
= −5.184 0 × 10⁶`.)

`det J ≠ 0` on `(0, 100 000]`, so the extremal lies in a **field of extremals** and is a
strong local minimiser by the classical Weierstrass field construction (the Weierstrass
excess function of a Randers metric is non-negative because the indicatrix is convex, which
here is the disc `D(c, V_s)`).

> ### Conj 8.2 (global optimality of the §8.3 extremal)
> The tabulated extremal is the *global* minimum-time route from `A` to `B`.
>
> **What is missing.** Global optimality requires in addition that `B` is not beyond the
> **cut locus** of `A` — equivalently, that the exponential map `E` is injective on the
> parameter region reaching `B`. We prove absence of *conjugate* points (above) but not
> absence of a cut point, and we have not carried out the global injectivity argument. The
> shear field is unbounded, and a route that first runs far north to harvest a larger drift
> is a genuine competitor in principle; a scaling estimate (go north for `t/2`, then east)
> gives an arrival time `≈ 2·sqrt(X/(a V_s)) = 2·sqrt(826 411/7.2e-5) ≈ 214 000 s` for this
> `X`, which is **more than twice** the tabulated `100 000 s`, so that family does not win
> here — but that is an estimate over one competitor family, not a proof over all curves.

**Consequently the pass criterion is asymmetric, and deliberately so.**

```
P1  the returned route matches the tabulated (x, y) points to the Class D floor of §8.7
    (a 16-neighbour grid route will not do better; a Zermelo-polished route should reach
     1e-6 relative)
P2  the returned arrival time is ≤ 100 000 s + Class D floor
P3  IF the solver returns an arrival strictly and materially below 100 000 s, that is NOT a
    test failure — it is either a bug or a refutation of Conj 8.2, and must be investigated,
    not suppressed. Report the route.
P4  tan θ along the returned route is linear in t: fit tan θ = α + βt and require
    |β + a|/a ≤ 1e-3 and R² ≥ 0.999.  (8.21) is the cleanest single assertion in this test.
P5  co-moving variant: run the same case with c₀(x,y) = (a y + w_x, w_y) and w = (w_x, w_y).
    The co-moving drift is again (a y, 0), so the SAME table must be returned in co-moving
    coordinates, and the ground route must be the table plus w·τ (Eq C.5).
```

P4 is the most valuable line in this test: it is a *shape* assertion that no amount of
resolution tuning can fake, and it fails immediately if the inner minimisation is pinned to
lattice directions (playbook S3 cause 1) because a quantised heading is a staircase, not a
line.

---

## Test 8.4 — Rankine vortex: an exact invariant without an exact solution

**What it decides.** Behaviour in a field with **closed streamlines, a discontinuous
vorticity, and a genuine left/right asymmetry** — the three things a real eddy has and the
shear of §8.3 does not. There is no closed-form geodesic, so the test is built from an exact
conserved quantity, exact bounds, and an exact symmetry, all derived below.

**Status:** invariant and bounds **derived here**. Not yet run.

**Prior art.** The vortex model is Rankine (1858). The conserved quantity is the Clairaut /
Noether invariant of a rotationally symmetric metric; its specialisation to the Zermelo
problem is derived here because we need the explicit form, not because it is new.

### 8.4.1 The field

Centre at the origin of the tangent plane, core radius `R`, peak swirl `c_max` at `r = R`:

```
c(r) = c_φ(r) · 𝐞_φ ,     𝐞_φ = (−sin φ, cos φ)     (counter-clockwise positive)

c_φ(r) = c_max · r/R          r ≤ R    (solid-body core)
c_φ(r) = c_max · R/r          r > R    (irrotational free vortex)           (8.29)
```

Normative test parameters: `R = 100 km`, `c_max = 3.0 m/s`, `V_s = 7.2 m/s`. The circulation
is `Γ = 2π R c_max = 2π × 10⁵ × 3.0 = 1 884 955.592 153 876 m²/s`.

**Exact pointwise checks on the field itself** (these catch interpolation and unit bugs
before any routing happens):

| Quantity | Exact value | Why it catches something |
|---|---|---|
| `c_φ(50 km)` | **1.5 m/s** | linear core branch |
| `c_φ(100 km)` from **both** branches | **3.0 m/s** | continuity at `r = R`; a mismatch means one branch has `R` and `r` swapped |
| `c_φ(200 km)` | **1.5 m/s** | `1/r` branch |
| `c_φ(300 km)` | **1.0 m/s** | `1/r` branch |
| circulation `∮c·dl` on `r = 200 km` | **1 884 955.592 153 876 m²/s** `= Γ` | independent of `r` outside the core |
| circulation on `r = 50 km` | **471 238.898 038 469 m²/s** `= Γ/4` | scales as `r²/R²` inside |
| vorticity inside the core | **6.0 × 10⁻⁵ s⁻¹** exactly `= 2 c_max/R` | uniform |
| vorticity outside | **0** exactly | the `1/r` branch is irrotational |
| `\|c\|_max / V_s` | `3.0/7.2 = 0.416 666 …` | `λ > 0` everywhere; Randers admissible |

`Υ_loc` at `r = R` is `(7.2+3.0)/(7.2−3.0) = 10.2/4.2 = 17/7 = 2.428 571 428 6` — well under
the `Υ_heap = 12` fallback threshold of ERRATA E2, so this test exercises the **bucket queue**
path, not the heap path. (§8.9 exercises the other.)

### 8.4.2 The exact invariant

> ### Lemma 8.3 (Clairaut invariant for a rotationally symmetric Zermelo problem)
> Let the drift be purely azimuthal, `c = c_φ(r) 𝐞_φ`, with constant through-water speed
> `V_s` and `|c| < V_s`. Let `ψ` be the angle from the outward radial direction `𝐞_r` to the
> **through-water heading** `n`, measured towards `𝐞_φ`. Then along every time-optimal route
> ```
> p_φ  =  r · sin ψ / ( V_s + c_φ(r) · sin ψ )  =  const                    (8.30)
> ```
>
> **Proof.** For the minimum-time problem with achievable ground velocities
> `𝒱 = D(c, V_s)`, the eikonal Hamiltonian is the support function of `𝒱`:
> `H(x,p) = max_{v∈𝒱} ⟨v,p⟩ = V_s|p| + ⟨c(x), p⟩`, and the value function satisfies
> `H(x, ∇T) = 1`. The characteristics of `H(x,p) = 1` are the bicharacteristics of the
> Hamiltonian system `ẋ = ∂H/∂p`, `ṗ = −∂H/∂x`.
>
> In polar coordinates `(r, φ)` with conjugate momenta `(p_r, p_φ)`, the covector `p` has
> components `⟨p, 𝐞_r⟩ = p_r` and `⟨p, 𝐞_φ⟩ = p_φ/r`, so
> ```
> |p| = sqrt( p_r² + p_φ²/r² ) ,      ⟨c, p⟩ = c_φ(r)·p_φ/r
> H(r, p_r, p_φ) = V_s·sqrt(p_r² + p_φ²/r²) + c_φ(r)·p_φ/r
> ```
> `H` contains **no explicit `φ`**. Hence `ṗ_φ = −∂H/∂φ = 0`: `p_φ` is conserved. (This is
> Noether's theorem for the rotational symmetry; the algebra above is the whole content.)
>
> It remains to express `p_φ` in observable quantities. From `H = V_s|p| + ⟨c,p⟩`,
> `∂H/∂p = V_s·p/|p| + c`, so the optimal ground velocity is `ẋ = V_s·(p/|p|) + c`, i.e.
> **the through-water heading is exactly the direction of `p`**: `n = p/|p|`. Then
> `H = 1` gives `|p|(V_s + ⟨c, n⟩) = 1`, so `|p| = 1/(V_s + ⟨c,n⟩)`. With
> `⟨n, 𝐞_φ⟩ = sin ψ` and `c = c_φ 𝐞_φ`, we get `⟨c,n⟩ = c_φ sin ψ` and
> ```
> p_φ = r·⟨p, 𝐞_φ⟩ = r·|p|·sin ψ = r sin ψ / ( V_s + c_φ(r) sin ψ )
> ```
> which is (8.30). ∎

**Degenerate check.** With `c_φ ≡ 0`, (8.30) reduces to `r sin ψ / V_s = const`, i.e.
`r sin ψ = const` — the elementary fact that a straight line's perpendicular distance from the
origin is constant. ✓ The invariant is therefore correctly normalised.

**How to use it.** (8.30) requires **no reference solution and no second solve.** Evaluate it
at every waypoint of the returned route and require the relative spread to be small:

```
I := max_k p_φ(k) ,   i := min_k p_φ(k) ,   spread := (I − i) / max(|I|, |i|)   (8.31)
```

> **Scope, stated because it is easy to misuse.** (8.30) holds for the **continuum** extremal.
> A route produced by a 16-neighbour grid sweep has its heading quantised to a lattice, and
> `∂p_φ/∂ψ = r V_s cos ψ /(V_s + c_φ sin ψ)²` is `O(r)`, so a heading error of `13°` at
> `r = 200 km` moves `p_φ` by tens of kilometres — a spread of order 10 %. **Test 8.4's
> invariant is a test of the Zermelo polish stage (Prop 3.5), not of the grid sweep.** Applied
> to a raw grid route it measures the metrication floor of §8.7 and nothing else.
> Normative thresholds: `spread ≤ 1e-3` for a polished route; for a raw grid route, *report*
> the spread and do not gate on it.

### 8.4.3 Exact bounds on the arrival time

Voyage `A = (−400 km, 0)` to `B = (+400 km, 0)`, i.e. straight through the vortex centre,
`|AB| = 800 km`.

**Lower bound.** The speed made good in any direction is at most `V_s + max|c| = 10.2 m/s`,
and the route length is at least `|AB|`:

```
T* ≥ 800 000 / 10.2 = 78 431.372 549 s = 21.786 492 h                       (8.32)
```

**Upper bound, by exhibiting an admissible route.** Take the straight segment along `y = 0`.
There `𝐞_φ = ±𝐞_N`, so the drift is **purely cross-track** and the speed made good is
`sqrt(V_s² − c_φ(|x|)²)` — case T4, evaluated pointwise. By symmetry about `x = 0`:

```
T_line = 2 ∫₀^X dx / sqrt( V_s² − c_φ(x)² )
       = 2[ (R/c_max)·arcsin(c_max/V_s)
            + (1/V_s²)( sqrt(V_s²X² − c_max²R²) − R·sqrt(V_s² − c_max²) ) ]  (8.33)
```

*Derivation.* On `[0,R]`, `c_φ = c_max x/R`; substituting `s = x/R` gives
`R∫₀¹ ds/sqrt(V_s² − c_max²s²) = (R/c_max)·arcsin(c_max/V_s)`. On `[R,X]`,
`c_φ = c_max R/x`, so the integrand is `x dx / sqrt(V_s²x² − c_max²R²)`, whose antiderivative
is `sqrt(V_s²x² − c_max²R²)/V_s²`; evaluating at `X` and `R` gives the second term (at `x=R`
the radicand is `R²(V_s² − c_max²)`). ∎

Numerically, with `R = 10⁵`, `c_max = 3`, `V_s = 7.2`, `X = 4×10⁵`:

```
arcsin(3/7.2) = arcsin(0.416 666 666 7) = 0.429 775 2 rad
term 1  = (10⁵/3) × 0.429 775 2                    = 14 325.84 s
sqrt(V_s²X² − c_max²R²) = sqrt(8.294 4e12 − 9e10) = sqrt(8.204 4e12) = 2 864 333.3
R·sqrt(V_s² − c_max²)   = 10⁵ × sqrt(42.84)       =   654 522.3
term 2  = (2 864 333.3 − 654 522.3)/51.84          = 42 627.53 s
T_line  = 2 × (14 325.84 + 42 627.53) = 113 906.7 s = 31.640 8 h            (8.34)
```

> **Flagged:** (8.34) is **derived here** to ≈ 7 significant figures by hand arithmetic. The
> closed form (8.33) is exact; recompute (8.34) at machine precision before using it as a
> Class E reference.

Hence, exactly,

```
21.786 492 h  ≤  T*  <  31.640 8 h                                          (8.35)
```

with the right inequality **strict**, because the straight segment is not an extremal (its
`p_φ` is not constant: at `x = −400 km`, `ψ = 90°` and `r = 400 km` give
`p_φ = 400 000/(7.2+0.75) = 50 314`, while at `x = −100 km`, `p_φ = 100 000/(7.2+3.0) = 9 804`
— a factor of five, so (8.30) is violated and by Lemma 8.3 the segment cannot be optimal).
Any implementation returning `T` outside (8.35) is wrong, and the two ends fail for different
reasons: below `21.786 h` means the metric is over-crediting drift (sign or `σ` bug); above
`31.641 h` means the solver is worse than a straight line, i.e. the search is not finding the
free route it is standing on.

### 8.4.4 The side test — the sharpest sign check in the suite

For a **counter-clockwise** vortex (`Γ > 0`) and an eastbound voyage:

- north of the centre, at `(0, +y)`, `φ = 90°` so `𝐞_φ = (−1, 0)`: the drift is **westward**,
  opposing.
- south of the centre, at `(0, −y)`, `φ = −90°` so `𝐞_φ = (+1, 0)`: the drift is **eastward**,
  helping.

```
PREDICTION: the time-optimal eastbound route passes SOUTH of a counter-clockwise vortex,
            and NORTH of a clockwise one.                                    (8.36)
```

This is a **binary, unambiguous, resolution-independent** assertion, and it is the single
cheapest detector of the two most common bugs in the field: an east/north transposition and a
sign flip in the drift decomposition (playbook S2). It also cannot be passed by accident —
a coin flip has a 50 % failure rate, and running both signs of `Γ` makes accidental passing a
25 % event, further reduced by the mirror test below.

**The mirror test (exact).** The map `(x, y, Γ) ↦ (x, −y, −Γ)` is an exact symmetry of the
problem, and `A`, `B` lie on `y = 0`. Therefore the solve with `+Γ` and the solve with `−Γ`
must return arrival times that are **identical**, and routes that are exact reflections:

```
| T(+Γ) − T(−Γ) |  ≤  round-off, IF the grid is symmetric about y = 0        (8.37)
```

(8.37) is Class I when the grid has a node row on `y = 0` and is symmetric — then the two
discrete problems are related by a relabelling of nodes and the two answers are bitwise equal
up to floating-point summation order, so require `≤ 1e-9` relative and investigate anything
larger. On an asymmetric grid the difference measures grid-induced anisotropy directly, which
is a useful number to publish.

### 8.4.5 Pass criteria for Test 8.4

```
P1  every field value in the §8.4.1 table, to 1e-12 relative
P2  continuity of c_φ at r = R from both branches, to 1e-15 absolute
P3  T* inside the exact bracket (8.35)
P4  the side test (8.36), for both signs of Γ
P5  the mirror test (8.37), ≤ 1e-9 relative on a symmetric grid
P6  Clairaut spread (8.31): ≤ 1e-3 on a POLISHED route; reported, not gated, on a raw
    grid route
P7  co-moving variant: advect the whole vortex at w = (2.0, 0.5) m/s and re-run. Since
    c_eff = c₀ − w is no longer rotationally symmetric, Lemma 8.3 does NOT apply in the
    co-moving frame — P6 is skipped and P3/P4 are re-derived with c ← c₀ − w. Recording
    this explicitly prevents an implementer from asserting a broken invariant.
```

P7 is a genuine limitation worth naming: the reduction preserves *Randers* structure (C.6)
but not *rotational symmetry*, so a symmetry-derived invariant does not survive the shift.
The reduction buys stationarity, not extra symmetry.

---

## Test 8.5 — THE BIJECTION TEST for Theorem C.1

**This is the decisive test of KAIROS.** Everything else in this file validates apparatus.
Test 8.5 validates the claim.

**Status: RUN. Measured**, `CORE-THEOREM.md` §4.

### 8.5.1 What is being tested, and why it is an identity and not a comparison

Theorem C.1(a) says: `x(·)` is admissible for the ground problem `ẋ ∈ 𝒱(x,t) = 𝒱₀(x − wt)`
**iff** `y(t) := x(t) − w t` is admissible for the stationary problem `ẏ ∈ 𝒱_w(y)`, with the
same time parameterisation. That is a statement about **individual trajectories**, not about
optimal values. So it can be tested on one trajectory, with no second optimisation, and
therefore with **no stencil error anywhere in the measurement**.

That is the whole design of the test, and it is what makes it decisive.

### 8.5.2 Setup (as run)

```
V_s      = 7.0 m/s
field    = eastward Gaussian jet, peak 3.0 m/s, half-width 60 km
advection w = (2.0, 0.5) m/s          |w| = 2.061 552 8 m/s
voyage   = 600 km
grid     = 4 km  (diagonal 5.656 854 km)
```

**Assumption A2 check, done exactly rather than by the triangle inequality.** The jet is
eastward with magnitude `j ∈ [0, 3.0]`, so `c_eff = c₀ − w = (j − 2.0, −0.5)` and
`|c_eff|² = (j−2)² + 0.25`, which over `j ∈ [0,3]` is maximised at the endpoint farthest from
`j = 2`:

```
j = 0 : |c_eff| = sqrt(4.25)  = 2.061 552 812 8   ← the max (here c_eff = −w exactly)
j = 3 : |c_eff| = sqrt(1.25)  = 1.118 033 988 7
σ_min^w = V_s − max|c_eff| = 7.0 − 2.061 552 812 8 = 4.938 447 187 2 m/s
A2:  |w| = 2.061 552 812 8  <  4.938 447 187 2  ✓   margin ratio 0.417 446
```

so `F_max^w·|w| = |w|/σ_min^w = 0.417 4 < 1` and the interception argument of Theorem C.1(c)
applies with room to spare. The triangle-inequality bound `max|c₀ − w| ≤ 3.0 + |w| = 5.06`
would have given `σ_min^w = 1.94 < |w|` and wrongly declared A2 to fail. **Compute
`max|c₀ − w|` over the field; never bound it by `max|c₀| + |w|`.** (C.7) is then satisfied
cell by cell, with the tightest margin `7.0 − 2.062 = 4.938 m/s` in the *calm* cells, not the
jet cells — which is counter-intuitive and worth reporting per cell rather than reasoning
about.

### 8.5.3 The procedure (normative, language-agnostic)

```
Alg 8.5  BIJECTION CHECK
Input:   ground field E₀ (a pattern), advection w, vessel speed V_s,
         a co-moving route as a node chain (y_k, τ_k), k = 0..M
Output:  four residual scalars; all four are Class I (exact zero in exact arithmetic)

 1  SOLVE in the co-moving frame:  T_w  ←  stationary sweep on 𝒱_w(y) = 𝒱₀(y) ⊖ w
 2  RECOVER the co-moving geodesic (y_k, τ_k) by backtracking
 3  MAP to the ground frame:      x_k := y_k + w·τ_k                         (C.5)
 4  FOR each leg k = 0 .. M−1:
 5      Δτ   := τ_{k+1} − τ_k                          (require Δτ > 0)
 6      v_x  := (x_{k+1} − x_k)/Δτ                     ground leg velocity
 7      v_y  := (y_{k+1} − y_k)/Δτ                     co-moving leg velocity
 8      y_m  := ½(y_k + y_{k+1})   ;  t_m := ½(τ_k + τ_{k+1})
 9      x_m  := ½(x_k + x_{k+1})
10      c_gnd := c₀( x_m − w·t_m )    ← the ADVECTED field, at the ACTUAL position
11                                       and the ACTUAL time of that leg
12      c_com := c₀( y_m ) − w        ← the shifted stationary field
13      RESIDUAL_k := ‖ (v_x − c_gnd) − (v_y − c_com) ‖          [m/s]        (8.38)
14      EXCESS_k   := ‖ v_y − c_com ‖ − V_s                       [m/s]       (8.39)
15      EXCESS_gnd_k := ‖ v_x − c_gnd ‖ − V_s                     [m/s]       (8.40)
16  REPORT max_k |RESIDUAL_k|, max_k EXCESS_k, max_k EXCESS_gnd_k
17  CONVERSE: solve independently in the GROUND frame, map that route into the
18            co-moving frame by y = x − w t, and report the difference in the
19            maximum required through-water speed V_req between the two views.
```

Line 10 is the load-bearing line. `c_gnd` must be **the advected field sampled at the leg's
own ground position and the leg's own absolute time** — not the pattern, not a frozen
snapshot, not the co-moving field in disguise. If an implementation evaluates `c₀(x_m)`
instead of `c₀(x_m − w t_m)`, the test passes trivially and measures nothing.

### 8.5.4 Why every residual is exactly zero — proof

> ### Lemma 8.4 (the bijection residual vanishes identically)
> In exact arithmetic on a flat tangent frame, `RESIDUAL_k = 0` for every leg, for every
> chain, optimal or not.
>
> **Proof.** By (C.5), `x_k = y_k + w τ_k` for every `k`. Hence
> ```
> v_x − v_y = [ (x_{k+1} − x_k) − (y_{k+1} − y_k) ] / Δτ
>           = [ w τ_{k+1} − w τ_k ] / Δτ  =  w·Δτ/Δτ  =  w                   (8.41)
> ```
> exactly — the ground and co-moving leg velocities differ by exactly `w`, independent of
> the chain.
>
> For the fields, the ground midpoint is
> ```
> x_m = ½(x_k + x_{k+1}) = ½(y_k + y_{k+1}) + w·½(τ_k + τ_{k+1}) = y_m + w·t_m
> ⟹  x_m − w·t_m = y_m       exactly                                        (8.42)
> ```
> so line 10 evaluates `c₀(y_m)` and line 12 evaluates `c₀(y_m) − w`, giving
> ```
> c_gnd − c_com = c₀(y_m) − (c₀(y_m) − w) = w                                (8.43)
> ```
> Substituting (8.41) and (8.43) into (8.38):
> `(v_x − c_gnd) − (v_y − c_com) = (v_x − v_y) − (c_gnd − c_com) = w − w = 0`. ∎
>
> **Consequences.** (i) The residual is *not* an approximation that improves with resolution
> — it is identically zero at every resolution, so any measured value is pure floating-point
> and geodesy round-off. (ii) `EXCESS_k` and `EXCESS_gnd_k` are equal, exactly, by the same
> substitution — the ground-frame through-water velocity of the mapped route equals its
> co-moving through-water velocity, vector for vector. This is Theorem C.1(a) made
> arithmetic.

**Where the identity is only approximate.** (8.41)–(8.43) use a flat frame. On the sphere,
`x = y + w τ` is applied through the local-frame conversion (E8.1); the composition of two
such conversions differs from a single one by curvature terms of relative order
`(|w|τ/R_E)²`. For `|w|τ ≈ 500 km` that is `(0.078)² ≈ 6.2e-3` in the *displacement*, which is
large — **but it enters the residual only through the difference of two evaluations of the
same conversion**, which cancels to the order at which the conversion is a group operation.
The measured residual `9.77e-14 m/s` against velocities of order `7 m/s` is `1.4e-14` relative,
about 60 ulps of IEEE double — consistent with a chain of ~10 trigonometric operations and
**not** with a curvature term. That is itself a result: the spherical implementation does not
leak curvature error into the reduction.

### 8.5.5 The measured results

From `CORE-THEOREM.md` §4, the run described in §8.5.2:

| Check | Theorem predicts | **Measured** | Class |
|---|---|---|---|
| Per-leg bijection residual (8.38) | **exactly 0** | **`9.77e-14` m/s** | I |
| Co-moving route, checked in the co-moving frame: excess over `V_s` (8.39) | 0 | **`2.84e-14` m/s** | I |
| Same route mapped to ground, checked against the **advected** field (8.40) | 0 | **`9.15e-14` m/s** | I |
| Converse (ground route mapped to co-moving): difference in max `V_req` | 0 | **`3.55e-15` m/s** | I |
| Ground arrival vs `x_B` | ≤ grid diagonal | **1.46 km** (diagonal 5.66 km) | D |

**Verified to machine precision.** Theorem C.1(a) is not approximately true on this field; it
is true to the last bits the hardware has.

### 8.5.6 The second, unplanned finding — and it is contribution 2

An *independent* ground-frame solve of the same problem required

```
V_req = 7.006 721 m/s        against a ship capable of V_s = 7.0 m/s
excess = 6.721e-3 m/s        i.e. 6.72e-03                                   (8.44)
```

Compare `2.84e-14 m/s` for the co-moving solve. **Eleven orders of magnitude.** The three
numbers must not be confused, and implementations routinely do confuse them:

```
2.84e-14  co-moving route, checked in the co-moving frame
9.15e-14  the SAME route, mapped to ground, checked against the advected field
6.72e-03  a DIFFERENT route — the one an independent ground-frame solve produces
```

The `6.72e-03` is not a bug in the ground solver. It is the **temporal discretisation error**:
sampling the advected field at the leg midpoint is only first-order accurate in *time* as well
as in space, so the field the ground solver believed it was steering against differs slightly
from the field at the leg's endpoints, and the recovered route asks the ship for slightly more
speed than it has.

**Order-of-magnitude derivation, to confirm the mechanism** (flagged as an estimate):
for a Gaussian jet of peak `A = 3.0 m/s` and half-width `L = 60 km`, `max|∇c₀| = A/(L√e)
= 3.0/(60 000 × 1.648 7) = 3.03e-5 s⁻¹`. With `|w| = 2.062 m/s`, the frozen-pattern time
derivative is `|∂c/∂t| = |(w·∇)c₀| ≲ 6.25e-5 m/s²`. A 4 km leg at ~7 m/s lasts `Δt ≈ 571 s`,
so half-leg sampling error in the drift is `≲ 6.25e-5 × 285 ≈ 1.8e-2 m/s`. **Predicted
`O(10⁻²) m/s`; measured `6.7e-3 m/s`** — the same order, on the low side as expected because
the route does not run along the steepest gradient. The mechanism is confirmed.

> **The reduction eliminates the temporal discretisation error entirely**, because in the
> co-moving frame there is nothing to sample in time. This was not designed for; it falls out
> of Theorem C.1(b). It means the co-moving solve is not merely faster and better-licensed —
> **it is more accurate on the same grid.** That is contribution 2, and (8.44) is its evidence.

*What breaks without A1:* the residual (8.38) is no longer identically zero; it acquires the
term `R(x_m, t_m)`, the non-translating part of the field (C.8). **Test 8.5 therefore doubles
as a quantitative measure of the A1 violation**: run it on a real forecast stack and
`max_k |RESIDUAL_k|` *is* `max |R|` along the route, in m/s, directly interpretable. That is
the recommended operational diagnostic, and it costs one pass over the route.

### 8.5.7 Why this test — and NOT a two-grid comparison — is the right instrument

The obvious test is: solve the same problem independently in both frames and compare arrival
times. **That test cannot settle Theorem C.1, and no amount of computation makes it able to.**

Solving the same problem in both frames on the same 16-neighbour grid gave (measured,
`CORE-THEOREM.md` §4):

```
h [km]:     24     16     12      8      6      4      3
disc. [%]: 0.36   0.15   0.79   0.92   0.17   0.98   0.58                   (8.45)
```

The discrepancy **does not converge under refinement**. It is the fixed-stencil metrication
floor, quantified and explained in §8.7: a stencil with finitely many neighbours quantises
heading, and the quantisation bias is `O(Δθ²)` in the angular gap, **independent of `h`**.
The two frames quantise *differently* — their optimal headings differ by the drift shift `w` —
so their biases do not cancel.

The instrument comparison, in one line:

| | Two-grid comparison | **Bijection test 8.5** |
|---|---|---|
| What it measures | difference of two optimal values | a per-leg velocity identity |
| Optimisation error present? | **yes, twice** | **no** |
| Noise floor | `~1 %` of arrival time, non-vanishing | `9.77e-14` m/s |
| Smallest detectable C.1 violation | `δ ≳ 0.01 × V_s ≈ 0.07 m/s` | `δ ≈ 1e-13 m/s` |
| Discriminating power | — | **~12 orders of magnitude finer** |
| Does refinement help? | **no** (8.45) | irrelevant — it is an identity |

`0.07 / 9.77e-14 = 7.2e11`, i.e. the bijection test resolves violations about **7×10¹¹ times
smaller** than the two-grid test can. But the decisive point is not sensitivity, it is
**confounding**: the two-grid residual is dominated by a term that has nothing to do with
Theorem C.1 and that does not vanish in the limit. A test whose noise floor is a fixed
systematic bias of unrelated origin is not a weak test of the hypothesis; it is not a test of
the hypothesis at all.

The two-grid comparison retains exactly one legitimate role, and §8.11 uses it in that role:
as an **end-to-end integration check** that the two pipelines agree to within the known,
published, measured floor. Agreement at `0.860 %` (§8.11) is then the *expected* outcome, not
a confirmation of the theorem.

### 8.5.8 Pass criteria for Test 8.5

```
P1  max_k |RESIDUAL_k| ≤ 1e-11 m/s               (Class I; 100× the measured floor)
P2  max_k EXCESS_k     ≤ 1e-11 m/s
P3  max_k EXCESS_gnd_k ≤ 1e-11 m/s               (the mapped route, vs the ADVECTED field)
P4  converse residual  ≤ 1e-11 m/s
P5  ground landfall miss ≤ one grid diagonal      (Class D)
P6  Δτ > 0 on every leg; the test aborts rather than dividing by zero
P7  ANTI-TEST (mandatory): re-run line 10 with c₀(x_m) — the un-advected field — and
    assert the test now FAILS. A bijection test that passes against the wrong field is
    measuring nothing, and this is the only way to know it is wired up.
P8  report max_k |RESIDUAL_k| on the real forecast stack as the A1-violation metric
```

P7 is not optional. It is the difference between a test and a decoration.

---

## Test 8.6 — ε-refinement protocol for the Pareto front

**What it decides.** Whether the ε-Pareto guarantee of Thm 5.2 is real, and specifically
whether the implementation buckets on the **objective value** (ERRATA E7.1, the Tsaggouris &
Zaroliagis 2009 construction) or on the per-edge **increment** (the vacuous version the first
draft had). The two are indistinguishable on short voyages and differ by orders of magnitude
on long ones. **Status: protocol only. Not yet run.**

**Prior art.** Front-quality indicators: Zitzler, Thiele, Laumanns, Fonseca & Grunert da
Fonseca (2003). Value bucketing: Tsaggouris & Zaroliagis (2009). Multi-objective control by
front propagation: Kumar & Vladimirsky (2010). None of this is claimed as new (ERRATA E11).

### 8.6.1 Indicators

For minimisation, with front sets `A` (the reference) and `B` (the candidate):

```
I_ε+(A, B) := max_{b ∈ B} min_{a ∈ A} max_i ( a_i − b_i )      additive        (8.46)
I_ε×(A, B) := max_{b ∈ B} min_{a ∈ A} max_i ( a_i / b_i )      multiplicative  (8.47)
```

`I_ε+` is the smallest additive amount by which `A` must be shifted to weakly dominate every
point of `B`; `I_ε×` is the smallest factor. `I_ε× ≤ 1` means `A` weakly dominates `B`.

> **Which indicator, and why it matters.** The E7 guarantee is **multiplicative**
> (`ℓ_i ≤ (1+ε)ℓ*_i`), so `I_ε×` is the indicator that matches the theorem and needs no
> normalisation. `I_ε+` mixes seconds, kilograms and dimensionless risk and is meaningless
> unless each objective is first normalised by its range over the union front `A ∪ B`. Report
> both — `I_ε×` for the guarantee, normalised `I_ε+` for a human-readable spread — and state
> the normalisation explicitly. An unnormalised additive indicator over mixed units is the
> most common way these numbers are reported wrongly.

Objective 0 (time) is **never bucketed** (ERRATA E7), so the guarantee is one-sided in time:
the front is exact in time and `(1+ε)`-approximate in objectives `2..k`. The indicators must
be computed over objectives `2..k` for the guarantee check, and over all `k` for reporting.

### 8.6.2 Protocol

```
Alg 8.6  ε-REFINEMENT
 1  fix one routing problem and one grid h; vary ONLY ε
 2  solve at ε, ε/4, ε/16  →  fronts  P_ε, P_{ε/4}, P_{ε/16}
 3  compute I_ε×(P_{ε/4}, P_ε) and I_ε×(P_{ε/16}, P_{ε/4})    [finer covers coarser]
 4  compute I_ε×(P_ε, P_{ε/4}) and I_ε×(P_{ε/4}, P_{ε/16})    [coarser covers finer]
 5  record Λ = peak labels retained per node, at each ε
 6  LENGTH SWEEP — the discriminating part:
 7      repeat steps 2–5 at voyage lengths S = 500, 1000, 2000, 4000 km
 8      on the SAME field and the SAME h, so D = S/h varies by 8×
 9      plot I_ε×(P_ε, P_{ε/4}) against D
```

### 8.6.3 Predictions, with the reasoning

**(i) The covering bound.** Every point of `P_{ε/4}` is a genuinely achievable route, hence
weakly dominated by some true Pareto point `ℓ*`; and by Thm 5.2, `P_ε` covers every `ℓ*`
within `(1+ε)` on objectives `2..k`. Composing,

```
I_ε×( P_ε , P_{ε/4} )  ≤  1 + ε          over objectives 2..k                (8.48)
```

This is a **hard upper bound implied by the theorem**, so exceeding it is a proof of a bug —
either in the bucketing or in the dominance pruning. Observed values should be well below it,
typically `1 + ε/2` or less, because the bound is worst-case over the front.

**(ii) The converse direction is not bounded and must not be asserted.** `P_{ε/4}` is a finer
front; `I_ε×(P_{ε/4}, P_ε)` can legitimately exceed `1 + ε/4` because `P_ε` may contain points
that `P_{ε/4}`'s bucketing discarded as dominated. Report it; do not gate on it. Getting this
backwards produces a suite that fails on correct code.

**(iii) Length invariance — the E7 discriminator.**

```
value bucketing (E7.1):  I_ε×(P_ε, P_{ε/4}) is FLAT in D              ← required
increment bucketing:     I_ε×(P_ε, P_{ε/4}) grows like (1+ε/D')^D     ← the bug   (8.49)
```

Under E7.1 the guarantee has **no path-length dependence** — a bucket index
`⌊log(ℓ_i/C_i^min)/log(1+ε)⌋` is a function of the accumulated value, so the error cannot
compound. Under increment bucketing each of `D` edges may lose a factor `(1+ε')`, and to keep
a uniform `(1+ε)` one must take `ε' = ε/D`, whereupon the label bound becomes
`Λ ≈ (D·log range / ε)^{k−1}` — polynomial of degree `k−1` in path length, exceeding `10¹⁰`
labels per node for `k=3, ε=0.02, D≈180` (ERRATA E7). **A flat curve in step 9 is the pass; a
rising curve is the E7 bug, and its slope identifies it unambiguously.**

This is exactly playbook S4 cause 3 ("short voyages fine, long voyages degrade"), made into a
measurement instead of a hunch.

**(iv) The label bound.** ERRATA E7.2:

```
Λ  ≤  ∏_{i=2}^{k} ( ⌈ log(C_i^max/C_i^min) / log(1+ε) ⌉ + 1 )                (8.50)
```

For `k = 3`, `ε = 0.02`, two decades of range in each bucketed objective:
`log 100 / log 1.02 = 4.605 170 / 0.019 803 = 232.5`, so `⌈232.5⌉ + 1 = 234` per objective and
`Λ ≤ 234² = 54 756 ≈ 5.5 × 10⁴` worst case. ERRATA reports **10–40 observed** after dominance
pruning — three orders of magnitude below the bound, which is expected (the bound assumes
every bucket combination is realised and non-dominated) and is worth publishing as the gap
between the theory and the practice.

**(v) Front shape.** If the front is a thin line rather than a spread, the cause is almost
never the ε machinery — it is that `SFOC` is effectively flat, so fuel is a monotone function
of time and there is nothing to trade (playbook S5). **Guard the ε test with a precondition:**
`fuel_per_mile(q)` sampled at `q = 0.35, 0.55, 0.75, 1.0` must have an interior minimum near
`q ≈ 0.75` (the `sfoc_q_opt` of the vessel model). If it does not, Test 8.6 is measuring
nothing and must report SKIPPED, not PASSED.

### 8.6.4 Pass criteria for Test 8.6

```
P1  I_ε×(P_ε, P_{ε/4}) ≤ 1 + ε on objectives 2..k, at every ε and every S     [(8.48)]
P2  time objective: min-time member of P_ε equals min-time member of P_{ε/4}
    to Class D — time is not bucketed, so refining ε must not change it
P3  LENGTH INVARIANCE: least-squares slope of I_ε×(P_ε,P_{ε/4}) against D is
    statistically indistinguishable from zero; report slope, standard error, R²
P4  Λ ≤ (8.50) at every node, every ε.  Report mean and peak.
P5  precondition (v) holds, else report SKIPPED
P6  co-moving: run the whole protocol on the co-moving field. The reduction does not
    touch the label algebra, so every number must be reproduced within Class D.
```

P3 is the reason this test exists. P1 is a bound the theorem gives for free; P3 is the one
that catches the error the theorem was corrected for.

---

## Test 8.7 — Grid refinement, Richardson extrapolation, and the metrication floor

**What it decides.** Whether the scheme is **consistent** — and it is the single most
important failure to catch, because an inconsistent scheme still produces routes that look
entirely reasonable (playbook S3). **Status: RUN. Measured.** The explanatory constant in
§8.7.3 is **derived here**.

### 8.7.1 Protocol

```
Alg 8.7  REFINEMENT
 1  fix ONE problem with a known or self-consistent reference (G4 uniform flow is ideal:
    its exact answer is (8.15) and is resolution-independent)
 2  solve at a decreasing sequence of h
 3  record e(h) := | T(h) − T_exact | / T_exact      (or the two-frame discrepancy where
                                                      no exact answer exists)
 4  fit log e = log C + p log h by least squares; report p, its standard error, and R²
 5  where three levels share a constant refinement ratio r, form the Richardson estimate
        p_R = log( (e₁ − e₂)/(e₂ − e₃) ) / log r                             (8.51)
 6  publish p, p_R, R², and the raw table. Publish it even when — especially when —
    it does not converge.
```

`p ≈ 1` is healthy for a first-order monotone scheme (Barles & Souganidis 1991 gives
convergence to the viscosity solution but not a rate; the rate is empirical and must be
measured, not assumed). `p ≈ 0` is a **plateau** and means the scheme is inconsistent.

### 8.7.2 The measured result — the reference signature of a metrication floor

From `CORE-THEOREM.md` §4, two-frame discrepancy on the 16-neighbour stencil:

| `h` [km] | 24 | 16 | 12 | 8 | 6 | 4 | 3 |
|---|---|---|---|---|---|---|---|
| discrepancy [%] | **0.36** | **0.15** | **0.79** | **0.92** | **0.17** | **0.98** | **0.58** |

**It oscillates. It does not decrease. Refinement buys nothing.**

**Least-squares fit, computed here from the table above** (`ln e` against `ln h`, all seven
points):

```
mean ln h = 2.113 09 ,   mean ln e = −0.796 39
Σ(δ ln h)(δ ln e) = −1.287 32 ,   Σ(δ ln h)² = 3.369 12 ,   Σ(δ ln e)² = 3.702 62
p   = −1.287 32 / 3.369 12 = −0.382                                          (8.52)
r   = −1.287 32 / sqrt(3.369 12 × 3.702 62) = −0.364    ⟹   R² = 0.133
```

**`p = −0.38` with `R² = 0.13`.** A negative order means the error *grows* as the grid is
refined, and `R² = 0.13` means the power law explains 13 % of the variance — i.e. there is no
power law. This is the signature. Publish it exactly like this.

**Richardson (8.51) on the ratio-2 subsequences of the table:**

| triple | `(e₁−e₂)/(e₂−e₃)` | `p_R` |
|---|---|---|
| `h = 24, 12, 6` | `(0.36−0.79)/(0.79−0.17) = −0.694` | **undefined** — log of a negative |
| `h = 12, 6, 3` | `(0.79−0.17)/(0.17−0.58) = −1.512` | **undefined** — log of a negative |
| `h = 16, 8, 4` | `(0.15−0.92)/(0.92−0.98) = 12.833` | **`log 12.833 / log 2 = 3.68`** |

> **The third row is the trap, and it is the reason this test is written out in full.** An
> implementer who computes Richardson on one triple and happens to pick `(16, 8, 4)` will
> report **`p = 3.68`** and announce near-fourth-order convergence — from a scheme that is not
> converging at all. Richardson extrapolation assumes a single-term asymptotic error
> expansion `e = C h^p + o(h^p)`; when the error is dominated by a **non-vanishing systematic
> bias plus noise**, the estimator is meaningless and it does not announce itself. It returns
> a number.
>
> **Normative:** never report a Richardson order from a single triple. Report it from every
> available triple, report the least-squares fit and its `R²`, and treat sign changes in the
> successive differences as a **hard stop**: they falsify the asymptotic-expansion hypothesis
> on which the extrapolation rests. Roache's (1994) grid-convergence-index discipline says the
> same thing; this table is a worked example of what happens when it is ignored.

### 8.7.3 Why: the fixed-stencil metrication floor, derived

A stencil with finitely many neighbour offsets makes only finitely many leg directions
available. A route whose true optimal heading falls between two available directions must be
realised as a zig-zag, and the zig-zag is longer than the straight line. The bias this creates
is a function of the **angular gap**, not of `h`.

> ### Lemma 8.5 (angular-quantisation penalty)
> Let a stencil offer leg directions with an angular gap `Δ` between two consecutive
> directions, and let the desired direction lie at angle `s ∈ [0, Δ]` from the lower one. In
> an isotropic medium, the minimum path length needed to achieve net displacement `1` in the
> desired direction, using only those two directions, is
> ```
> 1/E(s) ,     E(s) = sin Δ / ( sin s + sin(Δ − s) )                          (8.53)
> ```
> and the mean relative time penalty over `s` uniform on `[0, Δ]` is
> ```
> P(Δ) = (2/Δ)·tan(Δ/2) − 1  =  Δ²/12 + O(Δ⁴)                                 (8.54)
> ```
>
> **Proof.** Use fractions `f₁, f₂ ≥ 0`, `f₁ + f₂ = 1`, of the total path length on the two
> directions, which lie at angles `−s` and `+(Δ−s)` from the desired direction. Net transverse
> displacement must vanish: `f₁ sin s = f₂ sin(Δ−s)`. Net displacement along the desired
> direction per unit path length is `E = f₁ cos s + f₂ cos(Δ−s)`. Solving the transverse
> condition, `f₁ = sin(Δ−s)/(sin s + sin(Δ−s))`, `f₂ = sin s/(sin s + sin(Δ−s))`, so
> ```
> E = [ sin(Δ−s)cos s + sin s cos(Δ−s) ] / ( sin s + sin(Δ−s) )
>   = sin( (Δ−s) + s ) / ( sin s + sin(Δ−s) )  =  sin Δ / ( sin s + sin(Δ−s) )
> ```
> using the sine addition formula. That is (8.53). In an isotropic medium time is proportional
> to path length, so the relative penalty is `1/E − 1`, and
> ```
> (1/Δ)∫₀^Δ (1/E(s)) ds = (1/(Δ sin Δ)) ∫₀^Δ ( sin s + sin(Δ−s) ) ds
>                        = (1/(Δ sin Δ))·2(1 − cos Δ)
>                        = (2/Δ)·tan(Δ/2)
> ```
> using `(1−cos Δ)/sin Δ = tan(Δ/2)`. Subtracting 1 gives (8.54); the Taylor expansion
> `tan(u) = u + u³/3 + …` at `u = Δ/2` gives `(2/Δ)(Δ/2 + Δ³/24) − 1 = Δ²/12 + O(Δ⁴)`. ∎
>
> **Note the crucial feature: `Δ` does not depend on `h`.** Refining the grid shrinks the legs
> but not the set of directions, so `P(Δ)` is a **floor**, not an error term.

**Applied to the stencils in use.** For the 16-neighbour stencil of `comoving.stationary_sweep`
— offsets `(±1,0),(0,±1),(±1,±1),(±2,±1),(±1,±2)` — the available directions in the first
quadrant are `0°, arctan(1/2) = 26.565 051°, 45°, arctan 2 = 63.434 949°, 90°`, giving gaps
`26.565 051°, 18.434 949°, 18.434 949°, 26.565 051°` (summing to 90° ✓), i.e. **8 gaps of
`Δ_a = 0.463 647 61 rad` and 8 of `Δ_b = 0.321 750 55 rad`** around the circle, with
`Δ_a + Δ_b = π/4` exactly. Averaging (8.54) weighted by gap length:

```
P̄ = [ 2 tan(Δ_a/2) + 2 tan(Δ_b/2) − Δ_a − Δ_b ] / ( Δ_a + Δ_b )
   = [ 2(0.236 067 7) + 2(0.162 277 5) − 0.785 398 2 ] / 0.785 398 2
   = ( 0.472 135 4 + 0.324 555 0 − 0.785 398 2 ) / 0.785 398 2
   = 0.011 292 3 / 0.785 398 2 =  0.014 378                                  (8.55)
```

| stencil | max gap `Δ` | **mean penalty `P̄`** | worst-case penalty `1/cos(Δ/2) − 1` |
|---|---|---|---|
| 4-neighbour | 90° | **27.32 %** | 41.42 % (`√2 − 1`) |
| 8-neighbour | 45° | **5.48 %** | 8.24 % |
| **16-neighbour (as built)** | 26.565° | **1.44 %** | **2.75 %** |
| continuum semi-Lagrangian (`ζ` search) | 0 | **0** | 0 |

The 4-neighbour worst case `√2 − 1 = 41.42 %` is the classical Manhattan-vs-Euclidean figure,
which (8.54) and (8.53) reproduce exactly — an independent check on the derivation.

**This closes the loop with the measurement.** Each frame's solution carries a systematic bias
of order **1.44 %**; the *difference* between two independently-quantised frames is
`0.15–0.98 %`, smaller than either bias because the two biases partially cancel. Both numbers
are consistent with a single mechanism, and both are `h`-independent. That is the whole
explanation of table §8.7.2, and it was derived, not fitted.

### 8.7.4 What this licenses and what it forbids

- **Licensed:** publishing `~1 %` as the Class D floor of the reference implementation, and
  reporting cross-frame agreements at `0.860 %` (§8.11) as *inside the floor* rather than as
  independent confirmation of anything.
- **Forbidden:** claiming any convergence order from this stencil; using refinement to argue
  for correctness; comparing two solves at the `< 1 %` level and drawing a conclusion.
- **Implied roadmap:** the fix is not a finer grid, it is the **continuum semi-Lagrangian
  update** — minimise over a continuous parameter `ζ` along accepted-front edges rather than
  over a fixed neighbour set (spec §4, Sethian & Vladimirsky 2003), with the `ℓ_min = h/√2`
  exclusion of ERRATA E3.1. That takes `Δ → 0` and removes the floor. It is an accuracy
  improvement **orthogonal to Theorem C.1**; the reduction is exact at every resolution and
  neither causes nor cures this floor.

### 8.7.5 Pass criteria for Test 8.7

```
P1  run the sweep at ≥ 5 values of h and PUBLISH the table, whatever it shows
P2  report p (least squares), its standard error, and R²
P3  report p_R from EVERY constant-ratio triple, and flag sign changes in the
    successive differences as falsifying the extrapolation hypothesis
P4  on the G4 uniform-flow problem, where the exact answer (8.15) is known and
    resolution-independent, e(h) must DECREASE monotonically for a continuum-update
    implementation; for a fixed-stencil implementation it will plateau near P̄ of (8.55),
    and that plateau value must be reported as the Class D floor
P5  the measured plateau must agree with (8.55) to within a factor of 2. Agreement to
    better than that would be over-claiming for a one-parameter model; disagreement by
    more than that means the mechanism is NOT angular quantisation and must be
    diagnosed separately (playbook S3 causes 2 and 3)
P6  disable the wide stencil but KEEP the ζ search. If the plateau persists, the ζ
    minimisation is broken (S3 cause 1). If the error becomes resolution-dependent
    again, the stencil radius was the limit (S3 cause 2). This is the discriminating
    bisection and it must be part of the suite, not a debugging afterthought.
```

---

## Test 8.8 — Certificate soundness (Cor 4.12)

**What it decides.** Whether the a posteriori optimality certificate is **sound** — i.e.
whether the reported gap really bounds the true gap. After ERRATA E6 demoted the a-priori
realisability bound to vacuity (`exp(L_v T) ≈ 1.6×10⁵` over a 14-day voyage), the certificate
is the **primary** optimality guarantee of the whole method, so its soundness is not a bonus
test. **Status: protocol only. Not yet run as a formal suite.**

### 8.8.1 The claim under test

The certificate computes an optimistic lower bound `T_low` from a coarse solve on cells
**dilated by the coarse spacing `H`** (design decision D5), and reports

```
gap  :=  ( J − T_low ) / T_low                                               (8.56)
```

Soundness requires `T_low ≤ T*` for the true optimum `T*`, so that `gap` over-states rather
than under-states the distance to optimality.

### 8.8.2 Protocol

```
 1  run on the problems where T* is KNOWN exactly: 8.2 (both directions and the crab case)
    and 8.3 (subject to Conj 8.2)
 2  assert  T_low ≤ T* ≤ J  at every one
 3  assert  gap ≥ (J − T*)/T*  — the reported gap dominates the true gap
 4  ADMISSIBILITY STRESS: construct a case where a fine path clips a coarse-cell corner.
    Place a narrow favourable jet along a coarse-cell diagonal, width < H. Without the
    dilation of D5, the coarse edge cost misses the jet and T_low exceeds T*.
 5  run with the heuristic DISABLED (pure Dijkstra order) and compare answers. If the
    answer IMPROVES with the heuristic off, the heuristic is inadmissible (playbook S4
    cause 2), and the certificate built on it is unsound.
 6  report nodes expanded with and without the heuristic — this is what justifies its cost
```

Step 4 is the test that D5 exists for. The CONTRACT records that the naive "min over the bare
cell" construction is inadmissible and that the earlier draft got it wrong; step 4 is the
measurement that would have caught it.

### 8.8.3 Pass criteria

```
P1  T_low ≤ T* on every problem with a known T*, with zero exceptions.
    A single violation is a HARD FAIL: an inadmissible heuristic returns suboptimal
    answers silently, and the certificate then certifies a falsehood.
P2  gap ≥ true gap on every such problem
P3  step 4 (dilated) passes; step 4 with the dilation REMOVED must FAIL — an anti-test,
    for the same reason as 8.5 P7
P4  step 5: answers identical with the heuristic on and off, to Class D
P5  report nodes-expanded ratio and the median gap over a batch of ≥ 20 problems
```

---

## Test 8.9 — Solver invariants and coverage

**What it decides.** Whether the data structures obey the invariants their correctness proofs
assume. These are cheap, they run on every problem, and each one corresponds to a specific
corrected statement in ERRATA. **Status: protocol only. Not yet run as a formal suite.**

### 8.9.1 The invariant list

| # | Invariant | Source | Assertion |
|---|---|---|---|
| I1 | bucket-queue monotonicity violations `= 0` | Prop 4.9, Dial (1969), Martins (1984) | counter is exactly 0; a non-zero count means a key was inserted below the current minimum and the ring wrapped (playbook S1 cause 3) |
| I2 | `Δ_min = c_geo·h·F_min` with `c_geo = 1/√2 = 0.707 106 781…` | ERRATA E3.1 | the queue's configured width equals this, computed not hard-coded |
| I3 | every front point `ξ` with `\|x − ξ\| < ℓ_min = h/√2` is **skipped** | ERRATA E3 | count the exclusions; a count of 0 across a whole run means the exclusion is not wired in, and (E3.1) is then an assumption rather than a theorem |
| I4 | heap fallback fires **iff** `Υ_loc > Υ_heap = 12` | ERRATA E2 | run golden row T6 (`Υ_loc = 39`) and assert the heap path; run 8.4 (`Υ_loc = 17/7 = 2.43`) and assert the bucket path |
| I5 | `F > 0` and `isfinite(F)` at **every** metric evaluation | playbook S1 | record `(lat, lon, t, u)` of the first violation |
| I6 | `ζ` distribution is not endpoint-pinned | playbook S3 | histogram `ζ`; bimodality at `{0,1}` means the inner minimiser is broken |
| I7 | stencil-radius histogram is not saturated at the cap | CONTRACT §4 | saturation means `Υ` exceeds what the stencil can represent |
| I8 | `sample_env` is deterministic and side-effect free | `types.EnvField` | call twice at 10⁴ random `(x,t)`; require bitwise equality. The causality proof assumes it |
| I9 | `T7`/`T8` branches executed | §8.1 | branch coverage assertion |
| I10 | co-moving: `L_t ≡ 0` **identically** | Thm C.1(b) | measured `0.0` exactly in regime A (§8.10). Not "small" — zero |
| I11 | co-moving: `ground_position` and `comoving_position` compose to the identity | Eq (C.5) | round-trip to `1e-9` rad ≈ 6 mm, matching handbook G1's round-trip invariant |
| I12 | wait relaxation (E5.1) is evaluated at the **same `ℓ`** the update uses, and horizon truncations are counted | ERRATA E5 | report the count of horizon-truncated evaluations; a count of 0 on a voyage longer than `H_fc` means the truncation is not implemented |

I11 deserves its own line because sign confusion between `x = y + wt` and `y = x − wt` puts
the landfall `2|w|t*` away — twice the dilation distance, which is the distinctive signature
recorded in playbook S8b cause 3.

### 8.9.2 Geodesy (handbook G1) — the prerequisite

Nothing above is meaningful if the sphere is wrong. Assert, with `R_E = 6 371 000.0 m` exactly:

| From | To | Distance | Initial bearing |
|---|---|---|---|
| 0.00 N, 0.00 E | 0.00 N, 90.00 E | **10 007.543 398 010 3 km** | **90.000 000°** |
| 18.95 N, 72.95 E (JNPT) | 29.92 N, 32.55 E (Suez) | **4 243.611 km** | **294.619°** |
| 18.95 N, 72.95 E | 25.01 N, 55.06 E (Jebel Ali) | **1 961.706 km** | **293.284°** |
| 13.09 N, 80.29 E (Chennai) | 1.26 N, 103.85 E (Singapore) | **2 908.549 km** | **114.975°** |
| 9.96 N, 76.24 E (Kochi) | 12.79 N, 45.02 E (Aden) | **3 415.766 km** | **278.307°** |

The first row must equal `2πR_E/4 = 10 007.543 398 010 286 km` **exactly**; if it does not,
the radius constant or the `asin` guard is wrong, and that one row catches most geodesy errors
on its own. Round-trip invariant at all five pairs:
`destination(A, initial_bearing(A,B), haversine(A,B)) == B` to `1e-9 rad ≈ 6 mm`.

**Implementation trap with teeth** (from the reference build): a grid whose `latlon(i, j)`
wraps a negative `j` like a list index turns every westward stencil offset into a wrap-around
leg. Measured: a 57.9 km leg reported as **4 020 km**, with a bearing **142° wrong**. The fix
is to compute the per-row geometry cache from a reference column at least `max|dj|` from the
edge. Assert: every leg length in the geometry cache is within a factor of 2 of `h·|offset|`.

### 8.9.3 Seakeeping ban coverage

The bans are what remove regions from the indicatrix, and an unexercised ban is a ban that
does not exist. Assert that each of `S1..S7` is *reached* by at least one test case, with the
criteria drawn from their sources: parametric-roll and synchronous-roll resonance and
surf-riding/broaching per **IMO MSC.1/Circ.1228**; response and short-term extreme statistics
per **Ochi (1964)**; wind resistance and windage per **Fujiwara (2006)**.

The convention test from playbook S2, which must be in the suite: set `H_s = 6 m` with `μ_w`
pointing due **north** (waves travelling *towards* north). A ship steaming due north is then
in **following** seas and must lose the **least** speed; due south is head seas and must lose
the **most**. Reversed means the meteorological "from" convention has leaked in.

### 8.9.4 Pass criteria

```
P1  I1..I12 all hold on every problem in the suite
P2  I3, I4, I9, I12 each have a NON-ZERO exercise count somewhere in the suite —
    an invariant never exercised is not validated
P3  every G1 row to the printed precision; row 1 to 1e-12 relative
P4  round-trip invariant ≤ 1e-9 rad at all five pairs
P5  S1..S7 each reached; the wave-convention test passes
```

---

## Test 8.10 — The causality-constant measurement

**What it decides.** Contribution 3: whether the reduction works as a **preconditioner** where
assumption A1 fails — i.e. whether de-advecting a field with real evolution in it takes the
causality condition (E4.1) from *violated* to *satisfied*. **Status: RUN. Measured**,
`CORE-THEOREM.md` §7.

**Prior art.** The causality condition itself is **Vladimirsky (2006)**; ERRATA E10 records
this as a citation kill against the first draft's framing. What is measured here is not the
condition but the *effect of the frame change on it*, which is new.

### 8.10.1 The quantity

ERRATA E4 corrected the length scale: the ordered-upwind update traverses a segment of length
up to `r(x) ≤ Υ_loc·h`, not `h`, so

```
Causality holds at (x,t)   ⟸   r(x) · L_t(x,t)  ≤  1                         (E4.1)
L_t(x,t) := max_{|u|=1} |∂F(x,t,u)/∂t|                                        (8.57)
```

**The runtime diagnostic must report `max_x r(x)·L_t`, not `max_x h·L_t`.** In the isotropic
limit `r = h` the old condition is recovered, which is exactly why the error was invisible in
testing on weak fields — and why an implementation built to `h·L_t` reports a green certificate
on forecasts where the sweep is *not* licensed.

Splitting (C.8), `E(x,t) = E₀(x − wt) + R(x,t)`: under A1 exactly, `R ≡ 0` and the co-moving
`L_t` is identically zero. Otherwise the co-moving causality constant is driven by
`L_t^R := Lip_t(R)`, and the reduction's job is to make that small.

### 8.10.2 Measurement protocol (as run)

```
L_t evaluated as a centred difference over 24 headings, 3-day horizon, 10 km grid,
reported as max / 99th percentile / median over the domain, in both frames,
with r = 56 km  (≈ 2h·Υ for the field's anisotropy).
Three regimes, from A1-exact to A1-badly-violated.
```

### 8.10.3 The measured table

| Regime | frame | max | p99 | median | `r·L_t` at `r = 56 km` |
|---|---|---|---|---|---|
| **A** pure translation (A1 exact) | ground | 6.33e-07 | 6.33e-07 | 5.64e-07 | 0.035 OK |
| | co-moving | **0.0** | **0.0** | **0.0** | **0.000** |
| **B** + intensification 35 %/day | ground | 2.34e-05 | 2.34e-05 | 3.75e-07 | **1.309 VIOLATED** |
| | co-moving | 4.86e-06 | 4.86e-06 | 1.69e-06 | **0.272 OK** |
| **C** + second system at a different `w` | ground | 2.34e-05 | 2.33e-05 | 3.52e-07 | **1.307 VIOLATED** |
| | co-moving | 5.07e-06 | 4.67e-06 | 1.63e-06 | **0.261 OK** |

**Ratios, computed here from the table** so that no reader has to trust a summary:

```
regime B, max : 2.34e-05 / 4.86e-06 = 4.815 ×      p99: 2.34e-05 / 4.86e-06 = 4.815 ×
regime C, max : 2.34e-05 / 5.07e-06 = 4.615 ×      p99: 2.33e-05 / 4.67e-06 = 4.989 ×
⟹ the "4.6–5.0×" improvement quoted in CORE-THEOREM spans max-C (4.62) to p99-C (4.99)  (8.58)
```

**What this establishes.**

- **Regime A confirms the mechanism exactly.** `L_t` in the co-moving frame is *identically
  zero, to the last bit* — not small, zero. Theorem C.1(b) is not approximately true.
- **Regimes B and C are the result that matters practically.** The reduction takes a field on
  which the causality condition is **violated** (`r·L_t = 1.31 > 1`, so a single-pass solve is
  *not licensed*) and makes it **comfortably satisfied** (`0.26–0.27`). That is the difference
  between an answer with a machine-checkable licence and an answer without one.

**One internal inconsistency in the source table, recorded rather than smoothed over.** The
`r·L_t` column is computed from the **max** column in every row except regime C co-moving,
where `56 000 × 4.67e-06 = 0.2615` shows it was computed from the **p99**. Using the max
consistently gives `56 000 × 5.07e-06 = 0.2839`. Both are far below 1, so no conclusion
changes; but the column should be regenerated from a single statistic before publication, and
the statistic named. (Cross-checks for the other rows: `56 000 × 6.33e-07 = 0.0354` ✓ `0.035`;
`56 000 × 2.34e-05 = 1.310` ✓ `1.309`; `56 000 × 4.86e-06 = 0.2722` ✓ `0.272`.)

### 8.10.4 The three caveats, in full, because each costs the claim something

**Caveat 1 — the median gets *worse*, by ~4.5×.**

```
regime B median: 3.75e-07 (ground) → 1.69e-06 (co-moving) = 4.507 × WORSE
regime C median: 3.52e-07 (ground) → 1.63e-06 (co-moving) = 4.631 × WORSE       (8.59)
```

In the ground frame most cells are far from any weather system and see almost no change with
time; in the co-moving frame the sampling point *slides through space*, so quiet cells now see
the field vary as the frame carries them across spatial structure. **De-advection trades a
large improvement in the worst cells for a modest degradation in already-benign ones.**
Because (E4.1) is a **worst-case** condition — one violated cell voids the licence for the
whole sweep — this is the right trade. But it is a trade, not a free win, and
**anyone reporting only the max is overselling it.** Report max, p99 **and** median, always.

**Caveat 2 — regime A's test field was degenerate in `x`.** The field was an `x`-invariant
jet, so only the `y`-component of `w` was identifiable. The optimiser recovered
`w_y = +0.500` exactly against a true `+0.5`, and left `w_x` unconstrained. **The exactness of
the reduction is established by regime A; the *identifiability* of `w` is not**, by that test.
A non-degenerate identifiability test — a field with structure in both coordinates — is
outstanding.

**Caveat 3 — in B and C the optimised `w` is nowhere near the true advection velocity.**
`(−0.56, −1.38)` against a true `(+2.0, +0.5)`. Once A1 is violated, *minimising the residual
causality constant* and *estimating the meteorological advection* are **different problems**,
and it is the former that the algorithm needs. Say so; **do not dress the optimised `w` up as
a physical storm-track estimate.** It is a numerical preconditioner parameter.

### 8.10.5 Choosing `w`: the failed method and its replacement

The natural choice — **phase correlation** between consecutive forecast frames — was tried
first and **failed badly**: against a true dominant `w = (2.0, 0.5)` it returned
`(−0.74, 0.00)`. It locks onto whichever feature carries the most gradient energy, which need
not be the one governing the causality constant. This negative result is reported because it
is the method a reader would otherwise reach for.

It is replaced by choosing `w` to **directly minimise the co-moving causality constant**:

```
w* = argmin_w   P₉₉ over the domain of   max_u | ∂F_w/∂t |                    (C.10)
```

by coarse-to-fine search over a 2-D grid (three rounds of `9×9` is ample). The 99th percentile
rather than the max keeps a single pathological cell from steering the choice. Cost, measured
on the §8.11 problem: **+0.05 s** against a 3.38 s solve.

**Validation of the `w`-chooser itself** (protocol; the identifiability half is outstanding
per caveat 2):

```
W1  on a synthetic field satisfying A1 exactly and with structure in BOTH coordinates,
    the recovered w must equal the true w to within one search-grid cell, and the
    co-moving L_t must be 0.0 exactly
W2  the objective (C.10) must be evaluated on points fixed IN THE w-FRAME, not the
    ground frame — otherwise the search measures the wrong quantity
W3  monotone-improvement assertion: the returned L_t^{co-moving} ≤ L_t^{ground}.
    This is guaranteed by construction only because w = 0 is inside the search domain
    and the search is a minimisation seeded at w = 0. Assert it anyway; a violation
    means the search returned a point it did not actually evaluate.
W4  report BOTH the base (w = 0) and the optimised value, as choose_advection does
```

W3 is worth stating explicitly: the improvement claim is not an empirical hope, it is a
consequence of `w = 0` being feasible for (C.10). The *size* of the improvement is empirical;
its **sign** is guaranteed.

### 8.10.6 Pass criteria for Test 8.10

```
P1  regime A: co-moving L_t == 0.0 EXACTLY (bitwise). Not "< 1e-12" — zero.
P2  the diagnostic reports r(x)·L_t with the ACTUAL stencil radius, not h·L_t   [E4.1]
P3  max, p99 AND median are all reported, in both frames
P4  W1..W4 for the w-chooser
P5  ANTI-TEST: assert the ground-frame r·L_t on regimes B and C EXCEEDS 1. If it does
    not, the test field is too benign and the experiment demonstrates nothing.
P6  the reported r·L_t column is generated from ONE named statistic (see §8.10.3)
```

P5 is the counterpart of 8.5 P7: a preconditioner test on a field that never needed
preconditioning measures nothing.

---

## Test 8.11 — End-to-end, and the two failures that are silent

**What it decides.** Whether the whole pipeline — advection choice, co-moving metric,
stationary solve, interception, route recovery — produces the same voyage as a conventional
ground-frame time-dependent solve, to within the published Class D floor. And whether the two
implementation requirements that **fail silently** are detected rather than survived.
**Status: RUN. Measured**, `CORE-THEOREM.md` §8.1–8.2.

### 8.11.1 The voyage, as run

```
from      8.0 N, 77.0 E   (southern tip of India)
to       12.6 N, 43.5 E   (Gulf of Aden approaches)
great circle  3 698 km
V_s      = 7.2 m/s
weather  = cyclone translating at w_true = (3.0, 1.0) m/s
grid     = 0.25°  (h = 27.80 km at the equator; diagonal 39.31 km)
nodes    = 29 529
```

(`h`: `0.25° × π/180 × 6 371 000 = 0.004 363 323 1 × 6 371 000 = 27 799.9 m`; diagonal
`h√2 = 39 314 m`.)

### 8.11.2 Measured results

| | arrival | wall clock | notes |
|---|---|---|---|
| Ground-frame time-dependent Dijkstra | **141.210 7 h** | 2.14 s | conventional approach |
| **Co-moving reduction** | **139.996 3 h** | 3.38 s (+0.05 s to choose `w`) | landfall miss **11.2 km** |

**Agreement, computed here:**

```
Δ = 141.210 7 − 139.996 3 = 1.214 4 h
Δ / 141.210 7 = 0.008 600  =  0.860 %      (relative to the ground-frame value)
Δ / 139.996 3 = 0.008 674  =  0.867 %      (relative to the co-moving value)          (8.60)
```

**Report the denominator.** `0.860 %` is the ground-frame denominator; the difference between
the two is itself `0.007 %` and immaterial here, but a paper that does not say which it used
invites the question.

**Interpretation, and this is the part it is easy to overstate.** `0.860 %` sits **inside the
`~1 %` fixed-stencil metrication floor** derived and measured in §8.7 (mean predicted penalty
`1.44 %` per frame; measured two-frame discrepancies `0.15–0.98 %`). So this agreement is the
**expected** outcome and is **not** independent confirmation of Theorem C.1 — §8.5 is what
confirms the theorem. What 8.11 confirms is that the two *pipelines* are wired together
correctly end to end, which is a different and also necessary thing.

One asymmetry is informative: the co-moving answer is the **slightly faster** of the two,
consistently with it carrying **no temporal sampling error** (§8.5.6; the ground solve's
`V_req = 7.006 721 m/s` exceeds the ship's actual `7.0 m/s` capability, so its route is
marginally infeasible and its time correspondingly optimistic — yet it still comes out
*slower*). The sign of the difference is therefore a weak but real corroboration of
contribution 2.

**Landfall miss.** `11.2 km` against a grid diagonal of `39.31 km` — `0.285` of a diagonal,
comfortably under the half-diagonal criterion. This is the *discretisation* miss, and it is
what R1 below reduces the `104.5 km` miss to.

**Causality constant on this field** (Test 8.10 applied to the operational case):

```
L_t         : 3.22e-07  →  1.24e-07     (2.60 × reduction)
r·L_t at r = 2h = 55 km : 0.0177 → 0.0068                                     (8.61)
```

Both frames are licensed here — this is a well-behaved field — so 8.11 does not exercise the
preconditioner claim; §8.10 regimes B and C do.

### 8.11.3 R1 — the co-moving grid must be dilated. **Regression test.**

> **The requirement.** The solve lives in `y = x − w t`, so reaching ground point `x_B` at
> time `t` requires the node `y = x_B − w t` to be **inside the grid**. Over a voyage of
> duration `t_max` the co-moving domain is displaced from the ground domain by `w·t_max`,
> opposite to `w`, component by component:
> ```
> dilation_east  = |w_e| · t_max ,     dilation_north = |w_n| · t_max         (8.62)
> ```

**Undersized, this fails silently.** The sweep converges. The route looks plausible. The
landfall is simply wrong. **Measured** on a 140 h voyage with `w = (1,1) m/s`: the required
node lay **4.5° west of the grid edge**, giving a **104.5 km miss that a full-grid scan could
not reduce**, because no node in the domain mapped anywhere near the target. Extending the
domain by `|w|·t_max ≈ 500 km` per component brought the miss to **11.2 km**.

(Consistency check of those numbers, computed here: `t_max = 140 h = 504 000 s`;
`|w_e|·t_max = 1.0 × 504 000 = 504 km`; `504 km / 111.32 km per degree = 4.53°` ✓ matching the
observed 4.5° shortfall. For the §8.11.1 voyage with `w = (3.0, 1.0)` and `t_max ≈ 504 000 s`
the requirement is **1 512 km east and 504 km north** — 13.6° and 4.5°.)

**The regression test, and it must have three parts:**

```
R1a  PRE-FLIGHT ASSERTION.  Before the sweep, compute (8.62) from w and an upper bound
     on t_max (e.g. great-circle distance / σ_min^w) and assert the domain margin
     exceeds it in each component. FAIL LOUDLY if not — refuse to solve.
R1b  POST-HOC BOUNDARY DETECTOR, which needs no advance estimate of t_max.  After the
     sweep, find the node minimising ‖(y + w·T[y]) − x_B‖.  IF THAT NODE LIES ON THE
     DOMAIN BOUNDARY, the domain was too small: the true minimiser is outside.  This
     detector is always available, costs O(1) after the scan of §8.11.4, and catches the
     case where t_max was underestimated.
R1c  NEGATIVE CONTROL.  Deliberately shrink the domain by 5° on the upwind side and
     assert the implementation DETECTS it — via R1a or R1b — rather than returning a
     converged, plausible, wrong route.  A suite without R1c does not test R1 at all;
     it tests that the correct configuration works.
```

*Discriminating test between "domain too small" and "goal node chosen badly"* (playbook S8b):
scan **every** node for `min ‖(y + w·T[y]) − x_B‖`. If the minimum over the **whole grid** is
large, the domain is too small (R1). If the whole-grid minimum is small but the *selected*
node is worse, it is R2.

### 8.11.4 R2 — do not select the goal node by the interception root find. **Regression test.**

> **The requirement.** Sampling `T` at the nearest node makes
> `g(t) = T_w(x_B − w t) − t` a **step function**, so a bisection converges to a
> discontinuity rather than a root, and `T` at the returned node can be far from `t*`.
> Because the ground position is `y + w·T[y]`, that timing error is **amplified by `|w|`**:
> with `|w| ≈ 3 m/s` and a half-cell timing error of `~2 000 s`, the landfall moves
> `~6 km per cell` of snapping error.

**The fix, which is Eq (C.4) evaluated exactly on the discretisation.** Every node carries its
own arrival time, hence its own ground landfall `y + w·T[y]`; take the node minimising
`‖(y + w·T[y]) − x_B‖`. No interpolation, no root find, `O(N)` with one haversine per node.
The root find remains useful for **reporting** `t*` and would be the right method in a
continuum implementation — but it must not choose the node.

**Measured:** 104.5 km miss under the root-find selector, **unchanged by widening the
neighbourhood search**, because the offset is systematic rather than local. That
insensitivity-to-neighbourhood-width is the diagnostic signature of R2 as opposed to R1.

```
R2a  ASSERT the returned goal node equals argmin over ALL nodes of the ground miss.
R2b  STEP-FUNCTION DETECTOR.  Sample g(t) at 10 000 points across [0, t_max] and count
     DISTINCT values.  For nearest-node sampling the count is O(number of nodes crossed),
     far below 10 000.  Assert the implementation does NOT bisect on this function.
R2c  NEGATIVE CONTROL.  Run both selectors on the §8.11.1 voyage and report both misses.
     The root-find selector must be materially worse; if it is not, the case is too
     benign (small |w|) to exercise R2 and a larger |w| is required.
R2d  NEIGHBOURHOOD-WIDTH SWEEP.  Widen the neighbourhood search radius 1, 2, 4, 8, 16.
     Under R2 the miss is FLAT in the radius.  A flat curve at a large miss is the
     signature; a decreasing curve means the cause is something else.
```

### 8.11.5 Pass criteria for Test 8.11

```
P1  |T_ground − T_comoving| / T_ground ≤ the PUBLISHED Class D floor of §8.7 for this
    stencil (currently ~1 %).  State the floor and its provenance in the same breath;
    a bare "0.86 % agreement" is not a claim, it is a number.
P2  landfall miss ≤ ½ grid diagonal
P3  R1a fires on an undersized domain; R1b fires when the goal node is on the boundary;
    R1c (negative control) is present and passes
P4  R2a holds; R2b, R2c, R2d present and pass
P5  co-moving wall clock within 2× of the ground solve (measured: 3.38 s vs 2.14 s, a
    1.58× ratio — the reduction is not sold on speed and must not be)
P6  the run log reports: chosen w, base and optimised L_t, r·L_t in both frames,
    per-cell (C.7) violations, dilation required vs dilation provided, goal-node miss,
    and the certificate gap.  All of them, every run.
```

P5 states an uncomfortable truth plainly: on this problem the co-moving solve is **slower in
wall clock** than the ground solve (3.38 s vs 2.14 s), because the dilated domain has more
nodes. The reduction's case rests on *exactness*, *licence* and *accuracy* (contributions
1, 2, 3), not on speed, and the validation suite should not be arranged to imply otherwise.

---

## Test 8.12 — Hindcast validation against AIS

**STATUS: NOT YET RUN.** This section specifies a study that has not been carried out. Every
statement below is protocol or a known failure mode; **no result of any kind is reported
here**, and none should be inferred.

**What it would decide.** Whether any of the preceding correctness translates into an
operational benefit against what ships actually did. It is the only test in this file that
can, and it is also the one most easily made to say whatever the author wants.

### 8.12.1 Protocol

```
 1  PRE-REGISTER, before touching the data: the vessel class, the route pairs, the
    season, the sample size, the exclusion criteria, the primary statistic, and the
    decision threshold.  Deposit it (timestamped) and publish it with the result,
    including if the result is negative.
 2  SAMPLE.  N voyages of one vessel class on a fixed set of origin–destination pairs
    over one season, drawn WITHOUT looking at their outcomes.
 3  ENVIRONMENT — the load-bearing step.  For each voyage, assemble the forecast that
    was AVAILABLE AT THE ACTUAL DEPARTURE TIME (e.g. the operational forecast cycle
    preceding departure), NOT the reanalysis.  Reanalysis is the future; using it hands
    KAIROS information the master did not have and inflates every result.
 4  VESSEL CALIBRATION.  The true through-water capability (fouling, trim, engine
    derate) is unknown.  Fit V_s from calm-water segments of a HELD-OUT subset of
    voyages, never from the voyages being scored.
 5  SOLVE from the actual departure position and time to the actual arrival port, under
    the actual reported draught, with the seakeeping bans enabled.
 6  SCORE, per voyage:  ΔT := T_AIS − T_KAIROS  (positive = KAIROS faster), and a fuel
    proxy from the vessel model integrated along each track under the same environment.
 7  TEST.  Primary: one-sided WILCOXON SIGNED-RANK test on ΔT (Wilcoxon 1945) — paired,
    distribution-free, appropriate for a small sample with unknown, likely skewed
    differences.  Report the HODGES–LEHMANN (1963) median difference with a
    distribution-free confidence interval.  Secondary and more robust: the SIGN TEST on
    the fraction of voyages where KAIROS is faster.
 8  REPORT per route pair as well as pooled, and correct for multiple comparisons
    across route pairs (Holm).  Publish the raw per-voyage table.
```

**Power.** For the sign test at `α = 0.05` one-sided to detect a 70/30 split with 80 % power,
the normal approximation gives

```
n ≥ [ z_α·sqrt(0.25) + z_β·sqrt(p(1−p)) ]² / (p − 0.5)²
  = [ 1.645×0.5 + 0.8416×0.4583 ]² / 0.04
  = (0.8225 + 0.3857)² / 0.04 = 1.4597/0.04 = 36.5   ⟹  n ≈ 37 voyages       (8.63)
```

> **Flagged as a derived estimate**, computed here under the normal approximation to the
> binomial. A 60/40 effect needs roughly four times as many (`n ≈ 150`), which is the number
> that should actually be budgeted, because 70/30 is an optimistic effect size for a
> comparison against professionally-planned voyages.

### 8.12.2 Failure modes — why such a study is easy to get wrong

**F1 — Selection bias / survivorship.** AIS contains the voyages that *completed*. Voyages
diverted, abandoned, or ending in a port of refuge are precisely the ones where weather
mattered most, and they are systematically under-represented. This biases *against* finding a
safety benefit and *for* finding a time benefit. Mitigation: define the sample on *departures*
from a port-call database, not on *completed tracks*, and report the attrition.

**F2 — The real ship had different constraints.** A laycan window, a berth slot, a pilot
booking, a charter-party speed clause, bunker economics, ECA-zone boundaries, and the
scheduled convoy timings of the Gulf of Aden IRTC. Arriving early may be worth nothing or may
be penalised by demurrage-side incentives to arrive *late*. **A minimum-time route compared
against a schedule-constrained voyage measures the difference in objectives, not the
difference in algorithms.** Mitigation: score against the *same* objective the ship plausibly
had — usually "arrive by time `X` at least fuel" — which is a Pareto-front query (§5), not a
min-time query. This is the single largest threat to validity.

**F3 — The real ship may already have used a weather-routing service.** StormGeo, DTN and WNI
route a large fraction of commercial tonnage. If so, the baseline is not "unrouted", the
comparison is KAIROS against a mature commercial product, and reporting it as a gain over
"conventional practice" is a misdescription. Mitigation: the sample cannot be cleaned of this
without operator disclosure, so **state it as an uncontrolled confounder** and report the
result as a comparison against *observed practice*, whatever that practice was.

**F4 — Forecast leakage.** Step 3. This is the most common way such studies overstate, and it
is invisible in the output. Mitigation: an explicit forecast-vintage field on every
environment sample, asserted at solve time to be `≤ departure time`.

**F5 — Position and vessel-state provenance.** AIS has gaps and, in some regions,
deliberate spoofing; draught is self-reported and often stale; the true speed–power curve is
unknown and drifts with hull fouling. Fitting `V_s` from the track (step 4) risks
**circularity** — a model calibrated on the same voyages it is scored against will match them.
Mitigation: strict held-out calibration, and report the calibration residual.

**F6 — Multiple comparisons and the garden of forking paths.** Route pairs, seasons, vessel
classes, objectives, and thresholds multiply quickly. Step 1 is the mitigation and there is no
other.

**F7 — A1 does not hold for every voyage.** Where the residual `R` (C.8) is large, KAIROS is
running as a preconditioned approximation, not an exact reduction. Mitigation: report
`max_k |RESIDUAL_k|` from **Test 8.5 P8** on every hindcast voyage, and stratify the results
by it. That turns F7 from a caveat into a measurement, and it is the most interesting thing
such a study could produce.

### 8.12.3 What a negative result would mean

If the study returns no significant advantage, it does **not** falsify Theorem C.1 — the
theorem is proved and verified to `9.77e-14` (§8.5) and is independent of any hindcast. It
would indicate that under operational constraints the minimum-time margin is small, or that
the objective being compared is the wrong one (F2), or that the baseline was already routed
(F3). **Publish it either way.** A validated implementation with a null hindcast result is a
more credible artefact than an unvalidated one with a favourable anecdote.

---

## Test 8.13 — The reporting template

Any implementation claiming to be KAIROS should publish **this exact table**, filled in.
Blank cells are permitted; unmarked omissions are not. Rows marked **†** are the ones that
separate a validated implementation from a demo, and rows marked **‡** are the ones specific
to the Co-Moving Reduction and have no counterpart in prior ship-routing work.

### 8.13.1 Correctness table

| # | Quantity | Symbol | Required | Your value |
|---|---|---|---|---|
| 1 | Max relative error vs golden vectors T1–T6 | — | `< 1e-12` | |
| 2 | T7 returns `+∞` (never a finite or negative `F`) | — | PASS | |
| 3 | T8 returns `σ = 0`, `F = +∞`, no exception | — | PASS | |
| 4 | T7/T8 branch coverage reached | — | PASS | |
| 5 | G3 conjugate branch error | — | `< 1e-15` | |
| 6 | Co-moving golden vectors T2w–T7w | — | `< 1e-12` | |
| 7 | Max `\|dθ/dt\|`, uniform flow (8.13) | — | `< 1e-14` rad/s | |
| 8 | Intermediate waypoints, uniform flow | — | `0` | |
| 9 | Arrival error vs (8.15)/(8.16) | — | `< 1e-12` rel | |
| 10 | Anisotropy ratio check (8.17) vs `29/19` | `Υ` | `< 1e-10` rel | |
| 11 | Crab-angle case (8.18): sign and magnitude | — | south of east | |
| 12 | Linear shear: `tan θ` linearity `\|β+a\|/a`, `R²` (8.21) | — | `≤ 1e-3`, `≥ 0.999` | |
| 13 | Rankine field values, circulation, vorticity | — | `< 1e-12` rel | |
| 14 | Rankine arrival inside the exact bracket (8.35) | — | PASS | |
| 15 | Rankine side test (8.36), both signs of `Γ` | — | PASS | |
| 16 | Rankine mirror test (8.37) | — | `≤ 1e-9` rel | |
| 17 | Clairaut spread (8.31), polished route | — | `≤ 1e-3` | |

### 8.13.2 The Co-Moving Reduction ‡

| # | Quantity | Required | Your value |
|---|---|---|---|
| 18 ‡ | **Per-leg bijection residual (8.38)** | `≤ 1e-11` m/s | |
| 19 ‡ | Co-moving excess over `V_s` (8.39) | `≤ 1e-11` m/s | |
| 20 ‡ | Mapped-to-ground excess vs the **advected** field (8.40) | `≤ 1e-11` m/s | |
| 21 ‡ | Converse residual (ground route → co-moving) | `≤ 1e-11` m/s | |
| 22 ‡ | Anti-test 8.5 P7 (un-advected field) **fails** as required | PASS | |
| 23 ‡ | Independent ground solve: excess over `V_s` | report | |
| 24 ‡ | `max_k \|RESIDUAL_k\|` on the real forecast stack (= `max\|R\|`, A1 violation) | report, m/s | |
| 25 ‡ | Chosen `w`; base and optimised `L_t`; cost of choosing `w` | report | |
| 26 ‡ | Cells failing (C.7) `\|c₀ − w\| < V_max`; min margin | report | |
| 27 ‡ | `σ_min^w` and the A2 margin `\|w\|/σ_min^w` | `< 1` | |
| 28 ‡ | Regime-A co-moving `L_t` | **exactly `0.0`** | |
| 29 ‡ | Dilation required (8.62) vs dilation provided, per component | required ≤ provided | |
| 30 ‡ | R1b boundary detector: is the goal node on the boundary? | `no` | |
| 31 ‡ | Goal-node ground miss; and the miss under the root-find selector | report both | |
| 32 ‡ | R2d neighbourhood-width sweep: miss vs radius | report the curve | |
| 33 ‡ | Round-trip `ground_position ∘ comoving_position` | `≤ 1e-9` rad | |

### 8.13.3 Approximation quality †

| # | Quantity | Symbol | Required | Your value |
|---|---|---|---|---|
| 34 † | Arrival error vs G4 exact at 1.0° / 0.5° / 0.25° | — | must **decrease** | |
| 35 † | Observed convergence order, least squares | `p` | report **with `R²`** | |
| 36 † | Richardson order from **every** constant-ratio triple | `p_R` | report all; flag sign changes | |
| 37 † | **Measured Class D floor** (the plateau) | — | report; compare to (8.55) | |
| 38 | Predicted mean metrication penalty for your stencil (8.54) | `P̄` | derive it | |
| 39 † | `I_ε×(P_ε, P_{ε/4})` on objectives `2..k` | — | `≤ 1 + ε` | |
| 40 † | **Length-invariance slope** of `I_ε×` against `D = S/h` | — | indistinguishable from 0 | |
| 41 † | Peak and mean labels per node | `Λ` | report; `≤` bound (8.50) | |
| 42 † | Certificate gap on the returned route | — | `(J − T_low)/T_low` | |
| 43 † | `T_low ≤ T*` on every problem with known `T*` | — | PASS, no exceptions | |

### 8.13.4 Licence and invariants †

| # | Quantity | Required | Your value |
|---|---|---|---|
| 44 † | **`max_x r(x)·L_t`** over the domain — *not* `h·L_t` (E4.1) | `< 1` where not relaxed | |
| 45 † | Same, at max / p99 / **median**, in **both** frames | report all six | |
| 46 † | Fraction of cells needing wait relaxation | report | |
| 47 † | Horizon-truncated wait evaluations (E5.1) | report the count | |
| 48 † | Bucket-queue monotonicity violations | `0` | |
| 49 | `ℓ_min = h/√2` exclusions applied (E3.1) | count `> 0` | |
| 50 | Heap-fallback firings, and `Υ_loc` when they fired (E2) | `Υ_loc > 12` | |
| 51 | `ζ` distribution: fraction pinned at an endpoint | report the histogram | |
| 52 | Stencil-radius histogram; fraction at the cap | report | |
| 53 | Nodes expanded / nodes in domain | report | |
| 54 | Metric evaluations; support-table cache hit rate | report | |
| 55 | Seakeeping bans `S1..S7`: each reached by ≥ 1 case | PASS | |
| 56 | Wave-convention test (following vs head seas) | PASS | |
| 57 | Geodesy G1: all five rows; row 1 to `1e-12`; round trip `≤ 1e-9` rad | PASS | |

### 8.13.5 Provenance block (mandatory)

Publish alongside the tables:

```
implementation language and version; grid spacing h and node count;
stencil (list the neighbour offsets) and its predicted P̄ from (8.54);
vessel parameters; forecast source and VINTAGE (issue time, not valid time);
whether the run is co-moving, ground, or split (C.8) with a residual corrector;
the chosen w and how it was chosen;
which tests were RUN and which were SKIPPED, with the reason;
git commit hash of the code that produced the table.
```

**"Which tests were SKIPPED, with the reason" is not a formality.** The credibility of the
whole table rests on the reader being able to see the holes. This specification's own holes,
restated once so they cannot be missed: **8.3 and 8.4 have been derived but not run; 8.6, 8.8
and 8.9 exist as protocols only; 8.12 has not been run at all; the identifiability of `w` is
untested (§8.10 caveat 2); Conj 8.2 is unproved; and the `r·L_t` column of §8.10.3 mixes two
statistics.**

---

## 8.14 References

Barles, G. & Souganidis, P. E. (1991). *Convergence of approximation schemes for fully
nonlinear second order equations.* Asymptotic Analysis 4, 271–283. — Thm 7.1.

Bao, D., Robles, C. & Shen, Z. (2004). *Zermelo navigation on Riemannian manifolds.*
J. Differential Geometry 66, 377–435. — the Zermelo ↔ Randers correspondence, §8.1.

Bryson, A. E. & Ho, Y.-C. (1975). *Applied Optimal Control.* — the linear-shear Zermelo
problem reproduced in §8.3.

Dial, R. B. (1969). *Algorithm 360: shortest-path forest with topological ordering.*
Comm. ACM 12, 632–633. — the bucket queue, Prop 4.9.

Fujiwara, T. et al. (2006). *A new estimation method of wind forces and moments acting on
ships.* — windage, §8.9.3.

Hodges, J. L. & Lehmann, E. L. (1963). *Estimates of location based on rank tests.*
Ann. Math. Statist. 34, 598–611. — §8.12 step 7.

IMO MSC.1/Circ.1228 (2007). *Revised guidance to the master for avoiding dangerous situations
in adverse weather and sea conditions.* — the seakeeping bans, §8.9.3.

Kumar, A. & Vladimirsky, A. (2010). *An efficient method for multiobjective optimal control
and optimal exit-time problems.* J. Sci. Comput. 43, 274–298. — ERRATA E11; §8.6.

Lolla, T. & Lermusiaux, P. F. J. (2014). *Level-set methods for time-optimal path planning in
strong dynamic flows.* — the closest prior approach to the routing problem itself.

Markvorsen, S. (2025). *Time-dependent Zermelo navigation with tacking.* arXiv:2508.07274. —
indicatrix fields that are time-dependent **only**, a complementary special case to A1.

Martins, E. Q. V. (1984). *On a multicriteria shortest path problem.* EJOR 16, 236–245. —
label-setting with vector labels.

Ochi, M. K. (1964). *Prediction of occurrence and severity of ship slamming at sea.* — §8.9.3.

Rankine, W. J. M. (1858). *A Manual of Applied Mechanics.* — the vortex model of §8.4.

Richardson, L. F. (1911). *The approximate arithmetical solution by finite differences of
physical problems.* Phil. Trans. R. Soc. A 210, 307–357. — §8.7 (8.51).

Roache, P. J. (1994). *Perspective: a method for uniform reporting of grid refinement
studies.* J. Fluids Eng. 116, 405–413. — the discipline §8.7.2 violates loudly.

Sethian, J. A. & Vladimirsky, A. (2003). *Ordered upwind methods for static
Hamilton–Jacobi equations: theory and algorithms.* SIAM J. Numer. Anal. 41, 325–363. —
the sweep; the continuum update that removes the §8.7 floor.

Taylor, G. I. (1938). *The spectrum of turbulence.* Proc. R. Soc. A 164, 476–490. — the
frozen-field hypothesis, the meteorological ancestor of assumption A1.

Tsaggouris, G. & Zaroliagis, C. (2009). *Multiobjective optimization: improved FPTAS for
shortest paths and non-linear objectives with applications.* Theory Comput. Syst. 45,
162–186. — value bucketing, ERRATA E7.1; §8.6.

Vladimirsky, A. (2006). *Static PDEs for time-dependent control problems.* Interfaces and
Free Boundaries 8, 281–300. — the causality condition, ERRATA E10; §8.10.

Wilcoxon, F. (1945). *Individual comparisons by ranking methods.* Biometrics Bull. 1, 80–83.
— §8.12 step 7.

Zermelo, E. (1931). *Über das Navigationsproblem bei ruhender oder veränderlicher
Windverteilung.* ZAMM 11, 114–124. — §8.2, §8.3.

Zitzler, E., Thiele, L., Laumanns, M., Fonseca, C. M. & Grunert da Fonseca, V. (2003).
*Performance assessment of multiobjective optimizers: an analysis and review.* IEEE Trans.
Evol. Comput. 7, 117–132. — the ε-indicators (8.46), (8.47).





