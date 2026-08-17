"""Modal app for ChromaSAR training.

    modal run modal_app.py::prepare_data          # pull SEN1-2 into the volume (once)
    modal run modal_app.py::train --epochs 40     # train on GPU
    modal volume get chromasar-runs base/best.pt .

Budget discipline, because Modal bills by the second and the free tier is $30/month:
  * every function has a hard timeout - a hung job cannot drain the month overnight
  * the dataset lives in a Volume and is downloaded ONCE, not per run
  * `train` prints an elapsed-cost estimate so the spend is visible, not inferred
"""
from __future__ import annotations

import os

import modal

APP = "chromasar"
GPU = os.environ.get("CHROMASAR_GPU", "A10G")
# rough public on-demand rates; confirm against modal.com/pricing before trusting
RATE_USD_PER_HOUR = {"T4": 0.59, "L4": 0.80, "A10G": 1.10, "A100": 2.50, "H100": 4.00}

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("torch==2.5.1", "torchvision==0.20.1", "numpy<2", "pillow", "tifffile")
    .add_local_dir("train", "/root/train")
    .add_local_dir("flood", "/root/flood")
    .add_local_dir("eval", "/root/eval")
    # train.py resolves config.py from its parent directory
    .add_local_file("config.py", "/root/config.py")
)

data_vol = modal.Volume.from_name("chromasar-data", create_if_missing=True)
runs_vol = modal.Volume.from_name("chromasar-runs", create_if_missing=True)

app = modal.App(APP, image=image)


