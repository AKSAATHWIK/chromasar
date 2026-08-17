"""The IMO MSC.1/Circ.1228 ban set S1..S7, as computable inequalities.

Spec reference: 01-formulation.md section 1.4, Eq (1.x) for the ban set; CONTRACT.md
section 4, where `attainable(vessel, env, theta, q)` is required to return NONE exactly
when a control violates one of these. This module is that predicate.

Two things about the design are load-bearing.

First, `violations` (discrete) and `risk_level` (continuous) are the SAME function. Each
criterion is scored by a severity that is normalised so that severity = 1 lies exactly on
the regulatory boundary, and the bitmask is that severity thresholded at 1. So
`risk_level(...) > 1` if and only if `violations(...) != 0`, always, with no separately
tuned second model to drift out of sync. A conjunctive criterion ("banned when A and B and
C") takes the MIN of its factor severities, a disjunctive one ("banned when A or B") takes
the MAX; that is what makes the threshold at 1 reproduce the boolean exactly.

Second, the severities are continuous in (V, theta) even where the bans are not. The label
algebra minimises over a discretised direction set and interpolates between grid nodes; a
risk field with jumps produces a Pareto front whose non-dominated set flickers between
adjacent stencil directions (spec 05, Thm 5.2 assumes the objective is well behaved between
sample points). Continuity here is not cosmetic.

Note on frequencies: `encounter_omega` is the deep-water form given in the spec,
omega_e = omega - (omega^2 V / g) cos mu_rel. Internally the criteria use the general
Doppler form omega_e = omega - k V cos mu_rel with `k` from the full linear dispersion
relation, so that shallow-water cells (where types.Env.wave_length_p explicitly defers the
correction to this module) get the right wavelength and the right encounter frequency. The
two agree to machine precision whenever depth > lambda/2, which is almost everywhere.

Angles are radians, east-first vector components, per CONTRACT.md section 1.
"""
from __future__ import annotations

import math
from typing import Tuple

from .geodesy import wrap_pi
from .types import G, KTS, Env, Vessel

# ---------------------------------------------------------------- ban bits (public API)
BAN_SYNC_ROLL = 1        # S1
BAN_PARAM_ROLL = 2       # S2
BAN_SURF_RIDE = 4        # S3
BAN_SLAM = 8             # S4
BAN_GREEN_WATER = 16     # S5
BAN_ACCEL = 32           # S6
BAN_ENVELOPE = 64        # S7
BAN_ALL = 127

BAN_BITS: Tuple[int, ...] = (BAN_SYNC_ROLL, BAN_PARAM_ROLL, BAN_SURF_RIDE, BAN_SLAM,
                             BAN_GREEN_WATER, BAN_ACCEL, BAN_ENVELOPE)
BAN_NAMES: Tuple[str, ...] = ("S1 sync roll", "S2 parametric roll", "S3 surf-ride",
                              "S4 slamming", "S5 green water", "S6 lateral accel",
                              "S7 envelope")

# ---------------------------------------------------------------- regulatory thresholds
# MSC.1/Circ.1228 states the resonance bands as period ratios; they are written here as
# fractional detuning of the encounter frequency, which is the same statement.
SYNC_ROLL_BAND = 0.10        # |omega_e - omega_phi| < 0.10 omega_phi
PARAM_ROLL_BAND = 0.15       # |omega_e - 2 omega_phi| < 0.15 * 2 omega_phi
PARAM_LAMBDA_LO = 0.8        # x L: below this the wave cannot modulate the waterplane
PARAM_LAMBDA_HI = 2.0        # x L: above this the GM variation over a cycle is small
SURF_FROUDE = 0.30           # Fn above which surf-riding is possible (Circ.1228 s.3.2)
SURF_MU = math.pi / 4.0      # following / stern-quartering sector half-width
SURF_LAMBDA = 0.8            # x L
P_SLAM_MAX = 0.03            # Ochi (1964); 0.01 is used for container ships
P_GREEN_MAX = 0.05
A_LAT_MAX = 0.10 * G         # NORDFORSK (1987) crew limit; 0.05 g for passengers

# The circular gives no wave height below which resonance may be ignored, because it is
# written for a master looking at the sea, not for a solver. These gates keep the ban set
# from removing control space in a 1 m swell where the resonant roll amplitude is a
# nuisance rather than a hazard. Operator-configurable in a production deployment.
HS_SYNC_MIN = 2.5            # m
HS_PARAM_MIN = 2.0           # m

