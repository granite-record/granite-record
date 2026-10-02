#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-08.9
"""
Thirty years of calendars and journals, a night at a time.

    python3 fetch_calendar_archive.py --list             # the plan, no network
    python3 fetch_calendar_archive.py --discover         # list what exists
    python3 fetch_calendar_archive.py --listing          # what each index lists this
                                                         #   year: the night's, four requests
    python3 fetch_calendar_archive.py --budget 400       # fetch that many
    python3 fetch_calendar_archive.py --status           # what is held, no network

ARCHIVE_PLAN.md step 4, built the way that page says: DISCOVERY AND FETCHING
ARE SEPARATE PROGRAMS, there is one queue and it is a file, and one worker
drains it.

WHY IT IS BUILT THAT WAY AND NOT AS A LOOP

Calendar discovery once guessed filenames -- two folder spellings, two ways of
writing "No", two day paddings -- and made about a thousand requests for files
that mostly did not exist. The firewall read that as a directory scan, which is
what it was, and blocked this address. probe_calendars.py then established that
the index lists every document by its REAL filename, in a dropdown, for every
year back to 1997 in the House and 1998 in the Senate.

So nothing here is ever constructed. `--discover` asks the index what exists
and writes it to the queue; a fetch only ever drains the queue. The filename
travels verbatim, because across thirty years there are at least three
incompatible forms of it and (year, number) is not a key for anything -- the
2003 journal list holds "HJ No 21 09-04-2003" and "HJ No 21 06-30-2003", the
same number twice, and "HJ No 23 01-07-2004", a 2004 date filed under 2003.

THE QUEUE

archive/queue.csv, one row per document:

    chamber,kind,year,name,url,path,state,attempts,error,bytes,fetched

state is wanted / held / failed / gone. A file already on disk is never asked
for again, so an interrupted run resumes by re-reading the queue and every run
is idempotent.

ONE WORKER. The queue is drained by a single process holding archive/.lock.
Two fetches at once is what got this address blocked the second time, and a
design that cannot do it beats a rule that has to be remembered.

A NIGHTLY BUDGET, NOT A MARATHON. --budget stops the run at that many
requests whether or not the queue is empty. About 4,400 documents is then a
fortnight of quiet nights rather than one long crawl that looks exactly like
an attack from the far end.

AND SLOWLY. The first drain ran at three seconds and 18 documents a minute,
and one request in came back RemoteDisconnected -- the server accepting the
connection and closing it without sending a byte, which is this address's
signature for being refused. It recovered and kept going, and that is exactly
the behaviour not to have: a fetch that pushes through a refusal is how the
last two blocks were earned.

So the default is 15 seconds with jitter, which is four documents a minute and
about sixteen hours for the whole archive spread over as many nights as it
takes. The goal is every document eventually, not many documents today.
Nothing here has a deadline; the server is the only party that can be
inconvenienced, and it did not ask for any of this.

RemoteDisconnected is treated as its own thing. One is bad luck and costs a
two-minute pause; two in a run ends the run, whether or not they were
consecutive, because the second one is a pattern.

THE LIST IS THE NIGHT'S (1 October 2026)

The queue was last discovered on 13 September, and by 1 October it was three
House calendars behind: nothing refreshed it, and the Calendar page's picker
of calendars and journals is built from it. The person approved GitHub's
night reading the two index pages every night. --listing is that read, and
nightly.take_documents() runs it under the night's lock:

  what it asks     each chamber's index page once, which opens on its
                   calendars for the newest year, and once more for that
                   year's journals: four requests, LISTING_PAUSE seconds
                   apart. While two years' lists can both still gain a
                   document -- the next year's has opened, or it is January
                   -- the year before as well: eight, and never more
                   (LISTING_MOST). No PDF is asked for
  what it trusts   only what the page says of itself. Each answer is read
                   for the list it shows -- its own selected kind and year --
                   and for its own "View PDF File" link, whose folder is the
                   one every address of that list is written with. A page
                   that shows a list nobody asked for, or whose link names
                   another folder, year or file than its list, has changed
                   shape: the read stops there, with nothing written
  what it writes   with --out FILE, the whole queue with what is new added
                   (a row marked wanted, in the page's own order), and
                   documents_listed.json beside it: each list as the page
                   gave it, name and label, the folder, and when it was read.
                   The night installs both or neither (judge(), below). A
                   read that stops writes only why, in that second file,
                   for the night's warning to say
                   Without --out, on a machine that keeps its own list, it
                   judges and installs them itself
  the label        the queue kept a document's file name and not the words
                   the General Court shows for it. They differ for the
                   newest documents, which are posted as "HC 35.pdf" and
                   shown as "No 35 September 25 2026", so a new column,
                   label, keeps the General Court's own words

ONE WRITER FOR EACH FILE. archive/queue.csv is the night's in the kit
(cloud_kit.json) from that day, so on a laptop that has stood down nothing
here writes it: --discover and --listing refuse there (refusal.stand_down),
and the drain keeps what it fetched in archive/queue_fetched.csv -- the rows
whose state it changed, and no others -- which is the laptop's file.
load_queue() reads the two together wherever it runs, so the drain, --status
and --list see one queue; and on GitHub's machine --listing writes the
laptop's record into the queue it hands the night, which is how a calendar
the laptop has fetched comes to be marked held in the file the build reads.
A machine that has not stood down keeps one file, as before.
"""

