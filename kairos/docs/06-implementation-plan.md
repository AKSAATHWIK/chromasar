# 6. Implementation plan

Constraint we are building under: **no GPU** (Ryzen 7730U, 8 cores). Everything below is
sized for that. Nothing here needs training, so that constraint costs us nothing.

---

## 6.1 What to reuse from `../shiprouting/`

| Existing | Verdict |
|---|---|
| `forcing.py` — field sampling, haversine, bearings | **Reuse as-is.** Add trilinear interpolation in `(lat, lon, t)` and an ensemble-member axis. |
| `ship.py` — powering, wave penalty, speed loss | **Reuse the structure, extend the physics.** It becomes the `sigma()` provider of §2.6. Split the scalar `risk()` into the separate criteria S1–S7 of §1.4 so the ban set is a set, not a number. |
| `Grid` + `_geom` precompute in `router.py` | **Reuse.** The per-row geometry cache is exactly right and generalises to the metric table. |
| `astar()` | **Keep, do not delete.** It becomes the *baseline* every benchmark is measured against. Its value to us is now scientific. |
| `great_circle_route`, `grid_line_route` | **Keep.** Second and third baselines. |
| `pareto_sweep` | **Keep as a demonstration of the convex-hull defect** — plot its output against the KAIROS front on the same axes. That plot is the single most persuasive slide in the deck. |

Nothing gets thrown away. The old router becomes the control group.

---

## 6.2 Module layout

```
kairos/
  docs/                     # this theory (done)
  src/
    metric.py               # sigma(), F(), Randers fast path, metric table build   [§1-2]
    seakeeping.py           # S1-S7 ban set, IMO MSC.1/Circ.1228                    [§1.4]
    vessel.py               # vessel registry: bulker / container / tanker / ferry  [§1.3]
    causality.py            # L_t estimation, FIFO guard, wait relaxation           [§3]
    stencil.py              # local anisotropy, near-front sets                     [§4.3]
    labels.py               # Pareto label sets, eps-bucket pruning                 [§4.4]
    sweep.py                # the ordered-upwind sweep itself                       [§4.1-4.5]
    polish.py               # Zermelo shooting, notch projection                    [§4.6, 2.6]
    repair.py               # localised front repair on forecast update             [§4.7]
    certify.py              # optimality certificate, gap reporting                 [§4.5]
  tests/
    test_randers.py         # closed-form (2.1) vs numerical gauge
    test_zermelo_exact.py   # uniform flow / linear shear / Rankine vortex
    test_fifo.py            # constructed L_t violation -> wait relaxation fires
    test_pareto_eps.py      # eps vs eps/4 front comparison (Rmk 5.4.1)
    test_convergence.py     # grid refinement study, measured order
    test_vs_baseline.py     # KAIROS vs astar on identical inputs
```

---

## 6.3 Build order

Each phase ends with something demonstrable. Do not proceed until the phase's test passes.

**Phase 1 — the metric (2 days).**
`metric.py` + `seakeeping.py`. Deliverable: a **polar plot of the indicatrix** `𝒱(x,t)` at a
chosen point and time — the disc, the current offset, the wave dent, the parametric-roll
notch. This one figure explains the entire project to a non-specialist in ten seconds and
should go on slide 3.
*Gate:* `test_randers.py` — numerical gauge matches (2.1) to `1e-10` when waves and bans are
off.

**Phase 2 — single-objective sweep (3 days).**
`stencil.py` + `sweep.py`, time only, no labels. Deliverable: arrival-time field `T(x)` as a
contour plot with the optimal route as the steepest-descent curve. Compare against `astar`.
*Gate:* `test_zermelo_exact.py` — in a uniform current the route is a single constant
heading, **zero intermediate waypoints**. If waypoints appear, the implementation is wrong;
this is the sharpest available test and it comes free from (3.7).

**Phase 3 — causality (1 day).**
`causality.py`. Deliverable: a map of `h·L_t` over the domain with flagged cells, plus a
constructed cyclone case where the wait relaxation fires and the route visibly holds off.
*Gate:* `test_fifo.py`.

**Phase 4 — Pareto labels (3 days).**
`labels.py`. Deliverable: the 3-D front (time, fuel, peak risk) as a scatter with 20–50
distinct routes drawn on one map, coloured by their trade-off. Overlay `pareto_sweep`'s five
points to show what scalarisation misses.
*Gate:* `test_pareto_eps.py`.

**Phase 5 — heuristic, certificate, polish (2 days).**
`certify.py` + `polish.py`. Deliverable: the smooth route (no staircase) and a printed
optimality gap, e.g. `route is within 0.7 % of the proven lower bound`.
*Gate:* `test_convergence.py` — measured convergence order reported, whatever it turns out
to be.

