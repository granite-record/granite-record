#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-19.5
"""
A page for every day the House sat.

    python3 build_session_pages.py --site site --base https://graniterecord.org

WHAT IS ON ONE

The day in the order the clerk printed it, which is the order of the journal
pages the actions cite -- the record carries no clock for a floor action, and
the page number is the chamber's own sequence. For each bill, the motions put
to the House in turn: what was moved, who moved it, who spoke on which side,
how it was voted, and what carrying or failing did to the bill.

Then the debates the House voted to print in its permanent journal, and last
the remarks made under unanimous consent, which belong to no bill and are part
of the record all the same.

HOUSE ONLY, AND ON PURPOSE. Across all 491 Senate journal files "spoke in
favor" occurs four times and "spoke against" twice, and every one is ordinary
English inside a speech rather than a marker. The Senate journal does not
record who spoke on which side. Senate days are a separate job, not half of
this one.

THE MOTION IS THE HEADING, NEVER A FOOTNOTE

This is the whole shape of the page and it is not a style choice. "Rep. Ohm
spoke in favor" is not a fact a reader can use: in 320 measured cases the
motion was Inexpedient to Legislate and the member was arguing to KILL the
bill. Of 2,934 anchored attributions 655 -- 22% -- read in plain English as the
exact opposite of the truth. So speakers are never listed under a bill; they
are listed under the motion, with the motion stated above them, and the
sentence that follows says what the vote did.

ONE VOTE RENDERER, NOT TWO

The ring is drawn by app.js's simpleDonut, the same function the bill pages
use, from a payload this file emits. Drawing a second ring in Python that
merely looked like the first is the mistake this repository keeps a check
under. The tally is also written into the page as text, so a reader with no
script gets the count and the outcome and loses only the picture.

A roll call's named ballots are NOT copied here. A day with eleven roll calls
would carry four thousand names, and they are already on each bill's own page,
which this links to.
"""

import argparse
import collections
import json
import re
from pathlib import Path

import session_days
import journal_days
import shell as S
import structured as LD

DAYNAME = "Monday Tuesday Wednesday Thursday Friday Saturday Sunday".split()
MONTH = ("January February March April May June July August September "
         "October November December").split()

CHAMBER = {"H": "House", "S": "Senate"}

# The journal is the only source for who spoke, and it starts in 1997. Days
# before that get the record and say plainly that there is no journal for them,
# rather than looking like a day on which nobody spoke.
JOURNAL_FROM = "1997-01-01"


def words(iso):
    y, m, d = (int(x) for x in iso.split("-"))
    import datetime
    wd = datetime.date(y, m, d).weekday()
    return f"{DAYNAME[wd]} {d} {MONTH[m - 1]} {y}"


