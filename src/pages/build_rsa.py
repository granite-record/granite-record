#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-11.24
"""
The statutes (RSA) as pages: /laws, and one page a chapter at /laws/<chapter>.

    python3 src/pages/build_rsa.py --site site --base https://graniterecord.org

Asks nobody. Reads the General Court's statute table through rsa.py, what
rsa.py wrote (rsa_citations.json), the bill index the site build wrote
(site/idx/<term>.json) for each bill's number, title and whether it is still
moving, and for a law the record its page carries (site/bill/<year>/<id>.html,
through site_read) for when it takes effect. Writes site/laws.html,
site/laws/<chapter>.html and the three files the landing page's search reads,
site/laws/chapters.json, headings.json and words.json.

THE DESIGN IS RSA_PAGE.md (7 October 2026), with the person's asks of 11
October: "a more easily searchable and viewable interface for RSAs,
including tagging sections that are in progress that propose to amend that
RSA section, with history of how it's changed through various bills over the
years. You should be able to easily scroll through sections and search
through the database for related laws in plain text, and the RSA pages
should be linked throughout the site to the Granite Record pages as an
interlinked system."

A CHAPTER PAGE, top to bottom (RSA_PAGE.md §5):

1. The chapter's number and name, and one line saying what the text is: the
   table as the General Court holds it, through the laws of the latest year
   its source notes name, with the official page one link away.
2. Pending: the bills passed that change this chapter and have not taken
   effect, a line each saying when they do (Bills.passing, the person's ask
   of 24 October 2026); then the sitting term's bills still moving that say
   they change it, as chips. Each section they name is tagged below.
3. The sections in order, under the chapter's own inner headings, each an
   anchor (/laws/91-a#s4) carrying: its heading, a Pending tag where a bill
   passed or still moving would change it, its text with every citation the
   table holds linked to its own anchor and the first use of each defined
   term that applies to it marked (rsa.Defined, the person's ask of 24
   October 2026), its source note, and four folds -- How it has changed
   (the source note's laws, newest first, each the bill it was), Also
   proposed by (every other bill whose own instructions name the section,
   failed ones included), Cites, Cited by.
4. A repealed section is one muted line, its anchor kept, so an old bill's
   link still lands on something true.

TWO RECORDS, NOT ONE (RSA_PAGE.md §3). "How it has changed" is the Office of
Legislative Services' source note; "Also proposed by" is the bills' own
instructions. They are labelled apart and never merged.

THE TEXT IS TODAY'S. A 1997 bill's link opens the section as it reads now;
the currency line says so, and the history says when it changed, not what
it said.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import collections
import datetime
import html
import json
import math
import re
import unicodedata

import build_date
import components as C
import constitution_tab as CT
import parse_constitution as PC
import rsa
import shell as S
import site_read as SR
import structured as LD

E = html.escape
SHOWN = 8          # a list folds after this many, as the bill page's Amends row does
OG_ALT = "Granite Record: New Hampshire's statutes"

STOP = set("""a an and are as at be been by for from has have in is it its may not of on or
shall such that the this to under which with any all other each than those these who whom
whose upon into within without where when there their them they was were will would
pursuant thereof therein hereby section chapter paragraph subparagraph rsa provided
including include includes also more less only same such state new hampshire person""".split())
WORD = re.compile(r"[a-z][a-z']{2,}")


SMALL = set("a an and as at but by for in nor of on or per the to vs via with from into upon".split())
ROMAN = re.compile(r"^(?=[IVXLC]+$)[IVXLC]+$")


def nice(name):
    """The table's capitals as a heading: "ACCESS TO GOVERNMENTAL RECORDS AND
    MEETINGS" -> "Access to Governmental Records and Meetings", Roman numerals
    and abbreviations of two or more capitals left as they are."""
    if not name or not name.isupper():
        return name or ""
    out = []
    for i, w in enumerate(name.split()):
        core = w.strip("(),;:.")
        if ROMAN.match(core) or (len(core) <= 4 and "." in w) or core in ("RSA", "UCC", "N.H."):
            out.append(w)
        elif i and w.lower() in SMALL:
            out.append(w.lower())
        else:
            out.append("-".join(x[:1].upper() + x[1:].lower() for x in w.split("-")))
    return " ".join(out)


def shown_order(name):
    """A name's place in a list sorted by what it shows, letters only: case
    and accents set aside, so "Éducation" sits with "Education" and "fish &
    Game" with "Fish & Game" (the person, 24 October 2026: "Topics in the
    rsa pages should be sorted alphabetically"). The name itself breaks a tie,
    so the order is the same on every machine."""
    flat = unicodedata.normalize("NFKD", str(name or ""))
    return ("".join(c for c in flat if not unicodedata.combining(c)).casefold(), str(name or ""))


def bill_order(key):
    """A bill key in the order the site lists bills: kind, then number."""
    term, _, bill = key.partition("/")
    m = re.match(r"([A-Z]+)(\d+)", bill)
    return (term, m.group(1), int(m.group(2))) if m else (term, bill, 0)


def stem(w):
    """The light stem the search uses on both sides, so "dogs" finds "dog"
    and "liabilities" "liability"; the same rule is in LANDING_JS."""
    w = w.lower().strip("'")
    if w.endswith("'s"):
        w = w[:-2]
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def chapter_slug(ch):
    return ch.lower()


# The chapters whose page is a folder's index.html (chapter_file), and so
# whose address ends in a slash (chapter_path). Two scripts cannot import
# this and say it again -- app.js's LAW_FOLDERS and build_pages.NOT_FOUND's
# -- and preflight holds both to this one (16 October 2026).
FOLDER_CHAPTERS = ("404",)


def chapter_file(out, ch):
    """Where a chapter's page is written. RSA 404's page is laws/404/index.html,
    not laws/404.html: the host serves a folder's 404.html for every address
    in it that has no page, so every mistyped /laws/ address showed chapter
    404 (the preview, 11 October 2026). /laws/404/ is answered from the
    folder, and /laws/404 with a redirect to it, so chapter_path gives the
    address with its slash."""
    slug = chapter_slug(ch)
    return out / slug / "index.html" if slug in FOLDER_CHAPTERS else out / f"{slug}.html"


def chapter_path(ch, sec=""):
    """The address the host serves a chapter's page at: /laws/91-a, and
    /laws/404/ for the one chapter chapter_file puts in a folder; with
    `sec`, that section's anchor on it (/laws/404/#s5).

    THE SLASH IS PART OF RSA 404'S ADDRESS (the sitemap audit, 16 October
    2026). The host answers /laws/404 with a 308 to /laws/404/, measured on
    the live site, so the sitemap listed an address that redirects and the
    page named as its canonical the address that redirected back to it. Every
    place that writes a chapter's address asks here: the links, the sitemap,
    the page's canonical, og:url and citation, and the bill records, bill
    pages, feeds and guides that link a law."""
    slug = chapter_slug(ch)
    return f"/laws/{slug}" + ("/" if slug in FOLDER_CHAPTERS else "") + (f"#s{sec}" if sec else "")


def sec_anchor(addr):
    return "s" + addr.split(":", 1)[1]


def href(addr):
    """The site's own address for a statute address: /laws/91-a#s4, /laws/91-a."""
    ch, _, sec = addr.partition(":")
    return chapter_path(ch) + (f"#{sec_anchor(addr)}" if sec else "")


def term_of_year(y):
    y = int(y)
    a = y if y % 2 else y - 1
    return f"{a}-{a + 1}"


def term_before(term):
    """ "2025-2026" -> "2023-2024"; "" for anything else."""
    m = re.fullmatch(r"(\d{4})-(\d{4})", term or "")
    return f"{int(m.group(1)) - 2}-{int(m.group(2)) - 2}" if m else ""


def chapter_label(ch, name):
    """ "Chapter 71: The Tax Commission" (the person, 11 October 2026: "Laws
    should also be labeled as Chapter 71: The Tax Commission rather than just
    71")."""
    return f"Chapter {ch}: {nice(name)}" if name else f"Chapter {ch}"


def title_label(tno, tname):
    """("VI", "TITLE VI PUBLIC OFFICERS AND EMPLOYEES") -> ("Title VI", "Public Officers and Employees")."""
    return f"Title {tno}", nice(re.sub(r"^TITLE\s+\S+\s*", "", tname or "").strip())


# A CHAPTER'S TOPICS are the bill search's own, read off the bills that say
# they change it (the person, 11 October 2026: "If laws are groupable into
# topics in a similar way to bills, that would be helpful for searching").
# Miscellaneous says nothing about a chapter and is not counted; a topic is
# the chapter's where at least TOPIC_SHARE of the rest of its bills and at
# least TOPIC_LEAST of them carry it, at most two. A chapter no bill of the
# record has changed has none, rather than a guessed one: 1,274 of 1,786 have
# one on 8 September 2026's table.
TOPIC_SHARE, TOPIC_LEAST, TOPIC_SKIP = 0.3, 2, ("Miscellaneous",)


def chapter_topics(data, bills):
    votes = collections.defaultdict(collections.Counter)
    for term, bs in data.get("bills", {}).items():
        for bill, rec in bs.items():
            tp = bills.row(f"{term}/{bill}").get("topic") or ""
            if not tp or tp in TOPIC_SKIP:
                continue
            for ch in {str(c).split(":")[0] for c in rec.get("changes") or []}:
                votes[ch][tp] += 1
    out = {}
    for ch, c in votes.items():
        n = sum(c.values())
        top = [t for t, v in c.most_common(2) if v >= TOPIC_LEAST and v / n >= TOPIC_SHARE]
        if top:
            out[ch] = top
    return out


def chapter_pending(data, bills):
    """{chapter: [bill keys]} for the changes pending to it: the sitting
    term's bills still before the General Court that say they change it
    (Bills.pending), and the bills passed that change it and have not taken
    effect there (Bills.passing)."""
    out = collections.defaultdict(set)
    for term, bs in data.get("bills", {}).items():
        for bill, rec in bs.items():
            k = f"{term}/{bill}"
            chs = {str(c).split(":")[0] for c in rec.get("changes") or []}
            if chs and bills.pending(k):
                for ch in chs:
                    out[ch].add(k)
    # Not a law whose effective date the record does not state: it is listed
    # on the chapter's page under a heading that says so, and is not counted
    # as pending, which it may not be.
    for k, p in bills.passing(data).items():
        if p.effect.parts or p.effect.awaiting:
            for a in p.addrs:
                out[a.split(":")[0]].add(k)
    return {ch: sorted(ks, key=bill_order) for ch, ks in out.items()}


# ------------------------------------------------------------------ in effect

# WHEN A PASSED BILL TAKES EFFECT (the person, 24 October 2026: "Pending
# rsas should show when a bill has passed but has not yet taken effect, with
# a line about when the bill takes effect and a link to its page"). Until
# that day Pending was only the bills still before the General Court, so
# from the session's end to the next there was none: on 24 October 2026 the
# Laws page offered "Bills pending this term" at 0, while 68 of the term's
# laws took effect on a day still to come, most on 1 January 2027.
#
# WHERE THE DAY COMES FROM, IN ORDER (Bills.effect):
#   1. The chaptered law's own last lines, "Effective Date: January 01, 2027",
#      or a line a part: "I. Section 3 effective January 1, 2027" and "II.
#      Remainder effective August 1, 2026". The final version's text in the
#      bill's record ends with them.
#   2. The day the bill's page dates its Law stop by (its index row's rail),
#      which the docket's governor line gives -- for a law whose record has
#      no such lines, or whose record is not read (below).
#   3. The page's own words for a law in effect in parts ("Chapter 205, in
#      effect in parts: section 3 on Jan 1, 2027, the rest on Aug 1, 2026",
#      build_site_v2._j_effective_parts), from the same docket line.
#   4. The act's own Effective Date section, "This act shall take effect
#      January 1, 2027"; and "60 days after its passage" counted from the day
#      of passage the chaptered law states -- the veto overridden, the day it
#      became law without the Governor's signature, or Approved -- or, where
#      it states none, the Governor's stop on the rail, and the line says
#      how it was counted.
#   5. Nothing read: "Effective date not stated in the record we hold".
# The chaptered law first because the docket's line can be another bill's:
# HB 1184 of 2026's reads "I. Sec 2 eff 1/1/27 II. Sec 3 eff 1/1/27 III. Rem
# eff 1/1/28", which is HB 1102's, overridden the same day; its chaptered
# text says section 3 on August 19, 2027 and the rest on October 18, 2026.
# Of the 70 laws of the last two terms whose rail gives one day and whose
# text has the lines, the two agree on all 70 (24 October 2026).
#
# A part with no day -- "as section 21 provides", on another bill becoming
# law or a federal approval -- is said as the law says it, and does not by
# itself make a change pending.
# The chaptered law's reader is law_effect.py's (24 October 2026), shared
# with build_site_v2.py, whose bill pages date their Law stop by it too.
from law_effect import (ARTICLE_44, DATE_WORDS, MONTH_NO, PROVIDED,  # noqa: E402,F401
                        TRAILER_AT, TRAILER_PART, Part, act_sections,
                        chaptered_parts, day_of, day_said, part_of)

