#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-09.2
"""
The sponsors of a resolution, read from the House and Senate Journals that print it.

    python3 src/parse/resolution_sponsors.py            # writes resolution_sponsors.json
    python3 src/parse/resolution_sponsors.py --survey   # every resolution block, what it yields; writes nothing

No network. The standard library only.

WHY THIS EXISTS (9 November 2026)

The per-term coverage table showed 173 bills with no sponsor, every one a
resolution. 95 are housekeeping -- the rules, the return of votes, the joint
convention, the biennium's salary -- and the General Court names no sponsor for
them because the chamber moves them. The rest are memorial and honoring
resolutions, and the person's instruction was to look them up from disk first:
the journal of the day a resolution was adopted prints the resolution in full,
and may print who offered it.

WHAT THE JOURNALS PRINT, read off every House and Senate journal on disk
(1997 to 2026 and 2003 to 2026) and not assumed. A resolution opens with a
heading -- HOUSE RESOLUTION NO. 14, House Resolution No. 28, MEMORIAL
RESOLUTION NO. 6, or in 2007 and 2008 a bare MEMORIAL RESOLUTION and its
title -- and says who offered it in one of three places:

    Reps. Flanagan and Shurtleff offered the following:      (the line after the heading)
    Offered by: Representatives Gene Chandler, Stephen Shurtleff and Speaker Terie Norelli
    Offered by the House of Representatives.                 (the line after the last resolve)

The third is by far the commonest, 29 of the 31 memorial resolutions the
journals print since 1997 with a line at all, and it is not a sponsor: it says
the chamber offered the resolution, as it does for every memorial for a
member who died, and no member's name is printed. That is read and recorded as
nothing. A blank beats a guess, and "the House of Representatives" is not a
legislator the site can link. The same goes for "The Judiciary Committee
offered the following": a committee is not a person here.

WHAT IT WRITES

resolution_sponsors.json, {term: {bill: {"sponsors": [names as printed, in
order], "journal": "HJ 54 of 2015", "title": the title the journal prints,
"line": the sponsor line as printed}}}, only for a resolution whose journal
line names a person. build_data takes it for a bill that has no sponsor from
any other source, places each name on the member who sat in that chamber that
term (text_sponsors.Sat.resolve, as every journal-printed sponsor is) and
checks the printed title against the bill's own before it believes the number.

A numbered heading is the key where there is one. A heading with no number is
matched to its bill by its title, by build_data, and only where exactly one
bill of the term and chamber has that title; the reader keeps the title for
that and `number` is null.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import json
import re
from collections import Counter, defaultdict

HOUSE_ROOT = Path("journals")
SENATE_ROOT = Path("journals_senate")
OUT = Path("resolution_sponsors.json")
# The resolutions a chamber itself offered ("Offered by the House of
# Representatives"): {term: [bill]}. Alice, 9 November 2026: the body is the
# sponsor, so the coverage table counts them as covered (build_exports).
BODIES = Path("resolution_bodies.json")

# HOUSE RESOLUTION NO. 14 / House Resolution No. 28 / MEMORIAL RESOLUTION NO. 6 / SENATE RESOLUTION
# NO. 3, alone on its line. The number is optional: 2007 and 2008 print MEMORIAL RESOLUTION.
HEADING = re.compile(
    r"^\s*(?:(?P<body>HOUSE|SENATE)\s+)?(?P<memorial>MEMORIAL\s+)?RESOLUTION"
    r"(?:\s*(?:NO\.?|NUMBER|#)?\s*(?P<num>\d+))?\s*:?\s*$", re.I)
# Who offered it, on the line after the heading, or the lines after it.
OFFERED_THE_FOLLOWING = re.compile(
    r"^\s*(?P<who>(?:Reps?\.|Representatives?|Sens?\.|Senators?)\s.+?)\s+offered the following\b", re.I)
# At the foot of the resolution.
OFFERED_BY = re.compile(r"^\s*Offered(?:\s+and(?:\s+was)?\s+adopted(?:\s+unanimously)?)?"
                        r"\s+by:?\s*(?P<who>.+?)\s*$", re.I)
# A body, not a member.
BODY = re.compile(r"^(?:the\s+)?(?:new\s+hampshire\s+)?(?:house|senate|general court)\b", re.I)
COMMITTEE = re.compile(r"\bcommittee\b", re.I)
TITLES = re.compile(r"\b(?:Reps?\.|Representatives?|Sens?\.|Senators?|Speaker|Majority Leader|"
                    r"Minority Leader|Chairman|Chairwoman|Chair)\s+", re.I)
SPLIT = re.compile(r"\s*(?:,\s*(?:and\s+)?|;\s*|\s+and\s+|\s*&\s*)")
LOOK = 90
# Words every New Hampshire resolution's opening has, which prove nothing about which it is.
COMMON = {"memorializing", "memoralizing", "honoring", "resolution", "hampshire", "representative",
          "representatives", "congratulating", "supporting", "celebrating", "legislature",
          "general", "citizens", "contributions"}


def _norm(s):
    return re.sub(r"[^a-z]", "", (s or "").lower())


def names_of(who):
    """["Flanagan", "Gene Chandler"] from "Reps. Flanagan and Shurtleff", in order; [] where
    the line names a committee or a body, which is not a person the site can link."""
    who = re.sub(r"\([^)]*\)", " ", who or "").strip(" .:")
    if not who or BODY.match(who) or COMMITTEE.search(who):
        return []
    out = []
    for piece in SPLIT.split(TITLES.sub(" ", who)):
        p = piece.strip(" .,:")
        if p and re.search(r"[A-Za-z]{2}", p):
            out.append(p)
    return out


def blocks(path, chamber):
    """blocks_of the lines of one journal file."""
    return blocks_of(path.read_text(encoding="utf-8", errors="replace").split("\n"), chamber)


def blocks_of(lines, chamber):
    """Every resolution a journal prints, as {number, title, line, via, at}.

    `line` is the sponsor line that names a person, "" where the journal prints none or names
    a body or a committee; `via` says which of the shapes found it."""
    heads = []
    for i, ln in enumerate(lines):
        m = HEADING.match(ln)
        if m and (m.group("num") or m.group("memorial")) and (m.group("body") or "").upper() in ("", "HOUSE" if chamber == "H" else "SENATE"):
            heads.append((i, m))
    for k, (i, m) in enumerate(heads):
        end = min(heads[k + 1][0] if k + 1 < len(heads) else len(lines), i + LOOK)
        title = ""
        following = []
        for ln in lines[i + 1:i + 8]:
            s = ln.strip()
            if not s:
                continue
            if not title and not re.match(r"(?:WHEREAS|RESOLVED)", s, re.I) \
                    and not OFFERED_THE_FOLLOWING.match(s):
                title = s
                continue
            following.append(s)
            if len(following) == 2:
                break
        line = via = ""
        for s in ([title] if OFFERED_THE_FOLLOWING.match(title or "") else []) + following:
            o = OFFERED_THE_FOLLOWING.match(s)
            if o:
                line, via = s, "offered the following"
                break
        if OFFERED_THE_FOLLOWING.match(title or ""):
            title = ""
        if not line:
            # The footer closes the resolution: after its first RESOLVED, and before any other
            # "offered the following" -- a later motion of the sitting is another item.
            resolved = False
            for s_ in lines[i + 1:end]:
                if re.match(r"\s*RESOLVED\b", s_, re.I):
                    resolved = True
                elif re.search(r"\boffered the following\b", s_, re.I):
                    break
                elif resolved and OFFERED_BY.match(s_):
                    line, via = s_.strip(), "offered by"
                    break
        who = ""
        if line:
            o = OFFERED_THE_FOLLOWING.match(line) or OFFERED_BY.match(line)
            who = o.group("who")
            if via == "offered by":
                # "Offered by the House of Representatives and adopted unanimously."
                who = re.split(r"\s+and\s+adopted\b|\s+in\s+Regular\s+Session\b|,\s+[A-Z][a-z]+ \d",
                               who)[0]
        opening = re.sub(r"\s+", " ", " ".join(x.strip() for x in lines[i + 1:i + 14]))[:700]
        yield {"number": int(m.group("num")) if m.group("num") else None, "title": title,
               "line": line, "who": who, "via": via, "at": i, "opening": opening,
               "names": names_of(who) if via else []}


def journal_label(path, chamber):
    """"HJ 54 of 2015" from a file name: HJ054.txt, SJ 9.txt, "HJ 05 March 10, 2022.txt"."""
    m = re.match(r"([HS]J)\s*0*(\d+)", path.name)
    return f"{m.group(1)} {m.group(2)} of {path.parent.name}" if m else path.name


def term_of(year):
    y = int(year)
    t = y if y % 2 else y - 1
    return f"{t}-{t + 1}"


def files(root):
    for yd in sorted(p for p in root.glob("*") if p.is_dir() and p.name.isdigit()):
        for f in sorted(yd.glob("*.txt")):
            yield yd, f


# The resolutions the chamber moves as business of the session: the rules, the return of votes, the
# joint convention, the biennium's salary. The journal names the member who moved each one
# ("Reps. Ley and Hinch offered the following: RESOLVED, that the House adopt the Rules"), and
# that is the chamber's officer doing a formality, not a sponsor; the General Court names none.
# They are left as the General Court has them.
HOUSEKEEPING = re.compile(
    r"^RESOLVED\b|\brules of the\b|\bSenate Rules\b|\bRules of the House\b|recording house sessions|"
    r"distribution of house publications|speaker employing personnel|salary and mileage", re.I)


def housekeeping(title):
    return bool(HOUSEKEEPING.search(title or ""))


def agrees(rec, bill_title):
    """Whether the resolution this record was read from is the bill: the journal's own title
    agrees with the bill's, or -- where the journal prints none, as for HR 14 of 2015 -- a
    distinctive word of the bill's title is in the opening of the resolution's text."""
    mine = _norm(re.sub(r"^\W*(?:a\s+)?(?:resolution\s+)?", "", bill_title or "", flags=re.I))
    theirs = _norm(rec.get("title"))
    if theirs:
        n = min(len(mine), len(theirs), 24)
        return n >= 12 and mine[:n] == theirs[:n]
    opening = (rec.get("opening") or "").lower()
    words = [w for w in re.findall(r"[a-z]{6,}", (bill_title or "").lower())
             if w not in COMMON]
    return bool(words) and any(w in opening for w in words)


def printed(rec):
    """The names as a sponsor line carries them, for text_sponsors.split: "Rep. Gene Chandler"."""
    hon = "Rep." if rec.get("chamber") == "H" else "Sen."
    return [f"{hon} {n}" for n in rec["sponsors"]]


def read(house=HOUSE_ROOT, senate=SENATE_ROOT, stats=None, bodies=None):
    """{term: {bill: record}} for every numbered resolution whose journal line names a person.
    A resolution the journal does not number is not keyed."""
    out = defaultdict(lambda: defaultdict(list))
    seen = Counter() if stats is None else stats
    for chamber, root in (("H", house), ("S", senate)):
        if not Path(root).is_dir():
            continue
        for yd, f in files(Path(root)):
            term = term_of(yd.name)
            for b in blocks(f, chamber):
                seen["blocks"] += 1
                if not b["names"] and b["number"] and b["via"] and BODY.match(b["who"] or ""):
                    if bodies is not None:
                        bodies[term].add(f"{chamber}R{b['number']}")
                if not b["names"]:
                    seen["no person: " + (b["via"] or "no line")] += 1
                    continue
                if not b["number"]:
                    seen["a person, but no number"] += 1
                    continue
                seen["with a person"] += 1
                out[term][f"{chamber}R{b['number']}"].append(
                    {"sponsors": b["names"], "journal": journal_label(f, chamber),
                     "title": b["title"], "line": b["line"], "number": b["number"],
                     "opening": b["opening"], "chamber": chamber})
    res = {}
    for term, byb in out.items():
        res[term] = {}
        for key, recs in byb.items():
            # The same resolution printed twice (its introduction and its adoption) names the
            # same people; two that differ are not decided here.
            if len({tuple(r["sponsors"]) for r in recs}) > 1:
                seen["disagreeing: " + term + " " + key] += 1
                continue
            res[term][key] = recs[0]
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--survey", action="store_true", help="count the shapes; write nothing")
    ap.add_argument("--house", default=str(HOUSE_ROOT))
    ap.add_argument("--senate", default=str(SENATE_ROOT))
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    if not Path(a.house).is_dir():
        print(f"FAILED, no {a.house}/ here: the House Journals are not on this machine")
        return 1
    stats = Counter()
    bodies = defaultdict(set)
    res = read(Path(a.house), Path(a.senate), stats, bodies)
    for k, v in sorted(stats.items()):
        print(f"  {v:5,}  {k}")
    named = sum(len(t) for t in res.values())
    print(f"  {named} numbered resolutions name a person")
    if stats["blocks"] < 100:
        # Silence is not success: a reader that stops recognising a heading yields nothing.
        print("FAILED, fewer than 100 resolutions read: the heading shape has changed")
        return 1
    if a.survey:
        return 0
    Path(a.out).write_text(json.dumps(res, indent=1, sort_keys=True), encoding="utf-8")
    print(f"written to {a.out}")
    # Beside it, the ones the chamber offered itself, for the coverage table.
    bpath = Path(a.out).with_name(BODIES.name)
    bpath.write_text(json.dumps({t: sorted(v) for t, v in sorted(bodies.items())}, indent=1),
                     encoding="utf-8")
    print(f"  {sum(len(v) for v in bodies.values())} offered by the chamber itself, written to {bpath}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
