#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-05.38
"""
Generate the faceted site from real General Court data.

    python3 build_site_v2.py --data data --out site

Reads (all optional except data/):
    data/*.json              from build_data.py
    narratives.json          from narrative.py --all
    rollcalls.json           from rollcall_parser.py --all
    verification_manifest.csv  from build_manifest.py
    segments/<videoid>.json  from transcribe_and_align.py
    committee_reports.json   from fetch_committee_reports.py

Design note: 131,199 member votes are far too much to ship to a browser at
once, so this writes a small search index plus one JSON file per bill. The
index drives search and the facets; a bill's votes, sponsors and hearings load
only when that bill is expanded. Initial load stays a few hundred KB no matter
how many roll calls a session produced.

Standard library only.
"""

import argparse
import narrative as N
import proceedings as P
import csv
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import date as _date, timedelta as _td
from pathlib import Path

STATUS_ORDER = ["law", "veto", "done", "active"]


def load(p, default):
    p = Path(p)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default



# Sign-ins are filed for a public hearing, so the count belongs on that line.
PUBLIC_HEARING = re.compile(r"public hearing", re.I)


AMEND_NUM = re.compile(r"#\s*(\d{4}-\d+[a-z]?)", re.I)
AMEND_ANY = re.compile(r"\b(\d{4}-\d{3,4}[a-z]?)\b")
# AA is adopted, AF and AL are not. The docket's own abbreviations.
ADOPTED = {"AA": True, "ADOPTED": True, "AF": False, "AL": False}


# What an amendment says it changes. New Hampshire amendments are written as
# instructions rather than as a redline: "Amend RSA 415:6-e, III(a) as inserted
# by section 1 of the bill by replacing it with the following". So the targets
# can be read off the instruction, and two amendments touching the same target
# is the case where the later one governs.
RSA_CITE_T = re.compile(
    r"\bRSA\s+(\d{1,3}(?:-[A-Z])?:\d+(?:-[a-z])?"
    r"(?:,\s*[IVXLC]+(?:-[a-z])?)?(?:\([a-z]\))?)", re.I)
# Where the instruction stops and the new text begins. Everything after this is
# what the amendment INSERTS, and the statutes quoted in there are not the ones
# it changes -- an amendment replacing one paragraph may quote a dozen others
# around it.
PREAMBLE_END = re.compile(
    r"with the following|to read as follows|as follows\s*:", re.I)
TARGET_SECT = re.compile(
    r"\b(?:replacing|inserting after|deleting|amending)\s+section\s+(\d+)", re.I)
TARGET_ALL = re.compile(r"replacing all after the enacting clause", re.I)


def amendment_targets(text):
    """The parts of the bill or the statutes an amendment says it changes."""
    if not text:
        return []
    out = []
    if TARGET_ALL.search(text):
        out.append("the whole bill")
    # Only the instruction, so "Amend RSA 91-A:4 and RSA 91-A:1-a" gives both
    # and the statutes quoted in the replacement text give none.
    stop = PREAMBLE_END.search(text)
    head = text[:stop.start()] if stop else text[:400]
    if re.search(r"\bAmend\b", head, re.I):
        for m in RSA_CITE_T.finditer(head):
            v = "RSA " + re.sub(r"\s+", " ", m.group(1)).strip()
            if v not in out:
                out.append(v)
    for m in TARGET_SECT.finditer(text):
        v = f"section {m.group(1)}"
        if v not in out:
            out.append(v)
    return out[:8]


# The General Court prints an ANALYSIS above the bill: a plain-language
# summary written by the people who drafted it. Splitting it off means the
# reader meets that before several thousand words of statute -- and it is the
# drafters' own summary, not this site's, which makes it worth more.
ENACTING = re.compile(
    r"^\s*(?:Be it Enacted|That the following|Whereas\b|RESOLVED\b)", re.M | re.I)
# The General Court prints a rule of spaced dashes between the analysis and the
# bill's front matter. Read as text it is a line of "- - - - - -", and it ended
# up inside the analysis along with everything after it.
DASH_RULE = re.compile(r"^[\s\-\u2013\u2014_=]{10,}$", re.M)
# The drafting legend, which describes formatting the reader cannot see here.
# We say the same thing in our own words next to the text, so printing theirs
# as though it were the bill's summary is both wrong and confusing.
LEGEND = re.compile(
    r"(?:Matter (?:removed|added|which is)[^\n]*|Explanation:[^\n]*|"
    r"\[?in brackets and struck ?through[^\n]*)", re.I)
# "26-2608 07/06", "STATE OF NEW HAMPSHIRE", "In the Year of Our Lord ...",
# "AN ACT ..." -- the bill's formal opening. It belongs with the bill, not with
# the summary of it.
FRONT = re.compile(
    r"^\s*(?:\d{2}-\d{3,4}(?:\s+\d{2}/\d{2})?|STATE OF NEW HAMPSHIRE|"
    r"In the Year of Our Lord[^\n]*|AN ACT\b[^\n]*|A RESOLUTION\b[^\n]*|"
    r"CACR\s*\d+[^\n]*)\s*$", re.M | re.I)
# "Explanation: Matter added to current law appears in bold italics." The
# General Court says this on the page, and it is true of the PDF and false of
# the text, because bold and italic do not survive extraction.
EXPLANATION = re.compile(r"^\s*Explanation:.*$", re.M | re.I)


def bill_text_block(rec):
    """The analysis and the text itself, told apart."""
    if not rec:
        return None
    body = rec.get("text") or ""
    if not body:
        return None
    cut = ENACTING.search(body)
    analysis = body[:cut.start()] if cut else ""
    rest = body[cut.start():] if cut else body
    # The analysis is what sits between its heading and the rule under it.
    # Everything after that rule -- the drafting legend, the LSR number, the
    # formal opening -- is the bill's own front matter and was being printed as
    # though the drafters had written it as a summary.
    rule = DASH_RULE.search(analysis)
    if rule:
        front = analysis[rule.end():]
        analysis = analysis[:rule.start()]
        rest = (FRONT.sub("", LEGEND.sub("", front)).strip() + "\n" + rest).strip()
    analysis = LEGEND.sub("", EXPLANATION.sub("", analysis)).strip()
    # "ANALYSIS" or "AMENDED ANALYSIS", and any rule printed above it.
    analysis = re.sub(r"^[\s\u2500-\u257F_=-]*(?:[A-Z]+\s+)?ANALYSIS\s*", "",
                      analysis, flags=re.I).strip()
    return {"version": rec.get("version") or "",
            "title": rec.get("title") or "",
            "analysis": analysis,
            "body": rest.strip(),
            "in_text": rec.get("amendments_in_text") or [],
            "chars": len(body)}


def bill_amendments(narr, texts):
    """Every amendment on one bill, in the order the docket took them up.

    Order is the whole point. A committee amendment is considered before any
    floor amendment, and where two touch the same section the later one wins,
    so a list sorted any other way describes a bill that does not exist. The
    docket is already chronological, so it is simply not re-sorted.

    Text is attached where the calendars had it and left absent where they did
    not. An amendment nobody can read is still an amendment that was moved,
    and dropping it would hide a step rather than a document.
    """
    out, seen = [], set()
    for e in (narr or {}).get("events", []):
        if e.get("type") != "amendment" or e.get("cancelled"):
            continue
        num = (e.get("amendment") or "").strip()
        if not num:
            m = AMEND_NUM.search(e.get("raw", "")) or AMEND_ANY.search(e.get("raw", ""))
            num = m.group(1) if m else ""
        if not num or num in seen:
            continue
        seen.add(num)
        kind = (e.get("amend_kind") or "").strip() or "Amendment"
        doc = texts.get(num) or {}
        out.append({
            "num": num,
            "kind": kind,
            # Committee or floor is not a label this invents: it is the word
            # the docket line used, and where the line says only "Amendment"
            # that is what the reader is told.
            "where": ("committee" if "committee" in kind.lower()
                      else "floor" if "floor" in kind.lower()
                      else "enrolment" if "enrolled" in kind.lower() else ""),
            "date": e.get("date"), "body": e.get("body"),
            "adopted": ADOPTED.get((e.get("motion") or "").upper()),
            "vote_kind": e.get("vote_kind") or "",
            "mover": e.get("mover") or "",
            "proposed_by": doc.get("proposed_by") or "",
            "text": doc.get("text") or "",
            "source": doc.get("source") or "",
            "targets": amendment_targets(doc.get("text") or ""),
        })

    # Where a later amendment touches something an earlier one already
    # touched. That is the case the reader most needs pointed out, because
    # both were adopted and only the later one is in the bill.
    for i, a in enumerate(out):
        clash = []
        for b in out[:i]:
            shared = [x for x in a["targets"] if x in b["targets"]]
            if shared and a.get("adopted") and b.get("adopted"):
                clash.append({"num": b["num"], "shared": shared})
        a["supersedes"] = clash
    return out
VOTE_KIND_RE = re.compile(r"\b(RC|VV|DV)\b")


def vote_chronology(rcs, narr):
    """Put a day's votes back in the order they happened, and name amendments.

    Two problems, one cause. The votes tab sorted by question text inside a
    date, so a tabling motion came before the vote it interrupted because "Lay"
    sorts before "Ought". And an amendment roll call is recorded as "Adopt
    Amendment" with no number, so two of them in a row are indistinguishable.

    The docket already answers both. It lists every floor action in the order
    it happened, names the amendment each one is about, and marks how each was
    decided. The roll call file numbers its votes in that same order. So the
    two are paired, in order, within a chamber and a day.

    The pairing is only used when the counts agree. If the docket shows three
    roll calls that day and the roll call file has four, something is missing
    from one of them and lining them up would put the wrong number beside the
    wrong vote -- so nothing is claimed and the votes fall back to their own
    numbering.

    Returns (order, names) keyed by (body, roll call number).
    """
    lines = defaultdict(list)
    for i, e in enumerate((narr or {}).get("events", [])):
        if e.get("cancelled"):
            continue
        raw = e.get("raw", "")
        vk = (e.get("vote_kind") or "").upper()
        if not vk:
            m = VOTE_KIND_RE.search(raw)
            vk = m.group(1) if m else ""
        if vk:
            lines[(e.get("date"), e.get("body"))].append((i, vk, raw))

    order, names = {}, {}
    for (date, body), evs in lines.items():
        rc_lines = [(i, raw) for i, vk, raw in evs if vk == "RC"]
        mine = sorted((r for r in rcs
                       if r.get("date") == date and r.get("body") == body),
                      key=lambda r: int(r.get("number") or 0))
        if len(rc_lines) != len(mine):
            continue
        for (i, raw), r in zip(rc_lines, mine):
            k = (r.get("body"), r.get("number"))
            order[k] = i
            am = AMEND_NUM.search(raw)
            if am and "amendment" in (r.get("question") or "").lower():
                names[k] = am.group(1)
    return order, names


# The year a published volume is from, out of the path in its own link. Two
# shapes, because the two files were fetched by different scripts:
#
#   .../Journals/2026/HJ 03 February 5, 2026.PDF
#   .../viewer.aspx?fileName=calendars%5C2026%5CNo10 March 6 2026.pdf
#
# Every one of the 188 keys on file yields a year this way.
SOURCE_YEAR = re.compile(r"(?:%5C|/)(\d{4})(?:%5C|/)", re.I)


def _cite(ev, sources, year=""):
    """The journal or calendar one docket action is printed in, as a link.

    A docket line cites "HJ 7" with no year, because within one session there
    is only one. Across sessions there is one per year, so the lookup is tried
    with the year first.

    It then used to fall back to the bare key, and that was wrong. calendars.json
    and journals.json each hold both forms -- "HC 10" beside "HC 10 2025" and
    "HC 10 2026" -- because their fetchers write the bare key too, and the bare
    key holds whichever year was fetched last. So a 2025 action citing HJ 3
    resolved to the 2026 journal: 4,468 of 12,970 links, a third of them,
    pointing at a volume that does not contain the action they claim to record.
    SR1 cited SJ 1 on a 2024 action and opened the 2026 Senate Journal.

    A missing citation is a gap. A citation to the wrong document is a false
    one, on a site whose whole claim is that it can be checked -- so the year in
    the resolved link is compared with the year of the action, and a link that
    disagrees is not offered at all. The citation itself is still printed; only
    the link is withheld.

    This used to take the line and search it. The line it was given had already
    been through narrative.clean(), which removes the citation so that the
    hearing pattern's venue group does not swallow "SC 4" -- so the search
    found nothing, on every event of every bill, and the comment below saying
    each action keeps its citation described something that never happened.
    narrative.py now takes it off the raw line and carries it on the event,
    which is where this reads it.
    """
    key = (ev.get("cite") or "").strip()
    if not key:
        return {}
    page = (ev.get("cite_page") or "").strip()
    out = {"cite": key + (f", page {page}" if page else "")}
    url = sources.get(f"{key} {year}") if year else None
    if not url:
        # The bare key, taken only where it agrees with the action's year.
        m = SOURCE_YEAR.search(sources.get(key, ""))
        if m and m.group(1) == year:
            url = sources[key]
    if url:
        out["cite_url"] = url
    return out


# The General Court's own status vocabulary, mapped to the four display states.
# Reading the field beats inferring it from docket prose: this is the fact most
# people come to the site for, and a wrong guess here is a wrong headline.
# What a bill of each kind actually has to clear before it is finished.
#
# Reading every bill as House, then Senate, then governor is right for HB and
# SB and wrong for everything else. A House Resolution is adopted by the House
# and that is the end of it; a concurrent resolution needs both chambers and
# never goes to the governor; a CACR needs both chambers and then the voters.
# Measured on this term: 32 adopted resolutions read "Passed one chamber" and
# three more read "In progress", one of them offering "Pending action in the
# other chamber" for a resolution that has no other chamber.
SINGLE_CHAMBER = {"HR": "House", "SR": "Senate"}
NO_GOVERNOR = {"HCR", "SCR", "CACR"}


def bill_prefix(bid):
    """HB1442 -> HB, CACR9 -> CACR. The letters, which say what kind it is."""
    m = re.match(r"^[A-Za-z]+", str(bid or ""))
    return m.group(0).upper() if m else ""


