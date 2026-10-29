# What the misfiled House journals do to the site now, and what the move would change (wf20, 29 Oct 2026)

Read-only. Nothing in the repository, the kit, `corrections/` or `review/` was written, and nothing was asked of gc.nh.gov.

**Sources:**
- **The preview.** https://dry-run.graniterecord.pages.dev, fetched 18:25–18:45 UTC. Its `build.json` says `"finished": "2026-10-29T13:14:28"` and `"commit": "db56680…"`. db56680 is cfbee9f's parent, and `git diff --stat db56680 cfbee9f` touches only `preflight.py` and `versions.json`, so the pages are R1's. Four pages re-fetched at the end had the same sha256 as at the start.
- **The kit.** Its `journals/1999, 2000, 2009, 2010, 2011, 2023, 2025` folders and `archive/queue.csv` were read from R2.
- **The repository** at cfbee9f.

**Method:**
- "Now" is the kit as it stands.
- "After" is a scratch copy of those folders with the moves applied. The 12 copies were deleted (`cmp` confirmed each is identical to `journals/2011/` first), the Organization Day file was moved to `journals/2011/`, and `2000/HJ025` and `HJ026` were moved to `1999/`. `2000/HJ027` stays, as kit_table.md concludes.
- Every "now/after" number comes from the repository's own functions run on those two layouts.

**Scripts:** `im_scripts/`. **Derived tables:** `im_*.jsonl`, `im_*.txt`, `im_*.tsv`, `im_reported_diff.json`. The kit downloads and fetched pages are deleted.

---

## 0. In short

1. **What is wrong on the site comes from the issues the copies displaced, not from the copies.** The General Court's index lists both years under its `journals\2010\` folder. `archive/queue.csv` shows, for example, `journals\2010\HJ010.pdf` named for both "Daily Journal No 10 3-15-11 Final.pdf" and "Daily Journal No 10 3-11-10 Final.pdf". Because one local path served both, nine 2010 House sittings have no journal in the kit. Everything visibly wrong follows from that:
   - **11 session-day pages are missing what the Journal gives them:**
     - the nine 2010 pages;
     - the two 1999 pages whose issues sit in `journals/2000/`.
   - **1 Votes-on-No-Bill page** has 5 rows with no Journal words.
   - **2 term data files** carry 11 day records with no leave list.
   - **6 rows of `/data/rollcalls.csv`** say `outcome_source` "rule" where the Journal would decide. No outcome value is wrong.
2. **Nothing else predicted from the code is wrong on the preview.** Each of these was checked:
   - no bill page;
   - no 2011 page;
   - by-the-numbers;
   - search;
   - officers;
   - the journal links.
3. **The move as proposed:**
   - **Mends** the two 1999 pages.
   - **Costs** one page, `/session/H/2010-12-01`, its only Journal line, unless `journal_days.read_day` is given the December rule first.
   - **Leaves unchanged** the nine 2010 pages and the 5 no-bill rows. Deleting the copies does not bring back the 2010 issues; only fetching them does, and that asks gc.nh.gov, so it is a person's decision.

---

## 1. What is wrong now, page by page

### 1.1 Nine 2010 House session days: no opening, no "Assembled", no leave list, no speakers

**Reader:**
- `build_session_pages.py:3602-3606` calls `journal_days.read_day(date)` for every House day from `JOURNAL_FROM = "1997-01-01"` (line 92).
- `read_day` (`journal_days.py:1148-1155`) is `read_year(date[:4])`. That reads `journals/2010/*.txt` and keys each sitting by its printed dateline.
- No file in the kit prints a sitting on these dates. Run on the kit's copy, `read_day` returns `files: []`, an empty `opening` and 0 absences and attributions for each of them (`im_days_now.jsonl`).