def load_titles(site):
    """{bill_id: (title, year)} from the term indexes the site already built."""
    titles, years = {}, {}
    idx = site / "idx"
    if idx.exists():
        for f in idx.glob("*.json"):
            try:
                rows = json.loads(f.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                continue
            for b in rows:
                if b.get("id"):
                    titles[b["id"]] = b.get("title") or ""
                    years[b["id"]] = b.get("year")
    return titles, years


class Members:
    """Names to pages, and only where the name can mean one person.

    A WRONG LINK IS WORSE THAN NO LINK. 304 surnames are shared by more than
    one person across the 2,191 with pages, so a surname alone is matched only
    where the chamber has exactly one. The journal solves this itself when it
    matters -- it prints the first name when two sitting members share a
    surname -- so "Peter Schmidt" resolves where "Schmidt" cannot, which is
    the convention this follows rather than a rule invented here.
    """

    def __init__(self, site):
        self.by_last = collections.defaultdict(list)
        self.by_full = {}
        for f, in (("legislators.json",), ("former.json",)):
            p = site / f
            if not p.exists():
                continue
            try:
                rows = json.loads(p.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                continue
            for r in rows:
                slug, name = r.get("slug"), (r.get("name") or "")
                ch = (r.get("chamber") or "").strip().upper()
                if not slug or "," not in name:
                    continue
                last, first = (x.strip() for x in name.split(",", 1))
                self.by_last[(ch, last.lower())].append(slug)
                self.by_full[(ch, f"{first} {last}".lower())] = slug
                # "Peter Schmidt" where the record holds "Schmidt, Peter E."
                bare = first.split()[0] if first.split() else ""
                if bare:
                    self.by_full.setdefault(
                        (ch, f"{bare} {last}".lower()), slug)

    def slug(self, body, name):
        n = re.sub(r"\s+", " ", (name or "").strip()).strip(".")
        if not n:
            return None
        hit = self.by_full.get((body, n.lower()))
        if hit:
            return hit
        parts = n.split()
        if parts:
            cand = self.by_last.get((body, parts[-1].lower()), [])
            if len(cand) == 1:
                return cand[0]
        return None


def base_bill(bid):
    """HB 1685-FN-LOCAL and HB 1685 are the same bill.

    The journal prints the fiscal and local suffixes and the parsed record does
    not, so a join on the literal string matched almost nothing: 383 speaker
    blocks across 806 days, where there should be thousands. The suffix says
    the bill has a fiscal note, which is true of the bill and not of the day,
    so it is dropped for matching and the record's own id is what the page
    shows.
    """
    return re.split(r"-", (bid or "").upper(), maxsplit=1)[0].strip()


def member_html(body, name, members, esc):
    slug = members.slug(body, name)
    who = esc(f"Rep. {name}" if body == "H" else f"Sen. {name}")
    if slug:
        return f'<a href="legislator/{esc(slug)}.html">{who}</a>'
    return f"<span>{who}</span>"


def vote_payload(item):
    """What simpleDonut needs, and nothing it does not.

    `passed` is the clerk's MA or MF, never whichever number is larger. On
    9 April 2026 the House recorded 186 yeas to 169 nays and the veto was
    SUSTAINED, because an override needs two thirds: the larger number is the
    losing one, and a page that inferred the winner from the tally would get
    every override and every constitutional amendment backwards.
    """
    if not item.counted:
        return None
    return {"yeas": item.yeas, "nays": item.nays,
            "passed": bool(item.carried),
            # Not always half plus one. The Senate writes "3/5 nec." into the
            # motion for a supermajority, and drawn as a simple majority the
            # ring's threshold mark says a motion cleared a bar it never
            # faced, or missed one it did.
            "threshold_needed": item.threshold_needed,
            "kind": item.kind}


def runs(items):
    """Consecutive actions on the same bill, grouped.

    A bill that comes up once in the day is one card. HB 1756 on 7 March 2018
    took four motions in a row -- an ITL that failed, a motion to table that
    failed, an Ought to Pass that carried and a reconsideration that failed --
    and those are one passage of the day's business, not four. They are
    consecutive in the journal because the House disposed of the bill before
    moving on, so grouping runs rather than bills keeps the day's order intact
    while still showing the bill once.
    """
    out = []
    for it in items:
        if out and out[-1][0] == it.bill:
            out[-1][1].append(it)
        else:
            out.append((it.bill, [it]))
    return out


def speakers_for(attrs, bill, item, sole=False):
    """The attributions belonging to this motion, split by side.

    An attribution is claimed by a motion only when the journal put a vote
    between it and the next bill AND that vote's tally is this motion's. That
    is the one tie strong enough to publish: it does not depend on where the
    question line sits relative to the speech, which moved between eras --
    speeches precede the question line 338 times to 66 in 1997-2000 and follow
    it 1,427 to 148 by 2021-2026.

    Everything else is returned as unplaced, and the page says only that they
    spoke during the bill, which is true.
    """
    mine = {"for": [], "against": []}
    rest = {"for": [], "against": []}
    want = (item.yeas, item.nays) if item.counted else None
    for a in attrs:
        if base_bill(a.get("bill")) != base_bill(bill):
            continue
        side = a["side"]
        # ONE MOTION MEANS NO AMBIGUITY. Where the House put a single motion on
        # a bill that day there is nothing for a speech to belong to but that
        # motion, so the tally is not needed to claim it. Most bills are like
        # this, and requiring the tally threw away every speech on a bill
        # decided by voice -- which is the commonest way the House decides.
        if sole or (want and a.get("tally") == want):
            mine[side] += a["names"]
        else:
            rest[side] += a["names"]
    return mine, rest


def bill_href(bid, years, esc):
    yr = years.get(bid)
    return (f"bill/{yr}/{bid.lower()}.html" if yr
            else f"/bills#{esc(bid)}")


def opening_html(narrative, body, members, esc):
    """How the day began, in one sentence.

    THE PRAYER IS NOT QUOTED AND THE CHAPLAIN IS NOT NAMED. The journal prints
    the prayer in full and it is pastoral rather than parliamentary: the one on
    6 March 2025 asks the House to pray for "Rep. Grossman's son, Oscar" and
    for a named widow mourning her named husband. None of those people is a
    public official or party to any business before the House, and this site
    exists to make the record findable, which is exactly what would make
    republishing them different in kind from their sitting in a PDF.

    So the page records THAT a prayer was offered. The member who led the
    Pledge is named, because a legislator acting in the chamber is the record.
    """
    o = narrative.get("opening") or {}
    if not o:
        return ""
    bits = []
    if o.get("assembled"):
        bits.append(f"The {CHAMBER[body]} assembled at {esc(o['assembled'])}")
    say = []
    if o.get("prayer"):
        say.append("a prayer was offered")
    if o.get("pledge"):
        say.append(member_html(body, o["pledge"], members, esc)
                   + " led the Pledge of Allegiance")
    line = ". ".join(bits)
    if say:
        line = (line + ". " if line else "") + ", and ".join(say).capitalize() \
            if not line else line + ", " + " and ".join(say)
    return ('<section class="sday sopen"><h2>How the day began</h2>'
            f"<p>{line}.</p></section>")


def absences_html(narrative, body, members, esc):
    """Who the chamber excused. WHO, and not why.

    The journal records a ground for each leave -- illness, important
    business, illness in the family -- and this published it until
    19 September, when the person asked for names only. The reason is health
    information about a named person, and while the journal prints it, this
    site's business is making the record findable, which is what makes
    repeating it here different in kind from its sitting in a PDF. That a
    member was excused is the parliamentary fact; why is not.

    The groups are still read from the journal, because that is how the lines
    parse, and then flattened into one list.
    """
    rows = narrative.get("absences") or []
    if not rows:
        return ""
    names, seen = [], set()
    for r in rows:
        for nm in r["names"]:
            k = nm.lower()
            if k not in seen:
                seen.add(k)
                names.append(nm)
    if not names:
        return ""
    n = len(names)
    return ('<section class="sday"><h2>Excused for the day</h2>'
            f'<p class="note">{n} member{"" if n == 1 else "s"} had leave of '
            f'the {CHAMBER[body]} and were not in the chamber.</p>'
            '<p class="sspoke sabs">'
            + ", ".join(member_html(body, nm, members, esc) for nm in names)
            + "</p></section>")


# What a motion carrying did to a bill, in one word, for a list of seventy.
SHORT = (
    (("inexpedient to legislate", "indefinitely postpone"), "Killed", "Kept alive"),
    (("ought to pass",), "Passed", "Not passed"),
    (("refer for interim study", "re-refer", "rerefer"), "Sent to interim study",
     "Not sent to interim study"),
    (("adopt",), "Adopted", "Not adopted"),
)


def short_outcome(item):
    a = (item.action or "").strip().lower()
    for starts, yes, no in SHORT:
        if a.startswith(starts):
            if item.carried is None:
                return yes.rstrip("ed") + "ed?" if False else "Considered"
            return yes if item.carried else no
    return (item.action or "Considered").strip()


def consent_html(cons, removed, titles, years, esc):
    """The bills the chamber disposed of together, grouped by what happened.

    A consent calendar is one motion covering dozens of bills that nobody
    asked to debate -- 75 of the 121 things the House did on 6 March 2025 --
    so they belong in a list, by outcome. Printed as 75 entries in the day's
    sequence they bury the 46 bills it actually argued about.

    Any member may pull a bill off the list, and the journal names the bill
    and the members who did. A bill that came off was debated like any other
    and is not here; it is in the sequence below.
    """
    if not cons:
        return ""
    groups = {}
    for i in cons:
        groups.setdefault(short_outcome(i), []).append(i)
    n = len({i.bill for i in cons})
    note = (f'{n} bill{"" if n == 1 else "s"} the chamber disposed of '
            "together, in one motion and without debate.")
    if removed:
        pretty = ", ".join(re.sub(r"^([A-Z]+)(\d)", r"\1 \2", b)
                           for b in sorted(removed))
        note += (f" {pretty} {'was' if len(removed) == 1 else 'were'} taken off "
                 "the list at a member's request and debated separately.")
    H = ['<section class="sday"><h2>On the consent calendar</h2>'
         f'<p class="note">{esc(note)}</p>']
    for label in sorted(groups):
        items = sorted(groups[label], key=lambda x: x.bill)
        H.append(f'<div class="scons"><h3 class="slab">{esc(label)} '
                 f'&mdash; {len(items)}</h3><ul class="sconslist">')
        for i in items:
            num = re.sub(r"^([A-Z]+)(\d)", r"\1 \2", i.bill)
            ti = titles.get(i.bill) or ""
            H.append(f'<li><a class="cbn" href="{esc(bill_href(i.bill, years, esc))}">'
                     f"{esc(num)}</a>"
                     + (f'<span class="cbt">{esc(ti)}</span>' if ti else "")
                     + "</li>")
        H.append("</ul></div>")
    H.append("</section>")
    return "".join(H)


def render(day, narrative, titles, years, members, esc):
    """The day, as HTML."""
    H = []
    body = day.body
    attrs = narrative.get("attributions") or []
    debates = {base_bill(d.get("bill")): d
               for d in (narrative.get("debates") or []) if d.get("bill")}
    payloads = []

    # ONLY CLAIM AN ORDER WHERE THE RECORD HOLDS ONE. The journal page is the
    # chamber's own sequence and it is cited on 24% of House actions and 0.3%
    # of Senate ones -- in practice from 2016 for the House and almost never
    # for the Senate. Where it is absent the actions are listed by bill, which
    # is predictable and is NOT the order they happened in, and the heading
    # says so rather than letting an alphabetical list read as a narrative.
    # A printed debate is drawn once even where its bill holds the floor twice.
    removed = (narrative.get("consent") or {}).get("removed") or []
    seq_items, cons = day.split(removed)

    H.append(opening_html(narrative, body, members, esc))
    H.append(absences_html(narrative, body, members, esc))
    H.append(consent_html(cons, removed, titles, years, esc))

    drawn = set()
    if day.ordered:
        H.append('<section class="sday"><h2>The day in order</h2>')
    else:
        H.append('<section class="sday"><h2>What the '
                 f'{CHAMBER[body]} did that day</h2>'
                 '<p class="note">The record does not say what order these '
                 "came in: the journal page is cited on only a few of them, "
                 "so they are listed by bill.</p>")
    for bill, items in runs(seq_items):
        ti = titles.get(bill) or ""
        num = re.sub(r"^([A-Z]+)(\d)", r"\1 \2", bill)
        leftover = set()
        H.append('<article class="sitem">')
        H.append(f'<h3><a class="sbill" href="{esc(bill_href(bill, years, esc))}">'
                 f'{esc(num)}</a>'
                 + (f'<span class="sbt">{esc(ti)}</span>' if ti else "") + "</h3>")

        for it in items:
            H.append('<div class="smotion">')
            moved = (f' <span class="smover">moved by '
                     f'{member_html(body, it.mover.replace("Rep. ", "")
                                   .replace("Sen. ", ""), members, esc)}</span>'
                     if it.mover else "")
            H.append(f'<p class="smq">On the motion: <b>{esc(it.action)}</b>{moved}</p>')

            mine, rest = speakers_for(attrs, bill, it, sole=(len(items) == 1))
            for side, label in (("for", "Spoke for the motion"),
                                ("against", "Spoke against the motion")):
                who = mine[side]
                if who:
                    H.append(f'<p class="sspoke"><span class="slab">{label}</span>'
                             + ", ".join(member_html(body, n, members, esc)
                                         for n in who) + "</p>")

            leftover.update(rest["for"])
            leftover.update(rest["against"])
            p = vote_payload(it)
            if p:
                i = len(payloads)
                payloads.append(p)
                kindw = esc(it.kind_words or "vote")
                H.append(f'<div class="svote" data-vote="{i}">'
                         f'<p class="stally">A {kindw}: '
                         f'<b>{it.yeas}</b> yeas, <b>{it.nays}</b> nays.</p></div>')
                if it.kind == "RC":
                    H.append('<p class="swho">Who voted which way is on '
                             f'<a href="{esc(bill_href(bill, years, esc))}">'
                             f"{esc(num)}'s own page</a>.</p>")
            elif it.kind == "VV":
                H.append('<p class="stally">Taken on a voice vote, so no count '
                         "was recorded.</p>")

            if it.outcome_words:
                H.append(f'<p class="soutcome">{esc(it.outcome_words)}</p>')
            H.append("</div>")

        # NAMED, BUT NOT TAKEN A SIDE FOR. These spoke on this bill on a day
        # the House put several motions to it, and nothing in the record ties
        # the speech to one of them. Their side is deliberately NOT shown:
        # "spoke in favor" means the opposite of its plain reading 22% of the
        # time, and it is the motion that disambiguates it. Naming them without
        # a side is true; guessing the motion would not be.
        if leftover:
            names = sorted(n for n in leftover if n)
            if names:
                H.append('<p class="sspoke sother"><span class="slab">Also '
                         "spoke during this bill</span>"
                         + ", ".join(member_html(body, n, members, esc)
                                     for n in names)
                         + '<span class="snote">the record does not say which '
                           "of the day's motions</span></p>")

        # The debate the House voted to keep, under the bill it belongs to --
        # ONCE. A bill can hold the floor twice in a day with other business
        # between: HB 396 was vetoed at page 12, reconsidered at 38 and voted
        # again at 42, which is two runs, and the debate printed for it was
        # drawn under both. There is one debate; it goes under the first run.
        d = debates.get(base_bill(bill))
        if d and d["speeches"] and id(d) not in drawn:
            drawn.add(id(d))
            H.append(_debate_html(d, body, members, esc))
        H.append("</article>")
    H.append("</section>")

    # Debates whose bill is not among the day's actions -- a motion to print
    # can name a bill the House took no recorded vote on that day.
    seen = {base_bill(b) for b, _ in runs(seq_items)}
    loose = [d for k, d in debates.items() if k and k not in seen and d["speeches"]]
    if loose:
        H.append('<section class="sday"><h2>Also printed in the permanent '
                 "journal</h2>")
        for d in loose:
            H.append(_debate_html(d, body, members, esc, head=True))
        H.append("</section>")

    uc = narrative.get("unanimous_consent") or []
    if uc:
        H.append('<section class="sday"><h2>Under unanimous consent</h2>'
                 '<p class="note">These belong to no bill. The House gives a '
                 "member leave to address it, and what they said is part of "
                 "the permanent record.</p><ul class=\"suc\">")
        for x in uc:
            about = x["about"]
            H.append("<li>" + member_html(body, x["name"], members, esc)
                     + (f", on {esc(about)}." if about and
                        about != "addressed the House" else " addressed the House.")
                     + "</li>")
        H.append("</ul></section>")
    return "".join(H), payloads