import argparse
import csv
import html
import json
import os
import random
import re
import refusal
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date
from pathlib import Path

from fetch_committee_reports import (DOCNUM_RE, OPTION_RE, SEL_DOC, SEL_KIND,
                                     SEL_YEAR, SELECT_RE, UA, _hidden, _options)

ROOT = Path("archive")
QUEUE = ROOT / "queue.csv"
# No LOCK here. The one-worker lock is refusal.LOCK, taken through
# refusal.hold(); a second name for the same file is how this script came to
# manage it by hand.
FIELDS = ["chamber", "kind", "year", "name", "url", "path", "state",
          "attempts", "error", "bytes", "fetched", "label"]
# What the drain writes about a document. Every other column is the list's.
DRAIN_FIELDS = ("state", "attempts", "error", "bytes", "fetched")
# Beside the queue, wherever the queue is: what a stood-down laptop's drain
# has fetched (the laptop's file), and what the General Court's pages listed
# the last time they were read (the night's).
FETCHED_NAME = "queue_fetched.csv"
LISTED_NAME = "documents_listed.json"

# ---- the night's read of the two index pages --------------------------------
#
# Seconds between its requests, the night's pace for a web page (fetch_lsrs's
# PAUSE). The most it may ask in one run: four lists a chamber at the turn of
# a year. How long it may take in all, so it cannot hold the night's lock
# into the morning. And how much of a list on file may be missing from
# tonight's before tonight's is taken for a page half served -- the General
# Court does not unpublish a calendar.
LISTING_PAUSE = 5.0
LISTING_MOST = 8
LISTING_BUDGET = 300
LIST_GONE_MOST = 0.10
LIST_GONE_FLOOR = 1

# The two index pages, and what each calls its own document kinds. Read off
# the pages by probe_calendars.py rather than assumed: the House says
# "Calendar"/"Journal" and the Senate "SenateCalendar"/"SenateJournal", and
# the folder is lower case in one and capitalised in the other.
SOURCES = {
    ("H", "calendar"): ("https://gc.nh.gov/house/calendars_journals/",
                        "Calendar", "calendars", "calendars", "HC"),
    ("H", "journal"): ("https://gc.nh.gov/house/calendars_journals/",
                       "Journal", "journals", "journals", "HJ"),
    ("S", "calendar"): ("https://gc.nh.gov/senate/calendars_journals/",
                        "SenateCalendar", "Calendars", "calendars_senate", "SC"),
    ("S", "journal"): ("https://gc.nh.gov/senate/calendars_journals/",
                       "SenateJournal", "Journals", "journals_senate", "SJ"),
}
VIEWER = "viewer.aspx?fileName="
# What each list is called where a person reads it: the night's verdict.
SAID = {("H", "calendar"): "House Calendar", ("H", "journal"): "House Journal",
        ("S", "calendar"): "Senate Calendar", ("S", "journal"): "Senate Journal"}
# The page's own "View PDF File" link, which names the folder its list is in:
#   <a id="pageBody_btnGo" href="viewer.aspx?fileName=Calendars\2026\SC 29.pdf">
LINK_RE = re.compile(r'href\s*=\s*"[^"]*?viewer\.aspx\?fileName=([^"]*)"', re.I)


def _get(url, data=None, timeout=60):
    req = urllib.request.Request(
        url, data=data,
        headers=dict(UA, **({"Content-Type":
                             "application/x-www-form-urlencoded"} if data else {})))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _page(url, data=None):
    return _get(url, data).decode("utf-8", errors="replace")


def _local(prefix, name, label):
    """The name the existing archive uses: HC010.pdf, SC005.pdf, HJ016.pdf.

    The number comes from the LABEL ("No 32 September 4 2026"), not the
    filename, because a filename can be "SC 29.pdf" with no "No" in it at all
    while its label still reads "No 29". Where neither carries a number the
    source name is kept, so nothing is silently renamed to a collision.
    """
    m = DOCNUM_RE.search(label or "") or DOCNUM_RE.search(name or "")
    if not m:
        return name
    num = m.group(1)
    digits = "".join(c for c in num if c.isdigit())
    suffix = "".join(c for c in num if c.isalpha()).upper()
    if not digits:
        return name
    return f"{prefix}{int(digits):03d}{suffix}.pdf"


def read_rows(path):
    """The rows of a queue file as they are written, or [] when it is not there."""
    path = Path(path)
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_rows(path, rows):
    """A queue file, whole: a part file, then a rename."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) or "" for k in FIELDS})
    tmp.replace(path)


def _key(r):
    return (r.get("chamber"), r.get("kind"), r.get("year"), r.get("name"))


def fetched_file():
    """The laptop's record of what its drain fetched, beside the queue."""
    return QUEUE.with_name(FETCHED_NAME)


def listed_file():
    """What the index pages listed when they were last read, beside the queue."""
    return QUEUE.with_name(LISTED_NAME)


