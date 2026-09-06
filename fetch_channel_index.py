#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.1
"""
Step 1 of verification: pull the NH House/Senate YouTube video index.

Answers, without watching any video:
  - Does the title convention hold across every committee?
  - Do archived videos still carry a livestream start time?
  - Does a committee ever post two videos for the same day?
  - Does one video ever appear to cover two committees?

Usage:
    python fetch_channel_index.py --key YOUR_API_KEY --chamber house
    python fetch_channel_index.py --key YOUR_API_KEY --chamber senate --start 2025-01-01 --end 2025-06-30

Uses only the Python standard library. Nothing to install.
"""

import argparse
import csv
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone

API = "https://www.googleapis.com/youtube/v3/"

CHANNELS = {
    "house":  ("UCxqjz56akoWRL_5vyaQDtvQ", "NH House of Representatives Committee Streaming"),
    "senate": ("UCjBZdtrjRnQdmg-2MPMiWrA", "New Hampshire Senate Livestream"),
}

# "House Election Law (03/07/2025)"  and older  "House Election Law (01/24/23)"
# "House Election Law (03/07/2025)" and the older two-digit-year form, plus a
# trailing qualifier the 2026 season introduced: "... (01/12/2026) (Full Stream)".
# Real titles are less tidy than they look. Alongside the clean
# "House Election Law (03/07/2025)" there are trailing qualifiers,
# "(01/12/2026) (Full Stream)", and unclosed parentheses,
# "Committee of Conference on SB 534  (05/22/2026". The last of those matter:
# a conference video names its bill outright, which is exact alignment with no
# transcript at all, so losing them to a missing bracket is expensive.
TITLE_RE = re.compile(
    r"^\s*(?P<prefix>House|Senate)?\s*(?P<committee>.+?)\s*"
    r"\(\s*(?P<m>\d{1,2})/(?P<d>\d{1,2})/(?P<y>\d{2,4})\s*\)?"
    r"(?:\s*\([^)]*\)?)?\s*$",
    re.IGNORECASE,
)

# Some videos carry no date but name the bill outright, which is better than a
# date: "Committee of Conference on HB221".
BILL_TITLE_RE = re.compile(
    r"^\s*(?P<committee>.*?(?:Committee of Conference|Work Session).*?)\s+on\s+"
    r"(?P<bills>(?:HB|SB|CACR|HR|SR|HCR|SCR)\s?\d+(?:\s*,\s*(?:HB|SB|CACR|HR|SR|HCR|SCR)?\s?\d+)*)"
    r"\s*$", re.IGNORECASE)


def call(endpoint, key, **params):
    params["key"] = key
    url = API + endpoint + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        print("\n--- YouTube API error ---", file=sys.stderr)
        if e.code == 400 and "API key not valid" in body:
            print("Your API key was rejected. Check for stray spaces when you pasted it.",
                  file=sys.stderr)
        elif e.code == 403 and "has not been used" in body:
            print("The YouTube Data API v3 is not enabled for this project yet.\n"
                  "Go to console.cloud.google.com > APIs & Services > Library,\n"
                  "search 'YouTube Data API v3', and press Enable. Wait a minute, then retry.",
                  file=sys.stderr)
        elif e.code == 403 and "quota" in body.lower():
            print("Daily quota exhausted. It resets at midnight Pacific time.", file=sys.stderr)
        else:
            print(body[:800], file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"\nCould not reach YouTube: {e.reason}", file=sys.stderr)
        sys.exit(1)


def uploads_playlist(channel_id, key):
    data = call("channels", key, part="contentDetails", id=channel_id)
    items = data.get("items") or []
    if not items:
        print(f"No channel found for id {channel_id}.", file=sys.stderr)
        sys.exit(1)
    return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]


