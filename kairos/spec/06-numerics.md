# §6 — Numerics

**Block owner:** `06-numerics.md`. This file owns `§6`, `Proc 6.x`, `Eq (6.x)`, and the
lemmas `Lemma 6.x` / `Thm 6.x` introduced below. Numbering per `CONTRACT.md §2`.

**Normative order.** `CORE-THEOREM.md` and `ERRATA.md` supersede this file wherever they
disagree; `CONTRACT.md` is normative except where those two override it. Three places in
this file record a **conflict between the normative documents and the reference
implementation**, and in each case the normative statement given here is the one to port
(§6.2.6, §6.6.6, §6.8.4).

---

## 6.0 What this file is for, and where it sits

KAIROS is defined by the **Co-Moving Reduction (Theorem C.1)**: in `y = x − w t` the routing
problem is exactly stationary, the causality obstruction is gone, and the solve is one
monotone pass plus an interception. Everything in *this* file is arithmetic in service of
that: the scalar root finds, the interpolation, the geodesy, and the floating-point discipline
that decide whether a port of KAIROS produces the same route as the reference or a plausible
wrong one.

That is not a demotion. Routing is the rare setting where a wrong answer is
*indistinguishable from a right one by inspection* — the output is a curve on a map and almost
any curve looks like a route (`handbook/02-debugging-playbook.md`, preamble). The golden
vectors `T7` and `T8` (`handbook/01-golden-vectors.md` §G2) exist because two of the
degeneracies in §6.7 return **plausible finite numbers of the wrong sign**. This file is
therefore written as a set of *obligations*, not suggestions.

### 6.0.1 Four ways Theorem C.1 simplifies the numerics

Stated up front because they change what an implementer has to build, and because each is a
consequence of the reduction rather than an independent design choice.

| Consequence of Thm C.1 | Effect on §6 |
|---|---|
| `𝒱_w(y)` has no `t` argument (Thm C.1b) | **Proc 6.4's time axis disappears.** In the co-moving solve there is no temporal interpolation of the field at all, hence no temporal sampling error (measured: `2.8e-14` m/s excess vs `6.7e-3` in the ground frame, `CORE-THEOREM.md §4`). Time interpolation is needed *only* by the residual corrector (algorithm step 6). |
| `L_t ≡ 0` in the co-moving frame | The wait relaxation `F̃_ℓ` of `ERRATA (E5.1)` is **not evaluated**, so its inner `inf` over `s ∈ [0, S_max(t)]` — a third nested root find — does not exist in the pure case. §6.7 D14 covers the residual-corrector case where it does. |
| `F_w(y, ·)` is `t`-independent | **`A(ζ)` is exactly convex** (Lemma 6.9). This is what licenses golden section *and* safeguarded Newton in Proc 6.3 with a proof rather than a hope. In the ground frame convexity holds only up to a perturbation of size `ℓ_max·L_t·|T_j − T_k|`, which is why the ground-frame inner minimisation has no such guarantee. |
| Interception is solved on the discretisation (`CORE-THEOREM.md §8.1 R2`) | The scalar root find of `Eq (C.4)` is **not** the production path. Goal selection is an `O(N)` scan minimising `‖(y + w·T[y]) − x_B‖`. §6.5.6 gives the geodesy that scan needs and §6.7 D12 the failure mode when it is skipped. |

### 6.0.2 Prior art

Nothing in §6 is claimed as new. Root finding: **Dekker (1969)**, **Brent (1973)** for the
bracket-preserving hybrid; **Banach (1922)** for Proc 6.2's convergence. Derivative-free
unimodal minimisation: **Kiefer (1953)**. Floating-point analysis: **Sterbenz (1974)**,
**Higham (2002)**. Monotone interpolation: **Fritsch & Carlson (1980)**; cubic convolution:
**Keys (1981)**. Monotone schemes and convergence: **Barles & Souganidis (1991)**; the
ordered-upwind construction those tolerances serve: **Sethian & Vladimirsky (2003)**;
single-pass licences for time-dependent control: **Vladimirsky (2006)**; multi-objective
front propagation: **Kumar & Vladimirsky (2010)**; value bucketing: **Tsaggouris &
Zaroliagis (2009)**; label setting: **Martins (1984)**; bucket queues: **Dial (1969)**.
Geodesy: the haversine form as popularised by **Sinnott (1984)**, the everywhere-stable
variant of **Vincenty (1975)**. Physics touched here: **Zermelo (1931)** and the
Zermelo↔Randers correspondence of **Bao, Robles & Shen (2004)**; the frozen-field hypothesis
behind assumption A1 is **Taylor (1938)**; the windage regression whose kink Proc 6.1 must
tolerate is **Fujiwara (2006)**; the slamming statistics behind the zero-wave-height guard are
**Ochi (1964)**; the operational thresholds that make the admissible set discontinuous are
**IMO MSC.1/Circ.1228**; the level-set routing lineage is **Lolla & Lermusiaux (2014)**; the
time-dependent-only Zermelo special case is **Markvorsen (2025)**.

### 6.0.3 The floating-point model, fixed once

All of §6 assumes **IEEE-754 binary64** with round-to-nearest-even, unit roundoff

```
u = 2⁻⁵³ = 1.110 223 024 625 157 e−16                                        (6.1)
```

Normative constraints on the build:

- **No fast-math, no reassociation, no flush-to-zero.** Every bound in §6.6 assumes correctly
  rounded `+ − × ÷ sqrt`. `-ffast-math` (or its equivalent) invalidates Lemma 6.13 and
  Lemma 6.14 and voids the golden-vector tolerances of `handbook/01-golden-vectors.md`.
- **FMA is permitted but must not change a branch.** Contracting `a*b+c` into an FMA changes
  the rounding of intermediate values. Where a *sign test* depends on such an expression
  (Proc 6.3's `R(ζ)`, §6.6.5's dominance) the expression must be evaluated with explicit
  intermediate rounding, or the sign test must be made robust to one ulp. Both are specified
  in place.
- **`sqrt` is correctly rounded** by IEEE-754 and is therefore bit-reproducible across
  platforms. **`sin`, `cos`, `asin`, `atan2`, `log`, `exp`, `pow` are not** — no IEEE-754
  edition requires them to be correctly rounded, and libm implementations differ in the last
  ulp. §6.10 states exactly what reproducibility KAIROS does and does not guarantee as a
  result, and Proc 6.9 removes `log`/`pow` from the one place where a last-ulp difference
  would change the returned Pareto front.
- **No unordered comparison may be reached with a NaN operand.** Every procedure below is
  specified to return a defined value rather than NaN; §6.7 is the exhaustive list.

### 6.0.4 Units are physical, everywhere

Every tolerance in this file is stated in the unit of the quantity it bounds — m/s, seconds,
radians, metres — and justified against a physical scale, never as a bare relative epsilon.
This is not style. A relative tolerance on `V` is meaningless without knowing that `V ≈ 8 m/s`,
and the one place the reference implementation states a tolerance in the wrong form
(`_V_XTOL = 1e-4 m/s` as an *absolute* stop where a *relative* one is required) is precisely
the place where two procedures fail to compose (§6.2.6).

---

## Proc 6.1 — The attainable-speed root find

**Owns:** primitive `attainable(vessel, env, theta, q) -> Option<f64>` (`CONTRACT.md §4`).

### 6.1.1 Statement of the problem

Given a vessel, an environmental state `Env`, a heading `θ` and a throttle `q`, return the
speed through water `V` the ship can hold. With `P_D(V; θ)` the delivered shaft power of
`Eq (1.8)` and `V_cap := V_max_hull`, define

```
g(V)  :=  P_D(V; θ)  −  q · P_MCR                                            (6.2)
```

and

```
V_pwr(θ, q)  :=  sup { connected component containing 0⁺ of { V ∈ (0, V_cap] : g(V) ≤ 0 } }  (6.3)
```

**Not** "the largest `V` with `g(V) ≤ 0`.** The distinction is Lemma 1.4's and it is
physical: a ship accelerates continuously from rest, so a speed sitting beyond a power hump
the engine cannot climb is not attainable however comfortable the power balance looks once you
are there. For strictly increasing `P_D` the two definitions coincide; for a user-supplied
non-monotone speed–power spline they do not, and (6.3) is the one that is right.

Equivalently: **`V_pwr` is the smallest positive root of `g`**, or `V_cap` if `g < 0`
throughout.

### 6.1.2 Why the objective is not smooth

Three sources of non-smoothness, all real, all reasons Newton on `g` is unsafe:

1. **Windage.** The apparent wind is `W_a = W₁₀ − V·n(θ)`. Any drag law built on `|W_a|` has a
   kink at `W_a = 0`, i.e. at the single speed where the ship exactly matches the wind
   component. The reference physics avoids the worst of it by using
   `−½ρ C_X A_T |W_a| ⟨W_a, n⟩` rather than `½ρ C_X A_T |W_a|² cos ψ`, because the product is
   differentiable through the zero-wind point while `|W_a|` alone is not. The **Fujiwara
   (2006)** family of `C_X(ψ)` regressions is a Fourier series in the apparent-wind angle `ψ`,
   and `ψ = atan2(...)` is itself undefined at `W_a = 0`; the truncated series is smooth in
   `ψ` but the composition with `ψ(V)` is not smooth at that point.
2. **User-supplied speed–power curves.** `Vessel.calm_power` is explicitly replaceable by a
   spline through sea-trial data. A natural cubic spline through measured points is not
   guaranteed monotone; a Fritsch–Carlson monotone cubic is (§6.4.6).
3. **Sign changes.** Wave and wind resistance are *signed*: a following sea and a following
   wind reduce resistance, so `P_D` may be negative at low `V`. Clamping `P_D` at zero would
   introduce a flat segment, destroy strict monotonicity, and hand the root find a degenerate
   bracket. The clamp belongs in `fuel_rate`, not here.

### 6.1.3 Proc 6.1 — procedure

```
Proc 6.1  attainable_speed(vessel, env, theta, q) -> f64
Input :  vessel, env, theta [rad], q [-]
Output:  V in [0, V_cap]  (m/s).  NEVER NaN, NEVER raises, NEVER negative.
Invariant: the returned V satisfies g(V) <= 0 (it is holdable on the available power).

 1  if V_cap not finite or V_cap <= 0            : return 0.0      # corrupt vessel record
 2  if q not finite or q <= 0 or P_MCR <= 0      : return 0.0      # no power on offer
 3  P_avail <- min(q, Q_OVERLOAD) * P_MCR ;  Q_OVERLOAD = 1.15
 4  if P_avail not finite or P_avail <= 0        : return 0.0
 5  curve <- precompute the V-independent half of P_D at this (env, theta)
 6  g(V)  <- curve.at(V) - P_avail ;  if curve.at(V) not finite then g := +INF
 7  # --- bracketing scan ---
 8  v_prev <- V_EPS = 1e-6 ;  g_prev <- g(V_EPS)
 9  if g_prev not finite or g_prev > 0           : return 0.0      # not even a crawl
10  found <- false
11  for i = 1 .. N_SCAN                          # N_SCAN = 32
12      v_i <- V_cap * i / N_SCAN
13      g_i <- g(v_i)
14      if g_i > 0 : (a,b,fa,fb) <- (v_prev, v_i, g_prev, g_i) ; found <- true ; break
15      (v_prev, g_prev) <- (v_i, g_i)
16  if not found                                 : return V_cap    # hull cap binds
17  # --- bracket refinement, Proc 6.1a ---
18  V <- bracketed_root(g, a, b, fa, fb)
19  if V < V_FLOOR = 0.05                        : return 0.0      # no steerage way
20  return V
```

```
Proc 6.1a  bracketed_root(f, a, b, fa, fb) -> f64
Precondition: f(a) <= 0 < f(b).
Postcondition: returns a point of the final bracket on the FEASIBLE side.

 1  for k = 0 .. N_ROOT-1                        # N_ROOT = 60
 2      width <- b - a
 3      if width <= XTOL : break
 4      if k is even:                            # safeguarded secant
 5          d <- fb - fa
 6          c <- (a - fa*width/d)  if |d| > 1e-30  else  (a + 0.5*width)
 7          if not (a + 0.05*width < c < b - 0.05*width) : c <- a + 0.5*width
 8      else:                                    # unconditional bisection
 9          c <- a + 0.5*width
10      fc <- f(c)
11      if fc not finite : (b, fb) <- (c, +INF) ; continue     # never propagate poison
12      if fc <= 0 : (a, fa) <- (c, fc) ; if -fc <= FTOL : return c
13      else       : (b, fb) <- (c, fc)
14  return a
```

Line 14 of Proc 6.1a — **return `a`, not the midpoint** — is normative. The returned speed
must be one the ship can actually hold on the available power; erring the other way hands the
solver a route it cannot sail, and a shortest-path solver selects preferentially for exactly
that error (the bias argument of Lemma 6.5 applies verbatim).

### 6.1.4 Lemma 6.1 — guaranteed convergence of Proc 6.1a

> **Lemma 6.1.** Let `f` be any function with `f(a₀) ≤ 0 < f(b₀)` for which every evaluation
> returns a value in `ℝ ∪ {+∞}` (never NaN). Then Proc 6.1a maintains the invariant
> `f(a) ≤ 0 < f(b)` at every iteration, and after `k` iterations the bracket width satisfies
> ```
> b − a  ≤  (b₀ − a₀) · 2^(−⌊k/2⌋)                                            (6.4)
> ```
> Consequently the loop terminates in at most `2⌈log₂((b₀−a₀)/XTOL)⌉ + 1` iterations, and if
> `f` is continuous the returned point is within `XTOL` of a root.

**Proof.** *Invariant.* Initially it holds by hypothesis. Each iteration computes some
`c ∈ (a, b)`: on the even branch `c` is either the secant point, forced by line 7 into
`(a + 0.05w, b − 0.05w) ⊂ (a,b)`, or the midpoint; on the odd branch it is the midpoint.
Line 11 replaces `b` by `c` with `fb := +∞ > 0`, preserving the invariant. Line 12 replaces
`a` by `c` with `fc ≤ 0`; line 13 replaces `b` by `c` with `fc > 0`. In every branch the
invariant is preserved and the bracket strictly shrinks (`c` is interior).

*Width bound.* On every odd `k` the update is an unconditional bisection, so `b − a` is
exactly halved. Even iterations never increase the width. Among iterations `0..k−1` there are
`⌊k/2⌋` odd ones, giving (6.4).

*Termination.* (6.4) forces `b − a ≤ XTOL` once `⌊k/2⌋ ≥ log₂((b₀−a₀)/XTOL)`.

*Accuracy.* If `f` is continuous, `f(a) ≤ 0 < f(b)` and `b − a ≤ XTOL` place a root of `f`
in `[a,b]`, so `|a − root| ≤ XTOL`. ∎

**Remark 6.1.1 (why not Brent).** Brent (1973) adds inverse quadratic interpolation and
bookkeeping to guarantee superlinear convergence on smooth `f`. Proc 6.1a is the same safety
net without the bookkeeping. The trade is deliberate: the secant reuses the two bracket
endpoints and costs **zero** extra evaluations of `P_D`, whereas a Newton step needs a
derivative — a central difference costs two extra `P_D` evaluations per iteration. In an inner
loop that runs tens of millions of times, tripling the evaluation count to save two iterations
is a bad trade. Measured behaviour on the default bulker: the secant lands on the answer first
and the loop exits in about a dozen `P_D` calls.

**Remark 6.1.2 (what breaks without the alternation).** A pure secant iteration on a convex
`g` stalls: one endpoint never moves and the bracket width tends to a positive limit. Without
line 8–9 the `XTOL` exit is never reached and the method returns whatever line 14 holds after
`N_ROOT` iterations, with **no bound on its distance from the root**. The alternation is what
makes (6.4) a theorem.

### 6.1.5 Tolerances, in physical units

| Symbol | Value | Unit | Justification |
|---|---|---|---|
| `XTOL` (feeding Proc 6.2) | `8u·V` ≈ `1.8e-15·V` | m/s | **Relative**, not absolute. See §6.2.6: this root is the inner function of a fixed point whose residual tolerance is `1e-11·V`; an absolute inner floor above that makes the outer iteration unable to converge. Eight ulp is two bisections from the last representable bracket. |
| `XTOL` (standalone: fuel reporting, diagnostics) | `1e-4` | m/s | 0.2 milliknot — two orders below anything a helmsman holds, four below the metric's own modelling error. Refining further only buys arithmetic. |
| `FTOL` | `1e-9 · P_avail` | W | Relative power residual accepted as an exact hit. At `P_MCR = 11 MW` that is 11 mW. |
| `N_SCAN` | 32 | — | Resolves any power excursion wider than `V_cap/32 = 0.265 m/s` for the default bulker. See the limitation below. |
| `N_ROOT` | 60 | — | By (6.4), 60 iterations give `2⁻³⁰ ≈ 9.3e-10` of the initial bracket even if every secant step is rejected. Never reached in practice. |
| `V_EPS` | `1e-6` | m/s | Left end of the scan. `P_D(V) → 0` as `V → 0⁺`, so `g(V_EPS) < 0` for any sane vessel; reaching `g(V_EPS) > 0` means the supplied `calm_power` is singular at the origin, which is a corrupt record, not a sea state. |
| `V_FLOOR` | `0.05` | m/s | Below this the ship has no steerage way and calling the speed "attainable" is a lie the solver would build a route on. The *operational* minimum (manoeuvring speed, engine minimum load `q_min = 0.15`) is a seakeeping ban applied **above** this function, not inside it. |
| `Q_OVERLOAD` | `1.15` | — | Hard ceiling on throttle. MCR overload beyond 15 % is fiction, and the lower bound `q ≥ q_min` is the caller's job. |

### 6.1.6 Behaviour when no root exists — exhaustive

| Condition | Returned | Why |
|---|---|---|
| `g < 0` on all of `(V_EPS, V_cap]` | `V_cap` | Power-unlimited: the hull/contract cap binds. Not an error. |
| `g(V_EPS) > 0` | `0.0` | Not even a crawl is sustainable. With any bounded resistance model `P_D → 0` as `V → 0`, so this is unreachable physically; reaching it indicates a singular `calm_power`. |
| Smallest root `< V_FLOOR` | `0.0` | No steerage way. |
| `q ≤ 0`, `q` non-finite, `P_MCR ≤ 0`, `V_cap ≤ 0` non-finite | `0.0` | No power on offer / corrupt record. |
| `P_D(V)` returns non-finite in the interior | bracket collapses toward the feasible side (line 11) | A poisoned evaluation is treated as `+∞` (infeasible) and never propagated. |

**Limitation, stated not hidden.** A power excursion above `q·P_MCR` narrower than
`V_cap/N_SCAN` falls between scan samples and is missed; the function then reports a speed on
the *far* side of it — a speed the ship cannot in fact accelerate through. No fixed sampling
can do better without an a-priori bound on the spline's curvature. Raise `N_SCAN` if a
vessel's measured curve is known to be that spiky, and record the raised value in the run log.
**What breaks without the scan:** starting the bracket at the top and walking down finds *a*
root in two evaluations but the **wrong** one — the last crossing rather than the first —
which is exactly the non-monotone case (6.3) exists to get right.

**Cost.** Step 1 (the scan) dominates: at a normal throttle the root sits close to the hull
cap, so the scan runs most of the way to `N_SCAN` before it brackets anything. It is paid down
by hoisting the `V`-independent half of the resistance decomposition out of the loop, not by
shortening the scan.

---

## Proc 6.2 — The drift-correction fixed point

**Owns:** the inner solve of `sigma(x, t, u, q)` and of `legs(...)` — i.e. the step from a
*requested course over ground* `u` to a *commanded heading* `θ` and a speed made good.

### 6.2.1 The coupling, stated exactly

Let `u` be the requested unit direction over ground, at heading `α = atan2(u_E, u_N)`, and let
`u⊥ := (−u_N, u_E)`. Decompose the effective drift `c` (current + leeway; in the co-moving
frame `c ← c₀ − w`, `Eq (C.6)`):

```
c∥  := ⟨c, u⟩ ,        c⊥ := ⟨c, u⊥⟩                                          (6.5)
```

The ground velocity `V·n(θ) + c` is parallel to `u` iff its cross-track component vanishes.
Since `⟨n(θ), u⊥⟩ = sin(θ − α)`,

```
V · sin(θ − α)  =  c⊥          ⟹      θ  =  α + arcsin(c⊥ / V)               (6.6)
σ(u)            =  sqrt(V² − c⊥²) + c∥                                        (6.7)
```

**The coupling.** `V = V_pwr(θ, q)` from Proc 6.1 depends on `θ`, because added resistance is
directional: waves have a mean direction `μ_w` and wind a direction `W₁₀`, so the same throttle
buys a different speed on a different heading. Hence (6.6) and (6.7) are coupled and (6.6) is a
**fixed-point equation in `θ`**.

Write the iteration map

```
Θ(θ)  :=  α + arcsin( c⊥ / V(θ) ) ,      V(θ) := V_pwr(θ, q)                  (6.8)
```

on the interval `I := [α − π/2, α + π/2]`.

**What breaks if the coupling is ignored** (i.e. if one evaluates `V` once at `θ = α` and
stops): the reported `σ` is (6.7) evaluated with the wrong `V`. In head seas `V(θ*) < V(α)`,
so `σ` is **over**-stated; §6.2.5 shows why a shortest-path solver selects preferentially for
over-statement. Measured magnitude on the reference physics at `q = 1` in a 5 m sea:
`|dV/dθ| ≈ 0.12 m/s/rad` and the crab angle is a few degrees, so the one-shot error is
`~1e-2 m/s` — of the same order as the `6.7e-3 m/s` ground-frame temporal sampling error that
`CORE-THEOREM.md §4` calls out as significant.

### 6.2.2 Thm 6.2 — convergence of the fixed point

