"""Correct image-quality metrics, and a post-hoc evaluator for saved checkpoints.

Why this file exists: train.py tracks a GLOBAL-statistics SSIM (one mean/variance for
the whole image). That is cheap and fine as a training-progress signal, but it is NOT
SSIM as anyone else computes it, and its values are not comparable to published numbers.
Real SSIM slides an 11x11 Gaussian window over the image and averages the local scores.

Reporting the global version in a results table would be quietly wrong, so the final
numbers come from here instead. Nothing needs retraining - we recompute from the saved
checkpoints.

    python eval/metrics.py --ckpt <path>            # one model
    python eval/metrics.py --runs-dir <dir>         # every best.pt underneath
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

import numpy as np
import torch
import torch.nn.functional as F

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
for p in (ROOT, os.path.join(ROOT, "train")):
    sys.path.insert(0, p)

from config import REPORTS, SEN12_DIR                            # noqa: E402


# ------------------------------------------------------------------ SSIM
def _gauss(win, sigma, device):
    c = torch.arange(win, dtype=torch.float32, device=device) - (win - 1) / 2
    g = torch.exp(-(c ** 2) / (2 * sigma ** 2))
    g = (g / g.sum()).unsqueeze(0)
    return (g.t() @ g).unsqueeze(0).unsqueeze(0)                 # [1,1,win,win]


def ssim(a, b, data_range=2.0, win=11, sigma=1.5):
    """Standard windowed SSIM, averaged over channels and the image.

    Inputs are [B,C,H,W] in [-1,1] (hence data_range=2).
    """
    C = a.shape[1]
    k = _gauss(win, sigma, a.device).expand(C, 1, win, win)
    pad = win // 2
    mu_a = F.conv2d(a, k, padding=pad, groups=C)
    mu_b = F.conv2d(b, k, padding=pad, groups=C)
    mu_a2, mu_b2, mu_ab = mu_a * mu_a, mu_b * mu_b, mu_a * mu_b
    sa = F.conv2d(a * a, k, padding=pad, groups=C) - mu_a2
    sb = F.conv2d(b * b, k, padding=pad, groups=C) - mu_b2
    sab = F.conv2d(a * b, k, padding=pad, groups=C) - mu_ab
    c1 = (0.01 * data_range) ** 2
    c2 = (0.03 * data_range) ** 2
    s = ((2 * mu_ab + c1) * (2 * sab + c2)) / ((mu_a2 + mu_b2 + c1) * (sa + sb + c2))
    return s.mean().item()


def sharpness(x):
    """Mean image-gradient magnitude - a plain, honest proxy for detail.

    Needed because PSNR and L1 both reward the CONDITIONAL MEAN, which is literally
    blur: the safest prediction under squared/absolute error is the average of every
    plausible colour, and averaging destroys texture. Measured on the trained model,
    output scores 0.577 against 2.891 for the real Sentinel-2 optical - five times
    softer - while PSNR looked fine. A metric that cannot see the defect cannot be used
    to select against it.
    """
    g = x.mean(1, keepdim=True) if x.shape[1] > 1 else x
    gx = g[..., :, 1:] - g[..., :, :-1]
    gy = g[..., 1:, :] - g[..., :-1, :]
    return (gx.abs().mean() + gy.abs().mean()).item() / 2.0


def sharpness_ratio(fake, real):
    """fake/real gradient energy. 1.0 = matches reality, <1 = blurrier, >1 = noisy."""
    r = sharpness(real)
    return sharpness(fake) / max(r, 1e-8)


def psnr(a, b, data_range=2.0):
    mse = torch.mean((a - b) ** 2).item()
    return 99.0 if mse <= 0 else 10 * np.log10((data_range ** 2) / mse)


def global_ssim(a, b):
    """The cheap variant train.py uses - kept only so we can show the difference."""
    a2, b2 = (a + 1) / 2, (b + 1) / 2
    mu_a, mu_b = a2.mean(), b2.mean()
    va, vb = a2.var(), b2.var()
    cov = ((a2 - mu_a) * (b2 - mu_b)).mean()
    c1, c2 = 0.01 ** 2, 0.03 ** 2
    return (((2 * mu_a * mu_b + c1) * (2 * cov + c2)) /
            ((mu_a ** 2 + mu_b ** 2 + c1) * (va + vb + c2))).item()


# ------------------------------------------------------------ evaluation
def evaluate(ckpt, limit=400, batch=16, device=None):
    from dataset import SEN12Pairs
    from losses import VGGPerceptual
    from models import UNetGenerator
    from resunet import ResUNet
    from torch.utils.data import DataLoader

    dev = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ck = torch.load(ckpt, map_location=dev, weights_only=False)
    a = ck.get("args", {})
    kind = a.get("generator", "unet")
    G = (UNetGenerator(1, 3, a.get("nf", 64)) if kind == "unet"
         else ResUNet(1, 3, encoder=kind, pretrained=False))
    G.load_state_dict(ck["G"])
    G.eval().to(dev)

    ds = SEN12Pairs(str(SEN12_DIR), "val", augment=False, limit=limit,
                    exclude_file=os.path.join(REPORTS, "exclude_scenes.txt"))
    dl = DataLoader(ds, batch_size=batch, shuffle=False)
    perc = VGGPerceptual(dev)

    P, S, Sg, Pc, n = 0.0, 0.0, 0.0, 0.0, 0
    with torch.no_grad():
        for sar, real in dl:
            sar, real = sar.to(dev), real.to(dev)
            fake = G(sar)
            P += psnr(fake, real)
            S += ssim(fake, real)
            Sg += global_ssim(fake, real)
            Pc += perc(fake, real).item()
            n += 1
    n = max(n, 1)
    return {
        "checkpoint": os.path.relpath(ckpt),
        "generator": kind,
        "pretrained": not a.get("no_pretrained", False) if kind != "unet" else None,
        "lambda_perc": a.get("lambda_perc", 0.0),
        "lambda_gan": a.get("lambda_gan", None),
        "epoch": ck.get("epoch"),
        "psnr": round(P / n, 3),
        "ssim": round(S / n, 4),              # windowed - the one to report
        "ssim_global": round(Sg / n, 4),      # what training logged
        "perceptual": round(Pc / n, 4),
        "n_patches": len(ds),
        "n_scenes": ds.n_scenes,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt")
    ap.add_argument("--runs-dir")
    ap.add_argument("--limit", type=int, default=400)
    ap.add_argument("--pattern", default="best.pt",
                    help="best.pt = checkpoint selected on validation; "
                         "last.pt = the fully-trained final epoch")
    ap.add_argument("--out-name", default="ablation_metrics.json")
    args = ap.parse_args()
    os.makedirs(REPORTS, exist_ok=True)

    paths = ([args.ckpt] if args.ckpt else
             sorted(glob.glob(os.path.join(args.runs_dir, "**", args.pattern),
                              recursive=True)))
    if not paths:
        raise SystemExit("no checkpoints found")

    rows = []
    for p in paths:
        print(f"evaluating {p} ...", flush=True)
        rows.append(evaluate(p, limit=args.limit))
        print(f"   {rows[-1]}", flush=True)

    hdr = f"{'variant':22s} {'PSNR':>7s} {'SSIM':>7s} {'percep':>8s} {'epoch':>6s}"
    print("\n" + hdr)
    print("-" * len(hdr))
    for r in rows:
        name = os.path.basename(os.path.dirname(r["checkpoint"]))
        print(f"{name:22s} {r['psnr']:7.2f} {r['ssim']:7.4f} "
              f"{r['perceptual']:8.4f} {str(r['epoch']):>6s}")
    print("\nSSIM above is windowed (11x11 Gaussian) — the comparable definition.")

    out = os.path.join(REPORTS, args.out_name)
    with open(out, "w", encoding="utf8") as fh:
        json.dump(rows, fh, indent=2)
    print("wrote", out)


if __name__ == "__main__":
    main()
