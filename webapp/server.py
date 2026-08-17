"""ChromaSAR web application - FastAPI backend with live model inference.

Design decision that makes the UI feel instant: the server returns the model's raw
PROBABILITY map, not a thresholded mask. The browser thresholds it on a canvas and
recomputes IoU/precision/recall in JavaScript, so dragging the confidence slider
re-gates the result with no round trip. That is the interaction that demonstrates the
whole thesis - you can watch the confidence gate open and close.

    python webapp/server.py
    -> http://127.0.0.1:8000
"""
from __future__ import annotations

import base64
import io
import json
import os
import sys
import time
from pathlib import Path

from functools import lru_cache

import tifffile

import numpy as np
import torch
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "chromasar"))
sys.path.insert(0, str(ROOT / "chromasar" / "train"))
sys.path.insert(0, str(ROOT / "chromasar" / "flood"))

from config import FLOODS_DIR, SEN12_DIR, DATA_ROOT          # noqa: E402
from resunet import ResUNet                                  # noqa: E402

CKPT_DIR = DATA_ROOT / "checkpoints"
# temperature fitted on the validation split (eval/temperature.py). Applying it makes
# the served probabilities mean what they say: ECE 0.0293 -> 0.0160 on test.
_TJSON = Path(__file__).resolve().parent.parent / "chromasar" / "reports" / "temperature.json"
TEMPERATURE = 1.0
if _TJSON.exists():
    try:
        TEMPERATURE = float(json.loads(_TJSON.read_text())["temperature"])
    except Exception:
        pass
FLOOD_CKPT = CKPT_DIR / "flood_resnet34.pt"
COLOR_CKPT = CKPT_DIR / "colorization.pt"
STATIC = Path(__file__).resolve().parent / "static"

app = FastAPI(title="ChromaSAR")
DEV = torch.device("cuda" if torch.cuda.is_available() else "cpu")
_models = {}


# --------------------------------------------------------------- utilities
def scene_geo(name: str):
    """Georeferencing for a benchmark chip, or None if the tif is missing.

    Cached because /api/flood/batch resolves a whole region and every call re-opens the
    file otherwise.
    """
    from geo import read_geotiff_geo
    f = Path(FLOODS_DIR) / "S1Hand" / f"{name}_S1Hand.tif"
    if not f.exists():
        return None
    return _geo_cached(str(f))


@lru_cache(maxsize=1024)
def _geo_cached(path: str):
    from geo import read_geotiff_geo
    try:
        return read_geotiff_geo(path)
    except Exception:                                            # noqa: BLE001
        return None


def png_b64(arr: np.ndarray) -> str:
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    im = Image.fromarray(arr)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def db_to_grey(vv, lo=-25.0, hi=0.0):
    a = np.clip((vv - lo) / (hi - lo), 0, 1)
    a[~np.isfinite(vv)] = 0
    return (a * 255).astype(np.uint8)


def load_flood():
    if "flood" in _models:
        return _models["flood"]
    if not FLOOD_CKPT.exists():
        return None
    m = ResUNet(in_ch=2, out_ch=1, encoder="resnet34", pretrained=False,
                dropout=0.2, final=None)
    ck = torch.load(FLOOD_CKPT, map_location=DEV, weights_only=False)
    m.load_state_dict(ck["model"])
    m.eval().to(DEV)
    _models["flood"] = m
    print(f"loaded flood model (epoch {ck.get('epoch')})")
    return m


def load_color():
    if "color" in _models:
        return _models["color"]
    if not COLOR_CKPT.exists():
        return None
    ck = torch.load(COLOR_CKPT, map_location=DEV, weights_only=False)
    kind = ck.get("args", {}).get("generator", "unet")
    if kind == "unet":
        from models import UNetGenerator
        m = UNetGenerator(1, 3, ck.get("args", {}).get("nf", 64))
    else:
        m = ResUNet(1, 3, encoder=kind, pretrained=False)
    m.load_state_dict(ck["G"])
    m.eval().to(DEV)
    _models["color"] = m
    print(f"loaded colorization model ({kind}, epoch {ck.get('epoch')})")
    return m


# --------------------------------------------------------------- API
@app.get("/api/status")
def status():
    n_flood = len(list((Path(FLOODS_DIR) / "S1Hand").glob("*.tif"))) \
        if (Path(FLOODS_DIR) / "S1Hand").exists() else 0
    n_sar = len(list((Path(SEN12_DIR) / "s1").glob("*.png"))) \
        if (Path(SEN12_DIR) / "s1").exists() else 0
    return {
        "device": str(DEV),
        "flood_model": FLOOD_CKPT.exists(),
        "temperature": round(TEMPERATURE, 4),
        "color_model": COLOR_CKPT.exists(),
        "flood_chips": n_flood,
        "sar_pairs": n_sar,
    }


