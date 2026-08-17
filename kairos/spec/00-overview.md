# 0. Overview: problem, contributions, prior art, reading order

> ## ⚠️ SUPERSEDED — DO NOT IMPLEMENT FROM THIS FILE
>
> This file was written against the **previous** core, in which KAIROS was an assembly of
> known components (ordered upwind + ε-Pareto labels + a causality condition). An adversarial
> referee pass found **11 blocking errors and 18 major ones** in it, including two prior-art
> citations that killed its central novelty claims (Vladimirsky 2006; Kumar & Vladimirsky
> 2010).
>
> **It is retained only for its related-work survey (§0.3) and for provenance.** Its
> contribution list, its causality condition (`h·L_t`, too weak by a factor `Υ`), its bucket-
> queue justification, its realisability bound, and its finiteness lemma are all **wrong** and
> are corrected in `ERRATA.md` E1–E11.
>
> **Read instead:**
> - `CORE-THEOREM.md` — the actual core, the Co-Moving Reduction, with proof and measurements
> - `ERRATA.md` — the 11 blockers and their corrected statements
> - `01-` … `08-` — the specification proper, written against both of the above
>
> Where this file disagrees with any of those, they win.

**Status of this file.** `00-overview.md` owns numbering block **§0**. It states no theorem
and defines no symbol that is not already fixed in `CONTRACT.md §1`. Equations `(0.1)`–`(0.11)`
restate, for orientation, objects that are defined normatively in their owning files; where
this file and an owning file differ in appearance, **the owning file governs**. Theorem and
proposition numbers used here are references into other files and are exactly those fixed in
`CONTRACT.md §2`.

---

## 0.1 The problem

### 0.1.1 Control problem

A vessel moves on `Ω ⊆ S²` of radius `R_E = 6 371 000 m`, at position `x = (λ, ϕ)`, in the
local orthonormal frame `(𝐞_E, 𝐞_N)`. The free controls are the **throttle** `q ∈ [q_min, 1]`
and the **true heading** `θ`, with `n(θ) = (sin θ, cos θ)`. Speed through water is a
*dependent* variable: it is whatever the powering balance returns for that throttle in those
conditions,

```
V  =  attainable(vessel, Env(x,t), θ, q)   ∈ ℝ₊ ∪ {NONE}                         (0.1)
```

where `NONE` marks a `(V, θ)` pair excluded by a seakeeping ban (`S1`–`S7`, §1). The
kinematics are the vector sum of through-water velocity and effective drift `c(x,t)`
(surface current plus leeway):

```
ẋ(t)  =  V · n(θ(t))  +  c(x(t), t)                                              (0.2)
```

The admissible control set after bans is `𝒜(x,t)` (§1); the objectives are, in the normative
order of `CONTRACT.md §1`,

```
J_T = t_f − t₀                       arrival time                    (accumulate: +)
J_G = ∫ fuel_rate  dt                fuel mass burnt                 (accumulate: +)
J_R = ∫ risk_rate  dt   or   max_t risk_rate                         (+ or max)      (0.3)
J_C = ∫ comfort_rate dt              comfort / MSI                   (accumulate: +)
```

with `k` the number of active objectives, `k = 3` by default (`J_T, J_G, J_R`).

> **Problem P.** Given `x_A, x_B ∈ Ω`, a departure window `[t₀⁻, t₀⁺]`, a vessel model, and
> forecast fields on `Ω × [t₀⁻, t₀⁻ + H_fc]`, find `t₀` and a measurable control
> `(q(·), θ(·))` with `𝐚(t) ∈ 𝒜(x(t), t)` whose trajectory (0.2) steers `x_A → x_B` inside
> `Ω`, and which is **Pareto-optimal** for `(J_T, J_G, J_R, …)` — i.e. return the whole
> non-dominated set, not one scalarised representative.

### 0.1.2 The same problem as geometry

Push the control set forward through (0.2). The image is the **indicatrix**

```
𝒱(x,t)  :=  { V·n(θ) + c(x,t)  :  (V, θ) ∈ 𝒜(x,t) }  ⊂  ℝ²                       (0.4)
```

(Def 2.1). Two structural facts about `𝒱`, both consequences of the control constraint, and
both responsible for most of the design:

* **`𝒱` is a filled two-dimensional region, not a curve.** Because `q` ranges over
  `[q_min, 1]`, each heading contributes a whole segment of achievable ground velocities, and
  each direction `u` therefore carries a one-parameter family of `(σ, fuel-rate, risk-rate)`
  triples indexed by `q` (decision **D1**). Routing formulations that fix the speed to a
  service value make `𝒱` a translated circle and make the fuel objective a monotone function
  of time, which is exactly the degeneracy that renders the multi-objective problem cosmetic.
* **`𝒱` is compact but in general neither convex nor connected, and need not contain `0`.**
  The bans `S1`–`S7` cut wedges (surf-riding, `S3`) and *rings* (parametric roll, `S2`) out of
  the control set. Where `|c| ≥ max_θ V`, the origin leaves `𝒱` and there are directions that
  cannot be made good at all.

The **Minkowski gauge** of `𝒱`,

```
F(x, t, v)  :=  inf { τ > 0 : v/τ ∈ 𝒱(x,t) },     inf ∅ = +∞                     (0.5)
```

