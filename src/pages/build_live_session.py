#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-30.4
"""
The session days' side of the live layer (design sections 4.2 to 4.4),
written by the night after the session-day pages:

    site/session/<H|S>/<date>.json   each dated session-day page's roll calls
                                     as the record holds them, in the
                                     session.votes shape with provisional false
    site/session/<H|S>/<today>.html  the morning page: on a day the chamber's
                                     floor is on the calendar and the record
                                     has no page for it yet, the day's dated
                                     address, filled in by live.js as the
                                     votes are read
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

ONE PAGE AT ONE ADDRESS (the owner, 30 October 2026). On the morning of a
sitting, /session/<B>/<date> exists before the record has the day: the
morning page.
- It is written for the build's own day only, never another. It says the
  chamber is scheduled to sit, never that it sat.
- It draws the day's bills in the calendar's order as the session page's
  own cards (components.bill_card), each with its committee's report, and
  live.js fills each card's votes as they are read.
- It is noindex, and in no list, no sitemap and no days.json.
- The next night the session-day step writes the record's page over it.
  Without one, the page is gone: the nightly's site starts empty, and on a
  site kept between builds this step removes a morning page of an earlier
  day.
- It carries no record day file: an empty "record" of a sitting still to
  come would say the record holds no roll call.
- /session/<B>/today is retired, and an earlier build's copy goes.

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


def day_files(site, seen=None, skip=()):
    """{(body, date): session.votes document} for every dated page but the
    morning pages in `skip` ({(body, date)}): those are a sitting still to
    come, and an empty "record" of it would say the record holds no roll
    call. `seen`, a dict, gets what was read: {"rollcalls_csv": bool,
    "votes_csvs": n}."""
    seen = {} if seen is None else seen
    site = Path(site)
    want = {b: page_dates(site, b) - {d for (bb, d) in skip if bb == b} for b in "HS"}
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


# ---- the morning page: the dated address from the morning of a sitting ----------
MORNING = 'data-morning="1"'
TOP_LINE = ("Votes as they are read. Who spoke and the debate come with the {journal}, "
            "which can take months.")
JOURNAL = {"H": "House Journal", "S": "Senate Journal"}


def is_morning(path):
    """Whether a dated page is a morning page (this step's), not the record's."""
    try:
        return MORNING in Path(path).read_text(encoding="utf-8")
    except OSError:
        return False


def agenda(body, today, rows=None):
    """The bills on the chamber's floor today, in the calendar's order, each
    once: [(term, bill)]. From proceedings.csv's floor rows (build_calendar's
    FLOOR_KINDS), the same rows the Calendar's floor card and /live read."""
    import build_calendar as BC
    if rows is None:
        import proceedings
        rows = proceedings.load()
    iso, out = today.isoformat(), []
    for r in rows:
        if ((r.get("date") or "")[:10] == iso and (r.get("body") or "").strip().upper() == body
                and (r.get("kind") or "").strip().lower() in BC.FLOOR_KINDS and r.get("bill")):
            k = (r.get("term") or "", r["bill"].strip().upper())
            if k not in out:
                out.append(k)
    return out


