"""Download a balanced subset of the SEN1-2 dataset over FTP.

SEN1-2 stores individual PNGs in per-scene folders, so we can pull exactly the number
of pairs we want instead of a 50 GB archive. Every SAR patch is only kept if its matching
optical patch also downloads, so the output set is always perfectly paired.

Usage:
    python download_sen12.py --pairs 10000
    python download_sen12.py --pairs 10000 --dest D:/sih-data/sen1-2
Resumable: re-running skips files already on disk.
"""
import argparse
import ftplib
import os
import queue
import random
import sys
import threading
import time

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from config import SEN12_DIR


HOST = "dataserv.ub.tum.de"
USER = PASS = "m1436631"
SEASONS = ["ROIs1158_spring", "ROIs1868_summer", "ROIs1970_fall", "ROIs2017_winter"]
DEFAULT_DEST = str(SEN12_DIR)

_print_lock = threading.Lock()
_stats = {"ok": 0, "skip": 0, "fail": 0, "bytes": 0}


def log(msg):
    with _print_lock:
        print(msg, flush=True)


def connect(retries=5):
    last = None
    for a in range(retries):
        try:
            ftp = ftplib.FTP(HOST, timeout=60)
            ftp.login(USER, PASS)
            ftp.set_pasv(True)
            return ftp
        except Exception as e:                                    # noqa: BLE001
            last = e
            time.sleep(2 * (a + 1))
    raise RuntimeError(f"FTP connect failed after {retries} tries: {last}")


def listdir(ftp, path):
    try:
        return ftp.nlst(path)
    except ftplib.error_perm:
        return []


def plan(pairs_wanted, seed=1733):
    """Choose which patches to fetch, balanced across seasons and scenes."""
    rng = random.Random(seed)
    ftp = connect()
    per_season = pairs_wanted // len(SEASONS)
    jobs = []

    for season in SEASONS:
        scenes = [os.path.basename(p) for p in listdir(ftp, season)
                  if os.path.basename(p).startswith("s1_")]
        if not scenes:
            log(f"  !! no scenes found in {season}")
            continue
        rng.shuffle(scenes)

        got, si = 0, 0
        # spread the quota across as many distinct scenes as possible
        per_scene = max(20, per_season // max(1, min(len(scenes), 40)))
        while got < per_season and si < len(scenes):
            scene = scenes[si]
            si += 1
            files = [os.path.basename(f) for f in
                     listdir(ftp, f"{season}/{scene}") if f.endswith(".png")]
            if not files:
                continue
            rng.shuffle(files)
            take = files[:min(per_scene, per_season - got)]
            idx = scene.split("_", 1)[1]
            for fn in take:
                # ROIs1158_spring_s1_0_p1000.png -> ROIs1158_spring_s2_0_p1000.png
                s2_fn = fn.replace("_s1_", "_s2_", 1)
                jobs.append((f"{season}/{scene}/{fn}",
                             f"{season}/s2_{idx}/{s2_fn}",
                             season, fn, s2_fn))
            got += len(take)
        log(f"  {season}: planned {got} pairs across {si} scenes")

    ftp.quit()
    rng.shuffle(jobs)
    return jobs


def fetch(ftp, remote, local):
    tmp = local + ".part"
    with open(tmp, "wb") as fh:
        ftp.retrbinary(f"RETR {remote}", fh.write, blocksize=65536)
    size = os.path.getsize(tmp)
    if size == 0:
        os.remove(tmp)
        raise IOError("empty file")
    os.replace(tmp, local)
    return size


def worker(q, dest, total):
    ftp = connect()
    consecutive_fail = 0
    while True:
        try:
            job = q.get_nowait()
        except queue.Empty:
            break
        s1_remote, s2_remote, season, s1_fn, s2_fn = job
        s1_local = os.path.join(dest, "s1", s1_fn)
        s2_local = os.path.join(dest, "s2", s2_fn)
        try:
            if os.path.exists(s1_local) and os.path.exists(s2_local):
                _stats["skip"] += 1
            else:
                # only keep the SAR patch if its optical partner also arrives
                n1 = fetch(ftp, s1_remote, s1_local) if not os.path.exists(s1_local) else 0
                try:
                    n2 = fetch(ftp, s2_remote, s2_local) if not os.path.exists(s2_local) else 0
                except Exception:                                 # noqa: BLE001
                    if os.path.exists(s1_local):
                        os.remove(s1_local)
                    raise
                _stats["ok"] += 1
                _stats["bytes"] += n1 + n2
            consecutive_fail = 0
        except Exception as e:                                    # noqa: BLE001
            _stats["fail"] += 1
            consecutive_fail += 1
            if consecutive_fail >= 3:
                try:
                    ftp.quit()
                except Exception:                                 # noqa: BLE001
                    pass
                try:
                    ftp = connect()
                    consecutive_fail = 0
                except Exception:                                 # noqa: BLE001
                    break
            if _stats["fail"] <= 10:
                log(f"  fail {s1_fn}: {e}")
        finally:
            q.task_done()

        done = _stats["ok"] + _stats["skip"] + _stats["fail"]
        if done % 250 == 0:
            gb = _stats["bytes"] / 1e9
            log(f"  [{done}/{total}] ok={_stats['ok']} skip={_stats['skip']} "
                f"fail={_stats['fail']} {gb:.2f} GB")
    try:
        ftp.quit()
    except Exception:                                             # noqa: BLE001
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", type=int, default=10000)
    ap.add_argument("--dest", default=DEFAULT_DEST)
    ap.add_argument("--threads", type=int, default=8)
    args = ap.parse_args()

    os.makedirs(os.path.join(args.dest, "s1"), exist_ok=True)
    os.makedirs(os.path.join(args.dest, "s2"), exist_ok=True)

    log(f"Planning {args.pairs} pairs -> {args.dest}")
    t0 = time.time()
    jobs = plan(args.pairs)
    log(f"Planned {len(jobs)} pairs in {time.time() - t0:.0f}s. "
        f"Downloading with {args.threads} threads...")

    q = queue.Queue()
    for j in jobs:
        q.put(j)

    threads = [threading.Thread(target=worker, args=(q, args.dest, len(jobs)), daemon=True)
               for _ in range(args.threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    n1 = len(os.listdir(os.path.join(args.dest, "s1")))
    n2 = len(os.listdir(os.path.join(args.dest, "s2")))
    mins = (time.time() - t0) / 60
    log(f"\nDone in {mins:.1f} min. ok={_stats['ok']} skip={_stats['skip']} "
        f"fail={_stats['fail']}  {_stats['bytes'] / 1e9:.2f} GB")
    log(f"On disk: {n1} SAR patches, {n2} optical patches")
    if n1 != n2:
        log("WARNING: counts differ - run verify_pairs.py before training")


if __name__ == "__main__":
    sys.exit(main())