> **Thm 6.2 (contraction).** Fix `α`, `c⊥`, `q`. Suppose on `I`:
> (i) `V(·)` is Lipschitz with constant `M := sup_I |dV/dθ|` (finite);
> (ii) `V(θ) ≥ V_lo > |c⊥|` for all `θ ∈ I`.
> Put
> ```
> K  :=  |c⊥| · M / ( V_lo · sqrt(V_lo² − c⊥²) )                              (6.9)
> ```
> If `K < 1` then `Θ` maps `I` into `I`, has a unique fixed point `θ* ∈ I`, and the iteration
> `θ_{k+1} = Θ(θ_k)` converges to it from **any** `θ₀ ∈ I` with
> ```
> |θ_k − θ*|  ≤  K^k · |θ₀ − θ*|  ≤  K^k · (π/2)                              (6.10)
> ```

**Proof.** *Self-map.* By (ii), `|c⊥/V(θ)| < 1` for every `θ ∈ I`, so `arcsin(c⊥/V(θ))` is
defined and lies in `(−π/2, π/2)`; hence `Θ(θ) ∈ (α − π/2, α + π/2) ⊂ I`.

*Derivative.* `V` is Lipschitz hence differentiable a.e.; where it is,

```
Θ'(θ) = d/dθ [ arcsin(c⊥ / V) ]
      = (1 / sqrt(1 − (c⊥/V)²)) · (−c⊥/V²) · V'(θ)
```

so

```
|Θ'(θ)|  =  |c⊥| · |V'(θ)| / ( V² · sqrt(1 − (c⊥/V)²) )
         =  |c⊥| · |V'(θ)| / ( V · sqrt(V² − c⊥²) )                          (6.11)
```

The map `V ↦ V·sqrt(V² − c⊥²)` is strictly increasing on `V > |c⊥|`, so replacing `V` by the
lower bound `V_lo` and `|V'|` by `M` gives `|Θ'| ≤ K` a.e. on `I`. A Lipschitz function whose
a.e. derivative is bounded by `K` is `K`-Lipschitz (it is absolutely continuous, being
Lipschitz, so it is the integral of its derivative).

*Fixed point.* `Θ: I → I` is a `K`-contraction on the complete metric space `I` with `K < 1`;
**Banach (1922)** gives existence, uniqueness and (6.10). ∎

**Corollary 6.2.1 (iteration count).** To reach a heading accuracy `ε_θ` from `θ₀ = α`,
```
k  ≥  ln( ε_θ / (π/2) ) / ln K                                               (6.12)
```
iterations suffice. With the measured `K ≈ 3e-2` at `q = q_min` and `ε_θ = 1e-11` rad:
`ln(6.37e-12)/ln(0.03) = (−25.78)/(−3.507) = 7.35`, so **8 iterations** — which is exactly the
worst case measured on the `72 × 5` control grid of the reference self-test.

**Remark 6.2.2 (the rate is measured, not assumed, and the estimate and the measurement
disagree by an order of magnitude).** From (6.11) with `|c⊥| ≪ V` the rate scales as
`|c⊥| M / V²`. At full throttle in a 5 m sea, `M ≈ 0.12 m/s/rad` and `V ≈ 8 m/s`, giving
`K ≈ 3e-3` — and that is what is observed. At `q = q_min` the reference vessel's `V` falls to
`≈ 3.2 m/s`; the `1/V²` scaling alone predicts `(8/3.2)² = 6.25×`, i.e. `K ≈ 1.9e-2`, and the
observed value is `≈ 3e-2` (the residual factor is `M` also changing with throttle). The
measured relative cross-track residual sequence at `q_min` is

```
7.4e-3 , 2.3e-4 , 7.1e-6 , 2.2e-7 , 6.9e-9 , 2.2e-10 , 6.7e-12 , 2.1e-13 , … → 0
```

Ratio of consecutive terms `≈ 3.1e-2` ✓ consistent with (6.9). **"3–4 iterations" is right
only for physically meaningless tolerances** — `1e-7` relative is already a `1e-6` rad heading
error, i.e. `6e-5` degrees. Driving the residual to `1e-11` takes 6 in most directions and 8 in
the worst one.

**Remark 6.2.3 (where the contraction dies).** `K → ∞` as `|c⊥| → V`: the `arcsin` steepens
without bound. That is exactly where the direction is about to become infeasible anyway
(golden vector **T8**), so the degradation of the iteration and the degradation of the physics
coincide — the numerics fail where the answer is `+∞` regardless. The fallback of §6.2.4
covers the finite-but-badly-conditioned band.

**What breaks without hypothesis (i):** if `V(·)` has a genuine discontinuity in `θ` — which a
*hard* seakeeping ban would produce if it were applied inside `attainable` — then `M = ∞`, `K`
is undefined, and the iteration can cycle. This is why bans are applied **after** the fixed
point converges (Proc 6.2 line 12), not inside `attainable`. **IMO MSC.1/Circ.1228** thresholds
are step functions in `(V, θ)`; putting them inside the inner solve is a defect.
**What breaks without hypothesis (ii):** the `arcsin` argument leaves `[−1,1]` and the map is
undefined; the procedure below detects this and returns infeasible.

### 6.2.3 Proc 6.2 — procedure

```
Proc 6.2  solve_leg(env, alpha, c_par, c_perp, q) -> Option<Leg>
Input : env, alpha [rad], c_par, c_perp [m/s], q [-]
Output: a Leg (sog, rates, theta, q) or NONE meaning F = +INF in this direction.
Invariant on success: |V·sin(theta - alpha) - c_perp| <= EPS_RES · V.

 1  theta <- alpha
 2  V     <- attainable(vessel, env, theta, q)          # Proc 6.1
 3  residual <- +INF
 4  for it = 1 .. N_FP                                   # N_FP = 12
 5      if V <= |c_perp| : return NONE                   # T8: cannot hold the track
 6      theta <- alpha + asin( clamp(c_perp / V, -1, +1) )
 7      V     <- attainable(vessel, env, theta, q)
 8      residual <- V·sin(theta - alpha) - c_perp
 9      if |residual| <= EPS_RES · V : break
10  record it into fp_iters_max
11  if V <= |c_perp|              : return NONE
12  if |residual| > EPS_RES · V   : goto FALLBACK
13  if use_bans and violations(vessel, env, theta, q, V) != 0 : return NONE
14  sog <- sqrt(max(0, V² − c_perp²)) + c_par
15  if sog <= SIGMA_FLOOR : return NONE                   # set carries the ship backwards
16  return Leg(sog, rates(...), theta = wrap_pi(theta), q)

FALLBACK:                                                 # bracketed, always converges
17  fp_fallbacks <- fp_fallbacks + 1
18  G(theta) := attainable(vessel, env, theta, q)·sin(theta − alpha) − c_perp
19  lo <- alpha − pi/2 ;  hi <- alpha + pi/2
20  G_lo <- −attainable(...,lo,q) − c_perp ;  G_hi <- +attainable(...,hi,q) − c_perp
21  if not (G_lo < 0 < G_hi) : return NONE                # no bracket: unreachable
22  for 1 .. N_BIS                                        # N_BIS = 60
23      mid <- 0.5·(lo + hi)
24      if G(mid) < 0 : lo <- mid  else  hi <- mid
25  theta <- 0.5·(lo + hi) ;  V <- attainable(..., theta, q)
26  if V <= |c_perp| : return NONE
27  residual <- V·sin(theta − alpha) − c_perp
28  if |residual| > EPS_RES_FB · V : fp_hard_failures += 1 ; return NONE      # NORMATIVE
29  continue at line 13
```

**Line 6 is exact by construction.** `θ` solves `V_old·sin(θ−α) = c⊥` exactly, so the residual
computed at line 8 after re-evaluating `V` measures `(V_new − V_old)·sin(θ−α)`: *the fixed
point converges iff `V` does.* That is why one residual test suffices and no separate `Δθ`
test is needed.

**Line 20 — why the bracket exists.** `G` is continuous on `I` wherever `V` is (hypothesis (i)
of Thm 6.2). At `θ = α − π/2`, `sin(θ−α) = −1` so `G = −V − c⊥ < 0` whenever `V > |c⊥|`; at
`θ = α + π/2`, `G = +V − c⊥ > 0` under the same condition. So a bracket exists **iff the
direction is feasible at all**, and its absence at line 21 is a correct infeasibility
certificate rather than a numerical failure.

### 6.2.4 Non-convergence: the normative rule

> **NORMATIVE.** If the iteration does not reach `|residual| ≤ EPS_RES·V`, the implementation
> **must** run the bracketed fallback (lines 17–28). If the fallback finds no bracket, or its
> own residual exceeds `EPS_RES_FB·V`, the implementation **must return NONE** — the direction
> is infeasible, `F = +∞`, and it is excluded from the update.
>
> **Under no circumstance may a half-converged `θ`, `V` or `σ` be returned.** Returning the
> last iterate is a defect of the same severity as the negative-`F` bug of golden vector T7.

### 6.2.5 Lemma 6.5 — why a half-converged value is worse than no value

> **Lemma 6.5 (selection bias of an unconverged leg).** Let `θ` be an iterate with residual
> `ρ := V·sin(θ−α) − c⊥ ≠ 0`. Then:
> (a) the ground velocity `V n(θ) + c` has cross-track component `ρ`, so the ship does **not**
> follow `u`;
> (b) the along-track speed actually achieved at that heading is
> `σ_true = V·cos(θ−α) + c∥ = sqrt(V² − (c⊥+ρ)²) + c∥`, whereas the value reported by (6.7) is
> `σ_rep = sqrt(V² − c⊥²) + c∥`, so
> ```
> σ_rep − σ_true  =  sqrt(V² − c⊥²) − sqrt(V² − (c⊥+ρ)²)  ≈  (c⊥ ρ) / sqrt(V² − c⊥²)   (6.13)
> ```
> which is **positive** whenever `ρ` has the sign of `c⊥` — the generic case, since the
> iteration approaches `θ*` monotonically from the `θ₀ = α` side in a contraction;
> (c) the solver minimises `F = 1/σ` over a set of candidate rules, so any over-statement of
> `σ` is **preferentially selected**: the maximum over many noisy estimates is biased upward
> even when each estimate is unbiased.

**Proof.** (a) The cross-track component of `V n(θ) + c` is `V⟨n(θ),u⊥⟩ + ⟨c,u⊥⟩ =
V sin(θ−α) + c⊥`. Careful with signs: (6.6) is the condition `V sin(θ−α) = c⊥` under the
convention that the crab is *into* the set, so the residual as defined at line 8 is precisely
the failure of the track constraint; a nonzero `ρ` means the resulting motion is not along `u`.
(b) Substituting `sin(θ−α) = (c⊥+ρ)/V` into `cos(θ−α) = sqrt(1 − sin²)` gives the stated
`σ_true`, and (6.13) is the first-order expansion of the difference in `ρ`.
(c) Let `R` be the set of candidate rules at a node and `σ_r` the reported speed of rule `r`,
with true speeds `σ_r^true ≤ σ_r`. The update takes `min_r ℓ_r/σ_r`, and
`min_r ℓ_r/σ_r ≤ min_r ℓ_r/σ_r^true` with strict inequality whenever the argmin is a rule with
`σ_r > σ_r^true`. So the error does not average out over rules; it accumulates in the direction
that makes the route look faster. ∎

**Consequence.** An unconverged leg produces an arrival time that is **optimistic and
selected**, i.e. a route the ship cannot sail, reported as the best available. A `NONE`
produces a route that is merely suboptimal. Between an unsailable optimum and a sailable
suboptimum, a routing system must choose the second. This is the entire justification for the
rule in §6.2.4.

**Instrumentation (normative).** Report `fp_iters_max`, `fp_fallbacks` and `fp_hard_failures`
at the end of every run. `fp_fallbacks > 0` in calm water is a bug (the contraction is trivial
there). `fp_hard_failures / n_evaluations > 1e-4` invalidates the run and must be reported as
such, not silently absorbed.

### 6.2.6 CONFLICT: Proc 6.1 and Proc 6.2 do not compose at the reference tolerances

This is the one place in the numerics where two correct-looking procedures are jointly wrong,
and it is recorded here because it is invisible in either file alone.

- `metric.py` sets the outer residual tolerance `_FP_RES_TOL = 1e-11` **relative to `V`**, and
  its own `ReferencePhysics.attainable` stops on a **relative** bracket of `4` ulp.
- `powering.py` — the module the full `seakeeping` path routes through — sets
  `_V_XTOL = 1e-4 m/s`, an **absolute** stop.

An absolute inner tolerance of `1e-4 m/s` puts a noise floor of `1e-4/8 = 1.25e-5` *relative*
on `V`. The outer tolerance demands `1e-11` relative. The outer iteration therefore **cannot**
converge below a floor six orders of magnitude above its target: it thrashes, exhausts `N_FP`,
and takes the bisection fallback **on every leg**, at roughly 5× the cost and with no
accuracy gain.

> **Normative resolution.** When Proc 6.1 feeds Proc 6.2, its stopping criterion **must** be
> relative: `b − a ≤ 8u·b`. An implementation that cannot afford the tighter inner solve must
> instead set `EPS_RES := max(1e-11, 100 · XTOL_abs / V)` and record the loosened value in the
> run log.

**Honest framing of the severity.** The loose inner tolerance is *physically* harmless: from
(6.6), `|∂θ/∂V| = (|c⊥|/V²)/sqrt(1 − (c⊥/V)²)`, so `ΔV = 1e-4 m/s` at `c⊥ = 1.5, V = 8` gives
`Δθ ≈ 2.3e-6` rad `= 1.3e-4` degrees — utterly irrelevant to a ship. The damage is
**algorithmic and reproducibility-related**, not accuracy-related: a procedure that always
falls back is 5× slower, and a fallback that fires on a floating-point noise threshold fires
*non-deterministically* across compilers and thread counts, which is precisely the failure
mode `00-overview.md` L9 flags. Fix it because it destroys determinism, not because the route
moves.

### 6.2.7 Tolerances

| Symbol | Value | Unit | Justification |
|---|---|---|---|
| `EPS_RES` | `1e-11` | relative to `V` | `1e-11 · 8 m/s = 8e-11 m/s` of cross-track slip, equivalently `1e-11` rad of heading error. Physically meaningless — and still `10⁵` above the attainable-speed root find's own noise floor once §6.2.6 is applied, so the target is reachable rather than aspirational. |
| `EPS_RES_FB` | `1e-9` | relative to `V` | The fallback's acceptance. Looser than `EPS_RES` by two orders because a bisection on `G` reaches `2⁻⁶⁰·π` in `θ` but `G` itself carries the inner root find's error; demanding `EPS_RES` of a path that was already in trouble manufactures spurious `NONE`s. |
| `N_FP` | 12 | — | Measured worst case 8 (Cor 6.2.1 and Remark 6.2.2) plus 4 iterations of margin. The reference implementation uses 10, which clears the measured worst case but leaves only 2; each iteration is one `attainable` call and the cap is reached on a vanishing fraction of legs, so 12 is the recommended value. |
| `N_BIS` | 60 | — | A `π`-wide bracket halved 60 times is `2.7e-18` rad, below one ulp of `θ`. The loop is bounded, not adaptive, because a fallback that can spin is worse than one that gives up. |
| `SIGMA_FLOOR` | `1e-3` | m/s | See §6.6.6 for the derivation and for the conflict with the two different values in the reference code. |

---

## Proc 6.3 — The inner minimisation over the front-edge parameter

**Owns:** the `ζ`-minimisation of `Eq (3.23)`, i.e. the continuum semi-Lagrangian update that
distinguishes KAIROS from a fixed-neighbour graph search.

### 6.3.1 The objective

From `Eq (3.23)`, for an accepted-front edge `(x_j, x_k)` and an update target `x`:

```
ξ(ζ) = ζ x_j + (1−ζ) x_k ,   T̃(ζ) = ζ T_j + (1−ζ) T_k ,   ℓ(ζ) = |x − ξ(ζ)| ,
A(ζ) = T̃(ζ) + ℓ(ζ) · F( x, T̃(ζ), (x − ξ(ζ))/ℓ(ζ) ) ,      ζ ∈ [0,1]         (3.23)
```

Introduce the two edge vectors, both computed **once per (node, edge) pair** in the local
orthonormal frame of `ERRATA (E8)`:

```
p := x − x_k  ,      e := x_j − x_k  ,      v(ζ) := x − ξ(ζ) = p − ζ e        (6.14)
```

Because `F(x,t,·)` is positively 1-homogeneous (it is a Minkowski gauge, `Def 2.2`),
`ℓ·F(x,t,u) = F(x,t,ℓu)`, so

```
A(ζ)  =  T̃(ζ)  +  F( x, T̃(ζ), v(ζ) )                                        (6.15)
```

— no normalisation, no division by `ℓ`, and no special case at `ℓ → 0`. Use (6.15), not
(3.23), in code: it removes one square root and one division per evaluation and it removes the
only place where `ℓ` appears in a denominator.

### 6.3.2 The admissible `ζ`-set: the `ℓ_min` exclusion is a sub-interval computation

`ERRATA (E3)` requires the update to **skip any front point `ξ` with `|x − ξ| < ℓ_min`**, with
`ℓ_min = h/√2` and `c_geo = 1/√2 = 0.707 106 781 186 547 5` (Lemma E3.1). This is not a
post-hoc filter; it restricts the search interval, and the restriction must be computed
exactly or Dial's bucket-width bound `Δ_min = c_geo·h·F_min` (E3.1) is not a theorem.

`ℓ(ζ)² = |e|² ζ² − 2⟨p,e⟩ ζ + |p|²`, so `ℓ(ζ) < ℓ_min` on the open interval between the roots
of

```
|e|² ζ² − 2⟨p,e⟩ ζ + (|p|² − ℓ_min²) = 0                                      (6.16)
```

```
Proc 6.3a  admissible_zeta(p, e, l_min) -> list of at most 2 closed intervals in [0,1]
 1  E2 <- <e,e> ;  PE <- <p,e> ;  P2 <- <p,p>
 2  if E2 <= 0 : return [ [0,1] ]  if |p| >= l_min else []      # degenerate edge
 3  C  <- P2 - l_min*l_min
 4  disc <- PE*PE - E2*C
 5  if disc <= 0 : return [ [0,1] ]                              # never inside the ball
 6  s <- sqrt(disc)
 7  # stable quadratic roots (Citardauq/conjugate form): never subtract near-equal terms
 8  qq <- PE + sign(PE)*s          # sign(0) := +1
 9  z_a <- qq / E2 ;  z_b <- C / qq
10  (zlo, zhi) <- (min(z_a,z_b), max(z_a,z_b))
11  return [0,1] \ (zlo, zhi)      # 0, 1 or 2 closed sub-intervals
```

Line 8 is the standard cancellation-free root pair: computing both roots as
`(PE ± s)/E2` loses digits in whichever root involves the subtraction of near-equal
quantities, and that root is the one nearer `ζ = 0` — exactly the end the minimiser is drawn
to when `T_j ≫ T_k`. The pairing `z_a·z_b = C/E2` is exact to a rounding, which is the
identity the conjugate form exploits (**Higham 2002**, §1.8).

**What breaks without the exclusion.** `ERRATA (E3)` is explicit: an open interval has no
positive infimum, so `ℓ·F ≥ h·F_min` is *false*, Dial's correctness precondition
(bucket width ≤ minimum increment) fails, and the queue can finalise a node whose value is
later lowered — destroying the label-setting invariant. The exclusion costs nothing: such
points are interior to the stencil and their characteristics are represented by other front
edges.

**Infinite labels.** If `T_k = +∞` (unreached or land) then `T̃(ζ) = +∞` for every `ζ < 1`, so
the admissible set collapses to `{1}` and only the single-vertex rule `ρ_j` is informative
(`Remark 3.C.2`). Implement this as an early exit, before Proc 6.3a: it is the common case at
the edge of the reached region and it must not require evaluating `F` at `+∞`.

### 6.3.3 Lemma 6.9 — `A(ζ)` is convex in the co-moving frame

> **Lemma 6.9.** Let the solve be co-moving (Thm C.1b), so `F_w(x, ·)` has no `t` argument, and
> let `𝒱_w(x)` be convex (design decision D4: we solve with `conv 𝒱`). Then on any interval of
> `ζ` on which `T̃(ζ) < ∞`, the function `A(ζ)` of (6.15) is **convex**. If in addition
> `conv 𝒱_w(x)` is strictly convex and does not contain `0` on its boundary, `A` is strictly
> convex wherever `A` is finite, and `A ∈ C^∞` there when the indicatrix boundary is smooth.

**Proof.** `T̃(ζ) = T_k + ζ(T_j − T_k)` is affine in `ζ`. `v(ζ) = p − ζe` is affine in `ζ`.
`F_w(x, ·)` is the Minkowski gauge of the convex set `conv 𝒱_w(x)`, hence **sublinear**:
positively 1-homogeneous and subadditive, therefore convex on `ℝ²` (this is the standard
gauge/support duality, `Def 2.2` and `Prop 2.7`). A convex function composed with an affine map
is convex. The sum of a convex function and an affine function is convex. Hence
`A = T̃ + F_w ∘ v` is convex. Restriction to a sub-interval preserves convexity.

*Strictness and smoothness.* For a strictly convex indicatrix with `0 ∈ int conv 𝒱_w` the gauge
`F_w` is `C¹` away from the origin with positive-definite Hessian on the orthogonal complement
of `v` (the gauge is 1-homogeneous, so `∇²F_w · v = 0` always; strict convexity of `A` in the
scalar `ζ` follows because `e` is not parallel to `v(ζ)` for `ζ` in the interior of an
admissible interval, `e` being the edge direction and `v` the update direction, which are
independent by the `ℓ_min` exclusion). Smoothness of `A` follows from smoothness of `F_w`
away from `0` when the indicatrix boundary is smooth. ∎

