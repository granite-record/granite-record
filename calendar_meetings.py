#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-08.9
"""
Who is hearing what, when, and in which room -- out of the calendars on disk.

    python3 calendar_meetings.py --check          # parse and score, write nothing
    python3 calendar_meetings.py --show 2         # print two files' meetings
    python3 calendar_meetings.py --out meetings.json

No network. Reads calendars/ and calendars_senate/ only.

WHAT THIS IS FOR

Someone deciding whether to testify needs four things: the bill, the day, the
time, and the room. The docket has all four but only per bill -- you can ask
what happened to HB 1467 and you cannot ask what the Education committee is
hearing on Monday. The calendar is the other way round, and the calendar is
also the legal notice: it is where a hearing is announced.

That makes it worth parsing twice over. It gives the schedule view, and it
gives the date a hearing was NOTICED, which is what opens the window for
public testimony.

THE SHAPE, READ OFF THE FILES

House, under a heading "COMMITTEE MEETINGS":

    FRIDAY, MARCH 6                         <- no year; it comes from the masthead

    EDUCATION POLICY AND ADMINISTRATION, Room 232, GP
    10:00 a.m. HB 1467-FN, establishing the New Hampshire Seal of Civic Excel-
                        lence and Engagement program.
    10:15 a.m. HB 1573, permitting excused absences for students participating.

Senate, under "HEARINGS", and tidier -- its day headings carry the year and
its committee blocks name their members:

    TUESDAY, JANUARY 13, 2026

    COMMERCE, Room 100, SH
    Sen. Innis (C), Sen. Ricciardi (VC), Sen. Murphy, Sen. McGough
    9:30 a.m.   SB 417-FN, requiring on-premises licensees to post warnings.

THE RULE THAT DECIDES WHAT A MEETING IS

A time line either states its business or it does not:

    10:00 a.m. Executive session on HB 1542-FN, ...      <- stated
    10:00 a.m. Full committee work session on HB 1600-FN <- stated
    10:00 a.m. Regular meeting.                          <- stated, no bill
    10:00 a.m. HB 1467-FN, establishing the ...          <- NOT stated

An unstated one is a public hearing. That is not an assumption: it was checked
against the docket, which records the same two bills as

    HB1467  Public Hearing: 01/12/2026 10:00 am GP 232
    HB1573  Public Hearing: 01/12/2026 10:15 am GP 232

-- the same day, the same times, the same room. --check scores every parsed
row that way, against 4,954 scheduled-meeting rows the docket states for
itself, so the rule is measured on every run rather than trusted once.

WHAT THE TEXT DOES TO ITSELF

Three things, all measured across the 172 House files:

  4,070 pages, each starting with a form feed and a running head
        ("4  6 MARCH2026HOUSERECORD"). The form feed is the reliable
        marker; the head's spelling is not. 172 pages are blank and 9
        carry content where the head did not extract, so the head is
        dropped only when it looks like one -- dropping the first line
        of every page would have deleted nine real lines of business.
  2,585 words broken across a line with a hyphen ("manufac-" / "tured").
        Rejoined only where the next fragment starts lower case, because
        "sixty-day" and "RSA 415:6-e" are also in here.
    172 of 172 files state their own publication date in the masthead
        ("Concord,N.H.  Friday,January9,2026"), which is the notice date.
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# ---------------------------------------------------------------- the sources
CHAMBERS = {
    # THE SECTION'S TERMINATOR CHANGED PART WAY THROUGH 2023 and neither
    # spelling was in this list: 126 of 161 files end at REVISED FISCAL NOTES
    # and 24 at OFFICIAL NOTICES, and a bare "NOTICES" matches neither as a
    # whole line. So the section ran on past the meetings and swallowed the
    # fiscal notes into the last committee of the day. The score did not
    # catch it, because the junk rows were not in the docket and so fell
    # outside the set being scored -- silence is not success.
    "H": {"dir": "calendars", "glob": "HC*.txt", "head": "COMMITTEE MEETINGS",
          "running": "HOUSERECORD",
          "ends": ("REVISED FISCAL NOTES", "OFFICIAL NOTICES", "AMENDMENTS",
                   "NOTICES", "HOUSE DEADLINES", "DEADLINES")},
    "S": {"dir": "calendars_senate", "glob": "*.txt", "head": "HEARINGS",
          "running": "SENATERECORD",
          "ends": ("NOTICES", "OFFICIAL NOTICES", "SENATE CALENDAR",
                   "SENATE DEADLINES")},
}

MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], 1)}

# The masthead. Anchored on "Concord, N.H." rather than on "Vol. 48", which
# four files wrap away from it.
PUBDATE = re.compile(
    r"Concord\s*,?\s*N\.?\s*H\.?\s*[,.]?\s+(?:[A-Za-z]+day)\s*,?\s*"
    r"([A-Za-z]+)\s*(\d{1,2})\s*,?\s*(\d{4})", re.I)
# THE SENATE'S MASTHEAD IS NOT A VARIANT OF THE HOUSE'S. There is no
# "Concord, N.H." line at all -- the date stands alone in the top right corner
# with the issue number under it:
#
#                                                          January8,2026
#                                                          No.1
#
# Reading the Senate with the House's pattern found a date in 10 of 204 files,
# and those ten were matching "Concord, NH" inside a meeting's street address
# further down the page -- a wrong answer that looked like a right one. So the
# chamber decides the pattern.
SENATE_PUBDATE = re.compile(
    r"^\s*([A-Za-z]+)\s*(\d{1,2})\s*,\s*(\d{4})\s*$", re.M)

# A day heading, which four times in 2023 has a committee name bled onto it
# from the left column -- "CRIMINAL                 WEDNESDAY, FEBRUARY 8".
# In three of those files it is the ONLY day heading, so anchoring on the
# weekday at the start of the line returned nothing at all for them. What is
# allowed before the weekday is capitals and spaces, which prose is not.
DAY = re.compile(
    r"^(?:\s*[A-Z][A-Z ]{2,}?)?\s{2,}"
    r"(MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY|SATURDAY|SUNDAY)\s*,\s*"
    # re.M as well as re.I: without it "^" only matches at the start of the
    # whole string, so DAY.match() worked line by line and DAY.finditer() --
    # which is how a file with no section heading is found -- never matched
    # anything at all and failed silently.
    r"([A-Z]+)\s+(\d{1,2})\s*(?:,\s*(\d{4}))?\s*$", re.I | re.M)
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday",
            "saturday", "sunday"]

# NAME, Room 232, GP   |   NAME (RSA 79:32), Room 154, GP   |   NAME, <address>
HEADER = re.compile(
    r"^([A-Z][A-Z0-9 ,'&/\.\-]{2,}?)"          # the committee, shouting
    r"(?:\s*\(RSA[^)]*\))?"                     # an optional statute cite
    r"\s*,\s*(.+?)\s*$")

ROOM = re.compile(r"^Room\s+([\w\-]+)\s*,\s*(SH|LOB|GP|SL)$", re.I)
# A header opens with the committee's name in capitals. Everything after the
# first comma -- the room, the building, a street address -- is mixed case,
# so the test is on the opening run and not on the line.
SHOUT = re.compile(r"^[A-Z][A-Z0-9'&/\.\- ]{3,}?(?:\s*\(RSA[^)]*\))?\s*,")
TIME = re.compile(r"^\s*(\d{1,2}):(\d{2})\s*([ap])\.?\s?m\.?\s*(.*)$", re.I)
BILL = re.compile(r"\b(HB|SB|CACR|HR|SR|HCR|SCR)\s*0*(\d{1,4})"
                  r"((?:-(?:FN|A|L|LOCAL))*)\b")
MEMBER = re.compile(r"^\s*(?:Sen|Rep)\.\s")

# What a time line says it is, most specific first. Anything that matches none
# of these and names a bill is a public hearing -- see the docstring.
STATED = [
    (re.compile(r"^public hearing\b", re.I), "public hearing"),
    (re.compile(r"^continued public hearing\b", re.I), "public hearing"),
    (re.compile(r"^executive session\b", re.I), "executive session"),
    (re.compile(r"^continued executive session\b", re.I), "executive session"),
    (re.compile(r"^full committee work session\b", re.I),
     "full committee work session"),
    (re.compile(r"^division work session\b", re.I), "division work session"),
    (re.compile(r"^subcommittee work session\b", re.I),
     "subcommittee work session"),
    (re.compile(r"^work session\b", re.I), "work session"),
    (re.compile(r"^regular meeting\b", re.I), "regular meeting"),
    (re.compile(r"^organizational meeting\b", re.I), "organizational meeting"),
    (re.compile(r"^continued\b", re.I), "continued"),
]

HYPHEN = re.compile(r"([A-Za-z]{2,})-\n\s+([a-z]{2,})")
# The same break inside a shouted header, where the continuation is
# capitals too: "PERFLUORI-" / "NATED CHEMICALS", which otherwise left
# a committee called "Nated Chemicals". Kept as its own rule because a
# join is only safe when BOTH sides are capitals -- a lower-case word
# followed by a capital is "RSA 415:6-E" and must not be welded.
HYPHEN_CAPS = re.compile(r"\b([A-Z]{2,})-\n\s*([A-Z]{2,})")


def normalise(text, running):
    """The pages taken apart, the running heads dropped, the words rejoined.

    Splitting on the form feed rather than on the head's spelling: the head is
    written two ways on facing pages and does not always extract at all, and
    172 pages are blank. Dropping the first line unconditionally would have
    deleted nine lines of real business across the House archive.
    """
    pages = text.split("\x0c")
    out = [pages[0]]
    for p in pages[1:]:
        lines = p.split("\n")
        for i, l in enumerate(lines):
            if not l.strip():
                continue
            flat = l.replace(" ", "").upper()
            if running in flat or re.fullmatch(r"\d{1,4}", l.strip()):
                lines = lines[:i] + lines[i + 1:]
            break
        out.append("\n".join(lines))
    joined = "\x0c".join(out).replace("\x0c", "\n")
    # "manufac-\n     tured" is one word; "sixty-day" and "RSA 415:6-e" are
    # not, which is why only a lower-case continuation is rejoined.
    joined = HYPHEN.sub(r"\1\2", joined)
    return HYPHEN_CAPS.sub(r"\1\2", joined)


def section(text, head, ends):
    """The block under the section heading, up to whatever heading follows.

    Two files carry a full meetings section with NO heading over it at all --
    2023's HC010 (129 entries) and 2025's HC011 (67 committee blocks) -- and a
    heading-anchored reader returns zero for them and exits successfully. So
    where the heading is absent the section is found by its content instead:
    the first day heading that is followed by a committee block.
    """
    m = re.search(rf"^\s*{re.escape(head)}S?\s*$", text, re.M)
    if m:
        rest = text[m.end():]
    else:
        d = None
        for cand in DAY.finditer(text):
            after = text[cand.end():cand.end() + 400]
            if any(SHOUT.match(l.strip()) for l in after.split("\n")):
                d = cand
                break
        if not d:
            return ""
        rest = text[d.start():]
    stop = len(rest)
    for e in ends:
        mm = re.search(rf"^\s*{re.escape(e)}\s*$", rest, re.M)
        if mm:
            stop = min(stop, mm.start())
    return rest[:stop]


def pub_date(text, chamber="H"):
    rx = SENATE_PUBDATE if chamber == "S" else PUBDATE
    for m in rx.finditer(text[:4000] if chamber == "S" else text[:6000]):
        mo = MONTHS.get(m.group(1).lower())
        if mo:
            return (int(m.group(3)), mo, int(m.group(2)))
    return None


def _day_date(mon, day, stated_year, pub, weekday=None):
    """A day heading's date. The House states no year on any of its 2,000-odd
    headings, so it comes from the masthead -- and the December calendars list
    January meetings, which a naive read files a whole year early AND, since
    bill numbers repeat every two years, into the wrong term.

    THE WEEKDAY IS A FREE CHECKSUM. The heading says "TUESDAY, JANUARY 13", so
    the year that makes that a Tuesday is the year. Measured on 2025: all 617
    in-year headings and all 22 that roll into 2026 resolve with no ambiguity.
    """
    import datetime
    mo = MONTHS.get(mon.lower())
    if not mo:
        return None
    if stated_year:
        try:
            return datetime.date(int(stated_year), mo, day).isoformat()
        except ValueError:
            return None
    want = WEEKDAYS.index(weekday.lower()) if weekday else None

    # AND THE MASTHEAD OUTRANKS IT WHEN THE TWO DISAGREE. House Calendar 68A
    # of 1998 heads a section "THURSDAY, AUGUST 28". August 28 was a Friday in
    # 1998 and a Thursday in 1997, so the checksum alone read a hearing on
    # SB 409 as happening eleven months BEFORE the calendar that announced it.
    # The weekday is a typo in the source; the year on the masthead is not.
    #
    # So a candidate that lands before the calendar was printed is not
    # considered. Thirty days of slack, because a heading occasionally
    # continues a session recessed from the week before and the December
    # calendars legitimately roll into January.
    try:
        printed = datetime.date(*pub)
    except (TypeError, ValueError):
        printed = None
    floor = printed - datetime.timedelta(days=30) if printed else None

    ok = []
    for y in (pub[0], pub[0] + 1, pub[0] - 1):
        try:
            d = datetime.date(y, mo, day)
        except ValueError:
            continue
        if floor and d < floor:
            continue
        ok.append(d)
    for d in ok:
        if want is None or d.weekday() == want:
            return d.isoformat()
    # No year makes the stated weekday true. The heading is still a real day
    # in a real calendar, so it takes the earliest year the masthead allows
    # rather than being dropped -- a hearing with a right date and a wrong
    # weekday beats no hearing at all.
    return ok[0].isoformat() if ok else None


def _name(s):
    """"WAYS AND    MEANS" -> "Ways and Means". The extra spaces are the PDF's,
    and the small words are lower case because a committee is a name and not a
    shout."""
    s = re.sub(r"\s*\(RSA[^)]*\)", "", s)
    s = re.sub(r"\s{2,}", " ", s).strip(" ,")
    out = s.title()
    for w in ("And", "Of", "On", "The", "For", "To", "In"):
        out = re.sub(rf"(?<! )\b{w}\b", w.lower(), out)
        out = re.sub(rf"(?<=\w )\b{w}\b", w.lower(), out)
    return out[:1].upper() + out[1:]


def _room(tail):
    """"Room 232, GP" -> "GP 232", which is how the docket writes it. Anything
    else is an address and is kept verbatim."""
    m = ROOM.match(tail.strip())
    if m:
        return f"{m.group(2).upper()} {m.group(1)}", ""
    return "", tail.strip()


def _bills(s):
    out = []
    for m in BILL.finditer(s):
        out.append(f"{m.group(1).upper()}{int(m.group(2))}")
    seen, uniq = set(), []
    for b in out:
        if b not in seen:
            seen.add(b)
            uniq.append(b)
    return uniq


def parse(text, chamber):
    """Every meeting the section announces, one row per (meeting, bill)."""
    conf = CHAMBERS[chamber]
    pub = pub_date(text, chamber)
    if not pub:
        return [], None, []
    body = section(normalise(text, conf["running"]), conf["head"], conf["ends"])
    if not body.strip():
        return [], pub, []

    rows = []
    unpaired = []
    date = committee = room = venue = None
    pending = []            # time lines whose committee header is above them

    def flush(when, rest):
        if not (date and committee and when):
            return
        # THE CALENDAR IS TWO COLUMNS AND THEY SLIP. About one time line in
        # eight either has nothing after it at all or begins mid-sentence --
        # "ties for the use of school districts" -- because the extractor
        # emitted the time column and the text column out of step. Every field
        # of such a row is populated and the row validates; the meeting is
        # simply listed at an hour nobody scheduled it for, and the bill that
        # held that slot loses its time. There is no way to repair the pairing
        # from the text, so these are counted and dropped rather than
        # published at an hour the record does not support.
        body_ = rest.strip()
        if not body_ or (body_[:1].islower() and body_.split(" ")[0].lower()
                         not in ("and", "or")):
            unpaired.append((date, committee, when, body_[:40]))
            return
        kind = next((k for rx, k in STATED if rx.match(rest.strip())), "")
        bills = _bills(rest)
        if not kind:
            # Nothing said what it is and a bill is named: a public hearing.
            # Checked against the docket on every --check run.
            kind = "public hearing" if bills else "other"
        for b in (bills or [""]):
            rows.append({"date": date, "committee": committee, "room": room,
                         "venue": venue, "time": when, "kind": kind,
                         "bill": b, "body": chamber})

    lines = body.split("\n")
    i = 0
    while i < len(lines):
        raw = lines[i]
        line = raw.rstrip()
        i += 1
        if not line.strip():
            continue
        d = DAY.match(line)
        if d:
            date = _day_date(d.group(2), int(d.group(3)), d.group(4), pub,
                             weekday=d.group(1))
            committee = room = venue = None
            continue
        if MEMBER.match(line):
            continue                      # the Senate names its members
        t = TIME.match(line)
        if t:
            hh, mm, ap = int(t.group(1)), t.group(2), t.group(3).lower()
            if ap == "p" and hh != 12:
                hh += 12
            elif ap == "a" and hh == 12:
                hh = 0
            when = f"{hh:02d}:{mm}"
            # A wrapped entry continues on deeply indented lines beneath. But
            # THE CALENDAR IS SET IN TWO COLUMNS and they do not always line
            # up: times on the left, business on the right, and a committee's
            # closing "Executive session on HB 67; HB 340; HB 160" lands under
            # the last hearing of the morning at the same indent as a wrapped
            # title. Welded on, it turned that hearing into a public hearing
            # on three bills it was not hearing, at a time none of them had.
            #
            # So a continuation line that states its OWN business ends the
            # entry and opens another at the same time. That is the whole
            # difference between a title that ran over and a second item.
            segs = [rest_seg := t.group(4)]
            while i < len(lines):
                nxt = lines[i]
                if not nxt.strip():
                    i += 1
                    continue
                if TIME.match(nxt) or DAY.match(nxt) or SHOUT.match(nxt.strip()):
                    break
                if len(nxt) - len(nxt.lstrip()) < 12:
                    break
                stripped_next = nxt.strip()
                if any(rx.match(stripped_next) for rx, _ in STATED):
                    segs.append(stripped_next)
                else:
                    segs[-1] += " " + stripped_next
                i += 1
            for seg in segs:
                flush(when, seg)
            continue
        stripped = line.strip()
        if SHOUT.match(stripped):
            # A HEADER WRAPS, AND ONLY ITS NAME IS SHOUTED. "WAYS AND MEANS,
            # Room 159, GP" is not an upper-case line -- "Room" is not -- and
            # requiring the whole line to be upper case silently skipped it,
            # which left every bill it heard filed under whichever commission
            # was announced above it. So the NAME is the test, and the rest of
            # the header is whatever follows until a time line.
            buf = [stripped]
            while i < len(lines):
                nxt = lines[i]
                if not nxt.strip():
                    break
                if TIME.match(nxt) or DAY.match(nxt) or MEMBER.match(nxt):
                    break
                buf.append(nxt.strip())
                i += 1
            whole = re.sub(r"\s{2,}", " ", " ".join(buf))
            h = HEADER.match(whole)
            if h:
                committee = _name(h.group(1))
                room, venue = _room(h.group(2))
            else:
                committee = _name(whole)
                room, venue = "", ""
            continue
    return rows, pub, unpaired


UNPAIRED = []


def load(chamber, limit=None):
    conf = CHAMBERS[chamber]
    root = Path(conf["dir"])
    if not root.exists():
        return []
    files = sorted(root.rglob(conf["glob"]))
    if limit:
        files = files[:limit]
    out = []
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        rows, pub, unpaired = parse(text, chamber)
        UNPAIRED.extend(unpaired)
        if not rows:
            continue
        noticed = f"{pub[0]:04d}-{pub[1]:02d}-{pub[2]:02d}" if pub else ""
        for r in rows:
            r["noticed"] = noticed
            # HC010 exists in 2023, 2024, 2025 and 2026. Keyed on the
            # stem alone the four collapse into one, which had this
            # reporting 57 calendars where 161 had parsed.
            r["calendar"] = f"{f.parent.name}/{f.stem}"
        out.extend(rows)
    return out


# ------------------------------------------------------------------ scoring
DOCKET = re.compile(
    r"^\s*(Public Hearing|Executive Session|Full Committee Work Session|"
    r"Subcommittee Work Session|Division Work Session|Work Session)\s*:\s*"
    r"(\d{2})/(\d{2})/(\d{4})(?:\s+(\d{1,2}):(\d{2})\s*([ap])m)?\s*(.*)$", re.I)


def docket_truth(path="Docket.txt"):
    """What the docket says for itself: {(bill, date): {kind: (time, room)}}.

    A dict of kinds and not one kind, because a committee routinely takes a
    bill in public hearing and goes into executive session on it in the SAME
    slot, and the docket records both:

        HB267  Public Hearing:    01/16/2025 01:30 pm LOB 306-308
        HB267  Executive Session: 01/16/2025 01:30 pm LOB 306-308

    Keyed on (bill, date) alone the second overwrote the first, and 717 rows
    the calendar had read correctly as public hearings were being scored as
    wrong against a ground truth that had forgotten the hearing. A lossy key
    in the thing you measure against is worse than no measurement, because it
    reads as a failing parser.
    """
    truth = {}
    p = Path(path)
    if not p.exists():
        return truth
    for line in p.read_text(encoding="utf-8", errors="replace").split("\n"):
        parts = line.split("|")
        if len(parts) < 7:
            continue
        m = DOCKET.match(parts[5].strip())
        if not m:
            continue
        bill = parts[3].strip().upper()
        date = f"{m.group(4)}-{m.group(2)}-{m.group(3)}"
        when = ""
        if m.group(5):
            hh = int(m.group(5))
            if m.group(7).lower() == "p" and hh != 12:
                hh += 12
            elif m.group(7).lower() == "a" and hh == 12:
                hh = 0
            when = f"{hh:02d}:{m.group(6)}"
        truth.setdefault((bill, date), {})[m.group(1).lower()] = (
            when, m.group(8).strip())
    return truth


def check(rows):
    truth = docket_truth()
    if not truth:
        return {"note": "Docket.txt is not here, so nothing can be scored"}
    got = [r for r in rows if r["bill"]]
    known = [r for r in got if (r["bill"], r["date"]) in truth]
    # EACH FIGURE OVER ITS OWN DENOMINATOR. Time and room were first reported
    # over every row the docket knew, which counted a study commission meeting
    # at a street address as a room disagreement because neither side stated a
    # room code. That read as 78% when the real number of rooms the two
    # sources name differently is three.
    kind_ok = time_ok = time_n = room_ok = room_n = 0
    kind_bad, room_bad = Counter(), []
    for r in known:
        rec = truth[(r["bill"], r["date"])]
        if r["kind"] in rec:
            kind_ok += 1
            when, loc = rec[r["kind"]]
        else:
            kind_bad[f"{r['kind']} -> {'/'.join(sorted(rec))}"] += 1
            when, loc = next(iter(rec.values()))
        if when and r["time"]:
            time_n += 1
            time_ok += r["time"] == when
        if r["room"] and loc:
            room_n += 1
            if r["room"].split()[0] in loc:
                room_ok += 1
            elif len(room_bad) < 5:
                room_bad.append(f"{r['bill']} {r['date']}: "
                                f"{r['room']!r} vs docket {loc!r}")

    def pct(n, d):
        return f"{n:,} of {d:,} ({n / d:.0%})" if d else "none to compare"

    return {"rows": f"{len(rows):,}",
            "with a bill": f"{len(got):,}",
            "the docket also knows": f"{len(known):,}",
            "kind agrees": pct(kind_ok, len(known)),
            "time agrees, where both state one": pct(time_ok, time_n),
            "room agrees, where both state one": pct(room_ok, room_n),
            "kind disagreements": kind_bad.most_common(6),
            "room disagreements": room_bad}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--show", type=int, default=0)
    ap.add_argument("--out", default="")
    ap.add_argument("--chamber", choices=["H", "S", "both"], default="both")
    a = ap.parse_args()

    chambers = ["H", "S"] if a.chamber == "both" else [a.chamber]
    rows = []
    for ch in chambers:
        got = load(ch, limit=a.show or None)
        print(f"{ch}: {len(got):,} rows from {len({r['calendar'] for r in got})} calendars")
        rows.extend(got)

    if a.show:
        for r in rows[:60]:
            print(f"  {r['date']} {r['time']} {r['kind']:26} "
                  f"{(r['bill'] or '-'):10} {r['room'] or r['venue'][:28]:28} "
                  f"{r['committee']}")
        return

    by_kind = Counter(r["kind"] for r in rows)
    print("\nby kind:")
    for k, n in by_kind.most_common():
        print(f"  {n:7,}  {k}")
    print(f"\n{len({(r['bill'], r['date']) for r in rows if r['bill']}):,} "
          "distinct (bill, day) pairs")
    print(f"{len({r['committee'] for r in rows}):,} committees, "
          f"{len({r['date'] for r in rows}):,} meeting days")

    if a.check:
        print("\nagainst the docket, which nothing here wrote:")
        for k, v in check(rows).items():
            print(f"  {k}: {v}")

    if a.out:
        Path(a.out).write_text(json.dumps(rows, indent=1), encoding="utf-8")
        print(f"\n-> {a.out}")


if __name__ == "__main__":
    main()
