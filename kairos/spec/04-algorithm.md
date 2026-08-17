# §4 — The Algorithm

**Block ownership (CONTRACT §2).** This file owns `§4`, `Alg 4.x`, `Prop 4.x`, `Cor 4.x` and
`Eq (4.x)`. Fixed by the CONTRACT and not renumbered here: `Prop 4.7` (stencil locality),
`Prop 4.9` (bucket queue), `Prop 4.11` (coarse heuristic), `Cor 4.12` (certificate).
`Alg 4.1` (the semi-Lagrangian update) and `Alg 4.3` (the label-setting driver) are already
cited by `07-complexity.md §7.2.1` and `03-causality.md §3.6` and keep those meanings.
Objects owned elsewhere (`Thm C.1`, `Thm 3.1`, `Thm 3.3`, `Prop 2.7`, `Thm 5.2`, `Thm 7.1`)
are cited, never restated with a new number.

**Normative precedence.** `CORE-THEOREM.md` and `ERRATA.md` override `CONTRACT.md`. In
particular this file implements **E1** (reachable cone, not a Kropina branch), **E2**
(`Υ_heap` fallback, *not* an `F_min → 0` test), **E3** (`c_geo = 1/√2` and the `ℓ_min`
exclusion, *not* `Δ_min = h·F_min`), **E4** (`r(x)·L_t`, not `h·L_t`), **E5** (`ℓ`-scaled
wait relaxation with horizon truncation), **E7** (value bucketing) and **D5** (dilated cell).
Where this file has had to correct a normative document, it says so in §4.16.

**What is new here and what is not.** New: nothing in this file except the *consequences* of
`Thm C.1` — specifically §4.4 (choosing `w` by minimising the residual causality constant),
§4.5 (the co-moving grid and its mandatory dilation), §4.7 (interception solved on the
discretisation), and the licence in §4.6 to run the sweep with **no causality test at all**.
Everything else is supporting apparatus with named prior art: ordered upwind is
**Sethian & Vladimirsky (2003)**; the single-pass licence for time-dependent control is
**Vladimirsky (2006)**; the bucket queue is **Dial (1969)**; label-setting on general update
families is **Martins (1984)**; the ε-bucketed labels are **Tsaggouris & Zaroliagis (2009)**
and **Kumar & Vladimirsky (2010)**; convergence is **Barles & Souganidis (1991)**; the
navigation ODE is **Zermelo (1931)** with the Randers correspondence of
**Bao, Robles & Shen (2004)**; the frozen-pattern hypothesis behind A1 is **Taylor (1938)**;
level-set ship routing is **Lolla & Lermusiaux (2014)**; time-dependent-only indicatrices are
**Markvorsen (2025)**; dynamic shortest-path repair is **Ramalingam & Reps (1996)**;
seakeeping bans follow **IMO MSC.1/Circ.1228**, with **Ochi (1964)** for slamming and
**Fujiwara (2006)** for wind resistance.

---

## 4.1 The pipeline

Reproduced verbatim in structure from `CORE-THEOREM.md §8`, with each step bound to the
section of this file that specifies it. Steps 1, 2, 4, 5 and the *licence* for step 3 are the
new content; steps 3, 6, 7 are apparatus.

```
KAIROS(vessel, forecast stack, x_A, x_B, t₀):

  1. ADVECTION ESTIMATION        →  §4.4,  Alg 4.4
       w  ←  argmin_w  P₉₉ over the domain of  max_u |∂F_w/∂t|            (C.10)
       R  ←  E(x,t) − E₀(x − w t)                                          (C.8)
       report  L_t(E),  L_t(R)  and their ratio

  2. CO-MOVING METRIC            →  §4.5,  Alg 4.5
       𝒱_w(y) = 𝒱₀(y) ⊖ w   — implemented as  c ← c₀ − w                  (C.3, C.6)
       check A2 and |c₀−w| < V_max cell by cell; flag failures via E1
       DILATE the co-moving grid by |w|·t_max opposite to w        [R1, mandatory]

  3. STATIONARY SOLVE            →  §4.6,  Alg 4.1 / Alg 4.2 / Alg 4.3
       T_w ← ordered-upwind semi-Lagrangian sweep, adaptive stencil,
             monotone bucket queue, ℓ_min exclusion
       NO causality condition is evaluated: Thm C.1(b) makes it vacuous

  4. INTERCEPTION                →  §4.7,  Alg 4.6
       solve  t* = min{ t : T_w(x_B − w t) ≤ t }  ON THE GRID       [R2, mandatory]
       (the root find is for reporting only)                              (C.4)

  5. ROUTE RECOVERY              →  §4.7,  Alg 4.8
       backtrack in y; map  x(s) = y(s) + w·τ(s)                          (C.5)

  6. RESIDUAL CORRECTOR          →  §4.9,  Alg 4.9        [only if R is significant]
       one ground-frame corrector sweep seeded by step 5, causality guard
       applied to L_t^R, wait relaxation (E5.1) where it fails

  7. MULTI-OBJECTIVE / CERTIFICATE →  §4.10–§4.11         [supporting apparatus]
       ε-bucketed Pareto labels (E7);  dilated-cell optimistic coarse solve
       (Alg 4.10, Prop 4.11) → a posteriori certificate (Cor 4.12)
       Zermelo polish (Alg 4.13), notch projection (Alg 4.14)
```

The whole of §4.6 — the most machinery-heavy section — exists to solve a **stationary**
problem. That is the point of `Thm C.1`: the apparatus is unchanged, but it is now being run
on a problem for which it is unconditionally licensed, instead of on one where its licence
has to be checked cell by cell and repaired where it fails.

---

## 4.2 Discretisation

### 4.2.1 The lattice

Node-centred uniform lattice in `(λ, ϕ)`. Node `(i, j)` sits at

```
ϕ_i = ϕ_min + i·Δ ,     λ_j = λ_min + j·Δ ,     Δ = step in radians          (4.1)
0 ≤ i < n_ϕ  (south → north) ,   0 ≤ j < n_λ  (west → east)
```

**Flat index, NORMATIVE:**

```
n = i·n_λ + j ,        i = n div n_λ ,   j = n mod n_λ                       (4.2)
N = n_ϕ · n_λ
```

Row-major in `j`, so one latitude row is contiguous. This is not cosmetic: the stencil
template (§4.2.3) is constant along a row, so a row-contiguous layout makes the inner loop a
strided read with a per-row constant, and the template table is built once per row instead of
once per node.

Metric spacing per row (the only row-dependent quantity is `cos ϕ`):

```
h_E(i) = R_E · cos(ϕ_i) · Δ        [m]   east spacing in row i
h_N    = R_E · Δ                   [m]   north spacing, constant
h      := R_E · Δ                  [m]   the nominal spacing all bounds are quoted against
                                                                             (4.3)
```

`h` is measured at the equator; rows away from it are narrower in east by `cos ϕ_i`, and
`h_E(i)` is the truth used in every geometric computation. All theorems below are stated with
`h`; on a domain reaching latitude `ϕ_max` they hold with `h ← h·cos ϕ_max` wherever a
*lower* bound on spacing is needed (`ℓ_min`, `Δ_min`) and with `h` wherever an *upper* bound
is needed (`r_max`, `n_buckets`). Failing to make that substitution is the classic
mid-latitude bucket-queue bug: at 45 °N the east spacing is `0.707 h`, so a bucket width
computed from `h` exceeds the true minimum increment and `Prop 4.9` fails.

**Longitude wrap.** The domain closes the circle iff `|n_λ·Δ − 2π| < 10⁻⁹`. If it does, `j`
arithmetic is modulo `n_λ` and stencil offsets are capped at `|dj| ≤ ⌊(n_λ−1)/2⌋` so that no
node is offered twice from both sides. If it does not, out-of-range `j` is *not water*: the
domain edge is a coast as far as the solver is concerned. This single convention removes
every bounds check from the update loop except one.

**Reference configuration** used for all byte counts below — the end-to-end voyage of
`CORE-THEOREM §8.2` (8.0 °N 77.0 °E → 12.6 °N 43.5 °E):

| Quantity | Value | Derivation |
|---|---|---|
| `Δ` | 0.25° = 4.363 323 129 985 82 × 10⁻³ rad | given |
| `h` | **27 798.73 m** | `6 371 000 × 4.363 323 13e−3` |
| `n_ϕ × n_λ` | **153 × 193** | 38° × 48° span at 0.25°, inclusive |
| `N` | **29 529** | `153 × 193`, matches `CORE-THEOREM §8.2` |
| `ρ_c` | 8 | D2/D3 default |
| `H = ρ_c·h` | **222 389.85 m** | `8 × 27 798.73` |
| coarse `N_H` | **500** | `⌈153/8⌉ × ⌈193/8⌉ = 20 × 25` |
| `n_θ` | 72 | D2 |

### 4.2.2 Memory layout — every array, exactly

Abstract types only (D7). "f64" is IEEE-754 binary64, "f32" binary32, "i32" two's-complement
32-bit, "u8" one byte. Every array is a **flat, contiguous** block of length `N` indexed by
(4.2) unless a different shape is given. Byte counts are for the reference configuration.

| # | Name | Type | Shape | Index formula | Bytes (ref) | Purpose |
|---|---|---|---|---|---|---|
| A1 | `T` | f64 | `N` | `n` | 236 232 | arrival time in the co-moving frame, `+∞` = unreached |
| A2 | `parent` | i32 | `N` | `n` | 118 116 | backpointer node, `−1` at the source |
| A3 | `parent_zeta` | f32 | `N` | `n` | 118 116 | the minimising `ζ` on the parent edge; needed for sub-cell route recovery |
| A4 | `parent_edge` | u8 | `N` | `n` | 29 529 | which of the ≤ 255 stencil offsets carried the parent edge |
| A5 | `status` | u8 | `N` | `n` | 29 529 | 0 = far, 1 = considered, 2 = accepted |
| A6 | `water` | u8 | `N` | `n` | 29 529 | navigable mask; land, TSS/ECA bans and `d_b < T_d + UKC` all collapse to 0 |
| A7 | `bucket_of` | i32 | `N` | `n` | 118 116 | which bucket a live key sits in, for `decrease_key` |
| A8 | `ups` | f32 | `N` | `n` | 118 116 | `Υ_loc` per node, from `Def 2.9` |
| A9 | `radius` | f32 | `N` | `n` | 118 116 | the stencil radius `r(x)` fixed point of `Alg 4.2` |
| A10 | `lat` | f64 | `n_ϕ` | `i` | 1 224 | row latitude, radians |
| A11 | `hE` | f64 | `n_ϕ` | `i` | 1 224 | `R_E cos ϕ_i Δ`, the row east spacing |
| A12 | `lon` | f64 | `n_λ` | `j` | 1 544 | column longitude, radians |
| A13 | `support` | f64 | `N × n_θ` | `n·n_θ + m` | **17 008 704** | tabulated `𝔥(y, p_m)` (D2, `Prop 2.7`) |
| A14 | `labels` | f64 | `N × Λ × k` | `(n·Λ + l)·k + o` | `N·Λ·k·8` | Pareto labels, §4.10; 0 when `k = 1` |
| A15 | `label_parent` | i32 | `N × Λ` | `n·Λ + l` | `N·Λ·4` | label backpointer (node, label) packed as `p·Λ + l` |
| A16 | `T_low` | f64 | `N_H` | `I·n_λ^H + J` | 4 000 | coarse optimistic value, §4.11 |
| A17 | `F_low` | f64 | `N_H` | `I·n_λ^H + J` | 4 000 | dilated-cell metric minimum, Eq (4.19) |

**Totals for the reference configuration, `k = 1` (time-only, the co-moving solve):**

```
solver state  A1–A9      =    906 000 B  =   884.8 KiB
row/col caches A10–A12   =      3 992 B
coarse A16–A17           =      8 000 B
support table A13        = 17 008 704 B  =    16.22 MiB          ← dominates
                          ─────────────
total                    = 17 926 696 B  =    17.10 MiB          (4.4)
```

With `k = 3` and a measured `Λ = 10–40` (E7): `A14 + A15` adds
`29 529 × Λ × (3·8 + 4)` bytes = `826 812·Λ` B, i.e. **7.9 MiB at `Λ = 10`** and
**31.6 MiB at `Λ = 40`**. The label store, not the metric table, is what bounds a
multi-objective solve.

### 4.2.3 The metric table at 0.25° — and what the reduction saves

The support table A13 is the single largest allocation, and it is where `Thm C.1` pays a
second time. Per D2 the table is `𝔥(y, t, p_m)` on `n_θ = 72` directions **per cell and per
forecast slice**. In the co-moving frame there are **no slices**: `𝒱_w` depends on `y` only
(`Thm C.1b`), so the time axis of the table collapses to length 1.

```
size_stationary  =  N · n_θ · 8                                              (4.5)
                 =  29 529 · 72 · 8  =  17 008 704 B  =  16.22 MiB

size_ground(n_t) =  n_t · size_stationary
```

For the reference voyage (139.9963 h arrival, 3-hourly forecast slices, `n_t = 48`):

```
size_ground(48) = 48 · 17 008 704 = 816 417 792 B = 778.6 MiB                (4.6)
```

**A 48× reduction in the dominant allocation, exactly.** At 0.125° (`N = 118 116`, four
times the nodes) the stationary table is 64.9 MiB and the ground-frame table is 3.04 GiB —
i.e. the ground-frame formulation stops fitting in cache-friendly memory at the resolution
the accuracy study of `CORE-THEOREM §4` says you want, and the co-moving one does not.

Two permitted economies, both normative options rather than defaults:

- **f32 support table.** Halves A13 to 8.11 MiB. `𝔥` is used inside a binary search whose
  outcome is a *direction index*, and the golden vectors of `handbook/01` are quoted to 12
  significant figures on `F`, not on `𝔥`. Measured effect on the final arrival time: **not
  measured. Do not claim it is free.** If used, re-run G4 and report the arrival error.
- **No table at all.** Evaluate `sigma()` directly, `O(30)` metric evaluations per inner
  minimisation instead of `O(log 72) = 7` table probes (D2). Trades ~16 MiB for a measured
  constant factor that this file does not have a number for — flag it as unmeasured.

### 4.2.4 Edge and stencil indexing

Stencil offsets are stored per row, not per node, because the great-circle distance from
`(ϕ_i, λ)` to `(ϕ_i + dΦ, λ + dΛ)` is independent of `λ`:

```
TEMPLATE(i, r)  =  [ (di, dj) : dist( (ϕ_i,0), (ϕ_{i+di}, dj·Δ) ) ≤ r·(1 + 10⁻⁹) ]   (4.7)
```

The `1 + 10⁻⁹` is not slop: the natural radii are integer multiples of the spacing, which
puts the cardinal neighbour *exactly* on the boundary, and whether `asin` rounds it above or
below then decides whether a row's 4-neighbour stencil has four members or two — differently
in different rows. `10⁻⁹` relative is sub-millimetre at `h = 27.8 km`, far below any
geometric meaning, and makes the boundary case land inside, always.

Each template entry carries a precomputed triple `(dist, u_E, u_N)` — segment length in
metres and the unit direction over ground — so the update loop performs no trigonometry.
Template storage per row is `|TEMPLATE| × (4 + 4 + 8 + 8 + 8)` B for `(di, dj, dist, u_E, u_N)`
= 32 B per offset. At `Υ = 1.53` the radius is `r = 60.0 km ≈ 2.16 h` (§4.6.2) and
`|TEMPLATE| ≈ π r²/h² ≈ 14.6` → 15 offsets → **480 B per row, 73 KiB for all 153 rows**.
Cache the templates keyed by `(i, round(r, 1 mm))` and evict wholesale above a fixed count
(8 192 entries is ample); an adaptive radius varies `r` continuously and would otherwise grow
the cache without bound.

**The one indexing trap that is measured, not hypothetical.** If the per-row geometry cache
is built by evaluating offsets from column `j = 0`, every westward offset `dj < 0` wraps to
the far side of the domain. Measured symptom: a leg of **4 020 km instead of 57.9 km**, with
a bearing **142° wrong**, on a grid where the correct answer is one cell. Build the cache
from a reference column `j_ref ≥ max|dj|` instead. (`src/kairos/comoving.py`, `JREF = 2`.)

---

## 4.3 What the solver is allowed to call

Per CONTRACT §4 the solver touches exactly five primitives. §4 adds no sixth. For the
co-moving solve two of them are specialised, and that specialisation is the whole
implementation of `Thm C.1`:

```
sample_env(y, t)      →  sample_env₀(y)          -- t ignored (Thm C.1b)
sigma(y, t, u, q)     →  sigma_w(y, u, q)        -- built on c_eff = c₀ − w   (C.6)
support(y, t, p)      →  support_w(y, p)
attainable, rates                                -- unchanged
```

> **Implementation note, and the reason the reduction is cheap.** `𝒱_w(y) = 𝒱₀(y) ⊖ w` is
> obtained by **subtracting `w` from the drift vector** and changing nothing else, because
> every achievable ground velocity is `V·n(θ) + c` and shifting `c` by `−w` shifts the whole
> set by `−w`. Therefore the reduction requires **no new metric code**: it wraps the
> environment field and lets the existing metric run unchanged, on a field that is now
> stationary. The Randers closed form, the conjugate branch of `handbook/01 §G3`, the `λ > 0`
> guard of golden vector T7 and the excluded-direction test of E1 all carry over verbatim
> with `c ← c₀ − w` (`CORE-THEOREM §6`, Eq (C.6)).