(Def 2.2) is positively 1-homogeneous in `v`, generally **not** absolutely homogeneous
(`F(x,t,−v) ≠ F(x,t,v)`), and finite in every direction iff `0 ∈ int 𝒱(x,t)`. Equivalently,
in terms of the **speed made good** `σ` (Def 2.3),

```
F(x, t, v)  =  |v| / σ(x, t, v/|v|),        σ(x,t,u) = max { s > 0 : s·u ∈ 𝒱(x,t) }  (0.6)
```

Time-optimal routing is then the statement that, for a path `x(·)` parameterised by any
monotone parameter `s ∈ [0, S]`, the clock is *slaved to the path* by

```
t'(s)  =  F( x(s), t(s), x'(s) ),      t(0) = t₀,      J_T[x] = t(S) − t₀        (0.7)
```

Both (0.7) and its value are invariant under reparameterisation, because `F` is
1-homogeneous in `x'` and the ODE is therefore invariant under `s ↦ ς(s)`.

> **The precise statement of the problem.** *Time-optimal routing is the search for
> geodesics of a non-stationary Finsler structure whose indicatrix is the control-constrained
> reachable-velocity set (0.4), with the clock coupled to the path by (0.7); the full problem
> is the Pareto-optimal version of this over `k` accumulated objectives.*

Two remarks that are not decoration.

**(R1) Strictly, (0.7) is not a Finsler length.** A Finsler length is
`∫ F(x(s), x'(s)) ds` with the integrand determined pointwise by the path. Here `F` depends
on `t(s)`, which itself depends on the whole history of the path, so `J_T` is a Volterra-type
functional: a Finsler length only for a *frozen clock*. It is well posed — (0.7) has a unique
solution because `F` is Lipschitz in `t` by (A2) — but the Bellman principle it satisfies is
the one for a system with time in the state. Everything that makes the algorithm cheap
depends on recovering a *single monotone sweep* despite this, which is what **Thm 3.1**
(causality) licenses and what **Thm 3.3** (wait relaxation) makes unconditional. This is the
structural difficulty of the problem and it is worth naming precisely rather than absorbing
into a phrase like "time-dependent metric".

**(R2) `σ` is throttle-maximised.** The interface exposes `sigma(x, t, u, q)`; the metric of
Def 2.3 uses

```
σ(x, t, u)  :=  max_{ q ∈ [q_min, 1] }  sigma(x, t, u, q)                        (0.8)
```

so that `F` in (0.6) is built from the *fastest* attainable speed made good, as the gauge
requires. The other throttle settings are not discarded — they are exactly what populates the
non-time objectives, and the per-edge choice of `q` is itself a small Pareto problem (D1,
resolved in §5).

### 0.1.3 The solver's entire view of the physics

Everything above collapses, for the solver, into the **five primitives** of `CONTRACT.md §4`:
`sample_env`, `attainable`, `rates`, `sigma`, `support`. No algorithmic statement anywhere in
this specification uses anything else. That is what makes the vessel model swappable (bulker
→ container ship → ferry) without touching the algorithm, and it is what makes a
reimplementation in C++, Rust, Julia or Go a matter of providing five functions.

---

## 0.2 Contributions

Stated so a referee can check them. Each entry says what is **new**, what is **assembled**
from named prior work, and — for the new ones — one sentence on why it was not already done.
Per `CONTRACT.md §5`, novelty is claimed **only** for the combination and for
**Thm 2.11, Thm 3.1, Thm 3.3, Thm 5.2, Thm 5.3, Prop 4.9**. Everything else stands on named
shoulders and says so.

### New

**C1 — Sharp causality condition for a time-dependent Finsler eikonal (Thm 3.1, Prop 3.2).**
The arrival map `Arr(t) = t + h·F(x, t, u)` is non-decreasing whenever `h·L_t ≤ 1`, and this
is sharp: at `h·L_t = 1 + η` an explicit single-cell counterexample makes waiting strictly
profitable and defeats every finalise-by-arrival-time algorithm (Prop 3.2).
*Assembled from:* the FIFO / consistency property of time-dependent networks
(Dreyfus 1969; Kaufman & Smith 1993), which is the graph-level statement of the same idea.
*New:* the condition is here **derived** from a physical field — it ties the grid spacing to
the temporal Lipschitz constant of the metric, so it is a quantity one *checks on the actual
forecast, cell by cell*, and reports with a margin, rather than a modelling hypothesis one
assumes. The sharpness construction is new in this setting.
*Why not already done:* the graph literature takes FIFO as an axiom about given edge-cost
functions and has no grid spacing to trade against; the level-set literature sidesteps
causality entirely by marching in `t` and pays the full CFL cost for the privilege.

**C2 — Unconditional causality by wait relaxation (Thm 3.3).**
`F̃(x,t,u) := inf_{s≥0} [ s/h + F(x, t+s, u) ]` yields an arrival map that is the running
infimum of `Arr` over `[t,∞)`, hence non-decreasing for *every* `L_t`, and whose value
function is exactly the optimum of the problem in which loitering is permitted.
*Assembled from:* waiting policies in time-dependent networks (Orda & Rom 1990), which
established that unrestricted waiting restores tractability on graphs.
*New — and deliberately weakened from the earlier draft:* what is new is the `h`-scaled
lower-envelope form, the identification of `F̃` with the loiter-augmented value function of
the *continuum* problem, and the fact that no state dimension is added because the envelope is
taken pointwise inside the metric. **We do not claim the idea "allow waiting to restore
FIFO"**; that is Orda & Rom's.
*Why the instantiation was not already done:* it requires the metric to be a function of
departure time in the first place, which only a time-indexed eikonal formulation gives you.

