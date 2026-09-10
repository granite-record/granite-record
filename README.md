# Granite Record

A public record of the New Hampshire General Court, live at
**[graniterecord.org](https://graniterecord.org)**.

Every bill the legislature has filed since 1989, who sponsored it, what
happened to it, and how each legislator voted — and for the recent terms, the
moment in the recording where the committee actually took it up.

```
33,683 bills across 19 terms, 1989 to 2026
   406 sitting legislators, and 2,192 people who have served
29,837 proceedings across six terms, on 1,823 recordings
 8,749 of those placed at a boundary the chair spoke aloud
```

The General Court publishes all of this already. It publishes it as fixed-width
dumps, PDF calendars, an ODBC database and a search page that wants a bill
number you already know. This turns that into something a person can read and
a program can use.

---

## What is unusual about it

**It is files on a CDN. There is no server and no database.** Every page is
static HTML, every record is JSON, and the whole site is rebuilt from source
data in about five minutes. That constraint is deliberate: a public record
should not stop working because a bill ran out or a runtime got deprecated.

**The core build needs nothing but Python.** No framework, no package manager,
no lockfile. Four optional libraries are imported lazily where they are
actually needed (see [Requirements](#requirements)); the site build touches
none of them.

**Nothing that cannot be checked gets published as though it could.** A
timestamp taken from a chair saying "we'll open the hearing on House Bill 1123"
is presented differently from one a model guessed, and where neither exists the
page says so and links the recording instead. There is a file of proceedings
somebody timed by hand with a stopwatch, and every timing method is scored
against it before anything ships.

---

## Getting started

Python 3.14 and Node (the test suite loads the front end in node). Then:

```
python3 inventory.py     # every script and the version it should be
python3 preflight.py     # 78 checks; builds the whole site on a fixture
python3 handoff.py       # writes STATE.md with the current counts
```

Under a minute, no network, no credentials. **Trust their output over anything
written in prose, including this file.** If `preflight` is not green, that is
the thing to fix first.

To build the site from data already on disk:

```
python3 build_all.py --local        # the whole pipeline, ~5 minutes
python3 build_all.py --dry-run      # what it would run, and why
```

`site/` is then a complete static site. Serve it with anything:

```
python3 -m http.server 8787 --directory site
```

---

## How the code is arranged

**`build_all.py` is the pipeline.** Twenty-one steps, each printing what it did and
why it matters. `--local` skips the steps that need the network.

**`proceedings.csv` is the one table.** One row per (bill, date, kind,
recording), whether it is a committee hearing or a floor debate, read through
`proceedings.py` by everything downstream. It exists because the two sources
behind it used to be read separately, and five tools in one day were found to
be silently excluding floor debates — each presenting as a different bug.

**There is one renderer.** `bills.html` plus `app.js` draws the search page, and
every bill, legislator, committee and town page is that same shell with one
global set. A bill page and a search result cannot disagree about a bill
because they are the same code reading the same JSON.

**Every script carries a version stamp** (`# GRANITE_VERSION: YYYY-MM-DD.N`)
and `versions.json` says what each should be. `preflight` fails when they
disagree, which has caught several half-applied edits.

**Checks are the design record.** Most of the 76 in `preflight.py` exist
because something broke in a way a check could have caught, and each one's
docstring says what that was. Reading them is a fast way to learn where the
sharp edges are.

---

## If you want the data rather than the code

The site's own JSON is served from the same origin as the pages and is
CORS-open:

| | |
|---|---|
| `/index.json` | every bill, every term — title, sponsor, status, passage |
| `/idx/<term>.json` | one term's bills, which is what the search page loads |
| `/legislators.json` | the roster, with districts, towns and committees |
| `/rollcalls_index.json` | every recorded vote: question, tally, outcome, party split |
| `/committees.json`, `/towns.json`, `/districts.json` | membership and geography |
| `/feed/*.xml` | RSS, including one feed per bill |

And every table is downloadable as CSV from
**[graniterecord.org/data](https://graniterecord.org/data)** — bills, votes,
sponsors, roll calls, legislators and proceedings, 524,850 rows in all.
`/data/manifest.json` lists each one with its rows, size and column names, so a
program can discover what is there in one request. It also publishes a per-term
coverage table: titles go back to 1989, sponsors only to 2023, topics only to
2025, and a column that is empty is a record not yet collected rather than a
bill without one.

If you are building something and the shape is awkward, that is worth raising —
the point of this is to be used.

---

## Rules that matter if you contribute

**Do not point a `fetch_*` script at the General Court without asking.** This
address has been blocked twice by their firewall: once for probing filenames
that did not exist, once for running two fetches at the same time. Fetches run
one at a time, slowly, and a refusal ends the run rather than being retried
around. `netcheck.py` diagnoses a refusal without making it worse.

**`ground_truth.csv` and `review/checked.jsonl` are the record.** They hold
proceedings a person timed by watching. No generator writes them, and
`preflight` fails if a `build_*` or `fetch_*` script opens either for writing.

**Nothing about timestamps ships without scoring it first:**

```
python3 probe_alignment.py --truth --candidate candidate_segments.json
```

**A writer of a derived file, run on a subset, destroys the rest.** This has
happened twice. Writers merge; a full rebuild is an explicit flag.

**Say when something is a guess.** An invented number stated plainly costs more
than an admission of not knowing.

---

## Requirements

The build and the checks need only the standard library. These four are
imported lazily, inside the functions that use them:

| library | needed for |
|---|---|
| `pdfplumber`, `pypdf` | pulling text out of calendar and report PDFs |
| `openpyxl` | reading a hand-marked `.xlsx` manifest |
| `faster-whisper` | transcribing recordings YouTube has no captions for |

```
pip install pdfplumber pypdf openpyxl        # everything except transcription
```

Publishing uses `wrangler` (Cloudflare Pages) and the YouTube Data API needs a
key in `secrets.json` — copy `secrets.example.json`. Neither is needed to build
or to read the data.

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

- **`ARCHITECTURE.md`** — what is sound, what is not, and what it would take
  to fix. Written by measuring rather than remembering.
- **`LAUNCH.md`** — what is done, what is in progress, what to do first.
- **`HANDOFF.md`** — how the work runs, and the habits that produced the good
  results.
- **`STATE.md`** — generated. Never edit it; run `handoff.py` again.