| page | what took the issue's path (queue.csv, `journals\2010\…`) | what the page shows (preview) |
|---|---|---|
| `/session/H/2010-01-06` | `HJ001.pdf`: "Special Session Journal No 01 6-9-10" over "Daily Journal No 01 1-6-10" | Journal "House Journal 6"; no Assembled; How the Day Began has only "Presiding over the House during the day: Rep. Terie Norelli (D - Rock 26), Speaker of the House."; no Excused; 0 "Spoke for"/"Spoke against" |
| `/session/H/2010-02-10` | `HJ006.pdf`: 2-15-11 over 2-10-10 | the same: Presiding line only, 0 speakers, no Excused |
| `/session/H/2010-03-10` | `HJ009.pdf`: 3-2-11 over 3-10-10 | the same |
| `/session/H/2010-03-11` | `HJ010.pdf`: 3-15-11 over 3-11-10 | the same (quoted below) |
| `/session/H/2010-03-24` | `HJ013.pdf`: 3-30-11 over 3-24-10 | the same |
| `/session/H/2010-05-12` | `HJ018.pdf`: 5-18-11 over 5-12-10 | the same |
| `/session/H/2010-05-13` | `HJ019.pdf`: 5-25-11 over 5-13-10 | the same |
| `/session/H/2010-05-19` | `HJ020.pdf`: 6-1-11 over 5-19-10 | the same |
| `/session/H/2010-06-02` | `HJ021.pdf`: 6-8-11 over 6-2-10 | the same |

**Quoted, from `/session/H/2010-03-11`.** Header facts: "Journal / House Journal 24", "Votes Taken / 17 roll calls, 10 divisions / 24 voice votes", with no "Assembled". Then:

> How the Day Began
> Presiding over the House during the day: Rep. Terie Norelli (D - Rock 26), Speaker of the House, and Rep. Sherman Packard (R - Rock 3).
> What the House Did That Day

**What it should show, from a day whose issue is in the kit (`/session/H/2010-03-17`):**
- "Assembled 2:00 PM";
- "The House assembled at 2:00 PM, a prayer was offered and Rep. Michael O'Brien (D - Hills 10) led the Pledge of Allegiance.";
- "Excused for the Day / Show the 44 members excused";
- 12 "Spoke for" and 11 "Spoke against" entries under the bills.

The other 2010 days whose issues are in the kit show 23–44 excused (01-13: 24, 02-17: 23, 03-03: 29, 03-17: 44). What these nine days' own issues print cannot be known from the kit.

**Not caused by the copies, though the mechanism is the same.** 6 Jan 2010's issue lost its path to the June special session's HJ 1, not to a 2011 copy.

### 1.2 Two 1999 House session days: the same gaps

`read_day("1999-10-28")` and `read_day("1999-11-03")` read `journals/1999/`. The issues printing those sittings are `journals/2000/HJ025.txt` and `HJ026.txt`, so both come back empty.

- `/session/H/1999-10-28`: How the Day Began reads only "Presiding over the House during the day: Rep. Donna Sytek (R - Rock 26), Speaker of the House." No Assembled, no Excused, 0 speakers.
- `/session/H/1999-11-03`: the same.

`session_days._journal_day` (`session_days.py:2098`, folders at 2124-2125) also returns None for both dates on the kit as it is. Every rule that checks a vote against the day's journal then falls back to the docket alone, for example `_one_vote` at 820-835. No visible error from that fallback was found on these two pages, but it was not exhaustively traced.

### 1.3 Votes not on a bill, 2009-2010: five House rows without the Journal's words

The no-bill roll calls are paired with the Journal through `rollcall_outcomes.journal_links` (`rollcall_outcomes.py:761-796`). That reads the folder of the roll call's year and finds no tally for these days.

`/session/nobill/2009-2010` reads "Votes 18 / In the Journal's Words 9". Its five 2010 House rows on these days show only the roll-call file's words:

| row on the page | link | roll call |
|---|---|---|
| "Jan 6, 2010 · House · Misc vote · In the record: MOTION FOR LATE DRAFTING AND INTRODUCTION (REP W.O'BRIEN) · Motion Failed 161–201" | `session/H/2010-01-06#rc-2010-H-3` | RC 3 |
| "May 12, 2010 · House · Misc vote · In the record: MOTION TO TAKE UP BILLS W/OUT DEBATE BEFORE BILLS W/DEBATE · Motion Passed 222–102" | `#rc-2010-H-201` | RC 201 |
| "Jun 2, 2010 · House · Rules suspension · In the record: RULES SUSPENSION TO ALLOW LATE DRAFING, INTRO & CONSID (W.O'BRIEN) · Motion Failed 168–200" | `#rc-2010-H-239` | RC 239 |
| "Jun 2, 2010 · House · Misc vote · In the record: OUGHT NOT TO PASS · Motion Passed 187–155" | `session/H/2010-06-02` (**no anchor**) | RC 240, HA 3, the address for the removal of Philip Cross |
| "Jun 2, 2010 · House · Misc vote · In the record: LAY ON TABLE (REP EATON) · Motion Passed 204–137" | `session/H/2010-06-02` (**no anchor**) | RC 241, HA 2, the address for the removal of Lucinda Sadler |

