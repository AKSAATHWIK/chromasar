"""Resistance, delivered power, and the attainable-speed root find.

Spec reference: 01-formulation.md (c) resistance decomposition and (d) the throttle-to-speed
map; 06-numerics.md Proc 6.1 (bracket-then-safeguarded-secant root find).

This module answers exactly one question, and answers it without knowing anything about
routing: *given a vessel, a patch of weather, a heading and a throttle setting, how fast can
the ship go and how much fuel does that burn?* Everything above it (seakeeping bans, the
indicatrix, the metric) is somebody else's file. Nothing here samples an `EnvField`, holds
state, or knows what a grid is.

The resistance decomposition (Eq 1.7):

    R_total(V) = R_calm(V) + R_AW(H_s, beta) + R_AA(V, W_10, theta)

with delivered (shaft) power

    P_D(V) = R_total(V) * V / eta_D                                          (Eq 1.8)

and the calm-water term *defined* by inversion of `Vessel.calm_power` so that in still air
and flat water `delivered_power` reproduces the vessel's own speed-power curve to machine
precision. That round-trip identity is the reason a user can swap `calm_power` for a spline
through sea-trial data and have every other number in this file follow, which is design
decision D7 (nothing Python-specific, nothing hard-wired) applied to the physics layer.

SIGN CONVENTIONS. Wave and wind resistance are signed. A following sea and a following wind
*reduce* resistance, and `delivered_power` may therefore return a negative number: that means
the environment supplies net thrust and the engine is not required to hold that speed. This
is deliberate. Clamping power at zero inside `delivered_power` would introduce a flat segment
in P_D(V), destroy strict monotonicity, and hand the root find a degenerate bracket for no
physical gain. The clamp belongs in `fuel_rate`, where negative fuel would be nonsense, and
that is where it lives.
"""
from __future__ import annotations

import math
from typing import Callable, Tuple

from .geodesy import angdiff, heading_to_vec, vec_to_heading
from .types import G, RHO_AIR, RHO_SW, Env, Vessel

# --------------------------------------------------------------------------- tolerances
# Proc 6.1. The speed tolerance is two orders below anything a helmsman can hold and four
# below the metric's own modelling error, so refining further only buys arithmetic.
_V_XTOL = 1.0e-4            # [m/s] bracket width at which the root find stops
_P_RTOL = 1.0e-9            # relative power residual accepted as an exact hit
_N_SCAN = 32                # coarse samples used to bracket the FIRST power crossing
_V_EPS = 1.0e-6             # [m/s] left end of the scan; P_D(V) -> 0 as V -> 0
_V_FLOOR = 0.05             # [m/s] below this we report 0.0 rather than pretend
_MAX_ITER = 60              # safety net; the alternation below exits in ~12 for our brackets
_Q_OVERLOAD = 1.15          # hard ceiling on throttle; MCR overload beyond this is fiction
_ETA_FLOOR = 1.0e-3         # guards a vessel record with eta_D <= 0


# Fujiwara-style longitudinal windage coefficient, as a truncated Fourier series in the
# apparent-wind angle psi (0 = dead ahead). Fujiwara et al. (1998) regress the coefficients
# from superstructure geometry -- projected lateral area, bridge height, deckhouse position --
# none of which `Vessel` carries, and demanding them would violate the "no towing-tank
# campaign" rule in types.py. These four numbers are instead a fit to the published laden
# bulk-carrier C_X curve of that family: 1.00 head-on, sign change near 80 deg, -0.70 dead
# astern. A vessel with an unusual profile (car carrier, boxship with a high deck stow)
# should override `windage_coefficient`; the shape, not the magnitude, is what matters most.
_CX_FOURIER: Tuple[float, float, float, float] = (0.05, 0.80, 0.10, 0.05)

# Directionality factor applied to STAwave-1. See `added_resistance_waves`.
_FDIR_MEAN = 0.55
_FDIR_AMPL = 0.45


def _eta(vessel: Vessel) -> float:
    """Quasi-propulsive coefficient, floored. A zero or negative eta_D is a corrupt vessel
    record, not a physical state; we refuse to divide by it rather than raise inside the
    solver's inner loop."""
    return vessel.eta_D if vessel.eta_D > _ETA_FLOOR else _ETA_FLOOR


# ============================================================================ drift & wind
def drift_vector(vessel: Vessel, env: Env) -> Tuple[float, float]:
    """Effective drift c = surface current + leeway, (east, north) [m/s]. Spec §1.

    Leeway is `kappa_L` times the *true* wind vector, per the definition of `kappa_L` in
    types.py. The honest limitation: real leeway is not collinear with the wind -- a hull
    makes leeway largely abeam, and the fraction depends on the relative wind angle and on
    draft. Collinear scaling overstates the along-track component in a head or following
    wind and understates the cross-track component in a beam wind. At kappa_L = 0.025 the
    absolute error is a few centimetres per second, which is below the forecast's own
    current error, so the refinement is not worth the extra vessel parameters.

    Exported rather than kept private because `metric` needs exactly this vector to build
    the indicatrix, and two independent copies of a drift model is how sign errors are born.
    """
    return (env.cu + vessel.kappa_L * env.wu,
            env.cv + vessel.kappa_L * env.wv)


