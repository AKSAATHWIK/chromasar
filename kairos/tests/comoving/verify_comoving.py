"""Numerical verification of the Co-Moving Reduction Theorem.

CLAIM. If every environmental field is a rigid translation of a fixed pattern,
    E(x, t) = E0(x - w t),
then the TIME-DEPENDENT time-optimal routing problem in the ground frame is exactly
equivalent to a STATIONARY Finsler problem in the co-moving frame y = x - w t, whose
indicatrix is the ground indicatrix shifted by -w, followed by a 1-D root find for the
interception time.

If true:  t* = min{ t >= 0 : T_w(x_B - w t) <= t }
where T_w is the stationary co-moving arrival-time field.

TEST. Solve the same problem two completely different ways on the SAME grid and the SAME
8-neighbour discretisation, so any disagreement is attributable to the reduction and not
to discretisation:
  A) ground frame, time-dependent Dijkstra (field re-sampled at each departure time)
  B) co-moving frame, stationary Dijkstra + root find
and compare arrival times and routes.
"""
import heapq
import math
import numpy as np

# ----------------------------------------------------------------- configuration
V_S = 7.0                       # ship speed through water, m/s (constant: pure Zermelo)
W = np.array([2.0, 0.5])        # weather-system translation velocity, m/s

# current pattern in the co-moving frame: an eastward jet centred on ey = JET_Y
JET_A = 3.0                     # peak current speed, m/s
JET_Y = 100e3                   # jet axis, m
JET_W = 60e3                    # jet half-width, m

X_A = np.array([0.0, 0.0])
X_B = np.array([600e3, 0.0])

# grid must cover y = x - w t for all t of interest
XMIN, XMAX = -150e3, 750e3
YMIN, YMAX = -250e3, 350e3
H = 4e3                          # 4 km spacing


def c0(px, py):
    """Current pattern, evaluated in the CO-MOVING frame coordinates."""
    g = JET_A * np.exp(-((py - JET_Y) ** 2) / (2.0 * JET_W ** 2))
    return g, np.zeros_like(g)


def c_ground(px, py, t):
    """Ground-frame current at time t: the pattern advected by w."""
    return c0(px - W[0] * t, py - W[1] * t)


# ----------------------------------------------------------------- grid
nx = int(round((XMAX - XMIN) / H)) + 1
ny = int(round((YMAX - YMIN) / H)) + 1
N = nx * ny
gx = XMIN + H * np.arange(nx)
gy = YMIN + H * np.arange(ny)


def idx(i, j):
    return i * ny + j


def pos(n):
    return gx[n // ny], gy[n % ny]


NB = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1),
      (2, 1), (2, -1), (-2, 1), (-2, -1), (1, 2), (1, -2), (-1, 2), (-1, -2)]


def sog(ux, uy, cx, cy):
    """Speed made good in unit direction u given drift c. 0.0 if unreachable.

    c_par  = <c,u>;  c_perp = component of c orthogonal to u.
    sigma  = sqrt(V^2 - c_perp^2) + c_par     (drift-corrected, spec Def 2.3)
    """
    cpar = cx * ux + cy * uy
    cperp = -cx * uy + cy * ux
    r = V_S * V_S - cperp * cperp
    if r <= 0.0:
        return 0.0
    s = math.sqrt(r) + cpar
    return s if s > 1e-9 else 0.0


def nearest_node(p):
    i = int(round((p[0] - XMIN) / H))
    j = int(round((p[1] - YMIN) / H))
    i = min(max(i, 0), nx - 1)
    j = min(max(j, 0), ny - 1)
    return idx(i, j)


# ----------------------------------------------------------------- A: ground frame
def solve_ground():
    """Time-dependent Dijkstra in the ground frame. Field sampled at DEPARTURE time."""
    T = np.full(N, np.inf)
    par = np.full(N, -1, dtype=np.int64)
    s0 = nearest_node(X_A)
    T[s0] = 0.0
    pq = [(0.0, s0)]
    goal = nearest_node(X_B)
    while pq:
        t, n = heapq.heappop(pq)
        if t > T[n] + 1e-9:
            continue
        if n == goal:
            break
        i, j = n // ny, n % ny
        px, py = gx[i], gy[j]
        for di, dj in NB:
            i2, j2 = i + di, j + dj
            if not (0 <= i2 < nx and 0 <= j2 < ny):
                continue
            qx, qy = gx[i2], gy[j2]
            dx, dy = qx - px, qy - py
            L = math.hypot(dx, dy)
            ux, uy = dx / L, dy / L
            # sample at the segment midpoint, at the time we DEPART (spec Alg 4.1)
            mx, my = 0.5 * (px + qx), 0.5 * (py + qy)
            cx, cy = c_ground(np.array(mx), np.array(my), t)
            s = sog(ux, uy, float(cx), float(cy))
            if s <= 0.0:
                continue
            t2 = t + L / s
            m = idx(i2, j2)
            if t2 < T[m] - 1e-9:
                T[m] = t2
                par[m] = n
                heapq.heappush(pq, (t2, m))
    return T, par, goal


