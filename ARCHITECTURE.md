# Granite Record — Architecture

How the code and the data work: where the record comes from, how it becomes
one table and then one site, what each part guarantees, and the rough edges
that are known. It explains why things are shaped the way they are, so that a
change can keep the shape.

Where a number here disagrees with `STATE.md`, which `python3 handoff.py`
writes, `STATE.md` is generated and this is not. The history of how the code
got here -- the plans, the measurements taken along the way, and the order
the work was done in -- is kept privately rather than in this repository.

---

## Where the code lives

The repository root holds only what something outside the repository runs by
name: the pipeline (`build_all.py`), the night (`nightly.py`), the kit
(`cloud.py`), the livestream index (`livestreams.py`), the laptop's evening
job (`laptop_evening.py`), the pull of reader reports (`compile_reports.py`),
the first commands of a working session (`inventory.py`, `preflight.py`,
`handoff.py`) and the refusal tools (`refusal.py`, `netcheck.py`); beside
them `_paths.py`, the front end, the config and the data. Everything else is
under `src/`, one folder per job. `src/README.md` has the tree and the rule
for where a new file goes, and each folder's own README says what it holds:

    src/fetch/gc_web/    asks gc.nh.gov's web server
    src/fetch/gc_db/     asks the General Court's SQL host
    src/fetch/youtube/   asks YouTube
    src/fetch/other/     asks anyone else
    src/parse/           decides the record from what is already on disk
    src/towns/           towns, districts, counties and their officials
    src/hearings/        proceedings, their recordings, timestamps and the scorer
    src/pages/           writes what a reader gets in site/
    src/checks/          looks at something and reports
    src/lib/             the few modules every stage shares

**The network boundary is a folder.** A fetcher sits in the folder of whose
server it asks, because that is what decides what can go wrong, and
`preflight` holds the line from what each file does rather than from its
name: a `refusal.check()` outside `fetch/gc_web/`, the SQL host outside
`fetch/gc_db/`, yt-dlp outside `fetch/youtube/`, or a request from any folder
under `src/` outside `fetch/` -- `checks/` asking graniterecord.org is the one
exception -- fails it. So `parse/`, `towns/`, `hearings/`, `pages/` and `lib/`
ask nobody anything and are free to run. The entry points at the root that do
ask -- `nightly.py`, `livestreams.py`, `netcheck.py` and `cloud.py` -- stay
outside the folders, and every script that carries a gc.nh.gov address,
wherever it sits, is held to `refusal.check()` but `netcheck.py`, which is what
a person runs to diagnose a refusal.

**Names are bare and unique.** Every import and every launch is by bare name:
`_paths.py` puts each code folder on the import path, and whatever starts a
script as a process -- `build_all.py`'s steps, `nightly.py`, the evening job,
the lane -- finds it through `_paths.script`. So a file can move between
folders without anything that names it changing. A command a person types
gives the path from the root --
`python3 src/hearings/probe_alignment.py --truth` -- and `preflight` fails a
tracked command that names a script under `src/` without its folder, which
typed from the root answers "can't open file".

## How it runs

The site is built and published by a night on GitHub's machines and fed by
the maintainer's laptop, and the two meet in a private Cloudflare R2 bucket
rather than on either machine. `nightly.py`'s docstring is the long version
of the first four parts below, `cloud.py`'s of the morning and the kit, and
`laptop_evening.py`'s of the evening.

**The night, on GitHub.** `.github/workflows/nightly.yml` runs every night at
08:17 UTC on an empty Windows machine, from the commit of the branch it was
started on -- `main` on a schedule. Its first job brings the small state
files and the kit down from R2 (`cloud.py state-down`, `cloud.py kit-down`),
looks for new livestreams (`livestreams.py --since-state`), and runs
`nightly.py --runner`: the day's bulk files from gc.nh.gov, asked only when no
refusal is on file; the rebuild, `build_all.py --local --no-captions`, since
that machine holds no caption files; and the gates -- `preflight.py --code`,
`src/checks/check_site.py`, a census of the build against the last good
build's counts (`archive/census.json`), and a ceiling of 95,000 files
(`FILE_CEILING`) that nothing lifts. A build that passes goes to a preview
address and, when the night judged it fit for production, to the bucket as
one archive for the second job; what the night changed goes back to the kit
(`cloud.py kit-up`); and the night's verdict -- what it did,
whether it was clean, its warnings and its errors -- is written to
`archive/last-night.json` and kept in the bucket as `state/last-night.json`.
The second job deploys to production. It sits behind GitHub's `production`
environment, so it waits for a person's approval, and
`nightly.py --deploy-to production` deploys only the newest night's build: a verdict from
another run, a site whose fingerprint is not the one judged, or a checkout
not on `main` is refused. The weekly workflow, `weekly.yml`, runs on Sunday
night: the committee rosters, the members who have left and the study
committees, each fetch whole or not at all. It publishes nothing; Monday's
night builds what it took.

**When the export comes back empty.** The General Court's export has come back
empty on whole nights. When it does and nothing else is wrong, the night
turns at once to the SQL host the General Court publishes credentials for:
`src/fetch/gc_db/fetch_day_db.py` asks six views and five lookups,
`src/parse/dayfiles_from_db.py` rebuilds the seven day files that change and
guards them against the installed ones, and they go in through
`snapshot_gencourt.install()`, shrink rule and all -- every one of them or
none. It does not happen with a refusal on file, with a hold on the SQL host
(`archive/sql-held.json`), without installed files to take the years and the
row order from, or on a New term run. When the database cannot be used the
export is asked once more, half an hour later. The verdict says where the
installed files came from (`files_from`, `day_files`), a warning leads the
run's page, and seven such nights in a row (`DB_NIGHTS_MOST`) is an error
there, though the build still goes out.

**The term turnover.** The General Court's files describe the current term
only, so before they turn over, the finished term's inputs are frozen:
`src/lib/freeze_term.py --views` copies the database's views of the term into
`db/term/<term>/`, and `--session` the day files as installed into
`frozen/<term>/`, with the term's docket and manifest under the archived
terms' names (`Docket_<term>.txt`, `verification_manifest_<term>.csv`) and
its roll calls in `rollcalls/`. After the turn,
`python3 src/parse/build_data.py --frozen-terms` builds that term
from them every night, so a correction still reaches it. An ordinary night
refuses files that name a newer term than the installed ones, whatever their
size (`snapshot_gencourt.judge`). Only the *New term* run takes them: a box
on the nightly and the weekly, ticked by hand and never on a schedule, never
a dry run, and refused until the term it would leave is frozen as installed
(`freeze_term.ready`). For that run alone the smaller files are installed, the
feeds may be pruned (`build_all.py --allow-prune`) and the census lets the
feeds fall, and nothing it accepted is kept until its build is published: what
it changed waits in the bucket under `nights/<run>/kit/`
(`cloud.py kit-up --hold`), and its counts become the baseline only when the production deploy
has landed, when `cloud.py kit-release` moves the files into the kit. Until
then the next scheduled night meets the smaller files again, refuses them,
and says why. Item 3 under *What is structurally wrong* says how a frozen
term is read.

