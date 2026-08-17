"""Environmental fields: primitive 1 of the interface contract.

Spec reference: CONTRACT.md section 4 (`sample_env`), 06-numerics.md (f) for horizon
handling, Thm 3.1 for the temporal Lipschitz diagnostic at the bottom of this file.

Five implementations, in increasing order of dishonesty about the ocean:

    UniformField          constant -- the analytic test bed, F is a translate of a disc
    LinearShearField      c = (alpha (phi - phi0) R_E, 0) -- Zermelo's shear problem, which
                          has closed-form geodesics, so it is the convergence test
    RankineVortexField    solid-body core, potential exterior -- the hard analytic case:
                          the metric is strongly anisotropic in an annulus and the drift
                          exceeds any merchant speed near r = a for a realistic circulation
    GriddedField          trilinear on (time, lat, lon) -- what a real forecast arrives as
    SyntheticIndianOcean  a reproducible scenario with a western boundary jet, a monsoon
                          swell field and a translating cyclone

DETERMINISM. `EnvField` in types.py requires `at` to be side-effect free and repeatable,
because the ordered-upwind sweep evaluates the same (x, t) from several front edges and the
causality proof assumes it gets the same answer each time. Two consequences are visible in
the code below and must survive any edit:

  (a) No sampler mutates instance state. In particular there is no `field.last_clamped`
      attribute, which is the obvious way to "expose a flag" and is also a data race the
      moment the sweep is threaded. Clamping is reported by a *second entry point*,
      `at_flagged(lat, lon, t) -> (Env, SampleFlags)`; `at` discards the flags. All five
      classes provide it, so a caller can probe uniformly.
  (b) `SyntheticIndianOcean` draws from a seeded `numpy.random.Generator` exactly once, in
      `__init__`, and stores the draws as immutable tuples. `at` performs no random number
      generation. `GriddedField` copies its input arrays and marks them read-only, so a
      caller mutating the array it passed in cannot retroactively change past samples.

HORIZON. The two data-driven fields (`GriddedField`, `SyntheticIndianOcean`) persist the
final frame past `horizon` and raise `beyond_horizon` in the flags -- the "persist" branch
of 06-numerics.md (f). The three analytic fields are closed-form and valid for all t, so
they do NOT clamp; their `horizon` is advisory, published only so the solver can be
exercised against horizon logic. This asymmetry is deliberate; do not "fix" it.

Angles are radians, vectors are (east, north) with east FIRST, per CONTRACT.md section 1.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Callable, Optional, Sequence, Tuple

import numpy as np

from .geodesy import (
    R_E,
    destination,
    heading_to_vec,
    local_step_metres,
    vec_to_heading,
    wrap_pi,
)
from .types import Env, EnvField, Vessel

_TWO_PI = 2.0 * math.pi
_DEG = math.pi / 180.0
_DEFAULT_HORIZON_S = 5.0 * 86400.0      # typical operational forecast reach

__all__ = [
    "SampleFlags",
    "UniformField",
    "LinearShearField",
    "RankineVortexField",
    "GriddedField",
    "SyntheticIndianOcean",
    "temporal_lipschitz",
]


# ============================================================================ flags
@dataclass(frozen=True, slots=True)
class SampleFlags:
    """What a sampler had to do to answer a query outside its domain.

    Returned by `at_flagged`, never stored on the field (see the module docstring). The
    solver treats `clamped_space` as a hard warning -- a route that leaves the forecast
    domain is being costed against a boundary value that no model produced -- and
    `beyond_horizon` as the expected condition on any voyage longer than the forecast.
    """
    clamped_space: bool = False     # lat and/or lon outside the grid, nearest edge used
    clamped_time: bool = False      # t outside [t0, horizon], nearest frame used
    beyond_horizon: bool = False    # specifically t > horizon: the final frame persisted

    @property
    def any(self) -> bool:
        return self.clamped_space or self.clamped_time or self.beyond_horizon


_NO_FLAGS = SampleFlags()


def _resolve_horizon(t0: float, horizon: Optional[float]) -> float:
    if horizon is None:
        return t0 + _DEFAULT_HORIZON_S
    if horizon <= t0:
        raise ValueError(f"horizon {horizon} must be strictly after t0 {t0}")
    return float(horizon)


# ============================================================================ uniform
class UniformField(EnvField):
    """One `Env` everywhere, for all time.

    The indicatrix is then the same convex set at every node, so F is a Minkowski norm
    rather than a Finsler metric and the geodesics are straight lines in the tangent plane.
    Every unit test that wants to isolate the solver from the physics starts here: any
    curvature in the returned route is a bug in the sweep, not in the ocean.
    """

    def __init__(self, env: Env = Env(), t0: float = 0.0,
                 horizon: Optional[float] = None) -> None:
        self._env = env
        self._t0 = float(t0)
        self._horizon = _resolve_horizon(self._t0, horizon)

    @property
    def t0(self) -> float:
        return self._t0

    @property
    def horizon(self) -> float:
        return self._horizon

    def at(self, lat: float, lon: float, t: float) -> Env:
        return self._env

    def at_flagged(self, lat: float, lon: float, t: float) -> Tuple[Env, SampleFlags]:
        return self._env, _NO_FLAGS


# ============================================================================ linear shear
class LinearShearField(EnvField):
    """Zonal current with constant meridional shear: c = (alpha (phi - phi0) R_E, 0).

    This is the one non-trivial drift for which the Zermelo problem has closed-form
    geodesics (Zermelo 1931; the optimal heading satisfies dtheta/dt = -alpha cos^2 theta,
    so cot theta is affine in time and the track is a catenary-like curve). That makes it
    the convergence test of 08-validation: the numerical geodesic must approach the analytic
    one at the advertised order as h -> 0.

    `alpha` has units 1/s. alpha = 1.8e-6 gives 1 m/s of drift five degrees from phi0,
    which is the right order for a mid-ocean shear zone. Note that the field is unbounded:
    far enough from phi0 the drift exceeds any merchant speed and the westward directions
    become infeasible (F = +inf). That is not a defect, it is the point -- it exercises the
    infeasible-direction branch of the metric with a case whose answer is known.
    """

    def __init__(self, alpha: float, lat0: float = 0.0, base: Env = Env(),
                 t0: float = 0.0, horizon: Optional[float] = None) -> None:
        self._alpha = float(alpha)
        self._lat0 = float(lat0)
        self._base = base
        self._t0 = float(t0)
        self._horizon = _resolve_horizon(self._t0, horizon)

    @property
    def t0(self) -> float:
        return self._t0

    @property
    def horizon(self) -> float:
        return self._horizon

    @property
    def alpha(self) -> float:
        return self._alpha

    def at(self, lat: float, lon: float, t: float) -> Env:
        return replace(self._base, cu=self._alpha * (lat - self._lat0) * R_E, cv=0.0)

    def at_flagged(self, lat: float, lon: float, t: float) -> Tuple[Env, SampleFlags]:
        return self.at(lat, lon, t), _NO_FLAGS


# ============================================================================ Rankine vortex
class RankineVortexField(EnvField):
    """Rankine combined vortex, optionally translating.

    Tangential speed  v(r) = v_max * r/a      for r <= a   (solid-body core)
                      v(r) = v_max * a/r      for r >  a   (irrotational exterior)

    Continuous at r = a, peak exactly at r = a, and the exterior carries the whole
    circulation Gamma = 2 pi a v_max. It is the hard analytic case for two reasons: the
    metric is strongly anisotropic in the annulus around a (Upsilon_loc is roughly
    (V + v_max)/(V - v_max) there), and the exterior 1/r tail means the coarse heuristic of
    Prop 4.11 must dilate cells rather than take cell minima -- exactly the gap D5 closes.

    `inflow` rotates the velocity towards the centre by that angle in radians while
    preserving its magnitude; a tropical cyclone has 20-30 degrees of inflow in the
    boundary layer, so `inflow=0.35` is the realistic setting when this class is used for a
    storm wind field.

    The centre translates at (drift_east, drift_north) along a true spherical geodesic, so
    a multi-day translation does not accumulate tangent-plane error.
    """

    def __init__(self, lat_c: float, lon_c: float, a_m: float, v_max: float,
                 sign: float = 1.0, inflow: float = 0.0,
                 drift_east: float = 0.0, drift_north: float = 0.0,
                 base: Env = Env(), t0: float = 0.0,
                 horizon: Optional[float] = None) -> None:
        if a_m <= 0.0:
            raise ValueError("core radius a_m must be positive")
        self._lat_c0 = float(lat_c)
        self._lon_c0 = float(lon_c)
        self._a = float(a_m)
        self._v_max = float(v_max)
        self._sign = 1.0 if sign >= 0.0 else -1.0
        self._cos_in = math.cos(inflow)
        self._sin_in = math.sin(inflow)
        self._drift_speed = math.hypot(drift_east, drift_north)
        self._drift_bearing = vec_to_heading(drift_east, drift_north)
        self._base = base
        self._t0 = float(t0)
        self._horizon = _resolve_horizon(self._t0, horizon)

    @property
    def t0(self) -> float:
        return self._t0

    @property
    def horizon(self) -> float:
        return self._horizon

    @property
    def core_radius(self) -> float:
        return self._a

    @property
    def circulation(self) -> float:
        """Gamma = 2 pi a v_max [m^2/s]."""
        return _TWO_PI * self._a * self._v_max

    @property
    def drift_speed(self) -> float:
        return self._drift_speed

    @property
    def drift_bearing(self) -> float:
        """Translation heading, radians, 0 = north. Zero when the vortex is stationary."""
        return self._drift_bearing

    def centre_at(self, t: float) -> Tuple[float, float]:
        """Vortex centre (lat, lon) in radians at absolute time t."""
        d = self._drift_speed * (t - self._t0)
        if d == 0.0:
            return self._lat_c0, self._lon_c0
        return destination(self._lat_c0, self._lon_c0, self._drift_bearing, d)

    def radius_at(self, lat: float, lon: float, t: float) -> float:
        """Distance from the centre in metres, in the tangent-plane frame the velocity
        formula uses. Deliberately not haversine: the two must agree with each other or the
        vortex is not axisymmetric in the frame the solver integrates in."""
        lat_c, lon_c = self.centre_at(t)
        e, n = local_step_metres(0.5 * (lat + lat_c), lat - lat_c, lon - lon_c)
        return math.hypot(e, n)

    def velocity_at(self, lat: float, lon: float, t: float) -> Tuple[float, float]:
        """(east, north) velocity of the vortex flow. Reusable as a wind field -- see
        SyntheticIndianOcean, which drives its cyclone from this and puts the result in the
        wind slots rather than the current slots."""
        lat_c, lon_c = self.centre_at(t)
        # cos(lat) is taken at the mean latitude: a secant rather than a tangent
        # approximation, which halves the radius error at the top and bottom of a storm.
        e, n = local_step_metres(0.5 * (lat + lat_c), lat - lat_c, lon - lon_c)
        r = math.hypot(e, n)
        if r < 1e-6:
            # The eye. Solid-body v(0) = 0 exactly; returning it explicitly keeps the
            # division below from ever seeing zero.
            return 0.0, 0.0
        v = self._v_max * (r / self._a) if r <= self._a else self._v_max * (self._a / r)
        er, nr = e / r, n / r                       # outward radial unit
        te, tn = self._sign * -nr, self._sign * er  # tangential; sign > 0 is anticlockwise
        return (v * (self._cos_in * te - self._sin_in * er),
                v * (self._cos_in * tn - self._sin_in * nr))

    def at(self, lat: float, lon: float, t: float) -> Env:
        cu, cv = self.velocity_at(lat, lon, t)
        return replace(self._base, cu=cu, cv=cv)

    def at_flagged(self, lat: float, lon: float, t: float) -> Tuple[Env, SampleFlags]:
        return self.at(lat, lon, t), _NO_FLAGS


# ============================================================================ gridded
class _Axis:
    """A strictly ascending coordinate axis with O(1) lookup when uniformly spaced.

    searchsorted is O(log n) and shows up in profiles, because a single solve samples the
    field millions of times and three axes are located per sample. Every operational ocean
    and NWP product is on a regular grid, so the uniform branch -- one subtraction and one
    division -- is the case that matters; the searchsorted branch exists for hybrid vertical
    or stretched grids and is correct, just slower.
    """
    __slots__ = ("v", "n", "uniform", "_lo", "_hi", "_step")

    def __init__(self, values: Sequence[float], name: str) -> None:
        a = np.array(values, dtype=float, copy=True).ravel()
        if a.size < 1:
            raise ValueError(f"{name} axis is empty")
        if a.size > 1 and not bool(np.all(np.diff(a) > 0.0)):
            raise ValueError(f"{name} axis must be strictly ascending")
        a.setflags(write=False)
        self.v = a
        self.n = int(a.size)
        self._lo = float(a[0])
        self._hi = float(a[-1])
        if self.n > 1:
            d = np.diff(a)
            d0 = float(d[0])
            self.uniform = bool(np.all(np.abs(d - d0) <= 1e-9 * abs(d0) + 1e-12))
            self._step = d0
        else:
            self.uniform = True
            self._step = 1.0

    @property
    def lo(self) -> float:
        return self._lo

    @property
    def hi(self) -> float:
        return self._hi

    def locate(self, x: float) -> Tuple[int, int, float, bool]:
        """-> (i0, i1, w, clamped) with value(x) = (1-w) a[i0] + w a[i1]."""
        if self.n == 1:
            return 0, 0, 0.0, x != self._lo
        if x <= self._lo:
            return 0, 1, 0.0, x < self._lo
        if x >= self._hi:
            return self.n - 2, self.n - 1, 1.0, x > self._hi
        if self.uniform:
            g = (x - self._lo) / self._step
            i0 = int(g)
            if i0 > self.n - 2:
                i0 = self.n - 2
            return i0, i0 + 1, g - i0, False
        i0 = int(np.searchsorted(self.v, x, side="right")) - 1
        if i0 < 0:
            i0 = 0
        elif i0 > self.n - 2:
            i0 = self.n - 2
        lo = float(self.v[i0])
        return i0, i0 + 1, (x - lo) / (float(self.v[i0 + 1]) - lo), False


class GriddedField(EnvField):
    """Trilinear interpolation of forecast arrays on (time, lat, lon).

    Arrays are (nt, nlat, nlon), float, SI, in the conventions of `Env` -- in particular
    `mu_w` is the direction the waves travel TOWARDS. Convert at the reader that builds this
    object, never here.

    Three things this class exists to get right:

    ANTIMERIDIAN. The longitude axis is stored unwrapped: the constructor takes the wrapped
    differences and accumulates them, so an axis given as [170, 175, 180, -175, -170]
    degrees becomes strictly ascending and the interpolation across 180 is an ordinary
    interior interpolation with no special case. A query longitude is mapped into that frame
    by adding the multiple of 2 pi that lands it in [lon[0], lon[0] + 2 pi). If the axis
    covers the globe (the gap from the last column back to the first is about one cell) the
    seam cell between column n-1 and column 0 is interpolated too, so a global grid has no
    discontinuity anywhere.

    OUT OF DOMAIN. Latitude, and longitude on a regional grid, clamp to the nearest edge and
    raise `clamped_space`. Clamping rather than raising is the right default because the
    ordered-upwind stencil legitimately probes points just outside the front's own bounding
    box; a hard error there would make the solver's correctness depend on the grid's
    generosity. The flag is what lets the caller notice that a *route* left the domain.

    HORIZON. For t > `horizon` the final frame is persisted and `beyond_horizon` is set --
    06-numerics.md (f). Persisting is not free: it makes the field constant in time past the
    horizon, hence L_t = 0 there, hence the FIFO condition of Thm 3.1 holds trivially, which
    flatters the diagnostic. `temporal_lipschitz` says so in its docstring.

    Interpolating `mu_w` linearly would be wrong across the +-pi seam (the mean of 179 and
    -179 degrees is not 0), so the constructor stores sin and cos of the wave direction and
    interpolates those, recovering the angle with atan2. This costs one extra array.

    COST. Measured 13.6 us per sample on a Ryzen 7730U for a (8, 81, 180) grid with seven
    variables -- about 73 k samples/s. Roughly 10 us of that is the 56 numpy scalar
    extractions (8 corners x 7 fields); flattening the variables into one (n_var, N) buffer
    and replacing the per-field gather with a single `take` plus a length-8 dot product
    measures 4x faster, and is the first thing to do if this becomes the bottleneck. It is
    not done here because the support-function tabulation of D2 samples the environment once
    per (cell, forecast hour), not once per stencil evaluation: about 1 M samples, 13 s, once
    per solve. Vectorising over a batch of query points would beat both.
    """

    def __init__(self, times: Sequence[float], lats: Sequence[float], lons: Sequence[float],
                 cu: np.ndarray, cv: np.ndarray,
                 wu: Optional[np.ndarray] = None, wv: Optional[np.ndarray] = None,
                 hs: Optional[np.ndarray] = None, tp: Optional[np.ndarray] = None,
                 mu_w: Optional[np.ndarray] = None,
                 depth: Optional[np.ndarray] = None,
                 base: Env = Env(), lon_periodic: Optional[bool] = None) -> None:
        self._tax = _Axis(times, "time")
        self._latax = _Axis(lats, "lat")

        lon_in = np.array(lons, dtype=float, copy=True).ravel()
        if lon_in.size < 1:
            raise ValueError("lon axis is empty")
        # Unwrap: an axis crossing the antimeridian is ascending only after the wrapped
        # differences are accumulated. Requires every step to be a genuine eastward step.
        unwrapped = np.empty_like(lon_in)
        unwrapped[0] = lon_in[0]
        for i in range(1, lon_in.size):
            step = wrap_pi(float(lon_in[i]) - float(lon_in[i - 1]))
            if step <= 0.0:
                raise ValueError("lon axis must step monotonically eastward")
            unwrapped[i] = unwrapped[i - 1] + step
        self._lonax = _Axis(unwrapped, "lon")

        span = self._lonax.hi - self._lonax.lo
        if span >= _TWO_PI:
            raise ValueError("lon axis wraps the globe more than once")
        self._wrap_gap = (self._lonax.lo + _TWO_PI) - self._lonax.hi
        if lon_periodic is None:
            mean_step = span / (self._lonax.n - 1) if self._lonax.n > 1 else _TWO_PI
            # Global iff closing the axis costs about one more cell.
            self._periodic = bool(self._lonax.n > 1 and self._wrap_gap < 1.5 * mean_step)
        else:
            self._periodic = bool(lon_periodic)

        shape = (self._tax.n, self._latax.n, self._lonax.n)
        self._cu = self._store(cu, shape, "cu")
        self._cv = self._store(cv, shape, "cv")
        self._wu = self._store(wu, shape, "wu")
        self._wv = self._store(wv, shape, "wv")
        self._hs = self._store(hs, shape, "hs")
        self._tp = self._store(tp, shape, "tp")
        if mu_w is None:
            self._mu_sin = None
            self._mu_cos = None
        else:
            m = self._store(mu_w, shape, "mu_w")
            self._mu_sin = self._freeze(np.sin(m))
            self._mu_cos = self._freeze(np.cos(m))
        self._depth = self._store(depth, (self._latax.n, self._lonax.n), "depth")
        self._base = base

    # ---------------------------------------------------------------- construction
    @staticmethod
    def _freeze(a: np.ndarray) -> np.ndarray:
        a = np.ascontiguousarray(a, dtype=float)
        a.setflags(write=False)
        return a

    def _store(self, a: Optional[np.ndarray], shape: Tuple[int, ...],
               name: str) -> Optional[np.ndarray]:
        """Copy, validate the shape, and mark read-only.

        The copy is not defensive pedantry: a caller who keeps a handle on the array it
        passed in and mutates it later would make `at` non-repeatable, which invalidates the
        causality argument the sweep rests on (see types.py, EnvField).
        """
        if a is None:
            return None
        arr = np.array(a, dtype=float, copy=True)
        if arr.shape != shape:
            raise ValueError(f"{name} has shape {arr.shape}, expected {shape}")
        if not np.all(np.isfinite(arr)):
            raise ValueError(f"{name} contains non-finite values; mask them before loading")
        arr.setflags(write=False)
        return arr

    # ---------------------------------------------------------------- lookup
    @property
    def t0(self) -> float:
        return self._tax.lo

    @property
    def horizon(self) -> float:
        return self._tax.hi

    @property
    def lon_periodic(self) -> bool:
        return self._periodic

    def bounds(self) -> Tuple[float, float, float, float]:
        """(lat_min, lat_max, lon_min, lon_max) in radians, longitudes unwrapped."""
        return self._latax.lo, self._latax.hi, self._lonax.lo, self._lonax.hi

    def _locate_lon(self, lon: float) -> Tuple[int, int, float, bool]:
        ax = self._lonax
        if ax.n == 1:
            return 0, 0, 0.0, False
        # Representative of `lon` in [lon0, lon0 + 2 pi): this is where antimeridian
        # handling actually happens, and it is two lines because the axis was unwrapped.
        x = ax.lo + math.fmod(math.fmod(lon - ax.lo, _TWO_PI) + _TWO_PI, _TWO_PI)
        if x >= ax.hi:
            if self._periodic:
                return ax.n - 1, 0, (x - ax.hi) / self._wrap_gap, False
            # Regional grid: the query is in the gap behind the grid. Clamp to whichever
            # edge is nearer in true angular distance, not in axis coordinate.
            if (ax.lo + _TWO_PI) - x < x - ax.hi:
                return 0, 1, 0.0, True
            return ax.n - 2, ax.n - 1, 1.0, True
        return ax.locate(x)

    def at(self, lat: float, lon: float, t: float) -> Env:
        return self.at_flagged(lat, lon, t)[0]

    def at_flagged(self, lat: float, lon: float, t: float) -> Tuple[Env, SampleFlags]:
        it0, it1, wt, ct = self._tax.locate(t)
        ia0, ia1, wa, ca = self._latax.locate(lat)
        io0, io1, wo, co = self._locate_lon(lon)

        w1t, w1a, w1o = 1.0 - wt, 1.0 - wa, 1.0 - wo
        w000 = w1t * w1a * w1o
        w001 = w1t * w1a * wo
        w010 = w1t * wa * w1o
        w011 = w1t * wa * wo
        w100 = wt * w1a * w1o
        w101 = wt * w1a * wo
        w110 = wt * wa * w1o
        w111 = wt * wa * wo

        def tri(a: Optional[np.ndarray], fallback: float) -> float:
            if a is None:
                return fallback
            return float(a[it0, ia0, io0] * w000 + a[it0, ia0, io1] * w001
                         + a[it0, ia1, io0] * w010 + a[it0, ia1, io1] * w011
                         + a[it1, ia0, io0] * w100 + a[it1, ia0, io1] * w101
                         + a[it1, ia1, io0] * w110 + a[it1, ia1, io1] * w111)

        b = self._base
        cu = tri(self._cu, b.cu)
        cv = tri(self._cv, b.cv)
        wu = tri(self._wu, b.wu)
        wv = tri(self._wv, b.wv)
        hs = max(0.0, tri(self._hs, b.hs))
        # tp floors at 0.1 s: a zero here would be a hole in the input, and Env.wave_omega_p
        # would then hand the seakeeping layer a 6000 rad/s encounter frequency.
        tp = max(0.1, tri(self._tp, b.tp))

        if self._mu_sin is None:
            mu = b.mu_w
        else:
            s = tri(self._mu_sin, 0.0)
            c = tri(self._mu_cos, 1.0)
            # Both components vanish only when opposing directions cancel exactly, which
            # means the cell has no defined mean direction; fall back rather than atan2(0,0).
            mu = b.mu_w if (s * s + c * c) < 1e-12 else math.atan2(s, c)

        if self._depth is None:
            depth = b.depth
        else:
            d = self._depth
            depth = float(d[ia0, io0] * w1a * w1o + d[ia0, io1] * w1a * wo
                          + d[ia1, io0] * wa * w1o + d[ia1, io1] * wa * wo)

        flags = SampleFlags(clamped_space=bool(ca or co),
                            clamped_time=bool(ct),
                            beyond_horizon=bool(t > self._tax.hi))
        return Env(cu=cu, cv=cv, wu=wu, wv=wv, hs=hs, tp=tp, mu_w=mu, depth=depth), flags


# ============================================================================ synthetic
class SyntheticIndianOcean(EnvField):
    """A reproducible Indian Ocean scenario: boundary jet + monsoon swell + cyclone.

    This is not a model output and does not pretend to be. It is a closed-form field chosen
    so that (i) every feature has a location and an amplitude a reader can check against the
    literature, (ii) the whole thing is reproducible from an integer seed, and (iii) the
    features are the ones that make routing hard -- a narrow fast current the route wants to
    ride, a broad swell field that penalises one heading band, and a moving hazard whose
    avoidance decision depends on *when* you get there, which is what forces the
    time-dependent formulation instead of a static graph.

    Components
      * Somali-Current-like western boundary jet. Axis near 51.5 E with a seeded meander of
        about a third of a degree; cross-shore Gaussian of 120 km e-folding width; 2.5 m/s
        peak, which is at the lower end of the observed Great Whirl (2-3.5 m/s in the
        southwest monsoon). Flows north, turning offshore to the east north of about 9 N,
        as the real current does at Socotra. The turn rotates the velocity without touching
        its magnitude, so the cross-shore speed maximum sits exactly on the axis at every
        latitude -- which is what the self-test asserts.
      * Mesoscale eddies as a random-phase streamfunction, so the eddy field is
        nondivergent in the tangent plane by construction rather than by luck. Amplitudes
        give 0.10-0.30 m/s; the phases propagate west at 0.05 m/s (Rossby-like).
      * Southwest monsoon wind with a Findlater-jet enhancement over the same coastal band,
        7 m/s background rising to about 14 m/s in the core.
      * Waves as three superposed systems -- local wind sea, a southern-ocean swell of about
        1.2 m at 14 s, and the cyclone's own sea. Wind seas use the fully-developed SMB
        relation Hs = 0.021 U^2 rolled off by a tanh saturating at 14 m: the unsaturated
        form gives 36 m under a 42 m/s vortex, which no sea ever reaches because a compact
        moving storm is fetch- and duration-limited. The three combine by energy (Hs adds in
        quadrature), the mean direction is the energy-weighted vector mean, and Tp is that
        of the most energetic system, which is what a peak period means.
      * A translating tropical cyclone driven by `RankineVortexField`: 42 m/s peak wind at a
        60 km radius of maximum winds, 0.35 rad of boundary-layer inflow, cyclonic, tracking
        west-northwest across the Arabian Sea at 4 m/s from 14 N 68 E. An outer Gaussian
        envelope of 600 km is applied on top of the Rankine tail, because a bare 1/r exterior
        would still be blowing 2.5 m/s a thousand kilometres away and would contaminate the
        whole basin. Past about four days the track reaches the Omani coast; no land mask is
        applied and none should be, because the navigable domain Omega is a separate object
        in CONTRACT.md section 1 and the caller owns it. `EnvField` answers everywhere.
      * Bathymetry is a caricature: 4000 m abyssal, tapering to 200 m within about 150 km of
        two straight coast proxies (the African coast at 42 E, the Indian west coast at
        73 E north of 8 N). It is here so the under-keel ban has something to bite on. Load
        a `GriddedField` from GEBCO for anything real.

    Determinism: the generator is used only in `__init__`. See the module docstring.
    """

    def __init__(self, seed: int = 20260814, t0: float = 0.0,
                 horizon: Optional[float] = None, n_eddies: int = 6) -> None:
        self._seed = int(seed)
        self._t0 = float(t0)
        self._horizon = _resolve_horizon(self._t0, horizon)
        rng = np.random.default_rng(self._seed)

        # --- eddies: psi = sum A_k sin(kx e + ky n + phi_k + om_k (t - t0))
        eddies = []
        for _ in range(int(n_eddies)):
            wavelength = float(rng.uniform(300e3, 900e3))
            k = _TWO_PI / wavelength
            bearing = float(rng.uniform(0.0, _TWO_PI))
            kx, ky = k * math.sin(bearing), k * math.cos(bearing)
            speed = float(rng.uniform(0.10, 0.30))
            amp = speed / k                     # |grad psi| ~ A k, so A = U / k
            phase = float(rng.uniform(0.0, _TWO_PI))
            omega = kx * 0.05                   # westward phase propagation at 5 cm/s
            eddies.append((amp, kx, ky, phase, omega))
        self._eddies: Tuple[Tuple[float, float, float, float, float], ...] = tuple(eddies)

        self._meander_phase = float(rng.uniform(0.0, _TWO_PI))
        self._season_phase = float(rng.uniform(0.0, _TWO_PI))

        # --- fixed scenario geometry (radians / SI)
        self._lat_ref, self._lon_ref = 8.0 * _DEG, 70.0 * _DEG
        self._jet_lon0 = 51.5 * _DEG
        self._jet_lat0 = 5.0 * _DEG
        self._jet_lat_w = 9.0 * _DEG
        self._jet_width = 120e3
        self._jet_vmax = 2.5
        self._meander_amp = 0.35 * _DEG
        self._meander_klat = _TWO_PI / (11.0 * _DEG)
        self._turn_lat = 9.0 * _DEG
        self._turn_w = 2.0 * _DEG
        self._turn_max = 1.1                    # radians east of north, far north

        track = 300.0 * _DEG                    # west-northwest
        self._cyclone = RankineVortexField(
            lat_c=14.0 * _DEG, lon_c=68.0 * _DEG, a_m=60e3, v_max=42.0,
            sign=1.0, inflow=0.35,
            drift_east=4.0 * math.sin(track),
            drift_north=4.0 * math.cos(track),
            t0=self._t0, horizon=self._horizon)
        self._cyc_envelope = 600e3
        self._hs_sat = 14.0                     # saturating sea state, see class docstring

    # ---------------------------------------------------------------- accessors
    @property
    def t0(self) -> float:
        return self._t0

    @property
    def horizon(self) -> float:
        return self._horizon

    @property
    def seed(self) -> int:
        return self._seed

    def bounds(self) -> Tuple[float, float, float, float]:
        """Advisory (lat_min, lat_max, lon_min, lon_max) in radians. The field is defined
        outside this box too; the box is where the scenario is interesting."""
        return -10.0 * _DEG, 25.0 * _DEG, 40.0 * _DEG, 100.0 * _DEG

    def jet_axis_lon(self, lat: float) -> float:
        """Longitude of the boundary-current axis at this latitude, radians."""
        return self._jet_lon0 + self._meander_amp * math.sin(
            self._meander_klat * (lat - self._jet_lat0) + self._meander_phase)

    def cyclone_centre(self, t: float) -> Tuple[float, float]:
        """(lat, lon) of the cyclone centre in radians, persisted past the horizon."""
        return self._cyclone.centre_at(self._clamp_t(t))

    @property
    def cyclone_bearing(self) -> float:
        """Heading the storm is tracking on, radians. Constant by construction."""
        return self._cyclone.drift_bearing

    def _clamp_t(self, t: float) -> float:
        return min(max(t, self._t0), self._horizon)

    # ---------------------------------------------------------------- components
    def _season(self, t: float) -> float:
        """Slow monsoon modulation, +-15% over ten days. Small on purpose: the point is to
        make the field genuinely time-dependent (so L_t > 0 and Thm 3.1 has something to
        say) without a synoptic swing that would swamp the cyclone."""
        return 1.0 + 0.15 * math.sin(_TWO_PI * (t - self._t0) / (10.0 * 86400.0)
                                     + self._season_phase)

    def _jet(self, lat: float, lon: float, t: float) -> Tuple[float, float, float]:
        """-> (cu, cv, gaussian) for the boundary current. The Gaussian is returned because
        the wind's Findlater enhancement rides the same coastal band."""
        cross, _ = local_step_metres(lat, 0.0, lon - self.jet_axis_lon(lat))
        g = math.exp(-(cross / self._jet_width) ** 2)
        band = math.exp(-((lat - self._jet_lat0) / self._jet_lat_w) ** 2)
        speed = self._jet_vmax * g * band * self._season(t)
        # Turn offshore north of _turn_lat. This rotates the vector and leaves |v| alone,
        # so the cross-shore speed maximum stays exactly on the axis.
        s = (lat - self._turn_lat) / self._turn_w
        turn = self._turn_max / (1.0 + math.exp(-s)) if abs(s) < 700.0 else (
            self._turn_max if s > 0 else 0.0)
        return speed * math.sin(turn), speed * math.cos(turn), g * band

    def _eddy(self, lat: float, lon: float, t: float) -> Tuple[float, float]:
        e, n = local_step_metres(0.5 * (lat + self._lat_ref),
                                 lat - self._lat_ref, lon - self._lon_ref)
        dt = t - self._t0
        ue = 0.0
        vn = 0.0
        for amp, kx, ky, phase, omega in self._eddies:
            c = math.cos(kx * e + ky * n + phase + omega * dt)
            ue -= amp * ky * c       # u = -d(psi)/dN
            vn += amp * kx * c       # v = +d(psi)/dE
        return ue, vn

    def _monsoon_wind(self, lat: float, lon: float, t: float,
                      coastal: float) -> Tuple[float, float]:
        speed = (7.0 + 7.0 * coastal) * self._season(t)
        # Towards the northeast, veering with latitude: the cross-equatorial flow arrives
        # from the southeast and turns southwesterly as it crosses into the north.
        theta = 0.70 + 0.25 * math.tanh(lat / (10.0 * _DEG))
        return speed * math.sin(theta), speed * math.cos(theta)

    def _wind_sea(self, u: float) -> float:
        """Significant height of the wind sea for a 10 m wind of u m/s.

        Fully-developed SMB growth Hs = 0.021 u^2 (Sverdrup-Munk-Bretschneider, as tabulated
        in CEM 2002) rolled off by tanh to saturate at `_hs_sat`. Without the roll-off the
        42 m/s cyclone returns 36 m, which is roughly twice the largest sea ever measured;
        the roll-off stands in for the fetch and duration limits that a 60 km storm moving
        at 4 m/s imposes on its own sea. Below about 20 m/s the two forms agree to 3%.
        """
        if u <= 0.0:
            return 0.0
        return self._hs_sat * math.tanh(0.021 * u * u / self._hs_sat)

    def _depth(self, lat: float, lon: float) -> float:
        coslat = math.cos(lat)
        d_afr = abs(R_E * coslat * wrap_pi(lon - 42.0 * _DEG))
        if lat > 8.0 * _DEG:
            d_ind = abs(R_E * coslat * wrap_pi(lon - 73.0 * _DEG))
        else:
            d_ind = 1e9
        shelf = 150e3
        f = ((1.0 - math.exp(-(d_afr / shelf) ** 2))
             * (1.0 - math.exp(-(min(d_ind, 1e7) / shelf) ** 2)))
        return 200.0 + 3800.0 * f

    # ---------------------------------------------------------------- sampling
    def at(self, lat: float, lon: float, t: float) -> Env:
        return self.at_flagged(lat, lon, t)[0]

    def at_flagged(self, lat: float, lon: float, t: float) -> Tuple[Env, SampleFlags]:
        tq = self._clamp_t(t)
        flags = SampleFlags(clamped_space=False,
                            clamped_time=(t < self._t0 or t > self._horizon),
                            beyond_horizon=(t > self._horizon))

        jet_u, jet_v, coastal = self._jet(lat, lon, tq)
        edd_u, edd_v = self._eddy(lat, lon, tq)
        wu_m, wv_m = self._monsoon_wind(lat, lon, tq, coastal)

        # --- cyclone winds, with an outer envelope on the Rankine 1/r tail
        r = self._cyclone.radius_at(lat, lon, tq)
        env_c = math.exp(-(r / self._cyc_envelope) ** 2)
        if env_c > 1e-4:
            cwu, cwv = self._cyclone.velocity_at(lat, lon, tq)
            cwu *= env_c
            cwv *= env_c
        else:
            cwu = cwv = 0.0
        wu = wu_m + cwu
        wv = wv_m + cwv

        # Wind-driven surface current under the storm: 2.5% of the wind, deflected 20 deg
        # to the right (northern-hemisphere Ekman surface deflection).
        ca, sa = math.cos(-0.35), math.sin(-0.35)
        cyc_cu = 0.025 * (cwu * ca - cwv * sa)
        cyc_cv = 0.025 * (cwu * sa + cwv * ca)

        cu = jet_u + edd_u + cyc_cu
        cv = jet_v + edd_v + cyc_cv

        # --- wave systems: (hs, tp, direction-towards)
        u_mon = math.hypot(wu_m, wv_m)
        hs_sea = self._wind_sea(u_mon)
        mu_sea = vec_to_heading(wu_m, wv_m) - 0.15      # sea lags the wind slightly

        hs_swell = 1.2 * math.exp(-((lat - (-5.0 * _DEG)) / (25.0 * _DEG)) ** 2) + 0.4
        mu_swell = 20.0 * _DEG

        u_cyc = math.hypot(cwu, cwv)
        hs_cyc = self._wind_sea(u_cyc)
        # The storm sea runs out ahead of the wind vector; direction of translation is the
        # honest simple choice and is right in the dangerous semicircle, wrong behind.
        mu_cyc = self._cyclone.drift_bearing if u_cyc > 0.0 else 0.0

        systems = ((hs_sea, max(4.0, 4.3 * math.sqrt(max(hs_sea, 0.0))), mu_sea),
                   (hs_swell, 14.0, mu_swell),
                   (hs_cyc, max(4.0, 4.6 * math.sqrt(max(hs_cyc, 0.0))), mu_cyc))
        e_tot = 0.0
        se = ce = 0.0
        tp_dom = 8.0
        e_dom = -1.0
        for h, tp_i, mu_i in systems:
            e = h * h
            if e <= 0.0:
                continue
            e_tot += e
            se += e * math.sin(mu_i)
            ce += e * math.cos(mu_i)
            if e > e_dom:
                e_dom, tp_dom = e, tp_i
        hs = math.sqrt(e_tot)
        mu_w = math.atan2(se, ce) if (se * se + ce * ce) > 1e-12 else 0.0

        return Env(cu=cu, cv=cv, wu=wu, wv=wv, hs=hs, tp=tp_dom,
                   mu_w=wrap_pi(mu_w), depth=self._depth(lat, lon)), flags


