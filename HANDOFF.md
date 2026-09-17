# Granite Record — handoff

For whoever picks this up next, human or model. Read this once; it changes
slowly. For the current numbers, run `python3 handoff.py` and read `STATE.md`,
which is generated and always right.

**Three things are only here**, and they are the reason to open this page at
all: how the working relationship runs, **what is running on this machine right
now** (the one thing no generated file knows, and the thing that costs a day
when it is wrong), and how publishing works. Everything else below has a newer
home -- `CLAUDE.md` for the rules and the shape of the code, `STATE.md` for
every count, `LAUNCH.md` for the plan, `README.md` for the front door -- and
where this page disagrees with one of them, they win.

That duplication is not harmless. On 17 September seven of the numbers on this
page were stale, and every one of the seven was stale in `CLAUDE.md` too, in
the same words, because it had been copied. A second copy of a fact is a second
thing to keep true. Prefer deleting a paragraph here and leaving a pointer to
keeping two copies in step.

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

A couple of minutes, no network -- `preflight` is nearly all of it, and its
`--code` half alone took 63 s in this morning's nightly. `inventory` lists
every file and its version, `preflight` runs the 159 checks and builds the
whole site on a fixture, and `handoff` writes `STATE.md` with the current
counts.

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
touched: `preflight.py` at `2026-09-04.190` has been edited a hundred and
ninety times since 4 September. Do not read a stamp as a modification date, and
do not conclude that a file with an earlier date predates one with a later
date. This example read `2026-09-04.12` for a fortnight, which is worse than
stale: `.12` is the stamp three *other* scripts carry today
(`build_legislator_pages.py`, `check_live.py`, `nightly.py`), so anyone
grepping for it landed on the wrong file, and `preflight` would reject `.12` on
`preflight.py`. `python3 inventory.py` prints the current stamp of every file;
take one from there rather than from prose.

---

## What this is

graniterecord.org: a public record of the New Hampshire General Court. Every
bill since 1989, the sitting roster and everyone who has served, hearings on
record for all nineteen terms -- a `verification_manifest*.csv` for each, the
last eight of them built this morning -- and, for the recorded ones, the moment
in the recording where a chair took the bill up. The counts live in `STATE.md`,
which is generated; the ones that used to sit here were fifteen times too small
within a week of being typed, and this line said "seven terms" for a week after
it was eleven.

It is a static site. Files on a CDN, nothing to go down, and exactly one thing
that runs: `functions/api/report.js`, the write-only endpoint behind the "report
a problem" box, which is on no page's critical path and falls back to an email
link when it is down. That is a constraint worth keeping.

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

**A roll call's clock.** `RollCallSummary.txt` records the wall-clock time of a
House roll call -- 5,363 of the 5,577 House rows across the current file and
the 27 archived years in `rollcalls/`; the other 214 read midnight. Subtract
the livestream's start and you have the moment a floor debate ended, from a
source with no captions in it. Hand-checked at seven seconds, three seconds,
and exact. **The Senate gets none of this:** all 3,988 Senate rows in those
same files are stamped `12:00:00 AM`, so no Senate floor debate can be placed
this way. Anyone asking why a Senate timestamp is missing should start here and
not in the caption code.

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

The site says which by what it does *not* qualify: a boundary the chair stated
is shown plainly, and an inferred one carries one word, *approximate*. Those
are different claims. (This paragraph quoted *"estimated within ±5 min"* for a
fortnight after the string came out of `app.js` -- it appears there zero times
today.) The chair's words are deliberately
not published, because captions render "HB 1381" as "HP 1381" and a garbled
quote presented as what someone said is a transcription error wearing the
clothes of a citation.

---

## The shape of the code

**One table for proceedings.** `proceedings.csv`, built by
`build_proceedings.py` from every `verification_manifest*.csv` -- one per term,
nineteen of them as of this morning -- plus the floor index, and read through
`proceedings.py` by everything. It globs them all on every run so that no
writer here ever sees a subset (`build_proceedings.py:311-316`). This exists
because those sources used to be read separately, and five tools in one day
were found to silently exclude the floor. Do not add a sixth reader of the old
files, and do not give it a `--term` flag.

**Five files are a person's.** `ground_truth.csv` (35 proceedings timed
with a stopwatch), `review/checked.jsonl` (the bench's judgments,
append-only, 165 of them), `bill_notes.json` (what a recurring bill number
means), `officials.json` (offices filled by hand) and
`member_corrections.json` (a name or party a generator got wrong, with the
evidence beside it). None can be regenerated. `preflight` fails if any
`build_*` or `fetch_*` script opens one for writing, and the check is named for
the category, because for a while it named only the first file and the others
had no guard at all. The list is `HANDMADE` in `preflight.py`; read it there,
because it has grown twice and this sentence said "four" for a week after it
was five.

