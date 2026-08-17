"""The Finsler metric: indicatrix, gauge, support function, anisotropy.

Spec reference: 02-metric.md (Def 2.1-2.3, Eq (2.1), Def 2.6, Prop 2.7, Def 2.9) and
CONTRACT.md design decisions D1, D2, D4.

Three objects live here and they answer the same question at three levels of fidelity:

  RandersMetric   constant through-water speed, current only, no waves, no bans.
                  Closed form, exact to machine precision. This is the ground truth every
                  numerical claim in the project is measured against, and it is also the
                  fast path for the (many) cells where the sea state is below threshold.

  FinslerMetric   the real thing. Throttle is a control (D1), so a direction carries a
                  one-parameter *family* of legs rather than a speed; waves make the
                  attainable speed heading-dependent, which turns the drift correction into
                  a fixed point; seakeeping bans cut the control set and destroy convexity,
                  which D4 says to ignore at solve time and repair afterwards.

  SupportTable    D2. h(x,t,.) sampled on n_theta directions per (cell, forecast hour).
                  The gauge is recovered from it by duality in O(log n_theta) instead of
                  O(n_throttle) physics evaluations, which is the main inner-loop win.

Conventions, all inherited and none of them negotiable: angles in radians, vectors in the
local (east, north) frame with EAST FIRST, headings 0 = north clockwise via
`geodesy.heading_to_vec`, and `mu_w` is the direction waves travel TOWARDS.
"""
from __future__ import annotations

import math
from typing import List, Optional, Protocol, Sequence, Tuple

import numpy as np

from .geodesy import heading_to_vec, vec_to_heading, wrap_pi
from .types import G, RHO_AIR, RHO_SW, Env, EnvField, Leg, Vessel

Vec2 = Tuple[float, float]

__all__ = [
    "randers_gauge",
    "effective_drift",
    "RandersMetric",
    "FinslerMetric",
    "SupportTable",
    "ReferencePhysics",
    "PhysicsLike",
    "S1_SYNC_ROLL", "S2_PARAM_ROLL", "S3_SURF_RIDE", "S4_SLAM",
    "S5_GREEN_WATER", "S6_LATERAL_ACC", "S7_ENVELOPE",
]


# ============================================================ the Randers closed form
def randers_gauge(vx: float, vy: float, cx: float, cy: float, V_s: float) -> float:
    """Minkowski gauge of the disc D(c, V_s): F = inf{tau > 0 : v/tau in D}. Eq (2.1).

    Derivation (02-metric.md 2.2). `v/tau` lies in the disc iff |v - tau*c| <= tau*V_s, i.e.

        phi(tau) := lam*tau^2 + 2*<v,c>*tau - |v|^2  >=  0,      lam := V_s^2 - |c|^2

    and F is the smallest positive tau with phi(tau) >= 0. Writing a = <v,c>, D = |v|^2 and
    disc = a^2 + lam*D, the two roots are (-a +- sqrt(disc))/lam.

    BRANCH CHOICE, and it matters. The textbook form F = (sqrt(disc) - a)/lam subtracts two
    nearly equal quantities when a > 0 (a following current), because then
    sqrt(a^2 + lam*D) -> |a| = a as lam -> 0. The relative cancellation factor is
    1 - a/sqrt(disc), so the digits lost grow like log10(a^2/(lam*D)): about one digit at
    |c|/V_s = 0.9, seven at |c|/V_s = 1 - 1e-8. Multiplying by the conjugate gives

        F = D / (a + sqrt(disc))

    which adds two positive quantities when a > 0 and is unconditionally stable there. For
    a <= 0 the roles swap -- a + sqrt(disc) is the cancelling pair -- so the direct form is
    used instead. Each branch is exact to a couple of ulp; see the self-test at the bottom.

    Degenerations (spec (P3), and 01-formulation 1.5 on the Kropina case |c| >= V_s):
      * v = 0            -> 0.0 (the gauge of the zero vector).
      * lam > 0          -> always finite; 0 is interior to the disc, every direction is
                            makeable.
      * lam <= 0, a <= 0 -> +inf. phi has no positive root: the drift is at least as strong
                            as the ship and this direction has a non-positive projection on
                            it, so it cannot be made good at all.
      * lam <= 0, a > 0, disc < 0 -> +inf. Inside the forbidden cone: the direction is
                            within the drift's half-plane but outside the reachable wedge of
                            half-angle arcsin(V_s/|c|).
    Never returns NaN.
    """
    D = vx * vx + vy * vy
    if D <= 0.0:
        return 0.0
    a = vx * cx + vy * cy
    lam = V_s * V_s - (cx * cx + cy * cy)
    disc = a * a + lam * D
    if a > 0.0:
        if disc < 0.0:                      # Kropina forbidden cone
            return math.inf
        return D / (a + math.sqrt(disc))    # conjugate form, stable for a > 0
    if lam <= 0.0:                          # no positive root exists
        return math.inf
    return (math.sqrt(disc) - a) / lam      # direct form, stable for a <= 0


def _randers_gauge_naive(vx: float, vy: float, cx: float, cy: float, V_s: float) -> float:
    """Eq (2.1) transcribed literally, single branch. Kept ONLY so the self-test can
    measure how many digits the naive transcription throws away. Do not call it."""
    D = vx * vx + vy * vy
    a = vx * cx + vy * cy
    lam = V_s * V_s - (cx * cx + cy * cy)
    if lam <= 0.0:
        return math.inf
    return (math.sqrt(a * a + lam * D) - a) / lam


def effective_drift(vessel: Vessel, env: Env) -> Vec2:
    """c_eff = c + kappa_L * W10, spec 01-formulation 1.2. Everything downstream of this
    function means c_eff when it says "current"."""
    return env.cu + vessel.kappa_L * env.wu, env.cv + vessel.kappa_L * env.wv


# ============================================================ Randers metric
class RandersMetric:
    """Closed-form gauge for the constant-speed, current-only case. Exact ground truth.

    Implements MetricLike, so it drops into the solver unchanged. Its `legs` carries no
    fuel or risk model -- there is no throttle in this model, so there is nothing to trade
    off -- and reports zeros for both. Use FinslerMetric when the objectives matter.

    Note that this class reads `env.cu, env.cv` raw and does NOT add leeway: it has no
    vessel and therefore no kappa_L. That is deliberate. It is the analytic reference for
    the pure-Zermelo test cases of 06-implementation-plan 6.5 level 1, where the "current"
    is whatever the test field says it is.
    """

    __slots__ = ("V_s", "field")

    def __init__(self, V_s: float, field: EnvField) -> None:
        if not (V_s >= 0.0) or not math.isfinite(V_s):
            raise ValueError(f"V_s must be finite and non-negative, got {V_s!r}")
        self.V_s = float(V_s)
        self.field = field

    # ------------------------------------------------------------------ the gauge
    def F(self, lat: float, lon: float, t: float, vx: float, vy: float) -> float:
        """Eq (2.1). +inf where the direction is unmakeable, 0.0 for the zero vector."""
        e = self.field.at(lat, lon, t)
        return randers_gauge(vx, vy, e.cu, e.cv, self.V_s)

    def sigma_max(self, lat: float, lon: float, t: float, u: Vec2) -> float:
        """Speed made good in unit direction u. 0.0 if infeasible.

        Computed as 1/F rather than from the algebraically equivalent
        sigma = <u,c> + sqrt(<u,c>^2 + lam): that form cancels for a head-on current with
        |c| -> V_s, whereas F's branches never do, and inverting a well-conditioned
        quantity costs one ulp.
        """
        ue, un = u
        n = math.hypot(ue, un)
        if n <= 0.0:
            return 0.0
        f = self.F(lat, lon, t, ue / n, un / n)
        if not math.isfinite(f) or f <= 0.0:
            return 0.0
        return 1.0 / f

    def support(self, lat: float, lon: float, t: float, p: Vec2) -> float:
        """h(p) = max over the disc D(c, V_s) of <v,p> = <c,p> + V_s|p|. Def 2.6, exact.

        No sampling, no tabulation error: this is the value SupportTable is measured
        against when checking Prop 2.7.
        """
        e = self.field.at(lat, lon, t)
        px, py = p
        return e.cu * px + e.cv * py + self.V_s * math.hypot(px, py)

    def anisotropy(self, lat: float, lon: float, t: float) -> float:
        """Upsilon_loc = sigma_max/sigma_min = (V_s + |c|)/(V_s - |c|). Def 2.9, exact.

        sigma(u) = <u,c> + sqrt(<u,c>^2 + lam) is increasing in <u,c>, which ranges over
        [-|c|, |c|], so the extremes are attained dead downstream and dead upstream. +inf
        once |c| >= V_s, which is the correct answer and the one the stencil sizing in
        04-algorithm must handle rather than divide by.
        """
        e = self.field.at(lat, lon, t)
        cm = math.hypot(e.cu, e.cv)
        if cm >= self.V_s:
            return math.inf
        return (self.V_s + cm) / (self.V_s - cm)

    def legs(self, lat: float, lon: float, t: float, u: Vec2) -> List[Leg]:
        """A single leg: no throttle dimension, hence no Pareto family. Empty if infeasible."""
        sog = self.sigma_max(lat, lon, t, u)
        if sog <= 0.0:
            return []
        e = self.field.at(lat, lon, t)
        # Heading that makes u good: cancel the cross-track drift (same algebra as
        # FinslerMetric._solve_leg, but V is constant so there is no fixed point to iterate).
        alpha = vec_to_heading(*u)
        ue, un = u
        n = math.hypot(ue, un)
        ue, un = ue / n, un / n
        c_cross = -e.cu * un + e.cv * ue
        theta = alpha + math.asin(max(-1.0, min(1.0, c_cross / self.V_s))) if self.V_s > 0 else alpha
        return [Leg(sog=sog, fuel_rate=0.0, risk_rate=0.0, risk_level=0.0,
                    comfort_rate=0.0, q=1.0, theta=wrap_pi(theta))]