---

## 4.4 STEP 1 — choosing `w` by minimising the residual causality constant

### 4.4.1 What is being minimised, and why it is not the storm track

The objective is `Eq (C.10)`:

```
w*  =  argmin_w  P₉₉ over the domain of  L_t^w(y) ,
L_t^w(y) := max_{|u|=1} |∂F_w/∂t| (y, ·, u)                                  (4.8)
```

where `F_w` is the metric built on the field sampled **at points fixed in the `w`-frame**,
i.e. at ground position `y + w·t` at time `t`. Under A1 the field is constant along such a
trajectory and `L_t^w ≡ 0` identically; the measured value in `CORE-THEOREM` Test 8.10
Regime A is `0.0` to the last bit, which is the sharpest confirmation available that the
mechanism is exact and not merely small.

> **`w*` is not the meteorological advection velocity and must never be reported as one.**
> Once A1 is violated the two are different problems. Measured, Test 8.10 Regimes B and C:
> the optimised `w` was `(−0.56, −1.38) m/s` against a true system translation of
> `(+2.0, +0.5) m/s`, while still cutting `r·L_t` from `1.31` (unlicensed) to `0.26`
> (licensed). The algorithm wants the frame in which the *scheme* is best behaved, not the
> frame in which the *storm* is at rest, and where those disagree the algorithm is right and
> the meteorology is irrelevant.

### 4.4.2 Phase correlation was tried and failed — do not re-implement it

The natural first choice is image registration between consecutive forecast frames: phase
correlation of `‖E(·, t_k)‖` against `‖E(·, t_{k+1})‖`, peak of the cross-power spectrum,
divide by the frame interval. It is fast, standard, and **wrong for this purpose**.

**Measured (`CORE-THEOREM §7`, "Choosing `w`: what failed and what replaced it"):** against a
constructed field whose true dominant advection was `w = (2.0, 0.5) m/s`, phase correlation
returned

```
w_phase  =  (−0.74, 0.00) m/s                                                (4.9)
```

— wrong in sign on the dominant component and identically zero on the other. The failure
mode is structural, not a tuning problem: phase correlation locks onto whichever feature
carries the most **gradient energy**, which need not be the feature governing the causality
constant. A large, smooth, slowly-moving swell field can dominate the spectrum while a small,
sharp, fast-moving cyclone dominates `L_t`.

This is recorded so that no implementer re-derives it. If your port produces a `w` that looks
physically satisfying, check that it is not because you quietly reintroduced registration.

### 4.4.3 Why `P₉₉` and not `max`

The causality condition (E4.1) is a worst-case condition, so `max` is the object of interest
in principle. In practice `max` over a discretised domain is a **single-cell statistic** and
therefore an estimator with no stability: one cell at a land boundary, where a ban switches
and `F` jumps to `+∞` in finite time (`03-causality.md §3.8.4`), fixes `w*` for the entire
domain. `P₉₉` over `N = 29 529` cells discards the worst 295 cells, which is enough to
survive the coastal boundary layer of the mask and few enough to retain any genuinely
extended severe region.

The cost of this choice is explicit and must be reported: `P₉₉` licenses the sweep on 99 % of
cells, not all of them. The remaining 1 % are exactly the cells where the wait relaxation
(E5.1) or a heap fallback (E2) must be available. **A run that reports only `P₉₉` and not the
count of cells above the licence threshold is under-reporting.** Instrument both.

The measured spread justifying the choice, from Test 8.10 Regime C, co-moving frame:
`max = 5.07e−6`, `p99 = 4.67e−6`, `median = 1.63e−6` — the max exceeds the p99 by 8.6 %, and
in the ground frame of the same regime by 0.4 %. The two statistics are close on this field;
they are not close on fields with an active ban boundary, and the argument above is why the
percentile is the normative default rather than why it won on this test.

### 4.4.4 The search

> **Alg 4.4 — choose `w`.**
>
> **Input.** Forecast field `E`; `sigma()`; a spatial sample `Y` of `n_s` points; a temporal
> sample `t_1 … t_{n_t}` inside the forecast horizon; a direction sample `u_1 … u_{n_u}`
> spanning `S¹`; span `s₀`, grid size `n` (odd), rounds `n_r`; central-difference half-step
> `δt`.
> **Output.** `w*`, the ground-frame constant `L_t^0`, the co-moving constant `L_t^{w*}`.
> **Invariant.** The returned `L_t^{w*}` is `≤ L_t^0` (the candidate set contains `w = 0` at
> round 1, and the incumbent is never replaced by a worse value).
> **Complexity.** `n_r · n² · n_s · n_t · 2 · n_u` evaluations of `sigma()`.
>
> ```
>  1  best ← RESID(0);  w ← (0,0);  s ← s₀
>  2  for round = 1 … n_r:
>  3      for a = 0 … n−1:
>  4          for b = 0 … n−1:
>  5              w' ← ( w_x − s + 2s·a/(n−1) ,  w_y − s + 2s·b/(n−1) )
>  6              v  ← RESID(w')
>  7              if v < best:  best ← v ;  w_next ← w'
>  8      w ← w_next
>  9      s ← 2s/(n−1)                       -- next span = current sample spacing
> 10  return w, RESID(0), best
>
> RESID(w):
> 11  for each y ∈ Y:
> 12      worst ← 0
> 13      for each t ∈ {t_1 … t_{n_t}}:
> 14          for σ ∈ {−1, +1}:
> 15              t' ← t + σ·δt
> 16              x  ← y ⊕ w·t'                 -- ground position of the w-frame point
> 17              e  ← sample_env(x, t')
> 18              F_σ ← max over u_1…u_{n_u} of  1/sigma(e, u)   [skip sigma ≤ 10⁻⁶]
> 19          worst ← max( worst, |F_{+} − F_{−}| / (2δt) )
> 20      record worst
> 21  return the n_s-sample 99th percentile of the recorded values
> ```
>
> **Line 9 is the coarse-to-fine contraction.** Setting the next span equal to the current
> sample spacing `2s/(n−1)` guarantees the refined bracket contains the true minimiser of the
> sampled objective *given* that the objective is unimodal on the bracket; it is not a proof
> of global optimality, and none is claimed. With `s₀ = 4 m/s` and `n = 9`, the sample
> spacings are `1.000`, `0.250`, `0.0625 m/s` over three rounds — a final resolution of
> **6.25 cm/s**, which is four orders below any advection velocity of interest and two below
> the forecast's own wind uncertainty. `n = 9`, `n_r = 3` is the normative default
> (`CORE-THEOREM §7`: "three rounds of 9×9 is ample").
>
> **`s₀ = 4 m/s` is a physical bound, not a tuned constant.** Synoptic and tropical systems
> translate at 5–8 m/s (`CORE-THEOREM §1`); A2 requires `|w| < σ_min^w`, and with `V_s ≈ 7 m/s`
> and realistic drift the admissible `w` is inside `|w| ≲ 5 m/s` anyway. A `w*` landing on the
> boundary of the initial box is a diagnostic that A2 is in danger, and must be reported, not
> silently accepted.

**Cost, and the one number here that is inferred rather than measured.** `CORE-THEOREM §8.2`
measures the whole of Alg 4.4 at **+0.05 s** on the reference voyage. With `n_r n² = 243`
candidates, that implies roughly `5×10⁵` `sigma()` evaluations at vectorised throughput,
consistent with `n_s = 64`, `n_t = 2`, `n_u = 8` (`64·2·2·8 = 2 048` per candidate,
`497 664` total). **The 0.05 s is measured; the sample budget that reconciles with it is
inferred and is flagged as such.** Any port should re-measure rather than assume these
sample sizes.

### 4.4.5 What breaks without each hypothesis

| Dropped | Consequence |
|---|---|
| A1 (rigid translation) | `L_t^{w*} > 0`; the solve is no longer exactly licensed and §4.9 (the residual corrector) becomes mandatory rather than optional. The reduction degrades to a **preconditioner**: measured `r·L_t` 1.31 → 0.26 in Test 8.10 B/C. |
| A2 (`|w| < σ_min^w`) | `g(t) = T_w(x_B − wt) − t` need not tend to `−∞`; `Thm C.1(c)` has no root and Alg 4.6 must return "no interception" — which is the honest answer: *this system cannot be outrun*. Never substitute a large `t_max` for a failed A2. |
| `P₉₉` → `max` | The choice of `w` becomes a single-cell statistic and is destabilised by ban boundaries (§4.4.3). |
| central difference in `t` | A one-sided difference biases `L_t` by `O(δt·∂²F/∂t²)` and, because the search compares candidates, a *systematic* bias does not cancel between them unless the same stencil is used for all — so the stencil must be identical across candidates. |
| identical sample sets across candidates | The objective becomes noisy in `w` and the coarse-to-fine bracket contracts around sampling noise. `Y`, `{t}`, `{u}` are fixed once, before line 1. |

**A known non-identifiability, reported.** In Test 8.10 Regime A the test field was
`x`-invariant (an eastward jet), so only `w_y` was identifiable; the optimiser recovered
`w_y = +0.500` exactly against a true `+0.5` and left `w_x` unconstrained. The *exactness* of
the reduction is established by that test; the *identifiability* of `w` is not. On a field
with a symmetry direction, `w*` is determined only modulo that direction, and the search will
return an arbitrary point of the flat valley. Detect it by re-running Alg 4.4 from a
perturbed `w` seed and reporting the spread.

---

## 4.5 STEP 2 — the co-moving field, and R1

### 4.5.1 Building the field

```
c_eff(y)  :=  c₀(y) − w                                                     (4.10)
𝒱_w(y)    =  D( c_eff(y), V_max(y) )      when the indicatrix is a disc      (C.6)
```

Everything downstream reads `c_eff`. Two checks are performed **once per node**, before the
sweep, and both are cheap:

```
A2 check  :  |w|  <  σ_min^w  :=  inf_{y,|u|=1} σ_w(y,u)                     (4.11)
E1 check  :  |c_eff(y)|  <  V_max(y)                                         (4.12)
```

Where (4.12) fails, E1 applies and **the correct answer is not an exception**: the reachable
directions form a cone about `c_eff` of half-angle

```
α_reach(y) = arcsin( V_max(y) / |c_eff(y)| )                                 (4.13)
```

and `F_w(y,u) = +∞` for every `u` outside it. Equality `|c_eff| = V_max` is treated as
excluded for strict safety. This is a two-line test inside the direction loop, not a special
code path. Do **not** code `if (|c| ≥ σ_max)` — that branch never fires (E1), and an
implementation that relies on it silently runs the fast path in exactly the cells where the
theory forbids it.

Golden vectors T7 and T8 of `handbook/01 §G2` are the two cells that must be reachable in the
test suite: T7 (`λ = V_s² − |c|² < 0`) returns `F = −1.25`, a plausible-looking *negative
cost*, if the `λ > 0` guard is missing; T8 (`|c_⊥| ≥ V_s`) is a `sqrt` of a negative whose
correct handling is `σ = 0, F = +∞, direction excluded`.

### 4.5.2 R1 — the co-moving grid must be dilated. NORMATIVE.

> **R1 (mandatory, `CORE-THEOREM §8.1`).** The co-moving grid must extend beyond the ground
> domain by `|w|·t_max` in the direction **opposite to each component of `w`**:
> ```
> dilate_E = |w_E| · t_max        (extend west for w_E > 0)
> dilate_N = |w_N| · t_max        (extend south for w_N > 0)                 (4.14)
> ```
> where `t_max` is the largest arrival time the solve may need to represent.

**Why.** The solve lives in `y = x − w t`. Reaching ground point `x_B` at time `t` requires
the node `y = x_B − w t` to be *inside the grid*. Over a voyage of duration `t_max` the
co-moving domain is displaced from the ground domain by `w·t_max`.

**Why it is stated as a requirement and not a remark: it fails silently.** The sweep
converges, the route looks plausible, and the landfall is simply wrong.

**Measured (`CORE-THEOREM §8.1`, `handbook/02 §S8b`).** A 140 h voyage with `w = (1,1) m/s`:
the required node lay **4.5° west of the grid edge**, giving a **104.5 km landfall miss that
a full-grid scan could not reduce**, because no node in the domain mapped anywhere near the
target at all. Extending the domain by `|w|·t_max ≈ 500 km` per component brought the miss to
**11.2 km**, under half a grid diagonal.

**Discriminating test** (from the playbook, because the symptom is shared with two other
bugs): scan every node for `min ‖(y + w·T[y]) − x_B‖`. If the minimum over the **whole grid**
is large, the domain is too small (R1). If the minimum is small but the node your code
*selected* is worse, it is R2 (§4.7). If the landfall is exactly `2|w|t*` away, you have
swapped the sign convention: `ground_position` is `x = y + w t`, `comoving_position` is
`y = x − w t`.

**Cost of compliance, for the reference voyage.** `w = (3.0, 1.0) m/s`, `t_max = 5.04×10⁵ s`
(140 h): `dilate_E = 1 512 km`, `dilate_N = 504 km`. At 10 °N that is `13.79°` of longitude
and `4.53°` of latitude, i.e. **+56 columns and +19 rows**, taking the grid from `153 × 193 =
29 529` to `172 × 249 = 42 828` nodes — **+45.0 % nodes, +45.0 % on every array of §4.2.2**,
so the reference footprint (4.4) rises from 17.10 MiB to 24.8 MiB. That is the true price of
the reduction and it must be quoted alongside the 48× saving of (4.6); the net is still a
large win, but it is `48× / 1.45`, not `48×`.

**Choosing `t_max`.** Circular at first sight — `t_max` bounds the answer the solve produces.
Resolve it with the A2-consistent a priori bound, which is computable before the solve:

```
t_max  ≤  F_max^w · |x_B − x_A| / ( 1 − |w|/σ_min^w )                        (4.15)
```

*Proof.* From the proof of `Thm C.1(c)`:
`g(t) ≤ F_max^w|x_B − x_A| + (F_max^w|w| − 1)t`, and `g(t*) = 0` forces
`t* ≤ F_max^w|x_B−x_A| / (1 − F_max^w|w|)`; substitute `F_max^w = 1/σ_min^w`. ∎
The bound blows up as `|w| → σ_min^w`, which is A2 failing, and it is *tight* in the limit of
a straight-line voyage in a uniform field. Multiply by a safety factor `1.25` and round up to
a whole number of cells. Where (4.15) exceeds the forecast horizon, the horizon governs and
the run log must say so.

---

## 4.6 STEP 3 — the stationary sweep

### 4.6.1 The update, and the licence

> **Alg 4.1 — semi-Lagrangian ordered-upwind update.**
>
> **Input.** Node `x` (not accepted); the accepted front `AF`; the stencil radius `r(x)`;
> the metric `F_w` (stationary).
> **Output.** A candidate value `T̂(x)`, the minimising edge `e*` and parameter `ζ*`.
> **Invariant.** `T̂(x) ≥ min_{j ∈ AF} T(x_j) + Δ_min` with `Δ_min` of Eq (4.17).
> **Complexity.** `O( |NF(x)| · C_ζ )` where `|NF(x)| = Θ(r(x)/h)` front edges (assumption
> (A6) of `07-complexity.md`) and `C_ζ` is the inner-minimisation cost of §4.6.3.
>
> ```
>  1  T̂ ← +∞ ;  e* ← ⊥ ;  ζ* ← ⊥
>  2  NF(x) ← { edges (x_j, x_k) of AF : x_j, x_k accepted, adjacent,
>  3             and dist(x, [x_k, x_j]) ≤ r(x) }
>  4  for each e = (x_j, x_k) ∈ NF(x):
>  5      define  ξ_e(ζ)  = ζ·x_j + (1−ζ)·x_k                       ζ ∈ [0,1]
>  6      define  W̃_e(ζ)  = ζ·T(x_j) + (1−ζ)·T(x_k)
>  7      define  ℓ_e(ζ)  = |x − ξ_e(ζ)|
>  8      define  u_e(ζ)  = (x − ξ_e(ζ)) / ℓ_e(ζ)
>  9      Z_e ← { ζ ∈ [0,1] : ℓ_e(ζ) ≥ ℓ_min }               -- E3 exclusion, Eq (4.16)
> 10      if Z_e = ∅: continue
> 11      (ζ_e, G_e) ← MINIMISE over ζ ∈ Z_e of
> 12                      G_e(ζ) = W̃_e(ζ) + ℓ_e(ζ) · F_w( x, u_e(ζ) )        (4.16)
> 13      if G_e < T̂:  T̂ ← G_e ;  e* ← e ;  ζ* ← ζ_e
> 14  return (T̂, e*, ζ*)
> ```
>
> **`Eq (4.16)` is the equation `07-complexity.md §7.2.1` restates as `(7.2)` and
> `03-causality.md §3.6` calls the explicit update.** In the ground frame it carries a third
> argument, the **departure** time `W̃_e(ζ)`, at which `F` is evaluated. In the co-moving
> frame that argument is absent, because `F_w` has no time argument at all.