**`build_all.py` is the pipeline.** 39 steps declared; `--local` skips the
twelve that touch the network and the one marked superseded, so a local build
is 26 steps. `--dry-run` shows the plan, and `site/build.json` records what the
last build actually ran, step by step with its seconds -- read that rather than
this sentence. A step marked `superseded=True` is kept for a case a newer step
does not cover and does not run unasked.

**`preflight.py` is the test suite.** 159 checks, 120 of which run under
`--code` and need no data on disk. It builds the whole site on a fixture, loads
`app.js` -- the script `bills.html` pulls in -- in node and calls `render()`
and `renderDetail()`, and runs the marker cases. Add a check whenever something
breaks in a way a check could have caught.

---

## What to do next

`LAUNCH.md` is the working list, written on 9 September by measuring the site
rather than by reading these documents. What follows is the part of it that
belongs here, because it is about how the code is built rather than what it
shows.

**1. Split `build_site_v2.main`**, still the longest function in the file and
now **533 lines** -- it was 468 when this line was written, so it grows while
it waits, and `build_bills` behind it is back to 346. Its two predecessors are
done: `renderDetail` on 6 September, `build_bills` on 10 September -- 544 lines
to 294 in nine steps, each verified by building into a scratchpad tree and
diffing a sha256 manifest of all 34,114 files against a baseline that was
itself built twice under different `PYTHONHASHSEED` values first. A split does
not hold itself, so measure rather than quote this line:

```
python3 -c "import ast;t=ast.parse(open('build_site_v2.py',encoding='utf-8').read());print(sorted(((n.end_lineno-n.lineno+1,n.name) for n in ast.walk(t) if isinstance(n,ast.FunctionDef)),reverse=True)[:5])"
```

The station code that caused the floor-marker miss already came out; what is
left in `main` is the loading.

**2. More marker patterns.** `segment_markers.py --all --gaps` prints what the
chair says where no boundary was found; `--phrases` counts those across every
recording so a shared convention appears as a number. That loop took coverage
from 40% to 71% in an evening and is not exhausted. Add a phrase to
`tests/test_markers.py` only if it was actually spoken.

**3. Use the bench.** `python3 review.py` serves one sample at a time and
appends a judgment to `review/checked.jsonl` -- nine kinds of sample, 165
judgments on file -- and `probe_alignment.py --truth` reads the timed ones
beside `ground_truth.csv`'s 35, with `--no-bench` for a number comparable with
anything recorded before 9 September. **Take the two counts from the command's
own header, not from here**: the "43 marks across 15 recordings" this line
carried for a week is not reproducible from any state of `checked.jsonl`. The
bench showed the schedule offset rather than
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
reads "Rep. Steve Shurtleff (D - Merr 15)", which is the opposite of showing
members who have left exactly like the rest. This line used to say "676 members
read that way": 676 is the size of `former_members.json`, and `build_data.py`
builds `former` by merging that with `past_members.json` (2,614 more), so the
population carrying the database-row label is larger than 676. Count the
ballots before quoting a figure -- the item is bigger than it looks, which
strengthens it rather than weakening it.

**5. ~~The docket parser.~~ Done on 16 September** (`2dd7fec`, 18:35), three
and a half hours after this page was last written. 1,062 modern House docket
lines were taking the 1989-98 path in `docket_parser.py` and carrying a wrong
proceeding kind and a garbled room, 1,029 of them in 2021-2022 -- the largest
remaining bucket of factual error on bill pages. The defect was not the
meridiem everyone assumed: it was `HOUSE_SCHED_RE`'s trailing `$` anchor, which
made the venue class responsible for absorbing every word the clerk appended
after the room, so one colon or one Zoom paragraph failed the whole line and
dropped it through to the legacy pattern, which hardcodes kind="hearing".
Dropping the anchor rescued 1,061 and making the colon optional took it to
1,062. The manifests rebuilt and video matching re-ran, as this item warned
they would have to.

---

## Keeping the documents true

`STATE.md` is generated -- run `python3 handoff.py`. Never edit it.