**What a placed row looks like, on the same page:**
- "Jun 9, 2010 · House · Adjourning or recessing · Under the Journal's heading "Motion to Adjourn" · Motion Failed 74–294".
- On `/session/H/2010-06-09` it quotes "MOTION TO ADJOURN / Rep. Kappler moved that the House adjourn for 90 days. / The Speaker ruled the motion out of order. … and the motion failed." and cites "House Journal 1, June 9, 2010, page 11 of the file".

**The same gap on the session-day pages:**
- `/session/H/2010-01-06` and `/session/H/2010-05-12` each draw their no-bill roll call with no quotation, against 2010-06-09's quoted one.
- On `/session/H/2010-06-02`, "Votes on No Bill" shows RC 239 as "In the record: Rules suspension to allow late drafing, intro & consid (w.o'brien)" and nothing from the Journal.
- That page draws RC 240 and RC 241 under HA 3 and HA 2 as bill votes, which is why the no-bill page's links to them have no anchor.

**Pages:** 1 no-bill page and 3 session-day pages (01-06, 05-12, 06-02), all among the nine above.

### 1.4 The published data

- **`/session/H/2009-2010.json`:**
  - the nine days carry `"excused": null`;
  - their `summary` lacks the sentence the others end with. Compare 2010-03-11 "…Rep. Terie Norelli (D - Rock 26) and Rep. Sherman Packard (R - Rock 3) presided." with 2010-03-17 "…presided. 44 members were excused for the day."
- **`/session/H/1999-2000.json`:** the same for 1999-10-28 and 1999-11-03.
- **`/data/rollcalls.csv`:**
  - On the nine days, 96 of the 102 House roll calls are `docket`.
  - Six are `rule`: 2010 RC 3, 68 (HB 558, "OTP/AM 0417H (NT)" 213–141), 201, 239, 240 and 241. `rollcall_outcomes.apply` (`rollcall_outcomes.py:872`) asks the Journal only for roll calls no docket line names, and for these it finds nothing.
  - Every one of the six clears or misses its threshold by its own count, so `passed` is what the Journal would say. Only the `outcome_source` column is wrong. The table is in `im_rollcalls_affected_days.tsv`.
  - For comparison, the other 2010 days have `docket` 126 and `journal` 2.

### 1.5 How many pages, in all

| what | count | which |
|---|---|---|
| session-day pages missing the opening, Assembled, Excused and speakers | **11** | 2010-01-06, 02-10, 03-10, 03-11, 03-24, 05-12, 05-13, 05-19, 06-02; 1999-10-28, 11-03 |
| …of which with a no-bill vote drawn without the Journal's words | 3 | 2010-01-06, 05-12, 06-02 |
| Votes-not-on-a-bill pages with rows lacking the Journal's words | **1** | `/session/nobill/2009-2010` (5 rows) |
| term data files with day records lacking the leave list | **2** | `/session/H/2009-2010.json` (9 days), `/session/H/1999-2000.json` (2 days) |
| bulk-data rows with the wrong `outcome_source` | **6** | `/data/rollcalls.csv`, 2010 H RC 3, 68, 201, 239, 240, 241 |
| bill pages | **0** | §2 |
| 2011 pages | **0** | §2 |

These counts come from the term files and the CSV the preview serves, joined with what the readers return on the kit (`im_days_now.jsonl`, `im_session_features.jsonl`). They were not estimated.

---

## 2. Predicted from the code, checked, and not wrong