> ### The payoff: no causality check
>
> **`Alg 4.1` performs no causality test, and none is required.** By `Thm C.1(b)` the
> co-moving problem is autonomous, so `L_t ≡ 0` and the causality condition (E4.1),
> `r(x)·L_t ≤ 1`, holds **vacuously** — not approximately, identically. Measured
> (`CORE-THEOREM` Test 8.10 Regime A): `L_t` in the co-moving frame is `0.0` at max, p99 and
> median, to the last bit.
>
> Concretely, three things vanish from the implementation of `Alg 4.1` relative to a
> ground-frame ordered-upwind solver:
> 1. the per-cell evaluation of `L_t` and the guard `r(x)·L_t ≤ 1 − δ_safe`;
> 2. the wait relaxation `F̃_ℓ` (E5.1) and its horizon-truncation bookkeeping;
> 3. every temporal interpolation inside the update — and with it the temporal
>    discretisation error. Measured (`CORE-THEOREM §4`): the ground-frame solve on the same
>    grid required `V_req = 7.006721 m/s` against a ship capable of `7.000000`, an excess of
>    `6.7×10⁻³ m/s`; the co-moving solve's excess was `2.8×10⁻¹⁴ m/s`. **The reduction is not
>    only faster and better-licensed, it is more accurate on the same grid.**
>
> Where A1 is violated the residual `R` is handled in §4.9 and *there* the guard reappears,
> applied to `L_t^R` rather than `L_t`.

### 4.6.2 The `ℓ_min` exclusion — E3, and why the naive bound is false

`CONTRACT D3` asserts that every update advances the value by at least `Δ_min = h·F_min`.
**This is false**, and E3 corrects it. In `Alg 4.1` the segment runs from an *arbitrary
interior point* `ξ_e(ζ)` of a front edge to `x`, so its length ranges over an interval that
is open at the bottom; an open interval has no positive infimum, and `ℓ·F ≥ h·F_min` simply
does not hold. Dial's discipline requires the bucket width to be **at most** the minimum
increment. With an arbitrarily small increment the queue can finalise a node whose value is
later lowered, destroying the label-setting invariant — the failure mode is
`handbook/02 §S1` cause 3, "bucket queue receiving a key below its current minimum".

The repair is to enforce the bound **by construction**, and then it is a theorem:

> **Lemma E3.1 (restated with proof; source: `ERRATA.md §E3`).** On a grid of spacing `h`
> whose accepted front is 8-connected, the perpendicular distance from a node `x` to any
> accepted-front edge is at least `h/√2`.
>
> **Proof.** Place `x` at the origin. Grid nodes nearest `x` lie at distance `h`, at
> `(±h, 0)` and `(0, ±h)`. A front edge is a segment between two *adjacent* accepted nodes.
> Enumerate the adjacent pairs among the nodes at distance `h`:
> - Diagonal pairs, e.g. `(h,0)–(0,h)`. This segment lies on the line `x + y = h`, whose
>   distance from the origin is `h/√2 ≈ 0.7071 h`.
> - Pairs sharing an axis, e.g. `(h,0)–(h,h)`. This segment lies on the line `x = h`, whose
>   distance from the origin is `h`.
> No other pair among the four nearest nodes is adjacent: `(h,0)` and `(−h,0)` are two cells
> apart. Any edge with at least one endpoint at distance `> h` from `x` has every point at
> distance `≥` the distance of the nearer endpoint, and the perpendicular foot, if it lies
> inside the segment, is at distance at least that of the closest point of the line through
> the two endpoints — which for any grid-adjacent pair not among the above is `≥ h`, since
> such a pair lies in the closed half-plane at distance `≥ h` from the origin in at least one
> coordinate. Hence the infimum over all admissible front geometries is `h/√2`, and it is
> **attained** by the short diagonal. ∎
>
> *Remark (why "attained" matters).* Because the infimum is attained, `h/√2` is the exact
> constant, not a convenient underestimate. Any implementation choosing a larger `c_geo`
> makes the queue non-monotone; any smaller value merely wastes buckets.

Normatively, therefore:

```
c_geo := 1/√2 = 0.707 106 781 186 547 5…
ℓ_min := c_geo · h                                                          (4.16)
Δ_min := ℓ_min · F_min = c_geo · h · F_min                                  (4.17)
```

and **`Alg 4.1` line 9 must skip every front point `ξ` with `|x − ξ| < ℓ_min`.** That
exclusion is what turns (4.17) from an assumption into a theorem. It costs nothing:
excluded points are interior to the stencil and their characteristics are represented by
other front edges within the same `NF(x)`, so `Prop 4.7`'s locality conclusion is unaffected.

On the mid-latitude grid, use the row's *smallest* spacing in (4.16)–(4.17):
`ℓ_min = c_geo · min(h_E(i), h_N)` — see §4.2.1.

### 4.6.3 The inner minimisation over `ζ`, and its convexity

This is the step that separates KAIROS from a fixed-neighbour graph solver, and the one whose
omission produces the most dangerous failure in the whole system: **the error stops decreasing
under grid refinement while the routes still look right** (`handbook/02 §S3`). A fixed
`m`-neighbour stencil quantises heading and carries a consistency error that does **not**
vanish as `h → 0` — measured in `CORE-THEOREM §4` as a **0.15–0.98 % floor that did not
converge** over `h = 24, 16, 12, 8, 6, 4, 3 km`. That measurement was obtained accidentally,
as a two-frame comparison, and it is the strongest available evidence for the continuum `ζ`.

> **Prop 4.6 (convexity of the inner problem in the co-moving frame).** Let `𝒱_w(y)` be
> convex (guaranteed by D4, which solves with `conv 𝒱`) and let the metric be stationary
> (`Thm C.1b`). Then for every front edge `e`, the map
> `ζ ↦ G_e(ζ) = W̃_e(ζ) + ℓ_e(ζ)·F_w(x, u_e(ζ))` of Eq (4.16) is **convex** on `Z_e`, hence
> unimodal, hence golden-section search converges to its global minimiser.
>
> **Proof.** `F_w(x, ·)` is the Minkowski gauge of the convex set `𝒱_w(x)` containing the
> origin in its interior (E9 claim 2, equivalent to `|c_eff| < V_max`). A gauge of a convex
> set is **sublinear**: positively 1-homogeneous and subadditive, hence convex as a function
> of its *vector* argument. By 1-homogeneity,
> ```
> ℓ_e(ζ)·F_w(x, u_e(ζ)) = F_w( x, ℓ_e(ζ)·u_e(ζ) ) = F_w( x, x − ξ_e(ζ) ).
> ```
> The map `ζ ↦ x − ξ_e(ζ) = x − ζ x_j − (1−ζ)x_k` is **affine** in `ζ`. A convex function
> composed with an affine map is convex. `W̃_e(ζ)` is affine, and affine + convex is convex.
> `Z_e` is the intersection of `[0,1]` with the complement of an open disc about `x`, which is
> a union of at most two closed intervals; `G_e` is convex on each. ∎
>
> **Remarks.**
> - **What fails without stationarity.** In the ground frame `F` carries the departure time
>   `W̃_e(ζ)` as an argument, so `G_e(ζ) = W̃_e(ζ) + F(x, W̃_e(ζ), x − ξ_e(ζ))`, and the inner
>   argument is no longer affine-in-`ζ`-composed-with-a-convex-function. Convexity is lost;
>   only unimodality survives, and only under an extra hypothesis (`L_t` small enough that
>   the time-dependence cannot create a second local minimum). **This is a second, smaller
>   dividend of `Thm C.1`: it upgrades the inner minimisation from conditionally unimodal to
>   unconditionally convex.**
> - **What fails without convexity of `𝒱`.** The gauge is no longer sublinear, `G_e` may have
>   several local minima, and golden-section search returns an arbitrary one — a silent
>   suboptimality. D4 buys convexity by solving with `conv 𝒱`; the realisability gap that
>   opens is repaired by notch projection (`Alg 4.14`) and bounded by `Thm 2.11` in its
>   corrected **local** form (E6), never by the vacuous global bound.
> - **What fails when `Z_e` is disconnected.** Minimise on each component and take the better;
>   two golden-section runs, not one. Skipping this is a real bug: the excluded disc can cut
>   the middle out of an edge that straddles `x`.

**Two normative implementations of `MINIMISE`, in order of preference.**

**(i) Support-function fast path (D2, `Prop 2.7`).** For convex `𝒱_w` the gauge is recovered
exactly from the support function by duality. The minimiser of (4.16) satisfies a first-order
condition that locates it by **binary search over the `n_θ = 72` tabulated directions**, at
`O(log n_θ) = 7` table probes rather than `O(30)` metric evaluations. Use this wherever
`support` (A13) is materialised. The `n_θ = 72` tabulation is *not* a re-introduction of
heading quantisation: `07-complexity.md` Remark 6 bounds the induced relative error by
`(Δψ²/8)(Υ−1)/2 = 9.52×10⁻⁴·(Υ−1)/2`, which at `Υ = 1.53` is `2.5×10⁻⁴` — two orders below
the metrication floor the continuum `ζ` exists to remove.

**(ii) Golden-section search.** No table required. On a convex `G_e`, the bracket contracts by
`φ⁻¹ = 0.618 034` per evaluation. To reach a relative tolerance `tol` on `ζ`:

```
n_iter  =  ⌈ ln(tol) / ln(0.618 034) ⌉                                       (4.18)
```

At `tol = 10⁻⁴`: `n_iter = ⌈ −9.2103 / −0.481 212 ⌉ = ⌈19.14⌉ = 20` evaluations of `F_w`.
That is the `C_ζ` of `Alg 4.1`'s complexity line. Terminate additionally when the bracket is
narrower than `ℓ_min/(10·|x_j − x_k|)`, below which `ζ` no longer resolves a distinct
geometry.

**Mandatory instrumentation (`handbook/02 §S3`).** Log the distribution of the returned `ζ*`.
If it is bimodal at `{0, 1}`, the minimiser is not minimising and you have a fixed-neighbour
stencil wearing a continuum's clothes — the error will plateau under refinement and the
routes will still look fine.

### 4.6.4 Prop 4.7 — locality of the ordered-upwind stencil

> **Prop 4.7 (stencil locality).** Let `T` be the value function of the stationary co-moving
> problem, let the sweep accept nodes in non-decreasing order of value, and let `A` denote
> the **accepted region**: the union of closed grid cells all of whose corner nodes are
> accepted, with `AF := ∂A`. Assume (A1) of `07-complexity.md`, i.e.
> `0 < F_min ≤ F(y,u) ≤ F_max < ∞` for all `y` in the relevant neighbourhood and all unit
> `u`, and write `Υ_loc = F_max/F_min` for the local anisotropy. Let `x` be the node about to
> be accepted and let `γ` be an optimal path from the source to `x`, with `ξ` the **last**
> point at which `γ` meets `AF`. Then
> ```
> |x − ξ|  ≤  √2 · h · Υ_loc                                                 (4.19)
> ```
> where `Υ_loc` is taken over `B(x, √2 h Υ_loc)`. Consequently the update `Alg 4.1` may
> restrict `NF(x)` to front edges within radius `r(x) = √2 h Υ_loc` without changing `T̂(x)`.
>
> **Proof.**
>
> *Step 1 — every point of `γ` after `ξ` has value close to `T(x)`.* Let `p` be any point of
> `γ` strictly after `ξ`. By definition of `ξ`, `p ∉ A`. Hence the closed grid cell `C ∋ p`
> is not entirely accepted: it has a corner node `z` that is **not** accepted. Because the
> sweep accepts in non-decreasing order of value and `x` is the node being accepted now,
> every unaccepted node has value `≥ T(x)`; in particular `T(z) ≥ T(x)`.
>
> *Step 2 — `z` is close to `p` in value.* `T` is the minimum-time value function, so for any
> two points `a, b` it satisfies `T(b) ≤ T(a) + d_F(a,b)` where `d_F` is the Finsler distance,
> and `d_F(a,b) ≤ F_max·|a − b|` because the straight segment from `a` to `b` is admissible
> and costs at most `F_max` per unit length in every direction. `z` is a corner of the cell
> containing `p`, so `|p − z| ≤ √2 h` (the cell diagonal). Hence
> ```
> T(z)  ≤  T(p) + F_max·√2 h .
> ```
>
> *Step 3 — combine.* From Steps 1 and 2, `T(x) ≤ T(z) ≤ T(p) + √2 h F_max`, i.e.
> ```
> T(p)  ≥  T(x) − √2 h F_max        for every p ∈ γ after ξ.                 (∗)
> ```
> Applying (∗) at `p = ξ` (by continuity of `T` along `γ`, taking the limit from after `ξ`)
> gives `T(ξ) ≥ T(x) − √2 h F_max`.
>
> *Step 4 — a lower bound on the cost of the remaining arc.* The arc of `γ` from `ξ` to `x`
> is admissible and costs `T(x) − T(ξ)`; its cost is at least `F_min` times its Euclidean
> length, which is at least `|x − ξ|`. Hence
> ```
> F_min·|x − ξ|  ≤  T(x) − T(ξ)  ≤  √2 h F_max .
> ```
> Dividing by `F_min` gives (4.19). ∎
>
> **Remarks.**
> - **The constant.** Earlier drafts (and `07-complexity.md §7.2.1` note 2) write
>   `r_max = h·max Υ_loc`, omitting the `√2`. The proof above shows the cell **diagonal**,
>   not the spacing, is the correct length in Step 2, because the unaccepted corner witnessing
>   `p ∉ A` may be the far corner of the cell. This file therefore uses `√2 h Υ_loc`. The
>   change only *enlarges* the stencil, so every conclusion of `07-complexity.md` remains
>   valid under `Υ ← √2 Υ`; the cost is a `2×` increase in `|NF(x)|`. Reported in §4.16 as a
>   correction to a normative document.
> - **What fails without (A1).** If `F_max = ∞` on a cone (E1, strong drift), (4.19) is
>   vacuous and the stencil radius is unbounded. `Alg 4.2` therefore caps `r(x)` at `r_cap`
>   and `Alg 4.1` restricts the `ζ`-minimisation to directions with `F < ∞`. The honest
>   consequence, stated: in such cells the scheme is no longer provably local, the returned
>   value is an upper bound rather than the exact fixed point, and the cell must be counted
>   and reported.
> - **What fails without ordered acceptance.** Step 1 is the *only* place the sweep order is
>   used, and it is where the whole proposition lives. A Gauss–Seidel sweep in a fixed
>   geometric order does not satisfy "every unaccepted node has value `≥ T(x)`" and `Prop 4.7`
>   does not apply to it.
> - **What fails without front regularity (A6).** `Prop 4.7` bounds the stencil *radius*; the
>   number of edges inside it is `Θ(r/h)` only if the front has bounded 1-dimensional measure
>   in a ball. Near an archipelago (Maldives, Andamans, Indonesian straits) several front
>   sheets can occupy one stencil ball and `|NF(x)|` grows with the number of sheets. This is
>   observable: instrument `max_x |NF(x)|` and compare against `C_AF·r_max/h`.

### 4.6.5 Alg 4.2 — the stencil radius, as a fixed point

`Prop 4.7` is implicit: the radius depends on `Υ_loc` over a ball whose size is the radius.

> **Alg 4.2 — stencil radius by least fixed point.**
>
> **Input.** Node `x`; the array `ups` (A8); `h`; cap `r_cap`.
> **Output.** `r(x)`, the least fixed point of `Φ_x(r) := min( r_cap, √2·h·max_{B(x,r)} Υ_loc )`
> with `Φ_x` evaluated on grid nodes.
> **Invariant.** `r_m` is non-decreasing in `m` and bounded by `r_cap`.
> **Complexity.** `O(K·|B(x,r)|/h²)` with `K ≤ ⌈r_cap/h⌉` iterations (Step 3 below), and
> `O(1)` amortised if the running maximum is cached per shell.
>
> ```
>  1  r_0 ← √2·h                                   -- Υ_loc ≥ 1 always, so this is a lower bound
>  2  m ← 0
>  3  repeat
>  4      M ← max{ ups[n] : node n with dist(x, n) ≤ r_m }
>  5      r_{m+1} ← min( r_cap , √2·h·M )
>  6      m ← m + 1
>  7  until r_m = r_{m−1}
>  8  return r_m
> ```
>
> **Convergence (complete).**
> 1. *`Φ_x` is monotone.* If `r ≤ r'` then `B(x,r) ⊆ B(x,r')`, so the maximum over the larger
>    ball is `≥`, so `Φ_x(r) ≤ Φ_x(r')`.
> 2. *The iteration is non-decreasing.* `Υ_loc ≥ 1` by `Def 2.9` (`σ_max ≥ σ_min`), so
>    `Φ_x(r_0) ≥ min(r_cap, √2 h) = r_0` (assuming `r_cap ≥ √2 h`, which is required and
>    checked). Hence `r_1 ≥ r_0`; by monotonicity and induction, `r_{m+1} = Φ_x(r_m) ≥
>    Φ_x(r_{m−1}) = r_m`.
> 3. *It terminates in at most `⌈r_cap/h⌉ + 1` steps.* `Φ_x(r)` depends on `r` only through
>    the finite set of nodes in `B(x,r)`, and that set changes only when `r` crosses one of
>    the finitely many distinct node-distance values `≤ r_cap`. On a lattice of spacing `h`
>    those distances are separated by at least... they are not uniformly separated, so argue
>    instead by strict increase: at each iteration either `r_m = r_{m−1}` (terminate) or
>    `B(x, r_m) ⊋ B(x, r_{m−1})`, which strictly increases the node count. The node count is
>    bounded by `|B(x, r_cap)| = O((r_cap/h)²)`, so the iteration terminates in at most that
>    many steps. In practice it terminates in 2–3: each step multiplies the radius by roughly
>    the anisotropy ratio between successive shells, which on ocean fields is close to 1.
> 4. *The limit is the least fixed point.* `r_0 = √2h ≤ r*` for every fixed point `r*`
>    (since `r* = Φ_x(r*) ≥ min(r_cap, √2h) = r_0`). By monotonicity and induction
>    `r_m ≤ r*` for all `m`, so the limit — a fixed point by continuity of the iteration on
>    a finite set — is `≤` every fixed point, hence least. (This is the standard
>    least-fixed-point-from-below argument, Knaster–Tarski on the finite chain of achievable
>    radii.) ∎
>
> **`r_cap` is normative and must be reported.** Default `r_cap = 16 h`. It exists for the
> E1 cells where `Υ_loc = ∞`, and every node hitting the cap is a node where `Prop 4.7`'s
> guarantee has been traded for a bounded runtime. Count them.

