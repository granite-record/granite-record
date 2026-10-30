#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-29.1
"""
What each House committee said about the bills it held for interim study:
the INTERIM STUDY STATEMENTS of the House Calendar's autumn edition.

    python3 src/parse/interim_statements.py             # writes interim_statements.json
    python3 src/parse/interim_statements.py --dry-run   # counts, writes nothing

Reads calendars/<year>/HC*.txt on this disk and asks nobody anything.

WHY THIS EXISTS

A bill sent to interim study in the first year of a term comes back to its
committee in the second, and in the autumn the committee says whether the
subject should be filed again: RECOMMENDED FOR FUTURE LEGISLATION, NOT
RECOMMENDED FOR FUTURE LEGISLATION, or WITHOUT RECOMMENDATION, with a member's
reasoning and the vote. The calendar prints them all in one section, grouped
by committee -- 145 bills in House Calendar 40 of 2024 -- and it is the only
place the reasoning is printed. Anyone deciding whether to file the subject
again wants it beside the bill (the owner, 29 October 2026). The docket keeps
one line of it, "Interim Study Report: Not Recommended for Future
Legislation 09/02/2026 (Vote 18-0)", and no reasons.

On disk the section is in one calendar of every second year from 1998 to
2024: fourteen, and about 1,200 statements. 1998's and 2000's calendars are
browser printouts (2000 heads the section "interim study STATEMENTS").

WHY NOT fetch_committee_reports.py, which reads these same calendars for the
committee reports: it knows nothing of this section. Its split took a
statement only where the wording happened to look like an ordinary report,
and filed it as one -- 39 of the 1,200, HB 1530 of 2024's RECOMMENDED FOR
FUTURE LEGISLATION among them as a report of "INTERIM STUDY" -- and skipped
the rest. That split is the root cause, and its fix belongs with the run-on
of its Senate reports into veto messages (a fetch script: it is not run
here). Until then build_site_v2 shows the statement this file holds in place
of the mis-filed report from the same calendar.

This reads the calendar's text with that script's own clean-up, member line
and vote (clean_pdf_text, AUTHOR, VOTE_TAIL), so a statement reads exactly as
a report does on the same tab.

WHAT A STATEMENT HOLDS

    {"2023-2024": {"HB1530": [{"source": "House Calendar 40, 2024",
        "committee_heading": "FISH AND GAME AND MARINE RESOURCES",
        "title": "requiring fish and game officers to wear body cameras",
        "printed": "RECOMMENDED FOR FUTURE LEGISLATION", "rec": "rec",
        "author": "Rep. Cathryn Harvey",
        "committee": "Fish and Game and Marine Resources",
        "text": "This is a bill that ...", "vote_yeas": 10, "vote_nays": 0}]}}

KNOWN HOLD: a committee that split prints a majority's and a minority's
statement under one title -- HB 1164 of 2000, "MAJORITY: NOT RECOMMENDED
...", then each side's member and reasons. It is held back, not shown as
one statement; showing both, as the tab shows a split report, is a later
change (the manager, 29 October 2026).

`rec` is "rec", "not" or "without" from the words printed, or "" where the
calendar prints none: 2004's statements give the bill, the member and the
reasons, and say what they recommend only in the prose, which is never read
for it. The page then takes the docket's line and says it did.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import json
import re
from collections import Counter

import fetch_committee_reports as FCR
import proceedings as P

OUT = Path("interim_statements.json")

# The section's heading, alone on its line: "2024 INTERIM STUDY STATEMENTS",
# 1998's without the year, 2000's printout's "interim study STATEMENTS".
HEAD = re.compile(r"(?im)^[ \t\f]*(?:\d{4}[ \t]+)?interim[ \t]+study[ \t]+statements[ \t]*$")
# What the calendar goes on with after it: a heading, in any case -- 2000's
# printout heads it "COMMITTEE meetiNGS" -- or, in 2016 and 2018, no heading
# at all and straight into the meeting days, "THURSDAY, NOVEMBER 10".
END = re.compile(r"(?mi)^[ \t\f]*(?:COMMITTEE MEETINGS|OFFICIAL NOTICES|REVISED FISCAL NOTES?"
                 r"|(?:MON|TUES|WEDNES|THURS|FRI|SATUR|SUN)DAY,[ \t]+[A-Z]+[ \t]+\d{1,2})[ \t]*$")
# A bill's statement opens a line: "HB 1779-FN, supporting the cultural ...".
# And 2024 prints "HB.1507," once.
ENTRY = re.compile(r"(?m)^[ \t\f]*(?P<bill>(?:HB|SB|HJR|HCR|CACR|HR|SJR|SCR)[ \t.]?\d{1,4})"
                   r"(?P<suf>(?:-[A-Z]+)*)[ \t]*,")
# A sentence of reasons can open a line on a bill too: "HB 1348, Chapter 253,
# Laws of 2002." (2002). A statement's title starts in lower case, or, where
# 2014 capitalises it ("HB 1464, Exempting ..."), the statement before it has
# ended: its vote, its signature, a heading or a blank line stands above.
TITLE_LOWER = re.compile(r"\s*[a-z(]")
ENDED = re.compile(r"(?:\bVotes?[:\s]*\d{1,3}\s*-\s*\d{1,3}\.?|^[ \t\f]{12,}Re[po]s?\.?[ \t]+\S.*"
                   r"|^[ \t\f]*[A-Z][A-Z,&'’ -]{3,}[A-Z]|^)[ \t]*$")
# A committee's heading, alone on its line and in capitals: CHILDREN AND
# FAMILY LAW. Never a line of the recommendation, which wraps in capitals
# too ("FUTURE LEG-" / "ISLATION."), and never a page's running head, which
# carries digits.
CMTE = re.compile(r"(?m)^[ \t\f]*(?P<c>[A-Z][A-Z,&'’ -]{3,}[A-Z])[ \t]*$")
# Only the recommendation's own pieces: LEGISLATIVE ADMINISTRATION and
# STATE-FEDERAL RELATIONS AND VETERANS AFFAIRS are committees.
NOT_CMTE = re.compile(r"RECOMMEND|FUTURE|LEGISLATION|STATEMENTS|^(?:LEG|LEGIS)?-?(?:IS)?LATION\.?$"
                      r"|^LEG(?:IS)?-$")
# The recommendation as printed, wherever the line breaks it: "FUTURE LEG-"
# over "ISLATION.", and 2026's stray space before the stop.
# And as the clerks varied it: RECOMMENDED FOR FURTHER LEGISLATION (SB 366 of
# 2010), NOT RECOMMENDED FOR LEGISLATION (HB 1415 of 2006), NOT RECOMMENDED
# FOR FUTURE RECOMMENDATION (HB 579 of 2000), NO RECOMMENDATION (HB 1592 of
# 2014), and a footnote's number set inside the words where a page's note
# is keyed: "NOT RECOMMENDED FOR FUTURE 2 LEGISLATION" (HB 1191 of 2010).
_N = r"(?:\d{1,3}\s+)?"
# And a page's number between NOT and RECOMMENDED: "NOT" / "14" /
# "RECOMMENDED FOR FUTURE LEGISLATION" (HB 543 of 2012).
REC = re.compile(r"\b(?P<not>NOT\s+(?:\d{1,3}\s+)?)?RECOMMENDED\s+" + _N + r"FOR\s+" + _N
                 + r"(?:(?:FUTURE|FURTHER)\s+" + _N + r")?"
                 r"(?:LEG(?:-\s*)?ISLATION|RECOMMENDATION)\b"
                 r"|\b(?:WITHOUT|NO)\s+RECOMMENDATION\b")


def section(text):
    """The INTERIM STUDY STATEMENTS section of one calendar's text, or ""."""
    m = HEAD.search(text)
    if not m:
        return ""
    e = END.search(text, m.end())
    return text[m.end():e.start() if e else len(text)]


