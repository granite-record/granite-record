#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-24.1
"""
The Senate committees' own hearing reports, read out of the database dump
already on this disk.

    python3 senate_hearing_reports.py                  # parse all, write
    python3 senate_hearing_reports.py --show SB4       # one bill, as parsed
    python3 senate_hearing_reports.py --fallbacks      # the ones not split

WHAT A HEARING REPORT IS

After every public hearing a Senate committee's aide writes up who came and
what they said. The report is filed in the General Court's CandH_Reports table
beside the committee REPORTS (the recommendation and vote), under
CommitteeType "Hearing Report". fetch_reports_db.py reads the committee reports
and leaves these alone, deliberately: they are a different document.

The House files rows of the same type, and they are not this: they carry no
speakers and no testimony. Only ChamberCode 'S' is read.

Each report, in the order it is laid out:

    Senate Commerce Committee
    <the aide's name and phone>                  not published
    SB 4, relative to ...
    Hearing Date: January 9, 2025
    Time Opened: 1:34 p.m.   Time Closed: 1:48 p.m.
    Members of the Committee Present: Senators ...
    Members of the Committee Absent : None
    Bill Analysis: ...                            not carried: the page has it
    Sponsors: ...                                 not carried: the page has it
    Who supports the bill: Name (Organization), ...
    Who opposes the bill: ...
    Who is neutral on the bill: ...
    Summary of testimony presented in support:
    <a speaker's name on its own line>
      * a point the report attributes to them
      * another, sometimes with a question and its answer nested under it
    <the next speaker> ...
    Summary of testimony presented in opposition: ...
    Neutral Information Presented: ...
    <the aide's initials>
    Date Hearing Report completed: January 10, 2025

Written after reading several dozen of them, not from that outline, and the
outline is the tidy case. About two reports in five have one undivided
"Summary of testimony presented:" instead of three; the committee's questions
and the answers to them sit sometimes as bullets under a speaker and
sometimes as whole paragraphs between speakers; a name line may end in a
colon; one report in a few hundred is two documents run together, the second
an empty template.

WHAT IS PUBLISHED, AND HOW EXACTLY

The person decided on 24 September that these are shown as the Senate
published them: every speaker named, with the points the report attributes to
each, members of the public included. (The online testimony SIGN-IN system is
a different thing and stays counts-only.) So nothing here rewords a point.
The only changes are whitespace and HTML entities, and the aide's phone
number, which is dropped with the line it is on.

A speaker is a line that reads as a name -- a person's name, optionally a
title before it and an organisation after a comma -- and a point is anything
else. Where a section's structure cannot be read with that confidence -- text
before the first name, a bullet or a paragraph that reads as another
speaker's heading and that the report's own position lists do not name --
the report is NOT guessed at: its sections are carried
as the plain paragraphs and bullets they are, in order, with nobody's name
attached, and `fallback` says so. The page draws those as the text they are.

WHAT IT WRITES

senate_hearing_reports.json, {term: {bill: [report, ...]}}, which
build_site_v2 attaches to the bill's Senate public-hearing station by the
hearing date. Standard library only; no network.
"""

import argparse
import csv
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import proceedings as P

SOURCE = Path("db") / "CandH_Reports.psv"
COLUMNS = ["LegislationID", "DateTimeStamp", "CommitteeType",
           "PDFImage_bytes", "ChamberCode", "HTMLText", "BillNbr",
           "ReleaseDate"]
OUT = Path("senate_hearing_reports.json")

MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], 1)}


