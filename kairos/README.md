# KAIROS

**K**inematic **A**dvection-**I**solating **R**eduction for **O**ptimal **S**hip-routing

SIH 2026 · PS **SIH1658** — *Development of a versatile and fast algorithm for optimal ship routing*
Team **Delta Force**

---

## The claim, in one paragraph

Every method in the ship-routing literature treats the time-dependence of weather as an
obstacle: it breaks Dijkstra's FIFO property, it forces time into the state, or it forces a
full space-time HJB march. But on routing timescales the dominant part of that
time-dependence is not *evolution* — it is *motion*. A cyclone translates at 5–8 m/s along a
track that is steady for days. And motion is frame-dependent.

**KAIROS changes frames.** In coordinates co-moving with the weather, the routing problem
becomes exactly **stationary**: one single-pass anisotropic solve with no causality condition
at all, followed by a scalar root find for the interception time. The hardest theoretical
obstacle in time-dependent routing turns out to be an artefact of the ground frame.

Read [spec/CORE-THEOREM.md](spec/CORE-THEOREM.md) first. It is the paper.

---

## Status — what is proved, what is measured, what is not done

This project has been through one adversarial referee pass, which found **11 blocking errors
and 18 major ones** in the first draft, including two prior-art citations that killed the
original novelty claims outright. All of that is recorded in
[spec/ERRATA.md](spec/ERRATA.md) rather than quietly dropped. The current claims are what
survived.

| | Claim | Evidence |
|---|---|---|
| ✅ | **Theorem C.1**, the Co-Moving Reduction: rigidly-advected routing is *exactly* a stationary Finsler problem + a scalar root find | Proved; bijection verified to **9.77e-14 m/s** where theory says exactly 0 |
| ✅ | The reduction eliminates *temporal discretisation error*, not just temporal complexity | Measured: excess `2.8e-14` vs `6.7e-3` m/s on the same grid |
| ✅ | Where advection is not rigid, the reduction still moves a solve from **unlicensed to licensed** | Measured: causality `r·L_t` **1.31 → 0.26**; 4.6–5.0× at p99 |
| ⚠️ | …but the *median* cell gets ~4.5× worse — it is a worst-case trade, not a free win | Measured and reported, §7 |
| ✅ | **End to end on a 3698 km voyage**: co-moving 139.996 h vs ground-frame Dijkstra 141.211 h | **0.860 % apart** — inside the metrication floor, i.e. the expected result. `demo/run_comoving.py` |
| ❌ | Phase correlation to estimate the advection velocity | **Tried and failed** (`(−0.74, 0)` vs true `(2.0, 0.5)`); replaced by minimising the residual causality constant directly |
| 🚧 | Full ε-Pareto multi-objective solve, certificate, spec files | Modules written and unit-verified; **integration not finished** — two workflows died on a session limit |

### Three bugs found by building it, all of which fail *silently*

Recorded because they cost real time and none is visible in the mathematics:

1. **`Grid.latlon` wraps negative column indices** like a Python list. A row-geometry cache
   referenced from column 0 therefore turned every westward offset into a wrap-around leg —
   **4020 km instead of 57.9 km**, bearing 142° wrong, arrival time 10 419 h instead of 141 h.
2. **The co-moving grid must be dilated by `|w|·t_max`** opposite to `w`, or the target node
   `y = x_B − w t*` is outside the domain. Cost: a **104.5 km** landfall miss that a full-grid
   scan could not reduce. Fixed → 11.2 km.
3. **The interception root find must not select the goal node.** `g(t)` is a step function
   when `T` is sampled at the nearest node, so bisection converges to a discontinuity.
   Solve the interception condition directly on the grid instead.

Nothing in the table above is asserted without a number next to it.

---

## Layout

