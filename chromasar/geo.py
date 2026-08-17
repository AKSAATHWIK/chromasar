"""Where on Earth a scene is, and how big its pixels really are.

Two jobs, both of which the app was previously getting wrong or not doing at all.

**Pixel area.** Sen1Floods11 GeoTIFFs are in a *geographic* CRS - GeoKeyDirectoryTag
key 1024 (GTModelTypeGeoKey) is 2, ModelTypeGeographic, and GeoAsciiParamsTag reads
"WGS 84". So ModelPixelScaleTag is in DEGREES, not metres. A degree of latitude is
~111 km everywhere, but a degree of longitude shrinks as cos(latitude), so a "10 m"
pixel is 10.0 m north-south and only 7.8 m east-west at 38 deg N.

The app assumed a flat 100 m^2 per pixel. Measured against the real tiepoints, that
overstates ground area by:

    Somalia   +0.3%     Nigeria   +1.2%     Sri-Lanka +1.0%
    Ghana     +1.3%     Bolivia   +2.3%     Mekong    +2.5%
    Paraguay  +9.7%     India    +11.9%     Pakistan +14.6%
    Spain    +27.4%     USA      +28.4%

Flood extent in km^2 is the headline number on the flood tab, and India and Pakistan -
the two regions an SIH panel is most likely to ask about - were reading 12-15% high.

**Location.** Bounding boxes, not centroids. A nearest-centroid lookup silently returns
a confident wrong answer for anything coastal, and there is no worse failure mode for a
geolocation readout than being plausibly wrong. Every box below was checked against the
actual corpus tiepoints. Anything outside every box returns None rather than a guess.
"""
from __future__ import annotations

import math
from typing import NamedTuple

#: WGS84 arc-length coefficients. Standard series expansion, accurate to well under a
#: metre per degree - far tighter than the 10 m pixels we are measuring.
def _m_per_deg_lat(lat_deg: float) -> float:
    p = math.radians(lat_deg)
    return (111132.92 - 559.82 * math.cos(2 * p)
            + 1.175 * math.cos(4 * p) - 0.0023 * math.cos(6 * p))


def _m_per_deg_lon(lat_deg: float) -> float:
    p = math.radians(lat_deg)
    return (111412.84 * math.cos(p) - 93.5 * math.cos(3 * p)
            + 0.118 * math.cos(5 * p))


class Geo(NamedTuple):
    """Georeferencing resolved from a GeoTIFF, with real ground measurements."""
    lat: float                 # centre
    lon: float
    bounds: tuple              # (south, west, north, east)
    pixel_m2: float            # true ground area of one pixel
    pixel_ew_m: float
    pixel_ns_m: float
    country: str | None
    continent: str | None

    @property
    def label(self) -> str:
        """Human-readable place, honest when unknown."""
        if self.country and self.continent:
            return f"{self.country}, {self.continent}"
        if self.continent:
            return self.continent
        return "location outside reference set"

    @property
    def dms(self) -> str:
        ns = "N" if self.lat >= 0 else "S"
        ew = "E" if self.lon >= 0 else "W"
        return f"{abs(self.lat):.4f}°{ns} {abs(self.lon):.4f}°{ew}"


def read_geotiff_geo(path, shape=None) -> Geo | None:
    """Pull georeferencing out of a GeoTIFF. Returns None if the file carries none.

    Uploads from other sources may be ungeoreferenced, and that has to degrade to
    "unknown location" rather than to a fabricated coordinate.
    """
    import tifffile

    with tifffile.TiffFile(path) as t:
        page = t.pages[0]
        tags = page.tags
        if 33922 not in tags or 33550 not in tags:
            return None
        tie = tags[33922].value          # (i, j, k, x, y, z) for a raster point
        scale = tags[33550].value        # (dx, dy, dz) in CRS units
        h, w = (shape or page.shape[-2:])

    lon0, lat0 = float(tie[3]), float(tie[4])
    dlon, dlat = abs(float(scale[0])), abs(float(scale[1]))

    # tiepoint is the top-left corner; latitude decreases going down the raster
    north, west = lat0, lon0
    south, east = lat0 - dlat * h, lon0 + dlon * w
    lat, lon = (north + south) / 2.0, (west + east) / 2.0

    ew = dlon * _m_per_deg_lon(lat)
    ns = dlat * _m_per_deg_lat(lat)
    country, continent = locate(lat, lon)
    return Geo(lat=lat, lon=lon, bounds=(south, west, north, east),
               pixel_m2=ew * ns, pixel_ew_m=ew, pixel_ns_m=ns,
               country=country, continent=continent)


