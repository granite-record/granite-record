# Code map: what reads `journals/<year>/` and `journals_senate/<year>/`, and what the kit's 2010 and 2000 folders do to it

Repository: /home/user/granite-record at dev `cfbee9f` (R1). Read-only; nothing in the repository, the kit or `corrections/`/`review/` was written. The kit files were read from R2 into `/tmp/claude-0/audit/wf20/cm_dl*` and deleted afterwards. Every script used is in `/tmp/claude-0/audit/wf20/cm_scripts/`. Every number below comes from running the repository's own functions on the kit's files, or from the preview at dry-run.graniterecord.pages.dev. Anything not measured is marked **guess** or **not measured**.

---

## 0. Summary

1. **The 12 files are copies, not moved files.** `journals/2010/HJ006, HJ009, HJ010, HJ013, HJ018–HJ025 .txt` are byte-identical to the files of the same name in `journals/2011/` (sha256 prefixes match, §1.1). So the 2011 session is already complete in `journals/2011/` (apart from HJ 1–2). "Moving" the 12 into 2011 would overwrite identical files. The repair is to **delete** the 12 copies from `journals/2010/`.
2. **The real harm is what the copies took the place of.** The General Court's own index lists both years' issues under its `journals\2010\` folder. `fetch_calendar_archive._local` names a local file by its number alone, so two issues with the same number land on one path. On that path the 2011 issue was fetched, and the 2010 issue never was (§1.2). That leaves **nine 2010 House sittings with no journal in the kit**: 6 Jan, 10 Feb, 10 Mar, 11 Mar, 24 Mar, 12 May, 13 May, 19 May and 2 Jun 2010. HJ 1 of 6 Jan was lost to the June special session's HJ 1; the other eight were lost to 2011 copies. Every reader that goes by printed date then finds nothing for those nine days. This shows on the site (§3):
   - no "How the Day Began" and no "Excused for the Day" on those nine session pages;
   - 101 of the 102 House roll calls on those days are not matched to the Journal;
   - five no-bill House roll calls have no Journal passage, among them the two votes on the removal addresses of 2 June 2010 (HA 2 and HA 3).
3. **The 2011 copies themselves do almost nothing visible.** Most readers take the date from the text printed in the journal, not from the folder:
   - `journal_days.read_day` looks up a 2011 date only in `journals/2011/`.
   - `session_days._journal_day` does the same.
   - `officers`, `build_site_v2.journal_sittings` and `journal_motions`' division readers all date by the printed text.

   The readers that go by the **folder** are where a 2011 issue can be attributed to 2009–2010:
   - `rollcall_outcomes.journal_tallies`/`journal_links`: one 2010 roll call is paired to a 2011 tally.
   - `rollcall_outcomes.journal_divisions` (not measured).
   - `narrative.house_reported`: 2011 committee reports on 329 bill numbers, HB 134 among them, are mixed into the 2009–2010 lookup.
   - preflight's `_introductions_against_journal`.
4. **The three issues in `journals/2000/` belong to 1999.** HJ025 and HJ026 hold sittings of 28 Oct and 3 Nov 1999. HJ027 holds the 3 Nov 1999 sitting recessed to 5 Jan 2000. Every reader keyed on the date's own year looks in `journals/1999/` and misses them. On the site:
   - the 28 Oct and 3 Nov 1999 House pages have no opening and no leave list;
   - 13 House roll calls of 1999 are not matched to the Journal (RC 176–177, 179–187, 189–190).

   HJ027 is a true edge case: it also holds the tally of 2000's RC 2, the same day (§5).
5. **`journal_bills` does not read these folders.** It reads only 2025 onward, plus 2021 for HB 459.
6. **Moving the 2010 Organization Day file to `journals/2011/`, as the repository's convention requires, would cost the site something today.** `journal_days.read_day` has no December rule (§2.1). The 2010-12-01 page would lose "How the Day Began", as the 2022-12-07 and 2024-12-04 House pages already have. `read_day` needs the December rule that `read_senate_day` and `session_days._journal_day` already have, in the same change as the move or before it.

---

## 1. What the folders hold (the evidence the readers act on)

### 1.1 Printed sitting dates, from `journal_days.day_blocks`

Full table: `/tmp/claude-0/audit/wf20/cm_printed_dates.tsv`. Hashes are the first 10 hex characters of the sha256.

| file in kit | printed sitting(s) | sha256 | same bytes as |
|---|---|---|---|
| journals/2010/HJ006.txt | 2011-02-15 | 983330edf2 | journals/2011/HJ006.txt |
| journals/2010/HJ009.txt | 2011-03-02 | dff8ecaee2 | journals/2011/HJ009.txt |
| journals/2010/HJ010.txt | 2011-03-15 | 7119d1fea9 | journals/2011/HJ010.txt |
| journals/2010/HJ013.txt | 2011-03-30 | a6ac144c50 | journals/2011/HJ013.txt |
| journals/2010/HJ018–HJ025.txt | 2011-05-18 … 2011-11-30 | (each) | journals/2011/HJ018–HJ025.txt |
| journals/2010/Daily Journal #1, 12-1-10, Organization Day Final.txt | 2010-12-01 | da9e9e372f | — |
| journals/2010/HJ001.txt | 2010-06-09 (the special session) | 6266222dc6 | — |
| journals/2000/HJ025.txt | 1999-10-28, after a "(cont.)" of 1 Jul 1999 | 681d4b2ccc | — |
| journals/2000/HJ026.txt | 1999-11-03 | 21321fd07a | — |
| journals/2000/HJ027.txt | none: its only block is "HOUSE JOURNAL No. 27 (cont.)", 3 Nov 1999, reconvened 5 Jan 2000 | 4af1fbf118 | — |

Printed mastheads:
- `journals/2010/HJ010.txt` line 8: `Vol. 33 Concord, N. H. Tuesday, March 15, 2011 No. 26`
- `journals/2010/HJ010.txt` line 4297: `HB 134, relative to eligibility for walking disability plates. OUGHT TO PASS WITH`. This is 2011's HB 134, the bill the Clerks found.
- The Organization Day file: `Calendar and Journal of the 2011 Session` / `Vol. 33 … Wednesday, December 1, 2010 No. 5` / `HOUSE JOURNAL No. 1`.
- `journals/2000/HJ025.txt`: `Calendar and Journal of the 1999 Session` / `Vol. 21 … Thursday, October 28, 1999 No. 89`.
- `journals/2000/HJ027.txt`: `Calendar and Journal of the 1999 Session` / `Vol. 22 … Wednesday, January 5, 2000 No. 5` / `HOUSE JOURNAL No. 27 (cont.)` / `Wednesday, November 3, 1999` / "The Speaker called the recessed session of November 3, 1999 to order at 10:30 a.m. on Wednesday, January 5, 2000".

### 1.2 Why: the General Court's index and the local name

`kit/archive/queue.csv` (the drain's own record) lists both years under `year=2010`, `url=…fileName=journals%5C2010%5C…`, and gives both the same local `path`:

```
journals\2010\HJ009.pdf  fetched: "Daily Journal No 09 3-2-11 Final.pdf"   not fetched: "Daily Journal No 09 3-10-10 Final.pdf"
journals\2010\HJ006.pdf  fetched: "Daily Journal No 06 2-15-11 Budget Address Final.pdf"   not fetched: "Daily Journal No 06 2-10-10 Final.pdf"
journals\2010\HJ001.pdf  fetched: "Special Session Journal No 01 6-9-10 Final.pdf"   not fetched: "Daily Journal No 01 1-6-10 Final.pdf"
```

The same holds for HJ010 (3-11-10), HJ013 (3-24-10), HJ018 (5-12-10), HJ019 (5-13-10), HJ020 (5-19-10) and HJ021 (6-2-10). For HJ007, HJ008, HJ011, HJ012 and HJ014–HJ017 the 2010 issue won the path instead. HJ022–HJ025 have only the 2011 name in the 2010 list, so they are extras rather than displacements.

- **The local name.** `src/fetch/gc_web/fetch_calendar_archive.py:231-247` (`_local`) builds `f"{prefix}{int(digits):03d}{suffix}.pdf"` from the document's number. The docstring at line 30 of the same file already says "(year, number) is not a key for anything". Line 40 says "A file already on disk is never asked for again", so the second document of a pair is marked held and never fetched.
- **The full list.** `/tmp/claude-0/audit/wf20/cm_queue_collisions.tsv` holds every journal path that two or more queue rows name: **74**, House and Senate, 1997–2021. Only 2010 and 2000 were checked against printed dates. Whether the second document is a distinct issue in the other 60-odd cases is **not measured**: some are plainly the same file twice ("… (2).pdf").
  - Two worth a look: `journals\1999\HJ001.pdf` holds the 2 Dec 1998 Organization Day, and "HJ No 01 01-06-1999" was never fetched. The kit's 1999 folder has no 6 Jan 1999 sitting, but that was not checked on the site.
  - `journals_senate\2018\SJ001–SJ018` hold the "- Verbatim" editions. Those names lack "erbatim", so the readers' Verbatim skips do not apply.

### 1.3 The repository's convention for a December Organization Day

- `src/pages/session_days.py:3748-3752`, `journal_series`: "the December organization day opens the NEXT year's: journals/2023/HJ 01 December 7, 2022.txt."
- `src/parse/journal_days.py:1338-1340` (`read_senate_day`): "A December organization day opens the next year's journal (journals_senate/2025/SJ 01 December 4, 2024 Organization Day.txt), so both folders are read."
- The kit agrees in every other year that was looked at: 1997, 1999, 2001, 2003 and 2005 HJ001 are each the previous December's Organization Day (queue names "HJ No 01 12-04-1996", "12-02-1998", "12-06-2000", "12-04-2002", "12-01-2004").

So by the code's own convention, the 1 Dec 2010 file belongs in `journals/2011/`. Its masthead says "Calendar and Journal of the 2011 Session", and `journals/2011/` has no HJ001.

---

## 2. Every reader, what it keys on, and what the misfiled files do

"Folder" means the reader opens `journals/<Y>/` for a year it was asked about. "Printed" means it dates each sitting by the dateline printed inside.

### 2.1 `src/parse/journal_days.py`: speeches, openings and leave lists for the session pages

- **Folder, House.** `read_year(year)`, lines 1100-1145, globs `Path(root)/str(year)/*.txt` (line 1113). Inside the folder each sitting is keyed by **printed** date (`day_blocks`, 141-162; `DAY_HEADER` 126; `DATELINE` 130). "(cont.)" blocks are skipped (line 154).
- **House days: the date's own year only.** `read_day(date)`, lines 1148-1155, is `read_year(date[:4], root).get(date, …)` (line 1150). There is **no December rule**.
- **Senate.** `read_senate_year`/`read_senate_day`, 1304-1350. Same keying, but with the December rule at 1343-1344: `for year in dict.fromkeys((date[:4], str(int(date[:4]) + 1) if date[5:7] == "12" else date[:4]))`.
- **Effects:**
  - A 2011 copy in `journals/2010/` lands in `_YEARS[("journals","2010")]` under 2011 dates. `read_day("2011-…")` never reads there, so there is **no effect**.
  - A 2010 sitting whose issue is missing returns an empty record.
  - 1999 sittings in `journals/2000/` are invisible to `read_day("1999-…")`.
  - The 1 Dec 2010 file is **found now**, because it sits in 2010. Moved to `journals/2011/` it would not be found. Tested (`cm_scripts/orgday.py`): with the file in 2010, `read_day('2010-12-01')` gives `files=['Daily Journal #1, …'] opening=['prayer']`. In 2011 it gives `files=[] opening=[]`.
- **Caller.** `src/pages/build_session_pages.py:3602-3606` (`narrative = journal_days.read_senate_day(date)` / `journal_days.read_day(date)`), for every House day from `JOURNAL_FROM = "1997-01-01"` (line 92).
- **`--coverage`** (CLI only, 1378-1412) counts attributions by **folder name** (`years[d.name]`, line 1401). It counts the 12 copies twice, once under 2010.

### 2.2 `src/pages/session_days.py`: the session-day pages' votes, sittings and checks

- **`_journal_day(body, date)`, 2098-2215.**
  - Folder: the date's year, plus the next year in December (lines 2124-2125). It globs `*.txt` (2130) and skips "erbatim".
  - Key: **printed** date (`J.day_blocks` / `J.senate_sittings`, 2138).
  - Returns the roll-call and division counts, bills, `under` and `decided` the Journal prints for that sitting, or **None where no journal on disk opens a sitting that day**.
- **Callers:**
  - `_sat` (2055-2062: "the guard against a roll call the roll-call file misdates making a sitting that never was");
  - `_journal` (2065);
  - `_prints` (2218-2226), used in roll-call placement at 2619-2620 and 3004-3045;
  - `Day.printed` (721, set at 3620), used by `_one_vote` (831-835) to decide whether one count on several bills is one vote;
  - `_journal_checked` (3059);
  - `build_site_v2._sat_by_journal` (7263), used by `adjourned_by` (7370) for the day a tabled bill died.
- **Effects:**
  - 2011 copies: none, because a 2011 date reads only `journals/2011/`.
  - The 1 Dec 2010 file is found in either folder. Tested: `_journal_day('H','2010-12-01')` returns the same result from 2010 and from 2011.
  - **The nine 2010 sittings with no journal, and 28 Oct / 3 Nov 1999, get None**: "no journal on disk". Every rule above then falls back to the docket alone, for example `_one_vote`'s "with no journal on disk, every row cites the same journal page". The page-by-page consequences of that fallback were **not enumerated**.
- **`journal_series` (3748-3752)** reads no folder. It is used by `doubtful()` (3776) on docket citations, and by `queue_links` for 2025 onward only.

### 2.3 `src/parse/rollcall_outcomes.py`: the Journal's outcome for a roll call no docket line names

- `JOURNAL_DIRS = {"H": "journals", "S": "journals_senate"}` (623).
- `journal_files(root, body, year)` (660-667) globs the **folder** `journals/<year>/*.txt`, skips "erbatim", and sorts by `_journal_order` (648-657). That sort takes the number in the **file name**; a special session sorts last only if "SS" is in the name. The 2010 special session is `HJ001.txt`, so it sorts first. Tested: this changes no pairing in 2010.
- `journal_tallies` (683-721) reads every tally in those files in that order.
- `journal_links(rolls, want, root)` (761-796) groups roll calls by `(str(r["year"]), body)` (769). This is **the roll call's year → that folder**. It aligns them in order with the tallies (775), then pairs leftovers on a count found once on each side.
- **Used by:**
  - `outcomes()` at 872 and 910-919, for "the roll calls no docket line names" (`outcome_source = "journal"`);
  - `journal_motions.build` at `src/parse/journal_motions.py:2397`.
- **Measured** (`cm_scripts/pairing.py` and `unpaired.py`, using the repository's `journal_links` on the kit's files and `records/rollcalls/RollCallSummary_2010.txt` / `_1999.txt` / `_2000.txt`):
  - **2010 House: 230 roll calls, 129 paired. The 101 unpaired are exactly the roll calls of the nine sittings with no journal** (table: `/tmp/claude-0/audit/wf20/cm_unpaired_2010.txt`):
    - 6 Jan: 7 of 7
    - 10 Feb: 6 of 7
    - 10 Mar: 11 of 11
    - 11 Mar: 17 of 17
    - 24 Mar: 8 of 8
    - 12 May: 21 of 21
    - 13 May: 10 of 10
    - 19 May: 12 of 12
    - 2 Jun: 9 of 9
    - every other day: 0
  - **The one remaining roll call of those days is paired to a 2011 tally**: `RC 67 2010-02-10 HB1662 243-110 -> HJ021 ['2011-06-08'] carried=True said='and the motion was adopted.'` With the 12 copies removed it is unpaired, and nothing else changes. It names a bill, so whether the docket's outcome overrides it depends on the docket line (**not checked**).
  - **1999 House: 163 roll calls, 145 paired as the kit stands. With HJ025–027 added to `journals/1999/`, 158 are paired.** The 13 gained:
    - RC 176–177 (28 Oct 1999, HB 109);
    - RC 179–187 (3 Nov 1999, HB 999);
    - RC 189 (5 Jan 2000, "HR … ADOPT AMENDMENT TO HOUSE RULE 63");
    - RC 190 (5 Jan 2000, CACR 17).
  - **2000 House: 124 roll calls, 121 paired. One of them, RC 2 (5 Jan 2000, HB 239, 181–167), is paired to `HJ027`.** That issue serves both years (§5).
- **`journal_divisions` / `journal_division_words` (528-550)** use the **folder** `date[:4]`. They are used at `session_days.py:3572` for a CACR division's threshold wording. For a 2010 CACR division, the 2011 copies' divisions are pooled in. A count printed with two different sentences returns "" (the words are lost), and a count only a 2011 copy prints supplies 2011's sentence. **Not measured.**
- **`journal_corrections` (724-735)** covers the Senate only, by folder. Not affected.

### 2.4 `src/parse/journal_motions.py`: votes not on a bill (`journal_motions.json` → `/session/nobill/<term>`, vote_passage, session days)

- **No-bill roll calls** (`read_vote`, 1715-1866) use the `journal_links` pairing above, keyed by the roll call's **folder year**.
  - Gate 2 (1736-1742) holds back any passage whose **printed** page date is not 0–3 days before the roll call. A cross-year pairing would be held back, never shown.
  - A roll call with no pairing counts as "not placed in a Journal" (2416-2418) and gets no passage.
- **Divisions and voice votes only the Journal has**:
  - `journal_only` (1870-2062), `bill_motion_votes` (2211-2275) and the `tied` divisions;
  - **files**: every year folder (2423-2444);
  - **date and term**: from the **printed** running head (`sitting_date`, 513-532; `term = term_of(str(when.year), …)` at 1925, 1999, 2267).

  So a 2011 division read from the copy in `journals/2010/` is correctly dated 2011 and term 2011-2012. It is read twice and kept once (2445-2465, by key or by `(date, body, bill, motion, how, yeas, nays)`). The comment at 2454-2456 already knows: "ONE JOURNAL ON DISK TWICE IS ONE: journals/2010/ holds copies of House Journals of 2011 (HJ 9, 22 and 24 among them)".

  Because `years_read` is sorted (2442), **the copy kept is the `journals/2010/…` one**, so its `"file"` field names the wrong folder. Its `url` (`addresses()`, 1656-1673, `pick … if r.get("fetched")` at 1670) is the queue's fetched row, which is the correct 2011 PDF under the General Court's 2010 folder. No difference was visible on `/session/nobill/2011-2012`.
- **Site effect, measured on the preview:**
  - `/session/nobill/2009-2010` reads "Votes 18 In the Journal’s Words 9". The five 2010 House no-bill roll calls on sittings with no journal are drawn with the roll-call file's words only:
    - RC 3, 6 Jan ("MOTION FOR LATE DRAFTING AND INTRODUCTION (REP W.O'BRIEN)");
    - RC 201, 12 May ("MOTION TO TAKE UP BILLS W/OUT DEBATE…");
    - RC 239, 2 Jun ("RULES SUSPENSION TO ALLOW LATE DRAFING…");
    - **RC 240, 2 Jun ("HA 3: FOR THE REMOVAL OF PHILIP CROSS, MARITAL MASTER … OUGHT NOT TO PASS"), shown as "Misc vote … OUGHT NOT TO PASS"**;
    - **RC 241, 2 Jun ("HA 2: FOR THE REMOVAL OF LUCINDA SADLER, DISTRICT COURT JUDGE … LAY ON TABLE (REP EATON)"), shown as "Misc vote … LAY ON TABLE (REP EATON)"**.

    By contrast, 9 Jun 2010 (HJ001 on disk) reads "Under the Journal’s heading “Motion to Adjourn”".
  - `/session/nobill/1999-2000`: "Jan 5, 2000 | House | The chamber's own rules | In the record: ADOPT AMENDMENT TO HOUSE RULE 63 | 280–57". It is the only row of six that links with no anchor (`session/H/2000-01-05`), and the page reads "Votes 6 In the Journal’s Words 5". That fits RC 189 being unplaced because HJ027 is in `journals/2000/` (an **inference** from the simulation, not traced through the built JSON).

### 2.5 `src/parse/officers.py`: who held the chair (→ `site/officers.json`, the chair labels on session pages)

- `house_mentions` (315-339) and `senate_mentions` (342-366) glob `*/*.txt`, which is **every folder** (320, 346). `mentions` (530-544) does the same.
- Dates come from the **printed** text (`house_blocks`, 298-312); terms from `term_of(iso)` (260), with "Organization Day is the next term's".
- **Effect:**
  - The folder is irrelevant to the dates and terms. The 2011 copies give each 2011 mention twice.
  - `tenures` (437-493) folds an elected officer's repeated mention ("One election read twice"), and an appointed officer's people are kept unique.
  - The `source` text (`_source`, 433-434: `f'{m["cite"]}, …'`) cites the first file sorted, which is the `journals/2010/…` copy. That text is written to `officers.json` (`build_site_v2.py:3519`). Whether `source` is shown on any page was **not checked**.

### 2.6 `src/pages/build_site_v2.py`: when a tabled bill died

- `journal_sittings` (7172-7197) globs **every** year folder, dates by **printed** text, and keys `out[(body, d[:4])]` (7196). It is folder-agnostic.
  - It leaves out special-session journals **by file name** (`SPECIAL_JOURNAL`, 7169). The kit's 2010 special session is named `HJ001.txt`, so it is counted as a regular sitting. 2006's and 2008's HJ001 are special-session files too, by queue name. `with_journals` (7200-7222) then drops days the docket marks as special-session days; whether that covers 9 Jun 2010 was **not checked**.
- `with_journals(chamber_sittings(narratives), journal_sittings())` at 10929.
- `_sat_by_journal` (7263) → `session_days._sat`, as in §2.2.
- **Effect:** the 2011 copies add 2011 dates that 2011's own files already give, so there is no change. The 1999 sittings in `journals/2000/` are still keyed 1999, so there is no change. The nine missing 2010 days only matter here if the docket has no floor row for them (**not measured**; it does have rows, since the session pages exist).

### 2.7 `src/parse/narrative.py`: which House committee reported a bill (stage headings in a bill's history)

- `JOURNALS = Path("journals")` (4808).
- `house_reported(term, bill)` (4831-4847) reads the **folders** of the term's two years, globbing `HJ*.txt` (4839). It keys on the **bill number alone**, with no date.
- It is used once, at 5754: where a House docket row names a committee other than the one holding the bill, and the Journal prints the bill's report for the named committee, the stage is headed with it.
- **Effect, measured** (`cm_scripts/reports.py`, the repository's `journal_reports`): the 12 copies give reports on **329 bill numbers**, and 328 of them add a committee the genuine 2010 files do not. Examples: `HB134 ['Transportation']`, `HB102 ['Commerce and Consumer Affairs']`, `CACR10 ['Ways and Means']`. All of these enter `house_reported("2009-2010", …)`.
- A wrong heading needs a 2009–2010 House row that names another committee to match one of these. **Not measured** (it needs a full `narrative.py` run).
- The Organization Day file does not match `HJ*.txt`, so this reader never sees it in either folder.

### 2.8 `src/parse/journal_bills.py`: withdrawn bills

- `ROOT = Path("journals")` (123). `years()` (689-694) returns only folders `>= FIRST_YEAR = 2025` (125). `read_earlier` covers `EARLIER = {2021: ("HB459",)}` (130).
- The term is `term_of(folder year)` (199-202), so this reader does key on the folder, but only for 2021 and 2025 onward.
- It already has the check the manager proposes, for its own years: `own_year += sum(1 for d in r["sittings"] if d[:4] == str(y))` (721) and "journals/{y} holds {own_year} sittings of {y} and not one introduction was read" (757).
- **Effect: none.** 2000, 2010 and 2011 are never read.
- `introduction_resolutions(root, years)` (1040+) dates each resolution by the **printed** sitting. It is called on the real disk only by preflight (2.10).

### 2.9 Other readers

- **`src/pages/calendar_documents.py`** (the Calendar page's journal picker).
  - It is built from `archive/queue.csv` and links each General Court document by its own address, dated by its own name.
  - For a Senate journal only, it reads the printed date (322-325). A file that two listed documents share is read for neither unless one was fetched (344-358, which already names the collision: "fetch_calendar_archive names the local file by the document's number").
  - **No effect** from the folders.
- **`src/parse/extract_calendar_text.py`** (`ROOTS`, 47) makes the `.txt` beside each PDF in the same path. **`src/checks/archive_status.py:131`** counts files. Neither interprets years.
- **`src/pages/guides.py:1321,1470-1472`** and **`src/pages/legislative_year.py:109`** cite fixed 2022–2025 files by path. Not affected.

### 2.10 Checks that read the real journals (preflight.py)

- `_speakers_against_journal` (95501+): its `blocks(date)` reads `jroot / date[:4]` by printed date, like `read_day`. 2011 is unaffected; 2010's missing days and 1999's misfiled days are not checked.
- `_rail_endings_on_the_site` (96789+, `B.journal_sittings()` at 96888): folder-agnostic.
- **`_introductions_against_journal` (108855+)**:
  - `cache[years] = J.introduction_resolutions(J.ROOT, years)` for both years of a term (108957) is read by **folder**. The main reading filters to the printed year (108962: `x["date"][:4] == str(rec.get("lsr_year"))`).
  - The escape at 108971, `continue  # named by a resolution of the term's other year`, reads the whole unfiltered cache. That includes the 2011 resolutions in the copies, dated 2011 (measured: 2011-03-02 names HB 25, HB 1–2 and HB 651; 2011-09-14 names HB 652–656 and HR 13).
  - So a 2009 number that a 2009 resolution steps over, and that a 2011 copy names, would be excused. **Guess: no case today.** None of those numbers is in `build_data.INTRODUCTION_FROM_JOURNAL`, and HB 134 is not among them.
