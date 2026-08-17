"""Decisive test of the Co-Moving Reduction: the TRAJECTORY BIJECTION.

The two-grid comparison is limited by the 16-neighbour stencil's metrication error
(~1%, non-vanishing under refinement), so it cannot resolve the claim. Test the claim
itself instead.

CLAIM (the substantive half of the theorem):
    x(.) is admissible in the ground frame with advected fields E(x,t) = E0(x - w t)
      <=>  y(t) := x(t) - w t is admissible in the co-moving frame with the STATIONARY
           field E0 and indicatrix shifted by -w,
    with the SAME time parameterisation.

If that bijection holds exactly, then the co-moving arrival field plus the interception
root find gives the exact ground-frame optimum, independent of any grid.

TEST: take the route produced by the co-moving solve, map it to the ground frame, and
check leg by leg that the required ground velocity is achievable at the ground-frame
field sampled at the actual position and actual time. Then do the converse.
No second optimal solve is involved, so stencil error cannot contaminate the result.
"""
import heapq
import math
import numpy as np

import verify_comoving as VC   # reuse the field, grid and solvers


def route_of(par, goal):
    out, n = [], int(goal)
    while n != -1:
        out.append(n)
        n = int(par[n])
    return out[::-1]


def leg_check(pts, times, frame):
    """For each leg, compute the required velocity and the residual through-water speed.

    frame='ground'   : drift is c_ground(x_mid, t_mid)  -- advected, time-dependent
    frame='comoving' : drift is c0(y_mid) - w           -- stationary, shifted indicatrix
    Returns (max |V_required| , max excess over V_S).
    """
    worst = 0.0
    worst_excess = -1e9
    for k in range(len(pts) - 1):
        p0, p1 = np.array(pts[k]), np.array(pts[k + 1])
        t0, t1 = times[k], times[k + 1]
        dt = t1 - t0
        if dt <= 0:
            continue
        v = (p1 - p0) / dt                       # required velocity in this frame
        mid = 0.5 * (p0 + p1)
        tm = 0.5 * (t0 + t1)
        if frame == 'ground':
            cx, cy = VC.c_ground(np.array(mid[0]), np.array(mid[1]), tm)
            c = np.array([float(cx), float(cy)])
        else:
            cx, cy = VC.c0(np.array(mid[0]), np.array(mid[1]))
            c = np.array([float(cx), float(cy)]) - VC.W
        Vreq = np.linalg.norm(v - c)             # speed through water required
        worst = max(worst, Vreq)
        worst_excess = max(worst_excess, Vreq - VC.V_S)
    return worst, worst_excess


if __name__ == "__main__":
    print("=" * 78)
    print("CO-MOVING REDUCTION -- trajectory bijection test")
    print("=" * 78)
    print(f"V_s = {VC.V_S} m/s,  w = ({VC.W[0]}, {VC.W[1]}) m/s,  grid h = {VC.H/1000:.0f} km")
    print()

    # ---- solve in the co-moving frame -------------------------------------
    Tw, parw = VC.solve_comoving()
    tstar = VC.intercept_time(Tw)
    y_target = VC.X_B - VC.W * tstar
    gnode = VC.nearest_node(y_target)

    ypath = route_of(parw, gnode)
    ypts = [np.array(VC.pos(n)) for n in ypath]
    ytimes = [Tw[n] for n in ypath]

    print(f"co-moving solve: t* = {tstar:.2f} s = {tstar/3600:.5f} h, "
          f"{len(ypath)} nodes")

    # feasibility of the co-moving route IN THE CO-MOVING FRAME (sanity: must hold)
    w1, e1 = leg_check(ypts, ytimes, 'comoving')
    print(f"  co-moving route, checked in CO-MOVING frame : "
          f"max V_req = {w1:.6f} m/s, excess over V_s = {e1:+.3e} m/s")

    # ---- MAP TO THE GROUND FRAME: x(t) = y(t) + w t ------------------------
    xpts = [ypts[k] + VC.W * ytimes[k] for k in range(len(ypts))]
    xtimes = list(ytimes)

    w2, e2 = leg_check(xpts, xtimes, 'ground')
    print(f"  SAME route mapped to GROUND frame, checked   : "
          f"max V_req = {w2:.6f} m/s, excess over V_s = {e2:+.3e} m/s")
    print()
    print(f"  BIJECTION RESIDUAL |V_req(ground) - V_req(comoving)| per leg:")
    resid = 0.0
    for k in range(len(ypts) - 1):
        dt = ytimes[k + 1] - ytimes[k]
        if dt <= 0:
            continue
        vy = (ypts[k + 1] - ypts[k]) / dt
        vx = (xpts[k + 1] - xpts[k]) / dt
        # the claim: vx - c_ground = vy - (c0 - w) exactly, leg by leg
        midy = 0.5 * (ypts[k] + ypts[k + 1])
        tm = 0.5 * (ytimes[k] + ytimes[k + 1])
        midx = 0.5 * (xpts[k] + xpts[k + 1])
        c0x, c0y = VC.c0(np.array(midy[0]), np.array(midy[1]))
        cgx, cgy = VC.c_ground(np.array(midx[0]), np.array(midx[1]), tm)
        lhs = vx - np.array([float(cgx), float(cgy)])
        rhs = vy - (np.array([float(c0x), float(c0y)]) - VC.W)
        resid = max(resid, float(np.linalg.norm(lhs - rhs)))
    print(f"    max residual = {resid:.3e} m/s      (theorem says: exactly 0)")
    print()

    # ---- arrival check -----------------------------------------------------
    x_arrival = xpts[-1]
    print(f"  ground arrival point : ({x_arrival[0]/1000:9.3f}, {x_arrival[1]/1000:9.3f}) km")
    print(f"  target x_B           : ({VC.X_B[0]/1000:9.3f}, {VC.X_B[1]/1000:9.3f}) km")
    print(f"  miss distance        : {np.linalg.norm(x_arrival-VC.X_B)/1000:.3f} km "
          f"(<= grid diagonal {VC.H*math.sqrt(2)/1000:.3f} km)")
    print()

    # ---- converse: ground route mapped into the co-moving frame ------------
    Tg, parg, goal = VC.solve_ground()
    gpath = route_of(parg, goal)
    gpts = [np.array(VC.pos(n)) for n in gpath]
    gtimes = [Tg[n] for n in gpath]
    w3, e3 = leg_check(gpts, gtimes, 'ground')
    gy = [gpts[k] - VC.W * gtimes[k] for k in range(len(gpts))]
    w4, e4 = leg_check(gy, gtimes, 'comoving')
    print(f"converse: ground-frame route, {len(gpath)} nodes, t = {Tg[goal]/3600:.5f} h")
    print(f"  checked in GROUND frame     : max V_req = {w3:.6f}, excess = {e3:+.3e}")
    print(f"  mapped to CO-MOVING, checked: max V_req = {w4:.6f}, excess = {e4:+.3e}")
    print(f"  difference in max V_req     : {abs(w3-w4):.3e} m/s   (theorem says 0)")
