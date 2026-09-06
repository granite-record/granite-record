#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.5
"""
Segment a floor session on what the clerk actually says.

    python3 floor_markers.py --transcript housesession_5_14_2026.txt
    python3 floor_markers.py --transcript t.txt --summary RollCallSummary.txt

The aligner used everywhere else infers boundaries from where bill numbers
cluster in a transcript. That works, but it is statistics, which is why its
tolerances run from three to thirty minutes.

A floor session does not need inference. Every bill opens with the clerk reading
the committee report in a fixed form:

    "Majority of the Committee on Finance to which was referred Senate Bill 408,
     relative to insurance coverage for prosthetics, having considered the same,
     report the same with the following amendment..."

and closes with the outcome stated:

    "197 in the affirmative, 151 in the negative. The committee report is adopted."

Both are quotations, not estimates. The boundary is where the clerk says it is,
to the resolution of the caption line -- a few seconds.

The spoken tallies are a second, independent anchor: they can be matched against
RollCallSummary.txt, which confirms which bill a segment belongs to rather than
assuming the docket order held.
"""

import argparse
import json
import re
from pathlib import Path

# YouTube's copy-paste format runs the timestamp together with a verbose repeat
# and then the text: "1:07:45" + "1 hour, 7 minutes, 45 seconds" + text.
# Seconds must be exactly two digits or the verbose form's first digit is eaten.
LINE = re.compile(
    r"^(?:(\d+):)?(\d{1,2}):(\d{2})"
    r"(?:\d+\s*hours?)?(?:,?\s*\d+\s*minutes?)?(?:,?\s*\d+\s*seconds?)?"
    r"\s*(.*)$")

# The clerk reading a committee report. This is the opening of every bill.
# The clerk's phrasing varies more than it first appears. All of these occur
# in a single session:
#   "Majority of the committee on Finance to which was referred..."
#   "Majority Committee on Criminal Justice and Public Safety to which..."
#   "The Committee on Executive Departments and Administration, which has..."
#   "the committee on executive departments administration which has..."
# so "of the" is optional, "to" is optional, and a comma may sit before "which".
OPEN = re.compile(
    r"(?:majority|minority)?\s*(?:of\s+the\s+)?committee\s+on\s+"
    r"(?P<cmte>[\w ,\-]{4,70}?)\s*,?\s*"
    r"(?:to\s+)?which\s+(?:was|is|has\s+been|has|had)?\s*(?:referr?ed|referr?al)",
    re.I)

# Bill numbers as the captions render them, which is not always as spoken.
# Real examples from one committee session:
#
#   "HP 1381"            P for B
#   "House Bill 18 21FN" a space inserted inside the number
#   "House Bill6004"     the space before the number lost
#   "house bill 1255N"   -FN heard as N
#   "close the public hearing on 1187"   no prefix at all
#
# So the pattern is permissive and the result is checked against the bills the
# docket says were scheduled. Guessing from the transcript alone would be
# fragile; guessing against a known candidate list is not.
BILL_SPOKEN = re.compile(
    r"\b(?:(House|Senate)\s*Bill|(HB|HP|SB|SP|CACR|CAC|HR|SR|HCR|SCR))\s*#?\s*"
    r"(\d[\d\s]{0,5}\d|\d)", re.I)

# A bare number, used where the marker already says what kind of thing it is.
BARE_NUM = re.compile(r"\b(\d{2,4})\b")

# Captions confuse these letters constantly.
LETTER_FIX = {"HP": "HB", "SP": "SB", "CAC": "CACR", "HP.": "HB"}


def fix_bill(kind, num):
    kind = LETTER_FIX.get(kind.upper(), kind.upper())
    return f"{kind}{int(re.sub(r'[^0-9]', '', num))}"


def best_match(found, candidates):
    """Match a garbled number against the bills actually scheduled.

    The docket knows which bills a committee took up that day, so a transcript
    number only has to be close enough to pick one out of a handful. That is a
    far easier problem than reading it correctly in isolation.
    """
    if not candidates:
        return found
    if found in candidates:
        return found
    digits = re.sub(r"[^0-9]", "", found or "")
    kind = re.sub(r"[0-9]", "", found or "")
    # Same number, different letters: HP 1381 against HB1381.
    same_num = [c for c in candidates if re.sub(r"[^0-9]", "", c) == digits]
    if len(same_num) == 1:
        return same_num[0]
    # Same letters, digits differing by an inserted or dropped character.
    near = [c for c in candidates
            if re.sub(r"[0-9]", "", c) == kind
            and abs(len(re.sub(r"[^0-9]", "", c)) - len(digits)) <= 1
            and (digits in re.sub(r"[^0-9]", "", c)
                 or re.sub(r"[^0-9]", "", c) in digits)]
    return near[0] if len(near) == 1 else found

