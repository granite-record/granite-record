#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-05.5
"""
Join the docket to the video index. Produces a verification manifest with the
video ID and predicted offset already filled in, so the manual pass is only
"watch and mark boundaries" rather than "go find the video first."

Needs docket_parser.py in the same folder.

    python3 build_manifest.py --videos videos_house_2025-01-01_to_2025-03-31.csv

Downloads Docket.txt automatically unless you pass --docket with a local copy.
Standard library only.
"""

import argparse
import csv
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

try:
    from docket_parser import (parse_rows, build_referral_timeline,
                               parse_proceedings, build_sittings)
except ImportError:
    sys.exit("Put docket_parser.py in this same folder, then rerun.")

# Named so the error above can print it. Nothing here requests it: this is
# a build script and fetching is fetch_*'s job.
DOCKET_URL = "https://gc.nh.gov/dynamicdatadump/Docket.txt"

# Committee names differ between the docket and the video titles. Left side is
# what appears in a video title; right side is what the docket referral says.
TITLE_TO_DOCKET = {
    "Committee on Housing": "Housing",
}

# Finance splits into three divisions on the video side, but a bill's referral
# row only ever says "Finance". Division assignment is not in the docket, so a
# Finance bill matches up to four videos on a given day and cannot be resolved
# from this data alone.
AMBIGUOUS_FAMILIES = {"Finance"}

# Titles carrying a bill number align themselves -- no transcript needed.
# Must match build_floor_index.py exactly: both decide whether a recording
# names its bill, and disagreeing means a video is exact in one view and
# unmatched in the other. HJR was missing here, and so was case tolerance.
BILLS_IN_TITLE = re.compile(
    r"\b(HB|SB|CACR|HR|SR|HCR|SCR|HJR)\s?(\d+)\b", re.I)


def norm_title_committee(c):
    c = re.sub(r"\s+Work Session on .*$", "", c)
    c = re.sub(r"\s+(Afternoon\s+)?Subcommittee Work Session$", "", c)
    c = re.sub(r"\s+Work Session$", "", c)
    c = TITLE_TO_DOCKET.get(c.strip(), c.strip())
    return c


def family(c):
    """Finance Division II -> Finance. Everything else unchanged."""
    m = re.match(r"^(Finance)\b", c)
    return m.group(1) if m else c


def load_videos(paths):
    """Read one or more video index CSVs, tagging each row with its chamber.

    The chamber comes from the filename, since fetch_channel_index.py names
    them videos_house_... and videos_senate_..., and the CSV itself does not
    record which channel it came from.
    """
    if isinstance(paths, str):
        paths = [paths]

    # Expand patterns here rather than relying on the shell: Windows cmd does
    # not glob, so "videos_*.csv" arrives as a literal. Passing a pattern is
    # the only way to avoid typing six filenames exactly right, and typing
    # them exactly right is what has failed twice.
    files = []
    for pat in paths:
        if any(c in str(pat) for c in "*?["):
            hits = sorted(Path(".").glob(str(pat)))
            if not hits:
                sys.exit(f"Nothing matches {pat}")
            files.extend(hits)
        else:
            f = Path(pat)
            if not f.exists():
                near = sorted(x.name for x in Path(".").glob("videos_*.csv"))
                sys.exit(f"No {pat}.\n"
                         + ("These are here:\n  " + "\n  ".join(near)
                            if near else "No videos_*.csv here at all.")
                         + "\n\nOr just pass --videos \"videos_*.csv\" and let "
                           "it find them.")
            files.append(f)

    # The same recording can appear in two indexes whose date ranges overlap.
    # Counted twice it would look like a committee streamed the same sitting
    # on two channels, and the day would be treated as ambiguous.
    out, seen, dupes = [], {}, 0
    for p in files:
        body = "S" if "senate" in str(p).lower() else "H"
        for v in _load_one(p):
            if v["video_id"] in seen:
                dupes += 1
                continue
            seen[v["video_id"]] = True
            v["body"] = body
            v["source"] = str(p)
            out.append(v)
    print(f"  {len(out):,} videos from {len(files)} file(s)"
          + (f", {dupes:,} duplicates across overlapping ranges skipped"
             if dupes else ""))
    # What the indexes actually cover, so a gap is visible rather than
    # discovered later as a proceeding with no video.
    dates = sorted(v["date"] for v in out if v.get("date"))
    if dates:
        print(f"  covering {dates[0]} to {dates[-1]}")
        byyear = defaultdict(lambda: [None, None])
        for d in dates:
            y = d[:4]
            lo, hi = byyear[y]
            byyear[y] = [min(lo or d, d), max(hi or d, d)]
        for y, (lo, hi) in sorted(byyear.items()):
            print(f"    {y}: {lo} to {hi}")
    return out


