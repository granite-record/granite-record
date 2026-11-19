#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.4
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

from pf_core import (CHECKS, _OUTCOMES, _THIS_RUN, _answer, _in_order, _manifest, _manifest_text,
                     _map_kept, _parsed, _settle, _suite_files, imp)
from pf_fixture import (_EARLY_MAP, _EARLY_THREADS, _early_wanted, _start_early_builds)
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
    # A district the roster, the results or the map prints that the district table does not
    # hold (16 November 2026): the record's spelling or the table's age, never last night's.
    "_districts_printed_today",
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


# ---- the map: what each check read and ran (19 November 2026) -----------------
#
# THE MAP (the refactor's stage 1, step 8; reports/refactor/stage0-checks.md,
# sections 6 and 9). --changed chooses its checks by what their code names
# (check_select.py), which chooses hundreds where a change reaches a hub
# module and a handful where a check reads a folder whole. The map is what a
# later step may choose by instead: what each check was SEEN to read and run.
# This records it and chooses nothing. A run of every check of a kind -- the
# suite, --code, --data or --built; never --changed, which runs a part --
# writes for each check, in the order it ran:
#   reads    the repository's files it opened to read, but for a module's
#            import (imports), and every file a cache answered it
#            (pf_core._map_read, _map_kept);
#   lists    the repository's folders it listed (os.listdir, os.scandir, and
#            so glob, os.walk and copytree);
#   starts   the repository's files named on a command it started;
#   funcs    the repository's functions it ran, as "path:name" -- a method as
#            Class.method, a function defined inside another as the outer
#            one, and a module's own code, a class's body or a lambda at the
#            top as "<module>" and the class's name;
#   kept     the once-a-run work it took (_map_kept's keys), whose reads and
#            functions are among its own, as they are the check's that did
#            the work;
#   untraced how many Python children it started with no environment of their
#            own, which the map cannot follow;
# with its fingerprints from the manifest and its seconds. Its Python children
# are watched as it is: the environment each is handed (child.run always hands
# one) gets a folder holding _MAP_SITE as a sitecustomize.py at the head of
# PYTHONPATH, which records the child and, before the child's own code runs,
# takes the folder and its own words back out of the child's path and
# environment and runs the sitecustomize.py that stood behind it, as the
# seal's (pf_core._Seal); a child of a child is followed the same way.
# What it watches with: an audit hook (sys.addaudithook) for the files and
# the commands, installed once a process and idle while no map is kept, and
# sys.monitoring's PY_START for the functions, each function told once and
# then turned off until the next check turns every one back on
# (restart_events), so a function costs one call a check, not one a call.
# The early builds' threads (pf_fixture._EARLY_THREADS) are recorded as
# _EARLY_MAP's, which every check that takes one takes.
# RECORDS ONLY. No check is chosen, ordered or answered by it; a hook that
# fails is silent and records less; the map that cannot be written is one
# line under the run's count, and the run's exit is its checks'. Node's own
# reads and functions are not in it (step 10 of the plan), nor a file a
# module read when an earlier check imported it, nor what a cache inside a
# project module (functools.cache) answered without running.
# WHERE: logs/check-map-<kind>.json.gz, beside the run's record
# (logs/preflight-last.json), which git ignores and no build reads: the map
# describes a run of the checks, as that does, and is made again by the next
# one. Kept apart by kind, since the night's --code and --built see what the
# laptop's suite does not, and read together. src/checks/map_replay.py reads it.
MAP_OUT = "logs/check-map-{kind}.json.gz"
MAP_FORMAT = 1
MAP_ENV = ("GRANITE_CHECK_MAP", "GRANITE_CHECK_MAP_TO", "GRANITE_CHECK_MAP_ROOT")
_MAP_KINDS = ("reads", "imports", "lists", "starts", "funcs")

