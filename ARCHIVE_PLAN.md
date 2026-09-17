# Getting the whole record onto this disk

Written 8 September 2026 and revised the same day, after the three probes at
the end were run. Every number below was measured, and the measurement is
named beside it so it can be re-run.

The goal: stop fetching in chunks. Bring the New Hampshire record local — all
of it that is reachable — so that the remaining work is deciding how to
present it rather than deciding what to ask for next.

---

## What happened to this plan, 17 September

Carried out. Every lettered item below was done, one of them by a method this
page argued against; what is still outstanding is named in the table and is
small. `python3 archive_status.py` prints where each source stands today and is
still the authority; `LAUNCH.md` is the live list of what is left to do. This
page is kept for its reasoning, and each section below is true as of the date
it names.

| | what happened |
|---|---|
| A, every bill 1989–2024 | **done** — 18 terms, 31,449 bills, rather than the roughly 36,000 this page guessed |
| B, the database in full | **done** — 28 views of 28, 3,130,243 rows. `NH_RSA`, `VHearings`, `DocumentVersion`, `GeneralStatusCodes`, `BodyStatusCodes` and `DistrictPast` are all in `db/` |
| C, calendars and journals | **done bar 45** — 4,347 of 4,392 held. 44 Senate calendars are withheld as zero-padded names the source lists but has never served, and one Senate journal answers HTTP 500. Text is extracted beside 3,628 of the 4,248 PDFs; every one of the 620 without is a Senate calendar |
| D, video and captions | **done** — 4,428 indexed, captions beside 4,264. Of the 3,490 the archive drain asked for, 127 publish none and 5 are not yet broadcast |
| E, the 2017–2024 docket | **taken, and done on 11 September** — four `Docket_*.txt` files, and `Docket_2015-2016.txt` fills the fifth-of-a-year the database left in 2016 |
| F, bill text for older terms | **reversed**, below |

**The bill-text decision was reversed because the price halved.** Two requests
a bill was the price of reading a text id off a status page first. On 10
September a person found `gc.nh.gov/legislation/<year>/<HB0000>.html`, which is
constructible from a year and a padded number and carries the sponsor with
their district, the committee of referral, the title, the analysis and the full
text — one request, no search, no session. So `fetch_legislation.py` replaced
`fetch_archive_text.py`, which has never run, and the backfill is walking
backwards a term at a time and is still going as this is written. `python3
fetch_legislation.py --plan --all --from 1989 --to 2024` asks nobody anything
and prints what is saved and what is left.

---

## Where it stands, 9 September evening

`python3 archive_status.py` prints this and is the authority; the table below
is a snapshot with the reasoning attached.

| | held | of | |
|---|---|---|---|
| the public database | 28 views | 28 | **done** — 3,130,243 rows, 625 MB |
| bills, by term | 18 terms | 18 | **done** — 31,449 bills, 1989-2024 |
| videos indexed | 4,428 | 4,428 | **done** — both channels, back to May 2020 |
| House calendars | 1,589 | 1,589 | **done** |
| House journals | 629 | 629 | **done** |
| Senate journals | 511 | 512 | **done** bar one |
| Senate calendars | 998 | 1,662 | 60% — the last 664 are queued |
| text extracted beside them | 3,628 | 3,628 | **done** |
| captions | 1,131 | 4,428 | 26% |
| the 2017-2022 docket | in progress | 3 terms | fetching |
| archived bill text | not started | 31,449 bills | queued behind the docket |

**The database is finished.** Comparing `INFORMATION_SCHEMA` against
`db/_manifest.json` on 9 September found 28 objects there and 27 here; the
missing one was `vStatStudTemp`, 1,545 rows joining a statutory study
committee to the bill that created it and the RSA chapter it studies. `NHRSA`,
`NHLegislatureDB2` and `PublicNHLMS` show `publicuser` nothing at all. There is
nothing further on that host.

**What the calendars bought.** The hearings parser went from 8,008 distinct
(bill, day) pairs covering 2019-2026 to **61,429 covering 1997-2026**. Its
agreement with the docket — which nothing in the parser wrote — held across
that eightfold growth: kind 98%, room 100%, time 88%.