def list_is_the_nights():
    """Whether the queue is GitHub's night's to write and not this machine's:
    where the folder that holds it holds the stand-down as well, which is
    archive/ on a laptop that has stood down. Never on GitHub's own machine.

    THE FOLDER'S STAND-DOWN, NOT THE MACHINE'S, as refusal.py reads the one
    beside a refusal record: a queue somewhere else -- every test's -- is not
    the night's because the laptop running the test has stood down. Judged
    by the machine, preflight's check of the drain, which seeds its queue in
    a temp folder through save_queue(), wrote nothing there on the laptop."""
    return (os.environ.get("GITHUB_ACTIONS") != "true"
            and (QUEUE.parent / refusal.STANDDOWN.name).exists())


def load_queue():
    """The queue, with what a stood-down laptop's drain has fetched laid over
    it: the list is the night's file and the fetching is the laptop's, and
    everything here reads them as one."""
    rows = read_rows(QUEUE)
    mine = {_key(r): r for r in read_rows(fetched_file())}
    for r in rows:
        r["label"] = r.get("label") or ""
        m = mine.get(_key(r))
        if m:
            for f in DRAIN_FIELDS:
                r[f] = m.get(f) or ""
    return rows


def save_queue(rows):
    """What the drain did, kept. On a machine that keeps its own list that is
    the queue itself. On a stood-down laptop the queue is the night's, and a
    second writer is how the older copy wins: the rows whose state the drain
    changed go to the laptop's own file, and no others, so a row drops out of
    it once the night's list says the same."""
    ROOT.mkdir(exist_ok=True)
    if not list_is_the_nights():
        write_rows(QUEUE, rows)
        return
    listed = {_key(r): r for r in read_rows(QUEUE)}
    mine = [r for r in rows if _key(r) in listed and any(
        (r.get(f) or "") != (listed[_key(r)].get(f) or "") for f in DRAIN_FIELDS)]
    if mine or fetched_file().exists():
        write_rows(fetched_file(), mine)


def discover(chamber, kind, years=None, delay=3.0):
    """Ask one index what it has. One request to load, one per year to switch."""
    index, kindval, folder, outdir, prefix = SOURCES[(chamber, kind)]
    print(f"  {chamber} {kind}: reading {index}")
    page = _page(index)
    listed = [v for v, _ in _options(page, SEL_YEAR) if v.isdigit()]
    if not listed:
        print("    the year list is empty; the page shape has changed")
        return []
    print(f"    {len(listed)} years offered, {listed[0]} back to {listed[-1]}")
    want = [y for y in listed if not years or int(y) in years]

    found = []
    # DISCOVERY NEEDS THE SAME STOP-LOSS AS THE DRAIN. The first run made five
    # failing requests in a row -- the Senate publishes no journals for
    # 1998-2002 and its page answers HTTP 500 rather than an empty list -- and
    # nothing here stopped it. Five is harmless; a whole index answering 500
    # and this looping through thirty years of it is the shape of the request
    # pattern that got this address blocked.
    run = 0
    for n, y in enumerate(want, 1):
        fields = _hidden(page)
        fields[SEL_KIND] = kindval
        fields[SEL_YEAR] = y
        fields["__EVENTTARGET"] = SEL_YEAR
        fields["__EVENTARGUMENT"] = ""
        time.sleep(delay)
        try:
            page = _page(index, urllib.parse.urlencode(fields).encode())
        except Exception as e:                          # noqa: BLE001
            run += 1
            print(f"    {y}: {type(e).__name__}: {e}")
            if run >= 4:
                print("    four years in a row failed. Stopping this "
                      "index rather than asking for twenty-six more "
                      "that will answer the same way.")
                break
            continue
        run = 0
        docs = [(v, lab) for v, lab in _options(page, SEL_DOC)
                if v and v.lower() != "select"]
        for name, label in docs:
            rel = f"{folder}\\{y}\\{name}"
            found.append({
                "chamber": chamber, "kind": kind, "year": y,
                # THE SOURCE FILENAME, VERBATIM, because across thirty years
                # there are at least three incompatible forms of it and it is
                # the only identifier this source offers.
                "name": name,
                "url": index + VIEWER + urllib.parse.quote(rel, safe=""),
                # But the LOCAL name follows the 376 files already on this
                # disk: calendars/2026/HC010.pdf, calendars_senate/2026/
                # SC005.pdf. Keyed on the source name instead, not one of
                # them would be recognised as held, and the first run would
                # re-download every one -- 376 needless requests at the
                # address that has blocked this project twice.
                "path": str(Path(outdir) / y / _local(prefix, name, label)),
                "state": "wanted", "attempts": "0", "error": "",
                "bytes": "", "fetched": ""})
        print(f"    [{n}/{len(want)}] {y}: {len(docs)} documents", flush=True)
    return found


# ---- the night's listing ----------------------------------------------------

class Stop(Exception):
    """The listing cannot go on: the exit status, and why in this project's
    own words -- the night's page is public and takes none of a server's."""

    def __init__(self, code, why):
        super().__init__(why)
        self.code, self.why, self.requests = code, why, 0


def today():
    """The day the listing is read on. A name of its own so a test can set it."""
    return date.today()


