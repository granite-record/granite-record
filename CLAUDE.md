# Granite Record

A public record of the New Hampshire General Court, live at graniterecord.org.
33,683 bills across 19 terms, 1989 to 2026; 406 sitting legislators and the
2,192 people in `careers.json`, which is everyone with a recorded roll-call
vote since 1999 rather than everyone who has served -- roll calls start in
1999 and the bills start in 1989; hearings on record for all nineteen terms,
each with its own `verification_manifest*.csv`; and for the recorded ones, the
moment in the recording where a chair took the bill up.

`LAUNCH.md` is the list of what is done, what is not, and what to do first.
Every hand-written document here drifts, this one included; `STATE.md` is
generated and does not, so where a count disagrees, `STATE.md` wins.

Static site: files on a CDN. That constraint is deliberate. There is exactly
one exception: `functions/api/report.js`, the POST endpoint behind the "report
a problem" box. It is write-only, on no page's critical path, and the box falls
back to an email link when it is down, which is why it is acceptable on a site
that is static on purpose.

---

## Do this first, every session

```
python3 inventory.py       # every file and its version
python3 preflight.py       # the checks; builds the whole site on a fixture
python3 handoff.py         # writes STATE.md with current counts
```

A couple of minutes, no network -- `preflight` is nearly all of it, and its
`--code` half alone is about a minute of that. **Trust their output
over anything written in prose, including this file.** If `preflight` is not
green, fix that before anything else.

`STATE.md` is generated. Never edit it. `CLAUDE.md` (this file), `LAUNCH.md`,
`DESIGN.md` and `obsolete/README.md` are written by a person and explain why
things are the way they are. `HANDOFF.md` and `ARCHITECTURE.md` are the
assistant's to keep current, and `README.md` is the front door for the
open-source release.

---

## Never run these without asking

**Any `fetch_*.py` script.** They hit the New Hampshire General Court's
servers. This address has been blocked twice by their firewall: once for
probing filenames that did not exist, once for running two fetches at the same
time. Getting blocked again costs days and an email to a Clerk's office.

If a fetch is genuinely needed, say so and let the person start it. Never run
two at once. `python3 netcheck.py` diagnoses a refusal without making things
worse.

**Before assuming nothing is running.** `watchers/gc_lane.py` is the scheduled
lane, it works the queue in `watchers/gc_lane.queue`, and it holds
`archive/.lock` with its pid and touches it every minute while it does. A fresh
`archive/.lock` means a General Court fetch is in flight right now;
`logs/gc_lane.log` says which step and `logs/gc_*.log` how far it has got.
`watchers/README.md` explains the lane and carries the one-liner that lists
every fetch process on the machine. Look there before starting anything — a
session that trusted a stale table in a document is how the second block
happened.

**A refusal outlives the run that met it.** `refusal.py` records one in
`archive/refused.json` and holds the fetch lane for 24 hours. It exists because
a drain that met two 403s stopped itself correctly, and a chained run started
asking the same address for a docket twelve seconds later. Clearing it is a
person's decision: `python3 refusal.py --clear`, after `netcheck.py` has said
what kind of refusal it was.

It holds every fetch that asks the General Court. All 18 scripts carrying a
literal `gc.nh.gov` URL call `refusal.check()` straight after parsing their
arguments, and `preflight` fails if one stops. Ten of them did not until
18 September — the nine this paragraph used to list, plus
`fetch_archive_bills`, which asks `bill_status/legacy/bs2016/`, the one path
their IT office asked this project to go lightly on. Started by hand, any of
the ten walked straight through a standing refusal.

`fetch_town_clerks` is deliberately outside that set: it asks app.sos.nh.gov,
the Secretary of State, and names gc.nh.gov only to say so. The check tests for
a URL rather than for the words, so that distinction survives.