# ============================================================================ diagnostics
def _stw_surrogate(vessel: Vessel, env: Env, theta: float) -> float:
    """Through-water speed at full throttle, reduced by involuntary speed loss in waves.

    A stand-in for `vessel.attainable(...)`, which lives in the vessel/seakeeping modules and
    cannot be imported here without a cycle. It reproduces only the two effects that make F
    move with time -- the heavy-weather ban and the Hs^1.7 speed loss -- and deliberately
    ignores throttle, added wind resistance and the S1-S7 detail. Pass `sigma_fn` to
    `temporal_lipschitz` once the real metric exists; that is the measurement, this is the
    smoke test.
    """
    if env.hs > vessel.hs_limit:
        return 0.0                       # heavy-weather ban: direction is infeasible
    rel = wrap_pi(env.mu_w - theta)      # 0 following, +-pi head seas
    head = max(0.0, -math.cos(rel))
    if env.hs < 2.0:
        loss = 0.0
    else:
        loss = min(0.45, 0.020 * env.hs ** 1.7 * (0.35 + 0.65 * head))
    return vessel.V_ref * (1.0 - loss)


def _sigma_surrogate(vessel: Vessel, env: Env, u: Tuple[float, float]) -> float:
    """Speed made good in unit direction u, per Def 2.3 -- the drift-corrected scalar, not
    the magnitude of the ground velocity.

    The ship steers to cancel the cross-track drift and what is left adds along track. The
    two degenerate cases are handled explicitly and both mean the same thing (F = +inf):
    the cross-track drift exceeds the ship's speed so the track cannot be held at all, or it
    can be held but the along-track sum is non-positive so the ship goes backwards.
    """
    ue, un = u
    du = env.cu + vessel.kappa_L * env.wu
    dv = env.cv + vessel.kappa_L * env.wv
    V = _stw_surrogate(vessel, env, vec_to_heading(ue, un))
    if V <= 0.0:
        return 0.0
    along = du * ue + dv * un
    cross = -du * un + dv * ue
    if abs(cross) >= V:
        return 0.0
    sog = math.sqrt(V * V - cross * cross) + along
    return sog if sog > 0.0 else 0.0


