"""Render the ChromaSAR system architecture.

The point of the drawing: uncertainty is not a sibling branch, it is a GATE. Every
downstream analytic is filtered by the confidence map, so a low-confidence region
produces "insufficient evidence" rather than a silent wrong answer.

    python scripts/architecture.py
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "reports")

NAVY = "#0B3C5D"
ORANGE = "#C25E00"
TEAL = "#1F7A6C"
GREY = "#5A6B78"
LIGHT = "#EAF1F6"
WARM = "#FBF0E6"
RED = "#A3282F"


def box(ax, x, y, w, h, title, sub=None, fc=LIGHT, ec=NAVY, tc=NAVY, lw=1.6,
        title_size=11, sub_size=8.4):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.02",
                                fc=fc, ec=ec, lw=lw, zorder=2))
    ty = y + h * (0.60 if sub else 0.5)
    ax.text(x + w / 2, ty, title, ha="center", va="center", fontsize=title_size,
            fontweight="bold", color=tc, zorder=3)
    if sub:
        ax.text(x + w / 2, y + h * 0.26, sub, ha="center", va="center",
                fontsize=sub_size, color=GREY, zorder=3, linespacing=1.35)


def arrow(ax, p1, p2, color=NAVY, lw=1.8, style="-|>", ls="-", rad=0.0, z=1):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle=style, mutation_scale=15,
                                 color=color, lw=lw, linestyle=ls, zorder=z,
                                 connectionstyle=f"arc3,rad={rad}",
                                 shrinkA=2, shrinkB=3))


def main():
    os.makedirs(OUT, exist_ok=True)
    fig, ax = plt.subplots(figsize=(13.6, 9.4))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    # ---------------- input ------------------------------------------
    box(ax, 36, 91, 28, 7, "Sentinel-1 SAR input",
        "VV · VH · VV/VH ratio   —   all-weather, day & night",
        fc="#FFFFFF", ec=GREY, tc=NAVY)
    arrow(ax, (50, 91), (50, 86.5))

    # ---------------- core -------------------------------------------
    box(ax, 26, 78, 48, 8.5, "ChromaSAR CORE — conditional generator",
        "Swin-UNet + PatchGAN,  land-cover conditioned",
        fc=NAVY, ec=NAVY, tc="#FFFFFF")
    ax.text(75.4, 82.2, "trained on\nSEN1-2 / SEN12MS", fontsize=7.6, color=GREY,
            va="center", ha="left", linespacing=1.3)

    # ---------------- two outputs ------------------------------------
    arrow(ax, (40, 78), (30, 71.5))
    arrow(ax, (60, 78), (70, 71.5))
    box(ax, 12, 63, 36, 8.5, "Colorized scene",
        "optically-interpretable imagery", fc=LIGHT, ec=NAVY)
    box(ax, 55, 63, 33, 8.5, "Confidence map", "per-pixel trust from\nMC-dropout ensemble",
        fc=WARM, ec=ORANGE, tc=ORANGE)

    # ---------------- the gate ---------------------------------------
    arrow(ax, (30, 63), (41, 55.8), rad=-0.10)
    arrow(ax, (71.5, 63), (59, 55.8), color=ORANGE, lw=2.4, rad=0.10)
    ax.text(50, 59.9, "gates every downstream decision", fontsize=8.8,
            color=ORANGE, style="italic", ha="center", zorder=4)

    box(ax, 33, 46.5, 34, 9, "UNCERTAINTY GATE",
        "below threshold → “insufficient evidence”,\nnever a silent wrong answer",
        fc=WARM, ec=ORANGE, tc=ORANGE, lw=2.2)

    # ---------------- analytics --------------------------------------
    for x, t, s in [(6, "Flood mapping",
                     "SAR water = specular\n(dark) → threshold\n+ change, Sen1Floods11"),
                    (36, "Change detection",
                     "bi-temporal log-ratio\nof backscatter"),
                    (66, "Land-cover change",
                     "class transitions\nover time")]:
        box(ax, x, 27, 28, 12.5, t, s, fc="#FFFFFF", ec=TEAL, tc=TEAL)
        arrow(ax, (x + 14 if x == 36 else (41 if x == 6 else 59), 46.5),
              (x + 14, 39.5), color=ORANGE, lw=1.7)

    # ---------------- reporting + alerts -----------------------------
    for x in (20, 50, 80):
        arrow(ax, (x, 27), (50, 20.5), color=TEAL, lw=1.5, rad=0.0)
    box(ax, 20, 12, 60, 8, "Reporting layer — natural language over MEASURED quantities",
        "“flooded area 12.4 km², 18% of it below confidence threshold”\n"
        "narrates computed numbers only — never interprets pixels",
        fc=LIGHT, ec=NAVY)

    arrow(ax, (50, 12), (50, 6.5), color=RED, lw=2.2)
    box(ax, 30, 0.5, 40, 6, "ALERTS  —  confidence-qualified",
        fc="#FBECEC", ec=RED, tc=RED, lw=2.0)

    ax.text(50, 99.4, "ChromaSAR — SAR interpretation that knows what it doesn't know",
            ha="center", fontsize=13.5, fontweight="bold", color=NAVY)

    fig.tight_layout()
    p = os.path.join(OUT, "architecture.png")
    fig.savefig(p, dpi=170, facecolor="white")
    fig.savefig(p.replace(".png", ".svg"), facecolor="white")
    print("wrote", p, "and .svg")


if __name__ == "__main__":
    main()