`python3 calendar_meetings.py --check` prints that figure and costs no network,
so read it there: 61,543 on 17 September, the change since being committee-name
variants merged rather than documents arriving. All three agreement percentages
are unchanged.

**What the calendars cost.** The drain fetched 1,846 documents over eight
hours, was answered with two HTTP 403s, and stopped itself. That was the first
time a fetch here has stopped on a refusal rather than recovering and carrying
on — and fifty-four seconds later a chained run started asking the same
address for a docket, which is why `refusal.py` now exists and why a refusal
outlives the run that met it.

**Bill text is the one large thing left, and it is two requests a bill.**
`billText.aspx` is keyed by a text id that appears nowhere on this disk for an
archived bill: `Docket.psv` has `legislationid` 0 for every row from 1989 to
2016, `Legislation.psv` is 2025-2026 only, and `LegislationText` is one
session. The id is not derivable either — for 2025 it is a small dense
sequence, for 2023 it is the sequence and the year concatenated. So it is read
off each bill's status page, which is keyed by lsr and session year, both of
which every archived bill already carries. 31,449 bills, two requests each,
fifteen seconds apart.

### The pace, and why it changed

The first drain ran at three seconds and 18 documents a minute, and one
request came back `RemoteDisconnected` — the server accepting the connection
and closing it without sending a byte, which is this address's signature for
being refused. It recovered and kept going, which is exactly the behaviour not
to have: pushing through a refusal is how the last two blocks were earned.

So the default is now **15 seconds, jittered a quarter either way**, a budget
of 150 a run, and `RemoteDisconnected` treated as its own case — one costs a
two-minute pause, two in a run ends the run whether or not they were
consecutive. That is four documents a minute and about sixteen hours for the
rest of the archive, spread over as many nights as it takes.

The goal is every document eventually, not many documents today. Nothing here
has a deadline and the server is the only party that can be inconvenienced.

### Two things learned the hard way

**A fetched PDF that no parser can read is not fetched.**
`fetch_calendar_archive.py` saves the PDF and nothing else, and
`calendar_meetings.py` reads the `.txt`. 193 calendars sat on this disk
invisible until `extract_calendar_text.py` was written — the recurring failure
of this project exactly, a step that produces nothing and exits zero.

**The archive's recordings were unreachable through the only path that fetches
captions.** `fetch_captions.py` picks from `proceedings.csv`, which knows 915
of the 4,428 videos, and hands each to `transcribe_and_align.py`, which exits
with "No manifest rows" for anything else. `fetch_archive_captions.py` fetches
the caption file and stops there — raw first, parsed second — because the
alternative is no captions for four terms until dockets nobody has agreed to
buy are fetched.

### What is left, in the order it should go

1. **Calendars and journals**, 3,813 documents at 150 a run. The journals are
   the prize: not one is on this disk and the House Journal is the only
   document in the record carrying what a member actually said.
2. **Captions**, 3,512 recordings and about 20 GB. YouTube's server, not the
   General Court's, so it can move at its own pace — but it wants its own
   window rather than running beside anything else. Half of that 20 GB is
   `captions.en-orig.json3` duplicating `captions.en.json3`; `--sub-langs en`
   would halve it at the cost of diverging from the 915 folders already here.
3. **The 2017-2024 docket**, still the one open decision: ~7,200 requests, and
   at fifteen seconds that is thirty hours. The bill lists for those years are
   now local, so what is missing is the sequence of what happened to each one.

---

## 1. Five archives, and how far each one goes

| | span available | on this disk, 8 September | where it comes from |
|---|---|---|---|
| Bill lists and status | 1989–2026 | 2 terms (4,230) | Advanced Bill Status Search, **2 requests a year** |
| Dockets | 1989–2016, 2025–2026 | 2 terms | **the database, free** — 317,811 rows |
| Roll calls | **1999–2026, no gaps** | 2 terms | **the database, free** — 9,565 votes, 2,303,047 individual ballots |
| Calendars and journals | House **1997–2026**, Senate **1998–2026** | 376 calendars, **0 journals** | the index's own dropdowns, one request a document |
| Video and captions | **2020–2026, 4,428 videos** | 1,418 indexed, 883 with captions | YouTube uploads playlist |

Three spans are worth saying out loud because they change what this site can
be.