```
spec/
  CORE-THEOREM.md      ← THE RESULT. Theorem C.1, proof, numerical verification, algorithm
  ERRATA.md            ← 11 blockers + 18 major errors found by the referee, and the repairs
  01-formulation.md    the control problem, powering, throttle, seakeeping ban set
  02-metric.md         indicatrix, gauge, Randers closed form, the shifted indicatrix
  03-causality.md      the FIFO condition — and why the reduction makes it vacuous
  04-algorithm.md      the full pipeline, data structures, pseudocode
  05-multiobjective.md ε-Pareto labels, bottleneck objectives, throttle families
  06-numerics.md       root finds, stable branches, degenerate cases, indexing traps
  07-complexity.md     convergence, complexity, memory, parallelism
  08-validation.md     test vectors and protocols, with the measured results
  CONTRACT.md          normative symbols, numbering, design decisions D1–D7
  00-overview.md       SUPERSEDED — related-work survey only; carries the 11 blockers
handbook/
  IMPLEMENT-THIS.md    ← self-contained brief. Hand this to an implementer and nothing else.
  reference_min.py     ← working 300-line implementation, stdlib only, 15/15 self-tests pass
  PROMPT.md            handoff prompt for a coding agent, plus what good output looks like
  00-porting-guide.md  M0–M8 build order with falsifiable acceptance gates
  01-golden-vectors.md exact reference values, computed at 50 digits
  02-debugging-playbook.md  symptom → cause → discriminating test
  03-language-notes.md C++/Rust/Julia/Go/Python, and the invariants every port must share
src/kairos/            reference implementation (comoving, metric, grid, labels, bucketqueue,
                       powering, seakeeping, environment, polish, geodesy, types)
demo/run_comoving.py   end-to-end: co-moving vs conventional, on the same grid
tests/comoving/        the verification that settles Theorem C.1
docs/                  first draft — SUPERSEDED, kept for provenance
```

**Reading order:** `spec/CORE-THEOREM.md` → `spec/ERRATA.md` → `spec/01-` … `08-`.

**To hand this to someone else to implement:** send only
`handbook/IMPLEMENT-THIS.md` + `handbook/reference_min.py`, and use `handbook/PROMPT.md`.

---

## Verify it yourself

```bash
cd kairos/tests/comoving && python -u test_c1_bijection.py
```

That prints the per-leg bijection residual. Theory says exactly zero; it should print `~1e-13`.

```bash
cd kairos/tests/comoving && python -u test_8_10_causality_constant.py
```

That prints the causality constant in both frames across three regimes, including the one
where the reduction only partly helps.

---

## Honest limitations

- **Assumption A1** (rigid advection) is exact only for an isolated, coherently translating
  system. It holds well for tropical cyclones and monsoon surges over 2–5 days — the cases
  that matter most for Indian Ocean safety routing — and degrades for merging or rapidly
  deepening systems, where the reduction becomes a preconditioner rather than a solution.
- **Assumption A2** (the ship can outrun the system) is required for the interception time to
  exist. Where it fails, the correct answer really is *you cannot escape this storm*, and the
  metric says so via a one-sided reachable cone.
- The multi-objective apparatus, the optimality certificate and the end-to-end demo are
  **specified and partly built, not finished**. See the 🚧 row above.
- No hindcast validation against AIS tracks yet. The algorithm now runs on real ocean data
  (see below), but nobody has checked its routes against what real ships actually did.

---

## It is not an ocean algorithm

`src/kairos/core.py` knows nothing about ships, weather, latitude or currents. Abstractly the
result is a **reduction**: a minimum-time problem whose cost field *translates* becomes an
ordinary **stationary** shortest-path problem, solvable by whatever you already use.

```bash
python demo/run_traffic.py     # city traffic, congestion shockwave — no ocean anywhere
```

| Planner | Arrival | vs truth |
|---|---|---|
| Time-dependent Dijkstra (ground truth) | 19.41 min | — |
| Frozen-field Dijkstra (assume the jam stays put) | 20.77 min | **+7.02 %** |
| **KAIROS co-moving** | 19.49 min | **+0.40 %** |

