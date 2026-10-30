# The State Budget: design (phase 1)

A design for a Learn page that explains New Hampshire's state budget in plain
words, with charts: where the money comes from and where it goes, how the
budget is made, and how it changed from the last one. **Nothing here is on the
site.** It reaches the site only after the owner approves the design.

Written 30 October 2026 on branch `design/budget`. Every figure in the mock was
read that day from a source on hand, named beside it. Where no source is on
hand the mock shows a dashed placeholder and this document lists what is
needed.

**The owner's directions (30 October 2026, through the manager):** the page
stays private until every detail is complete and current. Nothing is linked or
published, and it does not go on `dev`. The page links readers straight to the
state's original PDFs (`sources/README.md` gives the addresses). Linking a
General Court address for a reader to click is fine; the project never fetches
one, and das.nh.gov answers this project 403.

What is in this folder:

| Path | What it is |
|---|---|
| `DESIGN.md` | this document |
| `screenshots/state-budget-{390,1280}-{light,dark}-{1,2}.webp` | the mock, full page, on the real built site, each in two parts (WebP holds at most 16,383 pixels a side) |
| `mock/state-budget.html` | the mock page as built (it needs the site's `/app.css`, so open it inside a built `site/`) |
| `tools/` | the scratch scripts that read the sources and draw the mock (below, *How the mock was made*) |
| `figures/figures.json`, `figures/history.json` | every figure the mock uses, as read from the bill texts, with each fund's lines checked against its printed total |
| `figures/actuals.json`, `figures/requests.json`, `figures/capital.json` | the LBA collections, the DAS summary of submissions, and HB 25's capital appropriations, as read and checked (section 1a) |
| `sources/` | the owner's five PDFs and their README (merged from `sources/budget-pdfs`) |

---

## 1. What is on hand, and what each source can support

### HB 1 of 2025 (chapter 140), the operating budget

**Where:** `db/LegislationText.psv` in the kit (the General Court's database
dump of 8 September 2026). Every printing is there: introduced, as amended by
the House, as amended by the Senate, the conference report, the version
adopted by both bodies, the enrolled bill amendment, and the chaptered final
version (stamped 30 June 2025). Read 30 October 2026.

**What it gives:**

- **The revenue estimates, fund by fund (section 140:17, "Estimates of
  Unrestricted Revenue").** Every source of unrestricted revenue, for fiscal
  2026 and fiscal 2027, in four funds: General, Education, Highway, Fish and
  Game. 26 lines, 22 distinct sources. Each fund's lines add up exactly to its printed total
  (checked by `tools/figures.py`). Together: $6,714.0 million for the two
  years.
- **One misprint.** The Highway Fund's gasoline road toll for fiscal 2026 is
  printed "$127,7000,000". The fund's printed total ($259,600,000) is
  $127,700,000 plus its other two lines, so that is the figure used, and the
  mock says so on the page.
- **Reductions the act directs** (sections 140:7 to 140:16): ten agencies, in
  dollars per year or per biennium, and which fund.
- **Positions abolished** (140:5): by position number, in eight agencies.
- **Budget footnotes** (140:1.08), which name the revenue classes agencies
  budget beyond the estimates (transfers, revolving funds, agency income,
  private and local funds) and federal funds.
- **The effective date** (140:18) and the approval date (June 27, 2025).

**What it cannot support: the department line items.** The footnotes apply to
"section 1.01 through 1.07", but the text in the database begins at 1.08, in
every printing of the bill (introduced, House, Senate, both bodies,
chaptered), and 2023's final version does the same. Section 1 (the department
tables: what each department may spend, by fund) is published somewhere other
than the bill text. **So nothing on hand says where the money goes, by
department, or what the budget's total from all sources, federal included,
is.** That is request 1.

### HB 2 of 2025 (chapter 141), the trailer bill

**Where:** the same dump; chaptered final version stamped 23 July 2025.

**What it gives:** the full text (about 530,000 characters, sections 141:1 to
141:461) and its **analysis, a numbered list of 247 changes** to the law
(four of them, 150, 153, 154 and 245, are printed without the full stop after
the number; the numbering itself runs 1 to 247 unbroken). The page can show
that list verbatim and link each change to its section.

**What it cannot support:** amounts in a form a chart can use. Its
appropriations are scattered through the sections in prose; totalling them
would be our arithmetic, not the state's.

### Earlier budgets (2015 to 2023)

**Where:** this project's saved pages `legislation/<year>/HB0001.html` (the
final versions), and `db/past/PastLegislationText.jsonl`.

