# KAIROS Reference Specification — Authoring Contract

**This file is normative.** Every other file in `spec/` must conform to it exactly:
same symbols, same numbering, same interface signatures. Do not redefine anything here.

---

## 0. What KAIROS is (one paragraph, use this framing everywhere)

Ship routing under currents, wind and waves is the problem of finding a **geodesic of a
non-stationary Finsler metric** on the sphere, where the metric is the Minkowski gauge of
the set of achievable over-ground velocities (the *indicatrix*), and where seakeeping
regulations remove regions from that set. KAIROS solves it by **ε-Pareto anisotropic
ordered-upwind front propagation**: a single monotone sweep that carries vector-valued
labels, is licensed by a sharp causality condition, is accelerated by a locally-adaptive
stencil and a monotone bucket queue, and returns the entire Pareto front together with a
computable certificate of how far each returned route is from the true optimum.

---

## 1. Symbol table (NORMATIVE — never deviate)

### Geometry and state
| Symbol | Type | Meaning | Units |
|---|---|---|---|
| `R_E` | scalar | Earth radius, 6 371 000 | m |
| `x = (λ, ϕ)` | point | longitude, latitude | rad |
| `Ω` | set | navigable domain ⊂ S² | — |
| `t` | scalar | absolute time (seconds since epoch) | s |
| `t₀` | scalar | departure time | s |
| `𝐞_E, 𝐞_N` | frame | local east/north orthonormal frame | — |
| `u` | unit vector | direction of travel over ground, `|u| = 1` | — |
| `v` | vector | over-ground velocity | m/s |

### Controls
| Symbol | Type | Meaning | Units |
|---|---|---|---|
| `V` | scalar | speed **through water** (STW) | m/s |
| `θ` | scalar | true heading, `n(θ) = (sin θ, cos θ)` | rad |
| `q` | scalar | **throttle** = fraction of MCR, `q ∈ [q_min, 1]` | — |
| `𝐚 = (V, θ)` | control | the control pair; `V` is determined by `q` and conditions | — |

`q_min = 0.15` default (engine minimum stable load). **Throttle is a first-class control
dimension** — this is required for the fuel objective to be non-trivial. See §3 below.

### Environment (all functions of `(x, t)`)
| Symbol | Meaning | Units |
|---|---|---|
| `c(x,t)` | effective drift = surface current + leeway | m/s |
| `W₁₀(x,t)` | 10 m wind vector | m/s |
| `H_s, T_p, μ_w` | significant wave height, peak period, mean wave-from direction | m, s, rad |
| `S(ω, β)` | directional wave spectrum (optional, RAO path) | m²·s/rad |
| `d_b(x)` | bathymetric depth | m |

### Vessel
| Symbol | Meaning | Units |
|---|---|---|
| `L, B, T_d` | length between perpendiculars, beam, draft | m |
| `∇_d, C_B` | displaced volume, block coefficient | m³, — |
| `P_MCR` | maximum continuous rating (shaft) | W |
| `η_D(V)` | quasi-propulsive coefficient | — |
| `SFOC(P)` | specific fuel oil consumption | kg/(W·s) |
| `GM, k_xx` | metacentric height, roll gyradius | m |
| `ω_φ` | natural roll frequency `= sqrt(g·GM)/k_xx` | rad/s |
| `κ_L` | leeway coefficient | — |
| `A_T, C_X(ψ)` | transverse windage area, wind resistance coefficient | m², — |

### Derived core objects
| Symbol | Definition | Where |
|---|---|---|
| `𝒜(x,t)` | admissible control set after seakeeping bans | §1 of spec |
| `𝒱(x,t)` | **indicatrix**: achievable over-ground velocities `⊂ ℝ²` | Def 2.1 |
| `F(x,t,v)` | Finsler metric = Minkowski gauge of `𝒱` | Def 2.2 |
| `σ(x,t,u)` | **speed made good** in unit direction `u`; `F = |v|/σ(x,t,v/|v|)` | Def 2.3 |
| `𝔥(x,t,p)` | support function of `𝒱`, `= max_{v∈𝒱}⟨v,p⟩` | Def 2.6 |
| `Υ_loc(x,t)` | local anisotropy `= σ_max/σ_min` | Def 2.9 |
| `Υ` | global anisotropy `= sup Υ_loc` | Def 2.9 |
| `T(x)` | earliest-arrival value function | §3 |
| `L_x, L_t` | Lipschitz constants of `F` in `x`, `t` | (A2) |
| `F_min, F_max` | uniform bounds on `F` over unit directions | (A1) |
| `h` | fine grid spacing (metres, at the equator) | §4 |
| `H = ρ_c·h` | coarse grid spacing, `ρ_c = 8` default | §4 |
| `ε` | Pareto approximation parameter | §5 |
| `Λ` | labels retained per node | §5 |
| `τ_d` | minimum steering dwell time | §2 |