The eight `fetch_*_db.py` scripts are the exception worth knowing about: they
read the SQL host the General Court publishes credentials
for at gc.nh.gov/downloads, not the web server that did the blocking. Still
ask -- they are somebody else's server -- but a refusal there is a different
problem with a different cause. `probe_db.py` reports what is in it;
`probe_db.run_to_file` streams an answer too big for the JSON bridge, which is
anything past a few thousand rows.

The three `*_from_db.py` scripts -- `docket_from_db.py`, `rollcalls_from_db.py`
and `testimony_from_db.py` -- ask nobody anything, despite the name. The
database is already dumped to `db/` on this disk and they reshape it into the
files the parsers read: standard library only, no network, free to run without
asking.

**`publish`.** It deploys to the live site.

Everything else — builds, checks, parsers, the site build — is fine to run
freely.

---

## The rules that produced the good results

**Read the artefact before modelling it.** Every good result here came from
opening real data first. The timestamp method that scores one second was built
by reading actual transcripts and collecting the phrases chairs really use. Its
predecessor was built from an assumption about how meetings run and scores 1m
27s against the same hand-marked times. When tempted to write a parser from a
description, open the file.

**Measure against something you did not generate.** `ground_truth.csv` holds 35
proceedings a person timed by watching the video, and `review/checked.jsonl`
holds whatever the bench has added since — `python3 review.py` serves one
sample at a time and appends a judgment. Any timestamp method is scored with:

```
python3 probe_alignment.py --truth --candidate candidate_segments.json
```

The candidate median is **0m 01s**, against 1m 27s for the clustering model and
17m 05s for the schedule alone. **Nothing about
timestamps goes on the site before that comparison has been run and the median
has not regressed.** This matters more in an agentic loop, not less: it is the
guard against tuning a pattern until the number looks right.

**Silence is not success.** A build that finishes having published nothing; a
fetch killed at fifteen minutes that looks like a hang; a step that prints one
line in twenty minutes. Five separate instances in a week. If a step can
produce nothing and still exit zero, it needs a guard that says so.

**A writer of a derived file, run on a subset, destroys the rest.** The
manifest lost the 35 hand-marked times twice. `segment_markers --transcript X`
once discarded 842 recordings' results. Writers merge; a full rebuild is an
explicit flag; anything a person made by hand lives where no generator writes.