**Roll calls go back to 1999 and cost nothing.** `RollCallSummary` and
`RollCallHistory` hold 27 years without a gap — 2.3 million individual ballots
— on the SQL host the General Court publishes credentials for. That is every
recorded vote by every member for thirteen terms, and it is a query, not a
crawl.

**The video record is more than three times what we knew about.** Both
channels were walked to the end on 8 September: the House has **3,029 videos
back to 14 May 2020** and the Senate **1,399 back to 29 May 2020**. The site
knows about 1,418 of those, because the index was only ever fetched from
January 2025. The other **3,010 cover two whole terms the site has no
recordings for at all**, including the 2023–2024 term that is already
published as cards.

**The docket has an eight-year hole and the database does not fill it.**
1989–2015 is complete, 2016 is a fifth of a year (1,962 rows against a normal
9,000), and **2017–2024 is absent**. The probe below asked the other seven
databases on that server and none of them has a `Docket` view. So those eight
years cost about 7,200 web requests or they do not happen — see §3E.

---

## 2. What is already here

Measured 8 September:

```
status_pages/       4,230 pages   91 MB    two terms, every bill
bill_text/          2,234 pages   50 MB    current term, ONE version each
calendars/            172 PDFs    70 MB    House, 2023-2026
calendars_senate/     204 PDFs    51 MB    Senate, 2023-2026
work/                 915 recordings       captions and transcripts, 5.0 GB
                       34 audio.wav        15.3 GB of intermediate WAV
```

`work/` is 20.3 GB and **15.3 GB of it is 34 `audio.wav` files** — the
intermediate the Whisper path writes before transcribing. They are
regenerable from YouTube and nothing reads them after the transcript exists.
Deleting the transcribed ones is the cheapest 15 GB on this machine, and it
roughly pays for the whole PDF archive below.

Journals: none. Not one, in either chamber, for any year. The House Journal is
the only document in the record that carries what a member actually **said**,
and the roadmap already calls it the largest content addition available.

---

## 3. What each remaining piece costs, in requests

Ordered by value per request, which is the order to do them in.

### A — Every bill, 1989 to 2024. **72 requests.**

The Advanced Bill Status Search answers a session year with every bill of
that year on one page: title, general and per-chamber status, last committee,
last hearing, and the links each bill cites. `fetch_archive_bills.py` already
does this and already parses it — 2023 returned 675 bills and 2024 returned
1,321 for four requests.

Thirty-six session years at two requests each is **72 requests for roughly
36,000 bills**. Nothing else on this page comes close to that ratio. Do it
first, in one evening.

### B — The database, in full. **About 40 queries. No web requests at all.**

One SELECT per view, streamed to file through `probe_db.run_to_file` where the
answer is more than a few thousand rows. Row counts already measured:

| view | rows | what it is |
|---|---|---|
| `RollCallHistory` | 2,303,047 | every ballot, 1999–2026 |
| `RollCallSummary` | 9,565 | every recorded vote |
| `Docket` | 317,811 | 1989–2016 and 2025–2026 |
| `houseRemoteTestify` | 402,918 | testimony sign-ins, 128,854 with written text |
| `NH_RSA` | 29,785 | the statutes themselves |
| `VHearings` | 8,728 | hearings, which is what "upcoming hearings" needs |
| `LegislationText` | 6,825 | **three versions per bill**, current term |
| `CandH_Reports` | 5,597 | committee reports |
| `Legislators` | 1,081 | the roster |
| `CommitteeMembers` | 814 | who sat on what |

`NH_RSA` and `VHearings` were counted but never fetched. The first would let
the RSA linker point at the statute's own words instead of at a citation; the
second is the table behind the hearing-schedule feature already planned for
the next term. **Both were fetched in the sweep** — `db/NH_RSA.psv` holds
29,785 rows and `db/VHearings.psv` 8,739 — along with the other 26.

**What the eight-database question turned up.** `NHLegislatureDB2` and `NHRSA`
answer nothing at all — not one known view name, and `INFORMATION_SCHEMA` is
closed to this account on both. `PublicNHLMS` is a different thing entirely:
it is the drafting system behind the public record, and two of its views are
worth having.

