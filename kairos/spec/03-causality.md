# §3 — Causality: the eikonal, the FIFO obstruction, and why it is frame-dependent

**Status of this file.** It owns block `§3` of CONTRACT §2: `Thm 3.x`, `Prop 3.x`, `Def 3.x`,
`Eq (3.x)`. It is normative for those objects. Where it disagrees with `CONTRACT.md` it is
because `ERRATA.md` or `CORE-THEOREM.md` overrides the CONTRACT; every such place is marked.

**Read this before reading the rest.** In the first draft of KAIROS, §3 was the heart of the
method: the causality condition was what licensed a single-pass solve of a time-dependent
problem, and the wait relaxation was what repaired it where it failed. Two things have since
happened.

1. `ERRATA.md` §E10 established that the causality condition for single-pass solution of
   time-dependent control problems is **not new**. It is Vladimirsky (2006), *Static PDEs for
   time-dependent control problems*, twenty years old. §3.8 states precisely what of this file
   is ours and what is his; the honest residue is narrow.
2. `CORE-THEOREM.md` established the **Co-Moving Reduction** (Thm C.1). In coordinates
   `y = x − w t` moving with the weather, the routing problem is *exactly autonomous*, so the
   temporal Lipschitz constant `L_t` — the entire content of the causality condition — is
   **identically zero**, and the condition holds vacuously. The obstruction this file was
   written to overcome is an artefact of the ground frame.

So the hierarchy of this file is:

- §3.1–§3.3 are **formulation**: the stationary Finsler eikonal, the derivation (not the
  assertion) of the sign of the non-stationary level-set HJB, and the check that the Randers
  case reproduces the Zermelo eikonal of Lolla & Lermusiaux (2014). These are needed by every
  other block and are not claimed as novel.
- §3.4–§3.7 are the **causality apparatus**: `Def 3.4`, `Thm 3.1`, `Prop 3.2`, `Thm 3.3`. Fully
  proved, corrected per `ERRATA` E4 and E5, credited per E10. They are what you need **only**
  where the Co-Moving Reduction does not fully apply.
- §3.8 is **attribution**.
- §3.9 is the **punchline** and the reason this file still exists: `Prop 3.6`, causality is
  frame-dependent, with the measured numbers from `CORE-THEOREM.md` §7 Test 8.10 and their
  honest caveats.
- §3.10 (`Prop 3.5`) is the costate/Pontryagin system and the derivation of Zermelo's
  navigation formula, which yields the sharpest implementation test in the project.
- §3.11 is cut loci: what they are physically, why `T` is non-smooth there, and what the
  algorithm must do about it.

**Numbering caveat.** CONTRACT §2 fixes the slots `Thm 3.1`, `Prop 3.2`, `Thm 3.3`, `Prop 3.5`.
The two free slots are used as `Def 3.4` (§3.4) and `Prop 3.6` (§3.9). Presentation order is by
logical dependence, so `Def 3.4` appears before `Thm 3.1` and `Prop 3.6` appears before
`Prop 3.5`. Auxiliary results are **lettered** (`Lemma 3.A`, `Lemma 3.B`, …) so that no
CONTRACT-reserved slot is ever shadowed.

---

## 3.0 Standing hypotheses, and what breaks without each

### 3.0.1 A naming collision that must be resolved before anything else

`CORE-THEOREM.md` uses **`A1`** for *frozen advection* (the field is a rigid translation) and
**`A2`** for the *outrun condition* `|w| < σ_min^w`. The earlier draft of this file, and
`07-complexity.md`, use `(A1)`/`(A2)` for non-degeneracy and Lipschitz regularity. These are
different statements with the same names, and confusing them is not a cosmetic problem: `A1`
frozen-advection is the hypothesis of the *core theorem*, while `(A1)` non-degeneracy is a
hypothesis of *this* file, and one can hold without the other.

> **Normative resolution.** `A1` and `A2` are reserved, globally, for the CORE-THEOREM meanings
> (frozen advection; outrun). The standing hypotheses of `§3` are relabelled **`(H1)`–`(H5)`**
> and are used under those names everywhere below. `07-complexity.md`'s `(A1)–(A4)` map to
> `(H1)`, `(H2)`, `(H3)`, and the causality condition `Eq (3.27)` respectively.

### 3.0.2 The hypotheses

Throughout `§3`, `Ω ⊂ S²_{R_E}` is the navigable domain, points are expressed in the local
orthonormal frame `(𝐞_E, 𝐞_N)` so that every velocity is an ordinary vector of `ℝ²` in m/s
(this is `ERRATA` E8's convention, and it is the only reason the planar statements below are
legitimate on a sphere), `x_A ∈ Ω` is the departure point, `t₀` the departure time.

> **(H1) Non-degeneracy of the convexified indicatrix.**
> For every `(x,t)` of interest `𝒱(x,t) ⊂ ℝ²` is compact and
> ```
> 0 ∈ int conv 𝒱(x,t)        ⟺        |c(x,t)| < V_max(x,t)
> ```
> where `V_max` is the best attainable **through-water** speed. Consequently there are
> `0 < F_min ≤ F_max < ∞` with `F_min ≤ F(x,t,u) ≤ F_max` for every unit `u`, and
> `F = 1/σ` with `1/F_max ≤ σ ≤ 1/F_min`.
>
> **This is the corrected form, per `ERRATA` E1 and E9.** It is *not* `0 ∈ int 𝒱`. Our own
> default vessel has `q_min = 0.15`, hence by the cube law `V_min/V_max = 0.15^{1/3} = 0.531`,
> so the ship cannot stop and `0 ∉ 𝒱` whenever `|c| < V_min`. Writing (H1) with `𝒱` instead of
> `conv 𝒱` makes the default configuration violate its own standing hypothesis. Where `|c| ≥
> V_max`, (H1) fails and by `ERRATA` (E1.1) the reachable directions form a cone about `c` of
> half-angle `α_reach = arcsin(V_max/|c|)`, with `F = +∞` outside it.

> **(H2) Lipschitz regularity of the metric.** For all unit `u`,
> ```
> | F(x,t,u) − F(x',t',u) |  ≤  L_x |x − x'|  +  L_t |t − t'| ,
> ```
> with `L_x` in `s/m²` and `L_t` in `1/m` (i.e. `(s/m)/s`). Additionally the set-valued map
> `(x,t) ↦ conv 𝒱(x,t)` is Lipschitz in Hausdorff distance, with constant `L_v` in `1/s` in the
> space variable (the symbol added by `ERRATA` E6) and `L_{vt}` in `m/s²` in time.

> **(H3) Domain regularity.** `Ω` is bounded with Lipschitz boundary. Land, depth violations
> and exclusion polygons are modelled by `F ≡ +∞`, `σ ≡ 0`, and are **static in time**.

> **(H4) Convexification (CONTRACT D4).** All statements about the support function `𝔥` and all
> HJB equations are made for `conv 𝒱`. This costs nothing at the level of the Hamiltonian:
> `𝔥_𝒱 = 𝔥_{conv 𝒱}` identically (`Prop 2.7`). The physical gap it opens — a commanded control
> may be a chattering average of two admissible ones — is `Thm 2.11`, in the corrected *local*
> form (`ERRATA` E6.3), and is not this file's business.

> **(H5) Forecast horizon.** The environment is known only on `[t₀⁻, t₀⁻ + H_fc]`, where `t₀⁻`
> is the forecast issue time and `H_fc` the horizon. Beyond it, **persistence of the final
> frame** is the normative convention (`ERRATA` E5).

### 3.0.3 What breaks without each

| Dropped | What actually fails |
|---|---|
| **(H1)** | `F = +∞` on a cone, so `F_max = ∞` and `Δ_min` (3.23) is no longer a positive bucket width: `Prop 4.9` loses its premise and the Dial ring must be replaced by a heap (`ERRATA` E2, trigger `Υ_loc > Υ_heap = 12`). More seriously for **this** file: *loitering ceases to be admissible*, so `Thm 3.3` — which repairs causality by waiting — is no longer physically realisable at that point. The correct answer there is `ERRATA` E1's: you cannot escape this storm. |
| **(H2)** | The arrival map (3.20) has no modulus, `Thm 3.1` has no hypothesis to check, and the ordered-upwind consistency argument of `Thm 7.1` fails. The practically important failure of (H2) is **not weather but ban switching** (§3.7.5): when an IMO MSC.1/Circ.1228 criterion or an Ochi (1964) slamming limit flips, `F` jumps to `+∞` in finite time and `L_t = ∞` on that cell. |
| **(H3)** | The comparison principle for the eikonal fails and viscosity uniqueness is lost, so `Thm 7.1` has no limit object to converge to. Time-varying land (tides, ice edges) violates it and must be handled by re-solving, not by making `F` time-dependent. |
| **(H4)** | `𝔥` is unchanged, so *nothing in §3 changes* — that is the point of D4. What changes is realisability, `Thm 2.11`. |
| **(H5)** | `inf_{s≥0}` in the wait relaxation would require a forecast that does not exist. This is the second defect `ERRATA` E5 identifies, and truncation (3.33) is the repair. |

**Interface discipline (CONTRACT D7 and §4).** Every quantity in this file is computable from
the five primitives alone: `F(x,t,u) = 1/sigma(x,t,u,q=1)` for the time objective,
`𝔥(x,t,p) = support(x,t,p)`, and every derivative of `𝔥` used in `Prop 3.5` is a finite
difference of `support`. Nothing in `§3` reaches past that interface into the physics layer.

---

## 3.1 The stationary Finsler eikonal and its support-function form

Freeze the fields: `𝒱(x,t) ≡ 𝒱(x)`, `F(x,t,v) ≡ F(x,v)`. Define

```
T(x)  :=  inf { τ ≥ 0 : ∃ admissible trajectory from x_A to x of duration τ }          (3.1)
```

By `Prop 2.2` the duration of a trajectory equals its Finsler length, so `T` is the (asymmetric)
Finsler distance `d_F(x_A, x)`, finite on `Ω` by (H1) and (H3), and Lipschitz:

```
| T(x) − T(x') |  ≤  F_max · |x − x'|                                                  (3.2)
```

*Proof of (3.2).* By (H1) `B(0, 1/F_max) ⊆ conv 𝒱(x)` for every `x`, so the straight segment
from `x` to `x'` is traversable in either direction at ground speed at least `1/F_max`, giving
`d_F(x,x') ≤ F_max|x−x'|` and likewise `d_F(x',x)`. The triangle inequality for `d_F` then bounds
`|T(x) − T(x')|` by `max(d_F(x,x'), d_F(x',x))`. ∎ Note that **(3.2) is exactly where (H1) is
used**; without it `T` is only lower semicontinuous, one-sided.

### 3.1.1 Lemma 3.A — the support function *is* the dual metric

> **Lemma 3.A (gauge–support duality).** Let `K ⊂ ℝ²` be compact convex with `0 ∈ int K`, let
> `g_K(v) = inf{τ > 0 : v/τ ∈ K}` be its Minkowski gauge (this is `F`, `Def 2.2`), and let
> `𝔥_K(p) = max_{v ∈ K} ⟨v,p⟩` be its support function (`Def 2.6`). Then for every `p ∈ ℝ²`
> ```
> 𝔥_K(p)  =  sup_{v ≠ 0} ⟨p,v⟩ / g_K(v)  =:  g_K^*(p) ,                                (3.3)
> ```
> i.e. the support function is exactly the polar (dual) Finsler function `F*`.

**Proof.** Since `0 ∈ int K` there is `r > 0` with `B(0,r) ⊆ K`, hence `g_K(v) ≤ |v|/r`; since
`K` is compact there is `ρ = max_{w∈K}|w| < ∞`, hence `g_K(v) ≥ |v|/ρ > 0` for `v ≠ 0`. So the
quotient in (3.3) is well defined and finite. Both `⟨p,·⟩` and `g_K` are positively
1-homogeneous, so the quotient is positively 0-homogeneous and the supremum may be restricted to
the level set `{g_K = 1}`.

Two gauge identities, proved rather than quoted:

- `{g_K ≤ 1} = K`. If `g_K(v) ≤ 1` then for every `τ > 1` we have `v/τ ∈ K`; letting `τ ↓ 1` and
  using that `K` is closed gives `v ∈ K`. Conversely if `v ∈ K` then `v/1 ∈ K` so `g_K(v) ≤ 1`.
- `{g_K = 1} = ∂K`. If `g_K(v) = 1` then `v ∈ K`; if `v` were interior there would be `ε>0` with
  `(1+ε)v ∈ K`, giving `g_K(v) ≤ 1/(1+ε) < 1`. Conversely if `v ∈ ∂K` then `g_K(v) ≤ 1`, and
  `g_K(v) < 1` would give `v/τ ∈ K` for some `τ < 1`, i.e. `v ∈ τK`; since `0 ∈ int K` and `K`
  is convex, `τK ⊆ int K` for `τ < 1`, contradicting `v ∈ ∂K`.

