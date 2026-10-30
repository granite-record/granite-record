# The public data API: design

Phase 1 of the API project the owner approved on 26 October 2026
("defaults"). This is a design only: nothing here changes the site. Phase 2
builds it on `feat/api`, after the owner's OK on this document, relayed by
the manager.

Written 30 October 2026 on branch `design/api`. **Every size and count below
was measured** on a full local build of that day (`build_all.py --local
--no-captions`, `GRANITE_BUILD_DATE=2026-10-30`, on the kit as `cloud.py
kit-down` brought it). Where a figure is an estimate it says so. *Measured*,
at the end, says how to repeat them.

---

## In one paragraph

Add five kinds of file to `/data/`, beside the spreadsheets that are there
now: one SQLite database of every table (16.7 MB compressed); every bill's
full record, one compressed file a term (17.0 MB for 2025-2026, 143.5 MB for
all nineteen); a people file joining every number the General Court uses for
a person (0.5 MB), whose person numbers are issued once and written down so
they never move; a description of every file and field (`schema.json`); and
clean dates and a `person` column in the existing spreadsheets, where they
fit under the host's file-size limit.
`/data/manifest.json` stays the index and lists them all. The nightly change
log under `/changes/` gains a list of what changed. It is all files: nothing
runs to serve it. The nightly build gets about two minutes longer and 24
files bigger, against 57,626 files today and the 90,000 at which
`check_site` warns.

Two of the plan's figures were off, and are corrected here: the 2025-2026
bill file is **17.0 MB**, not about 14 MB; and the database is **16.7 MB**
only if it is normalised (a vote stored as a roll call, a person and a value).
A straight copy of the spreadsheets into SQLite is 46.9 MB compressed, past
the 25 MiB per-file limit the host enforces.

---

## 1. What the nightly produces today

Read from the build, not from documents.

| What | Where | Built by | Measured |
|---|---|---|---|
| Spreadsheets | `/data/*.csv`: bills, legislators, rollcalls, proceedings, sponsors, and `votes-<term>.csv` for 14 terms from 1999-2000 | `src/pages/build_exports.py` (step 49, "bulk downloads") | 19 files, 2,581,692 rows, 238.5 MB (24.5 MB if each were gzipped) |
| The index of them | `/data/manifest.json`: each table's file, rows, bytes, columns and description; each term's `/idx/` file; a coverage table | the same | 17 KB |
| The page that describes them | `/data.html` | the same | |
| Each bill's record | inside its page, `/bill/<year>/<bill>.html`, as `<script id="gr-data">`; over 100 KB it is a file, `/bills/<year>/<BILL>.json` | `build_site_v2.py`, then `build_bill_pages.py` | 33,717 bills; 716 kept as files |
| Bill text versions (sitting term) | `/versions/<year>/<BILL>.<n>.txt` and their diffs | `build_bill_versions` steps | 13,202 files, 118 MB |
| Bill index | `/idx/<term>.json` (19 terms, plus `2027-requests`) | `build_site_v2.py` | |
| What changed | `/changes/current.json` and `/changes/<date>.json`, the last eight nights | `build_feeds.py` through `follow_changes.py`, to the contract in `workers/follow/CHANGES_FORMAT.md` | 9 files, 0.3 MB |
| Cross-origin reads | `_headers` allows any origin on `/idx/*`, `/legislators.json`, `/rollcalls_index.json`, `/data/manifest.json`, `/data/*.csv` | `build_pages.py` | |

The whole site: **57,626 files, 2,905 MB** (`check_site.py`). The build took
1,549 s on this machine: 47 steps ran, one was skipped for want of the
caption files, and one superseded step did not run, as by default.

Three things found while reading, which shape the design:

- **Dates are not uniform.** `rollcalls.csv` and `proceedings.csv` write
  `2026-01-07`. The 14 vote files write the General Court's own `1/7/2026`,
  in four shapes (`9/99/9999` and the rest) across 2,303,047 rows.
- **`member_id` is two number spaces in one column.** It is the General
  Court's PersonID where one exists and its Employeeno otherwise
  (`build_data.py`, `mid = r[4] or r[3]`). The PersonIDs in the vote files
  run from 27 to 11,524; Employeenos are six digits. Both are re-issued when a
  member moves from the House to the Senate (and a member who returns to a
  chamber gets their old number back, `member_links.py`), so 19 people carry
  two Employeenos. Cindy Rosenwald's House votes sit under PersonID 515 and
  her Senate votes under 9406; only 9406 has a page.