# ---------------------------------------------------------------- blocks ---
class _Blocks(HTMLParser):
    """The report as paragraphs and list trees, in document order.

    The HTML is Word's, run through a converter: every line is a <p> with a
    class, and the points are <ul>/<li>, nested where a question and its
    answer were indented. That nesting is kept, because flattening it would
    put a senator's question and the witness's answer on one level as though
    both were the witness's points.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []      # ("p", text) | ("ul", [item])
        self.buf = None
        self.lists = []    # open lists, outermost first
        self.items = []    # open <li>, innermost last
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script", "title", "head"):
            self.skip += 1
        elif tag in ("ul", "ol"):
            self._flush()
            new = []
            if self.items:
                self.items[-1]["subs"].append(new)
            self.lists.append(new)
        elif tag == "li":
            it = {"t": "", "subs": []}
            if self.lists:
                self.lists[-1].append(it)
            else:
                # A stray <li> with no list: read it as a one-item list.
                self.lists.append([it])
            self.items.append(it)
        elif tag == "br":
            self._text(" ")
        elif tag in ("p", "td", "div", "tr") and not self.items:
            self._flush()

    def handle_endtag(self, tag):
        if tag in ("style", "script", "title", "head"):
            self.skip = max(0, self.skip - 1)
        elif tag in ("ul", "ol"):
            if self.lists:
                done = self.lists.pop()
                if not self.lists:
                    self.out.append(("ul", done))
        elif tag == "li":
            if self.items:
                self.items.pop()
        elif tag in ("p", "td", "div", "tr") and not self.items:
            self._flush()

    def handle_data(self, d):
        self._text(d)

    def _text(self, d):
        if self.skip:
            return
        if self.items:
            self.items[-1]["t"] += d
        else:
            if self.buf is None:
                self.buf = []
            self.buf.append(d)

    def _flush(self):
        if self.buf is not None:
            t = norm("".join(self.buf))
            if t:
                self.out.append(("p", t))
        self.buf = None

    def result(self):
        self._flush()
        # A list left open by malformed markup is still content.
        if self.lists:
            self.out.append(("ul", self.lists[0]))
            self.lists = []
        return [(k, v if k == "p" else _items(v)) for k, v in self.out]


def norm(s):
    s = (s or "").replace(" ", " ").replace("​", "")
    return re.sub(r"\s+", " ", s).strip()


def _items(raw):
    """<li> trees as {"t": text, "sub": [...]}, empty items dropped."""
    out = []
    for it in raw:
        sub = [x for s in it.get("subs", []) for x in _items(s)]
        t = norm(it["t"])
        if t or sub:
            out.append({"t": t, "sub": sub})
    return out


def blocks(markup):
    b = _Blocks()
    b.feed(markup or "")
    b.close()
    return b.result()


# ------------------------------------------------------------ vocabulary ---
# "Date Hearing Report completed: January 10, 2025", and four times with the
# aide's initials run on to the front of it -- "VH Senate Hearing Report
# completed", "jab/Date ...", "jab Date ...", "V.H Date ..." -- which were
# being filed as the last speaker's point, with the date lost.
COMPLETED = re.compile(r"^(?:[A-Za-z.]{1,5}\s*/?\s*)?(?:Date\s+|Senate\s+)?"
                       r"Hearing Report completed\s*:?\s*(.*)$", re.I)
LABEL = re.compile(
    r"^(?P<label>Hearing Date|Time Opened|Members of the Committee Present|"
    r"Members of the Committee Absent|Bill Analysis|Amendment Analysis|"
    r"Sponsors|Who supports the (?:bill|amendment)|"
    r"Who opposes the (?:bill|amendment)|"
    r"Who is neutral on the (?:bill|amendment))\s*:?\s*(?P<rest>.*)$", re.I)
# Every heading the testimony is filed under, as the aides actually wrote
# them: "Summary of testimony presented in support", "Summary of the
# testimony presented", "Summary of testimony the presented", "Summary of
# testimony", "Neutral Information Presented", "Summary of neutral testimony
# presented". Where the heading has a colon the label is everything before
# it, so "Summary of testimony presented in support of HB 1491:" keeps its
# last three words rather than handing "of HB 1491:" to the section as text.
SECTION = re.compile(
    r"^(?P<label>(?:Summary of (?:the )?(?:neutral )?testimony|"
    r"Neutral Information Presented)"
    r"(?:[^:]{0,120}(?=:)|(?: the)?(?: presented)?"
    r"(?: in (?:support|opposition))?))\s*:?\s*(?P<rest>.*)$", re.I)
BILL_LINE = re.compile(r"^(SB|HB|CACR|HCR|SCR|HJR|SJR|HR|SR)\s*(\d+)\b", re.I)
AMEND_LINE = re.compile(r"^AMENDMENT\b", re.I)
TIMES = re.compile(r"Time Opened\s*:?\s*(?P<o>.*?)\s*(?:Time Closed\s*:?\s*"
                   r"(?P<c>.*))?$", re.I)
# The aide's initials, alone on the line above "Date Hearing Report completed".
INITIALS = re.compile(r"^(?:[A-Za-z]\.?){1,4}(?:/(?:[A-Za-z]\.?){1,4})?$")
# A phone or an address to write to. The aide's line is dropped whole; this
# is for the sentence some position lists end with, "Full sign in sheets are
# available upon request by contacting ... (name@gc.nh.gov)".
CONTACT = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+|\b\d{3}[-.–]\d{4}\b")

# A person's title, when a name line opens with one.
TITLE = (r"(?:Senators?|Sen\.|Representatives?\.?|Reps?\.|Hon\.|Honorable|"
         r"Dr\.|Mr\.|Ms\.|Mrs\.|Miss|Commissioner|Deputy Commissioner|"
         r"Assistant Commissioner|Director|Chief|Mayor|Sheriff|Attorney|"
         r"Judge|Chair|Chairman|Chairwoman|Councilor|Executive Councilor|"
         r"Councillor|Secretary of State|Treasurer|Lt\.|Colonel|Col\.|"
         r"Captain|Capt\.|Sergeant|Sgt\.|Major|General|Rev\.|Reverend|"
         r"Father|Professor|Prof\.|President|Speaker|Superintendent|"
         r"Commander|Officer|Trooper|Lieutenant|"
         # "Atty. Leah Cole Durst" (HB 1 and HB 2), "Maj. Gen. David
         # Mikolaities" (SB 196): headings these were missing, whose
         # witnesses' points were filed under the speaker before them.
         r"Atty\.|Maj\.|Gen\.|Brig\.)")
# One word of a name: capitalised, initials, or one of the particles
# surnames carry here -- "Sabourin dit Choiniere", "de Vries", "St. John".
# Initials may run without their last full stop: "D.J Withee" (HB 666).
NAME_WORD = (r"(?:(?:[A-Z]\.){1,3}(?:[A-Z](?![\w'’\-]))?|[A-Z][\w'’\-]*\.?|"
             r"de|dit|van|von|"
             r"der|den|la|le|du|da|del|di|St\.|Mc\w+|O'\w+|\"[A-Z][\w]*\"|"
             r"“[A-Z]\w*”)")
ONE_NAME = rf"(?:{TITLE}\s+)?{NAME_WORD}(?:\s+{NAME_WORD}){{0,5}}"
# "Wendi Aultman & Brian Clark", "Judith Jones and Trina Ingelfinger", and a
# House member's seat run on without a comma: "Michael Vose Rock 5".
NAMES = re.compile(rf"^{ONE_NAME}(?:\s*(?:,\s*)?(?:and|&)\s+{ONE_NAME})*"
                   rf"(?:\s+\d{{1,3}})?$")
LEAD_TITLE = re.compile(rf"^(?:{TITLE}\s+)+")
# Where a name line's name ends and the description of who they are begins.
# A comma, a bracket, a colon or a dash; or "of the ...", "on behalf of
# ...", "for the Prime Sponsor"; or a full stop after the surname --
# "Representative Carol McGuire. Merrimack 27". The title is taken off first
# so that "Sen. Lang" is not cut at its own full stop.
NAME_END = re.compile(r"\s*[,(:;–—]\s*|\s+--?\s+|"
                      r"(?<=[a-z]{2})\.\s+|"
                      r"\s+(?:of|on behalf of|for|from)\s+", re.I)
# A verb a sentence about somebody uses and a name line does not. The name
# test already rejects a line whose first clause has lower-case words in it;
# this catches the rest, where the verb comes after a comma: "Senator
# Watters, however, asked ...". Lower case only: "Will" is Representative
# Will Darby's name, and a heading reading "- Introduced the bill" after a
# name and a dash is still a heading.
VERB = re.compile(
    r"\b(asked|asks|said|says|stated|states|noted|notes|explained|"
    r"responded|replied|added|agreed|confirmed|clarified|questioned|"
    r"wondered|inquired|mentioned|commented|testified|testifies|emphasized|"
    r"shared|discussed|raised|followed|countered|spoke|pointed|expressed|"
    r"believes|believed|feels|felt|thinks|thought|wants|wanted|"
    r"is|are|was|were|would|will|has|have|had|does|do|did|can|could|"
    r"should|may|might|must|supports|opposes|introduced|presented|"
    r"described|argued|urged|requested|suggested|answered|indicated|"
    r"acknowledged|highlighted|offered|provided|reiterated|detailed|"
    r"lived|lives|works|worked|told|began|begins)\b")


def _head(text):
    """(the name a line opens with, whether a title stood before it)."""
    t = norm(text)
    m = LEAD_TITLE.match(t)
    titled = bool(m)
    body = t[m.end():] if m else t
    head = NAME_END.split(body, maxsplit=1)[0].rstrip(". ").strip()
    return head, titled


def is_name_line(text, strict=False):
    """True where a line reads as a speaker's name, as the reports write one.

        Senator Daniel Innis
        Senator Gannon, Prime Sponsor
        James Key-Wallace, Executive Director, New Hampshire BFA
        Ann Marie Banfield (Parental Rights Advocate):
        Betty Gay: Former Representative
        Wendi Aultman & Brian Clark, Department of Health and Human Services
        Kevin Grady of the State Veterans Advisory Council:

    and not

        Senator Perkins Kwoka asked whether the motivation is ...
        Senator Watters detailed the changes:
        Ultimately, everyone operates under the same rules.

    `strict` is for a bullet, where a name is the exception rather than the
    rule: what follows the name must itself read as a title or a place --
    capitalised words and the joining words between them -- so that "Ms.
    Casagranda, a survivor of trafficking, ..." stays a point.
    """
    t = norm(text)
    # 300: two witnesses from one department, each with a title, run to
    # 250 characters on one line in SB 27 and SB 229.
    if not t or len(t) > 300 or "?" in t:
        return False
    if VERB.search(t):
        return False
    # A sentence ends with a full stop and is made of lower-case words; a
    # name line ending in one is short or is made of titles -- "Director
    # John Marasco and Kathy O'Neill, Division of Motor Vehicles."
    low = [w for w in re.findall(r"[A-Za-z][\w'’\-]*", t)
           if w[0].islower() and w not in JOINING]
    if t.endswith(".") and (strict or len(low) > 4):
        return False
    head, titled = _head(t)
    if not head or len(head.split()) > 12:
        return False
    # "HB 51", heading one bill's testimony in a report covering several.
    if BILL_LINE.match(head):
        return False
    # One bare capitalised word is how a sentence starts ("Ultimately, ...",
    # "Questions, answers, ..."), not how a person is named, unless a title
    # stood before it: "Senator Gannon".
    if len(head.split()) < 2 and not titled:
        return False
    if not NAMES.match(head):
        return False
    if strict:
        # "Supported SB 144" is a point that happens to be capitalised.
        if re.search(r"\d", head):
            return False
        at = t.find(head)
        tail = t[at + len(head):] if at >= 0 else t
        for w in re.findall(r"[A-Za-z][\w'’\-]*", tail):
            if w[0].islower() and w not in JOINING:
                return False
    return True


# The small words a title or an organisation's name is joined with.
JOINING = {"of", "the", "and", "for", "on", "in", "at", "to", "de", "dit",
           "a", "an", "behalf", "&"}


def name_part(text):
    """The name a speaker line opens with, title and all, for resolving a
    legislator: "Senator Daniel Innis", "Rep. David Fracht"."""
    t = norm(text)
    m = LEAD_TITLE.match(t)
    body = t[m.end():] if m else t
    head = re.split(r"\s*[,(:;–—]\s*|\s+--?\s+|"
                    r"\s+(?:of|on behalf of|for|from)\s+", body,
                    maxsplit=1)[0].rstrip(". ").strip()
    return ((m.group(0) if m else "") + head).strip()


def iso(printed):
    """'January 9, 2025' -> '2025-01-09', or '' where it is not a date."""
    m = re.search(r"([A-Za-z]+)\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})",
                  printed or "")
    if not m:
        return ""
    mon = MONTHS.get(m.group(1).lower())
    if not mon:
        return ""
    return f"{m.group(3)}-{mon:02d}-{int(m.group(2)):02d}"


def side_of(label):
    low = label.lower()
    if "support" in low:
        return "support"
    if "oppos" in low:
        return "oppose"
    if "neutral" in low:
        return "neutral"
    return "all"


# Where the instruction to write to the aide begins. Read off all 833 position
# lists in the table that carry an address: "Contact Pete Mulvey (...)",
# "Please contact ...", "The full sign in sheets are available upon request
# by contacting ..." (and "Full sign-sheets", once), "To see the full list of
# sign-ins, please email ...", "for a complete list of those who signed
# please email ...", "If you would like a complete list, please contact
# ...", "For more information, please contact ...", "Please reach out to
# ...". The last form stops at a comma or a full stop so that "signed in
# opposition to HB 666-FN" is never read as "to ... details".
INSTRUCTION = re.compile(
    r"\b(?:(?:please|plese)\s+)?(?:contact(?:ing)?|e-?mail|reach\s+out)\b|"
    r"\b(?:the\s+)?full\s+sign[- ]?(?:in[- ]?)?sheets?\b|"
    r"\b(?:to|for|if)\b[^.;,?!]{0,40}?\b(?:list|information|details?)\b",
    re.I)


def _clean_position(text):
    """A position list without the instruction telling readers whom to email.

    "272 people signed in support of the bill. Full sign in sheets are
    available upon request by contacting the Legislative Aide, Sophie Walsh
    (sophie.walsh@...)." The count is the Senate's record; the instruction to
    write to a named member of staff is the one piece of a position list this
    does not carry. It is cut from where it begins to the end of its
    sentence, and nothing before it is touched: the count and the instruction
    often share a sentence -- "84 signed in opposition to HB 666-FN, contact
    ...", "174 individuals were in opposition.Full sign in sheets ...", "63
    people signed in opposition, for a complete list of those who signed
    please email ..." -- and cutting by sentence took the count with it on
    eight reports, which then showed a support count and no opposition row.

    Where the instruction is the whole of it -- "Please contact the Senate
    Finance Committee Aide for a complete list of those opposed to SB297.
    (...)" -- cutting it would hide that anyone took that side at all, so the
    Senate's sentence is kept and only the bracketed address comes out.
    Nothing is reworded either way.
    """
    first = CONTACT.search(text)
    if not first:
        return text
    last = list(CONTACT.finditer(text))[-1]
    ins = INSTRUCTION.search(text, 0, first.start())
    start = ins.start() if ins else first.start()
    # The instruction runs to the end of the sentence the last address is in;
    # anything after that is the Senate's again.
    tail = text[last.end():]
    stop = re.search(r"[.!?](?=\s+[A-Z])", tail)
    after = tail[stop.end():].strip() if stop else ""
    kept = text[:start].rstrip(" ,;:–—")
    # "... to?SB 96. ?To see the full list": the stray mark before the
    # instruction is the converter's, not a question.
    kept = re.sub(r"(?<=[.!])\s*\?$", "", kept).strip()
    if kept:
        return _join(kept, after)
    alone = re.sub(r"\s*\(\s*(?:" + CONTACT.pattern + r")\s*\)", "", text)
    alone = re.sub(r"\s+([.,;])", r"\1", alone).strip()
    return "" if CONTACT.search(alone) else alone


# ----------------------------------------------------------------- parse ---
def documents(bl):
    """Split at "Date Hearing Report completed": a row can hold two reports
    run together, the second usually an empty template for the same bill."""
    docs, cur = [], []
    for b in bl:
        cur.append(b)
        if b[0] == "p" and COMPLETED.match(b[1]):
            docs.append(cur)
            cur = []
    if any(k == "ul" or v.strip() for k, v in cur):
        docs.append(cur)
    return docs


def _point(item):
    """A list item as the page stores it: its text, and what nests under it."""
    sub = [_point(s) for s in item.get("sub", [])]
    return {"t": item["t"], "sub": sub} if sub else item["t"]


def parse_document(bl):
    """One report's blocks -> the record, plus the reasons it fell back."""
    rec = {"committee": "", "subject": "", "bill_line": "", "heard": "",
           "opened": "",
           "closed": "", "present": "", "absent": "", "completed": "",
           "positions": [], "sections": []}
    doubts = []
    ps = [v for k, v in bl if k == "p"]
    # The committee is the first line; the aide and their phone the second,
    # and that line is not carried at all.
    if ps and re.search(r"\bCommittee\b|\bSenate\b", ps[0]):
        rec["committee"] = ps[0]

    i, n = 0, len(bl)
    pos = None          # the position list being continued, if any
    # ---- the head, up to the first testimony heading
    while i < n:
        k, v = bl[i]
        if k == "p" and SECTION.match(v):
            break
        i += 1
        if k != "p":
            continue
        if COMPLETED.match(v):
            rec["completed"] = iso(COMPLETED.match(v).group(1))
            continue
        # What was heard: the bill -- "SB 4, relative to ..." -- or an
        # amendment to it, "AMENDMENT # 2025-1481s, to HB 381-FN, ...".
        if not rec["subject"] and (BILL_LINE.match(v) or AMEND_LINE.match(v)):
            rec["subject"] = v
            rec["bill_line"] = v if BILL_LINE.match(v) else ""
            pos = None
            continue
        m = LABEL.match(v)
        if not m:
            # A position list that runs on to a second paragraph:
            # "... Lobbyists who oppose include ...".
            if pos is not None and not set(v) <= set("_- "):
                pos[1] = _join(pos[1], v)
            elif set(v) <= set("_- "):
                pos = None
            continue
        label = m.group("label").lower()
        rest = m.group("rest").strip()
        pos = None
        if label == "hearing date":
            rec["heard"] = rec["heard"] or iso(rest)
        elif label == "time opened":
            t = TIMES.match(v)
            rec["opened"] = (t.group("o") or "").strip() if t else ""
            rec["closed"] = (t.group("c") or "").strip() if t else ""
        elif label.endswith("present"):
            rec["present"] = rest
        elif label.endswith("absent"):
            rec["absent"] = rest
        elif label.startswith("who"):
            pos = [m.group("label").strip(), rest]
            rec["positions"].append(pos)
    # Cleaned once each list is whole: HB 1 and HB 2 break "Please contact
    # the Senate Finance Committee Legislative" / "Aide (...) for a complete
    # sign-in list." over two paragraphs, and cleaning each alone left the
    # first half standing as the list.
    raw_positions = rec["positions"]
    rec["positions"] = [[lab, _clean_position(txt)]
                        for lab, txt in raw_positions]
    # Silence is not success: a list the cleaning left empty is a row the
    # page no longer draws, and parse_all names every one.
    rec["emptied"] = [lab for (lab, raw), (_l, txt)
                      in zip(raw_positions, rec["positions"])
                      if raw.strip() and not txt]

    # ---- the testimony, heading by heading
    sec = None
    while i < n:
        k, v = bl[i]
        i += 1
        if k == "p" and COMPLETED.match(v):
            rec["completed"] = iso(COMPLETED.match(v).group(1))
            break
        if (k == "p" and INITIALS.match(v) and not NONE_NOTE.match(v)
                and _next_is_completed(bl, i)):
            continue
        if k == "p":
            m = SECTION.match(v)
            if m:
                rest = m.group("rest").strip()
                sec = {"label": m.group("label").strip(),
                       "side": side_of(m.group("label")), "blocks": []}
                if rest:
                    sec["blocks"].append(("p", rest))
                rec["sections"].append(sec)
                continue
        if sec is None:
            continue
        sec["blocks"].append((k, v))

    known = " ".join(t for _l, t in rec["positions"]).lower()
    for sec in rec["sections"]:
        speakers, note, why = split_speakers(sec["blocks"], known)
        sec["plain"] = _plain_blocks(sec["blocks"])
        if why:
            doubts.append(f"{sec['label']}: {why}")
        sec["speakers"] = speakers
        if note:
            sec["note"] = note
        del sec["blocks"]
    return rec, doubts


