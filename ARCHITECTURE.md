# Granite Record — Architecture review

An honest account of the structure, what it has cost, and what the archive
needs from it.

IT IS LAYERED. A section that describes a problem as open may be describing
one that was fixed shortly after; where that is so, a line at its head says
so, and the reasoning underneath is kept because the measurement behind it is
still the right way to think. Where a number here disagrees with `STATE.md`,
`STATE.md` is generated and this is not.

Sections: what is sound and should be kept; the two plans of 10 September and
what became of them; what is structurally wrong, ranked by cost; and what to
do, in order.

---

## What is sound

**The data comes from bulk files.** Docket, roll calls, sponsors, members: one
download each, covering a whole session. That is why nineteen terms of bill
histories and fourteen of votes -- roll calls begin in 1999 -- are a shelf of
bulk files rather than a hundred thousand requests, and why the core of the
site has never been what provoked the General Court's firewall. The per-bill
fetches are the exception, and they are the ones that got the address blocked:
bill text, testimony, and the dockets of 2016-2024, which are in no bulk file
and no database table and had to be asked for one bill at a time --
`docket_pages/` holds 8,607 of them, 1,072 of those 2016.

**The narrative is rule-based and inspectable.** Every sentence on the site can
be traced to a docket line and a rule in `narrative.py`. When the Clerk says a
sentence is wrong, there is a specific rule to fix, and the fix applies to every
bill that shares the shape. A model would give neither.

**Ground truth exists and is wired to a scorer.** 35 proceedings a person timed
by hand, and `probe_alignment.py --truth --candidate` scores any method against
them in a second. Nothing about timestamps should ever again be tuned without
that number moving in the right direction. It is the single most valuable
artefact in the repository, and it lives in a spreadsheet that has been lost
twice.

**The site is static.** Files on a CDN, nothing to go down at two in the
morning, and exactly one write-only Function that no page waits on --
`functions/api/report.js`, behind the "report a problem" box. That constraint
is also what forces the file-count problem below, but it is the right
constraint.

**`preflight.py` builds the whole site on a fixture.** Most of its checks exist
because of a specific failure; it has caught stamp mismatches three times and a
dead-zone error once. Run it for the current count -- a number written here
would be wrong within a day, and was.

**A person can overrule a generator, in files the generators cannot touch.**
Five files are a person's: `ground_truth.csv`, `review/checked.jsonl`,
`bill_notes.json`, `officials.json` and `member_corrections.json`. The last
exists because a generated NAME can be
wrong and nothing downstream can tell -- `resolve_members.py` deduces who a
member id is by intersecting a saved roll call page with the ids that voted,
and one of its 676 deductions put the wrong person's name on 4,250 ballots.
The file it writes is regenerated on every run and is not tracked, so the
correction had nowhere to live that survived a build. Corrections carry their
evidence beside them, `build_data.py` applies them last over every generated
name source, and preflight fails if any generator opens the file for writing.

---

## Three things about the pipeline that are easy to get wrong

Each learned by getting it wrong.

**The record travels inside the bill's page, so `build_bill_pages.py` must run
after `build_site_v2.py`.** All but a few hundred of the 33,683 records are
embedded in the page rather than fetched; only those over `INLINE_CAP`
(100 KB, `build_bill_pages.py:141`) keep a file, and the step prints the split
when it runs. The split moves with the data, so read it off the run rather
than off this line. So rebuilding the
site alone leaves every bill page carrying the record as it was, and the change
you just made is in `site/bills/<year>/<id>.json` where nothing reads it. The
symptom is a page that looks stale while the JSON beside it looks right.

**`build_bill_pages.py` owns `sitemap.xml`, so running it alone truncates the
sitemap.** It writes the file rather than appending to it, and the legislator,
committee and town pages are added by steps that come later. Running it on its
own to pick up one change dropped every `/legislator/` page from the sitemap,
which preflight caught. **Use `build_all.py --local`** unless there is a reason
not to; the step order is the point of it.

**A relative `href` on any page built through `shell.py` resolves against the
site root, because `bills.html` carries `<base href="/">`.** That is not a
quirk to remember -- 462 links shipped broken through it, live from the 12th
of September until the 16th. preflight now resolves every internal link a
generator writes, honouring `<base>`, so a new generator cannot repeat it.

---

## proceedings.csv across terms, measured 10 September

> **Done.** `build_manifest.py` needed no change -- `--docket` names the term
> -- and `build_proceedings.py` now reads every `verification_manifest*.csv`.
> **All nineteen terms have a manifest**, 1989-1990 to 2025-2026. 2017-2018
> landed as hearings without video, as did every term before it, because the
> House streamed nothing until May 2020. 2019-2020 straddles that date:
> hearings across the whole term, with video on its rows from the 14th of May
> 2020 onwards.
> Run `python3 handoff.py` for the row and recording counts; the pair quoted
> here went stale twice in a week. "The order that followed" below is spent --
> its step 5 in particular, which sent the next person to the calendars for
> work the database dump had already put on this disk.

When this was written, `proceedings.csv` held 9,762 rows and 9,761 of them were
2025-2026: every recording, every stated boundary and every timestamp on the
site was one term, and this was the largest single thing the record was
missing. What follows is what it took, measured rather than estimated.

### It is not gated by the General Court fetches

That was the assumption and it is wrong. The two biggest pieces are sitting on
this disk already.

`docket_parser.parse_proceedings` takes a docket and returns structured
proceedings -- bill, body, kind, scheduled date, scheduled time, venue,
committee -- and it does not care which term's docket it is given. Run today:

    Docket_2023-2024.txt   23,808 rows ->  7,379 proceedings
    Docket_2017-2018.txt   21,984 rows ->  6,431 proceedings
    Docket.txt (current)   25,270 rows ->  7,115 proceedings

2023-2024 is a **larger** term than the one the site currently carries, its
docket has been on disk for days, and its 1,648 recordings are already in
`channel_index_full.json`. Nothing about it waits on anything.

Recordings exist from May 2020 onwards and only then:

    2019-2020    139        2021-2022  1,222
    2023-2024  1,648        2025-2026  1,419

So 2,870 recordings across 2021-2024 have no proceeding pointing at them.
That is twice what the current term has.

### What actually gates it: one number per video, from YouTube

`build_manifest.py` needs `start_eastern` -- when the stream actually began --
because the schedule offset is the scheduled time minus that. It reads it from
`videos_*.csv`, and the eight of those on this disk are all 2025 and 2026.
`channel_index_full.json` carries `id`, `published` and `title` and nothing
else, and `published` is not the start: a 09/09/2026 meeting is published the
evening before.

