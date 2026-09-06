#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-05.1
"""
The hand-marked proceedings, in a file that no generator writes.

    python3 ground_truth.py --extract      # once: pull the marks out of the manifest
    python3 ground_truth.py --check        # does the manifest still agree with them
    python3 ground_truth.py                # show them

ground_truth.csv is the only measurement of this system that a person made:
35 proceedings timed by watching the video. Every timestamp method is scored
against it. It has been lost twice, both times because it lived as two columns
in verification_manifest.csv and a rebuild wrote that file without them.

So it moves out. This file is edited by hand and read by everything; nothing
under build_*.py or fetch_*.py writes to it. build_manifest.py reads it to fill
the observed_* columns, and probe_alignment.py reads it directly.

Columns: video_id, bill, kind, observed_start, observed_end, notes, marked_on.
Times are seconds into the recording, the same unit the site uses.
"""

import argparse
import csv
import sys
from datetime import date
from pathlib import Path

TRUTH = Path("ground_truth.csv")
COLS = ["video_id", "bill", "kind", "observed_start", "observed_end", "notes",
        "marked_on"]


def hms_to_s(v):
    """'1:02:03' or '62:03' or 3723 -> seconds."""
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if s.replace(".", "", 1).isdigit():
        return float(s)
    parts = [float(x) for x in s.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0.0)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def read_manifest_rows(path):
    p = Path(path)
    if p.suffix.lower() == ".xlsx":
        import openpyxl
        wb = openpyxl.load_workbook(p, read_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        hdr = [str(h) if h is not None else "" for h in rows[0]]
        return [dict(zip(hdr, r)) for r in rows[1:]]
    with p.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def read_truth():
    if not TRUTH.exists():
        return []
    with TRUTH.open(encoding="utf-8-sig", newline="") as fh:
        out = []
        for r in csv.DictReader(fh):
            r["observed_start"] = hms_to_s(r.get("observed_start"))
            r["observed_end"] = hms_to_s(r.get("observed_end"))
            out.append(r)
        return out


def write_truth(rows):
    with TRUTH.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        for r in rows:
            w.writerow({c: ("" if r.get(c) is None else r.get(c)) for c in COLS})


def extract(manifest):
    have = {(r["video_id"], r["bill"], r["kind"]) for r in read_truth()}
    rows, added = read_truth(), 0
    for r in read_manifest_rows(manifest):
        st = hms_to_s(r.get("observed_start"))
        if st is None:
            continue
        key = (str(r.get("video_id") or ""), str(r.get("bill") or "").upper(),
               str(r.get("proceeding") or "").lower())
        if key in have:
            continue
        have.add(key)
        rows.append({
            "video_id": key[0], "bill": key[1], "kind": key[2],
            "observed_start": st,
            "observed_end": hms_to_s(r.get("observed_end")),
            "notes": str(r.get("notes") or ""),
            "marked_on": date.today().isoformat(),
        })
        added += 1
    rows.sort(key=lambda r: (r["video_id"], r["observed_start"] or 0))
    write_truth(rows)
    print(f"{added} marks extracted; {len(rows)} in {TRUTH}")
    if added:
        print("This file is now the record. Edit it by hand; nothing generates "
              "it.")


def check(manifest):
    truth = {(r["video_id"], r["bill"], r["kind"]): r for r in read_truth()}
    if not truth:
        sys.exit(f"{TRUTH} is empty or missing. Run --extract first.")
    seen, drift, missing = 0, [], []
    for r in read_manifest_rows(manifest):
        key = (str(r.get("video_id") or ""), str(r.get("bill") or "").upper(),
               str(r.get("proceeding") or "").lower())
        if key not in truth:
            continue
        seen += 1
        st = hms_to_s(r.get("observed_start"))
        if st is None:
            missing.append(key)
        elif abs(st - (truth[key]["observed_start"] or 0)) > 1:
            drift.append((key, st, truth[key]["observed_start"]))
    print(f"{len(truth)} marks in {TRUTH}; {seen} of them present in the "
          "manifest")
    if missing:
        print(f"\n  {len(missing)} manifest rows have LOST their mark -- the "
              "manifest was rebuilt\n  without carrying them. build_manifest.py "
              "reads ground_truth.csv, so a\n  rebuild restores them:")
        for k in missing[:5]:
            print(f"    {k[1]:<8} {k[2]:<18} {k[0]}")
    if drift:
        print(f"\n  {len(drift)} differ from the record:")
        for k, a, b in drift[:5]:
            print(f"    {k[1]:<8} manifest {a:.0f}s, record {b:.0f}s")
    if not missing and not drift:
        print("The manifest agrees with the record.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=None,
                    help="verification_manifest.csv, or .xlsx")
    ap.add_argument("--extract", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    manifest = a.manifest
    if manifest is None:
        for cand in ("verification_manifest.csv", "verification_manifest.xlsx"):
            if Path(cand).exists():
                manifest = cand
                break

    if a.extract:
        if not manifest:
            sys.exit("No manifest found to extract from.")
        extract(manifest)
        return
    if a.check:
        if not manifest:
            sys.exit("No manifest found to check against.")
        check(manifest)
        return

    rows = read_truth()
    if not rows:
        print(f"{TRUTH} does not exist yet. Run: python3 ground_truth.py --extract")
        return
    print(f"{len(rows)} proceedings a person timed by hand, in {TRUTH}\n")
    for r in rows:
        st = r["observed_start"] or 0
        en = r["observed_end"]
        span = f" to {int(en)//60}m" if en else ""
        print(f"  {r['bill']:<8} {r['kind']:<18} {r['video_id']}  "
              f"{int(st)//60}m {int(st)%60:02d}s{span}")


if __name__ == "__main__":
    main()