def for_bill_kind(needle, kind, label, prefix):
    """The same status word, read against what that kind of bill needs.

    "PASSED/ADOPTED" on a House Bill means one chamber down and one to go. On
    a House Resolution it is the final action. The status page does not make
    the distinction because it does not have to -- the reader knows which kind
    of thing they asked about, and this site has to say so.
    """
    if needle == "passed/adopted" and prefix in SINGLE_CHAMBER:
        return "adopted", f"Adopted by the {SINGLE_CHAMBER[prefix]}"
    if needle == "concurred" and prefix in NO_GOVERNOR:
        if prefix == "CACR":
            return "adopted", "Passed both chambers, goes to the voters"
        return "adopted", "Adopted by both chambers"
    return kind, label


STATED = [
    ("signed by governor", "law", "Signed into law"),
    # The field says "LAW WITHOUT SIGNATURE"; the needle wanted "became law
    # without signature" and so never matched it. Nine bills. Masked until
    # now because docket_outcome rescued every one of them from the docket.
    ("law without signature", "law", "Became law unsigned"),
    # The three outcomes of a veto, most specific first. A bill awaiting the
    # override vote, one where the override failed, and one where it succeeded
    # are three different situations, and lumping them as "Vetoed" hides the
    # only part anyone wants to know.
    ("veto overridden", "law", "Veto overridden, became law"),
    ("override adopted", "law", "Veto overridden, became law"),
    ("veto sustained", "veto", "Vetoed, override failed"),
    ("override failed", "veto", "Vetoed, override failed"),
    ("veto override", "veto", "Vetoed, override vote pending"),
    ("vetoed by governor", "veto", "Vetoed, awaiting an override vote"),
    ("inexpedient to legislate", "done", "Killed"),
    ("died on the table", "done", "Died on the table"),
    ("died, session ended", "done", "Died when the session ended"),
    # Parked for the committee to work on out of session, not killed.
    ("interim study", "study", "Referred for interim study"),
    ("indefinitely postponed", "done", "Indefinitely postponed"),
    ("laid on table", "active", "Laid on the table"),
    ("retained in committee", "active", "Retained in committee"),
    # The docket hyphenates; BodyStatusCodes.txt code 21 does not.
    ("re-referred", "active", "Re-referred to committee"),
    ("rereferred", "active", "Re-referred to committee"),
    # BEFORE "concurred", which is a substring of both of these. 21 bills
    # were live reading "Passed, awaiting the governor" when a chamber had
    # refused to concur -- the opposite of what happened, on the field the
    # site treats as most authoritative. BodyStatusCodes.txt has all three
    # as separate codes: 12 CONCURRED, 13 NONCONCURRED, 14 NONCONCURRED
    # REQUEST CONFERENCE.
    ("nonconcurred request conference", "active",
     "One chamber did not concur; a committee of conference was asked for"),
    ("nonconcurred", "active", "One chamber did not concur"),
    ("concurred", "active", "Passed, awaiting the governor"),
    ("passed/adopted", "active", "Passed one chamber"),
    ("in committee", "active", "In committee"),
]


# Docket lines that are procedural bookkeeping rather than steps in a bill's
# progress. Appointing an alternate to a committee of conference, or one member
# acceding to another's motion, is a real recorded action and is kept -- but it
# is not why anyone opened the page, and forty of them bury the four lines that
# matter.
#
# Nothing is discarded. Every action is still written to the bill's record and
# shown in full on its static page; the interactive view collapses these behind
# a toggle and says how many it is hiding.
ROUTINE = re.compile(
    r"\b(?:"
    r"appoint\w*\s+(?:alternate|conferee)|"
    r"alternate\s+(?:member|conferee)|"
    r"replaces\s+(?:Rep|Sen)\.|"
    r"accedes|"
    r"conference committee meeting|"
    r"committee meeting:|"
    r"(?:name|member)s?\s+(?:added|removed)|"
    r"reconsider(?:ation)?\s+(?:notice|filed)|"
    r"sponsor\s+(?:added|removed)|"
    r"enrolled bill amendment|"
    r"pending\s+(?:motion|question)|"
    r"lay on table\s*\(|"
    r"special order|"
    r"withdrawn from|"
    r"printed in|"
    r"referred to (?:the )?(?:committee on )?rules"
    r")", re.I)


# --------------------------------------------------------------------- RSA --
# A statute cites as "RSA 91-A:4", and its page lives at
#
#     /rsa/html/VI/91-A/91-A-4.htm
#             ^^ the TITLE, which the citation does not carry
#
# So the chapter has to be resolved to a title first. The General Court's own
# table of contents at /rsa/html/nhtoc.htm lists every title with the chapters
# it covers, and that is the table below, read from it on 4 September 2026.
#
# Chapters sort as (number, suffix), which is what makes the awkward pairs come
# out right: chapter 361 is Title XXXIII and 361-A is XXXIII-A; 227-F ends Title
# XIX and 227-G begins XIX-A. Comparing the pair handles both without a special
# case. A chapter in none of the ranges -- 251 to 258 exist in no title -- is
# not linked at all, because a citation link that 404s is worse than plain text.
RSA_TITLES = [
    ("I", "1", "21-V"), ("II", "22", "30-B"), ("III", "31", "53-G"),
    ("IV", "54", "70"), ("V", "71", "90"), ("VI", "91", "103"),
    ("VII", "104", "106-R"), ("VIII", "107", "119"), ("IX", "120", "124-A"),
    ("X", "125", "149-R"), ("XI", "150", "152"), ("XII", "153", "174"),
    ("XIII", "175", "180"), ("XIV", "183", "185"), ("XV", "186", "200-O"),
    ("XVI", "201", "202-B"), ("XVII", "203", "205-D"), ("XVIII", "206", "215-D"),
    ("XIX", "216", "227-F"), ("XIX-A", "227-G", "227-M"), ("XX", "228", "250"),
    ("XXI", "259", "269"), ("XXII", "270", "272"), ("XXIII", "273", "283"),
    ("XXIV", "284", "287-J"), ("XXV", "288", "288"), ("XXVI", "289", "291-A"),
    ("XXVII", "292", "303"), ("XXVIII", "304", "305-A"), ("XXIX", "306", "308"),
    ("XXX", "309", "332-N"), ("XXXI", "333", "359-U"), ("XXXII", "360", "360"),
    ("XXXIII", "361", "361"), ("XXXIII-A", "361-A", "361-E"),
    ("XXXIV", "362", "382"), ("XXXIV-A", "382-A", "382-A"),
    ("XXXV", "383", "397-B"), ("XXXVI", "398", "399-G"), ("XXXVII", "400", "420-Q"),
    ("XXXVIII", "421", "421-B"), ("XXXIX", "422", "424"), ("XL", "425", "439-A"),
    ("XLI", "444", "454-C"), ("XLII", "455", "456-B"), ("XLIII", "457", "461-B"),
    ("XLIV", "462", "465"), ("XLV", "466", "470"), ("XLVI", "471", "471-D"),
    ("XLVII", "472", "476"), ("XLVIII", "477", "479-B"), ("XLIX", "480", "480"),
    ("L", "481", "489-C"), ("LI", "490", "505"), ("LII", "506", "513"),
    ("LIII", "514", "526"), ("LIV", "527", "533"), ("LV", "534", "546-C"),
    ("LVI", "547", "567-A"), ("LVII", "568", "569"), ("LVIII", "570", "591"),
    ("LIX", "592", "614"), ("LX", "615", "623-C"), ("LXI", "624", "624"),
    ("LXII", "625", "651-F"), ("LXIII", "652", "671"), ("LXIV", "672", "679"),
]

# "RSA 91-A:4" / "RSA 638:26-a" / "RSA 91-A" / "RSA 91-A:2, III" -- the roman
# numeral after a comma is a paragraph within the section, not part of the
# address, so it is left out of the link and left in the sentence.
RSA_CITE = re.compile(r"\bRSA\s+(\d{1,3}(?:-[A-Z])?)(?::(\d{1,3}(?:-[a-z])?))?",
                      re.I)


def _chapter_key(ch):
    m = re.match(r"(\d+)(?:-([A-Za-z]+))?$", ch.strip())
    return (int(m.group(1)), (m.group(2) or "").upper()) if m else None


def rsa_url(chapter, section=None):
    """The General Court's own page for a citation, or "" if unresolvable."""
    key = _chapter_key(chapter)
    if not key:
        return ""
    for title, lo, hi in RSA_TITLES:
        klo, khi = _chapter_key(lo), _chapter_key(hi)
        if klo and khi and klo <= key <= khi:
            ch = chapter.upper()
            if section:
                return (f"https://gc.nh.gov/rsa/html/{title}/{ch}/"
                        f"{ch}-{section}.htm")
            return f"https://gc.nh.gov/rsa/html/NHTOC/NHTOC-{title}-{ch}.htm"
    return ""


def rsa_links(*texts):
    """{citation as written: url} for every statute cited in these strings.

    A map rather than rewritten text: the renderers escape what they print, and
    handing them HTML to escape would show the tags. They substitute after
    escaping, which is safe because a citation contains nothing to escape.
    """
    out = {}
    for txt in texts:
        for m in RSA_CITE.finditer(txt or ""):
            url = rsa_url(m.group(1), m.group(2))
            if url:
                out[m.group(0)] = url
    return out