- **A bill's record is the page's record.** It is what `app.js` draws, so it
  carries presentation (labels, slugs, the rail's stops) beside the record,
  and the release session changes its shape when the page changes. That
  matters for the stability promise (section 4).

---

## 2. The files

Everything under `/data/`. New names are in **bold**.

| File | What | Format | Measured size |
|---|---|---|---|
| `manifest.json` | the index: every file, its address, rows, bytes, sha256, the night it was built | JSON | ~30 KB (estimate) |
| **`schema.json`** | what every column and field means, its type, what it joins to | JSON, Frictionless Data Package | ~100 KB (estimate) |
| **`granite-record.sqlite.gz`** | every table in one SQLite database | SQLite 3, gzip | 16.7 MB (69 MB opened) |
| **`bills-<term>.jsonl.gz`** | every bill's full record, one line a bill, 19 files | JSON Lines, gzip | 3.8 MB (1989-1990) to 17.0 MB (2025-2026); 143.5 MB in all |
| **`people.json`**, **`people.csv`** | one entry a person, every number they carry | JSON; CSV, one row a number | 539 KB and 443 KB |
| `bills.csv` … `votes-<term>.csv` | as today, with the changes in 2.6 | CSV | 238.5 MB today; the vote files about 1.1 MB more with ISO dates (measured on the two largest) |

And, not under `/data/` and not built here: `/api/live/votes/<date>`, today's
roll calls, which the live-layer session builds (2.7).

### 2.1 `manifest.json`: the index, extended

It stays where it is and keeps every key it has, because programs read it
today. It gains:

```json
{
  "format": 1,
  "api": {"status": "beta", "stable_from": "2027-02-01",
          "docs": "https://graniterecord.org/api", "schema": "https://graniterecord.org/data/schema.json"},
  "files": [
    {"path": "/data/bills-2025-2026.jsonl.gz", "kind": "bills", "term": "2025-2026",
     "rows": 2243, "bytes": 17048895, "sha256": "…", "built": "2026-10-30",
     "encoding": "gzip", "media_type": "application/x-ndjson"}
  ],
  "live": {"votes": "https://graniterecord.org/api/live/votes/{date}"}
}
```

`files` lists every file, the CSVs included, so one request finds all of
them. `tables` and `bill_indexes` stay as they are, beside it. There is no
"last changed" date: it would need last night's checksums carried between
nights, which the nightly's empty machine does not have. A mirror compares
`sha256` with the copy it holds, which needs no state on this side.

### 2.2 `schema.json`: the description of every file

A **Frictionless Data Package** (datapackage v1): one `resources` entry a
file, each CSV with a Table Schema (`fields`: name, type, description,
`primaryKey`, `foreignKeys`), each JSON file with `fields` describing one
record, nested fields by dotted name (`rollcalls[].yeas`). Why a standard and
not our own: pandas, R's `frictionless`, Python's `frictionless`, and
`csvkit` read it, and it is a published specification a reader can look up.
The descriptions are the ones `build_exports.py` already writes into
`manifest.json` and the data page (`what`, `JOINS`, the folded notes), from
the same strings, so the three cannot disagree.

Each field also carries `"x-stability": "stable" | "beta" | "page"`. `page`
marks a field the bill's page draws and the API promises nothing about
(section 4).

### 2.3 `granite-record.sqlite.gz`: one database

Normalised, because a straight copy is too big (46.9 MB compressed):

```
bills(term, bill, year, title, sponsor, committee, topic, status, outcome,
      passage, roll_calls, chapter, chip)            PRIMARY KEY (term, bill)
rollcalls(id INTEGER PRIMARY KEY, roll_call UNIQUE, term, year, body, number,
          date, bill, question, question_plain, yeas, nays, not_voting,
          passed, procedural, threshold_needed, threshold_rule, outcome_source)
votes(rollcall → rollcalls.id, person → people.person, member_id, party,
      vote → vote_values.code)                         PRIMARY KEY (rollcall, member_id)
vote_values(code, vote)          -- Yea, Nay, Not Voting/Excused, … (7 values)
people(person, …), person_numbers(person, kind, number)
sponsors, proceedings, legislators                     -- as the CSVs
meta(key, value)                 -- format, built, licence, source
```

Measured on the prototype, which had the tables above except `people` and
`person_numbers` (and called its member table `members`): 69.1 MB opened,
**16.6 MB gzipped**, 15 s to write. The people tables are 69 KB gzipped as a
JSON file, so the whole is **about 16.7 MB, an estimate**. The votes table
is 37.5 MB of it. Every date ISO. Indexes on `votes(person)`,
`sponsors(term, bill)` and `proceedings(term, bill)` are left to the reader
by default (open question Q6), because each adds megabytes to every
download.

**Headroom.** 16.7 MB of the 23.6 MB the build allows itself (nine tenths of
25 MiB, `build_exports.SAFE`). Recent terms add 196,816 to 238,317 votes; at the
prototype's average (37.5 MB for 2,303,047 votes, compressed with the rest at
about a quarter) that is roughly 1 MB compressed a term, an estimate, so it
reaches the line in about seven terms. Past the line the build fails, as it
does for the CSVs today (`build_exports.py` writes each file, measures it,
and stops the build with the list of files over the line after writing the
manifest); the remedy, when it comes, is votes by decade in a second file.

