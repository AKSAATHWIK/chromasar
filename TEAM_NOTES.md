# Delta Force - Team Briefing

**Internal hackathon: Wed 19 Aug 2026** - SIH portal registration closes **24 Aug**
(no member or topic changes after that date).

Everyone reads **Sections 4, 5 and 10** before the 19th. Section 4 is the 5-minute desk pitch, Section 5 is
the assumptions judges will grade, Section 10 is the Q&A. Twenty minutes? Read Sections 4 and 5.

---

## 1. What we built, in plain language

### ChromaSAR - SIH1733 (ISRO), our primary

**The gap.** Radar satellites fire pulses at the ground and measure the echo. That means
they work at night and see straight through cloud - the only sensor that keeps working
through the Indian monsoon. But the output is a grayscale map of *surface texture*, not a
photograph. Reading it takes years of training, so the data reaches only a few specialists.

**What we do.** Three things on one Sentinel-1 scene:

1. **Flood mapping** - where the water is, in km2 of real ground area
2. **Change detection** - what is water *now* that was not water before
3. **Colorization** - render radar as optical-like imagery any responder can read

**The honest problem.** Radar does not measure colour. Nothing in the echo says a roof is
red. So part of our colour output is genuine inference from texture and polarisation, and
part is the model guessing from learned priors. For someone deciding where to send rescue
boats, a confidently wrong map is worse than no map.

**Our differentiator.** Every output carries a **per-pixel confidence map**, and that map
**gates** everything downstream. Where the model is guessing, the system says
"insufficient evidence" rather than quietly producing a wrong answer. And where we
measured that a whole capability does not work, **we removed it** rather than shipping it
(see Section 6).

### Ship routing - SIH1658 (INCOIS), our backup

Optimal ship routes across the Indian Ocean. The technical core is a **time-dependent
multi-objective shortest path**: the cost of a leg depends on *when* you sail it, because
the forecast changes during the voyage. Ordinary shortest-path cannot express that. CPU
only.

---

## 2. Measured results - nothing here is aspirational

| What | Result | Source |
|---|---|---|
| Flood, physics threshold | IoU **0.550**, P 0.754, R 0.671 | Sen1Floods11 official test split |
| Flood, learned U-Net | IoU **0.681**, P 0.822, R 0.893 | same split, 512 px, ImageNet encoder |
| Probability calibration | ECE 0.029 -> **0.016**, IoU unchanged | temperature scaling, T = 1.3678 |
| Colorization sharpness | **0.21 -> 0.78** of real optical | retrain, Section 6a |
| Colorization saturation | **45% -> 102%** of real | 24 held-out tiles |
| Scene geolocation | **446 / 446** resolved to country + continent | GeoTIFF tiepoints, offline |
| Upload == benchmark | water area matches to **0.00%** | India, Spain, Somalia |
| Training data verified | 10,000 pairs, 0 corrupt / unmatched / duplicate | 164 scenes, 4 seasons |
| Regression tests | **43 passing** | each guards a bug we actually hit |
| Ship routing | naive route **unnavigable**; ours cuts peak risk 0.63 -> 0.38 | synthetic validated field |
| Router speed | 21.3 s -> **12.0 s**, identical output | precomputed geometry |

**Inference:** ~1.1 s per flood scene, ~2.1 s for a 10-pass colorization. Laptop CPU.

---

## 3. Running it, and getting it onto the demo laptop

**The repo is 31 MB. The model is not in it.** Both checkpoints live under `SIH_DATA`,
outside the project, so `git clone` alone gives you a backend that starts, a UI that
renders, a scene list that populates - and a 503 on the first inference click. You do
not find out until someone clicks. Copy the data, or you have no demo.

### One-time setup on the demo laptop - AT HOME, needs internet

Do this days early, not the night before. It downloads ~550 MB.

```bash
git clone <repo-url> SIH
```

```bash
python -m pip install -r chromasar/requirements.txt
```

```bash
cd frontend && npm install
```

Then get the data. **The easy way - straight from GitHub, no USB drive, no second person:**

