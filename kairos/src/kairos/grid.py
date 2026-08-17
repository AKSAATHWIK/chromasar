"""Discretisation and land mask: the lattice the front propagates over.

Spec reference: CONTRACT.md section 4 (a); design decision D5 for `CoarseGrid`.

Two things in here are normative and must be reproduced exactly by any port:

  1. Node indexing is `n = i * nlon + j`, i = latitude row (south to north), j = longitude
     column (west to east). Every array the solver allocates -- values, labels, bucket
     membership -- is a flat array of length `n` in this order. Row-major in j means a
     latitude row is contiguous, which is what the ordered-upwind stencil sweeps.
  2. The neighbourhood template within a radius depends ONLY on the row, because the
     sphere is invariant under rotation about its axis: the distance from (i, j) to
     (i + di, j + dj) is independent of j. That invariance is the whole reason the
     stencil is affordable -- it turns a per-node O(r^2) geometric query into a per-row
     table lookup, and the OUM stencil radius (Upsilon * h) is large enough that the
     difference matters by two orders of magnitude.

Degrees appear in the constructor and in `land_fn`, because that is where data arrives
from the outside. Everything else is radians, per geodesy.py.
"""
from __future__ import annotations

import math
import warnings
from typing import Callable, Iterator, List, Optional, Tuple

import numpy as np

from .geodesy import R_E, haversine, wrap_pi

DEG = math.pi / 180.0
_TWO_PI = 2.0 * math.pi

#: `is_land(lat_deg, lon_deg) -> bool`. Scalars must work; arrays are used when supported.
LandFn = Callable[..., bool]

# Templates are keyed by (row, radius). A caller that varies the radius continuously --
# a locally adaptive stencil driven by Upsilon_loc does exactly that -- would otherwise
# grow the cache without bound. Beyond this many entries we drop it and start again;
# the rebuild is O(template size), not O(n).
_MAX_TEMPLATE_CACHE = 8192


