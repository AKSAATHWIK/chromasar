"""Make TEAM_NOTES.md render on any machine, in any font.

Six people read this on six laptops on hackathon day, some of them in a terminal. The
file was valid UTF-8 the whole time - nothing was corrupted - but a font without the
glyph draws a tofu box, and a briefing you cannot read is worse than one you never wrote.
U+00A7 SECTION SIGN failed first; it is Latin-1, so anything rarer in the same file was
already failing too. So the fix is not "escape the section sign", it is "hold the whole
document to ASCII" and stop depending on the reader's font.

Nothing is lost: the arrows, dashes and Greek letters all have exact ASCII spellings.
Cross-references get MORE readable, not less - "Section 6a" beats a symbol nobody can
pronounce out loud when they are reading it to a teammate.

Structure is verified, not assumed: a naive character swap can turn a table cell into a
row separator or invent a horizontal rule, so the pipe count per line and the set of
all-dash lines are both compared before and after.

    python deck/asciify_notes.py            # rewrite in place
    python deck/asciify_notes.py --check    # report only, exit 1 if not ASCII
"""
from __future__ import annotations

import io
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "TEAM_NOTES.md"

#: Exact ASCII spellings. Every one of these is a straight transliteration - if a
#: replacement changed the meaning it would belong in the prose, not in this table.
CHARS = {
    "—": "-",        # em dash
    "–": "-",        # en dash
    "−": "-",        # minus sign
    "·": "-",        # middle dot, used once as a separator
    "→": "->",
    "←": "<-",
    "⟷": "<->",
    "≡": "==",       # "upload == benchmark"
    "²": "2",        # km2, m2/pixel - matches the ASCII "m2" already in the file
    "×": "x",        # 5.7x
    "λ": "lambda",   # lambda_gan
    "ρ": "rho",      # rho=0.897
}

#: Run before the generic rule so runs of references read as English.
PHRASES = [
    (re.compile(r"§(\d+[a-z]?), §(\d+[a-z]?) and §(\d+[a-z]?)"),
     r"Sections \1, \2 and \3"),
    (re.compile(r"§(\d+[a-z]?) and §(\d+[a-z]?)"), r"Sections \1 and \2"),
    (re.compile(r"§(\d+[a-z]?)"), r"Section \1"),
]


def convert(text: str) -> str:
    for pat, rep in PHRASES:
        text = pat.sub(rep, text)
    for src, dst in CHARS.items():
        text = text.replace(src, dst)
    return text


def structure(text: str):
    """The two things a character swap can silently wreck.

    Both dashes AND equals signs matter: a line of either underlines the line above it
    into a setext heading. Guarding only dashes would have been a blind spot, because
    U+2261 maps to "==" - a cell of those would quietly promote its neighbour to an H1.
    """
    lines = text.split("\n")
    pipes = [ln.count("|") for ln in lines]
    rules = {i for i, ln in enumerate(lines)
             if ln.strip() and (set(ln.strip()) <= set("-") or set(ln.strip()) <= set("="))}
    return len(lines), pipes, rules


def main() -> int:
    check = "--check" in sys.argv
    before = io.open(TARGET, encoding="utf8").read()
    after = convert(before)

    n0, p0, r0 = structure(before)
    n1, p1, r1 = structure(after)
    bad = []
    if n0 != n1:
        bad.append(f"line count changed {n0} -> {n1}")
    if p0 != p1:
        rows = [i + 1 for i, (a, b) in enumerate(zip(p0, p1)) if a != b]
        bad.append(f"table pipe count changed on lines {rows[:10]}")
    if r0 != r1:
        bad.append(f"horizontal-rule lines changed: {sorted(r1 - r0)} appeared, "
                   f"{sorted(r0 - r1)} vanished")

    left = sorted({c for c in after if ord(c) > 126})
    if left:
        bad.append("still non-ASCII: " + ", ".join(
            "U+%04X %s" % (ord(c), unicodedata.name(c, "?")) for c in left))

    if bad:
        print("REFUSING TO WRITE:")
        for b in bad:
            print("  -", b)
        return 1

    swapped = sum(before.count(c) for c in CHARS) + before.count("§")
    print(f"{swapped} non-ASCII characters -> ASCII")
    print(f"tables intact ({sum(1 for x in p0 if x)} piped lines), "
          f"{len(r0)} horizontal rules unchanged")

    if check:
        print("--check: not written")
        return 0
    io.open(TARGET, "w", encoding="utf8", newline="\n").write(after)
    print("wrote", TARGET.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