Effect = collections.namedtuple("Effect", "parts source awaiting")
Effect.__doc__ = """When a passed bill takes effect: its parts (none where
nothing is read), where they were read ("law", "docket", "text" or ""), and
whether the bill awaits the Governor rather than being law."""

Passed = collections.namedtuple("Passed", "key effect addrs year")
Passed.__doc__ = """A bill passed and not yet in effect everywhere it changes
the statutes: its effect, {address: the day the change there takes effect,
or None where the record does not say which part makes it}, and the year of
the session laws it is a chapter of ("" for a bill awaiting the Governor)."""

# The bill's page's own words for a law in effect in parts, written by
# build_site_v2._j_effective_parts: each part's words, then "on Jan 1, 2027"
# or "as section 3 provides", parts apart by a comma.
PAGE_PARTS = re.compile(r"\bin effect in parts:\s*(.+)$", re.S)
PAGE_PART_END = re.compile(r"\s+(?:on\s+(?P<day>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?"
                           r"\s+\d{1,2},\s+\d{4})|as\s+section\s+(?P<prov>\d{1,3})\s+provides)(?:,\s*|\s*$)")


def journey_parts(rec):
    """The parts the bill's page states for a law in effect in parts, or
    None."""
    steps = [s for s in ((rec or {}).get("journey") or {}).get("steps") or [] if s.get("act") == "law"]
    m = PAGE_PARTS.search((steps[-1].get("text") or "") if steps else "")
    if not m:
        return None
    s, pos, parts = m.group(1).strip(), 0, []
    for e in PAGE_PART_END.finditer(s):
        what = part_of(s[pos:e.start()])
        if what is None:
            return None
        if e.group("day"):
            day = day_of(DATE_WORDS.match(e.group("day")))
            if not day:
                return None
            parts.append(Part(*what, day, ""))
        else:
            parts.append(Part(*what, None, f"as section {e.group('prov')} of the act provides"))
        pos = e.end()
    return tuple(parts) if parts and pos == len(s) else None


# The act's own section on when it takes effect: "4 Effective Date." in a
# bill, "205:5 Effective Date." (or "282 : 5") in the chaptered law, to the
# lines after it.
ACT_EFFECT = re.compile(r"(?:^|\n)[ \t]*(?:\d{1,4}[ \t]*:[ \t]*)?\d{1,3}[ \t]+Effective Date\.[ \t]*(?P<text>.*?)"
                        r"(?=\n(?:Approved:|VETOED|Veto Overridden|Enacted in accordance|Effective(?: Date)?:)|\Z)",
                        re.S | re.I)
ACT_PART = re.compile(r"^(?:[IVXL]{1,5}\.\s*)?(?P<what>.+?)\s+(?:shall\s+)?takes?\s+effect\s+(?P<when>.+?)\.?$",
                      re.I | re.S)
AFTER_PASSAGE = re.compile(r"(?P<n>\d{1,3})\s+days\s+after\s+(?:its\s+)?passage", re.I)
UPON_PASSAGE = re.compile(r"(?:up)?on\s+(?:its\s+)?passage", re.I)
# The day of passage, as the chaptered law states it, most particular first.
PASSED_ON = (("Veto Overridden", "the day the veto was overridden"),
             ("without the signature of the governor", "the day it became law without the Governor's signature"),
             ("Approved:", "the day it was approved"))


def passage_day(body, row):
    """(day, words) for the day a law passed, from the chaptered law's last
    lines, or failing those from the Governor's stop on its rail where the
    Governor signed it or let it become law unsigned; (None, "")."""
    for said, words in PASSED_ON:
        i = (body or "").rfind(said)
        m = DATE_WORDS.search(body, i + len(said), i + len(said) + 40) if i >= 0 else None
        if m and day_of(m):
            return day_of(m), words
    g = next((s for s in row.get("rail") or [] if str(s[0])[:1] == "G"), None)
    if g and len(g) > 2 and g[0] == "Gp" and g[2] in ("signed", "unsigned"):
        try:
            return datetime.date.fromisoformat(g[1]), ("the day the Governor signed it" if g[2] == "signed"
                                                       else "the day it became law without the Governor's signature")
        except ValueError:
            pass
    return None, ""


def act_parts(body, passed=(None, ""), awaiting=False):
    """The parts the act's own Effective Date section gives, every sentence
    of it read or None. A day after its passage is counted from `passed`
    where it is known and said as counted; for a bill awaiting the Governor
    it is said as the text says it."""
    found = list(ACT_EFFECT.finditer(body or ""))
    if not found:
        return None
    text = found[-1].group("text").strip()
    lines = [x.strip() for x in re.split(r"\n|(?<=\.)\s+(?=[IVXL]{1,5}\.\s)", text) if x.strip()]
    day0, how0 = passed
    parts = []
    for x in lines:
        m = ACT_PART.match(x)
        what = part_of(m.group("what")) if m else None
        if what is None:
            return None
        when = m.group("when").strip()
        day, prov = day_said(when), PROVIDED.fullmatch(when)
        after, upon = AFTER_PASSAGE.fullmatch(when.rstrip(". ")), UPON_PASSAGE.fullmatch(when.rstrip(". "))
        if day:
            parts.append(Part(*what, day, ""))
        elif prov:
            parts.append(Part(*what, None, f"as section {prov.group(1)} of the act provides"))
        elif (after or upon) and awaiting:
            parts.append(Part(*what, None, f"{after.group('n')} days after it becomes law" if after
                              else "the day it becomes law"))
        elif (after or upon) and day0:
            n = int(after.group("n")) if after else 0
            parts.append(Part(*what, day0 + datetime.timedelta(days=n),
                              f"{n} days after its passage, counted from {C.date_words(day0, 'full')}, {how0}"
                              if n else f"on its passage: {how0}"))
        else:
            return None
    return tuple(parts) or None


def body_of(rec):
    """The text a record holds of its bill, as the bill's page shows it."""
    return ((rec or {}).get("billtext") or {}).get("body") or ""


NOTE_YEARS = 30


def note_days(note, year, chapter):
    """{the act's section: the day it took or takes effect} that a statute
    section's source note gives for one session law: "2026, 262:1, eff. Jan.
    1, 2027; 309:7, eff. Jan. 1, 2027." gives {7: 2027-01-01} for chapter 309
    of 2026. The note is the Office of Legislative Services' own account of
    the section, and settles a part the law dates only "as section 9
    provides": RSA 362-A:9's note puts HB 1718 of 2026's section 8 at January
    1, 2027 (24 October 2026)."""
    out = {}
    note = note or ""
    opens = list(rsa.YEAR_OPEN.finditer(note))
    for i, g in enumerate(opens):
        if int(g.group(1)) != int(year or 0):
            continue
        group = note[g.end():opens[i + 1].start() if i + 1 < len(opens) else len(note)]
        for part in group.split(";"):
            m = re.match(rf"\s*{int(chapter)}:(\d{{1,4}}(?:\s*[-,]\s*\d{{1,4}})*)\s*,\s*eff\.\s*(.+)$", part, re.S)
            d = DATE_WORDS.match(m.group(2).strip()) if m else None
            # A day more than NOTE_YEARS after the law's own year is a slip
            # of the keys, not a plan: RSA 287-E:16's note reads "2015,
            # 276:127, eff. July 1, 2105".
            if not d or not day_of(d) or day_of(d).year - int(year) > NOTE_YEARS:
                continue
            for a, b in re.findall(r"(\d+)(?:\s*-\s*(\d+))?", m.group(1)):
                for n in range(int(a), int(b or a) + 1):
                    out[n] = day_of(d)
    return out


def numbered_sections(body, chapter):
    """{the act's section number: its text} from a chaptered law's body,
    whose sections open "205:1 ", "205:2 " (or "282 : 1 ") in order -- the
    law's own chapter number, so the statute's own headings inside an
    amendment ("193-F:4 Pupil Safety") are not taken for them. {} where they
    do not run from 1."""
    if not chapter or not str(chapter).isdigit():
        return {}
    heads, want = [], 1
    for m in re.finditer(rf"(?:^|\n)[ \t]*{int(chapter)}[ \t]*:[ \t]*(\d{{1,3}})[ \t]+(?=[A-Z])", body or ""):
        if int(m.group(1)) == want:
            heads.append((want, m.start()))
            want += 1
    return {n: body[at:(heads[i + 1][1] if i + 1 < len(heads) else len(body))]
            for i, (n, at) in enumerate(heads)}


def effect_words(eff, today):
    """The line under a passed bill on the Laws pages: when it takes
    effect, each part in order of its day, said as taking effect or as
    having taken effect by `today`, a part with no day as the law says it,
    and a day counted with how it was counted."""
    if not eff.parts:
        return "Effective date not stated in the record we hold."
    # Parts on one day with nothing more to say are one part.
    if len({(p.day, p.how) for p in eff.parts}) == 1 and eff.parts[0].day and not eff.parts[0].how:
        parts = [Part(frozenset(), True, "", eff.parts[0].day, "")]
    else:
        parts = sorted(eff.parts, key=lambda p: (p.day is None, p.day or datetime.date.min, p.rest))

    def when(p):
        return (C.date_words(p.day, "full") + (f" ({p.how})" if p.how else "")) if p.day else p.how

    def verb(p):
        if p.day and p.day <= today:
            return "took effect"
        return "take effect" if len(p.secs) > 1 else "takes effect"
    if len(parts) == 1 and parts[0].rest:
        p = parts[0]
        if eff.awaiting:
            return f"If it becomes law, it takes effect {when(p)}, its text says."
        return f"{verb(p)[:1].upper()}{verb(p)[1:]} {when(p)}."
    # The parts still to come first, by their day, and those with no day; the
    # parts in effect after them, named where there is one and gathered
    # where there are more (HB 282 of 2025 has twelve, five in effect).
    later = [p for p in parts if not p.day or p.day > today]
    done = [p for p in parts if p.day and p.day <= today]
    said = [f"{part_name(p)} {verb(p)} {when(p)}" for p in later]
    if len(done) == 1:
        said.append(f"{part_name(done[0])} {verb(done[0])} {when(done[0])}")
    elif done:
        said.append("its other parts have taken effect")
    said = "; ".join(said)
    if eff.awaiting:
        return f"If it becomes law, its text says: {said}."
    return said[:1].upper() + said[1:] + "."


def part_name(p):
    """A part as the line names it: "the rest", "RSA 654:12", "section 3 of
    the act", "sections 1, 2, 5 and 6 of the act", "sections 7 to 10 of the
    act", and a statute with the act's sections named beside it, "RSA
    597:2-b and sections 16 and 17 of the act" (HB 318 of 2024)."""
    if p.rest:
        return "the rest"
    if p.addr:
        return f"RSA {p.addr}" + (f" and {part_name(p._replace(addr=''))}" if p.secs else "")
    nums, runs = sorted(p.secs), []
    for n in nums:
        if runs and n == runs[-1][1] + 1:
            runs[-1][1] = n
        else:
            runs.append([n, n])
    said = []
    for a, b in runs:
        said += [str(a)] if a == b else [str(a), str(b)] if b == a + 1 else [f"{a} to {b}"]
    word = "section" if len(nums) == 1 else "sections"
    return f"{word} {', '.join(said[:-1]) + ' and ' + said[-1] if len(said) > 1 else said[0]} of the act"


# ------------------------------------------------------------------ bills

