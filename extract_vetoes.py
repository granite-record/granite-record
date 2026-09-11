#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-07.15
"""
The governor's veto messages, from the House calendars already on disk.

    python3 extract_vetoes.py --probe          # print what it finds, write nothing
    python3 extract_vetoes.py                  # write veto_messages.json

NO NETWORK. calendars/2025 and calendars/2026 were fetched for the committee
reports and carry these too, so this reads what is already here.

WHY THE CALENDAR AND NOT THE DOCKET

The docket records that a bill was vetoed and the date. It does not record why,
and the why is the whole of a veto message. The governor's reasons are read
into the House on the day and printed in the calendar under a heading of their
own:

    GOVERNOR'S VETO MESSAGE REGARDING HOUSE BILL 221

    I have questions about the impact of this legislation. ...
    For the reasons stated above, I have vetoed House Bill 221.

                                        Respectfully submitted,
                                        Kelly A. Ayotte, Governor
                                        Date: May 22, 2026

WHAT IS AND IS NOT HERE

House bills of the current term: all 34 the record calls vetoed have a message
here, which is why this is worth shipping without asking for anything.

Senate bills have theirs in the SENATE calendars, which this project does not
fetch -- 10 of the current term. The 2023-2024 term has no calendars on disk at
all, so its 24 vetoes have no message. Both gaps are printed at the end of a
run rather than left to be discovered on a page.

A MESSAGE IS REPRINTED UNTIL THE VETO SESSION

The same message appears in every calendar from the veto to the override vote
-- up to 22 times. The EARLIEST is cited, because that is the calendar it was
read into, and every later copy is compared against it: a message that differs
between two printings is reported, never silently resolved.

SOFT HYPHENS

The calendar is justified and pdftotext keeps the line-break hyphens, so the
text arrives with "protec-\ntions". Those are rejoined. Every one of the 34 in
the August 2026 calendar rejoins into a real word and none is a true compound,
but the joins are counted and any that produce a token appearing nowhere else
in the corpus are printed, because a garbled quotation with a citation on it is
worse than no quotation.
"""

import argparse
import collections
import csv
import json
import re
import sys
from pathlib import Path

import proceedings as P

# The heading, tolerant of what -layout does to a two-column page: HC012 has
# "HOUSE                                    BILL  451-FN" with 40 spaces in it.
#
# AND THE OLDER HEADINGS, 1997-2014, read off the calendars rather than
# imagined: "GOVERNOR'S VETO MESSAGE ON HB 149" (167 of them), "...REGARDING
# HB 1", "...ON hb 12", "...ON HOUSE BILL 1220", "...of HB 403", "Regarding
# Senate Bill 391". Those are accepted only when the heading stands ALONE on
# its line, because the same words open the calendar's contents entries --
# "Governor's Veto Message on HB 1220 / and HB 1333, Meetings and Notices" --
# and a contents entry read as a heading would put the calendar's welcome
# letter in a governor's mouth. messages() then requires such a message to
# name its own bill, which a contents entry never does.
HEAD = re.compile(
    r"GOVERNOR'?S\s+VETO\s+MESSAGE\s+REGARDING\s+"
    r"(?P<kind>HOUSE|SENATE)\s+BILL\s+(?P<num>\d+)(?P<suffix>-[A-Z]+)?"
    r"|GOVERNOR'?S[ \t]+VETO[ \t]+MESSAGE[ \t]+(?:ON|REGARDING|OF)[ \t]+"
    r"(?:(?P<okind>HOUSE|SENATE)[ \t]+BILL[ \t]+|(?P<abbr>HB|SB)[ \t]*)"
    r"(?P<onum>\d+)(?P<osuffix>(?:-[A-Z]+)*)[ \t]*(?=\n|$)",
    re.I)
# A date on its own line straight after an older heading -- "June 19, 1997",
# "April 26th, 2004" -- where Shaheen and Benson dated their messages.
TOPDATE = re.compile(r"^\s*([A-Z][a-z]+\s+\d{1,2})(?:st|nd|rd|th)?,\s*(\d{4})\s*$",
                     re.M)