**The release gate, in shadow.** Every night that builds records in its
verdict whether it could have gone to production without a person
(`review`: `needed` and `why`), and the run's page says in one line what the
gate would have done. It would hold a New term run; the first night after a
release; a night that changed far more than a data night does -- a finished
term's bill list rewritten, or more than `REVIEW_ROWS_MOST` of the current
term's rows; and a night with a kind of warning that neither the build
production serves nor a night published in the last fourteen days carried.
The day's files coming from the database, and an error on the run's page,
hold nothing: both stay on the page and in the verdict for the morning. The
workflow's `REVIEW_GATE` is `shadow`, so every night still waits for approval
in `production` and the gate decides nothing yet. Switching it to `on` is a
later step: a cleared night would then deploy through `production` with no
reviewer, and a held one, and every New term run, through
`production-review`, which keeps one. `preflight` holds the workflow's
setting and its environment line together.

**The morning triage.** On the maintainer's laptop,
`cloud.py pull --changes-only` brings down what the triage reads and nothing else: the
refusal record, the night's and the week's verdicts (into `archive/cloud/`,
where a verdict from before yesterday is called stale) and the change lists
`src/checks/gc_changes.py` wrote (`reports/gc-changes-<day>.md`). A full
`cloud.py pull` also brings back the night's kit files and logs, and never
`site/`. Reader reports are not pulled on GitHub's machine:
`compile_reports.py` reads them from the report database on the laptop,
screens every one without a model, and writes the triage file read in the
morning, holding back the words of any report the screen stops.

**The evening caption job.** YouTube refuses captions to GitHub's machines
and answers the laptop, so the exact start of a recording comes from there.
`laptop_evening.py`, which Windows' Task Scheduler runs each evening, stops at
the first step that fails: `cloud.py pull`, for the night's list of
recordings waiting for captions; `livestreams.py --catch-up`, which captions
up to twenty of them, oldest first, and reads the chair's boundaries out of
them;
`src/hearings/probe_alignment.py --truth --candidate candidate_segments.json`,
and nothing is sent if the median got worse; and
`cloud.py seed-kit --only` with the caption results and nothing else. The
next night publishes the times. Until then a recording is on its bill's page
with a start taken from the schedule, marked approximate.

**The kit.** `cloud_kit.json` lists everything the build reads that git does
not hold -- the day files, the saved bill pages, the database dump, the
frozen terms, the caption results, the logo and the icons -- and `cloud.py`
moves it: `kit-down` onto an empty machine, `kit-up` with what a night
changed, `seed-kit` from the laptop. Each file has one owner, the night or
the laptop, and neither sends over the other's copy. Nothing in the bucket is
overwritten or deleted outright: the old copy goes to `replaced/<date>/`,
which the bucket keeps for 30 days. Every file is checked against its size
and sha256 on the way down, and the list's `never` entries -- secrets, and
what readers typed -- are applied to every command. The small state the night
must remember (`refused.json`, `census.json`, the verdicts) lives under
`state/`, so a refusal the night meets outlives its machine and stops the
laptop's fetches too.

---

## What is sound

**The data comes from bulk files.** Docket, roll calls, sponsors, members: one
download each, covering a whole session. That is why nineteen terms of bill
histories and fourteen of votes -- roll calls begin in 1999 -- are a shelf of
bulk files rather than a hundred thousand requests, and why the core of the
site has never been what provoked the General Court's firewall. The per-bill
fetches are the exception, and they are the ones that got the address blocked:
bill text, testimony, and the dockets of 2016-2024, which were in no bulk file
and no database table until the `Past*` views described below, and had to be
asked for one bill at a time --
`docket_pages/` holds 8,607 of them, 1,072 of those 2016.

**The narrative is rule-based and inspectable.** Every sentence on the site can
be traced to a docket line and a rule in `narrative.py`. When the Clerk says a
sentence is wrong, there is a specific rule to fix, and the fix applies to every
bill that shares the shape. A model would give neither.

**Ground truth exists and is wired to a scorer.** 35 proceedings a person timed
by hand, and `python3 src/hearings/probe_alignment.py --truth --candidate` scores any method against
them in a second. Nothing about timestamps should ever again be tuned without
that number moving in the right direction. It is the single most valuable
artefact in the repository, and it lives in `ground_truth.csv`, which no
generator writes, after being lost twice as columns of a file that rebuilds
overwrote.

**The site is static.** Files on a CDN, nothing to go down at two in the
morning, and exactly one write-only Function that no page waits on --
`functions/api/report.js`, behind the "report a problem" box. That constraint
is also what forces the file cap under item 4 below, but it is the right
constraint.

**`preflight.py` builds the whole site on a fixture.** Most of its checks exist
because of a specific failure; it has caught stamp mismatches three times and a
dead-zone error once. Run it for the current count -- a number written here
would be wrong within a day, and was.

**A person can overrule a generator, in files the generators cannot touch.**
The files that are a person's are listed in `preflight.py`'s `HANDMADE`;
among them are `ground_truth.csv`, `review/checked.jsonl`,
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
(100 KB, in `src/pages/build_bill_pages.py`) keep a file, and the step prints the split
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

## One proceedings table

`proceedings.csv` is the one table of proceedings for every term -- hearings,
executive sessions, work sessions, committees of conference and floor
debates. Item 1 under *What is structurally wrong* below says why there is one
table; this section says how it is built.

**All nineteen terms have a manifest**, 1989-1990 to 2025-2026. 2017-2018
landed as hearings without video, as did every term before it, because the
House streamed nothing until May 2020. 2019-2020 straddles that date:
hearings across the whole term, with video on its rows from the 14th of May
2020 onwards.
Run `python3 handoff.py` for the row and recording counts.