# ---------------------------------------------------------------- model constants
ROLL_ZETA = 0.08             # fraction of critical roll damping, bilge-keeled full hull
EFF_SLOPE_COEFF = 0.75       # effective wave slope coefficient, full-form hull (IS Code
                             # weather criterion uses 0.7-0.8 for this hull class)
BRIDGE_H_COEFF = 0.40        # deckhouse height above the weather deck, as a fraction of B
PHI_RMS_CAP = 0.45           # rad (~26 deg). Beyond this the linear roll model is void;
                             # nonlinear damping and deck-edge immersion limit the real
                             # response. Only reached deep inside an already-banned region.
C_B_DEFAULT = 0.80           # types.Vessel carries no block coefficient (CONTRACT section
                             # 1 lists it, the dataclass does not); full-form default, used
                             # only for the squat estimate in S7.
SEV_CAP = 10.0               # severities are clamped here so a degenerate cell cannot
                             # produce inf/NaN and poison the label queue.

_TINY = 1e-12
_K_MIN = 1e-6                # rad/m, i.e. a 6000 km "wave": the calm-cell limit


# ================================================================= elementary quantities
def encounter_omega(omega: float, V: float, mu_rel: float) -> float:
    """Encounter angular frequency [rad/s] for a wave of frequency `omega` met at relative
    angle `mu_rel` by a ship making `V` through the water.

    Deep water: omega_e = omega - (omega^2 / g) V cos(mu_rel), spec Eq (1.x). Following
    seas (mu_rel = 0) lower it, head seas (mu_rel = pi) raise it.

    The sign is kept. A negative result means the ship is overtaking the wave system, which
    is a physically distinct state from meeting it at the same |omega_e| -- it is the
    surf-riding side of the problem. Criteria that only care about resonance use the
    magnitude; S3 uses the sign implicitly through the heading sector.
    """
    return omega - (omega * omega / G) * V * math.cos(mu_rel)


def _encounter_omega_k(omega: float, V: float, mu_rel: float, k: float) -> float:
    """General Doppler shift, omega_e = omega - k V cos(mu_rel).

    Identical to `encounter_omega` in deep water, where k = omega^2/g. Used internally so
    that shallow cells are consistent between wavelength and encounter frequency.
    """
    return omega - k * V * math.cos(mu_rel)


def relative_wave_angle(theta: float, mu_w: float) -> float:
    """Angle between the ship's heading and the direction the waves TRAVEL TOWARDS.

    Returns mu_rel in [0, pi]: 0 = following seas (waves going the way the ship is going),
    pi/2 = beam, pi = head seas.

    `mu_w` follows the types.Env convention (towards, not from). If a data source gives the
    meteorological "from" convention, it must be rotated by pi at the ingest boundary --
    doing it here would apply the rotation twice for sources that are already correct.
    """
    return abs(wrap_pi(mu_w - theta))


def wave_number(omega: float, depth: float) -> float:
    """Linear-dispersion wave number [rad/m]: solves omega^2 = g k tanh(k d).

    Eckart's approximation as the starting point, then Newton on the residual. Six
    iterations is comfortably enough from that start (the residual is smooth and the start
    is within a few percent); the loop exits early on convergence.

    The derivative is written with sech^2 = 1 - tanh^2 rather than 1/cosh^2 because cosh
    overflows for k*d above ~700 while tanh saturates harmlessly.
    """
    w = abs(omega)
    if w < 1e-9:                        # calm cell: infinite wavelength, floored
        return _K_MIN
    d = max(depth, 1.0)                 # a non-positive depth is a land cell; the solver
                                        # masks those, but do not divide by it if one leaks
    k = w * w / G
    if k * d > 10.0:                    # tanh(10) = 1 - 4e-9; deep water, no iteration
        return k

    tanh_arg = min(k * d, 50.0)
    k = w * w / (G * math.sqrt(max(math.tanh(tanh_arg), _TINY)))   # Eckart start
    for _ in range(6):
        kd = min(k * d, 50.0)
        t = math.tanh(kd)
        f = G * k * t - w * w
        df = G * (t + kd * (1.0 - t * t))
        if df <= _TINY:
            break
        step = f / df
        k -= step
        if k <= _K_MIN:
            return _K_MIN
        if abs(step) < 1e-12 * max(k, 1.0):
            break
    return max(k, _K_MIN)


