"""Run the AIS hindcast: 66 real voyages vs what KAIROS would have advised.

Usage:  python run_hindcast.py <path-to-ais.zip>

WHAT THIS VALIDATES, AND WHAT IT DOES NOT.

It validates the ROUTER against reality: the metric, the drift correction, the solver, and
whether the routes are physically sensible in a real 2 m/s current.

It does NOT validate the co-moving reduction. The Gulf Stream is quasi-stationary -- it
meanders over weeks, not hours -- so over a 15 h transit the advection velocity w is
essentially zero and the reduction is the identity map. Testing the reduction against real
data needs a TRANSLATING system (a tropical cyclone), which needs wave/wind forecast data,
which needs Copernicus credentials this project does not hold. That test remains unrun and
is the honest gap.
"""
from __future__ import annotations

import math
import pickle
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np

from hindcast import (LAT0, LAT1, LON0, LON1, REPORT_CAVEATS, Track, haversine,
                      parse_ais)
from kairos.fast import FastLattice, comoving_plan_fast

D2R = math.pi / 180.0
R_E = 6_371_000.0
HYCOM = "https://tds.hycom.org/thredds/dodsC/GLBy0.08/expt_93.0"
TIME_INDEX = 12017                      # 2023-01-15T12:00:00, exact


def load_currents():
    import xarray as xr
    ds = xr.open_dataset(HYCOM, decode_times=False)
    sub = (ds[["water_u", "water_v"]]
           .isel(time=TIME_INDEX, depth=0)
           .sel(lat=slice(LAT0 - 0.5, LAT1 + 0.5),
                lon=slice((LON0 - 0.5) % 360, (LON1 + 0.5) % 360)))
    u = np.asarray(sub.water_u.values, dtype=float)
    v = np.asarray(sub.water_v.values, dtype=float)
    lats = np.asarray(sub.lat.values, dtype=float)
    lons = np.asarray(sub.lon.values, dtype=float)
    lons = np.where(lons > 180.0, lons - 360.0, lons)
    ds.close()
    land = ~np.isfinite(u)
    u = np.nan_to_num(u); v = np.nan_to_num(v)
    print(f"  HYCOM {u.shape} grid, lat {lats[0]:.2f}..{lats[-1]:.2f}, "
          f"lon {lons[0]:.2f}..{lons[-1]:.2f}, "
          f"|c|max {np.hypot(u, v).max():.2f} m/s, land {land.mean()*100:.0f}%")
    return lats, lons, u, v, land


class Currents:
    """Bilinear sampler over the HYCOM slice. Degrees in, m/s out."""

    def __init__(self, lats, lons, u, v, land):
        self.la, self.lo, self.u, self.v, self.land = lats, lons, u, v, land

    def _idx(self, lat_deg, lon_deg):
        i = np.clip(np.searchsorted(self.la, lat_deg) - 1, 0, len(self.la) - 2)
        j = np.clip(np.searchsorted(self.lo, lon_deg) - 1, 0, len(self.lo) - 2)
        return int(i), int(j)

    def at(self, lat_deg, lon_deg):
        i, j = self._idx(lat_deg, lon_deg)
        a = (lat_deg - self.la[i]) / (self.la[i + 1] - self.la[i])
        b = (lon_deg - self.lo[j]) / (self.lo[j + 1] - self.lo[j])
        a = min(1.0, max(0.0, a)); b = min(1.0, max(0.0, b))
        def bil(m):
            return (m[i, j] * (1 - a) * (1 - b) + m[i + 1, j] * a * (1 - b)
                    + m[i, j + 1] * (1 - a) * b + m[i + 1, j + 1] * a * b)
        return float(bil(self.u)), float(bil(self.v))

    def is_land(self, lat_deg, lon_deg):
        i, j = self._idx(lat_deg, lon_deg)
        return bool(self.land[i, j])