Hence `sup_{v≠0} ⟨p,v⟩/g_K(v) = max_{v ∈ ∂K} ⟨p,v⟩`. Finally `max_{v∈∂K}⟨p,v⟩ = max_{v∈K}⟨p,v⟩`:
`≤` is trivial; for `≥`, a linear functional on a compact convex set attains its maximum at an
extreme point (Bauer's maximum principle), and every extreme point of `K` lies in `∂K`.
Therefore (3.3). ∎

**Consequence for the implementation.** `F*` never has to be built. The primitive
`support(x,t,p)` **is** `F*`, tabulated once per cell and forecast hour on `n_θ = 72` directions
by CONTRACT D2. Every occurrence of `F*` below may be read as a call to `support`.

**Coercivity.** If `B(0, 1/F_max) ⊆ conv 𝒱(x) ⊆ B(0, 1/F_min)` — which is (H1) — then directly
from the definition of `𝔥`,

```
|p| / F_max   ≤   𝔥(x,t,p)   ≤   |p| / F_min                                           (3.4)
```

so `𝔥` is coercive in `p` and vanishes only at `p = 0`. (3.4) is used three times: for viscosity
uniqueness (`Thm 7.1`), for the bucket width (`Prop 4.9`), and in the sign checks below.

### 3.1.2 The equation, with its sign derived

> **Stationary Finsler eikonal.** On `Ω ∖ {x_A}` the value function (3.1) is the unique
> viscosity solution of
> ```
> 𝔥( x, ∇T(x) )  =  1 ,      T(x_A) = 0 ,     T ≡ +∞ on the land complement.           (3.5)
> ```
> Equivalently, by `Lemma 3.A`, `F*(x, ∇T(x)) = 1`.

**Derivation, including the sign.** The dynamic programming principle for (3.1) is: for `δ > 0`
small enough that `x − δv ∈ Ω` for all `v ∈ conv 𝒱(x)`,

```
T(x)  =  min_{v ∈ conv 𝒱(x)} [ T(x − δ v) + δ ]  +  o(δ)                               (3.6)
```

Read (3.6) literally: *to stand at `x` at time `T(x)`, stand at `x − δv` at time `T(x) − δ` and
travel with ground velocity `v`.* Assume `T` differentiable at `x` and expand
`T(x − δv) = T(x) − δ⟨∇T(x), v⟩ + o(δ)`. Substituting, cancelling `T(x)`, dividing by `δ > 0`:

```
0  =  min_{v} [ 1 − ⟨∇T(x), v⟩ ] + o(1)     ⟹     max_{v ∈ conv 𝒱(x)} ⟨∇T(x), v⟩ = 1
```

which is (3.5) by `Def 2.6`.

**The sign is forced, not conventional.** `T` increases in the direction the front propagates,
so `⟨∇T, v⟩ > 0` for the propagating velocity. Writing `−∇T` inside the support function selects
the velocity that *decreases* `T` fastest, i.e. it solves the problem for the reversed indicatrix
`−𝒱`. For a symmetric (Riemannian) metric `−𝒱 = 𝒱` and the error is invisible; for a Finsler
metric with drift `c` it is exactly the substitution `c ↦ −c`, which yields a smooth,
plausible-looking, systematically wrong route, wrong in transit time by roughly `2|c|/V_s`. The
older `docs/03-causality-and-hjb.md` writes `max⟨−∇T,v⟩ = 1` and is wrong for this reason; that
directory is superseded.

**Regularity caveat.** `T` is Lipschitz by (3.2) but not `C¹` (§3.11), so (3.5) holds in the
viscosity sense of Crandall–Lions (1983). Existence, uniqueness and comparison follow from
convexity of `𝔥` in `p`, coercivity (3.4), continuity of `𝔥` in `(x,p)`, and (H3). Convergence of
the KAIROS scheme to this solution is `Thm 7.1` (Barles–Souganidis 1991) and is not restated
here.

---

## 3.2 The non-stationary problem: level sets, and the derivation of the sign

Now let the fields evolve. This subsection derives the level-set HJB **from** the dynamic
programming principle rather than asserting it, because the sign is the single most common
silent error in this literature and because the reduction of the level-set form to an
arrival-time form (`Lemma 3.B`) is what the rest of the file operates on.

### 3.2.1 The reached set and a level-set function that represents it

Define the set reached **at exactly** time `t`:

```
R(t)  :=  { x ∈ Ω : ∃ admissible y(·) on [t₀,t] with y(t₀) = x_A , y(t) = x }          (3.7)
```

> **Lemma 3.C (monotonicity of the reached set).** Under (H1) and (H4), `R(·)` is
> non-decreasing: `t' ≤ t ⟹ R(t') ⊆ R(t)`.

**Proof.** By (H1), `0 ∈ int conv 𝒱(x,s)` for every `(x,s)`, so the constant trajectory
`y(s) ≡ x` is admissible for the relaxed dynamics `ẏ ∈ conv 𝒱(y,s)` on any interval. Given
`x ∈ R(t')`, concatenate the trajectory reaching `x` at `t'` with the constant trajectory on
`[t',t]`; the concatenation is absolutely continuous and satisfies the inclusion a.e., so
`x ∈ R(t)`. ∎

**This is where (H4) earns its keep, and it should be said out loud.** With `q_min = 0.15` the
real ship *cannot* hold station (`ERRATA` E9); `0 ∉ 𝒱`. It is the convexification that makes
loitering admissible, realised physically by alternating headings, and the resulting realisability
gap is `Thm 2.11` in its corrected local form. Without (H4), `Lemma 3.C` fails, "reached at
exactly `t`" is not monotone, and the level-set formulation below has to be written for
`∪_{s≤t} R(s)` instead — which is the same thing only because loitering is available.

Fix any Lipschitz `φ₀ : ℝ² → ℝ` with `{φ₀ < 0} = {x_A}`-neighbourhood data — the normative
choice is the point-source seed `φ₀(x) = |x − x_A|`, and the `r₀ > 0` seed
`φ₀(x) = |x − x_A| − r₀` with `r₀ ↓ 0` for the regularised construction. Propagate it:

```
φ(x,t)  :=  inf { φ₀(y(t₀)) : y(·) admissible on [t₀,t] , y(t) = x } ,   inf ∅ = +∞    (3.8)
```

Then `{φ(·,t) < 0} = R(t)` exactly for the `r₀ ↓ 0` seed, and `φ(·,t₀) = φ₀`. `φ(·,t)` is
Lipschitz in `x` with constant `Lip(φ₀)·exp(L_v (t−t₀))`, by Filippov's theorem (Filippov 1967:
for a Lipschitz convex-valued right-hand side with constant `L_v`, two trajectories starting
`d` apart can be kept `d·e^{L_v(t−t₀)}` apart), applied backwards in time.

### 3.2.2 The exact dynamic programming principle

> **Lemma 3.D (exact DPP for `φ`).** For `t₀ ≤ s ≤ t`,
> ```
> φ(x,t)  =  inf { φ(z,s) : ∃ admissible y on [s,t] with y(s) = z , y(t) = x } .       (3.9)
> ```
> **No `o(δ)`: this identity is exact.**

**Proof.** Write `RHS` for the right-hand side.

*(`≥`)* Let `ε > 0` and pick an admissible `y` on `[t₀,t]` with `y(t) = x` and
`φ₀(y(t₀)) ≤ φ(x,t) + ε` (possible by definition of the infimum; if `φ(x,t) = +∞` there is
nothing to prove). Put `z := y(s)`. The restriction `y|_{[t₀,s]}` is admissible and ends at `z`,
so `φ(z,s) ≤ φ₀(y(t₀)) ≤ φ(x,t) + ε`. The restriction `y|_{[s,t]}` is admissible from `z` to `x`,
so `z` is one of the competitors in `RHS`. Hence `RHS ≤ φ(x,t) + ε`; let `ε ↓ 0`.

*(`≤`)* Let `z` be any competitor, joined to `x` by an admissible `y₂` on `[s,t]`, and let
`ε > 0`. Pick `y₁` admissible on `[t₀,s]` with `y₁(s) = z` and `φ₀(y₁(t₀)) ≤ φ(z,s) + ε`. The
concatenation `y := y₁ ⧺ y₂` is absolutely continuous on `[t₀,t]` (it is AC on each piece and
continuous at the junction) and satisfies `ẏ ∈ conv 𝒱(y,·)` a.e., hence is admissible, with
`y(t) = x`. So `φ(x,t) ≤ φ₀(y(t₀)) ≤ φ(z,s) + ε`. Take the infimum over `z` and let `ε ↓ 0`. ∎

### 3.2.3 Derivation of the level-set HJB and of its sign

> **Level-set HJB (non-stationary).**
> ```
> ∂φ/∂t  +  𝔥( x, t, ∇φ(x,t) )  =  0 ,        φ(·,t₀) = φ₀ ,                          (3.10)
> ```
> in the viscosity sense on `Ω × (t₀, ∞)`.

**Proof.** Write `B_δ(x,t) := { z : ∃ admissible y on [t−δ,t], y(t−δ) = z, y(t) = x }` for the
backward-reachable set. By (H2) and Filippov's theorem,

```
d_Hausdorff ( B_δ(x,t) ,  x − δ·conv 𝒱(x,t) )  =  O(δ²)                                (3.11)
```

— any trajectory of the inclusion on a length-`δ` interval stays within `O(δ²)` of the straight
segment generated by a frozen velocity, because the right-hand side varies by at most
`L_v·(displacement) + L_{vt}·δ = O(δ)` over the interval and this is integrated over a time `δ`.

*Subsolution.* Let `ψ ∈ C¹` and let `φ − ψ` have a local maximum at `(x̄,t̄)`, `t̄ > t₀`, normalised
so `φ(x̄,t̄) = ψ(x̄,t̄)`. Apply (3.9) with `s = t̄ − δ` and use (3.11) together with the Lipschitz
bound on `φ(·,s)`:

```
φ(x̄,t̄)  =  min_{v ∈ conv 𝒱(x̄,t̄)} φ( x̄ − δ v , t̄ − δ )  +  o(δ) .
```

The local-maximum property gives, for every `v`,
`φ(x̄ − δv, t̄ − δ) ≤ φ(x̄,t̄) + ψ(x̄ − δv, t̄ − δ) − ψ(x̄,t̄)`. Minimising both sides over `v`,

```
φ(x̄,t̄) + o(δ)  ≤  φ(x̄,t̄) + min_v [ ψ(x̄ − δv, t̄ − δ) − ψ(x̄,t̄) ]
0 + o(δ)        ≤  min_v [ −δ⟨∇ψ, v⟩ − δ ψ_t ] + o(δ)
                =  −δ ψ_t  −  δ max_v ⟨∇ψ, v⟩ + o(δ)
                =  −δ [ ψ_t + 𝔥(x̄,t̄,∇ψ) ] + o(δ) .
```

Divide by `δ > 0` and let `δ ↓ 0`: `ψ_t + 𝔥(x̄,t̄,∇ψ) ≤ 0`, which is the subsolution inequality
for (3.10).

*Supersolution.* Let `φ − ψ` have a local minimum at `(x̄,t̄)` with `φ(x̄,t̄) = ψ(x̄,t̄)`. The same
chain runs with every inequality reversed (`φ(x̄ − δv, t̄−δ) ≥ φ(x̄,t̄) + ψ(x̄ − δv,t̄−δ) − ψ(x̄,t̄)`),
giving `ψ_t + 𝔥(x̄,t̄,∇ψ) ≥ 0`. ∎

Two independent checks that the `+` sign is right:

1. *Monotone check.* At a point just outside the front, `𝔥 > 0` by (3.4), so (3.10) gives
   `φ_t < 0`: `φ` decreases everywhere, i.e. every point eventually joins `R(t)`. With a minus
   sign the reached set would shrink, contradicting `Lemma 3.C`. ✓
2. *Reduction check.* `Lemma 3.B` below plus §3.3. ✓

> **The opposite convention, and why it is a trap.** Set `ψ = −φ` (reached set `= {ψ > 0}`). The
> same computation gives
> ```
> ∂ψ/∂t  −  𝔥( x, t, −∇ψ )  =  0 .                                                     (3.12)
> ```
> **`𝔥(x,t,−p) ≠ −𝔥(x,t,p)`**: `𝔥` is 1-homogeneous only for *positive* scalars, and
> `𝔥_𝒱(−p) = 𝔥_{−𝒱}(p)`. In the Randers case `−𝒱 = D(−c, V_s)`, so "simplifying" (3.12) to
> `ψ_t + 𝔥(x,t,∇ψ) = 0` is numerically identical to **reversing every current in the domain**.
> Mandatory unit test: assert `support(x,t,p) + support(x,t,−p) ≥ 0` for all `p`, with equality
> for some `p ≠ 0` iff `c = 0`. (Proof of the assertion: `𝔥(p) + 𝔥(−p) = max_{v∈K}⟨v,p⟩ +
> max_{v∈K}⟨v,−p⟩ ≥ ⟨v₀,p⟩ + ⟨v₀,−p⟩ = 0` for any `v₀ ∈ K`; in the Randers case it equals
> `2V_s|p| > 0` for `p ≠ 0`, independent of `c` — so the *right* test is the numerical value
> `2V_s|p|`, not merely the sign.)

### 3.2.4 Lemma 3.B — reduction to the self-referential eikonal

> **Lemma 3.B (arrival-time reduction).** Let `φ` solve (3.10) and put
> `T(x) := inf{ t ≥ t₀ : φ(x,t) ≤ 0 }`. At every `x` where `T` is differentiable and `φ` is
> differentiable at `(x,T(x))` with `∇_xφ ≠ 0`, one has
> ```
> ∇T(x)  =  ∇_xφ( x, T(x) ) / 𝔥( x, T(x), ∇_xφ(x,T(x)) )                               (3.13)
> ```
> and consequently `T` satisfies the **self-referential Finsler eikonal**
> ```
> 𝔥( x , T(x) , ∇T(x) )  =  1 ,          T(x_A) = t₀ .                                 (3.14)
> ```

**Proof.** At such an `x` the crossing is transversal: by (3.10) and (3.4),
`φ_t = −𝔥(x,T(x),∇_xφ) ≤ −|∇_xφ|/F_max < 0`, so `φ(x,·)` is strictly decreasing near `T(x)` and
`φ(x,T(x)) = 0` with the infimum attained. Differentiate the identity `φ(x,T(x)) = 0` in `x`:
`∇_xφ + φ_t ∇T = 0`, hence `∇T = −∇_xφ/φ_t = ∇_xφ/𝔥(x,T(x),∇_xφ)`, which is (3.13). Apply
`𝔥(x,T(x),·)` to (3.13) and use positive 1-homogeneity in `p` with the **positive** scalar
`1/𝔥(x,T(x),∇_xφ)`:

```
𝔥( x, T(x), ∇T(x) )  =  𝔥( x, T(x), ∇_xφ ) / 𝔥( x, T(x), ∇_xφ )  =  1 .   ∎
```

**This is the equation KAIROS solves in the ground frame,** and it is *not* the stationary
eikonal (3.5): the Hamiltonian is evaluated at the value function's own value, `t = T(x)`. Three
consequences, which set up everything that follows:

- (3.14) is fully nonlinear of the form `G(x, T, ∇T) = 0` with genuine dependence on the unknown
  in the **middle** slot. Such equations do not in general admit a comparison principle, and
  their characteristics carry an extra term relative to `G(x,∇T) = 0`. Both facts are recovered
  below: the first as `Thm 3.1`, the second as `Prop 3.5`.
- The natural comparison hypothesis, properness `∂G/∂T ≥ 0`, reads `∂_t 𝔥(x,t,p) ≥ 0` — "the sea
  can only get worse". That is **false** in ocean routing: storms clear. The correct, weaker and
  sharp hypothesis is monotonicity of the **arrival map**, which is `Thm 3.1`.
- Discretising (3.14) semi-Lagrangianly by evaluating `𝔥` at the **departure** time — a value
  already known on the accepted front, not the unknown `T(x)` — makes the update explicit
  (`Eq (4.1)`). `Thm 3.1` is exactly the statement that this explicit scheme computes what the
  implicit one would.

---

## 3.3 The Randers case reduces to the Zermelo eikonal (Lolla & Lermusiaux 2014)

Take the classical configuration of `§2.2`: fixed through-water speed `V_s`, drift `c(x,t)`, no
wave dents, no active bans, `|c| < V_s`. Then `𝒱(x,t) = D(c(x,t), V_s)`, the closed disc of
radius `V_s` centred at `c`, and the support function is immediate:

```
𝔥(x,t,p)  =  max_{|w| ≤ V_s} ⟨ c + w , p ⟩  =  ⟨ c(x,t), p ⟩  +  V_s |p|               (3.15)
```

the maximiser being `w = V_s p/|p|` for `p ≠ 0`. Substituting (3.15) into the stationary form
(3.5), into the self-referential form (3.14), and into the level-set form (3.10):

```
V_s |∇T(x)|  +  ⟨ c(x), ∇T(x) ⟩  =  1                       (stationary)               (3.16)

V_s |∇T(x)|  +  ⟨ c(x, T(x)), ∇T(x) ⟩  =  1                 (non-stationary)           (3.17)

∂φ/∂t  +  V_s |∇φ|  +  ⟨ c(x,t), ∇φ ⟩  =  0                 (level set)                (3.18)
```

**(3.18) is precisely the reachability-front equation of Lolla & Lermusiaux (2014)** for
time-optimal path planning in dynamic flows, and (3.16) is the classical Zermelo (1931) eikonal.
We claim nothing here. The reduction is a consistency check on our formulation and it is why
their published test cases can be used verbatim as ground truth in `§8`. The two facts that make
the check non-vacuous:

- `Lemma 3.A` applied to `𝒱 = D(c,V_s)` says `F* = ` (3.15), so the gauge `F` is the Randers
  metric `Eq (2.1)`, and `‖b‖_a < 1 ⟺ |c| < V_s ⟺ 0 ∈ int 𝒱 ⟺` (H1) — all four are the same
  condition. This is Bao–Robles–Shen (2004) in the form we use it (`Thm 2.3`).
- `Lemma 3.B` applied to (3.18) returns (3.17), so the level-set and arrival-time formulations
  agree **including the sign**. Had we used `−∇T` in (3.5) we would have obtained
  `V_s|∇T| − ⟨c,∇T⟩ = 1`, the reversed-current equation of the warning in §3.2.3. The reduction
  is therefore a sharp test of the sign, not a formality.

### 3.3.1 A numerical duality check that reproduces a golden vector

`Lemma 3.A` says the gauge and the support function are Legendre-type duals, so the golden
vectors of `handbook/01-golden-vectors.md` §G2 — which are *gauge* values — must be recoverable
from the *support* function. They are, and the arithmetic is worth doing once because it catches
the commonest confusion in the whole project: **`𝔥(u)` is the normal speed of the front,
`1/F(u)` is the speed made good along `u`, and these are different numbers whenever the drift
has a cross-track component.**

Take `V_s = 7.2 m/s`, `c = (0, 1.5) m/s` (pure north current), and ask for the metric in the due
**east** direction `v = (1,0)`. Golden vector T4 gives `σ = 7.042 016 756 583 30 m/s`,
`F = 0.142 004 774 280 768 s/m`. From duality (3.3) with `F*` = (3.15), writing
`p = (cos α, sin α)`:

