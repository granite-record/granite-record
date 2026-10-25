#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-23.2
"""
Where each municipal official a town page shows comes from, how old the copy
on this disk is, and when it is due to be read again.

    python3 src/towns/town_sources.py           # the map: each source, its fields, its copy's date and age
    python3 src/towns/town_sources.py --due     # only what is due; exits 1 if anything is

Touches no network. It reads the three files the town pages are drawn from
and says what it finds; nothing here writes anything.

WHY (the freshness review of 23 October 2026). A town page names the town's
select board or council, its clerk, its town offices and where its voters
vote, from three sources read at three different times, and nothing said when
any of them was due to be read again. Measured that day: NHDOT's directory,
dated 2 September 2025, still gave the select board of 154 of the 221 towns,
the council of the eight towns governed by one and the mayor and council of
three cities -- every one of them chosen again since, at the March 2026 town
meetings or the November 2025 city elections. Of the 67 towns whose own page
was read in September 2026, 58 named at least one selectman the directory did
not, and every directory board or council the review could check against a
town's own words was wrong by at least one name. Berlin's directory row names
as mayor a man who left the office in January 2024.

THE THREE SOURCES, and the date each copy carries in its own file (SOURCES):

  sos_list    the Secretary of State's list of town and city clerks and
              polling places: collected/town_clerks.json, each row's
              `read_on`, the day of the export it was read from
  nhdot       NHDOT's directory of city and town officials:
              collected/town_officials.json, each municipality's `as_of`,
              the directory's own date (its PDF's CreationDate)
  town_sites  the towns' and cities' own websites: collected/town_boards.json,
              each board's and council's `read_on`, the moment its page was
              saved

AND THE TOWN DIRECTORY'S SOURCES (24 October 2026), the facts of the Town
Services tab rather than officials, held to the same rule:

  imls_pls    the Institute of Museum and Library Services' Public
              Libraries Survey: collected/libraries.json, each town's
              `read_on`, the day the survey was saved. A survey comes out
              once a year, so only MAX_AGE makes a copy due.

A copy is as old as its oldest row. The county officers are not here: the site
draws them from corrections/officials.json, a person's file, which preflight's
_officials_rechecked asks to be read again after every general election.

WHEN A COPY IS DUE (due). Officials change on a calendar, and the calendar is
what makes a copy stale, more than its age:

  the town meetings     the second Tuesday of March (RSA 669:1; April or May
                        where a town has chosen so, RSA 40:14, X). One
                        selectman a year (RSA 41:8), the clerk where the
                        clerk's term ends, the town councils, and every board
                        chooses its chair again after it. Due TOWN_GRACE
                        after, by when the results are in and the towns'
                        pages have had time to catch up.
  the cities' elections the Tuesday after the first Monday of November in an
                        odd year, the new mayor and council taking office in
                        the first days of January. Due CITY_GRACE after.
  the state election    the polling places the Secretary of State's list
                        names are for the election coming: from POLL_WINDOW
                        before a general election until its day, a list read
                        earlier than that is due.
  any day               appointed offices -- administrators, managers, road
                        agents -- change on no calendar, and neither does a
                        resignation: a copy older than MAX_AGE is due whatever
                        the calendar says.

A COPY NOBODY CAN READ AGAIN (LOOKED_ON). NHDOT publishes its directory when
it publishes it, and no request here can make a newer one. A person who looks
for a newer edition and finds none writes the day they looked in LOOKED_ON,
which counts as a reading until the next date passes, so the reminder asks
again after the next town meetings rather than every night until NHDOT acts.

WHO IS TOLD. preflight's _town_sources_fresh holds the real files to due() on
the clock: one of its REMINDERS, it warns on the night and never holds the
site, and it fails on the laptop until the copy is read again.
_town_sources_rule runs the same rule on fixed days, so a reminder that could
never fire fails at once.

FLOORS (short_of). A source read again can come back with less in it -- a
layout change, an export cut short, a parser run with nothing to match its
towns against -- and every writer of these files exits 0 having written
whatever it got. parse_officials.py, run on any machine with no built site,
wrote `{}` where the directory's 234 municipalities had been and exited 0
(found by the review, 23 October 2026, before it ever reached git). So each
file has a floor a little under what it holds, the writers of
the first two refuse to write under it unless a person passes --allow-shrink,
and preflight's _town_sources_floors holds the files in git to the same
floors. A floor is lowered by hand, with the reason beside it, when a source
really does get smaller.
"""
# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import datetime as dt
import json
import re

import build_date

# The repository root, wherever this file sits (_paths.py): the data it
# reads is the root's.
ROOT = _paths.ROOT