- **`DocumentVersion`, 54 rows** against the 13 in `NHLegislatureDB`. It is
  the authoritative version vocabulary — Introduced, As Amended by the House,
  As Amended by the House (2nd committee), Conference Committee report,
  Version adopted by both bodies, Adopted in concurrence, FINAL VERSION,
  CHAPTERED FINAL VERSION — each with a **`SortOrder`** and a **`SendToWEB`**
  flag. That is exactly what the version switcher in `ROADMAP.md` needs: the
  order of the versions is a published column, not something to infer, and the
  flag says which ones the public is meant to see.
- **`Legislation`, 2,428 rows** against 2,234 in the public view, on a
  different schema: `IntakeNbr` ("IN 25-0006"), `RequestReceiveDate`,
  `Confidential`, `IntakeTitleText`, `AttorneyReAssigenedDate`. This is the
  LSR pipeline — bills before they are bills, including 194 that never became
  one. Interesting, and a decision of its own: some of it is drafting-stage
  material and the `Confidential` column exists for a reason. Read before
  publishing anything from it.

### C — Calendars and journals. **About 5,500 documents.**

Confirmed at the index on 8 September. The House offers **30 years, 2026 back
to 1997**; the Senate **29 years, back to 1998**. Both have a Journals option
beside Calendars — `Calendar`/`Journal` in the House, `SenateCalendar`/
`SenateJournal` in the Senate. The document dropdown's option values are the
real filenames, so one postback lists a whole year and nothing is guessed.

Per year, per chamber, roughly 50 calendars and 40 journals:

```
listing      118 postbacks       30 House years x 2 kinds + 29 Senate years x 2
documents    ~5,500 requests     at 350 KB each, about 1.9 GB
```

At five seconds apart that is eight hours of requests. It should not be eight
hours; see §4.

### D — Video and captions. **Free to index, 24 GB to keep.**

Done for the index, on 8 September: 61 pages for the House and 28 for the
Senate, about 90 quota units against a daily allowance of ten thousand. The
whole result is in `channel_index_full.json`.

```
            2020  2021  2022  2023  2024  2025  2026   total
House         33   378   440   666   539   570   403   3,029
Senate       106   218   186   217   226   245   201   1,399
```

Captions are one request a video, to YouTube rather than to the General Court,
and land at about 5.5 MB a recording. 883 are already here, so **3,545 remain
— roughly 20 GB**. That is the largest single item on this page by disk and
the cheapest by politeness, since it is not the General Court's server.

### E — The 2017–2024 docket. **~7,200 requests, and now known to be the only way.**

One request per bill, and the only item here that is a crawl rather than a
question. `fetch_archive_docket.py` exists and paces at 1.5 s. The hope was
that another database on that server held it; the probe says none does. So
this is a real decision rather than a deferred one:

- **Take it**, and eight years get the sequence of what actually happened to
  each bill — the material every narrative on this site is built from.
- **Leave it**, and those years have bill lists, statuses and roll calls but
  no story, which is what the 2023–2024 term looked like before its dockets
  were fetched.

Either way it goes last, after everything cheap is in.

**Taken, and done on 11 September.** `Docket_2017-2018.txt`,
`Docket_2019-2020.txt` and `Docket_2021-2022.txt` sit beside the
`Docket_2023-2024.txt` that was already here, and `Docket_2015-2016.txt` fills
the fifth-of-a-year the database left in 2016. All five carry the same seven
columns as `Docket.txt`, so `narrative.py` reads them unchanged.

### F — Bill text for older terms. **Not planned.**

38,000 requests for a document that is one link away, on the address that
blocked us twice. `ARCHITECTURE.md` decided against this and the decision
stands. `LegislationText` covers the current term with every version; older
terms link out.

**Reversed on 10 September.** The arithmetic that made it not worth planning
was two requests a bill against a server that had blocked us; the archive path
found that day is one request against a constructible address, which is a
different sum. `fetch_legislation.py --plan --all --from 1989 --to 2024` prints
what is left of it — a figure that falls with every night the lane runs, so
read it there rather than here.

---

## 4. The method: one queue, one worker, discovery before fetching

The three rules that produced every good result here — read the artefact,
measure against something you did not generate, silence is not success — need
a shape at this scale. This is that shape.