def _select(page, name):
    """[(value, label, selected)] for one <select>, entities read.

    _options() gives the attribute as the page wrote it, which is how the one
    file name with an apostrophe in it came to be asked for with "&#39;" in
    its address, and has answered 500 since."""
    for m in SELECT_RE.finditer(page):
        if m.group("name") == name:
            out = []
            for o in OPTION_RE.finditer(m.group("body")):
                attrs = o.group("attrs")
                v = re.search(r"""\bvalue\s*=\s*(?:"([^"]*)"|'([^']*)')""", attrs)
                value = (v.group(1) if v and v.group(1) is not None else
                         v.group(2) if v else "")
                label = " ".join(re.sub(r"<[^>]+>", "", o.group("text")).split())
                out.append((html.unescape(value or ""), html.unescape(label),
                            bool(re.search(r"\bselected\b", attrs, re.I))))
            return out
    return []


def shown(page):
    """What an index page says it is showing: the kind and year its own
    selects have selected, the documents of that list as (name, label), the
    one the document select has selected, the years it offers, and the file
    its own "View PDF File" link names (or "")."""
    kinds, years, docs = (_select(page, n) for n in (SEL_KIND, SEL_YEAR, SEL_DOC))
    link = LINK_RE.search(page)
    return {
        "kind": next((v for v, _, s in kinds if s), ""),
        "year": next((v for v, _, s in years if s), ""),
        "years": [v for v, _, _ in years if v.isdigit()],
        "docs": [(v, lab) for v, lab, _ in docs if v and v.lower() != "select"],
        "doc": next((v for v, _, s in docs if s and v and v.lower() != "select"), ""),
        "link": urllib.parse.unquote(html.unescape(link.group(1))) if link else "",
    }


def years_wanted(listed, day):
    """The years whose lists are read on `day`: the newest the index offers,
    and the one before it while both can still gain a document -- when the
    newest is next year's, which opens in late November, and through January,
    when December's last journal is still to be posted. December's documents
    are filed under the year their session belongs to, so either list may be
    the one that grows."""
    newest = max(int(y) for y in listed)
    out = [str(newest)]
    if (newest > day.year or day.month == 1) and str(newest - 1) in listed:
        out.append(str(newest - 1))
    return out


def read_index(chamber, ask, day):
    """One chamber's lists for the years wanted on `day`, as its index page
    gives them: one request for each list and no more. ask(url, data) is the
    caller's, so the pacing, the count and the reading of a refusal are in
    one place.

    Whatever the page answers is taken for the list it SAYS it shows. The
    first answer opens on the calendars of the newest year; a change of year
    is asked alone and a change of kind alone, because the page has been seen
    to leave the year behind when both change at once (fetch_journals.py),
    and a list filed under the wrong year is an address that does not exist.
    """
    index = SOURCES[(chamber, "calendar")][0]
    ours = {SOURCES[(chamber, k)][1]: k for k in ("calendar", "journal")}
    theirs = {k: v for v, k in ours.items()}
    where = "House" if chamber == "H" else "Senate"
    page = ask(index, None)
    wanted, lists = None, []
    while True:
        st = shown(page)
        if st["kind"] not in ours or not st["year"].isdigit() \
                or st["year"] not in st["years"]:
            raise Stop(1, f"the {where} index page no longer says which list it "
                          "shows: its shape has changed")
        kind, year = ours[st["kind"]], st["year"]
        what = f"the {SAID[(chamber, kind)]} list for {year}"
        if wanted is None:
            wanted = {(k, y) for k in theirs for y in years_wanted(st["years"], day)}
        if (kind, year) not in wanted:
            raise Stop(1, f"the {where} index page showed {what}, which was not "
                          "the list asked for")
        folder = SOURCES[(chamber, kind)][2]
        directory = ""
        if st["docs"]:
            cut = st["link"].rfind("\\")
            directory, named = st["link"][:cut + 1], st["link"][cut + 1:]
            if directory.lower() != f"{folder}\\{year}\\".lower() or named != st["doc"]:
                raise Stop(1, f"the page's own link does not name {what} or the "
                              "document it has selected: its shape has changed")
        seen, docs = set(), []
        for name, label in st["docs"]:
            # A NAME IS A FILE NAME. It becomes the end of an address and, on
            # the laptop, of the path its PDF is saved to: one that names a
            # folder is not something this writes down.
            if re.search(r'[\\/:*?"<>|\x00-\x1f]', name) or name.startswith("."):
                raise Stop(1, f"{what} names a document that is not a file name: "
                              "the page's shape has changed")
            if name not in seen:
                seen.add(name)
                docs.append({"name": name, "label": label})
        lists.append({"chamber": chamber, "kind": kind, "year": year,
                      "directory": directory,
                      "read": time.strftime("%Y-%m-%dT%H:%M:%S"),
                      "documents": docs})
        print(f"    {what}: {len(docs)} documents", flush=True)
        wanted.discard((kind, year))
        if not wanted:
            return lists
        # ONE CHANGE AT A TIME. Another year of the kind shown, if one is
        # still wanted; otherwise the other kind, in the year shown.
        same = sorted(y for k, y in wanted if k == kind)
        fields = _hidden(page)
        if same:
            fields[SEL_KIND], fields[SEL_YEAR] = theirs[kind], same[-1]
            fields["__EVENTTARGET"] = SEL_YEAR
        else:
            other = "journal" if kind == "calendar" else "calendar"
            fields[SEL_KIND], fields[SEL_YEAR] = theirs[other], year
            fields["__EVENTTARGET"] = SEL_KIND
        fields["__EVENTARGUMENT"] = ""
        page = ask(index, urllib.parse.urlencode(fields).encode())