def member_slug(m, lab):
    """jodi-nelson-rock-13, debra-altschiller-sd-24.

    Computed here so the search page and the static page agree on the address
    without either having to guess.

    House districts are numbered within a county -- Rockingham 13 and
    Hillsborough 13 are different places -- so the county has to be in the
    address. Senate districts are numbered once across the state, so the number
    is already unique. Both are geographic; only the numbering differs.
    """
    name = re.sub(r"^(?:Rep|Sen)\.\s+", "",
                  lab.get("display_plain") or m.get("name", ""))
    if "," in name:
        last, _, first = name.partition(",")
        name = f"{first.strip()} {last.strip()}"
    senate = str(m.get("chamber", "")).upper().startswith("S")
    where = "sd" if senate else (m.get("county_abbr") or m.get("county") or "")
    s = unicodedata.normalize("NFKD", f"{name} {where} {m.get('district','')}")
    s = s.encode("ascii", "ignore").decode()
    return re.sub(r"-{2,}", "-", re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")).lower()


# ------------------------------------------------------------------ naming --
# One way of naming a member, used everywhere the site refers to one.
#
#     display_plain   Rep. Jodi Nelson
#     display         Rep. Jodi Nelson (R)
#     display_full    Rep. Jodi Nelson (R - Rock. 13)
#                     Sen. Debra Altschiller (D - SD24)
#
# Three forms rather than one because a party letter beside a name that already
# sits next to a party colour chip reads as a stutter. The page picks the form
# that fits what is already on screen; nothing downstream has to split strings
# apart to get there.
#
# The honorific comes from the CHAMBER, not from a member's `title` field. That
# field can hold "Speaker" or "President", and this is a consistent way of
# referring to somebody rather than a statement of their highest office.
#
# The party letter is DROPPED rather than guessed when it is not known, and the
# district with it. A member resolved from a roll call page may have neither,
# and "(?)" beside a name is worse than a name on its own. A House district
# with no county is likewise omitted: "Rock. 13" locates a seat, "13" does not.
# Without the trailing point, which is the form data/legislators.json's own
# county_abbr carries. A member drawn from the roster read "Hills 12" and
# one drawn from here read "Hills. 6", so the punctuation tracked exactly
# who had left office.
COUNTY_ABBR = {
    "belknap": "Belk", "carroll": "Carr", "cheshire": "Ches",
    "coos": "Coos", "co\u00f6s": "Coos", "grafton": "Graf",
    "hillsborough": "Hills", "merrimack": "Merr", "rockingham": "Rock",
    "strafford": "Straf", "sullivan": "Sull",
}
HONORIFIC = {"H": "Rep.", "S": "Sen."}

_TITLE_RE = re.compile(r"^(?:rep|sen|representative|senator)\.?\s+", re.I)
# Case-insensitive: the bill status page writes the letter in lower case,
# so "Howard Pearl (r)" kept its tail, sorted as "(r), howard pearl" and
# matched nobody on the roster. 112 sponsor rows, all his.
_PARTY_TAIL_RE = re.compile(r"\s*\([RDILU](?:\s*[-\u2013][^)]*)?\)\s*$", re.I)
# build_data.py's "label" field is a composite -- "Nelson, Jodi(R) Rock. 13" --
# with the party letter in the MIDDLE and the seat after it. Nothing here is
# fed that field any more, but a formatter that mangles its input silently is
# worse than one that guards against it: this cuts at the party marker
# wherever it appears. No real name contains "(R)".
_COMPOSITE_RE = re.compile(r"\s*\([RDILU]\)\s.*$")
_PLACEHOLDER_RE = re.compile(r"^(?:Member\s*#|\(unknown)", re.I)


def person_name(raw):
    """"Nelson, Jodi" -> "Jodi Nelson".

    Idempotent: run it on something already formatted and the honorific and
    party letter are stripped before being put back, so nothing can ever read
    "Rep. Rep. Jodi Nelson (R) (R)".
    """
    s = re.sub(r"\s+", " ", (raw or "").strip())
    s = _COMPOSITE_RE.sub("", _PARTY_TAIL_RE.sub("", _TITLE_RE.sub("", s)))
    if "," in s:
        parts = [x.strip() for x in s.split(",") if x.strip()]
        if len(parts) == 2:
            s = f"{parts[1]} {parts[0]}"
        elif len(parts) > 2:
            # "Smith, John, Jr." - the suffix belongs at the end, not the middle.
            s = f"{parts[1]} {parts[0]} {' '.join(parts[2:])}"
    return s.strip()


def sort_name(raw):
    """Surname first, for the lists that are read alphabetically."""
    s = re.sub(r"\s+", " ", (raw or "").strip())
    s = _PARTY_TAIL_RE.sub("", _TITLE_RE.sub("", s))
    if "," in s:
        return s.lower()
    bits = s.split()
    return f"{bits[-1]}, {' '.join(bits[:-1])}".lower() if len(bits) > 1 else s.lower()


def name_key(raw):
    """("rebecca", "kwoka") -- a member's first and last word, either way round.

    sort_name treats the final word as the surname, which is right until a
    surname has more than one word in it. "Rebecca Perkins Kwoka" becomes
    "kwoka, rebecca perkins" while the roster holds "Perkins Kwoka, Rebecca",
    and the two never meet. The same for "Sabourin dit Choiniere" and for the
    particle in "de Vries" -- 217 sponsor rows across four members, drawn
    without the district everybody else has beside their name.

    Taking the first word and the last word sidesteps the split entirely: both
    spellings of a name yield the same pair however many words sit between
    them. It is a weaker key than a surname, so it is tried only after
    sort_name has failed.
    """
    s = _PARTY_TAIL_RE.sub("", _TITLE_RE.sub("", re.sub(r"\s+", " ",
                                                        (raw or "").strip())))
    if "," in s:
        last, first = [x.strip() for x in s.split(",", 1)]
        s = f"{first} {last}"
    w = [x for x in re.sub(r"[^\w' -]", " ", s, flags=re.UNICODE).lower().split()
         if x]
    return (w[0], w[-1]) if len(w) >= 2 else None


def district_tag(chamber, district, county=None, county_abbr=None):
    d = str(district or "").strip()
    if not d:
        return ""
    if chamber == "S":
        return f"SD{d}"
    ab = (county_abbr or "").strip() or COUNTY_ABBR.get(
        (county or "").strip().lower(), "")
    return f"{ab} {d}" if ab else ""


def member_labels(name, chamber=None, party=None, district=None, county=None,
                  county_abbr=None, label=None):
    who = person_name(label or name)
    if not who:
        return {"display_plain": "", "display": "", "display_full": "",
                "district_label": "", "sort": ""}
    if _PLACEHOLDER_RE.match(who):
        # A member the roster could not name. Calling that "Rep. Member #377204"
        # dresses up a gap as a person.
        return {"display_plain": who, "display": who, "display_full": who,
                "district_label": "", "sort": who.lower()}
    hon = HONORIFIC.get((chamber or "").strip().upper()[:1], "")
    plain = f"{hon} {who}".strip()
    pc = (party or "").strip()[:1].upper()
    p = pc if pc in "RDILU" else ""
    short = f"{plain} ({p})" if p else plain
    tag = district_tag((chamber or "").strip().upper()[:1], district, county,
                       county_abbr)
    if tag:
        full = f"{plain} ({p} - {tag})" if p else f"{plain} ({tag})"
    else:
        full = short
    return {"display_plain": plain, "display": short, "display_full": full,
            "district_label": tag, "sort": sort_name(label or name)}


def is_routine(text):
    return bool(ROUTINE.search(text or ""))


def classify_stated(st, prefix=""):
    """Map the page's own status wording to a display state, or None.

    Scans every status field at once and takes the most specific match, rather
    than the first field that matches anything. Checking gen_status first meant
    a bill whose override had already failed still read "VETOED BY GOVERNOR" and
    came out as awaiting a vote, because the general field never catches up with
    the chamber's.
    """
    blob = " ".join((st.get(f) or "").strip().lower()
                    for f in ("gen_status", "house_status", "senate_status"))
    if not blob.strip():
        return None
    for needle, kind, label in STATED:
        if needle in blob:
            return for_bill_kind(needle, kind, label, prefix)
    # Nothing in the table matched. GeneralCodes.txt code 04 is "PASSED", and
    # the table does not carry it because for a bill it says nothing the docket
    # does not say better -- passed the legislature, governor next. For a
    # resolution it is the whole answer, and HR35 sat on "In progress" with
    # gen_status PASSED and an adopted floor vote behind it. Asked last, and
    # only of resolutions, so it cannot shadow a more specific outcome.
    if "passed" in blob:
        if prefix in SINGLE_CHAMBER:
            return "adopted", f"Adopted by the {SINGLE_CHAMBER[prefix]}"
        if prefix == "CACR":
            return "adopted", "Passed both chambers, goes to the voters"
        if prefix in NO_GOVERNOR:
            return "adopted", "Adopted by both chambers"
    return None


# The docket writes the signature two ways -- "Signed by Governor Ayotte
# 7/10/2026" and "Signed by the Governor on 7/10/2026" -- and the second is
# 233 of the 632. Reading only the first left those bills showing whatever
# they were before it: 137 "Passed one chamber", 82 "Passed, awaiting the
# governor", nine "In committee" and five "Killed", for bills that are law.
SIGNED_RE = re.compile(r"signed by (?:the )?governor", re.I)


# How a bill ends when the docket does not say so.
#
# The docket records actions, and a session ending is not an action: it just
# stops. For 111 bills the last line is a committee report and the status page
# alone knows the bill died with the term, so the page showed a red headline
# over a history that trailed off mid-sentence -- the status said one thing and
# the story below it said nothing at all.
#
# Each of these says what happened and what it means, because "DIED, SESSION
# ENDED" is the General Court's phrase rather than a plain-English one.
CLOSING = {
    # label: (phrases that mean the history ALREADY says it, the paragraph)
    #
    # The guards are per outcome, and they have to be. A first attempt tested
    # for "kill it" anywhere in the narrative and matched every bill whose
    # committee recommended that the chamber kill it -- which is a committee
    # report, not an ending, and it suppressed the paragraph on all 111.
    "Died when the session ended": (
        ("session ended", "died when the session", "died on the table"),
        "No vote was ever taken on it, and the bill died when the session "
        "ended. That is a procedural end rather than a decision -- much like a "
        "bill left on the table, it ran out of time -- and it would have to be "
        "filed again as a new bill in a later term."),
    "Indefinitely postponed": (
        ("indefinitely postpone",),
        "The chamber voted to indefinitely postpone it. That ends the bill for "
        "the term and, under the rules, bars the same subject from being taken "
        "up again before the term is out."),
    # "Killed" is deliberately NOT here. The status page reports it for bills
    # whose docket already says what ended them -- 28 were laid on the table
    # and died there, and the narrative says so in as many words -- so a
    # paragraph claiming "the docket does not record the vote that ended it"
    # would have been false on most of the bills it appeared under.
}


def closing_stage(label, narr):
    """A last paragraph for a bill whose ending the docket never narrates.

    The docket records actions, and a session ending is not an action: it just
    stops. For 111 bills the last line is a committee report and only the
    status page knows the bill died with the term, so a settled red headline
    sat above a history that trailed off mid-sentence.

    Returns None where the history already says it.
    """
    hit = CLOSING.get(label)
    if not hit:
        return None
    guards, text = hit
    told = " ".join(s.get("text", "") for s in (narr or {}).get("stages", [])).lower()
    if any(g in told for g in guards):
        return None
    return {"label": "How it ended", "text": text}


def docket_outcome(narr):
    """The outcome as the DOCKET states it, or None.

    classify_stated already knows the status page lags: its own note records a
    bill whose override had failed still reading VETOED BY GOVERNOR because
    "the general field never catches up with the chamber's". The docket is the
    same official source and does not lag -- it carries a dated line the day
    the vote happens.

    HB 396 is the case. The House sustained the veto on 19 August; the status
    page still says "Senate: PASSED/ADOPTED WITH AMENDMENT", which was true in
    May and is the Senate's last action rather than the bill's state. So a
    dated outcome in the docket outranks a summary field that has not caught
    up, and only for this family, where the lag is known.

    Sustained is tested before overridden for the reason it always is: both
    chambers must override, so one sustaining ends the bill.
    """
    text = " ".join(e.get("raw", "") for e in (narr or {}).get("events", [])).lower()
    if "veto sustained" in text:
        return "veto", "Vetoed, override failed"
    if "veto overridden" in text:
        return "law", "Veto overridden, became law"
    if ("without the signature of the governor" in text
            or "law without signature" in text):
        return "law", "Became law unsigned"
    # And the signature itself, for the same reason and on the same evidence.
    # The status page carries no governor field for 219 bills whose docket
    # records the day the governor signed them and the chapter number they
    # became -- so they read "Passed one chamber", "Passed, awaiting the
    # governor", "In committee" or, for five of them, "Killed". The page is
    # describing the last thing it was told; the docket is describing what
    # happened.
    if SIGNED_RE.search(text):
        return "law", "Signed into law"
    return None


# A floor motion the chamber ADOPTED that finishes the bill.
#
# Read from the motion code and the action, not from a substring of the whole
# docket. classify() below tests `"inexpedient to legislate" in text`, and that
# phrase appears in every MINORITY report as well -- which is how HCR1, HCR4
# and HCR9 came to read "Killed" when the House had adopted Ought to Pass on
# them 197-156, 195-149 and 204-163.
DISPOSED = [
    (re.compile(r"inexpedient to legislate", re.I), ("done", "Killed")),
    (re.compile(r"indefinitely postpone", re.I),
     ("done", "Indefinitely postponed")),
    (re.compile(r"interim study", re.I), ("study", "Referred for interim study")),
]


def floor_disposed(narr):
    """The last adopted floor motion that finished the bill, or None.

    A later adopted motion that is NOT a disposal clears an earlier one: a bill
    killed, reconsidered and then passed is not killed, and the docket records
    that as two adopted motions in order.
    """
    out = None
    for e in sorted((narr or {}).get("events", []),
                    key=lambda x: x.get("date") or ""):
        if e.get("cancelled") or e.get("type") != "floor":
            continue
        if (e.get("motion") or "").upper() != "MA":
            continue
        act = e.get("action") or ""
        hit = next((res for pat, res in DISPOSED if pat.search(act)), None)
        out = hit
    return out


def classify(narr, rcs, prefix=""):
    """Map a bill to one of four display states."""
    text = " ".join(e.get("raw", "") for e in (narr or {}).get("events", [])).lower()
    # The veto outcomes are tested first, and SUSTAINED before OVERRIDDEN.
    # Both chambers must override; one of them sustaining ends the bill. SB 434
    # carries both words in its docket -- the House sustained, the Senate
    # overrode -- so reading "overridden" first would call a dead bill law.
    #
    # This whole function is only the fallback for bills the status page does
    # not cover. That page states the outcome per chamber and is preferred, and
    # it is what would be needed to tell apart a veto sustained and then
    # reconsidered.
    if "veto sustained" in text:
        return "veto", "Vetoed, override failed"
    if "veto overridden" in text:
        return "law", "Veto overridden, became law"
    if ("without the signature of the governor" in text
            or "law without signature" in text):
        return "law", "Became law unsigned"
    if SIGNED_RE.search(text):
        return "law", "Signed into law"
    if "vetoed" in text:
        return "veto", "Vetoed"
    if "inexpedient to legislate" in text and "ma" in text:
        return "done", "Killed"
    if "interim study" in text:
        # Its own kind, not "done". A bill sent to interim study has not been
        # killed -- it is parked for the committee to work on out of session,
        # and it can come back. Grouping it with bills that were voted down
        # said something untrue about it every time.
        return "study", "Interim study"
    if "died on table" in text:
        return "done", "Died on table"
    if "retained in committee" in text:
        return "active", "Retained in committee"
    # A floor motion the chamber carried, however the vote was taken. This
    # asked the roll calls and nothing else, so a resolution adopted on a VOICE
    # vote -- which is how most of them are adopted -- fell past it. HR16 sat
    # on "In committee" with "Ought to Pass with Amendment: MA VV" in its
    # docket and the House's adoption of it on the page above.
    #
    # The motion has to be an adoption. Thirteen of these resolutions carried a
    # motion of Inexpedient to Legislate and two carried one to lay on the
    # table; both are caught further up, and naming the motion here means they
    # stay caught if that order ever changes.
    adopted_floor = any(
        e.get("type") == "floor" and (e.get("motion") or "").upper() == "MA"
        and re.search(r"ought to pass|adopted", e.get("action") or "", re.I)
        for e in (narr or {}).get("events", []) if not e.get("cancelled"))
    if adopted_floor or any(r.get("passed") for r in rcs):
        # A resolution of one chamber that has carried a vote is finished.
        # There is no other chamber for it to be in progress towards.
        if prefix in SINGLE_CHAMBER:
            return "adopted", f"Adopted by the {SINGLE_CHAMBER[prefix]}"
        return "active", "In progress"
    return "active", "In committee"


def next_step(narr, bill, prefix=""):
    """Plain-language 'what happens next', from the last recognised event."""
    evs = (narr or {}).get("events", [])
    if not evs:
        return "No recorded action yet"
    last = evs[-1]
    raw, t = last.get("raw", "").lower(), last.get("type")
    # A veto outcome is read from the WHOLE history, not just the last line.
    # An override is voted in each chamber separately, so the final line is one
    # chamber's answer rather than the bill's, and taking it alone reported
    # SB 434 as law when the House had already sustained the veto.
    every = " ".join(e.get("raw", "").lower() for e in evs)
    if "veto sustained" in every:
        return "Vetoed. The override failed and the bill is dead"
    if "veto overridden" in every:
        return "Vetoed, then overridden. It becomes law"
    if ("without the signature of the governor" in every
            or "law without signature" in every):
        return "Became law without the governor's signature"
    if SIGNED_RE.search(raw):
        return "Signed into law"
    if "vetoed" in raw:
        return "Vetoed. Awaiting a possible override vote"
    # A resolution of one chamber is finished the moment that chamber adopts
    # it, and the line recording that is not always the last one: HR16's floor
    # vote is followed by the roll call on the amendment it adopted, so the
    # chain below read "amendment" and answered "In progress" for a resolution
    # the House had passed a month earlier.
    if prefix in SINGLE_CHAMBER and any(
            e.get("type") == "floor" and (e.get("motion") or "").upper() == "MA"
            and re.search(r"ought to pass|adopted", e.get("action") or "", re.I)
            for e in evs if not e.get("cancelled")):
        return "Adopted. A resolution of one chamber goes no further"
    if t == "introduced":
        return f"Pending public hearing in {bill.get('house_committee') or 'committee'}"
    if t == "hearing":
        return "Pending executive session in committee"
    if t == "exec":
        return "Pending a committee report"
    if t == "report":
        return "Pending a vote of the full chamber"
    if t == "floor":
        if prefix in SINGLE_CHAMBER:
            return "Adopted. A resolution of one chamber goes no further"
        return "Pending action in the other chamber"
    if t == "enrolled":
        if prefix == "CACR":
            return "Goes to the voters at the next general election"
        if prefix in NO_GOVERNOR:
            return "Adopted by both chambers. It does not go to the governor"
        return "Enrolled. Pending the governor's signature"
    if t == "retained":
        return "Retained in committee for further work"
    if t == "died":
        return "Died when the session ended"
    return "In progress"


def station_for_proceeding(p, bid, segs, marks):
    """One committee proceeding -- a hearing or an executive session -- as the
    station the page draws.

    Split out of main() with station_for_floor below it. The two used to sit
    ninety lines apart inside one 955-line function, which is how a lookup
    added to one of them silently missed the other.
    """
    seg = None
    for s in segs.get(p.get("video_id", ""), []):
        if s.get("bill", "").upper() == bid and s.get("kind") == p["proceeding"]:
            seg = s
            break
    # Three states, and the middle one is the point. A recording matched
    # to the proceeding with only an approximate starting point is still
    # far more useful than no link at all: the reader scrubs a few
    # minutes instead of hunting through 331 videos. Exact timestamps
    # are an upgrade to this, not a precondition for it.
    if seg and seg.get("located"):
        state, start = "located", seg["start"]
    elif p.get("video_id"):
        state, start = "approximate", None
    elif p["sched_date"] < "2020-03-01":
        state, start = "prestream", None
    else:
        state, start = "novideo", None
    # A stated boundary replaces the estimate outright.
    # The filter exists to stop a hearing's boundary being handed to an
    # executive session on the same recording. A marker that names the
    # proceeding is checked against the kind; one that does not -- a weak
    # marker with no noun, or the bare word "session", which one chair uses
    # for what the docket calls a public hearing -- makes no claim to check,
    # so it is kept as a fallback rather than discarded.
    #
    # Two passes, in that order. Discarding the ambiguous ones outright cost
    # HB1123 its boundary: the chair said "we're opening the session on House
    # Bill 1123", the docket calls it a public hearing, neither word contained
    # the other, and the only quotation on the recording was thrown away in
    # favour of a clustered guess a minute and a half out.
    AMBIGUOUS = {"", "session"}

    def _matches(cand):
        want = str(p.get("proceeding") or "").lower()
        what = str(cand.get("what") or "")
        if not want or not what or what in AMBIGUOUS:
            return None
        return what.split()[-1] in want or want.split()[-1] in what

    usable = [c for c in (marks.get(p.get("video_id") or "") or {}).get(bid, [])
              if isinstance(c, dict) and c.get("start") is not None]
    said = next((c for c in usable if _matches(c) is True), None)
    if said is None:
        said = next((c for c in usable if _matches(c) is None), None)

    # The clustering's end, but only where it is describing the same span.
    #
    # A stated start replaces the clustered one outright, and it does that
    # precisely in the cases where the two disagree. Reaching past it for the
    # clustered END then pairs a quotation with an inference about somewhere
    # else in the recording. 2,732 proceedings did that: 429 ended at or
    # before the start they were pinned to -- which the page dropped without a
    # word, so a wrong number became a missing one in silence -- and 743 more
    # came from a placement further from the chair's than the clustering's own
    # tolerance allows, giving the reader a duration that was never measured
    # from that point.
    #
    # The threshold is the segment's own tolerance rather than one invented
    # here: the aligner already says how sure it is, from 30 seconds where the
    # evidence was thick to half an hour where it was thin, and a placement
    # inside that is the same placement. Where it is not, the proceeding keeps
    # its stated start and no end, which the page already draws as "from
    # 1:19:26".
    seg_end = None
    if seg and seg.get("located") and seg.get("end") is not None:
        anchor = said["start"] if said else seg.get("start")
        near = (abs(seg["start"] - anchor) <= (seg.get("tolerance") or 300)
                if said else True)
        if anchor is not None and seg["end"] > anchor and near:
            seg_end = seg["end"]

    return {
        "when": p["sched_date"], "time": p.get("sched_time"),
        "what": p["proceeding"], "committee": p.get("committee"),
        "venue": p.get("venue"), "video_id": p.get("video_id"),
        "watch": p.get("watch_url"), "predicted": p.get("predicted_offset"),
        "start": said["start"] if said else start,
        "state": "stated" if said else state,
        # The aligner sets a tolerance per segment from how much
        # evidence it had -- 3 minutes with many bill mentions, 30 with
        # a short span and few. Dropping it here made every hearing on
        # the site claim the same +/-5 minutes, understating the good
        # ones and, worse, overstating the weak ones.
        "tolerance": (5 if said else
                      (seg.get("tolerance") if seg else None)),
        "short": bool(seg.get("short")) if seg else False,
        # The aligner produces a span, not a point. Showing only the
        # start throws away half of it -- and the duration is what tells
        # a reader whether a proceeding was a five-minute executive
        # session or a two-hour hearing before they click anything.
        # A stated close outranks a clustered one: four seconds at the
        # median against whatever the cluster's tail happened to be.
        "end": (said.get("end") if said and said.get("end") else seg_end),
        "end_stated": bool(said and said.get("end")),
        "candidate": seg["start"] if seg and not seg.get("located") else None,
        # Which ends of this span were stated by the chair rather than
        # inferred, written by apply_markers.py. The page does not say
        # so in words -- the tolerance carries that -- but it decides
        # the tolerance's unit and how early the player opens, and it
        # is what a methodology page would count.
        #
        # Per end, not per segment: a Senate chair announces the close
        # and not the opening, so a proceeding can have a quoted end
        # and an estimated start.
        #
        # The caption lines themselves stay in work/<id>/segments.json
        # as the audit trail and are not shipped to the browser.
        # Seconds, not minutes: a boundary the chair said is good to
        # about a second, and calling that "+/- 1 min" would understate
        # it as badly as the old tolerances overstated theirs.
        "start_stated": bool(said) or (bool(seg.get("start_stated"))
                                       if seg else False),
        # The words are deliberately NOT published. Captions mangle
        # bill numbers constantly, and a garbled quote presented as the
        # chair's own words is a transcription error wearing the
        # clothes of a citation. How it was found is kept, because that
        # is a fact about this site's method rather than a claim about
        # what anyone said.
        "said_how": said.get("how") if said else None,
        "end_stated_cluster": bool(seg.get("end_stated")) if seg else False,
    }


def station_for_floor(f, bid, marks):
    """One floor appearance as a station.

    Returns a finished dict. The consent case and the stated-boundary upgrade
    are applied before returning, rather than by reaching back into
    stations[-1] after appending.
    """
    precise = f.get("precise") and f.get("debate_end")
    if f.get("whole_video"):
        # The title names the bill, so the entire recording is this
        # proceeding. No timestamp to estimate and none needed.
        return {
            "when": f["date"], "time": None,
            "what": f.get("kind", "committee of conference"),
            "committee": None, "venue": None,
            "video_id": f["video_id"],
            "watch": f"https://www.youtube.com/watch?v={f['video_id']}",
            "predicted": None, "start": 0, "debate_end": None,
            "window_start": None, "motions": [], "tallies": [],
            "title": f.get("title", ""),
            "state": "whole_video", "candidate": None}
    st = {
        "when": f["date"], "time": None,
        "what": "floor debate",
        "committee": "House" if f.get("body") == "H" else "Senate",
        "venue": None, "video_id": f["video_id"],
        "watch": (f"https://www.youtube.com/watch?v={f['video_id']}"
                  f"&t={max(int(f.get('window_start') or 0) - 60, 0)}s"),
        "predicted": None,
        "start": (max(f.get("window_start", 0),
                      f["debate_end"] - 1800) if precise else None),
        "debate_end": f.get("debate_end") if precise else None,
        "window_start": f.get("window_start") if precise else None,
        "motions": f.get("motions", []), "tallies": f.get("tallies", []),
        "state": "floor_precise" if precise else "floor_dated",
        "candidate": None,
    }
    # The clerk reads a committee report to open every bill, and
    # segment_markers.py finds it. That is the START of the debate --
    # exact, and from the clerk's own words. Without it the player fell
    # back to the window, which opens at the PREVIOUS bill's roll call
    # and can be half an hour of other business away.
    #
    # This branch once did not consult the markers at all: they were
    # found, written, and ignored, because floor stations were built in
    # one place and the lookup was added in another, ninety lines away
    # in the same function. The same manifest-and-floor-index split, for
    # the fifth time. Both halves are now one short function each, and
    # the station is finished before it is returned rather than adjusted
    # through stations[-1] after the fact.
    # A bill never named on its own floor recording passed on the
    # consent calendar: adopted as part of a block, never read out,
    # never debated. Offering to play a nine-hour session for it invites
    # a reader to listen for something that is not there.
    if bid in (marks.get("_absent") or {}).get(f.get("video_id") or "",
                                               []):
        st["state"] = "consent"
        st["start"] = None
        # Not a debate. The heading read "House floor debate" over a paragraph
        # explaining the bill was never debated, which is the page contradicting
        # itself in two lines.
        st["what"] = "consent calendar"
        return st

    said_f = None
    for cand in (marks.get(f.get("video_id") or "") or {}).get(bid, []):
        if not isinstance(cand, dict) or cand.get("start") is None:
            continue
        if str(cand.get("what") or "") not in ("", "floor debate"):
            continue
        end = f.get("debate_end")
        if precise and end and not (0 <= end - cand["start"] <= 7200):
            continue      # not this sitting's debate
        said_f = cand
        break
    if said_f:
        st["start"] = said_f["start"]
        st["debate_start"] = said_f["start"]
        st["start_stated"] = True
        st["said_how"] = said_f.get("how")
        if not precise and said_f.get("end"):
            st["debate_end"] = said_f["end"]
            st["state"] = "floor_stated"
    return st


def vote_date(s):
    """"8/19/2026" as something that sorts. Text does not.

    The docket writes m/d/Y with no padding, so a string sort puts August
    above December and 2023 above 2025. Every member page claimed "newest
    first" over that order.
    """
    p = (s or "").split("/")
    try:
        return (int(p[2]), int(p[0]), int(p[1]))
    except (IndexError, ValueError):
        return (0, 0, 0)


def build_legislators(out, legs, votes_by_member, towns, unnamed,
                      sponsored=None, bill_year=None):
    """One JSON per member, plus the index and the town map.

    Split out of main(). main() was 808 lines even after the station
    builders came out, and the bug that cost 611 bills their facts was two
    different things sharing the name `st` 350 lines apart in this scope.
    """
    lg = []
    for mid, m in legs.items():
        mv = sorted(votes_by_member.get(mid, []),
                    key=lambda v: vote_date(v.get("date")), reverse=True)
        counts = defaultdict(int)
        for v in mv:
            counts[v["vote"]] += 1
        lab = member_labels(m.get("name"), chamber=m.get("chamber"),
                            party=m.get("party_code") or m.get("party"),
                            district=m.get("district"), county=m.get("county"),
                            county_abbr=m.get("county_abbr"))
        lg.append({**{k: m.get(k) for k in ("id", "name", "chamber", "party", "county",
                                            "county_abbr", "district", "label", "email",
                                            "url", "url_past", "towns",
                                            "committees", "title", "phone")},
                   **lab, "n_votes": len(mv), "counts": dict(counts),
                   "n_sponsored": len((sponsored or {}).get(mid, [])),
                   "slug": member_slug(m, lab)})
        # What they put their name to. The page's own meta description has
        # promised "sponsored bills" since it was written and the file did not
        # carry them, so the page could not show them and a search engine was
        # being told about a section that does not exist.
        #
        # Prime sponsorship first, then the rest, newest first within each: a
        # member's own bills are the ones they are asked about.
        mine = sorted((sponsored or {}).get(mid, []),
                      key=lambda x: (not x["prime"], x.get("year") or 0,
                                     x["bill"]), reverse=False)
        (out / "legislators" / f"{mid}.json").write_text(json.dumps({
            **m, **lab, "counts": dict(counts),
            "n_sponsored": len(mine),
            "n_prime": sum(1 for x in mine if x["prime"]),
            "sponsored": mine,
            # y is the bill's FILING year, which is what its address is under
            # -- a 2025 bill voted on in 2026 lives at /bill/2025/. Without it
            # the page had to guess the year from the bill number, and a
            # number that exists in two terms was resolved to whichever came
            # first in the index.
            "votes": [{"d": v["date"], "b": v["bill"], "q": v["question"],
                       "v": v["vote"],
                       "y": (bill_year or {}).get(
                           (P.term_of(v.get("year", "")), v["bill"]), "")}
                      for v in mv],
        }), encoding="utf-8")
    if unnamed:
        print(f"{len(unnamed):,} member id(s) still have no name and appear as "
              '"Member #id" in roll calls:')
        print("  " + ", ".join(sorted(unnamed)[:12])
              + (" ..." if len(unnamed) > 12 else ""))
        # A six-digit id is an Employeeno that build_data fell back to because
        # the legislators table has no row for that person -- not a PersonID
        # nobody has looked up yet. fetch_members_db.py has already read every
        # inactive legislator the database holds, so re-running it will not
        # name these; the General Court's own roster does not carry them.
        #
        # resolve_members.py could, in principle: rc_yeahnay.aspx lists the
        # names who voted each way, and the leftovers after removing everyone
        # identified must be these people. It reads the current session's
        # RollCallHistory.txt only, and skips a blank id outright, so it needs
        # both of those changed first. Three members of the 2023-2024 House,
        # 1,470 votes, is what that would buy.
        orphans = [u for u in unnamed if u.isdigit() and len(u) >= 6]
        if orphans:
            print(f"  {len(orphans)} of these are an Employeeno, used because "
                  "the legislators table")
            print("  has no row for them at all. fetch_members_db.py has read "
                  "every inactive")
            print("  member it holds, so it will not name them; only "
                  "rc_yeahnay.aspx would.")
        if len(orphans) < len(unnamed):
            print("  The rest are PersonIDs: run fetch_members_db.py, which "
                  "writes")
            print("  former_members.json, then build_data.py, which reads it.")
    (out / "legislators.json").write_text(json.dumps(lg), encoding="utf-8")
    (out / "towns.json").write_text(json.dumps(towns), encoding="utf-8")
    print(f"{len(lg):,} legislator pages, {len(towns):,} towns")
    return lg


def build_composition(a, legs):
    """Party composition, vacancies, the Executive Council and the governor.

    Returns (comp, vac). Split out of main(); this block already carried a
    dead duplicate of itself once -- two versions of the same work eighteen
    lines apart, the second silently discarding the first.
    """
    # Seat totals come from the district files where available, since those sum
    # to the constitutional membership exactly. The roster holds only sitting
    # members, so the difference is vacancies -- which accumulate through a term
    # as people resign or die, and which nothing else reports.
    dj = load(a.districts, {})
    seats_by = defaultdict(int)
    for wards in dj.values():
        for v in wards.values():
            for h in v.get("house", []):
                seats_by[("H", h["county"], h["district"])] = h.get("seats") or 1
    house_seats = sum(seats_by.values()) or 400

    PARTY_FULL = {"R": "Republican", "D": "Democrat", "I": "Independent",
                  "L": "Libertarian"}
    comp = {}
    for ch, label, total in (("H", "House", house_seats), ("S", "Senate", 24)):
        members = [m for m in legs.values() if m["chamber"] == ch]
        counts = Counter(m["party_code"] or "?" for m in members)
        comp[ch] = {
            "chamber": label, "seats": total, "sitting": len(members),
            "vacant": max(total - len(members), 0),
            "parties": [{"code": k, "name": PARTY_FULL.get(k, k), "n": v}
                        for k, v in sorted(counts.items(), key=lambda x: -x[1])],
            # Reference thresholds, stated as arithmetic rather than as any
            # party's distance from them.
            "majority": total // 2 + 1,
            "two_thirds_note": "two thirds of those voting, so it moves with turnout",
            "three_fifths": -(-3 * total // 5),
        }

    # Which districts are short a member. Only possible where the district files
    # give seat counts.
    vac = []
    if seats_by:
        held = Counter()
        for m in legs.values():
            if m["chamber"] == "H":
                held[("H", m["county"], int(m["district"] or 0))] += 1
        for key, n in sorted(seats_by.items()):
            gap = n - held.get((key[0], key[1], int(key[2])), 0)
            if gap > 0:
                vac.append({"county": key[1], "district": key[2], "seats": n,
                            "vacant": gap})
    comp["vacancies"] = vac

    # Executive branch: hand-maintained, because the Council and the governor
    # are not the General Court and appear in none of its files. An unedited
    # file yields nothing, so the section is absent rather than wrong.
    op = Path(a.officials)
    if op.exists():
        council, gov, onote, oupd = [], None, "", ""
        last = None
        for raw in op.read_text(encoding="utf-8").splitlines():
            if raw.strip().startswith("#"):
                continue
            line = raw.split("#")[0].rstrip()
            if not line.strip():
                last = None
                continue
            if raw[:1] in " \t" and last == "note":
                onote = (onote + " " + line.strip()).strip()
                continue
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            k, v = k.strip().lower(), v.strip()
            last = k
            if k == "councilor":
                parts = [x.strip() for x in v.split("|")]
                if parts and parts[0]:
                    council.append({"district": parts[0],
                                    "name": parts[1] if len(parts) > 1 else "",
                                    "party": (parts[2] if len(parts) > 2 else "").upper()})
            elif k == "governor" and v:
                parts = [x.strip() for x in v.split("|")]
                gov = {"name": parts[0],
                       "party": (parts[1] if len(parts) > 1 else "").upper()}
            elif k == "note":
                onote = v
            elif k == "updated":
                oupd = v
        named = [c for c in council if c["name"]]
        if named or gov:
            cc = Counter(c["party"] or "?" for c in named)
            comp["council"] = {
                "chamber": "Executive Council", "seats": len(council) or 5,
                "sitting": len(named), "vacant": len(council) - len(named),
                "members": council,
                "parties": [{"code": k, "name": PARTY_FULL.get(k, k), "n": v}
                            for k, v in sorted(cc.items(), key=lambda x: -x[1])],
                "majority": (len(council) or 5) // 2 + 1,
                "note": onote, "updated": oupd}
            print(f"  Executive Council: {len(named)} of {len(council)} seats named")
        if gov:
            comp["governor"] = gov
        if not named and not gov:
            print("  status/officials.txt is unedited \u2014 the Executive Council "
                  "and governor are omitted from the page")

    return comp, vac


def build_status(a, index, procs, floor, today, latest_by_body, upcoming):
    """The site's "where the session is" panel.

    Hand-maintained facts from status/session.txt merged with what the data
    can show. Split out of main(); returns the status dict.
    """
    # Hand-maintained facts merged with what the data can show. The phase, the
    # session calendar and veto day are set by the chambers and published only
    # in the calendars, so they are edited rather than derived; the last session
    # date and the count of scheduled hearings come from the data.
    status = {"milestones": []}
    sp = Path(a.status)
    if sp.exists():
        last_key = None
        for raw in sp.read_text(encoding="utf-8").splitlines():
            if raw.strip().startswith("#"):
                continue
            line = raw.split("#")[0].rstrip()
            if not line.strip():
                last_key = None
                continue
            # An indented line continues the previous value, so a note can be
            # written as a paragraph instead of one unreadable line.
            if raw[:1] in " \t" and last_key in ("note", "headline"):
                status[last_key] = (status.get(last_key, "") + " "
                                    + line.strip()).strip()
                continue
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            k, v = k.strip().lower(), v.strip()
            last_key = k
            if k == "milestone":
                parts = [x.strip() for x in v.split("|")]
                if parts and parts[0] >= today:
                    status["milestones"].append({
                        "date": parts[0],
                        "label": parts[1] if len(parts) > 1 else "",
                        "note": parts[2] if len(parts) > 2 else ""})
            elif k in ("updated", "phase", "headline", "note"):
                status[k] = v
        status["milestones"].sort(key=lambda m: m["date"])
        if status.get("updated"):
            age = (_date.today() - _date.fromisoformat(status["updated"])).days
            status["stale_days"] = age
            if age > 45:
                print(f"  status/status.txt was last updated {age} days ago "
                      "\u2014 the page will say so")
    # Latest sitting of either chamber, from the per-chamber map that replaced
    # the old single "most recent session".
    status["last_session"] = (max(v["date"] for v in latest_by_body.values())
                              if latest_by_body else None)
    status["hearings_next_14"] = len(upcoming)
    # Always-correct live links: these URLs resolve to whatever is streaming now,
    # or to the channel if nothing is, so no polling is needed.
    status["live"] = [
        {"chamber": "House",
         "url": "https://www.youtube.com/@NHHouseofRepresentatives/live"},
        {"chamber": "Senate",
         "url": "https://www.youtube.com/@NewHampshireSenate/live"}]

    return status


# A calendar's publication date, out of the filename the viewer link carries:
# "calendars%5C2026%5CNo10%20March%206%202026.pdf". Every one of the 24
# calendars a committee report cites resolves this way, so a report that the
# docket does not date can still be placed on the day it was printed.
CAL_DATE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October"
    r"|November|December)%20(\d{1,2})%20(\d{4})", re.I)
MONTHS = ["january", "february", "march", "april", "may", "june", "july",
          "august", "september", "october", "november", "december"]
# "House Calendar 51, 2025" is how a report names the calendar it was printed
# in; "HC 51" is how the docket cites the same volume. One key for both.
REPORT_CAL = re.compile(r"House Calendar (\d+[A-Za-z]?)(?:,\s*(\d{4}))?", re.I)
# What the chamber did between one report and the next. These are the three
# ways a bill goes back to a committee that has already reported it, and one
# of them sits between the two reports on eight of the nine bills whose
# reports all come from a single committee -- which is the answer to "what
# does the second report mean". Interim study is deliberately not here: it
# ends a bill for the session rather than sending it back for another report.
REPORT_AGAIN = re.compile(r"recommit|re-?refer|retained in committee", re.I)


def rec_key(s):
    """A recommendation as the two sources agree on it.

    The docket writes "Ought to Pass with Amendment"; the Senate's own report
    writes "OUGHT TO PASS WITH AMENDMENT", and sometimes "IS INEXPEDIENT TO
    LEGISLATE" where the docket says "Inexpedient to Legislate". Stripping the
    leading verb, the case and the punctuation makes them one string -- the
    punctuation being what separates "Re-referred" from "rereferred". Measured
    on every Senate report the database holds: 1,443 of the 1,443 bills whose
    docket records a Senate report agree with the report's own wording, with
    no disagreements.
    """
    s = re.sub(r"^(?:is|be|has)\s+", "", (s or "").strip().lower())
    return re.sub(r"[^a-z ]", "", s).strip()


def _cal_key(source):
    """"House Calendar 51, 2025" as the docket writes it: ("HC 51", "2025")."""
    m = REPORT_CAL.search(source or "")
    return (f"HC {m.group(1)}", m.group(2) or "") if m else ("", "")


def _cal_date(url):
    """The day a calendar was published, from the filename in its link."""
    m = CAL_DATE.search(url or "")
    if not m:
        return ""
    return (f"{int(m.group(3)):04d}-{MONTHS.index(m.group(1).lower()) + 1:02d}"
            f"-{int(m.group(2)):02d}")


def _mdy(s):
    """The docket's 03/17/2026 as 2026-03-17."""
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})$", (s or "").strip())
    return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}" if m else ""


