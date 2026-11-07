# Members-elect polish: what the walk of dry run 4 found, as Alice answered it

The branch is `fix/members-elect-polish`, on top of dev 92247871 (dry run 6, which was clean).
The laptop manager asked for it on 7 November 2026, about 5 p.m., with Alice's four answers to
the walk list's "From the walk of dry run 4". She asked for it in one batch for one last dry run
on Sunday morning.

## What was wrong, and what it does now

### 1. The Members-Elect tab was cut off at laptop width

**Before.** With its seventh tab, the Officials strip needed 1,282px of its 1,132 at 1280 and at
1440. "Members-Elect (405)" showed only as "Mem" behind the edge, and the Spanish "Miembros
electos (405)" as "Miemb".

**Now.** Four tabs say a shorter name, with their counts. The panels below them keep the whole
name as their heading, which a screen reader walking the headings and a page read without the
script still get. Each Spanish word is a draft.

| Tab | English | Spanish | Its panel's heading |
|---|---|---|---|
| (unchanged) | My Town | Mi municipio | My Town |
| (unchanged) | Legislators (406) | Legisladores (406) | Legislators |
| federal | **Federal (4)** | **Federal (4)** | Federal Delegation / Delegación federal |
| executive | **Executive (26)** | **Ejecutivo (26)** | Executive Branch / Poder Ejecutivo |
| judicial | **Judicial (29)** | **Judicial (29)** | Judicial Branch / Poder Judicial |
| counties | **County (80)** | **Condados (80)** | County Officials / Funcionarios del condado |
| (unchanged) | Members-Elect (405) | Miembros electos (405) | Members-Elect |

- "Condados" is plural: a reader of Spanish took "Condado (80)" for one county, and the tab is
  the ten counties' (the review of 7 November 2026).
- Measured on dry run 6 with the web fonts, the seven tabs take 1,016px in English and about
  979px in Spanish, of the strip's 1,132, at 1280 and at 1440.
- Below 1024px the strip scrolls with its edge's shadow, as before. On a phone only the labels
  are shorter.
- The search rows (find.json) keep the panels' whole names.

### 2. "Your rep" on members-elect who are not the reader's rep in that seat

**Before.** With a town saved in the header, find.js's ytMark tags every link to one of the
town's members "Your rep" or "Your senator", and a list of members-elect is links.
- In Antrim, "Jim Creighton (R)" under State Senate — district 8 read "Your rep". He is a
  representative of Hillsborough 30, elected to the Senate.
- In Derry, Charles Foote alone of Rockingham 13's eight winners read "Your rep". That is
  right: he was re-elected to his own seat.

**Now, Alice's rule.** The tag stays on a member re-elected to the seat they hold. It goes
where the person is elected to a different seat, and from anyone not now holding that seat.
The same on the town pages, the district map and the Officials Members-Elect tab.
- `build_members_elect.py` writes `"own": true` on a sitting member whose seat is the race's
  (`seat_of`). On dry run 6's data that is 206 of the 213 sitting winners. The other seven are
  Creighton (S8), Telerski (S13), Gruber, Parshall, Cormen, Larochelle and Wade.
- `components.elect_race` and `components.electRace` mark such a winner's item
  `<li class="elown">`, only where it links to a page.
- ytMark adds `.ellist > li:not(.elown) a::after{content:none !important}`. That is the
  winners' own list, which every place draws: a town page's block, the map's panel and the
  Officials tab, which has no `.elect` round it.

### 3. From 2 December, `/officials#members-elect` was a blank page

**Before.** The tab hides itself from 2 December, by the build or by the reader's own date. An
address naming it opened six tabs, none chosen, with nothing under them.

**Now.** It opens Legislators, which the tab's own intro said "lists who holds each seat", and
writes `#legislators` into the address.
- Between the reader's midnight and the 2 December build, the tab is still drawn, retired.
  TABS_JS treats a tab as retired when it is hidden or its `data-until` day has come, by the
  reader's date as components.js judges it. It opens the strip's `data-retired` tab
  (Legislators on the Officials page) for its address, or for something inside its panel.
  The arrow keys, Home and End pass over it.
- From the 2 December build the tab is not drawn at all. OFFICIALS_HASH_JS sends
  `#members-elect`, `#of-elect-senate` and `#of-elect-house` to `#legislators` while nothing
  on the page has that id.
- Once the page has loaded, a reader sent this way is shown the strip, with Legislators chosen,
  so that nothing hides where they were sent. A reader who has scrolled on is not moved.
- With no address the page still opens My Town. A town page, whose strip names no
  `data-retired` tab and has no retiring tab, is as it was.

### 4. The Spanish heads of a members-elect block

They are "Elección del {day}" and "Toma de posesión: {day}.", as drafts in es.json, in place
of "Elegidos el" (plural, over one senator) and "Asume el cargo el" (singular, over a list).
The Members-Elect tab's own intro is unchanged.

### And the two small ones

- **A long status on a record's head wraps in its 18rem chip.** On `/bill/2026/cacr13`,
  "Passed both chambers, not ratified by the voters" ran 87px out of its chip and the page 16px
  sideways at 1280, and 66px at 1024. On live, "... went to the voters in November 2026" runs
  128px. Below 45em every chip already wrapped. (`.rtop > .chip`, `white-space:normal`.)
- **A member's chip that asks more than 290px gets it.** "Rep. Katherine Prudhomme-O'Brien (R
  - Rock 13)" asks 383px, and on Derry's page it ran under "kpo@gc.nh.gov".
  - A row whose first cell is a member's chip (`.offrow:has(> .offwho > .mchip)`, above phone
    width) gives the chip what it asks. Its address moves right on that row alone.
  - A shorter name keeps the 290px line, every other row is as it was, and a browser without
    `:has()` keeps the 290px.
  - At 1280 her address breaks at its `<wbr>` onto two lines, beside the chip rather than
    under it.

