#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-07.9
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
import json
import re
import sys
from pathlib import Path

import proceedings as P

# The heading, tolerant of what -layout does to a two-column page: HC012 has
# "HOUSE                                    BILL  451-FN" with 40 spaces in it.
HEAD = re.compile(
    r"GOVERNOR'?S\s+VETO\s+MESSAGE\s+REGARDING\s+"
    r"(?P<kind>HOUSE|SENATE)\s+BILL\s+(?P<num>\d+)(?P<suffix>-[A-Z]+)?",
    re.I)
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
INBODY = re.compile(r"\b(?:House|Senate)\s+Bill\s+(\d+)\b", re.I)
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
    # message runs over a page.
    r"\n*\x0c[ \t]*(?:[^\n]*(?:HOUSE|SENATE)\s*RECORD[^\n]*|\d{1,4})[ \t]*\n*",
    re.I)
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
    text, healed = unpaginate(text)
    HEALED[0] += healed
    found = []
    marks = list(HEAD.finditer(text))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        block = text[m.end():end]
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
        bill = ("HB" if m.group("kind").upper() == "HOUSE" else "SB") + m.group("num")
        said = {x for x in INBODY.findall(" ".join(paras))}
        # "Kelly A. Ayotte, Governor" and "Christopher T. Sununu, Governor"
        # -- one name shape, whichever line the title arrived on.
        who = (sig.group("who").strip().rstrip(",") if sig else "")
        if sig and sig.group("title") and "governor" not in who.lower():
            who = f"{who}, {sig.group('title').strip()}"
        when = iso(sig.group("date")) if (sig and sig.group("date")) else ""
        if not when:
            m2 = SAIDDATE.search(" ".join(paras))
            if m2:
                when = iso(m2.group(1))
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
    return found


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
        src = {"calendar": f.stem, "year": year, "name": name,
               "url": cal_url.get(f"{name} {year}") or cal_url.get(name, "")}
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
    op.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    print(f"-> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
