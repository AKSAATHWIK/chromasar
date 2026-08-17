"""Zermelo shooting refinement and notch projection.

Spec reference: Alg 4.13 (docs/04-algorithm.md section 4.6), Alg 4.14 / Prop 2.6
(docs/02-finsler-metric.md section 2.5), Eq (3.7) (docs/03-causality-and-hjb.md section 3.4).

The grid sweep returns a route whose headings are quantised by the stencil: an O(h) staircase.
This module removes the staircase in two stages.

  Alg 4.13  Shoot the Zermelo characteristic from the departure point and Newton-correct the
            initial heading until the trajectory passes through the arrival point. The result
            is continuous, O(dt^4)-accurate, and optimal for the *convexified* indicatrix.
  Alg 4.14  The convexified optimum may command a (V, theta) that a seakeeping ban forbids
            (design decision D4: convexify, then project). Walk the route and snap every such
            control to the nearest admissible boundary control, then re-integrate.

The diagnostic that makes Eq (3.7) worth implementing: heading responds only to current
SHEAR. In a spatially uniform current dtheta/dt is identically zero and the optimal route is
a single constant heading. Every intermediate waypoint a router emits in a uniform field is a
numerical artefact, and this module's self-test measures that to machine precision.

TWO CONVENTION HAZARDS, both of which produce plausible-looking wrong answers:

1. Eq (3.7) is stated for `psi` measured from the x-axis (east), counter-clockwise. KAIROS
   uses the compass heading `theta`, with n(theta) = (sin theta, cos theta), 0 = north,
   clockwise (types.py, CONTRACT.md section 1). These are related by psi = pi/2 - theta, so
   dtheta/dt = -dpsi/dt AND sin psi = cos theta, cos psi = sin theta. Substituting theta into
   Eq (3.7) as written flips the sign of the shear response and swaps the roles of the two
   diagonal partials. See `zermelo_rhs` for the derivation.

2. The partials d(current)/dx are taken in the LOCAL METRE frame, not in lat/lon. The two
   differ by a factor of R_E cos(lat) ~ 6.4e6, which is a scale error large enough that the
   heading either never turns or turns instantly, and neither looks like a bug in a plot.
"""
from __future__ import annotations

import math
from typing import List, Optional, Protocol, Sequence, Tuple

from .geodesy import (
    R_E,
    haversine,
    heading_to_vec,
    initial_bearing,
    local_step_metres,
    metres_to_dlatlon,
    vec_to_heading,
    wrap_pi,
)
from .types import G, Env, EnvField, Route, Vessel, Waypoint

# Central-difference step for the current partials, metres. Operational current forecasts
# arrive on 1/12 to 1/4 degree grids (9-28 km), so any step far below the grid spacing is
# differencing the interpolant, not the ocean. 1 km sits below the grid scale (so the stencil
# stays local) but far above the round-off floor: with |c| ~ 1 m/s the differenced numerator
# carries ~1e-16 m/s of noise, giving ~1e-19 1/s of noise in the partial against a physical
# shear of 1e-8 to 1e-5 1/s. Eleven orders of margin.
GRAD_STEP_M: float = 1000.0

# Latitude is clamped this far from the poles. The (lat, lon, theta) parametrisation is
# genuinely singular there -- longitude and heading both become meaningless on the axis -- so
# the honest move is to keep the integrator finite and say so rather than to pretend
# otherwise. 1e-4 rad is ~640 m from the pole.
POLE_GUARD: float = 1e-4

_COS_LAT_FLOOR: float = 1e-9
_TINY: float = 1e-12

# Seakeeping ban bits, matching S1..S7 of docs/01-formulation.md section 1.4 in order.
# INTEGRATOR NOTE: `Vessel.bans_enabled` is documented in types.py as "see seakeeping.py".
# When that module lands, its bit order must agree with this one or the masks silently
# disable the wrong criteria. This is the ordering the spec lists them in.
BAN_S1 = 1 << 0      # synchronous roll
BAN_S2 = 1 << 1      # parametric roll
BAN_S3 = 1 << 2      # surf-riding / broaching
BAN_S4 = 1 << 3      # slamming            (needs a response spectrum -- not evaluated here)
BAN_S5 = 1 << 4      # green water on deck (needs a response spectrum -- not evaluated here)
BAN_S6 = 1 << 5      # lateral acceleration(needs a response spectrum -- not evaluated here)
BAN_S7 = 1 << 6      # operator envelope


class BanPredicate(Protocol):
    """True if the control (V, theta) is forbidden at this environmental state.

    Injectable so that `notch_project` can be driven by the real `seakeeping` module once it
    exists, without this file having to import it (and without the solver acquiring a
    dependency on the physics layer -- see the module docstring of types.py).
    """

    def __call__(self, vessel: Vessel, env: Env, V: float, theta: float) -> bool: ...


# ============================================================== the characteristic system
def _clamp_lat(lat: float) -> float:
    lim = 0.5 * math.pi - POLE_GUARD
    return min(lim, max(-lim, lat))


def _current_partials(field: EnvField, lat: float, lon: float, t: float,
                      ds: float) -> Tuple[float, float, float, float]:
    """(du/dx, du/dy, dv/dx, dv/dy) of the current, all in 1/s, in the LOCAL METRE frame.

    x is east, y is north, both in metres; u = Env.cu, v = Env.cv. `ds` is the half-step in
    METRES, converted to a lat/lon offset at this latitude before sampling, which is the
    whole point -- see hazard 2 in the module docstring.

    Degenerate case: within `_COS_LAT_FLOOR` of a pole an eastward metre step spans an
    unbounded longitude range, so the east partials are reported as zero rather than as a
    number divided by a vanishing cosine. The heading is a meaningless coordinate there
    anyway.
    """
    lat = _clamp_lat(lat)
    dlat, _ = metres_to_dlatlon(lat, 0.0, ds)

    e_n = field.at(_clamp_lat(lat + dlat), wrap_pi(lon), t)
    e_s = field.at(_clamp_lat(lat - dlat), wrap_pi(lon), t)
    inv2ds = 0.5 / ds
    du_dy = (e_n.cu - e_s.cu) * inv2ds
    dv_dy = (e_n.cv - e_s.cv) * inv2ds

    cos_lat = math.cos(lat)
    if abs(cos_lat) < _COS_LAT_FLOOR:
        return 0.0, du_dy, 0.0, dv_dy

    dlon = ds / (R_E * cos_lat)
    e_e = field.at(lat, wrap_pi(lon + dlon), t)
    e_w = field.at(lat, wrap_pi(lon - dlon), t)
    du_dx = (e_e.cu - e_w.cu) * inv2ds
    dv_dx = (e_e.cv - e_w.cv) * inv2ds
    return du_dx, du_dy, dv_dx, dv_dy