def estimate_stw(trk: Track, cur: Currents) -> float:
    """Through-water speed capability, backed out of AIS.

    CRITICAL FOR FAIRNESS. AIS reports speed over GROUND, which in the Gulf Stream already
    contains up to 2 m/s of current help. Feeding that back in as the ship's own speed would
    credit the current twice and rig the comparison in KAIROS's favour.

    So for every AIS segment: STW vector = ground velocity - current, and we take the 90th
    percentile of |STW| as the vessel's sustainable through-water capability.
    """
    stws = []
    for (t1, la1, lo1), (t2, la2, lo2) in zip(trk.pts, trk.pts[1:]):
        dt = t2 - t1
        if dt < 60.0:
            continue
        d = haversine(la1, lo1, la2, lo2)
        if d < 1.0:
            continue
        # ground velocity components (east, north)
        dn = (la2 - la1) * R_E
        de = (lo2 - lo1) * R_E * math.cos(0.5 * (la1 + la2))
        ge, gn = de / dt, dn / dt
        cu, cv = cur.at(0.5 * (la1 + la2) / D2R, 0.5 * (lo1 + lo2) / D2R)
        stws.append(math.hypot(ge - cu, gn - cv))
    if not stws:
        return 0.0
    stws.sort()
    return stws[min(len(stws) - 1, int(0.90 * len(stws)))]


def plan_voyage(cur: Currents, src_deg, dst_deg, V, step_deg=0.08):
    """Solve with KAIROS on a local lattice in metres, centred on the voyage."""
    lat_c = 0.5 * (src_deg[0] + dst_deg[0])
    mlat = R_E * D2R
    mlon = R_E * D2R * math.cos(lat_c * D2R)

    pad = 0.9
    la_lo = max(LAT0 - 0.4, min(src_deg[0], dst_deg[0]) - pad)
    la_hi = min(LAT1 + 0.4, max(src_deg[0], dst_deg[0]) + pad)
    lo_lo = max(LON0 - 0.4, min(src_deg[1], dst_deg[1]) - pad)
    lo_hi = min(LON1 + 0.4, max(src_deg[1], dst_deg[1]) + pad)

    def to_xy(lat, lon):
        return (lon - lo_lo) * mlon, (lat - la_lo) * mlat

    h = step_deg * mlat
    nx = int(((lo_hi - lo_lo) * mlon) / h) + 1
    ny = int(((la_hi - la_lo) * mlat) / h) + 1
    if nx < 5 or ny < 5:
        return None

    def to_ll(x, y):
        return la_lo + y / mlat, lo_lo + x / mlon

    lat = FastLattice(0.0, 0.0, nx, ny, h,
                      passable_fn=lambda x, y: not cur.is_land(*to_ll(x, y)))

    def sample(x, y):
        return cur.at(*to_ll(x, y))

    def speed_from(c, ux, uy):
        cp = c[0] * ux + c[1] * uy
        cq = -c[0] * uy + c[1] * ux
        r = V * V - cq * cq
        if r <= 0.0:
            return 0.0
        s = math.sqrt(r) + cp
        return s if s > 1e-6 else 0.0

    p = comoving_plan_fast(lat, sample, speed_from, (0.0, 0.0),
                           to_xy(*src_deg), to_xy(*dst_deg),
                           sigma_max=V + 2.5, goal_tol=h)
    return p


def great_circle_through_currents(cur: Currents, src_deg, dst_deg, V, n=400):
    """THE CORRECT BASELINE: sail the great circle, but through the REAL current field.

    The first version of this script compared against `gc_distance / V`, which assumes NO
    current at all. That is not a route -- it is a fiction, and it is not even a bound: on an
    adverse-current leg the real great-circle transit takes LONGER, which is why that
    comparison produced nonsense like 'KAIROS is 3 % worse than the baseline' when KAIROS is
    provably optimal on the grid.

    This version integrates the actual great-circle track through the actual currents, with
    the drift correction applied at each step (the ship must crab to hold the track). It is a
    genuinely achievable route, so KAIROS must be no worse -- and the difference is the real
    value of routing.

    Crucially, it uses the SAME V as KAIROS, so the p90-speed assumption cancels out of the
    comparison entirely. This is the number to quote.
    """
    la1, lo1 = src_deg[0] * D2R, src_deg[1] * D2R
    la2, lo2 = dst_deg[0] * D2R, dst_deg[1] * D2R
    total = 0.0
    prev = (la1, lo1)
    for k in range(1, n + 1):
        f = k / n
        la = la1 + (la2 - la1) * f
        lo = lo1 + (lo2 - lo1) * f
        d = haversine(prev[0], prev[1], la, lo)
        if d < 1e-6:
            prev = (la, lo)
            continue
        dn = (la - prev[0]) * R_E
        de = (lo - prev[1]) * R_E * math.cos(0.5 * (la + prev[0]))
        L = math.hypot(de, dn)
        ux, uy = de / L, dn / L
        cu, cv = cur.at(0.5 * (la + prev[0]) / D2R, 0.5 * (lo + prev[1]) / D2R)
        cp = cu * ux + cv * uy
        cq = -cu * uy + cv * ux
        r = V * V - cq * cq
        if r <= 0.0:
            return math.inf                 # track unholdable against the cross-current
        sig = math.sqrt(r) + cp
        if sig <= 1e-6:
            return math.inf
        total += d / sig
        prev = (la, lo)
    return total / 3600.0


