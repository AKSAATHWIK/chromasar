"""Turn a real Sentinel-1 download into a file the app will actually accept.

"Show me it working on a scene you did not pick" is the question we are least ready for,
and the blocker is not the model - it is the format. `/api/flood/upload` requires a
2-band GeoTIFF, VV and VH, in DECIBELS, with georeferencing intact. What you can download
is none of those things:

  ASF HyP3 RTC   two SEPARATE GeoTIFFs, one per polarisation, in gamma0 POWER
  Copernicus GRD a 1 GB .SAFE with DN integers, no calibration, no terrain correction

This script closes the gap for the HyP3 route, which is the only one that does not need
SNAP and several hours. It stacks VV and VH into one file, converts power to dB if
needed, copies the georeferencing across so the scene still knows where it is, and
optionally crops to something that infers in about a second.

    # 1. search.asf.alaska.edu -> pick a scene -> "RTC GAMMA" On Demand -> download
    # 2. unzip it, then:
    python chromasar/scripts/prep_sentinel1.py <folder-with-VV-and-VH-tifs> out.tif

    # already in dB, or oddly named:
    python chromasar/scripts/prep_sentinel1.py VV.tif VH.tif out.tif --db --crop 1024

Then upload out.tif in the Flood tab. If it is rejected, the error says exactly which of
the three rules it broke.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import tifffile

GEO_TAGS = (33550, 33922, 34735, 34736, 34737)   # scale, tiepoint, keys, doubles, ascii


def find_pair(folder: Path):
    """HyP3 names them *_VV.tif / *_VH.tif. Be forgiving about case and suffixes."""
    tifs = sorted(p for p in folder.glob("*.tif") if p.is_file())
    vv = [p for p in tifs if "_vv" in p.name.lower() or p.stem.lower().endswith("vv")]
    vh = [p for p in tifs if "_vh" in p.name.lower() or p.stem.lower().endswith("vh")]
    if not vv or not vh:
        print(f"could not find a VV and a VH .tif in {folder}")
        print("files present:", [p.name for p in tifs] or "none")
        return None, None
    return vv[0], vh[0]


def to_db(a: np.ndarray, already_db: bool) -> np.ndarray:
    if already_db:
        return a
    # HyP3 RTC gamma0 ships as power. 10*log10 is the conversion; guard the zeros that
    # radiometric terrain correction leaves in layover/shadow so they become no-data
    # rather than -inf.
    out = np.full(a.shape, np.nan, dtype=np.float32)
    pos = a > 0
    out[pos] = 10.0 * np.log10(a[pos])
    return out


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    crop = 0
    for i, a in enumerate(sys.argv):
        if a == "--crop" and i + 1 < len(sys.argv):
            crop = int(sys.argv[i + 1])
            args = [x for x in args if x != sys.argv[i + 1]]

    if len(args) == 2 and Path(args[0]).is_dir():
        vv_p, vh_p = find_pair(Path(args[0]))
        out = Path(args[1])
    elif len(args) == 3:
        vv_p, vh_p, out = Path(args[0]), Path(args[1]), Path(args[2])
    else:
        print(__doc__)
        return 2
    if vv_p is None:
        return 1

    print(f"VV : {vv_p.name}")
    print(f"VH : {vh_p.name}")
    vv = tifffile.imread(str(vv_p)).astype(np.float32)
    vh = tifffile.imread(str(vh_p)).astype(np.float32)
    if vv.shape != vh.shape:
        print(f"shape mismatch: VV {vv.shape} vs VH {vh.shape} - not a matched pair")
        return 1

    already = "--db" in flags
    lo, hi = float(np.nanmin(vv)), float(np.nanmax(vv))
    if not already and lo < 0:
        print(f"  input range {lo:.1f}..{hi:.1f} already looks like dB; not converting")
        already = True
    vv, vh = to_db(vv, already), to_db(vh, already)

    if crop:                       # centre crop - inference is ~1 s at 1024
        h, w = vv.shape
        if h > crop or w > crop:
            y, x = max(0, (h - crop) // 2), max(0, (w - crop) // 2)
            vv, vh = vv[y:y + crop, x:x + crop], vh[y:y + crop, x:x + crop]
            print(f"  cropped {h}x{w} -> {vv.shape[0]}x{vv.shape[1]}")

    stack = np.stack([vv, vh]).astype(np.float32)

    # Carry the georeferencing over, or the scene lands as "unknown location" and the
    # area figures are meaningless - which is exactly the thing we fixed once already.
    geotags = []
    with tifffile.TiffFile(str(vv_p)) as tf:
        page = tf.pages[0]
        for code in GEO_TAGS:
            tag = page.tags.get(code)
            if tag is not None:
                geotags.append((code, tag.dtype, tag.count, tag.value, True))
    print(f"  georeferencing tags carried over: {len(geotags)}/{len(GEO_TAGS)}"
          + ("" if geotags else "  <-- WARNING: scene will show as unknown location"))

    tifffile.imwrite(str(out), stack, extratags=geotags,
                     description="ChromaSAR: VV+VH, dB, from Sentinel-1 RTC")

    fin = np.isfinite(stack)
    print(f"\nwrote {out}  shape {list(stack.shape)}  "
          f"{out.stat().st_size / 1048576:.1f} MB")
    print(f"  dB range {float(np.nanmin(stack[fin])):.1f} .. "
          f"{float(np.nanmax(stack[fin])):.1f}")
    ok = (stack.ndim == 3 and stack.shape[0] >= 2
          and np.nanmax(stack[fin]) <= 60 and np.nanmin(stack[fin]) >= -80)
    print("\n" + ("PASSES the upload checks - drop it in the Flood tab."
                  if ok else "WILL BE REJECTED - check the dB range above."))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
