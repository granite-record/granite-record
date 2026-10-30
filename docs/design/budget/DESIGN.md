# The State Budget: design (phase 1)

A design for a Learn page that explains New Hampshire's state budget in plain
words, with charts: where the money comes from and where it goes, how the
budget is made, and how it changed from the last one. **Nothing here is on the
site.** It reaches the site only after the owner approves the design.

Written 30 October 2026 on branch `design/budget`. Every figure in the mock was
read that day from a source on hand, named beside it. Where no source is on
hand the mock shows a dashed placeholder and this document lists what is
needed.

What is in this folder:

| Path | What it is |
|---|---|
| `DESIGN.md` | this document |
| `screenshots/state-budget-{390,1280}-{light,dark}.webp` | the mock, full page, on the real built site |
| `mock/state-budget.html` | the mock page as built (it needs the site's `/app.css`, so open it inside a built `site/`) |
| `tools/` | the scratch scripts that read the sources and draw the mock (below, *How the mock was made*) |
| `figures/figures.json`, `figures/history.json` | every figure the mock uses, as read from the bill texts, with each fund's lines checked against its printed total |

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

---

## 2. Sources needed from the owner

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
3. **Where It Goes.** Only a placeholder for the department chart (requests
   1 and 2), and a sentence saying the amounts, increases and decreases
   alike, are in section 1.
4. **Other Directions in HB 1.** The reductions the act directs, each with
   its section (which says how: some name accounts, one spreads its cut across
   other agencies), and the positions it abolishes. Kept apart from "Where It
   Goes" so that a list of cuts is not read as the budget's spending.
5. **How the Budget Is Made.** The site's timeline (`l-time`, as County
   Government uses for the county budget): RSA 9's calendar, then 2025's own
   dates and votes from the docket. The balanced-budget rule (RSA 9:8-b),
   quoted, with its bonded-debt and projected-lapse provisions. A
   placeholder for Ways and Means (request 6).
6. **What HB 2 Changed.** The analysis's 247 changes, verbatim and in order,
   in a fold, so the page does not choose which ones matter. The roll-call
   counts, linked to the bill pages.
7. **Compared With the Last Budget.** Fund totals as a table (2024-2025
   against 2026-2027, both as estimated), then the twelve largest sources as
   paired bars (the twelve largest in either budget, the rule stated on the
   chart), with the change at the end of each pair and every source's two
   amounts in a table in a fold. 2023's business taxes are its printed
   subtotal. A note that both are
   estimates and that a change in revenue estimates is not a change in
   spending. A placeholder for actuals (requests 3 and 4). Six budgets'
   General and Education Fund estimates as a bar chart, not adjusted for
   inflation.
8. **In the Record.** The bills, the committees, RSA 9, the articles.
9. **Where This Comes From.** Each source with the day it was read.

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

- `screenshots/state-budget-390-light.webp`, `state-budget-390-dark.webp`
- `screenshots/state-budget-1280-light.webp`, `state-budget-1280-dark.webp`

No horizontal scroll at either width. The mock is the County Government page
with its article replaced, so the header, hub tabs, "On this page", "Cite this
page", pager and the all-topics list are the site's own and match the pages
beside it. The all-topics list says "The Fourteen Pages" with the new topic
after the Governor. A banner at the top says it is a mock.

---

## 5. Open questions, each with a recommended default

1. **Ship before section 1 arrives?** Without request 1 the page says where
   the money comes from but not where it goes. *Default: wait.* A budget page
   with no spending is half a page; the revenue and process sections are
   ready to go the day request 1 is.
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
14. **Town and county budgets.** *Default: a later phase*, after request 9,
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

## The adversarial review (30 October 2026)

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
