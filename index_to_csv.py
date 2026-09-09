#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-09.1
"""
channel_index_full.json -> the video CSV shape build_manifest.py reads.

    python3 index_to_csv.py --year 2023 2024 --out videos_2023_2024.csv

The 2025 and 2026 video lists were produced by a YouTube search that recorded
the real stream start; the channel walk that found the other 3,513 recorded
only id, title and published time. That difference matters for PREDICTING AN
OFFSET inside a recording and not at all for deciding WHICH recording a
hearing is on, which is the date and the committee -- both of which are in the
title.

So start_eastern is left empty here and the match still works. A bill gets its
recording; the moment within it waits for captions.
"""
import argparse
import csv
import json
import re
from pathlib import Path

# "House Commerce and Consumer Affairs (09/09/2026)" and the older
# "Rules (12/16/20)". Two-digit years are the 2020-2022 convention and were
# what made a naive four-digit pattern read those years as 0% parseable.
DATE = re.compile(r"\((?P<m>\d{1,2})/(?P<d>\d{1,2})(?:/(?P<y>\d{2,4}))?")
# Some titles put the date outside the brackets: "House Session 03/17/2022".
BARE = re.compile(r"\b(?P<m>\d{1,2})/(?P<d>\d{1,2})/(?P<y>\d{2,4})\b")

FIELDS = ["video_id", "title", "title_parsed", "parsed_committee",
          "parsed_date", "has_start_time", "start_eastern",
          "actual_start_utc", "actual_end_utc", "duration_iso", "published_at"]


def parsed(title, published):
    m = DATE.search(title) or BARE.search(title)
    if not m:
        return None, None
    mo, day = int(m.group("m")), int(m.group("d"))
    y = m.group("y")
    if y:
        year = int(y)
        if year < 100:
            year += 2000
    else:
        # No year in the title -- 166 of the 2022 recordings. The publication
        # date is the only other evidence, and a calendar published in
        # December for a January meeting is the one case where it is a year
        # out, so the month is compared before it is trusted.
        year = int(published[:4])
        if mo == 12 and published[5:7] == "01":
            year -= 1
    if not (1 <= mo <= 12 and 1 <= day <= 31):
        return None, None
    # Everything before the bracket is the committee -- WITHOUT the chamber,
    # because that is the convention the 2025/2026 CSVs already record and the
    # docket's own committee column follows: "House Education (01/12/2026)"
    # is parsed_committee "Education". Leaving the chamber on matched nothing
    # at all: 5,868 proceedings, 0 videos.
    cut = title[:m.start()].strip(" -–—:,")
    for ch in ("House ", "Senate ", "NH House ", "NH Senate "):
        if cut.startswith(ch):
            cut = cut[len(ch):]
            break
    return cut or None, f"{year:04d}-{mo:02d}-{day:02d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default="channel_index_full.json")
    ap.add_argument("--year", nargs="*", help="only these publication years")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    idx = json.loads(Path(a.index).read_text(encoding="utf-8"))
    want = set(a.year) if a.year else None
    rows, skipped = [], 0
    for chamber, d in idx.items():
        for v in d.get("videos", []):
            pub = v.get("published") or ""
            if want and pub[:4] not in want:
                continue
            title = (v.get("title") or "").strip()
            cmte, date = parsed(title, pub)
            if want and date and date[:4] not in want:
                # A December 2022 hearing published in January 2023 belongs to
                # the year it happened, not the year it was posted.
                pass
            if not cmte or not date:
                skipped += 1
                continue
            rows.append({
                "video_id": v.get("id") or v.get("video_id") or "",
                "title": title, "title_parsed": "yes",
                "parsed_committee": cmte, "parsed_date": date,
                "has_start_time": "no", "start_eastern": "",
                "actual_start_utc": "", "actual_end_utc": "",
                "duration_iso": "", "published_at": pub})

    with open(a.out, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows):,} videos written -> {a.out}")
    print(f"  {skipped:,} had no committee and date in the title and were left out")
    if not rows:
        raise SystemExit("Nothing was written. Check --year against the index.")


if __name__ == "__main__":
    main()
