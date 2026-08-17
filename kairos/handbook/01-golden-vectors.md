# Golden Test Vectors

Every number below was computed at 50-digit precision from the closed forms and
cross-checked against an independent brute-force evaluation. They are **exact reference
values**, not observed outputs of our implementation — so they validate *any* implementation,
including ours. If your port disagrees, your port is wrong (or you have found a bug in this
table, which is also worth knowing — the arithmetic is shown so you can check it).

Tolerances: match to **12 significant figures** in IEEE double. Anything looser is hiding a
bug; anything tighter is asking for trouble from the last-bit behaviour of `sqrt`.

---

## G1 — Spherical geometry

`R_E = 6 371 000.0 m` exactly. Haversine formula. Bearings in degrees from true north,
clockwise.

| From | To | Distance | Initial bearing |
|---|---|---|---|
| 0.00 N, 0.00 E | 0.00 N, 90.00 E | **10 007.543 398 010 3 km** | **90.000 000°** |
| 18.95 N, 72.95 E (JNPT) | 29.92 N, 32.55 E (Suez) | **4 243.611 km** | **294.619°** |
| 18.95 N, 72.95 E | 25.01 N, 55.06 E (Jebel Ali) | **1 961.706 km** | **293.284°** |
| 13.09 N, 80.29 E (Chennai) | 1.26 N, 103.85 E (Singapore) | **2 908.549 km** | **114.975°** |
| 9.96 N, 76.24 E (Kochi) | 12.79 N, 45.02 E (Aden) | **3 415.766 km** | **278.307°** |

**Self-checking:** the first row must equal `2πR_E/4 = 10 007.543 398 010 286 km` exactly.
If it does not, your radius constant or your `asin` guard is wrong. This one row catches
most geodesy errors on its own.

**Round-trip invariant** (test at all five pairs):
`destination(A, initial_bearing(A,B), haversine(A,B)) == B` to `1e-9 rad ≈ 6 mm`.

---

## G2 — The Randers metric

Setup: through-water speed `V_s = 7.2 m/s` (13.9973 kt), no waves, no bans, uniform current.
Decompose the current relative to the requested unit direction `u` into along-track `c_∥`
and cross-track magnitude `|c_⊥|`.

```
σ(u) = sqrt(V_s² − |c_⊥|²) + c_∥          [speed made good, m/s]
F(u) = 1 / σ(u)                            [metric, s/m]
```

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

**The arithmetic, so you can check it by hand:**
- T2: `7.2 + 1.5 = 8.7`. T3: `7.2 − 1.5 = 5.7`. Both exact in binary? No — but exact in
  decimal to the printed digits, and the *difference* is exactly representable.
- T4: `sqrt(7.2² − 1.5²) = sqrt(51.84 − 2.25) = sqrt(49.59) = 7.042 016 756 583 301 399 891`.
- T5: `c_∥ = 1.5·cos 30° = 1.299 038 105 676 658`, `|c_⊥| = 1.5·sin 30° = 0.75`,
  `σ = sqrt(51.84 − 0.5625) + 1.299 038… = sqrt(51.2775) + 1.299 038… = 8.459 869 063 044 66`.
- T6: `7.2 − 6.84 = 0.36`, so `F = 1/0.36 = 2.7̄`.

### T7 and T8 are the important ones

These are the two cases that *silently produce garbage* in a naive implementation, and they
are the reason they are in this table at all.

**T7 (`λ = V_s² − |c|² < 0`).** The closed form
`F = [sqrt(⟨v,c⟩² + λ|v|²) − ⟨v,c⟩]/λ` evaluated with `V_s = 7.2, c = 8.0` against the
current returns **`F = −1.25`** — a *negative cost*. It does not raise, it does not produce
NaN, it returns a plausible-looking finite number with the wrong sign. Dropped into a
shortest-path algorithm this creates negative cycles and the sweep will not terminate, or
worse, will terminate with an arrival time in the past.

> **Guard `λ > 0` before dividing. Every time. No exceptions.**

**T8 (`|c_⊥| ≥ V_s`).** The cross-track current exceeds the ship's speed through water, so
no heading holds the track: the ship is set sideways faster than it can crab back.
`sqrt` of a negative. Correct behaviour is `σ = 0`, `F = +∞`, direction excluded from the
update — **not** an exception, because this is a routine, physically meaningful condition in
the Agulhas and the Somali Current, and it must not abort a voyage plan.