```
F(v)  =  max_{α} cos α / ( 1.5 sin α + 7.2 )                                           (3.19)
```

Differentiating the quotient, the stationarity condition is
`−sin α(1.5 sin α + 7.2) − 1.5 cos²α = 0`, i.e. `1.5 + 7.2 sin α = 0`, so

```
sin α  =  −1.5/7.2  =  −0.208 333 333 …      α = −12.024 7°
cos α  =  0.978 057 9…
F(v)   =  0.978 057 9 / (7.2 − 0.3125)  =  0.978 057 9 / 6.8875  =  0.142 004 77…
```

which is golden vector T4 to the digits carried. Two things fall out of the arithmetic itself:

- The maximising covector sits at `sin α = −c_⊥/V_s`, i.e. **at the crab angle**
  `arcsin(1.5/7.2) = 12.0247°`. Duality delivers the crab angle for free; if your implementation
  computes a crab angle by a separate fixed point (`§1.4.2`) the two must agree to `1e-12` rad,
  and that is a cheap cross-check between two unrelated code paths.
- The *support* value in the same direction is `𝔥(x,t,(1,0)) = ⟨c,(1,0)⟩ + V_s = 0 + 7.2 = 7.2`,
  not `7.042…`. An implementation that returns `7.2` where the gauge is wanted is 2.2 % fast in
  every cross-current cell, converges beautifully, and is wrong — symptom S4 of the debugging
  playbook.

**What KAIROS does differently from Lolla & Lermusiaux.** They march (3.18) forward in `t` over
the whole domain with a CFL-limited step, paying `O(N · t_f/Δt_CFL)` regardless of where the
destination is. KAIROS solves (3.14) — or, after the Co-Moving Reduction, the *stationary* (3.5)
— by a single monotone sweep, touching only the region the front reaches before the destination
is finalised. That sweep is legal only if arrival-time order is a valid finalisation order, which
is `Thm 3.1`, which is what §3.4–§3.7 are about, and which §3.9 makes vacuous in the co-moving
frame.

---

## 3.4 The arrival map, the segment lengths that are actually used, and the discrete system

`Thm 3.1` is a statement about two objects: a scalar map on times, and a discrete Bellman system.
Both are defined precisely here, before the theorem, because the earlier drafts conflate them and
because the *length scale* in the condition is the thing `ERRATA` E4 corrects.

### 3.4.1 Def 3.4 — the arrival map, the causality margin, and the relaxed arrival map

> ### Definition 3.4
> For a base point `x`, a unit direction `u`, and a **segment length** `ℓ > 0`:
>
> **(a) Arrival map.**
> ```
> Arr_{x,u,ℓ}( t )  :=  t  +  ℓ · F( x, t, u )   ∈  (t, +∞]                            (3.20)
> ```
> — depart `x` at absolute time `t`, traverse a Finsler-straight segment of Euclidean length `ℓ`
> in ground direction `u`, arrive at `Arr(t)`. By (H3) the value `+∞` is admitted and ordered
> above every real.
>
> **(b) Causality margin.** `m(x,t) := 1 − r(x)·L_t(x,t)`, where `r(x)` is the ordered-upwind
> stencil radius actually used at `x`. Causality holds at `(x,t)` when `m(x,t) ≥ 0`.
>
> **(c) Relaxed (wait-augmented) arrival map.** With `S_max(t)` from (3.33),
> ```
> Ãrr_{x,u,ℓ}(t)  :=  inf_{ s ∈ [0, S_max(t)] } Arr_{x,u,ℓ}( t + s )                   (3.21)
> ```

### 3.4.2 The segment lengths: `ℓ_min` and `r(x)` — ERRATA E3 and E4

**This is where the earlier drafts are wrong, and neither error is cosmetic.**

The KAIROS update `Eq (4.1)` does **not** traverse segments of length `h`. It searches the
accepted front out to the ordered-upwind radius `r(x)` (`Prop 4.7`), and the segment from the
interpolated front point `ξ(ζ)` to `x` can be as long as `r(x)` and, without an explicit
exclusion, arbitrarily short.

*Upper end.* `r(x) = h · max_{B(x,r(x))} Υ_loc ≤ h·Υ`, the ball-max fixed point of `Prop 4.7`.
With `Υ_loc` reaching 3.5–4 in the Agulhas and in heavy head seas (`Def 2.9`), `r(x)` is several
times `h`.

*Lower end.* `ERRATA` E3, Lemma E3.1: on a grid of spacing `h` whose accepted front is
8-connected, the perpendicular distance from a node to any accepted-front edge is at least
`h/√2`, attained by the diagonal pair `(h,0)–(0,h)` on the line `x+y = h`. The update **must skip
any front point `ξ` with `|x − ξ| < ℓ_min`**; that exclusion is what converts the bound from an
assumption into a theorem, and it costs nothing because such points are interior to the stencil
and their characteristics are carried by other front edges. Hence, normatively:

```
ℓ_min := c_geo · h ,   c_geo := 1/√2 = 0.707 106 781 …
ℓ ∈ [ ℓ_min , r(x) ]   for every segment the update uses                                (3.22)
Δ_min := ℓ_min · F_min = c_geo · h · F_min                                             (3.23)
```

`Δ_min` is the guaranteed minimum cost of any update and the correct Dial bucket width for
`Prop 4.9`.

