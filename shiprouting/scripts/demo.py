"""Run a voyage and plot it: optimised routes vs the great-circle baseline.

    python scripts/demo.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from forcing import SyntheticIndianOcean
from router import Grid, astar, great_circle_route, grid_line_route, pareto_sweep
from ship import Ship

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")

PORTS = {
    "Mumbai (JNPT)": (18.95, 72.95),
    "Chennai": (13.10, 80.30),
    "Colombo": (6.95, 79.85),
    "Port Louis": (-20.15, 57.50),
    "Singapore": (1.26, 103.85),
}


def main():
    os.makedirs(OUT, exist_ok=True)
    origin, dest = "Mumbai (JNPT)", "Port Louis"
    start, goal = PORTS[origin], PORTS[dest]

    grid = Grid(lat_min=-28.0, lat_max=26.0, lon_min=40.0, lon_max=95.0, step=0.5)
    ship = Ship()
    forcing = SyntheticIndianOcean()

    print(f"Grid {grid.nlat} x {grid.nlon} @ {grid.step} deg  "
          f"({sum(r.count(False) for r in grid._land)} water nodes)")
    print(f"Ship: {ship.name}, service {ship.service_speed_kts} kts\n")
    print(f"Voyage: {origin} -> {dest}\n")

    t0 = time.time()
    # continuous great circle (geometry reference) and the SAME-GRAPH baseline (fair)
    gc = great_circle_route(grid, ship, forcing, start, goal)
    base = grid_line_route(grid, ship, forcing, start, goal)
    print(f"  great circle (continuous) : "
          f"{gc.summary() if gc else 'UNNAVIGABLE - exceeds the ship limit'}")
    print(f"  straight line (same grid)  : "
          f"{base.summary() if base else 'UNNAVIGABLE - exceeds the ship limit'}")

    fast = astar(grid, ship, forcing, start, goal, w_time=1.0, w_fuel=0.0)
    eco = astar(grid, ship, forcing, start, goal, w_time=1.0, w_fuel=1.2)
    safe = astar(grid, ship, forcing, start, goal, w_time=1.0, w_fuel=0.4, w_risk=20.0)
    for nm, r in [("time-optimal", fast), ("fuel-optimal", eco), ("safety-first", safe)]:
        print(f"  {nm:26s}: {r.summary() if r else 'no route found'}")
    print(f"\nsolve time: {time.time() - t0:.1f}s")

    if base and eco:
        print("\n  vs same-grid straight line (the fair comparison):")
        print(f"    fuel {100 * (base.fuel_t - eco.fuel_t) / base.fuel_t:+.1f}%   "
              f"time {100 * (eco.hours - base.hours) / base.hours:+.1f}%   "
              f"peak risk {base.max_risk:.2f} -> {eco.max_risk:.2f}")
    if base and safe:
        print(f"    safety-first: peak risk {base.max_risk:.2f} -> {safe.max_risk:.2f}, "
              f"time {100 * (safe.hours - base.hours) / base.hours:+.1f}%")

    # ---- does departure time actually change the answer? --------------
    # If it does not, time-dependent routing is pointless and a static solver would do.
    print("\n  departure-time sensitivity (the case for time-dependence):")
    for dep in (0, 24, 48, 72):
        r = astar(grid, ship, forcing, start, goal, w_time=1.0, w_fuel=0.4,
                  w_risk=8.0, depart_h=dep)
        b = grid_line_route(grid, ship, forcing, start, goal, depart_h=dep)
        if r:
            delta = (f"{100 * (b.fuel_t - r.fuel_t) / b.fuel_t:+.1f}% fuel vs baseline"
                     if b else "baseline UNNAVIGABLE")
            print(f"    depart +{dep:3d} h : {r.hours:6.1f} h  {r.fuel_t:6.1f} t  "
                  f"peak risk {r.max_risk:.2f}   {delta}")

    _, front = pareto_sweep(grid, ship, forcing, start, goal)
    print(f"\nPareto front: {len(front)} non-dominated routes")
    for r in front:
        print(f"  w={r.weights}  {r.hours:6.1f} h  {r.fuel_t:7.1f} t  "
              f"peak risk {r.max_risk:.2f}")

    # ------------------------------------------------------------------ plot
    fig, ax = plt.subplots(figsize=(13, 9))
    lats = np.arange(grid.lat_min, grid.lat_max + 0.01, 2.0)
    lons = np.arange(grid.lon_min, grid.lon_max + 0.01, 2.0)
    t_mid = (fast.hours / 2) if fast else 48.0
    U, V, H = forcing.grid(lats, lons, t_mid)

    im = ax.contourf(lons, lats, H, levels=14, cmap="YlOrRd", alpha=0.55)
    plt.colorbar(im, ax=ax, label=f"significant wave height (m) at t = {t_mid:.0f} h")
    ax.quiver(lons[::2], lats[::2], U[::2, ::2], V[::2, ::2],
              color="#22506e", alpha=0.55, scale=22, width=0.0022)

    land = np.array(grid._land, dtype=float)
    ax.contourf(np.arange(grid.lon_min, grid.lon_max + 0.001, grid.step),
                np.arange(grid.lat_min, grid.lat_max + 0.001, grid.step),
                land, levels=[0.5, 1.5], colors=["#5b5b5b"])

    for r, col, nm in [(base, "black", "straight line (baseline)"),
                       (fast, "#0b6fb8", "time-optimal"),
                       (eco, "#1a9850", "fuel-optimal"),
                       (safe, "#8856a7", "safety-first")]:
        if not r:
            continue
        ax.plot([p[1] for p in r.waypoints], [p[0] for p in r.waypoints],
                color=col, lw=2.4, label=f"{nm} — {r.hours:.0f} h, {r.fuel_t:.0f} t",
                ls="--" if nm.startswith("great") else "-")

    for nm, (la, lo) in [(origin, start), (dest, goal)]:
        ax.plot(lo, la, "o", ms=9, color="crimson", zorder=5)
        ax.annotate(nm, (lo, la), textcoords="offset points", xytext=(7, 7),
                    fontsize=10, fontweight="bold")

    slat, slon = forcing.storm_centre(t_mid)
    ax.annotate("storm cell\n(drifting east)", (slon, slat), color="#7f2704",
                fontsize=9, ha="center", fontweight="bold")

    ax.set_xlabel("longitude (°E)")
    ax.set_ylabel("latitude (°N)")
    ax.set_title(f"Optimal ship routing — {origin} to {dest}\n"
                 "time-dependent A* over evolving currents and waves", fontsize=13)
    ax.legend(loc="lower left", fontsize=9)
    ax.set_xlim(grid.lon_min, grid.lon_max)
    ax.set_ylim(grid.lat_min, grid.lat_max)
    ax.grid(alpha=0.2)
    fig.tight_layout()
    p = os.path.join(OUT, "route_demo.png")
    fig.savefig(p, dpi=135)
    print(f"\nwrote {p}")


if __name__ == "__main__":
    main()
