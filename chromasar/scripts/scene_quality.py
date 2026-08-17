"""Per-scene optical quality over EVERY downloaded patch.

analyze.py samples, so its per-scene verdict rests on ~15 patches. Scene-level exclusion
is a decision about thousands of training samples at a time, so it deserves the full
sweep rather than a sample.

Signal: natural-colour imagery has strongly correlated R/G/B channels. False-colour or
corrupted optical targets decorrelate them while staying highly saturated.

    python scripts/scene_quality.py --dest $SIH_DATA/sen1-2
"""
import argparse
import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PIL import Image, ImageDraw

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from config import SEN12_DIR


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS = os.path.join(ROOT, "reports")


def stats_one(path):
    with Image.open(path) as im:
        a = np.asarray(im.convert("RGB"), dtype=np.float64)
    f = a.reshape(-1, 3)
    sd = f.std(0)
    if np.all(sd > 1e-6):
        c = np.corrcoef(f.T)
        corr = float(np.nanmean([c[0, 1], c[0, 2], c[1, 2]]))
    else:
        corr = 1.0                      # flat image: no colour disagreement
    mx, mn = f.max(1), f.min(1)
    satur = float(np.mean((mx - mn) / np.maximum(mx, 1e-6)))
    ch = f.mean(0)
    # magenta index: green sitting below both red and blue. Vegetation, soil, rock and
    # water all keep green at or above the R/B midpoint, so a strongly negative value
    # means the colour balance is not physical.
    magenta = float(ch[1] - 0.5 * (ch[0] + ch[2]))
    return corr, satur, float(f.mean()), float(f.std()), magenta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default=str(SEN12_DIR))
    ap.add_argument("--corr", type=float, default=0.55, help="correlation floor")
    ap.add_argument("--sat", type=float, default=0.40, help="saturation ceiling")
    ap.add_argument("--mag", type=float, default=-20.0, help="extreme colour-imbalance floor")
    args = ap.parse_args()
    os.makedirs(REPORTS, exist_ok=True)

    s2d = os.path.join(args.dest, "s2")
    files = sorted(f for f in os.listdir(s2d) if f.endswith(".png"))
    print(f"sweeping all {len(files)} optical patches...")

    paths = [os.path.join(s2d, f) for f in files]
    with ThreadPoolExecutor(max_workers=12) as ex:
        res = list(ex.map(stats_one, paths, chunksize=64))

    scenes = defaultdict(list)
    for f, r in zip(files, res):
        scenes[f.split("_p")[0]].append(r)

    rows = []
    for scene, vals in scenes.items():
        v = np.array(vals)
        rows.append((scene, len(vals), float(v[:, 0].mean()), float(v[:, 1].mean()),
                     float(v[:, 2].mean()), float(v[:, 3].mean()), float(v[:, 4].mean())))
    rows.sort(key=lambda r: r[2])           # worst correlation first

    def verdict(r):
        """Exclude only what is demonstrably defective.

        A magenta-cast rule at -6 was tried and REJECTED after visual review: it
        flagged 24 scenes (14.9% of the set), but the montage showed most were desert
        dunes, ploughed farmland and red-soil terrain - all legitimate. Worse, arid
        reddish landscape is exactly the Thar/Deccan-type terrain we need for the
        Indian-deployment claim, so that filter would have biased the model against
        our own use case. Kept only as a guard against extreme values.
        """
        _, _, corr, sat, bright, sd, mag = r
        if bright < 45 and sd < 18:
            return "near-black (dark AND flat)"
        if corr < args.corr and sat > args.sat:
            return "channel decorrelation"
        if mag < args.mag:
            return f"extreme colour imbalance ({mag:.1f})"
        return None

    flagged = [r for r in rows if verdict(r)]
    print(f"\n{len(scenes)} scenes;  {len(flagged)} flagged\n")
    print(f"{'scene':30s} {'n':>4s} {'corr':>5s} {'sat':>5s} {'brt':>6s} {'sd':>5s} "
          f"{'mag':>6s}  verdict")
    shown = sorted(rows, key=lambda r: (verdict(r) is None, r[2]))[:18]
    for r in shown:
        scene, n, corr, sat, bright, sd, mag = r
        print(f"{scene:30s} {n:4d} {corr:5.2f} {sat:5.2f} {bright:6.1f} {sd:5.1f} "
              f"{mag:6.1f}  {verdict(r) or ''}")

    excl = os.path.join(REPORTS, "exclude_scenes.txt")
    with open(excl, "w", encoding="utf8") as fh:
        for r in flagged:
            scene = r[0]
            fh.write(scene + "\n")
    n_lost = sum(r[1] for r in flagged)
    print(f"\nwrote {excl}")
    print(f"excluding {len(flagged)} scenes removes {n_lost} pairs "
          f"({100 * n_lost / len(files):.1f}% of the set)")

    # montage of the worst scenes so the call can be made by eye
    worst = rows[:8]
    cell = 132
    img = Image.new("RGB", (8 * (cell + 6) + 6, cell + 26), "white")
    d = ImageDraw.Draw(img)
    for i, (scene, n, corr, sat, bright, sd, mag) in enumerate(worst):
        sample = next(f for f in files if f.startswith(scene + "_p"))
        with Image.open(os.path.join(s2d, sample)) as im:
            img.paste(im.convert("RGB").resize((cell, cell)), (6 + i * (cell + 6), 6))
        d.text((8 + i * (cell + 6), cell + 10),
               f"{scene.split('_s2_')[-1]}  r={corr:.2f}", fill="black")
    p = os.path.join(REPORTS, "worst_scenes.png")
    img.save(p)
    print(f"wrote {p}")


if __name__ == "__main__":
    main()
