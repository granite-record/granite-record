#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.44
"""
Write RSS feeds so people can follow bills without a login.

    python3 src/pages/build_feeds.py --site site --base https://graniterecord.org

Following a bill normally needs an account, a server and an email list. RSS
needs none of that: the reader does the polling, nobody has to store an address,
and there is no list to leak. On a static site it costs a few megabytes of XML.

Five kinds:

    /feed/all.xml                    every recorded action, newest first
    /feed/hearings.xml               proceedings scheduled in the next month
    /feed/bill/2026/hb1442.xml       one bill's whole history
    /feed/committee/H05.xml          one committee's sitting days, keyed as its page is
    /feed/topic/<name>.xml           everything under one subject
    /feed/legislator/<id>.xml        one member's votes and sponsorships

Every link in every feed is the address the host serves -- /bill/2026/hb1442,
not hb1442.html, which answers with a redirect -- and a feed this run did not
write is removed, because a feed nothing links and nothing updates is a file
on a deployment with a ceiling, and a subscriber to it waits for nothing.

The hearings feed is the one that can change what somebody does. A person who
learns on Tuesday that a hearing is on Thursday can turn up and testify; the
same person reading about it afterwards cannot.

AND WHAT THE EMAIL SENDER READS (7 October 2026). The same items, record by
record, go to follow_changes.py as each feed is written, and it writes
/changes/current.json and one file a night under /changes/, deciding what is
new by the first-seen ledger (archive/first-seen.json, carried in the night's
state; --ledger and --ledger-out name it). follow_changes.py says how.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import build_date
import build_pages as BP
import build_rsa as BR
import components as C
import follow_changes as FC
import plain_action as PA
import json
import proceedings as P
import re
import shell as S
import site_read as SR
from collections import Counter
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from xml.sax.saxutils import escape

# One moment for the whole build: the day it decides "past" and "to come" by,
# and the changes files' night and their "built" (follow_changes), which must
# be the same day.
NOW = build_date.utcnow()
TODAY = NOW.strftime("%Y-%m-%d")
BUILT = FC.stamp(NOW)

# The first day a reader could have been following a bill and had it end under
# them: nobody was subscribed by RSS before it. A bill that concluded before
# that date can have had no subscriber, so it is owed no closing item and keeps
# no feed; one that concludes on or after it gets both. See the _closing gate
# below.
#
# This is a date and not a flag because it has to mean the same thing on every
# machine and in a fresh clone. Move it only if the premise changes.
FOLLOW_FROM = "2026-09-17"

# How a vote is written. Anything not listed is passed through as the record
# has it rather than translated into a word it did not use.
VOTE_WORD = {"Yea": "yes", "Nay": "no"}

# A BALLOT IN THE CHANGES FILES' WORDS (17 October 2026, the language sweep:
# an email read "voted Not Voting/Excused"). The contract's ballot is "yes",
# "no", "not voting" or "excused", in at most twenty characters, and the roll
# call's "Not Voting/Not Excused" is twenty-two, so it reached the email cut
# to "Not Voting/Not Exc…". The email says each in the site's own words
# (mail.js ballotWords, from app.js's names for them).
BALLOT_WORD = {"Yea": "yes", "Nay": "no", "Not Voting/Excused": "excused",
               "Not Voting/Not Excused": "not voting", "Presiding": "presiding"}


def ballot_word(v):
    """A member's ballot as the changes files carry it: the contract's word,
    or the record's own where it is none of these."""
    return BALLOT_WORD.get(v, v or "")


# HOW A BILL ENDED, IN THE SITE'S WORDS FOR IT (17 October 2026, the language
# sweep). The closing item and the email's ending line put the index's kind
# into a sentence, so every law "was signed into law" -- one that became law
# unsigned or over a veto too -- and every bill killed, tabled to death or
# otherwise done "has finished its course". The index's status is what the
# bill's page, its rail and its search row already say ("Became law
# unsigned", "Veto overridden, became law", "Killed"), and the ending says
# the same. A row with no status falls back to its kind, in words that claim
# no more than the kind does.
ENDED_KIND = {"law": "Became law", "veto": "Vetoed", "adopted": "Adopted",
              "study": "Referred for interim study"}


def ending_words(b):
    """ "HB 1442 — Became law unsigned." from a bill's index row."""
    said = str(b.get("status") or "").strip().rstrip(".")
    said = said or ENDED_KIND.get(str(b.get("kind") or "").lower(), "Concluded")
    return f"{b['n']} — {said[:1].upper()}{said[1:]}."


# WHAT KIND OF MEETING A COMMITTEE'S DAY WAS (the person, 17 October 2026:
# "The committee page didn't list what kind of session the labor committee
# was having, just the days"). A day's feed item is the committee and the
# date, and the email shows the date beside it already; this is what the email
# prints instead, from the day's own items, each bill under the kind of meeting
# the record names for it, in the site's words for the kind: "Executive session
# on HB 1767-FN and SB 416; full committee work session on HB 303-FN".
def sitting_words(session, most=6):
    kinds = C.WORDBOOK["meeting_kinds"]["kinds"]
    by_kind = {}
    for i in session.get("items") or []:
        k = " ".join(str(i.get("kind") or "").lower().split())
        n = str(i.get("n") or i.get("bill") or "").strip()
        if not k or not n:
            continue
        name = (kinds.get(k) or [k])[0].lower()
        if n not in by_kind.setdefault(name, []):
            by_kind[name].append(n)
    parts = []
    for name, bills in by_kind.items():
        if len(bills) > most:
            bills = bills[:most - 1] + [f"{len(bills) - most + 1} more"]
        listed = bills[0] if len(bills) == 1 else ", ".join(bills[:-1]) + " and " + bills[-1]
        parts.append(f"{name} on {listed}")
    out = "; ".join(parts) or "the committee met"
    return out[:1].upper() + out[1:]

