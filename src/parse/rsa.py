#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-11.2
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

AND THE STATUTES' OWN DEFINITIONS (24 October 2026). Table.defined() reads
every defined term in the table and where its own words say it applies --
this chapter, this subdivision, this section or paragraph, named sections --
for the Laws pages, which mark a term where it is used (build_rsa). Nothing
of it is written to rsa_citations.json; the pages ask the table.
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

# `sub` is the first heading inside the chapter, which a page prints; `heads`
# is every one, outermost first ("ARTICLE 6 ...", "Part 1 ..."), which the
# reader of defined terms needs to tell where a subdivision ends.
Section = collections.namedtuple(
    "Section", "addr chapter title_no title chapter_name heading sub html text note url repealed heads")

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
        self._defined = None
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
                repealed=bool(REPEALED_HEAD.search(heading)) and len(text) < 400,
                heads=tuple(subs[1:]))
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

    def defined(self):
        """The table's defined terms (Defined), read once."""
        if self._defined is None:
            self._defined = Defined(self)
        return self._defined


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


# ------------------------------------------------------------- defined terms

# WHAT A DEFINED TERM MEANS WHERE IT IS USED (the person, 24 October 2026:
# "Could you make it so that definitions in the rsa pages show up as tooltips
# in sections that cite them like 'dwelling unit' being defined in 153:1 and
# later referenced so that you know which definition it's referring to?").
#
# A definition applies where its own words say, and only there: "When
# appearing in this chapter:" (RSA 153:1), "In this subdivision:" (153:27),
# "For the purposes of this section,", "In this paragraph", "As used in RSA
# 162-C:1 to 162-C:5". The words are read from the definition's own
# sentence, or from the lead-in its numbering sits under -- "In this
# chapter:" above "III. "Dwelling unit" means ..." -- and from nothing else.
# Where they cannot be read for certain there is no mark: a "Definitions"
# section that names no scope at all (RSA 5-C:1), a lead-in that names part
# of a section ("For purposes of subparagraph (b)"), "this compact", "this
# act". A definition is never applied outside its own chapter, even where its
# words reach further ("In this chapter and RSA 328-F", "In this title"); but
# what it reaches still counts when two definitions could apply, and where
# two definitions of one word could apply to a passage, neither is marked.
#
# The words of every scope sentence were read on 24 October 2026's table
# before this was written, and Defined.report() says what it finds. That day:
# 11,484 terms in 2,264 sections; 9,673 with a scope read and 1,811 left
# unmarked (1,147 of them in sections that name no scope); 42,558 marks in
# 12,172 sections, and 701 uses withheld where two definitions could apply
# (361 two scopes in one chapter, 251 dated versions of one paragraph, 89 a
# chapter whose words reach another's).
#
# WHAT IS A GUESS. The scope is the statute's; whether a word in a sentence
# is the defined word is not always, and four rules below were made by
# reading samples of the marks, not from any statute: a capitalized word
# inside a name is not the word (marks()), a defined thing after "shall" is a
# verb (A_THING), a word that opens a phrase defined elsewhere is that phrase
# (NEXT_WORD), and a single word is matched in its case only where the
# chapter writes it as a name (_cases). What they do not catch is a word the
# chapter itself uses in another sense: RSA 153:1, VII's "Officer" is marked
# in "the secretary or other officer of the insurance company" (153:13). The
# box says what is certain -- "Defined for this chapter in RSA 153:1, VII" --
# and the reader judges the rest.

def paragraphs(text):
    """A section's text as a page sets it, a paragraph a line: what every
    reader of a section's lines counts by."""
    return [p.strip() for p in (text or "").split("\n") if p.strip()]