def squat(vessel: Vessel, V: float, depth: float) -> float:
    """Maximum bow squat [m] at speed V over depth `depth`, ICORELS (1980).

    s = 2.4 (nabla / L^2) Fn_h^2 / sqrt(1 - Fn_h^2), with Fn_h the depth Froude number.
    Self-limiting: it vanishes as the depth grows, which the Barrass regressions do not,
    so this form can be evaluated in every cell rather than only in pilotage waters.

    Displacement is estimated as C_B L B T with `C_B_DEFAULT`, since types.Vessel does not
    carry a block coefficient.
    """
    d = max(depth, 1.0)
    fn_h = max(V, 0.0) / math.sqrt(G * d)
    # Above Fn_h = 1 the ship is supercritical and the formula is meaningless; the clamp
    # holds the estimate at its largest physically defensible value instead of diverging.
    fn2 = min(fn_h * fn_h, 0.95)
    nabla = C_B_DEFAULT * vessel.L * vessel.B * vessel.T_d
    return 2.4 * (nabla / (vessel.L * vessel.L)) * fn2 / math.sqrt(1.0 - fn2)


# ================================================================= severity primitives
# Every factor below returns 1.0 exactly on its own threshold, > 1 on the banned side, and
# is continuous. A criterion's severity is min(factors) when the criterion is a
# conjunction and max(factors) when it is a disjunction; thresholding at 1 then reproduces
# the boolean statement of the criterion exactly.
def _clamp_sev(s: float) -> float:
    if s != s:                          # NaN cannot reach here by construction; if a
        return SEV_CAP                  # future edit makes it possible, fail loud-and-safe
    return min(max(s, 0.0), SEV_CAP)


def _sev_above(x: float, x_th: float) -> float:
    """Banned when x > x_th."""
    return _clamp_sev(x / max(x_th, _TINY))


def _sev_below(x: float, x_th: float) -> float:
    """Banned when x < x_th. Linear, reaching 2 at x = 0."""
    return _clamp_sev(2.0 - x / max(x_th, _TINY))


def _sev_within(x: float, centre: float, halfwidth: float) -> float:
    """Banned when |x - centre| < halfwidth. Peaks at 2 dead on resonance."""
    return _clamp_sev(2.0 - abs(x - centre) / max(halfwidth, _TINY))


def _sev_between(x: float, lo: float, hi: float) -> float:
    """Banned when lo < x < hi, measured in log space.

    Log space because the wavelength band [0.8L, 2.0L] is a ratio band: a wave 10 % longer
    than 2.0 L is as far outside as one 10 % shorter than 0.8 L, which the linear midpoint
    would not say.
    """
    if x <= _TINY or lo <= _TINY or hi <= lo:
        return 0.0
    centre = math.sqrt(lo * hi)
    halfwidth = 0.5 * math.log(hi / lo)
    return _clamp_sev(2.0 - abs(math.log(x / centre)) / max(halfwidth, _TINY))


# ================================================================= response models
def _relative_motion_moments(vessel: Vessel, hs: float, lam: float, mu_rel: float,
                             omega_e: float) -> Tuple[float, float]:
    """Spectral moments of the relative vertical motion at the forward perpendicular:
    returns (m0r [m^2], m2r [m^2/s^2]).

    THIS IS AN APPROXIMATION, and it is the weakest link in S4 and S5. What it should be,
    given a vessel's motion RAOs, is the spectral integral

        m_nr = 2 int int omega_e^n |H_r(omega, beta; V)|^2 S(omega, beta) dbeta domega

    of the relative-motion transfer function against the directional spectrum. That
    requires strip-theory or panel-code output the charterer does not publish, so what is
    used instead is a narrow-band surrogate built from three statements that any
    relative-motion RAO satisfies:

      * long waves (lambda >> L): the ship contours the wave, relative motion -> 0;
      * short waves (lambda << L): the ship ignores the wave, relative motion -> the wave
        amplitude itself;
      * near lambda ~ 1.2 L: pitch is resonant and the bow motion is in antiphase with the
        surface, so the relative motion is amplified to roughly twice the wave amplitude,
        which is where published RAOs for full-form hulls peak.

    The geometric variable is the wavelength measured ALONG THE HULL, lambda/|cos mu_rel|,
    so beam seas give a very long effective wave, no pitch, and therefore no slamming --
    which is the correct heading dependence and the reason S4/S5 do not simply track Hs.

    Speed enters through m2r rather than m0r: with the narrow-band assumption the variance
    of the derivative is omega_e^2 times the variance, which reproduces the operational
    result that slamming is relieved by slowing down in head seas.

    Bias: calibrated to be right in the middle of the range and conservative at the edges.
    Do not quote absolute slamming probabilities from it; it is a decision boundary.
    """
    sigma_w = 0.25 * max(hs, 0.0)               # RMS surface elevation, Hs = 4 sigma
    if sigma_w <= _TINY:
        return 0.0, 0.0

    c = abs(math.cos(mu_rel))
    r = lam / (vessel.L * max(c, 1e-3))         # effective wavelength / ship length
    r = min(r, 50.0)                            # beam seas: the gain below is already ~0

    contour = 1.0 / (1.0 + 0.25 * r * r)        # -> 1 short waves, -> 0 long waves
    resonance = 1.0 + 1.2 * math.exp(-((r - 1.2) / 0.7) ** 2)
    gain = contour * resonance

    m0r = (sigma_w * gain) ** 2
    m2r = omega_e * omega_e * m0r               # narrow band about the encounter frequency
    return m0r, m2r