def temporal_lipschitz(field: EnvField, vessel: Vessel, lat: float, lon: float,
                       t: float, dt: float, n_dirs: int = 36,
                       sigma_fn: Optional[Callable[[Env, Tuple[float, float]], float]] = None
                       ) -> float:
    """Finite-difference estimate of L_t at one point, for the FIFO diagnostic of Thm 3.1.

    L_t bounds |dF/dt|, and Thm 3.1 requires h L_t / F_min^2 to stay below the causality
    threshold; the sweep is only licensed to be single-pass where that holds. This returns
    the worst central difference of F = 1/sigma over `n_dirs` uniformly spaced directions,
    in units of 1/m (F is s/m, so its time derivative is s/m/s).

    Return values that are not a number of the expected kind, and what they mean:

      +inf   Some direction is feasible at one endpoint and infeasible at the other -- the
             heavy-weather ban switched, or the drift crossed the ship's speed. F genuinely
             jumps to infinity there, no finite L_t exists, and the FIFO condition cannot be
             satisfied by refining h. This is the case Thm 3.3 exists for: relax with
             waiting and causality is restored unconditionally.
      0.0    Either the field is static here, or every direction is infeasible at both
             endpoints (an unreachable point, where L_t is vacuous). The caller should
             distinguish these by checking sigma itself; this function does not guess.

    Two ways this understates the truth, both deliberate. Past `field.horizon` a gridded or
    synthetic field persists its final frame, so it is constant in time and this returns
    0.0 -- that is a property of the persistence policy, not of the weather. And the
    surrogate metric ignores throttle, so it misses the time variation in the fuel-optimal
    branch of the indicatrix; pass `sigma_fn` wired to `MetricLike.sigma_max` for the real
    number.
    """
    if dt <= 0.0:
        raise ValueError("dt must be positive")
    if n_dirs < 3:
        raise ValueError("n_dirs must be at least 3")

    t_lo, t_hi = t - dt, t + dt
    if t_lo < field.t0:
        # One-sided at the departure edge rather than sampling before t0, where a gridded
        # field would clamp and silently halve the difference.
        t_lo, t_hi = t, t + dt
    span = t_hi - t_lo
    if span <= 0.0:
        raise ValueError("degenerate time span")

    sig = sigma_fn if sigma_fn is not None else (lambda e, u: _sigma_surrogate(vessel, e, u))
    e_lo = field.at(lat, lon, t_lo)
    e_hi = field.at(lat, lon, t_hi)

    worst = 0.0
    for k in range(n_dirs):
        u = heading_to_vec(_TWO_PI * k / n_dirs)
        s_lo = sig(e_lo, u)
        s_hi = sig(e_hi, u)
        if s_lo <= 0.0 or s_hi <= 0.0:
            if (s_lo <= 0.0) != (s_hi <= 0.0):
                return math.inf
            continue                     # infeasible at both ends: no finite difference
        d = abs(1.0 / s_hi - 1.0 / s_lo) / span
        if d > worst:
            worst = d
    return worst