# A paragraph's numbering, as many marks as open it: "I.", "V-a.", "(a)",
# "(1)", "(A)", "(i)", "(a)(1)", "(6A)"; a range of repealed ones, "I-VIII.
# [Repealed.]" (RSA 184:79), "XXIV, XXV.", "(1)-(3)"; and "1." and "A.",
# which compacts and a few old chapters use, which nest like the rest but are
# not cited by paragraph here.
_RANGE = r"(?:\s*(?:-|,|to|through)\s*\([0-9A-Za-z-]{1,6}\))*"
PMARK = re.compile(r"\s*(?:(?P<R>[IVXLC]+(?:-[a-z]{1,2})?(?:\s*(?:-|,|to|through)\s*[IVXLC]+(?:-[a-z]{1,2})?)*)"
                   r"\.(?=[\s(\"]|$)|(?P<D>\d{1,3})\.(?=[\s\"A-Z(])"
                   r"|(?P<P>[A-H])\.(?=\s)|\((?P<n>\d{1,3}[A-Z]?(?:-[a-z])?)\)" + _RANGE +
                   r"|\((?P<a>[a-z]{1,3}(?:-\d{1,2})?)\)" + _RANGE + r"|\((?P<A>[A-Z]{1,2})\)" + _RANGE + r")\s*")
ROMAN_NUM = re.compile(r"(?=[IVXLC])C{0,3}(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})")
LOW_ROMAN = re.compile(r"x{0,3}(?:ix|iv|v?i{0,3})")


def outline(paras):
    """For each paragraph, (the numbering it stands under, outermost first,
    as ((kind, mark), ...), where its words begin after its own marks). "I."
    then "(a)" then "(1)" nest as they open, and a mark of a kind already
    open closes everything under it. "(i)" is a letter where it follows
    "(h)", a Roman numeral otherwise.

    A paragraph that opens with no mark continues the numbering open above
    it -- "The term does not include ..." after RSA 382-A:9-102(a)(11)(B)(ii),
    a bracketed note between two versions of a paragraph -- and stands under
    nothing only before the first mark of its section. Its words begin at 0,
    which is how a reader tells it has no number of its own."""
    stack, out = [], []
    for p in paras:
        pos, marks = 0, []
        while True:
            m = PMARK.match(p, pos)
            if not m or m.end() == pos:
                break
            kind = next(k for k in ("R", "D", "P", "n", "a", "A") if m.group(k))
            mark = m.group(kind)
            if kind == "R" and not ROMAN_NUM.fullmatch(re.split(r"[-,\s]", mark)[0]):
                break
            if kind == "a" and LOW_ROMAN.fullmatch(mark):
                prev = dict(stack).get("a", "")
                if not (len(mark) == 1 and len(prev) == 1 and ord(mark) == ord(prev) + 1):
                    kind = "r"
            marks.append((kind, mark))
            pos = m.end()
        for kind, mark in marks:
            ks = [k for k, _ in stack]
            if kind in ks:
                del stack[ks.index(kind):]
            stack.append((kind, mark))
        out.append((tuple(stack), pos))
    return out


def para_label(path):
    """The paragraph as a citation names it -- "III", "I(a)", "(a)(2)" -- or
    "" where its numbering is not one this reader cites ("1.", "A.")."""
    if not path or any(k in ("D", "P") for k, _ in path):
        return ""
    if path[0][0] == "R":
        return path[0][1] + "".join(f"({m})" for _k, m in path[1:])
    if any(k == "R" for k, _ in path):
        return ""
    return "".join(f"({m})" for _k, m in path)


def para_cite(addr, label):
    """ "RSA 153:1, III", "RSA 382-A:9-102(a)(2)", "RSA 4-A:2"."""
    if not label:
        return f"RSA {addr}"
    return f"RSA {addr}{label}" if label.startswith("(") else f"RSA {addr}, {label}"


# A defining sentence: the term quoted -- straight or curly, and "law''" as one
# section closes it -- then the verb. Several terms may share one definition:
# '"Director" or "registrar" means', '"Attending physician", "APRN", or
# "physician associate" means'; and the scope may stand between term and verb:
# '"tax preparer," as used in this section, shall include'; and the Uniform
# Commercial Code's '"Account", except as used in "account for", ... and
# "unit of account", means', whose excepted phrases are not terms it defines.
QUOTED = re.compile(r'["“]([^"“”\n]{1,100}?)(?:["”]|\'\')')
QJOIN = re.compile(r"\s*(?:\([A-Z]{2,8}\)\s*)?,?\s*(?:(?:or|and|and/or)\s+)?")
DEFINES = re.compile(
    r'\s*,?\s*(?:(?P<inline>(?:as|when) used in [^,"“]{1,120}?|for (?:the )?purposes? of [^,"“]{1,120}?)'
    r',\s*|except as used in [^;:]{1,300}?,?\s*)?(?:shall\s+)?(?:also\s+)?(?:means?|includes?|'
    r'ha(?:s|ve) the (?:same )?meanings?|refers? to|(?:is|are|be) defined as)\b', re.I)