`fetch_channel_index.py` pulls `actualStartTime` from `liveStreamingDetails`,
**fifty ids per call**, so 2,870 videos is about sixty requests. It needs a
YouTube Data API v3 key. That is the whole gate, it is against YouTube rather
than the General Court, and it takes minutes.

### The order that followed from that

Spent, and worked through term by term. Two things in it are still live:

- **`watchers/docket_chain.py` still exists and is superseded by
  `watchers/gc_lane.py`; do not start it** -- `watchers/README.md` says why.
  Everything asked of the General Court now goes through that one lane, which
  works `watchers/gc_lane.queue` holding `archive/.lock`.
- **The calendars stay the second source, and the only one for what a docket
  does not carry.** All 1,580 House calendar PDFs for 1997-2026 are on disk
  with text extracted, 100%. `calendar_meetings.py --check` reads the
  (bill, day) pairs out of them at no cost -- 61,767 across 2,107 committees on
  10 September, 61,543 across 1,058 on the 17th after committee-name variants
  were merged, so run it rather than quoting either. Senate calendars: 1,604
  PDFs, 984 with text, 620 still queued.

The step that was wrong is worth one line. It said no docket was fetchable
before 2015 and that the calendars were therefore the only source for
1997-2014 -- 1997 because that is where the House calendars start, which left
1989-1996 with no source at all. It sent the next person to build a calendar
parser for work that was one `build_manifest.py --docket` run away. The SQL
host's bulk dump had already overtaken it: `db/` carries the Docket view,
`docket_from_db.py` turns a slice of it into the shape `narrative.py` already
reads, and **fifteen `Docket_db_*.txt` files are on disk**, from
`Docket_db_1989-1990.txt` through `Docket_db_2015-2016.txt`, plus
`Docket_db_2015.txt`. Every one of those terms
has been through `build_manifest.py`.

### The decisions to make before writing any of it

- **A third producer, or a term-aware first one.** `build_proceedings.py`
  merges two sources today, and its whole reason for existing is that reading
  them separately made five tools silently drop the floor in one day. Adding a
  calendar producer alongside `build_manifest.py` repeats that mistake in a
  new place. Better: `build_manifest.py` becomes term-aware and takes the
  calendar as a fallback source for terms with no docket, so there is still
  one producer of committee proceedings.
- **The two sources disagree, and by a known amount.** Measured against the
  docket, the calendar parse agrees on kind 98% of the time, on room 100%,
  and on time 88%. For 1997-2014 there is no docket to prefer, so the calendar
  is the record and the 12% is unmeasurable there. That belongs on the page as
  a stated limit, not buried.
- **The shrink guard.** `build_proceedings.py` refuses to write a smaller
  table than last time without being told it may. Going to 60,000 rows is
  growth and is fine, but a `--term` run that rebuilds one term must merge
  rather than replace, or the first partial run destroys the rest -- which is
  the failure this project has had four times, enumerated under *2. Tools that
  write complete files, run on subsets* below.
- **Timestamps will lag, though not for the reason this expected.** When it was
  written, captions were the bottleneck: 1,278 recordings had them and almost
  all were current-term. **4,296 of the 4,429 recording folders in `work/` carry
  captions this can read** now, so that conclusion has inverted. A new term
  still arrives with hearings, rooms, dates and a recording link but no stated
  boundaries until transcription catches up. That is honest and the page
  already draws it.

### What it is worth

The current term was 9,762 rows when this was written. The dockets alone added
**30,400 more for 2015-2024**, three of those terms with recordings behind
them. The calendars add tens of thousands more for 1997-2014 without
recordings. The site goes from one term of hearings to thirty years of them,
and the two terms with the most recordings are the ones nothing is waiting for.

## The cleanup pass: scope, measured 10 September

Written before the pass so the pass is execution rather than deliberation.
Everything here is measured, and the decisions at the end are already made.

### What the modules actually weigh

Measured 17 September. Every figure moved in the week since the pass was
planned and two of them more than doubled -- `preflight.py` and
`build_proceedings.py`; the *shape* of the problem is what the pass was about,
and the shape has not changed:

    build_site_v2.py   3,888     main                 533 lines
    preflight.py       9,767     build_bills          346
    app.js            ~3,900     station_for_proceeding 181
    probe_alignment.py 2,039     committee_reports    136
    narrative.py       1,629
    segment_markers.py 1,071
    review.py          1,175
    build_manifest.py    512     main                 268
    build_proceedings.py 408     main                  95
                                 from_floor_index      56

`build_bills` was split on 10 September, 544 lines to 294 in nine functions,
each step verified byte-identical across 34,114 files. It has since grown back
to 346, which is what a function does when it is the right size to add to.
`main` is the longest function in the file again -- **533 lines**, up from the
468 this section first recorded -- the same problem one door along, and it is
CLAUDE.md's first item once more.

### In scope

> **Read the next section before acting on this one.** Two of the decisions
> below were overturned on the same day by reading the code rather than
> remembering it: `build_manifest.py` needed no `--term` flag and no change at
> all, the cross-term video hazard was measured and does not exist, and the
> shrink guard was built onto the whole-table read instead of as `--term` merge
> semantics. So "the decision, so it does not get relitigated" below is not the
> decision that shipped.

**1. `build_manifest.py` becomes term-aware.** The agreed shape: one producer
of committee proceedings, taking a term and its docket, with calendars as a
fallback source later for terms that have no docket. `main` is 191 of its 434
lines and is where the term has to thread through. The video side is mostly
argument plumbing -- `--videos` already accepts a glob.

**The hazard to design against, and it is the whole risk of this step:** the
matcher joins a bill to a video by committee and date. Point it at
`videos_*.csv` with every year present and a 2023 bill can take a 2025
recording on a same-day, same-committee coincidence. The term must filter the
video set, not merely label the output.

**2. `build_proceedings.py --term` merges rather than replaces.** It refuses
today to write a table smaller than the last one without being told it may,
which is the right instinct and the wrong granularity once terms arrive one at
a time. The decision, so it does not get relitigated: a `--term` run rebuilds
that term's rows and keeps every other term's untouched, and the shrink guard
applies **per term** rather than to the whole file. A full rebuild stays the
explicit flag it is now. This is the failure this project has had four times
and it is five lines to prevent.

**3. Land 2023-2024.** `Docket_2023-2024.txt` gives 7,379 proceedings, and its
1,648 recordings now have start times -- 1,643 of them, 100% of what YouTube
holds. Nothing about this waits on a fetch.

**4. Two cheap correctness items.**