def listing(held, day=None):
    """Tonight's lists from both index pages: (lists, requests made).

    Raises Stop with the exit status the run should end on: 2 when the
    General Court refused (recorded, as every fetch records one), 1 for
    anything else, and whatever the lock says when it is lost."""
    asked, t0 = [], time.time()

    def ask(url, data=None):
        # Immediately before the request: a refusal another process met, or
        # a lock lost, stops it here.
        if refusal.MARK.exists():
            raise Stop(2, "a refusal is on file")
        if not held.still():
            raise Stop(3, "the lock this runs under is gone, or GitHub's night has begun")
        if len(asked) >= LISTING_MOST:
            raise Stop(1, f"the lists were not all read in {LISTING_MOST} requests")
        if time.time() - t0 > LISTING_BUDGET:
            raise Stop(1, f"the lists were not all read in {LISTING_BUDGET} seconds")
        if asked:
            # Jittered, so a run does not arrive on a metronome.
            time.sleep(LISTING_PAUSE * random.uniform(0.9, 1.1))
        asked.append(url)
        try:
            body = _get(url, data).decode("utf-8", errors="replace")
        except Exception as e:                              # noqa: BLE001
            kind = refusal.classify(e) or "failed"
            print(f"    {kind}: {type(e).__name__}: {e}", flush=True)
            if kind == "refused":
                refusal.note("fetch_calendar_archive", f"{type(e).__name__}: {e}"[:180])
                raise Stop(2, "the General Court refused a request")
            # One dropped connection is not pushed through, and not asked
            # again tonight: the list waits for tomorrow.
            raise Stop(1, "a request was not answered" if kind == "dropped" else
                          "a request failed")
        if refusal.classify(body=body[:4000]) == "refused":
            refusal.note("fetch_calendar_archive", "the firewall's block page, served as 200")
            raise Stop(2, "the General Court refused a request")
        return body

    day = day or today()
    lists = []
    try:
        for chamber in ("H", "S"):
            print(f"  {'House' if chamber == 'H' else 'Senate'}: reading "
                  f"{SOURCES[(chamber, 'calendar')][0]}", flush=True)
            lists += read_index(chamber, ask, day)
    except Stop as e:
        e.requests = len(asked)
        raise
    return lists, len(asked)


def merged(rows, lists):
    """The queue with tonight's lists in it: (rows, the rows added).

    Nothing on file is dropped and no address on file is touched. A list
    read tonight is put in the page's own order, newest first as the General
    Court lists it, with what is new marked wanted; a document on file that
    tonight's page no longer lists stays, after them. A row gains the label
    the page shows for it."""
    out = [dict(r) for r in rows]
    added = []
    for li in lists:
        ch, kind, year = li["chamber"], li["kind"], li["year"]
        index, _, _, outdir, prefix = SOURCES[(ch, kind)]
        block = [r for r in out if (r["chamber"], r["kind"], r["year"]) == (ch, kind, year)]
        have = {}
        for r in block:
            have.setdefault(r["name"], r)
        fresh, names = [], set()
        for d in li["documents"]:
            name, label = d["name"], d.get("label") or ""
            names.add(name)
            r = have.get(name)
            if r is None:
                r = {"chamber": ch, "kind": kind, "year": year, "name": name,
                     # THE PAGE'S OWN FOLDER AND THE PAGE'S OWN NAME, never a
                     # pattern: the viewer address its own button would open.
                     "url": index + VIEWER + urllib.parse.quote(
                         li["directory"] + name, safe=""),
                     "path": str(Path(outdir) / year / _local(prefix, name, label)),
                     "state": "wanted", "attempts": "0", "error": "",
                     "bytes": "", "fetched": "", "label": ""}
                have[name] = r
                added.append(r)
            if label:
                r["label"] = label
            if not any(r is x for x in fresh):
                fresh.append(r)
        ids = {id(r) for r in block}
        rest = [r for r in block if r["name"] not in names]
        if block:
            at = next(i for i, r in enumerate(out) if id(r) in ids)
        else:
            # A year not on file yet goes where the file keeps years: newest
            # first within its chamber and kind.
            mine = [i for i, r in enumerate(out) if (r["chamber"], r["kind"]) == (ch, kind)]
            older = [i for i in mine if out[i]["year"].isdigit()
                     and int(out[i]["year"]) < int(year)]
            at = older[0] if older else (mine[-1] + 1 if mine else len(out))
        out = [r for r in out[:at] if id(r) not in ids] + fresh + rest \
            + [r for r in out[at:] if id(r) not in ids]
    return out, added


