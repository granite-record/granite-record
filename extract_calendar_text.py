#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-08.1
"""
The text beside every calendar PDF, so the parsers can read the archive.

    python3 extract_calendar_text.py --check     # what is missing, extracts nothing
    python3 extract_calendar_text.py            # extract every missing one
    python3 extract_calendar_text.py --limit 50

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
"""

import argparse
import json
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

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
    for i, pdf in enumerate(todo, 1):
        text, note = extract(pdf)
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