- `probe_alignment.py` defined `hms` twice and the second shadowed the first.
  **Fixed 10 September**: the first was unreachable, and its fourteen callers
  -- word-level caption times that wanted sub-second display -- had been
  getting the coarse `12m 05s` form since the second was written. Renamed
  `clock()`.
- Seven tools carry `--manifest default="verification_manifest.csv"`:
  `align_all`, `apply_markers`, `fetch_testimony`, `probe_alignment`,
  `score_alignment`, `transcribe_and_align`, `verify_batch`. Six of them open
  whatever `--manifest` names, so run with no flag they open that exact file:
  real coupling rather than a stale pointer, and only `fetch_testimony` never
  reads the value it declares. `ground_truth.py` is an eighth reader, falling
  back to the literal name when the flag is absent, and `preflight` opens it
  too. `build_proceedings.py` is the one that has moved -- it globs every
  `verification_manifest*.csv` rather than naming one -- and its own docstring
  says the intermediate goes away once every reader has followed. These
  defaults are the readers that have not.

### Explicitly not in scope

Saying so is what keeps a cleanup pass from becoming a rewrite.

- **The 1997-2014 calendar path.** A different source with a different error
  profile -- kind agrees with the docket 98%, time 88% -- and for those years
  there is no docket to prefer, so the 12% is unmeasurable. That is a decision
  about what the site may claim, not a refactor.
- **Captions and timestamps.** 4,296 of the 4,429 recording folders are
  captioned (910 of 915 when this was written, which was one term's
  denominator); that path is fed by transcription, not by more fetching.
- **The site's rendering.** `app.js` is about 3,900 lines and not the
  bottleneck.
- **`preflight.py` at 9,767 lines.** It is long because it is 161 checks, which
  is the good kind of long.

### Decided in advance, so the pass does not stop to argue

- One producer, term-aware. Not a sibling producer per source.
- `proceedings.csv` keeps its shape; it already carries a `term` column.
- The shrink guard becomes per-term.
- `ground_truth.csv` and `review/checked.jsonl` are not touched by anything.
- Every change is scored with `probe_alignment.py --truth` before it ships,
  and `--no-bench` gives the number comparable with anything recorded before
  9 September.

## The pass, step by step, planned 10 September

Planned by reading the code rather than by remembering it, which changed the
answer twice. Both corrections are below, because a plan that quietly drops
its own earlier advice is worse than one that says what it got wrong.

### Two corrections to what the section above recommends

**`build_manifest.py` needs no `--term` flag, and no change at all.** It takes
`--docket` and `--out`, the docket carries the term, and that is the whole of
term-awareness. Proved rather than argued:

    python3 build_manifest.py --videos "videos_*.csv" \
        --docket Docket_2023-2024.txt --out verification_manifest_2023-2024.csv

    Wrote verification_manifest_2023-2024.csv: 7,019 rows
    5,604 rows have a direct watch link

**And the cross-term hazard is not real.** The worry was that a 2023 bill
could take a 2025 recording on a same-day, same-committee coincidence. It
cannot: the matcher filters proceedings to dates that have videos, and a date
carries its year, so `2023-03-07` cannot match a video from `2025-03-07`.
Measured on those 7,019 rows: **0 matched to a video outside 2023-2024, and 0
whose video date differs from the scheduled date.**

**`build_proceedings.py` must not get `--term` merge semantics.** That was the
recommendation and it is the wrong shape. It would make a writer that runs on
one term and rewrites a file holding all of them, which is precisely the
failure this project has had four times -- the manifest lost the 35
hand-marked times exactly that way twice, `build_all.py` halved it a third
time with a narrower video set, and `segment_markers --transcript X` once
discarded 842 recordings' results. A per-term shrink guard is a guard against
a hazard that does not need to exist.

Build the table whole instead. One manifest per term on disk, and
`build_proceedings.py` reads all of them every time. No writer ever runs on a
subset, the existing shrink guard keeps working unchanged, and there is no
merge logic to get wrong.

> **One half of this was wrong, and the code now says so.** Reading every
> manifest stops a *writer* running on a subset; it does not stop a *rebuild*
> silently running with a manifest missing. Dropping one term's manifest loses
> its rows while keeping most of the table, which sails through a whole-table
> guard that only refuses a fifth. `build_proceedings.py` carries both now: the
> whole-table guard at line 353 and a per-(term, source) row count at line 365,
> each released only by `--allow-shrink` (line 320), and
> `preflight._proceedings_term_shrink` holds them there. So the per-term guard
> arrived after all -- on the read, which is the safe half, not on the write.

### The steps

**0. Fix the one bug that must not be running during a refactor.**
*Done 10 September.* `build_manifest.py` downloaded `Docket.txt` from
gc.nh.gov when `--docket` was omitted and the file was absent:

    if not Path(docket_path).exists():
        print("Downloading Docket.txt (this is a few MB)...")
        urllib.request.urlretrieve(DOCKET_URL, docket_path)

It is a `build_*` script making an unguarded network call to the address that
has blocked this one twice. The whole permission rule rests on the naming
contract -- `fetch_*` touches the network and is asked about first, everything
else is free to run -- and this breaks it silently. It does not fire today
because `Docket.txt` is on disk; it fires in a clean checkout, which is the
state a refactor is most likely to create. Make `--docket` required, or print
the fetch command and exit.

**1. `build_proceedings.py` reads every manifest.** *Done 10 September.*
The only code change in the pass. `--manifest` takes a glob, defaults to `verification_manifest*.csv`,
and `from_manifest` is called once per file. Roughly ten lines in a 193-line
file. Nothing else in it changes: the dedup key is already
`(bill, date, kind, video_id)` and a date carries its year, so two terms
cannot collide.

**2. Write the per-term manifests.** No code. One `build_manifest.py` run per
docket on disk, each to its own `--out`. 2023-2024 is done and sitting there.

**3. Rebuild and check the number went up.** 9,762 rows now; 2023-2024 alone
adds about 7,019 before dedup against the floor index. The shrink guard is
satisfied by growth and needs no flag.

### What happens downstream, checked in advance rather than discovered

- **Stations are already term-keyed.** `build_site_v2.py` builds
  `procs[(r["term"], r["bill"])]` and `floor[(r["term"], r["bill"])]` and
  reads them the same way. The "stations leak across terms" bug that an older
  plan flagged has been fixed, and it was the largest risk in this whole
  change -- with one term in the table it was latent, and a second term would
  have made it live on every page.
- **2023-2024 arrives without timestamps, and that is correct.** Its
  recordings are almost all uncaptioned, so no boundary can be stated and the
  stations carry a date, a room, a committee and a watch link. The page
  already draws exactly that for a proceeding it cannot place.
