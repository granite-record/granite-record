# Granite Record — handoff

For whoever picks this up next, human or model. Read this once; it changes
slowly. For the current numbers, run `python3 handoff.py` and read `STATE.md`,
which is generated and always right.

**What is only here**: how the working relationship runs, and how publishing
works. A handful of smaller details are only here too, each flagged where it
appears. Everything else has a newer home -- `CLAUDE.md` for the rules and the
shape of the code, `STATE.md` for every count, `LAUNCH.md` for the plan,
`README.md` for the front door, `watchers/README.md` for what is running on
this machine -- and where this page disagrees with one of them, they win.

A second copy of a fact is a second thing to keep true. Prefer deleting a
paragraph here and leaving a pointer to keeping two copies in step.

---

## How this working relationship runs

**The assistant works the repository directly.** It lists files, greps, runs
the builds and the checks, edits in place and commits.

- **Read the artefact before modelling it.** Open the file, the page, the
  record. Nearly every good result here came from that and nearly every bad
  one from assuming a shape.
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

A couple of minutes, no network. `inventory` lists every file and its version,
`preflight` runs the checks and builds the whole site on a fixture, and
`handoff` writes `STATE.md` with the current counts.

**Trust their output over anything written in prose, including this file.**
Documents go stale; those three read the disk.

If `preflight` is not green, stop and fix that first. It caught three stamp
mismatches, a dead-zone crash and a hung build in one week, and every one of
them would otherwise have reached the site.

Version stamps have their own rule in `CLAUDE.md`. The trap worth repeating:
the date in a stamp is when the file was **created**, so a stamp is not a
modification date and a later date does not mean a later edit.

---

## What this is

graniterecord.org: a public record of the New Hampshire General Court. Every
bill since 1989, the sitting roster and everyone who has served, hearings on
record for all nineteen terms, and for the recorded ones the moment in the
recording where a chair took the bill up. The counts live in `STATE.md`, which
is generated; the ones that used to sit here were fifteen times too small
within a week of being typed.

It is a static site. Files on a CDN, nothing to go down, and exactly one thing
that runs: `functions/api/report.js`, the write-only endpoint behind the "report
a problem" box, which is on no page's critical path and falls back to an email
link when it is down. That is a constraint worth keeping.

---

## The rules

The five learned expensively are in `CLAUDE.md`: read the artefact before
modelling it; measure against something you did not generate; silence is not
success; a writer of a derived file, run on a subset, destroys the rest; one
fetch at a time, and a refusal outlives its run.

Two things are only here. Every fetcher reads a list of what exists rather than
guessing at filenames, which is what the first block was for. And **YouTube is a
different host**, so a caption fetch may run beside a General Court one.

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
are different claims. The chair's words are deliberately not published, because
captions render "HB 1381" as "HP 1381" and a garbled quote presented as what
someone said is a transcription error wearing the clothes of a citation.

**Some bench verdicts cannot be used as verdicts.** For its first day the
sampler showed the schedule offset rather than the published time, so any
judgment made then graded the wrong number. The ledger is append-only and
nothing rewrites it; `review.py --report` flags those entries every time anybody
reads it. Their hand-timed values are a person's own stopwatch and are as good
as any other.

---

## The shape of the code

`CLAUDE.md` carries this: one table for proceedings, the five hand-made files
no generator writes, `build_all.py` as the pipeline, `preflight.py` as the test
suite. Two details are repeated here, `README.md` carrying the first and
`CLAUDE.md` the second, because the ranking below them is not written anywhere
else.

`site/build.json` records what the last build actually ran, step by step with
its seconds. Read that rather than any prose about step counts, including
`CLAUDE.md`'s.

`--local` skips the steps that touch the network and the one marked superseded,
which is why a local build is shorter than the declared plan. `--dry-run` shows
the plan.

---

## What to do next

`LAUNCH.md` is the working list, written by measuring the site rather than by
reading these documents, and `CLAUDE.md` holds the code-shaped items. Three
things belong here.

**A split does not hold itself**, so measure `build_site_v2.main` rather than
quoting a line about its length:

```
python3 -c "import ast;t=ast.parse(open('build_site_v2.py',encoding='utf-8').read());print(sorted(((n.end_lineno-n.lineno+1,n.name) for n in ast.walk(t) if isinstance(n,ast.FunctionDef)),reverse=True)[:5])"
```

**A label states the seat held when the record was made** -- the person's rule,
and half of it is still to do. Sponsor lines and roll call ballots now take
their chamber, county and district from the bill's own printed line where the
record can attest it, rather than from the roster of the House and Senate
sitting today. The gap is in `build_data.py`: a member who has LEFT still
carries one seat for all time, and reads as a database row -- `_former_label`
builds "Shurtleff, Steve(D) Merrimack 15" where everybody else reads
"Rep. Steve Shurtleff (D - Merr 15)", which is the opposite of showing members
who have left exactly like the rest. Count the ballots before quoting a figure:
`former_members.json` holds 676 names, but `build_data.py` builds `former` by
merging it with `past_members.json` (2,614 more), so the population carrying
the database-row label is larger than 676.

**One trap kept from the docket parser**, fixed in `f9e69f6`: `HOUSE_SCHED_RE`'s
trailing `$` anchor made the venue class responsible for absorbing every word
the clerk appended after the room, so one colon or one Zoom paragraph failed the
whole line and dropped it through to the 1989-98 legacy pattern, which hardcodes
kind="hearing". 1,062 modern House lines were carrying a wrong proceeding kind
and a garbled room because of it -- the largest single bucket of factual error
on bill pages at the time. Dropping the anchor rescued 1,061 and making the
colon optional took it to 1,062. Manifests and video matching had to rebuild
afterwards, as anything touching the docket parser will.

---

## Data defects waiting on one diagnosis

Reported and confirmed, deliberately NOT chased one at a time. Asked for on
19 September: "we should wait until after the bill fetch is done so we can look
into those issues more broadly rather than a couple at a time." These look like
they may share a cause, and a defect fixed alone gets a narrow patch while the
cause survives to make the next one. Open one investigation across all of them.

**A member on a committee he had left.** `site/committee/H12.json` lists Joseph
Barton as a member of House Legislative Administration. He has not been on it
for over a year, and -- this is the part that matters -- the General Court's own
page did not say he was when the roster was fetched either. So this is not
stale data. Something in the fetch, the parse or the merge put him there, which
makes it the same class of bug as a parser error and not a refresh problem. The
roster lives in `data/committee_members.json`, written 7 September, and reaches
the page through `build_committees.py`. **Start by asking how many other
members are on a committee their own record does not put them on**, rather than
by fixing this one row.

**Actions dated where they did not happen.** The docket carries floor actions
whose date disagrees with the journal number they cite. HB 1491's reconsider is
recorded as 09/19/2026 on a row that was WRITTEN at 8/19/2026 2:27 PM and cites
HJ 16, the 19 August sitting -- a clerk cannot record something a month before
it happens, so that one is provable. But across the whole record 436 events sit
on a date their journal number disagrees with, and most of those have a
legitimate alternative explanation: a journal issue can print business carried
over from an earlier day. The safe test is the narrow one -- an action dated
AFTER the row that recorded it is impossible -- and it needs the docket row's
creation timestamp carried into `narratives.json`, which it currently is not.
Do not bulk-correct on the journal number alone.

## Errors in the General Court's own record

There is a running list of them, for the person to bring to the House and
Senate Clerks' offices so each can be fixed at the source as well as here --
asked for on 24 September. It holds only the General Court's own errors, and
only errors of fact: a docket row, a database field, a roll-call file or a
journal that the rest of the record contradicts -- a wrong date, a vote filed
under the wrong bill, the wrong mover. Spelling slips stay off it (the person,
25 September). A misfiled vote or a wrong mover goes on the list rather than
being corrected on the site, unless the person approves a site correction for
that case, as they did for HB 1364 of 2026. Each entry quotes what the record says and where, what
the evidence shows, and where that evidence is, so the Clerk's staff can check
it without redoing the work; evidence that is suggestive but not conclusive
goes under "To check", with what would settle it.