@app.function(volumes={"/data": data_vol}, timeout=60 * 60, cpu=4.0)
def prepare_data(pairs: int = 10000, seed: int = 1733):
    """Download SEN1-2 straight into the Volume.

    Pulling from TUM on Modal's network is far faster than uploading the local copy
    over a home connection, and it keeps the dataset next to the GPU.
    """
    import ftplib
    import queue
    import random
    import threading
    import time

    HOST, USER = "dataserv.ub.tum.de", "m1436631"
    SEASONS = ["ROIs1158_spring", "ROIs1868_summer", "ROIs1970_fall", "ROIs2017_winter"]
    dest = "/data/sen1-2"
    os.makedirs(f"{dest}/s1", exist_ok=True)
    os.makedirs(f"{dest}/s2", exist_ok=True)

    have = len([f for f in os.listdir(f"{dest}/s1") if f.endswith(".png")])
    if have >= pairs:
        print(f"already have {have} pairs - nothing to do")
        return have

    def conn():
        f = ftplib.FTP(HOST, timeout=90)
        f.login(USER, USER)
        f.set_pasv(True)
        return f

    rng = random.Random(seed)
    ftp = conn()
    jobs = []
    per_season = pairs // len(SEASONS)
    for season in SEASONS:
        scenes = [os.path.basename(p) for p in ftp.nlst(season)
                  if os.path.basename(p).startswith("s1_")]
        rng.shuffle(scenes)
        got, si = 0, 0
        per_scene = max(20, per_season // max(1, min(len(scenes), 40)))
        while got < per_season and si < len(scenes):
            sc = scenes[si]
            si += 1
            files = [os.path.basename(f) for f in ftp.nlst(f"{season}/{sc}")
                     if f.endswith(".png")]
            rng.shuffle(files)
            take = files[:min(per_scene, per_season - got)]
            idx = sc.split("_", 1)[1]
            for fn in take:
                jobs.append((f"{season}/{sc}/{fn}",
                             f"{season}/s2_{idx}/{fn.replace('_s1_', '_s2_', 1)}", fn))
            got += len(take)
        print(f"  {season}: {got} pairs planned", flush=True)
    ftp.quit()

    q = queue.Queue()
    for j in jobs:
        q.put(j)
    done = [0]
    failed = [0]
    lock = threading.Lock()

    def worker():
        """TUM drops long-lived FTP connections under concurrency, so a dead socket
        must be replaced rather than treated as a failed file. Without this the whole
        job aborts on the first EOFError."""
        f = conn()
        streak = 0
        while True:
            try:
                s1r, s2r, fn = q.get_nowait()
            except queue.Empty:
                break
            try:
                p1 = f"{dest}/s1/{fn}"
                p2 = f"{dest}/s2/{fn.replace('_s1_', '_s2_', 1)}"
                if not (os.path.exists(p1) and os.path.exists(p2)):
                    with open(p1, "wb") as fh:
                        f.retrbinary(f"RETR {s1r}", fh.write, 65536)
                    with open(p2, "wb") as fh:
                        f.retrbinary(f"RETR {s2r}", fh.write, 65536)
                streak = 0
                with lock:
                    done[0] += 1
                    if done[0] % 500 == 0:
                        print(f"  {done[0]}/{len(jobs)}", flush=True)
            except Exception as e:                               # noqa: BLE001
                streak += 1
                with lock:
                    failed[0] += 1
                    if failed[0] <= 8:
                        print(f"  retry after {type(e).__name__} on {fn}", flush=True)
                q.put((s1r, s2r, fn))                # requeue, do not lose the file
                try:
                    f.quit()
                except Exception:                                # noqa: BLE001
                    pass
                try:
                    f = conn()
                except Exception:                                # noqa: BLE001
                    time.sleep(5)
                    try:
                        f = conn()
                    except Exception:                            # noqa: BLE001
                        break
                if streak >= 6:
                    break                            # this worker is wedged; let others finish
            finally:
                q.task_done()

    ts = [threading.Thread(target=worker, daemon=True) for _ in range(8)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()

    data_vol.commit()
    n1 = len([f for f in os.listdir(f"{dest}/s1") if f.endswith(".png")])
    n2 = len([f for f in os.listdir(f"{dest}/s2") if f.endswith(".png")])
    print(f"volume now holds {n1} SAR / {n2} optical patches "
          f"({failed[0]} transient FTP errors retried)")
    n = min(n1, n2)
    return n


@app.function(volumes={"/data": data_vol}, timeout=60 * 30, cpu=4.0)
def unpack_data():
    """Extract the uploaded SEN1-2 tar into the volume.

    We upload rather than download here because TUM's FTP refuses Modal's datacenter
    IPs. Shipping the local archive also means the remote dataset is byte-identical to
    the one we verified locally (0 corrupt, 0 unmatched, 0 duplicates), which download
    -again-remotely would not guarantee.
    """
    import glob
    import tarfile

    cands = ([f"/data/{n}" for n in ("sen1-2.tar", "data.tar")]
             + glob.glob("/data/**/sen1-2.tar", recursive=True))
    tar = next((c for c in cands if os.path.exists(c)), None)
    if tar is None:
        return {"ok": False, "reason": "no sen1-2.tar found in volume",
                "top_level": os.listdir("/data")}
    print(f"extracting {tar} ({os.path.getsize(tar)/1e9:.2f} GB)", flush=True)

    with tarfile.open(tar, "r") as tf:
        tf.extractall("/data")
    os.remove(tar)

    # drop the mangled upload directory if it is now empty
    for junk in glob.glob("/data/C:*"):
        for root, dirs, files in os.walk(junk, topdown=False):
            for d in dirs:
                try:
                    os.rmdir(os.path.join(root, d))
                except OSError:
                    pass
        try:
            os.rmdir(junk)
        except OSError:
            pass

    s1 = len([f for f in os.listdir("/data/sen1-2/s1") if f.endswith(".png")])
    s2 = len([f for f in os.listdir("/data/sen1-2/s2") if f.endswith(".png")])
    data_vol.commit()
    print(f"volume now holds {s1} SAR / {s2} optical patches")
    return {"ok": s1 == s2 and s1 > 0, "s1": s1, "s2": s2}


@app.function(volumes={"/data": data_vol}, timeout=60 * 40, cpu=4.0)
def prepare_floods():
    """Pull Sen1Floods11 from its public GCS bucket straight into the volume.

    GCS serves Modal happily - unlike TUM's FTP, there is no datacenter rate limit to
    trip. 446 chips: SAR VV+VH, hand-drawn flood masks, matching optical.
    """
    import json
    import queue
    import threading
    import urllib.parse
    import urllib.request

    BUCKET, BASE = "sen1floods11", "v1.1/data/flood_events/HandLabeled"
    SPLITS = "v1.1/splits/flood_handlabeled"
    API = f"https://storage.googleapis.com/storage/v1/b/{BUCKET}/o"
    dest = "/data/sen1floods11"

    def listing(prefix):
        out, tok = [], None
        while True:
            u = f"{API}?prefix={prefix}&maxResults=1000"
            if tok:
                u += f"&pageToken={tok}"
            with urllib.request.urlopen(u, timeout=90) as r:
                d = json.load(r)
            out += [i["name"] for i in d.get("items", [])]
            tok = d.get("nextPageToken")
            if not tok:
                return out

    objs = []
    for part in ("S1Hand", "LabelHand", "S2Hand"):
        got = listing(f"{BASE}/{part}/")
        objs += got
        print(f"  {part}: {len(got)} files", flush=True)
    objs += listing(SPLITS + "/")

    q = queue.Queue()
    for o in objs:
        q.put(o)
    done, lock = [0], threading.Lock()

    def worker():
        while True:
            try:
                name = q.get_nowait()
            except queue.Empty:
                return
            try:
                local = os.path.join(dest, *name.split("/")[-2:])
                os.makedirs(os.path.dirname(local), exist_ok=True)
                if not (os.path.exists(local) and os.path.getsize(local) > 0):
                    url = (f"https://storage.googleapis.com/{BUCKET}/"
                           f"{urllib.parse.quote(name)}")
                    with urllib.request.urlopen(url, timeout=120) as r:
                        data = r.read()
                    with open(local, "wb") as fh:
                        fh.write(data)
                with lock:
                    done[0] += 1
                    if done[0] % 200 == 0:
                        print(f"  {done[0]}/{len(objs)}", flush=True)
            except Exception as e:                               # noqa: BLE001
                print("  fail", name, e, flush=True)
            finally:
                q.task_done()

    ts = [threading.Thread(target=worker, daemon=True) for _ in range(16)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    data_vol.commit()
    counts = {d: len(os.listdir(os.path.join(dest, d)))
              for d in sorted(os.listdir(dest))
              if os.path.isdir(os.path.join(dest, d))}
    print("chips per folder:", counts)
    return counts


@app.function(gpu=GPU, volumes={"/data": data_vol, "/runs": runs_vol},
              timeout=60 * 60 * 3)
def train_flood(epochs: int = 40, size: int = 512, batch: int = 8,
                encoder: str = "resnet34", pretrained: bool = True,
                run: str = "flood512"):
    """Flood segmentation on GPU. This is the run that fixes the 128px-vs-512px
    caveat currently flagged in the deck."""
    import subprocess
    import sys
    import time

    cmd = [sys.executable, "/root/flood/train_flood.py",
           "--data", "/data/sen1floods11", "--out", f"/runs/{run}",
           "--epochs", str(epochs), "--size", str(size), "--batch", str(batch),
           "--encoder", encoder, "--workers", "4"]
    if not pretrained:
        cmd.append("--no-pretrained")
    t0 = time.time()
    rc = subprocess.call(cmd)
    hrs = (time.time() - t0) / 3600
    runs_vol.commit()
    rate = RATE_USD_PER_HOUR.get(GPU, 1.0)
    print(f"\n{GPU} {hrs:.2f} h ~= ${hrs*rate:.2f}")
    return {"rc": rc, "hours": round(hrs, 3), "est_usd": round(hrs * rate, 2)}


@app.function(gpu=GPU, volumes={"/data": data_vol, "/runs": runs_vol},
              timeout=60 * 60 * 4)
def train(epochs: int = 40, batch: int = 32, nf: int = 64, lr: float = 2e-4,
          lambda_l1: float = 100.0, limit: int | None = None, run: str = "base",
          exclude: str = "", lambda_gan: float = 0.2, gan_warmup: int = 5,
          lambda_perc: float = 0.0, generator: str = "unet",
          no_pretrained: bool = False):
    """Train pix2pix on the GPU. Hard 4h timeout caps the worst-case spend."""
    import subprocess
    import sys
    import time

    excl_path = ""
    if exclude:
        excl_path = "/root/exclude_scenes.txt"
        with open(excl_path, "w", encoding="utf8") as fh:
            fh.write(exclude)

    out = f"/runs/{run}"
    cmd = [sys.executable, "/root/train/train.py",
           "--data", "/data/sen1-2", "--out", out,
           "--epochs", str(epochs), "--batch", str(batch), "--nf", str(nf),
           "--lr", str(lr), "--lambda-l1", str(lambda_l1), "--workers", "4",
           "--lambda-gan", str(lambda_gan), "--gan-warmup", str(gan_warmup),
           "--lambda-perc", str(lambda_perc), "--generator", generator]
    if no_pretrained:
        cmd.append("--no-pretrained")
    if limit:
        cmd += ["--limit", str(limit)]
    if excl_path:
        cmd += ["--exclude", excl_path]

    t0 = time.time()
    rc = subprocess.call(cmd)
    hrs = (time.time() - t0) / 3600
    rate = RATE_USD_PER_HOUR.get(GPU, 1.0)
    print(f"\n{GPU} for {hrs:.2f} h  ~= ${hrs * rate:.2f} "
          f"(at ~${rate}/h - verify on modal.com/pricing)")
    runs_vol.commit()
    return {"rc": rc, "hours": hrs, "est_usd": round(hrs * rate, 2), "out": out}


@app.function(gpu=GPU, volumes={"/data": data_vol, "/runs": runs_vol}, timeout=900)
def smoke():
    """Cheapest possible end-to-end check. Run this FIRST.

    Verifies: GPU visible, image complete, volume mounted, dataset readable, and one
    training step actually runs - for a few cents instead of a few dollars.
    """
    import subprocess
    import sys

    import torch
    print(f"torch {torch.__version__}  cuda={torch.cuda.is_available()}  "
          f"device={torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none'}")
    n = len(os.listdir("/data/sen1-2/s1")) if os.path.exists("/data/sen1-2/s1") else 0
    print(f"dataset in volume: {n} SAR patches")
    if n < 64:
        return {"ok": False, "reason": f"only {n} patches - run prepare_data first"}

    rc = subprocess.call([sys.executable, "/root/train/train.py",
                          "--data", "/data/sen1-2", "--out", "/runs/smoke",
                          "--epochs", "1", "--batch", "8", "--limit", "64",
                          "--workers", "2"])
    runs_vol.commit()
    return {"ok": rc == 0, "rc": rc}


@app.function(gpu=GPU, volumes={"/data": data_vol, "/runs": runs_vol},
              timeout=60 * 60 * 6)
def sharpen(epochs: int = 32, batch: int = 32, exclude: str = ""):
    """Retrain the colouriser to stop producing blur, and PROVE it did.

    The shipped model measures a gradient-energy ratio of 0.20 against the real
    Sentinel-2 optical - five times too smooth. The cause is the objective, not the
    architecture: L1 at weight 100 dominates, and L1's optimum is the conditional MEAN
    of every plausible colour, which is by definition texture-free. PSNR rewards the
    same thing, so the metric we previously selected checkpoints on could not see the
    defect. The earlier conclusion "lambda_gan 0.2 is optimal, higher degrades" was
    reached by watching PSNR fall - which is exactly what should happen when an image
    stops being blurry.

    Two rows, one variable at a time, so the result is attributable:

      A-control    today's recipe, rerun on this code    -> the honest baseline
      B-sharp      L1 100->60, + gradient loss, GAN 0.2->0.5, select=balanced

    Both log `val_sharp` every epoch, so the trade is visible as it happens rather than
    discovered afterwards. Selection is `balanced` for row B: perceptual distance
    penalised by |1 - sharpness|, because selecting on sharpness alone is trivially
    won by noise.
    """
    import json
    import subprocess
    import sys
    import time

    excl = ""
    if exclude:
        excl = "/root/exclude_scenes.txt"
        with open(excl, "w", encoding="utf8") as fh:
            fh.write(exclude)

    COMMON = ["--generator", "resnet34", "--lambda-perc", "1.0"]
    runs = [
        ("A-control", COMMON + ["--lambda-gan", "0.2", "--gan-warmup", "5",
                                "--lambda-l1", "100", "--select", "perceptual"]),
        ("B-sharp",   COMMON + ["--lambda-gan", "0.5", "--gan-warmup", "5",
                                "--lambda-l1", "60", "--lambda-grad", "20",
                                "--select", "balanced"]),
    ]

    results = {}
    for name, extra in runs:
        out = f"/runs/sharpen/{name}"
        done = f"{out}/history.json"
        import os as _os
        if _os.path.exists(done):
            print(f"[{name}] already complete, skipping", flush=True)
            with open(done, encoding="utf8") as fh:
                results[name] = json.load(fh)[-1]
            continue
        cmd = [sys.executable, "/root/train/train.py",
               "--data", "/data/sen1-2", "--out", out,
               "--epochs", str(epochs), "--batch", str(batch)] + extra
        if excl:
            cmd += ["--exclude", excl]
        print("", flush=True)
        print(f"=== {name} ===", flush=True)
        print(" ".join(cmd), flush=True)
        t0 = time.time()
        subprocess.run(cmd, check=True)
        with open(done, encoding="utf8") as fh:
            hist = json.load(fh)
        results[name] = hist[-1]
        print(f"[{name}] {time.time() - t0:.0f}s", flush=True)

    print("")
    print("=" * 74)
    print(f"{'row':12} {'PSNR':>7} {'SSIM':>7} {'perc':>8} {'sharp':>7}   verdict")
    print("=" * 74)
    for name, r in results.items():
        sh = r.get("val_sharp", float("nan"))
        verdict = ("blurry" if sh < 0.45 else "soft" if sh < 0.7
                   else "close to real" if sh < 1.25 else "noisy")
        print(f"{name:12} {r['val_psnr']:7.2f} {r['val_ssim']:7.3f} "
              f"{r['val_perc']:8.4f} {sh:7.3f}   {verdict}")
    print("")
    print("PSNR is EXPECTED to fall on row B. It rewards the conditional mean, which")
    print("is the blur we are removing. Judge on sharp + perc together.")
    return results


@app.function(gpu=GPU, volumes={"/data": data_vol, "/runs": runs_vol},
              timeout=60 * 60 * 5)
def ablation(epochs: int = 15, batch: int = 32, exclude: str = ""):
    """The four-row ablation table — the actual technical contribution.

    ISRO's PS says existing DL models "are not satisfactory" without saying why. One
    trained model cannot answer that; a controlled comparison can. Each row changes
    exactly ONE thing:

      1 baseline           plain U-Net, L1 + adversarial          (what the field does)
      2 + perceptual       adds frozen-VGG16 feature loss         (does it fix blur?)
      3 + pretrained enc   ResNet34 with ImageNet weights         (does transfer help?)
      4 architecture only  same ResNet34, random init             (isolates transfer
                                                                   from architecture)

    Row 4 matters most for honesty: without it, any gain in row 3 could be the
    architecture rather than the pretrained weights, and the claim would be unproven.
    """
    import json
    import subprocess
    import sys
    import time

    excl = ""
    if exclude:
        excl = "/root/exclude_scenes.txt"
        with open(excl, "w", encoding="utf8") as fh:
            fh.write(exclude)

    GAN = ["--lambda-gan", "0.2", "--gan-warmup", "5"]   # measured optimum
    runs = [
        ("1-baseline", ["--generator", "unet", "--lambda-perc", "0"] + GAN),
        ("2-perceptual", ["--generator", "unet", "--lambda-perc", "1.0"] + GAN),
        ("3-pretrained", ["--generator", "resnet34", "--lambda-perc", "1.0"] + GAN),
        ("4-arch-only", ["--generator", "resnet34", "--lambda-perc", "1.0",
                         "--no-pretrained"] + GAN),
    ]
    results = {}
    t_all = time.time()
    for name, extra in runs:
        out = f"/runs/abl/{name}"
        # resume: a row that already completed this many epochs is not redone, so a
        # detached relaunch picks up where the previous one stopped
        hist_done = os.path.join(out, "history.json")
        if os.path.exists(hist_done):
            try:
                with open(hist_done, encoding="utf8") as fh:
                    h = json.load(fh)
                if len(h) >= epochs:
                    b = max(h, key=lambda r: -r.get("val_perc", 1e9))
                    results[name] = {"rc": 0, "minutes": 0.0,
                                     "psnr": round(b["val_psnr"], 3),
                                     "ssim": round(b["val_ssim"], 4),
                                     "epoch": b["epoch"], "resumed": True}
                    print(f"===== {name}: already complete, skipping =====",
                          flush=True)
                    continue
            except Exception:                                    # noqa: BLE001
                pass
        cmd = [sys.executable, "/root/train/train.py",
               "--data", "/data/sen1-2", "--out", out,
               "--epochs", str(epochs), "--batch", str(batch), "--workers", "4",
               "--sample-every", str(max(1, epochs // 2))] + extra
        if excl:
            cmd += ["--exclude", excl]
        print(f"\n===== {name} =====", flush=True)
        t0 = time.time()
        rc = subprocess.call(cmd)
        hist_p = os.path.join(out, "history.json")
        best = None
        if os.path.exists(hist_p):
            with open(hist_p, encoding="utf8") as fh:
                hist = json.load(fh)
            best = max(hist, key=lambda r: r["val_psnr"])
        results[name] = {
            "rc": rc, "minutes": round((time.time() - t0) / 60, 1),
            "psnr": round(best["val_psnr"], 3) if best else None,
            "ssim": round(best["val_ssim"], 4) if best else None,
            "epoch": best["epoch"] if best else None,
        }
        runs_vol.commit()
        print(f"  -> {results[name]}", flush=True)

    hrs = (time.time() - t_all) / 3600
    rate = RATE_USD_PER_HOUR.get(GPU, 1.0)
    print("\n================ ABLATION ================")
    print(f"{'variant':16s} {'PSNR':>7s} {'SSIM':>8s} {'min':>6s}")
    for k, v in results.items():
        print(f"{k:16s} {str(v['psnr']):>7s} {str(v['ssim']):>8s} {v['minutes']:>6.1f}")
    print(f"\ntotal {hrs:.2f} h on {GPU} ~= ${hrs*rate:.2f}")
    with open("/runs/abl/summary.json", "w", encoding="utf8") as fh:
        json.dump(results, fh, indent=2)
    runs_vol.commit()
    return results


@app.function(gpu=GPU, volumes={"/data": data_vol, "/runs": runs_vol},
              timeout=60 * 40)
def score_ablation(limit: int = 400, pattern: str = "best.pt"):
    """Score every ablation checkpoint with the CORRECT metrics, on GPU.

    Deliberately not reusing the numbers training logged: train.py tracks a
    global-statistics SSIM that is not the windowed 11x11 definition everyone else
    reports, and it flatters degraded images badly. This recomputes from the saved
    weights so the published table is comparable to other work.
    """
    import glob
    import json
    import subprocess
    import sys
    import time

    ck = sorted(glob.glob(f"/runs/abl/*/{pattern}"))
    if not ck:
        return {"ok": False, "reason": "no checkpoints under /runs/abl"}
    print(f"scoring {len(ck)} checkpoints", flush=True)
    t0 = time.time()
    # config.py resolves data paths from SIH_DATA; inside the container the volume
    # is mounted at /data, not the ~/sih-data default used on the dev machine
    env = dict(os.environ, SIH_DATA="/data")
    tag = pattern.replace(".pt", "")
    rc = subprocess.call([sys.executable, "/root/eval/metrics.py",
                          "--runs-dir", "/runs/abl", "--limit", str(limit),
                          "--pattern", pattern,
                          "--out-name", f"ablation_{tag}.json"], env=env)
    # metrics.py writes into the repo REPORTS dir inside the container; copy it out
    out = f"/root/reports/ablation_{tag}.json"
    alt = glob.glob(f"/root/**/ablation_{tag}.json", recursive=True)
    src = out if os.path.exists(out) else (alt[0] if alt else None)
    rows = json.loads(open(src, encoding="utf8").read()) if src else []
    with open(f"/runs/abl/metrics_{tag}.json", "w", encoding="utf8") as fh:
        json.dump(rows, fh, indent=2)
    runs_vol.commit()
    mins = (time.time() - t0) / 60
    print(f"scored in {mins:.1f} min on {GPU}")
    return {"ok": rc == 0, "minutes": round(mins, 2), "rows": rows}


@app.local_entrypoint()
def main(epochs: int = 40, batch: int = 32, do_prepare: bool = True):
    if do_prepare:
        n = prepare_data.remote()
        print(f"dataset ready: {n} pairs")
    excl = ""
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "reports", "exclude_scenes.txt")
    if os.path.exists(p):
        excl = open(p, encoding="utf8").read()
    print(train.remote(epochs=epochs, batch=batch, exclude=excl))