- **No new files.** More stations on pages that already exist. The 100,000
  file cap is not touched.
- **`segment_markers.py --all` will start seeing 2023-2024 recordings.** It
  reads captions and skips what has none, so it costs a pass over the
  proceedings table and nothing else.

### The other things to fix while in there

The two correctness items above -- the shadowed `hms`, and the seven stale
`--manifest` defaults -- are the ones a pass like this should look for, and
they were the only ones. Once there are several manifests, a default naming
one of them is actively wrong: decide per tool whether it is superseded or
should read `proceedings.csv`. One more:

- **`--keep-marks` is not vestigial; its help text is.** Every manifest this
  writes carries `observed_start` and `observed_end` -- all nineteen on disk
  have both columns, and `verification_manifest.csv` has 35 rows filled, put
  there from `ground_truth.csv`, which outranks anything in an old manifest
  (`build_manifest.py:709-733`). The other eighteen carry the columns empty,
  because every mark names a current-term video. A flagless rebuild also falls
  back to the file it is about to overwrite, which is what makes forgetting the
  flag harmless, so what the flag is actually for is reading marks out of some
  *other* file. The help still says they "are lost on every rebuild" without
  it; that is the sentence to fix.

### What said the pass worked

    python3 preflight.py                     green (76 checks then)
    python3 probe_alignment.py --truth       47 marks, candidate median 0m 01s
    python3 probe_alignment.py --truth --no-bench   35 marks, median 0m 01s
    python3 check_site.py                    ready, 49,304 files of 100,000

Those four commands are the check on a change of this kind. The numbers beside
them are that day's and are kept for shape rather than currency: `preflight`
declares 161 checks now, `proceedings.csv` reaches all nineteen terms, and
`STATE.md` has the file count -- which went *down*, because records moved
inside their pages.

## Sitting days, built 19 September

A page for every day the House sat, 806 of them, at `/session/H/<date>`.

**The record and the colour come from different places, and that is the whole
design.** `narratives.json` already holds 79,096 floor events across all
nineteen terms, each carrying the bill, the motion, who moved it, whether it
carried, how it was voted and the journal page it is printed on.
`session_days.py` reads them and contains no parser. Only what the record
cannot hold -- who spoke, and the text of a printed debate -- is parsed out of
the journal, by `journal_days.py`. A page that loses the journal entirely is
still true, and 333 of the 806 do lose it, because the journal starts in 1997.

**Why not parse the journal for the record too.** It was measured before it was
attempted. Forty candidate patterns were put to adversarial verification
against the 1,064 journal files and **thirty-six were refuted** -- the
constructs are real, but they wrap across lines, their eras are wrong, and the
regexes over-match. One proposed day-boundary pattern matched 1,076 lines of
which 561 were day starts. The lesson that survived is that every pattern must
be matched on JOINED text, never on lines.

**The ordering is the journal page.** A floor action carries no clock, so there
is no time to sort by. The `HJ 6 P. 31` citation is the chamber's own sequence
and it orders a day exactly: 247 actions on 5 March 2026 across pages 2 to 140.

**The motion is the heading.** Of 2,934 anchored attributions, 655 -- 22% --
read in plain English as the opposite of the truth, because 320 members "spoke
in favor" of an Inexpedient to Legislate motion, which is an argument to kill
the bill. So a speaker is never listed under a bill, only under a motion, and
987 attributions that cannot be tied to one motion are named without a side.

**Which side prevailed is the clerk's MA or MF, never the larger number.** On
9 April 2026 the House recorded 186 yeas to 169 nays and the veto was
sustained, an override needing two thirds. Inferring the winner from the tally
gets every override and every constitutional amendment backwards.

**What is not built, and why.** Senate sitting days. Across all 491 Senate
journal files "spoke in favor" occurs four times and "spoke against" twice, and
every one is ordinary English inside a speech rather than a marker -- the
Senate journal does not record who spoke on which side. The Senate's RECORD is
in `session_days` already (774 days), so a Senate page carrying bills, motions
and votes without a debate section is a small job; it is separate from this one
rather than half of it.

**Numbers, measured on the build of 19 September.** 806 pages; 473 carry a
journal narrative; 15,378 attributions found corpus-wide of which 9,222 are
tied to a specific vote; 298 printed debates holding 5,507 speeches; 580
remarks under unanimous consent; 13,523 of 18,096 speaker mentions (75%)
resolved to a member page, the rest being surnames shared inside one chamber
and deliberately left as text.

**A defect this uncovered.** The calendar was calling committee meetings the
floor. A row with no committee was labelled "House floor" or "Senate floor",
and only 3,969 of the 8,339 committee-less rows in `proceedings.csv` are floor
debate; the other 4,370 are hearings, work sessions and committees of
conference whose committee the docket did not record. Fixed in
`build_calendar.floor_name`.

## What is structurally wrong

Ranked by what it has actually cost, not by how it looks on paper.

### 1. Floor and committee data live in two different worlds

> **Fixed 5 September — this is the failure the fix was built for, and it is
> kept because it is the best argument in this document for one table.**
> `proceedings.csv` is that table: `build_proceedings.py` produces it from
> every `verification_manifest*.csv` and the floor index, `proceedings.py`
> reads it, and floor debates sit in it as `kind = floor debate`. Nothing may
> add a sixth reader of the old two files. Read below in the past tense.

`verification_manifest.csv` holds committee proceedings, one row each.
`floor_index.json` holds floor debates, keyed by bill with the recording inside.
Different producers (`build_manifest.py`, `build_floor_index.py`), different
shapes, different keys, and every tool that reads one has to be taught the
other separately.

**Five times in one day** a tool silently excluded the floor: `--suggest` could
not list floor recordings, `--transcript` could not read them, `fetch_captions`
refused them, `segment_markers` skipped them after the clerk's script had been
added specifically for them, and `build_site_v2` ignored their markers after
the markers had been wired in for committees. Each presented as a different
bug. Each was the same bug.

**Fix: one proceedings table.** One row per (bill, date, kind, recording),
whether it is a hearing, an executive session or a floor debate, produced by
one step, read by everything. Floor debates get `kind = floor debate` and the
roll-call clock fields where they exist. The split was an accident of build
order, not a design.

### 2. Tools that write complete files, run on subsets

