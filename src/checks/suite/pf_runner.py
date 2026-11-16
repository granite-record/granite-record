#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.2
"""
The runner: what `python3 preflight.py` does with its checks.

main() reads the arguments, takes the workflow's words for the run out of the
environment (_not_the_runs), chooses the checks (--code, --data, --built, and
--changed through check_select), starts beside them the fixture sites they
take, runs each and reads its answer, records the run for handoff.py and ends
on its ten slowest. With it the lists of the checks the night runs after its
build (BUILT_CODE and the rest), which --built reads. Moved out of
preflight.py as they stood, with the comments above each (16 November 2026,
the refactor's stage 1, step 4); preflight.py imports main and calls it. This
module uses pf_core and pf_fixture, and only preflight.py imports it.
"""

import argparse
import json
import os
import sys
import traceback
from collections import Counter
from pathlib import Path

from pf_core import (CHECKS, _OUTCOMES, _THIS_RUN, _answer, _in_order, _manifest_text, _parsed,
                     _settle, _suite_files, imp)
from pf_fixture import (_early_wanted, _start_early_builds)
MAIN_REF = "refs/heads/main"
# Preflight inherits the workflow's DRY_RUN too, when the night runs it first on
# GitHub's machine. The workflow's words for its own run, which no check's
# fixture may take for its own: main() takes them out before any check runs.
# GITHUB_REF is GitHub's own, and on dev it makes nightly.py and cloud.py take
# every fixture's night, kit-up and state-up for a dry run's, as DRY_RUN did.
# Taken out is not enough for it: a missing ref is not main's either (nightly's
# MAIN IS MAIN_REF EXACTLY), so main() then names main, and a fixture on
# GitHub's machine is a run of main unless its check names another ref.
# REVIEW_GATE TOO (15 October 2026). The workflow sets it for every step, and
# from 1436c5c it says "on": the first dry run after the switch stopped at
# "preflight failed. Nothing fetched, nothing built", because
# _nightly_review_says, reading the night's page lines, found the gate-on
# wording where its fixture expects shadow's. A laptop run never has the word,
# so no run here could see it. A check that wants the gate on sets it itself.
WORKFLOW_WORDS = ("DRY_RUN", "GITHUB_REF", "GITHUB_REF_NAME", "REVIEW_GATE")
CHECKS_REF = ("GITHUB_REF", MAIN_REF)
# THE RUN'S OWN FILES ARE NOT THE CHECKS' EITHER (13 November 2026). GitHub
# names for every step the file behind the run's page (GITHUB_STEP_SUMMARY),
# the step's outputs (GITHUB_OUTPUT) and what it leaves the steps after it
# (GITHUB_ENV, GITHUB_PATH, GITHUB_STATE), and the night runs preflight inside
# its own step. So a fixture that drove nightly.gh_summary or
# quick_preview.summary without a file of its own wrote onto the real page:
# the night of 13 November, clean and published, carried three "Why: ...
# Nothing was published." lines and eight quick previews that "may go on" or
# were "refused" (a commit 0123456789ab, an archive 2508 days old) above its
# own verdict, on the page the owner approves a night from. An output would
# have been worse than a line: the publish job reads publishable and review
# from the night's step. main() takes these out with the workflow's words, so
# no check and no child of one can reach them; a check that wants one names a
# file of its own and puts back what it found.
RUNNER_FILES = ("GITHUB_STEP_SUMMARY", "GITHUB_OUTPUT", "GITHUB_ENV", "GITHUB_PATH",
                "GITHUB_STATE")