def zermelo_rhs(field: EnvField, lat: float, lon: float, t: float, theta: float, V_s: float,
                *, ds: float = GRAD_STEP_M,
                sphere_correction: bool = False) -> Tuple[float, float, float]:
    """The Zermelo characteristic ODE: (d lat/dt, d lon/dt, d theta/dt), SI, radians.

    `theta` is the KAIROS compass heading (0 = north, clockwise); `V_s` is speed through
    water in m/s, held constant along a characteristic (the classical Zermelo problem, which
    is Eq (3.7) -- for the throttle-varying case the full costate system of section 3.4 is
    needed and this reduction does not apply).

    DERIVATION. With costate p and Hamiltonian H(x,t,p) = max over v in V of <v,p>, the
    maximiser over headings aligns the through-water velocity with p, so the heading unit
    vector is n = p/|p|. The costate obeys pdot = -(dc/dx)^T p, i.e.

        p1dot = -(u_x p1 + v_x p2),      p2dot = -(u_y p1 + v_y p2)

    with (u, v) the east/north current and subscripts denoting metre-frame partials. Writing
    psi = atan2(p2, p1) for the MATHEMATICAL angle from the east axis,

        dpsi/dt = (p1 p2dot - p2 p1dot)/|p|^2
                = v_x sin^2 psi + (u_x - v_y) sin psi cos psi - u_y cos^2 psi        (3.7)

    which is Zermelo's navigation formula. No V_s appears: heading responds to current SHEAR
    and to nothing else. Converting to the compass heading via psi = pi/2 - theta (so
    dtheta/dt = -dpsi/dt, sin psi = cos theta, cos psi = sin theta) gives what is implemented:

        dtheta/dt = u_y sin^2 theta - (u_x - v_y) sin theta cos theta - v_x cos^2 theta

    Uniform current => all four partials vanish => dtheta/dt == 0 exactly, not approximately.

    `sphere_correction` adds the rotation rate of the local east/north frame as the ship
    moves over it, (v_E/R_E) tan(lat), where v_E is the eastward GROUND speed. Eq (3.7) is a
    plane result; on the sphere the heading is measured against a frame that itself turns, and
    with no current this term is exactly the great-circle bearing rate (differentiate
    Clairaut's cos(lat) sin(theta) = const). It is DEFAULT OFF because switching it on makes
    dtheta/dt nonzero in a uniform current and so destroys the diagnostic above.

    It is NOT small, and the self-test measures exactly how not-small. Shooting 4300 km from
    35 N on a 070 heading in still water: with the correction off the track is a rhumb line,
    the bearing defect against the true great circle reaches 15.71 degrees and the path is
    61.1 km LONGER (1.43 %); with it on the track is a great circle to 0.0000 degrees and
    arc/great-circle = 1.000000000. So: leave it off for validation against planar analytics
    and for legs of a few hundred km, turn it on for ocean crossings, and never report a
    transocean distance with it off.

    Raises ValueError for V_s < 0. V_s == 0 is permitted and gives pure drift, in which case
    `theta` is carried along as a formal costate direction with no physical meaning.
    """
    if not (V_s >= 0.0):                      # also catches NaN, which must not propagate
        raise ValueError(f"V_s must be finite and non-negative, got {V_s!r}")

    lat = _clamp_lat(lat)
    lon_w = wrap_pi(lon)
    env = field.at(lat, lon_w, t)

    sin_th = math.sin(theta)
    cos_th = math.cos(theta)
    v_e = V_s * sin_th + env.cu          # ground velocity, east component first (section 1)
    v_n = V_s * cos_th + env.cv

    dlat_dt = v_n / R_E
    cos_lat = math.cos(lat)
    dlon_dt = 0.0 if abs(cos_lat) < _COS_LAT_FLOOR else v_e / (R_E * cos_lat)

    du_dx, du_dy, dv_dx, dv_dy = _current_partials(field, lat, lon_w, t, ds)
    dtheta_dt = (du_dy * sin_th * sin_th
                 - (du_dx - dv_dy) * sin_th * cos_th
                 - dv_dx * cos_th * cos_th)

    if sphere_correction:
        dtheta_dt += (v_e / R_E) * math.tan(lat)

    return dlat_dt, dlon_dt, dtheta_dt


def _rk4_step(field: EnvField, lat: float, lon: float, t: float, theta: float, V_s: float,
              dt: float, ds: float, sphere_correction: bool) -> Tuple[float, float, float]:
    """One classical RK4 step of the characteristic system. Returns (lat, lon, theta).

    Fixed step rather than adaptive: the metric is sampled from a forecast whose own temporal
    resolution is 1-3 hours, so an adaptive controller would be chasing interpolation
    artefacts. 10-minute steps (Alg 4.13 line 2) are two orders below that.
    """
    def f(la: float, lo: float, tt: float, th: float) -> Tuple[float, float, float]:
        return zermelo_rhs(field, la, lo, tt, th, V_s,
                           ds=ds, sphere_correction=sphere_correction)

    k1 = f(lat, lon, t, theta)
    k2 = f(lat + 0.5 * dt * k1[0], lon + 0.5 * dt * k1[1], t + 0.5 * dt, theta + 0.5 * dt * k1[2])
    k3 = f(lat + 0.5 * dt * k2[0], lon + 0.5 * dt * k2[1], t + 0.5 * dt, theta + 0.5 * dt * k2[2])
    k4 = f(lat + dt * k3[0], lon + dt * k3[1], t + dt, theta + dt * k3[2])

    sixth = dt / 6.0
    lat_n = lat + sixth * (k1[0] + 2.0 * k2[0] + 2.0 * k3[0] + k4[0])
    lon_n = lon + sixth * (k1[1] + 2.0 * k2[1] + 2.0 * k3[1] + k4[1])
    th_n = theta + sixth * (k1[2] + 2.0 * k2[2] + 2.0 * k3[2] + k4[2])
    return _clamp_lat(lat_n), wrap_pi(lon_n), wrap_pi(th_n)


def _ground_speed(field: EnvField, lat: float, lon: float, t: float,
                  theta: float, V_s: float) -> float:
    env = field.at(_clamp_lat(lat), wrap_pi(lon), t)
    n_e, n_n = heading_to_vec(theta)
    return math.hypot(V_s * n_e + env.cu, V_s * n_n + env.cv)


def shoot(field: EnvField, start: Tuple[float, float], theta0: float, V_s: float,
          t0: float, dt: float, n_steps: int, *, ds: float = GRAD_STEP_M,
          sphere_correction: bool = False) -> List[Waypoint]:
    """Integrate the Zermelo characteristic forward. Alg 4.13 lines 1-2.

    `start` is (lat, lon) in radians. Returns n_steps + 1 `Waypoint`s beginning with the
    departure point, each carrying the instantaneous heading and ground speed.

    `Waypoint.sog` is set to |ground velocity|. That is consistent with Def 2.3 (speed made
    good along the REQUESTED direction) because along a shot characteristic the requested
    direction is by construction the realised ground track, so the two coincide. `q` is left
    at 1.0: the classical reduction fixes V_s and carries no throttle, and only
    `notch_project`, which is given a Vessel, can invert the powering curve to fill it in.

    Integration stops early and returns a short list if the forecast horizon is reached
    (06-numerics.md (f) -- past the horizon the field must be persisted or refused, and this
    module refuses).
    """
    if n_steps < 0:
        raise ValueError(f"n_steps must be non-negative, got {n_steps}")
    if dt <= 0.0:
        raise ValueError(f"dt must be positive, got {dt}")

    lat, lon = _clamp_lat(start[0]), wrap_pi(start[1])
    theta, t = wrap_pi(theta0), t0
    horizon = field.horizon

    wps = [Waypoint(lat, lon, t, theta, 1.0, _ground_speed(field, lat, lon, t, theta, V_s))]
    for _ in range(n_steps):
        if t + dt > horizon:
            break
        lat, lon, theta = _rk4_step(field, lat, lon, t, theta, V_s, dt, ds, sphere_correction)
        t += dt
        wps.append(Waypoint(lat, lon, t, theta, 1.0,
                            _ground_speed(field, lat, lon, t, theta, V_s)))
    return wps