# The outcome, stated.
# The outcome, stated. The two chambers word this differently: the House says
# "the committee report is adopted", the Senate "the motion of ought to pass is
# adopted", and both fall back to "the ayes have it" on a voice vote -- which
# the captions render as "the eyes have it" every time.
CLOSE = re.compile(
    r"\b(?:the\s+)?(?:committee\s+report|motion(?:\s+of\s+\w[\w\s]{0,24})?|"
    r"amendment|bill|reports?)s?\s*"
    r"(?:'s|\s+is|\s+are|\s+was)?\s*(adopted|fails?|passed|defeated|carries)\b"
    r"|\b(?:the\s+)?(?:eyes|ayes|I's)\s+have\s+it\b", re.I)

# A tally read aloud. Caption text mangles "yea"/"nay" badly -- both often come
# out as "A" -- so the words are not trusted, only the two numbers and their
# order, which is always affirmative first.
TALLY = re.compile(
    r"\b(\d{2,3})\s*(?:in\s+the\s+affirmative|voting\s+\w{1,4})[,.\s]+"
    r"(?:and\s+)?(?:the\s+)?(\d{2,3})\s*(?:in\s+)?(?:the\s+)?"
    r"(?:negative|voting\s+\w{1,4})", re.I)

# Committee proceedings announce themselves, and say which bill.
#   "we are going to open the public hearing for House Bill 1082 ..."
#   "open the noticed executive session for House Bill 1520 ..."
#   "I'm closing the public hearing for HP 1381"
#   "close the public hearing on 1187"
PROCEEDING = re.compile(
    r"(?P<act>open(?:ing)?|clos(?:e|ing|ed))\s+(?:the\s+)?(?:noticed\s+)?"
    r"(?P<kind>public\s+hearing|executive\s+session|hearing)\s+"
    r"(?:for|on|of)?\s*(?P<rest>.{0,70})", re.I)

# Senate committees are much less formulaic than House ones. There is often no
# announced opening at all -- the chair simply says "Senate Judiciary is now
# hearing House Bill 1637" or "we're going to go on to House Bill 1416" -- but
# the CLOSE is reliable and always the same shape:
#
#   "Does anyone else wish to testify on 1419? Seeing no one, that'll end the
#    hearing"
#
# The bill is named in the question immediately before, so a close is both a
# boundary and a label. Segmenting backwards from the closes works where
# segmenting forwards from openings does not.
CLOSE_HEARING = re.compile(
    r"seeing\s+(?:no\s*one|none|nobody)[^.]{0,40}?"
    r"(?:end|lend|close|closing)\s+the\s+hearing", re.I)

# The looser openings a Senate chair uses.
OPEN_LOOSE = re.compile(
    r"(?:is\s+now\s+hearing|going\s+to\s+go\s+on\s+to|now\s+taking\s+up|"
    r"we(?:'ll| will)\s+(?:now\s+)?(?:hear|take\s+up))\s+(?P<rest>.{0,60})", re.I)

ROLLCALL = re.compile(r"this is a roll call vote|roll call has been requested", re.I)
DIVISION = re.compile(r"this is a division vote|division has been requested", re.I)


def hms(s):
    s = int(s)
    return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def parse(path):
    caps = []
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        m = LINE.match(line.strip())
        if m and m.group(4).strip():
            h, mm, ss, txt = m.groups()
            caps.append((int(h or 0) * 3600 + int(mm) * 60 + int(ss),
                         txt.strip()))
    return caps


def norm_bill(m):
    chamber, abbr, num = m.group(1), m.group(2), m.group(3)
    if abbr:
        return fix_bill(abbr, num)
    return fix_bill("HB" if chamber.lower().startswith("house") else "SB", num)


