"""The five interface primitives, as executable types.

Spec reference: CONTRACT.md section 4.

This module is the *only* coupling point between the physics layer and the solver. The
solver imports nothing from `vessel`, `seakeeping` or `environment` -- it sees `MetricLike`
and nothing else. That is what makes the vessel model swappable (bulker -> container ->
ferry) without touching the algorithm, which is the "versatile ... range of ships"
requirement of the problem statement discharged structurally rather than by promise.

A port to another language reproduces this file first. Everything else follows from it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, Protocol, Sequence, Tuple

G = 9.80665             # m/s^2
RHO_SW = 1025.0         # kg/m^3, seawater
RHO_AIR = 1.225         # kg/m^3
KTS = 0.5144444444      # m/s per knot


# ============================================================================ environment
@dataclass(frozen=True, slots=True)
class Env:
    """Environmental state at one (x, t). All SI, all in the local east/north frame.

    `mu_w` is the direction the waves are travelling TOWARDS, radians, 0 = north,
    clockwise. (Meteorological convention is "from"; we convert at the data boundary and
    never again. Mixing the two is a 180-degree error that looks plausible on a map.)
    """
    cu: float = 0.0          # current, east component  [m/s]
    cv: float = 0.0          # current, north component [m/s]
    wu: float = 0.0          # wind 10 m, east          [m/s]
    wv: float = 0.0          # wind 10 m, north         [m/s]
    hs: float = 0.0          # significant wave height  [m]
    tp: float = 8.0          # peak period              [s]
    mu_w: float = 0.0        # mean wave direction TOWARDS [rad]
    depth: float = 4000.0    # bathymetric depth        [m]

    @property
    def wave_omega_p(self) -> float:
        """Peak angular frequency. Guarded for tp -> 0 in calm cells."""
        return 2.0 * math.pi / max(self.tp, 1e-3)

    @property
    def wave_length_p(self) -> float:
        """Deep-water peak wavelength, L = g T^2 / 2pi. Shallow-water correction is applied
        in `seakeeping` where depth actually matters (surf-riding, S3)."""
        return G * self.tp * self.tp / (2.0 * math.pi)


class EnvField(Protocol):
    """Primitive 1: sample_env(x, t) -> Env. Must be deterministic and side-effect free.

    Determinism is not a style preference: the ordered-upwind sweep evaluates the same
    (x, t) from several front edges and the causality proof (Thm 3.1) assumes it gets the
    same answer every time. A field with hidden state breaks the algorithm silently.
    """

    def at(self, lat: float, lon: float, t: float) -> Env: ...

    @property
    def t0(self) -> float: ...

    @property
    def horizon(self) -> float:
        """Last time for which the forecast is valid. Past this, the solver must either
        persist the last frame or refuse -- see 06-numerics.md (f)."""
        ...


# ============================================================================ vessel
@dataclass(frozen=True, slots=True)
class Vessel:
    """Ship model. Defaults are a generic Handymax bulker.

    Every quantity is one a charterer or a class society actually publishes, which is the
    point: adding a vessel must not require a towing-tank campaign.
    """
    name: str = "Generic Handymax bulker"

    # --- geometry
    L: float = 190.0             # length between perpendiculars [m]
    B: float = 32.0              # beam [m]
    T_d: float = 11.0            # draft [m]
    L_bwl: float = 185.0         # length of bow at waterline [m], for STAwave-1
    freeboard: float = 6.5       # [m], green-water criterion
    A_T: float = 620.0           # transverse windage area [m^2]

    # --- powering
    V_ref: float = 14.0 * KTS    # reference (service) speed through water [m/s]
    P_ref: float = 8.2e6         # shaft power at V_ref, calm water [W]
    P_MCR: float = 11.0e6        # maximum continuous rating [W]
    n_adm: float = 3.0           # Admiralty exponent, P ~ V^n
    eta_D: float = 0.68          # quasi-propulsive coefficient
    q_min: float = 0.15          # minimum stable engine load, fraction of MCR
    V_max_hull: float = 16.5 * KTS   # hull/contract speed cap [m/s]

    # --- fuel
    sfoc_ref: float = 175e-9     # kg per (W s) at the SFOC optimum   (= 175 g/kWh)
    sfoc_q_opt: float = 0.75     # engine load at which SFOC is minimal
    sfoc_curv: float = 0.28      # curvature of the SFOC bowl (dimensionless)

    # --- stability / seakeeping
    GM: float = 2.4              # metacentric height [m]
    k_xx: float = 0.38           # roll gyradius as a fraction of beam
    hs_limit: float = 6.5        # operator heavy-weather limit [m]
    hs_caution: float = 4.5      # comfort / cargo threshold [m]
    ukc_margin: float = 2.0      # under-keel clearance required [m]

    # --- drift
    kappa_L: float = 0.025       # leeway as a fraction of true wind

    # --- which seakeeping criteria are enforced (bitmask, see seakeeping.py)
    bans_enabled: int = 0b1111111

    # ------------------------------------------------------------------ derived
    @property
    def omega_roll(self) -> float:
        """Natural roll angular frequency [rad/s]. T_roll = 2 pi k_xx B / sqrt(g GM)."""
        return math.sqrt(G * self.GM) / (self.k_xx * self.B)

    @property
    def T_roll(self) -> float:
        return 2.0 * math.pi / self.omega_roll

    def calm_power(self, V: float) -> float:
        """Calm-water shaft power at speed through water V [m/s] -> [W].

        Admiralty form by default. Override by subclassing and replacing this method with a
        spline through a measured speed-power curve; nothing else in the code changes.
        The solver requires only that this be strictly increasing on [0, V_max_hull]
        (Lemma 1.4 of the spec), which the Admiralty form satisfies for n > 0.
        """
        if V <= 0.0:
            return 0.0
        return self.P_ref * (V / self.V_ref) ** self.n_adm

    def sfoc(self, P: float) -> float:
        """Specific fuel consumption [kg/(W s)] at delivered power P.

        A shallow parabolic bowl in engine load with its minimum at `sfoc_q_opt`. This is
        what makes fuel a NON-MONOTONE function of speed, and therefore what makes the
        multi-objective machinery necessary rather than cosmetic (spec 01, section 1.7).
        A flat SFOC would make the fuel-optimal route always the slowest feasible one, and
        the whole Pareto front would collapse to a line.
        """
        q = P / self.P_MCR if self.P_MCR > 0 else 0.0
        q = min(max(q, 1e-6), 1.2)
        d = (q - self.sfoc_q_opt) / self.sfoc_q_opt
        return self.sfoc_ref * (1.0 + self.sfoc_curv * d * d)


# ============================================================================ controls
@dataclass(frozen=True, slots=True)
class Control:
    """A commanded control. `V` is through-water speed, NOT over ground."""
    V: float                 # [m/s] through water
    theta: float             # [rad] true heading, 0 = north, clockwise
    q: float                 # [-] throttle, fraction of MCR actually delivered


@dataclass(frozen=True, slots=True)
class Leg:
    """The result of evaluating one control in one direction: what the label algebra needs.

    `sog` is speed made good ALONG THE REQUESTED DIRECTION -- the drift-corrected scalar,
    not |ground velocity|. Those differ whenever the current has a cross-track component,
    and using the wrong one silently inflates progress. See spec Def 2.3.
    """
    sog: float               # [m/s] speed made good in the requested direction
    fuel_rate: float         # [kg/s]
    risk_rate: float         # [1/s] additive risk accrual
    risk_level: float        # [-]   instantaneous risk, for the bottleneck objective
    comfort_rate: float = 0.0
    q: float = 1.0
    theta: float = 0.0       # the heading actually commanded (differs from course by leeway/set)


# ============================================================================ the metric
class MetricLike(Protocol):
    """Primitives 3-5. The ONLY surface the solver touches.

    Implementations: `metric.FinslerMetric` (full physics), `metric.RandersMetric`
    (closed-form, for tests and for the fast path), and any mock a test wants.
    """

    def legs(self, lat: float, lon: float, t: float, u: Tuple[float, float]) -> Sequence[Leg]:
        """The one-parameter family of achievable legs in unit direction `u` at time `t`.

        This is design decision D1 made concrete: because throttle is a free control, a
        direction does not have *a* speed, it has a CURVE of (speed, fuel, risk) triples.
        Returns the Pareto-nondominated subset of that curve, ordered by decreasing `sog`.
        Empty sequence means the direction is infeasible (F = +inf there).
        """
        ...

    def sigma_max(self, lat: float, lon: float, t: float, u: Tuple[float, float]) -> float:
        """Fastest speed made good in direction `u`; 0.0 if infeasible.

        Equivalent to `legs(...)[0].sog` but allowed to be much cheaper, and it is: the
        time-only solve never needs the rest of the family. Most calls go here.
        """
        ...

    def support(self, lat: float, lon: float, t: float, p: Tuple[float, float]) -> float:
        """Support function h(p) = max over v in conv(V) of <v, p>. Spec Def 2.6."""
        ...

    def anisotropy(self, lat: float, lon: float, t: float) -> float:
        """Local anisotropy coefficient Upsilon_loc = sigma_max / sigma_min. Spec Def 2.9."""
        ...


# ============================================================================ objectives
class Accum:
    """How each objective accumulates along a route.

    Spec Prop 5.4: label setting stays correct for any accumulation that is monotone and
    isotone over an ordered semiring. `ADD` and `MAX` both qualify; `MAX` is the one a
    master actually uses ("what is the worst moment of this voyage") and is the one no
    weighted sum can express.
    """
    ADD = "add"
    MAX = "max"


@dataclass(frozen=True, slots=True)
class ObjectiveSpec:
    name: str
    accum: str               # Accum.ADD | Accum.MAX
    eps_bucket: bool         # participate in eps-dominance bucketing?
    floor: float = 1e-12     # smallest value distinguishable, for log bucketing


DEFAULT_OBJECTIVES: Tuple[ObjectiveSpec, ...] = (
    ObjectiveSpec("time", Accum.ADD, eps_bucket=False),   # index 0 drives the queue order
    ObjectiveSpec("fuel", Accum.ADD, eps_bucket=True),
    ObjectiveSpec("risk", Accum.MAX, eps_bucket=True),
)


# ============================================================================ results
@dataclass(slots=True)
class Waypoint:
    lat: float
    lon: float
    t: float
    theta: float = 0.0
    q: float = 1.0
    sog: float = 0.0


@dataclass(slots=True)
class Route:
    waypoints: list
    time_s: float
    fuel_kg: float
    risk: float
    comfort: float = 0.0
    expanded: int = 0
    label_peak: int = 0
    certificate_gap: Optional[float] = None   # (J - lower_bound) / lower_bound, spec Cor 4.12
    notes: list = field(default_factory=list)

    @property
    def hours(self) -> float:
        return self.time_s / 3600.0

    @property
    def fuel_t(self) -> float:
        return self.fuel_kg / 1000.0

    def summary(self) -> str:
        cert = "n/a" if self.certificate_gap is None else f"<={self.certificate_gap * 100:.2f}%"
        return (f"{self.hours:7.2f} h | {self.fuel_t:8.2f} t | risk {self.risk:5.3f} | "
                f"gap {cert} | {len(self.waypoints)} wpts")
