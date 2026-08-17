# Debugging Playbook

Keyed by **symptom**, because that is what you actually have when something is wrong.

Routing bugs are unusually nasty: the output is a curve on a map, and almost any wrong curve
looks like a reasonable route. You cannot eyeball correctness. Every entry below therefore
gives a *discriminating test* — one whose outcome differs between the candidate causes.

---

## S1 — The sweep never terminates, or arrival times go negative

**Cause, in order of likelihood:**

1. **`λ = V_s² − |c|²` used without a positivity guard.** In cells where the drift exceeds the
   ship's speed the Randers closed form returns a *negative* `F` (golden vector T7). Negative
   edge costs create negative cycles; label-setting never converges.
2. **`σ` allowed to be ≤ 0** and then inverted.
3. **Bucket queue receiving a key below its current minimum** and wrapping around the bucket
   ring.

**Discriminating test:** assert `F > 0 && isfinite(F)` at every metric evaluation and record
the `(lat, lon, t, u)` of the first violation. If it fires, it is (1) or (2). If it does not,
instrument the queue's `monotone_violations` counter — if that is non-zero it is (3).

**Fix:** guard `λ`, guard `σ`, and make the queue fall back to a heap rather than silently
mis-ordering.

---

## S2 — Routes bend the wrong way around a current or a storm

**Cause:** almost always an **east/north transposition** or a **sign flip** in the drift
decomposition. The second most common is wave direction "from" versus "towards".

**Discriminating test — the two-current probe.** Take a uniform current of `+1.5 m/s` due
**east**. Compute `σ` for travel due east and due west:

```
due east  → σ must be 8.7    (with the current)
due west  → σ must be 5.7    (against it)
due north → σ must be 7.042 016 756 583 30   (pure cross)
```

If east and west are swapped, your along-track sign is flipped. If north gives 8.7 or 5.7
instead of 7.042, your components are transposed.

**For the wave convention:** set `H_s = 6 m`, `μ_w` pointing due north (waves travelling
*towards* the north). A ship steaming due north is then in **following** seas and should lose
the *least* speed; steaming due south is in **head** seas and should lose the *most*. If
that is reversed, you have the meteorological "from" convention leaking in.

---

## S3 — Grid refinement does not reduce the error (the error plateaus)

This is the diagnostic that the scheme is **inconsistent**, and it is the single most
important failure to catch, because the routes still look fine.

**Cause:**
1. **The `ζ` minimisation over the front edge is being skipped**, or is minimising over the
   wrong interval, so the scheme is effectively a fixed-neighbour stencil. A fixed
   `m`-neighbour stencil has a consistency error that does **not** vanish as `h → 0` — it
   converges to a fixed `O(1/m²)` angular quantisation bias. That is exactly a plateau.
2. **The stencil radius is too small** for the local anisotropy, so the true characteristic
   direction is never in the search set.
3. The metric is being evaluated at the arrival time rather than the departure time (see S4).

**Discriminating test:** run the uniform-current case (G4) at 1.0°, 0.5°, 0.25°, 0.125° and
plot `log(error)` against `log(h)`. A slope near −1 is healthy. A slope near 0 is a plateau.
Then **disable the wide stencil but keep the `ζ` search**: if the plateau persists it is (1);
if the error becomes resolution-dependent again it was (2).

**Fix for (1):** verify the inner minimiser is actually being called and that its returned
`ζ` is genuinely interior (not always pinned at 0 or 1). Log the distribution of `ζ`; if it
is bimodal at the endpoints, the minimiser is broken.

---

## S4 — Everything converges, routes look right, answers are 2–5 % worse than they should be

The most dangerous class, because nothing looks wrong.

**Cause 1 — the metric is evaluated at the arrival time instead of the departure time.**
The update must be

```
T(x) = min over ζ:  T̃(ζ) + |x−ξ(ζ)| · F( x, T̃(ζ), û )
                                            ↑
                                   DEPARTURE time, not T(x)
```

Evaluating at `T(x)` makes the update implicit and circular. It still converges (to something)
and still produces plausible routes.

**Discriminating test:** run with a **stationary** field (no time dependence at all). If the
error disappears, it is the departure/arrival confusion; a stationary field makes the two
identical. That is a clean bisection.

**Cause 2 — inadmissible heuristic.** If the optimistic coarse solve takes its minimum over
the bare cell rather than the **dilated** cell, a fine path can clip a coarse-cell corner and
beat the heuristic's lower bound. A* with an inadmissible heuristic returns suboptimal
answers quietly.

**Discriminating test:** re-run with the heuristic disabled entirely (pure Dijkstra order).
If the answer improves, the heuristic is inadmissible. Then check the dilation.

**Cause 3 — labels bucketed on increments rather than values.** Symptom sharpens with route
length: short voyages fine, long voyages degrade. Test by comparing fronts on a route and on
the same route split into two halves solved sequentially.

---

## S5 — The Pareto front is a thin line instead of a spread

