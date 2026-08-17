# §5 — Multi-objective labels

**Block owned:** §5, Thm 5.x, Prop 5.x, Lemma 5.x, Eq (5.x).
**Normative sources:** `CORE-THEOREM.md` (Thm C.1), `ERRATA.md` (E7, E9, E11), `CONTRACT.md`
(D1, D7, §1 symbol table) — in that precedence order.

---

## 5.0 Scope, and what is not claimed here

This section is **supporting apparatus**. KAIROS is defined by the Co-Moving Reduction
(Thm C.1): in coordinates `y = x − w t` the routing problem is exactly stationary, the
causality/FIFO obstruction dissolves, and the solve is one monotone pass plus a scalar
interception. Everything in §5 rides on top of that pass. It is not the contribution.

**Prior art, stated first because ERRATA E11 is blunt about it.**

| Result | Owner | What they did |
|---|---|---|
| Multi-objective optimal control by fast-marching-type semi-Lagrangian front propagation | **Kumar & Vladimirsky (2010)**, *J. Sci. Comput.* **43**, 274–298 | vector-valued information carried through a minimisation-based update on a continuum front. This is the idea §5 uses. It is theirs. |
| Multi-objective level-set reachability | **Mitchell & Sastry (2003)** | the same idea in a level-set formulation |
| Value-bucketed FPTAS for multi-objective shortest paths | **Tsaggouris & Zaroliagis (2009)**, *Theory Comput. Syst.* **45** | the ε-scaling on the accumulated objective **value** that E7 mandates. Eq (5.21) is their construction. |
| Exact multi-objective label-setting, lexicographic pop order | **Martins (1984)** | the correctness argument Prop 5.4(iii) reproduces |
| Earlier FPTAS for MOSP | **Warburton (1987)**; **Papadimitriou & Yannakakis (2000)** | the ε-approximate-front concept itself |
| Bucket (Dial) queue discipline | **Dial (1969)** | the O(1) amortised pop that §4 uses, corrected by ERRATA E3 |
| Convergence of monotone schemes | **Barles & Souganidis (1991)** | invoked in §7, not here |

**The claim that survives, per ERRATA E11**, is narrow and is exactly three things:

1. **Bottleneck (`max`-accumulated) objectives carried through the front propagation** —
   the criterion a master actually uses, "how bad did the worst moment get". We have not
   found it treated in the front-propagation setting. Prop 5.5 proves no weighted sum can
   express it; Prop 5.8 proves it is *exactly* bucketable, which additive objectives are
   not, and that asymmetry is the technical content.
2. **Throttle families** (D1): each direction carries a one-parameter family of
   `(time, fuel, risk)` triples rather than a scalar (§5.3).
3. The **ε-bucketed label set on a continuum ordered-upwind front**, with credit to
   Tsaggouris & Zaroliagis (2009) for the value-bucketing itself.

And one thing that §5 does **not** claim, which §5.4.5 spends a page on: the uniform,
path-length-independent `(1+ε)` guarantee asserted in ERRATA E7 is **proved here for the
label count (Thm 5.3) and for the per-node bound (Thm 5.2b), and disproved as stated for
the per-path bound (Remark 5.11, with an explicit 4-node counterexample verified against the
reference implementation).** The correct per-path statement is Thm 5.2(c). Saying so is
cheaper than being told.

### 5.0.1 Objective indexing (a conflict between the normative files, resolved)

`CONTRACT.md` §1 indexes objectives `1…4` with index 1 = time. `ERRATA` E7 prose says
"objective **0** (time) is never bucketed" while E7.1 writes `i = 2 … k`. `src/kairos/types.py`
and `labels.py` use 0-based with index 0 = time.

**Resolution, normative for this file:** objectives are indexed `j = 0 … k−1`; `j = 0` is
arrival time. The `CONTRACT` table's index `i` maps as `i = j + 1`. E7.1's range `i = 2…k`
is the same set as `j = 1…k−1`. No other file needs to change; this is a labelling conflict,
not a mathematical one.

| `j` | Symbol | Name | Accumulation | Bucketed? | Units |
|---|---|---|---|---|---|
| 0 | `J_T` | arrival time | `+` | **never** (Eq 5.22) | s |
| 1 | `J_G` | fuel mass burnt | `+` | yes, geometric (5.21a) | kg |
| 2 | `J_R` | risk | `+` **or** `max` | yes; grid depends on accumulation (5.21b) | — or 1 |
| 3 | `J_C` | comfort / MSI | `+` | yes, geometric | — |

`k` = number of active objectives; `k = 3` default. `Λ` = labels retained per node.

### 5.0.2 Notation

`C := [0, +∞]^k` is the **cost space**, ordered componentwise:
`a ≤ b ⟺ a_j ≤ b_j ∀j`. This is a partial order, not a total one — the whole section
exists because of that. `a ≺ b` ("`a` dominates `b`") means `a ≤ b` and `a ≠ b`.
An **antichain** is a set no two of whose members are comparable. For `A ⊆ C`,
`PMin(A) := { a ∈ A : ∄ b ∈ A, b ≺ a }` is its **Pareto front**.

`𝒫(x_A → v)` is the set of admissible routes from the departure point to node `v`, and
`𝒥(v) := { J(P) : P ∈ 𝒫(x_A → v) } ⊆ C` its **attainable set**. `D` denotes the number of
legs in a route; for a 5 000 km voyage on a 28 km grid, `D ≈ 180` (ERRATA E7).

---

## 5.1 Why scalarisation fails

Scalarisation — pick weights `λ ≥ 0`, minimise `⟨λ, J⟩` with a single-objective solve,
sweep `λ` over a grid, collect the answers — is what most operational routing systems do.
It is cheap, it reuses the scalar machinery unchanged, and it is **provably incapable of
returning a large and operationally important part of the Pareto front**. This subsection
proves that and then exhibits a routing instance where the entire middle lane is invisible.

### 5.1.1 The supported-point theorem

> **Definition (supported and convex-dominated points).** Let `𝒥 ⊆ C` be attainable.
> A point `p ∈ 𝒥` is **supported** if there exists `λ ∈ ℝ^k_{≥0}`, `λ ≠ 0`, with
> ```
> ⟨λ, p⟩  =  min_{J ∈ 𝒥} ⟨λ, J⟩ .                                       (5.1)
> ```
> `p` is **convex-dominated** if there are finitely many `J^(1) … J^(m) ∈ 𝒥` and weights
> `α_i ≥ 0`, `Σ α_i = 1`, with
> ```
> z := Σ_i α_i J^(i)  ≤  p     componentwise, and     z ≠ p .            (5.2)
> ```

> ### Prop 5.1 (scalarisation reaches exactly the supported points)
> Let `𝒥 ⊆ C` be non-empty.
>
> **(a)** For every `λ ≥ 0`, `inf_{𝒥} ⟨λ,·⟩ = inf_{conv 𝒥} ⟨λ,·⟩`. Weighted-sum
> minimisation cannot distinguish `𝒥` from its convex hull.
>
> **(b)** If `p` is convex-dominated then `p` is **not** a minimiser of `⟨λ,·⟩` for any
> `λ > 0` (all components strictly positive). If in addition `p` is not a minimiser for any
> `λ ≥ 0` with a zero component, then no weight vector whatsoever returns `p`.
>
> **(c)** If `λ > 0` then every minimiser of `⟨λ,·⟩` over `𝒥` is Pareto-optimal.
>
> **(d)** If `λ ≥ 0` has a zero component, a minimiser of `⟨λ,·⟩` need only be *weakly*
> Pareto-optimal: it may be dominated. A solver that returns "a minimiser" can therefore
> return a route that is strictly worse than another attainable route.

**Proof.**

**(a)** `𝒥 ⊆ conv 𝒥` gives `inf_{𝒥} ≥ inf_{conv 𝒥}`. Conversely let `z ∈ conv 𝒥`, so
`z = Σ_{i=1}^m α_i J^(i)` with `α_i ≥ 0`, `Σα_i = 1`, `J^(i) ∈ 𝒥`. Then
```
⟨λ, z⟩ = Σ_i α_i ⟨λ, J^(i)⟩ ≥ (Σ_i α_i) · min_i ⟨λ, J^(i)⟩ = min_i ⟨λ, J^(i)⟩ ≥ inf_{𝒥} ⟨λ,·⟩ .
```
Taking the infimum over `z ∈ conv 𝒥` gives `inf_{conv 𝒥} ≥ inf_{𝒥}`. Hence equality. ∎

**(b)** Let `z = Σ α_i J^(i) ≤ p` with `z ≠ p`, and let `λ > 0`. Since `z ≤ p` and `z ≠ p`,
there is at least one index `j₀` with `z_{j₀} < p_{j₀}`, and `z_j ≤ p_j` for all `j`.
Because every `λ_j > 0`,
```
⟨λ, z⟩ − ⟨λ, p⟩ = Σ_j λ_j (z_j − p_j) ≤ λ_{j₀}(z_{j₀} − p_{j₀}) < 0 .        (5.3)
```
By the computation in (a), `min_i ⟨λ, J^(i)⟩ ≤ ⟨λ, z⟩ < ⟨λ, p⟩`. So some attainable
`J^(i)` beats `p` strictly, and `p` is not a minimiser. The second sentence is the
definition of "no weight vector returns `p`" once the `λ > 0` case is excluded. ∎

**(c)** Let `λ > 0` and let `p` minimise `⟨λ,·⟩`. Suppose `q ∈ 𝒥` with `q ≺ p`. Then
`q_j ≤ p_j` for all `j` with strict inequality somewhere, so by the same computation as
(5.3), `⟨λ, q⟩ < ⟨λ, p⟩`, contradicting minimality. ∎

**(d)** Take `k = 2`, `λ = (1, 0)`, `𝒥 = {(1,1), (1,2)}`. Both attain `⟨λ,·⟩ = 1`, so
`(1,2)` is a minimiser, and `(1,1) ≺ (1,2)`. ∎

> **Remark 5.1a (what breaks without each hypothesis).**
> * Drop **`λ > 0`** in (b)/(c) and you get (d): dominated routes come back.
> * Drop **convexity of the hull operation** — i.e. work with `𝒥` finite, which it is —
>   and nothing breaks; (a) is exactly the statement that finiteness does not help. The
>   convex hull of a finite attainable set has non-attainable faces, and scalarisation
>   sees the faces.
> * **The hull is fictional.** A point `z = Σ α_i J^(i)` with `0 < α_i < 1` is not a route.
>   It is the cost of a *randomised policy* — sail lane `i` with probability `α_i`. That is
>   a meaningful object for a fleet over a year and a meaningless one for this ship on this
>   passage. For a **bottleneck** objective it is worse than meaningless: the expected
>   bottleneck of a lottery is `Σ α_i r_i`, but the bottleneck actually experienced is
>   `r_i` for whichever lane is drawn. §5.1.2 exhibits a chord point whose "risk 0.30" is
>   realised as risk 0.62 on 40.7 % of voyages. Scalarisation is trading against a number
>   that never happens.

### 5.1.2 An explicit routing instance with an invisible middle lane

Everything below is computed from the **default Handymax of `types.py`** and the Randers
closed form of `handbook/01-golden-vectors.md` G2. No number is invented.

**Vessel.** `V_ref = 14 kt = 7.202 222 221 6 m/s`, `P_ref = 8.2 MW`, `P_MCR = 11.0 MW`,
Admiralty exponent `n = 3`, `SFOC(q) = 175·10⁻⁹ (1 + 0.28 ((q−0.75)/0.75)²) kg/(W·s)`.
Hence

```
V(q)     = V_ref · ( q · P_MCR / P_ref )^{1/3}                            (5.4)
ṁ(q)     = SFOC(q) · q · P_MCR                        [kg/s]              (5.5)
```

| `q` | `V(q)` [m/s] | `ṁ(q)` [kg/s] | `ṁ/V` [kg/m] |
|---|---|---|---|
| 0.35 | 5.597 775 | 0.727 410 44 | 0.129 946 |
| 0.50 | 6.304 483 | 0.992 444 44 | 0.157 419 |
| 0.75 | 7.216 831 | 1.443 750 00 | 0.200 053 |
| 1.00 | 7.943 151 | 1.984 888 89 | 0.249 887 |

*(Check one by hand: `q=1` gives `(11/8.2)^{1/3} = 1.102 874`, times `7.202 222` is
`7.943 151`; `d = (1−0.75)/0.75 = 1/3`, `0.28/9 = 0.031 111`, `SFOC = 180.444 4 ng/(W·s)`,
times `11 MW` is `1.984 889 kg/s`.)*

**Geography.** Three lanes from `x_A` to `x_B` around one weather system. Each lane is
characterised by its length `D`, a uniform along-track drift `c_∥` (no cross-track
component, so G2 gives `σ = V + c_∥` exactly), and a constant risk level.

| Lane | meaning | `D` [km] | `c_∥` [m/s] | risk level |
|---|---|---|---|---|
| **S** | south — cuts through the system's fast quadrant, short, current helps, dangerous | 2 900 | **+0.90** | **0.62** |
| **M** | middle — threads the gap, longer, slight set against, moderate | 3 550 | **−0.10** | **0.30** |
| **N** | north — wide detour clear of the system, longest, no help, safe | 3 700 | **0.00** | **0.08** |