**C3 — Certified realisability gap under a steering-dwell constraint (Thm 2.11).**
The HJB Hamiltonian is the support function of `𝒱` and therefore cannot distinguish `𝒱` from
`conv 𝒱`; the viscosity solution is the value of the *relaxed* (chattering) problem, which a
real rudder cannot execute. Thm 2.11 bounds the cost of that discrepancy in terms of the
minimum dwell time `τ_d`, so KAIROS solves the convex relaxation (decision **D4**), projects
the recovered controls back onto `𝒜`, and *certifies* the loss.
*Assembled from:* relaxed-control / chattering approximation (Gamkrelidze 1978; Warga 1972)
and Carathéodory's theorem in the plane.
*New:* turning the chattering lemma into a **computable a-priori bound on route cost**, and
doing so with the correct Grönwall structure (decision **D6**): the two trajectories drift
apart, so the tracking error obeys `e' ≤ L_v e + v_max/τ_d`-type growth and the constant
carries `exp(L_v · J_T*)`, reducing to a linear-in-`S` bound **only** under explicit per-leg
re-synchronisation. The earlier internal draft asserted the linear form unconditionally; that
was not justified and is corrected in `02-metric.md`.
*Why not already done:* the routing literature either ignores non-convexity of the control
set or optimises over it heuristically; nobody needed the bound because nobody was carrying
the seakeeping bans as hard constraints in a variational formulation.

**C4 — Dial-discipline bucket queue proved correct for an ordered-upwind front (Prop 4.9).**
Because `(A1)` gives `F ≥ F_min > 0`, every semi-Lagrangian update advances the value by at
least `Δ_min = h·F_min`, so a monotone bucket queue of width `Δ_min` (decision **D3**) is
correct and gives `O(1)` amortised queue operations, removing the `log N` factor.
*Assembled from:* the bucket queue itself (Dial 1969).
*New (as applied):* the correctness argument is not immediate, because an ordered-upwind
update is **not** a graph edge relaxation — the "edge" is a segment from an arbitrary point
`ξ(ζ)` on an accepted-front edge, of length anywhere in `(0, r(x)]` with `r(x)` up to
`Υ_loc·h`. Prop 4.9 must therefore bound the update increment from below over that continuum,
not over a fixed neighbour set, and must specify the heap fallback when `F_min → 0` in
strong-drift cells.
*Why not already done:* OUM implementations use binary heaps because the `log N` is not the
bottleneck in their target applications; the uniform positive lower bound on `F` is available
here only because the ship model bounds the indicatrix, which is a physics input, not a
numerical one.

**C5 — ε-Pareto label setting on a continuum semi-Lagrangian front (Thm 5.2, Thm 5.3).**
Nodes carry sets of non-dominated vector labels; labels are pruned by geometric
ε-bucketing on objectives `2 … k`; Thm 5.2 gives the `(1+ε)`-factor guarantee against the
**true** Pareto front and Thm 5.3 bounds the label count `Λ` per node.
*Assembled from:* multi-objective label setting (Hansen 1980; Martins 1984), the
FPTAS-by-geometric-rounding argument (Papadimitriou & Yannakakis 2000; Tsaggouris &
Zaroliagis 2009), and monotone-semiring shortest paths (Prop 5.4; the algebra is classical —
Gondran & Minoux 1984; Mohri 2002).
*New (as applied):* in the graph FPTAS the exponent `D` is a hop count on a fixed graph; here
"segments" are front relaxations of a continuum update whose count is not a graph invariant,
so the rescaling `ε' = ε/D` needs a bound on `D` that comes from the geometry (`D ≤ S/(h)`
up to the stencil factor), and the `max`-accumulated objective does **not** compound — a point
we make explicitly rather than inheriting the pessimistic `+`-case bound for all objectives.
*Why not already done:* the two literatures are disjoint. Label-setting is done on graphs,
where the update is a fixed edge; ordered-upwind is done for a single scalar value function,
where the update is a minimisation. Carrying a *set* of vector labels through a
minimisation-based update is the technical merge, and the dominance test has to be applied
after the inner minimisation, not before it.

### Assembled — credited, not claimed

**C6 — Support-function tabulation as the inner loop (Prop 2.7, decision D2).**
Tabulating `𝔥(x,t,p_j)` on `n_θ = 72` uniformly spaced directions (5° resolution) makes the
gauge recoverable exactly for convex `𝒱` by conjugate duality, and reduces the inner
minimisation of the update to an `O(log n_θ)` binary search. The mathematics is textbook
convex analysis (Rockafellar 1970, §13); the contribution is that this is the main inner-loop
optimisation and that Prop 2.7 states its exactness rather than assuming it.

**C7 — Locally adaptive ordered-upwind stencil (Prop 4.7).**
Ordered upwind methods and the `Υ·h` search radius are Sethian & Vladimirsky (2003); the
observation that `Υ` is set by the worst cell in the domain while the median cell is nearly
isotropic, and the resulting fixed-point construction `r(x) = h·max_{B(x,r(x))} Υ_loc`, is a
refinement of their argument, not a new theorem. An alternative route to the same end is the
lattice-basis-reduction anisotropic fast marching of Mirebeau (2014); we do not claim ours is
superior, only that it is the one whose correctness argument localises most directly.