def _debate_html(d, body, members, esc, head=False):
    """A printed debate: the opening, and the rest behind a disclosure.

    They run long -- 5,507 speeches across 298 debates -- so the page shows
    enough to know what it is and opens on request.
    """
    sp = d["speeches"]
    # THE CHAIR IS NOT A SPEAKER IN THE DEBATE. "Speaker Chandler: The question
    # before the House is the adoption of the majority committee report. The
    # Chair recognizes the member from Hampton" is the chair running the
    # debate, not taking part in it, and counting those turns reported a
    # thirteen-speech debate where five members spoke. The lines are still
    # shown -- they are what ties one speech to the next -- but the count is
    # of the people who argued.
    CHAIR = ("speaker", "deputy speaker", "madam speaker", "mister speaker",
             "president", "madam president", "mister president")
    # NOT `members`: that name is the index of people-to-pages this function
    # is handed, and shadowing it made every speaker link raise.
    spoke = [x for x in sp if not x[0].lower().startswith(CHAIR)]
    first = (spoke or sp)[0][1]
    opener = " ".join(re.split(r"(?<=[.!?])\s+", first)[:2])[:420]
    n = len(spoke)
    title = ""
    if head and d.get("bill"):
        title = f'<b>{esc(re.sub(r"^([A-Z]+)(\\d)", r"\\1 \\2", d["bill"]))}</b> '
    out = ['<details class="sdebate"><summary>',
           f'<span class="sdlab">{title}Debate printed in the permanent '
           f'journal</span>',
           f'<span class="sdn">{n} speech{"" if n == 1 else "es"}</span>',
           '<span class="caret"></span></summary>',
           f'<p class="sdopen">{esc(opener)}…</p>',
           '<div class="sdbody">']
    for who, said in sp:
        nm = re.sub(r"^(Rep(?:resentative)?\.?|Speaker|Deputy Speaker)\s+",
                    "", who).strip()
        link = (member_html(body, nm, members, esc)
                if not who.lower().startswith("speaker")
                else f"<span>{esc(who)}</span>")
        out.append(f'<p class="sdsp">{link}<span class="sdtx">{esc(said)}</span></p>')
    out.append("</div></details>")
    return "".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    ap.add_argument("--base", default="https://graniterecord.org")
    ap.add_argument("--body", default="H",
                    help="H or S. A Senate page carries the record only: its "
                         "journal records no speakers")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    site, base = Path(a.site), a.base.rstrip("/")
    body = a.body.strip().upper()

    days = session_days.load()
    mine = sorted(k for k in days if k[0] == body)
    # SILENCE IS NOT SUCCESS: no days is a Calendar linking at nothing, and a
    # build that said so by printing a zero.
    assert mine, f"no {CHAMBER.get(body, body)} sitting days in narratives.json"

    titles, years = load_titles(site)
    members = Members(site)
    out_dir = site / "session" / body
    out_dir.mkdir(parents=True, exist_ok=True)

    urls, wrote, with_narr, linked, unlinked = [], 0, 0, 0, 0
    order = mine[: a.limit] if a.limit else mine
    for n, key in enumerate(order):
        day = days[key]
        date = day.date
        # THE SENATE JOURNAL IS NOT READ, and that is not an oversight. Across
        # all 491 Senate files there are no UNANIMOUS CONSENT sections, no
        # REMARKS, no PERSONAL PRIVILEGE, and "spoke in favor" appears in three
        # files as ordinary English inside a speech. The Senate journal does
        # not record who spoke on which side, so there is nothing here to
        # parse and the page says so instead of showing an empty section.
        blank = {"attributions": [], "debates": [], "unanimous_consent": []}
        narrative = (blank if (body != "H" or date < JOURNAL_FROM)
                     else journal_days.read_day(date))
        if narrative.get("attributions") or narrative.get("debates"):
            with_narr += 1

        for at in (narrative.get("attributions") or []):
            for nm in at["names"]:
                if members.slug(body, nm):
                    linked += 1
                else:
                    unlinked += 1
        block, payloads = render(day, narrative, titles, years, members, S.E)
        label = f"The {CHAMBER[body]}, {words(date)}"
        lead = _lead(day, narrative, date, body)
        prev_ = order[n - 1][1] if n > 0 else ""
        next_ = order[n + 1][1] if n + 1 < len(order) else ""
        nav = []
        if prev_:
            nav.append(f'<a class="wkprev" href="{S.canon(f"session/{body}/{prev_}.html")}">'
                       f"&lsaquo; The sitting before</a>")
        if next_:
            nav.append(f'<a class="wknext" href="{S.canon(f"session/{body}/{next_}.html")}">'
                       f"The sitting after &rsaquo;</a>")

        path = f"session/{body}/{date}.html"
        html = S.page(S.template(site), path=path, base=base,
                      title=f"{label} | Granite Record",
                      description=(f"What the New Hampshire {CHAMBER[body]} did on "
                                   f"{words(date)}: every bill, motion and vote, "
                                   "in the order the journal records them."),
                      og_title=label, globals={"GR_STATIC": True}, noscript="",
                      skip_label="Skip to the sitting", sr_title="",
                      og_type="article", nav_current="calendar.html",
                      jsonld=LD.listing(label, lead, base, S.canon(path)))
        payload = json.dumps(payloads, separators=(",", ":"))
        full = ('<div id="results"><div class="wkpage sesspage">'
                f"<h1>{S.E(label)}</h1>"
                + (f'<p class="src">{S.E(day.journal)}. {S.E(lead)}</p>'
                   if day.journal else f'<p class="src">{S.E(lead)}</p>')
                + f'<nav class="wknav" aria-label="Other sittings">{"".join(nav)}</nav>'
                + block
                + f'<nav class="wknav wkfoot" aria-label="Other sittings">{"".join(nav)}</nav>'
                + f'<script type="application/json" id="sessvotes">{payload}</script>'
                "</div></div>")
        html = html.replace('<div id="results"></div>', full, 1)
        assert 'class="wkpage sesspage"' in html, f"{path}: no results slot"
        (site / path).write_text(html, encoding="utf-8")
        urls.append(base + S.canon(path))
        wrote += 1


    sm = site / "sitemap.xml"
    if sm.exists():
        text = sm.read_text(encoding="utf-8")
        add = "".join(f"<url><loc>{S.E(u)}</loc></url>\n" for u in urls
                      if S.E(u) not in text)
        if add:
            sm.write_text(text.replace("</urlset>", add + "</urlset>"),
                          encoding="utf-8")
            print(f"  {len(add.splitlines())} added to sitemap.xml")

    print(f"  {wrote:,} {CHAMBER[body]} sitting days -> site/session/{body}/")
    print(f"    {with_narr:,} carry a journal narrative "
          f"(the journal starts {JOURNAL_FROM[:4]})")
    named = linked + unlinked
    if named:
        # A WRONG LINK IS WORSE THAN NO LINK, so this number is meant to be
        # short of 100% -- a surname shared by two members of the same chamber
        # is left as text. It is printed so that a drop to nothing, which is
        # what a broken index looks like, cannot pass as normal.
        print(f"    {linked:,} of {named:,} speaker mentions resolved to a "
              f"member page ({100.0 * linked / named:.0f}%)")
    return 0


def _lead(day, narrative, date, body="H"):
    n = len(day.items)
    b = len(day.bills)
    k = day.counts()
    bits = [f"{n} action{'' if n == 1 else 's'} on {b} bill{'' if b == 1 else 's'}"]
    if k:
        bits.append(", ".join(f"{v} {name}{'' if v == 1 else 's'}"
                              for name, v in sorted(k.items())))
    d = len(narrative.get("debates") or [])
    if d:
        bits.append(f"{d} debate{'' if d == 1 else 's'} printed in the "
                    "permanent journal")
    if body == "S":
        bits.append("The Senate journal does not record who spoke for or "
                    "against a motion, so this is the vote record without "
                    "the debate")
    elif date < JOURNAL_FROM:
        bits.append("The journal is on record from 1997, so this day carries "
                    "the vote record without the debate")
    return ". ".join(bits) + "."


if __name__ == "__main__":
    raise SystemExit(main())
