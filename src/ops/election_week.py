#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-29.1
"""
Election week's routine work, around the one step a person does: saving the
Secretary of State's results files in a browser.

    python3 src/ops/election_week.py status  [--year 2026]
    python3 src/ops/election_week.py check   --year 2026 --url <the results page> [--site site]
    python3 src/ops/election_week.py draft-matches  [--report logs/election_week.step.txt]
    python3 src/ops/election_week.py draft-recounts --schedule <saved file> --day YYYY-MM-DD
                                                     [--deadline 2026-11-06] [--election 2026-11-03]
    python3 src/ops/election_week.py draft-cacr --file <saved question spreadsheet> --url <page>
                                                [--label "Question No. 1"] [--bill CACR13]

Asks nobody anything: no request to sos.nh.gov, the General Court or anyone.

WHY THE SAVE STAYS A PERSON'S (29 October 2026). The results files are saved
by a person in a browser (the person's decision of 16 October 2026,
parse_sos_results.py), sos.nh.gov refuses scripted clients -- the laptop's
own requests met 403 on 12 October (src/fetch/other/guide_sources.py) --
and nothing records where the 2026 page will put its files. So this does
everything around the save and nothing in its place.

    status          which of the eleven files (ten counties' House results
                    and the State Senate's) are saved, which are missing, and
                    any later numbered upload (_N, as after a recount) that
                    the collected file has not read yet. Touches no file.
    check           for a scheduled task. Until all eleven are saved it says
                    how many are, and stops. With all eleven it runs
                    parse_sos_results.py --year Y --url U and then
                    build_members_elect.py --site S, keeps what each printed
                    in logs/, drafts the matches (draft-matches), and writes
                    logs/election_week.md in plain words: FILES, REFUSED,
                    FLAGGED, NOT LINKED, NEW, DO NOT ADD UP, NOTES. Then it
                    is done (logs/election_week.state.json) and later runs
                    only say so -- until a file it has not read is saved, a
                    recount's later upload, when it runs again once.
    draft-matches   a DRAFT of corrections/members_elect.json's "matches"
                    from the step's NOT LINKED and NEW lines: each name with
                    the member the step names as likely ("Label [id]", where
                    it names exactly one), or null, and the step's own words
                    as the evidence. Written to logs/, never to corrections/.
    draft-recounts  a DRAFT "not_final" block and "recount_deadline" from
                    the Secretary of State's recount schedule as a person
                    saved it (its text: .txt, .csv, or a PDF's text), each
                    race it names as a district of site/districts.json, and
                    every line that names a district it could not place.
    draft-cacr      a DRAFT of CACR 13's row of corrections/ballot_results.json
                    from the question's results spreadsheet: the statewide
                    Yes and No, refused rather than guessed where the sheet
                    does not show one totals row under one Yes and one No.

Every draft is a file in logs/ for the person to read and copy. corrections/
is the person's (CLAUDE.md); nothing here opens it to write.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import datetime
import hashlib
import json
import re
import subprocess

import child
import parse_sos_results as PSR

LOGS = Path("logs")
REPORT = LOGS / "election_week.md"
STATE = LOGS / "election_week.state.json"
PARSER_OUT = LOGS / "election_week.parse.txt"
STEP_OUT = LOGS / "election_week.step.txt"
MATCHES_DRAFT = LOGS / "members_elect.matches.draft.json"
RECOUNTS_DRAFT = LOGS / "members_elect.recounts.draft.json"
CACR_DRAFT = LOGS / "ballot_results.cacr.draft.json"
EXPECTED = len(PSR.COUNTIES) + 1


# ---- the saved files -----------------------------------------------------------

def saved(year, root="."):
    """{"house": {county: [paths, by upload]}, "senate": [paths], "other":
    [names]}: what is saved for `year` in records/sources/, read by the
    reader's own name patterns. Opens no file."""
    d = Path(root) / PSR.SOURCES
    out = {"house": {}, "senate": [], "other": []}
    for p in sorted(d.glob(f"{year}-ge-*")) if d.is_dir() else []:
        m = PSR.HOUSE_FILE.match(p.name)
        if m and m.group(1) == str(year) and m.group(2) in PSR.COUNTIES:
            out["house"].setdefault(m.group(2), []).append(p)
        elif PSR.SENATE_FILE.match(p.name) and p.name.startswith(f"{year}-"):
            out["senate"].append(p)
        else:
            out["other"].append(p.name)
    key = lambda p: (PSR.upload_number(p), p.name)
    out["house"] = {c: sorted(ps, key=key) for c, ps in out["house"].items()}
    out["senate"] = sorted(out["senate"], key=key)
    return out


