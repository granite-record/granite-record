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

**2023-2024's sponsors come from the General Court's own record now**
(`past_sponsors.py`, 26 September), and two things about it are the
person's. PastSponsors is joined by each bill's stored LSR, and
`python3 past_sponsors.py --check` prints the bar against the saved pages and
every bill that misses it -- run it rather than quoting its counts. Where a
bill's printed line and the record disagree the page's list is published, and
most of those disagreements are sponsors the record and the status page both
list and the printed bill does not, or printed sponsors the record marks
withdrawn: which of the two should win there is the first decision. Letting
the record win is not a one-line switch in `past_sponsors.merge`: an entry's
`sponsors` are the record's live rows as it keeps them -- employee, id, name,
chamber, prime -- with no party, label or source, and are not a published
list, so those bills would need `records()` run for them in `build()`, as the
bills that agree already have. The second is whether any other term takes the
record's list; none does yet. What employee 377080 is called is settled:
Rep. Lorrie J. Carey (`member_corrections.json`), whose four co-sponsorships
link to her page once `build_data.py` has put the correction on the ballots.
A published row the status page has no row for takes its party from its
member's ballots that term, and every row's chamber is the one the bill
prints, then the ballots', before the status page's, which files six sitting
senators under the House. And the nightly's kit now carries `db/past/` and
`db/Legislators.psv`, so `python3 cloud.py seed-kit` has to run once before
the next night, or its kit-down stops with THE KIT IS SHORT.

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

**Twenty-two 2018 final versions nothing could check.** On 26 September 23
bills of 2017-2018 whose "Version adopted by both bodies" was an earlier
printing took the General Court's own final version from
`db/past/PastLegislationText.jsonl` (archive_text.final_versions; the rule and
its evidence are in the docstring). 22 other bills of 2018 carry that label on a
page that prints a 2017 LSR -- bills carried into the second year -- and the view
holds no printing of them, so they were left as the page shows them. The view is
in the kit (944 MB) so that GitHub's build applies the same rule; without it the
step keeps every page's own text and says how many it could not check.

**Sixteen member names that rest on a guess from voting patterns.** Of the 38
names `member_party.json` carries with source `solved` (fetch_rollcall_parties.py
inferring who an employee number is from how it voted), 21 agree with
`db/Legislators.psv` and one was wrong: 377080 was shown as H. Robert Menear and
is Rep. Lorrie J. Carey, corrected in `member_corrections.json` on 26 September
from the General Court's PastSponsors view, her printed bills, the House
Journals and the 2022 organisation-day roll. The other 16 have no second source
on disk, and the person decided on 26 September to keep them up rather than
remove names that may be right: 376211 Courchesne, 376261 Ouellette, 376307
Bouchard, 376488 Kudalis, 376531 Taylor, 376536 Webber, 376570 Donahue, 376611
Parker, 376649 Kelly, 376678 Matheson, 376695 DesRoches, 376766 Warren, 376889
LaPlante, 376950 Hogan, 377092 Dobson, 377105 Grace. The check that would settle
each is the one that named the ids added to `member_corrections.json` on
16 September (its `_added_16_september` note): score the id's ballots against
the names printed in the House Journals' vote lists for the same roll calls,
then corroborate from the organisation-day roll, which prints each member's
party. The journals for 1997-2026 are on disk under `journals/`.

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
to go any further unless this folder is on `main`** -- `--branch` sends the
deploy to production whatever git says, so a report-triage branch checked out
here would otherwise become the site. (The Pages project's production branch
is still called `master`, which is the name `--branch` is given; the
repository's own branch is `main`. `publish.bat` explains the rename.) It deploys with
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

## The nightly on GitHub

Since 26 September the nightly runs on GitHub Actions, not on this PC, so
that the site stays current whether or not the PC is on. `.github/workflows/nightly.yml` builds the
site each night on a Windows machine GitHub lends free to public repositories,
and deploys production only after the person approves the `production`
environment. `weekly.yml` takes the committee rosters, the members who have
left and the study committees early on Monday. The nightly's schedule is on
(08:17 UTC, 4:17 a.m. Eastern in summer and 3:17 in winter). It was 06:17
until 27 September, when the first scheduled night got all 13 files under
`dynamicdatadump/` as 3 bytes, an empty file's byte-order mark (the snapshot
rightly installed none of them): the General Court evidently rewrites them
around 2:00 to 2:30 a.m. Eastern; the laptop's snapshot at 2:04 a.m. on 20
September had got two of them that way. The weekly's is still commented out,
because its swap of `committees.json` would have dropped the clerk and the
purpose; `fetch_committee_details.py` now writes those to their own
`committee_details.json`, a laptop file in the kit that `build_committees.py`
joins in (`committee_details.py` says how). So the weekly can go on once that
change is on `main` and the laptop has written the file once, with `python3
committee_details.py --from-committees`, and sent it with `python3 cloud.py
seed-kit` -- before `dev` reaches `main`, since the kit now requires the file
and a night's `kit-down` stops without it. With the file there, it is the only
source of the clerk, the purpose and the page roster: the old values
`committees.json` still carries on the laptop, and in the bucket from the first
seed, are ignored, so taking a clerk out of the details takes it off the page.
A fetch of a page that reads as a committee's replaces that committee's three
with what the page says, stamped `fetched`; a page that failed or parsed as
nothing changes nothing. House Rules' blank assistant and researcher on the
listing (saved 6 September) now read as blank in both committee parsers,
rather than as the labels after them (`Researcher:`, `Location:`). Either
can be started by hand from the Actions tab; do not start one while a night is
waiting for approval, because the newer run makes the waiting one
unpublishable.