```bash
gh auth login
```

```bash
python migrate.py fetch
```

That pulls the two checkpoints and both datasets from the `demo-assets-v1` release and
extracts them into `~/sih-data`. Re-run it any time; it skips what is already there. The
repo is private, hence the `gh auth login` first.

**The offline way**, if the college wifi is the only network and you want everything in
hand beforehand - on the **build** laptop, with a USB drive plugged in:

```bash
python migrate.py pack E:\
```

Either route moves ~3.4 GB: the two checkpoints, `sen1floods11/` and `sen1-2/`. Both
deliberately leave behind `sen12ms/` (~50 GB) and `runs/` (~1.6 GB), which are
training-only and the server never reads. With the USB route, copy the folder onto the
demo laptop anywhere you like, then point the app at it:

```bash
setx SIH_DATA "D:\sih-data"
```

Two traps in that one line, both of which have bitten us:
- **Use the real path.** A `SIH_DATA` set to a folder that does not exist is *worse* than
  leaving it unset, because it overrides the working default (`~/sih-data`) and breaks a
  machine that would otherwise have been fine. If you put the data in `C:\Users\<you>\sih-data`,
  skip `setx` entirely - that is already the default.
- **`setx` does not affect the window you type it in.** Open a NEW terminal afterwards.

### Verify - one command, do it before you leave home

```bash
python migrate.py check
```

It checks the Python version, every import, the data root and all four required paths,
`node_modules`, and whether the ports are free. Every line must read PASS. Then **turn the
wifi off** and click through flood -> change -> color -> method including one upload from
`demo-uploads/`. Anything that needs the network fails there instead of at the desk.

### Running it - at the venue, offline

```bash
python webapp/server.py
```

```bash
cd frontend && npm run dev
```

Landing page at `/`, workspaces at `/flood`, `/change`, `/color`, `/method`.

The backend now **refuses to start** if the checkpoints are missing, and prints which
files it wanted and which folder it looked in. If you see that, `SIH_DATA` is wrong.

If port 8000 is taken (it is a common default - Docker, other dev servers), set
`CHROMASAR_PORT` and put the same value in `frontend/.env.local`, because the Next proxy
in `next.config.mjs` has to point at the same port or every request 404s at the proxy.

Data lives **outside** OneDrive deliberately - several GB inside a synced folder triggers
an enormous upload.

---

## 4. The 5-minute desk pitch - judges walk to you

**Format confirmed by Prof. Raghu:** no formal 10-minute talk. Judges move desk to desk.
You get **5 minutes**, graded on four things. A completed PPT template is uploaded at the
END of the hackathon - it is a submission artefact, not a presentation. Do not read slides
at a judge standing at your desk; **run the app**.

Most teams will not have a working prototype. You do. Lead with it.

### The USP - one line, then prove it in four seconds

> **"Every pixel carries a calibrated confidence, and it gates what the system is willing
> to report. Where we measured that something does not work, we removed it."**

Say that, then show it: work the confidence slider in `/color` from 0 to 0.8 and let them
watch the image go grey. The claim proves itself faster than you can explain it.

**Why that is a USP and not a feature.** Every other team will demo a model that produces
output. The distinguishing move is a model that *declines* to. Radar carries no colour, so
any colorization is partly real inference and partly the model guessing from priors.
Everyone else shows you the guess with no way to tell which is which. We show which is
which, and we refuse below a threshold the user sets. That is the difference between a
pretty picture and decision support - for someone routing rescue boats, a confidently
wrong map is worse than no map.

**For a technical panel, go one level deeper.** The PS says existing models are "not
satisfactory" and does not say why. That is the actual gap:

> Existing models are unsatisfactory because they train on L1, and L1's optimum is the
> conditional mean of every plausible colour - blur by definition. PSNR rewards the same
> thing, so standard evaluation cannot even see the defect. We measured it at 0.21 of the
> real optical's gradient energy, changed the objective, and got 0.78.

