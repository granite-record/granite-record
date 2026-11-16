#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-11.5
"""
The state's facts, read from src/lib/state_settings.json.

    import state_settings as ST
    ST.COUNTIES          # ("Belknap", "Carroll", ...), in the order the file lists them
    ST.TIMEZONE          # "America/New_York"
    ST.get("legislature", "name")
    ST.PARTY["D"]["plural"], ST.party_letters("r&d")   # "Democrats", ("R", "D")

WHY A JSON FILE. A fork for another state edits data, not code; the file is
read by the same loader whatever its values, and a script in another language
can read it too. A Python module would make the edit a code change.

WHAT A FORK STILL CHANGES is written in the file's "_about" key: this file
holds only the facts that were repeated, or that a fork would change first.
preflight loads it, checks every key, and fails on a second literal county list.
"""
import json
import re

import _paths

_FILE = _paths.ROOT / "src" / "lib" / "state_settings.json"
SETTINGS = json.loads(_FILE.read_text(encoding="utf-8"))

REQUIRED = {
    "state": ("name", "abbreviation"),
    "site": ("name", "domain"),
    "legislature": ("name", "chambers"),
    "counties": (),
    "county_abbreviations": (),
    "county_codes": (),
    "timezone": (),
    "term": ("length_years", "first_year_parity", "organization_day", "key", "label"),
    "bill_prefixes": ("house", "senate"),
    "source_hosts": ("legislature", "secretary_of_state"),
}


def get(*path):
    """A value by its keys: get("legislature", "name")."""
    v = SETTINGS
    for k in path:
        v = v[k]
    return v


STATE_NAME = get("state", "name")
STATE_ABBREVIATION = get("state", "abbreviation")
SITE_NAME = get("site", "name")
SITE_DOMAIN = get("site", "domain")
LEGISLATURE = get("legislature", "name")
CHAMBERS = get("legislature", "chambers")
COUNTIES = tuple(SETTINGS["counties"])
COUNTIES_LOWER = tuple(c.lower() for c in COUNTIES)
COUNTIES_UPPER = tuple(c.upper() for c in COUNTIES)
# The short form a roster prints ("Hills 22"), by name and by lower-case name.
COUNTY_ABBR = dict(SETTINGS["county_abbreviations"])
COUNTY_ABBR_LOWER = {c.lower(): a for c, a in COUNTY_ABBR.items()}
# The two-letter code GRANIT's layers and the district map use, by name and back.
COUNTY_CODE = dict(SETTINGS["county_codes"])
COUNTY_BY_CODE = {code: c for c, code in COUNTY_CODE.items()}
# The General Court's own number for each county (its Counties.txt: "06|Hillsborough|Hills."),
# which its roster prints beside a district's number ("06", "22"), by name.
COUNTY_NUMBER = dict(SETTINGS.get("county_numbers") or {})
# Every spelling of a county a roster uses, lower case, to its name.
COUNTY_LOOKUP = {**{c.lower(): c for c in COUNTIES}, **{a.lower(): c for c, a in COUNTY_ABBR.items()}}
TIMEZONE = SETTINGS["timezone"]
TERM = SETTINGS["term"]
BILL_PREFIXES = {k: tuple(v) for k, v in SETTINGS["bill_prefixes"].items()}
SOURCE_HOSTS = SETTINGS["source_hosts"]
# THE PARTIES (the model's design of 16 November 2026, step 3): one table of each party's
# letter, the site's words for it, the forms the files print it in and its colours as
# src/pages/app.css draws them, which the file's "parties" says field by field. The model reads
# it (entities.party_letters); the copies in the code are held to it by preflight
# (_party_copies_agree), and move onto it a reader at a time.
PARTIES = SETTINGS.get("parties") or {}
PARTY = dict(PARTIES.get("letters") or {})
PARTY_NONE = dict(PARTIES.get("none") or {})


def party_lookup(table=None):
    """{form, lower case: letter} of a table of parties (PARTIES where none is given): each
    party's letter, its spellings, and the site's words for it."""
    table = PARTIES if table is None else table
    out = {}
    for letter, row in (table.get("letters") or {}).items():
        for form in [letter, *(row.get("spellings") or []),
                     *(row.get(k) for k in ("name", "plural", "adjective", "party_name"))]:
            if form:
                out.setdefault(str(form).lower(), letter)
    return out


_LOOKUP = party_lookup()


def party_letters(printed, table=None):
    """The letters a party as a file prints it stands for, in the order printed, each once: "r"
    and "Republican" -> ("R",); "R/D", "r&d" and "REP/DEM" -> ("R", "D"); () where none is
    printed; and None where a part of it is a form the table does not know ("sgi", "u/d"), so
    that a party only partly read is never given as read."""
    look = _LOOKUP if table is None else party_lookup(table)
    whole = " ".join(str(printed or "").split()).lower()
    if whole in look:
        return (look[whole],)
    out = []
    for part in (p for p in re.split(r"[&/,\s]+", whole) if p):
        if part not in look:
            return None
        if look[part] not in out:
            out.append(look[part])
    return tuple(out)