> **Corollary 6.9.1 (ground frame).** Without the reduction, `F` carries a `t` argument and
> `A(ζ) = T̃(ζ) + F(x, T̃(ζ), v(ζ))`. Writing `A₀(ζ) := T̃(ζ) + F(x, t₀, v(ζ))` for any fixed
> `t₀` in the range of `T̃`, assumption (A2) gives
> ```
> | A(ζ) − A₀(ζ) |  ≤  ℓ_max · L_t · |T_j − T_k|  ≤  ℓ_max · L_t · h · F_max  (6.17)
> ```
> so `A` is convex **up to a perturbation of size (6.17)**, and nothing stronger can be
> claimed. With `r(x) = 2h = 55 km`, `L_t = 3.22e-7` (the ground-frame value measured in
> `CORE-THEOREM.md §8.2`), `h = 27.8 km` and `F_max = 0.175 s/m`, (6.17) is
> `55e3 · 3.22e-7 · 27.8e3 · 0.175 ≈ 86 s`. In the co-moving frame `L_t = 1.24e-7` on the same
> field, giving `33 s`; in the A1-exact regime `L_t ≡ 0` and the perturbation is **exactly
> zero**.

**This corollary is the practical payoff of Thm C.1 inside §6.** In the ground frame a
`ζ`-minimiser may be chasing a non-convex objective whose spurious local minima are up to
`86 s` deep, and neither golden section nor Newton has any guarantee. In the co-moving frame
the objective is convex by Lemma 6.9 and both methods are provably correct.

### 6.3.4 Golden section: when it is safe, and the tie rule

> **Lemma 6.10 (golden section is correct on a convex objective, including flat minima).**
> Let `A` be convex on `[lo, hi]` and let `c₁ < c₂` be interior points. If `A(c₁) < A(c₂)` then
> `argmin A ⊂ [lo, c₂]`. If `A(c₁) ≥ A(c₂)` then `argmin A ⊂ [c₁, hi]`. Hence the bracket
> update "keep `[lo, c₂]` when `A(c₁) < A(c₂)`, else keep `[c₁, hi]`" retains a minimiser at
> every step, with **no strict-unimodality hypothesis**.

**Proof.** Suppose `A(c₁) < A(c₂)` and some minimiser `ζ* > c₂`. Then `c₂ ∈ (c₁, ζ*)`, so
`c₂ = λ c₁ + (1−λ) ζ*` for some `λ ∈ (0,1)`, and convexity gives
`A(c₂) ≤ λ A(c₁) + (1−λ) A(ζ*) ≤ λ A(c₁) + (1−λ) A(c₂)`, hence
`(1−λ)(A(c₂) − A(c₂)) ≤ λ(A(c₁) − A(c₂))`, i.e. `0 ≤ λ (A(c₁) − A(c₂)) < 0` — contradiction.
So every minimiser lies in `[lo, c₂]`. The case `A(c₁) ≥ A(c₂)` is symmetric (with the
non-strict inequality the same argument places every minimiser in `[c₁, hi]`, and a flat
plateau spanning `c₁..c₂` is retained in both branches). ∎

**Remark 6.10.1.** Kiefer's (1953) classical statement requires *strict* unimodality precisely
because it must handle non-convex functions; Lemma 6.10 shows convexity buys the flat-plateau
case for free. The tie at `A(c₁) = A(c₂)` is resolved to the **`[c₁, hi]`** branch, normatively,
so that the comparison is a single `<` with a deterministic outcome — see §6.10.

```
Proc 6.3b  golden_section(A, lo, hi, tol_zeta, N_GS) -> (zeta, A_value)
 1  INV_PHI <- 0.618 033 988 749 894 848      # (sqrt(5)-1)/2, stored as a literal
 2  c1 <- hi - INV_PHI*(hi-lo) ;  c2 <- lo + INV_PHI*(hi-lo)
 3  f1 <- A(c1) ;  f2 <- A(c2)
 4  for 1 .. N_GS
 5      if hi - lo <= tol_zeta : break
 6      if f1 < f2 : (hi, c2, f2) <- (c2, c1, f1) ; c1 <- hi - INV_PHI*(hi-lo) ; f1 <- A(c1)
 7      else       : (lo, c1, f1) <- (c1, c2, f2) ; c2 <- lo + INV_PHI*(hi-lo) ; f2 <- A(c2)
 8  if f1 <= f2 : return (c1, f1) else return (c2, f2)
```

Note lines 6–7 are written so that **one** new evaluation of `A` occurs per iteration; that is
the whole point of the golden ratio and an implementation that recomputes both loses a factor
of two. `INV_PHI` is a stored decimal literal, not `(sqrt(5)-1)/2` evaluated at run time, so
that the sequence of bracket endpoints is bit-identical across platforms (§6.10).

**Iteration count, derived.** Set the target in *physical* units: the inner minimisation must
not contribute more than `τ_ζ = 1e-3 s` of arrival-time error. Near a minimum of a `C²`
objective, `A(ζ) − A(ζ*) ≈ ½ A''(ζ*) (ζ − ζ*)²`. Scale of `A''`: `A` is `T̃` (affine, no
contribution) plus `F(v(ζ))`, whose curvature in `ζ` is of order `|e|²/ℓ · (curvature of the
gauge)`, i.e. of order the leg cost itself, `ℓ·F ≈ r·F_max`. With `r = 56 km` and
`F_max = 0.175 s/m`, `A'' = O(1e4 s)`. Then

```
|ζ − ζ*|  ≤  sqrt( 2 τ_ζ / A'' )  =  sqrt( 2·1e-3 / 1e4 )  =  4.5e-4         (6.18)
```

From a bracket of width `≤ 1`, golden section needs
`k ≥ ln(4.5e-4)/ln(0.618 034) = (−7.706)/(−0.481 21) = 16.0` iterations. **`N_GS = 32` is
normative** — double the derived requirement, so the `tol_zeta` exit at line 5 is what
actually fires and the cap is a safety net. `tol_zeta = 4.5e-4` from (6.18).

**Cost.** 32 evaluations of `A`, each one call to `sigma`/`support`, is the dominant inner-loop
cost of the whole solver. Design decision **D2** exists to reduce it: with the support function
tabulated on `n_θ = 72` directions, `F` is recovered by duality (`Prop 2.7`) in `O(log n_θ)`
rather than by an `O(30)`-operation metric evaluation.

### 6.3.5 Safeguarded Newton: when it is safe, and the stable derivative

Newton is worth the extra machinery only in the **Randers fast path**, where `A'` is available
in closed form at the cost of a handful of flops. Elsewhere use golden section.

Differentiate (6.15). With `v'(ζ) = −e` and `T̃' = ΔT := T_j − T_k`,

```
A'(ζ)  =  ΔT  −  ⟨ ∇F_w( v(ζ) ) , e ⟩                                        (6.19)
```

For the Randers gauge with effective drift `c` (co-moving: `c = c₀ − w`, `Eq (C.6)`) and
through-water speed `V_s`, write

```
a := ⟨v, c⟩ ,   D := |v|² ,   λ := V_s² − |c|² ,   s := sqrt(a² + λD)         (6.20)
```

> **Lemma 6.11 (Randers gradient, two equivalent forms).** For `λ > 0` and `v ≠ 0`,
> ```
> ∇F(v)  =  ( v − F(v)·c ) / s                                               (6.21)
>        =  n(v) / ( V_s + ⟨n(v), c⟩ )                                       (6.22)
> ```
> where `n(v)` is the unit **through-water** heading that realises `v`, i.e.
> `v = F(v)·(V_s n(v) + c)`. Moreover `s = F(v)·V_s·(V_s + ⟨n(v),c⟩) > 0`.

**Proof.** `F = (s − a)/λ` with `a = ⟨v,c⟩`, `D = |v|²`. Then `∂a/∂v = c`, `∂D/∂v = 2v`, and
`∂s/∂v = (a c + λ v)/s`. So
`∇F = [ (a c + λ v)/s − c ] / λ = [ (a/s − 1) c + λ v/s ] / λ = v/s + (a − s) c/(λ s)`.
Since `(a − s)/λ = −F`, this is `(v − F c)/s`, which is (6.21).

For (6.22): by definition of the gauge, `v/F ∈ ∂D(c, V_s)`, i.e. `v = F(V_s n + c)` for a unit
`n`. Then `v − F c = F V_s n`. Compute `s`: with `b := ⟨n, c⟩` and `C := |c|²`,
`a = F(V_s b + C)`, `D = F²(V_s² + 2V_s b + C)`, so
```
a² + λD = F²[ (V_s b + C)² + (V_s² − C)(V_s² + 2V_s b + C) ]
        = F²[ V_s²b² + 2V_s bC + C² + V_s⁴ + 2V_s³b + V_s²C − CV_s² − 2V_s bC − C² ]
        = F²[ V_s²b² + 2V_s³b + V_s⁴ ]  =  F² V_s² (V_s + b)²
```
so `s = F V_s (V_s + b)` (positive, since `|b| ≤ |c| < V_s` when `λ > 0`). Dividing
`v − F c = F V_s n` by `s` gives `n/(V_s + b)`, which is (6.22).
*Consistency check (Euler).* `⟨∇F, v⟩ = ⟨n, F(V_s n + c)⟩/(V_s+b) = F(V_s + b)/(V_s+b) = F` ✓,
as 1-homogeneity requires. ∎

**Which form to compute.** (6.21) is the one to implement: it needs only `v`, `F` (already
computed), `c` and `s = sqrt(a² + λD)` — and for `λ ≥ 0` that square root adds two
**non-negative** quantities, so it carries no cancellation at all. (6.22) is the one to *think*
with: it says the sensitivity of the metric to a displacement is the through-water heading
divided by the speed made good along that heading — the transversality condition in disguise.

**The sign-stable residual.** A bracketed root find on `A'` needs only the **sign** of `A'` to
be correct. Multiplying (6.19) by `s > 0` removes the division entirely:

```
R(ζ)  :=  ΔT · s(ζ)  −  ⟨e, v(ζ)⟩  +  F(ζ) · ⟨e, c⟩ ,        sign A' = sign R  (6.23)
```

Use `R` for all bracket decisions and `A'` itself only for the Newton step length. This matters
because `⟨e,v⟩ − F⟨e,c⟩` can cancel — it vanishes exactly at the stationary point of `F` alone
— and near-cancellation in a *quantity whose sign is being tested* is the one place where a
lost digit changes the answer rather than merely blurring it.

```
Proc 6.3c  safeguarded_newton_on_A(zlo, zhi, R, A', A'') -> zeta
Precondition: R(zlo) <= 0 <= R(zhi)   (A convex => R non-decreasing => bracket is valid)
 1  z <- 0.5*(zlo + zhi)
 2  for 1 .. N_NEWT                                    # N_NEWT = 24
 3      r <- R(z)
 4      if r <= 0 : zlo <- z  else  zhi <- z
 5      if zhi - zlo <= tol_zeta : break
 6      d <- A''(z)
 7      z_new <- z - A'(z)/d   if d > 0  else  +INF
 8      if not (zlo < z_new < zhi) : z_new <- 0.5*(zlo + zhi)     # safeguard
 9      z <- z_new
10  return 0.5*(zlo + zhi)
```

> **Lemma 6.12 (safety of Proc 6.3c).** If `A` is convex on `[zlo, zhi]`, then `A'` is
> non-decreasing, so `R` is non-decreasing, so the sign test at line 4 preserves the bracket
> `R(zlo) ≤ 0 ≤ R(zhi)`. Line 8 forces every iterate into the open bracket. Therefore the
> bracket is nested, non-increasing, and contains a stationary point at every step; and since
> line 8 substitutes a bisection whenever Newton leaves the bracket, the width is at least
> halved on every iteration in which Newton fails, giving the same worst-case guarantee as
> Proc 6.1a.

**Proof.** Convexity gives monotone `A'`, hence monotone `R` by (6.23) and `s > 0`. A monotone
function with `R(zlo) ≤ 0 ≤ R(zhi)` has a sign change in the bracket; replacing whichever
endpoint has the matching sign preserves that. The safeguard is by construction. ∎

**When Newton is NOT safe — the exact list.**

1. **Ground-frame solves.** By Corollary 6.9.1, `A` is convex only up to (6.17); `A'` need not
   be monotone, and Lemma 6.12's precondition fails. **Use golden section.**
2. **Ban boundaries crossed within the segment.** Where a seakeeping ban (S1–S7,
   IMO MSC.1/Circ.1228 thresholds) switches inside the swept `ζ`-range, `F` is only lower
   semicontinuous (`Remark 3.1.3`); `A'` does not exist there. The infimum is still attained
   and (U1)/(U2) are unaffected, but Newton has nothing to converge to. **Use golden section**;
   Lemma 6.10 still applies on each side of the jump, and the correct treatment is to split the
   admissible interval at the crossing if it can be located, else to accept golden section's
   answer on the whole interval.
3. **Throttle switching (D1).** When the arg-max throttle changes with `ζ` — which it does
   whenever a ban is active at high `q` but not at low `q` — `A` has a kink. Same remedy.
4. **Non-strictly-convex indicatrix.** `A'' = 0` on a flat face; line 7 detects `d ≤ 0` and
   bisects.
5. **Endpoints.** `A'` is one-sided at `ζ ∈ {0,1}`; the bracket must be established with `R`
   evaluated *inside* the admissible interval returned by Proc 6.3a.

**Normative rule.** Use safeguarded Newton **only** when all of: the solve is co-moving; the
metric is the Randers closed form; no ban is active anywhere on the admissible `ζ`-interval;
`λ > 0` throughout. Otherwise use golden section. Implementations that cannot cheaply test the
ban condition must use golden section unconditionally — it is correct in every case and costs
a factor of about two.

### 6.3.6 The numerically stable closed form for the Randers case

Assemble. Given `x`, the edge `(x_j, x_k)`, the labels `(T_j, T_k)`, the local effective drift
`c` and speed `V_s`, all in the local frame:

```
Eq (6.24)   p  = x − x_k                    e  = x_j − x_k              ΔT = T_j − T_k
Eq (6.25)   P2 = ⟨p,p⟩   PE = ⟨p,e⟩   E2 = ⟨e,e⟩   PC = ⟨p,c⟩   EC = ⟨e,c⟩   λ = V_s² − |c|²

            D(ζ) = P2 − 2ζ·PE + ζ²·E2                       (= |v(ζ)|²)
            a(ζ) = PC − ζ·EC                                (= ⟨v(ζ),c⟩)
            s(ζ) = sqrt( a(ζ)² + λ·D(ζ) )

Eq (6.26)   F(ζ) = D(ζ) / ( a(ζ) + s(ζ) )         if a(ζ) > 0        [conjugate branch]
                 = ( s(ζ) − a(ζ) ) / λ            if a(ζ) ≤ 0 and λ > 0
                 = +INF                           if a(ζ) > 0 and a²+λD < 0   [Kropina cone]
                 = +INF                           if a(ζ) ≤ 0 and λ ≤ 0

Eq (6.27)   A(ζ) = T_k + ζ·ΔT + F(ζ)
Eq (6.28)   R(ζ) = ΔT·s(ζ) − ( PE − ζ·E2 )·(−1) … see below
```

`⟨e, v(ζ)⟩ = ⟨e, p − ζe⟩ = PE − ζ·E2`, so (6.23) becomes, fully expanded and division-free:

```
R(ζ)  =  ΔT · s(ζ)  −  ( PE − ζ·E2 )  +  F(ζ) · EC                           (6.28)
```

`D`, `a` and `s` are polynomials of degree ≤ 2 in `ζ` evaluated by Horner; `F` is one branch
and one square root; `A` and `R` are then two more flops each. **Total per `A`-evaluation in
the Randers fast path: one `sqrt`, one divide, about 20 flops** — which is why the fast path
exists, and why `N_GS = 32` is affordable.

**The branch on the sign of `a` is not optional.** It is golden vector **G3**, and it is the
single most-tested line in the reference implementation. Reproducing the textbook single-branch
form `F = (sqrt(a² + λD) − a)/λ` is a defect: see §6.6.1 for the derivation of exactly how many
digits it throws away and where.

**Sanity identity for a port.** At `ζ` such that `v(ζ)` is a pure following-current direction
with `V_s = 7.2, |c| = 6.48`, (6.26) must give `F = 1/13.68 = 0.073 099 415 204 678 362…`
(G3). At `V_s = 7.2` with `c∥ = +1.5, c⊥ = 0`, `σ = 8.7` and `F = 0.114 942 528 735 632` (G2
T2). These are the two values a broken branch gets wrong in opposite directions.

### 6.3.7 The outer minimisation and the causality clamp

Proc 6.3 returns `inf_{ζ ∈ admissible} A(ζ)`. That value feeds the **three-rule decomposition**
of `Eq (3.24)`, not the node update directly:

```
ρ_k    : S = {x_k} ,        A_{ρ_k}    = A(0)                                (3.24a)
ρ_j    : S = {x_j} ,        A_{ρ_j}    = A(1)                                (3.24b)
ρ_{jk} : S = {x_j, x_k} ,   A_{ρ_{jk}} = max{ inf_{ζ∈(0,1)} A(ζ) , max(T_j,T_k) + δ }  (3.24c)
```

with clamp margin `δ = Δ_min = c_geo·h·F_min` (no new constant). Numerically:

- `A(0)` and `A(1)` are **not** obtained from the `ζ`-search; evaluate them directly. They are
  the informative rules when one label is `+∞` (`Remark 3.C.2`) and they are never clamped.
- The `max` at (3.24c) must be applied **after** the minimisation, never inside the objective:
  clamping inside would make `A` non-convex and void Lemma 6.9.
- Instrument the **clamp firing rate**. `Remark 3.C.1` proves the per-update perturbation is
  `O(h)` but explicitly labels the aggregate along a route a **Conjecture**. The firing rate is
  the measurement that stands in for the missing proof; report it.

**Instrumentation (normative, from `handbook/02-debugging-playbook.md` S3).** Log the
**distribution of the returned `ζ`**. If it is bimodal at the endpoints `{0, 1}`, the inner
minimiser is broken or is being skipped, and the scheme has silently degenerated to a
fixed-neighbour stencil — whose consistency error does **not** vanish as `h → 0` but converges
to a fixed `O(1/m²)` angular quantisation bias. That is precisely the measured `~1 %`
metrication floor of `CORE-THEOREM.md §4`, which did **not** converge under refinement across
`h = 24, 16, 12, 8, 6, 4, 3 km` (`0.36, 0.15, 0.79, 0.92, 0.17, 0.98, 0.58 %`). A plateau in
the refinement study with an endpoint-pinned `ζ` histogram is a diagnosis, not a mystery.

---

## Proc 6.4 — Environmental interpolation

**Owns:** primitive `sample_env(x, t) -> Env` (`CONTRACT.md §4`).

### 6.4.1 What the solver is entitled to assume

`sample_env` is called from inside a monotone label-setting sweep whose correctness proof
(`Thm 3.1`) evaluates the same `(x, t)` from several front edges and **assumes it gets the same
answer every time**. Three obligations follow, and they are the whole specification of this
primitive:

| Obligation | Why the algorithm needs it |
|---|---|
| **O1 — Determinism.** Same `(x,t)` ⟹ bit-identical `Env`, with no hidden state, no cache eviction that changes a value, no thread-dependent ordering. | The causality argument of `Thm 3.1` and the label-setting invariant both assume `F` is a function. A field with hidden state breaks the algorithm **silently**. |
| **O2 — Range preservation.** Every interpolated component lies within the range of the data nodes that produced it. | `|c| < V_max` (`ERRATA E1`, `Eq (C.7)`) is the admissibility test the whole metric branches on. An interpolant that manufactures a value outside the data range manufactures cells the ship cannot escape. |
| **O3 — Computable Lipschitz constants.** `L_x` and `L_t` must be bounded by difference quotients of the *data*, not of an interpolant. | `L_t` is the causality diagnostic (`ERRATA E4.1`, `r(x)·L_t ≤ 1`) and the quantity `Eq (C.10)` minimises to choose `w`. A diagnostic computed from an interpolant with unbounded derivative is not a licence. |

**Trilinear interpolation on the `(t, lat, lon)` lattice is the normative choice** because it
is the highest-order scheme that satisfies all three. §6.4.4 proves it does; §6.4.5 shows what
breaks when higher order is used anyway.

### 6.4.2 Proc 6.4 — procedure

```
Proc 6.4  sample_env(lat, lon, t) -> (Env, flags)
Input : lat, lon [rad], t [s]
Output: Env (all SI, local east/north frame) + provenance flags
Complexity: O(1); 8 lattice reads and 7 fused multiply-adds per scalar component.

 1  # --- axis location, each O(1) for a uniform axis, O(log n) for a rectilinear one ---
 2  (i, fx) <- locate(lat_axis, lat)     # i in [0, n_lat-2], fx in [0,1]
 3  (j, fy) <- locate(lon_axis, lon_shifted)     # see 6.4.3 for lon_shifted
 4  (k, ft) <- locate(t_axis,  t)
 5  clamped_space <- (lat or lon outside its axis)
 6  clamped_time  <- (t outside [t0, horizon])
 7  beyond_horizon<- (t > horizon)
 8  # --- trilinear blend, per SCALAR component ---
 9  for each scalar component s in {hs, tp, depth, ...}:
10      s <- SUM over (di,dj,dk) in {0,1}^3 of
11               w(di,fx)*w(dj,fy)*w(dk,ft) * S[i+di, j+dj, k+dk]
12           where w(0,f) = 1-f, w(1,f) = f
13  # --- vector components: interpolate COMPONENTS, never magnitude+angle ---
14  (cu, cv) <- trilinear of the east and north components separately
15  (wu, wv) <- trilinear of the east and north components separately
16  # --- directional scalars: interpolate the (cos, sin) PAIR, recover by atan2 ---
17  (mx, my) <- trilinear of (cos mu_w, sin mu_w) stored as two arrays
18  mu_w     <- atan2(my, mx)             # see 6.4.7 for the (0,0) case
19  return (Env{...}, flags)
```

**Line 14 is normative and is a common porting error.** Interpolating a current or wind as
`(|c|, direction)` and recombining is wrong twice over: the direction wraps (see line 17), and
the magnitude of an average is not the average of magnitudes, so a `180°` shear across a cell
interpolates to a *finite* current where the true field passes through zero. Interpolating
components gives the correct zero crossing and is what the linearity of the momentum field
means physically.

