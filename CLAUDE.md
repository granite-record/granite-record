# Granite Record

A public record of the New Hampshire General Court, live at graniterecord.org.
33,683 bills across 19 terms, 1989 to 2026; 406 sitting legislators and 2,192
people who have served; hearings on record for seven terms; and for the
recorded ones, the moment in the recording where a chair took the bill up.

`LAUNCH.md` is the list of what is done, what is not, and what to do first.
Every hand-written document here drifts, this one included; `STATE.md` is
generated and does not, so where a count disagrees, `STATE.md` wins.

Static site: files on a CDN, no runtime. That constraint is deliberate.

---

## Do this first, every session

```
python3 inventory.py       # every file and its version
python3 preflight.py       # the checks; builds the whole site on a fixture
python3 handoff.py         # writes STATE.md with current counts
```

Under a minute, no network. **Trust their output over anything written in
prose, including this file.** If `preflight` is not green, fix that before
anything else.

`STATE.md` is generated. Never edit it. `HANDOFF.md`, `ARCHITECTURE.md`,
`LAUNCH.md`, `DESIGN.md` and `obsolete/README.md` are written by a person and
explain why things are the way they are. (`TESTING_QUEUE.md` was named here
for a while and has never existed; `LAUNCH.md` is what took its place.)

---

## Never run these without asking

**Any `fetch_*.py` script.** They hit the New Hampshire General Court's
servers. This address has been blocked twice by their firewall: once for
probing filenames that did not exist, once for running two fetches at the same
time. Getting blocked again costs days and an email to a Clerk's office.

If a fetch is genuinely needed, say so and let the person start it. Never run
two at once. `python3 netcheck.py` diagnoses a refusal without making things
worse.

**A refusal outlives the run that met it.** `refusal.py` records one in
`archive/refused.json` and every fetch stops for 24 hours — the calendar
drain, the docket, the archived text and its discovery pass. It exists because
on 9 September the calendar drain was answered with two 403s, stopped itself
correctly, and a chained run started asking the same address for a docket
fifty-four seconds later. Clearing it is a person's decision:
`python3 refusal.py --clear`, after `netcheck.py` has said what kind of
refusal it was.

The `fetch_*_db.py` scripts -- eight of them, plus `docket_from_db.py` --
are the exception worth knowing about: they read the SQL host the General Court publishes credentials
for at gc.nh.gov/downloads, not the web server that did the blocking. Still
ask -- they are somebody else's server -- but a refusal there is a different
problem with a different cause. `probe_db.py` reports what is in it;
`probe_db.run_to_file` streams an answer too big for the JSON bridge, which is
anything past a few thousand rows.

**`publish`.** It deploys to the live site.

Everything else — builds, checks, parsers, the site build — is fine to run
freely.

---

## The rules that produced the good results

**Read the artefact before modelling it.** Every good result here came from
opening real data first. The timestamp method that scores one second was built
by reading actual transcripts and collecting the phrases chairs really use. Its
predecessor was built from an assumption about how meetings run and was twelve
times worse. When tempted to write a parser from a description, open the file.

**Measure against something you did not generate.** `ground_truth.csv` holds 35
proceedings a person timed by watching the video, and `review/checked.jsonl`
holds whatever the bench has added since — `python3 review.py` serves one
sample at a time and appends a judgment. Any timestamp method is scored with:

```
python3 probe_alignment.py --truth --candidate candidate_segments.json
```

The candidate median was **0m 01s** on 5 September, against 1m 27s for the
clustering model and 17m 05s for the schedule alone. **Nothing about
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

