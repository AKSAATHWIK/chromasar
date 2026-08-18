# -*- coding: utf-8 -*-
"""ChromaSAR deck content (SIH1733).

Rewritten after the build started producing real numbers. Two rules applied:

1. NOTHING is claimed that the code does not do. Earlier drafts promised a
   Swin-Transformer generator, VGG-perceptual loss and land-cover conditioning.
   Only the perceptual loss exists today, so the rest moved to a clearly-labelled
   roadmap. A judge who asks "show me" must always get a yes.
2. Measured results lead. This is an idea-stage submission where most teams present
   concepts; we present a working system with numbers on public benchmarks.
"""

TEAM = "DELTA FORCE"
TEAM_ID = "(to be filled after portal registration)"

PS_ID = "SIH1733"
PS_TITLE = ("SAR Image Colorization for Comprehensive Insight using "
            "Deep Learning Model")
THEME = "Space Technology"
CATEGORY = "Software"
ORG = "Indian Space Research Organisation (ISRO)"

IDEA_TITLE = "ChromaSAR — Reading SAR Like a Photograph, and Knowing When Not To"

PAL = dict(primary="0B3C5D", accent="C25E00", card="EAF1F6",
           cardline="C7D8E4", body="1F2A44", muted="4A5A68",
           card2="FBF0E6", card2line="EAD3BB", good="1F7A6C")

# ---------------------------------------------------------------- slide 2
S2_LEFT = [
    ("The problem in one line:",
     " SAR is the only sensor that sees through cloud, smoke and darkness — and almost "
     "nobody can read it. Optical imagery is instantly readable and blocked by cloud for "
     "months of the Indian monsoon."),
    ("What we build:",
     " a deep-learning system that turns grayscale SAR into optical-like colour imagery, "
     "so any GIS user reads terrain directly instead of decoding radar backscatter."),
    ("The catch nobody addresses:",
     " radar does not measure colour. Some output is real inference from texture and "
     "polarisation; some is the model guessing from learned priors. A confidently wrong "
     "flood map is worse than no map."),
    ("Our USP:",
     " every pixel carries a CALIBRATED CONFIDENCE, and that map GATES what the system "
     "is willing to report. Below threshold it says “insufficient evidence” instead of "
     "a silent wrong answer — and where we measured that a capability does not work, we "
     "removed it rather than shipping it."),
]

S2_RIGHT_HDR = "ALREADY BUILT AND MEASURED"
S2_RIGHT = [
    ("Flood mapping from SAR — working",
     "IoU 0.681 on the Sen1Floods11 official test split, against 0.550 for the "
     "physics baseline. Probabilities calibrated: ECE 0.029 to 0.016."),
    ("Training data — verified",
     "10,000 SAR\u2013optical pairs and 446 hand-labelled flood chips. "
     "0 corrupt, 0 unmatched, 0 duplicate."),
    ("Colorization — retrained to remove blur",
     "Sharpness 0.21 \u2192 0.78 of the real optical; saturation 45% \u2192 102%. "
     "We changed the loss, not the network."),
    ("Uncertainty — calibrated, not guessed",
     "Per-pixel confidence from a 10-pass MC-dropout ensemble. The scale is the p99 of "
     "the measured spread over 2.62M pixels."),
    ("Every scene located — exactly",
     "Country, continent and coordinates from the file's own georeferencing. "
     "446/446 scenes resolved, offline."),
]