### Objectives (NORMATIVE ordering — index 1 is always time)
| Index | Symbol | Name | Accumulation |
|---|---|---|---|
| 1 | `J_T` | arrival time | `+` (and drives the queue order) |
| 2 | `J_G` | fuel mass burnt | `+` |
| 3 | `J_R` | risk | `+` (additive) **or** `max` (bottleneck) — both supported |
| 4 | `J_C` | comfort / MSI | `+` |

`k` = number of active objectives. `k = 3` is the default configuration.

---

## 2. Numbering (NORMATIVE — do not renumber)

Every file owns a fixed block. Reference across files freely using these numbers.

| Block | Owner file | Contents |
|---|---|---|
| §1, Def 1.x, Eq (1.x) | `01-formulation.md` | physics, controls, ban set, objectives |
| §2, Def 2.x, Prop 2.x, Eq (2.x) | `02-metric.md` | indicatrix, gauge, Randers, support-function tabulation, anisotropy |
| §3, Thm 3.x, Eq (3.x) | `03-causality.md` | HJB, FIFO theorem, sharpness, wait relaxation, costate/Zermelo |
| §4, Alg 4.x, Eq (4.x) | `04-algorithm.md` | the algorithm, data structures, bucket queue, stencil, pseudocode |
| §5, Thm 5.x | `05-multiobjective.md` | ε-Pareto labels, semiring conditions, bounds |
| §6, Proc 6.x | `06-numerics.md` | root finds, interpolation, tolerances, degeneracies |
| §7, Thm 7.x | `07-complexity.md` | complexity, parallelism, memory |
| §8, Test 8.x | `08-validation.md` | test vectors, analytic ground truth, protocol |

**Theorem names are fixed:**
- **Thm 3.1** Causality / FIFO condition
- **Prop 3.2** Sharpness of the FIFO condition
- **Thm 3.3** Wait relaxation restores causality unconditionally
- **Prop 3.5** Zermelo navigation formula / costate system
- **Thm 2.11** Realisability gap under dwell constraint
- **Prop 2.7** Support-function tabulation is exact for convex indicatrices
- **Thm 5.2** ε-Pareto approximation guarantee
- **Thm 5.3** Label-count bound
- **Prop 5.4** Admissible objectives = monotone semiring (covers `+` and `max`)
- **Prop 4.7** Locality of the ordered-upwind stencil
- **Prop 4.9** Correctness of the monotone bucket queue (Dial discipline)
- **Prop 4.11** Admissibility and consistency of the optimistic coarse heuristic
- **Cor 4.12** A posteriori optimality certificate
- **Thm 7.1** Convergence to the viscosity solution (Barles–Souganidis)
- **Thm 7.3** Total complexity

---

## 3. Design decisions already made (do not re-litigate; implement these)

**D1 — Throttle is an explicit control.** For the time objective alone the optimum is always
`q = 1`, so throttle is invisible; for fuel it is the dominant decision variable. Therefore
`𝒱(x,t)` is a **two-dimensional filled region**, not a curve, and each direction `u` carries a
one-parameter family of `(σ, fuel-rate, risk-rate)` triples indexed by `q`. The per-edge
optimisation is itself a small Pareto problem. Files must handle this; it is the single most
common thing routing papers get wrong.

**D2 — Support-function tabulation.** For each cell and forecast hour, precompute
`𝔥(x,t,p_j)` on `n_θ = 72` uniformly spaced directions `p_j`. For convex `𝒱` the gauge is
recovered exactly from the support function by duality, and the inner minimisation of the
update reduces to an `O(log n_θ)` binary search instead of `O(30)` metric evaluations. State
and prove this as **Prop 2.7**. This is the main inner-loop optimisation.

