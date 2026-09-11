#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.7
"""
Parse the NH General Court Docket.txt bulk dump into normalized "scheduled
proceedings" -- the input to video alignment.

Source: https://gc.nh.gov/dynamicdatadump/Docket.txt  (pipe-delimited, no header)

Field layout (positional, inferred -- see VERIFY notes in the design doc):
  0  lsr_year     pairs with field 1 to form the LSR id. NOT reliably the
                  session year: SB11 -> 2025 and SB15 -> 2026 were both
                  introduced 01/08/2025.
  1  lsr_number   zero-padded 4 digits
  2  created      timestamp the docket row was written
  3  bill         e.g. HB84, SB4, CACR2, HR6
  4  body         H | S
  5  description  free text, the only place scheduling data lives
  6  updated      timestamp the row was last modified
"""

import csv
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, date, time
from pathlib import Path

# --------------------------------------------------------------------------
# Description grammar
# --------------------------------------------------------------------------

# ==CANCELLED==, ==RECESSED==, ==ROOM CHANGE==, ==TIME CHANGE== ...
FLAG_RE = re.compile(r"==\s*([A-Z][A-Z ]*?)\s*==")

# House:  "Public Hearing: 01/13/2025 10:30 am LOB 301-303"
#         "Executive Session: 01/23/2025 01:40 pm LOB 301-303"
#         "Subcommittee Work Session: 01/22/2025 01:15 am LOB 302-304"
HOUSE_SCHED_RE = re.compile(
    r"(?P<kind>Public Hearing|Executive Session|Subcommittee Work Session|"
    r"Full Committee Work Session|Work Session|Committee of Conference)\s*:\s*"
    r"(?P<date>\d{1,2}/\d{1,2}/\d{4})"
    r"(?:\s+(?P<time>\d{1,2}:\d{2}\s*[ap]m))?"
    # The venue stops before a journal citation. A House line can end
    # "LOB 210-211 HC 19 P. 16" -- room, then House Calendar 19 page 16 -- and
    # a venue pattern that accepts letters, digits and spaces swallows the
    # citation whole, so the site printed a room number with a page reference
    # stuck to it.
    r"(?:\s+(?P<venue>[A-Za-z0-9 .\-]+?))?"
    r"(?:\s+(?P<cite>(?:HC|SC|HJ|SJ)\s*\d+\s*(?:P\.?\s*\d+)?))?\s*$",
    re.IGNORECASE,
)

# Senate: "Hearing: 01/14/2025, Room 103, LOB, 09:30 am;  SC 5"
SENATE_SCHED_RE = re.compile(
    r"(?P<kind>Hearing|Executive Session|Work Session)\s*:\s*"
    r"(?P<date>\d{1,2}/\d{1,2}/\d{4}),\s*"
    # The room is not always a number: "Room Map Room, SL, 09:30 am". A row
    # that does not parse here never becomes a Proceeding at all, so it is
    # absent from verification_manifest.csv and can never be matched to a
    # recording. Losing a hearing is quieter and worse than misparsing one.
    r"Room\s+(?P<room>[\w][\w .\-]*?),\s*(?P<bldg>[A-Za-z]+),\s*"
    r"(?P<time>\d{1,2}:\d{2}\s*[ap]m)",
    re.IGNORECASE,
)

# THE ARCHIVE'S OWN SHORTHAND, 1989-1998.
#
#   HEARING   02/08/89       10:00 REP HALL  FOR: EXEC DEPTS & ADM
#   HEARING MAR17 08:30 RM101,LOB    FOR: TRANSPORTATION
#   RESCHEDULED HEARING 3/06/90 10:00  RM209LOB FOR: EDUCATION
#   COMMERCE HEARING SECS.5-14 MAR24 01:30 RM207,LOB
#
# 15,401 lines mention a hearing across those ten terms and 14,836 carry a
# date and a time -- 96%. Nothing else on this disk has them: the calendars
# start in 1997 and the video starts in 2020, so for eight of these ten terms
# this line is the only record that a bill was ever heard.
#
# A DATE AND A TIME MUST FOLLOW THE WORD, which is what keeps "SEN RUSSMAN
# SUSP RULES FOR HEARING, MA 2/3VV; SJ15,P371" from becoming a hearing.
LEGACY_SCHED_RE = re.compile(
    # Up to ten characters of padding, because the clerk aligned these by eye
    # and "HEARING       02/07/89" carries seven spaces.
    r"\bHEARING\b[^0-9A-Za-z]{0,10}"
    # Three date forms: with a year, without one, and by month name. The
    # yearless ones take their year from the row that announced them.
    r"(?P<date>\d{1,2}\s*/\s*\d{1,2}\s*/\s*\d{2,4}"
    r"|\d{1,2}\s*/\s*\d{1,2}|[A-Z]{3}\s*\d{1,2})"
    # NOON is a time. It is written 39 times and means exactly midday.
    r"\s+(?P<time>\d{1,2}:\d{2}|NOON)"
    r"(?P<rest>.*)$", re.I)
