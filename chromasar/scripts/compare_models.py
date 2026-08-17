"""Side-by-side: shipped colouriser vs the sharpened retrain.

Numbers alone cannot settle this one. The retrain traded perceptual fidelity for
texture - sharpness 0.073 -> 0.958, perceptual distance 2.03 -> 2.75 - and whether
that is a good trade is a judgement about what the output is FOR. So this renders the
same scenes through both models next to the real optical ground truth and lets a human
decide, rather than presenting a table and calling it settled.

    python chromasar/scripts/compare_models.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "chromasar"), str(ROOT / "chromasar" / "train")]

OUT = ROOT / "comparison"
N_TILES = 5


def load(path):
    from resunet import ResUNet
    from models import UNetGenerator
    ck = torch.load(path, map_location="cpu", weights_only=False)
    kind = ck.get("args", {}).get("generator", "unet")
    g = (UNetGenerator(1, 3, ck.get("args", {}).get("nf", 64)) if kind == "unet"
         else ResUNet(1, 3, encoder=kind, pretrained=False))
    g.load_state_dict(ck["G"])
    g.eval()
    return g, ck


def grad_energy(a: np.ndarray) -> float:
    x = a.astype(np.float32)
    if x.ndim == 3:
        x = x.mean(-1)
    gy, gx = np.gradient(x)
    return float(np.hypot(gx, gy).mean())


def main() -> int:
    data = Path(os.environ.get("SIH_DATA", Path.home() / "sih-data"))
    old_p = data / "checkpoints" / "colorization.pt"
    new_p = data / "checkpoints" / "sharpen" / "B-sharp-last.pt"
    if not new_p.exists():
        print("missing", new_p)
        return 1
    OUT.mkdir(exist_ok=True)

    old, ock = load(old_p)
    new, nck = load(new_p)
    print(f"old: epoch {ock.get('epoch')}  lambda_gan="
          f"{ock.get('args', {}).get('lambda_gan')}  "
          f"lambda_grad={ock.get('args', {}).get('lambda_grad', 0)}")
    print(f"new: epoch {nck.get('epoch')}  lambda_gan="
          f"{nck.get('args', {}).get('lambda_gan')}  "
          f"lambda_grad={nck.get('args', {}).get('lambda_grad')}")

    d1, d2 = data / "sen1-2" / "s1", data / "sen1-2" / "s2"
    # spread the picks across the corpus rather than taking the first N of one ROI
    files = sorted(d1.glob("*.png"))
    picks = [files[i] for i in np.linspace(0, len(files) - 1, N_TILES).astype(int)]

    CELL, PAD, HDR = 256, 10, 28
    sheet = Image.new("RGB", (CELL * 4 + PAD * 5, HDR + (CELL + PAD) * len(picks) + PAD),
                      (8, 11, 18))
    dr = ImageDraw.Draw(sheet)
    for i, t in enumerate(["SAR input", "SHIPPED (blurry)", "RETRAINED (sharp)",
                           "Sentinel-2 truth"]):
        dr.text((PAD + i * (CELL + PAD) + 6, 8), t, fill=(200, 214, 232))

    stats = []
    for r, f in enumerate(picks):
        s2 = d2 / f.name.replace("_s1_", "_s2_")
        if not s2.exists():
            continue
        sar = np.asarray(Image.open(f).convert("L"))
        truth = np.asarray(Image.open(s2).convert("RGB"))
        x = torch.from_numpy(sar.astype(np.float32) / 127.5 - 1.0)[None, None]
        with torch.no_grad():
            a = ((old(x)[0].permute(1, 2, 0).numpy() + 1) * 127.5).clip(0, 255)
            b = ((new(x)[0].permute(1, 2, 0).numpy() + 1) * 127.5).clip(0, 255)

        gt = grad_energy(truth)
        stats.append((grad_energy(a) / gt, grad_energy(b) / gt))

        y = HDR + r * (CELL + PAD) + PAD
        for c, im in enumerate([Image.fromarray(sar).convert("RGB"),
                                Image.fromarray(a.astype(np.uint8)),
                                Image.fromarray(b.astype(np.uint8)),
                                Image.fromarray(truth)]):
            sheet.paste(im.resize((CELL, CELL), Image.NEAREST),
                        (PAD + c * (CELL + PAD), y))

    sheet.save(OUT / "colorization-old-vs-new.png")
    o = np.mean([s[0] for s in stats])
    n = np.mean([s[1] for s in stats])
    print()
    print(f"sharpness vs real optical, mean of {len(stats)} tiles")
    print(f"  shipped    {o:.3f}   ({1/max(o,1e-9):.1f}x smoother than reality)")
    print(f"  retrained  {n:.3f}   ({1/max(n,1e-9):.1f}x smoother than reality)")
    print(f"  gain       {n/max(o,1e-9):.1f}x")
    print()
    print("wrote", OUT / "colorization-old-vs-new.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