def list_videos(playlist_id, key, start, end):
    """Walk the uploads playlist newest-first, stopping once we pass the start date."""
    vids, token, pages = [], None, 0
    while True:
        page = call("playlistItems", key, part="contentDetails,snippet",
                    playlistId=playlist_id, maxResults=50,
                    **({"pageToken": token} if token else {}))
        pages += 1
        oldest_on_page = None
        for it in page.get("items", []):
            pub = it["contentDetails"].get("videoPublishedAt")
            if not pub:
                continue
            d = datetime.fromisoformat(pub.replace("Z", "+00:00")).date()
            oldest_on_page = d
            if start <= d <= end:
                vids.append({
                    "video_id": it["contentDetails"]["videoId"],
                    "title": it["snippet"]["title"],
                    "published_at": pub,
                })
        sys.stderr.write(f"\r  scanned {pages} page(s), {len(vids)} in range...")
        sys.stderr.flush()
        token = page.get("nextPageToken")
        if not token:
            break
        if oldest_on_page and oldest_on_page < start:
            break
    sys.stderr.write("\n")
    return vids


def add_details(vids, key):
    """Batch 50 ids per call. This is where actualStartTime comes from."""
    for i in range(0, len(vids), 50):
        chunk = vids[i:i + 50]
        data = call("videos", key, part="liveStreamingDetails,contentDetails",
                    id=",".join(v["video_id"] for v in chunk))
        by_id = {it["id"]: it for it in data.get("items", [])}
        for v in chunk:
            it = by_id.get(v["video_id"], {})
            live = it.get("liveStreamingDetails", {}) or {}
            v["actual_start_utc"] = live.get("actualStartTime", "")
            v["actual_end_utc"] = live.get("actualEndTime", "")
            v["duration_iso"] = (it.get("contentDetails", {}) or {}).get("duration", "")
        sys.stderr.write(f"\r  details for {min(i + 50, len(vids))}/{len(vids)}...")
        sys.stderr.flush()
    sys.stderr.write("\n")


def parse_title(title):
    m = TITLE_RE.match(title)
    if not m:
        return None, None
    y = int(m.group("y"))
    y += 2000 if y < 100 else 0
    try:
        d = datetime(y, int(m.group("m")), int(m.group("d"))).date()
    except ValueError:
        return None, None
    return m.group("committee").strip(), d


def _second_sunday_march(y):
    d = date(y, 3, 1)
    d += timedelta(days=(6 - d.weekday()) % 7)      # first Sunday
    return d + timedelta(days=7)


def _first_sunday_november(y):
    d = date(y, 11, 1)
    return d + timedelta(days=(6 - d.weekday()) % 7)