def read_already(year, root="."):
    """The files collected/election_<year>.json says it read, or None."""
    p = Path(root) / "collected" / f"election_{year}.json"
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
        return {Path(s["file"]).name for s in doc.get("_source") or []}
    except (OSError, ValueError, KeyError, TypeError):
        return None


def status(year, root="."):
    """(lines to say, complete, the latest files) -- the plain-words state of
    the eleven files."""
    s = saved(year, root)
    latest = [ps[-1] for ps in s["house"].values()] + s["senate"][-1:]
    have = len(s["house"]) + (1 if s["senate"] else 0)
    lines = [f"{have} of {EXPECTED} {year} results files saved in "
             f"{(Path(root) / PSR.SOURCES).as_posix()}/"]
    missing = [c for c in PSR.COUNTIES if c not in s["house"]]
    if missing:
        lines.append("  House, not saved yet: " + ", ".join(missing))
    if not s["senate"]:
        lines.append("  the State Senate file, not saved yet")
    for c, ps in sorted(s["house"].items()):
        if len(ps) > 1:
            lines.append(f"  {c}: {len(ps)} uploads saved; the reader takes {ps[-1].name}")
    if len(s["senate"]) > 1:
        lines.append(f"  State Senate: {len(s['senate'])} uploads saved; the reader takes "
                     f"{s['senate'][-1].name}")
    done = read_already(year, root)
    if done is not None:
        new = sorted(p.name for p in latest if p.name not in done)
        if new:
            lines.append("  saved since collected/election_" + str(year) + ".json was written, "
                         "and not read yet: " + ", ".join(new))
    if s["other"]:
        lines.append("  saved under a name the reader does not take (stop: the 2026 names "
                     "differ, and the pattern is code): " + ", ".join(s["other"]))
    return lines, have == EXPECTED and not s["other"], latest


def fingerprint(paths):
    """A sha256 of the files' names and bytes: what a check has read."""
    h = hashlib.sha256()
    for p in sorted(paths, key=lambda p: p.name):
        h.update(p.name.encode("utf-8") + b"\0" + hashlib.sha256(p.read_bytes()).digest())
    return h.hexdigest()


# ---- the step's report ----------------------------------------------------------

SECTION = re.compile(r"^(NOT LINKED|NEW|DO NOT ADD UP|NOTES)\b")
ROW = re.compile(r"^  (?P<key>[HS]\|\S+)\s+(?P<name>.+?): (?P<why>.*)$")
IDS = re.compile(r"\[(\d+)\]")


def step_rows(text):
    """{"NOT LINKED": [(race, name, why)], "NEW": [...], "DO NOT ADD UP":
    [lines], "NOTES": [lines]} from build_members_elect.py's printed report
    (say_report)."""
    out = {"NOT LINKED": [], "NEW": [], "DO NOT ADD UP": [], "NOTES": []}
    cur = None
    for line in text.splitlines():
        m = SECTION.match(line)
        if m:
            cur = m.group(1)
            continue
        if not line.startswith("  ") or cur is None:
            if line.strip() and not line.startswith("  "):
                cur = None
            continue
        if cur in ("NOT LINKED", "NEW"):
            r = ROW.match(line)
            if r:
                out[cur].append((r.group("key"), r.group("name"), r.group("why")))
        else:
            out[cur].append(line.strip())
    return out


