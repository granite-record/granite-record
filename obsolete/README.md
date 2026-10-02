# Superseded, and kept on purpose

Nothing here runs, nothing here is imported, and nothing in `build_all.py`
names any of it. It is kept because each of these answered a question, and the
answer is now built into something else — so the thing worth preserving is the
reasoning, not the code.

This follows the convention `build_all.py` already uses for a superseded step:
kept for a case a newer step does not cover, and never run unasked.

They carry no `GRANITE_VERSION` stamp and are not listed in `versions.json`.
`inventory.py` and `preflight.py` therefore ignore them, which is the point:
a stamp on a file nobody runs is a stamp somebody has to keep true.

---

## `floor_anchors.py`

An experiment, and it succeeded. It asked whether a House roll call's
wall-clock time in `RollCallSummary.txt`, minus the moment the livestream
started, lands on the right point in the recording — no transcription, no
guessing from the calendar.

It does, to within three to seven seconds, and that is now the most
authoritative timestamp this project has. `CLAUDE.md` lists it first, above
anything read from a caption. The experiment is over because its finding is
production.

**It is House-only, and the experiment could not have shown that.** Across the
current `RollCallSummary.txt` and the 27 archived years in `rollcalls/`, 5,363
of the 5,577 House rows carry a clock and all 3,988 Senate rows are stamped
`12:00:00 AM`. So this method places no Senate floor debate at all, and the
answer to "why is there no timestamp on this Senate debate" is here rather than
in the caption code.

## `floor_debates.py`

An early attempt at finding where debate on a bill starts and ends in a floor
session, built on the Speaker's uniform language. `segment_markers.py`
replaced it and does both chambers and committee hearings as well, scored
against `ground_truth.csv` rather than against a reading of how sessions are
supposed to run.

Kept because its description of the shape of a floor session — motion, against,
for, alternating, then the vote — is an accurate account of the room, and is
where the floor patterns in `tests/test_markers.py` came from.

## `senate_check.py`

A one-off diagnostic: the manifest's overall counts are dominated by 5,550
House rows, so a Senate-only failure would be invisible in them. It printed
the Senate rows on their own.

Superseded by `preflight.py`, which checks both chambers as a matter of course
and fails rather than printing. Kept as the record of a real failure mode:
a number that looks healthy because the broken part is a small share of it.

## `design_home.py`

Three arrangements of the home page, drawn from the built one, so that a
full-width hero could be looked at before anything was changed. It was a
design aid for one decision, and the decision went the other way: the home
page keeps its three columns with the hero in the middle one. Nothing in the
build ran it, and the `site/design/` folder it wrote is in no built site.

Kept because it shows how to try a layout without copying the page: it reads
`site/index.html` as built, finds its blocks and reorders them, so a variant
can never drift from the real page's content.

Moved here on 1 October 2026 (the refactor plan's first pruning pass).

## `fetch_archive_text.py`

The first route to the text of an archived bill: two requests a bill, one to
the bill's status page to read its text id and one to `billText.aspx` with it.
`fetch_legislation.py` replaced it on 10 September 2026 -- the static
`legislation/<year>/<HB0000>.html` address is built from a year and a padded
number, needs no id, and is one request -- and `archive_text.py` reads what
that saves. Nothing has run this since except `docket_chain.py`, below.

Kept for its opening, which records what was checked before any of it was
written: that no file or database view on this disk holds a text id for an
archived bill, and that the id cannot be derived, because its scheme changed
at least once. That is still the reason the address is read and never
guessed. Its queue was `archive/text_queue.csv`, not the calendars'
`archive/queue.csv`.

**It asks the General Court.** It is here to be read. Do not run it: it has
no place in the lane, and the route it takes is the slow one.

## `docket_chain.py`

Lived in `watchers/`. It waited for the calendar drain to finish and then ran
the archive fetches one after another under `archive/.lock`: the dockets, the
last Senate calendars, and the bill text through `fetch_archive_text.py`.
`watchers/gc_lane.py` replaced it: the lane works a queue that is a file,
holds the lock with a heartbeat, and stops for a refusal recorded by any
fetch, where the chain's order was written into its code.

Its seed for 2015-2016 is also wrong, and that is worth remembering: the
database's "2016" rows are the 2015 history of 190 carried-over bills, so
seeding from them skips those bills' whole 2016 record. The lane's queue uses
`Docket_db_2015.txt` instead.

`watchers/narrative_watch.py` still reads `logs/docket_chain.log` for the
line this wrote when a term's docket was complete. That watcher is dormant
too, and says so in `watchers/README.md`.

**It starts fetches.** Do not run it.
