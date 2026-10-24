#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-24.1
"""
When a law takes effect, as its chaptered text says it.

The chaptered law's last lines, after "Effective Date:" (or "Effective:"),
give the day it takes effect -- "January 01, 2027" -- or a line a part: "I.
Section 3 effective August 19, 2027" and "II. Remainder effective October
18, 2026". chaptered_parts() reads them into Parts and returns None on any
line it cannot read, so the next source is asked.

Two builders read them, which is why the reader is here and not in either
(24 October 2026): build_rsa.py, for the Laws pages' changes passed and not
yet in effect (Bills.effect, which wrote it); and build_site_v2.py's
journey(), for the day a bill's page dates its Law stop by, which until then
came from the docket's governor line alone -- and that line can be another
bill's. HB 1184 of 2026's reads "I. Sec 2 eff 1/1/27 II. Sec 3 eff 1/1/27
III. Rem eff 1/1/28", HB 1102's, overridden the same day; its own chaptered
text says section 3 on August 19, 2027 and the rest on October 18, 2026.

Standard library and rsa.py only (part_of reads a statute address with it).
"""
# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import collections  # noqa: E402
import datetime  # noqa: E402
import re  # noqa: E402

import rsa  # noqa: E402

Part = collections.namedtuple("Part", "secs rest addr day how")
Part.__doc__ = """One part of a law and when it takes effect: `secs` the
act's own section numbers it covers, `rest` whether it is the remainder (or
the whole act), `addr` a statute address it names instead ("RSA 654:12, VI
as inserted by section 5"), `day` a datetime.date or None, `how` the words
for a day that is not stated or was counted ("as section 21 of the act
provides", "60 days after its passage, counted from ...")."""

MONTHS = ("January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December")
MONTH_NO = {m[:3].lower(): i + 1 for i, m in enumerate(MONTHS)}
DATE_WORDS = re.compile(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2})[,.]?\s+(\d{4})\b",
                        re.I)


def day_of(m):
    """A DATE_WORDS match as a datetime.date, or None."""
    try:
        return datetime.date(int(m.group(3)), MONTH_NO[m.group(1).lower()[:3]], int(m.group(2)))
    except (KeyError, ValueError):
        return None


def day_said(words):
    """The day `words` is and nothing else ("January 01, 2027.", "on
    September 1, 2027", "at 12:01 a.m. on July 1, 2035", "12:01 a.m.
    January 1, 2027", "July 1, 2027 at 12:01 a.m."), or None."""
    w = re.sub(r"(?:\bat\s+)?\b\d{1,2}:\d\d\s*[ap]\.?\s*m\.?(?:\s+on\b)?", " ", (words or ""), flags=re.I)
    w = re.sub(r"^\s*on\s+", "", w.strip(), flags=re.I)
    m = DATE_WORDS.fullmatch(w.strip().rstrip(" ."))
    return day_of(m) if m else None


def act_sections(words):
    """The act's own sections a part names -- "Section 3", "Sections 7-10",
    "Sec 1,2,5,6,11,12", "Sections 3.4.5", "sections 1 to 2 and 5 to 6",
    "Section 5 paragraph VI" (section 5) -- as a frozenset, or None where the
    words are not plainly a list of them."""
    m = re.match(r"\s*sec(?:tion)?s?\b\.?\s*(.*)$", words or "", re.I | re.S)
    if not m:
        return None
    s = re.sub(r"\s+of\s+(?:this|the)\s+act\b.*$", "", m.group(1), flags=re.I)
    s = re.sub(r",?\s*paragraphs?\s+[IVXL]+\b.*$", "", s, flags=re.I)
    s = re.sub(r"\s*(?:-|–|\bto\b|\bthrough\b)\s*", "-", s.strip(" .,;"))
    nums = set()
    for p in re.split(r"\s*(?:,|\.|&|\+|\band\b)\s*|\s+", s):
        if not p:
            continue
        r = re.fullmatch(r"(\d{1,3})(?:-(\d{1,3}))?", p)
        if not r:
            return None
        a, b = int(r.group(1)), int(r.group(2) or r.group(1))
        if b < a or b - a > 300:
            return None
        nums.update(range(a, b + 1))
    return frozenset(nums) or None