**The attainable set.** `t = D/(V(q)+c_∥)`, `fuel = ṁ(q)·t`, `risk = ` the lane level
(bottleneck accumulation, constant along a lane). Twelve routes, `3 lanes × 4 throttles`:

| id | lane | `q` | `σ` [m/s] | time [h] | fuel [t] | risk |
|---|---|---|---|---|---|---|
| S1 | S | 1.00 | 8.843 15 | **91.094** | 650.92 | 0.62 |
| S2 | S | 0.75 | 8.116 83 | 99.245 | 515.83 | 0.62 |
| S3 | S | 0.50 | 7.204 48 | 111.813 | 399.49 | 0.62 |
| S4 | S | 0.35 | 6.497 78 | 123.974 | **324.65** | 0.62 |
| **M1** | M | 1.00 | 7.843 15 | 125.729 | 898.41 | 0.30 |
| **M2** | M | 0.75 | 7.116 83 | **138.560** | **720.17** | **0.30** |
| **M3** | M | 0.50 | 6.204 48 | 158.935 | 567.84 | 0.30 |
| **M4** | M | 0.35 | 5.497 78 | 179.365 | 469.70 | 0.30 |
| N1 | N | 1.00 | 7.943 15 | 129.392 | 924.58 | **0.08** |
| N2 | N | 0.75 | 7.216 83 | 142.414 | 740.20 | 0.08 |
| N3 | N | 0.50 | 6.304 48 | 163.023 | 582.45 | 0.08 |
| N4 | N | 0.35 | 5.597 78 | 183.605 | 480.80 | 0.08 |

> **Fact 5.1b.** In this instance:
> **(i)** all twelve routes are Pareto-optimal;
> **(ii)** all four **M** routes are convex-dominated, hence invisible to every weight
> vector `λ ≥ 0`;
> **(iii)** the eight **S** and **N** routes are supported, so a weight sweep returns
> exactly `8/12` of the front and **never** offers the operator any middle-lane option.

**Proof of (i).** Three cases, and dominance requires being no worse on **all** of time,
fuel and risk.

*Within a lane.* Risk is constant; time strictly decreases and fuel strictly increases with
`q`. No two are comparable.

*Any **S** route versus any **M** or **N** route.* Every **S** route has risk `0.62`,
strictly the worst in the instance, so no **S** route can dominate anything outside lane
**S**. Conversely, for an **M** or **N** route to dominate an **S** route it must be no
worse in time; the fastest non-**S** route is M1 at `125.729 h`, and the only **S** route
slower than that is S4 at `123.974 h` — which is faster, so no **M** or **N** route is
faster than *any* **S** route. Dominance in either direction is impossible.

*Lane **M** versus lane **N**.* `Mi` beats `Ni` in both time and fuel and loses on risk, so
each such pair is incomparable: M1 `125.729/898.41` vs N1 `129.392/924.58`; M2
`138.560/720.17` vs N2 `142.414/740.20`; M3 `158.935/567.84` vs N3 `163.023/582.45`; M4
`179.365/469.70` vs N4 `183.605/480.80`. For the off-diagonal pairs `Mi` vs `Nj`, `i ≠ j`:
if `j < i` then `Nj` is faster than `Mi` but dearer in fuel (e.g. N1 `129.392/924.58` vs M3
`158.935/567.84`), and if `j > i` then `Nj` is slower and cheaper (N4 `183.605/480.80` vs M2
`138.560/720.17`) — in both cases the pair splits on time versus fuel, so neither dominates
regardless of risk. Exhaustively: all 66 unordered pairs are incomparable. ∎

**Proof of (ii).** Set `α := 0.22/0.54 = 0.407 407 407 4`, so that
`α·0.62 + (1−α)·0.08 = 0.300 000` exactly — the convex combination matches lane **M**'s
risk. Then, with `z(s,n) := α·s + (1−α)·n`:

| dent point `p` | witness `z` | `z` time [h] | `z` fuel [t] | `z` risk |
|---|---|---|---|---|
| M1 (125.729, 898.41, 0.30) | `z(S1,N1)` | **113.789** | **813.09** | 0.300 |
| M2 (138.560, 720.17, 0.30) | `z(S2,N2)` | **124.827** | **648.79** | 0.300 |
| M3 (158.935, 567.84, 0.30) | `z(S2,N3)` | **137.040** | **555.31** | 0.300 |
| M4 (179.365, 469.70, 0.30) | `z(S4,N4)` | **159.311** | **417.18** | 0.300 |

Each `z` is `≤ p` componentwise with strict inequality in both time and fuel, which is
(5.2). By Prop 5.1(b) no `λ > 0` returns any `Mi`. For `λ ≥ 0` with a zero component:
`λ = (1,0,0)` selects S1 (least time, 91.094 h); `λ = (0,1,0)` selects S4 (least fuel,
324.65 t); `λ = (0,0,1)` selects the **N** lane (least risk, 0.08). In each case the
minimiser set excludes lane **M** entirely, because on the axis with the surviving weight
lane **M** is strictly beaten. Combining, for **every** `λ ≥ 0`, `λ ≠ 0`:
`min_{𝒥}⟨λ,·⟩ < ⟨λ, Mi⟩` unless `λ_T = λ_G = 0`, and in that residual case lane **N**
strictly wins. ∎

**Proof of (iii).** Lane **S** is supported: put `λ_R = 0`. Lane **S** attains both the
global minimum time (S1) and the global minimum fuel (S4), and every **M** or **N** point is
worse than some **S** point in both remaining coordinates, so the `(time, fuel)` lower hull
of all twelve points is the lane-**S** curve. That curve is strictly convex — its three
chord slopes are `−16.57`, `−9.26`, `−6.15` t/h, strictly increasing — so each of S1…S4 is
the unique minimiser of `λ_T·t + λ_G·f` for an open interval of ratios `λ_T/λ_G`
(respectively `> 16.57`, `(9.26, 16.57)`, `(6.15, 9.26)`, `< 6.15`). Lane **N** is
supported: it uniquely attains the minimum risk `0.08`, and the point set is finite, so
choosing `λ_R` large enough makes every **N** point beat every **S** and **M** point; among
the **N** points the residual `(λ_T, λ_G)` selects, and the lane-**N** curve is likewise
strictly convex (chord slopes `−14.16`, `−7.65`, `−4.94` t/h). ∎

**Numerical corroboration.** A brute-force sweep of all **20 301** weight vectors on the
grid `λ ∈ {0, 1/200, …, 1}³ ∩ simplex`, with each objective range-normalised first (so the
weights are comparable at all), was run against this instance. Count of weight vectors for
which each route is a minimiser:

```
S1 2891   S2 1355   S3 1049   S4 4459
N1 3183   N2 1407   N3 1070   N4 4890
M1    0   M2    0   M3    0   M4    0
```

**Zero.** Not "few" — zero, as Prop 5.1(b) forces.

> **Why this matters operationally.** M2 — 138.6 h, 720 t, worst-moment risk 0.30 — is a
> perfectly ordinary compromise: a day and a half slower than the aggressive southern
> route, 200 t dearer, and it halves the worst moment of the voyage. It is the sort of
> plan a master picks. It is also, by §5.7.2 below, **the point an equal-weight Chebyshev
> knee selection chooses out of the full front**. A weight-sweep router will never show it
> to anybody, and will never say that it is not showing it.

> **The dent is structural, not contrived.** It arises because the choice of *which side of
> a weather system to pass* is discrete. There is no route "40.7 % south, 59.3 % north";
> the chord that hides M2 joins two routes that cannot be blended. Discrete topological
> alternatives around obstacles are the norm in ocean routing, not the exception — cf.
> the cut-locus behaviour recorded in `handbook/02-debugging-playbook.md` S8, where two
> genuinely distinct optimal routes tie. Every cut locus is a candidate dent.

---

## 5.2 The label algebra — what accumulations are admissible

Label setting (pop in a fixed order, never revisit) is only correct for a restricted class
of cost accumulations. This subsection states that class exactly, verifies that both `+`
and `max` belong to it, and proves that `max` is not expressible by any weighted sum.

### 5.2.1 The structure

> **Definition 5.4a (accumulation).** For each objective `j`, an **accumulation**
> `⊗_j : [0,∞] × [0,∞] → [0,∞]` combines the value carried so far with the increment
> contributed by one leg. The vector accumulation is `(a ⊗ e)_j := a_j ⊗_j e_j`.
> KAIROS admits exactly two: `⊗_j = +` (**additive**) and `⊗_j = max` (**bottleneck**).

> **Definition 5.4b (admissibility conditions).** `(C, ≤, ⊗, 𝟘)` is **admissible for label
> setting** when, for all `a, b, e, e' ∈ C`:
>
> | | condition | name |
> |---|---|---|
> | **(A)** | `(a ⊗ e) ⊗ e' = a ⊗ (e ⊗ e')` | associativity |
> | **(N)** | `∃ 𝟘 : 𝟘 ⊗ e = e ⊗ 𝟘 = e` | neutral element |
> | **(I₁)** | `a ≤ b ⟹ a ⊗ e ≤ b ⊗ e` | **isotone in the accumulated argument** |
> | **(I₂)** | `e ≤ e' ⟹ a ⊗ e ≤ a ⊗ e'` | **isotone in the increment** |
> | **(F)** | `a ≤ a ⊗ e` | **inflationary** (no free progress) |
> | **(Q)** | `(a ⊗ e)_0 ≥ a_0 + Δ_min` for every real leg, some `Δ_min > 0` | strict queue progress |
>
> (A)+(N) make `(C, ⊗, 𝟘)` a monoid; adding (I₁)(I₂)(F) makes it an **isotone, inflationary
> ordered monoid**. Lifting to antichains with `⊕ := PMin ∘ ∪` makes `(𝔄(C), ⊕, ⊗)` an
> idempotent semiring, the setting Martins (1984) works in.

### 5.2.2 Prop 5.4

> ### Prop 5.4 (admissible objectives = monotone ordered semiring; `+` and `max` qualify)
>
> **(i)** Both `⊗_j = +` and `⊗_j = max` on `[0,∞]` satisfy (A), (N), (I₁), (I₂), (F), with
> `𝟘_j = 0` in both cases. Any componentwise product of such monoids satisfies them, so the
> vector accumulation of Def 5.4a is admissible for every mix of `+` and `max`.
>
> **(ii) (distributivity / subpath principle).** Under (I₁), for any `A ⊆ C` and `e ∈ C`,
> ```
> PMin( A ⊗ e )  =  PMin( PMin(A) ⊗ e )      as sets of cost vectors.      (5.6)
> ```
> Consequently the Pareto front at a node depends on its predecessors only through *their*
> Pareto fronts: pruning dominated prefixes never removes a Pareto-optimal complete route.
>
> **(iii) (label-setting correctness).** Assume (A)(N)(I₁)(I₂)(F)(Q), objective 0 additive
> with strictly positive increments bounded below by `Δ_min`, and a queue that pops labels
> in non-decreasing **lexicographic** order of the full cost vector. Then a popped label is
> Pareto-optimal among all attainable costs at its node, and is never subsequently
> dominated. Hence one pass suffices; no label is reopened.
>
> **(iv) (sharpness).** Dropping (I₁) breaks (ii); dropping (F) breaks (iii); dropping (Q)
> breaks the Dial bucket discipline of Prop 4.9 but not (iii). Each failure is exhibited.

**Proof.**

**(i)** Take the two accumulations in turn on `[0,∞]` with the usual order.

*Additive.* (A) `(a+e)+e' = a+(e+e')` ✓. (N) `0+e = e` ✓. (I₁) `a ≤ b ⟹ a+e ≤ b+e` ✓
(order-compatibility of addition). (I₂) symmetric ✓. (F) `a ≤ a+e` because `e ≥ 0` ✓. The
extended arithmetic `∞ + e = ∞` preserves all five.

*Bottleneck.* (A) `max(max(a,e),e') = max(a,e,e') = max(a,max(e,e'))` ✓. (N)
`max(0,e) = e` for `e ≥ 0` ✓. (I₁): let `a ≤ b`. If `max(a,e) = e` then
`max(a,e) = e ≤ max(b,e)` ✓; if `max(a,e) = a` then `a ≤ b ≤ max(b,e)` ✓. (I₂) symmetric
in the two arguments since `max` is commutative ✓. (F) `a ≤ max(a,e)` ✓.

*Product.* Let `(M_j, ≤_j, ⊗_j, 𝟘_j)` each satisfy (A)(N)(I₁)(I₂)(F) and give
`C = ∏_j M_j` the product order and componentwise operation. Each axiom is a universally
quantified statement whose hypotheses and conclusions are conjunctions over `j` of the
corresponding statements in `M_j`: `a ≤ b` in `C` **is** `a_j ≤_j b_j` for all `j`, and
`a ⊗ e ≤ b ⊗ e` in `C` **is** `a_j ⊗_j e_j ≤_j b_j ⊗_j e_j` for all `j`, which follows
factorwise. Same for (A)(N)(I₂)(F). ∎

**(ii)** Write `A ⊗ e := { a ⊗ e : a ∈ A }`.

