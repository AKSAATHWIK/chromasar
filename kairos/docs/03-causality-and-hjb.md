# 3. Non-stationary fields, the HJB equation, and causality

The forecast changes while the ship sails. This is the single hardest structural feature of
the problem — it is what breaks Dijkstra, and it is where the sharpest result in KAIROS
lives.

---

## 3.1 The equations

**Stationary case first** (frozen fields). The earliest-arrival function
`T(x) = min{ time to reach x from x_A }` is the viscosity solution of the **Finsler eikonal
equation**

```
F*( x, ∇T(x) )  =  1  on Ω \ {x_A},        T(x_A) = 0                       (3.1)
```

where `F*` is the dual (polar) of `F`. Equivalently, in support-function form,

```
max_{v ∈ 𝒱(x)}  ⟨ −∇T(x), v ⟩  =  1                                          (3.2)
```

— "the fastest achievable velocity, projected onto the direction of steepest arrival-time
decrease, makes good exactly one unit of `T` per unit time." For the Randers case (2.1),
(3.2) becomes the familiar

```
V_s |∇T|  +  ⟨ c, ∇T ⟩  =  1
```

which is the Zermelo eikonal used by Lolla & Lermusiaux. Our formulation contains it as the
special case where no waves and no bans are active — a useful reduction to state on a slide.

**Non-stationary case.** Let `φ(x,t)` be a level-set function whose zero set is the boundary
of the reachable set `R(t) = {x : φ(x,t) < 0}`. The front's outward normal speed is the
support function of `𝒱` in the normal direction, so

```
∂φ/∂t  +  H( x, t, ∇φ )  =  0 ,        H(x,t,p) = max_{v ∈ 𝒱(x,t)} ⟨ v, p ⟩   (3.3)
```

with `φ(x,t₀) = |x − x_A|`. Arrival time is recovered as `T(x) = min{ t : φ(x,t) ≤ 0 }`.

Equation (3.3) is correct, is what the level-set literature solves, and is **expensive**:
you march the whole domain forward in `t` with a CFL-limited step, whether or not the front
has reached anywhere interesting. KAIROS does not solve (3.3) directly. It solves for `T`
directly in a single monotone sweep — which is only legitimate under the condition of the
next subsection.

---

## 3.2 The causality problem

Label-setting methods (Dijkstra, FMM, OUM) rest on one property: **a node's final value can
be determined from nodes with strictly smaller value.** That is what lets you finalise nodes
in increasing order of `T` and never revisit them.

With time-dependent fields the local cost is evaluated *at the arrival time being computed*.
Traversing a segment of length `h` in direction `u`, departing at time `t`:

```
Arr(t)  :=  t  +  h · F( x, t, u )                                          (3.4)
```

Causality is exactly the statement that `Arr` is **non-decreasing in `t`**: leaving later can
never let you arrive earlier. In the time-dependent-shortest-path literature this is the
**FIFO** or *consistency* property (Kaufman & Smith, 1993), and it is the necessary and
sufficient condition for Dijkstra-type label setting to remain correct.

> **Theorem 3.2 (Causality condition — proved as Thm 5.1).** Suppose `F(x, ·, u)` is
> differentiable in `t` with `|∂F/∂t| ≤ L_t` uniformly. Then the arrival map (3.4) is
> non-decreasing for every `x, u` whenever
> ```
>                       h · L_t  ≤  1                                        (3.5)
> ```
> and under (3.5) the KAIROS sweep of §4 terminates in one pass with the exact discrete
> value function.

**What (3.5) means physically.** `L_t` is how fast the *cost of transit* changes with the
clock — the rate at which weather evolves. `h·L_t` compares that to the transit time of one
cell. The condition says:

> *The weather may not deteriorate (or improve) faster than the ship can traverse one grid
> cell.* Equivalently: waiting one hour must never buy you more than one hour of transit.

This is a genuinely mild condition for ocean routing. Take `h = 0.25° ≈ 28 km`, a ship
making 7 m/s → cell transit ≈ 1.1 h. For (3.5) to fail, the transit cost of that cell would
have to change by more than 100 % within 1.1 hours. Synoptic weather evolves on a 6–24 h
scale, so `h L_t ≈ 0.05–0.15` typically. **We can check it numerically on the actual
forecast, cell by cell, and report the margin** — which is a validation slide nobody else
will have.