def _join(a, b):
    return f"{a} {b}".strip() if a else b


def _next_is_completed(bl, i):
    for k, v in bl[i:]:
        if k == "p":
            return bool(COMPLETED.match(v))
        return False
    return True


# "None", "No one", "There was no testimony in opposition."
NONE_NOTE = re.compile(r"^(?:(?:none|no one|nobody|n/?a)\b[^A-Za-z]*|"
                       r"(?:there (?:was|were) )?no (?:one|neutral|"
                       r"testimony|further)\b[^.]{0,60}\.?)$", re.I)


def split_speakers(sec_blocks, known):
    """A section's blocks -> ([speaker, ...], note, why-not).

    `why-not` is empty where every line was placed with confidence. Where it
    is not, the caller keeps the section as plain text instead.
    """
    speakers, note = [], ""
    cur = None
    # True from a speaker's name line until their first point. A heading
    # often runs to a second line -- "Senator Bill Gannon" then "Senate
    # District 23", "Meredith Hatfield" then "The Nature Conservancy" -- and
    # 464 of those second lines were read as speakers of their own, each
    # taking the points of the person named above it.
    heading = False
    # The last point was a paragraph, so a list after it is indented under
    # it: a senator's question and the answers to it, or "Senator Watters
    # detailed the changes:" and the changes.
    under = False
    for k, v in sec_blocks:
        if k == "p":
            if not speakers and NONE_NOTE.match(v):
                note = v
                continue
            if heading and is_heading_line(v):
                cur["also"] = cur.get("also", []) + [v.rstrip(":").strip()]
                continue
            if is_name_line(v):
                cur = {"who": v.rstrip(":").strip(), "points": []}
                speakers.append(cur)
                heading, under = True, False
                continue
            if cur is None:
                return [], note, f"text before the first name: {v[:60]!r}"
            # A heading is_name_line turned down -- "Robert Johnson II New
            # Hampshire Farm Bureau", "Pasha Roberts 603 Equality", "David" --
            # filed here would give that witness's whole testimony, nested
            # under it, to the speaker above: 13 witnesses in 11 reports,
            # three of them under a legislator's chip. The report's own
            # position lists settle it where they name the person, as they
            # do for a witness typed as a bullet below; otherwise the report
            # is not guessed at.
            if not heading and reads_as_heading(v):
                if _listed(v, known):
                    cur = {"who": v.rstrip(":").strip(), "points": []}
                    speakers.append(cur)
                    heading, under = True, False
                    continue
                return [], note, (f"a line that reads as another speaker's "
                                  f"heading, under {cur['who'][:40]!r}: "
                                  f"{v[:60]!r}")
            cur["points"].append(v)
            heading, under = False, True
            continue
        # a list
        if cur is None:
            return [], note, "a list before the first name"
        if (under and cur["points"] and isinstance(cur["points"][-1], str)
                and not any(_bullet_name(it) for it in v)):
            cur["points"][-1] = {"t": cur["points"][-1],
                                 "sub": [_point(it) for it in v]}
            heading, under = False, False
            continue
        heading, under = False, False
        for j, it in enumerate(k == "ul" and v or []):
            # A bullet that is only a name, and a name the report's own
            # position lists carry, is the next speaker typed at the wrong
            # indent -- "Ken Barnes, Contoocook" under Liz Tentarelli's
            # points in SB 11. Their points follow it. Attributing them to
            # the speaker above would put words in the wrong mouth.
            if _bullet_name(it):
                bare = _head(it["t"])[0]
                if bare and bare.lower() in known:
                    cur = {"who": it["t"].rstrip(":").strip(), "points": []}
                    speakers.append(cur)
                    continue
                return [], note, (f"a bullet that reads as a name but is on "
                                  f"no position list: {it['t'][:60]!r}")
            cur["points"].append(_point(it))
    # A run of name lines with nothing under any of them -- SB 290 ends with
    # eight people and their organisations and no points -- cannot be told
    # from one heading on several lines, and folding it into one would name
    # a crowd as a single speaker.
    for sp in speakers:
        if not sp["points"] and sp.get("also"):
            return [], note, (f"names with nothing under them: "
                              f"{sp['who'][:40]!r} and {len(sp['also'])} "
                              "more lines")
    return speakers, note, ""