`(⊇)` Let `c ∈ PMin(PMin(A) ⊗ e)`, so `c = a ⊗ e` with `a ∈ PMin(A)`. Suppose
`c ∉ PMin(A ⊗ e)`: then some `b ∈ A` has `b ⊗ e ≺ c = a ⊗ e`. We claim this forces
`b ∈ PMin(A)` or the existence of some `b' ∈ PMin(A)` with `b' ≤ b`; in either case, by
(I₁), `b' ⊗ e ≤ b ⊗ e ≺ a ⊗ e`, contradicting the minimality of `c` in
`PMin(A) ⊗ e`. The claim is Lemma 5.4d below. Hence `c ∈ PMin(A ⊗ e)`.

> **Lemma 5.4d (every element has a minimal witness).** If `A` is a **finite** subset of
> `C`, then for every `b ∈ A` there is `b' ∈ PMin(A)` with `b' ≤ b`.
> *Proof.* The set `A_b := { a ∈ A : a ≤ b }` is non-empty (`b ∈ A_b`) and finite. Order
> `A_b` by the total order `≺_lex` (lexicographic on the cost tuple) and let `b'` be its
> `≺_lex`-least element. Then `b' ≤ b`. If `b'` were not in `PMin(A)`, some `a ∈ A` would
> satisfy `a ≺ b'`; but `a ≺ b' ≤ b` gives `a ∈ A_b`, and `a ≺ b'` implies `a ≺_lex b'`
> (componentwise `≤` with a strict coordinate forces lexicographic strictness), contradicting
> minimality. So `b' ∈ PMin(A)`. ∎
> *Finiteness is used and is available:* a node's label set is finite by Thm 5.3, and the
> set of routes of bounded length on a finite grid is finite. For an infinite `A` the lemma
> can fail — e.g. `A = {(1/n, 1) : n ≥ 1}` has empty `PMin` — which is why every statement in
> §5 is about the discretised problem and not the continuum front.

`(⊆)` Let `c = a ⊗ e ∈ PMin(A ⊗ e)`. If `a ∈ PMin(A)`, then `c ∈ PMin(A) ⊗ e` and it is
minimal there because `PMin(A) ⊗ e ⊆ A ⊗ e`. If `a ∉ PMin(A)`, take `a' ∈ PMin(A)` with
`a' ≤ a`, `a' ≠ a`. By (I₁), `a' ⊗ e ≤ a ⊗ e = c`. By minimality of `c` in `A ⊗ e` we
cannot have `a' ⊗ e ≺ c`, so `a' ⊗ e = c`. Thus `c ∈ PMin(A) ⊗ e`, and it is minimal
there. ∎

> **Remark 5.4c (why (5.6) is an equality of *value sets*, not of label sets).** The
> `a' ⊗ e = c` branch above is not vacuous: `max` is **not cancellative**, so a strictly
> dominated prefix can extend to a *tied* — never a strictly better — complete cost.
> Concretely with `⊗ = max`: `a' = 0.2 ≺ a = 0.4` but `max(a',0.5) = max(a,0.5) = 0.5`.
> Pruning `a` therefore loses a *label* whose cost is reproduced by another label. Nothing
> in the front is lost. An implementation that reports "number of distinct Pareto routes"
> rather than "number of distinct Pareto cost vectors" must be aware of this; the counts
> differ, and only the second is invariant.

**(iii)** Let `ℓ` be popped, at node `v`, with cost `c = J(P)` for some route `P`. Two
things to prove.

*`c` is not dominated by any attainable cost at `v` that has already been generated.* Every
generated label at `v` was offered to `v`'s label set, which by construction retains an
antichain (invariant (P) of §5.4.2); a label surviving in the set is not dominated by
another survivor, and a label evicted was dominated by a survivor whose cost is `≤` the
evicted one and is still present or was itself replaced by something `≤` it, by transitivity
of `≤`. So the retained set at `v` at pop time is an antichain containing a `≤`-minimum
witness for every generated cost.

*`c` is not dominated by any cost generated later.* Let `q` be any attainable cost at `v`
whose label is generated after `ℓ` is popped. Every such label is produced by extending a
label popped at time `≥` the pop of `ℓ`, i.e. lexicographically `≥ c`. Let `a` be that
popped ancestor's cost, so `a ≥_lex c`, and `q = a ⊗ e₁ ⊗ … ⊗ e_r` for the remaining legs.
By (F) applied `r` times, `q ≥ a` componentwise, hence in particular `q_0 ≥ a_0 ≥ c_0`
(the lexicographic order agrees with `≤` on the first coordinate). If `q_0 > c_0`, `q` cannot
dominate `c` (domination requires `q_0 ≤ c_0`). If `q_0 = c_0`, then `a_0 = c_0` and by (Q)
`r = 0` — no real leg was traversed, so `q = a`; and `a ≥_lex c` with `a_0 = c_0` means `a`
is lexicographically no smaller than `c`, so the first index where they differ has
`a_j > c_j`, hence `a ⊀ c`. In all cases `q ⊀ c`. Therefore `c` is Pareto-optimal at `v`
at pop time and remains so. ∎

**(iv)** *Without (I₁).* Let `k = 2`, and define an accumulation on the second coordinate
by `a ⊗ e := |a − e|`. Then `1 ≤ 2` but `1 ⊗ 3 = 2 > 1 = 2 ⊗ 3`, violating (I₁). Take a
prefix set `A = {(0,1), (0,2)}` at a node — `(0,1) ≺ (0,2)`, so `PMin(A) = {(0,1)}` — and
`e = (0,3)`. Then `PMin(A ⊗ e) = PMin({(0,2),(0,1)}) = {(0,1)}` which is *not* in
`PMin(A) ⊗ e = {(0,2)}`. Pruning the dominated prefix destroyed the optimum. (5.6) fails,
and with it every subpath argument.

*Without (F).* Give one leg a negative fuel increment (a hypothetical "bunkering at sea"
leg). Then a popped label can later be improved by a cycle through that leg, exactly the
negative-cycle failure of `handbook/02-debugging-playbook.md` S1, and label setting does
not terminate with correct values. This is also why ERRATA E1's `F = +∞` exclusion and
G2's `λ > 0` guard are load-bearing: a negative `F` from an unguarded Randers closed form
*is* a negative increment.

*Without (Q).* If `Δ_min = 0`, correctness of (iii) survives (the argument above only used
`Δ_min > 0` to force `r = 0` in the tie case; with `Δ_min = 0` replace it by
lexicographic tie-breaking on the remaining coordinates, which (F) still supports). What
fails is the **Dial bucket queue** of Prop 4.9, whose width must not exceed the minimum
increment — precisely ERRATA E3, which is why the `ℓ_min = h/√2` exclusion and
`Δ_min = c_geo·h·F_min` are enforced by construction rather than assumed. ∎

### 5.2.3 Why bottleneck risk cannot be a weighted sum

A master's question is not "how much risk did I accumulate" but "**how bad did it get**".
That is `J_R(P) = max_{legs} risk_level`. It is a different functional, and no re-weighting
recovers it.

> ### Prop 5.5 (bottleneck is not additive, and no scalarisation of additive objectives expresses it)
>
> Call a route functional `J` **additive** if there is an edge function `g` with
> `J(P) = Σ_{e ∈ P} g(e)` for every route `P`.
>
> **(a)** The bottleneck functional `B(P) := max_{e∈P} r(e)` is additive **iff** `r ≡ 0`.
>
> **(b)** Any weighted sum `Σ_j λ_j J_j` of additive objectives is itself additive.
> Combining with (a): no weighted sum of additive objectives equals `B` unless `B ≡ 0`.
>
> **(c) (the algebraic reason).** `([0,∞], max, 0)` is **idempotent** (`a ⊗ a = a`);
> `([0,∞], +, 0)` is **cancellative**. A monoid that is both is trivial. Hence there is no
> injective monoid homomorphism from the bottleneck monoid into any additive one: the
> obstruction is not the choice of weights, it is the algebra.
>
> **(d) (ordering, not just value).** Even the weaker requirement — that some additive `J`
> induce the *same preference order on routes* as `B` — fails.

**Proof.**

**(a)** (⇐) trivial. (⇒) Suppose `B(P) = Σ_{e∈P} g(e)` for all routes `P`. Apply to a
one-leg route `P = (e)`: `r(e) = B(P) = g(e)`, so `g = r`. Now take any two legs `e₁, e₂`
that can be traversed consecutively with `r(e₁) = r(e₂) = ρ`, and the two-leg route
`P = (e₁, e₂)`: `B(P) = max(ρ,ρ) = ρ`, while `Σ g = 2ρ`. Hence `ρ = 2ρ`, so `ρ = 0`.
Every attainable level is `0`. ∎

**(b)** `Σ_j λ_j J_j(P) = Σ_j λ_j Σ_{e∈P} g_j(e) = Σ_{e∈P} (Σ_j λ_j g_j(e))`, additive with
edge function `g = Σ_j λ_j g_j`. Interchange of the two finite sums is legitimate. ∎

**(c)** Let `(M, ⊗, 𝟘)` be a monoid that is both idempotent and cancellative, and let
`a ∈ M`. Idempotence gives `a ⊗ a = a = a ⊗ 𝟘`; cancelling `a` on the left gives `a = 𝟘`.
So `M = {𝟘}`. A monoid homomorphism `φ` from `([0,∞], max, 0)` into `([0,∞], +, 0)`
satisfies `φ(a) = φ(max(a,a)) = φ(a) + φ(a)`, hence `φ(a) = 0` for all `a`: the only
homomorphism is trivial, so no re-encoding of levels into additive costs preserves the
accumulation. ∎

**(d)** Suppose an additive `J` with edge function `g ≥ 0` induces the same weak preference
order on routes as `B`, i.e. `J(P) ≤ J(Q) ⟺ B(P) ≤ B(Q)`. Fix a level `ρ` attained by some
leg, and let `P_n` be a route of `n` legs all at level `ρ` (the domain is a connected grid,
so arbitrarily long such routes exist inside a region of constant risk). Then
`B(P_n) = ρ = B(P_1)` for every `n`, so `P_n` and `P_1` tie under `B` and must tie under
`J`: `n·g_ρ = g_ρ`, where `g_ρ` is the common edge value. Taking `n = 2` gives `g_ρ = 0`.
Since `ρ` was an arbitrary attained level, `g ≡ 0`, so `J ≡ 0` and `J` ties **every** pair of
routes — while `B` separates any two routes with different worst levels. Contradiction
whenever at least two distinct risk levels are attainable, which they are.

*The concrete instance behind the abstraction.* Route `P₁`: one leg at `r = 0.9`. Route
`P₂`: ten legs at `r = 0.5`. `B(P₁) = 0.9 > 0.5 = B(P₂)` prefers `P₂`; the natural additive
surrogate `g = r` gives `J(P₁) = 0.9 < 5.0 = J(P₂)` and prefers `P₁`. Rescaling `g` by any
constant scales both sides equally and cannot flip the comparison. ∎

> **Remark 5.5a (the log-sum-exp escape, and why it is not one).** The soft-max
> `B_T(P) := T · log Σ_{e∈P} exp(r(e)/T)` is additive in `exp(r/T)` and satisfies
> ```
> max_e r(e)  ≤  B_T(P)  ≤  max_e r(e) + T · log D                       (5.7)
> ```
> where `D` is the number of legs. *(Proof of (5.7): the sum exceeds its largest term, so
> `B_T ≥ max_e r(e)`; and the sum is at most `D` times its largest term, so
> `B_T ≤ max_e r(e) + T log D`.)* To force the error below `δ` one needs `T = δ/log D` —
> which **reintroduces exactly the path-length dependence that ERRATA E7 exists to
> eliminate**, and does so in the objective rather than in the label bound where it is at
> least visible. Worse, `D` varies across the routes being compared, so the bias is not
> even a common offset: two routes whose bottlenecks differ by less than `T log D` are
> ranked arbitrarily by `B_T`. With `D = 180`, `δ = 0.02`, `r_max = 1`: `T = 3.85·10⁻³` and
> the largest summand is `exp(1/T) = e^{260} ≈ 10^{113}`, within IEEE double range but
> eleven orders of magnitude of dynamic range away from the smallest contributing term at
> `r = 0.9` (`e^{233.7} ≈ 10^{101.5}`). It is not a numerical catastrophe; it is simply not the bottleneck.

> **Remark 5.5b (the parametric-threshold escape).** The other standard workaround —
> "constrain `max r ≤ ρ` by deleting every leg with `r > ρ`, solve, and bisect on `ρ`" —
> *is* correct, and is what a scalar router must do. It costs one full solve per level of
> `ρ`, it does not compose with the other objectives (each `ρ` gives a different
> time–fuel front, and the union of those fronts must then be filtered), and it cannot be
> interleaved with the sweep. The label algebra carries the bottleneck for the price of one
> extra coordinate in the cost vector and one extra factor `N_2 = ⌈1/ε⌉+1` in Thm 5.3 —
> `51` at `ε = 0.02`. That comparison is the practical case for §5, and it is a
> constant-factor case, not a complexity-class one. Say so.

---

## 5.3 Throttle families (design decision D1)

### 5.3.1 What an edge carries

Under D1 the throttle `q ∈ [q_min, 1]` is a **first-class control**. Consequently a
direction does not have *a* cost; it has a one-parameter family of costs. This is the
single most common thing routing papers get wrong (CONTRACT §3 D1), and it is what makes
fuel a genuine objective rather than a monotone function of arrival time.