# ---------------------------------------------------------------- slide 3
S3_LEFT_HDR = "TECHNOLOGIES TO BE USED"
S3_LEFT = [
    ("Core:", " Python, PyTorch, ONNX Runtime, Modal (GPU)"),
    ("Colorization:", " conditional GAN — U-Net / ResNet34 generator (ImageNet encoder) "
     "+ PatchGAN discriminator"),
    ("Losses:", " L1 + adversarial + frozen-VGG16 perceptual + GRADIENT-DIFFERENCE"),
    ("Uncertainty:", " Monte-Carlo dropout ensemble → per-pixel confidence"),
    ("Flood module:", " dual-polarisation threshold + ResNet34-UNet segmentation"),
    ("Geospatial:", " ESA SNAP, GDAL / Rasterio, QGIS plugin, tifffile; true ground area from the raster’s own georeferencing"),
    ("Serving:", " FastAPI + Next.js 15, runs CPU-only on a laptop — no GPU, "
     "no network and no cloud call at inference; the demo cannot be broken by "
     "venue wifi"),
    ("Geolocation:", " GeoTIFF tiepoint → WGS84 lat/lon → offline country and "
     "continent lookup; resolves 446/446 benchmark scenes"),
]
S3_RIGHT_HDR = "METHODOLOGY & IMPLEMENTATION PROCESS"
S3_RIGHT = [
    ("1  Data", "SEN1-2 and SEN12MS paired patches; every file decoded and verified; "
     "defective scenes excluded by an automated quality check."),
    ("2  Train", "Conditional generator, composite loss. Train/validation split is by "
     "SCENE, not by patch — adjacent tiles of one place on both sides would inflate "
     "the score."),
    ("3  Quantify", "MC-dropout ensemble; per-pixel spread becomes the confidence map, "
     "with a refuse-to-colorize threshold."),
    ("4  Evaluate", "PSNR, SSIM, LPIPS against ground truth, reported per land-cover "
     "class, plus a calibration curve proving confidence predicts error."),
    ("5  Apply", "Confidence-gated flood mapping, change detection and per-scene surface-cover breakdown; alerts qualified "
     "by trust, never issued from a low-confidence region."),
]

# ---------------------------------------------------------------- slide 4
S4_CARDS = [
    ("PROVEN — NOT ASSUMED", "card", [
        "10,000 verified SAR\u2013optical pairs. 0 corrupt, 0 unmatched, 0 duplicate.",
        "Beats its physics baseline on a public benchmark, official split.",
        "Your upload scores identically to our benchmark \u2014 0.00% difference, "
        "three scenes. 43 regression tests.",
        "We found and fixed a bug in our own headline number: flood area read "
        "11.9% high for India, 14.6% for Pakistan.",
    ]),
    ("CHALLENGES & RISKS", "card2", [
        "Hallucination \u2014 the network invents colour the radar never carried.",
        "PSNR rewards blur. “It looks right” is not a metric.",
        "Flooded vegetation returns BRIGHT, not dark - the threshold misses it.",
        "Land cover from radar alone does NOT work: built-up scores AUC 0.483, below chance."
        "the quantity being reported.",
    ]),
    ("HOW WE HANDLE THEM", "card", [
        "Ship the confidence map and refuse below threshold. Hallucination is "
        "surfaced, never hidden \u2014 the differentiator.",
        "A gradient-energy metric that PSNR cannot see \u2014 it caught the blur.",
        "Learned segmentation where physics fails: IoU 0.550 to 0.681, calibrated."
        "(ECE 0.029 → 0.016).",
        "We measured it and REFUSED to ship it. Cover comes from Sentinel-2 optical "
        "instead; built-up is marked unavailable, on screen.",
    ]),
]

# ---------------------------------------------------------------- slide 5
S5_STATS = [
    ("0.681", "IoU flood detection on the Sen1Floods11 public benchmark, official split — calibrated, ECE 0.016"),
    ("24 × 7", "Usable through cloud, monsoon and night — when optical satellites are blind"),
    ("Per-pixel", "Confidence on every output; low-trust regions never raise an alert, and classes we cannot score are not reported"),
]
S5_LEFT_HDR = "POTENTIAL IMPACT ON THE TARGET AUDIENCE"
S5_LEFT = [
    ("Disaster response:",
     " flood extent mapped during the monsoon, exactly when optical is blind."),
    ("Remote-sensing analysts:",
     " the PS's stated users. Interpretation drops from expert-only to any GIS user."),
    ("Defence and border surveillance:",
     " night-time, all-weather scene understanding for non-specialists."),
    ("Geology and environment:",
     " the PS's named use cases - lithology, wetlands, glacier retreat."),
]

S5_RIGHT_HDR = "BENEFITS (SOCIAL, ECONOMIC, STRATEGIC, ENVIRONMENTAL)"
S5_RIGHT = [
    ("Social:", " faster, better-informed disaster response in the months India is most "
     "vulnerable and least visible from optical orbit."),
    ("Economic:", " removes dependence on cloud-free optical tasking and commercial "
     "imagery purchase; fully open-source, zero licence cost."),
    ("Strategic:", " indigenous SAR-interpretation capability that scales onto RISAT and "
     "the incoming NISAR data volume."),
    ("Archive unlock:", " decades of existing SAR holdings become visually searchable by "
     "a far larger analyst pool."),
    ("Environmental:", " continuous all-weather monitoring of glaciers, wetlands, "
     "coastlines and forest cover."),
]