### 2.4 `bills-<term>.jsonl.gz`: every bill's full record

One line a bill, the bill's own record as its page carries it, with one key
added first:

```json
{"key": "2025-2026/HB1442", "id": "HB1442", "year": 2026, "term": "2025-2026",
 "title": "…", "sponsors": […], "events": […], "rollcalls": […],
 "billtext": {"version": "FINAL VERSION", "title": "AN ACT …", "analysis": "…", "body": "…"}, …}
```

- **The key** is `term/BILL` (`2025-2026/HB1442`), as the plan asks.
- **The text of the current printing** is already in the record, as
  `billtext` (its `version`, `title`, `analysis`, `fiscal` and `body`): 32,625
  of 33,717 bills carry one. Earlier printings come later, from
  `/versions/`, which holds them for the sitting term only.
- **One file a term, from the 19 `/idx/` terms.** `2027-requests`, the bill
  requests for the next session, is not bills and gets no file (Q8).
- **JSON Lines, not one JSON object**, so a reader can stream it a bill at a
  time without holding 80 MB in memory.

What a record holds, counted over all 33,717 (non-empty, and share of the
bytes): `rollcalls` 29,431 bills, 24.9%; `billtext` 32,625, 24.2%; `events`
7.9%; `sponsors` 7.8%; `stations` 6.7%; `stages` 5.7%; `reports` 5.1%;
`narrative` 3.8%; `documents` 3.1%; `journey` 3.1%; then 33 smaller fields.

**Sizes**, compressed (opened in brackets):

| Term | Bills | MB | | Term | Bills | MB |
|---|---|---|---|---|---|---|
| 2025-2026 | 2,243 | 17.0 (80.0) | | 2005-2006 | 1,837 | 7.4 (40.1) |
| 2023-2024 | 1,996 | 11.0 (59.2) | | 2003-2004 | 1,605 | 5.9 (32.2) |
| 2021-2022 | 1,753 | 9.4 (49.7) | | 2001-2002 | 1,487 | 5.8 (32.0) |
| 2019-2020 | 1,983 | 10.2 (54.8) | | 1999-2000 | 1,673 | 6.3 (35.0) |
| 2017-2018 | 1,810 | 8.7 (48.4) | | 1997-1998 | 1,849 | 5.0 (28.1) |
| 2015-2016 | 1,789 | 8.6 (46.9) | | 1995-1996 | 1,586 | 4.4 (24.1) |
| 2013-2014 | 1,553 | 7.7 (43.7) | | 1993-1994 | 1,784 | 4.2 (25.0) |
| 2011-2012 | 1,772 | 8.5 (48.8) | | 1991-1992 | 1,675 | 4.1 (23.2) |
| 2009-2010 | 1,735 | 7.8 (43.9) | | 1989-1990 | 1,632 | 3.8 (21.3) |
| 2007-2008 | 1,955 | 7.7 (44.1) | | **All** | **33,717** | **143.5** |

The sitting term is the largest by far, and is 17.0 MB of the 23.6 MB line
with two months of its session left; 2027-2028 will start small and grow.
Each roll call in a record repeats its members' votes, which `votes` already
carries (24.9% of the bytes). If a term ever nears the line, the first remedy
is to drop each roll call's member list from the bundle and point to
`votes` (Q7); the second is two files a term.

### 2.5 `people.json` and `people.csv`: the join

```json
{"format": 1, "people": [
  {"person": "p376622", "name": "Cindy Rosenwald",
   "employee_numbers": ["376622", "209106"], "person_ids": ["515", "9406"],
   "member_ids": ["515", "9406"], "page": "/legislator/cindy-rosenwald-sd-13",
   "sitting": true, "chambers": ["H", "S"],
   "first_term": "2005-2006", "last_term": "2025-2026"}
]}
```

