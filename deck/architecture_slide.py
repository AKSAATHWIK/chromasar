"""Wide, low-text architecture strip sized for a slide.

The full diagram (chromasar/reports/architecture.png) is for the repo and the report.
On a projector, small text is unreadable from row five - so this variant carries the ONE
idea that matters and nothing else: uncertainty is a gate, not a sibling branch.
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = os.path.dirname(os.path.abspath(__file__))
NAVY, ORANGE, TEAL = "#0B3C5D", "#C25E00", "#1F7A6C"
LIGHT, WARM, GREY, RED = "#EAF1F6", "#FBF0E6", "#5A6B78", "#A3282F"


def box(ax, x, y, w, h, title, sub=None, fc=LIGHT, ec=NAVY, tc=NAVY, lw=2.0, ts=13):
    ax.add_patch(FancyBboxPatch((x, y), w, h,
                                boxstyle="round,pad=0.01,rounding_size=0.02",
                                fc=fc, ec=ec, lw=lw, zorder=2))
    ax.text(x + w / 2, y + h * (0.62 if sub else 0.5), title, ha="center", va="center",
            fontsize=ts, fontweight="bold", color=tc, zorder=3)
    if sub:
        ax.text(x + w / 2, y + h * 0.24, sub, ha="center", va="center", fontsize=10,
                color=GREY, zorder=3, linespacing=1.3)


def arr(ax, p1, p2, c=NAVY, lw=2.6, rad=0.0):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle="-|>", mutation_scale=20,
                                 color=c, lw=lw, zorder=1, shrinkA=3, shrinkB=4,
                                 connectionstyle=f"arc3,rad={rad}"))


def main():
    fig, ax = plt.subplots(figsize=(16.0, 4.0))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 25)
    ax.axis("off")

    box(ax, 0.5, 9.5, 13, 7, "SAR input", "Sentinel-1\nVV · VH", fc="#FFFFFF", ec=GREY)
    arr(ax, (13.5, 13), (17.5, 13))

    box(ax, 17.5, 9.5, 16, 7, "ChromaSAR\nCORE", "conditional GAN",
        fc=NAVY, ec=NAVY, tc="#FFFFFF", ts=13)
    arr(ax, (33.5, 15), (38.5, 18.5))
    arr(ax, (33.5, 11), (38.5, 7.5))

    box(ax, 38.5, 16.5, 19, 6.5, "Colorized scene", "readable by any GIS user")
    box(ax, 38.5, 2.0, 19, 6.5, "Confidence map", "where the model is guessing",
        fc=WARM, ec=ORANGE, tc=ORANGE)

    arr(ax, (57.5, 19.5), (63.0, 15.5))
    arr(ax, (57.5, 5.5), (63.0, 10.5), c=ORANGE, lw=3.2)

    box(ax, 63.0, 8.5, 15.5, 9, "UNCERTAINTY\nGATE", None,
        fc=WARM, ec=ORANGE, tc=ORANGE, lw=3.0, ts=13)
    ax.text(70.75, 5.9, "low trust → “insufficient evidence”",
            ha="center", fontsize=10.5, color=ORANGE, style="italic")

    arr(ax, (78.5, 15.5), (83.5, 19.0), c=TEAL)
    arr(ax, (78.5, 13.0), (83.5, 13.0), c=TEAL)
    arr(ax, (78.5, 10.5), (83.5, 7.0), c=RED)

    box(ax, 83.5, 16.5, 16, 6, "Flood mapping", "IoU 0.681", fc="#FFFFFF", ec=TEAL,
        tc=TEAL, ts=12)
    box(ax, 83.5, 10.0, 16, 6, "Change detection", None, fc="#FFFFFF", ec=TEAL,
        tc=TEAL, ts=12)
    box(ax, 83.5, 3.5, 16, 6, "Alerts", "confidence-qualified", fc="#FBECEC", ec=RED,
        tc=RED, ts=12)

    fig.tight_layout(pad=0.2)
    p = os.path.join(OUT, "architecture_slide.png")
    fig.savefig(p, dpi=200, facecolor="white")
    print("wrote", p)


if __name__ == "__main__":
    main()
