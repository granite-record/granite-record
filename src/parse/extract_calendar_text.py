#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-08.3
"""
The text beside every calendar PDF, so the parsers can read the archive.

    python3 src/parse/extract_calendar_text.py --check     # what is missing, extracts nothing
    python3 src/parse/extract_calendar_text.py            # extract every missing one
    python3 src/parse/extract_calendar_text.py --limit 50
    python3 src/parse/extract_calendar_text.py --only A.pdf --into A.txt   # one PDF, by pdftotext alone
    python3 src/parse/extract_calendar_text.py --canary tests/documents   # does this machine make the laptop's text?

No network. Reads and writes only calendars/, calendars_senate/, journals/
and journals_senate/ -- and, for --only, the one PDF and the one text it
is given; for --canary, it reads the folder it is given and writes nothing.

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
when a parse looks wrong. On GitHub's night the pdftotext is the pinned one
nightly.yml installs and names in GRANITE_PDFTOTEXT, and no other (pdftotext()).

FOR GITHUB'S NIGHT (the person's design of 26 October 2026)

From the handover the night makes the text of the calendars and journals it
fetches, on its own machine (nightly.make_texts). Two things here exist for
that:

  --only PDF --into TXT  the text of that one PDF, wherever it is, written to
                   TXT and nowhere else, by pdftotext alone -- the pinned one
                   on GitHub's machine; no fallback, which sets a calendar's
                   columns its own way. The night makes each text so, in
                   scratch, and checks it before it goes in its folder. Exit 1
                   when no text came of it. The extractor's own 180 seconds
                   for one PDF stand, so one that stalls costs only itself
  --canary DIR     whether this machine makes the laptop's text of the
                   person's fixtures (tests/documents/ and its README): PDFs,
                   each with the .txt the laptop made from it. Exit 0 only
                   when there is at least one such pair, nothing in DIR is
                   unpaired, and every PDF's text is the laptop's, line for
                   line. Anything else is "not proved", and the night asks for
                   no document: no fixtures is not a pass

LINE FOR LINE, NOT BYTE FOR BYTE AT THE LINE ENDS. A text is written in this
machine's text mode, as it always has been: the laptop's with Windows' line
ends, the night's with Linux's. Every parser reads them the same, so the
canary compares the text, each side read with any line end, and a single
other byte is a difference.

A TEXT IS WRITTEN WHOLE: a part file, then a rename (write_text). It was
written in place, so a run killed part way could leave half a text, which
wanted() would then count as done and every parser read as the whole calendar.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import json
import os
import re
import shutil
import subprocess
import time
from collections import Counter

import refusal

ROOTS = ["calendars", "calendars_senate", "journals", "journals_senate"]
LEDGER = Path("archive/extracted.json")

# THE PINNED PDFTOTEXT, AND ONLY IT, ON GITHUB'S NIGHT. nightly.yml's pin step
# names the binary it installed, checked against its sha256, in this
# variable. Where it is set that binary is the one run, and no other; on
# GitHub's machine where it is not set, none is. Another pdftotext on that
# machine's PATH could make the same text of four small fixtures and still
# set another calendar's columns its own way, and the canary would have
# proved the wrong program.
PDFTOTEXT_ENV = "GRANITE_PDFTOTEXT"
VERSION_RE = re.compile(r"pdftotext version [0-9][0-9A-Za-z.-]*")


def pdftotext():
    """The pdftotext this runs, or None: the one PDFTOTEXT_ENV names, if it is
    a file; else none on GitHub's machine; else whichever is on PATH (the
    laptop's, as before)."""
    pinned = os.environ.get(PDFTOTEXT_ENV, "").strip()
    if pinned:
        return pinned if Path(pinned).is_file() else None
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return None
    return shutil.which("pdftotext")


def version_of(said):
    """"pdftotext version 26.09.0" from what `pdftotext -v` prints, or ""."""
    m = VERSION_RE.search(said or "")
    return m.group(0) if m else ""