class Grid:
    """Uniform lat/lon lattice with a boolean water mask.

    The lattice is *node*-centred: node (i, j) sits at latitude `lat_min + i*step` and
    longitude `lon_min + j*step`, and both bounds are inclusive. `step_deg` divides the
    span; if it does not, the span is rounded to the nearest whole number of cells and
    `lat_max`/`lon_max` are moved accordingly (the effective bounds are readable as
    `lat_max_deg`, `lon_max_deg` after construction).

    The tangent-plane metric this grid feeds (Eq 1.3) is only valid while a cell is small
    against the Earth's radius, so `step_deg` above a few degrees is outside the model's
    validity, not merely coarse.
    """

    __slots__ = (
        "lat_min_deg", "lat_max_deg", "lon_min_deg", "lon_max_deg", "step_deg",
        "nlat", "nlon", "n", "land_known",
        "_lat", "_lon", "_lat_deg", "_lon_deg", "_dlat", "_dlon",
        "_east_m", "_north_m", "_lon_wraps", "_water", "_tmpl",
    )

    def __init__(self,
                 lat_min: float,
                 lat_max: float,
                 lon_min: float,
                 lon_max: float,
                 step_deg: float,
                 land_fn: Optional[LandFn] = None,
                 water_mask: Optional[np.ndarray] = None) -> None:
        if step_deg <= 0.0:
            raise ValueError(f"step_deg must be positive, got {step_deg}")
        if lat_max < lat_min:
            raise ValueError(f"lat_max {lat_max} below lat_min {lat_min}")
        if lon_max < lon_min:
            raise ValueError(f"lon_max {lon_max} below lon_min {lon_min}")
        if lat_min < -90.0 or lat_max > 90.0:
            raise ValueError(f"latitude bounds {lat_min}..{lat_max} outside [-90, 90]")
        if lon_max - lon_min > 360.0:
            raise ValueError(f"longitude span {lon_max - lon_min} exceeds 360 degrees")

        self.step_deg = float(step_deg)
        self.lat_min_deg = float(lat_min)
        self.lon_min_deg = float(lon_min)
        self.nlat = int(round((lat_max - lat_min) / step_deg)) + 1
        self.nlon = int(round((lon_max - lon_min) / step_deg)) + 1
        if self.nlat < 2 or self.nlon < 2:
            raise ValueError(f"grid too small: {self.nlat} x {self.nlon} nodes")
        self.lat_max_deg = self.lat_min_deg + (self.nlat - 1) * self.step_deg
        self.lon_max_deg = self.lon_min_deg + (self.nlon - 1) * self.step_deg
        self.n = self.nlat * self.nlon

        self._lat_deg = self.lat_min_deg + self.step_deg * np.arange(self.nlat)
        self._lon_deg = self.lon_min_deg + self.step_deg * np.arange(self.nlon)
        self._lat = self._lat_deg * DEG
        self._lon = self._lon_deg * DEG
        self._dlat = self.step_deg * DEG
        self._dlon = self.step_deg * DEG

        # A domain whose columns close the full circle must wrap in j, or the solver
        # refuses to route across the antimeridian for no physical reason.
        self._lon_wraps = abs(self.nlon * self._dlon - _TWO_PI) < 1e-9

        # Per-row spacing, computed once. cos(lat) is the only row-dependent term
        # (geodesy.local_step_metres), so this is the complete cache.
        self._east_m = R_E * np.cos(self._lat) * self._dlon
        self._north_m = R_E * self._dlat

        self._tmpl: dict = {}
        self.land_known = True
        if water_mask is not None:
            if water_mask.shape != (self.nlat, self.nlon):
                raise ValueError(f"water_mask shape {water_mask.shape} != "
                                 f"{(self.nlat, self.nlon)}")
            self._water = np.ascontiguousarray(water_mask, dtype=bool)
        elif land_fn is None:
            self.land_known = False
            self._water = np.ones((self.nlat, self.nlon), dtype=bool)
            warnings.warn(
                "Grid built with no land_fn: every node is treated as navigable water, "
                "so routes may cross continents. Pass land_fn=global_land_mask.is_land "
                "(pip install global-land-mask) or a bathymetry-derived mask.",
                RuntimeWarning, stacklevel=2)
        else:
            self._water = self._build_mask(land_fn)

    # ------------------------------------------------------------------ construction
    def _build_mask(self, land_fn: LandFn) -> np.ndarray:
        """Evaluate `land_fn` over every node, row by row.

        Row-at-a-time rather than one big meshgrid: it bounds peak memory at O(nlon) and
        it lets an array-capable `land_fn` (global_land_mask.is_land, a rasterised
        shapefile lookup) be used without the caller having to declare that it is.
        Longitudes are wrapped to (-180, 180] first because that is what land datasets
        expect, and a domain spanning the antimeridian will otherwise index off the end.
        """
        lon_deg = np.degrees(np.array([wrap_pi(v) for v in self._lon]))
        water = np.ones((self.nlat, self.nlon), dtype=bool)

        vectorised = True
        try:
            probe = np.asarray(land_fn(self._lat_deg[:1], lon_deg[:1]))
            vectorised = probe.shape == (1,)
        except Exception:
            vectorised = False

        if vectorised:
            lat_row = np.empty(self.nlon)
            for i in range(self.nlat):
                lat_row.fill(self._lat_deg[i])
                water[i] = ~np.asarray(land_fn(lat_row, lon_deg), dtype=bool)
        else:
            for i in range(self.nlat):
                la = float(self._lat_deg[i])
                row = water[i]
                for j in range(self.nlon):
                    row[j] = not bool(land_fn(la, float(lon_deg[j])))
        return water

    # ------------------------------------------------------------------ indexing
    def index(self, i: int, j: int) -> int:
        """Flat node id. NORMATIVE: `i * nlon + j`. Not bounds-checked -- it is called
        once per stencil edge and the caller has already validated (i, j)."""
        return i * self.nlon + j

    def unindex(self, node: int) -> Tuple[int, int]:
        """Inverse of `index`."""
        return divmod(node, self.nlon)

    def in_bounds(self, i: int, j: int) -> bool:
        return 0 <= i < self.nlat and 0 <= j < self.nlon

    def latlon(self, i: int, j: int) -> Tuple[float, float]:
        """Node position in RADIANS, longitude wrapped to (-pi, pi]."""
        return float(self._lat[i]), wrap_pi(float(self._lon[j]))

    def latlon_deg(self, i: int, j: int) -> Tuple[float, float]:
        """Node position in degrees, for I/O and for `land_fn`-style callables."""
        lat, lon = self.latlon(i, j)
        return lat / DEG, lon / DEG

    def nearest(self, lat: float, lon: float) -> Tuple[int, int]:
        """Nearest node to (lat, lon) in RADIANS. Points outside the domain clamp to the
        boundary rather than raising: the caller usually wants the closest legal start.

        The longitude offset is taken modulo 2pi before rounding, so a domain that
        straddles the antimeridian indexes correctly and a point outside it clamps to
        whichever edge is actually nearer in angle -- not to whichever edge the sign of a
        naive subtraction happened to pick.
        """
        i = int(round((lat - float(self._lat[0])) / self._dlat))
        i = min(max(i, 0), self.nlat - 1)

        off = math.fmod(lon - float(self._lon[0]), _TWO_PI)
        if off < 0.0:
            off += _TWO_PI
        j = int(round(off / self._dlon))
        if j >= self.nlon:
            if self._lon_wraps:
                j %= self.nlon
            else:
                # Outside the eastern edge. Clamp to whichever end is closer in angle.
                gap_east = off - (self.nlon - 1) * self._dlon
                gap_west = _TWO_PI - off
                j = self.nlon - 1 if gap_east <= gap_west else 0
        return i, j

    # ------------------------------------------------------------------ mask
    def is_water(self, i: int, j: int) -> bool:
        """Navigable? Out-of-bounds nodes are not water -- the domain edge is a coast as
        far as the solver is concerned, and returning False keeps every caller's bounds
        check in one place."""
        if not (0 <= i < self.nlat and 0 <= j < self.nlon):
            return False
        return bool(self._water[i, j])

    @property
    def water(self) -> np.ndarray:
        """The (nlat, nlon) boolean mask. Read-only by convention; the template cache
        does not depend on it, but the solver's precomputed fronts do."""
        return self._water

    @property
    def water_fraction(self) -> float:
        return float(self._water.mean())

    def water_near(self, lat: float, lon: float, radius: int = 8) -> Tuple[int, int]:
        """Snap a position (RADIANS) to the nearest navigable node within `radius` CELLS.

        Ports sit on the coast by definition, so `nearest` lands on land roughly half the
        time and the solver would start from a node with no feasible outgoing direction.
        Searches the full Chebyshev square and returns the true-distance minimum rather
        than the first hit, because the square's corner is 1.4 cells further out than its
        edge and the first hit is therefore not the nearest.

        Raises ValueError when the neighbourhood is entirely land: that is a real input
        error (a port 8 cells inland, or a mask at the wrong resolution) and silently
        returning a land node would produce an infeasible solve much later and elsewhere.
        """
        i0, j0 = self.nearest(lat, lon)
        if self.is_water(i0, j0):
            return i0, j0
        best: Optional[Tuple[int, int]] = None
        best_d = float("inf")
        for i in range(max(0, i0 - radius), min(self.nlat, i0 + radius + 1)):
            for dj in range(-radius, radius + 1):
                j = j0 + dj
                if self._lon_wraps:
                    j %= self.nlon
                elif not (0 <= j < self.nlon):
                    continue
                if not self._water[i, j]:
                    continue
                la, lo = self.latlon(i, j)
                d = haversine(lat, lon, la, lo)
                if d < best_d:
                    best_d, best = d, (i, j)
        if best is None:
            raise ValueError(
                f"no navigable node within {radius} cells of "
                f"({lat / DEG:.4f}, {lon / DEG:.4f}) deg -- check the land mask "
                f"resolution or the port coordinates")
        return best

    # ------------------------------------------------------------------ metric spacing
    def spacing_m(self, i: int) -> Tuple[float, float]:
        """(east, north) metres per cell in row `i`. Cached per row at construction:
        cos(lat) is the only row-dependent factor, and evaluating it per node would put a
        transcendental call inside the stencil loop for no information gain."""
        return float(self._east_m[i]), self._north_m

    @property
    def h(self) -> float:
        """Nominal fine spacing `h` in metres, measured at the equator (spec section 1).
        Rows away from the equator are narrower in east by cos(lat); `spacing_m` is the
        truth, this is the scalar the spec's bounds are quoted against."""
        return R_E * self._dlon

    # ------------------------------------------------------------------ stencil
    def _template(self, i: int, radius_m: float) -> Tuple[Tuple[int, int], ...]:
        """Offsets (di, dj) whose node lies within `radius_m` of any node in row `i`.

        Correct for every j in the row because great-circle distance between
        (lat_i, lon) and (lat_i + di*dlat, lon + dj*dlon) does not depend on lon. Rows
        outside the grid are dropped here (di is bounded by i alone); dj cannot be, so
        the column bound is the only test left in the hot loop.
        """
        key = (i, int(round(radius_m * 1000.0)))     # mm resolution: enough to separate
        hit = self._tmpl.get(key)                    # any two stencil radii we would use
        if hit is not None:
            return hit
        if len(self._tmpl) >= _MAX_TEMPLATE_CACHE:
            self._tmpl.clear()

        offsets: List[Tuple[int, int]] = []
        if radius_m > 0.0:
            lat0 = float(self._lat[i])
            # The natural radii are integer multiples of the spacing, which puts nodes
            # EXACTLY on the boundary -- the cardinal neighbour is at R_E*dlat = h, and
            # whether haversine's asin rounds that above or below h then decides whether
            # the 4-neighbour stencil has four members or two, differently in each row.
            # A relative tolerance of 1e-9 (sub-millimetre at h = 56 km) is far below any
            # geometric meaning and makes the boundary case land inside, always.
            lim = radius_m * (1.0 + 1e-9)
            max_di = int(radius_m / self._north_m) + 1
            # A wrapping grid must not offer the same node twice from both sides, so |dj|
            # stops short of the half-circle. The node it excludes is the antipodal
            # column, which no stencil radius ever reaches.
            max_dj = (self.nlon - 1) // 2 if self._lon_wraps else self.nlon - 1
            for di in range(-max_di, max_di + 1):
                i2 = i + di
                if not (0 <= i2 < self.nlat):
                    continue
                lat2 = float(self._lat[i2])
                if abs(lat2 - lat0) * R_E > lim:
                    continue
                if di != 0:
                    offsets.append((di, 0))
                # Distance grows monotonically with |dj| while |dlon| <= pi, so the first
                # failure ends the row -- no need to probe further out.
                for dj in range(1, max_dj + 1):
                    if haversine(lat0, 0.0, lat2, dj * self._dlon) > lim:
                        break
                    offsets.append((di, dj))
                    offsets.append((di, -dj))
        out = tuple(offsets)
        self._tmpl[key] = out
        return out

    def neighbours_within(self, i: int, j: int, radius_m: float,
                          water_only: bool = False) -> Iterator[Tuple[int, int]]:
        """The OUM stencil support: every node within `radius_m` of (i, j), excluding
        itself. Order is unspecified but deterministic.

        `water_only=False` by default. The stencil's job is geometric; whether a support
        node carries a finite value is the solver's test, and a node can be land yet still
        bound a simplex edge in a mask-agnostic variant. Pass True when you want the
        filter here rather than in the caller's loop.
        """
        nlon = self.nlon
        wraps = self._lon_wraps
        water = self._water
        for di, dj in self._template(i, radius_m):
            j2 = j + dj
            if wraps:
                j2 %= nlon
            elif not (0 <= j2 < nlon):
                continue
            i2 = i + di
            if water_only and not water[i2, j2]:
                continue
            yield i2, j2

    def template_size(self, i: int, radius_m: float) -> int:
        """Number of support nodes for a mid-row node -- the OUM cost multiplier, and the
        number to look at when a stencil radius makes the solve unexpectedly slow."""
        return len(self._template(i, radius_m))

    # ------------------------------------------------------------------ misc
    def nbytes(self) -> int:
        """Bytes held by the mask and the coordinate/spacing caches (templates excluded:
        they are unbounded in principle and cleared under pressure)."""
        return int(self._water.nbytes + self._lat.nbytes + self._lon.nbytes
                   + self._lat_deg.nbytes + self._lon_deg.nbytes + self._east_m.nbytes)

    def __repr__(self) -> str:
        return (f"Grid({self.lat_min_deg:g}..{self.lat_max_deg:g} lat, "
                f"{self.lon_min_deg:g}..{self.lon_max_deg:g} lon, "
                f"step={self.step_deg:g} deg, {self.nlat}x{self.nlon}={self.n} nodes, "
                f"water={self.water_fraction * 100:.1f}%"
                f"{'' if self.land_known else ', MASK UNKNOWN'})")


