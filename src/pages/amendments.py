#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-20.1
"""
A bill's amendments and its text: the amendments the docket moved, in the
order it took them up, with what each says it changes (bill_amendments,
amendment_targets), and the text the General Court printed, its analysis
told apart from the bill itself (bill_text_block).

    import amendments as AM
    AM.bill_text_block(rec, narr)           # {"analysis", "body", "fiscal", "in_text", ...}
    AM.bill_amendments(narr, texts, claimed)   # every amendment on one bill, in order
    AM.amendment_claims(narratives)         # {term: {number: {bills whose docket names it}}}
    AM.amendment_num(event)                 # "2026-0103h", or ""

A SECTION OF build_site_v2.py UNTIL 20 NOVEMBER 2026 (the refactor's finding
4, reports/refactor/stage0-code.md: amendments and texts). It moved here as
it stood, comments and all, from AMEND_NUM to _amendment_said; the import of
session_days' ADOPTED and amendment_carried that stood inside it stays in
build_site_v2 with its comment, and this imports amendment_carried, the one
it reads, at its head. It imports no builder (_import_cycles_cut).
build_site_v2 imports every name here back under its own, so
build_site_v2.bill_amendments and the rest answer as they did, for
vote_chronology, bill_rollcalls, build_bills and the checks.
"""

import re
from collections import defaultdict

import fiscal
# Whether one amendment event says its amendment was adopted, rejected or
# neither (_amendment_said below): session_days', which a session day reads too.
from session_days import amendment_carried


AMEND_NUM = re.compile(r"#\s*(\d{4}-\d+[a-z]?)", re.I)
AMEND_ANY = re.compile(r"\b(\d{4}-\d{3,4}[a-z]?)\b")


# What an amendment says it changes. New Hampshire amendments are written as
# instructions rather than as a redline: "Amend RSA 415:6-e, III(a) as inserted
# by section 1 of the bill by replacing it with the following". So the targets
# can be read off the instruction, and two amendments touching the same target
# is the case where the later one governs.
# The same widening as RSA_CITE below, and for the same reason: a two-letter
# chapter (126-AA) and a hyphenated or dotted section (6-602, 10.01) are real
# addresses, and this pattern dropped an amendment's target entirely when it met
# one -- so the Changes row silently lost the statute the bill actually amends.
RSA_CITE_T = re.compile(
    r"\bRSA\s+(\d{1,3}(?:-[A-Z]{1,2})?:\d{1,4}(?:-[a-z0-9]{1,3})?(?:\.\d{1,2})?"
    r"(?:,\s*[IVXLC]+(?:-[a-z])?)?(?:\([a-z]\))?)(?!\d)", re.I)
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


# THE AMENDMENTS A TEXT SAYS IT CARRIES, BY THEIR OWN NUMBERS (the polish
# survey of 7 October 2026). The text prints them short, "20Mar2025 0103h",
# and fetch_bill_text gives each the year of the session its page is of:
# HB 68 of 2025-2026, carried over into 2026, read "includes 2026-0103h",
# where its history and docket say 2025-0103h, adopted on 20 March 2025 -- 76
# numbers on 54 bills. The number the bill's own docket gives with that
# short form is the amendment's: as its amendment and report rows give it,
# or, where they give none, as any of its rows does -- once, so that a
# clerk's slip elsewhere ("House Concurs with Senate Amendment 2026-3030s"
# on HB 126, whose amendment rows say 2025-3030s) does not choose. One the
# docket does not name is left as the page gave it. And one the text lists
# twice (HB 126's heading repeats its two) is listed once.
def amendments_in_text(stamps, narr):
    """The text's [{"date", "short", "num"}] with each num the bill's
    docket's own where the docket names that short form once (above), and
    each amendment once."""
    own, anywhere = defaultdict(set), defaultdict(set)

    def put(to, num):
        m = re.fullmatch(r"\d{4}-0*(\d+)([a-z])", (num or "").strip())
        if m:
            to[(int(m.group(1)), m.group(2))].add(num.strip())

    for e in (narr or {}).get("events", []):
        if e.get("type") in ("amendment", "report"):
            put(own, e.get("amendment"))
        for num in AMEND_ANY.findall(e.get("raw") or ""):
            put(anywhere, num)
    out, seen = [], set()
    for s in stamps or []:
        s = dict(s)
        m = re.fullmatch(r"0*(\d+)([a-z])", (s.get("short") or "").strip())
        key = (int(m.group(1)), m.group(2)) if m else None
        full = own.get(key) or anywhere.get(key)
        if full and len(full) == 1:
            s["num"] = next(iter(full))
        key = s.get("num") or s.get("short")
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def bill_text_block(rec, narr=None):
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
    # The fiscal note is a table, flattened to one column by the PDF
    # extraction. Taken out of the body so it can be drawn as a table and
    # not printed twice.
    note, rest = fiscal.parse(rest)
    return {"version": rec.get("version") or "",
            "title": rec.get("title") or "",
            "analysis": analysis,
            **({"fiscal": note} if note else {}),
            "body": rest.strip(),
            "in_text": amendments_in_text(rec.get("amendments_in_text"), narr),
            "chars": len(body)}


def amended_bill(s):
    """'HB 614-FN' -> 'HB614', 'SSHB1' -> 'HB1': near enough to compare the
    bill an amendment's heading names with the bill it is shown on, a Senate
    substitute amending the bill it substitutes for. extract_amendments.
    plain_bill writes the headings the same way."""
    m = re.match(r"(?:SS)?([A-Z]+)[ \t]*0*(\d+)", (s or "").upper().strip())
    return f"{m.group(1)}{int(m.group(2))}" if m else ""