def people(site="site"):
    """[(id, "Surname, First", chamber, county, district, "sitting"|"former")]
    from the built site's rosters, or [] where they are not there."""
    out = []
    for f, kind in (("legislators.json", "sitting"), ("former.json", "former")):
        try:
            rows = json.loads((Path(site) / f).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for r in rows if isinstance(rows, list) else []:
            if isinstance(r, dict) and r.get("id") and r.get("name"):
                out.append((str(r["id"]), r["name"], r.get("chamber") or "",
                            r.get("county") or "", str(r.get("district") or ""), kind))
    return out


def fold(s):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if c.isalnum() or c == " ")


def likely(name, key, roster):
    """Members a NEW name may be, by surname, for a person to check: the
    step found none of that exact name, and a winner printed "Matt
    Sabourin" or "Marty Jack" may be the sitting "Sabourin dit Choiniere,
    Matt" or "Jack, Martin". Same district first, then same county."""
    words = fold(name).split()
    if not words:
        return []
    last = [w for w in words if w not in ("jr", "sr", "ii", "iii", "iv")][-1]
    parts = key.split("|")
    chamber = parts[0]
    county = parts[1] if chamber == "H" and len(parts) > 2 else ""
    dist = parts[-1]
    hits = []
    for pid, pname, ch, co, di, kind in roster:
        surname = fold(pname.split(",")[0]).split()
        if last not in surname:
            continue
        if chamber == "H" and co.lower() != county.lower():
            continue
        rank = 0 if (ch == chamber and di == dist) else 1
        first = pname.split(",", 1)[1].strip() if "," in pname else ""
        hits.append((rank, f"{first} {pname.split(',')[0]} [{pid}], {kind}, "
                           f"{ch} {co + ' ' if co else ''}{di}".replace("  ", " ")))
    return [h for _r, h in sorted(hits)][:4]


def draft_matches(rows, election, roster=()):
    """The draft "matches" and the evidence: a NOT LINKED name takes the one
    member the step names, or null with every member it names listed; a NEW
    name takes null, with any member of its surname in its county named for
    a person to check."""
    matches, evidence = {}, {}
    for key, name, why in rows["NOT LINKED"]:
        ids = list(dict.fromkeys(IDS.findall(why)))
        matches.setdefault(key, {})[name] = ids[0] if len(ids) == 1 else None
        evidence.setdefault(key, {})[name] = (
            ("the step names one member: " if len(ids) == 1 else
             "the step names " + (f"{len(ids)} members, choose one: " if ids else "no member: "))
            + why)
    for key, name, why in rows["NEW"]:
        matches.setdefault(key, {})[name] = None
        maybe = likely(name, key, roster)
        evidence.setdefault(key, {})[name] = (
            "new, by the step: " + why
            + ("; CHECK, of that surname in the county: " + "; ".join(maybe) if maybe else ""))
    return {"_draft": f"A DRAFT for corrections/members_elect.json, under \"{election}\" -> "
                      "\"matches\". Read each evidence line; copy only what you have checked. "
                      "null is a new member.",
            election: {"matches": matches}, "_evidence": evidence}


# ---- check ----------------------------------------------------------------------

