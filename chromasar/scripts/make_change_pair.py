"""Build a before/after SAR pair for the change-detection demo.

WHY THIS SCRIPT EXISTS, AND WHAT IT IS NOT
------------------------------------------
Change detection needs two acquisitions of the SAME footprint at different dates.
Sen1Floods11 does not contain one: it ships a single acquisition per site, and the 446
chips are disjoint tiles. Measured, not assumed - every pair of chips in the same region
was checked for footprint overlap and **not one pair overlaps by even 15%**.

So this synthesises a "before" from a real flooded scene. The flood chip becomes the
AFTER, unchanged and real. The BEFORE is that same chip with the flooded pixels replaced
by dry-land texture taken from elsewhere in the SAME acquisition - a mirror of the scene,
falling back to sampling the scene's own dry pixels where the mirror is also flooded.

That last detail matters: the infill is REAL SAR texture from the same image, so speckle
statistics, spatial correlation length and the sensor's noise floor are all genuine. What
is synthetic is the *history*, not the pixels.

WHAT IT IS HONEST TO CLAIM
  - "This demonstrates the change-detection pipeline end to end."
  - "The before image is synthesised; we say so, and here is exactly how."

WHAT IT IS NOT HONEST TO CLAIM
  - "These are two Sentinel-1 passes over the same place."   <- NEVER say this
  - Any accuracy number derived from this pair. There is no ground truth for a
    before-image we invented, so the change output cannot be scored against anything.

For the real thing, download two dates over one footprint from Copernicus Browser or ASF
Vertex (search the same tile, pick dates either side of a flood) and drop those in. The
app does not care where the files came from.

    python chromasar/scripts/make_change_pair.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import tifffile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

#: Chips with a lot of real flood, so the change map has something obvious to find.
CANDIDATES = ["India_1018317", "India_1017769", "Pakistan_1027214"]


def synth_before(sar: np.ndarray, flood: np.ndarray, seed: int = 0) -> np.ndarray:
    """Replace flooded pixels with dry texture drawn from the same acquisition."""
    rng = np.random.default_rng(seed)
    out = sar.copy()
    # 1) mirror infill - real texture, real speckle, from the same image
    mirrored = sar[:, :, ::-1]
    mirror_flood = flood[:, ::-1]
    take = flood & ~mirror_flood
    for b in range(out.shape[0]):
        out[b][take] = mirrored[b][take]

    # 2) anything still flooded in both the scene and its mirror: sample the scene's own
    #    dry distribution. Loses spatial correlation, so it is the fallback, not the plan.
    left = flood & mirror_flood
    if left.any():
        for b in range(out.shape[0]):
            dry = sar[b][~flood]
            dry = dry[np.isfinite(dry)]
            if dry.size == 0:
                continue
            out[b][left] = rng.choice(dry, size=int(left.sum()), replace=True)
    return out


def main() -> int:
    data = Path(os.environ.get("SIH_DATA", Path.home() / "sih-data"))
    root = data / "sen1floods11"
    out = Path(__file__).resolve().parents[2] / "demo-uploads"
    out.mkdir(exist_ok=True)

    scene = None
    for c in CANDIDATES:
        if (root / "S1Hand" / f"{c}_S1Hand.tif").exists():
            scene = c
            break
    if scene is None:
        print("no candidate scene found under", root / "S1Hand")
        return 1

    s1 = tifffile.imread(root / "S1Hand" / f"{scene}_S1Hand.tif").astype(np.float32)
    lab = tifffile.imread(root / "LabelHand" / f"{scene}_LabelHand.tif").astype(np.int16)
    flood = lab == 1
    print(f"scene {scene}: {100 * flood.mean():.1f}% of pixels labelled water")

    before = synth_before(s1[:2], flood)
    after = s1[:2]

    # carry the georeferencing across, or the pair loses its location and the app
    # correctly reports "unknown" for a scene we know perfectly well
    with tifffile.TiffFile(root / "S1Hand" / f"{scene}_S1Hand.tif") as t:
        tags = t.pages[0].tags
        extra = [(c, tags[c].dtype, tags[c].count, tags[c].value, True)
                 for c in (33550, 33922, 34735, 34736, 34737) if c in tags]

    bp = out / "change-BEFORE-synthetic.tif"
    ap = out / "change-AFTER-real.tif"
    tifffile.imwrite(bp, before, extratags=extra)
    tifffile.imwrite(ap, after, extratags=extra)

    d_vv = float(np.nanmean(after[0][flood] - before[0][flood]))
    print(f"wrote {bp.name}  (flooded pixels replaced with dry texture)")
    print(f"wrote {ap.name}  (untouched real acquisition)")
    print(f"mean VV change inside the flood mask: {d_vv:+.2f} dB "
          f"(negative = surface became smooth = new water)")

    # a null pair too: identical files must produce NO change. If the tool invents
    # change here, nothing else it says can be trusted.
    tifffile.imwrite(out / "change-NULL-a.tif", after, extratags=extra)
    tifffile.imwrite(out / "change-NULL-b.tif", after, extratags=extra)
    print("wrote change-NULL-a.tif / change-NULL-b.tif  (identical - must report ~0 change)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
