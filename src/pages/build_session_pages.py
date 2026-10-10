#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-19.30
"""
A page for every day the House sat.

    python3 src/pages/build_session_pages.py --site site --base https://graniterecord.org

WHAT IS ON ONE

The day in the order the clerk printed it, which is the order of the journal
pages the actions cite -- the record carries no clock for a floor action, and
the page number is the chamber's own sequence. For each bill, the motions put
to the House in turn: what was moved, who moved it, who spoke on which side,
how it was voted, and what carrying or failing did to the bill.

AND THE DAYS AS DATA. Beside the pages, site/session/<H|S>/<term>.json:
every day of the term with its journal and counts, who presided and who was
excused, the consent calendar, and every bill voted on with each vote in
order and the committee recommendation acted on (day_record, below; the
person's feedback of 9 October 2026, v12-v18 and item 18).

Then the debates the House voted to print in its permanent journal, and last
the remarks made under unanimous consent, which belong to no bill and are part
of the record all the same.

WHO SPOKE IS HOUSE ONLY, AND ON PURPOSE. Across all 491 Senate journal files
"spoke in favor" occurs four times and "spoke against" twice, and every one is
ordinary English inside a speech rather than a marker. The Senate journal does
not record who spoke on which side. A Senate page carries the record and the
senators the journal excused for the day, which is all its journal adds.

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

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import collections
import datetime
import json
import re

import bill_order as BO
import build_date
import committee_acts as CA
import session_days
import journal_days
import officers
import proceedings
import shell as S
import structured as LD


CHAMBER = {"H": "House", "S": "Senate"}

# The journal is the only source for who spoke, and it starts in 1997. Days
# before that get the record and say plainly that there is no journal for them,
# rather than looking like a day on which nobody spoke.
JOURNAL_FROM = "1997-01-01"


def said_clock(t):
    """"10:00 a.m." as the journal prints it, "10:00 AM" as this site writes a
    time (the person's D6, 8 October 2026, and build_pages.clock's form, the
    no-break space included). Anything else comes back as it came."""
    m = re.fullmatch(r"\s*(\d{1,2}):(\d\d)\s*([ap])\.?\s*m\.?\s*", t or "", re.I)
    if not m or not 1 <= int(m.group(1)) <= 12:
        return t or ""
    return f"{int(m.group(1))}:{m.group(2)}\u00a0{m.group(3).upper()}M"


def words(iso):
    """"Thursday, February 19, 2026": a session day's own title, and the
    directory's, by shell.date_words."""
    return S.date_words(iso, "long")


def load_titles(site):
    """({(term, bill_id): title}, {(term, bill_id): year}) from the term
    indexes the site already built.

    KEYED ON THE TERM, BECAUSE A BILL NUMBER IS NOT A BILL. The numbers start
    again every two years, and these were keyed on the number alone, so
    whichever term's index was read last owned every number: 73,268 of the
    79,508 bill links on the sitting pages went to a bill of another term, and
    the title beside each was that other bill's. The House page for
    9 March 2016 linked HB 1102 to the 2026 bill of that number and printed
    its title. Every action on a sitting day comes from one term's record, and
    carries that term, so the lookup is by the pair.
    """
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
                    key = (b.get("term") or f.stem, b["id"])
                    titles[key] = b.get("title") or ""
                    years[key] = b.get("year")
    return titles, years


class Members:
    """Names to pages, and only where the name can mean one person.

    A WRONG LINK IS WORSE THAN NO LINK. 304 surnames are shared by more than
    one person across the 2,191 with pages, so a surname alone is matched only
    where the chamber has exactly one. The journal solves this itself when it
    matters -- it prints the first name when two sitting members share a
    surname -- so "Peter Schmidt" resolves where "Schmidt" cannot, which is
    the convention this follows rather than a rule invented here.

    ONLY THE MEMBERS WHO SERVED THAT TERM COUNT (the person, 9 October 2026,
    of the House's 19 August 2026 excused list). Gary Daniels, Ron Dunn,
    Kimberly Rice and Len Turcotte were left unlinked because a former member
    who left years ago shares each surname -- Eric Daniels, J. Timothy Dunn,
    three former Rices, Alan and Alisson Turcotte -- and nobody who had left
    could have been excused that day. A former member counts only for the
    terms their record gives (`served.terms`); a sitting member always counts.
    Two members serving the same term with one surname still leave the name
    unlinked, as before. `term` is set for each day before it is drawn.
    """

    def __init__(self, site):
        self.by_last = collections.defaultdict(list)
        # A FULL NAME IS NOT ALWAYS ONE PERSON EITHER: the sitting Mark Pearson
        # (Rock 34) and the Mark Pearson of 2007-2008 (Rock 4) share one, and
        # the former member, loaded second, took every "Rep. Mark Pearson" on
        # 38 House session days, 2026's among them -- a wrong link. Full names
        # are matched among the members serving the term, as surnames are.
        self.by_full = collections.defaultdict(list)
        self.term = ""
        # Each member by their id and by their page, with the party and the
        # label their record gives: a session day's term file counts the
        # excused by party and names who presided (day_record).
        self.by_id, self.by_slug = {}, {}
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
                if slug:
                    info = {"id": str(r.get("id") or ""), "slug": slug,
                            "label": r.get("display_full") or r.get("label") or "",
                            "party": party_letter(r.get("party") or r.get("party_code"))}
                    self.by_slug.setdefault(slug, info)
                    if info["id"]:
                        self.by_id.setdefault(info["id"], info)
                if not slug or "," not in name:
                    continue
                last, first = (x.strip() for x in name.split(",", 1))
                terms = (set((r.get("served") or {}).get("terms") or [])
                         if f == "former.json" else None)
                self.by_last[(ch, last.lower())].append((slug, terms))
                self.by_full[(ch, f"{first} {last}".lower())].append((slug, terms))
                # "Peter Schmidt" where the record holds "Schmidt, Peter E."
                bare = first.split()[0] if first.split() else ""
                if bare and bare != first:
                    self.by_full[(ch, f"{bare} {last}".lower())].append((slug, terms))

    def slug(self, body, name):
        n = re.sub(r"\s+", " ", (name or "").strip()).strip(".")
        if not n:
            return None
        full = self.serving(self.by_full.get((body, n.lower()), []))
        if len(full) == 1:
            return full[0]
        if full:
            return None
        # A surname of two words is the whole name: the Senate Journal's
        # "Senator Fuller Clark" and "Senator Perkins Kwoka", whose last word
        # alone is someone else's surname or no one's.
        cand = self.serving(self.by_last.get((body, n.lower()), []))
        if len(cand) == 1:
            return cand[0]
        parts = n.split()
        if parts:
            cand = self.serving(self.by_last.get((body, parts[-1].lower()), []))
            if len(cand) == 1:
                return cand[0]
        return None

    def serving(self, cands):
        """The slugs of `cands` who served `self.term`: every sitting member,
        and a former member only where their record names that term. With no
        term set, everyone, as before."""
        return list(dict.fromkeys(s for s, terms in cands
                                  if terms is None or not self.term or self.term in terms))


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


def members_row(body, names, members, esc):
    """The members of a line, each with the comma that follows it.

    THE COMMA BELONGS TO THE NAME BEFORE IT. These lines are flex rows
    (.sspoke) with a gap between their items, and the names were joined with
    ", ": a comma between two elements is a piece of text on its own, so it
    became an item of its own and took the gap on both sides -- "Rep. Barbour
    , Rep. Bridle ,", with a space before every comma, on every sitting's page
    (the audit of 2 October 2026, M20). Each name and its comma are one item
    now. The space written between two items is not drawn in a flex row; it
    is there for a copy of the text and for a screen reader.
    """
    out = [member_html(body, n, members, esc) for n in names]
    return " ".join(f'<span class="swho1">{h}{"," if i + 1 < len(out) else ""}</span>'
                    for i, h in enumerate(out))


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
            # faced, or missed one it did. Three fifths is of the members in
            # office, which session_days takes from the roll call's ballots;
            # where there are none, the ring draws no mark.
            "threshold_needed": item.threshold_needed,
            **({"threshold_unknown": True} if item.threshold_unknown else {}),
            "kind": item.kind}


ROLLCALL_ONLY = ('<p class="swho">The docket has no line for this vote: the '
                 "question is as the General Court&rsquo;s roll-call file words "
                 "it.</p>")


def _question_html(it, moved, esc):
    """"On the motion: ...", or, for a roll call the record states with no
    words for its question -- an empty question in the roll-call file, a
    1989-1998 docket row cut from its line -- says so rather than leaving the
    heading empty."""
    if (it.action or "").strip():
        return f'<p class="smq">On the motion: <b>{esc(it.action)}</b>{moved}</p>'
    return f'<p class="smq">On a question the record does not name{moved}</p>'


def _ballots_here(it):
    """Are this roll call's ballots on the bill's own page? Not where the
    roll-call file holds the vote under another bill or under none -- one
    motion on several bills -- and not for a motion drawn from the docket
    alone: no roll call on record is tied to it, so there are no ballots to
    be anywhere. The page said there were 1,402 times, every roll call of
    1989-1998 among them; HB 1's own page of 1997 holds no vote of 10 June."""
    rc = getattr(it, "rc", None)
    if rc is None:
        return False
    return bool(rc.get("bill")) and session_days._bill_of(rc["bill"]) == it.bill.upper()


def others_html(others, body, members, esc, payloads):
    """The day's roll calls on no bill -- the chamber's own rules, a ruling
    of the chair, printing a debate, adjourning -- in the roll-call file's
    order, worded as that file words them. The page says no more of them
    than the file does: no debate, no speaker, nothing done to a bill."""
    if not others:
        return ""
    H = ['<section class="sday"><h2>Votes on no bill</h2>'
         '<p class="note">Roll calls the '
         f"{CHAMBER[body]} took that day on questions that were on no bill, such "
         "as its own rules, a ruling of the chair or printing a debate. The "
         "question is as the General Court&rsquo;s roll-call file words it.</p>"]
    for it in others:
        moved = (f' <span class="smover">moved by '
                 f'{member_html(body, it.mover.replace("Rep. ", "").replace("Sen. ", ""), members, esc)}'
                 "</span>" if it.mover else "")
        H.append('<article class="sitem"><div class="smotion">')
        H.append(_question_html(it, moved, esc))
        p = vote_payload(it)
        if p:
            i = len(payloads)
            payloads.append(p)
            H.append(f'<div class="svote" data-vote="{i}">'
                     f'<p class="stally">A {esc(it.kind_words or "vote")}: '
                     f'<b>{it.yeas}</b> yeas, <b>{it.nays}</b> nays.</p></div>')
        if it.outcome_words:
            H.append(f'<p class="soutcome">{esc(it.outcome_words)}</p>')
        H.append("</div></article>")
    H.append("</section>")
    return "".join(H)


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
        # The same number from two terms is two bills: the House organization
        # day of 1 December 2004 took up HR 1 of 2003-2004 and HR 1 of
        # 2005-2006.
        if out and out[-1][0] == it.bill and out[-1][1][0].term == it.term:
            out[-1][1].append(it)
        else:
            out.append((it.bill, [it]))
    return out