**A row is what the docket scheduled, which is not always a sitting.** The
docket enters a meeting's notice ahead of the day, and a few bills never
reached theirs: withdrawn first, never introduced by the House at all, or
taken from the committee by the chamber before the day; and one notice states
a day before its bill existed (the history's `no_sitting`).
`proceedings.notice_only` says which rows those are, from the bill's own
history in `narratives.json`, and `proceedings.sittings` parts the table by
it. Everything that says a committee sat reads through that one rule -- a
bill's stations, its committee's days, the download `data/proceedings.csv`
and the Learn pages' count of hearings -- and the table itself keeps the row,
because the notice is on the docket. `build_committees.py` prints the rows it
leaves off, and stops if a row is filed for a bill the index says was never
introduced.

### Where the proceedings come from

`docket_parser.parse_proceedings` takes a docket and returns structured
proceedings -- bill, body, kind, scheduled date, scheduled time, venue,
committee -- and it does not care which term's docket it is given.

For the older terms the docket comes from the SQL host's bulk dump: `db/`
carries the Docket view,
`docket_from_db.py` turns a slice of it into the shape `narrative.py` already
reads, and **fifteen `Docket_db_*.txt` files are on disk**, from
`Docket_db_1989-1990.txt` through `Docket_db_2015-2016.txt`, plus
`Docket_db_2015.txt`. Every one of those terms
has been through `build_manifest.py`.
For 2016-2024 the Docket view held part of 2016 and nothing after it, so
`fetch_archive_docket.py` wrote `Docket_<term>.txt` in `Docket.txt`'s own
shape from the legacy web page, one bill at a time. 2015-2016 is built from
that fetched file -- 1,787 bills, the database's 905 kept as its seed and the
rest fetched -- and not from its 905-bill database copy, which gave truncated
histories.

**The calendars stay the second source, and the only one for what a docket
does not carry.** All 1,580 House calendar PDFs for 1997-2026 are on disk
with text extracted, 100%. `python3 src/hearings/calendar_meetings.py --check` reads the
(bill, day) pairs out of them at no cost -- 61,767 across 2,107 committees on
10 September, 61,543 across 1,058 on the 17th after committee-name variants
were merged, so run it rather than quoting either. Senate calendars: 1,604
PDFs, 984 with text.

### What a term's recordings need: one number per video, from YouTube

`build_manifest.py` needs `start_eastern` -- when the stream actually began --
because the schedule offset is the scheduled time minus that. It reads it from
`videos_*.csv`.
`channel_index_full.json` carries `id`, `published` and `title` and nothing
else, and `published` is not the start: a 09/09/2026 meeting is published the
evening before.

`fetch_channel_index.py` pulls `actualStartTime` from `liveStreamingDetails`,
**fifty ids per call**. It needs a
YouTube Data API v3 key. That is the whole gate, it is against YouTube rather
than the General Court, and it takes minutes.

### One manifest per term

**`build_manifest.py` needs no `--term` flag, and no change at all.** It takes
`--docket` and `--out`, the docket carries the term, and that is the whole of
term-awareness. Proved rather than argued:

    python3 src/hearings/build_manifest.py --videos "videos_*.csv" \
        --docket Docket_2023-2024.txt --out verification_manifest_2023-2024.csv

    Wrote verification_manifest_2023-2024.csv: 7,019 rows
    5,604 rows have a direct watch link

**And the cross-term hazard is not real.** The worry was that a 2023 bill
could take a 2025 recording on a same-day, same-committee coincidence. It
cannot: the matcher filters proceedings to dates that have videos, and a date
carries its year, so `2023-03-07` cannot match a video from `2025-03-07`.
Measured on those 7,019 rows: **0 matched to a video outside 2023-2024, and 0
whose video date differs from the scheduled date.**

`build_manifest.py` refuses to write an archived term's docket to plain
`verification_manifest.csv`, which is the current term's, so each term keeps a
file of its own.

### Built whole, from every manifest

**`build_proceedings.py` must not get `--term` merge semantics.** It would
make a writer that runs on one term and rewrites a file holding all of them,
which is precisely the failure this project has had four times -- the
manifest lost the 35
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
> whole-table guard in `main()` and a per-(term, source) row count in
> `shrunk_groups()`, each released only by `--allow-shrink`, and
> `preflight._proceedings_term_shrink` holds them there. So the per-term guard
> arrived after all -- on the read, which is the safe half, not on the write.

### The naming contract

`build_manifest.py` once downloaded `Docket.txt` from gc.nh.gov when `--docket`
was omitted and the file was absent:

    if not Path(docket_path).exists():
        print("Downloading Docket.txt (this is a few MB)...")
        urllib.request.urlretrieve(DOCKET_URL, docket_path)

It was a `build_*` script making an unguarded network call to the address that
has blocked this one twice. The whole permission rule rests on the naming
contract -- `fetch_*` touches the network and is asked about first, everything
else is free to run -- and this broke it silently. It never fired here
because `Docket.txt` was on disk; it would have fired in a clean checkout,
which is the state a refactor is most likely to create.
It now prints the fetch command and exits.

The contract has exceptions. `probe_archive_shape.py`, `probe_calendars.py`,
`probe_schema.py`, `resolve_members.py`, `snapshot_gencourt.py` and
`check_civics_links.py` ask the General Court too, and sit beside its
fetchers in `src/fetch/gc_web/` (`probe_archive.py` and
`probe_legacy.py` did, and are in `obsolete/` since 6 October 2026), and
each calls `refusal.check()` before its first request;
`preflight._every_fetcher_checks_refusal` finds every script that
asks, whatever its name, and fails one that does not check; and
`preflight._every_fetcher_notes_refusal` fails one that checks and never
records a refusal it meets with `refusal.note()`. `netcheck.py`
asks gc.nh.gov and skips the check on purpose, because it is what a person
runs to diagnose a refusal. `probe_db.py` queries the General Court's SQL
host, the one the `fetch_*_db.py` scripts read, and sits with them in
`src/fetch/gc_db/`.

Since the move into `src/` the contract no longer rests on a name alone: a
script that asks a server sits under `src/fetch/`, in the folder of whose
server it asks, and `preflight` fails a request made from anywhere else
under `src/` (*Where the code lives*, above).

### Downstream

**Stations are already term-keyed.** `build_site_v2.py` builds
`procs[(r["term"], r["bill"])]` and `floor[(r["term"], r["bill"])]` and
reads them the same way. The "stations leak across terms" bug was fixed: with
one term in the table it was latent, and a second term would have made it
live on every page.

### Checking a change

    python3 preflight.py
    python3 src/hearings/probe_alignment.py --truth
    python3 src/hearings/probe_alignment.py --truth --no-bench
    python3 src/checks/check_site.py

Those four commands are the check on a change of this kind.

## The bill search, and what it reads

One matcher, in `app.js` between its `BILLMATCH` marks. `/bills` runs it
there; `build_pages.py` cuts the marked lines into `site/billmatch.js`, which
`find.js` loads for the header's search box and for `/search`. So the three
count the same bills, and a change to the marked lines changes all three.

It reads, for each bill, in the order it lists them:

1. **the title**, the prime sponsor's name and the committees' names, from
   `site/idx/<term>.json` -- the word itself before a longer word it begins;
2. **the topic** the bill is filed under, for a single typed word that is the
   topic's name, and only where the topic names one subject. In a search of
   several words a topic stands for one of them only when it is that word
   and nothing else and the title has the rest;
3. **the drafters' analysis and the bill's text**, from
   `site/sidx/<term>.json`, which `build_search_index.py` writes: for each
   word, the bills it is central to and how central, 1 to 9; and, for each
   bill, which pairs of those words stand next to each other. The page
   fetches that file only when somebody searches, per term;
4. **a table of public words** (`CONCEPTS`), for what a reader types that no
   bill says -- "lgbtq", "weed", "bathroom bill" -- each standing for wording
   the bills do use. A phrase of the table is looked for in all of the
   above; a single word of it in titles and analyses, and in the body of a
   text only under an entry's `with` rule.

Twelve things in it are easy to undo by accident.

*A single word the table supplies is not read in the body of a text.* A
phrase ("risk protection order") is specific and a single word is not: read
in texts, "gun control" listed a speed enforcement fund for its radar guns
and "illegal immigrants" five bills on alien insurers. The word the reader
typed is still read there.

*A search that lists nothing is offered a word, never read as one.*
`site/sidx/words.json`, which the same build writes, is every word of five
letters or more that any bill of any term uses, with the names of members and
towns. A typed word that lists nothing and is in that file is a real word no
bill of the term is about, and nothing is offered for it; one that is not in
it is offered as the word of the bills it sounds like ("medicade", Medicaid),
as a "Did you mean" that the reader chooses. The file is fetched only when a
search has listed nothing. For one day the page read such a word again by
itself, with no such file: it showed 98 investment bills for "incest" under
"no bill says incest", which three bills do. The record's own slips are left
out of the file -- a word one bill uses that is a common word with a letter
dropped, added or swapped inside it ("goverment") -- so that a reader who
makes the same slip is offered the word; never a changed letter, which is
what "incest" and "invest" differ by. A dropped or added letter needs the
common word to be a hundred bills'; two letters swapped need ten ("flouride",
beside the 42 bills that say fluoride), because a swap is almost never
another word and a dropped letter often is (carving, caring).