def _not_the_runs():
    """Take the workflow's words for the run preflight is part of (WORKFLOW_WORDS)
    out of this process's environment, and so out of every child it starts.

    THE REVIEW OF 7 OCTOBER 2026. nightly.py runs preflight --code before it
    fetches anything, with the workflow's environment, and on a dry run that
    holds DRY_RUN=true beside GITHUB_ACTIONS=true -- which makes every kit-up,
    state-up and night a fixture drives a dry run's. Eight checks failed under
    it (the kit round trip, the R2 adapter, the New term nights, the database
    fallback among them), so every dry run would have stopped at "preflight
    failed. Nothing fetched, nothing built." A check that wants a dry run sets
    the word itself, and puts back what it found.

    And since every run of a branch other than main is a dry run (7 October
    2026), GitHub's own GITHUB_REF says it too, on every run of dev: it is
    taken out with GITHUB_REF_NAME, and a check that wants a run of a branch
    sets the ref itself. Since a missing ref is not main's either (nightly's
    MAIN IS MAIN_REF EXACTLY), the ref is then put back as main's (CHECKS_REF),
    on the laptop and on GitHub's machine alike, and a check that changes it
    puts main's back.

    THE RUN'S PAGE OF 13 NOVEMBER 2026 (RUNNER_FILES says what it carried).
    The paths of the run's own files go with the words: its page, the step's
    outputs, and what a step leaves the steps after it."""
    for k in WORKFLOW_WORDS + RUNNER_FILES:
        os.environ.pop(k, None)
    os.environ[CHECKS_REF[0]] = CHECKS_REF[1]


# THE CHECKS OF A SITE JUST BUILT (15 October 2026, the person's decision;
# nightly.BUILT_CHECKS says what the night does with them). The night runs
# --code before it builds, so a check that reads the built site skipped there,
# and the data group never ran on GitHub at all: from 12 to 15 October the
# report box dropped readers' reports from nearly every legislator page and no
# night could say so. --built is what the night runs after check_site: the
# code checks that read a built site (BUILT_CODE), again, and every data check
# but those that need the laptop (NOT_ON_THE_NIGHT). Which was which was
# measured, not guessed: each check was run alone under an audit hook on
# 15 October and every file it opened placed in the checkout, the kit, the
# build's own output, the site, or the laptop alone. A data check added later
# runs on the night unless it is put on the list here, with its reason.
BUILT_OUT = Path("logs/built-checks.json")
BUILT_CODE = {"_asset_headers", "_bill_shell", "_palette", "_one_stylesheet_linked",
              "_app_css_published", "_heading_levels",
              "_placeholder_colour", "_civics_examples", "_header_mark", "_one_stylesheet",
              "_card_words_short", "_one_head"}
NOT_ON_THE_NIGHT = {
    "_nightly_logs": "judges the nightly by its own logs: on the night, the run it is part of",
    "_full_pull_fresh": "the laptop's last pull from the bucket",
    "_refusal_reached_the_bucket": "the laptop's refusal record against the bucket's",
    "_kit_entries_match": "the laptop's own copies against the kit's list; the night has what came "
                          "down",
    "_dayfiles_pair": "the 8 September dump against the 6 September export, neither in the kit",
    "_dayfiles_pair_doctored": "the same pair, doctored, neither in the kit",
    "_late_captions_site": "the raw caption files in work/, which never leave the laptop",
    "_caption_summary_data": "the raw caption files in work/, which never leave the laptop",
    "_committee_codes_pages": "the saved status-page samples in archive_samples/",
    "_full_names_on_disk": "the dump's Committees.psv, not in the kit",
    "_hr69_title_in_journal": "the scanned 1992 House Journal in archive/unh/raw/",
    "_schedule": "the old fetched schedule.json, the laptop's",
}
# WHAT A FAILURE DOES ON A NIGHT THAT IS NOT A DRY RUN. A check against the
# official record -- one that reads the journals, calendars, dockets or the
# database dump beside the site -- and a reminder that fails on a date until a
# person acts only WARN: a slip or a change in the record must never stop the
# site. Every other check of the built site HOLDS the night for approval.
# (On a dry run any failure makes it not clean.)
RECORD_CHECKS = {
    "_a_dump_holds_the_terms_it_fills", "_calendar_copies", "_calendar_documents_on_disk",
    "_calendar_meetings", "_cite_survives", "_corrections_still_match",
    "_docket_dotted_month_on_disk", "_dropped", "_every_speaker_where_the_journal_decides",
    "_first_referral_on_disk", "_freeze_on_disk", "_introductions_against_journal",
    "_journal_folders", "_journal_folders_moved",
    "_journal_intros_on_record", "_learn_statutes_in_force", "_manifests_hold_no_called_off_sitting",
    "_no_phantom_sittings", "_own_lsr_on_disk", "_past_flags_data", "_past_measures_on_record",
    "_rail_endings_on_the_site", "_report_rec", "_rollcall_outcomes_data",
    "_session_designations_built", "_sitting_consent_on_disk", "_sponsors_on_record",
    "_vote_identity",
    # A past election, against the Secretary of State's saved files and the
    # roll calls (17 October 2026): what they find is the record's, or the
    # rule's, and never last night's.
    "_elect_2024_read_again", "_elect_2024_scored",
    # How long the night lets the record stand still, against the export's
    # finished dockets (18 October 2026): the record's history, never the site.
    "_still_days_from_history",
    # The installed files' term against the built index and the day (16
    # November 2026): build_all.py says such a difference and builds on.
    "_sitting_term_on_record",
    # The request list's Sponsors column printing co-sponsors in a form not yet
    # seen (15 November 2026): the source's shape, said on the run's page.
    "_lsr_sponsor_names_are_names"}