- **`person`** is this site's own number, the "person number" the plan adds.
  It does not change when a member moves chambers, which is the case every
  General Court number fails. It is issued once, written down, and never
  worked out again (below).
- **`member_ids`** are every id the other files use for the person:
  `member_id` in every vote and sponsor row, and `id` in `legislators.json`
  and `former.json`. Measured: every one of the 2,303,047 ballots' member ids
  falls to exactly one person, none to two and none to nobody. (The first
  prototype took only the ids with a page, and so missed Rosenwald's 515 and
  19 others; the counts here are the corrected join.)
- **`name`** is the plain name, without "Rep." or "Sen.": a person's title
  changes, and the prototype's, taken from the roster's display label, called
  Shannon Chandley "Rep." though she last sat in the Senate.
- **Built from** `generated/careers.json` (which joins Employeenos into
  people), `db/Legislators.psv` (Employeeno to PersonID), `legislators.json`
  and `former.json` (ids and pages), and the register of issued numbers.

Measured on the prototype: 2,192 people; 2,186 with a name and a page; 19
with two Employeenos; every id in `legislators.json` and `former.json`
falls to exactly one person; six people have no page (their votes carry a
number no roster names). 539 KB, 69 KB gzipped.

**A person number must be issued, not computed.** Computed afresh each night
from the joins ("`p` and the first Employeeno"), a number moves whenever a
join is corrected, and the joins are corrected: `member_links.py` records
that `careers.json` attached Sen. Pat Long's House record (Employeeno
376696, PersonID 540) to a freshman, Rep. Patrick Long, and the prototype
repeats it, giving `p376696` to the freshman. Fix that join after
publication and `p376696` would pass from one man to the other.

So the design is a **register**, `generated/person_numbers.json`, which git
keeps, as it keeps `careers.json`:

- Each entry is a person number and the General Court numbers it was issued
  for. Entries are only ever added. A number once issued is never reissued
  to someone else.
- **The nightly never writes it.** It reads it, and a General Court number
  the register does not hold (a new member, mid-term) gets a number the
  night marks `"provisional": true` in `people.json`, `p` and that number. A
  person adds it to the register with
  `python3 src/pages/build_people.py --issue`, which prints every new entry
  and every disagreement between the joins before it writes; the night's
  verdict says how many provisional numbers there are, so they are not
  forgotten.
- **Two entries that prove to be one person (a merge)**: the later number
  stays in `people.json` with `"replaced_by"` and nothing else.
- **One entry that proves to be two people (a split)**: the number stays with
  the person whose General Court number it was first issued for, the other
  gets a new number, and their entry carries `"split_from"`. The documentation
  says a split can happen, and why.
- **Before the first publication** the known disagreement (Pat Long) is
  settled by hand and the register is issued from the corrected join, so no
  number has to move on day one.

Which join decides (Q3). `careers.json` joins any two numbers by exact name
and no overlap in service; `member_links.py` joins an earlier number only
onto a *sitting* member, by six stricter rules, and so cannot decide for
everyone (it would not join Chandley's two numbers, 568 and 9404, neither
sitting). The default: `careers.json`'s join, overridden wherever
`member_links.py` decides otherwise, and every override printed by
`--issue`.

`people.csv` columns: `person, number_kind, number, name, page`, one row a
number (employee_number, person_id, member_id), so a spreadsheet can look up
any number in one column.

### 2.6 The spreadsheets: clean dates and a person

The vote files are the constraint. Two of them are near the line already,
and every byte a row gains is multiplied by up to 238,317 rows. Measured on
the built files (`measure/results/measure_votes.json`; the line is 23.59 MB):

| File | Today | ISO dates in place, plus `person` | `date_iso` added, plus `person` |
|---|---|---|---|
| `votes-2011-2012.csv` | 20.67 MB | 22.70 MB | **24.84 MB, fails the build** |
| `votes-2025-2026.csv` (term still sitting) | 19.83 MB | 22.06 MB | **24.36 MB, fails the build** |
| the other twelve | 9.19 to 16.62 MB | up to 18.48 MB | up to 20.36 MB |

So:

- **Every date `YYYY-MM-DD`, rewritten in place** (Q4). Only the vote files
  differ today. The column keeps its name and meaning, and a spreadsheet reads
  both shapes as a date. A second date column does not fit.
- **`person` as a new last column in `sponsors.csv` and `legislators.csv`
  only**, last as `chip` was added last, so a reader who counts columns finds
  each where it was. **Not in the vote files**: there it would leave
  2011-2012 with a megabyte to spare and the sitting term with 1.5. A vote's
  person is one join away, through `people.csv` (`member_id` to `person`)
  and inside the database, where `votes` carries it.