**Phase 6 — repair + demo (3 days).**
`repair.py` + the web front end (reuse `../webapp/`). Deliverable: a slider that advances the
clock, drops a new forecast, and re-optimises the remaining route in under a second with a
timing readout.

Total ≈ **14 working days** for one or two people. The theory is done, which is the part
that usually eats the time.

---

## 6.4 Data

Documented in `../shiprouting/DATA.md`; the additions KAIROS needs:

| Field | Source | Note |
|---|---|---|
| Surface currents `u, v` | INCOIS / HYCOM / CMEMS GLOBCURRENT, 1/12° daily | The Indian-Ocean specificity the PS asks for comes from using INCOIS products, not a global default |
| Waves `H_s, T_p, μ` + 2-D spectra | INCOIS WAM/WW3 Indian Ocean, 3-hourly | Spectra only needed for the RAO path; `H_s,T_p,μ` suffice for STAwave-1 |
| Wind `U10, V10` | IMD/NCMRWF or ERA5 reanalysis for hindcast validation | |
| Bathymetry | GEBCO 2024 | UKC screening and shallow-water resistance correction |
| Land / TSS / HRA | GSHHG, IMO TSS polygons, IRTC corridor | Straight into `Ω` as `F = ∞` |
| Ensemble | ECMWF ENS (51 members) | Only for the CVaR extension of §6.6 |

**Say "INCOIS" and mean it.** The PS is written by people for whom "customised for the
Indian Ocean region" means using Indian operational products with their actual grids and
update cycles, and handling the SW-monsoon Somali Current and the Bay of Bengal cyclone
season as first-class cases, not as generic weather.

---

## 6.5 Validation protocol

Four levels, weakest to strongest. Report all four.

1. **Analytic.** Randers closed form (2.1); Zermelo geodesics in uniform flow, linear shear,
   and a Rankine vortex — all have known exact solutions. Report max error vs `h`.
2. **Self-consistency.** Grid refinement `h = 1°, 0.5°, 0.25°, 0.125°`: report measured
   convergence order. Also `ε` refinement per Remark 5.4.1.
3. **Against the baselines.** Same fields, same vessel, same ports: KAIROS vs `astar` vs
   great circle. Report time, fuel, peak risk, wall-clock, nodes expanded. **The comparison
   must be on identical inputs** — the existing `grid_line_route` already shows the team
   understands why, which is a good sign.
4. **Against reality.** Take historical AIS tracks for Indian Ocean voyages (Mumbai–Jebel
   Ali, Chennai–Singapore, Kochi–Suez), pair with ERA5 hindcast for the actual dates, and
   ask: what would KAIROS have advised, and what would it have saved against what the ship
   actually did? **This is the number that wins the round.** A measured "would have saved
   4.2 % fuel on 30 real voyages" beats any amount of theory.

Also report, as headline honesty metrics: the fraction of FIFO-flagged cells, the max
`h·L_t`, and the optimality certificate gap. Nobody else will show their error bars.

---

## 6.6 Scoped extensions (say these are future work, do not claim them)

- **Ensemble robustness via nested CVaR.** As flagged in §5, static CVaR breaks the DP
  principle; the time-consistent version adds a state dimension. Correct and tractable, but
  a second project.
- **Rudder-rate dynamics** replacing the dwell-time abstraction of §2.5, tightening
  Theorem 5.3 into a genuine kinodynamic constraint.
- **Engine/RPM as an explicit control** rather than solving `P = P_MCR`, enabling exact
  SFOC-optimal slow steaming per leg.
- **Convergence rate for the joint `(h, ε) → 0` limit** — genuinely open.
- **Fleet-level routing** with berth-slot and port-congestion coupling.

---

## 6.7 What to put in front of the jury

In order of persuasiveness:

1. The **indicatrix figure** (Phase 1). It makes the idea obvious.
2. The **Pareto front plot** with `pareto_sweep`'s five points overlaid, showing the routes
   that scalarisation provably cannot find.
3. The **AIS hindcast saving**, in tonnes and dollars, over 30 real voyages.
4. The **optimality certificate**: "within 0.7 % of a proven lower bound."
5. The **live re-optimisation** on forecast update, timed on screen.
6. The four theorems, one slide, stated not proved, with the proofs in an appendix that
   exists — which is the point of `docs/05-proofs.md`.

The thing to lead with is not "we used a fancy method." It is: **ship routing is a Finsler
geodesic problem, nobody has treated it as one for the Indian Ocean, and treating it as one
gives you a certificate of optimality that no existing tool provides.**