def ground_velocity(vessel: Vessel, env: Env, V: float, theta: float) -> Tuple[float, float]:
    """Over-ground velocity v = V*n(theta) + c, (east, north) [m/s]. Eq 1.2."""
    ne, nn = heading_to_vec(theta)
    de, dn = drift_vector(vessel, env)
    return V * ne + de, V * nn + dn


def apparent_wind(vessel: Vessel, env: Env, V: float, theta: float) -> Tuple[float, float]:
    """Apparent wind (speed [m/s], angle psi [rad] off the bow, 0 = dead ahead, in [0, pi]).

    The relative wind is the vector difference of the true wind and the ship's *ground*
    velocity, not its through-water velocity: air does not know about the current. The
    distinction is worth up to a metre per second in the Agulhas or the Kuroshio.

    `psi` is the direction the apparent wind blows FROM, measured from the bow, which is why
    the heading of `-W_rel` is taken. In still air this returns (|v_ground|, 0) -- the ship
    makes its own head wind -- which is the identity `wind_resistance` relies on to avoid
    double-counting the still-air drag already inside the calm-water curve.
    """
    ge, gn = ground_velocity(vessel, env, V, theta)
    re, rn = env.wu - ge, env.wv - gn          # wind velocity as seen from the deck
    speed = math.hypot(re, rn)
    if speed <= 1e-12:                          # dead calm relative to the ship
        return 0.0, 0.0
    psi = abs(angdiff(vec_to_heading(-re, -rn), theta))
    return speed, psi


def _cx_poly() -> Tuple[float, float, float, float]:
    """Rewrite the C_X Fourier series as a cubic in cos(psi), via Chebyshev.

    cos(2psi) = 2c^2 - 1 and cos(3psi) = 4c^3 - 3c, so

        C_X = (a0 - a2) + (a1 - 3*a3)*c + 2*a2*c^2 + 4*a3*c^3.

    The point is that the hot path never has an angle in hand -- it has a wind vector and a
    heading vector, whose normalised dot product IS cos(psi). Going vector -> atan2 -> psi ->
    three cosines only to end up back at cos(psi) costs four transcendentals per evaluation
    and introduces an angle-wrapping step that can never improve the answer. Derived here
    rather than hand-transcribed so the two forms cannot drift apart when someone retunes
    `_CX_FOURIER`.
    """
    a0, a1, a2, a3 = _CX_FOURIER
    return a0 - a2, a1 - 3.0 * a3, 2.0 * a2, 4.0 * a3


_CX_POLY = _cx_poly()


def _cx_from_cos(c: float) -> float:
    """C_X as a function of cos(psi). The hot-path form; `windage_coefficient` wraps it.

    Evenness in psi is structural here, and correct: the longitudinal wind force does not
    care whether the wind is on the port or starboard bow.
    """
    if c > 1.0:
        c = 1.0
    elif c < -1.0:
        c = -1.0                    # guard rounding in the normalised dot product
    b0, b1, b2, b3 = _CX_POLY
    return b0 + c * (b1 + c * (b2 + c * b3))


def windage_coefficient(psi: float) -> float:
    """Longitudinal wind resistance coefficient C_X at apparent-wind angle `psi` [rad].

    Positive = the wind resists. C_X(0) = 1.00 by construction of the coefficients, which
    makes it the natural reference for the still-air subtraction in `wind_resistance`.
    """
    return _cx_from_cos(math.cos(psi))


_CX0 = windage_coefficient(0.0)     # still-air reference; see `wind_resistance`


# ============================================================================ resistance
def calm_resistance(vessel: Vessel, V: float) -> float:
    """Calm-water total resistance at speed through water V [m/s] -> [N]. Eq 1.6.

    Defined by inverting the vessel's own speed-power curve, R = eta_D * P_calm(V) / V,
    rather than by an independent Holtrop-Mennen build-up. Two reasons, both structural:
    the vessel record publishes power and not resistance, and inverting guarantees that
    `delivered_power` in flat calm returns `vessel.calm_power(V)` exactly, so overriding
    `calm_power` with a measured spline propagates through every function in this module
    with no further edits.

    Returns 0.0 at and below zero speed. The Admiralty default has R ~ V^(n-1) -> 0 there
    for n > 1; a spline that does not vanish at the origin will simply report its own value,
    which is the caller's business and not ours to smooth over.
    """
    if not (V > 0.0) or not math.isfinite(V):
        return 0.0
    p = vessel.calm_power(V)
    if not math.isfinite(p):
        return 0.0
    return _eta(vessel) * p / V


