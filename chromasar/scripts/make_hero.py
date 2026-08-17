"""Render the landing-page hero from REAL data.

The first hero was a vector satellite orbiting a wireframe globe. It was clip-art: the
satellite sat inside the globe, its beam fired into the planet's interior, and the swath
ellipse floated detached in the corner. No amount of easing fixes a drawing that is
lying about the geometry.

Sites that read as expensive - SpaceX, x.ai - do not draw a cartoon of the thing. They
show the thing, very large, with almost nothing around it. We have the thing: genuine
Sentinel-1 backscatter and the model's own output over it.

So the hero is now four real 512x512 frames exported straight from the pipeline:

    hero-sar.png    calibrated VV backscatter, the raw radar as an analyst sees it
    hero-color.png  the colorization generator's output for that scene
    hero-flood.png  the same scene with the calibrated water probability over it
    hero-conf.png   the per-pixel confidence map

    python chromasar/scripts/make_hero.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import tifffile
import torch
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "chromasar"), str(ROOT / "chromasar" / "train"),
                str(ROOT / "webapp")]

#: A scene with real, unambiguous flooding - the Brahmaputra in spate.
SCENE = "India_1018317"
OUT = ROOT / "frontend" / "public" / "hero"


def db_to_grey(a, lo=-25.0, hi=0.0):
    x = np.clip(np.nan_to_num(a, nan=lo), lo, hi)
    return ((x - lo) / (hi - lo) * 255).astype(np.uint8)


def main() -> int:
    data = Path(os.environ.get("SIH_DATA", Path.home() / "sih-data"))
    s1 = data / "sen1floods11" / "S1Hand" / f"{SCENE}_S1Hand.tif"
    ckpt = data / "checkpoints" / "flood_resnet34.pt"
    if not s1.exists():
        print("missing", s1)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)

    sar = tifffile.imread(s1).astype(np.float32)
    vv = sar[0]

    # ---- raw radar -------------------------------------------------------------
    grey = db_to_grey(vv)
    Image.fromarray(grey).convert("RGB").save(OUT / "hero-sar.png")

    # ---- calibrated water probability ------------------------------------------
    from resunet import ResUNet
    ck = torch.load(ckpt, map_location="cpu", weights_only=False)
    # exactly how webapp/server.py builds it - dropout 0.2, no final activation
    net = ResUNet(in_ch=2, out_ch=1, encoder="resnet34", pretrained=False,
                  dropout=0.2, final=None)
    net.load_state_dict(ck["model"])
    net.eval()

    x = np.clip(np.nan_to_num(sar[:2], nan=-30.0), -30.0, 0.0)
    x = (x + 30.0) / 30.0 * 2.0 - 1.0
    with torch.no_grad():
        prob = torch.sigmoid(net(torch.from_numpy(x)[None]) / 1.3678)[0, 0].numpy()

    # water rendered as depth, over the radar - the app's own palette
    rgb = np.stack([grey, grey, grey], -1).astype(np.float32)
    water = np.clip((prob - 0.35) / 0.5, 0, 1)[..., None]
    tint = np.array([46.0, 150.0, 235.0])
    rgb = rgb * (1 - water * 0.82) + tint * (water * 0.82)
    Image.fromarray(rgb.clip(0, 255).astype(np.uint8)).save(OUT / "hero-flood.png")

    # ---- colorization + confidence, if the generator is present ----------------
    cpath = data / "checkpoints" / "colorization.pt"
    if cpath.exists():
        from models import mc_colorize
        cc = torch.load(cpath, map_location="cpu", weights_only=False)
        kind = cc.get("args", {}).get("generator", "unet")
        if kind == "unet":
            from models import UNetGenerator
            gen = UNetGenerator(1, 3, cc.get("args", {}).get("nf", 64))
        else:
            gen = ResUNet(1, 3, encoder=kind, pretrained=False)
        gen.load_state_dict(cc["G"])
        gen.eval()
        one = (grey.astype(np.float32) / 127.5 - 1.0)[None, None]
        mean, conf, _ = mc_colorize(gen, torch.from_numpy(one), n=10)
        col = ((mean[0].permute(1, 2, 0).numpy() + 1) * 127.5).clip(0, 255)
        Image.fromarray(col.astype(np.uint8)).save(OUT / "hero-color.png")

        # low confidence -> amber, high -> teal. Same ordering as red/green but
        # separable for red-green colour blindness, and it matches the app's palette.
        c = conf[0, 0].numpy()[..., None]
        lo = np.array([255.0, 162.0, 74.0])       # --amber
        hi = np.array([46.0, 230.0, 200.0])       # --acc
        cm = lo * (1 - c) + hi * c
        Image.fromarray(cm.clip(0, 255).astype(np.uint8)).save(OUT / "hero-conf.png")

    for f in sorted(OUT.glob("*.png")):
        print(f"  {f.name:18} {f.stat().st_size / 1024:6.1f} KB")
    print(f"\nwrote to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
