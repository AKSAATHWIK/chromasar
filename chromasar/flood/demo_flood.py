"""Flood-mapping demo panel: SAR -> predicted water -> hand-labelled truth.

    python flood/demo_flood.py
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from flood import evaluate, load_chip, water_mask                # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")


def db_to_img(vv, lo=-25, hi=0):
    a = np.clip((vv - lo) / (hi - lo), 0, 1)
    a[~np.isfinite(vv)] = 0
    return a


def main():
    os.makedirs(OUT, exist_ok=True)
    res = evaluate("test", "dualpol")
    rows = [r for r in res["rows"] if r["water_frac_true"] > 0.05]
    rows.sort(key=lambda r: -r["iou"])
    picks = rows[:3] + rows[-2:]                 # best three and worst two - honest
    print(f"test micro-IoU {res['micro']['iou']:.3f} over {res['n']} chips")

    fig, axes = plt.subplots(len(picks), 4, figsize=(13.2, 3.05 * len(picks)))
    for r, axrow in zip(picks, axes):
        sar, lab = load_chip(r["name"])
        pred, thr = water_mask(sar)
        vv = sar[0]

        axrow[0].imshow(db_to_img(vv), cmap="gray")
        axrow[0].set_ylabel(r["name"][:18], fontsize=8)
        axrow[0].set_title("Sentinel-1 VV (dB)" if r is picks[0] else "", fontsize=10)

        axrow[1].imshow(db_to_img(vv), cmap="gray")
        m = np.ma.masked_where(~pred, pred)
        axrow[1].imshow(m, cmap="cool", alpha=0.65, vmin=0, vmax=1)
        axrow[1].set_title("predicted water" if r is picks[0] else "", fontsize=10)

        truth = np.ma.masked_where(lab != 1, lab)
        axrow[2].imshow(db_to_img(vv), cmap="gray")
        axrow[2].imshow(truth, cmap="autumn", alpha=0.65, vmin=0, vmax=1)
        axrow[2].set_title("hand-labelled truth" if r is picks[0] else "", fontsize=10)

        # agreement map: green TP, red FP, blue FN, grey unlabelled
        valid = lab >= 0
        rgb = np.zeros((*lab.shape, 3))
        rgb[~valid] = 0.55
        tp = valid & pred & (lab == 1)
        fp = valid & pred & (lab == 0)
        fn = valid & ~pred & (lab == 1)
        rgb[tp] = [0.10, 0.70, 0.25]
        rgb[fp] = [0.85, 0.15, 0.15]
        rgb[fn] = [0.15, 0.35, 0.90]
        axrow[3].imshow(rgb)
        axrow[3].set_title("green=hit  red=false  blue=miss" if r is picks[0] else "",
                           fontsize=9)
        axrow[3].set_xlabel(f"IoU {r['iou']:.2f}  P {r['precision']:.2f}  "
                            f"R {r['recall']:.2f}", fontsize=8)
        for a in axrow:
            a.set_xticks([])
            a.set_yticks([])

    mi = res["micro"]
    fig.suptitle(f"Flood mapping from SAR — Sen1Floods11 test split  |  "
                 f"IoU {mi['iou']:.3f}   precision {mi['precision']:.3f}   "
                 f"recall {mi['recall']:.3f}   (dual-pol VV<-18.5 OR VH<-24 dB, tuned on validation)",
                 fontsize=11.5, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.975])
    p = os.path.join(OUT, "flood_demo.png")
    fig.savefig(p, dpi=125)
    print("wrote", p)


if __name__ == "__main__":
    main()