Both cases must be *reachable in your test suite*, not just defended against in code.

---

## G3 — Numerical stability of the following-current branch

At `⟨v,c⟩ > 0` the naive form subtracts two nearly-equal numbers. Test at `|c|/V_s = 0.9`
with a pure following current, `V_s = 7.2`, `c = 6.48`, `v = (1, 0)`:

```
λ  = 51.84 − 41.9904 = 9.8496
⟨v,c⟩ = 6.48
naive:      F = ( sqrt(6.48² + 9.8496·1) − 6.48 ) / 9.8496
              = ( sqrt(41.9904 + 9.8496) − 6.48 ) / 9.8496
              = ( sqrt(51.84) − 6.48 ) / 9.8496
              = ( 7.2 − 6.48 ) / 9.8496                    ← catastrophic cancellation here
conjugate:  F = 1 / ( sqrt(51.84) + 6.48 ) = 1 / 13.68
```

Exact answer: `F = 1/13.68 = 0.073 099 415 204 678 362…`, i.e. `σ = 13.68 = 7.2 + 6.48` ✓.

The conjugate form is exact to the last bit. The naive form loses digits in proportion to
`⟨v,c⟩/λ`, which blows up exactly as `|c| → V_s` — i.e. precisely in the strong-current cells
where routing decisions actually matter. **Branch on the sign of `⟨v,c⟩`.**

---

## G4 — Zermelo, uniform flow: the sharpest test in the project

Zermelo's navigation formula:

```
dθ/dt = ∂v_c/∂x · sin²θ + (∂u_c/∂x − ∂v_c/∂y)·sin θ cos θ − ∂u_c/∂y · cos²θ
```

In a **uniform** current field every partial derivative vanishes, so `dθ/dt ≡ 0`
**identically**, for every heading, every position, every current magnitude.

**Expected:** `max |dθ/dt|` over the whole route `< 1e-14 rad/s` (i.e. floating-point zero),
and the recovered optimal route has **zero intermediate turns** — a single constant heading
from departure to arrival.

This test is worth more than any other single check. It requires no reference solution, it
is insensitive to grid resolution, and it fails loudly for: transposed east/north, wrong
finite-difference frame (degrees instead of metres), a `ζ` minimisation that is not actually
minimising, and any stencil that quantises heading. If your router emits waypoints in a
uniform current field, those waypoints are numerical artefacts and everything downstream is
suspect.

**Quantitative version.** With `V_s = 7.2 m/s` and a uniform current `c = (1.5, 0)` m/s,
travelling from `(0°N, 0°E)` to `(0°N, 5°E)` — due east along the equator, exactly
`5° · π/180 · R_E = 555 974.633 2 m`:

- crab angle: `arcsin(−c_⊥/V_s) = 0` (current is purely along-track) → heading exactly 090°
- `σ = 7.2 + 1.5 = 8.7 m/s`
- **expected arrival = 555 974.633 2 / 8.7 = 63 905.130 3 s = 17.751 425 h**

Against the current (0°E → 5°W): `σ = 5.7`, **arrival = 97 539.409 3 s = 27.094 280 h**.

The ratio `27.094 280 / 17.751 425 = 1.526 315 789 5` must equal the anisotropy
`Υ = (V_s+|c|)/(V_s−|c|) = 8.7/5.7 = 1.526 315 789 5` **to all printed digits** — the two are
computed by completely different code paths (a full sweep versus a one-line ratio), so
agreement to 10 figures is strong evidence both are right. This is the cheapest end-to-end
consistency check in the suite; run it on every commit.

---

## G5 — What to report

Any implementation claiming to be KAIROS should publish this table:

| Quantity | Symbol | Your value |
|---|---|---|
| Max error vs G2 golden vectors | — | should be `< 1e-12` |
| Max `\|dθ/dt\|`, uniform flow (G4) | — | should be `< 1e-14` |
| Arrival-time error vs G4 exact, at 1.0° / 0.5° / 0.25° | — | must **decrease** |
| Observed convergence order | `p` | report it, whatever it is |
| Fraction of cells needing wait relaxation | — | report it |
| Max `h·L_t` over the domain | — | must be `< 1` where not relaxed |
| Certificate gap on the returned route | — | `(J − T_low)/T_low` |
| Peak labels per node | `Λ` | report it |
| Bucket-queue monotonicity violations | — | should be 0; report if not |

Reporting the last five is what separates a validated implementation from a demo. Nobody
else in this space publishes their error bars.
