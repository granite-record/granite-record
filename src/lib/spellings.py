#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-10.1
"""
A member's name as the record misspells it, and the name it means.

The person, 10 October 2026: "Rep. Poloszaj" on HB 1689's session day is
Representative Tom Ploszaj, misspelled in the General Court's own record.
No matcher could link it -- there is no Poloszaj -- and none should guess:
a name one letter from a member's is often another member's. So the
spelling is a person's correction, in the "spellings" section of
corrections/member_corrections.json, keyed "H|Poloszaj" (the chamber, then
the name as the record writes it) with "means" the surname as the roster
spells it:

    "spellings": {
      "H|Poloszaj": {"means": "Ploszaj", "seen": "...", "why": "..."}
    }

The page keeps the record's words; only the name looked up changes, and it
is then matched by every rule an ordinary name is (one member of the
chamber, serving that term). This module only reads that file.
"""

import json
import re

import _paths

PATH = _paths.ROOT / "corrections" / "member_corrections.json"


def load(path=None):
    """{(chamber, name lower): means} from the file's "spellings" section;
    {} where there is none."""
    try:
        doc = json.loads((path or PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out = {}
    for key, v in ((doc or {}).get("spellings") or {}).items():
        if key.startswith("_") or "|" not in key or not isinstance(v, dict):
            continue
        ch, said = key.split("|", 1)
        means = str(v.get("means") or "").strip()
        if means and said.strip():
            out[(ch.strip().upper()[:1], said.strip().lower())] = means
    return out


def respell(body, name, table):
    """`name` with a misspelled word the table names put right, for looking
    the member up: "Poloszaj" -> "Ploszaj", "Tom Poloszaj" -> "Tom Ploszaj".
    Whole words only, and the whole name first."""
    if not table or not name:
        return name
    ch = (body or "").strip().upper()[:1]
    whole = table.get((ch, name.strip().lower()))
    if whole:
        return whole
    return re.sub(r"[\w'’-]+", lambda m: table.get((ch, m.group(0).lower()), m.group(0)), name)