REMINDERS ={"_probate_after_the_vote", "_session_over_current", "_town_clerks_reread",
            "_officials_rechecked", "_town_sources_fresh"}


def built_selected(c):
    """Whether --built runs check c: a code check that reads a built site, or
    a data check the laptop is not needed for."""
    fn = c["fn"].__name__
    return fn in BUILT_CODE or (c["group"] == "data" and fn not in NOT_ON_THE_NIGHT)


def built_tier(c):
    """"warn" for a check against the record or a reminder, "hold" for the rest."""
    return "warn" if c["fn"].__name__ in RECORD_CHECKS | REMINDERS else "hold"


# ======================================================================= main ==

# EVERY RUN ENDS ON ITS SLOWEST CHECKS (26 October 2026). The night's
# `preflight.py --code` took 110 s on 9 October and 285 s on 26 October, and
# nobody saw it grow: the night's log gave the step's seconds and never which
# checks took them. Now every run says its ten slowest, by function, under its
# count, which the night prints in GitHub's own log as well as its log file
# for --code and for --built (nightly.SLOWEST_LINE); and every check's seconds
# go into the run's record (handoff.record_run's "timings") and into --built's
# list (BUILT_OUT, "seconds").
#
# The seconds in all are the whole run's, and say how many of them came
# before main() began (_loading): compiling preflight.py and defining its
# checks. main()'s own clock starts after both: a run the review of this
# branch timed at 778 s said 754. How long the compile takes depends on how
# the file is run. As `python3 preflight.py` it took about 1 s on a Linux box
# with Python 3.14.0rc2 (29 October 2026); handed to compile() -- through
# runpy, or an import with no .pyc to read -- it took 10 to 11 s, and the
# codebase review's 14 s (26 October 2026) was timed by an import and by
# compile(). The line says
# whichever this run paid. What runs after it, as the process ends, it does
# not count: the shared fixtures' folders, removed at exit, and Python's own
# teardown, 8 s of a 277 s run on that box.
SLOWEST = 10


def _slowest(took, wall, loading, n=SLOWEST):
    """The line naming the `n` slowest of `took`, [(seconds, check)], slowest
    first, with how many ran and the run's seconds in all (`wall`), `loading`
    of them before main() began."""
    top = sorted(took, key=lambda x: -x[0])[:n]
    return (f"slowest {len(top)} of {len(took)} checks, of {wall:.0f} s in all "
            f"({loading:.0f} s of it compiling and loading preflight.py): "
            + "; ".join(f"{c['fn'].__name__} {s:.1f} s" for s, c in top))