# ============================================================ physics interface
S1_SYNC_ROLL = 1 << 0
S2_PARAM_ROLL = 1 << 1
S3_SURF_RIDE = 1 << 2
S4_SLAM = 1 << 3
S5_GREEN_WATER = 1 << 4
S6_LATERAL_ACC = 1 << 5
S7_ENVELOPE = 1 << 6


class PhysicsLike(Protocol):
    """What FinslerMetric needs from the vessel/seakeeping layer. Three functions.

    This is the seam CONTRACT.md section 4 specifies, split so that `use_bans=False` can
    skip the ban evaluation entirely rather than paying for it and discarding the answer.
    `kairos.seakeeping` and `kairos.vessel` are expected to provide an object satisfying
    this; until they do, `ReferencePhysics` below is used and says so in its docstring.
    """

    def attainable(self, vessel: Vessel, env: Env, theta: float, q: float) -> float:
        """Speed through water [m/s] sustainable at heading theta on throttle q. >= 0."""
        ...

    def violations(self, vessel: Vessel, env: Env, theta: float, q: float, V: float) -> int:
        """Bitmask of violated seakeeping criteria S1..S7. 0 means admissible."""
        ...

    def rates(self, vessel: Vessel, env: Env, theta: float, q: float,
              V: float) -> Tuple[float, float, float, float]:
        """(fuel_rate kg/s, risk_rate 1/s, risk_level -, comfort_rate 1/s)."""
        ...


class ReferencePhysics:
    """The powering / ban / rate model, at the fidelity 01-formulation defines and no more.

    This exists so that `metric.py` runs standalone today. It implements, honestly:
      * calm-water power from `Vessel.calm_power` (Admiralty form by default);
      * added resistance in waves by STAwave-1 (ISO 15016 Annex), 01-formulation 1.3, with
        the directionality factor f_dir = 0.625 - 0.375*cos(mu_rel): 1.0 in head seas,
        0.25 in following seas, which is the range that section quotes;
      * windage as a quadratic drag on the apparent wind with a constant C_X = 0.9,
        NOT Fujiwara's regression -- superstructure geometry is not in `Vessel`;
      * the attainable-speed map V_pwr as the root of P_required(V) = q*P_MCR, by bisection
        (01-formulation 1.3: P is strictly increasing in V, so the root is unique);
      * seakeeping criteria S1 (synchronous roll), S2 (parametric roll), S3 (surf-riding)
        and S7 (operator envelope), which are computable from Env and Vessel alone.

    LIMITATION, stated rather than hidden: S4 (slamming), S5 (green water) and S6 (lateral
    acceleration) all need the spectral moments m0r, m2r of the relative vertical motion,
    which need RAOs or a strip-theory pass. They are NOT evaluated here and never appear in
    the returned bitmask. A `kairos.seakeeping` that computes them should be passed to
    FinslerMetric(physics=...) and will be used in place of this class wholesale.

    The risk scalar is the prototype's (shiprouting/src/ship.py): sea state relative to the
    operator limit, with a beam-sea penalty. `risk_rate` is `risk_level`/3600, so the
    additive risk objective of 01-formulation 1.6 is measured in risk-hours and the
    bottleneck objective reads `risk_level` directly.
    """

    __slots__ = ("c_x_wind", "hs_roll_frac", "_v_rtol")

    def __init__(self, c_x_wind: float = 0.9, hs_roll_frac: float = 0.5) -> None:
        self.c_x_wind = c_x_wind
        # Roll criteria S1/S2 only bite once the sea is big enough to excite the ship. We
        # key that threshold to half the vessel's own comfort threshold rather than to a
        # loose constant; a seakeeping.py with RAOs should key it to the roll response.
        self.hs_roll_frac = hs_roll_frac
        self._v_rtol = 4.0 * 2.220446049250313e-16      # 4 ulp, relative

    # ---------------------------------------------------------------- resistance
    @staticmethod
    def added_resistance_waves(vessel: Vessel, env: Env, theta: float) -> float:
        """STAwave-1 mean added resistance in waves [N]. 01-formulation 1.3."""
        if env.hs <= 0.0:
            return 0.0
        mu_rel = wrap_pi(env.mu_w - theta)          # 0 = following, +-pi = head
        f_dir = 0.625 - 0.375 * math.cos(mu_rel)
        return (RHO_SW * G * env.hs * env.hs * vessel.B
                * math.sqrt(vessel.B / vessel.L_bwl) * f_dir / 16.0)

    def wind_resistance(self, vessel: Vessel, env: Env, theta: float, V: float) -> float:
        """Longitudinal windage on the apparent wind [N], positive = resisting.

        Apparent wind is W10 minus the ship's own through-water velocity. Taking the drag
        as -1/2 rho C_X A_T |W_a| <W_a, n> rather than 1/2 rho C_X A_T |W_a|^2 cos(psi)
        keeps it a smooth function of heading through the zero-wind point, which the
        heading fixed point in `FinslerMetric._solve_leg` needs and the cos form does not
        provide (|W_a| is not differentiable at W_a = 0, the product is).
        """
        nx, ny = heading_to_vec(theta)
        wax, way = env.wu - V * nx, env.wv - V * ny
        speed = math.hypot(wax, way)
        if speed <= 0.0:
            return 0.0
        w_along = wax * nx + way * ny               # < 0 in a head wind
        return -0.5 * RHO_AIR * self.c_x_wind * vessel.A_T * speed * w_along

    def power_required(self, vessel: Vessel, env: Env, theta: float, V: float) -> float:
        """Shaft power [W] to hold V through water at heading theta. Increasing in V."""
        if V <= 0.0:
            return 0.0
        R_add = (self.added_resistance_waves(vessel, env, theta)
                 + self.wind_resistance(vessel, env, theta, V))
        return vessel.calm_power(V) + R_add * V / vessel.eta_D

    # ---------------------------------------------------------------- attainable speed
    def attainable(self, vessel: Vessel, env: Env, theta: float, q: float) -> float:
        """V_pwr: the largest V with P_required(V, theta) <= q*P_MCR, capped by the hull.

        Bisection rather than Newton: P_required is only piecewise smooth (the windage term
        has a kink at zero apparent wind) and bisection cannot leave the bracket.

        The stopping criterion is RELATIVE (a few ulp of the bracket), not a fixed 1e-13.
        That matters more than it looks: this root is the inner function of the heading
        fixed point in `FinslerMetric._solve_leg`, and a fixed absolute tolerance puts a
        noise floor of that size on V, which the outer iteration then cannot converge
        below -- it thrashes, hits its iteration cap, and silently falls back to bisection
        on every leg. Returning V to full double precision removes the floor.

        Involuntary speed loss is not a separate multiplier here -- it IS this root moving
        left as the added resistance grows, which is what 01-formulation 1.3 says it is.
        """
        target = q * vessel.P_MCR
        if target <= 0.0:
            return 0.0
        hi = vessel.V_max_hull
        if self.power_required(vessel, env, theta, hi) <= target:
            return hi                                # power-unlimited: hull cap binds
        lo = 0.0
        for _ in range(80):
            mid = 0.5 * (lo + hi)
            if mid <= lo or mid >= hi:        # bracket is adjacent doubles: done
                break
            if self.power_required(vessel, env, theta, mid) <= target:
                lo = mid
            else:
                hi = mid
            if hi - lo <= self._v_rtol * hi:
                break
        return lo

    # ---------------------------------------------------------------- bans
    def violations(self, vessel: Vessel, env: Env, theta: float, q: float, V: float) -> int:
        """S1, S2, S3, S7 of 01-formulation 1.4. S4/S5/S6 are not evaluated (see class doc)."""
        flags = 0
        if env.hs > vessel.hs_limit:                                   # S7
            flags |= S7_ENVELOPE

        mu_rel = wrap_pi(env.mu_w - theta)
        cos_mu = math.cos(mu_rel)
        omega_p = env.wave_omega_p
        omega_e = omega_p - (omega_p * omega_p * V / G) * cos_mu       # 01-formulation 1.4
        omega_phi = vessel.omega_roll
        hs_roll = self.hs_roll_frac * vessel.hs_caution
        lam_w = env.wave_length_p

        if env.hs > hs_roll and abs(omega_e - omega_phi) < 0.10 * omega_phi:
            flags |= S1_SYNC_ROLL
        if (env.hs > hs_roll and abs(omega_e - 2.0 * omega_phi) < 0.15 * 2.0 * omega_phi
                and 0.8 * vessel.L <= lam_w <= 2.0 * vessel.L):
            flags |= S2_PARAM_ROLL
        if (V > 0.30 * math.sqrt(G * vessel.L) and abs(mu_rel) < 0.25 * math.pi
                and lam_w > 0.8 * vessel.L):
            flags |= S3_SURF_RIDE

        return flags & vessel.bans_enabled

    # ---------------------------------------------------------------- objective rates
    def rates(self, vessel: Vessel, env: Env, theta: float, q: float,
              V: float) -> Tuple[float, float, float, float]:
        """(fuel kg/s, risk 1/s, risk level -, comfort 1/s).

        Fuel is SFOC(P)*P at the DELIVERED power q*P_MCR, not at P_required(V): the engine
        burns what the throttle commands. Since SFOC has its minimum at q = 0.75 (types.py),
        fuel per metre is non-monotone in q, which is exactly what makes the Pareto family
        of D1 non-degenerate.

        Comfort is a scalar proxy -- beam-sea exposure relative to the comfort threshold --
        not the MSI/MII of criterion S6, which needs the spectral moments this class does
        not have.
        """
        P = q * vessel.P_MCR
        fuel_rate = vessel.sfoc(P) * P

        mu_rel = wrap_pi(env.mu_w - theta)
        beam = abs(math.sin(mu_rel))
        risk_level = (env.hs / vessel.hs_limit) * (1.0 + 0.35 * beam) if vessel.hs_limit > 0 else 0.0
        comfort_rate = (env.hs * beam / max(vessel.hs_caution, 1e-9)) / 3600.0
        return fuel_rate, risk_level / 3600.0, risk_level, comfort_rate