def _bullet_name(it):
    """A bullet that is nothing but a name and who the person is."""
    return (not it["sub"] and len(it["t"].split()) <= 10
            and is_name_line(it["t"], strict=True))


def is_heading_line(text):
    """The second line of a speaker's heading: who they are, not what they
    said. "Senate District 23", "City of Manchester, N.H.", "Prime Sponsor,
    Strafford County District 18", "Staff Attorney - New Hampshire
    Department of Education". Asked only of the line straight after a name.
    """
    t = norm(text)
    if not t or "?" in t or len(t.split()) > 25 or VERB.search(t):
        return False
    if NONE_NOTE.match(t) or SECTION.match(t):
        return False
    low = [w for w in re.findall(r"[A-Za-z][\w'’\-]*", t)
           if w[0].islower() and w not in JOINING]
    return len(low) <= 4


# Verbs a short point uses and a heading does not, in any case: "Supported
# SB 144", "Mr. Tierney opposed SB 260", "THIS BILL WAS RECESSED UNTIL
# FEBRUARY 10TH". Kept apart from VERB, which is lower case only so that
# "Will" can stay a name; none of these is anybody's name.
HEAD_VERB = re.compile(
    r"\b(?:opposed|opposes|supported|supports|spoke|speaking|appeared|"
    r"deferred|concurred|agrees|agreed|cosponsored|urges|urged|updates|"
    r"updated|deleted|completed|recessed|represents|representing|testified|"
    r"introduced|brought|outlined|suggested|offered|signed|thanked|was|were|"
    r"is|are)\b", re.I)