**The list is not in this repository, and must not be.** It is
`CLERK_CORRECTIONS.md` at the root of the working folder on the person's PC,
untracked: the person chose to keep it out of GitHub so that the Clerks' offices
hear about each error from them first, not from a public repository.
`.gitignore` names it, and preflight fails if git tracks it or if any commit on
any ref holds it -- the first version was committed before that answer came,
and had to be taken back out of its branch. Do not quote its entries in a
tracked file, this one included. A private link to it (an Artifact) may be
offered when the person wants to share it with the Clerks' offices.

**Whenever work finds an error in the General Court's own record, add it there
with its evidence, in the same session.** Rule out our own parser first, by
re-reading the raw row: HB 113 of 2005's "introduced on December 1, 2006" looks
like a clerk's slip and is `narrative.clamp_year` moving a row entered on
12/01/2004 into 2006, the year in the row's session column, because the bill was
retained into its second year. The list is the assistant's to keep and the
person's to deliver. A correction the site itself applies is a separate matter
and goes in `docket_corrections.json`, which is the person's.

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

When one of them says something the code no longer does, that is a bug in the
document; fix it in the same session, because a document that is wrong once is
not trusted again.

Numbers do not belong in the hand-written files. If you find yourself typing a
count, it belongs in `handoff.py` instead -- this page has broken that rule at
least seven times and every one of them was wrong within a week, in the same
words in `CLAUDE.md`, because it had been copied from one to the other. Where a
number is genuinely needed here, put the command that prints it on the line
beside it, so the next reader can tell in a second whether it still holds.

---

## Publishing

`publish.bat` rebuilds from local files, runs `check_site.py`, then **refuses
to go any further unless this folder is on `master`** -- `--branch` sends the
deploy to production whatever git says, so a report-triage branch checked out
here would otherwise become the site. It deploys with
`npx wrangler pages deploy` to the Cloudflare Pages project, retrying up to
four times because the failure it hits is an upload timeout on the fat files
and Pages assets are content-addressed, so each attempt starts where the last
one stopped. Then it runs `check_live.py --gate`, which compares what the
domain serves against what was just built -- because wrangler has reported
success for deployments the production domain never took. The gate has also run
too early: a deploy that "did not land" thirty seconds after upload had landed
by the second check.

`npx` is `npx.cmd`, and without `CALL` a batch file that runs another never
gets control back, so for a while every publish ended at wrangler's own
"Deployment complete!" and the gate never ran at all. A publish log that ends
there, with no "Confirming the world is getting what was just built" after it,
is that fault back.

Deploying is a person's decision. When the person is away from the keyboard
they have sometimes said so and permitted it; that is per-absence, not
standing.

## What is running

**No document can answer this, including this one.** The disk knows; a page only
remembers what somebody saw once, and a session that trusted a stale note is one
of the two things that got this address blocked by the General Court's firewall.
Look at these, in this order:

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
is the answer to "what is running".

`watchers/gc_lane.py` is **the one General Court worker**. It works
`watchers/gc_lane.queue` step by step while holding `archive/.lock`, and writes
each finished line to `logs/gc_lane.done`.

**Not running, on purpose: `watchers/narrative_watch.py`.** The 2015-2016
docket mixes database lines the narrator fails on with web lines; narrate it
by hand. See `watchers/README.md`.

A refusal stops the lane, and since 18 September it stops every fetcher holding
a literal `gc.nh.gov` URL as well: each calls `refusal.check()` once its
arguments are parsed, and `preflight` fails if one of them stops. Ten did not
check until that morning, so anything written before it -- a note, a session
summary, this paragraph in an older revision -- describes a wider gap than the
one that is left. What is left is `fetch_committee_details.py`, which reads its
addresses out of `committees.json` instead of carrying one, so it asks
gc.nh.gov without the check seeing it. `python3 netcheck.py` then
`python3 refusal.py --clear` is a person's decision.