**Reference numbers.** For the golden-vector field of `handbook/01 §G4` (`V_s = 7.2 m/s`,
uniform `|c| = 1.5 m/s`): `Υ = (7.2+1.5)/(7.2−1.5) = 8.7/5.7 = 1.526 315 789 5` — the exact
value the arrival-time ratio must reproduce. Then

```
r  =  √2 · 27 798.73 · 1.526 315 789 5  =  60 001.9 m  ≈  2.16 h              (4.20)
```

so `|NF(x)| ≈ 2π r/h ≈ 13.6` front edges and `|TEMPLATE| ≈ π r²/h² ≈ 14.6` support nodes,
consistent with the 15-offset, 480 B-per-row figure of §4.2.4.

### 4.6.6 Alg 4.3 — the label-setting driver

> **Alg 4.3 — the sweep.**
>
> **Input.** Grid; source node `s`; metric `F_w`; queue `Q` (§4.8).
> **Output.** `T` (A1), `parent` (A2), `parent_zeta` (A3), `parent_edge` (A4).
> **Invariants.**
> - **I1** every accepted node's value equals the exact fixed point `T_h` of the update
>   family (`03-causality.md Thm 3.C(b)`, whose hypotheses (U1)/(U2) hold here **because the
>   metric is stationary**, `Thm C.1b`);
> - **I2** the sequence of extracted keys is non-decreasing;
> - **I3** no node is ever reopened; exactly `N_water` extractions occur.
> **Complexity.** `O( N·(|NF|·C_ζ) )` update work plus `O(N)` queue work under `Prop 4.9`,
> or `O(N log N)` queue work under the heap fallback.
>
> ```
>  1  for every node n:  T[n] ← +∞ ;  parent[n] ← −1 ;  status[n] ← FAR
>  2  seed the source: see the seeding note below
>  3  Q.push(T[s], s) ;  status[s] ← CONSIDERED
>  4  while not Q.empty():
>  5      (key, x) ← Q.pop_min()
>  6      if status[x] = ACCEPTED:  continue          -- stale entry, lazy deletion
>  7      status[x] ← ACCEPTED
>  8      for each node y with dist(x,y) ≤ r(y), status[y] ≠ ACCEPTED, water[y]:
>  9          (T̂, e*, ζ*) ← Alg 4.1(y)                -- x has just joined AF
> 10          if T̂ < T[y] − τ_tie:
> 11              T[y] ← T̂ ; parent[y] ← e*.near_node ; parent_zeta[y] ← ζ*
> 12              parent_edge[y] ← e*.offset
> 13              Q.push(T̂, y) ;  status[y] ← CONSIDERED
> 14  return T, parent, parent_zeta, parent_edge
> ```
>
> **Line 6 (lazy deletion) versus `decrease_key`.** Both are permitted. Lazy deletion pushes
> a duplicate and discards stale pops; it costs `O(1)` per improvement and `≤ |NF|` duplicate
> entries per node. `decrease_key` via `bucket_of` (A7) keeps the queue at `≤ N` entries and
> is `O(1)` in the bucket queue. Use `decrease_key` when memory is tight; the invariants are
> identical.
>
> **Line 10, `τ_tie`.** A strict-improvement test with an absolute tolerance. `τ_tie = 10⁻⁹ s`
> is normative: it is 15 orders below a voyage time and above the round-off of a sum of
> `~10³` positive terms of magnitude `~10³ s`. Without it, two front edges that represent the
> same characteristic can trade a node back and forth on last-bit differences and the sweep
> re-pushes forever.
>
> **Seeding (line 2) is not optional.** Initialising only `T[s] = 0` produces an `O(h)`
> initialisation error concentrated at the source that then propagates globally, and a
> refinement study that looks "first-order with a floor" — a classic and easily misdiagnosed
> artefact (`07-complexity.md §7.2` Remark 3). Seed **exactly** on a disc of radius `2h`
> about `s` using the closed-form Randers metric (`Eq (2.1)`, `handbook/01 §G2`) where no ban
> is active, and an `n_θ`-direction integration where one is. For the co-moving solve the
> closed form applies with `c ← c_eff` (Eq (C.6)), so the seeding is exact wherever
> `|c_eff| < V_max`.

---

## 4.7 STEPS 4–5 — interception and route recovery

*(The number `Alg 4.7` is deliberately not used: `Prop 4.7` owns `4.7` per the CONTRACT and
two objects sharing a number is exactly the kind of ambiguity this spec exists to remove.)*

### 4.7.1 R2 — do not select the goal node by the root find. NORMATIVE.

`Thm C.1(c)` gives the interception condition

```
t*  =  min { t ≥ 0 : T_w(x_B − w t) ≤ t } ,   with  g(t*) = 0  and the
constraint ACTIVE at t*, so the optimum never loiters.                       (C.4)
```

In the **continuum** the right method is a bisection on `g(t) = T_w(x_B − wt) − t`: `g` is
continuous, `g(0) = T_w(x_B) > 0`, and under A2 `g → −∞`, so the first zero exists and is
`t*`.

> **R2 (mandatory, `CORE-THEOREM §8.1`).** On a **discretisation**, do *not* select the goal
> node by that root find.

**Why.** Sampling `T` at the nearest node makes `g` a **step function**. A bisection then
converges to a *discontinuity*, not a root, and `T` at the returned node can be far from
`t*`. Because the ground position is `y + w·T[y]`, that timing error is amplified by `|w|`:
with `|w| ≈ 3 m/s` and a half-cell timing error of `~2 000 s`, the landfall moves `~6 km` per
cell of snapping error.

**Measured:** a **104.5 km miss, unchanged by widening the neighbourhood search**, because
the offset is systematic rather than local (`handbook/02 §S8b`, `CORE-THEOREM §8.1`).

**The correct method** is to solve the interception condition **directly on the
discretisation**. Every node already carries its own arrival time, hence its own ground
landfall `y + w·T[y]`. Take the node minimising the ground miss.

> **Alg 4.6 — interception on the grid.**
>
> **Input.** `T` (A1); the grid; `w`; destination `x_B`.
> **Output.** goal node `n*`, miss distance `d*`, interception time `t* = T[n*]`.
> **Invariant.** `n*` minimises `‖(y_n + w·T[n]) − x_B‖` over all nodes with finite `T`.
> This is `Eq (C.4)` evaluated exactly on the discretisation, with **no interpolation and no
> root find**.
> **Complexity.** `O(N)`, one great-circle distance per node. On the reference grid,
> `29 529` haversines — microseconds, and negligible against the sweep.
>
> ```
>  1  n* ← −1 ;  d* ← +∞
>  2  for n = 0 … N−1:
>  3      τ ← T[n]
>  4      if τ is not finite: continue
>  5      (ϕ_y, λ_y) ← latlon(n)
>  6      (ϕ_x, λ_x) ← ground_position(ϕ_y, λ_y, τ)        -- x = y + w·τ,  Eq (C.5)
>  7      d ← haversine( (ϕ_x,λ_x) , x_B )
>  8      if d < d*:  d* ← d ;  n* ← n
>  9  if d* > d_accept:  report FAILURE (see below)
> 10  return n*, d*, T[n*]
> ```
>
> **Line 9, `d_accept`.** Normative default `d_accept = h·√2` (one grid diagonal). Measured
> on the reference voyage: `d* = 11.2 km` against a diagonal of `39.3 km` — comfortably
> inside. A `d*` above the diagonal is the R1 signature: the domain is undersized. **Never
> widen `d_accept` to make a run pass.**
>
> **The root find is retained for reporting only.** Bisect `g` on `[0, t_max]` to a tolerance
> of `1 s` and report the resulting `t*` alongside `T[n*]`; a disagreement between the two
> larger than one cell's transit is a diagnostic that the field is not well resolved near the
> target. In a genuine continuum implementation the root find would be the right method and
> R2 would not arise.

**A2 failure is reported, not worked around.** If no `t` in `[0, t_max]` satisfies
`g(t) ≤ 0`, the honest return is **"no interception"**: the weather system cannot be outrun.
Do not enlarge `t_max` until something is found — under a failed A2 the bracket expansion
never terminates for a reason that is physical, not numerical.

### 4.7.2 Route recovery

> **Alg 4.8 — recover the ground route.**
>
> **Input.** `parent`, `parent_zeta`, `parent_edge`, `T`; goal node `n*`; `w`.
> **Output.** the ground route as a sequence `(ϕ_k, λ_k, t_k)`, departure first.
> **Invariant (`Thm C.1(d)`, Eq (C.5)).** `x(s) = y(s) + w·τ(s)` where `τ` is the co-moving
> arrival-time parameterisation. Verified to **`9.77×10⁻¹⁴ m/s`** per-leg bijection residual
> (`CORE-THEOREM §4`).
> **Complexity.** `O(L)` in the number of legs.
>
> ```
>  1  chain ← [] ;  n ← n*
>  2  while n ≠ −1:  append n to chain ;  n ← parent[n]
>  3  reverse chain
>  4  out ← []
>  5  for each n in chain:
>  6      (ϕ_y, λ_y) ← latlon(n)
>  7      ζ ← parent_zeta[n]                          -- sub-cell refinement, see below
>  8      if ζ is defined and n is not the source:
>  9          (ϕ_y, λ_y) ← the point ξ on edge parent_edge[n] at parameter ζ
> 10      τ ← T[n]
> 11      (ϕ_x, λ_x) ← ground_position(ϕ_y, λ_y, τ)   -- x = y + w·τ
> 12      append (ϕ_x, λ_x, τ) to out
> 13  return out
> ```
>
> **Lines 7–9 matter.** The semi-Lagrangian update reaches `x` from an *interior point* of a
> front edge, not from a node. Backtracking node-to-node discards `ζ*` and re-imposes exactly
> the heading quantisation that `Alg 4.1` was built to avoid — the route will be correct in
> arrival time and visibly polygonal on a map, and `handbook/01 §G4`'s "zero intermediate
> turns in a uniform current" test will fail. Store `ζ*` (A3) at update time; it costs 4 B
> per node.
>
> **Sign convention, stated once.** `ground_position(y, τ) = y ⊕ w·τ`;
> `comoving_position(x, t) = x ⊖ w·t`. Swapping them puts the landfall `2|w|t*` away — twice
> the R1 dilation distance, which is a distinctive and recognisable signature
> (`handbook/02 §S8b` cause 3).

**End-to-end measured result of steps 1–5** (`CORE-THEOREM §8.2`), reproduced here because
it is the acceptance criterion for an implementation of this section: voyage
8.0 °N 77.0 °E → 12.6 °N 43.5 °E, 3 698 km great circle, `V_s = 7.2 m/s`, cyclone translating
at `(3.0, 1.0) m/s`, 0.25° grid, 29 529 nodes.

| | arrival | wall clock | landfall miss |
|---|---|---|---|
| Ground-frame time-dependent Dijkstra | 141.2107 h | 2.14 s | — |
| Co-moving reduction (this section) | **139.9963 h** | 3.38 s (+0.05 s for Alg 4.4) | 11.2 km |

Agreement **0.860 %**, inside the ~1 % fixed-stencil metrication floor of `CORE-THEOREM §4`.
The co-moving answer is the *slightly faster* of the two, consistent with it carrying no
temporal sampling error. Causality constant on this field: `L_t` **3.22e−07 → 1.24e−07**
(2.60×); `r·L_t` at `r = 2h = 55 km`: **0.0177 → 0.0068**.

> **Note on the 3.38 s versus 2.14 s.** The co-moving solve is *slower* here, and that is
> reported rather than hidden. It reflects the R1 dilation (§4.5.2: +45 % nodes on this
> voyage) and an unoptimised reference implementation, not a property of the reduction; the
> reduction removes work (one stationary metric instead of `n_t` slices, no causality
> evaluation, no temporal interpolation) and adds domain. Which dominates is
> implementation-dependent and this file makes **no speed claim**. The claims are exactness,
> licence, accuracy and memory — all four of which are measured above.

---

## 4.8 Prop 4.9 — the monotone bucket queue

The sweep's queue is `O(log N)` per operation with a binary heap. `N` here is nodes × retained
labels, which at 0.125° with `Λ = 8` is order `10⁷` and `log N ≈ 23` on *every* operation.
**Dial (1969)** removes that factor when every increment has a positive lower bound.

### 4.8.1 The structure

An abstract type `MonotoneQueue` with operations and required complexities:

| Operation | Required complexity | Meaning |
|---|---|---|
| `push(key, item)` | `O(1)` amortised | insert |
| `pop_min()` | `O(1)` amortised, `O(log b)` worst | remove and return the least key |
| `min_key()` | `O(1)` | the running lower bound, used by `Cor 4.12` |
| `decrease_key(item, key)` | `O(1)` | optional; requires `bucket_of` (A7) |
| `empty()`, `size()` | `O(1)` | |

Representation: a ring of `n_buckets` buckets of width `Δ_min`, a cursor `b_cur`, a base key
`κ_0`, an **overflow heap** for keys beyond the window, and three counters that are part of
the contract (`monotone_violations`, `overflow_events`, `fell_back`).
`bucket(key) = ⌊(key − κ_0)/Δ_min⌋ mod n_buckets`.

Three deviations from a textbook Dial, each with a reason:

1. **Exactly sorted output.** Textbook Dial drains a bucket in arbitrary order, which suffices
   for Dijkstra but leaves the popped-key sequence non-decreasing only to within `Δ_min`.
   KAIROS reads `min_key()` as the running lower bound for `Cor 4.12`, and an out-of-order key
   there makes the **certificate wrong**. So the bucket the cursor is parked on is sorted once
   on entry and drained from its tail: `O(log b)` amortised in the bucket occupancy `b`,
   against `O(log N)` for a heap, and `b ≪ N` is exactly the regime where buckets pay.
2. **An overflow heap** for keys beyond the window, re-bucketed when the window advances. Without
   it one long edge wraps the ring and corrupts the order.
3. **Downward re-anchoring** for keys below the cursor but above the current minimum. This can
   only happen before the first pop — afterwards the cursor sits exactly on the minimum's
   bucket — i.e. during bulk seeding (`Alg 4.3` line 2), where it happens routinely.

A key pushed **below** the current minimum breaks the invariant outright. It is counted,
logged, and — by default — the queue degrades transparently to a binary heap for the rest of
the run, because a voyage plan must not die on one bad cell.

### 4.8.2 The proposition