def added_resistance_waves(vessel: Vessel, env: Env, V: float, theta: float) -> float:
    """Added resistance in waves [N], STAwave-1 with a directionality factor. Eq 1.9.

        R_AW = f_dir(beta) * (1/16) * rho_sw * g * H_s^2 * B * sqrt(B / L_bwl)

    VALIDITY ENVELOPE (ITTC 7.5-04-01-01.2 / ISO 15016:2015 Annex F, stated here because the
    formula is used far outside it and the reader deserves to know):

      * Head waves only, nominally within +-45 deg of the bow. The `f_dir` factor below is
        an extension, not part of the standard.
      * Heave and pitch amplitudes must be small, which the standard operationalises as
        H_s <= 2.25 * sqrt(L_pp / 100) -- about 3.1 m for the default 190 m bulker. Above
        that the true added resistance saturates relative to the H_s^2 law, so this formula
        OVERSTATES resistance in the heaviest seas. That bias is conservative for routing
        (it makes storms look worse than they are) and we accept it deliberately.
      * No period dependence. STAwave-1 is blind to T_p, and therefore blind to the
        resonance peak near L_wave ~ L_pp where added resistance genuinely doubles. This is
        the formula's chief weakness. `env.tp` is available and a STAwave-2 or RAO-based
        replacement drops in behind this signature without touching any caller.
      * Deep water. No shallow-water correction is applied even though `env.depth` is
        present; that belongs with the squat model in `seakeeping`.

    `V` is accepted for signature uniformity and because every replacement for this function
    (STAwave-2, RAO integration) needs it. STAwave-1 itself is speed-independent, and that
    happens to be convenient: a constant added resistance contributes a term linear in V to
    the delivered power, which cannot break the monotonicity Lemma 1.4 depends on.

    DIRECTIONALITY. `beta` is the angle between the ship's heading and the direction the
    waves travel TOWARDS, so beta = pi is a head sea and beta = 0 a following sea (the
    convention is nailed down in the `Env.mu_w` docstring; getting it backwards is a
    180-degree error that looks entirely plausible on a chart). The factor

        f_dir(beta) = 0.55 - 0.45 * cos(beta)

    gives 1.00 head, 0.87 bow-quartering, 0.55 beam, 0.23 stern-quartering, 0.10 following,
    which tracks published RAO-integrated added-resistance polars for full-form hulls. It
    does not go to zero in a following sea because the real one does not either.
    """
    return _SpeedPowerCurve(vessel, env, theta).r_aw


def wind_resistance(vessel: Vessel, env: Env, V: float, theta: float) -> float:
    """Added aerodynamic resistance [N], Fujiwara-style. Eq 1.10.

        R_AA = 0.5 * rho_air * A_T * [ C_X(psi) * V_rel^2  -  C_X(0) * |v_ground|^2 ]

    The second term is not decoration. `Vessel.calm_power` is a fit to trial or service data
    taken in some ambient air, so the still-air windage at the ship's own speed is ALREADY
    inside `calm_resistance`. Subtracting it here is the ISO 15016 correction and it makes
    the still-air case cancel exactly: with W_10 = 0 the apparent wind is |v_ground| dead
    ahead, psi = 0, and R_AA is identically zero. Omitting the subtraction would add a
    spurious ~20 kN at service speed to every leg of every route, uniformly, which is the
    worst kind of error because it never looks wrong.

    Consequently R_AA is signed: a following wind returns a negative number. See the module
    docstring on why that is not clamped here.

    Limitation: no lateral force, no wind-induced yaw, hence no rudder-drag penalty for
    holding a heading in a beam wind. That penalty is real (a few percent in a strong beam
    wind) and is not modelled anywhere in KAIROS.
    """
    return _SpeedPowerCurve(vessel, env, theta).r_aa(V)


def total_resistance(vessel: Vessel, env: Env, V: float, theta: float) -> float:
    """R_calm + R_AW + R_AA [N]. Signed; see the module docstring."""
    c = _SpeedPowerCurve(vessel, env, theta)
    return calm_resistance(vessel, V) + c.r_aw + c.r_aa(V)


