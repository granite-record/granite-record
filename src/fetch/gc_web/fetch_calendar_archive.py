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
    python3 src/fetch/gc_web/fetch_calendar_archive.py --night PREV_LISTED --out .night/files/queue.csv --most 1
                                                                          # GitHub's night only: what
                                                                          #   two nights' lists name
    python3 src/fetch/gc_web/fetch_calendar_archive.py --settle "SJ 15 June 18, 2026.pdf"
                                                                          # a possible rename that is
                                                                          #   the same journal; no network

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

state is wanted / held / failed / gone, or settled: the same document as
another on file, by a person's word (--settle, below), and never asked for. A
file already on disk is never asked for again, so an interrupted run resumes
by re-reading the queue and every run is idempotent.

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
                   (LISTING_MOST). No PDF is asked for: --night, below,
                   is the night's one fetch of a document. Since 26
                   October 2026 the night runs this only if it can end by
                   12:00 UTC (nightly.asking_left), which the person
                   approved for the list too
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

THE NEWEST DOCUMENTS ARE THE NIGHT'S TO FETCH (26 October 2026)

The person approved GitHub's night fetching new calendars and journals
itself, gently. --night is that fetch, and it is built to the person's plan,
rule by rule (night_plan() and take_night(), below):

  who runs it      nightly.take_document_files, and nothing else: under the
                   night's lock, straight after the list, and only when the
                   repository's NIGHT_DOCUMENTS is a number (1 to NIGHT_MOST,
                   which it passes as --most), tonight's list went in and its
                   listing exited 0, no refusal is on file, the text canary
                   passed, and the step can end by 12:00 UTC; killed at
                   nightly.DOCS_FILES_MINUTES whatever its own limits say.
                   Unset or "off", nothing calls it; "shadow", and any dry
                   run, call night_plan() alone, which asks nothing. It
                   landed switched off (26 October 2026), and the person
                   turns it on
  what it asks     one GET of a row's own address -- the viewer address the
                   page's own list gave, its folder and its name, which is
                   checked -- for a row both tonight's list and the night
                   before's name, that no refusal is recorded against and
                   that has been asked fewer than NIGHT_TRIES times; and
                   following no redirect (_NoRedirect). A row with its text
                   already beside it is marked held unasked, before the cap
                   is counted; one held back for a person -- a journal that
                   may be a renamed one, a path two rows share, an address
                   its list does not give (held_back) -- is named and not
                   asked for. Oldest first within each list, at most --most
                   (never more than NIGHT_MOST)
  how gently       --pause seconds, jittered, before every request, the first
                   as well, with the refusal record and the lock read again
                   right before each; no request starts after --seconds; an
                   answer is a whole PDF ("%PDF-" first, "%%EOF" in its last
                   bytes, as long as it said, inside NIGHT_DEADLINE and
                   NIGHT_BYTES_MOST) or it is not taken
  when it stops    one refusal, recorded: status 2. The first failure that is
                   not a 404, or a second 404: status 1. Nothing is asked
                   again that night
  what it writes   the queue to --out and nowhere else, and beside it each
                   request and how it ended (ASKED_NAME) -- both before every
                   request as well, the try already counted, so a kill at the
                   night's limit loses neither; each PDF to its own path
                   through a part file. The night installs the queue, or does
                   not
  and after it     the night, out of the lock and before the build, makes
                   each document's text and checks it is that document's
                   (nightly.make_texts); the text goes to the kit, and the
                   PDF out of the four folders the build reads and into the
                   bucket's docs/ (cloud.py docs-up), from where docs-down
                   brings it to the laptop. The build reads no PDF

A NEW SUPPLEMENT KEEPS ITS OWN NAME. _local() names a calendar by its
number, and the Senate's "No 27 Supplement ..." of 19 June 2025 and its two
siblings came before "No 27 June 19 2025" on the page, all four SC027.pdf:
the first saved there, and the base edition then counted as held without
ever being asked for. merged() gives a new row whose name or label says
Supplement its source name, as _local() already does for a name with no
number. A path on file never moves.

AND THE LAPTOP LEAVES THEM TO IT. On a laptop that has stood down, --night
refuses (refusal.stand_down); and once the night's own verdict says it
fetches the newest documents (its switch a number, refusal.night_documents),
the drain there leaves the rows of this year and the year before, and any
later, to the night, and says how many it left. Until then -- the switch
lands off, and the person turns it on -- the laptop fetches them as before.