- **HB 134.**
  - `/bill/2010/hb134` does not exist ("No page at this address"): 134 is a first-year number, and the 2009–2010 bill is `/bill/2009/hb134`.
  - That page says "Status: Not introduced" and "the House Journal of January 7, 2009 leaves it out of the bills it introduces". Its note quotes "The resolution of January 7, 2009 (House Journal No. 2) names House Bills 31 through 86, 88 through 133 and 135 through 223".
  - That note comes from the hand-made table `build_data.INTRODUCTION_FROM_JOURNAL` (`build_data.py:611-612, 623`), not from reading the kit's folders at build time.
  - `/bill/2011/hb134` tells 2011's bill ("relative to eligibility for walking disability plates", Transportation 13–0, killed in the Senate 4 May 2011) from its docket.
  - No bill page before 2025 carries Journal text. `journal_bills` reads 2025 onward plus HB 459 of 2021, as code_map.md §2.8 says.
  - The 2011 bill does not reach the 2009 page.
- **`narrative.house_reported`** (`narrative.py:4831-4847`, used at 5754). It reads the term's folders and keys by bill number alone.
  - On the kit, the 12 copies add a committee to **307** bill numbers (measured by placed name; `im_reported_diff.json`).
  - I fetched the 2009–2010 record of all 301 that have a page. Six numbers have no 2009–2010 page: HB 27, HB 29, HCR 16–18 and HR 10.
  - Seven House stage headings name a committee only the copies give. Every one is supported by the bill's own docket (`im_stagecheck.txt`):
    - six are the bill's committee of referral (HB 25, HB 258, HCR 8, HB 607 twice, HCR 21);
    - HB 113 of 2009's "House Committee (Finance)" follows its own row "2009-02-12 Referred to Finance HJ 17".
  - No House committee stage among the 301 is left unnamed, which is the other way the copies could act: they could put `held` into `said_by`.
  - **Wrong headings found: 0.**
- **2010 RC 67 (HB 1662, 10 Feb 2010, 243–110)** is paired today to a tally in the 2011 copy `journals/2010/HJ021.txt`. The docket names it ("Inexpedient to Legislate: MA RC 243-110", HJ 16), so the Journal is never asked (`rollcall_outcomes.py:872`). The bill's data at `/bills/2010/HB1662.json` reads `"passed": True`, and the CSV says `docket`. **Visible effect: none.**
- **The twelve 2011 days the copies print** (`/session/H/2011-02-15`, 03-02, 03-15, 03-30, 05-18, 05-25, 06-01, 06-08, 06-22, 09-14, 10-12, 11-30) all have an opening, an Assembled time and a leave list of 10–31. `read_day` reads only `journals/2011/`, whose files are identical to the copies.
  - No 2011 page links into the General Court's `journals\2010\` folder. The only journal link on them is `journals%5C2011%5CDaily%20Journal%20No%2019%205-25-11%20Final.pdf`, on 2011-05-25.
  - `/session/nobill/2011-2012` reads "Votes 10 / In the Journal's Words 10", with no duplicate rows.
  - 2011-01-05, the issue missing from the kit, has no page ("No page at this address").
- **`/officers.json`** cites `journals/2010/` once: `"source": "journals/2010/Daily Journal #1, 12-1-10, Organization Day Final.txt, 2010-12-01: \"Rep. William L. O'Brien was declared the duly-elected Speaker\""`. It quotes the right sentence from the right file; only the folder is wrong. None of the 12 copies is cited. `source` is not drawn on any HTML page; `build_pages.py:4325` reads only the tenures.
- **Journal links** on session pages are built only from 2025 on (`queue_links.journal_keys_from_queue(…, since=2025)`, `queue_links.py:62`), so none can point at a wrong year here.
- **Learn's by-the-numbers, the About figures, search and the floor index.**
  - `learn_numbers.py`, `about_figures.py`, `build_search_index.py`, `build_floor_index.py` and `calendar_meetings.py` contain no read of a journal folder (grep: 0 lines).
  - By-the-numbers reads `narratives.json` and `rollcalls.json`. Their journal-dependent parts are the stage headings (0 changed, above) and `passed` (unchanged, §1.4).
  - Per-session counts ("took up 41 bills, with 17 roll calls…") come from the docket.
  - **Nothing there is wrong because of this.**

---

## 3. Nearby gaps the misfiling did not cause (do not credit them to it, or expect the move to fix them)

