"""Optional data adapters.

READ THIS FIRST, IT IS THE POINT OF THE MODULE:

    The KAIROS solver has ZERO data dependencies. Nothing in comoving.py, metric.py,
    grid.py, labels.py or sweep.py imports this file, and none of them ever will.

Exactly like A* does not ship with a map and Dijkstra does not ship with a road network,
KAIROS does not ship with an ocean. The solver consumes ONE interface:

    field.at(lat, lon, t) -> Env          # radians, seconds; Env is a plain struct

Anything satisfying that is a valid field: an analytic function, a synthetic test case, a
NetCDF file from ERA5 or INCOIS, a live OPeNDAP server, a CSV, or a mock in a unit test. The
algorithm cannot tell the difference and does not care.

This module is a CONVENIENCE layer that wraps common real-world sources in that interface.
It requires numpy + netCDF4/xarray. If you delete this file the algorithm still runs, and the
whole analytic test suite still passes -- that is the property worth protecting.

Sources covered:
  * NetCDFField  -- generic CF-style NetCDF/OPeNDAP. Covers ERA5, INCOIS, CMEMS, HYCOM,
                    WaveWatch III, and most operational products, via a variable-name map.
  * HYCOM_*      -- presets for HYCOM global ocean currents. OPEN ACCESS, no credentials.
  * ERA5_*       -- presets for ERA5 reanalysis (winds + waves). Needs a free Copernicus CDS
                    account and API key; see fetch instructions in `era5_request_template`.
  * INCOIS_*     -- presets for INCOIS Indian Ocean products.
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Dict, Optional, Sequence, Tuple

import numpy as np

from .types import Env

R2D = 180.0 / math.pi
D2R = math.pi / 180.0


# ============================================================ variable-name presets
# A varmap says which NetCDF variable supplies which Env field. Anything absent is left at
# its Env default, so a currents-only product is perfectly usable -- you just get zero waves.

HYCOM_CURRENTS: Dict[str, str] = {"cu": "water_u", "cv": "water_v"}

ERA5_WIND_WAVE: Dict[str, str] = {
    "wu": "u10", "wv": "v10",        # 10 m wind components
    "hs": "swh",                     # significant height of combined wind waves and swell
    "tp": "pp1d",                    # peak wave period
    "mu_w": "mwd",                   # mean wave direction (DEGREES, meteorological "FROM")
}

CMEMS_WAVES: Dict[str, str] = {"hs": "VHM0", "tp": "VTPK", "mu_w": "VMDR"}
CMEMS_CURRENTS: Dict[str, str] = {"cu": "uo", "cv": "vo"}

# INCOIS product variable names vary by product; these cover the common WW3/ROMS exports.
INCOIS_WAVES: Dict[str, str] = {"hs": "hs", "tp": "tp", "mu_w": "dp"}
INCOIS_CURRENTS: Dict[str, str] = {"cu": "u", "cv": "v"}


# Direction conventions differ between products and getting this wrong is a silent 180-degree
# error that makes head seas look like following seas. ERA5 `mwd` is the direction waves come
# FROM, in degrees. KAIROS wants the direction waves travel TOWARDS, in radians.
WAVE_DIR_FROM = "from"      # meteorological convention (ERA5, most wave models)
WAVE_DIR_TOWARDS = "towards"


@dataclass
class _Stack:
    """One variable on a (time, lat, lon) grid, held in memory."""
    times: np.ndarray            # seconds since epoch, ascending
    lats: np.ndarray             # radians, ascending
    lons: np.ndarray             # radians, ascending, in (-pi, pi]
    values: np.ndarray           # (nt, nlat, nlon), NaN over land


class NetCDFField:
    """Generic NetCDF / OPeNDAP adapter implementing the EnvField interface.

    Loads a spatial-temporal subset into memory once, then serves `at()` by trilinear
    interpolation. Loading eagerly rather than lazily is deliberate: the solver calls `at()`
    millions of times and a lazy handle would make every call a disk or network round trip.

    Args:
      source    : path or OPeNDAP URL
      varmap    : {env_field: netcdf_variable}, e.g. HYCOM_CURRENTS
      bbox      : (lat_min, lat_max, lon_min, lon_max) in DEGREES
      time_slice: (start_index, stop_index) or None for all
      wave_dir_convention: 'from' (meteorological) or 'towards'
      depth_index: for 3-D ocean products, which level is the surface (usually 0)
    """

    def __init__(self, source: str, varmap: Dict[str, str],
                 bbox: Tuple[float, float, float, float],
                 time_slice: Optional[Tuple[int, int]] = None,
                 wave_dir_convention: str = WAVE_DIR_FROM,
                 depth_index: int = 0,
                 decode_times: bool = True):
        import xarray as xr

        self.wave_dir_convention = wave_dir_convention
        ds = xr.open_dataset(source, decode_times=decode_times)
        try:
            self._stacks: Dict[str, _Stack] = {}
            lat_name = _find(ds, ("lat", "latitude", "nav_lat", "y"))
            lon_name = _find(ds, ("lon", "longitude", "nav_lon", "x"))
            time_name = _find(ds, ("time", "valid_time", "ocean_time"))

            lat0, lat1, lon0, lon1 = bbox
            lons_raw = np.asarray(ds[lon_name].values, dtype=float)
            # Products use either 0..360 or -180..180. Normalise the REQUEST to match the file
            # rather than the file to match the request -- reindexing a 4500-point axis on an
            # OPeNDAP server is far more expensive than shifting two scalars.
            if lons_raw.max() > 180.0:
                lon0 = lon0 % 360.0
                lon1 = lon1 % 360.0

            sel = {lat_name: slice(lat0, lat1), lon_name: slice(lon0, lon1)}
            sub = ds.sel(**sel)
            if time_slice is not None:
                sub = sub.isel({time_name: slice(*time_slice)})

            times = _to_epoch_seconds(sub[time_name])
            lats = np.asarray(sub[lat_name].values, dtype=float) * D2R
            lons = np.asarray(sub[lon_name].values, dtype=float)
            lons = np.where(lons > 180.0, lons - 360.0, lons) * D2R

            for env_key, var in varmap.items():
                if var not in sub:
                    continue
                da = sub[var]
                for dim in ("depth", "lev", "level", "depthu", "depthv"):
                    if dim in da.dims:
                        da = da.isel({dim: depth_index})
                vals = np.asarray(da.values, dtype=float)
                if vals.ndim == 2:                       # single time step
                    vals = vals[None, :, :]
                self._stacks[env_key] = _Stack(times, lats, lons, vals)

            if not self._stacks:
                raise ValueError(
                    f"none of {list(varmap.values())} found in {source}; "
                    f"available: {list(ds.data_vars)[:20]}")

            any_stack = next(iter(self._stacks.values()))
            self._t0 = float(any_stack.times[0])
            self._t1 = float(any_stack.times[-1])
        finally:
            ds.close()

    # ---------------------------------------------------------------- EnvField
    @property
    def t0(self) -> float:
        return self._t0

    @property
    def horizon(self) -> float:
        return self._t1

    def at(self, lat: float, lon: float, t: float) -> Env:
        """Trilinear sample. Out-of-domain queries CLAMP; past the horizon, the last frame
        persists. Both are stated conventions, not accidents -- see spec 06-numerics (f)."""
        vals = {}
        for key, st in self._stacks.items():
            v = _trilinear(st, lat, lon, t)
            vals[key] = 0.0 if not math.isfinite(v) else v   # NaN = land -> treat as calm

        mu = vals.get("mu_w", 0.0)
        if "mu_w" in vals:
            mu = mu * D2R
            if self.wave_dir_convention == WAVE_DIR_FROM:
                mu = mu + math.pi          # "from" -> "towards"; see the note at the top
        return Env(
            cu=vals.get("cu", 0.0), cv=vals.get("cv", 0.0),
            wu=vals.get("wu", 0.0), wv=vals.get("wv", 0.0),
            hs=max(0.0, vals.get("hs", 0.0)),
            tp=max(1e-3, vals.get("tp", 8.0)),
            mu_w=mu,
            depth=vals.get("depth", 4000.0),
        )

    # ---------------------------------------------------------------- extras
    def land_mask_fn(self, key: str = "cu"):
        """Return is_land(lat_deg, lon_deg) -> bool derived from NaNs in the data.

        Ocean products carry NaN over land, which is a free and perfectly good land mask --
        and it is guaranteed consistent with the currents the solver will actually see, which
        a separate coastline database is not.
        """
        st = self._stacks[key]

        def is_land(lat_deg: float, lon_deg: float) -> bool:
            i = int(np.clip(np.searchsorted(st.lats, lat_deg * D2R) - 1, 0, len(st.lats) - 1))
            lo = ((lon_deg + 180.0) % 360.0 - 180.0) * D2R
            j = int(np.clip(np.searchsorted(st.lons, lo) - 1, 0, len(st.lons) - 1))
            return not np.isfinite(st.values[0, i, j])
        return is_land

    def coverage(self) -> str:
        st = next(iter(self._stacks.values()))
        return (f"{list(self._stacks)} | "
                f"lat {st.lats[0]*R2D:.2f}..{st.lats[-1]*R2D:.2f} "
                f"lon {st.lons[0]*R2D:.2f}..{st.lons[-1]*R2D:.2f} | "
                f"{len(st.times)} time steps | grid {st.values.shape[1]}x{st.values.shape[2]}")


# ============================================================ helpers
def _find(ds, names: Sequence[str]) -> str:
    for n in names:
        if n in ds.coords or n in ds.dims or n in ds.variables:
            return n
    raise KeyError(f"none of {names} in dataset; have {list(ds.coords)}")


def _to_epoch_seconds(da) -> np.ndarray:
    v = da.values
    if np.issubdtype(v.dtype, np.datetime64):
        return v.astype("datetime64[s]").astype(np.int64).astype(float)
    # numeric time with CF units, e.g. "hours since 2000-01-01"
    units = str(da.attrs.get("units", "seconds since 1970-01-01"))
    scale = {"seconds": 1.0, "minutes": 60.0, "hours": 3600.0, "days": 86400.0}
    unit = units.split()[0].lower()
    mult = scale.get(unit, 1.0)
    try:
        base = str(units).split("since")[1].strip().replace("T", " ")[:19]
        epoch = np.datetime64(base).astype("datetime64[s]").astype(np.int64)
    except Exception:
        epoch = 0
    return np.asarray(v, dtype=float) * mult + float(epoch)


def _trilinear(st: _Stack, lat: float, lon: float, t: float) -> float:
    """Trilinear in (t, lat, lon) with clamping at every edge.

    Higher-order interpolation of the FIELDS is deliberately not offered: it can overshoot and
    break the monotonicity the sweep's correctness proof relies on. Interpolating the value
    function at higher order is fine; interpolating the data is not.
    """
    ti = _bracket(st.times, t)
    ai = _bracket(st.lats, lat)
    oi = _bracket(st.lons, lon)
    (t0, t1, ft), (i0, i1, fa), (j0, j1, fo) = ti, ai, oi
    v = st.values
    c00 = v[t0, i0, j0] * (1 - fo) + v[t0, i0, j1] * fo
    c01 = v[t0, i1, j0] * (1 - fo) + v[t0, i1, j1] * fo
    c10 = v[t1, i0, j0] * (1 - fo) + v[t1, i0, j1] * fo
    c11 = v[t1, i1, j0] * (1 - fo) + v[t1, i1, j1] * fo
    c0 = c00 * (1 - fa) + c01 * fa
    c1 = c10 * (1 - fa) + c11 * fa
    return c0 * (1 - ft) + c1 * ft


def _bracket(axis: np.ndarray, x: float) -> Tuple[int, int, float]:
    n = len(axis)
    if n == 1:
        return 0, 0, 0.0
    k = int(np.searchsorted(axis, x) - 1)
    k = max(0, min(k, n - 2))
    lo, hi = axis[k], axis[k + 1]
    f = 0.0 if hi == lo else (x - lo) / (hi - lo)
    return k, k + 1, float(min(1.0, max(0.0, f)))


# ============================================================ source presets
def hycom_currents(bbox, time_slice=(0, 8),
                   url: str = "https://tds.hycom.org/thredds/dodsC/GLBy0.08/expt_93.0"):
    """HYCOM global 1/12-degree ocean currents. OPEN ACCESS -- no account, no API key.

    This is the fastest way to get real currents into KAIROS, and the one used by
    demo/run_real_data.py. decode_times=False because HYCOM publishes non-CF time units
    ('hours since analysis') on some aggregations that xarray refuses to decode.
    """
    return NetCDFField(url, HYCOM_CURRENTS, bbox, time_slice, decode_times=False)


def era5_file(path, bbox, time_slice=None):
    """ERA5 reanalysis winds + waves from a NetCDF you downloaded. See era5_request_template.

    ERA5 requires a free Copernicus CDS account and a personal API key. This project will not
    fetch it for you and does not handle credentials -- run the template below yourself.
    """
    return NetCDFField(path, ERA5_WIND_WAVE, bbox, time_slice,
                       wave_dir_convention=WAVE_DIR_FROM)


def incois_file(path, bbox, time_slice=None, kind: str = "waves"):
    """INCOIS Indian Ocean product from a downloaded NetCDF.

    INCOIS distributes via https://incois.gov.in/ (registration required for some products).
    Their ERDDAP presented an expired/invalid TLS certificate when this was written; if that
    is still true, download over a browser session rather than disabling certificate
    verification in code.
    """
    varmap = INCOIS_WAVES if kind == "waves" else INCOIS_CURRENTS
    return NetCDFField(path, varmap, bbox, time_slice)


def era5_request_template(out_path: str = "era5_indian_ocean.nc",
                          year: str = "2024", month: str = "06",
                          days: Sequence[str] = ("01", "02", "03"),
                          area=(30, 40, -10, 100)) -> str:
    """Return a runnable CDS API script. YOU run it, with YOUR key.

    Setup, once:
      1. Create a free account at https://cds.climate.copernicus.eu/
      2. Copy your key into ~/.cdsapirc  (the site shows the exact two lines)
      3. pip install cdsapi
    `area` is (North, West, South, East) in degrees -- note CDS's unusual ordering.
    """
    return f'''\
import cdsapi
c = cdsapi.Client()
c.retrieve("reanalysis-era5-single-levels", {{
    "product_type": "reanalysis",
    "format": "netcdf",
    "variable": [
        "10m_u_component_of_wind", "10m_v_component_of_wind",
        "significant_height_of_combined_wind_waves_and_swell",
        "peak_wave_period", "mean_wave_direction",
    ],
    "year": "{year}",
    "month": "{month}",
    "day": {list(days)!r},
    "time": ["00:00", "03:00", "06:00", "09:00", "12:00", "15:00", "18:00", "21:00"],
    "area": {list(area)!r},
}}, "{out_path}")
print("wrote {out_path}")
'''


class CompositeField:
    """Combine several sources -- e.g. HYCOM currents + ERA5 waves + IMD winds.

    Later sources override earlier ones for the fields they provide. Real routing almost
    always needs this: no single product supplies currents, waves and wind together at the
    resolution you want.
    """

    def __init__(self, *fields):
        if not fields:
            raise ValueError("CompositeField needs at least one source")
        self.fields = fields

    @property
    def t0(self) -> float:
        return max(f.t0 for f in self.fields)

    @property
    def horizon(self) -> float:
        return min(f.horizon for f in self.fields)

    def at(self, lat: float, lon: float, t: float) -> Env:
        out = self.fields[0].at(lat, lon, t)
        for f in self.fields[1:]:
            e = f.at(lat, lon, t)
            out = Env(
                cu=e.cu or out.cu, cv=e.cv or out.cv,
                wu=e.wu or out.wu, wv=e.wv or out.wv,
                hs=e.hs or out.hs, tp=e.tp if e.tp != 8.0 else out.tp,
                mu_w=e.mu_w or out.mu_w,
                depth=e.depth if e.depth != 4000.0 else out.depth,
            )
        return out
