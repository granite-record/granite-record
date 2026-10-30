# Election week, 23 October 2026 to 7 January 2027

What to do, and when, so the site is right on election night, on Organization
Day and on the two swearing-in days. Written on 23 October 2026 after a
rehearsal of every day below on preflight's fixture. The dates are the law's
and the record's; the sources are at the end. Every file in `corrections/` is
yours: nothing here writes one, and the shapes below are drafts to copy.

Two rules hold the whole way through:

- **The nightly builds `main`.** A file you commit reaches the site only
  once it is merged into `main`, and the first night after a merge waits
  for your approval (Actions, "nightly", Review deployments), as does a
  night with a new kind of warning (the gate in `nightly.py`).
- **A refused input stops the night.** `build_members_elect.py` is not an
  optional step: a results file whose saved spreadsheet changed under it, or
  a `corrections/members_elect.json` that will not read, stops the build and
  nothing is published that night. Run the step on the laptop before you
  commit (step 3 below).

## Before 3 November

1. **Merge this branch** (the voting guide's student ID sentence) into `dev`
   and `main` by 30 October. The guide said an October 2 order "lets election
   officials consider a student ID"; the U.S. Supreme Court stayed that order
   on 22 October (No. 26A512). The sentence is out; nothing replaces it yet.
   Saying what happened needs the Supreme Court's address in
   `guide_sources.SOURCES`, which holds state pages only, so it is your
   call. Until a guide names that address, `guides.STAYED_ORDERS` and
   preflight keep the old sentence from coming back.
2. **Read the Secretary of State's proof page in a browser** on 1 or 2
   November (<https://www.sos.nh.gov/proof-voter-registration-qualifications>).
   If its guidance on the affidavit or student IDs has moved, change the
   note in `src/pages/guides.py` (`VOTING`) and its claims' dates.
3. **Polling hours** come from the Secretary of State's clerk list saved on
   20 September: 225 of its 331 rows give state-election hours, and 106 are
   blank. To fill more, save the list again as CSV
   (<https://app.sos.nh.gov/statelistclerkandpolling>) into `records/sources/`,
   point `CSV_IN` and `READ_ON` in `src/towns/parse_clerks_csv.py` at it, and
   run `python3 src/towns/parse_clerks_csv.py`. Optional: the statute's
   floor, 11 a.m. to 7 p.m., holds everywhere.

## 3 November, election day

Nothing to do. The site says "Next Election: November 3, 2026" on town pages,
"The vote is on Nov 3, 2026" on CACR 13, and "General election" under Coming
up on the schedule page.

## From 4 November, on its own

The night changes tense by itself. Check, once:

- CACR 13 (`/bill/2026/cacr13.html`): "went to the voters in November 2026",
  and on its Votes tab "The vote was on Nov 3, 2026; its count is not
  recorded here yet."
- `/learn/county-government.html`: "the Secretary of State's count is not on
  the site yet."
- A town page: "Last election: November 3, 2026".
- No Members-Elect tab on Officials, and no `/members_elect.json`. They come
  only from step 2 below.

## The helper: `src/ops/election_week.py`

It does the routine work around the one step that stays yours, saving the
files in a browser (sos.nh.gov refuses scripted clients, and saving them
stays a person's act: the decision of 16 October 2026). It asks nobody
anything. Its own files are all in `logs/`, and every draft is yours to read
and copy; the two steps `check` runs write what they write when you run them
by hand (`collected/election_2026.json`, `site/members_elect.json`), and
nothing writes `corrections/`.

- `status`: which of the eleven 2026 files are saved, which are missing, and
  any later numbered upload the collected file has not read yet.
- `check --url <the results page>`: until all eleven are saved, it says how
  many are. Other files of 2026 saved beside them, such as the question's
  spreadsheet, never hold it up; a name that looks like a results file the
  reader does not take is listed, and a download still in progress
  (`.crdownload`, `.part`) makes it wait. With all eleven it runs steps 2 and 3 below, writes
  `logs/election_week.md` (FILES, REFUSED, FLAGGED, NOT LINKED, NEW, DO NOT
  ADD UP, NOTES, THE STEP SAID) and drafts the matches in
  `logs/members_elect.matches.draft.json`: each NOT LINKED name with the
  member the step names, or `null`, and each NEW name `null` with any member
  of that surname in its county to CHECK ("Marty Jack": "Martin Jack [733]").
  NOT LINKED names get a member only where the step's reason is a first
  name it could not be sure of ("Peter" for "Pete"); every other reason
  names someone it ruled out, and the draft says so and leaves `null`. Then
  it is done, and later runs only say so, until a file it has not read is
  saved (a recount's `_N`): then it runs once more. A refusal, a failure, or
  a step that showed nobody is not done, and it tries again the next hour.
- `draft-recounts --schedule <the saved schedule> --day <its date>`: the
  `"not_final"` block and `"recount_deadline": "2026-11-06"` in
  `logs/members_elect.recounts.draft.json`, from the schedule's text (.txt,
  .csv, or a PDF). A line is drafted only where every race it names is a
  race on file; a line it could not place, or one saying a recount was
  withdrawn, is printed NOT PLACED for you to read.
- `draft-cacr --file <the question's spreadsheet> --url <the page>`: CACR
  13's row in `logs/ballot_results.cacr.draft.json`, with whether two thirds
  said yes. It reads only a statewide count: a "State Totals" row, or the
  one totals row of a sheet with a single Yes/No header, never a county's;
  otherwise it says to copy it by hand. The 2026 layout has not been seen;
  read the draft against the page.

To run `check` every hour from 4 November, 07:00 to 22:00, on the laptop --
on battery too, and as soon as it wakes when an hour was missed -- paste this
into PowerShell in the repository's folder, as yourself. Delete the task once
the results are in: `Unregister-ScheduledTask GraniteElectionWeek -Confirm:$false`.

```
$dir = (Get-Location).Path
$act = New-ScheduledTaskAction -Execute "cmd.exe" -WorkingDirectory $dir -Argument '/c python3 src\ops\election_week.py check --url https://www.sos.nh.gov/2026-general-election-results >> logs\election_week.log 2>&1'
$when = New-ScheduledTaskTrigger -Once -At ([datetime]"2026-11-04T07:00") -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration (New-TimeSpan -Days 16)
$how = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
Register-ScheduledTask -TaskName GraniteElectionWeek -Action $act -Trigger $when -Settings $how
```

It runs every hour, night too; at night it only says the files are saved or
not, which costs nothing.

Check the results page's address on the day: if it is not
`https://www.sos.nh.gov/2026-general-election-results`, give the one you
saved the files from (the Officials tab cites it).

## When the Secretary of State has posted every results file

Wait for all eleven: the ten county House spreadsheets and the Senate one. The
reader refuses a partial set ("no 2026 House results saved ... for ..."), and
nothing shows until it reads them all. If they come late, the site says
nothing about members-elect until then, which is true.

1. **Save each in a browser**, byte for byte, under the Secretary of State's
   own name, into `records/sources/`. The reader knows
   `2026-ge-house-<county>[_N].xls` or `.xlsx` and
   `2026-ge-state-senate-district-1-24[_N].xls` or `.xlsx`, as in 2024. If
   the 2026 names differ, stop: the pattern is code (`HOUSE_FILE`,
   `SENATE_FILE` in `src/parse/parse_sos_results.py`).
2. **Read them**, on a laptop with a built `site/` (for `site/districts.json`):

   ```
   python3 src/parse/parse_sos_results.py --year 2026 --url <the results page you saved them from>
   ```

   Read every `FLAGGED` line. On `REFUSED`, read why; never edit
   `collected/election_2026.json` by hand. Without `--url` the file names no
   address and the Officials tab cites the count unlinked.
3. **Run the step on its own** and settle what it prints:

   ```
   python3 src/parse/build_members_elect.py --site site
   ```

   `NOT LINKED`: give each name a member's id, or `null` for a new person,
   under `"matches"`. `NEW`: confirm with `null`. `DO NOT ADD UP` and `NOTES`:
   read every line. To see a later day, `set GRANITE_BUILD_DATE=2026-11-07`
   first (and `set GRANITE_BUILD_DATE=` after).
4. `python3 preflight.py` must end `0 failed`. Commit `records/sources/2026-*`,
   `collected/election_2026.json` and `corrections/members_elect.json`
   together, to `dev`.

**The results go to `main` only together with the recount deadline (Friday
6 November, 5 p.m.) and the recount list, below, in one merge; if that merge
cannot be approved by the night of 9–10 November, members-elect is left off
for the webinar.** Until `"recount_deadline"` is entered every race is drawn
"Result not final" and nobody is named, which is why the results do not go
out alone.

## The recount deadline: Friday 6 November, 5 p.m.

Candidates ask the Secretary of State for a recount by 5 p.m. on the Friday
after the election (RSA 660:1; 8 November in 2024). **Enter the deadline only
together with the recounts asked for**, in one commit, once the Secretary of
State has published which races are being recounted. A deadline entered alone
lets the next night draw every race as final, including one whose recount was
asked for that afternoon.

```json
"2026-11-03": {
  "recount_deadline": "2026-11-06",
  "matches": {"<race>": {"<name as the results print it>": "<member id, or null if new>"}},
  "not_final": {"<race>": {"recount": true, "why": "on the SoS recount schedule of <day>"}},
  "held": {}
}
```

A race is a key of `site/districts.json`: `"H|Hillsborough|9"`, `"S|24"`.
`"seats": 1` holds back only one seat of a multi-seat race. A reason is never
published.

## Each recount's result, or any corrected upload

The Secretary of State uploads the county's file again, under the next number
(`_4` after `_3`). Save it beside the earlier one, run the reader again (it
reads the later file, says so in `_notes`, and marks the race
`"recounted": true`), take that race out of `"not_final"`, and commit all three
together. **Never save over a file of the same name without running the reader
again**: its sha256 then no longer matches the results file, the step refuses,
and the night stops.

## CACR 13's count

When the Secretary of State posts the constitutional question's statewide
count, replace CACR 13's row in `corrections/ballot_results.json`:

```json
{"term": "2025-2026", "bill": "CACR13", "election": "2026-11-03",
 "label": "<as the results spreadsheet lists it, e.g. Question No. 1>",
 "yes": 0, "no": 0,
 "source": "<the 2026 general election results page on sos.nh.gov>",
 "cite": "2026 general election results, sos.nh.gov", "read": "<YYYY-MM-DD>",
 "note": "The spreadsheet also counts N blank and N overvoted ballots; neither is a vote cast on it.",
 "match": "<keep the row's match as it is>"}
```

Drop `"described"`; a decided row needs no Ballotpedia cross-check. The build
works out "ratified" from two thirds of yes plus no (Part Second, Article
100). Then read the register of probate paragraph in `src/pages/civics.py`
again. If two thirds said yes, its "still elected" and the county officers
sentence are no longer true; rewrite them, and set
`REGISTER_OF_PROBATE_REVIEWED` to the day. preflight's
`_probate_after_the_vote` fails until you do.

## The Governor, the Council and Congress

From 10 November preflight's `_officials_rechecked` warns each night until
`_checked` in `corrections/officials.json` is a day on or after 10 November.
Once the results are certified, give each seat that changes hands an `"elect"`
(`corrections/README.md`, "A successor"), and set `_checked`. A holder
re-elected needs nothing.

- **Certain to change:** Jeanne Shaheen's US Senate seat (`us_senate.seats[0]`)
  and US House District 1 (Chris Pappas ran for the Senate). Congress takes
  office **3 January 2027** (Twentieth Amendment).
- **On the ballot:** the Governor and all five Council seats, taking office
  on Inauguration Day, **7 January 2027 (likely)**: the Thursday after the
  session opens on 6 January, as in 2025 (9 January) and 2023 (5 January).
  The constitution fixes no day, so confirm it from the House or Senate
  calendar before entering it.
- A successor needs `"source"`, `"takes_office"`, and an `"official_url"`
  wherever the holder's record has one (the office's page will do until
  theirs exists), and every phone or email, since nothing is carried over.

```json
"1": {"name": "Chris Pappas", "...": "...",
      "elect": {"name": "<winner>", "party": "<R or D>", "phone": "", "phone_dc": "",
                "official_url": "https://www.house.gov/",
                "source": "<the certified results page>", "read": "<YYYY-MM-DD>",
                "takes_office": "2027-01-03"}}
```

## Before 2 December: freeze 2025–2026

After the turn, 2025–2026 is built every night from its frozen inputs and
nothing else, and the New term run stops before asking anything if they are
not the files installed. So, on the laptop (`src/lib/freeze_term.py`, *WHEN,
AND WHO*):

1. Straight after the late-November database download, which is yours to
   start: `python3 src/lib/freeze_term.py --views`, then
   `python3 src/ops/cloud.py seed-kit --only "db/term/*/*"`.
2. Before Organization Day, while the installed roster is still 2025–2026's:

   ```
   python3 src/lib/freeze_term.py --session
   python3 src/lib/freeze_term.py --check
   python3 src/ops/cloud.py seed-kit --only "frozen/**" Docket_2025-2026.txt verification_manifest_2025-2026.csv
   ```

   If `--session` says it wrote a `records/rollcalls/` copy, commit it and
   merge it to `main` before the switch night.

## 2 December, Organization Day

The members-elect retire by themselves: the step removes
`/members_elect.json`, the pages stop drawing it, and a reader's browser hides
any block it kept. Check that Officials has no Members-Elect tab.

**Until the General Court's member list names the new House, the old roster
shows alone as sitting.** That is the decision of 16 October, and it is a
gap: members who lost are listed as serving. A scheduled night installs the
new roster once the General Court publishes it, and the New term run turns
the term when its files do (rehearse both first with
`python3 tests/rehearse_turn.py --copy <a folder outside the repository> --guards`).
On the switch night -- the first scheduled night that refuses the files as a
new term -- freeze once more first: `python3 src/ops/cloud.py pull`, then
`--session`, `--check` and the same seed-kit, then the nightly by hand with
New term ticked.
Check Officials, Legislators, every morning from 3 December until the new
members are there.

Then edit `corrections/status/status.txt`, which still says the House and
Senate have finished the 2026 session, and goes stale-flagged from
7 December:

```
updated: 2026-12-02
phase: between sessions
headline: The 2027–2028 General Court was sworn in on Organization Day, December 2.
note: The 2027 session opens on January 6.
milestone: 2027-01-06 | 2027 session convenes | The first session of the 2027–2028 term.
```

Delete `session_over` once the New term run has turned the site
(preflight's `_session_over_current` says when), not before.

The legislature also elects the Secretary of State and the Treasurer in
December (Part Second, Article 67). Give either an `"elect"` only if the person
changes. Read the Secretary of State's 2027–2028 county roster when it is
published, for the county officers.

## 3 and 7 January

Nothing to do. On the 3rd the Federal Delegation tab and the town pages show
the new members of Congress. On the 7th the Executive Branch tab shows the
Governor and Council. Check each that morning.

## Sources, read 23 October 2026

- Recount deadline: RSA 660:1, the Friday after the election; for 2024,
  "Friday, Nov. 8th at 5 p.m." (NHPR, 30 October 2024,
  <https://www.nhpr.org/nh-news/2024-10-30/follow-the-ballot-what-happens-after-you-vote-in-nh>).
- Polling hours: RSA 659:4, open by 11 a.m. and closed no earlier than 7 p.m.
- Organization Day and the session's opening day: Part Second, Article 3
  (`collected/constitution.json`).
- Inauguration Day: Senate Journals 3 of 2025 ("INAUGURATION DAY - JANUARY 9,
  2025") and 2023 ("JANUARY 5, 2023"), in the kit.
- Congress: Twentieth Amendment, sections 1 and 2
  (<https://www.archives.gov/founding-docs/amendments-11-27>).
- The student ID stay: Supreme Court No. 26A512, 22 October 2026
  (<https://www.supremecourt.gov/opinions/26pdf/26a512_6j37.pdf>).
- CACR 13: "Are you in favor of eliminating the office of register of probate
  by amending articles 71 and 81 of the second part of the constitution";
  "To pass, two-thirds of those voting on this question must vote Yes."
  (the Secretary of State's 2026 list of questions, as LWV New Hampshire
  prints it, <https://lwvnh.org/issues-actions/>; Part Second, Article 100).