# A signature that is a name, not the rule it is signed on or the date line:
# a 2010 Senate block prints "Date: July 20, 2010 ______" where the name is.
NAMEISH = re.compile(r"^[A-Z][A-Za-z.'\-]+(?:\s+[A-Z][A-Za-z.'\-]*)*(?:,\s*Governor)?$")
# The 1997-1999 calendars are printouts of web pages, and the browser's own
# footer lands in the text: "file:///C/Users/.../houcal75.htm[11/8/2021 ...]".
PRINTOUT = re.compile(r"^[^\n]*file:///[^\n]*$", re.M)
# The signature block that ends one.
SIGN = re.compile(
    # A comma on most, a full stop on SB501.
    r"Respectfully\s+submitted[.,]?\s*\n"
    # The Senate prints the rule the governor signs on, between the closing
    # and the name. Skipped, or the byline is a row of underscores.
    r"(?:[ \t]*_{5,}[ \t]*\n)?"
    r"\s*(?P<who>[^\n]{3,60}?)\s*\n"
    # Sununu's title sits on its own line; Ayotte's is appended to the name.
    r"(?:[ \t]*(?P<title>Governor)[ \t]*\n)?"
    # And Sununu's block carries no Date at all.
    # "Date: May 22, 2026", or a bare date on its own line under the title,
    # or -- on nine of Ayotte's Senate messages -- nothing at all.
    r"(?:\s*(?:Date:\s*)?(?P<date>[A-Z][a-z]+\s+\d{1,2},\s*\d{4}))?",
    re.I)
# "...pursuant to part II, Article 44 of the New Hampshire Constitution, on
# August 2, 2024, I have vetoed House Bill 1622". The governor stating the day
# they vetoed it, which is where the date comes from when the signature has
# none.
SAIDDATE = re.compile(
    r"\bon\s+([A-Z][a-z]+\s+\d{1,2},\s*\d{4}),?\s*I\s+have\s+vetoed",
    re.I)
MONTHS = {m: i + 1 for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August",
     "September", "October", "November", "December"])}
SOFT = re.compile(r"(\w)-\n[ \t]*([a-z])")
# What the body says the bill is, so a heading and a body that disagree are
# noticed. HC029 heads one message "HOUSE BILL 1358" and ends it "I have vetoed
# House Bill 1385"; one of those is a typo at the source and this site does not
# get to decide which.
INBODY = re.compile(r"\b(?:House\s+Bill|Senate\s+Bill|HB|SB)\s*(\d+)\b", re.I)
HEALED = [0]


def iso(d):
    m = re.match(r"([A-Z][a-z]+)\s+(\d{1,2}),\s*(\d{4})", d or "")
    if not m or m.group(1) not in MONTHS:
        return ""
    return f"{m.group(3)}-{MONTHS[m.group(1)]:02d}-{int(m.group(2)):02d}"


# The running header pdftotext leaves at every page break: a form feed, then
# "13 JUNE2025HOUSERECORD  3" or "3  13 JUNE2025HOUSERECORD". Matched on the
# word RECORD rather than on "the line after a form feed", because one page in
# twenty calendars breaks straight into a sentence.
PAGEHEAD = re.compile(
    # The House's running header names the record: "13 JUNE2025HOUSERECORD 3".
    # The Senate's is a bare page number on its own line. Both are the line
    # straight after a form feed, and both land inside a sentence when a
    # message runs over a page. The 1997-2000 calendars are browser printouts
    # whose page header is "House Calendar 62" or "House Calendar No. 12":
    # it landed in HB1310 of 1998 as "...can be accepted. House Calendar 62
    # H.B. 1310 would impose...". Only straight after a form feed, so a
    # sentence that mentions a calendar is never touched.
    r"\n*\x0c[ \t]*(?:[^\n]*(?:HOUSE|SENATE)\s*RECORD[^\n]*|\d{1,4}"
    r"|(?:HOUSE|SENATE)\s+CALENDAR(?:\s+NO\.?)?\s*\d*[A-Z]?)[ \t]*\n*",
    re.I)