GitHub's machine starts empty every night. `cloud.py` brings it what git does
not hold, from the private R2 bucket (`keys.R2_BUCKET` names it), and its
docstring is the reference:

- `kit/` holds the files the build reads. `cloud_kit.json` lists them and says
  which machine owns each, because two writers of one file is how the older
  copy wins. The laptop sends it once with `seed-kit`; each night takes it
  with `kit-down` and sends back what it changed with `kit-up`.
- `state/` holds the few small files a night must remember -- the refusal
  record, the census -- which live under `archive/` on a machine.
- `nights/<run>/` holds the night's built site, handed to the publish job as
  one archive. Never as a GitHub artifact: anyone signed in to GitHub can
  download a public repository's artifacts, and the site carries the licensed
  logo. `preflight` fails if a workflow uses one.
- `backup/` is the laptop's copy of everything git does not hold
  (`cloud.py backup`).
- `replaced/` holds whatever a command would otherwise have overwritten or
  removed. `cloud.py` deletes nothing outright; the bucket's lifecycle rules
  clear `replaced/` and `logs/` after 30 days and `nights/` after three.

Credentials come from `keys.r2()`: repository secrets on GitHub, `secrets.json`
on the laptop. Nothing else reads them.

**The night never reads a caption file.** The captions stay on the laptop, and
what the night knows of them is two files the laptop owns in the kit:
`candidate_segments.json` (the boundaries the chair stated) and
`caption_spans.json` (where each recording's captions stop, which is how the
night withholds a track that runs an hour late). So whenever the laptop re-reads
captions -- a build after `segment_markers.py` or its patterns change, or a
caption job -- run `python3 cloud.py seed-kit` afterwards, and check that the
dry run lists only those files. Until it does, the night publishes the older
boundaries. On 26 September that was two hearings, HB 748 and HB 752 of 2025,
shown as approximate on GitHub's build and as stated on the laptop's.

**The laptop stood down on 26 September.** `python3 refusal.py --stand-down`
wrote `archive/runs-in-the-cloud.json`, so the laptop's nightly, snapshot and
the fetchers GitHub owns refuse with exit 4 and a sentence saying why, and
`publish` refuses with exit 1 (`publish --check` still builds and checks).
Other General Court fetchers still run here, each with the person's go-ahead,
and three things now keep them and the night apart.