12 km city, 200 m blocks, jam wave at 11.4 km/h. LWR kinematic wave theory says congestion
propagates as a shockwave — an advected cost field, exactly like a weather system.

**The limit, stated plainly:** the reduction needs the *space* to be translation-invariant,
because in co-moving coordinates the space is what shifts. Continuous space, regular lattices
and 1-D corridors qualify. An **arbitrary irregular graph does not** — a real road network in
co-moving coordinates becomes a moving graph, which is worse than moving costs. For those, use
ordinary FIFO time-dependent Dijkstra.

## Complexity — and why "faster" is the wrong claim

See [spec/COMPLEXITY-COMPARISON.md](spec/COMPLEXITY-COMPARISON.md). Summary:

**KAIROS is 2.5–6.4× faster than conventional time-dependent Dijkstra**, and the margin grows
with field-evaluation cost — the direction real forecast data pushes.

| field cost | conventional | **optimised** | |
|---|---|---|---|
| cheap | 0.357 s | **0.140 s** | 2.55× faster |
| ~200 flops | 2.048 s | **0.421 s** | 4.87× faster |
| ~1000 flops | 8.027 s | **1.254 s** | **6.40× faster** |

The win is the **edge-midpoint cache**, available *only* because the co-moving field is
stationary: every undirected edge is relaxed twice from the same midpoint, and a time-dependent
solver must re-interpolate because its two visits happen at different times.

**Precision: 0.57 % mean error with a 32-neighbour stencil** (5.49 % at 8), measured against the
exact Randers answer over 13 headings. The speed headroom pays for the richer stencil.

**Three claims were retracted along the way**, each after being checked rather than assumed:
the single-solve departure-time sweep, the eager-precomputation crossover, and an earlier
conclusion that "the speed avenue is closed" — profiling found the real bottleneck was field
evaluation (61 % of runtime), not solver overhead.

## Data is optional, by construction

**A\* does not ship with a map. KAIROS does not ship with an ocean.** The solver consumes one
interface — `field.at(lat, lon, t) -> Env` — and cannot tell whether the numbers came from a
satellite product or a two-line function.

This is enforced, not merely intended: an AST scan asserts that **no core module imports
`kairos.data`, xarray, netCDF4, cdsapi or requests**, and the solver is then re-run with the
data layer disabled to prove it still works. Both checks pass.

```bash
python demo/run_real_data.py
```

runs the identical solver twice:

| Run | Field | Result |
|---|---|---|
| 1 | **live HYCOM currents** over OPeNDAP, 501×413 grid, no credentials | arrival **118.55 h**, land mask from data NaNs (73.1 % navigable) |
| 2 | **analytic field** — no data, no network, no files | arrival **105.86 h** |

Both on a 3182 km Kochi → Gulf of Aden leg; no-current baseline is 122.8 h, so the HYCOM run
picking up a net favourable 4 h is physically sensible.

Adapters live in [src/kairos/data.py](src/kairos/data.py) and cover ERA5, INCOIS, CMEMS,
WaveWatch III and HYCOM through one generic NetCDF/OPeNDAP reader plus a variable-name map.
ERA5 and INCOIS need your own credentials — `data.era5_request_template()` prints the exact
CDS script to run; this project does not handle credentials.

---

## Prior art

Searched and not found: any application of a co-moving/Galilean reduction to weather routing
or time-dependent Zermelo navigation. Credited neighbours: Zermelo (1931); Taylor (1938) for
the frozen-field hypothesis that is A1's ancestor; Bao–Robles–Shen (2004); Sethian–Vladimirsky
(2003); Vladimirsky (2006) for causality conditions our step 3 removes rather than checks;
Kumar–Vladimirsky (2010); Tsaggouris–Zaroliagis (2009); Lolla–Lermusiaux (2014);
Markvorsen (2025) for the time-dependent-only Zermelo case.
