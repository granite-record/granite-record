# HB 287 of 2025: the correction for you to check (P14, D23)

**What is wrong.** On /bill/2025/hb287, HB 287's Votes tab shows *"Adopt the Conference Committee Report … Jun 26, 2025 · Senate · Roll Call … 16–8"*. HB 287 is a House bill that the House killed on 20 February 2025, so it never reached the Senate.

The vote belongs to **SB 287** (absentee ballot applications and photo ID). On 26 June 2025 the Senate adopted SB 287's conference report 16–8. The General Court's roll-call file lists that vote, Senate roll call 117 of 2025, under "HB287".

Because of that:
- SB 287's page has no record of its last Senate vote.
- All 24 senators' Votes tabs link HB 287 for this vote, and their date link (`session/S/2025-06-26#HB287`) points at a card that is not on that page.

**What fixes it.** One entry in a new hand-made file, `corrections/rollcall_corrections.json`. The site can read the file from branch `fix/release-xs` onwards (commits `826a8c6` and `f422d48`).

I did not write anything in `corrections/`. You create the file, check it, and commit it. Until you do, nothing changes.

---

## Why a new file, not an entry in an existing one

None of the existing files can move a roll call:

- **`docket_corrections.json`, "misfiled"** moves a *docket row*, the clerk's line on a bill's history (`narrative.py`). Here the docket is right. SB 287's docket records the 16–8, and HB 287's docket has no row for it. The mistake is in the roll-call file, which no hand-made file could correct.
- **`vote_lines.json`** holds the one-line summary of a Misc vote.
- **`member_corrections.json`, "ballots"** fills in a ballot whose member id is empty.

So the branch adds the smallest reader that can do it. `rollcall_parser.roll_call_bill` is the one place a roll call's bill is named, both for `rollcalls.json` (each bill's Votes tab and the session days) and for every member's ballot (`build_data.py`, the members' Votes tabs). It now reads `corrections/rollcall_corrections.json`. Because both read it in the same place, the bill's page and the members' tabs always move together.

One more reader had to follow: the floor-debate index (`build_floor_index.py`, commit `f422d48`). The real build showed that without it, HB 287's Hearings tab kept *"Jun 26, 2025 — HB 287-A - Senate Floor Debate"* (the day's recording, with "Conference Committee Report 16-8"), and SB 287 had no recording for that day. It now asks `roll_call_bill` too.

The rules, the same as for your docket corrections:
- An entry is applied only while the roll-call file still lists the vote under the bill the entry names in `says`.
- If the General Court changes the file, the entry is not applied. `rollcall_parser.py` and `build_data.py` say so in the night's log, and `preflight` fails (`_rollcall_refiled`), because then the entry is what is out of date.
- An entry this cannot read (a bad key, or `says` and `belongs_to` not two different bill numbers) stops the build rather than being skipped.
- Each run's log says what the file did, for example: `rollcall_corrections.json: 2025-S-117 is filed under HB287 in the roll-call file and drawn under SB287`.

---

## 1. The file: create `corrections/rollcall_corrections.json` with exactly this

The same text is beside this note, `docs/design/release-xs/rollcall_corrections.json` on branch `design/committee-videos`, ready to copy. Change `"checked"` to the day you read the evidence yourself.