@app.get("/api/flood/samples")
def flood_samples(limit: int = 40):
    d = Path(FLOODS_DIR) / "S1Hand"
    if not d.exists():
        raise HTTPException(404, "Sen1Floods11 not found")
    names = sorted(p.stem.replace("_S1Hand", "") for p in d.glob("*.tif"))
    regions = {}
    for n in names:
        regions.setdefault(n.split("_")[0], []).append(n)
    return {"regions": {k: v[:limit] for k, v in sorted(regions.items())},
            "total": len(names)}


@app.get("/api/flood/predict")
def flood_predict(name: str):
    """Return SAR, hand-label and the raw PROBABILITY map.

    Thresholding happens in the browser so the slider is instant.
    """
    import tifffile
    t0 = time.time()
    s1p = Path(FLOODS_DIR) / "S1Hand" / f"{name}_S1Hand.tif"
    lbp = Path(FLOODS_DIR) / "LabelHand" / f"{name}_LabelHand.tif"
    if not s1p.exists():
        raise HTTPException(404, f"unknown chip {name}")

    g = scene_geo(name)
    sar = tifffile.imread(s1p).astype(np.float32)
    lab = tifffile.imread(lbp).astype(np.int16) if lbp.exists() else None

    model = load_flood()
    if model is None:
        raise HTTPException(503, "flood model not available")

    x = np.clip(np.nan_to_num(sar, nan=-30.0), -30.0, 0.0)
    x = (x + 30.0) / 30.0 * 2.0 - 1.0
    with torch.no_grad():
        logits = model(torch.from_numpy(x)[None].to(DEV))
        prob = torch.sigmoid(logits / TEMPERATURE)[0, 0].cpu().numpy()

    permp = Path(FLOODS_DIR) / "JRCWaterHand" / f"{name}_JRCWaterHand.tif"
    perm = (tifffile.imread(permp).astype(np.uint8) == 1) if permp.exists() else None

    out = {
        "name": name,
        "temperature": round(TEMPERATURE, 4),
        "sar_vv": png_b64(db_to_grey(sar[0])),
        "sar_vh": png_b64(db_to_grey(sar[1], -32, -5)),
        "prob": png_b64((prob * 255).astype(np.uint8)),
        "ms": round((time.time() - t0) * 1000),
        "size": list(prob.shape),
        # the client used to multiply pixels by a flat 100 m^2 of its own, so the
        # metric tile read 15.06 km2 while the report card beside it said 13.42
        "pixel_m2": round(g.pixel_m2, 4) if g else 100.0,
    }
    if perm is not None:
        out["permanent"] = png_b64((perm * 255).astype(np.uint8))
        out["permanent_frac"] = float(perm.mean())
    if lab is not None:
        # encode truth AND validity: 0 = dry, 255 = water, 128 = unlabelled(-1)
        enc = np.full(lab.shape, 128, dtype=np.uint8)
        enc[lab == 0] = 0
        enc[lab == 1] = 255
        out["label"] = png_b64(enc)
        out["water_frac"] = float((lab == 1).sum() / max((lab >= 0).sum(), 1))
    return out