**C8 — Optimistic coarse heuristic and a posteriori certificate (Prop 4.11, Cor 4.12).**
`A*` with a consistent heuristic is Hart, Nilsson & Raphael (1968). Cor 4.12 —
`0 ≤ J(π) − J* ≤ J(π) − T_low(x_A)` for any route `π` — is elementary weak duality; we claim
only its systematic **emission as an output**, for arbitrary third-party or hand-drawn routes,
not its discovery. One real correction is embedded here (decision **D5**): the naive
"min over the open cell" construction of `F_low` is **not** admissible, because a fine route
may clip a coarse cell corner without having an interior point in it; `F_low` must be the
minimum over the *closed* cell dilated by `H = ρ_c·h` (`ρ_c = 8`), and Prop 4.11 proves
admissibility with the dilation included. The earlier internal draft omitted the dilation.

**C9 — Zermelo shooting polish (Prop 3.5).** Zermelo's navigation formula (Zermelo 1931) —
heading turns only in response to current *shear*, never to the current itself — supplies both
a second-order route polish and the sharpest available unit test: in a spatially uniform
current the optimal control is a constant heading, so **every waypoint a router emits in a
uniform flow is a numerical artefact**.

**C10 — Randers closed form as ground truth (Bao, Robles & Shen 2004).** For fixed
through-water speed and no bans, `𝒱` is a translated disc and `F` is a Randers metric with
`‖b‖_a < 1` exactly when `|c| < V`. We use this twice: as a fast path for benign cells, and —
more importantly — to validate against a *formula* rather than against another code (§8).

**C11 — Localised front repair on forecast update.** The dependency-closure reopen is the
D\*-Lite idea (Koenig & Likhachev 2002) transplanted onto a continuous anisotropic front. No
theorem is claimed beyond the closure argument in §4.

**C12 — Convergence to the viscosity solution (Thm 7.1).** Monotone + stable + consistent ⇒
convergence is Barles & Souganidis (1991), with the comparison principle for the Finsler
eikonal following from convexity and coercivity of the Hamiltonian (Crandall & Lions 1983).
We verify the three hypotheses; we do not claim the framework.

### The combination

**C13.** The claim of the paper as a whole is the *combination*: a single monotone sweep that
is simultaneously (i) continuous in heading, (ii) provably correct under anisotropy,
(iii) correct under time-varying fields with a checkable licence and an unconditional
fallback, (iv) vector-valued with a proven `(1+ε)` guarantee against the true — possibly
non-convex — Pareto front, (v) exact for bottleneck objectives, (vi) certificate-emitting,
and (vii) incrementally re-solvable. Each of (i)–(vii) exists somewhere in the literature.
No published method has more than three of them at once, and several pairs are in tension:
(ii) forces a wide stencil which fights (vii); (iv) multiplies the state which fights (iii);
(v) is invisible to the scalarisation that most implementations of (iv) rely on.

---

## 0.3 Related work, by approach

For each: what it gives, and precisely what it cannot do that KAIROS can. Being precise here
is a defence, not a courtesy — several of these methods are excellent within their scope.

### 0.3.1 Isochrone methods
*James (1957); Hagiwara (1989); Bijlsma (2001).*
Propagate a time front by fanning candidate headings from the current front and retaining the
outer envelope. **Gives:** anisotropy natively (it is a reachable-set construction, so the
metric never has to be symmetric), time-varying fields natively (the front carries its own
clock), and it is extremely cheap.
**Cannot:** guarantee convergence — the isochrone self-intersects in strong shear and the
standard remedies (sector pruning, envelope cleaning) are heuristic and grid-dependent; return
more than one objective; express a bottleneck objective; or certify anything. The failure mode
is silent: a pruned lobe is an optimal route thrown away with no record.

### 0.3.2 Graph search: Dijkstra / A\* on a lattice
*Dijkstra (1959); Hart, Nilsson & Raphael (1968); the baseline prototype in
`shiprouting/src/router.py`.*
**Gives:** simplicity, an admissible-heuristic speedup, exact optimality **on the graph**.
**Cannot:** shed the metrication error. On a lattice whose neighbour directions have maximum
angular gap `α_max`, a straight segment at angle `θ` inside a wedge spanned by unit lattice
directions `ê₁, ê₂` separated by `α` must be realised as `a·ê₁ + b·ê₂` with

```
a = sin(α−θ)/sin α ,   b = sin θ/sin α ,   a + b = [sin θ + sin(α−θ)]/sin α       (0.9)
```

maximised at `θ = α/2`, so the worst-case length ratio is

```
sup_θ (a+b)  =  2 sin(α/2)/sin α  =  sec(α/2)                                    (0.10)
```

