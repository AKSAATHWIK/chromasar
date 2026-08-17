"""AIS hindcast validation: what would KAIROS have advised, versus what the ship actually did?

This is the only test in the project that confronts the algorithm with a real ship in a real
ocean. Everything else uses fields we generated or analytic answers we derived.

DATA
  AIS      NOAA MarineCadastre, US waters, open access, ~319 MB/day zipped CSV.
           https://coast.noaa.gov/htdata/CMSP/AISDataHandler/<year>/AIS_<Y>_<M>_<D>.zip
  Currents HYCOM GLBy0.08 via OPeNDAP, open access, no credentials.

REGION  Florida Straits / Gulf Stream. Chosen because it is the strongest routing-relevant
        current in open AIS coverage -- the Gulf Stream core runs 1.5-2.0 m/s, which is 20-30 %
        of a merchant ship's speed. In a weak-current region the whole comparison would be
        noise, and reporting a "saving" there would be meaningless.

WHAT THIS CAN AND CANNOT SHOW
  CAN:    whether the routes KAIROS produces are physically sensible against real currents,
          and how its predicted transit time compares with what really happened.
  CANNOT: prove a fuel saving. See the confounders in `REPORT_CAVEATS` -- they are printed
          with every result on purpose, because the headline number is an UPPER BOUND on
          achievable savings, not an estimate of them.
"""
from __future__ import annotations

import csv
import io
import math
import sys
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

D2R = math.pi / 180.0
R_E = 6_371_000.0

# Florida Straits / Gulf Stream box
LAT0, LAT1 = 23.0, 28.5
LON0, LON1 = -81.5, -76.0

# AIS VesselType codes: 70-79 cargo, 80-89 tanker. Deep-draft commercial traffic only --
# fishing vessels and pleasure craft do not transit, they loiter, and would pollute the sample.
CARGO_TANKER = set(range(70, 90))

MIN_TRACK_KM = 120.0        # shorter transits are dominated by pilotage and manoeuvring
MIN_POINTS = 25
MAX_GAP_MIN = 45.0          # a longer gap means we cannot claim a continuous voyage

REPORT_CAVEATS = """
CONFOUNDERS -- read before quoting any number from this table.

 1. SCHEDULE. Ships arrive to a berth slot, not as early as possible. A ship that could have
    arrived sooner and chose not to is not a routing failure; it is just-in-time arrival, and
    it is often the FUEL-OPTIMAL choice. This test measures minimum transit time, which is
    the wrong objective for many of these voyages.
 2. SPEED CAPABILITY is inferred from the vessel's own observed SOG (90th percentile) and is
    therefore an UNDERESTIMATE of what the ship could do: it reflects the speed actually
    chosen, including any voluntary slow steaming.
 3. TRAFFIC SEPARATION SCHEMES, pilotage, security zones and draft restrictions constrain real
    routes. Our grid has none of them, so KAIROS is allowed shortcuts the ship was not.
 4. THE SHIP MAY ALREADY HAVE BEEN WEATHER-ROUTED by a commercial service, in which case the
    honest baseline is "as good as an existing router", not "naive".
 5. CURRENTS ONLY. Waves and wind are not in this comparison, so a ship that slowed for sea
    state looks slow for no visible reason.
 6. HYCOM is a model, not a measurement. Its Gulf Stream position can be off by tens of km.

The headline number is an UPPER BOUND on achievable saving, not an estimate of one.
"""


@dataclass
class Track:
    mmsi: str
    name: str
    vtype: int
    pts: List[Tuple[float, float, float]]   # (t_seconds, lat_rad, lon_rad)
    sog_p90: float                          # m/s, inferred speed capability

    @property
    def duration_h(self) -> float:
        return (self.pts[-1][0] - self.pts[0][0]) / 3600.0

    @property
    def path_km(self) -> float:
        return sum(haversine(self.pts[i][1], self.pts[i][2],
                             self.pts[i + 1][1], self.pts[i + 1][2])
                   for i in range(len(self.pts) - 1)) / 1000.0

    @property
    def gc_km(self) -> float:
        return haversine(self.pts[0][1], self.pts[0][2],
                         self.pts[-1][1], self.pts[-1][2]) / 1000.0


