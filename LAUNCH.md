# Granite Record — what is done, what is not, and what to do first

Rewritten 9 September 2026, in the evening, after the site went live, and
brought current on the 10th. Every number here was measured when it was typed,
and by the next morning several were wrong -- which is the case for reading
`STATE.md`, which is generated, for any count that matters.

The previous version listed items 6, 7 and 8 twice — once struck through and
once not — which is what happens when a working list is updated in pieces. It
is renumbered here in one pass.

---

## 0. The order to launch, agreed 13 September (evening)

**Decided by the person that evening.**

- **The interface is this session's.** The visuals session was disconnected by
  a reinstall of the app, so tab navigation, the theme control, branding and
  the homepage come here.
- **A member who changed chamber keeps both bodies' history** on their page.
  Done the same night for twenty sitting members (b9b7079, §6c): joined on
  name, party, ground and time together, never the name alone, and a pair
  short of any of them is listed for a person rather than joined.
- **The public repository carries no personal email, no home IP address and no
  keys**, by whatever method. Scoped the same evening by searching all 369
  commits: the personal email is the author of the first commit only; the IP
  is in four `LAUNCH.md` commits of the 12th and 13th; no API key shape
  appears anywhere in history. So history is rewritten before anything is
  pushed, and every commit hash changes -- the ones quoted in this file get
  remapped in the same pass.
- **The logo is the Old Man of the Mountain mark in `brand/`**, from clipart
  the person bought the rights to. Temporary, and good to use.
- **The theme control:** automatic from the reader's system by default; the
  button shows light or dark and swaps to the other; the choice is
  remembered; no Auto state.
- **Bill text goes as far as it can before launch**, and launch waits a few
  days for polish once the blockers are done.

**The order**, each phase unblocking the next:

0. *Today.* Lane restarted 20:47. Morning triage scheduled for 8:07, first run
   waiting on its tool approvals. `_chain` registered and green (0fd0611). The
   day's files as a daily lane step (e820318), queued once the lane restarts
   on that code.
1. *The data, before pages show it and search engines index it.* Done on the
   13th: the second-referral install (1,946 rows take the second committee
   and 877 a changed recording match; the median held at 0m 01s); committee
   name variants into one committee (1,119 rows of 1989-1998; distinct names
   House 202 to 148, Senate 117 to 85); chamber changers' two histories (20
   members). Left: the Learn pages' counts filled from the data, and a
   member's Sponsored tabs, which miss bills the bill pages credit them with
   (§6c).
2. *Features.* Topics for the archived terms, where 37-64% of each term's bills
   are "Miscellaneous", scored at the bench; search that finds what was meant,
   measured on a set of real queries; follow (committee pages name their
   feeds, a Follow control, the email backend written up); archived bill text
   on its pages; the schedule service and new calendars daily, once
   `fetch_schedule.py` meets the fetch standard.
3. *The interface.* The theme control as above; tabs and mobile; the homepage
   and status banner. Seen in the screenshots of the 14th: at 768px a member's
   Votes table gives the date 9% of the width, and "9/13/2018" runs into the
   bill number beside it, on every member's page.
4. *Launch prep.* The Learn read-through with the person; the About and Data
   pages; the history rewrite and the public repository; the SEO last mile and
   the sitemap; screenshots at 360, 768 and 1440, a full build, publish,
   `check_live`.

Then polish days, visuals and backend. After launch: email follows,
automation off the PC, the 1999-2014 calendar hearings (spec C3-C7), sponsors
for 1989-2022.

## 0a. A Learn page of the record's own numbers (asked 13 September)

"Interesting data for the political science nerds": statistics the site can
compute from what it holds, as a Learn page. The person's list, each over the
last twenty years (2007-2026, ten terms) unless it says otherwise:

- the share of bills vetoed, by year;
- the share of bills that die, and where -- the first chamber, the second, a
  committee of conference;
- constitutional amendments (CACRs) since 1989, and the closest any came to
  passing;
- the share of roll call, division and voice votes, by year;
- the share of bills passed or killed unanimously on the consent calendar;
- bills that passed as introduced against those amended, and a chart of how
  many amendments a bill takes before it passes;
- each committee's passage rate for the last completed term (2025-2026 now).

**Where it fits:** after the Learn counts come from the data (phase 1), which
builds the same machinery -- numbers computed at build time from the record,
never typed into prose -- and in the same Learn standard: charts as inline SVG
with the table beside them, the method stated under every number.

**Decided by the person the same evening:**
- **Vetoes** are measured against the bills that reached the governor, not
  every bill, over the last twenty years -- with how many of those vetoes were
  sustained and how many overridden.
- **A committee's number** is the share of its referred bills that passed on
  the consent calendar, so the page shows which committees are most often
  unanimous and which most divided. The consent calendar's own rule -- what a
  committee vote has to be for a report to go there -- is read from the House
  rules on disk and stated on the page, not assumed; and the marking in the
  older dockets is measured term by term before a twenty-year line is drawn
  through it.
- **Constitutional amendments:** the few that reached the voters are listed,
  each with its result as the Secretary of State certified it and a citation
  to that page. The results are not in this record, so they are read from the
  Secretary of State by hand and kept with their sources, as officials.json is.
- **The closest votes** are the few closest roll calls on bills of the most
  recent term.
- **The most sign-ins at a hearing** go in as counts only (testimony stays
  aggregate), and only after checking that the list is not dominated by the
  most polarizing bills -- the person asked for that check before it is
  published, and its result goes to them first.