def _default_physics() -> PhysicsLike:
    """Use `kairos.seakeeping`'s physics object if that module has landed AND asks to be the
    default, else the reference model in this file. Checked by duck-typing the three
    PhysicsLike methods so that a partial seakeeping.py cannot half-satisfy the interface and
    fail at solve time.

    INTEGRATOR NOTE. `seakeeping.PHYSICS` now exists (it did not when this function was
    written, so this branch had never once been taken and both `seakeeping` and `powering`
    were unreachable from the solver). It is opt-in rather than automatic because the full
    chain costs roughly 20x per control evaluation; `seakeeping.FULL_PHYSICS_DEFAULT = True`
    or an explicit `FinslerMetric(..., physics=seakeeping.PHYSICS)` selects it.
    """
    try:
        from . import seakeeping  # type: ignore
    except ImportError:
        return ReferencePhysics()
    if not getattr(seakeeping, "FULL_PHYSICS_DEFAULT", False):
        return ReferencePhysics()
    obj = getattr(seakeeping, "PHYSICS", None) or getattr(seakeeping, "Physics", None)
    if obj is None:
        return ReferencePhysics()
    if isinstance(obj, type):
        obj = obj()
    if all(callable(getattr(obj, m, None)) for m in ("attainable", "violations", "rates")):
        return obj
    return ReferencePhysics()


# ============================================================ the full metric
_FP_RES_TOL = 1e-11        # cross-track residual, relative to V. 1e-11*8 m/s is a 1e-11 rad
                           # heading error: physically meaningless, and still 1e5 above the
                           # attainable-speed root find's own noise floor.
_FP_ITERS = 10             # see _solve_leg docstring for the measured iteration count
_SOG_FLOOR = 1e-9          # below this the direction is not being made good at all