TOWN_GRACE = dt.timedelta(days=35)
CITY_GRACE = dt.timedelta(days=70)
POLL_WINDOW = dt.timedelta(days=60)
MAX_AGE = dt.timedelta(days=365)

SOURCES = {
    "sos_list": {
        "name": "the Secretary of State's list of town and city clerks and polling places",
        "url": "https://app.sos.nh.gov/statelistclerkandpolling",
        "file": "collected/town_clerks.json",
        "writer": "src/towns/parse_clerks_csv.py",
        "fetch": ("a person, in a browser: the page sits behind a CAPTCHA, so its CSV "
                  "export is saved by hand in records/sources/ "
                  "(src/fetch/other/fetch_town_clerks.py has never been run)"),
        "fields": ("the town or city clerk, with phone and e-mail, on Town officials and "
                   "How to vote", "where you vote and its hours",
                   "the election How to vote is headed with",
                   "the town website, where NHDOT's directory gives none",
                   "the My Town card's clerk, polling place and hours (places.json)"),
        "page_says": "no date: \"From the Secretary of State's list of town and city clerks.\"",
        "events": ("town_meeting", "before_general_election"),
        "again": ("export the list again as CSV from {url} (a person's to start: it sits "
                  "behind a CAPTCHA and is somebody else's server), save it in "
                  "records/sources/, point CSV_IN and READ_ON in "
                  "src/towns/parse_clerks_csv.py at it, and run that script"),
    },
    "nhdot": {
        "name": "the New Hampshire Department of Transportation's directory of city and "
                "town officials",
        "url": "records/sources/nh-municipal-officials-2025-09-01.pdf",
        "file": "collected/town_officials.json",
        "writer": "src/towns/parse_officials.py",
        "fetch": "a person saves each edition's PDF in records/sources/; NHDOT keeps no "
                 "schedule this project knows of",
        "fields": ("the select board of every town whose own page is not used",
                   "the town council of the eight towns governed by one",
                   "the mayor and council of a city whose own page is not used",
                   "the Town offices card: the mailing address, the office's phone, "
                   "e-mail and website, and the administrator or manager, road agent "
                   "and public works rows",
                   "the phone and e-mail beside a member read off a town's own page"),
        "page_says": "its month: \"dated September 2025\", \"before the 2026 town elections\"",
        "events": ("town_meeting", "city_election"),
        "again": ("look for a newer edition of the directory; if there is one, save it in "
                  "records/sources/ and run src/towns/parse_officials.py --pdf on it, and if "
                  "there is none, set LOOKED_ON[\"nhdot\"] in src/towns/town_sources.py to "
                  "the day you looked"),
    },
    "town_sites": {
        "name": "the towns' and cities' own websites",
        "url": "town_sites/ (saved pages, not in git)",
        "file": "collected/town_boards.json",
        "writer": "src/towns/town_boards.py",
        "fetch": ("a person, on the laptop: src/fetch/other/town_sites.py, five seconds "
                  "between requests, robots.txt obeyed; read through "
                  "src/towns/parse_town_sites.py"),
        "fields": ("the select board of each town whose own page was current when read",
                   "the mayor and council of each city whose own page was"),
        "page_says": "the day: \"when this site read it on September 20, 2026\"",
        "events": ("town_meeting", "city_election"),
        "again": ("read the towns' own pages again (src/fetch/other/town_sites.py --home, "
                  "then --officials: a person's to start, it asks the towns' servers), move "
                  "MEETING and CITY_ELECTION in src/towns/town_boards.py to the last town "
                  "meeting and city election, then run src/towns/parse_town_sites.py and "
                  "src/towns/town_boards.py"),
    },
    "imls_pls": {
        "name": "the Institute of Museum and Library Services' Public Libraries Survey",
        "url": "https://www.imls.gov/research-evaluation/surveys/public-libraries-survey-pls",
        "file": "collected/libraries.json",
        "writer": "src/towns/parse_libraries.py",
        "fetch": ("src/fetch/other/town_directory.py --source imls census_blocks (federal "
                  "files any machine can reach), read through src/towns/parse_libraries.py"),
        "fields": ("the Town Services tab's Library card: each public library in the town, "
                   "its address and phone",),
        "page_says": "its survey's year: \"from the Public Libraries Survey, fiscal year 2024\"",
        "events": (),
        "again": ("find the newest survey's CSV on {url}, point SOURCES['imls'] in "
                  "src/fetch/other/town_directory.py and SURVEY, OUTLETS and FISCAL_YEAR in "
                  "src/towns/parse_libraries.py at it, then run the two"),
    },
}

