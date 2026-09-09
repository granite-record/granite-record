# Granite Record

A public record of the New Hampshire General Court, live at graniterecord.org.
33,683 bills across 19 terms, 1989 to 2026; 406 sitting legislators and 2,192
people who have served; and every committee hearing and floor debate of the
current terms linked to the moment in the recording where it happened.

`LAUNCH.md` is the current list of what is done, what is not, and what to do
first. It was written by measuring the site rather than by reading these
documents, and where it disagrees with them it is the newer answer.

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

`STATE.md` is generated. Never edit it. `HANDOFF.md`, `ARCHITECTURE.md` and
`TESTING_QUEUE.md` are written by a person and explain why things are the way
they are.

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

`fetch_rollcalls_db.py` and `fetch_reports_db.py` are the exception worth
knowing about: they read the SQL host the General Court publishes credentials
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
proceedings a person timed by watching the video. Any timestamp method is
scored with:

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

**`ground_truth.csv` is the record.** Edited by hand only. `preflight` fails if
any `build_*` or `fetch_*` script opens it for writing.

**`build_all.py` is the pipeline.** 14 steps; `--local` skips network ones,
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

In order. `ARCHITECTURE.md` has the full reasoning.

1. **Split `build_site_v2.main`.** `renderDetail` was the other half of this
   and was split on 6 September: 472 lines and 26 `const` declarations became
   nine hoisted functions, one per tab, with the output verified
   byte-identical against the pre-split page. `build_site_v2.main`
   has the same problem: the floor-marker miss happened because the committee
   and floor station code sit 90 lines apart in one function.

2. **More marker patterns.** `segment_markers.py --all --gaps` prints what the
   chair says where no boundary was found; `--phrases` counts those across
   every recording so a shared convention appears as a number rather than a
   hunch. That loop took coverage from 40% to 71% in one evening. Add a phrase
   to `tests/test_markers.py` **only if it was actually spoken** — the floor
   patterns were validated against sentences typed out of a document for a
   whole day before anyone ran them on a floor caption file.

3. **The file cap: decided and no longer close.** Cloudflare Pages allows
   100,000 on the Pro plan. Every bill's record now travels inside its own
   page rather than beside it, so a bill is one file: **39,914 files, 40% of
   the cap**, against 73% before. The 98 records over 100 KB — almost all roll
   call ballots, HB2 alone being 2 MB — keep a file, and their page carries a
   `<meta name="gr-data">` pointing at it. `build_bill_pages.py` explains the
   threshold and the measurements behind it.

4. **Term keying: done.** Every per-bill file is `{term: {bill: ...}}` and
   `preflight` fails if any is fed the old shape, `bill_text.json` and
   `bill_status.json` included. All 19 terms are live.

5. **The bench.** `review.py` serves one sample at a time on the loopback
   address, takes a verdict and a note, and appends to
   `review/checked.jsonl` — which is hand-made evidence and is protected the
   way `ground_truth.csv` is. Five kinds today: hearing timings, narratives,
   hearings read from calendars, veto messages, committee reasoning. It exists
   because 35 hand-timed proceedings is a thin measuring stick, and related
   bills and auto-assigned topics will both need the same bench before they
   can honestly be published.

---

## Environment

Windows, `cmd`. Python 3.14 as `python3`. Node is installed and `preflight`
uses it. The working folder is the repository root; `work/` holds ~10.5 GB of
caption files and `site/` is the built output.

`publish` is a local command that builds, checks and deploys with wrangler.