def _loading(began):
    """The seconds this process ran before `began`, main()'s start by
    time.time(): Python starting, compiling preflight.py and running it down to
    main(). Linux's /proc says when the process began. Elsewhere, Windows
    among them, it is the CPU seconds its main thread has used, which on a
    busy machine run a little behind the clock (13.1 against 13.9 s for the
    compile alone, on a loaded Linux box) -- and the same where /proc gives
    an answer that cannot be right."""
    import time
    # The main thread's: it began with the process, so its CPU seconds can be
    # no more than the process's seconds so far, as all threads' could.
    cpu = time.thread_time()
    try:
        start = _began_from(Path("/proc/self/stat").read_text(encoding="ascii"),
                            Path("/proc/uptime").read_text(encoding="ascii"),
                            os.sysconf("SC_CLK_TCK"), time.time())
    except (OSError, ValueError, IndexError, AttributeError):
        return cpu
    # No sooner than the CPU it used allows, nor longer ago than a day.
    return began - start if cpu - 0.5 <= began - start < 86400 else cpu


def _began_from(stat, uptime, hz, now):
    """When a process began, by the clock that reads `now`: from its
    /proc/<pid>/stat, whose 22nd field is the ticks from boot to its start
    (counted from the last ")", because the name in field 2 may hold spaces
    and parentheses), /proc/uptime's seconds since boot, and `hz` ticks a
    second."""
    ticks = int(stat.rsplit(")", 1)[1].split()[19])
    return now - (float(uptime.split()[0]) - ticks / hz)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", action="store_true", help="skip the data checks")
    ap.add_argument("--data", action="store_true", help="only the data checks")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--changed", nargs="?", const="", metavar="BASE",
                    help="only the checks the files changed since BASE can reach (default: "
                         "the merge base with dev), and the always-run guards "
                         "(check_select.py) -- NOT the full suite")
    ap.add_argument("--built", action="store_true",
                    help="the checks of a site just built, as the night runs them after "
                         "check_site (BUILT_CODE, and the data checks but NOT_ON_THE_NIGHT); "
                         f"writes {BUILT_OUT.as_posix()} with each one's tier")
    ap.add_argument("--manifest", metavar="FILE",
                    help="run no check: write to FILE every check, in the order a run takes "
                         "them, with its group, words, needs and marks and two fingerprints of "
                         "its code (_manifest), and nothing else -- the proof that a move of "
                         "the checks changed none")
    a = ap.parse_args()
    # NOT BOTH. --code leaves the data checks out and --data runs only them,
    # so together they ran no check at all, printed "0 passed", exited 0 and
    # left a record of a run of the code checks for handoff.py to read.
    if a.code and a.data:
        ap.error("--code leaves the data checks out and --data runs only them: together "
                 "they run nothing")
    if a.built and (a.code or a.data or a.changed is not None):
        ap.error("--built is a selection of its own: the checks of a site just built")
    if a.manifest is not None:
        # BEFORE ANYTHING A RUN DOES: no record, no early builds, nothing
        # taken out of the environment. It reads the suite's files and writes FILE.
        if a.code or a.data or a.changed is not None or a.built:
            ap.error("--manifest runs no check, so there is none to leave out or choose: it "
                     "lists every one")
        text = _manifest_text()
        Path(a.manifest).write_text(text, encoding="utf-8", newline="\n")
        print(f"{len(json.loads(text)['checks'])} checks, in the order a run takes them, "
              f"written to {a.manifest}")
        sys.exit(0)

    sys.path.insert(0, ".")
    # NOTHING HERE REACHES THE BUCKET. Since 26 September refusal.note() sends
    # a refusal to R2 on a stood-down laptop, and cloud.py pull reads it; a
    # check that drove either in the wrong folder would put a made-up refusal
    # where GitHub's night reads it, and stop the real night. cloud.py refuses
    # R2 while this is set, for this process and everything it runs; a folder
    # bucket (--local-bucket) still works.
    os.environ["GRANITE_NO_BUCKET"] = "1"
    # THE CHECKS ARE NOT THE RUN'S (7 October 2026): the workflow's word that
    # the run preflight is part of is a dry run is taken out first.
    _not_the_runs()
    # THE CHECKS BUILD BY THE CLOCK. A day stated for comparing two builds
    # (build_date.py) is not carried into the fixtures, which date a hearing
    # three days from now by the clock and would find it outside a stated
    # week. _build_date_stated states one for its own builders.
    os.environ.pop("GRANITE_BUILD_DATE", None)
    # THE RUN IS RECORDED, for handoff.py, which used to run the code checks a
    # second time straight after this had. The record names the commit and
    # the state of the working tree as this run began (handoff.tree_state),
    # so that handoff.py can refuse it once either has moved; and a digest of
    # the data files as it began (handoff.data_state), which git does not see.
    import time as _time
    handoff = imp("handoff")
    began = _time.time()
    # Before tree_state asks git: where there is no /proc, _loading is the
    # main thread's CPU seconds at the moment it is asked.
    loading = _loading(began)
    tree = handoff.tree_state() if handoff else (None, None)
    data = handoff.data_state() if handoff else None
    print("=" * 74)
    print(f"preflight   {Path('.').resolve()}")
    print(f"python {sys.version.split()[0]}")
    print("=" * 74)
    chosen = _changed_choice(a) if a.changed is not None else None
    if chosen is not None or a.built:
        # NOT RECORDED: a --changed or --built run vouches for part of the
        # suite, and handoff.py reads a record as a run of all of it.
        handoff = None

    # WHAT THIS RUN CHOSE, for a check that reads it (_THIS_RUN), and the
    # fixture sites its checks take, built beside them (_early_for_run).
    _THIS_RUN.chosen = None if chosen is None else {CHECKS[i]["fn"].__name__
                                                    for i in chosen["run"]}
    _start_early_builds(_early_for_run(a, chosen))
    results, group, built, took = [], None, [], []
    for c in _in_order(CHECKS):
        if a.code and c["group"] == "data":
            continue
        if a.data and c["group"] != "data":
            continue
        if chosen is not None and id(c) not in chosen["ids"]:
            continue
        if a.built and not built_selected(c):
            continue
        if c["group"] != group:
            group = c["group"]
            print(f"\n{group.upper()}")
        t0 = _time.perf_counter()
        mods = []
        missing = None
        for n in c["needs"]:
            m = imp(n)
            if m is None:
                missing = n
                break
            mods.append(m)
        if missing:
            status, msg = "skip", f"{missing}.py will not import"
        else:
            try:
                status, msg = _answer(c["fn"](*mods))
            except AssertionError as e:
                status, msg = "FAIL", str(e) or "assertion failed"
            except Exception as e:
                status, msg = "ERROR", f"{type(e).__name__}: {e}"
                if a.verbose:
                    traceback.print_exc()
            _OUTCOMES[c["fn"].__name__] = (status, msg)
            status, msg = _settle(status, msg, c.get("expect_fail"))
        took.append((_time.perf_counter() - t0, c))
        results.append((c["group"], c["name"], status, msg))
        if a.built:
            built.append({"fn": c["fn"].__name__, "group": c["group"], "name": c["name"],
                          "status": status, "msg": str(msg)[:600], "tier": built_tier(c),
                          "seconds": round(took[-1][0], 2)})
        mark = {"ok": "  ok  ", "skip": " skip ", "FAIL": " FAIL ",
                "ERROR": "ERROR ", "xfail": "xfail "}[status]
        print(f"  [{mark}] {c['name']}")
        if status != "ok" or a.verbose:
            for line in str(msg).splitlines():
                print(f"           {line}")

    bad = [r for r in results if r[2] in ("FAIL", "ERROR")]
    skipped = [r for r in results if r[2] == "skip"]
    ok = [r for r in results if r[2] == "ok"]
    expected = [r for r in results if r[2] == "xfail"]
    if a.built:
        # What nightly.py reads (its BUILT_CHECKS): every check run, its
        # status and its tier.
        BUILT_OUT.parent.mkdir(parents=True, exist_ok=True)
        BUILT_OUT.write_text(json.dumps(built, indent=1), encoding="utf-8")
    if handoff:
        handoff.record_run("code" if a.code else "data" if a.data else "all", results,
                           tree, _time.time() - began, data=data,
                           timings=[(c["fn"].__name__, s) for s, c in took])

    print("\n" + "=" * 74)
    print(f"{len(ok)} passed, {len(bad)} failed, {len(skipped)} skipped"
          + (f", {len(expected)} expected to fail" if expected else ""))
    print(_slowest(took, loading + _time.time() - began, loading))
    if bad:
        print("\nWhat is broken:")
        for g, n, s, m in bad:
            print(f"  {g}/{n}")
            print(f"    {str(m)[:150]}")
        print("\nEach of these is independent, so fix them in any order. Nothing")
        print("here touched the site or the data files.")
    if skipped:
        print("\nSkipped, mostly because the file is not in this folder:")
        for g, n, s, m in skipped:
            print(f"  {g}/{n}: {m}")
    if expected:
        print("\nExpected to fail, each until the change it names lands (its findings are "
              "above):")
        for g, n, s, m in expected:
            print(f"  {g}/{n}")
            print(f"    {str(m).splitlines()[0][:150]}")
    if not bad:
        print("\nEverything that can be checked without the network is working"
              + (f", but for the {len(expected)} expected failures above." if expected else "."))
        print("What is left needs real data: run src/ops/inventory.py, then align_all,")
        print("then src/hearings/segment_markers.py --all --data data, and score the result:")
        print("  src/hearings/probe_alignment.py --truth --candidate candidate_segments.json")
        print("Do not run src/hearings/apply_markers.py --apply. It is the superseded")
        print("clustering path; build_all skips it unless --with-superseded,")
        print("and it overwrites boundaries segment_markers read from the chair.")
    if chosen is not None:
        print(f"\n--changed: all of that is of the {len(results)} checks run, of "
              f"{chosen['pool']}. THIS IS NOT THE FULL SUITE: python3 preflight.py runs "
              "every check, and runs before a merge into dev.")
    print("=" * 74)
    sys.exit(1 if bad else 0)