# A governor's name as the calendar printed it can carry the typesetter's
# slip -- "Margret Wood Hassan", "Jeanne Shaheen Governor" -- and a byline is
# a person's name, which this site gives correctly rather than as mistyped.
# The message itself is quoted exactly; only the byline is normalised, and
# only for the governors of the years on disk.
GOVERNORS = {"shaheen": "Jeanne Shaheen", "benson": "Craig R. Benson",
             "lynch": "John H. Lynch", "hassan": "Margaret Wood Hassan",
             "sununu": "Christopher T. Sununu", "ayotte": "Kelly A. Ayotte",
             "merrill": "Stephen Merrill", "gregg": "Judd Gregg"}
ENDS_SENTENCE = re.compile(r"[.!?:\u201d\"]\s*$")


def unpaginate(text):
    """Take the page furniture out, and heal the sentence it interrupted.

    A page can break mid-sentence or between paragraphs. Where the text before
    the break does not end a sentence and the text after starts lower case, it
    is one sentence and is rejoined; otherwise the paragraph break stays.
    """
    out, last, healed = [], 0, 0
    for m in PAGEHEAD.finditer(text):
        before = text[last:m.start()]
        after = text[m.end():m.end() + 2]
        out.append(before)
        if before.strip() and not ENDS_SENTENCE.search(before) \
                and after[:1].islower():
            # A word can be split by the SAME break: "...provid-", then
            # the page header, then "ing". Healing with a space left
            # "provid- ing" in three messages, which is exactly why those
            # three read differently from their own reprints.
            if before.rstrip().endswith("-"):
                out[-1] = before.rstrip()[:-1]
            else:
                out.append(" ")
            healed += 1
        else:
            out.append("\n\n")
        last = m.end()
    out.append(text[last:])
    # Any form feed the pattern did not claim is still a page break.
    return "".join(out).replace("\x0c", "\n\n"), healed


def dehyphenate(text):
    """Rejoin words the calendar's justification split across a line."""
    joins = []

    def one(m):
        joins.append(m.group(1) + m.group(2))
        return m.group(1) + m.group(2)
    return SOFT.sub(one, text), joins


def tidy(text):
    """Paragraphs, with the calendar's column padding taken out."""
    text, joins = dehyphenate(text)
    out, para = [], []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            if para:
                out.append(" ".join(para))
                para = []
            continue
        para.append(line)
    if para:
        out.append(" ".join(para))
    # A closing full stop can be set on a line of its own, which arrives as a
    # paragraph containing ".". It belongs to the sentence above it.
    merged = []
    for q in out:
        if merged and len(q) <= 2 and not q[:1].isalnum():
            # ...and not if the sentence already ends that way. In two
            # printings the stray stop is a duplicate of one already set, and
            # appending it produced "House Bill 1184.." -- a quotation this
            # site would have published with a citation on it.
            if not merged[-1].rstrip().endswith(q.strip()):
                merged[-1] += q
        else:
            merged.append(q)
    return [re.sub(r"\s{2,}", " ", q) for q in merged if q], joins