# A day a person looked for a newer copy of a source and found none, and what
# they looked at. It counts as a reading of that source (see the docstring).
LOOKED_ON = {
    "nhdot": ("2026-10-23",
              "the freshness review searched the web for an edition of NHDOT's directory "
              "newer than September 2025 and found none; NHDOT was not asked. Set so that "
              "the reminder first asks after the March 2027 town meetings, for a directory "
              "every town page already dates"),
}

# What each file holds at the least (the docstring's FLOORS). Measured on 23
# October 2026: the list 339 rows, every one with a clerk and a phone, 338
# with an e-mail, 312 a website and 225 a polling place; the directory 234
# municipalities, 1,407 named offices and 230 websites; the towns' own pages
# 67 select boards and 10 city councils.
FLOORS = {
    "sos_list": {"rows": 330, "clerk": 330, "phone": 330, "email": 320, "website": 290,
                 "polling_place": 200},
    "nhdot": {"municipalities": 230, "offices": 1300, "website": 220},
    "town_sites": {"boards": 55, "councils": 8},
    # Measured on 24 October 2026: 229 libraries in 207 towns, every one of the
    # survey's New Hampshire outlets placed by its census block.
    "imls_pls": {"towns": 200, "libraries": 220},
}


# ---------------------------------------------------------------- the calendar ---
def _tuesday(year, month, nth):
    first = dt.date(year, month, 1)
    return first + dt.timedelta(days=(1 - first.weekday()) % 7 + 7 * (nth - 1))


def town_meeting(year):
    """The town meetings' election day: the second Tuesday of March."""
    return _tuesday(year, 3, 2)


def general_election(year):
    """The Tuesday after the first Monday of November: the state general
    election in an even year, the cities' own in an odd one."""
    nov = dt.date(year, 11, 1)
    return nov + dt.timedelta(days=(0 - nov.weekday()) % 7 + 1)


def words(d):
    return f"{d:%B} {d.day}, {d.year}"


def day_of(value):
    """"2026-09-20" or "2026-09-20T22:22:15-0400" as a date; None for
    anything else."""
    m = re.match(r"^(\d{4})-(\d\d)-(\d\d)(?:$|T)", str(value or ""))
    if not m:
        return None
    try:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def checkpoints(key, today):
    """[(due, until, why)]: each day, in the year before `today`'s and in
    its own, from which a copy of the source read earlier than it is due --
    until `until`, or for good where that is None -- and the sentence that
    says why."""
    events = SOURCES[key]["events"]
    out = []
    for y in (today.year - 1, today.year):
        if "town_meeting" in events:
            m = town_meeting(y)
            out.append((m + TOWN_GRACE, None,
                        f"the town meetings of {words(m)} have been held since the copy's date"))
        if "city_election" in events and y % 2:
            e = general_election(y)
            out.append((e + CITY_GRACE, None,
                        f"the cities' elections of {words(e)} have been held since the "
                        "copy's date"))
        if "before_general_election" in events and not y % 2:
            e = general_election(y)
            out.append((e - POLL_WINDOW, e + dt.timedelta(days=1),
                        f"its polling places are for the general election of {words(e)}, "
                        f"and the copy is from more than {POLL_WINDOW.days} days before it"))
    return out


def due(key, as_of, today, looked_on=None):
    """"" while the copy is fresh enough on `today`, or why it is due.

    `as_of` is the copy's date (a date, or None where the file carries
    none), `looked_on` the day a person last looked for a newer copy and
    found none (LOOKED_ON), which counts as a reading; a day after today
    counts as none, since it records no look that happened."""
    if as_of is None:
        return "the file carries no date for its copy, so nothing can say how old it is"
    if as_of > today:
        return f"the copy is dated {as_of}, after today"
    seen = as_of
    if looked_on is not None and as_of < looked_on <= today:
        seen = looked_on
    said = []
    passed = [(d, why) for d, until, why in checkpoints(key, today)
              if d <= today and (until is None or today < until) and seen < d]
    if passed:
        said.append(max(passed)[1])
    if today - seen > MAX_AGE:
        said.append(f"the copy is {(today - seen).days} days old, more than "
                    f"{MAX_AGE.days}")
    return "; ".join(said)


def next_due(key, as_of, today, looked_on=None):
    """The first day after `today` on which due() will say the copy is due,
    if nobody reads it again before then; None where none comes within two
    years."""
    for n in range(1, 2 * 366):
        d = today + dt.timedelta(days=n)
        if due(key, as_of, d, looked_on):
            return d
    return None


