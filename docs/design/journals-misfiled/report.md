# The kit's misfiled House journals: assessment and fix (wf20, 29 Oct 2026)

For the manager and the owner. This was read-only:
- Nothing was written to the repository (dev `cfbee9f`, R1), the bucket, `corrections/` or `review/`.
- Nothing asked gc.nh.gov.

It draws on four notes in this folder:
- `kit_table.md`: every kit journal read against its folder;
- `code_map.md`: every reader of the folders;
- `impact.md`: the site, now and after the move, run with the repository's own readers;
- the verifier's re-check, `vf/verify_moves.md`. It downloaded all 1,064 files again, re-derived every move, and re-read the preview.

I added a reading of `src/ops/cloud.py` for §6, and a removal script tested against a folder bucket. The preview's `build.json` reads "finished": "2026-10-29T14:39:00", commit cfbee9f. Three pages re-read at 19:20 UTC were unchanged.

## In short

- **The Clerks are right about `journals/2010/`, and it is 13 files, not 12.** HJ006, HJ009, HJ010, HJ013 and HJ018–HJ025 make 12, and the Organization Day of 1 December 2010 makes 13. All are issues of the 2011 session.
- **In `journals/2000/`, only HJ025 and HJ026 are 1999 issues.** HJ027 is the issue of 5 January 2000 and stays.
- **15 files go: 12 deleted, 3 moved, no collisions.**
  - The 12 numbered 2010 files are **byte-identical copies** of files already in `journals/2011/`, so they are deleted.
  - The Organization Day moves to `journals/2011/`, and HJ025 and HJ026 move to `journals/1999/`.
- **"Misfiled" means against the readers' convention, not the source.**
  - The General Court's own index lists these documents under its `journals\2010\` and `journals\2000\` folders, and the fetch kept its folders.
  - The readers key a folder to one session's numbered series.
- **Most of the visible harm comes from what the copies displaced, not from the copies.**
  - The drain names a local file by its number alone, so 2011's issues took the paths of eight 2010 issues, and the June special session's HJ001 took a ninth.
  - Those nine 2010 issues were never fetched. **Moving files does not bring them back; only a fetch does, and that is a person's decision.**
- **On the site now:**
  - 11 session-day pages lack the Journal's opening, leave list and speakers: 9 of 2010 and 2 of 1999.
  - 1 votes-not-on-a-bill page has 5 rows without the Journal's words.
  - 2 term data files lack those days' leave lists.
  - 6 rows of `rollcalls.csv` give the wrong `outcome_source`; the outcomes themselves are right.
  - **Not wrong:** any bill page, any 2011 page, and any count "of the 2010 session".
- **After the move:**
  - The two 1999 pages are mended.
  - `/session/H/2010-12-01` loses its one Journal line, unless `journal_days.read_day` first learns the December rule the other readers already have. That rule would also give 13 other House Organization Day pages their opening.
- **No `cloud.py` command removes a laptop-owned file from the bucket's kit.** §6 gives the steps and a tested script that uses `cloud.py`'s own pieces.

## The convention, and what "misfiled" means here

**The readers' rule.** A folder holds one session's numbered series: that calendar year's sittings, plus the Organization Day of the December before, which is the series' No. 1.
- `session_days.journal_series` (`src/pages/session_days.py:3748-3752`): "the December organization day opens the NEXT year's: journals/2023/HJ 01 December 7, 2022.txt".
- `read_senate_day` (`src/parse/journal_days.py:1338-1344`) and `_journal_day` (`session_days.py:2124-2125`) both read the next year's folder for a December date.

**The kit keeps that rule everywhere else.**
- Every other Organization Day is in the next year's folder: House 1996–2024 except 2010, and Senate 2004–2024.
- Two kinds of exception are filed correctly and must not be "fixed":
  - **Odd-year December sittings stay in their own year:** `journals/2001/HJ022.txt` (l.1006 "(Wednesday, December 12, 2001)") and `journals/2025/HJ 19 December 17, 2025.txt`.
  - **`journals/2003/HJ023.txt` is a 2003-series issue whose only sitting is 7 January 2004.** It prints l.75-76 "The Speaker called the recessed session of September 4, 2003 to order … on Wednesday, January 7, 2004".

**The source files these documents differently.**
- `archive/queue.csv` shows the General Court's year-2010 index naming 2011 issues under `fileName=journals%5C2010%5C…`. Examples are "Daily Journal No 25 11-30-11 Final.pdf" and "Daily Journal #1, 12-1-10, Organization Day Final.pdf".
- Its 2000 index names "HJ No 25 07-01-2000" and "HJ No 26 11-04-2000".
- `src/fetch/gc_web/fetch_journals.py:51-58` keeps the General Court's folder.

