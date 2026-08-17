# ChromaSAR — Dataset Analysis & Download Plan

**PS:** SIH1733 — SAR Image Colorization for Comprehensive Insight using Deep Learning Model (ISRO)
**Team:** Delta Force

---

## 1. What we need from a dataset

The task is supervised image-to-image translation, so we need **co-registered pairs**: a SAR
patch and the optical image of the exact same ground, taken close enough in time that the
ground hasn't changed.

Requirements, in priority order:

| # | Requirement | Why |
|---|---|---|
| 1 | Co-registered SAR ↔ optical pairs | Without this there is no supervision signal at all |
| 2 | Enough volume (≥ 5k pairs) | GANs overfit badly on small sets |
| 3 | VV **and** VH polarisation | Our deck promises polarimetric encoding (VV, VH, VV/VH ratio) |
| 4 | Land-cover labels | Needed for the terrain-conditioning innovation |
| 5 | Geographic + seasonal diversity | Otherwise the model only works on one biome |

No single dataset wins on all five at a size we can download this week. So we use **two, in
sequence** — that is a deliberate choice, not indecision.

---

## 2. Candidates evaluated

### SEN1-2 — **chosen for the baseline** ✅

Schmitt et al., 2018. 282,384 co-registered patch pairs, 256×256 px at 10 m resolution.

- **SAR:** Sentinel-1, **VV polarisation only**
- **Optical:** Sentinel-2, **RGB only**
- **Format:** PNG (no geospatial preprocessing needed — load and train)
- **Coverage:** 4 seasons, globally distributed scenes
- **Licence:** CC-BY
- **Host:** TUM library, `mediatum.ub.tum.de/1436631`

**Why it wins for week 1:** stored as **individual PNG files in per-scene folders**, not as
one giant archive. That means we can download exactly the number of pairs we want — ~43 KB
per SAR patch, so 10,000 pairs is roughly 2 GB instead of 50 GB. It is also already in the
exact form the model consumes.

**The clinching detail:** the SEN1-2 paper *itself* names **"SAR image colorization"** as its
first exemplary application. This dataset was published for our task. Say this in the pitch —
it shows we chose the dataset deliberately rather than grabbing the first thing on Kaggle.

**Limitation:** VV only, and no land-cover labels. So it cannot support the polarimetric
encoding or the terrain-conditioning we promise in the deck. That is what SEN12MS is for.

### SEN12MS — **chosen for the full conditioned model** ✅ (second, larger download)

Schmitt et al., 2019. 180,662 triplets, 256×256 px at 10 m.

- **SAR:** Sentinel-1 **VV + VH** ← gives us the polarimetric channels
- **Optical:** Sentinel-2, **13 multispectral bands** (we use RGB, rest available)
- **Land cover:** MODIS-derived maps ← gives us the conditioning prior
- **Format:** GeoTIFF, in per-season `.tar.gz` archives

**Actual archive sizes (verified over FTP):**

| Season | `_s1` (SAR) | `_s2` (optical) | `_lc` (land cover) |
|---|---|---|---|
| winter (ROIs2017) | **14.4 GB** | 38.1 GB | 48 MB |
| spring (ROIs1158) | 18.5 GB | 49.3 GB | 64 MB |
| summer (ROIs1868) | 20.7 GB | 53.8 GB | 65 MB |
| fall (ROIs1970) | 28.2 GB | 74.4 GB | 95 MB |

Winter is the smallest full season at ~52 GB for s1+s2+lc. That's an overnight download, not
a week-1 blocker — which is exactly why it is stage 2.

### Rejected

- **SEN12MS-CR** — built for cloud removal, not colorization. Wrong pairing semantics.
- **Raw Copernicus / Bhoonidhi scenes** — the honest "correct" source, but you must do
  calibration, speckle filtering, terrain correction and co-registration yourself in SNAP.
  Multi-day work that produces nothing demoable. This is the right move *after* the internal
  round, to add genuine Indian terrain.
- **QXS-SAROPT** — small and convenient, but non-Sentinel sensors and awkward hosting.

---

## 3. The plan

**Stage 1 — now.** SEN1-2 subset, ~10,000 pairs sampled across all four seasons (~2–3 GB).
Trains the pix2pix baseline. Enough to prove the concept and produce a demo.

**Stage 2 — starts downloading in the background tonight.** SEN12MS winter (s1 + s2 + lc).
Unlocks VV/VH/ratio input and land-cover conditioning — the two things that separate our
model from a stock pix2pix.

**Stage 3 — after 19 Aug, for the national round.** Our own Sentinel-1/2 pairs over Indian
terrain via SNAP, so we can claim genuine Indian agro-climatic coverage rather than a
global average.

---

## 4. Access

The TUM data server blocks scripted HTTP (Anubis bot protection), but **FTP works fine**:

```
SEN1-2   ftp://m1436631:m1436631@dataserv.ub.tum.de/
SEN12MS  ftp://m1474000:m1474000@dataserv.ub.tum.de/
```

Password is the collection ID. `scripts/download_sen12.py` handles stage 1; it is resumable,
verifies that every SAR patch has its matching optical patch, and skips files already present.

**Data lives outside OneDrive** (`%USERPROFILE%\sih-data\`) — putting several GB of training
patches inside the synced Desktop folder would kick off a very unhappy OneDrive upload.

---

## 5. What to analyse once it lands

Worth doing properly — these findings become slide content and shape the loss function.

1. **Backscatter distribution.** Histogram the SAR patches. SAR is heavily right-skewed;
   this determines whether we normalise in dB or linear space, and it visibly changes results.
2. **Class balance across scenes.** How much is water / farmland / urban / forest? Whatever
   dominates is what the model will be good at — and reviewers *will* ask.
3. **Pair quality spot-check.** View ~50 pairs side by side. Some will be misaligned or the
   optical will be cloudy. Estimate what fraction is bad; if it's high we filter.
4. **Colour statistics per season.** Confirms whether season conditioning is worth adding.
5. **Hardest cases.** Find patches where SAR looks nearly uniform but optical is varied —
   these are where hallucination is guaranteed, and therefore where the confidence map has
   to earn its keep. Pull the best examples for the demo.

---

## 6. Citations (already in the deck)

- Schmitt et al., *The SEN1-2 Dataset for Deep Learning in SAR-Optical Data Fusion*, 2018 —
  arxiv.org/abs/1807.01569
- Schmitt et al., *SEN12MS — A Curated Dataset of Georeferenced Multi-Spectral Sentinel-1/2
  Imagery*, 2019 — arxiv.org/abs/1906.07789
- Isola et al., *Image-to-Image Translation with Conditional Adversarial Networks*, 2017 —
  arxiv.org/abs/1611.07004