def messages(text, source):
    """Every veto message in one calendar."""
    text = PRINTOUT.sub("", text)
    text, healed = unpaginate(text)
    HEALED[0] += healed
    found = []
    dropped = []
    marks = list(HEAD.finditer(text))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        block = text[m.end():end]
        old = m.group("onum") is not None
        # An older heading's date line, before it can become paragraph one.
        top = TOPDATE.match(block.lstrip("\n")) if old else None
        if top:
            block = block.lstrip("\n")[top.end():]
        sig = SIGN.search(block)
        body = block[:sig.start()] if sig else block
        paras, joins = tidy(body)
        # Drop a leading fragment that is the heading's own wrapped remainder
        # or the bill's title line, both of which arrive before the first
        # blank line and are not part of what the governor wrote.
        if paras and len(paras[0]) < 40 and not paras[0].endswith("."):
            paras = paras[1:]
        if not paras:
            continue
        if old:
            kind = m.group("okind") or ("HOUSE" if m.group("abbr").upper() == "HB"
                                        else "SENATE")
            bill = ("HB" if kind.upper() == "HOUSE" else "SB") + m.group("onum")
        else:
            bill = ("HB" if m.group("kind").upper() == "HOUSE" else "SB") + m.group("num")
        said = {x for x in INBODY.findall(" ".join(paras))}
        # AN OLDER HEADING MUST BE MET BY ITS OWN BILL IN THE TEXT. Shaheen,
        # Benson, Lynch and Hassan all end "I have vetoed HB 503" or name the
        # bill in the first sentence; a contents entry that slipped past the
        # alone-on-its-line rule names nothing. The modern form keeps its
        # old behaviour -- HC029's "HB 1358"/"House Bill 1385" typo is the
        # source's own and is published as it stands.
        if old and re.sub(r"\D", "", bill) not in said:
            dropped.append((bill, "does not name its own bill"))
            continue
        # "Kelly A. Ayotte, Governor" and "Christopher T. Sununu, Governor"
        # -- one name shape, whichever line the title arrived on.
        who = (sig.group("who").strip().rstrip(",") if sig else "")
        if sig and sig.group("title") and "governor" not in who.lower():
            who = f"{who}, {sig.group('title').strip()}"
        if who and not NAMEISH.match(who):
            dropped.append((bill, f"signed {who[:30]!r}, which is not a name"))
            continue
        # The byline, normalised to the governor's own name; a signature that
        # is the title alone names nobody.
        words = re.sub(r",?\s*Governor\s*$", "", who, flags=re.I).split()
        if who and not words:
            dropped.append((bill, "signed 'Governor' and no name"))
            continue
        if words and words[-1].lower() in GOVERNORS:
            who = f"{GOVERNORS[words[-1].lower()]}, Governor"
        when = iso(sig.group("date")) if (sig and sig.group("date")) else ""
        if not when:
            m2 = SAIDDATE.search(" ".join(paras))
            if m2:
                when = iso(m2.group(1))
        if not when and top:
            when = iso(f"{top.group(1)}, {top.group(2)}")
        # SHAPE FIRST. A message that runs past a plausible length, or that
        # carries a heading belonging to another section, is not a veto
        # message that needs trimming -- it is the end boundary having been
        # missed, and publishing it would put a room-booking list in a
        # Governor's mouth.
        ok, why = is_whole(paras)
        if not ok:
            dropped.append((bill, why))
            continue
        # AND FIT TO QUOTE, which is a separate question from being whole.
        # The Senate calendars that arrived on 9 September took the count from
        # 124 messages to 177 and brought two the site must not put in a
        # Governor's mouth: SB101 with "e- a" still in it, where the
        # calendar's justification split a word across a line and the rejoin
        # did not heal it, and SB141 with no calendar to cite.
        #
        # These are the same tests preflight applies to what is published, and
        # they belong here too, because the check can only say the site is
        # wrong -- this is where it stops being wrong. The veto itself is
        # still recorded from the docket; what is dropped is the quotation.
        unfit = quotable(paras, who, when, source)
        if unfit:
            dropped.append((bill, unfit))
            continue
        found.append({
            "bill": bill,
            "text": paras,
            "governor": who,
            "date": when,
            "source": source,
            # Every bill number the message itself names, so a heading and a
            # body that disagree can be seen rather than guessed at.
            "_named": sorted(said),
            "_joins": joins,
        })
    if dropped:
        print(f"  {len(dropped)} message(s) dropped as not a veto message: "
              + "; ".join(f'{b} ({w})' for b, w in dropped[:3]))
    return found