A search of several words that lists nothing says which of them list bills
on their own, and, for three words or more, which searches with one word left
out do; each is a button, and none is drawn in the search's place. In the
header's panel the offered word is a button too, and its click stops at the
panel: left to reach the document it shut the panel, and on a page `app.js`
draws it listed bills over the page.

*The word typed, in another form, is still the word typed.* What the table
supplies is listed after everything that has the reader's own word, which is
right for wording that names another thing ("landlord", for "eviction") and
wrong for a term that is the word itself: its letters written out ("dwi" and
"driving while intoxicated", "dmv" and the division of motor vehicles), which
counts as the word in a title; or the word with another ending ("eviction"
and "evict"), which counts as a longer word in a title does. Only among the
terms of the entry the word is an ask of.

*In a text, a longer word is read from six letters.* A word that is the
whole search also finds a longer word it begins. In a title that holds from
any length, lower down, as the person ruled ("bail" and the bailiffs). In an
analysis or a text it holds from six letters: below that the longer word is
mostly another word (fee and feet, plan and plant, "bail" and a bill on
cloud-stored files that says "bailment"), and from six it is mostly the same
one (municipal, municipality). The card says which word it was listed for.

*A search is read to its twelfth word, and a bill is asked once.* Every word
typed is a part every bill is asked for, so a pasted paragraph is read to
`MAXWORDS` words that carry a subject and the page says so; what a part
found in a bill is kept on the part (`recall`) for the list, the filters'
counts, the order and the cards; the box draws when the typing pauses; and
what a search that lists nothing is offered is counted after the page has
said so, one search at a time. Before that, 200 pasted words stopped the
page for 17 seconds and every letter on All terms for half a second.
`preflight` counts the searches one drawing runs and how often a bill is
asked, rather than timing a machine.

*What "about" means is decided at build time.* A word a text uses once is
nearly always a passing mention, so the build keeps a word for a bill when the
analysis has it, or the text uses it twice and leans on it. The exception is
kept at weight 0 and counts only under a table entry's `with` rule (a second
thing the bill must also say): four vetoed bills say "lavatory" once, beside
"biological sex", and that is all that marks them as what the public calls the
bathroom bills.