# ---------------------------------------------------------------- slide 6
S6_LEFT_HDR = "RESEARCH & REFERENCES"
S6_LEFT = [
    ("Isola et al., Image-to-Image Translation with Conditional Adversarial Networks "
     "(pix2pix), CVPR 2017", "arxiv.org/abs/1611.07004"),
    ("Wang et al., High-Resolution Image Synthesis with Conditional GANs (pix2pixHD), "
     "CVPR 2018", "arxiv.org/abs/1711.11585"),
    ("Fuentes Reyes et al., SAR-to-Optical Image Translation Based on Conditional GAN, "
     "Remote Sensing 2019", "mdpi.com/2072-4292/11/17/2067"),
    ("Gal & Ghahramani, Dropout as a Bayesian Approximation — the basis of our "
     "confidence map, ICML 2016", "arxiv.org/abs/1506.02142"),
    ("Bonafilia et al., Sen1Floods11 — georeferenced flood dataset for Sentinel-1, "
     "CVPRW 2020", "github.com/cloudtostreet/Sen1Floods11"),
]
S6_RIGHT_HDR = "DATASETS, TOOLS & DATA SOURCES"
S6_RIGHT = [
    ("Schmitt et al., SEN1-2 — 282k SAR–optical pairs; the paper names SAR colorization "
     "as its first application", "arxiv.org/abs/1807.01569"),
    ("Schmitt et al., SEN12MS — VV+VH plus MODIS land cover", "arxiv.org/abs/1906.07789"),
    ("Copernicus Data Space — Sentinel-1 GRD and Sentinel-2 L2A",
     "dataspace.copernicus.eu"),
    ("ISRO Bhoonidhi — Indian EO data portal (RISAT, Resourcesat)",
     "bhoonidhi.nrsc.gov.in"),
    ("ESA SNAP Toolbox — calibration, speckle filtering, terrain correction",
     "step.esa.int/main/toolboxes/snap"),
]