**GitHub's night window.** On a stood-down laptop no General Court request
starts from 08:00 to 13:30 UTC daily (the night starts 08:17 and may run four
hours, and GitHub often starts a scheduled run late, so an hour is allowed for
that) or from 04:00 to 06:30 UTC on Monday (the weekly, 04:17, two hours):
4:00 to 9:30 a.m. EDT in summer, 3:00 to 8:30 a.m. EST in winter, and on a
Monday also midnight to 2:30 a.m. EDT, which in winter is 11:00 p.m. EST on
the Sunday to 1:30 a.m. Nor does one start in the 30 minutes before a window
opens (`refusal.START_MARGIN_MINUTES`). Since the night moved to 08:17 the
two Monday windows are separate, so a fetch may start between them, from
2:30 to 3:30 a.m. EDT, once the bucket's refusal record has been read since
the weekly's closed; a weekly started late enough to run past 06:30 UTC is
not covered there, as the night's window used to cover it.
`refusal.NIGHT_WINDOWS` is the one definition, and moves with the cron line
in `nightly.yml`. `refusal.check()`, which every General Court fetcher calls after
parsing its arguments (after an offline branch that asks nobody, such as
`--parse` or `--reparse`), exits 4 inside the window and the half hour before
it, with a sentence naming the window in Eastern time and when it ends;
`watchers/gc_lane.py` stops before its next step the same way, daily steps
included, and does not record a daily step that itself exited 4 as run while
`refusal.gc_turn()` says it is GitHub's turn (a 4 that `gc_turn()` does not
explain is the stand-down itself -- the script refuses here because GitHub
runs that job -- so that step is recorded, the log says its line should come
out of the queue, and the lane goes on); and
`probe_db` stops a query of the SQL host in the window and the half hour
before, at every one of its bridges (`run`, `run_to_file`, and `_bridge`
under `run_to_file_counted` and `run_to_jsonl` -- preflight reads the source
for any function that starts PowerShell without asking first), because the
night takes the study committees' views from that host and the weekly the
rosters (the window only: the web server's refusal record is not the SQL
host's). Exit 4 and not 2, because the lane and the fetchers read 2 as the
address refusing. A fetch already running when the window opens stops at its
next request if it asks `refusal.hold().still()` before each one, as the
fetchers that hold `archive/.lock` do (legislation, the docket and calendar
archives, the Senate calendars, leadership, sponsors by member, the
snapshot); one that does not keeps asking, so a long one is best started
after 9:30 a.m. **A run the window stopped does not end as finished.** The
hold remembers the stop: a `with refusal.hold()` block left normally, or by
`sys.exit(0)`, exits 4 instead (the Senate calendars and sponsors by member
used to return 0 from the loop that stopped), and a 2, a 3 or an exception
passes unchanged. The lane names a file in `refusal.WINDOW_STOP_ENV` for
each step (`logs/gc_lane.window-stop`), which the step's hold writes when the
window stops it, so a step cut short is recorded in neither
`logs/gc_lane.done` nor `logs/gc_lane.daily` whatever status it ended with
-- 0, 1 and 3 included -- and the lane stops with 4. The weak point is still GitHub itself: a night started more
than an hour late could still be asking after 13:30. `python3 refusal.py`
prints the window and whether it is open.

**Bringing the nights back: `python3 cloud.py pull`.** It is the laptop's only
(it refuses on GitHub, where `kit-down` is the command), it only ever reads the
bucket (preflight reads every function it reaches for a put, copy or delete),
and it refuses beside a running build. It stops before reading anything from
a bucket that holds neither the kit manifest nor a night's verdict -- empty,
or not the night's. It brings the night's own kit files down where the
laptop's copy is still the one it last had in common with the bucket
(`archive/cloud/pull.json` records that; before a file's first pull the
bucket's own old manifests under `replaced/` settle it); a night's file the
laptop changed since -- or changed while the pull ran, which it looks for
again just before replacing the file -- is named as a clash and pull exits 1,
and `--take PATH` (written any way a person copies it: `.\x`, `./x`, `x\y`, or
absolute under the working folder) sets the laptop's copy aside under
`archive/cloud/set-aside/<day>/` and takes the bucket's. A laptop build
rewriting the carried outputs (`proceedings.csv`, `narratives.json` and the
rest) is the usual clash. It never touches the laptop's own files, which go
the other way with `seed-kit`, or `site/`. It brings the night's logs to
`logs/` (so `preflight`'s nightly check reads them), its change lists to
`reports/gc-changes-<day>.md` and `gc-changes-weekly-<day>.md`, and the
verdicts to `archive/cloud/last-night.json` and `last-weekly.json` -- from the
day before the last pull's (a night's folder is named for the day it started
in Eastern time, and the winter weekly starts on Sunday evening), seven days
at most, or `--day`; a last-pull date in the future is taken as today, and
said. A night's verdict from before yesterday is printed as STALE.
`--changes-only` is the morning triage's: the refusal, the verdicts and the
change lists, nothing else -- plus a line saying how old the last full pull
is and how many of the night's files the bucket's kit manifest has changed
since. `pull.json` records the last full pull (`"full"`) that brought every
file down whole. `--dry-run` writes nothing and makes no folder.
`--local-bucket` is for tests: pull refuses it in the stood-down repository
that holds `secrets.json` unless `--allow-local-bucket` is given.

**Refusals cross both ways.** Every pull reads the bucket's
`state/refused.json` first: where the laptop has none it comes down as
`archive/refused.json`, so a refusal the night met stops laptop fetches too;
where both hold one the newer stands and the older is set aside, never
dropped. What each stops is printed as `refusal.force()` says: in force for so
many more hours (every fetch here stops at it), or older than 24 hours (hand
fetches here are not stopped by it, the lane is, and GitHub's night stops at
it until `python3 cloud.py clear-refusal`). The read is recorded with the kind
and name of the bucket, and `refusal.check()` on a stood-down laptop refuses
to start a General Court fetch until the REAL bucket's record has been read
since the last night window closed -- `python3 cloud.py pull --changes-only`
is enough; a read of a `--local-bucket` folder never counts -- because
otherwise a refusal met last night is invisible here.

The other way, a refusal `refusal.note()` records on a stood-down laptop is
sent to the bucket's `state/refused.json` at once when the bucket holds none,
so the night stops too -- but only from the repository that holds
`secrets.json` (`cloud.home()`); a refusal recorded in any other folder with a
stand-down file in it, a test's, needs a folder bucket and never reaches R2.
**Not every General Court fetcher records a refusal.** The ones that call
`refusal.note()` are `fetch_archive_docket`, `fetch_archive_text`,
`fetch_calendar_archive`, `fetch_committees`, `fetch_leadership`,
`fetch_legislation`, `fetch_lsrs`, `fetch_rollcall_parties`,
`fetch_senate_calendars`, `fetch_sponsors_by_member` and `snapshot_gencourt`.
Fourteen others stop at a refusal on file (they call `refusal.check()`) but
record none they meet, so a refusal one of them meets reaches neither this
laptop's record nor the bucket's, and the night would ask again:
`fetch_archive_bills`, `fetch_bill_status`, `fetch_bill_text`,
`fetch_committee_reports`, `fetch_journals`, `fetch_members`,
`fetch_schedule`, `fetch_session`, `fetch_testimony`, `resolve_members`,
`probe_archive`, `probe_archive_shape`, `probe_calendars` and `probe_legacy`
(`fetch_committee_details`, `probe_schema` and `check_civics_links`, which
since 26 September check, record none either). Giving them `refusal.classify()` and `note()` is open
work, not done. If the bucket cannot be reached, `note()` says so loudly,
still returns, and leaves `archive/cloud/refusal-unsent.json`; if the bucket
already holds a different, older refusal, the laptop's newer one is not sent
over it -- that one stops the night already -- but waits behind it, and the
marker stays and says so. The marker goes only when the bucket holds the
refusal the laptop holds, or a person lifts the laptop's (`refusal.py
--clear`); pull, `state-up` and `preflight` report it until then, and `python3
cloud.py send-refusal` sends it whenever the bucket holds none. A standing
laptop refusal the bucket holds none of fails the pull, naming send-refusal.
**The refusal that stops a night is the bucket's**: `refusal.py --clear` lifts
the local one (and the unsent marker with it) and says so, and `python3
cloud.py clear-refusal` lifts the bucket's -- and says when the laptop holds
a refusal the bucket does not, which is the moment a waiting one needs
`send-refusal`; when the laptop's waited behind the one cleared (newer and
still in force, or named by the unsent marker) it exits 1 as well, the
clearing standing, because the bucket then holds no refusal and the night
would ask. Lifting only the local one brings the bucket's back at the next
pull. Both are a person's decision, after `netcheck.py`. Where the laptop
holds none, pull CREATES the bucket's here (a hard link from a part file, or
an exclusive create), never writing over one a fetch recorded while the pull
was reading: finding one, it compares the two as it would any two.
`cloud.home()` is the checkout that holds `secrets.json` -- it must be there,
not only named by `keys.PATH` -- so a worktree or fresh clone never counts.

`preflight`'s nightly check, on a stood-down laptop, reads the pulled logs and
`archive/cloud/last-night.json` rather than this machine's own logs, which
stopped at the stand-down: it skips until the first pull for 48 hours after
the stand-down's `since`, and fails after that, naming `python3 cloud.py
pull`; once there is a pull, it fails when the newest pulled night is more
than 48 hours old -- naming `python3 cloud.py pull` when the pull is what is
old, and the Actions tab when the pull is fresh and the night is not. A second
data check fails when the last FULL pull is more than 48 hours old (the same
48-hour grace after the stand-down when there has been none), because a laptop
that only runs `--changes-only` never brings the night's files down.
`preflight` itself sets `GRANITE_NO_BUCKET`, under which `cloud.py` refuses the
real bucket, so no check can send a made-up refusal to the night; the lane
test passes it on to the lane it runs. **And every check that starts a
fetcher, the lane or the pipeline as a process seals it** (`_Seal` in
preflight.py): a `sitecustomize.py` on the child's `PYTHONPATH` replaces
`socket.socket.connect`/`connect_ex`/`sendto`, `socket.create_connection` and
`socket.getaddrinfo` with a raiser that writes a sentinel file, the proxies
point at a closed loopback port with `NO_PROXY` cleared, and it passes to
every process the child starts. After each run the sentinel must be absent
and the seal must have loaded. Sealed now: the offline-mode check (fetch_lsrs,
fetch_members, fetch_session, probe_archive_shape, check_civics_links), the
lane test and its steps, the bill-status fetch, the docket fetch through its
wrapper, `build_all.py --local`, and every `livestreams.py` run. A check reads
preflight.py itself for any bare start of one of these, so the next check
that starts a fetcher without the seal fails.

**Branches, since 26 September: `main` is what is live, `dev` is where work
goes.** The nightly builds and publishes `main`, so a commit there reaches the
site the next night. Commit and push work to `dev`, and merge worktree branches
into `dev`. `dev` is merged into `main` only as a release the person has agreed
to, after the checks `CONTRIBUTING.md` lists, because the person wants fewer,
fuller releases rather than one per fix. The workflows stay on `main`, which
is GitHub's default branch and the one schedules run from; a run started by
hand from `dev` stops at its environment, which allows `main` only.

## What is running

**No document can answer this, including this one.** The disk knows; a page only
remembers what somebody saw once, and a session that trusted a stale note is one
of the two things that got this address blocked by the General Court's firewall.
Look at these, in this order:

```
archive\.lock          the lane's pid, touched every minute it runs.
                       A fresh mtime means a fetch is in flight RIGHT NOW.
archive\refused.json   absent is what "no refusal in force" looks like.
                       Since the stand-down, the bucket's state/refused.json
                       is the night's: python3 cloud.py pull reads it here.
archive\cloud\pull.json  when this laptop last read the bucket; python3
                       refusal.py prints it, with GitHub's night window.
archive\cloud\refusal-unsent.json  a refusal met here that the night has not
                       been told of: python3 cloud.py send-refusal.
logs\gc_lane.log       the lane's steps, newest last, each with its log file.
logs\gc_lane.done      every queue line already finished.
logs\gc_*.log          one per step, named for the time it started.
```

and the `Get-CimInstance Win32_Process` one-liner in `watchers/README.md`,
which prints every watcher, lane, nightly, fetch, snapshot, publish and
`cloud.py` process with its command line, and pastes into `cmd` as it stands.
That one-liner is the answer to "what is running" on this machine; GitHub's
night is the Actions tab, and its window is in "The nightly on GitHub" above.

`watchers/gc_lane.py` is **the one General Court worker**. It works
`watchers/gc_lane.queue` step by step while holding `archive/.lock`, and writes
each finished line to `logs/gc_lane.done`.

**Not running, on purpose: `watchers/narrative_watch.py`.** The 2015-2016
docket mixes database lines the narrator fails on with web lines; narrate it
by hand. See `watchers/README.md`.

A refusal stops the lane, and it stops every script here that asks the
General Court's web server: each calls `refusal.check()` once its arguments
are parsed (after an offline branch that asks nobody), and `preflight` reads
each for an actual call -- an `ast.Call` of `refusal.check`, not the words in
a comment -- and fails if one stops. As of 26 September those are the 28
scripts `check_civics_links`, `fetch_archive_bills`, `fetch_archive_docket`,
`fetch_archive_text`, `fetch_bill_status`, `fetch_bill_text`,
`fetch_calendar_archive`, `fetch_committee_details`,
`fetch_committee_reports`, `fetch_committees`, `fetch_journals`,
`fetch_leadership`, `fetch_legislation`, `fetch_lsrs`, `fetch_members`,
`fetch_rollcall_parties`, `fetch_schedule`, `fetch_senate_calendars`,
`fetch_session`, `fetch_sponsors_by_member`, `fetch_testimony`,
`probe_archive`, `probe_archive_shape`, `probe_calendars`, `probe_legacy`,
`probe_schema`, `resolve_members` and `snapshot_gencourt`: every script
holding a literal `gc.nh.gov` URL that makes a request (every `fetch_*.py`
holding one), plus `fetch_committee_details`, whose addresses come from
`committees.json`, and `check_civics_links`, whose come from `civics.py`
(its `--list` asks nobody and is not stopped). `netcheck.py` is the one
exception, by design: it diagnoses a refusal. The `fetch_*_db.py` scripts ask
the SQL host, not the web server, and none of them calls it. No other script
does either. `python3 netcheck.py` then `python3 refusal.py --clear` is a
person's decision.

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
