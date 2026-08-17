"""Surface-cover fractions for a scene.

WHAT THIS IS, AND WHAT IT IS NOT
--------------------------------
The obvious feature request is "tell me the percentage of forest / water / land from the
SAR image". We measured whether C-band SAR can actually do that, over all 446 chips,
calibrating on one set of regions and testing on regions the model had never seen. It
mostly cannot, and shipping five confident percentages would have been a lie:

    class        held-out IoU    per-scene area error     verdict
    water              52.5%     7.0 pp                   inferior to our CNN
    dense veg          54.3%     16.3 pp (ref mean 37.8)  too coarse to print
    low veg            22.3%     18.6 pp (ref mean 32.6)  no
    bare               13.7%     15.8 pp (ref mean 10.6)  error > the quantity
    built-up            0.0%     -                        not separable at all

Built-up scored AUC 0.483 against bare soil - below chance - and the NDBI "built"
reference label is itself invalid: it assigns 26% of rural Pakistani flood plain to
buildings, one chip as high as 84%. We cannot even score urban honestly, in either
direction. In arid regions the whole classifier lands *below* the majority-class
baseline (Pakistan -13.6 pp, Somalia -14.4 pp) - worse than guessing.

The ceiling is physics, not model capacity: a 60-tree random forest at depth 14 beats a
depth-4 decision tree by 0.66 pp. More model does not help.

So this module does NOT estimate land cover from SAR. It computes cover from the
CO-REGISTERED SENTINEL-2 OPTICAL chip, which is the instrument that actually measures
surface reflectance, and it labels every number as optical-derived. Water stays the
SAR model's job, because our trained CNN (IoU 0.681) beats optical MNDWI thresholding
on the same scenes.

For a user-uploaded SAR file there is no optical counterpart, so cover is reported as
unavailable rather than guessed.

MEASURED CONSTANTS
------------------
Every threshold below came from a census of the corpus, not from a textbook.
"""
from __future__ import annotations

import numpy as np

#: Sentinel-2 L1C band order in Sen1Floods11's S2Hand rasters.
B_BLUE, B_GREEN, B_RED, B_NIR, B_SWIR1 = 1, 2, 3, 7, 11

#: Cloud flag. The cirrus band (B10) is nearly useless here - best F1 0.311, and every
#: OR-combination with blue scored WORSE than blue alone. A plain blue-reflectance
#: threshold reaches F1 0.693, and it independently reproduces the human labeller's
#: "unlabelled" mask at chip level (Spearman rho 0.897, median |difference| 0.011).
CLOUD_BLUE = 0.20

#: MNDWI water cut. Xu (2006) says 0.0; measured optimum against the hand labels is
#: 0.16 (IoU 0.749 vs 0.615 at the literature value). Split-half over 200 repeats gives
#: a held-out IoU of 0.743 +/- 0.020 and a selected threshold of 0.167 +/- 0.030, so the
#: number is stable rather than overfitted.
MNDWI_WATER = 0.16

#: NDVI bands. These are DENSITY BANDS, deliberately named after what they measure
#: rather than after land-cover classes. Smoothed NDVI over ~8.7e7 clear land pixels is
#: a unimodal continuum with no robust interior minimum, so there is no discoverable
#: forest/cropland boundary - any single cut is a choice, not a finding. Calling a
#: bucket "forest" would be inventing a category the data does not contain.
NDVI_BARE, NDVI_SPARSE, NDVI_DENSE = 0.20, 0.40, 0.60


def _idx(a: np.ndarray, i: int, j: int) -> np.ndarray:
    """Normalised difference index, safe against the 0/0 that nodata produces."""
    num, den = a[i] - a[j], a[i] + a[j]
    return np.divide(num, den, out=np.zeros_like(num), where=np.abs(den) > 1e-6)


def cover_from_s2(s2: np.ndarray, label: np.ndarray | None = None) -> dict:
    """Surface-cover fractions from a [13,H,W] Sentinel-2 L1C chip.

    Returns fractions of the *analysable* area - cloud and nodata are excluded from the
    denominator and reported separately, so the percentages describe what was actually
    seen rather than being quietly diluted by cloud.
    """
    a = s2.astype(np.float32) / 10000.0
    valid = np.isfinite(a).all(0) & (a.sum(0) > 0)
    if label is not None:
        valid &= label != -1                     # -1 is no-data, not "not water"

    cloud = valid & (a[B_BLUE] > CLOUD_BLUE)
    clear = valid & ~cloud
    n = int(clear.sum())
    if n == 0:
        return {"usable": False, "reason": "no cloud-free, in-swath pixels",
                "cloud_fraction": round(float(cloud.sum()) / max(int(valid.sum()), 1), 4),
                "classes": []}

    mndwi = _idx(a, B_GREEN, B_SWIR1)
    ndvi = _idx(a, B_NIR, B_RED)

    water = clear & (mndwi > MNDWI_WATER)
    land = clear & ~water
    dense = land & (ndvi >= NDVI_DENSE)
    moderate = land & (ndvi >= NDVI_SPARSE) & (ndvi < NDVI_DENSE)
    sparse = land & (ndvi >= NDVI_BARE) & (ndvi < NDVI_SPARSE)
    bare = land & (ndvi < NDVI_BARE)

    def pct(m):
        return round(100.0 * float(m.sum()) / n, 2)

    return {
        "usable": True,
        "source": "Sentinel-2 optical, co-registered",
        "analysed_px": n,
        "cloud_fraction": round(float(cloud.sum()) / max(int(valid.sum()), 1), 4),
        "median_ndvi": round(float(np.median(ndvi[land])), 3) if land.any() else None,
        "classes": [
            {"key": "water", "label": "Open water",
             "pct": pct(water), "note": f"MNDWI > {MNDWI_WATER}"},
            {"key": "dense", "label": "Dense vegetation",
             "pct": pct(dense), "note": f"NDVI >= {NDVI_DENSE}"},
            {"key": "moderate", "label": "Moderate vegetation",
             "pct": pct(moderate), "note": f"NDVI {NDVI_SPARSE}-{NDVI_DENSE}"},
            {"key": "sparse", "label": "Sparse vegetation",
             "pct": pct(sparse), "note": f"NDVI {NDVI_BARE}-{NDVI_SPARSE}"},
            {"key": "bare", "label": "Bare / non-vegetated",
             "pct": pct(bare), "note": f"NDVI < {NDVI_BARE}"},
        ],
        #: Deliberately absent: built-up. See the module docstring - it is not separable
        #: from bare soil at C-band (AUC 0.483) and its optical reference label is
        #: invalid. Reporting it as 0% would be as misleading as reporting it wrong.
        "not_reported": ["built-up"],
        "caveat": (
            "Cover fractions are measured from the co-registered Sentinel-2 optical "
            "chip, not from the radar. Built-up area is not reported: it is not "
            "separable from bare soil at C-band and its optical reference is unreliable."
        ),
    }