# ============================================================================ self-test
def _selftest() -> None:
    kt = 1.0 / 0.5144444444
    print("=" * 74)
    print("SyntheticIndianOcean: transect across the western boundary jet")
    print("=" * 74)
    f = SyntheticIndianOcean(seed=20260814)
    t0 = f.t0
    lat = 6.0 * _DEG
    axis = f.jet_axis_lon(lat)
    print(f"jet axis at 6.00 N -> {axis / _DEG:7.3f} E   (seeded meander about 51.5 E)")
    print(f"{'lon E':>8} {'|c| m/s':>9} {'cu':>8} {'cv':>8} {'|c| kt':>8}")
    best_lon, best_spd = None, -1.0
    lons = [46.0 + 0.25 * i for i in range(int((58.0 - 46.0) / 0.25) + 1)]
    for lo in lons:
        e = f.at(lat, lo * _DEG, t0)
        spd = math.hypot(e.cu, e.cv)
        if spd > best_spd:
            best_spd, best_lon = spd, lo
        if abs(lo - round(lo * 2) / 2) < 1e-9 and (round(lo * 2) % 1 == 0):
            print(f"{lo:8.2f} {spd:9.3f} {e.cu:8.3f} {e.cv:8.3f} {spd * kt:8.2f}")
    print(f"\npeak |c| = {best_spd:.3f} m/s at {best_lon:.2f} E; "
          f"axis is {axis / _DEG:.3f} E; offset {abs(best_lon - axis / _DEG) * 60:.1f} nm")
    assert abs(best_lon - axis / _DEG) <= 0.25 + 1e-9, "jet peak is not on the axis"
    assert 1.5 < best_spd < 3.5, f"jet peak {best_spd} m/s is not plausible"
    far = f.at(lat, 58.0 * _DEG, t0)
    print(f"far field at 58 E: |c| = {math.hypot(far.cu, far.cv):.3f} m/s (eddies only)")

    print()
    print("=" * 74)
    print("Cyclone translation")
    print("=" * 74)
    prev = None
    for hours in (0.0, 24.0, 48.0, 72.0):
        clat, clon = f.cyclone_centre(t0 + hours * 3600.0)
        line = f"t0 + {hours:5.1f} h  centre = {clat / _DEG:7.3f} N  {clon / _DEG:8.3f} E"
        if prev is not None:
            from kairos.geodesy import haversine, initial_bearing
            d = haversine(prev[0], prev[1], clat, clon) / 1000.0
            b = initial_bearing(prev[0], prev[1], clat, clon) / _DEG % 360.0
            line += f"   moved {d:7.1f} km on {b:5.1f} deg"
        print(line)
        prev = (clat, clon)
    c0 = f.cyclone_centre(t0)
    c48 = f.cyclone_centre(t0 + 48 * 3600.0)
    assert c48[0] > c0[0] and c48[1] < c0[1], "cyclone did not track northwest"

    # wind at the radius of maximum winds, 48 h in
    clat, clon = c48
    e_eye = f.at(clat, clon, t0 + 48 * 3600.0)
    dlat_rmw = 60e3 / R_E
    e_rmw = f.at(clat + dlat_rmw, clon, t0 + 48 * 3600.0)
    e_out = f.at(clat + 8 * dlat_rmw, clon, t0 + 48 * 3600.0)
    print(f"wind |W| : eye {math.hypot(e_eye.wu, e_eye.wv):6.2f}   "
          f"r=RMW {math.hypot(e_rmw.wu, e_rmw.wv):6.2f}   "
          f"r=8RMW {math.hypot(e_out.wu, e_out.wv):6.2f}  m/s")
    print(f"Hs       : eye {e_eye.hs:6.2f}   r=RMW {e_rmw.hs:6.2f}   "
          f"r=8RMW {e_out.hs:6.2f}  m    (Tp at RMW {e_rmw.tp:.1f} s)")
    # 34 rather than 42 at the RMW because the monsoon flow opposes the cyclonic wind on
    # the poleward side; that is the correct vector sum, not a bug.
    assert math.hypot(e_rmw.wu, e_rmw.wv) > 30.0, "RMW wind too weak"
    assert math.hypot(e_eye.wu, e_eye.wv) < 20.0, "eye is not calm"
    assert 8.0 < e_rmw.hs < 16.0, f"RMW Hs {e_rmw.hs:.1f} m is not a real sea state"
    assert 10.0 < e_rmw.tp < 20.0, f"RMW Tp {e_rmw.tp:.1f} s is not plausible"

    print()
    print("=" * 74)
    print("Analytic fields")
    print("=" * 74)
    sh = LinearShearField(alpha=1.8e-6, lat0=0.0)
    for dlat_deg in (-5.0, 0.0, 5.0):
        e = sh.at(dlat_deg * _DEG, 0.0, 0.0)
        print(f"shear  lat {dlat_deg:+5.1f} deg -> cu = {e.cu:+7.3f} m/s, cv = {e.cv:+.3f}")

    v = RankineVortexField(lat_c=0.0, lon_c=0.0, a_m=100e3, v_max=1.5)
    print(f"rankine a = 100 km, v_max = 1.5 m/s, Gamma = {v.circulation:.3e} m^2/s")
    peak_r, peak_v = None, -1.0
    for r_km in (0.0, 25.0, 50.0, 75.0, 100.0, 150.0, 200.0, 400.0):
        lo = (r_km * 1000.0) / R_E
        vu, vv = v.velocity_at(0.0, lo, 0.0)
        s = math.hypot(vu, vv)
        if s > peak_v:
            peak_v, peak_r = s, r_km
        print(f"       r = {r_km:6.1f} km -> |v| = {s:6.3f}  (east {vu:+6.3f}, "
              f"north {vv:+6.3f})")
    assert peak_r == 100.0 and abs(peak_v - 1.5) < 1e-9, "Rankine peak is not at r = a"
    assert abs(math.hypot(*v.velocity_at(0.0, 0.0, 0.0))) == 0.0, "eye not exactly zero"

    print()
    print("=" * 74)
    print("GriddedField: antimeridian, clamping, horizon")
    print("=" * 74)
    times = [0.0, 3600.0, 7200.0]
    lats = [d * _DEG for d in (-2.0, 0.0, 2.0)]
    lons = [wrap_pi(d * _DEG) for d in (175.0, 177.5, 180.0, 182.5, 185.0)]
    print("lon axis as given (deg):", [round(l / _DEG, 1) for l in lons])
    shape = (3, 3, 5)
    cu = np.zeros(shape)
    cv = np.zeros(shape)
    for i in range(5):
        cu[:, :, i] = float(i)                       # ramps 0..4 across the seam
    cv[2, :, :] = 2.0                                # last frame differs, to test persist
    hs = np.full(shape, 3.0)
    mu = np.full(shape, math.pi - 0.05)              # near the +-pi seam
    mu[:, :, 3:] = -math.pi + 0.05
    g = GriddedField(times, lats, lons, cu, cv, hs=hs, mu_w=mu)
    print(f"periodic = {g.lon_periodic}  (regional grid, expected False)")
    print(f"t0 = {g.t0}  horizon = {g.horizon}")
    for lon_deg in (176.25, 179.0, 180.0, 181.0, 183.75):
        e, fl = g.at_flagged(0.0, wrap_pi(lon_deg * _DEG), 1800.0)
        print(f"  lon {lon_deg:7.2f} -> cu = {e.cu:5.2f}  mu_w = {e.mu_w / _DEG:+8.2f} deg"
              f"  flags(space={fl.clamped_space}, time={fl.clamped_time})")
    e, fl = g.at_flagged(0.0, wrap_pi(170.0 * _DEG), 1800.0)
    print(f"  lon  170.00 -> cu = {e.cu:5.2f}  clamped_space = {fl.clamped_space} "
          f"(expect True, cu = 0)")
    assert fl.clamped_space and e.cu == 0.0
    e, fl = g.at_flagged(9.0 * _DEG, wrap_pi(180.0 * _DEG), 1800.0)
    assert fl.clamped_space, "lat clamp not flagged"
    e_h, fl_h = g.at_flagged(0.0, wrap_pi(180.0 * _DEG), 99999.0)
    e_e, _ = g.at_flagged(0.0, wrap_pi(180.0 * _DEG), 7200.0)
    print(f"  t = 99999 s -> cv = {e_h.cv:.2f} (final frame cv = {e_e.cv:.2f}), "
          f"beyond_horizon = {fl_h.beyond_horizon}, clamped_time = {fl_h.clamped_time}")
    assert fl_h.beyond_horizon and e_h.cv == e_e.cv
    # mu_w interpolation must cross the seam without touching zero
    e_seam, _ = g.at_flagged(0.0, wrap_pi(181.25 * _DEG), 0.0)
    print(f"  seam mu_w at 181.25 E = {e_seam.mu_w / _DEG:+.3f} deg "
          f"(linear averaging would give 0.0)")
    assert abs(abs(e_seam.mu_w) - math.pi) < 1e-9

    glons = [wrap_pi(d * _DEG) for d in range(0, 360, 45)]
    gg = GriddedField([0.0, 3600.0], lats, glons,
                      np.zeros((2, 3, 8)), np.zeros((2, 3, 8)))
    print(f"global grid (0..315 E step 45): periodic = {gg.lon_periodic} (expect True)")
    assert gg.lon_periodic

    print()
    print("=" * 74)
    print("temporal_lipschitz")
    print("=" * 74)
    ves = Vessel()
    print(f"vessel V_ref = {ves.V_ref:.3f} m/s ({ves.V_ref * kt:.1f} kt), "
          f"hs_limit = {ves.hs_limit} m")
    uni = UniformField(Env(cu=0.5, cv=0.0, hs=2.0))
    print(f"  uniform field                  L_t = "
          f"{temporal_lipschitz(uni, ves, 0.0, 0.0, 3600.0, 600.0):.3e} 1/m (expect 0)")
    for name, la, lo in (("open ocean 8N 65E", 8.0, 65.0),
                         ("in the jet 6N", 6.0, axis / _DEG),
                         ("cyclone approach 16N 62E", 16.0, 62.0)):
        L = temporal_lipschitz(f, ves, la * _DEG, lo * _DEG, t0 + 36 * 3600.0, 1800.0)
        e = f.at(la * _DEG, lo * _DEG, t0 + 36 * 3600.0)
        print(f"  {name:30s} L_t = {L:.3e} 1/m   (Hs {e.hs:4.2f} m, "
              f"|c| {math.hypot(e.cu, e.cv):4.2f} m/s)")
    print(f"  {'persisted, t = horizon + 1 d':30s} L_t = "
          f"{temporal_lipschitz(f, ves, 8 * _DEG, 65 * _DEG, f.horizon + 86400.0, 1800.0):.3e}"
          f" 1/m (expect 0)")

    # Radial scan ahead of the storm at 48 h. Three regimes must appear in order: finite
    # L_t outside, +inf where the Hs > hs_limit ban switches between the two endpoints, and
    # 0.0 inside where every direction is banned at both endpoints (vacuous, NOT static).
    print("\n  radial scan along the track, 48 h -- the three regimes of L_t:")
    t48 = t0 + 48 * 3600.0
    clat48, clon48 = f.cyclone_centre(t48)
    brg = f.cyclone_bearing
    saw_inf = saw_vacuous = False
    for r_km in (300.0, 200.0, 160.0, 140.0, 130.0, 120.0, 100.0, 60.0, 20.0):
        pla, plo = destination(clat48, clon48, brg, r_km * 1000.0)
        L = temporal_lipschitz(f, ves, pla, plo, t48, 1800.0)
        e = f.at(pla, plo, t48)
        feasible = _sigma_surrogate(ves, e, heading_to_vec(brg)) > 0.0
        tag = ("finite" if math.isfinite(L) and L > 0.0 else
               ("+inf: ban switches (Thm 3.3)" if math.isinf(L) else
                ("0.0: vacuous, all dirs banned" if not feasible else "0.0: static")))
        saw_inf |= math.isinf(L)
        saw_vacuous |= (L == 0.0 and not feasible)
        print(f"    r = {r_km:6.1f} km  Hs = {e.hs:5.2f} m  L_t = {L:10.3e}  {tag}")
    assert saw_inf, "the +inf branch of temporal_lipschitz was never exercised"
    assert saw_vacuous, "the vacuous branch was never exercised"

    print()
    print("all assertions passed")


if __name__ == "__main__":
    _selftest()