def starts(sec, m):
    """Whether the bill at `m` opens a statement (ENTRY, ENDED)."""
    if TITLE_LOWER.match(sec, m.end()):
        return True
    # And it prints its recommendation within its first lines, as all four
    # of 2014's do and "HB 1348, Chapter 253," does not.
    if not REC.search(re.split(r"\n[ \t\f]*\n", sec[m.end():m.end() + 600])[0]):
        return False
    above = sec[:m.start()].rstrip(" \t\f").split("\n")
    last = above[-2] if len(above) > 1 and not above[-1].strip() else above[-1]
    return not above[-1].strip() or bool(ENDED.search(last))


def chunks(sec):
    """[(committee heading, raw text of one bill's statement)] in order."""
    marks = [(m.start(), "bill", m) for m in ENTRY.finditer(sec) if starts(sec, m)]
    marks += [(m.start(), "cmte", m) for m in CMTE.finditer(sec)
              if not NOT_CMTE.search(m.group("c"))]
    marks.sort(key=lambda x: x[0])
    out, cmte, last = [], "", None
    for i, (at, kind, m) in enumerate(marks):
        if kind == "cmte":
            cmte, last = re.sub(r"\s+", " ", m.group("c")).strip(), None
            continue
        end = marks[i + 1][0] if i + 1 < len(marks) else len(sec)
        # A statement whose reasons open on its own bill -- "HB 332,
        # introduced in January, 2011, was retained ..." (2012) -- is that
        # statement going on: a bill has one statement in the section.
        bill = re.sub(r"[\s.]", "", m.group("bill")).upper()
        if bill == last and out:
            out[-1] = (out[-1][0], out[-1][1] + sec[at:end])
            continue
        out.append((cmte, sec[at:end]))
        last = bill
    return out


