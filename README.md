# ChromaSAR

**SAR image colorization with a calibrated confidence for every pixel.**

Smart India Hackathon 2026 - problem statement **SIH1733** (ISRO). Team **Delta Force**,
Mahindra University.

---

## The problem

Radar satellites fire pulses at the ground and measure the echo, so they work at night and
see straight through cloud - the only sensor that keeps working through the Indian monsoon,
which is exactly when you most need to know where the water is. But the output is a
grayscale map of surface texture, not a photograph. Reading it takes years of training, so
the data reaches only a few specialists.

## What this does

Colorizes Sentinel-1 SAR into optical-like imagery using a conditional GAN trained on
10,000 co-registered SAR-optical pairs.

**Radar does not measure colour.** Nothing in the echo says a roof is red. So part of the
output is genuine inference from texture and polarisation, and part is the model guessing
from learned priors. For someone deciding where to send rescue boats, a confidently wrong
map is worse than no map.

So every output carries a **per-pixel confidence map, and that map gates everything
downstream**. Below your threshold the system returns neutral grey - "insufficient
evidence" - instead of a confident guess. Flood extent, change detection and surface cover
are all filtered by it.

## Measured results

Public benchmarks, official splits, nothing aspirational.

| | Result | Source |
|---|---|---|
| Flood, physics threshold | IoU 0.550 | Sen1Floods11 official test split |
| Flood, learned U-Net | **IoU 0.681** | same split |
| Probability calibration | ECE 0.029 -> **0.016**, IoU unchanged | temperature scaling |
| Colorization sharpness | 0.21 -> **0.78** of real optical | gradient-difference loss |
| Colorization saturation | 45% -> **102%** of real | 24 held-out tiles |
| Scene geolocation | **446 / 446** to country + continent | GeoTIFF tiepoints, offline |
| Upload == benchmark | matches to **0.00%** | India, Spain, Somalia |

Inference is ~1.1 s per flood scene on a laptop CPU, in-process. **No network call at
inference** - nothing leaves the machine.

## Two things we are careful about

**Why existing models look unsatisfactory.** They train on L1, whose optimum is the
conditional *mean* of every plausible colour - blur by definition - and PSNR rewards the
same thing, so standard evaluation cannot see the defect. Adding a gradient-difference
loss fixed it, measured with a sharpness metric PSNR is structurally blind to.

**What we refuse to ship.** Land cover from radar alone does not work: built-up scores
AUC 0.483 against bare soil, below chance. We measured it and removed it. Surface cover is
read from the co-registered Sentinel-2 optical instead, and labelled as such on screen.

## Running it

Needs Python 3.9+ and Node 20+.

```bash
python -m pip install -r chromasar/requirements.txt
```

```bash
cd frontend && npm install
```

The trained weights are **not in this repo**. They are 93.5 MB each and the benchmark
imagery is another 3.2 GB, which is past what git will carry, so they are published as
release assets instead and land under `SIH_DATA` (default `~/sih-data`):

```bash
python migrate.py fetch
```

That pulls both checkpoints and both datasets from the `demo-assets-v1` release and
extracts them into the right layout. It is idempotent - re-run it and it skips whatever
is already in place. (Needs `gh auth login` while the repo is private.)

```bash
python migrate.py check
```

That verifies the environment, the data, and the ports before you trust it - every line
must read PASS. Then:

```bash
python webapp/server.py
```

```bash
cd frontend && npm run dev
```

Workspaces at `/flood`, `/change`, `/color`, `/method`.

## Layout

| Path | What |
|---|---|
| `chromasar/` | models, training, evaluation, geolocation, land cover |
| `webapp/` | FastAPI inference backend |
| `frontend/` | Next.js 15 UI |
| `tests/` | 43 regression tests, each guarding a bug we actually hit |
| `deck/` | presentation generation |
| `migrate.py` | move to another laptop, and verify it will run |
| `TEAM_NOTES.md` | the full briefing: results, assumptions, Q&A |

## Data

Not redistributed here. Both are public:

- **Sen1Floods11** - Bonafilia et al., CVPRW 2020. 446 hand-labelled flood chips.
- **SEN1-2** - Schmitt et al., ISPRS 2018. 10,000 co-registered SAR-optical pairs.

See `chromasar/DATASETS.md` for acquisition.

## Acknowledgements

Built on pix2pix (Isola et al., CVPR 2017) as a deliberate baseline. The
gradient-difference loss is from Mathieu et al., ICLR 2016; MC-dropout uncertainty from
Gal & Ghahramani, ICML 2016; temperature scaling from Guo et al., ICML 2017.