```json
{
  "_whose": "This file belongs to the person who runs Granite Record, like docket_corrections.json and member_corrections.json. Claude drafted the one entry below on 26 October 2026 for that person's review (P14 of the polish of 26 October 2026). rollcall_parser.py applies every entry until the person removes it. Read it; the file is yours.",

  "_what": "Roll calls the General Court's roll-call file files under the wrong bill (RollCallSummary.txt, and records/rollcalls/RollCallSummary_<year>.txt for past years), put under the bill they were on by a person, with the evidence for each beside it. Edited by hand. No generator writes it, and preflight fails if any build_* or fetch_* script opens it for writing.",

  "_why": "A roll call's bill decides which bill's Votes tab draws it, which bill each member's Votes tab links, and which of the docket's rows the sitting's page pairs it with. The file types that bill by hand, and one mistyped number puts a vote on a bill that never had it and takes it off the bill that did. A correction is made only where the record settles it and nothing points the other way: the Journal page that prints the vote, the docket rows of both bills, and the roll call's own fields.",

  "_how": "Key each entry by the roll call as the site names it: year, H or S, number (\"2025-S-117\"). \"says\" is the bill the roll-call file gives it, as the file types it; \"belongs_to\" is the bill it was on. rollcall_parser.roll_call_bill is the only reader: it names a roll call's bill for rollcalls.json, for every member's ballot (build_data.py) and for the floor-debate index (build_floor_index.py), so the bill's Votes and Hearings tabs and the members' Votes tabs move together. An entry is applied only while the file still files that roll call under \"says\". One that has stopped matching is reported by rollcall_parser.py and build_data.py and NOT applied, and preflight fails on it (_rollcall_refiled): it means the General Court has changed the file and this entry is now the thing that is stale. An entry with no such key, or with \"says\" and \"belongs_to\" not two different bill numbers, stops the build. Nothing on the page says the vote was moved; \"why\" and \"evidence\" are for the next person to read.",

  "_fields": {
    "says": "The bill the roll-call file files the vote under, as it types it.",
    "belongs_to": "The bill the vote was on.",
    "why": "What the evidence shows, in a sentence or two.",
    "evidence": "Each line of the record that settles it, quoted with where it is.",
    "checked": "The day a person read the evidence (YYYY-MM-DD)."
  },

  "misfiled": {
    "2025-S-117": {
      "says": "HB287",
      "belongs_to": "SB287",
      "why": "Filed under the wrong bill: HB 287 for SB 287. The vote is the Senate's 16-8 adoption of the committee of conference report on SB 287 (2025-2797c) on 26 June 2025, which Senate Journal 17 prints on page 940 and SB 287's docket records. HB 287 was killed by the House on 20 February 2025, never reached the Senate and had no committee of conference; Senate Journal 17 does not name it. The file's title for the roll call is HB 287's, joined on the mistyped number.",
      "evidence": [
        "records/rollcalls/RollCallSummary_2025.txt line 379: '2025|S|117|6/26/2025 12:00:00 AM|HB287|16|8|24|0|||Conference Committee Report|requiring police departments to provide fire departments with certain motorist personal and insurance information following a motor vehicle incident.||6/27/2025 9:16:09 AM'",
        "journals_senate/2025/SJ 17 June 26, 2025.txt, page 940 (between the running heads 'SENATEJOURNAL26JUNE2025 940' and '941 SENATEJOURNAL26JUNE2025'): 'Committee of Conference Report on SB 287, requiring applicants for absentee ballots to present a copy of their photo identification with their application. ... The question is on the adoption of the Committee of Conference Report. A roll call was requested by Senator Altschiller, seconded by Senator Rosenwald. The following Senators voted Yes: Rochefort, Lang, McConkey, Gray, Innis, Ward, Ricciardi, McGough, Avard, Murphy, Pearl, Sullivan, Birdsell, Abbas, Gannon, Carson. The following Senators voted No: Watters, Prentiss, Fenton, Rosenwald, Reardon, Long, Perkins Kwoka, Altschiller. Roll Call, Yeas: 16 - Nays: 8. Adopted.'",
        "records/rollcalls/RollCallHistory_2025.txt, the 24 ballots of 2025|S|117: the 16 Yeas and 8 Nays are the senators the Journal names, each on the side it names",
        "The Senate's roll calls of 26 June 2025 in the file, 2025-S-107 to 117, and the eleven the Journal prints that day, in the Journal's order and with the same tallies: HB 282 24-0 and 24-0, HB 60, HB 71, HB 377, HB 506, HB 712, HB 1 and HB 2 each 16-8, HB 115 8-16, then SB 287 16-8 on page 940. The file's eleventh is 'HB287'",
        "Docket.txt (the copy of 26 October 2026) line 10663, SB 287's own row: '2025|1097|6/26/2025 3:59:58 PM|SB287|S|Conference Committee Report # 2025-2797c; RC 16Y-8N, Adopted; 06/26/2025;  SJ 17|6/26/2025 3:59:58 PM'. No Senate roll call of 2025 is filed under SB 287 but its 16-8 of 27 March (2025-S-39)",
        "Docket.txt lines 292 to 3587, HB 287's six rows: introduced 8 January 2025 and referred to House Transportation, heard 21 January, reported Inexpedient to Legislate 9-7, and last 'Inexpedient to Legislate: MA DV 201-163 02/20/2025  HJ 6  P. 19'. No Senate row, and no committee of conference",
        "journals_senate/2025/SJ 17 June 26, 2025.txt does not contain 'HB 287'"
      ],
      "checked": "2026-10-26"
    }
  }
}
```

## 2. One row for the table in `corrections/README.md`

Add it after the `docket_corrections.json` row:

```
| `rollcall_corrections.json` | roll calls the roll-call file files under the wrong bill, put under the bill they were on, with the Journal page, the docket rows and the roll call's own fields that settle each | `src/parse/rollcall_parser.py` (`roll_call_bill`, for `rollcalls.json`, for every ballot `build_data.py` keys and for `build_floor_index.py`) |
```

## 3. Then