- `manifest.json`'s `tables` entries gain nothing new; `files` (2.1) carries
  the checksum.

With ISO dates alone, measured: `votes-2011-2012.csv` 20.94 MB and
`votes-2025-2026.csv` 20.15 MB, both under the line with 2.6 MB or more to
spare.

### 2.7 Today's votes: `/api/live/votes/<date>`

Built by the live-layer session; this project's part is to name it in
`manifest.json` (`live.votes`, a URL template), describe its fields in
`schema.json` as that session states them, and say on the documentation page
that the next morning's files take the day in. The shape is that session's;
what this side asks of it (through the manager) is that its votes carry the
same `roll_call` key (`year-body-number`) and the same `member_id`, so that a
live vote joins `rollcalls` and `people` the next morning without a mapping.
Live-stream data is not part of the API.

### 2.8 The change log: `/changes/<date>.json`, extended

The night files already say, for every bill, member, committee and topic a
reader can follow, what was new that night: the feeds' own items, for the
email sender. Other sites need something plainer: *which records changed,
and which files*. One new top-level key in each night's file:

```json
{
  "format": 1, "date": "2026-10-30", "built": "…", "sitting_term": "2025-2026",
  "new_by": "first-seen", "refs": { … as today … },
  "data": {
    "bills":  ["2025-2026/HB1442", "2025-2026/SB12"],
    "people": ["p376622"]
  }
}
```

- `bills` is every bill whose record changed since the night before, in any
  term, so a correction to a 1997 bill is listed too, not only the bills a
  feed has an item for. `people` is the same for people.
- **What counts as a change is a hash of the `stable` fields only**
  (section 4). The records carry the page's presentation, and a change to how
  a page is drawn would otherwise list all 33,717 bills on one night, which
  says nothing.
- **No list of files.** A file's checksum is in `manifest.json`, and a mirror
  compares it with its own copy (2.1). Listing changed files here would need
  the files' checksums before `build_exports.py` has written them.

**Where the state lives.** The hashes have to be carried from one night to
the next, on a machine that starts empty. They go in the ledger the change
log already has, `archive/first-seen.json`, under a new key, and so ride all
of its machinery: it is on `cloud_kit.json`'s state list; tonight's goes to
`archive/first-seen.next.json` and `nightly.py` keeps it only for a build it
accepts; a dry night does not keep it. A second build on the same date
compares against the last *accepted* night's hashes, as the first-seen items
do, so the rerun's file lists everything the first listed and anything since
(CLAUDE.md: a writer run on a subset destroys the rest). No ledger (the
first night, or a lost state) lists nothing and says so in a WARNING, as the
first-seen half does, never every bill.

**One writer.** `follow_changes.py` writes the night files, and it is the one
that would write `data`, from hashes `build_feeds.py` can take from the bill
records it already reads. The alternative, `build_exports.py` opening the
night's file afterwards, makes a second writer of somebody else's file. Both
are the follow work's owners' call, through the manager (section 7).

- `changes.js` refuses a file whose head breaks the format, and reads only
  the keys it names (`checkHead` and `refs`, `workers/follow/changes.js`), so
  the sender reads these files as before. `CHANGES_FORMAT.md` should say that
  a reader ignores a key it does not know, so the next reader can rely on it;
  `tests/follow/check_changes.js` runs over the result in preflight.
- The key `bill:2026/HB1442` in `refs` stays as the sender's contract has it;
  the API key is `2025-2026/HB1442`. Two spellings of one bill is a cost,
  and changing the sender's is not this project's call (Q9).

`/changes/` is `build_feeds.py`'s and the follow contract's, not this
project's: this goes to the manager as a request (section 7).

---

## 3. Versioning

**A `format` field in every JSON file, and no `/v1/` in the path.**

- The site's files already work this way: the changes files carry
  `"format": 1`, and `changes.js` refuses any other.
- A `/v1/` path promises a `/v2/` beside it, which doubles 143 MB of bill
  files and 24 files the night a version changes. A version field costs
  nothing until it is needed.
- The CSVs, which cannot carry a field, are covered by the rule that columns
  are only added at the end, and by `schema.json`, which carries the format.
- When a change cannot be made by adding (after 1 February 2027), it becomes
  a new file name beside the old one (`bills-v2-<term>.jsonl.gz`), and both
  are published for a year (Q5).

---

## 4. Stability: what the promise covers

The plan: a beta until 1 February 2027, then changes only add things.

The bill records are the page's records, and the page changes. If the
promise covered every field, every change to a bill page after February
would need a new file. So the promise covers what `schema.json` marks
`stable`, and nothing else:

- **`stable`**: the key, `id`, `term`, `year`, `title`, `status`, `chip`,
  `sponsors` (names, ids, prime), `events` (date, body, text), `rollcalls`
  (date, body, question, tally, passed), `billtext`, `chapter`, `rsa`,
  `amendments` (number, date, outcome), `reports`, every CSV column, every
  `people` field. A proposed list; Phase 2 writes it field by field.
- **`page`**: what only the page uses: `stations`, `stages`, `journey`,
  `story_people`, `facts`, labels and slugs. Present, documented, promised
  nothing.

The build holds the promise rather than a person: a check in preflight
compares tonight's `schema.json` with the last published one and fails on a
`stable` field removed or retyped after 1 February 2027.

---

## 5. What changes for the nightly

| | Today | With the API | Source |
|---|---|---|---|
| Files on the site | 57,626 | 57,650 (+24: 19 bill files, the database, two people files, `schema.json`, and `api.html`) | counted |
| `check_site` warning line | 90,000 | unchanged; 32,350 to spare | |
| Bytes deployed | 2,905 MB | +about 161 MB: 143.5 bill files (measured), 16.7 database (estimate, 2.3), 0.5 and 0.4 people (measured), and `schema.json` and the page, well under 1 MB together (estimate) | |
| Build time | 1,549 s here | +about 90 s: 71 s for the bill files, 15 s for the database (written and gzipped), under a second for people and the schema | measured on this machine; the nightly's machine will differ |

Where it runs: in `build_exports.py`, the last step, which already reads
the site's files, so no step's order changes. The bill files read each
record back out of its page as `build_bill_pages.py` left it; writing them in
`build_bill_pages.py`, which already holds every record, would save the 71 s
but is the release session's file (Q10).