**What they give:** each budget's own revenue-estimate table, so the page can
compare this budget with the last one (HB 1 of 2023, section 106:9) and show
six budgets' estimates side by side (2016-2017 to 2026-2027). All six General
and Education Fund tables sum to their printed totals. 2017's General Fund
total is printed "1,538,700,000 , 1,572,700,000" (a stray comma), read by
hand.

**What they cannot support:** budgets before 2015. The saved pages for
1999-2013 carry no estimate table the scratch parser can find, and those of
1995 and 1997 parse only in part (another layout). Not pursued; open question 9.

### The docket and the roll calls

**Where:** `Docket.txt` (the day files, in the kit) and
`records/rollcalls/RollCallSummary_2025.txt` (in git).

**What they give:** the whole 2025 path of both bills, dated: introduction
(February 20), House Finance hearing (March 12) and vote (14-11, April 3),
House passage (April 10: HB 1 192-183, HB 2 185-175 after 26 roll calls that
day), Senate Finance hearing (May 6) and report (6-2, dated June 5 in the
calendar), Senate passage
(June 5: HB 1 15-9, HB 2 14-10), the committee of conference (conferees, six
meeting days June 12-19), the conference reports (June 26: House HB 1 failed
182-183, reconsidered, adopted 185-180; HB 2 adopted 184-183; Senate 16-8
both), and the Governor's signature (June 27). Roll calls per bill: HB 1, 5
House and 3 Senate; HB 2, 29 House and 16 Senate. The bill pages already show
every one of them with each member's vote.

**What they cannot support:** the Governor's proposal itself (what was asked
for, against what was passed). The docket starts at introduction.

### The law

- **RSA 9** (in `db/NH_RSA.psv`, dumped 26 October 2026, and on the site at
  `/laws/9`): the calendar (9:4 and 9:5, October 1; 9:6, November 1; 9:2 and
  9:2-a, February 15), the Governor's role (9:8) and the balanced-budget rule
  (9:8-b).
- **The Constitution, Part Second, Article 18** (money bills originate in the
  House; the Senate may propose or concur with amendments) and **Article 18-a**
  (a budget bill may hold only operating and capital expenses, and no other
  change to statutory law): `collected/constitution.json`, read from nh.gov on
  17 October 2026. With RSA 9:2-a, which makes the trailer bill "separate from
  the document known as the budget" and "not ... a budget bill as provided in
  part II, article 18-a", this is why the budget is two bills.
- **RSA 77**, Taxation of Incomes: "Repealed by 2021, 91:99, II, eff. Jan. 1,
  2025." Chapter 91 of 2021 is HB 2 of 2021 (`db/past/PastLegislation.psv`).

### Fiscal notes

None on hand for HB 1 or HB 2 of 2025. The database's `FiscalImpactCode` is
False for HB 1 and True for HB 2, but no fiscal-note text is in the dump.

### The owner's printouts

`records/sources/printouts/INDEX.csv` lists none on the budget.

### HB 25 of 2025 (chapter 159), the capital budget

**Where:** the same database dump; chaptered final version. Read 30 October
2026. Found because the DAS capital presentation's process slide ends at
"House Bill 25".

**What it gives:** HB 25 has been titled "making appropriations for capital
improvements" in every odd year from 1999 to 2025, and a variant of it in 1993,
1995 and 1997 (`PastLegislation.psv` and `Legislation.psv`). In 2025 it went to House Public Works and Highways and
Senate Capital Budget, and was signed July 15, 2025, as chapter 159 (docket).
Section 159:1 gives 17 paragraphs, one per department or agency; 16 print a
"Total state appropriation". The 16 paragraphs that print one add up exactly to
the printed section total, $137,678,945. The Fish and Game Department's
paragraph prints none: its three projects ($2,379,000) are "Less Other Funds
(Fish and Game Fund)". Section 159:2 adds $10,000,000 of highway funds.
Section 159:7, "to provide funds for the total of the appropriations of state
funds made in sections 1 and 2", authorizes the treasurer to borrow up to
$171,060,895, and gives "the source of funds" as general fund $137,678,945,
highway funds $10,000,000 and other funds $23,381,950. Those three add up to
the total. The other funds are the "Less Other Funds" lines of section 1: the
revolving loan fund $19,700,000, the Fish and Game Fund $2,379,000 and the
Plate Fund $1,302,950. Those three add up too. The project lines inside each paragraph mix gross
amounts and "Less Other Funds" deductions, so the page uses the paragraph
totals only.

---

## 1a. The owner's sources of 30 October 2026

Five PDFs, merged from `sources/budget-pdfs` (9a6c457) into `docs/design/budget/sources/`,
each read 30 October 2026 and checked as below (`tools/actuals.py`,
`tools/requests.py`, `tools/capital.py`).

