"""Download the Sen1Floods11 hand-labelled subset from its public GCS bucket.

Gives us what SEN1-2 and SEN12MS cannot: Sentinel-1 VV+VH chips WITH hand-drawn flood
water masks, plus the matching Sentinel-2 optical. That means the flood module can be
scored against ground truth (IoU, precision, recall) instead of just producing maps that
look plausible - and the S2 chips let us run colorization on real flood scenes.

446 chips, ~1.75 GB, no authentication required.

    python download_floods.py --parts S1Hand LabelHand S2Hand
"""
import argparse
import json
import os
import sys
import queue
import threading
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import FLOODS_DIR                     # noqa: E402



BUCKET = "sen1floods11"
BASE = "v1.1/data/flood_events/HandLabeled"
SPLITS = "v1.1/splits/flood_handlabeled"
DEST = str(FLOODS_DIR)
API = f"https://storage.googleapis.com/storage/v1/b/{BUCKET}/o"
MEDIA = f"https://storage.googleapis.com/{BUCKET}"

_lock = threading.Lock()
_done = [0]
_bytes = [0]
_fail = [0]


def list_prefix(prefix):
    out, tok = [], None
    while True:
        u = f"{API}?prefix={prefix}&maxResults=1000"
        if tok:
            u += f"&pageToken={tok}"
        with urllib.request.urlopen(u, timeout=90) as r:
            d = json.load(r)
        out += [(i["name"], int(i["size"])) for i in d.get("items", [])]
        tok = d.get("nextPageToken")
        if not tok:
            return out


def fetch(name, dest_root, total):
    local = os.path.join(dest_root, *name.split("/")[-2:])
    os.makedirs(os.path.dirname(local), exist_ok=True)
    if os.path.exists(local) and os.path.getsize(local) > 0:
        with _lock:
            _done[0] += 1
        return
    url = f"{MEDIA}/{urllib.parse.quote(name)}"
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                data = r.read()
            tmp = local + ".part"
            with open(tmp, "wb") as fh:
                fh.write(data)
            os.replace(tmp, local)
            with _lock:
                _done[0] += 1
                _bytes[0] += len(data)
                if _done[0] % 100 == 0:
                    print(f"  {_done[0]}/{total}  {_bytes[0]/1e6:.0f} MB", flush=True)
            return
        except Exception as e:                                   # noqa: BLE001
            if attempt == 3:
                with _lock:
                    _fail[0] += 1
                print(f"  FAIL {name}: {e}", flush=True)
            time.sleep(2 * (attempt + 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", nargs="+",
                    default=["S1Hand", "LabelHand", "S2Hand"])
    ap.add_argument("--dest", default=DEST)
    ap.add_argument("--threads", type=int, default=16)
    args = ap.parse_args()
    os.makedirs(args.dest, exist_ok=True)

    objs = []
    for p in args.parts:
        got = list_prefix(f"{BASE}/{p}/")
        objs += [n for n, _ in got]
        print(f"{p}: {len(got)} files, {sum(s for _, s in got)/1e6:.0f} MB")
    # official train/val/test splits - use theirs so results are comparable
    for n, _ in list_prefix(SPLITS + "/"):
        objs.append(n)

    print(f"\ndownloading {len(objs)} objects with {args.threads} threads...")
    t0 = time.time()
    q = queue.Queue()
    for o in objs:
        q.put(o)

    def worker():
        while True:
            try:
                n = q.get_nowait()
            except queue.Empty:
                return
            try:
                fetch(n, args.dest, len(objs))
            finally:
                q.task_done()

    ts = [threading.Thread(target=worker, daemon=True) for _ in range(args.threads)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()

    print(f"\ndone in {(time.time()-t0)/60:.1f} min  "
          f"{_done[0]} ok, {_fail[0]} failed, {_bytes[0]/1e6:.0f} MB")
    for d in sorted(os.listdir(args.dest)):
        p = os.path.join(args.dest, d)
        if os.path.isdir(p):
            print(f"  {d}: {len(os.listdir(p))} files")


if __name__ == "__main__":
    main()
