#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-05.10
"""
Run the whole pipeline in the right order.

    python3 build_all.py                    # everything except video
    python3 build_all.py --key YOURKEY      # including the video index
    python3 build_all.py --local            # no network at all, rebuild from files
    python3 build_all.py --dry-run          # print the plan and stop

The order is not obvious and getting it wrong has caused real bugs: narratives
must exist before the site build reads them, districts before the data build
checks them, and build_data runs TWICE -- once to produce the roster that
resolve_members needs, then again to pick up the names and titles it found.

Nothing here is clever. It runs the steps, stops at the first genuine failure,
skips steps whose inputs are missing rather than crashing on them, and writes a
record of what ran to site/build.json so the site can say how fresh it is.

Transcription is excluded by default: it is per-video and slow even with
captions. Run transcribe_and_align.py separately, then rebuild.
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


class Step:
    def __init__(self, name, args, needs=(), produces=(), network=False,
                 optional=False, note="", superseded=False):
        self.name, self.args = name, args
        self.needs = [Path(n) for n in needs]
        self.produces = [Path(p) for p in produces]
        self.network, self.optional, self.note = network, optional, note
        # Kept for the case a newer step does not cover, but not run
        # in a normal build. Two writers for one number is how the
        # clustering path came to announce "segments are back on
        # mention density" after the marker path had already found
        # the chair saying it.
        self.superseded = superseded

    def missing(self):
        return [str(n) for n in self.needs if not n.exists()]


def plan(a):
    key = a.key or "%YTKEY%"
    vids = sorted(str(p) for p in Path(".").glob("videos_*.csv"))

    def manifest_videos():
        """Every index covering the session, both chambers.

        This used to hand over a single House file, which is why no Senate
        hearing has ever had a timestamp: the manifest had no Senate
        proceedings in it to match. Pass both and the chambers covered follow
        from the data rather than from the code.
        """
        # Every index, not just the ones whose filename carries the session
        # year. A term runs across two calendar years -- a 2025 bill is heard,
        # amended and voted through 2026 -- so filtering to "2026" threw away
        # every 2025 hearing and halved the manifest. build_manifest.py already
        # limits proceedings to dates its videos cover, which is the correct
        # place for that decision because it uses the dates rather than the
        # filenames.
        return vids or ["videos_house.csv"]
    return [
        Step("archive the bulk files",
             ["snapshot_gencourt.py", "--dir", a.archive],
             network=True, optional=True,
             note="cannot be done retroactively; run it daily"),

        Step("parse district files",
             ["parse_districts.py", "--dir", "districts",
              "--towns", "site/towns.json", "--out", "site/districts.json"],
             needs=["districts/house.txt"], produces=["site/districts.json"],
             note="house.txt carries the floterial districts HouseDistricts.txt omits"),

        Step("roll call tallies and thresholds",
             ["rollcall_parser.py", "--file", "RollCallSummary.txt", "--all",
              "--out", "rollcalls.json"],
             needs=["RollCallSummary.txt"], produces=["rollcalls.json"]),

        Step("build data (first pass)",
             ["build_data.py", "--dir", ".", "--out", "data"],
             needs=["Docket.txt", "legislators.txt"], produces=["data/bills.json"],
             note="produces the roster that resolve_members needs"),

        Step("name members missing from the roster",
             ["resolve_members.py", "--data", "data", "--session", a.session,
              "--max-requests", "60"],
             needs=["data/legislators.json"], network=True, optional=True),

        Step("titles and sponsors for bills the session files omit",
             ["fetch_bill_status.py", "--data", "data"],
             needs=["data/bills.json"], network=True, optional=True,
             note="the status page carries both as labelled fields; slow, "
                  "seconds per bill, and cached afterwards"),

        Step("fill the blanks in bill status from the database",
             ["fetch_status_db.py"],
             needs=["bill_status.json"], network=True, optional=True,
             note="AFTER the step above, never before: that one rebuilds "
                  "bill_status.json from the pages and this one fills what "
                  "the pages left empty -- 577 general statuses, 311 House, "
                  "121 Senate, 188 committee codes. One SELECT, on the SQL "
                  "host, not gc.nh.gov"),

        Step("build data (second pass)",
             ["build_data.py", "--dir", ".", "--out", "data"],
             needs=["Docket.txt"], produces=["data/bills.json"],
             note="picks up the names and titles the two steps above found"),

        Step("plain-language bill histories",
             ["narrative.py", "--docket", "Docket.txt", "--all",
              "--out", "narratives.json", "--members", "data/legislators.json"],
             needs=["Docket.txt"], produces=["narratives.json"],
             note="runs AFTER build_data so the roster exists: it turns "
                  "\"a motion by Rep. N. Germana\" into the member's full name. "
                  "build_data.py does not read narratives.json, so nothing "
                  "before this point needs it"),

        # The governor's reasons, out of the calendars already on disk. No
        # network: fetch_committee_reports.py brought those PDFs down for the
        # committee reports and they carry the veto messages too. Skipped
        # where there is no calendars/ folder, so a checkout without it builds
        # exactly as before.
        Step("the governor's veto messages",
             ["extract_vetoes.py"],
             needs=["calendars"],
             produces=["veto_messages.json"],
             note="34 of the current term's 34 House vetoes; the Senate's are "
                  "in the Senate calendars, which this project does not fetch"),

        # An archived term's docket, and the histories built from it. Both
        # are skipped when the file is not there, so a checkout without the
        # archive builds exactly as before.
        #
        # narrative.py MERGES, and has to: it is run twice here, once per
        # docket, and the second run would otherwise replace the first term's
        # 2,233 bills with the other's 1,996 and build clean.
        Step("plain-language histories for the archived term",
             ["narrative.py", "--docket", "Docket_2023-2024.txt", "--all",
              "--out", "narratives.json",
              "--members", "data/legislators.json"],
             needs=["Docket_2023-2024.txt", "data/legislators.json"],
             produces=["narratives.json"],
             note="fetch_archive_docket.py writes that docket in Docket.txt's "
                  "own seven columns, so this is the same parser the current "
                  "term uses"),

        # Never a step until now, which is the only reason no chair, vice
        # chair, aide, room or phone is anywhere on disk: fetch_committees.py
        # has always parsed all of them, for both chambers, and has simply
        # never been run by the pipeline. --probe prints and writes nothing.
        Step("committee membership and leadership",
             ["fetch_committees.py"],
             produces=["committees.json"],
             network=True, optional=True,
             note="both chambers, two requests; the only source on this site "
                  "for who chairs what"),

        Step("who sits on each committee",
             ["fetch_committee_members_db.py"],
             produces=["data/committee_members.json"], network=True,
             optional=True,
             note="the database has both chambers' rosters; the web pages "
                  "have the Senate's only"),

        Step("committee majority and minority reports",
             ["fetch_committee_reports.py", "--year", a.session],
             network=True, optional=True,
             note="calendars are cached; discovery only needs running once a session"),

        Step("how many signed in for and against, per hearing",
             ["fetch_testimony_db.py"],
             produces=["testimony_db.json"],
             network=True, optional=True,
             note="the SQL host, not gc.nh.gov. Counts only -- the sign-in "
                  "sheet's names, towns and written testimony are not asked "
                  "for. 2,019 bills against the scraped page's 565"),

        Step("the Senate's committee reports, with their reasoning",
             ["fetch_reports_db.py"],
             produces=["senate_reports.json"],
             network=True, optional=True,
             note="the General Court's SQL host, not gc.nh.gov; 1,446 reports "
                  "in one SELECT, 1,096 of them explaining the vote"),

        # --summary was passed here and fetch_journals.py has never defined it,
        # so argparse rejected the call and this step has never run in a build.
        # Every "HJ 7 P. 55" link on the site is as old as the last time
        # somebody ran the script by hand.
        Step("journal links for docket citations",
             ["fetch_journals.py", "--year", a.session],
             produces=["journals.json"],
             network=True, optional=True,
             note="turns 'HJ 7 P. 55' into a link to the official record; "
                  "merges, so a chamber that fails loses nothing already "
                  "fetched"),

        Step("video index",
             ["fetch_channel_index.py", "--key", key, "--chamber", "house",
              "--start", f"{a.session}-01-01", "--end", f"{a.session}-12-31"],
             network=True, optional=True,
             note="needs an API key; skipped without one"),

        Step("match docket proceedings to recordings",
             ["build_manifest.py", "--videos"] + manifest_videos(),
             needs=["Docket.txt"], optional=True),

        Step("testimony sign-in counts",
             ["fetch_testimony.py"],
             produces=["testimony.json"], network=True, optional=True,
             note="was never in this list, so the counts on the site only "
                  "refreshed when it was remembered by hand. Slow -- one "
                  "request per bill with a delay -- and skipped by --local"),

        Step("floor debate index",
             ["build_floor_index.py", "--videos"] + (vids or ["videos_house.csv"])
             + ["--summary", "RollCallSummary.txt", "--narratives", "narratives.json"],
             needs=["RollCallSummary.txt"], produces=["floor_index.json"],
             optional=True),

        # One table from the two sources, for everything downstream. Sits
        # right after both producers so it can never be older than either.
        Step("one proceedings table",
             ["build_proceedings.py"],
             needs=["verification_manifest.csv"], produces=["proceedings.csv"],
             note="merges the manifest and the floor index into one file with "
                  "one shape; refuses to shrink by a fifth without "
                  "--allow-shrink, because a table that shrinks lost a "
                  "source"),

        Step("boundaries the chair stated",
             ["segment_markers.py", "--all", "--data", "data", "--quiet"],
             needs=["proceedings.csv", "work"], produces=["candidate_segments.json"],
             optional=True,
             note="reads every caption file and finds where each proceeding "
                  "was opened and closed; cached per recording, so a rerun "
                  "with nothing new takes seconds"),

        # apply_markers.py patches segments.json, which the clustering path
        # produced. segment_markers.py above supersedes it: candidate_segments
        # .json is read directly by build_site_v2 and a stated boundary there
        # replaces the clustered one outright. Running both means two writers
        # for one number, and the older one printing "segments are back on
        # mention density" after the newer one has already found the chair
        # saying it.
        #
        # Left in, off by default, because it is the fallback for recordings
        # segment_markers finds nothing on -- but it no longer runs unasked.
        Step("adopt boundaries the chair stated (superseded)",
             ["apply_markers.py", "--workdir", "work",
              "--manifest", "verification_manifest.csv", "--apply"],
             needs=["verification_manifest.csv", "work"], optional=True,
             superseded=True,
             note="the older clustering path; segment_markers.py above does "
                  "this better and build_site_v2 reads it directly. Pass "
                  "--with-apply-markers to run it anyway"),

        Step("site data",
             ["build_site_v2.py", "--data", "data", "--out", "site",
              "--segments", "work"],
             needs=["data/bills.json"], produces=["site/index.json"]),

        Step("home, legislators, towns, explainer, about",
             ["build_pages.py", "--out", "site"],
             needs=["site/legislators.json"], produces=["site/index.html"]),

        Step("a static page for every bill",
             ["build_bill_pages.py", "--site", "site", "--base", a.base],
             needs=["site/index.json"], produces=["site/sitemap.xml"],
             note="what makes bills findable in a search engine"),

        Step("a static page for every sitting legislator",
             ["build_legislator_pages.py", "--site", "site", "--base", a.base],
             needs=["site/legislators.json"],
             produces=["site/legislator"],
             note="what makes a member's voting record findable by name"),

        Step("a page for every committee",
             ["build_committees.py", "--site", "site", "--data", "data",
              "--base", a.base],
             needs=["site/index.json", "site/legislators.json"],
             produces=["site/committees.json"],
             note="what a committee did on a day, which bill-first search "
                  "cannot answer"),

        Step("RSS feeds",
             ["build_feeds.py", "--site", "site", "--base", a.base],
             needs=["site/index.json"], produces=["site/feed/all.xml"],
             note="following a bill without an account, an email address or a "
                  "list that could leak"),
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", help="YouTube API key; video index skipped without it")
    ap.add_argument("--session", default=str(datetime.now().year))
    ap.add_argument("--base", default="https://graniterecord.org")
    ap.add_argument("--archive", default="nh-archive")
    ap.add_argument("--with-superseded", action="store_true",
                    help="also run steps a newer one has replaced")
    ap.add_argument("--local", action="store_true",
                    help="skip every step that touches the network")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--keep-going", action="store_true",
                    help="carry on past a failed required step")
    a = ap.parse_args()

    steps = plan(a)
    if a.local:
        steps = [s for s in steps if not s.network]
    if not a.key:
        steps = [s for s in steps if "fetch_channel_index.py" not in s.args[0]]
    if not a.with_superseded:
        dropped = [s for s in steps if s.superseded]
        steps = [s for s in steps if not s.superseded]
        for s in dropped:
            print(f"  skipping '{s.name}' -- a newer step covers it. "
                  "--with-superseded runs it anyway.")

    print(f"{len(steps)} steps, session {a.session}\n")
    if a.dry_run:
        for i, s in enumerate(steps, 1):
            miss = s.missing()
            flag = ("SKIP, missing " + ", ".join(miss)) if miss else "run"
            print(f"{i:>2}. {s.name}")
            print(f"    python3 {' '.join(s.args)}")
            print(f"    {flag}" + (f"  ({s.note})" if s.note else ""))
        return

    results, failed = [], None
    t0 = time.time()
    for i, s in enumerate(steps, 1):
        miss = s.missing()
        if miss:
            print(f"[{i}/{len(steps)}] {s.name} — SKIPPED, missing {', '.join(miss)}")
            results.append({"step": s.name, "status": "skipped",
                            "missing": miss})
            continue
        print(f"[{i}/{len(steps)}] {s.name}", flush=True)
        st = time.time()
        r = subprocess.run([sys.executable] + s.args, capture_output=True, text=True)
        secs = round(time.time() - st, 1)
        if r.returncode == 0:
            tail = [l for l in r.stdout.strip().splitlines() if l.strip()][-3:]
            for l in tail:
                print(f"      {l}")
            print(f"      done in {secs}s")
            results.append({"step": s.name, "status": "ok", "seconds": secs})
        else:
            print(f"      FAILED after {secs}s")
            print("      " + (r.stderr.strip().splitlines() or ["no error text"])[-1])
            results.append({"step": s.name, "status": "failed", "seconds": secs,
                            "error": r.stderr.strip()[-800:]})
            if s.optional:
                print("      this step is optional; carrying on")
                continue
            failed = s.name
            if not a.keep_going:
                break

    total = round(time.time() - t0, 1)
    site = Path("site")
    if site.exists():
        site.mkdir(exist_ok=True)
        (site / "build.json").write_text(json.dumps({
            "finished": datetime.now().isoformat(timespec="seconds"),
            "session": a.session, "seconds": total,
            "ok": failed is None, "steps": results}, indent=2), encoding="utf-8")

    print(f"\n{'-' * 58}")
    ok = sum(1 for r in results if r["status"] == "ok")
    sk = sum(1 for r in results if r["status"] == "skipped")
    fl = sum(1 for r in results if r["status"] == "failed")
    print(f"{ok} ran, {sk} skipped, {fl} failed, {total}s total")
    if failed:
        print(f"\nStopped at: {failed}")
        print("Fix that and rerun. Steps before it are cached or idempotent, so a "
              "rerun is cheap.")
        sys.exit(1)
    if sk:
        print("\nSkipped steps were missing an input file. That is expected on a "
              "first run or with --local; check the list above if something you "
              "wanted is not on the site.")
    print("\nsite/build.json records what ran, and the site reads it to say how "
          "fresh the data is.")


if __name__ == "__main__":
    main()
