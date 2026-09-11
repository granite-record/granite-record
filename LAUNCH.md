# Granite Record — what is done, what is not, and what to do first

Rewritten 9 September 2026, in the evening, after the site went live, and
brought current on the 10th. Every number here was measured when it was typed,
and by the next morning several were wrong -- which is the case for reading
`STATE.md`, which is generated, for any count that matters.

The previous version listed items 6, 7 and 8 twice — once struck through and
once not — which is what happens when a working list is updated in pieces. It
is renumbered here in one pass.

---

## 1. Live

Published 9 September, five times on the 10th, and at 12:44 on the 11th
with that day's 24 commits. **92 preflight checks then, `check_site` ready,
55,318 files — 55% of the 100,000 Cloudflare Pages allows.** MIT-licensed,
with a README, since the 10th.

The 10th was the day the archive stopped being a list of bills and became a
record: votes for twenty-four years, committees for ten terms that had none,
hearings for ten terms whose hearings were thought lost, and a name and a
party on nearly every ballot ever cast.

| | |
|---|---|
| Bills | **33,683 across 19 terms**, 1989 to 2026, each with its own page |
| Legislators | 406 sitting, **2,192 who have served** |
| Committees | 53 |
| Data | **nineteen CSV tables at `/data`**, 2,419,330 rows, a manifest, rebuilt every run |
| Towns | **320 town-and-ward pages** — everyone who represents you, with contact |
| Civics | 11 topics at `/learn/` |
| Feeds | per bill, committee, topic and hearing |
| Veto messages | 175, each cited to the calendar it was printed in |
| Roll calls | **9,565 across 1999–2026**, 2.3M ballots, every term named and partied |
| Hearings | **50,911 proceedings across eleven terms**, 1989–2026 |
| Hearings parsed from calendars | **61,429 bill-days, 1997–2026** (not yet merged) |
| The archive on disk | 28 database views / 3.1M rows; House calendars and journals 100% |

## 2. Running

Everything the General Court is asked now goes through **one lane**,
`watchers/gc_lane.py`, which runs `watchers/gc_lane.queue` a step at a time
holding `archive/.lock`. `watchers/README.md` says how to watch it.

**Running again since 12:47 on the 11th, at 25 seconds a page rather than
15.** It stopped itself at 11:36 on a refusal, as designed: the 2015-2016
docket met two read timeouts (the address not answering within 60 s), and
two dropped connections is this address's sign of refusing, so the fetch
recorded it in `archive/refused.json` and the lane stopped and released the
lock with 381 of the 1,072 pages for 2016 on disk. `netcheck.py` at 12:37
found the address answering as in every run on record -- a browser's agent,
HTTP/1.1 on both hostnames and plain http all answered, HTTP/1.0 refused as
it always has -- and the refusal was cleared on the person's standing
permission. The first pages after the restart came back whole, so our own
agent is answered too. Both earlier runs that day slowed or stopped about 90
minutes in and during business hours -- a guess, not a finding, that the
evenings go better, and the reason for the slower pace. `build_all` skips
its own General Court steps while a refusal or the lane's lock is on file.

- **Docket**: 2017-2022 are done. **2015-2016 is running** (from the 11th):
  the database's "2016" rows turned out to be the 2015 history of 190
  carried-over bills, so all 1,072 bills filed under 2016 are asked from
  their own pages, seeded by `Docket_db_2015.txt` (the 716 bills filed under
  2015, with their own LSR).
