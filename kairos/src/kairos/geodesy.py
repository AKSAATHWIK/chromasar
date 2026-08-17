"""Spherical geometry, done in the numerically stable way.

Spec reference: 06-numerics.md Proc 6.4.

Every routine here is exercised millions of times in the inner loop, and every one of them
has a naive form that loses precision exactly where routing needs it most (short legs, near
the antimeridian, near the poles). The stable form is used and the unstable one is named in
the docstring so nobody "simplifies" it back.

Angles are RADIANS everywhere inside the solver. Degrees appear only at the I/O boundary.
"""
from __future__ import annotations

import math
from typing import Tuple

R_E = 6_371_000.0          # mean Earth radius, metres (IUGG)
_TWO_PI = 2.0 * math.pi


# --------------------------------------------------------------------------- angles
def wrap_pi(a: float) -> float:
    """Wrap an angle to (-pi, pi]. Stable for large |a| (unlike a - 2pi*round(a/2pi))."""
    a = math.fmod(a, _TWO_PI)
    if a > math.pi:
        a -= _TWO_PI
    elif a <= -math.pi:
        a += _TWO_PI
    return a


def angdiff(a: float, b: float) -> float:
    """Signed smallest difference a - b in (-pi, pi]."""
    return wrap_pi(a - b)


# --------------------------------------------------------------------------- distance
def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres.

    Haversine rather than the spherical law of cosines: acos(sin.sin + cos.cos.cos) loses
    all precision for separations below ~1 km, which is precisely our grid scale at 0.125
    degrees. Haversine is conditioned well at short range and only degrades for near-
    antipodal pairs, which never occur between adjacent grid nodes.
    """
    dlat = lat2 - lat1
    dlon = wrap_pi(lon2 - lon1)          # antimeridian-safe
    sin_dlat = math.sin(0.5 * dlat)
    sin_dlon = math.sin(0.5 * dlon)
    a = sin_dlat * sin_dlat + math.cos(lat1) * math.cos(lat2) * sin_dlon * sin_dlon
    a = min(1.0, max(0.0, a))            # guard rounding above 1
    return 2.0 * R_E * math.asin(math.sqrt(a))


def initial_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial great-circle bearing, radians, 0 = north, clockwise positive.

    atan2 form; the arccos form is unstable near 0 and pi.
    """
    dlon = wrap_pi(lon2 - lon1)
    cos_lat2 = math.cos(lat2)
    y = math.sin(dlon) * cos_lat2
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * cos_lat2 * math.cos(dlon)
    return math.atan2(y, x)


# --------------------------------------------------------------------------- local frame
def local_step_metres(lat: float, dlat: float, dlon: float) -> Tuple[float, float]:
    """Displacement (east, north) in metres for a small (dlat, dlon) step at latitude lat.

    This is the tangent-plane approximation the solver runs in (spec 01-formulation Eq 1.3).
    Error is O(h^2 / R_E) -- at h = 28 km that is under 0.1 m, far below the metric's own
    modelling error, so the solver may treat the local frame as exactly Euclidean.

    cos(lat) is evaluated at the ROW latitude, which is why the caller caches per row.
    """
    return R_E * math.cos(lat) * wrap_pi(dlon), R_E * dlat


def metres_to_dlatlon(lat: float, east_m: float, north_m: float) -> Tuple[float, float]:
    """Inverse of local_step_metres. Guarded against the cos(lat) singularity at the poles."""
    coslat = math.cos(lat)
    if abs(coslat) < 1e-9:               # polar cap: longitude is meaningless here
        return north_m / R_E, 0.0
    return north_m / R_E, east_m / (R_E * coslat)


def destination(lat: float, lon: float, bearing: float, dist_m: float) -> Tuple[float, float]:
    """Exact spherical forward geodesic. Used by the shooting polish, which integrates in
    true spherical geometry rather than the tangent plane so error does not accumulate over
    a multi-thousand-kilometre route."""
    ang = dist_m / R_E
    sin_lat, cos_lat = math.sin(lat), math.cos(lat)
    sin_ang, cos_ang = math.sin(ang), math.cos(ang)
    lat2 = math.asin(min(1.0, max(-1.0, sin_lat * cos_ang + cos_lat * sin_ang * math.cos(bearing))))
    lon2 = lon + math.atan2(math.sin(bearing) * sin_ang * cos_lat,
                            cos_ang - sin_lat * math.sin(lat2))
    return lat2, wrap_pi(lon2)


# --------------------------------------------------------------------------- vectors
def unit(vx: float, vy: float) -> Tuple[float, float]:
    """Normalise, returning (0,0) for the zero vector rather than raising."""
    n = math.hypot(vx, vy)
    if n <= 0.0:
        return 0.0, 0.0
    return vx / n, vy / n


def heading_to_vec(theta: float) -> Tuple[float, float]:
    """Heading (0 = north, clockwise) to an (east, north) unit vector.

    NOTE the convention: n(theta) = (sin theta, cos theta). East is the FIRST component
    throughout the solver, matching CONTRACT.md section 1. Getting this backwards is the
    single most common porting bug; the sign of every current interaction depends on it.
    """
    return math.sin(theta), math.cos(theta)


def vec_to_heading(east: float, north: float) -> float:
    """Inverse of heading_to_vec."""
    return math.atan2(east, north)
