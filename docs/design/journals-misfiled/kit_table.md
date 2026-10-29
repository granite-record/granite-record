# The kit's journals, every file, read against its folder (wf20, 29 Oct 2026)

Read-only. Source: the private R2 bucket, `kit/journals/` and `kit/journals_senate/`, listed and
downloaded on 29 Oct 2026. Repository at `cfbee9f` (dev, R1). **1,064 files read in all: 573 House
(30 year folders, 1997–2026) and 491 Senate (24 year folders, 2003–2026), 247.6 MB.** Every file was
opened. For each one I took the dates it prints: the House masthead (`Calendar and Journal of the
YYYY Session`), the issue line (`Vol. NN Concord, N.H. <weekday>, <date> No. NN`), every
`HOUSE JOURNAL No. N` heading with its dateline (continuation or not), the running heads
(`7MARCH2018HOUSERECORD`); for the Senate the `COMMENCEMENT -` / `ORGANIZATION DAY -` /
`ADJOURNMENT -` headings, every `The Senate met` sitting, the running heads
(`SENATE JOURNAL 9 FEBRUARY 2006`) and the date at the top right of the issue. Every file was
also hashed (sha256) to find duplicates. Scripts: `/tmp/claude-0/audit/wf20/scripts/`
(`extract.py`, `classify.py`, `strict.py`, `strict_s.py`, `ffcount.py`). Per-file results:
`extract.json` and `classify.txt` in the same folder.

## The folder convention (from the code, then checked against the kit)

* `src/pages/session_days.py:3748-3752`, `journal_series`: *"The year whose journal numbering a
  sitting's date belongs to. Numbers restart each session, and the December organization day
  opens the NEXT year's: journals/2023/HJ 01 December 7, 2022.txt."*
* `src/parse/journal_days.py:1334-1347`, `read_senate_day`: *"A December organization day opens the
  next year's journal (journals_senate/2025/SJ 01 December 4, 2024 Organization Day.txt), so both
  folders are read."*
* `src/pages/session_days.py:2133-2134`, `_journal_day`: reads folder `date[:4]`, and also
  `date[:4]+1` when the month is December.
* `src/fetch/gc_web/fetch_journals.py:51-58`: the folder is the General Court's own year
  (`/house/calendars_journals/Journals/2026/HJ 07 March 11, 2026.PDF`).