INLINE_OPEN = re.compile(r"(?:as|when) used in\s+|for (?:the )?purposes? of\s+", re.I)
# The words that open a scope, at the start of a sentence: "In", "As used in",
# "When appearing in", "For the purposes of", "The following words and
# phrases as used in" -- after "Definitions." or "Unless the context
# otherwise requires," where a section puts one first. "Under" and a bare
# "For" are not among them: "Under this chapter, the commissioner shall"
# opens no definition.
SCOPE_OPEN = re.compile(
    r"(?:(?:Definitions?|Terms Defined|Definition of Terms)\.\s*)?"
    r"(?:(?:Except as otherwise (?:provided|specified)|Unless (?:the|a)\b)[^,:\"]{0,80},\s*|In addition,\s*)?"
    r"(?:As used in|When used in|When appearing in|Wherever used in|For (?:the )?purposes? of|In|Within|"
    r"Throughout|The following (?:words|terms)(?: and (?:phrases|terms))?[^:\"]{0,60}?(?:used|referred to) in|"
    r"The following (?:definitions|words|terms)(?: and (?:phrases|terms))?\s+(?:shall\s+)?"
    r"(?:apply|be applicable|are applicable)\s+(?:to|in|throughout)|"
    r"(?:The )?(?:words|terms)(?: and phrases)? used in)\s+", re.I)
SCOPE_UNIT = re.compile(r"this\s+(chapter|subdivision|section|paragraph|subparagraph|article|title)\b", re.I)
SCOPE_JOIN = re.compile(r"\s*,?\s*(?:(?:and|or|as well as)\s+)?(?:in\s+)?", re.I)
# What may stand between the scope and the term in one sentence: "In this
# section, the term "debt" shall include". Anything else -- "For purposes of
# this section, all references in RSA 49-B to "city council" shall mean" --
# is not a definition of the term's use here, and is not read as one.
FILLER = re.compile(r"\s*,?\s*(?:(?:unless|except as otherwise)\b[^,\"]*,\s*)?(?:(?:the|a|an)\s+)?"
                    r"(?:(?:terms?|words?|phrases?|expressions?)\s+)?", re.I)
# What may follow the scope in a lead-in: nothing, a qualifier, or words about
# meaning. "For purposes of this chapter, health coverage does not include:"
# leads no list of definitions; "except RSA 153:5" would narrow the scope in
# a way not read here.
LEAD_REST = re.compile(r"\s*(?:,\s*)?(?:$|:|(?:unless|except as|except where|and unless|only|the following|"
                       r"these|shall|have|has|the (?:terms?|words?)|when|wherever)\b|.*\b(?:meanings?|definitions?|"
                       r"defined|construed)\b)", re.I | re.S)
NARROWS = re.compile(r"\bexcept\b(?!\s+(?:as|where|when|that|to the extent)\b)", re.I)
SENTENCE = re.compile(r"(?<=[.;:])\s+")
WORDCH = re.compile(r"[A-Za-z]")
NOTE = re.compile(r"\[[^\[\]]*\]")
# A capitalized word inside a longer name: one before it ("Federal
# Insecticide"), or one after it, "of" or "and" between ("Department of
# Education", "Insecticide, Fungicide").
NAME_PREV = re.compile(r"[A-Z][\w.'-]*,?$")
NAME_NEXT = re.compile(r",?\s+(?:(?:of|and|for|on)\s+(?:the\s+)?)?[A-Z]")


def term_of(raw):
    """A quoted term as one to match: spaces folded, a trailing comma inside
    the quotes ('"Board,"') dropped; '' for what is not a term."""
    t = re.sub(r"\s+", " ", raw).strip().rstrip(",.;:").strip()
    if not 2 <= len(t) <= 80 or len(WORDCH.findall(t)) < 2 or len(t.split()) > 8:
        return ""
    return t