# ============================================================== the two-point boundary problem
def _closest_approach(wps: Sequence[Waypoint],
                      target: Tuple[float, float]) -> Tuple[float, float, float, float, int, float]:
    """(signed_cross_track_m, |miss|_m, t_at_closest, lat_c, index, lon_c) for the polyline.

    The residual Newton drives to zero is the SIGNED perpendicular offset of the target from
    the track, positive when the target lies to starboard. Signed rather than the raw miss
    distance because |miss| has a kink at its root and Newton cannot cross it; and taken
    against the closest point of the POLYLINE rather than the closest waypoint because the
    latter jumps discontinuously as the index of the minimising waypoint changes with theta0,
    which would corrupt the derivative.

    Everything is done in one flat east/north frame anchored at the target. Far-away waypoints
    get the wrong east scale in that frame, but only the segment nearest the target is used
    and there the anchor error is O(miss^2 / R_E), i.e. millimetres at a 10 km miss.
    """
    tlat, tlon = target
    pts = [local_step_metres(tlat, w.lat - tlat, w.lon - tlon) for w in wps]
    if len(pts) < 2:
        d = math.hypot(*pts[0]) if pts else math.inf
        return 0.0, d, wps[0].t if wps else 0.0, wps[0].lat if wps else tlat, 0, tlon

    best_d = math.inf
    best = (0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0)
    for i in range(len(pts) - 1):
        ax, ay = pts[i]
        bx, by = pts[i + 1]
        dx, dy = bx - ax, by - ay
        dd = dx * dx + dy * dy
        if dd <= _TINY:
            continue
        s = min(1.0, max(0.0, -(ax * dx + ay * dy) / dd))
        cx, cy = ax + s * dx, ay + s * dy
        d = math.hypot(cx, cy)
        if d < best_d:
            best_d = d
            best = (i, s, cx, cy, dx, dy, math.sqrt(dd))

    i, s, cx, cy, dx, dy, seglen = best
    if not math.isfinite(best_d):                 # every segment degenerate (zero speed)
        return 0.0, math.hypot(*pts[0]), wps[0].t, wps[0].lat, 0, wps[0].lon

    # Starboard of the track direction (dx, dy) is (dy, -dx)/|d|; the offset from the closest
    # point to the target is -(cx, cy) since the target sits at the origin of this frame.
    signed = (-cx * dy + cy * dx) / seglen

    a, b = wps[i], wps[i + 1]
    t_c = a.t + s * (b.t - a.t)
    lat_c = a.lat + s * (b.lat - a.lat)
    lon_c = wrap_pi(a.lon + s * wrap_pi(b.lon - a.lon))
    return signed, best_d, t_c, lat_c, i, lon_c


def _track(field: EnvField, start: Tuple[float, float], target: Tuple[float, float],
           theta0: float, V_s: float, t0: float, dt: float, max_steps: int,
           t_max: float, ds: float, sphere_correction: bool) -> List[Waypoint]:
    """Shoot from `start` until the trajectory has passed its closest approach to `target`.

    Termination: three consecutive steps of increasing range, having approached at all. Three
    rather than one so that a trajectory grazing a current jet does not stop on a wiggle.
    Also bounded by `t_max`, the forecast horizon, and `max_steps`.
    """
    lat, lon = _clamp_lat(start[0]), wrap_pi(start[1])
    theta, t = wrap_pi(theta0), t0
    horizon = min(field.horizon, t_max)
    tlat, tlon = target

    wps = [Waypoint(lat, lon, t, theta, 1.0, _ground_speed(field, lat, lon, t, theta, V_s))]
    d0 = haversine(lat, lon, tlat, tlon)
    d_prev, d_best, rising = d0, d0, 0

    for _ in range(max_steps):
        if t + dt > horizon:
            break
        lat, lon, theta = _rk4_step(field, lat, lon, t, theta, V_s, dt, ds, sphere_correction)
        t += dt
        wps.append(Waypoint(lat, lon, t, theta, 1.0,
                            _ground_speed(field, lat, lon, t, theta, V_s)))
        d = haversine(lat, lon, tlat, tlon)
        rising = rising + 1 if d > d_prev else 0
        d_best = min(d_best, d)
        d_prev = d
        if rising >= 3 and d_best < d0:
            break
    return wps