**Proposed besides** (aggregate only, never a ranking of people):
- the median time from introduction to signature, and the fastest bill to law;
- laws that took effect without the governor's signature, by term;
- the busiest single days on the floor and in committee;
- the share of bills sent to interim study, and how few return.

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
| Legislators | 406 sitting, **2,192 with a recorded roll-call vote, 1999–2026** (not "who have served": the site's bills go back to 1989 and the ballots do not) |
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
- ~~**Eleven vetoed bills read "Veto overridden, became law".**~~ *Closed on
  the 11th* (d376ab6). One chamber overrode, the other sustained, and the
  status-field table tested "overridden" first; the docket reader already
  had it right. 1989-2012, each confirmed from its docket; found because
  none had a chapter.
- ~~**Archived statuses this site made up.**~~ *Closed on the 11th*
  (5e8bd26, 5a12efd). 495 bills of closed terms read "In committee" or "In
  progress" -- `classify()`'s last resort -- over fields saying REPORT
  FILED, CONFERENCE COMMITTEE or CONFERENCE REPORT ADOPTED, which they now
  read; HB 1075 of 1998, signed, read "In committee"; fifteen closed-term
  vetoes read "awaiting an override vote", thirteen of them with a docket
  line saying it failed. The signature and failed-override lines come from
  `extract_chapters.py` for the twelve terms whose dockets are not narrated.
  Each change was measured on every bill before and after: 496, then 38,
  exactly those. Also one name each now for "Died on the table" and
  "Referred for interim study", which the facet listed twice.
- ~~**About 9,000 archived laws said "No recorded action yet".**~~ *A
  regression made and closed on the 11th*, live from 14:10 to 15:01. The
  signature line that settles an unnarrated bill also sent its status box
  to `next_step()`, which reads a narrated history and, finding none, says
  that. The before/after diff behind the change compared kind, status and
  rail and not that line; preflight now reads it (d35ce77). The lesson for
  any status change: diff every field the page prints, not the ones the
  change was meant to move.
- **`fetch_senate_calendars.py` finds nothing for 2007 and earlier. Open, and
  deliberately not fixed.** It filters the index's document list with `str(year)
  in label` (`:126`), and the older editions' labels do not name their year:
  2007 is offered, and 61 of its calendars exist, and it reports "0 calendars
  listed" and exits 1. Queued in the lane on the 12th it stopped the lane at
  13:29 with 102 steps behind it, and nothing ran until the evening. The years
  it was for, 1998-2008, are drained from `archive/queue.csv` instead, where
  all 664 names have sat since discovery on the 9th; the script is still right
  for 2008 onward, whose labels carry the year. The proving step did its job
  -- five requests' worth of budget, and it stopped the lane before twelve
  more steps failed the same way. What cost the afternoon is that a stopped
  lane says so only in `logs/gc_lane.log`, and nobody was reading it. A lane
  that stops needs to tell somebody.
- ~~**`fetch_calendar_archive.py` could not run in the lane.**~~ *Closed on the
  12th.* It kept `archive/.lock` by hand: it exited when the lock was under an
  hour old -- the lane touches its lock every minute -- and unlinked the lock
  unconditionally when it finished, so under the lane it would have stopped the
  queue at once, and had it run it would have deleted the lane's lock. It also
  needed two 403s to stop, missed a reset at connect time, and would have saved
  the firewall's block page as a PDF. It takes the lock through `refusal.hold()`
  and reads every answer through `refusal.classify()` now, and preflight drives
  it through all of those on fake answers.
- **A refusal is on file from 21:36 on the 12th, and it is probably 44
  documents rather than the address. Open, and a person's decision.** The first
  proving run asked for 2008's `09B.pdf` -- chosen *because* it had answered 403
  on the 9th -- and it answered 403 again on the first request. The drain did
  what it should: one refusal, recorded, status 2, lane stopped. The choice was
  the mistake: a 403 on a document already known to 403 cannot tell the address
  from the document, and it costs a day of every fetch.

  The record points at the documents. On the 9th the drain fetched 2008's `11A`,
  `11`, `10B`, `10A`, `10` and `1.pdf` fifteen seconds apart, and the very next
  name, `09B`, was refused, then `09A`. **All 998 Senate calendars ever fetched
  have names that do not start with a zero; all 44 that do are unfetched** --
  2008: 14, 2002: 10, 2001: 9, 2000: 11. And the lane's bill-text runs were
  answered all day on the 12th. That is a reading, not a test.

  So the 44 are `withheld` in `archive/queue.csv` -- not gone, and the drain
  asks only for `wanted` -- and the proving run in the queue is now the first
  never-tried name of the years wanted, 2007's `SC 45.pdf`. (`archive/` is not
  in git; the queue file carries the reason on each row.) Three addresses
  settle it in a browser before anything is cleared:

  - the refused one, expected to fail:
    https://gc.nh.gov/senate/calendars_journals/viewer.aspx?fileName=Calendars%5C2008%5C09B.pdf
  - one this project already holds, expected to load:
    https://gc.nh.gov/senate/calendars_journals/viewer.aspx?fileName=Calendars%5C2008%5C9.pdf
  - the next proving run's first document, the real question:
    https://gc.nh.gov/senate/calendars_journals/viewer.aspx?fileName=Calendars%5C2007%5CSC%2045.pdf

  If the second loads and the first does not, the refusal was the document, and
  `python3 refusal.py --clear` then the lane is safe. If the third fails too,
  the pre-2008 Senate calendars are not served at these names, and the Senate
  block should come out of the queue so bill text can start.

  **Update, 13 September about 00:30: it is the address, not only the
  documents.** The person allowed a tested fetch (bill text) overnight, through
  the procedure. The procedure's first step, `netcheck.py`, found every HTTP/1.1
  request **closed without an answer** -- our User-Agent, a full browser header
  set, a raw socket, and the other hostname -- where on the 11th all of those
  were answered. HTTP/1.0 got the firewall's 403 block page, as it always has;
  plain http got its 301. That is the block's signature, so the refusal stays,
  nothing was cleared, and the lane was not started. (netcheck was run twice,
  16 requests, the second only to read the top of its own output -- once would
  have done.) Bill text 2024 and 2023 were fetched cleanly until 12:59 on the
  12th; when the block began between then and 21:36 is not known.

  ~~**A lead, not a finding:** the block page names the client address, and
  ProtonVPN was running on this machine at 00:13. If that address is a VPN
  exit, the firewall may be refusing the VPN's shared address rather than
  anything this project sent.~~ **Closed on the 13th, by the person: the VPN
  was not connected on the 12th** (it was causing wifi trouble), and with the
  VPN connected on the 13th this machine leaves from a different address than
  the one the block page named. So the refused address is this machine's own
  home connection. (The address itself was written here on the 12th and has
  been taken out: this file is in a repository headed for public release, and
  a person's home IP address does not belong in it. It remains in git history
  until that history is rewritten or the public repository starts fresh.)

  **Settled by the person on the 13th: fetches go through the VPN.** The home
  address was blocked early in the project by a faulty fetch command that ran
  too fast and asked for incorrect addresses. The Clerk who oversees the
  General Court's staff has approved the project; IT has not yet lifted that
  leftover block, which the person is pursuing. Until it is lifted, every fetch
  leaves through the VPN, one at a time, at the proven pace, under the refusal
  procedure. (For most of the 13th this file said the opposite, on the
  assistant's reading before the person explained; that reading is withdrawn.)
  A 403 while the VPN is disconnected is the old home-address block, not news --
  but it still stops the run. Check the VPN is up (https://1.1.1.1/cdn-cgi/trace
  shows the outgoing address) before netcheck and a restart.

  **For a person, in a browser on this machine:** https://gc.nh.gov/ -- if it
  loads there while the table above says refused, the block is on this
  program's requests rather than the whole address, and netcheck's docstring
  says what to compare. If it does not load, it is the address, and the wait
  is days, as the first two blocks were.

## 6c. Member histories, verified on the 12th

**What each legislator's page publishes is right, ballot for ballot.** Every
sitting member's votes (406 pages, 647,285 ballots) were rebuilt a second way
-- PersonID to employee number from the database's roster, then every ballot
cast under that number in the database's own RollCallHistory -- and compared
with what the page carries. All 406 identical. The page's route (the General
Court's per-year export, whose field 4 is a PersonID they joined in) and the
database's agree on every ballot.

**But fifteen pages show only part of a career, and it is not a bug in the
join: a member who changes chamber gets a new employee number and a new
PersonID.** No page's votes span two chambers. Checked against three sources
that do not depend on names -- years and chamber from the ballots, party,
county and district from `member_party.json`, and the General Court's own
`byAnyMember` label -- twelve are plainly one person moving from the House to
the Senate (same name, party and county, consecutive service, no overlap):
Rosenwald (1,399 votes on her page of 4,218), Gray, Lang, Fenton, K. Murphy,
Pearl, Abbas, Altschiller, Rochefort, McConkey (208 of 3,897), McGough and
V. Sullivan. Gary Daniels is the same shape the other way: House, the Senate
for 2015-2022, the House again; his page has the House years only. Whether a
member's page should carry the earlier chamber's votes is a decision about
the page, not yet made.

**`careers.json` has a wrong merge, and it is the kind its rule invites.** It
joins employee numbers on first and last name where service does not overlap.
Rep. Patrick Long of Hillsborough 23 (376696, 2007-2024) was joined to a
different, newer Rep. Patrick Long of Hillsborough 26 (409256, from 2025) --
two House numbers, consecutive, a different district -- while the continuation
that looks real, **Sen. Pat Long** of District 20 (218767, from 2025, a
Manchester Democrat like 376696), was missed because the roster spells him
"Pat". That is a reading of the files, not a confirmation. **Mark Pearson**
(a Democrat for Rockingham 4 in 2007-08, a Republican for Rockingham 34 from
2017) cannot be told apart from this disk at all. Nothing on the site reads
`careers.json` yet, so no page is wrong today; anything built on it should
join on continuity of party and county as well as name, and send the doubtful
ones to the bench.

**Joined on the 13th (b9b7079).** The person decided that a member's page
keeps every chamber they sat in. `member_links.py` joins an earlier number to
a sitting member only when all of these hold: it voted in the other chamber
only; the same surname, and the same first name or a short form of it; the
two never sat at once; the same party on every vote; the same ground on
today's map (a House seat's county among the senator's towns, a Senate
district among the representative's); and no other number fits. Run over
every number it joins **twenty** and leaves nothing doubtful: the thirteen
above, and Sen. Pat Long (to the Hillsborough 23 number -- the other Rep.
Patrick Long is joined to nothing), Tara Reardon, David Watters, Bill Gannon,
Kevin Avard, Regina Birdsell and Sharon Carson. Mutated copies of real cases
were all refused, and the 43 surname matches the first-name rule turned away
are different people, five of whom would have passed on party and county
alone. Rosenwald's page carries 4,218 votes now and McConkey's 3,897 -- the
totals the database route reached on the 12th. The page says "Votes on
record: House 2005-2018 · Senate 2019-2026" under the seat. Mark Pearson is
untouched: two House numbers are two people to this rule.

Sponsorships are not joined: `sponsors.json` holds 2023-2026 only.

**Found the same night, not fixed yet: a member's Sponsored tabs miss most of
the bills the bill pages credit them with.** `bill_sponsor_list` resolves a
sponsor to the roster by id, then by name, and so links the right member's
page -- but files the bill under the sponsor record's own id, and a member's
file lists only what is filed under the roster's. Every 2023-2024 record
carries an employee number or no id (8,890 of 8,890), and so do the 4,569
records of 2025-2026 that came from the bill-status path. Measured on the
built site: **349 of the 406 pages list fewer bills than the bill pages credit
them with, 11,855 in all**, every 2023-2024 sponsorship among them -- Sen.
David Watters's page lists 177 of 681. Nothing is listed that no record
credits, no bill names one member twice, and no record resolved by name lands
on a member who was not sitting in that chamber that term (the Patrick Long
shape). That last is measured, not guarded. The fix is to file each bill under
the member its page links, with that condition built in, and the joined
numbers counting as the member's.

## 6d. The civics pages' facts, measured on the 12th

Every checkable claim in `civics.py` was measured against the built site.
**Right, exactly:** HB 1002 of 2024 -- the hearing of 17 January, two
executive sessions, 193 to 179, and the split (62 Republicans for and 125
against, 128 Democrats for and 53 against); HB 1215's committee of conference
and six recorded proceedings; HB 66's two roll calls (its other two tallies
are a division and a voice vote); HB 349's override failing 145 to 206; HB
2026 overridden; HB 649 carried over and signed; 649 laws in 2025-2026 as 632
signed, 10 unsigned and 7 over a veto.

**Stale, all for one reason -- a count typed into prose when the site was two
terms:**

| the page says | the record says now |
|---|---|
| "Across the 4,230 bills on this site, 865 have at least one recorded roll call and 3,365 have none" | 33,683 bills; 4,920 with one; 28,763 without |
| "Across the two terms on this site there are 68 vetoed bills. In 58 the override failed. In 9 it succeeded... One was still awaiting its override vote" | nineteen terms; 348 vetoed, 308 failed, 39 overridden, 1 unresolved. 2025-2026 alone: 44, 37 failed, 7 overridden. Veto Day was 19 August |
| "this site carries 67 of the 68" veto messages | 261 messages on disk, 1997 onward |
| 2025-2026: "855 were killed", "214 were sent for interim study" | 853 and 215 |
| HB 2 "with 44 recorded votes" | 45 roll calls |

Not checked: "1,068 reached both chambers", "86 went to a committee of
conference", and the district counts (203 districts, 41 floterial, 65 seats).

**The fix that lasts is not new numbers.** It is `build_civics.py` filling
these from the data at build time, the way the home page's counts are, so the
prose cannot drift again -- and it wants doing before the example bills are
replaced with older, settled ones, which the person asked for and which will
change most of these sentences anyway. Not edited: the civics pass is one
the person reads with us.

## 6a. Filled from disk on the 11th, no request made

Committee reports and their reasoning for **every term 1997-2026** (from
2023-2026 alone), each vote checked against the docket at 96.9-99.8%;
veto messages back to **1997-1998** under the older headings (261, from
176); amendment texts **2011-2024** (4,577, from 663); sign-in counts for
**2024's** hearings (963 bills); the current term's **2025 committees
and subjects** (847 bills); and **the chapter each law became, for all
nineteen terms** (11,846 bills, from 1,273), read from the docket's
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

## 6b. The archived histories, scanned twice on the 11th

The 1989–2016 histories went on 20,600 pages that had none, so they were
scanned for every defect this kind of sentence has actually had — the list
built from what the bench and a person reading had already caught — before and
after fixing. **526 findings, then 3.** Zero for unfilled markers, doubled
spaces, `..`, zero-padded chapters, wrong tense, duplicate sentences, dates
outside the term.

Six causes, each read out of the record rather than guessed:

- *"The committee reported: None."* is the clerk's own word. SB 466 of 2000
  has `Committee Report None`, and the next line has Sen. Trombly moving to
  suspend Rule #22A "to allow no committee recommendation before the body".
- *"referred to the &nbsp;committee"* on six pages: HB 246 of 1999 reads
  `Re-Referred to committee` and names none, because it went back to the one
  it came from. The sentence stops saying which.
- 41 sentences ended `Jr..` — the full stop added to a name that had one.
- Six impossible dates (`April 26, 2089`, an amendment rejected `June 16,
  2062`). `docket_vocab` had clamped mistyped years for 1989–2016 since the
  11th; the fetched dockets of 2017–2026 never reached it. Same rule now for
  every term: the day and month are the clerk's, the year is the session's.
  Effective dates are exempt — a law of 2014 really can take effect in 2020.
- 426 pages named a committee in shorthand. Thirteen expansions.

**A fourth witness for committee names, and worth knowing about.**
`referrals.py` expands an abbreviation only where a source spells the name
out, and `Pub Prot` (104 pages) and `Corr & Cj` (152) stood in its own
comments as unexpandable: all 584 referral strings searched for PROTECTION
turn up only Consumer Protection, a different committee. The resolution each
House adopts its rules by defines every standing committee in a sentence —
*"the Committee on Public Protection and Veterans Affairs to consider all
matters affecting public protection…"* — and two are on this disk as bill
text. `--check` now reads them. It is not circular: the pattern is the
resolution's grammar, so it returned 22 committees, most of which nothing
here had asked about, including Corrections and Criminal Justice.

Still abbreviated: `Pub Instit`, two referrals, two candidates on this disk
that are different committees.

**Two findings from the same pass, not fixed, both with the cause located.**

1. `segment_markers` reads a *plan* as a boundary. On 3 April 2023 the chair,
   an hour behind schedule and in the middle of another bill's hearing, said
   "we might start the hearing on 68 before the lunch break"; `OPEN_RE`'s bare
   `start\b` fired, putting SB 68 eleven minutes early. The real opener — "I'm
   going to open a public hearing on Senate Bill 68" — is in the same
   transcript at 2:14:36, two seconds from the bench's mark. A modal guard
   separates the two, and it is a timestamp change, so it needs its own score.
2. **25,499 of 30,588 committee report texts end without a full stop.** Not
   truncation, which is what it looks like: `fetch_committee_reports.py`
   cuts at the vote line with `.strip(" .;,")` and eats the sentence's own
   period. The source reads "…our NH National Guard.Vote 11-6."

## 7. Before the next publish

1. ~~Run `check_civics_links.py`.~~ *Half done on the 11th.* The five links
   off the General Court's server were opened in a browser (a script's HEAD
   gets 403 from every state host): the Governor's, the Council's and the
   agency list were nh.gov "Page Not Found" and now point where nh.gov's own
   pages do (8c9cb5c). The eleven on gc.nh.gov are unchecked, because that
   is the address the lane is fetching from; `python3 check_civics_links.py
   --list` prints them, for a browser or for the lane once it is idle.
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

---

## 8. The feedback batch of 11 September, evening

Eleven items from the person, recorded verbatim in substance so none is lost.
**[back]** is the data and functionality side; **[vis]** belongs to the
visuals/dark-mode session working in parallel; **[both]** needs one of each.
Nothing here is done unless it says so.

1. **[back] DONE (bulk data and the rebuild date; GitHub waits for a URL). The footer carries the power-user items.** Link and explain
   the bulk data downloads, say when the site was last updated, and eventually
   link the GitHub repository. `data.html` and `manifest.json` already exist
   and already describe every table; the footer does not mention them, so the
   only way to find them is to know they are there.

2. **[back] ALREADY DONE, and I nearly broke it.** A vote on an amendment should name which amendment. "Adopt
   Committee Amendment (2247h)" or "Adopt Floor Amendment (1234h)", not a bare
   "Adopt Amendment".

   *Measured before starting:* 420 amendment-adoption roll calls across all
   terms — 196 of them labelled only "Adopt Amendment", 180 "Adopt Floor
   Amendment", 44 "Adopt Committee Amendment". **The amendment number is in
   none of them:** 0 of 420 `question_raw` values carry one. So both halves of
   this — which kind of amendment, and its number — have to be joined from the
   docket's own amendment events by bill, chamber and date.

   *The join, measured against the 19,105 amendment events on 9,895 bills:*

   | | roll calls |
   |---|---|
   | exactly one amendment that bill, chamber and day | **213** |
   | several, but only one was decided by a roll call | **47** |
   | several, and the question's own wording picks one | **9** |
   | **resolvable** | **269 of 420 (64%)** |
   | several roll-call amendments the same day | 70 |
   | no amendment event that day, or none at all | 55 |
   | still ambiguous | 26 |

   So 269 votes can name their amendment with certainty and 151 cannot. The
   151 keep the bare label: `bill_amendments` already states the rule this
   follows — "Committee or floor is not a label this invents: it is the word
   the docket line used, and where the line says only 'Amendment' that is what
   the reader is told."

   **`vote_chronology` in `build_site_v2.py` has done this all along, and
   names 269 of the 420.** It pairs the day's roll calls with the docket's
   floor actions IN ORDER within a chamber and a day, and claims nothing when
   the counts disagree. `rc.amendment` is `None` in `rollcalls.json` — which
   is what I measured, and it is the wrong file — and filled in the built
   payload.

   A second joiner written on top of it named 82 more and had to be reverted
   the same night. On HB 675, `vote_chronology` named roll calls 35 and 37 and
   left 36 alone; the addition saw 36 as "the only unnamed amendment vote that
   day", found one candidate and gave it `2025-3013h` — which 35 already had.
   One amendment, two votes, and nothing on the page would have looked wrong.
   The 82 it added were exactly the cases the original declines *because* the
   pairing is unknowable.

   What is left is not a joiner. It is the 151 the docket cannot settle, and
   they should stay unnamed. `preflight` now guards the refusal rather than
   the naming.

3. **[back] DONE. "Division Vote" and "Voice Vote", capitalised.** `build_site_v2.py`
   has `VK = {"VV": ("voice vote", False), "DV": ("division vote", False)}`.
   Care is needed: the same words are used mid-sentence elsewhere ("decided on
   a voice vote"), where lower case is correct.

4. **[back] DONE. A roll call is labelled above the vote diagram** the way
   division and voice votes already are.

5. **[back] Close every gap in coverage, or know the remainder is
   unrecoverable.** Missing bills, unknown members, missing dockets, broken
   links. The standard the person set: a remaining gap should be a document
   genuinely absent from the official record, *not* a parsing error of ours.
   A census is running: every gap classified PARSING / NOT-FETCHED /
   UNRECOVERABLE.

6. **[back] DONE. Bill search: expanded rows stayed open across a term change.** The cause was `openCards`, `openTab`, `segSel` and `fullOpen` being keyed on the bare bill number, which is not unique across terms; `detail` was already safe because `dkey()` keys it on the year too. Cleared on both term-change paths, and not on the deep-link path, where opening the named bill is the point. Expand
   some bills, switch term, and the open state is applied to whatever bills now
   sit in those positions — so the wrong bill shows as open. Almost certainly
   open-state keyed on row position rather than on the bill.

7. **[both] The Learn tab.** Accurate, straightforward explanations of
   structure and function, with diagrams, examples and links. Specifically:
   double-check the language, replace the example bills with neutral ones from
   terms further back, and add diagrams that carry the concept visually. The
   site is static with no runtime, so diagrams are inline SVG.

8. **[vis] DONE (the label; the layout pass is still open). "Versions" is now "Bill Text" in the tab strip** — `app.js`
   renders the tab label and the "Full text" / "What changed" toggle.

9. **[vis] The version view needs a layout pass.** Full text and what-changed
   are right in principle and read as cramped and hard to parse.

10. **[both] The town page.** Reformat so elected officials are grouped by
    branch and paired, rather than listed flat **[vis]**; and find a source for
    polling location per district and for clerk information **[back]**.

11. **[back] Municipal elected officials** — selectboard, city council, mayor.
    No source on this disk today. Being researched: whether any statewide list
    exists or whether this is 234 municipalities by hand.

### 8a. What the coverage audit found (11 September, overnight)

Five read-only agents audited every source. The findings below are measured;
the adversarial pass that would have checked them died on a spend limit, so
the two that matter most were verified by hand instead and are marked so.

**THE BIGGEST RECOVERABLE GAP IS NOT A FETCH. It is a match.** *(verified by
hand)*

- **1,930 of the 4,296 captioned recordings have no row in
  `proceedings.csv`**, so `segment_markers.py` never opens them. Only 2,413
  recordings are referenced. Nearly half the captions on this disk are read by
  nothing.
- **554 of the 4,427 indexed videos fail `title_parsed`, and
  `build_manifest.py:135` drops every one of them** (`if r["title_parsed"] !=
  "yes": continue`). **536 of those 554 carry an exact livestream start time**,
  so the date is known for certain and is being thrown away. 532 of the 554
  are 2020-2022 — which is the whole reason those years look thin.

  The titles say why, and all three shapes are the parser's fault rather than
  the clerk's: `Ways and Means - Revenue Estimates (5/27/20 - morning
  session)` puts trailing text inside the parentheses; `Ways and Means:
  Revenue Estimates (6/1/20 - morning session)` adds a colon; `Children and
  Family Law Orientation Meeting 1/11/21` has no parentheses at all.

  **Half the fix does not need the title at all.** Where a video carries
  `actual_start_utc`, the date is that start's date, exactly -- a stream's
  start IS the day the sitting happened. That removes the parsing problem
  rather than solving it, and it is sound.

  **The other half is the committee, and it is harder than it looks.** A first
  attempt on the 12th was written and reverted the same hour. It took the
  committee as the longest prefix of the title matching a name the index had
  already parsed, which measured 411 of 554 resolved and 788 unmatched
  proceedings on those days -- and recovered only 126 when actually wired in,
  because:

  - `_load_one` reads ONE csv at a time, so the list of known committees is
    per file rather than across all twelve;
  - and `parsed_committee` is not a clean committee name. It holds
    `'Judiciary :'` and `'Ways and Mean : Work Session and Revenue Estimates'`,
    so a longest-first match picks the noise, and a committee like that will
    never match a proceeding.

  The right source for the committee list is the DOCKET's own committee names,
  which this project already has, rather than a list scraped out of the video
  titles. That is the next attempt. It touches the matching pipeline, so it
  needs `probe_alignment --truth` scored before and after, and a wrong
  committee would put the wrong recording against a proceeding -- which is
  worse than leaving the row dropped.

Other findings, not yet verified by hand:

- **664 Senate calendars (1998-2007)** have sat as "wanted" in
  `archive/queue.csv` since a 403 stopped the drain on 9 September. Not in the
  lane. They are the only source for Senate committee reports 2008-2024.
- **86,718 rows / 187 MB of dumped database views have no reader at all**:
  `NH_RSA`, `VHearings`, `Sponsors`, `StatStud*`, `DistrictPast`,
  `CandH_Reports`. `VHearings` is worth looking at first — hearings 1999-2014
  is an open question and the view is already on this disk.
- **`db/document_versions.json` is a declared `build_all` dependency with no
  generator anywhere in the repo.**
- Four `build_all` steps still re-query the SQL host for views already dumped.
- **`fetch_members`, `fetch_leadership`, `fetch_session` and
  `fetch_archive_text` have never run.** The last is superseded by
  `fetch_legislation` and should be marked so; `ARCHIVE_PLAN.md` is stale on
  that point.
- The calendar/journal citation index covers 12 of 30 years, though every PDF
  is on disk and needs no network.
- **Every one of the 34,481 built pages asks the reader's browser for Google
  Fonts**, and no document records a decision about it. Worth one, given this
  project's care about not leaking its readers to third parties.
- Neither YouTube channel has anything before **2020-05-14**, so 2017-2018 and
  all of 1989-2016 have no recordings and never will. That gap is
  UNRECOVERABLE and can be stated as such on the site.

### 8b. The unread database views, and the committee names (12 September)

**The 86,718 unread rows are not a hidden archive.** Each was opened:

- **`VHearings`** — 8,739 rows, **2024-2026 only**, and not one names a bill.
  It is the current hearing and study-committee schedule. It does **not** fill
  the 1999-2014 hearing gap, which was the reason for looking.
- **`CandH_Reports`** — 5,597 full HTML documents, "Hearing Report" and
  "Committee Report", **2025-2026 only**. The current term's reports, already
  read from the database by another path.
- **`StatStud*`, `DistrictPast`** — study committees and past districts, small.

**`NH_RSA` is the one worth having: the complete New Hampshire statute
corpus.** 29,785 sections, each with its title, chapter, section heading,
source note and full text, 107 MB, already on this disk and needing no
request. `build_site_v2.py` already finds RSA citations in committee reports
and bill titles (`RSA_CITE_T`) and links them away to the state's own site. A
reader who has to leave to find out what 91-A says usually does not come back
— and the text to keep them here has been sitting in `db/` since 8 September.

**A defect found on the way: `proceedings.csv` splits committees by
truncation.** 137 of its committee names are under twelve characters, and many
are the same committee cut at different lengths:

| | rows | | rows |
|---|---|---|---|
| `Judiciary` | 3,250 | `Jud` | 264 |
| `Education` | 2,824 | `Educ` | 265 |
| `Commerce` | 1,328 | `Commer`, `Commerc`, `Comm` | 12 |

with `Judici`, `Judicia`, `Judiciar`, `Educati`, `Educs`, `Healt`, `Healthm`,
`Wildflife` and `Enrivon` besides. A committee page, a facet count and any
join on this field are all split across the variants. Not yet fixed.

**The captioned-recording recovery now has a clean vocabulary.** The attempt
of the 12th failed because it matched titles against committee names scraped
out of the video index, which are noisy. Measured against three sources:

| vocabulary | of the 554 dropped rows, resolved |
|---|---|
| names scraped from `parsed_committee` | 126 |
| `proceedings.csv`'s committee column | 461, but 40 of them to the junk name `Comm` |
| **`data/committees.json`, the canonical 48** | **412, no junk** |

So: the date comes from `actual_start_utc`, which is exact, and the committee
from a longest-prefix match against the canonical list after an optional
"House"/"Senate". 412 of 554. The 142 that remain are mostly not committee
proceedings at all — "House Session 03/16/2022 (Entire Session)", "Speaker
Packard's Legislative Staff Week Thank You" — and should stay out.

It touches the matching pipeline, so it wants `probe_alignment --truth` scored
before and after, and a wrong committee puts the wrong recording against a
proceeding.

---

## 9. The night of 12-13 September

The person went to bed and asked for launch work that needs no oversight. **Nothing was published and no request went to the General
Court** -- netcheck at 00:30 found the address refusing (§6, the refusal
entry), so the one fetch allowed overnight did not start. Everything below is
committed on `master` except where it says otherwise, and is on the built
`site/` but not on graniterecord.org.

**Waiting on a person, in the order they unblock things:**

1. ~~**The refusal.**~~ **Cleared on the 13th at 15:26, and the lane is
   running.** With the VPN connected, netcheck found the address answering
   (every HTTP/1.1 request 200; HTTP/1.0 refused as always); the person cleared
   the refusal; the lane restarted. **The 2007 Senate proving run fetched 5 of
   5** -- so the pre-2008 Senate calendars are served at the names the queue
   holds, which was the question left open on the 12th. The Senate calendars
   back to 1998 follow, then bill text. The 44 zero-padded names stay
   `withheld`. Still open: the home address. On the evening of the 13th the
   person wrote to the General Court's IT staff -- what the project is, why
   the address was blocked, what now keeps its requests safe, and a request
   to lift the block -- scheduled to send on the morning of Monday 14
   September. Their answer decides whether fetches can leave the VPN.
2. **Published on the 13th, in the afternoon** (merge 6222d12, deployment
   27c1e2a2): the report box is live -- `/api/report` answers 405 to a GET, a
   well-formed report sent to the deployment's own pages.dev address was
   refused and stored nothing (production database: 0 rows before and after),
   and `check_live --gate` passed. Everything below this line of the 12th and
   13th went out with it. **Before the next publish that changes app.js or a
   stylesheet:** the zone's Browser Cache TTL overrides the site's
   `max-age=0` to 4 hours for .js and .css, and the pages no longer carry a
   version query, so returning readers could get new pages with an old
   script. The person sets Caching > Configuration > Browser Cache TTL to
   "Respect Existing Headers" (or the version query comes back).

   *What was merged:* **the report box, from branch `report-box-merge`
   (`D:\nh-merge`)** -- master merged in (only version stamps conflicted),
   then hardened on the 13th: the Function refuses any host outside
   `REPORT_ORIGINS` and any path but `/api/report` exactly, because the
   zone's rate rule sees neither `*.graniterecord.pages.dev` nor
   `/api/report/`, which the Pages router also delivers. Merging it into
   master and publishing is the person's decision.

   **Cloudflare, as of the 13th** (from the person, and checked where it could
   be): the zone is on **Pro**. The rate-limiting rule exists -- "URI Path
   equals /api/report", Block, active -- and on the evening of the 13th the
   person confirmed it reads 5 requests a minute per IP, answered 429 and
   blocked for an hour, with 0 requests over the limit in its first week. The
   live robots.txt was read the same evening and is exactly the site's own
   (every crawler allowed, the sitemap named): Cloudflare's "block training in
   robots.txt" and AI Labyrinth are off. Its AI bot policies carry three
   configurations that act at the edge on AI crawlers, not on search engines;
   whether assistants may read the site is the person's call and not a launch
   blocker. The two `report-probe` preview
   deployments (053c0b70, 737842cd) are deleted and answer 404. The Pages
   project holds no production variables the merge could lose (read with
   `wrangler pages download config`). The production database holds 0
   reports; the preview one holds 3 test reports from the proving run.
   contact@ routing is active. Super Bot Fight Mode is present -- if
   "Definitely automated" is ever set to Block, `check_live` in publish will
   be refused. The optional Bulk Redirect of `graniterecord.pages.dev` failed
   to save for want of `https://` on the target; the Function's host check
   makes it unnecessary.
3. **The nightly, on the same branch.** Fetches only when nothing else is
   asking (no refusal, no lane lock, no build running), deploys only with
   `--deploy` and only from `master` with a clean tree. Not yet scheduled --
   and on the 13th the person said their PC will not always be on and
   scheduled work should run in the cloud, so where it runs is being
   redesigned rather than put into Task Scheduler.
4. **`fetch_leadership.py` is ready to run -- five requests, once the refusal
   is cleared** (d2606dc). It now saves the Senate's leadership and About
   pages and the House Speaker's, Majority and Minority office pages, each an
   address the General Court's own navigation links, 20 s apart, and stops on
   the first refusal. `--parse` then reads them with no request. The House
   pages have never been read, so the first `--parse` will print their lines
   for a pattern to be written against. No consumer on the site yet.
5. **Email follow.** The design is the person's (12 September). Decided on the
   13th: **Resend** sends the mail (Cloudflare's own Email Service is in beta
   and its terms cover transactional mail only); nobody -- the person, a Claude
   session, a log -- sees who signed up or what they follow, and the only
   number exposed is the total count of sign-ups; and it runs on Cloudflare,
   not on the PC. Still open: Turnstile on the sign-up form (explained to the
   person, not yet agreed), what a follow does when its bill concludes, and
   whether "as soon as available" and "daily" differ when the record
   refreshes once a night. The About page's "no accounts, no email addresses"
   has to change before it ships.

**Done tonight:**

- **Every record page is reachable without JavaScript.** `/directory` and 21
  lists beneath it -- every bill of each of 19 terms, every sitting
  legislator, every town and ward -- 34,409 static links where there had been
  almost none (`build_indexes.py`, a `build_all` step). Bill, legislator and
  committee pages carry schema.org JSON-LD (`structured.py`): Legislation,
  Person with no email or phone, GovernmentOrganization, and breadcrumbs.
- **Feeds only for bills still moving**, per the person's rule: a concluded
  bill's page links no feed and none is written. 107 bill feeds, committee
  feeds keyed by code, stale ones pruned.
- **`publish.bat` refuses to deploy from any branch but `master`**, and names
  the branch on the deploy line, so a deploy can no longer land on a preview
  because of which branch git was on.
- **The data is the General Court's of 6 September**, from the archive copy,
  with a record-by-record diff before and after showing only 2026 changes.
  The Judiciary committee's 30 September executive session is on HB 293 and
  on the committee's page -- where it said "met", seventeen days early,
  until the tense was fixed for days still to come (5 committee pages).
- **Keyboard:** arrow keys on a tab strip keep focus; a page opens on its own
  first tab; the version picker is a group of pressed buttons rather than a
  tablist with no tabs; and focus survives the bill text arriving
  asynchronously.
- **The 1989-1998 hearing line's shorthand is read** (`referrals.py`, 13abc9f).
  A hearing of those years names its committee after FOR: in letters the
  referral line never uses -- "FOR: ED+A". Nine anchored expansions, each in
  the General Court's key and each proven on the same bill: the referral line
  of the same bill in the same chamber spells it out (ED&A 601 of 630 bills,
  M&CG 253 of 261). `PUBLIC WKS` is deliberately absent, because the key
  gives today's name, "Public Works and Highways", and the committee of 1990
  was "Public Works". Proceedings naming no committee the site has: **9,094
  -> 7,735**, more than planned because the five archive manifests were also
  stale from the 10th and missed the 11th's expansions.
- **Committees no longer listed go to the bottom of `/committees`**, under
  "Not on the General Court's list today", each with the years its record
  covers. Two facts, both required: not on the General Court's list, and
  every bill and sitting day before this term. "Disbanded" is not claimed --
  the records show when a committee stops appearing, not why. The roster
  table cannot help: its `sitting` flag is about the legislator, not the seat,
  so three special committees with no record and mostly sitting members stay
  under "No bills or sessions on record", which claims nothing.
- **A proceeding takes its own chamber's committee** (`docket_parser.py`).
  The referral timeline was keyed by bill alone, so a Senate referral joined
  the House's timeline: HB 115's House executive session of 1 April 2025 was
  filed under the Senate's "Education", which is H05 by name in the House,
  and that one row kept H05 Education out of the archived list. 48
  proceedings across six terms. Reading why 2015-2016 then lost 318 more
  found the larger defect under it: **that term's docket writes 1,255
  introductions with no date** ("Introduced and Referred to Public Works and
  Highways."), and none was read, so **2,918 of its proceedings had no
  committee; 9 do now** -- with "(in recess of 3/12/2015)" and "&" taken off
  the names, so they match the committee's page. Across the table: 53,814
  proceedings, 49,158 naming a committee (43,701 before tonight), 7,710 naming
  one the site has no code for, **5 of them from 2015 onward** -- the rest is
  1989-1998 spelling, below. The 2015-2016 manifest was also a day stale
  against its docket, which is why the table grew by 2,850 rows. H05
  Education is in the archived list now, 1,530 bills and 496 sitting days.
  Eight recordings change match: six clearly better
  (CACR 21 in Judiciary's room now matches Judiciary's recording), HB 1288
  loses one that came from a borrowed name, and HB 296's June 2022 work
  session loses a House Judiciary match that was probably right by accident
  -- its room is Judiciary's, and its House referral was Criminal Justice.
  None of the eight is hand-timed or on the bench.
- **An archived committee's own page says so** (29e6383): "Not on the
  General Court's list of committees today. Its bills and sitting days on
  this record run 1989 to 2024 ..." -- a reader from a search never sees the
  listing.
- **Legislator search descriptions** named the seat twice on all 406 pages
  ("(R - Rock 30) Rock 30."). Now the name, the places, then what the page
  holds (9911dfb).
- `README.md`'s counts from `STATE.md`, and "2,192 people who have served"
  corrected to what the number is. `CLAUDE.md` still says "who have served"
  in its first paragraph; it is the person's file.

**Found and not fixed:**

- A pre-existing expansion collapses a joint hearing -- "Joint Ed and a and
  Sen Pub Affs", one row of 1991-1992 -- into "Public Affairs", because
  `\bPUB AFFS\b` searches rather than anchors. One row; the fix is to anchor
  the pattern or skip strings that start "Joint".
- `H Commerce`, 759 hearings of 1989-1998, the clerk writing COMMERCE for a
  House committee renamed inside the decade. Left as written.
- **A second pass of the same proof took nine more** (`referrals.py`
  2026-09-10.7): EDUC, W&M, CRIM JUST, SCIENCE, ENV & AG(R) -- all current
  committees -- and INSUR, ENVIRON, PUB WKS, PUB INST, which are historic. 1,224
  hearing rows of 1989-1998 renamed, each in the chamber its proof came from.
  JUD and WILDLIFE are left because they mean different committees in the
  two chambers and `expand()` is not told the chamber; giving it the chamber
  is the next step for those two (269 and 232 rows). Proceedings naming a
  committee the site has no code for: 7,710 -> **7,035** (9,094 at the start
  of the night). Records moved only for 1989-2003 bills.
- **What is left unmatched is spelling, and it wants a canonical list per
  era before any of it is listed as a committee.** The Senate's insurance
  committee is `Insurance` (292), `Insur` (144) and `Insuranc` (12); there is
  `Jud`, `Educ`, `Environ`, `W and M`, and three spellings of `Dev Rec and
  Env`. The archived section lists only committees with a code for that
  reason. The historic committees with no code -- Constitutional and
  Statutory Revision, Public Works, Banks, Insurance, Public Protection and
  Veterans Affairs -- need the same per-bill proof as tonight's nine before
  they get a section.
- `ST-FED` (113 hearings) and `ST INST` (118) are not in the key and each
  committee changed its name inside those years. Left as written.
- **A proceeding after a second referral is still filed under the first
  committee -- measured, and proposed rather than done, because it moves
  recording matches.** The timeline reads introductions only, so "Referred to
  Finance 03/13/2025" is not on it, and a Finance executive session is named
  for the policy committee the bill left. **2,042 proceedings across six
  terms, 309 of them in 2025-2026**, nearly all a policy committee standing
  in for Finance or Ways and Means (2023-2024: Education 72, Health and Human
  Services 68, ED&A 52, Children and Family Law 43).

  The rooms say which is right, and they are a witness the parser does not
  use. Each committee's home room was taken from the proceedings nobody
  disputes; of the re-referred proceedings held in either committee's home
  room, **571 were in the later committee's and 4 in the first's** (current
  term, 2023-2024 and 2021-2022). The rest were in neither, mostly Finance's
  divisions in their own rooms.

  The change is small: read "Referred to X <date>" rows into the chamber's
  timeline beside the introductions. What it moves is not: for the recorded
  terms, a Finance session stops matching the policy committee's video of
  that day and becomes "divisions - pick manually", which is honest, and
  some matches change. So: scratch-build the manifests, list every changed
  match, run `probe_alignment --truth` before and after, and let a person
  look at the list first.

  **Done on the 13th, in the evening (00eafb8), on the person's choice of
  "probe, install if it holds".** Every term's manifest was built in scratch
  twice, with the code before and after; the before copies equalled the
  installed manifests (the 35 hand-marked times carried as H:MM:SS where a
  fresh build writes seconds -- the same moments). After: 1,899 manifest rows
  of 2015-2026 and 47 of 1989-1998 change committee, and **877 change their
  recording match** -- 596 had none and now have a candidate, 104 go to a
  different recording, 41 lose one (nearly all Finance sessions in Finance's
  own rooms, LOB 209, 210-211 and 212, now "pick manually"), 136 keep the
  recording with a new note or offset. `probe_alignment --truth` on each:
  **median 0m 01s before and after, with the bench and without it, worst
  unchanged**, and the same again on what was installed. The one row still
  worth a person's eye is SB 128's session of 15 November 2023 in LOB 206-208,
  Judiciary's room, which loses its House Judiciary recording.