> **Superseded: CONTRACT D3.** D3 states `Δ_min = h·F_min` and prescribes a heap fallback "when
> `F_min` is not bounded away from 0". Both are wrong and `ERRATA` overrides both. `F_min =
> 1/(V_max + |c|)` is bounded below (E2: it varies only from 0.133 to 0.067 s/m across the entire
> realistic drift range for `V_max = 7 m/s`); what diverges is `Υ_loc = (V_max+|c|)/(V_max−|c|)`,
> so the heap fallback trigger is `Υ_loc > Υ_heap = 12`, not `F_min → 0`. And `Δ_min = h F_min`
> is *too large* by `√2`, which makes the Dial queue non-monotone — a newly created label can
> land in the bucket currently being drained — so `Prop 4.9` fails silently.

> **Superseded: `h·L_t ≤ 1`. This is ERRATA E4 and it is the reason to read this section.**
> The condition must be checked at the **largest segment the scheme actually traverses**, which
> is `r(x)`, not `h`:
> ```
> r(x) · L_t(x,t)  ≤  1                                                                (3.27)
> ```
> The `h`-version is weaker by the factor `Υ_loc = r(x)/h`, and `Υ_loc` is precisely the quantity
> the ordered-upwind machinery exists to handle, so the margin is not small. An implementation
> built to `h·L_t ≤ 1` reports a **green causality certificate on forecasts where the sweep is
> not licensed**. §3.6 constructs a field where `h·L_t = 0.625` (pass) while `r·L_t = 1.25`
> (fail) and the arrival-time-ordered solve is 5.8 % suboptimal. In the isotropic limit `r = h`
> and the old condition is recovered, which is why the error was invisible in weak-field testing.
>
> **Consequential documentation conflict.** `handbook/01-golden-vectors.md` §G5 asks
> implementations to report "Max `h·L_t` over the domain". That is the superseded quantity. The
> required diagnostic is `max_x r(x)·L_t(x,t)` and the per-cell margin `m(x,t)` of `Def 3.4(b)`.
> Likewise `handbook/02-debugging-playbook.md` §S7's sanity range "`h·L_t ≈ 0.05–0.15` for a
> 0.25° grid and 3-hourly forecasts" must be read as `r·L_t ≈ 0.05·Υ_loc … 0.15·Υ_loc`.

### 3.4.3 The discrete update system

Let `X` be the finite node set, `s := x_A ∈ X` the source. For each `y ∈ X∖{s}` let `U(y)` be a
finite set of **update rules**. A rule `ρ ∈ U(y)` consists of a non-empty source set
`S(ρ) ⊆ X` and an **update function** `A_ρ : (ℝ∪{+∞})^{S(ρ)} → ℝ∪{+∞}`. Write `T|_S` for the
restriction of a labelling `T : X → ℝ∪{+∞}` to `S`.

> **Discrete Bellman system.**
> ```
> T(s) = t₀ ;      T(y)  =  min_{ρ ∈ U(y)}  A_ρ( T|_{S(ρ)} )     for y ≠ s .           (3.24)
> ```

Define `Φ : (ℝ∪{+∞})^X → (ℝ∪{+∞})^X` by the right-hand side of (3.24). The **discrete value
function `T_h`** is the least fixed point of `Φ`, which exists by Knaster–Tarski: `([t₀,+∞])^X`
is a complete lattice under the pointwise order and `Φ` is order-preserving whenever (U1) below
holds. `T_h` is the object `Thm 3.1(b)` says the sweep computes; its convergence to the viscosity
solution of (3.14) as `h → 0` is `Thm 7.1`.

Two hypotheses on the rule family:

- **(U1) Monotonicity.** Each `A_ρ` is non-decreasing in every argument.
- **(U2) Strict causality.** `A_ρ(T|_S) > max_{z ∈ S(ρ)} T_z` whenever the right-hand side is
  finite, and moreover `A_ρ(T|_S) ≥ min_{z ∈ S(ρ)} T_z + Δ_min`.

(U1) is the discrete face of FIFO and is supplied by `Thm 3.1(a)`. (U2) is the ordered-upwind
causality requirement of Sethian & Vladimirsky (2003) — *an update must strictly post-date every
value it reads* — and is supplied by §3.4.4.

### 3.4.4 Rule decomposition and the causality clamp

The raw semi-Lagrangian update from an accepted-front edge `(x_j, x_k)` is, from `Eq (4.1)`,

```
ξ(ζ) = ζ x_j + (1−ζ) x_k ,   T̃(ζ) = ζ T_j + (1−ζ) T_k ,   ℓ(ζ) = |x − ξ(ζ)| ,
A(ζ)  =  T̃(ζ)  +  ℓ(ζ) · F( x, T̃(ζ), (x−ξ(ζ))/ℓ(ζ) ) ,     ζ ∈ [0,1] .                (3.25)
```

`min_{ζ∈[0,1]} A(ζ)` does **not** satisfy (U2) in general: if `T_j ≫ T_k` the minimiser sits near
`ζ = 0` and the value can be far below `T_j`. The repair is not to clamp the whole edge — that
would inflate legitimate single-vertex updates — but to split it into three rules with honest
source sets:

```
ρ_k    :  S = {x_k} ,          A_{ρ_k}    = A(0)                                       (3.26a)
ρ_j    :  S = {x_j} ,          A_{ρ_j}    = A(1)                                       (3.26b)
ρ_{jk} :  S = {x_j, x_k} ,     A_{ρ_{jk}} = max{ inf_{ζ∈(0,1)} A(ζ) , max(T_j,T_k) + δ }  (3.26c)
```

with clamp margin `δ ∈ (0, Δ_min]`; the normative choice is `δ = Δ_min`, introducing no new
constant.

> **Lemma 3.E (the rule family satisfies (U1) and (U2)).** Assume (H1)–(H3), the `ℓ_min`
> exclusion (3.22), and the causality condition (3.27) at the segment lengths used. Then each of
> (3.26a–c) satisfies (U1) and (U2) with margin `Δ_min` of (3.23).

**Proof.**

*(U2) for `ρ_k`.* `A(0) = T_k + ℓ(0)·F(x,T_k,u_k)` with `ℓ(0) ≥ ℓ_min` by the exclusion and
`F ≥ F_min` by (H1), so `A(0) ≥ T_k + ℓ_min F_min = T_k + Δ_min`. Since `S(ρ_k) = {x_k}` both
clauses of (U2) hold, strictly because `Δ_min > 0`. Identically for `ρ_j`.

*(U2) for `ρ_{jk}`.* The outer `max` forces `A_{ρ_{jk}} ≥ max(T_j,T_k) + δ > max(T_j,T_k)`, the
first clause; and `max(T_j,T_k) + δ ≥ min(T_j,T_k) + Δ_min` because `δ = Δ_min` and
`max ≥ min`, the second.

*(U1) for `ρ_k`.* `A(0) = Arr_{x,u_k,ℓ(0)}(T_k)` with `ℓ(0) ≤ r(x)`, hence non-decreasing in
`T_k` by `Thm 3.1(a)`. Identically for `ρ_j`.

*(U1) for `ρ_{jk}`.* For each fixed `ζ ∈ (0,1)`, `T̃(ζ) = ζT_j + (1−ζ)T_k` is non-decreasing in
each of `T_j,T_k` (coefficients are non-negative), and `A(ζ) = Arr_{x,u(ζ),ℓ(ζ)}(T̃(ζ))` with
`ℓ(ζ) ∈ [ℓ_min, r(x)]`, which is non-decreasing in `T̃(ζ)` by `Thm 3.1(a)`. A composition of
non-decreasing maps is non-decreasing; a pointwise infimum over `ζ` of non-decreasing functions
is non-decreasing; `(T_j,T_k) ↦ max(T_j,T_k) + δ` is non-decreasing; and the maximum of two
non-decreasing functions is non-decreasing. ∎

> **Remark 3.E.1 (what the clamp costs).** The clamp is active only when
> `inf_{ζ∈(0,1)} A(ζ) < max(T_j,T_k) + δ`, i.e. only when a front edge straddles a value jump
> comparable to one cell's cost. When active, the value returned by the *outer* minimisation of
> (3.24) is still at most `min(A(0), A(1))`, because `ρ_j` and `ρ_k` are separate rules and are
> never clamped. Hence
> ```
> 0  ≤  T_h^{clamped}(y) − T_h^{raw}(y)  ≤  min(A(0),A(1)) − inf_ζ A(ζ)
>                                        ≤  |T_j − T_k|  +  2 r(x) F_max
> ```
> using `|T̃(ζ) − T̃(ζ')| ≤ |T_j − T_k|` and `ℓ(ζ) ≤ r(x)`. Since `|T_j − T_k| ≤ h F_max` on a
> front edge by (3.2), and `r(x) ≤ Υh`, the per-update perturbation is `O(Υ h)` — the same order
> as the scheme's own truncation error, so `Thm 7.1` is unaffected in the limit and only the
> error constant degrades.
>
> **Honest limitation, labelled as such.** The *aggregate* effect along a route is
> `O(Υh) × (number of clamped updates traversed)`. We do **not** prove that this count is `O(1)`.
> Geometrically it should be — the clamp fires only where a front edge straddles a shock, and a
> route crosses `O(1)` shocks generically (§3.11) — but we have no proof.
>
> > **Conjecture 3.E.2.** For a metric satisfying (H1)–(H3) whose cut locus (§3.11) is a
> > finite union of Lipschitz arcs, the number of clamped updates on any optimal backpointer
> > chain is bounded independently of `h`.
> >
> > *What is missing:* a bound on how many front edges can straddle a shock during the sweep,
> > which requires control on the geometry of the discrete front near a shock that we do not
> > have. What **is** proved: the scheme is monotone, causal, and perturbed by `O(Υh)` per
> > update. The aggregate is *measured* (clamp-firing rate and front-to-front value gap) rather
> > than bounded, in `§8`.

> **Remark 3.E.3 (infinite labels).** If `T_k = +∞` (unreached or land) then `T̃(ζ) = +∞` for
> every `ζ < 1`, so `ρ_{jk}` and `ρ_k` return `+∞` and only `ρ_j` is informative. The
> decomposition therefore degrades gracefully to single-vertex updates at the edge of the reached
> region, with no special case in the code. That is a practical reason for splitting the rules,
> quite apart from causality.

---

## 3.5 Thm 3.1 — the causality / FIFO condition

> ### Theorem 3.1 (Causality / FIFO condition)
> Assume (H1)–(H3) and the `ℓ_min` exclusion (3.22). Let `r(x)` be the ordered-upwind stencil
> radius used at `x` and `r_max := max_x r(x)`.
>
> **(a) Monotonicity of the arrival map.** If
> ```
>                        r(x) · L_t   ≤   1                                             (3.27)
> ```
> then for every unit `u` and every `ℓ ∈ (0, r(x)]` the arrival map (3.20) is non-decreasing in
> `t`. If (3.27) is strict, `Arr` is strictly increasing with modulus `1 − r(x)L_t`:
> ```
> Arr(t₂) − Arr(t₁)  ≥  ( 1 − r(x) L_t ) ( t₂ − t₁ )     for  t₂ ≥ t₁ .                 (3.28)
> ```
> Moreover the arrival functional of any finite concatenation of such segments, as a function of
> the departure time from the first segment, is non-decreasing.
>
> **(b) Correctness of label setting.** Assume the update family satisfies (U1) and (U2) — by
> `Lemma 3.E` this follows from (3.27). Then:
> 1. the Bellman system (3.24) has a **unique** solution, equal to the least fixed point `T_h`;
> 2. the label-setting sweep `Alg 4.3` — repeatedly extract a node of minimum tentative label
>    among the non-accepted, accept it, and re-evaluate every rule whose source set has just
>    become fully accepted — terminates after exactly `|X|` extractions, one per node;
> 3. the sequence of extracted labels is **non-decreasing**;
> 4. no node is ever reopened, and on extraction every node's label equals `T_h`;
> 5. consequently the sweep returns `T_h` exactly, in a single pass.
>
> **(c) Necessity at the stated scale.** If (3.27) fails, the conclusion of (b) fails: `Prop 3.2`
> constructs a field with `r·L_t = 1 + η` on which every arrival-time-ordered label-setting
> algorithm is suboptimal by exactly `η · (t_c − T_M) > 0`.

### 3.5.1 Proof of (a)

Fix `x, u` and `ℓ ≤ r(x)`, and let `t₂ ≥ t₁`. If `F(x,t₁,u) = +∞` or `F(x,t₂,u) = +∞` then by
(H3) the direction is excluded for **all** `t` at that cell (land and exclusion polygons are
static), so both are `+∞`, `Arr ≡ +∞`, and the claim is trivial. Ban-induced time-varying
infinities are exactly the case where (H2) fails; they are treated in §3.7.5 and repaired by
`Thm 3.3`, not here.

Otherwise both are finite and (H2) gives `F(x,t₂,u) − F(x,t₁,u) ≥ −L_t (t₂ − t₁)`. Hence

```
Arr(t₂) − Arr(t₁)  =  (t₂ − t₁)  +  ℓ [ F(x,t₂,u) − F(x,t₁,u) ]
                   ≥  (t₂ − t₁)  −  ℓ L_t (t₂ − t₁)
                   =  (t₂ − t₁)( 1 − ℓ L_t )
                   ≥  (t₂ − t₁)( 1 − r(x) L_t )   ≥  0
```

using `ℓ ≤ r(x)` and (3.27). That is (3.28). **No differentiability of `F` in `t` is used** — the
Lipschitz bound (H2) is applied directly. (The earlier draft invoked a.e. differentiability with
`|∂_tF| ≤ L_t`; that is strictly stronger and it silently excludes the ban-switching case, where
`F` is not even continuous.)

For the concatenation claim, let `Arr_1, …, Arr_D` be the arrival maps of successive segments and
`G := Arr_D ∘ ⋯ ∘ Arr_1`. Each `Arr_i` is non-decreasing by the above and maps `(−∞,+∞]` into
itself with `Arr_i(+∞) = +∞`; a composition of non-decreasing maps is non-decreasing. ∎ *(a)*

### 3.5.2 Proof of (b) — the exchange argument in full

Notation: `D : X → ℝ∪{+∞}` is the tentative labelling maintained by the sweep, `A ⊆ X` the
accepted set. Initialisation: `A = ∅`, `D(s) = t₀`, `D(y) = +∞` for `y ≠ s`.

**Step 0 — attainment of each `A_ρ`.** `U(y)` is finite. For `ρ_j`, `ρ_k` the value is a single
evaluation. For `ρ_{jk}` the inner infimum is over the compact `[0,1]` of the function
`ζ ↦ A(ζ)` of (3.25), which is continuous wherever `T̃(ζ) < ∞`: `T̃` and `ξ` are affine,
`ℓ(ζ) = |x − ξ(ζ)|` is continuous and bounded below by `ℓ_min > 0` (so the direction
`(x−ξ)/ℓ` is continuous), and `F` is continuous in `(t,u)` by (H2) plus continuity of `𝒱` in `u`.
An infimum of a continuous function over a compact set is attained. If `F` is only lower
semicontinuous — the case when a ban boundary is crossed *within* the segment — the infimum is
still attained, and (U1)/(U2) are unaffected. So every `A_ρ` is a minimum, as used below. ∎

**Step 1 — base case: the source.** Every fixed point of `Φ` has `T(s) = t₀` by definition of
`Φ`, in particular `T_h(s) = t₀`, and no rule governs `s`. There is no "shortcut back to the
source": by (U2) any rule producing a value at `s` would give `≥ min_z T(z) + Δ_min`, but `s` is
not governed by a rule at all — its value is pinned by (3.24). The sweep's first extraction is
therefore `s` with value `t₀`, since every other initial label is `+∞`. If several nodes carry
`+∞` this is still well defined because `t₀ < +∞`. ∎ *Step 1*

**Step 2 — uniqueness of the solution of (3.24) (the minimal-counterexample exchange).**
Let `T` and `T'` both solve (3.24) and suppose `T ≠ T'`. Put

```
𝒟 := { y ∈ X : T(y) ≠ T'(y) } ≠ ∅ ,      and pick y ∈ 𝒟 minimising m(y) := min(T(y), T'(y)).
```

`𝒟` is finite and non-empty so the minimum is attained; **if several `y` attain it, pick any** —
the argument never uses uniqueness. WLOG `T(y) < T'(y)`, so `m(y) = T(y)`. By Step 1, `y ≠ s`.

By Step 0 there is `ρ ∈ U(y)` attaining `T(y) = A_ρ(T|_{S(ρ)})`. By (U2),

```
T(z)  <  A_ρ(T|_S)  =  T(y)      for every z ∈ S(ρ) .                                   (†)
```

Fix `z ∈ S(ρ)`. If `z ∈ 𝒟` then `m(z) ≤ T(z) < T(y) = m(y)`, contradicting minimality of `m(y)`
over `𝒟`. Hence `z ∉ 𝒟`, i.e. `T(z) = T'(z)`. As `z ∈ S(ρ)` was arbitrary,
`T|_{S(ρ)} = T'|_{S(ρ)}`. Therefore

```
T'(y)  ≤  A_ρ( T'|_{S(ρ)} )  =  A_ρ( T|_{S(ρ)} )  =  T(y)  <  T'(y) ,
```

a contradiction. Hence `𝒟 = ∅`, the solution is unique, and being unique it coincides with the
least fixed point `T_h`. ∎ *Step 2*

> *Where (U2) is indispensable.* Without the **strict** inequality in (†), `z` could satisfy
> `T(z) = T(y)` and the minimality argument stalls: `z` might lie in `𝒟` with `m(z) = m(y)`. This
> is exactly why the clamp (3.26c) is required and why "update `≥` max of sources" — non-strict —
> is not enough. Ties in *values* are fine (Remark 3.1.1); ties between an update and its own
> source are not.

**Step 3 — the sweep's invariants, by induction on the number of extractions.**
Write `A_m` for the accepted set and `D_m` for the labelling after `m` extractions. Claim:

- **(J1)** `D_m(y) = T_h(y)` for every `y ∈ A_m`, and these values are never subsequently changed;
- **(J2)** the extracted values are non-decreasing: `κ_1 ≤ κ_2 ≤ ⋯ ≤ κ_m`;
- **(J3)** for every `y ∉ A_m`,
  `D_m(y) = min{ A_ρ(D_m|_{S(ρ)}) : ρ ∈ U(y), S(ρ) ⊆ A_m }` (with `min ∅ = +∞`), except that
  `D_m(s) = t₀` if `s ∉ A_m`.

*Base `m = 0`.* `A_0 = ∅`, so (J1) and (J2) are vacuous, and (J3) holds because no rule has its
source set inside `∅` and `D_0(y) = +∞` for `y ≠ s`, while `D_0(s) = t₀`. ✓

*Inductive step.* Assume (J1)–(J3) after `m` extractions. Let `y*` be **a** node of `X ∖ A_m`
minimising `D_m`; the algorithm extracts it. Several nodes may tie; the argument never uses
uniqueness of the minimiser.

**(i) `D_m(y*) ≥ T_h(y*)`.** If `y* = s` this is equality by Step 1 and (J3). Otherwise, by (J3)
and (J1),

```
D_m(y*) = min{ A_ρ(T_h|_S) : ρ ∈ U(y*), S(ρ) ⊆ A_m }
        ≥ min{ A_ρ(T_h|_S) : ρ ∈ U(y*) }   =  Φ(T_h)(y*)  =  T_h(y*) ,
```

the inequality because a minimum over a subset of the rules is at least the minimum over all of
them, and the last equality because `T_h` is a fixed point.

**(ii) `D_m(y*) ≤ T_h(y*)` — the exchange.** Suppose not: `T_h(y*) < D_m(y*)`. Consider the
witness set

```
B  :=  { y ∈ X ∖ A_m  :  T_h(y) < D_m(y*) } .
```

`y* ∈ B`, so `B ≠ ∅`. Pick `y ∈ B` minimising `T_h(y)` over `B` (**any** minimiser if tied). Two
cases.

*Case `y = s`.* Then `s ∉ A_m` and by (J3) `D_m(s) = t₀ = T_h(s) < D_m(y*)`, contradicting the
minimality of `D_m(y*)` over `X∖A_m`.

*Case `y ≠ s`.* By Step 0 there is `ρ ∈ U(y)` attaining `T_h(y) = A_ρ(T_h|_{S(ρ)})`, and by (U2),

```
T_h(z)  <  T_h(y)  <  D_m(y*)      for every z ∈ S(ρ) .
```

Fix `z ∈ S(ρ)`. If `z ∉ A_m` then `z ∈ B` (it is non-accepted and `T_h(z) < D_m(y*)`) with
`T_h(z) < T_h(y)`, contradicting minimality of `T_h(y)` over `B`. Hence `z ∈ A_m`. As `z` was
arbitrary, `S(ρ) ⊆ A_m`, so `ρ` is one of the rules available to `y` in (J3), and using (J1) on
`S(ρ) ⊆ A_m`,

```
D_m(y)  ≤  A_ρ( D_m|_{S(ρ)} )  =  A_ρ( T_h|_{S(ρ)} )  =  T_h(y)  <  D_m(y*) .
```

But `y ∈ X∖A_m` with `D_m(y) < D_m(y*)` contradicts `y*` being a minimiser of `D_m` over
`X∖A_m`. Both cases are impossible, so (ii) holds; with (i), `D_m(y*) = T_h(y*)`.

*This is the exchange argument.* Its content is: **if the extracted node were not final, there
would have to exist an unaccepted node with a strictly smaller true value, whose own optimal rule
reads only accepted nodes — and that node would already carry a smaller tentative label,
contradicting the extraction rule.** Every hypothesis is used exactly once: (U1) to identify
`A_ρ(D_m|_S)` with `A_ρ(T_h|_S)` on accepted source sets, (U2) to make the source values
*strictly* smaller so the minimal witness is well founded, and finiteness of `U(y)` and Step 0 to
make "the rule attaining `T_h(y)`" exist.

**(iii) (J2) is maintained.** Every label of a non-accepted node at step `m` is `≥ D_m(y*)` by
minimality. After accepting `y*`, the only newly available rules are those `ρ` with
`y* ∈ S(ρ) ⊆ A_m ∪ {y*}`; for such `ρ`, (U2) gives
`A_ρ(D|_{S(ρ)}) > max_{z∈S(ρ)} D(z) ≥ D(y*)`. Rules with `S(ρ) ⊆ A_m` were already reflected in
`D_m`. Hence every label present after the extraction is `≥ D_m(y*)`, so the next extracted value
is `≥ D_m(y*)`. ✓

**(iv) (J1) and (J3) are maintained.** `D_{m+1}(y*) = D_m(y*) = T_h(y*)` and `y*` is never
relaxed again: by (iii) any candidate offered to `y*` later is `≥ D_m(y*)`, so skipping accepted
nodes loses nothing and reopening never occurs. (J3) for `y ∉ A_{m+1}` holds because the
algorithm re-evaluates exactly the rules whose source sets have just become fully accepted, and
`D` on `A_{m+1}` equals `T_h` by (J1). ✓

**Termination.** Each iteration moves one node from `X∖A` to `A`, so the sweep performs exactly
`|X|` extractions. Nodes with `D = +∞` at extraction have `T_h = +∞` by (i)–(ii) and are
unreachable; the implementation may stop early once the destination is accepted (`§4`). ∎ *(b)*

### 3.5.3 Remarks on Theorem 3.1

**Remark 3.1.1 (ties — read this before implementing).** Ties occur constantly: a symmetric
field, a uniform current, or simply two front edges of equal length. The proof of (b) never
assumes `y*` is unique, and the contradiction derived in (ii) is the *strict* inequality
`D_m(y) < D_m(y*)` with `y` non-accepted, which contradicts `y*` being **a** minimiser however
ties are broken. Therefore:

- any deterministic or nondeterministic tie-break is correct;
- the **values** `T_h` are tie-break independent; the **backpointers**, and hence the returned
  route, are not (§3.11);
- in the bucket queue of `Prop 4.9` (Dial 1969), nodes in the same bucket may be extracted in any
  order — which is what makes the `O(1)` amortised queue legitimate rather than a heuristic.

**Remark 3.1.2 (where FIFO is actually used).** Exactly once: in `Lemma 3.E`'s proof of (U1),
which feeds Step 3(i)–(ii) through the identity `A_ρ(T_h|_S) = A_ρ(D|_S)` when `D = T_h` on `S`.
Monotonicity is what allows the algorithm to commit to the *earliest* label at a node and never
revisit it with a later one. If arriving later at `z` could produce an earlier arrival
downstream, the earliest label at `z` is not the useful one and label setting is unsound — which
is exactly what `Prop 3.2` exhibits.

**Remark 3.1.3 (what `Thm 3.1` does *not* say).** It says the sweep computes `T_h`, the exact
solution of the **discrete** system (3.24). It does not say `T_h = T`. The gap is the
semi-Lagrangian truncation error plus the clamp perturbation of Remark 3.E.1, and it is
`Thm 7.1`'s business. Conflating "exact discrete solve" with "exact solve" is the commonest
overclaim in this literature and we do not make it. Independently, `CORE-THEOREM.md` §4 measures
a **fixed-stencil metrication floor of ~1 % that does not vanish under refinement** on a
16-neighbour stencil (h = 24 … 3 km gave 0.36, 0.15, 0.79, 0.92, 0.17, 0.98, 0.58 %); that floor
is a property of the stencil, not of `Thm 3.1`, and it is why the continuum-heading
semi-Lagrangian update of `§4` exists.

**Remark 3.1.4 (multi-objective labels).** Nothing in Step 2 or Step 3 uses that labels are
scalars beyond the *order* used by the queue. With vector labels the same argument runs on the
lexicographic-by-time order provided every objective accumulates monotonically (`Prop 5.4`), which
is the classical multi-objective label-setting setting of Martins (1984); `Thm 5.2`/`Thm 5.3`
carry it, and `ERRATA` E7 corrects the bucketing to Tsaggouris & Zaroliagis (2009) value
bucketing. §3 owns only objective index 1.

---

## 3.6 Prop 3.2 — sharpness: a field with `r·L_t = 1 + η` that defeats label setting

`Thm 3.1(c)` needs a counterexample, and it must be *explicit*, because the whole practical force
of `ERRATA` E4 is that a condition stated at the wrong length scale looks satisfied on fields
where the solve is not licensed. The construction below does double duty: it fails (3.27) while
**passing** the superseded `h·L_t ≤ 1`.

### 3.6.1 The construction

Three nodes on a line, `S → M → G`, with `M` a cut vertex (the only route from `S` to `G` passes
through `M`). Grid spacing `h = 25 km`; local anisotropy `Υ_loc = 2`, so the ordered-upwind radius
is `r = Υ_loc·h = 50 km = 5.0×10⁴ m` (`Prop 4.7`). Ship `V_s = 7.2 m/s`.

**Leg 1 (`S → M`): time-independent.** Length `ℓ₁ = 30 km`, speed made good `σ₁ = 6.0 m/s`
constant, so `F₁ = 1/6 s/m` and

```
T_M  =  30 000 / 6.0  =  5 000 s .                                                     (3.29a)
```

**Leg 2 (`M → G`): the gate.** Length `ℓ₂ = r = 5.0×10⁴ m`, with the metric specified directly
(and the current read off from it, so that `L_t` is exact rather than approximate):

```
F_gate(t)  =  F_hi − a·t     for t ∈ [0, t_c] ,        F_gate(t) = F_lo  for t ≥ t_c
F_hi = 0.30 s/m ,  F_lo = 0.10 s/m ,  t_c = 8 000 s ,  a = (F_hi−F_lo)/t_c = 2.5×10⁻⁵ m⁻¹  (3.29b)
```

The implied along-track current, from `σ = 1/F = V_s + c_∥`:

| `t` [s] | 0 | 5 000 | 8 000 |
|---|---|---|---|
| `F_gate` [s/m] | 0.300 | 0.175 | 0.100 |
| `σ = 1/F` [m/s] | 3.333 | 5.714 | 10.000 |
| `c_∥ = σ − 7.2` [m/s] | −3.867 | −1.486 | +2.800 |

`|c_∥| ≤ 3.867 < 7.2 = V_s` throughout, so **(H1) holds** and, by `Lemma 3.C`, loitering at `M` is
admissible. That matters: the optimum below *uses* loitering, and it must be legal.

**The two causality numbers.**

```
L_t  =  max_t |∂F_gate/∂t|  =  a  =  2.5×10⁻⁵ m⁻¹        (exact, by construction)

r · L_t  =  5.0×10⁴ × 2.5×10⁻⁵  =  1.25       ⟹  η = 0.25 ,  condition (3.27) VIOLATED
h · L_t  =  2.5×10⁴ × 2.5×10⁻⁵  =  0.625      ⟹  superseded condition SATISFIED         (3.29c)
```

### 3.6.2 Prop 3.2

> ### Proposition 3.2 (Sharpness of the causality condition, at the stencil scale)
> On the field (3.29), every algorithm that (i) finalises each node at its earliest achievable
> arrival time and (ii) thereafter computes downstream values from that finalised value alone,
> returns a `G`-arrival of `13 750 s`, whereas the true optimum is `13 000 s`. The loss is
> `750 s`, i.e. `5.77 %`. In general, with the construction parameterised by
> `r·L_t = 1 + η > 1`, the loss is exactly
> ```
> Loss  =  η · ( t_c − T_M )  >  0 ,                                                    (3.30)
> ```
> which vanishes linearly as `η ↓ 0` and is strictly positive for every `η > 0`. Hence (3.27) is
> sharp: it cannot be weakened to `r·L_t ≤ 1 + η` for any `η > 0`, and in particular it cannot be
> replaced by `h·L_t ≤ 1`.

**Proof.** On `[0, t_c]` the arrival map of leg 2 is affine:

```
Arr(t)  =  t + ℓ₂ F_gate(t)  =  t + 5.0×10⁴ (0.30 − 2.5×10⁻⁵ t)
        =  15 000  +  t(1 − 1.25)  =  15 000 − 0.25 t                                  (3.31)
```

and for `t ≥ t_c`, `Arr(t) = t + 5.0×10⁴ × 0.10 = t + 5 000`. `Arr` is continuous at `t_c`
(`15 000 − 2 000 = 13 000 = 8 000 + 5 000` ✓), strictly decreasing with slope `−η = −0.25` on
`[0,t_c]`, strictly increasing with slope `+1` after. So `Arr` attains its minimum over
`[T_M, ∞)` at `t = t_c`:

```
Arr(T_M) = Arr(5 000) = 15 000 − 1 250 = 13 750 s
Arr(t_c) = Arr(8 000) = 15 000 − 2 000 = 13 000 s
```

*The true optimum is `13 000 s`.* Depart `S` at 0, arrive `M` at `5 000`, loiter until `8 000`
(admissible by (H1) and `Lemma 3.C`; the physical realisation is station-keeping, or the
alternating-heading chattering of (H4) if `q_min > 0` forbids literal zero speed), depart, arrive
`G` at `13 000`. No smaller value is achievable: any admissible route reaches `M` no earlier than
`5 000` (leg 1 is time-independent, and `M` is a cut vertex so there is no alternative), and
`min_{t ≥ 5000} Arr(t) = Arr(8 000) = 13 000`.

*Any arrival-time-ordered label-setting algorithm returns `13 750 s`.* By hypothesis (i) it
finalises `M` at `T_M = 5 000`, the earliest achievable arrival there. By hypothesis (ii) the
value it assigns to `G` is computed from the finalised `T_M` alone, i.e. `Arr(5 000) = 13 750`.
Since `M` is a cut vertex, no other rule can reach `G`, so `13 750` is the returned value.

*The general formula.* With `F_gate(t) = F_hi − a t` on `[0,t_c]` and `ℓ₂ = r`, the slope of `Arr`
is `1 − r a = 1 − (1+η) = −η`, so `Arr(T_M) − Arr(t_c) = η(t_c − T_M)`, which is (3.30). For
`η ≤ 0` — i.e. under (3.27) — `Arr` is non-decreasing, `min_{t ≥ T_M} Arr(t) = Arr(T_M)`, and the
label-setting value is the true optimum; so the failure occurs **exactly** when (3.27) fails, and
the size of the failure is proportional to the amount by which it fails. ∎

### 3.6.3 Why this construction is the point of ERRATA E4

Read (3.29c) again. An implementation built to the superseded condition computes `h·L_t = 0.625`,
prints a green causality certificate, runs a single-pass unrelaxed sweep, and returns a route that
is **5.77 % slow** — on a voyage of a few days, hours. Nothing looks wrong: the sweep converges,
the route is smooth, the arrival time is plausible. This is symptom class S4 of the debugging
playbook, and it is undetectable without a reference solution. The `r(x)` form is the difference
between a licence and a rubber stamp.

### 3.6.4 Is the field physically extreme? Honest answer

The gate changes `σ` from 3.33 to 10.0 m/s in 8 000 s, i.e. a 6.67 m/s change in the along-track
current in 2 h 13 min. That is **not** typical open-ocean current evolution. It is attainable in
three real settings: (i) a **ban switching off** — an IMO MSC.1/Circ.1228 heavy-weather or Ochi
(1964) slamming criterion releasing as a squall line passes, which changes `F` discontinuously
and therefore has `L_t = ∞` locally, far worse than this construction; (ii) tidal streams in
straits; (iii) a fast-moving front in a coastal jet.

More to the point, compare the constructed `L_t` with the **measured** worst case in
`CORE-THEOREM.md` §7 Test 8.10, regime B (a translating cyclone with 35 %/day intensification):

```
constructed L_t = 2.50×10⁻⁵ m⁻¹        measured ground-frame max L_t = 2.34×10⁻⁵ m⁻¹
constructed r·L_t = 1.25 (r = 50 km)   measured r·L_t = 1.309 (r = 56 km)
```

The counterexample is **less** extreme than the measured ground-frame field. Two honest
qualifications: the measured field is a *constructed* three-regime test (translating Gaussian
system, intensification, second system), not a real operational forecast stack — `CORE-THEOREM`
§9 records that Test 8.10 on a real stack is still to be run — and the counterexample's geometry
(a single cut vertex) is contrived even though its magnitudes are not.

---

## 3.7 Thm 3.3 — the wait relaxation, scaled by the segment length

Where (3.27) fails, the repair is to let the ship do what mariners actually do: slow down, or
wait for the gate to open. `ERRATA` E5 corrects two defects in the first draft's version of this,
and both corrections are load-bearing.

### 3.7.1 The corrected definition

> **Superseded:** `F̃(x,t,u) := inf_{s≥0} [ s/h + F(x,t+s,u) ]`.
>
> **Wrong for two reasons.** (1) The running-infimum identity works **only** when the penalty
> denominator equals the multiplier applied to `F` in the update. The update multiplies `F` by
> `ℓ`, which can be as large as `r(x) = Υ_loc h`; charging waiting at `s/h` over-charges it by up
> to `Υ_loc`, and the result is then *not* the running infimum, so unconditional causality does
> not follow. (2) `inf_{s≥0}` requires forecast data beyond the horizon, which does not exist.

> ### Definition (corrected wait relaxation, ERRATA E5.1)
> Evaluated at the **same `ℓ`** the update uses:
> ```
> F̃_ℓ(x,t,u)  :=  inf_{ s ∈ [0, S_max(t)] } [  s/ℓ  +  F(x, t+s, u)  ]                 (3.32)
> S_max(t)     :=  ( t₀⁻ + H_fc ) − t                                                  (3.33)
> ```
> with `t₀⁻` the forecast issue time and `H_fc` the horizon (H5). Beyond the horizon,
> **persistence of the final frame** is the normative convention, and the run log **must** report
> how many evaluations were horizon-truncated — an evaluation that hits `s = S_max` is one whose
> answer is a property of the convention rather than of the forecast.

### 3.7.2 Lemma 3.F — the running-infimum identity

> **Lemma 3.F.** For every `x, u, ℓ > 0` and every `t`,
> ```
> t  +  ℓ · F̃_ℓ(x,t,u)  =  inf_{ t' ∈ [ t , t + S_max(t) ] }  Arr_{x,u,ℓ}( t' )
>                       =  Ãrr_{x,u,ℓ}(t) .                                             (3.34)
> ```

**Proof.** `ℓ > 0`, so multiplying the bracket of (3.32) by `ℓ` and adding `t` is a strictly
increasing affine map of the bracket, and therefore commutes with the infimum:

```
t + ℓ·F̃_ℓ(x,t,u)  =  t + ℓ · inf_{s∈[0,S_max]} [ s/ℓ + F(x,t+s,u) ]
                   =  inf_{s∈[0,S_max]} [ t + ℓ·(s/ℓ) + ℓ·F(x,t+s,u) ]
                   =  inf_{s∈[0,S_max]} [ (t+s) + ℓ·F(x,t+s,u) ]
                   =  inf_{s∈[0,S_max]} Arr_{x,u,ℓ}(t+s)
                   =  inf_{t'∈[t,t+S_max]} Arr_{x,u,ℓ}(t') .   ∎
```

**The cancellation `ℓ·(s/ℓ) = s` is the entire content of the lemma, and it is exactly what the
`s/h` version destroys.** With `s/h` one gets `(t + ℓs/h) + ℓF(x,t+s,u)`, whose first term
advances the clock by `ℓs/h ≥ s` — the scheme is charged more for waiting than waiting costs, so
the object computed is not the running infimum of the arrival map and `Thm 3.3` below has no
proof. The over-charge factor is `ℓ/h ∈ [1/√2, Υ_loc]`, i.e. up to `Υ_heap = 12` before the heap
fallback fires.

**Attainment.** The infimum in (3.32) is attained: `[0, S_max(t)]` is compact and
`s ↦ s/ℓ + F(x,t+s,u)` is continuous by (H2), or lower semicontinuous in the ban-switching case,
and an lsc function on a compact set attains its infimum. So `F̃_ℓ` is a minimum and the argmin
`s*(x,t,u)` is well defined (take the smallest minimiser for determinism, which matters because
`EnvField` is required to be deterministic — `types.py`).

### 3.7.3 Thm 3.3

> ### Theorem 3.3 (Wait relaxation restores causality unconditionally)
> Assume (H1), (H3), (H5). Then for every `x`, unit `u` and `ℓ > 0`:
>
> **(a)** The relaxed arrival map `Ãrr_{x,u,ℓ}` of (3.21)/(3.34) is non-decreasing in `t`, **with
> no condition on `L_t` whatsoever** — in particular (3.27) is not assumed and `L_t = ∞` is
> permitted.
>
> **(b)** `Ãrr(t) ≤ Arr(t)`, with equality for all `t` if and only if `Arr` is non-decreasing on
> the horizon window. Consequently, under (3.27) the relaxation is *inactive* and `F̃_ℓ ≡ F`.
>
> **(c)** Replacing `F` by `F̃_ℓ` and `Arr` by `Ãrr` in the rule family (3.26) preserves (U1) and
> (U2), hence `Thm 3.1(b)` holds for the relaxed scheme unconditionally.
>
> **(d)** The relaxed scheme's value at a node is the earliest arrival achievable by trajectories
> that are allowed to hold station at grid nodes for a non-negative duration bounded by the
> forecast horizon.

**Proof.**

*(a)* Let `t₂ ≥ t₁`. The horizon window shrinks: `[t₂, t₀⁻+H_fc] ⊆ [t₁, t₀⁻+H_fc]`. An infimum
over a smaller set is at least the infimum over the larger set, so by (3.34)

```
Ãrr(t₂)  =  inf_{t' ∈ [t₂, t₀⁻+H_fc]} Arr(t')   ≥   inf_{t' ∈ [t₁, t₀⁻+H_fc]} Arr(t')  =  Ãrr(t₁).
```

That is the whole proof, and it uses nothing about `F` beyond measurability of `Arr` — which is
why the conclusion is unconditional. ∎ *(a)*

*(b)* `t` is a competitor in its own infimum, so `Ãrr(t) ≤ Arr(t)`. If `Arr` is non-decreasing on
the window then `Arr(t') ≥ Arr(t)` for `t' ≥ t`, so the infimum is attained at `t' = t` and
equality holds; conversely if `Arr(t'') < Arr(t)` for some `t'' > t` in the window then
`Ãrr(t) ≤ Arr(t'') < Arr(t)`, strict. Under (3.27), `Thm 3.1(a)` makes `Arr` non-decreasing, so
`Ãrr ≡ Arr` and, dividing by `ℓ`, `F̃_ℓ ≡ F`. ∎ *(b)*

*(c)* (U1): the proof of `Lemma 3.E` used monotonicity of `Arr` only through `Thm 3.1(a)`;
substitute (a) of this theorem, which supplies it unconditionally. Every other step of
`Lemma 3.E` is untouched. (U2): `F̃_ℓ ≥ ?` — here care is needed, because `F̃_ℓ` can be *smaller*
than `F`, and (U2) needs a positive lower bound on the increment. From (3.32), for any `s`,
`s/ℓ + F(x,t+s,u) ≥ 0 + F_min = F_min` by (H1); hence `F̃_ℓ ≥ F_min` and

```
Ãrr(t) − t  =  ℓ · F̃_ℓ(x,t,u)  ≥  ℓ_min F_min  =  Δ_min > 0 ,
```

so the increment bound (U2) survives with the *same* constant `Δ_min`. This is the second place
where the `ℓ_min` exclusion of `ERRATA` E3 is indispensable. ∎ *(c)*

*(d)* By (3.34) the relaxed update evaluates `inf_{t' ≥ t} Arr(t')` over the horizon window, which
is by definition the best arrival over all departure times reachable by holding station at the
node from time `t`. Holding station is admissible by (H1) and `Lemma 3.C`. Conversely any
station-holding trajectory departs at some `t' ∈ [t, t + S_max]` and therefore arrives at
`Arr(t') ≥ Ãrr(t)`. The two inequalities give (d), node by node; composing over a route uses the
concatenation clause of `Thm 3.1(a)`, which (a) supplies. ∎ *(d)*

### 3.7.4 `F̃_ℓ` is a scheme-level object, not a continuum metric — and why that is fine

`ERRATA` E5 is explicit and this file will not soften it.

> **`F̃_ℓ` is not a continuum metric and must not be called one.** It contains `ℓ`, a
> discretisation quantity, and by (3.22) `ℓ ∈ [c_geo h, Υ h]`, so `ℓ → 0` as `h → 0`. Therefore
> for every fixed `s > 0` the waiting penalty `s/ℓ → ∞`, the infimum in (3.32) concentrates at
> `s = 0`, and
> ```
> F̃_ℓ  ⟶  F     pointwise as h → 0 :  the relaxation degenerates in the continuum limit. (3.35)
> ```
> Consequently `F̃_ℓ` cannot be identified with "the loiter-augmented value function of the
> continuum problem", which is what the first draft claimed.

The honest statement, and it is the one that matters:

> **The continuum claim, corrected.** The *scheme's* value function converges to the
> loiter-augmented value function of the continuum problem as `h → 0`. This is a statement about
> `§7` convergence (Barles–Souganidis 1991: monotone + stable + consistent ⇒ convergence to the
> viscosity solution), not about the per-edge object `F̃_ℓ`.

There is a clarifying observation that makes the degeneracy (3.35) unsurprising rather than
alarming, and it is worth stating because it reframes the whole of §3.4–§3.7:

> **The wait relaxation restores, at the scheme level, a control the continuum problem never
> lost.** Under (H1) and (H4), `0 ∈ int conv 𝒱`, so loitering is admissible in the continuum
> problem *by hypothesis*, and the true value function `T` already accounts for it: the set of
> achievable departure times from a point `z` is `[T(z), ∞)`, so the earliest arrival through `z`
> is `inf_{t ≥ T(z)}` of the downstream arrival — precisely the running infimum. The continuum
> problem is therefore always FIFO in the sense that matters. What is *not* FIFO is the
> **semi-Lagrangian update**, which consumes exactly `ℓ F` and cannot express "leave later". The
> causality condition (3.27) is exactly the condition under which the update does not need to
> express it, because `Arr` is already its own running infimum. And (3.35) says the scheme's
> inability disappears as `h → 0`, since a vanishing segment can be re-partitioned to encode any
> wait. All three statements are the same statement.

**Diagnostic consequence, and it is cheap.** By `Thm 3.3(b)`, the relaxation is active at
`(x,t,u)` exactly when the minimiser `s*(x,t,u) > 0`. So the handbook counter "fraction of cells
needing wait relaxation" is implementable as: *count nodes at which the argmin of (3.32) is
non-zero for at least one stencil direction.* No separate estimate of `L_t` is needed for the
counter — though `L_t` is still needed for the *licence*, `Def 3.4(b)`.

### 3.7.5 Ban switching: the case where (H2) genuinely fails

When a seakeeping ban activates or releases — S1 synchronous roll, S2 parametric roll, S3
surf-riding, S4 slamming (Ochi 1964), S5 green water, all per IMO MSC.1/Circ.1228 (2007) — `F`
jumps between a finite value and `+∞` in zero time. Then `L_t = ∞`, (H2) fails, and (3.27) can
never be satisfied at any stencil radius. `Thm 3.1(a)` is unavailable, and this is the practically
most important failure mode, far more common than smooth weather evolution defeating causality.

`Thm 3.3` covers it exactly, because its proof uses only that `Arr` is a function of `t` and that
the infimum is over a shrinking window; no continuity is needed. The physical reading is exactly
right: **when a ban is active you wait for it to lift, and the relaxed metric prices the wait
correctly.** This is `ERRATA` E10's re-scoped claim (3), and it is the strongest surviving part of
this file's original contribution — with the additional operational observation that the wait
branch is frequently Pareto-*dominant* on fuel and risk, not merely feasible: slow-steaming
through a lifting gate burns less fuel than the SFOC-optimal dash that arrives while the ban is
active (`§1.4.5`, `§5`).

**Bounded-wait variant.** Charterparty and crew-duty constraints may cap the loiter at `S_cap`.
Replace `S_max(t)` by `min(S_max(t), S_cap)` in (3.32); `Lemma 3.F` and `Thm 3.3(a)` are unchanged
because both only use that the window is an interval shrinking with `t` — and `[t, t+min(S_max,
S_cap)]` shrinks with `t` whenever `S_cap` is constant. Nothing else changes.

---

## 3.8 Attribution — what in this file is ours, and what is not

`ERRATA` §E10 is a citation kill and it is honoured here without hedging.

> **The causality condition is not new.**
> **A. Vladimirsky, *Static PDEs for time-dependent control problems*, Interfaces and Free
> Boundaries 8 (2006), 281–300.** That paper asks precisely when a time-dependent optimal-control
> problem admits a single-pass static (Dijkstra / fast-marching-type) solution, and derives the
> causality condition. The first draft's framing — "the graph literature has FIFO, the level-set
> literature has HJB, nobody joined them" — is simply false; that is the paper that joined them,
> twenty years ago. **`Thm 3.1` is a restatement of a known result in our notation**, and it is
> presented here because the specification must be self-contained and completely proved, not
> because it is a contribution.

Full credit list for `§3`:

| Object in this file | Owed to |
|---|---|
| The routing problem as a Zermelo navigation problem | **Zermelo (1931)** |
| Zermelo ↔ Randers correspondence; `‖b‖_a < 1 ⟺ \|c\| < V_s` | **Bao, Robles & Shen (2004)** |
| Level-set/reachability-front formulation for ship routing, Eq (3.18) | **Lolla & Lermusiaux (2014)** |
| Viscosity solutions, comparison, uniqueness of (3.5)/(3.14) | **Crandall & Lions (1983)** |
| Convergence of monotone, stable, consistent schemes | **Barles & Souganidis (1991)** |
| Ordered-upwind causality requirement (U2), anisotropic single-pass | **Sethian & Vladimirsky (2003)** |
| Causality condition for single-pass solution of *time-dependent* control | **Vladimirsky (2006)** |
| Bucket queue (Dial discipline) that makes ties harmless | **Dial (1969)** |
| Multi-objective label setting on which `Thm 5.x` builds | **Martins (1984)**; front-propagation form **Kumar & Vladimirsky (2010)**; value bucketing **Tsaggouris & Zaroliagis (2009)** |
| Trajectory-perturbation estimate used in (3.11) | **Filippov (1967)** |
| Time-dependent Zermelo navigation with tacking (adjacent, complementary) | **Markvorsen (2025)**, arXiv:2508.07274 — indicatrix fields that are *time-dependent only*, with no spatial structure; a different special case from ours |
| Frozen-field hypothesis, the meteorological ancestor of assumption A1 | **Taylor (1938)** |
| Ban criteria whose switching breaks (H2) | **IMO MSC.1/Circ.1228 (2007)**; slamming **Ochi (1964)**; wind resistance **Fujiwara (2006)** |

**What is ours in `§3`, stated narrowly (the `ERRATA` E10 re-scope):**

1. The identification of the causality constant with the **temporal Lipschitz constant of an
   operational forecast field**, estimated cell by cell from a real forecast stack rather than
   assumed.
2. The resulting **runtime diagnostic** — `Def 3.4(b)`, reported as `max_x r(x)L_t(x,t)` and as a
   per-cell margin — so that a solve ships with a machine-checkable licence rather than an
   assumption. Together with `ERRATA` E4's correction of the length scale from `h` to `r(x)`,
   without which the diagnostic is optimistic by `Υ_loc` and, per `Prop 3.2`, green-lights
   unlicensed solves.
3. The **wait relaxation** (3.32) as the physically meaningful repair where the condition fails,
   `ℓ`-scaled so that `Lemma 3.F` is true, horizon-truncated so that it is computable, and with
   the operational observation that loitering and slow-steaming are what mariners already do and
   that the wait branch is often Pareto-dominant rather than merely feasible.

Claim 3 is the one worth defending as genuinely new. Claims 1 and 2 are engineering that makes a
known theorem operational. **And all three are supporting apparatus** — the contribution of
KAIROS is `Thm C.1`, which is the subject of the next section.

---

## 3.9 Prop 3.6 — the punchline: causality is frame-dependent

Everything in §3.4–§3.7 exists to handle `L_t > 0`. `CORE-THEOREM.md` `Thm C.1(b)` says that
under assumption **A1** (frozen advection: every environmental field is a rigid translation,
`E(x,t) = E₀(x − wt)`) the co-moving problem in `y = x − wt` is **autonomous**. An autonomous
metric has `L_t = 0`. Not small — zero.

### 3.9.1 The statement

> ### Proposition 3.6 (Frame-dependence of the causality obstruction)
> Let `F(x,t,u)` be the ground-frame metric and, for a constant `w ∈ ℝ²`, let `F_w` denote the
> metric of the problem written in the frame `y = x − wt`, i.e. the gauge of
> `𝒱_w(y,t) := 𝒱(y + wt, t) ⊖ w`. Write `L_t^{(w)} := Lip_t(F_w)`. Then:
>
> **(a) Advective bound.** If `F(x,t,u) = F₀(x − wt, u)` for some `w` (assumption A1), then `F` is
> differentiable in `t` wherever `F₀` is differentiable in `y`, with
> ```
> ∂_t F(x,t,u)  =  − ⟨ w , ∇_y F₀(x − wt, u) ⟩ ,       hence   L_t^{(0)}  ≤  |w| · L_x .   (3.36)
> ```
> **The entire ground-frame causality constant of a rigidly advected field is a product of the
> pattern's spatial roughness and its translation speed.** Neither factor is a property of the
> ship or of the grid.
>
> **(b) Exact annihilation.** Under A1 with that same `w`, `F_w(y,t,u) = F₀(y,u)` has no `t`
> argument, so
> ```
> L_t^{(w)}  ≡  0 ,      and therefore   r(y)·L_t^{(w)} = 0 ≤ 1   for every stencil radius. (3.37)
> ```
> `Thm 3.1`'s hypothesis (3.27) holds **vacuously**, `Thm 3.3`'s relaxation is never active
> (`Thm 3.3(b)`), `Prop 3.2`'s counterexample cannot be constructed, and `Def 3.4(b)`'s margin is
> `m ≡ 1`. §3.4–§3.7 have empty content in this frame.
>
> **(c) Residual form.** Where A1 fails, decompose `E(x,t) = E₀(x − wt) + R(x,t)` (`CORE-THEOREM`
> Eq C.8). Then the condition to check is not (3.27) but
> ```
> r(y) · L_t^R  ≤  1 ,          L_t^R := Lip_t( F_w ) ,                                  (3.38)
> ```
> i.e. the reduction acts as a **preconditioner** on the causality constant: the apparatus of
> §3.4–§3.7 is applied to the residual only.

**Proof.**

*(a)* Under A1, `F(x,t,u) = F₀(x−wt,u)`. Fix `u`. For `t,t'`, `F(x,t,u) − F(x,t',u) =
F₀(x−wt,u) − F₀(x−wt',u)`, and `|(x−wt) − (x−wt')| = |w||t−t'|`, so by the spatial Lipschitz
bound in (H2), `|F(x,t,u) − F(x,t',u)| ≤ L_x |w| |t−t'|`. Taking the supremum over `x,t,t',u`
gives `L_t^{(0)} ≤ |w| L_x`. Where `F₀` is differentiable, the chain rule on
`t ↦ F₀(x − wt, u)` gives the displayed derivative. ∎

*(b)* By `Thm C.1(a)`, `x(·)` is admissible for `ẋ ∈ 𝒱(x,t)` iff `y(t) = x(t) − wt` is admissible
for `ẏ ∈ 𝒱_w(y)`, with the same time parameterisation; and by (C.3),
`𝒱_w(y) = 𝒱₀(y) ⊖ w = {v − w : v ∈ 𝒱₀(y)}` carries no `t` argument, because the translation has
been absorbed entirely into the shift of the coordinate. The gauge of a set that does not depend
on `t` does not depend on `t`, so `F_w(y,t,u) = F_w(y,u)` and `Lip_t(F_w) = 0` exactly. Then
`r(y)·0 = 0 ≤ 1` for any finite `r(y)`, which is (3.37). The consequences follow by inspection:
`Thm 3.1(a)`'s modulus (3.28) becomes `Arr(t₂) − Arr(t₁) ≥ t₂ − t₁`, i.e. `Arr(t) = t + ℓF_w(y,u)`
is a *translation*, exactly monotone; `Thm 3.3(b)` then gives `F̃_ℓ ≡ F_w`; and in `Prop 3.2` the
slope of `Arr` is `1 − r·0 = 1 > 0`, so no decreasing branch exists. ∎

*(c)* Immediate from (b) applied to the `E₀` part and (H2) applied to `R`: the metric in the
co-moving frame is a Lipschitz function of `(E₀-part, R-part)` and the `E₀` part contributes zero
temporal variation, so `Lip_t(F_w)` is controlled entirely by `Lip_t` of the residual. ∎

### 3.9.2 The measured numbers, with their caveats

From `CORE-THEOREM.md` §7, Test 8.10. `L_t = max_u |∂F/∂t|` over 24 headings, 3-day horizon,
10 km grid, reported as max / p99 / median over the domain, and `r·L_t` at `r = 56 km`.

| Regime | Frame | max [m⁻¹] | p99 [m⁻¹] | median [m⁻¹] | `r·L_t` (r = 56 km) |
|---|---|---|---|---|---|
| **A** pure translation (A1 exact) | ground | 6.33e−07 | 6.33e−07 | 5.64e−07 | 0.035 — licensed |
| | co-moving | **0.0** | **0.0** | **0.0** | **0.000** |
| **B** + intensification 35 %/day | ground | 2.34e−05 | 2.34e−05 | 3.75e−07 | **1.309 — VIOLATED** |
| | co-moving | 4.86e−06 | 4.86e−06 | 1.69e−06 | **0.272 — licensed** |
| **C** + second system at a different `w` | ground | 2.34e−05 | 2.33e−05 | 3.52e−07 | **1.307 — VIOLATED** |
| | co-moving | 5.07e−06 | 4.67e−06 | 1.63e−06 | **0.261 — licensed** |

**Derived checks on the table** (so the reader can verify it rather than trust it):

- `2.34e−05 × 5.6e4 = 1.3104` ✓ against the reported 1.309; `4.86e−06 × 5.6e4 = 0.2722` ✓ against
  0.272. The table is internally consistent.
- Improvement ratios, computed from the table: p99 `2.34e−05/4.86e−06 = 4.81×` (B),
  `2.33e−05/4.67e−06 = 4.99×` (C); max `2.34e−05/5.07e−06 = 4.62×` (C). Hence the **4.6–5.0×**
  quoted in `CORE-THEOREM` spans max and p99 across regimes B and C.
- Regime A tests (3.36): with the true `w = (2.0, 0.5)`, `|w| = 2.0616 m/s`, the bound
  `L_t ≤ |w|L_x` and the measured `L_t = 6.33e−07 m⁻¹` imply an inferred pattern roughness
  `L_x ≈ 3.07e−07 s/m²`. Sanity: `F ≈ 1/7 = 0.143 s/m` varying by `≈0.03 s/m` across a 100 km
  feature half-width gives `3e−07 s/m²`. Consistent to one significant figure — so (3.36) is not
  only proved but corroborated by the measurement. *(This inference is a consistency check, not
  an independent measurement of `L_x`.)*

**What this establishes, and it is contribution 3 of `CORE-THEOREM` §9.**

- **Regime A confirms the mechanism exactly.** `L_t` in the co-moving frame is identically zero,
  to the last bit. `Prop 3.6(b)` is not approximately true.
- **Regimes B and C are the practically important result.** The reduction takes a field on which
  the causality condition is *violated* (`r·L_t = 1.31 > 1`, single-pass **not** licensed) and
  makes it comfortably satisfied (`0.26`). The consequence is not a speed-up; it is the
  difference between a solve that has a licence and one that does not.

**Three caveats, each of which costs the claim something. All three are mandatory reporting.**

1. **The median gets *worse*, by about 4.5×.** From the table: B, `3.75e−07 → 1.69e−06`, a factor
   `0.222` "improvement" i.e. **4.51× worse**; C, `3.52e−07 → 1.63e−06`, `0.216`, **4.63× worse**.
   The mechanism is clear and not a bug: in the ground frame most cells are far from any system
   and see almost no temporal change; in the co-moving frame the sampling point slides through
   space, so quiet cells now see the field vary. **De-advection trades a large improvement in the
   worst cells for a moderate degradation in already-benign ones.** Because the causality
   condition is a *worst-case* condition — (3.27) must hold at every cell the sweep touches — this
   is the right trade. But it is a trade, not a free win, and reporting only the max oversells it.
2. **Regime A's identifiability is not established.** Its test field was `x`-invariant (a jet), so
   only `w_y` was identifiable; the optimiser recovered `w_y = +0.500` exactly against a true
   `+0.5` and left `w_x` unconstrained. The *exactness of the reduction* is established by that
   test; the *identifiability of `w`* is not.
3. **In B and C the optimised `w` is nowhere near the meteorological advection velocity**
   (`(−0.56, −1.38)` against a true `(+2.0, +0.5)`). Once A1 is violated, minimising the residual
   causality constant and estimating the storm track are **different problems**, and it is the
   former the algorithm wants. The optimised `w` must not be presented as a storm-track estimate.

**Scope of the measurement.** Test 8.10's three regimes are *constructed* fields (translating
Gaussian system; the same with 35 %/day intensification; the same plus a second system at a
different `w`), designed to span A1-exact to A1-badly-violated. `CORE-THEOREM` §9 records that the
same test on a **real operational forecast stack has not yet been run**. The mechanism is proved
and the magnitudes are measured on constructed fields; the operational magnitudes are not yet
measured. State it that way.