> **Prop 4.9 (correctness of the Dial discipline).** Let the update family be that of
> `Alg 4.1` with the `ℓ_min` exclusion of Eq (4.16), on a stationary metric with
> `F ≥ F_min > 0`. Set the bucket width to
> ```
> Δ_min  =  ℓ_min·F_min  =  c_geo·h·F_min ,        c_geo = 1/√2                (4.17)
> ```
> and the bucket count to
> ```
> n_buckets  =  ⌈ r_max·F_max / Δ_min ⌉ .                                      (4.21)
> ```
> Then:
> **(a)** every update strictly increases the value by at least `Δ_min`;
> **(b)** all live keys lie in the half-open window `[κ_min, κ_min + n_buckets·Δ_min)`, so the
> ring never wraps onto an occupied bucket;
> **(c)** popping buckets in cursor order, and within the active bucket in sorted order,
> yields a **non-decreasing** key sequence;
> **(d)** consequently `Alg 4.3` finalises each node exactly once, never reopens, and returns
> the exact fixed point `T_h` — the label-setting conclusion of `03-causality.md Thm 3.C(b)`
> — with `O(1)` amortised queue cost, i.e. `O(E + N)` total instead of `O(E + N log N)`.
>
> **Proof.**
>
> **(a)** Let `x` be updated from front edge `e` at parameter `ζ ∈ Z_e`. By Eq (4.16),
> `T̂(x) = W̃_e(ζ) + ℓ_e(ζ)·F_w(x, u_e(ζ))`. The interpolated front value satisfies
> `W̃_e(ζ) = ζT(x_j) + (1−ζ)T(x_k) ≥ min(T(x_j), T(x_k))`, a convex combination being at
> least the smaller term. The `ℓ_min` exclusion (line 9 of `Alg 4.1`) guarantees
> `ℓ_e(ζ) ≥ ℓ_min = c_geo·h`, and `Lemma E3.1` guarantees that this exclusion removes only
> geometrically impossible configurations, so the bound is achievable and not vacuous.
> Finally `F_w ≥ F_min > 0`. Hence
> ```
> T̂(x) − min(T(x_j), T(x_k))  ≥  ℓ_min·F_min  =  Δ_min  >  0.
> ```
> **This is exactly the step E3 shows fails without the exclusion**: without line 9,
> `ℓ_e(ζ)` ranges over the interval `(0, r(x)]`, which is open at the bottom, has infimum 0,
> and admits no positive lower bound at all. ∎(a)
>
> **(b)** Let `κ_min` be the current minimum key, attained at the node `x_min` about to be
> popped. Any live key was produced by an update from an accepted node, so it has the form
> `T̂(y) = W̃(ζ) + ℓ·F_w`. Two bounds:
> - `W̃(ζ) ≤ max(T(x_j), T(x_k)) ≤ κ_min`, because both endpoints are accepted, and by (c)
>   applied inductively every accepted value is `≤ κ_min`;
> - `ℓ ≤ r_max` by `Prop 4.7` / `Alg 4.2`'s cap, and `F_w ≤ F_max` by (A1).
>
> Hence `T̂(y) ≤ κ_min + r_max·F_max`, i.e. every live key lies in
> `[κ_min, κ_min + r_max F_max]`, which by (4.21) is contained in the window of
> `n_buckets` buckets of width `Δ_min`. Keys outside it (which can only arise transiently
> during bulk seeding, or under an `F_max = ∞` cell) go to the overflow heap and are
> re-bucketed when the cursor advances; that is a mechanism, not an exception, and it is
> counted by `overflow_events`. ∎(b)
>
> **(c)** The cursor advances monotonically through buckets, and bucket `b` contains only keys
> in `[κ_0 + bΔ_min, κ_0 + (b+1)Δ_min)`. So keys from different buckets come out in
> non-decreasing order by construction. Within the active bucket, the deviation of §4.8.1
> item 1 sorts on entry and drains from the tail, so keys come out non-decreasing there too.
> The only way a key could be inserted *behind* the cursor is if an update produced a value in
> the current or an earlier bucket — impossible by (a), since a child key exceeds its parent's
> key by at least one full bucket width. ∎(c)
>
> **(d)** By (c) the extraction order is non-decreasing; that is hypothesis (U2) of
> `03-causality.md Thm 3.C`, whose conclusion is that the sweep terminates after exactly
> `|X|` extractions, never reopens, and returns `T_h`. The hypotheses (U1)/(U2) of that
> theorem require monotonicity of the arrival map, which in the co-moving frame holds
> **unconditionally** because `L_t ≡ 0` (`Thm C.1b`) — no causality condition is invoked here
> and none is needed. Queue cost: each `push` is `O(1)`; each `pop_min` advances the cursor,
> and the cursor advances at most `n_buckets` positions per full ring traversal with total
> advancement bounded by `(T_max − t₀)/Δ_min`, giving `O(1)` amortised. ∎(d)
>
> **What fails without each hypothesis.**
> - *Without the `ℓ_min` exclusion*: (a) fails, as E3 shows; the queue can finalise a node
>   whose value is later lowered; `T` is silently wrong and the symptom is `handbook/02 §S1`.
> - *Without `F_min > 0`*: `Δ_min = 0`; there is no bucket width. This is the **stated**
>   failure mode of `CONTRACT D3` and it is the wrong one — see §4.8.3.
> - *Without a bounded `r_max`*: (b) fails and the window is unbounded; this is why
>   `Alg 4.2` caps.
> - *Without stationarity*: (d)'s appeal to unconditional monotonicity is replaced by the
>   conditional causality licence (E4.1), which must then be checked per cell. That is the
>   ground-frame corrector of §4.9, and it is the only place in KAIROS where it happens.

### 4.8.3 E2 — the fallback trigger is anisotropy, not `F_min`

> **`CONTRACT D3` says: "fall back to a heap when `F_min` is not bounded away from 0". That
> test is wrong and must not be implemented.**