# A STATUTE AND SECTIONS OF THE ACT IN ONE PART: "I. RSA 597:2-b, I-a &
# Sections 16-17 effective July 1, 2024" (HB 318 of 2024). Read as the address
# alone, sections 16 and 17 were left to the remainder, on January 1, 2025.
# "as inserted by section 5" names where the paragraph comes from and is not
# a section the part covers ("RSA 654:12 VI as inserted by section 5", HB 464
# of 2025).
AND_SECTIONS = re.compile(r"\s*(?:&|\band\b)\s*(?=sec(?:tion)?s?\b)", re.I)


def part_of(words):
    """A part's words as (secs, rest, addr): the remainder or the whole act,
    a statute address it names (with any sections of the act named beside
    it), or the act's sections; None where the words are none of them ("Sec
    20, except RSA 275:82")."""
    w = re.sub(r"\s+", " ", (words or "").strip(" .,;:"))
    if re.fullmatch(r"(?:the )?(?:rem(?:ainder|\.)?|rest)(?: of (?:this|the) act)?|this act", w, re.I):
        return frozenset(), True, ""
    if re.match(r"RSA\b", w, re.I):
        m = AND_SECTIONS.search(w)
        more = act_sections(w[m.end():]) if m else frozenset()
        if more is None:
            return None
        head = w[:m.start()] if m else w
        cs = list(rsa.cites(head))
        if len(cs) == 1 and not re.search(r"\bexcept\b", head, re.I):
            return frozenset(more), False, rsa.addr_of(cs[0])
        return None
    s = act_sections(w)
    return (s, False, "") if s else None


# The chaptered law's own last lines: "Effective Date:" (or "Effective:"),
# then one day or a line a part. The sentence saying it was enacted without
# the Governor's signature carries the day of enactment, not of effect, and
# is set aside first.
TRAILER_AT = re.compile(r"\nEffective(?: Date)?:")
ARTICLE_44 = re.compile(r"Enacted in accordance with Article 44[^\n]*", re.I)
TRAILER_PART = re.compile(r"^(?:[IVXL]{1,5}\.\s*)?(?P<what>.+?)\s+(?:shall\s+take\s+effect|effectuve|effective|eff\.?)"
                          r"\s+(?P<when>.+?)\s*\.?$", re.I)
PROVIDED = re.compile(r"as\s+provided\s+(?:in|by)\s+sec(?:tion)?\.?\s*(\d{1,3})(?:\s*,?\s*paragraph\s+[IVXL]+)?"
                      r"(?:\s+of\s+this\s+act)?\.?", re.I)


def trailer_lines(body):
    """The chaptered law's last lines, after its last "Effective Date:" (or
    "Effective:"), each stripped and the Article 44 sentence set aside; None
    where it has none."""
    at = None
    for at in TRAILER_AT.finditer(body or ""):
        pass
    if not at:
        return None
    return [x.strip() for x in ARTICLE_44.sub("", body[at.end():]).split("\n") if x.strip()] or None


def part_words(line):
    """What one of trailer_lines' lines says its part covers, as it says it --
    "RSA 654:12 VI as inserted by section 5" -- or "" where it is not a part's
    line."""
    m = TRAILER_PART.match(line or "")
    if not m:
        return ""
    w = re.sub(r"\s+of\s+(?:this|the)\s+act\b", "", m.group("what"), flags=re.I)
    return re.sub(r"\s+", " ", w).strip(" .,;:")


def chaptered_parts(body):
    """The parts the chaptered law's last lines give, or None where it has
    none or a line this does not read -- then the next source is asked."""
    lines = trailer_lines(body)
    if not lines:
        return None
    if len(lines) == 1 and day_said(lines[0]):
        return (Part(frozenset(), True, "", day_said(lines[0]), ""),)
    parts = []
    for x in lines:
        m = TRAILER_PART.match(x)
        what = part_of(m.group("what")) if m else None
        if what is None:
            return None
        day, prov = day_said(m.group("when")), PROVIDED.fullmatch(m.group("when").strip())
        if day:
            parts.append(Part(*what, day, ""))
        elif prov:
            parts.append(Part(*what, None, f"as section {prov.group(1)} of the act provides"))
        else:
            return None
    return tuple(parts)