**Line 17 is normative for `μ_w`.** A wave direction stored as an angle interpolates through
the `±π` seam catastrophically: `μ_w = 179°` and `μ_w = −179°` average to `0°`, i.e. waves
from exactly the opposite side. Storing and interpolating `(cos μ_w, sin μ_w)` costs one extra
array and removes the seam entirely. The recovered vector is not unit-length — it is shortened
where the directions disagree, which is the correct behaviour (directional spread reduces the
coherent forcing) — so **do not renormalise before using it as a weight**; renormalise only
when an angle is required.

**Convention, fixed once (`types.py`):** `μ_w` is the direction the waves are travelling
**towards**, radians, `0 = north`, clockwise. Meteorological data is published as "from". The
conversion happens at the data boundary and **never again**. Mixing the two is a `180°` error
that looks entirely plausible on a map; the discriminating test is
`handbook/02-debugging-playbook.md` **S2**: with `H_s = 6 m` and `μ_w` due north, a ship
steaming due north is in **following** seas and must lose the **least** speed.

### 6.4.3 The longitude seam and the shifted frame

**Normative:** store the longitude axis internally as a **strictly ascending unwrapped**
sequence, whose origin is chosen so the domain does not straddle the seam, and apply `wrap_pi`
only at the I/O boundary. A query longitude is mapped into that frame once, on entry.

With this, a domain crossing the antimeridian is an ordinary interior interpolation with no
special case, the seam cell between columns `n−1` and `0` of a global grid is interpolated like
any other, and — critically — the per-row geometry cache of §6.8 becomes valid. Without it,
every longitude arithmetic operation in the solver needs its own `wrap_pi`, and the two places
that were missed are documented in §6.8.5 and §6.8.6.

### 6.4.4 Lemma 6.13 — multilinear interpolation satisfies O1–O3

> **Lemma 6.13.** Let `S` be data on a rectilinear lattice and `S_h` its multilinear
> interpolant on a cell with corner set `C` (`|C| = 2^d`). Then
> **(a)** `S_h(z) = Σ_{γ∈C} ω_γ(z) S_γ` with `ω_γ(z) ≥ 0` and `Σ_γ ω_γ(z) = 1`; hence
> `min_{γ∈C} S_γ ≤ S_h(z) ≤ max_{γ∈C} S_γ` — **no new extrema** (O2).
> **(b)** `|∂S_h/∂z_m|` is bounded by the maximum over the `2^{d−1}` edge difference quotients
> of the data in direction `m` — the interpolant's Lipschitz constant in each axis is bounded
> by the data's own (O3).
> **(c)** `S_h` is computed by a fixed sequence of `+` and `×` with no data-dependent
> branching, hence bit-deterministic for a fixed evaluation order (O1).

**Proof.** **(a)** By construction `ω_γ(z) = Π_{m=1}^{d} w(γ_m, f_m)` with
`w(0,f) = 1−f`, `w(1,f) = f`, `f_m ∈ [0,1]`. Each factor is in `[0,1]`, so `ω_γ ≥ 0`. And
`Σ_{γ∈C} ω_γ = Π_{m=1}^{d} [ (1−f_m) + f_m ] = 1` by distributing the product over the sum
(this is exactly the multinomial expansion). A convex combination of points lies in their
convex hull, which for scalars is `[min, max]`.

**(b)** Fix `m` and differentiate: only the factor `w(γ_m, f_m)` depends on `f_m`, with
`∂w(0,f)/∂f = −1`, `∂w(1,f)/∂f = +1`. Grouping the `2^d` corners into `2^{d−1}` opposite pairs
`(γ⁻, γ⁺)` differing only in coordinate `m`,

```
∂S_h/∂f_m  =  Σ_{pairs}  ω̃_pair(z) · ( S_{γ⁺} − S_{γ⁻} )
```

where `ω̃_pair = Π_{m'≠m} w(γ_{m'}, f_{m'}) ≥ 0` and `Σ_{pairs} ω̃_pair = 1` by the same
argument as (a). So `∂S_h/∂f_m` is a convex combination of the `2^{d−1}` edge differences and
is bounded by the largest of them in absolute value; dividing by the axis spacing `Δz_m` gives
the difference quotient statement.

**(c)** Immediate: (a)'s formula has no branch on the data. Determinism across *runs on one
platform* follows; determinism across platforms additionally requires a fixed summation order,
which §6.10 makes normative. ∎

**Corollary 6.13.1.** With `d = 3` (time, lat, lon), trilinear interpolation of a current field
cannot produce `|c| > max over the 8 corners of |c|`… **but note the sharpening this needs**:
(a) bounds each *component*, and `|c| = hypot(c_E, c_N)` is a convex function of the
components, so `|c_h| ≤ max_γ |c_γ|` follows from convexity of the norm applied to a convex
combination (Jensen). So the magnitude bound does hold, and the admissibility test
`|c₀ − w| < V_max` of `Eq (C.7)` can never be triggered by interpolation alone. This is the
concrete form of obligation O2 and it is the reason O2 is stated at all.

### 6.4.5 Why higher-order interpolation of the FIELDS is unsafe

Two distinct failures. Be precise about which is which, because the loose version of this
claim ("higher order breaks monotonicity of the scheme") is not correct as stated.

**Failure 1 — overshoot manufactures physics that is not in the forecast.** This is the real
one. Any interpolant with negative weights is not a convex combination and violates O2. The
Catmull-Rom / cubic-convolution kernel (**Keys 1981**) with `a = −½` has taps

```
w₋₁ = −0.0625 ,  w₀ = +0.5625 ,  w₁ = +0.5625 ,  w₂ = −0.0625     (at the cell midpoint)
```

Two of the four are negative. On the data `(1, 1, 1, 0)` the midpoint value is
`−0.0625·1 + 0.5625·1 + 0.5625·1 − 0.0625·0 = 1.0625` — a **6.25 % overshoot above the global
maximum of the data**. Now instantiate that in the metric:

> A drift magnitude stepping from `0` to `6.8 m/s` across a front, with `V_s = 7.2 m/s`,
> overshoots to `6.8 × 1.0625 = 7.225 m/s > V_s`. So `λ = V_s² − |c|² < 0`, the Kropina branch
> of (6.26) fires, and the metric declares a **one-sided cell with a forbidden cone**
> (`ERRATA E1.1`) at a location where **no forecast node says the ship is outrun**.

The solver then routes around a storm the forecast does not contain. It converges, the route is
plausible, and it is wrong — the exact failure class `handbook/02-debugging-playbook.md` S4
identifies as the most dangerous. The same overshoot drives `H_s` above `hs_limit` and
manufactures spurious S7 bans, and drives `H_s` **below zero** on the other side of a front,
where `sqrt` and the STAwave-1 form both need a non-negative argument.

**Failure 2 — the Lipschitz constants stop being measurable.** `L_t` is estimated from the
forecast stack and is the licence for the whole single-pass solve (`ERRATA E4.1`) and the
objective `Eq (C.10)` minimises to choose `w`. Lemma 6.13(b) is what makes an estimate from
data differences a *bound*. A cubic spline's derivative can exceed the data's own difference
quotients without bound (the Runge phenomenon in derivative form), so `L_t` estimated from the
frames understates the interpolant's actual temporal Lipschitz modulus, and the reported
causality margin is not a margin. Note the consequence is one-sided and therefore worse: the
diagnostic reports **green** on fields where the sweep is not licensed — the same defect
`ERRATA E4` corrects at a different level.

**What is NOT the failure.** Barles–Souganidis (1991) monotonicity is a property of the update
operator in its arguments `T_j`, and interpolation of the *field* does not enter it: `F` may be
any function of `(x,t,u)` and the scheme remains monotone. Saying "higher-order interpolation
breaks scheme monotonicity" is imprecise. What it breaks is the **discrete maximum principle
of the field** (O2) and the **measurability of the constants** (O3), and those are enough.

**The safe way to get higher order in the fields, if it is ever wanted.** Use a
**monotonicity-preserving** limited interpolant — Fritsch & Carlson (1980) monotone cubic
Hermite per axis — which restores `O(h³)` accuracy on smooth data while guaranteeing no new
extrema. The price is that the interpolant is `C¹` but not `C²` and its derivative has kinks,
so any procedure that differentiates the field (the Zermelo polish, `Prop 3.5`, needs
`∂c/∂x`) must use the *unlimited* derivative or accept the kinks. **Not implemented; noted as
available and safe.**

### 6.4.6 What IS safe to interpolate at higher order — the exact list

| Object | Safe order | Why |
|---|---|---|
| **The arrival-time field `T`** for sub-cell goal location, backtracking and route densification | bilinear normative; higher order permitted **for display only** | `T` is not fed back into the update, so O2 and O3 do not apply to it. But near a shock (a cut locus, `S8`) `T` is only Lipschitz, so higher order buys nothing there and can overshoot across the shock. Normative: bilinear. |
| **The route polyline in time** | any order | Under Thm C.1(d) the ground route is `x(s) = y(s) + w·τ(s)` **exactly** — an affine map of the co-moving route. Densifying it introduces no model error at all. This is a direct consequence of the reduction. |
| **The vessel speed–power curve `calm_power(V)`** | **monotone** cubic (Fritsch–Carlson 1980) | Proc 6.1's definition (6.3) is well-posed for non-monotone curves but its `N_SCAN` limitation is not. A monotone interpolant through sea-trial points guarantees a single root and removes the limitation. A *natural* cubic spline is **not** monotone and must not be used. |
| **The SFOC bowl `sfoc(P)`** | any smooth interpolant | It is a rate multiplier, not a constraint; it enters no branch and no admissibility test. Its only requirement is a genuine interior minimum near `q ≈ 0.75`, without which the Pareto front collapses to a line (`S5`). |
| **The support-function table over the DIRECTION index** (D2, `n_θ = 72`) | refine by the **inscribed-polygon max**, `max_k σ(u_k)·⟨u_k, p⟩` | This is exact by duality for convex `𝒱` (`Prop 2.7`) and is always a **lower** bound on `h_𝒱`, which is the safe sign for a Hamiltonian: it can never overstate what the ship can do. Trigonometric interpolation of `h` between samples has no such sign guarantee. With bans active `𝒱` is non-convex, the sampled objective need not be unimodal, and golden-section refinement may polish a local maximum — the sampled max is still correct to `O((π/n_θ)²)` because `h_𝒱 = h_{conv 𝒱}` (D4), so only the refinement's benefit is lost, never the bound. |
| **Bathymetry `d_b` for the navigability mask** | **do not interpolate — take the cell minimum** | A mask must be conservative. Interpolating depth and thresholding opens shoals that the data closes. Taking `min` over the cell (equivalently, dilating land) is the same admissibility argument as design decision **D5**. Note the countervailing failure this cannot fix: at `h ≈ 0.25°` a strait narrower than one cell is topologically **closed** by any mask and an optimal route is lost silently. That is a correctness failure no interpolation order touches; the mitigation is a separate high-resolution channel graph, out of scope here. |

### 6.4.7 Degenerate inputs to Proc 6.4

| Input condition | Defined behaviour |
|---|---|
| `t` outside `[t0, horizon]` | Clamp to the nearest frame; set `clamped_time`; additionally set `beyond_horizon` if `t > horizon`. **Persistence of the final frame is the normative convention** (`ERRATA E5`). See §6.7 D14 for the consequences. |
| `(lat, lon)` outside the domain | Clamp to the boundary and set `clamped_space`. Do **not** raise: the caller usually wants the closest legal sample, and a raise inside the sweep's inner loop is unrecoverable. |
| A NaN or a fill value in the source data | **Must be resolved at ingest, not at sample time.** Replace with a documented fill policy (nearest valid neighbour, or the climatological value) and record the count in the run log. A NaN reaching (6.26) propagates to `F`, and a NaN `F` compares `false` against every threshold, so a banned direction silently becomes admissible. |
| `H_s = 0` exactly | Legal and common. Added resistance in waves is `0`; `μ_w` is undefined and **must not** be allowed to produce a NaN. See D8 in §6.7. |
| `T_p = 0` or missing | `ω_p := 2π / max(T_p, 1e-3)`. The floor is a guard, not physics; it caps `ω_p` at `6283 rad/s`, which multiplied by `H_s = 0` contributes nothing. Flag the cell. |
| All 8 corners identical | Returns that value exactly (the weights sum to `1` and the summation of equal terms is exact only if the order is fixed — see §6.10). |

### 6.4.8 The time axis, and why it usually is not there

Under Thm C.1(b) the co-moving field is a **single snapshot**: `CoMovingField.at(lat, lon, t)`
ignores `t` entirely, and its `horizon` is `+∞`. Proc 6.4 therefore degenerates to **bilinear**
in `(lat, lon)` for the whole of the main solve — 4 lattice reads instead of 8, and, far more
importantly, **zero temporal sampling error**. `CORE-THEOREM.md §4` measures the difference:
the ground-frame solve required `V_req = 7.006 721 m/s` against a capability of `7.0`, an
excess of `6.7e-3 m/s` caused by sampling the advected field at the leg midpoint being only
first-order accurate in *time* as well as space; the co-moving solve's excess was `2.8e-14`.

The time axis returns only for algorithm step 6, the residual corrector, where the field is
`R(x,t) = E(x,t) − E₀(x − wt)` of `Eq (C.8)`. There, all of §6.4.1–§6.4.7 applies in full.

---

## Proc 6.5 — Spherical geometry

**Owns:** distance, bearing, forward geodesic, and the local-frame conversion of
`ERRATA (E8.1)`. Angles are **radians everywhere inside the solver**; degrees appear only at
the I/O boundary. `R_E = 6 371 000.0 m` exactly (IUGG mean radius).

### 6.5.1 Distance — Proc 6.5a

```
Proc 6.5a  haversine(lat1, lon1, lat2, lon2) -> metres
 1  dlat <- lat2 - lat1
 2  dlon <- wrap_pi(lon2 - lon1)                       # antimeridian-safe, MANDATORY
 3  s1 <- sin(0.5*dlat) ;  s2 <- sin(0.5*dlon)
 4  a  <- s1*s1 + cos(lat1)*cos(lat2)*s2*s2
 5  a  <- min(1, max(0, a))                            # guard rounding above 1 / below 0
 6  return 2*R_E*asin(sqrt(a))
```

Line 2 is not optional and line 5 is not cosmetic: without the clamp, `asin` of `1 + 1e-16`
returns NaN on a conforming libm, and a NaN distance propagates into a leg cost that compares
`false` against every bound.

### 6.5.2 Lemma 6.14 — the law-of-cosines pitfall, quantified

The spherical law of cosines computes `δ = arccos(x)` with
`x = sin φ₁ sin φ₂ + cos φ₁ cos φ₂ cos Δλ`.

> **Lemma 6.14.** With `x` formed by three correctly rounded operations on quantities of
> magnitude `≤ 1`, `|Δx| ≲ 4u`. Since `dδ/dx = −1/sqrt(1−x²) = −1/sin δ`, the absolute error in
> the recovered angle is `|Δδ| ≈ 4u / sin δ`, and the **relative** error in the distance is
> ```
> |Δδ| / δ  ≈  4u / (δ sin δ)  ≈  4u / δ²      for small δ                   (6.29)
> ```

**Proof.** The three terms of `x` are each products of quantities bounded by 1, so each carries
absolute rounding `≤ u` plus the rounding of the sum, giving `|Δx| ≤ 4u` to leading order; no
cancellation occurs because both terms are of magnitude `≤ 1` and their sum is `≤ 1` (the sum
is not near zero for near-coincident points — it is near **one**, which is a subtraction from 1
only implicitly and therefore introduces no additional cancellation beyond the `4u` already
counted). Differentiating `arccos` gives the stated propagation, and `sin δ ≈ δ` for small
`δ`. ∎

**The numbers, with `u = 1.11e-16`, `4u = 4.44e-16`, `δ = d/R_E`:**

| separation `d` | `δ` [rad] | relative error `4u/δ²` | significant digits |
|---|---|---|---|
| 10 m | `1.570e-6` | `1.80e-4` | ≈ 3.7 |
| 100 m | `1.570e-5` | `1.80e-6` | ≈ 5.7 |
| 1 km | `1.570e-4` | `1.80e-8` | ≈ 7.7 |
| 28 km (0.25° grid) | `4.395e-3` | `2.30e-11` | ≈ 10.6 |
| 100 km | `1.570e-2` | `1.80e-12` | ≈ 11.7 |

> **Correction to a claim in the reference implementation.** `geodesy.py`'s docstring says the
> law of cosines "loses **all** precision for separations below ~1 km". Lemma 6.14 says it
> retains about **7.7 significant digits at 1 km** and about **10.6 at grid scale**. The
> docstring overstates the failure. The two real reasons haversine is nevertheless **normative**
> are precise and survive the correction:
> 1. `handbook/01-golden-vectors.md` requires agreement to **12 significant figures**. At grid
>    scale the law of cosines delivers ~10.6 and therefore **fails the acceptance criterion**,
>    while haversine delivers a few ulp.
> 2. Sub-100 m separations **do** occur — in the Zermelo shooting polish's RK4 substeps, in
>    route densification, and in the `O(N)` goal scan when a node's mapped landfall is nearly on
>    top of `x_B` — and there the law of cosines is down to 4–6 digits, which is a genuine
>    failure.

**Haversine's own conditioning.** In line 4 every term is non-negative, so no cancellation
occurs at any separation. The error is a few `u` relative for small `δ`. It degrades only for
**near-antipodal** pairs, where `a → 1` and `asin` steepens: relative error
`≈ u/sqrt(1−a) = u/|cos(δ/2)|`. At `d = 19 900 km` (`π − δ ≈ 0.005`), `cos(δ/2) ≈ 2.5e-3`, so
the error is `≈ 4.4e-14` rad `≈ 2.8e-7` m. Negligible for every use in KAIROS, including the
`O(N)` goal scan. If antipodal accuracy is ever needed, use the sphere-specialised **Vincenty
(1975)** formula, which is stable at both ends; it costs one extra `atan2` and two extra
multiplications.

### 6.5.3 Bearing — Proc 6.5b

```
Proc 6.5b  initial_bearing(lat1, lon1, lat2, lon2) -> radians, 0 = north, clockwise
 1  dlon <- wrap_pi(lon2 - lon1)
 2  cl2  <- cos(lat2)
 3  y <- sin(dlon) * cl2
 4  x <- cos(lat1)*sin(lat2) - sin(lat1)*cl2*cos(dlon)
 5  if y == 0 and x == 0 : return 0.0        # coincident or antipodal; see 6.7 D11
 6  return atan2(y, x)
```

**The arccos form is the pitfall.** Recovering a bearing as `arccos` of a normalised inner
product is unstable at **both** `0` and `π` — exactly the two bearings a routing grid uses most
(due north and due south are two of the sixteen stencil offsets) — for the same reason as
Lemma 6.14, with `1/sin` amplification at each end. `atan2` is well conditioned everywhere the
arguments are not both zero, and line 5 defines the one place they can be.

**Small separations.** Unlike distance, bearing has **no** small-separation degradation in the
`atan2` form: `y` and `x` both scale linearly with the separation, so their ratio is
well-determined and `atan2` is scale-invariant. Precision is limited only by the `O(u)` errors
in `sin`/`cos`, giving `O(u)` radians absolute. This is worth stating explicitly because the
intuition transferred from Lemma 6.14 — "short legs are badly conditioned" — is **false for
bearings** and leads implementers to add unnecessary special cases.

### 6.5.4 The local frame and the tangent-plane error

`ERRATA (E8)` fixes the convention: **`ẋ` denotes the components of the ground velocity
resolved in the local orthonormal frame `(𝐞_E, 𝐞_N)`, in m/s.** The chart conversion
`Eq (E8.1)` is applied **at the chart boundary only**; the solver runs entirely in the frame,
and exactly one module owns the conversion.

```
Proc 6.5c  local_step_metres(lat, dlat, dlon) -> (east_m, north_m)
 1  return ( R_E * cos(lat) * wrap_pi(dlon) ,  R_E * dlat )

Proc 6.5d  metres_to_dlatlon(lat, east_m, north_m) -> (dlat, dlon)
 1  cl <- cos(lat)
 2  if |cl| < EPS_COS = 1e-9 : return (north_m/R_E, 0.0)     # polar cap: lon is meaningless
 3  return ( north_m/R_E , east_m/(R_E*cl) )
```

**Error of the tangent-plane treatment, derived.** The chord–arc relative difference for a
separation `d` is `(d/R_E)²/24` to leading order (`arc = 2R asin(chord/2R)` expanded). At
`h = 28 km`: `(28e3/6.371e6)² = 1.931e-5`, divided by 24 gives `8.05e-7` relative, i.e.
**2.25 cm** on a 28 km leg. That is four orders below the metric's own modelling error, so the
solver **may treat the local frame as exactly Euclidean within one cell**, which is what the
stencil construction assumes.

**`cos(lat)` is evaluated at the ROW latitude**, which is why the leg-geometry cache of §6.8 is
per-row. That cache is also where the indexing trap lives.

### 6.5.5 Lemma 6.15 — the local frame is NOT safe for the co-moving shift

The co-moving map `x = y + w·t` (`Eq C.5`) and its inverse are applied with displacements of
`|w|·t`, which is **not** a cell-scale quantity: `CORE-THEOREM.md §8.1 R1` requires the grid to
be dilated by `|w|·t_max`, measured at `≈ 500 km` for a 140 h voyage with `w = (1,1) m/s`, and
the end-to-end run of §8.2 has `w = (3,1) m/s` over `t* = 139.9963 h`, giving
`|w|·t* ≈ 1 590 km`. Applying Proc 6.5d at that magnitude is a first-order approximation used
far outside its regime.

> **Lemma 6.15.** Let a point at latitude `φ` be displaced by `(E, N)` metres using Proc 6.5d,
> i.e. `Δφ = N/R_E`, `Δλ = E/(R_E cos φ)`. The eastward arc actually traversed at the
> destination latitude `φ + Δφ` is `R_E cos(φ+Δφ)·Δλ = E·cos(φ+Δφ)/cos φ`, so the relative
> error in the east displacement is
> ```
> | E_actual − E | / E  =  | cos(φ+Δφ)/cos φ − 1 |  ≈  |Δφ| · tan φ  =  (|N|/R_E)·tan φ  (6.30)
> ```