def amendment_num(e):
    """The amendment number a docket event moves, or ''."""
    num = (e.get("amendment") or "").strip()
    if not num:
        m = AMEND_NUM.search(e.get("raw", "")) or AMEND_ANY.search(e.get("raw", ""))
        num = m.group(1) if m else ""
    return num


def amendment_claims(narratives):
    """{term: {amendment number: {bills whose docket names it}}}: in any line,
    since a committee's report names the amendment it recommends before any
    line moves it -- "Ought to Pass with Amendment #2022-0996h" on HB 1347."""
    out = defaultdict(lambda: defaultdict(set))
    for term, byb in (narratives or {}).items():
        if not isinstance(byb, dict):
            continue
        for bid, narr in byb.items():
            for e in (narr or {}).get("events", []):
                nums = set(AMEND_ANY.findall(e.get("raw") or ""))
                if e.get("amendment"):
                    nums.add(e["amendment"].strip())
                for num in nums:
                    out[term][num].add(amended_bill(bid))
    return out


def bill_amendments(narr, texts, claimed=None):
    """Every amendment on one bill, in the order the docket took them up.

    Order is the whole point. A committee amendment is considered before any
    floor amendment, and where two touch the same section the later one wins,
    so a list sorted any other way describes a bill that does not exist. The
    docket is already chronological, so it is simply not re-sorted.

    Text is attached where the calendars had it and left absent where they did
    not. An amendment nobody can read is still an amendment that was moved,
    and dropping it would hide a step rather than a document.

    And left absent where the calendar printed it under ANOTHER bill's
    heading. extract_amendments records the bill named in "Amendment to HB
    1347" above each number, and where that is not this bill the text is
    that bill's: HB 1180's docket of 2022 moves 2022-0996h, which House
    Calendar 10A prints, and the database files, as HB 1347's. It is left off
    -- with its proposer and its calendar -- and the row stays, because the
    docket says the number was moved here.

    `claimed` is the term's {number: {bills whose docket moves it}}, from
    amendment_claims. Given, the heading must name a bill that moves the
    number too, since a calendar also misprints headings: it put 2022-1160h,
    HB 1604's, under "Amendment to HB 1160-FN" -- its own number -- and
    2026-0976h under "HB 16678-FN", which is no bill. Neither is another
    bill's amendment, and neither is left off.
    """
    own = amended_bill((narr or {}).get("bill"))
    out, seen = [], {}
    for e in (narr or {}).get("events", []):
        if e.get("type") != "amendment" or e.get("cancelled"):
            continue
        num = amendment_num(e)
        if not num:
            continue
        # THE ROW THAT DECIDED IT, WHERE THE FIRST ONLY ANNOUNCED IT. The
        # Senate enters a floor amendment twice: "Sen. Birdsell Floor
        # Amendment # 2026-0720s; 02/19/2026" when it is offered, then "...#
        # 2026-0720s, AA, VV" when it carries (HB 266 of 2026, 10:23 and
        # 10:26). In the order the clerk entered them the first has no
        # outcome, and keeping only it dropped "adopted" from three
        # amendments the Senate adopted (HB 266, HB 751 and SB 557 of 2026).
        # The first row keeps its place; a later one fills in the outcome,
        # with its own day, since the day is printed beside it: HB 718 of
        # 2025's 2025-2080s was offered on 15 May and adopted on 5 June.
        if num in seen:
            a = seen[num]
            said = _amendment_said(e)
            if a["adopted"] is None and said is not None:
                a["adopted"] = said
                a["vote_kind"] = a["vote_kind"] or e.get("vote_kind") or ""
                a["mover"] = a["mover"] or e.get("mover") or ""
                a["date"], a["body"] = e.get("date"), e.get("body")
            continue
        kind = (e.get("amend_kind") or "").strip() or "Amendment"
        doc = texts.get(num) or {}
        printed_for = amended_bill(doc.get("heading"))
        if own and printed_for and printed_for != own and (
                claimed is None or printed_for in claimed.get(num, ())):
            doc = {}
        seen[num] = {
            "num": num,
            "kind": kind,
            # Committee or floor is not a label this invents: it is the word
            # the docket line used, and where the line says only "Amendment"
            # that is what the reader is told.
            "where": ("committee" if "committee" in kind.lower()
                      else "floor" if "floor" in kind.lower()
                      else "enrolment" if "enrolled" in kind.lower() else ""),
            "date": e.get("date"), "body": e.get("body"),
            # Not the outcome of a vote the same docket line goes on to
            # undo: HB 375 of 2001's floor amendment 1081 lost 179-181, was
            # reconsidered, and was adopted 180-179, all on one line the
            # history tells question by question. The first carries
            # "decided_again", and the row that decided it again fills the
            # outcome in, as a row does for an amendment only announced.
            "adopted": None if e.get("decided_again") else _amendment_said(e),
            "vote_kind": e.get("vote_kind") or "",
            "mover": e.get("mover") or "",
            "proposed_by": doc.get("proposed_by") or "",
            "text": doc.get("text") or "",
            "source": doc.get("source") or "",
            "targets": amendment_targets(doc.get("text") or ""),
        }
        out.append(seen[num])

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


# Whether one amendment event says its amendment was adopted, rejected or
# neither: session_days.amendment_carried, which says why a vote on part of
# one says neither.
_amendment_said = amendment_carried