### LBA: General and Education Trust Fund revenue collections, FY 2020 to 2026

*Revised, "As of 06/30/26, Cash Basis"; "Source: DAS Monthly Revenue Focus
Reports."* Eleven pages: 19 tables, one per source, plus a combined business
taxes table and a grand total. Each table gives each month and the year to
date, for every fiscal year from 2020 to 2026.

- **Checks:** every table's twelve monthly figures sum to its June
  year-to-date figure, to rounding. The business profits tax plus the
  business enterprise tax equals the combined table. In every year, the
  sources sum exactly to the printed grand total: FY2020 $2,483.4M, FY2021
  $2,966.5M, FY2022 $3,229.0M, FY2023 $3,230.2M, FY2024 $3,340.5M, FY2025
  $3,138.8M, FY2026 $3,178.1M.
- **Oddities, as printed:**
  - The business enterprise tax's header reads "FY 2025 FY 2025" where the
    first column must be FY 2026, as on every other table.
  - The state property tax for FY2023 is $263.1M, against about $363M in
    every other year. Its own months sum to it, so it is not a slip of one
    cell; the PDF does not say why.
  - The grand total's "Y.T.D.*" carries an asterisk with no footnote in the
    text.
- **What it makes possible:** request 3, done. It shows actual collections
  against HB 1's estimates for the General and Education funds together:
  - FY2024: $3,200.1M estimated, $3,340.5M collected.
  - FY2025: $3,190.5M estimated, $3,138.8M collected.
  - FY2026: $3,038.5M estimated, $3,178.1M collected.

  It also gives seven years of collections, and source-by-source
  comparisons for lines whose names match.
- **What it cannot:** the Highway and Fish and Game funds; spending. Nor does
  it say whether HB 1's estimates are on the same cash basis.

### LBA: the FY 2026-2027 operating budget page (the owner's printout)

A printout made with Print to PDF, so it holds the link text and none of the
addresses. It lists, among much else:

- the Governor's Recommended Operating Budget (PDF and Excel), the Executive
  Budget Summary and the Trailer Bill Language: **request 5**;
- HB 1 Introduced, House Passed, Senate Passed, and **"HB 1 Chaptered Final
  Version (PDF)" and "(Excel)"**: almost certainly **request 1**, the section 1
  tables (a guess until opened);
- HB 2 at each stage, and "HB 282 Chaptered Final Version (PDF)". HB 282 of
  2025 is chapter 142, on first responders' benefits, education adequacy
  grants and group II retirement benefits. Its being on the budget page is
  worth an open question.
- the Committee of Conference documents, including both conference reports:
  **request 7**;
- surplus statements for every fund at every stage, the last "General and
  Education Trust Fund Surplus Statements - 06/27/25";
- revenue estimates (Senate to House, Department of Revenue, Insurance
  Department);
- compare reports (House Finance and House Passed against Governor
  Recommended; Senate Passed against House Passed; Committee of Conference
  against each);
- the agency budget requests (the printout gives no year) and House
  Finance's division detail.

It names no Ways and Means document (request 6 stays open).

### DAS: Summary of Budget Submissions by Agency, Total Funds

*Dated 9/28/2026, version 2028B01.* 56 agency rows: 46 departments and
agencies, and Health and Human Services' 10 divisions. Each row gives eight
columns:
- FY26 Actuals;
- FY27 Adj Auth;
- for FY28 and for FY29: the efficiency request, the prioritized needs, and
  the total agency request.

- **Checks:** every row's efficiency plus prioritized needs equals its
  request. Every column's rows sum exactly to the printed "Subtotal excluding
  DHHS" and "Subtotal DHHS", and those two to the grand total. Grand totals:
  - FY26 actuals: $8,005.6M.
  - FY27 adjusted authorized: $8,277.9M.
  - FY28 request: $9,093.6M (efficiency $8,795.3M plus prioritized needs
    $298.3M).
  - FY29 request: $9,318.0M (efficiency $8,988.6M plus prioritized needs
    $329.4M).
- **What it makes possible:**
  - **"Where it goes"** for the present budget, by department, under the
    summary's heading "Total Appropriations - Total Funds": fiscal 2026
    "actuals" and fiscal 2027 "adjusted authorized". Not the enacted HB 1
    amounts, and not by fund.
  - **"What agencies are asking for in 2028-2029"**, labelled as requests.