**Discovery and fetching are separate programs.** Discovery asks a source what
it has and writes rows to the queue: the index dropdown for calendars, the
search-by-year for bills, the uploads playlist for video. Fetching only ever
drains the queue. **Nothing is ever constructed from a filename convention** —
that is what got this address blocked, and the calendars alone use at least
three incompatible filename forms across the thirty years being asked for.

**One queue, and it is a file.** `archive/queue.csv`, one row per wanted
artefact:

```
chamber, kind, year, name, url, path, state, attempts, error, bytes, fetched
```

(Those are the columns as built. This page planned `source, key, url,
target_path, state, attempts, last_error, fetched_at, bytes`, and the source
turned out to be keyed by chamber and year rather than by an opaque key.)

`state` is one of wanted / held / failed / gone — and, as built, `withheld`,
which the 44 Senate calendars marked on 12 September carry: a name the source
lists, that answered 403 twice, and that no browser has yet been shown to
serve. A file already on disk is never requested again, so an interrupted run
resumes by re-reading the queue and every run is idempotent.

**One worker, and concurrency is structurally impossible.** The queue is
drained by a single process holding a lock file. Two fetches at once is what
got this address blocked the second time; a rule you have to remember is worse
than a design that cannot do it.

**Pacing is adaptive and already written.** `fetch_bill_text.py` carries a
limiter that watches the median response time, slows from 0.6 s to as much as
30 s when responses take three times as long as the baseline, and eases back
when the server recovers. That belongs in a module both fetchers import rather
than in one of them.

**A nightly budget, not a marathon.** A run takes `--budget 800` requests and
stops, whether or not the queue is empty. 5,500 documents is then a week of
quiet nights rather than one long crawl that looks exactly like an attack from
the far end.

**Stop-loss.** Three consecutive failures ends the run. A 403, or
`RemoteDisconnected` twice in a row, ends it and says loudly that it did —
`netcheck.py` then diagnoses without making anything worse.

**Raw first, parsed second.** Every fetch writes the artefact verbatim to the
store. Parsers read the store and never the network, so a parser can be
rewritten and re-run over thirty years of documents at no cost to anyone
else's server. This is already the pattern in `status_pages/` and `bill_text/`
and it is what makes "complete locally" worth having.

**A ledger that can say what is missing.** `archive_status.py` prints, per
source per year: wanted, held, failed, never-listed. "Complete" has to be a
number this prints, not a feeling.

---

## 5. What changed over the years

The user's phrase was "finding out info that's changed over the years", and it
is the part of this most likely to go wrong quietly. Thirty years of a
government's output is not one format. Three eras are now measured rather than
suspected.

**Filenames have at least three eras.** `HC 32.pdf` (2026); `No 51 December 29
2023.pdf` (2023 and 2006); `HJ No 21 09-04-2003.pdf` (2003). Day padding is
inconsistent inside a single year, and 2026 carries two forms at once — its
two most recent entries switched to `HC NN.pdf` while the rest below them did
not.

**(year, number) is not a key.** The 2003 journal list holds `HJ No 21
09-04-2003` and `HJ No 21 06-30-2003` — the same number twice — and `HJ No 23
01-07-2004`, a 2004 date filed under 2003 because the session runs into
January. The filename is the only identifier the source offers, so it travels
verbatim and is never parsed into parts and rebuilt.

**The Senate renamed its videos at the start of 2023.** Measured against the
title pattern in `fetch_channel_index.py`, over the full 4,428:

```
          2020  2021  2022  2023  2024  2025  2026
House      88%   87%   96%   98%   99%  100%   99%
Senate      1%   14%   10%  100%  100%  100%   99%
```

**459 Senate recordings from 2020–2022 cannot be read by the current
pattern**, and their forms are now known:

```
Senate Education (02/08)                              month and day, NO YEAR
Senate Finance Committee Budget Work Session-May 19   a written date, hyphen
Senate Election Law and Municipal Affairs             committee only, no date
REMOTE MEETING OF COMMISSION ON PRETRIAL DETENTION    not a committee at all
```

And a trap inside that: **the video is published the day after the meeting**.
`Senate Education (02/08)` was posted on 2022-02-09. Falling back to the
publish date where the title carries none would misdate the recording by one
day and file it against the wrong day's hearings — a silent, plausible,
entirely wrong answer of exactly the kind this project exists not to give.