def speech_groups(items):
    """{id(item): group} -- what a bill's speeches are shared out over:
    every motion the bill had that day, however many runs (above) they fall
    in. The journal gives a speech to a bill and a day, never to a run.

    Shared out run by run, a bill that two runs split had two "one motion"
    days, and each claimed every speech: HB 1633's tabling and its removal
    from the table on 13 June 2024 fell either side of another bill's roll
    call, and SB 101's amendment 1451h of 23 April 2026 sat on page 37 with
    SB 586 between it and the bill's other motions, so it took every speech
    the bill had and named Rep. Peternel on both sides of it."""
    return {id(it): (it.term, it.bill) for it in items}


def ambiguous_tallies(items):
    """The counts more than one of these motions is known by. A speech the
    journal ties to such a count is tied to neither: HB 1's reconsideration
    and its final adoption of 26 June 2025 were both 185-180, and each was
    given the other's speakers."""
    seen = collections.Counter(t for it in items
                               for t in (getattr(it, "tallies", None) or
                                         ({(it.yeas, it.nays)} if it.counted else set())))
    return frozenset(t for t, n in seen.items() if n > 1)


# The kinds of motion a speaker's own "moved ..." and the record's action are
# compared by, the more particular first: "Nonconcur" before "concur", and a
# reconsideration of a concurrence is a reconsideration. A motion neither side
# names one of is never called different.
MOTION_KINDS = [
    ("reconsider", r"reconsider"), ("nonconcur", r"non-?\s*concur"),
    ("concur", r"\bconcur"), ("recommit", r"\bre-?\s*commit|\bre-?\s*refer"),
    ("table", r"\btable\b"), ("itl", r"inexpedient|\bITL\b"),
    ("study", r"interim\s+study"), ("otp", r"ought\s+to\s+pass|\bOTP"),
    # Acceding to a request for a committee of conference, or refusing to, is
    # that motion, not the committee's report: "House Refuses to Accede to
    # Senate Request for C of C (Rep Bates)" (SB 193, 8 June 2011) read as a
    # conference motion and Rep. Bates's own "moved that the House refuse to
    # accede" as another, and his speech, tied by the count, went unnamed.
    ("accede", r"\baccede"),
    ("conference", r"committee\s+of\s+conference|\bC\s*of\s*C\b|conf\s+comm"),
    ("postpone", r"indefinitely\s+postpone"), ("vacate", r"\bvacate"),
]


def _motion_kind(text):
    for kind, pat in MOTION_KINDS:
        if re.search(pat, text or "", re.I):
            return kind
    return None


def _same_motion(moved, action):
    """False only where both name a kind of motion and the kinds differ."""
    a, b = _motion_kind(moved), _motion_kind(action)
    return not (a and b and a != b)


# The same kinds, and two more the House moves in the middle of a debate on
# something else: to postpone to a day certain and to make a special order.
# Only for asking whether a motion was made after a speech (made_after): the
# comparisons above keep the list they were measured with.
# And to divide the question: "Rep. Vaillancourt moved that Section 2 be
# divided" after eight members had spoken on HB 375's amendment (3 May
# 2001), and the roll call that followed, 20-338, was on dividing it.
MOTION_KINDS_SINCE = MOTION_KINDS + [
    ("postpone to a day", r"\bpostpone\b"),
    ("special order", r"\bspec(?:ial)?\.?\s+order"),
    ("divide", r"\bdivid(?:e|ed|ing)\b|\bdiv\s*\?"),
]


def _kind_since(text):
    for kind, pat in MOTION_KINDS_SINCE:
        if re.search(pat, text or "", re.I):
            return kind
    return None


# What a motion moved in the journal's long form asks for comes last: "moved
# that the request for concurrence with amendment on HB 374, relative to ...,
# be laid on the table" is a motion to table, and read from its first words
# it was one about concurring. A motion in any other form is read whole, in
# the kinds' order: what follows "reconsider" is the action to be
# reconsidered ("... whereby the House adopted the committee report of
# Inexpedient to Legislate on HR 30"), and a reconsideration is that kind
# first.
MOVED_TO_BE = re.compile(
    r"\bbe\s+((?:laid|tabled|indefinitely|postponed|made\s+a\s+special|re-?\s*committed|"
    r"re-?\s*referred|referred)\b.*)$", re.I | re.S)


def _moved_kind(moved):
    """The kind of one motion the journal records as moved (`moved_since`)."""
    m = MOVED_TO_BE.search(moved or "")
    return _kind_since(m.group(1) if m else moved)


def made_after(a, item):
    """True where the journal shows a motion of this item's kind being moved
    AFTER the speech and before the vote the speech precedes
    (journal_days.MOVED_SINCE, the attribution's `moved_since`).

    Then the vote is on that later motion and the speech was on whatever
    stood before it, so the count ties the speech to nothing. "Rep. Arndt
    moved that the House concur and spoke in favor", then "Rep. Rice moved
    that the request for concurrence ... be laid on the table", then YEAS 62
    NAYS 273: HB 374's page of 9 June 1999 had Rep. Arndt speaking for laying
    the bill on the table. While a lost motion carried no count in the
    1999-2006 docket there was nothing for such a speech to be tied to; once
    "Lay on the Table, ML RC(62-273)" was read with its count, sixteen tabling
    motions of those years and a postponement and a special order each took
    the speeches made before them. The rule is the journal's and holds for
    every year: measured on 1 October 2026 it moves 490 names on 163
    bill-days of 1997-2026, 36 of them in 1999-2006, from a motion to "also
    spoke". On 7 January 2026 the page had Rep. Mark Pearson speaking against
    his own motion to postpone HB 349 indefinitely.

    A motion of another kind made between the two does not untie the
    speech: on HR 20 of 2000 the House debated the report, refused to table
    it on a division, and then voted 162-179 on the report, and those who
    spoke on the report are tied to that vote as they were."""
    kind = _kind_since(item.action)
    return bool(kind) and any(_moved_kind(m) == kind
                              for m in a.get("moved_since") or ())


def several_on_line(item):
    """True where the item is a line the 1999-2006 reader joined back
    together from rows that, read one by one, were several floor actions,
    and which still tells one (session_days.Item.joined): a line the reader
    could split into its motions again is several items and carries no mark.
    Each row was a motion on this page before they were joined; the line
    tells the last one carried, so it is not the one motion of the day that
    ONE MOTION MEANS NO AMBIGUITY in speakers_for assumes."""
    return (getattr(item, "joined", 0) or 0) > 1


def journal_count(a):
    """The count the journal ties a speech to: the division or later roll
    call that decided its question (journal_days' `decided`), none where a
    voice vote decided it or another question was put first (`untied`), and
    otherwise the roll call printed after it; None where there is none."""
    d = a.get("decided") or {}
    if d.get("count"):
        return tuple(d["count"])
    if d.get("words") or d.get("untied"):
        return None
    return tuple(a["tally"]) if a.get("tally") else None


def untied(a):
    """Did the journal put another question between this speech and the
    next decision (journal_days' walk)? Then no motion claims it."""
    return bool((a.get("decided") or {}).get("untied"))


def clerk_counts(attrs, items):
    """The attributions, each tied by a roll call the journal prints one vote
    off the ballots tied instead by that roll call's own count.

    THE JOURNAL'S HEADER IS THE CLERK'S COUNT, AND IT CAN BE ONE OFF. SB 197's
    report of 6 June 2007 is roll call 140 of the year, 227-122 on the
    ballots; House Journal 18 prints "YEAS 227 NAYS 121" over it, and the
    four members who spoke before it -- Reps. Hunt, Martin, DeStefano and
    McLeod -- were tied to a count no motion of the day is known by and named
    nowhere. Only a roll call the journal itself prints after the speech
    (`tally`, or a later roll call journal_days' walk read to), and only
    where exactly one motion of the bill that day, a roll call, is known by a
    count within one vote a side of it: before the roll-call file the
    docket's count is the one the clerk's is compared with (HB 1520's
    adoption of 18 June 1998, 145-133 in the docket and 145-134 in the
    journal)."""
    mine = collections.defaultdict(list)
    for it in items:
        mine[base_bill(it.bill)].append(it)
    out = []
    for a in attrs:
        d = a.get("decided") or {}
        t = journal_count(a)
        its = mine.get(base_bill(a.get("bill")), [])
        if t is None or (d and not d.get("roll_call")) or \
                any(t in _known(it) for it in its):
            out.append(a)
            continue
        near = [(it, x) for it in its for x in sorted(_known(it)) if _near(t, x, 1)]
        if len({id(it) for it, _x in near}) == 1 and near[0][0].kind == "RC":
            x = tuple(near[0][1])
            a = dict(a, decided=dict(d, count=x)) if d else dict(a, tally=x)
        out.append(a)
    return out


def _near(a, b, by):
    return abs(a[0] - b[0]) <= by and abs(a[1] - b[1]) <= by


def _known(item):
    """Every count the motion is known by (session_days.Item.tallies)."""
    want = getattr(item, "tallies", None)
    if want is None:
        want = {(item.yeas, item.nays)} if item.counted else set()
    return want


# A question decided by voice on an amendment is the amendment's: "Floor
# amendment (0786h) failed." The report it amended -- "Ought to Pass with
# Amendment", which names one -- and a concurrence are not.
AMENDMENT = re.compile(r"\bamendment\b", re.I)
NOT_AMENDMENT = re.compile(r"\breport\b|ought\s+to\s+pass|\bOTP\b|concur", re.I)


VOICE_LOST = re.compile(r"\b(?:failed|lost|defeated)\b", re.I)
VOICE_CARRIED = re.compile(r"\b(?:adopted|prevailed|carried|passed)\b", re.I)


def on_amendment(words):
    return bool(AMENDMENT.search(words or "")) and not NOT_AMENDMENT.search(words or "")