**Say when something is a guess.** The person has caught several wrong answers
and prefers being told. An invented number stated plainly ("whisper takes about
six hours" — it took forty minutes) costs more than an admission of not
knowing.

---

## How the code is arranged

**`proceedings.csv` is the one table.** Built by `build_proceedings.py` from
the committee manifest and the floor index, read through `proceedings.py` by
everything. It exists because those two sources used to be read separately and
five tools in one day were found to silently exclude floor debates — each
presenting as a different bug. **Do not add a sixth reader of the old files.**

**Four files are a person's and no generator writes them.**
`ground_truth.csv` (35 proceedings timed with a stopwatch),
`review/checked.jsonl` (the bench's judgments, append-only), `bill_notes.json`
(what a recurring bill number means — HB1 has been the budget since 1993) and
`officials.json` (offices filled by hand from four official sources).
`preflight` fails if any `build_*` or `fetch_*` script opens one for writing,
and it is named for the category rather than for `ground_truth.csv` because
three of the four had no guard at all until 10 September.

**`build_all.py` is the pipeline.** 21 steps for `--local`, 34 declared; `--local` skips network ones,
`--dry-run` shows the plan. A step marked `superseded=True` is kept for a case
a newer step does not cover and does not run unasked.

**`preflight.py` is the test suite.** It builds the whole site on a fixture,
loads `bills.html` in node and calls `render()` and `renderDetail()`, and runs
`tests/test_markers.py`. Add a check whenever something breaks in a way a check
could have caught — that is how most of the current ones got there.

**Timestamps, in order of what they can claim.** A roll call's clock time from
`RollCallSummary.txt` (no captions involved, hand-checked at 3–7 seconds); a
boundary the chair stated, found by `segment_markers.py`; the clustering model
where neither fires. The page says which: *"the chair opens it at 1:08:43"*
against *"estimated within ±5 min"*.

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
`preflight.py` at `2026-09-04.12` has been edited many times since 4 September.
Increment the `.N`; leave the date alone.

---

## What to work on next

In order. `ARCHITECTURE.md` has the full reasoning, and `LAUNCH.md` is the
newer answer where they disagree.

1. **Split `build_site_v2.main`, which is now the longest function in the
   file at 468 lines.** Its two predecessors are done and both were verified
   the same way. `renderDetail` went from 472 lines and 26 `const`
   declarations to nine hoisted functions on 6 September, byte-identical.
   `build_bills` went from **544 lines to 294** on 10 September, in nine
   steps, each one checked by building the site into a scratchpad tree and
   comparing a sha256 manifest of all 34,114 files against a baseline — which
   was itself run twice under different `PYTHONHASHSEED` values first, to
   prove the output was deterministic rather than assume it.

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
   patterns were validated against sentences typed out of a document for a
   whole day before anyone ran them on a floor caption file.

   Note what will NOT move this: more captions. 910 of the 915 recordings
   that carry a scheduled bill already have them.

3. **`proceedings.csv` across the remaining terms.** It held one term until 10
   September and holds seven now — 29,837 rows, 1,823 recordings — because
   `build_manifest.py` turned out to need no change at all: `--docket` names
   the term, and `build_proceedings.py` reads every
   `verification_manifest*.csv` rather than one. What is left is the terms
   whose dockets have not been fetched, and the pre-2015 years, for which no
   docket is fetched at all and the calendars are the only source: all 1,580
   House calendar PDFs for 1997-2026 are on disk with text, yielding 61,767
   bill-days that need no network.

4. **A new archive path, found on 10 September and not yet used.**
   `gc.nh.gov/legislation/<year>/<HB0000>.html` is constructible from a year
   and a padded number — no search, no session — and carries the sponsor with
   their district, the committee of referral, the title, the analysis and the
   full text. Every one of eight years sampled from 1989 to 2017 returned a
   page. Five terms currently have no sponsor and no committee at all.
   `fetch_legislation.py` fetches and saves; `--parse` reads what is saved and
   touches no network, because the labels change with the decades and a parser
   must be allowed to be wrong without costing a request.

5. **The bench.** `review.py` serves one sample at a time on the loopback
   address, takes a verdict and a note, and appends to `review/checked.jsonl`.
   Five kinds: hearing timings, narratives, hearings read from calendars, veto
   messages, committee reasoning. `probe_alignment.py --truth` reads it
   alongside `ground_truth.csv` — 43 marks across 15 recordings against 35
   across 7 — and `--no-bench` gives the number comparable with anything
   recorded before 9 September.

**Settled, and no longer worth revisiting.** The file cap: records travel
inside their own pages, so a bill is one file and the site is **49,304 of the
100,000** Cloudflare Pages Pro allows. Term keying: every per-bill file is
`{term: {bill: ...}}` and `preflight` refuses the old shape.

---

## Environment

Windows. The person uses `cmd`; the assistant has PowerShell and a Git Bash
shell, and a heredoc in either eats backslash escapes -- write patch scripts
with the editor tool and copy them in. Python 3.14 as `python3`. Node is
installed and `preflight` uses it. The working folder is the repository root;
`work/` holds about 26 GB of caption files across ~2,500 recordings, and
`site/` is the built output.

`publish` is a local command that builds, checks and deploys with wrangler.