# How a sentence or a sub-heading opens and a person's heading does not:
# "This bill:", "Amendment #1641s:", "Two examples of recent instances:".
NOT_A_NAME = {
    "This", "That", "These", "Those", "The", "A", "An", "It", "Its", "He",
    "She", "They", "We", "I", "His", "Her", "Their", "Our", "Amendment",
    "Section", "Page", "Line", "Lines", "RSA", "Additionally", "Also",
    "However", "Finally", "Overall", "In", "On", "At", "For", "With", "If",
    "When", "Under", "After", "Before", "As", "Since", "Because", "No", "Yes",
    "All", "Some", "Many", "Most", "Both", "Each", "Every", "Other",
    "Another", "Current", "One", "Two", "Three", "Four", "Five", "Six",
    "Seven", "Eight", "Nine", "Ten", "Question", "Questions", "Testimony",
    "Summary"}


def reads_as_heading(text):
    """True where a paragraph that is_name_line turned down still reads as a
    speaker's heading rather than as something a speaker said:

        Robert Johnson II New Hampshire Farm Bureau
        Shawn Foster Senior Pastor at Crossing Light Church, Windham, NH
        Cori Tebbetts, Plainfield (her statement was read by her friend)
        Phil, LBG Courage Coalition
        David

    Short, no question, no verb outside its brackets, at most one lower-case
    word that is not a joining word, and not opening the way a sentence or a
    sub-heading does. It is deliberately wide: split_speakers asks it only of
    a paragraph that would otherwise be filed as the speaker above's point,
    and a line it wrongly calls a heading costs the report its split, never
    a name.
    """
    t = norm(text)
    if not t or "?" in t or not t[0].isupper() or t.endswith(","):
        return False
    if (BILL_LINE.match(t) or SECTION.match(t) or NONE_NOTE.match(t)
            or COMPLETED.match(t)):
        return False
    outside = norm(re.sub(r"\([^)]*\)?", " ", t))
    if not outside or VERB.search(outside) or HEAD_VERB.search(outside):
        return False
    words = re.findall(r"[A-Za-z][\w'’\-]*", outside)
    if not words or len(outside.split()) > 16 or words[0] in NOT_A_NAME:
        return False
    low = [w for w in words if w[0].islower() and w not in JOINING]
    if len(low) > 1:
        return False
    # A sentence ends with a full stop; a heading that does is short and
    # has no lower-case word in it.
    return not (outside.endswith(".") and (low or len(words) > 8))


