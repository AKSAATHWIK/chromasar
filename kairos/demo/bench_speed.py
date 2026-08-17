"""Where does KAIROS actually beat conventional time-dependent Dijkstra?

The demos so far used analytic fields costing a few flops per evaluation, and on those KAIROS
loses: it pays a spatial dilation factor and gets nothing back. That is an honest result but
an unrealistic setting.

Real routing does not evaluate a formula. It interpolates a forecast: a trilinear (or
quadrilinear) lookup into a big array, per edge relaxation. And there the two methods differ
structurally:

  * conventional time-dependent Dijkstra must interpolate in (x, y, T) at EVERY relaxation,
    because the time it needs is the arrival time it is currently computing;
  * the co-moving field is STATIONARY, so it can be tabulated once per (node, direction) and
    read as an array lookup for the rest of the run.

This benchmark sweeps the cost of a field evaluation and finds the crossover.
"""
from __future__ import annotations

import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np

from kairos.core import PlanarLattice, comoving_plan, required_bounds, time_dependent_dijkstra

KMH = 1000.0 / 3600.0
FREE, JAM = 60.0 * KMH, 20.0 * KMH
BLOCK = 200.0
W = (-3.0, -1.0)
SPAN = 12000.0
TRIP_FROM, TRIP_TO = (500.0, 500.0), (11500.0, 11500.0)

# A synthetic "forecast": congestion on a (time, y, x) grid, exactly the shape of a real
# product. Evaluating it means trilinear interpolation, which is the realistic cost.
NT, NY, NX = 24, 160, 160
GRID_H = SPAN / (NX - 1)
GRID_DT = 300.0
_rng = np.random.default_rng(7)


def _build_forecast():
    ys = np.arange(NY) * GRID_H
    xs = np.arange(NX) * GRID_H
    X, Y = np.meshgrid(xs, ys)
    out = np.empty((NT, NY, NX), dtype=np.float64)
    for k in range(NT):
        t = k * GRID_DT
        d = (X - W[0] * t + Y - W[1] * t - 9000.0) / math.sqrt(2.0)
        out[k] = np.exp(-(d * d) / (2.0 * 1400.0 ** 2))
    return out


FORECAST = _build_forecast()


def _trilinear(arr, x, y, t):
    """Realistic field evaluation: trilinear interpolation into the forecast array."""
    fx = min(max(x / GRID_H, 0.0), NX - 1.001)
    fy = min(max(y / GRID_H, 0.0), NY - 1.001)
    ft = min(max(t / GRID_DT, 0.0), NT - 1.001)
    i, j, k = int(fx), int(fy), int(ft)
    a, b, c = fx - i, fy - j, ft - k
    v = arr
    c00 = v[k, j, i] * (1 - a) + v[k, j, i + 1] * a
    c01 = v[k, j + 1, i] * (1 - a) + v[k, j + 1, i + 1] * a
    c10 = v[k + 1, j, i] * (1 - a) + v[k + 1, j, i + 1] * a
    c11 = v[k + 1, j + 1, i] * (1 - a) + v[k + 1, j + 1, i + 1] * a
    return (c00 * (1 - b) + c01 * b) * (1 - c) + (c10 * (1 - b) + c11 * b) * c


EXTRA_WORK = [0]     # simulates a heavier product (more variables, finer stencil)


def _burn():
    s = 0.0
    for _ in range(EXTRA_WORK[0]):
        s += math.sqrt(2.0)
    return s


def speed_ground(x, y, u, t):
    _burn()
    cong = _trilinear(FORECAST, x, y, t)
    return FREE - (FREE - JAM) * cong


def speed_comoving(x, y, u):
    _burn()
    cong = _trilinear(FORECAST, x, y, 0.0)     # stationary: always the t=0 slice
    s = FREE - (FREE - JAM) * cong
    dx, dy = -W[0], -W[1]
    c_par = dx * u[0] + dy * u[1]
    c_perp = -dx * u[1] + dy * u[0]
    r = s * s - c_perp * c_perp
    if r <= 0.0:
        return 0.0
    v = math.sqrt(r) + c_par
    return v if v > 1e-9 else 0.0


if __name__ == "__main__":
    nx = ny = int(SPAN / BLOCK) + 1
    lat_g = PlanarLattice(0.0, 0.0, nx, ny, BLOCK)
    bx0, by0, bx1, by1 = required_bounds(0.0, 0.0, SPAN, SPAN, W, 3600.0)
    lat_c = PlanarLattice(bx0, by0, int((bx1 - bx0) / BLOCK) + 1,
                          int((by1 - by0) / BLOCK) + 1, BLOCK)

    print("=" * 96)
    print("Crossover: KAIROS vs conventional time-dependent Dijkstra, as field cost rises")
    print("=" * 96)
    print(f"ground lattice {lat_g.n} nodes | co-moving lattice {lat_c.n} nodes "
          f"(dilation {lat_c.n/lat_g.n:.2f}x)")
    print(f"field = trilinear interpolation into a {NT}x{NY}x{NX} forecast array")
    print()
    print(f"{'field cost':>12} | {'conventional':>13} | {'co-moving+A*':>13} | "
          f"{'+precompute':>13} | {'best speedup':>13}")
    print("-" * 96)

    for extra in (0, 40, 200, 1000):
        EXTRA_WORK[0] = extra

        t0 = time.perf_counter()
        g = time_dependent_dijkstra(lat_g, speed_ground, TRIP_FROM, TRIP_TO)
        t_conv = time.perf_counter() - t0

        t0 = time.perf_counter()
        a = comoving_plan(lat_c, speed_comoving, W, TRIP_FROM, TRIP_TO,
                          sigma_max=FREE, goal_tol=BLOCK)
        t_astar = time.perf_counter() - t0

        t0 = time.perf_counter()
        p = comoving_plan(lat_c, speed_comoving, W, TRIP_FROM, TRIP_TO,
                          sigma_max=FREE, goal_tol=BLOCK, precompute=True)
        t_pre = time.perf_counter() - t0

        best = min(t_astar, t_pre)
        tag = "FASTER" if best < t_conv else "slower"
        label = f"1x (~{extra} flops)" if extra else "1x (cheap)"
        print(f"{label:>12} | {t_conv:11.3f} s | {t_astar:11.3f} s | {t_pre:11.3f} s | "
              f"{t_conv/best:8.2f}x {tag}")

    print()
    print("Note: `+precompute` tabulates the stationary field once per (node, direction).")
    print("A time-dependent solver cannot do this -- the time it needs is the arrival time it")
    print("is still computing, so every relaxation is a fresh interpolation.")
