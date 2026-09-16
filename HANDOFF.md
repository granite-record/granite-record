# Granite Record — handoff

For whoever picks this up next, human or model. Read this once; it changes
slowly. For the current numbers, run `python3 handoff.py` and read `STATE.md`,
which is generated and always right.

---

## How this working relationship runs

**The assistant works the repository directly.** It lists files, greps, runs
the builds and the checks, edits in place and commits. This section used to
say the opposite -- that the repository was on the person's machine, that the
assistant could read nothing it was not given, and that the loop was paste
output, receive whole files, download them, paste again -- and every word of
that is now wrong. It stayed wrong for weeks, which cost real turns: a session
that believes it cannot read a file asks for it instead, and a session told to
ship whole files rewrites a thousand lines to change ten.

What is still true, and is the useful part of what that section was reaching
for:

- **Read the artefact before modelling it.** Open the file, the page, the
  record. Nearly every good result here came from that and nearly every bad
  one from assuming a shape. It is cheaper now than it was when it needed a
  paste, so there is less excuse than ever.
- **Never hand-apply a patch, and never write one through a shell heredoc.**
  A heredoc eats backslash escapes -- `\n`, `\s`, `\b` -- and has silently
  corrupted a file about eight times, twice writing something that only
  `ast.parse` caught. Write the patch script to the scratchpad with the
  editor tool, copy it into the repository, run it, delete it. Every patch
  script asserts its anchor appears exactly once before it replaces anything.
- **Commit before starting a piece of work, and show the diff.** Two files
  shipped half-applied in one day and both recoveries were guesswork because
  there was no commit to fall back to.
- **Windows.** `cmd` for the person, PowerShell and a Git Bash shell for the
  assistant. Backslash paths, and `Get-CimInstance Win32_Process` is how a
  stray background process gets found -- six stacked `review.py` processes
  once held port 8799 and served a stale page while the file on disk was new.

## Start here, before anything else

Every session, before anything else.

```
python3 inventory.py
python3 preflight.py
python3 handoff.py
```

Under a minute, no network. `inventory` lists every file and its version,
`preflight` runs the checks and builds the whole site on a fixture, and
`handoff` writes `STATE.md` with the current counts.

**Trust their output over anything written in prose, including this file.**
Documents go stale; those three read the disk.

If `preflight` is not green, stop and fix that first. It caught three stamp
mismatches, a dead-zone crash and a hung build in one week, and every one of
them would otherwise have reached the site.

## Versions and stamps

Every script carries `# GRANITE_VERSION: YYYY-MM-DD.N` and `versions.json`
lists what each should be. `preflight` fails when they disagree, which has
caught three silent half-applied edits.

The date in a stamp is when that file was **created**, not when it was last
touched: `preflight.py` at `2026-09-04.12` has been edited many times since 4
September. Do not read a stamp as a modification date, and do not conclude
that a file with an earlier date predates one with a later date.

---

## What this is

graniterecord.org: a public record of the New Hampshire General Court. Every
bill since 1989, the sitting roster and everyone who has served, hearings on
record for seven terms, and -- for the recorded ones -- the moment in the
recording where a chair took the bill up. The counts live in `STATE.md`, which
is generated; the ones that used to sit here were fifteen times too small
within a week of being typed.

It is a static site. Files on a CDN, no runtime, nothing to go down. That is a
constraint worth keeping.

---

## The five rules

These were learned expensively. Breaking them is how the bad days happened.

**1. Read the artefact before modelling it.** Every good result here came from
looking at real data first. The timestamp method that scores one second was
built by reading actual transcripts and collecting the phrases chairs really
use. The one it replaced was built from an assumption about how meetings run,
and was twelve times worse. When tempted to write a parser from a description,
open the file instead.

**2. Measure against something you did not generate.** `ground_truth.csv` holds
35 proceedings a person timed by watching the video. `probe_alignment.py
--truth --candidate FILE` scores any method against it. Nothing about
timestamps goes on the site before that comparison exists. The tolerances the
site published for months were never checked against anything; when they
finally were, they happened to be honest, but that was luck.

**3. Silence is not success.** A build that finishes having published nothing;
a fetch killed at fifteen minutes that looks like a hang; a step that prints
one progress line in twenty minutes. Five separate instances in a week. If a
step can produce nothing and still exit zero, it needs a guard that says so.

**4. A writer of a derived file, run on a subset, destroys the rest.** The
manifest lost the hand-marked times twice. `segment_markers --transcript X`
once discarded 842 recordings' results. Writers merge; a full rebuild is an
explicit flag; anything a person made by hand lives where no generator writes.

**5. One fetch at a time, and a refusal outlives its run.** The address
has been blocked twice by the General Court's firewall: once for probing
filenames that did not exist, once for running two fetches at once. Every
fetcher reads a list rather than guessing, and `refusal.py` records a refusal
in `archive/refused.json` so that every fetcher stops for 24 hours -- it exists
because a chained run once started asking the same address for a docket
fifty-four seconds after two 403s ended the run before it. Clearing one is a
person's decision, after `python3 netcheck.py` has said whether the refusal is
the address, the client or the site. YouTube is a different host and a
caption fetch may run beside a General Court one.