- **Every House Organization Day page but one lacks an opening, and that one has it only because it is misfiled.**
  - Of the 14 House Organization Days from 1998 to 2024 (`/session/H/1998-12-02` … `/session/H/2024-12-04`), only `/session/H/2010-12-01` has "How the Day Began / A prayer was offered." None has a leave list.
  - The cause: `read_day` has no December rule. `read_senate_day` (`journal_days.py:1343-1344`) and `_journal_day` (`session_days.py:2124-2125`) have one.
  - 2010's file is found only because it sits in `journals/2010/`.
  - With the rule added (`DEC=1` in `im_scripts/days.py`):
    - 2022-12-07 reads `HJ 01 December 7, 2022.txt` with an opening, 6 excused names, 1 speech and 2 unanimous-consent records;
    - 2024-12-04 reads `HJ 01 December 4, 2024.txt` with an opening, 10 excused names, 3 speeches and 1 unanimous-consent record.
  - The other eleven Organization Days were not run.
- **`/session/H/2000-01-05` and `/session/H/2000-02-03` have no opening.**
  - The cause is the form feed before their headings, which `DAY_HEADER` (`journal_days.py:126`) misses. That is kit_table.md item 1, covering 10 sittings from 1997 to 2006.
  - `2000/HJ027.txt` is correctly filed, and moving it would not change this.
- **`/session/nobill/1999-2000`'s "Jan 5, 2000 … ADOPT AMENDMENT TO HOUSE RULE 63 … 280–57" row has no Journal words and no anchor.**
  - This is RC 189 of the **1999** roll-call file.
  - `journal_links` pairs a 1999-file roll call only with `journals/1999/`, and the issue that prints it, `2000/HJ027`, is rightly in 2000.
  - The session page draws it under HR 21: "A floor amendment was adopted on a roll call 280–57".
  - This is a reader limit, not a misfiling. Copying HJ027 into 1999 would pair it (code_map.md §2.3), and is the owner's call.
- **2010-05-21 and 2010-10-13 have no journal either**, but the General Court's 2010 index lists no issue for them. The last 2010 row in `archive/queue.csv` is "Daily Journal No 21 6-2-10 Final.pdf". So the collision did not cause these. Why they are absent is a guess.
- **2010-01-27 and 2010-04-28 have their issues in the kit.** `read_day` finds an opening (assembled, prayer, pledge) and 21 and 25 speech attributions, but no leave list. Unrelated to the move.
- **`/session/H/2010-05-19` draws 17 roll calls; the roll-call file has 12 for that date.** The five extra tallies (172–118, 170–118, 168–123, 168–117 and 158–179) come from docket rows, for example HB 1270's "House Concurs with Senate AM #1952s(NT) (Rep Kaen)". The roll-call file has no 2009–2010 row with those tallies. Whether the day's journal, if it were on disk, would change that is **a guess**. It is the only one of the eleven journal-less days whose count disagrees with the file.

---

## 4. What changes after the move

Measured by running the repository's readers on the "after" copy (`im_days_after.jsonl`, `im_pairs.txt`). Changes in **bold** are visible on the site.

