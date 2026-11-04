# Election results: design (draft for the owner)

Status: **design only, first draft, 4 November 2026.** Nothing here is built, and
nothing reaches the site until the owner approves it. Branch
`design/election-results`.

The owner's words (4 November 2026): "having a reliable, up to date results page
for all the positions up and down the ballot would be such a better system than
the way we do it now." They pointed to nhelectionresults.org/contested as the sort
of display they want.

**Labels used below:** **seen** (I fetched or opened it today), **read** (code
or a cited page), **reported** (a secondary source says so; the primary was not
read), **guess**.

**What I asked of other servers today:** six requests to nhelectionresults.org
(home, `/contested`, `/api/topline`, one board, one district's results) and
three to WMUR's election hub (widgets 1318, 1321 and 1323). All six used a plain
client named `granite-record-design/1.0`, about two seconds apart, with no
polling. A research helper read news pages and searched the web. Nothing went to
gc.nh.gov. sos.nh.gov refused the helper (403), and nobody tried to get round
that.

---

## 0. The design on one page

- **One page per election**, under Officials: `/elections/2026-general`,
  `/elections/2028-primary` and so on. It opens on an overview. Below that come
  tabs, one for each kind of office.
- **On election night it fills in by itself**, the way Live Now does. One small
  program (a Worker) reads one outside source every few minutes and writes a
  file to the live layer's store. The static page reads that file. The
  election-night version of this needs the owner's approval as a new running
  piece (CLAUDE.md).
- **It shows reported counts only.** Every card names its source and its time.
  It never makes a race call of its own. A seat is counted toward a party only
  once every polling place in that district has reported. Even then the page
  says "most votes", not "elected".
- **The Secretary of State's files are the final word.** Once they are saved and
  read, they replace everything unofficial, race by race. "Elected" then follows
  the rule the site already uses for members-elect: past the recount deadline,
  or the recount's own count.
- **Winners link to their member pages** through the same matching file the
  members-elect flow already uses.
- **The source is still open.** No feed I found states who runs it, where its
  numbers come from, or terms that would let us republish it. §1 recommends
  asking two of them for permission and getting a quote from the AP. The owner
  sends those requests; drafts are in §8.
- **The target date has moved.** NHPR reports that the state primary moves to
  June starting in 2028 (§1.7). The first live test would then be June 2028,
  not September.

Mock (2024 official, finished election), 1280 light:
`mock/2024-1280-light.png`; the same at 390 and in dark: `mock/2024-390-light.png`,
`mock/2024-1280-dark.png`, `mock/2024-390-dark.png`.
Mock (2026, election night, **illustrative numbers**): `mock/night-1280-light.png`,
`mock/night-390-light.png`, `mock/night-1280-dark.png`, `mock/night-390-dark.png`.

---

## 1. Sources

### 1.1 The Secretary of State: the final word

- **What it publishes after the election** (read, for 2024):
  - one spreadsheet per county for State Representative;
  - one State Senate spreadsheet covering all 24 districts;
  - counts town by town and ward by ward.

  When a county's file is uploaded again, for a recount or a correction, it
  takes the next number. The 2024 files on disk run from `_0` to `_7`
  (`records/sources/2024-ge-*`). `src/parse/parse_sos_results.py` reads them
  into `collected/election_2024.json`. The files mark no winners.
- **How the count reaches Concord** (reported): each town's or ward's "Return of
  Votes" is "collected and transported by the New Hampshire State Police to the
  Secretary of State's office in Concord". "The deadline for these forms to be
  submitted is 8 a.m. Wednesday, the day after the election."
  (NHPR, 30 October 2024,
  <https://www.nhpr.org/nh-news/2024-10-30/follow-the-ballot-what-happens-after-you-vote-in-nh>.)
  The statute is reported as RSA 659:75. I saw only a search snippet of it, not
  the text.
- **How fast the official results appear** (reported): "official results on the
  Secretary of State's website, which usually takes two days to complete"
  (InDepthNH, 2022 primary, a search snippet).
- **Election-night live results from the SoS: unknown.** I could not read
  sos.nh.gov. **For the owner to open in a browser:**
  <https://www.sos.nh.gov/elections/elections/election-results>, and the 2026
  results page. Two questions: does anything appear on the night itself, and are
  the other offices' files (Governor, Council, Congress, county offices,
  questions) spreadsheets as well?
- **Terms:** a public record. The site already republishes the 2024 files.
- **What it takes:** what the site does now. A person saves each file in a
  browser, and the reader reads it. The reader covers only House and Senate
  today; the other offices need new readers (§6).

### 1.2 The Associated Press

- **How it collects** (reported): "The AP hires vote count reporters who work
  with local election officials"; "If any of the results are available from
  state or county websites, the AP will gather the results from there, too."
  (AP, carried by WDIV, 3 March 2026.)
- **New Hampshire specifically** (reported, AP Decision Notes, via WCAX, 22
  October 2024): "New Hampshire reports its vote at the township or ward level,
  not by county"; "Each town or ward usually releases all of its results in a
  single update."
- **Race calls:** "The AP does not make projections and will declare a winner
  only when it has determined there is no scenario" in which the trailing
  candidate could win (same source).
- **Who uses it in New Hampshire:**
  - NHPR: "We will use AP's data to populate our election results pages"
    (NHPR, 5 November 2024).
  - The Boston Globe's New Hampshire pages say "Source: AP" and show "a
    town-by-town breakdown".
- **Does it cover all 400 House seats and the county offices? Unsourced.**
  NHPR's note names federal and statewide races only.
- **Licence:** paid. "Requires a (paid) account with the AP" (elex
  documentation). **No source gives a price.** One precedent: in 2024 AP made
  "some of its U.S. elections data available for free" to small members of the
  Institute for Nonprofit News (KSAT, 14 February 2024). Whether Granite Record
  could qualify is a question for the owner.
- **Reliability:** the best documented method of any source here. Its race
  calls are a judgment (§4).

### 1.3 WMUR (Hearst Television) election hub

- **Seen:**
  - JSON widgets at `https://ehub.htvapps.com/wmur/wp-json/election-hub/v1/widget/<id>`:
    1318 (State House, 203 races, 400 seats), 1321 (State Senate, 24) and 1323
    (Executive Council, 5). 1326 (County) was not fetched.
  - Each race has a title, seats, total votes, polling places reporting and
    expected, and the time of the last update (`2026-11-04T14:41:31+00:00` on
    all three). Each candidate has first and last name, party, whether they are
    the incumbent, and votes.
  - Every race carries `"source":"hearst"`.
  - 146 House candidates carried `"winner": true` at that time. That is a race
    call: somebody's judgment.
- **Not seen:** town-by-town counts, and any statement of where the numbers come
  from or of terms. The research helper could not open wmur.com.
- **Reliability:** a broadcaster that answers for what it publishes. Its method
  is unstated. Its numbers matched nhelectionresults.org exactly in one district
  (§1.5).
- **What it takes:** written permission from Hearst/WMUR to read the widgets and
  republish the counts with credit. The draft is in §8.

### 1.4 nhelectionresults.org

- **Seen:** its own words: "Unofficial results. Compiled from town clerks and
  reported by local volunteers as they come in. Projections are statistical
  estimates from the vote counted so far — not official calls. Official certified
  results come from the New Hampshire Secretary of State."
- **What it covers** (seen):
  - Governor, U.S. Senate and U.S. House.
  - Executive Council, State Senate, State House, "Delegate", Sheriff, County
    Attorney, County Treasurer, Register of Deeds, Register of Probate and
    County Commissioner.
  - Ballot questions, and a September primary view.
- **What it gives** (seen): counts polling place by polling place, with each
  polling place's "reported" flag. On top of the counts it adds its own model:
  a projected total, a probability of winning, and a status for each race
  ("called", "too_close", "unopposed"). Its page refreshes every 30 seconds.
- **Who runs it: not stated.** There is no about page (`/about` and
  `/methodology` return 404) and no terms. The registrant is hidden (RDAP,
  registered 6 April 2025). No news coverage was found.
- **Reliability concerns** (seen):
  - The same page says "of 320 polling places reporting" in one place and
    "282 /316" in another.
  - Its State House totals at the time read 267 won by Democrats and 96 by
    Republicans. WMUR's count at about the same time, for races where every
    polling place had reported, was 207 and 71 (§1.5). The two measure different
    things (its model's calls against complete counts), so this is not an error,
    but it shows how far a projection runs ahead of the count.
- **What it takes:** finding out who runs it, then asking. Until then it is a
  reference to compare against, not a source.

### 1.5 The two feeds side by side (seen, 4 November, mid-morning)

| | WMUR (Hearst) | nhelectionresults.org |
|---|---|---|
| Belknap District 6 (4 seats) | 3 of 3 places; David Nagel 3,492 … Glen Aldrich 3,120 | identical, every candidate |
| Executive Council District 1 | 72 of 92 places; Luz Bay 56,802, Joseph Kenney 51,164 | 82 of 108 places; Luz Bay 63,622, Joseph D. Kenney 59,627 |
| Names | "Joseph Kenney", "Priscilla Bean" | "Joseph D. Kenney", "Priscilla M. Bean" |

- **Guess:** the identical Belknap counts suggest a shared upstream, or one
  feed copying the other. The Council district has 92 polling places in one feed
  and 108 in the other, so the two count "polling places" differently.
- **What follows:**
  - "% reported" depends on whose denominator it is, and the page must say so.
  - Names differ between sources, so linking a person needs the matching step
    (§2), never a string match.
- **The snapshots** are kept in scratch, not in git, with these sha256 hashes:
  topline `cd392aa9…`, house board `f56783db…`, BE6 results `89833ec7…`, WMUR
  1318 `7ec680f3…`, 1321 `592ccd77…`, 1323 `eac417e8…`.

### 1.6 Other sources

- **Towns and cities themselves** (reported): the moderator "publicly announces
  the results" in each polling place. Manchester and Dover post ward results on
  their own sites. That makes 300-odd places with no common format, so it is
  not a feed. It is useful to check a single disputed number.
- **Decision Desk HQ** (reported): it carried State Senate and all 400 House
  seats in 2022 (Granite Memo). It is a commercial licence; no price was found.

### 1.7 Dates that change the plan

- **The state primary moves to June from 2028** (reported, NHPR, 11 May 2026:
  "will move to June starting in 2028", "holding primaries on the second
  Tuesday in June"). The bill and the new RSA 653:8 were not found. **The owner
  should confirm this.** If it holds, the first live election is about 13 June
  2028.
- **The recount deadline is not a fixed day.** The 2024 deadline was "Friday,
  Nov. 8th at 5 p.m." (NHPR). In 2022 it fell on a Monday, 14 November (Granite
  Memo). RSA 660:1 was reportedly amended in 2025. **The 2026 deadline is
  unsourced here.** `docs/ELECTION_WEEK.md` gives Friday 6 November. That
  should be checked against the Secretary of State's own notice before it is
  entered.

### 1.8 Recommendation

1. **The final word: the Secretary of State's files, always.** They replace any
   unofficial count race by race, as soon as they are read. This needs nothing
   new beyond readers for the other offices.
2. **Primary for the night: ask Hearst/WMUR, and get an AP quote alongside.**
   Two things favour WMUR: it covers every legislative race and the Council, and
   it is a publisher that answers for its numbers. AP is the better-documented
   method, but its coverage of the House is unsourced and its price is unknown.
   Pick whichever says yes first on terms the owner accepts.
3. **Fallback: the other of the two.** nhelectionresults.org only if its
   operator is found and agrees.
4. **If nobody agrees: no live page.** The election page would then appear when
   the Secretary of State's files are read, within days. That is the site's
   present system made fuller and better looking. It is still worth building.
5. **Measure before relying (the project's rule).** When the 2026 SoS files are
   saved, score each feed's snapshot against them race by race. The snapshots
   above are mid-count, so one more snapshot of each feed after the count
   settles (for example on 6 November, three requests) would give a fair score.
   **That is the owner's call.** I have not taken it.

---

## 2. The model

### 2.1 Every office on a New Hampshire ballot

RSA 653:1 is reported to list the Governor, five councillors, 24 senators and
400 representatives, all elected every two years, and "one each of sheriff,
county attorney, county treasurer, register of deeds, and register of probate in
each county". County commissioners vary by county. Rockingham's treasurer,
sheriff, register of deeds and county attorney reportedly have 4-year terms
since a 2022 law. CACR 13 of 2026 would remove the register of probate if voters
ratified it.

| Office | Race key (new, where needed) | Joins to |
|---|---|---|
| President (every 4 years) | `P` | none |
| U.S. Senate | `USS` (and `USS|special` if one occurs) | `corrections/officials.json` `us_senate` |
| U.S. House | `USH|1`, `USH|2` | district map layer `cong` |
| Governor | `GOV` | officials.json |
| Executive Council | `EC|1` … `EC|5` | map layer `exec` |
| State Senate | `S|9` (as now) | `site/districts.json`, map `senate` |
| State House, base and floterial | `H|Hillsborough|18` (as now; floterial flag from districts.json) | districts.json, map `base`/`float` |
| County offices | `C|Belknap|sheriff`, `…|attorney`, `…|treasurer`, `…|deeds`, `…|probate` | County Officials tab |
| County commissioner | `CC|Belknap|2` | County Officials tab |
| Ballot questions | `Q|2026|1` (and a CACR's own bill key) | `corrections/ballot_results.json`, the bill page |
| Delegates (a presidential year) | `DEL|…` | none |

- **A primary** is the same race key plus a party: `S|9#R`, `S|9#D`. Each
  party's primary is its own race with its own seats and winners. The page
  shows one party at a time, Republican first, as every list on the site does.
- **Places:** each race carries its towns and wards as `site/districts.json`
  names them. A drill-down row is a town or a city ward, and its key is the
  place name the district table uses. Floterial districts share towns with base
  districts, and the drill-down shows the same town under both.

### 2.2 People

- A candidate is a name and a party as the source prints them. A winner links
  to a member page only through a match a person has settled. That is
  `corrections/members_elect.json`'s `"matches"` (race and printed name to
  member id, or `null` for someone new), which `election_week.py` already
  drafts.
- Candidates in other races (Governor, Council, county) are matched only to the
  people already in officials.json. Anyone else is shown without a link.
- **Never a string match.** The two feeds spell "Joseph Kenney" two ways
  (§1.5).
- Person numbers (`generated/person_numbers.json`) are reached through the
  member id. Nothing new is issued for a candidate who never served.

### 2.3 Files

- `collected/election_<year>[_primary].json`: as now, from the SoS files, made
  wider to hold every office. Same shape: races keyed as above, each candidate
  with a party, votes, `elected`, `recounted`, and per-place counts. **New:**
  `"places": {"Bedford": [6921, 7295], …}` in candidate order, so the
  drill-down can be built from the official file.
- Live store (R2, the live layer's bucket): `elections/<date>.json`, written by
  the Worker. Each race has the source's name, the time it was read, the
  polling places reported and expected *as the source gives them*, and the
  counts. A source's calls, projections and probabilities are thrown away when
  read, so they can never be shown by accident (§4).
- The page's own file, `/elections/<date>.json`, is built each night from the
  official file where there is one, and points to the live file where there is
  not.

---

## 3. The display

The mocks are drawn in the site's own shell, with `app.css`, `map.css` and the
real `map.js` and 2022 district geometry. They are built by
`mock/build_mock.py.txt` (run from scratch on a fixture build; not a repository
script). The 2024 view uses only the Secretary of State's files on hand. The
2026 view uses illustrative numbers copied from one feed on 4 November and says
so in a box at the top.

### 3.1 What is reused, and what is new

| Piece | From |
|---|---|
| Page shell, title, lead, breadcrumb | every page |
| Tabs by office | Officials' `twntabs` (My Town, Legislators …) |
| A candidate | the one person chip (`pchip`), with the party letter as printed; linked only when matched |
| Status words | `chip` neutral: "Official results", "Recounted"; the members-elect words as they are: "Elected November 3, 2026", "Result not final", "a recount was requested" |
| The map | `map.js` as Officials draws it, with a results file in place of the roster fill; Republican, Democratic, striped for a split district |
| Seats by party | the Learn pages' proportion bar (`l-bar`) and its key |
| Town table | `table.votes` |
| A ballot question | the CACR "voters' card" already on bill pages (ring, Yes/No rows, source) |

**New, with reasons:**

- **A majority line on the seats bar.** The first thing a reader asks of a
  chamber is "who has a majority"; a line at 201 of 400 answers it without
  arithmetic.
- **A thin bar under each candidate's count.** House races run to eight or ten
  candidates for four or more seats, and a ring cannot be read with that many.
  A bar per row can, and on a phone too.
- **A "still counting" hollow segment** (the vacant-seat hollow square's style).
- **On the map at night, a "still counting" outline.** Today the map's hatch
  means a vacant seat. A district not fully counted needs its own word in the
  legend, not the vacancy hatch. That is a small change to `map.js`, not drawn
  in the mock.

### 3.2 The overview

- **Statewide and federal** (Governor, U.S. Senate, U.S. House): one card each.
- **The chambers:** "Seats Won" for a finished election (State Senate 16
  Republican, 8 Democratic; State House 222 and 178, from the 2024 files). On
  the night it reads "Seats So Far", with the count of seats still counting.
- **The map:** House, Senate, Council and US House layers.
- **Closest races:** the last seat's margin in votes, smallest first, each with
  "Recounted" where the file says so. In 2024 the closest was Hillsborough 18,
  by 9 votes.
- **Each tab** lists every race of that office as cards, sorted by county and
  district number, the order the Legislators tab uses. It has a box to find a
  town, the same box as My Town.

### 3.3 A race card

- **Title and meta:** the district; its towns or wards; the number of seats;
  "Recounted" where the count is a recount's.
- **One row per candidate:** the person chip, the count, the share, and a bar.
  - In a finished race (official, past the deadline), the winners carry
    "Elected".
  - In a finished race where a recount was asked for, the card reads "Result not
    final — a recount was requested", the wording the site already uses.
  - On the night, nobody carries "Elected". Where every polling place has
    reported, the top candidates (as many as there are seats) carry "Most
    votes". Otherwise no candidate is marked.
- **"By town and ward":** a folded table with a row per place. On the night,
  places not yet in are listed as "not reported".
- **Footer:** the source by name, the file or the time it was read, and the
  scattered write-ins.
  - A recount card shows the first count beside the recount (Hillsborough 18:
    Kesselring 2,048 then 2,050).

### 3.4 Wording for how much is counted

- **Counts, not percentages, and the source's own denominator:** "72 of 92
  polling places reported". New Hampshire votes in towns and in city wards, so
  "towns" would be wrong for Manchester and Nashua. "Polling places" is what
  both feeds count, and the denominators differ (§1.5), so the page never
  states a percentage it did not compute from a count it can name. "Every
  polling place reported (3 of 3)" when complete.
- **The day's standing line:** "Unofficial count. Updated 9:41 a.m., November 4.
  This page fills in by itself; there is no need to refresh." Once official:
  "Official results. Read from the Secretary of State's results files, saved
  <day>."

### 3.5 Recounts and close races

- **"Result not final — a recount was requested"** only from the Secretary of
  State's recount schedule. The owner enters it in `members_elect.json`'s
  `not_final`, as now.
- **"Too close to call" is not shown in the default design** (§4).
- Close races are shown as a list ordered by margin in votes. That is a fact
  about the count, not a judgment.

---

## 4. Neutrality

Three choices:

1. **No calls, reported counts only (recommended, the default).** The page
   never says who won until the Secretary of State's count says it.
2. **A source's calls, attributed** ("AP has declared …"). This is honest if
   the label is always there. But it puts another organisation's judgment on a
   neutral record, and a call that is later withdrawn stays in readers'
   screenshots.
3. **Our own projections.** No. That is the site's judgment, which it does not
   make.

The two feeds show why option 1 is the default:

- nhelectionresults.org's "too_close" is its own model's probability of 0.505
  in Belknap 6. That is a statistical estimate, not someone saying the race is
  too close.
- WMUR's `winner` flags are calls, by a method it does not state.

The default never shows either. **"Too close to call" appears only where a cited
source states it in words**, for example an AP or SoS statement, with the
source named. In practice that means rarely.

The seat count on the night counts a seat only where every polling place has
reported, and labels it "most votes". That is arithmetic on a complete
unofficial count, not a call, and the page says so beneath the bars.

---

## 5. Lifecycle

| When | What the page shows | What makes it |
|---|---|---|
| Before the night | the races and candidates, "No votes counted yet" | the candidate list; the SoS publishes one (**guess**; to confirm) |
| Polls close to the next morning | the counts as the source reports them; fills in by itself | the Worker, every 2–5 minutes, writing `elections/<date>.json`; the page reads it the way Live Now does |
| The days after | the same, slower; the Worker stops when the source stops changing, or after 3 days | the Worker; then the night's build |
| SoS files posted | race by race, "Official results"; unofficial counts gone for those races | the person saves the files; `parse_sos_results.py`; the night's build |
| Recount deadline to recount results | "Result not final — a recount was requested", then the recount's figures with "Recounted" | `members_elect.json` (`not_final`, `recount_deadline`); the next numbered upload |
| Certification | "Elected" | the existing members-elect rule: past the deadline, or the recount's count |
| History | `/elections/2024-general`, finished | `collected/election_2024.json` (House and Senate only until the other files are saved) |

- **Certification has no fixed date** (reported, NHPR: "There is no deadline
  for the formal certification of election results in New Hampshire"). The
  page therefore keys "Elected" to the files and the recount deadline, as the
  site already does, not to a certification date.
- **History before 2024** needs those years' files saved. Only 2024 is on disk.

---

## 6. Build plan

Effort figures are **guesses**, in working sessions.

1. **The official page, no live part** (2–3 sessions): readers for the other
   offices' SoS files; per-place counts in `collected/`; the page builder;
   history for 2024. It needs nothing from anyone and could cover 2026 once the
   2026 files are saved.
2. **Map results layer** (1 session): a results fill, and the "still counting"
   legend entry, in `map.js`.
3. **The live adapter** (2 sessions, once a source agrees): a Worker in
   `workers/live/` or beside it, reading one source and keeping only counts and
   reporting. Checks and replays run against saved snapshots, as the live layer
   does.
4. **A rehearsal** on a real election night before June 2028: a special
   election, or a September 2027 town vote if the source covers it (**guess**).

**What the owner must do:**

- choose the source;
- send the requests in §8 and say yes or no to any terms;
- approve a new running piece (the Worker);
- confirm the 2028 primary date;
- save the SoS pages listed in §1.1.

**Risks:**

- No source agrees. The page is then official-only.
- A feed changes shape on the night. The adapter refuses rather than guessing,
  and the page says "the unofficial count is not available".
- Names differ between sources. Linking needs the matching step (§2.2).
- Load on election night. The page is static and the live file is cached at
  the edge, as `/api/live/streams` is.
- A source corrects a number after it was shown. The page shows what the
  source says now, with the time.

---

## 7. Open questions, each with a recommended default

| Question | Default |
|---|---|
| Which live source? | Ask WMUR/Hearst; get an AP quote at the same time; take the first acceptable yes |
| Show race calls? | No. Reported counts only (§4) |
| Show "too close to call"? | Only where a cited source says it in words |
| Count seats on the night? | Only where every polling place has reported, as "most votes" |
| Percent or count for reporting? | Count, with the source's denominator |
| Where does the page live? | Under Officials, `/elections/<date>-<general|primary>`; a link from the home page during election week |
| Is the 2028 primary in June? | Plan for June; the owner confirms |
| One more feed snapshot to score against the SoS files? | The owner decides; three requests on 6 November if yes |
| Primaries: one party at a time? | Yes, Republican first |
| Build the official-only page before a source is settled? | Yes. It is useful alone |
| Where does a recount's "not final" come from? | The SoS schedule, entered by the owner, as now |

---

## 8. Drafts for the owner to send (nothing has been sent)

**To WMUR (Hearst Television), digital or news desk:**

> I run Granite Record (graniterecord.org), a free, non-commercial public
> record of the New Hampshire General Court. We would like to show election
> night results for State House, State Senate, Executive Council and county
> races, crediting WMUR on every race, and replacing them with the Secretary of
> State's official files once those are posted. Would WMUR allow us to read the
> election hub's public results widgets every few minutes on election nights
> for that purpose? We would show only the counts and polling places reported,
> not WMUR's race calls. Who should I ask, and on what terms? — Alice Wade

**To the AP (elections data licensing):**

> Granite Record is a free, non-commercial public record of the New Hampshire
> legislature. Could you send a quote, or tell us of any non-profit programme,
> for New Hampshire results down to town and ward for State House, State
> Senate, Executive Council and county offices, for the June 2028 primary and
> the November 2028 general? — Alice Wade

**nhelectionresults.org:** no contact is published. If the owner learns who
runs it, a note like the WMUR one fits.

---

## Sources (read 4 November 2026 unless said)

- nhelectionresults.org: the home page, `/contested` and the API (seen).
- WMUR election hub widgets 1318, 1321 and 1323 (seen).
- NHPR, "Follow the ballot", 30 October 2024 (returns, recount deadline,
  certification).
- NHPR, 5 November 2024, how NPR reports results (AP data).
- NHPR, 11 May 2026, the primary date.
- AP via WDIV, 3 March 2026, how AP counts the vote. AP Decision Notes via WCAX,
  22 October 2024, New Hampshire.
- PBS NewsHour, 7 November 2022 (AP stringers). KSAT, 14 February 2024 (AP and
  INN). elex documentation (paid account).
- Granite Memo, 2022 (DDHQ; recount schedule; Monday deadline). Boston Globe, 8
  November 2024 (recount eligibility, fee). Concord Monitor, 22 October 2024
  (county offices).
- InDepthNH 2022, RSA 653:1, 659:75, 659:84 and 660:1: search snippets only;
  the statute texts were not read.
- On disk: `collected/election_2024.json`; `records/sources/2024-ge-*`;
  `src/pages/components.py` (the members-elect words);
  `workers/live/DESIGN.md`; `generated/district_geometry.json`.