def _analyse(name, thr=0.5, exclude_permanent=True):
    """Compute every quantity the report narrates. Numbers only - no interpretation."""
    import tifffile
    s1p = Path(FLOODS_DIR) / "S1Hand" / f"{name}_S1Hand.tif"
    if not s1p.exists():
        raise HTTPException(404, f"unknown chip {name}")
    g = scene_geo(name)
    sar = tifffile.imread(s1p).astype(np.float32)
    model = load_flood()
    if model is None:
        raise HTTPException(503, "flood model not available")
    x = np.clip(np.nan_to_num(sar, nan=-30.0), -30.0, 0.0)
    x = (x + 30.0) / 30.0 * 2.0 - 1.0
    with torch.no_grad():
        prob = torch.sigmoid(
            model(torch.from_numpy(x)[None].to(DEV)) / TEMPERATURE)[0, 0].cpu().numpy()

    permp = Path(FLOODS_DIR) / "JRCWaterHand" / f"{name}_JRCWaterHand.tif"
    perm = (tifffile.imread(permp).astype(np.uint8) == 1) if permp.exists()         else np.zeros(prob.shape, bool)
    lbp = Path(FLOODS_DIR) / "LabelHand" / f"{name}_LabelHand.tif"
    lab = tifffile.imread(lbp).astype(np.int16) if lbp.exists() else None

    # Sen1Floods11 is in a GEOGRAPHIC crs, so the pixel scale is in degrees and a
    # degree of longitude shrinks as cos(lat). A flat 100 m^2/pixel overstated ground
    # area by +11.9% for India, +14.6% for Pakistan and +28.4% for the USA scenes.
    g = scene_geo(name)
    px_km2 = (g.pixel_m2 / 1e6) if g else (10.0 ** 2) / 1e6
    water = prob > thr
    flood = water & ~perm if exclude_permanent else water
    low_conf = float(((prob > 0.25) & (prob < 0.75)).mean())

    out = {
        "scene": name, "region": name.split("_")[0], "threshold": thr,
        "place": g.label if g else None,
        "country": g.country if g else None,
        "continent": g.continent if g else None,
        "lat": round(g.lat, 5) if g else None,
        "lon": round(g.lon, 5) if g else None,
        "coords": g.dms if g else None,
        "pixel_m2": round(g.pixel_m2, 2) if g else None,
        "water_km2": round(float(water.sum()) * px_km2, 3),
        "permanent_km2": round(float((water & perm).sum()) * px_km2, 3),
        "flood_km2": round(float(flood.sum()) * px_km2, 3),
        "scene_km2": round(float(prob.size) * px_km2, 3),
        "uncertain_fraction": round(low_conf, 4),
        "mean_probability": round(float(prob.mean()), 4),
    }
    out["flood_pct_of_scene"] = round(100 * out["flood_km2"] / max(out["scene_km2"], 1e-9), 2)
    if lab is not None:
        valid = lab >= 0
        t = (lab == 1) & (~perm if exclude_permanent else True)
        p = flood & valid
        tp = int((p & t & valid).sum()); fp = int((p & ~t & valid).sum())
        fn = int((~p & t & valid).sum())
        out["iou"] = round(tp / max(tp + fp + fn, 1), 4)
        out["precision"] = round(tp / max(tp + fp, 1), 4)
        out["recall"] = round(tp / max(tp + fn, 1), 4)
    return out


@app.get("/api/flood/report")
def flood_report(name: str, thr: float = 0.5, exclude_permanent: bool = True):
    """Natural-language bulletin over MEASURED quantities.

    Every sentence is generated from a number computed above - the text never
    interprets pixels. That is the distinction that keeps this from being another
    hallucinating image-captioner.
    """
    a = _analyse(name, thr, exclude_permanent)
    sev = ("negligible" if a["flood_pct_of_scene"] < 1 else
           "localised" if a["flood_pct_of_scene"] < 5 else
           "significant" if a["flood_pct_of_scene"] < 20 else "severe")
    lines = [
        f"Scene {a['scene']} ({a['region']}) covers {a['scene_km2']:.1f} km2 "
        f"at 10 m ground sampling.",
        f"Surface water detected over {a['water_km2']:.2f} km2 at a decision "
        f"threshold of {a['threshold']:.2f}.",
    ]
    if a["permanent_km2"] > 0:
        lines.append(
            f"Of that, {a['permanent_km2']:.2f} km2 coincides with permanent water "
            f"bodies in the JRC reference layer and is therefore not flooding.")
    lines.append(
        f"Estimated flood extent is {a['flood_km2']:.2f} km2, "
        f"{a['flood_pct_of_scene']:.1f}% of the scene - classified {sev}.")
    lines.append(
        f"{100*a['uncertain_fraction']:.1f}% of pixels fall in the low-confidence band "
        f"(0.25-0.75) where the model is not decisive; these should be reviewed "
        f"by an analyst rather than acted on automatically.")
    if "iou" in a:
        lines.append(
            f"Against hand labels for this scene: IoU {a['iou']:.3f}, "
            f"precision {a['precision']:.3f}, recall {a['recall']:.3f}.")
    lines.append(
        "Probabilities are temperature-calibrated (T=%.3f); expected calibration "
        "error on the held-out test split is 0.016." % TEMPERATURE)
    return {"metrics": a, "narrative": lines,
            "alert": a["flood_pct_of_scene"] >= 5 and a["uncertain_fraction"] < 0.35,
            "severity": sev}