### 3.9.3 Choosing `w`, and a conflict inside CORE-THEOREM that implementers will hit

`w` is chosen by **directly minimising the co-moving causality constant** (`CORE-THEOREM` C.10):

```
w*  =  argmin_w   P₉₉ over the domain of   max_u | ∂F_w/∂t |                            (3.39)
```

by coarse-to-fine search on a 2-D grid — three rounds of 9×9 is ample, and the field evaluation
vectorises. The 99th percentile rather than the max keeps one pathological cell from steering the
choice.

The natural alternative, **phase correlation between consecutive forecast frames, was tried and
failed badly**: against a true dominant `w = (2.0, 0.5)` it returned `(−0.74, 0.00)`. It locks
onto whichever feature carries the most gradient energy, which need not be the one governing the
causality constant. (3.39) optimises the quantity the algorithm actually needs.

> **Conflict found and reported, not resolved unilaterally.** `CORE-THEOREM.md` §8, the algorithm
> box, still reads `1. ADVECTION ESTIMATION: w ← phase-correlate consecutive forecast frames`.
> That contradicts §7 of the same document (which records phase correlation failing), contradicts
> C.10/(3.39), and contradicts the reference implementation, where `comoving.choose_advection`
> implements (3.39) by coarse-to-fine minimisation of `residual_causality_constant`. **The
> normative choice is (3.39).** `CORE-THEOREM` §8 step 1 should be amended.