def judge(was, new, rec):
    """Why tonight's list may not replace the one on file, or "" when it may.

    The night's rule for every fetch, in this file's terms: whole or not at
    all, and never sharply smaller than what it replaces.

      whole      all four lists were read -- both chambers, calendars and
                 journals -- each for at least the newest year on file
      not empty  a list with documents on file did not come back with none
      not short  a list is missing no more than LIST_GONE_MOST of what is on
                 file for it (and more than LIST_GONE_FLOOR): the General
                 Court does not unpublish a calendar, so a shorter list is a
                 page half served
      a merge    every document on file is still in the queue, at the
                 address and the path it had
      their own  what is new is named by a list read tonight, is marked
                 wanted, and its address is the viewer's with the page's own
                 folder and the page's own name

    Every sentence it returns is this project's: counts and the lists' own
    names, and nothing a page said."""
    lists = rec.get("lists") if isinstance(rec, dict) else None
    if not new:
        return "the list came back empty"
    if not isinstance(lists, list) or not lists:
        return "nothing records which lists were read"
    got = {}
    for li in lists:
        try:
            k = (li["chamber"], li["kind"], str(li["year"]))
            names = [d["name"] for d in li["documents"]]
            directory = str(li.get("directory") or "")
        except (KeyError, TypeError):
            return "the record of what was read is not whole"
        if k[:2] not in SOURCES or not k[2].isdigit():
            return "the record of what was read names a list this does not know"
        got[k] = (names, directory)
    have, newest = {}, {}
    for r in was:
        k = (r.get("chamber"), r.get("kind"), r.get("year"))
        have.setdefault(k, []).append(r.get("name"))
        if (r.get("year") or "").isdigit():
            newest[k[:2]] = max(newest.get(k[:2], 0), int(r["year"]))
    for pair in SOURCES:
        years = [int(k[2]) for k in got if k[:2] == pair]
        if not years:
            return f"the {SAID[pair]} list was not read"
        if max(years) < newest.get(pair, 0):
            return f"the {SAID[pair]} list for {newest[pair]} was not read"
    if not any(names for names, _ in got.values()):
        return "every list came back empty"
    for k in sorted(got):
        names, on_file = set(got[k][0]), have.get(k, [])
        what = f"the {SAID[k[:2]]} list for {k[2]}"
        gone = [n for n in on_file if n not in names]
        if on_file and not names:
            return f"{what} came back empty, with {len(on_file)} documents on file"
        if len(gone) > max(LIST_GONE_FLOOR, LIST_GONE_MOST * len(on_file)):
            return (f"{what} came back without {len(gone)} of the {len(on_file)} "
                    "documents on file")
    now = {_key(r): r for r in new}
    if len(now) != len(new):
        return "it names a document twice"
    lost = [r for r in was if _key(r) not in now]
    if lost:
        return (f"{len(lost)} of the {len(was)} documents on file "
                f"{'is' if len(lost) == 1 else 'are'} not in it")
    if any((now[_key(r)].get(f) or "") != (r.get(f) or "") for r in was for f in ("url", "path")):
        return "it changes the address or the path of a document on file"
    old = {_key(r) for r in was}
    for r in new:
        if _key(r) in old:
            continue
        k = (r.get("chamber"), r.get("kind"), r.get("year"))
        if k not in got or r.get("name") not in got[k][0]:
            return "it adds a document no list read tonight names"
        index, _, folder, _, _ = SOURCES[k[:2]]
        if got[k][1].lower() != f"{folder}\\{k[2]}\\".lower() or r.get("url") != (
                index + VIEWER + urllib.parse.quote(got[k][1] + r["name"], safe="")):
            return "it adds an address the General Court's page did not give"
        if r.get("state") != "wanted":
            return "it adds a document as already fetched"
    return ""


def news(was, new):
    """"6 new: House Calendar 3, ..." or "nothing new", for the verdict."""
    old = {_key(r) for r in was}
    by = Counter((r["chamber"], r["kind"]) for r in new if _key(r) not in old)
    if not by:
        return "nothing new"
    return (f"{sum(by.values())} new: "
            + ", ".join(f"{SAID[k]} {by[k]}" for k in SOURCES if by.get(k)))