`F_min = 1/σ_max = 1/(V_max + |c|)`, which is **bounded below** by `1/(V_max + |c|_max) > 0`.
It does not approach zero. With `V_max = 7 m/s` (E2's table):

| `\|c\|` [m/s] | 0.5 | 2 | 3 | 8 |
|---|---|---|---|---|
| `F_min` [s/m] | 0.133 | 0.111 | 0.100 | 0.067 |

It shrinks by a third across the entire realistic drift range. A fallback keyed on `F_min`
therefore **never fires**, and the queue runs unprotected in exactly the cells that motivated
the fallback.

What actually diverges in a strong-drift cell is the *other* end:

```
F_max = 1/σ_min → ∞           as σ_min = V_max − |c| → 0⁺
Υ_loc = F_max/F_min = (V_max + |c|)/(V_max − |c|) → ∞                        (E2.1)
```

and by (4.21) it is the **bucket count**, not the bucket width, that becomes unbounded.

> **Corrected fallback rule (E2), NORMATIVE.**
> ```
> use the heap when   Υ_loc(y)  >  Υ_heap ,        Υ_heap = 12  (default)     (4.22)
> and treat F = +∞ directions as excluded per E1 (Eq 4.13).
> ```
> The trigger is **anisotropy**, not `F_min`. The decision is made once at solver setup from
> `max_y Υ_loc` over the domain, not per cell, so the solver holds one queue object and never
> branches inside the loop.

**Why `Υ_heap = 12`, derived.** Substituting `r_max = √2 h Υ` (Prop 4.7) and (4.17) into
(4.21):

```
n_buckets = ⌈ √2 h Υ · F_max / (c_geo h F_min) ⌉ = ⌈ √2·Υ·Υ_loc/c_geo ⌉ = ⌈ 2·Υ² ⌉  (4.23)
```

using `c_geo = 1/√2` and `Υ_loc ≤ Υ`. So the ring size grows **quadratically** in the
anisotropy. With the normative ring of `1 024` buckets (one empty bucket is one empty list,
so a generous ring is nearly free), (4.23) is satisfiable up to `Υ = √512 = 22.6`. Setting
`Υ_heap = 12` leaves `2·144 = 288` buckets, a factor `3.6` of headroom against the ring, and
corresponds to `|c|/V_max = (Υ−1)/(Υ+1) = 11/13 = 0.846` — i.e. the fallback engages when the
drift reaches 85 % of the ship's through-water capability, which is the regime where E1's
cone is about to open and the metric is about to become one-sided anyway. Both numbers are
derived here; neither is tuned.

**Reference numbers** for the golden-vector field (`V_s = 7.2`, `|c| = 1.5`, `h = 27 798.73 m`):

```
F_min = 1/8.7 = 0.114 942 528 735 632 s/m      F_max = 1/5.7 = 0.175 438 596 491 228 s/m
Δ_min = 0.707 106 781 × 27 798.73 × 0.114 942 528 7  =  2 259.4 s  =  37.66 min
Υ = 1.526 315 789 5      n_buckets = ⌈2 × 1.526 315 789 5²⌉ = ⌈4.659⌉ = 5     (4.24)
```

Five buckets. The ring of 1 024 is not a tuning parameter on this field, it is slack.

**Mandatory counter.** `monotone_violations` must be reported and must be **0**
(`handbook/01 §G5`, `handbook/02` instrumentation table). A non-zero count means (a) or (b)
of `Prop 4.9` has been violated, and the returned `T` is not the fixed point.

---

## 4.9 STEP 6 — the residual corrector sweep

Run this **only** when the residual is significant. The decision rule is quantitative:

```
run the corrector  iff   max_y r(y)·L_t^R(y)  >  δ_trigger ,   δ_trigger = 0.05   (4.25)
```

where `L_t^R := Lip_t(R)` is the temporal Lipschitz constant of the **residual**
`R(x,t) = E(x,t) − E₀(x − wt)` of Eq (C.8), *not* of `E`. `δ_trigger = 0.05` is one twentieth
of the causality budget of 1 and is set so the corrector fires well before the licence is at
risk; it is a policy constant and is flagged as such, not derived.

**What the corrector is.** A single ground-frame sweep, seeded by the co-moving route of
step 5, restricted to a tube about that route. It is a *correction*, not a re-solve: the
co-moving answer is already exact for the advected part of the field (`Thm C.1`), so the
corrector's only job is the part `Thm C.1` does not cover.

> **Alg 4.9 — residual corrector.**
>
> **Input.** Ground-frame field `E`; the recovered route `x(·)` and its schedule `τ(·)` from
> `Alg 4.8`; tube radius `ρ_tube`; the corrector metric `F` (time-dependent, ground frame).
> **Output.** A corrected route and schedule, plus the corrector diagnostics.
> **Invariant.** The returned arrival time is `≤` the arrival time of the seed route
> evaluated against the true ground-frame field. (The seed is feasible, so the sweep can only
> improve on it; if it does not, it returns the seed.)
> **Complexity.** `O(N_tube · |NF| · C_ζ)` with
> `N_tube ≈ 2ρ_tube·length(route)/h²`. At `ρ_tube = 8h` on the reference voyage,
> `N_tube ≈ 2·8·27 799·3 698 000/27 799² ≈ 2 130` nodes — **7 % of `N`**.
>
> ```
>  1  build the tube  Ω_tube = { y : dist(y, route) ≤ ρ_tube } ∩ water
>  2  for y ∈ Ω_tube:  T[y] ← +∞ ;  status[y] ← FAR
>  3  seed: for each waypoint (ϕ_k, λ_k, t_k) of the route,
>  4        set T at its nearest node to t_k if smaller, push it
>  5  U ← the seed route's arrival time            -- a valid upper bound throughout
>  6  while not Q.empty():
>  7      (key, x) ← Q.pop_min()
>  8      if key > U:  break                       -- nothing left can improve on the seed
>  9      if status[x] = ACCEPTED: continue
> 10      status[x] ← ACCEPTED
> 11      ρ ← r(x)·L_t^R(x, T[x])                  -- E4.1, on the RESIDUAL constant
> 12      if ρ ≤ 1 − δ_safe:
> 13          F_use ← F                            -- plain time-dependent update
> 14      else:
> 15          F_use ← F̃_ℓ  of Eq (E5.1)            -- wait relaxation, ℓ-scaled
> 16          count_relaxed ← count_relaxed + 1
> 17      relax every y ∈ Ω_tube within r(y) of x using Alg 4.1 with F_use,
> 18          evaluating F_use at the DEPARTURE time W̃_e(ζ)
> 19  return the improved route, count_relaxed, count_horizon_truncated
> ```
>
> **Line 11 is the whole point of the reduction as a preconditioner.** The guard is applied to
> `L_t^R`, the temporal Lipschitz constant of what is left after the advection is removed,
> and not to `L_t` of the raw field. Measured (`CORE-THEOREM` Test 8.10, regimes B and C):
> `r·L_t` at `r = 56 km` goes from **1.309 / 1.307 (VIOLATED — a single-pass solve is not
> licensed)** in the ground frame to **0.272 / 0.261 (OK)** in the co-moving frame. A
> **4.6–5.0× reduction at the 99th percentile.** That is the difference between a sweep that
> is licensed and one that is not.
>
> **The honest cost, reported.** The **median** `r·L_t` gets *worse* by about 4.5× (a 0.22×
> "reduction"). In the ground frame most cells are far from any system and see almost no
> change; in the co-moving frame the sampling point slides through space, so quiet cells now
> see the field vary. De-advection **trades a large improvement in the worst cells for a
> modest degradation in already-benign ones.** Because the causality condition is a worst-case
> condition, this is the right trade — but it is a trade, and reporting only the max oversells
> it. Report max, p99 and median, in both frames, always.
>
> **Line 15 uses the corrected wait relaxation (E5.1), not the CONTRACT form.**
> ```
> F̃_ℓ(x,t,u)  :=  inf over s ∈ [0, S_max(t)] of [ s/ℓ + F(x, t+s, u) ]        (E5.1)
> S_max(t)     :=  (t₀⁻ + H_fc) − t
> ```
> The penalty denominator must be the **same `ℓ` the update uses**, not `h`. With `s/h`
> against a multiplier `ℓ ≤ Υ·h`, the waiting penalty is over-charged by a factor up to `Υ`,
> the running-infimum identity `t + ℓF̃ = inf_{t'≥t}[t' + ℓF(x,t',u)]` fails, and
> unconditional causality does **not** follow. The truncation at the forecast horizon is
> mandatory (`inf_{s≥0}` requires `F` beyond the horizon, which does not exist); beyond it,
> persistence of the final frame is the normative convention and
> **`count_horizon_truncated` must be reported**.
>
> **`δ_safe = 0.05`** — a policy margin against the estimation error in `L_t^R`, which is a
> finite difference across forecast frames. Flagged as policy, not derived.

**Sanity bound on `L_t` estimation (`handbook/02 §S7`).** `h·L_t` should be `≈ 0.05–0.15` for
a 0.25° grid with 3-hourly forecasts. A value inflated by `~10⁴` means the frame difference
was not divided by the frame interval **in seconds**. A value of exactly zero means the field
under test is not actually time-varying, or the difference was taken at a single time index.

---

## 4.10 STEP 7a — the ε-Pareto hook

Full treatment is `05-multiobjective.md` (§5, `Thm 5.2`, `Thm 5.3`, `Prop 5.4`). §4 owns only
the interface, which is one substitution in `Alg 4.3`:

```
scalar T[n]          →   LabelSet[n]  :  a bounded set of cost vectors in ℝ^k
line 10 "T̂ < T[y]"   →   "T̂ is not ε-dominated by any label already at y"
line 11 assignment   →   insert, then discard ε-dominated labels
queue key            →   objective 0 (time), which is NEVER bucketed
```

Two normative points that belong here because they bind the data layout of §4.2.2:

- **Value bucketing, not increment bucketing (E7).** Bucket on the objective *value*:
  ```
  bucket_i(ℓ) = ⌊ log(ℓ_i / C_i^min) / log(1+ε) ⌋ ,   i = 2 … k               (E7.1)
  ```
  This is the **Tsaggouris & Zaroliagis (2009)** construction, and it gives a uniform `(1+ε)`
  guarantee with **no path-length dependence**. The superseded increment-bucketing gives
  `Λ ≈ (D·log range/ε)^{k−1}` — with `D ≈ S/h ≈ 180`, `ε = 0.02` and two decades of range
  that exceeds `10¹⁰` labels per node, i.e. **vacuous**. The corrected bound is
  ```
  Λ  ≤  ∏_{i=2}^{k} ( ⌈ log(C_i^max/C_i^min)/log(1+ε) ⌉ + 1 )                 (E7.2)
  ```
  giving `Λ ≤ 234² ≈ 5.5×10⁴` worst case and **10–40 observed** after dominance pruning —
  which is the `Λ` that sizes arrays A14/A15.
- **Objective 0 (time) is never bucketed**, and bottleneck (`max`-accumulated) objectives take
  finitely many distinct values along a route and are bucketed on the value directly.

The symptom of getting this wrong is length-dependent and therefore easy to miss: short
voyages are fine and long ones degrade (`handbook/02 §S4` cause 3). Test by comparing the
front on a route against the front on the same route solved as two sequential halves.

**Interaction with the reduction.** `Thm C.1` is a statement about the *time* objective and
the geometry of the reachable set; it does not by itself make fuel or risk stationary. Fuel
and risk rates depend on the environment at the ship's position, which in the co-moving frame
is `E₀(y)` — stationary under A1. So under A1 **all** objectives become stationary and the
multi-objective solve inherits the same licence. Under a significant residual they do not, and
§4.9's corrector must carry the label sets too. This is stated, not measured; no
multi-objective co-moving run has been reported. **Flagged as unverified.**

---

## 4.11 STEP 7b — the optimistic coarse solve and the certificate

### 4.11.1 The construction (D5)

The coarse grid is the fine grid blocked by `ρ_c = 8`, with coarse nodes at block **centres**
so the representative point is never more than half a coarse cell from anything it represents.
Two things make the relaxation optimistic rather than merely plausible:

- the coarse water mask is the **OR** over the block, then dilated by one coarse cell. A block
  containing any navigable water is navigable at the coarse level. Anything stricter (AND, a
  majority vote) could declare a genuinely passable strait closed and turn the "optimistic"
  bound *pessimistic*, which destroys admissibility.
- the metric minimum is taken over the **dilated** cell:
  ```
  D_I  :=  C_I ⊕ B(0, H)        (the 3×3 coarse-block footprint around C_I)
  F_low(S)  :=  inf { F(z,u) : z ∈ S ∩ Ω , |u| = 1 }  =  inf_{z∈S∩Ω} 1/σ_max(z)   (4.26)
  ```

> **`CONTRACT D5` is explicit that the naive "min over the bare cell" is wrong, and it is.**
> A fine path can clip the corner of a cell it barely enters, and the cost of that clipped
> excursion is bounded below by the minimum over the *dilated* footprint, not over the cell
> itself. Step 2 of the proof below is precisely where the dilation is used, and the proof
> **fails without it**. The symptom of the un-dilated version is `handbook/02 §S4` cause 2:
> the answer is quietly suboptimal, and the discriminating test is to re-run with the
> heuristic disabled and see whether the answer *improves*.

### 4.11.2 Alg 4.10

> **Alg 4.10 — coarse optimistic solve.**
>
> **Input.** Fine grid, `ρ_c`, the metric, destination `x_B`.
> **Output.** `T_low` (A16), a lower bound on cost-to-go from every coarse cell.
> **Invariant.** `T_low(I) ≤ T(x → x_B)` for every fine node `x ∈ C_I` (`Prop 4.11a`).
> **Complexity.** `O(N/ρ_c² · log(N/ρ_c²))` for the coarse Dijkstra plus `O(9N)` for the
> dilated minima (each fine node contributes to the 9 coarse cells whose dilated footprint
> contains it). On the reference grid: 500 coarse nodes, `9 × 29 529 = 265 761` metric
> minimum updates. Negligible against the fine sweep.
>
> ```
>  1  build the coarse mask: blk[I] ← OR over the block ; then dilate blk by one coarse cell
>  2  for each coarse cell I:  F_low[I] ← min over fine nodes in the DILATED cell D_I
>  3                                        of  1/σ_max(that node)                (4.26)
>  4  build the coarse graph G_H: 8-adjacency between navigable coarse cells,
>  5      w(I,J) ← c_adm · dist(X_I, X_J) · min(F_low[I], F_low[J])                (4.27)
>  6      with  c_adm = 1/(2√2) = 0.353 553 390 6
>  7  seed: T_low[I] ← 0 for I_B AND ALL EIGHT of its coarse neighbours             (†)
>  8  run Dijkstra on G_H from that seed set (reverse orientation: costs to the goal)
>  9  return T_low
> ```
>
> `(†)` **The 3×3 goal seed is required for the proof, not a convenience.** See step 5 of the
> proof. Seeding only `I_B` leaves an uncompensated final edge of up to
> `c_adm·√2H·F_low = (H/2)F_low` and admissibility fails by exactly that much.

### 4.11.3 Prop 4.11

> **Prop 4.11 (admissibility and consistency of the optimistic coarse heuristic).**
>
> **(a) Admissibility.** With `F_low` over the **dilated** cell (4.26), edge cost (4.27) with
> `c_adm = 1/(2√2)`, and the 3×3 goal seed, `T_low(I) ≤ T(x → x_B)` for every fine node
> `x ∈ C_I`.
>
> **(b) Consistency on the coarse graph.** `T_low(I) ≤ w(I,J) + T_low(J)` for every coarse
> edge `(I,J)`.
>
> **(c) Consistency of the fine lift — FAILS, with an explicit bound.** The lifted heuristic
> `h(x) := T_low(I(x))` is **not** consistent on the fine grid: across a coarse-cell boundary
> it can jump by `c_adm√2H·F_low = 4h·F_low`, while one fine edge costs as little as
> `Δ_min = c_geo·h·F_min`. Since `F_low ≥ F_min` (a minimum over a subregion of the same
> quantity), the jump exceeds the fine edge cost by a factor of at least
> `4/c_geo = 4√2 ≈ 5.66`.
>
> **Proof.**
>
> **(a)** Let `γ : [0,L] → Ω` be an optimal admissible fine path from `x` to `x_B`,
> parameterised by arclength, with `J(γ) = ∫₀^L F(γ(s), γ'(s)) ds = T(x → x_B)`.
>
> *Step 1 — sample `γ` at separation `H/2`.* Set `s_0 = 0` and inductively
> `s_{k+1} = min{ s > s_k : |γ(s) − γ(s_k)| ≥ H/2 }`, terminating when no such `s ≤ L` exists;
> let `p_k = γ(s_k)`, `k = 0 … m`, and note `p_0 = x`. By continuity of `γ`, the minimum is
> attained with `|p_{k+1} − p_k| = H/2` **exactly**. Also `|x_B − p_m| < H/2` by termination.
>
> *Step 2 — the dilation, and where it is used.* For each `k < m`, the arc
> `γ|[s_k, s_{k+1}]` lies entirely within distance `H/2` of `p_k` (by minimality of `s_{k+1}`,
> no earlier point of the arc reaches distance `H/2`). Now `p_k ∈ C_{I_k}` where
> `I_k := I(p_k)`, so every point of that arc lies in `C_{I_k} ⊕ B(0, H/2) ⊆ D_{I_k}`.
> **The arc leaves the bare cell `C_{I_k}` — that is exactly the corner-clip of D5 — but it
> cannot leave the dilated cell `D_{I_k}`.** Hence, by (4.26),
> ```
> ∫_{s_k}^{s_{k+1}} F(γ, γ') ds  ≥  F_low(D_{I_k}) · length(γ|[s_k,s_{k+1}])
>                                ≥  F_low(D_{I_k}) · |p_{k+1} − p_k|  =  F_low[I_k]·(H/2).
> ```
> With the bare cell this step is false: the arc can spend most of its length outside
> `C_{I_k}` in a region where `F` is smaller than anything inside `C_{I_k}`, and the
> inequality reverses. **This is the gap D5 exists to close.**
>
> *Step 3 — consecutive samples lie in 8-adjacent coarse cells.* `|p_{k+1} − p_k| = H/2 < H`.
> If the coarse cell indices differed by 2 or more in either coordinate, the corresponding
> coordinate separation would be at least `H` (two full cell widths minus the interiors), so
> the distance would be `≥ H > H/2`. Hence the indices differ by at most 1 in each coordinate:
> `I_k` and `I_{k+1}` are equal or 8-adjacent. Both cells contain a point of `γ ⊂ Ω`, hence
> contain navigable water, hence are navigable coarse nodes under the block-OR mask — so if
> distinct, the edge `(I_k, I_{k+1})` exists in `G_H`.
>
> *Step 4 — each coarse edge is paid for.* If `I_k = I_{k+1}` there is no edge and nothing to
> pay. Otherwise, since the maximum centre-to-centre distance across an 8-adjacency is
> `√2 H`,
> ```
> w(I_k, I_{k+1})  =  c_adm·|X_{I_k} − X_{I_{k+1}}|·min(F_low[I_k], F_low[I_{k+1}])
>                  ≤  (1/(2√2))·√2H·F_low[I_k]
>                  =  (H/2)·F_low[I_k]
>                  ≤  ∫_{s_k}^{s_{k+1}} F(γ,γ') ds        by Step 2.
> ```
> **This is where `c_adm = 1/(2√2)` comes from**: it is exactly the factor that makes the
> longest coarse edge (`√2H`, a diagonal) no more expensive than the shortest guaranteed
> fine excursion (`H/2`). It is derived, not tuned.
>
> *Step 5 — the tail.* `|x_B − p_m| < H/2 < H`, so by the argument of Step 3, `I_m` is equal
> or 8-adjacent to `I_B`. Because `Alg 4.10` line 7 seeds `T_low = 0` on `I_B` **and all eight
> of its neighbours**, `T_low(I_m) ≤ 0 +` (nothing), i.e. the tail is free and needs no
> corresponding fine cost. Without the 3×3 seed a final edge of up to `(H/2)F_low` would be
> charged against a fine arc that may be arbitrarily short, and (a) would fail by that amount.
>
> *Step 6 — sum.* The coarse path `I_0 → I_1 → … → I_m` (with equal consecutive cells
> collapsed) is a path in `G_H` from `I_0 = I(x)` to the goal seed set, so `T_low(I(x))`, being
> the graph distance to that set, is at most its cost, which by Steps 4 and 5 is at most
> `Σ_k ∫_{s_k}^{s_{k+1}} F = J(γ) = T(x → x_B)`. ∎(a)
>
> **(b)** `T_low` is by construction the graph distance in `G_H` from `I` to the goal seed set.
> Graph distance satisfies the triangle inequality along any edge: a path from `J` prefixed by
> the edge `(I,J)` is a path from `I`, so `T_low(I) ≤ w(I,J) + T_low(J)`. ∎(b)
>
> **(c)** Take `x` and `y` fine nodes in 8-adjacent coarse cells `I ≠ J`, with `y` on the
> optimal side. Then `h(x) − h(y) = T_low(I) − T_low(J)`, which by (b) can be as large as
> `w(I,J) = c_adm·√2H·F_low = (H/2)F_low = (ρ_c h/2)F_low = 4h·F_low` at `ρ_c = 8`. The fine
> edge from `x` to `y` costs at least `Δ_min = c_geo h F_min = 0.7071 h F_min`. Since
> `F_low ≥ F_min`, the ratio is at least `4/0.7071 = 5.657 = 4√2`. Consistency
> (`h(x) ≤ c(x,y) + h(y)`) therefore fails, and can fail by a factor `4√2` at `ρ_c = 8`, or
> `ρ_c√2/(2c_geo) = ρ_c/√2` in general. ∎(c)
>
> **Consequence of (c), and the normative rule it forces.**
>
> An admissible-but-inconsistent heuristic makes A\* correct **only if nodes may be
> reopened**. Reopening destroys `Prop 4.9`'s invariant I3 and with it the single-pass
> property that `Thm C.1` exists to deliver. KAIROS therefore uses the coarse bound in
> **bounding mode only**:
>
> ```
> NORMATIVE: T_low is used (i) to prune — discard any queue entry with
>            key + T_low(I(node)) > U, the incumbent upper bound — and
>            (ii) to produce the certificate of Cor 4.12.
>            T_low is NEVER added to the queue key.                            (4.28)
> ```
>
> Pruning is safe with a merely admissible bound (it discards only entries that provably
> cannot beat the incumbent) and it does not reorder the queue, so `Prop 4.9(c)` and
> `Alg 4.3`'s invariants I1–I3 are untouched. An implementation that wants true A\* ordering
> must enable reopening and must then **stop claiming the single-pass property**; that
> trade-off is available but is not the KAIROS default.
>
> **What fails without each hypothesis.**
> - *Bare cell instead of dilated:* Step 2 fails; the bound is not a lower bound;
>   `handbook/02 §S4` cause 2.
> - *`c_adm = 1` instead of `1/(2√2)`:* Step 4 fails by up to `2√2`; a diagonal coarse edge
>   over-charges relative to the guaranteed fine excursion.
> - *4-adjacency instead of 8:* Step 3's conclusion "equal or 8-adjacent" cannot be realised
>   as a single edge; a diagonal move costs two cardinal edges and the constant becomes
>   `c_adm = 1/4`, halving the heuristic's strength.
> - *AND-mask instead of OR-mask:* a passable strait can be declared closed and `T_low`
>   becomes an over-estimate; admissibility fails.
> - *Goal seeded at `I_B` only:* Step 5 fails by `(H/2)F_low`; on the reference grid that is
>   `111 195 m × F_low`, i.e. ~3.4 h at `σ_max = 9 m/s`. Not small.

### 4.11.4 Cor 4.12 — the a posteriori certificate

> **Cor 4.12 (a posteriori optimality certificate).** Let `J` be the objective-0 value of a
> route actually returned by KAIROS (so `J` is achieved by a feasible trajectory, hence
> `J ≥ T*`, the true optimum), and let `T_low(I(x_A))` be the coarse bound of `Alg 4.10`.
> Then `T_low(I(x_A)) ≤ T*` and the reported gap
> ```
> gap  :=  ( J − T_low(I(x_A)) ) / T_low(I(x_A))                               (4.29)
> ```
> is an **upper bound on the true relative suboptimality** `(J − T*)/T*` of the returned
> route.
>
> **Proof.** `T_low(I(x_A)) ≤ T(x_A → x_B) = T*` is `Prop 4.11(a)` applied at `x = x_A`.
> Write `z ↦ J/z − 1 = (J−z)/z`, which is strictly decreasing in `z > 0`. Since
> `0 < T_low ≤ T*`, `(J − T_low)/T_low ≥ (J − T*)/T*`. ∎
>
> **Remarks.**
> - **This is the primary guarantee, not a bonus.** After E6, the a-priori realisability bound
>   is vacuous at voyage scale: with `L_v ≈ 10⁻⁵ s⁻¹` and `T ≈ 1.2×10⁶ s` (14 days),
>   `exp(L_v T) ≈ 1.6×10⁵`, so `Thm 2.11`'s global form says nothing. `Cor 4.12` is
>   computable, tight, and does not degrade with voyage length. That is a better guarantee
>   than the one the earlier draft claimed and could not support.
> - **In the co-moving frame the certificate needs no modification.** By `Thm C.1(c)` the
>   interception constraint is active, `t* = T_w(y*)`, so the ground arrival time equals the
>   co-moving arrival time at the goal node. The coarse solve is run on the co-moving
>   (stationary) metric and (4.29) bounds the ground-frame suboptimality directly.
> - **The bound is only as tight as `ρ_c`.** A larger `ρ_c` makes the coarse solve cheaper
>   and the certificate weaker (the dilated-cell minimum is taken over a larger region, so
>   `F_low` drops). `ρ_c = 8` is the default; report the achieved gap, and if it is
>   uninformatively large, lower `ρ_c` rather than reinterpreting the number.
> - **Report it always** (`handbook/01 §G5`). A KAIROS implementation that does not publish
>   the certificate gap on the returned route is not distinguishable from a demo.

---

## 4.12 Polish — Alg 4.13 (Zermelo shooting) and Alg 4.14 (notch projection)

The grid route is a *global* answer with a `~1 %` metrication floor (`CORE-THEOREM §4`).
Polish is *local*: it replaces the polyline with a true characteristic of the continuum
problem, using the grid route only as the initial guess that puts Newton inside the basin of
attraction. **The global sweep is not optional** — shooting alone has no way to choose which
side of a storm to pass.

### 4.12.1 The characteristic system

In the **local orthonormal metre frame** `(𝐞_E, 𝐞_N)` per E8, with `V_s` the through-water
speed held constant along a characteristic (`Zermelo 1931`; this is the classical reduction —
for the throttle-varying case the full costate system of `Prop 3.5` is needed and this
reduction does not apply), write `c = (u, v)` for the drift and subscripts `E, N` for metre-frame
partial derivatives. The state is `z = (x_E, x_N, θ)` with `θ` the compass heading
(`n(θ) = (sin θ, cos θ)`, 0 = north, clockwise):

```
ẋ_E = f₁ = V_s sin θ + u(x)
ẋ_N = f₂ = V_s cos θ + v(x)                                                  (4.30)
θ̇   = f₃ = Z(x,θ) = u_N sin²θ − (u_E − v_N) sin θ cos θ − v_E cos²θ
```

`(4.30₃)` is Zermelo's navigation formula in compass form. **No `V_s` appears in it**:
heading responds to current *shear* and to nothing else. In a uniform current every partial
vanishes, so `θ̇ ≡ 0` **identically**, for every heading, position and current magnitude —
which is golden test `G4`, the sharpest single check in the project
(`max |dθ/dt| < 10⁻¹⁴ rad/s`, and **zero intermediate turns** on the recovered route).

### 4.12.2 The variational equation for the Newton derivative

Newton on the shooting parameter `θ₀` needs `de/dθ₀` where `e` is the terminal residual. The
exact derivative is obtained from the **variational (first-variation) equation**, given here
explicitly as required.

Let `s(t) := ∂z(t)/∂θ₀ ∈ ℝ³`. Differentiating (4.30) with respect to `θ₀` and exchanging the
order of differentiation:

```
ṡ  =  J(t)·s ,      s(0) = (0, 0, 1)ᵀ                                        (4.31)
```

with `J = ∂f/∂z` evaluated along the trajectory:

```
        ⎡  u_E                     u_N                      V_s cos θ  ⎤
J(t) =  ⎢  v_E                     v_N                     −V_s sin θ  ⎥     (4.32)
        ⎣  ∂Z/∂x_E                 ∂Z/∂x_N                  ∂Z/∂θ      ⎦

∂Z/∂x_E =  u_{NE} sin²θ − (u_{EE} − v_{NE}) sin θ cos θ − v_{EE} cos²θ
∂Z/∂x_N =  u_{NN} sin²θ − (u_{EN} − v_{NN}) sin θ cos θ − v_{EN} cos²θ       (4.33)
∂Z/∂θ   =  (u_N + v_E)·sin 2θ  −  (u_E − v_N)·cos 2θ
```

*Derivation of `∂Z/∂θ`:* `d(sin²θ)/dθ = sin 2θ`, `d(sin θ cos θ)/dθ = cos 2θ`,
`d(cos²θ)/dθ = −sin 2θ`; substitute into `(4.30₃)` and collect. ✓

**From `s` to `de/dθ₀`.** Let the residual be the **signed** perpendicular offset of the
target `x_B` from the track at the closest-approach parameter `σ_c`, positive when the target
lies to starboard, measured against the closest point of the **polyline**:

```
e(θ₀) = ⟨ x_B − P(σ_c, θ₀) , n̂_⊥(σ_c, θ₀) ⟩ ,      n̂_⊥ = starboard unit normal   (4.34)
```

Then

```
de/dθ₀  =  − ⟨ n̂_⊥(σ_c) , ( s_E(σ_c), s_N(σ_c) ) ⟩                            (4.35)
```

**Proof of (4.35), including why the moving foot contributes nothing.** At the
closest-approach parameter, `⟨x_B − P, ∂P/∂σ⟩ = 0`, so `x_B − P` is parallel to `n̂_⊥` and
`|e| = |x_B − P|`. Consider `d²(θ₀) := |x_B − P(σ_c(θ₀), θ₀)|²`. Because `σ_c` is an interior
minimiser of `σ ↦ |x_B − P(σ,θ₀)|²`, the envelope theorem applies: the total derivative equals
the partial derivative at fixed `σ`,
```
d(d²)/dθ₀ = ∂/∂θ₀ |x_B − P(σ,θ₀)|²  |_{σ=σ_c}  =  −2⟨ x_B − P , ∂P/∂θ₀ ⟩ .
```
Substituting `x_B − P = e·n̂_⊥` and `d² = e²` gives `2e·de/dθ₀ = −2e⟨n̂_⊥, ∂P/∂θ₀⟩`, and
`∂P/∂θ₀ = (s_E, s_N)` by definition of `s`. Divide by `2e` (`e ≠ 0`; at `e = 0` Newton has
already converged). ∎

**Two conventions that are load-bearing.**
- The residual must be **signed**, not `|miss|`: the absolute value has a kink at its root and
  Newton cannot cross it.
- The residual must be taken against the closest point of the **polyline**, not the closest
  **waypoint**: the latter jumps discontinuously as the minimising index changes with `θ₀`,
  which corrupts the derivative.

> **NORMATIVE CAVEAT, and a deliberate divergence of the reference implementation.**
> `(4.33)` contains the **second** derivatives of the current. Operational forecasts are
> delivered as trilinear interpolants: inside a cell the second derivative is identically
> zero, and across a cell face it is a delta function. Differencing it yields either `0` or a
> spurious spike depending on where the step lands, so a variational solve on a `C⁰` field
> propagates interpolation noise with the authority of an ODE.
>
> Therefore:
> - **Use (4.31)–(4.35) when the environment is `C²`** — analytic test fields, or a bicubic /
>   spline reconstruction of the forecast. There it is exact and costs 6 extra right-hand-side
>   evaluations per RK4 step.
> - **Otherwise use a central difference on the fully integrated trajectory**,
>   `de/dθ₀ ≈ (e(θ₀+δ) − e(θ₀−δ))/(2δ)` with `δ = 10⁻⁶ rad` (0.2 arcsec). This differences a
>   quantity that is smooth in `θ₀` even when the field is only `C⁰`, and it is *cheaper*
>   here: two extra trajectories per Newton iteration against six extra right-hand-side
>   evaluations per step. This is what `src/kairos/polish.py` does, deliberately.
> - **Step-size justification for `δ = 10⁻⁶`:** the residual accumulates over `~10³` RK4 steps
>   on displacements `~10⁶ m`, so its round-off floor is `~10³ · 2×10⁻¹⁶ · 10⁶ ≈ 10⁻⁷ m`. A
>   `10⁻⁶ rad` perturbation moves the far end of a 1 000 km route by `~1 m`, seven orders
>   above that floor, while the central-difference truncation error `δ²e'''/6` stays `~10⁻⁶ m`
>   against a derivative of `~10⁶ m/rad`. Both error sources are below `10⁻¹¹` relative.

### 4.12.3 Alg 4.13

> **Alg 4.13 — Zermelo shooting polish.**
>
> **Input.** Field; start `x_A`; target `x_B`; `V_s`; `t₀`; heading guess `θ_guess` (the
> heading of the first leg of the grid route); step `dt`; tolerance `tol` (1 nautical mile =
> 1 852 m); `max_iters = 8`.
> **Output.** `(route, converged, iters)`; on non-convergence the caller **must** fall back to
> the grid route.
> **Invariant.** The returned track is a genuine characteristic of (4.30) from `x_A`; only its
> initial heading is adjusted.
> **Complexity.** `O(max_iters · n_steps)` right-hand-side evaluations, `n_steps ≤ t_max/dt`.
>
> ```
>  1  θ ← θ_guess ;  D ← great-circle range(x_A, x_B)
>  2  dt ← 600 s                                   -- 10 min; see note
>  3  t_cap ← t₀ + 5·D/V_s                         -- transit cap; see note
>  4  (e, miss, track) ← RESIDUAL(θ)
>  5  iters ← 0 ;  cut_locus ← false
>  6  while miss > tol and iters < max_iters:
>  7      iters ← iters + 1
>  8      de ← (4.35) if the field is C², else the central difference of §4.12.2
>  9      if de is not finite or |de| < max(1, 10⁻⁴·D):
> 10          cut_locus ← true ; break            -- see §4.12.4
> 11      step ← clamp( −e/de , −0.5 , +0.5 )      -- radians
> 12      accepted ← false
> 13      for 6 halvings:
> 14          (e', miss', track') ← RESIDUAL(θ + step)
> 15          if |e'| < |e| or miss' ≤ tol:
> 16              θ, e, miss, track ← θ+step, e', miss', track' ; accepted ← true ; break
> 17          step ← step/2
> 18      if not accepted: break                   -- keep the best iterate, flag it
> 19  return (track truncated at closest approach, miss ≤ tol, iters)
>
> RESIDUAL(θ):
> 20  integrate (4.30) by classical RK4 with fixed step dt from (x_A, θ, t₀),
> 21      stopping at t_cap, at the forecast horizon, or at closest approach
> 22  return the signed offset (4.34), |miss|, and the track
> ```
>
> **Line 2, fixed step rather than adaptive.** The metric is sampled from a forecast whose own
> temporal resolution is 1–3 h; an adaptive controller would be chasing interpolation
> artefacts. 600 s is two orders below the forecast's own resolution.
>
> **Line 3, the transit cap is not cosmetic.** On a sphere, a drift-dominated field
> (`|c| > V_s`) has **no unreachable points**: with 12 m/s of zonal current and a 3 m/s ship,
> the shot finds a characteristic that circumnavigates and arrives from the far side,
> converging to a 39-million-second route that is a perfectly valid Zermelo extremal and a
> completely useless answer. `5·D/V_s` excludes those.
>
> **The sphere-correction term, and its measured size.** `(4.30₃)` is a *plane* result. On the
> sphere the heading is measured against a frame that itself rotates as the ship moves over
> it; adding `(v_E/R_E)·tan ϕ` (with `v_E` the eastward **ground** speed) makes the drift-free
> characteristic an exact great circle — differentiate Clairaut's `cos ϕ sin θ = const` to see
> it. It is **default OFF** because switching it on makes `θ̇ ≠ 0` in a uniform current and so
> destroys the `G4` diagnostic. It is **not small**: shooting 4 300 km from 35 °N on a 070
> heading in still water, with it off the track is a rhumb line, the bearing defect against
> the true great circle reaches **15.71°** and the path is **61.1 km longer (1.43 %)**; with
> it on the track is a great circle to `0.0000°` and arc/great-circle `= 1.000 000 000`.
> **Leave it off for validation against planar analytics and for legs of a few hundred km;
> turn it on for ocean crossings; never report a transocean distance with it off.**

### 4.12.4 The cut-locus fallback

Non-convergence at a **cut locus** is a real geometric feature, not a bug. A cut locus is
where two genuinely distinct optimal routes tie — "north or south of the storm, both equally
good". The value function is non-smooth there and Newton has nothing to converge to: the
terminal point stops responding to `θ₀` and `|de/dθ₀|` collapses.

> **NORMATIVE.** Detect it as `|de/dθ₀| < max(1 m/rad, 10⁻⁴·D)` — four orders below the
> `~D` m/rad a well-posed shot exhibits — cap at 8 iterations, **return the unpolished grid
> route**, and **flag the leg**. Surfacing "there are two equally good options here" is a
> feature worth showing the operator, not an error to hide.
>
> **It is a bug, not a cut locus, if it fails to converge in a *uniform* field.** There
> `θ̇ ≡ 0` and the shooting problem is trivial — one Newton step should nail it. Failure there
> means the variational derivative has the wrong sign, or the RK4 integration is in the wrong
> frame (degrees where it should be metres). That is the discriminating test.

### 4.12.5 Alg 4.14 — notch projection

D4 solves with `conv 𝒱`, whose support function cannot see the dents that the seakeeping bans
S1–S7 punch in the indicatrix (`𝔥_𝒱 = 𝔥_{conv 𝒱}` identically). The returned control may
therefore sit **inside a notch**: realisable only by chattering between two admissible
headings at infinite frequency, which a rudder with a rate limit cannot do. `Alg 4.14`
replaces every such control with the nearest genuinely steerable one.

> **Alg 4.14 — notch projection.**
>
> **Input.** Route (waypoints with times); vessel; field; ban predicate; scan resolutions.
> **Output.** `(projected route, n_projected)`. The input is not mutated.
> **Invariant.** The **ground track is held fixed**; only the **schedule** is re-integrated.
> **Complexity.** `O(L · n_speed_scan)` typical, `O(L · n_heading_scan · n_speed_scan)` worst.
>
> ```
>  1  for each leg (a → b) of the route, in order:
>  2      recover the commanded control: ground velocity = leg displacement / leg duration;
>  3          through-water vector = ground velocity − c(midpoint, t_mid);
>  4          V_cmd = |through-water|,  θ_cmd = its direction
>  5          (θ_cmd is NOT the course over ground; the difference is the set-and-leeway crab)
>  6      if V_cmd outside the engine envelope, or banned(vessel, env, V_cmd, θ_cmd):
>  7          try the nearest admissible SPEED at the same heading      -- what a master does first
>  8          if none exists, sweep heading outward in steps of π/n_heading_scan and take the
>  9              smallest deviation admitting any speed
> 10          if still none: mark the leg INFEASIBLE and report it (S7 fired)
> 11          n_projected ← n_projected + 1
> 12      new speed made good ← projection of the new over-ground velocity onto the leg direction
> 13      new leg duration ← leg length / that ; shift every later waypoint in time
> 14      Δfuel ← [fuel_rate(V_new) − fuel_rate(V_cmd)] · leg duration        -- a DELTA
> 15  return the re-scheduled route and n_projected
> ```
>
> **Line 13 — later legs are then sampled at their shifted times**, so a projection early in
> the voyage correctly changes the weather the rest of the voyage sees.
>
> **What this deliberately does NOT do: move the waypoints.** The track was chosen by the
> sweep against bathymetry, land and traffic separation; re-routing it is the sweep's job. A
> projection that must change heading is recorded with its heading offset so the caller can
> decide whether to re-solve.
>
> **Line 14 takes a difference, and that is what makes it legitimate.** The added wave
> resistance that a bare powering model cannot see enters both terms and cancels to first
> order, so the correction is right even though neither absolute figure would be. Risk is left
> untouched: fabricating a risk model here would be worse than reporting the sweep's.
>
> **The cost of the whole D4 detour is bounded by `Thm 2.11` in its corrected LOCAL form
> (E6)**, never the global one:
> ```
> J_dwell − J_relax  ≤  L_x·v_max·τ_d·S_leg·(1 + L_v·Δt)   for  L_v·Δt ≪ 1     (E6.3)
> ```
> which for `τ_d = 300 s`, `Δt = 6 h`, `S_leg = 150 km` gives a gap **under 2 seconds**. The
> global bound `exp(L_v T)` is vacuous at voyage scale (`≈1.6×10⁵`); the operative global
> guarantee is `Cor 4.12`.

---

## 4.13 Alg 4.15 — localised front repair on forecast update

A new forecast arrives every 6 h; a voyage lasts days. Re-solving from cold discards work that
is still valid. This is the dynamic single-source shortest-path problem of
**Ramalingam & Reps (1996)**, specialised to the ordered-upwind front.

> **Alg 4.15 — localised front repair.**
>
> **Input.** The converged `T`, `parent` from a previous solve; the new field; a materiality
> threshold `δ_rel` (default 0.02, i.e. a 2 % change in `F` at any tabulated direction).
> **Output.** `T'`, `parent'` equal to what a **cold solve** on the new field would produce.
> **Invariant.** On termination, `T'` is the exact fixed point of the update family under the
> new metric.
> **Complexity.** `O(|R| · |NF| · C_ζ)` where `R` is the repair set. Measured target:
> `|R|/N < 0.2` for a 5 % field perturbation (`handbook/02 §S9`).
>
> ```
>  1  S ← { nodes y : max_u |F_new(y,u) − F_old(y,u)| / F_old(y,u) > δ_rel }
>  2  if |S| = 0: return (T, parent) unchanged
>  3  build the child lists by inverting `parent` (one O(N) pass)
>  4  R ← the set of nodes whose backpointer chain passes through S:
>  5      forward-traverse the backpointer forest from every node in S, collecting descendants
>  6  for y ∈ R:  T'[y] ← +∞ ;  parent'[y] ← −1 ;  status[y] ← FAR
>  7  for y ∉ R:  T'[y] ← T[y] ;  parent'[y] ← parent[y] ;  status[y] ← ACCEPTED
>  8  Q ← empty
>  9  -- (i) INCREASE seeds: re-derive every node of R from its non-affected support
> 10  for y ∈ R:
> 11      T̂ ← Alg 4.1(y) restricted to front edges with BOTH endpoints outside R
> 12      if T̂ < +∞:  T'[y] ← T̂ ;  Q.push(T̂, y) ;  status[y] ← CONSIDERED
> 13  -- (ii) DECREASE seeds: a cheapened cell can improve a node that never depended on it
> 14  for y with any stencil support inside S:
> 15      T̂ ← Alg 4.1(y) under F_new
> 16      if T̂ < T'[y] − τ_tie:
> 17          T'[y] ← T̂ ;  Q.push(T̂, y) ;  status[y] ← CONSIDERED ;  R ← R ∪ {y}
> 18  -- (iii) run the ordinary sweep, allowing nodes outside R to be lowered
> 19  run Alg 4.3 lines 4–13 from Q, under F_new, with the modification that a node
> 20      outside R which is improved is un-accepted, added to R, and pushed
> 21  return T', parent'
> ```
>
> **Correctness (complete).** Write `T*` for the cold-solve fixed point under `F_new`, and
> `T'` for the output.
>
> *Every value in `T'` is achievable.* Each assignment to `T'` is the result of `Alg 4.1`
> applied to values already in `T'`, i.e. it is the cost of a concatenation of admissible
> update rules starting from the source. Hence `T' ≥ T*` pointwise (no value undercuts the
> optimum).
>
> *Every node's optimal new value is reachable by the sweep.* Let `y` be any node and let
> `π*` be its optimal update chain under `F_new`, from the source. Two cases.
> - **`π*` avoids `S` entirely and every node of `π*` lies outside `R`.** Then `F_new = F_old`
>   on `π*` within tolerance and no node of `π*` had its chain through `S`, so `T'[z] = T[z]
>   = T*[z]` for every `z ∈ π*` by line 7 and by the optimality of `T` under `F_old`. In
>   particular `T'[y] = T*[y]`.
> - **`π*` meets `S`, or meets `R`.** Let `z` be the **last** node of `π*` whose value differs
>   from its old value, i.e. the last node at which the change is felt. Every node of `π*`
>   after `z` has `T' = T*` by the previous case applied to the suffix. The node `z` itself is
>   either in `R` (then line 11 or the sweep re-derives it, since its own support is either
>   outside `R` — line 11 — or itself in `R` and handled inductively in extraction order) or
>   outside `R` but improved by a cheapened support in `S` (then line 15 pushes it). Either
>   way `z` enters `Q` with a value `≤ T*[z]`, and thereafter the ordinary label-setting
>   argument of `Prop 4.9(d)` applies to the sub-problem seeded by `Q`: keys are extracted in
>   non-decreasing order, so `y` is finalised at `T*[y]`.
>
> *Both directions are necessary.* Seeds (i) alone catch only **increases** (a node whose old
> optimal chain used a cell that became more expensive). Seeds (ii) alone catch only
> **decreases**. Omitting (ii) is the classic dynamic-SSSP bug: values that should have gone
> down do not, silently, and the route is stale rather than wrong-looking. Omitting the
> "un-accept nodes outside `R` that improve" clause of line 20 has the same effect one hop
> further out. ∎
>
> **The dependency closure must be tight, and it is measurable.** `handbook/02 §S9`: if
> repair is as slow as a cold solve, the closure is too conservative — most likely you are
> re-opening every node with `T > t_now` rather than only those whose backpointer chain passes
> through a materially changed cell. **Report `|R|/N`.** For a 5 % perturbation it should be
> well under `0.2`; near `1.0` the closure is degenerate.
>
> **Interaction with the reduction.** A new forecast may change `w`. If the re-estimated `w`
> from `Alg 4.4` differs from the incumbent by more than a threshold (normative default
> `0.25 m/s`, one quarter of the coarse-search resolution of round 1), **the co-moving grid
> changes and repair is invalid** — every node's `y` coordinate has moved. Do a cold solve.
> Repair applies only while `w` is held fixed. Getting this wrong is a silent-landfall bug of
> exactly the R1 kind.

---

## 4.14 Alg 4.16 — the full algorithm

Every call is resolved to a section of this file or to a named object in another block.

> **Alg 4.16 — KAIROS.**
>
> **Input.**
> - `vessel` — the five primitives of CONTRACT §4 bound to a hull;
> - `field` — forecast stack `E(x,t)`, valid on `[t₀⁻, t₀⁻ + H_fc]`;
> - `x_A`, `x_B` — departure and destination, radians;
> - `t₀` — departure time, seconds since epoch;
> - `Δ` — grid step; `ρ_c = 8`; `ε`; `k`; `Υ_heap = 12`; `δ_trigger = 0.05`; `δ_safe = 0.05`.
>
> **Output.** A route `(ϕ_i, λ_i, t_i, θ_i, q_i)`, its objective vector, the certificate gap
> of `Cor 4.12`, and the diagnostic block of §4.15.
>
> **Global invariants.**
> - **G1** Every value ever written to `T` is the cost of a genuine admissible trajectory, so
>   `T ≥ T*` pointwise at all times, and any returned route is feasible.
> - **G2** `Alg 4.3`'s extraction keys are non-decreasing (`Prop 4.9c`), so no node is
>   reopened and the solve is single-pass (`Prop 4.9d`) — **unconditionally**, because
>   `Thm C.1(b)` makes `L_t ≡ 0` and (E4.1) vacuous.
> - **G3** The coarse bound is used only to prune and to certify (4.28), never to reorder, so
>   G2 survives `Prop 4.11(c)`'s failure of fine consistency.
> - **G4** Every reported number is either measured at runtime or derived in this file; none
>   is asserted.
>
> **Complexity.** `O(N·|NF|·C_ζ)` update work, `O(N)` queue work (`Prop 4.9`), `O(N)`
> interception (`Alg 4.6`), `O(N/ρ_c²·log)` coarse solve, `O(max_iters·n_steps)` polish. See
> `Thm 7.3` for the full account with constants.
>
> ```
>  1  ── STEP 0: geometry and domain ──────────────────────────────────────────
>  2  σ_min^w, V_max, |c|_max ← scan the field over the intended domain
>  3  t_max ← 1.25 · F_max^w·|x_B − x_A| / (1 − |w_guess|/σ_min^w)         (4.15)
>  4       (bootstrap with w_guess = 0, then recompute after line 8)
>  5  if t_max > H_fc: t_max ← H_fc ; log HORIZON-LIMITED
>  6
>  7  ── STEP 1: choose w ───────────────────────────────────────────────── §4.4
>  8  (w, L_t^0, L_t^w) ← Alg 4.4(field, sigma, samples, s₀=4, n=9, n_r=3)
>  9  report w, L_t^0, L_t^w, ratio; report max/p99/median in BOTH frames
> 10  assert |w| < σ_min^w                     -- A2; if it fails, STOP and say so (§4.7.1)
> 11  if |w| is on the boundary of the initial box: log A2-AT-RISK
> 12  recompute t_max from (4.15) with the chosen w
> 13
> 14  ── STEP 2: co-moving field and grid ───────────────────────────────── §4.5
> 15  (dilate_E, dilate_N) ← (|w_E|·t_max, |w_N|·t_max)                    (4.14)  [R1]
> 16  grid ← lattice over the ground domain EXTENDED by (dilate_E, dilate_N)
> 17           opposite to each component of w;  index by (4.2)
> 18  c_eff(y) ← c₀(y) − w                                                 (4.10)
> 19  for each node y: check |c_eff(y)| < V_max(y)                         (4.12)
> 20      where it fails, set the E1 reachable cone α_reach = arcsin(V_max/|c_eff|)  (4.13)
> 21      and mark every direction outside it as F = +∞ ;  count these cells
> 22  build the support table A13 (D2, n_θ = 72) — ONE slice, not n_t       (4.5)
> 23  Υ_loc ← σ_max/σ_min per node (A8) ;  r(y) ← Alg 4.2 per node (A9)
> 24
> 25  ── STEP 3: the stationary solve ───────────────────────────────────── §4.6
> 26  Q ← BucketQueue(width Δ_min of (4.17), n_buckets of (4.23))
> 27       if max_y Υ_loc(y) > Υ_heap:  Q ← HeapQueue()                    (4.22)  [E2]
> 28  (T, parent, parent_zeta, parent_edge) ← Alg 4.3(grid, s = nearest water node to x_A,
> 29                                                  F_w, Q)
> 30       -- Alg 4.1 inside, with the ℓ_min exclusion (4.16)              [E3]
> 31       -- NO causality condition is evaluated anywhere in this step    [Thm C.1b]
> 32  assert Q.monotone_violations = 0
> 33
> 34  ── STEP 4: interception ───────────────────────────────────────────── §4.7
> 35  (n*, d*, t*) ← Alg 4.6(T, grid, w, x_B)                              [R2]
> 36  if n* = −1 or d* > √2·h:  report FAILURE (R1 undersized, or A2 fails)
> 37  optionally bisect g(t) on [0, t_max] for a reported t*; log any disagreement
> 38
> 39  ── STEP 5: route recovery ─────────────────────────────────────────── §4.7
> 40  route ← Alg 4.8(parent, parent_zeta, parent_edge, T, n*, w)          (C.5)
> 41
> 42  ── STEP 6: residual corrector ─────────────────────────────────────── §4.9
> 43  R(x,t) ← E(x,t) − E₀(x − w t)                                        (C.8)
> 44  L_t^R ← temporal Lipschitz constant of R, per cell
> 45  if max_y r(y)·L_t^R(y) > δ_trigger:                                  (4.25)
> 46      route ← Alg 4.9(E, route, ρ_tube = 8h, guard on L_t^R, wait relaxation E5.1)
> 47      report count_relaxed, count_horizon_truncated
> 48
> 49  ── STEP 7: multi-objective, certificate, polish ────────── §4.10–§4.12
> 50  if k > 1:
> 51      re-run STEP 3 with LabelSets in place of scalars (§4.10, value bucketing E7.1)
> 52      report Λ_mean, Λ_peak                                            (E7.2)
> 53  T_low ← Alg 4.10(grid, ρ_c, metric, x_B)                             [D5]
> 54  gap ← (J − T_low[I(x_A)]) / T_low[I(x_A)]                            (4.29)  [Cor 4.12]
> 55  (polished, converged, iters) ← Alg 4.13(field, x_A, x_B, V_s, t₀,
> 56                                           θ_guess = heading of route leg 1)
> 57  if not converged:  route stays as the grid route ;  flag CUT-LOCUS or NON-CONVERGED
> 58  else:  route ← polished ;  re-score it against the metric
> 59  (route, n_projected) ← Alg 4.14(route, vessel, field)                [D4 repair]
> 60
> 61  ── STEP 8: report ─────────────────────────────────────────────────── §4.15
> 62  emit the route, the objective vector, gap, and the full diagnostic block
> 63
> 64  ── On a new forecast ──────────────────────────────────────────────── §4.13
> 65  w' ← Alg 4.4 on the new stack
> 66  if |w' − w| > 0.25 m/s:  cold solve from line 7
> 67  else:                    (T, parent) ← Alg 4.15(T, parent, new field, δ_rel = 0.02)
> ```
>
> **Line 51 is a genuine re-run, not an in-place upgrade.** The time-only solve uses
> `sigma_max` and never materialises the throttle family; the Pareto solve needs `legs()`,
> the full one-parameter family per direction (D1). Wiring the time-only fast path into the
> Pareto solver gives every label `q = 1` and collapses the front to a single route — which is
> `handbook/02 §S5`, second cause, and its discriminating test is to print `|legs()|` for a
> mid-ocean cell: it should be 2–4 after pruning, and if it is always 1, that is the bug.
>
> **Line 36 fails loudly on purpose.** Both R1 and a failed A2 present as "no node maps near
> the target". They are distinguished by the *whole-grid* minimum miss (§4.5.2): large
> everywhere ⟹ R1; small somewhere but the selected node worse ⟹ R2; `2|w|t*` away ⟹ sign
> convention.

---

## 4.15 Instrumentation — build it in before anything goes wrong

Every counter below is part of the algorithm's contract, not an optional extra. Printing them
at the end of every run costs nothing and is the difference between "it works" and "we know
it works". Sources: `handbook/01 §G5`, `handbook/02` instrumentation table.

| Counter | Section | Must be | Why |
|---|---|---|---|
| `w`, `L_t^0`, `L_t^w`, and max/p99/median in **both** frames | §4.4 | reported | reporting only the max oversells the reduction; the median regresses |
| `|w|` vs `σ_min^w` (the A2 margin) | §4.5.1 | `< 1` | A2 is the hypothesis of `Thm C.1(c)` |
| cells failing `|c_eff| < V_max` (E1 cone active) | §4.5.1 | counted | these cells are outside `Prop 4.7`'s guarantee |
| `dilate_E`, `dilate_N`, and node-count inflation | §4.5.2 | reported | R1 is the silent-failure requirement |
| whole-grid minimum landfall miss `d*` | §4.7.1 | `< √2 h` | measured 11.2 km against a 39.3 km diagonal |
| distribution of the inner minimiser's `ζ*` | §4.6.3 | not endpoint-pinned | bimodal at `{0,1}` ⟹ the `ζ` search is broken (`§S3`) |
| stencil radius histogram, and count at `r_cap` | §4.6.5 | not saturated | saturation ⟹ the adaptive radius is not adapting |
| `max_x |NF(x)|` vs `C_AF·r_max/h` | §4.6.4 | comparable | detects multi-sheet fronts in archipelagos |
| `monotone_violations` | §4.8 | **0** | non-zero ⟹ `T` is not the fixed point |
| `overflow_events`, `fell_back` | §4.8 | reported | tells you whether the bucket queue is actually being used |
| `Υ_max` vs `Υ_heap` | §4.8.3 | reported | the E2 trigger, per solve |
| metric evaluations and support-table hit rate | §4.6.3 | reported | tells you whether D2 is working |
| `Λ` mean and peak | §4.10 | reported | the measured `Λ` in `Thm 5.3`'s bound |
| cells needing the wait relaxation; `count_horizon_truncated` | §4.9 | reported | the FIFO honesty metric; E5 requires the truncation count |
| `max_x r(x)·L_t^R` | §4.9 | `< 1` where not relaxed | E4.1 with the **correct** length scale |
| nodes expanded vs nodes in domain | §4.11 | reported | tells you the bound is focusing the search |
| certificate gap `(J − T_low)/T_low` | §4.11.4 | reported | the headline number |
| `|R|/N` on repair | §4.13 | `< 0.2` at 5 % perturbation | detects a degenerate closure |
| Zermelo `max |dθ/dt|` in uniform flow | §4.12.1 | `< 10⁻¹⁴` | golden test G4 |
| polish iterations, cut-locus flags, `n_projected` | §4.12 | reported | cut loci are a feature to surface |

**Acceptance for an implementation of §4** — reproduce all of:

| Test | Expected | Source |
|---|---|---|
| G2 golden vectors T1–T8 | 12 significant figures | `handbook/01 §G2` |
| T7 (`λ < 0`) and T8 (`|c_⊥| ≥ V_s`) reachable in the suite | `F = +∞`, not an exception, not `−1.25` | `handbook/01 §G2` |
| G4 uniform-flow arrivals | 17.751 425 h east / 27.094 280 h west; ratio `= Υ = 1.526 315 789 5` to all printed digits | `handbook/01 §G4` |
| C.1 bijection residual | `≤ 10⁻¹³ m/s` (measured `9.77×10⁻¹⁴`) | `CORE-THEOREM §4` |
| co-moving `V_req` excess | `≤ 10⁻¹³ m/s` (measured `2.84×10⁻¹⁴`) vs ground-frame `6.7×10⁻³` | `CORE-THEOREM §4` |
| co-moving `L_t` on a purely advected field | **exactly 0.0** | Test 8.10 Regime A |
| landfall miss, reference voyage | `11.2 km` (`< √2 h = 39.3 km`) | `CORE-THEOREM §8.2` |
| arrival, reference voyage | `139.9963 h`, within 0.860 % of the ground-frame Dijkstra | `CORE-THEOREM §8.2` |
| `n_buckets`, golden field | 5, by (4.24) | this file |
| refinement study at 1.0°/0.5°/0.25° | error must **decrease**; report the observed order `p` | `handbook/01 §G5` |

> **The refinement study will plateau at `~1 %` if the `ζ`-continuum is not implemented, and
> the routes will still look right.** Measured floor over `h = 24, 16, 12, 8, 6, 4, 3 km`:
> `0.36, 0.15, 0.79, 0.92, 0.17, 0.98, 0.58 %`, non-monotone and non-converging
> (`CORE-THEOREM §4`). That is the fixed-stencil metrication error, it does not vanish as
> `h → 0`, and it is the single most important failure to catch.

---

## 4.16 Corrections this file makes to normative documents, and open items

Recorded because a spec that silently diverges from its own contract is worse than one that
says where it diverges.

| # | Document | Statement there | This file | Status |
|---|---|---|---|---|
| 1 | `CONTRACT D3` | `Δ_min = h·F_min`; fall back to a heap when `F_min` is not bounded away from 0 | `Δ_min = c_geo·h·F_min` with `c_geo = 1/√2` and the `ℓ_min` exclusion (§4.6.2); heap fallback on `Υ_loc > Υ_heap` (§4.8.3) | **Superseded by ERRATA E3 and E2.** Not a new divergence; recorded for the implementer who reads only the CONTRACT. |
| 2 | `07-complexity.md §7.2.1` note 2, `03-causality.md §3.4.2` | `r_max = h·max_x Υ_loc` | `r(x) = √2·h·max_{B(x,r)} Υ_loc` (`Prop 4.7`, Step 2 of the proof) | **New correction.** The witnessing unaccepted node is a cell *corner*, so the cell diagonal, not the spacing, is the correct length. The change only enlarges the stencil; every conclusion of `07` holds under `Υ ← √2Υ`, at a `2×` cost in `|NF(x)|`. |
| 3 | `CONTRACT §2` "Prop 4.11 Admissibility **and consistency** of the optimistic coarse heuristic" | implies both hold | admissibility holds (proved); **consistency of the fine lift fails**, by a factor `ρ_c/√2` (`Prop 4.11c`, proved) | **Weakened, with proof of the failure.** Forced normative consequence (4.28): the coarse bound prunes and certifies but never reorders, which preserves the single-pass property. |
| 4 | assignment brief for `Alg 4.13` | use the variational equation for the Newton derivative | variational equation given explicitly (4.31)–(4.35) **and** normatively restricted to `C²` fields; a central difference is normative on `C⁰` trilinear forecasts | **Weakened, with reason.** (4.33) needs second derivatives of the current, which are `0` inside a trilinear cell and a delta across a face. |
| 5 | `CORE-THEOREM §8` pipeline line 1 | `w ← phase-correlate consecutive forecast frames` | `w ← argmin` of the residual causality constant, `Alg 4.4` | **Internal inconsistency in `CORE-THEOREM.md`.** §7 of the same document states plainly that phase correlation was tried and failed (returned `(−0.74, 0)` against a true `(2.0, 0.5)`) and is *replaced* by (C.10). §8's pseudocode was not updated. §4.4 implements §7, which is unambiguously the intended method; **`CORE-THEOREM §8` line 1 should be amended.** |
| 6 | `src/kairos/bucketqueue.py` module docstring | "every edge costs at least `Delta_min = h * F_min`"; heap fallback when `F_min` is not bounded away from zero | E3 and E2 as above | **The reference implementation is stale against ERRATA here.** The queue's *mechanism* is correct; its stated licence and its fallback trigger are the pre-errata ones. Fix before publication. |
| 7 | `src/kairos/comoving.py` `stationary_sweep` | 16-neighbour node-to-node Dijkstra | `Alg 4.1` with the continuum `ζ` | **Known gap, already documented in the source.** The reduction is orthogonal to the update; the 16-neighbour sweep carries the ~1 % metrication floor of `CORE-THEOREM §4`. Upgrading the update is the next increment and does not affect any claim of `Thm C.1`. |

**Open items — stated, not hidden.**

1. **`Λ` in the co-moving frame is unverified.** §4.10 argues that under A1 all objectives
   become stationary, so the multi-objective solve inherits the licence. No multi-objective
   co-moving run has been reported. Flagged in §4.10.
2. **The f32 support table (§4.2.3) has no measured accuracy cost.** Do not claim it is free.
3. **The `Alg 4.4` sample budget reconciling with the measured 0.05 s is inferred**, not
   measured (§4.4.4).
4. **`δ_trigger`, `δ_safe`, `δ_rel`, `τ_tie`, `ρ_tube`** are policy constants, each flagged as
   such where it appears. `c_geo`, `c_adm`, `Υ_heap`, `n_buckets`, `ℓ_min`, `r(x)`, `t_max`,
   `n_iter` are **derived** in this file.
5. **Spatially varying `w(x)`** gives a *warped* reduction — a flow map `y = Φ_t^{-1}(x)`
   rather than a rigid shift, with the Jacobian entering the metric. Exact for constant `w`,
   approximate otherwise. **Not implemented**; noted as the obvious extension
   (`CORE-THEOREM §7`).
6. **Test 8.10 on a real operational forecast stack** (as opposed to the three constructed
   regimes) is still to run. Contribution 3 of `CORE-THEOREM §9` rests on the constructed
   regimes until then.

---

## 4.17 Reading order for an implementer

1. §4.2 — build the lattice and allocate A1–A12. Verify `h`, `N` and the byte totals against
   the reference configuration before writing any solver code.
2. `handbook/01 §G1–G3` — get `σ` and `F` right, including T7 and T8. Nothing downstream can
   be debugged until these pass to 12 figures.
3. §4.5 — the co-moving field is one line (`c ← c₀ − w`) plus R1. Do R1 first; it is the
   requirement that fails silently.
4. §4.6 — `Alg 4.1`, `Alg 4.2`, `Alg 4.3`, with a heap. Do **not** implement the bucket queue
   yet. Verify against G4 (uniform flow: constant heading, zero turns, arrival ratio `= Υ`).
5. §4.7 — `Alg 4.6` and `Alg 4.8`. Verify the landfall miss against the grid diagonal.
6. §4.8 — swap the heap for the bucket queue. `monotone_violations` must stay 0.
7. §4.11 — the coarse bound and the certificate. Verify by disabling it: the answer must not
   change (bounding mode does not alter the optimum, only the work).
8. §4.12, §4.13, §4.10 — polish, repair, multi-objective, in that order.

Steps 1–5 give a correct, licensed, certified time-optimal router. Everything after is
accuracy, speed and objectives.