**Proof.** Expand `cos(φ+Δφ) = cos φ cos Δφ − sin φ sin Δφ ≈ cos φ − Δφ sin φ` for small `Δφ`;
divide by `cos φ` and subtract 1. ∎

**Applying (6.30) to the §8.2 run.** `w = (3.0, 1.0) m/s`, `t* = 503 987 s`, so
`E = 1.512e6 m`, `N = 5.04e5 m`, `Δφ = 0.0791 rad = 4.53°`, mean latitude `≈ 10.3°`
(`tan = 0.1817`). Then (6.30) gives `0.0791 × 0.1817 = 1.437e-2`, i.e. a **21.7 km** error in
the east component of the shift.

> **This is larger than the measured landfall miss of 11.2 km**, and that discrepancy must be
> reported rather than papered over. Three readings are consistent with the data and this file
> does not choose between them:
> (i) (6.30) is a crude worst-case that ignores partial cancellation — `ground_position` is
> applied per node at that node's own latitude, and the goal scan then *selects* the node whose
> mapped landfall is closest, which is precisely an operation that hides a systematic shift by
> picking a compensating node;
> (ii) part of the 11.2 km is ordinary grid snapping — half a grid diagonal at `0.25°` is
> `19.6 km`, so 11.2 km is **entirely consistent with snapping alone**;
> (iii) both contribute.
> **Status: the attribution is a Conjecture. What is missing is a controlled experiment** —
> re-run §8.2 with the shift computed by the exact spherical forward geodesic (Proc 6.5e) and
> report the change in the miss. Until that is run, no claim is made that (6.30) explains the
> measured miss; only that (6.30) is an error of the same order and is trivially removable.

> **Normative rule.** Compute the co-moving shift with the **exact spherical forward geodesic**
> (Proc 6.5e), i.e. `destination(lat, lon, bearing = atan2(E, N), dist = hypot(E, N))`, whenever
> `hypot(E, N) > D_shift`. Derive `D_shift` by requiring the (6.30) error to stay below a tenth
> of a cell: with `E ≈ N ≈ S/√2`,
> ```
> (S/√2)·(S/√2)/R_E · tan φ  ≤  0.1 h   ⟹   S² ≤ 0.2 h R_E / tan φ          (6.31)
> ```
> At `h = 28 km`, `φ = 20°` (`tan = 0.364`): `S² ≤ 0.2·2.8e4·6.371e6/0.364 = 9.80e10 m²`, so
> `S ≤ 313 km`. **`D_shift = 300 km` is normative**, rounded down. Since a routing-relevant
> `|w|·t` is routinely 5× that, **in practice the exact form is always used** and the
> tangent-plane shift should be reserved for cell-scale displacements only.

```
Proc 6.5e  destination(lat, lon, bearing, dist_m) -> (lat2, lon2)      # exact on the sphere
 1  ang <- dist_m / R_E
 2  sl, cl <- sin(lat), cos(lat) ;  sa, ca <- sin(ang), cos(ang)
 3  lat2 <- asin( clamp( sl*ca + cl*sa*cos(bearing), -1, +1 ) )
 4  lon2 <- lon + atan2( sin(bearing)*sa*cl , ca - sl*sin(lat2) )
 5  return (lat2, wrap_pi(lon2))
```

The `clamp` at line 3 is mandatory for the same reason as Proc 6.5a line 5. Proc 6.5e is also
what the Zermelo shooting polish integrates in, so that error does not accumulate over a
multi-thousand-kilometre route the way a tangent-plane march would.

### 6.5.6 Acceptance: the G1 golden values

These are **exact reference values** computed at 50-digit precision, not observed outputs.
Match to **12 significant figures** in IEEE double. Anything looser is hiding a bug; anything
tighter is asking for trouble from the last-bit behaviour of `sqrt`.

| From | To | Distance | Initial bearing |
|---|---|---|---|
| 0.00 N, 0.00 E | 0.00 N, 90.00 E | **10 007.543 398 010 3 km** | **90.000 000°** |
| 18.95 N, 72.95 E (JNPT) | 29.92 N, 32.55 E (Suez) | **4 243.611 km** | **294.619°** |
| 18.95 N, 72.95 E | 25.01 N, 55.06 E (Jebel Ali) | **1 961.706 km** | **293.284°** |
| 13.09 N, 80.29 E (Chennai) | 1.26 N, 103.85 E (Singapore) | **2 908.549 km** | **114.975°** |
| 9.96 N, 76.24 E (Kochi) | 12.79 N, 45.02 E (Aden) | **3 415.766 km** | **278.307°** |

**Self-check that catches most geodesy errors on its own.** Row 1 must equal `2πR_E/4` exactly:

```
2π · 6 371 000 / 4  =  π · 6 371 000 / 2  =  10 007 543.398 010 286 m         (6.32)
```

If it does not, the radius constant or the `asin` guard is wrong.

**Round-trip invariant**, tested at all five pairs:
`destination(A, initial_bearing(A,B), haversine(A,B)) == B` to `1e-9 rad ≈ 6 mm`. This
simultaneously exercises Proc 6.5a, 6.5b and 6.5e and is the cheapest test that catches an
east/north transposition in any one of them.

### 6.5.7 Poles and the dateline

**Dateline.** Fully handled by two mechanisms and nothing else is needed: `wrap_pi` on **every**
longitude difference (Proc 6.5a line 2, Proc 6.5b line 1, Proc 6.5c line 1), and the
shifted-longitude storage frame of §6.4.3. The two places the reference implementation misses a
`wrap_pi` are §6.8.5 (the leg midpoint) and §6.8.2 (the negative-column wrap).

```
Proc 6.5f  wrap_pi(a) -> a in (-pi, pi]
 1  a <- fmod(a, 2*pi)          # exact for the IEEE fmod; stable for large |a|
 2  if a >  pi : a <- a - 2*pi
 3  elif a <= -pi : a <- a + 2*pi
 4  return a
```

Do **not** implement this as `a − 2π·round(a/2π)`: that form loses digits proportional to
`|a|/2π` because `a/2π` is inexact, whereas IEEE `fmod` is **exact** (it is defined as the
exactly-rounded remainder). For a solver that accumulates longitudes over a 1 590 km co-moving
shift, the difference is measurable.

**Poles.** Three separate problems, only one of which is numerical:

1. **The local frame is undefined at `|φ| = π/2`** and ill-conditioned near it. Proc 6.5d
   guards `|cos φ| < EPS_COS = 1e-9` (i.e. `|φ|` within `5.7e-8` degrees of the pole) by
   returning a pure north step. This is a *guard*, not a solution.
2. **The lat/lon grid degenerates in longitude.** Cell width in longitude is `h·cos φ` while
   cell height stays `h`, so the grid contributes a **geometric** anisotropy of `1/cos φ` that
   has nothing to do with the physics. Setting this equal to the `ERRATA (E2)` heap-fallback
   threshold `Υ_heap = 12`:
   ```
   1/cos φ = 12   ⟹   φ = arccos(1/12) = 85.22°                              (6.33)
   ```
   So **above `|φ| ≈ 85.2°` the bucket queue must fall back to a heap for reasons of map
   projection alone**, before any current or wave has been considered. This is a derived
   consequence of E2 and is worth knowing before someone reports the fallback firing
   "spuriously" in an Arctic test.
3. **The stencil radius in columns blows up.** `r(x) ≤ Υ_loc·h` translates into
   `Υ_loc/cos φ` columns, which interacts with §6.8's `J_REF` requirement and with the domain
   width.

> **Normative:** restrict the solve domain to `|φ| ≤ φ_max = 80°` and **refuse** (return an
> explicit error, do not clamp) for a source or destination with `|φ| > φ_hard = 89.9°`. As
> `00-overview.md` L8 states, a latitude bound is a **modelling choice, not a theorem**;
> `80°` is chosen because `1/cos 80° = 5.76` keeps the purely geometric anisotropy comfortably
> under `Υ_heap = 12` with room for the physical anisotropy `(V_max+|c|)/(V_max−|c|)` on top.
> A polar solve needs a different chart (a polar stereographic patch), not a tighter tolerance.

---

## §6.6 — Floating point: cancellation, formula by formula

Every formula in the spec that can lose digits, where it loses them, and the reformulation.
The organising principle throughout: **a lost digit is harmless in a quantity that is averaged
and fatal in a quantity whose sign or whose branch is tested.**

### 6.6.1 The Randers gauge — the conjugate branch (golden vectors G2, G3)

The gauge of the disc `D(c, V_s)` is the smallest positive `τ` with `v/τ ∈ D`, i.e. the
smallest positive root of

```
φ(τ) := λ τ² + 2 a τ − D  ≥  0 ,     a := ⟨v,c⟩ ,  D := |v|² ,  λ := V_s² − |c|²   (6.34)
```

Roots `(−a ± sqrt(a² + λD))/λ`. The textbook form takes

```
F = ( sqrt(a² + λD) − a ) / λ                                    [UNSTABLE for a > 0]
```

> **Lemma 6.16 (digits lost by the textbook form).** For `a > 0` and `λD ≪ a²`, the subtraction
> `sqrt(a² + λD) − a` cancels with relative cancellation factor
> ```
> 1 − a/s  =  1 − 1/sqrt(1 + λD/a²)  ≈  λD / (2a²)                           (6.35)
> ```
> so the number of decimal digits lost is
> ```
> n_digits  ≈  log₁₀( 2a² / (λ D) )                                          (6.36)
> ```

**Proof.** `s = sqrt(a²+λD) = a sqrt(1+λD/a²)`. Subtracting two positive quantities whose ratio
is `a/s = 1/sqrt(1+λD/a²)` loses `−log₁₀(1 − a/s)` digits by the standard cancellation
estimate (**Higham 2002** §1.7); expanding the square root to first order gives (6.35), and
inverting gives (6.36). ∎

**The numbers.** Golden vector **G3**: `V_s = 7.2`, pure following current `c = 6.48`,
`v = (1,0)`. Then `λ = 51.84 − 41.9904 = 9.8496`, `a = 6.48`, `D = 1`, and (6.36) gives
`log₁₀(2·41.9904/9.8496) = log₁₀(8.527) = 0.93` — **about one digit at `|c|/V_s = 0.9`**. At
`|c|/V_s = 1 − 1e-8`: `λ ≈ 2V_s²·1e-8 = 1.037e-6`, `a ≈ 7.2`, `D = 1`, giving
`log₁₀(2·51.84/1.037e-6) = log₁₀(1.0e8) = 8.0` — **eight digits**. The loss blows up exactly
as `|c| → V_s`, i.e. precisely in the strong-current cells where routing decisions actually
matter.

**The fix.** Multiply by the conjugate:

```
F  =  D / ( a + sqrt(a² + λD) )                                              (6.37)
```

which **adds** two positive quantities when `a > 0` and is unconditionally stable there. For
`a ≤ 0` the roles swap — `a + s` becomes the cancelling pair — so the direct form is used
instead. Each branch is exact to a couple of ulp.

> **NORMATIVE — branch on the sign of `a = ⟨v,c⟩`:**
> ```
> if D <= 0                     : F = 0                    # gauge of the zero vector
> if a >  0 and a²+λD <  0      : F = +INF                  # Kropina forbidden cone
> if a >  0                     : F = D / (a + sqrt(a²+λD)) # conjugate, stable
> if a <= 0 and λ <= 0          : F = +INF                  # no positive root exists
> if a <= 0                     : F = (sqrt(a²+λD) − a)/λ   # direct, stable
> ```
> **Never returns NaN.** This is `Eq (6.26)` and it is the same branch table for the co-moving
> case with `c ← c₀ − w` (`Eq C.6`) — every closed form and every golden vector carries over
> verbatim under the shift.

**G3 verification, to the last bit.**
```
naive:      F = (sqrt(6.48² + 9.8496·1) − 6.48)/9.8496 = (sqrt(51.84) − 6.48)/9.8496
              = (7.2 − 6.48)/9.8496            <- catastrophic cancellation here
conjugate:  F = 1/(sqrt(51.84) + 6.48) = 1/13.68 = 0.073 099 415 204 678 362…
```
The conjugate form is exact to the last bit; the naive form loses digits in proportion to
`a²/(λD)`, per (6.36).

### 6.6.2 Lemma 6.17 — `λ` cannot be rescued by factoring, and does not need to be

The obvious "fix" for `λ = V_s² − |c|²` as `|c| → V_s` is to factor it as `(V_s − |c|)(V_s + |c|)`.
**It gains nothing**, and believing otherwise leads to a false sense of safety.

> **Lemma 6.17.** Let `|c|` be computed with relative error `≤ u` (true for `hypot`). Then both
> forms give `λ` with absolute error `≈ 2u V_s²`, hence relative error
> ```
> |Δλ| / λ  ≈  2u V_s² / λ                                                   (6.38)
> ```
> and no reformulation in terms of `V_s` and `c` alone recovers it in binary64.

**Proof.** *Direct form.* `fl(V_s²)` has absolute error `≤ u V_s²`; `fl(|c|²)` has absolute
error `≤ 2u|c|²` (one rounding from `|c|`, one from squaring); the subtraction of two values
whose difference is `λ` introduces at most `uλ`, negligible. Total absolute error
`≈ u(V_s² + 2|c|²) ≈ 2uV_s²` when `|c| ≈ V_s`.

*Factored form.* When `|c|/2 ≤ V_s ≤ 2|c|` — which holds throughout the regime of interest —
**Sterbenz's lemma (1974)** says the subtraction `V_s − |c|` is computed **exactly**. But the
input `|c|` already carries absolute error `u|c|`, so the difference carries absolute error
`u|c|`. Multiplying by `(V_s + |c|) ≈ 2V_s` gives absolute error `≈ 2u V_s |c| ≈ 2u V_s²`.

The two are the same to leading order. The information destroyed is destroyed when `|c|` is
rounded to a double, before any rearrangement can act. ∎

**Why this does not matter, and what to do instead.** (6.38) says `λ`'s *relative* accuracy is
poor near degeneracy. But:

- In the **conjugate branch** (6.37), `λ` appears only inside `a² + λD` where `λD ≪ a²`; an
  error `δ` relative in `λ` perturbs `s` by `δ·λD/(2s²)` relative — **heavily damped**. The
  conjugate branch is essentially insensitive to `λ`'s conditioning. This is a second,
  independent reason to prefer it.
- In the **direct branch** (`a ≤ 0`), `λ` sits in the denominator and the relative error of `F`
  inherits (6.38) at `O(1)`. But there `F → ∞` and `σ = λ/(s + |a|) → 0`, so the badly
  conditioned quantity is a speed made good that is heading to zero. The correct response is
  **not** to floor `λ`; it is to floor `σ` on **physical** grounds (§6.6.6).

**Do not introduce a `λ` floor.** A floor on `λ` is a floor in `(m/s)²` with no physical
meaning, and it changes the boundary of the Kropina cone (`ERRATA E1.1`) by an amount nobody
can justify. Floor `σ` instead.

### 6.6.3 `σ` must be computed as `1/F`, not from its own closed form

The algebraically equivalent

```
σ(u)  =  ⟨u,c⟩ + sqrt( ⟨u,c⟩² + λ )                              [UNSTABLE for ⟨u,c⟩ < 0]
```

cancels for a **head-on** current as `|c| → V_s`: the two terms approach `−|c|` and `+|c|`. Its
condition is the mirror image of (6.36). Since `F`'s two branches never cancel and inverting a
well-conditioned quantity costs one ulp:

> **NORMATIVE:** `σ(x,t,u) := 1/F(x,t,u)` for a unit `u`, with `σ := 0` when `F` is `+∞` or
> non-positive. Do not implement `σ` from its own closed form.

**Golden vector cross-check (G2).** `V_s = 7.2`:

| # | case | `c∥` | `\|c⊥\|` | `σ` [m/s] | `F` [s/m] |
|---|---|---|---|---|---|
| T1 | no current | 0 | 0 | **7.2** exact | **0.138 888 888 888 889** |
| T2 | pure following | +1.5 | 0 | **8.7** exact | **0.114 942 528 735 632** |
| T3 | pure head | −1.5 | 0 | **5.7** exact | **0.175 438 596 491 228** |
| T4 | pure cross | 0 | 1.5 | **7.042 016 756 583 30** | **0.142 004 774 280 768** |
| T5 | 30° off a 1.5 m/s current | +1.299 038 105 676 66 | 0.75 | **8.459 869 063 044 66** | **0.118 205 139 175 062** |
| T6 | near-degenerate, `\|c\|/V_s = 0.95` | −6.84 | 0 | **0.36** exact | **2.777 777 777 777 78** |
| T7 | Kropina, `\|c\| > V_s`, head-on | −8.0 | 0 | **blocked** | **+∞** |
| T8 | cross-dominated | 0 | 7.5 | **infeasible** | **+∞** |

`T4`: `sqrt(7.2² − 1.5²) = sqrt(49.59) = 7.042 016 756 583 301 399 891`. `T6`: `7.2 − 6.84 =
0.36`, `F = 1/0.36 = 2.7̄`. T6 is the case that exercises (6.38): `λ = 51.84 − 46.7856 = 5.0544`,
relative error `2u·51.84/5.0544 = 2.3e-15` — still 14 good digits, so T6 passes the 12-figure
criterion even in the direct branch. The branch only matters at `|c|/V_s > 0.999`.

### 6.6.4 The remaining formulas, in one table

| Formula | Where it cancels | Reformulation | Residual accuracy |
|---|---|---|---|
| `F = (sqrt(a²+λD) − a)/λ` | `a > 0`, `λ → 0` | conjugate (6.37) | 2 ulp, both branches |
| `σ = ⟨u,c⟩ + sqrt(⟨u,c⟩²+λ)` | `⟨u,c⟩ < 0`, `λ → 0` | `σ := 1/F` | 1 ulp above `F` |
| `λ = V_s² − \|c\|²` | `\|c\| → V_s` | **none available** (Lemma 6.17) | (6.38); avoid dividing by it |
| `ℓ(ζ) = \|x − ξ(ζ)\|` | `ξ → x` | none needed: the `ℓ_min` exclusion (§6.3.2) guarantees `ℓ ≥ h/√2` | ≤ 2 ulp; and use (6.15) so `ℓ` never appears in a denominator |
| quadratic roots of (6.16) | `PE² ≫ E2·C` | Citardauq pairing, Proc 6.3a line 8 | 2 ulp on both roots |
| `A(ζ) = T̃ + F(v)` | `T̃ ≫ ℓF` | see Lemma 6.18 — no reformulation needed | (6.39) |
| `R(ζ)` sign test (6.23) | `⟨e,v⟩ ≈ F⟨e,c⟩` | multiply through by `s > 0`; never divide | sign correct to 1 ulp of the bracket |
| `∇F = (v − Fc)/s` | `v ≈ Fc` (drift-dominated) | equivalent form (6.22); or note `v − Fc = F V_s n` is exactly the through-water leg and is `O(F V_s)`, never small | 3 ulp |
| `x = sinφ₁sinφ₂ + cosφ₁cosφ₂cosΔλ` | never (both terms `≤ 1`, sum `≤ 1`) | — but `arccos(x)` amplifies, Lemma 6.14 | use haversine |
| `a = sin²(Δφ/2) + cosφ₁cosφ₂sin²(Δλ/2)` | never (all terms `≥ 0`) | — | few ulp |
| `wrap_pi` via `a − 2π·round(a/2π)` | large `\|a\|` | `fmod` (Proc 6.5f), which is exact | exact |
| `1 − cos ψ` in windage / STAwave directionality `f_dir = 0.625 − 0.375 cos μ_rel` | `μ_rel → 0` | `f_dir` is bounded in `[0.25, 1.0]` and is a *multiplier*, not a branch; the cancellation costs relative digits in a quantity that is never near zero. **No action.** | fine |
| `ω_e = ω_p − (ω_p² V/g) cos μ_rel` (encounter frequency) | resonance test `\|ω_e − ω_φ\| < 0.10 ω_φ` | this **is** a branch, but the comparison band is `10 %` wide — twelve orders above any rounding. **No action**, but see §6.7 D9 for the discontinuity it creates. | fine |

> **Lemma 6.18 (accumulated rounding along a route is negligible).** Arrival times accumulate
> as `T ← T̃ + increment` with `T = O(10⁶ s)` for a two-week voyage and increments
> `O(10³–10⁴ s)`. Each addition contributes absolute error `≤ u·T`. Over `n` accumulations the
> errors are independent to leading order and grow as a random walk,
> ```
> |ΔT_accum|  ≲  sqrt(n) · u · T                                             (6.39)
> ```
> With `n = 10⁵` updates along a path and `T = 10⁶ s`: `316 × 1.11e-16 × 10⁶ = 3.5e-8 s`.
> The worst case (all errors aligned) is `n·u·T = 1.1e-5 s`. Both are utterly negligible against
> arrival times quoted to `1e-4 h = 0.36 s` (`CORE-THEOREM.md §8.2`).

**But (6.39) is the floor for every time-comparison tolerance in the solver**, and it is why
§6.6.7 sets `ε_mono = 1e-6 s` rather than the `1e-9 s` the reference implementation uses:
`1e-9 s` sits **below** the `3.5e-8 s` random-walk bound, so a queue built on it will report
monotonicity violations that are pure rounding.

### 6.6.5 Dominance tests: make them exact

Label dominance decides which routes survive. If it is decided by floating-point noise, the
returned Pareto front is not reproducible and the `ε`-vs-`ε/4` experiment of `00-overview.md`
L6 is unreadable. `ERRATA (E7)` hands us the fix for free.

> **Key observation.** `ERRATA (E7.1)` buckets on the **objective value**:
> `bucket_i(ℓ) = ⌊ log(ℓ_i/C_i^min) / log(1+ε) ⌋` for `i = 2…k`. Bucket indices are
> **integers**. Therefore dominance on objectives `2…k` is an **integer comparison** — exact,
> tie-free, and bit-reproducible.

