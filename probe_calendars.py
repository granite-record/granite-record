#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.1
"""
Read the calendar list instead of guessing at it.

    python3 probe_calendars.py              # 2026, one request
    python3 probe_calendars.py --year 2025  # two: one to load, one to switch
    python3 probe_calendars.py --raw        # also save the HTML

Nothing is written except with --raw. Nothing else is touched.

WHAT WAS WRONG

Calendar discovery guessed filenames. Two folder spellings, two ways of writing
"No", two day paddings, two extension cases, across thirty weeks: about a
thousand requests for files that mostly did not exist, which the General
Court's firewall correctly read as a directory scan and blocked the address
for.

Then it was made to learn the convention from a filename that had worked. That
was worse, because there is no convention. From the page itself:

    No 32 September 4 2026     space after No, day not padded
    No 31 August 28 2026       space
    No30 August 14 2026        no space
    No29 August 07 2026        no space, day padded
    No28 July 31 2026          no space, not padded

Five spellings in five consecutive entries. Any rule learned from one of them
misses the rest, which is why 2025 came back empty while its calendars sat
there in the dropdown.

WHAT IS ACTUALLY THERE

gc.nh.gov/house/calendars_journals lists every calendar and journal, by number
and date, for every year from 1997. And the link it builds gives the real name:

    viewer.aspx?fileName=calendars\\2026\\HC 32.pdf

"No 32 September 4 2026" is the label. "HC 32.pdf" is the file. The number in
the label is the number in the filename, so the list is not a hint about where
to look -- it is the answer.

WHAT THIS PROBE REPORTS

  every <select> on the page, with its name and how many options it has
  the first few options of each, with the value the page actually submits
  whether the year list needs a postback, and the fields it would need
  every viewer.aspx link, which is where the filename form is visible

Send that and the fetcher gets written against it: one request per year to list
them, then one per calendar to fetch it. No probing, nothing asked for that
does not exist.
"""

import argparse
import html
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

URL = "https://gc.nh.gov/house/calendars_journals/"
UA = {"User-Agent": "granite-record/1.0 (civic transparency project; "
                    "corrections@graniterecord.org)"}

SELECT = re.compile(r"<select\b(?P<attrs>[^>]*)>(?P<body>.*?)</select>", re.S | re.I)
OPTION = re.compile(r"<option\b(?P<attrs>[^>]*)>(?P<text>.*?)</option>", re.S | re.I)
ATTR = re.compile(r"(\w[\w:-]*)\s*=\s*[\"']([^\"']*)[\"']")
HIDDEN = re.compile(r"<input\b[^>]*type=[\"']hidden[\"'][^>]*>", re.I)
VIEWER = re.compile(r"viewer\.aspx\?fileName=([^\"'&<>\s][^\"'<>]*)", re.I)
FORM = re.compile(r"<form\b([^>]*)>", re.I)


def get(url, data=None):
    req = urllib.request.Request(url, data=data, headers=dict(
        UA, **({"Content-Type": "application/x-www-form-urlencoded"} if data else {})))
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", errors="replace")


def attrs(s):
    return {k.lower(): v for k, v in ATTR.findall(s or "")}


def show(page, label):
    print(f"\n{'=' * 70}\n{label}\n{'=' * 70}")

    for m in FORM.finditer(page):
        a = attrs(m.group(1))
        print(f"\n  <form action={a.get('action', '(same page)')!r} "
              f"method={a.get('method', 'get')!r}>")

    fields = {}
    for m in HIDDEN.finditer(page):
        a = attrs(m.group(0))
        if a.get("name"):
            fields[a["name"]] = a.get("value", "")
    if fields:
        print(f"\n  {len(fields)} hidden fields, which is how ASP.NET carries "
              "state:")
        for k, v in list(fields.items())[:6]:
            print(f"    {k:<26}{len(v):,} chars"
                  + (f"  {v[:40]}" if len(v) < 60 else ""))

    for m in SELECT.finditer(page):
        a = attrs(m.group("attrs"))
        opts = [(attrs(o.group("attrs")).get("value", ""),
                 html.unescape(re.sub(r"\s+", " ", o.group("text"))).strip())
                for o in OPTION.finditer(m.group("body"))]
        name = a.get("name") or a.get("id") or "(unnamed)"
        auto = "autopostback" in " ".join(a.values()).lower() or \
               "__dopostback" in (a.get("onchange") or "").lower()
        print(f"\n  <select name={name!r}>  {len(opts)} options"
              + ("   posts back on change" if auto else ""))
        for v, txt in opts[:6]:
            print(f"    value={v!r:<28} {txt}")
        if len(opts) > 6:
            print(f"    ... {len(opts) - 6} more")

    links = [urllib.parse.unquote(x) for x in VIEWER.findall(page)]
    if links:
        print(f"\n  {len(links)} viewer.aspx links. The filename is the answer:")
        for x in links[:4]:
            print(f"    {x}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", help="also switch the year, to see what changes")
    ap.add_argument("--raw", action="store_true", help="save the HTML")
    a = ap.parse_args()

    print(f"fetching {URL}")
    try:
        page = get(URL)
    except Exception as e:
        sys.exit(f"failed: {type(e).__name__}: {e}")
    if a.raw:
        Path("probe_calendars.html").write_text(page, encoding="utf-8")
        print("wrote probe_calendars.html")
    show(page, "AS LOADED")

    if a.year:
        # One postback, to find out whether another year can be listed without
        # a browser. If this works, every year back to 1997 is two requests.
        fields = {}
        for m in HIDDEN.finditer(page):
            at = attrs(m.group(0))
            if at.get("name"):
                fields[at["name"]] = at.get("value", "")
        ysel = None
        for m in SELECT.finditer(page):
            at = attrs(m.group("attrs"))
            nm = at.get("name") or ""
            body = m.group("body")
            if re.search(r"\b(19|20)\d{2}\b", body) and "January" not in body:
                ysel = nm
        if not ysel:
            print("\n  Could not tell which select is the year. Send --raw.")
            return
        fields[ysel] = a.year
        fields.setdefault("__EVENTTARGET", ysel)
        fields.setdefault("__EVENTARGUMENT", "")
        print(f"\n  posting {ysel}={a.year} ...")
        try:
            page2 = get(URL, urllib.parse.urlencode(fields).encode())
            show(page2, f"AFTER SWITCHING TO {a.year}")
        except Exception as e:
            print(f"  postback failed: {type(e).__name__}: {e}")
            print("  If the year cannot be switched this way, the list for "
                  "earlier\n  years may live at its own address instead.")


if __name__ == "__main__":
    main()