**The proof point nobody else will have.** Built-up land cover from radar alone scores AUC
0.483, below chance, so we measured it and took it out. Showing a judge a capability you
DELETED is counterintuitive enough to be memorable, and it retroactively makes every number
you did keep credible - it is evidence the rest was measured rather than hoped for.

**If you only get 15 seconds:** *"We colorize radar so anyone can read it, and we tell you
per pixel how much to trust it - including where we refuse to answer."*

### The four criteria, and your answer to each

| They assess | Your one-line answer |
|---|---|
| **Unique selling point** | "Every pixel carries a calibrated confidence, and it gates what the system is willing to report. Where we measured that something does not work, we removed it." |
| **Completeness** | "Working software, not a notebook - four workspaces, upload, georeferenced export, 43 tests, running on this laptop's CPU." |
| **Assumptions** | See Section 5. State them before you are asked. This is where most teams have nothing. |
| **Technical feasibility** | "Already feasible - it is running. 1.1 s per scene, CPU only, no cloud call, no API key." |

### Minute by minute

**0:00-0:40 - the problem and the USP.**
> "Optical satellites go blind under cloud, exactly during the monsoon. Radar sees through
> it, but radar is grayscale texture only specialists can read. We colorize it - and
> because radar carries no colour, every pixel ships a confidence value. Where the model
> is guessing, we say so instead of guessing confidently."

**0:40-2:30 - run it.** Flood tab, `India_1018317`. Drag the compare curtain. Move the
threshold - extent and IoU respond live. Toggle permanent water: *"a river is not a
disaster."* Then Colorization, and work the confidence gate from 0 to 0.8 - grey means
insufficient evidence.

**2:30-3:15 - completeness.** Scroll to Location & surface cover. *"Country, coordinates,
true ground area per pixel. And built-up is deliberately not reported - we measured it at
AUC 0.483, below chance, so we refuse to print it."*

**3:15-4:00 - assumptions, unprompted.** Two or three from Section 5. The flooded-vegetation one
lands hardest.

**4:00-5:00 - feasibility and questions.** *"Trained on Modal for about three dollars.
Inference runs here on the CPU - nothing leaves the machine, so venue wifi cannot break
it."* Then take questions from Section 10.

### If they only give you 90 seconds

USP sentence, run the flood tab once, then: *"and here is the part we refuse to report,
and why."* That is the whole pitch.

---

## 5. Assumptions we have made - a graded criterion, so say them first

Judges are explicitly assessing this. Every one below is a real modelling decision with a
consequence, not a disclaimer. **Volunteering these is worth more than being caught by
them.**

| # | Assumption | Why it is reasonable | Where it breaks |
|---|---|---|---|
| 1 | **Water appears dark in SAR** | Water is a specular reflector - it bounces the pulse away from the satellite | Flooded vegetation double-bounces off trunks and returns **bright**. Wind-roughened water too. On some fully-flooded chips the threshold scores IoU 0.01. **This is why we trained a network instead of trusting physics** |
| 2 | **Backscatter clipped to -30..0 dB** | Covers the physical range of land and water returns | Very bright urban double-bounce saturates at the top of the range |
| 3 | **Train/validation split by scene, not patch** | Adjacent tiles of one place are near-identical; a random split leaks | Costs us score - our numbers are *lower* than a random split would give, and real |
| 4 | **Sen1Floods11 hand labels are ground truth** | Published benchmark, expert-annotated, official test split | Human judgement on ambiguous edges. Label -1 means no-data and we mask it everywhere |
| 5 | **MC-dropout spread approximates model uncertainty** | Standard Bayesian approximation (Gal & Ghahramani) | Captures *epistemic* uncertainty only - not sensor noise or label error |
| 6 | **Confidence scale = p99 of measured spread (0.075)** | Measured over 2.62M validation pixels, not chosen | If the data distribution shifts, the scale should be re-measured |
| 7 | **Sentinel-2 optical is a valid cover reference** | It is the instrument that actually measures reflectance | Acquired days apart from the SAR, so crops and water genuinely differ. We exclude cloudy chips (blue-band mask, validated rho=0.897 against the human labeller) |
| 8 | **Temperature calibration transfers val to test** | Standard practice; ECE improved 0.029 to 0.016 with IoU unchanged | A very different region could need re-fitting |
| 9 | **Pixels are ~10 m, in a geographic CRS** | Read from each file's own georeferencing tags | We *assumed* a flat 100 m2/pixel early on and it overstated area by 14.6% for Pakistan. Now computed per scene (Section 6c) |
| 10 | **SEN1-2 pairs are co-registered** | Dataset design; we verified 0 unmatched across 10,000 pairs | Near-simultaneous, not simultaneous |

