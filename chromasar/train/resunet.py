"""U-Net with an ImageNet-pretrained ResNet encoder.

Shared by BOTH tasks, deliberately:
  * colorization: in_ch=1 (SAR VV), out_ch=3, tanh output
  * flood segmentation: in_ch=2 (VV+VH), out_ch=1, logits

Why pretrained matters more for flood: Sen1Floods11 gives us 252 training chips. A
segmentation network trained from scratch on 252 images overfits badly. An ImageNet
encoder supplies edge/texture priors that 252 images cannot teach.

The honest caveat, which belongs in the pitch: ImageNet features come from natural
photographs and SAR is not a natural photograph. Transfer helps low-level texture more
than semantics. That is why we run it as an ABLATION against the from-scratch baseline
rather than assuming it wins.

First-conv adaptation: ResNet expects 3 channels. Rather than discarding the pretrained
first layer, we sum its RGB weights into the channels we actually have, which preserves
the filters' response magnitude instead of re-randomising them.
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class DecoderBlock(nn.Module):
    def __init__(self, in_c, skip_c, out_c, dropout=0.0):
        super().__init__()
        self.conv1 = nn.Conv2d(in_c + skip_c, out_c, 3, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(out_c)
        self.conv2 = nn.Conv2d(out_c, out_c, 3, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(out_c)
        self.drop = nn.Dropout2d(dropout) if dropout > 0 else None

    def forward(self, x, skip=None):
        x = F.interpolate(x, scale_factor=2, mode="nearest")
        if skip is not None:
            if x.shape[-2:] != skip.shape[-2:]:
                x = F.interpolate(x, size=skip.shape[-2:], mode="nearest")
            x = torch.cat([x, skip], 1)
        x = F.relu(self.bn1(self.conv1(x)), inplace=True)
        x = F.relu(self.bn2(self.conv2(x)), inplace=True)
        if self.drop is not None:
            x = self.drop(x)
        return x


class ResUNet(nn.Module):
    """ResNet18/34-encoder U-Net.

    dropout stays live at inference for the MC-dropout confidence map, exactly as in
    the from-scratch generator - so the uncertainty machinery works for both variants.
    """

    def __init__(self, in_ch=1, out_ch=3, encoder="resnet34", pretrained=True,
                 dropout=0.5, final="tanh"):
        super().__init__()
        from torchvision import models
        if encoder == "resnet34":
            weights = models.ResNet34_Weights.IMAGENET1K_V1 if pretrained else None
            net = models.resnet34(weights=weights)
            chans = [64, 64, 128, 256, 512]
        elif encoder == "resnet18":
            weights = models.ResNet18_Weights.IMAGENET1K_V1 if pretrained else None
            net = models.resnet18(weights=weights)
            chans = [64, 64, 128, 256, 512]
        else:
            raise ValueError(encoder)

        # --- adapt first conv to our channel count, keeping pretrained filters ---
        old = net.conv1
        new = nn.Conv2d(in_ch, 64, 7, stride=2, padding=3, bias=False)
        if pretrained:
            with torch.no_grad():
                w = old.weight                                # [64,3,7,7]
                if in_ch == 3:
                    new.weight.copy_(w)
                else:
                    # sum across RGB and share - preserves filter response magnitude
                    new.weight.copy_(w.sum(1, keepdim=True).repeat(1, in_ch, 1, 1) / in_ch)
        net.conv1 = new

        self.stem = nn.Sequential(net.conv1, net.bn1, net.relu)   # /2   64
        self.pool = net.maxpool                                   # /4
        self.enc1 = net.layer1                                    # /4   64
        self.enc2 = net.layer2                                    # /8  128
        self.enc3 = net.layer3                                    # /16 256
        self.enc4 = net.layer4                                    # /32 512

        self.dec4 = DecoderBlock(chans[4], chans[3], 256, dropout)
        self.dec3 = DecoderBlock(256, chans[2], 128, dropout)
        self.dec2 = DecoderBlock(128, chans[1], 64, dropout)
        self.dec1 = DecoderBlock(64, chans[0], 48, 0.0)
        self.dec0 = DecoderBlock(48, 0, 32, 0.0)
        self.head = nn.Conv2d(32, out_ch, 3, padding=1)
        self.final = final

    def forward(self, x):
        s0 = self.stem(x)          # /2
        s1 = self.enc1(self.pool(s0))
        s2 = self.enc2(s1)
        s3 = self.enc3(s2)
        s4 = self.enc4(s3)
        d = self.dec4(s4, s3)
        d = self.dec3(d, s2)
        d = self.dec2(d, s1)
        d = self.dec1(d, s0)
        d = self.dec0(d)
        out = self.head(d)
        if self.final == "tanh":
            out = torch.tanh(out)
        return out


def build_generator(kind="unet", nf=64, in_ch=1, out_ch=3, pretrained=True):
    """Factory so train.py can switch variants from one flag (the ablation axis)."""
    if kind == "unet":
        from models import UNetGenerator, init_weights
        return init_weights(UNetGenerator(in_ch, out_ch, nf))
    if kind in ("resnet18", "resnet34"):
        return ResUNet(in_ch, out_ch, encoder=kind, pretrained=pretrained)
    raise ValueError(kind)
