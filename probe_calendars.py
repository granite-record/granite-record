#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.5
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

THE FILENAME FORM CHANGED; THE DIRECTORY DID NOT

Probed 6 September, two requests a year. The year list holds 30 options, 2026
back to 1997, and switching one lists that whole year at once: the document
select's option VALUES are the filenames.

    2026   36 documents   HC 32.pdf ... No30 August 14 2026.pdf
    2023   60 documents   No 51 December 29 2023.pdf
    2006   48 documents   No 67 November 30 2006.pdf

Journals live behind the same page on a second select, Calendar or Journal.
Two supplied journal links show the same drift:

    journals\\2021\\No 11 June 24 2021.pdf
    journals\\2003\\HJ No 21 09-04-2003.pdf

So the forms across eras are at least three: a short code and a number
(HC 32.pdf, 2026); "No" then number, month name, day, year (2006 and 2023); a
chamber prefix with a numeric MM-DD-YYYY date (2003 journals). Day padding is
not stable either -- 2023 writes December 08 and December 01, 2006 writes
November 9 and November 2 -- and 2026 alone carries two forms at once, its two
most recent entries having switched to HC NN.pdf while the rest below them
did not.

Journals confirmed 6 September with --type Journal. 2026 lists 16, as
HJ 16 August 19, 2026.pdf -- a comma, which no calendar form uses. 2003 lists
25, as HJ No 23 01-07-2004.pdf. A supplied link, HJ No 21 09-04-2003.pdf,
came back in that list exactly, so the path is confirmed end to end.

TWO THINGS IN THE 2003 LIST THAT A KEY CANNOT SURVIVE

    HJ No 23 01-07-2004.pdf     a 2004 date, filed under 2003
    HJ No 21 09-04-2003.pdf     and
    HJ No 21 06-30-2003.pdf     the same number twice in one year

So the issue number is not unique within a year, and the year folder does not
only hold that year's dates -- a session runs into January of the next one and
its journal stays with the session. (year, number) is therefore not a key for
anything. The filename is the only identifier this source offers, which is one
more reason to carry it verbatim rather than parse it into parts and rebuild
it later.

The directory shape -- {calendars|journals}\\{year}\\ behind one viewer.aspx at
/house/calendars_journals/ -- has held since at least 2003.

Which settles the archive question for this source. The filenames cannot be
constructed for any era, so a back-fill reuses this probe rather than needing
anything new: one postback per year to list it, one request per document to
fetch it. A two-year term is roughly 100 calendars and a similar number of
journals. The five spellings below are not a 2026 quirk to be worked around
but the normal state of this source across thirty years.

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

BASE = "https://gc.nh.gov/{chamber}/calendars_journals/"
# Kept as the default so anything importing URL still works. The Senate
# serves the same page at its own address and answered HTTP 500 to
# fetch_journals on 6 September, which is why --chamber exists.
URL = BASE.format(chamber="house")
UA = {"User-Agent": "granite-record/1.0 (civic transparency project; "
                    "contact@graniterecord.org)"}

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


def form_fields(page):
    """The hidden inputs ASP.NET uses to carry state between posts."""
    out = {}
    for m in HIDDEN.finditer(page):
        at = attrs(m.group(0))
        if at.get("name"):
            out[at["name"]] = at.get("value", "")
    return out


def selects(page):
    """(name, [(value, label)]) for every select on the page."""
    out = []
    for m in SELECT.finditer(page):
        at = attrs(m.group("attrs"))
        opts = [(attrs(o.group("attrs")).get("value", ""),
                 html.unescape(re.sub(r"\s+", " ", o.group("text"))).strip())
                for o in OPTION.finditer(m.group("body"))]
        out.append((at.get("name") or at.get("id") or "", opts))
    return out


def year_select(page):
    """The select whose every option is a bare four-digit year.

    The earlier test was "contains a year and does not contain January". On
    the 2026 page that is correct, because the document list does carry a
    January calendar and so is excluded. It is correct by luck: the document
    list comes after the year list in the DOM and would win the loop, so any
    year whose documents happen not to include January would be read as the
    year select. Requiring every option to be a bare year cannot confuse the
    two, and does not depend on which months a year happens to hold.
    """
    for nm, opts in selects(page):
        if opts and all(re.fullmatch(r"(19|20)\d{2}", (v or "")) for v, _ in opts):
            return nm
    return None