_MAP_SITE = r'''# Written by preflight.py (pf_runner._MapRecorder): what this process read and ran, for the map.
def _granite_map():
    import os
    import sys
    env = os.environ
    out, to, root = (env.get(k, "") for k in ("GRANITE_CHECK_MAP", "GRANITE_CHECK_MAP_TO",
                                                "GRANITE_CHECK_MAP_ROOT"))
    here = os.path.normcase(os.path.dirname(os.path.abspath(__file__)))

    def ours(d):
        try:
            return bool(d) and os.path.normcase(os.path.abspath(d)) == here
        except Exception:
            return False
    behind = None
    for d in sys.path:
        f = os.path.join(d, "sitecustomize.py") if d and not ours(d) else ""
        if f and os.path.isfile(f):
            behind = f
            break
    sys.path[:] = [d for d in sys.path if not ours(d)]
    parts = [p for p in env.get("PYTHONPATH", "").split(os.pathsep) if p and not ours(p)]
    if parts:
        env["PYTHONPATH"] = os.pathsep.join(parts)
    else:
        env.pop("PYTHONPATH", None)
    for k in ("GRANITE_CHECK_MAP", "GRANITE_CHECK_MAP_TO", "GRANITE_CHECK_MAP_ROOT"):
        env.pop(k, None)
    if out and to and root:
        try:
            _granite_watch(out, to, root, os.path.dirname(os.path.abspath(__file__)))
        except Exception:
            pass
    if behind:
        import types
        mod = types.ModuleType("sitecustomize")
        mod.__file__ = behind
        with open(behind, encoding="utf-8") as fh:
            exec(compile(fh.read(), behind, "exec"), mod.__dict__)


def _granite_watch(out, to, root, site):
    import atexit
    import os
    import sys
    got = {k: set() for k in ("reads", "imports", "lists", "starts", "funcs")}
    untraced = [0]
    on = [True]
    nroot = os.path.normcase(os.path.abspath(root)).rstrip("\\/") + os.sep
    W = os.O_WRONLY | getattr(os, "O_CREAT", 0) | getattr(os, "O_APPEND", 0) | getattr(os, "O_TRUNC", 0)

    def under(p, cwd=None):
        if isinstance(p, int) or p is None:
            return None
        if isinstance(p, bytes):
            p = os.fsdecode(p)
        p = os.fspath(p)
        p = os.path.abspath(os.path.join(cwd, p) if cwd else p)
        n = os.path.normcase(p)
        if n + os.sep == nroot:
            return "."
        if not n.startswith(nroot):
            return None
        rel = p[len(nroot):].replace("\\", "/")
        return None if "__pycache__" in rel else rel

    def from_import():
        return sys._getframe(2).f_code.co_filename.startswith("<frozen importlib")

    def words(argv):
        # Windows hands the hook the command as one line: its words, quotes taken off.
        if not isinstance(argv, str):
            return list(argv) if isinstance(argv, (list, tuple)) else []
        out, cur, q, quoted = [], [], False, False
        for ch in argv[:4096]:
            if ch == '"':
                q, quoted = not q, True
            elif ch in " \t" and not q:
                if cur or quoted:
                    out.append("".join(cur))
                cur, quoted = [], False
            else:
                cur.append(ch)
        if cur or quoted:
            out.append("".join(cur))
        return out

    def hook(event, args):
        if not on[0]:
            return
        try:
            if event == "open":
                path, mode, flags = args
                if isinstance(mode, str):
                    if "w" in mode or "a" in mode or "x" in mode:
                        return
                elif isinstance(flags, int) and flags & W:
                    return
                rel = under(path)
                if rel:
                    got["imports" if from_import() else "reads"].add(rel)
            elif event in ("os.listdir", "os.scandir"):
                if not from_import():
                    rel = under(args[0] if args and args[0] is not None else ".")
                    if rel is not None:
                        got["lists"].add(rel)
            elif event == "subprocess.Popen":
                executable, argv, cwd, cenv = args
                argv = words(argv)
                try:
                    for a in argv:
                        if isinstance(a, (str, os.PathLike)) and len(os.fspath(a)) < 400:
                            rel = under(a, cwd)
                            if rel and rel != "." and os.path.isfile(os.path.join(root, rel)):
                                got["starts"].add(rel)
                except Exception:
                    pass
                if isinstance(cenv, dict):
                    cenv["GRANITE_CHECK_MAP"], cenv["GRANITE_CHECK_MAP_TO"] = out, to
                    cenv["GRANITE_CHECK_MAP_ROOT"] = root
                    pp = [p for p in cenv.get("PYTHONPATH", "").split(os.pathsep) if p]
                    cenv["PYTHONPATH"] = os.pathsep.join([site] + [p for p in pp if p != site])
                elif "python" in os.path.basename(str(executable or (argv[0] if argv else ""))).lower():
                    untraced[0] += 1
        except Exception:
            pass
    sys.addaudithook(hook)
    mon = getattr(sys, "monitoring", None)
    codes = {}
    if mon is not None:
        tool = next((t for t in (4, 3, 5, 2) if mon.get_tool(t) is None), None)
        if tool is not None:
            mon.use_tool_id(tool, "preflight: the map")

            def started(code, offset):
                k = codes.get(code)
                if k is None:
                    rel = under(code.co_filename) if on[0] else None
                    k = False
                    if rel and rel.endswith(".py"):
                        q = code.co_qualname.split(".<locals>", 1)[0]
                        k = rel + ":" + ("<module>" if q.startswith("<") else q)
                    codes[code] = k
                if k:
                    got["funcs"].add(k)
                return mon.DISABLE
            mon.register_callback(tool, mon.events.PY_START, started)
            mon.set_events(tool, mon.events.PY_START)

    def write():
        on[0] = False
        try:
            import json
            import time
            body = {k: sorted(v) for k, v in got.items()}
            body["to"], body["untraced"] = int(to), untraced[0]
            name = os.path.join(out, f"{os.getpid()}-{time.time_ns()}.json")
            with open(name + ".part", "w", encoding="utf-8") as fh:
                json.dump(body, fh)
            os.replace(name + ".part", name)
        except Exception:
            pass
    atexit.register(write)


_granite_map()
del _granite_map, _granite_watch
'''