# The committee is named after FOR, with or without its colon, and sometimes
# with the room run into it: "RM105-A,SHFOR: APPROPRIATIONS".
LEGACY_FOR_RE = re.compile(r"FOR\s*:?\s*(?P<committee>[A-Z][^;]*?)\s*$", re.I)
MONTHS = {m: i for i, m in enumerate(
    "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split(), 1)}


def _legacy_date(s, written, session=None):
    """The hearing's date. Two forms, and only one of them states a year.

    "4/5/89" is a date. "MAR17" is not -- it takes its year from the row that
    announced it, which is the only year on the line. A row is written days or
    weeks BEFORE the hearing it announces (02/08 announced on 01/25), so where
    the month-name form would fall well before the row was written, it belongs
    to the following year: a December row announcing a January sitting.
    """
    s = re.sub(r"\s+", "", s or "")
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{2,4})$", s)
    if m:
        mo, dy, yr = (int(x) for x in m.groups())
        two_digit = len(m.group(3)) <= 2
        if yr < 100:
            yr += 1900 if yr >= 60 else 2000
        try:
            got = date(yr, mo, dy)
        except ValueError:
            return None
        # A TWO-DIGIT YEAR IS ONE KEYSTROKE FROM A DIFFERENT DECADE. One row
        # in the 1989-1990 docket reads "HEARING 3/20/99" and was written on
        # 13 March 1990, announcing a hearing the following week; read
        # literally it put a 1990 hearing in 1999. Where the row that
        # announced it is on the record and the stated year is more than a
        # year away from it, the row's own year is taken instead -- and only
        # when that lands the hearing within a year, so a genuinely distant
        # date is kept rather than dragged closer.
        if two_digit and written and abs((got - written.date()).days) > 400:
            try:
                near = date(written.year, mo, dy)
            except ValueError:
                return got
            if abs((near - written.date()).days) <= 400:
                return near
        return got
    # "3/15", a month and a day with no year at all.
    m = re.match(r"(\d{1,2})/(\d{1,2})$", s)
    if m:
        mo, dy = int(m.group(1)), int(m.group(2))
    else:
        m = re.match(r"([A-Za-z]{3})(\d{1,2})$", s)
        if not m or m.group(1).upper() not in MONTHS:
            return None
        mo, dy = MONTHS[m.group(1).upper()], int(m.group(2))
    if not written:
        return None
    # THE ROW'S OWN TIMESTAMP IS NOT ALWAYS SANE. Ten rows of these ten terms
    # carry a written year more than a year from their session year, and one
    # of them -- SB623, "01/06/1904" for a 1994 row -- put a hearing in 1904
    # and invented a 1903-1904 term in proceedings.csv. Where the two
    # disagree, the session year is the better of them: it is the year the
    # docket file is FOR, and it is not a keystroke.
    if session and abs(written.year - session) > 1:
        written = written.replace(year=session)
    try:
        got = date(written.year, mo, dy)
    except ValueError:
        return None
    if (got - written.date()).days < -60:
        try:
            got = date(written.year + 1, mo, dy)
        except ValueError:
            return None
    return got


def _legacy_time(s):
    """The stated time, on a twenty-four hour reading of a twelve-hour clock.

    The old docket writes "01:30" and "10:00" and never says which half of the
    day it means. The modern docket does say, and it settles the convention by
    counting rather than by assumption -- across 31,000 modern hearings:

        1:00 pm 7,196 / am 21      8:00 am    93 / pm  0
        2:00 pm 2,780 / am  4      9:00 am 6,000 / pm  0
        3:00 pm   638 / am  0     10:00 am 11,116 / pm 10
        4:00 pm    63 / am  0     11:00 am  3,439 / pm 15
        12:00 pm  333 / am  3

    So one to six is the afternoon and eight to eleven is the morning, and
    the legacy hours fall in exactly those two clusters: 10:00 is the commonest
    at 4,993 and 1:00 next at 2,242, with nothing between 12 and 1 either way.

    Seven is the one guess on this page. It occurs 15 times in the old docket
    and once in the whole modern one, where it is 7 am -- so it is read as
    morning, on a single instance of evidence, and it is worth knowing that is
    all that stands behind it.
    """
    if (s or "").strip().upper() == "NOON":
        return time(12, 0)
    try:
        h, mi = (int(x) for x in s.split(":"))
    except (ValueError, AttributeError):
        return None
    if not (0 <= mi < 60):
        return None
    if 1 <= h <= 6:
        h += 12
    if not (0 <= h < 24):
        return None
    return time(h, mi)


# Trailing journal/calendar citation: "HJ 2  P. 5", "SJ 3", "SC 7", "HC 5  P. 7".
# Must be stripped BEFORE referral extraction -- flag-cleaning collapses runs of
# whitespace, which destroys the two-space delimiter these rely on. Leaving it in
# makes "Municipal and County Government HJ 2 P. 5" and "... P. 6" look like two
# different committees, which silently splits a shared executive-session cohort
# and upgrades its members to unique-slot confidence.
JOURNAL_TAIL_RE = re.compile(r"\s*(?:HJ|SJ|HC|SC)\s+\d+\b.*$")

# "Introduced 01/08/2025 and referred to Municipal and County Government  HJ 2  P. 5"
# "Introduced 01/08/2025 and Referred to Commerce;  SJ 2"
REFERRAL_RE = re.compile(
    r"[Rr]eferred to\s+(?P<committee>.+?)\s*(?:;|$)"
)


def normalize_committee(name):
    if not name:
        return None
    name = JOURNAL_TAIL_RE.sub("", name)
    name = re.sub(r"\s*\bP\.\s*\d+\b.*$", "", name)   # stray page refs
    name = re.sub(r"\s+", " ", name).strip(" .,;")
    return name or None

# "Vacated and Referred to Finance (Rep. C. McGuire): MA VV 01/08/2025  HJ 2"
VACATED_RE = re.compile(
    r"Vacated and Referred to\s+(?P<committee>.+?)\s*(?:\(|:)"
)

# "Committee Report: Ought to Pass, 01/30/2025, Vote 5-0;  SC 7"
CMTE_REPORT_RE = re.compile(r"Committee Report:\s*(?P<rec>[^,(]+)")

# Effective-date extraction for referral ordering
INTRODUCED_RE = re.compile(r"Introduced(?:\s+\(in recess of\))?\s+(?P<date>\d{1,2}/\d{1,2}/\d{4})")

# A proceeding that produces video. Committee Report does NOT: its date is the
# calendar day the report is *published to the chamber*, not when the committee
# voted. The vote happens in the executive session.
VIDEO_KINDS = {
    "public hearing",
    "hearing",
    "executive session",
    "subcommittee work session",
    "full committee work session",
    "work session",
    "committee of conference",
}


def _parse_time(s):
    """The stated time, or None if the record does not state a usable one.

    ONE BAD ROW MUST NOT END THE RUN. The 2023-2024 docket contains exactly
    one time the twelve-hour clock cannot express -- HB639, "Full Committee
    Work Session: 02/14/2023 00:00 pm LOB 302-304" -- and it raised out of the
    whole of build_manifest, so 1,643 recordings could not be matched against
    23,808 docket lines because of a typo in one of them.

    It is left as None rather than read as noon. Noon is very likely what was
    meant, and "very likely" is not something this project publishes as a
    time. The proceeding keeps its date and loses only the hour."""
    s = s.strip().replace(" ", "").upper()
    try:
        return datetime.strptime(s, "%I:%M%p").time()
    except ValueError:
        return None


def _parse_date(s):
    return datetime.strptime(s.strip(), "%m/%d/%Y").date()


@dataclass
class Proceeding:
    bill: str
    body: str
    lsr: str
    kind: str
    sched_date: str
    sched_time: str | None
    venue: str | None
    flags: list
    committee: str | None
    raw: str
    row_created: str
    row_updated: str
    # filled in by the sitting pass
    sitting_key: str | None = None
    agenda_ordinal: int | None = None
    cohort_size: int = 1
    confidence: str | None = None
    expected_title: str | None = None
    notes: list = field(default_factory=list)


# --------------------------------------------------------------------------
# Pass 1: row -> typed events
# --------------------------------------------------------------------------

def parse_rows(path):
    rows = []
    with open(path, encoding="utf-8-sig") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.rstrip("\n")
            if not line.strip():
                continue
            parts = line.split("|")
            if len(parts) < 7:
                sys.stderr.write(f"skip line {lineno}: {len(parts)} fields\n")
                continue
            rows.append({
                "lsr": f"{parts[0]}-{parts[1]}",
                "created": parts[2],
                "bill": parts[3].strip(),
                "body": parts[4].strip(),
                "desc": parts[5],
                "updated": parts[6],
                "lineno": lineno,
            })
    return rows


def extract_flags(desc):
    flags = [m.group(1).strip() for m in FLAG_RE.finditer(desc)]
    clean = FLAG_RE.sub(" ", desc).strip()
    clean = re.sub(r"\s{2,}", " ", clean)
    return flags, clean


def build_referral_timeline(rows):
    """bill -> sorted [(effective_date, committee)] from referral + vacate rows."""
    timeline = defaultdict(list)
    for r in rows:
        _, clean = extract_flags(r["desc"])
        m_vac = VACATED_RE.search(clean)
        if m_vac:
            d = INTRODUCED_RE.search(clean)
            eff = _parse_date(d.group("date")) if d else None
            if eff is None:
                m2 = re.search(r"(\d{1,2}/\d{1,2}/\d{4})", clean)
                eff = _parse_date(m2.group(1)) if m2 else date.min
            timeline[r["bill"]].append((eff, normalize_committee(m_vac.group("committee")), "vacated"))
            continue
        if "Vacated" in clean:
            continue
        m_ref = REFERRAL_RE.search(clean)
        if m_ref and INTRODUCED_RE.search(clean):
            eff = _parse_date(INTRODUCED_RE.search(clean).group("date"))
            timeline[r["bill"]].append((eff, normalize_committee(m_ref.group("committee")), "introduced"))
    for b in timeline:
        # vacated sorts after introduced on the same date
        timeline[b].sort(key=lambda t: (t[0], 0 if t[2] == "introduced" else 1))
    return timeline


def committee_on(timeline, bill, when):
    """Which committee held the bill on a given date."""
    entries = timeline.get(bill, [])
    current = None
    for eff, cmte, _ in entries:
        if eff <= when:
            current = cmte
        else:
            break
    return current or (entries[0][1] if entries else None)


def _legacy_committee(raw):
    """"EXEC DEPTS & ADM" as a committee's name, or None."""
    if not raw:
        return None
    try:
        import referrals
    except ImportError:
        return normalize_committee(raw)
    got = referrals.committee("INTRODUCED AND REF TO " + raw)
    return got or normalize_committee(raw)


def parse_proceedings(rows, timeline):
    out = []
    for r in rows:
        flags, clean = extract_flags(r["desc"])
        m = SENATE_SCHED_RE.search(clean) if r["body"] == "S" else None
        if m:
            kind = m.group("kind").lower()
            venue = f"{m.group('bldg').upper()} {m.group('room')}"
        else:
            m = HOUSE_SCHED_RE.search(clean)
            if m:
                kind = m.group("kind").lower()
                venue = (m.group("venue") or "").strip() or None
            else:
                m = LEGACY_SCHED_RE.search(clean)
                if not m:
                    continue
                kind = "hearing"
                rest = m.group("rest") or ""
                fm = LEGACY_FOR_RE.search(rest)
                venue = (rest[:fm.start()] if fm else rest).strip(" .,:") or None
                legacy_cmte = fm.group("committee").strip() if fm else None

        if kind not in VIDEO_KINDS:
            continue

        legacy = m.re is LEGACY_SCHED_RE
        if legacy:
            written = None
            try:
                written = datetime.strptime(r["created"].strip(),
                                            "%m/%d/%Y %I:%M:%S %p")
            except ValueError:
                try:
                    written = datetime.strptime(r["created"].strip()[:10],
                                                "%m/%d/%Y")
                except ValueError:
                    written = None
            session = None
            head = (r.get("lsr") or "").split("-")[0]
            if head.isdigit():
                session = int(head)
            d = _legacy_date(m.group("date"), written, session)
            if d is None:
                continue
            t = _legacy_time(m.group("time"))
        else:
            legacy_cmte = None
            d = _parse_date(m.group("date"))
            t = _parse_time(m.group("time")) if m.group("time") else None

        p = Proceeding(
            bill=r["bill"], body=r["body"], lsr=r["lsr"], kind=kind,
            sched_date=d.isoformat(),
            sched_time=t.strftime("%H:%M") if t else None,
            venue=venue, flags=flags,
            # The legacy line names its own committee -- "FOR: EXEC DEPTS
            # & ADM" -- which is a better answer than the referral timeline,
            # because that timeline is built from "Introduced ... and referred
            # to", and the clerk of 1989 wrote "INTRODUCED AND REF TO". The
            # name is expanded through referrals, which knows the General
            # Court's own key to its shorthand.
            committee=(_legacy_committee(legacy_cmte)
                       or committee_on(timeline, r["bill"], d)),
            raw=r["desc"].strip(), row_created=r["created"], row_updated=r["updated"],
        )

        if t and t.hour < 8:
            p.notes.append(
                f"time {t.strftime('%I:%M %p').lower()} is outside normal hearing "
                "hours - likely am/pm data entry error"
            )
        if not p.committee:
            p.notes.append("no referral row found in input; committee unresolved")
        out.append(p)
    return out


# --------------------------------------------------------------------------
# Pass 2: group into sittings, assign ordinals and confidence
# --------------------------------------------------------------------------

def build_sittings(procs):
    """A sitting = one committee meeting in one room on one day.

    Keyed on (committee, date, venue) rather than room alone, because a
    committee moves rooms between days and two committees share a room on
    different days.
    """
    sittings = defaultdict(list)
    for p in procs:
        if "CANCELLED" in p.flags:
            p.confidence = "X-cancelled"
            p.notes.append("cancelled; no video expected for this row")
            continue
        key = f"{p.committee or 'UNKNOWN'}|{p.sched_date}|{p.venue or 'UNKNOWN'}"
        p.sitting_key = key
        sittings[key].append(p)

    for key, group in sittings.items():
        # An executive session is a distinct block within the day even when it
        # shares a room with that morning's hearings, so ordinal is computed
        # per (kind, time) within the sitting.
        by_time = defaultdict(list)
        for p in group:
            by_time[(p.kind, p.sched_time)].append(p)

        ordered = sorted(by_time.keys(), key=lambda k: (k[1] or "99:99", k[0]))
        for idx, k in enumerate(ordered, 1):
            cohort = by_time[k]
            for p in cohort:
                p.agenda_ordinal = idx
                p.cohort_size = len(cohort)
                if p.sched_time is None:
                    p.confidence = "D-no-time"
                elif len(cohort) == 1:
                    p.confidence = "A-unique-slot"
                else:
                    p.confidence = "C-shared-slot"
                    p.notes.append(
                        f"{len(cohort)} bills share this slot "
                        f"({', '.join(sorted(x.bill for x in cohort))}); "
                        "running order not recoverable from docket"
                    )
                if "RECESSED" in p.flags:
                    p.notes.append(
                        "RECESSED flag: proceeding continued to a later date that "
                        "this row does not state; actual video date unconfirmed"
                    )
    return sittings


HOUSE_TITLE = "House {committee} ({date})"


def attach_expected_titles(procs):
    for p in procs:
        if p.body == "H" and p.committee:
            d = datetime.fromisoformat(p.sched_date).strftime("%m/%d/%Y")
            p.expected_title = HOUSE_TITLE.format(committee=p.committee, date=d)
        else:
            p.expected_title = None  # Senate convention not yet verified


# --------------------------------------------------------------------------

def main(inp, outdir):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    rows = parse_rows(inp)
    timeline = build_referral_timeline(rows)
    procs = parse_proceedings(rows, timeline)
    sittings = build_sittings(procs)
    attach_expected_titles(procs)

    procs.sort(key=lambda p: (p.sched_date, p.sched_time or "99:99", p.bill))

    with open(outdir / "proceedings.json", "w") as fh:
        json.dump([asdict(p) for p in procs], fh, indent=2)

    cols = ["bill", "body", "lsr", "committee", "kind", "sched_date", "sched_time",
            "venue", "agenda_ordinal", "cohort_size", "confidence",
            "expected_title", "flags", "notes", "raw"]
    with open(outdir / "proceedings.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for p in procs:
            d = asdict(p)
            d["flags"] = "; ".join(d["flags"])
            d["notes"] = " | ".join(d["notes"])
            w.writerow(d)

    tally = defaultdict(int)
    for p in procs:
        tally[p.confidence] += 1
    print(f"rows in           : {len(rows)}")
    print(f"proceedings out   : {len(procs)}")
    print(f"distinct sittings : {len(sittings)}")
    print(f"bills w/ referral : {len(timeline)}")
    print("confidence tiers  :")
    for k in sorted(tally):
        print(f"  {k:16s} {tally[k]}")
    return procs


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data/docket_sample.txt",
         sys.argv[2] if len(sys.argv) > 2 else "out")