| action | what changes on the site | what does not |
|---|---|---|
| **delete** `journals/2010/HJ006, 009, 010, 013, 018–025.txt` | No HTML page is predicted to change. 2011 pages read `journals/2011/`: `read_day` and `_journal_day` give identical results for all twelve 2011 days before and after (`im_days_2011_now.jsonl` / `_after.jsonl`). Behind the pages: `read_year("2010")` stops returning 12 dates of 2011; `house_reported("2009-2010")` loses the 307 added committees, none of which reaches a heading (§2); `journal_links` for 2010 pairs 128 instead of 129 (RC 67 → none; the docket still decides it, so the CSV is unchanged). | The nine 2010 pages and the five no-bill rows: their issues are still not in the kit. |
| **move** `journals/2010/Daily Journal #1, 12-1-10, Organization Day Final.txt` → `journals/2011/` | **`/session/H/2010-12-01` loses "How the Day Began / A prayer was offered."** Run on the moved copy, `read_day` returns `files: []` and an empty `opening`. **`/officers.json`**: O'Brien's `source` changes to `journals/2011/…`. | `_journal_day` returns the same thing from either folder. 2011's roll-call pairing stays 249 of 249: the file has no name `_journal_order` reads, so it sorts last and holds no tally that moves anything. |
| …**with** `read_day` given the December rule first | 2010-12-01 keeps its opening. **13 other House Organization Day pages gain an opening**, and a leave list where the Journal prints one. Verified for 2022 and 2024 (§3). | — |
| **move** `journals/2000/HJ025.txt` → `journals/1999/` | **`/session/H/1999-10-28` gains** Assembled, "How the Day Began" (assembled, prayer, Pledge), "Excused for the Day" (16 names read) and speakers (7 attribution records). The 1999-2000 term file gains its excused count and summary sentence. | outcomes, CSV and no-bill page |
| **move** `journals/2000/HJ026.txt` → `journals/1999/` | **`/session/H/1999-11-03` gains** the same: 33 names, 21 attribution records. `_journal_day` now finds the sitting (9 roll calls, 30 bills), so the vote-placement checks run against it; any page change from that was **not measured**. | |
| both 2000 moves, roll calls | 1999 pairing goes from 145 to 156 (RC 176–177, 179–187). All eleven are docket-decided, so `rollcalls.csv` is unchanged, and none is a no-bill vote. 2000 stays at 121. | 2000-01-05 and 02-03 (form feed); the RC 189 row (§3) |

**What the owner should expect, in one line:**
- two 1999 pages gain their Journal content;
- one 2010 page loses its only Journal line unless `read_day` reads December from the next folder first, and with that change thirteen more Organization Day pages gain theirs;
- the nine 2010 pages and the five no-bill rows stay as they are until the nine 2010 issues are fetched.

**For the fetch** (the owner's word, and only one fetch at a time): the queue names are "Daily Journal No 01 1-6-10", "No 06 2-10-10", "No 09 3-10-10", "No 10 3-11-10", "No 13 3-24-10", "No 18 5-12-10", "No 19 5-13-10", "No 20 5-19-10" and "No 21 6-2-10", each `Final.pdf` under `journals\2010\`. They need local names that cannot collide, because `fetch_calendar_archive._local` (`fetch_calendar_archive.py:231-247`) names a file by its number alone. When they arrive:
- the nine pages gain an opening, a leave list and speakers;
- 101 roll calls pair (code_map.md §2.3);
- the five no-bill rows gain the Journal's words and `/session/nobill/2009-2010` reaches 14 of 18. That last number is a prediction from the code, not a measurement.

**After the move, `seed-kit` alone does not clear the old keys.** It leaves keys that are in the bucket and no longer on the laptop (`cloud.py:1432, 1441-1442`), so the 14 old keys need removing explicitly (kit_table.md).

---

## 5. Not measured, or a guess

- Any change on the two 1999 pages from `_journal_day` finding the sitting (vote placement, `_one_vote`) beyond the opening, leave list and speakers. A phrase search found no "on N bills" grouping line on any of the eleven pages, before or after; that is a weak check.
- What the nine 2010 issues would put on their pages. That needs them fetched.
- The eleven other Organization Days under a December rule: only 2010, 2022 and 2024 were run.
- Whether 2010-05-19's five docket-only roll calls would be placed differently with its journal (§3).
- Why 2010-05-21 and 2010-10-13 have no issue in the General Court's 2010 index.

## Files (under /tmp/claude-0/audit/wf20/)

- **Scripts**, in `im_scripts/`:
  - `fetch.sh`, `text.py`, `sessfeat.py` (page features);
  - `termdays.py`;
  - `billdata.py` and `stagecheck.py` (the 301 bills);
  - `reported.py` (house_reported with and without the copies);
  - `days.py` (read_day and _journal_day on a layout; `DEC=1` for the December rule);
  - `pairs.py` (journal_links now and after).
- **Tables:**
  - `im_session_features.jsonl` (45 session pages as served);
  - `im_days_now.jsonl` and `im_days_after.jsonl`, plus `im_days_2011_now.jsonl` and `im_days_2011_after.jsonl`;
  - `im_pairs.txt`;
  - `im_reported_diff.json` and `im_stagecheck.txt`;
  - `im_rollcalls_affected_days.tsv`.