# ---------------------------------------------------------------- speaker notes
NOTES = {
1: """TITLE SLIDE — 20 seconds, do not linger.

Say: "Delta Force, problem statement SIH1733 from ISRO — SAR image colorization."

Then move. The title slide earns nothing; your time budget belongs to slides 2 and 3.

If asked "why this PS?" — because SAR is the only sensor that works through the monsoon,
and it is unreadable to non-specialists. That gap is the whole project.""",

2: """THE IDEA — your most important slide. Aim ~60 seconds.

STRUCTURE: problem, solution, the catch, our answer.

Say roughly: "SAR sees through cloud and darkness — it is the only thing that works
during the monsoon. But it is a grayscale map of surface texture, and reading it takes
years of training. We colorize it so any GIS user can read it directly.

Here is what nobody else addresses: radar does not measure colour. So part of our output
is genuine inference from texture and polarisation, and part is the model guessing. We
make the model tell you which is which — a per-pixel confidence map that gates every
downstream decision."

THEN POINT AT THE RIGHT PANEL. This is the credibility moment. Most teams at this stage
present concepts. Say: "This is not a proposal — the flood module already runs at IoU
0.681 on a public benchmark, the probabilities are calibrated, and every upload is
verified to give the same answer as the benchmark path to 0.00%."

THE PS SAYS existing DL models are "not satisfactory" WITHOUT SAYING WHY. That gap is the
whole opening: "They are unsatisfactory because they train on L1, and L1's optimum is the
conditional mean of every plausible colour - which is blur by definition. PSNR rewards the
same thing, so the standard evaluation cannot even see the defect. We measured it at 0.21
of the real optical's gradient energy, changed the objective, and got 0.78."

ON "NOVEL MODEL": do NOT claim a new architecture - ours is pix2pix-family on purpose, as
the honest baseline. The novelty is the objective and the evaluation: a gradient-difference
loss, calibrated per-pixel uncertainty, confidence-gated analytics, and a sharpness metric
that saw what PSNR could not.

IF THE PANEL IS TECHNICAL, LEAD WITH THE REFUSAL: "We measured whether radar alone can
break a scene into forest, bare ground and built-up. Built-up scored AUC 0.483 - below
chance - so we do not report it, and the app says why on screen. Most demos will show you
five confident percentages nobody validated."

SECOND STRONGEST: the colorization retrain. "Our first colouriser was five times smoother
than reality. The cause was the loss, not the network - L1's optimum is the conditional
mean of every plausible colour, which is blur by definition. We added a gradient loss,
raised the adversarial weight, and gradient energy went 0.21 to 0.78 of ground truth.
PSNR fell, and that is the expected signature of removing blur."

IF ASKED "WHY A FLOOD DETECTOR IN A COLORIZATION PS?": colorization is the METHOD the PS
asks for; usability is its stated GOAL. Flood mapping is how we prove usability improved -
and it is the only half with hard ground truth (446 hand-labelled masks, public split), so
it is what keeps the project honest. A confidence map also needs a consumer: flood mapping
is what turns "here is an uncertainty map" into "low-trust regions never raise an alert."

ANTICIPATE: "Isn't colorization just cosmetic?" Answer: no — it converts an image only
specialists can use into one any responder can use, and the PS itself names analyst
usability as the goal.""",

3: """TECHNICAL APPROACH — ~60 seconds. Let the diagram do the work.

THE ONE THING TO CONVEY: uncertainty is not a feature sitting beside the others, it is a
GATE. Trace the orange arrow with your finger: confidence flows into the gate, and every
analytic below passes through it.

Say: "SAR goes into a conditional GAN. Two things come out — the colorized scene, and a
confidence map from a Monte-Carlo dropout ensemble. Everything downstream is filtered by
that confidence, so a low-trust region produces 'insufficient evidence' rather than a
silent wrong answer."

KNOW THESE, they will be asked:
 - Why a GAN and not plain L1? L1 rewards hedging — an unsure model outputs muddy
   average colour. The discriminator forces a committed, sharp answer.
 - What is MC-dropout? Keep dropout ON at inference, run the model ten times. Where the
   runs agree the model is reading real evidence; where they diverge it is guessing.
 - Why split by scene and not randomly? Patches from one scene are adjacent tiles of the
   same place. A random split puts near-identical imagery on both sides and the
   validation score becomes meaningless. Ours is lower and real.

HONESTY LINE if pushed on architecture: the Swin-Transformer generator and land-cover
conditioning are the next steps, not today's build. Say so. Never claim a component we
have not run.""",

4: """FEASIBILITY — ~45 seconds. The left card is your weapon.

Say: "Feasibility is not a projection for us — the data is downloaded and verified, and
the flood module already beats its baseline."

THE RISK CARD IS A STRENGTH, NOT A WEAKNESS. Teams that list no risks look naive.
Deliver the flooded-vegetation point deliberately:

"Our threshold assumes water is dark, because water reflects radar away. But floodwater
under trees produces a double bounce off the trunks and comes back BRIGHT. So the
threshold misses it — and worse, it confidently reports no water across a fully flooded
scene. We measured that. It is why we trained a segmentation network, and why the
confidence gate exists."

That single answer shows you understand the physics, that you tested honestly, and that
your architecture responds to a real failure. It is the strongest thirty seconds
available to you.

IF ASKED "what is your biggest risk?" — hallucination, and say it plainly. Then: which
is exactly why we built the confidence map first rather than last.""",

5: """IMPACT — ~40 seconds. Lead with the number, land on the monsoon.

Say: "0.681 IoU on a public flood benchmark, official test split — not a number we chose
for ourselves, and the probabilities are calibrated so 0.7 means 0.7."

THE LINE THAT MATTERS: "During the Indian monsoon, optical satellites see cloud. SAR
sees the ground. Right now that data reaches only the small number of analysts trained
to read radar. We widen that to every GIS user in every state disaster management
authority."

Name real events if the room is receptive — Kerala 2018, Assam floods, Sikkim 2023 GLOF.
Concrete beats abstract.

DO NOT oversell economics. You have no cost model. Stick to: open-source, no licence
cost, no dependence on commercial cloud-free tasking.""",

6: """REFERENCES — 10 seconds. Do not read them aloud.

Say: "Sources are listed; the datasets are public and the splits are the published ones,
so our numbers are reproducible."

THE POINT of this slide is reproducibility, not literature review. If a judge engages,
the strongest fact is: the SEN1-2 paper names SAR colorization as its first intended
application — we did not pick a dataset at random, we picked the one built for this task.

CLOSING LINE if you get one: "Every number on these slides came from code that runs
today, on public data, with published splits. We would rather show you a smaller true
result than a larger claim."
""",
}