> **Definition 5.6 (throttle family).** At co-moving node `y`, unit direction `u`, the
> **throttle family** is
> ```
> 𝔏(y,u) := { (σ, ṁ, ṙ, r̂)(q) : q ∈ [q_min, 1],  attainable(vessel, env, θ(q,u), q) ≠ NONE }
>                                                                        (5.8)
> ```
> where `σ` is speed made good along `u` (Def 2.3 — **not** `|v|`), `ṁ` the fuel rate
> [kg/s], `ṙ` the additive risk rate [1/s] and `r̂` the instantaneous risk level [—] used by
> the bottleneck accumulation. The `NONE` filter is the seakeeping ban set `S1…S7`;
> `𝔏(y,u) = ∅` means `F(y,u) = +∞` and the direction is excluded, exactly as in ERRATA E1.
>
> The cost of traversing a leg of length `ℓ` in direction `u` at throttle `q` is
> ```
> e_j(q)  =  ℓ/σ(q)  (j=0, time)
>          =  ṁ(q) · ℓ/σ(q)  (additive fuel)
>          =  ṙ(q) · ℓ/σ(q)  (additive risk)   or   r̂(q)  (bottleneck risk)   (5.9)
> ```
> Note the asymmetry already: additive coordinates scale with the leg *duration*; the
> bottleneck coordinate does not depend on `ℓ` at all. A leg of zero duration contributes
> nothing to either — a bottleneck attained on a set of measure zero is not a bottleneck.

This is `MetricLike.legs()` of `CONTRACT.md` §4, and it is the only place the vessel physics
enters the multi-objective layer. A port replaces `attainable`, `rates` and `sigma`; §5
is untouched.

### 5.3.2 Sampling the family

The continuum family is replaced by a finite sample `q_0 < q_1 < … < q_{n_q−1}` spanning
`[q_min, 1]`. Refining below the resolution the bucket grid can represent is wasted work,
because two samples in the same bucket cell collapse to one label anyway (§5.4.2). That
observation *derives* `n_q` rather than leaving it a magic number.

> **Proc 5.6a (throttle sampling).**
> Let `φ(q) := ṁ(q)/σ(q)` be **fuel per unit distance** — the quantity the fuel bucket
> actually resolves, since fuel and time enter (5.9) through the same factor `ℓ/σ`.
> Choose
> ```
> n_q  =  ⌈ log( φ_max / φ_min ) / log(1+ε) ⌉ + 1                          (5.10)
> ```
> and place the samples geometrically in `φ`, i.e. solve `φ(q_m) = φ_min (1+ε)^m` for `q_m`
> by one bisection each on the strictly monotone `φ`; if `φ` is not monotone in `q` for a
> given vessel model, fall back to a uniform grid in `q` with the same `n_q` and rely on the
> per-edge pruning of §5.3.3 to remove the redundancy.
>
> **Derived value for the default Handymax, calm water.** From the table in §5.1.2,
> `φ_min = φ(0.35) = 0.129 946 kg/m`, `φ_max = φ(1.00) = 0.249 887 kg/m`, ratio
> `1.923 000`, `log = 0.653 887`. Hence
> ```
> ε = 0.02  →  n_q = ⌈33.02⌉ + 1 = 35
> ε = 0.10  →  n_q = ⌈ 6.86⌉ + 1 =  8
> ```
> These are the normative defaults. They are *derived*, and they change if the vessel's
> speed–power curve or SFOC bowl changes; recompute (5.10) when `Vessel.calm_power` or
> `Vessel.sfoc` is overridden.

> **Remark 5.6b (a discrepancy with the handbook, recorded honestly).**
> `handbook/02-debugging-playbook.md` S5 asserts that `fuel_per_mile(q)` "must have an
> interior minimum near `q ≈ 0.75`". For the **default** `types.py` vessel it does not:
> with `P = P_ref (V/V_ref)³` and the shallow SFOC bowl,
> `φ = SFOC(q)·P/V ∝ SFOC(q)·V²`, which is strictly increasing in `V` because the bowl's
> `1 + 0.28 d²` factor varies by at most a factor `1.28` while `V²` varies by a factor
> `(7.943/5.598)² = 2.01`. The table above confirms it: `φ` is monotone increasing in `q`.
> An interior minimum requires a **hotel / auxiliary load** `P_aux`, giving
> `φ = (SFOC·P + ṁ_aux)/V` with a `1/V` term; the default `Vessel` has none. This does not
> weaken §5 — the fuel–time trade-off in §5.1.2 is real and monotone-`φ` is enough for it —
> but S5's *discriminating test* as written will report a false bug on the stock
> configuration. Either add `P_aux` to `Vessel` or restate S5's test as "`φ(q)` must be
> non-constant"; the second is what the Pareto front actually needs.

### 5.3.3 Per-edge Pareto pruning

> **Proc 5.6c (per-edge pruning).** After sampling, replace `𝔏(y,u)` by the antichain
> ```
> 𝔏*(y,u)  :=  PMin { e(q_m) : m = 0 … n_q−1 }                            (5.11)
> ```
> where `e(q)` is the leg cost vector of (5.9), and dominance is the componentwise order on
> that vector. Ordered by decreasing `σ`, this is exactly what `MetricLike.legs()` returns.
>
> **Complexity.** `O(n_q² k)` by pairwise comparison, or `O(n_q log n_q + n_q k)` by sorting
> on time and sweeping. With `n_q = 35` and `k = 3` the pairwise form is ~3 600 float
> compares per (node, direction); the sweep form is the normative one for
> `n_q > 16`. Memory `O(|𝔏*| k)`.
>
> **Observed size.** `handbook/02-debugging-playbook.md` S5 records `|𝔏*| = 2–4` for a
> mid-ocean cell, and `|𝔏*| = 1` always as the signature of the time-only fast path
> (`sigma_max`) being wrongly wired into the Pareto solver.

> ### Prop 5.6d (per-edge pruning is lossless)
> Let `e, e'` be two members of a throttle family on the same leg with `e ≤ e'`
> componentwise. Then every route using `e'` has a companion route, identical except that
> `e'` is replaced by `e`, whose total cost is `≤`. Consequently
> ```
> PMin { J(P) : P uses 𝔏 }  =  PMin { J(P) : P uses 𝔏* }                  (5.12)
> ```
> and discarding dominated per-edge entries removes no Pareto-optimal route cost.

**Proof.** Let `P = (a-prefix) ⊗ e' ⊗ (suffix)` and `P̃` the same route with `e` in place of
`e'`. Write the prefix cost `a` and the suffix legs `f_1 … f_s`. By (I₂) of Prop 5.4,
`a ⊗ e ≤ a ⊗ e'`. Applying (I₁) with increment `f_1`,
`(a ⊗ e) ⊗ f_1 ≤ (a ⊗ e') ⊗ f_1`; inducting on `f_2 … f_s` gives `J(P̃) ≤ J(P)`. Hence
every attainable cost with `e'` is dominated-or-equalled by an attainable cost without it,
so removing `e'` cannot delete a Pareto-minimal cost vector. The reverse inclusion is
trivial since `𝔏* ⊆ 𝔏`. ∎

> **What breaks without the hypotheses.**
> 1. **Per-leg independence of the throttle.** Prop 5.6d requires that swapping `q` on one
>    leg leaves every other leg's admissible set unchanged. That is true for the throttle
>    itself. It is **false** under a coupling constraint — an engine ramp-rate limit, or
>    the minimum steering-dwell time `τ_d` of §2. Under such a coupling an entry that is
>    dominated *in isolation* may be the only one compatible with its neighbour, and
>    pruning it is lossy. KAIROS does not attempt to carry the coupling in the label
>    algebra: per D4 it solves the relaxed problem and certifies the gap **a posteriori**
>    (Cor 4.12), with the a-priori local bound of ERRATA E6.3 —
>    `J_dwell − J_relax ≤ L_x v_max τ_d S_leg (1 + L_v Δt)`, under 2 s for
>    `τ_d = 300 s`, `Δt = 6 h`, `S_leg = 150 km`. The global a-priori bound is vacuous
>    (ERRATA E6); the certificate is the guarantee. Do not claim otherwise.
> 2. **Isotonicity (I₂).** Without it, Prop 5.6d's very first step fails, and the whole
>    per-edge optimisation is unsound. This is why Prop 5.4(i) has to be verified for
>    `max` explicitly rather than waved through: the bottleneck coordinate of (5.9) enters
>    the dominance test as a *level*, not a rate, and (I₂) for `max` is what licenses
>    comparing levels directly.
> 3. **A continuous risk level.** If `r̂` jumps discontinuously in `(V,θ)` — e.g.
>    `1.0 if banned else 0.0` — the pruned set `𝔏*` changes discontinuously with the
>    environment and the front becomes unstable in `ε` (playbook S6). `r̂` must be a smooth
>    blend of the margins to each seakeeping criterion. Prop 5.6d remains *true* in that
>    case; it is the *stability* of the result that is lost, not its correctness.

---

## 5.4 ε-buckets: Thm 5.2 and Thm 5.3

### 5.4.1 The error that E7 corrects, quantified

The first draft bucketed the **per-edge increment** at ratio `(1+ε')` with `ε' = ε/D`, so
that `D` roundings compose to `(1+ε'/1)^D ≤ 1+ε`. ERRATA E7 kills it: the label bound is

```
Λ ≈ ( log(range) / log(1+ε') )^{k−1}  with  ε' = ε/D
  ≈ ( D · log(range) / ε )^{k−1}                                          (5.13)
```

**Derived numbers.** `range = 10³`, `ε = 0.02`, `D = S/h ≈ 5 000 km / 28 km = 179 ≈ 180`.
Then `ε' = 1.111·10⁻⁴`, `log(1+ε') = 1.1110·10⁻⁴`, `log(range) = 6.9078`, so the per-axis
cell count is `6.9078 / 1.1110·10⁻⁴ = 6.217·10⁴` and

```
k = 3 :  Λ ≲ (6.217·10⁴)²  =  3.87·10⁹
k = 4 :  Λ ≲ (6.217·10⁴)³  =  2.40·10¹⁴                                   (5.14)
```

per node. E7 states the headline as "exceeds `10¹⁰`"; our derivation gives `3.9·10⁹` at
`k = 3` and `2.4·10¹⁴` at `k = 4`, so E7's figure sits between the two — a difference of
which `k` was assumed, not of substance. **Both are vacuous**: at `k = 3` the bound exceeds
the number of nodes in the domain by five orders of magnitude, so it constrains nothing.

The repair is E7's: bucket on the **accumulated objective value**.

### 5.4.2 The bucket map and the retention rule

> **Definition 5.7 (bucket map).** Let `B ⊆ {1,…,k−1}` be the bucketed objectives and
> `Φ := {0,…,k−1} \ B` the **free** ones (`0 ∈ Φ` always). For `j ∈ B`:
> ```
> ADD-accumulated, geometric grid:
>   b_j(c) = 0                                       if c_j ≤ C_j^min
>          = 1 + ⌊ log(c_j / C_j^min) / log(1+ε) ⌋   otherwise            (5.21a)
>
> MAX-accumulated, uniform grid of width ε·R_j:
>   b_j(c) = 0                    if c_j ≤ floor_j
>          = 1 + ⌊ c_j /(ε R_j) ⌋ otherwise                               (5.21b)
> ```
> `R_j` is the characteristic scale of the bottleneck objective; `R_j = 1` for the
> normalised `Leg.risk_level`. The **cell** of `c` is `b(c) := (b_j(c))_{j ∈ B}`.
>
> **Objective 0 is never bucketed:**
> ```
> 0 ∉ B ,   always.                                                        (5.22)
> ```

Two independent reasons for (5.22), both load-bearing:
1. **Correctness of the queue.** Objective 0 drives the Dial order (Prop 4.9). Bucketing it
   would let the sweep pop a label whose time has been rounded *past* a label still queued,
   destroying the monotone-pop invariant. `LabelSet` refuses the configuration rather than
   approximating it.
2. **Operational.** Arrival time is contractual. An ε-approximate ETA is not a deliverable.

> **The retention rule (normative).** A node's label set maintains simultaneously:
> * **(P)** no stored cost dominates another stored cost — an exact Pareto antichain;
> * **(B)** within one cell, only the labels Pareto-minimal on the **free** coordinates
>   survive.
>
> With `Φ = {0}` (the default `k = 3` configuration) rule (B) reads: *one label per cell,
> the earliest-arriving one*. Time is never approximated; the price of the approximation is
> paid entirely on fuel and risk.

### 5.4.3 Why `max` and `+` are discretised differently

This is the part that is ours (ERRATA E11 claim 2), and the reason is algebraic, not
heuristic.