def run(args):
    """(exit code, stdout + stderr) of a project script, from the root."""
    r = child.run([sys.executable] + [str(a) for a in args], capture_output=True, text=True,
                  encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (("\n" + r.stderr) if r.stderr else "")


def check(year, url, site="site", root="."):
    """The scheduled task's one run. Returns its exit code: 0 waiting or done,
    1 where a step refused."""
    LOGS.mkdir(exist_ok=True)
    lines, complete, latest = status(year, root)
    now = datetime.datetime.now().isoformat(timespec="minutes")
    if not complete:
        REPORT.write_text(f"# Election week, {now}\n\nWAITING: " + "\n".join(lines) + "\n",
                          encoding="utf-8")
        print("\n".join(lines))
        return 0
    seen = fingerprint(latest)
    try:
        state = json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    if state.get("year") == year and state.get("read") == seen:
        print(f"done: the {year} files were read at {state.get('at')}, and none has been saved "
              "since. Nothing to do.")
        return 0
    code_p, out_p = run([_paths.script("parse_sos_results.py"), "--year", year, "--url", url])
    PARSER_OUT.write_text(out_p, encoding="utf-8")
    code_s, out_s = (None, "")
    if code_p == 0:
        code_s, out_s = run([_paths.script("build_members_elect.py"), "--site", site])
        STEP_OUT.write_text(out_s, encoding="utf-8")
    rows = step_rows(out_s)
    election = election_day(year, root)
    if code_s == 0:
        MATCHES_DRAFT.write_text(json.dumps(draft_matches(rows, election, people(site)),
                                            indent=2, ensure_ascii=False), encoding="utf-8")
    md = [f"# Election week, {now}", "",
          "Nothing here is committed or published. Read each section; corrections/ is yours.", "",
          "## FILES", ""] + [f"- {x.strip()}" for x in lines] + [""]
    refused = [x for x in (out_p + "\n" + out_s).splitlines() if x.startswith("REFUSED")]
    md += ["## REFUSED", ""] + ([f"- {x}" for x in refused] or ["- none"]) + [""]
    flagged = [x for x in out_p.splitlines() if x.startswith(("FLAGGED", "NO --url"))]
    md += ["## FLAGGED (the reader's notes: read every one)", ""] + \
          ([f"- {x}" for x in flagged] or ["- none"]) + [""]
    for title, items in (("NOT LINKED", rows["NOT LINKED"]), ("NEW", rows["NEW"])):
        md += [f"## {title}", ""] + ([f"- `{k}` {n}: {w}" for k, n, w in items] or ["- none"]) + [""]
    for title in ("DO NOT ADD UP", "NOTES"):
        md += [f"## {title}", ""] + ([f"- {x}" for x in rows[title]] or ["- none"]) + [""]
    said = [x.strip() for x in out_s.splitlines()
            if x.startswith(("members-elect:", "  NOT FINAL", "  wrote", "  "))
            and not ROW.match(x) and x.strip() and not x.startswith("    ")][-4:]
    md += ["## THE STEP SAID", ""] + ([f"- {x}" for x in said] or ["- nothing"]) + [""]
    if code_s == 0:
        md += ["## The drafts", "",
               f"- {MATCHES_DRAFT.as_posix()}: \"matches\" to read and copy into "
               "corrections/members_elect.json.",
               "- The recount list and its deadline go in only together, once the Secretary of "
               "State publishes the recount schedule: save it, then run `draft-recounts` "
               "(docs/ELECTION_WEEK.md).", ""]
    md += ["## What each step printed", "", f"- {PARSER_OUT.as_posix()} (exit {code_p})",
           f"- {STEP_OUT.as_posix()} (exit {code_s})" if code_s is not None
           else "- build_members_elect.py did not run: the reader refused", ""]
    REPORT.write_text("\n".join(md), encoding="utf-8")
    ok = code_p == 0 and code_s == 0
    if ok:
        STATE.write_text(json.dumps({"year": year, "read": seen, "at": now,
                                     "files": sorted(p.name for p in latest)}, indent=1),
                         encoding="utf-8")
    print(f"{'read' if ok else 'REFUSED'}: {REPORT.as_posix()}")
    return 0 if ok else 1


def election_day(year, root="."):
    """The election's day, as the collected file names it, or the first
    Tuesday after the first Monday of November."""
    try:
        doc = json.loads((Path(root) / "collected" / f"election_{year}.json")
                         .read_text(encoding="utf-8"))
        return doc["election"]
    except (OSError, ValueError, KeyError, TypeError):
        d = datetime.date(int(year), 11, 2)
        while d.weekday() != 1:
            d += datetime.timedelta(days=1)
        return d.isoformat()


# ---- the recount schedule ------------------------------------------------------

COUNTY_NAMES = {c: c.capitalize() for c in PSR.COUNTIES}
COUNTY_NAMES["coos"] = "Coos"
HOUSE_RACE = re.compile(
    r"\b(?P<county>" + "|".join(c.capitalize() for c in PSR.COUNTIES)
    + r")(?:\s+County)?\s*(?:,\s*)?(?:State\s+Rep(?:resentative)?s?\s*,?\s*)?"
      r"(?:District|Dist\.?)\s*(?:No\.?\s*)?(?P<n>\d{1,2})\b", re.I)
SENATE_RACE = re.compile(r"\b(?:State\s+)?Senat(?:e|or)\s*,?\s*(?:District|Dist\.?)\s*"
                         r"(?:No\.?\s*)?(?P<n>\d{1,2})\b", re.I)
NAMES_DISTRICT = re.compile(r"\b(?:District|Dist\.?)\b", re.I)


def schedule_text(path):
    """The saved schedule's text: a .txt or .csv as it is, a PDF through
    pdfplumber where it is installed."""
    p = Path(path)
    if p.suffix.lower() == ".pdf":
        try:
            import pdfplumber
        except ImportError:
            raise SystemExit(f"{p.name}: a PDF needs pdfplumber (requirements.txt), or save "
                             "the schedule's text as a .txt beside it")
        with pdfplumber.open(p) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    return p.read_text(encoding="utf-8", errors="replace")


def draft_recounts(text, districts, day, deadline, election):
    """(the draft, the lines naming a district that could not be placed).
    `districts` is the races on file, build_members_elect.races_on_file's
    keys: "H|Hillsborough|12", "S|24"."""
    not_final, unplaced = {}, []
    for line in text.splitlines():
        keys = [f"H|{COUNTY_NAMES[m.group('county').lower()]}|{int(m.group('n'))}"
                for m in HOUSE_RACE.finditer(line)]
        keys += [f"S|{int(m.group('n'))}" for m in SENATE_RACE.finditer(line)]
        placed = [k for k in keys if k in districts]
        for k in placed:
            not_final[k] = {"recount": True, "why": f"on the SoS recount schedule of {day}"}
        if NAMES_DISTRICT.search(line) and len(placed) < max(1, len(keys)):
            unplaced.append(line.strip())
    draft = {"_draft": f"A DRAFT for corrections/members_elect.json, under \"{election}\". "
                       "Enter the deadline only together with the recounts (docs/ELECTION_WEEK.md). "
                       "A multi-seat race whose recount is for one seat takes \"seats\": 1.",
             election: {"recount_deadline": deadline, "not_final": not_final}}
    return draft, unplaced


# ---- the question's count -----------------------------------------------------

def question_count(path):
    """{"yes", "no", "blank", "over", "label"} from the question's results
    spreadsheet: the one sheet with one header row holding a Yes and a No,
    and one totals row below it. Anything else is refused (SystemExit)."""
    found = []
    for name, rows in PSR.sheets(Path(path)):
        label = next((str(c) for r in rows for c in r
                      if isinstance(c, str) and re.search(r"question\s+no\.?\s*\d+", c, re.I)), None)
        for i, r in enumerate(rows):
            cells = [str(c).strip().lower() if isinstance(c, str) else None for c in r]
            if "yes" in cells and "no" in cells:
                y, n = cells.index("yes"), cells.index("no")
                b = next((j for j, c in enumerate(cells) if c in ("blank", "undervotes")), None)
                o = next((j for j, c in enumerate(cells) if c in ("overvotes", "over votes")), None)
                totals = [t for t in rows[i + 1:]
                          if t and isinstance(t[0], str) and re.fullmatch(r"(state\s+)?totals?",
                                                                          t[0].strip(), re.I)]
                if len(totals) == 1:
                    t = totals[0]
                    num = lambda j: t[j] if j is not None and j < len(t) and isinstance(t[j], int) \
                        else None
                    found.append({"sheet": name, "yes": num(y), "no": num(n), "blank": num(b),
                                  "over": num(o), "label": label})
    good = [f for f in found if f["yes"] is not None and f["no"] is not None]
    if len(good) != 1:
        raise SystemExit(f"{Path(path).name}: {len(good)} tables of one Yes, one No and one "
                         "totals row; the count is read only where there is exactly one. Copy it "
                         "by hand from the page.")
    return good[0]


def draft_cacr(count, url, bill, read, label=None, election="2026-11-03", term="2025-2026"):
    note = []
    if count.get("blank") is not None:
        note.append(f"{count['blank']:,} blank")
    if count.get("over") is not None:
        note.append(f"{count['over']:,} overvoted")
    return {"_draft": f"A DRAFT of {bill}'s row of corrections/ballot_results.json. Keep the "
                      "row's \"match\" as it is, drop \"described\", and read civics.py's register "
                      "of probate paragraph again (docs/ELECTION_WEEK.md).",
            "row": {"term": term, "bill": bill, "election": election,
                    "label": label or count.get("label") or "<as the spreadsheet lists it>",
                    "yes": count["yes"], "no": count["no"], "source": url,
                    "cite": f"{election[:4]} general election results, sos.nh.gov",
                    "read": read,
                    **({"note": "The spreadsheet also counts " + " and ".join(note)
                        + " ballots; neither is a vote cast on it."} if note else {})},
            "two_thirds": {"yes_share": round(count["yes"] / (count["yes"] + count["no"]), 4)
                           if count["yes"] + count["no"] else None,
                           "ratified": count["yes"] * 3 >= (count["yes"] + count["no"]) * 2}}


# ---- the command line ----------------------------------------------------------

def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[1].strip())
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("status")
    s.add_argument("--year", default="2026")
    c = sub.add_parser("check")
    c.add_argument("--year", default="2026")
    c.add_argument("--url", required=True)
    c.add_argument("--site", default="site")
    m = sub.add_parser("draft-matches")
    m.add_argument("--report", default=str(STEP_OUT))
    m.add_argument("--site", default="site")
    m.add_argument("--election", default=None)
    r = sub.add_parser("draft-recounts")
    r.add_argument("--schedule", required=True)
    r.add_argument("--day", required=True, help="the day the schedule was published")
    r.add_argument("--deadline", default="2026-11-06")
    r.add_argument("--election", default="2026-11-03")
    r.add_argument("--districts", default="site/districts.json")
    q = sub.add_parser("draft-cacr")
    q.add_argument("--file", required=True)
    q.add_argument("--url", required=True)
    q.add_argument("--bill", default="CACR13")
    q.add_argument("--label", default=None)
    q.add_argument("--read", default=datetime.date.today().isoformat())
    a = ap.parse_args()
    LOGS.mkdir(exist_ok=True)
    if a.cmd == "status":
        print("\n".join(status(a.year)[0]))
        return 0
    if a.cmd == "check":
        if not PSR.URL.fullmatch(a.url):
            raise SystemExit(f"--url {a.url!r} is not an https address")
        return check(a.year, a.url, a.site)
    if a.cmd == "draft-matches":
        rows = step_rows(Path(a.report).read_text(encoding="utf-8"))
        election = a.election or election_day("2026")
        MATCHES_DRAFT.write_text(json.dumps(draft_matches(rows, election, people(a.site)),
                                            indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"wrote {MATCHES_DRAFT.as_posix()}: {len(rows['NOT LINKED'])} not linked, "
              f"{len(rows['NEW'])} new")
        return 0
    if a.cmd == "draft-recounts":
        import build_members_elect as BME
        districts = BME.races_on_file(json.loads(Path(a.districts).read_text(encoding="utf-8")))[0]
        draft, unplaced = draft_recounts(schedule_text(a.schedule), districts, a.day,
                                         a.deadline, a.election)
        RECOUNTS_DRAFT.write_text(json.dumps(draft, indent=2), encoding="utf-8")
        print(f"wrote {RECOUNTS_DRAFT.as_posix()}: {len(draft[a.election]['not_final'])} race(s)")
        for line in unplaced:
            print(f"  NOT PLACED, read it: {line}")
        return 0
    if a.cmd == "draft-cacr":
        draft = draft_cacr(question_count(a.file), a.url, a.bill, a.read, a.label)
        CACR_DRAFT.write_text(json.dumps(draft, indent=2), encoding="utf-8")
        print(f"wrote {CACR_DRAFT.as_posix()}: yes {draft['row']['yes']:,}, no "
              f"{draft['row']['no']:,}; two thirds {'reached' if draft['two_thirds']['ratified'] else 'not reached'}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