So these 15 files are where the source put them, and wrong only for the readers.

## 1. The moves, every one

All paths are bucket keys under `kit/`, and every one is the laptop's (`cloud_kit.json`, "journals/*/*.txt", owner "laptop"). The quoted evidence was re-derived by the verifier from each file's own text.

| # | old | → new / action | why (quoted, line) |
|---|---|---|---|
| 1 | `journals/2010/Daily Journal #1, 12-1-10, Organization Day Final.txt` | **move** → `journals/2011/` (same name) | l.4 "Calendar and Journal of the 2011 Session"; l.6 "Vol. 33 … Wednesday, December 1, 2010 No. 5"; l.8 "HOUSE JOURNAL No. 1": the 2011 series' No. 1, and the kit has no other copy |
| 2 | `journals/2010/HJ006.txt` | **delete** | l.6 "Vol. 33 … Tuesday, February 15, 2011 No. 17"; l.15 "HOUSE JOURNAL No. 6"; byte-identical to `journals/2011/HJ006.txt` (cmp, sha256) |
| 3 | `journals/2010/HJ009.txt` | **delete** | l.8 "… Wednesday, March 2, 2011 No. 25"; identical to 2011/HJ009 |
| 4 | `journals/2010/HJ010.txt` | **delete** | l.8 "… Tuesday, March 15, 2011 No. 26"; l.4297 "HB 134, relative to eligibility for walking disability plates" (the Clerks' example); identical to 2011/HJ010 |
| 5 | `journals/2010/HJ013.txt` | **delete** | l.8 "… Wednesday, March 30, 2011 No. 34"; identical |
| 6 | `journals/2010/HJ018.txt` | **delete** | l.8 "… May 18, 2011 No. 44"; identical |
| 7 | `journals/2010/HJ019.txt` | **delete** | l.8 "… May 25, 2011 No. 46"; identical |
| 8 | `journals/2010/HJ020.txt` | **delete** | l.8 "… June 1, 2011 No. 48"; identical |
| 9 | `journals/2010/HJ021.txt` | **delete** | l.8 "… June 8, 2011 No. 51"; identical |
| 10 | `journals/2010/HJ022.txt` | **delete** | l.8 "… June 22, 2011 No. 57"; identical |
| 11 | `journals/2010/HJ023.txt` | **delete** | l.8 "… September 14, 2011 No. 64"; identical |
| 12 | `journals/2010/HJ024.txt` | **delete** | l.8 "… October 12, 2011 No. 68"; identical |
| 13 | `journals/2010/HJ025.txt` | **delete** | l.8 "… November 30, 2011 No. 76"; identical |
| 14 | `journals/2000/HJ025.txt` | **move** → `journals/1999/HJ025.txt` | l.6 "Calendar and Journal of the 1999 Session"; l.8 "Vol. 21 … Thursday, October 28, 1999 No. 89"; l.135 "HOUSE JOURNAL No. 26" |
| 15 | `journals/2000/HJ026.txt` | **move** → `journals/1999/HJ026.txt` | l.8 "Vol. 21 … Wednesday, November 3, 1999 No. 95"; l.38 "HOUSE JOURNAL No. 27" |
| — | `journals/2000/HJ027.txt` | **stays** | l.8 "Vol. 22 … Wednesday, January 5, 2000 No. 5"; l.738 "HOUSE JOURNAL No. 1" / l.740 "Wednesday, January 5, 2000". Its masthead "1999 Session" is a misprint, and its first 737 lines are the tail of 1999's No. 27, as every first issue of a year carries the old tail |

HJ025 and HJ026 continue 1999's chain exactly: `1999/HJ024.txt` ends at l.54 "HOUSE JOURNAL No. 25" / l.56 "Thursday, July 1, 1999".

**Collisions.**
- **Rows 2–13:** a "move" would overwrite `journals/2011/HJ0NN.txt` with the same bytes. They are resolved by deleting the 2010 copy.
- **Rows 1, 14 and 15:** nothing is in the way.
  - `journals/2011/` holds only HJ003–HJ025.
  - `journals/1999/` holds HJ001, HJ003–HJ012 and HJ014–HJ024.
- Keep the Organization Day's name. The readers glob `*.txt`, and verified 2011 roll-call pairing stays at 249 of 249 with it last.

**Corrections to the earlier notes.**
- **The old keys to remove number 15, not 14.** `kit_table.md`, `code_map.md`, `impact.md` and the verifier all say 14: 12 copies + 1 Organization Day + 2 from 2000 is 15. All 15 are in the bucket listing (`ls_house.txt`).
- **The PDFs move with their texts, on the laptop.** The bucket holds only the `.txt`.
  - The 12 `journals\2010\HJ0NN.pdf` files are the 2011 PDFs: the queue's byte counts equal the 2011 rows'.
  - If one is left, `src/parse/extract_calendar_text.py:90-92` writes its `.txt` again, and `seed-kit` sends it back.
- **Leave `archive/queue.csv` alone.** It is the night's file since 1 October 2026 (`cloud_kit.json`, owner "night"). `seed-kit` keeps the night's copy, and `send-night` sends only the caption results (`cloud.py:3641-3645`), so the laptop has no way to change it.
  - **The one cost is a missing link.** `journal_motions.addresses()` (`src/parse/journal_motions.py:1656-1673`) finds a journal's General Court address only by the queue's `path` column. A passage quoted from one of the three moved files would therefore lose its link; the citation text stays.
  - Whether any such passage is drawn was **not measured**. If it matters, it is a code change, not a kit one.
- **Moving a held file does not make the drain ask for it again.** The drain takes only rows in state "wanted" (`fetch_calendar_archive.py:1029-1032`).

## 2. Which builds read the folders, and how each is affected

The test is whether a reader opens a folder by year ("folder") or dates each sitting by the dateline printed inside ("printed"). Only folder-keyed readers can attribute a file to the wrong session.

| reader (file:lines) | keys on | effect today | after the move |
|---|---|---|---|
| `journal_days.read_year` / `read_day` (`src/parse/journal_days.py:1100-1155`), called for every House day from 1997 by `build_session_pages.py:3602-3606`: the opening, Assembled time, leave list and speakers | the folder of `date[:4]`, then the printed date; **no December rule** (1150) | nine 2010 days and 1999-10-28 / 11-03 find no file and come back empty; 2010-12-01 is found only because it is misfiled | the 1999 days are found; 2010-12-01 is lost unless `read_day` reads the next folder for December, as `read_senate_day` does at 1343-1344 |
| `session_days._journal_day` (`src/pages/session_days.py:2098-2215`; folders 2124-2125): vote placement, `_sat`, `Day.printed`, `_one_vote` | the folder of the date's year, plus the next year in December; then printed | None ("no journal on disk") for the same 11 days, so the docket alone decides | the 1999 days are found (9 roll calls, 30 bills on 11-03); any page change from that was **not measured** |
| `rollcall_outcomes.journal_files` / `journal_links` (`src/parse/rollcall_outcomes.py:660-667, 761-796`), used for `outcome_source = "journal"` at 872 and by `journal_motions` at 2397 | the folder of the roll call's year | 2010: 129 of 230 House roll calls paired, the 101 unpaired being exactly the nine journal-less days; RC 67 is paired to a tally in a 2011 copy, with no visible effect (the docket decides it). 1999: 145 of 163 | 2010: 128 (RC 67 unpaired). 1999: 156 (RC 176–177 and 179–187 gained, all docket-decided, so the CSV is unchanged). 2000: 121, unchanged |
| `rollcall_outcomes.journal_divisions` / `journal_division_words` (528-550), used at `session_days.py:3572` for a CACR division's wording | the folder of `date[:4]` | 2011 divisions are pooled into 2010's; **not measured** | the pooling ends |
| `journal_motions` (`src/parse/journal_motions.py`): no-bill votes via `journal_links`; journal-only divisions read every folder, dated by the printed running head, de-duplicated (2452-2457 already names "journals/2010/ holds copies of House Journals of 2011") | folder for no-bill votes; printed for the rest | `/session/nobill/2009-2010` has 5 rows without the Journal's words, because the issues are missing; the kept copy's `file` names `journals/2010/` | copies gone, so `file` names `journals/2011/`; a passage from a moved file loses its link (above) |
| `narrative.house_reported` (`src/parse/narrative.py:4831-4847`, used at 5754): which committee a stage heading names | the folders of the term's two years, `HJ*.txt`, **by bill number alone** | 2011 reports on 329 bill numbers (307 by placed name) enter the 2009–2010 lookup; **0 wrong headings** among the 301 with a page (`im_stagecheck.txt`) | the exposure ends |
| `officers.house_mentions` (`src/parse/officers.py:315-339`) → `/officers.json` | every folder; printed | O'Brien's `source` cites `journals/2010/Daily Journal #1…`. It is the right sentence; `source` is drawn on no page | cites `journals/2011/…` |
| `build_site_v2.journal_sittings` (7172-7197) | every folder; printed | none | none |
| `journal_bills` (`src/parse/journal_bills.py:123-130`) | folder, 2025 onward and 2021 (HB 459) only | none | none |
| preflight `_introductions_against_journal` (108855+, escape at 108971) | folder | could excuse a 2009 number a 2011 copy names; a **guess**: no case today | none |
| preflight `_speakers_against_journal` (95501+) | folder `date[:4]`; printed | the 11 days are simply not checked | the 1999 days are checked |
| `calendar_documents.py`, `extract_calendar_text.py`, `archive_status.py`; `journal_days --coverage` (CLI only, counts by folder) | queue / file names | none on the site; `--coverage` counts the copies twice | — |

**Not readers of the folders** (checked by grep): `learn_numbers.py`, `about_figures.py`, `build_search_index.py`, `build_floor_index.py` and `calendar_meetings.py`. `build_nobill_votes.py` and `vote_passage.py` read only `journal_motions.json`. Per-session counts come from the docket through `session_days`.

## 3. What is wrong on the site now

Measured on the preview (R1) and joined with what the readers return on the kit (`impact.md` §1; the verifier re-checked §1.1 and the Organization Days on the 14:39 build).

| what | count | where |
|---|---|---|
| Session-day pages missing the Journal's part. "How the Day Began" has only the presiding line; there is no Assembled time, no "Excused for the Day", and 0 "Spoke for" / "Spoke against" | **11** | `/session/H/2010-01-06`, `-02-10`, `-03-10`, `-03-11`, `-03-24`, `-05-12`, `-05-13`, `-05-19`, `-06-02`; `/session/H/1999-10-28`, `/session/H/1999-11-03` |
| …of which a no-bill vote is drawn without the Journal's words | 3 | 2010-01-06, 05-12, 06-02 |
| Votes-not-on-a-bill page with rows lacking the Journal's words | **1** page, 5 rows | `/session/nobill/2009-2010` ("Votes 18 / In the Journal's Words 9"): RC 3, 201 and 239, plus RC 240 (HA 3, the address for Philip Cross's removal) and RC 241 (HA 2, Lucinda Sadler's), both shown as "Misc vote" and linked with no anchor |
| Term data files with day records lacking the leave list (`"excused": null`) and the summary's closing sentence | **2** | `/session/H/2009-2010.json` (9 days), `/session/H/1999-2000.json` (2 days) |
| `/data/rollcalls.csv` rows whose `outcome_source` is "rule" where the Journal would decide. `passed` is right in every one | **6** | 2010 House RC 3, 68, 201, 239, 240, 241 |

**Quoted, `/session/H/2010-03-11` (re-read 19:20 UTC):**

> How the Day Began — Presiding over the House during the day: Rep. Terie Norelli (D - Rock 26), Speaker of the House, and Rep. Sherman Packard (R - Rock 3).

**Compare `/session/H/2010-03-17`, whose issue is in the kit:** "The House assembled at 2:00 PM, a prayer was offered …", "Show the 44 members excused", 12 Spoke for, 11 Spoke against.

**Cause.**
- **The nine 2010 pages** have no issue in the kit: the copies, or the special session's HJ001, took their paths.
- **The two 1999 pages** have their issues in `journals/2000/`, where `read_day` does not look.

**What the manager asked about and is not wrong:**
- **Counts "of the 2010 session":** by-the-numbers, the About figures, search and the session indexes do not read journals.
- **Journal excerpts on bills:** no bill page before 2025 carries Journal text. `/bill/2009/hb134` ("Not introduced", from the hand-made `INTRODUCTION_FROM_JOURNAL`) and `/bill/2011/hb134` are both right; 2011's HB 134 reaches no 2009–2010 page.
- **The twelve 2011 session days the copies print:** all have an opening, an Assembled time and leave lists of 10–31.
- **Journal links:** they are built only from 2025 on.

## 4. What changes after the move

Run with the repository's readers on a scratch copy with the moves applied (`impact.md` §4; `im_days_after.jsonl`, `im_pairs.txt`).

| action | visible change | unchanged |
|---|---|---|
| delete the 12 copies | none predicted on any HTML page. Behind them: `read_year("2010")` stops returning 12 dates of 2011; `house_reported` loses the 2011 reports; RC 67 is unpaired (the docket still decides it) | the nine 2010 pages and the 5 no-bill rows, whose issues are still missing |
| move the Organization Day to 2011 | **`/session/H/2010-12-01` loses "How the Day Began / A prayer was offered."**: `read_day` returns `files: []`. `/officers.json` cites `journals/2011/` | `_journal_day` gives the same result from either folder |
| …with `read_day` given the December rule first | 2010-12-01 keeps its opening, and **13 other House Organization Day pages (1998–2024) gain one**, with a leave list where the Journal prints it. Verified for 2022-12-07 (6 excused) and 2024-12-04 (10 excused); the other eleven were not run | — |
| move 2000/HJ025 to 1999 | **`/session/H/1999-10-28` gains** an Assembled time, the opening (prayer, Pledge), "Excused for the Day" (16 names) and 7 speech records | outcomes, the CSV, the no-bill page |
| move 2000/HJ026 to 1999 | **`/session/H/1999-11-03` gains** the same: 33 names, 21 speech records. Its vote placement now runs against the Journal; any change from that was **not measured** | — |

**The owner's decision on order.** `read_day`'s December rule is a code change on dev that reaches the site only through `main`.
- **Either land it first** (recommended: the move then costs nothing and 13 pages gain),
- **or move first and accept** that `/session/H/2010-12-01` loses one line until it lands.

**What the move does not fix:**
- The nine 2010 issues are still not in the kit. They need a fetch, which is a person's decision, one at a time and outside the night window.
- They also need names that cannot collide. `_local` (`fetch_calendar_archive.py:231-247`) would put them back on `journals\2010\HJ0NN.pdf`, and their queue rows are already "held" with no `fetched`.
- Their queue names are "Daily Journal No 01 1-6-10", "No 06 2-10-10", "No 09 3-10-10", "No 10 3-11-10", "No 13 3-24-10", "No 18 5-12-10", "No 19 5-13-10", "No 20 5-19-10" and "No 21 6-2-10", each "Final.pdf" under `journals\2010\`.
- `code_map.md` §1.2 lists 74 journal paths that two queue rows share, from 1997 to 2021. Only 2000 and 2010 were checked against printed dates.

## 5. The check that stops it recurring (designed, not written)

**Where it lives.**
- **Code:** a small module, `src/checks/journal_folders.py`, with a CLI. Running `python3 src/checks/journal_folders.py` prints the table.
- **Data check:** one in preflight, `@check("data", "every journal file is in its session's folder, and no two are the same bytes")`.
  - It runs wherever the kit is on disk: the laptop, and GitHub's machine after `kit-down`.
  - Where there is no `journals/`, it returns `"skip", "no journals/ or journals_senate/ here"`.
  - Add it to `RECORD_CHECKS` (`preflight.py:109782+`), so that on a real night it **warns** rather than holding the site, as the other checks against the record do. A dry run is then not clean.
- **Order.** Land it after the bucket move. Or land it with `expect_fail="the kit's 15 misfiled House journals not yet moved (wf20)"`: it then fails as expected until the move, and the first run after the move tells whoever runs it to take the mark off.
- **Its own reader.** It must not reuse `journal_days.day_blocks`. `DAY_HEADER` (`journal_days.py:126-128`, `^[ \t]*HOUSE…`) misses a heading after a form feed, which hides 10 sittings in the kit, among them 2000/HJ027's No. 1. A check written apart from the reader is the project's rule for exactly this.

**What it reads from each file (strong evidence, in this order).**

1. **House: its own sittings.** Each `HOUSE JOURNAL No. N` heading, with `\f` allowed before it and "No." or "NO." in either case. Skip continuations: "(cont.)", "(Cont'd)", and any other form the kit prints, read from the kit before writing the pattern. Take the dateline within the next few lines; it may be in parentheses, as in 2001/HJ022 l.1006.
2. **House: the issue line**, `Vol. NN Concord, N.H. <Weekday>, <Month> <d>, <yyyy> No. NN`. Its date counts **only when a weekday is printed**: 2003/HJ023's issue line has none, and its date is 2004 for a 2003-series issue.
3. **Senate: the dates of each "The Senate met" sitting**, and the `COMMENCEMENT -` / `ORGANIZATION DAY -` headings, never `ADJOURNMENT -`.

**The rule.**
- Map each strong date to its series: **`year + 1` if the month is December and the year is even (the Organization Day), otherwise the year itself.**
  - Odd-year December sittings stay (2001/HJ022, 2025/HJ 19).
  - Do **not** reuse `session_days.journal_series`. It moves every December forward, including those two, which is a separate bug. `doubtful()` groups citations by it.
- **A file's strong dates must all map to one series, and that series must be its folder.**
- **A file with no strong date falls back to weak evidence:** the masthead "Calendar and Journal of the YYYY Session", the running heads ("7MARCH2018HOUSERECORD", "SENATE JOURNAL 9 FEBRUARY 2006"), and the Senate's date at the top of the issue.
  - Weak evidence must agree with the folder.
  - It is never used against strong evidence. Masthead and running heads are misprinted in 7 files: 1998/HJ004, 1999/HJ001, 2000/HJ027, 2019/HJ004, and Senate 2005/SJ 9, 2007/SJ 14 and the 2011 and 2025 inauguration-day issues.
- **A file with no date at all fails, by name.** It is never passed in silence.
- **Never read** the "Vol." number (2006/HJ004 l.6 prints "Vol. 27" among Vol. 28s) or "First/Second Year of the NNNth" (misprinted in 1999/HJ001 and 2000/HJ027).
- **Carry the two non-journals as a named list with the reason:** `journals/2003/HB1_FinanceAmended.txt` and `HB1_Floor_Amendment.txt`. The check fails if a named one is no longer there.
- **A second rule: no two files under `journals/` and `journals_senate/` may have the same sha256.** Today this finds exactly the 12 pairs.
- **Silence guard:** it fails if either chamber has no files, or if fewer than 90% are dated by strong evidence. Today, measured, 1,028 of 1,064 are, about 96.6%.

**How it names a misfiled file.** One line each:
- `journals/2010/HJ010.txt: in 2010, prints the 2011 series: its own sitting HOUSE JOURNAL No. 10 of Tuesday, March 15, 2011 (line 17) and its issue of March 15, 2011 (line 8). Belongs in journals/2011/, where HJ010.txt is the same bytes: this copy goes.`
- The tail of the line varies: "nothing of that name there", "a different file of that name is there: look", "spans two sessions: …", or "no date read".
- **The OK line gives the counts:** files per chamber, how many were dated strongly, how many weakly, how many named non-journals, and that there are no duplicates.

**Measured against today's kit.** `kit_table.md`'s `scripts/check_rule.py` is the strong rule as stated. It flags **exactly the 15 files, and nothing else among the 1,064**, and it reads no strong date from 36 files. The verifier's independent classifier (`vf/vclass.tsv`) agrees.

**The code-tier fixture test**, in a code group, in a temp folder:
- The fixture lines must be **quoted from the kit's real files**, each with its source file and line, not typed from a description.
- It calls `journal_folders.audit(tmp)`.

The fixtures that **must pass**:
- an Organization Day in the next year (the 1 Dec 2010 lines, under `journals/2011/`);
- 2025/HJ 19 and 2001/HJ022, the odd-year Decembers, in their own years;
- 2003/HJ023: "(cont.)" only, an issue line with no weekday dated 2004, masthead 2003, so dated weakly;
- 2000/HJ027: misprinted masthead, a "(cont.)" of 3 Nov 1999, then `\fHOUSE JOURNAL No. 1` / "Wednesday, January 5, 2000". The test asserts the evidence names No. 1 at its line, which proves the form feed is read;
- 2020/HJ001's "NO. 23 (Cont'd)" then "NO. 1";
- 2006/HJ004's Vol. misprint;
- 1998/HJ004's masthead misprint;
- the Senate's "SJ 01 December 4, 2024 Organization Day" in 2025;
- 2005/SJ 9 with a 2004 running head and "COMMENCEMENT - MARCH 17, 2005 SESSION";
- a named HB 1 text.

The fixtures that **must fail**, each with the message's path, series, target and collision state asserted:
- the Organization Day text under `journals/2010/` ("nothing of that name there");
- identical bytes in 2010 and 2011 (flagged as misfiled and as a duplicate: "same bytes there");
- 2000/HJ025's lines under 2000 (belongs in 1999);
- a Senate Organization Day under 2024;
- a file with no date;
- a file with sittings of June 2010 and February 2011 ("spans two sessions");
- a tree where nothing dates (the 90% floor).

An empty tree must give the skip.

## 6. The owner's steps, on the laptop

**What `cloud.py` can and cannot do here.**
- **`seed-kit` sends new and changed laptop files, and never removes.** It lists "in the bucket's kit and not here; left as they are" (`src/ops/cloud.py:1432, 1441`), and its manifest write passes no removals (`write_manifest(…, {**have, **sent}, [], …)`).
- **`kit-up` removes only the night's own files** gone since `kit-down` (`cloud.py:1731-1734`, `owner_of(kit, r) == "night"`).
- **`kit-release` removes only a held run's files.**
- **`send-night` sends only the caption results** (`cloud.py:3641-3645`).

**What this means for the night.**
- **`kit-down` takes exactly what `state/kit-manifest.json` lists** (`cloud.py:1471`, `want = man["files"]`).
- **After a laptop move and `seed-kit`, every night would hold both copies.** The 15 old keys stay in the manifest, so the night takes them down beside the new ones.
- **Deleting only the objects would break the night.** `kit-down` would then stop with "THE KIT IS SHORT".

**The script.** The old keys must leave the manifest and the bucket together. The script `/tmp/claude-0/audit/wf20/wf20_remove_keys.py` (124 lines) does this as `kit-up` does for a night's file, using `cloud.py`'s own pieces.
- **What it does, in order:**
  1. It writes the merged manifest without the 15 (`cloud.write_manifest`, which keeps the old manifest under `replaced/`) first, so a `kit-down` never meets an entry without an object.
  2. Then, for each object, it copies it to `replaced/<day>/kit/…` (`cloud.Replacer`, kept 30 days) and deletes it.
  3. Finally it reads both back.
- **What it refuses:**
  - inside the night window or before the night has reported (`send_night_late` and `night_unfinished`, the guards `send-night` uses);
  - while any old `.txt` or its `.pdf` is still on the laptop;
  - unless each new path is already in `kit/` and the manifest with the same sha256.
- **Run again, it finishes what an interrupted run left.**
- **Tested against a folder bucket only, never R2** (`wf20_test_bucket.py` builds one):
  - the dry run;
  - the real run: 15 removed, 16 copies under `replaced/`, read back clean;
  - a second run: nothing to do;
  - the refusals: new path missing, bytes differ, an old PDF on disk, inside the window (`GRANITE_CLOCK_UTC`), and after the window with no verdict;
  - an interrupted run.
- **Copy it to the laptop with an editor**, not a heredoc, which eats backslashes (CLAUDE.md), as `%USERPROFILE%\wf20_remove_keys.py`.

**The longer-term choice** is a `seed-kit --prune GLOB…` in `cloud.py` that does the same with a preflight check. That is a code change, and the owner's call; this one-off does not need it.

**When.**
- **Not inside GitHub's night window: 08:00–13:30 UTC every day, and Mondays also 04:00–06:30 UTC** (`refusal.NIGHT_WINDOWS`).
  - Until Saturday 31 October (EDT): 4:00–9:30 a.m. Eastern, and on Monday also midnight–2:30 a.m.
  - From Sunday 1 November (EST): 3:00–8:30 a.m., and Sunday 11 p.m.–Monday 1:30 a.m.
- **Not until that morning's night has sent its verdict**, or 18:30 UTC has passed. Its job may run 300 minutes from a late start.
- **Why the timing matters:**
  - A `kit-down` reads the manifest once and then fetches every key it lists. A key removed between the two makes the night stop short.
  - The manifest is read, merged and written, so two writers at once could drop each other's entries. That is from reading the code, not tested.
- **In practice:** the afternoon or evening, Eastern time.
- `seed-kit` has no window guard of its own, so step 1 is the timing check.
- **The stand-down:**
  - The laptop has stood down from the nightly (`nightly.py:1434`): do not run `nightly.py` or a publishing build there.
  - `cloud.py` and the script are the laptop's to run.
  - Nothing here asks the General Court, so `refusal.check()` and the fetch lane are not involved.
  - Do not run `extract_calendar_text.py` between steps 3 and 6.

**Steps.** All are run from the repository root on the laptop, in PowerShell.

0. **Decide the order with `read_day`'s December rule (§4).** It is best on `main` first.

1. **Is it a good time?** This must print "clear".
   ```
   python3 $env:USERPROFILE\wf20_remove_keys.py --when
   ```

2. **Baseline.** Run the following and note its "to send" list (it should name no `journals/` path) and the count on "in the bucket's kit and not here".
   ```
   python3 src/ops/cloud.py seed-kit --dry-run
   ```

3. **On disk.** Check, then move.
   ```powershell
   $n = '006','009','010','013','018','019','020','021','022','023','024','025'
   # a) the 12 are the 2011 files, text and PDF: prints nothing when they are
   foreach ($i in $n) { foreach ($x in 'txt','pdf') {
     $a = "journals\2010\HJ$i.$x"; $b = "journals\2011\HJ$i.$x"
     if (-not (Test-Path -LiteralPath $a)) { "NOT HERE $a" }
     elseif (-not (Test-Path -LiteralPath $b)) { "NO 2011 COPY $b" }
     elseif ((Get-FileHash -LiteralPath $a).Hash -ne (Get-FileHash -LiteralPath $b).Hash) { "DIFFERS $a" } } }
   # b) nothing waits at the new paths: prints nothing when free
   $org = 'Daily Journal #1, 12-1-10, Organization Day Final'
   "journals\2011\$org.txt","journals\2011\$org.pdf","journals\1999\HJ025.txt","journals\1999\HJ025.pdf","journals\1999\HJ026.txt","journals\1999\HJ026.pdf" |
     ForEach-Object { if (Test-Path -LiteralPath $_) { "TAKEN $_" } }
   ```
   If either check prints anything, **stop** and look. A missing 2011 PDF would mean keeping that 2010 PDF, moved to the 2011 name; it is not expected, since the queue records them all as held.
   ```powershell
   # c) set the 12 copies aside OUTSIDE the repository (not under journals\, whose */*.txt the kit globs)
   $aside = "$env:USERPROFILE\granite-wf20-set-aside\journals\2010"
   New-Item -ItemType Directory -Force -Path $aside | Out-Null
   foreach ($i in $n) { Move-Item -LiteralPath "journals\2010\HJ$i.txt","journals\2010\HJ$i.pdf" -Destination $aside }
   # d) the three moves (Move-Item without -Force refuses to overwrite)
   Move-Item -LiteralPath "journals\2010\$org.txt","journals\2010\$org.pdf" -Destination journals\2011\
   Move-Item -LiteralPath journals\2000\HJ025.txt,journals\2000\HJ025.pdf,journals\2000\HJ026.txt,journals\2000\HJ026.pdf -Destination journals\1999\
   ```
   An error naming a `.pdf` that is not there is harmless. **One naming a `.txt` is not: stop.**

4. **Send the three new paths, and nothing else.** The dry run should show "to send: 3 files", and the "not here" count up by 15 on the baseline. Then send.
   ```
   python3 src/ops/cloud.py seed-kit --dry-run --only "journals/1999/HJ025.txt" "journals/1999/HJ026.txt" "journals/2011/Daily Journal #1, 12-1-10, Organization Day Final.txt"
   python3 src/ops/cloud.py seed-kit --only "journals/1999/HJ025.txt" "journals/1999/HJ026.txt" "journals/2011/Daily Journal #1, 12-1-10, Organization Day Final.txt"
   ```
   `--only` keeps any other pending laptop change out of this send.

5. **Remove the 15 old keys.**
   ```
   python3 $env:USERPROFILE\wf20_remove_keys.py --dry-run
   python3 $env:USERPROFILE\wf20_remove_keys.py
   ```
   - **The dry run must say** "15 of 15 old keys to remove" and print no "would refuse now".
   - **The real run must end with** "removed 15 keys; 16 copies kept under replaced/<day>/" and "read back: no old path in kit/ or its manifest; every new path in both".

6. **Check afterwards.**
   - Running `python3 $env:USERPROFILE\wf20_remove_keys.py --dry-run` should give "0 of 15 old keys to remove".
   - Running `python3 src/ops/cloud.py seed-kit --dry-run` should show the "not here" count back to the baseline, and nothing under `journals/` to send.
   - **After the next night** (or a dry run, on the preview):
     - `/session/H/1999-10-28` and `/session/H/1999-11-03` show "Excused for the Day" (16 and 33 names) and an Assembled time.
     - `/officers.json` cites `journals/2011/Daily Journal #1…`.
     - `/session/H/2010-12-01` keeps "A prayer was offered." only if `read_day`'s December rule is on `main`.
     - The nine 2010 pages are unchanged, as expected.
   - The laptop's next `cloud.py backup` moves the old paths' backup copies to `replaced/` and sends the new ones. Run `--dry-run` first; it should be well inside its removal cap.

7. **To undo** within 30 days: the old objects and the old manifest are under `replaced/<day>/`, and the 12 laptop copies are in `%USERPROFILE%\granite-wf20-set-aside\`.

## Open, and what is a guess

- **Not measured:**
  - whether any `journal_motions` passage is quoted from the three moved files, which would lose its link;
  - vote placement on the two 1999 days once `_journal_day` finds them;
  - `journal_division_words` on 2010 CACR divisions;
  - the eleven Organization Days other than 2010, 2022 and 2024 under a December rule.
- **Not known from the kit:**
  - how many House issues the 2010 session had after No. 17;
  - why 2010-05-21 and 2010-10-13 have no issue in the General Court's 2010 index;
  - whether the other 60-odd colliding queue paths lost a distinct issue. Two are worth checking first: `journals\1999\HJ001.pdf`, where "HJ No 01 01-06-1999" was never fetched, and Senate 2018's Verbatim editions.
- **Separate bugs found on the way, not caused by the misfiling:**
  - `read_day` has no December rule;
  - `DAY_HEADER` misses form-feed headings (10 sittings 1997–2006, among them `/session/H/2000-01-05` and `2000-02-03`);
  - `journal_series` moves odd-year Decembers forward;
  - `/session/nobill/1999-2000`'s RC 189 row (5 Jan 2000) is unplaced because `journal_links` pairs a 1999-file roll call only with `journals/1999/`. Copying HJ027 into 1999 would pair it; that is a judgement for the owner, and not part of this fix.

## Files (all under /tmp/claude-0/audit/wf20/)

- **This report:** not on disk; the harness refused it.
- **The removal script:** `wf20_remove_keys.py`, with `wf20_test_bucket.py` for a folder-bucket test.
- **The source notes:** `kit_table.md`, `code_map.md`, `impact.md`, `vf/verify_moves.md`, and their scripts and tables (`scripts/`, `cm_*`, `im_*`, `vf/`).
- **Deleted:** every download, the kit files and queue.csv. `git status` in the repository is clean.