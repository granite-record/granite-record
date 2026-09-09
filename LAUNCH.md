# Granite Record — what is done, what is not, and what to do first

Written 9 September 2026 by reading the code and measuring the site, not by
reading the older documents. Where this disagrees with `ROADMAP.md`,
`ARCHITECTURE.md` or `HANDOFF.md`, this is the newer answer — several of their
"outstanding" items shipped in the last three days and one of their
assumptions is now known to be wrong.

Every number here was measured today.

---

## 1. Shipped and working

| | evidence |
|---|---|
| Search, facets, per-bill cards and detail | 33,683 bills across 19 terms |
| One renderer for every page | `bills.html` + `app.js`; the second renderer was deleted 7 Sep |
| Term keying | all per-bill files are `{term: {bill: …}}`; preflight fails on the old shape |
| Per-term index split | first load 15,329 KB → **1,068 KB** |
| Static page per bill, legislator, committee | 73,086 files |
| Committee pages | 104 built |
| Civics section | 11 topics + hub at `/learn/` |
| RSS feeds | per bill, per committee, hearings, all |
| Passage rail | including vetoes, and closed terms no longer read as in progress |
| Veto messages | 175, every one citable and fit to quote |
| The archive on disk | DB 27 views / 3.1M rows; 18 terms of bills; House calendars 100%; journals 100% |
| Hearings parsed from calendars | **61,429 bill-days, 1997–2026**, kind 98% and room 100% against the docket |
| The test suite | 67 checks, green |

## 2. Running right now

- **Docket for 2017-2018**, then 2019-2020, 2021-2022, 2015-2016. ~23 hours.
- **Archived bill text** after that. Two requests per bill, 15s apart, days.
- **Captions**, trickling — YouTube throttled this address after a 984-in-a-day
  run on 5 September. 890 of 4,428.
- **Calendar text extraction**, idle and current.

## 3. Two facts that change the plan

**Archived sponsors are not in the database.** `Sponsors` holds 2025 and 2026
only; `Subject` holds the current session only. 2023-2024's sponsors came from
its *status pages*. Since the archived-text fetch already asks for each bill's
status page as stage one, **sponsors, committee and subject for all sixteen
remaining terms arrive with it, free**. That single queued fetch is worth far
more than "bill text".

Today: **16 of 19 terms have zero sponsors and 18 of 19 have zero topics.**

**Full pages for every archived term will not fit.** 73,086 files today, three
per bill. The seventeen terms without pages are ~28,000 bills ≈ 84,000 more
files, against Cloudflare Pages' 100,000. So: full pages for roughly **two more
terms**, cards beyond that — or per-bill data behind a Worker, which is a
bigger change than it looks.

---

## 4. Ranked: most impact for least effort

### Done, 9 September

Items 1-4 below are fixed and struck through. Each was measured before and
after.

1. ~~**Narratives in the past tense**~~ — 13 current-term bills said a
   committee "held a work session on October 13, 2026" for a session not yet
   held. `narrative.py` compares the docket date to today; those read "A work
   session is scheduled for..." now. 0 remain.
2. ~~**HTML entities published raw**~~ — `text_of()` replaced a hand-written
   list of six entities, so `&ldquo;` and `&rdquo;` went out as themselves:
   **3,882 occurrences**, 3,816 in bill text and 41 in official analysis.
   `html.unescape` knows the whole table. 0 remain.
3. ~~**Page furniture inside committee reports**~~ — **542 running headers**
   landed mid-sentence in members' reasoning. The pattern wanted whitespace
   the PDF does not have: pdftotext emits "19 DECEMBER2025HOUSERECORD" jammed
   together. 0 remain, and a date written out in prose still survives.
4. ~~**The rail was wrong for resolutions**~~ — 36 adopted resolutions drew a
   cross on the chamber that adopted them, against a Senate they were never
   going to see. HR and SR now carry a two-stop rail: the chamber, and whether
   it was adopted. HCR, SCR and CACR do cross and are untouched.

### Do first — small and visible

5. **Special-bill notes.** HB1 is the budget, HB2 the trailer bill, HB2026 the
   ten-year transportation plan. A reader cannot know that. Hand-written, a
   dozen of them.
6. **Search loads everything.** 100, then more on scroll.
7. **Sponsor party colour is inconsistent** across bill, committee and
   legislator pages. One chip, used everywhere.
8. **Ranking and deputy ranking members** are not named. Conventionally the
   first two in the minority; `CommitteeMembers` has the data.

### Do next — larger, and each unlocks something

9. **The sampling review tool.** A local page that opens one sample with the
   thing being measured already up, takes a verdict and a note, and moves on.
   `ground_truth.csv` has 35 proceedings and is the only independent measure
   this project has. **Related bills, auto-topics and narrative quality all
   need the same tool**, so it is one build for three features — and related
   bills cannot honestly be evaluated without it.
10. **Wire the video match.** Proved today on 2023-2024 with no network: 1,643
    of 1,648 recordings convert and **4,731 of 5,868 proceedings (81%) match a
    single video, 1,693 bills reaching a recording** — no captions needed. The
    remaining work is the merge into `proceedings.csv`, which must not destroy
    the current term.
11. **Legislator names in one format everywhere** — "Seidel, Sheila" should be
    "Rep. Sheila Seidel (R-Rock 21)", including for members who have left.
    `names.py` is where it goes.
12. **Roll calls on legislator pages are unreadable** — date, bill number,
    motion, vote, and no way to see what the bill was, how the vote came out,
    or how the member voted against their party. Group by session day.
13. **Amendment diffing.** The data is already here: `LegislationText`, 6,825
    rows, every version of every current-term bill with `SortOrder`. Current
    term only, and no fetching needed.
14. **Committee pages: upcoming hearings**, and a session day as a table —
    every bill heard, its status change, the report split, bill numbers linked.

### Then — new surface

15. Session calendar page: consent calendar, regular calendar, committee
    motions, in order, explained.
16. Executive Council, Governor, CD-1, CD-2 and US Senator pages.
17. Cross-term legislator identity, so a member's whole career is one record.
    `DistrictPast` exists because a 1998 member's district is not today's.
18. Related bills — after the review tool, never before.
19. Topics for the eighteen terms without them — visibly derived, method
    stated, scored against a checked sample.

### Housekeeping, not blocking

20. Dark mode, favicon and logo, header and footer, the redundant status block.
21. Email routing, and the follow-by-email decision the static site cannot
    make on its own.
22. Google indexing — needs the URLs and titles cleaned first.
23. Accessibility, continuously.
24. `build_site_v2.main` is still **449 lines**. Internal, and the reason a
    floor-marker miss went unnoticed.

---

## 5. Known bugs not yet fixed

- The four above are fixed. What follows is what is left.
- **Veto coverage regressed** 124 → 67 newly-extracted messages when the
  citation fallback was removed today. 175 publish in total, all correct, but
  `calendars.json` still covers only 976 of 2,564 calendars, and the rest
  cannot be cited and so are not quoted. Rebuilding that index fully would
  recover them.
- **`--phrases` and marker coverage**: 4,180 of 10,830 proceedings carry no
  time. 2,522 of those passed on a consent calendar and were never taken up
  separately, which is honest; the rest are recoverable.

## 6. Before launch, specifically

1. The four correctness bugs in §4.
2. A decision on the file cap — two more terms as pages, or a Worker.
3. `check_civics_links.py` has never been run; the civics section's outbound
   sources are unverified.
4. The proposal's own instruction that somebody who knows the building reads
   the civics pages before they ship.
5. Accessibility pass at 360, 768 and 1440.
