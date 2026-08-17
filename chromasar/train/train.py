"""pix2pix training loop for SAR colorization. Runs on CPU or GPU unchanged.

    python train/train.py --data $SIH_DATA/sen1-2 --epochs 1 --limit 64
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from torch.utils.data import DataLoader

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)                       # train/  -> dataset, models
sys.path.insert(0, os.path.dirname(_HERE))      # project -> config
from config import SEN12_DIR                                    # noqa: E402
from dataset import SEN12Pairs, denorm                          # noqa: E402
from losses import VGGPerceptual, gradient_loss                 # noqa: E402
from models import (PatchDiscriminator, init_weights,           # noqa: E402
                    mc_colorize)
from resunet import build_generator                             # noqa: E402


def sharpness_ratio(fake, real):
    """fake/real gradient energy. 1.0 matches reality, <1 is blurrier, >1 is noisier.

    Logged every epoch because PSNR and L1 are both BLIND to blur - their optimum is the
    conditional mean, which has no texture at all. Without this number you cannot tell a
    model that is getting better from one that is quietly getting smoother.
    """
    def g(x):
        m = x.mean(1, keepdim=True)
        gx = (m[..., :, 1:] - m[..., :, :-1]).abs().mean()
        gy = (m[..., 1:, :] - m[..., :-1, :]).abs().mean()
        return ((gx + gy) / 2).item()
    return g(fake) / max(g(real), 1e-8)


def psnr(a, b):
    mse = torch.mean((a - b) ** 2).item()
    return 10 * np.log10(4.0 / mse) if mse > 0 else 99.0        # range is 2.0 => max 4


def ssim(a, b, C1=0.01 ** 2, C2=0.03 ** 2):
    """Global SSIM on [-1,1] tensors - adequate for tracking, not for the final table."""
    a = (a + 1) / 2
    b = (b + 1) / 2
    mu_a, mu_b = a.mean(), b.mean()
    va, vb = a.var(), b.var()
    cov = ((a - mu_a) * (b - mu_b)).mean()
    return (((2 * mu_a * mu_b + C1) * (2 * cov + C2)) /
            ((mu_a ** 2 + mu_b ** 2 + C1) * (va + vb + C2))).item()


def save_grid(path, sar, fake, real, conf=None, n=4):
    rows = []
    for i in range(min(n, sar.shape[0])):
        s = np.repeat(denorm(sar[i])[:, :, :1], 3, axis=2)      # grey SAR -> 3ch
        tiles = [s, denorm(fake[i]), denorm(real[i])]
        if conf is not None:
            c = conf[i, 0].detach().cpu().numpy()
            cm = np.stack([(1 - c), c, np.zeros_like(c)], -1)   # red = guessing
            tiles.append((cm * 255).astype(np.uint8))
        rows.append(np.concatenate(tiles, axis=1))
    Image.fromarray(np.concatenate(rows, axis=0)).save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(SEN12_DIR))
    ap.add_argument("--out", default="runs/base")
    ap.add_argument("--exclude", default=None)
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--lambda-l1", type=float, default=100.0)
    ap.add_argument("--nf", type=int, default=64)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--sample-every", type=int, default=1)
    # ---- ablation axes -------------------------------------------------
    ap.add_argument("--generator", default="unet",
                    choices=["unet", "resnet18", "resnet34"],
                    help="unet = from scratch (baseline); resnet* = ImageNet encoder")
    ap.add_argument("--no-pretrained", action="store_true",
                    help="use the resnet architecture WITHOUT ImageNet weights - "
                         "isolates architecture from transfer learning")
    ap.add_argument("--lambda-grad", type=float, default=0.0,
                    help="weight on the gradient-difference loss. L1 alone is minimised "
                         "by the conditional mean, i.e. blur; this makes flatness cost.")
    ap.add_argument("--lambda-perc", type=float, default=0.0,
                    help="weight on frozen-VGG perceptual loss (0 = off)")
    # ---- GAN stability ---------------------------------------------------
    ap.add_argument("--lr-d", type=float, default=None,
                    help="discriminator LR. Default = lr/2 (two-timescale update "
                         "rule). A discriminator that wins gives the generator no "
                         "usable gradient.")
    ap.add_argument("--real-label", type=float, default=0.9,
                    help="one-sided label smoothing; stops D becoming over-confident")
    ap.add_argument("--decay-from", type=float, default=0.5,
                    help="fraction of training after which LR decays linearly to 0")
    ap.add_argument("--lambda-gan", type=float, default=1.0,
                    help="weight on the adversarial term once warmed up")
    ap.add_argument("--gan-warmup", type=int, default=5,
                    help="epochs of L1-only training before the discriminator is "
                         "introduced, then ramped linearly over the same span. "
                         "Without this the untrained D emits noise that pushes the "
                         "generator off the data - measured: L1 stuck at 0.43, worse "
                         "than the 0.22 a constant-colour prediction achieves.")
    ap.add_argument("--select", default="perceptual",
                    choices=["perceptual", "psnr", "ssim", "last", "balanced"],
                    help="checkpoint selection metric. NOT psnr by default: early "
                         "blurry outputs score best on PSNR, which is the exact "
                         "failure mode we are trying to remove.")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    tr = SEN12Pairs(args.data, "train", exclude_file=args.exclude, limit=args.limit)
    va = SEN12Pairs(args.data, "val", exclude_file=args.exclude,
                    limit=(args.limit // 4 if args.limit else None))
    print(f"device={dev}  train={len(tr)} patches / {tr.n_scenes} scenes  "
          f"val={len(va)} / {va.n_scenes} scenes  (excluded {tr.dropped} patches)")
    if len(tr) == 0 or len(va) == 0:
        sys.exit("empty split - check --data and --limit")

    dl_tr = DataLoader(tr, batch_size=args.batch, shuffle=True,
                       num_workers=args.workers, drop_last=True, pin_memory=(dev.type == "cuda"))
    dl_va = DataLoader(va, batch_size=args.batch, shuffle=False, num_workers=args.workers)

    G = build_generator(args.generator, nf=args.nf,
                        pretrained=not args.no_pretrained).to(dev)
    D = init_weights(PatchDiscriminator(4, args.nf)).to(dev)
    n_par = sum(p.numel() for p in G.parameters()) / 1e6
    print(f"generator={args.generator} "
          f"{'(ImageNet weights)' if args.generator != 'unet' and not args.no_pretrained else '(from scratch)'}"
          f"  {n_par:.1f}M params  perceptual={args.lambda_perc}")

    perc = VGGPerceptual(dev) if args.lambda_perc > 0 else None
    lr_d = args.lr_d if args.lr_d is not None else args.lr / 2.0
    optG = torch.optim.Adam(G.parameters(), lr=args.lr, betas=(0.5, 0.999))
    optD = torch.optim.Adam(D.parameters(), lr=lr_d, betas=(0.5, 0.999))
    gan_loss = nn.BCEWithLogitsLoss()
    l1 = nn.L1Loss()
    print(f"lr_G={args.lr}  lr_D={lr_d}  real_label={args.real_label}  "
          f"select={args.select}")

    # linear decay to zero over the tail of training - standard pix2pix schedule
    def lr_lambda(ep):
        start = int(args.epochs * args.decay_from)
        if ep < start:
            return 1.0
        return max(0.0, 1.0 - (ep - start) / max(1, args.epochs - start))
    schedG = torch.optim.lr_scheduler.LambdaLR(optG, lr_lambda)
    schedD = torch.optim.lr_scheduler.LambdaLR(optD, lr_lambda)

    # always available for VALIDATION, even when it is not part of the loss - this is
    # what we select checkpoints on
    eval_perc = VGGPerceptual(dev)

    hist = []
    best = -1e9
    best_row = None
    for ep in range(1, args.epochs + 1):
        G.train()
        D.train()
        t0 = time.time()
        # 0 during warmup, then linear ramp to full weight over the same span
        w = args.gan_warmup
        gan_w = 0.0 if ep <= w else args.lambda_gan * min(1.0, (ep - w) / max(w, 1))
        agg = {"G": 0.0, "D": 0.0, "L1": 0.0, "n": 0}
        for sar, real in dl_tr:
            sar, real = sar.to(dev), real.to(dev)
            fake = G(sar)

            # --- discriminator -----------------------------------------
            if gan_w > 0:
                optD.zero_grad(set_to_none=True)
                pr = D(sar, real)
                pf = D(sar, fake.detach())
                lossD = 0.5 * (gan_loss(pr, torch.full_like(pr, args.real_label))
                               + gan_loss(pf, torch.zeros_like(pf)))
                lossD.backward()
                optD.step()
            else:
                lossD = torch.zeros((), device=dev)

            # --- generator ---------------------------------------------
            optG.zero_grad(set_to_none=True)
            l1v = l1(fake, real)
            lossG = args.lambda_l1 * l1v
            if gan_w > 0:
                pf2 = D(sar, fake)
                lossG = lossG + gan_w * gan_loss(pf2, torch.ones_like(pf2))
            if perc is not None:
                lossG = lossG + args.lambda_perc * perc(fake, real)
            if args.lambda_grad > 0:
                lossG = lossG + args.lambda_grad * gradient_loss(fake, real)
            lossG.backward()
            optG.step()

            agg["G"] += lossG.item()
            agg["D"] += lossD.item()
            agg["L1"] += l1v.item()
            agg["n"] += 1

        # --- validation -----------------------------------------------
        G.eval()
        ps, ss, pc, sh, k = 0.0, 0.0, 0.0, 0.0, 0
        with torch.no_grad():
            for sar, real in dl_va:
                sar, real = sar.to(dev), real.to(dev)
                fake = G(sar)
                ps += psnr(fake, real)
                ss += ssim(fake, real)
                pc += eval_perc(fake, real).item()
                sh += sharpness_ratio(fake, real)
                k += 1
        schedG.step()
        schedD.step()
        n = max(agg["n"], 1)
        k = max(k, 1)
        row = {"epoch": ep, "G": agg["G"] / n, "D": agg["D"] / n, "L1": agg["L1"] / n,
               "val_psnr": ps / k, "val_ssim": ss / k, "val_perc": pc / k,
               "val_sharp": sh / k,
               "lr": schedG.get_last_lr()[0], "sec": time.time() - t0}
        hist.append(row)
        row["gan_w"] = gan_w
        print(f"ep {ep:3d}  gw {gan_w:.2f}  G {row['G']:7.3f}  D {row['D']:6.3f}  "
              f"L1 {row['L1']:.4f}  "
              f"PSNR {row['val_psnr']:5.2f}  SSIM {row['val_ssim']:6.3f}  "
              f"perc {row['val_perc']:.4f}  sharp {row['val_sharp']:.3f}  "
              f"{row['sec']:.0f}s", flush=True)

        if ep % args.sample_every == 0 or ep == args.epochs:
            sar, real = next(iter(dl_va))
            sar, real = sar[:4].to(dev), real[:4].to(dev)
            mean, conf, _ = mc_colorize(G, sar, n=8)
            save_grid(os.path.join(args.out, f"sample_ep{ep:03d}.png"),
                      sar, mean, real, conf)

        # lower perceptual distance is better; the others are higher-is-better.
        #
        # `balanced` is the one to use for sharpness work. Selecting on raw sharpness
        # alone is trivially gamed - pure noise scores a ratio far above 1 - so it is
        # perceptual distance PENALISED by how far the gradient energy sits from the
        # ground truth's. A model can only win by being both accurate and textured.
        score = {"perceptual": -row["val_perc"], "psnr": row["val_psnr"],
                 "ssim": row["val_ssim"], "last": float(ep),
                 "balanced": -(row["val_perc"] + 0.5 * abs(1.0 - row["val_sharp"])),
                 }[args.select]
        if score > best:
            best = score
            best_row = row
            torch.save({"G": G.state_dict(), "D": D.state_dict(),
                        "epoch": ep, "args": vars(args)},
                       os.path.join(args.out, "best.pt"))
        with open(os.path.join(args.out, "history.json"), "w", encoding="utf8") as fh:
            json.dump(hist, fh, indent=2)

    torch.save({"G": G.state_dict(), "epoch": args.epochs, "args": vars(args)},
               os.path.join(args.out, "last.pt"))
    if best_row:
        print(f"\nbest by {args.select} @ epoch {best_row['epoch']}:  "
              f"PSNR {best_row['val_psnr']:.2f}  SSIM {best_row['val_ssim']:.3f}  "
              f"perc {best_row['val_perc']:.4f}   -> {args.out}/best.pt")
    else:
        print(f"\nno checkpoint selected -> {args.out}/last.pt")


if __name__ == "__main__":
    main()