def _listed(text, known):
    """Whether the name a heading opens with starts an entry of the report's
    own position lists -- "..., Shawn Foster, ...", "..., David, ...". An
    organisation in brackets after somebody's name does not count: only what
    follows the start of the list, a comma, a semicolon or "and"."""
    head = _head(text)[0].replace("’", "'")
    words = head.split()
    if not words:
        return False
    k = known.replace("’", "'")
    start = rf"(?:^|[,;:]\s*|\band\s+|&\s*)(?:{TITLE}\s+)?"
    if len(words) == 1:
        # One word only as a whole entry: "David" is on SB 558's list as
        # "David", and is not "David Dokken".
        return bool(re.search(start + re.escape(words[0]) +
                              r"\s*(?:[,;(.]|$|\s+and\b)", k, re.I))
    return any(re.search(start + re.escape(" ".join(words[:n])) +
                         r"(?![\w'\-])", k, re.I)
               for n in range(len(words), 1, -1))


def _plain_blocks(sec_blocks):
    """A section as it is laid out: a paragraph is a string, a list is
    {"li": [points]}, in the report's order."""
    out = []
    for k, v in sec_blocks:
        if k == "p":
            out.append(v)
        elif v:
            out.append({"li": [_point(it) for it in v]})
    return out


def _weight(rec):
    return (sum(len(s["plain"]) for s in rec["sections"])
            + sum(1 for _l, t in rec["positions"] if t))


