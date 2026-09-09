# Getting the whole record onto this disk

Written 8 September 2026. Every number below was measured, not estimated, and
the measurement is named beside it so it can be re-run.

The goal: stop fetching in chunks. Bring the New Hampshire record local — all
of it that is reachable — so that the remaining work is deciding how to present
it rather than deciding what to ask for next.

---

## 1. Five archives, and how far each one goes

| | span available | on this disk | where it comes from |
|---|---|---|---|
| Bill lists and status | 1989–2026 | 2 terms (4,230) | Advanced Bill Status Search, **2 requests a year** |
| Dockets | 1989–2016, 2025–2026 | 2 terms | **the database, free** — 317,811 rows |
| Roll calls | **1999–2026, no gaps** | 2 terms | **the database, free** — 9,565 votes, 2,303,047 individual ballots |
| Calendars and journals | **1997–2026** | 376 calendars, **0 journals** | the index's own dropdowns, one request a document |
| Video and captions | unknown, ≥2024 | 1,418 indexed, 883 with captions | YouTube uploads playlist |

Two spans are worth saying out loud because they change what this site can be.

**Roll calls go back to 1999 and cost nothing.** `RollCallSummary` and
`RollCallHistory` hold 27 years without a gap — 2.3 million individual ballots
— on the SQL host the General Court publishes credentials for. That is every
recorded vote by every member for thirteen terms, and it is a query, not a
crawl.

**The docket has an eight-year hole.** 1989–2015 is complete, 2016 is a
fifth of a year (1,962 rows against a normal 9,000), and **2017–2024 is not
in the database at all**. Those eight years exist on the web at one request
per bill, which is about 7,200 requests — the single most expensive item on
this page, and the only one that deserves an argument.

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
Deleting the transcribed ones is the cheapest 15 GB on this machine.

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

One SELECT per view per year where a view is large, streamed to file through
`probe_db.run_to_file`. What that gets, with row counts already measured:

| view | rows | what it is |
|---|---|---|
| `RollCallHistory` | 2,303,047 | every ballot, 1999–2026 |
| `RollCallSummary` | 9,565 | every recorded vote |
| `Docket` | 317,811 | 1989–2016 and 2025–2026 |
| `houseRemoteTestify` | 402,908 | testimony sign-ins, 128,854 with written text |
| `NH_RSA` | 29,785 | the statutes themselves |
| `VHearings` | 8,728 | hearings, which is what "upcoming hearings" needs |
| `LegislationText` | 6,825 | **three versions per bill**, current term |
| `CandH_Reports` | 5,597 | committee reports |
| `Legislators` | 1,081 | the roster |
| `CommitteeMembers` | 814 | who sat on what |

`NH_RSA` and `VHearings` were counted but never fetched. The first would let
the RSA linker point at the statute's own words instead of at a citation; the
second is the table behind the hearing-schedule feature already planned for
the next term.

Also unexplored, and one query settles it: this server holds **eight
databases**, and only `NHLegislatureDB` has been read. `NHLegislatureDB2`
exists and answers nothing under the same view names; `PublicNHLMS` answers
`Legislation`, `LegislationText`, `DocumentVersion` and testimony. **If the
2017–2024 docket lives anywhere, it is in one of those two**, and finding it
turns the most expensive item on this page into a free one. Ask before
assuming it does not.

### C — Calendars and journals, 1997 to 2026. **About 5,400 documents.**

The index at `gc.nh.gov/{house,senate}/calendars_journals/` lists every
calendar and every journal, by number and date, for **thirty years back to
1997**, and the document dropdown's option values are the real filenames.
`probe_calendars.py` established this on 6 September and
`fetch_senate_calendars.py` already fetches against it. One postback lists a
whole year.

Per year, per chamber, roughly 50 calendars and 40 journals. Thirty years,
two chambers, minus the 376 calendars already here:

```
listing      ~120 postbacks      one per year per kind per chamber
documents    ~5,400 requests     at 350 KB each, about 1.9 GB
```

At five seconds apart that is eight hours of requests. It should not be eight
hours; see the method below.

### D — Video and captions. **Cheap on quota, heavy on disk.**

Both channels are walked through the **uploads playlist**, which costs one
YouTube API unit per fifty videos against a daily allowance of ten thousand.
Indexing every video either channel has ever posted costs a few hundred units
— call it free.

What is unknown is **how far back the channels go**. The index was only ever
fetched from 1 January 2025, so 1,418 videos are known and the back catalogue
is unmeasured. One API call per channel answers it and should be the first
thing done here.