@app.get("/api/flood/batch")
def flood_batch(region: str, limit: int = 8, thr: float = 0.5):
    """Aggregate a whole region - the operational view, not one chip."""
    d = Path(FLOODS_DIR) / "S1Hand"
    names = sorted(p.stem.replace("_S1Hand", "") for p in d.glob(f"{region}_*.tif"))
    names = names[:limit]
    if not names:
        raise HTTPException(404, f"no chips for region {region}")
    rows, t0 = [], time.time()
    for n in names:
        try:
            rows.append(_analyse(n, thr))
        except HTTPException:
            continue
    tot_f = sum(r["flood_km2"] for r in rows)
    tot_w = sum(r["water_km2"] for r in rows)
    tot_p = sum(r["permanent_km2"] for r in rows)
    ious = [r["iou"] for r in rows if "iou" in r]
    return {
        "region": region, "chips": len(rows),
        "flood_km2": round(tot_f, 2), "water_km2": round(tot_w, 2),
        "permanent_km2": round(tot_p, 2),
        "mean_iou": round(sum(ious) / len(ious), 4) if ious else None,
        "worst": sorted(rows, key=lambda r: -r["flood_km2"])[:5],
        "ms": round((time.time() - t0) * 1000),
    }


@app.get("/api/flood/export")
def flood_export(name: str, thr: float = 0.5, exclude_permanent: bool = True,
                 kind: str = "geotiff"):
    """Export the detection as a real, georeferenced GeoTIFF.

    This is what makes the output usable rather than a screenshot: the geotransform
    and CRS are copied from the source Sentinel-1 chip, so the mask drops straight
    into QGIS or ArcGIS on top of the original imagery.
    """
    import tifffile
    s1p = Path(FLOODS_DIR) / "S1Hand" / f"{name}_S1Hand.tif"
    if not s1p.exists():
        raise HTTPException(404, f"unknown chip {name}")

    a = _analyse(name, thr, exclude_permanent)
    g = scene_geo(name)
    sar = tifffile.imread(s1p).astype(np.float32)
    model = load_flood()
    x = np.clip(np.nan_to_num(sar, nan=-30.0), -30.0, 0.0)
    x = (x + 30.0) / 30.0 * 2.0 - 1.0
    with torch.no_grad():
        prob = torch.sigmoid(
            model(torch.from_numpy(x)[None].to(DEV)) / TEMPERATURE)[0, 0].cpu().numpy()
    permp = Path(FLOODS_DIR) / "JRCWaterHand" / f"{name}_JRCWaterHand.tif"
    perm = (tifffile.imread(permp).astype(np.uint8) == 1) if permp.exists()         else np.zeros(prob.shape, bool)
    mask = (prob > thr)
    if exclude_permanent:
        mask = mask & ~perm

    # Reject an unrecognised kind instead of falling through to the mask. The old
    # else-branch returned the uint8 mask for ANY value while stamping the requested
    # name into the embedded description - so a typo produced a file whose provenance
    # string disagreed with its own contents, which is the worst kind of wrong.
    if kind not in ("mask", "geotiff", "probability"):
        raise HTTPException(
            400, f"unknown export kind {kind!r}; expected 'mask' or 'probability'. "
                 f"The situation report is exported as JSON by the client, not here.")

    buf = io.BytesIO()
    if kind == "probability":
        payload, dtype = prob.astype(np.float32), "float32"
    else:
        payload, dtype = mask.astype(np.uint8), "uint8"

    # carry over the source georeferencing tags so the export lands in the right place
    geotags = []
    try:
        with tifffile.TiffFile(s1p) as tf:
            page = tf.pages[0]
            for code in (33550, 33922, 34735, 34736, 34737):     # pixel scale, tiepoint,
                if code in page.tags:                            # geokeys
                    t = page.tags[code]
                    geotags.append((t.code, t.dtype, t.count, t.value, True))
    except Exception:                                            # noqa: BLE001
        pass
    tifffile.imwrite(buf, payload, extratags=geotags,
                     description=f"ChromaSAR {kind} | scene={name} thr={thr} "
                                 f"exclude_permanent={exclude_permanent} "
                                 f"flood_km2={a['flood_km2']}")
    buf.seek(0)
    fn = f"chromasar_{name}_{'prob' if kind=='probability' else 'flood'}.tif"
    from fastapi.responses import Response
    return Response(buf.getvalue(), media_type="image/tiff",
                    headers={"Content-Disposition": f'attachment; filename="{fn}"',
                             "X-Flood-Km2": str(a["flood_km2"]),
                             "X-Georeferenced": str(bool(geotags))})


