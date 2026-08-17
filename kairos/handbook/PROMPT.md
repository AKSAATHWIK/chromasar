# Handoff

## For the human

Send your friend **two files and nothing else**:

```
IMPLEMENT-THIS.md     the brief — self-contained, no other file needed
reference_min.py      a working 300-line implementation, 15/15 self-tests pass
```

That is the whole package. Everything needed to build it — the mathematics, the algorithm, the
exact test numbers, the traps, and the measured optimisations — is in those two files. They do
not need the repo, the spec, the papers, or an ocean.

**What the algorithm is, in one line, if they ask before reading:** a way to route through a
cost field that *moves* (weather, congestion, a fire front) by changing to coordinates that
move with it, which turns a time-dependent problem into an ordinary stationary shortest-path
problem — then solving that with Dijkstra or A*.

**What it is measured to do:** 2.5–6.4× faster than conventional time-dependent Dijkstra
(margin grows with field cost), 0.57 % mean accuracy with a 32-neighbour stencil, and correct
in cases where Dijkstra is not licensed at all.

Then have them paste the prompt below into Claude Code / Codex / Cursor, with those two files
in the working directory.

**Tell them the one thing that matters:** this algorithm's bugs do not throw exceptions. They
produce routes that look completely reasonable on a map and are wrong. The brief has six
documented traps and a set of gates with exact expected numbers. An agent that skips the gates
will produce something that looks finished and isn't. Insist on the gate output.

---

## The prompt

> I'm implementing a ship weather-routing algorithm called KAIROS. Two files are in the
> working directory:
>
> - `IMPLEMENT-THIS.md` — the complete specification. Self-contained; you need nothing else.
> - `reference_min.py` — a working Python reference implementation, ~300 lines, standard
>   library only. It passes all 15 of its own self-tests.
>
> **Read `IMPLEMENT-THIS.md` in full before writing any code.** Then run
> `python reference_min.py` and confirm you see 15 `PASS` lines, so you have a known-good
> baseline to compare against.
>
> Implement it in **<LANGUAGE>**, following the build order in §6 (M0 through M5).
>
> **Rules I care about:**
>
> 1. **Do not skip the gates.** After each of M0–M5, run that milestone's gate and paste me
>    the actual numbers. Section 7 gives exact expected values to 12 significant figures. If a
>    gate fails, fix it before continuing — do not proceed and plan to come back.
> 2. **The M4 gate is the one that matters.** It checks that the route, mapped back to the
>    ground frame, is exactly feasible against the time-varying field. It must come out around
>    `1e-13`. If it doesn't, the core reduction is wrong somewhere and everything downstream
>    is meaningless.
> 3. **Read §8 (the traps) before you write the grid code, not after.** All six failure modes
>    produce plausible wrong answers with no error message. Two of them — negative array
>    indices in the leg cache, and the un-dilated co-moving grid — cost real debugging time and
>    are easy to avoid if you know they exist.
> 4. **Implement the guards.** `λ ≤ 0` and `|c⊥| ≥ V` are routine physical conditions, not
>    error cases. They return "infinite cost", never an exception, never a NaN.
> 5. **Don't build anything in §11.** Core only. Those extras are real but they are not needed
>    for a working router and they will bury the part that has to be right.
> 6. **Optimise only after M5 passes**, then follow §10.1 — the edge-midpoint cache first
>    (it is the one structural win, worth 2.5–6.4×), then A* with the exact interception
>    heuristic, then a 32-neighbour stencil for accuracy. Do NOT eagerly precompute the whole
>    lattice; that was measured at 2.6× *worse*.
> 6. **Report honestly.** If something doesn't work or you're unsure a gate really passed, say
>    so. A known limitation is worth far more to me than a claim of success I can't reproduce.
>
> Start by reading both files and telling me your implementation plan and anything in the spec
> that's ambiguous.

---

## What good output looks like

Your friend should end up able to show you, for their language:

| Gate | Expected |
|---|---|
| M0 geodesy | `10 007.543 398 010 3 km` for the quarter circumference |
| M1 speed made good | T1–T8 to 12 significant figures; T7 and T8 return **zero** |
| M2 closed form | `1/13.68 = 0.073 099 415 204 678`; `λ ≤ 0` gives `+∞` |
| M3 sweep | zero-current arrival ≈ great-circle distance / V |
| M4 **bijection** | residual `~1e-13` m/s |
| M5 cross-check | ~1 % vs a conventional ground-frame solver |

If they report M4 passing at `1e-13`, the core is correct. Everything else is engineering.

If they report the grid-refinement difference *not* converging to zero, that is **expected** —
see §10. It is the fixed-stencil metrication floor, not a bug.

---

## If they ask "is this actually new?"

Honest answer, so nobody overclaims:

The **algorithm** — reduce the moving-weather problem to a stationary one, solve once,
intercept — appears to be unpublished for ship routing, and the theorem is verified to machine
precision.

The **underlying move** is classical. A Galilean change of variables to make an advected field
stationary is old; Taylor's frozen-field hypothesis (1938) is the same idea in meteorology.
The novelty is applying it here and quantifying what it buys, not new mathematics.

Everything else in the full system (ordered upwind, multi-objective labels, the certificate)
is borrowed and credited to Sethian–Vladimirsky 2003, Vladimirsky 2006, Kumar–Vladimirsky
2010, Tsaggouris–Zaroliagis 2009.