- **What it cannot:** split the money by fund (so it cannot say how much is
  federal); define "actuals" or "prioritized needs"; give anything below the
  agency. (The *statute* defines the adjusted authorized budget, RSA 9:4,
  IV(a), and the page quotes it. It also puts prioritized "special or
  problematic needs" inside the efficiency request, IV(f), so the page does
  not let readers take the summary's "prioritized needs" column for those.)
- **Its own note:** the Legislative Branch submits no formal budget at this
  stage, and its FY28-29 figures repeat FY27.

### DAS: FY28-29 Department Name and Number Crosswalk

56 lines: 46 departments by name and five-digit number, plus the 10 HHS
divisions, all under HEALTH AND HUMAN SVCS DEPT, 00095. Every agency in the
summary is in it. The page uses it to add the ten HHS divisions together as
one department. The names are DAS abbreviations ("AGRICULT, MARKETS & FOOD
DEPT"). The mock shows them title-cased and expands nothing; open question 16.

### DAS: Capital Budget Presentation (Governor's Capital Budget Hearings, June 16, 2026)

One agency's capital requests for 2028-2029: $143.4M in all ($5.0M for the
ERP system, $56.3M for new courthouses, $82.1M for deferred maintenance). The
three parts add up to the total. Its slide of past DAS capital appropriations
gives $15,400,000 for 2025, the figure HB 25 printed for the department
(159:1, I). Its process slide names the steps from facility assessments to
"House Bill 25". **Its dates differ from the statute's in one place:** the
slide gives agency request forms as "Due by May 31st", where RSA 9:3-a gives
requests to the commissioner by May 1 and the commissioner's summary to the
Governor by May 31. The page states the statute's dates only.

### What the five make possible, and what is still missing

| Request | Now |
|---|---|
| 1. HB 1 section 1, enacted, by department and fund | **Still missing.** The LBA page lists it ("HB 1 Chaptered Final Version", PDF and Excel). The owner can save either. |
| 2. The enacted budget book | **Still missing**; request 1 would probably cover it (a guess until opened). The DAS summary gives total funds by department, as spent and as authorized, but not as enacted and not by fund. |
| 3. Actual revenue | **Done** (LBA collections), for the General and Education funds. |
| 4. The ACFR | Still missing; less needed now that the DAS summary gives FY26 actuals. |
| 5. The Governor's proposal | **Located**: listed on the LBA page; not saved. |
| 6. Ways and Means | Still missing; nothing on the LBA page. |
| 7. Conference reports | **Located**: listed on the LBA page; not saved. |
| 8. RSA 77 | Still missing. |
| New: the FY28-29 Final Statewide Agency Budget Book | Named by the owner (address in `sources/README.md`); not saved. |
| New: the exact addresses of the DAS summary and crosswalk | The README gives only das.nh.gov/budget/. The page links there until the owner gives the file addresses. |

---

## 2. Sources needed from the owner

The table below is the first block's list. Section 1a gives where each now
stands.

The owner saves these in a browser or files a printout (state sites refuse
scripted fetches, and this project does not pretend to be a browser). Nothing
here was fetched. **Where a page name or address is a guess, it says so.**

| # | What | Why | Where it officially lives |
|---|---|---|---|
| 1 | **Section 1 of HB 1 of 2025 (chapter 140): the department tables, sections 1.01 to 1.07**, as enacted | Where the money goes, by department and by fund; the all-funds total, federal included. The page's biggest gap. | The General Court publishes the enacted budget; the bill text on gc.nh.gov does not carry section 1. **Guess:** the Legislative Budget Assistant's budget pages, or the Department of Administrative Services' budget office. Ask the LBA if it is not obvious. |
| 2 | **The enacted operating budget document for fiscal 2026-2027** (the book with department totals by fund, often with a summary table) | The same, in a form with totals; a cross-check on request 1 | **Guess:** Department of Administrative Services, "State of New Hampshire Operating Budget, Fiscal Years 2026 and 2027". The exact title is a guess. |
| 3 | **Actual unrestricted revenue, fiscal 2024 and 2025** | How the last budget's estimates turned out; the page currently compares estimate with estimate only | **Guess:** the Department of Administrative Services' monthly revenue reports (year-end, June). |
| 4 | **The Annual Comprehensive Financial Report, fiscal 2025** | Actual spending and revenue, audited | Named by HB 1 itself (140:15): "the audited annual comprehensive financial report pursuant to RSA 21-I:8, II(a)". Published by the Department of Administrative Services (**guess** at the page). |
| 5 | **The Governor's budget proposal for fiscal 2026-2027** (February 2025), and the budget address if there is a text | The first step of the process, with figures: what was proposed against what passed | RSA 9:2 requires it by February 15. **Guess:** the Governor's office or the Department of Administrative Services publishes the "Governor's Executive Budget". |
| 6 | **A source on the Ways and Means committees' part in the budget** | The brief names House Ways and Means. Neither 2025 budget bill's docket shows it: both went to Finance in each chamber. The page says nothing about Ways and Means until a source does. | Perhaps the 2025-2026 House Rules the owner printed on 26 October 2026, if they cover it (**guess**); otherwise the LBA. |
| 7 | **The committee of conference reports** 2025-2865c (HB 1) and 2025-2871c (HB 2) | What the conference changed. Possibly already in `db/CandH_Reports.psv`; not checked this block. | The General Court; check the dump first. |
| 8 | **A source that RSA 77 was the interest and dividends tax** | The page places the repeal of RSA 77 (on hand) beside the interest and dividends estimate falling to nothing in fiscal 2027 (on hand), but nothing on hand says the two are the same tax. | The text of RSA 77 before 2025, or the Department of Revenue Administration's page on the tax (**guess**). |
| 9 | **Later: town and county budgets** | The brief's possible next phase | **Guess:** the Department of Revenue Administration's municipal forms (the MS-series). The site's County Government page already explains the county budget from RSA 24. |

---

## 3. The page

### Where it sits

**A Learn topic, "The State Budget", at `/learn/state-budget`, in How the State
Works, after The Governor and the Executive Council and before The Courts.**
The Learn section already has the voice, the margin headings, the sources
list and the "In the Record" pattern this needs, and a reader looking for how
the state works will look there. The Governor's page already ends at the
budget ("proposing the biennial (two-year) state budget"), so it is the
natural previous topic.

**And a way in from the bills.** HB 1's and HB 2's bill pages already show
the owner's bill note ("The state budget", "The budget trailer bill"). The
proposal is one line under that note: *How the budget works: The State
Budget*, linking here. That is a change to the bill page builder, which is not
this session's, so it goes to the manager as a request once the design is
approved.

Not a new top-level section: one page, linked from where people already are,
is "clean and simple, not a labyrinth". If town and county budgets come later
(request 9), they can be sections of County Government and Town Meeting, or a
second page, decided then.

### Sections

1. **Two Bills, Two Years.** The biennium; why two bills (Article 18-a
   limits a budget bill; RSA 9:2-a makes the trailer bill separate); both
   introduced in the House, with Article 18's words on money bills. Two
   boxes (the site's `l-who`), one per bill, with its chapter and date.
2. **Where the Money Comes From.** The four funds as one proportion bar
   (`l-bar`), then every source as a bar chart (`l-chart`), with every source
   by fund in a table in a fold. A note that these are estimates and are not
   all the money. A placeholder for the all-funds, federal-included total
   (request 1).
3. **Where It Goes.** The DAS summary's fiscal 2026 actuals by department,
   total funds, as a bar chart: the ten largest, then the rest together. HHS's
   ten agencies are added into one department, by the DAS crosswalk. Every
   department's fiscal 2026 actuals and fiscal 2027 adjusted authorized
   amounts are in a table in a fold. A note quotes RSA 9:4 IV(a)'s definition
   of the adjusted authorized budget, says the summary does not define
   "actuals", and that it does not split by fund. A placeholder
   remains for HB 1's own section 1 (request 1).
4. **Other Directions in HB 1.** The reductions the act directs, each with
   its section (which says how: some name accounts, one spreads its cut across
   other agencies), and the positions it abolishes. Kept apart from "Where It
   Goes" so that a list of cuts is not read as the budget's spending.
5. **The Capital Budget.** HB 25: its title since 1999, its committees,
   chapter 159, section 1's state appropriations by department (bar chart),
   the bonds that pay for it (159:7), set against RSA 9:8-b's bar on bonding
   the operating budget, RSA 9:3-a's calendar, and the 2026 hearings.
6. **How the Budget Is Made.** The site's timeline (`l-time`, as County
   Government uses for the county budget): RSA 9's calendar, then 2025's own
   dates and votes from the docket. The balanced-budget rule (RSA 9:8-b),
   quoted, with its bonded-debt and projected-lapse provisions. A
   placeholder for Ways and Means (request 6).
7. **What HB 2 Changed.** The analysis's 247 changes, verbatim and in order,
   in a fold, so the page does not choose which ones matter. The roll-call
   counts, linked to the bill pages.
8. **Compared With the Last Budget.** Fund totals as a table (2024-2025
   against 2026-2027, both as estimated), then the twelve largest sources as
   paired bars (the twelve largest in either budget, the rule stated on the
   chart), with the change at the end of each pair and every source's two
   amounts in a table in a fold. 2023's business taxes are its printed
   subtotal. A note that both are
   estimates and that a change in revenue estimates is not a change in
   spending. Six budgets'
   General and Education Fund estimates as a bar chart, not adjusted for
   inflation.
   Then *What Came In*: estimated against collected for fiscal 2024, 2025
   and 2026, as paired bars and a table, with a note that the LBA's figures
   are on a cash basis and HB 1 does not state its estimates' basis; and
   seven years of collections.
9. **Now Under Way: The 2028-2029 Budget.** Under a box saying "Requests,
   not a budget". The totals requested against fiscal 2027's adjusted
   authorized amount. RSA 9:4's own definition of the efficiency expenditure
   request, and "prioritized needs" named as undefined. The ten largest fiscal
   2028 requests as paired bars, the request hatched (the site's hatching for
   what is not, or not yet, the thing itself). Every department's FY28 and
   FY29 request in a fold. The Legislative Branch note. A placeholder for the
   Statewide Agency Budget Book.
10. **In the Record.** The bills, the committees, RSA 9, the articles.
11. **Where This Comes From.** Each source with the day it was read.

### Charts

Every chart uses a component the site already has: `l-bar` (proportion bar
and key, as on How a Bill Becomes Law) and `l-chart`/`l-bars` (labelled
horizontal bars with a scale, as on By the Numbers). Each has an `aria-label`
carrying its numbers, a table or the prose saying the same numbers, a title on
every bar for hover, and a direct label on every bar.

New CSS, all in `mock.css`, all on the site's tokens:

- **Four fund colours**, the one place the page needs categorical colour (four
  funds, part of a whole). Light `#2A64A8, #B9420B, #1A8456, #7A4BB0`; dark
  `#4F88D0, #CC7A35, #35A06E, #9A72D6`. Checked with the dataviz validator:
  light passes every check; dark passes with a colour-blindness warning in the
  6-8 band, which the direct key (amount and name beside each swatch) and the
  2px gaps answer. The site's own pine failed as a categorical slot (too dark
  and too grey), so it is not one of the four.
