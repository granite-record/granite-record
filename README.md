# Granite Record

A public record of the New Hampshire General Court, live at
**[graniterecord.org](https://graniterecord.org)**.

Every bill the legislature has filed since 1989 — who sponsored it, what
happened to it, how each legislator voted — and, for the terms with recordings,
the moment in the video where a committee actually took it up.

The General Court publishes all of this already. It publishes it as fixed-width
dumps, PDF calendars, an ODBC database, and a search page that wants a bill
number you already know. This turns that into something a person can read and a
program can use.

```
33,683 bills across 19 terms, 1989 to 2026
   406 sitting legislators, and 2,192 people with a recorded vote since 1999
        hearings and floor debates for all 19 terms, one manifest per term
        and, where a chair said so aloud, the second the bill was taken up
```

The last two lines carry no figure on purpose: every version of this block that
named one was stale within a week. `python3 src/ops/handoff.py` writes the current
counts into `STATE.md`, which is generated and is the copy to believe.

## What's where

| Folder | What it holds |
|---|---|
| [`src/`](src/README.md) | the code, one folder per job: what asks other servers, what decides the record, what writes the pages, what checks them, and in `src/ops/` the tools that keep the site running |
| [`corrections/`](corrections/README.md) | what a person corrects or adds to the record by hand — a date the docket gets wrong, a member's name, a polling place, what a recurring bill number means, the voters' answer on each amendment, the state of the session. No script writes here |
| [`review/`](review/README.md) | a person's checks of the site's own work: proceedings timed with a stopwatch, and the bench's judgments |
| [`records/`](records/README.md) | official lists and documents as published: every past session's roll calls, the district lists, the Secretary of State's documents |
| [`collected/`](collected/README.md) | what was gathered from outside sources and git keeps: the YouTube channels' video indexes, the towns' clerks and officials, the county officers |
| [`generated/`](generated/README.md) | what is computed ahead of time and kept: careers, places, the topic model's settings, the timestamp scores |
| `functions/`, `workers/` | the Cloudflare code: the report box's endpoint, and Workers deployed on their own |
| `watchers/`, `tests/`, `obsolete/` | the General Court fetch lane, the tests and their fixtures, retired code kept for its reasoning |
| `assets/`, `reports/`, `data/unh/` | one file each that git keeps where the rest is not: the web app manifest, the report box's database schema, and a survey of the University of New Hampshire's scanned journals |

The root holds what something outside the repository runs by name
(`build_all.py`, `nightly.py`, `preflight.py`, `refusal.py`, `netcheck.py`,
`laptop_evening.py`, `publish.bat`), `_paths.py`, the config and these
documents — and, untracked, the General Court's day files as the night
installs them and everything the build writes (`site/`, `data/` and the JSON
beside them), which `.gitignore` names. Each folder's README says what is in
it and what reads it.

**Three things worth knowing before you read the code.**

*It is files on a CDN.* Every page is static HTML, every record is JSON. A full
rebuild takes about twenty minutes and produces a directory you can serve with
anything. That constraint is deliberate: a public record should not stop
working because a bill went unpaid or a runtime got deprecated. One endpoint is
the exception and is the only thing here that runs:
`functions/api/report.js`, which takes a reader's "this is wrong" report. It is
write-only, on no page's critical path, and the box on the page falls back to
an email link when it is down.

*Nothing that cannot be checked is published as though it could be.* A
timestamp taken from a chair saying "we'll open the hearing on House Bill 1123"
is presented differently from one a model guessed, and where neither exists the
page says so and links the recording. There is a file of proceedings somebody
timed by hand with a stopwatch, and every timing method is scored against it
before it ships.

*The checks are the design record.* `preflight.py` holds several hundred of
them — its summary line gives the number — and most exist because something
broke in a way a check could have caught. Each one's docstring says what that
was. It is the fastest way to learn where the sharp edges are.

---

## Quickstart

You need **Python** and **NumPy**. Node is optional but wanted — the checks
load the front end in it, and skip those checks when it is missing.

```
git clone https://github.com/granite-record/granite-record.git
cd granite-record
pip install numpy
```

Python 3.14 is what this is developed and run on. Nothing in the code checks
the version, so an older 3.x may be fine; that is untested.

**Run the checks first.** Most of them work on a bare clone, because
`preflight` synthesises the data it needs in a temp folder and builds a fixture
site on it:

```
python3 preflight.py --code     # the checks that need no data on disk
```

On a fresh clone the summary ends **`0 failed`** with some skipped. That is
the expected first run, not a fault: the skipped checks read the real built
`site/` or the record, which a clone does not have, and they say so one by
one. The number to watch is the failures; the counts move as checks are added,
so take them from the summary rather than from here.

It takes a few minutes. **Trust its output over anything written in prose,
including this file.** If it is not green, that is the thing to fix before
anything else. `python3 preflight.py` with no flag adds the data checks,
which need the record described below, and takes longer.

### A clone has the code, not the record

The repository is the Python scripts, the front end, the documents, the
files a person made by hand, and the data in the five folders of
[What's where](#whats-where); `git ls-files` lists them. The General Court's
**live** bulk dumps and everything derived from them are deliberately
untracked — they are the state's, they are large, and they change daily, so
tracking them would store a new copy of a 4.7 MB file every day.

What does not change is tracked. `records/rollcalls/` carries the roll-call history
since 1999 as the General Court published it, a summary and a history file
for each year — about 100 MB, and most of the reason a clone weighs what it
does rather than a few megabytes. The General Court's two small code tables,
`GeneralCodes.txt` and `BodyStatusCodes.txt`, are tracked too, at the root
beside the day files the night installs there.
`.gitignore` says which files and why.

Four things are absent on purpose and are not missing:

- `secrets.json` — a YouTube API key, wanted by one step of the pipeline, which
  skips and says so without it. Nothing else in the repository needs a
  credential, and `preflight` has a check that no tracked file carries one.
- `work/` — the recordings' caption files, about 20 GB, and the audio of a few
  dozen transcribed here, about 15 GB; all of it re-fetchable.
- `site/` — the built output.
- the logo and the icons — used under licence and not part of the open-source
  release, so there is no `brand/` and `assets/` holds one text file. The build
  runs without them and says so once: the header is the site's name alone, the
  home page's heading is text, and `check_site.py` reports the missing icons.
  [`DATA.md`](DATA.md) says how a fork brings its own.

So `build_all.py --local` on a fresh clone has almost nothing to build from,
and it will **skip rather than fail**. If you only want the data, take it from
[graniterecord.org/data](https://graniterecord.org/data) and skip the build
entirely.

To get the record, `src/fetch/gc_web/snapshot_gencourt.py` fetches the
fourteen bulk files. That is fourteen requests to somebody else's server —
read **[Fetching, and the one hard rule](#fetching-and-the-one-hard-rule)**
before you run it.

```
python3 src/fetch/gc_web/snapshot_gencourt.py --plan                       # what it would ask for; makes no request
python3 src/fetch/gc_web/snapshot_gencourt.py --dir nh-archive --into .    # fetch, then install for the build
```

### Then build

```
python3 build_all.py --dry-run      # the plan: every step, its command, and why it matters
python3 build_all.py --local        # every step that asks no network
python3 src/ops/inventory.py        # what is on disk, and which scripts are stale
python3 src/ops/handoff.py          # writes STATE.md with the counts as measured
```

`--local` takes the better part of an hour on the full record; every run
records its total and its per-step timings in `site/build.json`, which is the
figure to believe. `src/ops/handoff.py --print`
prints instead of writing `STATE.md`.

`site/` is then a complete static site:

```
python3 -m http.server 8787 --directory site
```

---

## How it fits together

**How the code is laid out.** The repository root holds only what something
outside the repository runs by name — `build_all.py`, `nightly.py`,
`laptop_evening.py`, `preflight.py`, the refusal tools (`refusal.py`,
`netcheck.py`) and `publish.bat` — with `_paths.py`, the config and the
documents; the data a clone carries is in the five folders of
[What's where](#whats-where). Everything else is under `src/`, in one folder
per job: `fetch/` (one folder per whose server it asks), `parse/`, `towns/`,
`hearings/`, `pages/`, `checks/`, `lib/`, and `ops/` — `cloud.py`,
`livestreams.py`, `compile_reports.py` and the session's first commands
(`inventory.py`, `handoff.py`), which the workflows and a person run by
their path.
The front end (`bills.html`, `components.js`, `app.js`, `find.js`,
`app.css`, and a bill's print sheet, `print.js` and `print.css`) is in
`src/pages/` with the builders that read it, and the `dom_stub.js` that
`preflight` loads it against is in `tests/`.
[`src/README.md`](src/README.md) has the tree, what each folder holds, and
where a new file goes. Run a script under `src/` from the root by its path
(`python3 src/parse/narrative.py`); imports and the pipeline's steps use bare
names, which `_paths.py` resolves, so a file can move without anything that
names it changing.

**`build_all.py` is the pipeline.** `--dry-run` lists every step, the command
it runs and why it matters; `--local` leaves out the steps that touch the
network, and a step marked superseded does not run unless asked. Each step
declares what it needs and what it produces, prints what it did, and skips
loudly when an input is missing. A failed required step ends the run unless
you pass `--keep-going`.

**Data flows in one direction.** The General Court's bulk files and page caches
→ `src/parse/build_data.py` → `data/` (intermediate JSON, untracked) →
`src/pages/build_site_v2.py` → `site/*.json` → the page builders in
`src/pages/` → `site/`. Two different things are called *data*: `data/` in
the repo root is generated scratch with no published schema; `site/data/` is
the published CSV, documented by its own manifest.

**How it runs.** Every night GitHub Actions builds `main` on an empty machine
(`.github/workflows/nightly.yml`, which runs `nightly.py --runner`): it takes
the day's files from the General Court — from its SQL host instead, when the
export comes back empty — rebuilds the site with `build_all.py --local`
(less the steps that read caption files, which that machine does not hold),
checks it, and puts it on a preview address; production waits for a person's
approval. Everything the build reads that git does not hold comes down from a
private R2 bucket through the list in `cloud_kit.json`. `ARCHITECTURE.md`
says how the night, the term turnover and the caption job fit together.

**`proceedings.csv` is the one table.** One row per (bill, date, kind,
recording), whether it is a committee hearing or a floor debate, read through
`src/lib/proceedings.py` by everything downstream.
`src/hearings/build_proceedings.py` builds it from every
`verification_manifest*.csv` — one per term, nineteen of them — plus the
floor index, and globs them all on every run so that no writer ever sees a
subset. It exists because those sources used to be read separately, and five
tools in one day were found to be silently excluding floor debates — each
presenting as a different bug. Do not add a sixth reader of the old files, and
do not give it a `--term` flag.

**There are two id spaces, and both bite.** A bill is a *term plus a number*:
bill numbers repeat every biennium, so every per-bill file is
`{term: {bill: ...}}` and `preflight` refuses the old shape. A legislator is
*not* an employee number: the roll call record keys ballots to an
`EmployeeNumber`, and a member who moves from the House to the Senate is issued
a second one. `src/parse/build_careers.py` merges those into one person per
record — narrowly, on identical names with non-overlapping service — and
`generated/careers.json` is the result.

**Where a bill page comes from.** `src/pages/build_bill_pages.py` writes
`/bill/<year>/<id>.html` using `src/pages/shell.py`, which is
`src/pages/bills.html` with one record open. The record itself travels inside
the page, in a `<script type="application/json" id="gr-data">` block, and
`src/pages/app.js` renders it.
A bill page and a search result cannot disagree about a bill, because they are
the same code reading the same JSON.

**Every script carries a version stamp** (`# GRANITE_VERSION: YYYY-MM-DD.N`)
and `versions.json` says what each should be. `preflight` fails when they
disagree, which has caught several half-applied edits.

`ARCHITECTURE.md` has the reasoning behind all of this, and the parts that are
not sound.

---

## Where to change things

`python3 build_all.py --dry-run` prints the plan, with the command each step
runs. The plan names each script by its bare name, which `build_all` finds
wherever it sits under `src/`; to run one by hand, give its path, as the table
does. The plan leaves some steps out: the superseded step needs
`--with-superseded`, and the General Court steps are held back while
`archive/.lock` or `archive/refused.json` exists. The ones people most often
want:

| I want to change… | The file |
|---|---|
| how any record page looks | `src/pages/app.js` — one `render…` function per tab (`renderSummary`, `renderVotes`, `renderHearings`…); `BILL_TABS` maps slug → tab |
| what data a bill page *has* | `src/pages/build_site_v2.py`, which assembles the payload |
| how a person, a committee, a date or a time is drawn, on every page | `src/pages/components.py` for the pages built in Python and `src/pages/components.js` for the ones drawn in the browser: the same helpers under the same names, which `preflight` holds to one answer on `tests/components_cases.json` |
| the frame every record page is built in | `src/pages/shell.py` — every page builder in `src/pages/` imports it |
| what the search does | `src/pages/bills.html` + `src/pages/app.js` (the lines between its `BILLMATCH` marks, which `src/pages/build_pages.py` cuts into `billmatch.js` for the header's `src/pages/find.js`); what each bill is about, `src/pages/build_search_index.py` |
| the plain-English history under a bill | `src/parse/narrative.py` (sitting terms), `src/parse/narrate_archive.py` (archived) |
| which subject a bill is filed under | `src/parse/topic_model.py`, and `src/parse/topics.py`, the baseline it imports |
| committee, member or town pages | `src/pages/build_committees.py`, `src/pages/build_legislator_pages.py`, `src/pages/build_town_pages.py` |
| the plain lists of every bill, member and town | `src/pages/build_indexes.py` |
| the civics explainers under `/learn` and the Resources hub, `/resources` | `src/pages/build_civics.py`, which reads `src/pages/civics.py` (the writing and its diagrams) and `src/pages/learn_numbers.py` (The Record in Numbers) |
| the CSV downloads and `/data` | `src/pages/build_exports.py` |
| the RSS feeds | `src/pages/build_feeds.py` |
| what changed each night, for the email updates | `src/pages/follow_changes.py`, called by `build_feeds.py` |
| where a hearing sits in a recording | `src/hearings/segment_markers.py`, scored by `src/hearings/probe_alignment.py` |
| which rows exist at all | `src/parse/build_data.py` → `data/`, then `src/pages/build_site_v2.py` → `site/*.json` |
| a fact the General Court's own record gets wrong | `corrections/` — its README says which file, and which step reads it |
| towns, districts and their officials | `src/towns/` |
| look and type | `src/pages/app.css`; `style.css` in `site/` is generated from it |
| the pipeline, or its order | `build_all.py` — one `Step(...)` per entry in `plan()` |
| the night on GitHub | `nightly.py`, and `.github/workflows/nightly.yml` that runs it |
| what counts as correct | `preflight.py` — each check's docstring names the incident behind it |

---

## The data

The site's own JSON is served from the same origin as the pages, at stable
addresses:

| | |
|---|---|
| `/idx/<term>.json` | one term's bills — title, sponsor, committee, topic, status, the chip's word (`chip`: Became Law, Died, Interim Study, Tabled, Vetoed, Withdrawn, or a word of its own), passage, and its dated rail (`rail`: each stop, its mark, its day and a word or two of how it went — the card draws the day, and says the words to a reader who hears the page) — and what the bills page and the search load. Every term's file together is every bill of every term; `/data/manifest.json` lists them with their addresses, bills and sizes. They replace `/index.json`, the same rows in one file, retired on 5 October 2026 at nine tenths of the 25 MiB a file may be |
| `/sidx/<term>.json` | what each of that term's bills is about, from its analysis and text: for each word, the bills it is central to and how central, and for each bill the pairs of those words that stand next to each other, each pair as five letters of a hash. The search fetches it when somebody searches. `/sidx/manifest.json` says what each file holds and weighs, and `/sidx/words.json` is every word of five letters or more that any bill of any term uses, with the names of members and towns and without the record's own slips ("goverment", in one bill): what tells a misspelt search from a real word no bill is about |
| `/legislators.json` | the roster — who holds a seat now, with districts, towns and committees |
| `/former.json` | the people in the record who hold no seat now, with the span of their record. Deliberately a separate file: everything that reads the roster reads it to mean "who serves today" |
| `/rollcalls_index.json` | every recorded vote — tally, whether it passed, party split, and a plain-English question where one could be made |
| `/officers.json` | who held the chair's offices — the Speaker, the Deputy Speaker and the Speaker Pro Tempore of the House, the President of the Senate — from which day to which, each with the member it names and the sentence of the House or Senate Journal or the House Calendar it was read from |
| `/session/<H\|S>/<term>.json` | one chamber's session days of one term, oldest first: each day's journal and counts, who presided (the roll calls' presiding ballots and the journal's turns in the chair, with the office the record gives them that day), the members excused counted by party, the consent calendar's outcomes and the bills taken off it, and every bill voted on that day with each vote in order — motion, amendment numbers, result, count, the roll call's id (`rollcall`, as `/rollcalls_index.json` keys it) and its card on the bill's Votes tab (`card`) — and the committee recommendation the chamber acted on |
| `/committees.json`, `/towns.json`, `/districts.json` | membership and geography |
| `/district_map.json` | the district map's one file: NH GRANIT's 2022 boundaries for every State House, floterial, Senate, Executive Council and US House district, county and town, simplified at 100 ft on shared arcs in New Hampshire's own State Plane feet (EPSG:3437, 100-ft units, y down); every town and ward with the districts it votes in; and who sits for each district, with the party letters the map fills it with. Not for legal use: the Secretary of State's published definitions are the legal text |
| `/feed/*.xml` | RSS: everything, upcoming hearings, and one feed each per topic, per legislator, per bill still moving, and per committee that is not archived and has a sitting day or a bill on record — so `/feed/committee/` holds fewer feeds than `/committees.json` has rows. An archived committee's would never change again |
| `/changes/current.json`, `/changes/<date>.json` | what changed, night by night: what can be followed tonight and what is scheduled, and for each of the last eight nights what was new for each bill, member, committee and topic — the feeds' own items and ids, filed under the night each first appeared. Rewritten every night, and nothing in them is about a reader |

Every table is also downloadable as CSV from
**[graniterecord.org/data](https://graniterecord.org/data)** — bills, votes,
sponsors, roll calls, legislators and proceedings. `/data/manifest.json` lists
each one with its rows, size and column names, and each term's `/idx/` file
with its address, bills and size, so a program can discover what is there in
one request, and how much, without a figure here going stale.

That manifest also carries a per-term coverage table, and it is the honest
answer to "how far back does this go". Titles, topics, committees and passage
run the full 19 terms. Named sponsors do not: the nine terms from 1989-1990 to
2005-2006 name fewer than twenty each, and 2007-2008 and 2015-2016 are only
part-filled. **An empty column is a record not yet collected, not a bill
without one.**

If you are building something and the shape is awkward, say so — the point of
this is to be used.

### Fetching, and the one hard rule

**Do not point a `fetch_*` script at the General Court without asking first**
— <contact@graniterecord.org>. This address has been blocked by their firewall
twice: once for probing filenames that did not exist, once for running two
fetches at the same time. Getting blocked again costs days and an email to a
Clerk's office.

Fetches run one at a time, slowly, and a refusal ends the run rather than being
retried around: `refusal.py` records it in `archive/refused.json`. A fetch
started by hand stops at it for 24 hours; the fetch lane, `build_all.py`'s
General Court steps and the nightly stop at it for as long as it is on file,
because clearing it is a person's decision (`python3 refusal.py --clear`,
after `python3 netcheck.py` has said what kind of refusal it was). Every
script that asks gc.nh.gov, but `netcheck.py`, consults the record before
its first request and records a refusal it meets, and `preflight` fails one
that does not; those scripts live in `src/fetch/gc_web/`. The machinery stops
a run that meets a refusal. It does not make starting one safe, so the rule
above still stands.

The `fetch_*_db.py` scripts read the SQL host the General Court publishes
credentials for, not the web server that did the blocking. Still ask — but a
refusal there is a different problem.

---

## Contributing

`CONTRIBUTING.md` has the detail. The short version:

- **Run `python3 preflight.py` before and after.** That is the test suite:
  checks that build the whole site on a fixture, load the front end in node
  and call `render()` and `renderDetail()`, and run `tests/test_markers.py`.
  Add a check whenever something breaks in a way a check could have caught —
  that is how most of the current ones got there.
- **Bump the `# GRANITE_VERSION:` stamp and `versions.json` in the same edit.**
  Increment the `.N`; leave the date alone. This is the most common way a first
  change fails.
- **Some files are a person's, and no generator writes them.** They are in
  `corrections/` and `review/`, and a check enforces it.
- **Nothing about timestamps ships without scoring it first**, with
  `python3 src/hearings/probe_alignment.py --truth`. The number to watch is the candidate median;
  do not let it regress.
- **A writer of a derived file, run on a subset, destroys the rest.** This has
  happened four times, across three tools — `ARCHITECTURE.md` has the list.
  Writers merge; a full rebuild is an explicit flag.
- **Say when something is a guess.** An invented number stated plainly costs
  more than an admission of not knowing.

---

## Unfinished

Honest list, not a roadmap.

- **No issue templates.** `CONTRIBUTING.md` and `SECURITY.md` exist; neither
  has been through a round with anyone but us.
- **Sponsors are uneven by term.** The General Court's own sponsor files and
  saved bill pages do not reach every term equally, and `/data/manifest.json`
  says how many bills of each term carry one.
- **`proceedings.csv` reaches all nineteen terms**, but what is behind it is
  uneven: a term whose docket came from the database dump has no recordings to
  match against, because the House streamed nothing before May 2020.
- **Email following is designed and not built.** RSS is live.

---

## Licence

**MIT** — see [`LICENSE`](LICENSE). Use it, change it, sell it; keep the notice.

That covers the software and the texts this project writes: the plain-English
bill histories, the explainers under `/learn`, and the editorial notes on
particular bills. It does not cover the underlying record, because it cannot —
the bills, votes, calendars and recordings are the State of New Hampshire's,
and facts are not copyrightable. [`DATA.md`](DATA.md) separates the three.

The logo and the icons are the exception to all of it, and they are not in the
repository: the logo is an artist's drawing and the icons are bought clipart,
used under licences that are not the project's to pass on. A fork should bring
its own; `DATA.md` says which files that means and what the build does without
them. Commits from before the clipart was removed, on 1 October 2026, still
carry it; it was never offered under MIT.

---

## Where to read next

- **`ARCHITECTURE.md`** — how the code and the data work: what is sound, what
  is not, and why. Written by measuring rather than remembering.
- **`DATA.md`** — what each published file holds, and which licence covers
  what.
- **`CONTRIBUTING.md`** — how a change is made and checked.
- **`src/README.md`** — where the code lives, and where a new file goes; each
  folder under `src/` has a README of its own, and so does each data folder.
- **`CLAUDE.md`** — the working rules: what may not be run without asking, and
  why each rule exists.
- **`STATE.md`** — generated by `handoff.py`. Never edit it; run it again.
- **`watchers/README.md`** — the long-running loops: what each one is, which
  are superseded, and how to find out what is running before starting a second
  copy of it.

The project's plans, design briefs and working notes are kept off the
repository, which holds the code and what explains it.
