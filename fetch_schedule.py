#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-08.8
"""
What each committee is meeting about next, and which bills at what time.

    python3 fetch_schedule.py --probe        # the event list only, one request
    python3 fetch_schedule.py                # the list, then each event's bills
    python3 fetch_schedule.py --reparse      # rebuild from the cache, no network

Writes schedule.json and caches every event page under schedule_pages/.

WHY THIS AND NOT THE CALENDAR

The calendars give the hearings of a session that has happened, out of PDFs
already on this disk -- that is calendar_meetings.py. This is the other half:
what is scheduled NEXT, which is the half a person needs to decide whether to
turn up and speak.

The General Court publishes it twice. dailyschedule.aspx is a FullCalendar
page, and behind it is the thing worth having:

    GET /house/schedule/CalendarWS.asmx/GetEvents

A JSON web service. No parameters, no __VIEWSTATE, no postback -- which makes
it unlike almost everything else on this site. One request returns every
scheduled meeting:

    {"title": "House Ways and Means : GP, Room 234",
     "start": "2026-09-10T10:00:00", "end": "2026-09-10T16:30:00",
     "backgroundColor": "#2980B9",
     "url": "eventDetails.aspx?event=3027&et=1"}

THE COLOUR IS THE KIND, and that is the page's own legend saying so, not an
inference: "BLUE = Hearing | GREEN = Meeting | ORANGE = Executive Session |
RED = Committee of Conference". The title carries ==CANCELLED== and
==REVISED== inline, the same markers the docket writes as ==FLAG==.

Then one request per event gives the bills at their times:

    Date Sep 10, 2026 - 10:00 AM to 04:30 PM - Granite Place, Room 234
    HOUSE WAYS AND MEANS
      10:00 AM  HB1648  providing property tax exemptions for qualifying residences.
      10:00 AM  HB1787  modifying the statewide education property tax.

ONE SITTING CAN BE LISTED TWICE

Event 3027 comes back as both "House Ways and Means" in blue with et=1 and
"Ways and Means" in green with et=2 -- the same room, the same three bills,
the same morning. That is the service making a real distinction rather than
repeating itself: the sitting is a hearing and it is also a meeting. 87
distinct event ids across 88 rows, so it is rare. Anything
presenting this should key on the event id and keep the more specific kind,
not print the morning twice.

WHAT IT COSTS

One request for the whole schedule and one per event. About forty events were
listed out of session; in session it will be tens a week. An
event already cached is never asked for again, so a nightly run costs the
list plus whatever is new.

This is the address that has blocked this project twice, so: one request at a
time, a delay between each, a hard --limit, and three consecutive failures
ends the run.
"""

import argparse
import json
import re
import refusal
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

UA = {"User-Agent": "granite-record/1.0 (civic transparency project; "
                    "contact@graniterecord.org)"}
# The .asmx endpoint answers HTTP 500 to a plain GET and 200 to the one the
# page's own jQuery makes. Its $.ajax call sets contentType and dataType, so
# jQuery sends Content-Type: application/json and X-Requested-With, and an
# ASP.NET script service refuses to serialise JSON without them. Doing what
# the browser does, which is the same rule as posting __VIEWSTATE back.
JSON_HEADERS = dict(UA, **{"Content-Type": "application/json; charset=utf-8",
                           "Accept": "application/json, text/javascript, */*",
                           "X-Requested-With": "XMLHttpRequest"})
BASE = "https://gc.nh.gov/house/schedule/"
EVENTS = BASE + "CalendarWS.asmx/GetEvents"
CACHE = Path("schedule_pages")

# From the legend printed at the top of dailyschedule.aspx.
# #D68100 is the orange the service actually sends; the others are kept
# because the legend names four colours and only three have been seen so far.
# An unmapped colour is reported as the hex rather than guessed at.
KIND = {"#2980B9": "hearing", "#66A362": "meeting",
        "#D68100": "executive session", "#E8A33D": "executive session",
        "#F39C12": "executive session",
        "#C0392B": "committee of conference", "#E74C3C": "committee of conference"}

FLAG = re.compile(r"^\s*(?:==\s*([A-Z ]+?)\s*==\s*)+")
TITLE = re.compile(r"^(.*?)\s*:\s*(.*)$")
EVENT_ID = re.compile(r"[?&]event=(\d+)", re.I)
BILL = re.compile(r"\b(HB|SB|CACR|HR|SR|HCR|SCR)\s*0*(\d{1,4})\b", re.I)
TIME12 = re.compile(r"^(\d{1,2}):(\d{2})\s*([AP])M$", re.I)