class CoarseGrid(Grid):
    """The coarse lattice carrying the optimistic heuristic (D5, Prop 4.11).

    Built from a fine `Grid` by blocking `rho_c` fine cells in each direction. A coarse
    node sits at the CENTRE of its block, not its corner, so the representative point is
    never more than half a coarse cell from anything it represents.

    Two things make the heuristic admissible rather than merely plausible:

      * the coarse water mask is the OR over the block, dilated by one coarse cell. A
        block containing any navigable water is navigable at the coarse level; anything
        stricter could declare a genuinely passable strait closed and turn the "optimistic"
        bound pessimistic, which breaks A*.
      * `dilated_fine_cells` returns the block PLUS a one-coarse-cell ring. A fine path
        crossing block C can clip the corner of a neighbouring block, and its cost is then
        bounded below by the minimum over the dilated footprint, not over C itself. This
        is decision D5, and the un-dilated version is the gap D5 exists to close.

    Note the constructor differs from `Grid`'s: a coarse grid is always derived from a
    fine one, never specified independently, or the two lattices would not nest.
    """

    __slots__ = ("fine", "rho_c")

    def __init__(self, fine: Grid, rho_c: int = 8) -> None:
        if rho_c < 1:
            raise ValueError(f"rho_c must be >= 1, got {rho_c}")
        self.fine = fine
        self.rho_c = int(rho_c)

        nlat_c = -(-fine.nlat // rho_c)          # ceil: the last block may be partial
        nlon_c = -(-fine.nlon // rho_c)
        if nlat_c < 2 or nlon_c < 2:
            raise ValueError(f"rho_c={rho_c} leaves a {nlat_c}x{nlon_c} coarse grid; "
                             f"use a smaller rho_c")
        step_c = fine.step_deg * rho_c
        off = 0.5 * (rho_c - 1) * fine.step_deg  # block centre
        lat_min_c = fine.lat_min_deg + off
        lon_min_c = fine.lon_min_deg + off

        super().__init__(lat_min_c, lat_min_c + (nlat_c - 1) * step_c,
                         lon_min_c, lon_min_c + (nlon_c - 1) * step_c,
                         step_c,
                         water_mask=_block_or_dilate(fine.water, rho_c, nlat_c, nlon_c))

        self.land_known = fine.land_known

    # ------------------------------------------------------------------ mapping
    def coarse_of(self, i: int, j: int) -> Tuple[int, int]:
        """Fine node -> the coarse node whose block contains it."""
        return i // self.rho_c, j // self.rho_c

    def fine_block(self, I: int, J: int) -> Tuple[int, int, int, int]:
        """Half-open fine index range (i0, i1, j0, j1) of the UNDILATED block."""
        r = self.rho_c
        return (I * r, min((I + 1) * r, self.fine.nlat),
                J * r, min((J + 1) * r, self.fine.nlon))

    def dilated_fine_cells(self, I: int, J: int) -> Iterator[Tuple[int, int]]:
        """Fine nodes in coarse cell (I, J) dilated by one coarse cell (D5).

        Yields the 3x3 coarse-block footprint, clipped to the fine grid (or wrapped in
        longitude when the fine grid closes the circle). Used to build
        `F_low(C, u) = min over the dilated closed cell`, which is what makes the coarse
        edge cost a lower bound for fine paths that only clip C.
        """
        r = self.rho_c
        fine = self.fine
        i0 = max(0, I * r - r)
        i1 = min(fine.nlat, (I + 1) * r + r)
        j0 = J * r - r
        j1 = (J + 1) * r + r
        wraps = fine._lon_wraps
        if not wraps:
            j0 = max(0, j0)
            j1 = min(fine.nlon, j1)
        for i in range(i0, i1):
            for j in range(j0, j1):
                yield i, (j % fine.nlon) if wraps else j

    def __repr__(self) -> str:
        return (f"CoarseGrid(rho_c={self.rho_c}, {self.nlat}x{self.nlon}={self.n} nodes, "
                f"H={self.h / 1000.0:.1f} km, water={self.water_fraction * 100:.1f}%)")


def _block_or_dilate(water: np.ndarray, rho_c: int,
                     nlat_c: int, nlon_c: int) -> np.ndarray:
    """Block-OR the fine mask, then dilate by one coarse cell in each direction.

    The OR (not the AND, not a majority vote) is what keeps the coarse relaxation
    optimistic: a coarse cell is passable if any fine cell in it is. The 3x3 dilation is
    applied separably, which is exact for a square structuring element.
    """
    nlat, nlon = water.shape
    pad = np.zeros((nlat_c * rho_c, nlon_c * rho_c), dtype=bool)
    pad[:nlat, :nlon] = water
    blk = pad.reshape(nlat_c, rho_c, nlon_c, rho_c).any(axis=(1, 3))

    dil = blk.copy()
    dil[1:, :] |= blk[:-1, :]
    dil[:-1, :] |= blk[1:, :]
    col = dil.copy()
    dil[:, 1:] |= col[:, :-1]
    dil[:, :-1] |= col[:, 1:]
    return dil