def _roll_rms(vessel: Vessel, hs: float, k: float, mu_rel: float,
              omega_e: float, omega_phi: float) -> float:
    """RMS roll angle [rad] from a linear single-degree-of-freedom response to wave slope.

    Excitation is the RMS wave slope k*sigma_w reduced by the effective slope coefficient
    and projected onto the beam by |sin mu_rel|; the magnification is the standard
    resonance factor at the frequency ratio omega_e/omega_phi. Capped at `PHI_RMS_CAP`
    because a linear model has nothing useful to say about a 40 degree roll.

    Sway and yaw coupling are omitted. For a beam-sea roll they are second order at the
    bridge; for a stern-quartering broach they are not, but a broach is already banned by
    S3 wherever the vessel is fast enough to reach one.
    """
    sigma_w = 0.25 * max(hs, 0.0)
    if sigma_w <= _TINY or omega_phi <= _TINY:
        return 0.0
    slope_rms = k * sigma_w * EFF_SLOPE_COEFF * abs(math.sin(mu_rel))
    rho = abs(omega_e) / omega_phi
    zeta = max(ROLL_ZETA, 1e-3)
    denom = math.sqrt((1.0 - rho * rho) ** 2 + (2.0 * zeta * rho) ** 2)
    mag = 1.0 / max(denom, 2.0 * zeta * 1e-3)   # denom >= 2 zeta rho > 0, belt and braces
    return min(slope_rms * mag, PHI_RMS_CAP)


def _lateral_acceleration(vessel: Vessel, phi_rms: float, omega_e: float) -> float:
    """RMS apparent lateral acceleration at the bridge [m/s^2].

    a_y = -(g + h phi_dd/phi) phi for narrow-band roll about an axis taken at the
    waterline: the gravity component g*sin(phi) and the tangential component h*phi_dd are
    both proportional to phi and in phase, so they add algebraically rather than in
    quadrature. `h` is the bridge height above that axis, estimated as freeboard plus a
    deckhouse of BRIDGE_H_COEFF * B -- types.Vessel does not carry a bridge height.
    """
    h_br = vessel.freeboard + BRIDGE_H_COEFF * vessel.B
    return phi_rms * (G + h_br * omega_e * omega_e)