def solve_bvp(field: EnvField, start: Tuple[float, float], target: Tuple[float, float],
              V_s: float, t0: float, theta_guess: Optional[float] = None, *,
              dt: float = 600.0, tol_m: float = 1852.0, max_iters: int = 8,
              fd_step: float = 1e-6, max_steps: int = 20000,
              max_transit_factor: float = 5.0, ds: float = GRAD_STEP_M,
              sphere_correction: bool = False) -> Tuple[Route, bool, int]:
    """Alg 4.13 lines 3-4: Newton-correct theta0 so the characteristic hits `target`.

    Returns (route, converged, iters). `theta_guess` defaults to the initial great-circle
    bearing; in production it is the heading of the first leg of the grid route, which is what
    puts Newton inside the basin of attraction -- the global sweep is not optional.

    Tolerance defaults to 1 nautical mile (Alg 4.13 line 4).

    THE DERIVATIVE IS A FINITE DIFFERENCE, NOT THE VARIATIONAL EQUATION, and that is a
    deliberate choice rather than a shortcut. The variational equation ds/dt = J s needs
    J = d(rhs)/d(state), and the rhs already contains the first derivatives of the current, so
    J contains its SECOND derivatives. Operational forecasts are delivered as trilinear
    interpolants: inside a cell the second derivative is identically zero, and across a cell
    face it is a delta function. Differencing it yields either 0 or a spurious spike depending
    on where the step lands, so a variational solve would be propagating noise with the
    authority of an ODE. A central difference in theta0 differences the FULLY INTEGRATED
    trajectory, which is smooth in theta0 even when the field is only C0, and it is also
    cheaper here: two extra trajectories per iteration against six extra rhs evaluations per
    step.

    Step size: `fd_step` = 1e-6 rad (0.2 arcsec). The residual is accumulated over ~10^3 RK4
    steps on displacements of ~10^6 m, so its round-off floor is ~10^3 * 2e-16 * 10^6 ~ 1e-7 m.
    A 1e-6 rad perturbation moves the far end of a 1000 km route by ~1 m, seven orders above
    that floor, while the central-difference truncation error h^2 e'''/6 stays ~1e-6 m against
    a derivative of ~1e6 m/rad. Both error sources are therefore below 1e-11 relative.

    Non-convergence is reported, never hidden. Two failure modes are detected separately:
    exhausting `max_iters`, and |de/dtheta0| collapsing below a fraction of the direct range.
    The second is the CUT LOCUS signature -- the terminal point has stopped responding to the
    initial heading because two distinct characteristics tie -- and per Alg 4.13 that is a
    feature to surface ("north or south of the storm, both equally good"), so it is written
    into `route.notes` rather than swallowed.

    `max_transit_factor` caps the shot at that multiple of the drift-free direct time D/V_s.
    It is not cosmetic. On a sphere a drift-dominated field (|c| > V_s) has NO unreachable
    points: with 12 m/s of zonal current and a 3 m/s ship, the shot happily finds a
    characteristic that circumnavigates and arrives from the far side, converging to a
    39-million-second route that is a perfectly valid Zermelo extremal and a completely
    useless answer. The cap excludes those; a caller who genuinely wants one raises it.
    """
    if not (V_s > 0.0):
        raise ValueError(f"solve_bvp needs positive through-water speed, got {V_s!r}")
    if not math.isfinite(t0):
        raise ValueError(f"t0 must be finite, got {t0!r}")

    slat, slon = _clamp_lat(start[0]), wrap_pi(start[1])
    tlat, tlon = _clamp_lat(target[0]), wrap_pi(target[1])
    D = haversine(slat, slon, tlat, tlon)

    theta = initial_bearing(slat, slon, tlat, tlon) if theta_guess is None else wrap_pi(theta_guess)
    notes: List[str] = []

    if D <= tol_m:
        wps = [Waypoint(slat, slon, t0, theta, 1.0, 0.0)]
        notes.append("start and target coincide within tolerance; no shooting performed")
        return Route(wps, 0.0, 0.0, 0.0, notes=notes), True, 0

    # Below this the endpoint has stopped responding to theta0: cut locus, or the drift
    # dominates the ship (|c| >= V_s) and whole sectors are unreachable. 1e-4 * D metres per
    # radian is four orders below the ~D m/rad a well-posed shot exhibits.
    deriv_floor = max(1.0, 1e-4 * D)
    t_max = t0 + max(dt, max_transit_factor * D / V_s)

    def residual(th: float) -> Tuple[float, float, List[Waypoint]]:
        wps = _track(field, (slat, slon), (tlat, tlon), th, V_s, t0, dt, max_steps,
                     t_max, ds, sphere_correction)
        signed, miss, _, _, _, _ = _closest_approach(wps, (tlat, tlon))
        return signed, miss, wps

    e, miss, wps = residual(theta)
    converged = miss <= tol_m
    iters = 0
    cut_locus = False

    while not converged and iters < max_iters:
        iters += 1
        e_p, _, _ = residual(theta + fd_step)
        e_m, _, _ = residual(theta - fd_step)
        de = (e_p - e_m) / (2.0 * fd_step)

        if not math.isfinite(de) or abs(de) < deriv_floor:
            cut_locus = True
            notes.append(f"shooting derivative collapsed (|de/dtheta0| = {abs(de):.3e} m/rad "
                         f"< {deriv_floor:.3e}); cut locus or drift-dominated cell")
            break

        step = -e / de
        # A Newton step larger than this means the linearisation is not trusted; the grid
        # route is supposed to have delivered a guess within a few degrees.
        step = max(-0.5, min(0.5, step))

        accepted = False
        for _ in range(6):                       # backtracking line search on |residual|
            th_try = wrap_pi(theta + step)
            e_try, miss_try, wps_try = residual(th_try)
            if abs(e_try) < abs(e) or miss_try <= tol_m:
                theta, e, miss, wps = th_try, e_try, miss_try, wps_try
                accepted = True
                break
            step *= 0.5
        if not accepted:
            notes.append("line search failed to reduce the terminal miss; keeping best iterate")
            break
        converged = miss <= tol_m

    signed, miss, t_c, lat_c, idx, lon_c = _closest_approach(wps, (tlat, tlon))

    route_wps = [Waypoint(w.lat, w.lon, w.t, w.theta, w.q, w.sog) for w in wps[:idx + 1]]
    tail = wps[min(idx + 1, len(wps) - 1)]
    if converged:
        # Land the final waypoint exactly on the target: the residual is already inside
        # tolerance, so this is snapping to the intended point, not moving the solution.
        route_wps.append(Waypoint(tlat, tlon, t_c, tail.theta, tail.q, tail.sog))
    else:
        route_wps.append(Waypoint(lat_c, lon_c, t_c, tail.theta, tail.q, tail.sog))
        notes.append(f"Zermelo shooting did NOT converge: miss {miss:.1f} m after "
                     f"{iters} iteration(s); caller must fall back to the grid route")

    notes.append(f"Zermelo polish: theta0 = {math.degrees(theta):.4f} deg, "
                 f"terminal miss {miss:.2f} m, {iters} Newton iteration(s)"
                 + (", CUT LOCUS FLAGGED" if cut_locus else ""))
    notes.append("fuel and risk are not evaluated here: solve_bvp is the geometric polish and "
                 "takes no Vessel; the caller re-scores the polished track against the metric")

    route = Route(route_wps, max(0.0, t_c - t0), 0.0, 0.0, notes=notes)
    return route, converged, iters


# ============================================================== notch projection (Alg 4.14)
def _invert_power(vessel: Vessel, P_target: float) -> float:
    """Smallest V with calm_power(V) >= P_target, by bisection on [0, V_max_hull].

    Bisection rather than inverting the Admiralty exponent in closed form because types.py
    explicitly invites `calm_power` to be replaced by a spline through a measured speed-power
    curve. Lemma 1.4 guarantees strict monotonicity, which is all bisection needs.
    """
    lo, hi = 0.0, vessel.V_max_hull
    if vessel.calm_power(hi) <= P_target:
        return hi
    for _ in range(50):                          # 8.5 m/s / 2^50 is far below float resolution
        mid = 0.5 * (lo + hi)
        if vessel.calm_power(mid) < P_target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _speed_bounds(vessel: Vessel) -> Tuple[float, float]:
    """(V_lo, V_hi): the through-water speeds the engine can actually hold.

    V_lo is the minimum stable engine load q_min (below it the plant must stop, not slow), and
    V_hi is the tighter of the hull/contract cap and the speed at MCR. For the default
    Handymax the MCR cap binds first, so the hull cap never appears -- which is the correct
    behaviour and worth checking on any new vessel.
    """
    return (_invert_power(vessel, vessel.q_min * vessel.P_MCR),
            min(vessel.V_max_hull, _invert_power(vessel, vessel.P_MCR)))


def default_banned(vessel: Vessel, env: Env, V: float, theta: float) -> bool:
    """S1, S2, S3, S7 of docs/01-formulation.md section 1.4. True = forbidden.

    LIMITATION, stated rather than hidden: S4 (slamming), S5 (green water) and S6 (lateral
    acceleration) are all Ochi-type criteria on moments of the RELATIVE MOTION RESPONSE
    SPECTRUM, m0^r and m2^r. Computing those needs the vessel RAOs and a directional wave
    spectrum, which live in the `seakeeping` module, not here. They are therefore NOT
    evaluated by this predicate; pass a `banned=` callable from `seakeeping` to enforce them.
    Since S4-S6 only ever ADD forbidden regions, this predicate is an under-approximation of
    the ban set: `notch_project` driven by it will fix every violation it can see and will not
    invent any, but it cannot certify full admissibility on its own.

    Two modelling choices the spec leaves to the vessel record. The spec writes distinct
    thresholds H_s^roll and H_s^par for S1 and S2; `Vessel` exposes only `hs_caution` and
    `hs_limit`, so both map to `hs_caution` (the comfort/cargo threshold -- resonant roll in a
    1 m sea is not an operational concern). And the resonance tests use |omega_e|: in
    following seas the ship can overtake the waves and the encounter frequency passes through
    zero and changes sign, but the roll excitation depends on its magnitude.
    """
    if not math.isfinite(V) or V < 0.0:
        return True

    bans = vessel.bans_enabled

    # S7 first because it is CONTROL-INDEPENDENT: when it fires no (V, theta) is admissible
    # and the projection search below must be allowed to fail rather than spin.
    if bans & BAN_S7:
        if env.hs > vessel.hs_limit:
            return True
        if env.depth - vessel.T_d - vessel.ukc_margin < 0.0:
            return True

    mu_rel = wrap_pi(env.mu_w - theta)           # 0 = following, +-pi = head (section 1.4)
    omega_p = env.wave_omega_p
    omega_e = omega_p - (omega_p * omega_p * V / G) * math.cos(mu_rel)
    omega_phi = vessel.omega_roll
    lam = env.wave_length_p

    if bans & BAN_S1:
        if abs(abs(omega_e) - omega_phi) < 0.10 * omega_phi and env.hs > vessel.hs_caution:
            return True

    if bans & BAN_S2:
        if (abs(abs(omega_e) - 2.0 * omega_phi) < 0.15 * 2.0 * omega_phi
                and 0.8 * vessel.L <= lam <= 2.0 * vessel.L
                and env.hs > vessel.hs_caution):
            return True

    if bans & BAN_S3:
        froude = V / math.sqrt(G * vessel.L)
        if froude > 0.30 and abs(mu_rel) < 0.25 * math.pi and lam > 0.8 * vessel.L:
            return True

    return False