- **Bill text**, queued behind it: `fetch_legislation.py`, one request a
  bill, 31,003 for 1989-2024 by `--plan`. Every address was settled by hand
  in a browser: the static path for 1989-2021 (1996 at `.htm`, even-year
  four-digit bills included), and `billText.aspx` with **the stored id and
  `sy=<year>`** for 2016 and 2022-2024 -- opened on the 11th, `id=32&sy=2023`
  serves 2023 HB42. The rule this document stated until then, that 2023-2024
  want the year appended, was wrong for 1,826 of 1,996 bills and would have
  saved 615 of them under another bill's name. Floor resolutions (LSR 8000+)
  have no text (1990 HR55, opened by hand) and are not asked. Before any of
  it ran, three read-only reviewers went through the fetchers: every page
  must print the bill's own LSR, 404s go on an address-keyed gone-list, and
  both fetchers read refusals through `refusal.classify()` -- a reset wrapped
  in a URLError is a dropped connection, a 503 or the block page a refusal.
  **No consumer yet**: the pages are raw-first and wait for the decision on
  what an archived bill page shows.
- **Captions**, YouTube: the watcher, restarted on the 11th with 676 wanted.

**Sponsors: `byAnyMember.aspx` answers, and it changes the plan.** Opened by
hand on the 10th. One combobox of **2,614 distinct past and present
legislators**, no session-year selector at all, and two radio buttons --
Prime Sponsored and CoSponsored. Choosing a member returns every bill they
sponsored as `Year | Bill # | Status | Title`, **back to 1989**: Rep. Elsie
Vartanian (Rock. 20) comes back with HB175 and HB569 of 1989 and three bills
of 1990. Each row links `billinfo.aspx?sy=1989&Pastid=<lsr><year>`, so the
LSR is in the address and the join to `data/bills.json` is exact rather than
a match on a surname.

That is **5,228 requests** -- two per member -- for the sponsors of every
term from 1989 to 2026, against 7,830 for five terms alone one bill at a
time. It also returns a member's full first name, where a bill's own text
gives only "Rep. Vartanian".

One caveat, from the one bill checked against another source: HB1 of 1989 is
a SPECIAL SESSION bill (LSR 1989-9100) and its text names Vartanian, but it
appears in neither of her lists. Whether special sessions are excluded or
filed elsewhere is not known from one sample, and should be measured against
the archived bill text before this route is trusted alone.

`refusal.py` stops every fetch for 24 hours when the address says no, and
clearing it is a person's decision.

## 2a. Sources found by hand, and what each is for

Six addresses were opened in a browser on 10 September and each changed a
plan. Kept together because the pattern is worth seeing: every one of them
answered a question this project had been about to spend days inferring.

- **`legislation/1996/HB0297.htm`** -- 1996 is served at `.htm`, and the only
  address that fails is the one the archive itself publishes.
- **`byAnyMember.aspx`** -- 2,614 past and present legislators in one list,
  keyed by the Employeeno the roll call history uses. It named 733,474
  ballots that said "Member #330274", and it is the route to sponsors for
  every term at two requests a member.
- **`Roll_calls/billstatus_rcdetails.aspx?sy=&vs=&lb=`** -- every voter's
  PARTY, county and district. 54 requests closes a 773,506-ballot gap that
  the day before looked unclosable.
- **`docket_abbrev.htm`** -- the General Court's own key to its docket, kept
  as `docket_abbrev.json`. It settled JUD (Judiciary and Family Law) and
  ECON DEVEL, which nothing else on this disk ever spells out, and it is the
  vocabulary the archived docket is written in: LOT, ITL, OTP/AM, MA, MF,
  VV, DIV, RC, MAJ REPORT, MIN REPORT. Narrating 1989-2015 needs it.

### Two leads, recorded rather than acted on

- **Amendment texts.** Floor amendments are printed in the House calendars
  and journals, which are on disk for 1997-2026 and need no network. Committee
  amendments are not known to be anywhere. `bill_versions.json` is 2025-2026
  only, so every archived term has a bill's text and none of its amendments.
- **`scholars.unh.edu/senate_house/`** -- scanned House and Senate journals
  at UNH, not digitised, in a structure quite unlike the modern ones. It is
  the only candidate found so far for the years the database does not reach:
  roll calls stop at 1999, so 1989-1998 has no recorded vote anywhere. Worth
  opening once the modern terms are finished, and not before -- OCR of
  scanned journals is a project of its own, and everything else here is
  cheaper per fact.