class Bills:
    """Each bill's number, title, chip and whether it is still moving, from
    the site's own index (site/idx/<term>.json); and, for a bill passed, when
    it takes effect, from its record (site/bill/<year>/<id>.html, through
    site_read) and its row."""

    def __init__(self, site, current, today=None, table=None):
        self.rows, self.current, self.site = {}, current, Path(site)
        # The day the build is "now" for: build_date.today(), or the day a
        # check states. The statute table, where given, lends its source
        # notes' days to a part a law does not date (note_days).
        self.as_of, self.table = today or build_date.today(), table
        self._records, self._effects, self._later, self._passing = {}, {}, {}, None
        for p in sorted((Path(site) / "idx").glob("[0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9].json")):
            try:
                for r in json.loads(p.read_text(encoding="utf-8")):
                    self.rows[f"{p.stem}/{r.get('id')}"] = r
            except (OSError, ValueError):
                continue

    def row(self, key):
        return self.rows.get(key) or {}

    def moving(self, key):
        r = self.row(key)
        return bool(r) and S.still_moving(dict(r, term=r.get("term") or key.split("/")[0]),
                                          self.current)

    def awaiting(self, key):
        """Passed both chambers and with the Governor: still moving, its
        rail's Governor stop the one it is at ("Gh")."""
        return self.moving(key) and any(str(s[0]) == "Gh" for s in self.row(key).get("rail") or [])

    def pending(self, key):
        """Pending before the General Court, as the Laws page says it: still
        moving, and not sent to interim study (the person, 22 October 2026: a
        bill studied "won't become law this year regardless of whether [it
        is] recommended for future legislation"), nor through both chambers
        and with the Governor, which is listed with the bills passed
        (passing). A bill studied is followable still (shell.still_moving),
        and listed under Other bills that proposed changes."""
        return self.moving(key) and self.row(key).get("kind") != "study" and not self.awaiting(key)

    def record(self, key):
        """The bill's record as its page carries it (site_read.one), once."""
        if key not in self._records:
            r, (term, _, bill) = self.row(key), key.partition("/")
            self._records[key] = SR.one(self.site, r.get("year") or term[:4], bill) or {}
        return self._records[key]

    def note_later(self, addr):
        """Whether a section's source note dates anything in a year not
        before the build's: the only notes that can move a law's day later."""
        if addr not in self._later:
            note = self.table.sections[addr].note if self.table is not None and addr in self.table.sections else ""
            self._later[addr] = any(int(y) >= self.as_of.year for y in re.findall(r"\beff\.[^;]*?\b(\d{4})\b", note))
        return self._later[addr]

    def law_year(self, key):
        """The year of the session laws a law is a chapter of, where its
        statutes' source notes do not say: the year the Governor signed it or
        let it become law, and failing that the year of its page. A law
        signed in January can be the year before's -- HB 778 of 2025, signed
        8 January 2026, is chapter 305 of 2025 (extract_chapters) -- which is
        why the notes are asked first (passing)."""
        g = next((s for s in self.row(key).get("rail") or [] if str(s[0])[:1] == "G"), None)
        if g and len(g) > 1 and g[0] == "Gp" and re.match(r"\d{4}-", g[1] or ""):
            return g[1][:4]
        return str(self.row(key).get("year") or key[:4])

    def effect(self, key):
        """When a law, or a bill awaiting the Governor, takes effect (the
        sources in order are above Part); None for any other bill.

        WHICH RECORDS ARE READ. Every law of the sitting term and the one
        before it, and every older law whose rail gives no one day: an older
        law with one day on its rail is in effect when that day has passed,
        and its record would only say so again. In effect in parts, an older
        law can still have one to come -- HB 495 of 2019's section 2 takes
        effect November 1, 2029 -- so those are read whatever their term."""
        if key in self._effects:
            return self._effects[key]
        r, term = self.row(key), key.split("/")[0]
        eff = None
        rail_law = next((s for s in r.get("rail") or [] if str(s[0])[:1] == "L"), None)
        one = rail_law[1] if rail_law and len(rail_law) > 1 and rail_law[1] else ""
        try:
            one_day = datetime.date.fromisoformat(one) if one else None
        except ValueError:
            one_day = None
        if r.get("kind") == "law":
            recent = term in (self.current, term_before(self.current))
            if one_day and not recent:
                eff = Effect((Part(frozenset(), True, "", one_day, ""),), "docket", False)
            else:
                rec = self.record(key)
                body = body_of(rec)
                parts, source = chaptered_parts(body), "law"
                if not parts and one_day:
                    parts, source = (Part(frozenset(), True, "", one_day, ""),), "docket"
                if not parts:
                    parts, source = journey_parts(rec), "docket"
                if not parts:
                    parts, source = act_parts(body, passage_day(body, r)), "text"
                eff = Effect(parts or (), source if parts else "", False)
        elif self.awaiting(key):
            parts = act_parts(body_of(self.record(key)), awaiting=True)
            eff = Effect(parts or (), "text" if parts else "", True)
        self._effects[key] = eff
        return eff

    def passing(self, data):
        """{bill key: Passed} for every bill passed whose change to a statute
        has not taken effect: a law with a part still to come, a bill awaiting
        the Governor, and a law of the sitting term whose record states no day
        we can read ("Effective date not stated in the record we hold"),
        which cannot be said to be in effect.

        WHERE IN THE STATUTES. A law in effect on one day changes every
        section it names on that day. A law in effect in parts changes each
        section on the day of the part of the act that changes it: the act's
        sections are matched to the statutes by the source notes (RSA
        193-F:4's "2026, 205:1" is section 1 of chapter 205) and by each
        section of the chaptered text read on its own (rsa.changes) -- the
        text is needed, since a change still to come is often not in the note
        yet: HB 131 of 2026's section 3, a prospective repeal of RSA 193-F:4,
        V on January 1, 2027, is not in 193-F:4's note. A section whose part
        is not found carries the law, undated (None), so the line with every
        part is still there to read.

        AND THE SOURCE NOTE, WHERE IT DATES THE LAW'S SECTION ITSELF (note_days).
        It dates a part the law gives no day ("as section 9 provides"), and a
        day still to come there is taken over the law's own, since a later act
        can move it: SB 36 of 2026 moved HB 712 of 2025's section 14 from
        January 1 to July 1, 2027, which RSA 329:49-a's note says and HB 712's
        chaptered text cannot. A day already past in a note is not taken over
        a day still to come in the law, because a note can give two of the
        act's sections one day: RSA 170-E:11's note reads "197:1, 2, eff.
        Sept. 10, 2024", where HB 1407 of 2024's section 2, which repeals and
        reenacts paragraph I(c), takes effect December 31, 2026. Held against
        the notes section by section on 24 October 2026, the parts read here
        agree on 452 of 459, and those 7 are these cases."""
        if self._passing is not None:
            return self._passing
        named = collections.defaultdict(set)
        by_note = collections.defaultdict(lambda: collections.defaultdict(set))
        law_year = {}
        for term, bs in (data or {}).get("bills", {}).items():
            for bill, rec in bs.items():
                named[f"{term}/{bill}"].update(rec.get("changes") or [])
        for a, rows in (data or {}).get("enacted", {}).items():
            for y, law, b in rows:
                if not b:
                    continue
                named[b].add(a)
                ch, _, n = str(law).partition(":")
                if n.isdigit() and ch == str(self.row(b).get("chapter") or ""):
                    by_note[b][a].add(int(n))
                    law_year[b] = y
        out = {}
        for key in sorted(named, key=bill_order):
            r = self.row(key)
            if r.get("kind") != "law" and not self.awaiting(key):
                continue
            eff = self.effect(key)
            if eff is None:
                continue
            today, addrs = self.as_of, {}
            if not eff.parts:
                if eff.awaiting or key.split("/")[0] == self.current:
                    addrs = {a: None for a in named[key]}
            elif eff.awaiting:
                addrs = {a: min((p.day for p in eff.parts if p.day), default=None) for a in named[key]}
            else:
                whole = len(eff.parts) == 1 and eff.parts[0].rest
                secs = collections.defaultdict(set)
                for a, ns in by_note[key].items():
                    secs[a] |= ns
                if not whole:
                    for n, text in numbered_sections(body_of(self.record(key)), r.get("chapter")).items():
                        for a in rsa.changes(text):
                            secs[a].add(n)
                rest = next((p for p in eff.parts if p.rest), None)
                undated = any(p.day is None for p in eff.parts)
                of_sec = {}
                for p in eff.parts:
                    for n in sorted(p.secs):
                        of_sec.setdefault(n, p.day)
                for a in sorted(named[key]):
                    # The note is asked for a day still to come, or for a part
                    # the law does not date, so a note that can give neither
                    # is not read.
                    said = (note_days(self.table.sections[a].note, law_year[key], r.get("chapter"))
                            if self.table is not None and key in law_year and a in self.table.sections
                            and (self.note_later(a) or undated) else {})
                    if whole:
                        # The law's one day, or the note's still to come for
                        # its section of the law, where a later act moved it.
                        moved = [said[n] for n in secs[a] if n in said and said[n] > today]
                        days = moved or [eff.parts[0].day]
                    else:
                        days = [p.day for p in eff.parts if p.addr and p.addr == a]
                        if not secs[a] and not days:
                            if any(p.day and p.day > today for p in eff.parts):
                                addrs[a] = None
                            continue
                        for n in secs[a]:
                            d = of_sec[n] if n in of_sec else (rest.day if rest else None)
                            nd = said.get(n)
                            days.append(nd if nd and (nd > today or not d) else d)
                    later = [d for d in days if d and d > today]
                    if later:
                        addrs[a] = min(later)
            if addrs:
                out[key] = Passed(key, eff, addrs,
                                  "" if eff.awaiting else str(law_year.get(key) or self.law_year(key)))
        self._passing = out
        return out

    def passed_item(self, key, data, here=None, path="", addr=None):
        """A passed bill as the Laws pages list it: its number linked to its
        page, its status, and the line saying when it takes effect.

        On a section's tag (`addr`), the day its change there takes effect,
        where that is not simply the law's one day. In a chapter's list
        (`here`, its page at `path`), the sections of it the bill changes,
        linked, under the day each change takes effect where the law's days
        differ by section; the whole line, with every part, is the bill's
        own page's."""
        p = self.passing(data).get(key)
        if not p:
            return ""
        r, eff, today = self.row(key), p.effect, self.as_of
        term = key.split("/")[0]
        when = "" if term == self.current else f' <span class="rs-yr">{E(term)}</span>'
        if eff.awaiting:
            st = "Passed both chambers; with the Governor"
        else:
            st = (r.get("status") or "Became law") + (
                f", chapter {r['chapter']} of the Laws of {p.year}" if r.get("chapter") and p.year
                else f", chapter {r['chapter']}" if r.get("chapter") else "")
        one = eff.parts[0].day if len(eff.parts) == 1 and eff.parts[0].rest else None
        line, where = effect_words(eff, today), ""
        if addr:
            day = p.addrs.get(addr)
            if day and not eff.awaiting and day != one:
                line = f"Its change to this section takes effect {C.date_words(day, 'full')}."
        elif here:
            mine = sorted((a for a in p.addrs if a.startswith(here + ":")), key=rsa.addr_key)

            def links(addrs):
                return ", ".join(f'<a href="{E(path)}#{E(sec_anchor(a))}">{E(a)}</a>' for a in addrs[:SHOWN]) + (
                    f" and {len(addrs) - SHOWN} more" if len(addrs) > SHOWN else "")
            if mine and not eff.awaiting and eff.parts and all(p.addrs[a] for a in mine) \
                    and any(p.addrs[a] != one for a in mine):
                by_day = collections.defaultdict(list)
                for a in mine:
                    by_day[p.addrs[a]].append(a)
                line = None
                where = (' <span class="rs-eff">Its changes here take effect '
                         + "; ".join(f"{E(C.date_words(d, 'full'))}: {links(by_day[d])}" for d in sorted(by_day))
                         + ".</span>")
            elif mine:
                where = f' <span class="rs-in">Changes {links(mine)}.</span>'
            elif here in p.addrs:
                where = ' <span class="rs-in">Changes this chapter.</span>'
        return (f'<li><a href="{E(self.url(key))}" title="{E(r.get("title") or "")}">{E(self.label(key))}</a>{when}'
                f' <span class="rs-st">{E(st)}</span>'
                + (f' <span class="rs-eff">{E(line)}</span>' if line else "") + where + "</li>")

    def label(self, key):
        r = self.row(key)
        term, _, bill = key.partition("/")
        if r.get("n"):
            return r["n"]
        m = re.match(r"([A-Z]+)(\d+)$", bill)
        return f"{m.group(1)} {m.group(2)}" if m else bill

    def url(self, key):
        r = self.row(key)
        term, _, bill = key.partition("/")
        year = r.get("year") or term[:4]
        return f"/bill/{year}/{bill.lower()}"

    def chip(self, key, with_year=True, always_year=False):
        """A bill as the site draws one in a list: its number linked, its
        status after it, the term's years where it is not the sitting one --
        or always, where a list mixes the sitting term with others (Other
        bills that proposed changes, the person, 22 October 2026)."""
        r = self.row(key)
        term = key.split("/")[0]
        when = ("" if not with_year or (term == self.current and not always_year)
                else f' <span class="rs-yr">{E(term)}</span>')
        st = r.get("chip") or ""
        title = r.get("title") or ""
        return (f'<li><a href="{E(self.url(key))}" title="{E(title)}">{E(self.label(key))}</a>{when}'
                + (f' <span class="rs-st">{E(st)}</span>' if st else "") + "</li>")


def folded(items, cls="rs-list"):
    """A list of <li>, the first SHOWN open and the rest behind Show all."""
    if not items:
        return ""
    head = "".join(items[:SHOWN])
    rest = items[SHOWN:]
    more = (f'<details class="rs-more"><summary>Show all {len(items)}</summary>'
            f'<ul class="{cls}">{"".join(rest)}</ul></details>') if rest else ""
    return f'<ul class="{cls}">{head}</ul>{more}'