Captions are a separate request per video, to YouTube rather than to the
General Court, and land at about 5.5 MB a recording. 535 already-indexed
videos have no captions on disk; 19 of those are known to have none available.

### E — The 2017–2024 docket. **~7,200 requests. Decide after B.**

One request per bill, and the only item here that is a crawl rather than a
question. `fetch_archive_docket.py` exists and paces at 1.5 s. Do not start it
until the database question in B is answered, because the answer may delete
the whole item.

### F — Bill text for older terms. **Not planned.**

38,000 requests for a document that is one link away, on the address that
blocked us twice. `ARCHITECTURE.md` decided against this and the decision
stands. `LegislationText` covers the current term with every version; older
terms link out.

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
source, key, url, target_path, state, attempts, last_error, fetched_at, bytes
```

`state` is one of wanted / held / failed / gone. A file already on disk is
never requested again, so an interrupted run resumes by re-reading the queue
and every run is idempotent.

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
stops, whether or not the queue is empty. 5,400 documents is then a week of
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

## 5. What changed over the years, and finding out before parsing

The user's phrase was "finding out info that's changed over the years", and it
is the part of this most likely to go wrong quietly. Thirty years of a
government's output is not one format. What is already known:

- **Filenames have at least three eras.** `HC 32.pdf` (2026); `No 51 December
  29 2023.pdf` (2023 and 2006); `HJ No 21 09-04-2003.pdf` (2003). Day padding
  is inconsistent inside a single year, and 2026 carries two forms at once.
- **(year, number) is not a key.** The 2003 journal list holds `HJ No 21
  09-04-2003` and `HJ No 21 06-30-2003` — the same number twice — and
  `HJ No 23 01-07-2004`, a 2004 date filed under 2003 because the session runs
  into January. The filename is the only identifier the source offers, so it
  travels verbatim and is never parsed into parts and rebuilt.
- **Status vocabulary is in the database.** `GeneralStatusCodes` and
  `BodyStatusCodes` are views. Whether they carry codes retired before 2016 is
  one query, and it decides whether `STATED` in `build_site_v2.py` covers the
  archive or only the present.
- **Districts and committees are not stable.** `DistrictPast` exists as a view
  and has never been read. A 1998 member's district does not mean today's
  district, and presenting it as if it did would be the kind of confident wrong
  answer this project exists not to give.

So the survey is a step, not an afterthought: **once a source is listed, sample
one document per era before writing a parser for it.** One from 2026, 2015,
2005, 1997. The timestamp method scored one second because it was built from
real transcripts and its predecessor was twelve times worse because it was
built from an assumption; the same asymmetry applies here, thirty times over.

---

## 6. Order of work

1. **The database sweep** (B). No web requests, answers the biggest open
   question, and includes the 2017–2024 hunt in `NHLegislatureDB2` and
   `PublicNHLMS`.
2. **Every bill 1989–2024** (A). 72 requests, one evening, ~36,000 bills.
3. **Both channels' full index** (D, first half). Two API calls; tells us what
   the video archive actually is before planning to fetch it.
4. **Calendars and journals** (C). The long one. Listing first, all of it, so
   the queue is complete and measurable; then nightly budgets against it.
5. **Captions**, paced alongside 4 but against a different host.
6. **The 2017–2024 docket** (E), only if step 1 says it is not free.

---

## 7. Two things this does not solve

**Publishing is a different constraint from fetching.** Cloudflare Pages allows
100,000 files on the current plan and the site uses 14,112 for two terms —
about 3 files a bill. Thirty-six thousand archived bills at that rate is
108,000 files and does not fit. The archive is therefore fetched in full and
**published as cards, not pages**, which is the shape already agreed for
2023–2024. Nothing in this plan needs deciding differently, but nothing in it
should be read as a promise of a page per bill either.

**Disk.** The archive fetch adds roughly 2 GB of PDFs and, if the video back
catalogue is as large as the current one, another 20 GB of captions. Deleting
the 34 transcribed `audio.wav` files pays for the PDFs eight times over.

---

## 8. What to run first, and what it costs

Three probes, each one question, before any of the above begins:

| probe | requests | answers |
|---|---|---|
| list the views in `NHLegislatureDB2` and `PublicNHLMS` | 2 queries | whether 2017–2024 is free or costs 7,200 requests |
| the uploads playlist of both YouTube channels | 2 API calls | how far back the video record goes |
| the year dropdown on both chambers' calendar index | 2–4 requests | how far back journals go, and how many there are |

Six requests and four queries. Every number in this plan that is currently a
range becomes a figure, and the queue can then be built complete before a
single document is fetched.