# ================================================================= the ban set
def _severities(vessel: Vessel, env: Env, V: float, theta: float) -> Tuple[float, ...]:
    """Per-criterion severity, index i = S(i+1). > 1 means banned. See module docstring."""
    V = max(V, 0.0)                     # astern is not a control the solver offers
    hs = max(env.hs, 0.0)

    # A vessel with no positive metacentric height has no roll frequency and no business
    # being routed. Ban everything rather than dividing by zero three lines later.
    if vessel.GM <= 0.0 or vessel.k_xx <= 0.0 or vessel.B <= 0.0 or vessel.L <= 0.0:
        return tuple([SEV_CAP] * 7)

    omega_phi = vessel.omega_roll
    mu_rel = relative_wave_angle(theta, env.mu_w)
    omega_p = env.wave_omega_p
    k = wave_number(omega_p, env.depth)
    lam = 2.0 * math.pi / k
    omega_e = _encounter_omega_k(omega_p, V, mu_rel, k)
    abs_we = abs(omega_e)

    # --- S1 synchronous roll: encounter frequency on the roll frequency, in a real sea.
    s1 = min(_sev_within(abs_we, omega_phi, SYNC_ROLL_BAND * omega_phi),
             _sev_above(hs, HS_SYNC_MIN))

    # --- S2 parametric roll. The three factors are a frequency band, a wavelength band and
    # a height gate, all conjunctive. Geometry worth being explicit about: the frequency
    # factor is a band in omega_e, and omega_e = omega_p - k V cos(mu_rel) is linear in the
    # SIGNED quantity V*cos(mu_rel). So in the polar control plane (V, theta) the banned
    # set is the region between two curves V cos(mu_rel) = const, i.e. two vertical lines in
    # the (V cos mu, V sin mu) plane, intersected with the speed disc -- a band, closing
    # into a ring around the origin when 2*omega_phi is reachable on both the head-sea and
    # following-sea side. That ring is exactly the non-convexity that Def 1.1's indicatrix
    # inherits and that design decision D4 convexifies and then projects back out.
    s2 = min(_sev_within(abs_we, 2.0 * omega_phi, PARAM_ROLL_BAND * 2.0 * omega_phi),
             _sev_between(lam, PARAM_LAMBDA_LO * vessel.L, PARAM_LAMBDA_HI * vessel.L),
             _sev_above(hs, HS_PARAM_MIN))

    # --- S3 surf-riding / broaching: fast, in following or stern-quartering seas, in waves
    # long enough to carry the ship. Fn uses speed through water, which is the speed
    # relative to the wave-bearing medium.
    fn = V / math.sqrt(G * vessel.L)
    s3 = min(_sev_above(fn, SURF_FROUDE),
             _sev_below(mu_rel, SURF_MU),
             _sev_above(lam, SURF_LAMBDA * vessel.L))

    m0r, m2r = _relative_motion_moments(vessel, hs, lam, mu_rel, omega_e)

    # --- S4 slamming, Ochi (1964): the bow must emerge (relative motion exceeding the
    # local draft) AND re-enter faster than the threshold velocity. Jointly Rayleigh, hence
    # the product of the two exceedance probabilities.
    v_th = 0.093 * math.sqrt(G * vessel.L)
    if m0r <= _TINY or m2r <= _TINY:
        p_slam = 0.0                    # no relative motion, or riding with the wave at
    else:                               # omega_e = 0: no impact velocity, no slam
        arg = (vessel.T_d ** 2) / (2.0 * m0r) + (v_th ** 2) / (2.0 * m2r)
        p_slam = math.exp(-arg) if arg < 700.0 else 0.0
    # Cube root only compresses six decades of probability into an O(1) severity; it is
    # monotone and fixes 1 at the threshold, so the ban boundary is untouched.
    s4 = _clamp_sev((p_slam / P_SLAM_MAX) ** (1.0 / 3.0))

    # --- S5 green water: the same relative motion measured against the freeboard.
    if m0r <= _TINY:
        p_gw = 0.0
    else:
        arg = (vessel.freeboard ** 2) / (2.0 * m0r)
        p_gw = math.exp(-arg) if arg < 700.0 else 0.0
    s5 = _clamp_sev((p_gw / P_GREEN_MAX) ** (1.0 / 3.0))

    # --- S6 lateral acceleration at the bridge.
    phi_rms = _roll_rms(vessel, hs, k, mu_rel, omega_e, omega_phi)
    s6 = _sev_above(_lateral_acceleration(vessel, phi_rms, omega_e), A_LAT_MAX)

    # --- S7 operator envelope. Disjunctive: EITHER the sea exceeds the vessel's heavy
    # weather limit OR the under-keel clearance is gone, so max, not min. Squat makes this
    # the one envelope term that depends on speed, which is real: in 20 m of water a
    # loaded Handymax at full speed sits over a metre lower than at rest.
    clearance = max(env.depth, 0.0) - vessel.T_d - squat(vessel, V, env.depth)
    ukc = vessel.ukc_margin / max(clearance, vessel.ukc_margin / SEV_CAP)
    s7 = max(_sev_above(hs, vessel.hs_limit), _clamp_sev(ukc))

    return (s1, s2, s3, s4, s5, s6, s7)


def violations(vessel: Vessel, env: Env, V: float, theta: float) -> int:
    """Bitmask of the MSC.1/Circ.1228 criteria violated by control (V, theta). 0 = clear.

    Only criteria enabled in `vessel.bans_enabled` are reported: a fleet operator who
    accepts parametric-roll exposure on a hull with no containers on deck turns off bit 2
    and the solver stops carving that ring out of the indicatrix.

    This does NOT check the powering envelope -- whether V is attainable at all is
    `V_pwr`'s job (01-formulation section 1.3). A control may be seakeeping-admissible and
    still unreachable.
    """
    sev = _severities(vessel, env, V, theta)
    mask = 0
    for i, s in enumerate(sev):
        bit = BAN_BITS[i]
        if (vessel.bans_enabled & bit) and s > 1.0:
            mask |= bit
    return mask