def quotable(paras, who, when, source):
    """Why this must not be quoted, or None if it may be.

    A garbled quote presented as what somebody said is a transcription error
    wearing the clothes of a citation, which is the rule this whole file
    exists under."""
    text = " ".join(paras).strip()
    m = BROKEN.search(text)
    if m:
        return f"carries {m.group(0)!r}"
    if len(text) < 80:
        return f"{len(text)} characters, not a message"
    if not who:
        return "names no author"
    if when and not ISO.fullmatch(when):
        return f"date is {when!r}"
    if not (source or {}).get("url"):
        return "cites no calendar"
    # THE CITATION MUST BE FROM THE MESSAGE'S OWN YEAR. All 108 messages of
    # 2013-2022 cited a calendar of 2023 or 2024 -- 2015's HB151 linked
    # "No40 November 08 2024.pdf" for a message printed in June 2015 -- left
    # by a run before the year went into the key, and kept by the merge,
    # because this asked only that a URL exist.
    m = URL_YEAR.search(source["url"])
    if m and str(source.get("year") or "") and m.group(1) != str(source["year"]):
        return f"cites a {m.group(1)} calendar for one printed in {source['year']}"
    return None


# The year folder in a calendar's address: fileName=calendars%5C2015%5C...
URL_YEAR = re.compile(r"(?:calendars|journals)(?:%5C|\\|/)(\d{4})(?:%5C|\\|/)",
                      re.I)


def queue_urls(path="archive/queue.csv"):
    """{calendar PDF on disk: the address it was fetched from}.

    The drain's queue names every calendar's address and the file it went
    to, which calendars.json never did for the years before 2023. Where
    several listed documents share one file -- a Senate supplement saved at
    its base calendar's path, two 2018 calendars given one number -- the
    address is the one row that records fetching it, and where that is not
    one row, no address: a quotation must cite the document it came from.
    """
    try:
        rows = list(csv.DictReader(open(path, encoding="utf-8")))
    except OSError:
        return {}
    by = collections.defaultdict(list)
    for r in rows:
        if r.get("kind") == "calendar" and r.get("state") == "held":
            by[r["path"].replace("\\", "/").lower()].append(r)
    out = {}
    for p, rs in by.items():
        fetched = [r for r in rs if r.get("fetched")]
        pick = rs if len(rs) == 1 else fetched
        if len(pick) == 1 and pick[0].get("url"):
            out[p] = pick[0]["url"]
    return out


# A VETO MESSAGE HAS A SHAPE, AND THESE ARE NOT IT.
#
# The archived calendars arrived in an older layout and the end boundary is
# not always found in them. HB455's message came out at 195 lines and had
# swallowed the whole rest of the document -- COMMITTEE MEETINGS, OFFICIAL
# NOTICES, MEMBERS' NOTICES, a list of room bookings -- and would have been
# published under a heading saying the Governor wrote it.
#
# That is the worst thing this file can produce. A missing veto message is a
# gap; a wrong one is words put in a Governor's mouth. So a message that runs
# past a plausible length, or that contains a heading belonging to another
# section, is dropped and counted rather than trimmed and hoped over.
RUNAWAY = 60
NOT_A_MESSAGE = ("COMMITTEE MEETINGS", "OFFICIAL NOTICES", "MEMBERS' NOTICES",
                 "REVISED FISCAL NOTES", "BILLS LAID ON THE TABLE",
                 "HOUSE DEADLINES")


# A word the calendar's justification split across a line and rejoin() did
# not heal: a letter, a hyphen, a space, then a lone letter.
BROKEN = re.compile(r"\w- \w")
ISO = re.compile(r"\d{4}-\d\d-\d\d")


