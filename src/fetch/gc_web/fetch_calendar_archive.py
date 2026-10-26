#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-08.14
"""
Thirty years of calendars and journals, a night at a time.

    python3 src/fetch/gc_web/fetch_calendar_archive.py --list             # the plan, no network
    python3 src/fetch/gc_web/fetch_calendar_archive.py --discover         # list what exists
    python3 src/fetch/gc_web/fetch_calendar_archive.py --listing          # what each index lists this
                                                                          #   year: the night's, four requests
    python3 src/fetch/gc_web/fetch_calendar_archive.py --budget 400       # fetch that many
    python3 src/fetch/gc_web/fetch_calendar_archive.py --status           # what is held, no network

ARCHIVE_PLAN.md step 4 (the person's plan, in private/ and not in the
repository), built the way that page says: DISCOVERY AND FETCHING ARE
SEPARATE PROGRAMS, there is one queue and it is a file, and one worker
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
                   apart and as long before the first, because the night
                   has asked this address for something else a moment
                   before. While two years' lists can both still gain a
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
  a year with no   the Senate's page answers HTTP 500, not an empty list,
  journals yet     for a year it has no journals for (discover(), below).
                   So when a new year's list opens, its journal list would
                   stop the whole read every night until the first journal
                   was posted. That one answer -- a 500 to the last list
                   asked of a chamber, a year's journals, with none on file
                   and that year's calendars just read -- is written down as
                   a list nobody answered for ("unanswered": 500) and taken
                   as none posted yet. Any other 500 stops the read
  what it writes   with --out FILE, the whole queue with what is new added
                   (a row marked wanted, in the page's own order), and
                   documents_listed.json beside it: each list as the page
                   gave it, name and label, the folder, and when it was read.
                   The night installs both or neither (judge(), below). A
                   read that stops writes only why, in that second file,
                   for the night's warning to say
  never sharply    a list missing more than LIST_GONE_MOST of what the page
  shorter          listed when it was last installed is a page half served,
                   and is not installed. Measured against that last read,
                   not against everything on file: a row never leaves the
                   queue, so counted against the file every document the
                   page had ever dropped would count again each night, and
                   the second one would have stopped the list for good. And
                   a list that comes back short the same way night after
                   night is the page's own: the night takes it on the third
                   (nightly.LIST_SAME_NIGHTS)
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

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import csv
import hashlib
import html
import json
import os
import random
import re
import refusal
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date, datetime

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
# Seconds between its requests, and before the first, the night's pace for a
# web page (fetch_lsrs's PAUSE). The most it may ask in one run: four lists a
# chamber at the turn of a year. How long it may go on starting requests, so
# it cannot hold the night's lock into the morning: none is started after
# this, and one already started may take its own timeout more. And how much
# of a list may be missing from tonight's before tonight's is taken for a
# page half served -- the General Court does not unpublish a calendar -- with
# the fewest that counts as missing at all.
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


# What a new row's name or label says when it is a supplement to a calendar.
SUPPLEMENT_RE = re.compile(r"supplement", re.I)


def _new_local(prefix, name, label):
    """The path a row NEW to the queue is given while its year is the night's
    (merged's `night_from`): _local()'s, but a supplement keeps its source name
    (the person's plan, 26 October 2026). The Senate's page lists "No 27
    Supplement June 19 2025" and two more supplements of No 27 before "No 27
    June 19 2025", and by number alone all four were SC027.pdf: the first saved
    there, and the base edition then counted as held, never asked for. A row
    on file keeps the path it has."""
    if SUPPLEMENT_RE.search(name or "") or SUPPLEMENT_RE.search(label or ""):
        return name
    return _local(prefix, name, label)


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


def doc_key(r):
    """A document as every warning prints it and every command takes it:
    chamber|kind|year|name, "S|calendar|2026|No 21 Supplement.pdf"."""
    return "|".join(str(x or "") for x in _key(r))


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


def night_rows():
    """{doc_key: fields} for the years handed to GitHub's night: the handover's
    frozen rows -- the laptop's last word on them -- with the night's own record
    laid over them row by row where that record is of this handover (its
    "handover" is the record's "at"). {} with no record that reads: the rows
    of those years then stand as the night's list has them."""
    state, h = refusal.read_handover()
    if state != "ok":
        return {}
    n = refusal.read_night_record() or {}
    out = {}
    for d in (h, n if h.get("at") and n.get("handover") == h["at"] else {}):
        got = d.get("rows")
        if isinstance(got, dict):
            out.update((k, v) for k, v in got.items() if isinstance(v, dict))
    return out


def load_queue():
    """The queue, with what a stood-down laptop's drain has fetched laid over
    it: the list is the night's file and the fetching is the laptop's, and
    everything here reads them as one.

    THREE LAYERS ONCE THE YEARS ARE HANDED OVER (the person's design of 26
    October 2026), in the same order on both machines: the night's list; over
    its rows of years before the handover's, the laptop's file; over the rows
    of the night's years, the night's own record of them, or the handover's
    frozen rows (night_rows). The laptop's file never touches a year of the
    night's, and only what the drain writes is laid over, never a path."""
    rows = read_rows(QUEUE)
    mine = {_key(r): r for r in read_rows(fetched_file())}
    y = refusal.night_years()
    theirs = night_rows() if y is not None else {}
    for r in rows:
        r["label"] = r.get("label") or ""
        m = theirs.get(doc_key(r)) if refusal.handed(r.get("year"), y) else mine.get(_key(r))
        if m:
            for f in DRAIN_FIELDS:
                r[f] = m.get(f) or ""
    return rows


def save_queue(rows):
    """What the drain did, kept. On a machine that keeps its own list that is
    the queue itself. On a stood-down laptop the queue is the night's, and a
    second writer is how the older copy wins: the rows whose state the drain
    changed go to the laptop's own file, and no others, so a row drops out of
    it once the night's list says the same -- and never a row of the years
    handed to the night, which are the night's to record. While the handover
    record will not read (every year the night's) the file is left as it is:
    kept to no year, it would lose the laptop's own."""
    ROOT.mkdir(exist_ok=True)
    if not list_is_the_nights():
        write_rows(QUEUE, rows)
        return
    y = refusal.night_years()
    if y == 0:
        return
    listed = {_key(r): r for r in read_rows(QUEUE)}
    mine = [r for r in rows if not refusal.handed(r.get("year"), y) and _key(r) in listed
            and any((r.get(f) or "") != (listed[_key(r)].get(f) or "") for f in DRAIN_FIELDS)]
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

    def __init__(self, code, why, http=0):
        super().__init__(why)
        # http: the status of the answer that stopped it, where one came.
        self.code, self.why, self.requests, self.http = code, why, 0, http


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


def read_index(chamber, ask, day, on_file=None):
    """One chamber's lists for the years wanted on `day`, as its index page
    gives them: one request for each list and no more. ask(url, data, what)
    is the caller's, so the pacing, the count and the reading of a refusal
    are in one place; `what` names the list asked for, for the reason given
    when no answer comes.

    Whatever the page answers is taken for the list it SAYS it shows. The
    first answer opens on the calendars of the newest year; a change of year
    is asked alone and a change of kind alone, because the page has been seen
    to leave the year behind when both change at once (fetch_journals.py),
    and a list filed under the wrong year is an address that does not exist.

    A YEAR WITH NO JOURNALS YET. The Senate's page answers HTTP 500, not an
    empty list, for a year it has no journals for. At a year's turn that is
    the new year's journal list, every night until the first journal is
    posted, and a 500 that stopped the read would leave all four lists
    unrefreshed for those weeks -- the weeks the new calendars appear in. So
    one answer is taken for "none yet", and written down as what it was
    ("unanswered": 500, no documents): a 500 to the LAST list asked of this
    chamber, when that list is a year's journals, nothing is on file for it
    (`on_file`, the lists the queue has rows for), and the same year's
    calendars were read a moment before from the same page. The order below
    makes the newest year's journals the last list asked. Any other 500, and
    this one where the caller has not said what is on file, stops the read.
    """
    index = SOURCES[(chamber, "calendar")][0]
    ours = {SOURCES[(chamber, k)][1]: k for k in ("calendar", "journal")}
    theirs = {k: v for v, k in ours.items()}
    where = "House" if chamber == "H" else "Senate"
    page = ask(index, None, f"the {where} index page")
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
            asking = (kind, same[-1])
            fields[SEL_KIND], fields[SEL_YEAR] = theirs[kind], same[-1]
            fields["__EVENTTARGET"] = SEL_YEAR
        else:
            other = "journal" if kind == "calendar" else "calendar"
            asking = (other, year)
            fields[SEL_KIND], fields[SEL_YEAR] = theirs[other], year
            fields["__EVENTTARGET"] = SEL_KIND
        fields["__EVENTARGUMENT"] = ""
        said = f"the {SAID[(chamber, asking[0])]} list for {asking[1]}"
        try:
            page = ask(index, urllib.parse.urlencode(fields).encode(), said)
        except Stop as e:
            # A year with no journals yet (the docstring): this answer only.
            if not (e.http == 500 and asking[0] == "journal" and wanted == {asking}
                    and on_file is not None and (chamber, *asking) not in on_file
                    and any(li["kind"] == "calendar" and li["year"] == asking[1]
                            and li["documents"] for li in lists)):
                raise
            lists.append({"chamber": chamber, "kind": asking[0], "year": asking[1],
                          "directory": "", "read": time.strftime("%Y-%m-%dT%H:%M:%S"),
                          "documents": [], "unanswered": 500})
            print(f"    {said}: no answer (HTTP 500), and nothing on file for it: "
                  "taken as none posted yet", flush=True)
            return lists


def listing(held, day=None, on_file=None):
    """Tonight's lists from both index pages: (lists, requests made).

    `on_file`: the (chamber, kind, year) lists the queue has rows for, which
    read_index needs before it takes one unanswered journal list for a year
    with none posted yet; None, and no such answer is taken.

    Raises Stop with the exit status the run should end on: 2 when the
    General Court refused (recorded, as every fetch records one), 1 for
    anything else, and whatever the lock says when it is lost."""
    asked, t0 = [], time.time()

    def ready():
        if refusal.MARK.exists():
            raise Stop(2, "a refusal is on file")
        if not held.still():
            raise Stop(3, "the lock this runs under is gone, or GitHub's night has begun")

    def ask(url, data, what):
        ready()
        if len(asked) >= LISTING_MOST:
            raise Stop(1, f"the lists were not all read in {LISTING_MOST} requests")
        if time.time() - t0 > LISTING_BUDGET:
            raise Stop(1, f"the lists were not all read in {LISTING_BUDGET} seconds")
        # A PAUSE BEFORE EVERY REQUEST, THE FIRST AS WELL. It used to wait
        # only between its own, so the night's first request here left about
        # a second after fetch_lsrs's last to the same address: the kind of
        # join at which a chained run once asked twelve seconds after a
        # refusal. This cannot know what asked before it, so it always
        # waits. Jittered, so a run does not arrive on a metronome.
        time.sleep(LISTING_PAUSE * random.uniform(0.9, 1.1))
        # Immediately before the request, not before the pause that preceded
        # it: a refusal another process met while this one waited, or a lock
        # lost, stops it here.
        ready()
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
            raise Stop(1, f"the request for {what} "
                          + ("was not answered" if kind == "dropped" else "failed"),
                       http=e.code if isinstance(e, urllib.error.HTTPError) else 0)
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
            lists += read_index(chamber, ask, day, on_file)
    except Stop as e:
        e.requests = len(asked)
        raise
    return lists, len(asked)


def merged(rows, lists, night_from=None):
    """The queue with tonight's lists in it: (rows, the rows added).

    Nothing on file is dropped and no address on file is touched. A list
    read tonight is put in the page's own order, newest first as the General
    Court lists it, with what is new marked wanted; a document on file that
    tonight's page no longer lists stays, after them. A row gains the label
    the page shows for it.

    `night_from`: the first year handed to GitHub's night (refusal.night_years),
    or None. Only a new row of those years is given a supplement's own name
    for its path (_new_local); every other path is given as it always was."""
    out = [dict(r) for r in rows]
    added = []
    for li in lists:
        ch, kind, year = li["chamber"], li["kind"], li["year"]
        index, _, _, outdir, prefix = SOURCES[(ch, kind)]
        path_of = _new_local if refusal.handed(year, night_from) else _local
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
                     "path": str(Path(outdir) / year / path_of(prefix, name, label)),
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


def lists_of(rec):
    """{(chamber, kind, year): [names]} for the lists of a listing record the
    page answered for; {} for anything that is not such a record."""
    out = {}
    try:
        for li in rec["lists"]:
            if not li.get("unanswered"):
                out[(li["chamber"], li["kind"], str(li["year"]))] = [
                    d["name"] for d in li["documents"]]
    except (KeyError, TypeError, AttributeError):
        return {}
    return out


def unanswered(rec):
    """The lists of a record the page gave no answer for, as the verdict names
    them: ["the Senate Journal list for 2027"]."""
    try:
        return [f"the {SAID[(li['chamber'], li['kind'])]} list for {li['year']}"
                for li in rec["lists"] if li.get("unanswered")]
    except (KeyError, TypeError, AttributeError):
        return []


def shortfall(was, rec, last=None):
    """The lists tonight's read is missing too much of: [(list, the names
    gone, of how many, whether that is counted against an earlier read)].

    AGAINST WHAT THE PAGE LISTED WHEN IT WAS LAST INSTALLED (`last`, the
    listing record on file), where that record holds the list. As first
    written it was counted against every row on file, and a row never leaves
    the queue: each document the page had ever stopped listing counted again
    every night, so with sixteen journals on file the second name to go
    refused all four lists every night after, until somebody edited the
    night's file by hand. Against the last read, a document let through one
    night, within the limit, is not there to be counted the next.

    Where no earlier read of a list is on record -- the first night -- it is
    counted against what is on file, which is then what the page last
    listed. An empty list is not this function's: judge() refuses one
    outright."""
    got, then = lists_of(rec), lists_of(last)
    have = {}
    for r in was:
        have.setdefault((r.get("chamber"), r.get("kind"), r.get("year")), []).append(
            r.get("name"))
    out = []
    for k in sorted(got):
        names, on_file, since = set(got[k]), have.get(k, []), k in then
        before = set(then[k]) if since else None
        base = [n for n in on_file if n in before] if since else on_file
        gone = [n for n in base if n not in names]
        if names and len(gone) > max(LIST_GONE_FLOOR, LIST_GONE_MOST * len(base)):
            out.append((k, gone, len(base), since))
    return out


def judge(was, new, rec, last=None, shorter=False):
    """Why tonight's list may not replace the one on file, or "" when it may.

    The night's rule for every fetch, in this file's terms: whole or not at
    all, and never sharply smaller than what it replaces.

      whole      all four lists were read -- both chambers, calendars and
                 journals -- each for at least the newest year on file. A
                 list the page gave no answer for counts only as read_index
                 may take one: a year's journals, none on file, and that
                 year's calendars read with documents in them
      not empty  a list with documents on file did not come back with none
      not short  a list is missing no more than LIST_GONE_MOST of what the
                 page listed for it when it was last installed (`last`; and
                 more than LIST_GONE_FLOOR): the General Court does not
                 unpublish a calendar, so a shorter list is a page half
                 served (shortfall(), above). `shorter` lets one through:
                 the night passes it once the same list has come back short
                 the same way on enough nights running to be the page's own
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
    got, silent = {}, []
    for li in lists:
        try:
            k = (li["chamber"], li["kind"], str(li["year"]))
            names = [d["name"] for d in li["documents"]]
            directory = str(li.get("directory") or "")
            if li.get("unanswered"):
                silent.append(k)
        except (KeyError, TypeError, AttributeError):
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
    for k in silent:
        calendars = (k[0], "calendar", k[2])
        if k[1] != "journal" or got[k][0] or have.get(k) or calendars in silent \
                or not got.get(calendars, ([], ""))[0]:
            return (f"the {SAID[k[:2]]} list for {k[2]} was not answered, and that is "
                    "taken for none posted yet only of a year's journals with none on file")
    short = {} if shorter else {k: (gone, of, since)
                                for k, gone, of, since in shortfall(was, rec, last)}
    for k in sorted(got):
        names, on_file = set(got[k][0]), have.get(k, [])
        what = f"the {SAID[k[:2]]} list for {k[2]}"
        if on_file and not names:
            return f"{what} came back empty, with {len(on_file)} documents on file"
        if k in short:
            gone, of, since = short[k]
            return (f"{what} came back without {len(gone)} of the {of} documents "
                    + ("it listed when it was last read" if since else "on file"))
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
            lists, n = listing(held, on_file={(r["chamber"], r["kind"], r["year"])
                                              for r in rows})
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
    new, added = merged(rows, lists, refusal.night_years())
    if a.out:
        out = Path(a.out)
        listed = out.with_name(LISTED_NAME)
    else:
        # By hand, on a machine that keeps its own list: the night's rule,
        # against the listing this machine installed last.
        try:
            last = json.loads(listed_file().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            last = None
        why = judge(read_rows(QUEUE), new, rec, last)
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
    for what in unanswered(rec):
        print(f"    no answer for {what}: taken as none posted yet")
    print(f"\n{n} requests, {len(lists)} lists, {news(rows, new)}; "
          f"{len(new):,} in the queue -> {out}")
    return 0


# ---- GitHub's night asks for the documents of the years handed to it --------
#
# From the handover (refusal.night_years) the night is the one machine that
# asks for the calendars and journals of its years (the person's design of 26
# October 2026). --night is that ask: night_plan() decides what may be asked
# before anything is; take_night() asks, one at a time, and writes what
# happened to the night's own record -- never the queue -- and every PDF
# under --root, never in the four folders.
#
# The pause before every request, the first too, jittered by a quarter; the
# most documents a night; how long it may go on starting requests; the tries
# a document gets across nights before a person is told. For one answer, the
# socket's timeout, the whole answer's deadline and the largest PDF taken:
# guesses, written down as guesses, for nothing on this disk measures them.
NIGHT_PAUSE = 20.0
NIGHT_MOST = 8
NIGHT_SECONDS = 600
NIGHT_TRIES = 3
# The night before's list must be this much older than tonight's: a night is
# a day apart, and a second run the same morning finds the first run's list
# on file.
LISTED_APART_HOURS = 20
NIGHT_TIMEOUT = 60
NIGHT_DEADLINE = 90
NIGHT_BYTES_MOST = 50_000_000
# A whole PDF ends with its end-of-file marker; this much of its tail is read for it.
NIGHT_EOF_TAIL = 2048
NIGHT_CHUNK = 1 << 16
# Beside --out: each request the night made and how it ended, and the rows its
# plan marked held without asking -- what the night installs the record against.
ASKED_NAME = "documents_asked.json"
# The bucket's own list of the PDFs it keeps, {path: bytes}, read tonight
# after kit-down (cloud.py docs-night): on the runner only.
IN_BUCKET = Path(".night") / "docs_in_bucket.json"

# A refusal written against a row, in the words the drain wrote it with: a
# 403, 429 or 503, a Retry-After, the firewall's page, or a dropped
# connection, this address's usual way of saying no. A second ask cannot
# tell whether the address or the document is refusing, so the night never
# asks for such a row (the approved rule B7): a person settles it, or hands
# the years back.
REFUSED_BEFORE = re.compile(
    r"(?:Error|HTTP)\s*(?:403|429|503)\b|Forbidden|Too Many Requests|Retry-After|block page|Blocked"
    r"|Attack ID|RemoteDisconnected|Connection\s?(?:Reset|Aborted|Refused)|reset by peer"
    r"|EOF occurred|SSLEOF|WinError 100(?:53|54|60|61)|timed out|refus", re.I)
# The word every refusal the night meets is written with, whatever the answer
# said: refusal.classify calls more answers refused than their own words show
# (a 500 with a Retry-After), and REFUSED_BEFORE reads this ("refus").
REFUSED_MARK = "refused: "
# A journal's number, from its name or its label: "HJ 16 August 19, 2026",
# "SJ 15", "HJ No 21 09-04-2003".
JOURNAL_NO_RE = re.compile(r"\b[HS]J\s*(?:No\.?\s*)?0*(\d+)([A-Za-z]?)(?![A-Za-z0-9])", re.I)


# NO REDIRECTS ON THE NIGHT, as fetch_legislation.py's _NoRedirect has it:
# urlopen follows up to ten, unpaced and uncounted, to addresses no list gave.
# A 3xx is an HTTPError here, and the night records it as a refusal
# (redirect_said): a firewall's redirect to its block page may carry the sign
# only in its Location.
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def redirect_said(err):
    """A redirect the night met, in this project's words: its status and the
    host its Location names, reduced to a host name's own characters."""
    loc = ""
    try:
        loc = (err.headers.get("Location") if err.headers is not None else "") or ""
    except Exception:                                       # noqa: BLE001
        loc = ""
    host = re.sub(r"[^A-Za-z0-9.-]", "", urllib.parse.urlsplit(str(loc)).hostname or "")[:80]
    return f"a redirect (HTTP {err.code}) to {host or 'an address it did not name'}"


# The opener the night's requests go through: one that follows no redirect,
# or a test's fake.
_open = urllib.request.build_opener(_NoRedirect).open


class NotWhole(Exception):
    """An answer that did not arrive whole: too slow, too large, or shorter
    than it said it would be. Said in this project's words."""


def _utc_now():
    """Now, by refusal's UTC clock, as the night's records write it."""
    return refusal._utc().strftime("%Y-%m-%dT%H:%M:%SZ")


def _disk(r):
    """A row's path on this machine. The queue was written on Windows, where
    its paths carry backslashes; read as folders wherever this runs."""
    return Path((r.get("path") or "").replace("\\", "/"))


def _list_of(r):
    """The list a row is on: (chamber, kind, year)."""
    return (r.get("chamber"), r.get("kind"), str(r.get("year")))


def _dict(x):
    return x if isinstance(x, dict) else {}


def _json(path):
    """A JSON file as it reads, or None."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None


def refused_before(error):
    """Whether a row's recorded error is a refusal (REFUSED_BEFORE)."""
    return bool(REFUSED_BEFORE.search(error or ""))


def journal_number(r):
    """A journal row's number as "16" or "16A", or "" where none is read."""
    for text in (r.get("name") or "", r.get("label") or ""):
        m = JOURNAL_NO_RE.search(text) or DOCNUM_RE.search(text)
        if m:
            num = m.group(1)
            digits = "".join(c for c in num if c.isdigit())
            letter = "".join(c for c in num if c.isalpha()) + (
                m.group(2) if m.re is JOURNAL_NO_RE else "")
            if digits:
                return f"{int(digits)}{letter.upper()}"
    return ""


def _tries(r):
    try:
        return int((r.get("attempts") or "0").strip() or 0)
    except (ValueError, AttributeError):
        return NIGHT_TRIES


def directories_of(rec):
    """{(chamber, kind, year): the folder the list's own link names} for the
    lists of a listing record the page answered for; {} for anything else."""
    out = {}
    try:
        for li in rec["lists"]:
            if not li.get("unanswered"):
                out[(li["chamber"], li["kind"], str(li["year"]))] = str(li.get("directory") or "")
    except (KeyError, TypeError, AttributeError):
        return {}
    return out


def listed_address(r, directory):
    """Whether a row's own address is the viewer address its list gives it:
    the index page's viewer, the list's own folder -- in any case, as judge()
    compares it -- and the row's own name. Compared as the viewer reads it,
    so a spelling of the same address in other escapes is the same."""
    try:
        head = SOURCES[(r.get("chamber"), r.get("kind"))][0] + VIEWER
    except KeyError:
        return False
    url, name = r.get("url") or "", r.get("name") or ""
    if not directory or not name or not url.startswith(head):
        return False
    tail = urllib.parse.unquote(url[len(head):])
    return tail.endswith(name) and tail[:len(tail) - len(name)].lower() == directory.lower()


def held_back(rows, latest, dirs):
    """{id(row): (why, the row it is held back for, or None)} for each row its
    list names that the night holds back for a person whatever else is true of
    it (night_plan's rule 3). `latest`: {(chamber, kind, year): the names its
    list's newest read gives}; `dirs`: {(chamber, kind, year): that read's
    folder}.

      unlisted  its own address is not the viewer address its list gives it
                (the list's folder and its name): a request for a name nobody saw
      shared    another row its list names has its path: rows merged before
                the handover gave a supplement its own name share one (the
                2026 Senate list's "No 21 Supplement" and "No 21" are both
                SC021.pdf), and one download would go over the other
      renamed   a journal with the number of a held journal of its chamber and
                year, whose own name its list no longer gives: fetched, a
                second text every reader of journals reads twice"""
    def listed(x):
        return x.get("name") in latest.get(_list_of(x), ())
    paths = {}
    for r in rows:
        p = _disk(r).as_posix().lower()
        if p and p != ".":
            paths.setdefault(p, []).append(r)
    held = {}
    for r in rows:
        if r.get("kind") == "journal" and r.get("state") == "held" and journal_number(r):
            held.setdefault((r.get("chamber"), str(r.get("year")), journal_number(r)), []).append(r)
    out = {}
    for r in rows:
        k = _list_of(r)
        if not listed(r):
            continue
        if not listed_address(r, dirs.get(k, "")):
            out[id(r)] = ("unlisted", None)
            continue
        others = [x for x in paths.get(_disk(r).as_posix().lower(), ()) if x is not r and listed(x)]
        if others:
            out[id(r)] = ("shared", others[0])
            continue
        if r.get("kind") == "journal" and journal_number(r):
            gone = [h for h in held.get((k[0], k[2], journal_number(r)), ()) if not listed(h)]
            if gone:
                out[id(r)] = ("renamed", gone[0])
    return out


def live(word, key, hand, night):
    """The person's one-shot id for `key` under `word` -- "again" (docs-again)
    or "accept" (docs-accept) -- while the night's record has not spent it:
    the handover's id where it differs from the one the night's row carries;
    "" otherwise. No date is compared with anything, so one id buys exactly
    one request, or one text."""
    want = str(_dict(_dict(hand).get(word)).get(key) or "")
    had = str(_dict(_dict(_dict(night).get("rows")).get(key)).get(word) or "")
    return want if want and want != had else ""


def night_record(hand):
    """The night's own record of the years the handover `hand` gave it: the
    one on file (refusal.read_night_record) where its "handover" is the
    record's "at", or a new one. {"handover", "from_year", "rows": {key:
    fields}, "lists": {list: {read, directory, names}}, "dropped": day}."""
    n = refusal.read_night_record() or {}
    at = _dict(hand).get("at")
    if not (at and n.get("handover") == at):
        n = {"handover": at, "from_year": _dict(hand).get("from_year")}
    for k, empty in (("rows", {}), ("lists", {})):
        if not isinstance(n.get(k), dict):
            n[k] = empty
    n.setdefault("dropped", None)
    return n


def remember_lists(record, tonight, before):
    """Each list of the night's years read tonight, kept in the night's
    `record` as {read, directory, the names both reads gave} where the night
    before's read is at least LISTED_APART_HOURS older; a list no longer read
    keeps its last entry. From 1 February the listing reads a year's lists no
    more (years_wanted), and this is what the night asks that year's last
    documents from: the two reads that named them, at their list's own
    address (night_plan's rule 2). The record, changed in place."""
    apart = _hours_apart(_dict(before).get("read"), _dict(tonight).get("read"))
    if apart is None or apart < LISTED_APART_HOURS:
        return record
    then, dirs = lists_of(before), directories_of(tonight)
    kept = record.setdefault("lists", {})
    for k, names in lists_of(tonight).items():
        if k in then and refusal.handed(k[2], record.get("from_year")):
            both = set(then[k])
            kept["|".join(k)] = {"read": tonight["read"], "directory": dirs.get(k, ""),
                                 "names": [n for n in names if n in both]}
    return record


def night_plan(rows, tonight, before, most, y, hand=None, night=None, bucket=None, root=None):
    """What tonight may ask for, decided before anything is asked; it asks
    nothing and writes nothing. A dict:

      ask      the rows to ask for, in the order they are asked, at most `most`
      waiting  how many more might have been asked, past the cap
      text     rows to mark held from the text beside them, unasked
      bucket   rows to mark held from the bucket's copy of their PDF, unasked
      person   [(reason, row, detail)]: the rows only a person can move, the
               reason one of "held back", "refused", "not found", "tried
               out", "text refused" and "not in the bucket"
      new      rows listed for the first time tonight, which wait a night
      why      "" or why nothing may be asked at all

    `rows` is the queue as load_queue lays it; `tonight` and `before` the
    listing records installed tonight and the night before; `y` the first year
    of the night's (the handover's from_year, or this year before one);
    `hand` the handover record, for the person's word; `night` the night's
    own record (night_record); `bucket` the bucket's list of kept PDFs
    (IN_BUCKET), None where it was not read; `root` where tonight's PDFs go.

    THE RULES (the person's design of 26 October 2026), in this order:

      1  the night's years only: from `y`
      2  named by the two newest reads of its list, at least
         LISTED_APART_HOURS apart: tonight's and the night before's, or for a
         list no longer read the pair kept in the night's record
         (remember_lists). A name the lists gave once, or never, is not asked
      3  held back for a person (held_back): neither asked for nor held from a
         text, whatever else is true of it
      4  its text: a wanted row with a .txt beside its path is held from it --
         whatever its tries or its error, which is cleared -- and not asked
         for. A row not found is not: a text at its path is another row's
      5  the bucket: a wanted row whose PDF the bucket keeps is held, its text
         to be made from the bucket's copy, and not asked for
      6  settled by a person: never asked for, never named
      7  again: a live one-shot id (live) asks once, first in line, whatever
         the row's state or tries -- never past rules 1 to 3, nor a refusal
      8  asked: wanted, no refusal recorded against it, under NIGHT_TRIES tries
      9  for a person: every other row its lists name, by reason
      10 order: again first, then the never tried, then oldest first within
         each list, the lists in the queue's order; at most `most` requests,
         a document not found counted as one"""
    out = {"ask": [], "waiting": 0, "text": [], "bucket": [], "person": [], "new": 0, "why": ""}
    if not lists_of(tonight):
        out["why"] = "tonight's list of calendars and journals is not on file"
        return out
    if not lists_of(before):
        out["why"] = "the night before's list of calendars and journals is not on file"
        return out
    if tonight.get("read") == before.get("read"):
        out["why"] = ("tonight's list is the night before's, read at the same time: it was "
                      "not installed tonight")
        return out
    apart = _hours_apart(before.get("read"), tonight.get("read"))
    if apart is None or apart < LISTED_APART_HOURS:
        out["why"] = ("when the two lists were read is not on file" if apart is None else
                      "the night before's list is from this morning: it was read less than "
                      f"{LISTED_APART_HOURS} hours before tonight's, by an earlier run")
        return out
    # {list: (the names its newest read gives, those both reads give, its folder)}
    named = {}
    for k, e in _dict(_dict(night).get("lists")).items():
        if isinstance(e, dict) and isinstance(e.get("names"), list):
            named[tuple(str(k).split("|"))] = (e["names"], e["names"], str(e.get("directory") or ""))
    now, then, dirs = lists_of(tonight), lists_of(before), directories_of(tonight)
    for k, names in now.items():
        named[k] = (names, [n for n in names if n in set(then.get(k, ()))], dirs.get(k, ""))
    back = held_back(rows, {k: v[0] for k, v in named.items()}, {k: v[2] for k, v in named.items()})
    settled, mine = _dict(_dict(hand).get("settled")), _dict(_dict(night).get("rows"))
    blocks, asks = {}, []
    for i, r in enumerate(rows):
        k, key, state = _list_of(r), doc_key(r), r.get("state")
        if not refusal.handed(k[2], y) or k not in named:                      # 1
            continue
        if r.get("name") not in named[k][1]:                                    # 2
            if state == "wanted" and r.get("name") in named[k][0]:
                out["new"] += 1
            continue
        again, why = live("again", key, hand, night), back.get(id(r))
        if why and (state == "wanted" or again):                                # 3
            if key not in settled:
                out["person"].append(("held back", r, why[0]))
            continue
        if state == "wanted" and _disk(r).with_suffix(".txt").exists():         # 4
            out["text"].append(r)
            continue
        if state == "wanted" and bucket is not None and _disk(r).as_posix() in bucket:   # 5
            out["bucket"].append(r)
            continue
        if key in settled:                                                      # 6
            continue
        if refused_before(r.get("error")):
            out["person"].append(("refused", r, r.get("error") or ""))
            continue
        if again or (state == "wanted" and _tries(r) < NIGHT_TRIES):            # 7, 8
            asks.append((0 if again else 1 if _tries(r) == 0 else 2,
                         blocks.setdefault(k, len(blocks)), -i, r))
            continue
        e = _dict(mine.get(key))                                                # 9
        text = str(e.get("text") or "")
        if state == "gone":
            out["person"].append(("not found", r, r.get("error") or ""))
        elif state in ("wanted", "failed"):
            out["person"].append(("tried out", r, f"{_tries(r)} tries"))
        elif text.startswith(REFUSED_MARK) and not live("accept", key, hand, night):
            out["person"].append(("text refused", r, text[len(REFUSED_MARK):]))
        elif (e.get("sha256") and text != "pending" and bucket is not None
              and _disk(r).as_posix() not in bucket
              and not (root and (Path(root) / _disk(r)).exists())):
            out["person"].append(("not in the bucket", r, ""))
    order = [a[-1] for a in sorted(asks, key=lambda a: a[:3])]                 # 10
    out["ask"], out["waiting"] = order[:max(0, most)], max(0, len(order) - max(0, most))
    return out


def _hours_apart(earlier, later):
    """Hours from one listing record's "read" to another's, or None where
    either will not read. Both are written the same way, by take_listing on
    the same kind of machine."""
    try:
        a = datetime.strptime(str(earlier), "%Y-%m-%dT%H:%M:%S")
        b = datetime.strptime(str(later), "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None
    return (b - a).total_seconds() / 3600


def whole_pdf(blob):
    """"" when `blob` reads as a whole PDF, or why not, in this project's
    words. The drain took anything that began "%PDF", so a file the server
    held half written was saved and marked held for good."""
    if not blob.startswith(b"%PDF-"):
        return f"not a PDF ({len(blob):,} bytes)"
    if b"%%EOF" not in blob[-NIGHT_EOF_TAIL:]:
        return "not a whole PDF: it has no end-of-file marker"
    return ""


def read_whole(r, started):
    """An answer's body, read in chunks: whole, within NIGHT_DEADLINE seconds
    of `started`, no larger than NIGHT_BYTES_MOST, and as long as its own
    Content-Length says. NotWhole otherwise. The socket's timeout bounds one
    read; this bounds them all, so a server that sends a byte a minute
    cannot hold the night's lock into the morning."""
    headers = getattr(r, "headers", None)
    said = (headers.get("Content-Length") if headers is not None else None) or ""
    chunks, n = [], 0
    while True:
        b = r.read(NIGHT_CHUNK)
        # After every read, the last empty one too: an answer that came
        # whole in two minutes still took two minutes of the night's lock.
        if time.time() - started > NIGHT_DEADLINE:
            raise NotWhole(f"it took longer than {NIGHT_DEADLINE} seconds")
        if not b:
            break
        n += len(b)
        if n > NIGHT_BYTES_MOST:
            raise NotWhole(f"it is larger than {NIGHT_BYTES_MOST // 1_000_000} MB")
        chunks.append(b)
    if str(said).strip().isdigit() and int(said) != n:
        raise NotWhole(f"it is {n:,} bytes of the {int(said):,} it said")
    return b"".join(chunks)


def _get_document(url):
    """One document, whole (read_whole), through _open."""
    started = time.time()
    req = urllib.request.Request(url, headers=dict(UA))
    with _open(req, timeout=NIGHT_TIMEOUT) as r:
        return read_whole(r, started)


def _said(kind, e, why):
    """How a request ended, in this project's words: the night's verdict and
    its run's page are public, and take none of a server's."""
    if kind == "missing":
        return f"not found (HTTP {getattr(e, 'code', '?')})"
    if kind in ("refused", "dropped"):
        return kind
    if isinstance(e, urllib.error.HTTPError):
        return f"failed: HTTP {e.code}"
    if isinstance(e, NotWhole):
        return f"failed: {e}"
    if e is not None:
        return f"failed: {type(e).__name__}"
    return f"failed: {why}"


def take_night(a, rows, held):
    """--night: ask for what night_plan() allows, and write what happened to
    the night's own record of its years at --out; nightly.py installs it, or
    does not. 0 when it ended as it should -- everything asked that might be,
    the cap reached, or the time allowed spent; 1 when it stopped on a failure
    or a second document not found, or could ask nothing at all; 2 on a
    refusal, recorded; 3 when the lock it runs under was lost.

    THE STOP RULES. A refusal -- a 403, 429 or 503, a Retry-After, the
    firewall's page served as a 200, a redirect -- is written against its row
    beginning REFUSED_MARK, the record goes to disk, and only then is it
    noted (refusal.note), and nothing more is asked. A 404 marks its row gone;
    a second ends the step, because 404s one after another are what a scan of
    guessed names looks like from the far end, which is how this address was
    first blocked. Any other failure counts its try, writes no error -- the
    Calendar page's picker drops a row that carries one -- and ends the step.
    A dropped connection counts as all NIGHT_TRIES tries; one on the next
    night that asks too (the record's "dropped" names the last such night) is
    a refusal, the drain's two-drop rule carried across nights. No request
    starts once --seconds have passed.

    WHAT IT WRITES. The night's record, whole, to --out, and beside it
    ASKED_NAME: each request, with its key, bytes, seconds, sha256 and how it
    ended, and the rows the plan held from a text or from the bucket's copy.
    Both are written before every request, with that request and its try (and
    a live `again` id) already in them, so a step killed at its limit still
    counts what it asked; the log first, so the record never changes a row its
    log does not name. A PDF fetched goes to --root/<its path> through a part
    file, and its row becomes held with its text to be made (text: pending)."""
    t0 = time.time()
    out, root = Path(a.out), Path(a.root)
    asked_file = out.with_name(ASKED_NAME)
    log = {"started": _utc_now(), "most": a.most, "seconds": a.seconds, "requests": 0,
           "asked": [], "held_from_text": [], "from_bucket": [], "person": {},
           "new_tonight": 0, "waiting": 0, "stopped": "", "exit": 1}
    code, stopped, done, plan, night, dropped = 0, "", False, None, None, False

    def write(path, d):
        part = path.with_name(path.name + ".part")
        part.parent.mkdir(parents=True, exist_ok=True)
        part.write_text(json.dumps(d, indent=1) + "\n", encoding="utf-8", newline="\n")
        os.replace(part, path)

    def keep():
        write(asked_file, log)
        if night is not None:
            write(out, night)

    def put(r, **kw):
        e = dict(_dict(night["rows"].get(doc_key(r))))
        e.update({f: r.get(f) or "" for f in DRAIN_FIELDS}, **kw)
        night["rows"][doc_key(r)] = e
    try:
        state, hand = refusal.read_handover()
        y = refusal.night_years() if state == "ok" else None
        bucket = _json(IN_BUCKET)
        if y is None:
            code, stopped = 1, "nothing was asked for: the handover is not in force"
        elif not isinstance(bucket, dict):
            code, stopped = 1, ("nothing was asked for: the bucket's list of the PDFs it keeps "
                                "was not read tonight")
        else:
            night = night_record(hand)
            plan = night_plan(rows, _json(listed_file()), _json(a.night), a.most, y, hand,
                              night, bucket, root)
            for r in plan["text"]:
                r["state"], r["error"] = "held", ""
                put(r)
                log["held_from_text"].append(doc_key(r))
            for r in plan["bucket"]:
                r["state"], r["error"] = "held", ""
                r["bytes"] = str(bucket.get(_disk(r).as_posix()) or "")
                put(r, text="pending")
                log["from_bucket"].append(doc_key(r))
            for reason, r, _ in plan["person"]:
                log["person"].setdefault(reason, []).append(doc_key(r))
            log["new_tonight"] = plan["new"]
            keep()
            print(f"{len(plan['ask'])} to ask for, at most {a.most}, about {NIGHT_PAUSE:g}s apart "
                  f"and as long before the first; {len(plan['text'])} held from their text; "
                  f"{len(plan['bucket'])} from the bucket's copy; {len(plan['person'])} for a "
                  f"person; {plan['new']} listed for the first time tonight", flush=True)
            if plan["why"]:
                code, stopped = 1, f"nothing was asked for: {plan['why']}"
            missing = 0
            for r in plan["ask"]:
                pause = NIGHT_PAUSE * random.uniform(0.75, 1.25)
                if time.time() - t0 + pause >= a.seconds:
                    stopped = f"the {a.seconds:g} seconds allowed were spent"
                    break
                time.sleep(pause)
                # Immediately before the request, not before the pause.
                if refusal.MARK.exists():
                    code, stopped = 2, "a refusal is on file"
                    break
                if not held.still():
                    code, stopped = 3, "the lock this runs under is gone"
                    break
                key = doc_key(r)
                entry = {"key": key, "path": r.get("path") or "", "at": _utc_now(), "bytes": 0,
                         "seconds": 0.0, "sha256": "", "ended": "no answer: it was stopped while asking"}
                log["asked"].append(entry)
                log["requests"] += 1
                # THE TRY COUNTED BEFORE THE REQUEST, with the id it spends.
                r["attempts"] = str(_tries(r) + 1)
                again = live("again", key, hand, night)
                put(r, **({"again": again} if again else {}))
                log["stopped"] = "it was stopped while asking"
                keep()
                begun, blob, e, why = time.time(), b"", None, ""
                try:
                    blob = _get_document(r["url"])
                    kind = refusal.classify(body=blob[:4000].decode("utf-8", "replace"))
                    why = "the firewall's block page, served as 200" if kind else whole_pdf(blob)
                    kind = kind or ("failed" if why else None)
                except Exception as err:                        # noqa: BLE001
                    e, why = err, f"{type(err).__name__}: {err}"
                    kind = refusal.classify(err) or "failed"
                    if isinstance(err, urllib.error.HTTPError) and 300 <= err.code < 400:
                        kind, why = "refused", redirect_said(err)
                log["stopped"] = ""
                entry.update(seconds=round(time.time() - begun, 1), bytes=len(blob))
                if kind == "dropped":
                    r["attempts"] = str(max(_tries(r), NIGHT_TRIES))
                    if night.get("dropped"):
                        kind, why = "refused", ("a dropped connection on the second night "
                                                f"running that asked (the first {night['dropped']})")
                    night["dropped"], dropped = _utc_now()[:10], True
                if kind:
                    entry["ended"] = _said(kind, e, why)
                    print(f"  [{log['requests']}] {key}: {entry['ended']}", flush=True)
                    if kind == "refused":
                        # THE MARK ON DISK BEFORE THE REFUSAL GOES ON FILE.
                        r["error"] = (REFUSED_MARK + why)[:180]
                        put(r)
                        keep()
                        refusal.note("fetch_calendar_archive", why[:180])
                        code, stopped = 2, "the General Court refused a request"
                        print("\nRefused. Recorded, and nothing more is asked of it.\n"
                              "python3 netcheck.py says what kind of refusal it is "
                              "without making it worse.", flush=True)
                        break
                    if kind == "missing":
                        r["state"], r["error"] = "gone", why[:180]
                        put(r)
                        missing += 1
                        if missing >= 2:
                            code, stopped = 1, "a second document the list names was not found"
                            break
                        continue
                    put(r)
                    code, stopped = 1, ("a connection was dropped" if kind == "dropped"
                                        else f"a request {entry['ended']}")
                    break
                dest = root / _disk(r)
                try:
                    if not dest.resolve().is_relative_to(root.resolve()):
                        raise OSError("its path is not under --root")
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    part = dest.with_name(dest.name + ".part")
                    part.write_bytes(blob)
                    os.replace(part, dest)
                except OSError as err:
                    entry["ended"] = f"failed: it could not be saved ({type(err).__name__})"
                    put(r)
                    code, stopped = 1, "a document fetched could not be saved"
                    break
                sha = hashlib.sha256(blob).hexdigest()
                r["state"], r["bytes"], r["error"] = "held", str(len(blob)), ""
                r["fetched"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                put(r, text="pending", sha256=sha)
                entry.update(ended="fetched", sha256=sha)
                print(f"  [{log['requests']}] {key}: fetched, {len(blob):,} bytes, "
                      f"{entry['seconds']:g}s", flush=True)
            if log["requests"] and not dropped:
                night["dropped"] = None
        done = True
    finally:
        if plan is not None:
            log["waiting"] = plan["waiting"] + len(plan["ask"]) - log["requests"]
        log.update(ended=_utc_now(), stopped=stopped if done else (
            stopped or "it stopped on an error of its own"), exit=code if done else 1)
        keep()
    got = sum(1 for x in log["asked"] if x["ended"] == "fetched")
    print(f"\n{log['requests']} requests, {got} fetched, {time.time() - t0:.0f}s"
          + (f"; stopped: {stopped}" if stopped else "")
          + f"; {log['waiting']} still to ask for -> {out}", flush=True)
    return code


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--discover", action="store_true")
    ap.add_argument("--listing", action="store_true",
                    help="what each index lists for its newest year, added to the "
                         "queue: the night's read, four requests")
    ap.add_argument("--out", help="(--listing) write the queue here, and "
                                  f"{LISTED_NAME} beside it, and leave judging and "
                                  "installing them to the caller: nightly.py. (--night) "
                                  f"the night's record of its years, with {ASKED_NAME} "
                                  "beside it")
    ap.add_argument("--night", metavar="PREV_LISTED",
                    help="GitHub's night, the years handed to it: ask for what tonight's "
                         "list and the night before's (PREV_LISTED) both name, gently "
                         "(take_night). Writes --out, the log beside it, and each PDF "
                         "under --root")
    ap.add_argument("--most", type=int, default=1,
                    help=f"(--night) the most documents asked for, 1 to {NIGHT_MOST} (default 1)")
    ap.add_argument("--seconds", type=float, default=NIGHT_SECONDS,
                    help="(--night) no request starts after this many seconds, at most "
                         f"{NIGHT_SECONDS} (the default)")
    ap.add_argument("--root", help="(--night) the folder each PDF fetched is saved under, at "
                                   "its own path: never the four folders")
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
    if a.night is None and (a.root or a.most != 1 or a.seconds != NIGHT_SECONDS):
        ap.error("--most, --seconds and --root belong to --night")
    if a.night is not None:
        if a.listing or a.discover or a.status or a.list:
            ap.error("--night asks for what two nights' lists name, at its own pace: it "
                     "takes no --listing, --discover, --status or --list")
        if not (a.out and a.root):
            ap.error("--night writes only --out and under --root, and needs both")
        if Path(a.root).resolve() == Path(".").resolve() or Path(a.out).resolve() in {
                QUEUE.resolve(), fetched_file().resolve(), listed_file().resolve(),
                refusal.NIGHT_RECORD.resolve()}:
            ap.error("--night writes none of the queue's own files, and no PDF in the four "
                     "folders: the night installs what it writes")
        if not 1 <= a.most <= NIGHT_MOST:
            ap.error(f"--most is 1 to {NIGHT_MOST}: the night asks for no more documents "
                     "than that")
        if not 0 < a.seconds <= NIGHT_SECONDS:
            ap.error(f"--seconds is more than 0 and at most {NIGHT_SECONDS}")
        # GITHUB'S NIGHT'S, AND ONLY THERE (the person's design of 26 October
        # 2026): from the handover the laptop has no request path for the
        # night's years at all, and before it the laptop's drain is the one.
        if os.environ.get("GITHUB_ACTIONS") != "true":
            print("--night does not run on this machine: it is GitHub's night's alone. "
                  "The calendars and journals of the years handed to the night reach this "
                  "machine with python3 src/ops/cloud.py pull; the drain fetches the "
                  "others.", file=sys.stderr)
            return refusal.STOOD_DOWN

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
            "with python3 src/ops/cloud.py pull. The drain still runs here, and keeps "
            f"what it fetches in {fetched_file()}.")
        refusal.check("The calendar and journal listing")
    if a.listing:
        return take_listing(a, rows)

    if a.night is not None:
        refusal.check("The night's fetch of the calendars and journals handed to it")
        with refusal.hold("the night's fetch of the calendars and journals") as held:
            return take_night(a, rows, held)

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
        # THE NIGHT'S YEARS ARE NOT ASKED FOR HERE (the person's design of 26
        # October 2026): from the handover, GitHub's night is the one machine
        # that asks for them.
        y = refusal.night_years()
        left = [r for r in todo if refusal.handed(r.get("year"), y)]
        if left:
            todo = [r for r in todo if not refusal.handed(r.get("year"), y)]
            print(f"{len(left):,} wanted left to the night: {refusal.years_said(y)}")
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
