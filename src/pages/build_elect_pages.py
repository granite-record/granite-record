#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-08.2
"""
A provisional page for each new member-elect: who they are until the General
Court numbers them.

    python3 src/pages/build_elect_pages.py --site site --collected collected

Alice, 7 November 2026: "create their pages with just their name and
district and fill in information as it comes in". The design is
docs/design/requests-members/DESIGN.md, 3 (on design/api), and her answers
to it: the pages are noindex until the person is numbered (B2), and they
stay past Organization Day until then (B3).

WHAT THIS WRITES

  site/elect_pages.json   {"election", "takes_office", "pages": [...]}, one
                          entry for each new member-elect with a page: slug,
                          name as the results print it, party, chamber,
                          county, district, race and towns. Nothing else, and
                          no id: a member-elect has none until the General
                          Court assigns one (the owner's rule of 30 October
                          2026, commit 776cbe70).

build_legislator_pages.py draws each page from this; build_members_elect.py
links a new person's chip to it; build_lsrs.py matches their requests by
name. None of them reads the roster for it.

KEPT APART FROM THE ROSTER. The rules of 16 October hold as they are: a
member-elect is never in legislators.json, former.json, places.json or the
census, and this writes none of them. It reads the roster only to keep an
address from being a member's, and to see whether the person has been
numbered.

WHO GETS ONE. The winners build_members_elect.members_elect() calls new
("k": "new") in the newest general election's results, by its rules --
final races only, the owner's "matches" and "held" applied -- and nobody
else. It is called here outside the members-elect window on purpose: the
members-elect file and its blocks retire on Organization Day, and these
pages do not (B3).

THE ADDRESS is build_site_v2.member_slug of the printed name and the race,
the roster's own function, so most pages keep their address when the person
is numbered. One that is already a sitting or former member's page, or that
two new people share, is not written: the person stays unlinked and this
says so. No suffix is invented.

NUMBERED. From Organization Day, the night the roster carries the person --
exactly one sitting member of the same chamber and district whose name folds
to theirs -- no provisional page is written for them: their regular page is.
Where its address is the provisional one, it simply replaces it. Where it is
another, the provisional address goes in "moved", and build_pages writes a
301 from it to the regular page for as long as these results are the newest.
Before Organization Day nobody is numbered: the roster is still the old
term's, and a sitting member of the same name and district is somebody else.
Who is new is the step's word or the owner's (a null match), so a person the
step comes to call sitting once the roster has them is still followed.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import datetime
import json

import build_date
import build_members_elect as BME
import proceedings

OUT_NAME = "elect_pages.json"
MOVED = Path("generated/moved_addresses.json")


def slug_of(name, chamber, county, district):
    """The address the roster would give this person: build_site_v2's own
    member_slug, so the two agree without either guessing."""
    import build_site_v2 as BS
    abbr = BS.COUNTY_ABBR.get(str(county or "").lower(), county or "")
    return BS.member_slug({"name": name, "chamber": chamber, "county_abbr": abbr,
                           "district": district}, {})


def race_parts(key):
    """("H", "Rockingham", "13") or ("S", "", "24") from a race key."""
    p = key.split("|")
    return (p[0], p[1], p[2]) if p[0] == "H" else (p[0], "", p[1])


def first_last(name):
    """'Nelson, Jodi' -> 'Jodi Nelson'; a name already first-last as it is."""
    last, sep, first = str(name or "").partition(",")
    return f"{first.strip()} {last.strip()}".strip() if sep else str(name or "").strip()


def numbered_as(e_name, chamber, county, district, sitting):
    """The one sitting member this person now is, or None: same chamber, same
    district (and county, for the House), and a name that folds to theirs."""
    want = BME.fold(e_name)
    hits = [m for m in sitting
            if str(m.get("chamber", "")).upper()[:1] == chamber
            and str(m.get("district", "")).lstrip("0") == str(district).lstrip("0")
            and (chamber == "S" or str(m.get("county", "")).lower() == county.lower())
            and BME.fold(first_last(m.get("name"))) == want]
    return hits[0] if len(hits) == 1 else None


def confirmed_new(hand):
    """{(race, name)} the owner's hand file confirms new (a match of null):
    new by the owner's word whatever the roster comes to say."""
    return {(race, name) for race, names in ((hand or {}).get("matches") or {}).items()
            for name, v in (names or {}).items() if v is None}