giving `sec(π/8) − 1 = 8.24 %` for 8-neighbour and, for the 16-neighbour set whose widest gap
is `α = arctan(1/2) = 26.565°`, `sec(13.283°) − 1 = 2.75 %`. **This bound is independent of
`h`** — refining the grid does not remove it — and it is asymptotically attained as
(path length)/`h` → ∞. Under anisotropy it is a *lower* estimate of the true cost error,
because the two legs traverse directions of unequal metric cost. Additionally: time-dependence
must be handled either by bucketing time into the state (an `O(Δt_bucket)` error and a
state-space multiplication — exactly what `router.py` does with `time_bucket_h = 3.0`) or by
permitting reopenings (losing the `O(N log N)` bound); and multi-objective output via a weight
sweep recovers only the **convex hull** of the attainable set (Das & Dennis 1997), which is
precisely wrong here because safety constraints make the front non-convex.

### 0.3.3 Dynamic programming on a discretised state grid
*Bijlsma (1975); Calvert, Deakins & Motte (1991).*
**Gives:** time-dependence for free (time is the stage variable), anisotropy for free,
bottleneck objectives for free (`max` composes stagewise), and global optimality on the
discretisation.
**Cannot:** avoid the curse of dimensionality. The state is `(x, t)` at minimum and `(x, t, J_G,
J_R)` for a genuine Pareto solve; the grid is `O(N · n_t · ∏ n_i)`. There is also no
goal-direction: DP fills the whole reachable state space regardless of where `x_B` is. KAIROS
replaces the `t` dimension with the causality argument of Thm 3.1 (so `t` is *derived*, not
enumerated) and the objective dimensions with ε-buckets whose count is proven, not chosen.

### 0.3.4 Level-set and HJB methods
*Lolla & Lermusiaux (2014); Subramani & Lermusiaux (2016).*
This is the closest rigorous relative and the fairest comparison. The reachability front obeys
`∂φ/∂t + 𝔥(x, t, ∇φ) = 0` with `𝔥` the support function of `𝒱`, which is **exactly correct**:
continuous in heading, exactly anisotropic, natively time-varying, and convergent to the
viscosity solution.
**Cannot:** (i) prune toward the goal — it marches the *entire* domain forward in `t` at
CFL-limited steps whether or not the front is anywhere near `x_B`, so cost is set by the
domain, not by the route; (ii) return a Pareto front — it is single-objective, and the
energy-optimal variant handles a second objective by solving a parameterised family of
separate problems, which again only reaches the convex hull; (iii) express a bottleneck
objective, since `max_t` is not an integrand; (iv) re-optimise incrementally on a new forecast
— a level-set solve has no notion of a dependency closure to reopen; (v) accommodate a
throttle dimension or hard seakeeping bans, because the published formulations fix the
through-water speed, making `𝒱` a translated circle. KAIROS keeps (0.4)'s exactness while
solving for `T` directly in one monotone sweep — which is legitimate **only** under Thm 3.1,
and that is the price of admission.

### 0.3.5 Evolutionary / NSGA-II weather routing
*Deb, Pratap, Agarwal & Meyarivan (2002); Szłapczyńska & Śmierzchalski (2009);
Marie & Courteille (2009).*
**Gives:** continuous decision variables, arbitrary objectives (including bottleneck ones),
non-convex Pareto fronts (a genuine strength — this is the one prior family that reaches the
dents), and trivial handling of hard constraints by rejection.
**Cannot:** guarantee anything. There is no bound on the distance from the returned front to
the true front, no convergence proof, no reproducibility without seed control, and no
certificate. The KAIROS difference is not that we find non-convex front points — NSGA-II does
too — it is Thm 5.2: our front is within a **proven** `(1+ε)` factor on every objective
simultaneously. That is the entire distinction, and it should be stated that narrowly.

### 0.3.6 Zermelo navigation and Finsler geometry
*Zermelo (1931); Randers (1941); Bao, Robles & Shen (2004); Bao, Chern & Shen (2000).*
**Gives:** the exact identification of navigation-under-drift with Randers metrics
(`F = √(a_ij v^i v^j) + b_i v^i`, admissible iff `‖b‖_a < 1`), closed-form geodesics for
uniform and simple-shear flows, and Zermelo's heading ODE.
**Cannot:** accommodate a heading-dependent, throttle-parameterised, ban-punctured indicatrix
— the Randers correspondence requires `𝒱` to be a translated *ellipse*, which fails the moment
waves dent it or `S2` rings it. We use the Randers case as the analytic ground truth in §8 and
as a fast path in benign cells, and we treat the general case numerically.

### 0.3.7 Ordered upwind and anisotropic fast marching
*Tsitsiklis (1995); Sethian (1996); Sethian & Vladimirsky (2003); Mirebeau (2014).*
**Gives:** the correct fix for anisotropy — plain fast marching is *silently non-convergent*
when `Υ > 1`, because the characteristic through `x` need not pass through the simplex spanned
by `x`'s immediate neighbours — at cost `O(Υ N log N)`, together with the Barles–Souganidis
convergence proof.
**Cannot:** handle time-dependent metrics (the static HJ setting has no clock), vector-valued
labels, or bottleneck objectives. KAIROS's stencil is theirs, localised (Prop 4.7); the
time-dependence and the labels are what is added on top, and neither is a small addition to
their proof.

### 0.3.8 Time-dependent shortest paths
*Dreyfus (1969); Kaufman & Smith (1993); Orda & Rom (1990); Dean (2004).*
**Gives:** the FIFO/consistency property as the necessary and sufficient condition for
label-setting to survive time-dependence, and waiting policies as the repair when it fails.
**Cannot:** say anything about a continuum. FIFO is stated for given arc-delay functions on a
fixed graph; there is no grid spacing, no metric, no anisotropy and no notion of a
characteristic direction. Thm 3.1 is the continuum instantiation with the constant made
explicit and checkable against a forecast.