def pdftotext_version():
    """What the pdftotext this runs says it is (`-v`, on stderr), or ""."""
    exe = pdftotext()
    if not exe:
        return ""
    try:
        out = subprocess.run([exe, "-v"], capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=30)
    except (OSError, subprocess.SubprocessError):
        return ""
    return version_of((out.stderr or "") + (out.stdout or ""))


def extract(pdf, fallback=True):
    """(text, how) -- or (None, why not). `fallback`: pdfplumber, then pypdf,
    where pdftotext gives nothing; --only gives none, and a PDF pdftotext
    makes no text of has none."""
    exe = pdftotext()
    if exe:
        try:
            out = subprocess.run([exe, "-layout", str(pdf), "-"],
                                 capture_output=True, text=True,
                                 encoding="utf-8", errors="replace", timeout=180)
            if out.returncode == 0 and (out.stdout or "").strip():
                return out.stdout, "pdftotext -layout"
        except subprocess.TimeoutExpired:
            return None, "pdftotext timed out"
    if not fallback:
        return None, ("pdftotext made no text of it" if exe else
                      "no pdftotext here" + (" (on GitHub's machine, only the pinned one runs)"
                                             if os.environ.get("GITHUB_ACTIONS") == "true" else ""))
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
    """Every PDF with no text beside it -- but none of a year handed to GitHub's
    night (refusal.night_years): from the handover the night makes those texts,
    with its pinned pdftotext, and pull brings them here."""
    y = refusal.night_years()
    out = []
    for root in ROOTS:
        r = Path(root)
        if not r.exists():
            continue
        for pdf in sorted(r.rglob("*.pdf")):
            if refusal.handed(pdf.relative_to(r).parts[0], y):
                continue
            txt = pdf.with_suffix(".txt")
            if not txt.exists() or txt.stat().st_size == 0:
                out.append(pdf)
    return out


def write_text(path, text):
    """A text file, whole: a part file beside it, then a rename over it, in
    this machine's text mode as every text here has been written."""
    path = Path(path)
    part = path.with_name(path.name + ".part")
    part.write_text(text, encoding="utf-8")
    os.replace(part, path)


def _first_difference(a, b):
    """The first line, counted from 1, on which two texts differ."""
    la, lb = a.split("\n"), b.split("\n")
    for i, (x, y) in enumerate(zip(la, lb), 1):
        if x != y:
            return i
    return min(len(la), len(lb)) + 1


def canary(folder):
    """(proved, sentence): whether this machine makes, from each PDF in
    `folder`, the text the laptop made from it, line for line.

    FAILS CLOSED. No pair at all, a PDF without its text or a text without
    its PDF, a PDF that yields nothing here, and one character of difference
    are each "not proved", and the night then asks for no document. Every
    pair is read, so the sentence says how many agreed and where the first
    that did not first differs. Files that are neither a PDF nor a text --
    the folder's README -- are not fixtures."""
    folder = Path(folder)
    if not folder.is_dir():
        return False, f"not proved: {folder.as_posix()} is not a folder"
    files = [p for p in sorted(folder.iterdir()) if p.is_file()]
    pdfs = [p for p in files if p.suffix.lower() == ".pdf"]
    txts = [p for p in files if p.suffix.lower() == ".txt"]
    lone = [p.name for p in pdfs if p.with_suffix(".txt") not in txts] + \
           [p.name for p in txts if p.with_suffix(".pdf") not in pdfs]
    pairs = [(p, p.with_suffix(".txt")) for p in pdfs if p.with_suffix(".txt") in txts]
    if not pairs:
        return False, (f"not proved: {folder.as_posix()} holds no PDF with the laptop's text "
                       "beside it")
    if lone:
        return False, f"not proved: {', '.join(lone)} in {folder.as_posix()} has no pair"
    same, first, how = 0, "", Counter()
    for pdf, txt in pairs:
        text, note = extract(pdf)
        if text is None:
            first = first or f"{pdf.name} gave no text here ({note})"
            continue
        how[note] += 1
        # Each side read with any line end (the docstring's LINE FOR LINE):
        # what extract() returns came through text mode already.
        theirs = txt.read_text(encoding="utf-8", errors="replace")
        if text == theirs:
            same += 1
        elif not first:
            first = f"{pdf.name} differs from line {_first_difference(text, theirs)}, by {note}"
    by = ", ".join(how) or "no extractor"
    # Which pdftotext, by its own word, so that the verdict says the version
    # it proved, or failed to.
    ver = pdftotext_version()
    ver = f"; {ver}" if ver else "; no pdftotext here"
    if same == len(pairs):
        return True, f"identical for {same} of {len(pairs)}, by {by}{ver}"
    return False, (f"not proved: identical for {same} of {len(pairs)}; the first that is not: "
                   f"{first}{ver}")