class FinslerMetric:
    """The indicatrix of Def 1.1 and its gauge, with throttle as a control (D1).

    `n_theta` is the direction sampling used by `support` and `anisotropy` only; `legs` and
    `sigma_max` are evaluated at the exact requested direction and are not quantised.

    `use_bans=False` solves with the ban set switched off. That is not a shortcut -- it is
    how the realisability gap of Thm 2.11 is measured, by differencing the two solves.
    """

    __slots__ = ("vessel", "field", "n_theta", "n_throttle", "use_bans", "physics",
                 "_throttles", "_dirs", "fp_fallbacks", "fp_iters_max")

    def __init__(self, vessel: Vessel, field: EnvField, n_theta: int = 72,
                 n_throttle: int = 5, use_bans: bool = True,
                 physics: Optional[PhysicsLike] = None) -> None:
        if n_theta < 8:
            raise ValueError(f"n_theta must be at least 8, got {n_theta}")
        if n_throttle < 1:
            raise ValueError(f"n_throttle must be at least 1, got {n_throttle}")
        self.vessel = vessel
        self.field = field
        self.n_theta = int(n_theta)
        self.n_throttle = int(n_throttle)
        self.use_bans = bool(use_bans)
        self.physics = physics if physics is not None else _default_physics()

        # Throttle samples, descending. Descending order is load-bearing: sog increases with
        # V and V increases with q, so `sigma_max` can stop at the first admissible sample.
        if n_throttle == 1:
            self._throttles = (1.0,)
        else:
            step = (1.0 - vessel.q_min) / (n_throttle - 1)
            self._throttles = tuple(1.0 - i * step for i in range(n_throttle))

        dphi = 2.0 * math.pi / self.n_theta
        self._dirs = tuple(heading_to_vec(k * dphi) for k in range(self.n_theta))
        self.fp_fallbacks = 0     # legs that needed the bisection fallback
        self.fp_iters_max = 0     # worst fixed-point iteration count observed

    # ---------------------------------------------------------------- one control
    def _solve_leg(self, env: Env, alpha: float,
                   c_along: float, c_cross: float, q: float) -> Optional[Leg]:
        """Drift correction at fixed throttle. Returns None if this control cannot make u good.

        Geometry. With u at heading alpha, decompose the drift as
            c_along  = <c, u>,        c_cross = <c, u_perp>,   u_perp = (-u_n, u_e).
        The ground velocity V*n(theta) + c is parallel to u iff its cross-track component
        vanishes. Since <n(theta), u_perp> = sin(alpha - theta),

            V * sin(theta - alpha) = c_cross        =>   theta = alpha + asin(c_cross / V)

        and taking the forward root of the along-track component,

            sog = sqrt(V^2 - c_cross^2) + c_along.

        THE FIXED POINT. V = V_pwr(theta, q) depends on theta, because added resistance is
        directional, so the two lines above are coupled. Iterate theta_{k+1} = alpha +
        asin(c_cross / V(theta_k)) from theta_0 = alpha. The map's derivative is

            |dTheta/dtheta| = |c_cross| |dV/dtheta| / (V^2 sqrt(1 - (c_cross/V)^2))

        Convergence is linear, and the observed rate is the one that sets `_FP_ITERS` -- it
        was measured, not assumed, because the estimate and the measurement disagree by an
        order of magnitude. At full throttle in a 5 m sea the rate is ~3e-3, as the formula
        above predicts with |dV/dtheta| ~ 0.12 m/s/rad and V ~ 8 m/s. At q_min it degrades
        to ~3e-2: V drops to ~3.2 m/s, and the rate scales as 1/V^2. The relative cross-
        track residual then runs

            7.4e-3, 2.3e-4, 7.1e-6, 2.2e-7, 6.9e-9, 2.2e-10, 6.7e-12, 2.1e-13, ... -> 0

        so "3-4 iterations" is right only for the physically meaningful tolerances (1e-7
        relative is already a 1e-6 rad heading error); driving the residual to 1e-11 takes
        6 in most directions and 8 in the worst one on the 72x5 control grid of the
        self-test. `_FP_ITERS = 10` is that measured worst case plus margin, and gives zero
        fallbacks there.

        The contraction degrades as |c_cross| -> V, where the arcsin steepens without bound
        -- which is exactly where the direction is about to become infeasible anyway. If the
        residual is still above tolerance after `_FP_ITERS`, fall back to bisection on

            g(theta) = V(theta) sin(theta - alpha) - c_cross

        over [alpha - pi/2, alpha + pi/2], where g is continuous, g(alpha - pi/2) < 0 and
        g(alpha + pi/2) > 0 whenever the direction is feasible at all. That fallback always
        converges; `self.fp_fallbacks` counts how often it fires and `self.fp_iters_max`
        records the worst iteration count, so the cost is measured rather than assumed.
        """
        att = self.physics.attainable
        vessel = self.vessel

        theta = alpha
        V = att(vessel, env, theta, q)
        residual = math.inf
        for it in range(_FP_ITERS):
            if V <= abs(c_cross):
                return None                      # cannot hold the track at this throttle
            # theta solves V_old*sin(theta-alpha) = c_cross exactly, so the residual after
            # re-evaluating V measures (V_new - V_old): the fixed point converges iff V does.
            theta = alpha + math.asin(max(-1.0, min(1.0, c_cross / V)))
            V = att(vessel, env, theta, q)
            residual = V * math.sin(theta - alpha) - c_cross
            if abs(residual) <= _FP_RES_TOL * V:
                break
        self.fp_iters_max = max(self.fp_iters_max, it + 1)

        if V <= abs(c_cross):
            return None
        if abs(residual) > _FP_RES_TOL * V:
            self.fp_fallbacks += 1
            lo, hi = alpha - 0.5 * math.pi, alpha + 0.5 * math.pi
            g_lo = -att(vessel, env, lo, q) - c_cross
            g_hi = att(vessel, env, hi, q) - c_cross
            if not (g_lo < 0.0 < g_hi):
                return None                      # no bracket: direction is unreachable
            for _ in range(60):
                mid = 0.5 * (lo + hi)
                if att(vessel, env, mid, q) * math.sin(mid - alpha) - c_cross < 0.0:
                    lo = mid
                else:
                    hi = mid
            theta = 0.5 * (lo + hi)
            V = att(vessel, env, theta, q)
            if V <= abs(c_cross):
                return None

        if self.use_bans and self.physics.violations(vessel, env, theta, q, V):
            return None

        sog = math.sqrt(max(0.0, V * V - c_cross * c_cross)) + c_along
        if sog <= _SOG_FLOOR:
            return None                          # set carries the ship backwards

        fuel_rate, risk_rate, risk_level, comfort_rate = self.physics.rates(
            vessel, env, theta, q, V)
        return Leg(sog=sog, fuel_rate=fuel_rate, risk_rate=risk_rate,
                   risk_level=risk_level, comfort_rate=comfort_rate,
                   q=q, theta=wrap_pi(theta))

    @staticmethod
    def _decompose(env_c: Vec2, ue: float, un: float) -> Tuple[float, float]:
        cx, cy = env_c
        return cx * ue + cy * un, -cx * un + cy * ue

    # ---------------------------------------------------------------- MetricLike
    def legs(self, lat: float, lon: float, t: float, u: Vec2) -> List[Leg]:
        """D1 made real: the Pareto-nondominated (sog high, fuel low, risk low) legs in
        direction u, sorted by decreasing sog. Empty means F = +inf there.

        Dominance is tested on RATES, not on per-metre quantities. Time and fuel accumulate
        independently along the route (Prop 5.4), so a leg that is slower but burns less per
        second is genuinely incomparable and must survive; collapsing to fuel-per-metre here
        would silently discard labels the solver is entitled to.
        """
        ue, un = u
        n = math.hypot(ue, un)
        if n <= 0.0:
            return []
        ue, un = ue / n, un / n
        alpha = vec_to_heading(ue, un)
        env = self.field.at(lat, lon, t)
        c_along, c_cross = self._decompose(effective_drift(self.vessel, env), ue, un)

        cand: List[Leg] = []
        for q in self._throttles:
            leg = self._solve_leg(env, alpha, c_along, c_cross, q)
            if leg is not None:
                cand.append(leg)
        if not cand:
            return []

        # O(n_throttle^2) pairwise filter. n_throttle is 5 by default; a sort-based sweep
        # would be asymptotically better and measurably slower at this size.
        front: List[Leg] = []
        for i, a in enumerate(cand):
            dominated = False
            for j, b in enumerate(cand):
                if i == j:
                    continue
                if (b.sog >= a.sog and b.fuel_rate <= a.fuel_rate
                        and b.risk_level <= a.risk_level
                        and (b.sog > a.sog or b.fuel_rate < a.fuel_rate
                             or b.risk_level < a.risk_level)):
                    dominated = True
                    break
            if not dominated:
                front.append(a)
        front.sort(key=lambda lg: -lg.sog)
        return front

    def sigma_max(self, lat: float, lon: float, t: float, u: Vec2) -> float:
        """Fastest speed made good in direction u; 0.0 if infeasible.

        Equivalent to legs(...)[0].sog but stops at the first admissible throttle, because
        sog is increasing in V and V is increasing in q. Bans break that monotonicity in the
        FEASIBILITY of a sample (S3 forbids high speed in following seas while permitting
        low), which is why the loop continues past a rejected sample rather than giving up
        -- but it never has to evaluate a sample below the first one that is accepted.
        """
        ue, un = u
        n = math.hypot(ue, un)
        if n <= 0.0:
            return 0.0
        ue, un = ue / n, un / n
        alpha = vec_to_heading(ue, un)
        env = self.field.at(lat, lon, t)
        c_along, c_cross = self._decompose(effective_drift(self.vessel, env), ue, un)
        for q in self._throttles:
            leg = self._solve_leg(env, alpha, c_along, c_cross, q)
            if leg is not None:
                return leg.sog
        return 0.0

    def support(self, lat: float, lon: float, t: float, p: Vec2) -> float:
        """h(p) = max over conv(V) of <v,p>. Def 2.6.

        Evaluated as max_k sigma(u_k) <u_k, p> over the n_theta sampled directions, then
        refined by golden section over the bracket around the best sample. Every value
        entering the max is the inner product with a genuine boundary point of V, so the
        result is the support function of a polygon inscribed in conv(V) and therefore a
        LOWER bound -- it can never overstate what the ship can do, which is the safe sign
        for a Hamiltonian. Refinement drops the gap from O((pi/n)^2) to the root-find
        tolerance for convex V.

        Limitation: with bans active V is not convex, the sampled objective need not be
        unimodal, and golden section may polish a local maximum. The sampled max itself is
        still correct to O((pi/n)^2) because support(V) = support(conv V) (D4), so the error
        is bounded by the sampling either way; only the refinement's benefit is lost.
        """
        px, py = p
        pn = math.hypot(px, py)
        if pn <= 0.0:
            return 0.0

        best, best_k = -math.inf, 0
        vals = [0.0] * self.n_theta
        for k, (ue, un) in enumerate(self._dirs):
            s = self.sigma_max(lat, lon, t, (ue, un))
            vals[k] = s * (ue * px + un * py)
            if vals[k] > best:
                best, best_k = vals[k], k

        if best <= -math.inf:
            return 0.0

        dphi = 2.0 * math.pi / self.n_theta
        lo = (best_k - 1) * dphi
        hi = (best_k + 1) * dphi

        def obj(phi: float) -> float:
            ue, un = heading_to_vec(phi)
            return self.sigma_max(lat, lon, t, (ue, un)) * (ue * px + un * py)

        # Golden section, 24 iterations: 0.618^24 shrinks a 2*dphi bracket by 5e-6, i.e. to
        # about 1e-7 rad at n_theta = 72, well past where the O(bracket^2) objective is flat.
        inv_phi = 0.5 * (math.sqrt(5.0) - 1.0)
        c1 = hi - inv_phi * (hi - lo)
        c2 = lo + inv_phi * (hi - lo)
        f1, f2 = obj(c1), obj(c2)
        for _ in range(24):
            if f1 < f2:
                lo, c1, f1 = c1, c2, f2
                c2 = lo + inv_phi * (hi - lo)
                f2 = obj(c2)
            else:
                hi, c2, f2 = c2, c1, f1
                c1 = hi - inv_phi * (hi - lo)
                f1 = obj(c1)
        return max(best, f1, f2)

    def anisotropy(self, lat: float, lon: float, t: float) -> float:
        """Upsilon_loc = sigma_max/sigma_min over the n_theta sampled directions. Def 2.9.

        +inf if any sampled direction is infeasible, which is the honest answer: the metric
        is one-sided there and no finite stencil radius is admissible.
        """
        hi, lo = 0.0, math.inf
        for d in self._dirs:
            s = self.sigma_max(lat, lon, t, d)
            if s <= 0.0:
                return math.inf
            hi = max(hi, s)
            lo = min(lo, s)
        if lo <= 0.0:
            return math.inf
        return hi / lo

    def indicatrix(self, lat: float, lon: float, t: float) -> List[Tuple[float, float]]:
        """The n_theta (heading, sigma) pairs that Phase 1 of the build plan plots. Not part
        of MetricLike; it exists because the polar plot of V is the figure that explains the
        project, per 06-implementation-plan 6.7."""
        dphi = 2.0 * math.pi / self.n_theta
        return [(k * dphi, self.sigma_max(lat, lon, t, d))
                for k, d in enumerate(self._dirs)]


