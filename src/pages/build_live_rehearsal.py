#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-12.1
"""
LIVE NOW, REHEARSED: every state a reader will meet, on past sittings, at a
stable address of a dry run's preview (the laptop manager, 8 November 2026,
at Alice's choice), so Live Now is seen and polished in November rather than
first on Organization Day.

    python3 src/pages/build_live_rehearsal.py --site site

    site/live/rehearse/index.html       the list of states, each linked
    site/live/rehearse/<state>.html     a state, at its moment
    site/live/rehearse/files/<state>/   the files that state's page reads

THIS RUNS ONLY ON THE BRANCH live/rehearsal, WHICH NEVER MERGES. Its step is
in that branch's build_all.py alone, so a dry run of the branch builds it and
the night, which builds main, never does. Every page is noindex, in no
sitemap and linked from nowhere but its own index, and says at its top that
it is a rehearsal and not live.

FROM THE RECORD, AS THE LIVE FILES WOULD HAVE BEEN:
- streams: collected/videos/*.csv, in git: each stream's real title and its
  real start and end (actual_start_utc, actual_end_utc), live or ended at the
  state's moment;
- roll calls: records/rollcalls/RollCallSummary_2026.txt, in git: each roll
  call's real number, bill, question, tally and time, read once its time has
  passed (a Senate roll call carries no time in the file, and is read once
  the Senate has risen, as the Senate saves its roll calls after);
- the docket's outcome on a roll call: the built site's own record of it
  (data/rollcalls.csv's passed), given to roll calls more than five minutes
  old at the moment, as the clerk's line follows the vote (a stand-in: the
  docket's own lines are not in git);
- the pages: build_live.page_body and build_live_session.morning_body, the
  builders' own, on the built site's calendar and bills.

A page runs its script at its moment on these files (live.js's
L.rehearsal): it asks the live API nothing.

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
import shutil

import build_live as BL
import build_live_session as BLS
import rollcall_parser as RP
import shell as S

OUT = Path("live") / "rehearse"
ROBOTS = '<meta name="robots" content="noindex">'
UTC = datetime.timezone.utc

# The two days: 10 March 2026, a Tuesday of Senate hearings, every one
# streamed; 19 August 2026, veto day, both chambers sitting, the House's
# overrides read through the morning and the Senate's after it rose.
COMMITTEES, VETO = datetime.date(2026, 3, 10), datetime.date(2026, 8, 19)

# Each state: its address, what a reader would be shown, and the moment.
# "page" is "live" (/live as it was) or "H"/"S" (that chamber's morning
# page). "streams"/"votes" say what each file holds: None for none at all.
STATES = [
    {"key": "a", "page": "live", "day": datetime.date(2026, 8, 18), "at": "2026-08-18T22:00:00Z",
     "title": "Nothing live, the next sitting ahead",
     "what": "The evening before veto day: nothing streaming; the next day's sessions on the calendar."},
    {"key": "b", "page": "live", "day": COMMITTEES, "at": "2026-03-10T14:00:00Z",
     "title": "Committees streaming, matched to their agenda",
     "what": "10 March 2026 at 10:00 ET: the Senate's committees live, each matched to its calendar card."},
    {"key": "c", "page": "live", "day": VETO, "at": "2026-08-19T15:50:00Z",
     "title": "The House sitting: Live Now",
     "what": "Veto day at 11:50 ET: the House session streaming, its roll calls read so far on the session card."},
    {"key": "c-day", "page": "H", "day": VETO, "at": "2026-08-19T15:50:00Z",
     "title": "The House sitting: its day's page",
     "what": "The same moment on the House's page for the day: vetoes overridden and sustained, In short "
             "under each, the bills not reached yet pending."},
    {"key": "d", "page": "live", "day": VETO, "at": "2026-08-19T18:00:00Z",
     "title": "Both chambers sitting",
     "what": "Veto day at 14:00 ET: both sessions streaming."},
    {"key": "d-senate", "page": "S", "day": VETO, "at": "2026-08-19T20:00:00Z",
     "title": "The Senate's day, its roll calls saved after it rose",
     "what": "Veto day at 16:00 ET: the Senate has risen and saved its roll calls."},
    {"key": "e", "page": "H", "day": VETO, "at": "2026-08-19T23:30:00Z", "done": True,
     "title": "The day over, before the night's record",
     "what": "Veto day at 19:30 ET: reading stopped for the day; a bill with no roll call says so."},
    {"key": "g-youtube", "page": "live", "day": VETO, "at": "2026-08-19T15:50:00Z", "streams_off": True,
     "title": "YouTube off",
     "what": "As state c, with the YouTube half switched off (control.json all-off)."},
    {"key": "g-stale", "page": "live", "day": VETO, "at": "2026-08-19T15:50:00Z", "stale": True,
     "title": "Live status stale",
     "what": "As state c, with the last look 40 minutes old: the page says it has not been checked since."},
    {"key": "g-votes-off", "page": "H", "day": VETO, "at": "2026-08-19T15:50:00Z", "votes_off": True,
     "title": "The database half off",
     "what": "As state c's day page, with the votes switched off (sql-off): the page says so."},
]
# State f is the record's own page the morning after, which the night built:
# the overlay asks for nothing older than 14 days, so it is as a reader meets
# it then.
RECORD = {"key": "f", "href": f"/session/H/{VETO.isoformat()}",
          "title": "The morning after: the record in place of the live copy",
          "what": "The House's page for veto day as the night built it from the record."}


def when(s):
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))


def iso(t):
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def videos(root=Path(".")):
    """[{video, chamber, title, start, end}] from the committed video index."""
    import proceedings
    out, seen = [], set()
    for f in proceedings.video_indexes(root):
        chamber = "S" if "senate" in f.name else "H"
        with f.open(encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                vid, start = r.get("video_id") or "", r.get("actual_start_utc") or ""
                if not vid or vid in seen or not start.endswith("Z"):
                    continue
                seen.add(vid)
                end = r.get("actual_end_utc") or ""
                out.append({"video": vid, "chamber": chamber, "title": r.get("title") or "",
                            "start": when(start), "end": when(end) if end.endswith("Z") else None})
    return out


def streams_file(day, at, vids, off=False, stale=False):
    """streams/<day>.json as the Worker would have written it at `at`."""
    rows = []
    for v in vids:
        if v["start"] > at or v["start"].astimezone(BL_TZ(v["start"])).date() != day:
            continue
        live = v["end"] is None or v["end"] > at
        rows.append({"video": v["video"], "chamber": v["chamber"], "title": v["title"],
                     "status": "live" if live else "ended", "scheduled": None, "started": iso(v["start"]),
                     "ended": None if live else iso(v["end"]), "embeddable": True,
                     "seen": {"playlist": iso(v["start"] + datetime.timedelta(minutes=2)), "search": None}})
    checked = at - datetime.timedelta(minutes=40 if stale else 1)
    status = ({"ok": False, "problem": "off", "since": iso(at - datetime.timedelta(hours=1))} if off
              else {"ok": True, "problem": None, "since": None})
    return {"kind": "live.streams", "day": day.isoformat(), "checked": iso(checked),
            "next_check": iso(checked + datetime.timedelta(minutes=2)), "status": status,
            "streams": [] if off else rows}


def BL_TZ(t):
    """New Hampshire's offset at `t`, by the rule build_live.nh_today keeps."""
    y = t.year

    def sunday(month, nth):
        d = datetime.date(y, month, 1)
        return d + datetime.timedelta(days=(6 - d.weekday()) % 7, weeks=nth - 1)
    start = datetime.datetime.combine(sunday(3, 2), datetime.time(7), UTC)
    end = datetime.datetime.combine(sunday(11, 1), datetime.time(6), UTC)
    return datetime.timezone(datetime.timedelta(hours=-4 if start <= t < end else -5))