*Two words found apart are not a bill.* In a search of several words, a
plain word found only in a bill's analysis or text counts only where it
stands beside another word of the search there -- next to it, either way
round, with only words that carry no subject between ("custody of
children"); and words joined by "and" or "or" share what stands beside them
("meals and rooms tax" is the meals tax). Before that each word could be
found in a different place, and
"medical debt" listed the consolidation of the health and education
facilities authority, "small claims" a tariff credit for small businesses and
"eminent domain" the right to hunt and fish. The index keeps each pair as
five letters of a hash, under `"b"`, because spelt out they were more than
the rest of the file; the docstring of `build_search_index.py` has the
numbers. Not asked of the table's own wording, of a word beside a sponsor's
name, nor where every other part of the search is the table's and the title
has it ("public records request", for a bill titled for the right-to-know
law). The same rule covers the other guesses: a longer word in the title, a
committee's name and a sponsor's name with an ending each count beside words
the title has, and never two of them together.

*A repeat is not a second mention.* "The text uses it twice" is counted in
sentences that say different things: a constitutional amendment printed as
the amendment and again as the ballot question, or one sentence amended into
two sections, is one mention, and so is a word used twice in one sentence. A
section's heading counts each time, because it names the statute being
amended. `distinct()` in `build_search_index.py` is the rule.

*The same letters are one word however they are spaced.* A title is also
read with its hyphens taken out and with each two neighbouring words run
together, and two plain words typed together are also read as one: "ezpass",
"ez pass" and "e-zpass" find "E-Z Pass", and "reassessment" finds
"re-assessment".

*A bill is listed for its own words.* A table term finds a bill because the
bill's title, analysis or text has it; a card listed that way says which
("text says: lavatory"). The table never lists a bill for what it is said to
do.

*Two programs read the same words.* `stem()`, `wordKeys()`, `altRx()` and
`pairCode()` in `app.js` have twins in `build_search_index.py`, and the build
reads the tables' phrases and the words a search skips out of `app.js` with a
regular expression. `preflight` runs both over the same words, pairs and
texts and fails when they differ; without that check a word is filed under
one key, looked up under another, and nothing fails.

*A typed word is not a property of an object.* The tables a typed word is
looked up in are made with no prototype, and a list out of a fetched file is
checked to be a list. "constructor" is a word, and on a plain object it was
a function: the search stopped with a TypeError and drew nothing.

*The build stops before it writes.* `build_search_index.py` makes every
file in memory and replaces nothing in `site/sidx` unless the texts were
there: a term before the newest with text for fewer than half its bills, the
newest with none where it had some, or a vocabulary under 25,000 words stops
the run with `site/sidx` as it was. `check_site.py`, which the nightly runs,
reads `sidx/manifest.json` against `idx/` and refuses a site whose search
index is missing or has an earlier term without text.

`tests/search_cases.json` holds real searches against real bills, with
`tests/search_index.json` cut from the real index for them;
`python3 src/pages/build_search_index.py --fixture tests/search_cases.json` refreshes
both from the record. Its `across` list is searches held to bills of other
terms, which only the built site can answer. `matchScore()` is the one place
a bill's score is added up, for `/bills`, the header, `/search` and those
cases.

## The bill index, one file per term

Every bill's row -- title, sponsor, committees, topic, status, passage -- is
published one term to a file, `site/idx/<term>.json`, and `site/meta.json`
names the terms, newest first. Those are what the bills page, the header's
search, `/search` and every record page fetch. The build reads the same files
through one reader, `site_read.bill_index(site)`, which answers in three ways:
`None` where no site is built (there is no `meta.json`: GitHub's machine starts
with `site/` empty); `site_read.Broken` where the files do not hold together (a
term named with no file, an empty or unreadable one, a row in another term's
file, a term file `meta.json` does not name); and otherwise every row, newest
term first. A builder that cannot go on without every bill asks
`bill_index_or_stop`, which turns both of the first two into a stop that says
what to run: four of the old readers read a missing file as no bills and went
on. The nightly's census counts it, its fingerprint hashes the files
`meta.json` names, and `check_site` refuses a site whose index does not hold
together. `build_site_v2.py` deletes a term's file it did not write this time,
which an earlier build on the laptop's never-emptied `site/` could leave and
the reader would refuse. Once a deploy is up, `python3 src/checks/check_live.py --gate` reads the
served `meta.json` and the newest term's file: a `meta.json` naming no term or
other terms than the build's, or a term file empty, not JSON or a web page in
its place, fails it as a deploy that did not land; a file too large for it to
read fails it as not checked, with an exit of its own (`NOT_CHECKED`) that the
nightly reports as such rather than as a deploy that did not land.

`/index.json`, the same rows joined into one file, was retired on 5 October
2026. No page read it; six build steps did, and it had reached 23.7 MB --
90.5% of the 25 MiB Cloudflare Pages takes in one file -- growing about a
megabyte with every field added to a row. Each term's file is 1.0 to 1.3 MB,
so the limit no longer depends on how many terms there are. For programs,
`data/manifest.json` lists the term files with their addresses, bills and
sizes, and `data/bills.csv` is every bill in one table. `build_site_v2.py`
deletes a leftover `site/index.json`, because `site/` is never emptied and
`publish` would otherwise go on deploying a frozen copy, and `check_site`
refuses one.

The order a builder writes in is its own to state, not the order the rows
arrive in. The sitemap lists the newest term's bills first, and a committee's
file its terms newest first, sorted where they are written; within a term the
sitemap keeps the order of the term's file, which the reader keeps. Until 5
October both followed `index.json`'s order, which was `data/bills.json`'s:
2025-2026, 2023-2024, then 1989-1990 upward.

The governor's veto messages are read before the site data, which puts each
on its bill's page, so the report of the vetoed bills with no message is a
step of its own after it (`python3 src/parse/extract_vetoes.py --gaps`): at the end of the
writing run it read the previous build's index, and on GitHub's machine
nothing at all.

## Sitting days, built 19 September

A page for every day the House sat, at `/session/H/<date>`, and for every day
the Senate sat, at `/session/S/<date>`.

**The record and the colour come from different places, and that is the whole
design.** `narratives.json` already holds 79,096 floor events across all
nineteen terms, each carrying the bill, the motion, who moved it, whether it
carried, how it was voted and the journal page it is printed on.
`session_days.py` reads them and contains no parser. Only what the record
cannot hold -- who spoke, and the text of a printed debate -- is parsed out of
the journal, by `journal_days.py`. A page that loses the journal entirely is
still true, and every page before 1997 does lose it, because the journal
starts in 1997.

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

**Every roll call on record is drawn, and counted once (2 October 2026).**
The pages were first made of the docket rows typed as floor motions and
nothing else, and a roll call on an amendment, a committee of conference
report, a motion worded without "MA", a veto row spelled "Overriden", or a
second question on one 1999-2006 line was on no page: 1,552 of the House's
5,577 roll calls and 1,431 of the Senate's 3,988, with the opening's count
wrong on 697 pages. `session_days._roll_calls` now takes `rollcalls.json`
as the list. Each roll call is paired with its docket tally the way
`rollcall_outcomes` pairs it for its outcome, and drawn on the floor motion
that is that vote (the ballots' count, the record's outcome), on a motion of
its own worded and dated from the row or clause that states it, under its bill
worded as the roll-call file words it where no docket row does, or among the
day's "Votes on no bill" -- rules, rulings of the chair, printing a debate --
which the page builds from the roll-call file alone. A roll call the file
dates on a day the chamber did not sit (the House's of 24 and 25 February 2021
are all dated the 26th) goes on the sitting the docket and the journal put
it on. Before 1999 the docket is the only record, and its roll calls are drawn
from its own words. The opening counts votes, not motions: one motion entered
on 35 bills' dockets is one roll call, and so is a consent calendar. What no
sitting draws is a named list with its reason (a quorum call, a date no sitting
holds), and `preflight` holds every roll call and every page's count to that.

**And held to the journal the build did not make.** A review of that change
found one vote drawn twice on ten pages, a vote on two pages, a division drawn
as a roll call and speeches moved onto motions they were not made on -- all
invisible to a check that compared the pages with the model that made them.
So the chamber's journal on disk is read for what it prints (`_journal_day`:
the House's YEAS-NAYS and divisions from 1997, the Senate's "Yeas: n - Nays: n"
from 2003, and the measures each sitting names), and it decides four things.
Where the docket and the roll-call file date a vote on different days, it is
drawn on the one whose journal prints its count (SB 319's roll calls of 15 May
2014 were on a 16 May page of a day the House did not sit; three such pages are
gone). Where the docket says division and the journal prints a division, it
stays one, whatever the roll-call file holds (HB 299, 20 February 2025). Where
a page would count more votes of one count than the journal prints, a count only
the docket states beside a roll call on record is a copy and is taken off its
motion (HB 461's "MA RC 289-48" of 22 January 2014 is HB 597's), and a copied
row on a bill the day's journal never names is not drawn (HB 1559's special
order of 12 March 2026 is HB 1708's). And business the docket marks as done in
recess carries no roll call: a recess takes none. Without the journal the
record still finds each vote's motion: an uncounted motion owns the clause of
its line that names it, a count the reader missed is read off the motion's own
line, several roll calls of one count are told apart by what their questions
name (the consent calendar, the bill, the member), a roll call filed under the
wrong bill goes to the one docket row that states it (SB 287's conference report
of 26 June 2025, filed under HB 287), and the file's own bill is drawn even where
the docket holds no row for it (HB 476). A speech goes to a motion only by the
journal's count, never by being the one motion of a run, and never to two
motions of one count or to both sides of one; a name is said once.
`preflight` now holds every page to each roll call once, the House journal's
own count on every day it is on disk (nineteen days named, each for its reason)
and the speaker lists of every built page.

**And to what the journal prints after each speech (3 October 2026).** A
second review read 1,127 speakers on 35 House pages against their journals and
found 76 on a motion the journal contradicts: on another bill, on a censure or
a reprimand, on a rules suspension, or on an amendment's failure set down as a
speech on the report. A speech is now read where it stands -- it was found
again by its first forty characters, which is the first sentence that begins
the same way -- in a text whose running heads leave the line break they sat in,
since a bill heading that opened a page was glued to the line before and its
speeches read as the previous bill's (`journal_days.clean(lines=True)`, used
for the speeches only). A speech is closed by what the journal prints first
after it: a roll call, a division, or a question carried or lost by voice
("Floor amendment (0786h) failed."), unless a motion was moved in between,
which is then that motion's (`decided`). A motion claims a speech only where
that is its own decision: the one motion a bill had that day no longer takes a
speech the journal ties to another count, and a speech tied to a vote none of
the bill's motions is -- a reprimand, a censure, an amendment's division the
page does not draw -- is named nowhere, which is less than the journal says and
nothing it contradicts. The same review found the docket's division counts
copied and mistyped as its roll calls are. A division the docket alone states
loses its count where the House Journal prints a count within three of it after
the bill's own heading and not the count itself, or prints the count fewer
times than the docket states it, after the heading of another bill whose row
states it; a motion with no heading of its own (a reconsideration, a tabling)
is printed under whichever came before, so a division is never taken off for
that alone. One division entered on many bills counts once where the journal
prints it fewer times than it is entered. And a vote is drawn as the question
its own clause names: a veto override's result is read from its result words,
never from "override"; a count before 1999 belongs to the clause that holds it,
not the line's final disposition (HB 386's "OTP/AM ML RC(45-241); ITL REPORT
ADOPTED" of 3 January 1996); and a Senate amendment row's roll call on third
reading or re-referral, and a motion to divide, are drawn as those questions.

