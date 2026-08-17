"""Run the trained colorizer on real held-out SAR tiles and lay the results out.

Deliberately shows the BEST and the WORST cases side by side. A panel of pictures where
everything works is not evidence, it is selection - and the failures are where the
confidence map has to justify itself.

Columns: SAR input | our colorization | ground truth | confidence (green trusted,
red guessing) | gated output (grey = refused).

    python eval/showcase.py --n 6
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import torch
from PIL import Image, ImageDraw

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
for p in (ROOT, os.path.join(ROOT, "train")):
    sys.path.insert(0, p)

from config import DATA_ROOT, REPORTS, SEN12_DIR                 # noqa: E402
from dataset import SEN12Pairs, denorm                           # noqa: E402
from metrics import psnr, ssim                                   # noqa: E402
from models import mc_colorize                                   # noqa: E402
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
    G.to(dev)
    print(f"model: {kind}, epoch {ck.get('epoch')}, "
          f"lambda_perc={ck.get('args', {}).get('lambda_perc')}")
    return G


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=6, help="rows: half best, half worst")
    ap.add_argument("--scan", type=int, default=120)
    ap.add_argument("--passes", type=int, default=10)
    ap.add_argument("--gate", type=float, default=0.55)
    args = ap.parse_args()
    os.makedirs(REPORTS, exist_ok=True)

    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    G = load(dev)
    ds = SEN12Pairs(str(SEN12_DIR), "val", augment=False, limit=args.scan,
                    exclude_file=os.path.join(REPORTS, "exclude_scenes.txt"))
    print(f"scanning {len(ds)} held-out patches from {ds.n_scenes} unseen scenes")

    rows = []
    for i in range(len(ds)):
        sar, real = ds[i]
        x = sar[None].to(dev)
        mean, conf, _ = mc_colorize(G, x, n=args.passes)
        r = real[None].to(dev)
        rows.append({
            "i": i,
            "psnr": psnr(mean, r),
            "ssim": ssim(mean, r),
            "conf": float(conf.mean()),
            "sar": sar, "real": real,
            "fake": mean[0].cpu(), "cmap": conf[0, 0].cpu(),
        })
    rows.sort(key=lambda d: -d["ssim"])
    half = max(1, args.n // 2)
    picks = rows[:half] + rows[-half:]

    cell, pad, cap = 200, 6, 20
    cols = 5
    W = cols * (cell + pad) + pad
    H = len(picks) * (cell + pad + cap) + pad + 26
    canvas = Image.new("RGB", (W, H), "#0a1119")
    d = ImageDraw.Draw(canvas)
    heads = ["SAR input", "ChromaSAR output", "ground truth (S2)",
             "confidence", f"gated @ {args.gate:.2f}"]
    for c, t in enumerate(heads):
        d.text((pad + c * (cell + pad) + 4, 7), t, fill="#9db0c4")

    for r_i, r in enumerate(picks):
        y = 26 + pad + r_i * (cell + pad + cap)
        sar_img = np.repeat(denorm(r["sar"])[:, :, :1], 3, 2)
        fake = denorm(r["fake"])
        real = denorm(r["real"])
        c = r["cmap"].numpy()
        heat = np.stack([(1 - c) * 255, c * 215, 70 + 40 * c], -1).astype(np.uint8)
        gated = fake.copy()
        gated[c < args.gate] = 84                       # refuse: neutral grey
        pct = 100.0 * float((c < args.gate).mean())

        for c_i, arr in enumerate([sar_img, fake, real, heat, gated]):
            canvas.paste(Image.fromarray(arr).resize((cell, cell)),
                         (pad + c_i * (cell + pad), y))
        d.text((pad + 4, y + cell + 4),
               f"PSNR {r['psnr']:.2f} dB   SSIM {r['ssim']:.3f}   "
               f"mean conf {r['conf']:.3f}   gated {pct:.1f}%",
               fill="#64788c")

    out = os.path.join(REPORTS, "colorization_showcase.png")
    canvas.save(out)
    best = picks[:half]
    worst = picks[half:]
    print(f"\nbest  {half}: SSIM {np.mean([r['ssim'] for r in best]):.3f}  "
          f"PSNR {np.mean([r['psnr'] for r in best]):.2f}  "
          f"conf {np.mean([r['conf'] for r in best]):.3f}")
    print(f"worst {half}: SSIM {np.mean([r['ssim'] for r in worst]):.3f}  "
          f"PSNR {np.mean([r['psnr'] for r in worst]):.2f}  "
          f"conf {np.mean([r['conf'] for r in worst]):.3f}")
    cb, cw = np.mean([r["conf"] for r in best]), np.mean([r["conf"] for r in worst])
    print("\nconfidence is " + ("HIGHER on good cases - the map is informative"
                                if cb > cw else
                                "NOT higher on good cases - the map is NOT predictive"))
    print("wrote", out)


if __name__ == "__main__":
    main()
