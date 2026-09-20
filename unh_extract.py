#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-19.3
"""
Turn repaired journal text into rows: one per member, per vote. No network.

    python3 unh_extract.py --all              # every repaired volume
    python3 unh_extract.py journalofhouseof1991newh
    python3 unh_extract.py --all --summary    # counts only, write nothing

Writes two files:

    data/unh/rollcalls.csv    one row per member per roll call
    data/unh/members.csv      everyone those rows name, and how they are keyed

WHO A MEMBER IS, WHEN THE GENERAL COURT HAS NO NUMBER FOR THEM

Granite Record keys a legislator on the General Court's employee number.
careers.json and rollcalls/RollCallHistory_<year>.txt are both built on it.
That works back only as far as the General Court's own records reach:
past_members.json covers a good deal of the 1990s, and the scanned journals
run to 1881, so the further back this goes the more people there are who have
no employee number anywhere because the numbering postdates them.

Those people are given an identifier of their own kind rather than one that
could be mistaken for the General Court's:

    201723                    a General Court employee number, used as is
    NHA-H-CLEMONS-JANE        minted here, for someone the General Court's
                              own list does not carry

The two never share a space and neither is converted into the other, because
a collision would quietly attribute an archived vote to a modern legislator.
The minted form is deterministic -- the same person gets the same identifier
on every run -- and legible on purpose, so that a wrong one is obvious in a
way a hash would not be.

WHAT A ROW CAN AND CANNOT SAY

The name and the vote are what this is for and they are the best-measured
part: 96.81% agreement with the General Court's own journals on a volume the
extraction was never fitted to. Two fields are weaker and are left empty
rather than guessed:

  the BILL is the nearest bill number printed before the roll call, within
  LOOKBACK lines. Most roll calls are on a bill and some are on a rule or a
  procedural motion, where the nearest bill number belongs to other business
  entirely -- so a roll call with no bill number close above it gets none.

  the DATE comes from the sitting-day heading the roll call falls under. A
  volume that prints no such heading, or a roll call before the first one,
  gets none.
"""

import argparse
import bisect
import csv
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import unh_measure as M
import unh_repair as R

REPAIRED = Path("data/unh/repaired")
OUT = Path("data/unh")
PAST_MEMBERS = Path("past_members.json")

LOOKBACK = 40           # lines above a roll call to look for its bill

# "HOUSE JOURNAL No. 11" / "SENATE JOURNAL 27 MARCH 2003"
DAY = re.compile(r"^\s*(HOUSE|SENATE)\s+JOURNAL\s+(?:No\.\s*)?(\d+)", re.I)
# "Wednesday, January 29, 1997" -- the line under a House day heading.
DATE = re.compile(r"^\s*(?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day,?\s+"
                  r"([A-Z][a-z]+)\s+(\d{1,2}),?\s+(\d{4})\s*$")
HEAD_DATE = re.compile(r"\b(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})\b")
BILL = re.compile(r"\b((?:HB|SB|CACR|HR|SR|HCR|SCR|HJR|SJR)\s*\d+)\b")
MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], 1)}

COLS = ["term", "year", "body", "journal", "date", "bill", "yeas", "nays",
        "member_id", "name", "vote", "volume", "page"]
MEMBER_COLS = ["member_id", "source", "body", "name", "surname", "given",
               "votes", "first_year", "last_year"]


def term_of(year, month):
    """The biennium a sitting belongs to.

    December rolls forward: the House organises in the December before its
    first session, so 4 December 1996 is the opening day of 1997-1998 and not
    the tail of 1995-1996.
    """
    if month == 12:
        year += 1
    start = year if year % 2 else year - 1
    return f"{start}-{start + 1}"