**And to what comes between a speech and its decision (3 October 2026).** A
third review read every name the second pass put on a motion. A speech whose
question was decided after another motion was moved fell through to the next
roll call in the bill: Rep. Rowe spoke for HB 1670's committee amendment on 15
February 2012, a Call of the House was moved, the amendment carried 177-99 on
a division, and the page named him on the floor amendment lost 96-179 next.
`journal_days` now walks forward from each speech (`walk`): a Call of the House
is read through; the previous question, or a motion to limit debate or print
remarks, is read through with the decision printed straight after it where
that is plainly its own; a motion to table, postpone, make a special order,
recommit, refer or divide is read past where the journal shows it failing,
withdrawn or ruled out of order (HR 20's report of 23 March 2000, debated, a
tabling lost, then 162-179 on the report); and anything else put first -- a
motion, an amendment offered, an appeal of the chair -- ties the speech to
nothing (`untied`), and its speaker is named as having spoken during the
bill. A bare "Adopted." straight after an amendment is offered is the
amendment's, not the report's, and a voice verdict the other way from the
motion ("The report failed." before an adopted Ought to Pass with Amendment)
is another question's. A conference report's own heading
("COMMITTEE OF CONFERENCE REPORT ON SB 449") opens its bill's stretch, and a
resolution offered from the floor ends the bill before it. A speaker's name is
one member's: "moved ..., spoke in favor" is read, and a name no longer runs
back over a committee statement's right-aligned signature. The clerk's count a
roll call is printed under can be one vote off its ballots or the docket's
count, and still ties the speeches before it (`build_session_pages.clerk_counts`).
A division whose docket count the journal prints within three under the bill's
own heading is drawn with the journal's count rather than with none; one the
journal prints nowhere, for a bill it names that day, loses its count; a
docket-only count that contradicts its own outcome (a tabling "adopted" 154 to
167) is drawn with neither; and a consent calendar's count is the one the
journal prints. A carried override is said to have overridden the veto in that
chamber, never to have made the bill law. `preflight`'s data check
`_every_speaker_where_the_journal_decides` holds every counted motion on a House
page to the journal by a walk written apart from `journal_days`', in both
directions: each name on a motion spoke on its question, and each speech the
journal decides with its count is named.

**What the Senate's pages leave out, and why.** Who spoke. Across all 491
Senate journal files "spoke in favor" occurs four times and "spoke against"
twice, and every one is ordinary English inside a speech rather than a marker
-- the Senate journal does not record who spoke on which side. The Senate's
RECORD is in `session_days`, so a Senate page carries bills, motions and
votes without a debate section.

**Numbers.** `python3 src/parse/journal_days.py --coverage` prints what the journal
parse finds, corpus-wide.

**A defect this uncovered.** The calendar was calling committee meetings the
floor. A row with no committee was labelled "House floor" or "Senate floor",
and only about half of the committee-less rows in `proceedings.csv` are floor
debate; the rest are hearings, work sessions and committees of
conference whose committee the docket did not record. Fixed in
`build_calendar.floor_name`.

**How a sitting day is reached, since 2 October.** Until then a past sitting
had a link only from the sitting next to it: 62 of 1,563 had one from
anything else. Three things lead to one now, and each asks the same question
first, which is whether the page was built.

- *The date of a vote.* A roll call on a bill and a row of a member's votes
  name the day and the chamber, and `app.js` draws the date as a link
  (`sittingLink`). It asks `site/session/days.json`, the list of the pages
  `build_session_pages.py` wrote, written by that step a chamber at a time
  with the other chamber's list kept. A date not on the list stays text.
- *The directory.* `/directory/sessions-house` and `/directory/sessions-senate`
  list every day by year (`build_indexes.sessions_pages`).
- *The line up.* Each sitting leads to its chamber's list, and to its week on
  the Calendar where the calendar has that week.

The home page, the lists and that line are written **before** the pages and
the weeks they link, so on a machine that starts empty none of them can read
the disk. `build_session_pages.sittings()` is the one rule for which days get
a page, and `build_calendar.week_keys()` is the calendar's own reading of
which weeks do; the earlier steps ask those.

## Keeping the keyboard's place

A navigation and accessibility audit on 2 October measured the built site in
a browser with real key presses. What it changed in how the code works:

**A redraw gives focus back.** `app.js` draws by replacing markup, and the
control that had focus is replaced with it. `render()`, `renderPage()` and
`renderFacets()` each take the key of the focused control before they draw
(`focusKey`: its id; or its tag and data attributes, inside its card; or its
tag and classes; and its place among what that matches) and focus the control
with that key after (`refocus`), but only if the redraw took focus away. A
new control inside those three needs nothing, provided it has an id or a data
attribute that says what it is. "Show more" is deliberately given no key: its
own handlers put focus on the first card, or the first vote, it brought,
because the redraw replaces the whole list and the browser's own starting
point is then the top of it.

**The address, and what going back means.** `app.js` writes the address in
four places (`tabAddress`, `focusBill`, `unfocus`, `addressSearch`) and each
calls `addressed()`, which keeps two things true: the skip link names the
document as it is addressed now, and `STOOD` holds the address without its
fragment. `popstate` needs the second. A link to a place on the page, which
the skip link is, fires `popstate` with no state, and so does going back from
a bill to the list; where only the fragment moved, or the address is still a
bill's own (`BILL_PATH`), nothing is redrawn. A bill's own page never leaves
for `/bills` because of one. "Back to bill search" goes back in history only
where this entry is the one `focusBill` pushed over the list (its state says
so) or, on a bill's own page, where the referrer is this site's `/bills`;
where the address itself opened the bill in the search (`/bills#2025/HB2`) it
draws the list in place. A search run from a bill's own page goes to
`/bills?q=`, with `term=` where the picker beside the box names a term that
is not the newest.

**The header's menu and search** (`find.js`) put focus inside when they open
and close when focus goes somewhere else in the page; focus that goes nowhere
(the window losing it) closes nothing. The search panel has one
`role="status"` line, written by `findSay` from the markup `findDraw` has just
drawn.