> ### Prop 5.8 (bottleneck axes are exactly bucketable; additive axes are not)
>
> Let `G_j := { m · ε R_j : m = 0, 1, 2, … }` be the uniform grid of (5.21b), and suppose
> every leg's bottleneck level is rounded **up** to `G_j` at the source:
> `r̃(e) := ε R_j ⌈ r(e)/(ε R_j) ⌉`.
>
> **(a) (closure).** `G_j` is closed under `max`. Hence every route's accumulated bottleneck
> value lies in `G_j`, at every node, for every route, for every route length.
>
> **(b) (injectivity).** `b_j` restricted to `G_j` is injective: distinct grid values fall
> in distinct cells. Hence rule (B) never conflates two distinct attainable bottleneck
> values on that axis, and the label set is **exact** on it.
>
> **(c) (one-time, path-length-independent error).** The only error is the source rounding:
> ```
> max_e r(e)  ≤  max_e r̃(e)  <  max_e r(e) + ε R_j                        (5.23)
> ```
> independent of `D`, of the route, and of everything downstream.
>
> **(d) (the additive contrast).** No non-trivial grid is closed under `+`: if
> `g, g' ∈ G` with `g, g' > 0` then `g + g' ∈ G` requires `G` to be closed under addition,
> which for the geometric grid `C^min(1+ε)^m` fails already at `m = 0`:
> `2C^min ∈ G` iff `(1+ε)^m = 2` for an integer `m`, which fails for all but a measure-zero
> set of `ε`. Quantisation and accumulation therefore **do not commute** for `+`, and the
> rounding error must be re-incurred at every leg. This is the entire source of the
> difficulty in §5.4.5.

**Proof.**

**(a)** `G_j` is a subset of `[0,∞]` totally ordered by `≤`, and `max(g, g') ∈ {g, g'}` for
any two comparable elements. So `max` of finitely many elements of `G_j` is one of them,
hence in `G_j`. By induction along the route, the running maximum after every leg is in
`G_j`, starting from the identity `0 ∈ G_j`. ∎

**(b)** For `g = m ε R_j ∈ G_j` with `m ≥ 1`, `b_j(g) = 1 + ⌊ m ε R_j /(ε R_j) ⌋ = 1 + m`,
and `b_j(0) = 0`. The map `m ↦ 1+m` is injective on `m ≥ 1` and `0 ↦ 0` is distinct from
all of them. Hence distinct grid values occupy distinct cells; rule (B) merges only labels
of *equal* bottleneck value. ∎

**(c)** `r(e) ≤ r̃(e) < r(e) + ε R_j` by definition of the ceiling. Taking the max over the
legs of a route, `max r ≤ max r̃`. For the upper bound let `e*` attain `max_e r̃(e)`; then
`max_e r̃(e) = r̃(e*) < r(e*) + ε R_j ≤ max_e r(e) + ε R_j`. Both inequalities are over the
same finite leg set, so `D` does not appear. ∎

**(d)** The geometric grid is `G = {C^min(1+ε)^m}`. Suppose `g = g' = C^min ∈ G` and
`g + g' = 2C^min ∈ G`. Then `2 = (1+ε)^m` for some integer `m ≥ 0`, i.e.
`ε = 2^{1/m} − 1`. For `m = 1, 2, 3, …` these are `ε = 1, 0.4142, 0.2599, …`, a countable
set not containing the normative `ε = 0.02`. A uniform additive grid `{mδ}` *is* closed
under `+`, but then the cell count on an axis of range `[C^min, C^max]` is
`(C^max − C^min)/δ`, and to get a relative guarantee `ε` at the *bottom* of the range one
needs `δ = εC^min`, so the count is `(C^max/C^min − 1)/ε = 99/0.02 = 4 950` for two decades
against `234` for the geometric grid — a factor 21 worse, per axis, and squared for `k=3`.
So closure under `+` is purchasable only at a cost that (E7.2) exists to avoid. ∎

> **Remark 5.8a (the deep statement).** `max` is **idempotent**; `+` is **cancellative**.
> Prop 5.5(c) showed those two properties cannot coexist non-trivially. Prop 5.8 is the
> numerical shadow of the same fact: idempotence makes a bottleneck's value set finite and
> closed under accumulation, so quantisation commutes with accumulation and the error is
> incurred once; cancellativity makes an additive value set dense and open under
> accumulation, so quantisation must be re-applied and the errors compose. The objective
> that is hardest to *express* (Prop 5.5) is the easiest to *approximate* (Prop 5.8).

> **Remark 5.8b (limitation, stated because it is real).** (5.21b)'s uniform width assumes
> the bottleneck objective is normalised to order 1, which `Leg.risk_level` is (`types.py`).
> A bottleneck on another scale — metres of freeboard, degrees of roll — must be
> normalised before it reaches the label algebra, or `R_j` set to its characteristic
> magnitude. A *geometric* grid on a bottleneck axis would be actively wrong: it spends
> unboundedly many cells separating risk `10⁻⁹` from `10⁻⁸`, differences with no
> operational meaning, while giving a single `(1+ε)` factor to the interval around `0.9`
> where a master actually decides. A bottleneck index is compared by **difference**, not by
> ratio, so the guarantee on that axis is additive-`ε`, not multiplicative.

### 5.4.4 Thm 5.3 — the label-count bound

> ### Thm 5.3 (label-count bound)
> Assume a priori bounds `0 < C_j^min ≤ c_j ≤ C_j^max` on every bucketed objective, and the
> retention rule (P)+(B) with the bucket map (5.21). Let
> ```
> N_j := ⌈ log( C_j^max / C_j^min ) / log(1+ε) ⌉ + 1      (ADD, geometric)  (5.24a)
> N_j := ⌈ R_j^max / (ε R_j) ⌉ + 1                        (MAX, uniform)    (5.24b)
> ```
> Then the number of labels retained at any node satisfies
> ```
> Λ  ≤  A_Φ · ∏_{j ∈ B} N_j ,                                             (5.25)
> ```
> where `A_Φ` is the maximum size of an antichain in the free coordinates within one cell.
> With a single free coordinate (`Φ = {0}`, the default), `A_Φ = 1` and
> ```
> Λ  ≤  ∏_{j ∈ B} N_j ,                                                   (5.26)
> ```
> **with no dependence on the route length `D`, on the number of nodes `N`, or on the
> graph at all.**

**Proof.** By rule (B), the labels retained at a node that share a cell form an antichain in
the free coordinates, so a cell holds at most `A_Φ` labels. When `|Φ| = 1` the free
coordinates are totally ordered, so an antichain in them has at most one element, giving
`A_Φ = 1`. It remains to count occupied cells. For a bucketed ADD axis, `c_j ∈ [C_j^min,
C_j^max]` gives, by (5.21a), `b_j(c) ∈ {0, 1, …, 1 + ⌊log(C_j^max/C_j^min)/log(1+ε)⌋}`,
which has at most `⌈log(C_j^max/C_j^min)/log(1+ε)⌉ + 1 = N_j` elements. For a bucketed MAX
axis, (5.21b) gives `b_j(c) ∈ {0, …, 1 + ⌊R_j^max/(εR_j)⌋}`, at most `N_j` elements. The
cell is the tuple of these indices, so at most `∏_{j∈B} N_j` cells are occupied. Multiplying
gives (5.25). No step referred to the route length or the graph. ∎

**Derived values.** `ε = 0.02`; fuel spanning two decades (`C^max/C^min = 100`); risk a
normalised bottleneck on `[0,1]`.

```
N_fuel = ⌈ log 100 / log 1.02 ⌉ + 1 = ⌈ 4.605170 / 0.0198026 ⌉ + 1
       = ⌈ 232.55 ⌉ + 1 = 234
N_risk (bottleneck, uniform) = ⌈ 1 / 0.02 ⌉ + 1 = 51
N_risk (if additive, geometric, two decades) = 234
```

| configuration | `Λ` bound | source |
|---|---|---|
| `k=3`, fuel + **additive** risk, both geometric | `234² = ` **54 756 ≈ 5.5·10⁴** | E7.2 worst case, reproduced |
| `k=3`, fuel geometric + **bottleneck** risk uniform | `234 × 51 = ` **11 934** | (5.24b), a 4.6× improvement |
| `k=4`, + comfort geometric two decades | `234 × 51 × 234 = ` **2.79·10⁶** | (5.26) |
| observed after dominance pruning, `k=3` | **10–40** | ERRATA E7, measured |
| observed peak, `labels.py` self-test, `ε=0.10`, 10 000 offers | **102** retained, 368 accepted | measured, §5.4.6 |

Compare (5.14): `5.5·10⁴` against `3.9·10⁹` is a factor `7.1·10⁴`. **That** is what E7's
correction buys, and it is the correction's real content.

> **What breaks without the a priori bounds.** `N_j` is finite only because `C_j^max` and
> `C_j^min` exist. Supply them, do not guess them:
> * `C_j^max` from an **admissible upper bound route** — the great-circle route at
>   `q = 1` gives a finite time and fuel, and any Pareto-optimal route is no worse in at
>   least one coordinate. In practice use the fastest-route cost inflated by the operator's
>   ETA window.
> * `C_j^min` from an **optimistic lower bound** — the dilated-cell coarse solve of D5 /
>   Prop 4.11, which is the same object that produces the certificate of Cor 4.12. It is
>   already computed; reuse it.
> * If a bound is missing, `Λ` is unbounded and Thm 5.3 says nothing. Cells at the extreme
>   ends are then created on demand by the hash structure of §5.5, and the run must report
>   `Λ_peak`; an unexpectedly large `Λ_peak` is the diagnostic that a bound is wrong.

### 5.4.5 Thm 5.2 — the approximation guarantee, stated correctly

This is where care is required, and where this file departs from ERRATA E7's headline
phrasing. E7 says value bucketing "gives a uniform `(1+ε)` guarantee with **no path-length
dependence**". That is **exactly right for the label count** (Thm 5.3, just proved) and
**exactly right per node** (Thm 5.2(b) below). It is **not** right for the per-path
guarantee, and Remark 5.11 exhibits a four-node counterexample that the reference
implementation reproduces. State the true theorem.

> **Definition 5.9 (the witness relation).** For `s, p ∈ C` write `s ⊴_μ p` when
> ```
> s_j ≤ p_j                        for every free j ∈ Φ  (time exact)
> s_j ≤ (1+ε)^μ · p_j              for every bucketed ADD j
> s_j ≤ p_j + μ · ε R_j            for every bucketed MAX j              (5.27)
> ```
> `⊴_1` is the **one-cell** guarantee; `⊴_0` is exact dominance.

> ### Thm 5.2 (ε-Pareto approximation guarantee)
> Assume the bucket map (5.21) with (5.22), the retention rule (P)+(B), and Prop 5.4's
> admissibility. Let `v` be any node and `P` any route to `v` with cost `p = J(P)`.
>
> **(a) (time is exact — unconditional).** The retained set at `v` contains a label `s` with
> `s_0 ≤ p_0`. No approximation is ever applied to arrival time, for any route, any `D`,
> any `ε`.
>
> **(b) (one-cell bound, per node — unconditional, `D`-independent).** If the cost `p` is
> *offered* at `v` (i.e. `P`'s prefix survived to be extended along `P`'s last leg) and is
> rejected, then the retained set at `v` contains `s` with `s ⊴_1 p`. Equivalently: **the
> distance from a rejected cost to its surviving witness is one bucket width in total — not
> one per eviction and not one per leg.**
>
> **(c) (per-path bound — the correct global statement).** In general the retained set at
> `v` contains `s` with `s ⊴_{μ(P)} p`, where `μ(P)` is the number of **displacement
> events** along `P`'s witness chain (Def 5.10), and
> ```
> μ(P)  ≤  min ( D ,  max_{j∈B} N_j )                                     (5.28)
> ```
> **(d) (recovering a uniform bound, and its price).** Setting `ε' := ε/D_max` in (5.21a)
> restores `⊴_1` uniformly, at the label count (5.14) — which is vacuous. The value-bucketed
> construction is precisely the decision **not** to pay that.
>
> **(e) (the costs reported are exact).** Every retained label's cost vector is the cost of
> a genuinely attainable route, computed by accumulation and never rounded. The
> approximation in (b)/(c) concerns the **completeness** of the returned front, never the
> **correctness** of the costs attached to the routes it returns.

**Proof.**

> **Definition 5.10 (witness chain, displacement event).** Let `P = (e_1, …, e_D)` visit
> `v_0 = x_A, v_1, …, v_D = v` with prefix costs `p^{(i)}`. Define `s^{(0)} := 𝟘 = p^{(0)}`.
> Given `s^{(i)}` retained at `v_i`, form `x^{(i+1)} := s^{(i)} ⊗ e_{i+1}` and offer it at
> `v_{i+1}`. Set `s^{(i+1)} := x^{(i+1)}` if accepted; otherwise `s^{(i+1)} :=` the retained
> label that rejected it. A **displacement event at step `i+1` on axis `j`** occurs when the
> rejection puts the witness in a strictly higher cell than the true prefix, i.e.
> `b_j(s^{(i+1)}) > b_j(p^{(i+1)})`. `μ_j(P)` counts them; `μ(P) := max_j μ_j(P)`.

