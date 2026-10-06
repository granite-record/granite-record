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

`narrative_watch.py`, below, reads `logs/docket_chain.log` for the line this
wrote when a term's docket was complete. It followed this here on 6 October
2026.

**It starts fetches.** Do not run it.

---

The rest moved here on 6 October 2026, the refactor plan's second phase, with
the person's agreement: one-offs whose job is done and watchers that had stood
dormant since the drains they followed finished. Nothing ran any of them --
not `build_all.py`, the nightly, the weekly, the laptop's evening job, the
lane's queue or a scheduled task -- and no check imported one. Each one that
imports a project module (`proceedings`, `docket_parser`, `build_manifest`)
expects to be run from the repository root, as it was.

## `fetch_archive_years.py`

The loop that brought every archived term's bills down from the Advanced Bill
Status Search, two requests a session year, by running
`fetch_archive_bills.py --year` once a year with a wait between and a stop
after two failures in a row. It did its job: `archive_years.json`, the record
it wrote, has every term from 1989-1990 to 2023-2024 and no failure.
`fetch_archive_bills.py` is still at the root and still the fetcher; this was
only the loop around it.

**It asks the General Court, and it never called `refusal.check()` itself**:
it carries no `gc.nh.gov` address of its own, so the refusal check that reads
every script never asked it to. The script it ran does call it. Do not run
this; a year is one `fetch_archive_bills.py --year` in the lane.

## `fix_meridiem_manifests.py`

A one-off repair of the manifests built before `docket_parser._unslip` learned
to correct a meridiem the clerk typed the wrong way round ("12:15 am" for a
hearing at quarter past noon). It recomputed `sched_time`, `predicted_offset`
and `watch_url` in the rows inside the window and left every other column --
`observed_start` and `observed_end` above all -- as it found them. Run without
`--apply` on 6 October it found 0 reversed meridiems across the 19 manifests,
and every manifest built since is right without it.

Kept for its account of what a repair of a derived file may and may not
touch, which is the rule the hand-marked times were lost twice for want of.

## `index_to_csv.py`

Turned `channel_index_full.json`, the channel walk that found the
recordings before 2025, into the video CSV shape `build_manifest.py` reads,
with the stream start left empty. On 9 September it proved the point on
2023-2024 with no network: 1,643 of 1,648 recordings converted and 81% of that
term's proceedings matched a single recording, because a recording is matched
to a hearing by the date and the committee in its title, not by its start.
The `videos_*_2019-...` and `videos_*_2023-...` lists the build reads were
then written by `fetch_channel_index.py`, which records the stream start as
well, so nothing has read this one's output since.

## `setup_archive.py`

A sketch of an `archive/<term>/raw|pages|parsed` layout, written on 4
September so that bill numbers repeating between terms could not overwrite one
another. It was never switched on -- `archive/sessions.json`, which it writes,
does not exist -- because the same problem was solved inside the files
instead: every per-bill file is `{term: {bill: ...}}`, and `preflight` refuses
the old shape. Kept for its statement of that problem, which is still the
reason for the keying.

## `caption_gaps.py`

Which recordings `proceedings.csv` names and has no captions for, split into
the two cases one count hides: a recording never fetched, and one fetched that
produced nothing. Measured on 6 September at 119 proceedings on 54
recordings, 112 of them committees of conference. No network and no writes,
and nothing ran it after that day; `probe_alignment.py --missing` writes the
recordings with no captions, busiest first, for a fetcher to read, and
`STATE.md` counts the caption folders. `proceedings.py`'s docstring still
names it among the readers that open `proceedings.csv` by name.

## `captions_watch.py`

Lived in `watchers/`. A politeness loop for YouTube, not the General Court:
when YouTube answered 429 to this address on the first request at a
twenty-second pace, it probed a few recordings at a time through
`fetch_archive_captions.py`, backed off when refused and drained when not.
Captions now arrive through `livestreams.py`, which the laptop's evening job
runs (`--catch-up`) and the nightly reads (`--markers`), and nothing starts
this any more. Kept for its shape: a loop that
lengthens its wait on every refusal costs the far end less in a night than
one impatient minute.

## `extract_watch.py`

Lived in `watchers/`. It walked behind the calendar drain and wrote the text
beside each new calendar and journal PDF, through `extract_calendar_text.py`,
because the hearings parser reads the `.txt` and 696 House calendars had sat
unread without one. The drain is finished; `extract_calendar_text.py` is still
at the root, does nothing when nothing is missing, and is run by hand after a
fetch of PDFs (`archive_status.py` says when).

## `narrative_watch.py`

Lived in `watchers/`, and was stood down on purpose before it moved. It
narrated each archived docket as its fetch finished, and once built 2015-2016
from a half-complete database seed, putting ten wrong passage rails on the
live site -- HB148 among them, with a vote rail beside the word "vetoed".
Its two guards (skip `Docket_db_*.txt`; wait for `docket_chain.py` to log the
term done) came from that. The archived terms are narrated by the build now:
`narrative.py` and `narrate_archive.py` are steps of `build_all.py`, and both
merge rather than replace.

Kept for the rule it enforced, and checked rather than assumed: a writer of a
derived file run on a subset destroys the rest, so it compared the terms in
`narratives.json` before and after each run and stopped if one went missing.

## `score_alignment.py`

The first scorer: `work/*/segments.json`, the clustering model's own output,
against the `observed_start` a person typed into the manifest, with the
question it was written for -- not "is the aligner accurate" but "does it
know when it is", the share of published estimates inside the tolerance they
claimed. `probe_alignment.py`, written the next day, scored the clustering
model at 1m 27s on 5 September, and its `--truth --site` asks the same
question of what the site actually publishes -- how many of the published
tolerances the true error falls inside -- split by whether the chair stated
the boundary. It also reads `review/checked.jsonl`, the bench, where
this read only the manifest's 35 marks; and it cannot read
`ground_truth.csv`, the truth file since, which calls the proceeding `kind`
where this wants `proceeding`. Nothing named it but `transcribe_and_align.py`'s
docstring, which now names `probe_alignment.py --truth`.