def to_eastern_clock(iso_utc):
    """UTC -> New Hampshire local time, with the real DST rule.

    An earlier version treated any month from March to November as daylight
    time. That is wrong for the first week of March and the last three weeks of
    November, and the House sits through both. On 2026-03-05 it put every
    stream an hour late, which made roll call timestamps look useless when they
    are in fact accurate to a few seconds.

    US rule since 2007: daylight time runs from 2 a.m. on the second Sunday in
    March to 2 a.m. on the first Sunday in November.
    """
    if not iso_utc:
        return ""
    dt = datetime.fromisoformat(iso_utc.replace("Z", "+00:00")).astimezone(timezone.utc)
    # Decide using the provisional standard-time date, which is safe except in
    # the one ambiguous hour at each transition.
    est = datetime.fromtimestamp(dt.timestamp() - 5 * 3600, timezone.utc)
    d, y = est.date(), est.year
    start, end = _second_sunday_march(y), _first_sunday_november(y)
    daylight = (start < d < end) or \
               (d == start and est.hour >= 2) or (d == end and est.hour < 1)
    offset = -4 if daylight else -5
    local = dt.timestamp() + offset * 3600
    return datetime.fromtimestamp(local, timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True, help="YouTube Data API v3 key")
    ap.add_argument("--chamber", choices=["house", "senate"], default="house")
    ap.add_argument("--start", default="2025-01-01")
    ap.add_argument("--end", default="2025-06-30")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    start = datetime.strptime(a.start, "%Y-%m-%d").date()
    end = datetime.strptime(a.end, "%Y-%m-%d").date()
    chan_id, chan_name = CHANNELS[a.chamber]
    out = a.out or f"videos_{a.chamber}_{a.start}_to_{a.end}.csv"

    print(f"Channel : {chan_name}")
    print(f"Window  : {start} to {end}\n")

    print("Listing videos...")
    pl = uploads_playlist(chan_id, a.key)
    vids = list_videos(pl, a.key, start, end)
    if not vids:
        print("No videos found in that window. Try widening the dates.")
        return

    print("Fetching start times...")
    add_details(vids, a.key)

    for v in vids:
        cmte, d = parse_title(v["title"])
        # A title that names a bill but carries no date, e.g. "Committee of
        # Conference on SB599", is still fully usable: the whole recording is
        # that one bill. These stream live, so the publish date is the meeting
        # date. Recovering them is worth it -- conference committees are where
        # the final compromise on a contested bill gets written.
        if not cmte:
            m = BILL_TITLE_RE.match(v["title"])
            if m and v.get("published_at"):
                try:
                    d = datetime.fromisoformat(
                        v["published_at"].replace("Z", "+00:00")).date()
                    cmte = m.group("committee").strip()
                    v["date_from"] = "published"
                except ValueError:
                    pass
        v["parsed_committee"] = cmte or ""
        v["parsed_date"] = d.isoformat() if d else ""
        v["title_parsed"] = "yes" if cmte else "NO"
        v.setdefault("date_from", "title")
        v["has_start_time"] = "yes" if v["actual_start_utc"] else "NO"
        v["start_eastern"] = to_eastern_clock(v["actual_start_utc"])

    cols = ["video_id", "title", "title_parsed", "parsed_committee", "parsed_date",
            "date_from",
            "has_start_time", "start_eastern", "actual_start_utc", "actual_end_utc",
            "duration_iso", "published_at"]
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for v in sorted(vids, key=lambda x: x["published_at"]):
            w.writerow(v)

    # ----------------------------------------------------------------
    n = len(vids)
    parsed = sum(1 for v in vids if v["title_parsed"] == "yes")
    timed = sum(1 for v in vids if v["has_start_time"] == "yes")

    print("\n" + "=" * 62)
    print("WHAT THIS TELLS US")
    print("=" * 62)
    print(f"\nVideos found: {n}   ->  saved to {out}\n")

    pub = sum(1 for v in vids if v.get("date_from") == "published")
    print(f"1. Title convention holds for {parsed}/{n} ({parsed/n:.0%})")
    if pub:
        print(f"   {pub} had no date in the title; the publish date was used "
              "(these name their bill outright)")
    if parsed < n:
        print("   Titles that did NOT parse (the matcher needs to handle these):")
        for v in vids:
            if v["title_parsed"] == "NO":
                print(f"     - {v['title']}")
    print()

    print(f"2. Livestream start time present on {timed}/{n} ({timed/n:.0%})")
    if timed < n:
        print("   IMPORTANT: videos without a start time cannot be anchored by")
        print("   scheduled time. Those fall back to transcript search alone.")
    print()

    pairs = Counter((v["parsed_committee"], v["parsed_date"])
                    for v in vids if v["title_parsed"] == "yes")
    dupes = {k: c for k, c in pairs.items() if c > 1}
    print(f"3. Committee-days with more than one video: {len(dupes)}")
    for (c, d), n_ in sorted(dupes.items())[:15]:
        print(f"     {d}  {c}  -> {n_} videos")
    if dupes:
        print("   The matcher must pick among these, not assume one video per day.")
    print()

    byday = defaultdict(set)
    for v in vids:
        if v["title_parsed"] == "yes":
            byday[v["parsed_date"]].add(v["parsed_committee"])
    busiest = sorted(byday.items(), key=lambda kv: -len(kv[1]))[:5]
    print("4. Busiest days (committees streaming simultaneously):")
    for d, cs in busiest:
        print(f"     {d}: {len(cs)} committees")
    print("   Cross-check these against the docket: if the docket shows a committee")
    print("   meeting on one of these days with no matching video, that is a gap.")
    print()

    print("NEXT: open the CSV, then spot-check 3 rows against the workbook to")
    print("confirm the start times look sane before doing the full clip pass.")


if __name__ == "__main__":
    main()