def parse_report(markup):
    """A row's HTML -> [(record, doubts), ...], one per document in it.

    A row can hold two documents run together. Sometimes the second is an
    empty template of the first (SB 34: the same bill, "Time Opened 3:19,
    Time Closed 3:19", every list blank), and it is dropped. Sometimes it is
    the committee's hearing on an AMENDMENT to the bill, the same afternoon
    (HB 381 at 1:26 and then its amendment at 1:51), which is a hearing of
    its own and is kept.
    """
    docs = documents(blocks(markup))
    parsed = [parse_document(d) for d in docs]
    kept = [p for p in parsed if _weight(p[0])]
    return kept or parsed[:1]


def finish(rec, doubts, bill, row_stamp):
    """The record as the site stores it: sections either split into
    speakers or, where that could not be done with confidence, plain."""
    fallback = bool(doubts)
    out_secs = []
    for s in rec["sections"]:
        o = {"label": s["label"], "side": s["side"]}
        if s.get("note"):
            o["note"] = s["note"]
        if fallback:
            # "None." after a heading's colon is the section's note, not its
            # text; carried once, as the note.
            plain = s["plain"]
            if s.get("note") and plain and plain[0] == s["note"]:
                plain = plain[1:]
            o["text"] = plain
        else:
            o["speakers"] = s["speakers"]
        out_secs.append(o)
    r = {
        "bill": bill,
        "committee": rec["committee"],
        "subject": rec["subject"],
        "heard": rec["heard"],
        "opened": rec["opened"], "closed": rec["closed"],
        "present": rec["present"], "absent": rec["absent"],
        "positions": rec["positions"],
        "sections": out_secs,
        "completed": rec["completed"],
        "filed": row_stamp,
    }
    if fallback:
        r["fallback"] = doubts
    return r


def read_rows(path=SOURCE):
    """Every Senate hearing report row in the dump."""
    csv.field_size_limit(1 << 30)
    with open(path, encoding="utf-8", newline="") as fh:
        for row in csv.reader(fh, delimiter="|", quoting=csv.QUOTE_NONE):
            if len(row) != len(COLUMNS):
                continue
            r = dict(zip(COLUMNS, row))
            if (r["CommitteeType"].strip() == "Hearing Report"
                    and r["ChamberCode"].strip() == "S"):
                yield r


def stamp_iso(s):
    """'01/10/2025 10:05:21' -> '2025-01-10'."""
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", s or "")
    return f"{m.group(3)}-{m.group(1)}-{m.group(2)}" if m else ""


