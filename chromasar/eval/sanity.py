"""Is the colorization model actually doing anything useful?

A model can post respectable-looking PSNR while being worthless, because PSNR rewards
predicting the average. This compares our generator against baselines that require no
learning at all:

  constant-mean  : predict the dataset's average colour for every pixel
  grey-copy      : copy the SAR intensity into R, G and B
  shuffled       : our model's output, paired with the WRONG ground truth

If we cannot beat constant-mean, the model has learned nothing worth shipping.
If `shuffled` scores close to the real pairing, the metric is not measuring alignment
at all - it is measuring "looks like a satellite image on average".

    python eval/sanity.py --n 150
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import torch

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
for p in (ROOT, os.path.join(ROOT, "train")):
    sys.path.insert(0, p)

from config import DATA_ROOT, REPORTS, SEN12_DIR                 # noqa: E402
from dataset import SEN12Pairs                                   # noqa: E402
from metrics import psnr, ssim                                   # noqa: E402
from resunet import ResUNet                                      # noqa: E402


def load(dev):
    ck = torch.load(DATA_ROOT / "checkpoints" / "colorization.pt",
                    map_location=dev, weights_only=False)
    kind = ck.get("args", {}).get("generator", "unet")
    if kind == "unet":
        from models import UNetGenerator
        G = UNetGenerator(1, 3, ck.get("args", {}).get("nf", 64))
    else:
        G = ResUNet(1, 3, encoder=kind, pretrained=False)
    G.load_state_dict(ck["G"])
    G.eval().to(dev)
    return G, kind, ck.get("epoch")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=150)
    args = ap.parse_args()

    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    G, kind, epoch = load(dev)
    ds = SEN12Pairs(str(SEN12_DIR), "val", augment=False, limit=args.n,
                    exclude_file=os.path.join(REPORTS, "exclude_scenes.txt"))
    print(f"model={kind} epoch={epoch}   {len(ds)} held-out patches "
          f"from {ds.n_scenes} unseen scenes\n")

    sars, reals, fakes = [], [], []
    with torch.no_grad():
        for i in range(len(ds)):
            s, r = ds[i]
            sars.append(s)
            reals.append(r)
            fakes.append(G(s[None].to(dev))[0].cpu())
    sar = torch.stack(sars)
    real = torch.stack(reals)
    fake = torch.stack(fakes)

    # ---- baselines -------------------------------------------------
    mean_colour = real.mean(dim=(0, 2, 3), keepdim=True).expand_as(real)
    grey = sar.repeat(1, 3, 1, 1)
    shuffled = fake[torch.randperm(fake.shape[0], generator=torch.Generator().manual_seed(0))]

    rows = [
        ("ChromaSAR", fake, real),
        ("constant-mean colour", mean_colour, real),
        ("grey copy of SAR", grey, real),
        ("ChromaSAR vs WRONG truth", shuffled, real),
    ]
    print(f"{'variant':28s} {'PSNR':>7s} {'SSIM':>8s} {'L1':>7s}")
    print("-" * 54)
    out = {}
    for name, a, b in rows:
        p = np.mean([psnr(a[i:i+1], b[i:i+1]) for i in range(len(a))])
        s = np.mean([ssim(a[i:i+1], b[i:i+1]) for i in range(len(a))])
        l1 = (a - b).abs().mean().item()
        out[name] = (p, s, l1)
        print(f"{name:28s} {p:7.2f} {s:8.4f} {l1:7.4f}")

    ours = out["ChromaSAR"]
    base = out["constant-mean colour"]
    shuf = out["ChromaSAR vs WRONG truth"]

    print("\n--- verdict ---")
    beats = ours[0] > base[0] + 0.25 and ours[1] > base[1] + 0.01
    print(f"beats constant-mean: {'YES' if beats else 'NO'}  "
          f"(PSNR {ours[0]:.2f} vs {base[0]:.2f}, SSIM {ours[1]:.4f} vs {base[1]:.4f})")
    gap = ours[1] - shuf[1]
    print(f"alignment signal   : SSIM drops {gap:+.4f} when paired with the wrong "
          f"truth ({ours[1]:.4f} -> {shuf[1]:.4f})")
    if gap < 0.02:
        print("  WARNING: barely changes when mispaired - the score reflects generic "
              "'looks like terrain', not per-scene accuracy.")
    else:
        print("  Good: the score genuinely depends on matching the right scene.")

    # ---- how much colour is the model actually producing? ------------
    sat_fake = (fake.max(1).values - fake.min(1).values).mean().item()
    sat_real = (real.max(1).values - real.min(1).values).mean().item()
    print(f"\ncolour saturation  : ours {sat_fake:.4f} vs truth {sat_real:.4f} "
          f"({100*sat_fake/max(sat_real,1e-9):.0f}% of real)")
    var_fake = fake.var(dim=(2, 3)).mean().item()
    var_real = real.var(dim=(2, 3)).mean().item()
    print(f"spatial variance   : ours {var_fake:.4f} vs truth {var_real:.4f} "
          f"({100*var_fake/max(var_real,1e-9):.0f}% of real)")
    if var_fake < 0.35 * var_real:
        print("  -> output is markedly flatter than reality: the blur/hedging failure.")


if __name__ == "__main__":
    main()