def main(zip_path: str):
    print("=" * 100)
    print("AIS HINDCAST -- 2023-01-15, Florida Straits / Gulf Stream")
    print("=" * 100)
    cache = Path(zip_path).with_suffix(".tracks.pkl")
    if cache.exists():
        tracks = pickle.load(open(cache, "rb"))
        print(f"  {len(tracks)} voyages (cached)")
    else:
        tracks = parse_ais(zip_path)
        pickle.dump(tracks, open(cache, "wb"))
    cur = Currents(*load_currents())
    print()

    rows = []
    t0 = time.perf_counter()
    for trk in sorted(tracks, key=lambda t: -t.gc_km):
        V = estimate_stw(trk, cur)
        if V < 2.5 or V > 13.0:                 # implausible; drop rather than distort
            continue
        s = (trk.pts[0][1] / D2R, trk.pts[0][2] / D2R)
        d = (trk.pts[-1][1] / D2R, trk.pts[-1][2] / D2R)
        p = plan_voyage(cur, s, d, V)
        if p is None or not math.isfinite(p.arrival) or p.miss > 25_000:
            continue
        actual_h = trk.duration_h
        kairos_h = p.arrival / 3600.0
        gc_h = great_circle_through_currents(cur, s, d, V)
        if not math.isfinite(gc_h):
            continue
        rows.append((trk, V, actual_h, kairos_h, gc_h))

    el = time.perf_counter() - t0
    print(f"{'vessel':<21}{'gc km':>7}{'V kt':>6}{'actual h':>9}{'KAIROS h':>9}"
          f"{'GC+cur h':>9}{'vs actual':>10}{'vs GC':>8}")
    print("-" * 100)
    for trk, V, a, k, n in rows[:18]:
        print(f"{trk.name[:20]:<21}{trk.gc_km:7.0f}{V/0.514444:6.1f}{a:9.2f}{k:9.2f}"
              f"{n:9.2f}{(k-a)/a*100:+9.1f}%{(k-n)/n*100:+7.1f}%")

    if not rows:
        print("  no usable voyages after filtering")
        return
    va = np.array([(k - a) / a * 100 for _, _, a, k, _ in rows])
    vn = np.array([(k - n) / n * 100 for _, _, _, k, n in rows])
    print("-" * 100)
    print(f"  n = {len(rows)} voyages, solved in {el:.1f} s")
    print(f"  KAIROS vs ACTUAL : median {np.median(va):+.1f}%   mean {va.mean():+.1f}%   "
          f"[p25 {np.percentile(va,25):+.1f}%, p75 {np.percentile(va,75):+.1f}%]")
    print(f"  KAIROS vs GC+cur : median {np.median(vn):+.1f}%   mean {vn.mean():+.1f}%   "
          f"[p25 {np.percentile(vn,25):+.1f}%, p75 {np.percentile(vn,75):+.1f}%]   <-- THE NUMBER")
    worse = int((vn > 0.05).sum())
    print(f"  sanity: KAIROS worse than the great circle on {worse}/{len(rows)} "
          f"(must be 0 -- the GC is a feasible route, so an optimal solver cannot lose)")
    best = float(vn.min())
    print(f"  best single voyage vs GC: {best:+.1f}%")
    faster = int((va < 0).sum())
    print(f"  KAIROS predicts a shorter transit than the ship achieved on "
          f"{faster}/{len(rows)} voyages ({100*faster/len(rows):.0f}%)")
    print(REPORT_CAVEATS)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ais.zip")