### 3.9.4 What this means for an implementation

1. **Estimate `w` by (3.39)** and build the co-moving field (`𝒱_w(y) = 𝒱₀(y) ⊖ w`, i.e. subtract
   `w` from the drift vector — no new metric code is required, because the shift of the drift
   *is* the shift of the whole indicatrix).
2. **Solve stationary.** No causality check, no wait relaxation, no `L_t` estimate. `Alg 4.x` runs
   with `Def 3.4(b)`'s margin pinned at 1.
3. **Report the residual anyway.** Compute `L_t^R` and `r·L_t^R` per (3.38) and log them. If the
   residual is significant, the ground-frame corrector sweep (`CORE-THEOREM` §8 step 6) applies
   §3.4–§3.7 to `L_t^R` — that, and only that, is what the causality apparatus is now for.
4. **Two implementation requirements that fail silently** (`CORE-THEOREM` §8.1; both were found by
   building, not by thinking, and neither is visible in the mathematics):
   - **R1 — dilate the co-moving grid by `|w|·t_max` opposite to `w`.** Reaching ground point
     `x_B` at time `t` requires node `y = x_B − wt` to be inside the grid. Undersized, this fails
     silently: the sweep converges, the route looks plausible, the landfall is wrong. Measured on
     a 140 h voyage with `w = (1,1) m/s`: the required node lay 4.5° west of the grid edge, a
     **104.5 km miss that a full-grid scan could not reduce**. Extending by `|w|t_max ≈ 500 km`
     brought it to **11.2 km**, under half a grid diagonal.
   - **R2 — do not select the goal node by the interception root find.** Sampling `T` at the
     nearest node makes `g(t) = T_w(x_B − wt) − t` a step function, so a bisection converges to a
     discontinuity; and because the ground position is `y + w·T[y]`, the timing error is amplified
     by `|w|`. Instead evaluate the interception condition (C.4) **directly on the
     discretisation**: every node has a ground landfall `y + w·T[y]`, so take the node minimising
     `‖(y + w·T[y]) − x_B‖`, at `O(N)` with one great-circle distance per node. The root find
     remains the right method in a continuum implementation and is still useful for reporting
     `t*`.

