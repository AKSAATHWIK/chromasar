"""Test 8.10 (revised) -- how much does de-advection actually buy?

Findings from the first attempt forced two changes:

(1) Phase correlation on the raw field returned w = (-0.74, 0.00) against a true (2.0, 0.5)
    -- it locks onto whichever system has the most gradient energy, not the one that matters.
    REPLACED by choosing w to directly minimise the co-moving causality constant. That is the
    quantity the algorithm actually cares about, so optimise it rather than a proxy.

(2) Reporting only the max over the grid hides the distribution. A single cell where two
    systems collide can pin the max while 99 % of the domain improves enormously. Report
    median and 99th percentile too, because the algorithm's fallback is per-cell.

Three regimes, from A1-exact to A1-badly-violated.
"""
import math
import numpy as np

V_S = 7.0
JET_A, JET_Y, JET_W = 3.0, 100e3, 60e3
SYS2_A, SYS2_W = 1.2, 90e3
W1 = np.array([2.0, 0.5])
W2 = np.array([-0.6, 1.1])


def make_field(intensify, second_system):
    beta = (0.35 / 86400.0) if intensify else 0.0

    def current(px, py, t):
        ay = py - W1[1] * t
        ax = px - W1[0] * t
        g1 = JET_A * (1.0 + beta * t) * np.exp(-((ay - JET_Y) ** 2) / (2.0 * JET_W ** 2))
        cx, cy = g1, np.zeros_like(g1)
        if second_system:
            bx = px - W2[0] * t - 300e3
            by = py - W2[1] * t + 80e3
            amp = SYS2_A * np.exp(-(bx * bx + by * by) / (2.0 * SYS2_W ** 2))
            cx = cx - amp * by / SYS2_W
            cy = cy + amp * bx / SYS2_W
        return cx, cy
    return current


def sigma(ux, uy, cx, cy):
    cpar = cx * ux + cy * uy
    cperp = -cx * uy + cy * ux
    r = V_S * V_S - cperp * cperp
    r = np.where(r <= 0.0, np.nan, r)
    s = np.sqrt(r) + cpar
    return np.where(s <= 1e-6, np.nan, s)


def dFdt_field(current, w, times, dt, X, Y, dirs):
    """Per-cell max over headings of |dF/dt|, sampled at points fixed in the w-frame."""
    acc = np.zeros_like(X)
    for t in times:
        F = []
        for tt in (t - dt, t + dt):
            px, py = X + w[0] * tt, Y + w[1] * tt
            cx, cy = current(px, py, tt)
            F.append(np.nanmax(np.stack(
                [1.0 / sigma(ux, uy, cx, cy) for ux, uy in dirs]), axis=0))
        acc = np.maximum(acc, np.abs(F[1] - F[0]) / (2.0 * dt))
    return acc


def optimise_w(current, times, dt, X, Y, dirs, span=4.0, n=9, rounds=3):
    """Choose w to minimise the co-moving causality constant (99th pct, robust to one cell)."""
    c = np.zeros(2)
    s = span
    for _ in range(rounds):
        best, bw = np.inf, c
        for wx in np.linspace(c[0] - s, c[0] + s, n):
            for wy in np.linspace(c[1] - s, c[1] + s, n):
                v = np.nanpercentile(
                    dFdt_field(current, np.array([wx, wy]), times, dt, X, Y, dirs), 99)
                if v < best:
                    best, bw = v, np.array([wx, wy])
        c, s = bw, s * 2.0 / (n - 1)
    return c


def summarise(name, arr):
    return (f"{name:34s} max {np.nanmax(arr):.4e}  p99 {np.nanpercentile(arr,99):.4e}  "
            f"med {np.nanmedian(arr):.4e}")


if __name__ == "__main__":
    H = 10e3
    X, Y = np.meshgrid(np.arange(0.0, 700e3, H), np.arange(-200e3, 300e3, H))
    dirs = [(math.sin(a), math.cos(a)) for a in np.linspace(0, 2 * math.pi, 24, endpoint=False)]
    times = np.linspace(0.0, 3 * 86400.0, 9)
    dt = 1800.0

    cases = [
        ("A  pure translation (A1 exact)", False, False),
        ("B  + intensification 35 %/day", True, False),
        ("C  + second system, different w", True, True),
    ]

    print("=" * 92)
    print("Test 8.10 (revised) -- causality constant  L_t = max_u |dF/dt|   [1/m]")
    print("=" * 92)

    for label, inten, sys2 in cases:
        cur = make_field(inten, sys2)
        g = dFdt_field(cur, np.zeros(2), times, dt, X, Y, dirs)
        w_opt = optimise_w(cur, times, dt, X, Y, dirs)
        co = dFdt_field(cur, w_opt, times, dt, X, Y, dirs)

        print()
        print(label)
        print("  " + summarise("ground frame", g))
        print("  " + summarise("co-moving (optimised w)", co))
        print(f"  optimised w = ({w_opt[0]:+.3f}, {w_opt[1]:+.3f}) m/s"
              f"   [dominant system truly at ({W1[0]:+.1f}, {W1[1]:+.1f})]")
        for tag, f in (("max", np.nanmax), ("p99", lambda a: np.nanpercentile(a, 99)),
                       ("median", np.nanmedian)):
            print(f"     reduction ({tag:6s}) : {f(g)/max(f(co),1e-30):8.2f} x")

        r = 56e3
        print(f"     causality r*L_t at r=56 km : ground {r*np.nanpercentile(g,99):7.3f}"
              f"  ->  co-moving {r*np.nanpercentile(co,99):7.3f}")