**A ring is drawn inside a control that fills a clipping box** (a card's
header, Play, a filter group's head), and **a text box's edge is `--edge`**.
`preflight` holds both, and holds `--ink-2` on the Calendar's week band to
4.5:1, computed from the tokens.

**On a phone a control is 44px**, in one block placed after the rules it has
to outrank; a person's chip is its link to the edges. The line above a Learn
article's heading and a sitting's is the exception: there is no 44px between
the row of "Cite this page" and the heading, so the link stays the size of
its words and what can be pressed is laid over it (`::after`), 35px. **On
paper the page is the light theme**: one `@media print` block writes the
light palette again under the dark palette's two selectors, and `preflight`
fails if the two stop matching. What that block leaves off is a control and
never the record: a recording's box prints, with Play set as the line of text
that carries its time. And a ground that carries white marks is asked for
(`print-color-adjust:exact`): `preflight` reads every rule that sets type in
white and fails if one is neither left off the sheet nor on that list.

**A box that scrolls sideways** is marked `data-scrollstop` and `app.js`
(`scrollStops`) makes it a Tab stop only while its content is wider than it
is. **The seat map** listens for focus on the box round the chart, not on the
`<svg>`: Chrome makes an `<svg>` that listens for focus a Tab stop.

**The header's tab strip** is centred on the bar from 1100px, the width from
which it clears the wordmark; below that it sits between its neighbours. The
brand's side padding changes at the same width, and `preflight` holds the two
numbers together.

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
> it refuses a table a fifth smaller than the last (in `main()`) and separately
> refuses a rebuild that loses a fifth of any (term, source) holding at least
> 100 rows (`shrunk_groups()`), both released only by `--allow-shrink`. The
> hand-made files `preflight.py`'s
> `HANDMADE` lists live where no generator writes, and `preflight` fails if a
> `build_*` or `fetch_*` script opens one.
> Kept because the rule is only as good as the next writer somebody adds.

`build_manifest.py` overwrote the manifest twice, taking the hand-marked times
with it. `python3 src/hearings/segment_markers.py --transcript X` wrote a candidate file containing
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

**Converted one file at a time.** What is worth keeping is why each mattered
and what the conversions turned up.

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

**`testimony.json` is retired** (5 October 2026), with `fetch_testimony`'s
step: all 565 of its bills were in `testimony_db.json`, so no page ever showed
one of its counts, and `testimony_from_db.py` rebuilds the database's 2,019
bills of 2025-2026 from the dump, every count and hearing equal -- and after
the turn from the term's freeze. Read by number for the current term, it would
have given 2027's bills 2025-2026's sign-ins.

**When a term ends.** The General Court's files are the current term's, so at
the turn they stop holding the last one. `freeze_term.py` keeps its inputs --
the day files as installed in `frozen/<term>/`, the database's views in
`db/term/<term>/`, `Docket_<term>.txt` and `verification_manifest_<term>.csv`,
the roll calls in `rollcalls/` -- and `python3 src/parse/build_data.py --frozen-terms` builds the
term from them every night once the session's files are the next term's,
whole, marked archived. Rows of a finished term that turn up in new files are
counted and left out, never merged, in every reader that would otherwise
replace or skip a whole term; `snapshot_gencourt` refuses files that name a
newer term whatever their size, and only the New term run takes them, once the
term it leaves is frozen as installed. `proceedings.session_term()` is the one
answer to which term the session's files describe, read from the same six
files the guard reads. `tests/rehearse_turn.py` runs the turn's nights on a
copy.

**Organization Day can come first.** The General Court's roster may show the
next House nights before its files show the next term, and `LsrsOnly.txt` lists
sitting members only. So a roster that is not the term's own goes in only once
the term's roster is frozen (`snapshot_gencourt.roster_moved`, and the
database night's `roster_frozen`), and from then until the switch the term's
members and sponsor files are the freeze's (`freeze_term.own_roster_terms`):
`build_data` reads its sponsors from the frozen `LsrsOnly.txt` and
`LsrSponsors.txt` and names them from the frozen roster, a continuing member's
ballots keep the party and seat of that roster, `narrative.py` tells its
histories with it (`build_all.session_roster`), and `build_site_v2` labels the
term's sponsors from it -- a member now in the Senate under a new id reads as
the Representative they were -- for a finished term as for the session's.
`freeze_term --session` refuses a roster whose members sponsored and voted
nothing in the term, and keeps the freeze's roster over one that has turned.
The rows of a finished term a night's files still carry go on the run's page
(`data/left_out.json`). The New term run lets only the feeds fall, and asks for
a freeze only while the installed files are in the last session of their term,
so a term's second January passes as a new session year.

**Fix, for what is left: `(term, bill)` everywhere.**
`obsolete/probe_archive.py` and `obsolete/setup_archive.py` sketched this;
the per-term files took a different road, `{term: {bill: ...}}` inside each
file. The year-keyed journal and calendar citations were part of the same
job.

### 4. The deployment has a file cap

> **Resolved.** The plan is Pro, so the cap is 100,000. And an archived
> bill is one file rather than two: its record travels inside its own page,
> except for those over 100 KB which keep a file the page points at. A
> current-term bill costs more: its text versions sit under `versions/`, and
> one still moving has a feed. `STATE.md`, which `python3 handoff.py` writes,
> has the current count, and the nightly's gate line prints it on every run.

**The site is on Cloudflare's Pro plan**, which raises the limit from
20,000 files to 100,000. Two things to know, and the second is the trap: it
needs the environment variable `PAGES_WRANGLER_MAJOR_VERSION=4` set in the
Pages project, and it is the Pro *zone* plan, not Workers Paid -- several
people have reported the 20,000 limit still enforced after upgrading the
latter.

`check_site.py` warns once the site passes 90,000 files, and the nightly will
not deploy past 95,000. Run `python3 src/checks/check_site.py` for the count rather than
quoting one.

### 5. Long functions where declaration order is load-bearing

**One of the three is gone rather than split.** `build_bill_pages.py` was 909
lines rendering every bill a second time in Python, beside `app.js` rendering
the same bill from the same JSON in the browser. It renders no bill
now: a bill's page is `bills.html` with one bill open, and what
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

> **Both halves of this are done.** `renderDetail` is in `app.js` now and
> calls one function per tab -- `renderSummary`, `renderVotes` and
> `renderHearings` among them; the Bill Text tab reaches `renderBillText`
> through `billTextSection` -- and `station_for_proceeding` and
> `station_for_floor` are top-level functions in `build_site_v2.py`. Kept as
> written because the failure it describes is the one the splits were done to
> stop.

`renderDetail` in `bills.html` was 472 lines and one function, with 26 `const`
declarations. Three times in a day a template literal read one of them before
its line ran, and the page died with the data already in hand. A lint that skips
template literals cannot see it; the runtime check only caught it once
extended to the focused view, which is the branch where two of the three lived.

`build_site_v2.py` was 1,672 lines and its `main()` built every station,
document, sponsor and amendment for every bill in one pass. The floor-marker
bug in item 1 happened because the committee-station code and the floor-station
code were 90 lines apart in the same function and only one of them was changed.

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
> real recordings -- `MUST_MATCH` and `MUST_NOT_MATCH`, which
> `python3 tests/test_markers.py` counts when it runs -- and `preflight`
> runs it. Kept because the reason it was needed is the reason it must be
> maintained.

Every fix was verified by a fixture written in a heredoc and thrown away.
`OPEN_RE` has been through nine revisions and the phrasings it must match are
scattered across those heredocs. When someone
changes it in six months, the only way to know what broke is to re-run the
whole marker pass and score it.

**Fix: a `tests/` directory** with the real phrasings as cases, grouped by
where each was found: the seven read by hand, the seven from `--gaps`, the
thirteen from `--phrases`, the five floor forms, the five things that must not
match. Twenty lines each. That is the 32 and 5 the file was first committed
with. `preflight` runs them.

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
That was overtaken: old terms carry their own text in `archive_text.json`,
which `archive_text.py` builds with no network from the pages saved under
`legislation/<year>/` and, for some 2018 bills, from `PastLegislationText`.

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

`LegislationText.LegislationTextID` is a different id space -- HB1442 is
`legislationID` 1937 and has seven `LegislationTextID`s, 23441 among them --
and the legacy URL uses `legislationID`: 1937, not 23441.

---

## What the database actually covers, measured 6 September

What the database covers is not what the table names suggest. Asking
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

The General Court's IT office has since added six views of past sessions,
first read here on 26 September 2026, and `fetch_past_db.py` has put them in
`db/past/`. `PastLegislation`, `PastSponsors`, `PastDocket` and
`PastLegislationText` hold rows for every session year from 1989 to 2024, so
the years the `docket` table lacks, and the titles and sponsors `Legislation`
and `sponsors` keep for the current term alone, are on this disk for past
terms too. `PastCommitteeReports` and `PastAmendments` begin in 2016.
`past_sponsors.py` matches `PastSponsors` to bills by LSR, `archive_text.py`
reads `PastLegislationText`, and
`python3 src/fetch/gc_db/fetch_past_db.py --list` says what is here.

---

## What a year's page actually carries, measured 7 September

`probe_archive_shape.py` takes a couple of bills per session year, fetches each
one's status page once into `archive_samples/`, and reports what
`fetch_bill_status.parse()` -- the parser the real fetch uses -- gets out of
it. Eighty requests, and it settles what a year's page carries.

- **`Bill_status.aspx` serves a 1989 bill**, in the same shape as a 2026 one:
  title, LSR, body, both chamber statuses, committee, dates, chapter and the
  local-government flag. The archive is reachable.
- **Sponsors are the exception, and they are the finding that matters.** 8 of
  8 bills sampled from 1989 carry none; 1992 and 1995 carry one each across
  seven and six bills. They become reliable only in the mid-2000s. The
  database's `PastSponsors` view does go back, to 1989, as the section above
  says.
- **Every year links its bill text; only the address and the label change.**
  All 80 pages sampled, 1989 to 2026, carry a plain `<a href>` to it. The
  older form is `/legislation/<year>/HB0169.html`, labelled "Bill Text" up to
  2012 and "[HTML]" and "[PDF]" for the three years after, which is why
  grepping for the words "Bill Text" finds nothing there; 2016 onwards use
  `billText.aspx?id=`. Nothing here is an ASP.NET postback: `__doPostBack`
  occurs zero times in the 81 saved files, and "Bill Docket" is an ordinary
  anchor as far back as 1989. `TEXT_ID` in `fetch_bill_status.py` matches
  `billText.aspx?` and looks for nothing else, so to that parser the older
  form reads as absent. That older form is the address
  `fetch_legislation.py` builds.

Two cautions about the method, both learned the hard way. The first version
matched its own regexes and reported that no year carries sponsors, *including
2026* -- an hour after the same parser had pulled sponsors off 1,865 of the
1,996 bills of 2023-2024. A confident, tabulated, wrong answer. And two bills
a year cannot tell "the field does not exist" from "this bill never reached
the Senate", so the year-to-year flicker in that table is sample noise; the
sponsor question only became an answer when four years were widened to seven
or eight bills each.

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

The general fixes matter more than the two members: it reads an archived
year's roll call files, it no longer skips a blank PersonID, and "already
known" now includes the **676** members in
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

## Veto messages

**The two chambers print a veto message differently**, which cost four
readings of the artefact. The House prints the full text in its calendar; the
Senate mostly prints "PENDING VETO MESSAGES: SENATE BILLS: 268" and carries
the text only in the veto-session editions. Between two governors and two
chambers there are four signature shapes, and nine of Ayotte's Senate messages
state no date anywhere -- so the page shows none for those rather than
borrowing the docket's, which is the day the veto reached the chamber and not
the day it was signed.

## Comparing two builds

A change that is meant to leave the site alone is proved by building it before
and after and comparing a sha256 of every file. The day a build is made is in
every page -- it is the date a citation falls back on for a reader without
JavaScript -- and in the sitemap, the feeds, `home.json` and the downloads'
manifest, and a dozen builders ask what today is to decide what is still to
come. So two builds made on different days differ in every page.

`GRANITE_BUILD_DATE=2026-10-02` states the day instead, or
`2026-10-02T01:22:13` the moment, for every builder: `build_date.py` is the
one place the build's day is read, and `preflight` fails a script on the
build's path that asks the clock for itself. It is for comparing builds, not
for publishing one -- `build_all.py` says when the day is stated and records
it in `site/build.json`, whose own `finished` and step times stay the clock's
and are left out of the comparison. Without the variable nothing changes.

## Known rough edges

Each is described where it belongs; this is the list in one place.

- `build_bills` and `main` are the two longest functions in
  `build_site_v2.py`, each several hundred lines. Item 5 says why length is a
  hazard there.
- Five tools carry `--manifest default="verification_manifest.csv"`:
  `align_all`, `apply_markers`, `probe_alignment`, `transcribe_and_align`,
  `verify_batch`. Each opens whatever `--manifest` names, so run with no
  flag they open that exact file: real coupling rather than a stale pointer
  (`score_alignment` went to `obsolete/` on 6 October 2026, and
  `fetch_testimony`, which declared the flag and never read it, on
  7 October). `ground_truth.py` is another reader, falling
  back to the literal name when the flag is absent, and `preflight` opens it
  too. `build_proceedings.py` is the one that has moved -- it globs every
  `verification_manifest*.csv` rather than naming one -- and its own docstring
  says the intermediate goes away once every reader has followed. These
  defaults are the readers that have not.
- **`python3 src/hearings/build_manifest.py --keep-marks` is not vestigial; its help text is.** Every manifest this
  writes carries `observed_start` and `observed_end` -- all nineteen on disk
  have both columns, and `verification_manifest.csv` has 35 rows filled, put
  there from `ground_truth.csv`, which outranks anything in an old manifest
  (in `build_manifest.main`). The other eighteen carry the columns empty,
  because every mark names a current-term video. A flagless rebuild also falls
  back to the file it is about to overwrite, which is what makes forgetting the
  flag harmless, so what the flag is actually for is reading marks out of some
  *other* file. The help still says they "are lost on every rebuild" without
  it; that is the sentence to fix.
- Item 6's primitive was never written -- `find_in_transcript` appears nowhere
  but in the paragraph proposing it, so every other matcher still builds its
  own window.
- The site stores one party per person, not per term, and a comment in
  `resolve_members.py` still says 675; both are under *Members the record
  cannot name*.

## What scales

The things that scale already: the marker method (per recording, cached, one
second at the median), the bulk-file pipeline, the narrative rules. The things
that do not: per-bill text fetches, and any tool that assumes one term.

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
