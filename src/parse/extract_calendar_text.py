#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-08.4
"""
The text beside every calendar PDF, so the parsers can read the archive.

    python3 src/parse/extract_calendar_text.py --check     # what is missing, extracts nothing
    python3 src/parse/extract_calendar_text.py            # extract every missing one
    python3 src/parse/extract_calendar_text.py --limit 50

No network. Reads and writes only calendars/, calendars_senate/, journals/
and journals_senate/.

WHY THIS IS A SEPARATE STEP

fetch_calendar_archive.py saves the PDF and nothing else, deliberately: a
fetch should do one thing, and a text extractor that runs inside it would be
one more reason for a fetch to fail part way through and leave the archive in
a state nobody can describe.

But calendar_meetings.py reads the .txt, not the .pdf. So a calendar with no
text beside it is on this disk and invisible -- which is exactly the failure
this project keeps naming, a step that produces nothing and exits zero. The
first 193 archived calendars landed that way.

WHAT IT USES

pdftotext -layout where poppler is installed, because the calendar is set in
columns and -layout is what keeps a time in the same line as its bill.
pdfplumber and pypdf are the fallbacks, and they are worse at exactly that,
so which one produced a file is recorded rather than left to be guessed at
when a parse looks wrong.

WHERE PDFTOTEXT IS (16 November 2026). Every one of the 3,257 texts on the
laptop was made by the pdftotext that Git for Windows installs beside git
(mingw64/bin), which a Git Bash shell has on its path and cmd and GitHub's
machine do not. pdftotext() looks there as well as on the path, so the night,
which extracts what it fetched (nightly.take_document_files), reads a
calendar with the same program the laptop's texts came from. --layout-only
is the night's: pdftotext -layout or no text at all, because every reader of
these texts was written against that program's columns, and a calendar read
another way would be read differently without anything saying so.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import json
import os
import shutil
import subprocess
import time
from collections import Counter

ROOTS = ["calendars", "calendars_senate", "journals", "journals_senate"]
LEDGER = Path("archive/extracted.json")
# Where Git for Windows keeps the pdftotext it installs, under the folder git
# is installed in: C:\Program Files\Git\mingw64\bin\pdftotext.exe.
GIT_PDFTOTEXT = ("mingw64/bin/pdftotext.exe", "usr/bin/pdftotext.exe")
LAYOUT = "pdftotext -layout"


def pdftotext():
    """The pdftotext to run: the one on the path, or else Git for Windows'
    beside git; None where there is neither."""
    found = shutil.which("pdftotext")
    if found:
        return found
    roots = []
    git = shutil.which("git")
    if git:
        here = Path(git).resolve()
        # git.exe is in Git\cmd, Git\bin or Git\mingw64\bin.
        roots += [here.parents[1], here.parents[2]] if len(here.parents) > 2 else []
    if os.environ.get("ProgramFiles"):
        roots.append(Path(os.environ["ProgramFiles"]) / "Git")
    for root in roots:
        for rel in GIT_PDFTOTEXT:
            if (root / rel).is_file():
                return str(root / rel)
    return None


def extract(pdf, layout_only=False):
    """(text, how) -- or (None, why not). With `layout_only`, pdftotext
    -layout's text or none: no other program's reading of the columns."""
    tool = pdftotext()
    if tool:
        try:
            out = subprocess.run([tool, "-layout", str(pdf), "-"],
                                 capture_output=True, text=True,
                                 encoding="utf-8", errors="replace", timeout=180)
            if out.returncode == 0 and (out.stdout or "").strip():
                return out.stdout, LAYOUT
            if layout_only:
                return None, f"pdftotext gave no text (exit {out.returncode})"
        except subprocess.TimeoutExpired:
            return None, "pdftotext timed out"
    elif layout_only:
        return None, "no pdftotext here"
    try:
        import pdfplumber
        with pdfplumber.open(pdf) as d:
            t = "\n".join(p.extract_text() or "" for p in d.pages)
        if t.strip():
            return t, "pdfplumber"
    except ImportError:
        pass
    except Exception as e:                                  # noqa: BLE001
        return None, f"pdfplumber: {type(e).__name__}"
    try:
        from pypdf import PdfReader
        t = "\n".join(p.extract_text() or "" for p in PdfReader(str(pdf)).pages)
        if t.strip():
            return t, "pypdf"
    except ImportError:
        return None, "no extractor installed"
    except Exception as e:                                  # noqa: BLE001
        return None, f"pypdf: {type(e).__name__}"
    return None, "no text came out"


def wanted():
    out = []
    for root in ROOTS:
        r = Path(root)
        if not r.exists():
            continue
        for pdf in sorted(r.rglob("*.pdf")):
            txt = pdf.with_suffix(".txt")
            if not txt.exists() or txt.stat().st_size == 0:
                out.append(pdf)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--layout-only", action="store_true",
                    help="pdftotext -layout's text or none, as the night extracts "
                         "what it fetched: a PDF it cannot read keeps no text")
    a = ap.parse_args()

    todo = wanted()
    have = sum(len(list(Path(r).rglob("*.txt"))) for r in ROOTS if Path(r).exists())
    pdfs = sum(len(list(Path(r).rglob("*.pdf"))) for r in ROOTS if Path(r).exists())
    print(f"{pdfs:,} PDFs, {have:,} with text beside them, {len(todo):,} without")
    if a.check or not todo:
        by = Counter(p.parts[0] + "/" + p.parts[1] for p in todo)
        for k, n in sorted(by.items()):
            print(f"  {k}: {n}")
        if a.check:
            print("\n  Nothing was extracted.")
        return 0

    if a.limit:
        todo = todo[:a.limit]
    ledger = {}
    if LEDGER.exists():
        try:
            ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        except ValueError:
            ledger = {}

    ok, bad, how = 0, [], Counter()
    t0 = time.time()
    tool = pdftotext()
    print(f"pdftotext: {tool or 'none here'}"
          + (", and only its -layout text is written" if a.layout_only else ""))
    for i, pdf in enumerate(todo, 1):
        text, note = extract(pdf, layout_only=a.layout_only)
        if text is None:
            bad.append((str(pdf), note))
            ledger[str(pdf)] = {"ok": False, "why": note}
            print(f"  ! {pdf}: {note}")
            continue
        pdf.with_suffix(".txt").write_text(text, encoding="utf-8")
        ledger[str(pdf)] = {"ok": True, "how": note, "chars": len(text)}
        how[note] += 1
        ok += 1
        if ok % 50 == 0:
            print(f"  {i}/{len(todo)}  {ok} extracted, "
                  f"{ok / max(1e-9, time.time() - t0) * 60:.0f}/min", flush=True)
    LEDGER.parent.mkdir(exist_ok=True)
    LEDGER.write_text(json.dumps(ledger, indent=1), encoding="utf-8")

    print(f"\n{ok:,} extracted in {time.time() - t0:.0f}s, {len(bad)} failed")
    for k, n in how.most_common():
        print(f"  {n:,} by {k}")
    for p, why in bad[:6]:
        print(f"  failed: {p} -- {why}")
    if bad:
        print("\nA PDF with no text in it is usually a scan. It stays on disk; "
              "nothing\nelse changes, and the parsers simply will not see it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