# ------------------------------------------------------------------ text

def linked_text(table, text, own, terms=None, wraps=None):
    """The section's text as paragraphs, every citation the table holds a
    link to its own anchor, the rest as written; a repealed target says so.

    `terms` is {paragraph: [(start, end, href)]}, a defined term's use, drawn
    as a quiet link to its definition (rs-tm); `wraps` is {first paragraph:
    (last paragraph, id, cite, scope words)}, a definition something on the
    page points at, its paragraphs held in one rs-dfn with the id the uses
    link to. DEFS_JS reads the definition from there, so its words are on
    the page once, where the statute puts them."""
    out = []
    close_at = None
    for li, para in enumerate(rsa.paragraphs(text)):
        spans = []
        for c in rsa.cites(para):
            kind, target = table.resolve(c.chapter, c.section)
            if not kind or target == own:
                continue
            # the span to link: from "RSA" for the head, the number alone in a list
            st = c.start if c.how == "rsa" else para.find(c.section, c.start)
            en = c.end
            if spans and st < spans[-1][1] or st < 0:
                continue
            gone = kind == "section" and table.sections[target].repealed
            spans.append((st, en, f'<a href="{E(href(target))}">',
                          "</a>" + (' <span class="rs-gone">(repealed)</span>' if gone else "")))
        for st, en, to in (terms or {}).get(li, []):
            if not any(st < b and a < en for a, b, _o, _c in spans):
                spans.append((st, en, f'<a class="rs-tm" href="{E(to)}">', "</a>"))
        pieces, pos = [], 0
        for st, en, opening, closing in sorted(spans):
            pieces.append(E(para[pos:st]))
            pieces.append(opening + E(para[st:en]) + closing)
            pos = en
        pieces.append(E(para[pos:]))
        p = f"<p>{''.join(pieces)}</p>"
        w = (wraps or {}).get(li)
        if w and close_at is None:
            last, ident, cite, scope = w
            p = (f'<div class="rs-dfn" id="{E(ident)}" data-cite="{E(cite)}"'
                 + (f' data-for="{E(scope)}"' if scope else "") + f">{p}")
            close_at = last
        if close_at == li:
            p += "</div>"
            close_at = None
        out.append(p)
    if close_at is not None:
        out.append("</div>")
    return "".join(out)


# The words a definition's scope is said in, over its use: "Defined for this
# chapter in RSA 153:1, III". A scope the reader names some other way ("RSA
# 162-C:1 to 162-C:5") is said as "Defined in".
SCOPE_WORDS = {"chapter": "this chapter", "subdivision": "this subdivision", "section": "this section",
               "paragraph": "this paragraph", "subparagraph": "this subparagraph",
               "article": "this article", "title": "this title"}


def defined_terms(table, ch, path):
    """({section: {paragraph: [(start, end, href)]}}, {section: wraps}) for a
    chapter's page: each section's marks (rsa.Defined.marks) and the
    definitions they point at, which are always on the same page, since a
    definition is never marked outside its own chapter."""
    d = table.defined()
    marks, wraps = {}, collections.defaultdict(dict)
    for a in table.chapters[ch]["sections"]:
        if table.sections[a].repealed:
            continue
        got, _withheld = d.marks(a)
        if not got:
            continue
        marks[a] = {li: [(st, en, f"{path}#{d.defs[i].anchor}") for st, en, i in ms]
                    for li, ms in got.items()}
        for ms in got.values():
            for _st, _en, i in ms:
                x = d.defs[i]
                wraps[x.addr][x.para] = (x.shown, x.anchor, x.cite, SCOPE_WORDS.get(x.scope, ""))
    return marks, wraps


# ------------------------------------------------------------------ indexes

# A CHAPTER'S POPULAR NAME, as the statutes themselves write it: readers search
# "right to know", and chapter 91-A is titled "Access to Governmental Records
# and Meetings". The statutes say the name beside the citation, in either
# order -- "the right-to-know law, RSA 91-A", "RSA 91-A, the right-to-know
# law" -- or declare it: "This chapter shall be known as the Uniform
# Commercial Code". A name is kept where the chapter declares it or the
# statutes use it at least twice.
KNOWN_AS = re.compile(r"(?:shall|may)\s+be\s+(?:known|cited)(?:\s+and\s+(?:may\s+be\s+)?cited)?\s+as\s+"
                      r"(?:the\s+)?[\"\u201c]?([A-Z][^\"\u201d.;]{3,80}?)[\"\u201d]?(?:\.|,|;|\s+and\b)")
NAME_THEN_RSA = re.compile(r"\bthe\s+((?:[A-Za-z'\u2019-]+\s+){0,4}(?:law|act|code))\s*,\s*RSA\s+"
                           r"(\d{1,3}(?:-[A-Z]{1,2})?)(?![:\d])", re.I)
RSA_THEN_NAME = re.compile(r"\bRSA\s+(\d{1,3}(?:-[A-Z]{1,2})?)(?![:\d])\s*,\s*the\s+"
                           r"((?:[A-Za-z'\u2019-]+\s+){0,4}(?:law|act|code))\b", re.I)


def popular_names(table):
    """{chapter: [names]} from the statutes' own words."""
    got = collections.defaultdict(collections.Counter)
    for s in table.sections.values():
        for m in KNOWN_AS.finditer(s.text):
            got[s.chapter][m.group(1).strip()] += 2
        for m in NAME_THEN_RSA.finditer(s.text):
            got[m.group(2).upper()][m.group(1).strip().lower()] += 1
        for m in RSA_THEN_NAME.finditer(s.text):
            got[m.group(1).upper()][m.group(2).strip().lower()] += 1
    out = {}
    for ch, names in got.items():
        if ch not in table.chapters:
            continue
        keep, seen = [], set()
        for n, c in names.most_common():
            if c >= 2 and n.lower() not in seen:
                seen.add(n.lower())
                keep.append(n)
        if keep:
            out[ch] = keep[:4]
    return out


def build_indexes(table, cites, topics=None, pending=None):
    """chapters.json, headings.json and words.json for the landing page's
    search (RSA_PAGE.md §6), all in the reader's browser.

    words.json is what each section is ABOUT, not every word in it: the
    heading's words, and its twelve most telling words by how often the
    section uses them against how many sections do -- the plain-text search
    the person asked for, at a size a reader can fetch once."""
    names = popular_names(table)
    chapters = {ch: [nice(info["name"]), info["title_no"], len(info["sections"]), info["repealed"],
                     names.get(ch, []), (topics or {}).get(ch, []), len((pending or {}).get(ch, []))]
                for ch, info in table.chapters.items()}
    headings = [[a, s.heading] for a, s in table.sections.items() if not s.repealed]
    df = collections.Counter()
    tfs = {}
    for a, s in table.sections.items():
        if s.repealed:
            continue
        tf = collections.Counter(stem(w) for w in WORD.findall(s.text.lower()) if w not in STOP)
        tfs[a] = tf
        df.update(tf.keys())
    n = max(1, len(tfs))
    order = list(tfs)
    idx = {a: i for i, a in enumerate(order)}
    post = collections.defaultdict(list)
    for a, tf in tfs.items():
        head = {stem(w) for w in WORD.findall(table.sections[a].heading.lower()) if w not in STOP}
        top = sorted(tf, key=lambda w: (-tf[w] * math.log(n / df[w]), w))[:12]
        for w in sorted(head | set(top)):
            post[w].append(idx[a])
    # Postings as the gap from the one before, which compresses to about half
    # (951 KB to 518 KB gzipped on 8 September 2026's table), and numbered by
    # headings.json's own order, which is the same list -- so the sections are
    # not written twice.
    assert [h[0] for h in headings] == order, "headings.json and words.json list sections differently"
    words = {"words": {w: [v[0]] + [b - a for a, b in zip(v, v[1:])] for w, v in sorted(post.items())}}
    return chapters, headings, words


# ------------------------------------------------------------------ pages

# A REPEALED CHAPTER'S NOTE, as the table holds it: its title and name in
# capitals, then "[Repealed by 1971, 227:15, eff. Aug. 17, 1971.]". All 468
# chapters the table marks repealed carry the bracket, and nine of them were
# not repealed but moved: "[Redesignated as RSA 246 by 2024, 33:4, eff. July
# 1, 2024.]". The banner says which, in words.
REPEAL = re.compile(r"\[\s*Repealed,?\s+(?:by\s+)?(\d{4}),\s*([^\]]*?)"
                    r"(?:,?\s*(?:eff\.|effective)\s*([^\]]*?))?\.?\s*\]")
MOVED = re.compile(r"\[\s*Redesignated\s+as\s+RSA\s+(\d{1,3}(?:-[A-Z]{1,2})?)\s+by\s+(\d{4}),\s*"
                   r"([^\]]*?)(?:,?\s*(?:eff\.|effective)\s*([^\]]*?))?\.?\s*\]")


def moved_to(note):
    """The chapter a redesignated chapter became, or ''."""
    m = MOVED.search(note or "")
    return m.group(1) if m else ""


def repeal_words(note):
    """The banner's words after its first: when and by what law the chapter
    was repealed or moved, or the bracket as the table has it where its words
    are in neither shape, or ''."""
    note = note or ""
    m = MOVED.search(note)
    if m:
        to, y, law, eff = m.groups()
        return (f' It is now <a href="{E(href(to))}">RSA {E(to)}</a>, moved there by the Laws of {E(y)}, '
                f"chapter {E(law)}" + (f", effective {E(eff)}." if eff else "."))
    m = REPEAL.search(note)
    if m:
        y, law, eff = m.groups()
        return (f" It was repealed by the Laws of {E(y)}, chapter {E(law)}"
                + (f", effective {E(eff)}." if eff else "."))
    b = re.search(r"\[([^\]]+)\]", note)
    return f" {E(b.group(1).strip())}" if b else ""