**D3 — Monotone bucket queue instead of a binary heap.** Because `F ≥ F_min > 0`, every edge
costs at least `Δ_min = h·F_min`, so a Dial-style bucket queue with width `Δ_min` is correct
and gives `O(1)` amortised queue operations, removing the `log N` factor. State and prove as
**Prop 4.9**. Fall back to a heap when `F_min` is not bounded away from 0 (strong-drift
cells).

**D4 — Convexify, then project.** Solve with `conv 𝒱` (the HJB Hamiltonian cannot see
non-convexity anyway — the support function of a set equals that of its hull), then run
notch projection and certify the gap with **Thm 2.11**.

**D5 — The coarse heuristic must be admissible across cell boundaries.** The naive
"min over the cell" construction is admissible only if the coarse edge cost also accounts for
paths that clip a cell corner. Use `F_low(C, u) = min over the *closed* cell C dilated by the
coarse spacing H`, and prove admissibility with the dilation included. **This fixes a real
gap in the earlier draft — do not copy the earlier version.**

**D6 — Grönwall, not naive Lipschitz, in Thm 2.11.** The tracking error between the relaxed
and dwell-constrained trajectories compounds along the route because the trajectories drift
apart; the correct bound uses a Grönwall argument and carries `exp(L_x v_max S)`, or must be
stated on a per-leg basis with explicit re-synchronisation. **The earlier draft's linear
bound is not justified as stated — derive it properly.**

**D7 — Everything language-agnostic.** No Python idioms in the spec. Pseudocode uses
explicit typed arrays, explicit loops, explicit memory layout. Any statement like "use a
dict" must instead specify the abstract data type and its required operations with
complexities.

---

## 4. Interface contract (NORMATIVE — the code must match these signatures)

The entire algorithm is written against **five** primitives. Anything a language can
implement these in, it can run KAIROS in.

```
# ---- environment ------------------------------------------------------------
sample_env(x: Point, t: Time) -> Env
    # Env = { c: Vec2, W10: Vec2, Hs: f64, Tp: f64, mu_w: f64, depth: f64 }
    # trilinear in (lon, lat, t); MUST be deterministic and side-effect free

# ---- vessel + seakeeping ----------------------------------------------------
attainable(vessel: Vessel, env: Env, theta: f64, q: f64) -> Option<f64>
    # returns V (speed through water, m/s) for throttle q and heading theta,
    # or NONE if the (V, theta) pair violates any seakeeping ban S1..S7.

rates(vessel: Vessel, env: Env, theta: f64, q: f64) -> (f64, f64, f64)
    # (fuel_rate kg/s, risk_rate 1/s, comfort_rate 1/s)

# ---- the metric -------------------------------------------------------------
sigma(x: Point, t: Time, u: UnitVec2, q: f64) -> f64
    # speed made good over ground in direction u at throttle q; 0 if infeasible.
    # THIS IS THE ONLY FUNCTION THE SOLVER CALLS. Everything above is behind it.

support(x: Point, t: Time, p: Vec2) -> f64
    # h_V(x,t,p) = max over v in conv V(x,t) of <v, p>.  Tabulated per D2.
```

Every algorithmic statement in the spec must be expressible using only these five.

---

## 5. House style for the spec files

- Every formula gets an equation number in its owning block.
- Every theorem gets: **Statement**, **Proof** (complete, not "sketch"), **Remarks** covering
  sharpness and what fails without each hypothesis.
- Every algorithm gets: **Input / Output / Invariant / Complexity**, then numbered pseudocode
  lines so the handbook can reference `Alg 4.3 line 7`.
- Every numerical constant gets a justification or a citation. No magic numbers.
- Where a claim is believed but unproved, write **Conjecture** and say so. Never dress a
  conjecture as a theorem.
- Prior art is cited by name and year inline. We are claiming novelty for the *combination*
  and for Thm 2.11, Thm 3.1/3.3, Thm 5.2/5.3 and Prop 4.9 as applied here — everything else
  is standing on named shoulders and must say so.

---

## 6. Files to produce

```
spec/
  CONTRACT.md            <- this file
  00-overview.md         contributions, related work, reading order
  01-formulation.md      §1
  02-metric.md           §2
  03-causality.md        §3
  04-algorithm.md        §4
  05-multiobjective.md   §5
  06-numerics.md         §6
  07-complexity.md       §7
  08-validation.md       §8
```