def pixel_km2(lat: float, deg_per_px: float = 8.983152841195215e-05) -> float:
    """Ground area of one pixel in km^2 at a given latitude.

    The default degrees-per-pixel is the Sen1Floods11 value (nominally 10 m).
    """
    return (deg_per_px * _m_per_deg_lon(lat)) * (deg_per_px * _m_per_deg_lat(lat)) / 1e6


#: (south, west, north, east) -> (country, continent).
#: Deliberately bounding boxes rather than centroids: a nearest-centroid lookup answers
#: confidently and wrongly for coastal points, and these boxes are checked against the
#: real tiepoints of all 446 corpus chips.
#:
#: Boxes for real countries overlap - India's box contains most of Pakistan and all of
#: Sri Lanka - so declaration order silently decided the answer, and the first draft of
#: this table duly reported Pakistani and Sri Lankan chips as "India". They are sorted
#: by area at import time instead, smallest first, so the tightest containing box always
#: wins and the coarse continental fallbacks are only reached when nothing else matches.
_BOXES: list[tuple[tuple[float, float, float, float], str, str]] = [
    # --- the eleven Sen1Floods11 regions, verified against corpus tiepoints ---
    # east limit is 97.5, not 89.5: Arunachal reaches 97.4E and the Assam flood chips
    # sit at 92.9E, so a 89.5 cut-off dropped every Brahmaputra scene to "Asia".
    ((5.5, 68.0, 35.7, 97.5), "India", "Asia"),
    ((23.5, 60.8, 37.1, 77.9), "Pakistan", "Asia"),
    ((5.8, 79.5, 10.0, 82.0), "Sri Lanka", "Asia"),
    ((8.0, 102.0, 23.4, 109.5), "Vietnam", "Asia"),
    ((9.9, 97.3, 20.5, 105.7), "Thailand", "Asia"),
    ((9.5, 102.3, 14.7, 107.7), "Cambodia", "Asia"),
    ((13.9, 100.0, 22.5, 107.7), "Laos", "Asia"),
    ((-1.7, 40.9, 12.0, 51.5), "Somalia", "Africa"),
    ((4.7, -3.3, 11.2, 1.2), "Ghana", "Africa"),
    ((4.2, 2.6, 13.9, 14.7), "Nigeria", "Africa"),
    ((35.9, -9.4, 43.8, 3.4), "Spain", "Europe"),
    ((-22.9, -73.0, -9.6, -57.5), "Bolivia", "South America"),
    ((-27.6, -62.7, -19.2, -54.2), "Paraguay", "South America"),
    ((24.5, -125.0, 49.4, -66.9), "United States", "North America"),
    # --- coarse fallbacks so an arbitrary upload still gets a continent ---
    ((-56.0, -82.0, 13.5, -34.0), None, "South America"),
    ((7.0, -170.0, 72.0, -52.0), None, "North America"),
    ((-35.0, -18.0, 37.5, 51.5), None, "Africa"),
    ((34.0, -25.0, 71.5, 45.0), None, "Europe"),
    ((-11.0, 25.0, 78.0, 180.0), None, "Asia"),
    ((-50.0, 110.0, -9.0, 180.0), None, "Oceania"),
    ((-90.0, -180.0, -60.0, 180.0), None, "Antarctica"),
]

#: Smallest box first. Sri Lanka (10.5 deg^2) beats India (891 deg^2) on a point they
#: both contain, and every named country beats every continental fallback.
_BOXES.sort(key=lambda b: (b[0][2] - b[0][0]) * (b[0][3] - b[0][1]))


def locate(lat: float, lon: float):
    """(country, continent) for a point, or (None, None) when out of reference.

    Returning None is the point of this function. A geolocation readout that is
    confidently wrong is worse than one that admits it does not know.
    """
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None, None
    for (s, w, n, e), country, continent in _BOXES:
        if s <= lat <= n and w <= lon <= e:
            return country, continent
    return None, None
