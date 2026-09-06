#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.4
"""
Check alignment across every video processed, without needing hand-marked times.

    python3 verify_batch.py --work work --manifest verification_manifest.csv
    python3 verify_batch.py --sample 20        # draw spot-checks to eyeball

Two kinds of checking, because at this scale you cannot verify everything.

STRUCTURAL: things that must be true regardless of accuracy. Segments within a
video should not overlap, should run in docket order, should be a plausible
length for a hearing, and should not claim more of the recording than exists.
Violations are bugs, not misses, and can be found without watching anything.

SAMPLED: a stratified random draw across tolerance bands, with links. Checking
twenty of these by hand gives a real confidence figure for thousands. Checking
the twenty that happen to be first gives nothing, because the early ones in a
sitting are systematically easier.
"""

import argparse
import csv
import json
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path


def hms(s):
    s = int(s)
    return f"{s//3600}:{(s%3600)//60:02d}:{s%60:02d}"


def structural(segs):
    """Checks that are true or false regardless of accuracy."""
    problems = defaultdict(list)
    overlap_secs = 0
    for vid, ss in segs.items():
        real = [s for s in ss if s.get("kind") != "revisit?"]
        span = max((s["end"] for s in real), default=0)
        for s in real:
            if s["end"] <= s["start"]:
                problems["end before start"].append((vid, s["bill"]))
            if s.get("located"):
                L = s["end"] - s["start"]
                if L < 60:
                    problems["located but under a minute"].append((vid, s["bill"]))
                if L > 4 * 3600:
                    problems["located but over four hours"].append((vid, s["bill"]))

        # Two different findings, and lumping them hid which one mattered.
        #
        # Segments are stored in DOCKET order. The aligner's DP forces its
        # spans to run in that order, monotonic by construction. A stated
        # boundary reports when the chair actually took the bill up, and chairs
        # skip around -- so a marker run can put bill 5 before bill 3 in time
        # while the file still lists them 3 then 5. Nothing is wrong with that
        # recording; the docket order simply was not the running order, which
        # is a thing worth knowing rather than a bug.
        #
        # Two spans sharing the same minutes IS a bug: both cannot be right,
        # and the site would show two bills claiming one stretch of tape.
        pub = [s for s in real if s.get("located")]
        for i in range(1, len(pub)):
            a, b = pub[i - 1], pub[i]
            ov = min(a["end"], b["end"]) - max(a["start"], b["start"])
            if ov > 1:
                problems["overlapping in time"].append((vid, b["bill"]))
                overlap_secs += ov
            elif b["start"] < a["start"]:
                problems["taken out of docket order"].append((vid, b["bill"]))

        covered = sum(s["end"] - s["start"] for s in real if s.get("located"))
        if span and covered > span * 1.02:
            problems["segments exceed the recording"].append((vid, ""))
    problems["_overlap_seconds"] = [("", "")] * int(overlap_secs / 60)
    return problems