**(a)** Induction on `i`. Base: `s^{(0)}_0 = 0 = p^{(0)}_0`. Step: assume `s^{(i)}_0 ≤
p^{(i)}_0`. The extension uses the *same* leg `e_{i+1}` with the *same* throttle, so the
same time increment `Δt = ℓ/σ`. Since objective 0 is additive,
`x^{(i+1)}_0 = s^{(i)}_0 + Δt ≤ p^{(i)}_0 + Δt = p^{(i+1)}_0`. If `x^{(i+1)}` is accepted,
`s^{(i+1)}_0 = x^{(i+1)}_0` and we are done. If it is rejected, the rejecting label `t`
satisfies either `t ≺ x^{(i+1)}` (rule (P)), whence `t_0 ≤ x^{(i+1)}_0`, or `t` shares
`x^{(i+1)}`'s cell and is no worse on every free coordinate (rule (B)), whence again
`t_0 ≤ x^{(i+1)}_0`. Either way `s^{(i+1)}_0 ≤ p^{(i+1)}_0`. Finally, a retained label may
later be **evicted**; it is evicted only by a label that dominates it (rule (P), so `≤` on
every coordinate including 0) or by a same-cell label no worse on the free coordinates (rule
(B), so `≤` on coordinate 0). Both preserve the inequality, and `≤` is transitive, so a
witness with `s_0 ≤ p_0` is present at `v` at all later times. ∎

**(b)** Let `p` be offered at `v` and rejected by a retained `t`. Two cases.
*Rule (P) fired:* `t ≺ p`, so `t ≤ p` on every coordinate, which is `⊴_0`, hence `⊴_1`.
*Rule (B) fired:* `t` and `p` share the cell `b(p)` and `t ≤ p` on every free coordinate.
On a bucketed ADD axis, sharing cell `m ≥ 1` means `t_j, p_j ∈ [C^min(1+ε)^{m−1},
C^min(1+ε)^{m})`, so `t_j / p_j < (1+ε)`; cell `0` means `t_j, p_j ≤ C^min` so
`t_j ≤ C^min ≤ (1+ε)p_j` provided `p_j ≥ C^min/(1+ε)`, and for `p_j` below that the axis is
at its floor and `t_j ≤ C^min` is the declared resolution limit. On a bucketed MAX axis,
sharing a cell of width `εR_j` gives `|t_j − p_j| < εR_j`, so `t_j < p_j + εR_j`. Hence
`t ⊴_1 p`.
*Persistence.* If `t` is later evicted, its evictor `t'` satisfies `t' ≤ t` (rule (P)) — then
`t' ⊴_1 p` by transitivity — or shares `t`'s cell, which **is** `p`'s cell, and is no worse
on the free coordinates than `t` hence than `p`; so `t' ⊴_1 p` by the same cell-width
argument. The witness stays within one cell of `p` however many evictions occur. ∎

**(c)** Induction on `i` with hypothesis `s^{(i)} ⊴_{μ_i} p^{(i)}`, `μ_i` = displacement
events so far.

*Extension preserves the relation with no growth.* This is the property value bucketing has
and increment bucketing does not, and it is worth isolating:

> **Lemma 5.2a.** If `s ⊴_μ p` then `s ⊗ e ⊴_μ p ⊗ e` for every `e ∈ C`.
>
> *Proof.* Free ADD axes: `s_0 + Δ ≤ p_0 + Δ` ✓. Bucketed ADD axes: from
> `s_j ≤ (1+ε)^μ p_j` and `Δ ≥ 0`,
> ```
> s_j + Δ  ≤  (1+ε)^μ p_j + Δ  ≤  (1+ε)^μ p_j + (1+ε)^μ Δ  =  (1+ε)^μ (p_j + Δ)
> ```
> using `(1+ε)^μ ≥ 1` ✓. Bucketed MAX axes: from `s_j ≤ p_j + μεR_j` and monotonicity of
> `max`,
> ```
> max(s_j, r)  ≤  max(p_j + μεR_j, r)  ≤  max(p_j, r) + μεR_j
> ```
> the last step because `max(a+δ, b) ≤ max(a,b) + δ` for `δ ≥ 0`: if the left max is `a+δ`
> then it equals `a + δ ≤ max(a,b)+δ`; if it is `b` then `b ≤ max(a,b) ≤ max(a,b)+δ`. ✓ ∎
>
> **This is the whole reason E7 mandates value bucketing.** Under *increment* bucketing the
> quantity preserved is a bound on `Δ`, not on the accumulated value, so the same step reads
> `s_j + (1+ε)Δ ≤ …` and picks up a factor at every leg, giving `(1+ε)^D`.

*Rejection costs at most one displacement.* Let `x = s^{(i)} ⊗ e_{i+1}` and
`y = p^{(i+1)}`; by Lemma 5.2a, `x ⊴_{μ_i} y`. If `x` is accepted, `μ_{i+1} = μ_i` and we
are done. If rejected by `t`: by rule (P) `t ≤ x`, giving `t ⊴_{μ_i} y` with no
displacement; or by rule (B), `t` shares `x`'s cell. On a bucketed ADD axis,
`x_j ≤ (1+ε)^{μ_i} y_j` gives `b_j(x) ≤ b_j(y) + μ_i`, and `t` in `x`'s cell gives
`t_j < C^min(1+ε)^{b_j(x)} ≤ C^min(1+ε)^{b_j(y)+μ_i} ≤ (1+ε)^{μ_i} · (1+ε) y_j` — using
`y_j ≥ C^min(1+ε)^{b_j(y)−1}` — so `t ⊴_{μ_i + 1} y`, one displacement. The MAX axis is the
same computation with `+εR_j` in place of `×(1+ε)`, using Prop 5.8(b): on a MAX axis with
source-rounded levels the cells are singletons, so **no displacement is possible at all**
and `μ_j ≡ 0` for bottleneck objectives.

*Bounding `μ`.* Each displacement on axis `j` increases `b_j(s) − b_j(p)` by at least 1, and
that difference never decreases (extension is isotone by Lemma 5.2a, and rule-(P) rejections
do not increase it). There are at most `D` steps, so `μ_j ≤ D`; and `b_j(s) ≤ N_j − 1`
always, while `b_j(p) ≥ 0`, so `μ_j ≤ N_j − 1 < N_j`. Hence (5.28). ∎

**(d)** With `ε' = ε/D_max`, Lemma 5.2a plus the one-displacement-per-step bound gives
`s_j ≤ (1+ε')^{D} p_j ≤ (1 + ε/D_max)^{D_max} p_j ≤ e^{ε} p_j ≤ (1+ε(1+ε)) p_j` for
`ε ≤ 1`, i.e. a uniform bound of the required form. The label count is then (5.13)/(5.14),
`3.9·10⁹` per node at `k=3`. ∎

**(e)** Immediate from the construction: `extend()` accumulates real leg costs and rule
(P)/(B) only ever *selects among* accumulated vectors; no stored coordinate is ever replaced
by a rounded value. The bucket index is used as a **key**, never as a **value**. (An
implementation that stored the cell representative instead would gain a cleaner invariant
and lose (e) — see Remark 5.12.) ∎

> ### Remark 5.11 — the counterexample to the uniform per-path bound
>
> `ε = 0.10`, `k = 2`, objectives `(time free, fuel bucketed ADD)`, fuel floor
> `C^min = 1.0`, so the geometric cells are `(1.00, 1.10)`, `[1.10, 1.21)`, `[1.21, 1.331)`.
> Four nodes: `x_A → u` by two routes, `u → v` by one leg, and `x_A → v` directly.
>
> | route | cost at `u` | cell at `u` |
> |---|---|---|
> | `A` | `(10.00, 1.09)` | 1 |
> | `B` | `(11.00, 1.05)` | 1 |
>
> Same cell; `A` is earlier, so rule (B) **rejects `B`**. Extend both by the leg
> `e = (Δt, Δfuel) = (0.02, 0.02)`, and let a third route reach `v` directly with
> `C = (9.00, 1.20)`.
>
> | at `v` | cost | cell |
> |---|---|---|
> | `C` (direct) | `(9.00, 1.20)` | 2 |
> | `A ⊗ e` | `(10.02, 1.11)` | 2 |
> | `B ⊗ e` (**never generated**) | `(11.02, 1.07)` | 1 |
>
> `C` and `A⊗e` share cell 2; `C` is earlier, so rule (B) rejects `A⊗e`. **The retained set
> at `v` is `{(9.00, 1.20)}` alone**, while the true Pareto front at `v` is all three
> points. The witness for the true point `(11.02, 1.07)` is `C`, with fuel ratio
> ```
> 1.20 / 1.07  =  1.121 495…   >   1.10 = 1+ε ,     and  ≤ (1+ε)² = 1.21 .
> ```
> Two displacement events, `μ = 2`, exactly as Thm 5.2(c) predicts, and the uniform `(1+ε)`
> claim is false.
>
> **This was run against `src/kairos/labels.py` verbatim**, not constructed on paper:
> `LabelSet.insert` returns `True, False` at `u` and `True, False` at `v`, and
> `LabelSet.costs()` at `v` returns `[(9.0, 1.2)]`. The chain extends: `r` such displacement
> events in series give `(1+ε)^r`, up to the cap (5.28).
>
> **Consistency with ERRATA E7.** E7's substantive correction — bucket the value, not the
> increment — is right and is what makes Thm 5.3 non-vacuous. Its phrase "no path-length
> dependence" is right for the label count and for the per-node bound, and overstated for
> the per-path bound. This matches the literature: Tsaggouris & Zaroliagis (2009) carry a
> factor `n` in their scaling for exactly this reason. **The right response is Thm 5.2(e)
> plus Cor 4.12**, not a smaller `ε`.

> ### Remark 5.12 — the two repairs, and why neither is adopted
>
> 1. **Round stored values down to the cell bottom.** Then the invariant
>    `b_j(s) ≤ b_j(p)` *is* preserved exactly (the argument in Thm 5.2(c) never reaches the
>    displacement case, because a cell holds one value), and the front is a valid **lower
>    bound**. Rejected because it destroys Thm 5.2(e): the reported cost would no longer be
>    the cost of any route, and the operator would be handed a fuel figure the ship cannot
>    achieve. The compounding reappears as a gap between reported and realised cost, where
>    it is *less* visible, not more.
> 2. **Keep, in each cell, the free-axis minimiser *and* the minimiser of each bucketed
>    axis.** This blocks the counterexample of Remark 5.11 (both `C` and `A⊗e` survive) at
>    the cost of `Λ → (1 + |B|)·Λ`, i.e. `×3` at `k = 3`. It does **not** yield a proof of
>    the uniform bound, because the guarantee would then be per-axis rather than joint:
>    there is a stored label good on fuel and a stored label good on time, but not
>    necessarily one label good on both — and demanding one label good on both is exact
>    Pareto filtering, `ε = 0`.
>
> **What is adopted** is honesty plus the certificate: report `ε`, report `Λ_peak`, report
> `μ_peak` if instrumented, and attach the a posteriori gap of Cor 4.12 to every returned
> route. Per ERRATA E6, the a posteriori certificate is the primary guarantee in KAIROS
> anyway, and it does not degrade with voyage length.
>
> **Conjecture 5.12a.** Under retention rule (P)+(B) with value bucketing and a single free
> coordinate, `μ(P) = O(1)` for every route in an instance whose leg costs satisfy a uniform
> non-degeneracy condition (no two distinct prefix costs at a node lie in the same cell
> within `o(ε)` of a cell boundary). *What is missing:* a proof that displacement events
> cannot recur, or a bound on their frequency in terms of the leg-cost distribution. We have
> neither, and the counterexample of Remark 5.11 shows `μ ≥ 2` is reachable. It is a
> conjecture, and it is labelled one.

### 5.4.6 Measured behaviour of the label set

Run of `python -m kairos.labels` (the `_selftest`), 10 000 seeded cost triples shaped like
real routes (time and fuel anti-correlated, risk `Beta(2,5)`), `k = 3`, `ε = 0.10`,
objectives `(time ADD unbucketed, fuel ADD geometric, risk MAX uniform)`:

| quantity | value |
|---|---|
| costs offered | 10 000 |
| accepted (inserted at some point) | 368 |
| final retained set | 101 (peak 102) |
| internal dominations among retained | **0** (invariant (P) holds) |
| exact Pareto set of the same input | 338 |
| max relative loss, time | **+0.000 000** (bound 0) — Thm 5.2(a) |
| max relative loss, fuel (geometric) | **+0.081 762** (bound 0.10) |
| max absolute loss, risk (uniform MAX) | **+0.083 521** (bound 0.10) |
| guarantee violations over the exact front | **0** |

This is a **single-node** experiment: every cost is offered directly, so it measures
Thm 5.2(b), the one-cell bound, and confirms it with ~18 % margin. It does *not* test
Thm 5.2(c); Remark 5.11 is the test that does, and it fails the uniform claim. Both are
reported.

---

## 5.5 Dominance testing: the data structure

### 5.5.1 Required operations

A node's label store must support, on an antichain of size `m ≤ Λ`:

| op | signature | called |
|---|---|---|
| `dominated?(c)` | is there a stored `s` with `s ≤ c`? | once per offer |
| `cell_occupant(b(c))` | the label in cell `b(c)`, if any | once per offer |
| `insert(c, ℓ)` | store, evicting everything `c` dominates or supersedes in-cell | once per accepted offer |
| `iterate()` | in a deterministic total order | once per node, at reconstruction |
| `best(j)` | the stored label minimising objective `j` | once per pop |

**Determinism is a correctness requirement, not tidiness.** Prop 5.4(iii) and the
reproducibility of a reported route both assume that re-running the sweep retains the same
labels. Every tie must be broken by a **stated total order** — cost lexicographically,
then arrival time, node id, heading, throttle, and a bounded ancestor signature — never by
insertion order, pointer identity or hash iteration order. `labels.py::_order_key` is that
order.

