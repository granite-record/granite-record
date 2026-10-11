#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-11.1
"""
The statutes (RSA): the General Court's table read once, and one reader of
statute citations for everything that needs them.

    python3 src/parse/rsa.py              # writes rsa_citations.json
    python3 src/parse/rsa.py --score      # the extractor against the source notes
    python3 src/parse/rsa.py --dry-run    # counts only, writes nothing

Asks nobody: it reads db/NH_RSA.psv (the General Court's SQL table, dumped to
disk by fetch_archive_db.py, a person's run), the bill texts in
bill_text.json and archive_text.json, and chapters.json. Standard library only.

WHY ONE MODULE (RSA_PAGE.md, 7 October 2026). The site reads statute
citations in two places (build_site_v2's RSA_CITE and bill_amends,
topic_model's RSA_RE) and each has its own blind spots: a list that drops
"RSA" ("RSA 9:17-a and 9:17-c"), a range, a four-digit article section cut
short ("RSA 564-B:10-1001" read as 564-B:10). The statute pages, the bill
pages, the search and related bills all need the same facts, so the facts
are decided here. This first version stands beside the site's readers and
changes no page; moving them onto it is its own change, checked
byte-for-byte against a whole-site manifest, as CLAUDE.md asks of a refactor.

WHAT IT WRITES, rsa_citations.json at the root:

    {"bills":   {"2025-2026": {"HB100": {"changes": ["21-L:2", "228"],
                                         "cites":   ["17-J:1", "21-L:2"]}}},
     "enacted": {"91-A:4": [["2024", "49:1", "2023-2024/SB 1"], ...]},
     "statute": {"91-A:4": ["91-A:3", "91-A:5"]},
     "asof":    {"table_rows": 29785, "laws_through": 2025}}

"bills" is keyed {term: {bill}}, as preflight requires of every per-bill file.
"changes" is what a bill's own instructions say it changes ("Amend RSA 91-A:4,
IV to read as follows:"), and "cites" everything it names. A section address
is the citation as the statute's own heading prints it, "293-A:10.01"; a bare
chapter, "228", where the bill names no section. "enacted" is the source
notes read against chapters.json: which session laws wrote each section, in
the order the note lists them, and the bill each law was where this site has
it -- a section's history of change, written by the Office of Legislative
Services rather than inferred by us. "statute" is what each section's own
text cites, resolved against the table: the "Cites" row of a statute page,
and inverted, its "Cited by".

TWO RECORDS, NOT ONE. "changes" and "enacted" disagree for enacted bills about
a third of the time (RSA_PAGE.md §3): one is the bill as filed, the other the
law as codified. They are kept apart and a page labels them apart. --score
measures one against the other; the source notes are the reference this
extractor did not generate.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import collections
import html
import json
import re

ROOT = _paths.ROOT
TABLE = ROOT / "db" / "NH_RSA.psv"
COLUMNS = ROOT / "db" / "_columns.json"
OUT = ROOT / "rsa_citations.json"

# ------------------------------------------------------------------ the table

Section = collections.namedtuple(
    "Section", "addr chapter title_no title chapter_name heading sub html text note url repealed")

TAG = re.compile(r"<[^>]+>")
CODESECT = re.compile(r"<codesect>(.*?)(?:</codesect>|$)", re.S | re.I)
H2 = re.compile(r"<h2>(.*?)</h2>", re.S | re.I)
# The address as the heading prints it: "Section 293-A:10.01 Authority." --
# SectionNo drops the dot (293-A-1001), so it is not the address.
HEAD_ID = re.compile(r"^Section\s+(\d{1,3}(?:-[A-Z]{1,2})?:[0-9A-Za-z.\-]+?)(?=[,\s]|$)")
# "Section 12-K:12 to 12-K:14 Repealed": one row for several repealed sections.
HEAD_RANGE = re.compile(r"^Section\s+(\d{1,3}(?:-[A-Z]{1,2})?):([0-9A-Za-z.\-]+?)\s+(?:to|through)\s+"
                        r"(?:\d{1,3}(?:-[A-Z]{1,2})?:)?([0-9A-Za-z.\-]+?)\s+Repealed", re.I)
REPEALED_HEAD = re.compile(r"\bRepealed\b", re.I)
HEAD_HYPHEN_RANGE = re.compile(r"^Section\s+(\d{1,3}(?:-[A-Z]{1,2})?):([0-9A-Za-z.]+)-"
                               r"(\d{1,3}(?:-[A-Z]{1,2})?):([0-9A-Za-z.\-]+)\s+")


def plain(s):
    """HTML to text: <br> as a line, tags gone, entities read, spaces folded."""
    s = re.sub(r"<br\s*/?>", "\n", s or "", flags=re.I)
    s = re.sub(r"</p>", "\n", s, flags=re.I)
    s = TAG.sub(" ", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t ]+", " ", s)
    return re.sub(r"\n\s*", "\n", s).strip()


def chap_key(ch):
    """Sort key for a chapter: 6 < 6-A < 6-B < 7 < 126-AA."""
    m = re.match(r"(\d+)(?:-([A-Za-z]+))?$", (ch or "").strip())
    return (int(m.group(1)), len(m.group(2) or ""), (m.group(2) or "").upper()) if m else (99999, 0, ch or "")


def sec_key(s):
    """Sort key for a section: 10.01 < 10.02; 7 < 7-a < 7-b < 8; 6-602."""
    m = re.match(r"(\d+)(?:\.(\d+))?(?:-(.*))?$", s or "")
    if not m:
        return (99999, 0, (2, 0, s or ""))
    suf = m.group(3) or ""
    return (int(m.group(1)), int(m.group(2) or 0),
            (0, int(suf), "") if suf.isdigit() else (1, 0, suf))


def addr_key(addr):
    ch, _, sec = addr.partition(":")
    return (chap_key(ch), sec_key(sec) if sec else (-1, 0, (0, 0, "")))


class Table:
    """The statute table: titles, chapters and sections, by address.

    sections   {"91-A:4": Section}, in statute order
    chapters   {"91-A": {"name", "title_no", "title", "sections": [addr], "repealed": bool}}
    ranges     [(chapter, lo, hi, addr)]: rows that stand for several repealed sections
    dropped    chapter-level "repealed" rows inside a chapter with live sections
               (one on 8 September 2026: the old 382-A's note inside the Uniform
               Commercial Code), left out so a page never calls a live chapter
               repealed (RSA_PAGE.md §1)
    """

    def __init__(self, rows):
        self.sections, self.chapters, self.ranges, self.dropped = {}, {}, [], []
        chapter_rows = []
        for r in rows:
            ch = (r.get("ChapterNo") or "").strip().upper()
            if not ch:
                continue          # the title-level row of the repealed Title IV
            info = self.chapters.setdefault(ch, {
                "name": re.sub(rf"^CHAPTER\s+{re.escape(ch)}\s*", "", r.get("Chapter") or "", flags=re.I).strip(),
                "title_no": r.get("TitleNo") or "", "title": r.get("Title") or "",
                "sections": [], "repealed": False})
            head = (r.get("Section") or "").strip()
            # "Section 339:71-339:76 Repealed by ...": a range in the hyphen
            # form, read as its first section with the range kept.
            head = HEAD_HYPHEN_RANGE.sub(r"Section \1:\2 to \3:\4 ", head)
            m = HEAD_ID.match(head)
            if not m:
                chapter_rows.append((ch, r))
                continue
            addr = m.group(1)
            if not addr.upper().startswith(ch + ":"):
                # 373:40 filed under chapter 246 (RSA_PAGE.md §1): kept under
                # its own chapter, where a citation of it will look.
                ch = addr.split(":")[0].upper()
                self.chapters.setdefault(ch, dict(info, sections=[], repealed=False))
            rng = HEAD_RANGE.match(head)
            if rng:
                self.ranges.append((ch, rng.group(2), rng.group(3), addr))
            subs = [plain(h) for h in H2.findall(r.get("rsa") or "")]
            body = CODESECT.search(r.get("EntireRSA") or r.get("rsa") or "")
            body_html = body.group(1) if body else ""
            text = plain(body_html)
            heading = re.sub(r"^Section\s+\S+\s*", "", head).strip()
            self.sections[addr] = Section(
                addr=addr, chapter=ch, title_no=r.get("TitleNo") or "", title=r.get("Title") or "",
                chapter_name=self.chapters[ch]["name"], heading=heading,
                sub=subs[1] if len(subs) > 1 else "",
                html=body_html, text=text,
                note=re.sub(r"^Source\.\s*", "", plain(r.get("SourceNote") or "")),
                url=(r.get("url") or "").replace("\\", "/"),
                repealed=bool(REPEALED_HEAD.search(heading)) and len(text) < 400)
        for ch, r in chapter_rows:
            live = any(not self.sections[a].repealed for a in self.sections if a.startswith(ch + ":"))
            if live:
                self.dropped.append(f"{ch}: {(r.get('Section') or '').strip()[:60]}")
            else:
                self.chapters[ch]["repealed"] = True
                self.chapters[ch]["note"] = plain(r.get("rsa") or "")[-300:]
        for addr in sorted(self.sections, key=addr_key):
            self.chapters[self.sections[addr].chapter]["sections"].append(addr)
        self.sections = {a: self.sections[a] for a in sorted(self.sections, key=addr_key)}

    def resolve(self, chapter, section=None):
        """(kind, address) for a citation: "section", "chapter", "range" (a
        section inside a row standing for several repealed ones), or (None,
        None) where the table holds nothing -- which a page prints as words."""
        ch = (chapter or "").upper()
        if section:
            a = f"{ch}:{section}"
            if a in self.sections:
                return "section", a
            k = sec_key(section)
            for rch, lo, hi, addr in self.ranges:
                if rch == ch and sec_key(lo) <= k <= sec_key(hi):
                    return "range", addr
            return None, None
        if ch in self.chapters:
            return "chapter", ch
        return None, None


def load(path=None, columns=None):
    """The table, or None where db/NH_RSA.psv is not on this disk."""
    path, columns = Path(path or TABLE), Path(columns or COLUMNS)
    if not path.is_file() or not columns.is_file():
        return None
    cols = json.loads(columns.read_text(encoding="utf-8"))["NH_RSA"]
    with open(path, encoding="utf-8", errors="replace") as fh:
        rows = [dict(zip(cols, line.rstrip("\n").split("|"))) for line in fh if line.strip()]
    return Table(rows)


# -------------------------------------------------------------- the citations

Cite = collections.namedtuple("Cite", "chapter section para start end how")

CH = r"\d{1,3}(?:-[A-Z]{1,2})?"
# 1, 1-a, 10-1001, 10-1005A, 10.01, 6-602.
SEC = r"\d{1,4}(?:\.\d{1,2})?(?:-(?:[a-z]{1,3}|\d{1,4}[A-Z]?))?"
END = r"(?![\d:]|\.\d|-[A-Za-z0-9])"
PARA = (r"(?:,\s*(?:[IVXLC]+(?:-[a-z])?)(?:\([a-z0-9]{1,3}\))*"
        r"(?:\s*(?:and|or|through)\s*[IVXLC]+(?:-[a-z])?)?)")
# U+2011, the non-breaking hyphen, prints in some texts where "-" is meant.
HEAD = re.compile(rf"\bRSA\s+({CH})(?![\d-])(?::({SEC}){END})?({PARA})?")
# A list continued without "RSA": ", 9:17-c", " and 17", " through 7:32-a".
NEXT = re.compile(
    rf"(\s*,\s*(?:and\s+|or\s+)?|\s*;\s*|\s+(?:and|or)\s+|\s+(?:through|to)\s+(?:RSA\s+)?)"
    rf"(?:({CH}):)?({SEC}){END}({PARA})?")


def cites(text):
    """Every statute address written in a string, as Cite(chapter, section,
    para, start, end, how): how is "rsa" for one that says RSA, "list" or
    "through" for one a list continues. Resolution is the table's: the same
    digits can be a section (383-A:6-602) or something else."""
    t = (text or "").replace("‑", "-")
    pos = 0
    while True:
        m = HEAD.search(t, pos)
        if not m:
            return
        ch, sec = m.group(1).upper(), m.group(2)
        yield Cite(ch, sec, (m.group(3) or "").strip(", "), m.start(), m.end(), "rsa")
        pos = m.end()
        if not sec:
            continue
        while True:
            n = NEXT.match(t, pos)
            if not n:
                break
            join = n.group(1)
            if "RSA" in join and not n.group(2):
                break
            if not n.group(2):
                # A bare number continues the chapter only where it reads as a
                # section: "and 17." / "29-a, 30," -- not "and 3 years",
                # "and 1990", "2017, 258:1".
                after = t[n.end():n.end() + 6]
                if re.match(r"\s+[a-z]", after) or len(n.group(3)) == 4:
                    break
            how = "through" if re.search(r"through|\bto\b", join) else "list"
            yield Cite((n.group(2) or ch).upper(), n.group(3), (n.group(4) or "").strip(", "),
                       n.start(), n.end(), how)
            if n.group(2):
                ch = n.group(2).upper()
            pos = n.end()


def addr_of(c):
    return f"{c.chapter}:{c.section}" if c.section else c.chapter


# ------------------------------------------------- what a bill says it changes

# The instruction-clause reader of build_site_v2.bill_amends, on this
# module's citations (RSA_PAGE.md §4, `changes`). A New Hampshire bill states
# what it changes in one clause ending in a colon, and everything after the
# colon is the new text; a repeal names its target before "is repealed" or
# lists it after "The following are repealed:".
AMEND_WORD = re.compile(r"\bAmend\b")
REPEALED = re.compile(r"\b(?:is|are)\s+repealed\b", re.I)
REPEAL_LIST = re.compile(r"\bfollowing\s+(?:is|are)\s+repealed\s*:", re.I)
CLAUSE_END = re.compile(r":(?!\d)")
NEXT_SECTION = re.compile(r"^\s*(?:\d{1,3}:)?\d{1,3}\s+[A-Z(]", re.M)
PART_WORD = re.compile(r"\S+$")
# A NEW SECTION, which the clause can only name by its neighbour: "Amend RSA
# 206 by inserting after section 33-g the following new section:" -- and the
# text that follows writes the new heading itself, "206:33-h Fees." That
# heading is the claim (RSA_PAGE.md §3: most of what the clause reader missed
# against the source notes was new sections). The session law's own numbering
# ("213:1 New Chapter;") is a different chapter's and is not read as one.
# The same holds for a chapter written whole: "the following new chapter:"
# and "RSA 410 is repealed and reenacted to read as follows:", where every
# heading of that chapter in the text that follows is a section the bill
# writes. The texts on disk keep no line breaks (a heading follows two spaces
# or a full stop), so a heading is a citation-shaped address at the start of
# a sentence, followed by a capitalised title and its full stop.
NEW_SECTIONS = re.compile(r"\bthe following new (?:sections?|subdivisions?|chapter)\b[^:]{0,80}:"
                          r"|\bis repealed and reenacted to read as follows:", re.I)
NEW_CHAPTER = re.compile(rf"\s*CHAPTER\s+({CH})\b")
FOLLOWING_PROVISIONS = re.compile(r"\bAmend the following RSA provisions\b")
NEW_HEAD = re.compile(rf"(?:^|\n|\s{{2}}|[.:]\s)\s*({CH}):({SEC})\s+[A-Z][^.\n]{{0,160}}\.")


def changes(text):
    """The statute addresses a bill's own instructions say it changes, in
    order of first appearance: sections where it names one, else chapters."""
    body = (text or "").replace("‑", "-")
    out = {}

    def take(s):
        for c in cites(s):
            out.setdefault(addr_of(c), None)

    def written(clause, after):
        """The headings a new-section or reenacting clause goes on to write,
        in the chapters it names, up to the next instruction."""
        named = {c.chapter for c in cites(clause)}
        nxt = AMEND_WORD.search(body, after)
        window = body[after:nxt.start() if nxt else len(body)][:60000]
        # A new chapter declares itself: "...the following new chapter:
        # CHAPTER 14-B LEGISLATIVE ETHICS COMMITTEE 14-B:1 Definitions."
        declared = NEW_CHAPTER.match(window)
        if declared:
            named.add(declared.group(1).upper())
        for h in NEW_HEAD.finditer(window):
            if h.group(1).upper() in named:
                out.setdefault(f"{h.group(1).upper()}:{h.group(2)}", None)

    for m in AMEND_WORD.finditer(body):
        stop = CLAUSE_END.search(body, m.end(), m.end() + 400)
        if not stop:
            continue
        clause = body[m.start():stop.start()]
        take(clause)
        if NEW_SECTIONS.search(body, m.start(), stop.end() + 1):
            written(clause, stop.end())
    # "RSA 410 is repealed and reenacted to read as follows:" opens with the
    # citation, not with "Amend".
    for m in re.finditer(r"is repealed and reenacted to read as follows:", body, re.I):
        lo = body.rfind(". ", max(0, m.start() - 300), m.start())
        clause = body[(lo + 2 if lo != -1 else max(0, m.start() - 300)):m.start()]
        take(clause)
        written(clause, m.end())
    # "Amend the following RSA provisions by replacing \"division\" with
    # \"department\": RSA 125-I:3, I; 125-J:1, I, II(c); 146-A:3-c, II(a)." --
    # the targets follow the colon, to the bill's next numbered section.
    for m in FOLLOWING_PROVISIONS.finditer(body):
        stop = CLAUSE_END.search(body, m.end(), m.end() + 400)
        if not stop:
            continue
        nxt = NEXT_SECTION.search(body, stop.end())
        sentence = re.search(r"\.\s+(?:\d{1,3}:)?\d{1,3}\s+[A-Z]", body[stop.end():stop.end() + 4000])
        end = stop.end() + (sentence.start() if sentence else 4000)
        if nxt:
            end = min(end, nxt.start())
        take(PART_WORD.sub("", body[stop.end():end]))
    for m in REPEAL_LIST.finditer(body):
        nxt = NEXT_SECTION.search(body, m.end())
        end = min(nxt.start() if nxt else len(body), m.end() + 2000)
        take(PART_WORD.sub("", body[m.end():end]))
    for m in REPEALED.finditer(body):
        lo = body.rfind(". ", max(0, m.start() - 300), m.start())
        take(body[(lo + 2 if lo != -1 else max(0, m.start() - 300)):m.start()])
    return list(out)


# ---------------------------------------------------------- the source notes

# "1967, 251:1. 2019, 107:1, eff. Jan. 1, 2020; 163:2, eff. Jan. 1, 2020 at
# 12:01 a.m. 2024, 49:1, 2, eff. Aug. 13, 2024." (RSA 91-A:4) -- a year, then
# that year's laws separated by semicolons, each "chapter:section" first and
# then whatever follows it (more sections, an effective date, a time of day,
# which must not be read as a law: "12:01"). A year opens a group only where
# a law follows it, so "Jan. 1, 2020 at" opens none.
YEAR_OPEN = re.compile(r"\b(1[6-9]\d\d|20\d\d)\s*,\s*(?=\d{1,4}:\d)")
LAW_AT = re.compile(r"\s*(\d{1,4}):(\d{1,4}(?:-[a-z])?)")
SIGNED = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{2,4})")


def laws_to_bills(chapters):
    """{(law year, law chapter): "term/BILL"} from chapters.json: the bill
    each session law was, by the year it was signed."""
    out = {}
    for term, bills in (chapters or {}).items():
        for bill, rec in bills.items():
            if rec.get("chapter") in (None, ""):
                continue
            m = SIGNED.search(rec.get("line") or "")
            if not m:
                continue
            y = int(m.group(3))
            y = y + (1900 if y > 50 else 2000) if y < 100 else y
            out[(y, int(rec["chapter"]))] = f"{term}/{bill}"
    return out


def history(note, law_bill):
    """[(year, "chapter:section", "term/BILL" or "")] for a source note, in
    the order it lists them: the session laws that wrote the section."""
    note = note or ""
    opens = list(YEAR_OPEN.finditer(note))
    out = []
    for i, g in enumerate(opens):
        y = int(g.group(1))
        group = note[g.end():opens[i + 1].start() if i + 1 < len(opens) else len(note)]
        for part in group.split(";"):
            p = LAW_AT.match(part)
            if p:
                out.append((y, f"{p.group(1)}:{p.group(2)}", law_bill.get((y, int(p.group(1))), "")))
    return out


# ------------------------------------------------------------------ the run

def bill_texts():
    """{(term, bill): text}: the current term's latest printing and the
    archive's one, the current file first."""
    out = {}
    for name in ("bill_text.json", "archive_text.json"):
        p = ROOT / name
        if not p.is_file():
            continue
        for term, bills in json.loads(p.read_text(encoding="utf-8")).items():
            for bill, rec in bills.items():
                out.setdefault((term, bill), (rec or {}).get("text") or "")
    return out