# ============================================================ D2: support tabulation
class SupportTable:
    """Precomputed support function on n_theta directions per (cell, forecast hour). D2.

    Layout is a dense float64 array [n_time][n_lat][n_lon][n_theta], C-contiguous with the
    direction axis last so that a single cell's whole indicatrix is one cache line run --
    which is the access pattern of the update in 04-algorithm.

    Prop 2.7 (support-function tabulation is exact for convex indicatrices) is what licenses
    reading sigma back out of this table. Its numerical form, which the self-test measures:

        For convex V and h tabulated EXACTLY on n uniformly spaced directions, the recovery
            sigma_hat(u) = min over k with <u,p_k> > 0 of  h(p_k)/<u,p_k>
        is the radial function of the circumscribed polygon P ⊇ V. Hence the recovery is
        one-sided, sigma_hat >= sigma, and the error is O(n^-2).

    The constant in that O(n^-2) is NOT sec(pi/n) - 1 in general, and getting this wrong is
    easy. sec(pi/n) - 1 is the bound on the radial error measured from the CENTRE of the
    inscribed disc. Sigma is measured from the ORIGIN, and for a Randers indicatrix the
    origin sits at -c relative to the centre. Concretely, for V = D(c, V_s) the stored
    half-planes are <v - c, p_k> <= V_s, so P - c is the regular n-gon circumscribing the
    disc of radius V_s and therefore

        V  ⊆  P  ⊆  D(c, V_s * sec(pi/n)) ,

    which is a pointwise bound on sigma_hat but one whose worst relative effect is upstream,
    where sigma is smallest:

        max_u [sigma_hat(u)/sigma(u) - 1]  =  (sec(pi/n) - 1) * V_s / (V_s - |c|).

    The amplification factor V_s/(V_s - |c|) is 1 for a still ocean and diverges as the
    metric degenerates. The self-test asserts the pointwise containment bound directly
    rather than the circular one; measured values sit right on it.

    The recovery is a minimisation of a quasi-convex sequence over the half-circle of
    directions with <u,p_k> > 0 -- quasi-convex because h(.)/<u,.> blows up at both ends of
    that arc and touches its minimum where the supporting line grazes the boundary at
    sigma(u)u. So ternary search finds it in O(log n_theta), which is the D2 claim, and
    `sigma_max` does exactly that rather than the O(n_theta) scan.

    READ THIS BEFORE COMPARING THE TABLE AGAINST THE METRIC. `SupportTable.sigma_max` and
    `FinslerMetric.sigma_max` do NOT agree when seakeeping bans are active, and the
    disagreement is not a bug in either. A support function cannot see a non-convex dent
    (h_V = h_{conv V}), so the table necessarily describes conv V, while the metric's own
    `sigma_max` describes V. Measured on the default bulker in Hs = 3 m with bans on:

        bans off  ->  max relative excess 1.1e-3   (pure direction discretisation, n = 72)
        bans on   ->  max relative excess 3.5e-1   in the parametric-roll notch,
                      median 2.9e-4 elsewhere

    That 35 % is the chattering gap of D4 and 02-metric.md 2.5, localised exactly where a
    heading is banned: the table says the ship can average its way across the notch, which
    it can only do by oscillating heading faster than a rudder moves. This is by design --
    the solver is supposed to run on conv V and get a genuine lower bound -- but it means
    the table is NOT a drop-in substitute for the metric when reporting achievable speeds.
    Route reconstruction must re-query the metric and then run the notch projection, and
    Thm 2.11 bounds what that costs. A test that asserts table == metric with bans on is
    testing the wrong thing.
    """

    __slots__ = ("lats", "lons", "times", "n_theta", "h", "_dirs", "_dphi")

    def __init__(self, lats: np.ndarray, lons: np.ndarray, times: np.ndarray,
                 n_theta: int, h: np.ndarray) -> None:
        self.lats = np.asarray(lats, dtype=np.float64)
        self.lons = np.asarray(lons, dtype=np.float64)
        self.times = np.asarray(times, dtype=np.float64)
        self.n_theta = int(n_theta)
        self.h = h
        self._dphi = 2.0 * math.pi / self.n_theta
        self._dirs = np.array([heading_to_vec(k * self._dphi) for k in range(self.n_theta)],
                              dtype=np.float64)

    # ---------------------------------------------------------------- construction
    @staticmethod
    def build(metric, grid, times: Sequence[float], n_theta: Optional[int] = None
              ) -> "SupportTable":
        """Tabulate `metric.support` over the grid and forecast times.

        `grid` is anything exposing 1-D `lats` and `lons` in RADIANS, or a (lats, lons)
        pair. `n_theta` defaults to the metric's own sampling if it has one, else 72 (D2).

        Cost is n_time * n_lat * n_lon * n_theta support evaluations and is embarrassingly
        parallel over cells; it is done serially here because the reference implementation
        is single-threaded by construction (house rule: stdlib + numpy only).
        """
        if hasattr(grid, "lats") and hasattr(grid, "lons"):
            lats, lons = np.asarray(grid.lats, dtype=np.float64), np.asarray(grid.lons, dtype=np.float64)
        else:
            lats, lons = (np.asarray(a, dtype=np.float64) for a in grid)
        if n_theta is None:
            n_theta = int(getattr(metric, "n_theta", 72))
        times_a = np.asarray(times, dtype=np.float64)
        if times_a.ndim != 1 or times_a.size == 0:
            raise ValueError("times must be a non-empty 1-D sequence")
        if np.any(np.diff(times_a) <= 0.0):
            raise ValueError("times must be strictly increasing (bracket search assumes it)")

        dphi = 2.0 * math.pi / n_theta
        dirs = [heading_to_vec(k * dphi) for k in range(n_theta)]
        h = np.empty((times_a.size, lats.size, lons.size, n_theta), dtype=np.float64)
        for it, t in enumerate(times_a):
            for i, la in enumerate(lats):
                for j, lo in enumerate(lons):
                    for k, p in enumerate(dirs):
                        h[it, i, j, k] = metric.support(float(la), float(lo), float(t), p)
        return SupportTable(lats, lons, times_a, n_theta, h)

    # ---------------------------------------------------------------- lookup
    def _frame(self, i: int, j: int, t: float) -> np.ndarray:
        """The n_theta support values at cell (i,j), linearly interpolated in forecast time.

        Clamped at both ends rather than extrapolated: past `horizon` the forecast is not
        valid and 06-numerics (f) says persist the last frame, not invent a new one. A
        convex combination of support functions is the support function of the corresponding
        combination of the sets, so the interpolant is always a legitimate h.
        """
        ts = self.times
        if t <= ts[0]:
            return self.h[0, i, j]
        if t >= ts[-1]:
            return self.h[-1, i, j]
        k = int(np.searchsorted(ts, t, side="right")) - 1
        k = min(max(k, 0), ts.size - 2)
        span = ts[k + 1] - ts[k]
        w = 0.0 if span <= 0.0 else (t - ts[k]) / span
        return (1.0 - w) * self.h[k, i, j] + w * self.h[k + 1, i, j]

    def support(self, i: int, j: int, t: float, p: Vec2) -> float:
        """h(p) at cell (i,j), time t. O(1): direct index, no search.

        Positive 1-homogeneity gives h(p) = |p| h(p_hat), so only the direction is looked
        up. Between stored directions h is linearly interpolated in the angle; the error is
        O(dphi^2) and unsigned, which is why the sigma recovery below reads the stored
        values directly instead of going through this.
        """
        px, py = p
        pn = math.hypot(px, py)
        if pn <= 0.0:
            return 0.0
        hv = self._frame(i, j, t)
        a = vec_to_heading(px, py) / self._dphi
        k0 = math.floor(a)
        w = a - k0
        k0 = int(k0) % self.n_theta
        k1 = (k0 + 1) % self.n_theta
        return pn * ((1.0 - w) * hv[k0] + w * hv[k1])

    def sigma_max(self, i: int, j: int, t: float, u: Vec2) -> float:
        """Recover sigma(u) from the tabulated h by duality. O(log n_theta). Prop 2.7.

        sigma(u) = 1/F(u) = min over p != 0 with <u,p> > 0 of h(p)/<u,p>. Restricted to the
        stored directions this is the radial function of the circumscribed polygon, so the
        answer is an over-estimate bounded by sec(pi/n_theta) - 1 in relative terms for a
        convex indicatrix. Returns 0.0 when no stored direction admits a finite ratio, i.e.
        when the direction is infeasible.
        """
        ue, un = u
        n = math.hypot(ue, un)
        if n <= 0.0:
            return 0.0
        ue, un = ue / n, un / n
        hv = self._frame(i, j, t)
        nt = self.n_theta
        k_near = int(round(vec_to_heading(ue, un) / self._dphi)) % nt
        span = nt // 4 + 1                    # every direction with <u,p_k> > 0 is inside

        dirs = self._dirs

        def ratio(off: int) -> float:
            k = (k_near + off) % nt
            d = dirs[k, 0] * ue + dirs[k, 1] * un
            if d <= 1e-15:
                return math.inf
            hk = hv[k]
            if hk <= 0.0:                     # 0 not in V: this half-plane forbids u
                return math.inf if hk < 0.0 else 0.0
            return hk / d

        # Ternary search on the quasi-convex sequence, then a short scan over the residual
        # bracket (integer ternary search cannot resolve the last few indices).
        lo, hi = -span, span
        while hi - lo > 4:
            m1 = lo + (hi - lo) // 3
            m2 = hi - (hi - lo) // 3
            if ratio(m1) <= ratio(m2):
                hi = m2
            else:
                lo = m1
        best = math.inf
        for off in range(lo - 1, hi + 2):
            r = ratio(off)
            if r < best:
                best = r
        if not math.isfinite(best) or best <= 0.0:
            return 0.0
        return best

    def sigma_max_bruteforce(self, i: int, j: int, t: float, u: Vec2) -> float:
        """The same minimisation by an O(n_theta) scan. Only for validating the ternary
        search; the sweep must never call it."""
        ue, un = u
        n = math.hypot(ue, un)
        if n <= 0.0:
            return 0.0
        ue, un = ue / n, un / n
        hv = self._frame(i, j, t)
        best = math.inf
        for k in range(self.n_theta):
            d = self._dirs[k, 0] * ue + self._dirs[k, 1] * un
            if d <= 1e-15:
                continue
            if hv[k] <= 0.0:
                return 0.0
            best = min(best, hv[k] / d)
        return 0.0 if not math.isfinite(best) else best

    @property
    def nbytes(self) -> int:
        return int(self.h.nbytes)