def printed_words(m):
    """The recommendation as the calendar prints it, one line: NOT RECOMMENDED
    FOR FUTURE LEGISLATION."""
    words = re.sub(r"\s+", " ", re.sub(r"-\s+", "", m.group(0))).strip().upper()
    return re.sub(r" \d{1,3}(?= )", "", words)         # a footnote's or a page's number


# 2006 to 2014 sign a statement below it instead: the reasons and the vote,
# then the member's name alone on a line set far to the right --
# "                       Rep. Caroline Gargasz". The committee is then the
# heading the statement stands under.
# "Rep Bette R. Lasky" with no stop, and 2010's "Reo. Suzanne H. Gottling";
# at the top of a page, after its form feed.
SIGNED = re.compile(r"(?m)^\f?[ \t]{12,}(?P<who>(?:Re[po]|Sen)\.?[ \t]+[A-Z][^\n]*?\S)[ \t]*$")


# 1998 to 2004 also print the member's line in forms the report reader does
# not take: "Rep David A. Welch for ...:", "Reps. Timothy N. Robertson and
# Everett A. Weare for ...:", "Rep. John E. Tholl, Jr. for ...:", and once
# "Rep. Harold P. Melcher Environment and Agriculture:" with no "for". Read
# to the colon, where the line names the committee the heading does.
LOOSE = re.compile(r"(?P<who>Reps?\.?[ \t]+[A-Z][^:]{2,140}?)[ \t]*:[ \t]")


class _Line:
    """A member's line read by LOOSE, shaped as FCR.AUTHOR's match is."""

    def __init__(self, m, who, committee):
        self._m, self._g = m, {"who": who, "committee": committee, "side": None}

    def group(self, k):
        return self._g[k]

    def start(self):
        return self._m.start()

    def end(self):
        return self._m.end()


def member_line(s, at, cmte, names):
    """The member's line after `at` in one of the older forms, or None."""
    m = LOOSE.search(s, at)
    if not m or not cmte:
        return None
    name = (names or {}).get(cmte) or titled(cmte)
    tail = re.search(r",?[ \t]+(?:for[ \t]+)?" + re.escape(name) + r"$", m.group("who"), re.I)
    if not tail:
        return None
    return _Line(m, m.group("who")[:tail.start()].strip(" ,"), name)