# Every recorder on, the innermost last: the audit hook tells the last.
_MAP_ON = []
_MAP_HOOKED = []


def _map_hook(event, args):
    """The process's one audit hook for the map (above): idle while no map is
    kept, and silent whatever happens in it."""
    if _MAP_ON and event in _MapRecorder.EVENTS:
        try:
            _MAP_ON[-1].event(event, args)
        except Exception:                                       # noqa: BLE001
            pass


class _MapRecorder:
    """What each check of a run read and ran (the map, above). begin(name)
    before a check and end() after it; enter(key) and leave(key) around a
    once-a-run helper's work (pf_core._map_kept); read(path) for a file a
    cache answered; then map(...) for what is written."""

    EVENTS = frozenset(("open", "os.listdir", "os.scandir", "subprocess.Popen"))
    OWN = ("_MapRecorder", "_map_")
    WRITES = os.O_WRONLY | getattr(os, "O_CREAT", 0) | getattr(os, "O_APPEND", 0) \
        | getattr(os, "O_TRUNC", 0)

    def __init__(self, root=None):
        import _paths
        import _thread
        self.root = str(Path(root or _paths.ROOT).resolve())
        self.nroot = os.path.normcase(self.root).rstrip("\\/") + os.sep
        self.buckets, self.named, self.stack = [], {}, []
        self.codes = {}
        self.main = _thread.get_ident()
        self.ident = _thread.get_ident
        self.dir = self.site = self.tool = None
        self.on = False
        self.early = self.bucket(("kept", _EARLY_MAP))

    # -- the buckets: one a check, one a key a helper kept work under --------

    def bucket(self, name):
        if name not in self.named:
            self.named[name] = len(self.buckets)
            self.buckets.append({**{k: set() for k in _MAP_KINDS}, "untraced": 0, "takes": set()})
        return self.named[name]

    def target(self):
        """The bucket what happens now goes to: the innermost key a helper is
        keeping work under, else the check running; an early build's thread's
        goes to _EARLY_MAP. None between checks."""
        if self.ident() != self.main:
            import threading
            if threading.current_thread().name.startswith(_EARLY_THREADS):
                return self.early
        return self.stack[-1] if self.stack else None

    def begin(self, name):
        self.stack = [self.bucket(("check", name))]
        self._rearm()

    def end(self):
        self.stack = []

    def enter(self, key):
        b = self.bucket(("kept", key))
        if self.stack:
            self.buckets[self.stack[-1]]["takes"].add(b)
        self.stack.append(b)
        self._rearm()

    def leave(self, key):
        b = self.named.get(("kept", key))
        if self.stack and self.stack[-1] == b:
            self.stack.pop()
            self._rearm()

    def _rearm(self):
        if self.tool is not None:
            sys.monitoring.restart_events()

    # -- what is seen ----------------------------------------------------------

    def under(self, p, cwd=None):
        """`p`'s path from the root with "/", or None where it is not a file of
        the repository (or a cache of compiled code)."""
        if isinstance(p, int) or p is None:
            return None
        if isinstance(p, bytes):
            p = os.fsdecode(p)
        p = os.fspath(p)
        p = os.path.abspath(os.path.join(cwd, p) if cwd else p)
        n = os.path.normcase(p)
        if n + os.sep == self.nroot:
            return "."
        if not n.startswith(self.nroot):
            return None
        rel = p[len(self.nroot):].replace("\\", "/")
        return None if "__pycache__" in rel else rel

    def read(self, path):
        b = self.target()
        rel = self.under(path) if b is not None else None
        if rel:
            self.buckets[b]["reads"].add(rel)

    def event(self, event, args):
        if not self.on:
            return
        b = self.target()
        if b is None:
            return
        got = self.buckets[b]
        if event == "open":
            path, mode, flags = args
            if isinstance(mode, str):
                if "w" in mode or "a" in mode or "x" in mode:
                    return
            elif isinstance(flags, int) and flags & self.WRITES:
                return
            rel = self.under(path)
            if rel:
                got["imports" if self._from_import() else "reads"].add(rel)
        elif event in ("os.listdir", "os.scandir"):
            if not self._from_import():
                rel = self.under(args[0] if args and args[0] is not None else ".")
                if rel is not None:
                    got["lists"].add(rel)
        elif event == "subprocess.Popen":
            self._popen(got, b, *args)

    @staticmethod
    def _from_import():
        # The frame that opened: the hook's caller's caller (event, then this).
        return sys._getframe(3).f_code.co_filename.startswith("<frozen importlib")

    @staticmethod
    def words(argv):
        """The words of a command as the audit hook is handed it: a list, or on
        Windows one line, read here with its quotes taken off."""
        if not isinstance(argv, str):
            return list(argv) if isinstance(argv, (list, tuple)) else []
        out, cur, q, quoted = [], [], False, False
        for ch in argv[:4096]:
            if ch == '"':
                q, quoted = not q, True
            elif ch in " \t" and not q:
                if cur or quoted:
                    out.append("".join(cur))
                cur, quoted = [], False
            else:
                cur.append(ch)
        if cur or quoted:
            out.append("".join(cur))
        return out

    def _popen(self, got, b, executable, argv, cwd, env):
        argv = self.words(argv)
        try:
            for a in argv:
                if isinstance(a, (str, os.PathLike)) and len(os.fspath(a)) < 400:
                    rel = self.under(a, cwd)
                    if rel and rel != "." and os.path.isfile(os.path.join(self.root, rel)):
                        got["starts"].add(rel)
        except Exception:                                       # noqa: BLE001
            pass
        if isinstance(env, dict) and self.site:
            env[MAP_ENV[0]], env[MAP_ENV[1]], env[MAP_ENV[2]] = self.dir, str(b), self.root
            pp = [p for p in env.get("PYTHONPATH", "").split(os.pathsep) if p]
            env["PYTHONPATH"] = os.pathsep.join([self.site] + [p for p in pp if p != self.site])
        elif "python" in os.path.basename(str(executable or (argv[0] if argv else ""))).lower():
            got["untraced"] += 1

    def _started(self, code, offset):
        k = self.codes.get(code)
        if k is None:
            rel = self.under(code.co_filename)
            k = False
            if rel and rel.endswith(".py"):
                q = code.co_qualname.split(".<locals>", 1)[0]
                k = rel + ":" + ("<module>" if q.startswith("<") else q)
                if rel.startswith("src/checks/suite/") and q.startswith(self.OWN):
                    k = False       # the map's own code, which every check would carry
            self.codes[code] = k
        if k and self.on:
            b = self.target()
            if b is not None:
                self.buckets[b]["funcs"].add(k)
            if b == self.early and self.ident() != self.main:
                return None     # the early builds' threads do not turn a function off
        return sys.monitoring.DISABLE

    # -- on and off ------------------------------------------------------------

    def start(self):
        """Begin watching: the children's folder, the hook, a tool of
        sys.monitoring. Where no tool is free, the map has no functions."""
        import atexit
        import shutil
        import tempfile
        self.dir = tempfile.mkdtemp(prefix="gr-map-")
        atexit.register(shutil.rmtree, self.dir, ignore_errors=True)
        self.site = os.path.join(self.dir, "site")
        os.mkdir(self.site)
        with open(os.path.join(self.site, "sitecustomize.py"), "w", encoding="utf-8") as fh:
            fh.write(_MAP_SITE)
        if not _MAP_HOOKED:
            sys.addaudithook(_map_hook)
            _MAP_HOOKED.append(True)
        mon = getattr(sys, "monitoring", None)
        if mon is not None:
            self.tool = next((t for t in (4, 3, 5, 2) if mon.get_tool(t) is None), None)
            if self.tool is not None:
                mon.use_tool_id(self.tool, "preflight: the map")
                mon.register_callback(self.tool, mon.events.PY_START, self._started)
                mon.set_events(self.tool, mon.events.PY_START)
        self.on = True
        _MAP_ON.append(self)
        return self

    def stop(self):
        """Stop watching, and take in what the children recorded."""
        import json
        import shutil
        self.on = False
        if self in _MAP_ON:
            _MAP_ON.remove(self)
        if self.tool is not None:
            mon = sys.monitoring
            mon.set_events(self.tool, 0)
            mon.register_callback(self.tool, mon.events.PY_START, None)
            mon.free_tool_id(self.tool)
            self.tool = None
        if self.dir and os.path.isdir(self.dir):
            for name in os.listdir(self.dir):
                if not name.endswith(".json"):
                    continue
                try:
                    with open(os.path.join(self.dir, name), encoding="utf-8") as fh:
                        got = json.load(fh)
                    into = self.buckets[int(got["to"])]
                except (OSError, ValueError, KeyError, IndexError, TypeError):
                    continue
                for k in _MAP_KINDS:
                    into[k].update(got.get(k) or ())
                into["untraced"] += int(got.get("untraced") or 0)
            shutil.rmtree(self.dir, ignore_errors=True)
        self.dir = self.site = None

    # -- what is written -------------------------------------------------------

    def seen(self, name):
        """{kind: set} of the check `name`, with everything it took, at any
        depth, and the keys it took."""
        b0 = self.named.get(("check", name))
        out = {**{k: set() for k in _MAP_KINDS}, "untraced": 0, "kept": set()}
        if b0 is None:
            return out
        keys = {b: n[1] for n, b in self.named.items() if n[0] == "kept"}
        todo, seen = [b0], set()
        while todo:
            b = todo.pop()
            if b in seen:
                continue
            seen.add(b)
            got = self.buckets[b]
            for k in _MAP_KINDS:
                out[k] |= got[k]
            out["untraced"] += got["untraced"]
            if b in keys:
                out["kept"].add(keys[b])
            todo += got["takes"]
        return out

    def map(self, kind, ran, prints=None):
        """The map of the checks `ran`, [(check, seconds)] in the order they
        ran: the file's whole content (MAP_FORMAT)."""
        import datetime
        import platform
        files, funcs, rows = {}, {}, []
        for c, secs in ran:
            fn = c["fn"].__name__
            got = self.seen(fn)
            row = {"fn": fn, "group": c["group"], "needs": list(c["needs"]),
                   "seconds": round(secs, 2)}
            if prints and fn in prints:
                row["own"], row["reach"] = prints[fn]
            for k in _MAP_KINDS:
                table = funcs if k == "funcs" else files
                row[k] = sorted(table.setdefault(x, len(table)) for x in got[k])
            row["kept"], row["untraced"] = sorted(got["kept"]), got["untraced"]
            rows.append(row)
        commit, idents, dirty = _map_files(self.root, files)
        return {"format": MAP_FORMAT, "kind": kind, "commit": commit, "dirty": dirty,
                "python": platform.python_version(),
                "finished": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                "files": [[p, idents.get(p, "")] for p in sorted(files, key=files.get)],
                "funcs": sorted(funcs, key=funcs.get), "checks": rows}