- `_withdrawn_on_record` (105939+) and `_journal_intros_on_record` (109121+) cover 2025 onward only.

### 2.11 Not readers of the journal folders (checked by grep; no "journal" in the file, or only derived JSON)

`src/hearings/calendar_meetings.py`, `src/pages/about_figures.py`, `src/pages/learn_numbers.py`, `src/pages/build_search_index.py`, `src/hearings/build_floor_index.py`.

`src/pages/build_nobill_votes.py` and `src/pages/vote_passage.py` read `journal_motions.json` only. `build_indexes.py`, `build_calendar.py`, `build_pages.py` and `latest_activity.py` read `session_days.load()`.

So any "count of the 2010 session" on the learn and about pages does not come from the journals. Counts on the session indexes come from the docket through `session_days`.

---

## 3. What is wrong on the site now (preview, R1), and its reader

| page | what it shows | why | reader |
|---|---|---|---|
| `/session/H/2010-01-06`, `-02-10`, `-03-10`, `-03-11`, `-03-24`, `-05-12`, `-05-13`, `-05-19`, `-06-02` | no "Excused for the Day", no "How the Day Began" | the issue is not in the kit (displaced by a 2011 copy, or by the special session's HJ001 on 6 Jan) | journal_days.read_day (2.1) |
| for comparison: `/session/H/2010-01-13`, `-02-17`, `-03-03`, `-03-17` | 24, 23, 29 and 44 members excused, with an opening | the issue is in the kit | same |
| `/session/H/1999-10-28`, `/session/H/1999-11-03` | no leave list, no opening | HJ025/HJ026 are in `journals/2000/` | read_day reads `journals/1999/` |
| `/session/nobill/2009-2010` | 5 House rows from the roll-call file alone, among them the HA 2 and HA 3 removal votes of 2 June 2010 | not placed in a Journal: 101 roll calls of the nine days unpaired | rollcall_outcomes.journal_links → journal_motions (2.3, 2.4) |
| `/session/nobill/1999-2000` | 5 Jan 2000 House Rule 63 vote with no Journal passage | HJ027 is in `journals/2000/` (inference) | same |
| `/session/H/2010-12-01` | "How the Day Began: A prayer was offered." **(correct now)** | the file is in `journals/2010/`, where read_day looks | would be lost by the move unless read_day gains the December rule |
| `/session/H/2022-12-07`, `/session/H/2024-12-04` | no "How the Day Began" | their Organization Day files are in the next year's folder by convention, and read_day has no December rule | an existing gap of the same reader, unrelated to the misfiling |
| 2011 session pages, e.g. `/session/H/2011-03-02` | 31 excused, opening, speeches **(correct)** | read from `journals/2011/HJ009.txt` | — |

Not seen on the site but possible through folder-keyed readers (§2.3, §2.7, §2.10): a 2009–2010 bill's stage headed with a committee that reported the 2011 bill of the same number; a 2010 CACR division's threshold wording from a 2011 sentence; one 2010 roll call (RC 67) paired with a 2011 tally.

---

## 4. The move, old path → new path

All are kit paths. Each is an R2 write, for the owner to run.

**What has to happen on the laptop too (guess, not traced through `cloud.diff`).** `cloud.py seed-kit` (`src/ops/cloud.py:1395-1459`) sends what the laptop holds and leaves alone "in the bucket's kit and not here". A kit-only fix can be undone if the laptop's own `journals/2010/HJ0NN.txt` (and `.pdf`) are re-sent later. So the laptop's files and `archive/queue.csv`'s `path` column need the same change.

| kit path now | action | why |
|---|---|---|
| journals/2010/HJ006.txt, HJ009, HJ010, HJ013, HJ018, HJ019, HJ020, HJ021, HJ022, HJ023, HJ024, HJ025 (.txt) | **delete** (moving onto journals/2011/HJ0NN.txt would overwrite byte-identical files) | 2011 issues; identical copies already in journals/2011/ |
| journals/2010/Daily Journal #1, 12-1-10, Organization Day Final.txt | → journals/2011/ (e.g. `journals/2011/HJ001.txt`; the readers do not care about the name except `narrative.house_reported`, which reads only `HJ*.txt`, and `_journal_order`, which sorts a nameless file last) | the 2011 session's HJ 1 by masthead and by convention (§1.3). **Only after `journal_days.read_day` reads December from the next year's folder** (§2.1); otherwise `/session/H/2010-12-01` loses its opening |
| journals/2000/HJ025.txt | → journals/1999/HJ025.txt (free) | 1999-10-28 sitting |
| journals/2000/HJ026.txt | → journals/1999/HJ026.txt (free) | 1999-11-03 sitting |
| journals/2000/HJ027.txt | → journals/1999/HJ027.txt **is a judgement call** | a 1999-session "(cont.)" that met on 5 Jan 2000. In 1999 it pairs RC 189–190 of RollCallSummary_1999; in 2000 it pairs RC 2 of 2000 (HB 239, 181–167), the same day. Either folder loses one; a copy in both gives each year its own (the readers that date by print would then read it twice, and `journal_motions` keeps one by key) |
| (missing) the 2010 issues "Daily Journal No 01 1-6-10", "No 06 2-10-10", "No 09 3-10-10", "No 10 3-11-10", "No 13 3-24-10", "No 18 5-12-10", "No 19 5-13-10", "No 20 5-19-10", "No 21 6-2-10" | **fetch**: a person's decision (it asks gc.nh.gov), to names that cannot collide | deleting the copies does not bring back 2010's content; only these do |

---

## 5. A check that would stop it recurring

The rule the code already follows:
- A sitting in `journals/<Y>/` or `journals_senate/<Y>/` is printed in **Y**, or it is the **Organization Day of December Y−1**. This is `journal_series`, `read_senate_day` and `_journal_day`'s December rule.
- A December sitting of an even year is **not** in its own year's folder.
- The proven precedent is `journal_bills.read_all`'s `own_year` (journal_bills.py:721/757).

A preflight data check over every `*.txt` would:
1. Date each sitting by `journal_days.day_blocks`, reading the "(cont.)" headings' dates as well, or HJ027 of 2000 gives none. Use `senate_sittings` for the Senate.
2. Fail on any sitting outside {Y, Dec Y−1}. Against today's kit this flags:
   - the 12 copies;
   - the 2010 Organization Day;
   - 2000/HJ025, HJ026 and HJ027.

   The last is a person's call.
3. Fail on any two files under different years with the same bytes. This flags the 12 again, directly.
4. As a separate guard, fail where two `archive/queue.csv` journal rows give one `path`. That is the root cause (`fetch_calendar_archive._local`). Today it flags 74 paths (§1.2), so it needs a list of accepted pairs to start from.

The masthead line "Calendar and Journal of the YYYY Session" is **not** a safe single test. It gives the session year, which is 2011 for the 1 Dec 2010 file but **1998** for `journals/1999/HJ001.txt`, the 2 Dec 1998 Organization Day, which is correctly filed.

---

## 6. What is a guess, or not measured

- Whether the docket names RC 67 of 2010 (and so whether its 2011 Journal pairing changes `passed`).
- How many 2009–2010 bill histories `narrative.house_reported` heads wrongly. The exposure is 329 bill numbers; the hits are unknown.
- `journal_division_words` on 2010 CACR divisions.
- Whether `officers.json`'s `source` is drawn anywhere.
- Whether seed-kit would re-send deleted kit files from the laptop (§4).
- Whether the other ~60 colliding queue paths (§1.2) lost a distinct issue. Two are worth checking first: 1999-01-06 (1999/HJ001) and Senate 2018 (the Verbatim editions stored as SJ001–SJ018).
- That the 1999-2000 no-bill row of 5 Jan 2000 is unplaced *because of* HJ027. This comes from the simulation (RC 189 pairs only when HJ027 is in 1999) and the page's 5-of-6 count, not from reading `journal_motions.json`.

Files kept: this note; `cm_queue_collisions.tsv`, `cm_unpaired_2010.txt`, `cm_unpaired_1999.txt`, `cm_printed_dates.tsv` (tables); `cm_scripts/` (the scripts behind every number).
