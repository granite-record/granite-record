# Official election results page: build plan

Written 7 November 2026, after the owner's answers of the same day, relayed by
the manager on the laptop. They were:

- **Build the official-results page** from the Secretary of State's files, for
  2024 and 2026, after the webinar (10 November).
- **Official results only.** Every race reads "Result not final" until the
  recount deadline she enters.
- **The election-night source is decided closer to 2028.** No request is made
  or prepared now.

**Nothing in this plan starts before this weekend's release is live.**
Effort figures are guesses, in working sessions.

The design it builds is `DESIGN.md` (§2, §3, §5), without the live parts. §3's
night view, §4's race-call questions and §6's Worker wait for a source.

---

## 1. What exists already

| Piece | Where | State |
|---|---|---|
| 2024 House and Senate, read | `collected/election_2024.json` on `dev` | 227 races; candidate totals, winners, `recounted` |
| 2026 House and Senate, read | `collected/election_2026.json` on `data/election-2026-sos` | 227 races, same shape; **waits on the Secretary of State's recount list** before it merges |
| 2026 Governor, U.S. Senate, Congress, Council, county offices, CACR 13 | spreadsheets saved by the owner on `data/election-2026-sos` | saved, **not read** |
| 2024 offices other than House and Senate | nowhere | not saved |
| The "final" rule | `src/parse/build_members_elect.py`, `members_elect()` with `recount_open()` | in use for members-elect |
| Who a winner is | `corrections/members_elect.json` `"matches"` (the owner's) | 2026 entry exists, empty; **no 2024 entry** |
| The map | `map.js` with a `data` option; `generated/district_geometry.json` (2022 districts) | works as the mock shows |

---

## 2. Branches, in order

Each branch is cut from `dev` and holds one concern. Each is pushed for the
manager to merge; none is rebased or force-pushed.

### 2.1 `feat/elections-final-rule` (about ½ session)

- **What:** move the rule that decides whether a race is final into one
  function, `src/lib/race_final.py`: `race_final(race, hand, today)`.
  - It returns, per seat, final or not, and why.
  - The rule is as `members_elect()` applies it now:
    - a recount's count is final;
    - otherwise a race is final only when a recount deadline is entered, today
      is past it, and the race is not in `not_final`;
    - `{"seats": n}` holds back the n winners with the fewest votes;
    - a tie for the last seat is never final for that seat;
    - `held` winners are kept off the pages.
- **Who calls it:** `build_members_elect.py` now. The page builder (§2.3) and
  the API's election downloads (design/api, QE1–QE6, which import it rather
  than copy it) later.
- **Proof:** a pure refactor, so the site must build byte for byte the same.
  - Record a baseline twice under different `PYTHONHASHSEED` values, then
    compare (`src/checks/site_manifest.py`), with `GRANITE_BUILD_DATE` set.
  - Add a preflight check that runs `race_final` through every case on a
    fixture: no deadline; before the deadline; past it; `not_final` whole;
    `not_final` `{"seats": 1}`; recounted; a tie; held.

### 2.2 `feat/elections-places` (about 1 session; after `data/election-2026-sos` merges)

- **Why it waits:** that branch rewrote much of `parse_sos_results.py`. This
  one builds on it, never beside it.
- **What:** the reader writes two more fields per race.
  - `"places": {"<place>": [votes in candidate order]}`, every town, ward and
    unincorporated place as the district table names it.
  - `"first_count"` for a recounted race: the candidate votes before the
    recount, in the same order.
- **Files it rewrites:** `collected/election_2024.json` and
  `election_2026.json`, by running the reader, never by hand.
- **Proof:**
  - **Every field that was there is unchanged.** A check compares each file
    with the new keys taken out against its committed version.
  - **Each candidate's places add up to their total.** The reader already
    refuses a column that does not add up to the file's own Totals. The 2026
    notes show where the file's Totals were wrong: Grafton's `=SUM(B47:B48)`
    leaves out Orange, and the towns win.
  - `first_count` equals the column beside each `RECOUNT` column. The checked
    case is Hillsborough 18, 2024: Kesselring 2,048 on the first count, 2,050
    on the recount.
  - `--check` on both years reports nothing else changed.
- **Shared with design/api:** these field names are the ones that design reads
  (`places` for later, `first_count` as its `first_votes`). They are not
  renamed without telling it.

### 2.3 `feat/elections-page` (about 2 sessions)

- **What:** `src/pages/build_elections.py` writes three things.
  - `/elections/<YYYY-MM-DD>-general.html` for each election with a collected
    file: 2024-11-05 and 2026-11-03.
  - `/elections/index.html`, a list of them.
  - `/elections/<YYYY-MM-DD>-map.json`: the district map's data with each
    district filled by the parties of its winners. That is one file per
    election; `check_site`'s count is checked before and after.
- **The page,** as `DESIGN.md` §3 and the 2024 mock draw it:
  - title, lead and the standing line, "Official results. Read from the
    Secretary of State's results files, saved <day>.";
  - tabs only for offices the file holds;
  - "Seats Won", with the majority line;
  - the map;
  - closest races;
  - a card per race, with "By town and ward" and the recount's first count.
- **Words:**
  - The members-elect words, unchanged: "Result not final", "— a recount was
    requested", "Elected".
  - Before the owner's deadline is past, the chamber block reads "Seats Won"
    only for final seats. The rest are counted as "result not final", with
    their own key entry, so nothing is drawn as won early.