The House's 91 misses are mostly not legislative at all: `Inside New
Hampshire's Golden Dome`, `NH Fallen Officer Memorial Ceremony 2026`, a state
house video tour. Those should be recognised and skipped, not forced.

**Status vocabulary and districts are still unread.** `GeneralStatusCodes` and
`BodyStatusCodes` are views, and whether they carry codes retired before 2016
decides whether `STATED` in `build_site_v2.py` covers the archive or only the
present. `DistrictPast` exists as a view and has never been read; a 1998
member's district is not today's district, and presenting it as though it were
would be the same class of error as the misdated recording.

**All three are now dumped** — `GeneralStatusCodes` 10 rows,
`BodyStatusCodes` 76, `DistrictPast` 235 — which answers where they are, not
what they say. `build_site_v2.py` reads the body codes. Nothing in the
repository reads `DistrictPast` at all, so the warning in the paragraph above
still stands and is now a warning about a file that is sitting there.

So the survey stays a step, not an afterthought: **once a source is listed,
sample one document per era before writing a parser for it.** One from 2026,
2015, 2005, 1997. The timestamp method scored one second because it was built
from real transcripts, and its predecessor was twelve times worse because it
was built from an assumption. That asymmetry applies here thirty times over.

---

## 6. Order of work

1. **The database sweep** (B). No web requests, ~40 queries, and it includes
   `NH_RSA`, `VHearings` and `PublicNHLMS.DocumentVersion` — the last of which
   unblocks the version switcher.
2. **Every bill 1989–2024** (A). 72 requests, one evening, ~36,000 bills.
3. **Captions for the 3,010 newly found recordings** (D). A different host
   from the General Court, so it can run on its own schedule. Two whole terms
   of hearings and floor debates the site has never had.
4. **Calendars and journals** (C). The long one. All 118 listings first, so
   the queue is complete and measurable, then nightly budgets against it.
5. **The 2017–2024 docket** (E), if it is judged worth 7,200 requests.

Steps 3 and 4 are the only two that could overlap, and they must not: one
worker, one queue, whatever the hosts.

**All five are done**, and so is F, which this list does not carry because §3
did not plan it. The table at the top of this page says how each one landed.
Steps 3 and 4 did not overlap; the docket chain that followed them waited on
`archive/.lock` and, on one morning, was stopped by hand because the calendar
run before it had ended on two 403s against the same address.

---

## 7. Two things this does not solve

**Publishing is a different constraint from fetching.** Cloudflare Pages allows
100,000 files on the current plan and the site uses 14,112 for two terms —
about 3 files a bill. Thirty-six thousand archived bills at that rate is
108,000 files and does not fit. The archive is therefore fetched in full and
**published as cards, not pages**, which is the shape already agreed for
2023–2024. Nothing in this plan needs deciding differently, but nothing in it
should be read as a promise of a page per bill either.

**That promise was made anyway, by changing the rate rather than the shape.**
Three files a bill was what made 36,000 bills not fit. A record now travels
inside its own page, so a bill costs one file: `site/bill/` holds one for each
of the 33,683 bills, in a folder per year from 1989 to 2026, and they are
pages rather than cards. The cap is still 100,000 — Pages Pro, not the 20,000
in Cloudflare's general docs — and `python3 check_site.py` prints the site's
file count and warns above 90,000, so that is the number to read rather than
any written here.

**Disk.** About 1.9 GB of PDFs and about 20 GB of captions. Deleting the 34
transcribed `audio.wav` files covers most of it.

---

## 8. What the probes found

Run 8 September, six requests and about a dozen queries, before any of the
above begins.

| probe | answer |
|---|---|
| the views in `NHLegislatureDB2`, `PublicNHLMS`, `NHRSA` | **no `Docket` anywhere.** 2017–2024 costs 7,200 requests or nothing. `PublicNHLMS` holds the drafting system, and its `DocumentVersion` is the version order the diff feature needs |
| both YouTube channels, walked to the end | **4,428 videos back to May 2020**, 3,010 of them unknown to the site — two whole terms of recordings |
| the year dropdowns, both chambers | **House 1997–2026, Senate 1998–2026**, journals listed beside calendars in both |

Nothing in this plan is now written as a range.