def load_segments(work):
    out = {}
    w = Path(work)
    if not w.exists():
        return out
    for d in w.iterdir():
        f = d / "segments.json"
        if d.is_dir() and f.exists():
            try:
                out[d.name] = json.loads(f.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"  unreadable: {d.name}: {e}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default="work")
    ap.add_argument("--manifest", default="verification_manifest.csv")
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()

    segs = load_segments(a.work)
    if not segs:
        print(f"No segments.json found under {a.work}/")
        return
    print(f"{len(segs):,} videos aligned")

    rows = []
    for vid, ss in segs.items():
        for s in ss:
            if s.get("kind") == "revisit?":
                continue
            rows.append({**s, "video": vid})
    loc = [r for r in rows if r.get("located")]
    print(f"{len(rows):,} proceedings, {len(loc):,} located "
          f"({len(loc)/len(rows):.0%})")

    print("\ntolerance bands:")
    stated = sum(1 for r in loc if r.get("start_stated"))
    # Bucketed, not one row per distinct value. A marker derives its tolerance
    # from the window between two stated closes, so the values are arbitrary
    # integers now -- 63, 121, 234 -- and a row each made the table unreadable
    # and printed several different bands under the same label.
    BUCKETS = [(30, "up to 30 sec"), (60, "up to 1 min"), (180, "up to 3 min"),
               (300, "up to 5 min"), (600, "up to 10 min"),
               (900, "up to 15 min"), (1800, "up to 30 min"),
               (10 ** 9, "over 30 min")]
    counts = Counter()
    for r in loc:
        v = r.get("tolerance") or 0
        counts[next(lab for lim, lab in BUCKETS if v <= lim)] += 1
    for lim, lab in BUCKETS:
        if counts[lab]:
            print(f"  {lab:<14} {counts[lab]:>6,}  ({counts[lab]/len(loc):.0%})")
    if stated:
        print(f"\n{stated:,} of {len(loc):,} located segments start on a boundary "
              "the chair stated")
        print("  (apply_markers.py); the rest are inferred from mention density")

    why = Counter(r.get("why_not") for r in rows if not r.get("located"))
    if why:
        print("\nnot located:")
        for k, n in why.most_common():
            print(f"  {n:>6,}  {k}")

    # ---------------------------------------------------------- structural --
    print("\n" + "=" * 62)
    print("STRUCTURAL CHECKS  (true or false regardless of accuracy)")
    print("=" * 62)
    problems = structural(segs)
    if problems:
        mins = len(problems.pop("_overlap_seconds", []))
        for k, v in sorted(problems.items(), key=lambda x: -len(x[1])):
            ex = ", ".join(f"{a_}/{b}" for a_, b in v[:3] if a_)
            print(f"  {len(v):>6,}  {k}   e.g. {ex}")
        if mins:
            print(f"\n  {mins:,} minutes of tape are claimed by two bills at once.")
    else:
        print("  none")

    # ---- did applying the markers cause any of that? ----------------------
    # apply_markers.py copies segments.json to segments.pre_markers.json before
    # its first write, so this is answerable from disk rather than by opinion.
    # Only the videos that were actually patched are compared, so it is the
    # same set of proceedings measured twice.
    base = {}
    for d in Path(a.work).iterdir():
        f = d / "segments.pre_markers.json"
        if d.is_dir() and f.exists():
            try:
                base[d.name] = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                pass
    if base:
        after = {k: v for k, v in segs.items() if k in base}
        b4, af = structural(base), structural(after)
        print("\n" + "=" * 62)
        print(f"BEFORE AND AFTER THE MARKERS  ({len(base):,} patched videos)")
        print("=" * 62)
        print(f"  {'check':<34}{'before':>8}{'after':>8}{'change':>9}")
        b4.pop("_overlap_seconds", None); af.pop("_overlap_seconds", None)
        for k in sorted(set(b4) | set(af)):
            x, y = len(b4.get(k, [])), len(af.get(k, []))
            d_ = y - x
            print(f"  {k:<34}{x:>8,}{y:>8,}{(f'{d_:+,}' if d_ else '  same'):>9}")
        worse = [k for k in set(b4) | set(af)
                 if len(af.get(k, [])) > len(b4.get(k, []))]
        if worse:
            print("\nThe markers made these worse:")
            for k in worse:
                had = {x for x in b4.get(k, [])}
                for vid, bill in af.get(k, []):
                    if (vid, bill) not in had:
                        print(f"  {k}: {vid}/{bill}")
                        break
            print("\nEvery patched segment keeps the estimate it replaced under")
            print('"marker", so a bad one can be read back without rerunning.')
        else:
            print("\nNothing got structurally worse. Everything listed above was")
            print("already there before a single boundary was adopted.")

    lens = [r["end"] - r["start"] for r in loc]
    if lens:
        lens.sort()
        print(f"\nlocated segment length: median {hms(lens[len(lens)//2])}, "
              f"shortest {hms(lens[0])}, longest {hms(lens[-1])}")

    # ------------------------------------------------------------ coverage --
    mp = Path(a.manifest)
    if mp.exists():
        man = list(csv.DictReader(open(mp, encoding="utf-8-sig")))
        have = {(r["video"], r["bill"].upper(), r.get("kind", "")) for r in rows}
        want = [(r["video_id"], r["bill"].upper(), r["proceeding"])
                for r in man if r.get("video_id")]
        hit = sum(1 for k in want if k in have)
        print(f"\nmanifest coverage: {hit:,} of {len(want):,} proceedings with a "
              f"video have a segment ({hit/max(len(want),1):.0%})")
        novid = sum(1 for r in man if not r.get("video_id"))
        if novid:
            print(f"  {novid:,} manifest rows have no video at all")

    # -------------------------------------------------------------- sample --
    if a.sample:
        print("\n" + "=" * 62)
        print(f"SPOT CHECKS  ({a.sample}, stratified by tolerance band)")
        print("=" * 62)
        print("Open each, confirm the chair is taking up that bill near that")
        print("point, and note whether it fell inside the stated tolerance.\n")
        rnd = random.Random(a.seed)
        by = defaultdict(list)
        for r in loc:
            by[r.get("tolerance")].append(r)
        per = max(1, a.sample // max(len(by), 1))
        picked = []
        for t in sorted(by, key=lambda x: (x or 0)):
            picked += rnd.sample(by[t], min(per, len(by[t])))
        for r in picked[:a.sample]:
            tol = r.get("tolerance") or 300
            from_ = max(int(r["start"]) - min(tol, 300), 0)
            print(f"  {r['bill']:<8} {r.get('kind',''):<20} +/-{tol//60} min   "
                  f"starts around {hms(r['start'])}")
            print(f"    https://www.youtube.com/watch?v={r['video']}&t={from_}s\n")
        print("A stratified draw matters: the first bill in a sitting is much")
        print("easier to place than the fifth, so checking the first few of each")
        print("video would flatter the result.")


if __name__ == "__main__":
    main()