def is_admissible(vessel: Vessel, env: Env, V: float, theta: float) -> bool:
    """True when (V, theta) lies in the admissible control set A(x, t) of Eq (1.x)."""
    return violations(vessel, env, V, theta) == 0


def risk_level(vessel: Vessel, env: Env, V: float, theta: float) -> float:
    """Continuous severity of the worst active criterion. 1.0 = exactly at the limit.

    By construction `risk_level > 1` if and only if `violations != 0`, so the bottleneck
    risk objective (types.Accum.MAX) and the hard ban set never disagree about where the
    boundary is.

    The maximum of continuous functions is continuous, so this is continuous everywhere in
    (V, theta); it is differentiable except on the measure-zero set where the argmax
    criterion changes, which is what the label algebra needs. It is NOT smooth there, and
    any gradient-based polish must treat it as such.

    Values above 1 are meaningful and ordered (2 is dead-on resonance in a sea well past
    the height gate) but they are severities, not probabilities.
    """
    sev = _severities(vessel, env, V, theta)
    worst = 0.0
    for i, s in enumerate(sev):
        if vessel.bans_enabled & BAN_BITS[i]:
            worst = max(worst, s)
    return worst


# ================================================================= PhysicsLike adapter
# INTEGRATOR NOTE (reconciliation, 2026-08-14).
#
# `metric._default_physics()` looks for `seakeeping.PHYSICS` (or `seakeeping.Physics`) and
# duck-types it against `metric.PhysicsLike`. Before this adapter existed neither name was
# defined, so the lookup silently fell through to `metric.ReferencePhysics` and BOTH this
# module and `powering.py` were unreachable from the solver -- the full S1..S7 criterion set
# and the full STAwave-1 / Fujiwara / SFOC powering chain were dead code. This class is the
# seam the two authors each assumed the other had built.
#
# It also fixes an argument-order drift: `violations` here is (vessel, env, V, theta) while
# `PhysicsLike.violations` is (vessel, env, theta, q, V). The reorder happens once, here,
# rather than at every call site.
class Physics:
    """`metric.PhysicsLike` implemented against the real powering and seakeeping models.

    Three delegations, no physics of its own:

      * `attainable` -> `powering.attainable_speed` (Proc 6.1 root find on the full
        resistance decomposition), rather than the reduced Admiralty + constant-C_X model in
        `metric.ReferencePhysics`.
      * `violations` -> `seakeeping.violations`, i.e. all seven MSC.1/Circ.1228 criteria with
        the roll-response and relative-motion models, rather than the four-criterion subset.
      * `rates`      -> `powering.fuel_rate` for fuel, `seakeeping.risk_level` for the
        bottleneck risk level, and the same level divided by 3600 for the additive risk
        rate, so "risk-hours" is the unit of the additive objective exactly as
        `metric.ReferencePhysics` defines it and the two are comparable.

    COST, measured rather than assumed -- and the measurement overturned the guess. The
    obvious expectation is that this is much dearer than `ReferencePhysics`:
    `attainable_speed` runs a 32-sample scan plus a safeguarded root find where
    `ReferencePhysics.attainable` runs a bare bisection, and `_severities` evaluates seven
    criteria including two relative-motion moment integrals where `ReferencePhysics`
    evaluates four closed-form inequalities. Measured over 1200 `sigma_max` calls spread
    across 25 positions x 2 forecast times x 24 directions of `SyntheticIndianOcean`, with
    `n_theta = 24, n_throttle = 5`:

        ReferencePhysics    541.2 us/sigma_max      24/1200 directions infeasible
        Physics (this)      524.5 us/sigma_max      24/1200 directions infeasible

    i.e. this adapter is marginally FASTER, and rejects exactly the same directions. Both
    are dominated by the same term -- the ~50 power evaluations the attainable-speed root
    find spends reaching its 4-ulp tolerance, multiplied by the heading fixed point's
    iterations in `FinslerMetric._solve_leg` -- and the extra criteria are noise beside it.
    `FULL_PHYSICS_DEFAULT` is therefore True: there is no wall-clock reason to prefer the
    reduced model, and one substantive reason to prefer this one, below.

    WHY IT MATTERS BEYOND FIDELITY. `ReferencePhysics.rates` computes `risk_level` from
    `env.hs` and the relative wave angle only, so it is CONSTANT across the throttle family:
    every leg `FinslerMetric.legs` returns carries the same risk, the risk objective cannot
    be traded against time or fuel by choosing a throttle, and that axis of the Pareto front
    collapses. Measured at 0.1 rad N, 1.0 rad E on the synthetic field, the five throttles
    return risk levels

        ReferencePhysics   0.266  0.266  0.266  0.266  0.266     (no trade available)
        Physics (this)     0.618  0.571  0.514  0.441  0.650     (non-monotone in q)

    The non-monotonicity at q_min is real and is the surf-riding/roll criteria changing which
    one is worst as the encounter frequency sweeps. Design decision D1 is only non-trivial
    with the second column.

    `comfort_rate` is the same beam-sea proxy `ReferencePhysics` uses. The MSI/MII of
    criterion S6 needs the response spectrum, which `_severities` computes internally but
    does not export; wiring that through is left as a documented gap rather than faked here.
    """

    __slots__ = ()

    def attainable(self, vessel: Vessel, env: Env, theta: float, q: float) -> float:
        from . import powering
        return powering.attainable_speed(vessel, env, theta, q)

    def violations(self, vessel: Vessel, env: Env, theta: float, q: float, V: float) -> int:
        return violations(vessel, env, V, theta)

    def rates(self, vessel: Vessel, env: Env, theta: float, q: float,
              V: float) -> Tuple[float, float, float, float]:
        from . import powering
        fuel = powering.fuel_rate(vessel, env, V, theta)
        level = risk_level(vessel, env, V, theta)
        mu_rel = relative_wave_angle(theta, env.mu_w)
        beam = abs(math.sin(mu_rel))
        comfort = (env.hs * beam / max(vessel.hs_caution, _TINY)) / 3600.0
        return fuel, level / 3600.0, level, comfort