# ----------------------------------------------------------------- B: co-moving frame
def solve_comoving():
    """Stationary Dijkstra in the co-moving frame: indicatrix shifted by -w."""
    T = np.full(N, np.inf)
    par = np.full(N, -1, dtype=np.int64)
    s0 = nearest_node(X_A)          # at t=0, y = x
    T[s0] = 0.0
    pq = [(0.0, s0)]
    while pq:
        t, n = heapq.heappop(pq)
        if t > T[n] + 1e-9:
            continue
        i, j = n // ny, n % ny
        px, py = gx[i], gy[j]
        for di, dj in NB:
            i2, j2 = i + di, j + dj
            if not (0 <= i2 < nx and 0 <= j2 < ny):
                continue
            qx, qy = gx[i2], gy[j2]
            dx, dy = qx - px, qy - py
            L = math.hypot(dx, dy)
            ux, uy = dx / L, dy / L
            mx, my = 0.5 * (px + qx), 0.5 * (py + qy)
            cx, cy = c0(np.array(mx), np.array(my))
            # THE REDUCTION: effective drift is c0(y) - w, and the field is STATIONARY
            s = sog(ux, uy, float(cx) - W[0], float(cy) - W[1])
            if s <= 0.0:
                continue
            t2 = t + L / s
            m = idx(i2, j2)
            if t2 < T[m] - 1e-9:
                T[m] = t2
                par[m] = n
                heapq.heappush(pq, (t2, m))
    return T, par


def interp_T(T, p):
    """Bilinear sample of the co-moving arrival field at an arbitrary point."""
    fi = (p[0] - XMIN) / H
    fj = (p[1] - YMIN) / H
    i0 = int(math.floor(fi)); j0 = int(math.floor(fj))
    if not (0 <= i0 < nx - 1 and 0 <= j0 < ny - 1):
        return np.inf
    a, b = fi - i0, fj - j0
    v = (T[idx(i0, j0)] * (1 - a) * (1 - b) + T[idx(i0 + 1, j0)] * a * (1 - b)
         + T[idx(i0, j0 + 1)] * (1 - a) * b + T[idx(i0 + 1, j0 + 1)] * a * b)
    return v


def intercept_time(Tw):
    """t* = smallest t with T_w(x_B - w t) <= t.  g(t) = T_w(x_B - w t) - t is
    continuous, g(0) > 0, and g -> -inf when |w| < sigma_min, so a bisection is valid."""
    def g(t):
        return interp_T(Tw, X_B - W * t) - t
    lo, hi = 0.0, 1.0
    while g(hi) > 0 and hi < 5e6:
        hi *= 1.6
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if g(mid) > 0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# ----------------------------------------------------------------- run
if __name__ == "__main__":
    print(f"grid {nx} x {ny} = {N} nodes, h = {H/1000:.0f} km, 16-neighbour")
    print(f"V_s = {V_S} m/s   w = ({W[0]}, {W[1]}) m/s  |w| = {np.linalg.norm(W):.3f}")
    print(f"jet: {JET_A} m/s peak at y = {JET_Y/1000:.0f} km, half-width {JET_W/1000:.0f} km")
    print()

    Tg, parg, goal = solve_ground()
    t_ground = Tg[goal]
    print(f"A) ground-frame time-dependent Dijkstra : t* = {t_ground:14.4f} s "
          f"= {t_ground/3600:9.5f} h")

    Tw, parw = solve_comoving()
    t_co = intercept_time(Tw)
    print(f"B) co-moving reduction + 1-D root find  : t* = {t_co:14.4f} s "
          f"= {t_co/3600:9.5f} h")

    d = abs(t_ground - t_co)
    print()
    print(f"   absolute difference : {d:.4f} s")
    print(f"   relative difference : {d/t_ground*100:.6f} %")
    print()

    # control: what if we WRONGLY freeze the field at t=0 (the naive thing)?
    Wsave = W.copy()
    W[:] = 0.0
    Tf, parf, goalf = solve_ground()
    t_frozen = Tf[goalf]
    W[:] = Wsave
    print(f"   control: naive frozen-field (ignore advection) t* = {t_frozen/3600:.5f} h"
          f"   -> error {abs(t_frozen-t_ground)/t_ground*100:.3f} %")
    print(f"   great-circle-equivalent no-current time         = "
          f"{np.linalg.norm(X_B-X_A)/V_S/3600:.5f} h")