def build(table, texts, chapters):
    law_bill = laws_to_bills(chapters)
    bills = collections.defaultdict(dict)
    for (term, bill), text in sorted(texts.items()):
        ch = changes(text)
        ci = list(dict.fromkeys(addr_of(c) for c in cites(text)))
        if ch or ci:
            bills[term][bill] = {"changes": ch, "cites": ci}
    enacted, statute, latest = {}, {}, 0
    for addr, s in table.sections.items():
        # A repealed section's last change is in its own text, "Repealed by
        # 2024, 365:18", not in a source note.
        h = history(s.note + (" " + s.heading + " " + s.text if s.repealed else ""), law_bill)
        if h:
            enacted[addr] = [[str(y), law, b] for y, law, b in h]
            latest = max(latest, max(y for y, _l, _b in h))
        out = []
        for c in cites(s.text):
            kind, target = table.resolve(c.chapter, c.section)
            if kind and target != addr and target not in out:
                out.append(target)
        if out:
            statute[addr] = out
    return {"bills": {t: dict(sorted(b.items())) for t, b in sorted(bills.items())},
            "enacted": enacted, "statute": statute,
            "asof": {"table_rows": len(table.sections), "laws_through": latest,
                     "dropped_chapter_rows": sorted(table.dropped)}}