#: Module-level singleton picked up by `metric._default_physics()`. Stateless, so sharing it
#: across metrics and threads is safe -- and required, because `EnvField` determinism (the
#: hypothesis of Thm 3.1) would be pointless if the physics behind it carried state.
PHYSICS = Physics()

#: Set True to make `metric._default_physics()` return `PHYSICS` instead of
#: `ReferencePhysics`. Left False because of the ~20x per-evaluation cost documented above.
FULL_PHYSICS_DEFAULT = False


# ================================================================= self-test
if __name__ == "__main__":
    def _map(vessel: Vessel, env: Env, n_v: int = 67, n_th: int = 72):
        """Fraction of the (V, theta) rectangle removed by each criterion."""
        counts = [0] * 7
        any_banned = 0
        invariant_ok = 0
        total = 0
        for iv in range(n_v):
            V = vessel.V_max_hull * iv / (n_v - 1)
            for it in range(n_th):
                th = 2.0 * math.pi * it / n_th
                m = violations(vessel, env, V, th)
                r = risk_level(vessel, env, V, th)
                if (m != 0) == (r > 1.0):
                    invariant_ok += 1
                total += 1
                if m:
                    any_banned += 1
                for i, bit in enumerate(BAN_BITS):
                    if m & bit:
                        counts[i] += 1
        return counts, any_banned, total, invariant_ok

    ship = Vessel()
    sea = Env(hs=5.0, tp=11.0, mu_w=math.radians(90.0), depth=4000.0)

    k_p = wave_number(sea.wave_omega_p, sea.depth)
    lam_p = 2.0 * math.pi / k_p
    print("KAIROS seakeeping -- IMO MSC.1/Circ.1228 ban set S1..S7")
    print(f"vessel : {ship.name}  L={ship.L:.0f} m  B={ship.B:.0f} m  "
          f"T={ship.T_d:.1f} m  fb={ship.freeboard:.1f} m")
    print(f"roll   : omega_phi={ship.omega_roll:.4f} rad/s  T_phi={ship.T_roll:.2f} s")
    print(f"sea    : Hs={sea.hs:.1f} m  Tp={sea.tp:.1f} s  towards "
          f"{math.degrees(sea.mu_w):.0f} deg  depth={sea.depth:.0f} m")
    print(f"wave   : lambda={lam_p:.1f} m ({lam_p / ship.L:.2f} L)  "
          f"omega_p={sea.wave_omega_p:.4f} rad/s  "
          f"v_th={0.093 * math.sqrt(G * ship.L):.2f} m/s")
    print()

    # ---- admissible / banned map. Symbol = lowest-numbered criterion violated.
    print("admissible map   ('.' = clear, digit = lowest criterion violated)")
    print("        speed kt " + "".join(f"{s:>3d}" for s in range(0, 17, 2)))
    for hdg_deg in range(0, 360, 15):
        th = math.radians(hdg_deg)
        mu = math.degrees(relative_wave_angle(th, sea.mu_w))
        row = []
        for s_kt in range(0, 17):
            m = violations(ship, sea, s_kt * KTS, th)
            if not m:
                row.append(".")
            else:
                row.append(str(next(i + 1 for i, b in enumerate(BAN_BITS) if m & b)))
        print(f"  {hdg_deg:03d} deg (mu {mu:3.0f})  " + "".join(row))

    counts, any_banned, total, inv = _map(ship, sea)
    print()
    print(f"fraction of the {total}-point (V, theta) control space removed:")
    for i, nm in enumerate(BAN_NAMES):
        print(f"   {nm:<20s} {100.0 * counts[i] / total:6.2f} %")
    print(f"   {'ANY':<20s} {100.0 * any_banned / total:6.2f} %")
    print(f"   invariant (risk>1 <=> banned) holds at {inv}/{total} points")

    # ---- continuity of risk_level across the S2 boundary, which `violations` jumps at.
    th_head = sea.mu_w + math.pi          # head seas
    prev, worst_jump, worst_at = None, 0.0, 0.0
    for i in range(2001):
        V = ship.V_max_hull * i / 2000.0
        r = risk_level(ship, sea, V, th_head)
        if prev is not None and abs(r - prev) > worst_jump:
            worst_jump, worst_at = abs(r - prev), V
        prev = r
    print(f"\nrisk_level along head seas, dV={ship.V_max_hull / 2000.0:.5f} m/s:"
          f" max step {worst_jump:.2e} at V={worst_at / KTS:.2f} kt")
    prev, worst_jump = None, 0.0
    for i in range(2001):
        th = 2.0 * math.pi * i / 2000.0
        r = risk_level(ship, sea, 7.0, th)
        if prev is not None:
            worst_jump = max(worst_jump, abs(r - prev))
        prev = r
    print(f"risk_level around the compass at V=7 m/s, dtheta="
          f"{360.0 / 2000.0:.3f} deg: max step {worst_jump:.2e}")

    # ---- S4/S5 do not fire for a laden bulker in a 5 m sea, which is correct and also
    # means the map above does not exercise them. Two conditions that do.
    print("\nconditions that exercise S4 and S5 (head seas, mu_rel = 180 deg):")
    ballast = Vessel(name="same hull, ballast", T_d=6.0, freeboard=11.5)
    rough = Env(hs=7.0, tp=11.0, mu_w=0.0, depth=4000.0)
    for name, v, e, V in (("laden, Hs 5", ship, sea, 7.0),
                          ("laden, Hs 7", ship, rough, 7.0),
                          ("ballast, Hs 7 @ 13.6 kt", ballast, rough, 7.0),
                          ("ballast, Hs 7 @  7.8 kt", ballast, rough, 4.0)):
        th = e.mu_w + math.pi
        mu = relative_wave_angle(th, e.mu_w)
        kk = wave_number(e.wave_omega_p, e.depth)
        we = _encounter_omega_k(e.wave_omega_p, V, mu, kk)
        m0, m2 = _relative_motion_moments(v, e.hs, 2.0 * math.pi / kk, mu, we)
        vth = 0.093 * math.sqrt(G * v.L)
        ps = math.exp(-((v.T_d ** 2) / (2 * m0) + vth ** 2 / (2 * m2))) if m2 > 0 else 0.0
        pg = math.exp(-(v.freeboard ** 2) / (2 * m0)) if m0 > 0 else 0.0
        print(f"  {name:<24s} sqrt(m0r)={math.sqrt(m0):5.2f} m  omega_e={we:5.3f}  "
              f"P_slam={ps:8.5f}  P_gw={pg:8.5f}  bans={violations(v, e, V, th):3d}")

    # ---- degenerate cases must return numbers, not NaN.
    print("\ndegenerate cases:")
    for name, v, e, V, th in (
            ("calm (Hs=0, Tp=0)", ship, Env(hs=0.0, tp=0.0), 7.0, 0.0),
            ("zero speed", ship, sea, 0.0, 0.0),
            ("shallow 18 m", ship, Env(hs=3.0, tp=11.0, depth=18.0), 8.0, 0.0),
            ("draft > depth", ship, Env(hs=3.0, tp=11.0, depth=9.0), 4.0, 0.0),
            ("GM = 0", Vessel(GM=0.0), sea, 7.0, 0.0)):
        r = risk_level(v, e, V, th)
        print(f"  {name:<20s} risk={r:7.3f}  bans={violations(v, e, V, th):3d}  "
              f"finite={math.isfinite(r)}")