def chapter_page(tmpl, table, data, bills, ch, base):
    info = table.chapters[ch]
    secs = info["sections"]
    proposed = collections.defaultdict(list)     # address -> [bill key]
    for term, bs in data.get("bills", {}).items():
        for bill, rec in bs.items():
            for a in rec.get("changes", []):
                if a == ch or a.startswith(ch + ":"):
                    proposed[a].append(f"{term}/{bill}")
    cited_by = collections.defaultdict(list)
    for src, targets in data.get("statute", {}).items():
        for t in targets:
            if t.startswith(ch + ":") or t == ch:
                cited_by[t].append(src)
    pending_ch = sorted({k for a, ks in proposed.items() for k in ks if bills.pending(k)},
                        key=bill_order)
    # THE BILLS PASSED THAT CHANGE IT AND HAVE NOT TAKEN EFFECT (Bills.passing),
    # each with when it does, above the bills still before the General Court.
    passing = bills.passing(data)
    passed_ch = sorted((k for k, p in passing.items() if any(a == ch or a.startswith(ch + ":") for a in p.addrs)),
                       key=bill_order)
    latest = data.get("asof", {}).get("laws_through") or ""
    # THE PAGE'S OWN ADDRESS, AS THE HOST SERVES IT (16 October 2026): the
    # canonical, og:url, citation and the sections' own links all start from
    # this, so RSA 404's carry its slash (chapter_path).
    path = chapter_path(ch)
    title = chapter_label(ch, info["name"])
    first = table.sections[secs[0]] if secs else None
    # The General Court's own table of contents page for the chapter, the
    # address build_site_v2.rsa_url has linked for a chapter since 4
    # September, rather than a guessed one for the whole chapter's text.
    tno = (first.url.split("/")[0] if first and first.url else "") or (first.title_no if first else "")
    official = (f"https://gc.nh.gov/rsa/html/NHTOC/NHTOC-{tno}-{ch}.htm" if tno
                else "https://gc.nh.gov/rsa/html/nhtoc.htm")
    # THE NAME A READER SEARCHES FOR (the SEO review, 12 October 2026). The
    # title read "Chapter 91-A -- Laws": no "RSA", which is how the chapter is
    # cited and searched, and no name. Now "RSA 91-A -- Access to Governmental
    # Records and Meetings", with the state in the link card, and the page
    # says what it is in structured data, as a bill's does.
    name = nice(info["name"]) if info.get("name") else ""
    p = S.page(tmpl, path=path, base=base, title=S.title_of(f"RSA {ch}", name),
               og_title=f"New Hampshire RSA {ch}" + (f": {name}" if name else ""),
               description=f"New Hampshire RSA chapter {ch}, {name or info['name']}: "
               "its text, the bills that changed it and the bills that would.",
               og_image="og-learn.png", og_alt=OG_ALT, globals={"GR_STATIC": True, "GR_LAW": ch},
               noscript="", skip_label="Skip to the statute", sr_title="",
               nav_current="laws.html", cite=False,
               jsonld=LD.statute_chapter(ch, name, base, S.canon(path), official,
                                         bool(info.get("repealed"))))
    # "as the General Court's table holds it" went (the audit of 25 October
    # 2026, S7): it said where the text came from twice, before the line
    # that says so -- "Taken from the General Court's database on ..." -- and
    # the link to the official text.
    lead = (f"{as_of(latest)} "
            f'<a href="{E(official)}" rel="noopener">The official text on gc.nh.gov</a>.')
    tl, tn = title_label(info["title_no"], info["title"])
    crumb = f"{tl}: {tn}" if tn else tl
    # A REPEALED CHAPTER SAYS SO AT THE TOP, at the size of the lead (the
    # person, 11 October 2026: "Repealed pages are a bit hard to tell that the
    # chapter has been repealed on the page since the text is quite small").
    gone = ""
    if info.get("repealed"):
        word = "Moved" if moved_to(info.get("note")) else "Repealed"
        gone = (f'<p class="rs-banner" role="note"><strong>{word}.</strong> This chapter is no '
                f'longer in force.{repeal_words(info.get("note"))}</p>')
    head = (f'<header class="l-head"><p class="rs-crumb"><a href="/laws">Laws</a> &rsaquo; '
            f'<a href="/laws#t-{E(info["title_no"])}">{E(crumb)}</a></p>'
            f'<p class="rs-kick">RSA {E(ch)}</p><h1>{E(title)}</h1>{gone}'
            f'<p class="l-lead">{lead}</p>' + S.cite_block(path, title, base, S.BUILT) + "</header>")
    pend = ""
    if pending_ch or passed_ch:
        # A law whose record states no effective date that can be read is
        # listed apart, under words that do not say it is not yet in effect.
        known = [k for k in passed_ch if passing[k].effect.parts or passing[k].effect.awaiting]
        unread = [k for k in passed_ch if k not in known]
        pend = ('<section class="rs-pending" aria-label="Pending changes">'
                + ('<h2>Passed, not yet in effect</h2><ul class="rs-plist">'
                   + "".join(bills.passed_item(k, data, ch, path) for k in known) + "</ul>"
                   if known else "")
                + ('<h2>Passed this term, effective date not stated</h2><ul class="rs-plist">'
                   + "".join(bills.passed_item(k, data, ch, path) for k in unread) + "</ul>"
                   if unread else "")
                + ('<h2>Bills now before the General Court that would change this chapter</h2>'
                   + folded([bills.chip(k) for k in pending_ch]) if pending_ch else "")
                + "</section>")
    toc_items = []
    body = []
    sub = None
    terms, wraps = defined_terms(table, ch, path)
    for a in secs:
        s = table.sections[a]
        if s.sub and s.sub != sub:
            sub = s.sub
            body.append(f'<h2 class="rs-sub">{E(sub)}</h2>')
        anchor = sec_anchor(a)
        if s.repealed:
            body.append(f'<p class="rs-repealed" id="{E(anchor)}"><a href="{E(path)}#{E(anchor)}">{E(a)}</a> '
                        f'<span class="rs-rbadge">Repealed</span> {E(s.heading)}</p>')
            toc_items.append(f'<li class="rs-off"><a href="{E(path)}#{E(anchor)}">{E(a)}</a> '
                             f'<span>Repealed</span></li>')
            continue
        toc_items.append(f'<li><a href="{E(path)}#{E(anchor)}"><b>{E(a)}</b> {E(s.heading)}</a></li>')
        pend_k = sorted((k for k in proposed.get(a, []) if bills.pending(k)), key=bill_order)
        passed_k = [k for k in passed_ch if a in passing[k].addrs]
        hist = list(reversed(data.get("enacted", {}).get(a, [])))
        # A BILL IN THE HISTORY IS NOT ALSO "PROPOSED" (the person, 11 October
        # 2026: the two "sometimes show the exact same bill numbers which is
        # redundant"): the other list is the bills that did not become this
        # section's law -- nor one passed and pending here, which its tag lists.
        in_hist = {b for _y, _law, b in hist if b}
        other = [k for k in proposed.get(a, []) if not bills.pending(k) and k not in in_hist
                 and k not in passed_k]
        rows = []
        if hist:
            items = []
            for y, law, b in hist:
                bl = (f' &middot; <a href="{E(bills.url(b))}">{E(bills.label(b))}</a>' if b else "")
                items.append(f'<li><span class="rs-yr">{E(y)}</span> Laws of {E(y)}, chapter '
                             f'{E(law.split(":")[0])}{bl}</li>')
            rows.append(("How it has changed", "From the section's source note, newest first.",
                         folded(items, "rs-hist")))
        if other:
            other.sort(key=lambda k: (k.split("/")[0], bill_order(k)[1], -bill_order(k)[2]), reverse=True)
            rows.append(("Other bills that proposed changes", "Bills whose own text says they "
                         "change this section, and that are not in its history above.",
                         folded([bills.chip(k, always_year=True) for k in other])))
        out_c = data.get("statute", {}).get(a, [])
        if out_c:
            rows.append(("Cites", "", folded([f'<li><a href="{E(href(t))}">RSA {E(t)}</a></li>'
                                              for t in out_c], "rs-refs")))
        if cited_by.get(a):
            rows.append(("Cited by", "", folded([f'<li><a href="{E(href(t))}">RSA {E(t)}</a></li>'
                                                 for t in sorted(cited_by[a], key=rsa.addr_key)],
                                                "rs-refs")))
        tag = ""
        if pend_k or passed_k:
            # One law passed and nothing else: the tag says the day its change
            # here takes effect, where the record says which part makes it.
            n = len(pend_k) + len(passed_k)
            one = passing[passed_k[0]] if len(passed_k) == 1 and not pend_k else None
            day = one.addrs[a] if one else None
            tag_says = (f"Change takes effect {C.date_words(day, 'medium')}" if day and not one.effect.awaiting
                        else "Passed, effective date not stated" if one and not one.effect.parts
                        and not one.effect.awaiting
                        else f'Pending: {n} bill{"s" if n != 1 else ""}')
            tag = (f'<details class="rs-tag"><summary>{E(tag_says)}</summary>'
                   + ('<ul class="rs-plist">' + "".join(bills.passed_item(k, data, addr=a) for k in passed_k)
                      + "</ul>" if passed_k else "")
                   + (folded([bills.chip(k) for k in pend_k]) if pend_k else "") + "</details>")
        folds = "".join(
            f'<details class="rs-fold"><summary>{E(h)}</summary>'
            + (f'<p class="rs-note">{E(n)}</p>' if n else "") + f"{c}</details>"
            for h, n, c in rows)
        # ONE LEVEL UNDER WHAT HEADS IT (the cohesion audit of 30 October
        # 2026, I-1): an h3 under a part's h2, and an h2 straight under the
        # title, where a chapter has no parts -- most of them -- and went from
        # h1 to h3. The look is .rs-h's at either level.
        lv = 3 if sub else 2
        body.append(
            f'<section class="rs-sec" id="{E(anchor)}"><h{lv} class="rs-h"><a href="{E(path)}#{E(anchor)}">'
            f'{E(a)}</a> {E(s.heading)}</h{lv}>{tag}'
            f'<div class="rs-text" translate="no">{linked_text(table, s.text, a, terms.get(a), wraps.get(a))}</div>'
            + (f'<p class="rs-source">Source. {E(s.note)}</p>' if s.note else "")
            + (f'<div class="rs-folds">{folds}</div>' if folds else "") + "</section>")
    # THE SECTIONS IN A SIDEBAR (the person, 11 October 2026: "when you're in
    # an RSA chapter, the sidebar would show you the chapter sections so you
    # could easily click through them"): sticky beside the text on a wide
    # screen, a fold above it on a narrow one.
    toc = ""
    if toc_items:
        toc = (f'<nav class="rs-side" aria-label="Sections of chapter {E(ch)}"><details class="rs-sidebox" open>'
               f'<summary><span class="rs-sumw">Chapter {E(ch)}: {len(toc_items)} '
               f'section{"s" if len(toc_items) != 1 else ""}</span>'
               f'<span class="rs-now" aria-hidden="true"></span></summary>'
               f'<ol>{"".join(toc_items)}</ol></details></nav>')
    art = f'<div class="rs-art">{pend}{"".join(body)}</div>'
    return p.replace('<div id="results"></div>',
                     f'<div id="results"><div class="l-page rs-page">{head}'
                     f'<div class="rs-chap{" rs-notoc" if not toc else ""}">{toc}{art}</div></div>'
                     f'{CHAPTER_JS}{DEFS_JS if terms else ""}</div>', 1)


CHAPTER_JS = """<script>
(function(){
  // The sidebar's sections: the one being read marked as the page scrolls
  // past it. ON A PHONE (the person, 11 October 2026: "The index is not
  // accessible on mobile on individual chapters") the list is a bar held at
  // the top of the screen, naming the section being read; it opens over the
  // page, and choosing a section closes it.
  var d=document.querySelector(".rs-sidebox");if(!d)return;
  var narrow=function(){return window.matchMedia&&matchMedia("(max-width:60em)").matches;};
  if(narrow())d.open=false;
  var links={},box=d.querySelector("ol"),cur=null,now=d.querySelector(".rs-now");
  [].forEach.call(d.querySelectorAll("a[href*='#']"),function(a){links[a.getAttribute("href").split("#")[1]]=a;});
  d.addEventListener("click",function(e){if(e.target.closest("a")&&narrow())d.open=false;});
  document.addEventListener("keydown",function(e){if(e.key==="Escape"&&d.open&&narrow()){d.open=false;d.querySelector("summary").focus();}});
  if(!("IntersectionObserver" in window)||!box)return;
  var io=new IntersectionObserver(function(es){es.forEach(function(e){
    if(!e.isIntersecting)return;var a=links[e.target.id];if(!a||a===cur)return;
    if(cur)cur.removeAttribute("aria-current");a.setAttribute("aria-current","location");cur=a;
    if(now){var b=a.querySelector("b");now.textContent=b?b.textContent:a.textContent.split(" ")[0];}
    var li=a.parentNode;if(li.offsetTop<box.scrollTop||li.offsetTop>box.scrollTop+box.clientHeight-40)
      box.scrollTop=li.offsetTop-box.clientHeight/3;});},{rootMargin:"-15% 0px -75% 0px"});
  [].forEach.call(document.querySelectorAll(".rs-sec[id],.rs-repealed[id]"),function(s){io.observe(s);});
})();
</script>"""