Objective **0 (time) is never bucketed** (`E7`), so it needs a real comparison. And the
`log`-based definition above is itself a portability hazard: `log` is not correctly rounded, so
two platforms can assign a value straddling a bucket boundary to different buckets. Proc 6.9
removes both problems.

```
Proc 6.9  bucket_index(value, i) -> integer                 # replaces the log/floor form
Precomputation, once per objective i:
 1  B[0] <- C_i_min
 2  for m = 1 .. M_i :  B[m] <- B[m-1] * (1 + eps)          # repeated MULTIPLY, not pow()
 3  M_i <- ceil( log(C_i_max / C_i_min) / log(1+eps) )      # sizing only; off-by-one is safe
Query:
 4  return the smallest m with value <= B[m]                # binary search, O(log M_i)
                                                            # i.e. round the bucket UP
```

Three normative properties, each with a reason:

1. **Repeated multiplication, not `pow`.** Each IEEE multiply is correctly rounded, so the
   boundary sequence `B[·]` is bit-identical on every conforming platform. `pow(1+ε, m)` is
   not required to be correctly rounded and differs in the last ulp between libm
   implementations, which would put a value on different sides of a boundary on two machines.
2. **Round the bucket UP** (`value ≤ B[m]`). A value exactly on a boundary is assigned the
   **higher** (worse-looking) bucket. This is the safe direction: assigning too **low** a bucket
   makes a label look better than it is, and it could then dominate — and prune — a genuinely
   incomparable label, breaking the `(1+ε)` guarantee of `Thm 5.2`. Assigning too high a bucket
   can only cause a label to be pruned by a better one, which is exactly what the `ε`-relaxation
   licenses.
3. **Binary search, not `floor(log(...))`.** Removes `log` from the query path entirely, so the
   bucket assignment involves only comparisons of doubles — the one operation IEEE-754 makes
   fully deterministic.

**Bottleneck (`max`-accumulated) objectives** take finitely many distinct values along a route
and are bucketed **on the value directly** (`E7`), which is the same Proc 6.9 with the same
tie rule.

**The label bound this buys** (`E7.2`): `Λ ≤ Π_{i=2}^{k} ( ⌈log(C_i^max/C_i^min)/log(1+ε)⌉ + 1 )`.
For `k = 3`, `ε = 0.02`, two decades of range: `Λ ≤ (log 100/log 1.02 + 1)² ≈ 234² ≈ 5.5e4`
worst case, and **10–40 observed after dominance pruning**. Contrast the rejected
increment-bucketing construction, which gave `>10¹⁰` labels per node — vacuous.

**The time comparison.** Two labels tie on time when `|T_a − T_b| ≤ ε_time`. Normative
`ε_time = 1e-6 s`, justified in §6.6.7. The full dominance predicate:

```
Eq (6.40)   a  dominates  b   iff
              T_a  <=  T_b + eps_time
              and  bucket_i(a) <= bucket_i(b)  for every i = 2..k
              and  ( T_a < T_b - eps_time  or  bucket_i(a) < bucket_i(b) for some i )
```

**Determinism of the surviving set** additionally requires a total order for tie-breaking; that
is §6.10.

### 6.6.6 The direction-exclusion floor, and a CONFLICT in the reference code

A direction must be excluded when the ship makes no useful progress along it. Three different
thresholds appear in the reference implementation:

| Site | Value | Quantity |
|---|---|---|
| `metric.py` `_SOG_FLOOR` | `1e-9` | m/s |
| `comoving.py` stationary sweep | `1e-6` | m/s |
| `RandersMetric.sigma_max` | `F` non-finite or `≤ 0` | — |

> **NORMATIVE resolution: a single constant `SIGMA_FLOOR = 1e-3 m/s`,** applied uniformly.
> A direction with `σ ≤ SIGMA_FLOOR` is excluded: `F := +∞`, the direction does not enter the
> update, and this is **not** an exception.

**Justification, on physical grounds rather than numerical ones.** `σ = 1e-3 m/s` is `86 m/day`.
The implied `F_max = 1/σ = 1000 s/m` makes a single 28 km leg cost `2.8e7 s = 324 days`. No
route contains such a leg; if one did, the voyage is not a voyage. Two further checks:

- **It cannot exclude anything useful.** The slowest sensible progress in a routing context is
  perhaps `0.1 m/s` (0.2 kt), two orders above the floor.
- **It bounds the queue.** `ERRATA (E2.2)` gives `n_buckets = ⌈r_max·F_max/Δ_min⌉`; an
  unbounded `F_max` makes the bucket count unbounded, which is the *actual* failure mode E2
  identifies (not `F_min → 0`, which E2 shows is false — `F_min = 1/(V_max+|c|)` is bounded
  below by `1/(V_max + |c|_max) > 0` and shrinks only by a third across the entire realistic
  drift range: `0.133, 0.111, 0.100, 0.067 s/m` at `|c| = 0.5, 2, 3, 8 m/s` with
  `V_max = 7 m/s`). `SIGMA_FLOOR` caps `F_max` at `1000 s/m`, hence caps the bucket count.
- **It composes with the E2 fallback.** The heap fallback fires on `Υ_loc > Υ_heap = 12`
  (normative default), long before `σ` approaches the floor, so in practice the floor is a
  backstop for the excluded-direction test, not a working threshold.

**Why not `1e-9`.** At `σ = 1e-9 m/s` a 28 km leg costs `2.8e13 s ≈ 890 000 years`, and — worse
— the *relative* accuracy of `σ` there is governed by (6.38) and is meaningless. A floor should
sit where the quantity stops being trustworthy **and** stops being useful; `1e-3` satisfies
both and `1e-9` satisfies neither.

### 6.6.7 Bucket-queue arithmetic

The Dial (1969) queue is correct only if the bucket width is **≤ the minimum increment**. That
is `ERRATA (E3)`'s subject, and it is why the `ℓ_min` exclusion of §6.3.2 exists.

```
Eq (6.41)   l_min  := h/sqrt(2) ,   c_geo := 1/sqrt(2) = 0.707 106 781 186 547 5
Eq (6.42)   Delta_min := l_min · F_min = c_geo · h · F_min
Eq (6.43)   n_buckets  := ceil( r_max · F_max / Delta_min )
```

**Worked value.** `h = 27.8 km` (0.25°), `V_max = 7.2`, `|c| = 1.5`: `F_min = 1/8.7 =
0.1149 s/m`, so `Δ_min = 0.7071 × 27 800 × 0.1149 = 2 259 s`. With `r_max = 2h = 55.6 km` and
`F_max = 1/5.7 = 0.1754 s/m`: `n_buckets = ⌈55 600 × 0.1754 / 2 259⌉ = ⌈4.32⌉ = 5`. A five-slot
ring. That is the whole point of the construction.

**Index computation.** `bucket = ⌊(key − key_base)/Δ_min⌋ mod n_buckets`, computed in
floating point then truncated to an integer. Two hazards:

1. **A key below the current minimum** wraps the ring and silently mis-orders the queue —
   `handbook/02-debugging-playbook.md` **S1** cause (3). Every push must test
   `key ≥ current_min − ε_mono`; a violation must **increment a counter and fall back to a
   heap**, never be silently absorbed.
2. **A key exactly on a boundary.** Truncation is deterministic given the same key, so this is
   not a reproducibility hazard; it is only a hazard if `key_base` is recomputed differently in
   two places. Compute `key_base` once, at queue construction, and never again.

> **NORMATIVE `ε_mono = 1e-6 s`.** Justification, both directions:
> - **Above the noise:** by Lemma 6.18 the accumulated rounding along a path is `3.5e-8 s`
>   (random walk) and `1.1e-5 s` (worst case aligned). `1e-6 s` clears the random-walk bound by
>   `30×`. It does **not** clear the aligned worst case — accepted, because a fully aligned
>   `10⁵`-step error is not a physical scenario and the counter will surface it if it happens.
> - **Below anything meaningful:** `1e-6 s` is `9` orders below `Δ_min ≈ 2 259 s`, so it can
>   never merge two distinct buckets or reorder two genuinely different keys.
>
> **This corrects the reference implementation's `1e-9 s`**, which sits *below* the `3.5e-8 s`
> random-walk bound and therefore reports monotonicity violations that are pure rounding —
> exactly the counter that `handbook/02-debugging-playbook.md` says "should be 0".

`ε_time` for the dominance test (6.40) takes the **same** value `1e-6 s` and for the same
reason: both are comparisons of accumulated arrival times, and using two different tolerances
for the same quantity is how a queue and a label set come to disagree about which of two labels
is earlier.

---

## §6.7 — Degenerate and edge cases

Every case below has an **exactly defined behaviour**. "Handle gracefully" is not a
specification and does not appear. Each entry states the condition, the required behaviour, the
reason, and what goes wrong if it is not implemented.

### D1 — Drift exceeds through-water speed: the one-sided metric and the reachable cone

**Condition.** `|c| > V_max(x,t)`, where `V_max := max_{θ,q} attainable(vessel, env, θ, q)` is
the best **through-water** speed. In the co-moving frame the test is on the effective drift:
`|c₀(y) − w| > V_max(y)` — `Eq (C.7)`, "the precise, checkable statement of *the ship can work
against this system*".

**Required behaviour.**
```
alpha_reach = arcsin( V_max / |c| )                                          (E1.1)
F(x,t,u) = +INF   for every u outside the cone of half-angle alpha_reach about c
```
All achievable ground velocities lie in `D(c, V_max)`, which excludes the origin. Implement as
a **two-line check**, not a special case. `|c| = V_max` exactly: the cone degenerates to a
half-plane boundary; **treat as excluded (`F = +∞`) for strict safety.**

**Why the naive test never fires.** `ERRATA (E1)` is emphatic: the earlier condition
`|c| ≥ σ_max` is *identically false*, because `σ_max = max_u σ(x,t,u)` is speed made good **over
ground** and in the direction of the drift `σ ≥ V_max + |c| > |c|` always, for any `V_max > 0`.
Any implementer coding `if (norm_c >= sigma_max)` gets a branch that **never fires** — silently
running the fast path in exactly the cells where the theory says it must not. Everywhere
`σ_max` was used as a proxy for through-water speed, substitute `V_max`.

**What this means operationally.** Where it fails, the correct answer really is *you cannot
escape this storm*, and the router must say so rather than return a route through the cone.

### D2 — `λ ≤ 0` in the Randers form returning a NEGATIVE `F` (golden vector T7)

**Condition.** `λ = V_s² − |c|² ≤ 0` with the single-branch closed form.

**What happens without the guard.** With `V_s = 7.2`, `c = 8.0` against the current, the form
`F = [sqrt(⟨v,c⟩² + λ|v|²) − ⟨v,c⟩]/λ` returns

```
F  =  −1.25                                                                  [T7]
```

**a negative cost.** It does not raise. It does not produce NaN. It returns a plausible-looking
finite number with the wrong sign.

**Why this is catastrophic in a shortest-path solver.** A negative edge cost creates a negative
cycle. Label setting then either (a) never converges — the sweep runs forever, re-lowering
values around the cycle — or (b) terminates with **an arrival time in the past**. Neither
failure is visible in the route geometry, which is why this is golden vector T7 and why
`handbook/02-debugging-playbook.md` **S1** lists it as the first cause to check.

**Required behaviour.** The branch table of §6.6.1, in full. Specifically:
`λ ≤ 0` **and** `a ≤ 0` ⟹ `F = +∞` (no positive root exists: the drift is at least as strong
as the ship and this direction has a non-positive projection on it, so it cannot be made good
at all). `λ ≤ 0` **and** `a > 0` **and** `a² + λD < 0` ⟹ `F = +∞` (inside the forbidden cone of
D1). `λ ≤ 0` and `a > 0` and `a² + λD ≥ 0` ⟹ the conjugate form `D/(a + sqrt(a²+λD))`, which is
finite and positive — this is the *reachable* part of the cone and is a legitimate answer.

> **Guard `λ > 0` before dividing. Every time. No exceptions.**

**Mandatory assertion.** `assert F > 0 && isfinite(F)` at **every** metric evaluation, with the
`(lat, lon, t, u)` of the first violation recorded. This is the discriminating test of S1: if it
fires, the cause is the `λ` guard or the `σ` guard; if it does not fire and the sweep still
misbehaves, instrument the queue's `monotone_violations` counter instead.

**Test-suite obligation.** T7 must be **reachable in the test suite**, not merely defended
against in code.

### D3 — Cross-track drift exceeds `V` (golden vector T8)

**Condition.** `|c⊥| ≥ V` for the requested direction `u`.

**Physics.** The cross-track current exceeds the ship's speed through water, so **no heading
holds the track**: the ship is set sideways faster than it can crab back. Algebraically, `sqrt`
of a negative in (6.7).

**Required behaviour.** `σ := 0`, `F := +∞`, the direction is excluded from the update. In
Proc 6.2 this is line 5 (`if V ≤ |c⊥| : return NONE`), tested **before** the `arcsin`, so the
`arcsin` argument is never out of range.

> **Not an exception.** This is a routine, physically meaningful condition in the Agulhas and
> the Somali Current, and it **must not abort a voyage plan**. A router that raises here fails
> on the first realistic Indian Ocean forecast it is given.

**Test-suite obligation.** T8 must be reachable in the test suite.

**Interaction with D1.** D1 and D3 are different: D1 says the drift beats the ship in *every*
sense and the reachable directions form a cone; D3 says this *particular* direction is
unreachable while others may not be. A cell can satisfy D3 for some `u` and be perfectly
navigable in others. Implement both; neither subsumes the other.

### D4 — Empty admissible set at a node

**Condition.** `legs(x, t, u)` returns empty for **every** sampled `u`, either because all
directions are excluded by D1/D3, or because every `(V,θ,q)` triple violates a seakeeping ban.

**Required behaviour.**
- The node's value stays `T = +∞`; it is a sink; the sweep does not expand from it.
- If it is the **source**: refuse the query with an explicit "departure conditions inadmissible"
  result, listing which bans fire. Do **not** return an empty route as if it were a route.
- If it is the **destination**: report unreachable (see D6).
- Count such nodes and report the count. A high count is the signature of a mis-scaled ban
  threshold, not of bad weather.

**Related but distinct — `0 ∉ 𝒱`.** `ERRATA (E9)` corrects a claim that matters here. The
statement "`F` is finite in every direction **iff** `0 ∈ int 𝒱`" is **false**: sufficiency holds,
necessity does not. Counterexample `𝒱 = {1 ≤ |v| ≤ 2}` — every ray from the origin meets `𝒱`, so
`F` is finite in every direction, yet `0 ∉ 𝒱`. And it is not academic: the default vessel has
`q_min = 0.15`, so by the cube law `V_min/V_max = 0.15^{1/3} = 0.53 > 0`, **the ship cannot
stop**, and `0 ∉ 𝒱` whenever `|c| < V_min`. The three correct claims:

1. `F(x,t,u) < ∞` **iff** the ray `ℝ₊u` meets `𝒱(x,t)`.
2. `F(x,t,·)` is finite in **every** direction **iff** `0 ∈ int(star-hull 𝒱)`; under D4 (we
   solve with `conv 𝒱`) this is equivalent to `0 ∈ int conv 𝒱`, i.e. `|c| < V_max`.
3. `0 ∈ 𝒱` itself is **false** whenever `|c| < V_min`, and is **not required by anything**.

**Practical consequence for the implementer:** do not code a "can the ship hold station" test
against `𝒱`. It is about `conv 𝒱`. A ship with a minimum engine load genuinely cannot hold
station, and the convexification is what lets it be treated as if it could (by alternating
headings). Testing `0 ∈ 𝒱` will reject perfectly navigable cells.

### D5 — Source or destination on land

**Condition.** `is_water(i,j)` is false at the snapped node, or the point lies outside the
domain.

**Required behaviour, normative.**
- **Default: refuse**, with a result that names which endpoint failed and its distance to the
  nearest water node. Silent snapping changes the problem the user asked about.
- **On explicit request** (`snap_to_water = true`): search a neighbourhood of radius
  `R_SNAP = 8` cells for the nearest water node, snap to it, and **report the snap distance in
  the result**. If no water node exists within `R_SNAP`, refuse.
- Out-of-bounds points **clamp to the boundary** inside `nearest()` (the caller usually wants
  the closest legal start) but the clamp distance must be reported. A clamp of more than one
  cell is a domain-setup error, not a routing input.

**Why `R_SNAP = 8`.** At `0.25°` that is ~220 km. Beyond that the snapped problem is a
different voyage. The number is an operational choice, not a theorem; record it in the run log.

**Related failure that snapping cannot fix.** At `h ≈ 0.25°` a strait narrower than one cell is
topologically **closed** by the land mask (an optimal route is lost silently) and a shoal
narrower than one cell is topologically **open** (an inadmissible route is returned). This is a
**correctness** failure, not an accuracy failure, and no convergence theory touches it.

### D6 — Destination unreachable

**Condition.** `T[destination] = +∞` after the sweep terminates, or (co-moving) no node's mapped
ground landfall comes within an acceptance radius of `x_B`.

**Required behaviour.** Return an explicit *unreachable* result carrying: the number of nodes
expanded, the number of nodes with finite `T`, the minimum ground miss achieved over the whole
grid, and whether the sweep hit `max_expand`. **Never return a partial route.** Distinguish the
three causes, because they have different fixes:

| Cause | Signature | Fix |
|---|---|---|
| Genuinely disconnected water | `min` ground miss large, sweep terminated naturally, many finite-`T` nodes | none — report it |
| Co-moving grid undersized | `min` ground miss large **over the whole grid** | dilate (§6.7 D12) |
| Sweep truncated | `expanded ≥ max_expand` | raise the cap; report that it was raised |

### D7 — Queue ties, and the deterministic total order

**Condition.** Two entries with keys within `ε_mono`, or two labels incomparable under (6.40).

**Required behaviour.** A **total order** independent of insertion order, thread count and
compiler. Normative:

```
Eq (6.44)   compare(label a, label b) :=  lexicographic on the tuple
              ( quantise(T, eps_time),        # integer: floor(T / eps_time)
                bucket_2, ..., bucket_k,      # integers, Proc 6.9
                source_node_id,               # integer, the node the label came from
                rule_id )                     # integer: 0 = rho_k, 1 = rho_j, 2 = rho_jk
```

Every field is an **integer**, so the comparison is exact and platform-independent. `rule_id`
orders the three rules of `Eq (3.24)` so that a tie between a single-vertex update and an edge
update always resolves the same way. Ties beyond `rule_id` cannot occur: `(source_node_id,
rule_id)` uniquely identifies the update.

**Why this is required and not a nicety.** `00-overview.md` L9: the inner minimisations
terminate at finite tolerance, so near-ties in dominance are otherwise decided by
floating-point noise, and without a specified tie-break the returned front is not reproducible
across compilers or thread counts — which makes the `ε`-vs-`ε/4` sensitivity experiment
unreadable. §6.10 states what reproducibility this does and does not deliver.

**FIFO within a bucket.** Within one Dial bucket the order is FIFO by a monotonically increasing
insertion sequence number. This is a tie-break of last resort and must never be reached for two
labels of the same node, since (6.44) already separates those.

### D8 — Zero wave height

**Condition.** `H_s = 0` exactly, which is legal, common in the lee of land, and produced by
Lemma 6.13's range preservation whenever all 8 corners are zero.

**Required behaviour, component by component:**

| Quantity | Behaviour at `H_s = 0` |
|---|---|
| Added resistance in waves (STAwave-1) | `R_AW := 0` by an early return on `H_s ≤ 0`, **before** any `sqrt` or division. |
| `μ_w` | Undefined. The interpolated `(cos, sin)` pair is `(0,0)` and `atan2(0,0)` returns `0` on a conforming libm — **define it as `0` and mark the direction immaterial**. Every downstream use of `μ_w` is multiplied by a factor proportional to `H_s` or `H_s²` (added resistance, roll excitation, comfort), so a wrong angle times zero amplitude is zero. Verify this multiplication exists before relying on it. |
| `ω_p = 2π/max(T_p, 1e-3)` | Finite by the floor. With `H_s = 0` the roll criteria S1/S2 are gated on `H_s > hs_roll` and do not fire. |
| Roll/parametric-roll bans (S1, S2) | Gated on `H_s > hs_roll = 0.5·hs_caution`; do not fire. Correct: a ship does not roll resonantly in flat water. |
| Comfort rate | `∝ H_s · |sin μ_rel|` = 0. |
| Risk level | `∝ H_s/hs_limit` = 0. |
| Surf-riding (S3) | **Still fires** — it is gated on speed and wavelength, not on `H_s`. With `H_s = 0` and a residual swell period the wavelength test can be true. This is a modelling artefact: gate S3 additionally on `H_s > 0`. |

**The deeper point.** `H_s = 0` is the case where every "divide by the sea state" normalisation
in a naive implementation produces `0/0`. The reference vessel model avoids it by making every
sea-state term a **multiplier** rather than a divisor; a port that inverts any of them
reintroduces the problem. The slamming statistics of **Ochi (1964)**, if implemented, are a
probability computed from spectral moments `m0r, m2r` which are both zero at `H_s = 0` — that
ratio is `0/0` and must be short-circuited to "no slamming".

### D9 — Discontinuous risk and the ragged front

**Condition.** `risk_level` implemented as `1.0 if banned else 0.0`.

**Symptom.** The Pareto front is ragged and tiny changes in `ε` produce very different route
sets (`handbook/02-debugging-playbook.md` **S6**).

**Required behaviour.** `risk_level` **must be continuous in `(V, θ)`** even though
`violations()` is discrete. Build it as a smooth blend of the margin to each criterion — e.g.
`H_s/hs_limit` scaled by a beam-sea penalty — rather than as an indicator of the ban. The bans
themselves stay discrete (they are IMO MSC.1/Circ.1228 thresholds and are not negotiable); it
is the *risk objective* that must be smooth.

**Discriminating test.** Sample `risk_level` along a heading sweep at fixed speed and plot it.
Any vertical jump is the bug.

