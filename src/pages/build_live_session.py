#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-30.3
"""
The session days' side of the live layer (design sections 4.2 to 4.4),
written by the night after the session-day pages:

    site/session/<H|S>/<date>.json   each dated session-day page's roll calls
                                     as the record holds them, in the
                                     session.votes shape with provisional false
    site/session/<H|S>/today.html    "The House today" and "The Senate today":
                                     two pages that never move
    site/schema/session.votes.json   the shape both writers keep (schema/)

    python3 src/pages/build_live_session.py --site site [--today 2027-01-07]

ONE SHAPE, TWO WRITERS. The Worker writes /api/live/votes/<date> during the
day, read from the General Court's database; this writes the record's copy
of each sitting every night, from the roll-call files the site already
publishes (data/rollcalls.csv and data/votes-<term>.csv). A page draws both
with one function, and where both hold a roll call's id the record's wins
(section 4.3). Every file is checked against schema/session.votes.json
before it is written, and the step stops on one that does not hold.

A DAY'S FILE GOES WITH ITS PAGE. One is written for every dated page in
session/<B>/ and none for a date with no page, so a sitting the session-day
step removes (build_session_pages.prune) loses its file on the next run of
this one. The term files beside them (2025-2026.json) are that step's and
are not touched.

A roll call is filed under its roll-call file's date, which is the date the
database's VoteDate gives and so the date the Worker files it under. The
record's `taken` is null: the roll-call file's clock is not in the published
CSV, and a time this step cannot vouch for is not written. `passed` and
`threshold_needed` are the record's own (vote_passage.py), which the live
file never has: the Worker never works out whether a motion carried.

THE TODAY PAGES publish no sitting. They hold the Calendar's floor card for
the build's day, marked with its date so live.js can hide it on another day;
the chamber's list of session days; a <noscript> line; and empty places that
live.js fills from /api/live/streams and /api/live/votes/<the reader's New
Hampshire date>. They are noindex, in no list and in no sitemap.

Nothing here asks the network.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import csv
import datetime
import json
import re
import shutil

import build_date
import build_live as BL
import live_gen as LG
import rollcall_parser as RP
import shell as S

SCHEMA = Path("schema") / "session.votes.json"
DATE_PAGE = re.compile(r"\d{4}-\d{2}-\d{2}")
CHAMBER_NAME = {"H": "House", "S": "Senate"}
CHAMBER_LIST = {"H": "session/house.html", "S": "session/senate.html"}
SOURCE = ("The night's record: the General Court's roll-call files as this site publishes them "
          "(/data/rollcalls.csv and /data/votes-<term>.csv).")
NOTES = {"record": "This is the night's record of the day. A page draws it with the day's live file "
                   "(/api/live/votes/<date>), and where both hold a roll call's id this one wins.",
         "taken": "taken is null here: the record's clock for a roll call is not in the published files."}


# ---- the schema, checked by hand ----------------------------------------------
class Invalid(ValueError):
    pass


def check(doc, schema, root=None, where="$"):
    """Raise Invalid where `doc` breaks `schema`. The part of JSON Schema the
    file uses (its description lists it); tests/live/schema.js is the same
    rule in node, and both run tests/live/schema_cases.json."""
    root = schema if root is None else root
    if "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/$defs/"):
            raise Invalid(f"{where}: unknown $ref {ref}")
        return check(doc, root["$defs"][ref.split("/")[-1]], root, where)
    # Compared as JSON compares: true is not 1 (Python's True == 1 is).
    if "const" in schema and not _same(doc, schema["const"]):
        raise Invalid(f"{where}: {doc!r} is not {schema['const']!r}")
    if "enum" in schema and not any(_same(doc, e) for e in schema["enum"]):
        raise Invalid(f"{where}: {doc!r} is not one of {schema['enum']}")
    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_is(doc, t) for t in types):
            raise Invalid(f"{where}: {type(doc).__name__} is not {'/'.join(types)}")
    # JavaScript's $ (no m flag) is the end of the string; Python's also
    # matches before a final newline, so "2027-01-07\n" would pass here alone.
    if isinstance(doc, str) and "pattern" in schema and not re.search(schema["pattern"].replace("$", r"\Z"), doc):
        raise Invalid(f"{where}: {doc!r} does not match {schema['pattern']}")
    if _is(doc, "integer") and "minimum" in schema and doc < schema["minimum"]:
        raise Invalid(f"{where}: {doc} is below {schema['minimum']}")
    if isinstance(doc, dict):
        for k in schema.get("required", ()):
            if k not in doc:
                raise Invalid(f"{where}: no {k}")
        props = schema.get("properties", {})
        extra = schema.get("additionalProperties", True)
        for k, v in doc.items():
            if k in props:
                check(v, props[k], root, f"{where}.{k}")
            elif extra is False:
                raise Invalid(f"{where}: {k} is not a field of this shape")
            elif isinstance(extra, dict):
                check(v, extra, root, f"{where}.{k}")
    if isinstance(doc, list) and "items" in schema:
        for i, v in enumerate(doc):
            check(v, schema["items"], root, f"{where}[{i}]")


def _same(a, b):
    return type(a) is type(b) and a == b if isinstance(a, bool) or isinstance(b, bool) else a == b


def _is(v, t):
    return {"object": isinstance(v, dict), "array": isinstance(v, list), "string": isinstance(v, str),
            "boolean": isinstance(v, bool), "null": v is None,
            # JSON has one number: 2.0 is an integer to JavaScript, and so here.
            "integer": (isinstance(v, int) and not isinstance(v, bool)) or (isinstance(v, float) and v.is_integer()),
            "number": isinstance(v, (int, float)) and not isinstance(v, bool)}[t]


def schema():
    return json.loads(_paths.locate(SCHEMA.as_posix()).read_text(encoding="utf-8"))


# ---- the record's day files ---------------------------------------------------
def _int(s):
    s = (s or "").strip()
    return int(s) if s.lstrip("-").isdigit() else None


def page_dates(site, body):
    folder = Path(site) / "session" / body
    return {f.stem for f in folder.glob("*.html") if DATE_PAGE.fullmatch(f.stem)} if folder.is_dir() else set()


def day_files(site, seen=None):
    """{(body, date): session.votes document} for every dated page. `seen`, a
    dict, gets what was read: {"rollcalls_csv": bool, "votes_csvs": n}."""
    seen = {} if seen is None else seen
    site = Path(site)
    want = {b: page_dates(site, b) for b in "HS"}
    rcs, order = {}, []
    path = site / "data" / "rollcalls.csv"
    seen["rollcalls_csv"] = path.is_file()
    seen["votes_csvs"] = 0
    if path.is_file():
        with path.open(encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                body, date = r.get("body"), r.get("date") or ""
                if body in want and date in want[body] and r.get("roll_call"):
                    rcs[r["roll_call"]] = r
                    order.append(r["roll_call"])
    ballots = {k: {} for k in rcs}
    for vf in sorted((site / "data").glob("votes-*.csv")):
        seen["votes_csvs"] += 1
        with vf.open(encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                got = ballots.get(r.get("roll_call"))
                if got is None or not (r.get("member_id") or "").isdigit():
                    continue
                word = r.get("vote") or ""
                if word not in LG.BALLOT_CHARS:
                    raise SystemExit(f"{vf.name}: the vote {word!r} has no character in the session.votes "
                                     f"shape (live_gen.BALLOT_CHARS); what it means on the page is a decision")
                got[r["member_id"]] = LG.BALLOT_CHARS[word]
    out = {}
    for body in "HS":
        for date in sorted(want[body]):
            mine = [rcs[k] for k in order if rcs[k]["body"] == body and rcs[k]["date"] == date]
            members = sorted({m for r in mine for m in ballots[r["roll_call"]]}, key=int)
            rows = []
            for r in sorted(mine, key=lambda r: _int(r.get("number")) or 0):
                got = ballots[r["roll_call"]]
                line = "".join(got.get(m, ".") for m in members)
                yeas, nays = _int(r.get("yeas")) or 0, _int(r.get("nays")) or 0
                passed = {"1": True, "0": False}.get((r.get("passed") or "").strip())
                # The bill as the record reads the field, as the Worker's
                # billNumber does: a procedural vote ("SUSPRULE", "RULE 1-2")
                # names no bill, and keeps its words in bill_as_recorded.
                bill = RP.bill_number(r.get("bill"))
                rows.append({
                    "id": r["roll_call"], "body": body, "seq": _int(r.get("number")),
                    "bill": f"{r['term']}/{bill}" if bill else None,
                    "bill_as_recorded": r.get("bill") or None, "question": r.get("question") or None,
                    "taken": None, "saved": None, "keyed_by": None,
                    "yeas": yeas, "nays": nays, "present": None, "absent": None,
                    "ballots": line,
                    # merge.js's rule: Y and N agree with the count, and
                    # something was recorded (a 0-0 set of "." is not).
                    "ballots_complete": bool(line) and line.count("Y") == yeas and line.count("N") == nays
                                        and (yeas + nays > 0 or bool(line.strip("."))),
                    "docket": None, "first_seen": None, "note": None,
                    "passed": passed, "threshold_needed": _int(r.get("threshold_needed"))})
            out[(body, date)] = {
                "api": 1, "kind": "session.votes", "date": date, "provisional": False,
                "read_at": None, "next_read_by": None,
                "status": {"state": "record", "problem": None, "since": None},
                "source": SOURCE,
                "record": {"H": f"/session/H/{date}.json", "S": f"/session/S/{date}.json"},
                "members": {"H": members if body == "H" else [], "S": members if body == "S" else []},
                "rollcalls": rows, "tallies": [], "notes": dict(NOTES)}
    return out


def write_day_files(site, docs, shape=None):
    """Writes each document after checking it; removes a date's file whose page is gone."""
    site, shape = Path(site), shape or schema()
    for (body, date), doc in docs.items():
        try:
            check(doc, shape)
        except Invalid as e:
            raise SystemExit(f"session/{body}/{date}.json does not hold to {SCHEMA.as_posix()}: {e}")
    wrote = 0
    for (body, date), doc in sorted(docs.items()):
        f = site / "session" / body / f"{date}.json"
        text = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
        if not f.is_file() or f.read_text(encoding="utf-8") != text:
            f.write_text(text, encoding="utf-8")
        wrote += 1
    gone = []
    for body in "HS":
        folder = site / "session" / body
        if not folder.is_dir():
            continue
        pages = page_dates(site, body)
        for f in sorted(folder.glob("*.json")):
            if DATE_PAGE.fullmatch(f.stem) and f.stem not in pages:
                f.unlink()
                gone.append(f"{body}/{f.name}")
    return wrote, gone