ONLY THE ONES THE NIGHT WILL STILL ASK FOR (the review of 26 October 2026).
A row of those years with a refusal recorded against it, NIGHT_TRIES tries,
a name the newest list on file no longer gives -- last year's leftovers,
once the year's list has closed -- or one the night holds back for a person
is never asked for by the night, and its verdict calls it a person's. So the
drain does not leave those to the night, where nobody would have fetched
them: it takes them when a person runs it, and says how many
(nights_to_ask). And its own record of a row it leaves to the night goes,
so that an older line of this machine's is not laid over the night's.

THE NEWER RECORD WINS (the review of 26 October 2026). The laptop's record
of a document is laid over the night's list only where it is the newer one
(laptop_wins): it has the document, or a person's word on it (--settle), or
it tried more often than the night's row says, and the night's row is not
gone, failed or refused. Laid over every row it named, an old "wanted, one
try" undid the night's own 404 or refusal every night.
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
from datetime import date, datetime, timezone

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
# A row a person has settled as the same document as another on file (the
# review of 26 October 2026): a journal the night held back as a possible
# rename that is that very journal. Not "held": two held journals that claim
# one number give that number no link at all (queue_links), and a renamed
# journal has a text already, under its old name.
SETTLED = "settled"

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
    """The path a row NEW to the queue is given: _local()'s, but a supplement
    keeps its source name (the person's plan, 26 October 2026). The Senate's
    page lists "No 27 Supplement June 19 2025" and two more supplements of No
    27 before "No 27 June 19 2025", and by number alone all four were
    SC027.pdf: the first saved there, and the base edition then counted as
    held, never asked for. A row on file keeps the path it has."""
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


def laptop_wins(night, laptop):
    """Whether the laptop's record of a document is laid over the night's.

    THE NEWER RECORD WINS (the review of 26 October 2026). Once the night
    fetched documents itself, the laptop's older line -- wanted, one try, "not
    a PDF" -- went over the night's own of the same document -- gone after a
    404, or a refusal -- every night, so the night asked again for a document
    that had answered 404 or 403, and its tries never reached three. The
    laptop's wins only where it has the document (held), or where it has
    tried more often than the night's record says and the night's record is
    not gone, failed or refused. A person's word (SETTLED) wins too."""
    if (laptop.get("state") or "") in ("held", SETTLED):
        return True
    if (night.get("state") or "") in ("gone", "failed") or refused_before(night.get("error")):
        return False
    return _tries(laptop) > _tries(night)


def load_queue():
    """The queue, with what a stood-down laptop's drain has fetched laid over
    it where that is the newer record (laptop_wins): the list is the night's
    file and the laptop's fetching its own, and everything here reads them as
    one."""
    rows = read_rows(QUEUE)
    mine = {_key(r): r for r in read_rows(fetched_file())}
    for r in rows:
        r["label"] = r.get("label") or ""
        m = mine.get(_key(r))
        if m and laptop_wins(r, m):
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
                     "path": str(Path(outdir) / year / _new_local(prefix, name, label)),
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
    new, added = merged(rows, lists)
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


# ---- the night's fetch of what the lists name (26 October 2026) --------------
#
# The person approved GitHub's night fetching the newest calendars and
# journals itself, gently (the person, 26 October 2026: "The nightly may
# gently fetch new calendars, journals, and the hearing schedule from the
# general court."). These numbers are how gently.
#
# Seconds before every request, the first as well -- the lane's pace for the
# Senate archive -- and the least a caller may ask for, the drain's own
# fifteen. The most documents a night whatever the caller asks; the person
# raises the night's own number a step at a time (1, then 4, then 8). How long the step may go
# on starting requests: none starts after it. How many tries a document gets,
# across nights, before the night stops asking and a person is told. And for
# one answer: the socket's timeout, the whole answer's deadline and the
# largest PDF taken. Those last three are guesses, written down as guesses:
# nothing on this disk measures them.
NIGHT_PAUSE = 20.0
NIGHT_PAUSE_LEAST = 15.0
NIGHT_MOST = 8
NIGHT_SECONDS = 600
NIGHT_TRIES = 3
NIGHT_TIMEOUT = 60
NIGHT_DEADLINE = 90
NIGHT_BYTES_MOST = 50_000_000
# A whole PDF ends with its end-of-file marker; this much of its tail is read for it.
NIGHT_EOF_TAIL = 2048
NIGHT_CHUNK = 1 << 16
# Beside --out: each request the night made, and how it ended.
ASKED_NAME = "documents_asked.json"