def _nearest_admissible_speed(vessel: Vessel, env: Env, theta: float, V_cmd: float,
                              banned: BanPredicate, V_lo: float, V_hi: float,
                              n_scan: int, tol_V: float) -> Optional[float]:
    """Nearest admissible V to V_cmd at fixed heading, snapped onto the ban BOUNDARY.

    The bans carve V-intervals out of [V_lo, V_hi] (S1 and S2 are resonance windows in
    encounter frequency, S3 a Froude threshold), so the admissible set is a union of a few
    closed intervals and its nearest point to V_cmd is an endpoint of one of them.

    BOTH neighbouring boundaries are refined before they are compared, and that ordering
    matters. Comparing raw scan samples instead picks the wrong side whenever the scan step
    is coarser than the difference between the two gap widths: for the default Handymax in
    following seas the S1 window is (4.706, 6.688) m/s, so a command of 5.7 m/s sits 0.994
    from the lower edge and 0.988 from the upper -- an asymmetry of 6 mm/s that a 192-point
    scan over a 3.7 m/s envelope (19 mm/s per step) cannot resolve. Refining first makes the
    result independent of `n_scan`, which is what the phrase "nearest admissible boundary
    control" has to mean if it is to mean anything.
    """
    if V_hi <= V_lo:
        return None

    # The bisection needs a point known to be INSIDE the notch to converge against. V_cmd may
    # lie outside the engine envelope (the sweep can command a speed the plant cannot hold),
    # so clamp it first; if the clamped point is already admissible that is the answer.
    V_ref = min(V_hi, max(V_lo, V_cmd))
    if not banned(vessel, env, V_ref, theta):
        return V_ref

    n_scan = max(8, n_scan)
    step = (V_hi - V_lo) / n_scan
    below: Optional[float] = None
    above: Optional[float] = None
    for i in range(n_scan + 1):
        v = V_lo + i * step
        if banned(vessel, env, v, theta):
            continue
        if v <= V_ref:
            below = v                        # samples ascend, so this keeps the last one
        elif above is None:
            above = v

    def _refine(v_ok: float) -> float:
        """Push an admissible sample toward V_ref until it sits on the ban boundary."""
        v_bad = V_ref
        while abs(v_ok - v_bad) > tol_V:
            mid = 0.5 * (v_ok + v_bad)
            if banned(vessel, env, mid, theta):
                v_bad = mid
            else:
                v_ok = mid
        return v_ok

    cands = [_refine(v) for v in (below, above) if v is not None]
    if not cands:
        return None
    return min(cands, key=lambda v: abs(v - V_cmd))


