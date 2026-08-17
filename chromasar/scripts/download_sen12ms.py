"""Download SEN12MS season archives over FTP, with resume.

SEN12MS gives us what SEN1-2 cannot: VV+VH polarisation (for the polarimetric encoding)
and MODIS land-cover maps (for the terrain-conditioning prior). Archives are large, so
this resumes with FTP REST rather than restarting on a dropped connection.

    python download_sen12ms.py --season winter --parts s1 s2 lc
"""
import argparse
import ftplib
import os
import sys
import time

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from config import SEN12MS_DIR


HOST = "dataserv.ub.tum.de"
USER = PASS = "m1474000"
DEST = str(SEN12MS_DIR)

SEASONS = {
    "spring": "ROIs1158_spring",
    "summer": "ROIs1868_summer",
    "fall": "ROIs1970_fall",
    "winter": "ROIs2017_winter",
}


def connect():
    ftp = ftplib.FTP(HOST, timeout=180)
    ftp.login(USER, PASS)
    ftp.set_pasv(True)
    return ftp


def remote_size(ftp, name):
    """SIZE is refused in ASCII mode by many servers, which silently kills the ETA."""
    try:
        ftp.voidcmd("TYPE I")
    except Exception:                                            # noqa: BLE001
        pass
    try:
        n = ftp.size(name)
        if n:
            return n
    except Exception:                                            # noqa: BLE001
        pass
    # fall back to parsing the directory listing
    try:
        rows = []
        ftp.dir(rows.append)
        for r in rows:
            parts = r.split()
            if parts and parts[-1] == name:
                return int(parts[4])
    except Exception:                                            # noqa: BLE001
        pass
    return None


def fetch(name, dest, max_retries=12):
    path = os.path.join(dest, name)
    for attempt in range(max_retries):
        ftp = None
        try:
            ftp = connect()
            total = remote_size(ftp, name)
            have = os.path.getsize(path) if os.path.exists(path) else 0
            if total and have >= total:
                print(f"  {name}: complete ({have/1e9:.2f} GB)", flush=True)
                return True
            mode = "ab" if have else "wb"
            if have:
                print(f"  {name}: resuming at {have/1e9:.2f} / "
                      f"{(total or 0)/1e9:.2f} GB (attempt {attempt+1})", flush=True)
            else:
                print(f"  {name}: starting, {(total or 0)/1e9:.2f} GB", flush=True)

            t0 = time.time()
            got = [have]
            last = [time.time()]

            def cb(block, fh):
                fh.write(block)
                got[0] += len(block)
                now = time.time()
                if now - last[0] > 30:
                    last[0] = now
                    el = now - t0
                    rate = (got[0] - have) / 1e6 / max(el, 1e-9)
                    pct = 100 * got[0] / total if total else 0
                    eta = ((total - got[0]) / 1e6 / rate / 60) if (total and rate > 0) else 0
                    print(f"    {name}: {got[0]/1e9:6.2f} GB ({pct:5.1f}%) "
                          f"{rate:5.2f} MB/s  ETA {eta:5.1f} min", flush=True)

            with open(path, mode) as fh:
                ftp.retrbinary(f"RETR {name}", lambda b: cb(b, fh),
                               blocksize=1 << 20, rest=have if have else None)
            print(f"  {name}: done, {os.path.getsize(path)/1e9:.2f} GB", flush=True)
            return True
        except Exception as e:                                   # noqa: BLE001
            print(f"  {name}: error ({e}) - retrying in 15s", flush=True)
            time.sleep(15)
        finally:
            if ftp:
                try:
                    ftp.quit()
                except Exception:                                # noqa: BLE001
                    pass
    print(f"  {name}: FAILED after {max_retries} attempts", flush=True)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", default="winter", choices=list(SEASONS))
    ap.add_argument("--parts", nargs="+", default=["lc", "s1", "s2"],
                    choices=["lc", "s1", "s2"])
    ap.add_argument("--dest", default=DEST)
    args = ap.parse_args()
    os.makedirs(args.dest, exist_ok=True)

    roi = SEASONS[args.season]
    # smallest first so something useful lands early
    order = {"lc": 0, "s1": 1, "s2": 2}
    parts = sorted(args.parts, key=lambda p: order[p])
    t0 = time.time()
    ok = True
    for p in parts:
        ok &= fetch(f"{roi}_{p}.tar.gz", args.dest)
    print(f"\n{'all archives present' if ok else 'SOME DOWNLOADS FAILED'} "
          f"in {(time.time()-t0)/60:.1f} min")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