def parse_all(path=SOURCE):
    """Every Senate hearing report -> ({term: {bill: [rec]}}, census)."""
    out, census = {}, {"rows": 0, "parsed": 0, "fallback": 0,
                       "two_documents": 0, "no_date": [], "unread": [],
                       "speakers": 0, "points": 0, "with_testimony": 0,
                       "bill_differs": [], "emptied": []}
    for r in read_rows(path):
        census["rows"] += 1
        bill = re.sub(r"\s+", "", r["BillNbr"]).upper()
        docs = parse_report(r["HTMLText"])
        if not docs:
            census["unread"].append(bill)
            continue
        if len(docs) > 1:
            census["two_documents"] += 1
        census["parsed"] += 1
        for rec, doubts in docs:
            # Which bill the text is about, against the row's own column.
            m = BILL_LINE.match(rec["bill_line"] or "")
            said = f"{m.group(1).upper()}{int(m.group(2))}" if m else ""
            if said and said != bill:
                census["bill_differs"].append((bill, said))
            heard = rec["heard"]
            if rec.get("emptied"):
                census["emptied"].append(
                    f"{bill} {heard}: " + "; ".join(rec["emptied"]))
            if not heard:
                census["no_date"].append(bill)
                continue
            fin = finish(rec, doubts, bill, stamp_iso(r["DateTimeStamp"]))
            term = P.term_of(heard)
            out.setdefault(term, {}).setdefault(bill, []).append(fin)
    # ONE REPORT PER HEARING, and a hearing is its date, what was heard and
    # when it opened -- not the date alone. Seven bills were heard twice on
    # one day, the bill and then an amendment to it, and keying on the date
    # threw the bill's own hearing away. Where the table does hold the same
    # hearing twice, the later filing is the one the committee let stand.
    dup = 0
    for byb in out.values():
        for bill, recs in byb.items():
            keep = {}
            for rec in sorted(recs, key=lambda x: x["filed"]):
                key = (rec["heard"], norm(rec["subject"]).lower(),
                       rec["opened"])
                if key in keep:
                    dup += 1
                keep[key] = rec
            byb[bill] = sorted(keep.values(),
                               key=lambda x: (x["heard"], _clock(x["opened"])))
    census["duplicates"] = dup
    for byb in out.values():
        for recs in byb.values():
            for fin in recs:
                if fin.get("fallback"):
                    census["fallback"] += 1
                spk = sum(len(s.get("speakers", [])) for s in fin["sections"])
                census["speakers"] += spk
                census["points"] += sum(count_points(sp["points"])
                                        for s in fin["sections"]
                                        for sp in s.get("speakers", []))
                if spk or any(s.get("text") for s in fin["sections"]):
                    census["with_testimony"] += 1
    return out, census


def _clock(t):
    """'1:51 p.m.' -> minutes after midnight, for ordering one day's
    hearings; 0 where it does not read."""
    m = re.match(r"(\d{1,2}):(\d{2})\s*([ap])", (t or "").lower())
    if not m:
        return 0
    h = int(m.group(1)) % 12 + (12 if m.group(3) == "p" else 0)
    return h * 60 + int(m.group(2))


def count_points(points):
    n = 0
    for p in points:
        n += 1
        if isinstance(p, dict):
            n += count_points(p.get("sub", []))
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--source", default=str(SOURCE))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--show", help="print one bill's reports as parsed")
    ap.add_argument("--fallbacks", action="store_true",
                    help="list the reports kept as plain text, and why")
    a = ap.parse_args()

    src = Path(a.source)
    if not src.exists():
        sys.exit(f"{src} is not on this disk. It is the database dump "
                 "fetch_archive_db.py writes; this script only reads it.")
    out, c = parse_all(src)
    if a.show:
        want = a.show.replace(" ", "").upper()
        for term, byb in sorted(out.items()):
            for rec in byb.get(want, []):
                print(json.dumps(rec, indent=1, ensure_ascii=False))
        return 0

    n_recs = sum(len(v) for byb in out.values() for v in byb.values())
    print(f"{c['rows']:,} Senate hearing reports in {src}")
    print(f"  {c['parsed']:,} read, giving {n_recs:,} hearing reports after "
          f"{c['duplicates']:,} filed twice for one hearing were folded to "
          "the later filing")
    print(f"  {c['with_testimony']:,} carry testimony; "
          f"{c['speakers']:,} speakers and {c['points']:,} points attributed")
    print(f"  {c['fallback']:,} kept as plain text, section by section, "
          "because a speaker could not be placed with confidence")
    if c["two_documents"]:
        print(f"  {c['two_documents']:,} rows held two reports run together "
              "and both are kept")
    if c["bill_differs"]:
        print(f"  {len(c['bill_differs']):,} name a different bill in their "
              "text than in the row: "
              + ", ".join(f"{a_} says {b_}" for a_, b_ in c["bill_differs"][:8]))
    if c["no_date"]:
        print(f"  {len(c['no_date']):,} have no hearing date that reads as "
              "one and are not carried: " + ", ".join(c["no_date"][:12]))
    if c["unread"]:
        print(f"  {len(c['unread']):,} had no text at all")
    if c["emptied"]:
        print(f"  {len(c['emptied']):,} position lists were nothing but an "
              "address to write to, and are not drawn: "
              + ", ".join(c["emptied"]))
    if a.fallbacks:
        for term, byb in sorted(out.items()):
            for bill, recs in sorted(byb.items()):
                for rec in recs:
                    for why in rec.get("fallback", []):
                        print(f"    {term} {bill} {rec['heard']}: {why}")

    # SILENCE IS NOT SUCCESS. A dump that changed shape reads as zero reports
    # and would otherwise write an empty file the site then shows as "no
    # hearing reports anywhere".
    if not c["rows"]:
        sys.exit(f"NOT WRITING {a.out}: no Senate hearing report rows in "
                 f"{src}. The table held 1,294 on 8 September 2026.")
    if c["parsed"] < c["rows"] * 0.9:
        sys.exit(f"NOT WRITING {a.out}: only {c['parsed']:,} of "
                 f"{c['rows']:,} reports read. That is a format change.")
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False,
                                      separators=(",", ":")),
                           encoding="utf-8")
    print(f"wrote {a.out}: {n_recs:,} reports across "
          f"{sum(len(b) for b in out.values()):,} bills")
    return 0


if __name__ == "__main__":
    sys.exit(main())