def read_ledger(path):
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def write_ledger(path, ledger):
    """The ledger, whole: what it held with this run's entries laid over."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    merged = read_ledger(path)
    merged.update(ledger)
    part = path.with_name(path.name + ".part")
    part.write_text(json.dumps(merged, indent=1), encoding="utf-8")
    os.replace(part, path)


def only(pdf, into):
    """--only PDF --into TXT: 0 when the PDF's text, by pdftotext alone, is
    at TXT; 1, with nothing written there, when it is not."""
    pdf, into = Path(pdf), Path(into)
    if pdf.suffix.lower() != ".pdf" or not pdf.is_file():
        print(f"  ! {pdf.as_posix()}: not a PDF on this disk")
        return 1
    text, note = extract(pdf, fallback=False)
    if text is None:
        print(f"  ! {pdf.as_posix()}: {note}")
        return 1
    into.parent.mkdir(parents=True, exist_ok=True)
    write_text(into, text)
    print(f"  {pdf.as_posix()} -> {into.as_posix()}: {len(text):,} characters, by {note}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", metavar="PDF",
                    help="the text of this one PDF, wherever it is, by pdftotext alone; "
                         "written to --into")
    ap.add_argument("--into", metavar="TXT", help="(--only) where its text is written, whole")
    ap.add_argument("--canary", metavar="DIR",
                    help="exit 0 only if this machine makes, from each PDF in DIR, the text "
                         "beside it, line for line; extracts nothing anywhere")
    a = ap.parse_args()
    if bool(a.only) != bool(a.into):
        ap.error("--only and --into go together: one PDF, and where its text is written")
    if (a.only or a.canary) and (a.check or a.limit or (a.only and a.canary)):
        ap.error("--only and --canary each stand alone: no --check, --limit, or each other")
    if a.canary:
        proved, said = canary(a.canary)
        print(f"text canary: {said}")
        return 0 if proved else 1
    if a.only:
        return only(a.only, a.into)

    y = refusal.night_years()
    if y is not None:
        print(f"No text is made here for those years: {refusal.years_said(y)}")
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

    ok, bad, how = 0, [], Counter()
    t0 = time.time()
    for i, pdf in enumerate(todo, 1):
        text, note = extract(pdf)
        if text is None:
            bad.append((str(pdf), note))
            ledger[str(pdf)] = {"ok": False, "why": note}
            print(f"  ! {pdf}: {note}")
            continue
        write_text(pdf.with_suffix(".txt"), text)
        ledger[str(pdf)] = {"ok": True, "how": note, "chars": len(text)}
        how[note] += 1
        ok += 1
        if ok % 50 == 0:
            print(f"  {i}/{len(todo)}  {ok} extracted, "
                  f"{ok / max(1e-9, time.time() - t0) * 60:.0f}/min", flush=True)
    write_ledger(LEDGER, ledger)

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