# A DEFINED TERM'S DEFINITION OVER THE WORD (the person, 24 October 2026:
# "definitions in the rsa pages show up as tooltips in sections that cite
# them like 'dwelling unit' being defined in 153:1 and later referenced so
# that you know which definition it's referring to"). The word is a link to
# its definition (linked_text's rs-tm), so with no script it still goes
# there. With it, the definition opens in a box under the word, as the
# site's term popovers do (components.js, C9): a pointer held over it half a
# second, or keyboard focus; on a phone the first tap opens it and a second
# follows the link. It stays while the pointer moves onto it, and closes on
# Escape, a press elsewhere or focus leaving (WCAG 1.4.13). The words are
# read from the definition's own paragraphs on the page (rs-dfn), the first
# 400 characters of them, and the box says which section defines the word
# and for what: "Defined for this chapter in RSA 153:1, III". One box serves
# every word, inside the chapter's text, so it scrolls with it.
DEFS_JS = r"""<script>
(function(){
  var pop=null,cur=null,wait=0,shut=0,opened=0,touch=false,HOLD=500;
  function target(a){var h=a.getAttribute("href")||"",i=h.indexOf("#");return i<0?null:document.getElementById(h.slice(i+1));}
  function words(w){
    var t=[].map.call(w.querySelectorAll("p"),function(p){return p.textContent;}).join(" ")
      .replace(/^\s*(?:(?:[IVXLC]+(?:-[a-z]+)?|\d+|[A-H])\.\s*|\([0-9A-Za-z-]+\)\s*)+/,"");
    return t.length>420?t.slice(0,t.lastIndexOf(" ",400))+"…":t;}
  function hide(){if(!cur)return;pop.hidden=true;cur.removeAttribute("aria-describedby");cur=null;}
  function line(cls,text){var s=document.createElement("span");s.className=cls;s.textContent=text;return s;}
  function show(a){
    var w=target(a),box=a.closest(".rs-art");if(!w||!box)return;
    clearTimeout(shut);if(cur&&cur!==a)hide();
    if(!pop){pop=document.createElement("div");pop.className="termpop rs-dpop";pop.id="rs-dpop";
      pop.setAttribute("role","tooltip");
      pop.addEventListener("pointerenter",function(){clearTimeout(shut);});
      pop.addEventListener("pointerleave",function(e){if(e.pointerType==="mouse")shut=setTimeout(hide,250);});}
    if(pop.parentNode!==box)box.appendChild(pop);
    var f=w.getAttribute("data-for");
    pop.textContent="";
    pop.appendChild(line("rs-dpcite",(f?"Defined for "+f+" in ":"Defined in ")+w.getAttribute("data-cite")));
    pop.appendChild(line("rs-dptext",words(w)));
    if(touch)pop.appendChild(line("rs-dphint","Tap the word again to go to the definition."));
    pop.style.left="0";pop.hidden=false;cur=a;opened=Date.now();a.setAttribute("aria-describedby","rs-dpop");
    // Under the word, kept on the screen.
    var r=a.getBoundingClientRect(),b=box.getBoundingClientRect(),vw=document.documentElement.clientWidth;
    var x=r.left-b.left;pop.style.top=Math.round(r.bottom-b.top+6)+"px";pop.style.left=Math.round(x)+"px";
    var p=pop.getBoundingClientRect();
    if(p.right>vw-8)x-=p.right-(vw-8);
    if(b.left+x<8)x=8-b.left;
    pop.style.left=Math.round(x)+"px";
  }
  function term(e){return e.target.closest&&e.target.closest("a.rs-tm");}
  document.addEventListener("pointerdown",function(e){touch=e.pointerType!=="mouse";},true);
  document.addEventListener("keydown",function(e){touch=false;
    if(e.key==="Escape"&&cur){var a=cur;hide();a.focus();}});
  document.addEventListener("click",function(e){
    var a=term(e);
    // A tap opens the box; the next tap on the same word follows its link.
    if(a&&touch&&target(a)&&(cur!==a||Date.now()-opened<700)){e.preventDefault();show(a);return;}
    // A click goes to the definition, which the page marks (rs-dfn:target).
    if(cur&&(a===cur||!(e.target.closest&&e.target.closest(".rs-dpop"))))hide();
  });
  document.addEventListener("pointerover",function(e){
    var a=term(e);if(!a||e.pointerType!=="mouse")return;
    clearTimeout(shut);clearTimeout(wait);
    if(cur!==a)wait=setTimeout(function(){show(a);},HOLD);
  });
  document.addEventListener("pointerout",function(e){
    var a=term(e);if(!a||e.pointerType!=="mouse"||(e.relatedTarget&&a.contains(e.relatedTarget)))return;
    clearTimeout(wait);
    if(cur===a&&document.activeElement!==a)shut=setTimeout(hide,250);
  });
  document.addEventListener("focusin",function(e){
    var a=term(e);
    if(a)show(a);else if(cur&&!(e.target.closest&&e.target.closest(".rs-dpop")))hide();
  });
  document.addEventListener("focusout",function(e){
    if(cur&&e.target===cur&&!(e.relatedTarget&&pop.contains(e.relatedTarget)))shut=setTimeout(hide,250);
  });
})();
</script>"""


LANDING_JS = """<script>
(function(){
  var root=document.getElementById("lw");if(!root)return;
  var box=document.getElementById("rsq"),out=document.getElementById("rsout"),dir=document.getElementById("lwdir"),
      read=document.getElementById("lwread"),count=document.getElementById("lwcount");
  var narrow=function(){return window.matchMedia&&matchMedia("(max-width:59.9375em)").matches;};
  var CH=null,HD=null,WD=null,PAGES={};
  function get(u){return fetch(u).then(function(r){return r.ok?r.json():null;});}
  function esc(s){return String(s).replace(/[&<>"]/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c];});}
  function chOf(a){return a.split(":")[0];}
  // A chapter's address is the one its row links (build_rsa.chapter_path),
  // so RSA 404's keeps the slash the host serves it at.
  function link(a){var p=a.split(":"),g=root.querySelector('.lw-ch[data-ch="'+p[0]+'"] > .lw-go');
    return (g?g.getAttribute("href"):"/laws/"+p[0].toLowerCase())+(p[1]?"#s"+p[1]:"");}
  function heads(){return HD?Promise.resolve(HD):get("laws/headings.json").then(function(d){return HD=d||[];});}
  function chapters(){return CH?Promise.resolve(CH):get("laws/chapters.json").then(function(d){return CH=d||{};});}

  // ---- THE READER: a section's text from its chapter's own page, on the right.
  function page(ch){
    if(!PAGES[ch])PAGES[ch]=fetch(link(ch)).then(function(r){return r.ok?r.text():"";}).then(function(t){
      return new DOMParser().parseFromString(t,"text/html");});
    return PAGES[ch];}
  function open(a){
    if(narrow()){location.href=link(a);return;}
    var ch=chOf(a),li=root.querySelector('.lw-ch[data-ch="'+ch+'"]');
    [].forEach.call(root.querySelectorAll("[data-sec][aria-current]"),function(x){x.removeAttribute("aria-current");});
    [].forEach.call(root.querySelectorAll('[data-sec="'+a+'"]'),function(x){x.setAttribute("aria-current","true");});
    var crumb=li?crumbOf(li):"",name=li?labelOf(li):"Chapter "+ch;
    read.innerHTML='<p class="lw-wait">Opening RSA '+esc(a)+'&hellip;</p>';
    page(ch).then(function(doc){
      var sec=doc&&doc.getElementById("s"+a.split(":")[1]);
      read.innerHTML='<p class="lw-rcrumb">'+esc(crumb)+' &rsaquo; '+esc(name)+'</p>'
        +(sec?sec.outerHTML:'<p>This section could not be opened here.</p>')
        +'<p class="lw-own"><a href="'+link(a)+'">Open RSA '+esc(a)+' on its chapter&rsquo;s page</a></p>';
      read.scrollTop=0;
      var r=read.getBoundingClientRect();if(r.top<0)read.scrollIntoView({block:"start"});
    });
  }
  root.addEventListener("click",function(e){
    var t=e.target.closest("[data-sec]");if(!t||e.metaKey||e.ctrlKey||e.shiftKey)return;
    if(narrow())return;e.preventDefault();open(t.getAttribute("data-sec"));});

  // A chapter's label and its title's name, from what the row already shows.
  function labelOf(li){var n=li.querySelector(".lw-chname");return "Chapter "+li.getAttribute("data-ch")+": "+(n?n.textContent:"");}
  function crumbOf(li){var t=li.closest(".lw-title"),a=t&&t.querySelector(".lw-tno"),b=t&&t.querySelector(".lw-tname");
    return (a?a.textContent:"")+(b&&b.textContent?": "+b.textContent:"");}
  // ---- A CHAPTER OPENED IN THE DIRECTORY lists its sections, and the way
  // to its own page under them.
  root.addEventListener("toggle",function(e){
    var d=e.target;if(!d.classList||!d.classList.contains("lw-chd")||!d.open)return;
    if(d.querySelector(".lw-secs"))return;
    var ch=d.parentNode.getAttribute("data-ch");
    var ol=document.createElement("ol");ol.className="lw-secs";ol.setAttribute("data-ch",ch);
    ol.innerHTML='<li class="lw-none">Loading the sections&hellip;</li>';
    var own=document.createElement("p");own.className="lw-own";
    own.innerHTML='<a href="'+link(ch)+'">Open Chapter '+esc(ch)+' on its own page</a>';
    d.appendChild(ol);d.appendChild(own);
    heads().then(function(hd){
      var rows=hd.filter(function(x){return chOf(x[0])===ch;});
      ol.innerHTML=rows.length?rows.map(function(x){return '<li><a href="'+link(x[0])+'" data-sec="'+esc(x[0])
        +'"><b>'+esc(x[0])+'</b> '+esc(x[1])+'</a></li>';}).join(""):'<li class="lw-none">No section of this chapter is in force.</li>';
    });
  },true);

  // ---- THE FILTERS: topic, status and title, over the chapters the page
  // lists, in the bill search's groups (the person, 24 October 2026): a
  // group's head opens and shuts it, and how many are chosen in a group is
  // on its head, and on the Filter button that opens them under 60em, as on
  // /bills. What is chosen is in the address (?topic=Housing), which the page
  // reads when it opens, so a filtered list can be kept and sent.
  var rows=[].slice.call(root.querySelectorAll(".lw-ch")),titles=[].slice.call(root.querySelectorAll(".lw-title"));
  var side=document.getElementById("lwfacets"),tog=document.getElementById("lwftoggle"),
      clear=document.getElementById("lwclear"),form=document.getElementById("rsform");
  var NAMES={tp:"topic",st:"status",ti:"title"},SHOWN=[0,0];
  function inputs(name){return [].slice.call(side.querySelectorAll('input[name="'+name+'"]'));}
  function picked(name){return inputs(name).filter(function(x){return x.checked;}).map(function(x){return x.value;});}
  function anyPicked(){return picked("st").length+picked("tp").length+picked("ti").length;}
  function keep(li){
    var st=picked("st"),tp=picked("tp"),ti=picked("ti");
    if(st.length){var ok=st.some(function(v){return v==="in"?li.getAttribute("data-rep")!=="1":
      v==="rep"?li.getAttribute("data-rep")==="1":Number(li.getAttribute("data-pend"))>0;});if(!ok)return false;}
    if(tp.length){var mine=(li.getAttribute("data-topics")||"").split("|");if(!tp.some(function(v){return mine.indexOf(v)>=0;}))return false;}
    if(ti.length&&ti.indexOf(li.getAttribute("data-title"))<0)return false;
    return true;}
  // A chapter the search finds is kept where its row is.
  function keepCh(c){var li=root.querySelector('.lw-ch[data-ch="'+c+'"]');return !li||keep(li);}
  function head(key){return side.querySelector('.fhead[data-lwg="'+key+'"]');}
  function openGroup(h,on){
    if(!h)return;
    h.setAttribute("aria-expanded",on?"true":"false");h.parentNode.classList.toggle("open",on);
    var b=document.getElementById(h.getAttribute("aria-controls"));if(b)b.hidden=!on;}
  side.addEventListener("click",function(e){
    var h=e.target.closest&&e.target.closest(".fhead[data-lwg]");
    if(h)openGroup(h,h.getAttribute("aria-expanded")!=="true");});
  // Under 60em the groups are behind the Filter button, shut until it is
  // pressed; Escape inside them shuts them and goes back to the button.
  if(tog)tog.addEventListener("click",function(){
    var on=!root.classList.contains("fopen");root.classList.toggle("fopen",on);
    tog.setAttribute("aria-expanded",on?"true":"false");});
  root.addEventListener("keydown",function(e){
    if(e.key!=="Escape"||!tog||!root.classList.contains("fopen")||!(e.target.closest&&e.target.closest("#lwfacets,#lwftoggle")))return;
    root.classList.remove("fopen");tog.setAttribute("aria-expanded","false");tog.focus();});
  function badges(){
    var all=0;
    Object.keys(NAMES).forEach(function(k){var n=picked(k).length,b=head(k)&&head(k).querySelector(".badge");all+=n;
      if(b){b.textContent=n?String(n):"";b.hidden=!n;}});
    var tb=tog&&tog.querySelector(".badge");if(tb){tb.textContent=all?String(all):"";tb.hidden=!all;}
  }
  function address(){
    try{
      var p=new URLSearchParams(location.search);
      Object.keys(NAMES).forEach(function(k){p.delete(NAMES[k]);picked(k).forEach(function(v){p.append(NAMES[k],v);});});
      var s=p.toString(),want=location.pathname+(s?"?"+s:"")+location.hash;
      if(want!==location.pathname+location.search+location.hash)history.replaceState(history.state,"",want);
    }catch(e){}
  }
  // The count under the box: the chapters listed, or the search's hits.
  function tell(hits){
    if(hits!=null){count.textContent=hits.toLocaleString()+(hits===1?" match":" matches")
      +(anyPicked()?" in the filters chosen":"");return;}
    count.textContent=anyPicked()?SHOWN[0].toLocaleString()+" chapter"+(SHOWN[0]===1?"":"s")+" in "+SHOWN[1]
      +" title"+(SHOWN[1]===1?"":"s")+" match":count.getAttribute("data-all");
  }
  function filter(){
    var any=anyPicked(),shown=0,ts=0;
    rows.forEach(function(li){var k=keep(li);li.hidden=!k;if(k)shown++;});
    titles.forEach(function(t){var n=t.querySelectorAll(".lw-ch:not([hidden])").length;t.hidden=!n;
      if(n)ts++;var c=t.querySelector(".lw-tn");if(c)c.textContent=any?n+" of "+c.getAttribute("data-all"):c.getAttribute("data-all");
      if(any&&n&&n<=40)t.open=true;});
    SHOWN=[shown,ts];
    clear.hidden=!any;badges();address();
    // The search's hits are held to the filters too, as the bill search's are.
    if(box.value.trim())run();else tell();
  }
  side.addEventListener("change",function(e){if(e.target.matches&&e.target.matches("input[type=checkbox]"))filter();});
  clear.addEventListener("click",function(){
    inputs("st").concat(inputs("tp"),inputs("ti")).forEach(function(x){x.checked=false;});
    titles.forEach(function(t){t.open=false;});filter();});

  // ---- THE SEARCH: a number goes straight to it; words are ranked across the
  // chapters' names, the sections' headings and what each section is about.
  function stem(w){w=w.toLowerCase().replace(/^'+|'+$/g,"");if(/'s$/.test(w))w=w.slice(0,-2);
    if(w.length>4&&/ies$/.test(w))return w.slice(0,-3)+"y";
    if(w.length>3&&/s$/.test(w)&&!/ss$/.test(w))return w.slice(0,-1);return w;}
  var STOP=" a an and are as at be by for from in is it of on or the to with any all under ";
  function words(q){return (q.toLowerCase().match(/[a-z][a-z']{1,}/g)||[]).filter(function(w){
    return STOP.indexOf(" "+w+" ")<0;}).map(stem);}
  function has(text,w){return (text.toLowerCase().match(/[a-z][a-z']+/g)||[]).some(function(x){
    return stem(x)===w||(w.length>=4&&x.indexOf(w)===0);});}
  var CITE=/^\\s*(?:rsa\\s*)?(?:chapter\\s*)?(\\d{1,3}(?:-[a-z]{1,2})?)(?::\\s*([0-9a-z.\\-]+))?\\s*$/i;
  function label(a,ch,hd){var c=chOf(a),info=ch[c]||[];
    if(a.indexOf(":")<0)return "Chapter "+c+": "+(info[0]||"");
    var h=(hd.filter(function(x){return x[0]===a;})[0]||[])[1]||"";return h;}
  function show(list,note){
    var on=!!(list||note);
    dir.hidden=on;
    out.innerHTML=!on?"":(note?'<p class="rs-note">'+esc(note)+'</p>':'')+(list&&list.length?'<ol class="rs-hits">'
      +list.slice(0,60).map(function(r){var sec=r[0].indexOf(":")>=0;
        return '<li><a href="'+link(r[0])+'"'+(sec?' data-sec="'+esc(r[0])+'"':'')+'>'
          +(sec?'<b>RSA '+esc(r[0])+'</b> ':'')+esc(r[1]||"")+'</a>'
          +(sec&&CH&&CH[chOf(r[0])]?' <span class="rs-in">in Chapter '+esc(chOf(r[0]))+'</span>':'')+'</li>';}).join("")+'</ol>':'');
    tell(on?(list||[]).length:null);
  }
  function run(){
    var q=box.value.trim();
    if(!q){show(null,"");return;}
    var m=CITE.exec(q);
    Promise.all([chapters(),heads(),WD?WD:get("laws/words.json").then(function(d){return WD=d||{words:{}};})]).then(function(r){
      if(box.value.trim()!==q)return;
      var ch=r[0],hd=r[1],wd=r[2];
      if(m&&ch[m[1].toUpperCase()]){
        var c=m[1].toUpperCase(),a=c+(m[2]?":"+m[2]:"");
        show([[a,label(a,ch,hd)]].concat(m[2]?[[c,label(c,ch,hd)]]:[]),"By number:");
        if(m[2]&&!narrow())open(a);return;
      }
      var ws=words(q);if(!ws.length){show([],"");return;}
      var hit={},name={};
      function add(a,lab,w,pts){var h=hit[a]||(hit[a]={w:{},s:0});h.w[w]=1;h.s+=pts;if(lab)name[a]=lab;}
      Object.keys(ch).forEach(function(c){var known=(ch[c][4]||[]).join(" "),lab="Chapter "+c+": "+ch[c][0];
        ws.forEach(function(w){if(has(ch[c][0]||"",w))add(c,lab,w,3);
          else if(known&&has(known,w))add(c,lab+" (the "+ch[c][4][0]+")",w,3);});});
      hd.forEach(function(x){ws.forEach(function(w){if(has(x[1],w))add(x[0],x[1],w,2);});});
      var hs={};hd.forEach(function(x){hs[x[0]]=x[1];});
      ws.forEach(function(w){var i=0;(wd.words[w]||[]).forEach(function(g){i+=g;var a=(hd[i]||[])[0];
        if(a)add(a,hs[a],w,1);});});
      var list=Object.keys(hit).map(function(a){return [a,name[a]||hs[a]||"",Object.keys(hit[a].w).length,hit[a].s];})
        .filter(function(x){return x[2]>=Math.min(ws.length,Math.max(1,ws.length-1));})
        .filter(function(x){return keepCh(chOf(x[0]));})
        .sort(function(x,y){var cx=x[0].indexOf(":")<0,cy=y[0].indexOf(":")<0;
          return y[2]-x[2]||(cy-cx)||y[3]-x[3]||(x[0]<y[0]?-1:1);});
      var all=list.filter(function(x){return x[2]===ws.length;}).length;
      show(list,list.length?(all===list.length?"Matching every word:":all+" match every word; then the closest:")
        :"Nothing found. Try fewer words, "+(anyPicked()?"fewer filters, ":"")+"or a chapter number such as 91-A.");
    });
  }
  var t=null;box.addEventListener("input",function(){clearTimeout(t);t=setTimeout(run,180);});
  // The search's files are fetched once the box is chosen, not on the first
  // letter typed, so the first answer does not wait for them.
  box.addEventListener("focus",function(){chapters();heads();if(!WD)WD=get("laws/words.json").then(function(d){return WD=d||{words:{}};});},{once:true});

  // ---- A FILTER OFFERED FOR ITS NAME as the box is typed in (the person,
  // 24 October 2026): app.js's filterOffers and filterCombo, which the bill
  // search's box uses, given this page's filters -- a topic, a title by its
  // name, a status. Choosing one ticks it as a click in its group would, and
  // the words it stands for leave the box. app.js loads after this script,
  // so they are taken up once the page has; without them the box searches
  // as it always has.
  var offers=null;
  var SAY_ST={"in":"All chapters <b>in force</b>","pend":"All chapters with <b>pending changes</b>",
              "rep":"All <b>repealed or moved</b> chapters"};
  function named(x){var lab=x.closest("label"),s=lab&&(lab.querySelector(".tname > span")||lab.querySelector("span"));
    return s?s.textContent:x.value;}
  function counted(x){var c=x.closest("label").querySelector(".c");return c?Number(c.textContent.replace(/,/g,"")):null;}
  function lawOffers(q){
    if(CITE.test(q)||!window.filterOffers)return [];
    function vals(k){return inputs(k).filter(function(x){return !x.checked;}).map(function(x){return [x.value,named(x),counted(x)];});}
    return window.filterOffers(q,[
      {key:"tp",values:vals("tp"),say:function(n){return "All chapters with the topic <b>"+esc(n)+"</b>";}},
      {key:"ti",values:vals("ti"),say:function(n,v){return "All chapters in <b>Title "+esc(v)+": "+esc(n)+"</b>";}},
      {key:"st",values:vals("st"),say:function(n,v){return SAY_ST[v]||esc(n);}}]);
  }
  function take(o){
    var x=inputs(o.key).filter(function(i){return i.value===o.v;})[0];
    if(!x)return;
    x.checked=true;openGroup(head(o.key),true);
    box.value=o.rest;clearTimeout(t);
    if(!o.rest)show(null,"");
    filter();
  }
  form.addEventListener("submit",function(e){
    e.preventDefault();
    // Return takes the offer the arrow keys are on; with none, the words are
    // searched, as they always were.
    if(offers&&offers.enter())return;
    clearTimeout(t);run();
  });
  function wire(){
    if(offers||!window.filterCombo)return;
    offers=window.filterCombo(box,{offers:lawOffers,choose:take,label:"Filters that match the words typed"});
  }
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",wire);else wire();

  // ---- WHAT THE ADDRESS NAMES: the filters chosen (?topic=, ?status=,
  // ?title=, each as often as chosen), their groups open; and a search, as
  // the box's form sends one where the page's script has not loaded.
  (function(){
    var p;try{p=new URLSearchParams(location.search);}catch(e){return;}
    Object.keys(NAMES).forEach(function(k){p.getAll(NAMES[k]).forEach(function(v){
      inputs(k).forEach(function(x){if(x.value===v){x.checked=true;openGroup(head(k),true);}});});});
    if(p.get("q"))box.value=p.get("q");
  })();
  // A title linked from a chapter's breadcrumb (/laws#t-VI) opens.
  var h=location.hash.match(/^#t-(.+)$/);if(h){var d=document.getElementById("t-"+decodeURIComponent(h[1]));if(d){d.open=true;}}
  filter();
})();
</script>"""