---

## How the timestamps work

This is the part that took the longest and matters most. Three sources, in
order of what they can claim.

**A roll call's clock.** `RollCallSummary.txt` records the wall-clock time of
every House roll call. Subtract the livestream's start and you have the moment
a floor debate ended, from a source with no captions in it. Hand-checked at
seven seconds, three seconds, and exact.

**A boundary the chair stated.** `segment_markers.py` reads caption files and
finds the sentence opening or closing each proceeding, then matches the bill it
names against what the docket scheduled that day. Every pattern was read out of
a real transcript; `tests/test_markers.py` holds the cases and `preflight`
runs them. Scores **one second** at the median against the hand-marked times.
The published END is measured separately now, by where it came from: a close
the chair spoke scores three seconds; an end inferred from the next bill's
opening scored half an hour and failed in both directions, and is no longer
published at all.

**The clustering model**, still there, still used where neither of the above
fires. It is not bad -- twelve times better than the schedule -- it is just
outclassed by a quotation.

The site says which: *"the chair opens it at 1:08:43"* against *"estimated
within ±5 min"*. Those are different claims. The chair's words are deliberately
not published, because captions render "HB 1381" as "HP 1381" and a garbled
quote presented as what someone said is a transcription error wearing the
clothes of a citation.

---

## The shape of the code

**One table for proceedings.** `proceedings.csv`, built by
`build_proceedings.py` from the committee manifest and the floor index, read
through `proceedings.py` by everything. This exists because those two sources
used to be read separately, and five tools in one day were found to silently
exclude the floor. Do not add a sixth reader of the old files.

**Four files are a person's.** `ground_truth.csv` (35 proceedings timed
with a stopwatch), `review/checked.jsonl` (the bench's judgments,
append-only), `bill_notes.json` (what a recurring bill number means) and
`officials.json` (offices filled by hand). None can be regenerated. `preflight`
fails if any `build_*` or `fetch_*` script opens one for writing, and the
check is named for the category, because for a while it named only the first
file and the other three had no guard at all.

**`build_all.py` is the pipeline.** 21 steps under `--local`, 34 declared,
`--dry-run` to see the plan. A step marked `superseded=True` is kept for a case
a newer step does not cover and does not run unasked.

**`preflight.py` is the test suite.** It builds the whole site on a fixture,
loads `bills.html` in node and calls `render()` and `renderDetail()`, and runs
the marker cases. Add a check whenever something breaks in a way a check could
have caught.

---

## What to do next

`LAUNCH.md` is the working list, written on 9 September by measuring the site
rather than by reading these documents. What follows is the part of it that
belongs here, because it is about how the code is built rather than what it
shows.

**1. Split `build_site_v2.main`**, now the longest function in the file
at 468 lines. Its two predecessors are done: `renderDetail` on 6 September,
`build_bills` on 10 September -- 544 lines to 294 in nine steps, each verified
by building into a scratchpad tree and diffing a sha256 manifest of all 34,114
files against a baseline that was itself built twice under different
`PYTHONHASHSEED` values first. The station code that caused the floor-marker
miss already came out; what is left in `main` is the loading.

**2. More marker patterns.** `segment_markers.py --all --gaps` prints what the
chair says where no boundary was found; `--phrases` counts those across every
recording so a shared convention appears as a number. That loop took coverage
from 40% to 71% in an evening and is not exhausted. Add a phrase to
`tests/test_markers.py` only if it was actually spoken.

**3. Use the bench.** `python3 review.py` serves one sample at a time and
appends a judgment to `review/checked.jsonl`, and `probe_alignment.py --truth`
reads that file beside `ground_truth.csv` -- 43 marks across 15 recordings
against 35 across 7 -- with `--no-bench` for a number comparable with anything
recorded before 9 September. The bench showed the schedule offset rather than
the published time for its first day; the nine verdicts from then are
quarantined by `review.py --report` and their stopwatch readings are kept. Related bills and auto-assigned
topics both need the same bench before either can honestly be published, so
the samples taken now are what makes those possible later.

**Settled, and recorded here because this list used to say otherwise.** The
file cap is decided: a bill's record travels inside its page, and the site
is under half of the 100,000 files Cloudflare Pages allows on the Pro plan
(`STATE.md` has the count). Term keying is
finished across every per-bill file, and all 19 terms are live.