def haversine(lat1, lon1, lat2, lon2):
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = (math.sin(dlat / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2)
    return 2.0 * R_E * math.asin(math.sqrt(min(1.0, max(0.0, a))))


def parse_ais(zip_path: str, limit_rows: Optional[int] = None) -> List[Track]:
    """Stream the AIS zip, keep only cargo/tanker fixes inside the box, assemble voyages.

    Streaming matters: the CSV is ~1.5 GB uncompressed and there is no reason to land it.
    """
    by_ship: Dict[str, List[tuple]] = defaultdict(list)
    meta: Dict[str, Tuple[str, int]] = {}
    kept = seen = 0

    with zipfile.ZipFile(zip_path) as z:
        name = [n for n in z.namelist() if n.lower().endswith(".csv")][0]
        with z.open(name) as raw:
            rdr = csv.reader(io.TextIOWrapper(raw, encoding="utf-8", errors="replace"))
            header = next(rdr)
            col = {c.strip().upper(): i for i, c in enumerate(header)}
            iM, iT = col["MMSI"], col["BASEDATETIME"]
            iLa, iLo = col["LAT"], col["LON"]
            iS = col.get("SOG", -1)
            iN, iV = col.get("VESSELNAME", -1), col.get("VESSELTYPE", -1)
            for row in rdr:
                seen += 1
                if limit_rows and seen > limit_rows:
                    break
                try:
                    la = float(row[iLa]); lo = float(row[iLo])
                except (ValueError, IndexError):
                    continue
                if not (LAT0 <= la <= LAT1 and LON0 <= lo <= LON1):
                    continue
                try:
                    vt = int(float(row[iV])) if iV >= 0 and row[iV] else 0
                except ValueError:
                    vt = 0
                if vt not in CARGO_TANKER:
                    continue
                ts = row[iT].strip()
                try:                                   # 2023-01-15T00:00:02
                    hh = int(ts[11:13]); mm = int(ts[14:16]); ss = int(ts[17:19])
                except (ValueError, IndexError):
                    continue
                sog = 0.0
                if iS >= 0 and row[iS]:
                    try:
                        sog = float(row[iS]) * 0.514444      # knots -> m/s
                    except ValueError:
                        pass
                m = row[iM]
                by_ship[m].append((hh * 3600 + mm * 60 + ss, la * D2R, lo * D2R, sog))
                meta.setdefault(m, (row[iN] if iN >= 0 else "", vt))
                kept += 1

    print(f"  scanned {seen:,} rows, kept {kept:,} cargo/tanker fixes "
          f"for {len(by_ship):,} vessels")

    tracks: List[Track] = []
    for m, pts in by_ship.items():
        pts.sort()
        # split on long gaps: each continuous run is a candidate voyage
        runs, cur = [], [pts[0]]
        for a, b in zip(pts, pts[1:]):
            if (b[0] - a[0]) / 60.0 > MAX_GAP_MIN:
                runs.append(cur); cur = [b]
            else:
                cur.append(b)
        runs.append(cur)
        for run in runs:
            if len(run) < MIN_POINTS:
                continue
            trk = Track(m, meta[m][0], meta[m][1],
                        [(p[0], p[1], p[2]) for p in run],
                        _p90([p[3] for p in run]))
            if trk.gc_km >= MIN_TRACK_KM and trk.sog_p90 > 3.0:
                tracks.append(trk)
    return tracks


def _p90(xs: List[float]) -> float:
    s = sorted(xs)
    return s[min(len(s) - 1, int(0.90 * len(s)))] if s else 0.0