`CLAUDE.md`, `LAUNCH.md`, `DESIGN.md` and `obsolete/README.md` are the
person's, written by hand to explain why things are as they are. Correct a
stale number in them freely; never rewrite the argument, because the argument
is the point of them. `HANDOFF.md` (this file) and `ARCHITECTURE.md` are the
assistant's to keep current. `README.md` is the front door for the open-source
release and is the first thing a newcomer reads. `ROADMAP.md`,
`ARCHIVE_PLAN.md`, `FOLLOW.md` and `PROPOSAL-civics.md` are older plans kept
for their reasoning, and `watchers/README.md` is the truth about the
long-running loops.

`TESTING_QUEUE.md` was named here and in `CLAUDE.md` for a while and has never
existed in this repository -- which is exactly the kind of thing this paragraph
is about. When one of them says something the code no longer does, that is a
bug in the document; fix it in the same session, because a document that is
wrong once is not trusted again.

Numbers do not belong in the hand-written files. If you find yourself typing a
count, it belongs in `handoff.py` instead -- and this page has broken that rule
at least seven times, every one of them wrong within a week: the terms with
hearings, `build_all`'s step counts, `main`'s length, the hand-made file count,
the bench's marks, the example version stamp and the members reading as a
database row. Every one of the seven was wrong in `CLAUDE.md` in the same
words, because it had been copied there or from there. Where a number is
genuinely needed here, put the command that prints it on the line beside it, so
the next reader can tell in a second whether it still holds.

---

## Publishing

`publish.bat` rebuilds from local files, runs `check_site.py`, then **refuses
to go any further unless this folder is on `master`** -- `--branch` sends the
deploy to production whatever git says, so a report-triage branch checked out
here would otherwise become the site. It deploys with
`npx wrangler pages deploy` to the Cloudflare Pages project, retrying up to
four times because the failure it hits is an upload timeout on the fat files
and Pages assets are content-addressed, so each attempt starts where the last
one stopped. Then it runs
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

**Do not start a fetch on the strength of the table below.** It is a snapshot
of one moment, it has been six days out of date twice, and a session that
trusts a stale copy of it starts a second fetcher -- which is one of the two
things that got this address blocked by the General Court's firewall. The disk
knows; this page only remembers. Look at these instead, in this order:

```
archive\.lock          the lane's pid, touched every minute it runs.
                       A fresh mtime means a fetch is in flight RIGHT NOW.
archive\refused.json   absent is what "no refusal in force" looks like.
logs\gc_lane.log       the lane's steps, newest last, each with its log file.
logs\gc_lane.done      every queue line already finished.
logs\gc_*.log          one per step, named for the time it started.
```

and the `Get-CimInstance Win32_Process` one-liner in `watchers/README.md`,
which prints every `watch|fetch_` process with its command line. That one-liner
is the answer to "what is running"; this table is only ever a note about when
somebody last looked.

Last looked at 17 September, 10:32 — `archive/.lock` held by pid 10796,
`archive/refused.json` absent:

| | |
|---|---|
| `watchers/gc_lane.py` | **the one General Court worker**, started 16 September 09:44 and still up. Works `watchers/gc_lane.queue` step by step holding `archive/.lock`, and writes each finished line to `logs/gc_lane.done` |
| `fetch_legislation.py ... --note bills-06` | the lane's current step, started 08:30. Archived bill text 1989-2024, newest first, 2016 skipped, 800 requests at 20 s apart -- about four and a half hours a run, with an hour of `watchers/rest.py` between runs. `bills-01` to `bills-05` are behind it in `logs/gc_lane.done` |
| one `http.server` on 8787 | serves `site/` -- the `site` entry in `.claude/launch.json` |
| two `http.server` on 8802 | also serving `site/`, both started 16 September 08:44. Nothing in this repository starts them and no config here names that port |

Not running, though this page listed them as running for six days:
`watchers/captions_watch.py` and `review.py --port 8799`. `review.py`'s pools
are cached on disk in `review/.pool-*.json`, so it needs `--refresh` after any
parser change or rebuild, across restarts too.

**Not running, on purpose: `watchers/narrative_watch.py`.** The 2015-2016
docket mixes database lines the narrator fails on with web lines; narrate it
by hand. See `watchers/README.md`.

A refusal stops the lane, and stops every fetcher that consults `refusal.py` --
which is twelve of the twenty-four web fetchers, not all of them. The nine that
ask gc.nh.gov directly and never look (`fetch_bill_status`, `fetch_bill_text`,
`fetch_committee_reports`, `fetch_committees`, `fetch_journals`,
`fetch_members`, `fetch_schedule`, `fetch_session`, `fetch_testimony`) would
walk straight through a recorded refusal if somebody started one by hand. That
is a gap, not a design. `python3 netcheck.py` then `python3 refusal.py --clear`
is a person's decision.

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