# ============================================================================ the curve
class _SpeedPowerCurve:
    """P_D as a function of V alone, with every V-independent quantity hoisted out.

    Not a data type and not part of the interface contract -- a computational helper, and
    private for that reason. It exists because `attainable_speed` evaluates the power curve
    about forty times per call at one fixed (vessel, env, theta), and roughly half of that
    work does not depend on V at all: the added wave resistance is *entirely* constant in V,
    as are the heading vector, the drift vector and the still-air reference coefficient.
    Recomputing them forty times cost more than the root find itself.

    This class is the single implementation of the resistance sum. `added_resistance_waves`,
    `wind_resistance`, `total_resistance` and `delivered_power` are all thin wrappers over
    it, so there is no second copy of the physics that can quietly disagree with the first --
    which matters more here than the speed does.
    """
    __slots__ = ("vessel", "eta", "r_aw", "ne", "nn", "de", "dn", "wu", "wv", "q_air")

    def __init__(self, vessel: Vessel, env: Env, theta: float) -> None:
        self.vessel = vessel
        self.eta = _eta(vessel)
        self.ne, self.nn = heading_to_vec(theta)
        self.de, self.dn = drift_vector(vessel, env)
        self.wu, self.wv = env.wu, env.wv
        self.q_air = 0.5 * RHO_AIR * vessel.A_T if vessel.A_T > 0.0 else 0.0

        # STAwave-1 is speed-independent, so it is a constant of this curve. See
        # `added_resistance_waves` for the formula's validity envelope.
        hs = env.hs
        if (not math.isfinite(hs)) or hs <= 0.0 or vessel.L_bwl <= 0.0 or vessel.B <= 0.0:
            self.r_aw = 0.0
        else:
            f_dir = _FDIR_MEAN - _FDIR_AMPL * math.cos(angdiff(env.mu_w, theta))
            self.r_aw = f_dir * (0.0625 * RHO_SW * G * hs * hs * vessel.B
                                 * math.sqrt(vessel.B / vessel.L_bwl))

    def r_aa(self, V: float) -> float:
        """Aerodynamic resistance [N] at speed through water V. See `wind_resistance`."""
        if self.q_air <= 0.0:
            return 0.0
        ge = V * self.ne + self.de
        gn = V * self.nn + self.dn
        vg2 = ge * ge + gn * gn
        re, rn = self.wu - ge, self.wv - gn          # wind as seen from the deck
        vr2 = re * re + rn * rn
        if vr2 <= 1e-24:                             # dead calm relative to the ship
            return -self.q_air * _CX0 * vg2
        # cos(psi) directly from the vectors: psi is measured from the bow to the direction
        # the wind blows FROM, hence the minus sign on the relative-wind vector.
        cpsi = -(re * self.ne + rn * self.nn) / math.sqrt(vr2)
        r = self.q_air * (_cx_from_cos(cpsi) * vr2 - _CX0 * vg2)
        return r if math.isfinite(r) else 0.0

    def at(self, V: float) -> float:
        """Delivered power [W] at speed through water V. See `delivered_power`."""
        if not math.isfinite(V) or V <= 0.0:
            return 0.0
        p_calm = self.vessel.calm_power(V)
        if not math.isfinite(p_calm):
            return 0.0
        # The calm term is used directly rather than round-tripped through
        # R_calm = eta*P/V and back, which makes the identity P_D(calm) == calm_power(V)
        # exact instead of merely accurate to a few parts in 10^15.
        p = p_calm + (self.r_aw + self.r_aa(V)) * V / self.eta
        return p if math.isfinite(p) else 0.0


# ============================================================================ power & fuel
def delivered_power(vessel: Vessel, env: Env, V: float, theta: float) -> float:
    """Delivered (shaft) power [W] required to hold speed through water V on heading theta.

        P_D = R_total(V) * V / eta_D                                         (Eq 1.8)

    MONOTONICITY (Lemma 1.4). The root find in `attainable_speed` has a unique answer iff
    P_D is strictly increasing on (0, V_max_hull]. Term by term:

      * The calm term contributes exactly `vessel.calm_power(V)`, strictly increasing by the
        contract that types.py places on that method.
      * The wave term contributes R_AW * V / eta_D with R_AW >= 0 constant in V, hence
        non-decreasing, and strictly increasing whenever there is any sea at all.
      * The wind term is NOT monotone in general, and this is the one place the guarantee is
        empirical rather than proved. Its derivative is bounded by roughly
        rho_air * A_T * C_X_max * (W + V)^2 / eta_D, which for the default bulker is ~1.6e5
        W per m/s against the calm term's 3 * P_ref * V^2 / V_ref^3. The two cross near
        V ~ 1 m/s in a following wind above ~18 m/s: below that speed, in a strong tailwind,
        P_D genuinely decreases with V. The self-test at the foot of this file measures
        exactly where. It does not matter operationally -- P_D is deeply negative there, far
        below any throttle setting -- and `attainable_speed` is built not to care.

    A user who replaces `calm_power` with a non-monotone spline (a badly conditioned fit
    through sea-trial points will do it, and a hump near the hump speed is physically real
    for some hulls) breaks uniqueness properly. `attainable_speed` then returns the SMALLEST
    root, which is the physically attainable one: a ship accelerates continuously from rest
    and cannot jump across a power hump it does not have the power to climb.

    Returns a signed value; may be negative in a strong following wind or sea, meaning the
    environment supplies net thrust at that speed.
    """
    return _SpeedPowerCurve(vessel, env, theta).at(V)


def fuel_rate(vessel: Vessel, env: Env, V: float, theta: float) -> float:
    """Fuel mass rate [kg/s] at speed through water V on heading theta. Eq 1.12.

        mdot = SFOC(P_D) * P_D

    SFOC comes from `Vessel.sfoc`, a parabolic bowl in engine load. That non-flatness is
    what makes fuel a non-monotone function of speed and therefore what makes the Pareto
    machinery earn its keep rather than collapse to "go as slow as possible" (types.py says
    this at length; it is true).

    Negative delivered power is clamped to zero here, and only here: the environment cannot
    put bunkers back in the tank. The honest limitation is at the other end -- at P_D = 0
    this returns 0.0, whereas a real ship still burns auxiliary and boiler fuel, of order
    0.02-0.05 kg/s for a Handymax. That constant offset is not modelled because it is
    identical on every route of equal duration and so cancels out of every comparison the
    solver makes; add it to the reported total at the I/O boundary if a charterer wants it.

    Engine minimum stable load (`vessel.q_min`) is NOT enforced here. This function reports
    what the given power costs; deciding that a throttle setting is inadmissible is the
    metric's job, and duplicating the check would let the two disagree.

    NOTE FOR THE INTEGRATOR: the default `sfoc_ref = 175e-9` kg/(W*s) in types.py is
    commented as 175 g/kWh, but 175 g/kWh is 48.6e-9 kg/(W*s); as written the default is
    630 g/kWh, roughly 3.6x a modern two-stroke. We use the field as given -- it is not this
    module's to redefine -- but every absolute fuel figure below scales with it.
    """
    p = delivered_power(vessel, env, V, theta)
    if not math.isfinite(p) or p <= 0.0:
        return 0.0
    rate = vessel.sfoc(p) * p
    return rate if math.isfinite(rate) and rate > 0.0 else 0.0