> **Lemma 5.13 (the free-axis cutoff).** If `s_0 > c_0` then `s` cannot dominate `c`, and if
> `s_0 < c_0` then `c` cannot dominate `s`.
> *Proof.* Domination requires `≤` in every coordinate, including 0. ∎
>
> **Consequence.** Keep the store sorted ascending by objective 0. The `dominated?(c)` scan
> visits only the prefix `{s : s_0 ≤ c_0}`; the "what does `c` evict" scan visits only the
> suffix `{s : s_0 ≥ c_0}`. One binary search splits the array and each scan is one-sided.

### 5.5.2 Structures, by `k`

> **Structure D-2 (`k = 2`; one free + one bucketed axis).** The antichain is **totally
> ordered**: sorting by `c_0` ascending forces `c_1` descending, since two labels with both
> coordinates ordered the same way would be comparable. Store as a sorted dynamic array
> (or balanced BST) keyed on `c_0`.
> * `dominated?(c)`: one predecessor query on `c_0`, then compare that element's `c_1`.
>   **`O(log m)`**.
> * `insert`: predecessor query, then delete the contiguous run of successors `c` dominates.
>   **`O(log m + d)`** for `d` deletions, **`O(log m)`** amortised (each label is deleted
>   once).
> * Optimal: `Ω(log m)` by reduction from predecessor search.
>
> *Proof of the total-order claim.* Let `s ≠ t` be stored, `s_0 < t_0` (ties broken by the
> total order, so assume strict). If `s_1 ≤ t_1` then `s ≤ t` and `s ≺ t`, contradicting
> antichain. Hence `s_1 > t_1`. ∎

> **Structure D-3 (`k = 3`, NORMATIVE).** Two tiers.
> 1. **Cell tier** — an open-addressing hash map from the packed integer cell key
>    `b(c) ∈ ℤ^{|B|}` (pack as a single 64-bit word: 32 bits per axis is ample, since
>    `N_j ≤ 234`) to the slot index of that cell's occupant. Serves `cell_occupant` in
>    **`O(1)` expected**, `O(m)` worst case. Load factor `≤ 0.7`, linear probing, no
>    allocation after the initial reserve of `min(Λ_bound, 64)` slots.
> 2. **Dominance tier** — a struct-of-arrays: `k` contiguous `f64` arrays of length `m`,
>    plus parallel arrays for `node`, `parent`, `theta`, `q`. Sorted ascending by
>    objective 0. `dominated?` and eviction are the one-sided scans of Lemma 5.13.
>    **`O(m·k)` worst case, `O(m_≤ · k)` typical**, with `m_≤` the prefix length.
>
> **Why not an asymptotically better structure.** Exact 3-D dominance-emptiness under
> insertion is solvable in `O(log² m)` per operation with a range tree whose secondary
> structure is a priority search tree (Overmars 1988; de Berg–Cheong–van Kreveld–Overmars,
> *Computational Geometry*, ch. 5 and 10), with `O(m log m)` space. The constant is large
> and the structure allocates. With the **measured** `m = 10–40` (ERRATA E7) and `k = 3`,
> the flat scan is at most `40 × 3 = 120` sequential `f64` comparisons on contiguous memory
> — roughly two cache lines per array, no pointer chasing, and it vectorises. `log²(40) ≈
> 27` "operations" of a pointer-chasing structure is not faster. Break-even is around
> `m ≈ 10³`, which Thm 5.3 puts out of reach at `k = 3` (`Λ ≤ 11 934` is the *bound*; the
> observation is two orders below it). **Normative: flat arrays for `k ≤ 3`.**

> **Structure D-4 (`k = 4`).** The label count bound rises to `2.79·10⁶` (§5.4.4) and the
> observed `m` rises with it, so the flat scan can stop paying. Two options, in order of
> preference:
> 1. **Keep D-3 but exploit the cell tier harder.** Because rule (B) keeps one label per
>    cell, `m ≤ ` (occupied cells) and the *cells* form a `|B|`-dimensional integer grid.
>    Maintain, per value of the first bucketed index `b_1`, the sorted list of occupied
>    `(b_2, b_3)`; `dominated?` then scans only cells with `b_1 ≤ b_1(c)`. This is a
>    constant-factor cut of typically `2×`–`5×`, not an asymptotic one, and it costs
>    nothing in complexity.
> 2. **A k-d tree over the cost vectors with dominance pruning** — descend only into
>    subtrees whose per-node bounding box could contain a dominator. Expected
>    `O(m^{1−1/k})` per query for uniformly distributed points; **this is a standard
>    expected-case bound from the literature and is an unverified estimate for KAIROS
>    label distributions**, which are strongly anti-correlated (that is what a Pareto front
>    *is*) and so violate the uniformity assumption. Measure before adopting. Worst case
>    remains `O(m)`.
>
> Rebalancing a k-d tree under the eviction pattern of a Pareto filter is itself a cost;
> a periodic bulk rebuild every `m/2` insertions, amortised `O(log m)` per insertion, is the
> normative form if D-4(2) is used at all.

### 5.5.3 Memory

Per label, `k = 3`: `3 × 8` (cost) `+ 8` (node) `+ 8` (parent index) `+ 8` (`t`)
`+ 8` (`theta`) `+ 8` (`q`) `= 64` bytes, with the parent as a **32- or 64-bit index into a
label arena**, never a language-level pointer (D7). For the CORE-THEOREM §8.2 grid,
`N = 29 529` nodes at `Λ = 40`:

```
29 529 × 40 × 64 B  =  75.6 MB                                            (5.29)
```

At the Thm 5.3 bound `Λ = 11 934` this would be **22.6 GB**, which is why `Λ_peak` must be
instrumented and reported (`Route.label_peak`): the bound is not a budget. If `Λ_peak`
approaches the bound, either an a priori range is wrong (§5.4.4) or `ε` is too small for the
problem.

---

## 5.6 Interaction with the Co-Moving Reduction

This is the one place where the core theorem simplifies the multi-objective layer directly,
and it is a real simplification, not a rhetorical one.

### 5.6.1 What the reduction removes

In the **ground frame**, every label at a node carries its own arrival time `t_ℓ`. The
consequences compound:

1. The throttle family `𝔏*(x, u)` depends on `t`, so it must be re-evaluated **per label**.
   Metric evaluations scale as `O(N · n_dir · n_q · Λ)`.
2. The causality condition ERRATA (E4.1), `r(x)·L_t(x,t) ≤ 1`, must hold **at each label's
   own time**. `k` objectives multiply the number of `(x,t)` pairs at which it can fail, and
   a single failure invalidates the single-pass licence for the labels that pass through it.
3. Where it fails, the wait relaxation (E5.1) `F̃_ℓ = inf_{s∈[0,S_max]}[s/ℓ + F(x,t+s,u)]`
   must be evaluated per label, at that label's `ℓ` and its own horizon truncation
   `S_max(t_ℓ)`.
4. No caching is possible: two labels at the same node with different arrival times see
   different environments.

In the **co-moving frame**, `𝒱_w(y) = 𝒱₀(y) ⊖ w` has no `t` argument (Thm C.1(b)). Therefore:

> **Prop 5.14 (the labels ride the stationary sweep).** Under A1, the throttle family
> `𝔏*(y,u)` of Def 5.6 depends on `y` and `u` only. Consequently
>
> **(a)** `𝔏*(y,u)` is computed **once** per `(node, direction)` and shared by all `Λ`
> labels at that node. Metric evaluations drop from `O(N·n_dir·n_q·Λ)` to
> `O(N·n_dir·n_q)` — a factor `Λ`, i.e. **10–40× measured**, on the dominant cost of the
> solve.
>
> **(b)** `L_t ≡ 0`, so (E4.1) holds vacuously **for every label simultaneously**. Label
> setting is licensed regardless of the forecast's temporal Lipschitz constant. Measured in
> CORE-THEOREM Test 8.10 Regime A: `L_t` in the co-moving frame is `0.0` to the last bit,
> `max` and `p99` and median alike.
>
> **(c)** No wait relaxation appears anywhere in the multi-objective layer: by Thm C.1(c)
> the interception constraint is active at `t*`, so the optimum never loiters. `extend()`
> still *accepts* a zero-`sog` leg (a wait is a legal move with `dt > 0`), but nothing in
> the pure co-moving case generates one.
>
> **Proof.** (a) is immediate from (C.3): `𝒱_w(y)` is `t`-free, and `𝔏*` is a function of
> the indicatrix and the vessel model alone, so the family is a function of `y, u`. (b) is
> Thm C.1(b): `L_t = 0` makes `r(x)·L_t = 0 ≤ 1` for any stencil radius. (c) is
> Thm C.1(c). ∎

**Caching cost.** The precomputed families occupy `n_dir · |𝔏*| · k · 8` bytes per node.
With `n_dir = 16`, `|𝔏*| = 3` (playbook S5), `k = 3`:

```
16 × 3 × 3 × 8 B = 1 152 B/node ;   × 29 529 nodes  =  34.0 MB            (5.30)
```

against the `75.6 MB` of (5.29) for the labels themselves. It pays for itself immediately:
each cached entry replaces `Λ` recomputations.

### 5.6.2 What the reduction *costs* the multi-objective layer

One thing, and it is not small. Requirement **R2** of CORE-THEOREM §8.1 says: do not select
the goal node by the interception root find; select it by minimising the ground miss
`‖(y + w·T[y]) − x_B‖` over nodes. **With labels, `T[y]` is not a single number.**

> **Prop 5.15 (the goal is a `Λ`-way selection, not a node).** Each label `ℓ` at co-moving
> node `y` carries its own arrival time `τ_ℓ = ℓ.cost_0`, hence its own ground landfall
> ```
> x_ℓ  =  y + w · τ_ℓ .                                                   (5.31)
> ```
> Two labels at the *same* node land `|w| · |τ_ℓ − τ_{ℓ'}|` apart on the ground.
>
> **Quantification.** For the CORE-THEOREM §8.2 voyage, `w = (3.0, 1.0) m/s`, `|w| = 3.162
> m/s`. A `k=3` Pareto front spanning the arrival-time range of the §5.1.2 instance
> (`91.094 h` to `183.605 h`, i.e. `Δτ = 92.5 h = 3.33·10⁵ s`) gives a landfall spread of
> ```
> |w| · Δτ  =  3.162 × 3.33·10⁵  =  1.05·10⁶ m  =  1 053 km .             (5.32)
> ```
> **A single goal node is therefore not merely imprecise; it is wrong by a thousand
> kilometres for the slow end of the front.**

> **Proc 5.15a (goal selection with labels).**
> ```
> 1  best ← empty label list
> 2  for each node y in the co-moving grid:
> 3      for each label ℓ retained at y:
> 4          if not finite(ℓ.cost_0): continue
> 5          x_ℓ ← ground_position(y, ℓ.cost_0)              -- Eq (5.31)
> 6          miss_ℓ ← haversine(x_ℓ, x_B)
> 7          if miss_ℓ ≤ tol_miss: append ℓ to best          -- CONSTRAINT, not objective
> 8  F ← PMin( { ℓ.cost : ℓ in best } )                      -- exact filter, ε = 0
> ```
> **Input:** the sweep result, the label store, `x_B`, `tol_miss`.
> **Output:** the returned Pareto front `F` with its labels.
> **Invariant:** every `ℓ ∈ best` names a route whose ground landfall is within `tol_miss`
> of `x_B`.
> **Complexity:** `O(N · Λ)` with one haversine each — `29 529 × 40 ≈ 1.2·10⁶` haversines,
> under a second. Line 8 is `O(|best|² k)`.
>
> **`tol_miss` is a constraint, not an objective.** Adding the miss as a fourth objective
> would inflate `Λ` by another factor `N_4` (Thm 5.3) and, worse, would return routes that
> trade landfall accuracy against fuel — which is not a trade a voyage plan is allowed to
> make. Normative default `tol_miss = 1.5 h` where `h` is the grid spacing; the measured
> single-objective miss is `11.2 km` on a `0.25°` grid (CORE-THEOREM §8.1 R1), i.e. under
> half a grid diagonal.
>
> **The grid dilation of R1 applies per label, at the slowest label's time.** Required
> dilation is `|w| · t_max` where `t_max` is the **largest** arrival time on the front, not
> the time-optimal one. For the §8.2 voyage that is `|w| · t_max`; sizing it from the
> time-optimal solve alone under-dilates by `|w|·Δτ`, which is (5.32) again — and it
> fails **silently** (`comoving.required_dilation_m`, playbook S8b cause 1).

### 5.6.3 Where A1 fails

Under A1 the *whole* environment translates rigidly, so `Hs`, `Tp`, `μ_w` and the current
all shift together and `r̂(y)` is well defined. If only the current translates while the
wave field intensifies, the bottleneck risk carries the residual `R` of (C.8) and the
co-moving risk is approximate. The repair is CORE-THEOREM §8 step 6: one corrector sweep in
the ground frame seeded by the co-moving route, with the causality guard applied to `L_t^R`
rather than `L_t`. Measured leverage (Test 8.10): `r·L_t` falls from `1.31` (violated) to
`0.26` (satisfied) in the intensification and two-system regimes. The **median** cell
degrades by `4.5×` — de-advection trades a large gain in the worst cells for a modest loss
in benign ones, which is the right trade for a worst-case condition but is a trade.