def type_select(page):
    """The select that switches Calendars and Journals.

    Matched on what its options MEAN, not on their exact text. The House
    offers Calendar/Journal; the Senate offers SenateCalendar/SenateJournal.
    An exact match found the House and missed the Senate entirely.
    """
    for nm, opts in selects(page):
        if len(opts) == 2 and all(
                any(word in ((v or "") + " " + (lbl or "")).lower()
                    for v, lbl in opts)
                for word in ("calendar", "journal")):
            return nm
    return None


def type_value(page, want):
    """The option value THIS page uses for "Calendar" or "Journal".

    Posting a value the select does not carry fails ASP.NET event validation,
    which comes back as HTTP 500 -- which is what the Senate returned to
    fetch_journals on 6 September, because "Journal" is not one of its options.
    """
    nm = type_select(page)
    if not nm:
        return None
    for n, opts in selects(page):
        if n != nm:
            continue
        for v, lbl in opts:
            if want.lower() in ((v or "") + " " + (lbl or "")).lower():
                return v
    return None


def post(page, changes, target, label, raw_name=None, url=URL):
    """One postback. Returns the new page, or None if it failed."""
    fields = form_fields(page)
    fields.update(changes)
    # A browser names the control that changed. The earlier code used
    # setdefault, which would have left this empty had the page ever carried
    # an __EVENTTARGET hidden input of its own.
    fields["__EVENTTARGET"] = target
    fields["__EVENTARGUMENT"] = ""
    shown = ", ".join(f"{k}={v}" for k, v in changes.items())
    print(f"\n  posting {shown} ...")
    try:
        out = get(url, urllib.parse.urlencode(fields).encode())
    except Exception as e:
        print(f"  postback failed: {type(e).__name__}: {e}")
        return None
    if raw_name:
        Path(raw_name).write_text(out, encoding="utf-8")
        print(f"  wrote {raw_name}")
    show(out, label)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", help="also switch the year, to see what changes")
    ap.add_argument("--type", dest="doctype", choices=["Calendar", "Journal"],
                    help="switch Calendars/Journals before switching year")
    ap.add_argument("--chamber", default="house",
                    choices=["house", "senate"],
                    help="which chamber's page to read")
    ap.add_argument("--raw", action="store_true", help="save the HTML")
    a = ap.parse_args()
    url = BASE.format(chamber=a.chamber)

    print(f"fetching {url}")
    try:
        page = get(url)
    except Exception as e:
        sys.exit(f"failed: {type(e).__name__}: {e}")
    if a.raw:
        Path("probe_calendars.html").write_text(page, encoding="utf-8")
        print("wrote probe_calendars.html")
    show(page, "AS LOADED")

    # The type is switched first and on its own: it is its own postback, and it
    # re-renders the document list under it.
    if a.doctype:
        tsel = type_select(page)
        if not tsel:
            print("\n  Could not tell which select is Calendar/Journal. "
                  "Send --raw.")
            return
        tval = type_value(page, a.doctype) or a.doctype
        if tval != a.doctype:
            print(f"\n  this page calls {a.doctype.lower()}s {tval!r}")
        page = post(page, {tsel: tval}, tsel,
                    f"AFTER SWITCHING TO {a.doctype.upper()}S",
                    "probe_calendars_type.html" if a.raw else None,
                    url=url)
        if page is None:
            return

    if a.year:
        # One postback, to find out whether another year can be listed without
        # a browser. If this works, every year back to 1997 is two requests.
        ysel = year_select(page)
        if not ysel:
            print("\n  Could not tell which select is the year. Send --raw.")
            return
        changes = {ysel: a.year}
        # Carry the type across. A browser posts every control with each
        # change; ASP.NET would otherwise see this one as unset.
        tsel = type_select(page)
        if tsel and a.doctype:
            changes[tsel] = type_value(page, a.doctype) or a.doctype
        if post(page, changes, ysel, f"AFTER SWITCHING TO {a.year}",
                "probe_calendars_year.html" if a.raw else None,
                url=url) is None:
            print("  If the year cannot be switched this way, the list for "
                  "earlier\n  years may live at its own address instead.")


if __name__ == "__main__":
    main()