### 0.3.9 Multi-objective label setting
*Hansen (1980); Martins (1984); Papadimitriou & Yannakakis (2000);
Tsaggouris & Zaroliagis (2009).*
**Gives:** exact Pareto label setting (worst-case exponential in label count) and the
geometric-rounding FPTAS that tames it, with monotone semirings covering both `+` and `max`
accumulation.
**Cannot:** be applied to a minimisation-based update. Every result in this family assumes the
extension operator is "traverse edge `e`", a fixed map. The KAIROS update (§4) minimises over a
continuum of departure points `ξ(ζ)` on an accepted-front edge, so the label extension is
`arg min`-valued and dominance must be re-tested after the inner solve. Thm 5.2 and Thm 5.3
are these results restated in that setting.

---

## 0.4 Comparison

**Legend.** ● = yes, with a proof; ◐ = partial or heuristic; ○ = no. "Anisotropy-correct"
means convergence is proved for `Υ > 1`, not merely that the code runs. "True Pareto front"
means non-convex portions are reachable. "Certificate" means a computable bound on the
suboptimality of the *returned* route.

| Method | Continuous headings | Anisotropy-correct | Time-varying fields | True Pareto front | Bottleneck objectives | Optimality certificate | Re-optimisation cost |
|---|---|---|---|---|---|---|---|
| Isochrone (James 1957; Hagiwara 1989) | ◐ heading fan, refinable | ◐ native, unproved | ● native | ○ | ○ | ○ | full re-run |
| Graph A\*/Dijkstra, 8–16 nbr (Dijkstra 1959; Hart et al. 1968) | ○ fixed `sec(α/2)−1` error, (0.10) | ○ metric asymmetry unmodelled | ◐ time bucketed into state | ○ convex hull only (Das & Dennis 1997) | ○ under scalarisation | ◐ heuristic gap, rarely emitted | full re-run (D\*-Lite retrofit possible) |
| State-grid DP (Bijlsma 1975) | ○ control discretised | ● | ● stage variable | ◐ state explodes | ● | ○ | full re-run |
| Level-set HJB (Lolla & Lermusiaux 2014) | ● | ● | ● native | ○ single objective | ○ `max_t` not an integrand | ○ | full re-run |
| Evolutionary / NSGA-II (Deb et al. 2002) | ● | n/a — no metric discretisation | ● | ◐ found, never bounded | ● | ○ | warm start, unbounded |
| Isotropic fast marching (Sethian 1996) | ● | ○ silently non-convergent | ○ | ○ | ○ | ○ | full re-run |
| OUM / anisotropic FM (Sethian & Vladimirsky 2003; Mirebeau 2014) | ● | ● | ○ static HJ only | ○ | ○ | ○ | full re-run |
| MO label setting on a graph (Martins 1984; Tsaggouris & Zaroliagis 2009) | ○ graph | n/a | ◐ FIFO assumed | ● `(1+ε)` bounded | ● | ○ | full re-run |
| **KAIROS** | ● continuum `ζ`-minimisation, §4 | ● Prop 4.7, Thm 7.1 | ● Thm 3.1 checkable + Thm 3.3 unconditional | ● Thm 5.2, `(1+ε)` on every objective | ● Prop 5.4, `max` semiring | ● Cor 4.12, for any route incl. third-party | `O(|closure(S)|·Λ)`, §4.7 |

**Two honest qualifications on the last row.** (i) The `●` for time-varying fields is
conditional in the following precise sense: under `h·L_t ≤ 1` the sweep is exact; where that
fails, Thm 3.3 restores exactness **for the loiter-augmented problem**, which is a
*different* problem — a strictly larger admissible set. If loitering is contractually
forbidden (laycan windows, charter-party terms), the wait-relaxed value is a lower bound, not
an achievable one. (ii) The `●` for the Pareto front is `(1+ε)`, not exact; exact Pareto label
setting is worst-case exponential and we do not attempt it.

---

## 0.5 Reading order and dependency graph

### 0.5.1 Files

```
CONTRACT.md          normative: symbols, numbering, interfaces, design decisions D1–D7
00-overview.md       §0   this file: problem, contributions, prior art, limitations
01-formulation.md    §1   physics, controls, powering, seakeeping bans S1–S7, objectives
02-metric.md         §2   indicatrix, gauge, Randers, support-function tabulation, Υ, Thm 2.11
03-causality.md      §3   HJB, Thm 3.1 FIFO, Prop 3.2 sharpness, Thm 3.3 wait, Prop 3.5 Zermelo
04-algorithm.md      §4   the sweep, stencil, bucket queue, heuristic, certificate, pseudocode
05-multiobjective.md §5   ε-Pareto labels, semiring conditions, Thm 5.2, Thm 5.3
06-numerics.md       §6   root finds, interpolation, tolerances, degeneracies
07-complexity.md     §7   Thm 7.1 convergence, Thm 7.3 complexity, parallelism, memory
08-validation.md     §8   analytic ground truth, test vectors, protocol
```

### 0.5.2 Dependency graph

An arrow `A → B` means: *B cannot be read, or its proofs cannot be checked, without A.*