def committee_reports(recs, narr, sources, house_cmte, senate_cmte):
    """Every committee report on a bill, dated, in the order they were signed.

    Two sources hold different halves of this and neither is enough alone.

    The House Calendar prints why a committee decided as it did, signed by
    name, and that is the only place the reasoning exists. It says nothing
    about when, and a bill reported twice by one committee -- 9 of the 108
    with more than one report -- came out as two identical-looking blocks with
    no way to tell which was which, or that on HB104 they are one report
    printed in two calendars.

    The docket records that a committee reported, the day it signed, what it
    moved, by what vote, and the volume and page it was printed in. It has no
    prose. It also has the Senate: 1,708 reports the tab used to answer with
    "Senate reports use a different format and are not loaded yet". The format
    is one report, with a vote and no minority -- which is what the Senate
    does.

    So each written report is dated from the docket line citing the same
    calendar, or failing that from the day that calendar was published, and
    every report the docket has that no calendar printed is carried alongside
    it. The page says which of the two dates it is showing.
    """
    events = [e for e in (narr or {}).get("events", [])
              if e.get("type") == "report" and not e.get("cancelled")]
    # The date the committee signed, per calendar volume, from the docket.
    signed = {}
    for e in events:
        d = _mdy(e.get("report_date"))
        if e.get("cite") and d:
            signed.setdefault(e["cite"], d)

    # The Senate's reports come from the database, not from a House Calendar,
    # and carry their own printed date. Where the docket records the same
    # recommendation it has the day the committee SIGNED and the journal page
    # it was printed in, which are better than the day it was released -- so
    # those are taken, and that docket line is then not shown a second time
    # saying what the report above it already says.
    #
    # Keyed on the CHAMBER as well as the recommendation. On the wording alone
    # it matched the wrong chamber 364 times out of 1,446 -- both chambers say
    # "Ought to Pass" -- and gave a Senate report a House Calendar citation and
    # the day the House committee signed. A citation to the wrong document is
    # worse than none on a site whose whole claim is that it can be checked.
    by_rec, used = {}, set()
    for e in events:
        if e.get("recommendation"):
            by_rec.setdefault((e.get("body") or "",
                               rec_key(e["recommendation"])), []).append(e)

    out, seen_cal = [], set()
    for r in recs:
        key, year = _cal_key(r.get("source"))
        seen_cal.add(key)
        url = sources.get(f"{key} {year}") if year else None
        url = url or sources.get(key, "")
        rr = dict(r)
        if signed.get(key):
            rr["date"], rr["dated"] = signed[key], "signed"
        elif _cal_date(url):
            rr["date"], rr["dated"] = _cal_date(url), "printed"
        elif r.get("date"):
            rr["date"], rr["dated"] = r["date"], r.get("dated") or "printed"
        else:
            rr["date"], rr["dated"] = "", ""
        rr["cite"] = key
        rr["cite_url"] = url
        if not key and r.get("date") and r.get("body"):
            match = next((e for e in
                          by_rec.get((r["body"],
                                      rec_key(r.get("majority_recommendation"))), [])
                          if id(e) not in used), None)
            if match:
                used.add(id(match))
                when = _mdy(match.get("report_date"))
                if when:
                    rr["date"], rr["dated"] = when, "signed"
                cite = match.get("cite", "")
                rr["cite"] = cite
                rr["cite_url"] = (sources.get(f"{cite} {rr['date'][:4]}")
                                  or sources.get(cite, "")) if cite else ""
        out.append(rr)
    out.sort(key=lambda x: x.get("date") or "9999")

    # Reports the docket has and no calendar printed. A House report reaches
    # this list when it was printed in a calendar this site has not read; a
    # Senate report always does, because the Senate prints no reasoning.
    docket = []
    for e in events:
        if id(e) in used:
            continue          # a written report above is this same report
        if e.get("cite") and e["cite"] in seen_cal:
            continue
        # A minority report carries no vote and no volume of its own; where the
        # calendar's version of it is already above, showing the docket's bare
        # line again says nothing new.
        if e.get("side") and any(x.get("side") == e["side"]
                                 for r in recs for x in (r.get("reports") or [])):
            continue
        docket.append({
            "date": _mdy(e.get("report_date")) or e.get("date", ""),
            "dated": "signed" if _mdy(e.get("report_date")) else "recorded",
            "body": e.get("body", ""),
            # The committee that reported, which narrative.py carries forward
            # from the referral line. The bill record holds only the committee
            # it is with now, so a report from an earlier one had no name.
            "committee": (e.get("committee")
                          or (senate_cmte if e.get("body") == "S" else house_cmte)),
            "side": e.get("side", ""),
            "recommendation": (e.get("recommendation") or "").upper(),
            "vote_yeas": int(e["yeas"]) if e.get("yeas") else None,
            "vote_nays": int(e["nays"]) if e.get("nays") else None,
            "amendment": e.get("amendment", ""),
            "new_title": bool(e.get("new_title")),
            "cite": e.get("cite", ""),
            "cite_url": (sources.get(f"{e['cite']} {(e.get('date') or '')[:4]}")
                         or sources.get(e.get("cite", ""), "")),
        })
    docket.sort(key=lambda x: x.get("date") or "9999")

    # Why there is a second report. Taken from the docket between one report
    # and the next, so it is the chamber's own record of what it did rather
    # than an inference from the two reports looking different.
    dates = sorted(x["date"] for x in out + docket if x.get("date"))
    between = []
    for a, z in zip(dates, dates[1:]):
        for e in (narr or {}).get("events", []):
            if e.get("cancelled") or e.get("type") == "report":
                continue
            # Strictly before the later report: an action on the same day
            # is the floor acting on that report, not the reason for it.
            if a < (e.get("date") or "") < z and REPORT_AGAIN.search(
                    e.get("raw", "")):
                between.append({"before": z, "date": e["date"],
                                "text": e.get("raw", "")})
                break
    return out, docket, between