# The body letter in a roll call key, spelled out. A ballot the clerk filed
# under no bill has nothing else to name it by.
CHAMBER = {"H": "House", "S": "Senate"}

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def rfc822(d):
    """RSS wants RFC 822 dates. Readers use these to order and de-duplicate."""
    try:
        dt = datetime.strptime(d[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        dt = build_date.utcnow()
    return (f"{DAYS[dt.weekday()]}, {dt.day:02d} {MONTHS[dt.month - 1]} "
            f"{dt.year} {dt.hour:02d}:{dt.minute:02d}:00 +0000")


def iso_day(d):
    """'8/19/2026' or '2026-08-19' -> '2026-08-19'; '' when it is neither.

    A member file writes a vote's date as the roll call export does, M/D/YYYY,
    and everything a vote's date is used for below -- the term its bill is
    found in, the order items sort in, the pubDate a reader sees -- reads
    YYYY-MM-DD. Every vote in every legislator feed once carried the build
    time as its date, sorted 9/4 above 8/19 and 12/2 below both, and linked
    the bills page for any bill number used in more than one term.
    """
    s = str(d or "").strip()
    for fmt, n in (("%Y-%m-%d", 10), ("%m/%d/%Y", None)):
        try:
            return datetime.strptime(s[:n] if n else s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""


def feed_events(d):
    """The dated rows of a bill's docket list that a feed tells.

    NOT A ROW THAT CALLS A MEETING OFF (7 October 2026). The bill's page lists
    it, with a note saying it is a cancellation (build_site_v2.called_off),
    and an item cannot carry the note: its line, the clerk's "==CANCELLED=="
    stripped as every line's mark is, reads as a notice of the very meeting
    it cancels. So the feeds tell what they told before the page listed it."""
    return [e for e in (d.get("events") or []) if e.get("date") and not e.get("called_off")]


def next_lines(d):
    """{id(event): the docket line after it} for one bill's record, in the
    order its page lists them, which plain_action reads a line with: an
    "Introduced and Adopted" line on a bill is its introduction only where
    "Ought to Pass" follows it (plain_action._introduced, 16 October 2026).
    A feed reads its events newest first, so the order is the record's."""
    evs = d.get("events") or []
    return {id(x): y.get("text") or "" for x, y in zip(evs, evs[1:])}


def filed_date(d):
    """The day a bill's sponsorship is dated in its sponsors' feeds: the
    oldest dated docket event, and for a bill with no docket, the Introduced
    stop of its rail.

    A bill whose record is the House Journal's (build_site_v2.journal_story)
    has no docket event, and an empty date is today's to rfc822 -- so every
    sponsor's feed carried it as new, dated afresh every night."""
    dated = sorted(e["date"] for e in feed_events(d))
    if dated:
        return dated[0]
    return next((s.get("date") or "" for s in
                 ((d.get("journey") or {}).get("rail") or [])
                 if s.get("stop") == "Introduced"), "")


def chamber_of(k):
    """'2026-H-305' -> 'House'; '' where the key is not that shape.

    A member file writes each ballot's roll call as year-body-number, so the
    chamber that took the vote is already in hand for the roll calls the clerk
    filed under no bill at all -- which is the only thing left to name them by.
    """
    p = str(k or "").split("-")
    return CHAMBER.get(p[1].upper(), "") if len(p) == 3 else ""


def vote_guid(mid, v, q):
    """One member's ballot in one roll call, named so no two share an id.

    THE ROLL CALL IS PART OF THE IDENTITY. This was the member, the bill, the
    day and the first thirty characters of the question, and a chamber takes a
    bill up twice in a day under the same words all the time. The House voted
    on overriding the veto of HB 396 twice on 19 August 2026 -- 2026-H-305 at
    11:07 and 2026-H-318 at 14:00, both questioned "Veto Override" -- so both
    ballots carried one guid, and a reader's feed reader showed the first and
    dropped the second without a word. That is one hidden ballot in every one
    of the 382 sitting House members' feeds; in 26 of them the two ballots
    disagree, so the feed had the member voting yes and no on the same bill on
    the same day and showed only one of those.

    The shape changes, so every subscriber is shown their member's last sixty
    votes once more. That is the one-time price of the ballots that were never
    shown at all. A file carrying no key keeps the old shape, where it is
    still the best available.
    """
    k = str(v.get("k") or "").strip().strip("-").strip()
    if k:
        return f"vote:{mid}:{k}"
    return f"vote:{mid}:{v.get('b')}:{v.get('d')}:{q[:30]}"


def clip(s, n=88):
    """Cut a title at a word boundary.

    A hard slice put "...without the signatur" in the feed, which is how the
    item reads in every reader that shows titles only.
    """
    s = " ".join((s or "").split())
    if len(s) <= n:
        return s
    cut = s[:n]
    sp = cut.rfind(" ")
    return (cut[:sp] if sp > n * 0.6 else cut).rstrip(" ,;:-\u2013") + "\u2026"


def slug(s):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", (s or "").lower())).strip("-")


# A TOPIC RENAMED KEEPS ITS FEED'S ADDRESS (17 October 2026): two topics took a
# reader's words (build_site_v2.TOPIC_WORDS), and their feeds and follow keys
# stay where a reader already subscribed to them.
TOPIC_ADDRESS = {"Crimes, Criminal Procedure and Corrections": slug("Crimes, Crim.Proc. & Corr."),
                 "Constitutional Amendments": slug("CACR")}


def topic_slug(name):
    return TOPIC_ADDRESS.get(name) or slug(name)


def long_date(d):
    """2026-02-12 -> February 12, 2026, the way a feed title reads aloud:
    shell.date_words, month first like every date the site writes."""
    return S.date_words(d, "full")


def prune(root, keep, allow, fall=0.25):
    """Remove feeds under root this run did not write. (removed, note).

    A large fall is refused without --allow-prune: a run that wrote almost
    nothing -- an empty index, a failed read of the pages -- would otherwise
    unpublish every feed a reader subscribes to, and look like housekeeping.
    """
    if not root.is_dir():
        return 0, ""
    keep = {p.resolve() for p in keep}
    have = sorted(root.rglob("*.xml"))
    stale = [p for p in have if p.resolve() not in keep]
    if not stale:
        return 0, ""
    if len(stale) > fall * len(have) and not allow:
        return 0, (f"  LEFT {len(stale):,} of {len(have):,} feeds in {root.name}/ that this "
                   f"run did not write: more than {fall:.0%} is the shape of a run that "
                   "failed, not of housekeeping. --allow-prune once, if it is intended: "
                   "build_all.py passes it on the nightly's New term run.")
    for p in stale:
        p.unlink()
    for d in sorted((p for p in root.rglob("*") if p.is_dir()), reverse=True):
        if not any(d.iterdir()):
            d.rmdir()
    return len(stale), ""


# Feeds this run wrote that carry two items under one guid, and how many items
# each loses to that. Filled by feed(), printed at the end of main().
COLLIDED = Counter()


def feed(title, desc, link, self_link, items, base):
    """items: (title, link, description, date, guid)"""
    # A READER KEEPS ONE ITEM PER GUID, and two items sharing one is not an
    # error anywhere: the XML is valid, the build exits zero, and the
    # subscriber simply never sees the second. That is how every one of the
    # 382 sitting House members' feeds hid a ballot for months. Nothing was
    # going to notice it except a count, so this is the count.
    seen = set()
    for i in items:
        if i[4] in seen:
            COLLIDED[self_link] += 1
        seen.add(i[4])
    body = ""
    for t, l, d, dt, g in items:
        body += (f"<item><title>{escape(t)}</title>"
                 f"<link>{escape(l)}</link>"
                 f"<guid isPermaLink=\"false\">{escape(g)}</guid>"
                 f"<pubDate>{rfc822(dt)}</pubDate>"
                 f"<description>{escape(d)}</description></item>\n")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n<channel>\n'
            f"<title>{escape(title)}</title>\n"
            f"<link>{escape(link)}</link>\n"
            f"<description>{escape(desc)}</description>\n"
            "<language>en-us</language>\n"
            f"<lastBuildDate>{rfc822(build_date.utcnow().isoformat())}</lastBuildDate>\n"
            f'<atom:link href="{escape(self_link)}" rel="self" '
            'type="application/rss+xml"/>\n'
            f"{body}</channel>\n</rss>\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    ap.add_argument("--base", default="https://graniterecord.org")
    ap.add_argument("--per-feed", type=int, default=60)
    ap.add_argument("--allow-prune", action="store_true",
                    help="remove stale feeds even when more than a quarter of a folder")
    ap.add_argument("--ledger", default=str(FC.LEDGER),
                    help="the first-seen ledger the last accepted night left")
    ap.add_argument("--ledger-out", default=str(FC.CANDIDATE),
                    help="where this build leaves its own, for nightly.py to keep or not")
    a = ap.parse_args()
    site, base = Path(a.site), a.base.rstrip("/")
    # THE CHANGES FILES' SIDE OF EVERY FEED (follow_changes.py). Each record a
    # reader may follow tonight, under its key, with its feed's own items;
    # the ledger the last accepted night left; and the records it listed,
    # whose items are wanted too: one that leaves tonight takes its last
    # items with its ending.
    led, led_why = FC.load(a.ledger, TODAY)
    want = FC.wanted(led, TODAY)
    followable, lists, upcoming, hints = {}, {}, {}, {}
    fc_items = {}                       # guid -> its item, for every bill row's

    def path_of(url):
        """A feed's link as the path on the site the changes files carry."""
        return url[len(base):] or "/" if url.startswith(base) else ""

    def fc_list(feed_items, *pools):
        """A feed's items, in its order, as follow_changes items: each found
        by its guid in the first of `pools` that has it, and once. Two items
        of one feed under one guid (COLLIDED, below) are one to a feed reader,
        and one to the sender, which refuses an item twice in a night."""
        out, had = [], set()
        for t in feed_items:
            it = next((p[t[4]] for p in pools if t[4] in p), None)
            if it and it["guid"] not in had:
                had.add(it["guid"])
                out.append(it)
        return out
    # Every bill's row, from the term files the pages read (site_read).
    idx = SR.bill_index_or_stop(site, "build_feeds.py")
    # Keyed on (term, bill), because a bill number is unique within a term and
    # not across terms. build_feeds had no notion of a term at all, and it is
    # 2,233 of the site's 8,017 files.
    by_id = {((b.get("term") or ""), b["id"]): b for b in idx}
    by_number = {}
    for b in idx:
        by_number.setdefault(b["id"], []).append(b)
    ambiguous = [0]

    def find(bill, date=""):
        """A bill row, by number and the term its date falls in.

        Where the caller has a date -- an upcoming hearing, a recorded vote --
        the term follows from it. Where it does not, a number that exists in
        exactly one term still resolves; one that exists in several is
        ambiguous, and is counted rather than guessed at.
        """
        bill = (bill or "").upper()
        if not bill:
            return None
        if date:
            hit = by_id.get((P.term_on(date), bill))
            if hit:
                return hit
        cands = by_number.get(bill, [])
        if len(cands) == 1:
            return cands[0]
        if len(cands) > 1:
            ambiguous[0] += 1
        return None

    fd = site / "feed"
    (fd / "bill").mkdir(parents=True, exist_ok=True)
    (fd / "committee").mkdir(parents=True, exist_ok=True)
    (fd / "topic").mkdir(parents=True, exist_ok=True)

    # The address the host serves. A feed's links ended in .html, which the host
    # answers with a 308 to the address without it -- every click from every
    # reader a redirect, and a guid-less reader could treat the two as two items.
    def bill_url(b):
        return base + S.canon(f"/bill/{b.get('year','')}/{b['id'].lower()}.html")

    bills_page = base + S.canon("/bills.html")
    written = []

    all_items, by_topic, nbill = [], {}, 0
    bill_items, topics_now = {}, {}
    # THE LAWS (11 October 2026): every chapter build_rsa listed, and which
    # chapters each of the sitting term's bills says it changes (rsa.py's
    # rsa_citations.json). Neither is there on a build without the statute
    # table, and then no law is followable.
    law_items = {}
    try:
        law_names = json.loads((site / "laws" / "chapters.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        law_names = {}
    try:
        cited = json.loads(Path("rsa_citations.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cited = {}

    # How a concluded bill's closing feed item names its ending: ending_words,
    # the index's own status, which is what the bill's page says.
    skipped_closed = retired = skipped_concluded = 0
    noyear = []
    sponsored = {}
    # Each bill's record, read from its page. It used to be opened from
    # site/bills/<year>/<ID>.json, which since the records moved inside the
    # pages exists only for the few too large to inline -- so for two days this
    # wrote 173 feeds and skipped every other bill without a word, while 5,436
    # bill pages linked a feed that was never written.
    recs = SR.by_bill(site, fields=("events", "sponsors", "next_step", "journey"))
    # A FEED IS FOR A BILL THAT CAN STILL DO SOMETHING. One per bill of a
    # closed term is a file that will never gain an item: nobody subscribes
    # to 1993. Writing them for every archived bill once the 1989-2016
    # histories arrived would have put 22,840 more files on the deployment,
    # against the 100,000 Cloudflare Pages allows -- run check_site.py for
    # what is actually on it, because this comment carried a count that no
    # command produced. What decides this is the 22,840, not the total -- and it is
    # the per-bill feed only. The all-bills, committee and topic feeds are
    # unchanged, and every archived bill's history is on its page.
    current = max((b.get("term") or "" for b in idx), default="")
    changes_of = {bid.upper(): sorted({str(c).split(":")[0].upper() for c in (r or {}).get("changes") or []})
                  for bid, r in ((cited.get("bills") or {}).get(current) or {}).items()}
    # UNDER THE MEMBER THE BILL'S PAGE LINKS, where it links one. The record's
    # own id is an employee number or nothing on most sponsor records, and a
    # sitting member's feed filed under it missed the sponsorships their page
    # lists -- build_site_v2.bill_sponsor_list files them the same way.
    # THE SITTING TERM'S FLOOR ROLL CALLS, COUNTED (22 October 2026), for the
    # email's vote bar: each bill's roll calls as follow_changes.rollcall_detail
    # gives them -- counts, no names -- read from the term's own pages only,
    # since the walk above keeps no ballots. A docket line finds its roll call
    # by its day and its count (FC.FLOOR_COUNT), and a line that matches none,
    # or two that disagree, carries none.
    rc_of = {}
    # EVERY MEETING STILL TO COME, FROM THE BILL'S OWN RECORD (26 October
    # 2026), for current.json's upcoming: the rows the Testify button reads,
    # by its rules (follow_changes.bill_upcoming), so that an email counts
    # the hearings the site counts -- each of them, not home.json's first
    # eighty of the fortnight -- with the hearings on a proposed amendment,
    # and says them as the button's pane does. Read in this same walk.
    ahead_of, walked = {}, set()
    for year, bid, rec in (SR.records(site, years=current.split("-")) if current else ()):
        walked.add(bid)
        got = [((r.get("date") or "")[:10], r.get("yeas"), r.get("nays"), FC.rollcall_detail(r))
               for r in rec.get("rollcalls") or []
               if isinstance(r, dict) and (r.get("vote_kind") or "RC") == "RC"]
        got = [g for g in got if g[3]]
        if got:
            rc_of[(year, bid)] = got
        if (rec.get("term") or current) == current:
            ahead = FC.bill_upcoming(rec, kind=(by_id.get((current, bid)) or {}).get("kind"),
                                     today=TODAY, place=PA.place)
            if ahead:
                ahead_of[(year, bid)] = ahead

    def rollcall_for(year_bid, day, text):
        m = FC.FLOOR_COUNT.search(str(text or ""))
        if not m:
            return None
        hits = [x for dt, y, n, x in rc_of.get(year_bid, ())
                if dt == day and (y, n) == (int(m.group(1)), int(m.group(2)))]
        # Two roll calls of one day and one count (a reconsideration, a pair
        # of amendments) draw the same bar where they agree in every count
        # and outcome; where they do not, the line carries none.
        return hits[0] if hits and all(h == hits[0] for h in hits) else None

    lp0 = site / "legislators.json"
    by_slug = ({m["slug"]: str(m.get("id")) for m in
                json.loads(lp0.read_text(encoding="utf-8")) if m.get("slug")}
               if lp0.exists() else {})
    for b in idx:
        # Under the filing year, like the feed's own output path below.
        d = recs.get((str(b.get("year") or ""), b["id"].upper()))
        if d is None:
            continue
        url = bill_url(b)
        then = next_lines(d)
        events = feed_events(d)
        events.sort(key=lambda e: e["date"], reverse=True)
        # A BILL WITH NO DOCKET is dated by its introduction: filed_date.
        filed = filed_date(d)
        seen = set()
        for sp in (d.get("sponsors") or []):
            mid = by_slug.get(sp.get("slug")) or str(sp.get("member_id") or "")
            if mid and mid not in seen:
                seen.add(mid)
                sponsored.setdefault(mid, []).append(
                    (b, url, bool(sp.get("prime")), filed))

        items = []
        # The changes files want these for the sitting term's bills, whose
        # items reach the bill, topic and committee records, and for a bill
        # the ledger listed, which may be leaving tonight.
        key = f"bill:{b.get('year')}/{b['id'].upper()}"
        on_record = (b.get("term") or "") == current or key in want
        for e in events:
            items.append((
                f"{b['n']} \u2014 {clip(e.get('text',''))}",
                url,
                f"{b.get('title','')}\n\n{e.get('text','')}\n\n"
                # The bill's status as its page says it, not the General
                # Court's two fields run together ("House: INTERIM STUDY ·
                # Senate: PASSED/ADOPTED WITH AMENDMENT"), 17 October 2026.
                f"Status: {b.get('status') or d.get('next_step','')}",
                e["date"],
                f"{b.get('term','')}:{b['id']}:{e['date']}:"
                f"{slug(e.get('text',''))[:40]}"))
            if on_record:
                t = items[-1]
                ek = FC.event_kind(e.get("text"), t[3][:10], TODAY)
                # A line that sets a meeting goes to the email as the meeting
                # too, which the email says in its own words (17 October
                # 2026: "emails can use plain words for hearing entries"). The
                # feed item above keeps the clerk's line.
                it = FC.item(t[4], t[3][:10], ek,
                             t[0], path_of(url), b.get("term") or "",
                             study=FC.STUDY_REPORT.match(str(e.get("text") or "").strip()) is not None,
                             recommends=FC.study_says(e.get("text")),
                             milestone=FC.milestone(ek, e.get("text")),
                             plain=(lambda w: f"{b['n']} \u2014 {w}" if w else "")(
                                 PA.plain(e.get("text") or "", b["id"], next_line=then.get(id(e), ""))),
                             meeting=PA.meeting(e.get("text")),
                             rollcall=(rollcall_for((str(b.get("year") or ""), b["id"].upper()),
                                                    t[3][:10], e.get("text"))
                                       if ek == "vote" else None))
                if it:
                    fc_items[t[4]] = it

        # A BILL THAT HAS FINISHED GETS ONE LAST ITEM, AND THEN NOTHING: one
        # final update on how it ended, and the feed retires after that.
        #
        # Before this, a bill concluding in the sitting term was skipped
        # outright -- so 107 feeds sat in site/ whose newest item was the last
        # procedural step. 2025 HB156's was "House Non-Concurs with Senate
        # Amendment", and somebody following it was never told the bill had
        # finished, or how. Deleting the file instead would answer their reader
        # with a 404, which tells them less still.
        #
        # The closing item's guid carries no date and its date is the last
        # event's, so every rebuild produces the SAME closing item rather than
        # a fresh one each night -- which is what retiring a feed means.
        # ONLY WHERE SOMEBODY COULD HAVE BEEN SUBSCRIBED. A closing item is
        # owed to a reader who was following the bill when it ended; a bill
        # that concluded before anyone could follow anything is owed nothing,
        # and keeping its feed is 2,000 files bought for no reader.
        #
        # Nobody was following bills by RSS before FOLLOW_FROM, so the rule
        # starts from that day rather than reaching back over the term.
        #
        # The gate is the bill's OWN concluding date, not the state of site/.
        # Scoping it to feeds already on disk was the first attempt and was
        # wrong for a subtler reason than the file count: it would have made
        # the build depend on what a previous run left behind, so two runs from
        # identical data could differ and a fresh clone would produce a
        # different site. A date in the record is the same on every machine.
        _closing = (items and (b.get("term") or "") == current
                    and not S.still_moving(b, current)
                    and events[0]["date"][:10] >= FOLLOW_FROM)
        if _closing:
            _end = ending_words(b)
            items.insert(0, (
                f"{_end} This feed is now closed.",
                url,
                f"{b.get('title','')}\n\n{_end} No further updates "
                "will be posted here: a bill that has concluded has "
                "nothing more to report. Its full history stays on its page.",
                events[0]["date"],
                f"{b.get('term','')}:{b['id']}:closed:{(b.get('kind') or '')}"))
            retired += 1
            # The same ending, in the changes files' words: the closing item's
            # guid, and the index's own word for how.
            hints[key] = {"closing": {
                "how": (b.get("kind") or "").lower() if FC.HOW.match((b.get("kind") or "").lower())
                else "done",
                "summary": _end, "date": events[0]["date"][:10],
                "guid": items[0][4]}}
        elif key in want:
            hints[key] = {"kind": (b.get("kind") or "").lower(), "term": b.get("term") or "",
                          "said": ending_words(b)}
        if on_record and S.still_moving(b, current) and str(b.get("year") or "").strip():
            followable[key] = {"label": FC.line(b["n"], 120),
                               "title": FC.line(b.get("title") or "", 300),
                               "now": FC.line(b.get("chip") or "", 120),
                               "url": path_of(url)}
            for f in ("title", "now"):
                if not followable[key][f]:
                    del followable[key][f]
        if on_record and (key in followable or key in want):
            lists[key] = fc_list(items[:a.per_feed], fc_items)
        # A LAW'S FOLLOWERS hear what the sitting term's bills that would
        # change it do (CHANGES_FORMAT.md, law), under the bills' own guids.
        if (b.get("term") or "") == current and key in followable:
            for ch in changes_of.get(b["id"].upper(), ()):
                law_items.setdefault(ch, []).extend(items[:a.per_feed])

        if items and (b.get("term") or "") != current:
            skipped_closed += 1
        elif items and not S.still_moving(b, current) and not _closing:
            # Concluded, and concluded before anyone could have been following
            # it: no feed at all. Only a bill still moving can be followed, and
            # a bill that ended before FOLLOW_FROM has no subscriber to tell.
            # Restoring this was the whole point of the gate above -- without
            # it every bill of the term kept a feed, which is 2,000 files for
            # no reader.
            skipped_concluded += 1
        elif items and not str(b.get("year") or "").strip():
            # Without a year the path collapses to feed/bill/<id>.xml, where
            # the next term's bill of the same number lands on top of it.
            noyear.append(b["id"])
        elif items:
            out = fd / "bill" / str(b.get("year"))
            out.mkdir(parents=True, exist_ok=True)
            self_l = f"{base}/feed/bill/{b.get('year')}/{b['id'].lower()}.xml"
            written.append(out / f"{b['id'].lower()}.xml")
            (out / f"{b['id'].lower()}.xml").write_text(
                feed(f"{b['n']} — Granite Record",
                     b.get("title", "") or f"Actions on {b['n']}",
                     url, self_l, items[:a.per_feed], base), encoding="utf-8")
            nbill += 1

        # Scheduled proceedings are dated in the FUTURE, deliberately, so the
        # hearings feed reaches somebody in time to attend. An aggregate feed
        # is the record of what has happened, and readers treat a future date
        # as a reason to hide an item or sort it to the top -- either of which
        # buries the newest real activity. Future dates belong in one feed
        # only.
        #
        # That rule was written here and then applied to all_items alone,
        # while the two lines under it went on reading the unfiltered list.
        # 52 events of the sitting term are dated after today across 45 bills
        # -- "Full Committee Work Session: 09/29/2026 10:00 am GP 228" on
        # HB100, and forty-four like it, every one of them the newest thing
        # its bill has done -- so all 52 reached the 23 topic feeds those
        # bills fall under, at the top, above what has actually happened.
        # One list, filtered once, and every reader of it gets the same rule.
        past = [i for i in items if i[3] <= TODAY]
        all_items += past[:4]
        # The newest three per bill, for a committee with bills and no sitting
        # day on record, whose feed is its bills' actions instead.
        bill_items[(str(b.get("year") or ""), b["id"].upper())] = past[:3]
        if b.get("topic"):
            by_topic.setdefault(b["topic"], []).extend(past[:3])
            # A topic is followed for the sitting term only, and carries that
            # term's items alone (CHANGES_FORMAT.md): the same three a bill.
            if (b.get("term") or "") == current:
                topics_now.setdefault(b["topic"], []).extend(past[:3])

    def newest(items):
        return sorted(items, key=lambda x: x[3], reverse=True)[:a.per_feed]

    for name, its in topics_now.items():
        key = f"topic:{topic_slug(name)}"
        followable[key] = {"label": FC.line(name, 120),
                           "url": "/bills?topic=" + quote(name, safe="")}
        lists[key] = fc_list(newest(its), fc_items)

    nlaw = 0
    for ch, info in sorted(law_names.items()):
        key = f"law:{ch}"
        if not FC.key_ok(key) or (isinstance(info, list) and len(info) > 3 and info[3]):
            continue                    # a repealed chapter is not followed
        name = info[0] if isinstance(info, list) and info else ""
        followable[key] = {"label": FC.line(f"RSA {ch}" + (f": {name}" if name else ""), 120),
                           # RSA 404's with its slash (build_rsa.chapter_path,
                           # the sitemap audit, 16 October 2026).
                           "url": BR.chapter_path(ch)}
        if law_items.get(ch):
            lists[key] = fc_list(newest(law_items[ch]), fc_items)
        nlaw += 1
    if law_names:
        print(f"  {nlaw:,} laws can be followed; {len(law_items):,} have a bill of "
              f"{current} that would change them")

    (fd / "all.xml").write_text(
        feed("Granite Record — all activity",
             "Every recorded action on New Hampshire legislation, newest "
             "first. Hearings and sessions still to come are in the hearings feed.",
             f"{base}/", f"{base}/feed/all.xml", newest(all_items), base),
        encoding="utf-8")

    # ---- one feed per committee, keyed the way its page is -----------------
    # These were keyed on a committee NAME as the search index spells it, and
    # thirty-eight years of abbreviations spell one committee many ways: six
    # feeds for the House's children and juvenile justice committee alone, 274
    # feeds for 53 committees, none of them linked from anywhere -- and no
    # stable address for a Follow button to name. The page is /committee/H05;
    # the feed is /feed/committee/H05.xml, written from the committee's own
    # record of its sitting days, each with the sentence the page shows for it.
    # A committee with bills and no sitting day on record gets its bills'
    # newest actions instead.
    ncmte = 0
    # (chamber, lower-cased name) -> code, for filing a hearing under the
    # committee that will sit: the same key build_pages.committee_codes
    # gives a calendar card, read here off the records already open.
    cmte_code = {}
    for cj in sorted((site / "committee").glob("*.json")) if (site / "committee").is_dir() else []:
        try:
            c = json.loads(cj.read_text(encoding="utf-8"))
        except ValueError:
            continue
        code = str(c.get("code") or cj.stem)
        if not S.committee_followable(c):
            if f"committee:{code}" in want:
                hints[f"committee:{code}"] = {"archived": bool(c.get("archived"))}
            continue
        chamber = {"H": "House", "S": "Senate"}.get(code[:1].upper(), "")
        who = f"{chamber} {c.get('name') or code}".strip()
        page = base + S.canon(f"/committee/{code}.html")
        if c.get("name"):
            cmte_code[(code[:1].upper(), c["name"].strip().lower())] = code
        items, mine = [], {}
        for s in c.get("sessions") or []:
            d = s.get("date") or ""
            if not d or d > TODAY:
                continue
            taken = [i.get("n") or i.get("bill") or "" for i in (s.get("items") or [])]
            items.append((
                f"{who} — {long_date(d)}", page,
                (s.get("narrative") or f"{who} met on {long_date(d)}.")
                + (f"\n\nBills taken up: {', '.join(t for t in taken[:15] if t)}"
                   + (f" and {len(taken) - 15} more" if len(taken) > 15 else "")
                   if taken else ""),
                d, f"committee:{code}:{d}"))
            it = FC.item(items[-1][4], d[:10], "sitting", items[-1][0], path_of(page),
                         s.get("term") or P.term_on(d), plain=sitting_words(s))
            if it:
                mine[it["guid"]] = it
        if not items:
            for rows in (c.get("bills") or {}).values():
                for r in rows or []:
                    items += bill_items.get((str(r.get("year") or ""), str(r.get("id") or "").upper()), [])
        key = f"committee:{code}"
        # NAMED AS THE SEARCH NAMES IT, WITH ITS CHAMBER BESIDE (16 October
        # 2026). The emails and the manage page call a committee by this label,
        # and the manage page sets committees beside the topics, so it reads
        # "House Housing Committee" and is not taken for the subject
        # (follow_changes.committee_label). The chamber apart is what the
        # manage page's list of committees is grouped by.
        followable[key] = {"label": FC.line(FC.committee_label(c.get("name") or code, chamber), 120),
                           "url": path_of(page)}
        if chamber:
            followable[key]["chamber"] = chamber
        lists[key] = fc_list(newest(items), mine, fc_items)
        # Written empty rather than skipped: the committee's page names this
        # feed on the same test, and an address a page offers must answer.
        out = fd / "committee" / f"{code}.xml"
        written.append(out)
        out.write_text(
            feed(f"{who} committee — Granite Record",
                 f"The days the {who} committee met, and what it did with each bill.",
                 page, f"{base}/feed/committee/{code}.xml", newest(items), base),
            encoding="utf-8")
        ncmte += 1

    for name, items in by_topic.items():
        out = fd / "topic" / f"{topic_slug(name)}.xml"
        written.append(out)
        out.write_text(
            feed(f"{name} — Granite Record",
                 f"Activity on New Hampshire bills about {name}.",
                 bills_page, f"{base}/feed/topic/{topic_slug(name)}.xml",
                 newest(items), base), encoding="utf-8")

    # current.json's upcoming: each meeting still to come, filed under its
    # bill and under the committee that will sit, by chamber and name. THE
    # COMMITTEE BY ITS FOLLOW LABEL, THE ROOM IN WORDS (17 October 2026): the
    # email names the committee as current.json does, so that it is the same
    # name as the reader's own heading and links to the committee's page,
    # and says "Granite Place 231" where the clerk wrote "GP 231", as every
    # other line of the email does. FROM THE RECORDS, NOT home.json (26
    # October 2026): home.json's rows are the home page's calendar, cut at
    # eighty, and so were these (bill_upcoming, above, says why that is
    # gone). A committee's followers are sent the meeting without the
    # bill's own form and amendment link (committee_row).
    for (year, bid), ahead in sorted(ahead_of.items()):
        for one in ahead:
            upcoming.setdefault(f"bill:{year}/{bid}", []).append(one["row"])
            sits = cmte_code.get((one["body"], one["name"].lower())) if one["name"] else None
            if sits:
                upcoming.setdefault(f"committee:{sits}", []).append(FC.committee_row(one["row"]))

    # Upcoming hearings. Dated in the FUTURE, which most readers handle by
    # showing the item now -- which is the point. An item nobody sees until
    # after the hearing is worthless.
    hp = site / "home.json"
    nhear = 0
    if hp.exists():
        home = json.loads(hp.read_text(encoding="utf-8"))
        items = []
        for u in (home.get("upcoming") or []):
            b = find(u.get("bill", ""), u.get("date", ""))
            n = b["n"] if b else u.get("bill", "")
            when = u.get("date", "")
            items.append((
                f"{n} — {u.get('what','hearing')} on {when}"
                + (f" at {u['time']}" if u.get("time") else ""),
                bill_url(b) if b else bills_page,
                f"{(b or {}).get('title','')}\n\n"
                f"{u.get('committee','')} {u.get('what','')}"
                # The room in words, as the email's row below has it and
                # every page says it: "State Library Map Room", not "SL Map
                # Room" (26 October 2026).
                + (f", {PA.place(u['venue'])}" if u.get("venue") else "")
                # build_pages' note, by the hearing's chamber (hearing_note): the
                # person's words of 7 October 2026 (F2), and since 23 October
                # 2026 the Senate's, whose online sign-in takes no testimony.
                # Taken from there, not typed here, now that the home page
                # prints neither.
                + "\n\n" + BP.hearing_note(u.get("body")),
                when, f"hearing:{u.get('bill')}:{when}:{u.get('time','')}"))
            # A MEETING ON A BILL WITH NO PAGE still reaches the committee's
            # followers, from the calendar's row as before: the records above
            # have every other.
            if str(u.get("bill") or "").upper() in walked:
                continue
            body = str(u.get("body") or "").strip().upper()
            name = str(u.get("committee") or "").strip()
            sits = cmte_code.get((body, name.lower()))
            word = CHAMBER.get(body, "")
            row = FC.upcoming_row(
                when[:10], u.get("what") or "hearing", u.get("time") or "",
                FC.committee_label(name, word) if name else "",
                PA.place(u.get("venue") or ""))
            if row and sits:
                upcoming.setdefault(f"committee:{sits}", []).append(row)
        nhear = len(items)
        (fd / "hearings.xml").write_text(
            feed("Granite Record — upcoming hearings",
                 "Public hearings and executive sessions scheduled in the "
                 "next two weeks.",
                 f"{base}/", f"{base}/feed/hearings.xml", items, base),
            encoding="utf-8")

    # ---- one feed per legislator ------------------------------------------
    # Every vote and every sponsorship, in order, with nothing rated or
    # selected. The whole point of the site is that it does not keep a
    # scorecard, and a feed that ranked or summarised would be one.
    #
    # A vote is on the MOTION, not the bill. Voting yes on Inexpedient to
    # Legislate is a vote to kill it, so the motion is named in the title of
    # every item rather than left to the description, where a reader scanning
    # headlines would never see it.
    nleg = 0
    undated = 0
    empty = []
    lp = site / "legislators.json"
    # Each roll call's outcome and tally, for the ballots the changes files
    # set beside them (build_site_v2.write_rollcall_index).
    try:
        rc_index = json.loads((site / "rollcalls_index.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        rc_index = {}
    if lp.exists():
        (fd / "legislator").mkdir(parents=True, exist_ok=True)
        for m in json.loads(lp.read_text(encoding="utf-8")):
            mid = str(m.get("id") or "")
            # THE TEST THE MEMBER'S PAGE NAMES ITS FEED ON. build_legislator_pages
            # runs before this and has no file to look for, so both ask
            # shell.member_followable. This once wrote a feed wherever the
            # items below came to something, and no page named one.
            if not S.member_followable(m):
                continue
            who = m.get("display") or m.get("name") or f"Member #{mid}"
            items, mine = [], {}
            vp = site / "legislators" / f"{mid}.json"
            if vp.exists():
                rec = json.loads(vp.read_text(encoding="utf-8"))
                # Newest first by the day cast, before the cut: the file's own
                # order is not a promise this feed can lean on. Stable, so one
                # day's roll calls keep the order the file gives them.
                votes = sorted(rec.get("votes") or [],
                               key=lambda v: iso_day(v.get("d")), reverse=True)
                for v in votes[:a.per_feed]:
                    day = iso_day(v.get("d"))
                    undated += not day
                    bb = find(v.get("b"), day)
                    # A ROLL CALL THE CLERK FILED UNDER NO BILL is still a vote
                    # the member cast, and it needs a name of its own.
                    # RollCallSummary leaves the bill column empty for a motion
                    # the chamber makes about itself: 2026-H-290 "Affirm The
                    # Report" and 2026-H-291 "Remove From Table", both on the
                    # afternoon of 21 May 2026, and 2026-H-329 "Affirm The
                    # Report" on 19 August. All three sit inside the sixty
                    # items this feed carries for every one of the 382 sitting
                    # House members, so 1,146 titles opened on the em dash with
                    # nothing in front of it, reading "yes on Affirm The
                    # Report" after a leading space and a dash -- and in a
                    # reader that shows titles only, that is the whole item.
                    # The roll call's key says which chamber took it; say that.
                    seat = chamber_of(v.get("k"))
                    named = bool(bb) or bool((v.get("b") or "").strip())
                    if bb:
                        label = bb["n"]
                    elif named:
                        label = v["b"]
                    else:
                        label = f"{seat} floor vote" if seat else "Floor vote"
                    how = VOTE_WORD.get(v.get("v"), v.get("v") or "")
                    q = v.get("q") or "the motion"
                    # Joined from the parts there are. With no bill there is no
                    # title either, and the description used to open on a blank
                    # line for all 1,146 of them.
                    note = ("The vote is on the motion, not the bill." if named
                            else "The record files this roll call under no"
                                 " bill: it is a motion of the"
                                 f" {seat or 'chamber'} itself.")
                    items.append((
                        f"{label} \u2014 {how} on {q}",
                        bill_url(bb) if bb else bills_page,
                        "\n\n".join(x for x in (
                            (bb or {}).get("title", ""),
                            f"{who} voted {how} on {q}.", note) if x),
                        day,
                        # The roll call's own key, so two ballots cast on one
                        # bill on one day are two items. See vote_guid.
                        vote_guid(mid, v, q)))
                    rc = rc_index.get(v.get("k") or "") or {}
                    # The ballot and the motion in the site's words (17 October
                    # 2026): "On OTPA: voted Not Voting/Excused" was the roll
                    # call's codes. The feed's own title is left as it was.
                    asked = rc.get("q") or q
                    it = FC.item(items[-1][4], day, "vote", items[-1][0], path_of(items[-1][1]),
                                 (bb or {}).get("term") or P.term_on(day), milestone=True,
                                 vote=FC.vote_detail(
                                     ballot_word(v.get("v")),
                                     motion=PA.motion_words(asked, (bb or {}).get("id") or "",
                                                            {"House": "H", "Senate": "S"}.get(seat, ""))
                                     or asked,
                                     result=("passed" if rc.get("p") else "failed") if rc else "",
                                     tally=f"{rc['y']}-{rc['n']}" if rc.get("y") is not None
                                     and rc.get("n") is not None else "",
                                     bill=label, title=(bb or {}).get("title", "")))
                    if it:
                        mine[it["guid"]] = it
            for bb, burl, prime, filed in sponsored.get(mid, []):
                role = "prime sponsor" if prime else "co-sponsor"
                items.append((
                    f"{bb['n']} \u2014 {role}",
                    burl,
                    f"{bb.get('title', '')}\n\n{who} is the {role} of this bill.",
                    filed, f"sponsor:{mid}:{bb['id']}"))
                it = FC.item(items[-1][4], (filed or "")[:10], "sponsor", items[-1][0],
                             path_of(burl), bb.get("term") or "")
                if it:
                    mine[it["guid"]] = it
            key = f"member:{mid}"
            followable[key] = {"label": FC.line(m.get("display_full") or who, 120),
                               "url": path_of(base + S.canon(f"/legislator/{m.get('slug')}.html"))
                               if m.get("slug") else ""}
            if not followable[key]["url"]:
                del followable[key]["url"]
            # THE ROSTER'S OWN SORT NAME AND CHAMBER (the person's test of 16
            # October 2026: the manage page's list "sorted them by first name
            # instead of last name"). The label begins with the title and the
            # first name, so the page orders legislators by the roster's
            # "aldrich, glen" and sets the House and the Senate apart, as every
            # listing of legislators on the site does. Carried, not worked out
            # again from the label: a surname of two words, or a first name
            # the roster gives in another form, would be split wrongly.
            if FC.line(m.get("sort") or "", 120):
                followable[key]["sort"] = FC.line(m["sort"], 120)
            if FC.CHAMBERS.get(str(m.get("chamber") or "").upper()):
                followable[key]["chamber"] = FC.CHAMBERS[str(m["chamber"]).upper()]
            lists[key] = fc_list(newest(items), mine)
            if not items:
                # The roster counts a vote or a sponsorship that neither the
                # member's file nor any bill page carries: a site built in
                # pieces. Written anyway, because the member's page names it,
                # and counted below rather than passed over.
                empty.append(mid)
            self_l = f"{base}/feed/legislator/{mid}.xml"
            written.append(fd / "legislator" / f"{mid}.xml")
            (fd / "legislator" / f"{mid}.xml").write_text(
                feed(f"{who} \u2014 Granite Record",
                     f"Every recorded vote and sponsorship for {who}, newest "
                     "first. Nothing is rated, scored or selected.",
                     base + S.canon("/officials.html"), self_l, newest(items), base),
                encoding="utf-8")
            nleg += 1

    pruned, notes = 0, []
    for sub in ("bill", "committee", "topic", "legislator"):
        n, note = prune(fd / sub, written, a.allow_prune)
        pruned += n
        if note:
            notes.append(note)

    # BILL REQUESTS, FOLLOWED UNTIL THEY ARE BILLS (the person, 22 October
    # 2026: "email following for LSRs should ping when the legislation has
    # been drafted and then convert that into following the bill version").
    # Next session's requests (build_lsrs.py, site/idx/<year>-requests.json)
    # are followable as lsr:<number> while each is filed and not withdrawn --
    # and, once introduced, until its bill is followable itself, so the
    # follow always has somewhere to go. The night one leaves, its ending
    # names the bill it became (hints "becomes"), and the sender moves the
    # follow onto that bill; a withdrawn one ends as withdrawn.
    reqs = {}
    try:
        meta = json.loads((site / "meta.json").read_text(encoding="utf-8"))
        rterm = str(((meta.get("requests") or {}).get("term")) or "")
        if rterm:
            reqs = {"term": rterm, "rows": json.loads(
                (site / "idx" / f"{rterm}.json").read_text(encoding="utf-8"))}
    except (OSError, ValueError):
        reqs = {}
    nreq = 0
    for r in reqs.get("rows") or []:
        num = str(r.get("n") or "").replace("LSR", "").strip()
        key = f"lsr:{num}"
        if not FC.key_ok(key):
            continue
        intro = str(r.get("introduced") or "")
        m = re.match(r"^([A-Z]+) (\d+)$", intro)
        becomes = f"bill:{r.get('year') or num[:4]}/{m.group(1)}{m.group(2)}" if m else ""
        if r.get("withdrawn"):
            hints[key] = {"withdrawn": True}
            continue
        if becomes and becomes in followable:
            hints[key] = {"becomes": becomes, "bill": intro}
            continue
        followable[key] = {"label": FC.line(f"LSR {num}", 120),
                           "title": FC.line(r.get("title") or "", 300),
                           "now": FC.line(r.get("status") or "Filed as a request", 120),
                           "url": f"/bills?term={reqs['term']}&q=LSR%20{num}"}
        if not followable[key]["title"]:
            del followable[key]["title"]
        nreq += 1
    if reqs:
        print(f"  {nreq:,} bill requests followable until they are bills")

    # The changes files, from the items every feed above was written with.
    # A key the sender would refuse is left out and named, not sent.
    unkeyed = sorted(k for k in followable if not FC.key_ok(k))
    for k in unkeyed:
        followable.pop(k)
        lists.pop(k, None)
    changes_said = FC.write(site, built=BUILT, sitting_term=current, followable=followable,
                            lists=lists, upcoming=upcoming, hints=hints, led=led, why=led_why,
                            ledger_out=a.ledger_out)
    if unkeyed:
        changes_said.append(f"  WARNING: {len(unkeyed):,} records are not followable because "
                            f"their key is not one the sender reads: {unkeyed[:5]}")

    total = sum(p.stat().st_size for p in fd.rglob("*.xml"))
    print(f"{nbill:,} bill feeds")
    if skipped_closed:
        print(f"  {skipped_closed:,} bills of closed terms got no feed of "
              "their own: their history is on the page and cannot change")
    if skipped_concluded:
        print(f"  {skipped_concluded:,} concluded bills of the sitting term got "
              "no feed: only a bill still moving can be followed, and one that")
        print("    ended before anyone was following has no subscriber to tell")
    if retired:
        print(f"  {retired:,} bills concluded with a feed already published got "
              "a closing item and a retired feed:")
        print("    the outcome, and that nothing further will be posted there")

    if noyear:
        print(f"  {len(noyear):,} bills have no filing year and got no feed, "
              f"rather than one at feed/bill/ where the next term's bill of "
              f"the same number would overwrite it: {noyear[:5]}")
    if ambiguous[0]:
        print(f"  {ambiguous[0]:,} references name a bill number that exists "
              "in more than one term with no date to tell them apart")
    print(f"all.xml covers actions up to {TODAY}; anything scheduled later is "
          "in hearings.xml")
    print(f"{ncmte} committee feeds, keyed by code, {len(by_topic)} topic feeds")
    print(f"{nleg:,} legislator feeds")
    if empty:
        print(f"  {len(empty):,} of them have no items: legislators.json counts a vote or a "
              "sponsorship that neither the member's file nor any bill page carries, so the "
              f"site was built in pieces. Written anyway, since their pages name them: {empty[:5]}")
    if undated:
        print(f"  {undated:,} votes carry no date this reads (neither YYYY-MM-DD nor "
              "M/D/YYYY), so a reader is shown the build time for them")
    print(f"{pruned:,} stale feeds removed")
    if COLLIDED:
        print(f"  {sum(COLLIDED.values()):,} items across {len(COLLIDED):,} feeds "
              "share a guid with another item in the same feed. A reader keeps "
              "one item per guid, so it will show one of each pair and drop the "
              "rest without saying so:")
        for u, n in COLLIDED.most_common(3):
            print(f"    {u}  ({n:,})")
    for note in notes:
        print(note)
    print(f"all.xml: {len(newest(all_items))} items")
    print(f"hearings.xml: {nhear} upcoming")
    print(f"\n{total/1e6:.1f} MB of XML -> {fd}/")
    print()
    for ln in changes_said:
        print(ln)
    print(f"\nSubscribe links:\n  {base}/feed/all.xml\n  {base}/feed/hearings.xml")


if __name__ == "__main__":
    main()