BARE_TALLY = re.compile(r"(?<=\.)\s+(?P<y>\d{1,3})\s*[-\u2013]\s*(?P<n>\d{1,3})\.?\s*$")


def statement(cmte, raw, source, names=None):
    """(bill, statement), or (why, None) where it cannot be read. `names`
    is {COMMITTEE HEADING: the committee's name as a member's line spells
    it}, for a signed statement."""
    # "Vote 16-" at a line's end and "1." on the next is 16-1 (seven of them).
    raw = re.sub(r"(\bVote[:\s]\s*\d{1,3}\s*-)[ \t]*\n[ \t\f]*(?=\d)", r"\1", raw)
    sig = list(SIGNED.finditer(raw))
    if sig:
        raw = raw[:sig[-1].start()]
    s = FCR.clean_pdf_text(raw)
    b = ENTRY.match(s)
    if not b:
        return "no bill at its start", None
    # A committee that split prints a majority's and a minority's statement
    # under one title (HB 1164 of 2000, "MAJORITY:"): not one statement, and
    # held back rather than shown as one.
    first = re.search(r"\bReps?\.?\s", s[b.end():])
    if re.search(r"\bMAJORITY\s*:", s[b.end():b.end() + (first.start() if first else len(s))]):
        return "a majority's and a minority's statement", None
    a = FCR.AUTHOR.search(s, b.end()) or member_line(s, b.end(), cmte, names)
    if a and len(list(FCR.AUTHOR.finditer(s, a.end()))):
        return "more than one member's statement", None
    bare = not a and not sig
    if bare and not REC.search(s, b.end()):
        return "no member's line, no signature and no recommendation", None
    if bare and s[REC.search(s, b.end()).end():].strip(" ."):
        return "words after the recommendation, and no member's line or signature", None
    if a and sig:
        return "a member's line and a signature both", None
    # Where the statement's own words begin: after the member's line, or,
    # signed, after the recommendation, or after the title's full stop.
    r = REC.search(s, b.end(), a.start() if a else len(s))
    if a:
        title_end, start = (r.start() if r else a.start()), a.end()
    elif r:
        title_end, start = r.start(), r.end()
    else:
        stop = re.search(r"\.\s", s[b.end():])
        if not stop:
            return "no end to the title", None
        title_end = start = b.end() + stop.end()
    title = s[b.end():title_end].strip(" .,")
    rec = ("" if not r else "not" if r.group("not") else
           "rec" if r.group(0).upper().startswith("RECOMMENDED") else "without")
    body = s[start:].strip().lstrip(".").strip()
    # A statement can be its recommendation alone: HB 1547 of 2010, WITHOUT
    # RECOMMENDATION and nothing under it. It is shown as that.
    who = a.group("who") if a else sig[-1].group("who") if sig else ""
    # The committee as the heading names it on the page: "Public Works and
    # Highways Committee" and "Resources , Recreation and Development
    # Committee" as printed would read "... Committee committee" there.
    committee = (re.sub(r"\s+,", ",", re.sub(r"\s+(?:Committee)?\s*$", "",
                                              re.sub(r"\s+", " ", a.group("committee")))).strip()
                 if a
                 else (names or {}).get(cmte) or titled(cmte))
    out = {"source": source, "committee_heading": cmte, "title": title,
           "printed": printed_words(r) if r else "", "rec": rec,
           "author": re.sub(r"\s+", " ", who).strip(),
           "committee": committee, **({"signed": True} if sig else {})}
    # The vote, as the report reader takes it: the last one with only page
    # furniture after it, cut out of the text, the sentence keeping its stop.
    # And as a few statements print it: "Vote13-0." with no space (2008,
    # 2010), "Votes 17-0." (2008), "Vote : 13-0." (2004), and the tally alone
    # as the last sentence,
    # "... legislation. 16-0." (2006, 2008). "Vote 161." (SB 387 of 2000) is
    # left as printed: which digit the dash fell from is a guess.
    body = re.sub(r"\bVotes?[ \t]*:?[ \t]*(?=\d{1,3}\s*[-\u2013]\s*\d)", "Vote ", body)
    v = None
    for cand in FCR.VOTE_TAIL.finditer(body):
        if len(body) - cand.end() <= FCR.VOTE_TAIL_SLACK:
            v = cand
    if not v:
        v = BARE_TALLY.search(body)
    if v:
        out["vote_yeas"], out["vote_nays"] = int(v.group("y")), int(v.group("n"))
        body = body[:v.start()].lstrip(" .;,").rstrip().rstrip(";,").rstrip()
    out["text"] = body
    return re.sub(r"[\s.]", "", b.group("bill")).upper(), out