- **Single-series bars in pine**, the site's accent, not the status green By
  the Numbers uses for "Became Law" (that green means a bill passed).
- **Tighter table cells on a phone** for the two four-column comparison
  tables, which otherwise lost their Change column off the edge at 390px.
- **Paired bars** for the comparison: the earlier budget in the recessive grey
  (`--rule-2`), this one in pine.
- **On a phone, the bar's name goes above the bar.** By the Numbers' labels
  are short ("1989-1990"); "Real Estate Transfer Tax" is not, and side by side
  it squeezed the bars to slivers at 390px (seen in the first screenshots and
  fixed). A reason for a new layout rule: the labels are longer than any the
  component has carried.
- **The placeholder box**: dashed, in the "needs" colour the site already uses
  for an unfilled table row (`--st-table`).

No chart library, no script: the site draws its charts in HTML and CSS, and
so does this.

### From the explainer to the record

Every bill number is a link to its page (HB 1 and HB 2 of 2025, 2023 and
2021), where every printing, hearing, committee vote and roll call already
is, with how each member voted. The committees link to House Finance
(`committee/H34`) and Senate Finance (`committee/S07`). Every statute and
article links to the site's Laws pages, to the section (`/laws/9#s8-b`,
`/laws#part2-art18-a`). The page shows no member's vote itself: the bill
pages do that, and repeating party splits here would make the explainer an
argument.