def _map_files(root, files):
    """(the commit HEAD names, {path: what it held}, the tracked files the
    working tree has changed): a tracked file by git's blob id ("git:<id>"),
    any other by its size and time of writing ("size:<n>:<ns>"), a folder
    "dir", and one gone since "gone". Git's ids cost nothing to read, and a
    change since the map's commit is git's to say."""
    import child
    idents, commit, dirty = {}, "", []
    try:
        r = child.run(["git", "ls-files", "-s", "-z"], cwd=root, capture_output=True, timeout=120)
        for row in (r.stdout or "").split("\0") if r.returncode == 0 else ():
            if "\t" in row:
                head, path = row.split("\t", 1)
                idents[path] = "git:" + head.split()[1]
        r = child.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, timeout=60)
        commit = (r.stdout or "").strip() if r.returncode == 0 else ""
        r = child.run(["git", "diff", "--name-only", "-z", "HEAD"], cwd=root, capture_output=True,
                      timeout=120)
        dirty = sorted(p for p in (r.stdout or "").split("\0") if p) if r.returncode == 0 else []
    except (OSError, ValueError):
        pass
    out = {}
    for p in files:
        if p in idents and p not in dirty:
            out[p] = idents[p]
            continue
        f = os.path.join(root, p)
        try:
            st = os.stat(f)
            out[p] = "dir" if os.path.isdir(f) else f"size:{st.st_size}:{st.st_mtime_ns}"
        except OSError:
            out[p] = "gone"
    return commit, out, dirty