SMALL = {"and", "of", "the", "for", "on", "in", "to"}


def titled(heading):
    """CHILDREN AND FAMILY LAW as Children and Family Law, for a heading no
    member's line in another year spells."""
    return " ".join(w.lower() if i and w.lower() in SMALL else w.capitalize()
                    for i, w in enumerate(heading.split()))


def read(root="."):
    """({term: {bill: [statement]}}, Counter of what was held and why, [per
    calendar (path, statements, held)])."""
    out, held, per = {}, Counter(), []
    found = []
    for f in sorted(Path(root).glob("calendars/*/HC*.txt")):
        sec = section(f.read_text(encoding="utf-8", errors="replace"))
        if sec:
            found.append((f, sec))
    # How a member's line spells each committee heading, from every year that
    # prints one, for the years that sign below instead.
    names = Counter()
    for f, sec in found:
        for cmte, raw in chunks(sec):
            a = FCR.AUTHOR.search(FCR.clean_pdf_text(raw))
            if a and cmte:
                names[(cmte, re.sub(r"\s+", " ", a.group("committee")).strip())] += 1
    spelled = {}
    for (h, n), _c in names.most_common():
        if n.upper() == h:
            spelled.setdefault(h, n)
    for f, sec in found:
        year = f.parent.name
        num = re.match(r"HC0*(\d+[A-Z]?)", f.stem).group(1)
        source = f"House Calendar {num}, {year}"
        term = P.term_of(year)
        n = h = 0
        for cmte, raw in chunks(sec):
            bill, st = statement(cmte, raw, source, spelled)
            if st is None:
                held[f"held: {bill}"] += 1
                h += 1
                continue
            out.setdefault(term, {}).setdefault(bill, []).append(st)
            n += 1
        per.append((f.as_posix(), n, h))
    return out, held, per


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    ap.add_argument("--dry-run", action="store_true", help="count, write nothing")
    ap.add_argument("--root", default=".", help="where calendars/ is")
    a = ap.parse_args()
    data, held, per = read(a.root)
    for path, n, h in per:
        print(f"  {path}: {n} statements" + (f", {h} held" if h else ""))
    total = sum(len(v) for t in data.values() for v in t.values())
    recs = Counter(s["rec"] or "none printed" for t in data.values()
                   for v in t.values() for s in v)
    print(f"interim study statements: {total:,} in {len(per)} calendars; "
          + ", ".join(f"{n:,} {k}" for k, n in sorted(recs.items()))
          + ("; " + ", ".join(f"{n} {k}" for k, n in sorted(held.items())) if held else ""))
    # SILENCE IS NOT SUCCESS: fourteen calendars on disk carry the section.
    # A run that finds a few read the wrong folder, not a quiet decade.
    if not per or total < 10 * len(per):
        sys.exit(f"only {total} statements in {len(per)} calendars: the section was "
                 "not read; interim_statements.json not written")
    if a.dry_run:
        return 0
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True),
                   encoding="utf-8")
    print(f"  wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