def hearing_testimony(e, tdb, scraped):
    """Who signed in for and against, on the hearing this line records.

    The database carries the hearing DATE with each sign-in, so the count sits
    with the hearing it belongs to rather than as one number for the whole
    bill -- which is the point of it: a hearing next week, and where opinion
    stands today. 2,072 of the 2,122 docket hearing lines match a date the
    database also has.

    Counts only. The table has names, towns and the written testimony, and
    almost every one of the 400,000 rows is a private individual who signed a
    committee's sheet; fetch_testimony_db does not ask for any of it.
    """
    if not PUBLIC_HEARING.search(e.get("raw", "")):
        return {}
    if tdb:
        hit = next((h for h in tdb.get("hearings", [])
                    if h.get("date") == e.get("date")), None)
        if hit:
            return {"testimony": {**hit, "dated": True}}
        # The database has the bill but not this date. Its whole-bill total is
        # still true of the bill; it is just not true of this hearing alone,
        # and the page has to say which it is showing.
        return {"testimony": {k: tdb[k] for k in
                              ("total", "support", "oppose", "neutral")}}
    return {"testimony": scraped} if scraped else {}


def build_bills(out, bills, narratives, rollcalls, reports, sponsors,
                bill_texts, amend_texts, testimony, testimony_db, procs, floor, segs,
                marks, sources, legs, leg_by_sort, leg_by_name,
                votes_by_bill):
    """One JSON per bill, and the index row for each.

    This is the loop ARCHITECTURE item 5 names. It ran inside a 955-line
    main(), which is how `st` came to mean the bill's status record at the
    top and a video station 350 lines later -- costing 611 bills their
    facts, their bill-text link and, for 496, their status line.

    Every input is named in the signature rather than inherited from an
    enclosing scope, so a name can no longer be quietly reused.

    Returns (index, years, unnamed, sponsored) -- unnamed being the member
    ids the roll calls reference that the roster cannot name, and sponsored
    being what each member put their name to, which the legislator pages have
    advertised since they were written and never had.
    """
    unnamed = set()
    sponsored = defaultdict(list)

    def _vote_name(m, body):
        """One member's entry in a roll call.

        The name comes from the VOTE record, which build_data.py has already
        resolved against the roster and against former_members.json. The
        roster is the fallback rather than the source, because it holds
        sitting members only.

        Not "label": that field is a composite of name, party and seat, and
        the roll call grid wants a name.

        The party letter comes from the vote too, so the name agrees with the
        party segment the member is shown under.
        """
        raw = (m.get("name") or "").strip()
        if not raw or raw.lower().startswith(("member #", "former member")):
            rec = legs.get(m.get("member_id"), {})
            raw = (rec.get("name") or raw or "").strip()
        if not raw or raw.lower().startswith(("member #", "former member")):
            unnamed.add(str(m.get("member_id")))
            raw = f"Member #{m.get('member_id')}"
        lab = member_labels(raw, chamber=(legs.get(m.get("member_id"), {})
                                          .get("chamber") or body),
                            party=m.get("party"))
        return {"n": lab["display"], "s": lab["sort"] or sort_name(raw),
                "p": m.get("party") or "X", "v": m.get("vote")}
    index, years = [], set()
    status_pages = load("bill_status.json", {})
    if status_pages:
        n = (sum(len(v) for v in status_pages.values())
             if P.term_keyed(status_pages) else len(status_pages))
        terms = (", ".join(sorted(status_pages)) if P.term_keyed(status_pages)
                 else "one term, not keyed")
        print(f"stated status available for {n:,} bills ({terms})")
    n_stated = 0

    # Every bill of every term the file holds. The term is still taken from the
    # bill's own filing year rather than from the key, so the two can be
    # compared if they ever disagree.
    #
    # bill_status.json and bill_text.json are keyed on the term. Either may
    # still be in the flat shape, in which case it holds the current term and
    # P.per_term hands an archived term nothing -- HB100 exists in every
    # biennium, so the current term's text on an archived bill is worse than
    # no text. testimony.json is still flat and is read through the `own`
    # guard below for the same reason.
    current = max(bills) if bills else ""
    for bid, b in ((k, v) for byb in bills.values() for k, v in byb.items()):
        # New Hampshire sits in two-year terms beginning in odd years. Bill
        # numbers are unique across the whole term, so the term -- not the year
        # -- is the unit a number identifies within, and it has to be known
        # before anything is looked up by bill number.
        year = int(b.get("lsr_year") or 0)
        term = P.term_of(str(year)) if year else ""
        rcs = rollcalls.get(term, {}).get(bid, [])
        tdb = testimony_db.get(term, {}).get(bid)
        narr = narratives.get(term, {}).get(bid)
        # Only for the term these files describe; see the loop header.
        own = term == current
        # An archived term reads its own term out of bill_status.json, and
        # falls back to the statuses carried on the bill record itself -- put
        # there by build_data from the General Court's own search, in the same
        # vocabulary classify_stated already reads -- for a term the file does
        # not hold yet.
        st = P.per_term(status_pages, term, current).get(bid, {})
        if not st and not own:
            st = {k: b.get(k, "") for k in ("gen_status", "house_status",
                                            "senate_status", "text_pdf")}
        prefix = bill_prefix(bid)
        told = classify_stated(st, prefix)
        settled = docket_outcome(narr)
        disposed = floor_disposed(narr)
        if settled:
            # A dated docket line beats a status field that has not caught up.
            kind, status = settled
            n_stated += 1
        elif told and told[0] == "active" and disposed:
            # A bill cannot be "In committee" after the chamber adopted a
            # motion to kill it. The status columns are not always advanced
            # once a bill is finished -- 21 of them still read REPORT FILED or
            # NO ACTION on bills signed into law -- and an in-progress status
            # is the one case where a dated floor vote is plainly later than
            # the field. Only "active" yields; a stated outcome still wins.
            kind, status = disposed
            n_stated += 1
        elif told:
            kind, status = told
            n_stated += 1
        else:
            kind, status = classify(narr, rcs, prefix)
        # Sponsor records already carry member_id, party and chamber from
        # build_data.py, and for the LsrSponsors path that id IS the roster's.
        # The bill-status fallback path carries a web member id from a
        # different space, so that one falls back to matching on the name.
        sp_list = []
        for _s in P.per_term(sponsors, term, current).get(bid, []):
            _m = (legs.get(_s.get("member_id"))
                  or leg_by_sort.get(sort_name(_s.get("name") or ""))
                  or leg_by_name.get(name_key(_s.get("name") or "") or ("", ""))
                  or {})
            # The roster first, then whatever the sponsor record carries in
            # its own right. build_data fills the county and district in for a
            # member who has left, from former_members.json, so that they are
            # named the same way as anyone else: "Rep. Suzanne Vail (D - Hills
            # 6)", not a bare name under a heading about a missing chamber.
            _lab = member_labels(
                _s.get("name"),
                chamber=_m.get("chamber") or _s.get("chamber"),
                party=_m.get("party_code") or _s.get("party"),
                district=_m.get("district") or _s.get("district"),
                county=_m.get("county") or _s.get("county"),
                county_abbr=_m.get("county_abbr"))
            # The address of this member's own page, where the sponsor was
            # matched to the roster. Where they were not -- a former member,
            # or a name the join missed -- there is no page and no link, which
            # is the honest outcome rather than a link that goes nowhere.
            _slug = member_slug(_m, _lab) if _m.get("id") else ""
            sp_list.append({**_s, **_lab, "slug": _slug})
        for _s in sp_list:
            _mid = str(_s.get("member_id") or "")
            if _mid:
                sponsored[_mid].append({
                    "bill": bid, "n": b.get("designation") or bid,
                    "title": b.get("title", ""), "year": year, "term": term,
                    "prime": bool(_s.get("prime"))})
        prime = next((s for s in sp_list if s.get("prime")), sp_list[0] if sp_list else None)
        years.add(year)
        ev = [e for e in (narr or {}).get("events", []) if not e.get("cancelled")]
        dates = sorted(e["date"] for e in ev if e.get("date"))
        act_years = {d[:4] for d in dates}
        # Filed one year, acted on the next: retained in committee or sent to
        # interim study. These are exactly the bills someone loses when they
        # search the current year and the bill was filed in the previous one.
        carried = len(act_years) > 1
        # Committees carry their chamber. Both chambers have a Finance, a
        # Judiciary and a Ways and Means, and the ones that differ differ
        # slightly -- Senate "Health and Human Services" against House "Health,
        # Human Services and Elderly Affairs" -- which is worse than a
        # collision, because it looks like a typo rather than two committees.
        #
        # A bill also gets BOTH where it has both. The old line took the House
        # committee or the Senate one, so a Senate bill's own committee vanished
        # from the facets the moment it crossed over and was referred in the
        # House. Filtering for the committee that actually heard it found
        # nothing.
        cmtes = [f"{ch} {nm}" for ch, nm in
                 (("House", b.get("house_committee") or ""),
                  ("Senate", b.get("senate_committee") or "")) if nm]
        cmte = cmtes[0] if cmtes else ""
        index.append({
            "id": bid,
            "n": b.get("designation") or re.sub(r"^([A-Z]+)(\d+)$", r"\1 \2", bid),
            "year": year, "title": b.get("title", ""),
            # The sponsor FACET groups on this string, so it has to be one
            # spelling per person. The two sources spell a name differently --
            # the LSR files write "Germana, Nicholas" and the status page
            # writes "Nicholas Germana" -- and the raw name was going straight
            # into the facet, so 323 of the site's 430 sponsors were listed
            # twice, once per source. person_name() is the same normaliser the
            # display label already goes through.
            "sponsor": person_name(prime["name"]) if prime else "",
            "sponsor_label": prime.get("display", "") if prime else "",
            "committee": cmte, "committees": cmtes,
            "topic": b.get("subject", ""),
            "kind": kind, "status": status,
            "term": term, "carried": carried,
            # An archived term, whose bills come from the General Court's
            # search rather than from a session's own files. The page says
            # so, because an empty summary reads as a broken page and this
            # is a stated limit rather than a fault.
            **({"archived": True} if b.get("archived") else {}),
            "status_stated": bool(told),
            "last_action": dates[-1] if dates else "",
            "nrc": len([r for r in rcs if not r.get("procedural")]),
            "votedays": sorted({r["date"] for r in rcs if r.get("date")}),
        })

        # ---- one detail file per bill, loaded only when expanded
        # ---- the official documents behind this bill --------------------
        # Every one of these is a page or a PDF the General Court publishes.
        # They are already scattered across the tabs -- a text link in the
        # header, a citation on a timeline row, a calendar name under a
        # committee report -- and somebody who wants the source rather than
        # the summary has to hunt for them. Gathered in one place, with the
        # thing each one actually is written next to it.
        # Every committee report on this bill, dated and in order, with
        # the Senate's alongside the House's. Computed here because the
        # Documents list below cites the same calendars.
        rep_written, rep_docket, rep_actions = committee_reports(
            reports.get(term, {}).get(bid, []), narr, sources,
            b.get("house_committee", ""), b.get("senate_committee", ""))

        docs, seen_doc = [], set()

        def add_doc(label, url, kind):
            if url and url not in seen_doc:
                seen_doc.add(url)
                docs.append({"label": label, "url": url, "kind": kind})

        # billText.aspx needs the session year as well as the id. Without it
        # the page answers with an ASP.NET error and the reader gets a blank
        # screen. Records fetched before that was understood carry a two-
        # parameter link, so the year is added here from the bill's own filing
        # year -- which is what the status page's link says, on every one
        # checked. Re-running fetch_bill_status.py --reparse replaces the
        # guess with the page's own value and needs no network.
        text_url = st.get("text_pdf", "")
        if text_url and "sy=" not in text_url:
            sy = st.get("text_year") or b.get("lsr_year") or ""
            if sy:
                text_url += f"&sy={sy}"
        add_doc("Bill text", text_url, "text")
        add_doc("Bill status page", (
            "https://gc.nh.gov/bill_status/legacy/bs2016/Bill_status.aspx"
            f"?lsr={b.get('lsr_num','')}&sy={b.get('lsr_year','')}"
            f"&txtsessionyear={b.get('lsr_year','')}"
            f"&txtbillnumber={bid.lower()}&sortoption=billnumber"), "status")
        add_doc("Docket", (
            "https://gc.nh.gov/bill_status/legacy/bs2016/bill_docket.aspx"
            f"?lsr={b.get('lsr_num','')}&sy={b.get('lsr_year','')}"
            f"&txtsessionyear={b.get('lsr_year','')}"
            f"&txtbillnumber={bid.lower()}&sortoption=billnumber"), "docket")
        # The journals and calendars the docket itself cites. These are the
        # official record of the individual actions, which is a stronger thing
        # to link than a summary of them.
        # One entry per volume, naming every page of it this bill is on.
        # add_doc dedupes on the URL, and a volume has one URL however many
        # pages are cited -- so listing them per event kept whichever page came
        # first and dropped the rest without a word. 565 of the 7,013 volumes
        # cited on this site carry a bill on more than one page; HB686 is on
        # HJ 7 at both 143 and 144, and the list named only 143.
        vols = {}
        for e in (narr or {}).get("events", []):
            if e.get("cancelled"):
                continue
            c = _cite(e, sources, (e.get("date") or "")[:4])
            if not c.get("cite_url"):
                continue
            key = (e.get("cite") or "").strip()
            v = vols.setdefault(key, {"url": c["cite_url"], "pages": []})
            pg = (e.get("cite_page") or "").strip()
            if pg and pg not in v["pages"]:
                v["pages"].append(pg)
        for key, v in vols.items():
            pages = sorted(v["pages"], key=lambda x: int(x))
            label = key + ("" if not pages else
                           f", page {pages[0]}" if len(pages) == 1 else
                           ", pages " + ", ".join(pages[:-1]) + " and " + pages[-1])
            add_doc(label, v["url"], "record")
        # The calendar a committee report was printed in.
        # committee_reports() has already turned each report's calendar into
        # a key and a URL, so this cites what the report itself is citing
        # rather than parsing "House Calendar 51, 2025" a second time.
        for r in rep_written:
            add_doc(f"{r.get('source') or r.get('cite')}, committee report",
                    r.get("cite_url", ""), "report")
        for r in rep_docket:
            if r.get("cite_url"):
                add_doc(f"{r['cite']}, committee report", r["cite_url"], "report")

        bill_amds = bill_amendments(narr, amend_texts)
        btext = bill_text_block(P.per_term(bill_texts, term, current).get(bid))

        rc_out = []
        rc_order, rc_names = vote_chronology(rcs, narr)
        for r in sorted(rcs, key=lambda x: (x.get("date", ""), int(x.get("number", 0)))):
            key = f"{r.get('year')}-{r['body']}-{r['number']}"
            members = votes_by_bill.get((term, bid), {}).get(key, [])
            tally = defaultdict(lambda: defaultdict(int))
            for m in members:
                tally[m["party"] or "X"][m["vote"]] += 1
            rc_out.append({
                "date": r.get("date"), "body": r.get("body"),
                "question": r.get("question"), "yeas": r.get("yeas"),
                "nays": r.get("nays"), "passed": r.get("passed"),
                "threshold_note": r.get("threshold_note"),
                # Which amendment this vote was on, where the docket says so.
                # "Adopt Amendment" twice in an afternoon is two different
                # amendments and no way to tell which is which.
                "amendment": rc_names.get((r.get("body"), r.get("number"))),
                "_ord": (r.get("date") or "",
                         rc_order.get((r.get("body"), r.get("number")),
                                      10 ** 6 + int(r.get("number") or 0))),
                # What the yes side had to reach, so the chart can mark it.
                # rollcall_parser works this out per motion: two thirds of
                # those voting for a veto override, three fifths of the whole
                # membership for a CACR, a simple majority otherwise.
                "threshold_needed": r.get("threshold_needed"),
                "threshold_rule": r.get("threshold_rule"),
                "tally": {p: dict(v) for p, v in tally.items()},
                # "s" is the surname-first sort key. The grids are read
                # alphabetically, and sorting the displayed string would order
                # 400 members by honorific and then by first name.
                "members": [_vote_name(m, r.get("body")) for m in members],
            })

        # Voice and division votes, from the docket. A voice vote records only
        # which side sounded louder; a division records the count but not who
        # voted which way. Both decide bills, and leaving them off the votes tab
        # makes a bill look as though nothing happened on the floor.
        VK = {"VV": ("voice vote", False), "DV": ("division vote", False)}
        for _i, e in enumerate((narr or {}).get("events", [])):
            if e.get("type") != "floor" or e.get("cancelled"):
                continue
            kind = VK.get(e.get("vote_kind"))
            if not kind:
                continue          # RC is already covered by the roll call file
            label, _ = kind
            y, n = e.get("yeas"), e.get("nays")
            rc_out.append({
                "date": e["date"], "body": e.get("body"),
                "question": e.get("action") or "Floor action",
                "yeas": int(y) if y else None, "nays": int(n) if n else None,
                "passed": e.get("motion") in ("MA", "AA"),
                "vote_kind": e.get("vote_kind"), "vote_kind_label": label,
                "threshold_note": None, "tally": {}, "members": [],
                "amendment": None, "_ord": (e["date"], _i),
            })
        # By the docket's own sequence, not by the wording of the motion.
        rc_out.sort(key=lambda r: r["_ord"])
        for r in rc_out:
            r.pop("_ord", None)

        # Two short builders, defined together above main(). Committee
        # proceedings and floor appearances are different enough to need
        # different code and close enough that a change to one usually belongs
        # in the other; adjacent functions make that visible, which one long
        # function did not.
        stations = [station_for_proceeding(p, bid, segs, marks)
                    for p in sorted(procs.get((term, bid), []),
                                    key=lambda x: (x["sched_date"],
                                                   x["sched_time"] or ""))]
        # The sign-in counts, on the hearing itself. They already reach the
        # docket line that records the hearing -- 2,115 of them across 2,018
        # bills -- but that line sits inside a collapsed disclosure on another
        # tab, so somebody wanting to know how opinion stood before a hearing
        # had to go looking for it among the raw docket actions.
        #
        # Matched on the date, so the figure belongs to THIS hearing. Where
        # the database has the bill but not this date, nothing is attached
        # rather than the whole-bill total: on a station the reader is looking
        # at one sitting, and a number that quietly means something else is
        # worse than no number. The docket line still shows the whole-bill
        # figure and still says that is what it is.
        if tdb:
            _by_date = {h.get("date"): h for h in (tdb.get("hearings") or [])}
            for _st in stations:
                if "hearing" not in (_st.get("what") or "").lower():
                    continue
                _hit = _by_date.get(_st.get("when"))
                if _hit:
                    _st["testimony"] = {**_hit, "dated": True}
        # Floor debates, stacked with the committee proceedings and sorted by
        # date so a bill's whole journey reads in order: hearing, executive
        # session, floor, then the second chamber.
        stations += [station_for_floor(f, bid, marks)
                     for f in floor.get((term, bid), [])]
        stations.sort(key=lambda x: (x["when"], x.get("time") or ""))

        # Under the filing year, because a bill number is unique within a term
        # and not beyond it. A 2027 HB686 is a different bill from this one and
        # would have overwritten it here, taking its docket, its votes and its
        # recordings with it. The static page and the feed have carried the
        # year in their paths from the start -- build_bill_pages says why, in
        # as many words -- and both of them read THIS file, so the year they
        # were keeping the pages apart by was doing nothing for the data.
        _bd = out / "bills" / str(year)
        _bd.mkdir(parents=True, exist_ok=True)
        (_bd / f"{bid}.json").write_text(json.dumps({
            "id": bid, "year": year, "term": term,
            "title": b.get("title", ""),
            "narrative": (narr or {}).get("narrative", ""),
            # The history, plus a closing paragraph where the bill's ending
            # is only on the status page. 120 bills showed a settled headline
            # over a story that stopped at the committee report.
            "stages": ((narr or {}).get("stages", [])
                       + [x for x in [closing_stage(status, narr)] if x]),
            "notes": (narr or {}).get("notes", []),
            # Each action keeps the citation it ends with -- "HJ 7 P. 55" -- and
            # the URL of that journal or calendar where we have it. That is the
            # official record of the line being displayed, and it is the thing
            # that makes a claim on this site checkable rather than trusted.
            "events": [{"date": e["date"], "text": e.get("raw", ""),
                        "routine": is_routine(e.get("raw", "")),
                        **hearing_testimony(
                            e, tdb, testimony.get(bid) if own else None),
                        **_cite(e, sources, (e.get("date") or "")[:4])}
                       for e in (narr or {}).get("events", []) if not e.get("cancelled")],
            # Prefer what the General Court says over what we would infer.
            # Where the docket has settled the bill, the per-chamber fields
            # are describing a superseded state and reading them beside
            # "Vetoed, override failed" is a contradiction. Say what happened.
            "next_step": next_step(narr, b, prefix) if settled else (
                " \u00b7 ".join(x for x in [
                    f"House: {st['house_status']}" if st.get("house_status") else "",
                    f"Senate: {st['senate_status']}" if st.get("senate_status") else "",
                ] if x) or next_step(narr, b, prefix)) if told
                       else next_step(narr, b, prefix),
            **({"archived": True} if b.get("archived") else {}),
            "status_source": ("General Court docket" if settled
                              else "General Court bill status page" if told
                              else "derived from the docket"),
            "chapter": st.get("chapter", ""),
            "text_pdf": st.get("text_pdf", ""),
            # The rest of what the status page states. All of it was being
            # fetched and thrown away; the detail page is where it belongs,
            # since these are the facts someone reads when the summary card is
            # not enough.
            "facts": {k: st[k] for k in
                      ("lsr", "body", "local", "gen_status", "house_status",
                       "senate_status", "date_introduced", "floor_date",
                       "committee_code") if st.get(k)},
            "sponsors": sp_list, "rollcalls": rc_out, "stations": stations,
            "reports": rep_written,
            # Reports the docket records that no calendar this site has
            # read printed the reasoning for. Almost all of them are the
            # Senate's, which files one report with a vote and no
            # minority -- the shape the tab used to say was not loaded.
            "docket_reports": rep_docket,
            # What the chamber did between one report and the next.
            "report_actions": rep_actions,
            "subject": b.get("subject", ""),
            "house_committee": b.get("house_committee", ""),
            "senate_committee": b.get("senate_committee", ""),
            "lsr": b.get("lsr", ""),
            "docket_url": ("https://gc.nh.gov/bill_status/legacy/bs2016/bill_docket.aspx"
                           f"?lsr={b.get('lsr_num','')}&sy={b.get('lsr_year','')}"
                           f"&txtsessionyear={b.get('lsr_year','')}"
                           f"&txtbillnumber={bid.lower()}&sortoption=billnumber"),
            "documents": docs,
            # The amendments this bill went through, in the order they were
            # taken up, with the text where the calendars printed it.
            "amendments": bill_amds,
            # The bill itself, as the General Court publishes it.
            "billtext": btext,
            # Statutes cited in the committee's own words and in the bill's
            # title. Committee reports cite the RSAs constantly, and a reader
            # who has to leave to find out what 91-A says usually does not
            # come back.
            # Amendment text as well as report text. An amendment is mostly
            # statute citations by volume -- "Amend RSA 415:6-e, III(a)" is
            # how one opens -- so leaving it out meant the linker missed the
            # place it was most useful.
            "rsa": rsa_links(b.get("title", ""),
                             *[e.get("text", "") for r in rep_written
                               for e in r.get("reports", [])],
                             *[x.get("text", "") for x in bill_amds],
                             # And the bill, which is mostly statute citations
                             # by weight -- it is the document the linker was
                             # built for.
                             (btext or {}).get("body", "")),
        }), encoding="utf-8")

    if status_pages:
        print(f"  {n_stated:,} bills take their status from the page; "
              f"{len(index) - n_stated:,} still derive it from the docket")
    return index, years, unnamed, dict(sponsored)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--narratives", default="narratives.json")
    ap.add_argument("--rollcalls", default="rollcalls.json")
    ap.add_argument("--markers", default="candidate_segments.json",
                    help="boundaries a chair stated, from segment_markers.py")
    ap.add_argument("--allow-no-manifest", action="store_true",
                    help="build anyway, with no committee proceedings at all")
    # "work", not "segments". The aligner writes work/<videoid>/segments.json
    # and every other default here names the file it will actually find, so a
    # bare run of this script quietly built a site with no video timestamps on
    # it at all -- and then reported the cause as a session-year mismatch,
    # which sent the diagnosis in the wrong direction entirely.
    ap.add_argument("--segments", default="work")
    ap.add_argument("--reports", default="committee_reports.json")
    ap.add_argument("--senate-reports", default="senate_reports.json")

    ap.add_argument("--status", default="status/status.txt")
    ap.add_argument("--districts", default="site/districts.json")
    ap.add_argument("--officials", default="status/officials.txt")
    ap.add_argument("--out", default="site")
    a = ap.parse_args()

    D, out = Path(a.data), Path(a.out)
    (out / "bills").mkdir(parents=True, exist_ok=True)
    (out / "legislators").mkdir(parents=True, exist_ok=True)

    bills = load(D / "bills.json", {})
    # {term: {bill: record}} -- the file the whole per-bill loop is driven from.
    # Read flat and the loop would run over term names instead of bills.
    if bills and not P.term_keyed(bills):
        sys.exit(f"{D / 'bills.json'} is keyed on bill number, not on term. "
                 "Rebuild it: python3 build_data.py --dir . --out data")
    sponsors = load(D / "sponsors.json", {})
    legs = {m["id"]: m for m in load(D / "legislators.json", [])}
    # Sponsor records carry a name but not a party or a district. The roster
    # has both, so they are joined on the surname-first form of the name --
    # never on a member id, because there are three id spaces in these files
    # and a sponsor's is not necessarily the roster's. A sponsor who matches
    # nobody keeps a bare name rather than borrowing somebody else's party.
    leg_by_sort, leg_by_name = {}, {}
    for _m in legs.values():
        leg_by_sort.setdefault(sort_name(_m.get("name") or ""), _m)
        _k = name_key(_m.get("name") or "")
        if _k:
            leg_by_name.setdefault(_k, _m)

    # Members who left mid-term are already named upstream: resolve_members.py
    # writes former_members.json to the project root, build_data.py reads it
    # there, and every member_votes row therefore carries a resolved "name"
    # whether the member is sitting or not. That is what the double build_data
    # pass in build_all.py exists for. Reading the file a second time here
    # would only add a way for the two to disagree -- and the copy this looked
    # for, under the data directory, is not where the pipeline writes it.
    towns = load(D / "towns.json", {})
    narratives = load(a.narratives, {})
    # {term: {bill: record}}, for the reason rollcalls.json is: a bill number
    # is unique within a term and not across terms. Reading the old flat shape
    # with a term lookup finds nothing for every bill and still exits zero.
    if narratives and not N.is_term_keyed(narratives):
        sys.exit(f"{a.narratives} is keyed on bill number, not on term. "
                 "Rebuild it: python3 narrative.py --docket Docket.txt --all "
                 f"--out {a.narratives}")
    rollcalls = load(a.rollcalls, {})
    # {term: {bill: [votes]}}, since rollcall_parser started reading past
    # sessions. The older shape was {bill: [votes]}, and reading one with the
    # new lookup returns nothing for every bill without failing -- the exact
    # shape of silence this project keeps getting caught by. So it is checked.
    if rollcalls and not all(isinstance(v, dict) for v in rollcalls.values()):
        sys.exit(f"{a.rollcalls} is keyed on bill number, not on term. Rebuild "
                 "it: python3 rollcall_parser.py --all --out rollcalls.json")
    reports = load(a.reports, {})
    # The Senate's committee reports, with their reasoning, from the General
    # Court's database -- the half the House Calendar PDFs cannot cover. Kept
    # in its own file because fetch_committee_reports.py rebuilds
    # committee_reports.json a calendar year at a time and decides what to keep
    # by looking for ", <year>" in each record's source; a record that is not
    # from a calendar has no business inside that. Merged here instead, which
    # is the one place that has to know both exist.
    senate = load(a.senate_reports, {})
    # Both are {term: {bill: [reports]}} now, for the reason every per-bill file
    # is: a bill number is unique within a term and not across terms. Reading
    # the old flat shape with a term lookup gives every bill no reports and
    # still exits zero, so it is refused.
    for name, data in ((a.reports, reports), (a.senate_reports, senate)):
        if data and not N.is_term_keyed(data):
            sys.exit(f"{name} is keyed on bill number, not on term. Rebuild it: "
                     "delete it and run its fetcher once for each year of the "
                     "term.")
    if senate:
        for term, byb in senate.items():
            into = reports.setdefault(term, {})
            for bid, recs in byb.items():
                into.setdefault(bid, []).extend(recs)
        n_prose = sum(1 for byb in senate.values() for v in byb.values()
                      for r in v for x in r.get("reports", [])
                      if len((x.get("text") or "").split()) >= 15)
        n_bills = sum(len(byb) for byb in senate.values())
        print(f"Senate committee reports: {n_bills:,} bills, "
              f"{n_prose:,} with the committee's reasoning")
    # Written by extract_amendments.py out of the cached calendars. Absent is
    # fine: the amendments are still listed, without their text.
    amend_texts = load("amendments.json", {})
    if amend_texts:
        print(f"{len(amend_texts):,} amendment texts loaded")
    bill_texts = load("bill_text.json", {})
    if bill_texts:
        n = (sum(len(v) for v in bill_texts.values())
             if P.term_keyed(bill_texts) else len(bill_texts))
        print(f"{n:,} bill texts loaded")
    # Journal and calendar URLs, so every docket line can cite its source.
    sources = {**load("calendars.json", {}), **load("journals.json", {})}
    # Sign-in counts, attached to the hearing they were filed for.
    testimony = load("testimony.json", {})
    # Counts per bill AND per hearing, from the General Court's database:
    # 2,019 bills against the scraped page's 565. Keyed on the term, because
    # legislationID is reused across terms -- joining without that put 67,119
    # sign-ins from 2024 onto 856 bills of this one.
    testimony_db = load("testimony_db.json", {})
    if testimony_db:
        nb = sum(len(v) for v in testimony_db.values())
        ns = sum(r["total"] for v in testimony_db.values() for r in v.values())
        print(f"testimony sign-ins: {ns:,} across {nb:,} bills, per hearing")
    if testimony:
        print(f"testimony counts for {len(testimony):,} bills")
    if sources:
        print(f"source links available for {len(sources)} journals and calendars")
    # One table for every proceeding on the site: committee hearings, executive
    # sessions, work sessions, floor debates. Presented below in the two shapes
    # the station code was written against -- manifest columns for committee
    # rows, floor-index keys for floor rows -- so that code did not change.
    # It is the SOURCE that changed. Committee and floor proceedings used to be
    # loaded from two files here, ninety lines apart, and the floor half never
    # saw the markers that had been wired into the committee half.
    prows = P.load()
    if not prows:
        print("=" * 74)
        print("NO proceedings.csv. Every hearing, executive session and floor")
        print("debate on this site comes from that one file. Without it the")
        print("build will finish and publish a site with none of them, and no")
        print("error anywhere to say why.")
        print("")
        print("Run: python3 build_proceedings.py")
        print("=" * 74)
        if not a.allow_no_manifest:
            raise SystemExit("Refusing to build without it. Pass "
                             "--allow-no-manifest to override.")

    # Keyed (term, bill), like everything else per-bill on this site. Keyed
    # on the number alone, and with the per-bill file written per filing
    # year, site/bills/2023/CACR10 carried the 2025-2026 CACR10's hearings
    # and floor debates verbatim -- an archived bill showing another term's
    # recordings. The path was made term-aware and this lookup was not.
    procs = defaultdict(list)
    for r in P.committee_only(prows):
        procs[(r["term"], r["bill"])].append({
            "bill": r["bill"], "body": r["body"], "committee": r["committee"],
            "proceeding": r["kind"], "sched_date": r["date"],
            "sched_time": r["time"], "venue": r["venue"], "match": r["match"],
            "video_id": r["video_id"], "video_title": r["video_title"],
            "stream_start": r["stream_start"],
            "predicted_offset": ("" if r["predicted_offset"] is None
                                 else r["predicted_offset"]),
        })
    floor = defaultdict(list)
    for r in P.floor_only(prows):
        floor[(r["term"], r["bill"])].append({
            "date": r["date"], "body": r["body"], "video_id": r["video_id"],
            "motions": r["motions"], "tallies": r["tallies"],
            "kind": r["kind"], "debate_end": r["debate_end"],
            "window_start": r["window_start"], "precise": r["precise"],
            "whole_video": r["whole_video"], "title": r["video_title"],
        })
    print(f"{sum(len(v) for v in procs.values()):,} committee proceedings and "
          f"{sum(len(v) for v in floor.values()):,} floor appearances from "
          f"{P.PATH.name}")

    votes_by_bill = defaultdict(lambda: defaultdict(list))
    votes_by_member = defaultdict(list)
    for v in load(D / "member_votes.json", []):
        # A vote sequence number restarts each session, so "H-112" names two
        # different roll calls once 2025 sits beside 2026 -- and both years
        # belong to the same term, so the term alone does not separate them.
        # The bill is keyed by term for the same reason every other per-bill
        # map now is: HB396 exists in every biennium.
        key = f"{v['year']}-{v['body']}-{v['vote_number']}"
        votes_by_bill[(P.term_of(v["year"]), v["bill"])][key].append(v)
        votes_by_member[v["member_id"]].append(v)
    print(f"{len(bills):,} bills, {len(legs):,} legislators, "
          f"{sum(len(x) for x in votes_by_member.values()):,} member votes")

    # The aligner writes work/<videoid>/segments.json; an earlier layout used
    # segments/<videoid>.json. Accept either so the site picks them up wherever
    # they are.
    segs = {}
    sp = Path(a.segments)
    if sp.exists():
        for f in sp.glob("*.json"):
            segs[f.stem] = json.loads(f.read_text(encoding="utf-8"))
        for d_ in sp.iterdir():
            f = d_ / "segments.json"
            if d_.is_dir() and f.exists():
                segs[d_.name] = json.loads(f.read_text(encoding="utf-8"))
    print(f"segments loaded for {len(segs):,} videos")

    # Boundaries a chair stated aloud, from segment_markers.py. Measured
    # against the 35 hand-marked proceedings at a median of ONE SECOND, with
    # ends at four -- against 1m 27s for the clustering estimate and 17m 05s
    # for the schedule. Where one of these exists it is not an improvement on
    # the estimate, it is a different kind of claim: a quotation rather than an
    # inference, and the page says so.
    mp2 = Path(a.markers)
    marks = {}
    if mp2.exists():
        try:
            marks = json.loads(mp2.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            marks = {}
    if marks:
        # _absent and _sequence are siblings of the recordings, not recordings,
        # and counting them made the total two higher than the truth.
        vids = {k: v for k, v in marks.items() if not k.startswith("_")}
        nb = sum(len(v) for v in vids.values())
        print(f"{nb:,} stated boundaries across {len(vids):,} recordings "
              f"from {mp2.name}")
    # A silent mismatch here looks exactly like poor alignment accuracy: every
    # hearing reads "start time not identified" because the transcripts are for
    # a different set of videos than the manifest now points at.
    if procs:
        man_vids = {r["video_id"] for rs in procs.values() for r in rs
                    if r.get("video_id")}
        overlap = man_vids & set(segs)
        print(f"  manifest references {len(man_vids):,} videos; "
              f"{len(overlap):,} of them have transcripts")
        if man_vids and not overlap:
            print(f"  NONE overlap. Either --segments is pointing somewhere "
                  f"with no transcripts\n  in it (it is {a.segments!r}; the "
                  "aligner writes work/<videoid>/segments.json),\n  or the "
                  "transcripts cover a different set of videos than the "
                  "manifest --\n  most likely a different session year.")
        elif len(overlap) < len(man_vids) * 0.5:
            print(f"  {len(man_vids) - len(overlap):,} manifest videos have no "
                  "transcript; those proceedings get a recording link with no "
                  "start time.")



    # -------------------------------------------------------------- index --
    index, years, unnamed, sponsored = build_bills(out, bills, narratives, rollcalls, reports,
                               sponsors, bill_texts, amend_texts, testimony,
                               testimony_db,
                               procs, floor, segs, marks, sources,
                               legs, leg_by_sort, leg_by_name,
                               votes_by_bill)
    (out / "index.json").write_text(json.dumps(index), encoding="utf-8")
    size = (out / "index.json").stat().st_size / 1024
    print(f"index.json: {size:.0f} KB for {len(index):,} bills "
          f"(roughly {size/4:.0f} KB gzipped, which is what a static host sends)")

    # (term, bill) -> the year its page is under, so a vote can link to the
    # right one of two bills sharing a number.
    bill_year = {(t, b): str(r.get("lsr_year") or "")
                 for t, byb in bills.items() for b, r in byb.items()}
    lg = build_legislators(out, legs, votes_by_member, towns, unnamed,
                           sponsored, bill_year)

    # ---- home page data ----------------------------------------------------
    # Everything the landing page needs, precomputed here where the full records
    # are already in memory rather than making the browser fetch 2,000 files.
    today = _date.today().isoformat()
    soon = (_date.today() + _td(days=14)).isoformat()
    recent_cut = (_date.today() - _td(days=3650)).isoformat()

    actions = []
    for b in index:
        narr = narratives.get(b["term"], {}).get(b["id"])
        for e in (narr or {}).get("events", []):
            if e.get("cancelled") or not e.get("date") or e["date"] > today:
                continue
            actions.append({"date": e["date"], "bill": b["id"], "n": b["n"],
                            "title": b["title"][:110], "what": e.get("raw", "")[:150]})
    actions.sort(key=lambda x: x["date"], reverse=True)

    upcoming = []
    for bid, ps in procs.items():
        for pr in ps:
            d = pr.get("sched_date", "")
            if today <= d <= soon:
                upcoming.append({"date": d, "time": pr.get("sched_time"),
                                 "bill": bid, "committee": pr.get("committee"),
                                 "what": pr.get("proceeding"),
                                 "venue": pr.get("venue")})
    upcoming.sort(key=lambda x: (x["date"], x["time"] or ""))

    # "Most contested" beats "most viewed": it is a fact about the record rather
    # than about traffic, and needs no analytics on a static site.
    contested = sorted([b for b in index if b["nrc"] > 1],
                       key=lambda b: -b["nrc"])[:8]
    closest = []
    for b in index:
        for r in rollcalls.get(b["term"], {}).get(b["id"], []):
            # RollCallSummary holds chamber floor votes only, but be explicit:
            # procedural motions and anything without a tally are excluded, so
            # "closest" means how close the chamber came on the bill itself.
            if r.get("procedural") or not r.get("yeas"):
                continue
            if r.get("body") not in ("H", "S"):
                continue
            m = abs(r["yeas"] - r["nays"])
            if m <= 12:
                closest.append({"bill": b["id"], "n": b["n"], "title": b["title"][:110],
                                "date": r.get("date"), "q": r.get("question"),
                                "y": r["yeas"], "nn": r["nays"], "margin": m})
    closest.sort(key=lambda x: (x["margin"], x["date"] or ""))

    # "Still moving" counts the CURRENT term only. A bill that did not finish
    # before its biennium ended did not carry on moving -- it died with the
    # session -- and counting 492 bills of 2023-2024 among the 599 the home
    # page called live was the site asserting something that stopped being
    # true two years ago. The other totals are of the whole record on purpose:
    # a law passed in 2023 is still a law.
    newest = max((b["term"] for b in index if b.get("term")), default="")
    by_kind = defaultdict(int)
    for b in index:
        if b["kind"] == "active" and b.get("term") and b["term"] != newest:
            continue
        by_kind[b["kind"]] += 1
    # One per chamber. The House and Senate sit on different days, so a single
    # "most recent" hides whichever sat second.
    latest_by_body = {}
    for v in floor.values():
        for f in v:
            if not (f.get("date") and f.get("video_id")):
                continue
            b = f.get("body") or "H"
            cur = latest_by_body.get(b)
            if not cur or f["date"] > cur["date"]:
                latest_by_body[b] = {"date": f["date"], "video_id": f["video_id"],
                                     "chamber": "House" if b == "H" else "Senate"}
    latest_session = latest_by_body.get("H")   # kept for older page versions

    comp, vac = build_composition(a, legs)
    status = build_status(a, index, procs, floor, today,
                          latest_by_body, upcoming)
    (out / "home.json").write_text(json.dumps({
        "status": status, "composition": comp,
        "generated": today,
        "counts": {"bills": len(index), "legislators": len(lg) if 'lg' in dir() else 0,
                   "votes": sum(len(x) for x in votes_by_member.values()),
                   "by_kind": dict(by_kind)},
        "terms": sorted({b["term"] for b in index if b["term"]}, reverse=True),
        "recent": actions[:12], "upcoming": upcoming[:12],
        "contested": contested, "closest": closest[:6],
        "latest_session": latest_session,
        "latest_sessions": [latest_by_body[b] for b in ("H", "S")
                            if b in latest_by_body],
    }), encoding="utf-8")
    print(f"home.json: {len(actions):,} actions, {len(upcoming)} upcoming, "
          f"{len(closest)} close votes")
    for ch in ("H", "S"):
        c = comp[ch]
        print(f"  {c['chamber']}: {c['sitting']} of {c['seats']} seats"
              + (f", {c['vacant']} vacant" if c["vacant"] else "")
              + " — " + ", ".join(f"{p['n']} {p['code']}" for p in c["parties"]))
    if vac:
        print(f"  {sum(v['vacant'] for v in vac)} vacant House seats identified "
              f"across {len(vac)} districts")

    # Name as the index writes it -- "House Finance" -- to the code its page
    # lives at. Both chambers have a Finance, so the chamber is part of the
    # key, and it comes from the code's own first letter.
    committee_codes = {}
    for _code, _rec in (load(D / "committees.json", {}) or {}).items():
        _nm = (_rec.get("name") or "").strip()
        _ch = _code[:1].upper()
        if _nm and _ch in ("H", "S"):
            committee_codes[f"{'House' if _ch == 'H' else 'Senate'} {_nm}"] = _code
    meta = {"years": sorted(years, reverse=True),
            "terms": sorted({b["term"] for b in index if b["term"]}, reverse=True),
            "committees": sorted({b["committee"] for b in index if b["committee"]}),
            # {"House Finance": "H34"}, so a committee named on a bill card is
            # a link to that committee rather than a dead end -- 3,967
            # mentions across the site, none of them clickable before.
            # Written from data/committees.json, whose codes carry the
            # chamber, because "Finance" alone names one in each.
            "committee_codes": committee_codes,
            "topics": sorted({b["topic"] for b in index if b["topic"]}),
            "sponsors": sorted({b["sponsor"] for b in index if b["sponsor"]}),
            "votedays": sorted({d for b in index for d in b["votedays"]}, reverse=True)}
    (out / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    print(f"facets: {len(meta['committees'])} committees, {len(meta['topics'])} topics, "
          f"{len(meta['sponsors'])} sponsors, {len(meta['votedays'])} vote days")

    total = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print(f"\nsite data: {total/1e6:.1f} MB total, {size:.0f} KB loaded up front")
    print(f"-> {out}/")
    print("\nNext: the HTML shell reads index.json and meta.json for search and")
    print("facets, then fetches bills/<year>/<id>.json when a card is expanded.")


if __name__ == "__main__":
    main()