def _load_one(path):
    vids = []
    for r in csv.DictReader(open(path, encoding="utf-8")):
        if r["title_parsed"] != "yes":
            continue
        raw = r["parsed_committee"]
        vids.append({
            "video_id": r["video_id"],
            "title": r["title"],
            "date": r["parsed_date"],
            "committee_raw": raw,
            "committee": norm_title_committee(raw),
            "family": family(norm_title_committee(raw)),
            "start_eastern": r["start_eastern"],
            "bills_in_title": {f"{m.group(1)}{m.group(2)}"
                               for m in BILLS_IN_TITLE.finditer(r["title"])},
        })
    return vids


def predicted_offset(sched_time, start_eastern):
    """Seconds from the start of the stream to the scheduled time."""
    if not sched_time or not start_eastern:
        return None
    try:
        st = datetime.strptime(start_eastern, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    h, m = (int(x) for x in sched_time.split(":"))
    sched = st.replace(hour=h, minute=m, second=0)
    return int((sched - st).total_seconds())


def hhmmss(sec):
    if sec is None:
        return ""
    sign = "-" if sec < 0 else ""
    return sign + str(timedelta(seconds=abs(int(sec))))


def read_any(path):
    """Rows from a .csv or a .xlsx, as dicts of strings."""
    p = Path(path)
    if p.suffix.lower() in (".xlsx", ".xlsm"):
        from openpyxl import load_workbook
        rws = list(load_workbook(p, read_only=True).active
                   .iter_rows(values_only=True))
        head = [str(c).strip() if c is not None else "" for c in rws[0]]
        return [dict(zip(head, r)) for r in rws[1:]]
    with p.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def as_date(v):
    """YYYY-MM-DD from a date cell, an Excel serial, or a string."""
    from datetime import date as _d, datetime as _dt
    if v is None or v == "":
        return ""
    if isinstance(v, _dt):
        return v.date().isoformat()
    if isinstance(v, _d):
        return v.isoformat()
    s = str(v).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    if re.fullmatch(r"\d{5}(\.\d+)?", s):
        # Excel counts days from 1899-12-30.
        return (_d(1899, 12, 30) + timedelta(days=int(float(s)))).isoformat()
    m = re.match(r"^(\d{4}-\d{2}-\d{2})", s)
    return m.group(1) if m else s


def as_clock(v):
    """H:MM:SS from a time cell, a timedelta, an Excel fraction, or text."""
    from datetime import time as _t, timedelta as _td
    if v is None or v == "":
        return ""
    if isinstance(v, _td):
        return str(_td(seconds=int(v.total_seconds())))
    if isinstance(v, _t):
        return f"{v.hour}:{v.minute:02d}:{v.second:02d}"
    s = str(v).strip()
    if re.fullmatch(r"0?\.\d+", s):
        return str(timedelta(seconds=int(float(s) * 86400)))
    return s


def load_marks(path):
    """{(bill, date, kind): (start, end, notes)} from an earlier manifest.

    These are the only numbers in this project a person produced by watching
    the video. A fresh manifest writes observed_start empty, so without this
    every rebuild throws them away -- which has already happened once, and is
    why the site and the hand marks now name entirely different videos.
    """
    marks = {}
    for r in read_any(path):
        start = as_clock(r.get("observed_start"))
        if not start:
            continue
        key = (str(r.get("bill") or "").strip().upper(),
               as_date(r.get("sched_date")),
               str(r.get("proceeding") or "").strip().lower())
        marks[key] = (start, as_clock(r.get("observed_end")),
                      str(r.get("notes") or ""))
    return marks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--videos", required=True, nargs="+",
                    help="one or more video index CSVs; pass the House and "
                         "Senate indexes together to match both chambers")
    ap.add_argument("--docket", default=None, help="local Docket.txt (downloads if omitted)")
    ap.add_argument("--out", default="verification_manifest.csv")
    ap.add_argument("--keep-marks", metavar="OLD",
                    help="carry observed_start/observed_end forward from an "
                         "earlier manifest (.csv or .xlsx). Without this they "
                         "are lost on every rebuild.")
    a = ap.parse_args()

    # A build_* SCRIPT DOES NOT TOUCH THE NETWORK. This used to fetch
    # Docket.txt from gc.nh.gov when the file was absent, and the whole
    # permission rule in CLAUDE.md rests on the naming contract that only
    # fetch_* does that -- so a person or a model running this in good faith
    # would have asked the address that has blocked this one twice, without
    # ever being asked. It never fired here because Docket.txt is on disk. It
    # fires in a clean checkout, which is the state a refactor creates.
    #
    # Naming the file it wants and the command that gets it costs one run and
    # keeps the decision with a person.
    docket_path = a.docket or "Docket.txt"
    if not Path(docket_path).exists():
        sys.exit(
            f"No {docket_path}.\n\n"
            "This builds the manifest and does not fetch anything. Get the "
            "docket first:\n"
            f"    curl -o Docket.txt {DOCKET_URL}\n\n"
            "or pass an archived term's docket with --docket "
            "Docket_2023-2024.txt.\n"
            "Those are on this disk already if fetch_archive_docket.py has "
            "run for that term.")
    print(f"Parsing {docket_path}...")

    rows = parse_rows(docket_path)
    timeline = build_referral_timeline(rows)
    procs = parse_proceedings(rows, timeline)
    build_sittings(procs)
    # Senate proceedings were filtered out here from the start. That single
    # condition, not any transcription problem, is why no Senate hearing has
    # ever had a timestamp: there was nothing in the manifest for a Senate
    # recording to align against.
    #
    # Which chambers are covered now follows from the video indexes given,
    # rather than being fixed in the code.
    vids = load_videos(a.videos)
    bodies = {v.get("body") or ("S" if "senate" in (v.get("source") or "").lower()
                                else "H") for v in vids}
    procs = [p for p in procs
             if p.confidence != "X-cancelled" and p.body in bodies]
    from collections import Counter as _C
    byb = _C(p.body for p in procs)
    print(f"  {len(procs):,} proceedings in {'/'.join(sorted(bodies))}: "
          + ", ".join(f"{n:,} {'House' if b == 'H' else 'Senate'}"
                      for b, n in sorted(byb.items())))
    dates = {v["date"] for v in vids}
    procs = [p for p in procs if p.sched_date in dates]
    print(f"  {len(procs):,} fall inside the video window")

    exact = defaultdict(list)
    fam = defaultdict(list)
    for v in vids:
        exact[(v["committee"], v["date"])].append(v)
        fam[(v["family"], v["date"])].append(v)

    out, stats = [], defaultdict(int)
    for p in procs:
        cands = exact.get((p.committee, p.sched_date)) or fam.get((family(p.committee or ""), p.sched_date)) or []

        named = [v for v in cands if p.bill in v["bills_in_title"]]
        if named:
            cands, match = named, "title names this bill"
        elif not cands:
            match = "no video found"
        elif len(cands) == 1:
            match = "single video"
        elif family(p.committee or "") in AMBIGUOUS_FAMILIES:
            match = f"{len(cands)} divisions - pick manually"
        else:
            match = f"{len(cands)} videos that day - pick manually"
        stats[match.split(" -")[0].split(" that")[0]] += 1

        v = cands[0] if len(cands) == 1 or named else None
        off = predicted_offset(p.sched_time, v["start_eastern"]) if v else None

        out.append({
            "bill": p.bill,
            # Which chamber. The manifest covers both now, and without this
            # there is no way to tell a Senate row from a House one, or to see
            # that Senate matching is failing while the totals look healthy.
            "body": p.body,
            "committee": p.committee,
            "proceeding": p.kind,
            "sched_date": p.sched_date,
            "sched_time": p.sched_time,
            "venue": p.venue,
            "tier": p.confidence,
            "bills_in_slot": p.cohort_size,
            "match": match,
            "video_id": v["video_id"] if v else "",
            "video_title": v["title"] if v else "",
            "stream_start": v["start_eastern"][11:19] if v else "",
            "predicted_offset": hhmmss(off),
            "watch_url": (f"https://www.youtube.com/watch?v={v['video_id']}&t={max(off - 300, 0)}s"
                          if v and off is not None else ""),
            "candidates": " | ".join(c["title"] for c in cands) if len(cands) > 1 else "",
            "observed_start": "",
            "observed_end": "",
            "notes": "",
        })

    # If nothing was named, fall back to the file about to be overwritten.
    # Hand-marked times have now been lost twice by a rebuild that simply did
    # not know about them -- once when a later matching run replaced the
    # manifest, and once when build_all.py re-ran this without the flag. A
    # default that preserves them makes forgetting harmless; the flag is for
    # reading marks out of some OTHER file.
    keep = a.keep_marks
    if not keep:
        for c in (Path(a.out), Path(a.out).with_suffix(".xlsx")):
            if c.exists():
                keep = str(c)
                break
    marks = load_marks(keep) if keep else {}
    if marks and not a.keep_marks:
        print(f"  {len(marks)} hand-marked times found in {keep}; keeping them")

    # ground_truth.csv is the record and outranks anything in an old manifest.
    # It is keyed by (video, bill, kind) rather than by date, because the video
    # is what a person watched; map that back onto this manifest's rows.
    gt = Path("ground_truth.csv")
    if gt.exists():
        byvid = {}
        for r in read_any(gt):
            st = as_clock(r.get("observed_start"))
            if not st:
                continue
            k = (str(r.get("video_id") or ""),
                 str(r.get("bill") or "").upper(),
                 str(r.get("kind") or "").lower())
            byvid[k] = (st, as_clock(r.get("observed_end")),
                        str(r.get("notes") or ""))
        matched = 0
        for r in out:
            k = (r.get("video_id") or "", r["bill"].upper(),
                 (r["proceeding"] or "").lower())
            if k in byvid:
                r["observed_start"], r["observed_end"], nt = byvid[k]
                if nt:
                    r["notes"] = nt
                matched += 1
        print(f"  {len(byvid)} marks in ground_truth.csv, {matched} placed on "
              "this manifest's rows")
        if matched < len(byvid):
            print(f"  ({len(byvid) - matched} name a video this manifest does "
                  "not -- see ground_truth.py --check)")
    kept = 0
    if marks:
        for r in out:
            k = (r["bill"].upper(), r["sched_date"],
                 (r["proceeding"] or "").lower())
            if k in marks:
                r["observed_start"], r["observed_end"], nt = marks[k]
                if nt:
                    r["notes"] = nt
                kept += 1

    out.sort(key=lambda r: (r["sched_date"], r["sched_time"] or "99:99", r["bill"]))
    with open(a.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)

    if marks:
        print(f"\ncarried {kept} of {len(marks)} hand-marked times forward "
              f"from {keep}")
        if kept < len(marks):
            missed = [k for k in marks
                      if k not in {(r["bill"].upper(), r["sched_date"],
                                    (r["proceeding"] or "").lower())
                                   for r in out}]
            print(f"  {len(missed)} did not match a row in the new manifest. "
                  "First three:")
            for k in missed[:3]:
                print(f"    {k[0]} {k[2]} on {k[1]}")
            print("  Those proceedings are not in the new docket parse or fall "
                  "outside\n  the video window.")
            if keep == a.out:
                bak = Path(a.out).with_suffix(".marks-backup.csv")
                import shutil as _sh
                _sh.copy(a.out, bak)
                print(f"  {a.out} is about to be overwritten, so a copy is at "
                      f"{bak.name}.")

    print(f"\nWrote {a.out}: {len(out):,} rows\n")
    print("Video matching:")
    for k, v in sorted(stats.items(), key=lambda kv: -kv[1]):
        print(f"  {v:6,}  {k}")

    ready = sum(1 for r in out if r["watch_url"])
    print(f"\n{ready:,} rows have a direct watch link, opening 5 minutes before")
    print("the predicted start. Open one, find where the chair takes the bill up,")
    print("and put that elapsed time in observed_start.\n")
    print("Start with rows where tier is A-unique-slot -- those calibrate drift.")
    print("Then do one whole C-shared-slot executive session in a single sitting.")


if __name__ == "__main__":
    main()