### How it would be built

Like `learn_numbers.py`: **the figures computed at build time from the bill
texts, never typed.** A module would read HB 1's "Estimates of Unrestricted
Revenue" for every budget the dump holds, check every fund's lines against its
printed total (and stop the build if they disagree, the way the mock's
`figures.py` does), and hand the figures to the page. Preflight would hold the
parser to a fixture with known answers, and fail if a fund stops summing. The
misprint rule ($127,7000,000) becomes a named correction with its evidence,
not a silent fix. The prose would live in `civics.py` with the other topics.

---

## 4. Screenshots

Full page, on the site built from the kit (`build_all.py --local`, 47 steps,
0 failed), served locally:

- `screenshots/state-budget-390-light-{1,2}.webp`, `state-budget-390-dark-{1,2}.webp`
- `screenshots/state-budget-1280-light-{1,2}.webp`, `state-budget-1280-dark-{1,2}.webp`

No horizontal scroll at either width. The mock is the County Government page
with its article replaced, so the header, hub tabs, "On this page", "Cite this
page", pager and the all-topics list are the site's own and match the pages
beside it. The all-topics list says "The Fourteen Pages" with the new topic
after the Governor. A banner at the top says it is a mock.

---

## 5. Open questions, each with a recommended default

1. **Ship before section 1 arrives?** *Settled by the owner on 30 October
   2026: the page stays private until every detail is complete and current.*
   The DAS summary now gives where the money went by department in total
   funds, but HB 1's own amounts by fund still need request 1.