- **Components reused:**
  - `pchip` and `chip` (`components.py` and `components.js`);
  - `twntabs`, `l-bar`, `table.votes`;
  - `map.js` with its `data` option;
  - the ballot question's card from the CACR Votes tab, once questions are
    read (§2.4).
- **New CSS:** in `app.css`, palette tokens only. It covers the majority line,
  the candidate's bar, the race card grid and the "result not final" segment.
  Preflight's palette, rem and 13px checks hold it like everything else.
- **People:**
  - A winner links to their member page only through `members_elect.json`
    `"matches"` (or the existing auto-link `build_members_elect` already
    makes for a sitting or former member it is sure of).
  - Never a name match in the page builder.
  - A loser is shown by name and party only.
- **Reached from:**
  - a link in Officials' lead, "Election results";
  - the sitemap and the site search;
  - the member page of a 2024 or 2026 winner: "Elected November 3, 2026" links
    to the race.
- **Not in it:**
  - anything live or unofficial;
  - percentages of polling places;
  - race calls;
  - any number not in a collected file.
- **Proof:**
  - **Every figure on the built page is the collected file's.** A preflight
    check parses the built 2024 page on the fixture and compares each count,
    each winner and each seat total with `election_2024.json`.
  - **"Elected" appears only where `race_final` says so.** A fixture election
    covers each case in §2.1, and the check reads the built cards.
  - **A check against something this project did not generate.** The 2024
    winners against the 2025–2026 roster as sworn in on Organization Day 2024.
    Every winner should be a member of that term in the same district, except
    where a vacancy or special election says otherwise. The mismatches are
    listed for a person to read; a number is not tuned until it passes.
  - **Ten races, chosen at random, read cell by cell against the spreadsheets**
    by me, with the list in the branch's commit message. The owner may re-read
    any.
  - **Screenshots at 390 and 1280, light and dark,** of both years. They are
    shown next to the approved mocks, and the rendered sweep passes.
  - `preflight.py --code` 0 failed. On the laptop, `preflight.py` 0 failed with
    the kit.

### 2.4 `feat/elections-offices` (about 2 sessions; after 2.2)

- **What:** readers for the 2026 files already saved on
  `data/election-2026-sos`: Governor, U.S. Senate, the two congressional
  districts, the five Council districts, the ten counties' county offices, and
  CACR 13's summary.
- **Keys:** as `DESIGN.md` §2.1 has them: `GOV`, `USS`, `USH|1`, `EC|1`,
  `C|Belknap|sheriff`, `CC|Belknap|2`, `Q|2026|1`.
- **The rule they follow:** each reader is written after opening the file, as
  the House reader was. It refuses a layout it does not know rather than
  guessing.
- **Where it shows:** the page gains the matching tabs. CACR 13's count also
  goes to `corrections/ballot_results.json`, but by the owner's hand from the
  draft `election_week.py draft-cacr` already makes. Nothing here writes
  `corrections/`.
- **2024:** these offices appear for 2024 only once the owner saves the 2024
  files. Until then the 2024 page says those offices' files have not been
  read, as the mock does.
- **Proof:** the same as 2.3. The Governor's and Council winners are also
  checked against `corrections/officials.json` and its `elect` entries, which
  the owner keeps from four official sources.

---

## 3. What the owner does

1. **2026:** once the Secretary of State publishes the recount list, enter
   `"recount_deadline": "2026-11-06"` and each race being recounted under
   `"not_final"`, in one commit (as `docs/ELECTION_WEEK.md` says). That unblocks
   `data/election-2026-sos`.
2. **2024:** add a `"2024-11-05"` entry to `corrections/members_elect.json`
   with `"recount_deadline": "2024-11-08"` (NHPR: "Friday, Nov. 8th at 5 p.m.").
   It needs `"matches"` only for any 2024 winner the step cannot link by
   itself. Without this entry every 2024 race reads "Result not final".
3. **Optional:** save the 2024 files for Governor, Congress, Council, county
   offices and questions, if she wants them on the 2024 page.
4. Approve each branch's merge.

## 4. Order and dates

| When | What |
|---|---|
| This weekend | the release goes live; nothing here starts |
| From 10 November (after the webinar) | 2.1 |
| When `data/election-2026-sos` merges | 2.2 |
| After 2.2 | 2.3; then 2.4 |

2.3 can show 2024 before 2026 is merged: the page draws every election with a
collected file.

## 5. Risks

- **The recount list is late, or long.** The 2026 page then shows "Result not
  final" for longer. That is true, and the page says why.
- **A 2026 file is re-uploaded** (`_1`, `_2`). The reader reads the later one
  and says so, as now. The page changes the next night.
- **The other offices' files have layouts the reader has not seen.** Each is
  opened before its reader is written (2.4), and a refusal stops only that
  reader's night step, as `build_members_elect` does.
- **The file count.** One HTML page and one map file per election. That is far
  under the 90,000 warning. `check_site` is run, not quoted.

## 6. Open questions, each with a default

| Question | Default |
|---|---|
| Spanish pages? | English first; every phrase goes through `i18n.say` with a key, so the Spanish pages can follow as the Learn pages did |
| Where is it linked from? | Officials' lead, the sitemap and search, and a winner's member page |
| A 2024 winner who has since left office? | Shown as elected in 2024, linked to their member page (former members have pages) |
| Show 2024 before the owner's 2024 entry exists? | Yes, with "Result not final" on every race, which is true until she enters the deadline |