def morning_cards(site, body, today, bills):
    """Each bill as the session page's card (components.bill_card, as
    build_session_pages draws it), with the committee's report the chamber
    acts on (its recommendation_on and recommendation_html) and an empty
    place live.js fills with the day's roll calls."""
    import build_session_pages as BSP
    import committee_acts as CA
    import components as C
    import session_days
    rows, codes = BSP.load_rows(site), BSP.load_codes(site)
    titles, years = BSP.load_titles(site)
    try:
        data = json.loads(Path(session_days.NARRATIVES).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    out = []
    for term, bill in bills:
        row = rows.get((term, bill)) or {}
        year = years.get((term, bill)) or row.get("year") or ""
        acts = CA.acts(((data.get(term) or {}).get(bill) or {}).get("events"))
        rec = BSP.recommendation_on(acts, body, today.isoformat(), [])
        chip_w = row.get("chip") or ""
        topic = "" if (row.get("topic") == "Miscellaneous"
                       and row.get("topic_by") == "granite record") else (row.get("topic") or "")
        sponsor = ({"display_full": row.get("sponsor_label"), "slug": row.get("sponsor_slug") or "",
                    "party": row.get("sponsor_party") or ""} if row.get("sponsor_label") else None)
        out.append(C.bill_card({
            "id": bill, "href": f"bill/{year}/{bill.lower()}.html" if year else "",
            "n": re.sub(r"^([A-Z]+)(\d)", r"\1 \2", bill), "year": year,
            "word": C.card_word(chip_w, row.get("passage")) if chip_w else "",
            "cls": (C.WORDBOOK["chips"]["chip"].get(chip_w)
                    or C.WORDBOOK["chips"]["kind"].get(row.get("kind") or "", "")),
            "title": titles.get((term, bill)) or row.get("title") or "",
            "byline": C.bill_byline(sponsor, row.get("committees") or [], topic, term, codes),
            "notes": C.rail_html(row.get("rail") or [], chip_w == "Died"),
            "line": BSP.recommendation_html(rec, body, term, codes, S.E)
                    + f'<div class="lv-rcs" data-bill="{S.E(bill)}"></div>',
            "rail": "", "open": None}))
    return out


def morning_body(site, body, today, bills):
    import build_session_pages as BSP
    import components as C
    import proceedings
    name, iso = CHAMBER_NAME[body], today.isoformat()
    day_words = S.date_words(today, "long")
    cards = morning_cards(site, body, today, bills)
    n = len(bills)
    line = (f"The {name} is scheduled to sit today"
            + (f", with {n} bill{'s' if n != 1 else ''} on its calendar." if n else "."))
    # The record page's head (build_session_pages' record_head call): the same
    # trail, up to the chamber's session days at the day's term, and the top
    # line as its note, where a Senate record page says its journal has no
    # debate.
    days = (f"{S.canon(f'session/{BSP.CHAMBER_PAGE[body]}.html')}"
            f"?term={proceedings.vote_term(iso[:4], iso)}#day-{iso}")
    return (f'<div class="wkpage sesspage lvday">'
            + C.record_head({"trail": [["Committees", "committees.html"], [f"{name} Session Days", days],
                                       ["Session Day", ""]],
                             "title": S.E(f"The {name}, {day_words}"), "line": S.E(line), "kind": "day"})
            + f'<p class="rnote lv-top">{S.E(TOP_LINE.format(journal=JOURNAL[body]))}</p>'
            f'<div id="live-day" {MORNING} data-day="{iso}" data-body="{body}">'
            f'<p id="live-day-status" class="lv-status"></p>'
            f'<noscript><p class="lv-status">This page fills in with the {name}\'s votes as they are '
            f'read, which needs its script.</p></noscript></div>'
            f'<div class="w4s"><section class="w4 wday" id="order"><div class="wside">'
            f'<h2 class="w4h">The Day in Order</h2></div>'
            f'<div class="w4b" id="lv-cards">{"".join(cards)}</div></section>'
            f'<section class="w4" id="nobill" hidden><h2 class="w4h">Votes on No Bill</h2>'
            f'<div class="w4b" id="lv-nobill"></div></section></div>'
            # The term's bills by the year each was introduced, for the link of
            # a bill that is not on the calendar (build_live.bill_years).
            f'<script type="application/json" id="live-bills">'
            f'{json.dumps(BL.bill_years(site, today), separators=(",", ":")).replace("</", "<\\/")}</script>'
            '</div>')


def write_morning(site, base, body, today, rows=None):
    """session/<B>/<today>.html, the morning page, where the chamber's floor
    has today on the calendar and the record has no page for the day. Never
    for another day than the build's. Returns the path written, or None."""
    site = Path(site)
    out = site / "session" / body / f"{today.isoformat()}.html"
    if out.is_file() and not is_morning(out):
        return None                                   # the record's page: the overlay fills it
    bills = agenda(body, today, rows)
    if not bills and not floor_today(site, body, today):
        if out.is_file():
            out.unlink()                              # a morning page of a sitting no longer on the calendar
        return None
    name = CHAMBER_NAME[body]
    path = f"/session/{body}/{today.isoformat()}.html"
    html = S.page(S.template(site), path=path, base=base,
                  title=f"The {name}, {S.date_words(today, 'full')} | Granite Record",
                  description=f"The {name}'s votes today, as they are read, on the bills on its calendar.",
                  og_title=f"The {name}, {S.date_words(today, 'full')}", globals={"GR_STATIC": True},
                  noscript="", skip_label="Skip to the votes", sr_title="", og_type="website", cite=False)
    html = html.replace('<div id="results"></div>',
                        f'<div id="results">{morning_body(site, body, today, bills)}</div>', 1)
    assert MORNING in html, f"{path}: the template has no results slot"
    html = html.replace("</head>", '<meta name="robots" content="noindex">\n'
                                   '<link rel="stylesheet" href="/live.css">\n</head>', 1)
    html = html.replace("</body>", '<script src="/live.js" defer></script>\n</body>', 1)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(S.clean_links(html), encoding="utf-8")
    return out


def floor_today(site, body, today):
    """Whether /live's schedule has the chamber's floor today (a sitting with
    no bills listed yet: Organization Day)."""
    try:
        sched = json.loads((Path(site) / "live" / "schedule.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return any(r.get("kind") == "floor" and body in (r.get("chamber") or "")
               for r in (sched.get("days") or {}).get(today.isoformat()) or [])


def write(site, base, today, seen=None, rows=None):
    site = Path(site)
    # /session/<B>/today is retired (the owner, 30 October 2026): the dated
    # address is the one page. An earlier build's copy goes.
    # A morning page of an earlier day goes too, as it does in the nightly's
    # empty site: the record's page takes the address when the record has it.
    for b in "HS":
        old = site / "session" / b / "today.html"
        if old.is_file():
            old.unlink()
        for d in sorted(page_dates(site, b) - {today.isoformat()}):
            if is_morning(site / "session" / b / f"{d}.html"):
                (site / "session" / b / f"{d}.html").unlink()
    mornings = [p for b in "HS" if (p := write_morning(site, base, b, today, rows))]
    docs = day_files(site, seen, skip={(p.parent.name, p.stem) for p in mornings})
    wrote, gone = write_day_files(site, docs)
    (site / "schema").mkdir(exist_ok=True)
    shutil.copyfile(_paths.locate(SCHEMA.as_posix()), site / SCHEMA)
    for f in ("live.js", "live.css"):                      # the same files build_live copies
        shutil.copyfile(_paths.locate(f"src/pages/{f}"), site / f)
    if seen is not None:
        seen["mornings"] = [f"{p.parent.name}/{p.name}" for p in mornings]
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
    mornings = seen.get("mornings") or []
    print(f"live session: {wrote} day files ({n:,} roll calls), {SCHEMA.as_posix()}; "
          + (f"morning page(s) {', '.join(mornings)}" if mornings else "no sitting on the calendar today")
          + (f"; removed {len(gone)} for pages gone: {', '.join(gone[:5])}" if gone else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