## 3. The bench

`python3 review.py` — local only, loopback address, nothing on the site. One
sample at a time: a verdict, a correction, a note, appended to
`review/checked.jsonl`, which is hand-made evidence and is protected the way
`ground_truth.csv` is.

| kind | pool |
|---|---|
| Bill hearing timings | 6,279 published boundaries |
| Plain-language histories | 4,198 |
| Hearings read from calendars | 97,158 |
| Governors' veto messages | 175 |
| Committee report reasoning | 4,274 |

A timings item embeds the recording, shows both printed times, and captures
the player's current position straight into the field — so a judgment is play,
pause, press, rather than read-off-and-retype.

**It is being used.** Dozens of judgments across all five kinds by the 10th,
and `probe_alignment.py --truth` reads them beside `ground_truth.csv`. Related
bills and auto-assigned topics still wait on a checked sample of their own.

Its samples are built when it starts and **cached on disk** in
`review/.pool-<kind>.json`, so after a parser changes or the site is rebuilt
it goes on serving the old ones -- across restarts too -- until it is
restarted with `--refresh`.

A sixth kind since the 11th, **Hour-late recordings**: every proceeding on
the nine recordings whose YouTube caption track runs an hour behind its own
video (seen in YouTube's own player). The page prints no time for them, so
the bench shows none either and asks for the time. One timing per recording
decides whether an hour's shift can put 76 stated starts back.

---

## 4. What is left

### Small and visible

1. **Special-bill notes.** *HB1 and HB2 shipped on the 10th* from
   `bill_notes.json`, hand-written and protected, applied from 1993-1994
   onward because the 1989 and 1991 HB1s are not budgets. The transportation
   plan -- a different number every term -- has a `by_term` section waiting
   for it.
2. **Dark mode**, favicon and logo. The footer is on every page and the
   redundant status block is gone.

### Larger, and each unlocks something

3. ~~**Wire the video match.**~~ *Done on the 10th.* `proceedings.csv` went
   from one term to seven: 2023-2024 landed with 854 recordings, and
   2017-2018 and 2019-2020 as hearings without video, which is correct for
   years before the House streamed. The current term came through
   station-for-station identical.
4. **Roll calls on legislator pages.** *Mostly done on the 9th*: each row
   names the bill and its title, the question in plain English, the outcome
   with its tally, and whether the member took their own party's side --
   stated as a count with its denominator, never a score. Not yet grouped by
   session day.
5. ~~**Amendment diffing.**~~ *Shipped.* Every version of a bill and what
   each amendment changed, as a Versions tab; 9,471 files under
   `site/versions/`, which is most of the file-count growth since the 9th.
6. **Committee pages: upcoming hearings**, and a session day as a table —
   every bill heard, its status change, the report split, bill numbers linked.
7. **A member's whole career on their page.** `careers.json` exists: 2,211
   employee numbers resolved to **2,192 people**, 17 who served in both
   chambers and 289 who left and came back. Nothing on the site reads it yet,
   and it needs the archived roll calls built before it says much.
8. **Narrative prose into the HTML.** A bill page gives a crawler about 137
   words;
   everything else arrives by JavaScript. The narrative already exists — a
   median of 192 words of specific prose — and putting it in the `<noscript>`
   block is a text dump, not a second renderer. Worth doing when the 2017–2022
   dockets land, because only 12% of bills have a narrative today.

### New surface

9. **A session calendar page**: the consent calendar, the regular calendar and
   the committee motions, in order, explained.
10. **Related bills** — after the bench, never before. The hard part is
    already named: two bills can touch the same RSA for unrelated purposes,
    and two bills can do the same thing through different RSAs.
11. **Topics for the eighteen terms without them.** Visibly derived, method
    stated on the page, scored against a checked sample.

### Not blocking

12. Email routing, and the follow-by-email decision a static site cannot make
    on its own.
13. Accessibility, continuously.
14. `build_site_v2.main` is **468 lines** and the longest function in the
    file, now that `build_bills` has gone from 544 to 294 in nine
    byte-identical steps. The station code that caused the floor-marker miss
    already came out; what is left in `main` is the loading.

---

## 5. Answered, and the answer was no

**Ranking and deputy ranking members.** Asked for as "typically the first two
names listed in the minority". Every source on this disk was searched: the
database's `CommitteeMembers.comments` holds only Chairman, V Chairman and
Clerk; `committees.json` positions are Chair, Vice Chair and Member; and the
only "ranking member" text in the calendars is statutory language inside bill
text. Naming one would infer a real person's leadership role from list order.
Publishable only if the page says it is inferred, and worth checking against a
few real committees first — the bench again.

**Party for eight of the ten offices in `officials.json`.** `senate.gov` gives
(D) for both senators. `governor.nh.gov`, `council.nh.gov` and the members'
own house.gov sites do not print a party at all. The file holds what a source
said.

---

## 5a. Measured on 9-10 September, and what it changed

The bench (`review.py`) was showing `proceedings.csv`'s `predicted_offset` --
the SCHEDULE, meeting time minus stream start -- and not the time the page
prints. Somebody timed HB1118 at 58:06, was shown 5:39, and correctly marked
it wrong. Nine judgments were entered against a number no reader has ever
seen. The bench now reads the built pages. Those nine keep their stopwatch
readings, which are good; `review.py --report` quarantines their verdicts.

`probe_alignment.py --truth` now scores against `ground_truth.csv` AND
`review/checked.jsonl` together -- and the bench keeps growing, so the count
in this sentence is the one number here most certain to be stale: 49 marks
across 21 recordings by the afternoon of the 10th, against 35 across 7. `--no-bench` reproduces the old set exactly. Every score is split by
which hand-made file it came from, because the ruler grows every time somebody
sits at the bench and a median that moved because the set got harder is not a
median that moved because the method got worse.

`--site` had been broken since inlining and nobody knew. `census`, `coverage`
and `site_estimates` all globbed `site/bills/<year>/<ID>.json`, which now holds
the 98 records too large to inline instead of all 33,683. It reported 519
stations and called 96% of the docket absent. Nothing was absent. `site_read.py`
is the one reader of the record-in-a-page convention now.

With that fixed, the site's own claims got measured for the first time:

    WHAT THE SITE CURRENTLY SAYS  (36 of 43 marked proceedings)
      median off by 0m 32s, worst 88m 08s
      26 say the boundary was STATED by the chair -- 0m 04s at the median.

And the ENDS, which nothing had ever scored. Split by where each came from:

    the chair closed it        9 scored, median 0m 03s, 9/9 within a minute
    last mention of the bill  10 scored, median 0m 58s, 7/10
    next boundary              7 scored, median 29m 06s, 1/7  -- both ways

An end taken from the next boundary inherits every error in the placement of
the item after it: HB84's hearing published as 101 seconds against the 29
minutes it ran, SB659's stretched 94 minutes past where it finished. Those are
no longer published -- 1,586 stations lose a span, keep their start, and read
as "from 1:19:26" as they already did where there was no end at all. Worst end
error 93m 48s -> 12m 05s. `end_from` now travels with each station and
`end_stated` means the close was spoken rather than merely present.

**Captions were done for the purpose they served -- for one afternoon.**
On the morning of the 10th, 910 of the 915 recordings carrying a scheduled
bill had captions, and this paragraph said more fetching would not help. By
that evening `proceedings.csv` held seven terms and 1,823 bill-carrying
recordings, 370 of them uncaptioned, and the caption fetch was needed again.
The claim was true of the table it was measured on and false of the table
that replaced it the same day. Kept, corrected, because it is the cleanest
example on this site of a number outliving its premise.

## 6. Known bugs

- ~~**Nine recordings published an hour early.**~~ *Closed late on the 10th.*
  Their YouTube caption track starts an hour into the recording, so the
  chair's stated boundary and the clustering beside it were both an hour
  early -- 74 starts, 55 drawn as stated. The bench's mark on HB1130 was
  3,622 seconds out. `caption_span.py` compares where the captions stop with
  the duration YouTube published, and `build_site_v2` withholds both sources
  past fifty minutes short; the page falls back to the schedule. What is
  still open: the shift looks like exactly 3,600 seconds on every recording
  measured, and moving those times rather than withholding them would put
  74 starts back -- but that is a new way of making a timestamp and wants a
  few of the nine timed at the bench first.
- ~~**Calendar headers split in the wrong place.**~~ *Closed late on the
  10th*: a committee name with a comma of its own is kept whole (22,454
  rows), and a bill's untimed line is no longer read as a committee (4,841).
  What is still open, and measured: **2021's headers print with no room**
  ("CRIMINAL JUSTICE AND PUBLIC SAFETY") and are not read at all, so its 383
  rows that had only a misread bill number for a committee now have none and
  are not produced; the Senate prints many standing commissions the same way,
  and their meetings inherit the committee above. A lookup against names
  printed in full elsewhere was tried and moves 622 rows between real
  committees -- Finance prints budget hearings under agency sub-headings that
  are also committee names -- so it is not a fix yet. And where the two
  columns slip, the times after the slip belong one line up: the docket puts
  HB 1540 of 2018 at 1:00 and HB 1240 at 1:30, and the parser still gives
  HB 1240 1:00.
- ~~**Veto coverage.**~~ *Closed on the 11th, and the sentence here was
  wrong.* It said every one of 175 messages was correctly cited; 108 of them
  (all of 2013-2022) cited a calendar of 2023 or 2024, and the live site
  carries them until the next publish. The address now comes from the
  drain's own queue for the very file a message was read from, and
  `quotable()` refuses a citation from another year: 176 messages, none
  citing another year.
- ~~**Three readers of files that no longer exist.**~~ *Closed on the 11th.*
  Since records moved inside the pages on the 9th, the committee pages
  printed no time for 9,672 proceedings the bill pages time, 5,436 bill
  pages linked a feed nobody wrote, and preflight's `_one_start` and veto
  checks read the dead path and passed. All read the pages through
  `site_read` now.
- ~~**The archived-term note.**~~ *Closed on the 11th*: it told 15,389 bills
  of 1999-2016 their votes were not fetched, beside a Votes tab.
- ~~**The bulk download's start time.**~~ *Closed on the 11th*:
  `/data/proceedings.csv` exported the schedule as `start_seconds`.
- ~~**Amendment text**~~ *Closed on the 11th*: it carried the next
  amendment's heading at its end (97%) and a running page header inside
  (52%), on the live site's current term.
- ~~**Committee report citations.**~~ *Closed on the 11th*: all 7,376 of
  2013-2022 linked a 2023 or 2024 calendar and printed its date; every
  report of 1997-2024 now links its own year's calendar, from the queue.
- ~~**Roll calls' "not voting".**~~ *Closed on the 11th*: 2,483 House votes
  of 1999-2013 showed more members than the House has; counted from the
  ballots now.
- ~~**2025's bills had no committee and no subject.**~~ *Closed on the 11th*,
  from the database's Legislation view, which equals LSRs.txt on every bill
  both carry.
- ~~**No 404 page.**~~ *Closed on the 11th.*
- ~~**The home page's status note says the general election is 2 November.**~~
  *Closed on the 11th*: Tuesday 3 November, and the primary in the past
  tense. `status/status.txt` is still written by hand.
- ~~**`publish` never ran its live check.**~~ *Closed on the 11th.* npx is
  `npx.cmd`, and a batch file that runs another without `CALL` never gets
  control back, so every publish since the gate was added ended at
  wrangler's "Deployment complete!" and `check_live --gate` never ran. The
  12:44 publish's log stopped one line early, which is how it showed. Run by
  hand afterwards, the gate said the deploy landed. `preflight` now fails a
  bare `npx` in `publish.bat`.

## 6a. Filled from disk on the 11th, no request made

Committee reports and their reasoning for **every term 1997-2026** (from
2023-2026 alone), each vote checked against the docket at 96.9-99.8%;
veto messages back to **1997-1998** under the older headings (261, from
176); amendment texts **2011-2024** (4,577, from 663); sign-in counts for
**2024's** hearings (963 bills); the current term's **2025 committees
and subjects** (847 bills); and **the chapter each law became, for all
nineteen terms** (11,819 bills, from 1,273), read from the docket's
signature line and checked against the enrolled text on disk (46 of 46)
and the status page's field (1,268 of 1,270, the two being the docket's
typing). 14 are withheld where the docket gives one number to two bills;
the enrolled text, which the lane is fetching, settles each. The commits
carry the measurements.
- **Marker coverage.** The denominator tripled on the 10th when four more
  terms of hearings landed, most without recordings. Of 29,827 published
  stations, 8,388 carry a start. On the recorded ones the phrases are the
  lever, and on 2021-2024 so are captions, which are still arriving.
