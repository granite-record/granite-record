# Videos tab: committees, session days, study committees and commissions

Scout's findings and spec. Read-only on `origin/dev` at 8bede52. The numbers come from the preview
(https://dry-run.graniterecord.pages.dev, i.e. dev at 8bede52) and from the files in git
(`collected/videos/*.csv`, `collected/videos/channel_index_full.json`), measured 26 October 2026.

The owner (26 October 2026): "Committee pages should have a videos tab that essentially compiles the
youtube playlist of that committee's meetings in a structured table with the date, list of bills, and
other pertinent information that can fit in a relatively compact table. The embedded player could
potentially take up most of the tab, and the other videos persist in a scrollable playlist on the right
side, with the most recent entry in the playlist as the default. Same goes for session days, or study
committees, commissions, etc that are livestreamed from those channels."

Mock-ups were injected into the preview's real pages with real rows; nothing loaded from YouTube:
- `/tmp/claude-0/audit/wf18/shots/mock_s07_1280.png`: Senate Finance at 1280
- `/tmp/claude-0/audit/wf18/shots/mock_h43_1280.png`: House Commerce at 1280
- `/tmp/claude-0/audit/wf18/shots/mock_h34_390.png`: House Finance at 390
- The pages as they are today: `s07_bills_1280.png`, `s07_meet_1280.png`, `s07_meet_390.png`,
  `house_1280.png` and `ss57_1280.png` in the same folder
- The scripts: `/tmp/claude-0/audit/wf18/mock.cjs` (with `mockrows.json`) and `shot.cjs`

---

## 0. In one paragraph

Give every page whose body is livestreamed one "Videos" view built from a single component: a still
press-to-play player taking about two thirds of the width, the chosen recording's facts and bills
under it, and a scrolling list of that term's recordings on the right, newest first and chosen by
default. This covers the 46 standing or special committee pages that have a recording, the two
chamber pages (`/session/house` and `/session/senate`), and the 15 study or statutory pages that have
one. The list is built from data the pages already load. It needs two build-side additions:
- the recordings the YouTube index names for a committee that no bill row places (218 this term);
- each recording's own start time and length.

Both travel inside files that already exist, so the deploy gains no files.

---

## 1. Which bodies have pages today, and at what addresses

| Body | Address | Pages | Built by | Has tabs? |
|---|---|---|---|---|
| Standing and special committees, House and Senate, current and former | `/committee/<code>` such as `/committee/H07` or `/committee/S07` | **86** (`committees.json`). By group: House 23 sitting, 4 with no bills or meetings, 19 former; Senate 14 sitting, 1 with neither, 25 former | `src/pages/build_committees.py` writes the JSON and the shell; `app.js` draws the page | Yes: **Bills \| Meetings** (`/committee/H07/sessions`) |
| The chamber as a whole: session days | `/session/house`, `/session/senate` | 2 | `src/pages/build_full_sessions.py` (static HTML plus an inline `SCRIPT`) | No: a term select, an order select, folded days |
| One session day | `/session/H/<date>`, `/session/S/<date>` | **802** House and **800** Senate days (`session/days.json`) | `src/pages/build_session_pages.py` | No (record page with a sticky index) |
| Statutory and study committees, commissions, boards, joint committees (Fiscal, JLCAR, LRCPU and others) | `/committee/ss<CommitteeID>` such as `/committee/ss57` (Fiscal) | **152** active ones (`study_committees.json`): 143 statutory (House 100, Senate 43) and 9 study | `src/pages/build_study_committees.py` (static) | No: W4 sections (What It Does, Report, Members, Meetings) |
| Committees of conference | none | 0 | | Recordings are on each bill's Hearings tab |

### Livestreamed bodies with no page

These were counted from the index; the counts are of recordings.
- Commission to Study Costs of Special Education: 9 in 2025-26, more before that.
- Committee to Study Long-Term Managed Care: 5.
- Committee to Study Reducing the Number of SAUs: 5.
- Governor's Capital Budget Hearing: 6 in total, 2 in 2026.
- House and Senate Finance "Budget Briefing" recordings.
- Commissions before 2025 that the database's active list no longer carries: Retirement Benefits
  Commission (8), the cannabis commission (8), Charitable Gaming (7).
- Committees of conference: about 53 untied recordings.
- Ceremonies and tours.

A page for those bodies is a separate job, and the Videos view can only appear where a page exists.

### Pages that have recordings but no meeting on record

Four special committees have a page and recordings but show "No bills or meetings on record":
- H57 Commissions: 9
- H59 Family Division: 23
- H60 COVID Response Efficacy: 21
- H61 DCYF: 6

House Rules (H23) has 10 recordings, 2 of them this term. Each of these gets its first content from
this tab.

---

## 2. How recordings are tied to bodies and meetings today

**The YouTube index.** It is `collected/videos/videos_{house,senate}_*.csv` plus the night's
`videos_*_livestreams.csv` from the kit, and every reader takes it through
`proceedings.video_indexes()` (`src/lib/proceedings.py:85`).
- It holds **4,427** distinct recordings in git. `channel_index_full.json` has 4,428: 3,029 House and
  1,399 Senate.
- Each row carries `parsed_committee`, `parsed_date`, `start_eastern` (when the stream actually
  began), `duration_iso` and `title`.
- 4,204 of 4,758 rows have a parsed title. The rest are 2020-22 titles in the older form, such as
  "Senate Judiciary (02/22)" or "Education 1/26/21".
- Every row has a duration, and 4,661 have a start time.
- Recordings after the git files (September 2026 onwards) are only in the kit's livestreams CSV. A
  scratch read of git alone therefore shows them without start or length; the nightly has both.

**`proceedings.csv`** (the one table; `/data/proceedings.csv` on the preview) has 105,476 rows, of
which 22,601 carry a `video_id`. They name **2,966** distinct recordings, and 2,937 of those are in
the index.
- Kinds of row: executive session 6,596, public hearing 5,537, floor debate 4,142, hearing 3,420, full
  committee work session 1,256, subcommittee work session 1,035, work session 384, committee of
  conference 223, study committee 8.
- How each was placed (`how_placed`): stated 11,958, approximate 5,532, consent 1,980, floor_dated
  967, floor_stated 936, located 746, floor_precise 441, whole_video 41.
- **No recording is shared by two committees, and none spans two dates.**
- Bills per committee recording: **median 5, 90th percentile 11, maximum 53** (House Commerce).
  Bills per session day: median 56.5 (House, 2025-26) and 60 (Senate), maximum 229.
- **1,490 recordings in the index are tied to no row.**

**Committee pages.** `site/committee/<code>.json` (built at `build_committees.py:1161`) is loaded
whole by the page; H07 is 5 MB. In it, `sessions[]` holds one entry per committee per day, and each
day has:
- `video_id`: the day's first recording.
- `items[]`: one per bill and kind, with `video_id`, `start`, `end`, `state`, `inferred`, `time`,
  `venue`, `kind`, `bill`, `n`, `title`, `year` and `term`.

The Meetings tab draws one player per recording of the day (`meetingPlayers`, `app.js:8814`).
- **41 of 86** committee pages have a recording through their bills, with a median of 63 and a
  maximum of 170 (H07) across all terms.
- 35 of them have one in 2025-26, with a median of 29 and a maximum of 56.
- 17 committee-days hold more than one recording.
- Bill-recording items: 10,491 have a stated moment, shown plain. 2,203 have an inferred one
  (`stated` with `inferred` set, or `located`), shown as "approximate". 5,515 are in a recording with
  no moment. 318 are `candidates`: a committee in divisions that streamed separately, mostly House
  Finance.

**What the committee pages miss.** The index names recordings for a committee that no bill row
places. Matching strictly, those are recordings where `parsed_committee` equals the page's name in
that chamber, plus House "Finance Division I/II/III" filed under House Finance. That gives **626**
across all terms and **218 in 2025-26**. The biggest gaps this term:

| Page | Placed by bills | Matched by title | Total |
|---|---|---|---|
| House Finance (divisions) | 30 | 76 | 106 |
| Senate Finance | 18 | 33 | 51 |
| Senate Energy | 34 | 9 | 43 |
| House Ways and Means | 42 | 7 | 49 |
| Senate HHS | 32 | 7 | 39 |
| Senate Commerce | 29 | 7 | 36 |
| H60 COVID (no bills) | 0 | 6 | 6 |

For Senate Finance, the page's head says its last meeting was 7 April 2026. The channel has it
meeting on 14, 21 and 28 April and on 5 and 12 May 2026, and the docket has no Senate Finance row on
any of those days.

With the strict match added:
- **46 committee pages** have a recording, with a median of 64.5 and a maximum of 308 (House
  Finance) across all terms. The five pages added are H23, H57, H59, H60 and H61.
- **38** have a recording in 2025-26, with a **median of 31.5 and a maximum of 106**, then 57 (H43).
- By term (pages, recordings): 2019-20 25 and 41; 2021-22 33 and 862; 2023-24 39 and 1,340; 2025-26
  38 and 1,175. That makes **3,418** recordings in all.

**Session days.** Each day in `site/session/<H|S>/<term>.json` carries `videos` (ids), `counts`,
`summary`, `journal` and `journal_url`. The ids come from `day_videos`
(`build_session_pages.py:3359`), which reads only the floor index's "moments", so only the current
term has any:

| | Days | With a recording now | Index adds by date | Total |
|---|---|---|---|---|
| House 2025-26 | 34 | 32 | 2 | 34 |
| Senate 2025-26 | 33 | 27 | 6 | 33 |
| House 2023-24 | 34 | 0 | 34 | 34 |
| Senate 2023-24 | 39 | 0 | 39 | 39 |
| House 2021-22 | 26 | 0 | 15 | 15 |
| Senate 2021-22 | 34 | 0 | 12 | 12 |
| 2019-20 | | 0 | 0 | 0 |

The index's "<Chamber> Session (MM/DD/YYYY)" recordings agree with the moments wherever both exist
(0 differ). Each day has at most one session recording.

**Study and statutory pages.** Each meeting carries `video` from `build_calendar.study_recordings`
(`build_calendar.py:392`). That function scores word overlap at 0.6 or more against recordings on no
bill, from 2025-01-01 (`FROM`) on.
- **15 of 152** pages have a recording, **125** in all. By page: Administrative Rules 22, Fiscal 20,
  HHS Oversight 17, Performance Audit 11, Stable Tokens 10, LRCPU 8, Dedicated Funds 7, Carbon
  Sequestration 7, Capital Project Overview 6, and 1 to 4 for the rest.
- The median across the 15 is 7.
- Of 728 meetings held from 2025 on, 125 are recorded.
- Recordings before 2025 are not on these pages, because the database holds no study meetings from
  2016 to 2023: Fiscal has 41 in the index, JLCAR 39 and LRCPU 17.

**The calendar** (`build_calendar.py`, from 2025-01-01). A study meeting's card links "The recording,
on YouTube". A committee card leads to its bills, whose pages hold the recording. Recent Session Days
on the home page has its own two players (`build_pages.recent_sessions`, `HOME_JS`).

**Bill pages.** The Hearings tab (`/bill/<y>/<id>/hearings`, also served at `/videos`) shows one
player per sitting, with a jump to the bill's moment. 6,054 bill-terms have a recording.

---

## 3. Where the code is (reuse these)

### The player

`.player[data-player=pid]` > `button.pstub[data-embed="vid|from|pid"][data-title]` + `.pbar`
("On YouTube").

One document-level handler at `app.js:9996` swaps the button for the iframe:
`https://www.youtube-nocookie.com/embed/<vid>?start=<from>&autoplay=1&enablejsapi=1`.
- It titles the frame from `data-title` and gives the frame the focus the button had.
- `[data-seek="pid|t"]` builds the frame at that time, or seeks an open one with `postMessage`.
- `app.js` is loaded by every page built from `S.template`, which includes the study and chamber
  pages; they load `/components.js`, `app.js` and `/find.js`. So one handler serves all three page
  types.
- CSS is in `app.css`: `.player`, `.player iframe` and `.pstub` at :1209 (16:9 still), `.pbar` at
  :3016, and `.cmlay`/`.cmplay` at :6879 (the Meetings tab's two columns at ≥60em, player sticky).

### The bill's moment

`meetingLine(s, o, items)` at `app.js:8782` draws the moment buttons. A plain time is used where
`state` is stated, floor_stated or floor_precise and `inferred` is not set; otherwise the time is
followed by *approximate*. Reuse it verbatim: nothing about timestamps changes.

### Committee page tabs

| What | Where |
|---|---|
| `COMMITTEE_TABS={sessions:1}` | `app.js:2832` |
| `TAB_PATH` / `tabAddress` | `app.js:2833` |
| `renderCommittee` | `app.js:9241` (tabs `[["Bills",n],["Meetings",n]]`, bodies by `PAGE_TAB`) |
| `tabStrip` / `pagePane` | `app.js:8027` (role=tablist, `ptab_i`, `#ppane`) |
| Arrow, Home and End keys on `.tab` | `app.js:10478` |
| `termControl` | `app.js:7979` (the term governs every tab, and the term is not in the address) |
| `openPage` | `app.js:9522` (reads the tab from the path) |
| `showDay` | `app.js:9477` (`#day-<date>` opens the Meetings tab and the day) |
| `dayHref` | `app.js:9464` |
| `parkActions` | `app.js:6864` |
| Rewrites | `build_pages.py:254` `COMMITTEE_TAB_SLUGS=("sessions",)` → `REDIRECTS` at :292 (`/committee/:code/<slug> /committee/:code 200`); preflight holds the two lists together (`preflight.py:34587`) |

### Shared helpers

These are in `components.js`, on every page: `dateWords(iso)` gives "Apr 7, 2026" by default and
"7 abr. 2026" with `es`; `clock("13:15")` gives "1:15 PM"; `chip`, `icon` and `pchip`.

### Chamber page

`build_full_sessions.py`:
- `day_section` at :183 and its JS twin in `SCRIPT` at :277, which "preflight holds the two to the
  same markup";
- the term files are fetched by `SCRIPT.show(t)`;
- `/session/house` is a name of its own beside `/session/H/` (see its docstring).

### Study page

`build_study_committees.py`: `player` at :606, `meeting_html` at :621, `meetings_html` at :651 and
`page_body` at :720 (the W4 sections). `OPEN_JS` opens `#day-<date>`.

### Building the recordings

| Need | Where |
|---|---|
| The index | `proceedings.video_indexes()` at :85 |
| A date's term | `proceedings.term_on(day)` at :218 (Organization Day goes with the new term) |
| A name to a page | `build_committees.who_sits().code_of(name, chamber, term)` |
| Index reader | `build_calendar.recordings_by_day()` at :372 (the pattern) |

### Precedent for one component drawn in two languages of code

`build_pages.calendar_html()` ↔ `app.js` `calendarBlock()`, with preflight failing if the class names
drift.

### Spanish

`i18n.PAGES` (`i18n.py:130`) lists the home page, glossary, resources, officials, guides and Learn.
**Committee, chamber, session-day and study pages have no Spanish today.** Existing keys this tab can
use:
- `cal.n_bills` and `cal.one_bill`;
- `cal.recording` ("La grabación, en YouTube");
- `kind.*` (public hearing → "Audiencia pública", executive session → "Sesión ejecutiva", work
  session, subcommittee and full committee work session, session day → "Día de sesión", study and
  statutory committee);
- `sess.play` ("Reproducir"), `sess.rec_house` and `sess.rec_senate`;
- the glossary's "votación nominal" for roll call, and "la Legislatura" for the General Court.

---

## 4. What a row can honestly say

| Field | Source | Committee | Chamber | Study page |
|---|---|---|---|---|
| Date ("Apr 7, 2026") | the recording's own date (index `parsed_date`, else its `start_eastern` day) | yes | yes | yes |
| When it began ("1:13 PM") | index `start_eastern` (YouTube's actualStartTime) | yes, where known | yes | yes |
| Length ("1 h 52 min", "36 min") | index `duration_iso` | yes, where known | yes | yes |
| Kind | committee: the kinds of the bill rows placed in it, as the Meetings tab's chips (`kindChips`). Title-matched with no bill: only what the title says ("Division II"), never a guessed kind. Chamber: "Session Day". Study: the database's meeting type ("Regular meeting") | yes | yes | yes |
| Bills | committee: the bills whose rows carry this `video_id`, in the order taken up (by `start`), with links; a count and the first three numbers in the row. Chamber: counts only ("65 bills · 9 roll calls"), because the owner said on 10 October not to list bill numbers on the chamber page. Study: none (meetings on no bill) | yes | counts | no |
| The bill's moment | `items[].start`/`state`/`inferred` → jump buttons, plain or *approximate*, under the player only | yes | no (the day page has them) | no |
| Scheduled time and room | `items[].time` span and `venue` (committee), `time` and `venue` (study), from the record | in the detail | no | in the detail |
| Link to the meeting | committee: "This meeting" → `dayHref(date)` (Meetings tab, that day) where the page has a meeting that day; "On the Calendar" → `calendar?week=<ISO week>&day=<date>` for dates from 2025-01-01. Chamber: "The full session day" → `session/H/<date>`, plus the journal PDF. Study: "This meeting on the Calendar", as `meeting_html` writes it | yes | yes | yes |
| The recording's own link | `https://www.youtube.com/watch?v=<id>`, as "On YouTube", in the `.pbar` | yes | yes | yes |
| A recording no bill row places | "The record ties no bill to this recording." Never "no bills were discussed": Senate Finance's April-May 2026 recordings are untied because the Senate docket lists no Finance rows those days. Where the same committee has a meeting that day on this page, also "This committee's meeting of Apr 7 lists 2 bills" with a link | yes | n/a | n/a |
| Finance divisions | label from the title ("Division I/II/III"). Bills are never assigned: the docket's `candidate_ids` say which recording each bill was in is not established, and the detail says so in the Meetings tab's words | H34 | | |

The page never shows a caption or a transcript line. The words in a row are the record's and the
recording's own facts (date, start, length, title words), not captions.

---

## 5. THE SPEC

### 5.1 Name, where it appears, addresses

**The tab is named Videos.** The bill page's tab was renamed Hearings because it listed sittings
without recordings. This one lists only recordings, so "Videos" is exact. The count beside it is the
number of recordings in the term the page shows.

| Page | Where the view goes | Opens on | One recording |
|---|---|---|---|
| Committee (`/committee/<code>`) | a third tab after Meetings: **Bills \| Meetings \| Videos**. It appears only if the committee has a recording in any term (46 of 86 pages) | `/committee/H07/videos` | `/committee/H07/videos#v-<videoId>` |
| Chamber (`/session/house`, `/session/senate`) | a tab strip under the term select: **Session Days \| Videos**. The Order select moves into the Session Days pane | `/session/house/videos` | `/session/house/videos#v-<videoId>` |
| Study or statutory (`/committee/ss<id>`) | a W4 section **Videos**, after Members and before Meetings, only where a meeting has a recording (15 of 152). These pages have no tabs, and adding a strip for one view is a second system | `/committee/ss57/videos`, which scrolls to the section | `/committee/ss57/videos#v-<videoId>` |

**Addresses.**
- Add `"videos"` to `COMMITTEE_TABS` (`{sessions:1, videos:2}`) and to `COMMITTEE_TAB_SLUGS`.
- The existing rewrite `/committee/:code/videos /committee/:code 200` then serves both committee
  pages and `ss` pages.
- Add two lines to `REDIRECTS`: `/session/house/videos /session/house 200` and
  `/session/senate/videos /session/senate 200`.
- No tab address goes in the sitemap; the canonical link stays the page's own, as today.

**Deep link.** The hash is `#v-<videoId>`. YouTube ids may begin with `-`, so `#v--vjHAnQ1eXM` is a
valid deep link.
- On a committee page the term is not in the address. A hash naming a recording of another term
  switches the page to that term (`PAGE.term`, `ensureTerm`) and opens Videos with it chosen.
- A hash naming no recording on the page leaves the newest chosen and says nothing.
- `#v-...` on another tab is asking for Videos, as `#day-...` asks for Meetings in `showDay`, and is
  tried once.
- `showDay` already ignores any hash that is not `#day-YYYY-MM-DD`.

**Choosing a row writes its address** with `history.replaceState`, as `tabAddress` does. The
address is shareable and no history entry is added per row.

### 5.2 Data: no new files

Measured by `check_site`, the deploy's file count does not change.

**Committee pages.** `build_committees.py` writes one more key into each `site/committee/<code>.json`:

```json
"recordings": [
  {"id": "itJRViVSJqk", "date": "2026-04-07", "term": "2025-2026",
   "began": "13:13", "seconds": 6712, "label": "Division II"}
]
```

- **Order:** newest first.
- **`began`, `seconds` and `label`:** present only when known.
- **Which recordings:** every `video_id` on any of the committee's `items` (tied), plus every index
  recording that **no proceedings row carries** and whose `parsed_committee`, read through
  `code_of(name, chamber-of-the-channel-file, proceedings.term_on(date))`, is this page.
- **Finance divisions:** `parsed_committee` matching `^Finance\s*-?\s*Division\s+(I|II|III)$` on the
  House channel goes to House Finance, with `label` "Division I/II/III".
- **Nothing else is matched** (no fuzzy words), so older-form titles that no bill places stay off.
  The build prints how many: about 554 index rows are in the older form, most of them already tied by
  their bills.
- **Bills, kinds and moments** come from `sessions[].items` with that `video_id`, which the page
  already holds. `recordings` carries no bill list.
- **Size:** about 3,418 entries across 46 files at about 90 bytes each, roughly 300 KB in total. The
  largest file is H34 with 308 entries (about 28 KB), on files of 1 to 5 MB today.
- **Silence is not success.** The step prints "N recordings on committee pages: T by their bills, M
  by their titles; U titled for no page". It stops if proceedings carries video ids and the index
  reads as empty: the index is in git, so empty means a broken checkout.

**Chamber pages.** `build_session_pages.day_record` (`:3429`) gives each day of the term files:
- `recordings: [{"id","began","seconds"}]`;
- where no moment names a recording, the index's "<Chamber> Session (MM/DD/YYYY)" recording of that
  date from that chamber's channel (`parsed_committee == "Session"`). That adds 108, from the 2021-22
  term on.
- `videos` (ids) stays for the readers that use it.
- The chamber page writes the latest term's Videos pane into its HTML, as it writes the latest term's
  days. Other terms come from the term file `SCRIPT` already fetches.

**Study pages.** Static. The build reads each meeting's `video` (unchanged) plus `began` and
`seconds` from the index, and writes the section into the page. It writes no JSON.

**One component.** There is a JS renderer in `components.js` (on every page) and a Python one in
`components.py`.
- The committee tab (`app.js`) and the chamber page's other terms (`SCRIPT`) call the JS one.
- The chamber page's latest term and the study pages call the Python one.
- preflight holds the two to the same markup, as `calendar_html` and `calendarBlock` are held.
- One click and keydown handler in `app.js` serves every page (`[data-vpick]`, below).

### 5.3 Layout

**At 1280** (measured in the mock: pane 1,132 px wide):

```
┌───────────────────────────── pane ─────────────────────────────┐
│ ┌────────────── player 16:9 ─────────────┐ ┌─ 51 recordings in ┐│
│ │                                         │ │   2025–2026       ││
│ │           ▸ Play the recording          │ │▌May 12, 2026  12:58 PM · 1 h 49 min
│ │                                         │ │ Hearing           ││
│ └─────────────────────────────────────────┘ │ 2 bills: HB 1042, ││
│  Senate Finance · May 12, 2026   On YouTube  │ HB 1491          ││
│  May 12, 2026 · began 12:58 PM · 1 h 49 min  │ May 5, 2026 ...  ││
│  [Public Hearing]  Set for 1:00 PM, SH 103   │ ... scrolls ...  ││
│  HB 1042  title…   ▸ 00:03:45                │                  ││
│  HB 1491  title…   ▸ 00:09:12  approximate   │                  ││
│  This meeting · On the Calendar              └──────────────────┘│
└────────────────────────────────────────────────────────────────┘
```

- The grid is `minmax(0,1fr) minmax(18rem,22rem)` at ≥60em, the site's breakpoint for `.cmlay`. The
  mock measured a player of **718 × 447** (about 64% of the pane) and a list column of **352 px**.
- The left column holds the player (`.player`, margin-top 0), the `.pbar` (who, date, On YouTube,
  status line), then the chosen recording's detail. The detail is one line of facts with kind chips,
  "Set for <time> in <room>" from the record, the bills in order with title and moment buttons,
  then the links.
- The right column is `align-self:start; position:sticky; top:var(--sp-5)`, as `.cmplay` is.
  - It has a small heading, "51 recordings in 2025–2026", over an `<ol>` with
    `max-height: calc(100vh - 8rem); overflow:auto`. The list stays in view while a long bill list
    (H43: 26 bills) scrolls past.
  - The chosen row is scrolled into view inside the list on arrival with `list.scrollTop` and
    `block:nearest` arithmetic, never `scrollIntoView` on the page.
- Each row is three short lines. Mock row height is 64 to 110 px.
  - Line 1: **date** on the left; began · length on the right, in small ink-2.
  - Line 2: kind chips, and the label chip ("Division II").
  - Line 3: "7 bills: SB 408, SB 534, SB 538 and 4 more", or "The record ties no bill to this
    recording". On a chamber page it reads "65 bills · 9 roll calls". On a study page it gives the
    meeting type and room.
- The chosen row has a 4 px pine left bar and the wash background (`aria-current="true"`).

**At 390** (the mock: pane 366, player 348 × 238). One column, in this order:
1. the player (full width);
2. the `.pbar`;
3. the chosen recording's detail;
4. the list heading;
5. the list, as a bounded scroll box with `max-height: min(60vh, 32rem)`, because the owner asked for
   a scrollable playlist.

The flowing alternative was 10,012 px for House Finance's 106 rows. The tab strip
**Bills · Meetings · Videos** fits at 390 without scrolling: Videos 106 on House Finance was measured
in the mock.

**Study pages** have W4 sections, which put the heading in a left column. The Videos section's body
spans the full content width under its heading, so the player keeps most of the width.

### 5.4 Choosing a recording

**Default.** The newest recording of the term is chosen as a still: the `.pstub` button with the
play icon and "Play the recording", and `data-title`, for example "Recording of the Senate Finance,
May 12, 2026". Nothing is fetched from YouTube: no thumbnail, no iframe, no script.

**A row is a link** (`<a href=".../videos#v-<id>" data-vpick="<id>">`).
- A plain left click or Enter chooses the recording in place: `preventDefault`, then `replaceState`.
- A modified or middle click falls through to the link, so the reader gets the page in a new tab,
  opened on that recording, as the site's bill-list links do.
- The row holds no other control. Bill links live in the detail, so nothing interactive is nested.

**Before a first press** (no frame in this view):
- Choosing replaces the still's `data-embed` (`<id>|0|<pid>`), `data-title` and `aria-label`, the
  `.pbar` (date, On YouTube link) and the detail. Nothing loads from YouTube.
- **Focus moves to the Play button.** Its name ("Play the recording of the Senate Finance, May 12,
  2026") tells a screen reader what was chosen, and Enter plays it.
- The player is brought into view (`block:"nearest"`), which matters on a phone where it is above the
  list.

**After a first press** (a frame is open in this view): the reader has pressed Play in this player,
so choosing a recording is choosing what it plays.
- The frame's `src` becomes the new id with `autoplay=1`, and its `title` is updated.
- Focus stays on the row, so the reader can keep choosing.
- The `.pbar`'s status line (`role="status"`, polite) says "Playing: May 5, 2026".
- This is the one case where a frame loads a recording without a press on that recording's own Play.
  See Q1.

**Moment buttons.** A bill's ▸ time in the detail is `[data-seek="<pid>|<t>"]` on this player's pid,
handled by the existing seek handler: it builds the frame at that time, or seeks an open one.
- Plain where stated; *approximate* where inferred, exactly as `meetingLine`.
- Recordings with no moment for a bill show no button for it.
- The pid is per recording (`meetingPid`'s form), so a time moves only its own player.

**Redraws must not stop a playing recording.** An iframe moved or recreated in the DOM reloads.
- Choosing a row updates the player, the detail and `aria-current` in place, by targeted DOM
  changes, and never through `renderPage`.
- On a committee page `renderPage` redraws `#results` when the term index, `home.json` and the
  officers arrive. While the Videos pane holds an open frame, it must leave that pane as it is and
  redraw only the head.
- Changing the term, or leaving the tab, ends playback and draws the newest of that term as a still.
  That is expected.

### 5.5 Keyboard and screen reader

**The tab** is the existing `role=tab` button. Arrows, Home and End already work (`app.js:10478`),
and the pane is `role=tabpanel` `#ppane`. On the chamber page the strip uses the same markup and its
`SCRIPT` toggles the two panes, with `hidden` on the inactive one.

**Order in the document** (which is also the Tab order): Play (or the frame) → On YouTube → the
detail (moment buttons, bill links, This meeting, On the Calendar) → the list heading → the rows. At
1280 the list sits to the right but comes after the detail in the DOM. That matches the reading
order: what is playing, then what else there is.

**The list** is `<h3 id="vlh">51 recordings in 2025–2026</h3><ol aria-labelledby="vlh">` with one
link per row.
- The chosen row has `aria-current="true"`.
- A link's name is its text: "May 12, 2026, 12:58 PM, 1 h 49 min, Hearing, 2 bills: HB 1042, HB
  1491". The middle dot (`&middot;`) is `aria-hidden` and a comma is spoken instead.
- Rows are plain links in Tab order, as the site's other lists are. Roving tabindex was considered
  and rejected as a second widget system (Q3).

**Focus.** Every focusable element gets the site's focus ring, inside the list's overflow, so use
`outline-offset:-2px` as `.pstub` does. The frame keeps the focus the Play button had, which the
existing handler already does.

**Without script.** Static study and chamber pages show the still, On YouTube and the rows as links;
`#v-` does nothing. On the chamber page both panes are visible stacked until the script hides one.

### 5.6 Empty states

| Case | What shows |
|---|---|
| Committee with no recording in any term | **No tab.** 40 of 86 pages: the former committees from before 2020, and s100 (Senate Special Committee on Redistricting). s100's 10 recordings from 2021 have older-form titles ("Senate Special Committee on Redistricting- Merrimack County- Sep. 14, 2021") that the strict match leaves off |
| Committee with recordings, none in the chosen term | The tab stays, with no count. Pane: "No recording of this committee from 2017–2018 is on file." For a term before 2019-2020, add "Recordings here begin in May 2020, with the General Court's YouTube channels.", the sentence already on bill pages, which preflight ties to `about_figures.STREAM_START_WORDS` |
| Chamber, a term with none (2019-20 and earlier) | The tab stays. "No recording of the House's session days in 2019–2020 is on file." plus the same sentence |
| Chamber term with some days unrecorded (House 2021-22: 15 of 26) | Only the recorded days are rows. The heading counts recordings, not days |
| Study page with no recorded meeting | **No section** (137 of 152) |
| A recording whose start or length is unknown | That part is left out. There is no "unknown" and no dash |
| Recording tied to no bill | "The record ties no bill to this recording." (see §4) |
| Recording newer than the index the build read | Not listed until the night's index has it. Nothing is guessed from the docket alone |

### 5.7 Words (English, then the Spanish draft for `lang/es.json`)

These pages have no Spanish today (`i18n.PAGES`). The keys go in now as `"state": "draft"` so the tab
is ready when the pages are added; the proofreader passes them. Reuse the existing keys wherever they
fit.

| Key | English | Spanish (draft) |
|---|---|---|
| `vid.tab` | Videos | Videos |
| `vid.count` | {n} recordings in {term} | {n} grabaciones de {term} |
| `vid.count_one` | 1 recording in {term} | 1 grabación de {term} |
| `vid.play` | Play the recording | Reproducir la grabación |
| `vid.rec` | Recording of the {name}, {date} | Grabación de {name}, {date} |
| `vid.on_youtube` | On YouTube | En YouTube |
| `vid.began` | began {time} | comenzó a las {time} |
| `vid.len_h` | {h} h {m} min | {h} h {m} min |
| `vid.len_m` | {m} min | {m} min |
| `vid.set_for` | Set for {time} in {room} | Programada para las {time} en {room} |
| `vid.no_bill` | The record ties no bill to this recording. | El registro no vincula ningún proyecto de ley a esta grabación. |
| `vid.meeting_lists` | This committee's meeting of {date} lists {bills}. | La reunión de este comité del {date} incluye {bills}. |
| `vid.this_meeting` | This meeting | Esta reunión |
| `vid.on_calendar` | On the Calendar | En el calendario |
| `vid.full_day` | The full session day | El día de sesión completo |
| `vid.playing` | Playing: {date} | Reproduciendo: {date} |
| `vid.none_term` | No recording of this committee from {term} is on file. | No hay ninguna grabación de este comité de {term} en el registro. |
| `vid.none_chamber` | No recording of the {chamber}'s session days in {term} is on file. | No hay ninguna grabación de los días de sesión de {chamber} de {term} en el registro. |
| `vid.begin` | Recordings here begin in May 2020, with the General Court's YouTube channels. | Las grabaciones de este sitio comienzan en mayo de 2020, con los canales de YouTube de la Legislatura. |
| `vid.division` | Division {n} | División {n} |
| `vid.approx` | approximate | aproximado |
| (existing) | {n} bills / 1 bill | `cal.n_bills` / `cal.one_bill` |
| (existing) | Public Hearing, Executive Session, Work Session… | `kind.*` |
| (existing) | Session Day | `kind.session_day` "Día de sesión" |
| (existing) | roll calls | "votaciones nominales" |

Dates use `dateWords(iso)`: "Apr 7, 2026", or "7 abr. 2026" with `es`. Times use `clock()`: "1:13
PM", or "1:13 p. m." in Spanish.

### 5.8 Checks to add (preflight)

- **Tab slugs.** `COMMITTEE_TABS` and `COMMITTEE_TAB_SLUGS` stay equal, through the existing check.
  The two new `/session/<house|senate>/videos` rewrites are present.
- **Markup.** The JS and Python renderers of the Videos component emit the same classes and
  attributes, as `calendar_html` and `calendarBlock` are held.
- **No YouTube before Play.** On the fixture site, no page in its static HTML or in `app.js`'s first
  render of the Videos tab carries an `iframe`, `img` or `script` from youtube.com, youtube-nocookie
  or ytimg. Every `data-embed` is a button.
- **Timestamps.** The Videos detail's moment buttons for a recording equal the Meetings tab's for
  the same items: same seconds, same *approximate*. This guards "nothing about timestamps changes".
  No run of `probe_alignment` is needed, because no method changes.
- **Recordings and bills agree.** Every `recordings[].id` that a committee's items carry is listed
  once. No id appears on two committee pages. A title-matched id is on no proceedings row.
- **Silence.** The build prints for both `build_committees` and `build_session_pages`, as in §5.2.
- **Data checks**, where the kit is present: House Finance has three Division recordings on its
  division days, and Senate Finance lists its 12 May 2026 recording.

### 5.9 Not in this change

- Pages for the livestreamed bodies that have none (§1).
- Study recordings before 2025: the database has no meetings to attach them to.
- Older-form titles from 2020-22 that no bill places.
- Committees of conference.
- Session-day pages (`/session/H/<date>`) taking the index's recording where no moment names one.
  The same fallback could feed them; that is a follow-up.
- Changing the Meetings tab's own players.
- Any change to how timestamps are found.

---

## 6. Questions for the owner

1. **After the first press, should choosing another recording play it straight away?** This spec
   says yes, as a YouTube playlist does. The privacy text says "a player only loads if you press
   play", and here a player is already open. The alternative: every choice returns to a still and
   needs its own Play.
2. **Study and statutory pages: a Videos section or tabs?** They have no tabs today, so the spec
   gives them a Videos section in their W4 layout. Should they instead get a tab strip, for example
   About | Meetings | Videos, like committee pages?
3. **The list as plain links.** The spec makes rows plain links, one Tab stop each (House Finance has
   106 this term). The alternative is a single Tab stop with arrow keys to move and Enter to choose.
   Is the simpler form acceptable?
4. **Recordings the docket ties to no bill.** Should these be listed on the committee's page? There
   are 218 this term, such as Senate Finance's April-May 2026 meetings and the House Finance
   divisions. The spec lists them, matched only by an exact committee name in the channel's own
   title (and the three Finance divisions), each marked "The record ties no bill to this recording".
5. **Chamber page tab name.** Should the first tab be named "Session Days", matching the page's
   title?