### 3.9.5 What the reduction does *not* fix, stated plainly

- **A1 is an assumption about the weather, not about the ship.** It holds well for isolated,
  coherently translating systems over 2–5 day horizons — the tropical-cyclone and monsoon-surge
  case. It degrades for rapidly deepening or merging systems, and there the reduction is a
  preconditioner, not a solution. Then §3.4–§3.7 are back in force, applied to `L_t^R`.
- **A2 (outrun, `|w| < σ_min^w`) is a separate hypothesis** and is what makes the interception
  (C.4) have a root at all. Where it fails, the honest output is *no interception within the
  horizon* — the weather system cannot be outrun — not a longer route.
- **The reduction does not improve the median cell** (caveat 1 above), and it does not remove the
  fixed-stencil metrication floor of ~1 % (`CORE-THEOREM` §4): that floor is a stencil property
  and survives any change of frame. Indeed the two frames quantise heading *differently*, so
  their metrication errors do not cancel — which is why the two-grid comparison is the wrong
  instrument for testing `Thm C.1`, and why the per-leg bijection residual (`9.77e−14 m/s`) is
  the test that settles it.
- **In regime A the causality benefit is nil, because the ground frame was already licensed**
  (`r·L_t = 0.035`). In the A1-exact case the reduction's payoff is *exactness* — elimination of
  temporal discretisation error, measured at `2.8e−14 m/s` against `6.7e−3 m/s` for the
  ground-frame solve (`CORE-THEOREM` §4) — not licensing. The two payoffs bite in complementary
  regimes, and conflating them oversells both.
- **End-to-end, on the 3 698 km Kochi→Aden-corridor voyage** of `CORE-THEOREM` §8.2 the causality
  constant was never near the limit in either frame: `L_t` `3.22e−07 → 1.24e−07` (2.60×), and
  `r·L_t` at `r = 2h = 55 km` went `0.0177 → 0.0068`. (Check: `3.22e−07 × 5.5e4 = 0.01771` ✓;
  `1.24e−07 × 5.5e4 = 0.00682` ✓.) On that voyage the reduction's value was accuracy and
  structure, not a licence. Say so.

---

## 3.10 Prop 3.5 — the costate system, and Zermelo's navigation formula derived

The eikonal gives the value function. The Pontryagin system gives the *route*, and it gives the
single most useful correctness test in the project. Everything here is classical (Zermelo 1931;
Bryson & Ho 1975 for the modern PMP form); it is derived rather than quoted because the derivation
is what fixes the sign conventions, and the convention traps here are the ones that actually bite.

### 3.10.1 Setup

Work in the local frame with the mathematical convention `x = (x₁, x₂) = (east, north)` and

```
ẋ  =  V_s n(θ)  +  c(x) ,        n(θ) = (cos θ, sin θ) ,   θ measured CCW from east.
```

(The nautical convention `n(θ_nav) = (sin θ_nav, cos θ_nav)`, `θ_nav` clockwise from north, is
CONTRACT §1's and is restored in §3.10.5. Deriving in the mathematical convention and converting
once is safer than deriving in the nautical one, because every published form of Zermelo's formula
is in the mathematical convention and a silent mismatch is a plausible-looking wrong route.)

Write `c = (u_c, v_c)` and abbreviate the four partial derivatives

```
u_x := ∂u_c/∂x₁ ,  u_y := ∂u_c/∂x₂ ,  v_x := ∂v_c/∂x₁ ,  v_y := ∂v_c/∂x₂ .
```

Stationary field (the co-moving case; see §3.10.4 for why that is the right case to treat).

### 3.10.2 Prop 3.5

> ### Proposition 3.5 (Costate system and Zermelo's navigation formula)
> For the minimum-time problem above with `|c| < V_s`, along any optimal trajectory:
>
> **(a) Maximum principle.** There is an absolutely continuous costate `p : [0,T] → ℝ² ∖ {0}` with
> ```
> ṗ  =  − ( ∇c )ᵀ p ,        i.e.   ṗ₁ = −( p₁ u_x + p₂ v_x ) ,  ṗ₂ = −( p₁ u_y + p₂ v_y )  (3.40)
> ```
> and the optimal heading is the covector direction,
> ```
> n(θ)  =  p / |p| ,                                                                    (3.41)
> ```
> with the transversality/normalisation `V_s|p| + ⟨c,p⟩ = 1`; moreover `p = ∇T` wherever `T` is
> differentiable, so (3.41) says the optimal heading is normal to the arrival-time level set *in
> the dual sense*, not the Euclidean one.
>
> **(b) Zermelo's navigation formula.**
> ```
> dθ/dt  =  v_x sin²θ  +  ( u_x − v_y ) sin θ cos θ  −  u_y cos²θ                       (3.42)
> ```
>
> **(c) Invariant form — heading responds only to shear.** With vorticity `ω := v_x − u_y`,
> normal strain `s_n := u_x − v_y`, shear strain `s_s := v_x + u_y`, and divergence
> `δ := u_x + v_y`,
> ```
> dθ/dt  =  ½ [ ω  −  s_s cos 2θ  +  s_n sin 2θ ] .                                     (3.43)
> ```
> **`δ` does not appear.** Neither does `c` itself. The optimal heading responds to the *velocity
> gradient*, and within it only to the vorticity and the strain — never to the magnitude of the
> current, never to its divergence.

**Proof of (a).** Minimum time is `min ∫₀^T 1 dt` subject to `ẋ = f(x,θ) := V_s n(θ) + c(x)`. The
Pontryagin maximum principle for a free-terminal-time, fixed-endpoint problem gives an absolutely
continuous `p` and a constant `p₀ ≤ 0`, not both zero, with `H(x,p,θ) := ⟨p, f(x,θ)⟩ + p₀`
maximised over the control at a.e. `t`, `ẋ = ∂H/∂p`, `ṗ = −∂H/∂x`, and `H ≡ 0` along the optimal
trajectory (free terminal time). Normalise `p₀ = −1` (the abnormal case `p₀ = 0` forces `p ≠ 0` and
`max_θ H = V_s|p| + ⟨c,p⟩ ≥ (V_s − |c|)|p| > 0` by `|c| < V_s`, contradicting `H ≡ 0`; so the
problem has no abnormal extremals — **this is exactly where (H1) is used, and without it abnormal
extremals must be considered**).

Maximising `H` over `θ`: `max_θ ⟨p, V_s n(θ)⟩ = V_s |p|`, attained uniquely at `n(θ) = p/|p|`
(uniqueness because `p ≠ 0` and the disc is strictly convex), which is (3.41). Then `H ≡ 0` reads

```
V_s |p|  +  ⟨ c(x), p ⟩  =  1                                                          (3.44)
```

— **which is exactly the eikonal (3.16) with `p = ∇T`.** So the maximum principle and the HJB
formulation agree, and `p` is the gradient of the value function, as claimed. The costate equation
is `ṗ_i = −∂H/∂x_i = −⟨p, ∂c/∂x_i⟩`, which written out is (3.40) (`n(θ)` does not depend on `x`,
so the `V_s n(θ)` term contributes nothing). ∎

**Proof of (b).** By (3.41), `p = |p|(cos θ, sin θ)`, so `θ = atan2(p₂, p₁)` and, wherever `p` is
differentiable,

```
dθ/dt  =  ( p₁ ṗ₂ − p₂ ṗ₁ ) / |p|² .
```

Substituting (3.40):

```
p₁ṗ₂ − p₂ṗ₁  =  −p₁( p₁ u_y + p₂ v_y )  +  p₂( p₁ u_x + p₂ v_x )
              =  v_x p₂²  +  ( u_x − v_y ) p₁ p₂  −  u_y p₁² .
```

Divide by `|p|²` and use `p₁/|p| = cos θ`, `p₂/|p| = sin θ`:

```
dθ/dt  =  v_x sin²θ  +  ( u_x − v_y ) sin θ cos θ  −  u_y cos²θ ,
```

which is (3.42). Note `|p|` cancels identically — the turning rate is independent of the
normalisation of the costate, as it must be. ∎

**Proof of (c).** Invert the definitions: `v_x = (ω + s_s)/2`, `u_y = (s_s − ω)/2`,
`u_x − v_y = s_n`. Substitute into (3.42):

```
dθ/dt = (ω+s_s)/2 · sin²θ  −  (s_s−ω)/2 · cos²θ  +  s_n sin θ cos θ
      = (ω/2)( sin²θ + cos²θ )  +  (s_s/2)( sin²θ − cos²θ )  +  (s_n/2)( 2 sin θ cos θ )
      = ω/2  −  (s_s/2) cos 2θ  +  (s_n/2) sin 2θ ,
```

using `sin²θ + cos²θ = 1`, `sin²θ − cos²θ = −cos 2θ`, `2 sinθ cosθ = sin 2θ`. That is (3.43), and
`δ = u_x + v_y` appears in none of `ω, s_n, s_s`. ∎

### 3.10.3 Three exact consequences, and why (3.43) is the sharpest test available

Each of the following is an *exact* statement with no discretisation in it, which is what makes
them testable to machine precision on any implementation, in any language, without a reference
solution.

**(i) Uniform current ⇒ zero turning.** All four partials vanish, so `dθ/dt ≡ 0` identically, for
every heading, every position, every current magnitude. The optimal route in a uniform current is
a **single constant heading** from departure to arrival, with **zero intermediate turns**. This is
golden-vector test G4, and the required tolerance is `max |dθ/dt| < 1e−14 rad/s`, i.e.
floating-point zero. Quantitatively, with `V_s = 7.2 m/s`, `c = (1.5,0) m/s`, and the equatorial
leg `0°E → 5°E` of length `555 974.633 2 m`: `σ = 8.7 m/s` and the arrival is
`63 905.130 3 s = 17.751 425 h`; against the current, `σ = 5.7` and `97 539.409 3 s = 27.094 280 h`;
and the ratio `27.094 280/17.751 425 = 1.526 315 789 5` must equal
`Υ = (V_s+|c|)/(V_s−|c|) = 8.7/5.7 = 1.526 315 789 5` to all printed digits — two completely
different code paths (a full sweep versus a one-line ratio) agreeing to 10 figures.

**(ii) Pure divergence ⇒ zero turning.** Take `c = (k x₁, k x₂)`: then `u_x = v_y = k`,
`u_y = v_x = 0`, so `ω = s_n = s_s = 0` and `dθ/dt ≡ 0` by (3.43) — even though `|c|` and `∇·c` are
both large. This test discriminates against the commonest wrong implementation, one that couples
the heading to the current *magnitude* or to its divergence.

**(iii) Solid-body rotation ⇒ heading co-rotates at exactly `ω/2`.** Take `c = Ω(−x₂, x₁)`: then
`u_x = v_y = 0`, `u_y = −Ω`, `v_x = +Ω`, so `ω = 2Ω`, `s_n = s_s = 0`, and (3.43) gives
`dθ/dt = Ω` exactly, for every heading. Physically necessary: the whole problem is invariant under
co-rotation with the fluid. This is an exact non-trivial value — not zero — so it discriminates
against implementations that pass (i) and (ii) merely by returning zero.