def _changed_choice(a):
    """--changed: which checks a change since a.changed (or the merge base
    with dev) can reach (check_select.choose), said before any of them runs,
    with the always-run core by name and the plain words that this is not
    the full suite."""
    import check_select as CS
    try:
        got = CS.choose(CHECKS, _suite_files(), a.changed or None, parse=_parsed)
    except RuntimeError as e:
        print(f"--changed: {e}")
        sys.exit(2)
    if got["core_missing"]:
        print("--changed: check_select.CORE names " + ", ".join(got["core_missing"])
              + ", which is no longer a check here, and a renamed guard would drop out of "
              "every --changed run: name it again in CORE")
        sys.exit(2)
    pool = {i for i, c in enumerate(CHECKS)
            if not (a.code and c["group"] == "data") and not (a.data and c["group"] != "data")}
    got["run"] = {i: r for i, r in got["run"].items() if i in pool}
    got["ids"] = {id(CHECKS[i]) for i in got["run"]}
    got["pool"] = len(pool)
    ch = got["changed"]
    print(f"--changed since {got['base'][:10]} ({a.changed or 'the merge base with dev'}): "
          f"{len(ch)} file(s) changed" + (": " + ", ".join(ch[:12])
                                          + (f" and {len(ch) - 12} more" if len(ch) > 12 else "")
                                          if ch else ""))
    kinds = Counter("core" if r == "core" else "scan" if r == "reads every code file"
                    else "near" for r in got["run"].values())
    print(f"running {len(got['run'])} of {len(pool)} checks: {kinds['core']} always, the core "
          f"({', '.join(CS.CORE)}); {kinds['scan']} that read every code file; "
          f"{kinds['near']} related to what changed. Skipping {len(pool) - len(got['run'])}.")
    print("THIS IS NOT THE FULL SUITE: python3 preflight.py runs every check, and runs "
          "before a merge into dev. --verbose says why each check was chosen.")
    if a.verbose:
        for i, r in sorted(got["run"].items()):
            print(f"  {CHECKS[i]['fn'].__name__}: {r}")
    print("=" * 74)
    return got


def _early_for_run(a, chosen):
    """Which early builds main() starts for a run of the arguments `a`: every
    one (None) for a run of every check of a kind but the data's; none for
    --built or --data, whose checks build no fixture site; and for --changed
    those its chosen checks take (`chosen` as _changed_choice gives it;
    _early_wanted)."""
    if a.built or a.data:
        return set()
    if chosen is None:
        return None
    return _early_wanted([CHECKS[i] for i in chosen["run"]])