def notch_project(route: Route, vessel: Vessel, field: EnvField, *,
                  banned: Optional[BanPredicate] = None,
                  n_speed_scan: int = 192, n_heading_scan: int = 36,
                  tol_V: float = 1e-4) -> Tuple[Route, int]:
    """Alg 4.14 / Prop 2.6: snap banned controls onto the admissible boundary, re-integrate.

    Design decision D4 solves the route against `conv V`, whose support function cannot see
    the dents S1-S7 punch in the indicatrix, so the returned control may sit inside a notch --
    realisable only by chattering between two admissible headings at infinite frequency, which
    a rudder with a rate limit cannot do. This walks the route and replaces every such control
    with the nearest control that is actually steerable. Prop 2.6 bounds the cost of doing so
    by L_x v_max tau_d S.

    Returns (new_route, n_projected). The input route is not mutated.

    HOW THE CONTROL IS RECOVERED. A Waypoint stores position and time, so the commanded
    control is reconstructed per leg: the ground velocity is the leg displacement over the leg
    duration, and subtracting the current gives the through-water vector, whose magnitude is V
    and whose direction is the commanded heading theta. Note that theta is generally NOT the
    course over ground -- the difference is the set-and-leeway crab angle, which is exactly the
    distinction Leg.theta is annotated with in types.py.

    HOW THE LEG IS RE-INTEGRATED, and its limitation. The projection holds the GROUND TRACK
    fixed and re-integrates the SCHEDULE: the new speed made good along the leg is the
    projection of the new over-ground velocity onto the leg direction, the leg duration is the
    leg length over that, and every later waypoint shifts in time. Later legs are then sampled
    at their shifted times, so a projection early in the voyage correctly changes the weather
    the rest of the voyage sees. What this deliberately does NOT do is move the waypoints:
    the track was chosen by the sweep against bathymetry and traffic separation, and re-routing
    it is the sweep's job, not the projection's. A projection that must change heading is
    therefore recorded with its heading offset so the caller can decide whether to re-solve.

    The fuel total is adjusted by the per-leg DELTA between the old and the new control,
    evaluated with the vessel's own calm-water power and SFOC curves for both. Taking a
    difference rather than a total is what makes this legitimate: the added wave resistance
    that this module cannot see enters both terms and cancels to first order, so the correction
    is right even though neither absolute figure would be. `risk` is left untouched -- there is
    no risk model here and fabricating one would be worse than reporting the sweep's.
    """
    predicate: BanPredicate = default_banned if banned is None else banned
    src = route.waypoints
    notes = list(route.notes)

    if len(src) < 2:
        notes.append("notch projection skipped: route has fewer than two waypoints")
        return Route(list(src), route.time_s, route.fuel_kg, route.risk, route.comfort,
                     route.expanded, route.label_peak, route.certificate_gap, notes), 0

    V_lo, V_hi = _speed_bounds(vessel)
    if V_hi <= V_lo:
        notes.append(f"notch projection skipped: empty engine envelope "
                     f"[{V_lo:.3f}, {V_hi:.3f}] m/s")
        return Route(list(src), route.time_s, route.fuel_kg, route.risk, route.comfort,
                     route.expanded, route.label_peak, route.certificate_gap, notes), 0

    def fuel_rate(V: float) -> float:
        P = vessel.calm_power(V)
        return vessel.sfoc(P) * P

    out = [Waypoint(src[0].lat, src[0].lon, src[0].t, src[0].theta, src[0].q, src[0].sog)]
    t_cur = src[0].t
    horizon = field.horizon
    n_projected = 0
    d_fuel = 0.0

    for i in range(len(src) - 1):
        a, b = src[i], src[i + 1]
        dt_leg = b.t - a.t
        lat_mid = 0.5 * (a.lat + b.lat)
        east, north = local_step_metres(lat_mid, b.lat - a.lat, wrap_pi(b.lon - a.lon))
        leg_len = math.hypot(east, north)

        if dt_leg <= 0.0 or leg_len <= _TINY:
            # Degenerate leg (a duplicated waypoint, or a wait). No control to project; carry
            # the schedule and the previous control through unchanged.
            t_cur += max(0.0, dt_leg)
            out.append(Waypoint(b.lat, b.lon, t_cur, out[-1].theta, out[-1].q, 0.0))
            continue

        u_e, u_n = east / leg_len, north / leg_len
        t_sample = min(t_cur + 0.5 * dt_leg, horizon)
        env = field.at(_clamp_lat(lat_mid),
                       wrap_pi(a.lon + 0.5 * wrap_pi(b.lon - a.lon)), t_sample)

        vg_e, vg_n = east / dt_leg, north / dt_leg
        w_e, w_n = vg_e - env.cu, vg_n - env.cv          # through-water velocity vector
        V_cmd = math.hypot(w_e, w_n)
        # Drift exactly cancels the ground velocity: the ship is stopped in the water and the
        # heading is undefined. Keep the previous commanded heading rather than emit atan2(0,0).
        theta_cmd = out[-1].theta if V_cmd < 1e-9 else vec_to_heading(w_e, w_n)

        V_new, theta_new = V_cmd, theta_cmd
        in_envelope = V_lo - tol_V <= V_cmd <= V_hi + tol_V
        violated = (not in_envelope) or predicate(vessel, env, V_cmd, theta_cmd)

        if violated:
            # First try holding the heading and moving only the speed: voluntary speed
            # reduction is the cheapest response and the one a master reaches for first.
            cand = _nearest_admissible_speed(vessel, env, theta_cmd, V_cmd, predicate,
                                             V_lo, V_hi, n_speed_scan, tol_V)
            if cand is None:
                # No admissible speed on this heading. Sweep outward in heading and take the
                # smallest deviation that admits any speed. If S7 fired, nothing will.
                dth_step = math.pi / max(1, n_heading_scan)
                found = None
                for k in range(1, n_heading_scan + 1):
                    for sgn in (1.0, -1.0):
                        th = wrap_pi(theta_cmd + sgn * k * dth_step)
                        v = _nearest_admissible_speed(vessel, env, th, V_cmd, predicate,
                                                      V_lo, V_hi, n_speed_scan, tol_V)
                        if v is not None:
                            found = (v, th)
                            break
                    if found is not None:
                        break
                if found is None:
                    notes.append(f"leg {i}: NO admissible control exists (control-independent "
                                 f"ban, e.g. S7 Hs {env.hs:.2f} m or under-keel clearance); "
                                 f"leg left unprojected")
                    t_cur += dt_leg
                    out.append(Waypoint(b.lat, b.lon, t_cur, theta_cmd, a.q, a.sog))
                    continue
                V_new, theta_new = found
            else:
                V_new = cand

        n_e, n_n = heading_to_vec(theta_new)
        sog_new = (V_new * n_e + env.cu) * u_e + (V_new * n_n + env.cv) * u_n

        if violated and sog_new <= _TINY:
            # The projected control cannot make progress along this leg (drift exceeds the
            # admissible speed in this direction). Reverting is honest: the ban is real but so
            # is the fact that this module may not move the track.
            notes.append(f"leg {i}: projected control makes no progress along the leg "
                         f"(sog {sog_new:.3f} m/s); leg left unprojected and FLAGGED")
            t_cur += dt_leg
            out.append(Waypoint(b.lat, b.lon, t_cur, theta_cmd, a.q, a.sog))
            continue

        if violated:
            n_projected += 1
            dt_new = leg_len / sog_new
            d_fuel += fuel_rate(V_new) * dt_new - fuel_rate(V_cmd) * dt_leg
            notes.append(f"leg {i}: projected V {V_cmd:.3f} -> {V_new:.3f} m/s, "
                         f"theta {math.degrees(theta_cmd):.2f} -> {math.degrees(theta_new):.2f} "
                         f"deg, dt {dt_leg:.0f} -> {dt_new:.0f} s")
        else:
            dt_new = dt_leg
            sog_new = leg_len / dt_leg

        q_new = min(1.0, vessel.calm_power(V_new) / vessel.P_MCR) if vessel.P_MCR > 0 else 1.0
        out[-1].theta = theta_new
        out[-1].q = q_new
        out[-1].sog = sog_new
        t_cur += dt_new
        out.append(Waypoint(b.lat, b.lon, t_cur, theta_new, q_new, sog_new))

        if t_cur > horizon:
            notes.append(f"leg {i}: schedule ran past the forecast horizon; later legs are "
                         f"projected against the last valid frame")

    if n_projected:
        notes.append(f"notch projection: {n_projected} leg(s) projected onto the ban boundary; "
                     f"fuel delta {d_fuel:+.1f} kg (calm-water model, taken as a difference so "
                     f"the unmodelled added resistance cancels to first order); risk NOT "
                     f"re-evaluated")

    new = Route(out, out[-1].t - out[0].t, max(0.0, route.fuel_kg + d_fuel), route.risk,
                route.comfort, route.expanded, route.label_peak, route.certificate_gap, notes)
    return new, n_projected