> **The rule is in force.** `build_proceedings.py` reads every
> `verification_manifest*.csv` on every run, so no writer here sees a subset;
> it refuses a table a fifth smaller than the last (line 353) and separately
> refuses a rebuild that drops a whole (term, source) (line 365), both released
> only by `--allow-shrink`. Five hand-made files live where no generator
> writes, and `preflight` fails if a `build_*` or `fetch_*` script opens one.
> Kept because the rule is only as good as the next writer somebody adds.

`build_manifest.py` overwrote the manifest twice, taking the hand-marked times
with it. `segment_markers.py --transcript X` wrote a candidate file containing
only X and discarded 842 recordings' results. `build_all.py` re-ran the manifest
build with a narrower video set and halved it. In every case the tool did
exactly what it was asked and nothing warned.

The pattern: a script whose output is "the file", invoked in a way that covers
part of the input. The fix applied each time was to merge rather than replace,
and to carry forward what was already there. That should be the default for
every writer of a derived file, not a patch applied after each loss.

**Fix: writers merge; a full rebuild is an explicit flag.** And anything a
person produced by hand -- the 35 marks -- lives in its own file that no
generator ever writes.

### 3. Bill numbers repeat every two years, and nothing knows it

**Partly done, 6-7 September**, one file at a time. What is worth keeping is
why each mattered and what the conversions turned up.

`rollcalls.json` is `{term: {bill: [votes]}}` and two `preflight` checks hold
it there: one builds the fixture with the same bill number in two terms and
fails if their votes merge, the other fails the build outright if it is handed
the old flat shape rather than reading it and finding nothing. The member-vote
key gained its year at the same time, because vote sequence numbers restart
each session and "H-112" named two different roll calls the moment 2025 arrived
beside 2026 -- 2025's HB324 and 2026's CACR10.

`narratives.json` mattered most for reach: status, stages, events, the dating
of every committee report, the floor index and the amendment numbers all read
through it. It refuses the flat shape rather than producing 2,234 bills with no
history in them.

`build_feeds.py` was the largest single place a bill number still stood in for
a bill: 2,233 of the site's 8,045 files. A bill with no filing year collapsed
`feed/bill/<year>/<id>.xml` to `feed/bill/<id>.xml`, which the next term's bill
of the same number would land on top of. It now gets no feed and is named in
the output.

`committee_reports.json` and `senate_reports.json` show what the constraint
really is. Neither could change shape without being rebuilt in the same commit,
and both could be: the Senate's come from the database, and
`fetch_committee_reports` gained `--offline`, which re-reads the 82 calendars
already on disk and makes no request. Output-neutral across all 2,234 bills.

`data/bills.json` sits at the very top of the pipeline -- the loop in
`build_bills` runs over it, so a bare bill number there put two terms' bills
under one key -- and converting it turned up the bug the whole exercise exists
to prevent: `yearOf(id)` in `bills.html` searched the entire index for the
first row with that number, so opening the 2023 HB1 fetched the 2026 one's
record and showed it under the 2023 heading.

`bill_text.json` and `bill_status.json` closed the gate. Both were held back
because their writers need the network and reshaping one without regenerating
it leaves the site unbuildable. That turned out to be the wrong way round: the
writers could be taught the term first and the files migrated in place, with
the readers tolerating either shape, so no fetch was needed at all. The whole
site rebuilt byte-identical.

The general shape is now in `proceedings.py`, so the next file to convert is
half a dozen lines rather than a judgement call each time:

- `per_term(data, term, current)` reads one term and tolerates the flat shape,
  handing an archived term **nothing** out of a file that has not been
  converted -- the wrong term's sponsors being worse than none.
- `in_term(data, current_term)` is its counterpart for a writer, so a run over
  one term keeps every other. This is the failure that cost the manifest its
  hand-marked times twice, and `--reparse` is where it hides: rebuilding from
  a cache that holds one term's pages must not delete the terms it cannot
  rebuild.

`preflight` holds both directions: an archived bill must read its own term's
status and text, and must not read the current term's. A lookup that ignores
the term passes the first half by accident, which is why the check asserts the
second.

`data/sponsors.json` is what makes a search for a prime sponsor work before
2025: 1,865 of the 1,996 bills of 2023-2024 carry one. An archived term's
sponsors come from that term's slice of `bill_status.json`, which is why this
had to wait for that file.

The first attempt at the split was the bug the keying exists to prevent, which
is worth keeping written down. It built a bill -> term map from
`data/bills.json` and divided the flat dict with it -- but a bill number is in
more than one term, so every repeated number took whichever term the loop
reached last. 1,849 of 2,220 bills' sponsors landed under 2023-2024, read out
of the 2025-2026 files, and **the site still built byte-identical**, because
`build_site_v2` then found nothing for the current term and drew no sponsors
rather than wrong ones. Silence again. `preflight` now asserts that the term
whose own files were read has sponsors on more than 75% of its bills.

**Still flat: `testimony.json`**, and it is superseded by `testimony_db.json`,
which is keyed on the term already. It is read through the `own` guard in
`build_site_v2`, so an archived bill gets nothing from it.

**Fix, for what is left: `(term, bill)` everywhere.** `setup_archive.py` and
`probe_archive.py` already sketch this. The year-keyed journal and calendar
citations were part of the same job without my recognising it.

### 4. The deployment has a file cap, and the archive hits it at five terms

> **Resolved, 9 September.** The plan is Pro, so the cap is 100,000. And a
> bill is one file rather than two: its record travels inside its own page,
> except for those over 100 KB which keep a file the page points at. All 19
> terms are live and the site is under half the cap, where the reasoning below
> predicted it breaking partway through the third term and the arithmetic
> below predicted 79,877 files. The difference is the inlining: an archived
> term costs roughly one file per bill rather than two. The reasoning is kept
> because the measurement of what each term costs is still the right way to
> think about it, and because the trap it names about paid plans is real.
> `STATE.md` has the current count, and the nightly's gate line prints it on
> every run.

**Measured on the two-term site, 6 September:** 12,013 files of 20,000.

| | files |
|---|---|
| the current term | 4,468 |
| the 2023-2024 term | 3,992 |
| everything shared -- legislators, towns, feeds, the shell | 3,553 |

An archived term costs **3,992 files**, so at 20,000 there was room for two
more -- 19,997 files across four terms -- and the cap broke on the fifth term
overall. That is further off than the one-term estimate this section used to
carry -- 8,045 files, 6,701 a term -- which was wrong in the direction that
matters: it counted a per-bill RSS feed for every term, and an archived term
has none, having no docket to report.

The cap is real for the archive as a whole all the same. Nineteen terms back to
1989, at two files a bill, is roughly 76,000 files. The options were three:

1. **Fewer static pages for older terms.** Dropping `bill/<year>/<id>.html`
   for archived terms halves the cost to ~2,000 a term and buys six archived
   terms on top of the 8,021 the shell and the current term already cost. It
   costs those bills their own indexable address, which is the entire reason
   those pages exist.
2. **One file per term rather than per bill**, read by the search page.
   Roughly ten files a term, so every term ever fits. Archived bills then have
   no address of their own at all, and the reader downloads a term to read one
   bill.
3. **Per-bill data in R2 behind a Worker.** No cap, at the cost of the
   constraint the whole site is built on: files on a CDN, no runtime.

**Settled 7 September: pay Cloudflare instead**, which raises the limit from
20,000 files to 100,000. Two things to know, and the second is the trap: it
needs the environment variable `PAGES_WRANGLER_MAJOR_VERSION=4` set in the
Pages project, and it is the Pro *zone* plan, not Workers Paid -- several
people have reported the 20,000 limit still enforced after upgrading the
latter.

The arithmetic, at 3,992 files per archived term and 8,021 for the shell plus
the current term: 20,000 buys three archived terms and reaches back to
2019-2020; 100,000 buys twenty-three and reaches back to 1979-1980. Every term
the General Court's database can supply -- 1989 to 2026, nineteen terms, which
is eighteen archived ones on top of the current -- is **79,877 files with
20,123 to spare.** So the cap stops being the constraint, and options 1 to 3
above stop being forced choices.

What replaces it as the constraint is **data**, not files. See the section on
what a year's page actually carries, below.

A fourth looked promising and is not: **a page only for bills that were
actually taken up.** Measured on the current term, where the record is
complete, **2,220 of 2,234 bills have a hearing on the record -- 99.4%**, and
2,118 reached the floor (`floor_index.json`), though only 450 of those carry a
roll call. New
Hampshire gives every bill a public hearing, so "the ones anybody acted on" is
very nearly all of them and this saves nothing.
Worth writing down because it is the option that sounds best before it is
measured: on the 2023-2024 term it looks like a 79% saving, but only because
that term's hearings have not been fetched yet and 416 roll calls are all the
site currently knows about. Selecting on what has been *fetched* rather than on
what *happened* would have been a rule that tightened every time the data got
better.

### 5. Long functions where declaration order is load-bearing — one left

**One of the three is gone rather than split.** `build_bill_pages.py` was 909
lines rendering every bill a second time in Python, beside `app.js` rendering
the same bill from the same JSON in the browser. It is 356 lines now and
renders no bill: a bill's page is `bills.html` with one bill open, and what
those lines do is the shell, the no-JavaScript fallback, `sitemap.xml`, and the
decision whether a record travels inside its page or keeps a file. That is why
a bill reached from a legislator page used to look unlike the one you had been
reading, and why a fix to one view never reached the other.

The audit before deleting it is the part worth keeping. `app.js` read neither
`d.notes` nor `d.facts`, so the swap would have silently removed the
explanatory notes from **2,065 of 4,230 bills** and the "On the record" status
table from **all 4,230**. Both are in `renderSummary` now. A refactor that
deletes a renderer has to be preceded by an inventory of what only that
renderer drew, and reading the two files side by side is not enough -- the
notes were invisible because nothing in `app.js` mentions the word.


> **Both halves of this are done.** `renderDetail` is 82 lines in `app.js`,
> calling one function per tab -- `renderSummary` 42, `renderVotes` 36,
> `renderBillText` 94, and `renderHearings` 223, which is the one that has
> grown back far enough to be worth watching. `build_bills` was split as
> described above, and `station_for_proceeding` and `station_for_floor` exist
> as top-level functions. Kept as written because the failure it describes is
> the one the splits were done to stop.

`renderDetail` in `bills.html` was 472 lines and one function, with 26 `const`
declarations. Three times in a day a template literal read one of them before
its line ran, and the page died with the data already in hand. A lint that skips
template literals cannot see it; the runtime check only caught it once
extended to the focused view, which is the branch where two of the three lived.

`build_site_v2.py` was 1,672 lines and its `main()` built every station,
document, sponsor and amendment for every bill in one pass. The floor-marker
bug in item 1 happened because the committee-station code and the floor-station
code are 90 lines apart in the same function and I changed one.

**Fix: one function per tab.** `renderVotes(d)`, `renderHearings(d)`,
`renderBillText(d)`. Each small enough that order is obvious, each testable
alone. The same for `build_site_v2`: `station_for_proceeding()`,
`station_for_floor()`, called from a loop.

### 6. Every text-matcher reports the window's start as the match's time

Five times: titles 45 seconds early; an opening logged at the previous bill's
closing; phrases collected from twenty seconds before the words they described;
a 40-word chunk spanning a ten-minute silence. Each was a separate function
that built its own window and returned its own start.

**Fix: one primitive.** `find_in_transcript(words, pattern) -> [(time, match)]`
that joins the words once, searches once, and maps character offsets back to
word times. `segment_markers.find_markers` does this correctly now; nothing
else uses it.

### 7. Silence is indistinguishable from failure

A fixed progress interval of 200 on a 20-row run; a print with no newline;
output captured until a step finished; Whisper killed at 15 minutes and looking
like a hang; a build that finished normally while publishing a site with no
committee hearings. Five separate instances, each fixed separately.

**Fix: one progress helper** (`Ticker` in `fetch_bill_text.py` is the good
version), and a rule that a build step which produces a smaller output than
last time stops rather than continues. `nightly.py` has the sanity gate;
`build_site_v2` did not have it for the manifest.

### 8. The parsers have no tests

> **Done.** `tests/test_markers.py` holds the phrasings that were read out of
> real recordings -- **51 that must match and 10 that must not**, counted on
> 17 September, against the 47 and 8 this line first carried -- and `preflight`
> runs it. Kept because the reason it was needed is the reason it must be
> maintained.

Every fix was verified by a fixture written in a heredoc and thrown away.
`OPEN_RE` has been through nine revisions and the phrasings it must match are
scattered across those heredocs and `TRANSCRIPT_MARKERS.md`. When someone
changes it in six months, the only way to know what broke is to re-run the
whole marker pass and score it.

**Fix: a `tests/` directory** with the real phrasings as cases, grouped by
where each was found: the seven read by hand, the seven from `--gaps`, the
thirteen from `--phrases`, the five floor forms, the five things that must not
match. Twenty lines each. That is the 32 and 5 the file was first committed
with; the counts in the note above are today's. `preflight` runs them.

### 9. The cache keys on patterns, not on logic

> **Done.** `segment_markers.pattern_signature()` hashes the whole tokenised
> module, comments stripped, and its docstring quotes this section back.