def defining(para):
    """[(start, end, [terms], inline scope words)] for each defining sentence
    in a paragraph, in order."""
    out = []
    qs = list(QUOTED.finditer(para))
    k = 0
    while k < len(qs):
        if out and qs[k].start() < out[-1][1]:
            k += 1            # inside the sentence that defined the term before it
            continue
        group = [qs[k]]
        while k + 1 < len(qs) and QJOIN.fullmatch(para, group[-1].end(), qs[k + 1].start()):
            k += 1
            group.append(qs[k])
        m = DEFINES.match(para, group[-1].end())
        if m:
            terms = [t for t in (term_of(q.group(1)) for q in group) if t]
            if terms:
                inline = m.group("inline") or ""
                out.append((group[0].start(), m.end(), terms,
                            INLINE_OPEN.sub("", inline, count=1).strip() if inline else ""))
        k += 1
    return out


# A THING, NOT AN ACT. A term whose definition opens with an article --
# '"State" means any state of the United States', '"Account" means a right to
# payment' -- names a thing; met straight after "shall", "may" or "does not"
# it is the verb of the same spelling ("the notice shall state the time",
# RSA 402-C:11; "shall account to and pay a debtor", 382-A:9-615; "A
# recreation camp shall permit a child", 170-E:63), and is not marked. A term
# defined as an act -- '"Register" means to file', '"Accompany" means when a
# person is within sight' -- is marked there, as the statute uses it.
A_THING = re.compile(r"\s*,?\s*(?:a|an|any|the|each|every|all)\b", re.I)
# A WORD THAT OPENS A TERM OF ITS OWN. A defined word followed by one with
# which it makes a phrase some chapter defines -- "dwelling unit" (RSA
# 153:1), "warehouse receipt", "appraiser panel", "parole board" -- is that
# phrase, not the word: "single-family house or dwelling unit" in RSA 48-A:1
# is not 48-A's "dwelling", nor "interest rates" 293-A's "interest". Not
# marked; the word's next use may be. Measured on 24 October 2026's table: it
# takes 133 of 25,001 one-word marks, about half of them wrong.
NEXT_WORD = re.compile(r"\s+([A-Za-z][\w-]*)")
AS_VERB = re.compile(r"\b(?:(?:shall|may|must|will|would|can|could|should|might)(?:\s+not)?|cannot|"
                     r"(?:does|do|did)\s+not)\s+$", re.I)


def plural(word):
    """The regular plural of a term's last word, or '' where it already reads
    as one ("premises", "goods") or has none to make."""
    lo = word.lower()
    if not lo[-1:].isalpha() or (lo.endswith("s") and not lo.endswith(("ss", "us"))):
        return ""
    if lo.endswith(("ss", "us", "x", "z", "ch", "sh")):
        return word + "es"
    if len(lo) > 1 and lo.endswith("y") and lo[-2] not in "aeiou":
        return word[:-1] + "ies"
    return word + "s"


def forms(term):
    """The term and its plural, as a reader meets them: "dwelling unit" and
    "dwelling units", "facility" and "facilities". Irregular plurals are not
    made ("child", "children")."""
    words = term.split()
    p = plural(words[-1])
    return [term] + ([" ".join(words[:-1] + [p])] if p else [])


def quoted_spans(paras):
    """For each paragraph, the stretches inside quotation marks: a term is
    not marked inside a quotation, which is someone else's words (a form, a
    ballot question, "next of kin" as RSA 290:16 defines it). A quotation
    left open runs on into the next paragraph, as a quoted form does."""
    out, inq, start = [], False, 0
    for p in paras:
        spans, start, i = [], 0, 0
        while i < len(p):
            c = p[i]
            if (c == "“" or c == '"') and not inq:
                inq, start = True, i
            elif (c == "”" or c == '"') and inq:
                inq = False
                spans.append((start, i + 1))
            elif c == "'" and inq and p[i:i + 2] == "''":
                inq = False
                spans.append((start, i + 2))
                i += 1
            i += 1
        if inq:
            spans.append((start, len(p)))
        out.append(spans)
    return out


Definition = collections.namedtuple(
    "Definition", "terms addr para last shown cite anchor scope here there thing")
# terms   the terms as the statute writes them, ("Dwelling unit",)
# addr    the section that defines them, para the paragraph the definition
#         opens in, last the last paragraph of its own numbering (where the
#         term is not marked) and shown the last a reader is shown of it
# cite    "RSA 153:1, III"; anchor its id on the chapter's page, "s1_III"
# scope   the word that set it: "chapter", "subdivision", "section" ...
# here    {address: None, or (first, last) paragraph} where it is marked: in
#         its own chapter only
# there   the addresses outside its chapter its words also reach, which are
#         never marked but count when two definitions could apply
# thing   whether the definition opens with an article (A_THING)