```
                         CONTRACT.md
                              │  (normative for all)
                              ▼
                        01-formulation
                         (𝒜, S1–S7, J_i)
                              │
                              ▼
                          02-metric ─────────────────────────┐
                    (𝒱, F, σ, 𝔥, Υ, Thm 2.11)                │
                          │      │                           │
              ┌───────────┘      └───────────┐               │
              ▼                              ▼               │
        03-causality                    06-numerics          │
   (HJB, Thm 3.1/3.3, Prop 3.5)   (root finds, interp)       │
              │                              │               │
              └──────────────┬───────────────┘               │
                             ▼                               │
                       04-algorithm ◄────────────────────────┘
              (sweep, Prop 4.7/4.9/4.11, Cor 4.12)
                             │
              ┌──────────────┴───────────────┐
              ▼                              ▼
      05-multiobjective                 07-complexity
     (Thm 5.2/5.3, Prop 5.4)          (Thm 7.1, Thm 7.3)
              │                              │
              └──────────────┬───────────────┘
                             ▼
                       08-validation
                (02 Randers · 03 Zermelo · 05 · 07)
```

Back-edges that exist but are not structural: `04` uses the `Υ_loc` table built in `02`;
`07`'s Thm 7.1 needs the consistency expansion of the `04` update and the FIFO hypothesis from
`03`; `08` needs the closed forms of `02` and `03` for ground truth. `06` is a leaf for
mathematical purposes and a hard dependency for implementation purposes — every `min` in `04`
and `05` is realised by a procedure in `06`.

### 0.5.3 Reading orders

| Reader | Path |
|---|---|
| **Implementer** (writing C++/Rust/Julia/Go) | CONTRACT → §1 → §2 → **§6** → §4 → §5 → §7 → §8. `§6` before `§4` because every inner minimisation in `§4` is a procedure specified in `§6`; skip `§3`'s proofs on a first pass but implement the `h·L_t` guard and the wait branch from §3's statements. |
| **Referee checking correctness** | CONTRACT → §0 → §3 → §5 → §7 → §2 (Thm 2.11) → §4 (Prop 4.9, 4.11). The load-bearing claims are Thm 3.1/3.3 (is the sweep legitimate?), Thm 5.2 (is the front what you say it is?), Thm 7.1 (does it converge?). Everything else is engineering around those three. |
| **Naval architect / domain reviewer** | §1 in full → §2.1–§2.3 → §8. The question you are being asked is whether `𝒜` and `rates` are right; the rest is geometry on top of your answer. |
| **"Is it fast?"** | §7 → §4.3 (stencil) → §4.5 (heuristic) → §0.6 below, which says which of the speed claims are measured and which are not. |

---

## 0.6 Limitations and threats to validity

Stated before a referee states them. Each item names what breaks and what would fix it.

**L1 — Performance claims are targets, not results.**
No number in this specification describing speed, expansion reduction, label count in
practice, or re-optimisation saving is a measured result at the time of writing. The stencil
saving from Prop 4.7, the expansion reduction from the coarse heuristic (Prop 4.11), the
practical `Λ`, and the incremental re-solve saving are all **hypotheses**, and §8 is the
protocol that tests them. Earlier internal drafts quoted specific multipliers (`≈3.3×`
stencil, `5–20×` expansion, `20–50×` re-optimisation, "under 20 s cold"); those are removed
here and must not be reintroduced without a measurement. The *complexity* results (Thm 7.3)
are proved and stand independently of any measurement.

**L2 — Deterministic forecast; uncertainty is not modelled as uncertainty.**
Everything is conditional on one forecast realisation. The natural object for an ensemble is a
risk measure such as CVaR, and **static CVaR is not time-consistent**, so it breaks the
dynamic programming principle on which every result in §3, §5 and §7 rests. The correct repair
is nested (dynamic) CVaR, which restores time-consistency at the cost of an extra state
dimension and a corresponding multiplication of `Λ`. This is scoped as future work, not
claimed as done. A cheap partial mitigation available now — run the sweep per ensemble member
and intersect the ε-Pareto fronts — is *not* the same thing and does not inherit Thm 5.2.

**L3 — Physical model error almost certainly dominates numerical error.**
The default powering stack (Admiralty-form `P_calm`, STAwave-1 added resistance per ISO 15016,
Fujiwara 2006 wind coefficients, Ochi 1964 slamming, and the advisory criteria of
IMO MSC.1/Circ.1228 2007) carries an uncertainty on `σ` that is plausibly 5–15 %, whereas the
discretisation error is `O(h)` with `h ≈ 28 km` and the ε-Pareto loss is `O(ε)` with `ε` of
order `10⁻²`. **A geodesic computed to three digits in the wrong metric is still the wrong
route.** Three specific model weaknesses: STAwave-1 is validated for head-ish seas and
moderate `H_s/L`, and is extrapolation elsewhere; MSC.1/Circ.1228 is advisory guidance keyed
to the peak period `T_p` rather than the full directional spectrum `S(ω, β)`, so the ban
boundaries are sharp edges drawn on a fuzzy phenomenon; and `SFOC(P)` is a shallow U in engine
load whose minimum position is engine-specific and rarely published. The honest framing of the
contribution is therefore *"correct optimisation of a stated model"*, and §8 must report
sensitivity of the returned front to perturbations of the model, not only grid refinement.