# ============================================================== self-test
if __name__ == "__main__":
    import sys

    class _Uniform:
        """Spatially and temporally constant current. dtheta/dt must be EXACTLY zero."""

        def __init__(self, cu: float, cv: float, **kw):
            self._e = Env(cu=cu, cv=cv, **kw)

        def at(self, lat: float, lon: float, t: float) -> Env:
            return self._e

        @property
        def t0(self) -> float:
            return 0.0

        @property
        def horizon(self) -> float:
            return 1e12

    class _Shear:
        """cu = alpha * y with y = R_E * lat the north arc distance; cv = 0.

        du/dy = alpha exactly and every other partial is exactly zero, so
        dtheta/dt = alpha sin^2(theta) holds on the sphere as well as in the plane.
        """

        def __init__(self, alpha: float):
            self.alpha = alpha

        def at(self, lat: float, lon: float, t: float) -> Env:
            return Env(cu=self.alpha * R_E * lat, cv=0.0)

        @property
        def t0(self) -> float:
            return 0.0

        @property
        def horizon(self) -> float:
            return 1e12

    fails: List[str] = []

    def check(name: str, ok: bool, detail: str) -> None:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")
        if not ok:
            fails.append(name)

    # ---------------------------------------------------------------- 1. uniform current
    print("\n== TEST 1: uniform current -> dtheta/dt identically zero (Eq 3.7) ==")
    uf = _Uniform(cu=0.9, cv=-0.4)
    V_s = 6.5

    worst = 0.0
    for ilat in range(-6, 7):
        for ilon in range(-6, 7):
            for ith in range(24):
                la = ilat * 0.2
                lo = ilon * 0.5
                th = ith * math.pi / 12.0
                _, _, dth = zermelo_rhs(uf, la, lo, 0.0, th, V_s)
                worst = max(worst, abs(dth))
    check("max |dtheta/dt| over 4056 samples", worst < 1e-14, f"{worst:.3e} rad/s")

    wps = shoot(uf, (0.35, -0.2), 1.0, V_s, 0.0, 600.0, 120)
    turn = max(abs(wrap_pi(w.theta - 1.0)) for w in wps)
    check("max intermediate turn over 120 RK4 steps", turn < 1e-14, f"{turn:.3e} rad")

    vg = math.hypot(V_s * math.sin(1.0) + 0.9, V_s * math.cos(1.0) - 0.4)
    arc = sum(haversine(wps[i].lat, wps[i].lon, wps[i + 1].lat, wps[i + 1].lon)
              for i in range(len(wps) - 1))
    exp_arc = vg * 600.0 * 120
    check("track arc length vs |v_ground| * T", abs(arc / exp_arc - 1.0) < 2e-6,
          f"{arc:.1f} m vs {exp_arc:.1f} m (rel {arc / exp_arc - 1.0:+.2e})")

    # tol_m tightened to 1 m (from the 1 nm operational default) so that this measures the
    # Newton solve rather than the tolerance: 1852 m of permitted miss over a 510 km route is
    # 3.6e-3 rad of heading slack, which would make any theta0 check meaningless.
    tgt = (wps[-1].lat, wps[-1].lon)
    r_u, conv_u, it_u = solve_bvp(uf, (0.35, -0.2), tgt, V_s, 0.0, 0.9, dt=600.0, tol_m=1.0)
    th_err = max(abs(wrap_pi(w.theta - 1.0)) for w in r_u.waypoints)
    check("solve_bvp recovers theta0 = 1.0 rad (tol 1 m)", conv_u and th_err < 1e-5,
          f"converged={conv_u}, {it_u} iters, max |theta - 1.0| = {th_err:.3e} rad")
    check("solve_bvp route has ZERO intermediate turns",
          max(abs(wrap_pi(r_u.waypoints[k + 1].theta - r_u.waypoints[k].theta))
              for k in range(len(r_u.waypoints) - 2)) == 0.0,
          "all commanded headings bitwise identical")

    # ---------------------------------------------------------------- 2. linear shear
    print("\n== TEST 2: linear shear cu = alpha*y -> analytic Zermelo solution ==")
    alpha = 1.0 / 3.0e5                       # 1 m/s per 300 km
    sf = _Shear(alpha)
    V2, dt2, n2 = 6.0, 300.0, 200
    th0 = math.radians(80.0)                  # psi0 = +10 deg, north of east

    worst_rhs = 0.0
    for ith in range(48):
        th = ith * math.pi / 24.0
        _, _, dth = zermelo_rhs(sf, 0.01, 0.03, 0.0, th, V2)
        worst_rhs = max(worst_rhs, abs(dth - alpha * math.sin(th) ** 2))
    check("|dtheta/dt - alpha sin^2(theta)|", worst_rhs < 1e-18, f"{worst_rhs:.3e} rad/s")

    w2 = shoot(sf, (0.0, 0.0), th0, V2, 0.0, dt2, n2)

    # Analytic: dpsi/dt = -alpha cos^2(psi) => tan psi(t) = tan psi0 - alpha t.
    psi0 = 0.5 * math.pi - th0
    worst_tan = 0.0
    for w in w2:
        psi = 0.5 * math.pi - w.theta
        worst_tan = max(worst_tan, abs(math.tan(psi) - (math.tan(psi0) - alpha * (w.t - 0.0))))
    check("max |tan psi(t) - (tan psi0 - alpha t)|", worst_tan < 1e-12, f"{worst_tan:.3e}")

    T = n2 * dt2
    psi_T = math.atan(math.tan(psi0) - alpha * T)
    th_T = 0.5 * math.pi - psi_T
    check("theta(T) vs analytic", abs(w2[-1].theta - th_T) < 1e-12,
          f"{w2[-1].theta:.12f} vs {th_T:.12f} rad (err {w2[-1].theta - th_T:+.3e})")

    # y(psi) - y0 = -(V/alpha)(sec psi - sec psi0); exact on the sphere because
    # d(R_E lat)/dt = V sin psi with no cos(lat) factor.
    y_an = -(V2 / alpha) * (1.0 / math.cos(psi_T) - 1.0 / math.cos(psi0))
    y_num = R_E * w2[-1].lat
    check("north displacement vs analytic", abs(y_num / y_an - 1.0) < 1e-9,
          f"{y_num:.4f} m vs {y_an:.4f} m (rel {y_num / y_an - 1.0:+.3e})")

    # x(psi): K = alpha*y0 + V sec psi0; the sec^3 integral gives the closed form below.
    def _x_of(psi: float, K: float) -> float:
        sec, tan = 1.0 / math.cos(psi), math.tan(psi)
        lg = math.log(abs(sec + tan))
        return -(1.0 / alpha) * (0.5 * V2 * lg + K * tan - 0.5 * V2 * sec * tan)

    K = V2 / math.cos(psi0)
    x_an = _x_of(psi_T, K) - _x_of(psi0, K)
    x_num = R_E * w2[-1].lon
    check("east displacement vs PLANAR analytic (cos(lat) gap expected ~3e-6)",
          abs(x_num / x_an - 1.0) < 2e-5,
          f"{x_num:.2f} m vs {x_an:.2f} m (rel {x_num / x_an - 1.0:+.3e})")

    # ---------------------------------------------------------------- 3. bvp in shear
    print("\n== TEST 3: solve_bvp in shear -> bows north into the favourable current ==")
    lon_t = 400_000.0 / R_E
    r_s, conv_s, it_s = solve_bvp(sf, (0.0, 0.0), (0.0, lon_t), V2, 0.0, dt=300.0)
    _, miss_s, _, _, _, _ = _closest_approach(r_s.waypoints, (0.0, lon_t))
    max_lat = max(w.lat for w in r_s.waypoints)
    t_straight = 400_000.0 / V2
    check("converged to within 1 nm", conv_s and miss_s <= 1852.0,
          f"converged={conv_s}, {it_s} iters, miss {miss_s:.1f} m")
    check("route bows NORTH into the stronger current", max_lat > 0.0,
          f"max northing {R_E * max_lat / 1000.0:.2f} km")
    check("beats the straight rhumb line", r_s.time_s < t_straight,
          f"{r_s.time_s:.1f} s vs {t_straight:.1f} s "
          f"({100.0 * (1.0 - r_s.time_s / t_straight):.3f} % faster)")

    # ---------------------------------------------------------------- 4. notch projection
    print("\n== TEST 4: notch projection onto the S1 synchronous-roll boundary ==")
    ves = Vessel()
    V_lo, V_hi = _speed_bounds(ves)
    print(f"  engine envelope: V in [{V_lo:.4f}, {V_hi:.4f}] m/s "
          f"({V_lo / 0.5144444444:.2f} - {V_hi / 0.5144444444:.2f} kt), "
          f"omega_roll = {ves.omega_roll:.5f} rad/s")

    tol_V_default = 1e-4                       # matches notch_project's tol_V default
    V_ban = 5.7                                # inside the S1 resonance window, following seas
    wf = _Uniform(cu=0.0, cv=0.0, hs=5.5, tp=10.0, mu_w=0.0, depth=3000.0)
    check("commanded 5.7 m/s due north in following seas is banned",
          default_banned(ves, wf.at(0, 0, 0), V_ban, 0.0), "S1 fires as predicted")

    raw = shoot(wf, (0.2, 0.1), 0.0, V_ban, 0.0, 600.0, 20)
    r_in = Route(raw, raw[-1].t - raw[0].t, 0.0, 0.25)
    r_out, n_proj = notch_project(r_in, ves, wf)
    sog_out = r_out.waypoints[0].sog
    # The upper S1 edge, from |omega_e| = 0.9 omega_phi in following seas:
    # V = (omega_p - 0.9 omega_phi) * g / omega_p^2.
    om_p = wf.at(0, 0, 0).wave_omega_p
    V_edge = (om_p - 0.9 * ves.omega_roll) * G / (om_p * om_p)
    V_edge_lo = (om_p - 1.1 * ves.omega_roll) * G / (om_p * om_p)
    print(f"  S1 window at theta=0: V in ({V_edge_lo:.4f}, {V_edge:.4f}) m/s; "
          f"commanded {V_ban} sits {V_ban - V_edge_lo:.4f} above the lower edge and "
          f"{V_edge - V_ban:.4f} below the upper -- the upper is nearer")
    check("every leg projected", n_proj == len(raw) - 1, f"{n_proj} of {len(raw) - 1} legs")
    check("projected speed snaps to the NEARER (upper) S1 boundary",
          abs(sog_out - V_edge) < 2.0 * tol_V_default,
          f"{sog_out:.5f} m/s vs analytic edge {V_edge:.5f} "
          f"(err {sog_out - V_edge:+.2e}); no current, so sog == V")
    check("projected control is admissible",
          not default_banned(ves, wf.at(0, 0, 0), sog_out, 0.0), "S1 cleared")
    check("projected control is on the BOUNDARY (1 mm/s slower is banned)",
          default_banned(ves, wf.at(0, 0, 0), sog_out - 1e-3, 0.0), "boundary confirmed")
    check("schedule re-integrated: faster ship arrives earlier",
          r_out.time_s < r_in.time_s,
          f"{r_out.time_s:.1f} s vs {r_in.time_s:.1f} s "
          f"(ratio {r_out.time_s / r_in.time_s:.6f} vs V ratio {V_ban / sog_out:.6f})")
    check("ground track held fixed", all(
        abs(r_out.waypoints[k].lat - raw[k].lat) == 0.0
        and abs(r_out.waypoints[k].lon - raw[k].lon) == 0.0 for k in range(len(raw))),
        "all waypoint positions bitwise unchanged")

    # control-independent ban: S7 must be detected, not looped on
    sf7 = _Uniform(cu=0.0, cv=0.0, hs=9.0, tp=10.0, mu_w=0.0, depth=3000.0)
    r7, n7 = notch_project(Route([Waypoint(w.lat, w.lon, w.t) for w in raw[:4]],
                                 raw[3].t, 0.0, 0.0), ves, sf7)
    check("S7 (Hs 9.0 > 6.5 m) reported as unprojectable, not looped", n7 == 0
          and any("NO admissible control" in s for s in r7.notes),
          f"{n7} projected, {sum('NO admissible' in s for s in r7.notes)} legs flagged")

    # ---------------------------------------------------------------- 5. degeneracies
    print("\n== TEST 5: degenerate cases return finite numbers, never NaN ==")
    strong = _Uniform(cu=12.0, cv=0.0)         # drift far exceeds ship speed
    rr = zermelo_rhs(strong, 0.5, 0.5, 0.0, 1.2, 3.0)
    check("drift > ship speed: rhs finite", all(math.isfinite(x) for x in rr),
          f"{tuple(f'{x:.3e}' for x in rr)}")
    rr = zermelo_rhs(uf, 0.5 * math.pi, 0.0, 0.0, 1.0, V_s)
    check("at the north pole: rhs finite", all(math.isfinite(x) for x in rr),
          f"{tuple(f'{x:.3e}' for x in rr)}")
    rr = zermelo_rhs(uf, 0.1, 0.0, 0.0, 1.0, 0.0)
    check("V_s = 0 (pure drift): rhs finite", all(math.isfinite(x) for x in rr),
          f"{tuple(f'{x:.3e}' for x in rr)}")
    try:
        zermelo_rhs(uf, 0.1, 0.0, 0.0, 1.0, -1.0)
        check("V_s < 0 raises", False, "no exception")
    except ValueError as exc:
        check("V_s < 0 raises ValueError", True, str(exc))

    # 12 m/s of easting against a 3 m/s ship, target to the WEST. With an unbounded budget
    # this is REACHABLE -- the extremal circumnavigates -- which is why the transit cap
    # exists. Under an operational budget it must report failure rather than a bad route.
    r_far, conv_far, it_far = solve_bvp(strong, (0.0, 0.0), (0.4, -0.6), 3.0, 0.0,
                                        dt=600.0, max_iters=6, max_steps=200)
    check("target beyond the shooting budget reports converged=False",
          conv_far is False, f"converged={conv_far} after {it_far} iters; "
          f"note: {[n for n in r_far.notes if 'NOT converge' in n or 'collapsed' in n][0][:88]}")

    r_circ, conv_circ, _ = solve_bvp(strong, (0.0, 0.0), (0.4, -0.6), 3.0, 0.0, dt=600.0,
                                     max_transit_factor=1e3)
    check("...but the circumnavigating extremal IS found when the cap is lifted",
          conv_circ, f"converged={conv_circ}, transit {r_circ.time_s / 86400.0:.1f} days "
                     f"-- valid Zermelo extremal, useless route; hence max_transit_factor")

    # ------------------------------------------------- 6. RK4 order and the sphere term
    print("\n== TEST 6: RK4 convergence order, and sphere_correction vs a true great circle ==")
    psi0_b = math.radians(10.0)
    th0_b, Tb = 0.5 * math.pi - psi0_b, 60_000.0
    th_an_b = 0.5 * math.pi - math.atan(math.tan(psi0_b) - alpha * Tb)
    ratios, prev = [], None
    for nb in (25, 50, 100):
        wb = shoot(sf, (0.0, 0.0), th0_b, 6.0, 0.0, Tb / nb, nb)
        eb = abs(wb[-1].theta - th_an_b)
        if prev is not None:
            ratios.append(prev / eb)
        prev = eb
    check("halving dt cuts the heading error by 16 (RK4 is 4th order)",
          all(14.0 < r < 18.0 for r in ratios),
          "error ratios " + ", ".join(f"{r:.2f}" for r in ratios)
          + " at dt = 2400 -> 1200 -> 600 s")

    still = _Uniform(cu=0.0, cv=0.0)
    st6 = (math.radians(35.0), math.radians(-40.0))
    for corr in (False, True):
        w6 = shoot(still, st6, math.radians(70.0), 8.0, 0.0, 600.0, 900, sphere_correction=corr)
        end6 = (w6[-1].lat, w6[-1].lon)
        defect = max(abs(wrap_pi(p.theta - initial_bearing(p.lat, p.lon, *end6)))
                     for p in w6[:-2])
        gc = haversine(st6[0], st6[1], *end6)
        arc6 = sum(haversine(w6[i].lat, w6[i].lon, w6[i + 1].lat, w6[i + 1].lon)
                   for i in range(len(w6) - 1))
        if corr:
            check("sphere_correction=True traces a TRUE GREAT CIRCLE",
                  math.degrees(defect) < 1e-3 and abs(arc6 / gc - 1.0) < 1e-9,
                  f"bearing defect {math.degrees(defect):.6f} deg, "
                  f"arc/great-circle = {arc6 / gc:.9f} over {gc / 1000.0:.0f} km")
        else:
            check("sphere_correction=False is a RHUMB LINE (Eq 3.7 is a plane result)",
                  math.degrees(defect) > 1.0,
                  f"bearing defect {math.degrees(defect):.4f} deg, "
                  f"{arc6 - gc:.0f} m longer than the great circle "
                  f"({100.0 * (arc6 / gc - 1.0):.2f} %) over {gc / 1000.0:.0f} km")

    print(f"\n{'ALL TESTS PASSED' if not fails else 'FAILURES: ' + ', '.join(fails)}")
    sys.exit(1 if fails else 0)