def record_passed(site):
    """{roll_call id: passed} from the built site's record."""
    out = {}
    try:
        with (Path(site) / "data" / "rollcalls.csv").open(encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                p = (r.get("passed") or "").strip()
                if p in ("0", "1"):
                    out[r.get("roll_call") or ""] = p == "1"
    except OSError:
        pass
    return out


def roll_calls(day, root=Path(".")):
    """The day's roll calls from the record: [{body, seq, bill, question, yeas, nays, at}]; a
    Senate one has no time (at None)."""
    out = []
    path = root / "records" / "rollcalls" / f"RollCallSummary_{day.year}.txt"
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        p = line.split("|")
        if len(p) < 13 or p[1] not in ("H", "S"):
            continue
        try:
            t = datetime.datetime.strptime(p[3].strip(), "%m/%d/%Y %I:%M:%S %p")
        except ValueError:
            continue
        if t.date() != day:
            continue
        local = None
        if t.time() != datetime.time(0):
            guess = t.replace(tzinfo=UTC)
            local = t.replace(tzinfo=BL_TZ(guess)).astimezone(UTC)
        bill = RP.bill_number(p[4])
        out.append({"body": p[1], "seq": int(p[2]), "bill": bill, "as_recorded": p[4] or None,
                    "question": p[11].strip() or None, "yeas": int(p[5]), "nays": int(p[6]), "at": local})
    return sorted(out, key=lambda r: (r["body"], r["seq"]))


def votes_file(day, at, rcs, passed, senate_after, done=False, off=False):
    """votes/<day>.json as the Worker would have written it at `at`."""
    rows = []
    for r in rcs:
        seen = r["at"] if r["at"] is not None else (senate_after if r["body"] == "S" else None)
        if seen is None or seen > at:
            continue
        rid = f"{day.year}-{r['body']}-{r['seq']}"
        p = passed.get(rid)
        old = at - seen >= datetime.timedelta(minutes=5)
        rows.append({"id": rid, "body": r["body"], "seq": r["seq"],
                     "bill": f"2025-2026/{r['bill']}" if r["bill"] else None, "bill_as_recorded": r["as_recorded"],
                     "question": r["question"], "taken": iso(r["at"]) if r["at"] else None,
                     "saved": None if r["at"] else iso(senate_after), "keyed_by": None,
                     "yeas": r["yeas"], "nays": r["nays"], "present": None, "absent": None, "ballots": "",
                     "ballots_complete": False,
                     "docket": {"outcome": "Motion Adopted" if p else "Motion Failed"} if (p is not None and old) else None,
                     "first_seen": iso(seen), "note": None, "passed": None, "threshold_needed": None})
    state = "off" if off else "day_over" if done else "reading"
    return {"api": 1, "kind": "session.votes", "date": day.isoformat(), "provisional": True,
            "read_at": iso(at - datetime.timedelta(minutes=1)),
            "next_read_by": None if (done or off) else iso(at + datetime.timedelta(minutes=1)),
            "status": {"state": state, "problem": state if state != "reading" else None,
                       "since": iso(at - datetime.timedelta(hours=1)) if state != "reading" else None},
            "rollcalls": rows, "tallies": []}


def banner(state, at):
    local = at.astimezone(BL_TZ(at))
    return (f'<div class="lv-rehearse" role="note"><p><b>Rehearsal, not live.</b> {S.E(state["title"])}. '
            f'{S.E(state["what"])} The moment shown is {S.E(S.date_words(local.date(), "full"))}, '
            f'{local:%I:%M %p} Eastern, replayed from the record. This page is not indexed and is linked '
            f'from nowhere on the site. <a href="/live/rehearse/">Every state</a>.</p></div>')


def rehearse_js(at, files):
    return ('<script>window.GR_REHEARSE=' + json.dumps({"now": iso(at), "files": files}).replace("</", "<\\/")
            + ';</script>')


def page(site, base, path, title, body):
    html = S.page(S.template(site), path=path, base=base, title=f"{title} | Rehearsal | Granite Record",
                  description="A rehearsal of Live Now on a past sitting, for review; not live.",
                  og_title=title, globals={"GR_STATIC": True}, noscript="", skip_label="Skip to the page",
                  sr_title="", og_type="website", cite=False)
    html = html.replace('<div id="results"></div>', f'<div id="results">{body}</div>', 1)
    html = html.replace("</head>", f'{ROBOTS}\n<link rel="stylesheet" href="/live.css">\n</head>', 1)
    assert ROBOTS in html and "lv-rehearse" in html, f"{path}: not written as a rehearsal"
    return S.clean_links(html)


def build(site, base, root=Path(".")):
    site = Path(site)
    out = site / OUT
    out.mkdir(parents=True, exist_ok=True)
    vids, passed = videos(root), record_passed(site)
    rcs = {d: roll_calls(d, root) for d in (VETO, COMMITTEES)}
    # The Senate saves its roll calls after it rises: its stream's end.
    senate_end = max((v["end"] for v in vids if v["chamber"] == "S" and v["end"]
                      and v["start"].astimezone(BL_TZ(v["start"])).date() == VETO), default=None)
    senate_after = (senate_end or when("2026-08-19T19:15:00Z")) + datetime.timedelta(minutes=5)
    written = []
    for st in STATES:
        at, day, key = when(st["at"]), st["day"], st["key"]
        # The files under files/<state>/, not <state>/: a folder of a page's
        # own name beside <state>.html makes /live/rehearse/<state> ambiguous.
        folder = out / "files" / key
        folder.mkdir(parents=True, exist_ok=True)
        files = {}
        sf = streams_file(day, at, vids, off=st.get("streams_off"), stale=st.get("stale"))
        (folder / "streams.json").write_text(json.dumps(sf), encoding="utf-8")
        files["/api/live/streams"] = f"/{OUT.as_posix()}/files/{key}/streams.json"
        vf = votes_file(day, at, rcs.get(day, []), passed, senate_after, done=st.get("done"),
                        off=st.get("votes_off"))
        (folder / f"votes-{day.isoformat()}.json").write_text(json.dumps(vf), encoding="utf-8")
        files[f"/api/live/votes/{day.isoformat()}"] = f"/{OUT.as_posix()}/files/{key}/votes-{day.isoformat()}.json"
        if st["page"] == "live":
            sched = BL.schedule(site, day)
            body = (banner(st, at) + rehearse_js(at, files) + BL.page_body(sched, day))
        else:
            b = st["page"]
            body = (banner(st, at) + rehearse_js(at, files)
                    + BLS.morning_body(site, b, day, BLS.agenda(b, day))
                    + '<script src="/motions.js" defer></script><script src="/live.js" defer></script>')
        (out / f"{key}.html").write_text(page(site, base, f"/{OUT.as_posix()}/{key}.html", st["title"], body),
                                         encoding="utf-8")
        written.append(st)
    items = "".join(f'<li><a href="/{OUT.as_posix()}/{s["key"]}"><b>{S.E(s["key"])}</b>. {S.E(s["title"])}</a>'
                    f'<br><span class="lv-status">{S.E(s["what"])}</span></li>' for s in written + [RECORD]
                    if s["key"] != RECORD["key"]) + \
        (f'<li><a href="{RECORD["href"]}"><b>f</b>. {S.E(RECORD["title"])}</a><br>'
         f'<span class="lv-status">{S.E(RECORD["what"])}</span></li>')
    index = ('<div class="clist lvpage"><h1>Live Now, rehearsed</h1>'
             '<p class="lv-status">Each state a reader will meet, replayed on past sittings from the record. '
             'For review on a dry run\'s preview only: not indexed, linked from nowhere on the site.</p>'
             f'<ul class="lv-list">{items}</ul></div>')
    (out / "index.html").write_text(page(site, base, f"/{OUT.as_posix()}/index.html", "Live Now, rehearsed",
                                         '<div class="lv-rehearse" hidden></div>' + index), encoding="utf-8")
    for f in ("live.js", "live.css", "motions.js"):
        shutil.copyfile(_paths.locate(f"src/pages/{f}"), site / f)
    return written, sum(len(v) for v in rcs.values())


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    ap.add_argument("--site", default="site")
    ap.add_argument("--base", default="https://graniterecord.org")
    a = ap.parse_args()
    written, n = build(a.site, a.base)
    # SILENCE IS NOT SUCCESS: a rehearsal of veto day with no roll calls read
    # from the record would draw empty pages and look like a quiet day.
    if not n:
        raise SystemExit("live rehearsal: no roll calls for 19 August or 10 March 2026 in records/rollcalls/")
    print(f"live rehearsal: {len(written)} states at /{OUT.as_posix()}/ ({n} roll calls from the record)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