# ============================================================================ the root find
def _bracketed_root(f: Callable[[float], float],
                    a: float, b: float, fa: float, fb: float,
                    ftol: float) -> float:
    """Smallest root of `f` in [a, b] given f(a) <= 0 < f(b). Proc 6.1.

    Guaranteed convergence by construction: iterations alternate between a secant step
    safeguarded into the open interior of the bracket and an unconditional bisection. The
    bisection halves the bracket at least every second iteration, so the width is bounded by
    (b-a) * 2^(-floor(k/2)) after k iterations regardless of how badly conditioned f is --
    that is the Brent-style safety net without Brent's inverse quadratic bookkeeping. In
    practice the secant lands on the answer first and the loop exits in about a dozen calls.

    Secant rather than a true Newton step: Newton needs a derivative, and a central
    difference costs two extra `delivered_power` evaluations per iteration where the secant
    costs none (it reuses the bracket endpoints). In an inner loop that runs tens of
    millions of times, a 3x evaluation count to save two iterations is a bad trade.

    Returns the FEASIBLE side of the final bracket. Reporting `a` rather than the midpoint
    means the returned speed is always one the ship can actually hold on the available
    power; erring the other way would hand the solver a route it cannot sail.
    """
    for k in range(_MAX_ITER):
        width = b - a
        if width <= _V_XTOL:
            break
        if k % 2 == 0:
            d = fb - fa
            c = a - fa * width / d if abs(d) > 1e-30 else a + 0.5 * width
            lo_guard, hi_guard = a + 0.05 * width, b - 0.05 * width
            if not (lo_guard < c < hi_guard):
                c = a + 0.5 * width
        else:
            c = a + 0.5 * width
        fc = f(c)
        if not math.isfinite(fc):
            # A pathological power model in the interior: fall back to pure bisection on
            # the side we still trust rather than propagate the poison.
            b = c
            fb = math.inf
            continue
        if fc <= 0.0:
            a, fa = c, fc
            if -fc <= ftol:
                return c
        else:
            b, fb = c, fc
    return a


def attainable_speed(vessel: Vessel, env: Env, theta: float, q: float) -> float:
    """Largest sustainable speed through water [m/s] on heading `theta` at throttle `q`.

    Formally: the supremum of the connected component containing 0 of

        { V in (0, V_max_hull] : delivered_power(V) <= q * P_MCR }

    which for strictly increasing P_D is simply the largest such V, and in general is the
    SMALLEST root of P_D(V) - q*P_MCR. The distinction is Lemma 1.4's: a ship accelerates
    continuously from rest, so a speed sitting beyond a power hump the engine cannot climb
    is not attainable however comfortable the power balance looks once you are there. If a
    user supplies a non-monotone speed-power spline this function silently and correctly
    returns the near side of the hump.

    Procedure (Proc 6.1):
      1. Scan `_N_SCAN` uniform samples of (0, V_max_hull] for the FIRST sign change of
         g(V) = P_D(V) - q*P_MCR.
      2. Refine that bracket with `_bracketed_root`.
      3. If no sign change is found, the hull cap is reachable and is returned.

    Step 1 dominates the cost, and does so unavoidably: at a normal throttle the root sits
    close to the hull cap, so the scan runs most of the way to `_N_SCAN` before it brackets
    anything. Starting from the top and walking down would find *a* root in a couple of
    evaluations but the WRONG one -- it would find the last crossing rather than the first,
    which is precisely the non-monotone case this function exists to get right. The scan is
    the price of that guarantee, and it is paid down instead by hoisting the V-independent
    half of the power curve out of the loop (`_SpeedPowerCurve`).

    Limitation of step 1: a power excursion above q*P_MCR that is narrower than
    V_max_hull / 32 (about 0.27 m/s for the default bulker) falls between samples and is
    missed, and the function then reports a speed on the far side of it. No fixed sampling
    can do better without an analytic bound on the spline's curvature. Raise `_N_SCAN` if a
    vessel's measured curve is known to be that spiky.

    NEVER raises and NEVER returns NaN. Degenerate cases, all returning 0.0:
      * q <= 0, non-finite q, or P_MCR <= 0 -- no power on offer.
      * V_max_hull <= 0 -- a corrupt vessel record.
      * g(0+) > 0, i.e. not even a crawl is sustainable. With any bounded resistance model
        P_D -> 0 as V -> 0 and this cannot happen, so reaching it means the supplied
        `calm_power` is singular at the origin.
      * A root below `_V_FLOOR` (0.05 m/s). At that speed the ship has no steerage way and
        calling it "attainable" would be a lie the solver would then build a route on. Note
        that the *operational* minimum -- manoeuvring speed, engine minimum load -- is a
        seakeeping ban (S-series) and is applied above this function, not inside it.

    `q` is clamped to `_Q_OVERLOAD` = 1.15. Enforcing the lower bound `q >= vessel.q_min` is
    the caller's job, for the same reason `fuel_rate` does not enforce it.
    """
    v_cap = vessel.V_max_hull
    if not math.isfinite(v_cap) or v_cap <= 0.0:
        return 0.0
    if not math.isfinite(q) or q <= 0.0 or vessel.P_MCR <= 0.0:
        return 0.0
    p_avail = min(q, _Q_OVERLOAD) * vessel.P_MCR
    if not math.isfinite(p_avail) or p_avail <= 0.0:
        return 0.0

    curve = _SpeedPowerCurve(vessel, env, theta)

    def g(v: float) -> float:
        p = curve.at(v)
        if not math.isfinite(p):
            return math.inf          # treat a poisoned evaluation as infeasible, never NaN
        return p - p_avail

    v_prev, g_prev = _V_EPS, g(_V_EPS)
    if not math.isfinite(g_prev) or g_prev > 0.0:
        return 0.0

    lo = hi = g_lo = g_hi = 0.0
    found = False
    for i in range(1, _N_SCAN + 1):
        v_i = v_cap * i / _N_SCAN
        g_i = g(v_i)
        if g_i > 0.0:
            lo, hi, g_lo, g_hi = v_prev, v_i, g_prev, g_i
            found = True
            break
        v_prev, g_prev = v_i, g_i

    if not found:
        return v_cap                 # full power everywhere below the hull cap

    v = _bracketed_root(g, lo, hi, g_lo, g_hi, ftol=_P_RTOL * p_avail)
    if not math.isfinite(v) or v < _V_FLOOR:
        return 0.0
    return min(v, v_cap)


