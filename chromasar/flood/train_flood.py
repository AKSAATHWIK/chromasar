"""Train a flood-segmentation U-Net on Sen1Floods11 and compare it to the threshold.

The point of this file is a single honest comparison:

    physics threshold (no training)  ->  IoU 0.550 on the official test split
    learned segmentation             ->  ?

252 training chips is very little, which is exactly why the encoder is ImageNet
pretrained. `--no-pretrained` runs the same architecture from scratch so the ablation
separates "U-Net helps" from "transfer learning helps".

    python flood/train_flood.py --epochs 40 --size 256          # CPU-friendly
    python flood/train_flood.py --epochs 60 --size 512 --batch 8 # GPU
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import torch
from torch.utils.data import DataLoader

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "train"))
sys.path.insert(0, os.path.dirname(_HERE))
from config import FLOODS_DIR, RUNS_DIR                         # noqa: E402
from dataset_flood import FloodChips, iou_counts, masked_bce_dice  # noqa: E402
from resunet import ResUNet                                     # noqa: E402


def evaluate(model, loader, dev, thr=0.5):
    model.eval()
    tp = fp = fn = 0
    with torch.no_grad():
        for sar, tgt, val in loader:
            sar, tgt, val = sar.to(dev), tgt.to(dev), val.to(dev)
            a, b, c = iou_counts(model(sar), tgt, val, thr)
            tp += a
            fp += b
            fn += c
    iou = tp / max(tp + fp + fn, 1)
    prec = tp / max(tp + fp, 1)
    rec = tp / max(tp + fn, 1)
    return iou, prec, rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(FLOODS_DIR))
    ap.add_argument("--out", default=str(RUNS_DIR / "flood"))
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--size", type=int, default=256)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--encoder", default="resnet34", choices=["resnet18", "resnet34"])
    ap.add_argument("--no-pretrained", action="store_true")
    ap.add_argument("--workers", type=int, default=0)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tr = FloodChips(args.data, "train", args.size)
    va = FloodChips(args.data, "valid", args.size, augment=False)
    te = FloodChips(args.data, "test", args.size, augment=False)
    print(f"device={dev}  train={len(tr)}  valid={len(va)}  test={len(te)}  "
          f"size={args.size}")

    dl_tr = DataLoader(tr, batch_size=args.batch, shuffle=True,
                       num_workers=args.workers, drop_last=len(tr) > args.batch)
    dl_va = DataLoader(va, batch_size=args.batch, num_workers=args.workers)
    dl_te = DataLoader(te, batch_size=args.batch, num_workers=args.workers)

    model = ResUNet(in_ch=2, out_ch=1, encoder=args.encoder,
                    pretrained=not args.no_pretrained, dropout=0.2,
                    final=None).to(dev)
    tag = f"{args.encoder}{'-scratch' if args.no_pretrained else '-imagenet'}"
    print(f"model={tag}  {sum(p.numel() for p in model.parameters())/1e6:.1f}M params")

    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs)

    best, hist = -1.0, []
    for ep in range(1, args.epochs + 1):
        model.train()
        t0, tot, k = time.time(), 0.0, 0
        for sar, tgt, val in dl_tr:
            sar, tgt, val = sar.to(dev), tgt.to(dev), val.to(dev)
            opt.zero_grad(set_to_none=True)
            loss = masked_bce_dice(model(sar), tgt, val)
            loss.backward()
            opt.step()
            tot += loss.item()
            k += 1
        sched.step()
        v_iou, v_p, v_r = evaluate(model, dl_va, dev)
        hist.append({"epoch": ep, "loss": tot / max(k, 1), "val_iou": v_iou,
                     "val_p": v_p, "val_r": v_r, "sec": time.time() - t0})
        print(f"ep {ep:3d}  loss {tot/max(k,1):.4f}  val IoU {v_iou:.3f} "
              f"(P {v_p:.3f} R {v_r:.3f})  {time.time()-t0:.0f}s", flush=True)
        if v_iou > best:
            best = v_iou
            torch.save({"model": model.state_dict(), "args": vars(args), "epoch": ep},
                       os.path.join(args.out, f"best_{tag}.pt"))
        with open(os.path.join(args.out, f"history_{tag}.json"), "w",
                  encoding="utf8") as fh:
            json.dump(hist, fh, indent=2)

    # ---- final: load best-on-validation, report ONCE on test ----------
    ck = torch.load(os.path.join(args.out, f"best_{tag}.pt"), map_location=dev)
    model.load_state_dict(ck["model"])
    t_iou, t_p, t_r = evaluate(model, dl_te, dev)
    print(f"\n{tag}  best val IoU {best:.3f} (epoch {ck['epoch']})")
    print(f"TEST  IoU {t_iou:.3f}  precision {t_p:.3f}  recall {t_r:.3f}")
    print(f"baseline (dual-pol threshold, no training):  IoU 0.550  P 0.754  R 0.671")


if __name__ == "__main__":
    main()
