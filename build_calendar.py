#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-18.1
"""
The General Court's week, as one small file per week.

    python3 build_calendar.py --site site

WHY A FILE PER WEEK

The home page used to show a fixed fortnight, cut from home.json, and there
was no way to look at any other. Asked for on 18 September: "the calendar can
be more of a week to week thing where you can tap back and forth to view all
the hearings and sessions this week, next week, the previous week, etc."

Paging needs the weeks to be reachable, and there are 11,020 proceedings from
2025 onward across 67 weeks -- a median of 112 a week and 609 in the busiest.
That is about a megabyte if it travels as one file, on a page whose whole data
budget today is 20 KB. So each week is its own file and a reader fetches the
one they turned to, which is a dozen kilobytes. The site is files on a CDN;
this is what that constraint is for.

  site/cal/2026-W40.json    one week, its days, and what sat on each
  site/cal/index.json       which weeks exist, so the arrows know where to stop

WHAT COUNTS AS A WEEK'S BUSINESS

Every proceedings.csv row with a date: committee hearings, executive and work
sessions, and floor debates. proceedings.csv is the one table and this reads
it through proceedings.py like everything else -- it is not a sixth reader of
the files behind it.

A row names a BILL, so a committee that took up nine bills in one sitting is
nine rows. They are grouped back into sittings here -- by day, committee and
time -- because that is what a reader is looking at: a meeting with a list of
bills, not nine meetings.
"""

import argparse
import datetime
import json
from collections import OrderedDict, defaultdict
from pathlib import Path

import proceedings

# From 2025: the current term and the one before it. Earlier terms are in the
# record and reachable through a bill, but nobody pages a calendar back to
# 1998, and 67 weeks of files is enough to carry the arrows.
FROM = "2025-01-01"


def week_of(iso_date):
    """('2026-W40', the Monday) for a date, or None if it will not parse."""
    try:
        d = datetime.date.fromisoformat(iso_date[:10])
    except (ValueError, TypeError):
        return None
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}", d - datetime.timedelta(days=d.isoweekday() - 1)


def titles_for(site):
    """{term: {bill id: (number as printed, title)}} from the built indexes."""
    out = {}
    idx = site / "idx"
    if not idx.exists():
        return out
    for f in idx.glob("*.json"):
        try:
            rows = json.loads(f.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        out[f.stem] = {r.get("id"): (r.get("n") or r.get("id"), r.get("title") or "")
                       for r in rows if r.get("id")}
    return out


def committee_codes(site):
    """{committee name folded: code} so a sitting links to its own page."""
    f = site / "committees.json"
    if not f.exists():
        return {}
    try:
        return {c["name"].strip().lower(): c["code"]
                for c in json.loads(f.read_text(encoding="utf-8"))
                if c.get("name") and c.get("code")}
    except (ValueError, OSError):
        return {}


def build(site):
    rows = [r for r in proceedings.load()
            if (r.get("date") or "") >= FROM]
    titles = titles_for(site)
    codes = committee_codes(site)

    # (week, day, committee, time) -> the sitting, with its bills
    weeks = defaultdict(lambda: defaultdict(OrderedDict))
    for r in rows:
        w = week_of(r.get("date") or "")
        if not w:
            continue
        key = w[0]
        day = r["date"][:10]
        floor = (r.get("kind") or "").strip().lower() == "floor debate"
        cm = (r.get("committee") or "").strip()
        where = ("Floor" if floor else cm) or "Not named"
        slot = (where, (r.get("time") or "").strip(), (r.get("kind") or "").strip())
        sit = weeks[key][day].get(slot)
        if sit is None:
            sit = weeks[key][day][slot] = {
                "what": r.get("kind") or "",
                "body": r.get("body") or "",
                "time": (r.get("time") or "").strip(),
                "where": where,
                "venue": (r.get("venue") or "").strip(),
                "code": "" if floor else codes.get(cm.lower(), ""),
                "bills": [],
            }
        term = r.get("term") or ""
        bid = r.get("bill") or ""
        n, title = titles.get(term, {}).get(bid, (bid, ""))
        if bid and not any(b["id"] == bid for b in sit["bills"]):
            sit["bills"].append({"id": bid, "n": n, "term": term,
                                 "title": title[:120],
                                 "video": r.get("video_id") or ""})

    out = site / "cal"
    out.mkdir(parents=True, exist_ok=True)
    # SILENCE IS NOT SUCCESS: a calendar that writes nothing and exits zero is
    # a home page with dead arrows and no way to tell from the build log.
    assert weeks, f"no proceedings dated {FROM} or later; nothing to page through"

    index, written = [], 0
    for key in sorted(weeks):
        days = weeks[key]
        monday = week_of(min(days))[1]
        payload = {
            "week": key,
            "starts": monday.isoformat(),
            "ends": (monday + datetime.timedelta(days=6)).isoformat(),
            "days": [{"date": d,
                      "sittings": list(days[d].values())}
                     for d in sorted(days)],
        }
        n = sum(len(s["sittings"]) for s in payload["days"])
        (out / f"{key}.json").write_text(json.dumps(payload, separators=(",", ":")),
                                         encoding="utf-8")
        index.append({"week": key, "starts": payload["starts"],
                      "sittings": n,
                      "bills": sum(len(x["bills"]) for d in payload["days"]
                                   for x in d["sittings"])})
        written += 1

    (out / "index.json").write_text(json.dumps(index, separators=(",", ":")),
                                    encoding="utf-8")
    size = sum(f.stat().st_size for f in out.glob("*.json"))
    big = max(index, key=lambda x: x["sittings"])
    print(f"  {written} weeks -> {out}/ ({size/1024:.0f} KB in all, "
          f"{size/written/1024:.1f} KB a week)")
    print(f"  {sum(x['sittings'] for x in index):,} sittings, "
          f"{sum(x['bills'] for x in index):,} bill-sittings; "
          f"busiest {big['week']} with {big['sittings']}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    a = ap.parse_args()
    return build(Path(a.site))


if __name__ == "__main__":
    raise SystemExit(main())
