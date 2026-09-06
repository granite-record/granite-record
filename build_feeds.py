#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.4
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
    /feed/committee/<name>.xml       everything before one committee
    /feed/topic/<name>.xml           everything under one subject
    /feed/legislator/<id>.xml        one member's votes and sponsorships

The hearings feed is the one that can change what somebody does. A person who
learns on Tuesday that a hearing is on Thursday can turn up and testify; the
same person reading about it afterwards cannot.
"""

import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape

TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

# How a vote is written. Anything not listed is passed through as the record
# has it rather than translated into a word it did not use.
VOTE_WORD = {"Yea": "yes", "Nay": "no"}

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


def feed(title, desc, link, self_link, items, base):
    """items: (title, link, description, date, guid)"""
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
    a = ap.parse_args()
    site, base = Path(a.site), a.base.rstrip("/")
    idx = json.loads((site / "index.json").read_text(encoding="utf-8"))
    by_id = {b["id"]: b for b in idx}

    fd = site / "feed"
    (fd / "bill").mkdir(parents=True, exist_ok=True)
    (fd / "committee").mkdir(parents=True, exist_ok=True)
    (fd / "topic").mkdir(parents=True, exist_ok=True)

    def bill_url(b):
        return f"{base}/bill/{b.get('year','')}/{b['id'].lower()}.html"

    all_items, by_cmte, by_topic, nbill = [], {}, {}, 0
    sponsored = {}
    for b in idx:
        f = site / "bills" / f"{b['id']}.json"
        if not f.exists():
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        url = bill_url(b)
        events = [e for e in (d.get("events") or []) if e.get("date")]
        events.sort(key=lambda e: e["date"], reverse=True)
        filed = events[-1]["date"] if events else ""
        for sp in (d.get("sponsors") or []):
            mid = str(sp.get("member_id") or "")
            if mid:
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
                f"{b['id']}:{e['date']}:{slug(e.get('text',''))[:40]}"))

        if items:
            out = fd / "bill" / str(b.get("year", ""))
            out.mkdir(parents=True, exist_ok=True)
            self_l = f"{base}/feed/bill/{b.get('year','')}/{b['id'].lower()}.xml"
            (out / f"{b['id'].lower()}.xml").write_text(
                feed(f"{b['n']} — Granite Record",
                     b.get("title", "") or f"Actions on {b['n']}",
                     url, self_l, items[:a.per_feed], base), encoding="utf-8")
            nbill += 1

        # Scheduled proceedings are dated in the FUTURE, deliberately, so the
        # hearings feed reaches somebody in time to attend. This feed is the
        # record of what has happened, and readers treat a future date as a
        # reason to hide an item or sort it to the top -- either of which
        # buries the newest real activity. Future dates belong in one feed
        # only.
        all_items += [i for i in items if i[3] <= TODAY][:4]
        if b.get("committee"):
            # A bill that crossed over went through a committee in each
            # chamber, and belongs in both feeds. Committee names now carry
            # their chamber, so "House Finance" and "Senate Finance" are two
            # feeds rather than one mixed one.
            for cm in (b.get("committees") or ([b["committee"]] if b.get("committee") else [])):
                by_cmte.setdefault(cm, []).extend(items[:3])
        if b.get("topic"):
            by_topic.setdefault(b["topic"], []).extend(items[:3])

    def newest(items):
        return sorted(items, key=lambda x: x[3], reverse=True)[:a.per_feed]

    (fd / "all.xml").write_text(
        feed("Granite Record — all activity",
             "Every recorded action on New Hampshire legislation, newest "
             "first. Proceedings still to come are in the hearings feed.",
             f"{base}/", f"{base}/feed/all.xml", newest(all_items), base),
        encoding="utf-8")

    for name, items in by_cmte.items():
        (fd / "committee" / f"{slug(name)}.xml").write_text(
            feed(f"{name} — Granite Record",
                 f"Activity on bills before the {name} committee.",
                 f"{base}/bills.html", f"{base}/feed/committee/{slug(name)}.xml",
                 newest(items), base), encoding="utf-8")

    for name, items in by_topic.items():
        (fd / "topic" / f"{slug(name)}.xml").write_text(
            feed(f"{name} — Granite Record",
                 f"Activity on New Hampshire bills about {name}.",
                 f"{base}/bills.html", f"{base}/feed/topic/{slug(name)}.xml",
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
            b = by_id.get(u.get("bill", "").upper())
            n = b["n"] if b else u.get("bill", "")
            when = u.get("date", "")
            items.append((
                f"{n} — {u.get('what','hearing')} on {when}"
                + (f" at {u['time']}" if u.get("time") else ""),
                bill_url(b) if b else f"{base}/bills.html",
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
    lp = site / "legislators.json"
    if lp.exists():
        (fd / "legislator").mkdir(parents=True, exist_ok=True)
        for m in json.loads(lp.read_text(encoding="utf-8")):
            mid = str(m.get("id") or "")
            if not mid:
                continue
            who = m.get("display") or m.get("name") or f"Member #{mid}"
            items = []
            vp = site / "legislators" / f"{mid}.json"
            if vp.exists():
                rec = json.loads(vp.read_text(encoding="utf-8"))
                for v in (rec.get("votes") or [])[:a.per_feed]:
                    bb = by_id.get((v.get("b") or "").upper())
                    label = bb["n"] if bb else (v.get("b") or "")
                    how = VOTE_WORD.get(v.get("v"), v.get("v") or "")
                    q = v.get("q") or "the motion"
                    items.append((
                        f"{label} \u2014 {how} on {q}",
                        bill_url(bb) if bb else f"{base}/bills.html",
                        f"{(bb or {}).get('title', '')}\n\n{who} voted {how} on "
                        f"{q}.\n\nThe vote is on the motion, not the bill.",
                        v.get("d", ""),
                        f"vote:{mid}:{v.get('b')}:{v.get('d')}:{q[:30]}"))
            for bb, burl, prime, filed in sponsored.get(mid, []):
                role = "prime sponsor" if prime else "co-sponsor"
                items.append((
                    f"{bb['n']} \u2014 {role}",
                    burl,
                    f"{bb.get('title', '')}\n\n{who} is the {role} of this bill.",
                    filed, f"sponsor:{mid}:{bb['id']}"))
            if not items:
                continue
            self_l = f"{base}/feed/legislator/{mid}.xml"
            (fd / "legislator" / f"{mid}.xml").write_text(
                feed(f"{who} \u2014 Granite Record",
                     f"Every recorded vote and sponsorship for {who}, newest "
                     "first. Nothing is rated, scored or selected.",
                     f"{base}/legislators.html", self_l, newest(items), base),
                encoding="utf-8")
            nleg += 1

    total = sum(p.stat().st_size for p in fd.rglob("*.xml"))
    print(f"{nbill:,} bill feeds")
    print(f"all.xml covers actions up to {TODAY}; anything scheduled later is "
          "in hearings.xml")
    print(f"{len(by_cmte)} committee feeds, {len(by_topic)} topic feeds")
    print(f"{nleg:,} legislator feeds")
    print(f"all.xml: {len(newest(all_items))} items")
    print(f"hearings.xml: {nhear} upcoming")
    print(f"\n{total/1e6:.1f} MB of XML -> {fd}/")
    print(f"\nSubscribe links:\n  {base}/feed/all.xml\n  {base}/feed/hearings.xml")


if __name__ == "__main__":
    main()
