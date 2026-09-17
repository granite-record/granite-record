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
54,855 proceedings across eleven terms, on 2,533 recordings
15,758 of those placed at a boundary the chair spoke aloud
```

Those move with every build. `python3 handoff.py` rewrites them into
`STATE.md`, which is generated and is the copy to believe.

**Three things worth knowing before you read the code.**

*It is files on a CDN. There is no server and no database.* Every page is
static HTML, every record is JSON. A full rebuild takes about twenty minutes
and produces a directory you can serve with anything. That constraint is
deliberate: a public record should not stop working because a bill went unpaid
or a runtime got deprecated.

*Nothing that cannot be checked is published as though it could be.* A
timestamp taken from a chair saying "we'll open the hearing on House Bill 1123"
is presented differently from one a model guessed, and where neither exists the
page says so and links the recording. There is a file of proceedings somebody
timed by hand with a stopwatch, and every timing method is scored against it
before it ships.

*The checks are the design record.* `preflight.py` holds 159 of them, and most
exist because something broke in a way a check could have caught. Each one's
docstring says what that was. It is the fastest way to learn where the sharp
edges are.

---

## Quickstart

You need **Python** and **NumPy**. Node is optional but wanted — the checks
load the front end in it, and skip those checks when it is missing.

```
git clone <REPOSITORY URL — not yet set; see "Unfinished">
cd nh
pip install numpy
```

Python 3.14 is what this is developed and run on. Nothing in the code checks
the version, so an older 3.x may be fine; that is untested.

**Run the checks first.** They work on a bare clone, because `preflight`
synthesises the data it needs in a temp folder and builds the whole site on it:

```
python3 preflight.py --code     # the 120 checks that need no data on disk
```

Roughly two minutes. **Trust its output over anything written in prose,
including this file.** If it is not green, that is the thing to fix before
anything else. `python3 preflight.py` with no flag adds the 39 data checks,
which need the record described below, and takes about five.

### A clone has the code, not the record

The repository is 285 files: 131 Python scripts, the front end, the documents,
and the five files a person made by hand. The General Court's bulk dumps and
everything derived from them are deliberately untracked — they are the state's,
they are large, and they change daily, so tracking them would store a new copy
of a 4.7 MB file every day. `.gitignore` says which files and why.

So `build_all.py --local` on a fresh clone has almost nothing to build from,
and it will **skip rather than fail**. If you only want the data, take it from
[graniterecord.org/data](https://graniterecord.org/data) and skip the build
entirely.

To get the record, `snapshot_gencourt.py` fetches the fourteen bulk files.
That is fourteen requests to somebody else's server — read **[Fetching, and the
one hard rule](#fetching-and-the-one-hard-rule)** before you run it.

```
python3 snapshot_gencourt.py --plan                       # what it would ask for; makes no request
python3 snapshot_gencourt.py --dir nh-archive --into .    # fetch, then install for the build
```

### Then build

```
python3 build_all.py --dry-run      # the plan: every step, its command, and why it matters
python3 build_all.py --local        # 26 steps, no network
python3 inventory.py                # what is on disk, and which scripts are stale
python3 handoff.py                  # writes STATE.md with the counts as measured
```

`--local` took 1,059 seconds on its last run here — about eighteen minutes,
most of it in three steps. Every run records its own per-step timings in
`site/build.json`. `handoff.py --print` prints instead of writing `STATE.md`.

`site/` is then a complete static site:

```
python3 -m http.server 8787 --directory site
```

---

## How it fits together

**`build_all.py` is the pipeline.** Thirty-nine steps are declared; twelve of
them touch the network and `--local` skips those, leaving 26. One more is
marked superseded and does not run unless asked. Each step declares what it
needs and what it produces, prints what it did, and skips loudly when an input
is missing. A failed required step ends the run unless you pass `--keep-going`.

**Data flows in one direction.** The General Court's bulk files and page caches
→ `build_data.py` → `data/` (intermediate JSON, untracked) → `build_site_v2.py`
→ `site/*.json` → the page builders → `site/`. Two different things are called
*data*: `data/` in the repo root is generated scratch with no published schema;
`site/data/` is the published CSV, documented by its own manifest.

**`proceedings.csv` is the one table.** One row per (bill, date, kind,
recording), whether it is a committee hearing or a floor debate, read through
`proceedings.py` by everything downstream. It exists because the two sources
behind it used to be read separately, and five tools in one day were found to
be silently excluding floor debates — each presenting as a different bug. Do
not add a sixth reader of the old files.

**There are two id spaces, and both bite.** A bill is a *term plus a number*:
bill numbers repeat every biennium, so every per-bill file is
`{term: {bill: ...}}` and `preflight` refuses the old shape. A legislator is
*not* an employee number: the roll call record keys ballots to an
`EmployeeNumber`, and a member who moves from the House to the Senate is issued
a second one. `build_careers.py` merges those into one person per record —
narrowly, on identical names with non-overlapping service — and `careers.json`
is the result.

**Where a bill page comes from.** `build_bill_pages.py` writes
`/bill/<year>/<id>.html` using `shell.py`, which is `bills.html` with one
record open. The record itself travels inside the page, in a
`<script type="application/json" id="gr-data">` block, and `app.js` renders it.
A bill page and a search result cannot disagree about a bill, because they are
the same code reading the same JSON.

**Every script carries a version stamp** (`# GRANITE_VERSION: YYYY-MM-DD.N`)
and `versions.json` says what each should be. `preflight` fails when they
disagree, which has caught several half-applied edits.

`ARCHITECTURE.md` has the reasoning behind all of this, and the parts that are
not sound.

---

## Where to change things

`python3 build_all.py --dry-run` prints all 39 steps with the command each
runs. The ones people most often want:

| I want to change… | The file |
|---|---|
| how any record page looks | `app.js` — one `render<Tab>` function per tab; `BILL_TABS` maps slug → tab |
| what data a bill page *has* | `build_site_v2.py`, which assembles the payload |
| the frame every record page is built in | `shell.py` — nine builders import it |
| what the search page does | `bills.html` + `app.js`; the header search index is `build_indexes.py` |
| the plain-English history under a bill | `narrative.py` (sitting terms), `narrate_archive.py` (archived) |
| which subject a bill is filed under | `topic_model.py`, and `topics.py`, the baseline it imports |
| committee, member or town pages | `build_committees.py`, `build_legislator_pages.py`, `build_town_pages.py` |
| the civics explainers under `/learn` | `build_civics.py` |
| the CSV downloads and `/data` | `build_exports.py` |
| the RSS feeds | `build_feeds.py` |
| where a hearing sits in a recording | `segment_markers.py`, scored by `probe_alignment.py` |
| which rows exist at all | `build_data.py` → `data/`, then `build_site_v2.py` → `site/*.json` |
| look and type | `app.css`; `style.css` in `site/` is generated from it. `DESIGN.md` says why it is as it is |
| the pipeline, or its order | `build_all.py` — one `Step(...)` per entry in the plan |
| what counts as correct | `preflight.py` — each check's docstring names the incident behind it |

---

## The data

The site's own JSON is served from the same origin as the pages, at stable
addresses:

| | |
|---|---|
| `/index.json` | every bill, every term — title, sponsor, committee, topic, status, passage |
| `/idx/<term>.json` | one term's bills; this is what the search page loads |
| `/legislators.json` | the roster, with districts, towns and committees |
| `/rollcalls_index.json` | every recorded vote — tally, whether it passed, party split, and a plain-English question where one could be made (5,007 of 9,565) |
| `/committees.json`, `/towns.json`, `/districts.json` | membership and geography |
| `/feed/*.xml` | RSS: everything, upcoming hearings, and one feed each per committee, topic, legislator, and per bill still moving |

Every table is also downloadable as CSV from
**[graniterecord.org/data](https://graniterecord.org/data)** — bills, votes,
sponsors, roll calls, legislators and proceedings, about 2.4 million rows
across 19 files. `/data/manifest.json` lists each one with its rows, size and
column names, so a program can discover what is there in one request.

That manifest also carries a per-term coverage table, and it is the honest
answer to "how far back does this go". Titles, topics, committees and passage
run the full 19 terms. Named sponsors are substantial only from 2011-2012 on;
before that each term names fewer than twenty. **An empty column is a record
not yet collected, not a bill without one.**

If you are building something and the shape is awkward, say so — the point of
this is to be used.

### Fetching, and the one hard rule

**Do not point a `fetch_*` script at the General Court without asking the
project owner.** This address has been blocked by their firewall twice: once
for probing filenames that did not exist, once for running two fetches at the
same time. Getting blocked again costs days and an email to a Clerk's office.

Fetches run one at a time, slowly, and a refusal ends the run rather than being
retried around. A refusal also **outlives the run that met it**: `refusal.py`
records it in `archive/refused.json`, and every fetch in the project then stops
for 24 hours — including a full `build_all.py`, which skips its General Court
steps and says so. `netcheck.py` diagnoses a refusal without making it worse.
Clearing one (`python3 refusal.py --clear`) is the owner's decision, not a step
in a recipe.

The `fetch_*_db.py` scripts read the SQL host the General Court publishes
credentials for, not the web server that did the blocking. Still ask — it is
still somebody else's server — but a refusal there is a different problem.

---

## Contributing

**Run `python3 preflight.py` before and after.** That is the test suite: 159
checks, which build the whole site on a fixture, load the front end in node and
call `render()` and `renderDetail()`, and run `tests/test_markers.py`. Add a
check whenever something breaks in a way a check could have caught — that is
how most of the current ones got there.

**Bump the version stamp in the same edit.** When you change a file, increment
the `.N` in its `# GRANITE_VERSION:` line and update `versions.json` to match.
**Leave the date alone** — it is when the file was created, not last modified.
`preflight` fails if the two disagree, and this is the most common way a first
change fails.

**Five files are a person's, and no generator writes them.**
`ground_truth.csv` (35 proceedings timed with a stopwatch),
`review/checked.jsonl` (review judgments, append-only), `bill_notes.json` (what
a recurring bill number means — HB1 has been the budget since 1993),
`officials.json` (offices filled by hand from four official sources) and
`member_corrections.json` (a name a generator got wrong, and the evidence).
`preflight` fails if any `build_*` or `fetch_*` script opens one for writing.

**Nothing about timestamps ships without scoring it first:**

```
python3 probe_alignment.py --truth --candidate candidate_segments.json
```

The number to watch is the candidate median. Do not let it regress.

**A writer of a derived file, run on a subset, destroys the rest.** This has
happened twice. Writers merge; a full rebuild is an explicit flag.

**Say when something is a guess.** An invented number stated plainly costs more
than an admission of not knowing.

---

## Unfinished

Honest list, not a roadmap — `LAUNCH.md` is the roadmap.

- **This repository has no remote yet.** The `git clone` line above cannot be
  filled in until the address is chosen.
- **No `CONTRIBUTING.md`, no issue templates, no CI.** The rules above are all
  there is, and `preflight` is run by hand.
- **The JSON sets no CORS header.** Nothing in the tree writes
  `Access-Control-Allow-Origin`, so a cross-origin `fetch` from another site
  will fail. Fixing it is two lines where `build_pages.py` writes
  `site/_headers`.
- **Sponsors before 2011 are nearly empty** — fewer than twenty per term across
  eleven terms. The archive path that would fill them exists and is not yet
  run to completion.
- **`proceedings.csv` covers eleven of the nineteen terms.** The rest depend on
  dockets and calendars not yet parsed.
- **Email following is designed and not built** (`FOLLOW.md`). RSS is live.

---

## Licence

**MIT** — see [`LICENSE`](LICENSE). Use it, change it, sell it; keep the notice.

That covers the software and the texts this project writes: the plain-English
bill histories, the explainers under `/learn`, and the editorial notes on
particular bills. It does not cover the underlying record, because it cannot —
the bills, votes, calendars and recordings are the State of New Hampshire's,
published by them, and facts are not copyrightable. Nothing here claims
otherwise.

---

## Where to read next

- **`LAUNCH.md`** — what is done, what is not, and what to do first. The newest
  of these, and the one that wins where they disagree. It is a working journal;
  the current agreed order is in §0e rather than at the top.
- **`ARCHITECTURE.md`** — what is sound, what is not, and what it would take to
  fix. Written by measuring rather than remembering.
- **`HANDOFF.md`** — how the work runs, and the habits that produced the good
  results.
- **`DESIGN.md`** — why the site looks and reads the way it does.
- **`CLAUDE.md`** — the working rules: what may not be run without asking, and
  why each rule exists.
- **`STATE.md`** — generated by `handoff.py`. Never edit it; run it again.

Also here, and not current: `ROADMAP.md` and `ARCHIVE_PLAN.md` are superseded
by `LAUNCH.md` and kept for their reasoning; `PROPOSAL-civics.md` and
`FOLLOW.md` are designs, one built and one not.
