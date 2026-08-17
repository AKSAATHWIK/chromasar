"""Single source of truth for where data lives.

Every script imported a hardcoded absolute path under one developer's profile, which
meant nobody else on the team could run any of it. Paths now resolve in this order:

    1. the --dest / --data flag, if given
    2. the SIH_DATA environment variable
    3. ~/sih-data

If your data sits at `%USERPROFILE%\\sih-data` you need to set nothing at all - that is
already the default. Only set the variable when the data lives somewhere else:

    Windows (this shell):  $env:SIH_DATA = "D:\\sih-data"
    Windows (persistent):  setx SIH_DATA "D:\\sih-data"     # NOT this shell - open a new one
    Linux / macOS:         export SIH_DATA=~/sih-data

Point it at a folder that does not exist and you are worse off than leaving it unset,
because a set-but-wrong value overrides the working default. `python migrate.py check`
tells you which root resolved and whether everything it needs is actually there.

Data deliberately lives OUTSIDE the OneDrive-synced project folder - several GB of
training patches inside a synced directory triggers a very unhappy upload.
"""
from __future__ import annotations

import os
from pathlib import Path

# repo layout ---------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
REPORTS = PROJECT_ROOT / "reports"

# data layout ---------------------------------------------------------------
DATA_ROOT = Path(os.environ.get("SIH_DATA") or (Path.home() / "sih-data")).resolve()

SEN12_DIR = DATA_ROOT / "sen1-2"          # SEN1-2 paired PNG patches
SEN12MS_DIR = DATA_ROOT / "sen12ms"       # SEN12MS season archives (VV+VH, land cover)
FLOODS_DIR = DATA_ROOT / "sen1floods11"   # Sen1Floods11 chips + hand labels
RUNS_DIR = DATA_ROOT / "runs"             # training checkpoints and samples

EXCLUDE_FILE = REPORTS / "exclude_scenes.txt"


def ensure(*paths):
    for p in paths:
        Path(p).mkdir(parents=True, exist_ok=True)
    return paths[0] if len(paths) == 1 else paths


def describe():
    lines = [f"SIH_DATA      {DATA_ROOT}"
             f"{'  (from env)' if os.environ.get('SIH_DATA') else '  (default)'}"]
    for name, p in [("SEN1-2", SEN12_DIR), ("SEN12MS", SEN12MS_DIR),
                    ("Sen1Floods11", FLOODS_DIR), ("runs", RUNS_DIR)]:
        mark = "ok " if Path(p).exists() else "-- "
        lines.append(f"  {mark}{name:14s} {p}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(describe())