Where it *does* fail: a tropical cyclone wall passing over a strait, or the leading edge of
a monsoon surge. Which brings us to the fix.

---

## 3.3 The waiting relaxation

When FIFO fails, the reason is always the same: it would have been better to *wait*. So make
waiting a control.

> **Definition 3.3.** The **wait-relaxed** local cost is
> ```
> F̃( x, t, u )  :=  inf_{s ≥ 0}  [  s/h  +  F( x, t + s, u )  ]              (3.6)
> ```
> i.e. the lower envelope over "hold position for `s`, then transit".

> **Corollary 3.4 (proved as Cor. 5.2).** `F̃ ≤ F`, the arrival map built from `F̃` is
> **always** FIFO regardless of `L_t`, and the value function it induces is the true optimal
> arrival time of the problem in which loitering is permitted.

Three things make this more than a technical patch:

1. **It is physically real.** Loitering, slow-steaming and heaving-to are what ships
   actually do when a low is crossing their track. Voluntary speed reduction is already in
   the control set (`V < V_pwr`), so (3.6) is not adding an unphysical capability; it is
   admitting one that was always there.
2. **It is fuel-cheap.** Loitering at 5 kt burns a fraction of transit power. So the wait
   branch is often *dominant* in the Pareto sense, not merely feasible — a route that
   arrives at the same hour having waited out a storm at low RPM beats one that punched
   through, on fuel *and* on risk, and ties on time.
3. **It costs almost nothing to compute.** The infimum in (3.6) is over a 1-D grid of
   forecast time steps (typically 3-hourly, ≤ 8 candidates within the useful horizon), and
   is evaluated only for the cells where the FIFO check of Thm 3.2 actually fails —
   empirically < 2 % of the domain.

This is the piece we would put in the paper: *causality is restored by admitting waiting,
and waiting is what mariners do anyway.*

---

## 3.4 The characteristic system, and why we still want it

The PDE gives a global answer on a grid. The Pontryagin side gives an exact local one, and
we use it to polish.

With costate `p` (adjoint to `x`), Hamiltonian `H(x,t,p) = max_{v∈𝒱} ⟨v,p⟩`, the optimal
trajectory satisfies

```
ẋ  =  ∂H/∂p  =  v*(x,t,p)          (the maximiser — the optimal ground velocity)
ṗ  =  −∂H/∂x  =  −(∂c/∂x)ᵀ p  −  ∂/∂x [ σ-terms ]
```

In the classical constant-`V_s` case this collapses to **Zermelo's navigation formula**, a
closed-form ODE for the heading with no costate at all. With current `c = (u_c, v_c)` and
heading `θ` measured from the x-axis:

```
dθ/dt  =  ∂v_c/∂x · sin²θ  +  ( ∂u_c/∂x − ∂v_c/∂y ) · sinθ cosθ  −  ∂u_c/∂y · cos²θ   (3.7)
```

Read it: **heading changes only in response to current *shear*, never to the current
itself.** In a uniform flow, the optimal control is a constant heading — the ship crabs and
holds it. Every waypoint your router emits in a uniform current field is a numerical
artefact. That is a devastatingly good diagnostic, and (3.7) gives us:

- **A unit test with an exact answer.** Uniform flow → straight line in heading space.
  Linear shear → analytic solution. Any implementation that fails these is broken, and we
  will know before the judges do.
- **A polishing step (§4.6).** The grid solve gives a route accurate to `O(h)` with headings
  quantised by the stencil. Take the grid route as an initial guess, shoot (3.7) plus the
  costate equations from `x_A`, and Newton-correct the initial heading to hit `x_B`. Two or
  three iterations converge, and the result is a **continuous, smooth, second-order-accurate
  route with no staircase** — the visual difference on a plot is enormous and it is
  mathematically justified rather than a cosmetic spline.

---

## 3.5 Summary of the layer

| | |
|---|---|
| Exact model | HJB level-set (3.3) — correct, slow, marches all of space forward in time |
| What KAIROS solves | The eikonal (3.2) with a time-indexed metric, in one monotone sweep |
| Licence to do so | Theorem 3.2: `h·L_t ≤ 1`, checkable on the real forecast |
| Fallback where it fails | Wait relaxation (3.6) — always FIFO, physically meaningful, < 2 % of cells |
| Polish | Zermelo/costate shooting (3.7) — removes grid quantisation |