# A refusal written against a row, in the words the drain wrote it with: a
# 403, 429 or 503, a Retry-After, the firewall's page, or a connection this
# address dropped, its usual way of saying no. 664 Senate calendars of
# 1998-2008 still carry "HTTP Error 403: Forbidden" from 9 September, and a
# second ask of a document that once answered 403 cannot tell whether the
# address or the document is refusing (watchers/gc_lane.queue, the proving
# run of 12 September). The night never asks for such a row; a person does.
REFUSED_BEFORE = re.compile(
    r"(?:Error|HTTP)\s*(?:403|429|503)\b|Forbidden|Too Many Requests|Retry-After|block page|Blocked"
    r"|Attack ID|RemoteDisconnected|Connection(?:Reset|Aborted|Refused)|WinError 100(?:53|54|60|61)"
    r"|timed out|refus", re.I)
# THE WORD EVERY REFUSAL IS WRITTEN WITH (the review of 26 October 2026). A
# row's error was the answer's own words, and refusal.classify calls more
# answers refused than those words show: a 500 carrying a Retry-After, or
# the firewall's page served with a 400. Written as "HTTPError: HTTP Error
# 500: ...", refused_before() did not know it for one, and once a person
# cleared the record the night put that very document first in line again.
# So a refusal is written against its row beginning with this, whatever the
# answer was, and REFUSED_BEFORE reads it ("refus").
REFUSED_MARK = "refused: "
# A journal's number, from its name or its label: "HJ 16 August 19, 2026",
# "SJ 15", "HJ No 21 09-04-2003".
JOURNAL_NO_RE = re.compile(r"\b[HS]J\s*(?:No\.?\s*)?0*(\d+)([A-Za-z]?)(?![A-Za-z0-9])", re.I)


# NO REDIRECTS ON THE NIGHT (the review of 26 October 2026), as
# fetch_legislation.py's _NoRedirect has it: urlopen follows up to ten,
# back to back, with no pause and none counted, to addresses no list gave,
# so one request the night counted could be eleven. A 3xx is an HTTPError
# here, which refusal.classify reads as a failure, and the step ends on it.
# Nobody on this disk knows whether the General Court's viewer answers with
# a redirect; if it does, the first night's one request says "failed: HTTP
# 302" and nothing more is asked, and following one -- paced and counted --
# is a person's decision.
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


# The opener the night's requests go through: one that follows no redirect,
# or a test's fake.
_open = urllib.request.build_opener(_NoRedirect).open


class NotWhole(Exception):
    """An answer that did not arrive whole: too slow, too large, or shorter
    than it said it would be. Said in this project's words."""


def _utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _disk(r):
    """A row's path on this machine. The queue was written on Windows, where
    its paths carry backslashes; read as folders wherever this runs."""
    return Path((r.get("path") or "").replace("\\", "/"))


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


def nights_to_ask(r, lists, back=None):
    """Whether GitHub's night may still ask for a wanted row of its years
    (night_plan's own rules, the night before's list aside): no refusal
    recorded against it, fewer than NIGHT_TRIES tries, named by the newest
    list on file (`lists`, as lists_of() gives it), and not held back for a
    person (`back`, as held_back() gives it for that list: a possible
    rename, a path another row shares, an address the list does not give).
    The night never asks for one it holds back, so left to the night it was
    fetched by nobody (the review of 26 October 2026). With no list on file
    at all the row counts as named, so that a laptop that cannot tell leaves
    it to the night rather than ask for it too."""
    if refused_before(r.get("error")) or _tries(r) >= NIGHT_TRIES:
        return False
    if back and id(r) in back:
        return False
    return not lists or r.get("name") in lists.get(
        (r.get("chamber"), r.get("kind"), str(r.get("year"))), ())


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


def held_back(rows, rec):
    """{id(row): (why, the row it is held back for, or None)}: each wanted
    row the listing record `rec` names that the night holds back for a
    person, whatever else is true of it (night_plan; and the laptop's drain,
    through nights_to_ask, takes these when a person runs it):

      unlisted  its own address is not the viewer address that list gives
                it -- the list's folder and its name. The night asks only for
                what the page listed, and a stored address built some other
                way is a request for a name nobody saw (the review of 26
                October 2026)
      shared    another row of the queue that the same record lists has its
                path. Rows merged before supplements kept their own names
                share one: the 2026 Senate list's "No 21 Supplement" and
                "No 21" are both SC021.pdf, so
                the second download went over the first, or the base edition
                was counted held from the supplement's text. A person repairs
                the path; until then neither is asked for or held from text
      renamed   a journal with the number of a held journal of its chamber
                and year, whose own name that list no longer gives: a journal
                is named by the file the General Court posted, so a rename is
                a second row, a second fetch and a second text every reader
                of journals reads twice"""
    now, dirs = lists_of(rec), directories_of(rec)
    if not now:
        return {}
    paths = {}
    for r in rows:
        p = _disk(r).as_posix().lower()
        if p and p != ".":
            paths.setdefault(p, []).append(r)
    held = {}
    for r in rows:
        if r.get("kind") == "journal" and r.get("state") == "held":
            n = journal_number(r)
            if n:
                held.setdefault((r.get("chamber"), str(r.get("year")), n), []).append(r)
    out = {}
    for r in rows:
        k = (r.get("chamber"), r.get("kind"), str(r.get("year")))
        if r.get("state") != "wanted" or r.get("name") not in now.get(k, ()):
            continue
        if not listed_address(r, dirs.get(k, "")):
            out[id(r)] = ("unlisted", None)
            continue
        # BOTH LISTED TONIGHT: two documents at one path. A calendar renamed
        # from its short name to its long one shares its number's path with
        # its old row too, but the old name is no longer listed, and that is
        # the same document: held from its text, as it always was.
        others = [x for x in paths.get(_disk(r).as_posix().lower(), ()) if x is not r
                  and x.get("name") in now.get((x.get("chamber"), x.get("kind"),
                                                str(x.get("year"))), ())]
        if others:
            out[id(r)] = ("shared", others[0])
            continue
        if r.get("kind") == "journal" and journal_number(r):
            gone = [h for h in held.get((k[0], k[2], journal_number(r)), ())
                    if h.get("name") not in now.get(k, ())]
            if gone:
                out[id(r)] = ("renamed", gone[0])
    return out