**Cause:** the SFOC model is effectively flat, so fuel is a monotone function of time and
there is nothing to trade off. Check `fuel_per_mile(q)` at `q = 0.35, 0.55, 0.75, 1.0` — it
must have an interior minimum near `q ≈ 0.75`. If it is monotone decreasing in `q`, your
`sfoc()` is constant and the physics has no trade-off in it.

**Second cause:** `metric.legs()` is returning only the max-throttle entry. If the time-only
fast path (`sigma_max`) is accidentally wired into the Pareto solver, every label has `q = 1`
and there is one route.

**Discriminating test:** print the length of `legs()` for a mid-ocean cell. It should be 2–4
after Pareto pruning. If it is always 1, that is the bug.

---

## S6 — Front is ragged; tiny changes in ε produce very different route sets

**Cause:** a **discontinuous risk function**. If `risk_level` is `1.0 if banned else 0.0`,
the objective jumps and the dominance pruning becomes unstable. `risk_level` must be
continuous in `(V, θ)` even though `violations()` is discrete. Build it as a smooth blend of
the margin to each criterion.

**Discriminating test:** sample `risk_level` along a heading sweep at fixed speed and plot it.
Any vertical jump is the bug.

---

## S7 — Wait relaxation fires everywhere (or never)

**Fires everywhere:** your `L_t` estimate is wrong — most likely you are differencing across
forecast frames without dividing by the frame interval in *seconds*, so `L_t` is inflated by
~10⁴. Sanity: `h·L_t` should be `≈ 0.05–0.15` for a 0.25° grid and 3-hourly forecasts.

**Never fires:** you may be estimating `L_t` from a field that is not actually time-varying
(a stationary test field), or the finite difference is being taken at a single time index.
Confirm on the constructed sharpness case from the spec, where it *must* fire.

---

## S8 — Zermelo polish does not converge

**Expected occasionally** — non-convergence at a **cut locus** is a real geometric feature,
not a bug. A cut locus is where two genuinely distinct optimal routes tie ("north or south of
the storm, both equally good"). The value function is non-smooth there and Newton has nothing
to converge to.

**Correct behaviour:** cap at 8 iterations, return the unpolished grid route, and *flag the
leg*. Surfacing "there are two equally good options here" is a feature worth showing the
operator, not an error to hide.

**It is a bug if:** it fails to converge in a *uniform* field. There, `dθ/dt ≡ 0` and the
shooting problem is trivial — one Newton step should nail it. Failure there means the
variational derivative is wrong (check its sign) or the RK4 integration is in the wrong frame
(degrees where it should be metres).

---

## S8b — Co-moving solve: route is plausible but lands in the wrong place

Three distinct causes, all of which produce a *converged, sensible-looking* route. Measured
values are from the actual build, not hypothetical.

1. **Co-moving grid not dilated.** The solve lives in `y = x − w t`, so the target node
   `y = x_B − w t*` must be inside the grid, and it sits `|w|·t*` away from `x_B`. On a 140 h
   voyage with `w = (1,1) m/s` that is ~500 km. Undersized, the landfall was **104.5 km off,
   and a full-grid scan could not improve it** — because no node in the domain mapped near
   the target at all.
   *Discriminating test:* scan every node for `min ‖(y + w·T[y]) − x_B‖`. If the minimum over
   the **whole grid** is large, the domain is too small; if it is small but your selected node
   is worse, it is cause 2.
2. **Goal node chosen by the interception root find.** `g(t) = T_w(x_B − w t) − t` is a step
   function when `T` is sampled at the nearest node, so bisection lands on a discontinuity and
   `T` at that node need not equal `t*`. The error is then amplified by `|w|`.
   *Fix:* select the goal node by minimising the ground miss directly (see above).
3. **`w` sign convention.** `ground_position` is `x = y + w t`; `comoving_position` is
   `y = x − w t`. Swapping them puts the landfall `2|w|t*` away — twice the dilation distance,
   which is a distinctive signature worth recognising.

## S9 — Forecast repair is as slow as a cold solve

**Cause:** the dependency closure is too conservative — probably you are re-opening every node
whose value is greater than `t_now` rather than only those whose *backpointer chain passes
through a materially changed cell*.

**Discriminating test:** report `|closure(S)| / N`. For a 5 % perturbation this should be well
under 0.2. If it is near 1.0, the closure is degenerate.

---

## Instrumentation to build in from day one

Do not add these after something goes wrong. Add them before anything does.

| Counter | Why |
|---|---|
| metric evaluations, and cache hit rate | tells you whether the support table is working |
| distribution of the inner minimiser's `ζ` | endpoint-pinned means the `ζ` search is broken (S3) |
| stencil radius histogram | confirms the adaptive radius is adapting, not saturating |
| bucket-queue monotonicity violations | must be 0 (S1) |
| labels per node: mean and peak | the `Λ` in the complexity bound, measured |
| cells needing wait relaxation, and max `h·L_t` | the FIFO honesty metric (S7) |
| certificate gap on the returned route | your headline number |
| nodes expanded vs nodes in domain | tells you the heuristic is focusing the search |

Print all of them at the end of every run. They cost nothing and they are the difference
between "it works" and "we know it works."
