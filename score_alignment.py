#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.2
"""
Score alignment against hand-marked times, across every video transcribed.

    python3 score_alignment.py --manifest verification_manifest.csv --work work

Reads the observed_start column you filled in and every work/<videoid>/segments.json
that exists, matches on bill and proceeding, and reports how far off each was and
whether it fell inside the tolerance the aligner claimed.

The question this answers is not "is the aligner accurate" but "does it know when
it is accurate". A system that is right 70% of the time and honest about which 70%
is publishable. One that is right 90% of the time with no idea which 90% is not.
"""

import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path


def secs(s):
    s = (s or "").strip()
    if not s:
        return None
    if ":" in s:
        p = [float(x) for x in s.split(":")]
        return p[0] * 3600 + p[1] * 60 + p[2] if len(p) == 3 else p[0] * 60 + p[1]
    try:
        v = float(s)
    except ValueError:
        return None
    return v * 86400 if 0 < v < 1 else v


def ms(x):
    return f"{int(abs(x))//60}m{int(abs(x))%60:02d}s"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="verification_manifest.csv")
    ap.add_argument("--work", default="work")
    a = ap.parse_args()

    # The generated manifest and the one you filled in are usually different
    # files with forgettable names. If the given one has no marks, look for one
    # that does rather than reporting zero and stopping.
    def marks_in(path):
        try:
            return sum(1 for r in csv.DictReader(open(path, encoding="utf-8-sig"))
                       if (r.get("observed_start") or "").strip())
        except Exception:
            return 0

    if not Path(a.manifest).exists() or marks_in(a.manifest) == 0:
        cands = [(marks_in(f), f) for f in Path(".").glob("*.csv")]
        cands = [c for c in cands if c[0] > 0]
        if cands:
            cands.sort(reverse=True)
            a.manifest = str(cands[0][1])
            print(f"Using {a.manifest} ({cands[0][0]} marked rows) \u2014 the file "
                  "given had none.")
        else:
            print("No CSV in this folder has anything in observed_start.")
            print("Marked files found:", ", ".join(str(f) for f in Path(".").glob("*.csv")) or "none")
            return

    truth = {}
    for r in csv.DictReader(open(a.manifest, encoding="utf-8-sig")):
        t = secs(r.get("observed_start"))
        if t is not None and r.get("video_id"):
            truth[(r["video_id"], r["bill"].upper(), r["proceeding"])] = {
                "t": t, "tier": r.get("tier", ""), "committee": r.get("committee", ""),
                "date": r.get("sched_date", ""), "end": secs(r.get("observed_end")),
            }
    print(f"{len(truth)} hand-marked proceedings in the manifest")

    segs, missing = {}, []
    for d in Path(a.work).iterdir() if Path(a.work).exists() else []:
        f = d / "segments.json"
        if not f.exists():
            continue
        for s in json.loads(f.read_text(encoding="utf-8")):
            if s.get("kind") == "revisit?":
                continue
            segs[(d.name, s["bill"].upper(), s.get("kind", ""))] = s
    vids_truth = {k[0] for k in truth}
    vids_seg = {k[0] for k in segs}
    print(f"{len(vids_seg)} of {len(vids_truth)} marked videos have been transcribed")
    for v in sorted(vids_truth - vids_seg):
        missing.append(v)

    rows = []
    for k, t in truth.items():
        s = segs.get(k)
        if not s:
            continue
        rows.append({"key": k, "err": s["start"] - t["t"], "tier": t["tier"],
                     "kind": k[2], "committee": t["committee"], "date": t["date"],
                     "located": s.get("located"), "tol": s.get("tolerance"),
                     "n": s.get("mentions_inside", 0),
                     "seg_len": s["end"] - s["start"],
                     "true_len": (t["end"] - t["t"]) if t["end"] else None})
    if not rows:
        print("\nNo overlap yet. Transcribe a video that has marked rows.")
        if missing:
            print("Marked but not transcribed:")
            for v in missing:
                print(f"  {v}")
        return

    print(f"\n{'bill / proceeding':<40}{'error':>9}{'claimed':>9}{'ment':>6}  verdict")
    print("-" * 82)
    for r in sorted(rows, key=lambda x: (x["date"], x["key"][1])):
        # Sub-minute claims round to "+/-0m" otherwise, which reads as a
        # broken value rather than as the tightest tolerance on the site.
        claim = ("--" if not r["tol"] else
                 f"+/-{r['tol']}s" if r["tol"] < 60 else f"+/-{r['tol']//60}m")
        if not r["located"]:
            verdict = "not published"
        elif abs(r["err"]) <= (r["tol"] or 0):
            verdict = "inside tolerance"
        else:
            verdict = "OUTSIDE - would mislead"
        print(f"{r['key'][1]+' '+r['kind']:<40}{ms(r['err']):>9}{claim:>9}"
              f"{r['n']:>6}  {verdict}")

    pub = [r for r in rows if r["located"]]
    inside = [r for r in pub if abs(r["err"]) <= (r["tol"] or 0)]
    errs = [abs(r["err"]) for r in rows]

    print("\n" + "=" * 62)
    print(f"published            {len(pub)}/{len(rows)}")
    if pub:
        print(f"inside tolerance     {len(inside)}/{len(pub)}  "
              f"({len(inside)/len(pub):.0%})  <- the number that matters")
    print(f"median error         {ms(statistics.median(errs))}")
    print(f"within 2 min         {sum(1 for e in errs if e <= 120)}/{len(errs)}")
    print(f"within 5 min         {sum(1 for e in errs if e <= 300)}/{len(errs)}")
    print(f"worst                {ms(max(errs))}")

    for label, key in (("proceeding type", "kind"), ("tier", "tier")):
        by = defaultdict(list)
        for r in rows:
            by[r[key]].append(abs(r["err"]))
        if len(by) > 1:
            print(f"\nby {label}:")
            for k, v in sorted(by.items()):
                print(f"  {k:<24} n={len(v):<4} median {ms(statistics.median(v))}  "
                      f"within 5 min {sum(1 for e in v if e<=300)}/{len(v)}")

    bad = [r for r in pub if abs(r["err"]) > (r["tol"] or 0)]
    if bad:
        print(f"\n{len(bad)} published outside their own tolerance. These are the")
        print("failures that matter, because the site would state them as fact:")
        for r in bad:
            tol = r["tol"] or 0
            claimed = f"+/-{tol}s" if tol < 60 else f"+/-{tol//60}m"
            print(f"  {r['key'][1]} {r['kind']} on {r['date']} — off by {ms(r['err'])}, "
                  f"claimed {claimed}, {r['n']} mentions")

    if missing:
        print(f"\n{len(missing)} marked videos not yet transcribed:")
        for v in missing:
            print(f"  python3 transcribe_and_align.py --video {v} "
                  f"--manifest {a.manifest} --model medium")


if __name__ == "__main__":
    main()