@app.get("/api/color/samples")
def color_samples(limit: int = 40):
    d = Path(SEN12_DIR) / "s1"
    if not d.exists():
        raise HTTPException(404, "SEN1-2 not found")
    names = sorted(p.name for p in d.glob("*.png"))[:2000]
    step = max(1, len(names) // max(limit, 1))
    return {"samples": names[::step][:limit], "total": len(names)}


@app.get("/api/color/predict")
def color_predict(name: str, passes: int = 10):
    """Colorize + Monte-Carlo dropout confidence.

    Dropout is left ON for `passes` forward runs. Where the passes agree, the model is
    reading real evidence out of the backscatter; where they diverge it is guessing.
    """
    t0 = time.time()
    s1p = Path(SEN12_DIR) / "s1" / name
    s2p = Path(SEN12_DIR) / "s2" / name.replace("_s1_", "_s2_")
    if not s1p.exists():
        raise HTTPException(404, f"unknown tile {name}")

    model = load_color()
    if model is None:
        raise HTTPException(503, "colorization model still training")

    sar = np.asarray(Image.open(s1p).convert("L"), dtype=np.float32)
    x = torch.from_numpy(sar / 127.5 - 1.0)[None, None].to(DEV)

    # Use the SINGLE tested implementation rather than re-deriving it here. The
    # duplicate that used to live in this file matched only nn.Dropout, missed
    # nn.Dropout2d (which ResUNet uses), and therefore returned confidence 1.0
    # everywhere - a perfect-looking map carrying no information at all.
    from models import mc_colorize
    mean_b, conf_b, std_b = mc_colorize(model, x, n=passes)
    mean = mean_b[0]
    conf = conf_b[0, 0]

    rgb = ((mean.permute(1, 2, 0).cpu().numpy() + 1) * 127.5)
    out = {
        "name": name,
        "sar": png_b64(sar.astype(np.uint8)),
        "color": png_b64(rgb),
        "confidence": png_b64((conf.cpu().numpy() * 255).astype(np.uint8)),
        "passes": passes,
        "ms": round((time.time() - t0) * 1000),
        "mean_confidence": float(conf.mean()),
    }
    if s2p.exists():
        out["truth"] = png_b64(np.asarray(Image.open(s2p).convert("RGB")))
    return out


@app.get("/api/scene/cover")
def scene_cover(name: str):
    """Surface-cover fractions for a benchmark scene.

    Measured from the co-registered Sentinel-2 optical chip, NOT from the radar - see
    chromasar/landcover.py for the held-out numbers that ruled SAR out for this job.
    Built-up is deliberately absent.
    """
    from landcover import cover_from_s2
    s2 = Path(FLOODS_DIR) / "S2Hand" / f"{name}_S2Hand.tif"
    if not s2.exists():
        raise HTTPException(404, f"no optical counterpart for {name}; surface cover "
                                 f"is measured from Sentinel-2, not from the radar")
    lbp = Path(FLOODS_DIR) / "LabelHand" / f"{name}_LabelHand.tif"
    lab = tifffile.imread(lbp).astype(np.int16) if lbp.exists() else None
    out = cover_from_s2(tifffile.imread(s2), lab)
    g = scene_geo(name)
    out["scene"] = name
    out["place"] = g.label if g else None
    out["country"] = g.country if g else None
    out["continent"] = g.continent if g else None
    out["coords"] = g.dms if g else None
    return out


@app.post("/api/flood/upload")
async def flood_upload(file: UploadFile = File(...)):
    """Flood detection from a user-supplied SAR file, and NOTHING else.

    Everything returned here is derived from the uploaded image alone: no labels, no
    permanent-water reference, no ground truth. Accuracy metrics are therefore
    unavailable by construction and the UI shows n/a rather than borrowing numbers from
    a benchmark scene the user did not supply.
    """
    import tifffile
    from geo import read_geotiff_geo
    raw = await file.read()
    t0 = time.time()
    try:
        arr = tifffile.imread(io.BytesIO(raw)).astype(np.float32)
    except Exception:                                            # noqa: BLE001
        # The raw tifffile error is a header hexdump, which tells a user nothing. The
        # common mistake is dropping a screenshot or a JPEG of a SAR image; say why
        # that cannot work rather than printing bytes at them.
        raise HTTPException(
            400,
            "This is not a GeoTIFF. Flood detection needs the original 2-band "
            "Sentinel-1 GRD file (VV and VH, in decibels) - a PNG, JPEG or screenshot "
            "has already been stretched to 8-bit and thrown away the calibrated "
            "backscatter the model reads. Download the .tif from Copernicus Browser or "
            "ASF Vertex and upload that.")

    # An upload may carry no georeferencing at all. That has to degrade to "unknown
    # location" - never to a fabricated coordinate.
    try:
        up_geo = read_geotiff_geo(io.BytesIO(raw))
    except Exception:                                            # noqa: BLE001
        up_geo = None

    # accept [2,H,W] or [H,W,2]; a single band cannot drive the dual-pol model
    if arr.ndim == 3 and arr.shape[-1] in (2, 3) and arr.shape[0] > 4:
        arr = np.moveaxis(arr, -1, 0)
    if arr.ndim != 3 or arr.shape[0] < 2:
        raise HTTPException(
            400, f"expected a 2-band Sentinel-1 GeoTIFF (VV, VH) in dB, got shape "
                 f"{list(arr.shape)}. Single-band or 8-bit screenshots cannot be used: "
                 f"the model needs both polarisations in decibels.")
    sar = arr[:2]
    if np.nanmax(sar) > 60 or np.nanmin(sar) < -80:
        raise HTTPException(
            400, f"values look like raw DN, not decibels (range "
                 f"{float(np.nanmin(sar)):.1f}..{float(np.nanmax(sar)):.1f}). "
                 f"Convert to dB before uploading.")

    model = load_flood()
    if model is None:
        raise HTTPException(503, "flood model not available")
    x = np.clip(np.nan_to_num(sar, nan=-30.0), -30.0, 0.0)
    x = (x + 30.0) / 30.0 * 2.0 - 1.0
    with torch.no_grad():
        prob = torch.sigmoid(
            model(torch.from_numpy(x)[None].to(DEV)) / TEMPERATURE)[0, 0].cpu().numpy()

    # same correction for uploads; an ungeoreferenced upload falls back to the
    # nominal 10 m pixel and says so via place=None rather than inventing a location
    px_km2 = (up_geo.pixel_m2 / 1e6) if up_geo else (10.0 ** 2) / 1e6
    water_km2 = float((prob > 0.5).sum()) * px_km2
    scene_km2 = float(prob.size) * px_km2
    low_conf = float(((prob > 0.25) & (prob < 0.75)).mean())
    pct = 100 * water_km2 / max(scene_km2, 1e-9)
    sev = ("negligible" if pct < 1 else "localised" if pct < 5
           else "significant" if pct < 20 else "severe")
    narrative = [
        f"Uploaded scene {file.filename}: {prob.shape[1]}x{prob.shape[0]} px, "
        + (f"{scene_km2:.1f} km2 at {up_geo.pixel_ew_m:.1f}x{up_geo.pixel_ns_m:.1f} m "
           f"ground sampling, centred {up_geo.dms} ({up_geo.label})."
           if up_geo else
           f"{scene_km2:.1f} km2 assuming 10 m sampling. The file carries no "
           f"georeferencing, so its location is unknown and the area is nominal."),
        f"Surface water detected over {water_km2:.2f} km2 ({pct:.1f}% of the scene) "
        f"at a decision threshold of 0.50 - classified {sev}.",
        f"{100*low_conf:.1f}% of pixels fall in the low-confidence band (0.25-0.75).",
        "No hand labels or permanent-water reference exist for an uploaded scene, so "
        "accuracy metrics and flood-versus-permanent separation are not reported. "
        "Every number above derives from your SAR file alone.",
    ]
    return {
        "name": file.filename,
        "sar_vv": png_b64(db_to_grey(sar[0])),
        "sar_vh": png_b64(db_to_grey(sar[1], -32, -5)),
        "prob": png_b64((prob * 255).astype(np.uint8)),
        "size": list(prob.shape),
        "ms": round((time.time() - t0) * 1000),
        "narrative": narrative,
        "severity": sev,
        "water_km2": round(water_km2, 3),
        "uncertain_fraction": round(low_conf, 4),
        "place": up_geo.label if up_geo else None,
        "country": up_geo.country if up_geo else None,
        "continent": up_geo.continent if up_geo else None,
        "coords": up_geo.dms if up_geo else None,
        "pixel_m2": round(up_geo.pixel_m2, 2) if up_geo else None,
    }


@app.post("/api/color/upload")
async def color_upload(file: UploadFile = File(...), passes: int = 10):
    """Colorize a user-supplied SAR image. Derived from the upload alone.

    Accepts a single-band SAR GeoTIFF or an 8-bit grayscale PNG/JPEG, because the
    colorization generator takes one channel. No ground truth exists for an upload, so
    PSNR is not reported - only the output and its confidence map.
    """
    raw = await file.read()
    t0 = time.time()
    arr = None
    try:
        import tifffile
        arr = tifffile.imread(io.BytesIO(raw)).astype(np.float32)
    except Exception:                                            # noqa: BLE001
        try:
            arr = np.asarray(Image.open(io.BytesIO(raw)).convert("L"), dtype=np.float32)
        except Exception as e:                                   # noqa: BLE001
            raise HTTPException(400, f"could not read as TIFF or image: {e}")

    if arr.ndim == 3:
        arr = arr[0] if arr.shape[0] <= 4 else arr[..., 0]

    # dB-scaled SAR -> [-1,1]; 8-bit grayscale -> [-1,1]
    if float(np.nanmin(arr)) < -1.5:
        x = (np.clip(np.nan_to_num(arr, nan=-30.0), -30.0, 0.0) + 30.0) / 30.0 * 2 - 1
        src = "dB SAR"
    else:
        x = np.nan_to_num(arr, nan=0.0) / 127.5 - 1.0
        src = "8-bit grayscale"

    model = load_color()
    if model is None:
        raise HTTPException(503, "colorization model not available")

    from models import mc_colorize
    t = torch.from_numpy(x.astype(np.float32))[None, None].to(DEV)
    mean_b, conf_b, _ = mc_colorize(model, t, n=max(2, min(passes, 24)))
    mean, conf = mean_b[0], conf_b[0, 0]
    rgb = (mean.permute(1, 2, 0).cpu().numpy() + 1) * 127.5
    return {
        "name": file.filename,
        "source": src,
        "sar": png_b64(((x + 1) * 127.5).astype(np.uint8)),
        "color": png_b64(rgb),
        "confidence": png_b64((conf.cpu().numpy() * 255).astype(np.uint8)),
        "passes": max(2, min(passes, 24)),
        "ms": round((time.time() - t0) * 1000),
        "mean_confidence": float(conf.mean()),
        "note": "No optical ground truth exists for an uploaded scene, so PSNR is not "
                "reported. Output and confidence derive from your SAR image alone.",
    }


@app.post("/api/change")
async def change_detect(before: UploadFile = File(...), after: UploadFile = File(...),
                        thr_db: float = 3.0, water_thr: float = 0.5):
    """Bi-temporal change between two SAR acquisitions of the same area.

    Two products, both computed from the uploaded pair alone:

    1. BACKSCATTER CHANGE. SAR is already logarithmic, so the classic log-ratio
       reduces to a plain difference in dB. Darkening (negative) usually means a
       surface became smooth - new water, or a harvested field. Brightening usually
       means new roughness or double-bounce - construction, or flooded vegetation.

    2. NEW WATER. The flood model runs on BOTH dates and the masks are differenced.
       This is the operational answer: not "where is water" but "where is water now
       that was not water before".
    """
    import tifffile

    def read(u_bytes, label):
        try:
            arr = tifffile.imread(io.BytesIO(u_bytes)).astype(np.float32)
        except Exception as e:                                   # noqa: BLE001
            raise HTTPException(400, f"{label}: not a readable TIFF ({e})")
        if arr.ndim == 3 and arr.shape[-1] in (2, 3) and arr.shape[0] > 4:
            arr = np.moveaxis(arr, -1, 0)
        if arr.ndim != 3 or arr.shape[0] < 2:
            raise HTTPException(400, f"{label}: expected 2-band SAR (VV, VH) in dB, "
                                     f"got shape {list(arr.shape)}")
        if np.nanmax(arr) > 60 or np.nanmin(arr) < -80:
            raise HTTPException(400, f"{label}: values look like raw DN, not dB")
        return arr[:2]

    t0 = time.time()
    before_raw, after_raw = await before.read(), await after.read()
    b = read(before_raw, "before")
    a = read(after_raw, "after")
    if b.shape != a.shape:
        raise HTTPException(400, f"scenes must be the same size and footprint: "
                                 f"before {list(b.shape)} vs after {list(a.shape)}")

    model = load_flood()
    if model is None:
        raise HTTPException(503, "flood model not available")

    def water(sar):
        x = np.clip(np.nan_to_num(sar, nan=-30.0), -30.0, 0.0)
        x = (x + 30.0) / 30.0 * 2.0 - 1.0
        with torch.no_grad():
            return torch.sigmoid(
                model(torch.from_numpy(x)[None].to(DEV)) / TEMPERATURE)[0, 0].cpu().numpy()

    pb, pa = water(b), water(a)
    wb, wa = pb > water_thr, pa > water_thr
    new_water = wa & ~wb
    gone_water = wb & ~wa

    # dB difference on VV; SAR is logarithmic already, so this IS the log-ratio
    diff = np.nan_to_num(a[0], nan=-30.0) - np.nan_to_num(b[0], nan=-30.0)
    darker = diff < -thr_db
    brighter = diff > thr_db

    # Same correction as the flood endpoints, which this one was missing: the rasters
    # are in a geographic CRS, so a flat 100 m^2 per pixel overstated area by 11.9% at
    # India's latitude. Left unfixed, the flood tab and the change tab reported
    # different areas for the SAME footprint.
    from geo import read_geotiff_geo
    try:
        ch_geo = read_geotiff_geo(io.BytesIO(after_raw), shape=diff.shape)
    except Exception:                                            # noqa: BLE001
        ch_geo = None
    px_km2 = (ch_geo.pixel_m2 / 1e6) if ch_geo else (10.0 ** 2) / 1e6
    scene_km2 = float(diff.size) * px_km2

    def pct(mask):
        return round(100.0 * float(mask.sum()) / max(diff.size, 1), 2)

    stats = {
        "scene_km2": round(scene_km2, 3),
        "place": ch_geo.label if ch_geo else None,
        "coords": ch_geo.dms if ch_geo else None,
        "pixel_m2": round(ch_geo.pixel_m2, 2) if ch_geo else None,
        # percentages of the scene, which is what a reader actually wants to compare
        # across two dates. These are SAR-derived WATER only - vegetation and bare
        # ground need the optical instrument, see /api/scene/cover.
        "water_before_pct": pct(wb),
        "water_after_pct": pct(wa),
        "new_water_pct": pct(new_water),
        "darkened_pct": pct(darker),
        "brightened_pct": pct(brighter),
        "water_before_km2": round(float(wb.sum()) * px_km2, 3),
        "water_after_km2": round(float(wa.sum()) * px_km2, 3),
        "new_water_km2": round(float(new_water.sum()) * px_km2, 3),
        "receded_water_km2": round(float(gone_water.sum()) * px_km2, 3),
        "darkened_km2": round(float(darker.sum()) * px_km2, 3),
        "brightened_km2": round(float(brighter.sum()) * px_km2, 3),
        "mean_db_shift": round(float(np.nanmean(diff)), 3),
        "threshold_db": thr_db,
    }
    net = stats["new_water_km2"] - stats["receded_water_km2"]
    stats["net_water_change_km2"] = round(net, 3)

    # signed change map: blue = new water, amber = receded, grey = unchanged
    h, w = diff.shape
    rgb = np.full((h, w, 3), 16, np.uint8)
    mag = np.clip(np.abs(diff) / 12.0, 0, 1)
    rgb[..., 0] = (18 + 60 * mag).astype(np.uint8)
    rgb[..., 1] = (24 + 60 * mag).astype(np.uint8)
    rgb[..., 2] = (32 + 60 * mag).astype(np.uint8)
    rgb[new_water] = (61, 200, 255)
    rgb[gone_water] = (255, 160, 66)

    narrative = [
        f"Comparing {before.filename} (before) with {after.filename} (after) over "
        f"{stats['scene_km2']:.1f} km2.",
        f"Water extent moved from {stats['water_before_km2']:.2f} km2 to "
        f"{stats['water_after_km2']:.2f} km2.",
        f"NEW water covers {stats['new_water_km2']:.2f} km2; "
        f"{stats['receded_water_km2']:.2f} km2 has receded - "
        f"a net change of {net:+.2f} km2.",
        f"Backscatter darkened by more than {thr_db:.0f} dB over "
        f"{stats['darkened_km2']:.2f} km2 (smoother surface, typically new water) and "
        f"brightened over {stats['brightened_km2']:.2f} km2 (rougher surface or "
        f"double-bounce, typically construction or flooded vegetation).",
        "Both dates are scored by the same calibrated model, so the difference "
        "reflects the ground rather than a change of method. No labels are used.",
    ]
    return {
        "before_vv": png_b64(db_to_grey(b[0])),
        "after_vv": png_b64(db_to_grey(a[0])),
        "change": png_b64(rgb),
        "water_before": png_b64((pb * 255).astype(np.uint8)),
        "water_after": png_b64((pa * 255).astype(np.uint8)),
        "stats": stats,
        "narrative": narrative,
        "size": [int(w), int(h)],
        "ms": round((time.time() - t0) * 1000),
    }


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


if __name__ == "__main__":
    import uvicorn
    print(f"device={DEV}  flood_model={FLOOD_CKPT.exists()}  "
          f"color_model={COLOR_CKPT.exists()}")
    uvicorn.run(app, host="127.0.0.1", port=8000)