def pages(results, sitting, former, districts, hand, today, takes_office, moved=None):
    """(the pages, what to say, {old address: new address} for a person the
    roster has numbered at another address).

    NEW is the step's own word ("k": "new") or the owner's (a null match):
    once the roster carries a person, the step's rule may call them sitting,
    and their provisional address must still go somewhere. NUMBERED only from
    Organization Day: before it the roster is the old term's, and a sitting
    member of the same name and district is somebody else (a parent, say),
    whom the owner has already told apart."""
    races, _report = BME.members_elect(results, sitting, former, districts, hand, today)
    on_file, _ = BME.races_on_file(districts)
    sure = confirmed_new(hand)
    # A member's page, and an old address that already answers with a 301
    # (generated/moved_addresses.json), are both taken.
    taken = {m.get("slug") for m in [*sitting, *former] if m.get("slug")}
    taken |= {a.rsplit("/", 1)[-1] for a in (moved or {})}
    out, said, moves, seen = [], [], {}, {}
    for key in sorted(races, key=BME.race_order):
        for e in races[key].get("elected") or []:
            if e.get("k") != "new" and (key, e.get("n")) not in sure:
                continue
            chamber, county, district = race_parts(key)
            slug = slug_of(e.get("n"), chamber, county, district)
            now = (numbered_as(e.get("n"), chamber, county, district, sitting)
                   if today >= takes_office else None)
            if now:
                # Their regular page now. At the same address it simply
                # replaces this one; at another, this address answers with a
                # 301 to it (build_pages writes them from "moved").
                if now.get("slug") and now.get("slug") != slug:
                    moves[f"/legislator/{slug}"] = f"/legislator/{now['slug']}"
                continue
            if slug in taken:
                said.append(f"{e.get('n')} ({key}): /legislator/{slug} is a member's page; "
                            "left unlinked for a person to settle")
                continue
            seen.setdefault(slug, []).append(e.get("n"))
            out.append({"slug": slug, "name": e.get("n"), "party": e.get("p") or "",
                        "chamber": chamber, "county": county, "district": district, "race": key,
                        "towns": sorted((on_file.get(key) or {}).get("towns") or [])})
    twice = {s for s, who in seen.items() if len(who) > 1}
    if twice:
        said += [f"{', '.join(seen[s])}: two new members-elect would share /legislator/{s}; "
                 "neither is given a page" for s in sorted(twice)]
        out = [p for p in out if p["slug"] not in twice]
    return out, said, moves


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    ap.add_argument("--site", default="site")
    ap.add_argument("--collected", default="collected")
    ap.add_argument("--hand", default=str(BME.HAND_DEFAULT))
    a = ap.parse_args()
    site = Path(a.site)
    dest = site / OUT_NAME
    path = BME.newest_results(a.collected)
    today = build_date.today()
    if path is None:
        dest.unlink(missing_ok=True)
        print(f"  elect pages: none -- no election results in {a.collected}/")
        return 0
    results = BME.read_results(path)
    election = datetime.date.fromisoformat(results["election"])
    if today <= election:
        dest.unlink(missing_ok=True)
        print(f"  elect pages: none -- {path.as_posix()} is of an election not yet held")
        return 0
    hand, _note = BME.read_hand(Path(a.hand), results["election"])
    sitting = BME.load_json(site / "legislators.json", "the sitting roster")
    former = BME.load_json(site / "former.json", "the former members") \
        if (site / "former.json").exists() else []
    districts = BME.load_json(site / "districts.json", "the district table")
    moved = json.loads(MOVED.read_text(encoding="utf-8")) if MOVED.is_file() else {}
    takes_office = proceedings.organization_day(election.year)
    got, said, moves = pages(results, sitting, former, districts, hand,
                             today.isoformat(), takes_office.isoformat(), moved)
    doc = {"election": results["election"], "takes_office": takes_office.isoformat(),
           "sources": [s.get("url") for s in results.get("_source") or [] if s.get("url")],
           "pages": got,
           # A provisional address the roster numbered its person at another:
           # build_pages writes a 301 for each, as long as these results are
           # the newest. For good, a person can record it in
           # generated/moved_addresses.json.
           "moved": dict(sorted(moves.items()))}
    tmp = dest.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(dest)
    print(f"  elect pages: {len(got)} new members-elect given a provisional page -> "
          f"{dest.as_posix()}")
    for s in said:
        print(f"    {s}")
    for old, new in doc["moved"].items():
        print(f"    numbered at another address: {old} answers with a 301 to {new}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