def claims(a, item, sole=False, ambiguous=frozenset()):
    """Does this motion claim one attribution of its bill? speakers_for says
    when; the page's "also spoke" list asks the same question of every
    motion (unplaced). `ambiguous` is the counts more than one of the bill's
    motions that day is known by (ambiguous_tallies)."""
    # A SPEECH ANOTHER QUESTION CAME BETWEEN IS NO MOTION'S. The journal put a
    # motion, an amendment or an appeal after it and decided that first; the
    # speech fell through to the next roll call and named Rep. Rowe on HB
    # 1670's floor amendment of 15 February 2012, whose committee amendment he
    # had spoken for. journal_days reads what comes between (walk).
    if untied(a):
        return False
    # A motion moved after the speech, where the speech is tied to the roll
    # call after it: journal_days' walk reads it where it decides first.
    if not a.get("decided") and made_after(a, item):
        return False
    # Any count the motion is known by: where the page draws the ballots'
    # count the journal prints the clerk's, and the speech is tied by that.
    want = _known(item)
    t = journal_count(a)
    tied = bool(want) and t is not None and t in want and t not in ambiguous
    # THE JOURNAL'S COUNT IS NOT OVERRULED BY THERE BEING ONE MOTION. A speech
    # the journal ties to another count was on another question, and the one
    # motion the record holds for the bill that day did not take it: on
    # 21 May 2026 Reps. Corcoran, Simpson and McFarlane spoke before the roll
    # call of 288-54 on a report censuring Rep. Corcoran, which the journal
    # prints after HB 1194 under no bill heading of its own, and the page had
    # them speaking on HB 1194's nonconcurrence, decided by voice.
    if t is not None and not tied:
        return False
    # Nor is a question decided by voice: a motion that was counted did not
    # decide it, and one on an amendment is the amendment's.
    d = a.get("decided") or {}
    words = d.get("words")
    if words and (item.counted or ((on_amendment(words) or d.get("amendment"))
                                   and not on_amendment(item.action))):
        return False
    # Nor one the voice vote decided the other way: "Rep. Daniels spoke
    # against the Majority report. The report failed." (HB 1417, 5 March
    # 1998) was on the report, not on the Ought to Pass with Amendment he then
    # moved and the House adopted, the one motion the record holds that day.
    if words and item.carried is not None:
        lost = bool(VOICE_LOST.search(words))
        if lost == bool(item.carried) and (lost or VOICE_CARRIED.search(words)):
            return False
    if sole and not _same_motion(a.get("inline_motion"), item.action):
        return False
    if sole and several_on_line(item):
        k = _motion_kind(a.get("inline_motion"))
        return tied or bool(k and k == _motion_kind(item.action))
    return bool(sole or tied)


def unplaced(attrs, bill, items, ambiguous=frozenset(), known=None):
    """The names of the bill's speakers no motion of the day claims, sorted.

    BY THE SPEECH, NOT BY THE MOTION. This was every speech each motion did
    not claim, motion by motion, so a speech one motion claimed was listed
    again as unplaced because the motion beside it did not claim it too: HB
    1348 of 2002 named all five of its credited speakers a second time under
    "the record does not say which of the day's motions", 633 bill-days of
    1997-2026 did the same, and telling a line's questions one by one made it
    677. A member who spoke twice, once on a motion the record ties and once
    not, is still named in both places, which is what happened.

    NOT A SPEECH THE JOURNAL TIES TO A VOTE NONE OF THE BILL'S MOTIONS IS.
    Its question is one the page does not draw under the bill, and the
    journal can print such a question inside a bill's stretch without being
    the bill's: Reps. Steven Smith and Paige Beauchemin spoke on the motion to
    reprimand her, carried on a division of 264-89 after the recess that
    followed HB 1584's roll call on 12 February 2026 and under no bill heading
    of its own, and were the page's "also spoke" for HB 1584. Such a speech is
    named nowhere, which is less than the journal says
    and nothing it contradicts. `known` is every count the bill's motions that
    day are known by, the vote of a recess and of the roll-call file among
    them; by default, `items`'."""
    sole = len(items) == 1
    if known is None:
        known = set().union(*(_known(it) for it in items)) if items else set()
    out = set()
    for a in attrs:
        if base_bill(a.get("bill")) != base_bill(bill):
            continue
        t = journal_count(a)
        if t is not None and t not in known:
            continue
        if not any(claims(a, it, sole, ambiguous) for it in items):
            out.update(n for n in a["names"] if n)
    for it in items:
        mine = {"for": [], "against": []}
        for a in attrs:
            if base_bill(a.get("bill")) == base_bill(bill) and \
                    claims(a, it, sole, ambiguous):
                mine[a["side"]] += a["names"]
        out |= two_sided(mine)
    return sorted(out)


def speakers_for(attrs, bill, item, sole=False, ambiguous=frozenset()):
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
    for a in attrs:
        if base_bill(a.get("bill")) != base_bill(bill):
            continue
        side = a["side"]
        # ONE MOTION MEANS NO AMBIGUITY. Where the House put a single motion on
        # a bill that day there is nothing for a speech to belong to but that
        # motion, so the tally is not needed to claim it. Most bills are like
        # this, and requiring the tally threw away every speech on a bill
        # decided by voice -- which is the commonest way the House decides.
        # UNLESS THE JOURNAL NAMES ANOTHER. "Rep. Mock moved Re-commit to
        # Committee and spoke in favor" is a speech on recommittal, and the
        # 14 April 1999 page put it under HB 605's Inexpedient to Legislate,
        # the one motion the record holds that day. Where the motion the
        # speaker moved and the record's are plainly different motions, the
        # speaker is named as having spoken during the bill and no more.
        # UNLESS THE LINE PUT SEVERAL. A joined line whose rows were several
        # floor actions and which still tells one (several_on_line) is one
        # motion on the page and several on the floor, so a speech is claimed
        # only on evidence: its vote's tally is this motion's, or the speaker
        # moved this kind of motion. A speech on CACR 21 of 1999's passage,
        # which failed 224-109 short of three fifths, would otherwise be
        # credited to the tabling that followed it on the same line.
        # AND NEVER A MOTION MADE AFTER THE SPEECH, whether it is the one
        # motion of the day or its count is the vote's (made_after).
        # All of it is decided in claims(), which the page's "also spoke"
        # list asks of every motion too.
        # A member who spoke twice on the motion is named once: HB 317's
        # report of 4 June 2026 read "Spoke for the motion Rep. Berry, Rep.
        # Berry, Rep. Berry, Rep. Berry".
        to = (mine if claims(a, item, sole, ambiguous) else rest)[side]
        for n in a["names"]:
            if n not in to:
                to.append(n)
    # NEVER ON BOTH SIDES OF ONE MOTION. A member the journal has speaking in
    # favor and against on the one day a bill had one motion spoke on two
    # questions -- an amendment and the report -- and which side of this
    # motion they took the record does not say: 153 motions of 1997-2026
    # named someone on both sides, Rep. Daniels on HB 666's Inexpedient to
    # Legislate of 5 March 1997 among them. Such a member spoke during the
    # bill (unplaced), and no more.
    both = two_sided(mine)
    for side in ("for", "against"):
        rest[side] += [n for n in mine[side] if n in both and n not in rest[side]]
        mine[side] = [n for n in mine[side] if n not in both]
    return mine, rest


def two_sided(mine):
    return set(mine["for"]) & set(mine["against"])


def bill_href(term, bid, years):
    """The page of THIS term's bill of that number, or None.

    None where the term's index does not hold the bill, and the caller then
    prints the number without a link. A WRONG LINK IS WORSE THAN NO LINK: the
    old fallback, /bills#HB1, opened whichever HB 1 the bill list shows first,
    which is the current term's.
    """
    yr = years.get((term, bid))
    return f"bill/{yr}/{bid.lower()}.html" if yr else None


def bill_link(term, bid, text, years, esc, cls=""):
    """The bill's number, linked to its own term's page where there is one."""
    href = bill_href(term, bid, years)
    c = f' class="{cls}"' if cls else ""
    if href:
        return f'<a{c} href="{esc(href)}">{esc(text)}</a>'
    return f"<span{c}>{esc(text)}</span>"


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
        bits.append(f"The {CHAMBER[body]} assembled at {esc(said_clock(o['assembled']))}")
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

    THE NOTE SAYS WHAT THE JOURNAL SAYS AND NO MORE. It said these members
    "were not in the chamber", which the ballots contradict on 244 member-days
    from 1999 to 2026: on 11 March 2026 Rep. Cornell, on leave for the day, is
    recorded excused on roll calls 133 to 172 and voting on 173 to 188. The
    two records also disagree the other way: Rep. William Dolan, on leave on
    7 January 2026, is recorded "not excused" on all 31 roll calls that day.

    THE SENATE NAMES ITS OWN, from the opening of each sitting
    (journal_days.read_senate_day), and only those excused for the day, by
    the person's decision of 24 September 2026. The same caution holds there:
    of 103 senators so named on a day with roll calls, 2003 to 2026, 102 are
    recorded excused on every one of them, and Senator Carson, excused as
    the Senate opened on 7 May 2026, voted on all seven that afternoon.
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
    if body == "S":
        who = f'{n} senator{"" if n == 1 else "s"} as excused by the Senate'
        one = "A senator excused for the day may still have voted on part of it"
    else:
        who = (f'{n} member{"" if n == 1 else "s"} as having leave of the '
               f"{CHAMBER[body]}")
        one = "A member on leave may still have voted on part of the day"
    return ('<section class="sday"><h2>Excused for the day</h2>'
            f'<p class="note">The journal records {who} for the day, that is, '
            f"permission to be away. {one}, and the roll call record does not "
            "always agree with the journal about who was excused.</p>"
            '<p class="sspoke sabs">'
            + members_row(body, names, members, esc)
            + "</p></section>")


