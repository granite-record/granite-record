#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-08.3
"""
The text beside every calendar PDF, so the parsers can read the archive.

    python3 src/parse/extract_calendar_text.py --check     # what is missing, extracts nothing
    python3 src/parse/extract_calendar_text.py            # extract every missing one
    python3 src/parse/extract_calendar_text.py --limit 50
    python3 src/parse/extract_calendar_text.py --only calendars/2026/HC036.pdf --ledger .night/extracted.json
    python3 src/parse/extract_calendar_text.py --canary tests/documents   # does this machine make the laptop's text?

No network. Reads and writes only calendars/, calendars_senate/, journals/
and journals_senate/ -- and, for --canary, reads the folder it is given and
writes only in a temporary one.

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

FOR GITHUB'S NIGHT (the person, 26 October 2026)

The person approved the night fetching the newest calendars and journals
itself, and making their text on its own machine. Three things here exist
for that:

  --only PATH...   the text of these PDFs and no others: the night extracts
                   what it fetched tonight, and a run over every PDF on its
                   machine would be a run over a subset that looks whole.
                   A PDF that already has text beside it is left alone -- a
                   new text never replaces one -- and a path that is not a
                   PDF of the four folders is refused. Exit 1 unless every
                   PDF named has its text when it ends, because a caller
                   that named them wants each one
  --ledger FILE    where the record of what was made, and by which
                   extractor, is kept: archive/extracted.json by default.
                   It is merged into, never replaced
  --canary DIR     whether this machine makes the laptop's text, byte for
                   byte. DIR holds the person's fixtures (tests/documents/
                   and its README say what): PDFs, each with the .txt the
                   laptop made from it. Exit 0 only when there is at least
                   one such pair, nothing in DIR is unpaired, and every
                   PDF's text, written the way this writes it, is identical
                   to the laptop's. Anything else is "not proved", and the
                   night asks for no document it could not read as the
                   laptop would: no fixtures is not a pass

A TEXT IS WRITTEN WHOLE: a part file, then a rename. It was written in
place, so a run killed part way could leave half a text, which wanted()
would then count as done and every parser read as the whole calendar.
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
import tempfile
import time
from collections import Counter

ROOTS = ["calendars", "calendars_senate", "journals", "journals_senate"]
LEDGER = Path("archive/extracted.json")


def extract(pdf):
    """(text, how) -- or (None, why not)."""
    if shutil.which("pdftotext"):
        try:
            out = subprocess.run(["pdftotext", "-layout", str(pdf), "-"],
                                 capture_output=True, text=True,
                                 encoding="utf-8", errors="replace", timeout=180)
            if out.returncode == 0 and (out.stdout or "").strip():
                return out.stdout, "pdftotext -layout"
        except subprocess.TimeoutExpired:
            return None, "pdftotext timed out"
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


def write_text(path, text):
    """A text file, whole: a part file beside it, then a rename over it.

    Written in text mode with this machine's line endings, as it always has
    been, because the laptop's texts were written that way and --canary
    holds this machine's text to them byte for byte."""
    path = Path(path)
    part = path.with_name(path.name + ".part")
    part.write_text(text, encoding="utf-8")
    os.replace(part, path)


def has_text(pdf):
    """Whether a PDF already has a text beside it with something in it."""
    txt = Path(pdf).with_suffix(".txt")
    return txt.exists() and txt.stat().st_size > 0


def wanted():
    out = []
    for root in ROOTS:
        r = Path(root)
        if not r.exists():
            continue
        for pdf in sorted(r.rglob("*.pdf")):
            if not has_text(pdf):
                out.append(pdf)
    return out


def named(paths):
    """(todo, kept, refused) for --only: the PDFs to extract; those left
    alone because they already have text; and each path refused, with why.
    A path the queue wrote on Windows carries backslashes, read as folders
    here wherever this runs."""
    todo, kept, refused = [], [], []
    for p in paths:
        pdf = Path(str(p).replace("\\", "/"))
        if pdf.is_absolute() or ".." in pdf.parts or not pdf.parts \
                or pdf.parts[0] not in ROOTS:
            refused.append((str(p), "not in " + ", ".join(f"{r}/" for r in ROOTS)))
        elif pdf.suffix.lower() != ".pdf":
            refused.append((str(p), "not a PDF"))
        elif not pdf.is_file():
            refused.append((str(p), "not on disk"))
        elif has_text(pdf):
            kept.append(pdf)
        elif pdf not in todo:
            todo.append(pdf)
    return todo, kept, refused