def committee_segments(caps, expect=()):
    """Proceedings in a committee recording, from what the chair announces.

    Unlike the floor, a committee chair states both ends outright, so a
    proceeding's span is quoted rather than estimated.
    """
    text, index = join(caps)
    events = []
    for m in PROCEEDING.finditer(text):
        rest = m.group("rest")
        bm = BILL_SPOKEN.search(rest)
        bill = norm_bill(bm) if bm else None
        if not bill:
            nm = BARE_NUM.search(rest)
            if nm:
                bill = f"HB{int(nm.group(1))}"
        events.append({
            "at": time_at(index, m.start()),
            "act": "open" if m.group("act").lower().startswith("open") else "close",
            "kind": ("executive session"
                     if "exec" in m.group("kind").lower() else "public hearing"),
            "bill": best_match(bill, expect) if bill else None,
            "said": m.group(0)[:90]})

    # Where a chair announces openings loosely, or not at all, fall back to
    # closes: each one ends a bill and names it in the question before.
    if len(events) < 2:
        text2, index2 = join(caps)
        closes = []
        for m in CLOSE_HEARING.finditer(text2):
            # A chair may close with "seeing none, that'll end the hearing"
            # without naming the bill, so look back far enough to catch the
            # last time it was named in questioning.
            back = text2[max(0, m.start() - 600):m.start()]
            bm = None
            for cand in BILL_SPOKEN.finditer(back):
                bm = cand
            bill = norm_bill(bm) if bm else None
            if not bill:
                nums = BARE_NUM.findall(back)
                bill = f"HB{int(nums[-1])}" if nums else None
            closes.append({"at": time_at(index2, m.end()),
                           "bill": best_match(bill, expect) if bill else None})
        for m in OPEN_LOOSE.finditer(text2):
            bm = BILL_SPOKEN.search(m.group("rest"))
            if bm:
                events.append({"at": time_at(index2, m.start()), "act": "open",
                               "kind": "public hearing",
                               "bill": best_match(norm_bill(bm), expect),
                               "said": m.group(0)[:90]})
        # Anything still unnamed is filled from the docket's order, which is
        # what the committee published in advance and generally followed.
        if expect:
            used = {c["bill"] for c in closes if c["bill"]}
            spare = [b for b in expect if b not in used]
            for c in closes:
                if not c["bill"] and spare:
                    c["bill"] = spare.pop(0)
                    c["from_docket"] = True

        prev = caps[0][0]
        out = []
        for c in closes:
            if c["bill"]:
                # The opening, if one was announced for this bill, beats the
                # previous close as a start.
                op = next((e["at"] for e in events
                           if e["act"] == "open" and e["bill"] == c["bill"]
                           and prev <= e["at"] < c["at"]), None)
                out.append({"bill": c["bill"], "kind": "public hearing",
                            "start": op or prev, "end": c["at"],
                            "stated_end": True,
                            "stated_start": op is not None,
                            "bill_from_docket": c.get("from_docket", False),
                            "said": "closed by the chair"})
            prev = c["at"]
        if out:
            return out, events

    # Pair each opening with the next closing for the same bill; fall back to
    # the next opening, which is what happens when a chair moves straight on.
    segs = []
    for i, e in enumerate(events):
        if e["act"] != "open" or not e["bill"]:
            continue
        end = None
        for f in events[i + 1:]:
            if f["act"] == "close" and f["bill"] == e["bill"]:
                end = f["at"]
                break
            if f["act"] == "open":
                end = f["at"]
                break
        segs.append({"bill": e["bill"], "kind": e["kind"], "start": e["at"],
                     "end": end or caps[-1][0],
                     "stated_end": bool(end), "stated_start": True,
                     "said": e["said"]})
    return segs, events


def join(caps):
    """One string, with a map back from character position to timestamp.

    Caption lines break mid-sentence, so "of the committee on Finance to which
    was referred" is regularly split across two of them. Searching line by line
    missed most of the openings; searching the joined text finds them all and
    the index gives the time back.
    """
    parts, index, pos = [], [], 0
    for t, txt in caps:
        parts.append(txt)
        index.append((pos, t))
        pos += len(txt) + 1
    return " ".join(parts), index


def time_at(index, pos):
    lo, hi = 0, len(index) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if index[mid][0] <= pos:
            lo = mid
        else:
            hi = mid - 1
    return index[lo][1]


