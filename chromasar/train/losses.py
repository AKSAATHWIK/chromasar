"""Perceptual loss on frozen ImageNet VGG16 features.

Why this exists: L1 alone rewards hedging. When the model is unsure whether a field is
green or brown, the pixel-wise-optimal answer is muddy olive - so plain L1 drives every
output toward a blurry average. That is precisely the failure mode ISRO's problem
statement complains about ("their performance is not satisfactory").

Comparing VGG features instead of pixels scores images on structure and texture, so a
sharp answer that is slightly wrong beats a blurry answer that is on-average right.

The VGG weights are ImageNet-pretrained and FROZEN - we use them as a fixed feature
extractor, we do not fine-tune them. That distinction matters when describing the work.
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

# ImageNet normalisation constants - VGG expects inputs in this distribution
_MEAN = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
_STD = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)


class VGGPerceptual(nn.Module):
    """Weighted L1 between VGG16 feature maps at several depths.

    Early layers capture edges and texture, deeper layers capture structure. Using a
    spread of depths keeps both.
    """

    # relu1_2, relu2_2, relu3_3, relu4_3
    SLICES = ((0, 4), (4, 9), (9, 16), (16, 23))
    WEIGHTS = (1.0, 0.75, 0.5, 0.35)

    def __init__(self, device="cpu", weights=None):
        super().__init__()
        from torchvision.models import VGG16_Weights, vgg16
        vgg = vgg16(weights=VGG16_Weights.IMAGENET1K_V1).features.eval()
        for p in vgg.parameters():
            p.requires_grad_(False)                     # frozen feature extractor
        self.blocks = nn.ModuleList(
            [nn.Sequential(*[vgg[i] for i in range(a, b)]) for a, b in self.SLICES])
        self.to(device)
        self.register_buffer("mean", _MEAN.to(device))
        self.register_buffer("std", _STD.to(device))
        self.w = weights or self.WEIGHTS

    def _prep(self, x):
        """[-1,1] -> ImageNet-normalised [0,1]."""
        x = (x.clamp(-1, 1) + 1.0) / 2.0
        return (x - self.mean) / self.std

    def forward(self, fake, real):
        f, r = self._prep(fake), self._prep(real)
        loss = fake.new_zeros(())
        for blk, w in zip(self.blocks, self.w):
            f = blk(f)
            r = blk(r)
            loss = loss + w * F.l1_loss(f, r)
        return loss


def gradient_penalty_free_ssim(a, b):
    """Cheap differentiable SSIM-ish term (global statistics) for the loss mix.

    Not a substitute for windowed SSIM in the metrics table - it is a regulariser.
    """
    a = (a + 1) / 2
    b = (b + 1) / 2
    mu_a, mu_b = a.mean(dim=(2, 3), keepdim=True), b.mean(dim=(2, 3), keepdim=True)
    va = ((a - mu_a) ** 2).mean(dim=(2, 3), keepdim=True)
    vb = ((b - mu_b) ** 2).mean(dim=(2, 3), keepdim=True)
    cov = ((a - mu_a) * (b - mu_b)).mean(dim=(2, 3), keepdim=True)
    c1, c2 = 0.01 ** 2, 0.03 ** 2
    ssim = (((2 * mu_a * mu_b + c1) * (2 * cov + c2))
            / ((mu_a ** 2 + mu_b ** 2 + c1) * (va + vb + c2)))
    return 1.0 - ssim.mean()


def gradient_loss(fake, real):
    """L1 between the two images' spatial gradients.

    Plain L1 on pixels is minimised by the conditional mean, so it actively rewards
    blur. Matching GRADIENTS instead makes flatness expensive: a smooth patch where the
    target has texture now costs, in a way that no amount of averaging can hide. This is
    the classic gradient-difference term (Mathieu et al. 2016), and it targets exactly
    the defect we measured - output five times softer than the ground truth.

    Cheap: two shifted subtractions, no extra network, unlike the VGG perceptual term.
    """
    fx = fake[..., :, 1:] - fake[..., :, :-1]
    rx = real[..., :, 1:] - real[..., :, :-1]
    fy = fake[..., 1:, :] - fake[..., :-1, :]
    ry = real[..., 1:, :] - real[..., :-1, :]
    return (fx - rx).abs().mean() + (fy - ry).abs().mean()
