#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.3
"""
Work out which eras of the bill history archive are actually machine-readable.

    python3 probe_archive.py --from 1989 --to 2024

The Secretary of State bill histories live at a completely predictable address:

    /BillHistory/SofS_Archives/2001/house/CACR1H.pdf
                              year  chamber  bill + chamber letter

So enumeration for old sessions needs no search at all -- the URL can simply be
constructed. The catch is that a 2001 PDF turned out to be a SCAN with no text
layer, which no parser can read. Somewhere between then and now the documents
became born-digital, and that boundary decides how much of the archive is
cheap and how much needs OCR.

This samples a handful of bills per year and reports, for each:
  - does the URL pattern work
  - does the PDF carry extractable text, or is it an image
  - roughly how much text

Twenty-odd years at three bills each is about sixty requests, rate limited.
The answer shapes everything downstream, so it is worth doing before writing a
single parser for the older eras.
"""

import argparse
import io
import re
import time
import urllib.error
import urllib.request
import child
from collections import defaultdict
from pathlib import Path

BASE = "https://gc.nh.gov/BillHistory/SofS_Archives/{year}/{chamber}/{bill}.pdf"
UA = {"User-Agent": "granite-record/1.0 (civic transparency archive; "
                    "contact@graniterecord.org)"}


def get(url, timeout=60, tries=2):
    for n in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read(), r.status, None
        except urllib.error.HTTPError as e:
            return None, e.code, e
        except Exception as e:
            if n < tries - 1:
                time.sleep(2)
            else:
                return None, None, e
    return None, None, None


def pdf_text(data):
    """Extract text if any tool can. Returns (text, tool) or ("", reason)."""
    tmp = Path("_probe.pdf")
    tmp.write_bytes(data)
    try:
        import shutil, subprocess
        if shutil.which("pdftotext"):
            r = child.run(["pdftotext", "-layout", str(tmp), "-"],
                               capture_output=True, text=True)
            if r.returncode == 0:
                return r.stdout, "pdftotext"
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(data)) as d:
                return "\n".join(p.extract_text() or "" for p in d.pages), "pdfplumber"
        except ImportError:
            pass
        try:
            from pypdf import PdfReader
            rd = PdfReader(io.BytesIO(data))
            return "\n".join(p.extract_text() or "" for p in rd.pages), "pypdf"
        except ImportError:
            return "", "no extractor installed"
    finally:
        tmp.unlink(missing_ok=True)
    return "", "extraction failed"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="y0", type=int, default=1989)
    ap.add_argument("--to", dest="y1", type=int, default=2024)
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--samples", default="HB1,HB100,CACR1",
                    help="bills to try per year")
    a = ap.parse_args()

    bills = [b.strip().upper() for b in a.samples.split(",") if b.strip()]
    print(f"sampling {bills} for {a.y0}-{a.y1}\n")
    print(f"{'year':<6}{'found':<7}{'text?':<9}{'chars':>8}  note")
    print("-" * 62)

    eras = defaultdict(list)
    for year in range(a.y0, a.y1 + 1):
        found = 0
        best_text, best_tool = "", ""
        note = ""
        for b in bills:
            chamber = "senate" if b.startswith("S") else "house"
            letter = "S" if chamber == "senate" else "H"
            url = BASE.format(year=year, chamber=chamber, bill=f"{b}{letter}")
            time.sleep(a.delay)
            data, code, err = get(url)
            if data is None:
                if code == 404 and not note:
                    note = "404"
                elif err and not note:
                    note = type(err).__name__
                continue
            if data[:4] != b"%PDF":
                note = note or "not a PDF"
                continue
            found += 1
            txt, tool = pdf_text(data)
            txt = re.sub(r"\s+", " ", txt or "").strip()
            if len(txt) > len(best_text):
                best_text, best_tool = txt, tool

        has = "TEXT" if len(best_text) > 120 else ("scan" if found else "-")
        eras[has].append(year)
        print(f"{year:<6}{found}/{len(bills):<5}{has:<9}{len(best_text):>8}  "
              f"{note or best_tool}")
        if has == "TEXT" and len(best_text) > 200:
            snippet = best_text[:110]
            print(f"        {snippet}")

    print("\n" + "=" * 62)
    for k in ("TEXT", "scan", "-"):
        if eras[k]:
            ys = eras[k]
            label = {"TEXT": "machine-readable",
                     "scan": "scanned images, would need OCR",
                     "-": "nothing found at this URL pattern"}[k]
            runs, start = [], ys[0]
            for i in range(1, len(ys) + 1):
                if i == len(ys) or ys[i] != ys[i - 1] + 1:
                    runs.append(f"{start}" if start == ys[i - 1]
                                else f"{start}-{ys[i - 1]}")
                    if i < len(ys):
                        start = ys[i]
            print(f"{label}: {', '.join(runs)}")

    print("\nWhat to do with this:")
    print("  Machine-readable years can be parsed like any other era.")
    print("  Scanned years need OCR, which is a much larger commitment: a new")
    print("  dependency, error-prone output on old print, and every extracted")
    print("  fact needing a lower confidence than the rest of the site.")
    print("  Years with nothing found may use a different path or naming.")


if __name__ == "__main__":
    main()