def take_listing(a, rows):
    """--listing: read the lists, and write the queue with them in it."""
    print("=" * 70)
    print("Asking each index what it lists for its newest year. Nothing is "
          "constructed,\nand no document is asked for.")
    print("=" * 70)
    with refusal.hold("the calendar and journal listing") as held:
        try:
            lists, n = listing(held)
        except Stop as e:
            print(f"\nThe lists were not read: {e.why}. Nothing is written.")
            if a.out:
                # WHY, WHERE THE NIGHT CAN READ IT. Its warning said only
                # "exit 1" of a page that had changed shape, and the reason
                # was a line in a log nobody opens for a warning.
                said = Path(a.out).with_name(LISTED_NAME)
                said.parent.mkdir(parents=True, exist_ok=True)
                said.write_text(json.dumps(
                    {"read": time.strftime("%Y-%m-%dT%H:%M:%S"), "requests": e.requests,
                     "stopped": e.why}, indent=1) + "\n", encoding="utf-8", newline="\n")
            return e.code
    rec = {"read": time.strftime("%Y-%m-%dT%H:%M:%S"), "requests": n, "lists": lists}
    new, added = merged(rows, lists)
    if a.out:
        out = Path(a.out)
        listed = out.with_name(LISTED_NAME)
    else:
        # By hand, on a machine that keeps its own list: the night's rule.
        why = judge(read_rows(QUEUE), new, rec)
        if why:
            print(f"\nNot installed: {why}. {QUEUE} is as it was.")
            return 1
        out, listed = QUEUE, listed_file()
    write_rows(out, new)
    tmp = listed.with_name(listed.name + ".part")
    tmp.write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, listed)
    for r in added:
        print(f"    new: {r['chamber']} {r['kind']} {r['year']}  {r['label'] or r['name']}")
    print(f"\n{n} requests, {len(lists)} lists, {news(rows, new)}; "
          f"{len(new):,} in the queue -> {out}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--discover", action="store_true")
    ap.add_argument("--listing", action="store_true",
                    help="what each index lists for its newest year, added to the "
                         "queue: the night's read, four requests")
    ap.add_argument("--out", help="(--listing) write the queue here, and "
                                  f"{LISTED_NAME} beside it, and leave judging and "
                                  "installing them to the caller: nightly.py")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--chamber", choices=["H", "S", "both"], default="both")
    ap.add_argument("--kind", choices=["calendar", "journal", "both"],
                    default="both")
    ap.add_argument("--from", dest="first", type=int, default=0)
    ap.add_argument("--to", dest="last", type=int, default=9999)
    ap.add_argument("--budget", type=int, default=150,
                    help="requests this run, then stop (default 150)")
    ap.add_argument("--delay", type=float, default=15.0,
                    help="seconds between requests (default 15). Jittered by "
                         "a quarter either way, so a run does not arrive on a "
                         "metronome.")
    a = ap.parse_args()

    ROOT.mkdir(exist_ok=True)
    rows = load_queue()

    if a.status or a.list:
        by = Counter((r["chamber"], r["kind"], r["state"]) for r in rows)
        print(f"{len(rows):,} documents in the queue")
        for (ch, kind, state), n in sorted(by.items()):
            print(f"  {ch} {kind:9} {state:7} {n:6,}")
        if not rows:
            print("  Nothing yet. Run --discover first; it asks the index what "
                  "exists\n  and writes the answer here.")
        held = sum(1 for r in rows if r["state"] == "held")
        if rows:
            print(f"\n  {held:,} of {len(rows):,} held "
                  f"({held / len(rows):.0%}), "
                  f"{sum(int(r['bytes'] or 0) for r in rows) / 1e6:.0f} MB")
        try:
            read = json.loads(listed_file().read_text(encoding="utf-8")).get("read")
        except (OSError, ValueError, AttributeError):
            read = None
        if read:
            print(f"  the General Court's lists were last read {read} "
                  f"({listed_file()})")
        return 0

    chambers = ["H", "S"] if a.chamber == "both" else [a.chamber]
    kinds = ["calendar", "journal"] if a.kind == "both" else [a.kind]
    years = set(range(a.first, a.last + 1)) if a.first else None

    if a.listing or a.discover:
        if a.listing and (a.discover or a.chamber != "both" or a.kind != "both"
                          or a.first):
            ap.error("--listing reads all four lists for the newest year, or "
                     "none: it takes no --discover, --chamber, --kind or --from")
        # ONE WRITER PER FILE. Both of these write the list, and the list is
        # the night's wherever GitHub runs the night. And neither starts
        # while a refusal stands: --discover asked the index with no check
        # at all until 1 October 2026, the one call being on the drain's path.
        refusal.stand_down(
            "Listing the calendars and journals",
            "GitHub's nightly reads the General Court's two index pages now "
            f"(nightly.take_documents), and {QUEUE} reaches this machine from R2 "
            "with python3 cloud.py pull. The drain still runs here, and keeps "
            f"what it fetches in {fetched_file()}.")
        refusal.check("The calendar and journal listing")
    if a.listing:
        return take_listing(a, rows)

    if a.discover:
        print("=" * 70)
        print("Asking each index what it has. Nothing is constructed.")
        print("=" * 70)
        seen = {(r["chamber"], r["kind"], r["year"], r["name"]) for r in rows}
        added = 0
        for ch in chambers:
            for kind in kinds:
                for rec in discover(ch, kind, years, a.delay):
                    key = (rec["chamber"], rec["kind"], rec["year"], rec["name"])
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append(rec)
                    added += 1
        # A document already on disk is held before anything is asked for.
        for r in rows:
            if r["state"] == "wanted" and Path(r["path"]).exists():
                r["state"] = "held"
                r["bytes"] = str(Path(r["path"]).stat().st_size)
        save_queue(rows)
        held = sum(1 for r in rows if r["state"] == "held")
        print(f"\n{added:,} new, {len(rows):,} in the queue, {held:,} already "
              f"on disk -> {QUEUE}")
        return 0

    # ---- draining, and only one process may ------------------------------
    #
    # refusal.hold() is the one-worker rule: take archive/.lock, or run under
    # the lane that holds it, or do not run. This block used to do it by hand
    # -- exit if the lock was under an hour old, delete it if older, and
    # unlink it unconditionally on the way out. Under watchers/gc_lane.py,
    # whose lock is touched every minute, that meant exiting 1 at once, which
    # stops the lane; and had it run, it would have deleted the lane's own
    # lock when it finished. refusal.py names this script as the one that
    # deleted locks.
    refusal.check("The calendar drain")
    with refusal.hold("the calendar drain") as held:
        return drain(rows, chambers, kinds, years, a, held)