**L4 — Thm 2.11 certifies cost, not admissibility, and its constant is exponential in
general.** Solving the convex relaxation (D4) may command a literally banned heading; the
notch projection restores admissibility and Thm 2.11 bounds what that costs. But per D6 the
Grönwall constant carries `exp(L_v · J_T*)`, which for a long voyage in a strongly sheared
field is not small. The linear-in-`S` form requires per-leg re-synchronisation, i.e. an
additional structural assumption on the projected trajectory. Where the exponential constant
is vacuous, the certificate degrades to "the relaxed value is a lower bound" — still true,
still usable via Cor 4.12, but no longer a tight gap.

**L5 — `(A1)` fails in strong-drift cells and the guarantees localise.**
Where `|c| ≥ σ_max`, `0 ∉ 𝒱`, the metric is one-sided (Kropina-type rather than Randers),
`F = +∞` in a cone of directions, `Υ_loc = ∞`, and `F_min → 0` so the Dial bucket width
degenerates and Prop 4.9's queue must fall back to a heap (D3). All statements in §3–§7 hold
on the subdomain where `(A1)` holds, with `F = +∞` treated as an excluded direction; the a
priori error constant of the ordered-upwind scheme degrades in the transition band. This is
not a corner case invented for completeness — western boundary currents (Agulhas; the Somali
Current in the southwest monsoon, Schott & McCreary 2001) reach surface speeds of order 2 m/s
and above, which is a substantial fraction of a slow bulker's through-water speed.

**L6 — `(1+ε)` compounds along the route, and the fix inflates the label count.**
Thm 5.2's guarantee is `(1+ε')^D` over `D` extensions; the uniform `(1+ε)` statement requires
`ε' = ε/D`, and by Thm 5.3 the label bound `Λ` grows like `(log range / log(1+ε'))^{k−1}`, so
tightening `ε'` by `D` inflates `Λ` polylogarithmically in a way that is benign in the bound
and may not be benign in cache. The compounding is worst-case and requires an adversarial
instance; the empirical loss is directly measurable by running at `ε` and at `ε/4` and
comparing fronts (§8), and until that is run we should quote the worst case. Note the
asymmetry worth exploiting: for a **`max`-accumulated** objective the bucket loss does **not**
compound, because `max` of bucketed values is bucketed by the same single factor — so
bottleneck risk is `(1+ε)`-accurate outright.

**L7 — Departure-time optimisation is not inside the sweep.**
Problem P asks for `t₀` as well as the control. The sweep solves for a *fixed* `t₀`; sweeping
the departure window means repeating the solve, and the returned Pareto front is then a union
over `t₀` values, which is correct but not certified as the optimum over a *continuum* of
departure times. Adding `t₀` as a state dimension is straightforward and expensive; sampling
it is what we do. This should be stated in any results table as "front over the sampled
departure grid".

**L8 — Geometry and topology of the grid.**
Three distinct risks. (i) The local-frame planarisation (§1) is exact only to `O((h/R_E)²)`
per cell, and the ordered-upwind stencil is constructed in the tangent plane; near the poles
the lat/lon grid degenerates in longitude and the effective `h` becomes anisotropic
*for reasons unrelated to the physics*, so the domain must be restricted (a bound such as
`|ϕ| ≤ 70°` is a modelling choice, not a theorem). (ii) At `h ≈ 0.25°` a strait narrower than
one cell is topologically closed by the land mask, and a shoal narrower than one cell is
topologically open — the first loses an optimal route silently, the second returns an
inadmissible one. This is a **correctness** failure, not an accuracy failure, and no amount of
convergence theory touches it; the mitigation is a separate high-resolution channel graph
stitched into `Ω`, which is out of scope here. (iii) `d_b(x)` under-keel clearance is applied
as a hard mask, so tidal windows in shallow approaches are not represented.

**L9 — Reproducibility of the returned front.**
The inner minimisations (golden section / Newton on `ζ`, the `V_pwr` root find, the throttle
sub-Pareto) terminate at finite tolerance, so near-ties in dominance tests are decided by
floating-point noise. Without a specified deterministic tie-break the returned front is not
bit-reproducible across compilers or thread counts, which would make the `ε`-vs-`ε/4`
experiment of L6 unreadable. §6 must specify the tie-break rule and §8 must test determinism
explicitly; this is called out here because it is the kind of thing that is discovered late.

**L10 — Open: no rate for the joint `(h, ε) → 0` limit.**
Thm 7.1 gives convergence in `h` for each fixed scalar objective; Thm 5.2 gives `(1+ε)` in the
objectives for fixed `h`. Letting both go to zero recovers the exact Pareto front in the
limit, but **we have no rate for the joint limit and do not claim one.** Stated as a
*Conjecture* in §7: the joint error is `O(h) + O(ε)` with no cross term under the standing
assumptions. What is missing for a proof is a stability estimate for the ε-pruned label set
under perturbation of the metric — i.e. that ε-bucketing commutes with the `h → 0` limit
uniformly — and we have not established it.

**L11 — Prop 3.2 (sharpness) is a statement about the discrete scheme.**
It exhibits a metric and a cell on which `h·L_t > 1` defeats finalise-by-arrival-time. It does
**not** claim that the underlying continuous problem is ill-posed there — it is not; it claims
that the *one-pass sweep* is the wrong algorithm there, which is why Thm 3.3 exists. Do not
let the two statements blur in the abstract.