**4. A label states the seat held when the record was made** -- the person's
rule, 16 September, and half of it is still to do. Sponsor lines and roll call
ballots now take their chamber, county and district from the bill's own printed
line where the record can attest it, rather than from the roster of the House
and Senate sitting today. Two gaps remain, both in `build_data.py`: a member who
has LEFT still carries one seat for all time, and reads as a database row --
`_former_label` builds "Shurtleff, Steve(D) Merrimack 15" where everybody else
reads "Rep. Steve Shurtleff (D - Merr 15)". 676 members read that way, which is
the opposite of showing members who have left exactly like the rest.

**5. The docket parser, when the person says so.** 1,062 modern House docket
lines take the 1989-98 path in `docket_parser.py` and carry a wrong proceeding
kind and a garbled room, 1,029 of them in 2021-2022. It is the largest
remaining bucket of factual error on bill pages. It is not a small fix:
`HOUSE_SCHED_RE` changes, all eleven manifests rebuild, and video matching
re-runs, because `build_sittings` keys on (committee, date, venue) and the
venues are exactly what changes. Deferred by the person on the 16th, to come
back to.

---

## Keeping the documents true

`STATE.md` is generated -- run `python3 handoff.py`. Never edit it.

`HANDOFF.md` (this file), `ARCHITECTURE.md`, `LAUNCH.md`, `DESIGN.md`,
`README.md` and `obsolete/README.md` are written by a person and should stay
short enough to reread. `TESTING_QUEUE.md` was named here and in `CLAUDE.md` for a while and
has never existed in this repository -- which is exactly the kind of thing
this paragraph is about. When one of them says
something the code no longer does, that is a bug in the document; fix it in the
same session, because a document that is wrong once is not trusted again.

Numbers do not belong in the hand-written files. If you find yourself typing a
count, it belongs in `handoff.py` instead.

---

## Publishing

`publish.bat` rebuilds from local files, runs `check_site.py`, deploys with
`npx wrangler pages deploy` to the Cloudflare Pages project, then runs
`check_live.py --gate`, which compares what the domain serves against what was
just built -- because wrangler has reported success for deployments the
production domain never took. The gate has also run too early: a deploy that
"did not land" thirty seconds after upload had landed by the second check.
Until 11 September it did not run at all: `npx` is `npx.cmd`, and without
`CALL` a batch file that runs another never gets control back, so every
publish ended at wrangler's own "Deployment complete!". A publish log that
ends there, with no "Confirming the world is getting what was just built"
after it, is that fault back.

Deploying is a person's decision. When the person is away from the keyboard
they have sometimes said so and permitted it; that is per-absence, not
standing.

## What is already running

**Check this before starting anything.** Loops from an earlier session outlive
it, and two of the same fetcher is two fetchers. `watchers/README.md` holds the
detail and a one-liner that lists them.

On 11 September, running (Windows Update restarted the machine at 03:18 and
took down everything listed here the day before; these were started again
from 08:57, with the person's leave to fetch for that absence):

| | |
|---|---|
| `watchers/gc_lane.py` | **the one General Court worker**: runs `watchers/gc_lane.queue` step by step holding `archive/.lock` -- the 2015-2016 docket, then bill text 2017-2024 in 800-request runs with an hour's rest between. Stopped at 11:36 on the 11th on a refusal (two read timeouts); **restarted at 12:47** after `netcheck.py` and `refusal.py --clear`, on the person's leave, at 25 s a page |
| `watchers/captions_watch.py` | YouTube, not the General Court; 676 captions wanted at the start |
| `review.py --port 8799 --refresh --no-open` | the bench, loopback only; pools are cached on disk in `review/.pool-*.json`, so it needs `--refresh` after any parser change or rebuild, across restarts too |
| one `http.server` on 8787 | serves `site/` (the `site` entry in `.claude/launch.json`) |

**Not running, on purpose: `watchers/narrative_watch.py`.** The 2015-2016
docket mixes database lines the narrator fails on with web lines; narrate it
by hand. See `watchers/README.md`.

A refusal stops the lane and every fetcher. `archive/refused.json` absent is
what "no refusal in force" looks like; `python3 netcheck.py` then
`python3 refusal.py --clear` is a person's decision.

**Those watchers used to live in a session scratchpad** -- a temp directory
keyed to one conversation -- so when the conversation ended they kept running
and could not be found again. One of them polled for eleven hours and forty
minutes for a token a crashed build was never going to write. They are in
`watchers/` now for that reason.

## Starting a new session

Run the three commands at the top. Read `STATE.md`, which they just wrote, and
then `LAUNCH.md`, which says what to do next and is the newer answer wherever
it disagrees with this page.

The person you are working with knows this system well, has caught several
wrong answers, and prefers being told when something is a guess. Several of the
best sources in this archive were found by them opening a URL in a browser
after the code had concluded the data did not exist -- the 1996 bill text, the
list of everyone who ever served, the roll call page carrying every member's
party, and the General Court's own key to its docket shorthand. When something
looks unreachable, say so plainly and say what a person could open; do not
quietly conclude it is impossible.

Two habits they asked for and should not have to ask for again: a brief status
of any running fetch at the end of every reply, and the next two steps named.