def drain(rows, chambers, kinds, years, a, held):
    """Fetch up to --budget wanted documents. 0 done, 1 stopped, 2 refused.

    A run that stops early says so in its exit status. The lane reads any
    non-zero status as "stop here", and a drain that broke off on two failures
    and exited 0 would have had the lane rest half an hour and send the next
    batch at the same address.
    """
    stopped = ""
    try:
        todo = [r for r in rows
                if r["state"] == "wanted"
                and (r["chamber"] in chambers) and (r["kind"] in kinds)
                and (not years or int(r["year"]) in years)]
        n = min(len(todo), a.budget)
        print(f"{len(todo):,} wanted, taking {n:,} this run at about "
              f"{a.delay:g}s apart -- roughly {n * a.delay / 60:.0f} minutes, "
              f"{60 / a.delay:.1f} a minute")
        got = fail = 0
        run = dropped = 0
        t0 = time.time()
        for i, r in enumerate(todo[:a.budget], 1):
            path = Path(r["path"])
            if path.exists():
                r["state"] = "held"
                r["bytes"] = str(path.stat().st_size)
                continue
            # Immediately before the request, not before the sleep that
            # preceded it: a refusal another process met while this one
            # waited, or a lane killed while it waited, stops it here.
            if refusal.MARK.exists():
                stopped = "refused"
                print("\narchive/refused.json is on file. Stopping.")
                break
            if not held.still():
                stopped = "the lane"
                print("\nThe lane holding archive/.lock is gone. Stopping.")
                break
            path.parent.mkdir(parents=True, exist_ok=True)
            # ONE READING OF EVERY ANSWER. This loop used to recognise a
            # refusal by searching the error text for RemoteDisconnected,
            # ConnectionReset or 403 -- which missed a reset at connect time
            # ("[WinError 10054]"), a 429, a 503, and the firewall's block
            # page served with HTTP 200, which it would have saved as a PDF
            # and marked held for ever. refusal.classify() is the reading
            # every other fetch uses.
            try:
                blob = _get(r["url"])
                kind = refusal.classify(
                    body=blob[:4000].decode("utf-8", "replace"))
                why = "the firewall's block page, served as 200" if kind else ""
                if not kind and not blob.startswith(b"%PDF"):
                    kind, why = "failed", f"not a PDF ({len(blob):,} bytes)"
            except Exception as e:                      # noqa: BLE001
                kind = refusal.classify(e) or "failed"
                why = f"{type(e).__name__}: {e}"
            if kind:
                r["attempts"] = str(int(r["attempts"] or 0) + 1)
                r["error"] = why[:180]
                fail += 1
                print(f"  [{i}] {r['name']}: {kind}: {r['error'][:80]}",
                      flush=True)
                if kind == "refused":
                    # The address saying no. One ends the run.
                    refusal.note("fetch_calendar_archive", r["error"])
                    stopped = "refused"
                    print("\nRefused. Stopping and not coming back today.\n"
                          "python3 netcheck.py says what kind of refusal it "
                          "is without making it worse.")
                    break
                if kind == "missing":
                    # Listed by the index and not served. Not a refusal and
                    # not worth asking again: the index is where the name
                    # came from, so a 404 is the index being out of date.
                    r["state"] = "gone"
                    time.sleep(a.delay * random.uniform(0.75, 1.25))
                    continue
                if int(r["attempts"]) >= 3:
                    r["state"] = "failed"
                run += 1
                if kind == "dropped":
                    # Accepted and closed without an answer. One is bad
                    # luck; two in a run is this address refusing.
                    dropped += 1
                    if dropped >= 2:
                        refusal.note("fetch_calendar_archive", r["error"])
                        stopped = "refused"
                        print("\nTwo dropped connections this run. Stopping "
                              "and not coming back today.\npython3 "
                              "netcheck.py says what kind of refusal it is "
                              "without making it worse.")
                        break
                if run >= 2:
                    stopped = "two in a row"
                    print("\nTwo in a row. Stopping. netcheck.py says why "
                          "without making it worse.")
                    break
                cool = 120 if kind == "dropped" else a.delay * 3
                print(f"      waiting {cool:.0f}s before the next one",
                      flush=True)
                time.sleep(cool)
                continue
            run = 0
            # A part file, then a rename: a run killed mid-write must not
            # leave half a PDF that path.exists() then calls held.
            tmp = path.with_name(path.name + ".part")
            tmp.write_bytes(blob)
            os.replace(tmp, path)
            r["state"] = "held"
            r["bytes"] = str(len(blob))
            r["error"] = ""
            r["fetched"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            got += 1
            if got % 10 == 0:
                save_queue(rows)
                rate = got / max(1e-9, time.time() - t0)
                print(f"  {i}/{min(len(todo), a.budget)}  {got} fetched, "
                      f"{rate * 60:.0f}/min", flush=True)
            # Jittered, so a run does not arrive on a metronome.
            time.sleep(a.delay * random.uniform(0.75, 1.25))
    finally:
        # The queue is saved however the run ends. The lock is NOT touched
        # here: refusal.hold() releases it, and only if it is this run's own.
        save_queue(rows)
    n_held = sum(1 for x in rows if x["state"] == "held")
    print(f"\n{got:,} fetched, {fail} failed, {time.time() - t0:.0f}s")
    print(f"{n_held:,} of {len(rows):,} held "
          f"({sum(int(x['bytes'] or 0) for x in rows) / 1e6:.0f} MB)")
    left = sum(1 for x in rows if x["state"] == "wanted")
    if left and not stopped:
        print(f"{left:,} still wanted. Run again for the next {a.budget}.")
    if stopped == "refused":
        return 2
    return 1 if stopped else 0


if __name__ == "__main__":
    sys.exit(main())
