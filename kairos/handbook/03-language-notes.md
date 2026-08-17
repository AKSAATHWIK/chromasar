# Language Notes

KAIROS is deliberately built on five primitives and plain arrays. It ports cleanly. These are
the language-specific things that actually bite.

---

## Universal: the data layout that decides your performance

Nothing else matters as much as this.

**The metric table dominates memory and cache behaviour.** Layout:

```
sigma_table[ t_idx ][ node_idx ][ theta_idx ]        float32
             n_fc        N          n_theta
```

Index arithmetic: `((t*N) + n)*n_theta + k`. Theta is the **fastest-varying** axis, because
the inner loop of the update sweeps directions at a fixed node and time. Getting this
transposed costs a factor of 5–20 in wall clock through cache misses alone, and it is
invisible in profiling until you look at cache-miss counters.

**Sizes.** Indian Ocean, lat −40…30, lon 20…120:

| Grid | Nodes `N` | ×8 forecast frames ×72 headings, float32 |
|---|---|---|
| 0.5° | 28 341 | 65 MB |
| 0.25° | 112 921 | 260 MB |
| 0.125° | 450 801 | 1.04 GB |

At 0.125° you must either stream frames or drop to float16 for `σ` (the metric's own
modelling error is ~5 %, so 3 decimal digits is ample — but keep the *accumulated* arrival
times in float64).

**float32 for the metric table, float64 for accumulated costs.** Arrival times accumulate
over thousands of edges; float32 there loses ~4 digits by the end of a long voyage.

---

## C++

**Do:**
- `std::vector<float>` with manual index arithmetic. Not `vector<vector<>>` — the double
  indirection destroys the inner loop.
- `-ffast-math` is **not safe here.** It permits reassociation, which breaks the conjugate-form
  branch of the Randers gauge (the whole point of that branch is a specific association
  order). Use `-O2 -fno-fast-math`. If you want vectorisation, use explicit SIMD intrinsics
  or `#pragma omp simd` on the loops you have checked.
- `std::priority_queue` for the fallback heap; hand-roll the bucket queue as a
  `vector<vector<Item>>` ring.

**Watch:**
- `std::fmod` for angle wrapping is correct but slow in a hot loop; the branch-free
  `x - 2π·std::nearbyint(x/2π)` is faster but changes the boundary convention at exactly ±π.
  Pick one and test it.
- Denormals in `σ` near infeasible directions will tank performance. Flush to zero *after*
  you have applied the feasibility guard, never before.

---

## Rust

**Do:**
- `Vec<f32>` with an index helper; `#[inline(always)]` on the metric evaluation.
- `ordered-float`'s `NotNan<f64>` for queue keys — it turns "NaN got into the priority queue"
  from a silent mis-ordering into a compile-time-enforced impossibility. Worth it.
- `rayon` for the metric table build (embarrassingly parallel). Do **not** reach for it on the
  sweep; the sweep is inherently sequential and a naive parallel version is wrong.

**Watch:**
- Bounds checking in the innermost index arithmetic is a real cost. Use `get_unchecked` only
  inside a function whose invariants you have proved, and leave the checked version behind a
  debug feature flag so tests exercise it.
- `f32::sqrt` is an intrinsic; `powi(2)` is faster and more accurate than `powf(2.0)`.

---

## Julia

Julia is arguably the best fit — the math reads like the spec.

**Do:**
- `Array{Float32,3}` — but note Julia is **column-major**, so the index order reverses:
  declare `sigma[theta, node, t]` so that `theta` is the fastest axis. Transcribing the C
  layout literally gives you the worst possible stride pattern.
- `StaticArrays.SVector{2,Float64}` for the 2-vectors. This is the single biggest win — it
  keeps velocity vectors in registers instead of heap-allocating.
- `@inbounds` and `@fastmath` selectively — but **not** `@fastmath` on the Randers gauge, for
  the same reassociation reason as C++.

**Watch:**
- Type instability in the metric function will silently cost 10–50×. Run `@code_warntype` on
  `sigma` and make sure nothing is `Any`. The usual culprit is a `nothing`-or-`Float64` return
  for infeasible directions — return `Inf` instead of `nothing`, or use a concrete `Union`.
- 1-based indexing: every index formula in the spec is 0-based. Convert once, in a helper, and
  never inline the arithmetic.

---

## Go

**Do:**
- `[]float32` with index arithmetic; Go's escape analysis handles the small structs fine.
- Goroutines + `sync.WaitGroup` for the metric build, chunked by rows.

**Watch:**
- **No operator overloading and no generics-free numeric abstraction**, so the vector math is
  verbose. Write `vec2` as a struct with methods and accept it.
- Go's `math.Sqrt` is a hardware instruction; `math.Pow(x,2)` is not — never use it.
- Bounds-check elimination is weaker than in Rust or C++. Hoist slice lengths and use the
  three-index slice form `s[a:b:b]` to help the compiler.

---

## Python (the reference implementation here)

Python is for *validating the algorithm*, not for shipping it. That said:

**Do:**
- numpy for the metric table (build it vectorised over headings; that is the only place
  vectorisation helps much).
- Keep the sweep in plain Python but make the inner metric call as cheap as possible — the
  support table lookup should be a pure array index, not a function call chain.
- `__slots__` on `Label` and `Leg`. Label objects are created in the millions; `__slots__`
  roughly halves the memory and speeds attribute access measurably.

**Watch:**
- The sweep is a scalar loop and will be ~100× slower than C++. That is fine and expected.
  Do not contort the algorithm to vectorise it; that is how you end up with a
  vectorised-but-wrong implementation. Validate here, port for speed.
- `heapq` is C-implemented and fast; the bucket queue's advantage in pure Python is smaller
  than it is in a compiled language. Measure before assuming.

---

## What must be identical across every port

These are the things that make two implementations agree. Fix them once, in a shared
constants file, and make the test suite check them:

| Item | Value |
|---|---|
| `R_E` | `6 371 000.0` m exactly |
| `g` | `9.806 65` m/s² |
| Heading convention | `n(θ) = (sin θ, cos θ)`, **east first**, 0 = north, clockwise |
| Wave direction | direction waves travel **towards**, converted at the data boundary only |
| Node indexing | `n = i·n_lon + j`, row-major in the spec's 0-based form |
| Angle units | radians internally, degrees only at I/O |
| `λ` guard | `λ > 0` checked before every division |
| `σ` guard | `σ > 0` checked before every inversion |
| Metric evaluation time | **departure** time, never arrival time |
| Label bucketing | on objective **value**, never on increment |
| Objective 0 | time, never ε-bucketed |

Two ports that agree on all eleven of these will agree on their routes to discretisation
error. Two ports that differ on any one of them will produce plausible, different, and
undiagnosable answers.
