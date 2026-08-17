"""Separate FLOOD water from water that is supposed to be there.

The metric a disaster manager needs is not "how much water is in this scene" — a river
is water, and it is meant to be. What matters is water where there normally is none.

Sen1Floods11 ships a JRC permanent-water layer, so:

    flood extent = detected water AND NOT permanent water

This costs no training at all: it is set arithmetic on an existing model's output. It
also changes the headline number from an ML metric into an operational one.

    python flood/extent.py --split test
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import tifffile
import torch

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
for p in (ROOT, os.path.join(ROOT, "train"), _HERE):
    sys.path.insert(0, p)

from config import DATA_ROOT, FLOODS_DIR, REPORTS               # noqa: E402
from flood import list_split                                    # noqa: E402
from resunet import ResUNet                                     # noqa: E402

PIXEL_M = 10.0                       # Sentinel-1 GRD ground sampling
PIXEL_KM2 = (PIXEL_M ** 2) / 1e6


def load_model(dev):
    ck_path = DATA_ROOT / "checkpoints" / "flood_resnet34.pt"
    m = ResUNet(2, 1, encoder="resnet34", pretrained=False, dropout=0.2, final=None)
    ck = torch.load(ck_path, map_location=dev, weights_only=False)
    m.load_state_dict(ck["model"])
    return m.eval().to(dev)


def predict(m, sar, dev, tta=False):
    """Water probability. With --tta, average over the 4 flips (free accuracy)."""
    x = np.clip(np.nan_to_num(sar, nan=-30.0), -30.0, 0.0)
    x = (x + 30.0) / 30.0 * 2.0 - 1.0
    views = [(x, None)]
    if tta:
        views = [(x, None), (x[:, :, ::-1], "h"), (x[:, ::-1], "v"),
                 (x[:, ::-1, ::-1], "hv")]
    acc = None
    with torch.no_grad():
        for arr, kind in views:
            t = torch.from_numpy(np.ascontiguousarray(arr))[None].to(dev)
            p = torch.sigmoid(m(t))[0, 0].cpu().numpy()
            if kind == "h":
                p = p[:, ::-1]
            elif kind == "v":
                p = p[::-1]
            elif kind == "hv":
                p = p[::-1, ::-1]
            acc = p if acc is None else acc + p
    return acc / len(views)


def run(split="test", thr=0.5, tta=False, limit=None):
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    m = load_model(dev)
    names = list_split(split, str(FLOODS_DIR))
    if limit:
        names = names[:limit]

    rows = []
    agg = {"tp": 0, "fp": 0, "fn": 0}          # scored on FLOOD-ONLY water
    for n in names:
        s1 = os.path.join(FLOODS_DIR, "S1Hand", f"{n}_S1Hand.tif")
        lb = os.path.join(FLOODS_DIR, "LabelHand", f"{n}_LabelHand.tif")
        jrc = os.path.join(FLOODS_DIR, "JRCWaterHand", f"{n}_JRCWaterHand.tif")
        if not (os.path.exists(s1) and os.path.exists(lb) and os.path.exists(jrc)):
            continue
        sar = tifffile.imread(s1).astype(np.float32)
        if not np.isfinite(sar).any():
            continue
        lab = tifffile.imread(lb).astype(np.int16)
        perm = tifffile.imread(jrc).astype(np.uint8) == 1

        prob = predict(m, sar, dev, tta)
        water = prob > thr
        flood_only = water & ~perm                       # <- the operational answer

        valid = lab >= 0
        true_water = (lab == 1)
        true_flood = true_water & ~perm
        tp = int((flood_only & true_flood & valid).sum())
        fp = int((flood_only & ~true_flood & valid).sum())
        fn = int((~flood_only & true_flood & valid).sum())
        for k, v in zip(("tp", "fp", "fn"), (tp, fp, fn)):
            agg[k] += v

        rows.append({
            "name": n,
            "water_km2": round(float(water.sum()) * PIXEL_KM2, 3),
            "permanent_km2": round(float((water & perm).sum()) * PIXEL_KM2, 3),
            "flood_km2": round(float(flood_only.sum()) * PIXEL_KM2, 3),
            "flood_frac_of_water": round(float(flood_only.sum()) /
                                         max(float(water.sum()), 1), 3),
        })

    tp, fp, fn = agg["tp"], agg["fp"], agg["fn"]
    iou = tp / max(tp + fp + fn, 1)
    prec = tp / max(tp + fp, 1)
    rec = tp / max(tp + fn, 1)

    tot_w = sum(r["water_km2"] for r in rows)
    tot_p = sum(r["permanent_km2"] for r in rows)
    tot_f = sum(r["flood_km2"] for r in rows)

    print(f"\n{len(rows)} chips, split={split}, threshold={thr}, TTA={tta}")
    print(f"  total water detected   {tot_w:8.1f} km²")
    print(f"  of which permanent     {tot_p:8.1f} km²  ({100*tot_p/max(tot_w,1e-9):.1f}%)")
    print(f"  ACTUAL FLOOD EXTENT    {tot_f:8.1f} km²  ({100*tot_f/max(tot_w,1e-9):.1f}%)")
    print(f"\n  flood-only IoU {iou:.3f}   precision {prec:.3f}   recall {rec:.3f}")

    worst = sorted(rows, key=lambda r: -r["flood_km2"])[:5]
    print("\n  largest flood events in the split:")
    for r in worst:
        print(f"    {r['name']:22s} {r['flood_km2']:7.2f} km² flood "
              f"of {r['water_km2']:7.2f} km² water")

    out = {"split": split, "threshold": thr, "tta": tta, "n": len(rows),
           "total_water_km2": round(tot_w, 2), "permanent_km2": round(tot_p, 2),
           "flood_km2": round(tot_f, 2),
           "flood_only": {"iou": iou, "precision": prec, "recall": rec},
           "chips": rows}
    os.makedirs(REPORTS, exist_ok=True)
    p = os.path.join(REPORTS, f"flood_extent_{split}.json")
    with open(p, "w", encoding="utf8") as fh:
        json.dump(out, fh, indent=2)
    print(f"\nwrote {p}")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test")
    ap.add_argument("--thr", type=float, default=0.5)
    ap.add_argument("--tta", action="store_true", help="4-flip test-time augmentation")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    run(a.split, a.thr, a.tta, a.limit)