def _map_prints():
    """{check: (own, reach)} from the manifest (pf_core._manifest), or {} where
    it cannot be made."""
    try:
        return {e["fn"]: (e["own"], e["reach"]) for e in _manifest()["checks"]}
    except Exception:                                           # noqa: BLE001
        return {}


def _map_write(rec, kind, ran, out=None):
    """Write the map of the checks `ran` that `rec` watched to MAP_OUT for
    `kind` (or `out`), whole and at once, and say so in a line; a map that
    cannot be made or written is that line, and nothing else."""
    import gzip
    path = Path(out or MAP_OUT.format(kind=kind))
    try:
        rec.stop()
        body = rec.map(kind, ran, _map_prints())
        path.parent.mkdir(parents=True, exist_ok=True)
        part = path.with_name(path.name + ".part")
        with gzip.open(part, "wt", encoding="utf-8", compresslevel=6) as fh:
            json.dump(body, fh, separators=(",", ":"))
        os.replace(part, path)
        return (f"the map of what each check read and ran: {path.as_posix()} "
                f"({len(body['checks'])} checks, {len(body['files'])} files, "
                f"{len(body['funcs'])} functions)")
    except Exception as e:                                      # noqa: BLE001
        return f"the map of what each check read and ran was not written: {type(e).__name__}: {e}"


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
    ap.add_argument("--no-map", action="store_true",
                    help="do not record the map of what each check read and ran, which a run "
                         "of every check of a kind writes to " + MAP_OUT.format(kind="<kind>")
                         + " (the map, in pf_runner.py)")
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
    # THE MAP (above): what each check read and ran, in a run of every check
    # of a kind. It records, and chooses and changes nothing.
    rec = None
    if chosen is None and not a.no_map:
        try:
            rec = _MapRecorder().start()
        except Exception as e:                                  # noqa: BLE001
            print(f"the map of what each check read and ran is not kept this run: "
                  f"{type(e).__name__}: {e}")
        _THIS_RUN.map = rec
    with _map_kept(_EARLY_MAP):
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
        if rec is not None:
            rec.begin(c["fn"].__name__)
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
        if rec is not None:
            rec.end()
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
    if rec is not None:
        _THIS_RUN.map = None
        print(_map_write(rec, "built" if a.built else "code" if a.code else "data" if a.data
                         else "all", [(c, s) for s, c in took]))
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