So: **a folder holds one session's numbered series — the sittings of that calendar year, plus the
Organization Day of the December before (which is that series' No. 1).** Two files in the kit show
that the series, not the calendar, is the rule, and both are correctly filed:
`journals/2025/HJ 19 December 17, 2025.txt` (l.5 "Calendar and Journal of the 2025 Session", l.18
"HOUSE JOURNAL NO. 19", l.20 "Wednesday, December 17, 2025": a December sitting of an *odd* year,
which stays in its own year), and `journals/2003/HJ023.txt` — l.4 "Calendar and Journal of the 2003
Session", l.6 "Vol. 25 Concord N.H. January 7, 2004 No. 74", l.8 "HOUSE JOURNAL No. 23 (cont.)",
l.75-76 "The Speaker called the recessed session of September 4, 2003 to order at 10:00 a.m. on
Wednesday, January 7, 2004", l.1827 "Rep. Hess moved that the 2003 session of the New Hampshire
House of Representatives adjourn." — a 2003-series journal whose only sitting is dated 2004.

The kit itself confirms it: **every** Organization Day in the kit is in the next year's folder —
House 1996 (in 1997), 1998, 2000, 2002, 2004, 2006, 2008, 2012, 2014, 2016, 2018, 2020, 2022, 2024;
Senate 2004, 2006, 2008, 2010, 2012, 2014, 2016, 2018, 2020, 2022, 2024 — **except the House's of
1 December 2010, which is in `journals/2010/`.**

## The misfiled files: 15, all House

The rule that decides it is the issue line plus the sittings' own datelines (below, under "a
check"). Line numbers are the raw file's (`grep -n`), white space collapsed in the quotes.

| # | folder | file | bytes | what it prints (quoted, line) | belongs in | same name there? | what that is |
|---|---|---|---|---|---|---|---|
| 1 | journals/2010 | `Daily Journal #1, 12-1-10, Organization Day Final.txt` | 45,088 | l.4 "Calendar and Journal of the 2011 Session"; l.6 "Vol. 33 Concord, N.H. Wednesday, December 1, 2010 No. 5"; l.8 "HOUSE JOURNAL No. 1" / "Wednesday, December 1, 2010" — the Organization Day of the 162nd General Court | journals/2011 | **no** (2011 has no HJ001 and no Org Day under any name) | — move it |
| 2 | journals/2010 | `HJ006.txt` | 190,031 | l.4 "Calendar and Journal of the 2011 Session"; l.6 "Vol. 33 Concord, N. H. Tuesday, February 15, 2011 No. 17"; l.15 "HOUSE JOURNAL No. 6" (15 Feb 2011) | journals/2011 | **yes**, `2011/HJ006.txt` | **byte-identical duplicate** (sha256 983330edf2d90c38…) |
| 3 | journals/2010 | `HJ009.txt` | 108,669 | l.6 "…2011 Session"; l.8 "Vol. 33 … Wednesday, March 2, 2011 No. 25"; l.17 "HOUSE JOURNAL No. 9" | journals/2011 | yes, `2011/HJ009.txt` | byte-identical (dff8ecaee2c00341…) |
| 4 | journals/2010 | `HJ010.txt` | 613,580 | l.6 "…2011 Session"; l.8 "Vol. 33 … Tuesday, March 15, 2011 No. 26"; l.17 "HOUSE JOURNAL No. 10". Holds HB 134 (l.4297 "HB 134, relative to eligibility for walking disability plates") — the Clerks' example | journals/2011 | yes, `2011/HJ010.txt` | byte-identical (7119d1fea9e4080a…) |
| 5 | journals/2010 | `HJ013.txt` | 523,764 | l.6 "…2011 Session"; l.8 "Vol. 33 … Wednesday, March 30, 2011 No. 34"; l.18 "HOUSE JOURNAL No. 13" | journals/2011 | yes, `2011/HJ013.txt` | byte-identical (a6ac144c50c38761…) |
| 6 | journals/2010 | `HJ018.txt` | 189,347 | l.6 "…2011 Session"; l.8 "Vol. 33 … Wednesday, May 18, 2011 No. 44"; l.18 "HOUSE JOURNAL No. 18" | journals/2011 | yes, `2011/HJ018.txt` | byte-identical (db35ffe336cdb4ff…) |
| 7 | journals/2010 | `HJ019.txt` | 157,827 | l.8 "Vol. 33 … Wednesday, May 25, 2011 No. 46"; l.17 "HOUSE JOURNAL No. 19" | journals/2011 | yes | byte-identical (672d5be4129a7695…) |
| 8 | journals/2010 | `HJ020.txt` | 253,042 | l.8 "Vol. 33 … Wednesday, June 1, 2011 No. 48"; l.17 "HOUSE JOURNAL No. 20" | journals/2011 | yes | byte-identical (cac5496bfe3c5923…) |
| 9 | journals/2010 | `HJ021.txt` | 153,071 | l.8 "Vol. 33 … Wednesday, June 8, 2011 No. 51"; l.17 "HOUSE JOURNAL No. 21" | journals/2011 | yes | byte-identical (f09eed52c8345cdf…) |
| 10 | journals/2010 | `HJ022.txt` | 272,334 | l.8 "Vol. 33 … Wednesday, June 22, 2011 No. 57"; l.17 "HOUSE JOURNAL No. 22" | journals/2011 | yes | byte-identical (16763ba518d775ad…) |
| 11 | journals/2010 | `HJ023.txt` | 62,679 | l.8 "Vol. 33 … Wednesday, September 14, 2011 No. 64"; l.17 "HOUSE JOURNAL No. 23" | journals/2011 | yes | byte-identical (718765ac346ca31a…) |
| 12 | journals/2010 | `HJ024.txt` | 188,272 | l.8 "Vol. 33 … Wednesday, October 12, 2011 No. 68"; l.17 "HOUSE JOURNAL No. 24" | journals/2011 | yes | byte-identical (a2d863618bcf76a9…) |
| 13 | journals/2010 | `HJ025.txt` | 145,235 | l.8 "Vol. 33 … Wednesday, November 30, 2011 No. 76"; l.17 "HOUSE JOURNAL No. 25" | journals/2011 | yes | byte-identical (8970f93d213ad9f6…) |
| 14 | journals/2000 | `HJ025.txt` | 37,393 | l.6 "Calendar and Journal of the 1999 Session"; l.8 "Vol. 21 Concord N.H. Thursday, October 28, 1999 No. 89"; l.10 "HOUSE JOURNAL No. 25 (cont.)" (1 July 1999); l.135 "HOUSE JOURNAL No. 26" (28 Oct 1999) | journals/1999 | **no** (1999 holds HJ001, HJ003–HJ012, HJ014–HJ024) | — move it |
| 15 | journals/2000 | `HJ026.txt` | 195,928 | l.6 "Calendar and Journal of the 1999 Session"; l.8 "Vol. 21 Concord N.H. Wednesday, November 3, 1999 No. 95"; l.10 "HOUSE JOURNAL No. 26 (cont.)" (28 Oct 1999); l.38 "HOUSE JOURNAL No. 27" (3 Nov 1999) | journals/1999 | no | — move it |

The 12 duplicates (rows 2–13) are **the only duplicate files in the whole kit**: a sha256 of all
1,064 files finds no other pair, House or Senate.

## The manager's list, confirmed and corrected

* **journals/2010: confirmed, and it is 13 files, not 12.** The names the manager gives are exactly
  the 13 above (HJ006, HJ009, HJ010, HJ013, HJ018–HJ025 is 12, plus the Daily Journal #1 makes 13).
  Twelve are 2011 issues that are **byte-for-byte copies of the files already in journals/2011**; the
  thirteenth, the Organization Day of 1 December 2010, exists nowhere else in the kit.
* **journals/2000: two of the three, not three.** `HJ025.txt` and `HJ026.txt` are 1999 issues.
  **`2000/HJ027.txt` is correctly filed.** It is the issue of **Wednesday, January 5, 2000**
  (l.8 "Vol. 22 Concord N.H. Wednesday, January 5, 2000 No. 5" — Vol. 22 is the 2000 volume; 1999's
  issues are Vol. 21). Its first 737 lines are the tail of House Journal No. 27 of 3 November 1999
  (l.10 "HOUSE JOURNAL No. 27 (cont.)"), which is what the first issue of every year carries (as
  `2020/HJ001.txt`, `2022/HJ 01 January 5, 2022.txt` and `2014/HJ005.txt` carry the previous
  year's adjournment), and then at **l.738 "HOUSE JOURNAL No. 1" / l.740 "Wednesday, January 5,
  2000" / l.742-745 "This day, January 5, 2000, … the second-year session of the 156th General Court
  … the Speaker convened the 2000 House of Representatives"** — the 2000 session's own No. 1. Its
  masthead is a misprint carried over from 1999: l.3 "First Year of the 156th Session", l.6
  "Calendar and Journal of the 1999 Session". It should stay where it is. (The heading at l.738 opens
  with a form feed, which the repository's reader does not see — see "Other things found", item 1.)
* **No other year is misfiled, House or Senate.** Every Senate file (491) is in its right folder.

## The moves (old key → new key)

All are in the bucket `kit/` prefix. The `.txt` files are the laptop's (`cloud_kit.json:149-151`,
owner "laptop"), with the PDFs beside them on the laptop; the PDFs should move the same way there.

| action | old | new |
|---|---|---|
| move | `kit/journals/2010/Daily Journal #1, 12-1-10, Organization Day Final.txt` | `kit/journals/2011/Daily Journal #1, 12-1-10, Organization Day Final.txt` (renaming it `HJ001.txt` is optional: no collision either way, and the readers glob `*.txt`) |
| delete (identical copy already in 2011) | `kit/journals/2010/HJ006.txt`, `HJ009.txt`, `HJ010.txt`, `HJ013.txt`, `HJ018.txt`, `HJ019.txt`, `HJ020.txt`, `HJ021.txt`, `HJ022.txt`, `HJ023.txt`, `HJ024.txt`, `HJ025.txt` | — (`kit/journals/2011/<same name>` stands; a "move" would overwrite it with the same bytes) |
| move | `kit/journals/2000/HJ025.txt` | `kit/journals/1999/HJ025.txt` |
| move | `kit/journals/2000/HJ026.txt` | `kit/journals/1999/HJ026.txt` |
| leave | `kit/journals/2000/HJ027.txt` | stays (5 Jan 2000 issue) |

**Doing it on the laptop and running `seed-kit` would not remove the wrong keys from R2.**
`cmd_seed_kit` (`src/ops/cloud.py:1432`, `1441-1442`) lists keys "in the bucket's kit and not here;
left as they are" and sends only what is new or changed. So after a laptop-side move, the 14 old
keys would still be in R2 and the night would still build from them; their removal has to be done
explicitly, which is the owner's call. (I read this from the code; I did not run it.)

## What is missing in each affected year

Found by indexing every `HOUSE JOURNAL No. N` heading in all 573 House files (own and "(cont.)"),
so a sitting whose issue is absent still shows up where the next issue prints its tail.

**2010 session (journals/2010, after the 12 duplicates go):** the folder keeps HJ001 (which is
*not* the regular No. 1 but l.3 "2010 SPECIAL SESSION" / l.5 "HOUSE JOURNAL NO. 1" / l.7
"Wednesday, June 9, 2010"), HJ002–HJ005, HJ007, HJ008, HJ011, HJ012, HJ014–HJ017. **The 2010
session's own issues of the misfiled names are nowhere in the kit.** Missing, with what survives:

| 2010 House Journal | sitting | what the kit has of it |
|---|---|---|
| No. 1 | Wed 6 Jan 2010 | only its tail, `2010/HJ002.txt` l.8 "HOUSE JOURNAL No. 1 (cont.)" / l.10 "Wednesday, January 6, 2010" (the name HJ001 is taken by the special session) |
| No. 6 | Wed 10 Feb 2010 | only its tail, `2010/HJ007.txt` l.8 "HOUSE JOURNAL No. 6 (cont.)" / l.10 "Wednesday, February 10, 2010" |
| No. 9 | between 3 and 11 Mar 2010 (date unknown) | nothing at all |
| No. 10 | Thu 11 Mar 2010 (and perhaps the 10th) | only its tail, `2010/HJ011.txt` l.8 "HOUSE JOURNAL No. 10 (cont.)" / l.10 "Thursday, March 11, 2010" |
| No. 13 | Wed 24 Mar 2010 | only its tail, `2010/HJ014.txt` l.8 "HOUSE JOURNAL No. 13 (cont.)" / l.10 "Wednesday, March 24, 2010" |
| No. 18 onward | after Wed 5 May 2010 | nothing: no House sitting of the 2010 regular session after 5 May 2010 is anywhere in the kit, and No. 17's own adjournment tail is absent too. How many there were I cannot tell from the kit; a guess, from the Senate's 2010 folder (`SJ 21 June 2, 2010`, `SJ 22 October 13, 2010 Veto Day`), is a few in May–June and a veto day in October |

**2011 session (journals/2011, after the Org Day moves in):** No. 1 (1 Dec 2010, moved in), Nos.
3–25. Missing: **No. 2, Wed 5 Jan 2011** (the convening day) — only its tail, `2011/HJ003.txt` l.10
"HOUSE JOURNAL No. 2 (cont.)" / "Wednesday, January 5, 2011". Whether anything followed No. 25
(30 Nov 2011) I cannot tell.

**1999 session (journals/1999, after HJ025/HJ026 move in):** Nos. 1 (Org Day, 2 Dec 1998), 4–13,
15–27. Missing: **No. 2 and No. 3** (Jan 1999; No. 3's tail is in `1999/HJ003.txt` l.10 "HOUSE
JOURNAL No. 3 (cont.)" / l.12 "Thursday, January 7, 1999"; of No. 2 nothing) and **No. 14, Thu 15
Apr 1999** (tail only, `1999/HJ014.txt` l.10 / l.12 "Thursday, April 15, 1999"). No collision with
the two files moving in.

**2000 session (journals/2000, after HJ025/HJ026 leave):** No. 1 (5 Jan 2000, in `HJ027.txt`),
Nos. 2–15, 17–20. Missing: **No. 16, Wed 17 May 2000** (tail only, `2000/HJ016.txt` l.10 "HOUSE
JOURNAL No. 16 (cont.)" / l.12 "Wednesday, May 17, 2000"). Nothing after No. 20 (12 July 2000);
whether there was more I cannot tell.

## Printed errors that are NOT misfilings (a check must not trust these)

| file | what is misprinted | why it is filed right |
|---|---|---|
| journals/1998/HJ004.txt | l.4 "Calendar and Journal of the 1997 Session" | l.3 "Second Year of the 155th"; issue "Vol. 20 … Wednesday, February 18, 1998"; sitting No. 5, 18 Feb 1998 |
| journals/1999/HJ001.txt | l.3 "Second Year of the 156th", l.6 "…of the 1998 Session" | the Organization Day of 2 Dec 1998, "Vol. 21" (1999's volume): next year's folder by the convention |
| journals/2000/HJ027.txt | l.3 "First Year of the 156th", l.6 "…of the 1999 Session" | issue of 5 Jan 2000, Vol. 22, opens No. 1 of 2000 (above) |
| journals/2004/HJ012.txt | l.10 "Thursday, April 22, 2005" under "HOUSE JOURNAL No. 12 (cont.)" | 22 April 2005 was a Friday; issue "Thursday, April 29, 2004", masthead 2004, sitting No. 13 of 29 Apr 2004 |
| journals/2019/HJ004.txt | running heads l.137, 277, 415 … "31JANUARY2018HOUSERECORD" (alternating with 2019) | masthead 2019, sittings 3 and 31 Jan 2019 |
| journals_senate/2005/SJ 9.txt | running heads l.75 "SENATE JOURNAL 17 MARCH 2004", l.146 | l.13 "COMMENCEMENT - MARCH 17, 2005 SESSION" (already noted in journal_days.py:1209) |
| journals_senate/2007/SJ 14.txt | running heads l.179 "SENATE JOURNAL 26 APRIL 2006", l.324 | commencement 26 Apr 2007 |
| journals_senate/2011/SJ 02 January 6, 2011 Inauguration Day.txt | l.13 "inauguration day - january 6, 2010 session" | its sitting and running heads are 6 Jan 2011 |
| journals_senate/2025/SJ 03 January 9, 2025 Inauguration Day.txt | l.14 "ADJOURNMENT - CONVENING DAY - JANUARY 8, 2024 SESSION" | l.15 "COMMENCEMENT - INAUGURATION DAY - JANUARY 9, 2025 SESSION" |

## Other things found on the way (for the reader-side work; each shown, not guessed)

1. **The House reader misses a sitting whose heading line opens with a form feed.**
   `journal_days.DAY_HEADER` (`src/parse/journal_days.py:126-128`) is `^[ \t]*HOUSE\s+JOURNAL…`; a
   page break written by pdftotext as `\f` before the heading defeats it. 10 own-sitting headings in
   the kit are behind one: 1997/HJ011 (No. 12, 18 Mar 1997), 1998/HJ012 (No. 13, 14 May 1998),
   1999/HJ014 (No. 15, 22 Apr 1999), 1999/HJ020 (No. 21, 16 Jun 1999), 2000/HJ004 (No. 5, 3 Feb
   2000), 2000/HJ027 (No. 1, 5 Jan 2000), 2001/HJ019 (No. 20, 7 Jun 2001), 2002/HJ003 (No. 4),
   2005/HJ004 (No. 5, 9 Feb 2005), 2006/HJ006 (No. 7, 7 Mar 2006). Run with the repository's own
   code, `journal_days.day_blocks(clean(text))` returns `[]` for 2000/HJ027, 1997/HJ011 and
   2006/HJ006, and `read_year("2000")` on the kit's copy lists no 2000-01-05 and no 2000-02-03.
2. **What the misfiling does to the reader today, shown with the repository's code on the kit's
   copy:** `journal_days.read_year("2010")` returns 26 sittings, 12 of them dated 2011
   (2011-02-15 … 2011-11-30); `read_year("2000")` includes 1999-10-28 and 1999-11-03; and
   `read_day("1999-10-28")` finds no file, because it reads only folder `date[:4]`. `_journal_day`
   (`session_days.py:2133`) has the same rule, so the 28 Oct and 3 Nov 1999 sittings are never
   read for their session-day pages until the two files move.
3. **House `read_day` does not do what `read_senate_day` does for December.**
   `journal_days.read_day` (`journal_days.py:1148-1155`) reads only `read_year(date[:4])`;
   `read_day("2022-12-07")` on the kit finds nothing, because that Org Day is (correctly) in
   journals/2023. Today `read_day("2010-12-01")` finds the 2010 Org Day only *because* it is
   misfiled; after the move it will be lost to `read_day` like every other House Org Day, unless
   `read_day` reads the next year's folder for a December date as `read_senate_day` and
   `_journal_day` do. `build_session_pages.py:3606` calls it for every House date from
   `JOURNAL_FROM`.
4. **`journal_series` puts every December in the next year**, so the one odd-year December House
   sitting in the kit, `journals/2025/HJ 19 December 17, 2025.txt` (House Journal No. 19 of 2025),
   is keyed to series 2026 by `session_days.journal_series` (`session_days.py:3748-3752`), which
   `doubtful()` groups citations by. `_journal_day` still finds it (it reads both years).
5. Not journals, filed in a journal folder: `journals/2003/HB1_FinanceAmended.txt` (1,824,440 B) and
   `journals/2003/HB1_Floor_Amendment.txt` (131,345 B) — l.1-5 "House Finance / April 10, 2003 /
   2003-1268h … Amendment to HB 1-A". Right year; no `HOUSE JOURNAL` heading, so no sitting is read
   from them.

## A check that would have caught it

Measured on all 1,064 files: comparing the folder with **(House) the issue line's date and the
dates of the non-continuation `HOUSE JOURNAL No. N` headings, allowing a form feed before the
heading; (Senate) the dates of the `The Senate met` sittings and the non-`ADJOURNMENT` headings**,
each mapped by the convention (December of an even year → next year, every other date → its own
year), flags **exactly the 15 files above and nothing else**. Adding the masthead or the running
heads as evidence adds 7 false alarms (the misprints in the table above), so they should not be
used. (`scripts/check_rule.py` is the rule exactly as stated; same 15 with or without the Senate's
COMMENCEMENT/ORGANIZATION DAY headings.)

Three cautions for whoever writes it:

* **It cannot date every file, and must say so rather than pass.** The rule reads no date from 36
  files (variant with the Senate headings; 50 without): 21 House files whose issue line has no
  weekday or whose own heading is a continuation (e.g. 1997/HJ001, 2002/HJ001–HJ005, the two 2013
  special-session files, the two 2003 HB 1 amendment texts) and 15 Senate part-files and short
  issues (2003/SJ 19--Pt2, 2007/SJ 24 Long Version Pt 2–6, 2008/SJ 10A, 14A …). I dated every one of
  them from the masthead, the running heads or the date at the top of the issue, and every one
  agrees with its folder; but a check that skips them silently would not have noticed a misfiled one.
* **The calendar rule is wrong for two correctly filed files** (above): 2003/HJ023 (its sitting,
  7 Jan 2004, is in the 2003 series) and 2025/HJ 19 (17 Dec 2025, the 2025 series). The rule passes
  them today only because it reads no date from 2003/HJ023's issue line (no weekday) and maps an
  odd-year December to its own year. A check should therefore key on the series where the file
  states it, or carry these two as named exceptions.
* A second check worth having: no two kit files with the same sha256 under different year folders
  (it finds exactly the 12 pairs).

`scripts/strict.py`, `strict_s.py` and `check_rule.py` hold the code; `classify.txt` and
`extract.json` the per-file evidence. **All 1,064 files were decided**: 1,049 agree with their folder
and 15 do not.

## Per-year inventory

House (files per folder; misfiled in brackets): 1997:16 1998:19 1999:22 **2000:21 (2)** 2001:20
2002:14 2003:22 2004:16 2005:19 2006:17 2007:22 2008:19 2009:21 **2010:26 (13)** 2011:23 2012:24
2013:22 2014:23 2015:20 2016:16 2017:21 2018:20 2019:23 2020:11 2021:11 2022:15 2023:18 2024:17
2025:19 2026:16 — 573.

Senate: 2003:23 2004:19 2005:26 2006:19 2007:33 2008:28 2009:22 2010:23 2011:24 2012:17 2013:19
2014:16 2015:21 2016:21 2017:20 2018:22 2019:23 2020:10 2021:20 2022:14 2023:20 2024:18 2025:18
2026:15 — 491, none misfiled.

Guesses, stated as such: how many House journals the 2010 session had after No. 17, and whether
anything followed 2000's No. 20 or 2011's No. 25, cannot be read from the kit. Whether the General
Court's own 2010 directory serves 2011 PDFs under those names (which would explain byte-identical
copies) is a guess; finding out would mean asking gc.nh.gov, which I did not do.
