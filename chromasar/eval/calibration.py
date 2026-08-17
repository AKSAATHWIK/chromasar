"""Does our uncertainty actually predict error?

Until this is measured, "we ship a confidence map" is decoration. Two standard tests,
one per task:

FLOOD (classification) — RELIABILITY DIAGRAM + ECE
    Bin pixels by predicted probability. Among pixels predicted at p=0.8, is 80% of them
    genuinely water? A perfectly calibrated model sits on the diagonal. Expected
    Calibration Error (ECE) is the average gap, weighted by bin population.

COLORIZATION (regression) — SPARSIFICATION + AUSE
    The right test for regression uncertainty. Progressively drop the least-confident
    pixels and re-measure error on what remains. If the confidence is informative, error
    falls FASTER than dropping pixels at random. The gap between our curve and the
    oracle (dropping the genuinely-worst pixels first) is AUSE — lower is better.
    Random removal is the null hypothesis: if we match it, the confidence is worthless.

    python eval/calibration.py --task flood
    python eval/calibration.py --task color --ckpt <path>
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
for p in (ROOT, os.path.join(ROOT, "train"), os.path.join(ROOT, "flood")):
    sys.path.insert(0, p)

import matplotlib                                                    # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                      # noqa: E402
import torch                                                         # noqa: E402
from config import FLOODS_DIR, REPORTS, SEN12_DIR, DATA_ROOT         # noqa: E402

AMBER, GREEN, BLUE, GREY = "#C25E00", "#1F7A6C", "#2E6FA8", "#8794A2"


# ------------------------------------------------------------------ flood
def flood_calibration(n_bins=15, limit=None):
    import tifffile
    from flood import list_split
    from resunet import ResUNet

    ck_path = DATA_ROOT / "checkpoints" / "flood_resnet34.pt"
    if not ck_path.exists():
        raise SystemExit(f"missing {ck_path}")
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    m = ResUNet(2, 1, encoder="resnet34", pretrained=False, dropout=0.2, final=None)
    ck = torch.load(ck_path, map_location=dev, weights_only=False)
    m.load_state_dict(ck["model"])
    m.eval().to(dev)

    names = list_split("test", str(FLOODS_DIR))
    if limit:
        names = names[:limit]
    probs, truth = [], []
    for n in names:
        s1 = os.path.join(FLOODS_DIR, "S1Hand", f"{n}_S1Hand.tif")
        lb = os.path.join(FLOODS_DIR, "LabelHand", f"{n}_LabelHand.tif")
        if not (os.path.exists(s1) and os.path.exists(lb)):
            continue
        sar = tifffile.imread(s1).astype(np.float32)
        lab = tifffile.imread(lb).astype(np.int16)
        x = np.clip(np.nan_to_num(sar, nan=-30.0), -30.0, 0.0)
        x = (x + 30.0) / 30.0 * 2.0 - 1.0
        with torch.no_grad():
            p = torch.sigmoid(m(torch.from_numpy(x)[None].to(dev)))[0, 0].cpu().numpy()
        valid = lab >= 0
        probs.append(p[valid])
        truth.append((lab[valid] == 1).astype(np.float32))
    p = np.concatenate(probs)
    t = np.concatenate(truth)
    print(f"{len(names)} chips, {p.size/1e6:.2f}M labelled pixels")

    edges = np.linspace(0, 1, n_bins + 1)
    idx = np.clip(np.digitize(p, edges) - 1, 0, n_bins - 1)
    conf, acc, cnt = [], [], []
    for b in range(n_bins):
        m_ = idx == b
        if m_.sum() < 50:
            conf.append(np.nan); acc.append(np.nan); cnt.append(0)
            continue
        conf.append(float(p[m_].mean()))
        acc.append(float(t[m_].mean()))
        cnt.append(int(m_.sum()))
    conf, acc, cnt = np.array(conf), np.array(acc), np.array(cnt)
    ok = ~np.isnan(conf)
    ece = float(np.sum(cnt[ok] * np.abs(conf[ok] - acc[ok])) / max(cnt[ok].sum(), 1))
    # Brier score: mean squared error of the probability itself
    brier = float(np.mean((p - t) ** 2))

    fig, ax = plt.subplots(1, 2, figsize=(11.5, 4.6))
    ax[0].plot([0, 1], [0, 1], "--", color=GREY, lw=1.4, label="perfect calibration")
    ax[0].plot(conf[ok], acc[ok], "o-", color=AMBER, lw=2.2, ms=6, label="ChromaSAR")
    ax[0].set_xlabel("predicted water probability")
    ax[0].set_ylabel("observed fraction that is water")
    ax[0].set_title(f"Reliability — ECE {ece:.4f}, Brier {brier:.4f}", fontsize=11)
    ax[0].legend(fontsize=9)
    ax[0].grid(alpha=.25)
    ax[1].bar(np.arange(n_bins)[ok], cnt[ok] / cnt[ok].sum(), color=BLUE, alpha=.85)
    ax[1].set_xlabel("probability bin")
    ax[1].set_ylabel("fraction of pixels")
    ax[1].set_title("Where the predictions live", fontsize=11)
    ax[1].grid(alpha=.25, axis="y")
    fig.suptitle("Flood model calibration — Sen1Floods11 test split",
                 fontsize=12.5, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, .95])
    out = os.path.join(REPORTS, "calibration_flood.png")
    fig.savefig(out, dpi=140)
    print(f"ECE {ece:.4f}   Brier {brier:.4f}   -> {out}")
    return {"ece": ece, "brier": brier,
            "bins": [{"conf": c, "acc": a, "n": int(n)}
                     for c, a, n in zip(conf, acc, cnt) if not np.isnan(c)]}


# ------------------------------------------------------------ colorization
def color_calibration(ckpt, n_points=20, limit=200, passes=10):
    from dataset import SEN12Pairs
    from models import UNetGenerator, mc_colorize
    from resunet import ResUNet

    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ck = torch.load(ckpt, map_location=dev, weights_only=False)
    kind = ck.get("args", {}).get("generator", "unet")
    G = (UNetGenerator(1, 3, ck.get("args", {}).get("nf", 64)) if kind == "unet"
         else ResUNet(1, 3, encoder=kind, pretrained=False))
    G.load_state_dict(ck["G"])
    G.to(dev)

    ds = SEN12Pairs(str(SEN12_DIR), "val", augment=False, limit=limit,
                    exclude_file=os.path.join(REPORTS, "exclude_scenes.txt"))
    print(f"{len(ds)} validation patches from {ds.n_scenes} held-out scenes")

    errs, confs = [], []
    for i in range(len(ds)):
        sar, real = ds[i]
        sar = sar[None].to(dev)
        mean, conf, _ = mc_colorize(G, sar, n=passes)
        err = (mean[0] - real.to(dev)).abs().mean(0)      # per-pixel L1 over channels
        errs.append(err.flatten().cpu().numpy())
        confs.append(conf[0, 0].flatten().cpu().numpy())
    err = np.concatenate(errs)
    conf = np.concatenate(confs)

    # ---- sparsification: drop least-confident first --------------------
    fracs = np.linspace(0, 0.95, n_points)
    order_unc = np.argsort(conf)              # least confident first
    order_err = np.argsort(-err)              # worst error first (oracle)
    rng = np.random.default_rng(1733)
    order_rnd = rng.permutation(err.size)

    def curve(order):
        out = []
        for f in fracs:
            k = int(f * err.size)
            keep = order[k:]
            out.append(float(err[keep].mean()) if keep.size else np.nan)
        return np.array(out)

    c_unc, c_oracle, c_rnd = curve(order_unc), curve(order_err), curve(order_rnd)
    # normalise so all curves start at 1.0, then AUSE = area between ours and oracle
    n0 = c_unc[0]
    ause = float(np.trapezoid((c_unc - c_oracle) / n0, fracs))
    gain = float(np.trapezoid((c_rnd - c_unc) / n0, fracs))
    # rank correlation between confidence and error (should be strongly negative)
    s = rng.choice(err.size, size=min(200_000, err.size), replace=False)
    rc = float(np.corrcoef(np.argsort(np.argsort(conf[s])),
                           np.argsort(np.argsort(err[s])))[0, 1])

    fig, ax = plt.subplots(1, 2, figsize=(11.5, 4.6))
    ax[0].plot(fracs, c_rnd / n0, "--", color=GREY, lw=1.8, label="random removal (null)")
    ax[0].plot(fracs, c_unc / n0, "-", color=AMBER, lw=2.4, label="by our confidence")
    ax[0].plot(fracs, c_oracle / n0, ":", color=GREEN, lw=2.0, label="oracle (true error)")
    ax[0].set_xlabel("fraction of least-confident pixels removed")
    ax[0].set_ylabel("mean error on remaining pixels (normalised)")
    ax[0].set_title(f"Sparsification — AUSE {ause:.4f}, gain over random {gain:.4f}",
                    fontsize=11)
    ax[0].legend(fontsize=9)
    ax[0].grid(alpha=.25)

    bins = np.linspace(0, 1, 16)
    bi = np.clip(np.digitize(conf, bins) - 1, 0, 14)
    mids, mErr = [], []
    for b in range(15):
        m_ = bi == b
        if m_.sum() > 200:
            mids.append((bins[b] + bins[b + 1]) / 2)
            mErr.append(err[m_].mean())
    ax[1].plot(mids, mErr, "o-", color=AMBER, lw=2.2, ms=6)
    ax[1].set_xlabel("predicted confidence")
    ax[1].set_ylabel("actual mean L1 error")
    ax[1].set_title(f"Confidence vs error — rank corr {rc:+.3f}", fontsize=11)
    ax[1].grid(alpha=.25)

    fig.suptitle("Colorization confidence calibration — held-out scenes",
                 fontsize=12.5, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, .95])
    out = os.path.join(REPORTS, "calibration_color.png")
    fig.savefig(out, dpi=140)
    print(f"AUSE {ause:.4f}   gain-over-random {gain:.4f}   rank corr {rc:+.3f}")
    print(f"-> {out}")
    if rc > -0.05:
        print("WARNING: confidence barely correlates with error. The map is decorative "
              "as it stands and must not be presented as validated.")
    return {"ause": ause, "gain_over_random": gain, "rank_corr": rc}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="flood", choices=["flood", "color"])
    ap.add_argument("--ckpt", default=str(DATA_ROOT / "checkpoints" / "colorization.pt"))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--passes", type=int, default=10)
    args = ap.parse_args()
    os.makedirs(REPORTS, exist_ok=True)

    res = (flood_calibration(limit=args.limit) if args.task == "flood"
           else color_calibration(args.ckpt, limit=args.limit or 200,
                                  passes=args.passes))
    p = os.path.join(REPORTS, f"calibration_{args.task}.json")
    with open(p, "w", encoding="utf8") as fh:
        json.dump(res, fh, indent=2)
    print("wrote", p)


if __name__ == "__main__":
    main()