2. **Placement.** *Default: Learn, after The Governor and the Executive
   Council*, plus the one-line link under the bill note on HB 1 and HB 2
   (a request to the manager).
3. **Figures generated or typed?** *Default: generated at build*, like By the
   Numbers, with preflight checks that each fund sums to its printed total.
4. **The misprint.** *Default: use the fund total's figure, and say so on the
   page*, as the mock does.
5. **"Education Fund" or "Education Trust Fund"?** The bill prints EDUCATION
   FUND. *Default: the bill's name.* (The longer name is not used: no source
   on hand was read for it.)
6. **HB 2's 247 changes: verbatim list or grouped by subject?** Grouping is
   an editorial choice of what goes with what. *Default: verbatim, in the
   bill's order, in a fold*, each linked to its section in the text.
7. **The reductions table.** It is what the act says, but it is a list of
   cuts with no list of increases beside it (the increases are in section 1,
   not on hand). *Default: keep it in its own section, "Other Directions in
   HB 1", and ship it only with the department chart from request 1*, so the
   page shows both.
8. **Inflation.** The six-budget chart is in dollars of each year. *Default:
   no adjustment*, and the chart says so; adjusting needs a price index from
   a source on hand.
9. **How far back.** *Default: six budgets, 2016-2017 to 2026-2027*, the run
   where every table parses and sums. Earlier ones only if the owner wants
   them; the 1999-2013 pages need reading first.
10. **The interest and dividends line.** The repeal of RSA 77 (on hand) sat
    beside the fall in the estimate in the first draft; the review read it as
    implying cause, and it is out of the mock. *Default: add it back only once
    request 8 confirms RSA 77 was that tax*, quoting the RSA note's own words.
11. **Spanish.** *Default: later*, through the guides session, once the
    English is approved (new keys flagged in `lang/es.json` then).
12. **Party breakdown of the budget votes.** *Default: no*; the bill pages
    have every vote, and the explainer stays neutral by linking to them.
13. **The four fund colours** need adding to `app.css` (shared). *Default:
    as validated here*, through the manager.
14. **Estimated against collected.** The LBA's collections are on a cash
    basis; nothing on hand says HB 1's estimates are. *Default: show the
    comparison with that caveat on the page*, and ask the LBA (or the owner)
    for a source on the estimates' basis before shipping.
15. **Source by source, collected against estimated.** Possible for lines
    whose names plainly match: meals and rooms, tobacco, real estate
    transfer, business taxes. Others need a mapping, such as "Liquor Sales and
    Distribution" against "Transfer from Liquor", or "Lottery" plus "Video
    Lottery Terminal Revenue" against "Transfer from Lottery". *Default:
    totals only*, until a source gives the mapping.
16. **Department names.** DAS prints abbreviations. *Default: each
    department's name as its own statute or website gives it*, checked one by
    one at build, with the DAS number kept beside it. The mock title-cases the
    DAS names and expands nothing.
17. **FY2027 "adjusted authorized" against HB 1.** *Default: quote RSA 9:4
    IV(a)'s definition, which already says why it is not simply HB 1's
    figure*, and show both once request 1 is on hand.
18. **How long the requests section stays.** It is current only until the
    Governor's budget (due by February 15, 2027, by RSA 9:2). *Default: the
    page carries the date the summary was dated, and the section is replaced
    by the Governor's recommended budget when that is saved.*
19. **HB 282 on the LBA's budget page.** *Default: leave it off the page*
    until a source says what part of the budget it is.
20. **Wide tables on a phone.** The every-source and every-department
    tables scroll sideways inside their folds at 390px, as By the Numbers'
    tables do; the page itself does not. *Default: keep the site's pattern.*
21. **Town and county budgets.** *Default: a later phase*, after request 9,
    probably as sections of the existing County Government and Town Meeting
    pages rather than new pages.

---

## How the mock was made

All scratch; nothing outside this folder was written. Run from the repository
root with Python 3.14, the kit taken down read-only into a scratch folder
`KIT` (`src/ops/cloud.py kit-down --root KIT`, with `cloud_kit.json` copied in),
and the site built there with `build_all.py --local`.