def _first_difference(a, b):
    """The first line, counted from 1, on which two texts' bytes differ."""
    la, lb = a.split(b"\n"), b.split(b"\n")
    for i, (x, y) in enumerate(zip(la, lb), 1):
        if x != y:
            return i
    return min(len(la), len(lb)) + 1


def canary(folder):
    """(proved, sentence): whether this machine makes, from each PDF in
    `folder`, the text the laptop made from it, byte for byte.

    FAILS CLOSED. No pair at all, a PDF without its text or a text without
    its PDF, a PDF that yields nothing here, and a single byte of difference
    are each "not proved", and the night then asks for no document. Every
    pair is read, so the sentence says how many agreed as well as where the
    first one that did not first differs. Files that are neither a PDF nor a
    text -- the folder's README -- are not fixtures."""
    folder = Path(folder)
    if not folder.is_dir():
        return False, f"not proved: {folder.as_posix()} is not a folder"
    files = [p for p in sorted(folder.iterdir()) if p.is_file()]
    pdfs = [p for p in files if p.suffix.lower() == ".pdf"]
    txts = [p for p in files if p.suffix.lower() == ".txt"]
    stems = {p.stem for p in pdfs}
    lone = [p.name for p in pdfs if p.with_suffix(".txt") not in txts] + \
           [p.name for p in txts if p.stem not in stems]
    pairs = [(p, p.with_suffix(".txt")) for p in pdfs if p.with_suffix(".txt") in txts]
    if not pairs:
        return False, (f"not proved: {folder.as_posix()} holds no PDF with the laptop's text "
                       "beside it")
    if lone:
        return False, f"not proved: {', '.join(lone)} in {folder.as_posix()} has no pair"
    same, first, how = 0, "", Counter()
    with tempfile.TemporaryDirectory(prefix="gr-canary-") as tmp:
        for pdf, txt in pairs:
            text, note = extract(pdf)
            if text is None:
                first = first or f"{pdf.name} gave no text here ({note})"
                continue
            made = Path(tmp) / txt.name
            write_text(made, text)
            mine, theirs = made.read_bytes(), txt.read_bytes()
            how[note] += 1
            if mine == theirs:
                same += 1
            elif not first:
                first = (f"{pdf.name} differs from line {_first_difference(mine, theirs)}, "
                         f"by {note}")
    by = ", ".join(f"{k}" for k, _ in how.most_common()) or "no extractor"
    if same == len(pairs):
        return True, f"identical for {same} of {len(pairs)}, by {by}"
    return False, f"not proved: identical for {same} of {len(pairs)}; the first that is not: {first}"


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", nargs="+", metavar="PDF",
                    help="the text of these PDFs only, each in one of "
                         + ", ".join(f"{r}/" for r in ROOTS)
                         + "; one that has text already is left alone")
    ap.add_argument("--ledger", default=str(LEDGER),
                    help=f"the record of what was made, merged into (default {LEDGER.as_posix()})")
    ap.add_argument("--canary", metavar="DIR",
                    help="exit 0 only if this machine makes, from each PDF in DIR, the text "
                         "beside it, byte for byte; extracts nothing anywhere else")
    a = ap.parse_args()
    if a.canary and (a.only or a.check or a.limit):
        ap.error("--canary only compares: it takes no --only, --check or --limit")
    if a.only and (a.check or a.limit):
        ap.error("--only names the PDFs: it takes no --check or --limit")

    if a.canary:
        proved, said = canary(a.canary)
        print(f"text canary: {said}")
        return 0 if proved else 1

    refused, kept = [], []
    if a.only:
        todo, kept, refused = named(a.only)
        for p, why in refused:
            print(f"  ! {p}: {why}")
        for p in kept:
            print(f"  {p.as_posix()}: has its text already, left as it is")
        print(f"{len(a.only):,} named, {len(todo):,} to extract")
    else:
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
    if ledger:
        write_ledger(a.ledger, ledger)

    print(f"\n{ok:,} extracted in {time.time() - t0:.0f}s, {len(bad)} failed")
    for k, n in how.most_common():
        print(f"  {n:,} by {k}")
    for p, why in bad[:6]:
        print(f"  failed: {p} -- {why}")
    if bad:
        print("\nA PDF with no text in it is usually a scan. It stays on disk; "
              "nothing\nelse changes, and the parsers simply will not see it.")
    if a.only and (bad or refused):
        print(f"\nNot every PDF named has its text: {len(bad)} gave none and "
              f"{len(refused)} could not be read here.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
