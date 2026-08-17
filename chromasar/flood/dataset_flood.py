"""Sen1Floods11 dataset for segmentation training.

Handles the two traps in this data:
  * labels are {-1, 0, 1} and -1 means NO DATA. Those pixels must be excluded from the
    LOSS as well as the metrics - training against them teaches the network to predict
    "not water" for regions nobody ever labelled.
  * SAR chips contain NaN. Those are filled with the low-end clip value and masked out,
    never left as NaN (which would silently poison every gradient in the batch).
"""
from __future__ import annotations

import os
import random

import numpy as np
import tifffile
import torch
from torch.utils.data import Dataset

DB_LO, DB_HI = -30.0, 0.0        # Sentinel-1 GRD dB range that matters for water


def _norm_db(a):
    a = np.clip(a, DB_LO, DB_HI)
    return (a - DB_LO) / (DB_HI - DB_LO) * 2.0 - 1.0      # -> [-1, 1]


class FloodChips(Dataset):
    """-> (sar[2,H,W] in [-1,1], label[1,H,W] in {0,1}, valid[1,H,W] bool)"""

    def __init__(self, root, split="train", size=512, augment=None):
        self.root = root
        self.size = size
        self.augment = (split == "train") if augment is None else augment
        csv = os.path.join(root, "flood_handlabeled", f"flood_{split}_data.csv")
        names = []
        with open(csv, encoding="utf8") as fh:
            for line in fh:
                first = line.strip().split(",")[0]
                if first:
                    n = first.replace("_S1Hand.tif", "").replace(".tif", "")
                    if os.path.exists(os.path.join(root, "S1Hand", f"{n}_S1Hand.tif")):
                        names.append(n)
        self.names = names

    def __len__(self):
        return len(self.names)

    def __getitem__(self, i):
        n = self.names[i]
        sar = tifffile.imread(
            os.path.join(self.root, "S1Hand", f"{n}_S1Hand.tif")).astype(np.float32)
        lab = tifffile.imread(
            os.path.join(self.root, "LabelHand", f"{n}_LabelHand.tif")).astype(np.int16)

        nan = ~np.isfinite(sar)
        sar[nan] = DB_LO
        sar = _norm_db(sar)
        valid = (lab >= 0) & ~nan.any(0)          # unlabelled OR no-SAR -> excluded
        target = (lab == 1).astype(np.float32)

        if self.size and self.size != sar.shape[-1]:
            s = self.size
            sar = np.stack([_resize(c, s) for c in sar])
            target = _resize(target, s)
            valid = _resize(valid.astype(np.float32), s) > 0.5

        if self.augment:
            if random.random() < 0.5:
                sar, target, valid = sar[:, :, ::-1], target[:, ::-1], valid[:, ::-1]
            if random.random() < 0.5:
                sar, target, valid = sar[:, ::-1], target[::-1], valid[::-1]
            k = random.randint(0, 3)
            if k:
                sar = np.rot90(sar, k, axes=(1, 2))
                target = np.rot90(target, k)
                valid = np.rot90(valid, k)

        return (torch.from_numpy(np.ascontiguousarray(sar)),
                torch.from_numpy(np.ascontiguousarray(target))[None],
                torch.from_numpy(np.ascontiguousarray(valid.astype(np.float32)))[None])


def _resize(a, s):
    """Nearest-neighbour resize without pulling in scipy/cv2."""
    h, w = a.shape[-2:]
    yi = (np.arange(s) * h / s).astype(int).clip(0, h - 1)
    xi = (np.arange(s) * w / s).astype(int).clip(0, w - 1)
    return a[..., yi, :][..., :, xi]     # rows on axis -2, columns on axis -1


def masked_bce_dice(logits, target, valid, dice_w=1.0, eps=1e-6):
    """BCE + soft Dice, both restricted to labelled pixels.

    Dice matters here because water is a minority class on most chips; plain BCE lets
    the network score well by predicting "dry everywhere".
    """
    import torch.nn.functional as F
    bce = F.binary_cross_entropy_with_logits(logits, target, reduction="none")
    n = valid.sum().clamp(min=1.0)
    bce = (bce * valid).sum() / n

    p = torch.sigmoid(logits) * valid
    t = target * valid
    inter = (p * t).sum()
    dice = 1.0 - (2 * inter + eps) / (p.sum() + t.sum() + eps)
    return bce + dice_w * dice


@torch.no_grad()
def iou_counts(logits, target, valid, thr=0.5):
    p = ((torch.sigmoid(logits) > thr).float() * valid).bool()
    t = (target * valid).bool()
    tp = int((p & t).sum())
    fp = int((p & ~t).sum())
    fn = int((~p & t).sum())
    return tp, fp, fn