def get(url, timeout=45, tries=3, delay=3.0, headers=None):
    """One request, with the retry this server has taught us it needs."""
    last = None
    for n in range(tries):
        try:
            req = urllib.request.Request(url, headers=headers or UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace"), None
        except Exception as e:                      # noqa: BLE001
            last = f"{type(e).__name__}: {e}"
            if n + 1 < tries:
                time.sleep(delay * (n + 2))
    return None, last


class Rows(HTMLParser):
    """The event page's one table: a time, a bill number, a title."""

    def __init__(self):
        super().__init__()
        self.rows, self.cur, self.cell, self.in_cell = [], [], "", False

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.cur = []
        elif tag in ("td", "th"):
            self.in_cell, self.cell = True, ""

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self.cur.append(re.sub(r"\s+", " ", self.cell).strip())
            self.in_cell = False
        elif tag == "tr" and self.cur:
            self.rows.append(self.cur)
            self.cur = []

    def handle_data(self, data):
        if self.in_cell:
            self.cell += data


def _24h(s):
    m = TIME12.match(s.strip())
    if not m:
        return ""
    hh = int(m.group(1)) % 12
    if m.group(3).upper() == "P":
        hh += 12
    return f"{hh:02d}:{m.group(2)}"


def parse_event(html):
    """(the details, the bills) out of one event page."""
    text = re.sub(r"<[^>]+>", "\n", html)
    text = re.sub(r"[ \t]+", " ", text)
    det = {}
    for key, label in (("date", "Date"), ("time", "Time"),
                       ("building", "Building"), ("room", "Room")):
        m = re.search(rf"^\s*{label}\s*$\s*^\s*(.+?)\s*$", text, re.M)
        if m:
            det[key] = m.group(1).strip()
    p = Rows()
    p.feed(html)
    bills = []
    for r in p.rows:
        if len(r) < 2:
            continue
        when = _24h(r[0])
        m = BILL.search(r[1])
        if not (when and m):
            continue
        bills.append({"time": when,
                      "bill": f"{m.group(1).upper()}{int(m.group(2))}",
                      "title": (r[2] if len(r) > 2 else "").strip()})
    return det, bills


def split_title(raw):
    """"==CANCELLED==HOUSE WAYS AND MEANS : GP, Room 234" in its three parts."""
    flags = []
    while True:
        m = re.match(r"\s*==\s*([A-Za-z ]+?)\s*==\s*", raw)
        if not m:
            break
        flags.append(m.group(1).strip().lower())
        raw = raw[m.end():]
    m = TITLE.match(raw.strip())
    if m:
        return m.group(1).strip(), m.group(2).strip(), flags
    return raw.strip(), "", flags


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true",
                    help="the event list only: one request, nothing else")
    ap.add_argument("--reparse", action="store_true",
                    help="rebuild from schedule_pages/, no network")
    ap.add_argument("--limit", type=int, default=400)
    ap.add_argument("--delay", type=float, default=8.0,
                    help="seconds between event pages (default 8)")
    ap.add_argument("--out", default="schedule.json")
    a = ap.parse_args()
    refusal.check("The schedule fetch")

    CACHE.mkdir(exist_ok=True)
    listing = CACHE / "_events.json"

    if a.reparse:
        if not listing.exists():
            sys.exit("no cached event list; run without --reparse first")
        raw = listing.read_text(encoding="utf-8")
    else:
        print(f"asking {EVENTS}")
        raw, err = get(EVENTS, headers=JSON_HEADERS)
        if err:
            sys.exit(f"the schedule did not answer: {err}")
        listing.write_text(raw, encoding="utf-8")

    payload = json.loads(raw)
    events = json.loads(payload["d"]) if isinstance(payload.get("d"), str) \
        else payload.get("d", [])
    print(f"{len(events):,} scheduled events")

    out, todo = [], []
    for e in events:
        committee, where, flags = split_title(e.get("title", ""))
        m = EVENT_ID.search(e.get("url", "") or "")
        rec = {"committee": committee, "where": where, "flags": flags,
               "start": e.get("start", ""), "end": e.get("end", ""),
               "kind": KIND.get((e.get("backgroundColor") or "").upper(),
                                KIND.get(e.get("backgroundColor") or "", "")),
               "colour": e.get("backgroundColor", ""),
               "event": m.group(1) if m else "",
               "url": (BASE + e["url"]) if e.get("url") else "",
               "bills": []}
        out.append(rec)
        if rec["event"]:
            todo.append(rec)

    kinds = {}
    for r in out:
        kinds[r["kind"] or r["colour"]] = kinds.get(r["kind"] or r["colour"], 0) + 1
    print("by kind:", kinds)

    if a.probe:
        print("\nNothing else was asked for. The first five:")
        for r in out[:5]:
            print(f"  {r['start'][:16]}  {r['kind']:22} {r['committee'][:44]}")
        return

    fetched = cached = failed = 0
    run = 0
    for i, rec in enumerate(todo[:a.limit], 1):
        path = CACHE / f"event_{rec['event']}.html"
        if path.exists():
            html = path.read_text(encoding="utf-8", errors="replace")
            cached += 1
        else:
            html, err = get(rec["url"], delay=a.delay)
            if err:
                failed += 1
                run += 1
                print(f"  [{i}/{len(todo)}] event {rec['event']}: {err[:90]}")
                if run >= 3:
                    print("\nThree failures in a row. Stopping rather than "
                          "pushing at a server that is refusing.\n"
                          "python3 netcheck.py says why without making it worse.")
                    break
                continue
            run = 0
            path.write_text(html, encoding="utf-8")
            fetched += 1
            time.sleep(a.delay)
        det, bills = parse_event(html)
        rec["details"], rec["bills"] = det, bills
        if fetched and fetched % 10 == 0:
            print(f"  {i}/{len(todo)}  {fetched} fetched, {cached} cached")

    Path(a.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    n_bills = sum(len(r["bills"]) for r in out)
    print(f"\n{fetched} fetched, {cached} from cache, {failed} failed")
    print(f"{len(out):,} events, {n_bills:,} bill slots -> {a.out}")
    if not n_bills and fetched:
        print("\nEvery event page came back without a bill row. That is the "
              "shape having changed,\nnot an empty schedule -- look at one in "
              "schedule_pages/ before trusting this.")


if __name__ == "__main__":
    main()
