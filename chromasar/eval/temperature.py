"""Temperature scaling — fix the measured over-confidence with ONE fitted scalar.

Calibration on the test split showed the reliability curve sagging below the diagonal
between p=0.4 and p=0.9: where the model says 0.7, only ~0.45 of those pixels are
really water. It is over-confident in exactly the ambiguous band where a gate has to
make its decision.

Temperature scaling divides the logits by a single learned constant T before the
sigmoid. T > 1 softens confidence, T < 1 sharpens it. It cannot change WHICH pixels are
ranked as most likely water, so IoU, precision and recall at the corresponding threshold
are untouched — it only makes the probability mean what it says.

Critically, T is fitted on VALIDATION and reported on TEST. Fitting on test would be
marking our own homework.

    python eval/temperature.py
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
for p in (ROOT, os.path.join(ROOT, "train"), os.path.join(ROOT, "flood")):
    sys.path.insert(0, p)

import matplotlib                                                # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                  # noqa: E402
from config import DATA_ROOT, FLOODS_DIR, REPORTS                # noqa: E402
from flood import list_split                                     # noqa: E402
from resunet import ResUNet                                      # noqa: E402

AMBER, GREEN, GREY = "#C25E00", "#1F7A6C", "#8794A2"


def collect(split, m, dev, limit=None):
    """-> (logits, targets) over labelled pixels only."""
    names = list_split(split, str(FLOODS_DIR))
    if limit:
        names = names[:limit]
    L, T = [], []
    for n in names:
        s1 = os.path.join(FLOODS_DIR, "S1Hand", f"{n}_S1Hand.tif")
        lb = os.path.join(FLOODS_DIR, "LabelHand", f"{n}_LabelHand.tif")
        if not (os.path.exists(s1) and os.path.exists(lb)):
            continue
        sar = tifffile.imread(s1).astype(np.float32)
        if not np.isfinite(sar).any():
            continue
        lab = tifffile.imread(lb).astype(np.int16)
        x = np.clip(np.nan_to_num(sar, nan=-30.0), -30.0, 0.0)
        x = (x + 30.0) / 30.0 * 2.0 - 1.0
        with torch.no_grad():
            lg = m(torch.from_numpy(x)[None].to(dev))[0, 0].cpu().numpy()
        v = lab >= 0
        L.append(lg[v])
        T.append((lab[v] == 1).astype(np.float32))
    return np.concatenate(L), np.concatenate(T)


def ece_of(prob, targ, n_bins=15):
    edges = np.linspace(0, 1, n_bins + 1)
    idx = np.clip(np.digitize(prob, edges) - 1, 0, n_bins - 1)
    tot, num = 0, 0
    conf, acc, cnt = [], [], []
    for b in range(n_bins):
        m_ = idx == b
        if m_.sum() < 50:
            continue
        c, a, k = prob[m_].mean(), targ[m_].mean(), m_.sum()
        conf.append(c); acc.append(a); cnt.append(k)
        tot += k * abs(c - a); num += k
    return tot / max(num, 1), np.array(conf), np.array(acc), np.array(cnt)


def fit_temperature(logits, targets, iters=300):
    """Minimise NLL over a single scalar, on validation data."""
    lg = torch.from_numpy(logits.astype(np.float32))
    tg = torch.from_numpy(targets.astype(np.float32))
    logT = torch.zeros(1, requires_grad=True)          # T = exp(logT), starts at 1
    opt = torch.optim.LBFGS([logT], lr=0.1, max_iter=iters)
    lossf = torch.nn.BCEWithLogitsLoss()

    def closure():
        opt.zero_grad()
        loss = lossf(lg / torch.exp(logT), tg)
        loss.backward()
        return loss
    opt.step(closure)
    return float(torch.exp(logT).item())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    os.makedirs(REPORTS, exist_ok=True)

    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    m = ResUNet(2, 1, encoder="resnet34", pretrained=False, dropout=0.2, final=None)
    ck = torch.load(DATA_ROOT / "checkpoints" / "flood_resnet34.pt",
                    map_location=dev, weights_only=False)
    m.load_state_dict(ck["model"])
    m.eval().to(dev)

    print("collecting validation logits...")
    lv, tv = collect("valid", m, dev, args.limit)
    print(f"  {lv.size/1e6:.2f}M labelled pixels")
    T = fit_temperature(lv, tv)
    print(f"fitted temperature T = {T:.4f}  "
          f"({'softening' if T > 1 else 'sharpening'} confidence)")

    print("evaluating on test...")
    lt, tt = collect("test", m, dev, args.limit)
    p_before = 1 / (1 + np.exp(-lt))
    p_after = 1 / (1 + np.exp(-lt / T))
    e0, c0, a0, n0 = ece_of(p_before, tt)
    e1, c1, a1, n1 = ece_of(p_after, tt)
    b0 = float(np.mean((p_before - tt) ** 2))
    b1 = float(np.mean((p_after - tt) ** 2))

    # ranking is unchanged, so the operating point must be identical
    iou0 = float(((p_before > .5) & (tt > .5)).sum() /
                 max(((p_before > .5) | (tt > .5)).sum(), 1))
    iou1 = float(((p_after > .5) & (tt > .5)).sum() /
                 max(((p_after > .5) | (tt > .5)).sum(), 1))

    print(f"\n  ECE    {e0:.4f} -> {e1:.4f}   ({100*(e0-e1)/max(e0,1e-9):+.1f}%)")
    print(f"  Brier  {b0:.4f} -> {b1:.4f}")
    print(f"  IoU@0.5 {iou0:.4f} -> {iou1:.4f}  (threshold shifts with T; "
          f"ranking is unchanged)")

    fig, ax = plt.subplots(figsize=(6.2, 5.4))
    ax.plot([0, 1], [0, 1], "--", color=GREY, lw=1.4, label="perfect calibration")
    ax.plot(c0, a0, "o-", color=AMBER, lw=2.2, ms=5, label=f"before (ECE {e0:.4f})")
    ax.plot(c1, a1, "s-", color=GREEN, lw=2.2, ms=5, label=f"after T={T:.2f} (ECE {e1:.4f})")
    ax.set_xlabel("predicted water probability")
    ax.set_ylabel("observed fraction that is water")
    ax.set_title("Temperature scaling — fitted on validation, shown on test",
                 fontsize=11.5, fontweight="bold")
    ax.legend(fontsize=9)
    ax.grid(alpha=.25)
    fig.tight_layout()
    out = os.path.join(REPORTS, "calibration_temperature.png")
    fig.savefig(out, dpi=145)

    res = {"temperature": T, "ece_before": e0, "ece_after": e1,
           "brier_before": b0, "brier_after": b1,
           "iou_before": iou0, "iou_after": iou1}
    with open(os.path.join(REPORTS, "temperature.json"), "w", encoding="utf8") as fh:
        json.dump(res, fh, indent=2)
    print(f"wrote {out}")
    return res


if __name__ == "__main__":
    main()