# WHEN THE TABLE WAS TAKEN: db/_manifest.json's "fetched" for NH_RSA, which
# the weekly refreshes (nightly.STATUTE_VIEWS). Set by main(); "" where the
# manifest does not say, and then the pages say nothing of it.
TABLE_TAKEN = ""


def taken_on(db):
    """'September 8, 2026' from <db>/_manifest.json's NH_RSA entry, or ""."""
    try:
        got = json.loads((Path(db) / "_manifest.json").read_text(encoding="utf-8"))["NH_RSA"]["fetched"]
        d = datetime.date.fromisoformat(str(got)[:10])
    except (OSError, ValueError, KeyError, TypeError):
        return ""
    return C.date_words(d, "full")


def as_of(latest, today=None):
    """The lead's sentences on how current the text is.

    IN THE PERSON'S WORDS (approved 17 October 2026): "Includes changes
    through 2025; 2026 laws not yet included." It said the table held the
    text "through the laws of 2025", which left a reader to work out that a
    law of 2026 was not in it.

    AND ONLY ONCE THERE CAN BE SUCH LAWS (the audit of 25 October 2026, S7):
    the next year's laws are said not to be included from the January its
    session opens, `today` being build_date.today() unless a caller states
    it. In October 2026, with the table through 2026, the page said "2027
    laws not yet included" of a session that had not begun."""
    taken = (f" Taken from the General Court's database on {E(TABLE_TAKEN)}."
             if TABLE_TAKEN else "")
    y = str(latest or "")
    if not y.isdigit():
        return taken.strip()
    today = today or build_date.today()
    later = f"; {int(y) + 1} laws not yet included" if today.year > int(y) else ""
    return f"Includes changes through {E(y)}{later}.{taken}"