def score(table, data):
    """The clause reader against the source notes, for enacted bills: of what
    it claims at section level, how much a note confirms (precision), and of
    what the notes say, how much it finds (recall). Printed; preflight holds
    the figures from falling."""
    claims, notes = set(), set()
    enacted_bills = set()
    for addr, rows in data["enacted"].items():
        for _y, _law, b in rows:
            if b:
                notes.add((addr, b))
                enacted_bills.add(b)
    for term, bills in data["bills"].items():
        for bill, rec in bills.items():
            key = f"{term}/{bill}"
            if key not in enacted_bills:
                continue
            for a in rec["changes"]:
                if ":" in a and a in table.sections:
                    claims.add((a, key))
    both = claims & notes
    return {"claims": len(claims), "notes": len(notes), "confirmed": len(both),
            "precision": round(len(both) / max(1, len(claims)), 4),
            "recall": round(len(both) / max(1, len(notes)), 4)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    ap.add_argument("--score", action="store_true", help="print precision and recall against the source notes")
    ap.add_argument("--dry-run", action="store_true", help="count, write nothing")
    a = ap.parse_args()
    table = load()
    if table is None:
        # SILENCE IS NOT SUCCESS: a night without the table says so, and the
        # pages that read this file say they have nothing rather than nothing.
        print(f"rsa: {TABLE.relative_to(ROOT)} is not on this disk; rsa_citations.json not written")
        return 0
    texts = bill_texts()
    chp = ROOT / "chapters.json"
    chapters = json.loads(chp.read_text(encoding="utf-8")) if chp.is_file() else {}
    data = build(table, texts, chapters)
    n_bills = sum(len(b) for b in data["bills"].values())
    n_changes = sum(1 for b in data["bills"].values() for r in b.values() if r["changes"])
    print(f"rsa: {len(table.sections):,} sections in {len(table.chapters):,} chapters; "
          f"{len(table.dropped)} chapter-level repeal row(s) dropped from live chapters "
          f"({', '.join(table.dropped) or 'none'})")
    print(f"  {n_bills:,} bills cite a statute, {n_changes:,} say they change one; "
          f"{len(data['enacted']):,} sections have a source-note history, "
          f"{len(data['statute']):,} cite another; laws through {data['asof']['laws_through']}")
    assert n_changes, "no bill said it changes a statute: the bill texts or the reader are wrong"
    if a.score:
        s = score(table, data)
        print(f"  against the source notes, enacted bills: {s['confirmed']:,} of {s['claims']:,} "
              f"claims confirmed (precision {s['precision']:.1%}); {s['confirmed']:,} of "
              f"{s['notes']:,} noted pairs found (recall {s['recall']:.1%})")
    if a.dry_run:
        return 0
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
                   encoding="utf-8")
    print(f"  wrote {OUT.name}, {OUT.stat().st_size / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