1. Merge `fix/release-xs` to `dev`, so the reader is there. Commit the file on its own if you want: without the reader it is just a file that nothing reads, and `preflight`'s hand-made guard covers it from the day it exists.
2. Run `python3 preflight.py`. `_rollcall_refiled` reads your entry against `records/rollcalls/RollCallSummary_2025.txt`, which is in git, and passes only if roll call 117 of 2025 is still filed under HB287 there.
3. Commit it to `dev`. The next night's build applies it.

---

## The evidence, in plain words

I read every item below myself on 26 October 2026. The Senate Journal, the docket and the day's roll-call file came from the kit in the bucket (a read-only download). The archived roll calls are in git.

1. **The roll call's own fields.** `records/rollcalls/RollCallSummary_2025.txt`, line 379:
   `2025|S|117|6/26/2025 12:00:00 AM|HB287|16|8|24|0|||Conference Committee Report|requiring police departments to provide fire departments with certain motorist personal and insurance information following a motor vehicle incident.||6/27/2025 9:16:09 AM`
   It is a Senate conference-report vote of 26 June 2025, 16–8, typed under HB287. The title in the row is HB 287's. I take that to mean the title was looked up from the mistyped number, but that is my inference, not something the record says.

2. **The Senate Journal prints it as SB 287's.** Senate Journal 17 (26 June 2025), page 940, between the running heads `SENATEJOURNAL26JUNE2025 940` and `941 SENATEJOURNAL26JUNE2025`:
   > Committee of Conference Report on SB 287, requiring applicants for absentee ballots to present a copy of their photo identification with their application. … The question is on the adoption of the Committee of Conference Report. A roll call was requested by Senator Altschiller, seconded by Senator Rosenwald. The following Senators voted Yes: Rochefort, Lang, McConkey, Gray, Innis, Ward, Ricciardi, McGough, Avard, Murphy, Pearl, Sullivan, Birdsell, Abbas, Gannon, Carson. The following Senators voted No: Watters, Prentiss, Fenton, Rosenwald, Reardon, Long, Perkins Kwoka, Altschiller. Roll Call, Yeas: 16 - Nays: 8. Adopted.

   The same Journal never mentions HB 287.

3. **The ballots are those senators.** The 24 ballots of `2025|S|117` (`records/rollcalls/RollCallHistory_2025.txt`) are the same senators the Journal names, each on the side it names: 16 Yea, 8 Nay, no one else.

4. **The day's order agrees, one for one.** The Senate took 11 roll calls on 26 June 2025: numbers 107 to 117 in the file. The Journal prints 11 that day, in this order and with these tallies:

   | Roll call | Bill | Tally |
   |---|---|---|
   | 107, 108 | HB 282 | 24–0 and 24–0 |
   | 109 to 115 | HB 60, HB 71, HB 377, HB 506, HB 712, HB 1, HB 2 | 16–8 each |
   | 116 | HB 115 | 8–16 |
   | 117 | SB 287 | 16–8 |

   The file's number 117 says "HB287". The other ten match the Journal by bill and tally.

5. **SB 287's docket records the vote.** `Docket.txt` (the copy of 26 October 2026), line 10663:
   `2025|1097|6/26/2025 3:59:58 PM|SB287|S|Conference Committee Report # 2025-2797c; RC 16Y-8N, Adopted; 06/26/2025;  SJ 17|6/26/2025 3:59:58 PM`
   SB 287's only other Senate roll call is its 16–8 passage of 27 March 2025 (2025-S-39).

6. **HB 287's docket ends in February.** HB 287 has six docket rows (lines 292 to 3587):
   - introduced on 8 January 2025 and referred to House Transportation;
   - public hearing on 21 January;
   - committee report: Inexpedient to Legislate, 9–7;
   - last row: `Inexpedient to Legislate: MA DV 201-163 02/20/2025  HJ 6  P. 19`.

   It has no Senate row and no committee of conference. Its status is "INEXPEDIENT TO LEGISLATE".

Nothing points the other way.

The site already partly corrects this. The Senate's page for 26 June 2025 shows the vote on SB 287's card: `session_days.py` matches a roll call to the one row on that day that states its tally. Only the bill's page and the members' Votes tabs still say HB 287. Those are what this entry fixes.

---

## Proof that the entry does what it says

### How I tested it

I built the whole site from the real record on 26–27 October 2026, in a temporary folder outside the repository:
- the code is this branch;
- the data is the kit in the bucket, read only;
- `corrections/` is a **copy** of yours, with this one file added;
- every page is dated `GRANITE_BUILD_DATE=2026-10-26`;
- the command is `build_all.py --local --no-captions`, as the night runs it. 46 steps ran, 1 was skipped (no livestream state here), 0 failed.

Your `corrections/` folder was not touched.

"Before" below is the preview, https://dry-run.graniterecord.pages.dev: this morning's dry run of the same record, built without the entry or the new code.

### 1. The roll-call file: exactly one roll call moves

