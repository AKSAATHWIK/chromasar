"""pix2pix U-Net generator and PatchGAN discriminator.

Dropout is deliberately kept in the decoder and is NOT disabled at inference. That is
what makes the confidence map possible: running the generator N times with dropout
active gives N plausible colourings, and their per-pixel disagreement is the model
telling us where it is guessing rather than inferring from the radar.
"""
from __future__ import annotations

import torch
import torch.nn as nn


class UNetBlock(nn.Module):
    """One level of the U-Net, built recursively from the innermost outward."""

    def __init__(self, outer_c, inner_c, input_c=None, submodule=None,
                 outermost=False, innermost=False, use_dropout=False, norm=nn.BatchNorm2d):
        super().__init__()
        self.outermost = outermost
        input_c = input_c or outer_c
        down_conv = nn.Conv2d(input_c, inner_c, 4, 2, 1, bias=False)
        down_relu = nn.LeakyReLU(0.2, True)
        down_norm = norm(inner_c)
        up_relu = nn.ReLU(True)
        up_norm = norm(outer_c)

        if outermost:
            up_conv = nn.ConvTranspose2d(inner_c * 2, outer_c, 4, 2, 1)
            down = [down_conv]
            up = [up_relu, up_conv, nn.Tanh()]
            model = down + [submodule] + up
        elif innermost:
            up_conv = nn.ConvTranspose2d(inner_c, outer_c, 4, 2, 1, bias=False)
            down = [down_relu, down_conv]
            up = [up_relu, up_conv, up_norm]
            model = down + up
        else:
            up_conv = nn.ConvTranspose2d(inner_c * 2, outer_c, 4, 2, 1, bias=False)
            down = [down_relu, down_conv, down_norm]
            up = [up_relu, up_conv, up_norm]
            model = down + [submodule] + up
            if use_dropout:
                model += [nn.Dropout(0.5)]
        self.model = nn.Sequential(*model)

    def forward(self, x):
        if self.outermost:
            return self.model(x)
        return torch.cat([x, self.model(x)], 1)


class UNetGenerator(nn.Module):
    def __init__(self, in_c=1, out_c=3, nf=64, depth=8, use_dropout=True):
        super().__init__()
        block = UNetBlock(nf * 8, nf * 8, submodule=None, innermost=True)
        for _ in range(depth - 5):
            block = UNetBlock(nf * 8, nf * 8, submodule=block, use_dropout=use_dropout)
        block = UNetBlock(nf * 4, nf * 8, submodule=block)
        block = UNetBlock(nf * 2, nf * 4, submodule=block)
        block = UNetBlock(nf, nf * 2, submodule=block)
        self.model = UNetBlock(out_c, nf, input_c=in_c, submodule=block, outermost=True)

    def forward(self, x):
        return self.model(x)


class PatchDiscriminator(nn.Module):
    """70x70 PatchGAN: judges local realism instead of one global real/fake score."""

    def __init__(self, in_c=4, nf=64, n_layers=3):
        super().__init__()
        layers = [nn.Conv2d(in_c, nf, 4, 2, 1), nn.LeakyReLU(0.2, True)]
        mult = 1
        for n in range(1, n_layers + 1):
            prev, mult = mult, min(2 ** n, 8)
            stride = 1 if n == n_layers else 2
            layers += [nn.Conv2d(nf * prev, nf * mult, 4, stride, 1, bias=False),
                       nn.BatchNorm2d(nf * mult), nn.LeakyReLU(0.2, True)]
        layers += [nn.Conv2d(nf * mult, 1, 4, 1, 1)]
        self.model = nn.Sequential(*layers)

    def forward(self, sar, opt):
        return self.model(torch.cat([sar, opt], 1))


def init_weights(net, gain=0.02):
    def fn(m):
        cls = m.__class__.__name__
        if hasattr(m, "weight") and ("Conv" in cls or "Linear" in cls):
            nn.init.normal_(m.weight.data, 0.0, gain)
            if getattr(m, "bias", None) is not None:
                nn.init.constant_(m.bias.data, 0.0)
        elif "BatchNorm2d" in cls:
            nn.init.normal_(m.weight.data, 1.0, gain)
            nn.init.constant_(m.bias.data, 0.0)
    net.apply(fn)
    return net


#: Divisor mapping MC-dropout spread onto a 0..1 confidence.
#: MEASURED, not guessed: over 2.62M validation pixels the per-pixel std of a 10-pass
#: ensemble is median 0.034, p95 0.061, p99 0.075. The original hand-picked 0.35 packed
#: 99% of pixels into confidence 0.79-0.95, so the gate slider did nothing across most
#: of its travel — it jumped straight from 0% to 100% gated between 0.80 and 0.95.
#: Using p99 spreads the real distribution across the full range.
CONF_SCALE = 0.075


@torch.no_grad()
def mc_colorize(gen, sar, n=10, scale=CONF_SCALE):
    """Monte-Carlo dropout ensemble -> (mean colourisation, per-pixel confidence).

    Dropout stays ON. Each pass is a different plausible answer; where the passes agree
    the model is reading real evidence out of the backscatter, and where they diverge it
    is inventing colour. Confidence is returned in [0,1], 1 = fully trusted.
    """
    was_training = gen.training
    gen.eval()
    # _DropoutNd covers Dropout, Dropout2d, Dropout3d and AlphaDropout. Matching only
    # nn.Dropout silently misses nn.Dropout2d - they are SIBLING classes, not parent
    # and child - which leaves the ResNet generator fully deterministic, makes every
    # MC pass identical, and pins confidence at 1.0 everywhere. The map looks perfect
    # and means nothing.
    n_active = 0
    for m in gen.modules():                 # re-enable dropout only
        if isinstance(m, torch.nn.modules.dropout._DropoutNd):
            m.train()
            n_active += 1
    if n_active == 0:
        raise RuntimeError(
            "mc_colorize: this generator has no dropout layers, so the confidence "
            "map would be a meaningless constant. Build it with dropout enabled.")

    # Dropout draws an independent mask per batch element, so tiling the input into a
    # single batch of n gives n genuinely independent samples - identical statistics to
    # n sequential forwards, but one pass instead of n. On CPU that is the difference
    # between ~13 s and ~2 s for a 256x256 tile.
    B = sar.shape[0]
    tiled = sar.repeat_interleave(n, dim=0)                   # [B*n,1,H,W]
    out = gen(tiled)                                          # [B*n,3,H,W]
    preds = out.view(B, n, *out.shape[1:]).transpose(0, 1)    # [n,B,3,H,W]
    mean = preds.mean(0)
    # spread across passes, averaged over colour channels
    std = preds.std(0).mean(1, keepdim=True)
    conf = (1.0 - (std / scale)).clamp(0, 1)

    gen.train(was_training)
    return mean, conf, std