# ============================================================================ self-test
def _selftest() -> None:
    """Exercised with `python -m kairos.powering`. Prints the numbers, asserts the claims."""
    from .types import KTS

    def kn(v: float) -> float:
        return v / KTS

    v = Vessel()
    calm = Env(hs=0.0)
    # Ship steams north; a head sea travels towards the south (mu_w = pi), a head wind
    # blows towards the south (wv < 0). Every scenario below is at theta = 0.
    head6 = Env(hs=6.0, tp=11.0, mu_w=math.pi)
    head6w = Env(hs=6.0, tp=11.0, mu_w=math.pi, wu=0.0, wv=-18.0)
    foll6 = Env(hs=6.0, tp=11.0, mu_w=0.0, wu=0.0, wv=18.0)
    beam6 = Env(hs=6.0, tp=11.0, mu_w=0.5 * math.pi, wu=18.0, wv=0.0)
    th = 0.0

    print("=" * 78)
    print(f"vessel: {v.name}   P_MCR {v.P_MCR/1e6:.2f} MW   hull cap {kn(v.V_max_hull):.2f} kn")
    print("=" * 78)

    # --- identity: in flat calm, still air, no current, P_D must BE the vessel's own curve
    worst = max(abs(delivered_power(v, calm, V, th) - v.calm_power(V))
                for V in (1.0, 3.0, 5.0, 7.0, v.V_max_hull))
    print(f"\n[1] calm-water round trip |P_D - vessel.calm_power| max = {worst:.3e} W")
    assert worst == 0.0, "calm-water identity must be exact, not merely close"

    # The two optimisations in this module are only safe if they are exactly equivalent to
    # the readable forms they replace. Both invariants are cheap to check and expensive to
    # debug once something has silently drifted, so they are asserted rather than trusted.
    a0, a1, a2, a3 = _CX_FOURIER
    e_cx = max(abs(windage_coefficient(p) - (a0 + a1 * math.cos(p) + a2 * math.cos(2 * p)
                                             + a3 * math.cos(3 * p)))
               for p in [i * math.pi / 2000 for i in range(2001)])
    e_wrap = 0.0
    for hs in (0.0, 3.0, 7.0):
        for mu in [i * math.pi / 5 for i in range(10)]:
            for w in (0.0, 15.0, 30.0):
                for tt in (0.0, 1.3, -2.2):
                    en = Env(hs=hs, mu_w=mu, wu=w * math.sin(mu + 0.7),
                             wv=w * math.cos(mu + 0.7), cu=0.5, cv=-0.3)
                    cur = _SpeedPowerCurve(v, en, tt)
                    for V in (0.5, 4.0, 8.0):
                        e_wrap = max(e_wrap,
                                     abs(wind_resistance(v, en, V, tt) - cur.r_aa(V)),
                                     abs(added_resistance_waves(v, en, V, tt) - cur.r_aw),
                                     abs(delivered_power(v, en, V, tt) - cur.at(V)))
    print(f"    C_X Chebyshev cubic vs Fourier series, max err = {e_cx:.2e}")
    print(f"    public wrappers vs _SpeedPowerCurve, max err   = {e_wrap:.2e}")
    assert e_cx < 1e-12, "the cos-domain C_X is not the Fourier series it claims to be"
    assert e_wrap == 0.0, "a public wrapper has drifted from the curve it delegates to"

    # --- resistance decomposition at the service speed
    vr = v.V_ref
    print(f"\n[2] resistance at V_ref = {kn(vr):.2f} kn")
    print(f"    R_calm            {calm_resistance(v, vr)/1e3:9.1f} kN")
    print(f"    R_AW  head Hs=6   {added_resistance_waves(v, head6, vr, th)/1e3:9.1f} kN")
    print(f"    R_AW  beam Hs=6   {added_resistance_waves(v, beam6, vr, th)/1e3:9.1f} kN")
    print(f"    R_AW  foll Hs=6   {added_resistance_waves(v, foll6, vr, th)/1e3:9.1f} kN")
    print(f"    R_AA  still air   {wind_resistance(v, calm, vr, th)/1e3:9.1f} kN  (must be 0)")
    print(f"    R_AA  head 18 m/s {wind_resistance(v, head6w, vr, th)/1e3:9.1f} kN")
    print(f"    R_AA  foll 18 m/s {wind_resistance(v, foll6, vr, th)/1e3:9.1f} kN  (signed)")
    assert abs(wind_resistance(v, calm, vr, th)) < 1e-9, "still-air windage must cancel"
    assert added_resistance_waves(v, head6, vr, th) > added_resistance_waves(v, beam6, vr, th)
    assert added_resistance_waves(v, beam6, vr, th) > added_resistance_waves(v, foll6, vr, th)

    # --- Lemma 1.4: sample the curve and verify strict monotonicity
    print("\n[3] Lemma 1.4 monotonicity of P_D on (0, V_max_hull], 400 samples")
    n = 400
    for label, e in (("calm", calm), ("head sea", head6),
                     ("head sea + wind", head6w), ("beam sea + wind", beam6)):
        prev = -math.inf
        ok = True
        for i in range(1, n + 1):
            p = delivered_power(v, e, v.V_max_hull * i / n, th)
            if not (p > prev):
                ok = False
                break
            prev = p
        print(f"    {label:<18} strictly increasing: {ok}")
        assert ok, f"P_D not strictly increasing in {label}"

    # The documented exception. Measured, not assumed.
    prev, dips, last_dip = -math.inf, 0, 0.0
    for i in range(1, n + 1):
        vv = v.V_max_hull * i / n
        p = delivered_power(v, foll6, vv, th)
        if p <= prev:
            dips += 1
            last_dip = vv
        prev = p
    print(f"    {'foll sea + 18 wind':<18} strictly increasing: {dips == 0}"
          f"   ({dips} dips, all below {last_dip:.2f} m/s = {kn(last_dip):.2f} kn)")
    # The dip must stay far below anything the solver will ever ask for, and P_D must be
    # negative throughout it -- that is what makes it operationally invisible.
    assert last_dip < 0.15 * v.V_max_hull
    assert delivered_power(v, foll6, last_dip, th) < 0.0

    # --- headline: attainable speed and fuel rate
    # --- root find against ground truth. In flat calm and still air the Admiralty law
    # inverts in closed form, V = V_ref * (q*P_MCR/P_ref)^(1/n), so the root find can be
    # checked against an exact answer rather than against itself.
    print("\n[3b] root find vs analytic inverse of the Admiralty law (calm, still air)")
    worst_v = 0.0
    for q in (1.0, 0.75, 0.5, 0.25, 0.15):
        ana = v.V_ref * (q * v.P_MCR / v.P_ref) ** (1.0 / v.n_adm)
        num = attainable_speed(v, calm, th, q)
        worst_v = max(worst_v, abs(num - ana))
        # The returned speed must be on the FEASIBLE side: never ask for more than q*MCR.
        assert delivered_power(v, calm, num, th) <= q * v.P_MCR * (1.0 + 1e-12)
    print(f"    max |V_root - V_analytic| = {worst_v:.2e} m/s "
          f"(tolerance {_V_XTOL:.0e}), always on the feasible side")
    assert worst_v <= _V_XTOL, "root find is outside its own stated tolerance"

    print("\n[4] attainable speed / fuel rate")
    print(f"    {'scenario':<26}{'q':>5}{'V [kn]':>10}{'P_D [MW]':>11}"
          f"{'kg/s':>9}{'t/day':>9}{'kg/nm':>9}")
    rows = {}
    for label, e in (("calm water", calm), ("6 m head sea", head6),
                     ("6 m head sea + 18 m/s", head6w)):
        for q in (1.0, 0.5):
            V = attainable_speed(v, e, th, q)
            p = delivered_power(v, e, V, th)
            f = fuel_rate(v, e, V, th)
            rows[(label, q)] = (V, p, f)
            # kg per nautical mile of water track. At a fixed throttle the fuel RATE is the
            # same in every weather -- the engine burns what it is fed -- so the rate column
            # alone makes weather look free. The penalty is entirely in the speed, and only
            # a per-distance figure exposes it. This is why the metric costs edges by
            # fuel/sog and not by fuel rate.
            per_nm = f * (1852.0 / V) if V > 0.0 else float("inf")
            print(f"    {label:<26}{q:>5.2f}{kn(V):>10.3f}{p/1e6:>11.3f}"
                  f"{f:>9.4f}{f*86.4:>9.2f}{per_nm:>9.1f}")
            assert math.isfinite(V) and V >= 0.0
            assert abs(p - q * v.P_MCR) < 1e-3 * v.P_MCR or V >= v.V_max_hull - 1e-9

    print("\n[5] head-sea speed loss vs calm water, same throttle")
    for q in (1.0, 0.5):
        v_calm = rows[("calm water", q)][0]
        v_wave = rows[("6 m head sea", q)][0]
        v_full = rows[("6 m head sea + 18 m/s", q)][0]
        loss_w = (v_calm - v_wave) / v_calm
        loss_f = (v_calm - v_full) / v_calm
        print(f"    q={q:.2f}  waves only {loss_w*100:5.2f}%   "
              f"waves + consistent wind {loss_f*100:5.2f}%")
        # A 6 m sea does not exist without ~18 m/s of wind, so the combined case is the
        # physical one and carries the assertion. The waves-only figure is the decomposition.
        assert 0.10 <= loss_f <= 0.30, f"combined head-sea loss {loss_f:.3f} outside 10-30%"
        assert 0.05 <= loss_w <= 0.30, f"wave-only head-sea loss {loss_w:.3f} implausible"

    # --- the non-monotone spline contract: SMALLEST root
    print("\n[6] non-monotone speed-power spline -> smallest root")

    class _HumpedVessel(Vessel):
        """A hull with a power hump at 5 m/s that exceeds MCR, then falls back below it.

        Physically this is an exaggerated hump-speed hull; numerically it is what a badly
        conditioned spline through sea-trial points does. The feasible set is disconnected,
        and only the component containing rest is reachable.
        """
        def calm_power(self, V: float) -> float:
            if V <= 0.0:
                return 0.0
            base = self.P_ref * (V / self.V_ref) ** self.n_adm
            return base + 9.5e6 * math.exp(-((V - 5.0) / 0.9) ** 2)

    hv = _HumpedVessel()
    v_hump = attainable_speed(hv, calm, th, 1.0)
    p_hump = delivered_power(hv, calm, v_hump, th)
    p_peak = delivered_power(hv, calm, 5.0, th)
    p_beyond = delivered_power(hv, calm, 7.5, th)
    print(f"    attainable   = {kn(v_hump):6.3f} kn ({v_hump:.3f} m/s), P_D = {p_hump/1e6:.3f} MW")
    print(f"    P_D(5.0 m/s) = {p_peak/1e6:6.3f} MW  > MCR  <- the hump blocks the way")
    print(f"    P_D(7.5 m/s) = {p_beyond/1e6:6.3f} MW <= MCR  <- feasible but UNREACHABLE")
    assert v_hump < 5.0, "must return the near side of the hump"
    assert p_peak > hv.P_MCR, "the demo needs the hump to actually exceed MCR"
    assert p_beyond <= hv.P_MCR, "the demo needs a feasible far component to be meaningful"
    # The base vessel with the same throttle reaches well past the hump: proof that the
    # short answer above comes from the spline, not from some unrelated clamp.
    assert attainable_speed(v, calm, th, 1.0) > 7.5

    # --- degeneracies: none of these may raise or return NaN
    print("\n[7] degenerate inputs")
    cases = [("q = 0", (v, calm, th, 0.0)),
             ("q < 0", (v, calm, th, -0.4)),
             ("q = NaN", (v, calm, th, float("nan"))),
             ("q = 1e-9", (v, calm, th, 1e-9)),
             ("q = 5 (clamped)", (v, calm, th, 5.0)),
             ("Hs = 25 m head", (v, Env(hs=25.0, mu_w=math.pi), th, 1.0)),
             ("40 m/s head wind", (v, Env(wv=-40.0), th, 1.0)),
             ("40 m/s foll wind", (v, Env(wv=40.0), th, 1.0)),
             ("6 kn head current", (v, Env(cv=-3.0), th, 1.0))]
    for label, args in cases:
        V = attainable_speed(*args)
        f = fuel_rate(args[0], args[1], V, th)
        assert math.isfinite(V) and V >= 0.0, f"{label} gave {V}"
        assert math.isfinite(f) and f >= 0.0, f"{label} gave fuel {f}"
        print(f"    {label:<20} V = {kn(V):7.3f} kn   fuel = {f:.4f} kg/s")

    # a vessel with a zero hull cap, and a zero-power vessel
    import dataclasses
    assert attainable_speed(dataclasses.replace(v, V_max_hull=0.0), calm, th, 1.0) == 0.0
    assert attainable_speed(dataclasses.replace(v, P_MCR=0.0), calm, th, 1.0) == 0.0
    print("    zero hull cap / zero MCR -> 0.0")

    print("\nall assertions passed")


if __name__ == "__main__":
    _selftest()
