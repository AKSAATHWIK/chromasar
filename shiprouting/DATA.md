# Ship Routing (SIH1658) — data sources & status

**PS:** SIH1658 — Development of a versatile and fast algorithm for the optimal ship routing
**Org:** INCOIS, Ministry of Earth Sciences · **Team:** Delta Force

---

## The important thing about this PS

Read the Expected Solution again:

> *"Identification of a versatile optimization method and development of a reasonably fast
> algorithm, preferably written in an open-source programming language such as Python"*

**The algorithm is the deliverable, not the data pipeline.** INCOIS already has the data and
says they will provide it. So the build is engine-first: everything sits behind one
`ForcingField` interface, and swapping analytic fields for real INCOIS feeds changes nothing
in the router.

---

## Status

| Source | What it gives | Status |
|---|---|---|
| **Analytic field** (`SyntheticIndianOcean`) | currents, waves, wind, moving storm | ✅ working, used for validation |
| **INCOIS OSF** | the PS's own forecast source | ⬜ **needs a request email — do this first** |
| HYCOM / RTOFS NCSS | global ocean currents, NetCDF | ⚠️ endpoints not responding when probed |
| NOAA NOMADS | GFS winds, GFS-Wave waves (GRIB2) | ✅ server reachable; GRIB parsing on Windows needs eccodes |
| Copernicus Marine | currents + waves, NetCDF | ⬜ free registration required |
| `global-land-mask` | land/sea mask | ✅ installed and verified |

### Why analytic fields are the right starting point, not a shortcut

They are **known-answer tests**. The field contains a westward jet at 5°S, an Arabian Sea
gyre, and a storm drifting east at 9 km/h. We know what a correct optimiser should do with
each. Real forecast data cannot tell you whether your router is correct — it has no ground
truth. This does.

The storm **moves**, which is the whole point: the cost of a route depends on *when* you
arrive. A static shortest-path solver cannot represent that, and our departure-time
experiment measures it directly.

---

## Action items

1. **Email INCOIS this week** requesting access to the surface current, wave and wind
   forecasts referenced in the PS. Lead time is the risk here, not difficulty. A reply from
   INCOIS is also a credibility asset in the presentation.
2. **Register for Copernicus Marine** as the fallback — free, NetCDF, no GRIB pain.
3. Coastlines and bathymetry: `global-land-mask` covers land. For shallow-water and
   under-keel-clearance constraints we will need GEBCO or ETOPO bathymetry.

---

## Current results (Mumbai JNPT → Port Louis, Handymax bulker, 0.5° grid)

| Route | Time | Fuel | Peak risk |
|---|---|---|---|
| Straight line, same grid | — | — | **UNNAVIGABLE** — sails into the storm |
| Great circle (continuous) | 179.0 h | 347.2 t | 0.63 |
| Time-optimal | 180.2 h | 341.2 t | 0.41 |
| Fuel-optimal | 180.3 h | 340.0 t | 0.38 |
| Safety-first | 185.6 h | 346.6 t | 0.38 |

**The headline is safety, not fuel.** The naive same-grid straight line is *unnavigable* —
it puts the ship into conditions beyond its limit. Our router finds a passage and cuts peak
risk from 0.63 to 0.38 (−40%) against the great circle, while also saving 2.1% fuel and
costing 0.7% more time.

That framing matters for the pitch: the PS explicitly says *"to avoid loss of life and
property, route weather safety needs to be considered."* We answer that directly.

---

## Performance

"Reasonably fast" is an explicit requirement, so it is measured, not assumed.

| Change | Fuel-optimal solve |
|---|---|
| Naive | 21.3 s |
| + precomputed edge geometry & cached heuristic | **12.0 s** |

Profiling drove this. `haversine_km` was called 3.9M times and dominated the profile — but
edge distance and bearing depend only on the latitude row and the neighbour offset, never on
time or search state. Precomputing them per row cut the solve nearly in half with **identical
output** (same route, same 111,455 nodes expanded).

A forcing-lookup cache was also tried and **rejected**: 80.5% hit rate but no speedup,
because with analytic fields `at()` is cheap. `CachedForcing` is kept but off by default —
it will matter once `at()` does real interpolation from a NetCDF grid, where it is expensive.

Still to do on speed: coarser time buckets, a tightened heuristic for the risk-weighted
objective (safety-first still expands 224k nodes), and an isochrone solver as a fast
first-pass.

---

## Next

- Isochrone method as a second algorithm — the classical marine technique, and the PS asks
  for a *versatile* method, so having two with a comparison is the honest answer.
- Real forcing loader once INCOIS or Copernicus access lands.
- Variable-speed optimisation (throttle as a decision variable, not fixed at service speed).
  This is where most real fuel saving lives and is the single biggest modelling gap today.
