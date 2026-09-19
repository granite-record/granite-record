#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-05.31
"""
Run the whole pipeline in the right order.

    python3 build_all.py                    # everything, the video index too
                                            #   when secrets.json holds a key
    python3 build_all.py --local            # no network at all, rebuild from files
    python3 build_all.py --dry-run          # print the plan and stop

The video index is the one step here that needs a credential, and it reads it
out of secrets.json like everything else that needs one. `publish YOURKEY`
still works -- that argument is what tells publish.bat to do a full rebuild
rather than a local one -- but the key itself is no longer carried on a
command line, and --key is accepted and ignored.

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
import os
import subprocess
import sys
import threading
import time
import child
from datetime import datetime
from pathlib import Path


BUILD_LOCK = Path(".build.lock")
# A build touches its lock every half minute. A lock older than this belonged
# to a build that was killed, and is taken rather than obeyed -- otherwise one
# interrupted build stops every later one until somebody deletes a file.
STALE_AFTER = 180


class building:
    """One build at a time. `with building(): ...`

    TWO BUILDS AT ONCE DESTROYED narratives.json ON 12 SEPTEMBER. One was
    started, its log file did not appear within a few seconds, it was assumed
    not to have started, and a second was launched. Both ran. Both wrote
    narratives.json, and the file ended as a complete JSON document with more
    data after it -- "JSONDecodeError: Extra data: line 309112" -- with seven
    of its nineteen terms gone. Nothing was published; it was caught because
    the floor-index step reads that file and failed on it.

    The fetch lane has had a lock since the address blocked this project a
    second time, for exactly this reason, and the build had none. Every step
    here writes a derived file that another step reads, so two builds are two
    writers on all of them at once.

    The lock keeps a pid for a person to read, and its own freshness is what
    decides whether it is live: a build that is killed leaves the file behind,
    and a rule that trusts the file alone would block every later build until
    somebody worked out what it was.
    """

    def __enter__(self):
        if BUILD_LOCK.exists():
            age = time.time() - BUILD_LOCK.stat().st_mtime
            held = BUILD_LOCK.read_text(encoding="utf-8", errors="replace").strip()
            if age < STALE_AFTER:
                print(f"\n{BUILD_LOCK} is held (pid {held or '?'}) and was "
                      f"touched {age:.0f}s ago: another build is running, and "
                      f"this will not be a second one.\n\n"
                      f"Two builds at once is what emptied seven terms out of "
                      f"narratives.json once. Wait for it, or -- if nothing is "
                      f"really running -- delete {BUILD_LOCK}.\n",
                      file=sys.stderr)
                sys.exit(3)
            print(f"  {BUILD_LOCK} (pid {held or '?'}) has not been touched "
                  f"for {age / 60:.0f} minutes; that build is gone, taking it")
        BUILD_LOCK.write_text(str(os.getpid()), encoding="utf-8")
        self._stop = threading.Event()

        def beat():
            while not self._stop.wait(30):
                try:
                    os.utime(BUILD_LOCK, None)
                except OSError:
                    pass
        threading.Thread(target=beat, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        try:
            BUILD_LOCK.unlink()
        except OSError:
            pass
        return False


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

        # AFTER build_data, because it reads data/bills.json, and before
        # build_site_v2, which merges its answers in. Regenerated every run
        # rather than kept, so a term the General Court labels later simply
        # stops being guessed at: topic_model.py never answers for a bill that
        # already has a topic.
        #
        # topic_model.py rather than topics.py: it is the second model, it
        # imports the first rather than replacing it, and it writes the same
        # file key for key. topics.py stays runnable and stays what preflight
        # tests.
        Step("a topic for the bills the General Court gave none",
             ["topic_model.py", "--apply", "--space", "B"],
             needs=["data/bills.json"], produces=["topics_assigned.json"],
             note="learns from the 2,221 bills of 2025-2026 that carry the "
                  "General Court's own topic and answers for the other "
                  "29,449, or says Miscellaneous where it cannot; in the "
                  "site's own vocabulary -- five thin categories folded, "
                  "Housing and Study added"),

        # AFTER build_data, for the same reason as topics: it reads
        # data/sponsors.json to leave alone every bill the database already
        # names sponsors for, and build_site_v2 merges its answer in. Every run,
        # so each night's pages from the lane reach the next build.
        Step("sponsors named on each bill's saved text",
             ["text_sponsors.py", "--apply"],
             needs=["data/bills.json", "data/member_votes.json", "legislation"],
             produces=["text_sponsors.json"],
             note="the sponsor line of the pages fetch_legislation.py saves, "
                  "matched to members who cast a roll call that term; no "
                  "network, and never over a sponsor the database names"),

        # AFTER text_sponsors, which walks the same saved pages, and BEFORE
        # build_site_v2, which imports this module (build_site_v2.py:36) and
        # calls AT.merge_into to fold archive_text.json in under
        # bill_text.json. While it was missing from this list, the text of
        # every archived bill reached the site only when somebody remembered
        # the command by hand, and the gap widened every hour the lane kept
        # fetching.
        #
        # No network -- it reads what fetch_legislation.py has already saved --
        # so --local runs it too, which is the point of putting it here: a
        # rebuild from files on disk should pick up the pages the last fetch
        # brought down, not wait for the next one.
        Step("the text of every archived bill, off the pages on disk",
             ["archive_text.py", "--apply"],
             needs=["data/bills.json", "legislation"],
             produces=["archive_text.json"],
             note="bill_text.json covers 2025-2026 and nothing else, so every "
                  "older term drew a Bill Text tab with nothing in it; merged "
                  "UNDER bill_text.json, never over it"),

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

        # The chapter each bill became, from the line in its docket that
        # records the signature. Every term's docket is on disk; before this
        # a chapter was on the page for 2023-2026 only.
        Step("the chapter of the session laws each bill became",
             ["extract_chapters.py"],
             needs=["data/bills.json"],
             produces=["chapters.json"],
             note="11,812 bills across all 19 terms; 18 withheld where the "
                  "docket gives one number to two bills"),

        # An archived term's docket, and the histories built from it. Both
        # are skipped when the file is not there, so a checkout without the
        # archive builds exactly as before.
        #
        # narrative.py MERGES, and has to: it is run twice here, once per
        # docket, and the second run would otherwise replace the first term's
        # 2,233 bills with the other's 1,996 and build clean.
        # EVERY ARCHIVED TERM WHOSE DOCKET IS ON DISK, not just the one that
        # was narrated by hand. narrative.py merges, and has to: run per
        # docket, each term's bills are added to narratives.json rather than
        # replacing the last term's. This step once named Docket_2023-2024.txt
        # alone, so a rebuild from a clean narratives.json produced two terms
        # out of nineteen.
        Step("plain-language histories for every archived term",
             ["narrate_archive.py"],
             needs=["data/legislators.json"],
             produces=["narratives.json"],
             note="18 terms, 1989-2024: the database's own dockets for "
                  "1989-2014 and the fetched ones for 2015-2024. The older "
                  "vocabulary is read by docket_vocab.py"),

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

        # NO --key HERE, and that is the whole of the fix. A key on a command
        # line is visible to every process on the machine and lands in shell
        # history -- keys.py sets out why -- and fetch_channel_index.py reads
        # secrets.json whenever the flag is absent. Passing it was also what
        # made this step vanish: main() used the presence of --key to decide
        # whether to run the step at all, so the secrets.json path README
        # documents could never reach the pipeline, whatever was in the file.
        Step("video index",
             ["fetch_channel_index.py", "--chamber", "house",
              "--start", f"{a.session}-01-01", "--end", f"{a.session}-12-31"],
             network=True, optional=True,
             note="needs the YouTube key in secrets.json; skipped, and says "
                  "so, without one"),

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

        Step("the bill-version vocabulary, out of the dump already on disk",
             ["document_versions_from_db.py"],
             needs=["db/DocumentVersion.psv"],
             produces=["db/document_versions.json"],
             note="asks nobody anything -- it reshapes the dumped view. Here "
                  "because the file it writes was a declared need of the next "
                  "step with no generator anywhere, which a fresh clone could "
                  "not satisfy: db/ is gitignored and this was the one file in "
                  "it that no run could rebuild"),

        Step("every version of a bill, and what each amendment changed",
             ["build_bill_versions.py", "--site", "site"],
             needs=["db/LegislationText.psv", "db/document_versions.json"],
             produces=["data/bill_versions.json"],
             note="BEFORE site data, because it writes the manifest that "
                  "tells each bill's record how many versions it has -- "
                  "without which the page would draw a Versions tab on all "
                  "2,234 bills and put a 404 behind the 1,085 that have one"),

        Step("site data",
             ["build_site_v2.py", "--data", "data", "--out", "site",
              "--segments", "work"],
             needs=["data/bills.json"], produces=["site/index.json"]),

        # AFTER "site data" AND BEFORE build_indexes: it reads the meta.json
        # build_site_v2 writes and merges one key into it, so running it first
        # would have its key overwritten and the option would silently not be
        # there. build_lsrs asserts meta.json exists rather than trusting this
        # ordering to stay put.
        Step("the 2027 bill requests",
             ["build_lsrs.py", "--site", "site"],
             # index.json rather than meta.json: the same step writes both,
             # so this orders it the same way, and it is the one that step
             # declares. build_lsrs.py asserts on meta.json itself, which is
             # the guard that matters -- a missing key would otherwise show
             # only as the picker quietly lacking an option.
             needs=["site/index.json"], produces=["site/idx/2027-requests.json"],
             note="what the next session will be about, months before a bill "
                  "of it exists: title and prime sponsor and nothing else, "
                  "which is all an LSR has"),

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

        Step("how New Hampshire works",
             ["build_civics.py", "--site", "site", "--base", a.base],
             needs=["site/index.json"],
             produces=["site/learn.html"],
             note="eleven civics pages and the hub they hang off; needs no "
                  "data and no network, and it owns learn.html"),

        Step("a page per town and ward",
             ["build_town_pages.py", "--site", "site", "--base", a.base],
             needs=["site/districts.json", "site/legislators.json"],
             produces=["site/town"],
             note="who represents the people who live there -- state "
                  "representatives and senator from the roster, and the "
                  "executive council, US House and Senate districts that were "
                  "in districts.json all along and had never been shown"),

        Step("the whole record, as lists",
             ["build_indexes.py", "--site", "site", "--base", a.base],
             needs=["site/idx", "site/legislators.json", "site/towns.json", "site/town"],
             produces=["site/directory.html"],
             note="every bill of every term, every legislator and every town as plain "
                  "links: the bill list and the legislator search are drawn by "
                  "script, so without these a page was reachable from the sitemap "
                  "and almost nothing else"),

        # AFTER the legislator pages, because a speaker's name becomes a link
        # only if site/legislators.json and site/former.json are on disk to
        # resolve it against, and BEFORE the calendar, whose floor cards link
        # to these pages.
        Step("a page for every day the Senate sat",
             ["build_session_pages.py", "--site", "site", "--base", a.base,
              "--body", "S"],
             needs=["narratives.json", "site/legislators.json"],
             produces=["site/session/S"],
             note="the record only. The Senate journal carries no unanimous "
                  "consent, no remarks and no speaker attributions at all, so "
                  "a Senate page says so rather than showing an empty section"),

        Step("a page for every day the House sat",
             ["build_session_pages.py", "--site", "site", "--base", a.base],
             needs=["narratives.json", "site/legislators.json"],
             produces=["site/session/H"],
             note="the day in the order the journal prints it: every bill, "
                  "the motions put to it, who spoke on which side, how it was "
                  "voted and what that did to the bill. House only -- the "
                  "Senate journal records no speakers"),

        # AFTER the committees, whose codes turn a committee name on a card
        # into a link to its page, and after the sitemap exists so the weeks
        # can be appended to it the way every other builder appends.
        Step("a page for every week of the General Court",
             ["build_calendar.py", "--site", "site", "--base", a.base],
             needs=["site/committees.json", "proceedings.csv"],
             produces=["site/calendar.html"],
             note="the hearings, work and executive sessions and floor "
                  "sittings of one week, on one page, with the weeks either "
                  "side a link away -- and sitting days listed at all, which "
                  "nothing else on the site does because every listing is "
                  "keyed on a committee and the floor has none"),

        # THE FEEDS ARE WRITTEN BEFORE THE PAGE THAT DOCUMENTS THEM.
        # This pair used to run the other way round, and the consequence was
        # not a crash: site/data.html simply contained the word "feed" zero
        # times, because at the moment it was written there were no feed files
        # on disk to count. 704 of them, across five families, published and
        # undocumented. The two steps share nothing -- build_feeds names
        # data.html, the manifest and exports zero times; build_exports names
        # feed zero times; neither mentions the sitemap -- so the order is
        # free, and this is the order that lets the page tell the truth.
        Step("RSS feeds",
             ["build_feeds.py", "--site", "site", "--base", a.base],
             needs=["site/index.json"], produces=["site/feed/all.xml"],
             note="following a bill without an account, an email address or a "
                  "list that could leak"),

        Step("bulk downloads",
             ["build_exports.py", "--site", "site", "--base", a.base],
             needs=["site/index.json", "site/feed/all.xml"],
             produces=["site/data/manifest.json", "site/data.html"],
             note="the same record as CSV, for anybody who would rather work "
                  "with it than read it, and the page that describes both the "
                  "tables and the feeds. It runs in the pipeline rather than "
                  "by hand because an export nobody rebuilds is worse than "
                  "no export: it looks current and is not"),
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", help="accepted so `publish YOURKEY` keeps "
                                  "working, and ignored: the video index "
                                  "reads the key from secrets.json")
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
    # ONE WORKER FOR THE GENERAL COURT, and it may be the lane. While
    # archive/.lock is held -- watchers/gc_lane.py fetching the archive for
    # days -- or a refusal is on file, a full build's network steps would be
    # a second fetcher asking the same address, which is how it was blocked
    # the second time: `publish YOURKEY` beside the lane. They are skipped,
    # and said so. The YouTube video index is another host and still runs.
    gc_busy = [w for w, p in (("archive/.lock is held (the General Court "
                               "lane, or another fetch)", "archive/.lock"),
                              ("archive/refused.json is on file",
                               "archive/refused.json")) if Path(p).exists()]
    if gc_busy and any(s.network for s in steps):
        held = [s for s in steps if s.network
                and "fetch_channel_index.py" not in s.args[0]]
        steps = [s for s in steps if s not in held]
        print(f"  {'; '.join(gc_busy)}: skipping {len(held)} step(s) that "
              f"would ask the General Court -- " + ", ".join(s.name for s in held))
    # A STEP THAT CANNOT RUN SAYS SO. This one used to disappear without a
    # word -- `if not a.key: steps = [s for s in steps if
    # "fetch_channel_index.py" not in s.args[0]]`, no print -- four lines
    # under the branch above, which names every step it holds. A build on a
    # machine with a perfectly good secrets.json therefore dropped the video
    # index and reported nothing wrong, and the plan printed by --dry-run did
    # not list it either, so there was nowhere to notice it from.
    #
    # The key is no longer a step argument, so what decides now is the file
    # the key actually lives in.
    if a.key:
        print("  --key was given and is ignored: a key on a command line is "
              "visible to every process on the machine (see keys.py), so the "
              "video index reads secrets.json. Put the key there.")
    vid = [s for s in steps if "fetch_channel_index.py" in s.args[0]]
    if vid and not Path("secrets.json").exists():
        steps = [s for s in steps if s not in vid]
        print("  no secrets.json: skipping the video index -- the one step "
              "here that needs the YouTube key. Copy secrets.example.json to "
              "secrets.json and fill it in.")
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

    # NOTHING BELOW THIS LINE MAY RUN TWICE AT ONCE. --dry-run returns above
    # and never reaches here, so listing the plan while a build runs is fine.
    with building():
        return _run_steps(steps, a)


def _run_steps(steps, a):
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
        r = child.run([sys.executable] + s.args, capture_output=True, text=True)
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
