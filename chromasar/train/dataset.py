"""SEN1-2 paired dataset.

One decision here matters more than the rest: **the train/val split is by SCENE, not by
patch.** Patches from one scene are adjacent tiles of the same place, so a random split
puts near-identical imagery on both sides and the validation score becomes a lie. Every
paper that reports suspiciously good SAR-colorization numbers should be read with that
in mind. Splitting by scene is harder and honest.
"""
from __future__ import annotations

import os
import random

import numpy as np
import torch
from PIL import Image
from torch.utils.data import Dataset


def load_exclusions(path):
    if path and os.path.exists(path):
        with open(path, encoding="utf8") as fh:
            return {ln.strip() for ln in fh if ln.strip()}
    return set()


class SEN12Pairs(Dataset):
    """Returns (sar[1,256,256], optical[3,256,256]), both scaled to [-1, 1]."""

    def __init__(self, root, split="train", val_frac=0.15, exclude_file=None,
                 seed=1733, augment=True, limit=None):
        self.root = root
        self.s1d = os.path.join(root, "s1")
        self.s2d = os.path.join(root, "s2")
        self.augment = augment and split == "train"

        excl = load_exclusions(exclude_file)
        # exclusion list is written with s2_ ids; normalise so either form matches
        excl_norm = {e.replace("_s2_", "_X_").replace("_s1_", "_X_") for e in excl}

        files = sorted(f for f in os.listdir(self.s1d) if f.endswith(".png"))
        kept, dropped = [], 0
        for f in files:
            scene = f.split("_p")[0].replace("_s1_", "_X_")
            if scene in excl_norm:
                dropped += 1
                continue
            kept.append(f)

        scenes = sorted({f.split("_p")[0] for f in kept})
        rng = random.Random(seed)
        rng.shuffle(scenes)
        n_val = max(1, int(len(scenes) * val_frac))
        val_scenes = set(scenes[:n_val])

        want_val = split == "val"
        self.files = [f for f in kept
                      if (f.split("_p")[0] in val_scenes) == want_val]
        if limit:
            self.files = self.files[:limit]
        self.n_scenes = len(val_scenes) if want_val else len(scenes) - len(val_scenes)
        self.dropped = dropped

    def __len__(self):
        return len(self.files)

    def __getitem__(self, i):
        f = self.files[i]
        sar = np.asarray(Image.open(os.path.join(self.s1d, f)).convert("L"),
                         dtype=np.float32)
        opt = np.asarray(
            Image.open(os.path.join(self.s2d, f.replace("_s1_", "_s2_"))).convert("RGB"),
            dtype=np.float32)

        if self.augment:
            if random.random() < 0.5:
                sar, opt = sar[:, ::-1], opt[:, ::-1]
            if random.random() < 0.5:
                sar, opt = sar[::-1], opt[::-1]
            k = random.randint(0, 3)
            if k:
                sar, opt = np.rot90(sar, k), np.rot90(opt, k)

        # These PNGs are already dB-scaled by the dataset authors (verified: skew -0.14,
        # median 138/255), so a fixed linear map is correct. Raw Sentinel-1 GRD would
        # need a log transform here instead.
        sar_t = torch.from_numpy(np.ascontiguousarray(sar)).unsqueeze(0) / 127.5 - 1.0
        opt_t = torch.from_numpy(np.ascontiguousarray(opt)).permute(2, 0, 1) / 127.5 - 1.0
        return sar_t, opt_t


def denorm(t):
    """[-1,1] tensor -> uint8 HWC array for saving."""
    a = (t.detach().cpu().float().clamp(-1, 1) + 1.0) * 127.5
    a = a.numpy()
    if a.ndim == 3:
        a = a.transpose(1, 2, 0)
    return a.round().astype(np.uint8)