def night_plan(rows, tonight, before, most):
    """What tonight may ask for, decided before anything is asked. A dict:

      ask       the rows to ask for, in the order they are asked, at most
                `most` of them
      waiting   how many more might have been asked, past the cap
      text      the rows to mark held from the text beside them, unasked
      renames   [(row, the held row of the same number)]: possible renames,
                not asked, for a person to decide
      shared    [(row, a row of the same path)]: not asked, not held from
                text, for a person to repair (held_back)
      unlisted  [(row, None)]: rows whose own address is not the one
                tonight's list gives them, not asked (held_back)
      new       rows listed tonight for the first time, which wait a night
      refused   rows a refusal is recorded against, never asked
      tried     rows asked NIGHT_TRIES times already, which a person decides
      why       "" or why nothing may be asked at all

    THE RULES (the person's plan, 26 October 2026), in the order they apply:

      eligible  wanted; named by tonight's list (`tonight`, the listing
                record installed tonight) AND by the night before's
                (`before`), so it has been listed for at least a night --
                a document can be listed before its upload is done, and the
                newest are posted under short names and renamed; no refusal
                recorded against it; and asked fewer than NIGHT_TRIES times
      held back its address not the one tonight's list gives it, or its path
                another row's (held_back, which says why): neither asked for
                nor held from its text, and named for a person
      its text  a row with its text (or its PDF) beside its path is marked
                held and never asked for: GitHub's machine holds the texts
                and no PDFs, and the laptop fetched most of these long ago.
                Applied before the cap, so a held row never takes a place
      renamed   a journal is named by the file the General Court posted it
                as, so a journal renamed is a second row, a second fetch and
                a second text every reader of journals reads twice. A
                journal with the number of a held journal of its chamber and
                year, whose own name tonight's list no longer gives, is not
                asked for; it is named for a person to decide
      order     oldest first within each list, the lists in the queue's order

    Nothing here asks or writes, so the night can say what it would ask
    without asking it (a dry run's "would ask")."""
    out = {"ask": [], "waiting": 0, "text": [], "renames": [], "shared": [], "unlisted": [],
           "new": 0, "refused": 0, "tried": 0, "why": ""}
    if not (isinstance(tonight, dict) and lists_of(tonight)):
        out["why"] = "tonight's list of calendars and journals is not on file"
        return out
    if not (isinstance(before, dict) and lists_of(before)):
        out["why"] = "the night before's list of calendars and journals is not on file"
        return out
    if tonight.get("read") == before.get("read"):
        out["why"] = ("tonight's list is the night before's, read at the same time: it was "
                      "not installed tonight")
        return out
    now, then = lists_of(tonight), lists_of(before)
    eligible = []
    for r in rows:
        if r.get("state") != "wanted":
            continue
        k = (r.get("chamber"), r.get("kind"), str(r.get("year")))
        if r.get("name") not in now.get(k, ()):
            continue
        if r.get("name") not in then.get(k, ()):
            out["new"] += 1
        elif refused_before(r.get("error")):
            out["refused"] += 1
        elif _tries(r) >= NIGHT_TRIES:
            out["tried"] += 1
        else:
            eligible.append(r)
    back = held_back(rows, tonight)
    blocks = {}
    for r in eligible:
        why, other = back.get(id(r), ("", None))
        # Before the text rule: a row whose path another shares would be
        # "held" from the other's text, and never asked for.
        if why in ("unlisted", "shared"):
            out[why].append((r, other))
            continue
        p = _disk(r)
        if p.with_suffix(".txt").exists() or p.exists():
            out["text"].append(r)
            continue
        if why == "renamed":
            out["renames"].append((r, other))
            continue
        blocks.setdefault((r.get("chamber"), r.get("kind"), str(r.get("year"))), []).append(r)
    order = [r for block in blocks.values() for r in reversed(block)]
    out["ask"], out["waiting"] = order[:max(0, most)], max(0, len(order) - max(0, most))
    return out


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
    """--night: ask for what tonight's lists name, as night_plan() allows.

    0 when it ended as it should -- everything asked for that might be, the
    cap reached, or the time allowed spent; 1 when it stopped on an answer
    that was not a whole PDF, on a second document not found, or because
    two nights' lists were not on file to ask from; 2 on a refusal,
    recorded; 3 when the lock it runs under was lost.

    THE STOP RULES. One refusal: recorded (note()), and nothing more is
    asked. The first failure that is not a 404 ends the step -- a dropped
    connection, an error page, a PDF not whole -- where the laptop's drain
    cools off and asks again. A 404 marks its document gone, as the drain
    does; a second ends the step, because 404s one after another are what a
    scan of guessed names looks like from the far end, and that is how this
    address was first blocked. And no request starts once --seconds have
    passed since the step began.

    WHAT IT WRITES. The queue, whole, to --out and nowhere else: the night
    installs it, or does not. Beside it, ASKED_NAME: each request, with the
    document's name, its bytes, its seconds, its sha256 and how it ended,
    and the rows marked held from their text, the possible renames, those
    held back for a person and the reason it stopped. Both are written
    however it ends -- and before every request as well, with that request
    and its try already in them (the review of 26 October 2026): the night
    kills this at its own limit, a kill skips `finally`, and a document whose
    answer always hangs was asked for again every night with its tries never
    counted. A PDF fetched goes to its own path, through a part file;
    nothing else is written.

    A FAILURE COUNTS AS A TRY AND WRITES NO ERROR. The Calendar page's picker
    drops a row that carries an error (calendar_documents.linkable), and a
    night's dropped connection is no reason for a reader to lose the link to
    a calendar the page lists. A refusal is written against its row, so that
    nothing asks for that document again without a person -- beginning
    REFUSED_MARK, whatever the answer was -- and a 404 too, with the row
    gone, as the drain writes it."""
    t0 = time.time()
    out = Path(a.out)
    asked_file = out.with_name(ASKED_NAME)
    rec = {"started": _utc_now(), "most": a.most, "pause": a.pause, "seconds": a.seconds,
           "requests": 0, "asked": [], "held_from_text": [], "possible_renames": [],
           "held_back": [], "new_tonight": 0, "refused_before": 0, "tried_out": 0,
           "waiting": 0, "stopped": "", "exit": 1}
    code, stopped, done, plan, asked = 0, "", False, None, 0

    def who(r):
        return {k: r.get(k) or "" for k in ("chamber", "kind", "year", "name", "path")}

    def keep():
        # The record first, then the queue: killed between the two, the
        # record names a request whose try the queue does not yet count,
        # which the night installs as it is -- never a queue that changed a
        # row its record does not name.
        part = asked_file.with_name(asked_file.name + ".part")
        part.parent.mkdir(parents=True, exist_ok=True)
        part.write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8", newline="\n")
        os.replace(part, asked_file)
        write_rows(out, rows)
    try:
        def read(p):
            try:
                return json.loads(Path(p).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return None
        plan = night_plan(rows, read(listed_file()), read(a.night), a.most)
        for r in plan["text"]:
            r["state"] = "held"
            rec["held_from_text"].append(who(r))
        rec["possible_renames"] = [dict(who(r), held=h.get("name") or "")
                                   for r, h in plan["renames"]]
        rec["held_back"] = [dict(who(r), why=why, other=(o or {}).get("name") or "")
                            for why in ("shared", "unlisted") for r, o in plan[why]]
        rec.update(new_tonight=plan["new"], refused_before=plan["refused"],
                   tried_out=plan["tried"])
        print(f"{len(plan['ask'])} to ask for, at most {a.most}, about {a.pause:g}s apart and "
              f"as long before the first; {len(plan['text'])} held from their text; "
              f"{len(plan['renames'])} possible renames; {len(rec['held_back'])} held back for "
              f"a person; {plan['new']} listed for the first time tonight, asked for from "
              "tomorrow", flush=True)
        for r, h in plan["renames"]:
            print(f"  possible rename, not asked for: {r['chamber']} {r['kind']} {r['year']} "
                  f"{r['name']} -- the held {h.get('name')} is no longer listed", flush=True)
        for r, o in plan["shared"]:
            print(f"  not asked for, its path is another's: {r['chamber']} {r['kind']} "
                  f"{r['year']} {r['name']} and {o.get('name')}, both {r.get('path')}", flush=True)
        for r, _ in plan["unlisted"]:
            print(f"  not asked for, its address is not the one tonight's list gives it: "
                  f"{r['chamber']} {r['kind']} {r['year']} {r['name']}", flush=True)
        if plan["why"]:
            # NOT A QUIET NOTHING. The night runs this only after it has
            # installed tonight's list, so a list missing here is something
            # wrong, and a step that asked nothing for it says so in its status.
            code, stopped = 1, f"nothing was asked for: {plan['why']}"
            print(f"\n{stopped[0].upper()}{stopped[1:]}.", flush=True)
        missing = 0
        for r in plan["ask"]:
            pause = a.pause * random.uniform(0.75, 1.25)
            if time.time() - t0 + pause >= a.seconds:
                stopped = f"the {a.seconds:g} seconds allowed were spent"
                break
            # A PAUSE BEFORE EVERY REQUEST, THE FIRST AS WELL: the night has
            # asked this address for its lists a moment before (the listing's
            # own rule, LISTING_PAUSE).
            time.sleep(pause)
            if time.time() - t0 >= a.seconds:
                stopped = f"the {a.seconds:g} seconds allowed were spent"
                break
            # Immediately before the request, not before the pause.
            if refusal.MARK.exists():
                code, stopped = 2, "a refusal is on file"
                break
            if not held.still():
                code, stopped = 3, "the lock this runs under is gone"
                break
            entry = dict(who(r), at=_utc_now(), bytes=0, seconds=0.0, sha256="",
                         ended="no answer: it was stopped while asking")
            rec["asked"].append(entry)
            rec["requests"] += 1
            asked += 1
            # THE TRY COUNTED BEFORE THE REQUEST, and written down: killed
            # while it waits, the night still has the try and the request.
            r["attempts"] = str(_tries(r) + 1)
            rec["stopped"] = "it was stopped while asking"
            keep()
            begun = time.time()
            blob, e, why = b"", None, ""
            try:
                blob = _get_document(r["url"])
                kind = refusal.classify(body=blob[:4000].decode("utf-8", "replace"))
                why = "the firewall's block page, served as 200" if kind else whole_pdf(blob)
                kind = kind or ("failed" if why else None)
            except Exception as err:                        # noqa: BLE001
                e = err
                kind = refusal.classify(err) or "failed"
                why = f"{type(err).__name__}: {err}"
            rec["stopped"] = ""
            entry["seconds"] = round(time.time() - begun, 1)
            entry["bytes"] = len(blob)
            if kind:
                entry["ended"] = _said(kind, e, why)
                print(f"  [{asked}] {r['name']}: {entry['ended']}", flush=True)
                if kind == "refused":
                    r["error"] = (REFUSED_MARK + why)[:180]
                    refusal.note("fetch_calendar_archive", why[:180])
                    code, stopped = 2, "the General Court refused a request"
                    print("\nRefused. Recorded, and nothing more is asked of it.\n"
                          "python3 netcheck.py says what kind of refusal it is "
                          "without making it worse.", flush=True)
                    break
                if kind == "missing":
                    r["state"], r["error"] = "gone", why[:180]
                    missing += 1
                    if missing >= 2:
                        code, stopped = 1, "a second document the list names was not found"
                        break
                    continue
                code, stopped = 1, ("a connection was dropped" if kind == "dropped"
                                    else f"a request {entry['ended']}")
                break
            path = _disk(r)
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                tmp = path.with_name(path.name + ".part")
                tmp.write_bytes(blob)
                os.replace(tmp, path)
            except OSError as err:
                entry["ended"] = f"failed: it could not be saved ({type(err).__name__})"
                code, stopped = 1, "a document fetched could not be saved"
                break
            r["state"], r["bytes"], r["error"] = "held", str(len(blob)), ""
            r["fetched"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            entry.update(ended="fetched", sha256=hashlib.sha256(blob).hexdigest())
            print(f"  [{asked}] {r['name']}: fetched, {len(blob):,} bytes, "
                  f"{entry['seconds']:g}s", flush=True)
        done = True
    finally:
        if plan is not None:
            rec["waiting"] = plan["waiting"] + len(plan["ask"]) - asked
        rec.update(ended=_utc_now(), stopped=stopped if done else (
            stopped or "it stopped on an error of its own"), exit=code if done else 1)
        write_rows(out, rows)
        part = asked_file.with_name(asked_file.name + ".part")
        part.write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8", newline="\n")
        os.replace(part, asked_file)
    got = sum(1 for x in rec["asked"] if x["ended"] == "fetched")
    print(f"\n{rec['requests']} requests, {got} fetched, {time.time() - t0:.0f}s"
          + (f"; stopped: {stopped}" if stopped else "")
          + f"; {rec['waiting']} still to ask for -> {out}", flush=True)
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
                                  f"the same, with {ASKED_NAME} beside it")
    ap.add_argument("--night", metavar="PREV_LISTED",
                    help="GitHub's night: fetch what tonight's lists and the night "
                         "before's both name, gently (take_night); PREV_LISTED is the "
                         f"night before's {LISTED_NAME}. Writes only --out, the record "
                         "beside it, and each PDF at its path")
    ap.add_argument("--most", type=int,
                    help=f"(--night) the most documents asked for, 1 to {NIGHT_MOST} "
                         "(default 1)")
    ap.add_argument("--pause", type=float,
                    help=f"(--night) seconds before every request, the first as well; at "
                         f"least {NIGHT_PAUSE_LEAST:g} (default {NIGHT_PAUSE:g}), jittered "
                         "by a quarter either way")
    ap.add_argument("--seconds", type=float,
                    help="(--night) no request starts after this many seconds, at most "
                         f"{NIGHT_SECONDS} (the default)")
    ap.add_argument("--settle", nargs="+", metavar="NAME",
                    help="mark the wanted documents of these names settled, asking nobody: a "
                         "journal the night holds back as a possible rename that a person has "
                         "found is the same journal. Kept where the drain keeps what it "
                         "fetched, which the night's list then takes")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--chamber", choices=["H", "S", "both"], default="both")
    ap.add_argument("--kind", choices=["calendar", "journal", "both"],
                    default="both")
    ap.add_argument("--from", dest="first", type=int, default=0)
    ap.add_argument("--to", dest="last", type=int, default=9999)
    ap.add_argument("--budget", type=int,
                    help="requests this run, then stop (default 150)")
    ap.add_argument("--delay", type=float,
                    help="seconds between requests (default 15). Jittered by "
                         "a quarter either way, so a run does not arrive on a "
                         "metronome.")
    a = ap.parse_args()
    # THE NIGHT'S FETCH TAKES ITS OWN ROWS AT ITS OWN PACE (26 October 2026),
    # so nothing of the drain's is accepted beside it -- a --budget 50 that
    # was silently ignored would read as obeyed -- and nothing of its own
    # without it. The drain's two defaults are set here, after that test,
    # so that the test can tell a flag given from one left out.
    nights = [f for f, v in (("--most", a.most), ("--pause", a.pause),
                             ("--seconds", a.seconds)) if v is not None]
    if a.night is None and nights:
        ap.error(f"{', '.join(nights)} belong to --night")
    if a.settle is not None and (
            a.night is not None or a.listing or a.discover or a.status or a.list or a.out
            or a.chamber != "both" or a.kind != "both" or a.first or a.last != 9999
            or a.budget is not None or a.delay is not None):
        ap.error("--settle names documents and asks nobody: it takes no other flag")
    if a.night is not None:
        if (a.listing or a.discover or a.status or a.list or a.chamber != "both"
                or a.kind != "both" or a.first or a.last != 9999
                or a.budget is not None or a.delay is not None):
            ap.error("--night asks for what two nights' lists name, at its own pace: it "
                     "takes no --listing, --discover, --status, --list, --chamber, --kind, "
                     "--from, --to, --budget or --delay")
        if not a.out:
            ap.error("--night writes the queue only to --out, and needs one")
        if Path(a.out).resolve() in {QUEUE.resolve(), fetched_file().resolve(),
                                     listed_file().resolve()}:
            ap.error("--out is a file of the queue's own: the night installs what --night "
                     "writes, and --night writes none of them")
        a.most = 1 if a.most is None else a.most
        a.pause = NIGHT_PAUSE if a.pause is None else a.pause
        a.seconds = NIGHT_SECONDS if a.seconds is None else a.seconds
        if not 1 <= a.most <= NIGHT_MOST:
            ap.error(f"--most is 1 to {NIGHT_MOST}: the night asks for no more documents "
                     "than that")
        if a.pause < NIGHT_PAUSE_LEAST:
            ap.error(f"--pause is at least {NIGHT_PAUSE_LEAST:g} seconds")
        if not 0 < a.seconds <= NIGHT_SECONDS:
            ap.error(f"--seconds is more than 0 and at most {NIGHT_SECONDS}")
    a.budget = 150 if a.budget is None else a.budget
    a.delay = 15.0 if a.delay is None else a.delay

    ROOT.mkdir(exist_ok=True)
    if a.settle is not None:
        return settle(a.settle)
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
        # GitHub's night's, and only there: on a laptop that has stood down
        # the newest documents are the night's to fetch, and one fetch of a
        # document is all the General Court should see.
        refusal.stand_down(
            "The night's fetch of the newest calendars and journals",
            "GitHub's night fetches what the newest lists name itself now (the person, "
            "26 October 2026). The drain still runs here for the years before them.")
        refusal.check("The night's fetch of the newest calendars and journals")
        with refusal.hold("the night's fetch of the newest calendars and journals") as held:
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


def settle(names):
    """--settle: each wanted document of these names marked SETTLED, asking
    nobody; 0 when every name was found, 1 otherwise.

    A PERSON'S WORD ON A POSSIBLE RENAME (the review of 26 October 2026). The
    night holds back a journal with the number of one held whose own name
    its list no longer gives, and warns of it every night, because fetched it
    is a second text every reader of journals reads twice. When a person
    finds it is a different journal, the drain here takes it. When it is the
    same journal under a new name, this says so: kept where the drain keeps
    what it fetched (save_queue) -- the laptop's file, on a laptop that has
    stood down, whose settled row the night's list then takes (laptop_wins)
    -- under the lock, so that no drain running writes over it."""
    with refusal.hold("settling documents by hand"):
        rows = load_queue()
        hit = [r for r in rows if r.get("name") in names and r.get("state") == "wanted"]
        for r in hit:
            r["state"], r["error"] = SETTLED, ""
            print(f"  settled: {r['chamber']} {r['kind']} {r['year']} {r['name']}")
        found = {r["name"] for r in hit}
        missing = [n for n in names if n not in found]
        for n in missing:
            print(f"  not settled: no wanted document is named {n!r}")
        if hit:
            save_queue(rows)
    print(f"{len(hit)} settled; the night never asks for a settled document")
    return 1 if missing else 0


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
        if list_is_the_nights() and refusal.night_documents():
            # THE NEWEST YEARS ARE THE NIGHT'S (the person, 26 October 2026)
            # -- once it fetches them. While GitHub's night fetches what the
            # newest lists name, as its own verdict says (the switch a
            # number: refusal.night_documents), this drain on a laptop that
            # has stood down leaves this year's rows, last year's and any
            # later to it: two machines asking for one document is a request
            # the General Court did not need to see. With the night's
            # switch off or in shadow, it fetches them as before.
            #
            # BUT ONLY THE ONES THE NIGHT WILL STILL ASK FOR (the review of
            # 26 October 2026). The night never asks again for a row with a
            # refusal recorded against it or NIGHT_TRIES tries, and never for
            # one its newest list no longer names -- last year's leftovers,
            # once January's two lists are one again. Those are a person's,
            # the verdict says so, and this drain, which a person starts, is
            # the person's way to fetch them; left to the night as well, they
            # would have been fetched by nobody.
            first = today().year - 1
            try:
                rec = json.loads(listed_file().read_text(encoding="utf-8"))
            except (OSError, ValueError):
                rec = None
            lists = lists_of(rec)
            back = held_back(rows, rec) if lists else {}
            newest = [r for r in todo
                      if str(r.get("year") or "").isdigit() and int(r["year"]) >= first]
            theirs = {id(r) for r in newest if nights_to_ask(r, lists, back)}
            if theirs:
                todo = [r for r in todo if id(r) not in theirs]
                # AND THIS MACHINE'S OWN RECORD OF THEM GOES (the review of 26
                # October 2026): left to the night, a row is the night's to
                # record, and an older line of this machine's laid over it
                # would tell the night's list it was never tried.
                night = {_key(x): x for x in read_rows(QUEUE)}
                for r in newest:
                    if id(r) in theirs and _key(r) in night:
                        for f in DRAIN_FIELDS:
                            r[f] = night[_key(r)].get(f) or ""
                print(f"{len(theirs):,} wanted of {first} and later are left to GitHub's "
                      "night, which fetches what the newest lists name: this machine "
                      "drains the years before them")
            if len(newest) > len(theirs):
                print(f"{len(newest) - len(theirs):,} wanted of {first} and later the night "
                      "will not ask for -- a refusal recorded against it, "
                      f"{NIGHT_TRIES} tries, no longer on its list, or held back for a "
                      "person (a possible rename, a path another shares, an address its "
                      "list does not give) -- are a person's, and this drain takes them")
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
                # A refusal in the one word the night reads for one
                # (REFUSED_MARK), whatever the answer said.
                r["error"] = ((REFUSED_MARK if kind == "refused" else "") + why)[:180]
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
