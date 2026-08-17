"""Full integrity check on the downloaded SEN1-2 subset.

Opens and decodes every file - a PNG that lists fine can still be truncated, and a
truncated patch will fail mid-training rather than up front.

    python scripts/verify_data.py --dest $SIH_DATA/sen1-2
"""
import argparse
import hashlib
import os
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PIL import Image

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from config import SEN12_DIR



def check_one(args):
    path, expect_mode = args
    try:
        with Image.open(path) as im:
            im.load()                       # forces full decode - catches truncation
            mode, size = im.mode, im.size
            arr = np.asarray(im)
        h = hashlib.md5(arr.tobytes()).hexdigest()
        problems = []
        if size != (256, 256):
            problems.append(f"size {size}")
        if mode != expect_mode:
            problems.append(f"mode {mode} (expected {expect_mode})")
        const = bool(arr.min() == arr.max())
        return path, h, problems, const, int(arr.min()), int(arr.max())
    except Exception as e:                                       # noqa: BLE001
        return path, None, [f"UNREADABLE: {e}"], False, 0, 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default=str(SEN12_DIR))
    args = ap.parse_args()
    s1d, s2d = os.path.join(args.dest, "s1"), os.path.join(args.dest, "s2")

    s1 = sorted(f for f in os.listdir(s1d) if f.endswith(".png"))
    s2 = sorted(f for f in os.listdir(s2d) if f.endswith(".png"))
    parts = ([f for f in os.listdir(s1d) if f.endswith(".part")]
             + [f for f in os.listdir(s2d) if f.endswith(".part")])
    print(f"SAR patches     : {len(s1)}")
    print(f"optical patches : {len(s2)}")
    print(f"stray .part     : {len(parts)}")

    # ---- pairing --------------------------------------------------------
    k1 = {f.replace("_s1_", "_X_") for f in s1}
    k2 = {f.replace("_s2_", "_X_") for f in s2}
    only1, only2 = k1 - k2, k2 - k1
    print(f"\nPAIRING  unmatched SAR: {len(only1)}   unmatched optical: {len(only2)}")
    for f in list(only1)[:5]:
        print("   orphan SAR:", f)
    for f in list(only2)[:5]:
        print("   orphan optical:", f)

    # ---- decode every file ---------------------------------------------
    jobs = ([(os.path.join(s1d, f), "L") for f in s1]
            + [(os.path.join(s2d, f), "RGB") for f in s2])
    print(f"\nDecoding {len(jobs)} files...")
    bad, consts, hashes = [], [], defaultdict(list)
    zero_files = 0
    with ThreadPoolExecutor(max_workers=12) as ex:
        for path, h, problems, const, lo, hi in ex.map(check_one, jobs, chunksize=64):
            if problems:
                bad.append((path, problems))
            if const:
                consts.append((path, lo))
            if h:
                hashes[h].append(path)
            if os.path.getsize(path) == 0:
                zero_files += 1

    print(f"  corrupt / wrong-shape : {len(bad)}")
    for p, pr in bad[:10]:
        print(f"     {os.path.basename(p)}: {', '.join(pr)}")
    print(f"  zero-byte files       : {zero_files}")
    print(f"  constant (flat) images: {len(consts)}")
    for p, lo in consts[:6]:
        print(f"     {os.path.basename(p)} all={lo}")

    # ---- duplicates -----------------------------------------------------
    dupes = {h: ps for h, ps in hashes.items() if len(ps) > 1}
    n_dup_files = sum(len(p) - 1 for p in dupes.values())
    print(f"\nDUPLICATES  {len(dupes)} repeated images, {n_dup_files} redundant files")
    for h, ps in list(dupes.items())[:5]:
        print(f"   x{len(ps)}: {os.path.basename(ps[0])}")

    # ---- distribution ---------------------------------------------------
    season = Counter(f.split("_s1_")[0] for f in s1)
    scenes = Counter(f.split("_p")[0] for f in s1)
    print(f"\nDISTRIBUTION  {len(scenes)} distinct scenes")
    for s, n in sorted(season.items()):
        sc = len({k for k in scenes if k.startswith(s)})
        print(f"   {s:22s} {n:5d} pairs across {sc:3d} scenes")
    top = scenes.most_common(3)
    print("   largest scenes: " + ", ".join(f"{k.split('_s1_')[-1]}={v}" for k, v in top))
    conc = 100 * top[0][1] / len(s1)
    print(f"   most-represented scene is {conc:.1f}% of the set")

    ok = (not bad and not only1 and not only2 and not parts and zero_files == 0)
    print("\n" + ("PASS - dataset is training-ready" if ok
                  else "ISSUES FOUND - see above"))


if __name__ == "__main__":
    main()
