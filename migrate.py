"""Move ChromaSAR to the demo laptop, and prove it will run there.

The project folder is 31 MB and clones from GitHub. The part that does NOT clone is
the corpus at $SIH_DATA - 57 GB of it - and, critically, the two 93.5 MB model
checkpoints that live inside it. Copy only the repo and you get a backend that starts,
a UI that renders, a scene list that populates from the dataset, and a 503 on the first
inference click. That failure is invisible until a judge is watching, which is why this
script exists instead of a paragraph in a README.

You do not need 57 GB. The demo reads three things; the other 50.5 GB is training-only.

    python migrate.py pack E:\\            # on THIS laptop: copy the ~3.4 GB it needs
    python migrate.py check                # on EITHER: is this machine demo-ready?

`check` is the one that matters. Run it on the demo laptop with the wifi OFF, and it
answers the only question worth asking the morning of the 19th: will this work.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import os
import shutil
import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent

#: Same rule as chromasar/config.py:29 - env var wins, else ~/sih-data. Duplicated
#: rather than imported so `check` still runs on a machine where the deps are missing,
#: which is exactly the machine you most need to run it on.
def data_root() -> Path:
    return Path(os.environ.get("SIH_DATA") or (Path.home() / "sih-data")).resolve()


#: (relative path, why). Everything the running demo actually reads, and nothing else.
NEEDED = [
    ("checkpoints/flood_resnet34.pt", "flood segmentation weights - /flood is dead without it"),
    ("checkpoints/colorization.pt", "colour generator weights - /color and /change"),
    ("sen1floods11", "446 benchmark chips; the scene list is built by globbing S1Hand/"),
    ("sen1-2", "SAR-optical pairs for the colorization workspace"),
]

#: Deliberately left behind, with the reason - so nobody 'helpfully' copies them.
SKIPPED = [
    ("sen12ms", "~50 GB. Land-cover conditioning is roadmap, not wired. Never read at demo time"),
    ("runs", "~1.6 GB of training logs and intermediate epochs"),
    ("checkpoints/backup-pre-sharpen", "superseded weights, kept only as a rollback on the build box"),
    ("checkpoints/sharpen", "the retrain's raw output; colorization.pt is the copy that ships"),
]

REQUIRED_IMPORTS = [
    ("numpy", "arrays"), ("torch", "inference"), ("torchvision", "ResNet34 encoder"),
    ("tifffile", "GeoTIFF"), ("imagecodecs", "compressed TIFF"), ("PIL", "images"),
    ("fastapi", "backend"), ("uvicorn", "ASGI server"), ("multipart", "file uploads"),
    ("matplotlib", "reports"),
]


def size_of(p: Path) -> int:
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:,.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def sha256(p: Path, cap: int = 64 << 20) -> str:
    """Hash the first 64 MB. Enough to catch a truncated or corrupt USB copy without
    spending minutes re-reading gigabytes; size is checked separately and exactly."""
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        while len(h.digest()) and (chunk := fh.read(1 << 20)):
            h.update(chunk)
            cap -= len(chunk)
            if cap <= 0:
                break
    return h.hexdigest()[:16]


def copy_tree(src: Path, dst: Path, done: list) -> None:
    """Copy with progress. shutil.copytree gives no feedback, and silence for four
    minutes on a 1.6 GB tree reads as a hang."""
    files = [f for f in src.rglob("*") if f.is_file()] if src.is_dir() else [src]
    total = sum(f.stat().st_size for f in files)
    moved, t0, last = 0, time.time(), 0.0
    for f in files:
        rel = f.relative_to(src) if src.is_dir() else Path(f.name)
        out = (dst / rel) if src.is_dir() else dst
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists() and out.stat().st_size == f.stat().st_size:
            moved += f.stat().st_size            # resumable: skip what already matches
        else:
            shutil.copy2(f, out)
            moved += f.stat().st_size
        if time.time() - last > 0.5:
            pct = 100 * moved / max(total, 1)
            rate = moved / max(time.time() - t0, 1e-9)
            print(f"\r    {pct:5.1f}%  {human(moved)} / {human(total)}  "
                  f"({human(rate)}/s)   ", end="", flush=True)
            last = time.time()
    print(f"\r    100.0%  {human(total)}  in {time.time() - t0:.0f}s"
          f"{' ' * 20}")
    done.append((str(src.name), total, len(files)))


def pack(dest_arg: str) -> int:
    src_root = data_root()
    if not src_root.exists():
        print(f"source data root not found: {src_root}")
        print("Set SIH_DATA to where sih-data actually lives, then re-run.")
        return 1
    dest = Path(dest_arg).resolve()
    if dest.drive and dest == Path(dest.drive + "\\").resolve():
        dest = dest / "sih-data"                 # `migrate.py pack E:\` -> E:\sih-data
    print(f"source : {src_root}")
    print(f"target : {dest}\n")

    need = [(src_root / rel, rel, why) for rel, why in NEEDED]
    absent = [rel for p, rel, _ in need if not p.exists()]
    if absent:
        print("MISSING on this machine, cannot pack:")
        for rel in absent:
            print("  -", rel)
        return 1

    total = sum(size_of(p) for p, _, _ in need)
    free = shutil.disk_usage(dest.parent if dest.parent.exists() else dest.anchor).free
    print(f"to copy: {human(total)}   free at target: {human(free)}")
    if free < total * 1.05:
        print("NOT ENOUGH SPACE at the target. Aborting before writing anything.")
        return 1
    skipped_bytes = sum(size_of(src_root / r) for r, _ in SKIPPED if (src_root / r).exists())
    print(f"skipping {human(skipped_bytes)} of training-only data\n")

    dest.mkdir(parents=True, exist_ok=True)
    done, manifest = [], {}
    for p, rel, why in need:
        print(f"  {rel}  ({why})")
        copy_tree(p, dest / rel, done)
        if p.is_file():
            manifest[rel] = {"bytes": p.stat().st_size, "sha256_head": sha256(p)}

    # Verify the checkpoints byte-for-byte-ish. A truncated .pt still loads far enough
    # to look plausible and then fails inside the model, which is the worst way to find
    # out that a USB copy went wrong.
    print("\nverifying checkpoints:")
    ok = True
    for rel, meta in manifest.items():
        out = dest / rel
        good = out.exists() and out.stat().st_size == meta["bytes"] and sha256(out) == meta["sha256_head"]
        print(f"  {'OK  ' if good else 'BAD '} {rel}  {human(meta['bytes'])}")
        ok &= good
    (dest / "MANIFEST.json").write_text(
        json.dumps({"packed_from": str(src_root), "files": manifest,
                    "trees": [{"name": n, "bytes": b, "files": c} for n, b, c in done]},
                   indent=2), encoding="utf8")

    print(f"\n{'done' if ok else 'FINISHED WITH ERRORS'} - {human(sum(b for _, b, _ in done))} at {dest}")
    print("\nOn the demo laptop:")
    print(f'  1. copy this folder to that machine (anywhere), then set SIH_DATA to it')
    print(f'  2. python migrate.py check')
    return 0 if ok else 1


def check() -> int:
    rows, fatal = [], 0

    def row(ok, label, detail=""):
        nonlocal fatal
        rows.append(("PASS" if ok else "FAIL", label, detail))
        if not ok:
            fatal += 1

    v = sys.version_info
    row(v >= (3, 9), f"python {v.major}.{v.minor}.{v.micro}", "need >= 3.9")

    for mod, why in REQUIRED_IMPORTS:
        try:
            importlib.import_module(mod)
            row(True, f"import {mod}", why)
        except Exception as e:
            row(False, f"import {mod}", f"{why} - {type(e).__name__}. "
                                        f"pip install -r chromasar/requirements.txt")

    dr = data_root()
    src = "SIH_DATA" if os.environ.get("SIH_DATA") else "default ~/sih-data"
    row(dr.exists(), f"data root ({src})", str(dr))
    for rel, why in NEEDED:
        p = dr / rel
        row(p.exists(), f"  {rel}", (human(size_of(p)) if p.exists() else "MISSING - " + why))

    nm = ROOT / "frontend" / "node_modules"
    row(nm.exists(), "frontend/node_modules",
        human(size_of(nm)) if nm.exists() else "MISSING - run `npm install` in frontend/ WITH INTERNET")
    row(shutil.which("node") is not None, "node on PATH",
        shutil.which("node") or "install Node 20+")

    port = int(os.environ.get("CHROMASAR_PORT", "8000"))
    for p, what in ((port, "backend"), (3000, "frontend")):
        s = socket.socket()
        s.settimeout(0.4)
        busy = s.connect_ex(("127.0.0.1", p)) == 0
        s.close()
        row(not busy, f"port {p} free ({what})",
            "IN USE - set CHROMASAR_PORT to something else" if busy else "")

    w = max(len(r[1]) for r in rows)
    print()
    for status, label, detail in rows:
        print(f"  [{status}] {label:<{w}}  {detail}")
    print()
    if fatal:
        print(f"{fatal} problem(s). This machine is NOT ready - fix the FAILs above.")
    else:
        print("READY. Now do the real test: turn the wifi OFF, start both servers,")
        print("and click through flood -> change -> color -> method with one upload.")
    return 1 if fatal else 0


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "pack" and len(sys.argv) > 2:
        return pack(sys.argv[2])
    if cmd == "check":
        return check()
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