def landing_page(tmpl, table, data, base, topics, pending, con=None):
    """THE LAWS AS THE BILL SEARCH IS LAID OUT (the person, 11 October 2026):
    filters at the side, the directory of titles and chapters in the middle
    -- each title saying which chapters it holds before it is opened, as the
    General Court's own table of contents does -- and a section's text on the
    right when one is chosen, with the way to its own page.

    AND MORE AS THE BILL SEARCH IS (the person, 24 October 2026): the search
    box across the top with the count under it, and the filters as the bill
    search's groups, Topic open and Status and Title shut; under 60em, behind
    the bill search's Filter button. Typing a filter's name in the box offers
    that filter (LANDING_JS, app.js filterCombo).

    AND THE CONSTITUTION ON A TAB OF ITS OWN (the person, 17 October 2026),
    from collected/constitution.json, which `con` is when a check hands it
    in. The statutes are the first tab and read as they did, their lead at
    the top of their panel; a disk without the file builds the page as it
    was, with no tabs."""
    path = "/laws"
    title = "New Hampshire Laws"
    con = PC.load() if con is None else con
    p = S.page(tmpl, path=path, base=base,
               title=S.title_of("New Hampshire Laws", "every chapter of the RSA"),
               jsonld=LD.listing("New Hampshire Revised Statutes Annotated",
                                 "Every chapter of the New Hampshire Revised Statutes Annotated, "
                                 "with the bills that changed each section and the bills that would.",
                                 base, "/laws"),
               og_title=title, description="Every chapter of the New Hampshire Revised Statutes "
               "Annotated: browse by title or topic, search by number or words, with the bills that "
               "changed each section and the bills that would."
               + (" And the state Constitution, article by article." if con else ""),
               og_image="og-learn.png", og_alt=OG_ALT,
               globals={"GR_STATIC": True}, noscript="", skip_label="Skip to the laws",
               sr_title="", nav_current="laws.html", cite=False)
    latest = data.get("asof", {}).get("laws_through") or ""
    rsa_lead = ('The Revised Statutes '
                'Annotated (RSA), chapter by chapter: '
                f'each section with the bills that changed it and the bills that would. {as_of(latest)}')
    head_lead = ("The state Constitution, and the statutes the General Court passes under it, the "
                 "Revised Statutes Annotated (RSA)." if con else rsa_lead)
    head = (f'<header class="l-head"><h1>{E(title)}</h1><p class="l-lead">{head_lead}</p>'
            + S.cite_block(path, title, base, S.BUILT) + "</header>")
    groups = collections.OrderedDict()
    for ch in sorted(table.chapters, key=rsa.chap_key):
        info = table.chapters[ch]
        groups.setdefault((info["title_no"], info["title"]), []).append(ch)
    # Counted over the chapters the page lists: a bill can name a chapter the
    # table does not hold, and the filter then promised rows it could not show.
    tcount = collections.Counter(t for c, ts in topics.items() if c in table.chapters for t in ts)
    n_rep = sum(1 for c in table.chapters.values() if c["repealed"])
    n_pend = sum(1 for c in table.chapters if pending.get(c))
    blocks, title_opts = [], []
    for (tno, tname), chs in groups.items():
        tl, tn = title_label(tno, tname)
        live = [c for c in chs if not table.chapters[c]["repealed"]]
        span = f"Chapters {chs[0]} to {chs[-1]}" if len(chs) > 1 else f"Chapter {chs[0]}"
        lis = []
        for c in chs:
            info = table.chapters[c]
            label = chapter_label(c, info["name"])
            pend = len(pending.get(c, []))
            badges = ((f'<span class="lw-badge lw-rep">{"Moved" if moved_to(info.get("note")) else "Repealed"}'
                       '</span>' if info["repealed"] else "")
                      + (f'<span class="lw-badge lw-pend">{pend} pending</span>' if pend else ""))
            # THE LEAST A CHAPTER NEEDS UNTIL IT IS OPENED (the polish of 12
            # October 2026): its sections, its label and its title's name are
            # drawn by LANDING_JS from what is here when it opens. Written
            # into every one of 1,786 rows they were about half the page.
            #
            # BUT THE WAY TO ITS OWN PAGE IS IN THE HTML (the sitemap audit,
            # 16 October 2026). It was drawn by the script too, only once a
            # reader opened the row, and a crawler opens none: /laws linked
            # no chapter at all, and 315 chapter pages had no link from
            # anywhere on the site. So each row carries one plain link,
            # "RSA 3-A", beside its summary and not inside it: a link inside
            # a <summary> would make the chapter's name a second control in
            # the one that opens the row, and a click on the name would leave
            # the page instead of listing the sections, which is what the
            # row is for. app.css sets it at the row's right, level with the
            # name, on a phone as on a desktop.
            topic_attr = f' data-topics="{E("|".join(topics.get(c, [])))}"' if topics.get(c) else ""
            lis.append(
                f'<li class="lw-ch" data-ch="{E(c)}" data-title="{E(tno)}"'
                + (' data-rep="1"' if info["repealed"] else "") + (f' data-pend="{pend}"' if pend else "")
                + f'{topic_attr}><details class="lw-chd"><summary><span class="lw-chn">Chapter {E(c)}:</span> '
                f'<span class="lw-chname">{E(nice(info["name"]))}</span>{badges}</summary></details>'
                f'<a class="lw-go" href="{E(chapter_path(c))}">RSA {E(c)}</a></li>')
        blocks.append(
            f'<details class="lw-title" id="t-{E(tno)}"><summary><span class="lw-tno">{E(tl)}</span>'
            f'<span class="lw-tname">{E(tn)}</span><span class="lw-tspan">{E(span)} &middot; '
            f'<span class="lw-tn" data-all="{len(chs)} chapters">{len(chs)} chapters</span></span>'
            # A title's first three chapter names stood under its count until
            # 14 October 2026; the person asked for the count alone.
            f'</summary><ul class="lw-chs">{"".join(lis)}</ul></details>')
        title_opts.append(f'<label class="fopt"><input type="checkbox" name="ti" value="{E(tno)}">'
                          f'<span class="tname"><b class="tcode">{E(tno)}</b><span>{E(tn)}</span></span>'
                          f'<span class="c">{len(chs):,}</span></label>')
    # THE TOPICS BY NAME (the person, 24 October 2026: "Topics in the rsa
    # pages should be sorted alphabetically"), case and accents set aside
    # (shown_order). They ran by how many chapters each holds.
    topic_opts = "".join(f'<label class="fopt"><input type="checkbox" name="tp" value="{E(t)}">'
                         f'<span>{E(t)}</span><span class="c">{n:,}</span></label>'
                         for t, n in sorted(tcount.items(), key=lambda x: shown_order(x[0])))
    n_all = len(table.chapters)
    status_opts = "".join(
        f'<label class="fopt"><input type="checkbox" name="st" value="{v}"><span>{w}</span>'
        f'<span class="c">{n:,}</span></label>'
        for v, w, n in (("in", "In force", n_all - n_rep), ("pend", "Pending changes", n_pend),
                        ("rep", "Repealed or moved", n_rep)))

    def group(key, label, body, opened=False, whole=False):
        """A filter as the bill search draws one (app.js fgroup): its head a
        button that opens and shuts it, with the count chosen in a badge."""
        return (f'<div class="fgroup{" open" if opened else ""}"><button type="button" class="fhead" '
                f'data-lwg="{key}" aria-expanded="{"true" if opened else "false"}" aria-controls="lwg-{key}">'
                f'<span>{label}</span><span class="badge" hidden></span><span class="chev" aria-hidden="true">'
                f'&#9656;</span></button><div class="fbody{" whole" if whole else ""}" id="lwg-{key}"'
                f'{"" if opened else " hidden"}>{body}</div></div>')
    # THE SEARCH AT THE TOP AND THE FILTERS ON THE LEFT, AS THE BILL SEARCH
    # HAS THEM (the person, 24 October 2026: "the searchbar at the top, the
    # filters on the left side that are dropdowns closed by default except
    # for the first one which is the most common filter to be used, likely
    # topics for the laws page"). The bill search's own parts and classes --
    # the box and its Return key (.qline, .qbox), the count under it (.qhint),
    # the groups (.fgroup, .fhead, .fbody, .fopt) and, under 60em, the button
    # that opens them (.ftoggle) -- so the two read as one search; app.css
    # carries the few rules the Laws page's place in the template needs.
    search = (
        '<div class="lw-q" role="search" aria-label="Search the laws">'
        '<form id="rsform" class="qline" action="/laws"><label for="rsq" class="sr">Search the laws</label>'
        '<div class="qbox"><input id="rsq" name="q" type="search" spellcheck="false" autocomplete="off" '
        'placeholder="Chapter, section or key words"><button id="rsgo" type="submit" '
        'title="Search" aria-label="Search">&#8629;</button></div></form>'
        f'<p class="qhint"><span class="lw-count" id="lwcount" role="status" aria-live="polite" aria-atomic="true" '
        f'data-all="{n_all:,} chapters in {len(groups)} titles">{n_all:,} chapters in {len(groups)} titles</span></p>'
        '</div>')
    toggle = ('<button class="ftoggle" id="lwftoggle" type="button" aria-expanded="false" aria-controls="lwfacets">'
              '<span>Filter by topic, status or title</span><span class="badge" hidden></span>'
              '<span class="chev" aria-hidden="true">&#9656;</span></button>')
    side = (
        '<aside class="facets lw-side" id="lwfacets" aria-label="Filters">'
        + group("tp", "Topic", '<p class="lw-fnote">From the bills that changed each chapter.</p>' + topic_opts,
                opened=True)
        + group("st", "Status", '<p class="lw-fnote">Pending: a bill now before the General Court, or a law '
                'passed and not yet in effect.</p>' + status_opts, whole=True)
        + group("ti", "Title", "".join(title_opts))
        + '<button type="button" class="link lw-clear" id="lwclear" hidden>Clear all filters</button></aside>')
    middle = ('<section class="lw-dir" aria-label="The laws by title">'
              '<div id="rsout" aria-live="polite"></div>'
              f'<div id="lwdir">{"".join(blocks)}</div></section>')
    reader = ('<aside class="lw-read" id="lwread" aria-label="The section chosen" aria-live="polite">'
              '<p class="lw-empty">Choose a chapter, then a section, to read it here.</p></aside>')
    art = f'{search}<div class="lw" id="lw">{toggle}{side}{middle}{reader}</div>'
    if con:
        # The constitution's sidebar is a chapter page's, so the chapter
        # page's script marks the article being read in it.
        art = CT.tabbed(art, rsa_lead, con) + CHAPTER_JS
        # The search first in its panel, above the panel's lead: at the top,
        # as the bill search's is (the person, 24 October 2026).
        lead = f'<p class="l-lead">{rsa_lead}</p>'
        assert art.count(lead + search) == 1, "the statutes' panel no longer opens with its lead and the search"
        art = art.replace(lead + search, search + lead, 1)
    return p.replace('<div id="results"></div>',
                     f'<div id="results"><div class="l-page rs-page rs-landing">{head}{art}</div>{LANDING_JS}</div>', 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    ap.add_argument("--site", default="site")
    ap.add_argument("--base", default="https://graniterecord.org")
    ap.add_argument("--only", nargs="*", help="build these chapters alone (for a look), not the set")
    # The fixture's own table, which preflight's chain builds the Laws pages
    # from: the nav links laws.html from every page, so a fixture without
    # them is a site of broken links.
    ap.add_argument("--db", help="the folder holding NH_RSA.psv and _columns.json (default: db/)")
    a = ap.parse_args()
    site = Path(a.site)
    table = rsa.load(Path(a.db) / "NH_RSA.psv", Path(a.db) / "_columns.json") if a.db else rsa.load()
    global TABLE_TAKEN
    TABLE_TAKEN = taken_on(a.db or rsa.TABLE.parent)
    cit = Path("rsa_citations.json")
    if table is None or not cit.is_file():
        print("build_rsa: no statute table or rsa_citations.json here; no statute pages written")
        return 0
    data = json.loads(cit.read_text(encoding="utf-8"))
    current = term_of_year(build_date.today().year)
    bills = Bills(site, current, table=table)
    tmpl = S.template(site)
    out = site / "laws"
    out.mkdir(parents=True, exist_ok=True)
    chs = [c.upper() for c in a.only] if a.only else sorted(table.chapters, key=rsa.chap_key)
    n_marks = n_marked = 0
    for ch in chs:
        chapter_file(out, ch).parent.mkdir(parents=True, exist_ok=True)
        page = S.clean_links(chapter_page(tmpl, table, data, bills, ch, a.base))
        chapter_file(out, ch).write_text(page, encoding="utf-8")
        n = page.count('<a class="rs-tm"')
        n_marks, n_marked = n_marks + n, n_marked + bool(n)
    # SAID EITHER WAY, as the Constitution tab is below: a table that defines
    # terms and pages that mark none is a reader that has stopped reading.
    d = table.defined()
    print(f"build_rsa: {d.terms_found:,} defined terms in {d.sections_read:,} sections; "
          f"{sum(len(x.terms) for x in d.defs):,} with a scope read, {sum(d.skipped.values()):,} left unmarked "
          f"for a scope not read; {n_marks:,} marked uses on {n_marked:,} chapter pages"
          + ("" if n_marks or not d.terms_found else " -- NO defined term marked on any page"))
    stale = out / "404.html"       # an earlier build's RSA 404, before chapter_file
    if not a.only and stale.is_file():
        stale.unlink()
    topics, pending = chapter_topics(data, bills), chapter_pending(data, bills)
    (site / "laws.html").write_text(S.clean_links(landing_page(tmpl, table, data, a.base, topics, pending)), encoding="utf-8")
    chapters, headings, words = build_indexes(table, data, topics, pending)
    for name, obj in (("chapters.json", chapters), ("headings.json", headings), ("words.json", words)):
        (out / name).write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")),
                                encoding="utf-8")
    sizes = {n: (out / n).stat().st_size for n in ("chapters.json", "headings.json", "words.json")}
    passing = bills.passing(data)
    unread = sum(1 for p in passing.values() if not p.effect.parts)
    print(f"build_rsa: {len(topics):,} of {len(table.chapters):,} chapters with a topic from their bills, "
          f"{len(pending):,} with a change pending; {len(passing):,} bills passed and not yet in effect "
          f"in {len({a.split(':')[0] for p in passing.values() for a in p.addrs}):,} chapters, "
          f"{unread:,} of them with no effective date read ({len(bills._records):,} records read)")
    print(f"build_rsa: {len(chs):,} chapter pages and the landing page; search files "
          + ", ".join(f"{n} {s / 1e6:.1f} MB" for n, s in sizes.items()))
    # SAID EITHER WAY: a landing page without its Constitution tab is a page
    # that lost a part, and must not pass in silence.
    con = PC.load()
    print("build_rsa: " + (f"the Constitution tab, {sum(con['counts'].values())} articles"
                           if con else f"NO Constitution tab: {PC.OUT.name} is not on this disk"))
    if not a.only:
        S.sitemap_merge(site, a.base, [a.base + "/laws"] + [a.base + chapter_path(c) for c in chs],
                        owns="/laws")
    return 0


if __name__ == "__main__":
    sys.exit(main())
