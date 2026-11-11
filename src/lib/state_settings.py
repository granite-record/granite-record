#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-11.2
"""
The state's facts, read from src/lib/state_settings.json.

    import state_settings as ST
    ST.COUNTIES          # ("Belknap", "Carroll", ...), in the order the file lists them
    ST.TIMEZONE          # "America/New_York"
    ST.get("legislature", "name")

WHY A JSON FILE. A fork for another state edits data, not code; the file is
read by the same loader whatever its values, and a script in another language
can read it too. A Python module would make the edit a code change.

WHAT A FORK STILL CHANGES is written in the file's "_about" key: this file
holds only the facts that were repeated, or that a fork would change first.
preflight loads it, checks every key, and fails on a second literal county list.
"""
import json

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
    "term": ("length_years", "first_year_parity", "organization_day"),
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
# Every spelling of a county a roster uses, lower case, to its name.
COUNTY_LOOKUP = {**{c.lower(): c for c in COUNTIES}, **{a.lower(): c for c, a in COUNTY_ABBR.items()}}
TIMEZONE = SETTINGS["timezone"]
TERM = SETTINGS["term"]
BILL_PREFIXES = {k: tuple(v) for k, v in SETTINGS["bill_prefixes"].items()}
SOURCE_HOSTS = SETTINGS["source_hosts"]
