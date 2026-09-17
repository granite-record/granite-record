#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.16
"""
Write RSS feeds so people can follow bills without a login.

    python3 build_feeds.py --site site --base https://graniterecord.org

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
"""

import argparse
import json
import proceedings as P
import re
import shell as S
import site_read as SR
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape

TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

# How a vote is written. Anything not listed is passed through as the record
# has it rather than translated into a word it did not use.
VOTE_WORD = {"Yea": "yes", "Nay": "no"}

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
        dt = datetime.now(timezone.utc)
    return (f"{DAYS[dt.weekday()]}, {dt.day:02d} {MONTHS[dt.month - 1]} "
            f"{dt.year} {dt.hour:02d}:{dt.minute:02d}:00 +0000")


def iso_day(d):
    """'8/19/2026' or '2026-08-19' -> '2026-08-19'; '' when it is neither.

    A member file writes a vote's date as the roll call export does, M/D/YYYY,
    and everything a vote's date is used for below -- the term its bill is
    found in, the order items sort in, the pubDate a reader sees -- reads
    YYYY-MM-DD. Until 13 September every vote in every legislator feed carried
    the build time as its date, sorted 9/4 above 8/19 and 12/2 below both, and
    linked the bills page for any bill number used in more than one term.
    """
    s = str(d or "").strip()
    for fmt, n in (("%Y-%m-%d", 10), ("%m/%d/%Y", None)):
        try:
            return datetime.strptime(s[:n] if n else s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""


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


FULL_MONTHS = ["January", "February", "March", "April", "May", "June", "July",
               "August", "September", "October", "November", "December"]


def long_date(d):
    """2026-02-12 -> 12 February 2026, the way a feed title reads aloud."""
    try:
        y, m, dd = (int(x) for x in d[:10].split("-"))
        return f"{dd} {FULL_MONTHS[m - 1]} {y}"
    except (ValueError, IndexError):
        return d


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
                   "failed, not of housekeeping. --allow-prune once, if it is intended.")
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
            f"<lastBuildDate>{rfc822(datetime.now(timezone.utc).isoformat())}</lastBuildDate>\n"
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
    a = ap.parse_args()
    site, base = Path(a.site), a.base.rstrip("/")
    idx = json.loads((site / "index.json").read_text(encoding="utf-8"))
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
            hit = by_id.get((P.term_of(date), bill))
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
    bill_items = {}
    # How a concluded bill's closing feed item names its ending. The index's
    # own `kind`, put into a sentence -- the record's word for what happened is
    # already on the page, and this is the feed saying the same thing once.
    OUTCOME = {
        "law": "was signed into law",
        "done": "has finished its course",
        "veto": "was vetoed",
        "adopted": "was adopted",
        "study": "was referred for interim study",
    }
    skipped_closed = retired = 0
    noyear = []
    sponsored = {}
    # Each bill's record, read from its page. It used to be opened from
    # site/bills/<year>/<ID>.json, which since the records moved inside the
    # pages exists only for the few too large to inline -- so for two days this
    # wrote 173 feeds and skipped every other bill without a word, while 5,436
    # bill pages linked a feed that was never written.
    recs = SR.by_bill(site, fields=("events", "sponsors", "next_step"))
    # A FEED IS FOR A BILL THAT CAN STILL DO SOMETHING. One per bill of a
    # closed term is a file that will never gain an item: nobody subscribes
    # to 1993. Writing them for every archived bill once the 1989-2016
    # histories arrived would have put 22,840 more files on a deployment
    # already at 55,318 of the 100,000 Cloudflare Pages allows -- and it is
    # the per-bill feed only. The all-bills, committee and topic feeds are
    # unchanged, and every archived bill's history is on its page.
    current = max((b.get("term") or "" for b in idx), default="")
    # UNDER THE MEMBER THE BILL'S PAGE LINKS, where it links one. The record's
    # own id is an employee number or nothing on most sponsor records, and a
    # sitting member's feed filed under it missed the sponsorships their page
    # lists -- build_site_v2.bill_sponsor_list files them the same way.
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
        events = [e for e in (d.get("events") or []) if e.get("date")]
        events.sort(key=lambda e: e["date"], reverse=True)
        filed = events[-1]["date"] if events else ""
        seen = set()
        for sp in (d.get("sponsors") or []):
            mid = by_slug.get(sp.get("slug")) or str(sp.get("member_id") or "")
            if mid and mid not in seen:
                seen.add(mid)
                sponsored.setdefault(mid, []).append(
                    (b, url, bool(sp.get("prime")), filed))

        items = []
        for e in events:
            items.append((
                f"{b['n']} \u2014 {clip(e.get('text',''))}",
                url,
                f"{b.get('title','')}\n\n{e.get('text','')}\n\n"
                f"Status: {d.get('next_step','')}",
                e["date"],
                f"{b.get('term','')}:{b['id']}:{e['date']}:"
                f"{slug(e.get('text',''))[:40]}"))

        # A BILL THAT HAS FINISHED GETS ONE LAST ITEM, AND THEN NOTHING.
        # The person's decision of 17 September: "A concluding bill should get
        # one final update on how it ended and retire the feed after that."
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
        # EVERY CONCLUDED BILL OF THE SITTING TERM, not only the ones whose
        # feed happens to be on disk. Scoping it to existing files was the
        # first attempt and it was wrong twice over: it would have made the
        # build depend on the state of site/, so two runs from identical data
        # could differ, and a fresh clone would produce a different site from
        # this one. Determinism is worth more than the file count.
        #
        # The consequence, stated plainly because it is the real cost: a feed
        # is kept for every bill of the term that ever had one, which is about
        # 2,200 rather than 215. prune() removes what a run does not write, so
        # a retired feed survives only by being written every run -- and it is
        # written identically each time, same guid and same date, so it sits
        # still. No page advertises it; a subscriber who already has it is who
        # it is for.
        _closing = (items and (b.get("term") or "") == current
                    and not S.still_moving(b, current))
        if _closing:
            _end = OUTCOME.get((b.get("kind") or "").lower(), "has concluded")
            items.insert(0, (
                f"{b['n']} — {_end}. This feed is now closed.",
                url,
                f"{b.get('title','')}\n\n{b['n']} {_end}. No further updates "
                "will be posted here: a bill that has finished its course has "
                "nothing more to report. Its full history stays on its page.",
                events[0]["date"],
                f"{b.get('term','')}:{b['id']}:closed:{(b.get('kind') or '')}"))
            retired += 1

        if items and (b.get("term") or "") != current:
            skipped_closed += 1
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

    def newest(items):
        return sorted(items, key=lambda x: x[3], reverse=True)[:a.per_feed]

    (fd / "all.xml").write_text(
        feed("Granite Record — all activity",
             "Every recorded action on New Hampshire legislation, newest "
             "first. Proceedings still to come are in the hearings feed.",
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
    for cj in sorted((site / "committee").glob("*.json")) if (site / "committee").is_dir() else []:
        try:
            c = json.loads(cj.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if not S.committee_followable(c):
            continue
        code = str(c.get("code") or cj.stem)
        chamber = {"H": "House", "S": "Senate"}.get(code[:1].upper(), "")
        who = f"{chamber} {c.get('name') or code}".strip()
        page = base + S.canon(f"/committee/{code}.html")
        items = []
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
        if not items:
            for rows in (c.get("bills") or {}).values():
                for r in rows or []:
                    items += bill_items.get((str(r.get("year") or ""), str(r.get("id") or "").upper()), [])
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
        out = fd / "topic" / f"{slug(name)}.xml"
        written.append(out)
        out.write_text(
            feed(f"{name} — Granite Record",
                 f"Activity on New Hampshire bills about {name}.",
                 bills_page, f"{base}/feed/topic/{slug(name)}.xml",
                 newest(items), base), encoding="utf-8")

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
                + (f", {u['venue']}" if u.get("venue") else "")
                + "\n\nAnyone may attend and speak, or sign in for or against "
                  "without speaking.",
                when, f"hearing:{u.get('bill')}:{when}:{u.get('time','')}"))
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
    if lp.exists():
        (fd / "legislator").mkdir(parents=True, exist_ok=True)
        for m in json.loads(lp.read_text(encoding="utf-8")):
            mid = str(m.get("id") or "")
            # THE TEST THE MEMBER'S PAGE NAMES ITS FEED ON. build_legislator_pages
            # runs before this and has no file to look for, so both ask
            # shell.member_followable. Until 13 September this wrote a feed
            # wherever the items below came to something, and no page named one.
            if not S.member_followable(m):
                continue
            who = m.get("display") or m.get("name") or f"Member #{mid}"
            items = []
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
            for bb, burl, prime, filed in sponsored.get(mid, []):
                role = "prime sponsor" if prime else "co-sponsor"
                items.append((
                    f"{bb['n']} \u2014 {role}",
                    burl,
                    f"{bb.get('title', '')}\n\n{who} is the {role} of this bill.",
                    filed, f"sponsor:{mid}:{bb['id']}"))
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
                     base + S.canon("/legislators.html"), self_l, newest(items), base),
                encoding="utf-8")
            nleg += 1

    pruned, notes = 0, []
    for sub in ("bill", "committee", "topic", "legislator"):
        n, note = prune(fd / sub, written, a.allow_prune)
        pruned += n
        if note:
            notes.append(note)

    total = sum(p.stat().st_size for p in fd.rglob("*.xml"))
    print(f"{nbill:,} bill feeds")
    if skipped_closed:
        print(f"  {skipped_closed:,} bills of closed terms got no feed of "
              "their own: their history is on the page and cannot change")
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
    print(f"\nSubscribe links:\n  {base}/feed/all.xml\n  {base}/feed/hearings.xml")


if __name__ == "__main__":
    main()