**Numerical reason.** `ε`-dominance pruning compares bucketed values (Proc 6.9). A discontinuous
objective puts neighbouring headings in far-apart buckets, so the pruning decision flips on an
arbitrarily small change in heading — and the heading is itself the output of a fixed point
converged to `1e-11` rad. The front then depends on the last bits of Proc 6.2.

### D10 — Thin Pareto front

**Condition.** The front collapses to a line: every label has `q = 1`.

**Two causes, both diagnosable.**
1. `sfoc()` is effectively constant, so fuel is a monotone function of time and there is nothing
   to trade off. **Test:** evaluate `fuel_per_mile(q)` at `q = 0.35, 0.55, 0.75, 1.0`; it **must**
   have an interior minimum near `q ≈ 0.75`. Monotone decreasing in `q` means the SFOC bowl is
   flat and the physics contains no trade-off.
2. The time-only fast path (`sigma_max`) is wired into the Pareto solver, so `legs()` returns
   only the max-throttle entry. **Test:** print `len(legs())` for a mid-ocean cell. It should be
   **2–4** after Pareto pruning. Always 1 is the bug.

This is a numerics issue and not only a modelling one because `sigma_max` is *allowed* to be
much cheaper than `legs(...)[0]` — that licence (`CONTRACT.md §4`) is exactly what makes the
mis-wiring easy and invisible.

### D11 — Coincident, antipodal and zero-length legs

| Condition | Behaviour |
|---|---|
| `haversine(A, A)` | `0.0` exactly (`a = 0`, `asin(0) = 0`). Safe. |
| `initial_bearing(A, A)` | `y = x = 0`; Proc 6.5b line 5 returns `0.0`. The bearing is genuinely undefined; returning `0` with no flag is acceptable **only** because every caller multiplies it by a zero distance. If a caller does not, it must test the distance first. |
| Antipodal pair | `initial_bearing` is undefined (infinitely many great circles). `atan2` returns *some* value; the distance is correct to `2.8e-7 m` (§6.5.2). Never arises between grid neighbours; can arise in the `O(N)` goal scan, where only the distance is used. |
| `ℓ(ζ) = 0` in the update | **Cannot occur:** the `ℓ_min` exclusion (§6.3.2) removes the whole sub-interval where `ℓ < h/√2`. This is the concrete payoff of `ERRATA (E3)`. |
| `|v| = 0` in the gauge | `F := 0` (the gauge of the zero vector), by the first line of the branch table. |
| Source `=` destination | `t* = 0`, empty waypoint list, zero fuel. Return it as a valid result, not an error. |
| `V_s = 0` | Every direction has `σ = c∥` at best; if `c∥ ≤ SIGMA_FLOOR` the direction is excluded. A vessel with `V_s = 0` yields an all-`+∞` metric and D4 fires at the source. Refuse at input validation with a clear message rather than let it propagate. |

### D12 — The co-moving grid is undersized (R1)

**Condition.** The co-moving domain does not contain `y = x_B − w t` for the relevant `t`.

**Why it happens.** The solve lives in `y = x − w t`, so reaching ground point `x_B` at time `t`
requires the node `y = x_B − w t` to be **inside the grid**. Over a voyage of duration `t_max`
the co-moving domain is displaced from the ground domain by `w·t_max`.

**Measured consequence (`CORE-THEOREM.md §8.1 R1`).** On a 140 h voyage with `w = (1,1) m/s`
the required node lay **4.5° west of the grid edge**, giving a **104.5 km landfall miss that a
full-grid scan could not reduce** — because no node in the domain mapped anywhere near the
target at all. Extending the domain by `|w|·t_max ≈ 500 km` brought the miss to **11.2 km**,
under half a grid diagonal.

**Required behaviour.**
```
Eq (6.45)   required_dilation = ( |w_E| · t_max ,  |w_N| · t_max )   [metres]
```
Extend the grid by this much in the direction **opposite** to each component of `w` (west/south
for positive `w`). Compute it before allocating the grid, from an upper bound on `t_max`.

**Why it must be checked explicitly.** It fails **silently**: the sweep converges, the route
looks plausible, and the landfall is simply wrong.

**Discriminating test (`S8b`).** Scan every node for `min ‖(y + w·T[y]) − x_B‖`. If the minimum
over the **whole grid** is large, the domain is too small. If it is small but the selected node
is worse, the cause is D13 instead.

### D13 — Goal node selected by the interception root find (R2)

**Condition.** Selecting the goal by bisecting `g(t) = T_w(x_B − w t) − t` and snapping to the
nearest node.

**Why it fails.** Sampling `T` at the nearest node makes `g` a **step function**, so a bisection
converges to a **discontinuity rather than a root**, and `T` at the returned node can be far
from `t*`. Because the ground position is `y + w·T[y]`, that timing error is **amplified by
`|w|`**: with `|w| ≈ 3 m/s` and a half-cell timing error of `~2000 s`, the landfall moves
`~6 km` per cell of snapping error. Measured at **104.5 km** before the fix, and unchanged by
widening the search neighbourhood, because the offset is **systematic rather than local**.

**Required behaviour.** Solve the interception condition **directly on the discretisation**.
Every node carries its own arrival time, hence its own ground landfall `y + w·T[y]`; take the
node minimising `‖(y + w·T[y]) − x_B‖`. This **is** `Eq (C.4)` evaluated exactly on the grid,
with no interpolation and no root find, at `O(N)` with one haversine per node.

```
Proc 6.7  goal_node(grid, w, T[·], x_B) -> (node, miss_metres)
 1  best_node <- -1 ; best_miss <- +INF
 2  for n = 0 .. N-1
 3      tau <- T[n] ;  if not finite(tau) : continue
 4      (y_lat, y_lon) <- latlon(n)
 5      (g_lat, g_lon) <- ground_position(y_lat, y_lon, tau)     # x = y + w*tau, Proc 6.5e
 6      miss <- haversine(g_lat, g_lon, x_B)
 7      if miss < best_miss : (best_miss, best_node) <- (miss, n)
 8  return (best_node, best_miss)
```

Line 5 must use the **exact spherical** shift when `|w|·τ > D_shift = 300 km` (Lemma 6.15),
which for a routing-scale voyage is essentially always.

**The root find remains useful** for *reporting* `t*` and would be the right method in a
continuum implementation; it is simply not the production goal-selection path.

**Sign convention (`S8b` cause 3).** `ground_position` is `x = y + w t`; `comoving_position` is
`y = x − w t`. Swapping them puts the landfall `2|w|t*` away — **twice** the dilation distance,
a distinctive signature worth recognising on sight.

### D14 — Forecast horizon exceeded mid-voyage

**Condition.** `t > horizon` during evaluation.

**Required behaviour, normative (`ERRATA E5`).**
1. **Persist the final frame.** This is the normative convention; the alternative (refuse) is
   available and must be offered as an option, but persistence is the default because a 14-day
   voyage against a 10-day forecast is the normal case, not the exception.
2. **Set `beyond_horizon` on the returned `Env`** and **count** the horizon-truncated
   evaluations. The run log must report how many.
3. **Truncate the wait relaxation's search interval.** `Eq (E5.1)`:
   ```
   F̃_ℓ(x,t,u) := inf over s ∈ [0, S_max(t)] of [ s/ℓ + F(x, t+s, u) ]        (E5.1)
   S_max(t)    := (t₀⁻ + H_fc) − t
   ```
   The unbounded `inf_{s≥0}` of the earlier draft requires `F` beyond the forecast horizon,
   which **does not exist**. Note also the scaling: the penalty denominator must be the **same
   `ℓ` the update uses**, not `h`. With `s/h` against a multiplier `ℓ ≤ Υ·h`, the waiting penalty
   is over-charged by a factor up to `Υ` and the result is *not* the running infimum, so
   unconditional causality does not follow.
4. **Report the fraction of the route beyond horizon** alongside the certificate. A certificate
   computed on a persisted field certifies the *model*, not the weather.

**The trap.** Past the horizon a persisted field is constant in time, so `L_t = 0` there, so the
causality condition `r(x)·L_t ≤ 1` holds **trivially**. An implementation that reports
`max_x r(x)·L_t` over the whole voyage will report a comfortable green margin that is an
artefact of the **persistence policy, not a property of the weather**. Report `L_t` restricted
to `t ≤ horizon` separately, and report the beyond-horizon fraction next to it.

**Under the co-moving reduction this case largely disappears** from the main solve: the
co-moving field is a single snapshot with `horizon = +∞` by construction (Thm C.1b). It returns
in the residual corrector, where `R(x,t)` is a genuine time-dependent field.

### D15 — Assumption A2 fails: the weather system cannot be outrun

**Condition.** `|w| ≥ σ_min^w := inf_{y,|u|=1} σ_w(y,u)`, so the bracket expansion in the
interception search never finds `g(t) ≤ 0`.

**Why.** The proof of Thm C.1(c) needs `F_max^w·|w| = |w|/σ_min^w < 1` to make
`g(t) ≤ F_max^w|x_B − x_A| + (F_max^w|w| − 1)t` tend to `−∞`. Without it the bracket is
negative-slope-free and no zero need exist.

**Required behaviour.** Return `NONE` from the interception, and surface it as an explicit
**"the weather system cannot be outrun"** result — *the honest answer when A2 fails*, not a
timeout and not an unreachable-destination error. Report `|w|` and the computed `σ_min^w` so the
operator can see the margin.

**Bracket expansion, normative.** `hi ← 3600 s`, then `hi ← 1.7·hi` while `g(hi) > 0` and
`hi < t_max`, with `t_max = 30 days` default. Growth factor `1.7` reaches 30 days from 1 hour in
14 doublings — cheap, and slower than `2×` so the final bracket is tighter. If `g(hi) > 0` at
`t_max`, return `NONE`.

### D16 — Numerical hygiene at input validation

Checked **once**, at input, not in the inner loop:

| Input | Rejected when | Reason |
|---|---|---|
| `V_max_hull` | not finite, `≤ 0` | corrupt vessel record; Proc 6.1 returns 0 for every query |
| `P_MCR`, `P_ref` | `≤ 0` | ditto |
| `eta_D` | `≤ 1e-3` | division by it in `Eq (1.8)`; floored rather than raising, inside the loop |
| `q_min` | outside `(0, 1]` | throttle family is empty or inverted |
| `GM`, `k_xx`, `B` | `≤ 0` | `ω_φ = sqrt(g·GM)/(k_xx·B)` is NaN or infinite |
| `hs_limit` | `≤ 0` | `risk_level = H_s/hs_limit` divides by it |
| `t_max` | `≤ 0` or not finite | (6.45) gives a zero or infinite dilation |
| `ε` (Pareto) | `≤ 0` | Proc 6.9's boundary sequence does not increase |
| grid `nlon` | `≤ 2·max|dj|` | §6.8: the reference-column construction has no valid choice |
| `|φ|` of any endpoint | `> φ_hard = 89.9°` | §6.5.7 |

---

## §6.8 — Indexing traps

Indexing bugs in a routing solver are a distinct hazard class because they produce **converged,
sensible-looking routes**. The one documented in §6.8.2 was found by building the system, not by
reasoning about it, and it cost a factor of 74 in arrival time while the solver reported success.

### 6.8.1 The normative index algebra

```
Eq (6.46)   node id      n  =  i · nlon + j          i = latitude row (south to north)
                                                     j = longitude column (west to east)
Eq (6.47)   inverse      (i, j) = divmod(n, nlon)
Eq (6.48)   in_bounds    0 <= i < nlat  and  0 <= j < nlon
```

Row-major, latitude-major, **normative**. A port that transposes this will produce a solver that
works on a square grid and fails on a rectangular one — the worst kind of latent bug, because the
first test grid is usually square.

`is_water(i,j)` returns **false** for out-of-bounds `(i,j)`: the domain edge is a coast as far as
the solver is concerned. This keeps every caller's bounds check in one place and is normative.

### 6.8.2 THE TRAP: negative column indices in a per-row geometry cache

**The optimisation that creates it.** On a regular lat/lon lattice, the length and bearing of a
stencil leg depend on the **row** and the **offset**, never on the column. So the geometry can be
computed once per row and reused across all `nlon` columns — a real and necessary optimisation:
it turns `O(N · |stencil|)` haversine/bearing evaluations into `O(nlat · |stencil|)`, a saving of
a factor of `nlon` (hundreds).

**The bug.** The cache is built by evaluating `latlon(i, J_REF + dj)` for each stencil offset
`(di, dj)`, from some reference column `J_REF`. If `J_REF = 0`, then every **westward** offset
`dj < 0` produces a **negative column index**.

**Why it is silent.** In a language whose array indexing wraps negatives like a list index —
Python, and NumPy — `latlon(i, −1)` does not fault. It returns the longitude of the **last
column of the domain**. The "leg" from column `J_REF` to column `J_REF − 1` therefore spans the
**entire width of the domain** instead of one cell.

**Why it is not a boundary-only bug.** This is the part that makes it severe. Because the cache
is keyed on the **row alone** and reused for every column in that row, the corrupted geometry is
applied to **every westward leg in the entire row**, not merely to legs at the western edge. A
bounds check at the point of use would not fire, because the *use* sites `(i2, j2) = (i+di,
j+dj)` are all perfectly in bounds; only the *cache construction* went out of range.

**Measured consequences.**

| Quantity | Correct | With `J_REF = 0` |
|---|---|---|
| Westward leg length | **57.9 km** | **4 020 km** |
| Leg bearing | correct | **142° wrong** |
| Voyage arrival time | **141 h** | **10 419 h** |

The `4 020 km` is the diagnostic signature: it is the **width of the domain in longitude at that
latitude**, which is what a wrapped column index measures. A 74× arrival time is not subtle once
you look at it — but the route is a plausible curve on a map, and every intermediate quantity is
finite and positive.

**THE FIX, NORMATIVE.**

> **The reference column must satisfy `J_REF ≥ max |dj|` over the stencil, and the grid must
> satisfy `nlon > 2·max|dj|`.** Formally, with `Δ_j := max over the stencil of |dj|`:
> ```
> Eq (6.49)    J_REF := Δ_j ,     require   nlon  ≥  2·Δ_j + 1
> ```
> This guarantees `0 ≤ J_REF + dj ≤ 2Δ_j < nlon` for every offset, so no index in the cache
> construction is ever out of range in either direction.

For the 16-neighbour stencil
`{(±1,0),(0,±1),(±1,±1),(±2,±1),(±1,±2)}`, `Δ_j = 2`, so **`J_REF = 2` and `nlon ≥ 5`**. For the
anisotropy-adaptive ordered-upwind stencil, `Δ_j` grows with the local radius:
`Δ_j = ⌈ r(x) / (h·cos φ) ⌉ ≤ ⌈ Υ_loc / cos φ ⌉`, which at `Υ_loc = 12` and `φ = 40°` is `16`,
requiring `nlon ≥ 33`. Compute `Δ_j` from the actual stencil in use and validate `nlon` against
it at construction time (§6.7 D16).

**MANDATORY ASSERTIONS.** Two, both `O(1)` per cache entry, both of which would have caught this
instantly:

```
Eq (6.50)   assert  0 <= J_REF + dj < nlon           for every stencil offset  (construction)
Eq (6.51)   assert  leg_length(i, k)  <=  3·h        for every cached entry
```

(6.51) is the cheap invariant: the largest offset in the 16-neighbour stencil has
`sqrt(di² + dj²) = sqrt(5) ≈ 2.236`, and longitude compression only **shortens** legs, so `3h` is
a safe bound with 34 % margin. The bogus `4 020 km` against `3h = 84 km` fails it by a factor of
48. For an adaptive stencil, replace `3h` by `1.5·r(x)`.

**Per-language behaviour — know which one you are porting into.**

| Language | `array[-1]` | Consequence |
|---|---|---|
| **Python / NumPy** | wraps to the last element | **silent corruption** — this is where the bug was found |
| **C / C++** (raw pointer or `operator[]`) | undefined behaviour; usually reads adjacent memory without faulting | silent corruption, possibly *different* corruption per build |
| **Rust** (`Vec`/slice index) | panics | loud, immediate — the safe case |
| **Go** (slice index) | panics | loud, immediate |
| **Julia** | 1-based; `A[0]` and `A[-1]` both throw `BoundsError` | loud — but note the **1-based offset** must be applied consistently in (6.46)–(6.48), which is its own porting hazard |
| **C++ `std::vector::at`** | throws | loud, at a cost |

The lesson generalises past this one grid: **any negative index arising from an offset
computation must be bounds-asserted at the site where it is computed, not where it is used.** In
Python the two sites have completely different failure behaviour and only the first one can
detect the fault.

### 6.8.3 Related trap: the flat index and the inverse must be the same convention

`index(i,j) = i·nlon + j` and `unindex(n) = divmod(n, nlon)` are inverse **only** if `nlon` is
identical in both. A coarse grid (`ρ_c = 8` default, `H = ρ_c·h`) has a different `nlon`, and a
solver that carries both must never pass a coarse node id to a fine `unindex`. Normative: make
node ids **type-distinct** where the language permits (a newtype in Rust, a distinct struct in
Go/C++), or prefix-tag them where it does not. This costs nothing at run time and eliminates a
class of bug that produces — again — a converged, plausible, wrong route.

### 6.8.4 CONFLICT: the longitude midpoint across the antimeridian

The stationary sweep samples the environment at the **midpoint** of each leg:

```
sigma_of( 0.5·(lat + lat2) ,  0.5·(lon + lon2) ,  u )
```

Since `latlon()` returns longitudes wrapped to `(−π, π]`, a leg crossing the antimeridian has
`lon = +3.141` and `lon2 = −3.141`, whose arithmetic mean is **`0.0`** — the environment is
sampled on the **opposite side of the globe**, roughly 20 000 km away, for every leg crossing
the seam. The resulting `σ` is not merely inaccurate; it is a different ocean.

> **NORMATIVE fix.**
> ```
> Eq (6.52)   lon_mid  =  wrap_pi( lon + 0.5 · wrap_pi(lon2 − lon) )
> ```
> Latitudes need no such treatment (there is no seam in latitude within the domain restriction
> of §6.5.7).

This is present in the reference implementation and is recorded here as a defect to fix on port.
It is invisible in every Indian Ocean test case (the domain does not reach the antimeridian) and
would appear the first time KAIROS is run on a trans-Pacific voyage. **Adopting the
shifted-longitude storage frame of §6.4.3 removes it structurally** — in an unwrapped ascending
frame the arithmetic mean is correct by construction — which is the stronger fix and the
recommended one.

### 6.8.5 Related trap: `nearest()` clamps rather than raising

`nearest(lat, lon)` clamps out-of-domain points to the boundary. That is the right default (§6.7
D5) but it interacts badly with the co-moving reduction: `comoving_position(x_B, t)` for a large
`t` produces a point far outside the ground domain, and a clamp then returns a boundary node
whose `T` bears **no relation** to the query. The interception `g(t) = T_w(x_B − wt) − t` built
on clamped samples is not the function being root-found.

**Normative:** the interception evaluation must test in-bounds **explicitly** and return `+∞`
for an out-of-domain query, rather than relying on `nearest()`. This is one more reason the
production goal selection is Proc 6.7 (the `O(N)` scan), which never queries by position at all.

Note also the correct clamping rule for longitude when the domain does not wrap: an out-of-range
query must clamp to **whichever edge is nearer in angle**, not to whichever edge the sign of a
naive subtraction happens to pick. Take the offset modulo `2π` into `[0, 2π)` first, then compare
`gap_east = off − (nlon−1)·Δλ` against `gap_west = 2π − off`.

### 6.8.6 Related trap: the water mask and the coarse grid

The optimistic coarse solve (`Prop 4.11`, `Cor 4.12`) requires the coarse cell's cost to be a
**lower bound** on any fine path through it, including one that clips a corner. Design decision
**D5**: use `F_low(C, u) = min over the closed cell C dilated by the coarse spacing H`, and the
water mask must correspondingly be **dilated** (a coarse cell is water if **any** fine cell in
its dilated block is water). Indexing this dilation off by one cell makes the heuristic
inadmissible, and A* with an inadmissible heuristic returns suboptimal answers **quietly** —
`handbook/02-debugging-playbook.md` **S4** cause 2. The discriminating test: re-run with the
heuristic disabled (pure Dijkstra order); if the answer *improves*, the heuristic is
inadmissible, and the dilation is the first thing to check.

---

## §6.9 — Recommended tolerances

Every number has a justification. No magic numbers (`CONTRACT.md §5`). Values marked **[E]** are
inherited from `ERRATA.md` and are not this file's to change; values marked **[M]** are measured
in `CORE-THEOREM.md` or the handbook; the rest are derived here.

### 6.9.1 Machine and structural constants

| Symbol | Value | Unit | Justification |
|---|---|---|---|
| `u` | `1.110 223 024 625 157e-16` | — | `2⁻⁵³`, IEEE-754 binary64 unit roundoff |
| `R_E` | `6 371 000.0` | m | IUGG mean radius, **exact by definition** for KAIROS. Row 1 of G1 checks it: `2πR_E/4 = 10 007 543.398 010 286 m` |
| `c_geo` | `0.707 106 781 186 547 5` | — | `1/√2`, **[E]** Lemma E3.1: the infimum of the perpendicular distance from a node to any 8-connected accepted-front edge, attained on the diagonal pairs |
| `ℓ_min` | `c_geo · h` | m | **[E]** (E3.1). The update **must skip** any front point closer than this; that exclusion is what makes `Δ_min` a theorem rather than an assumption |
| `Δ_min` | `c_geo · h · F_min` | s | **[E]** (E3.1). Dial bucket width. Worked: `0.7071 × 27 800 m × 0.1149 s/m = 2 259 s` |
| `δ` (clamp margin) | `= Δ_min` | s | **[E]** (3.24c). Normative choice, deliberately introducing no new constant |
| `Υ_heap` | `12` | — | **[E]** (E2). Heap fallback trigger. The trigger is **anisotropy**, not `F_min` — E2 proves `F_min` is bounded below and does not approach zero |
| `ρ_c` | `8` | — | Coarse-grid ratio `H = ρ_c·h`. A coarse solve `64×` cheaper in nodes, still fine enough that the dilated-cell bound is not vacuous |
| `n_θ` | `72` | — | Support tabulation (**D2**). `5°` spacing gives `O((π/72)²) = 1.9e-3` relative sampling error on a convex indicatrix, below the ~1 % metrication floor **[M]** |
| `ε` (Pareto) | `0.02` | — | **[E]** (E7). Not a numerical tolerance: it is the approximation parameter of `Thm 5.2`. At `k = 3` and two decades of range it bounds labels at `Λ ≤ 234² ≈ 5.5e4`; **10–40 observed** after pruning **[M]** |

