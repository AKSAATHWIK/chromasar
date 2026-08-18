"""Build the single ZIP the hackathon asks you to upload.

    python submit.py 42

Produces 42.zip with everything inside a top-level folder named 42, because the brief
says "name the folder with just your team no" - a zip that explodes 180 loose files into
the marker's download directory is a bad first impression, and it is the first thing they
see of your work.

Deliberately EXCLUDED, with reasons, so nobody wonders whether it was an accident:
  node_modules/   346 MB of reinstallable dependencies
  .next/          114 MB of build output
  .git/           the whole history; the repo link is in README.md
  sih-data        never inside the project, but guarded in case someone copies it in
  *.pt            93.5 MB each; they are published as GitHub release assets

What ships is the source, the decks, the notes, and the demo inputs - which is what the
brief means by "all your files", and it stays small enough to actually upload over
conference wifi.
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SKIP_DIRS = {"node_modules", ".next", ".git", "__pycache__", ".pytest_cache",
             ".mypy_cache", ".ruff_cache", "venv", ".venv", "sih-data", "runs",
             "comparison", ".claude"}
SKIP_EXT = {".pt", ".pth", ".ckpt", ".pyc", ".zip"}


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        print("error: give your team number, e.g.  python submit.py 42")
        return 2
    team = sys.argv[1].strip().lstrip("#")
    out = ROOT / f"{team}.zip"

    files, skipped = [], 0
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT)
        if set(rel.parts) & SKIP_DIRS or p.suffix.lower() in SKIP_EXT:
            skipped += 1
            continue
        if p == out:
            continue
        files.append((p, rel))

    if not files:
        print("nothing to package - are you in the project root?")
        return 1

    total = sum(p.stat().st_size for p, _ in files)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p, rel in files:
            z.write(p, Path(team) / rel)          # everything under one named folder

    size = out.stat().st_size
    print(f"{out.name}  -  {len(files)} files, {total/1048576:.1f} MB "
          f"-> {size/1048576:.1f} MB zipped")
    print(f"  ({skipped} files skipped: dependencies, build output, git, checkpoints)")

    # The things a marker actually looks for. Say plainly if one is missing rather than
    # letting it be discovered after upload.
    want = ["README.md", "TEAM_NOTES.md", "ROUND1_FEEDBACK.md",
            "SIH2026-DeltaForce-SIH1733-IDEA-SUBMISSION.pptx",
            "SIH2026-DeltaForce-SIH1733-IDEA-SUBMISSION.pdf"]
    have = {str(r).replace("\\", "/") for _, r in files}
    print()
    for w in want:
        print(f"  {'ok  ' if w in have else 'MISSING'} {w}")
    print(f"\nupload {out.name} to the SharePoint link in the brief.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