---

## 5.7 Front extraction and knee selection

### 5.7.1 Extraction

> **Proc 5.18 (front extraction).**
> ```
> 1  F, labels ← Proc 5.15a                                  -- goal selection
> 2  for each ℓ in labels:                                   -- RE-INTEGRATE
> 3      walk ℓ's parent chain to x_A, collecting (node, theta, q)
> 4      recompute time, fuel, risk leg by leg from `rates()` and `sigma()`
> 5      assert the recomputed vector equals ℓ.cost to 1e-9 relative
> 6  attach the Cor 4.12 certificate gap (J − T_low)/T_low to each route
> 7  sort F ascending by objective 0
> 8  emit anchors: fastest = F[0]; cheapest = argmin_j=1; safest = lexmin (j=2, then j=0)
> ```
> Line 5 is not paranoia. It is the check that makes Thm 5.2(e) an *audited* claim rather
> than an architectural one, and it catches parent-chain corruption, throttle/heading
> mismatch, and any place a rounded value leaked into a stored cost. It costs `O(|F| · D)`.

### 5.7.2 Knee selection

Prop 5.1 said linear scalarisation cannot *find* the dents. It does not follow that the
operator cannot *choose* one — the front is already computed, so selection is a search over
a finite list, and a nonlinear selector is free.

> ### Prop 5.16 (Chebyshev selection reaches every non-anchor Pareto point, dents included)
> Let `F` be a finite attainable set, `z*_j := min_{q∈F} q_j` the **ideal point**, and let
> `p ∈ PMin(F)` satisfy `p_j > z*_j` for every `j` (`p` is not an anchor). Put
> `λ_j := 1/(p_j − z*_j) > 0`. Then `p` minimises the weighted Chebyshev scalarisation
> ```
> g_λ(q)  :=  max_j  λ_j ( q_j − z*_j )                                    (5.33)
> ```
> over `F`. Anchors are reached by `λ = e_j`.
>
> **Proof.** `g_λ(p) = max_j λ_j(p_j − z*_j) = max_j 1 = 1`. Suppose `q ∈ F` has
> `g_λ(q) < 1`. Then `λ_j(q_j − z*_j) < 1` for **every** `j`, i.e. `q_j − z*_j < p_j − z*_j`,
> i.e. `q_j < p_j` for every `j`. Hence `q ≺ p`, contradicting `p ∈ PMin(F)`. So no `q`
> beats `p` and `p` is a minimiser. For an anchor `p` with `p_{j₀} = z*_{j₀}`, `λ = e_{j₀}`
> gives `g_λ(p) = 0`, the global minimum. ∎
>
> **Verified on the §5.1.2 instance.** `z* = (91.094 h, 324.65 t, 0.08)`. For the dent point
> M2, `p − z* = (47.466, 395.52, 0.22)` and `λ = (0.021 068, 0.002 528 3, 4.545 5)`. Any `q`
> with `g_λ(q) < 1` would need `time < 138.560`, `fuel < 720.17` **and** `risk < 0.30`
> simultaneously; the only routes with `risk < 0.30` are N1–N4, and the fastest of those,
> N1, burns `924.58 t > 720.17 t`. No such `q` exists. **M2 — invisible to all 20 301
> weight vectors of §5.1.2 — is the exact minimiser of a Chebyshev scalarisation.**

> ### Prop 5.17 (Chebyshev cannot be used *inside* the solve)
> The functional `g_λ` of (5.33) is **not decomposable**: there is no binary operation `⊙`
> with `g_λ(c ⊗ e) = g_λ(c) ⊙ g_λ(e)` for all `c, e`. Hence no scalar dynamic program
> computes it, and the vector-valued labels of §5.4 are necessary, not merely convenient.
>
> **Proof.** Take `k = 2`, additive accumulation, `λ = (1,1)`, `z* = 0`. Let `c = (1,0)` and
> `c' = (0,1)`, so `g_λ(c) = g_λ(c') = 1`. Let `e = (0,5)`, `g_λ(e) = 5`. Then
> `g_λ(c ⊗ e) = g_λ((1,5)) = 5` while `g_λ(c' ⊗ e) = g_λ((0,6)) = 6`. Since
> `g_λ(c) = g_λ(c')` and the increment is the same, `g_λ(·⊗e)` is not a function of
> `g_λ(·)`. ∎
>
> **This closes the loop of §5.** Linear scalarisation is decomposable but cannot reach the
> dents (Prop 5.1). Chebyshev selection reaches the dents but is not decomposable
> (Prop 5.16, 5.17). The only construction that does both is to propagate the whole vector
> and select afterwards — which is what Kumar & Vladimirsky (2010) do and what §5
> implements, with the bucketing of Tsaggouris & Zaroliagis (2009) to keep `Λ` finite.

**Selection procedures, all on the extracted front `F` after range normalisation
`ẑ_j = (z_j − z*_j)/(z^{nadir}_j − z*_j) ∈ [0,1]`** (normalisation is mandatory — no knee
measure is scale-invariant, and time in seconds against fuel in kilograms would make the
choice an artefact of units):

| method | definition | complexity | when |
|---|---|---|---|
| **Chebyshev knee (normative default)** | `argmin_{z∈F} max_j w_j ẑ_j`, `w = 1` unless the operator supplies preferences | `O(\|F\|·k)` | always compute it |
| **max-bend (`k = 2` only)** | `argmax` perpendicular distance from `ẑ` to the chord joining the two anchors | `O(\|F\|)` | 2-objective displays |
| **trade-off ratio** (Rachmawati & Srinivasan 2009) | `argmax_z min_{z'≠z} [ Σ_j max(0, ẑ'_j − ẑ_j) ] / [ Σ_j max(0, ẑ_j − ẑ'_j) ]` | `O(\|F\|²·k)` | `k ≥ 3`, when the Chebyshev knee sits at an anchor |
| **hypervolume contribution** | `argmax HV(F) − HV(F \ {z})` w.r.t. the nadir | `O(\|F\| log\|F\|)` per HV at `k=3` (Beume et al. 2009); `O(\|F\|² log\|F\|)` for all contributions | diagnostic, not for selection |

**Worked knee on the §5.1.2 instance.** `z* = (91.094, 324.65, 0.08)`,
`z^{nadir} = (183.605, 924.58, 0.62)`, ranges `(92.511 h, 599.93 t, 0.54)`.

| route | `ẑ_time` | `ẑ_fuel` | `ẑ_risk` | Chebyshev `max` |
|---|---|---|---|---|
| S1 | 0.000 00 | 0.543 85 | 1.000 00 | 1.000 00 |
| S2 | 0.088 11 | 0.318 67 | 1.000 00 | 1.000 00 |
| S3 | 0.223 97 | 0.124 74 | 1.000 00 | 1.000 00 |
| S4 | 0.355 42 | 0.000 00 | 1.000 00 | 1.000 00 |
| M1 | 0.374 39 | 0.956 37 | 0.407 41 | 0.956 37 |
| **M2** | **0.513 09** | **0.659 27** | **0.407 41** | **0.659 27** ← knee |
| M3 | 0.733 34 | 0.405 37 | 0.407 41 | 0.733 34 |
| M4 | 0.954 18 | 0.241 78 | 0.407 41 | 0.954 18 |
| N1 | 0.413 98 | 1.000 00 | 0.000 00 | 1.000 00 |
| N2 | 0.554 75 | 0.692 66 | 0.000 00 | 0.692 66 |
| N3 | 0.777 53 | 0.429 72 | 0.000 00 | 0.777 53 |
| N4 | 1.000 00 | 0.260 28 | 0.000 00 | 1.000 00 |

The equal-weight Chebyshev knee is **M2 (138.56 h, 720.17 t, worst-moment risk 0.30)**, a
route no weight vector can produce. The runner-up, N2 at `0.692 66`, is the corresponding
northern route.

### 5.7.3 What to hand the operator

Not a route. A **table plus the local exchange rates**, because a decision-maker chooses by
marginal rate, not by absolute cost.

| pair | Δtime | Δfuel | Δrisk | reading |
|---|---|---|---|---|
| S1 → S2 | +8.151 h | **−135.09 t** | 0 | slowing from full to 75 % throttle saves **16.6 t/h** |
| S2 → S3 | +12.568 h | −116.34 t | 0 | **9.3 t/h** |
| S3 → S4 | +12.161 h | −74.84 t | 0 | **6.2 t/h** — diminishing returns, the fuel knee is here |
| S2 → M2 | +39.315 h | +204.34 t | **−0.32** | leaving the southern lane costs 1.6 days and 204 t |
| M2 → N2 | +3.854 h | +20.03 t | **−0.22** | the last 0.22 of risk costs only **3.9 h and 20 t** |

The final row is the kind of statement that changes a decision, and it exists only because
the front contains M2. A weight-sweep router shows S2 and N2 and reports the difference as
"43.2 h and 224.4 t buys 0.54 of risk" — hiding that the **last 41 % of the risk reduction
(M2 → N2) costs only 8.9 % of that time and 8.9 % of that fuel**, and that the first 59 %
costs the other 91 % of both. The marginal rate is the decision; the endpoints conceal it.

**Report with every front:**

| quantity | why |
|---|---|
| `ε`, `Λ_peak`, cells occupied | the approximation actually used, against Thm 5.3 |
| `μ_peak` (displacement events), if instrumented | the exponent in Thm 5.2(c) |
| certificate gap per route (Cor 4.12) | the **primary** guarantee (ERRATA E6) |
| `tol_miss` and the achieved miss per route | Prop 5.15 — without it the front is of the wrong voyage |
| `|𝔏*|` distribution over cells | `≡ 1` means the throttle family collapsed (playbook S5) |
| bucket-queue monotonicity violations | must be 0 (playbook S1) |
| whether A1 held, and `r·L_t` before/after | whether §5.6's licence applies |

---

## 5.8 Summary of §5's claims and their status

| # | Claim | Status |
|---|---|---|
| 5.1 | Linear scalarisation returns only supported points; an explicit 12-route instance where the whole middle lane (4 of 12 Pareto routes) is invisible to all `λ ≥ 0` | **Proved** (Prop 5.1) and **verified** by exhaustive sweep of 20 301 weight vectors |
| 5.4 | `+` and `max` both give an isotone, inflationary ordered monoid; label setting is correct over it | **Proved** (Prop 5.4), with each hypothesis's failure exhibited |
| 5.5 | No weighted sum of additive objectives expresses bottleneck risk | **Proved** four ways (path, additivity, algebra, order) |
| 5.6d | Per-edge throttle pruning is lossless | **Proved**; fails under inter-leg coupling, which is handled by D4 + Cor 4.12 instead |
| 5.8 | Bottleneck axes are *exactly* bucketable with a one-time `εR` error; additive axes are not | **Proved.** This is the technical content of the E11 re-scoped claim |
| 5.3 | `Λ ≤ ∏ N_j`, no `D`-dependence: `5.5·10⁴` (E7.2 form), `1.19·10⁴` with a bottleneck axis, against `3.9·10⁹` for increment bucketing | **Proved** (Thm 5.3); numbers derived in §5.4.1, §5.4.4 |
| 5.2a | Arrival time is never approximated | **Proved**, unconditional |
| 5.2b | One-cell `(1+ε)` bound per node, `D`-independent | **Proved**; **measured** at `+0.0818` against a `0.10` bound |
| 5.2c | Per-path bound is `(1+ε)^{μ}`, `μ ≤ min(D, N_j)`; the uniform `(1+ε)` of ERRATA E7 is **false as stated** | **Proved**, with a 4-node counterexample **reproduced against `labels.py`** |
| 5.12a | `μ = O(1)` under a non-degeneracy condition | **Conjecture.** Missing: any bound on the recurrence of displacement events |
| 5.14 | The co-moving reduction makes throttle families `t`-free: `Λ`-fold fewer metric evaluations, causality vacuous for every label, no per-label wait relaxation | **Proved** from Thm C.1; the `Λ`-fold factor is `10–40` measured |
| 5.15 | With labels the goal is a `Λ`-way selection; landfalls of one node's labels spread by `\|w\|Δτ` = **1 053 km** on the §8.2 voyage | **Proved**; the number is derived from measured `w` and the §5.1.2 front span |
| 5.16 | Chebyshev selection reaches every non-anchor Pareto point, including the dents; on the §5.1.2 instance the equal-weight knee **is** a dent point | **Proved** and **computed** |
| 5.17 | Chebyshev is not decomposable, so vector labels are necessary | **Proved** |

**Novelty, stated once more so it is not mistaken.** Nothing in §5 is claimed as new except
Prop 5.8 (the exact bucketability of bottleneck axes and its algebraic cause) and the
throttle-family treatment of D1 — and both only in the front-propagation setting, per
ERRATA E11. The front propagation is Kumar & Vladimirsky (2010). The value bucketing is
Tsaggouris & Zaroliagis (2009). The label-setting correctness argument is Martins (1984).
The queue is Dial (1969). The novelty of KAIROS is Theorem C.1, in `CORE-THEOREM.md`, and
§5 is what rides on it.