**The HB/SB/CACR sweep of 1989-2024 is finished.** It ran on 19 September at
the person's word -- `fetch_legislation.py --all --from 1989 --to 2024
--skip-year 2016 --kinds HB,SB,CACR --delay 5 --budget 800`, queued as
repeating steps of 800 -- and step 17 at 20:38 reported `0 to ask ... the
range is done`. **29,324 pages across 38 year folders**, up from 11,937 when
`CLAUDE.md` described this path and 27,258 at the start of that session:
20,883 HB, 7,718 SB, 491 CACR. Run `find legislation -name '*.html' | wc -l`
rather than quoting that figure. 2016 was skipped throughout and has not been
retested.

**Then the lane stopped, and the stop is the guard working.** The queue's next
command dropped both filters -- `--all --from 1989 --to 2024 --delay 5
--budget 400 --note everything-else-01` -- to go after the other thirteen
kinds. It asked 82, saved 74, met three 404s in a row on 1992 SR bills and
stopped itself at 20:45. No refusal was recorded, because a 404 is not one,
and `archive/refused.json` is absent: nothing is held, and the next fetch is
free to start whenever a person wants one.

**Do not simply restart it.** Counted against `site/index.json`, the thirteen
minor kinds hold **1,259 bills in 1989-2024 and 232 of them are on this path**
-- 461 of 514 HR missing, 278 of 334 HCR, 104 of 139 SR. Most years carry one
SR and one HR and no more. So the remaining 1,027 addresses are mostly not
there, every one costs a request, and three misses in a row stops the queue:
the run would stall about every third miss and need restarting each time.
That is the same shape already recorded below for the 1998 CACRs, and the same
decision is still open -- whether three in a row within one year AND one kind
should mean "this kind is not on this path for this year" and skip the rest of
that kind, rather than stopping everything. It is a change to fetching
behaviour, so it stays the person's call.

What those 1,027 would buy is also the least of what this path offers. The
page is fetched for the sponsor, and `CLAUDE.md` already records that the
pages naming no sponsor are the housekeeping resolutions and budget tables --
which is most of what is left.

**1996 answers.** `CLAUDE.md` says "Only 1996 and 2016 answer 404 for every
bill asked, and that stays unexplained", and on the evening of 19 September the
lane walked into 1996 and began saving real pages -- `legislation/1996/`
HB0061, HB0148, HB0151 and on, 5 to 9 KB each, carrying the sponsor line, the
committee of referral, the title and the analysis, which is everything that
path is fetched for. Whether 1996 always answered and the earlier finding was
a probe of the wrong addresses, or whether something changed at their end, is
not established here; what is established is that pages are on disk now. 2016
is still skipped by the running command and has not been retested. The person
should be told before that line in `CLAUDE.md` is trusted again.

**Why it stopped before.** It stopped at 21:10 on 18 September with three 404s
in a row -- 1998 CACR 30, 31 and 32 -- which is the guard working exactly as
intended: three refusals or gaps in a row and it stops rather than asking on,
because asking on regardless is how the first block was earned. No refusal was
recorded, because a 404 is not one.

What the 404s mean is now known, and it is not a bug. The docket says 1998 had
25 CACRs: 8, 9, 21 and then 30 through 51. `legislation/1998/` holds CACR 8, 9
and 21, and the General Court answers 404 for every one of 30-51. So the bills
are real and their pages are simply not on that path, the same unexplained
shape as 1996 and 2016.

The consequence for a restart: the three that failed are on `legislation/
_gone.json` and will be skipped, so the lane resumes at CACR 33, meets three
more 404s, and stops again -- three requests spent to advance three numbers,
about seven restarts to clear 33-51. It works, but it limps, and every restart
spends requests on addresses now known to be absent. Worth deciding before the
next start: whether the lane should treat three in a row within one year and
one kind as "this kind is not on this path for this year" and skip the rest of
that kind, rather than stopping the whole queue. That is a change to fetching
behaviour, so it is the person's call.

`review.py` caches its sample pools on disk in `review/.pool-*.json`, so it
needs `--refresh` after any parser change or rebuild, across restarts too.

**Watchers live in `watchers/`, never in a session scratchpad.** When they lived
in a temp directory keyed to one conversation, the end of the conversation left
them running and unfindable; one polled for eleven hours and forty minutes for a
token a crashed build was never going to write.

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