**The line to use:** *"We can show you where each of these breaks - that is why the
confidence map exists."*

---

## 6. Three results we are proud of *because* they cost us something

### 6a. The colorization retrain - our strongest technical story

**The finding.** The first colouriser measured a gradient-energy ratio of **0.21** against
the real Sentinel-2 optical: five times too smooth. The cause was the *objective*, not the
architecture. L1 at weight 100 dominated the loss, and **L1's optimum is the conditional
mean of every plausible colour - which is blur by definition.** PSNR rewards the same
thing, so the metric we were selecting checkpoints on **could not see the defect**.

That also means an earlier conclusion of ours was wrong for the wrong reason. We had
recorded "lambda_gan 0.2 is optimal, higher degrades" - but we reached that by watching PSNR
fall, which is exactly what *should* happen when an image stops being blurry.

**The fix.** Two rows on an A10G, one variable changed, 32 epochs each:

| row | recipe | sharp | perc | PSNR | SSIM |
|---|---|---|---|---|---|
| A-control | existing recipe, rerun | 0.073 | 2.0285 | 12.68 | 0.175 |
| **B-sharp** | L1 100->60, +gradient loss 20, GAN 0.2->0.5 | **0.958** | 2.7511 | 11.71 | **0.200** |

Independently re-measured on held-out tiles: gradient energy **0.21 -> 0.78**, saturation
**45% -> 102%**, spatial variance **12% -> 51%**.

**What it cost.** Perceptual distance rose 36% and PSNR fell ~1 dB. SSIM *improved*
(0.175 -> 0.200), which matters - SSIM is structure-sensitive, so it agrees that real
detail appeared rather than noise.

**Three caveats to volunteer, never to hide:**

1. The comparison is 32 epochs against a shipped model trained for 45. B still wins
   sharpness by 5.7x, so the conclusion holds, but a matched-length run is the clean claim.
2. Our `balanced` checkpoint-selection metric was **miscalibrated** and would have picked
   the blurriest epoch. We used `last.pt` instead. Say so if asked - a real bug caught by
   reading the numbers rather than trusting the machinery.
3. Spatial variance is 51% of reality. **Better, not solved.**

**A trade the demo exposes.** MC-dropout averaging itself costs texture: sharpness is
0.53 at 2 passes and 0.43 at 20. More passes buys a better uncertainty estimate and spends
detail. The passes slider is that dial, and it is worth saying out loud.

**Rollback:** previous weights in `~/sih-data/checkpoints/backup-pre-sharpen/`.

### 6b. Land cover from radar does not work, and we say so

The obvious feature is "percentage forest / water / bare from the SAR image". We built the
experiment properly - calibrated on five regions, tested on six the model had never seen -
and it failed:

| class | held-out IoU | per-scene area error |
|---|---|---|
| water | 52.5% | 7.0 pp - but our own CNN gets 68.1% |
| dense vegetation | 54.3% | 16.3 pp |
| low vegetation | 22.3% | 18.6 pp |
| bare | 13.7% | 15.8 pp |
| **built-up** | **0.0%** | **AUC 0.483 - below chance** |

Built-up is not separable from bare soil at C-band, and the NDBI reference label used to
score it is itself invalid: it calls **26% of rural Pakistani flood plain "buildings"**,
one chip as high as 84%. We cannot score it honestly in either direction. In arid regions
the whole classifier lands *below* the majority-class baseline (Pakistan -13.6 pp, Somalia
-14.4 pp). The ceiling is physics: a 60-tree random forest at depth 14 beats a depth-4
decision tree by 0.66 pp.

