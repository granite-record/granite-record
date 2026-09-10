# Granite Record — what is done, what is not, and what to do first

Rewritten 9 September 2026, in the evening, after the site went live. Every
number here was measured, not remembered. Where this disagrees with
`ROADMAP.md`, `ARCHITECTURE.md` or `HANDOFF.md`, this is the newer answer.

The previous version listed items 6, 7 and 8 twice — once struck through and
once not — which is what happens when a working list is updated in pieces. It
is renumbered here in one pass.

---

## 1. Live

Published 9 September. **72 preflight checks, `check_site` ready, 39,821 files
across 411 MB — 40% of the 100,000 Cloudflare Pages allows.**

| | |
|---|---|
| Bills | **33,683 across 19 terms**, 1989 to 2026, each with its own page |
| Legislators | 406 sitting, **2,192 who have served** |
| Committees | 104 pages |
| Towns | **320 town-and-ward pages** — everyone who represents you, with contact |
| Civics | 11 topics at `/learn/` |
| Feeds | per bill, committee, topic and hearing |
| Veto messages | 175, each cited to the calendar it was printed in |
| Hearings parsed from calendars | **61,429 bill-days, 1997–2026** |
| The archive on disk | 28 database views / 3.1M rows; House calendars and journals 100% |

## 2. Running

- **Docket**, 2017-2018 then 2019-2020, 2021-2022 and a seeded 2015-2016.
  3,404 pages cached. Roughly 19 hours to go.
- **664 Senate calendars**, queued behind the docket, then their text.
- **Archived bill text**, behind those. ~63,000 requests, days.
- **Captions**, recovering after YouTube throttled this address on
  5 September: cycles of 48, 59, 59, 50.

`refusal.py` stops every fetch for 24 hours when the address says no, and
clearing it is a person's decision.

## 3. The bench

`python3 review.py` — local only, loopback address, nothing on the site. One
sample at a time: a verdict, a correction, a note, appended to
`review/checked.jsonl`, which is hand-made evidence and is protected the way
`ground_truth.csv` is.

| kind | pool |
|---|---|
| Bill hearing timings | 5,950 (243 stated by a chair, 5,707 inferred) |
| Plain-language histories | 4,198 |
| Hearings read from calendars | 97,158 |
| Governors' veto messages | 175 |
| Committee report reasoning | 4,274 |

A timings item embeds the recording, shows both printed times, and captures
the player's current position straight into the field — so a judgment is play,
pause, press, rather than read-off-and-retype.

**Nothing has been judged yet.** `ground_truth.csv` is still 35 proceedings,
and until the bench has been used, related bills and auto-assigned topics
cannot honestly be published.

---

## 4. What is left

### Small and visible

1. **Special-bill notes.** HB1 is the budget, HB2 the trailer bill, HB2026 the
   ten-year transportation plan. A reader cannot know that. Hand-written, a
   dozen of them.
2. **Dark mode**, favicon and logo, header and footer, and dropping the
   redundant status block on the bill page.

### Larger, and each unlocks something

3. **Wire the video match.** Proved on 2023-2024 with no network: 1,643 of
   1,648 recordings convert to the shape `build_manifest.py` reads, and
   **4,731 of 5,868 proceedings (81%) match a single recording** — 1,693 bills
   reaching video, no captions needed. What is left is the merge into
   `proceedings.csv`, which must not destroy the current term.
   `index_to_csv.py` is the converter.
4. **Roll calls on legislator pages are unreadable** — date, bill number,
   motion, vote, and no way to see what the bill was, how the vote came out,
   or how the member voted against their own party. Group by session day.
5. **Amendment diffing.** The data is already here and needs no fetching:
   `LegislationText`, 6,825 rows, every version of every current-term bill,
   with `DocumentVersion.SortOrder` to order them.
6. **Committee pages: upcoming hearings**, and a session day as a table —
   every bill heard, its status change, the report split, bill numbers linked.
7. **A member's whole career on their page.** `careers.json` exists: 2,211
   employee numbers resolved to **2,192 people**, 17 who served in both
   chambers and 289 who left and came back. Nothing on the site reads it yet,
   and it needs the archived roll calls built before it says much.
8. **Narrative prose into the HTML.** A bill page gives a crawler 70 words;
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
14. `build_site_v2.main` is still **449 lines**. Internal, and the reason a
    floor-marker miss went unnoticed.

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
`review/checked.jsonl` together: 43 marks across 15 recordings, against 35
across 7. `--no-bench` reproduces the old set exactly. Every score is split by
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

**Captions are done for the purpose they serve.** 910 of the 915 recordings
that carry a scheduled bill have captions; only 5 do not. The 353 further
captioned recordings carry no scheduled bill -- they are study commissions,
oversight bodies and interim committees, and `proceedings.csv` correctly has
no row for them. More captions will not raise marker coverage on the current
terms. Earlier terms will, once their calendars reach `proceedings.csv`, and
that is the unlock rather than more fetching.

## 6. Known bugs

- **Veto coverage.** 175 messages publish and every one is correctly cited,
  but only 67 were newly extracted on the last run against 124 before, because
  the wrong-citation fallback was removed. `calendars.json` covers 976 of
  2,564 calendars; a calendar with no known address cannot be cited and so is
  not quoted. Rebuilding that index recovers them.
- **Marker coverage.** 4,180 of 10,830 proceedings carry no time. 2,522 of
  those passed on a consent calendar and were never taken up separately, which
  is honest; the rest are recoverable with more phrases. Not with more
  captions: the recordings that carry bills are 910 of 915 captioned already.
- **`proceedings.csv` is one term.** 9,761 of its 9,762 rows are 2025-2026, so
  every recording, boundary and timestamp on this site is current-term. The
  archived calendars are parsed -- 61,429 bill-days back to 1997 -- and have
  never been merged into the one table. That merge is the largest single
  unlock left and it is an architecture decision, not an evening's work.
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
   rule in `CLAUDE.md`. Run on 10 September after the end-provenance change:
   candidate median 0m 02s on 26 of 43, unmoved; worst published end 93m 48s
   -> 12m 05s. `--no-bench` for a number comparable with anything recorded
   before 9 September.
