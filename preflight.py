#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.952
"""
Run every check that needs no network, and report all of them at once.

    python3 preflight.py            # everything
    python3 preflight.py --code     # logic only, ignore the data on disk
    python3 preflight.py --verbose  # show what each check actually produced
    python3 preflight.py --changed  # only what a change since the merge base with
                                    #   dev can reach, and the core: NOT the full suite
    python3 preflight.py --manifest FILE
                                    # no check run: every check in run order, with
                                    #   two fingerprints of its code, into FILE

The failure this exists to prevent: twelve files change, the first one raises on
line 3, and an hour goes into that one traceback while the other eleven stay
unknown. Nothing here stops at the first failure. Every check is independent,
catches its own exceptions, and reports. What you get is a list of what is
broken, not the first thing that broke.

This is the companion to inventory.py, not a replacement. That answers "am I
running the copy you gave me". This answers "does the copy I am running work".
Run inventory first; a failure here on a stale file is not worth debugging.

WHAT IT DOES NOT DO

No network, no YouTube, no gencourt. It never runs a build and never writes
anything into the project: the marker checks build a throwaway tree under the
system temp directory and delete it. Running this cannot change the site and
cannot lose anything. The one file it leaves is its own record of the run,
logs/preflight-last.json, which handoff.py reads in place of running the
checks a second time; git ignores logs/ and no build reads it. Outside the
project it keeps one more, in the system temp directory: its parse of the
officials directory (_officials_read), made again whenever the PDF, its
parser or the PDF library changes.

TWO HALVES

CODE checks call the changed functions with fixed inputs and known answers.
They run anywhere, need no data, and prove the logic works on your Python
before it meets 2,234 bills.

DATA checks run only when the real files are present, and are read-only. They
answer the questions the code cannot: what shape former_members.json really is,
what the manifest's venue values look like, how many docket rows the proceeding
parser drops on the floor.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import ast
import csv
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import traceback
from collections import Counter

import child

# THE SUITE'S OWN MODULES (16 November 2026, the refactor's stage 1, step 4).
# The registry, the runner and the helpers the checks share are modules of
# src/checks/suite/ (README.md there), so that a check registers into a
# registry that is a module's and not this script's. Every name is imported
# here, so that a check, and anything that reads this module, finds each as it
# did. The checks are in the modules by area imported below, which register
# them as they are imported, and those not moved yet are here; a run takes
# them in ORDER.json's order.
from pf_core import (CHECKS, _run, _SEAL_SITE, _PROXY_NAMES, _Seal, _sealed_run, check,
                     _in_order, _settle, _answer, imp, _suite_files, _in_suite,
                     _suite_namespaces, _Switches, _SWITCHED, _SOURCES, _SOURCE_TEXT, _source,
                     _PARSED, _parsed, _parsed_warned, _PIECE_LINES, _PIECE_FROM, _PIECE_OPENS,
                     _piece_cuts, _parse_whole, _parse_in_pieces, _MANIFEST_DEFS,
                     _manifest_tops, _manifest_print, _ManifestPrints, _manifest,
                     _manifest_text, _OUTCOMES, _ThisRun, _THIS_RUN, _reaching, _check_outcome)
from pf_fixture import (_NB_FIXTURE, _site_fixture, FIXTURE_VIDEO_COLS, FIXTURE_VIDEOS,
                        _fixture_videos, PROCEEDINGS_MODULES, CHAIN_NEEDS, _stand_in_png,
                        LICENSED_STAND_IN, _fixture_brand, _study_fixture, _built_site,
                        _built_site_prepare, _built_site_run, _MADE_ONCE, _once_a_run,
                        _shared_root, _fixture_site_v2, _fixture_site_shared,
                        _fixture_site_whole, _EARLY, _start_early_builds, _early_build,
                        _built_nobrand, _built_stated, _EARLY_TAKEN_BY, _early_wanted)
from pf_harness import (_app_js, _TESTIFY_LOG_TAIL, _node_app, _components_js, _node_file,
                        _with_components, _STRIPPED, _stripped)
from pf_runner import (MAIN_REF, WORKFLOW_WORDS, CHECKS_REF, RUNNER_FILES, _not_the_runs,
                       BUILT_OUT, BUILT_CODE, NOT_ON_THE_NIGHT, RECORD_CHECKS, REMINDERS,
                       built_selected, built_tier, SLOWEST, _slowest, _loading, _began_from,
                       main, _changed_choice, _early_for_run)
from pf_shared import (_bill_index_write, _site_bills, _RECORD_WHOLE, _RECORD_KEPT,
                       _SITE_RECORDS, _KeptRecord, _site_records, _RUNNERS, _mk, _plant,
                       _first_script, _RUN_BY_PATH, _runner_names, _RUNNER_FLOORS,
                       _DOCKET_OVERTAKEN, _told_from_rows, _DOCKET_TIME_CHANGE, _ROOM_CHANGED,
                       _CLOCK_SEMICOLON, _CLERKS_COMMITTEES, _ev, _nar, _SOS_2024, _MANUAL_1993,
                       _MANUAL_1999, _BALLOTPEDIA, _voters_row, _ballot_file, _narrated,
                       _CHIP_STAGES, _CHIP_OWN, _CHIP_FINISHED, _CHIP_LIVE,
                       _CONSENT_REMOVAL_LOOSE, _CONSENT_REMOVAL_NOT, _WRITTEN_DAY,
                       _COMMITTEE_WORK, _SITTINGS, _sittings_on_disk, _json3, _inbox_words,
                       _inbox_files, page_source, _cite_plain, _cors_rules, _cors_said,
                       _css_hex, _css_ratio, _css_rules, _css_decls, _css_palette, _css_px,
                       _css_font_size, _FRONT_EXEMPT, _front_sources, _line_of, _css_selectors,
                       _css_token_colour, _built_sites, ic_SOURCES, LSR_LISTLIKE,
                       _strip_js_comments, _VERDANA, _RAIL_FACE, _SUMMARY_VOTES,
                       _ballot_mixed_rows, BASE_HREF, OFFSITE, INLINE_BODY,
                       _JOURNAL_MOTION_AFTER, _READ_ONCE, _read_once, _narratives, _json_rows,
                       _ballot_census, _docket_rows, _DOCKET_CUT_1999, _site_gen,
                       _sitting_fixture, _rc, _one_roll_call_each, SD_key, CALENDAR_PAGE,
                       AMENDMENT_PAGE, _HEARD_PRELUDE, _STATUS_CATEGORY, _STATUS_REAL_PAIRS,
                       _STATUS_CATS, _STATUSCAT_HARNESS, _json3_cues, _cloud_call, _DOCS_FIX,
                       _DOCS_REAL, _DOCS_H, _DOCS_S, _DOCS_HC, _DOCS_HJ, _DOCS_SJ, _DOCS_HC25,
                       _DOCS_HJ25, _DOCS_SJ25, _docs_page, _docs_fixture, _docs_turn,
                       _docs_write_old, _DOCS_HC35, _DOCS_SC29, _hearing_fixture,
                       _FULL_COMMITTEE_NAMES, _VW_DOT_HEAD, _vw_loose_dots, CAL_TODAY,
                       _cal_rows, _cal_fixture, _cal_node, _fixture_drawn, _CAL_DOM, _braced,
                       _rsa_sections, _css_parts, _css_simple, _css_compound_fits,
                       _css_can_reach, _css_specificity, _OUTLINE_STYLES, _css_sides,
                       _css_screen_rules, _css_won, _html_walk, _officials_now, _visible_text,
                       _ASKS_GC_FLOOR, _tap_failures, NIGHTLY_STALE_HOURS, NIGHTLY_WEEK,
                       NIGHTLY_SCHEDULE_RUN, NIGHTLY_DAY_APART, NIGHTLY_STARTED,
                       NIGHTLY_INSTALLED, NIGHTLY_NO_FETCH, NIGHTLY_REPORTS_RAN,
                       NIGHTLY_REPORTS_FAILED, NIGHTLY_WHY, NIGHTLY_WHY_UNNAMED, _nightly_night,
                       _installed_none, _nightly_log_findings, _nightly_log_selftest,
                       _TURN_LASTS, _turn_day, _turn_member, _turn_files, _DBDAY_VIEWS,
                       _DBDAY_EXPORT, _dbday_bytes, _dbday_install, _dbday_views,
                       _dbday_expected, _DBGUARD_REAL, _workflows, _wf_block, _wf_jobs,
                       _wf_steps, _wf_code, _HAND, WF_RUNS, _GH_TOKEN, _gh_eval, _gh_render,
                       _wf_value, _wf_dry_run_sets, _wf_run_ctx, _gh_unwrap, _wf_job_heads,
                       _member_surnames, _one_edit, _speakers_against_journal,
                       SPONSOR_HONORIFIC, _ELECT_SOURCE, _ELECT_IN, _elect_former,
                       _ELECT_FORMER, _ELECT_DEADLINE, _ELECT_HAND, _elect_absent,
                       _elect_fixture, _elect_run, _elect_part, _ELECT_BASE, _ELECT_PAGES,
                       _ELECT_TAG, _elect_pages, _elect_blocks, _elect_strip, _elect_built,
                       _ELECT_CARD_JS, _elect_card, _map_data, _MAP_TOTALS_JS, _map_totals_run,
                       _map_totals_text, _LEFT_OUT, _CARD_DOCKETS, _card_events,
                       _published_harnesses)
import pf_pages  # noqa: E402,F401  (its checks register)
import pf_narrative  # noqa: E402,F401  (its checks register)
import pf_repo  # noqa: E402,F401  (its checks register)
import pf_workflows  # noqa: E402,F401  (its checks register)
import pf_bills  # noqa: E402,F401  (its checks register)
import pf_data_unsorted  # noqa: E402,F401  (its checks register)
import pf_hearings  # noqa: E402,F401  (its checks register)
import pf_committees  # noqa: E402,F401  (its checks register)
import pf_session  # noqa: E402,F401  (its checks register)
import pf_learn  # noqa: E402,F401  (its checks register)
import pf_votes  # noqa: E402,F401  (its checks register)
import pf_night  # noqa: E402,F401  (its checks register)
import pf_cloud  # noqa: E402,F401  (its checks register)
import pf_css  # noqa: E402,F401  (its checks register)
import pf_sources  # noqa: E402,F401  (its checks register)
import pf_browser  # noqa: E402,F401  (its checks register)
import pf_towns  # noqa: E402,F401  (its checks register)
import pf_build_unsorted  # noqa: E402,F401  (its checks register)
import pf_people  # noqa: E402,F401  (its checks register)
import pf_elections  # noqa: E402,F401  (its checks register)
import pf_calendar  # noqa: E402,F401  (its checks register)
import pf_laws  # noqa: E402,F401  (its checks register)
import pf_entities  # noqa: E402,F401  (its checks register)
import pf_bench  # noqa: E402,F401  (its checks register)


if __name__ == "__main__":
    main()
