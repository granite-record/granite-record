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

Published 9 September and four times on the 10th. **76 preflight checks,
`check_site` ready, 49,304 files — 49% of the 100,000 Cloudflare Pages
allows.** MIT-licensed, with a README, since the 10th.

| | |
|---|---|
| Bills | **33,683 across 19 terms**, 1989 to 2026, each with its own page |
| Legislators | 406 sitting, **2,192 who have served** |
| Committees | 53 |
| Data | **seven CSV tables at `/data`**, 524,850 rows, a manifest, rebuilt every run |
| Towns | **320 town-and-ward pages** — everyone who represents you, with contact |
| Civics | 11 topics at `/learn/` |
| Feeds | per bill, committee, topic and hearing |
| Veto messages | 175, each cited to the calendar it was printed in |
| Hearings parsed from calendars | **61,429 bill-days, 1997–2026** |
| The archive on disk | 28 database views / 3.1M rows; House calendars and journals 100% |

## 2. Running

- **Docket**: 2017-2018 and 2019-2020 are done. **2021-2022 resumed on the
  10th at 588 of 1,752** -- about five and a half hours -- once the hearing
  dates were traced to the General Court's own server rather than to anything
  here. The 588 pages already on disk were checked first and are the right
  term: the session year is an explicit request parameter, 5 of 5 sampled
  pages carry the 2021-2022 title, and 4,718 of 4,720 action dates fall inside
  the term. 2016 and the Senate calendars wait behind it.
- **The 380-page sample of `gc.nh.gov/legislation/<year>/<BILL>.html` is
  done**: 297 pages saved, the parser read against them in three passes, and
  every bill asked for under 1996, 2016 and 2022 onward answered 404. The
  **every bill of every term from 1989 to 2026 now has an address** --
  27,171 by the static path, 6,512 by `billText.aspx`, none unreachable,
  against 2,103 unreachable on the morning of the 10th. Six addresses opened
  by hand in a browser settled it: 2016 and 2022-2026 have no static
  directory and are served by the application; 2022, 2025 and 2026 take the
  id `data/bills.json` already stores while 2023 and 2024 want the session
  year appended to it; and 1996 is served at `.htm`, padded and upper-case
  like every other year, the only address that fails being the one the
  archive itself publishes. The full run waits on the docket, and on nothing
  else.
- **Captions**, no longer throttled: about 60 a cycle, ~2,400 folders.

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

- **Veto coverage.** 175 messages publish and every one is correctly cited,
  but only 67 were newly extracted on the last run against 124 before, because
  the wrong-citation fallback was removed. `calendars.json` covers 976 of
  2,564 calendars; a calendar with no known address cannot be cited and so is
  not quoted. Rebuilding that index recovers them.
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
3. An accessibility pass at 360, 768 and 1440.
4. `probe_alignment.py --truth` if anything about timestamps changed — the
   rule in `CLAUDE.md`. Last run on the 10th: candidate median 0m 01s to
   0m 02s depending on how many bench marks had landed, worst published end
   12m 05s (was 93m 48s). `--no-bench` for a number comparable with anything
   recorded before 9 September.