# ------------------------------------------------------------------- the files ---
def load(key, root=None):
    """The source's file, as JSON, or None where it is not there."""
    p = Path(root or ROOT) / SOURCES[key]["file"]
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def rows(key, data):
    """The rows of a source's file that carry its copy's date."""
    if not isinstance(data, dict):
        return []
    if key == "town_sites":
        return list((data.get("boards") or {}).values()) + \
            list((data.get("councils") or {}).values())
    return [v for k, v in data.items() if isinstance(v, dict) and not k.startswith("_")]


DATE_FIELD = {"sos_list": "read_on", "nhdot": "as_of", "town_sites": "read_on",
              "imls_pls": "read_on"}


def copy_date(key, data):
    """(the copy's date, how many rows carry no date): the oldest row's day,
    or None where no row carries one."""
    days = [day_of(r.get(DATE_FIELD[key])) for r in rows(key, data)]
    have = [d for d in days if d]
    return (min(have) if have else None), len(days) - len(have)


def looked(key):
    """LOOKED_ON's day for a source, as a date, or None."""
    entry = LOOKED_ON.get(key)
    return day_of(entry[0]) if entry else None


def counts(key, data):
    """What FLOORS counts, in a source's file."""
    rs = rows(key, data)
    if key == "sos_list":
        out = {"rows": len(rs)}
        for f in ("clerk", "phone", "email", "website", "polling_place"):
            out[f] = sum(1 for r in rs if r.get(f) or (f == "polling_place"
                                                       and r.get("polling_by_ward")))
        return out
    if key == "nhdot":
        return {"municipalities": len(rs),
                "offices": sum(len(r.get("officials") or []) for r in rs),
                "website": sum(1 for r in rs if r.get("website"))}
    if key == "imls_pls":
        return {"towns": len(rs), "libraries": sum(len(r.get("libraries") or []) for r in rs)}
    d = data if isinstance(data, dict) else {}
    return {"boards": len(d.get("boards") or {}), "councils": len(d.get("councils") or {})}


def short_of(key, data):
    """[sentence] for each count in the file under its floor; [] for none."""
    have = counts(key, data)
    return [f"{SOURCES[key]['file']}: {have.get(f, 0)} {f}, under the floor of {n}"
            for f, n in FLOORS[key].items() if have.get(f, 0) < n]


def report(today=None, root=None):
    """[(key, {"date", "age", "due", "missing", "counts", "short"})] for
    every source, read from its file on `today`."""
    today = today or build_date.today()
    out = []
    for key in SOURCES:
        data = load(key, root)
        if data is None:
            out.append((key, {"date": None, "age": None, "missing": None, "counts": {},
                              "short": [f"{SOURCES[key]['file']} is not there"],
                              "due": f"{SOURCES[key]['file']} is not there"}))
            continue
        when, missing = copy_date(key, data)
        out.append((key, {"date": when, "missing": missing,
                          "age": (today - when).days if when else None,
                          "counts": counts(key, data), "short": short_of(key, data),
                          "due": due(key, when, today, looked(key)),
                          "next": next_due(key, when, today, looked(key)) if when else None}))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--due", action="store_true",
                    help="only the sources due a reading; exit 1 if any is")
    a = ap.parse_args(argv)
    today = build_date.today()
    found = report(today)
    late = 0
    for key, r in found:
        s = SOURCES[key]
        if a.due and not r["due"]:
            continue
        late += bool(r["due"])
        print(f"\n{key}: {s['name']}")
        print(f"  file      {s['file']}, written by {s['writer']}")
        print(f"  fetch     {s['fetch']}")
        when = (f"{r['date']} ({r['age']} days old on {today})" if r["date"]
                else "no date in the file")
        if r.get("missing"):
            when += f"; {r['missing']} rows carry no date"
        print(f"  copy      {when}")
        if looked(key):
            print(f"  looked    {LOOKED_ON[key][0]}: {LOOKED_ON[key][1]}")
        print(f"  page says {s['page_says']}")
        print("  shows     " + "\n            ".join(s["fields"]))
        print("  holds     " + ", ".join(f"{n} {f}" for f, n in r["counts"].items()))
        for x in r["short"]:
            print(f"  ! {x}")
        if r["due"]:
            print(f"  DUE       {r['due']}: {s['again'].format(url=s['url'])}")
        elif r["next"]:
            print(f"  next due  {r['next']}, unless it is read again before then")
    if a.due and not late:
        print("nothing is due")
    return 1 if (a.due and late) else 0


if __name__ == "__main__":
    sys.exit(main())