### 6.9.2 Root finds and iterations

| Symbol | Value | Unit | Procedure | Justification |
|---|---|---|---|---|
| `XTOL` | `8u·V` | m/s (relative) | 6.1 → 6.2 | §6.2.6: the composition requirement. Eight ulp is two bisections from the last representable bracket |
| `XTOL_abs` | `1e-4` | m/s | 6.1 standalone | 0.2 milliknot: two orders below what a helmsman holds, four below the metric's modelling error |
| `FTOL` | `1e-9 · P_avail` | W | 6.1a | 11 mW at `P_MCR = 11 MW`; an exact-hit shortcut, not a correctness bound (Lemma 6.1 does not use it) |
| `N_SCAN` | `32` | — | 6.1 | Resolves power excursions wider than `V_cap/32 = 0.265 m/s`. Limitation stated in §6.1.6 |
| `N_ROOT` | `60` | — | 6.1a | By (6.4), `2⁻³⁰ ≈ 9.3e-10` of the initial bracket even if every secant step is rejected |
| `V_EPS` | `1e-6` | m/s | 6.1 | Left end of the scan; `P_D → 0` as `V → 0` |
| `V_FLOOR` | `0.05` | m/s | 6.1 | No steerage way below this. The *operational* minimum is a ban, applied above Proc 6.1 |
| `Q_OVERLOAD` | `1.15` | — | 6.1 | MCR overload beyond 15 % is fiction |
| `EPS_RES` | `1e-11` | relative to `V` | 6.2 | `8e-11 m/s` cross-track slip ≡ `1e-11` rad heading. Physically meaningless, and reachable once §6.2.6 is applied |
| `EPS_RES_FB` | `1e-9` | relative to `V` | 6.2 fallback | Two orders looser: `G` carries the inner root find's error, and demanding `EPS_RES` of an already-difficult leg manufactures spurious infeasibilities |
| `N_FP` | `12` | — | 6.2 | Cor 6.2.1 gives 8 at the measured worst-case rate `K ≈ 3e-2` **[M]**; 4 iterations of margin. Reference code uses 10 (adequate, thin) |
| `N_BIS` | `60` | — | 6.2 fallback | `π·2⁻⁶⁰ = 2.7e-18` rad, below one ulp of `θ` |
| `τ_ζ` | `1e-3` | s | 6.3 | Arrival-time error budget for the inner minimisation: `1e-3 s` on a leg of `~1e4 s` is `1e-7` relative, five orders below the ~1 % metrication floor **[M]** |
| `tol_zeta` | `4.5e-4` | — | 6.3 | (6.18): `sqrt(2τ_ζ/A'')` with `A'' = O(1e4 s)` estimated from `r·F_max = 56 km × 0.175 s/m` |
| `N_GS` | `32` | — | 6.3b | Derived requirement is 16 (§6.3.4); doubled so the `tol_zeta` exit fires and the cap is a net |
| `N_NEWT` | `24` | — | 6.3c | Safeguarded: `2⁻²⁴ = 6e-8 < tol_zeta` even if **every** Newton step is rejected and replaced by a bisection |
| `INV_PHI` | `0.618 033 988 749 894 8` | — | 6.3b | `(√5−1)/2` **as a stored literal**, so the bracket sequence is bit-identical across platforms (§6.10) |
| `t_max` | `30` | days | interception | Default cap on the interception bracket; any voyage beyond it is a different problem |
| growth | `1.7` | — | interception | Reaches 30 days from 1 h in 14 steps; slower than `2×` so the final bracket is tighter |
| `tol_t*` | `1.0` | s | interception | **Reporting only** — the production goal selection is Proc 6.7, which needs no root find (§6.7 D13) |

### 6.9.3 Comparisons, floors and guards

| Symbol | Value | Unit | Justification |
|---|---|---|---|
| `SIGMA_FLOOR` | `1e-3` | m/s | §6.6.6. `86 m/day`; implies `F_max = 1000 s/m`, so one 28 km leg costs 324 days. Two orders below any useful progress, and it bounds the Dial bucket count via (E2.2). **Replaces the reference code's inconsistent `1e-9` and `1e-6`** |
| `ε_mono` | `1e-6` | s | §6.6.7. `30×` above Lemma 6.18's `3.5e-8 s` random-walk bound; `9` orders below `Δ_min ≈ 2 259 s` so it can never merge buckets. **Replaces the reference code's `1e-9`, which sits below the noise** |
| `ε_time` | `1e-6` | s | Same quantity, same value, by §6.6.7's final paragraph — two tolerances on one quantity is how a queue and a label set come to disagree |
| dominance on objectives `2..k` | **exact integer** | — | §6.6.5. Bucket indices from Proc 6.9 are integers; no epsilon exists or is needed |
| `EPS_COS` | `1e-9` | — | Proc 6.5d pole guard. `|cos φ| < 1e-9` is `|φ|` within `5.7e-8°` of the pole; a guard, not a solution (§6.5.7) |
| `φ_max` | `80°` | — | Domain restriction. `1/cos 80° = 5.76` keeps the *purely geometric* grid anisotropy comfortably under `Υ_heap = 12`, leaving room for physical anisotropy on top. **A modelling choice, not a theorem** |
| `φ_hard` | `89.9°` | — | Hard refusal for an endpoint. Above this the local frame is not merely ill-conditioned but meaningless |
| `D_shift` | `300` | km | Lemma 6.15, (6.31): above this the tangent-plane co-moving shift exceeds a tenth of a cell in error. Routing-scale `\|w\|t` is 5× this, so **the exact spherical form is effectively always required** |
| `R_SNAP` | `8` | cells | ~220 km at `0.25°`. Beyond that a snapped endpoint is a different voyage. Operational choice; log it |
| `T_p` floor | `1e-3` | s | Guards `ω_p = 2π/T_p` in calm cells. Caps `ω_p` at `6283 rad/s`, multiplied by `H_s = 0` |
| `η_D` floor | `1e-3` | — | A zero or negative quasi-propulsive coefficient is a corrupt record, not a physical state; refuse to divide by it without raising inside the inner loop |
| `max_expand` | `5e6` | nodes | Safety net. Reaching it must be **reported**, since a truncated sweep is indistinguishable from an unreachable destination (§6.7 D6) |

### 6.9.4 Acceptance thresholds (what a port must achieve)

| Quantity | Threshold | Source |
|---|---|---|
| Max error vs G2/G3 golden vectors | `< 1e-12` relative | `handbook/01-golden-vectors.md` — 12 significant figures |
| G1 distances and bearings | 12 significant figures | G1 |
| G1 round trip `destination(A, bearing(A,B), dist(A,B)) = B` | `1e-9` rad ≈ 6 mm | G1 |
| Max `\|dθ/dt\|` in a uniform flow (G4) | `< 1e-14` rad/s | G4 — Zermelo's formula has **all** partials zero in a uniform field, so `dθ/dt ≡ 0` identically |
| G4 arrival, `(0°N,0°E) → (0°N,5°E)`, `V_s = 7.2`, `c = (1.5,0)` | `555 974.633 2 / 8.7 = 63 905.130 3 s = 17.751 425 h` | G4 |
| G4 against the current | `97 539.409 3 s = 27.094 280 h` | G4 |
| G4 ratio vs closed-form anisotropy | `27.094 280/17.751 425 = 1.526 315 789 5 = 8.7/5.7` to all printed digits | G4 — two completely different code paths (a full sweep vs a one-line ratio); agreement to 10 figures is strong evidence both are right |
| Intermediate turns in a uniform current | **zero** | G4 — any emitted waypoint is a numerical artefact |
| Arrival error at `1.0° / 0.5° / 0.25°` | must **decrease** | G5; a plateau is the `S3` inconsistency diagnosis |
| Bucket-queue monotonicity violations | `0` | G5, `S1` |
| `fp_fallbacks` in calm water | `0` | §6.2.5 — the contraction is trivial there |
| Co-moving bijection residual, per leg | `≈ 1e-13` m/s | **[M]** `9.77e-14` measured, `CORE-THEOREM.md §4` |
| Co-moving `L_t` under A1 | **exactly `0.0`** | **[M]** Regime A, Test 8.10 — `0.0` at max, p99 and median, to the last bit |

**Two numbers a port should expect to reproduce, and one it should not.**
The end-to-end voyage `8.0 N 77.0 E → 12.6 N 43.5 E` (3 698 km great circle), `V_s = 7.2 m/s`,
cyclone at `(3.0, 1.0) m/s`, `0.25°` grid, 29 529 nodes, gives **141.2107 h** by ground-frame
time-dependent Dijkstra and **139.9963 h** by the co-moving reduction — agreement **0.860 %**,
inside the ~1 % fixed-stencil metrication floor, with the co-moving answer the *slightly faster*
of the two, consistent with it carrying no temporal sampling error **[M]**.
What a port should **not** expect to reproduce is the two-frame agreement converging under
refinement: it does not. Measured at `h = 24, 16, 12, 8, 6, 4, 3 km` the discrepancy was
`0.36, 0.15, 0.79, 0.92, 0.17, 0.98, 0.58 %` — **a fixed-stencil metrication error floor that does
not vanish as `h → 0`**, because a stencil with finitely many neighbours quantises heading and the
quantisation bias is `O(1/m²)` independent of `h`. The two frames quantise *differently* (their
optimal headings differ by the drift shift), so their errors do not cancel. **On a fixed-neighbour
grid, refinement buys nothing beyond ~1 %** — which is the measured motivation for the
continuum-heading semi-Lagrangian update of Proc 6.3, and the reason the two-grid comparison is
the wrong instrument for Theorem C.1 (the bijection test of `CORE-THEOREM.md §4` is the right one).

---

## §6.10 — Determinism and reproducibility

`00-overview.md` **L9** requires §6 to specify the tie-break rule and §8 to test determinism.
This section discharges that, and states honestly what is and is not achievable.

### 6.10.1 What is guaranteed

> **Guarantee R1 — run-to-run determinism on a fixed platform and toolchain.** Two runs of the
> same binary on the same input produce **bit-identical** routes, fronts, and diagnostics.

Requirements, all normative:

1. **`sample_env` is deterministic and side-effect free** (obligation O1, §6.4.1). No cache whose
   eviction changes a returned value; no hidden state; no dependence on evaluation order.
2. **Fixed summation order** in the trilinear blend (Lemma 6.13(c)) and in every reduction.
   Floating-point addition is not associative, so a parallel reduction over cells must either use
   a deterministic tree of fixed shape or be replaced by a sequential accumulation.
3. **The tie-break order (6.44)** decides every comparison that floating point leaves open. Every
   field in it is an integer.
4. **No parallel non-determinism in the queue.** If the sweep is parallelised, the set of nodes
   finalised at each wavefront must be determined by value, not by which thread arrived first;
   ties are broken by (6.44).

### 6.10.2 What is NOT guaranteed, and why

> **Not guaranteed — bit-identical output across platforms, compilers or libm versions.**

The reason is precise: IEEE-754 requires `+ − × ÷ sqrt` and `fma` to be correctly rounded, but
**does not require it of `sin`, `cos`, `asin`, `atan2`, `log`, `exp` or `pow`**. Implementations
differ in the last ulp. Every one of those appears in KAIROS: `asin` in the crab angle (6.6),
`atan2` in the bearing (Proc 6.5b) and in the wave direction recovery (Proc 6.4 line 18), `sin`
and `cos` throughout the geodesy.

**What survives across platforms, and how it is achieved:**

| Mechanism | What it protects |
|---|---|
| Proc 6.9 (boundary table by repeated multiplication + binary search) | Bucket assignment — the thing that decides which labels survive. Removes `log` and `pow` from the decision path entirely |
| `INV_PHI` as a stored literal | The golden-section bracket sequence, hence the `ζ` iterates, hence `A(ζ*)` |
| (6.23): sign tests on `R(ζ)`, never on `A'(ζ)` | Bracket decisions in Proc 6.3c |
| (6.44): integer tie-break | The identity of the surviving front |
| Proc 6.5f `wrap_pi` via exact `fmod` | Longitude arithmetic over large accumulated shifts |

> **The honest residual.** After all of the above, two platforms can still disagree if an
> objective value sits within `~1e-12` relative of a bucket boundary, or if two labels' times
> differ by less than `ε_time`. **This must be detected and reported, not assumed away.**
> Normative instrumentation: count values within `1e-10` relative of a bucket boundary
> (`near_boundary_count`) and label pairs within `10·ε_time` (`near_tie_count`). A nonzero count
> is not an error; it is a statement that the returned front is one of several equally valid
> `ε`-approximate fronts, and it must accompany any cross-platform comparison. A comparison of
> two implementations that ignores these counts is comparing tie-break conventions, not
> algorithms.

### 6.10.3 Mandatory instrumentation

Build these in **before** anything goes wrong (`handbook/02-debugging-playbook.md`, closing
section). They cost nothing and they are the difference between "it works" and "we know it works."

| Counter | What it catches |
|---|---|
| metric evaluations, and support-table cache hit rate | whether D2 is actually working |
| distribution of the inner minimiser's `ζ` | endpoint-pinned ⟹ the `ζ` search is broken and the scheme has degenerated to a fixed-neighbour stencil (**S3**) |
| stencil radius histogram | confirms the adaptive radius is adapting rather than saturating |
| bucket-queue `monotone_violations` | must be `0` (**S1**); with `ε_mono = 1e-6 s` a nonzero count is a real ordering bug, not rounding |
| `fp_iters_max`, `fp_fallbacks`, `fp_hard_failures` | Proc 6.2 health (§6.2.5). Fallbacks in calm water are a bug |
| labels per node: mean and peak (`Λ`) | the complexity bound, measured (E7.2) |
| clamp firing rate for `ρ_{jk}` | stands in for the unproved aggregate bound of `Remark 3.C.1` |
| cells needing wait relaxation, and `max_x r(x)·L_t` | the causality honesty metric. **`r(x)·L_t`, not `h·L_t`** — E4 |
| horizon-truncated evaluations, and route fraction beyond horizon | §6.7 D14 |
| `near_boundary_count`, `near_tie_count` | §6.10.2 |
| certificate gap `(J − T_low)/T_low` on the returned route | the headline number |
| nodes expanded vs nodes in domain | whether the heuristic is focusing the search |
| co-moving: `required_dilation`, achieved landfall miss, `\|w\|`, `σ_min^w` | §6.7 D12, D15 |

Print all of them at the end of every run.

**A sanity band for `r·L_t`.** `handbook/02-debugging-playbook.md` **S7**: if the wait relaxation
fires everywhere, the `L_t` estimate is almost certainly differencing across forecast frames
without dividing by the frame interval **in seconds**, inflating `L_t` by `~10⁴`. Expect
`h·L_t ≈ 0.05–0.15` on a `0.25°` grid with 3-hourly forecasts. Measured on the §8.2 field:
`L_t` `3.22e-07 → 1.24e-07` (`2.60×`) under the reduction, and `r·L_t` at `r = 2h = 55 km`
`0.0177 → 0.0068` **[M]**.

---

## §6.11 — What breaks without each assumption

Collected, because it is the question a referee asks and the question an implementer asks at
3 a.m. Each row names the assumption, where it is used, and the **observable** consequence of
its failure.

| Assumption | Used by | What breaks, observably |
|---|---|---|
| **A1** (frozen advection, `E(x,t) = E₀(x − wt)`) | Thm C.1, hence the whole co-moving path | The reduction is no longer exact. It remains a **preconditioner**: measured `r·L_t` `1.31 → 0.26`, moving a solve from *unlicensed* to *licensed*, `4.6–5.0×` at p99 **[M]**. **But the median regresses `4.5×`** — in the ground frame most cells are far from any system and see almost no change, whereas in the co-moving frame the sampling point slides through space so quiet cells now see the field vary. De-advection trades a large improvement in the worst cells for a modest degradation in benign ones. Because causality is a worst-case condition this is the right trade, but **it is a trade, and anyone reporting only the max is overselling it**. |
| **A2** (outrun, `\|w\| < σ_min^w`) | Thm C.1(c); the interception | `g(t)` no longer tends to `−∞` and no interception root need exist. §6.7 D15: return "cannot be outrun", not a timeout. |
| `\|c\| < V_max` (`Eq C.7`) | finiteness of `F` in every direction (E9 claim 2) | The reachable set becomes a cone (E1.1) and `F = +∞` outside it. Cells become one-sided. Correct behaviour, not an error — but a solver coding the `σ_max` test instead of the `V_max` test **never detects it** (E1). |
| `λ > 0` guard | (6.26) | `F` goes **negative** (T7 → `−1.25`), creating negative cycles: the sweep does not terminate, or terminates with an arrival time in the past. |
| `ℓ_min` exclusion (E3) | Dial correctness | The bucket width no longer bounds the minimum increment; the queue finalises a node whose value is later lowered; **the label-setting invariant is destroyed**. |
| `r(x)·L_t ≤ 1` (E4.1) | single-pass licence | Label setting is unsound: arriving later at a node can yield an earlier arrival downstream. The old form `h·L_t ≤ 1` is weaker by the factor `Υ` and reports a **green certificate on forecasts where the sweep is not licensed**. |
| Convexity of `conv 𝒱` (D4) | Lemma 6.9, Lemma 6.10, Lemma 6.12 | `A(ζ)` need not be convex; golden section may return a local minimum and Newton's bracket argument fails. The Hamiltonian cannot see non-convexity anyway (support function of a set equals that of its hull), so the **relaxed** problem is what is solved and the gap is certified by `Thm 2.11`. |
| Stationarity of `F` in `t` (Thm C.1b) | Lemma 6.9 exactly; Cor 6.9.1 approximately | `A(ζ)` is convex only up to (6.17), measured `≈ 86 s` in the ground frame at `r = 55 km` vs `33 s` co-moving vs **exactly 0** under A1. |
| Range preservation of the interpolant (O2) | `Eq (C.7)` admissibility test | Cubic interpolation overshoots by **6.25 %** on a step (§6.4.5), so `\|c\| = 6.8 m/s` becomes `7.225 > V_s = 7.2`: the Kropina branch fires and the solver **routes around a storm the forecast does not contain**. |
| Lipschitz constants bounded by data differences (O3) | the causality diagnostic and `Eq (C.10)` | `L_t` estimated from frames understates a spline interpolant's actual modulus; the reported margin is not a margin, one-sidedly. |
| Determinism of `sample_env` (O1) | `Thm 3.1`, the label-setting invariant | The sweep evaluates the same `(x,t)` from several front edges. A field with hidden state breaks the algorithm **silently**. |
| Strict monotonicity of `P_D(V)` | Proc 6.1's uniqueness | Not required — (6.3) is well-posed regardless, returning the **near** side of a power hump. What breaks instead is the `N_SCAN` sampling limitation (§6.1.6): a hump narrower than `V_cap/32` is missed. |
| Lipschitz `V(θ)` (Thm 6.2 (i)) | Proc 6.2's contraction | `K` is undefined and the iteration can cycle. **This is why bans are applied after the fixed point, not inside `attainable`** — IMO MSC.1/Circ.1228 thresholds are step functions in `(V, θ)`. |
| `V(θ) > \|c⊥\|` (Thm 6.2 (ii)) | Proc 6.2 | The `arcsin` argument leaves `[−1,1]`. Detected at Proc 6.2 line 5 and returned as infeasible (T8) — a routine condition in the Agulhas and Somali Current, **not** an exception. |
| Grid dilation by `\|w\|·t_max` (R1) | co-moving goal reachability | Fails **silently**: the sweep converges, the route looks plausible, the landfall is wrong. Measured **104.5 km**, irreducible by a full-grid scan **[M]**. |
| `J_REF ≥ max\|dj\|` (§6.8.2) | the per-row geometry cache | Westward legs become wrap-around legs: **4 020 km instead of 57.9 km**, bearing **142° wrong**, arrival **10 419 h instead of 141 h** **[M]** — with the corrupted geometry applied to *every* column in the row, not just at the edge. |
| Correctly rounded `+ − × ÷ sqrt` (no fast-math) | Lemma 6.13, 6.16, 6.17, 6.18 | Every error bound in §6.6 is void, and the golden-vector 12-figure criterion cannot be met. |

---

## §6.12 — Reading order for an implementer

1. **Proc 6.5** and the G1 table first. Geodesy errors contaminate everything downstream and the
   `2πR_E/4` self-check catches most of them in one line.
2. **§6.6.1 and the G2/G3 tables.** Get the Randers branch table right before anything else
   touches the metric; T7 and T8 must be reachable in your tests from day one.
3. **Proc 6.1, then Proc 6.2**, in that order, honouring §6.2.6 — they do not compose at the
   reference tolerances and the failure is a determinism failure, not an accuracy one.
4. **Proc 6.4**, with the shifted-longitude frame of §6.4.3 adopted from the start. Retro-fitting
   it means auditing every longitude subtraction in the codebase.
5. **§6.8** before writing the sweep. The per-row cache is a necessary optimisation and it has
   exactly one correct construction.
6. **Proc 6.3** last: it is the piece that distinguishes KAIROS from a graph search, and it is
   also the piece whose absence is invisible (the routes still look fine; only the refinement
   study exposes it — `S3`).

Then run G4. It requires no reference solution, is insensitive to grid resolution, and fails
loudly for transposed east/north, a wrong finite-difference frame, a `ζ` minimisation that is
not actually minimising, and any stencil that quantises heading. **If your router emits waypoints
in a uniform current field, those waypoints are numerical artefacts and everything downstream is
suspect.**