A `.gz` file must be served as it is, with no `Content-Encoding`, so that a
program gets the bytes the manifest's sha256 describes. That is expected of
Cloudflare Pages and not yet verified: Phase 2 checks it on the live host
before the announcement, and `_headers` (the release session's `build_pages.py`)
gets two lines: `Access-Control-Allow-Origin: *` on `/data/*`, and
`Content-Type` for `.jsonl.gz` and `.sqlite.gz`.

---

## 6. The documentation page

A page of its own, **`/api`**, built by `build_exports.py` beside
`data.html` and linked from its "For Developers" section; nothing in the
header until the announcement in December. Its own page because the data
page is for a person with a spreadsheet and is already long, and the API is
for a person writing a program (Q1).

It is drawn with the data page's components and nothing new but one rule:
`dphead` and its lead, `dponp` ("On this page"), `dpsec` sections with the
heading in the margin from 60em, the `dpdl` downloads table (a list on a
phone), `dpmore` and `dpfold` folds, and the `dptermgrid` term grid the vote
files use. **The one new pattern is `.apicode`**, a block of example code:
the data page has inline `code` and no block of it, and a command a reader
copies has to keep its lines. It is built from the tokens `.repo code`
already uses (`--mono`, `--wash`, `--rule`), and scrolls inside itself on a
phone rather than widening the page.

The mock is `mock_body.html`, put into a built `data.html` by
`mock_page.py`. Screenshots, with the data page beside them for comparison:

| | Light | Dark |
|---|---|---|
| 1280 | `screens/api-1280-light.png` | `screens/api-1280-dark.png` |
| 390 | `screens/api-390-light.png` | `screens/api-390-dark.png` |
| The data page, as it is | `screens/data-1280-light.png`, `screens/data-390-light.png` | `screens/data-1280-dark.png`, `screens/data-390-dark.png` |

No page sideways-scrolls at either width (measured: 0 px in all eight). The
mock's figures are the measured ones except three it marks as estimates (the
manifest's and `schema.json`'s sizes, and the database's 16.7 MB); the page
will count its own each build, as the data page does. Its wording follows the
defaults of Q5, Q11 and Q12 and changes with the answers; its line on
cross-origin reads depends on the `_headers` request (section 7).

---

## 7. Who owns what (requests through the manager)

| Change | Owner | Request |
|---|---|---|
| New files, `manifest.json`, `schema.json`, `/api` page, CSV columns | this project (`build_exports.py`) | |
| `"data"` key in `/changes/<date>.json`, the record hashes in the first-seen ledger, a line in `CHANGES_FORMAT.md` that unknown keys are ignored | `build_feeds.py`, `follow_changes.py`, the follow contract | yes: their owners write it (default, one writer), or agree that `build_exports.py` adds it afterwards |
| `generated/person_numbers.json`, the register, and `build_people.py --issue` | this project, but the register is a record that cannot be rebuilt: issuing is a person's run | the owner's OK on where it lives (Q14) |
| `_headers` lines for `/data/*` | release session (`build_pages.py`) | yes |
| A link from `data.html`'s "For Developers" | this project (`build_exports.py`) | |
| `/api/live/votes/<date>`: same `roll_call` and `member_id` keys | live-layer session | yes |
| `versions.json`, `preflight.py` (new checks) | shared | both sides, as usual |

---

## 8. Phase 2, in small proven branches

Each on `feat/api-*`, merged by the manager, each proven by a full build's
sha256 manifest against a baseline built twice under different
`PYTHONHASHSEED`s, with `GRANITE_BUILD_DATE` fixed (CLAUDE.md, "Verifying a
refactor"), so that existing files change only where intended.

1. **`people`**: the register, issued once by hand after the Pat Long join is
   settled, then `people.json`, `people.csv`; nothing else changes. Proof: only
   new files in the manifest diff.
2. **CSV columns**: ISO dates in the 14 vote files, `person` in
   `sponsors.csv` and `legislators.csv`. Proof: only those 16 CSVs and
   `manifest.json` and `data.html` differ, and a check that every other column
   is byte-identical.
3. **Bill files**: the 19 `bills-<term>.jsonl.gz`. Proof: new files only; a
   check that every line parses, keys are unique, and the count per term
   equals `/idx/<term>.json`'s.
4. **Database**: `granite-record.sqlite.gz`. Proof: new file only; a check
   that every table's row count equals its CSV's.
5. **`schema.json` and the manifest's `files`**, with the preflight check that
   every column of every file is described and every description names a
   column that exists.
6. **The `/api` page**, with screenshots on real data at 390 and 1280, light and
   dark.
7. **The change log key**, after the owners of `/changes/` agree.

Each step that writes a file measures it and fails the build, naming the
file, if it is past nine tenths of 25 MiB, as `build_exports.py` does for the
CSVs. Each says how many rows
it wrote, and stops on none (CLAUDE.md, "Silence is not success").

Timetable against the plan: branches 1 to 4 by 13 November, 5 to 7 by
24 November (built, unlinked), announcement material in December.

---

## 9. Open questions, each with a default

| # | Question | Default if nobody says otherwise |
|---|---|---|
| Q1 | The documentation as its own page, `/api`, or a section of `/data`? | Its own page, linked from the data page. |
| Q2 | The database's file name and compression? | `granite-record.sqlite.gz`, gzip, which every language reads and which matches the bill files. Not zip. |
| Q3 | Which join decides that two numbers are one person? | `careers.json`'s, overridden wherever `member_links.py` decides otherwise (its rules cover only sitting members); `--issue` prints every override, and Pat Long's case is settled by hand before the register is first issued. |
| Q4 | The vote files' `date`: rewrite to `YYYY-MM-DD`, or add `date_iso`? | Rewrite in place, and say so on the data page and in the change list. A second column would fail the build for two files (2.6). |
| Q5 | After 1 February 2027, how long does an old file live beside its replacement? | One year. |
| Q6 | Indexes inside the database? | Primary keys only; the documentation gives the three `CREATE INDEX` lines a reader may want. |
| Q7 | Each roll call's member list inside the bill records (a quarter of their bytes), or only in `votes`? | Keep it while every term fits; drop it from the bill files first if one nears the line. |
| Q8 | A file for `2027-requests` (bill requests, not yet bills)? | Not in the API until they are bills; they are on `/idx/2027-requests.json` already. |
| Q9 | One spelling of a bill's key across the site (`2025-2026/HB1442` vs the follow contract's `2026/HB1442`)? | Leave the follow contract alone; the API's key is the term's. The `data` block uses the API's. |
| Q10 | Write the bill files in `build_exports.py` (71 s, own file) or in `build_bill_pages.py` (free, release session's)? | `build_exports.py`. |
| Q11 | Announce a beta change a week ahead (as the mock says) or on the night it happens? | A week ahead, in `manifest.json`'s `api.notices` and on the page. |
| Q12 | The licence statement in the files: "public domain" for what the site adds needs a named instrument. | CC0 1.0 for the site's ids, joins, corrections and timings; the State's record named as the State's; MIT for the code. `DATA.md` gains a paragraph, which is a licence text the owner should read before it is published. |
| Q13 | The bill page's narrative (`narrative`) is "authored" text, offered under MIT today (`DATA.md`). Under CC0 with the rest of the file, or stays MIT? | Stays as `DATA.md` says (MIT) until the owner decides; `schema.json` names each field's terms. |
| Q14 | Where does the register of person numbers live? It is a record that cannot be rebuilt once numbers are out. | `generated/person_numbers.json`, kept by git, written only by `build_people.py --issue`, which a person runs; preflight fails if a build or fetch script opens it for writing, as it does for `corrections/` and `review/`. The nightly reads it and marks a new member's number provisional until it is issued. |
| Q15 | A person number for a member who is not yet in the register (a special election): publish a provisional one, or none until it is issued? | Provisional, marked `"provisional": true`, counted in the night's verdict. |
| Q16 | `person` in the vote spreadsheets too, at the cost of the 2011-2012 file's headroom (2.6)? | No: through `people.csv` and the database. |
| Q17 | Does a bill count as changed (2.8) when only its page's presentation changed? | No: the hash covers the `stable` fields only. |

---

## 10. Things noticed on the way, for their owners

Not this project's to fix; passed to the manager.

- `journal_motions.resolve_member` returns `careers.json`'s key, an
  Employeeno, and treats it as the site's member id, which is a PersonID for
  anyone who has one (`journal_motions.py` near lines 1658-1679). Worth a
  look by its owner; not verified here beyond reading.
- Shannon Chandley has two former-member pages, one for each number (568 and 9404),
  because former members are joined only to a sitting member, never to each
  other. `people.json` joins them; the pages do not.
- `build_exports.py`'s docstring says the member votes are 437,702 rows; the
  build wrote 2,303,047. Its own text; this project will correct it in
  branch 2.

---

## Measured

On 30 October 2026, in a scratch worktree of `dev` at `7865829`:

```
python3 src/ops/cloud.py kit-down            # 35,774 files, 3.64 GB, each checked
GRANITE_BUILD_DATE=2026-10-30 python3 build_all.py --local --no-captions
                                             # 47 ran, 1 skipped, 0 failed, 1,549 s
python3 src/checks/check_site.py             # 57,626 files, 2,905.3 MB
python3 docs/design/api/measure/measure_api.py site OUT       # bill files, plain SQLite, CSVs, dates
python3 docs/design/api/measure/measure_db.py site OUT        # the normalised database
python3 docs/design/api/measure/measure_people.py . OUT       # people
python3 docs/design/api/measure/measure_votes.py . > OUT.json # vote files with the new columns; every ballot to a person
python3 docs/design/api/mock_page.py site                     # the mock
node docs/design/api/measure/shoot.js http://127.0.0.1:PORT docs/design/api/screens api.html data.html
                                             # the site served on the loopback address
```

The scripts write only into the folder named, never into the site or the
repository, and ask nothing of the network. Their raw output is in
`measure/results/`.

Two things to know when reading the raw output. `measure_api.json`'s
`date_shapes` counts only the first 200,001 rows of each file (the script
stops there), so its shapes sum to 2,245,289; the 2,303,047 ballots are the
manifest's count. And `measure_people.json` is the first prototype, whose
`member_ids` held only the ids with a page; `measure_votes.json` is the join
the design describes, every ballot to one person.

---

## Review

An adversarial review by a fresh reader, on 30 October 2026, before this
went to the manager. What it found and what changed:

- **The person number was computed afresh each night**, so correcting a join
  would move a published number to another person; the prototype already
  gave Pat Long's House number to a freshman. Now issued once into a
  register (2.5, Q14, Q15).
- **`person` and a second date column would push two vote files past the
  cap**, and that had not been measured. Now measured (2.6): ISO dates in
  place, and `person` stays out of the vote files (Q16).
- **The change log needed state the design never placed**, and would have
  listed every bill whenever the page's shape changed. Now in the first-seen
  ledger's machinery, hashed over `stable` fields, with one writer (2.8,
  Q17); the file list and the manifest's "changed" date are dropped.
- **Wrong figures**: the PersonID range (now 27 to 11,524, measured), the
  database's 16.7 MB (now marked an estimate beside the measured 16.6), the
  mock's database row count (now ten tables), the deployed bytes, and the
  build's cap check (it fails the build after writing, not before).
- **"Every existing join keeps working"** was false for 20 member ids; the
  join is now every ballot's id, measured to the last ballot.
- **The mock** gave a reason about YouTube with no source on hand, promised
  the live file's refresh rate (another session's to promise), read an 80 MB
  file into memory in its example, and said "at least a year" where Q5 says
  one. All corrected; its licence and notice wording is marked as following
  Q11's and Q12's defaults.