- ~~**`proceedings.csv` is one term.**~~ *Seven, since the 10th.* What is
  left is the terms whose dockets have not been fetched, and 1989-2014, for
  which the calendars are the only source: 61,767 bill-days parsed from PDFs
  already on disk, never merged. Still an architecture decision.
- ~~**`data/bills.json` had 1,485 hearing dates from the wrong term.**~~
  *Diagnosed and closed on the 10th, and re-fetching was NOT the fix.* Asked
  for session year 2021 or 2022, the legacy search returns the right bills and
  fills the date of "Next/Last Hearing" from the 2025-2026 record with the
  same legislationID -- an id that restarts each term. 1,481 of the 1,485
  match the current session's hearing to the minute against the General
  Court's own database dump; none disagree; no other term does it. The 93
  dates that were inside the term are conference-committee meetings, not
  hearings, so the whole field is dropped for that term and its hearings come
  from its docket. Two findings fell out of the measurement: **1989-1998 have
  no hearing dates at all** (all 8,524 bills read "Time not specified", and
  were counted as hearings until now), and conference meetings sit in this
  field for every archived term -- 79 in 2017-2018, 78 in 2023-2024 -- which
  is not fixed, because the date alone cannot tell them apart.
- **`end_stated` was not what it said** until 9 September, and any number
  recorded against it before then counted a next-boundary guess as a chair's
  spoken close.
- **`check_civics_links.py` has never been run.** The civics section's
  outbound source URLs are unverified.

## 7. Before the next publish

1. Run `check_civics_links.py`.
2. The proposal's own instruction that somebody who knows the building reads
   the civics pages before they ship.
3. ~~An accessibility pass at 360, 768 and 1440.~~ *A first one on the
   11th*, read from the DOM in the browser at each width rather than by
   eye: nothing scrolls sideways; 460 pages opened with the wrong hidden
   heading, the home search box was 21px tall on a phone, and the sponsor
   filter had no label -- all fixed (9f4e80e). Not done: a pass with a
   screen reader, and colour contrast beyond the Nay/Failed fix. Left as
   found: bill pages jump from the hidden `<h1>` to `<h3>`, and the civics
   pages' "All topics" link is 22px tall.
4. `probe_alignment.py --truth` if anything about timestamps changed — the
   rule in `CLAUDE.md`. Last run on the 10th: candidate median 0m 01s to
   0m 02s depending on how many bench marks had landed, worst published end
   12m 05s (was 93m 48s). `--no-bench` for a number comparable with anything
   recorded before 9 September.
