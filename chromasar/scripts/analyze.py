"""Analyse the SEN1-2 subset: contact sheets, backscatter stats, bad-pair detection.

    python analyze.py --dest $SIH_DATA/sen1-2 --sheet 24

Writes into reports/:
    contact_sheet.png   SAR | optical side by side, for eyeballing pair quality
    worst_pairs.png     the pairs most likely to be junk (dark / flat optical)
    hallucination_risk.png   flat SAR but varied optical - where the model MUST guess
    stats.md            numbers worth quoting on a slide
"""
import argparse
import os
import random
from collections import defaultdict

import numpy as np
from PIL import Image, ImageDraw

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from config import SEN12_DIR


REPORTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")


def season_of(fn):
    return fn.split("_s1_")[0]


def load_pair(dest, fn):
    sar = np.array(Image.open(os.path.join(dest, "s1", fn)).convert("L"))
    opt = np.array(Image.open(os.path.join(dest, "s2", fn.replace("_s1_", "_s2_"))).convert("RGB"))
    return sar, opt


def grid(pairs, dest, path, cols=6, cell=128, captions=None):
    """Contact sheet: each cell is SAR above optical."""
    rows = (len(pairs) + cols - 1) // cols
    pad, cap = 6, 14
    cw, ch = cell, cell * 2 + cap
    img = Image.new("RGB", (cols * (cw + pad) + pad, rows * (ch + pad) + pad), "white")
    d = ImageDraw.Draw(img)
    for i, fn in enumerate(pairs):
        sar, opt = load_pair(dest, fn)
        x = pad + (i % cols) * (cw + pad)
        y = pad + (i // cols) * (ch + pad)
        img.paste(Image.fromarray(sar).convert("RGB").resize((cell, cell)), (x, y))
        img.paste(Image.fromarray(opt).resize((cell, cell)), (x, y + cell))
        label = captions[i] if captions else fn.split("_s1_")[-1].replace(".png", "")
        d.text((x + 2, y + cell * 2 + 1), label[:26], fill="black")
    img.save(path)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default=str(SEN12_DIR))
    ap.add_argument("--sheet", type=int, default=24)
    ap.add_argument("--scan", type=int, default=1500, help="how many pairs to compute stats on")
    args = ap.parse_args()
    os.makedirs(REPORTS, exist_ok=True)

    files = sorted(f for f in os.listdir(os.path.join(args.dest, "s1")) if f.endswith(".png"))
    if not files:
        print("no data yet - is the download still running?")
        return
    rng = random.Random(1733)
    print(f"{len(files)} pairs on disk")

    # ---- contact sheet -------------------------------------------------
    grid(rng.sample(files, min(args.sheet, len(files))), args.dest,
         os.path.join(REPORTS, "contact_sheet.png"))

    # ---- stats ---------------------------------------------------------
    scan = rng.sample(files, min(args.scan, len(files)))
    sar_hist = np.zeros(256, dtype=np.int64)
    by_season = defaultdict(list)
    rows = []
    for fn in scan:
        sar, opt = load_pair(args.dest, fn)
        sar_hist += np.bincount(sar.ravel(), minlength=256)
        opt_std = float(opt.std())
        opt_mean = float(opt.mean())
        sar_std = float(sar.std())
        rows.append((fn, sar.mean(), sar_std, opt_mean, opt_std))
        by_season[season_of(fn)].append((opt.reshape(-1, 3).mean(0), opt_mean))

    arr = np.array([[r[1], r[2], r[3], r[4]] for r in rows])
    dark = [r for r in rows if r[3] < 25]                     # near-black optical
    flat_opt = [r for r in rows if r[4] < 12]                 # no optical detail
    # flat SAR but varied optical => model has no evidence, must hallucinate
    risk = sorted(rows, key=lambda r: (r[2] / max(r[4], 1e-3)))[:12]

    # ---- problem sheets ------------------------------------------------
    worst = sorted(rows, key=lambda r: r[3])[:12]
    grid([r[0] for r in worst], args.dest, os.path.join(REPORTS, "worst_pairs.png"), cols=6,
         captions=[f"opt mean {r[3]:.0f}" for r in worst])
    grid([r[0] for r in risk], args.dest, os.path.join(REPORTS, "hallucination_risk.png"), cols=6,
         captions=[f"sar sd {r[2]:.0f}/opt sd {r[4]:.0f}" for r in risk])

    # ---- per-scene quality -------------------------------------------
    # Natural RGB has strongly correlated channels. False-colour / corrupted optical
    # patches decorrelate them, which is a cheap and reliable anomaly signal.
    scene_stats = defaultdict(list)
    for fn in scan:
        _, opt = load_pair(args.dest, fn)
        f = opt.reshape(-1, 3).astype(np.float64)
        c = np.corrcoef(f.T)
        corr = float(np.nanmean([c[0, 1], c[0, 2], c[1, 2]]))
        mx = f.max(1)
        mn = f.min(1)
        satur = float(np.mean((mx - mn) / np.maximum(mx, 1e-6)))
        scene = fn.split("_p")[0]
        scene_stats[scene].append((corr, satur, f.mean()))

    suspect = []
    for scene, vals in scene_stats.items():
        if len(vals) < 3:
            continue
        corr = float(np.mean([v[0] for v in vals]))
        satur = float(np.mean([v[1] for v in vals]))
        bright = float(np.mean([v[2] for v in vals]))
        reason = None
        if bright < 25:
            reason = f"near-black (mean {bright:.0f})"
        elif corr < 0.35 and satur > 0.45:
            reason = f"channel decorrelation {corr:.2f}, saturation {satur:.2f}"
        if reason:
            suspect.append((scene, len(vals), reason))
    suspect.sort(key=lambda r: -r[1])

    with open(os.path.join(REPORTS, "exclude_scenes.txt"), "w", encoding="utf8") as fh:
        for scene, _, _ in suspect:
            fh.write(scene + "\n")

    # ---- write up ------------------------------------------------------
    cum = np.cumsum(sar_hist) / sar_hist.sum()
    p50 = int(np.searchsorted(cum, 0.50))
    p90 = int(np.searchsorted(cum, 0.90))
    p99 = int(np.searchsorted(cum, 0.99))

    # describe the ACTUAL distribution rather than assuming the textbook one
    vals = np.arange(256, dtype=np.float64)
    w = sar_hist / sar_hist.sum()
    mu = float((vals * w).sum())
    sd = float(np.sqrt(((vals - mu) ** 2 * w).sum()))
    skew = float((((vals - mu) / max(sd, 1e-9)) ** 3 * w).sum())
    sat = 100 * float(w[255])

    if skew > 0.4:
        skew_note = (
            f"Right-skewed (skew {skew:+.2f}): most of the scene is dark and a few bright "
            "scatterers carry a long tail — the classic raw-backscatter shape.")
        norm_note = ("normalise per-patch, not globally — otherwise a handful of bright "
                     "pixels compress everything else into a narrow band.")
    elif skew < -0.4:
        skew_note = (f"Left-skewed (skew {skew:+.2f}): the bulk of pixels sit high with a "
                     "tail into the darks.")
        norm_note = "check for clipping at the bright end before choosing a normalisation."
    else:
        skew_note = (
            f"**Roughly symmetric** (skew {skew:+.2f}, median {p50}/255). This is *not* the "
            "long-tailed shape of raw SAR backscatter — these PNGs have already been "
            "dB-scaled and contrast-stretched by the dataset authors. Worth knowing: it "
            "means we are training on preprocessed imagery, not raw returns.")
        norm_note = (
            "a simple fixed [-1, 1] scaling is fine here — no log transform needed, since "
            "the dB conversion has already been applied. **But** when we move to raw "
            "Sentinel-1 GRD for the Indian-terrain data, that step comes back and the "
            "normalisation must change with it.")
    if sat > 2:
        skew_note += (f" Note {sat:.1f}% of pixels are saturated at 255 — real bright "
                      "scatterers are being clipped.")

    lines = [
        "# SEN1-2 subset — data analysis",
        "",
        f"Pairs on disk: **{len(files)}**  |  scanned for stats: **{len(scan)}**",
        "",
        "## SAR backscatter distribution",
        "",
        f"- median pixel value **{p50}**, 90th pct **{p90}**, 99th pct **{p99}**",
        f"- mean {arr[:, 0].mean():.1f}, std {arr[:, 1].mean():.1f}, "
        f"skewness **{skew:+.2f}**",
        "",
        skew_note,
        "",
        f"**Decision this drives:** {norm_note}",
        "",
        "## Pair quality",
        "",
        f"- near-black optical patches (mean < 25): **{len(dark)}** "
        f"({100 * len(dark) / len(scan):.1f}%)",
        f"- flat optical patches (std < 12): **{len(flat_opt)}** "
        f"({100 * len(flat_opt) / len(scan):.1f}%)",
        "",
        "These are the pairs to consider filtering — a black optical target teaches the "
        "model to output black. See `worst_pairs.png` and judge by eye before deciding.",
        "",
        "## Where hallucination is guaranteed",
        "",
        "`hallucination_risk.png` shows pairs with **flat SAR but varied optical** — the "
        "radar carries almost no information yet the answer is colourful. The model cannot "
        "do anything but guess here.",
        "**These are the demo cases for the confidence map.** If it does not light up on "
        "these, it does not work.",
        "",
        "## Suspect scenes (recommend excluding)",
        "",
        f"**{len(suspect)}** scenes flagged. Written to `reports/exclude_scenes.txt` so the "
        "training loader can skip them.",
        "",
        "| scene | patches scanned | why |",
        "|---|---|---|",
    ]
    for scene, n, reason in suspect[:20]:
        lines.append(f"| {scene} | {n} | {reason} |")
    lines += [
        "",
        "Natural RGB imagery has strongly correlated colour channels. Where correlation "
        "collapses *and* saturation is high, the optical target is not plausible natural "
        "colour — training against it teaches the model to invent colour that has no "
        "physical basis.",
        "",
        "## Season breakdown",
        "",
        "| season | pairs | mean optical R,G,B |",
        "|---|---|---|",
    ]
    for s, vals in sorted(by_season.items()):
        rgb = np.array([v[0] for v in vals]).mean(0)
        lines.append(f"| {s} | {len(vals)} | {rgb[0]:.0f}, {rgb[1]:.0f}, {rgb[2]:.0f} |")
    lines += ["", "Generated by `scripts/analyze.py`."]

    with open(os.path.join(REPORTS, "stats.md"), "w", encoding="utf8") as fh:
        fh.write("\n".join(lines))

    print("\n".join(lines[:24]))
    print(f"\nwrote {REPORTS}\\contact_sheet.png, worst_pairs.png, "
          f"hallucination_risk.png, stats.md")


if __name__ == "__main__":
    main()
