# Granite Record — Architecture review

Written 5 September 2026, after four days of building and one long day of
finding out what breaks. This is an honest account of the structure, what it
has cost, and what the archive needs from it that it does not yet have.

Three sections: what is sound and should be kept; what is structurally wrong,
ranked by how much it has cost; and what to do, in order.

---

## What is sound

**The data comes from bulk files.** Docket, roll calls, sponsors, members: one
download each, covering a whole session. That is why an archive of fifteen
terms of votes and histories is fifteen downloads and not a hundred thousand
requests, and why the General Court's firewall has never been provoked by the
core of the site. The per-bill fetches -- text, testimony -- are the exception,
and they are the ones that got the address blocked.

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

**The site is static.** Files on a CDN, no runtime, nothing to go down at two in
the morning. That constraint is also what forces the file-count problem below,
but it is the right constraint.

**`preflight.py` builds the whole site on a fixture.** Several of its checks
exist because of specific failures this week; it has caught stamp mismatches
three times and a dead-zone error once. Run it for the current count -- a
number written here would be wrong within a day, and was.

---

## What is structurally wrong

Ranked by what it has actually cost, not by how it looks on paper.

### 1. Floor and committee data live in two different worlds

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

**Partly done, 6 September.** `rollcalls.json` is now `{term: {bill: [votes]}}`
and two `preflight` checks hold it there: one builds the fixture with the same
bill number in two terms and fails if their votes merge, the other fails the
build outright if it is handed the old flat shape rather than reading it and
finding nothing. The member-vote key gained its year at the same time, because
vote sequence numbers restart each session and "H-310" named two different roll
calls the moment 2025 arrived beside 2026.

`narratives.json` is done too, and it was the one that mattered most: status,
stages, events, the dating of every committee report, the floor index and the
amendment numbers all read through it. Its four readers were changed and run;
the build is byte-for-byte the same site, and it now refuses the flat shape
rather than producing 2,234 bills with no history in them.

`build_feeds.py` is done as well, and it was the largest single place a bill
number still stood in for a bill: 2,233 of the site's 8,045 files. A bill with
no filing year collapsed `feed/bill/<year>/<id>.xml` to `feed/bill/<id>.xml`,
which the next term's bill of the same number would land on top of. It now gets
no feed and is named in the output.

`committee_reports.json` and `senate_reports.json` are done too, and they are
the ones that show what the constraint really is. Neither could change shape
without being rebuilt in the same commit, and both could be: the Senate's come
from the database, and fetch_committee_reports gained --offline, which re-reads
the 82 calendars already on disk and makes no request. Output-neutral across
all 2,234 bills.

`data/bills.json` is done as well, and it was the one that mattered most: the
loop in `build_bills` runs over it, so a bare bill number there put two terms'
bills under one key at the very top of the pipeline. It also turned up the bug
the whole exercise exists to prevent -- `yearOf(id)` in `bills.html` searched
the entire index for the first row with that number, so opening the 2023 HB1
fetched the 2026 one's record and showed it under the 2023 heading.

**The 2023-2024 term is live**, which is the proof this all worked: 4,230 bills
across two terms, and no per-bill file of one term reachable from the other.

`bill_text.json` and `bill_status.json` are done, 7 September, and they closed
the gate. Both were held back because their writers need the network and
reshaping one without regenerating it leaves the site unbuildable. That turned
out to be the wrong way round: the writers could be taught the term first and
the files migrated in place, with the readers tolerating either shape, so no
fetch was needed at all. The whole site rebuilt byte-identical.

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

**Still flat: `testimony.json` and `sponsors.json`.** Both are read through the
`own` guard in `build_site_v2`, so an archived bill gets nothing from them,
which is correct but is also why an archived bill has no sponsors on the page.
Converting them is what the 2023-2024 fill needs next.

**Fix, for what is left: `(term, bill)` everywhere.** `setup_archive.py` and
`probe_archive.py` already sketch this. The year-keyed journal and calendar
citations were part of the same job without my recognising it.

### 4. The deployment has a file cap, and the archive hits it at five terms

**Measured on the two-term site, 6 September:** 12,013 files of 20,000.

| | files |
|---|---|
| the current term | 4,468 |
| the 2023-2024 term | 3,992 |
| everything shared -- legislators, towns, feeds, the shell | 3,553 |

An archived term costs **3,992 files**, so there is room for **three more** and
the cap breaks on the fifth term overall. That is further off than the earlier
estimate of three, because an archived term is cheaper than a live one: it has
no per-bill RSS feed, having no docket to report.

It is still the constraint on the archive as a whole -- nineteen terms back to
1989 is not reachable one file per bill by any arrangement -- so the decision
below stands. It is just not urgent until a third archived term is wanted.

The one-term estimate this section used to carry -- 8,045 files, 6,701 a term,
the cap breaking partway through the third -- was made before a second term
existed and is superseded by the measurement above. It was wrong in the
direction that matters: it counted a per-bill RSS feed for every term, and an
archived term has none.

What has not changed is that the cap is real for the archive as a whole.
Nineteen terms back to 1989, at two files a bill, is roughly 76,000 files. The
options are the same three:

1. **Fewer static pages for older terms.** Dropping `bill/<year>/<id>.html`
   for archived terms halves the cost to ~2,000 a term and buys about eight
   terms. It costs those bills their own indexable address, which is the
   entire reason those pages exist.
2. **One file per term rather than per bill**, read by the search page.
   Roughly ten files a term, so every term ever fits. Archived bills then have
   no address of their own at all, and the reader downloads a term to read one
   bill.