def is_whole(lines):
    """(ok, why not). Shape only -- nothing here reads the prose."""
    if len(lines) > RUNAWAY:
        return False, f"{len(lines)} lines, which is not a veto message"
    for l in lines:
        s = l.strip().upper()
        for h in NOT_A_MESSAGE:
            if s == h or s.startswith(h):
                return False, f"contains the heading {h!r}"
    return True, ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="calendars",
                    help="the House calendars")
    ap.add_argument("--senate-dir", default="calendars_senate",
                    help="the Senate calendars, where a veto message on a\n Senate bill is printed; skipped if the folder is not there")
    ap.add_argument("--out", default="veto_messages.json")
    ap.add_argument("--index", default="calendars.json",
                    help="calendar name -> its address on gc.nh.gov")
    ap.add_argument("--probe", action="store_true", help="print, write nothing")
    a = ap.parse_args()

    root = Path(a.dir)
    if not root.exists():
        sys.exit(f"{root} is not there. The calendars are fetched by "
                 "fetch_committee_reports.py.")
    try:
        cal_url = json.loads(Path(a.index).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cal_url = {}
    # The address of the very file a message is read from, where the drain's
    # queue can say it; calendars.json, keyed by name and year, where not.
    by_file = queue_urls()

    # (term, bill) -> the earliest printing, plus every later one for comparison
    best, copies = {}, collections.defaultdict(list)
    all_joins = collections.Counter()
    # Both chambers. A veto message is read into the chamber the bill came
    # from, so a Senate bill's is in a Senate calendar and nowhere else.
    roots = [(root, "HC")]
    sroot = Path(a.senate_dir)
    if sroot.exists():
        roots.append((sroot, "SC"))
    files = [(f, pre) for r, pre in roots for f in sorted(r.rglob("*.txt"))]
    for f, prefix in files:
        year = f.parts[-2]
        num = re.sub(r"\D", "", f.stem)
        name = f"{prefix} {int(num)}" if num else f.stem
        # THE YEAR IS PART OF THE KEY, and the fallback that dropped it was
        # citing the wrong document. calendars.json holds one entry per
        # "SC 25 2023"; asking it for bare "SC 25" returned whichever year it
        # happened to hold, so all 48 Senate messages from terms before
        # 2023 cited a 2023 calendar -- SB101 of 2015-2016 pointing at
        # "No 25 June 01 2023.pdf".
        #
        # A message whose calendar has no known address now cites none, and
        # quotable() drops it rather than publishing a quotation attached to
        # a document it did not come from. Citing the wrong source is worse
        # than citing no source.
        pdf = str(f.with_suffix(".pdf")).replace("\\", "/").lower()
        src = {"calendar": f.stem, "year": year, "name": name,
               "url": by_file.get(pdf) or cal_url.get(f"{name} {year}", "")}
        for msg in messages(f.read_text(encoding="utf-8", errors="replace"), src):
            term = P.term_of(year)
            key = (term, msg["bill"])
            all_joins.update(msg.pop("_joins"))
            copies[key].append(msg)

    # A message is reprinted in every calendar from the veto to the override
    # vote. Where those printings disagree -- a missing space, a stray full
    # stop, whatever that day's typesetting did -- the published text is the
    # one most of them carry, and the citation is the EARLIEST calendar
    # carrying that text rather than the earliest overall, so the calendar
    # cited actually contains the sentence quoted from it.
    differ = []
    for key, group in copies.items():
        counts = collections.Counter(" ".join(m["text"]) for m in group)
        winner, n = counts.most_common(1)[0]
        best[key] = min((m for m in group if " ".join(m["text"]) == winner),
                        key=lambda m: (m["source"]["year"],
                                       m["source"]["calendar"]))
        if len(counts) > 1:
            differ.append(f"{key[1]}: {n} of {len(group)} printings agree, "
                          f"{len(counts) - 1} other reading(s) not used")

    # A heading and a body that name different bills.
    mismatched = [f"{k[1]} is headed {k[1]} and its text names "
                  f"{', '.join(v['_named'])}"
                  for k, v in best.items()
                  if v["_named"] and re.sub(r"\D", "", k[1]) not in v["_named"]]

    out = {}
    for (term, bill), msg in sorted(best.items()):
        msg = {k: v for k, v in msg.items() if not k.startswith("_")}
        out.setdefault(term, {})[bill] = msg

    per = collections.Counter(pre for _, pre in files)
    print(f"{len(files)} calendars read ("
          + ", ".join(f"{n} {k}" for k, n in sorted(per.items()))
          + f"), {sum(len(v) for v in copies.values())} printings, "
          f"{len(best)} distinct messages")
    for term in sorted(out):
        print(f"  {term}: {len(out[term])} bills")
    print(f"  {sum(all_joins.values()):,} line-break hyphens rejoined "
          f"({len(all_joins)} distinct words)")
    print(f"  {HEALED[0]:,} sentences rejoined across a page break")
    undated = sum(1 for byb in out.values() for m in byb.values()
                  if not m.get("date"))
    if undated:
        print(f"  {undated} message(s) state no date anywhere -- not in the "
              "signature\n    and not in the text. The page shows none for "
              "those rather than the\n    docket's date, which is a different "
              "fact: it is the day the veto\n    reached the chamber.")
    if differ:
        print(f"  {len(differ)} message(s) differ between printings: "
              + "; ".join(differ[:3]))
    if mismatched:
        print("  heading and text name different bills -- the source's own "
              "typo, kept as it is:")
        for x in mismatched[:4]:
            print(f"    {x}")

    # What is missing, said out loud rather than left to be found on a page.
    try:
        idx = json.loads(Path("site/index.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        idx = []
    want = collections.Counter()
    for b in idx:
        if "eto" not in (b.get("status") or ""):
            continue
        if b.get("id") in (out.get(b.get("term")) or {}):
            continue
        want[(b.get("term"), re.match(r"[A-Z]+", b["id"]).group(0))] += 1
    if want:
        print("  vetoed bills with no message here:")
        for (term, kind), n in sorted(want.items()):
            # Two different gaps, and a bill can be in both. Say which one
            # actually applies rather than whichever the test reaches first.
            if term not in out:
                why = f"no calendar for {term} is on disk"
            elif kind == "SB" and not sroot.exists():
                why = ("their messages are in the SENATE calendars, and "
                       f"{a.senate_dir}/ is not there")
            else:
                why = "no calendar on disk carries one"
            print(f"    {n:>2} {kind} in {term} -- {why}")

    if a.probe:
        k = next(iter(sorted(best)), None)
        if k:
            m = best[k]
            print(f"\n--probe, {k[1]} from {m['source']['calendar']}:")
            print(f"    {m['governor']}, {m['date']}")
            for p in m["text"][:2]:
                print(f"    {p[:150]}{'...' if len(p) > 150 else ''}")
        print("\nNothing written. Drop --probe once that looks right.")
        return 0

    if not out:
        print(f"\nNOT WRITING {a.out}: no message was found in {len(files)} "
              "calendars. That is a parser that no longer matches the "
              "calendar, not a year without vetoes.")
        return 1

    # MERGE. A run over a directory holding one term's calendars must not
    # remove another term's, the same rule narratives.json and rollcalls.json
    # follow.
    op = Path(a.out)
    prior = {}
    if op.exists():
        try:
            prior = json.loads(op.read_text(encoding="utf-8"))
        except ValueError:
            prior = {}
    kept = [t for t in prior if t not in out]
    merged = {**{t: prior[t] for t in kept}, **out}
    if kept:
        print("  kept, because no calendar read here covers them: "
              + ", ".join(f"{t} ({len(prior[t])})" for t in sorted(kept)))
    # THE GATE GOES ON THE WRITE, NOT ONLY ON THE READ. A term this run did
    # not produce is kept whole -- the rule that a writer run on a subset must
    # not destroy the rest -- and that is right, but it also kept two messages
    # this run had deliberately rejected: SB101 with "e- a" still in it and
    # SB141 citing a calendar it did not come from. They had been written by
    # an earlier run under looser rules and no later run could remove them.
    #
    # So every message is tested on the way out, whether this run made it or
    # inherited it. The veto is still recorded from the docket; what is
    # dropped is the quotation.
    culled = []
    for term_, bills_ in list(merged.items()):
        if not isinstance(bills_, dict):
            continue
        for bill_, rec_ in list(bills_.items()):
            if not isinstance(rec_, dict):
                continue
            why_ = quotable(rec_.get("text") or [], rec_.get("governor"),
                            rec_.get("date"), rec_.get("source"))
            if why_:
                del bills_[bill_]
                culled.append(f"{bill_} ({why_})")
    if culled:
        print(f"  {len(culled)} message(s) not fit to quote and left out: "
              + "; ".join(culled[:4]))
    op.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    print(f"-> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
