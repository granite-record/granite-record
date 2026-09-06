# Granite Record

A public record of the New Hampshire General Court, live at graniterecord.org.
2,234 bills, 406 legislators, 131,199 votes, and every committee hearing and
floor debate linked to the moment in the recording where it happened.

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

1. **Split `renderDetail` and `build_site_v2.main`.** `renderDetail` is 472
   lines with 26 `const` declarations and had three dead-zone crashes in one
   day — the failure mode is a blank page for a visitor arriving from a link,
   with the data already loaded. One function per tab. `build_site_v2.main`
   has the same problem: the floor-marker miss happened because the committee
   and floor station code sit 90 lines apart in one function.

2. **More marker patterns.** `segment_markers.py --all --gaps` prints what the
   chair says where no boundary was found; `--phrases` counts those across
   every recording so a shared convention appears as a number rather than a
   hunch. That loop took coverage from 40% to 71% in one evening. Add a phrase
   to `tests/test_markers.py` **only if it was actually spoken** — the floor
   patterns were validated against sentences typed out of a document for a
   whole day before anyone ran them on a floor caption file.

3. **A decision on the file cap**, before term-keying is built. Cloudflare
   Pages allows 20,000 files. A static page and a JSON per bill breaks that at
   the fourth term. Fewer static pages for older terms, or per-bill data in R2
   behind a Worker — the two imply different paths, so deciding first stops
   term-keying being built twice.

4. **Term-keyed identifiers.** Bill numbers repeat every two years and nothing
   outside `proceedings.csv` knows it. `committee_reports.json`,
   `bill_text.json`, `narratives.json` and the per-bill site files are keyed on
   `HB396` alone. Fetch anything from 2024 today and it merges into 2026. This
   gates the archive.

---

## Environment

Windows, `cmd`. Python 3.14 as `python3`. Node is installed and `preflight`
uses it. The working folder is the repository root; `work/` holds ~7.6 GB of
caption files and `site/` is the built output.

`publish` is a local command that builds, checks and deploys with wrangler.