**Say when something is a guess.** An invented number stated plainly ("whisper
takes about six hours" — it took forty minutes) costs more than an admission of
not knowing.

---

## How the code is arranged

**`proceedings.csv` is the one table.** Built by `build_proceedings.py` from
every `verification_manifest*.csv` — one per term — plus the floor index, and
read through `proceedings.py` by everything. It globs them all on every run so
that no writer here ever sees a subset (`build_proceedings.py:311-316`). It
exists because those sources used to be read separately and five tools in one
day were found to silently exclude floor debates — each presenting as a
different bug. **Do not add a sixth reader
of the old files, and do not give it a `--term` flag.**

**Five files are a person's and no generator writes them.**
`ground_truth.csv` (35 proceedings timed with a stopwatch),
`review/checked.jsonl` (the bench's judgments, append-only), `bill_notes.json`
(what a recurring bill number means — HB1 has been the budget since 1993),
`officials.json` (offices filled by hand from four official sources) and
`member_corrections.json` (a name or party a generator got wrong, with the
evidence for the correction beside it).
`preflight` fails if any `build_*` or `fetch_*` script opens one for writing,
and the check is named for the category rather than for one file, because while
it named only `ground_truth.csv` three of the others had no guard at all. The
list lives in `preflight.py`'s `HANDMADE`; read it there rather than here,
because it has grown twice.

**`build_all.py` is the pipeline.** 26 steps for `--local`, 39 declared; `--local` skips network ones,
`--dry-run` shows the plan. A step marked `superseded=True` is kept for a case
a newer step does not cover and does not run unasked.

**`preflight.py` is the test suite.** 161 checks — 122 of them under `--code`,
which needs no data on disk — and no network. It builds the whole site on a
fixture, loads `app.js` (the script `bills.html` pulls in) in node against
`dom_stub.js` and calls `render()` and `renderDetail()`, and runs
`tests/test_markers.py`. Add a check whenever something breaks in a way a check
could have caught — that is how most of the current ones got there.

**Timestamps, in order of what they can claim.** A roll call's clock time from
`RollCallSummary.txt` (no captions involved, hand-checked at 3–7 seconds, and
House only — all 3,988 Senate rows across the current file and the 27 archived
years in `rollcalls/` are stamped midnight, so this method places no Senate
floor debate at all, while 5,363 of the 5,577 House rows carry a clock); a
boundary the chair stated, found by `segment_markers.py`; the clustering model
where neither fires. The page says which by what it does *not* qualify: a
stated boundary is shown plainly, and an inferred one carries one word,
*approximate*.

**Captions are not quoted on the site.** They render "HB 1381" as "HP 1381" and
"HB 1444" as "HB1 1444". A garbled quote presented as what someone said is a
transcription error wearing the clothes of a citation. The timestamp is the
claim; the recording is the evidence.

---

## Version stamps

Every script carries `# GRANITE_VERSION: YYYY-MM-DD.N`, and `versions.json`
lists what each should be. `preflight` fails when they disagree — this has
caught three silently half-applied edits.

**When you change a file, bump its stamp and update `versions.json` in the same
edit.** The date is when the file was *created*, not last modified:
`preflight.py` at `2026-09-04.190` has been edited a hundred and ninety times
since 4 September. Increment the `.N`; leave the date alone. `python3
inventory.py` prints the current stamp of every file; take one from there and
do not copy one into prose. A stamp quoted in a document goes stale, and then
points at whichever other file has since grown into that number.

---

## What to work on next

In order **within their category, and the category comes first.** The site's
readers include General Court staff and legislators, so: a factual error — a
wrong roster, a wrong count, a mislabelled vote, a sponsor on the wrong person
— is fixed before anything else; then bugs that hide or break data; then
everything below, all of which is in that third group. `LAUNCH.md` holds the
current order and is the newer answer where it and this disagree;
`ARCHITECTURE.md` has the full reasoning.

1. **Split `build_site_v2.main`, which is still the longest function in the
   file and is now 533 lines** — it was 468 when this was written, so it grows
   while it waits. Its two predecessors are done and both were verified
   the same way: `renderDetail`, 472 lines and 26 `const` declarations to nine
   hoisted functions, byte-identical output; `build_bills`, **544 lines to
   294** in nine steps (it has since drifted back to 346, which is what a
   function does when it is the right size to add to). Each step was checked by
   building the site into a scratchpad tree and comparing a sha256 manifest of
   all 34,114 files against a baseline — which was itself run twice under
   different `PYTHONHASHSEED` values first, to prove the output was
   deterministic rather than assume it.

   That split paid for itself beyond the line count: `kind` meant the bill's
   status kind in the payload and a `("voice vote", False)` tuple 147 lines
   later, and `n` was a bill count and a nay count. Both stopped existing
   when the blocks became functions.

   `main` is not the same disease -- the station code that caused the
   floor-marker miss already came out as `station_for_proceeding` and
   `station_for_floor`. What is left in `main` is the loading: two dozen
   files read and shape-checked in one scope, with the per-term `procs` and
   `floor` maps built beside the roster and the roll calls. The seams are the
   `load(...)` calls, and the verification is the same manifest diff.

2. **More marker patterns.** `segment_markers.py --all --gaps` prints what the
   chair says where no boundary was found; `--phrases` counts those across
   every recording so a shared convention appears as a number rather than a
   hunch. That loop took coverage from 40% to 71% in one evening. Add a phrase
   to `tests/test_markers.py` **only if it was actually spoken** — the floor
   patterns once spent a day being validated against sentences typed out of a
   document rather than against a floor caption file.

   Note what will NOT move this: more captions. 4,296 of the 4,429 recording
   folders in `work/` carry captions this can read, and the recordings
   `proceedings.csv` names are nearly all of them. Fetching more captions will
   not move the coverage.

3. **~~`proceedings.csv` across the remaining terms.~~ Done: all nineteen terms
   have a manifest**, because `build_manifest.py` turned out to need no change
   at all — `--docket` names the term, and `build_proceedings.py` reads every
   `verification_manifest*.csv` rather than one. The last terms cost no network
   because the database dump had already put `Docket_db_1999-2000.txt` through
   `Docket_db_2013-2014.txt` on this disk; fifteen `Docket_db_*.txt` are there
   now. Run `python3 handoff.py` for the row and recording counts — this line
   has carried a stale pair twice.

   The calendars stay the independent check, and the only source for a hearing
   the docket never recorded: all 1,580 House calendar PDFs for 1997-2026 are
   on disk with text, and `calendar_meetings.py --check` reads the bill-days
   out of them at no cost. Run it rather than quoting a count from here; merging
   committee-name variants moved the number by 224 in a week. The Senate
   calendars are 1,604 PDFs with text for 984.

4. **A constructible archive path.**
   `gc.nh.gov/legislation/<year>/<HB0000>.html` is built from a year and a
   padded number — no search, no session — and carries the sponsor with their
   district, the committee of referral, the title, the analysis and the full
   text. The parser reads sponsor, committee and title across all 15 kinds and
   31 years; the pages naming no sponsor are housekeeping resolutions and
   budget tables, which name none.

   11,937 pages across 38 year folders are saved under `legislation/` and the
   lane is still walking backwards through them. Only 1996 and 2016 answer 404
   for every bill asked, and that stays unexplained; the current term lives at
   bill_status. No term lacks a committee — the docket fills committee of
   referral for all nineteen. What this path is still buying is the sponsor,
   for the terms that carry one on fewer than twenty bills;
   `/data/manifest.json`'s per-term coverage table says which, and it moves
   with every build. `fetch_legislation.py` fetches and saves; `--parse` reads
   what is saved and touches no network, because the labels change with the
   decades and a parser must be allowed to be wrong without costing a request.

5. **The bench.** `review.py` serves one sample at a time on the loopback
   address, takes a verdict and a note, and appends to `review/checked.jsonl`.
   Nine kinds of sample: topics, bill hearing timings, hour-late recordings,
   timings before 2025, histories of 1989-2016, plain-language histories,
   hearings read from calendars, governors' veto messages and committee report
   reasoning. `probe_alignment.py --truth` reads the timed ones alongside
   `ground_truth.csv`'s 35, and `--no-bench` gives the number comparable with
   anything recorded before the bench existed. **Take the counts from the
   command's own header**, not from a document — the pair this line used to
   carry was not reproducible from any state of `checked.jsonl`.

**Settled, and no longer worth revisiting.** The file cap: records travel
inside their own pages, so a bill is one file. Term keying: every per-bill file
is `{term: {bill: ...}}` and `preflight` refuses the old shape.

The *margin* is comfortable and still worth watching before anything adds a
file per record. The deploy is **49,361 files, 1.8 GB — 49% of the 100,000**
Cloudflare Pages Pro allows, and `check_site` warns at 90,000. **Run `python3
check_site.py` rather than quoting that pair**, which is the rule the rest of
this file states and which this paragraph itself broke: it read "45,862 files
to 82,574 — 2.3 GB" for one day, a figure no command produces and whose own
arithmetic refuted it, since the 1,785 former-member pages it credited could
not add 36,712 files.

---

## Environment

Windows. The person uses `cmd`; the assistant has PowerShell and a Git Bash
shell, and a heredoc in either eats backslash escapes -- write patch scripts
with the editor tool and copy them in. Python 3.14 as `python3`. Node is
installed and `preflight` uses it. The working folder is the repository root;
`work/` holds about 34 GB of caption files across 4,429 recording folders,
4,296 of them with captions this can read, and `site/` is the built output.

`publish` is a local command that builds, checks and deploys with wrangler.