`segment_markers` cached per recording, keyed on a hash of the regexes. Change
a regex and everything re-runs; change the dedupe rule, the window size or the
bill-matching threshold and nothing does. That is the second such trap in one
file. A hash of the whole module's source is crude and correct.

### 10. Per-bill fetching does not scale and has already caused harm

Bill text is 2,234 requests a term, at four seconds each. The address has been
blocked twice -- once for probing, once for two fetches at once.
Fifteen terms of text is thirty-seven hours of continuous requests for a
document that is one link away and better in its original form.

**Fix: fetch text for the current term only, and only bills whose docket has
moved since last time.** `narratives.json` knows the last action date. A
nightly becomes fifty requests, not two thousand. Old terms get a link.

**Better fix, found 6 September: the General Court's own SQL host has all of
it.** `LegislationText` holds the full text of every version of every bill --
"Introduced", "As Amended by the House", "Version adopted by both bodies",
"CHAPTERED FINAL VERSION" -- as HTML, in one query. `Legislation` holds the 48
columns behind the bill status page, statuses with their dates included.
`sponsors` holds them on the roster's own PersonID rather than the web member
id the scrape returns. That is 2,234 requests to the server that blocked this
address twice, replaced by one SELECT to a service published for public use.

Two things done this way already: 2025's roll calls, which the General Court
publishes for the current session only and which the site therefore did not
have at all (197 bills gained a recorded vote), and the Senate's committee
reports (1,254 bills, 1,096 with the committee's reasoning, where the site had
been showing a bare docket line).

**The database carries the bill-text link too, measured 17 September.**
`text_pdf` is built from the `id` and `sy` of the legacy bill-text URL, and
those two are `Legislation.legislationID` and `sessionyear` -- columns of the
table `fetch_status_db.py` already queries, though not yet in its SELECT.
Across all 2,234 bills of the current term the scraped `text_id` equals
`legislationID` and `text_year` equals `sessionyear`, none differing and none
absent. The equality is not circular: `fetch_status_db.py` leaves all three
fields out of what it fills, and `fetch_bill_status.py` reads them out of the
page's own link.

This paragraph used to say the link was the one thing the database lacked, on
the strength of `LegislationText.LegislationTextID` being a different id space.
It is a different space -- HB1442 is `legislationID` 1937 and has seven
`LegislationTextID`s, 23441 among them -- but the legacy URL never used that
id. It used 1937. The comparison was against the wrong column, and it made an
open decision out of nothing. What is left is the smaller choice between
linking the legacy page, linking the General Court's current bill status page,
or rendering the database's own text.

---

## What the database actually covers, measured 6 September

This decides the archive, and it is not what the table names suggest. Asking
for `MIN(SessionYear)` on `docket` says 1989 and asking for `MAX` says 2026,
and both are true with an eight-year hole between them.

| table | years | rows |
|---|---|---|
| `docket` | 1989-2015 complete, **2016 partial** (190 bills against a normal ~900), **2017-2024 absent**, 2025-2026 complete | 317,811 |
| `rollcallsummary` / `rollcallhistory` | **1999-2026, no gaps** | 9,565 / 2,303,047 |
| `Legislation`, `sponsors` | **2025-2026 only** | 2,234 / 13,326 |
| `CandH_Reports` | 2025-2026 | 5,597 |
| `LegislationText` | 2025-2026, every version of every bill as HTML | — |

So:

- **Roll calls are the easy half.** 13 terms back to 1999, one query a year,
  in the download's own format. Proven: 2025 took three seconds.
- **The docket is available for 1989-2015** and is the bill's whole history.
- **2017-2024 exists nowhere on this host.** Those four terms need the legacy
  web pages, which is the slow path and the one that got this address blocked.
- **Titles, sponsors and status do not go back at all.** `Legislation` holds
  the current term and nothing else, so an archived bill's title has to come
  from its docket, from the legacy pages, or from the LSR files if those can be
  had for a past year.

That last point is the one that changes the plan: the archive is not "one query
per term". A term before 2025 can have its votes and its docket cheaply, and
needs another source for what a bill is called and who filed it.

---

## What a year's page actually carries, measured 7 September

`probe_archive_shape.py` takes a couple of bills per session year, fetches each
one's status page once into `archive_samples/`, and reports what
`fetch_bill_status.parse()` -- the parser that will actually run -- gets out of
it. Eighty requests, and it settles the questions that decide the build.

- **`Bill_status.aspx` serves a 1989 bill**, in the same shape as a 2026 one:
  title, LSR, body, both chamber statuses, committee, dates, chapter and the
  local-government flag. The archive is reachable.
- **Sponsors are the exception, and they are the finding that matters.** 8 of
  8 bills sampled from 1989 carry none; 1992 and 1995 carry one each across
  seven and six bills. They become reliable only in the mid-2000s. Neither the
  database's `Sponsors` table nor the LSR files go back either -- both are the
  current session only. So an early term published at current depth shows
  bills with nobody's name on them.
- **Every year links its bill text; only the address and the label change.**
  All 80 pages sampled, 1989 to 2026, carry a plain `<a href>` to it. The
  older form is `/legislation/<year>/HB0169.html`, labelled "Bill Text" up to
  2012 and "[HTML]" and "[PDF]" for the three years after, which is why
  grepping for the words "Bill Text" finds nothing there; 2016 onwards use
  `billText.aspx?id=`. Nothing here is an ASP.NET postback: `__doPostBack`
  occurs zero times in the 81 saved files, and "Bill Docket" is an ordinary
  anchor as far back as 1989. This bullet used to read "bill text links appear
  from 2016", which was the probe measuring its own parser -- `TEXT_ID` in
  `fetch_bill_status.py` matches `billText.aspx?` and looks for nothing else,
  so the older form reads as absent. That older form is the constructible
  archive path the fetching plan now rests on.

Two cautions about the method, both learned the hard way. The first version
matched its own regexes and reported that no year carries sponsors, *including
2026* -- an hour after the same parser had pulled sponsors off 1,865 of the
1,996 bills of 2023-2024. A confident, tabulated, wrong answer. And two bills
a year cannot tell "the field does not exist" from "this bill never reached
the Senate", so the year-to-year flicker in that table is sample noise; the
sponsor question only became an answer when four years were widened to seven
or eight bills each.

**The consequence for the archive:** the file cap is payable, but sponsor data
is not purchasable. How far back a term is worth publishing as full records
rather than cards is set by the mid-2000s, not by 1989.

---

## Members the record cannot name