```
python3 -I tools/extract_budget.py KIT OUT/          # every printing of HB 1/HB 2 of 2025, as text
python3 -I tools/estimates.py KIT OUT/HB1_2025_*CHAPTERED*.txt estimates.json
python3 -I tools/figures.py estimates.json figures.json   # checks each fund sums to its total
python3 -I tools/history.py estimates.json history.json   # the six budgets
python3 -I tools/mock.py KIT/site figures.json history.json KIT/site/learn/state-budget.html
node tools/shoot.js http://127.0.0.1:8765 SHOTS budget=/learn/state-budget.html
```

`mock.py` reads `mock.css` from beside itself. The docket dates and votes in
the timeline are copied from the docket lines (section 1 above names them);
in the built page they would be read from the docket.

---

## The adversarial review of block 1 (30 October 2026)

A fresh reviewer recomputed every figure against the bill texts, docket and
roll calls and found none wrong. It found these, all fixed in the mock and
this document:

- *Reductions "each to be found by the department itself"*: not so (140:9
  spreads IT's cut across other agencies; 140:16 names two accounts; 140:15
  lets the Liquor Commission count excess revenue). Dropped, and the table
  moved to a section of its own.
- *"Two bills because the constitution requires it"*: Article 18-a limits a
  budget bill; RSA 9:2-a makes the trailer bill separate. Both now cited for
  what each says. *"Both begin in the House, because every money bill must"*:
  nothing on hand calls HB 2 a money bill; now the docket fact and the
  article's words, no "because".
- *"After 26 roll calls"*: the 26th was passage itself. Reworded.
- *HB 2 "in force July 1, 2025"*: 141:461 says "unless otherwise specified";
  now "most of it".
- *RSA 9:8-b paraphrase narrower than the statute*: now quoted, with the
  bonded-debt and projected-lapse provisions.
- *2023's business taxes "added together"*: the bill prints a subtotal; now
  cited as the subtotal. "Largest single source" is now "largest line".
- *The RSA 77 sentence implied cause*: removed (open question 10).
- *The comparison chart's selection rule was unstated*: now on the chart, with
  a table of both amounts, since phones have no hover.
- *Fish and Game grey in the 1280 screenshots*: my 256-colour compression of
  the PNGs mapped the small purple area to grey. The screenshots are now
  lossless WebP.
- *The 390px fund table lost its Change column*: tightened.
- *Counts in this document*: 26 lines (not 22), sections 141:1-461 (not 453),
  the Senate Finance date is the report's; and `figures.json` keyed the fund
  "Education Trust Fund", a name no source on hand prints. Now "Education
  Fund".
- *Item 247 paraphrased loosely*: now quoted.

## The adversarial review of block 2 (30 October 2026)

A fresh reviewer recomputed every new figure (the LBA collections, the DAS
summary and crosswalk, the capital presentation, HB 25) and found none wrong.
It found these, all fixed:

- *"Adjusted authorized" called undefined*: RSA 9:4 IV(a) defines it. Now
  quoted on the page.
- *"Actuals" glossed as "spent"*: the summary's heading is "Total
  Appropriations - Total Funds". The page now uses its words.
- *"Each request comes in two parts"*, set beside the statute's definition:
  the two parts are the summary's columns, and RSA 9:4 IV(f) puts
  prioritized needs inside the efficiency request. Reworded, with IV(f)
  quoted. The RSA 9:4 II quote is now marked as cut short.
- *The capital borrowing read as borrowing "from" the funds*: now 159:7's
  "source of funds", with the $23,381,950 of other funds explained by its
  three "Less Other Funds" lines. Fish and Game is quoted ("Net State 0")
  rather than called "no state appropriation".
- *The DAS slide's "Due by May 31st" against RSA 9:3-a's May 1*: recorded
  above.
- Smaller points:
  - "Ten divisions" is now "ten agencies", and "the department's own
    crosswalk" is now "the DAS crosswalk".
  - "They were held in June 2026" is now the one June 16 hearing on hand.
  - The Legislative Branch note moved above the requests chart, since the
    totals include it.
  - RSA 9:8-b's "to fund operating appropriations" is restored.
  - HB 25's title is dated from 1999, not 2015.
- *Stale lines here*: "placeholder for actuals", "requests of 2024", and
  request 2's unmarked guess. Fixed.
- *The estimated-against-collected note*: now names which HB 1 each year's
  estimate comes from, as enacted, and that the LBA file is a revised
  edition.
- *Visuals*:
  - The capital chart's caption now says Transportation's section 2 money is
    not in it.
  - The requests chart's scale shows its last figure on a phone.
  - "Nh" and "Of The" are fixed in the title-cased DAS names.