**So the app measures surface cover from the co-registered Sentinel-2 optical chip**, says
so on screen, and reports built-up as *not available* with the reason. Water stays with the
trained SAR model, which beats optical thresholding on the same scenes.

**If a judge asks why there is no urban number, this is the strongest moment in the demo.**

### 6c. A live bug the geolocation work exposed

Sen1Floods11 rasters are in a **geographic** CRS, so pixel scale is in degrees and a degree
of longitude shrinks as cos(latitude). The app had assumed a flat 100 m2/pixel, overstating
ground area by:

| Somalia | Nigeria | India | Pakistan | Spain | USA |
|---|---|---|---|---|---|
| +0.3% | +1.2% | **+11.9%** | **+14.6%** | +27.4% | +28.4% |

Flood extent in km2 is the headline number, and India and Pakistan - the two an SIH panel
is most likely to ask about - read 12 to 15% high. Fixed; area now comes from each file's own
georeferencing, and the metric tile, the report card and the exported GeoTIFF all agree.

---

## 7. Does what we built actually answer the PS? Clause by clause

Print this. If a judge challenges scope or novelty, answer from this table.

| The PS asks for | What we have | Strength |
|---|---|---|
| "colorize grayscale SAR images for enhanced interpretation" | Working colouriser, live in the app | **Direct** |
| "trained using pairs of SAR and Optical images" | 10,000 verified SEN1-2 pairs, split by scene | **Direct** |
| "minimizing a loss function that captures the difference between predicted and actual color images" | L1 + frozen-VGG perceptual + adversarial + **gradient-difference** | **Direct** |
| "innovative approaches in **data pre-processing**" | Scene-level splits, dB calibration, cloud masking validated against the human labeller (rho=0.897), corrupt/duplicate audit | Strong |
| "innovative approaches in **evaluation methodologies**" | **Our strongest clause.** We built a sharpness metric because PSNR and L1 are structurally blind to blur | **Strongest** |
| "Existing DL models... performance is **not satisfactory**" | **We diagnosed WHY and fixed it** - see Section 6a | **Strongest** |
| "improve usability in geological studies and **environmental monitoring**" | Flood mapping, IoU 0.681 calibrated, on a public benchmark | **Direct** |
| "Users: Remote Sensing Image Analysts" | Analyst-shaped tooling: georeferenced GeoTIFF export, QGIS-ready, confidence gating | **Direct** |
| "Desired Outcome: DL based SAR Image Colorization **Software**" | Running software, not a notebook. Landing page + 4 workspaces + upload + export | **Direct** |

### The line that matters most

The PS says: *"Existing Deep Learning models have been proposed and used but their
performance is **not satisfactory**."* **It does not say why.** That is the gap the PS is
actually pointing at, and it is exactly what we answered:

> Existing models are unsatisfactory because they are trained on L1, and **L1's optimum is
> the conditional mean of every plausible colour - which is blur by definition.** PSNR
> rewards the same thing, so the standard evaluation cannot even see the defect. We
> measured it (0.21 of the real optical's gradient energy), changed the objective, and
> got 0.78.

**That is a direct answer to the PS's own framing of the problem, in the PS's own words.**
Lead with it against a technical panel.

### Where to be careful: "a **novel** DL model needs to be designed"

Be precise here, because it is the one clause where an overclaim is available and a sharp
judge would catch it.

**Do not say:** "we invented a new architecture." Our generator is a ResNet34-UNet with a
PatchGAN discriminator - a well-known pix2pix-family design, chosen deliberately because
row 1 of our ablation is the honest baseline.

**Do say:** "the novelty is in the objective and the evaluation, not the layer diagram."
Specifically:

1. A **gradient-difference loss** that targets the exact failure mode we measured
2. A **calibrated per-pixel uncertainty** layer, with the scale measured (p99 of 2.62M
   pixels) rather than guessed
3. **Confidence-gated downstream analytics** - the uncertainty actually controls what the
   system is willing to report
4. A **sharpness metric** that made a defect visible which PSNR and SSIM could not see

Then the honest close: *"Swapping in a Swin or a diffusion backbone is a weekend. Knowing
which loss is causing the blur, and having a metric that can see it, is the part that
took the work."*

### Two gaps we do not paper over

- **Geological studies** are named in the PS; we demonstrated environmental monitoring
  (flood) and not lithology. Say so if asked - the pipeline is identical, we simply have
  no geological ground truth to validate against, and we do not ship unvalidated claims.
- **Colour fidelity** is still imperfect: spatial variance is 51% of reality and output
  runs ~23% darker than truth (Section 6a). Sharp and correctly saturated, not yet photographic.


---

## 8. Why we expanded past colorization - know this answer

**Expect the challenge:** *"SIH1733 asks for SAR colorization. Why have you built a flood
detector?"* It is a fair question and there is a principled answer. Do not sound defensive.

**1. The PS's goal is usability, not colour.** SIH1733 asks us to improve the *usability of
SAR data for environmental monitoring*, and names remote-sensing analysts as the users.
Colorization is the **method**; usability is the **goal**. Flood mapping is how we
demonstrate the goal was actually met - a colour image nobody acts on has not improved
anything.

**2. Colorization alone cannot be validated, and we refuse to ship unvalidated work.**
This is the strongest reason. Radar carries no colour, so there is no ground truth for
"is this colour correct?" - only a same-place optical image taken days apart, by which
time crops, water and snow have genuinely changed. Flood mapping has **hard ground truth**:
446 hand-labelled masks on a public benchmark with a published test split. Without the
flood module our entire project would rest on *"it looks better"*, which is not a claim a
technical panel should accept, and not one we want to make.

**3. A confidence map needs a consumer.** Per-pixel uncertainty is only interesting if
something downstream *uses* it. Flood mapping is what turns "here is an uncertainty map"
into "low-confidence regions never raise an alert." The gate is the contribution; flood
mapping is what it gates.

**4. Change detection is the operational question.** A responder does not ask "where is
water" - rivers are always water. They ask **"what is water NOW that was not water
before."** That is a different computation, and it is the one that matters during a flood.

**5. Risk management, stated plainly.** Colorization was the weaker half for most of the
build (see Section 6a). It is independent of the flood module, so a bad colorization result could
never leave us with nothing to show. That is engineering judgement, not scope creep.

**The one-line answer:** *"Colorization is the method the PS asks for. Flood mapping is how
we prove it improved usability, and it is the only half with hard ground truth - so it is
what keeps us honest."*

---

## 9. What each tab does

### Flood mapping - `/flood`
The measured core. One Sentinel-1 scene in, inundation extent out.

- **Six layers:** Compare (swipe SAR against detection), Detection, Agreement
  (hit / false-positive / missed against the hand labels), SAR VV, SAR VH, Permanent water
- **Decision panel:** water-probability threshold slider - extent, IoU, precision and
  recall all respond live, because this is a decision tool, not a picture
- **Permanent-water toggle:** separates flood from baseline. A river is not a disaster
- **Region sweep:** run the whole region at once, ranked worst-first
- **Location & surface cover:** country, continent, coordinates and true m2/pixel, plus the
  optical cover breakdown (Section 6b)
- **Exports:** georeferenced flood-mask GeoTIFF, probability GeoTIFF, JSON report. The
  GeoTIFFs carry the source CRS so they drop straight onto the original in QGIS
- **Upload:** your own 2-band Sentinel-1 GeoTIFF - verified to score identically to the
  benchmark path

### Change detection - `/change`
Two acquisitions of one footprint, differenced.

- **Four layers:** Before <-> After swipe, Change map, Before, After
- **dB-difference threshold:** SAR is already logarithmic, so the classic log-ratio reduces
  to a plain subtraction. Darkening = new water, brightening = new roughness
- **New water vs receded:** the flood model runs on *both* dates and the masks are
  differenced - the operational answer, not just "where is water"
- **Water cover before/after** as percentages of the scene
- Needs two of your own GeoTIFFs. `demo-uploads/` has a **synthetic** before-image,
  labelled as such - never present it as two real passes

### Colorization - `/color`
The PS's headline capability, retrained to remove blur (Section 6a).

- **Four layers:** Compare, Colorized, Ground truth, Confidence
- **MC-dropout passes (2-24):** more passes = better uncertainty, less texture. A real
  trade, and the slider is the dial
- **Confidence gate:** pixels below your threshold return neutral grey - *"insufficient
  evidence"* rather than a confident guess. This is the differentiator; demo it
- **Pixel probe:** hover the Confidence layer for the exact value at that pixel
- **Exports:** the *gated* frame you are looking at, plus the confidence map
- **Upload:** single-band SAR GeoTIFF or grayscale PNG; it reports how it read your file

### Method - `/method`
The numbers and how they were produced. Open this when a judge asks "how do you know?"

### Shared across tabs
Zoom and pan are **locked across every layer and both compare halves** - zoom into a corner
on Colorized, switch to Confidence, and you are on the same patch at the same magnification.
That is the actual analysis gesture. `Ctrl+K` searches all 446 scenes; `?` lists shortcuts.

---

## 10. Questions you will be asked

**"Isn't colorization just cosmetic?"**
No. It converts imagery only radar specialists can use into imagery any responder can use.
The PS names analyst usability as the goal and lists remote-sensing analysts as the users.

**"How do you know the colours are right?"**
We don't, everywhere - and that is the point. Radar carries no colour information, so part
of the output is inference. We measure the model's own disagreement across ten dropout
passes and publish it per pixel. Where passes agree the model is reading evidence; where
they diverge it is guessing.

**"What is Monte-Carlo dropout?"**
Dropout normally switches off at inference. We leave it on and run the model ten times,
getting ten plausible colourings. Their spread is the uncertainty.

**"What does a confidence of 0.6 actually mean?"**
`conf = 1 - std/0.075`, where std is the per-pixel standard deviation across 10 passes.
The 0.075 is the **p99 of the measured spread over 2.62M validation pixels** (median 0.034,
p95 0.061). Our first version divided by 0.35, which was guessed - it squeezed 99% of
pixels into 0.79 to 0.95, so the gate slider had two reachable states instead of a range.

**"Why split train/validation by scene?"**
Patches from one scene are adjacent tiles of the same place. A random split puts
near-identical imagery on both sides and the score becomes meaningless. Our numbers are
lower than they would otherwise be, and they are real.

**"Why does water look dark in SAR?"**
Water is a specular reflector - it bounces the pulse away from the satellite.

**"Then why does your flood detector miss some floods?"** <- *know this cold*
Because that assumption breaks. Floodwater under vegetation double-bounces off trunks and
returns **bright**, not dark. Wind-roughened water does the same. On some fully-flooded
chips the threshold scores IoU 0.01 and confidently reports no water. That is exactly why
we trained a segmentation network and why the confidence gate exists.

**"Have you trained the full model yet?"**
Yes, both. Flood: ResNet34-UNet, epoch 32, IoU 0.681 calibrated. Colorization: ResNet34
generator retrained to remove blur (Section 6a). Training on Modal A10G; **inference on the
laptop CPU**.

**"Where is the model running right now?"** <- *expect this during the live demo*
This laptop's CPU, in-process. No GPU, no cloud call, no API key. Modal was training only.
*"Nothing leaves the machine, so venue wifi cannot break the demo."*

**"Can it handle an image I give you?"**
Yes, and we verified it rather than assuming: POST the raw file of a benchmark chip to the
upload endpoint and the water area matches the benchmark path to **0.00%** on India, Spain
and Somalia. It needs a genuine 2-band Sentinel-1 GeoTIFF - a screenshot is refused with an
explanation, because an 8-bit stretch has already destroyed the calibrated backscatter.

**"Is this not just pix2pix?"**
pix2pix is our baseline, deliberately - row one of the ablation. The contribution is the
uncertainty layer, the confidence-gated analytics, and the measured objective fix in Section 6a.

**"What is your biggest risk?"**
Hallucination. Say it plainly, then: which is why we built the confidence map first rather
than last.

---

## 11. Claims we do NOT make

Claiming a component we have not run is the fastest way to lose a technical panel.

| Claim | Status |
|---|---|
| Conditional GAN colouriser, ResNet34 + ImageNet | **built** |
| Frozen VGG16 perceptual loss | **built** |
| Gradient-difference loss (the blur fix) | **built and measured** - Section 6a |
| MC-dropout confidence map | **built**, scale measured not guessed |
| Flood mapping, threshold + learned | **built and benchmarked** |
| Probability calibration | **built** - ECE 0.029 -> 0.016 |
| Geolocation, country + continent | **built** - 446/446, offline |
| Surface cover from Sentinel-2 optical | **built** - built-up deliberately refused |
| Surface cover from SAR alone | **measured and REJECTED** - Section 6b. Do not claim it |
| Confidence *predicts error* on colorization | **roadmap** - not yet proven to rank error |
| Swin-Transformer generator | **roadmap** |
| Land-cover conditioning of the generator | **roadmap** - data downloaded, not wired |
| QGIS plugin | **roadmap** |

If asked about a roadmap row: *"that is the next step, not today's build."* That answer
costs nothing. A bluff costs everything.

---

## 12. Who owns what

| Area | Owns | Must be able to explain |
|---|---|---|
| Data & verification | download, quality checks, exclusions | why we split by scene, not patch |
| Colorization | generator, losses, the retrain | why L1 causes blur (Section 6a) |
| Uncertainty | MC-dropout, calibration | what confidence measures, and the passes trade |
| Flood | threshold + segmentation | why water is dark, and when it is not |
| App & demo | UI, inference, packaging | the live demo, offline |
| Pitch & deck | slides, timing, Q&A | all of the above one level deep |

**Put real names on these before the 19th.** Every member should answer at a basic level
for *any* row - judges pick who they ask.

---

## 13. Before the 19th

**Format (from Prof. Raghu):** no formal 10-minute talk. Judges circulate desk to desk,
5 minutes each, grading USP / completeness / assumptions / technical feasibility. The
filled PPT template is uploaded **at the end** of the hackathon.

- [ ] Rehearse the Section 4 desk pitch **twice, timed**, with wifi **off**
- [ ] Everyone reads Section 5 (assumptions) - it is a graded criterion and it is free marks
- [ ] Assign the six names in Section 12; judges pick who they ask
- [x] Fill the PPT template Prof. Raghu mailed - done, in **his** template, not ours:
      `SIH2026-DeltaForce-SIH1733-IDEA-SUBMISSION.pptx`. Six slides (the template caps it
      at six including the title), points not paragraphs, pipeline diagram on TECHNICAL
      APPROACH, instructions slide deleted as it tells you to. Rebuild with
      `python deck/fill_template.py`; the blank template is left untouched
- [ ] **Team ID on slide 1** - it currently reads `<FILL BEFORE UPLOAD>`. This is the only
      missing field in the whole file
- [ ] **Re-export to PDF after filling the Team ID.** The portal takes PDF only - "No PPT,
      Word Doc or any other format will be supported." File > Export > Create PDF. The
      `.pdf` next to the pptx is from before the Team ID went in, so it is stale
- [ ] Real Sentinel-1 `.tif` on the laptop (Copernicus Browser or ASF Vertex)
- [ ] A real before/after pair for change detection - `demo-uploads/` currently holds a
      **synthetic** before-image, clearly labelled. Never present it as two real passes
- [ ] Laptop charged, app already running before judging starts - do not cold-start in
      front of a judge (first inference loads the model and takes ~5 s)
- [ ] Ask the professor: is AI-assisted development disclosed? Are pre-trained ImageNet
      weights allowed? Dataset attribution needed on the template?
- [ ] **Revoke the Modal API token** pasted in chat and issue a fresh one

## 14. One-line summary

*"Radar sees through the monsoon. We make it readable, we tell you per pixel how much to
trust it, and where we measured that something does not work, we removed it."*
