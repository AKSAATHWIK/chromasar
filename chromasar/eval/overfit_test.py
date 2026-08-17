"""Diagnostic: can the generator overfit a handful of images?

If a network with 54M parameters cannot drive L1 near zero on 16 fixed images with no
augmentation and no adversarial term, the problem is a BUG in the data or model
plumbing - not learning rate, not epochs, not GAN balance. This test separates those
two worlds in about a minute, instead of guessing across GPU-hours.

    python eval/overfit_test.py
"""
from __future__ import annotations

import os
import sys
import time

import torch
import torch.nn as nn

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
for p in (ROOT, os.path.join(ROOT, "train")):
    sys.path.insert(0, p)

from config import SEN12_DIR                                    # noqa: E402
from dataset import SEN12Pairs                                  # noqa: E402
from resunet import build_generator                             # noqa: E402


def run(kind="unet", steps=300, n=16, lr=2e-4, lam=100.0):
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ds = SEN12Pairs(str(SEN12_DIR), "train", limit=n, augment=False)
    sar = torch.stack([ds[i][0] for i in range(len(ds))]).to(dev)
    real = torch.stack([ds[i][1] for i in range(len(ds))]).to(dev)
    print(f"{kind}: {sar.shape[0]} images  sar{list(sar.shape[1:])} "
          f"opt{list(real.shape[1:])}  device={dev}")
    print(f"  sar range [{sar.min():.2f},{sar.max():.2f}]  "
          f"opt range [{real.min():.2f},{real.max():.2f}]")

    G = build_generator(kind, pretrained=(kind != "unet")).to(dev)
    opt = torch.optim.Adam(G.parameters(), lr=lr, betas=(0.5, 0.999))
    l1 = nn.L1Loss()

    # baseline: what does predicting the dataset mean give us?
    const = real.mean(dim=(0, 2, 3), keepdim=True).expand_as(real)
    print(f"  L1 of constant-mean prediction = {l1(const, real).item():.4f}  "
          "(anything near this means NOT LEARNING)")

    t0 = time.time()
    G.train()
    for s in range(1, steps + 1):
        opt.zero_grad(set_to_none=True)
        loss = lam * l1(G(sar), real)
        loss.backward()
        opt.step()
        if s in (1, 10, 25, 50, 100, 150, 200, 250, 300) or s == steps:
            print(f"  step {s:4d}  L1 {loss.item()/lam:.4f}   {time.time()-t0:.0f}s",
                  flush=True)
    final = loss.item() / lam
    verdict = ("PASS - the pipeline can learn; the earlier failure is training "
               "dynamics" if final < 0.12 else
               "FAIL - cannot overfit 16 images. There is a bug in data or model.")
    print(f"  => final L1 {final:.4f}  {verdict}\n")
    return final


if __name__ == "__main__":
    run("unet")