# ============================================================ self-test
if __name__ == "__main__":
    from decimal import Decimal, getcontext

    getcontext().prec = 60

    class _UniformField:
        """Constant Env everywhere. Enough for every check below; the spatial and temporal
        structure is `environment.py`'s problem, not the metric's."""

        def __init__(self, env: Env, t0: float = 0.0, horizon: float = 1e9) -> None:
            self._env, self._t0, self._h = env, t0, horizon

        def at(self, lat: float, lon: float, t: float) -> Env:
            return self._env

        @property
        def t0(self) -> float:
            return self._t0

        @property
        def horizon(self) -> float:
            return self._h

    def _brute_gauge(vx, vy, cx, cy, V_s):
        """F by bisection on tau until v/tau lands on the disc boundary. Independent of the
        closed form: it only ever evaluates |v/tau - c| - V_s."""
        def g(tau):
            return math.hypot(vx / tau - cx, vy / tau - cy) - V_s
        lo = 1e-12
        while g(lo) < 0.0:
            lo *= 0.5
            if lo < 1e-300:
                return 0.0
        hi = lo * 2.0
        for _ in range(4000):
            if g(hi) <= 0.0:
                break
            hi *= 2.0
        else:
            return math.inf
        for _ in range(200):
            mid = 0.5 * (lo + hi)
            if mid <= lo or mid >= hi:
                break
            if g(mid) > 0.0:
                lo = mid
            else:
                hi = mid
        return 0.5 * (lo + hi)

    def _exact_gauge(vx, vy, cx, cy, V_s):
        """60-digit reference. 8 digits of cancellation still leaves 52 correct."""
        D = Decimal(vx) * Decimal(vx) + Decimal(vy) * Decimal(vy)
        a = Decimal(vx) * Decimal(cx) + Decimal(vy) * Decimal(cy)
        lam = Decimal(V_s) * Decimal(V_s) - (Decimal(cx) * Decimal(cx) + Decimal(cy) * Decimal(cy))
        return (a * a + lam * D).sqrt() / lam - a / lam

    print("=" * 78)
    print("KAIROS metric.py self-test")
    print("=" * 78)

    # ---------------------------------------------------------------- 1
    print("\n[1] Randers closed form vs brute-force bisection on the disc boundary")
    rng = np.random.default_rng(20260814)
    worst, worst_case = 0.0, None
    n_cases = 0
    for _ in range(4000):
        V_s = float(rng.uniform(1.0, 12.0))
        cm = float(rng.uniform(0.0, 0.97)) * V_s
        ca = float(rng.uniform(-math.pi, math.pi))
        cx, cy = cm * math.sin(ca), cm * math.cos(ca)
        vm = float(rng.uniform(0.01, 100.0))
        va = float(rng.uniform(-math.pi, math.pi))
        vx, vy = vm * math.sin(va), vm * math.cos(va)
        f = randers_gauge(vx, vy, cx, cy, V_s)
        b = _brute_gauge(vx, vy, cx, cy, V_s)
        rel = abs(f - b) / b
        n_cases += 1
        if rel > worst:
            worst, worst_case = rel, (V_s, cm / V_s)
    print(f"    cases                    : {n_cases}")
    print(f"    max relative error       : {worst:.3e}   (target < 1e-12)")
    print(f"    worst at V_s={worst_case[0]:.3f} m/s, |c|/V_s={worst_case[1]:.3f}")
    assert worst < 1e-12, "closed form disagrees with the numerical gauge"

    # ---------------------------------------------------------------- 2
    print("\n[2] The three sanity limits of 02-metric.md 2.2")
    V_s, cm = 7.5, 2.1
    fld0 = _UniformField(Env(cu=0.0, cv=0.0))
    fldc = _UniformField(Env(cu=cm, cv=0.0))       # current due east
    m0 = RandersMetric(V_s, fld0)
    mc = RandersMetric(V_s, fldc)
    v_len = 3.7
    got_a = m0.F(0.0, 0.0, 0.0, 0.0, v_len)
    exp_a = v_len / V_s
    got_b = mc.F(0.0, 0.0, 0.0, 1.0, 0.0)
    exp_b = 1.0 / (V_s + cm)
    got_c = mc.F(0.0, 0.0, 0.0, -1.0, 0.0)
    exp_c = 1.0 / (V_s - cm)
    print(f"    no current   F(|v|={v_len})  = {got_a:.17g}  expect {exp_a:.17g}  "
          f"relerr {abs(got_a-exp_a)/exp_a:.2e}")
    print(f"    with current F(v || c)   = {got_b:.17g}  expect {exp_b:.17g}  "
          f"relerr {abs(got_b-exp_b)/exp_b:.2e}")
    print(f"    against      F(v || -c)  = {got_c:.17g}  expect {exp_c:.17g}  "
          f"relerr {abs(got_c-exp_c)/exp_c:.2e}")
    print(f"    anisotropy               = {mc.anisotropy(0,0,0):.17g}  "
          f"expect {(V_s+cm)/(V_s-cm):.17g}")
    assert abs(got_a - exp_a) <= 4e-16 * exp_a
    assert abs(got_b - exp_b) <= 4e-16 * exp_b
    assert abs(got_c - exp_c) <= 4e-16 * exp_c

    # ---------------------------------------------------------------- 3
    print("\n[3] Stable vs naive branch, following current (<v,c> > 0)")
    print("    Worst case over 400 directions in the following half-plane, against a")
    print("    60-digit Decimal reference. One sample point is not enough: at the extreme")
    print("    ratios individual roundings cancel by luck and flatter the naive form.")
    print("    |c|/V_s     lam/V_s^2      naive relerr   stable relerr   digits lost")
    V_s = 1.0
    for ratio in (0.9, 0.99, 0.999, 1 - 1e-6, 1 - 1e-9, 1 - 1e-12):
        cx, cy = ratio * V_s, 0.0
        e_n_max = Decimal(0)
        e_s_max = Decimal(0)
        for k in range(400):
            # v swept across the half-plane <v,c> > 0, where the naive form cancels.
            ang = (k / 399.0 - 0.5) * (math.pi * 0.98)
            vx, vy = math.cos(ang), math.sin(ang)
            ref = _exact_gauge(vx, vy, cx, cy, V_s)
            e_n = abs(Decimal(_randers_gauge_naive(vx, vy, cx, cy, V_s)) - ref) / ref
            e_s = abs(Decimal(randers_gauge(vx, vy, cx, cy, V_s)) - ref) / ref
            e_n_max = max(e_n_max, e_n)
            e_s_max = max(e_s_max, e_s)
        lost = 0.0 if e_n_max == 0 else max(0.0, math.log10(float(e_n_max) / 1.1e-16))
        print(f"    {ratio:<11.12g} {1-ratio*ratio:<14.6e} {float(e_n_max):<14.3e} "
              f"{float(e_s_max):<15.3e} {lost:4.1f}")
        assert e_s_max < Decimal("1e-14"), "the stable branch lost precision"
    print("    Digits lost by the naive form go as log10(a^2/(lam*|v|^2)), so at the")
    print("    |c|/V_s = 0.9 case specifically it is well under one digit, NOT eight -- the")
    print("    cancellation only becomes severe as lam -> 0. Eight digits go at |c|/V_s")
    print("    ~ 1 - 1e-12. The stable branch holds ~1e-16 across the whole sweep, which is")
    print("    the point: it costs nothing and removes the failure mode entirely. It also")
    print("    never forms lam at all when <v,c> > 0, so it is immune to the SECOND")
    print("    cancellation, the one inside lam = V_s^2 - |c|^2 itself.")

    # ---------------------------------------------------------------- Kropina
    print("\n[K] Kropina degeneration |c| >= V_s: the metric goes one-sided")
    V_s, c_k = 3.0, 4.0                              # Agulhas core vs a slow bulker
    mk = RandersMetric(V_s, _UniformField(Env(cu=c_k, cv=0.0)))
    half = math.asin(V_s / c_k)                      # reachable wedge half-angle, 48.59 deg
    print(f"    V_s={V_s}, |c|={c_k}, lam={V_s*V_s-c_k*c_k:+.1f}  "
          f"reachable wedge half-angle = {math.degrees(half):.4f} deg about the drift")
    n_ok = n_inf = 0
    for k in range(3600):
        a = k * math.pi / 1800.0
        d = heading_to_vec(a)
        f = mk.F(0.0, 0.0, 0.0, d[0], d[1])
        s = mk.sigma_max(0.0, 0.0, 0.0, d)
        offset = abs(wrap_pi(a - 0.5 * math.pi))     # angle from the drift (due east)
        inside = offset < half - 1e-9
        outside = offset > half + 1e-9
        assert math.isfinite(f) == (f != math.inf)
        assert not (isinstance(f, float) and f != f), "F returned NaN"
        if inside:
            assert math.isfinite(f) and f > 0.0 and s > 0.0, f"wedge interior at {a}"
            n_ok += 1
        elif outside:
            assert f == math.inf and s == 0.0, f"outside the wedge F must be +inf at {a}"
            n_inf += 1
    print(f"    directions inside the wedge  : {n_ok}  all finite F, sigma > 0")
    print(f"    directions outside the wedge : {n_inf}  all F = +inf, sigma = 0.0 (no NaN)")
    print(f"    F straight downstream        : {mk.F(0,0,0,1.0,0.0):.17g}  "
          f"expect 1/(V_s+|c|) = {1.0/(V_s+c_k):.17g}")
    print(f"    F straight upstream          : {mk.F(0,0,0,-1.0,0.0)}  (unmakeable)")
    print(f"    anisotropy                   : {mk.anisotropy(0,0,0)}  (Def 2.9, one-sided)")
    assert mk.anisotropy(0, 0, 0) == math.inf
    assert abs(mk.F(0, 0, 0, 1.0, 0.0) - 1.0 / (V_s + c_k)) < 1e-16

    # ---------------------------------------------------------------- 4
    print("\n[4] FinslerMetric in calm water with bans off reproduces RandersMetric")
    vessel = Vessel()
    env_calm = Env(cu=1.4, cv=-0.8, wu=0.0, wv=0.0, hs=0.0, tp=8.0, mu_w=0.0)
    fld = _UniformField(env_calm)
    fm = FinslerMetric(vessel, fld, n_theta=72, n_throttle=5, use_bans=False,
                       physics=ReferencePhysics())
    # The disc radius is whatever the power balance yields at full throttle in this Env.
    V_full = ReferencePhysics().attainable(vessel, env_calm, 0.0, 1.0)
    cx_eff, cy_eff = effective_drift(vessel, env_calm)
    rm = RandersMetric(V_full, _UniformField(Env(cu=cx_eff, cv=cy_eff)))
    worst = 0.0
    for k in range(720):
        a = k * math.pi / 360.0
        d = heading_to_vec(a)
        s_f = fm.sigma_max(0.0, 0.0, 0.0, d)
        s_r = rm.sigma_max(0.0, 0.0, 0.0, d)
        worst = max(worst, abs(s_f - s_r) / s_r)
    print(f"    V through water at q=1   : {V_full:.9f} m/s  ({V_full/0.5144444:.3f} kt)")
    print(f"    |c_eff|                  : {math.hypot(cx_eff, cy_eff):.6f} m/s")
    print(f"    max relative sigma error : {worst:.3e}  over 720 directions")
    print(f"    fixed-point: max iters   : {fm.fp_iters_max}, fallbacks {fm.fp_fallbacks}")
    assert fm.fp_fallbacks == 0, "calm water should never need the bisection fallback"
    print(f"    Finsler anisotropy       : {fm.anisotropy(0,0,0):.9f}   "
          f"Randers exact {rm.anisotropy(0,0,0):.9f}")
    print("      (the 4e-6 gap is direction sampling, not metric error: 72 bins never land")
    print("       exactly on the up/downstream extremes. Def 2.9's exact value is Randers'.)")
    assert worst < 1e-12, "calm-water Finsler does not reduce to Randers"

    # ---------------------------------------------------------------- Prop 2.7
    print("\n[*] Prop 2.7: sigma recovered from the tabulated support function")
    print(f"    indicatrix D(c, V_s) with V_s = {V_full:.6f}, |c| = "
          f"{math.hypot(cx_eff, cy_eff):.6f}  ->  amplification "
          f"V_s/(V_s-|c|) = {V_full/(V_full-math.hypot(cx_eff, cy_eff)):.4f}")
    print("    n_theta   max rel error   circular sec-1   offset bound   ratio   "
          "ternary==brute")
    grid = (np.array([0.0, 0.05]), np.array([0.0, 0.05]))
    prev = None
    for nt in (36, 72, 144):
        st = SupportTable.build(rm, grid, [0.0, 3600.0], n_theta=nt)
        sec = 1.0 / math.cos(math.pi / nt)
        # Pointwise containment: V ⊆ P ⊆ D(c, V_s*sec(pi/n)), so sigma_hat(u) can never
        # exceed the radial function of the dilated disc in the SAME direction u.
        rm_dilated = RandersMetric(V_full * sec, _UniformField(Env(cu=cx_eff, cv=cy_eff)))
        worst_r, agree, one_sided = 0.0, True, True
        for k in range(1000):
            a = k * 2.0 * math.pi / 1000.0
            d = heading_to_vec(a)
            s_tab = st.sigma_max(0, 0, 1800.0, d)
            s_bf = st.sigma_max_bruteforce(0, 0, 1800.0, d)
            s_ref = rm.sigma_max(0.0, 0.0, 1800.0, d)
            s_cap = rm_dilated.sigma_max(0.0, 0.0, 1800.0, d)
            if abs(s_tab - s_bf) > 1e-13 * max(s_bf, 1.0):
                agree = False
            if s_tab < s_ref * (1.0 - 1e-12) or s_tab > s_cap * (1.0 + 1e-12):
                one_sided = False
            worst_r = max(worst_r, (s_tab - s_ref) / s_ref)
        circ = sec - 1.0
        offset = circ * V_full / (V_full - math.hypot(cx_eff, cy_eff))
        print(f"    {nt:<9d} {worst_r:<15.3e} {circ:<16.3e} {offset:<14.3e} "
              f"{worst_r/offset:<7.3f} {agree}")
        assert one_sided, "recovery left the [sigma, dilated-disc] envelope"
        assert worst_r <= offset * 1.000001, "recovery exceeds the offset-disc bound"
        assert worst_r > 0.0, "recovery must over-estimate, not under-estimate"
        assert agree, "ternary search disagrees with the O(n) scan"
        if prev is not None:
            print(f"              observed order on halving dphi: "
                  f"error ratio {prev/worst_r:.2f}  (2nd order => 4.00)")
        prev = worst_r
    st72 = SupportTable.build(rm, grid, [0.0, 3600.0], n_theta=72)
    print(f"    table for a 2x2 cell block x 2 hours x 72 dirs : {st72.nbytes} bytes")

    # ---------------------------------------------------------------- 5
    print("\n[5] Indicatrix: 1.4 m/s current bearing 090, Hs = 5 m beam sea, bans ON")
    # Waves travelling towards 000 (north) while we mostly want to go east => beam seas.
    env_sea = Env(cu=1.4, cv=0.0, wu=6.0, wv=2.0, hs=5.0, tp=10.5, mu_w=0.0, depth=3000.0)
    fm2 = FinslerMetric(vessel, _UniformField(env_sea), n_theta=72, n_throttle=5,
                        use_bans=True, physics=ReferencePhysics())
    pairs = fm2.indicatrix(0.0, 0.0, 0.0)
    print("      k  heading[deg]   sigma[m/s]    |    k  heading[deg]   sigma[m/s]")
    half = len(pairs) // 2
    for k in range(half):
        a1, s1 = pairs[k]
        a2, s2 = pairs[k + half]
        print(f"    {k:3d}  {math.degrees(a1):9.2f}  {s1:11.6f}    |  {k+half:3d}  "
              f"{math.degrees(a2):9.2f}  {s2:11.6f}")
    sigs = [s for _, s in pairs]
    print(f"    sigma_max = {max(sigs):.6f} m/s at heading "
          f"{math.degrees(pairs[sigs.index(max(sigs))][0]):.1f} deg")
    print(f"    sigma_min = {min(sigs):.6f} m/s at heading "
          f"{math.degrees(pairs[sigs.index(min(sigs))][0]):.1f} deg")
    print(f"    anisotropy Upsilon_loc = {fm2.anisotropy(0,0,0)}")
    print(f"    fixed-point: max iters = {fm2.fp_iters_max}, fallbacks = {fm2.fp_fallbacks}"
          f" (cap {_FP_ITERS}, residual tol {_FP_RES_TOL:.0e}*V)")
    assert fm2.fp_fallbacks == 0, "the heading fixed point did not converge within the cap"

    # The zeroed sectors must be the ban set, not a root find that quietly gave up. Rerun
    # with use_bans=False: if the notch is real it fills in and the anisotropy becomes finite.
    fm2_nb = FinslerMetric(vessel, _UniformField(env_sea), n_theta=72, n_throttle=5,
                           use_bans=False, physics=ReferencePhysics())
    sig_nb = [s for _, s in fm2_nb.indicatrix(0.0, 0.0, 0.0)]
    banned = [k for k, s in enumerate(sigs) if s <= 0.0]
    print(f"    banned sectors (sigma=0): {len(banned)} of 72 headings, "
          f"{math.degrees(banned[0]*2*math.pi/72):.0f}..{math.degrees(banned[-1]*2*math.pi/72):.0f} deg")
    print(f"    same field, bans OFF   : min sigma = {min(sig_nb):.6f} m/s, "
          f"Upsilon_loc = {fm2_nb.anisotropy(0,0,0):.4f}, fallbacks = {fm2_nb.fp_fallbacks}")
    assert min(sig_nb) > 0.0, "the notch is a root-find failure, not a seakeeping ban"
    assert math.isfinite(fm2_nb.anisotropy(0, 0, 0))
    # Confirm the mechanism: S2 parametric roll, the ring-shaped hole of 01-formulation 1.4.
    rp = ReferencePhysics()
    u_notch = heading_to_vec(banned[len(banned) // 2] * 2 * math.pi / 72)
    c_a, c_c = FinslerMetric._decompose(effective_drift(vessel, env_sea), *u_notch)
    flags = []
    for qq in fm2._throttles:
        th = vec_to_heading(*u_notch)
        Vq = rp.attainable(vessel, env_sea, th, qq)
        for _ in range(6):
            th = vec_to_heading(*u_notch) + math.asin(max(-1.0, min(1.0, c_c / Vq)))
            Vq = rp.attainable(vessel, env_sea, th, qq)
        flags.append(rp.violations(vessel, env_sea, th, qq, Vq))
    print(f"    ban bitmask per throttle at the notch centre: {flags}  "
          f"(S2_PARAM_ROLL = {S2_PARAM_ROLL})")
    assert all(f & S2_PARAM_ROLL for f in flags), "notch is not parametric roll"

    east = fm2.legs(0.0, 0.0, 0.0, (1.0, 0.0))
    print(f"\n    Pareto family due east ({len(east)} nondominated of {fm2.n_throttle}):")
    for lg in east:
        print(f"      q={lg.q:.3f}  sog={lg.sog:7.4f} m/s  fuel={lg.fuel_rate*3600:8.2f} kg/h"
              f"  risk={lg.risk_level:.4f}  heading={math.degrees(lg.theta):7.2f} deg")
    h_e = fm2.support(0.0, 0.0, 0.0, (1.0, 0.0))
    print(f"    support h((1,0)) = {h_e:.6f} m/s   vs sigma_max(east) = "
          f"{fm2.sigma_max(0,0,0,(1.0,0.0)):.6f} m/s")

    # ---------------------------------------------------------------- D4
    print("\n[6] D4: the support table describes conv(V), the metric describes V")
    env_d4 = Env(cu=0.9, cv=0.3, wu=5.0, wv=1.0, hs=3.0, tp=9.0, mu_w=1.2)
    for bans_on in (False, True):
        fmd = FinslerMetric(vessel, _UniformField(env_d4), use_bans=bans_on,
                            physics=ReferencePhysics())
        std = SupportTable.build(fmd, (np.array([0.0]), np.array([0.0])), [0.0])
        errs = []
        for k in range(360):
            d = heading_to_vec(k * math.pi / 180.0)
            s_d = fmd.sigma_max(0.0, 0.0, 0.0, d)
            if s_d > 0.0:
                errs.append((std.sigma_max(0, 0, 0.0, d) - s_d) / s_d)
        errs.sort()
        print(f"    bans {'ON ' if bans_on else 'OFF'}: max rel excess {errs[-1]:.3e}, "
              f"median {errs[len(errs)//2]:.3e}, min {errs[0]:.3e}")
        assert errs[0] > -1e-9, "conv(V) can never be smaller than V"
        if not bans_on:
            assert errs[-1] < 2e-3, "no bans: only direction discretisation should remain"
        else:
            assert errs[-1] > 0.05, "with bans the chattering gap of D4 must be visible"
    print("    The gap with bans on is the D4 chattering gap (Thm 2.11), not a table bug:")
    print("    h_V = h_{conv V} identically, so no support tabulation can represent a notch.")

    print("\n" + "=" * 78)
    print("all self-test assertions passed")
    print("=" * 78)