class Defined:
    """The table's defined terms, where each applies, and where a page marks
    it. Built once by Table.defined()."""

    def __init__(self, table):
        self.table = table
        self.defs = []
        self.skipped = collections.Counter()     # why a term is never marked -> terms
        self.sections_read = 0                   # sections that define at least one term
        self.terms_found = 0
        self.phrases = set()                     # every term of two words or more, anywhere
        self._runs = {}
        for s in table.sections.values():
            if not s.repealed:
                self._read(s)
        self.at = collections.defaultdict(list)      # address -> definitions marked there
        self.near = collections.defaultdict(list)    # address -> definitions from other chapters that reach it
        for i, d in enumerate(self.defs):
            for a in d.here:
                self.at[a].append(i)
            for a in d.there:
                self.near[a].append(i)
        self.keys = [{f.lower() for t in d.terms for f in forms(t)} for d in self.defs]
        self.exact = self._cases()
        self._rx = {}

    # ---- reading the definitions

    def _read(self, s):
        paras = paragraphs(s.text)
        found = [(i, d) for i, p in enumerate(paras) for d in defining(p)]
        if not found:
            return
        self.sections_read += 1
        self.phrases.update(f.lower() for _i, d in found for t in d[2] if " " in t for f in forms(t))
        out = outline(paras)
        depth = [len(path) for path, _ in out]
        starts = sorted({i for i, _ in found})

        def own(i):
            """The last paragraph of the numbering a definition opens in: its
            own sub-paragraphs, or, unnumbered, the list its colon opens."""
            last = i
            if depth[i] or paras[i].rstrip().endswith(":"):
                while last + 1 < len(paras) and depth[last + 1] > depth[i]:
                    last += 1
            return last

        seen, anchor_of, taken = [], {}, set()
        sec = s.addr.split(":", 1)[1]
        for i, (start, end, terms, inline) in found:
            low = {t.lower() for t in terms}
            # '"Building" means ... "Building" also includes ...': a second
            # sentence of one definition, inside its own numbering, is not a
            # second definition.
            if any(low & t2 and i2 <= i <= l2 for t2, i2, l2 in seen):
                continue
            seen.append((low, i, own(i)))
            self.terms_found += len(terms)
            if inline:
                units, rest, _e = read_scope(inline)
                at, why = i, (None if units and not rest.strip(" ,")
                              else "the scope words name no part of the statutes")
            else:
                units, at, why = self._scope_words(paras, out, depth, i, start)
            if not why:
                here, there, scope, why = self._places(s, units, out, at)
            if not why and not here:
                why = "its scope is outside its own chapter"
            if why:
                self.skipped[why] += len(terms)
                continue
            # A paragraph with no number of its own is cited by its section.
            label = para_label(out[i][0]) if out[i][1] else ""
            if i not in anchor_of:
                slug = re.sub(r"[()]+", "_", label).strip("_") or "def"
                a, n = f"s{sec}_{slug}", 2
                while a in taken:
                    a, n = f"s{sec}_{slug}_{n}", n + 1
                taken.add(a)
                anchor_of[i] = a
            last = own(i)
            nxt = next((j for j in starts if j > i), len(paras))
            self.defs.append(Definition(tuple(terms), s.addr, i, last, min(last, nxt - 1),
                                        para_cite(s.addr, label), anchor_of[i], scope, here, there,
                                        bool(A_THING.match(paras[i], end))))

    def _scope_words(self, paras, out, depth, i, start):
        """(units, the paragraph they stand in, None) for a definition with
        no scope between its term and its verb; or (None, None, why)."""
        para = paras[i]
        prefix = para[out[i][1]:start]
        sents = SENTENCE.split(prefix)
        frag = sents[-1]
        m = SCOPE_OPEN.match(frag)
        if m:
            units, rest, end = read_scope(frag[m.end():])
            if units:
                # Between the scope and this term: filler, or an earlier
                # definition of the same sentence ('In this section, "a"
                # means x, and "b" means y').
                q = frag.find('"', m.end() + end)
                q = frag.find("“", m.end() + end) if q < 0 else q
                gap = frag[m.end() + end:q if q >= 0 else len(frag)]
                if FILLER.fullmatch(gap):
                    return units, i, None
            return None, None, "the scope words in its own sentence are not read here"
        if not frag.strip() and len(sents) > 1 and sents[-2].rstrip().endswith(":"):
            m = SCOPE_OPEN.match(sents[-2])
            if m:
                return self._lead_units(sents[-2][m.end():], i)
        if any(SCOPE_OPEN.match(x) for x in sents):
            return None, None, "the scope words in its own sentence are not read here"
        if not FILLER.fullmatch(frag):
            return None, None, "it stands inside a sentence about something else"
        # The lead-in its numbering sits under: the nearest paragraph above
        # that holds it -- every paragraph between is numbered deeper -- and
        # whose last sentence opens a scope. An editor's note between them,
        # "[Paragraph VI effective until January 1, 2027; ...]" (RSA
        # 541-A:1), is no part of the numbering and is passed over.
        low = depth[i]
        if not depth[i]:
            return None, None, "no scope is stated"
        for j in range(i - 1, -1, -1):
            if NOTE.fullmatch(paras[j]):
                continue
            if depth[j] < low:
                low = depth[j]
                last = SENTENCE.split(paras[j][out[j][1]:].strip())[-1]
                m = SCOPE_OPEN.match(last)
                if m and '"' not in last and "“" not in last:
                    return self._lead_units(last[m.end():], j)
                if not depth[j]:
                    break
            elif depth[j] == low and not depth[j]:
                break
        return None, None, "no scope is stated"

    @staticmethod
    def _lead_units(words, j):
        units, rest, _end = read_scope(words)
        if not units:
            return None, None, "its lead-in names no part of the statutes"
        if not LEAD_REST.match(rest) or NARROWS.search(rest):
            return None, None, "its lead-in qualifies the scope in words not read here"
        return units, j, None

    def _subdivision(self, s):
        """The run of sections under the same heading as s, or None where s
        stands under no heading or under more than one level of them."""
        if len(s.heads) != 1:
            return None
        ch = s.chapter
        if ch not in self._runs:
            runs, cur, key = {}, [], None
            for a in self.table.chapters[ch]["sections"]:
                h = self.table.sections[a].heads
                k = h[:1]
                if k != key:
                    cur = []
                    key = k
                cur.append(a)
                runs[a] = cur
            self._runs[ch] = runs
        run = self._runs[ch].get(s.addr)
        if not run or any(len(self.table.sections[a].heads) != 1 for a in run):
            return None
        return run

    def _places(self, s, units, out, at):
        """(here, there, scope, None) for what the units name, or (.., why)."""
        t, ch = self.table, s.chapter
        here, there, kinds = {}, set(), []
        prev = None
        for u in units:
            if isinstance(u, str):
                kinds.append(u)
                if u == "chapter":
                    here.update((a, None) for a in t.chapters[ch]["sections"])
                elif u == "section":
                    here[s.addr] = None
                elif u == "subdivision":
                    run = self._subdivision(s)
                    if not run:
                        return {}, set(), u, "its subdivision cannot be told from the table's headings"
                    here.update((a, None) for a in run)
                elif u in ("paragraph", "subparagraph"):
                    path = out[at][0]
                    kind = "R" if u == "paragraph" else "a"
                    ks = [k for k, _ in path]
                    if kind not in ks or (u == "subparagraph" and "R" not in ks and ks[0] != "a"):
                        return {}, set(), u, f"its {u} cannot be told from the numbering"
                    head = path[:ks.index(kind) + 1]
                    lo = hi = at
                    while lo > 0 and out[lo - 1][0][:len(head)] == head:
                        lo -= 1
                    while hi + 1 < len(out) and out[hi + 1][0][:len(head)] == head:
                        hi += 1
                    if here.get(s.addr, ()) is not None:
                        here[s.addr] = (lo, hi)
                elif u == "article":
                    m = re.match(r"(\d+[A-Z]?)-\d", s.addr.split(":", 1)[1])
                    if not m:
                        return {}, set(), u, "its article cannot be told from the numbering"
                    here.update((a, None) for a in t.chapters[ch]["sections"]
                                if a.split(":", 1)[1].startswith(m.group(1) + "-"))
                elif u == "title":
                    here.update((a, None) for a in t.chapters[ch]["sections"])
                    for c2, info in t.chapters.items():
                        if c2 != ch and info["title_no"] == t.chapters[ch]["title_no"]:
                            there.update(info["sections"])
                prev = None
                continue
            c = u
            kinds.append("named sections")
            if c.para:
                return {}, set(), "named sections", "its scope names part of a section"
            if c.how == "through":
                if not prev or prev.chapter != c.chapter or not prev.section or not c.section:
                    return {}, set(), "named sections", "its scope names a range not read here"
                lo, hi = sec_key(prev.section), sec_key(c.section)
                got = [a for a in t.chapters.get(c.chapter, {}).get("sections", [])
                       if lo <= sec_key(a.split(":", 1)[1]) <= hi]
            elif c.section:
                a = f"{c.chapter}:{c.section}"
                got = [a] if a in t.sections else []
            else:
                got = list(t.chapters.get(c.chapter, {}).get("sections", []))
            if c.chapter == ch:
                here.update((a, None) for a in got)
            else:
                there.update(got)
            prev = c
        scope = "named sections" if "named sections" in kinds else (kinds[0] if len(set(kinds)) == 1 else "+".join(kinds))
        return here, there, scope, None

    def _cases(self):
        """Whether each definition is matched as written rather than in any
        case: an abbreviation ("APRN"), and a single word the chapter writes
        capitalized on its own inside a sentence more often than not ("the
        Act", "the Code"), which is a name and not the common word ("an
        act"). A capital inside a longer name -- "the Federal Insecticide,
        Fungicide and Rodenticide Act" in RSA 430 -- is the name's, and is
        not counted."""
        exact = []
        want = collections.defaultdict(set)
        for i, d in enumerate(self.defs):
            for tm in d.terms:
                if len(tm.split()) == 1 and tm[:1].isupper() and not tm.isupper():
                    want[d.addr.split(":")[0]].add(tm.lower())
        tally = {}
        for ch, words in want.items():
            rx = re.compile(r"(?<![\w-])(" + "|".join(sorted(map(re.escape, words), key=len, reverse=True))
                            + r")(?![\w-])", re.I)
            c = collections.Counter()
            for a in self.table.chapters[ch]["sections"]:
                ps = paragraphs(self.table.sections[a].text)
                for p, (_path, opens) in zip(ps, outline(ps)):
                    for m in rx.finditer(p):
                        w = m.group(1)
                        before = p[opens:m.start()].rstrip()
                        if not w[:1].isupper():
                            c[(w.lower(), "low")] += 1
                        elif before and before[-1] not in '.:;!?"“(' and not NAME_PREV.search(before) \
                                and not NAME_NEXT.match(p, m.end()):
                            c[(w.lower(), "up")] += 1
            tally[ch] = c
        for d in self.defs:
            ch = d.addr.split(":")[0]
            ex = set()
            for tm in d.terms:
                if tm.isupper() and len(WORDCH.findall(tm)) >= 2:
                    ex.add(tm.lower())
                elif len(tm.split()) == 1 and tm[:1].isupper():
                    c = tally.get(ch, {})
                    if c.get((tm.lower(), "up"), 0) > c.get((tm.lower(), "low"), 0):
                        ex.add(tm.lower())
            exact.append(ex)
        return exact

    # ---- marking a section

    def _covers(self, i, addr, li):
        span = self.defs[i].here.get(addr)
        return span is None or span[0] <= li <= span[1]

    def _regex(self, keys):
        """One pattern for a set of (form, exact) pairs, longest first."""
        if keys not in self._rx:
            alts = []
            for form, exact in sorted(keys, key=lambda k: (-len(k[0]), k[0])):
                pat = r"\s+".join(map(re.escape, form.split()))
                alts.append(pat if exact else f"(?i:{pat})")
            self._rx[keys] = re.compile(r"(?<![\w-])(?:" + "|".join(alts) + r")(?![\w-])")
        return self._rx[keys]

    def marks(self, addr):
        """({paragraph: [(start, end, definition index)]}, {key withheld as
        ambiguous}) for a section: the first use of each term that applies
        to it, outside quotations, citations and the term's own definition;
        and the words two definitions could both explain, which are not
        marked.

        A NAME IS NOT THE WORD. A term the statute writes in small letters,
        met with a capital inside a sentence, is part of a name: "the Federal
        Trade Commission Act" in RSA 358-A:13, where 358-A:1 defines "trade";
        "the Hague Convention on the Civil Aspects of International Child
        Abduction" in 458-A:36. It is not marked, and the term's next use
        may be."""
        mine = self.at.get(addr, [])
        if not mine:
            return {}, set()
        near = self.near.get(addr, [])
        paras = paragraphs(self.table.sections[addr].text)
        quoted = quoted_spans(paras)
        opens = [o for _path, o in outline(paras)]
        out, used, withheld = {}, set(), set()
        for li, p in enumerate(paras):
            active = [i for i in mine if self._covers(i, addr, li)] + near
            if not active:
                continue
            who = collections.defaultdict(set)
            for i in active:
                for k in self.keys[i]:
                    who[k].add(i)
            pairs = set()
            for i in active:
                for t in self.defs[i].terms:
                    for f in forms(t):
                        pairs.add((f, f.lower() in self.exact[i] or t.lower() in self.exact[i]))
            skip = quoted[li] + [(c.start, c.end) for c in cites(p)]
            for m in self._regex(frozenset(pairs)).finditer(p):
                if any(a < m.end() and m.start() < b for a, b in skip):
                    continue
                key = re.sub(r"\s+", " ", m.group(0)).lower()
                ids = who.get(key, set())
                if len(ids) > 1:
                    withheld.add(key)
                    continue
                if not ids:
                    continue
                i = next(iter(ids))
                d = self.defs[i]
                if i in used or i not in mine or (d.addr == addr and d.para <= li <= d.last):
                    continue
                if d.thing and AS_VERB.search(p, max(0, m.start() - 30), m.start()):
                    continue
                if " " not in key:
                    nxt = NEXT_WORD.match(p, m.end())
                    if nxt and f"{key} {nxt.group(1).lower()}" in self.phrases:
                        continue
                if m.group(0)[:1].isupper():
                    written = [t for t in d.terms if key in {f.lower() for f in forms(t)}]
                    before = p[opens[li]:m.start()].rstrip()
                    if before and before[-1] not in ".:;!?" and \
                            not any(t.lower() in self.exact[i] or any(c.isupper() for c in t[1:])
                                    for t in written):
                        continue
                used.add(i)
                out.setdefault(li, []).append((m.start(), m.end(), i))
        return out, withheld

    def report(self, chapters=None):
        """The counts a person checks this by: definition sections read,
        terms found, terms never marked and why, and over `chapters` (every
        one by default) the sections marked, the marks, and the uses
        withheld because two definitions could apply."""
        marked = marks = withheld = 0
        for ch in chapters or self.table.chapters:
            for a in self.table.chapters[ch]["sections"]:
                got, held = self.marks(a)
                n = sum(len(v) for v in got.values())
                marked += bool(n)
                marks += n
                withheld += len(held)
        return {"sections_read": self.sections_read, "terms_found": self.terms_found,
                "definitions": len(self.defs), "terms_marked_in_scope": sum(len(d.terms) for d in self.defs),
                "skipped": dict(self.skipped.most_common()), "sections_marked": marked, "marks": marks,
                "withheld_ambiguous": withheld}


def read_scope(words):
    """The parts of the statutes scope words name, and where they stop:
    ([unit or Cite, ...], the words after them, their end). A unit is
    "chapter", "subdivision", "section", "paragraph", "subparagraph",
    "article" or "title"; a Cite is a section, a chapter or the end of a
    range ("RSA 153:1 to 153:14"). ([], words, 0) where they name none."""
    starts = {c.start: c for c in cites(words)}
    pos, units = 0, []
    while True:
        if units and pos in starts and starts[pos].how != "rsa":
            c = starts[pos]
            units.append(c)
            pos = c.end
            continue
        p = SCOPE_JOIN.match(words, pos).end() if units else pos
        m = SCOPE_UNIT.match(words, p)
        if m:
            units.append(m.group(1).lower())
            pos = m.end()
            continue
        if p in starts and starts[p].how == "rsa":
            units.append(starts[p])
            pos = starts[p].end
            continue
        return units, words[pos:], pos


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