## The shots

The before shots are dry run 6 (https://7c76e0a0.graniterecord.pages.dev) as served. The after
shots are the same pages with this branch applied in the browser. Each is described below.
- The branch's app.css, components.js and find.js went through its own build_pages
  publishing. Dev's run of the same matched dry run 6's files byte for byte.
- The Officials HTML has the four labels, `data-retired`, and the branch's TABS_JS in place of
  dev's.
- The `own` flag was computed from dry run 6's members-elect and roster files with the branch's
  rule.
- The Spanish heads come from the branch's es.json.

| Shot | What it shows |
|---|---|
| `o1-before-1280-light`, `o1-after-1280-light`, `-1280-dark`, `-1440-light` | The Officials strip: "Mem" cut off, then all seven on one line. |
| `o1-before-390-dark`, `o1-after-390-dark` | On a phone the strip still scrolls; the labels are shorter. |
| `o2-before-1280-light`, `o2-after-1280-light`, `-1280-dark`, `o2-after-390-dark` | The same in Spanish. |
| `o3-before-1280-light`, `o3-after-1280-light`, `o3-after-390-dark` | `/officials#members-elect` with the clock at 2 December, 10 a.m.: blank, then Legislators with `#legislators` in the address. |
| `p1-before-1280-light`, `p1-after-1280-light`, `p1-after-390-dark` | Antrim saved, its State Senate district 8: Creighton's "Your rep" gone; Ruth Ward keeps "Your senator". |
| `p2-after-1280-light` | Derry saved, Rockingham 13: Foote keeps "Your rep". |
| `p3-before-1280-light`, `p3-after-1280-light`, `-1280-dark` | Antrim saved, the Officials Members-Elect tab's Senate District 8: Creighton's "Your rep" gone. |
| `s1-before-1280-light`, `s1-after-1280-light`, `s1-after-390-dark` | `/es/officials`, Mi municipio with Derry saved: the new Spanish heads. |
| `c1-before-1280-light`, `c1-after-1280-light`, `c1-after-1024-light` | CACR 13's status: off its chip and the page, then two lines inside it. |
| `d1-before-1280-light`, `d1-after-1280-light`, `d1-after-1024-light` | Derry's Prudhomme-O'Brien row: over her address, then clear of it. |

## The checks

- **New, `_elect_own_seat`.**
  - On the fixture's election, `own` is on Jodi Nelson and Debra Altschiller alone. It is not on
    a sitting member of another seat whom the hand file takes to be another race's winner.
  - The renderers mark only a linked own winner `elown`.
  - Every winner's link on the Officials tab and in a town page's block sits in a
    `<ul class="ellist">`, which ytMark's rule reaches. The rule comes after the rules that set
    the tag.
- **New, `_officials_tabs_fit_and_retire`.**
  - The short labels, English and Spanish, over the panels' whole headings, and es.json's
    drafts.
  - TABS_JS in node, in seven cases: the day before, the day itself, no address, a section
    inside the retired panel, the tab built hidden, a strip naming no tab for it, and an
    ordinary tab. Each covers load (and whether the strip is brought into view), End,
    ArrowLeft, a hashchange, and a page left open across midnight with the tab focused.
  - OFFICIALS_HASH_JS in seven cases, among them the tab not drawn at all.
- **Changed.** `_legislators_page_tabs`, `_executive_branch_renamed`, `_officials_heads_and_judges`
  and `_spanish_officials` read the short labels on the tabs and the whole names on the panels.
  The members-elect cases in tests/components_cases.json gain an own winner and an unlinked one.
  `elown` is a known class.
- **Mutants.** 24 of 25 each turn a check red, one per piece, in two runs: 19 on the first
  commit and 6 on what the reviews added. The 25th keeps `own` on a winner whose link "one
  person, one seat" took away. Nothing can draw it, because the renderers want a link too.
- **Two reviews**, one for correctness and one reading as Alice would, each with experiments in
  Chromium on dry run 6.
  - Their two blocking findings are fixed: the rule did not reach the Officials tab, and every
    town-page row widened, not just a member's.
  - So are their should-fix findings: the address after the 2 December build, "Condados", and
    the strip for a reader sent from a retired tab.
  - What stays the owner's call is under "Not here".
- **The town pages.** A sweep of all 320 on dry run 6, every panel shown and every `<details>`
  open, at 700, 820 and 1280, with this app.css in place. No page scrolls sideways and no
  contact column is squeezed. One row is past its edge, Plaistow's highway supervisor's phone,
  and dev's own app.css has it too.
- `preflight --code`: see the STATUS commit.

## Not here, for Alice to say

- **A long-named member's address.** At 1280 and 1440, where the House and Senate cards sit side
  by side, Prudhomme-O'Brien's address breaks onto two lines beside her chip ("kpo@ /
  gc.nh.gov"). Derry's House list then has address edges at 405, 411 and 499px. Seabrook's
  "Matt.Sabourin@ / gc.nh.gov" breaks the same way. Nothing overlaps any more.
  - One alternative the reader's review tried: when a member's chip is wider than the column,
    the address drops under the chip in one piece.
- **The English strip between 1024 and about 1062px** still scrolls, by up to 40px, with its
  edge's shadow; the chosen tab is always brought into view. Spanish fits there, on its
  tighter padding, which English could take too.
- **The My Town card** still says "The county's own officials are under County Officials", the
  panel's heading, over a tab that reads "County (80)". Any new wording would be a draft in
  Spanish too.
- The 2 December switch night itself is not exercised here. The cases above are the browser's
  side of it.