I ran `rollcall_parser.py --all` over the real roll-call files twice, without and then with the entry.
- Of 9,565 roll calls, exactly one changes: 2025-S-117 moves from HB287 to SB287.
- Its outcome is now read from SB 287's own docket row (`docket`) instead of from the Journal (`journal`). No other field of any roll call changes.
- The log says: `rollcall_corrections.json: 2025-S-117 is filed under HB287 in the roll-call file and drawn under SB287`.

### 2. The ballots move with it

In `data/member_votes.json`, all 24 ballots of 2025-S-117 are now filed under SB287: 16 Yea, 8 Nay. No Senate ballot of 2025 is filed under HB287 any more.

### 3. The floor-debate index: one entry moves

This needs commit `f422d48` as well. Between the build without that commit and the build with it:
- `floor_index.json` differs in exactly one of its 4,396 entries: the Senate's recording of 26 June 2025 (`ezonqMvgvZg`, "Conference Committee Report 16-8", no clock time) moves from HB287 to SB287;
- `proceedings.csv` differs in exactly that one row.

`python3 src/hearings/probe_alignment.py --truth --site site` gave byte-identical output on both builds: 63 timed proceedings, the same medians. The timestamp gate has not moved.

### 4. The pages, in Chromium

The built site was served on 127.0.0.1, with every other origin blocked.

| Page | Before (preview) | After (built with the entry) |
|---|---|---|
| /bill/2025/hb287, Votes | **2**: the House's 201–163 of 20 Feb, and "Adopt the Conference Committee Report · Jun 26, 2025 · Senate · Roll Call · 16–8" | **1**: the House's 201–163 of 20 Feb only |
| /bill/2025/hb287, Hearings | **5**, including "Jun 26, 2025 — HB 287-A - Senate Floor Debate" | **4**, with no Senate floor debate |
| /bill/2025/sb287, Votes | **6**: the House's voice vote on the conference report of 26 June, but no Senate vote that day | **7**: adds "Adopt the Conference Committee Report · Jun 26, 2025 · Senate · Roll Call · 16–8", Republican 16 Yes, Democrat 8 No, with all 24 senators' ballots |
| /bill/2025/sb287, Hearings | **6**: no recording for 26 June | **7**: adds "Jun 26, 2025 — SB 287 - Senate Floor Debate" |
| /bill/2025/sb287, "How It Got Here" | "Adopted the conference report, 16–8" on 26 June (from the docket) | unchanged |

**A senator's Votes tab.** On /legislator/cindy-rosenwald-sd-13 (Votes, 2025–2026, the 26 June row), before:
> Jun 26, 2025 · **HB 287-A** requiring police departments to provide fire departments with certain motorist personal and insurance information… · Adopt the Conference Committee Report · No

It linked `bill/2025/hb287.html` and `session/S/2025-06-26#HB287`, an anchor that page does not have.

After:
> Jun 26, 2025 · **SB 287** requiring applicants for absentee ballots to present a copy of their photo identification with their application. · Adopt the Conference Committee Report · No

It links `bill/2025/sb287.html` and `session/S/2025-06-26#SB287`. That page has a card with `id="SB287"` and no card for HB287.

In the members' vote files, every one of the 24 senators' rows for 2025-S-117 now names SB287, year 2025.

**The download.** In `/data/rollcalls.csv`, the row reads: `2025-S-117, 2025-06-26, SB287, Adopt Conference Committee Report, 16, 8`, with the outcome taken from the docket.

### 5. `preflight` reads your file once it exists

I pointed `_rollcall_refiled` at a scratch folder holding this file and the real `records/rollcalls/`:
- **this entry:** passes;
- the same entry with `says` changed to HB288 (a **stale** entry): fails, with "2025-S-117 is filed under HB287 in the roll-call file now, not HB288: the entry is stale";
- an entry for a roll call that does not exist: fails;
- an entry for a year whose file is not on disk: passes, and says it was not checked.

---

## What this does not do (for you to decide, none needed for the release)

- **The page does not say the vote was moved.** A docket correction shows a note under the row ("The General Court's online docket also lists this vote under …"), but a moved roll call shows none. SB 287's Votes tab will simply show the vote. The entry's `why` and `evidence` are kept for the next person. A note on the card would be a small change to `app.js`, if you want one.
- **A later correction of a *House* roll call would move timestamps.** The floor-debate index reads the corrected bill too (commit `f422d48`). A House roll call has a clock time, so moving one moves a debate window from one bill to another. When you add such an entry, run `python3 src/hearings/probe_alignment.py --truth --site site` before and after, as CLAUDE.md asks. This entry is a Senate roll call with no clock time: the score was identical (proof, part 3).
- The file keeps HB 287's title on the roll call's internal row. No page shows it: the session page and the Votes tabs take the title from the bill index, which is SB 287's.