**Why (3.43) is the sharpest correctness test an implementation has.** It is independent of the
destination, of the grid, of the stencil, of any reference solution, and of the solver's global
correctness; it is a pointwise identity on the recovered route. It fails loudly and
distinguishably for: transposed east/north (swaps `u_c ↔ v_c`, flipping the sign of `ω` and of
`s_n`); a finite-difference frame in degrees rather than metres (`dθ/dt` scales by
`R_E cos ϕ · π/180 ≈ 10⁵`, i.e. off by five orders of magnitude, unmissable); a sign flip in the
drift decomposition (flips `ω`); a `ζ` minimisation that is not actually minimising (the recovered
route acquires spurious turns); and **any stencil that quantises heading** — a fixed
`m`-neighbour stencil emits waypoints in a uniform field, and by (i) those waypoints are pure
numerical artefacts. If your router emits waypoints in a uniform current field, everything
downstream is suspect. Conversely, an implementation that satisfies (i)–(iii) to `1e−14` has its
frame, units, signs, and inner minimisation all correct simultaneously, which no other single test
establishes.

### 3.10.4 Corollary 3.5.1 — the heading law is Galilean invariant, so `Thm C.1` holds at the level of the necessary conditions too

> **Corollary 3.5.1.** Let `w` be constant and let `c_eff := c₀ − w` be the co-moving drift
> (`CORE-THEOREM` C.6). Then `∇c_eff = ∇c₀` — a constant shift has zero gradient — so `ω`, `s_n`,
> `s_s` are identical in the two frames and (3.43) has **identical coefficients** in the ground and
> co-moving frames. Moreover the commanded heading is itself frame-invariant: the through-water
> velocity is `v − c` in the ground frame and `(v−w) − (c₀−w) = v − c` in the co-moving frame, the
> same vector. Hence the optimal heading history `θ(·)` is the same function of time in both
> frames.

**Proof.** `∇(c₀ − w) = ∇c₀` since `w` is constant, so the four partials, hence `ω, s_n, s_s`, are
unchanged. By `Thm C.1(a)` the trajectories correspond with the same time parameterisation, and by
the displayed identity the through-water velocity — hence `n(θ) = (v−c)/V_s` — agrees at
corresponding times. The costates then satisfy the *same* linear ODE (3.40) with the same
coefficient matrix `(∇c₀)ᵀ` evaluated at corresponding points, and the same maximisation (3.41)
pins their common direction. ∎

**Why this is worth stating.** `Thm C.1` is proved in `CORE-THEOREM` from the dynamic programming
side (bijection of admissible trajectories). Corollary 3.5.1 confirms it independently from the
**Pontryagin** side: the necessary conditions for optimality are literally the same system in both
frames. Two derivations from different halves of optimal control agreeing is worth more than
either alone, and it costs one line — the gradient of a constant is zero.

It also explains the *shape* of the measured result in §3.9.2: the reduction changes `L_t`, which
is about the *value function's* time dependence, while leaving the turning law untouched. The
routes in the two frames are the same routes; only the licence to compute them in one pass
differs.

### 3.10.5 The nautical convention, and the conversion trap

CONTRACT §1 fixes `θ` as **true heading, clockwise from north**, `n(θ) = (sin θ, cos θ)`. The
conversion is `θ_nav = π/2 − θ_math`, hence `dθ_nav/dt = −dθ_math/dt`, and `2θ_math = π − 2θ_nav`
gives `cos 2θ_math = −cos 2θ_nav`, `sin 2θ_math = sin 2θ_nav`. Substituting into (3.43):

```
dθ_nav/dt  =  − ½ [ ω  +  s_s cos 2θ_nav  +  s_n sin 2θ_nav ]                          (3.45)
```

Note the two changes: an overall sign, **and** a sign change on the `s_s` term only. An
implementation that flips only the overall sign passes the uniform-current test (i), passes the
divergence test (ii), passes the solid-body test (iii) — because `s_s = 0` in all three — and is
wrong in every field with shear strain.

> **(iv) Pure shear strain — the fourth test, and the only one that catches the `s_s` sign.**
> Take `c = (γ x₂, 0)`, a zonal current increasing northward. Then `u_y = γ` and
> `u_x = v_x = v_y = 0`, so `ω = v_x − u_y = −γ`, `s_s = v_x + u_y = +γ`, `s_n = 0`, `δ = 0`.
> ```
> mathematical convention, (3.43):  dθ/dt      = ½[ −γ − γ cos 2θ ]      = −γ cos²θ
> nautical convention,   (3.45):    dθ_nav/dt  = −½[ −γ + γ cos 2θ_nav ] = +γ sin²θ_nav      (3.45b)
> ```
> Both are non-zero and heading-dependent, and the two are consistent under
> `θ_nav = π/2 − θ_math` (`cos²θ_math = sin²θ_nav`, plus the overall sign) — which is itself a
> check that the conversion was done correctly. A `γ = 10⁻⁵ s⁻¹` shear (1 m/s over 100 km, a
> realistic western-boundary-current edge) turns the optimum by `γ·T ≈ 0.5 rad` over a 14-hour
> leg at `θ_nav = 90°`: not a rounding error, and the sign of it decides which side of the
> current you route.

---

## 3.11 Cut loci: what they are, why `T` is non-smooth there, and what the algorithm must do

### 3.11.1 Definition and physical meaning

> **Definition (cut locus).** `Cut(x_A) := { x ∈ Ω : more than one minimising trajectory from
> `x_A` reaches `x` in time `T(x)` }`, together with the points beyond which a given minimising
> trajectory ceases to be minimising.                                                     (3.46)

Physically it is the *"north or south of the storm, both equally good"* set. It is not a numerical
artefact and it is not rare: it is created whenever the domain routes around an obstruction — a
cyclone, a landmass, a banned-sea-state region — and its trace on a chart is the ridge where two
advancing fronts meet. Every long-haul route through the Indian Ocean in cyclone season has one.

Two distinct mechanisms generate it, and they should not be conflated:

- **Global tie (the common case).** Two topologically distinct trajectory families — one around
  each side of an obstruction — arrive with equal time. Nothing is singular locally; the arrival
  times simply coincide.
- **Focusing / conjugate points.** Neighbouring characteristics from the same family cross,
  forming a caustic. This is a local phenomenon of the geodesic flow and requires curvature of the
  metric, i.e. spatial structure in `c` or in the seakeeping bans.

### 3.11.2 Why `T` is non-smooth there — proved

`T(x) = inf over trajectories` is an **infimum of a family of functions**, each smooth where the
corresponding trajectory family is. An infimum of smooth functions is in general only Lipschitz,
and at a point where the infimum is attained by two families with distinct arrival covectors
`p⁽¹⁾ ≠ p⁽²⁾`, `T` cannot be differentiable: were `∇T(x)` to exist it would be a supergradient
common to both branches, but near `x` the value function is bounded above by each branch's smooth
extension, and their first-order expansions in a direction `d` with `⟨p⁽¹⁾ − p⁽²⁾, d⟩ ≠ 0` disagree
at first order, so `T(x + εd) ≤ min(⟨p⁽¹⁾,εd⟩, ⟨p⁽²⁾,εd⟩) + T(x) + o(ε)`, whose right-hand side is
not differentiable in `d` at `ε = 0`. Hence `T` has a **concave kink** across the cut locus, never
a convex one — the value function is *semiconcave*, and the kink always opens downward.

Consequences, in decreasing order of certainty:

- **`T` is differentiable a.e.** `T` is Lipschitz by (3.2), so by Rademacher's theorem it is
  differentiable Lebesgue-a.e. and the non-differentiability set — which contains the cut locus —
  has **measure zero**. This is complete, and it is all we prove here.
- **`T` is locally semiconcave** under (H1)–(H3) with a uniformly convex, `C^{1,1}` indicatrix.
  This is standard (Cannarsa & Sinestrari, *Semiconcave Functions, Hamilton–Jacobi Equations and
  Optimal Control*, 2004), and we **cite rather than prove** it; the conclusion we use from it —
  that `T` is differentiable exactly where the minimiser is unique — is likewise cited. Under (H4)
  the indicatrix is convex but need not be *uniformly* convex or `C^{1,1}` — a throttle family
  with a flat segment produces a facet — so semiconcavity is not automatic in KAIROS's general
  setting. **We flag this rather than assume it.** The Randers case *is* uniformly convex
  (`𝒱 = D(c,V_s)`), so the cited results apply on the fast path without qualification.
- **The viscosity solution is the right object.** At the kink there are two candidate classical
  solutions; the viscosity condition selects the one with the concave kink, which is the one that
  is the value function. This is exactly what a monotone scheme computes, which is why nothing
  special is required of the algorithm — see next.

### 3.11.3 What the algorithm must do

1. **The sweep needs no special case.** `Thm 3.1` and `Prop 4.9` never assume differentiability of
   `T`; they are statements about a finite Bellman system. Monotone + stable + consistent schemes
   converge to the viscosity solution *including across shocks* (Barles–Souganidis 1991), which is
   `Thm 7.1`. Do not add shock detection to the sweep. It cannot help and it will break
   monotonicity.
2. **The route is not unique and must not be reported as if it were.** By Remark 3.1.1 the values
   `T_h` are tie-break independent but the **backpointers are not**: at a cut locus the returned
   route is whichever branch the tie-break happened to select, and an arbitrarily small change in
   the forecast can flip it. An implementation that reports a single route across a cut locus as
   *the* optimum is reporting a coin flip. Detect it — two labels within `Δ_min` at a node, or a
   backpointer whose parent's incoming direction differs by more than a threshold from the node's
   own — and **surface both branches to the operator**. "There are two equally good options here"
   is a feature worth showing a master, not an error to hide.
3. **Do not run gradient-based polish across a cut locus.** The Newton/shooting polish of `§6`
   solves for a stationary point of a functional that is non-smooth exactly there, and it will not
   converge — correctly, because there is nothing to converge to. Normative behaviour (playbook
   S8): **cap at 8 iterations, return the unpolished grid route for that leg, and flag the leg.**
   It **is** a bug if the polish fails to converge in a *uniform* field, where by §3.10.3(i)
   `dθ/dt ≡ 0` and one Newton step should nail it; failure there means the variational derivative
   has the wrong sign or the RK4 integration is in the wrong frame (degrees where metres are
   meant).
4. **The certificate is unaffected.** `Cor 4.12`'s a posteriori bound is a statement about the
   *value*, `(J − T_low)/T_low`, and the value is single-valued across a cut locus even when the
   route is not. This is another reason the a posteriori certificate is the primary guarantee
   (`ERRATA` E6) rather than the a priori bound.
5. **Multi-objective labels resolve most ties for free.** Two routes that tie on time will
   generically *not* tie on fuel and risk, so the ε-Pareto front of `§5` carries both branches as
   distinct non-dominated labels and the operator sees the trade-off explicitly. This is the
   cleanest resolution available and it costs nothing extra, since the labels are being carried
   anyway.
6. **Under the Co-Moving Reduction the cut locus is a genuine geometric object.** `T_w` is the
   distance function of a *stationary* Finsler metric, so `Cut(x_A)` is the classical Finsler cut
   locus of that metric — closed, of measure zero, and independent of any time discretisation. In
   the ground frame the corresponding set is its image under `x = y + w·T_w(y)`, which can look
   qualitatively different (it is sheared by the advection) even though it is the same set of
   decisions. When plotting a "decision ridge" for an operator, state which frame it is drawn in.

---

## 3.12 Summary for the implementer

**What you must implement from this file, in the co-moving frame (the normative path):**

| Item | Where | Effort |
|---|---|---|
| Stationary eikonal via `support` (3.5), gauge/support duality | §3.1 | already in `Prop 2.7` |
| The sign check `support(p) + support(−p) = 2V_s\|p\|` in the Randers case | §3.2.3 | one unit test |
| The duality/crab-angle cross-check against golden vector T4 | §3.3.1 | one unit test |
| `ℓ_min = h/√2` exclusion in the update; `Δ_min = ℓ_min F_min` bucket width | §3.4.2 | two lines, load-bearing |
| Nothing else. `L_t ≡ 0`, so `Thm 3.1`, `Prop 3.2`, `Thm 3.3` are vacuous | §3.9 | — |
| Report `r(x)·L_t^R` anyway, per cell and as `max`/`p99` | §3.9.4 | diagnostic |
| Zermelo turning-rate tests (i)–(iii) and the shear test of (3.45) | §3.10.3–5 | four unit tests, highest value per line in the project |
| Cut-locus behaviour: cap the polish, flag the leg, surface both branches | §3.11.3 | UI + one flag |

**What you must implement additionally if `A1` fails badly and you run the ground-frame corrector
(`CORE-THEOREM` §8 step 6):** the causality diagnostic `Def 3.4(b)` at `r(x)` (**never** at `h`),
and the wait relaxation (3.32) with the `ℓ`-scaling and horizon truncation, with a counter for
horizon-truncated evaluations.

**Status of every claim in this file.**

| Claim | Status |
|---|---|
| `Lemma 3.A`, `3.B`, `3.C`, `3.D`, `3.E`, `3.F` | proved in full here |
| Eq (3.5), (3.10), (3.14) incl. the sign of each | derived here from the DPP, not asserted |
| `Thm 3.1(a),(b)` | proved in full here; **the result is Vladimirsky (2006)**, restated |
| `Thm 3.1(c)` / `Prop 3.2` | proved by explicit construction with concrete numbers |
| `Thm 3.3(a)–(d)` | proved in full here; unconditional |
| `Prop 3.5(a)–(c)`, `Cor 3.5.1` | derived in full here; the formula is Zermelo (1931) |
| `Prop 3.6(a)–(c)` | proved here; the underlying `Thm C.1` is proved in `CORE-THEOREM` §3 and verified numerically to `9.8e−14` |
| Test 8.10 numbers (§3.9.2) | **measured** on constructed regimes A/B/C; **not yet** on a real forecast stack |
| `L_x ≈ 3.07e−07 s/m²` (§3.9.2) | **inferred** from (3.36) and the regime-A measurement; a consistency check, not a measurement |
| Aggregate clamp perturbation `O(1)` along a route | **Conjecture 3.E.2**, explicitly unproved; measured instead |
| Semiconcavity of `T` in the general (non-uniformly-convex) indicatrix case | **not established**; cited only for the Randers case |
| Fixed-stencil metrication floor ~1 %, non-vanishing under refinement | measured, `CORE-THEOREM` §4 |

**Conflicts between normative documents, found while writing this file and reported here rather
than resolved unilaterally:**

1. `CORE-THEOREM.md` §8 algorithm box step 1 prescribes **phase correlation** for `w`; §7 and
   (C.10) of the same document, and the reference implementation, prescribe **minimisation of the
   residual causality constant**, and record phase correlation *failing*. §3.9.3 takes (3.39) as
   normative and flags §8 step 1 for amendment.
2. `CORE-THEOREM.md` §7 presents Test 8.10 as **measured**; §9 records it as **still to be run on
   a real forecast stack**. Resolved in §3.9.2 by stating exactly what was measured on what: three
   constructed regimes, not an operational stack.
3. `A1`/`A2` name collision between `CORE-THEOREM.md` (frozen advection, outrun) and the earlier
   `§3`/`§7` standing assumptions (non-degeneracy, Lipschitz). Resolved in §3.0.1 by relabelling
   this file's hypotheses `(H1)`–`(H5)` and reserving `A1`, `A2` globally for the CORE-THEOREM
   meanings.
4. `CONTRACT.md` D3 (`Δ_min = h F_min`; heap fallback on `F_min → 0`) is overridden by `ERRATA`
   E2 (`Υ_heap = 12`) and E3 (`Δ_min = h F_min/√2`); `CONTRACT.md` §1 (A1) (`0 ∈ int 𝒱`) is
   overridden by `ERRATA` E9 (`0 ∈ int conv 𝒱`); `CONTRACT.md` §5's novelty claim for
   `Thm 3.1/3.3` is overridden by `ERRATA` E10. ERRATA wins in all four, per its own status line.
5. `handbook/01-golden-vectors.md` §G5 requires reporting `max h·L_t` and
   `handbook/02-debugging-playbook.md` §S7 gives a sanity range for `h·L_t`. Both are the
   superseded quantity (`ERRATA` E4); the required diagnostic is `max_x r(x)·L_t`. The handbook
   should be amended; §3.4.2 gives the conversion in the meantime.