# ---- the two pages that never move ---------------------------------------------
def floor_card(site, body, today):
    """The Calendar's floor card for `today`, from live/schedule.json, or ""."""
    try:
        sched = json.loads((Path(site) / "live" / "schedule.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    for r in (sched.get("days") or {}).get(today.isoformat()) or []:
        if r.get("kind") == "floor" and body in (r.get("chamber") or "") and r.get("card"):
            return r["card"]
    return ""


def today_body(site, body, today):
    name = CHAMBER_NAME[body]
    iso = today.isoformat()
    card = floor_card(site, body, today)
    dated = (Path(site) / "session" / body / f"{iso}.html").is_file()
    return (f'<div class="clist lvpage lvtoday"><h1>The {name} today</h1>'
            f'<div id="live-today" data-body="{body}" data-built="{iso}">'
            f'<p id="live-today-day" class="lv-status" hidden></p>'
            f'<p id="live-today-status" class="lv-status"></p>'
            f'<noscript><p class="lv-status">Today\'s roll calls reach the {name}\'s session pages '
            f'by tomorrow morning.</p></noscript>'
            + '<p id="live-today-dated" class="lv-dated-js" hidden></p>'
            + (f'<p class="lv-dated" data-day="{iso}">Today\'s page: '
               f'<a href="{S.E(S.canon(f"session/{body}/{iso}.html"))}">/session/{body}/{iso}</a></p>'
               if dated else "")
            + '<div id="live-today-stream" class="lv-streams"></div>'
            + (f'<div class="lv-floor" data-day="{iso}"><h2>On the calendar</h2>{card}</div>' if card else "")
            + '<h2>Roll calls</h2>'
            '<ol id="live-today-votes" class="lv-votes" reversed hidden></ol>'
            '<p id="live-today-votes-status" class="lv-status"></p>'
            '<p class="lv-provisional" hidden>Provisional: the night\'s record replaces this tomorrow '
            'morning; excusals settle days later.</p>'
            + ('<p class="lv-senate" hidden>Senate names follow once the Senate enters them, usually '
               'that afternoon or the next day.</p>' if body == "S" else "")
            + '</div>'
            f'<p class="lv-list"><a href="{S.E(S.canon(CHAMBER_LIST[body]))}">Every {name} session day</a></p>'
            # The term's bills by the year each was introduced, for a roll
            # call's bill link (build_live.bill_years, live.js L.billHref).
            f'<script type="application/json" id="live-bills">'
            f'{json.dumps(BL.bill_years(site, today), separators=(",", ":")).replace("</", "<\\/")}</script>'
            '<script src="live.js" defer></script></div>')


def write_today(site, base, body, today):
    site = Path(site)
    name = CHAMBER_NAME[body]
    path = f"/session/{body}/today.html"
    html = S.page(S.template(site), path=path, base=base, title=f"The {name} today | Granite Record",
                  description=f"The {name}'s roll calls today, read during the sitting, and its stream.",
                  og_title=f"The {name} today", globals={"GR_STATIC": True}, noscript="",
                  skip_label="Skip to the roll calls", sr_title="", og_type="website", cite=False)
    html = html.replace('<div id="results"></div>', f'<div id="results">{today_body(site, body, today)}</div>', 1)
    assert 'id="live-today"' in html, f"{path}: the template has no results slot"
    html = html.replace("</head>", '<meta name="robots" content="noindex">\n'
                                   '<link rel="stylesheet" href="live.css">\n</head>', 1)
    out = site / "session" / body / "today.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(S.clean_links(html), encoding="utf-8")
    return out


def write(site, base, today, seen=None):
    site = Path(site)
    docs = day_files(site, seen)
    wrote, gone = write_day_files(site, docs)
    for b in "HS":
        write_today(site, base, b, today)
    (site / "schema").mkdir(exist_ok=True)
    shutil.copyfile(_paths.locate(SCHEMA.as_posix()), site / SCHEMA)
    for f in ("live.js", "live.css"):                      # the same files build_live copies
        shutil.copyfile(_paths.locate(f"src/pages/{f}"), site / f)
    return wrote, gone, docs


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    ap.add_argument("--site", default="site")
    ap.add_argument("--base", default="https://graniterecord.org")
    ap.add_argument("--today", help="the day to write for, YYYY-MM-DD (default: the build's)")
    a = ap.parse_args()
    today = datetime.date.fromisoformat(a.today) if a.today else build_date.today()
    seen = {}
    wrote, gone, docs = write(a.site, a.base, today, seen)
    n = sum(len(d["rollcalls"]) for d in docs.values())
    # SILENCE IS NOT SUCCESS: with the roll-call files missing, every day file
    # would be written empty and the step exit 0.
    if wrote:
        missing = ([] if seen.get("rollcalls_csv") else ["data/rollcalls.csv"]) + \
                  ([] if seen.get("votes_csvs") else ["data/votes-<term>.csv"])
        if missing:
            raise SystemExit(f"live session: {wrote} dated pages, and no {' or '.join(missing)} to read "
                             f"their roll calls from (bulk downloads runs before this step)")
        if not n:
            raise SystemExit(f"live session: {wrote} dated pages and not one roll call filed under their dates")
        balloted = sum(1 for d in docs.values() for r in d["rollcalls"] if r["ballots"].strip("."))
        if not balloted:
            raise SystemExit(f"live session: {n:,} roll calls and not one ballot read for them")
    print(f"live session: {wrote} day files ({n:,} roll calls), session/H/today.html and "
          f"session/S/today.html, {SCHEMA.as_posix()}"
          + (f"; removed {len(gone)} for pages gone: {', '.join(gone[:5])}" if gone else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