Three members of the 2023-2024 House cast 1,470 votes and have **no row in the
General Court's `legislators` table**, so no SELECT names them. The roll call
files identify a voter by Employeeno and the roster's PersonID is joined in on
it; that join comes back empty, and until 7 September `build_data` wrote all
three with a blank id, putting three people's votes in one row of the grid.

`resolve_members.py` deduces a name where the database cannot: the roll call
page gives the NAMES who voted a certain way, the history file gives the IDS,
and removing everyone already identified leaves two sets that must be the same
people. It named one of the three. The other two over-constrain to nothing,
because the page and the history disagree by a few members on each roll call.

This will recur through the archive, so the general fixes matter more than the
two members: it reads an archived year's roll call files, it no longer skips a
blank PersonID, and "already known" now includes the **676** members in
`former_members.json` rather than the sitting roster alone. (A comment in
`resolve_members.py` still says 675.)

**A separate limitation, not yet fixed.** The site stores **one party per
person, not per term**, and applies it to every vote they ever cast. A member
who changed party is shown under their current one on votes from when they sat
with the other. Zero members show two party letters anywhere in the record, and
that is the symptom rather than the reassurance. The General Court's
`legislators` table has a single party column too, so this needs a per-term
source that has not been found.

---

## What the archive needs

> **All five are done, and the list is kept for its ordering argument.** The
> file-cap decision did come before term keying, and that was right: it is the
> one dependency here that would have forced work to be redone. What the
> archive got is in `STATE.md` -- nineteen terms of histories, a proceedings
> manifest for each, and a site well under half the file cap.

In order. Each depends on the one before it.

1. **One proceedings table** (item 1). Everything downstream reads it.
2. **A decision on the file cap** (item 4). Changes the shape of the build,
   and the options imply different keying paths -- so it comes before
   term keying, not after. An earlier draft of this list had them the other
   way round, which contradicted the closing section of this same document.
3. **Term-keyed identifiers** (item 3). Nothing archival can start without it.
4. **One term back-filled end to end** -- 2023–2024 -- as the proof. Calendars
   and journals are two requests a year; votes and dockets are bulk files;
   videos and captions are the same pipeline that runs now. Bill text is a
   link.
5. **Then the rest**, which by that point is a long fetch and a lot of disk.

### What 2023-2024 actually got

The back-fill went much further than this section anticipated: **all nineteen
terms are live**, 33,683 bills in the index, each with a proceedings manifest.
The table is kept as the record of what the *first* archived term cost,
measured after the fetch rather than before it, because that per-term
arithmetic is still how to think about the next one:

| | 2023-2024 | how |
|---|---|---|
| titles, status, docket | 1,996 | bulk files |
| narratives | 1,996 | built from the docket |
| roll calls | **705 votes, 416 bills** | the database, 1999-2026 with no gaps |
| committee reports | **1,344 bills** | 90 House calendars |
| veto messages | **23 of 24** | those calendars and the term's 117 Senate ones |
| Senate committee reports | 0 | `CandH_Reports` holds 2025-2026 only |
| testimony | 0 | see below |
| bill text | **1,938 of 1,996** | `archive_text.json`, off the pages saved under `legislation/<year>/` |

**Three things the database cannot give an archived term**, asked of it
directly rather than inferred from the table names:

- `CandH_Reports` is 2025 and 2026 only, so the Senate's committee reports --
  which are one query for the current term -- are a per-bill web fetch for any
  other, or nothing.
- `houseRemoteTestify` **does** reach back: 74,084 sign-ins in 2024. But its
  only bill reference is `legislationID`, and `Legislation` holds the current
  term alone, so there is nothing to join them to. The rows are there and
  unaddressable. A 2024 `Legislation` dump, if the downloads page offers one,
  would unlock all 74,084 in a single bulk file and is the cheapest
  outstanding win in the archive.
- `LegislationText` is current-term only too, so the **database** does not
  rescue bill text either. It turned out not to have to: the constructible
  archive path `gc.nh.gov/legislation/<year>/<HB0000>.html` does, and
  `archive_text.json` holds **11,851 bills across eighteen terms**, 1,938 of
  them 2023-2024's. Item 10's decision -- that old terms get a link -- was
  overtaken by a route this section did not know about. The reasoning about the
  database is still right; only the conclusion moved.

**The two chambers print a veto message differently**, which cost four
readings of the artefact. The House prints the full text in its calendar; the
Senate mostly prints "PENDING VETO MESSAGES: SENATE BILLS: 268" and carries
the text only in the veto-session editions. Between two governors and two
chambers there are four signature shapes, and nine of Ayotte's Senate messages
state no date anywhere -- so the page shows none for those rather than
borrowing the docket's, which is the day the veto reached the chamber and not
the day it was signed.

**Do not point at `CLAUDE.md` by item number.** A note here once corrected
"CLAUDE.md's step 4"; step 4 was rewritten to be about something else entirely
and the correction outlived the thing it corrected. Name the claim, not the
item number.

The things that scale already: the marker method (per recording, cached, one
second at the median), the bulk-file pipeline, the narrative rules. The things
that do not: per-bill text fetches, and any tool that assumes one term.

---

## What I would do first

Not the archive. Consolidation before any of it: merge the two proceedings
sources into one file, split `renderDetail` and `build_site_v2.main`, write the
parser tests, and move the 35 marks into `ground_truth.csv`. Then the archive,
with the file-cap decision made **before** term-keyed identifiers are built:
R2-behind-a-Worker and fewer-static-pages imply different paths, so deciding
item 4 first stops item 3 being built twice.

That is what happened, and it was right. Three items are still outstanding.
**`build_site_v2.main`** is the last of the three long functions, and the one
`LAUNCH.md` ranks -- behind the factual work, which is the newer answer where
the two disagree. Item 3 is still partly done: `testimony.json` is flat to
this day, 565 bills under bare numbers. And item 6's primitive was never
written -- `find_in_transcript` appears nowhere but in the paragraph proposing
it, so every other matcher still builds its own window.

---

## A note on method

Most of what worked here came from one habit: read the artefact before
modelling it, and measure against something you did not generate. The marker
parser scored one second because every phrasing in it was read out of a real
transcript and it was scored against hand-marked times before it touched the
site. The clustering model it replaced was built before anyone read a
transcript, and its tolerances were asserted before anything measured them --
`probe_alignment.py` scored it at 1m 27s on 5 September, four days before the
site went live. They turned out to be honest, but that was luck.

The mistakes that repeated -- the floor split, the window-start time, the
silent overwrite -- repeated because the same shape of code was written in
several places rather than once. Consolidation is not tidiness here. It is the
difference between a bug fixed five times and a bug fixed once.
