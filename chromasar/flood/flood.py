"""Flood water mapping from Sentinel-1 SAR, scored against Sen1Floods11 hand labels.

Physics: water is a specular reflector. It bounces the radar pulse away from the
satellite instead of back to it, so open water returns almost no energy and appears
near-black. Flood mapping is therefore a thresholding problem on backscatter, not a
deep-learning problem - which is why this module works with no GPU and no training,
and why it is independent of the colorization model.

Two data details that silently corrupt results if missed:
  * labels are {-1, 0, 1} where -1 means NO DATA. Counting those as "not water"
    inflates every metric. They are masked out of both prediction and truth.
  * some chips are entirely NaN in the SAR. They are skipped, not zero-filled.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import tifffile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import FLOODS_DIR                     # noqa: E402



DATA = str(FLOODS_DIR)


# ---------------------------------------------------------------- loading
def load_chip(name, root=DATA):
    """-> (sar[2,H,W] dB with NaN, label[H,W] in {-1,0,1})"""
    sar = tifffile.imread(os.path.join(root, "S1Hand", f"{name}_S1Hand.tif"))
    lab = tifffile.imread(os.path.join(root, "LabelHand", f"{name}_LabelHand.tif"))
    return sar.astype(np.float32), lab.astype(np.int16)


def list_split(split, root=DATA):
    """Official Sen1Floods11 splits, so numbers are comparable to published work."""
    f = os.path.join(root, "flood_handlabeled", f"flood_{split}_data.csv")
    names = []
    with open(f, encoding="utf8") as fh:
        for line in fh:
            first = line.strip().split(",")[0]
            if first:
                names.append(first.replace("_S1Hand.tif", "").replace(".tif", ""))
    return names


# ---------------------------------------------------------------- method
def otsu(values, bins=256):
    """Otsu's threshold: split the histogram to maximise between-class variance."""
    values = values[np.isfinite(values)]
    if values.size < 32:
        return None
    hist, edges = np.histogram(values, bins=bins)
    hist = hist.astype(np.float64)
    p = hist / max(hist.sum(), 1)
    omega = np.cumsum(p)
    mids = (edges[:-1] + edges[1:]) / 2
    mu = np.cumsum(p * mids)
    mu_t = mu[-1]
    denom = omega * (1 - omega)
    denom[denom <= 1e-12] = np.nan
    sigma_b = (mu_t * omega - mu) ** 2 / denom
    if np.all(np.isnan(sigma_b)):
        return None
    return float(mids[int(np.nanargmax(sigma_b))])


def water_mask(sar, method="dualpol", fixed_db=-16.5, min_water_frac=0.0005,
               clamp=(-24.0, -13.0), vv_db=-18.5, vh_db=-24.0):
    """Predict open water. Returns (mask bool[H,W], threshold or None).

    Water is DARK, so water = backscatter below the threshold.
    """
    vv, vh = sar[0], sar[1]
    if not np.isfinite(vv).any():
        return None, None

    if method == "dualpol":
        # Best measured rule. Either polarisation going dark is enough to call water.
        # VH alone actually outscores VV alone (valid IoU 0.486 vs 0.464) - cross-pol
        # return over smooth water is very low, and it is less confused by the
        # bright dry surfaces that fool VV. OR-ing them recovers water that either
        # channel alone misses.
        # Tuned on the validation split; on test this lifts recall 0.549 -> 0.671
        # at unchanged precision (0.752 -> 0.754), IoU 0.465 -> 0.550.
        thr = vv_db
        pred = (vv < vv_db) | (vh < vh_db)
    elif method == "fixed":
        thr = fixed_db
        pred = vv < thr
    elif method == "otsu_vv":
        thr = otsu(vv)
        if thr is None:
            return None, None
        pred = vv < thr
    elif method == "otsu_clamped":
        # Otsu always splits, even where there is no water, so an unconstrained
        # threshold can land in the middle of dry land. Clamping it to the dB range
        # open water actually occupies lifts test IoU from 0.211 to 0.354.
        t = otsu(vv)
        if t is None:
            return None, None
        thr = float(np.clip(t, clamp[0], clamp[1]))
        pred = vv < thr
    elif method == "otsu_both":
        tvv, tvh = otsu(vv), otsu(vh)
        if tvv is None or tvh is None:
            return None, None
        thr = tvv
        # both channels must agree - cuts false positives on smooth dry surfaces
        pred = (vv < tvv) & (vh < tvh)
    else:
        raise ValueError(method)

    pred = pred & np.isfinite(vv)
    # Otsu always splits, even on a scene with no water at all. If the "water" class
    # is a negligible sliver, treat it as no water rather than reporting noise.
    if pred.mean() < min_water_frac:
        pred[:] = False
    return pred, thr


# ---------------------------------------------------------------- scoring
def score(pred, lab):
    """IoU / precision / recall on LABELLED pixels only (-1 excluded)."""
    valid = lab >= 0
    if not valid.any():
        return None
    p = pred[valid].astype(bool)
    t = (lab[valid] == 1)
    tp = int(np.sum(p & t))
    fp = int(np.sum(p & ~t))
    fn = int(np.sum(~p & t))
    tn = int(np.sum(~p & ~t))
    iou = tp / (tp + fp + fn) if (tp + fp + fn) else np.nan
    prec = tp / (tp + fp) if (tp + fp) else np.nan
    rec = tp / (tp + fn) if (tp + fn) else np.nan
    f1 = (2 * prec * rec / (prec + rec)
          if (prec and rec and np.isfinite(prec) and np.isfinite(rec)) else np.nan)
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "iou": iou, "precision": prec, "recall": rec, "f1": f1,
            "water_frac_true": float(t.mean())}


def evaluate(split="test", method="otsu_vv", root=DATA, limit=None):
    names = list_split(split, root)
    if limit:
        names = names[:limit]
    rows, skipped = [], 0
    agg = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    for n in names:
        try:
            sar, lab = load_chip(n, root)
        except FileNotFoundError:
            skipped += 1
            continue
        pred, thr = water_mask(sar, method)
        if pred is None:
            skipped += 1
            continue
        s = score(pred, lab)
        if s is None:
            skipped += 1
            continue
        for k in agg:
            agg[k] += s[k]
        s["name"] = n
        s["thr"] = thr
        rows.append(s)

    tp, fp, fn = agg["tp"], agg["fp"], agg["fn"]
    micro = {
        "iou": tp / (tp + fp + fn) if (tp + fp + fn) else np.nan,
        "precision": tp / (tp + fp) if (tp + fp) else np.nan,
        "recall": tp / (tp + fn) if (tp + fn) else np.nan,
    }
    micro["f1"] = (2 * micro["precision"] * micro["recall"]
                   / (micro["precision"] + micro["recall"])
                   if micro["precision"] and micro["recall"] else np.nan)
    return {"rows": rows, "skipped": skipped, "n": len(rows),
            "micro": micro,
            "macro_iou": float(np.nanmean([r["iou"] for r in rows])) if rows else np.nan}
