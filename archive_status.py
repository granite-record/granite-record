#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-08.1
"""
How much of the record is on this disk, and what is still missing.

    python3 archive_status.py            # every source, one line each
    python3 archive_status.py --detail   # and the gaps, year by year

No network, nothing written. Under a second.

WHY

The goal is every document eventually. That only means something if "how far
along" is a number somebody can print, rather than a feeling about how many
fetches have been run. ARCHIVE_PLAN.md put it plainly: complete has to be a
figure this prints.

So this reads what is actually on disk -- not a log of what was attempted --
and reports each source as held over wanted. A source whose denominator is
unknown says so rather than reporting a percentage of nothing.
"""

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


def _json(path):
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return None


def bar(held, want, width=24):
    if not want:
        return "  " + "?" * 4
    n = int(round(width * held / want))
    return "[" + "#" * n + "." * (width - n) + f"] {held / want:4.0%}"


def line(name, held, want, note=""):
    if want:
        print(f"  {name:<34} {held:>7,} / {want:<7,} {bar(held, want)}  {note}")
    else:
        print(f"  {name:<34} {held:>7,}   {'':<7} {'':<31}  {note}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--detail", action="store_true")
    a = ap.parse_args()

    print("=" * 78)
    print("What is on this disk")
    print("=" * 78)

    # ---- the database ----------------------------------------------------
    man = _json("db/_manifest.json") or {}
    ok = {k: v for k, v in man.items() if "rows" in v}
    rows = sum(v["rows"] for v in ok.values())
    mb = sum(v.get("bytes", 0) for v in ok.values()) / 1e6
    print("\nTHE PUBLIC DATABASE")
    line("views dumped", len(ok), 27, f"{rows:,} rows, {mb:,.0f} MB")
    if a.detail:
        for k, v in sorted(ok.items(), key=lambda x: -x[1]["rows"])[:8]:
            print(f"      {k:<26} {v['rows']:>10,} rows")

    # ---- archived bills --------------------------------------------------
    bills = _json("archive_bills.json") or {}
    n_bills = sum(len(v) for v in bills.values())
    print("\nBILLS, BY TERM")
    # 1989-1990 through 2023-2024 is 18 terms; the current one comes from
    # bill_status.json rather than from here.
    line("terms fetched", len(bills), 18, f"{n_bills:,} bills")
    if a.detail:
        for t in sorted(bills):
            print(f"      {t}  {len(bills[t]):>6,}")
    cur = _json("bill_status.json") or {}
    line("current term (bill_status)", sum(len(v) for v in cur.values()), 0,
         f"{len(cur)} term(s)")

    # ---- calendars and journals -----------------------------------------
    q = Path("archive/queue.csv")
    print("\nCALENDARS AND JOURNALS")
    if not q.exists():
        line("queue", 0, 0, "not discovered yet -- run --discover")
    else:
        with q.open(encoding="utf-8", newline="") as f:
            rows_ = list(csv.DictReader(f))
        by = defaultdict(lambda: [0, 0])
        for r in rows_:
            k = f"{'House' if r['chamber'] == 'H' else 'Senate'} {r['kind']}s"
            by[k][1] += 1
            if r["state"] == "held":
                by[k][0] += 1
        for k in sorted(by):
            line(k, by[k][0], by[k][1])
        held = sum(v[0] for v in by.values())
        line("all four", held, len(rows_),
             f"{sum(int(r['bytes'] or 0) for r in rows_) / 1e6:,.0f} MB")
        failed = [r for r in rows_ if r["state"] == "failed"]
        if failed:
            print(f"      {len(failed)} failed after three attempts")
        if a.detail:
            gaps = Counter((r["chamber"], r["kind"], r["year"])
                           for r in rows_ if r["state"] != "held")
            for (ch, kind, yr), n in sorted(gaps.items())[:14]:
                print(f"      {ch} {kind:9} {yr}: {n} still wanted")

    # ---- the text beside them -------------------------------------------
    pdfs = txts = 0
    for root in ("calendars", "calendars_senate", "journals", "journals_senate"):
        p = Path(root)
        if p.exists():
            pdfs += len(list(p.rglob("*.pdf")))
            txts += len(list(p.rglob("*.txt")))
    line("text extracted beside them", txts, pdfs,
         "extract_calendar_text.py" if txts < pdfs else "")

    # ---- recordings ------------------------------------------------------
    print("\nRECORDINGS")
    chan = _json("channel_index_full.json") or {}
    total = sum(c.get("total", 0) for c in chan.values()) if chan else 0
    work = Path("work")
    caps = len([d for d in work.iterdir()
                if d.is_dir() and (d / "captions.en.json3").exists()]) \
        if work.exists() else 0
    line("videos indexed", total, total, "both channels, back to May 2020")
    line("captions on disk", caps, total)

    # ---- bill text -------------------------------------------------------
    print("\nBILL TEXT AND STATUS")
    bt = Path("bill_text")
    sp = Path("status_pages")
    line("bill text pages", len(list(bt.glob("*.html"))) if bt.exists() else 0,
         0, "current term only, one version each")
    line("status pages", len(list(sp.glob("*.html"))) if sp.exists() else 0, 0)

    # ---- what is coming --------------------------------------------------
    sched = _json("schedule.json")
    if sched is not None:
        print("\nTHE SCHEDULE")
        line("events", len(sched), 0,
             f"{sum(len(e.get('bills') or []) for e in sched)} bill slots")

    print("\n" + "=" * 78)
    print("  A percentage here is held over what the source says exists.")
    print("  Where no denominator is known the count stands on its own.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