def segment(caps, lookahead=400):
    """One segment per committee report reading."""
    text, index = join(caps)
    opens = []
    for m in OPEN.finditer(text):
        # The bill number follows the phrase, within a sentence or so.
        bm = BILL_SPOKEN.search(text[m.end():m.end() + lookahead])
        opens.append({"start": time_at(index, m.start()),
                      "committee": " ".join(m.group("cmte").split()),
                      "bill": norm_bill(bm) if bm else None,
                      "line": text[m.start():m.start() + 110]})

    for i, o in enumerate(opens):
        o["end"] = opens[i + 1]["start"] if i + 1 < len(opens) else caps[-1][0]
        span = [(t, x) for t, x in caps if o["start"] <= t <= o["end"]]
        o["tallies"] = [{"at": t, "yeas": int(a), "nays": int(b)}
                        for t, x in span for a, b in TALLY.findall(x)]
        o["outcome"] = next(((c.group(1) or "voice vote").lower()
                             for t, x in reversed(span)
                             if (c := CLOSE.search(x))), None)
        o["rollcalls"] = sum(1 for _, x in span if ROLLCALL.search(x))
        o["divisions"] = sum(1 for _, x in span if DIVISION.search(x))
        o["lines"] = len(span)
    return opens


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--transcript", required=True)
    ap.add_argument("--summary", help="RollCallSummary.txt, to check the tallies")
    ap.add_argument("--committee", action="store_true",
                    help="a committee recording rather than a floor session")
    ap.add_argument("--expect", help="comma-separated bills the docket says were "
                                     "scheduled, used to correct garbled numbers")
    ap.add_argument("--out")
    a = ap.parse_args()

    caps = parse(a.transcript)
    if not caps:
        print("No caption lines parsed. Is this a YouTube transcript copy-paste?")
        return
    print(f"{len(caps):,} caption lines, {hms(caps[0][0])} to {hms(caps[-1][0])}\n")

    if a.committee:
        expect = tuple(x.strip().upper().replace(" ", "")
                       for x in (a.expect or "").split(",") if x.strip())
        segs, events = committee_segments(caps, expect)
        print(f"{len(events)} announcements, {len(segs)} proceedings\n")
        print(f"{'start':<10}{'end':<10}{'len':<8}{'bill':<9}{'end?':<7}kind")
        print("-" * 74)
        for s_ in segs:
            print(f"{hms(s_['start']):<10}{hms(s_['end']):<10}"
                  f"{hms(s_['end'] - s_['start']):<8}{s_['bill']:<9}"
                  f"{('both' if s_.get('stated_start') and s_['stated_end']
                       else 'end' if s_['stated_end'] else 'next'):<7}"
                  f"{s_['kind']}")
        if a.out:
            Path(a.out).write_text(json.dumps(segs, indent=2), encoding="utf-8")
            print(f"\nwritten to {a.out}")
        print("\nA span marked 'stated' has both ends quoted from the chair. One")
        print("marked 'next' ran straight into the following bill, so its end is")
        print("where the next one begins.")
        return

    segs = segment(caps)
    named = sum(1 for s in segs if s["bill"])
    print(f"{len(segs)} committee reports read, {named} with a bill number\n")
    print(f"{'start':<10}{'end':<10}{'bill':<9}{'outcome':<10}{'votes':<7}committee")
    print("-" * 78)
    for s in segs:
        print(f"{hms(s['start']):<10}{hms(s['end']):<10}"
              f"{s['bill'] or '?':<9}{(s['outcome'] or '-'):<10}"
              f"{len(s['tallies']):<7}{s['committee'][:30]}")

    # The spoken tallies are an independent check: they should appear in the
    # official record for the same bill.
    if a.summary and Path(a.summary).exists():
        official = {}
        for line in Path(a.summary).read_text(encoding="utf-8-sig",
                                              errors="replace").splitlines():
            f = line.split("|")
            # Fields 5 and 6 are the yea and nay counts. This read 8 and 9,
            # which are the non-voting categories -- so the check could never
            # match and reported every segment as unconfirmed, which reads as
            # "the captions are too garbled to use". rollcall_parser.py is the
            # authority on this layout.
            if len(f) > 12 and f[4].strip():
                official.setdefault(f[4].strip().upper(), []).append(
                    (f[5].strip(), f[6].strip()))
        hit = miss = 0
        for s in segs:
            if not s["bill"]:
                continue
            want = {(str(y), str(n)) for t in s["tallies"]
                    for y, n in [(t["yeas"], t["nays"])]}
            got = {(y, n) for y, n in official.get(s["bill"], [])}
            if want & got:
                hit += 1
            elif want:
                miss += 1
        print(f"\ntallies matched to RollCallSummary: {hit} bills, {miss} not found")
        print("A match confirms the segment is the bill it claims to be, "
              "independently of the docket order.")

    if a.out:
        Path(a.out).write_text(json.dumps(segs, indent=2), encoding="utf-8")
        print(f"\nwritten to {a.out}")

    print("\nEvery boundary here is a quotation, not an estimate: the clerk "
          "states\nwhere each bill begins and how it ended. That is a different "
          "kind of\nfact from a mention cluster, and it deserves a different "
          "tolerance.")


if __name__ == "__main__":
    main()