# What a motion carrying did to a bill, in one word, for a list of seventy.
# A RE-REFERRAL IS NOT INTERIM STUDY (8 October 2026). "re-refer" and
# "rerefer" sat in the interim study row, so every Senate consent calendar's
# "Rereferred to Committee, MA, VV" (SB 18 of 2015, on the calendar of 12
# February 2015) was listed under "Sent to interim study": 160 entries on the
# Senate's sitting pages, 32 of them this term, every one a bill the Senate
# had sent back to the committee that reported it. The bill's own How it got
# here says "Sent back to committee" (build_site_v2._j_words, a recommittal),
# and so does this list now. A re-referral whose words name interim study is
# interim study, and the study row is read first.
SHORT = (
    (("inexpedient to legislate", "indefinitely postpone"), "Killed", "Kept alive"),
    (("ought to pass",), "Passed", "Not passed"),
    (("refer for interim study", "re-refer for interim study", "re-refer to interim study",
      "rerefer for interim study", "rerefer to interim study"), "Sent to interim study",
     "Not sent to interim study"),
    (("re-refer", "rerefer"), "Sent back to committee", "Not sent back to committee"),
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


# THE BILL'S OWN LINE CAN SAY IT CAME OFF. journal_days.taken_off counts a
# removal the journal prints outside the consent segment only for a bill the
# record has on that day's list, and the record's list is the bills whose
# floor action that day is a consent item. HB 605 of 1999 was one while its
# 14 April line was read a row at a time, wrongly, as the report to kill it
# adopted; read whole the line is "ITL Report adopted; Consent Cal
# reconsidered, Rep Mock MA VV; Removed from Consent Cal, req Rep Mock;
# Recommitted to committee, Rep Mock MA VV", its action is the recommittal,
# and the page's note that HB 605 was taken off the list -- true, and printed
# in the journal -- went with the mistake. A floor line with a clause of its
# own saying the bill was removed from the consent calendar puts the bill on
# that day's list as surely as a consent item does. A clause of its own: "Special
# Order to after the bills removed from the Consent Calendar" names other
# bills. Measured on 1 October 2026 this is HB 605 and nothing else: the
# 1989 lines that open "REMOVED FROM CC" are older than the journals on
# disk, and HB 1563 of 2012's removal is printed inside the segment.
CAME_OFF_IN_LINE = re.compile(
    r"(?:^|;)\s*removed\s+from\s+(?:the\s+)?(?:consent|cons\b|cons\.|CC\b)", re.I)


def came_off_in_line(item):
    return bool(CAME_OFF_IN_LINE.search(getattr(item, "raw", "") or ""))


def calendar_vote(cons):
    """[(kind words, yeas, nays, carried)] -- the counted votes a consent
    calendar was taken on, each once.

    The calendar is one motion, and where the chamber counted it -- the
    Senate by roll call through 2021, 23 to 1 on 22 April 2021; the House
    on a division, 282 to 9, on 25 March 2014 -- that one vote is every
    consent bill's tally (session_days._one_counted_vote). It is said once,
    on the list, and counted once in the opening."""
    out = []
    for i in cons:
        if i.kind in ("RC", "DV") and i.counted:
            k = (i.kind_words, i.yeas, i.nays, i.carried)
            if k not in out:
                out.append(k)
    return out


def consent_html(cons, removed, titles, years, esc, calendar=()):
    """The bills the chamber disposed of together, grouped by what happened.

    A consent calendar is one motion covering dozens of bills that nobody
    asked to debate -- 75 of the 121 things the House did on 6 March 2025 --
    so they belong in a list, by outcome. Printed as 75 entries in the day's
    sequence they bury the 46 bills it actually argued about.

    Any member may pull a bill off the list, and the journal names the bill
    and the members who did. A bill that came off is not here.

    THE NOTE SAYS IT CAME OFF AND NO MORE. It said such bills were "debated
    separately", which the record does not say and often contradicts: HB 189,
    389, 527, 549 and 679 came off on 13 March 2013 and were "Special Ordered
    to Next Session Without Objection" that day, and HB 1288 and HB 1223, off
    on 11 March 2026, were taken up the next day. The bill histories had
    already stopped saying it.
    """
    if not cons:
        return ""
    groups = {}
    for i in cons:
        groups.setdefault(short_outcome(i), []).append(i)
    n = len({(i.term, i.bill) for i in cons})
    note = (f'{n} bill{"" if n == 1 else "s"} the chamber disposed of '
            "together, in one motion and without debate.")
    for kind, yeas, nays, carried in calendar:
        how = ("was adopted" if carried else "failed" if carried is False
               else "was taken")
        note += (f" The calendar {how} on a {kind}, {yeas} "
                 f"yea{'' if yeas == 1 else 's'} to {nays} nay{'' if nays == 1 else 's'}.")
    if removed:
        pretty = ", ".join(re.sub(r"^([A-Z]+)(\d)", r"\1 \2", b)
                           for b in sorted(removed, key=BO.bill_key))
        note += (f" {pretty} {'was' if len(removed) == 1 else 'were'} taken off "
                 "the calendar.")
    H = ['<section class="sday"><h2>On the consent calendar</h2>'
         f'<p class="note">{esc(note)}</p>']
    for label in sorted(groups):
        # By number as bills.html lists them; as text, SB 16 followed SB 133.
        items = sorted(groups[label], key=lambda x: BO.bill_key(x.bill))
        H.append(f'<div class="scons"><h3 class="slab">{esc(label)} '
                 f'&mdash; {len(items)}</h3><ul class="sconslist">')
        for i in items:
            num = re.sub(r"^([A-Z]+)(\d)", r"\1 \2", i.bill)
            ti = titles.get((i.term, i.bill)) or ""
            H.append("<li>" + bill_link(i.term, i.bill, num, years, esc, "cbn")
                     + (f'<span class="cbt">{esc(ti)}</span>' if ti else "")
                     + "</li>")
        H.append("</ul></div>")
    H.append("</section>")
    return "".join(H)


def day_parts(day, narrative):
    """(removed, seq_items, cons): the bills the journal says came off the
    day's consent calendar (journal_days.taken_off), and the day split into
    its sequence and its consent list (Day.split). render() draws the page
    from these and day_record() writes the term file from them: one reading
    of the day for both."""
    removed = journal_days.taken_off(
        narrative, {i.bill for i in day.items if i.consent or came_off_in_line(i)})
    seq_items, cons = day.split(removed)
    return removed, seq_items, cons


def render(day, narrative, titles, years, members, esc, chair=None):
    """The day, as HTML. `chair` heads a printed debate's turns in the chair
    (_debate_html); without it they are printed as the journal heads them."""
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
    # The bills the journal says came off the consent calendar. A removal it
    # prints outside the calendar's own segment counts only for a bill the
    # record has on this day's list: journal_days.taken_off says why.
    removed, seq_items, cons = day_parts(day, narrative)
    attrs = clerk_counts(attrs, [it for it in seq_items if not it.entered
                                 and getattr(it, "added", "") != "rollcall"])

    H.append(opening_html(narrative, body, members, esc))
    H.append(absences_html(narrative, body, members, esc))
    H.append(consent_html(cons, removed, titles, years, esc,
                          calendar=calendar_vote(cons)))

    drawn = set()
    # A sitting whose every vote was on no bill -- the House's organisation
    # days, which adopted its rules by roll call -- has no motions to list.
    if day.ordered and seq_items:
        H.append('<section class="sday"><h2>The day in order</h2>')
    elif seq_items:
        H.append('<section class="sday"><h2>What the '
                 f'{CHAMBER[body]} did that day</h2>'
                 '<p class="note">The record does not say what order these '
                 "came in: the journal page is cited on only a few of them, "
                 "so they are listed by bill.</p>")
    groups = speech_groups(seq_items)
    shared_out = collections.defaultdict(list)
    known = collections.defaultdict(set)
    for it in seq_items:
        known[groups[id(it)]] |= _known(it)
        if not it.entered and getattr(it, "added", "") != "rollcall":
            shared_out[groups[id(it)]].append(it)
    unsure = {g: ambiguous_tallies(its) for g, its in shared_out.items()}
    told = set()
    for bill, items in runs(seq_items):
        term = items[0].term
        href = bill_href(term, bill, years)
        ti = titles.get((term, bill)) or ""
        num = re.sub(r"^([A-Z]+)(\d)", r"\1 \2", bill)
        # WHAT WAS DONE IN RECESS TAKES NO PART IN THE DAY'S DEBATE. The
        # journal prints it with no speaker -- "Rep. Almy moved that the House
        # accede. Adopted." -- so the speeches the journal gives the bill that
        # day are the sitting's own motions', and a recess row neither claims
        # them nor counts as a second motion that leaves them unplaced. Before
        # this, SB 389's accession on 15 May 2014 took five speeches made on
        # its floor amendments, and SB 148's on 5 June 2013 pushed Reps.
        # O'Brien and Tucker off the roll call they spoke on.
        own = [it for it in items if not it.entered
               and getattr(it, "added", "") != "rollcall"]
        H.append('<article class="sitem">')
        H.append("<h3>" + bill_link(term, bill, num, years, esc, "sbill")
                 + (f'<span class="sbt">{esc(ti)}</span>' if ti else "") + "</h3>")

        for it in items:
            H.append('<div class="smotion">')
            moved = (f' <span class="smover">moved by '
                     f'{member_html(body, it.mover.replace("Rep. ", "")
                                   .replace("Sen. ", ""), members, esc)}</span>'
                     if it.mover else "")
            H.append(_question_html(it, moved, esc))
            # BUSINESS DONE IN RECESS is on the sitting the journal prints it
            # with (session_days.recess_sitting), and the bill's own history
            # keeps the day the docket entered it. Said here, so the two
            # dates read as one fact rather than as a contradiction. "Recess"
            # only where the docket says it: a row placed by the journal it
            # cites may be one entered late from the sitting itself.
            if it.entered:
                where = ("Done in the recess of this session day" if it.recess
                         else "Printed in the journal with this session day")
                H.append(f'<p class="swho">{where}, '
                         "and entered in the docket on "
                         f"{esc(words(it.entered))}, the date the bill&rsquo;s "
                         "own history gives it.</p>")
            elif getattr(it, "added", "") == "rollcall":
                # NO DEBATE AND NO SPEAKER FOR A VOTE THE DOCKET DOES NOT
                # STATE: the roll-call file records the question and the
                # ballots, and that is all the page says of it.
                H.append(ROLLCALL_ONLY)
            else:
                grp = groups[id(it)]
                mine, _rest = speakers_for(attrs, bill, it,
                                           sole=(len(shared_out[grp]) == 1),
                                           ambiguous=unsure.get(grp, frozenset()))
                for side, label in (("for", "Spoke for the motion"),
                                    ("against", "Spoke against the motion")):
                    who = mine[side]
                    if who:
                        H.append(f'<p class="sspoke"><span class="slab">{label}'
                                 "</span>"
                                 + members_row(body, who, members, esc) + "</p>")
            p = vote_payload(it)
            if p:
                i = len(payloads)
                payloads.append(p)
                kindw = esc(it.kind_words or "vote")
                H.append(f'<div class="svote" data-vote="{i}">'
                         f'<p class="stally">A {kindw}: '
                         f'<b>{it.yeas}</b> yeas, <b>{it.nays}</b> nays.</p></div>')
                if (getattr(it, "shared", 0) or 0) > 1:
                    H.append(f'<p class="swho">One {kindw} on {it.shared} bills: the '
                             "same vote is drawn under each of them, and counted "
                             "once.</p>")
                elif it.kind == "RC" and href and _ballots_here(it):
                    H.append('<p class="swho">Who voted which way is on '
                             f'<a href="{esc(href)}">'
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
        grp = groups[id(items[0])]
        if own and grp not in told:
            told.add(grp)
            names = unplaced(attrs, bill, shared_out[grp],
                             unsure.get(grp, frozenset()), known=known[grp])
            if names:
                H.append('<p class="sspoke sother"><span class="slab">Also '
                         "spoke during this bill</span>"
                         + members_row(body, names, members, esc)
                         + '<span class="snote">the record does not say which '
                           "of the day's motions</span></p>")

        # The debate the House voted to keep, under the bill it belongs to --
        # ONCE. A bill can hold the floor twice in a day with other business
        # between: HB 396 was vetoed at page 12, reconsidered at 38 and voted
        # again at 42, which is two runs, and the debate printed for it was
        # drawn under both. There is one debate; it goes under the first run
        # the sitting itself took up, and never under recess business alone.
        d = debates.get(base_bill(bill))
        if d and d["speeches"] and own and id(d) not in drawn:
            drawn.add(id(d))
            H.append(_debate_html(d, body, members, esc, chair=chair))
        H.append("</article>")
    if seq_items:
        H.append("</section>")
    H.append(others_html(getattr(day, "others", ()), body, members, esc, payloads))

    # Debates whose bill is not among the day's actions -- a motion to print
    # can name a bill the House took no recorded vote on that day -- or is
    # there only for what was done in the sitting's recess.
    seen = {base_bill(b) for b, its in runs(seq_items)
            if any(not it.entered for it in its)}
    loose = [d for k, d in debates.items() if k and k not in seen and d["speeches"]]
    if loose:
        H.append('<section class="sday"><h2>Also printed in the permanent '
                 "journal</h2>")
        for d in loose:
            H.append(_debate_html(d, body, members, esc, head=True, chair=chair))
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


def _debate_html(d, body, members, esc, head=False, chair=None):
    """A printed debate: the opening, and the rest behind a disclosure.

    They run long -- 5,507 speeches across 298 debates -- so the page shows
    enough to know what it is and opens on request.

    THE CHAIR BY THE OFFICE THEY HELD THAT DAY (the person, 9 October 2026:
    "he is the deputy speaker and sometimes fills in for Sherman Packard").
    The journal heads whoever is in the chair "Speaker", so the Deputy
    Speaker was printed "Speaker Steven Smith". `chair` is
    officers.chair_label for the day: the Speaker's heading stands, and
    anyone else in the chair is "Deputy Speaker Steven Smith" where the
    record gives them the office and "Rep. Kofalt, in the chair" where it
    does not. Without it the headings are printed as the journal has them.
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
        said_by = chair(who) if chair else who
        link = (f"<span>{esc(said_by)}</span>" if said_by != who
                else member_html(body, nm, members, esc)
                if not who.lower().startswith("speaker")
                else f"<span>{esc(who)}</span>")
        out.append(f'<p class="sdsp">{link}<span class="sdtx">{esc(said)}</span></p>')
    out.append("</div></details>")
    return "".join(out)


def sittings(days=None, today=None):
    """(built, later): the (body, date) of every sitting a page is written
    for, and of those after today, which get none. Both sorted.

    A SITTING CANNOT BE AFTER THE BUILD. The Senate enters floor rows up to
    ten days before the sitting they belong to, and a mistyped month put a
    House sitting a month ahead of veto day; neither is a day to publish.

    ONE RULE, ASKED BY EVERYTHING THAT LINKS A SITTING. This step runs after
    the home page and the directory's lists are written, so on a machine that
    starts empty neither can read the pages off the disk: build_pages.py and
    build_indexes.py ask this instead, and link the days it says are built.
    """
    days = session_days.load() if days is None else days
    today = today or build_date.today().isoformat()
    return (sorted(k for k in days if k[1] <= today),
            sorted(k for k in days if k[1] > today))


# THE WAY UP. A sitting's page led to the sittings either side of it, to the
# bills and to the members, and to nothing above itself: no list of sittings
# and not its week on the Calendar, though that is the tab it is marked
# under (the audit of 2 October 2026, B3). The list is build_indexes.py's,
# one per chamber, with a heading for each year.
DAYS_LIST = {"H": "directory/sessions-house.html",
             "S": "directory/sessions-senate.html"}


def calendar_weeks(site):
    """{"2026-W21", ...}: the weeks build_calendar.py will write a page for.

    Asked of the calendar's own functions and not read off the disk: that
    step runs after this one, so on a machine that starts empty there is no
    week to find yet. The calendar starts in 2025; a sitting before its
    first week has no week to lead up to, and leads to the list alone.
    Nothing here if the calendar's rows cannot be read: the list still stands.
    """
    import contextlib
    import io
    try:
        import build_calendar as BC
        with contextlib.redirect_stdout(io.StringIO()):
            return BC.week_keys(site)
    except Exception as e:   # an addition: the page stands without it
        print(f"  WARNING: the calendar's weeks could not be read ({e!r}); "
              "no sitting links its week")
        return set()


def up_links(body, date, weeks):
    """The links above a sitting, in the order the line above its heading
    gives them: the chamber's list, at the sitting's year, and its week on
    the Calendar where the calendar has that week."""
    y, m, d = (int(x) for x in date.split("-"))
    iso = datetime.date(y, m, d).isocalendar()
    wk = f"{iso[0]}-W{iso[1]:02d}"
    out = [f'<a href="{S.canon(DAYS_LIST[body])}#y{y}">'
           f"Every {CHAMBER[body]} session day</a>"]
    if wk in weeks:
        out.append(f'<a href="{S.canon(f"calendar/{wk}.html")}">'
                   "That week on the Calendar</a>")
    return out


def write_days_index(site, body, dates):
    """site/session/days.json: {"H": [dates], "S": [dates]}, this chamber's
    list replaced and the other's kept.

    WHAT app.js ASKS BEFORE IT LINKS A DATE. A roll call on a bill and a row
    of a member's votes name a day and a chamber, and the sitting's page is
    session/<H|S>/<date> -- where there is one. This is the list of the ones
    there are, written by the step that writes them, so a date is linked only
    to a page that was built. Each run writes one chamber; the other's list
    is the other run's, and is left as it was.
    """
    f = site / "session" / "days.json"
    try:
        had = json.loads(f.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        had = {}
    had = {k: v for k, v in had.items() if k in CHAMBER and isinstance(v, list)}
    had[body] = sorted(dates)
    f.write_text(json.dumps(had, separators=(",", ":"), sort_keys=True),
                 encoding="utf-8")
    return f


# ------------------------------------------------------- the day as data --
#
# THE CHAMBER'S SESSION DAYS AS DATA, ONE FILE A TERM: site/session/<H|S>/
# <term>.json, written beside the day's pages by the run that writes them.
# What the next pages of a session day are drawn from, decided here once
# rather than by each page (the component plan's C4, approved 9 October
# 2026), out of the same model of the day this step draws its page from:
#
#   every day the chamber sat that term, with its journal and its counts,
#     for the House and Senate full sessions at the top of the Committees
#     page, a reader going through them as a committee page shows its
#     meetings (the person, 9 October 2026, v12 and v13);
#   each day's members excused, counted by party (v16); the members who
#     presided over the chamber that day, as a list and not bill by bill
#     (v18: "a general line naming the members who presided ... they switch
#     back and forth"); and the consent calendar's outcomes with the bills
#     each took, and the bills taken off it (item 18);
#   and every bill the chamber voted on that day, with every vote on it
#     that day in order -- the motion, its amendment numbers, the result,
#     the count, and the roll call's id and the place of its card on the
#     bill's Votes tab, so that the vote display the Votes tab draws is the
#     one used (v2) -- and the committee recommendation the floor acted on
#     (v15).
#
# THE AMENDMENTS ARE THE DOCKET'S, NOT ONLY THE ROLL CALLS. The sitting model
# draws a floor motion and every roll call on record, an amendment's among
# them, and no amendment voted by voice or division: the House's day of
# 19 February 2026 draws none, where its bills' dockets record nineteen,
# three of them divisions (HB 1811-FN's committee amendment failed 166-171,
# HB 1775's adopted 178-145, HB 1492's adopted 315-25 -- the second-round
# prototype's finding, 9 October 2026). They are read here from each bill's
# own rows and put among its motions where the docket enters them. The
# day's `counts` stay the page's own -- the motions it draws, each counted
# vote once -- and `amendment_votes` counts what the bills' entries add, so
# the two can be told apart and added up.

# What the site data step knows of the floor that only the ballots and the
# bills' Votes tabs say: who presided over each roll call, and where each
# roll call's card is on its bill's Votes tab (build_site_v2.
# write_floor_record). Not published: everything a page needs of it is in
# the files below.
FLOOR_RECORD = Path("data") / "floor_record.json"
TERM_FILE = re.compile(r"\d{4}-\d{4}")
HOW = {"RC": "roll call", "DV": "division", "VV": "voice vote"}
PARTY_LETTER = {"republican": "R", "democrat": "D", "democratic": "D",
                "independent": "I", "libertarian": "L"}


def party_letter(p):
    """"Republican" (the sitting roster) and "R" (a former member's) alike."""
    s = (p or "").strip()
    return PARTY_LETTER.get(s.lower(), s[:1].upper())


def rollcall_id(rc):
    """"2026-H-95": the roll-call file's own name for a roll call, the key of
    rollcalls_index.json and the roll_call column of data/rollcalls.csv."""
    return f"{rc.get('year')}-{rc.get('body')}-{rc.get('number')}" if rc else None


def floor_record(path=FLOOR_RECORD):
    """{"presiding": {roll call: [[member id, label], ...]}, "cards": {term:
    {bill: {roll call: card}}}}; empty where the site data step wrote none,
    and said, because every day would then name nobody presiding."""
    try:
        got = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print(f"  WARNING: {path} is not here or will not read: no day names who "
              "presided, and no roll call names its card on its bill's Votes tab")
        got = {}
    return {"presiding": got.get("presiding") or {}, "cards": got.get("cards") or {}}


def published_officers(site):
    """site/officers.json's tenures (build_site_v2.build_officers), or []."""
    try:
        return json.loads((Path(site) / "officers.json").read_text(
            encoding="utf-8")).get("officers") or []
    except (OSError, ValueError):
        print("  WARNING: site/officers.json is not here: no one presiding is "
              "named by their office")
        return []


def load_numbers(site):
    """{(term, bill): "HB 1705-FN"}: each bill's number as its card prints
    it, suffix kept, from the term indexes load_titles reads."""
    out = {}
    for f in sorted((Path(site) / "idx").glob("*.json")):
        try:
            rows = json.loads(f.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        for b in rows if isinstance(rows, list) else ():
            if b.get("id") and b.get("n"):
                out[(b.get("term") or f.stem, b["id"])] = b["n"]
    return out


AMENDMENT_NUMBER = re.compile(r"\b(\d{4}-\d{3,4}[a-z]?)\b|\{(\d{3,4})\}|#\s*(\d{3,4}[a-z]?)\b(?!-)")


def amendment_numbers(text):
    """Every amendment a motion's words name, in order: "2026-0531h", the
    1999-2006 clerk's "{1066}", "#0026h". Not the year of "# 2026-1709s"
    on its own."""
    out = []
    for m in AMENDMENT_NUMBER.finditer(text or ""):
        x = next(g for g in m.groups() if g)
        if x not in out:
            out.append(x)
    return out


def item_vote(it, cards):
    """One motion of the day, as data. `result` is the clerk's -- MA, or MF
    and ML -- never the larger number (vote_payload); `did` is what carrying
    or failing did to the bill, where session_days can say; `card` the
    place of the roll call's card on the bill's Votes tab (`cards`)."""
    v = {"motion": it.action or "",
         "result": None if it.carried is None else ("adopted" if it.carried else "failed")}
    amds = amendment_numbers(it.action)
    if amds:
        v["amendments"] = amds
    if it.mover:
        v["mover"] = it.mover
    if HOW.get(it.kind):
        v["how"] = HOW[it.kind]
    if it.counted:
        v["yeas"], v["nays"] = it.yeas, it.nays
        v["threshold_needed"] = it.threshold_needed
        if it.threshold_unknown:
            v["threshold_unknown"] = True
    rid = rollcall_id(it.rc)
    if rid:
        v["rollcall"] = rid
        if rid in cards:
            v["card"] = cards[rid]
    if (getattr(it, "shared", 0) or 0) > 1:
        v["shared"] = it.shared
    if it.consent:
        v["consent"] = True
    if it.entered:
        v["entered"] = it.entered
        if it.recess:
            v["recess"] = True
    if getattr(it, "added", "") == "rollcall":
        v["docket"] = False
    did = None if it.plain else session_days._consequence(it.action, it.carried, it.law,
                                                           it.overturned)
    if did:
        v["did"] = did
    return v


def amendment_vote(e):
    """An amendment its own docket row says was voted by voice or division,
    as data, worded as the bill's Votes tab words one (build_site_v2.
    bill_rollcalls) with the docket's own kind beside it ("Minority
    Amendment", "Enrolled Bill Amendment"); None where the row records no
    vote. A roll call on an amendment is the sitting model's already."""
    k = (e.get("amend_kind") or "").lower()
    result = session_days.amendment_carried(e)
    y, n = e.get("yeas"), e.get("nays")
    counted = str(y or "").strip().isdigit() and str(n or "").strip().isdigit()
    if result is None and not counted:
        return None
    vk = (e.get("vote_kind") or "").strip().upper().rstrip(".")
    vk = "DV" if vk in ("DV", "DIV") else vk
    v = {"motion": ("Adopt Floor Amendment" if "floor" in k
                    else "Adopt Committee Amendment" if "committee" in k
                    else "Adopt Amendment"),
         "result": None if result is None else ("adopted" if result else "failed"),
         "amendment_kind": (e.get("amend_kind") or "").strip()}
    num = (e.get("amendment") or "").strip()
    if num:
        v["amendments"] = [num]
    if (e.get("mover") or "").strip():
        v["mover"] = e["mover"].strip()
    if HOW.get(vk):
        v["how"] = HOW[vk]
    if counted:
        v["yeas"], v["nays"] = int(y), int(n)
        v["threshold_needed"] = (int(y) + int(n)) // 2 + 1
    if e.get("part"):
        v["part"] = e["part"]
    return v


def amendments_on_sittings(days, data, body):
    """({sitting: {(term, bill): [(seq, event)]}}, [rows no sitting holds]):
    each amendment row of the chamber not voted by roll call, on the sitting
    it belongs to -- the one the sitting model put the bill's floor rows of
    that docket day on (a row done in the recess of an earlier sitting
    takes its amendments with it), else its own day where the chamber sat
    then, else the sitting the row says it was done in the recess of.
    `seq` is its place in its bill's docket in the model's terms (Item.seq,
    session_days.load's `base`), so it sorts among the bill's motions."""
    moved = {}
    for (b, date), d in days.items():
        if b == body:
            for it in d.items:
                moved[(it.term, it.bill, it.entered or date)] = date
    base = getattr(days, "base", None) or {}
    out = collections.defaultdict(lambda: collections.defaultdict(list))
    lost = []
    for term, bills in data.items():
        for bill, rec in bills.items():
            if (term, bill) not in base:
                continue
            for n, e in enumerate(rec.get("events") or []):
                if (e.get("type") != "amendment" or e.get("cancelled")
                        or (e.get("body") or "").strip().upper() != body
                        or (e.get("vote_kind") or "").strip().upper() == "RC"):
                    continue
                day = (e.get("date") or "")[:10]
                at = moved.get((term, bill, day))
                if at is None and (body, day) in days:
                    at = day
                if at is None:
                    rs = session_days.recess_sitting(e)
                    at = rs if rs and (body, rs) in days else None
                if at is None:
                    lost.append((term, bill, day))
                    continue
                out[at][(term, bill)].append((base[(term, bill)] + n, e))
    return out, lost


def bill_votes(items, amendments, cards):
    """A bill's votes of the day in order: its motions as the day draws
    them, and each amendment row before the first motion its docket enters
    after it."""
    votes = [(it.seq, item_vote(it, cards)) for it in items]
    for seq, e in sorted(amendments, key=lambda x: x[0]):
        v = amendment_vote(e)
        if v is None:
            continue
        at = next((i for i, (s, _v) in enumerate(votes) if s > seq), len(votes))
        votes.insert(at, (seq, v))
    return [v for _s, v in votes]


# A motion that disposes of a committee's report: the chamber passing,
# killing, studying or re-referring the bill on it. A tabling, a special
# order or a reconsideration leaves the report before the chamber.
DISPOSES = re.compile(r"^\s*(?:ought\s+to\s+pass|inexpedient|indefinitely\s+postpone|"
                      r"(?:re-?)?refer(?:red)?\s+(?:for|to)\s+interim\s+study|"
                      r"interim\s+study|re-?\s*refer|recommit)", re.I)


def recommendation_on(acts, body, date, floor):
    """The committee recommendation the chamber acted on that day: the
    latest report of the chamber's committees (committee_acts.acts) the
    docket enters on or before the day, where no sitting since that entry
    disposed of the bill on it (`floor`: the bill's [(sitting, Item)] in
    this chamber). None where there is none: HB 1525 of 2026's report is
    entered on 22 February, three days after the House killed the bill (the
    second-round prototype's finding 3, 9 October 2026), and a concurrence
    months after the chamber passed a bill is no vote on its committee's
    report."""
    reps = [a for a in acts if a["act"] == "report" and a["body"] == body
            and a["entered"] <= date]
    if not reps:
        return None
    r = reps[-1]
    if any(r["entered"] <= s < date and it.carried
           and (it.consent or DISPOSES.match(it.action or "")) for s, it in floor):
        return None
    return {k: v for k, v in CA.public(r).items() if k != "act"}


# THE SECOND COMMITTEE, as the docket refers a bill on to it: the House's own
# row ("Referred to Finance 02/19/2026", 1989-2006's "RE-REFERRED TO WAYS AND
# MEANS"), and the Senate's clause in the line of the vote that passed it
# ("Ought to Pass: MA, VV; Refer to Finance Rule 4-5; 05/07/2026", the older
# "PASSED/ADOPTED WITH AM, REF TO FINANCE (RULE #24)"). Not a referral for
# interim study, and not a motion to refer that is itself the question.
SECOND_COMMITTEE = re.compile(r"\bre-?\s*ref(?:er(?:red)?)?\.?\s+to\s+(?:the\s+)?"
                              r"(?P<c>finance|ways\s+and\s+means|w\s*&\s*m)\b"
                              r"|\bref(?:er(?:red)?)?\.?\s+to\s+(?:the\s+)?"
                              r"(?P<d>finance|ways\s+and\s+means|w\s*&\s*m)\b", re.I)
WAIVED = re.compile(r"\breferral\s+waived|\bwaived\s+(?:second\s+committee\s+)?referral", re.I)


def referral_on(events, body, docket_days):
    """{"referred": "Finance"} where the docket refers the bill on to Finance
    or Ways and Means on one of `docket_days`, and {"referral_waived": True}
    where it says that referral was waived (House Rule 47(f)): the vote
    words' row 1a, "Motion Passed: Sent to Finance", turns on it, and is
    "not the 93 bill-days whose docket says the referral was waived"."""
    out = {}
    for e in events or ():
        if e.get("cancelled") or (e.get("body") or "").strip().upper() != body \
                or (e.get("date") or "")[:10] not in docket_days:
            continue
        raw = e.get("raw") or ""
        m = SECOND_COMMITTEE.search(raw)
        if m and not re.search(r"interim\s+study", raw, re.I) and (
                e.get("type") == "rereferred"
                or (e.get("type") == "floor" and m.start() > 0
                    and session_days.CARRIED.get((e.get("motion") or "").strip().upper()))):
            c = (m.group("c") or m.group("d")).lower()
            out["referred"] = "Finance" if c.startswith("fin") else "Ways and Means"
        if WAIVED.search(raw):
            out["referral_waived"] = True
    return out


# A turn the House Journal gives the chair in a printed debate: "Speaker
# Packard:", "Speaker Steven Smith:", "Deputy Speaker Steven Smith:".
CHAIR_TURN = re.compile(r"^(?:Deputy\s+Speaker|Speaker\s+Pro\s+Tem(?:pore)?|Speaker)\s+"
                        r"(?P<n>(?!Pro\s+Tem)\S.*)$")


def office_on(offices, body, date, mid):
    """The office officers.json gives member `mid` of `body` on the day, or
    "": the record's, never inferred from who presided."""
    for t in offices:
        if (t.get("b") == body and str(t.get("id")) == str(mid)
                and t.get("from", "") <= date < t.get("to", "")):
            return t.get("office") or ""
    return ""


def presiding_on(day, narrative, presided, members, offices):
    """The members who presided over the chamber that day, from the record:
    each that a roll call's "Presiding" ballot names, with how many roll
    calls (`roll_calls`), in the order they first took the chair; then each
    the journal heads a turn in the chair of a printed debate with
    ("Speaker Steven Smith:") who is on no such ballot (`journal`). Each
    with the office officers.json gives them that day, or none -- a member
    in the chair. The Senate records its President presiding on few ballots
    (attendance_context), so most Senate days name nobody: the record does
    not say, and this does not guess."""
    out, seen = [], {}
    rcs = {}
    for it in list(day.items) + list(day.others):
        rid = rollcall_id(it.rc)
        if rid and rid not in rcs:
            rcs[rid] = int(it.rc.get("number") or 0)
    for rid in sorted(rcs, key=lambda r: (rcs[r], r)):
        for mid, label in presided.get(rid) or ():
            if mid not in seen:
                who = members.by_id.get(mid) or {}
                seen[mid] = {"id": mid, "slug": who.get("slug") or "",
                             "label": label or who.get("label") or "",
                             "party": who.get("party") or "", "roll_calls": 0}
                off = office_on(offices, day.body, day.date, mid)
                if off:
                    seen[mid]["office"] = off
                out.append(seen[mid])
            seen[mid]["roll_calls"] += 1
    by_slug = {x["slug"]: x for x in out if x["slug"]}
    for d in narrative.get("debates") or ():
        for who, _said in d.get("speeches") or ():
            m = CHAIR_TURN.match(who or "")
            slug = members.slug(day.body, m.group("n")) if m else None
            if not slug:
                continue
            if slug in by_slug:
                by_slug[slug]["journal"] = True
                continue
            info = members.by_slug.get(slug) or {}
            x = {"id": info.get("id") or "", "slug": slug, "label": info.get("label") or "",
                 "party": info.get("party") or "", "roll_calls": 0, "journal": True}
            off = office_on(offices, day.body, day.date, x["id"])
            if off:
                x["office"] = off
            by_slug[slug] = x
            out.append(x)
    return out


def excused_on(narrative, body, members):
    """The members the journal excused for the day, counted by party: each
    name read as the member serving that term it can only mean (Members),
    with the party their record gives; `unmatched` the names that are no one
    member's. The names absences_html lists, once each. None where the
    journal excused nobody, or is not on disk for the day."""
    names, seen = [], set()
    for r in narrative.get("absences") or ():
        for nm in r.get("names") or ():
            if nm.lower() not in seen:
                seen.add(nm.lower())
                names.append(nm)
    if not names:
        return None
    parties, unmatched = collections.Counter(), 0
    for nm in names:
        slug = members.slug(body, nm)
        p = (members.by_slug.get(slug) or {}).get("party") if slug else ""
        if p:
            parties[p] += 1
        else:
            unmatched += 1
    return {"total": len(names), "by_party": dict(sorted(parties.items())),
            "unmatched": unmatched}


def consent_on(cons, removed):
    """The consent calendar as data: its outcomes, each with the bills it
    took, in consent_html's words and order; the bills taken off it; and
    its counted vote where the chamber counted it. None where there was no
    calendar."""
    if not cons and not removed:
        return None
    groups = collections.Counter(short_outcome(i) for i in cons)
    return {"bills": len({(i.term, i.bill) for i in cons}),
            "outcomes": [{"outcome": k, "bills": groups[k]} for k in sorted(groups)],
            "removed": sorted({str(b).split("-")[0].upper() for b in removed},
                              key=BO.bill_key),
            "votes": [{"how": kind, "yeas": y, "nays": n,
                       "result": None if c is None else ("adopted" if c else "failed")}
                      for kind, y, n, c in calendar_vote(cons)]}


def day_record(day, narrative, jurl, ctx):
    """One sitting as data, for its chamber's term file. `ctx` carries what
    the run read once: members, numbers, years, amendments (by sitting),
    cards, presided, offices, acts (by bill), floor (by bill), data."""
    removed, seq_items, cons = day_parts(day, narrative)
    off = {str(b).split("-")[0].upper() for b in removed}
    seq_keys = [(it.term, it.bill) for it in seq_items]
    cons_keys = {(i.term, i.bill) for i in cons}
    order = list(dict.fromkeys(seq_keys + sorted(cons_keys - set(seq_keys),
                                                 key=lambda k: (BO.bill_key(k[1]), k[0]))))
    amds = ctx["amendments"].get(day.date) or {}
    order += sorted((k for k in amds if k not in set(order)),
                    key=lambda k: (BO.bill_key(k[1]), k[0]))
    added = collections.Counter()
    bills = []
    for term, bill in order:
        items = [it for it in day.items if (it.term, it.bill) == (term, bill)]
        votes = bill_votes(items, amds.get((term, bill), ()),
                           ctx["cards"].get(term, {}).get(bill, {}))
        for v in votes:
            if "amendment_kind" in v:
                added[v.get("how") or "not stated"] += 1
        if not votes:
            continue
        entry = {"bill": bill, "term": term, "year": ctx["years"].get((term, bill)) or "",
                 "n": ctx["numbers"].get((term, bill)) or re.sub(r"^([A-Z]+)(\d)", r"\1 \2", bill),
                 "consent": (term, bill) in cons_keys and (term, bill) not in set(seq_keys)}
        if bill.upper() in off:
            entry["removed"] = True
        if not items:
            entry["amendments_only"] = True
        entry["votes"] = votes
        rec = recommendation_on(ctx["acts"](term, bill), day.body, day.date,
                                ctx["floor"].get((term, bill), ()))
        if rec:
            entry["recommendation"] = rec
        entry.update(referral_on(((ctx["data"].get(term) or {}).get(bill) or {}).get("events"),
                                 day.body, {it.entered or day.date for it in items} or {day.date}))
        bills.append(entry)
    k = day.counts()
    return {"date": day.date, "journal": day.journal or "", "journal_url": jurl or "",
            "ordered": bool(day.ordered),
            "counts": {"bills": len(day.bills), "actions": len(day.items),
                       "roll_calls": k.get("roll call", 0), "divisions": k.get("division", 0),
                       "voice_votes": k.get("voice vote", 0),
                       "debates": len(narrative.get("debates") or [])},
            "amendment_votes": {"divisions": added["division"],
                                "voice_votes": added["voice vote"],
                                "not_stated": added["not stated"]},
            "presiding": presiding_on(day, narrative, ctx["presided"], ctx["members"],
                                      ctx["offices"]),
            "excused": excused_on(narrative, day.body, ctx["members"]),
            "consent": consent_on(cons, removed),
            "bills": bills}


TERM_ABOUT = (
    "One chamber's session days of one term, oldest first, each as its own page draws it "
    "(session/<H|S>/<date>.html), from the docket, the journals and the roll calls. counts: "
    "the page's own count of the bills taken up, the motions it draws and each counted vote "
    "once; amendment_votes: the amendments voted by voice or division that the bills' "
    "entries add from their dockets. presiding: who a roll call's Presiding ballot or a "
    "journal's turn in the chair names, with the office the record gives them that day. "
    "excused: the journal's names counted by the party of the member each can only mean. "
    "consent: the calendar's outcomes, the bills taken off it and its counted vote. bills: "
    "every bill voted on that day, each vote in order (rollcall is the roll-call file's id; "
    "card is the vote's place on the bill's Votes tab), and the committee recommendation "
    "the chamber acted on.")


def write_term_records(site, body, records):
    """site/session/<body>/<term>.json for each term in `records`, and none
    left for a term this run holds no day of. Written only for the whole
    chamber: a run cut short by --limit writes none."""
    folder = Path(site) / "session" / body
    wrote = set()
    for term in sorted(records):
        f = folder / f"{term}.json"
        f.write_text(json.dumps({"_about": TERM_ABOUT, "body": body, "term": term,
                                 "days": sorted(records[term], key=lambda d: d["date"])},
                                separators=(",", ":")), encoding="utf-8")
        wrote.add(f.name)
    for f in sorted(folder.glob("*.json")):
        if TERM_FILE.fullmatch(f.stem) and f.name not in wrote:
            f.unlink()
    return sorted(wrote)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    ap.add_argument("--base", default="https://graniterecord.org")
    ap.add_argument("--body", default="H",
                    help="H or S. A Senate page carries the record and who was "
                         "excused: its journal records no speakers")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--prune", action="store_true",
                    help=f"remove more than {PRUNE_CEILING} pages of sittings "
                         "the record no longer holds; without it a larger "
                         "removal is refused")
    a = ap.parse_args()
    site, base = Path(a.site), a.base.rstrip("/")
    body = a.body.strip().upper()

    days = session_days.load()
    today = build_date.today().isoformat()
    built, later = sittings(days, today)
    ahead = [k for k in later if k[0] == body]
    mine = [k for k in built if k[0] == body]
    if ahead:
        print(f"  {len(ahead)} {CHAMBER[body]} day(s) after today not built: "
              + ", ".join(k[1] for k in ahead))
    # SILENCE IS NOT SUCCESS: no days is a Calendar linking at nothing, and a
    # build that said so by printing a zero.
    assert mine, f"no {CHAMBER.get(body, body)} sitting days in narratives.json"
    # A ROLL CALL ON NO PAGE IS SAID, with why: the night a roll call arrives
    # before the docket's rows for its sitting shows here, not only in the
    # data check that holds each to a named reason.
    left = [(r, why) for r, why in days.left if r.get("body") == body]
    if left:
        why = collections.Counter(w.split(",")[0] for _r, w in left)
        print(f"  {len(left)} {CHAMBER[body]} roll call(s) on record drawn on no "
              "sitting page, the latest of " + max(r["date"] for r, _w in left)
              + ": " + "; ".join(f"{n} {w}" for w, n in sorted(why.items())))

    titles, years = load_titles(site)
    members = Members(site)
    # WHO HELD THE CHAIR'S OFFICES, read from the journals and calendars on
    # disk (officers.py), for the headings of the turns the chair takes in
    # a printed debate. The House's alone: the Senate's pages print none.
    tenures = officers.load()[0] if body == "H" else []
    # THE CHAMBER'S DAYS AS DATA, a file a term (write_term_records), from
    # what this run reads once: the bills' histories, for each bill's
    # amendments, reports and referrals; what the site data step wrote of the
    # ballots (floor_record); the officers' tenures; the bills' numbers.
    data = json.loads(Path(session_days.NARRATIVES).read_text(encoding="utf-8"))
    amendments, unplaced_amendments = amendments_on_sittings(days, data, body)
    fr = floor_record()
    floor = collections.defaultdict(list)
    for (b_, d_), day_ in days.items():
        if b_ == body:
            for it in day_.items:
                floor[(it.term, it.bill)].append((d_, it))
    acts_cache = {}

    def acts_of(term, bill):
        if (term, bill) not in acts_cache:
            acts_cache[(term, bill)] = CA.acts(
                ((data.get(term) or {}).get(bill) or {}).get("events"))
        return acts_cache[(term, bill)]
    retitled = collections.Counter()
    out_dir = site / "session" / body
    out_dir.mkdir(parents=True, exist_ok=True)

    urls, wrote, with_narr, linked, unlinked = [], 0, 0, 0, 0
    records = collections.defaultdict(list)
    ctx = {"members": members, "numbers": load_numbers(site), "years": years,
           "amendments": amendments, "cards": fr["cards"], "presided": fr["presiding"],
           "offices": published_officers(site), "acts": acts_of, "floor": floor,
           "data": data}
    excused = 0
    order = mine[: a.limit] if a.limit else mine
    weeks = calendar_weeks(site)
    import queue_links as B2  # not build_site_v2: see queue_links.py
    journal_keys, jlinked = B2.journal_keys_from_queue(), 0
    for n, key in enumerate(order):
        day = days[key]
        date = day.date
        # Names are matched among the members serving this day's term
        # (Members: ONLY THE MEMBERS WHO SERVED THAT TERM COUNT).
        members.term = proceedings.vote_term(str(date)[:4], str(date))
        # THE SENATE JOURNAL IS READ FOR ONE THING: WHO WAS EXCUSED. Across
        # all 491 Senate files there are no UNANIMOUS CONSENT sections, no
        # REMARKS, no PERSONAL PRIVILEGE, and "spoke in favor" appears in three
        # files as ordinary English inside a speech. The Senate journal does
        # not record who spoke on which side, so there is nothing of that to
        # parse and the page says so instead of showing an empty section. It
        # does name the senators excused for the day, as each sitting opens,
        # and read_senate_day returns those in the shape the House's come in.
        blank = {"attributions": [], "debates": [], "unanimous_consent": []}
        if body == "S":
            narrative = journal_days.read_senate_day(date)
        elif date < JOURNAL_FROM:
            narrative = blank
        else:
            narrative = journal_days.read_day(date)
        if narrative.get("attributions") or narrative.get("debates"):
            with_narr += 1
        if any(r.get("names") for r in narrative.get("absences") or []):
            excused += 1

        for at in (narrative.get("attributions") or []):
            for nm in at["names"]:
                if members.slug(body, nm):
                    linked += 1
                else:
                    unlinked += 1
        def chair(who, _date=date):
            got = officers.chair_label(who, _date, tenures)
            if got != who:
                retitled[next((t for t in ("Deputy Speaker", "Speaker Pro Tempore")
                               if got.startswith(t)), "a member in the chair")] += 1
            return got
        block, payloads = render(day, narrative, titles, years, members, S.E,
                                 chair=chair if tenures else None)
        label = f"The {CHAMBER[body]}, {words(date)}"
        lead = _lead(day, narrative, date, body)
        prev_ = order[n - 1][1] if n > 0 else ""
        next_ = order[n + 1][1] if n + 1 < len(order) else ""
        nav = []
        if prev_:
            nav.append(f'<a class="wkprev" href="{S.canon(f"session/{body}/{prev_}.html")}">'
                       f"&lsaquo; The session day before</a>")
        if next_:
            nav.append(f'<a class="wknext" href="{S.canon(f"session/{body}/{next_}.html")}">'
                       f"The session day after &rsaquo;</a>")

        # From the root, with its slash: the canonical link, the citation and
        # the sitemap are the domain joined to this.
        path = f"/session/{body}/{date}.html"
        html = S.page(S.template(site), path=path, base=base,
                      title=f"{label} | Granite Record",
                      description=(f"What the New Hampshire {CHAMBER[body]} did on "
                                   f"{words(date)}: every bill, motion and vote, "
                                   "in the order the journal records them."),
                      og_title=label, globals={"GR_STATIC": True}, noscript="",
                      skip_label="Skip to the session day", sr_title="",
                      og_type="article", nav_current="calendar.html",
                      jsonld=LD.listing(label, lead, base, S.canon(path)))
        payload = json.dumps(payloads, separators=(",", ":"))
        # THE JOURNAL ITSELF, where the record holds its address: by the
        # number this day's rows cite and never by the date alone (see
        # build_site_v2.journal_url), so a page is linked to its own journal
        # or to none.
        jurl = B2.journal_url(date, day.journal, journal_keys) if day.journal else ""
        if jurl:
            jlinked += 1
        records[members.term].append(day_record(day, narrative, jurl, ctx))
        # A journal PDF opens in a new tab, marked as going out, as the
        # Calendar's do (the person, 7 October 2026, F12: "a calendar or
        # journal PDF").
        cite = (f'<a class="jpdf out" href="{S.E(jurl)}" target="_blank" rel="noopener">'
                f'{S.E(day.journal)} (PDF)</a>' if jurl else S.E(day.journal))
        # The line up, above the heading, as a Learn article's is above its
        # own: where this page sits, as links.
        crumb = ('<p class="crumb">'
                 + " &middot; ".join(up_links(body, date, weeks)) + "</p>")
        full = ('<div id="results"><div class="wkpage sesspage">'
                + crumb
                + f"<h1>{S.E(label)}</h1>"
                + (f'<p class="src">{cite}. {S.E(lead)}</p>'
                   if day.journal else f'<p class="src">{S.E(lead)}</p>')
                + f'<nav class="wknav" aria-label="Other session days">{"".join(nav)}</nav>'
                + block
                + f'<nav class="wknav wkfoot" aria-label="Other session days">{"".join(nav)}</nav>'
                + f'<script type="application/json" id="sessvotes">{payload}</script>'
                "</div></div>")
        html = html.replace('<div id="results"></div>', full, 1)
        assert 'class="wkpage sesspage"' in html, f"{path}: no results slot"
        (site / path.lstrip("/")).write_text(html, encoding="utf-8")
        urls.append(base + S.canon(path))
        wrote += 1

    # A run cut short by --limit leaves every page it did not build, and the
    # list of the pages there are: it names the whole chamber or it is not
    # written.
    if not a.limit:
        prune(out_dir, {k[1] for k in mine}, a.prune)
        write_days_index(site, body, [k[1] for k in mine])
        # SILENCE IS NOT SUCCESS: a day drawn and not written as data would
        # be a day missing from the chamber's list with nothing to say so.
        n_rec = sum(len(v) for v in records.values())
        assert n_rec == wrote, f"{wrote} days drawn and {n_rec} written as data"
        terms_written = write_term_records(site, body, records)
        bill_days = sum(len(d["bills"]) for v in records.values() for d in v)
        added = sum(sum(d["amendment_votes"].values()) for v in records.values() for d in v)
        print(f"  {len(terms_written)} term file(s) -> site/session/{body}/<term>.json: "
              f"{n_rec:,} days, {bill_days:,} bills voted on a day, {added:,} amendment "
              "votes the pages do not draw; "
              f"{sum(1 for v in records.values() for d in v if d['presiding']):,} days name "
              f"who presided, {sum(1 for v in records.values() for d in v if d['excused']):,}"
              f" count the excused by party; {len(unplaced_amendments):,} amendment row(s) "
              "on no sitting")

    # This chamber's days only, and all of them unless --limit cut the run
    # short: a limited run takes out only entries that were never an address.
    added, dropped = S.sitemap_merge(site, base, urls, f"/session/{body}",
                                     whole=not a.limit)
    if added or dropped:
        print(f"  sitemap.xml: {added} added, {dropped} no longer written taken out")

    print(f"  {wrote:,} {CHAMBER[body]} sitting days -> site/session/{body}/")
    print(f"    {jlinked:,} link their journal PDF ({len(journal_keys):,} journals "
          "from 2025 in archive/queue.csv)")
    print(f"    {with_narr:,} carry a journal narrative "
          f"(the journal starts {JOURNAL_FROM[:4]})")
    # Printed so that none at all, which is what a moved journal folder or a
    # changed opening looks like, cannot pass as a quiet chamber.
    print(f"    {excused:,} name the members the journal excused for the day")
    if body == "H":
        # The chair by the office held that day: none at all, with the
        # journals here, is the patterns no longer reading them.
        print(f"    {sum(retitled.values()):,} turn(s) in the chair the journal heads "
              "\"Speaker\" given to someone not the Speaker that day: "
              + (", ".join(f"{n:,} {k}" for k, n in sorted(retitled.items())) or "none")
              + f" ({len(tenures)} officers' tenures read)")
    named = linked + unlinked
    if named:
        # A WRONG LINK IS WORSE THAN NO LINK, so this number is meant to be
        # short of 100% -- a surname shared by two members of the same chamber
        # is left as text. It is printed so that a drop to nothing, which is
        # what a broken index looks like, cannot pass as normal.
        print(f"    {linked:,} of {named:,} speaker mentions resolved to a "
              f"member page ({100.0 * linked / named:.0f}%)")
    return 0


# A DAY THAT STOPPED EXISTING KEEPS ITS PAGE unless this removes it. This step
# owns site/session/<body>/ and writes a page per sitting; a sitting that a
# corrected date moved away from -- "The House, Saturday 19 September 2026" --
# would otherwise stay on disk, stay deployed and stay linkable from the
# calendar, which reads the pages off the disk.
#
# AND A WRITER RUN ON A SUBSET DESTROYS THE REST, in reverse: a narratives.json
# that held only some terms would take every other term's pages with it. So
# more than PRUNE_CEILING removals at once is refused -- nothing is removed and
# the step fails -- unless --prune says the person meant it. The first run
# after the corrections of 24 September 2026 removes 8 House pages and 5
# Senate ones.
PRUNE_CEILING = 25


def prune(out_dir, keep, allowed=False):
    """Remove the pages in out_dir whose date is not in `keep`. Returns the
    dates removed; refuses (SystemExit) past the ceiling without `allowed`."""
    stale = sorted(f for f in out_dir.glob("*.html")
                   if re.fullmatch(r"\d{4}-\d\d-\d\d", f.stem)
                   and f.stem not in keep)
    if len(stale) > PRUNE_CEILING and not allowed:
        raise SystemExit(
            f"REFUSED: {len(stale)} pages in {out_dir} are for sittings "
            f"narratives.json does not hold ({', '.join(f.stem for f in stale[:6])}"
            f"{', ...' if len(stale) > 6 else ''}). More than {PRUNE_CEILING} "
            "at once looks like a narratives.json missing whole terms, not a "
            "corrected date; nothing was removed. Rebuild the narratives, or "
            "pass --prune if these sittings really are gone.")
    for f in stale:
        f.unlink()
    if stale:
        print(f"  {len(stale)} page(s) removed for sittings the record no "
              f"longer holds: {', '.join(f.stem for f in stale)}")
    return [f.stem for f in stale]


def _lead(day, narrative, date, body="H"):
    n = len(day.items)
    b = len(day.bills)
    # Each vote once, the day's votes on no bill among them (session_days
    # Day.votes): the count of roll calls the page draws.
    k = day.counts()
    bits = [f"{n} action{'' if n == 1 else 's'} on {b} bill{'' if b == 1 else 's'}"] \
        if n else []
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