def gencourt_numbers():
    """{(body, surname, given): (number, name)}, from the General Court's list.

    KEYED ON THE CHAMBER, because the list says which one and throwing that
    away merges people. Every entry begins "Rep." or "Sen.", and without it a
    Senate "J. King" resolved to the House's John King: one record, 634 votes,
    both chambers, two men. The Senate prints surnames alone and leans on an
    initial only where it has two of the same name, so its names are exactly
    the ones with least to distinguish them and most need of this.

    A member who served in both chambers appears in the list twice and keeps
    both records, which is the right shape -- joining them is a judgment about
    a person, not a lookup.
    """
    if not PAST_MEMBERS.exists():
        return {}
    try:
        rows = json.loads(PAST_MEMBERS.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out = {}
    for number, text in (rows.items() if isinstance(rows, dict) else []):
        m = R.AUTHORITY_LINE.match(str(text).strip())
        if not m:
            continue
        given = m.group(3).strip().split()
        if not given:
            continue
        body = "S" if m.group(1).lower().startswith("sen") else "H"
        out.setdefault((body, R.key(m.group(2)), R.key(given[0])),
                       (str(number), f"{m.group(2).strip()}, {m.group(3).strip()}"))
    return out


#
# THE SEAT LOOKS LIKE A BETTER KEY THAN THE NAME, AND IS NOT. Tried and
# measured before being believed: past_members.json prints the seat --
# "Rep. Emerton, Larry(Hills 07)" -- and the rosters read out of the journals
# carry county and district too, so a surname plus a seat should pin a person
# where a nickname defeats the given name.
#
# Across the rosters, 1,289 people resolve by BOTH the name and the seat. The
# two agree on 1,198 and DISAGREE ON 91 -- the seat points at a different
# employee number seven times in a hundred -- while resolving only 28 people
# the name cannot. Kenneth J. MacDonald of Carroll 6 is two different men,
# decades apart, because districts are renumbered at every redistricting and
# a seat is not the same place twice.
#
# So it is not used. It would buy 28 joins at the price of 91 wrong ones, and
# a vote on the wrong member is the worst thing this project can publish.
# --unresolved writes the evidence out for a person to weigh instead.


def mint(body, surname, given):
    """An identifier for someone the General Court has no number for.

    Deterministic and readable. NHA for the archive, then the chamber, then
    the name as printed -- so that a wrong one is visible on inspection, and
    so that it cannot be mistaken for an employee number, which is six digits.
    """
    def slug(s):
        return re.sub(r"[^A-Z]", "", (s or "").upper()) or "X"
    return f"NHA-{body}-{slug(surname)}-{slug(given)}"


def lines_with_offsets(text):
    out, pos = [], 0
    for line in text.split("\n"):
        out.append((pos, line))
        pos += len(line) + 1
    return out


def head_pages(identifier, rows):
    """(offset, leaf) checkpoints, so a row can name the page it came from.

    Without this a person checking a roll call has the text and no way to see
    the page it was read off, which is most of what checking one means. The
    reflow's sidecar already records which leaf each running head sat on.
    """
    side = REPAIRED.parent / "reflow" / f"{identifier}.heads.tsv"
    if not side.exists():
        return []
    out = []
    with side.open(encoding="utf-8", errors="replace") as f:
        for row in f:
            if row.startswith("#") or row.startswith("line\t"):
                continue
            parts = row.rstrip("\n").split("\t")
            if len(parts) < 3:
                continue
            try:
                line, leaf = int(parts[0]), int(parts[1])
            except ValueError:
                continue
            if line < len(rows):
                out.append((rows[line][0], leaf))
    return sorted(out)


def head_dates(identifier, rows):
    """Dates read off the running heads the reflow set aside.

    The House prints its sitting date in the body, under a day heading. The
    Senate does not: its only statement of the date is the running head --
    "SENATE JOURNAL 7 DECEMBER 1994" -- which unh_rollcalls.py drops from the
    text because in the House the same furniture lands inside vote lists and
    a name can be read out of it. Dropped and forgotten, every Senate roll
    call came out undated, all 13,545 of them. The reflow now writes the
    heads to a sidecar keyed by line, and this reads them back.
    """
    side = REPAIRED.parent / "reflow" / f"{identifier}.heads.tsv"
    if not side.exists():
        return []
    out = []
    with side.open(encoding="utf-8", errors="replace") as f:
        for row in f:
            if row.startswith("#") or row.startswith("line\t"):
                continue
            parts = row.rstrip("\n").split("\t")
            if len(parts) < 3:
                continue
            try:
                line = int(parts[0])
            except ValueError:
                continue
            m = HEAD_DATE.search(parts[2])
            if not m or line >= len(rows):
                continue
            month = MONTHS.get(m.group(2).title())
            if not month:
                continue
            try:
                out.append((rows[line][0],
                            datetime(int(m.group(3)), month, int(m.group(1)))))
            except ValueError:
                continue
    return out


def context(text, identifier=None):
    """(offset -> journal, date, bill) as three sorted lists of checkpoints."""
    days, dates, bills = [], [], []
    rows = lines_with_offsets(text)
    for i, (pos, line) in enumerate(rows):
        m = DAY.match(line)
        if m:
            days.append((pos, int(m.group(2))))
            # The date is printed on the next non-empty line under it.
            for _pos2, nxt in rows[i + 1:i + 4]:
                d = DATE.match(nxt)
                if d:
                    try:
                        dates.append((pos, datetime(
                            int(d.group(3)), MONTHS[d.group(1)], int(d.group(2)))))
                    except (KeyError, ValueError):
                        pass
                    break
        for b in BILL.finditer(line):
            bills.append((pos, i, re.sub(r"\s+", "", b.group(1)).upper()))
    # Where the body carries no dates at all, the running heads do.
    if identifier and not dates:
        dates = sorted(head_dates(identifier, rows))
    pages = head_pages(identifier, rows) if identifier else []
    return rows, days, plausible(dates), bills, pages


def plausible(dates):
    """Drop sitting dates that cannot belong to this volume.

    A bound volume covers at most two calendar years -- December of one
    session year through the summer of the next. So a date more than a year
    from the volume's own commonest year is a misread number, not a sitting.

    This exists because the 1989-1990 House volume prints one day heading the
    scan reads as 12 April 1999, and 666 member votes were filed under a term
    nine years after the book closed. The volume dates itself, so nothing
    outside it has to be consulted.
    """
    if not dates:
        return dates
    years = Counter(d.year for _pos, d in dates)
    middle = years.most_common(1)[0][0]
    keep = [(pos, d) for pos, d in dates if abs(d.year - middle) <= 1]
    dropped = len(dates) - len(keep)
    if dropped:
        bad = sorted({d.year for _p, d in dates if abs(d.year - middle) > 1})
        print(f"      {dropped} date(s) dropped as impossible for a volume "
              f"centred on {middle}: {bad}")
    return keep


def latest(checkpoints, pos):
    """The last checkpoint at or before pos. Checkpoints are in order."""
    i = bisect.bisect_right([c[0] for c in checkpoints], pos) - 1
    return checkpoints[i] if i >= 0 else None


def extract(identifier, numbers, seen):
    path = REPAIRED / f"{identifier}.txt"
    if not path.exists():
        return [], f"{path} is not there"
    text = path.read_text(encoding="utf-8", errors="replace")
    rows, days, dates, bills, pages = context(text, identifier)
    # Line starts, for turning a character offset back into a line number.
    # Bisected rather than scanned: this runs once per roll call and there
    # are sixty thousand lines in a volume.
    starts = [pos for pos, _l in rows]
    calls = M.rollcalls(text)
    if not calls:
        return [], "no roll call found"
    body = "S" if M.chamber_of(text) == "senate" else "H"

    out, cursor = [], 0
    for yeas, nays, yb, nb, chamber in calls:
        at = text.find(yb, cursor)
        if at < 0:
            at = cursor
        cursor = at + max(1, len(yb))

        day = latest(days, at)
        when = latest(dates, at)
        leaf = latest(pages, at)
        # The bill must be ABOVE the roll call and close to it. A bill number
        # forty lines up is the previous item of business, not this vote's.
        bill = ""
        b = latest(bills, at)
        if b is not None:
            here = bisect.bisect_right(starts, at) - 1
            if 0 <= here - b[1] <= LOOKBACK:
                bill = b[2]

        year = when[1].year if when else None
        month = when[1].month if when else 1
        for side, block in (("Yea", yb), ("Nay", nb)):
            for name in M.names_in(block, chamber):
                parts = name.split(",")
                surname, given = parts[0], (parts[1] if len(parts) > 1 else "")
                hit = numbers.get((body, surname, given))
                # AN INITIAL RESOLVES WHERE ONLY ONE LISTED NAME STARTS WITH
                # IT. The Senate prints surnames alone, and an initial only
                # where it has two of the same name -- "J. King" and "F.
                # King". The General Court lists King, Bill; King, Frank;
                # King, Frederick; King, John, and only one of those begins
                # with J, so J. King is John King and nothing is guessed.
                # F. King is Frank or Frederick and stays unresolved, which
                # is the same refusal used everywhere else here.
                if not hit and len(given) == 1:
                    # NOT "starts": that name is already the list of line
                    # offsets this function bisects, and shadowing it made
                    # every volume die on the next roll call.
                    same_initial = [v for (bod, sur, giv), v in numbers.items()
                                    if bod == body and sur == surname
                                    and giv.startswith(given)]
                    if len(same_initial) == 1:
                        hit = same_initial[0]
                source = "gencourt"
                if hit:
                    mid, shown = hit
                else:
                    mid, source = mint(body, surname, given), "archive"
                    # Title case is the best this can do for someone the
                    # General Court does not list. It is the scan's reading,
                    # made presentable, not an authority's spelling -- which
                    # is what the source column is there to say.
                    shown = f"{surname.title()}, {given.title()}".rstrip(", ")
                out.append({
                    "term": term_of(year, month) if year else "",
                    "year": year or "", "body": body,
                    "journal": day[1] if day else "",
                    "date": when[1].date().isoformat() if when else "",
                    "bill": bill, "yeas": yeas, "nays": nays,
                    "page": leaf[1] if leaf else "",
                    "member_id": mid, "name": shown, "vote": side,
                    "volume": identifier,
                })
                rec = seen.setdefault(mid, {
                    "member_id": mid, "source": source, "body": body,
                    "surname": surname, "given": given,
                    "name": shown, "votes": 0,
                    "first_year": year or "", "last_year": year or ""})
                rec["votes"] += 1
                if year:
                    rec["first_year"] = min(rec["first_year"] or year, year)
                    rec["last_year"] = max(rec["last_year"] or year, year)
    return out, f"{len(calls)} roll calls, {len(out):,} votes"


def suspects(seen, numbers, limit):
    """Minted people who most deserve a person's eye, and why.

    A minted identifier means the General Court's own list does not carry
    that name. There are two quite different reasons for that and they need
    different work, so they are separated rather than piled together:

      NEAR A REAL NAME -- the scan probably misread someone. The repair
      refused to merge them for a reason, usually that the scan's reading is
      ALSO a real surname from another era. 1997 reads Tholl as Toll; Tholl
      is absent from past_members.json and Amanda Toll of Cheshire sat in the
      2020s, so "Toll" looked legitimate and was left alone. The vote did not
      go to Amanda Toll -- the given name kept them apart -- but the name on
      it is wrong.

      NOT NEAR ANYTHING -- more likely a real member the General Court's list
      simply does not reach. Those are the ones an archive identifier exists
      for in the first place.

    Ranked by votes, because a wrong name on eighty votes matters more than
    on one, and printed rather than acted on.
    """
    import difflib
    by_surname = {}
    for (_bod, sur, _giv), (_num, shown) in numbers.items():
        by_surname.setdefault(sur, []).append(shown.split(",")[1].strip())
    rows = [r for r in seen.values() if r["source"] == "archive"]
    rows.sort(key=lambda r: -r["votes"])
    print(f"\n{len(rows)} people carry an identifier minted here, "
          f"{sum(r['votes'] for r in rows):,} votes between them.")
    print(f"The {min(limit, len(rows))} with the most:\n")
    print(f"  {'votes':>6}  {'minted as':<26} {'why it did not resolve':<46}")
    for r in rows[:limit]:
        if r["surname"] in by_surname:
            others = ", ".join(sorted(by_surname[r["surname"]])[:3])
            why = f"same surname listed, given name differs: {others}"
        else:
            near = difflib.get_close_matches(r["surname"],
                                             list(by_surname), n=1, cutoff=0.8)
            why = (f"surname not listed; nearest is {near[0]}"
                   if near else "surname not listed, nothing close")
        print(f"  {r['votes']:>6}  {r['name']:<26} {why}")
    print("""
  The first kind is usually the General Court listing the name a member goes
  by where the journal prints the name they were elected under -- Emerton,
  Larry against Emerton, Lawrence; Lovett, Sid against Lovett, Sidney. Those
  are one person and this does not join them, because doing it on the initial
  alone would also join a 1991 member to a namesake elected thirty years
  later, and a vote on the wrong person is worse than a vote on nobody.

  The second kind is mostly people the list does not reach at all. Barry,
  William sat for Hillsborough in the 1990s and is not in it.

  Both keep an archive identifier, which is correct rather than a failure:
  the vote is recorded against the right name, and is simply not yet joined
  to a General Court record. Joining them is a person's decision, one at a
  time, and this list is what that person would work from.""")


def unresolved_csv(seen, numbers):
    """Everyone with a minted identifier, and the evidence about them.

    A worklist, not a decision. Each row carries what the General Court lists
    under that surname, so a person can see at a glance whether this is the
    nickname case -- Emerton, Lawrence against the list's Larry -- or somebody
    the list does not reach. Ranked by votes, because a name that is wrong on
    eighty votes matters more than one wrong on a single vote.
    """
    import difflib
    by_surname = {}
    for (_bod, sur, _giv), (num, shown) in numbers.items():
        by_surname.setdefault(sur, []).append(shown)
    rows = []
    for r in sorted((r for r in seen.values() if r["source"] == "archive"),
                    key=lambda r: -r["votes"]):
        listed = sorted(by_surname.get(r["surname"], []))
        near = "" if listed else ", ".join(
            difflib.get_close_matches(r["surname"], list(by_surname), n=2,
                                      cutoff=0.8))
        rows.append({
            "member_id": r["member_id"], "name": r["name"], "body": r["body"],
            "votes": r["votes"], "first_year": r["first_year"],
            "last_year": r["last_year"],
            "cause": "same surname listed, given name differs" if listed
                     else "surname not listed",
            "general_court_lists": "; ".join(listed[:4]),
            "nearest_surnames": near,
        })
    dest = OUT / "unresolved.csv"
    with dest.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else
                           ["member_id"])
        w.writeheader()
        w.writerows(rows)
    nick = sum(1 for r in rows if r["cause"].startswith("same"))
    print(f"\n  -> {dest}")
    print(f"     {len(rows):,} people to work through: {nick:,} where the "
          f"General Court lists the\n     surname under another given name, "
          f"{len(rows)-nick:,} it does not list at all")
    return dest


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("identifiers", nargs="*")
    ap.add_argument("--all", action="store_true", help="every repaired volume")
    ap.add_argument("--summary", action="store_true", help="counts only, write nothing")
    ap.add_argument("--unresolved", action="store_true",
                    help="write data/unh/unresolved.csv, a worklist of the "
                         "people who carry a minted identifier")
    ap.add_argument("--suspect", type=int, default=0, metavar="N",
                    help="list the N minted people most worth a person's eye")
    a = ap.parse_args()

    idents = a.identifiers
    if a.all or not idents:
        idents = sorted(p.stem for p in REPAIRED.glob("*.txt"))
    if not idents:
        sys.exit(f"nothing in {REPAIRED}; unh_repair.py writes it")

    numbers = gencourt_numbers()
    print(f"{len(numbers):,} name-to-number pairs from the General Court\n")

    seen, allrows = {}, []
    for ident in idents:
        rows, note = extract(ident, numbers, seen)
        allrows.extend(rows)
        print(f"  {ident:<62} {note}")

    if not allrows:
        sys.exit("\nno volume yielded a single vote; nothing written")

    by_source = Counter(r["source"] for r in seen.values())
    dated = sum(1 for r in allrows if r["date"])
    billed = sum(1 for r in allrows if r["bill"])
    print(f"\n{len(allrows):,} member votes across {len(idents)} volumes")
    print(f"  {len(seen):,} people: {by_source.get('gencourt', 0):,} carry a "
          f"General Court number, {by_source.get('archive', 0):,} are minted here")
    print(f"  {100*dated/len(allrows):.1f}% carry a sitting date, "
          f"{100*billed/len(allrows):.1f}% a bill")
    # Before the --summary return, so that the review list can be had without
    # rewriting the data files.
    if a.suspect:
        suspects(seen, numbers, a.suspect)
    if a.unresolved and not a.summary:
        unresolved_csv(seen, numbers)
    if a.summary:
        return

    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "rollcalls.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(allrows)
    with (OUT / "members.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MEMBER_COLS)
        w.writeheader()
        w.writerows(sorted(seen.values(), key=lambda r: (-r["votes"], r["member_id"])))
    print(f"\n  -> {OUT/'rollcalls.csv'}  ({(OUT/'rollcalls.csv').stat().st_size:,} bytes)")
    print(f"  -> {OUT/'members.csv'}")


if __name__ == "__main__":
    main()