3. **Per-bill data in R2 behind a Worker.** No cap, at the cost of the
   constraint the whole site is built on: files on a CDN, no runtime.

A fourth looked promising and is not: **a page only for bills that were
actually taken up.** Measured on the current term, where the record is
complete, **2,220 of 2,234 bills have a hearing on the record -- 99.4%**, and
2,144 have a roll call. New Hampshire gives every bill a public hearing, so
"the ones anybody acted on" is very nearly all of them and this saves nothing.
Worth writing down because it is the option that sounds best before it is
measured: on the 2023-2024 term it looks like a 79% saving, but only because
that term's hearings have not been fetched yet and 416 roll calls are all the
site currently knows about. Selecting on what has been *fetched* rather than on
what *happened* would have been a rule that tightened every time the data got
better.

### 5. Two thousand-line functions where declaration order is load-bearing

`renderDetail` in `bills.html` is 472 lines and one function, with 26 `const`
declarations. Three times today a template literal read one of them before its
line ran, and the page died with the data already in hand. A lint that skips
template literals cannot see it; the runtime check only caught it once
extended to the focused view, which is the branch where two of the three lived.

`build_site_v2.py` is 1,672 lines and its `main()` builds every station,
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
`build_site_v2` did not have it for the manifest until today.

### 8. The parsers have no tests

Every fix today was verified by a fixture written in a heredoc and thrown away.
`OPEN_RE` has been through nine revisions and the phrasings it must match are
scattered across those heredocs and `TRANSCRIPT_MARKERS.md`. When someone
changes it in six months, the only way to know what broke is to re-run the
whole marker pass and score it.

**Fix: a `tests/` directory** with the real phrasings as cases: the twelve
openings from `--gaps`, the eleven from `--phrases`, the seven floor forms, the
four things that must not match. Twenty lines each. `preflight` runs them.

### 9. The cache keys on patterns, not on logic

`segment_markers` caches per recording, keyed on a hash of the regexes. Change
a regex and everything re-runs; change the dedupe rule, the window size or the
bill-matching threshold and nothing does. That is the second such trap in one
file. A hash of the whole module's source is crude and correct.

### 10. Per-bill fetching does not scale and has already caused harm

Bill text is 2,234 requests a term, at four seconds each. The address was
blocked twice this week -- once for probing, once for two fetches at once.
Fifteen terms of text is nearly five days of continuous requests for a document
that is one link away and better in its original form.

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

**The one thing the database does not carry is the PDF link.** `text_pdf` is
built from a `text_id` in the legacy bill-text URL, and
`LegislationText.LegislationTextID` is a different id space -- HB1442 is 1937
scraped and 23441 in the database. So a status source swap either keeps the
scrape for that one field, links the General Court's current bill status page
instead, or renders the database's own text. That is a decision, not a
detail.

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

## What the archive needs

In order. Each depends on the one before it.

1. **One proceedings table** (item 1). Everything downstream reads it.
2. **A decision on the file cap** (item 4). Changes the shape of the build,
   and the two options imply different keying paths -- so it comes before
   term keying, not after. An earlier draft of this list had them the other
   way round, which contradicted the closing section of this same document.
3. **Term-keyed identifiers** (item 3). Nothing archival can start without it.
4. **One term back-filled end to end** -- 2023–2024 -- as the proof. Calendars
   and journals are two requests a year; votes and dockets are bulk files;
   videos and captions are the same pipeline that runs now. Bill text is a
   link.
5. **Then the rest**, which by that point is a long fetch and a lot of disk.

The things that scale already: the marker method (per recording, cached, one
second at the median), the bulk-file pipeline, the narrative rules. The things
that do not: per-bill text fetches, and any tool that assumes one term.

---

## What I would do first

Not the archive. Consolidation before any of it. Three of the four are now
done -- this section is kept so the reasoning survives, with the state marked.

**~~Merge the two proceedings sources into one file~~** — done 5 September.
`proceedings.csv`, built by `build_proceedings.py`, read through
`proceedings.py` by all four tools that used to read the two old files.

**Split `renderDetail` and `build_site_v2.main`.** `renderDetail` was split
into one function per tab on 6 September, its output verified byte-identical
against the pre-split page over ten renders. `build_site_v2.main` is **still
outstanding, and now the first thing to do.** Removes the class of bug that
cost the second
most, and it is the one that breaks the page for a visitor arriving from a
link.

**~~Write the parser tests~~** — done. `tests/test_markers.py`, 40 cases, run
by `preflight`.

**~~Move the 35 marks into `ground_truth.csv`~~** — done. `preflight` fails if
any generator opens it for writing.

Then the archive, with the file-cap decision made **before** term-keyed
identifiers are built: R2-behind-a-Worker and fewer-static-pages imply
different paths, so deciding item 4 first stops item 3 being built twice.

---

## A note on method

Most of what worked this week came from one habit: read the artefact before
modelling it, and measure against something you did not generate. The marker
parser scored one second because every phrasing in it was read out of a real
transcript and it was scored against hand-marked times before it touched the
site. The clustering model it replaced was built before anyone read a
transcript, and its tolerances were published for months without being checked
-- they turned out to be honest, but that was luck.

The mistakes that repeated -- the floor split, the window-start time, the
silent overwrite -- repeated because the same shape of code was written in
several places rather than once. Consolidation is not tidiness here. It is the
difference between a bug fixed five times and a bug fixed once.
